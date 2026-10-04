# Adapted from Laya's fine-tuning notebook (notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb,
# github.com/NandhaKishorM/laya, Apache 2.0) via RecMeets' scripts/laya/train.py: one GPU, our items.
# Changes for ShadowRealms: the model name, MICRO_BATCH / GRAD_ACCUM from the environment,
# FREEZE_EMBEDDINGS, and lower GPU memory (bucket-view gradients, AdamW foreach=False).
# usage: torchrun --standalone --nproc_per_node=1 train.py <base_dir> <run_dir> <items.pt>
import os, sys, time, json, random, math
import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from safetensors.torch import load_file, save_file
from transformers import AutoTokenizer
from laya.common import build_model, proper_reward, QTYPES

def collate_train_batch(items, pad_id):
    n, L = len(items), max(len(it["ids"]) for it in items)
    kmax = max(len(it["markers"]) for it in items)
    ids = torch.full((n, L), pad_id, dtype=torch.long)
    att = torch.zeros((n, L), dtype=torch.long)
    mpos = torch.zeros((n, kmax), dtype=torch.long)
    mmask = torch.zeros((n, kmax), dtype=torch.bool)
    target = torch.zeros((n, kmax), dtype=torch.float32)
    for i, it in enumerate(items):
        ids[i, : len(it["ids"])] = torch.tensor(it["ids"])
        att[i, : len(it["ids"])] = 1
        k = len(it["markers"])
        mpos[i, :k] = torch.tensor(it["markers"])
        mmask[i, :k] = True
        target[i, : len(it["target"])] = torch.tensor(it["target"], dtype=torch.float32)
    return {
        "input_ids": ids,
        "attention_mask": att,
        "marker_pos": mpos,
        "marker_mask": mmask,
        "target": target,
        "qtype": torch.tensor([it["qtype"] for it in items]),
        "label": torch.tensor([it["label"] for it in items])
    }

def fit_one_temp(sel):
    if len(sel) < 10:
        return 1.0
    kmax = max(len(z) for z, _ in sel)
    Z = torch.full((len(sel), kmax), -1e4)
    T = torch.zeros((len(sel), kmax))
    for i, (z, t) in enumerate(sel):
        Z[i, :len(z)] = torch.tensor(z)
        T[i, :len(t)] = torch.tensor(t, dtype=torch.float32)
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=100)
    def closure():
        opt.zero_grad()
        loss = -(T * torch.log_softmax(Z / log_t.exp(), -1)).sum(-1).mean()
        loss.backward()
        return loss
    opt.step(closure)
    return float(torch.clamp(log_t.exp(), 0.1, 10.0).item())

