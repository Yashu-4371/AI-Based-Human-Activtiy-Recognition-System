"""
Shared CSV/metadata handling for every dataset source (own webcam recordings,
public video clips, converted public skeleton datasets).

training_features.csv is the single merged training table. Each source
(`source_dataset`) owns its rows: re-running an extraction/ingestion step
REPLACES that source's rows and leaves all other sources untouched, so
adding a dataset never silently destroys another one. The previous file is
always backed up first.

Columns: FEATURE_NAMES + activity_label, subject_id, source_dataset,
source_clip, frame_index, timestamp_sec. subject_id must be unique per real person across
sources (ingesters namespace it as "<source_dataset>-<subject>").
"""

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from app.ml.feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION

VALID_LABELS = ["walking", "standing", "sitting", "lying"]
META_COLUMNS = ["activity_label", "subject_id", "source_dataset", "source_clip", "frame_index", "timestamp_sec"]
COLUMNS = FEATURE_NAMES + META_COLUMNS


def _read_rows(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or any(c not in reader.fieldnames for c in COLUMNS):
            return None  # incompatible (older schema, e.g. synthetic v1)
        return list(reader)


def merge_source_into_csv(csv_path: Path, new_rows: List[dict], source_dataset: str) -> int:
    """Replaces all rows of `source_dataset` in csv_path with new_rows. Returns total rows written."""
    existing = _read_rows(csv_path)
    if csv_path.exists():
        backup = csv_path.with_suffix(f".backup-{int(datetime.now().timestamp())}.csv")
        shutil.copy(csv_path, backup)
        print(f"Existing {csv_path.name} backed up to {backup.name}")
    if existing is None:
        print("NOTE: existing training CSV uses an incompatible/older feature schema; it is NOT carried over.")
        existing = []

    kept = [r for r in existing if r["source_dataset"] != source_dataset]
    for r in new_rows:
        r.setdefault("source_dataset", source_dataset)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
        writer.writerows(new_rows)
    return len(kept) + len(new_rows)


def write_dataset_info(csv_path: Path, info_path: Path, extra: dict = None) -> dict:
    rows = _read_rows(csv_path) or []
    subjects = sorted({r["subject_id"] for r in rows})
    clips = {(r["source_dataset"], r["source_clip"]) for r in rows}
    per_source = {}
    for src in sorted({r["source_dataset"] for r in rows}):
        src_rows = [r for r in rows if r["source_dataset"] == src]
        per_source[src] = {
            "subjects": len({r["subject_id"] for r in src_rows}),
            "clips": len({r["source_clip"] for r in src_rows}),
            "samples": len(src_rows),
            "samples_per_label": dict(Counter(r["activity_label"] for r in src_rows)),
        }
    subjects_per_label = {
        lbl: len({r["subject_id"] for r in rows if r["activity_label"] == lbl}) for lbl in VALID_LABELS
    }
    info = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "num_subjects": len(subjects),
        "subjects": subjects,
        "num_clips": len(clips),
        "total_frames_used": len(rows),
        "frames_per_label": dict(Counter(r["activity_label"] for r in rows)),
        "subjects_per_label": subjects_per_label,
        "per_source": per_source,
    }
    if extra:
        info.update(extra)
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return info
