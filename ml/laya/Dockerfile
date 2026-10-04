# The training image: RecMeets' recmeets-laya-train (python 3.12, torch cu128,
# laya[serve] 0.3.21, transformers) plus what package.py needs for ONNX.
# Build it from scratch with RecMeets' Dockerfile if it isn't on the machine:
#   FROM python:3.12-slim
#   RUN pip install --index-url https://download.pytorch.org/whl/cu128 torch && \
#       pip install "laya[serve]" "transformers>=4.48" safetensors huggingface_hub accelerate scipy
FROM recmeets-laya-train:latest
RUN pip install -q onnx onnxruntime onnx-ir onnxscript
WORKDIR /ft
