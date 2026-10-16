# Speech service: CUDA runtime for faster-whisper (CTranslate2), CPU-only torch for Pocket TTS.
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/venv

# CPU torch first so pocket-tts does not pull the multi-GB CUDA build.
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt

COPY app /srv/app
WORKDIR /srv
RUN useradd -u 1000 -m speech || true
USER 1000

# Models are mounted read-only; never download at run time.
ENV VOICE_MODELS_DIR=/models VOICE_CACHE_DIR=/cache HF_HOME=/models/hf \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=2
CMD ["sh", "-c", "exec nice -n 10 uvicorn app.main:app --host ${SPEECH_HOST:-127.0.0.1} --port ${SPEECH_PORT:-5055} --workers 1 --no-access-log"]
