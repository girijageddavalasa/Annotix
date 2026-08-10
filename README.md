# Annotix

Annotix is a local-first computer-vision annotation and YOLO training platform. The React/Vite frontend and FastAPI backend run on the user's PC; datasets, annotations, generated files, logs, and trained models remain inside the local project workspace.

## Project structure

```text
Annotix/
├── frontend/    # React + Vite application
├── backend/     # FastAPI and local training worker
├── data/        # Project workspaces (ignored by Git)
└── models/      # Reserved global model storage (ignored by Git)
```

## Install and run

Backend, in the first PowerShell terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend health endpoint is `http://127.0.0.1:8000/api/health`.

## Local training

Training uses only images with at least one stored annotation. Before starting YOLO, the worker creates a project-scoped snapshot, corrects EXIF orientation in generated copies, converts original-coordinate boxes to normalized YOLO labels, and records the stable Annotix class-ID-to-YOLO-index mapping.

Annotated images are deterministically divided into disjoint 80% training and 20% validation splits using a configurable seed (default `42`). The image and all of its annotations always remain together. The immutable snapshot records stable split IDs, copied annotation data, class mapping, configuration, augmentation settings, diagnostics, and warnings. Very small validation sets are allowed but identified as producing potentially unstable metrics.

Training runs in a separate local Python process. FastAPI remains available for status, Server-Sent Events logs, metrics, and cancellation. Conflicting edits to the training project's images, annotations, and classes are locked until the job finishes; browsing and switching projects remain available.

The default model is the bundled `yolo11n.yaml` architecture and therefore does not download pretrained weights. To use an already-downloaded local checkpoint or another local model definition, set `ANNOTIX_YOLO_MODEL` before starting FastAPI:

```powershell
$env:ANNOTIX_YOLO_MODEL = "C:\path\to\local\weights.pt"
```

Completed model versions are stored under:

```text
data/projects/<project_id>/models/<model_id>/
├── best.pt
├── last.pt
├── configuration.json
├── class_mapping.json
├── dataset.yaml
└── run/
```

Job state is stored under `metadata/training/`, and structured console events are stored under the project's `logs/` directory. Temporary training snapshots are written below `generated/training/`. When “Save augmented images” is selected, generated copies and transformed YOLO labels are placed under `generated/augmented/<model_id>/`; original files in `images/` are never overwritten.

Every run receives a history record under `metadata/training_history/<training_run_id>.json`. Completed model directories contain `training_run.json` with real final losses and evaluation metrics, the snapshot reference, split IDs, status, checkpoint path, and validation smoke-test results. A run is marked complete only after `best.pt` exists and can be loaded by Ultralytics.

## Training API

- `GET /api/training/status`
- `POST /api/training/jobs`
- `GET /api/training/jobs/{job_id}`
- `GET /api/training/jobs/{job_id}/events`
- `POST /api/training/jobs/{job_id}/cancel`

Ultralytics is forced into offline mode by the worker. Its local settings live under `data/.ultralytics/`.

## Local prediction and review

The Annotation page can run any completed model version on the current image or on all currently unannotated images. Inference runs in a separate local process and streams real progress and logs to the UI. The default confidence threshold is `0.25` (configurable from `0.05` to `0.95`), and the backend-enforced per-image detection limit defaults to `100` (`25`, `50`, `100`, or `200`). Ultralytics performs class-aware NMS and only its final post-NMS detections are persisted.

Predictions are stored as project-scoped proposals under `data/projects/<project_id>/predictions/`. They remain separate from human annotations until explicitly accepted. Proposals can be moved, resized, assigned to another compatible class, accepted, or rejected. Accepting a proposal appends a normal annotation with original-image pixel coordinates; it never replaces existing annotations or modifies source images.

The model's saved stable class mapping must match the current project's classes before inference can start. Repeated prediction runs have unique run IDs so their origin remains traceable.

### Prediction API

- `GET /api/predictions/models`
- `GET /api/predictions/status`
- `POST /api/predictions/jobs`
- `GET /api/predictions/jobs/{job_id}`
- `GET /api/predictions/jobs/{job_id}/events`
- `POST /api/predictions/jobs/{job_id}/cancel`
- `GET /api/predictions/images/{image_id}`
- `PATCH /api/predictions/items/{prediction_id}`
- `POST /api/predictions/items/{prediction_id}/accept`
- `POST /api/predictions/items/{prediction_id}/reject`
- `POST /api/predictions/accept-all`
