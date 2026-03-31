CURRENT_DIR = $(shell pwd)
RUN_ID = $(shell date +%Y%m%d_%H%M%S)
PROJECT_NAME = art_scraper
include .env
export

upload-job-files:
	aws s3 sync \
	    ${CURRENT_DIR}/src \
	    s3://${S3_BUCKET} \
	    --endpoint-url ${S3_ENDPOINT} \
	    --exclude "output/*" \
	    --exclude "*.md"

deploy: upload-job-files
	nebius ai job create \
	    --name "art-genre-classification-prod" \
	    --image nvidia/cuda:13.1.1-runtime-ubuntu24.04 \
	    --platform gpu-l40s-a \
	    --preset 1gpu-8vcpu-32gb \
	    --disk-size 100Gi \
	    --shm-size 16Gi \
	    --volume "${BUCKET_ID}:/workspace/data" \
	    --container-command bash \
	    --args '-c "export JOB_CONFIG_PATH=/workspace/data/configs/config_prod.yaml && \
	      export OUTPUT_DIR=/workspace/data/output/${RUN_ID} && \
	      export HF_HUB_ENABLE_HF_TRANSFER=1 && \
	      apt-get update -y && \
	      apt-get install -y python3 python3-pip python3-dev && \
	      cd /workspace/data && \
	      mkdir -p output/${RUN_ID} && \
	      python3 -m pip install --no-cache-dir --break-system-packages \
	        --index-url https://download.pytorch.org/whl/cu121 \
	        torch torchvision && \
	      python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt && \
	      python3 train.py"'

logs:
	nebius ai job logs $$(nebius ai job list --format json | jq -r '.items[] | select(.metadata.name == "art-genre-classification-prod") | .metadata.id' | head -n 1) --follow

# One-time: tune AWS CLI transfer settings for large uploads
configure-s3-transfer:
	aws configure set default.s3.max_concurrent_requests 50
	aws configure set default.s3.multipart_threshold 64MB
	aws configure set default.s3.multipart_chunksize 64MB
	aws configure set default.s3.max_queue_size 1000

upload-dataset-s3: configure-s3-transfer
	aws s3 sync \
	    ${CURRENT_DIR}/data/hf_dataset \
	    s3://${S3_BUCKET}/hf_dataset \
	    --endpoint-url ${S3_ENDPOINT} \
	    --no-progress \
	    --cli-read-timeout 300 \
	    --cli-connect-timeout 30

download_model:
	$(eval LATEST_RUN := $(shell aws s3 ls s3://${S3_BUCKET}/output/ \
	    --endpoint-url ${S3_ENDPOINT} \
	    | grep PRE \
	    | awk '{print $$2}' \
	    | sort \
	    | tail -1 \
	    | tr -d '/'))
	@echo "Latest run: $(LATEST_RUN)"
	aws s3 sync \
	    s3://${S3_BUCKET}/output/$(LATEST_RUN) \
	    ${CURRENT_DIR}/output/$(LATEST_RUN) \
	    --endpoint-url ${S3_ENDPOINT} \
	    --no-progress

delete-earliest-run:
	$(eval EARLIEST_RUN := $(shell aws s3 ls s3://${S3_BUCKET}/output/ \
	    --endpoint-url ${S3_ENDPOINT} \
	    | grep PRE \
	    | awk '{print $$2}' \
	    | sort \
	    | head -1 \
	    | tr -d '/'))
	@echo "Earliest run: $(EARLIEST_RUN)"
	aws s3 rm \
	    s3://${S3_BUCKET}/output/$(EARLIEST_RUN) \
	    --endpoint-url ${S3_ENDPOINT} \
	    --recursive
