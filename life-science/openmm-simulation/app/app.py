"""
OpenMM Molecular Dynamics Dashboard — Nebius AI Jobs
Run: streamlit run app.py
"""

import hashlib
import json
import os
import re
import time
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

import boto3
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

try:
    import mdtraj as md
    MDTRAJ_AVAILABLE = True
except ImportError:
    MDTRAJ_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

IMAGE    = "mnrozhkov/openmm-serverless:v0.1.5"
PRESET   = "1gpu-8vcpu-32gb"
GPU_OPTIONS = {
    "l40s": "gpu-l40s-a",
    "gpu-h100-sxm": "gpu-h100-sxm",
}
DEFAULT_GPU = "l40s"

# `nebius ai job create` often blocks 2–5+ min while the job is accepted / queued; do not use a short CLI timeout.
JOB_CREATE_CLI_TIMEOUT_SEC = 600
JOBS_AUTO_REFRESH_SEC = 10
DUPLICATE_SUBMIT_BLOCK_SEC = 10

PROTEINS = {
    "1UBQ": {
        "name": "Ubiquitin",
        "organism": "H. sapiens",
        "atoms": 1231,
        "desc": "Small regulatory protein. Classic MD benchmark — ideal for smoke tests.",
    },
    "1CRN": {
        "name": "Crambin",
        "organism": "C. hispanica",
        "atoms": 327,
        "desc": "Tiny and very stable. Fastest simulation, great for quick validation.",
    },
    "2PTC": {
        "name": "Trypsin–BPTI",
        "organism": "B. taurus",
        "atoms": 3283,
        "desc": "Protease–inhibitor complex. Relevant for drug-design workflows.",
    },
    "1VII": {
        "name": "Villin headpiece",
        "organism": "G. gallus",
        "atoms": 596,
        "desc": "Ultra-fast folder. Popular choice for protein folding studies.",
    },
}

STEP_PRESETS = {
    "Smoke test  — 200 steps":    200,
    "Quick demo  — 1,000 steps":  1_000,
    "Standard   — 5,000 steps":   5_000,
    "Production — 50,000 steps": 50_000,
}

# ──────────────────────────────────────────────────────────────────────────────
# Session state bootstrap
# ──────────────────────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "selected_protein": "1UBQ",
        "job_id":           None,
        "job_status":       None,
        "logs":             "",
        "active_tab":       0,
        "recent_jobs":      [],
        "selected_log_job": None,
        "logs_by_job":      {},
        "last_submit_by_run": {},
        "selected_gpu":     DEFAULT_GPU,
        "last_jobs_poll_at": 0.0,
        "last_jobs_refresh_label": "",
        "recent_jobs_error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _env_or(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _subnet_from_env() -> str:
    """Nebius: use when the CLI reports multiple subnets."""
    return (
        os.getenv("SUBNET_ID", "").strip()
    )


def _seed_credentials_from_env() -> None:
    """Populate sidebar widget keys from the environment on first use (per session)."""
    seeds: dict[str, str] = {
        "aws_key":    _env_or("AWS_ACCESS_KEY_ID"),
        "aws_secret": _env_or("AWS_SECRET_ACCESS_KEY"),
        "region":     _env_or("AWS_DEFAULT_REGION") or "eu-north1",
        "endpoint":   _env_or("S3_ENDPOINT_URL") or "https://storage.eu-north1.nebius.cloud",
        "bucket":     _env_or("S3_BUCKET"),
        "prefix":     _env_or("S3_PREFIX") or "openmm",
        "subnet_id":  _subnet_from_env(),
    }
    for state_key, value in seeds.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = value

# ──────────────────────────────────────────────────────────────────────────────
# Credentials helpers
# ──────────────────────────────────────────────────────────────────────────────


def _creds():
    """Merge session-state sidebar values with env fallbacks (if a field was cleared)."""
    def _pick(key: str, env: str) -> str:
        v = st.session_state.get(key)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
        return os.getenv(env, "").strip()

    sid = st.session_state.get("subnet_id")
    if sid is None or str(sid).strip() == "":
        sid = _subnet_from_env()
    return {
        "aws_key":    _pick("aws_key",    "AWS_ACCESS_KEY_ID"),
        "aws_secret": _pick("aws_secret", "AWS_SECRET_ACCESS_KEY"),
        "region":     _pick("region",     "AWS_DEFAULT_REGION") or "eu-north1",
        "endpoint":   _pick("endpoint",   "S3_ENDPOINT_URL")    or "https://storage.eu-north1.nebius.cloud",
        "bucket":     _pick("bucket",     "S3_BUCKET"),
        "prefix":     _pick("prefix",     "S3_PREFIX")          or "openmm",
        "subnet_id":  (sid or "").strip(),
    }

def _s3(creds):
    return boto3.client(
        "s3",
        endpoint_url=creds["endpoint"],
        aws_access_key_id=creds["aws_key"],
        aws_secret_access_key=creds["aws_secret"],
        region_name=creds["region"],
    )

# ──────────────────────────────────────────────────────────────────────────────
# Nebius CLI wrappers
# ──────────────────────────────────────────────────────────────────────────────

