# OpenMM Simulation Dashboard

A local Streamlit UI for submitting, monitoring, and visualizing OpenMM molecular dynamics jobs on **Nebius AI Jobs**.

## Setup and run

```bash
# from life-science/openmm-simulation

# 1) Sync dependencies (project + app UI group)
uv sync --group app

# 2) Start the Streamlit UI
cd app
uv run --group app streamlit run app.py
```

Opens at `http://localhost:8501`. The app loads [`.streamlit/config.toml`](.streamlit/config.toml), so **saving `app.py` triggers an automatic rerun** (hot reload for local demos).

If the Nebius CLI reports **multiple subnets**, set a subnet before launching (UI: sidebar **Nebius job network**, or shell):

```bash
export SUBNET_ID="subnet-xxxxxxxx"
```

## What this UI is for

This dashboard is a lightweight control panel for OpenMM runs on Nebius:

- Configure and submit a molecular dynamics job from the browser.
- Track job status and inspect logs while it is running.
- Open completed run artifacts from S3 for quick analysis (plots, RMSD, downloads).

## How to use

1. Start the app and enter credentials in the sidebar (or export env vars first).
2. In **Configure & launch**, choose a sample protein and simulation settings.
3. Submit the job and watch progress in the monitor view (status + logs).
4. Open **Results** to browse run files, visualize metrics, and download outputs.
5. Optional: paste an existing job ID in **Reconnect to existing job** to continue monitoring a previous run.

## UI sections

| Tab | What happens |
|-----|-------------|
| **Configure & launch** | Pick a protein, set step count, preview the CLI command, submit the job |
| **Results** | Download files from S3, plot energy & temperature, compute RMSD |

## Authentication

Set environment variables before running (recommended):

```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="eu-north1"
export S3_ENDPOINT_URL="https://storage.eu-north1.nebius.cloud"
export S3_BUCKET="openmm-simulation-s3" # Modify name, s3 bucket names should be unique
export S3_PREFIX="openmm"
# Optional — only if `nebius ai job create` asks for a subnet:
# export SUBNET_ID="subnet-..."
```

All fields can also be typed directly in the sidebar. Env vars are used as defaults and can be overridden per-session.

## Requirements

- **Nebius CLI** installed and authenticated (`nebius auth ...`)
- **Nebius Object Storage** bucket with read/write access
- Python 3.11+
- `mdtraj` is optional — only needed for RMSD plots

## Reconnecting to a running job

Paste any existing job ID into the **"Reconnect to existing job"** field in the sidebar and click **Load**. The monitor tab will pick it up immediately.