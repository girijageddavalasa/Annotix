import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from services.export_service import ExportValidationError, class_mapping, create_export, yolo_box


class ExportServiceTests(unittest.TestCase):
    def setUp(self):
        temporary_parent = Path(__file__).parent / ".tmp"
        temporary_parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_parent)
        self.root = Path(self.temporary.name) / "project-a"
        for directory in ("images", "annotations", "metadata/training_history", "generated/training/job-1"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        classes = [{"id": 7, "name": "dog", "color": "#ffffff", "created_at": "2026-01-01T00:00:00Z"}, {"id": 2, "name": "person", "color": "#000000", "created_at": "2026-01-01T00:00:00Z"}]
        images = []
        for index, image_id in enumerate(("image-a", "image-b")):
            filename = f"source-{index}.jpg"
            (self.root / "images" / filename).write_bytes(b"immutable-image-" + bytes([index]))
            images.append({"id": image_id, "filename": filename, "relative_path": filename, "width": 100, "height": 50})
            (self.root / "annotations" / f"{image_id}.json").write_text(json.dumps({"image_id": image_id, "annotations": [{"id": f"box-{index}", "image_id": image_id, "class_id": 7, "x1": 10, "y1": 5, "x2": 50, "y2": 25}]}), encoding="utf-8")
        (self.root / "metadata" / "dataset.json").write_text(json.dumps({"images": images}), encoding="utf-8")
        (self.root / "metadata" / "classes.json").write_text(json.dumps({"next_id": 8, "classes": classes}), encoding="utf-8")
        snapshot = {"images": [{"id": "image-a", "split": "train"}, {"id": "image-b", "split": "validation"}]}
        (self.root / "generated" / "training" / "job-1" / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
        history = {"state": "COMPLETED", "finished_at": "2026-01-02T00:00:00Z", "snapshot_path": "generated/training/job-1/snapshot.json"}
        (self.root / "metadata" / "training_history" / "job-1.json").write_text(json.dumps(history), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def generate(self, root=None):
        target = root or self.root
        with patch("services.export_service.get_current_project_id", return_value=target.name), patch("services.export_service.get_project_root", return_value=target):
            return create_export()

    def test_yolo_coordinate_conversion(self):
        self.assertEqual(yolo_box(10, 5, 50, 25, 100, 50), (.3, .3, .4, .4))

    def test_class_mapping_uses_immutable_id_order(self):
        mapping, names = class_mapping([{"id": 7, "name": "dog"}, {"id": 2, "name": "person"}])
        self.assertEqual(mapping, {2: 0, 7: 1})
        self.assertEqual(names, ["person", "dog"])

    def test_training_snapshot_membership_is_preserved(self):
        record = self.generate()
        workspace = self.root / "generated" / "exports" / record.id
        self.assertTrue((workspace / "images" / "train" / "image-a.jpg").exists())
        self.assertTrue((workspace / "images" / "val" / "image-b.jpg").exists())
        self.assertEqual((record.stats.train_images, record.stats.validation_images), (1, 1))

    def test_invalid_annotation_is_rejected(self):
        path = self.root / "annotations" / "image-a.json"
        payload = json.loads(path.read_text())
        payload["annotations"][0]["x2"] = 101
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ExportValidationError):
            self.generate()

    def test_export_does_not_modify_sources(self):
        watched = list((self.root / "images").glob("*")) + list((self.root / "annotations").glob("*"))
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in watched}
        record = self.generate()
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in watched}
        self.assertEqual(before, after)
        with zipfile.ZipFile(self.root / "generated" / "exports" / record.id / record.filename) as archive:
            self.assertIn("data.yaml", archive.namelist())

    def test_project_isolation(self):
        other = Path(self.temporary.name) / "project-b"
        for directory in ("images", "annotations", "metadata"):
            (other / directory).mkdir(parents=True, exist_ok=True)
        (other / "metadata" / "dataset.json").write_text('{"images": []}', encoding="utf-8")
        (other / "metadata" / "classes.json").write_text('{"classes": []}', encoding="utf-8")
        first = self.generate()
        self.assertTrue((self.root / "generated" / "exports" / first.id).exists())
        with self.assertRaises(ExportValidationError):
            self.generate(other)
        self.assertFalse((other / "generated" / "exports" / first.id).exists())


if __name__ == "__main__":
    unittest.main()
