import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

import yaml
from PIL import Image, ImageOps

from core.config import settings
from schemas.training import TrainingJob
from services.project_workspace import get_project_root

os.environ.setdefault('YOLO_OFFLINE', 'true')
os.environ.setdefault('YOLO_CONFIG_DIR', str(settings.data_dir / '.ultralytics'))
os.environ.setdefault('NO_ALBUMENTATIONS_UPDATE', '1')
os.environ.setdefault('ALBUMENTATIONS_NO_TELEMETRY', '1')


def stable_seed(value: object) -> int:
    return int.from_bytes(hashlib.sha256(str(value).encode()).digest()[:4], 'big')


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    os.replace(temporary, path)


class Worker:
    def __init__(self, project_id: str, job_id: str):
        self.root = get_project_root(project_id)
        self.job_path = self.root / 'metadata' / 'training' / f'{job_id}.json'
        self.cancel_path = self.root / 'metadata' / 'training' / f'{job_id}.cancel'
        self.events_path = self.root / 'logs' / f'training-{job_id}.jsonl'
        self.event_sequence = 0
        self.job = TrainingJob.model_validate_json(self.job_path.read_text(encoding='utf-8'))
        self.model_root = self.root / 'models' / self.job.model_id
        self.workspace = self.root / 'generated' / 'training' / job_id

    def event(self, level: str, message: str, event_type: str = 'log', data: dict | None = None) -> None:
        self.event_sequence += 1
        payload = {'id': f'{self.job.id}:{self.event_sequence}', 'type': event_type, 'timestamp': datetime.now().strftime('%H:%M:%S'), 'level': level, 'message': message}
        if data is not None:
            payload['data'] = data
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(payload) + '\n')

    def update(self, **changes) -> None:
        current = TrainingJob.model_validate_json(self.job_path.read_text(encoding='utf-8'))
        self.job = current.model_copy(update=changes)
        atomic_json(self.job_path, self.job.model_dump(mode='json'))

    def cancelled(self) -> bool:
        return self.cancel_path.exists()

    def persist_history(self) -> None:
        current = TrainingJob.model_validate_json(self.job_path.read_text(encoding='utf-8'))
        snapshot_path = self.workspace / 'snapshot.json'
        snapshot = json.loads(snapshot_path.read_text(encoding='utf-8')) if snapshot_path.exists() else {}
        record = {
            'schema_version': 1, 'training_run_id': current.id, 'model_id': current.model_id,
            'created_at': current.created_at.isoformat(),
            'finished_at': current.finished_at.isoformat() if current.finished_at else None,
            'training_status': current.state, 'error': current.error,
            'dataset_snapshot': current.snapshot_path,
            'train_image_ids': [item.id for item in current.train_images],
            'validation_image_ids': [item.id for item in current.validation_images],
            'class_mapping': snapshot.get('class_mapping'),
            'epochs': current.configuration.epochs,
            'training_configuration': current.configuration.model_dump(mode='json'),
            'augmentation_configuration': current.configuration.augmentation.model_dump(mode='json'),
            'seed': current.configuration.seed, 'final_metrics': current.metrics.model_dump(mode='json'),
            'model_path': current.model_path, 'dataset_summary': current.dataset_summary.model_dump(mode='json'),
            'warnings': current.warnings, 'checkpoint_validated': current.checkpoint_validated,
            'validation_smoke_test': {'validation_images_tested': current.validation_images_tested, 'images_with_predictions': current.smoke_images_with_predictions, 'total_predictions': current.smoke_total_predictions},
        }
        history_path = self.root / 'metadata' / 'training_history' / f'{current.id}.json'
        history_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(history_path, record)
        if self.model_root.exists():
            atomic_json(self.model_root / 'training_run.json', record)

    def prepare_dataset(self) -> tuple[Path, dict[int, int], dict]:
        dataset_payload = json.loads((self.root / 'metadata' / 'dataset.json').read_text(encoding='utf-8'))
        class_payload = json.loads((self.root / 'metadata' / 'classes.json').read_text(encoding='utf-8'))
        classes = sorted(class_payload.get('classes', []), key=lambda item: int(item['id']))
        class_map = {int(record['id']): index for index, record in enumerate(classes)}
        annotated = []
        for image in dataset_payload.get('images', []):
            annotation_path = self.root / 'annotations' / f"{image['id']}.json"
            if not annotation_path.exists():
                continue
            annotations = json.loads(annotation_path.read_text(encoding='utf-8')).get('annotations', [])
            annotations = [item for item in annotations if int(item['class_id']) in class_map]
            if annotations:
                annotated.append((image, annotations))
        if not annotated:
            raise ValueError('No valid annotated images were found')
        annotated.sort(key=lambda item: item[0]['id'])
        random.Random(self.job.configuration.seed).shuffle(annotated)
        if len(annotated) == 1:
            validation_count = 0
        else:
            validation_count = max(1, round(len(annotated) * self.job.configuration.validation_fraction))
            validation_count = min(validation_count, len(annotated) - 1)
        validation_ids = {item[0]['id'] for item in annotated[-validation_count:]} if validation_count else set()
        train_items = [item for item in annotated if item[0]['id'] not in validation_ids]
        validation_items = [item for item in annotated if item[0]['id'] in validation_ids]
        train_class_ids = {int(box['class_id']) for _, boxes in train_items for box in boxes}
        missing_class_ids = sorted(set(class_map) - train_class_ids)
        warnings = []
        if missing_class_ids:
            names = [next(record['name'] for record in classes if int(record['id']) == class_id) for class_id in missing_class_ids]
            warnings.append(f"Classes with zero training examples: {', '.join(names)}.")
        if validation_count == 0:
            warnings.append('Validation contains only 0 images; metrics may be unstable.')
        elif validation_count <= 2:
            image_word = 'image' if validation_count == 1 else 'images'
            warnings.append(f'Validation contains only {validation_count} {image_word}; metrics may be unstable.')
        summary = {
            'total_images': len(annotated), 'training_images': len(train_items), 'validation_images': len(validation_items),
            'total_annotations': sum(len(boxes) for _, boxes in annotated),
            'training_annotations': sum(len(boxes) for _, boxes in train_items),
            'validation_annotations': sum(len(boxes) for _, boxes in validation_items),
            'number_of_classes': len(classes), 'every_class_in_training': not missing_class_ids,
            'missing_training_class_ids': missing_class_ids,
        }
        snapshot = {
            'schema_version': 1, 'training_run_id': self.job.id, 'model_id': self.job.model_id,
            'created_at': self.job.created_at.isoformat(), 'seed': self.job.configuration.seed,
            'epochs': self.job.configuration.epochs,
            'validation_fraction': self.job.configuration.validation_fraction,
            'train_image_ids': [item[0]['id'] for item in train_items],
            'validation_image_ids': [item[0]['id'] for item in validation_items],
            'images': [{'id': image['id'], 'filename': image['filename'], 'relative_path': image['relative_path'], 'width': image['width'], 'height': image['height'], 'split': 'validation' if image['id'] in validation_ids else 'train', 'annotations': boxes} for image, boxes in annotated],
            'class_mapping': {'stable_to_yolo': class_map, 'classes': classes},
            'training_configuration': self.job.configuration.model_dump(mode='json'),
            'augmentation_configuration': self.job.configuration.augmentation.model_dump(mode='json'),
            'summary': summary, 'warnings': warnings,
        }
        self.workspace.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.workspace / 'snapshot.json'
        if snapshot_path.exists():
            raise ValueError('Immutable training snapshot already exists')
        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
        self.update(
            train_images=[{'id': image['id'], 'filename': image['filename']} for image, _ in train_items],
            validation_images=[{'id': image['id'], 'filename': image['filename']} for image, _ in validation_items],
            dataset_summary=summary, warnings=warnings,
            snapshot_path=f'generated/training/{self.job.id}/snapshot.json',
        )
        for warning in warnings:
            self.event('WARNING', warning)
        for split in ('train', 'val'):
            (self.workspace / 'images' / split).mkdir(parents=True, exist_ok=True)
            (self.workspace / 'labels' / split).mkdir(parents=True, exist_ok=True)
        for image_record, annotations in annotated:
            splits = ['val'] if image_record['id'] in validation_ids else ['train']
            source = (self.root / 'images' / image_record['relative_path']).resolve()
            if self.root / 'images' not in source.parents or not source.is_file():
                raise ValueError(f"Image file is missing: {image_record['filename']}")
            with Image.open(source) as image:
                normalized = ImageOps.exif_transpose(image).convert('RGB')
                width, height = normalized.size
                for split in splits:
                    destination = self.workspace / 'images' / split / f"{image_record['id']}.jpg"
                    normalized.save(destination, 'JPEG', quality=95)
            label_lines = []
            for box in annotations:
                x1, y1 = max(0.0, float(box['x1'])), max(0.0, float(box['y1']))
                x2, y2 = min(float(width), float(box['x2'])), min(float(height), float(box['y2']))
                if x2 <= x1 or y2 <= y1:
                    continue
                label_lines.append(f"{class_map[int(box['class_id'])]} {(x1+x2)/(2*width):.8f} {(y1+y2)/(2*height):.8f} {(x2-x1)/width:.8f} {(y2-y1)/height:.8f}")
            for split in splits:
                (self.workspace / 'labels' / split / f"{image_record['id']}.txt").write_text('\n'.join(label_lines), encoding='utf-8')
        data_yaml = self.workspace / 'dataset.yaml'
        data_yaml.write_text(yaml.safe_dump({'path': str(self.workspace), 'train': 'images/train', 'val': 'images/val', 'names': {index: record['name'] for index, record in enumerate(classes)}}), encoding='utf-8')
        self.model_root.mkdir(parents=True, exist_ok=True)
        atomic_json(self.model_root / 'class_mapping.json', {'stable_to_yolo': class_map, 'classes': classes})
        atomic_json(self.model_root / 'configuration.json', self.job.configuration.model_dump(mode='json'))
        shutil.copy2(data_yaml, self.model_root / 'dataset.yaml')
        return data_yaml, class_map, snapshot

    def augmentation_transforms(self):
        config = self.job.configuration.augmentation
        if not config.enabled:
            return []
        import albumentations as A
        if config.mode == 'manual':
            import cv2
            values = config.manual
            transforms = []
            normalized_rotation = values.rotation % 360
            if normalized_rotation:
                transforms.append(A.Rotate(limit=(values.rotation, values.rotation), border_mode=cv2.BORDER_CONSTANT, p=1.0))
            if values.horizontal_flip: transforms.append(A.HorizontalFlip(p=1.0))
            if values.vertical_flip: transforms.append(A.VerticalFlip(p=1.0))
            if values.brightness != 1 or values.contrast != 1: transforms.append(A.RandomBrightnessContrast(brightness_limit=(values.brightness-1, values.brightness-1), contrast_limit=(values.contrast-1, values.contrast-1), p=1.0))
            if values.saturation != 1 or values.hue: transforms.append(A.HueSaturationValue(hue_shift_limit=(round(values.hue), round(values.hue)), sat_shift_limit=(round((values.saturation-1)*100), round((values.saturation-1)*100)), val_shift_limit=0, p=1.0))
            if values.grayscale: transforms.append(A.ToGray(p=1.0))
            if values.pixelation: transforms.append(A.Downscale(scale_range=(max(.1, 1-values.pixelation/105), max(.1, 1-values.pixelation/105)), p=1.0))
            if values.blur: transforms.append(A.GaussianBlur(blur_limit=(3, max(3, int(values.blur)*2+1)), p=1.0))
            if values.noise: transforms.append(A.GaussNoise(std_range=(values.noise/255, values.noise/255), p=1.0))
            return transforms
        random_config = config.random
        pool = []
        enabled = set(random_config.enabled_operations)
        if 'rotation' in enabled: pool.append(A.RandomRotate90(p=1.0))
        if 'horizontal_flip' in enabled: pool.append(A.HorizontalFlip(p=1.0))
        if 'vertical_flip' in enabled: pool.append(A.VerticalFlip(p=1.0))
        if 'brightness' in enabled: pool.append(A.RandomBrightnessContrast(brightness_limit=.3, contrast_limit=0, p=1.0))
        if 'contrast' in enabled: pool.append(A.RandomBrightnessContrast(brightness_limit=0, contrast_limit=.3, p=1.0))
        if 'saturation' in enabled: pool.append(A.HueSaturationValue(hue_shift_limit=0, sat_shift_limit=40, val_shift_limit=0, p=1.0))
        if 'hue' in enabled: pool.append(A.HueSaturationValue(hue_shift_limit=18, sat_shift_limit=0, val_shift_limit=0, p=1.0))
        if 'grayscale' in enabled: pool.append(A.ToGray(p=1.0))
        if 'pixelation' in enabled: pool.append(A.Downscale(scale_range=(.92, 1.0), p=1.0))
        if 'blur' in enabled: pool.append(A.GaussianBlur(blur_limit=(3, 7), p=1.0))
        if 'noise' in enabled: pool.append(A.GaussNoise(std_range=(0, .063), p=1.0))
        if not pool or random_config.max_operations == 0:
            return []
        minimum = min(len(pool), random_config.min_operations)
        maximum = min(len(pool), max(minimum, random_config.max_operations))
        class VariableSomeOf(A.SomeOf):
            def __init__(self, transforms, min_operations, max_operations):
                self.min_operations = min_operations
                self.max_operations = max_operations
                super().__init__(transforms, n=max_operations, replace=False, p=1.0)

            def __call__(self, *args, force_apply=False, **data):
                self.n = self.py_random.randint(self.min_operations, self.max_operations)
                return super().__call__(*args, force_apply=force_apply, **data)

        subset = VariableSomeOf(pool, minimum, maximum)
        subset.set_random_seed(stable_seed(random_config.seed or self.job.id))
        return [subset]

    def generate_saved_augmentations(self, transforms) -> None:
        if not transforms:
            return
        import albumentations as A
        import cv2
        generated_root = self.root / 'generated' / 'augmented' / self.job.model_id
        generated_images = generated_root / 'images'
        generated_labels = generated_root / 'labels'
        generated_images.mkdir(parents=True, exist_ok=True)
        generated_labels.mkdir(parents=True, exist_ok=True)
        seed_value = self.job.configuration.augmentation.random.seed
        seed = stable_seed(seed_value or self.job.id)
        pipeline = A.Compose(transforms, bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels'], min_visibility=.01), seed=seed)
        for source in list((self.workspace / 'images' / 'train').glob('*.jpg')):
            labels_path = self.workspace / 'labels' / 'train' / f'{source.stem}.txt'
            lines = [line.split() for line in labels_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            class_labels = [int(parts[0]) for parts in lines]
            boxes = [tuple(float(value) for value in parts[1:5]) for parts in lines]
            image = cv2.imread(str(source))
            for index in range(self.job.configuration.augmentation.augmentations_per_image):
                result = pipeline(image=image, bboxes=boxes, class_labels=class_labels)
                name = f'{source.stem}_aug{index + 1}'
                output_image = generated_images / f'{name}.jpg'
                output_label = generated_labels / f'{name}.txt'
                cv2.imwrite(str(output_image), result['image'])
                output_label.write_text('\n'.join(f"{label} {' '.join(f'{value:.8f}' for value in box)}" for label, box in zip(result['class_labels'], result['bboxes'])), encoding='utf-8')
                shutil.copy2(output_image, self.workspace / 'images' / 'train' / output_image.name)
                shutil.copy2(output_label, self.workspace / 'labels' / 'train' / output_label.name)
        self.event('INFO', f'Saved augmented copies under generated/augmented/{self.job.model_id}.')

    def run(self) -> None:
        try:
            self.events_path.unlink(missing_ok=True)
            self.update(state='PREPARING', started_at=datetime.now(UTC), pid=os.getpid())
            self.event('INFO', 'Preparing an immutable YOLO training snapshot.')
            data_yaml, class_map, snapshot = self.prepare_dataset()
            self.event('INFO', f"Prepared {snapshot['summary']['training_images']} training and {snapshot['summary']['validation_images']} validation images.")
            if self.cancelled():
                self.update(state='CANCELLED', finished_at=datetime.now(UTC)); self.event('WARNING', 'Training cancelled before model initialization.'); return
            from ultralytics import YOLO
            transforms = self.augmentation_transforms()
            if self.job.configuration.augmentation.output_strategy == 'save':
                self.generate_saved_augmentations(transforms)
            model_reference = os.getenv('ANNOTIX_YOLO_MODEL', 'yolo11n.yaml')
            self.event('INFO', f'Loading local model definition: {model_reference}.')
            model = YOLO(model_reference)

            def on_train_start(trainer):
                self.update(state='TRAINING')
                self.event('INFO', f'YOLO training started for {int(trainer.epochs)} epochs.')

            def on_batch_end(trainer):
                if self.cancelled(): trainer.stop = True

            def on_fit_epoch_end(trainer):
                metrics = {str(key): float(value) for key, value in getattr(trainer, 'metrics', {}).items() if isinstance(value, (int, float)) or hasattr(value, 'item')}
                epoch = int(trainer.epoch) + 1
                total = int(trainer.epochs)
                if epoch > total:
                    return
                csv_metrics = {}
                if Path(trainer.csv).exists():
                    with Path(trainer.csv).open('r', encoding='utf-8') as results_file:
                        rows = list(csv.DictReader(results_file))
                    if rows:
                        csv_metrics = {key.strip(): float(value) for key, value in rows[-1].items() if value not in (None, '')}
                box_loss = csv_metrics.get('train/box_loss')
                class_loss = csv_metrics.get('train/cls_loss')
                dfl_loss = csv_metrics.get('train/dfl_loss')
                validation_box_loss = csv_metrics.get('val/box_loss')
                validation_class_loss = csv_metrics.get('val/cls_loss')
                validation_dfl_loss = csv_metrics.get('val/dfl_loss')
                training_losses = [value for value in (box_loss, class_loss, dfl_loss) if value is not None]
                validation_losses = [value for value in (validation_box_loss, validation_class_loss, validation_dfl_loss) if value is not None]
                values = {
                    'epoch': epoch, 'total_epochs': total, 'progress': min(100, epoch / total * 100),
                    'loss': sum(training_losses) if training_losses else None, 'box_loss': box_loss, 'class_loss': class_loss,
                    'validation_loss': sum(validation_losses) if validation_losses else None,
                    'validation_box_loss': validation_box_loss, 'validation_class_loss': validation_class_loss,
                    'precision': csv_metrics.get('metrics/precision(B)', metrics.get('metrics/precision(B)')),
                    'recall': csv_metrics.get('metrics/recall(B)', metrics.get('metrics/recall(B)')),
                    'map50': csv_metrics.get('metrics/mAP50(B)', metrics.get('metrics/mAP50(B)')), 'map50_95': csv_metrics.get('metrics/mAP50-95(B)', metrics.get('metrics/mAP50-95(B)')),
                }
                current = TrainingJob.model_validate_json(self.job_path.read_text(encoding='utf-8'))
                self.update(metrics=current.metrics.model_copy(update=values))
                self.event('INFO', f'Epoch {epoch}/{total} completed.', 'metrics', values)
                if self.cancelled(): trainer.stop = True

            model.add_callback('on_train_start', on_train_start)
            model.add_callback('on_train_batch_end', on_batch_end)
            model.add_callback('on_fit_epoch_end', on_fit_epoch_end)
            device = self.job.configuration.device
            device_arg = 'cpu' if device == 'cpu' else 0 if device == 'gpu' else None
            run_dir = self.model_root / 'run'
            on_the_fly = self.job.configuration.augmentation.output_strategy == 'on_the_fly'
            model.train(data=str(data_yaml), epochs=self.job.configuration.epochs, imgsz=self.job.configuration.image_size, batch=self.job.configuration.batch_size, device=device_arg, seed=self.job.configuration.seed, deterministic=True, project=str(self.model_root), name='run', exist_ok=True, workers=0, augmentations=(transforms or None) if on_the_fly else None, degrees=0, translate=0, scale=0, shear=0, perspective=0, flipud=0, fliplr=0, mosaic=0, mixup=0, cutmix=0, hsv_h=0, hsv_s=0, hsv_v=0, auto_augment=None, erasing=0, plots=False, verbose=True)
            if self.cancelled():
                self.update(state='CANCELLED', finished_at=datetime.now(UTC)); self.event('WARNING', 'Training cancelled. Partial checkpoints were retained.'); return
            weights = run_dir / 'weights'
            for name in ('best.pt', 'last.pt'):
                if (weights / name).exists(): shutil.copy2(weights / name, self.model_root / name)
            best_checkpoint = self.model_root / 'best.pt'
            if not best_checkpoint.is_file() or best_checkpoint.stat().st_size == 0:
                raise ValueError('Expected trained checkpoint best.pt was not created')
            validated_model = YOLO(str(best_checkpoint))
            validation_sources = [str(self.workspace / 'images' / 'val' / f"{item['id']}.jpg") for item in snapshot['images'] if item['split'] == 'validation']
            smoke_with_predictions = smoke_total_predictions = 0
            if validation_sources:
                self.event('INFO', f'Running inference smoke test on {len(validation_sources)} validation images.')
                smoke_results = validated_model.predict(source=validation_sources, conf=.25, max_det=100, agnostic_nms=False, verbose=False)
                smoke_counts = [len(result.boxes) if result.boxes is not None else 0 for result in smoke_results]
                smoke_with_predictions = sum(count > 0 for count in smoke_counts)
                smoke_total_predictions = sum(smoke_counts)
            finished_at = datetime.now(UTC)
            self.update(state='COMPLETED', finished_at=finished_at, error=None, model_path=f'models/{self.job.model_id}/best.pt', checkpoint_validated=True, validation_images_tested=len(validation_sources), smoke_images_with_predictions=smoke_with_predictions, smoke_total_predictions=smoke_total_predictions)
            self.event('INFO', f'Training completed. Model saved as {self.job.model_id}.')
        except Exception as error:
            self.update(state='FAILED', finished_at=datetime.now(UTC), error=str(error))
            self.event('ERROR', str(error))
            (self.root / 'logs' / f'training-{self.job.id}.traceback.log').write_text(traceback.format_exc(), encoding='utf-8')
        finally:
            try:
                self.persist_history()
            except Exception as history_error:
                self.event('ERROR', f'Could not persist training history: {history_error}')
            self.cancel_path.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--job-id', required=True)
    arguments = parser.parse_args()
    Worker(arguments.project_id, arguments.job_id).run()
