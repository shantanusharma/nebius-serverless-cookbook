# Serverless Cookbook

Runnable, workload-first examples for **Serverless AI Jobs and Endpoints** on Nebius.

This repository shows how to run real AI/ML workloads without managing VM lifecycle directly.  
Examples focus on practical use cases such as:

- model training
- fine-tuning
- batch inference
- LLM serving
- simulations and domain workloads

> ⚠️ This is a **community-style repository maintained by Nebius engineers**.  
> It is not official product documentation, but reflects real usage patterns and experiments.  
> APIs and behavior may evolve.  
>  
> For official documentation, see: https://docs.nebius.com/serverless

## Try a workload

Choose the path that best matches what you want to run:

- **First run** → [Quickstarts](./quickstarts/)
- **Training / fine-tuning** → [Training examples](./training/)
- **Inference / serving** → [Inference examples](./inference/)
- **Scientific / domain workloads** → [Life science examples](./life-science/)

## Getting started

1. Install the Nebius CLI: [Install guide](https://docs.nebius.com/cli/install)
2. Configure your CLI profile and project: [Configure guide](https://docs.nebius.com/cli/configure)
3. Pick an example from the sections below
4. Follow the example README and verify the expected output

## Example catalog

### 🚀 Quickstarts
Lowest-friction first runs.

- [`first-job.md`](./quickstarts/first-job.md) — run `nvidia-smi` in a Serverless AI job
- [`first-endpoint.md`](./quickstarts/first-endpoint.md) — deploy a quick `nginx` endpoint

### 🏋️ Training
Model training and fine-tuning workloads.

- [`axolotl-finetuning`](./training/axolotl-finetuning/README.md) — get started fine-tuning with Axolotl

### ⚡ Inference
Endpoint serving and batch inference workloads.

- [`vllm-endpoint`](./inference/vllm-endpoint/README.md) — serve Qwen with an OpenAI-compatible vLLM endpoint

### 🧬 Life Science
Domain-specific simulation and analysis workloads.

- [`openmm-simulation`](./life-science/openmm-simulation/README.md) — run GPU-backed molecular dynamics simulations with OpenMM

## Repository structure

```text
serverless-cookbook/
├─ README.md
├─ CONTRIBUTING.md
├─ DEVELOPER_GUIDE.md
├─ LICENSE
├─ quickstarts/
│  ├─ first-job.md
│  ├─ first-endpoint.md
├─ training/
│  ├─ axolotl-finetuning/
│  └─ ...
├─ inference/
│  ├─ vllm-endpoint/
│  └─ ...
├─ life-science/
│  ├─ openmm-simulation/
│  └─ ...
```

## Section guide

- `quickstarts/`: lowest-friction first runs.
- `training/`: model training and fine-tuning workloads.
- `inference/`: endpoint serving and batch inference workloads.
- `life-science/`: domain-specific simulation and analysis workloads.


## Resources

- [Contributing](./CONTRIBUTING.md)
- [Developer Guide](./DEVELOPER_GUIDE.md)
- [Serverless AI overview docs](https://docs.nebius.com/serverless/overview)
- [CLI AI reference](https://docs.nebius.com/cli/reference/ai/)