def _run(args, timeout=30):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        msg = (
            f"Subprocess timed out after {timeout}s (local UI limit, not the job runtime). "
            "For `nebius ai job create`, the API may already have accepted the job — "
            "check the Nebius console and use **Reconnect to existing job** in the sidebar if needed."
        )
        return "", msg, 1
    except FileNotFoundError:
        return "", f"'{args[0]}' not found — is the Nebius CLI installed and on PATH?", 1


def submit_job(protein_id: str, steps: int, creds: dict, platform: str):
    cmd = [
        "nebius", "ai", "job", "create",
        "--name",    f"openmm-{protein_id.lower()}-{steps}",
        "--image",   IMAGE,
        "--platform", platform,
        "--preset",  PRESET,
        "--timeout", "4h",
        "--env", f"AWS_ACCESS_KEY_ID={creds['aws_key']}",
        "--env", f"AWS_SECRET_ACCESS_KEY={creds['aws_secret']}",
        "--env", f"AWS_DEFAULT_REGION={creds['region']}",
        "--env", f"S3_ENDPOINT_URL={creds['endpoint']}",
        "--env", f"S3_BUCKET={creds['bucket']}",
        "--env", f"S3_PREFIX={creds['prefix']}",
        "--args",    f"--protein-id {protein_id} --steps {steps}",
    ]
    subnet = (creds.get("subnet_id") or "").strip()
    if subnet:
        cmd.extend(["--subnet-id", subnet])
    return _run(cmd, timeout=JOB_CREATE_CLI_TIMEOUT_SEC)


def job_status(job_id: str) -> str:
    stdout, stderr, rc = _run(["nebius", "ai", "job", "get", job_id, "--format", "json"])
    if rc != 0:
        stdout, stderr, rc = _run(["nebius", "ai", "job", "get", job_id])
    return _normalize_status(stdout + stderr)


def job_logs(job_id: str) -> str:
    stdout, stderr, rc = _run(["nebius", "ai", "logs", job_id, "--tail", "300"], timeout=20)
    merged = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part).strip()
    if rc == 0 and merged:
        return merged

    # Nebius CLI defaults to a recent time window; older completed jobs often
    # require an explicit lookback to return historical logs.
    stdout2, stderr2, rc2 = _run(
        ["nebius", "ai", "logs", job_id, "--since", "720h", "--tail", "300"],
        timeout=20,
    )
    merged2 = "\n".join(part for part in (stdout2.strip(), stderr2.strip()) if part).strip()
    if rc2 == 0 and merged2:
        return merged2

    if rc != 0 or rc2 != 0:
        return (merged2 or merged or "Failed to fetch job logs.").strip()
    return "No log lines returned for this job (including extended history window)."


