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

Pick the section that matches your goal — each links to runnable examples:

- 🚀 [**Quickstarts**](./quickstarts/) — lowest-friction first runs.
- 🏋️ [**Training**](./training/) — model training and fine-tuning workloads.
- ⚡ [**Inference**](./inference/) — endpoint serving and batch inference workloads.
- 🔁 [**MLOps / Pipelines**](./mlops/) - orchestration, artifact handoffs, and multi-stage workflows.
- 🧬 [**Life Science**](./life-science/) — domain-specific simulation and analysis workloads.
- 🤖 [**Robotics**](./robotics/) — simulation, dataset generation, and robotics workflows.

## Getting started

1. Install the Nebius CLI: [Install guide](https://docs.nebius.com/cli/install)
2. Configure your CLI profile and project: [Configure guide](https://docs.nebius.com/cli/configure)
3. Pick an example from the sections below
4. Follow the example README and verify the expected output
   - Optional: shared setup helpers live in [`scripts/README.md`](scripts/README.md)

## Example catalog

### 🚀 Quickstarts
Lowest-friction first runs.

- [`first-job.md`](./quickstarts/first-job.md) — run `nvidia-smi` in a Serverless AI job
- [`first-endpoint.md`](./quickstarts/first-endpoint.md) — deploy a quick `nginx` endpoint

### 🏋️ Training
Model training and fine-tuning workloads.

- [`axolotl-finetuning`](./training/axolotl-finetuning/README.md) — get started fine-tuning with Axolotl
- [`train-and-serve`](./training/train-and-serve/README.md) — fine-tune TinyLlama in a Job and serve it with a vLLM Endpoint

### ⚡ Inference
Endpoint serving and batch inference workloads.

- [`vllm-endpoint`](./inference/vllm-endpoint/README.md) — serve Qwen with an OpenAI-compatible vLLM endpoint

### 🔁 MLOps / Pipelines
Workflow orchestration and artifact handoff patterns.

- [`video-transcription-pipeline`](./mlops/video-transcription-pipeline/README.md) - orchestrate Object Storage, CPU jobs, and GPU Whisper jobs with Prefect

### 🧬 Life Science
Domain-specific simulation and analysis workloads.

- [`openmm-simulation`](./life-science/openmm-simulation/README.md) — run GPU-backed molecular dynamics simulations with OpenMM

### 🤖 Robotics
Robotics and physical-AI experiment loops.

- [`lerobot-finetune-job`](./robotics/lerobot-finetune-job/README.md) — fine-tune a LeRobot ACT or Diffusion policy on a robotics dataset in a serverless GPU job
- [`smolva-ft-norma-core`](./robotics/smolva-ft-norma-core/README.md) — fine-tune SmolVLA for SO-101 with bundled trajectories

## Awesome Community Projects

External examples and writeups from the community running serverless workloads on Nebius. Got something to add? Open a PR.

### Robotics

- 🤖 **Positronic + Nebius serverless workflows** — Convert datasets, train ACT/SmolVLA, and serve checkpoints as endpoints — all serverless on Nebius. — *by vertix* · [💻 code](https://github.com/vertix/positronic-open/tree/add-nebius-workflows/workflows/nebius)
- 🦾 **norma-core SmolVLA — Nebius fine-tune recipe** — Upstream recipe the [`robotics/smolva-ft-norma-core`](./robotics/smolva-ft-norma-core/) example mirrors. — *by norma-core* · [💻 code](https://github.com/norma-core/norma-core/blob/main/software/ai/smolvla_py/nebius.md)


## Repository structure

```text
serverless-cookbook/
├─ README.md
├─ CONTRIBUTING.md
├─ DEVELOPER_GUIDE.md
├─ LICENSE
├─ quickstarts/
├─ training/
├─ robotics/
├─ inference/
├─ mlops/
├─ life-science/
├─ robotics/
```

## Resources

- [Contributing](./CONTRIBUTING.md)
- [Developer Guide](./DEVELOPER_GUIDE.md)
- [Serverless AI overview docs](https://docs.nebius.com/serverless/overview)
- [CLI AI reference](https://docs.nebius.com/cli/reference/ai/)
