# 1) Base image: CUDA + cuDNN + PyTorch runtime. Replace it when your framework
# or CUDA version requires a different base.
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

# 2) Stable UTF-8 output and unbuffered logs for real-time platform progress.
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 3) Common runtime libraries used by medical-imaging Python packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 4) The default MedVisora script path is /workspace/predict.py.
WORKDIR /workspace

# 5) Install all Python dependencies required by every workflow stage.
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt

# 6) Copy all stage model files into the image when stored in the build context.
# Keep these paths synchronized with the stage routes used by predict.py.
# COPY models/ /workspace/models/

# 7) Keep the platform adapter at the default path.
COPY predict.py /workspace/predict.py

# 8) Do not set ENTRYPOINT. MedVisora overrides CMD and invokes one stage with:
# python /workspace/predict.py --node-id ... --input ... --output ... --extra-params ...
CMD ["python", "/workspace/predict.py", "--help"]