def _parse_job_id(output: str) -> str | None:
    """Extract job id from Nebius CLI stdout and/or stderr."""
    if not (output or "").strip():
        return None
    for pattern in [
        r'"id"\s*:\s*"([^"]+)"',
        r'"(?:job_)?id"\s*:\s*"([^"]+)"',
        r'(?:created|job\s*id|job_id)\s*[:=]\s*([a-zA-Z0-9\-_]{8,})',
        r'/jobs/([a-zA-Z0-9\-]{8,})',
        r'job[_\-]id\s*[:\s]+([a-zA-Z0-9\-_]+)',
        r'\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b',
        r'id\s*[:\s]+([a-zA-Z0-9\-_]{6,})',
    ]:
        m = re.search(pattern, output, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            if cand:
                return cand
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    return lines[0] if lines else None


def _cli_submission_output(stdout: str, stderr: str) -> str:
    return f"{stdout or ''}\n{stderr or ''}".strip()


_STATUS_ALIASES: dict[str, str] = {
    "SUCCEEDED": "SUCCEEDED",
    "COMPLETED": "COMPLETED",
    "FAILED": "FAILED",
    "ERROR": "FAILED",
    "RUNNING": "RUNNING",
    "PENDING": "PENDING",
    "QUEUED": "QUEUED",
    "SUBMITTED": "SUBMITTED",
    "STARTING": "STARTING",
    "PROVISIONING": "PROVISIONING",
    "STATING": "STARTING",
}


def _normalize_status(raw_status: str) -> str:
    upper = (raw_status or "").strip().upper()
    if not upper:
        return "UNKNOWN"
    for token, normalized in _STATUS_ALIASES.items():
        if token in upper:
            return normalized
    return upper


def _remember_job(job_id: str, status: str = "SUBMITTED") -> None:
    """Keep last 5 distinct jobs, newest first."""
    existing = st.session_state.get("recent_jobs", [])
    kept = [j for j in existing if j.get("job_id") != job_id]
    kept.insert(0, {"job_id": job_id, "status": status})
    st.session_state["recent_jobs"] = kept[:5]


def _parse_recent_jobs(raw_output: str) -> list[dict[str, str]]:
    if not raw_output.strip():
        return []

    jobs: list[dict[str, str]] = []

    try:
        payload = json.loads(raw_output)
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("items") or payload.get("jobs") or []
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            jid = str(
                item.get("id")
                or item.get("job_id")
                or item.get("jobId")
                or ""
            ).strip()
            status = _normalize_status(str(item.get("status") or "UNKNOWN"))
            if jid:
                jobs.append({"job_id": jid, "status": status})
    except json.JSONDecodeError:
        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith(("type ", "id ", "name ", "platform ", "resources ", "state ", "created ")):
                continue
            if set(stripped) <= {"-", " "}:
                continue

            jid_match = re.search(r"\b(aijob-[a-z0-9]+|[a-f0-9]{8}-[a-f0-9\-]{27,})\b", stripped, re.IGNORECASE)
            if not jid_match:
                continue
            status = _normalize_status(stripped)
            jobs.append({"job_id": jid_match.group(1), "status": status})

    # Keep first-seen order from CLI output; de-duplicate by job id.
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for job in jobs:
        jid = job["job_id"]
        if jid in seen:
            continue
        seen.add(jid)
        deduped.append(job)
        if len(deduped) >= 5:
            break
    return deduped


def _refresh_recent_jobs_from_cli(force: bool = False) -> None:
    now = time.time()
    last_polled = float(st.session_state.get("last_jobs_poll_at", 0.0))
    if not force and (now - last_polled < JOBS_AUTO_REFRESH_SEC):
        return

    # Nebius CLI commonly uses the singular form: `nebius ai job list`.
    # Keep a plural fallback for compatibility with older/alternate CLI variants.
    stdout, stderr, rc = _run(["nebius", "ai", "job", "list", "--format", "json"], timeout=30)
    if rc != 0:
        alt_stdout, alt_stderr, alt_rc = _run(
            ["nebius", "ai", "jobs", "list", "--format", "json"],
            timeout=30,
        )
        if alt_rc == 0:
            stdout, stderr, rc = alt_stdout, alt_stderr, alt_rc
    st.session_state["last_jobs_poll_at"] = now

    if rc != 0:
        st.session_state["recent_jobs_error"] = stderr.strip() or "Failed to fetch recent jobs."
        return

    # Some CLI versions can emit parseable content to stderr and/or return table
    # output even when JSON format is requested.
    primary_output = stdout.strip() or stderr.strip()
    jobs = _parse_recent_jobs(primary_output)
    if not jobs and stdout.strip() and stderr.strip():
        jobs = _parse_recent_jobs(f"{stdout}\n{stderr}")

    if not jobs:
        plain_stdout, plain_stderr, plain_rc = _run(["nebius", "ai", "job", "list"], timeout=30)
        if plain_rc != 0:
            alt_plain_stdout, alt_plain_stderr, alt_plain_rc = _run(
                ["nebius", "ai", "jobs", "list"],
                timeout=30,
            )
            if alt_plain_rc == 0:
                plain_stdout, plain_stderr, plain_rc = alt_plain_stdout, alt_plain_stderr, alt_plain_rc
        if plain_rc == 0:
            plain_output = plain_stdout.strip() or plain_stderr.strip()
            jobs = _parse_recent_jobs(plain_output)
            if not jobs and plain_stdout.strip() and plain_stderr.strip():
                jobs = _parse_recent_jobs(f"{plain_stdout}\n{plain_stderr}")

    if jobs:
        st.session_state["recent_jobs"] = jobs
        st.session_state["recent_jobs_error"] = ""
    else:
        st.session_state["recent_jobs_error"] = "No jobs parsed from `nebius ai job list` output."


STATUS_COLOR = {
    "SUCCEEDED": "#16a34a",
    "COMPLETED": "#16a34a",
    "RUNNING": "#0ea5e9",
    "STARTING": "#3b82f6",
    "PROVISIONING": "#6366f1",
    "SUBMITTED": "#eab308",
    "PENDING": "#f59e0b",
    "QUEUED": "#f59e0b",
    "FAILED": "#ef4444",
    "UNKNOWN": "#9ca3af",
}


def _status_chip(status: str) -> str:
    color = STATUS_COLOR.get(status, STATUS_COLOR["UNKNOWN"])
    return (
        f"<span style='display:inline-block;padding:0.15rem 0.45rem;"
        f"border:1px solid {color};border-radius:999px;color:{color};"
        f"font-size:0.78rem;font-weight:600;'>{status}</span>"
    )


def _render_recent_jobs_table() -> None:
    jobs = st.session_state.get("recent_jobs", [])
    jobs_error = st.session_state.get("recent_jobs_error", "").strip()
    selected_job = st.session_state.get("selected_log_job")

    h1, h2, h3 = st.columns([2.8, 1.1, 1.1])
    h1.markdown("**Job ID**")
    h2.markdown("**Status**")
    h3.markdown("**Logs**")

    if jobs:
        for row in jobs:
            jid = row["job_id"]
            status = row["status"]
            is_selected = jid == selected_job
            c1, c2, c3 = st.columns([2.8, 1.1, 1.1])
            if is_selected:
                c1.markdown(f"**`{jid}`**")
            else:
                c1.caption(f"`{jid}`")
            c2.markdown(_status_chip(status), unsafe_allow_html=True)
            if is_selected:
                with c3.container(key=f"selected_logs_btn_{jid}"):
                    c3.markdown(
                        f"""
<style>
.st-key-selected_logs_btn_{jid} button {{
    border-width: 2px !important;
    background-color: #dcfce7 !important;
    border-color: #86efac !important;
}}
</style>
""",
                        unsafe_allow_html=True,
                    )
                    if st.button("Logs", key=f"view_logs_{jid}", use_container_width=True):
                        st.session_state["selected_log_job"] = jid
                        st.session_state["logs_by_job"][jid] = job_logs(jid)
                        st.rerun()
            else:
                if c3.button("Logs", key=f"view_logs_{jid}", use_container_width=True):
                    st.session_state["selected_log_job"] = jid
                    st.session_state["logs_by_job"][jid] = job_logs(jid)
                    st.rerun()
    else:
        c1, c2, c3 = st.columns([2.8, 1.1, 1.1])
        c1.caption("No jobs returned")
        c2.caption("—")
        c3.caption("—")
        if jobs_error:
            st.caption(f"CLI message: {jobs_error}")

    selected = st.session_state.get("selected_log_job")
    st.markdown("**Job logs**")
    if selected:
        content = st.session_state["logs_by_job"].get(selected) or "No log lines returned yet."
        st.caption(f"Job ID: `{selected}`")
        st.text_area(
            "",
            value=content,
            height=320,
            disabled=True,
            label_visibility="collapsed",
            key=f"logs_box_{selected}",
        )
    else:
        st.caption("Click **Logs** on a job row to display logs here.")

# ──────────────────────────────────────────────────────────────────────────────
# S3 helpers
# ──────────────────────────────────────────────────────────────────────────────

def list_runs(creds):
    try:
        r = _s3(creds).list_objects_v2(
            Bucket=creds["bucket"],
            Prefix=creds["prefix"].rstrip("/") + "/",
            Delimiter="/",
        )
        return sorted(
            [cp["Prefix"] for cp in r.get("CommonPrefixes", [])],
            reverse=True,
        )
    except Exception as e:
        st.error(f"S3 error listing runs: {e}")
        return []


def list_files(creds, prefix) -> list[tuple[str, int]]:
    """Return (S3 key, size in bytes) for each object under prefix."""
    try:
        r = _s3(creds).list_objects_v2(Bucket=creds["bucket"], Prefix=prefix)
        return [(o["Key"], int(o.get("Size", 0))) for o in r.get("Contents", [])]
    except Exception as e:
        st.error(f"S3 error listing files: {e}")
        return []


def fetch_bytes(creds, key) -> bytes:
    buf = BytesIO()
    _s3(creds).download_fileobj(creds["bucket"], key, buf)
    return buf.getvalue()


def fetch_bytes_prefix(creds, key: str, max_bytes: int) -> bytes:
    """First max_bytes of an object (for text preview without full download)."""
    cli = _s3(creds)
    end = max(0, max_bytes - 1)
    try:
        r = cli.get_object(
            Bucket=creds["bucket"],
            Key=key,
            Range=f"bytes=0-{end}",
        )
        return r["Body"].read()
    except Exception:
        return fetch_bytes(creds, key)


def _s3_basename(key: str) -> str:
    return key.rstrip("/").split("/")[-1] or key


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MiB"


TEXT_PREVIEW_MAX_BYTES = 262_144
TEXT_PREVIEW_MAX_LINES = 400
IMAGE_PREVIEW_MAX_BYTES = 8 * 1024 * 1024
DOWNLOAD_AUTO_FETCH_MAX_BYTES = 32 * 1024 * 1024

_TEXT_EXT = (
    ".pdb",
    ".log",
    ".txt",
    ".csv",
    ".md",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".rst",
)


def _is_probably_text_preview(fname: str) -> bool:
    n = fname.lower()
    return any(n.endswith(ext) for ext in _TEXT_EXT) or n.endswith("_metadata.txt")


def _preview_file_area(
    creds,
    *,
    s3_key: str,
    fname: str,
    size: int,
    data_full: bytes | None,
) -> None:
    """In-expander preview: uses full bytes if provided, else ranged S3 read for text."""
    st.markdown("**Preview**")
    name_l = fname.lower()

    if name_l.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        if size > IMAGE_PREVIEW_MAX_BYTES:
            st.caption(f"Image is {_human_size(size)} — preview skipped; download the file.")
            return
        with st.spinner("Rendering image…"):
            blob = data_full if data_full is not None else fetch_bytes(creds, s3_key)
        st.image(blob)
        return

    if name_l.endswith(".dcd"):
        st.info(
            f"Binary trajectory ({_human_size(size)}). "
            "No in-browser preview — download and open in VMD, PyMOL, or similar."
        )
        return

    if _is_probably_text_preview(fname):
        if data_full is not None:
            raw = data_full
        elif size and size <= TEXT_PREVIEW_MAX_BYTES:
            with st.spinner("Loading preview…"):
                raw = fetch_bytes(creds, s3_key)
        else:
            with st.spinner("Loading preview…"):
                raw = fetch_bytes_prefix(creds, s3_key, TEXT_PREVIEW_MAX_BYTES)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        truncated_lines = len(lines) > TEXT_PREVIEW_MAX_LINES
        if truncated_lines:
            text = "\n".join(lines[:TEXT_PREVIEW_MAX_LINES]) + "\n\n… (truncated)"
        notes: list[str] = []
        if size and size > len(raw):
            notes.append(f"First {_human_size(len(raw))} of {_human_size(size)}.")
        if truncated_lines:
            notes.append(f"First {TEXT_PREVIEW_MAX_LINES} lines shown.")
        if notes:
            st.caption(" ".join(notes))
        st.code(text or "(empty)", language="text")
        return

    st.caption("No in-browser preview for this file type — use Download.")


def pick_topology_key_for_rmsd(keys: list[str], traj_key: str | None) -> str | None:
    """
    Choose a PDB that matches the DCD atom count.

    The trajectory is written after Modeller.addHydrogens; `*_simulation_topology.pdb`
    is that exact topology. `*_processed.pdb` is an earlier clean structure and will
    mismatch MDTraj with a typical "same atoms" error.
    """
    for k in keys:
        if k.endswith("_simulation_topology.pdb"):
            return k
    for k in keys:
        if k.endswith("_processed.pdb"):
            return k
    if traj_key and "_trajectory.dcd" in traj_key:
        candidate = traj_key.replace("_trajectory.dcd", ".pdb")
        if candidate in keys:
            return candidate
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Simulation log parser
# ──────────────────────────────────────────────────────────────────────────────

_LOG_RE = re.compile(
    r"[Ss]tep\s+(\d+)\s*\|.*?[Tt]emp[:\s]+([0-9.]+)\s*K.*?[Ee]_pot[:\s]+([+\-]?[0-9,.]+)"
)

def parse_log(text: str) -> pd.DataFrame | None:
    rows = []
    for line in text.splitlines():
        m = _LOG_RE.search(line)
        if m:
            rows.append({
                "step":    int(m.group(1)),
                "temp_K":  float(m.group(2)),
                "e_kj":    float(m.group(3).replace(",", "")),
            })
    return pd.DataFrame(rows) if rows else None

# ──────────────────────────────────────────────────────────────────────────────
# Plotting
# ──────────────────────────────────────────────────────────────────────────────

_PLOT_BG = dict(paper_bgcolor="#ffffff", plot_bgcolor="#f1f5f9")
_MARGIN = dict(l=55, r=20, t=45, b=40)


def fig_energy_temp(df: pd.DataFrame):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("Potential energy", "Temperature"),
        vertical_spacing=0.10,
    )
    fig.add_trace(go.Scatter(
        x=df["step"], y=df["e_kj"], mode="lines",
        name="E_pot (kJ/mol)", line=dict(color="#0369a1", width=1.8),
        fill="tozeroy", fillcolor="rgba(3,105,161,0.08)",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["step"], y=df["temp_K"], mode="lines",
        name="Temp (K)", line=dict(color="#15803d", width=1.8),
    ), row=2, col=1)
    fig.add_hline(y=300, row=2, col=1, line=dict(dash="dash", color="rgba(15,23,42,0.25)"),
                  annotation_text="300 K target", annotation_font_color="#64748b")
    fig.update_layout(height=400, template="plotly_white", **_PLOT_BG,
                      margin=_MARGIN, legend=dict(orientation="h", y=1.08))
    fig.update_yaxes(title_text="kJ/mol", row=1, col=1)
    fig.update_yaxes(title_text="K",      row=2, col=1)
    fig.update_xaxes(title_text="Step",   row=2, col=1)
    return fig


