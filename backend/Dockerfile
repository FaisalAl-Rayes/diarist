# CUDA 12.4 has mature torch/ctranslate2 wheel support and is forward-
# compatible with recent NVIDIA drivers (works with driver 525.60.13+). If
# your GPU node runs an older driver, check the CUDA compatibility matrix at
# https://docs.nvidia.com/deploy/cuda-compatibility/ and adjust the base
# image tag accordingly.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/models \
    JOB_DATA_DIR=/data/jobs

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.11 \
      python3.11-venv \
      python3-pip \
      ffmpeg \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Install torch with CUDA 12.4 wheels first (large layer, changes rarely).
RUN pip install --index-url https://download.pytorch.org/whl/cu124 \
      "torch>=2.4,<3"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

RUN useradd --create-home --uid 1000 diarist \
    && mkdir -p /data/models /data/jobs \
    && chown -R diarist:diarist /app /data
USER diarist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python3.11 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python3.11", "-m", "diarist.main"]
