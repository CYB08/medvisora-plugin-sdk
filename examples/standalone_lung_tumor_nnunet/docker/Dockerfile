# 1) Base image: ships CUDA + cuDNN + PyTorch. Replace it when your framework
# or CUDA version requires a different base.
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

# 2) Timezone and UTF-8; PYTHONUNBUFFERED keeps PROGRESS lines real-time.
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 3) Minimal system libraries required by nnUNet (ITK behind SimpleITK, libgl).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# 4) Install Python dependencies. Append "-i <index-url>" if a closer PyPI
# mirror speeds up the build.
COPY requirements.txt /workspace/
RUN pip install --no-cache-dir -r requirements.txt

# 5) Install nnUNet from local source (git clone it into docker/nnUNet/ first,
# see the examples README).
COPY nnUNet/ /workspace/nnUNet/
RUN cd /workspace/nnUNet && pip install --no-cache-dir -e .

# 6) Standard nnUNet directories.
RUN mkdir -p /workspace/nnUNet_raw \
             /workspace/nnUNet_preprocessed \
             /workspace/nnUNet_results
ENV nnUNet_raw=/workspace/nnUNet_raw \
    nnUNet_preprocessed=/workspace/nnUNet_preprocessed \
    nnUNet_results=/workspace/nnUNet_results

# 7) Weights for both stages plus the inference script. Put your own weights
# into nnUNet_results/ before building; see the README in that folder.
COPY nnUNet_results/ /workspace/nnUNet_results/
COPY predict.py /workspace/

# 8) Do not set ENTRYPOINT. MedVisora overrides CMD and invokes
# "python /workspace/predict.py --node-id ... --input ... --output ...".
CMD ["python", "/workspace/predict.py", "--help"]