def fig_rmsd(rmsd: list[float]):
    fig = go.Figure(go.Scatter(
        x=list(range(len(rmsd))), y=rmsd, mode="lines",
        name="RMSD (Å)", line=dict(color="#c2410c", width=2),
        fill="tozeroy", fillcolor="rgba(194,65,12,0.08)",
    ))
    fig.update_layout(
        height=280, template="plotly_white", **_PLOT_BG,
        margin=_MARGIN, title="RMSD from initial structure (Cα)",
        xaxis_title="Frame", yaxis_title="RMSD (Å)",
    )
    return fig


def compute_rmsd(traj_bytes: bytes, top_bytes: bytes) -> list[float] | None:
    if not MDTRAJ_AVAILABLE:
        return None
    with tempfile.TemporaryDirectory() as d:
        traj_path = Path(d) / "traj.dcd"
        top_path  = Path(d) / "top.pdb"
        traj_path.write_bytes(traj_bytes)
        top_path.write_bytes(top_bytes)
        try:
            traj = md.load(str(traj_path), top=str(top_path))
            ca   = traj.topology.select("name CA")
            rmsd = md.rmsd(traj, traj, 0, atom_indices=ca) * 10  # nm → Å
            return rmsd.tolist()
        except Exception as e:
            st.warning(f"MDTraj RMSD failed: {e}")
            return None

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────

