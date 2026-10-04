#!/usr/bin/env python3
"""A trained run -> what the backend loads: model.onnx, tokenizer.json, laya.json.
usage: package.py <run_dir> <out_dir>   (in the shadowrealms-laya-train image)

As in RecMeets' scripts/laya/package.py: a 32-bit export (Laya's export_onnx.py),
then the matrix products in ONNX Runtime's 8-bit block format (MatMulNBits,
block 64, accuracy_level 4) and the 256,000-token embedding table in 8 bits per
tensor. Laya's default per-channel int8 quantizer (export_onnx.py --quantize)
broke RecMeets' fine-tune (constant outputs), so it is not used.
"""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from question import OOC_QUESTION, INTENT_QUESTION, INTENTS, state_of  # noqa: E402

import torch
from transformers import AutoTokenizer
from laya.agent import Agent, _fix_tokenizer_config

run, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
_fix_tokenizer_config(run)
tok = AutoTokenizer.from_pretrained(os.path.join(run, "tokenizer"))
cfg = json.load(open(os.path.join(run, "rl_agent_config.json")))
full = os.path.join(out, "full")
os.makedirs(full, exist_ok=True)

# 1. 32-bit export (Laya's scripts/export_onnx.py, Apache 2.0, inlined)
agent = Agent(run, compile=False, device="cpu")
dummy = (torch.randint(0, 100, (1, 16), dtype=torch.long), torch.ones((1, 16), dtype=torch.long),
         torch.tensor([[1, 5]], dtype=torch.long), torch.tensor([[True, True]], dtype=torch.bool),
         torch.tensor([0], dtype=torch.long))
names_in = ["input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype"]
dyn = {"input_ids": {0: "batch_size", 1: "seq_len"}, "attention_mask": {0: "batch_size", 1: "seq_len"},
       "marker_pos": {0: "batch_size", 1: "num_markers"}, "marker_mask": {0: "batch_size", 1: "num_markers"},
       "qtype": {0: "batch_size"}, "logits": {0: "batch_size", 1: "num_markers"}, "act_logits": {0: "batch_size"}}
torch.onnx.export(agent.model, dummy, os.path.join(full, "model.onnx"), export_params=True, opset_version=18,
                  do_constant_folding=True, input_names=names_in, output_names=["logits", "act_logits"],
                  dynamic_axes=dyn)  # torch 2.11 default exporter, as RecMeets ran it

# 2. 8-bit blocks for MatMul, 8-bit per-tensor embedding table
import onnx
from onnxruntime.quantization import QuantType, quantize_dynamic
from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer
q = MatMulNBitsQuantizer(onnx.load(os.path.join(full, "model.onnx")), bits=8, block_size=64, is_symmetric=True,
                         accuracy_level=4)
q.process()
mid = os.path.join(full, "blocks.onnx")
q.model.save_model_to_file(mid, use_external_data_format=False)
m = onnx.load(mid)
del m.graph.value_info[:]
quantize_dynamic(model_input=m, model_output=os.path.join(out, "model.onnx"), op_types_to_quantize=["Gather"],
                 weight_type=QuantType.QInt8, per_channel=False)
if os.environ.get("KEEP_FP32"):
    shutil.copy(os.path.join(full, "model.onnx"), os.path.join(out, "model.fp32.onnx"))
    for f in os.listdir(full):  # the export may write external data next to it
        if f not in ("model.onnx", "blocks.onnx"):
            shutil.copy(os.path.join(full, f), os.path.join(out, f))
shutil.rmtree(full)

# 3. tokenizer + the config infer.py needs (questions, special ids, temperatures)
shutil.copy(os.path.join(run, "tokenizer", "tokenizer.json"), os.path.join(out, "tokenizer.json"))
temps = cfg.get("temperature", [1.0, 1.0, 1.0])
json.dump({
    "model_name": cfg.get("model_name"),
    "questions": {"ooc": OOC_QUESTION, "intent": INTENT_QUESTION},
    "intents": INTENTS,
    "state_prefix": state_of(""),
    "max_len": cfg["max_len"], "head_max_len": cfg["head_max_len"],
    "cls": tok.cls_token_id, "sep": tok.sep_token_id, "mask": tok.mask_token_id, "pad": tok.pad_token_id,
    "mask_token": tok.mask_token,
    "qtypes": {"choice": 0, "score": 1, "noul": 2},
    "temperature": {"choice": temps[0], "noul": temps[2]},
}, open(os.path.join(out, "laya.json"), "w"), ensure_ascii=False, indent=1)
for f in sorted(os.listdir(out)):
    print(f, os.path.getsize(os.path.join(out, f)))
