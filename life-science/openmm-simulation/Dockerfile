# Use CUDA 12 runtime image for broad driver compatibility
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    build-essential \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Miniforge (conda-forge)
RUN curl -fsSL \
    "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh" \
    -o /tmp/miniforge.sh && \
    bash /tmp/miniforge.sh -b -p /opt/conda && \
    rm -f /tmp/miniforge.sh

ENV PATH="/opt/conda/bin:/root/.local/bin:$PATH"

# Install OpenMM with GPU support from conda-forge (Option A):
# https://docs.openmm.org/latest/userguide/application/01_getting_started.html
# cuda-version is pinned to 12 to avoid PTX incompatibilities.
RUN conda install -y -c conda-forge --strict-channel-priority \
    "openmm=8.4.*" "cuda-version=12" && \
    conda clean -afy

RUN mkdir -p /openmm/results
WORKDIR /openmm

# Copy project files
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY sim/ ./sim/
COPY assets/ ./assets/

# Install package with non-OpenMM dependencies from pyproject.
# We intentionally keep OpenMM from conda-forge to preserve CUDA platform support.
RUN uv pip install --python /opt/conda/bin/python --no-deps . && \
    uv pip install --python /opt/conda/bin/python \
      boto3 \
      requests \
      "matplotlib>=3.7.0" \
      "seaborn>=0.12.0" \
      "numpy>=1.24.0" \
      "pandas>=2.0.0" \
      "mdtraj>=1.9.8"

# Define the entrypoint using the modular approach
ENTRYPOINT ["python", "-m", "sim.run"]
