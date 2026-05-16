# Contributing to Serverless Cookbook

This repository accepts runnable, workload-first examples.

## What to contribute

- Runnable, workload-first examples with clear input/output behavior.
- Open contribution scope for categories:
  `quickstarts/`, `training/`, `inference/`, `agents/`, `robotics/`, `life-sciences/`, `mlops/`.

### `quickstarts/`

Use for first-run examples with the lowest setup cost.

Expected scope:

- first job and first endpoint flows
- small, fast validation workloads
- minimal setup with explicit success criteria

### `training/`

Use when the main value is model training or fine-tuning.

Expected scope:

- framework-specific training runs
- fine-tuning workflows (for example LoRA/QLoRA)
- distributed or multi-GPU training patterns

### `inference/`

Use for serving and batch inference workloads.

Expected scope:

- endpoint-based model serving
- batch inference over prompts or datasets
- OpenAI-compatible API serving patterns

### `agents/`

Use for workloads where agent behavior is the core workload.

Expected scope:

- concrete tasks with clear outcomes
- explicit runtime model and tool usage
- clear deployment pattern

### `robotics/`

Use for simulation, dataset generation, and robotics-adjacent compute workflows.

Expected scope:

- simulation jobs
- synthetic dataset generation
- robotics-oriented GPU/CPU pipelines

### `life-sciences/`

Use for health, biology, and life-science workloads that are recognizable and runnable.

Expected scope:

- drug discovery workflows
- protein folding workloads
- genomics pipelines
- molecular simulations
- batch processing pipelines for scientific data
- reproducible domain-specific examples

Contributor expectation for all sections:

- prefer updating an existing example over creating a near-duplicate
- keep examples concise, runnable, and easy to adapt
- include practical commands and expected output

## What not to contribute

- Planning-only docs
- Marketing copy
- Placeholder examples without a runnable path


## Required example layout

Each example directory should be self-contained and easy to scan.

```text
example-name/
├─ README.md
├─ scripts/               # optional
├─ src/                   # optional
└─ assets/                # optional
```

Minimum required files:

- `README.md`
- runnable config/command files needed for first execution

## Optional: shared scripts toolkit

The repo ships an opt-in `scripts/` toolkit (`bootstrap-env.sh`, `bootstrap-storage.sh`, `activate.sh`, `cleanup.sh`) for common setup — resolving project/subnet, creating buckets and service accounts, writing `.env` files. Currently used by the robotics examples; not required.

Use it when:

- your example needs a Nebius project ID, subnet ID, or an S3 bucket
- you want users to skip manual CLI plumbing on a first run
- the example is one of several in a category and benefits from per-example `.env.<example>` isolation

Skip it when:

- the example is fully self-contained (no S3, no per-tenant config)
- the setup is already trivially short (a single `nebius ai job create ...`)

Canonical docs and full helper list: [`scripts/README.md`](./scripts/README.md).

## README front matter

Store lightweight metadata in YAML front matter at the top of each example `README.md`.

Recommended fields:

- `title`
- `category`
- `type`
- `runtime`
- `frameworks`
- `keywords`
- `difficulty`

`category` must be one of:
`quickstarts`, `training`, `inference`, `agents`, `robotics`, `life-sciences`, `mlops`.

## README checklist

Keep README files concise and practical. Include:

1. What this example does
  - Why this is useful
  - Requirements
  - Runtime / compute
2. Run
3. Expected output
4. How to adapt
5. Troubleshooting

## Naming rules

- Use kebab-case directory names
- Prefer workload-first names (for example: `vllm-endpoint`, `first-job`)
- Avoid generic names like `demo1`, `sample-project`

## Submission checklist

- [ ] Example is runnable end-to-end
- [ ] Workload and outcome are obvious within 5 minutes
- [ ] Compute assumptions are explicit
- [ ] `README.md` includes expected output
- [ ] `README.md` includes accurate YAML front matter
- [ ] No secrets or tenant-specific values are committed