def render_sidebar():
    st.sidebar.title("⚙️ Configuration")
    c = _creds()

    with st.sidebar.expander("🔑 Credentials", expanded=not c["aws_key"]):
        st.caption("Values load from your shell env on startup; edit here to override.")
        st.text_input("AWS_ACCESS_KEY_ID", key="aws_key", type="password")
        st.text_input("AWS_SECRET_ACCESS_KEY", key="aws_secret", type="password")
        st.text_input("AWS_DEFAULT_REGION", key="region")
        st.text_input("S3_ENDPOINT_URL", key="endpoint")

    with st.sidebar.expander("🪣 Object storage", expanded=not c["bucket"]):
        st.text_input("S3_BUCKET", key="bucket")
        st.text_input("S3_PREFIX", key="prefix")

    with st.sidebar.expander("🌐 Nebius job network", expanded=False):
        st.caption("Required if the CLI reports multiple subnets.")
        st.text_input(
            "Subnet ID",
            key="subnet_id",
            placeholder="e.g. subnet-…",
            help="Set SUBNET_ID in the environment, or paste here.",
        )

    c = _creds()
    missing = [k for k, v in {"AWS key": c["aws_key"], "AWS secret": c["aws_secret"], "S3 bucket": c["bucket"]}.items() if not v]
    if missing:
        st.sidebar.warning("Missing: " + ", ".join(missing))
    else:
        st.sidebar.success("✅ Ready")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 1 — Configure & launch
