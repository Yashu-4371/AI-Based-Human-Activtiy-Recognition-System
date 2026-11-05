"""
Turns labeled video clips into rows of app/ml/data/training_features.csv using
the EXACT SAME PoseEstimator and FeatureExtractor classes the live webcam
pipeline uses. This is what guarantees the model sees the same feature
distribution at train time as at inference time.

Supported input layouts under app/ml/data/raw_clips/ (mix freely):

  raw_clips/<label>/<subject>_<anything>.mp4        -> source_dataset "own_recordings"
        (produced by record_clips.py or your own recordings)

  raw_clips/<dataset_name>/<label>/<subject>_<anything>.mp4
        -> source_dataset "<dataset_name>", subject_id "<dataset_name>-<subject>"
        (clips exported from a public video dataset; one folder per dataset)

  <label> must be one of: walking, standing, sitting, lying.
  <subject> is the token before the first underscore in the file name. It is
  kept as subject_id and drives the subject-wise evaluation in train_model.py.
  Clips without a subject token get subject "unknown" - avoid that.

Run (from backend/):   python -m app.ml.data.extract_features_from_clips

Rows of each source are REPLACED in training_features.csv; other sources
(e.g. converted skeleton datasets) are preserved. See dataset_io.py.
Every Nth frame is processed (--frame-stride, default 2). Frames without a
detected person are skipped.
"""

import argparse
from collections import Counter
from pathlib import Path
from typing import List

import cv2

from app.ml.pose_estimator import PoseEstimator
from app.ml.feature_extractor import FeatureExtractor, FEATURE_NAMES
from app.ml.data.dataset_io import VALID_LABELS, merge_source_into_csv, write_dataset_info

RAW_CLIPS_DIR = Path(__file__).parent / "raw_clips"
OUTPUT_CSV = Path(__file__).parent / "training_features.csv"
DATASET_INFO_JSON = Path(__file__).parent / "dataset_info.json"
OWN_SOURCE = "own_recordings"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def _iter_clips():
    """Yields (clip_path, label, subject_id, source_dataset)."""
    if not RAW_CLIPS_DIR.exists():
        return
    for top in sorted(RAW_CLIPS_DIR.iterdir()):
        if not top.is_dir():
            continue
        if top.name in VALID_LABELS:
            label_dirs = [(top, OWN_SOURCE, "")]
        else:
            label_dirs = [(d, top.name, top.name + "-") for d in sorted(top.iterdir()) if d.is_dir() and d.name in VALID_LABELS]
        for label_dir, source, prefix in label_dirs:
            for clip_path in sorted(label_dir.iterdir()):
                if clip_path.suffix.lower() in VIDEO_EXTENSIONS:
                    subject = clip_path.stem.split("_")[0] or "unknown"
                    yield clip_path, label_dir.name, prefix + subject, source


def _extract_clip(clip_path: Path, label: str, subject: str, source: str, frame_stride: int) -> List[dict]:
    cap = cv2.VideoCapture(str(clip_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    frame_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    frame_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    aspect_ratio = (frame_w / frame_h) if frame_w and frame_h else 1.0
    clip_id = f"{source}/{label}/{clip_path.name}"

    pose_estimator = PoseEstimator()
    feature_extractor = FeatureExtractor()
    rows = []
    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_index % frame_stride == 0:
                landmarks = pose_estimator.process(frame)
                if landmarks is not None:
                    timestamp_sec = frame_index / fps
                    feature_vector = feature_extractor.extract(landmarks, timestamp_sec, aspect_ratio)
                    if feature_vector is not None:
                        row = {name: float(value) for name, value in zip(FEATURE_NAMES, feature_vector)}
                        row["activity_label"] = label
                        row["subject_id"] = subject
                        row["source_dataset"] = source
                        row["source_clip"] = clip_id
                        row["frame_index"] = frame_index
                        row["timestamp_sec"] = round(timestamp_sec, 4)
                        rows.append(row)
                else:
                    feature_extractor.reset()

            frame_index += 1
    finally:
        pose_estimator.close()
        cap.release()

    return rows


def build_dataset(frame_stride: int = 2) -> None:
    clips = list(_iter_clips())
    if not clips:
        raise SystemExit(
            f"No clips found under {RAW_CLIPS_DIR}.\n"
            "Record some with `python -m app.ml.data.record_clips --subject s1 --label walking` "
            "(repeat for all four activities and several people), or drop in clips from a public "
            "dataset as raw_clips/<dataset_name>/<label>/<subject>_<name>.mp4, then re-run this script."
        )

    rows_by_source: dict = {}
    for clip_path, label, subject, source in clips:
        rows = _extract_clip(clip_path, label, subject, source, frame_stride)
        print(f"  [{source}] {clip_path.name:36s} label={label:9s} subject={subject:16s} usable_frames={len(rows)}")
        rows_by_source.setdefault(source, []).extend(rows)

    if not any(rows_by_source.values()):
        raise SystemExit(
            "No usable frames were extracted from any clip (MediaPipe never detected a person). "
            "Check lighting/framing and that the full body is visible, then re-record."
        )

    total = 0
    for source, rows in rows_by_source.items():
        total = merge_source_into_csv(OUTPUT_CSV, rows, source)

    info = write_dataset_info(OUTPUT_CSV, DATASET_INFO_JSON, extra={"frame_stride": frame_stride})
    print(f"\nTraining CSV now has {total} rows, {info['num_subjects']} subject(s), {info['num_clips']} clip(s)")
    print(f"Per-label counts: {info['frames_per_label']}")
    print(f"Subjects per label: {info['subjects_per_label']}")
    print(f"-> {OUTPUT_CSV}\n-> {DATASET_INFO_JSON}")
    missing = [l for l in VALID_LABELS if info["frames_per_label"].get(l, 0) == 0]
    if missing:
        print(f"\nWARNING: no usable frames for: {missing}. Add data for these before training.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frame-stride", type=int, default=2, help="Process every Nth frame (default: 2)")
    args = parser.parse_args()
    build_dataset(frame_stride=args.frame_stride)


if __name__ == "__main__":
    main()