def main():
    dist.init_process_group("nccl")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank)

    model_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    with open(os.path.join(model_dir, "rl_agent_config.json")) as f:
        cfg = json.load(f)
    cfg["gradient_checkpointing"] = True
    cfg["max_tokens_per_batch"] = 4096
    cfg["max_len"] = 1024
    cfg["head_max_len"] = 256

    tok = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))
    model = build_model(cfg, encoder_dir=os.path.join(model_dir, "encoder"))
    
    weights = load_file(os.path.join(model_dir, "model.safetensors"))
    model.load_state_dict(weights, strict=True)
    
    # FREEZE_EMBEDDINGS=1: keep mmBERT's 256,000-token embedding table (197M of the 322M
    # parameters) fixed. Weights + grads + AdamW state then need ~2.5 GB instead of ~5 GB,
    # which is what fits next to LM Studio and ComfyUI on the shared 16 GB card.
    if os.environ.get("FREEZE_EMBEDDINGS", "0") == "1":
        emb = model.encoder.embeddings.tok_embeddings
        emb.weight.requires_grad_(False)
        emb.half()  # frozen, so fp16 storage loses nothing in training and saves 0.4 GB
    model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.head_checkpointing = True
    model.to(device)
    model.train()

    ddp_model = DDP(model, device_ids=[local_rank], find_unused_parameters=True,
                    gradient_as_bucket_view=True)  # no second copy of the gradients (memory)
    
    all_items = torch.load(sys.argv[3], weights_only=False)

    # Hold the calibration slice out of training before sharding. Temperatures fitted on
    # items the run has already trained on measure the fit rather than the calibration: the
    # model is near-certain and near-correct on them, so the optimiser has nothing to soften
    # and returns a degenerate scale. The seed is fixed and rank-independent, so every rank
    # withholds exactly the same items and none of them reaches a training batch.
    CALIB_MAX = 400
    order = list(range(len(all_items)))
    random.Random(20260922).shuffle(order)
    n_calib = min(CALIB_MAX, len(all_items) // 10)
    calib_items = [all_items[i] for i in sorted(order[:n_calib])]
    train_items = [all_items[i] for i in sorted(order[n_calib:])]
    my_items = train_items[rank::world_size]
    
    EPOCHS = int(os.environ.get("EPOCHS", "3"))
    MICRO_BATCH = int(os.environ.get("MICRO_BATCH", "8"))  # sequences per forward pass per GPU
    GRAD_ACCUM = int(os.environ.get("GRAD_ACCUM", "4"))      # Effective batch across 2 GPUs = 64 sequences (8 * 2 * 4)
    GROUP_SIZE = 4       # GRPO baseline samples
    LR_ENCODER = 2.5e-5  # Encoder adaptation rate
    LR_HEAD = 1.0e-4     # Head adaptation rate
    # A continuation (from a fine-tuned run) learns gentler: LR_SCALE=0.3, say.
    LR_ENCODER *= float(os.environ.get("LR_SCALE", "1"))
    LR_HEAD *= float(os.environ.get("LR_SCALE", "1"))
    SIGMA_START = 0.4    # Exploration noise
    SIGMA_END = 0.1

    enc_params = [p for n, p in ddp_model.named_parameters() if "encoder." in n and p.requires_grad]
    head_params = [p for n, p in ddp_model.named_parameters() if "encoder." not in n and p.requires_grad]
    
    optimizer = torch.optim.AdamW([
        {"params": enc_params, "lr": LR_ENCODER},
        {"params": head_params, "lr": LR_HEAD}
    ], weight_decay=0.01, foreach=False)  # foreach=False: no multi-tensor temporaries (memory)
    
    total_updates = (len(my_items) // (MICRO_BATCH * GRAD_ACCUM)) * EPOCHS
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, total_updates), eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    
    if rank == 0:
        print(f"Starting training: {len(train_items)} train items ({len(calib_items)} held out for calibration) | {len(my_items)} per rank | {EPOCHS} epochs")
    t0 = time.time()
    
    def save_calibrated(out_dir):
        """Fits the temperatures on the held-out calibration slice and saves
        the model, tokenizer and config into `out_dir`."""
        model.eval()
        calib_preds = []
        with torch.no_grad():
            for c_idx in range(0, len(calib_items), 16):
                c_chunk = calib_items[c_idx:c_idx + 16]
                cb = collate_train_batch(c_chunk, tok.pad_token_id)
                with torch.autocast("cuda", dtype=torch.float16):
                    l_sub, _ = model(cb["input_ids"].to(device), cb["attention_mask"].to(device),
                                     cb["marker_pos"].to(device), cb["marker_mask"].to(device), cb["qtype"].to(device))
                l_np = l_sub.float().cpu().numpy()
                for r, it in enumerate(c_chunk):
                    k = len(it["markers"])
                    calib_preds.append((it["qtype"], l_np[r, :k], it["target"]))
        fitted = [1.2, 1.2, 1.2]
        try:
            for qt in range(3):
                sel = [(z, t) for q_type, z, t in calib_preds if q_type == qt]
                if sel:
                    fitted[qt] = fit_one_temp(sel)
        except Exception as e:
            print("Temperature fitting fallback:", e)
        os.makedirs(out_dir, exist_ok=True)
        sd = {k: v.half().contiguous().cpu() for k, v in model.state_dict().items()}
        save_file(sd, os.path.join(out_dir, "model.safetensors"))
        model.encoder.config.save_pretrained(os.path.join(out_dir, "encoder"))
        tok.save_pretrained(os.path.join(out_dir, "tokenizer"))
        c = dict(cfg)
        c["fine_tuned"] = True
        c["model_name"] = "laya-shadowrealms-chat"
        c["temperature"] = fitted
        c.pop("temperature_by_options", None)
        with open(os.path.join(out_dir, "rl_agent_config.json"), "w") as f:
            json.dump(c, f, indent=2)
        print(f"  Saved {out_dir} (temperatures {[round(t, 3) for t in fitted]})")

    for epoch in range(EPOCHS):
        random.seed(42 + epoch + rank)
        random.shuffle(my_items)
        epoch_loss, n_batches = 0.0, 0
        optimizer.zero_grad(set_to_none=True)
        accum_step = 0
        
        progress = epoch / max(1, EPOCHS - 1)
        sigma = SIGMA_START + (SIGMA_END - SIGMA_START) * progress
        
        for b_idx in range(0, len(my_items), MICRO_BATCH):
            chunk = my_items[b_idx:b_idx + MICRO_BATCH]
            if not chunk:
                continue
            
            batch = collate_train_batch(chunk, tok.pad_token_id)
            
            with torch.autocast("cuda", dtype=torch.float16):
                logits, act = ddp_model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                    batch["marker_pos"].to(device),
                    batch["marker_mask"].to(device),
                    batch["qtype"].to(device)
                )
            
            logits = logits.float()
            mask = batch["marker_mask"].to(device)
            k = mask.sum(-1, keepdim=True).float()
            target = batch["target"].to(device)
            
            # 1. Sample G noisy logit distributions with zero-mean projection
            eps = torch.randn((GROUP_SIZE,) + logits.shape, device=device) * sigma * mask
            eps = (eps - eps.sum(-1, keepdim=True) / k) * mask
            z = logits.detach().unsqueeze(0) + eps
            q = torch.softmax(z.masked_fill(~mask, -1e4), -1)
            
            # 2. Evaluate proper scoring reward (w_sph=0.75 for soft target matching)
            with torch.no_grad():
                r = proper_reward(q, target.unsqueeze(0), batch["qtype"].to(device), mask, w_sph=0.75, w_rps=1.0)
                adv = r - r.mean(0, keepdim=True)
                adv = adv / (adv.std() + 1e-6)
            
            # 3. Policy gradient loss + full 1.0 soft cross-entropy guidance
            logp = -(((z - logits.unsqueeze(0)) ** 2) * mask).sum(-1) / (2 * sigma ** 2)
            loss_rl = -(adv * logp).mean()
            loss_ce = -(target * torch.log_softmax(logits.masked_fill(~mask, -1e4), -1)).sum(-1).mean()
            loss = (loss_rl + 1.0 * loss_ce) / GRAD_ACCUM + 0.0 * act.sum()
            
            scaler.scale(loss).backward()
            accum_step += 1
            
            if accum_step % GRAD_ACCUM == 0 or (b_idx + MICRO_BATCH) >= len(my_items):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(ddp_model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
            
            epoch_loss += loss.item() * GRAD_ACCUM
            n_batches += 1
            
            if rank == 0 and (n_batches % 50) == 0:
                cur_lr = scheduler.get_last_lr()[0]
                print(f"  Epoch {epoch+1}/{EPOCHS} | Step {n_batches} | Loss: {loss.item()*GRAD_ACCUM:.4f} | Reward: {r.mean().item():.3f} | LR: {cur_lr:.2e}")

        if rank == 0:
            print(f"=== Epoch {epoch+1}/{EPOCHS} Completed in {time.time()-t0:.1f}s | Avg Loss: {epoch_loss/max(1, n_batches):.4f} ===")

        dist.barrier()

        # Each epoch saved whole (calibrated, with its config), so every
        # epoch can be measured and the best one kept (RecMeets, 2026-09-29).
        if rank == 0:
            save_calibrated(os.path.join(output_dir, f"epoch-{epoch+1}"))
            model.train()
    dist.barrier()
    # The last epoch is also the run's own folder, as before.
    if rank == 0:
        save_calibrated(output_dir)
    dist.destroy_process_group()

if __name__ == "__main__":
    main()