# ──────────────────────────────────────────────────────────────────────────────

def render_configure():
    creds = _creds()
    st.subheader("Select protein")

    cols = st.columns(len(PROTEINS))
    for col, (pid, info) in zip(cols, PROTEINS.items()):
        active = st.session_state["selected_protein"] == pid
        with col:
            st.markdown(f"""
            <div style="border:2px solid {'#0369a1' if active else '#cbd5e1'};border-radius:10px;
                        padding:14px;background:{'#e0f2fe' if active else '#f8fafc'};
                        min-height:140px;">
              <div style="font-weight:700;color:#0f172a;font-size:15px;">{info['name']}</div>
              <div style="color:#0369a1;font-size:11px;margin:3px 0 6px;">
                PDB {pid} &nbsp;·&nbsp; {info['atoms']:,} atoms
              </div>
              <div style="color:#475569;font-size:12px;line-height:1.45">{info['desc']}</div>
              <div style="color:#64748b;font-size:11px;margin-top:6px;font-style:italic">{info['organism']}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(
                "✓ Selected" if active else "Select",
                key=f"btn_{pid}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                st.session_state["selected_protein"] = pid
                st.rerun()

    st.divider()

    pid   = st.session_state["selected_protein"]
    pinfo = PROTEINS[pid]

    left, right = st.columns([2, 1])

    with left:
        st.subheader("Configure run")
        preset_label = st.selectbox("Simulation length", list(STEP_PRESETS.keys()))
        steps = STEP_PRESETS[preset_label]
        selected_gpu = st.selectbox("GPU", list(GPU_OPTIONS.keys()), key="selected_gpu")
        selected_platform = GPU_OPTIONS[selected_gpu]

        st.markdown("**CLI equivalent**")
        _sub = (creds.get("subnet_id") or "").strip()
        _sub_line = f'  --subnet-id "{_sub}" \\\n' if _sub else ""
        st.code(
            f'nebius ai job create \\\n'
            f'  --name "openmm-{pid.lower()}-{steps}" \\\n'
            f'  --image "{IMAGE}" \\\n'
            f'  --platform "{selected_platform}" --preset "{PRESET}" \\\n'
            f'{_sub_line}'
            f'  --args "--protein-id {pid} --steps {steps}"',
            language="bash",
        )

    with right:
        st.subheader("Summary")
        st.metric("Protein",  pinfo["name"])
        st.metric("Atoms",    f"{pinfo['atoms']:,}")
        st.metric("Steps",    f"{steps:,}")
        st.metric("GPU",      selected_gpu)

    st.divider()

    ready = all([creds["aws_key"], creds["aws_secret"], creds["bucket"]])
    if not ready:
        st.warning("Complete credentials in the sidebar before launching.")

    submit_key = f"{pid}:{steps}"
    now = time.time()
    last_submit_by_run = st.session_state.get("last_submit_by_run", {})
    last_submit_at = float(last_submit_by_run.get(submit_key, 0.0))
    remaining_block = int(DUPLICATE_SUBMIT_BLOCK_SEC - (now - last_submit_at))
    duplicate_blocked = remaining_block > 0

    if duplicate_blocked:
        st.info(
            f"Duplicate submit protection: wait {remaining_block}s "
            f"before launching the same run ({pid}, {steps} steps) again."
        )

    if st.button(
        "🚀  Launch simulation on Nebius GPU",
        type="primary", use_container_width=True, disabled=(not ready) or duplicate_blocked,
    ):
        last_submit_by_run[submit_key] = time.time()
        st.session_state["last_submit_by_run"] = last_submit_by_run
        with st.spinner("Submitting job…"):
            stdout, stderr, rc = submit_job(pid, steps, creds, selected_platform)

        combined = _cli_submission_output(stdout, stderr)
        jid = _parse_job_id(combined)

        if jid:
            st.session_state.update({
                "job_id":     jid,
                "job_status": "SUBMITTED",
                "logs":       "",
                "active_tab": 0,
            })
            _remember_job(jid, "SUBMITTED")
            st.session_state["selected_log_job"] = jid
            st.success("Job submitted.")
            st.markdown("**Job ID**:")
            st.code(jid, language=None)
            with st.expander("Full CLI output", expanded=False):
                st.code(combined or "(empty)", language="text")
            time.sleep(0.35)
            st.rerun()

        if rc != 0:
            st.error("Submission failed — CLI returned a non-zero exit code.")
            st.code(combined or f"stdout:\n{stdout}\n\nstderr:\n{stderr}", language="text")
        elif not combined:
            st.error("Submission returned no output from the Nebius CLI.")
        else:
            st.warning(
                "The CLI finished but no job ID could be parsed. "
                "Check the output below or the Nebius console."
            )
            st.code(combined, language="text")

    st.divider()
    st.markdown("### Jobs")
    _, jobs_ctl_r = st.columns([4, 1])
    with jobs_ctl_r:
        refresh_jobs = st.button("Refresh jobs", key="refresh_jobs_btn", use_container_width=True)

    should_bootstrap = not st.session_state.get("recent_jobs")
    if refresh_jobs or should_bootstrap:
        with st.spinner("Refreshing jobs…"):
            _refresh_recent_jobs_from_cli(force=True)
            selected = st.session_state.get("selected_log_job")
            if selected:
                st.session_state["logs_by_job"][selected] = job_logs(selected)
        st.session_state["last_jobs_refresh_label"] = time.strftime("%H:%M:%S")

        jobs_error = st.session_state.get("recent_jobs_error", "").strip()
        if refresh_jobs and jobs_error:
            st.warning(f"Refresh completed with CLI warning: {jobs_error}")
        elif refresh_jobs:
            st.success("Jobs refreshed.")

    _render_recent_jobs_table()
    refreshed_at = st.session_state.get("last_jobs_refresh_label", "").strip()
    suffix = f" Last refresh: `{refreshed_at}`." if refreshed_at else ""
    st.caption("Manual refresh mode. Use **Refresh jobs** to update statuses and logs." + suffix)

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2 — Monitor
# ──────────────────────────────────────────────────────────────────────────────

STATUS_ICON = {
    "RUNNING":   "🟢",
    "SUCCEEDED": "✅",
    "COMPLETED": "✅",
    "FAILED":    "❌",
    "PENDING":   "🟡",
    "QUEUED":    "🟡",
    "SUBMITTED": "🟡",
    "STARTING": "🟡",
    "PROVISIONING": "🟡",
    "UNKNOWN":   "⚪",
}

def render_monitor():
    jid = st.session_state.get("job_id")
    if not jid:
        st.info("No active job. Go to **Configure** to launch one, or paste a Job ID in the sidebar.")
        return

    st.subheader("Job monitor")
    st.caption(f"Job ID: `{jid}`")

    ctl_left, ctl_right = st.columns([4, 1])
    with ctl_right:
        if st.button("🔄 Refresh now", use_container_width=True):
            st.rerun()

    with ctl_left:
        with st.spinner("Fetching status…"):
            status = job_status(jid)
            st.session_state["job_status"] = status
        icon = STATUS_ICON.get(status, "⚪")
        st.markdown(f"### {icon}")
        st.markdown(_status_chip(status), unsafe_allow_html=True)

    st.markdown("**Output log**")
    logs = job_logs(jid)
    if logs:
        st.session_state["logs"] = logs
    st.text_area(
        "",
        value=st.session_state.get("logs") or "Waiting for output…",
        height=340,
        disabled=True,
        label_visibility="collapsed",
    )

    if status in ("SUCCEEDED", "COMPLETED"):
        st.success("Simulation complete!")
        if st.button("→ Go to Results", type="primary"):
            st.session_state["active_tab"] = 2
            st.rerun()

    if status == "FAILED":
        st.error("Job failed — check the log above for details.")

    if status in ("RUNNING", "PENDING", "QUEUED", "SUBMITTED", "STARTING", "PROVISIONING"):
        st.caption("Auto-refresh every 10 s while the job is active. Use **Refresh now** for an immediate update.")
        time.sleep(10)
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3 — Results
# ──────────────────────────────────────────────────────────────────────────────

def render_results():
    creds = _creds()
    st.subheader("Results")

    if not creds["bucket"]:
        st.warning("Set your S3 bucket in the sidebar to load results.")
        return

    with st.spinner("Listing runs…"):
        prefixes = list_runs(creds)

    if not prefixes:
        st.info("No completed runs found yet in your S3 bucket.")
        return

    run_labels = [p.rstrip("/").split("/")[-1] for p in prefixes]
    sel_label  = st.selectbox("Run", run_labels)
    if st.session_state.get("_results_sel_label") != sel_label:
        st.session_state["_results_sel_label"] = sel_label
        st.session_state.pop("_s3_dl_prev_sel", None)

    prefix     = prefixes[run_labels.index(sel_label)]
    file_entries = list_files(creds, prefix)
    keys = [k for k, _ in file_entries]
    size_by_key = dict(file_entries)

    if not keys:
        st.warning("No files found for this run.")
        return

    # ── Downloads + preview ─────────────────────────────────────────────────────
    with st.expander("📁 Download & preview", expanded=False):
        sorted_keys = sorted(keys, key=lambda k: _s3_basename(k).lower())

        def _fmt_choice(k: str) -> str:
            return f"{_s3_basename(k)}  ({_human_size(size_by_key.get(k, 0))})"

        pick = st.selectbox(
            "Select a file",
            options=sorted_keys,
            format_func=_fmt_choice,
            key=f"s3_file_pick_{sel_label}",
        )
        fname = _s3_basename(pick)
        fsize = size_by_key.get(pick, 0)
        name_l = fname.lower()
        huge = fsize > DOWNLOAD_AUTO_FETCH_MAX_BYTES or name_l.endswith(".dcd")

        prev_sel = st.session_state.get("_s3_dl_prev_sel")
        if prev_sel is not None and prev_sel != pick:
            st.session_state.pop(f"s3_full_{prev_sel}", None)
        st.session_state["_s3_dl_prev_sel"] = pick

        full_cache = f"s3_full_{pick}"

        if not huge:
            if full_cache not in st.session_state:
                try:
                    with st.spinner("Loading file from S3…"):
                        st.session_state[full_cache] = fetch_bytes(creds, pick)
                except Exception as e:
                    st.error(f"Could not load file: {e}")
                    st.session_state.pop(full_cache, None)
            if full_cache in st.session_state:
                st.download_button(
                    "⬇ Download",
                    data=st.session_state[full_cache],
                    file_name=fname,
                    use_container_width=True,
                )
                _preview_file_area(
                    creds,
                    s3_key=pick,
                    fname=fname,
                    size=fsize,
                    data_full=st.session_state[full_cache],
                )
        else:
            st.caption(
                f"Large or binary file ({_human_size(fsize)}). "
                "Preview uses a snippet when possible; full download is on demand."
            )
            _preview_file_area(creds, s3_key=pick, fname=fname, size=fsize, data_full=None)
            _ld_key = hashlib.sha256(f"{sel_label}|{pick}".encode()).hexdigest()[:20]
            if st.button("Load full file for download", key=f"s3_ld_{_ld_key}"):
                try:
                    with st.spinner("Downloading full object…"):
                        st.session_state[full_cache] = fetch_bytes(creds, pick)
                except Exception as e:
                    st.error(f"Download failed: {e}")
                    st.session_state.pop(full_cache, None)
                else:
                    st.rerun()
            if full_cache in st.session_state:
                st.download_button(
                    "⬇ Download",
                    data=st.session_state[full_cache],
                    file_name=fname,
                    use_container_width=True,
                )

    st.divider()

    # ── Energy & temperature plots ────────────────────────────────────────────
    log_key = next((k for k in keys if "_simulation.log" in k), None)
    if log_key:
        with st.spinner("Parsing simulation log…"):
            try:
                df = parse_log(fetch_bytes(creds, log_key).decode("utf-8", errors="replace"))
            except Exception as e:
                df = None
                st.warning(f"Log parse error: {e}")

        if df is not None and not df.empty:
            st.subheader("Energy & temperature")
            st.plotly_chart(fig_energy_temp(df), use_container_width=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Final E_pot",      f"{df['e_kj'].iloc[-1]:,.1f} kJ/mol",
                      delta=f"{df['e_kj'].iloc[-1] - df['e_kj'].iloc[0]:+.1f}")
            m2.metric("Mean temperature", f"{df['temp_K'].mean():.1f} K")
            m3.metric("Steps logged",     f"{len(df):,}")
        else:
            st.info("No step-level data found in simulation log.")
    else:
        st.info("Simulation log not found in this run.")

    st.divider()

    # ── RMSD ──────────────────────────────────────────────────────────────────
    st.subheader("RMSD from initial structure")
    traj_key = next((k for k in keys if k.endswith("_trajectory.dcd")), None)
    top_key  = pick_topology_key_for_rmsd(keys, traj_key)

    if not MDTRAJ_AVAILABLE:
        st.info("Install `mdtraj` to enable RMSD: `pip install mdtraj`")
    elif traj_key and top_key:
        top_basename = top_key.rstrip("/").split("/")[-1]
        st.caption(
            f"Topology for MDTraj: `{top_basename}` "
            "(matches the DCD; prefer `*_simulation_topology.pdb` over `*_processed.pdb`)."
        )
        if st.button("Compute RMSD (downloads trajectory)"):
            with st.spinner("Downloading trajectory and computing RMSD…"):
                try:
                    rmsd = compute_rmsd(
                        fetch_bytes(creds, traj_key),
                        fetch_bytes(creds, top_key),
                    )
                    if rmsd:
                        st.plotly_chart(fig_rmsd(rmsd), use_container_width=True)
                        st.metric("Final RMSD", f"{rmsd[-1]:.3f} Å",
                                  delta=f"max {max(rmsd):.3f} Å")
                    else:
                        st.warning("RMSD computation returned no data.")
                except Exception as e:
                    st.error(f"RMSD error: {e}")
    else:
        st.info(
            "Trajectory (`*_trajectory.dcd`) or a matching topology "
            "(`*_simulation_topology.pdb` or fallback `*_processed.pdb`) not found in this run."
        )

# ──────────────────────────────────────────────────────────────────────────────
# App entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="OpenMM · Nebius AI Jobs",
        page_icon="⚛",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
    <style>
      .stApp { background-color: #f8fafc; color: #0f172a; }
      section[data-testid="stSidebar"] { background-color: #f1f5f9; }
      div[data-testid="stMetricValue"] { color: #0369a1; }
      .stTextArea textarea { font-family: 'Fira Code', 'Courier New', monospace; font-size: 12px; }
      .stTabs [data-baseweb="tab"] { padding: 8px 22px; }
    </style>
    """, unsafe_allow_html=True)

    _init()
    _seed_credentials_from_env()
    render_sidebar()

    st.title("⚛  OpenMM Molecular Dynamics")
    st.caption("GPU-accelerated simulation · AMBER ff14SB + TIP3P · Nebius AI Jobs")
    st.divider()

    # Session state `active_tab` records intent (e.g. after submit); tabs stay default until user switches.
    tabs = st.tabs(["⚙  Configure & launch", "📊  Results"])

    with tabs[0]:
        render_configure()
    with tabs[1]:
        render_results()


if __name__ == "__main__":
    main()