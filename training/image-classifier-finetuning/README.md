# Fine-tuning Image Classification on Nebius AI Jobs

| Field | Value |
|-------|-------|
| title | Fine-tuning Image Classification on a HuggingFace Dataset |
| category | training |
| type | job |
| runtime | gpu |
| hardware | 1× L40S (48 GB VRAM), 8 vCPU, 32 GB RAM |
| frameworks | transformers, datasets, torchvision |
| model | google/vit-base-patch16-224 |
| task | image-classification |
| classes | Impressionism, Surrealism, Minimalism, Pop Art |
| dataset size | 4 × 400 images (80/10/10 split) |
| best val accuracy | 76% |
| keywords | fine-tuning, vision-transformer, wikiart |
| difficulty | beginner |

**Task:** Multi-class art genre classification (image → label)

**Approach:** Fine-tune a pretrained ViT (Vision Transformer) using HuggingFace `transformers` + `Trainer`

---

## 1. Project structure

```
src/
├── train.py                     # Training script
├── requirements.txt             # Python dependencies
└── configs/
    ├── config_prod.yaml         # Production hyperparameters
├── .env.template                # Environment variables template
```

---

## 2. Dataset

4 art style classes (400 images each, 80/10/10 train/val/test split): [aleksandr-dzhumurat/art-genre-classification-slim](https://huggingface.co/datasets/aleksandr-dzhumurat/art-genre-classification-slim)

- Impressionism
- Surrealism
- Minimalism
- Pop Art

---

## 3. Upload job files to Object Storage

Start with `mv .env.template .env` and fill in the values.

```bash
# Create bucket
nebius storage bucket create --name art-genre-classification

# Get bucket ID
export BUCKET_ID=$(nebius storage bucket get-by-name \
  --name art-genre-classification \
  --format jsonpath='{.metadata.id}')
```

Update `.env` with `BUCKET_ID`.

---

## 4. Launch the job

```bash
make deploy
```

This creates a Nebius AI job named `art-genre-classification-prod` on a 1×L40S GPU with the production config.

---

## 5. Monitor logs

```bash
make logs
```

---

## 6. Artifacts

Each run saves the following to S3 `output/<RUN_ID>/`:

| File | Description |
|------|-------------|
| `best_model/` | Final model weights + processor config |
| `learning_curve.json/csv` | Per-epoch train/eval loss and accuracy |
| `test_results.json` | Overall test set metrics |
| `accuracy_table.json/csv` | Per-class precision, recall, F1 |

## 7. Helpers

Download model to local machine

```shell
make download_model
```

Clean up the bucket (deletes single earliest run, run it several times to clean up all runs)

```shell
make delete-earliest-run
```

