---
title: Serve Qwen with vLLM
category: inference
type: endpoint
runtime: gpu
frameworks:
  - vllm
  - transformers
keywords:
  - llm
  - inference
  - openai-compatible
  - serving
difficulty: quickstart
---

# Serve Qwen with vLLM

Use this example when you want an OpenAI-compatible LLM API on GPU without managing VM lifecycle details.

Keywords: vLLM, LLM inference, OpenAI-compatible API, GPU serving

## What this example does

Deploys a vLLM endpoint that exposes an OpenAI-compatible API for chat completions.

### Why this is useful

It gives you a production-style serving pattern you can reuse for model APIs and app backends.

### Requirements

- Nebius CLI installed and authenticated
- GPU endpoint quota and subnet available
- `jq` for parsing CLI JSON output

### Runtime / compute

- model: `Qwen/Qwen3-0.6B` (default)
- image: `vllm/vllm-openai` container
- example presets:
  - `gpu-l40s-a` with `1gpu-8vcpu-32gb`
  - `gpu-h100-sxm` with `1gpu-16vcpu-200gb`

## Quickstart

```bash
export MODEL_ID="Qwen/Qwen3-0.6B"
export AUTH_TOKEN="$(openssl rand -hex 32)"
export SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')

nebius ai endpoint create \
  --name vllm-qwen-chat \
  --image vllm/vllm-openai:cu130-nightly-e68de8adc0301babb3bb3fcd2ddccaf98e7695c8 \
  --container-command "python3 -m vllm.entrypoints.openai.api_server" \
  --args "--model $MODEL_ID --host 0.0.0.0 --port 8000" \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --public \
  --container-port 8000 \
  --auth token \
  --token "$AUTH_TOKEN" \
  --shm-size 16Gi \
  --disk-size 450Gi \
  --subnet-id "$SUBNET_ID"

nebius ai endpoint list
export ENDPOINT_ID="<endpoint-id>"
ENDPOINT_IP=$(nebius ai endpoint get "$ENDPOINT_ID" --format json | jq -r '.status.public_endpoints[0]')
export ENDPOINT_URL="http://$ENDPOINT_IP"
```

## Expected output

```bash
curl -sS "$ENDPOINT_URL/v1/models" -H "Authorization: Bearer $AUTH_TOKEN" | jq

curl -sS "$ENDPOINT_URL/v1/chat/completions" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL_ID\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Say hello\"}]
  }" | jq -r '.choices[0].message.content'
```

You should see model metadata and a valid assistant response.

## How to adapt it

- swap `MODEL_ID` for another Hugging Face model
- tune platform/preset for latency and throughput targets
- add your app-specific prompt format and auth integration

## Troubleshooting

- if startup is slow, check endpoint logs and model download time
- if completions fail, verify model name matches the deployed model ID