import argparse
import json
import os
import shutil
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps

from core.config import settings
from schemas.predictions import PredictionJob, PredictionRecord
from services.project_workspace import get_project_root

os.environ.setdefault('YOLO_OFFLINE', 'true')
os.environ.setdefault('YOLO_CONFIG_DIR', str(settings.data_dir / '.ultralytics'))


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp'); temporary.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8'); os.replace(temporary, path)


class PredictionWorker:
    def __init__(self, project_id: str, job_id: str):
        self.root = get_project_root(project_id)
        self.job_path = self.root / 'metadata' / 'prediction_jobs' / f'{job_id}.json'
        self.cancel_path = self.root / 'metadata' / 'prediction_jobs' / f'{job_id}.cancel'
        self.events_path = self.root / 'logs' / f'prediction-{job_id}.jsonl'
        self.workspace = self.root / 'generated' / 'prediction' / job_id
        self.job = PredictionJob.model_validate_json(self.job_path.read_text(encoding='utf-8'))

    def event(self, level: str, message: str, event_type='log', data=None):
        payload = {'type':event_type,'timestamp':datetime.now().strftime('%H:%M:%S'),'level':level,'message':message}
        if data is not None: payload['data'] = data
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open('a',encoding='utf-8') as stream: stream.write(json.dumps(payload)+'\n')

    def update(self, **changes):
        current = PredictionJob.model_validate_json(self.job_path.read_text(encoding='utf-8'))
        self.job = current.model_copy(update=changes); atomic_json(self.job_path,self.job.model_dump(mode='json'))

    def run(self):
        try:
            self.events_path.unlink(missing_ok=True)
            self.update(state='PREPARING',started_at=datetime.now(UTC),pid=os.getpid())
            model_root = self.root / 'models' / self.job.model_id
            mapping = json.loads((model_root/'class_mapping.json').read_text(encoding='utf-8'))
            yolo_to_stable = {int(yolo):int(stable) for stable,yolo in mapping['stable_to_yolo'].items()}
            dataset = {item['id']:item for item in json.loads((self.root/'metadata'/'dataset.json').read_text(encoding='utf-8'))['images']}
            from ultralytics import YOLO
            self.event('INFO',f'Loading model {self.job.model_id}.')
            model = YOLO(str(model_root/'best.pt'))
            self.workspace.mkdir(parents=True,exist_ok=True)
            self.update(state='RUNNING')
            self.event('INFO', f"Running inference on {self.job.total} image{'' if self.job.total == 1 else 's'}.")
            prediction_count=with_predictions=without_predictions=0
            confidence_sum=0.0
            highest_confidence=lowest_confidence=None
            for position,image_id in enumerate(self.job.image_ids,1):
                if self.cancel_path.exists():
                    self.update(state='CANCELLED',finished_at=datetime.now(UTC)); self.event('WARNING','Prediction cancelled.'); return
                record = dataset[image_id]
                source = (self.root/'images'/record['relative_path']).resolve()
                normalized_path = self.workspace/f'{image_id}.jpg'
                with Image.open(source) as image: ImageOps.exif_transpose(image).convert('RGB').save(normalized_path,'JPEG',quality=95)
                # Ultralytics returns final post-NMS boxes. agnostic_nms=False keeps NMS class-aware.
                result = model.predict(
                    source=str(normalized_path),
                    conf=self.job.confidence_threshold,
                    iou=.7,
                    agnostic_nms=False,
                    max_det=self.job.max_detections,
                    verbose=False,
                )[0]
                predictions=[]
                if result.boxes is not None:
                    for box,confidence,class_index in zip(result.boxes.xyxy.cpu().tolist(),result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist()):
                        stable_id=yolo_to_stable.get(int(class_index))
                        if stable_id is None: raise ValueError(f'Model returned unmapped class index {int(class_index)}')
                        predictions.append(PredictionRecord(id=uuid.uuid4().hex,run_id=self.job.id,image_id=image_id,model_id=self.job.model_id,class_id=stable_id,confidence=float(confidence),x1=float(box[0]),y1=float(box[1]),x2=float(box[2]),y2=float(box[3]),original_class_id=stable_id,original_box=[float(value) for value in box],created_at=datetime.now(UTC)))
                output = self.root/'predictions'/self.job.model_id/self.job.id/f'{image_id}.json'
                atomic_json(output,{'schema_version':1,'run_id':self.job.id,'model_id':self.job.model_id,'image_id':image_id,'confidence_threshold':self.job.confidence_threshold,'predictions':[item.model_dump(mode='json') for item in predictions]})
                confidences=[item.confidence for item in predictions]
                prediction_count += len(predictions); with_predictions += bool(predictions); without_predictions += not predictions
                confidence_sum += sum(confidences)
                if confidences:
                    image_high=max(confidences); image_low=min(confidences)
                    highest_confidence=image_high if highest_confidence is None else max(highest_confidence,image_high)
                    lowest_confidence=image_low if lowest_confidence is None else min(lowest_confidence,image_low)
                progress={'processed':position,'total':self.job.total,'prediction_count':prediction_count,'images_with_predictions':with_predictions,'images_without_predictions':without_predictions,'average_confidence':confidence_sum/prediction_count if prediction_count else None,'highest_confidence':highest_confidence,'lowest_confidence':lowest_confidence}
                self.update(**progress); self.event('INFO',f'Processed {position} / {self.job.total}.','progress',progress)
            self.update(state='COMPLETED',finished_at=datetime.now(UTC),error=None)
            self.event('INFO', f"Prediction completed with {prediction_count} proposal{'' if prediction_count == 1 else 's'}.")
        except Exception as error:
            self.update(state='FAILED',finished_at=datetime.now(UTC),error=str(error)); self.event('ERROR',str(error))
            (self.root/'logs'/f'prediction-{self.job.id}.traceback.log').write_text(traceback.format_exc(),encoding='utf-8')
        finally:
            self.cancel_path.unlink(missing_ok=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--project-id',required=True); parser.add_argument('--job-id',required=True); arguments=parser.parse_args()
    PredictionWorker(arguments.project_id,arguments.job_id).run()
