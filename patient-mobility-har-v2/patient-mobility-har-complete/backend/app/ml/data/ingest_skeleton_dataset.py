"""
Converts a public 2D-skeleton dataset (already exported as CSV) into rows of
training_features.csv, using the SAME FeatureExtractor as live inference.

Required long-format CSV (one row per person per frame; write a small
converter from the dataset's native files if it differs):

    subject,clip,frame,activity,kp0_x,kp0_y,kp0_c,kp1_x,kp1_y,kp1_c,...

  subject   person identifier (kept as subject_id, namespaced "<source>-<subject>")
  clip      recording/trial identifier (frames of one clip must share it)
  frame     integer frame number (sorted per clip); time = frame / --fps
  activity  the dataset's own activity name/code (mapped by --label-map)
  kp{i}_x/_y   keypoint i in the chosen --format's index order (pixels, or 0..1 with
               --normalized); kp{i}_c is an optional confidence

--label-map is a JSON file mapping dataset activity values to the four
project labels, e.g. {"walking": "walking", "sitting": "sitting",
"laying": "lying", "standing": "standing"}. Activities not in the map (e.g.
falls, jumping) are dropped and counted - never guessed.

Example (from backend/):
  python -m app.ml.data.ingest_skeleton_dataset --csv upfall_skeleton.csv \
      --source-name upfall --format coco17 --width 640 --height 480 --fps 18 \
      --label-map upfall_labels.json

Only what the file actually contains is ingested; the script prints the
real subject/clip/frame counts per label afterwards.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.data.dataset_io import VALID_LABELS, merge_source_into_csv, write_dataset_info
from app.ml.data.skeleton_adapters import NUM_KEYPOINTS, SUPPORTED_FORMATS, to_mediapipe_landmarks
from app.ml.feature_extractor import FEATURE_NAMES, FeatureExtractor

OUTPUT_CSV = Path(__file__).parent / "training_features.csv"
DATASET_INFO_JSON = Path(__file__).parent / "dataset_info.json"


def convert_dataframe(
    df: pd.DataFrame, source_name: str, fmt: str, width: float, height: float, fps: float,
    label_map: dict, normalized: bool = False, frame_stride: int = 1,
):
    """Returns (rows, stats). Pure function - used by the CLI and by tests."""
    n_kp = NUM_KEYPOINTS[fmt]
    has_conf = "kp0_c" in df.columns
    for col in ["subject", "clip", "frame", "activity"] + [f"kp{i}_{a}" for i in range(n_kp) for a in "xy"]:
        if col not in df.columns:
            raise ValueError(f"Input CSV is missing required column {col!r}")

    dropped_activities: Counter = Counter()
    skipped_frames = 0
    rows = []
    aspect_ratio = width / height  # source image shape; also needed when keypoints are normalized

    for (subject, clip, activity), group in df.groupby(["subject", "clip", "activity"], sort=False):
        label = label_map.get(str(activity))
        if label is None:
            dropped_activities[str(activity)] += len(group)
            continue
        if label not in VALID_LABELS:
            raise ValueError(f"label-map maps {activity!r} to invalid label {label!r}")

        extractor = FeatureExtractor()
        group = group.sort_values("frame")
        clip_id = f"{source_name}/{subject}/{clip}"
        for i, (_, r) in enumerate(group.iterrows()):
            if i % frame_stride:
                continue
            cols = [[r[f"kp{k}_x"], r[f"kp{k}_y"]] + ([r[f"kp{k}_c"]] if has_conf else []) for k in range(n_kp)]
            landmarks = to_mediapipe_landmarks(np.array(cols, dtype=float), fmt, width, height, normalized)
            if landmarks is None:
                extractor.reset()
                skipped_frames += 1
                continue
            vec = extractor.extract(landmarks, float(r["frame"]) / fps, aspect_ratio)
            if vec is None:
                skipped_frames += 1
                continue
            row = {n: float(v) for n, v in zip(FEATURE_NAMES, vec)}
            row.update(activity_label=label, subject_id=f"{source_name}-{subject}",
                       source_dataset=source_name, source_clip=clip_id, frame_index=int(r["frame"]),
                       timestamp_sec=round(float(r["frame"]) / fps, 4))
            rows.append(row)

    return rows, {"dropped_activity_frames": dict(dropped_activities), "skipped_frames_missing_joints": skipped_frames}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, nargs="+", help="Long-format skeleton CSV file(s)")
    p.add_argument("--source-name", required=True, help="Short dataset name, e.g. upfall")
    p.add_argument("--format", required=True, choices=SUPPORTED_FORMATS)
    p.add_argument("--width", type=float, required=True, help="Source image width in pixels")
    p.add_argument("--height", type=float, required=True, help="Source image height in pixels")
    p.add_argument("--fps", type=float, required=True, help="Dataset frame rate (for velocity timing)")
    p.add_argument("--label-map", required=True, help="JSON file: dataset activity -> walking|standing|sitting|lying")
    p.add_argument("--normalized", action="store_true", help="Keypoints already in 0..1")
    p.add_argument("--frame-stride", type=int, default=1)
    a = p.parse_args()

    label_map = {str(k): v for k, v in json.loads(Path(a.label_map).read_text()).items()}
    df = pd.concat([pd.read_csv(c) for c in a.csv], ignore_index=True)
    rows, stats = convert_dataframe(df, a.source_name, a.format, a.width, a.height, a.fps, label_map,
                                    a.normalized, a.frame_stride)
    if not rows:
        raise SystemExit(f"No usable rows produced. Stats: {stats}")

    total = merge_source_into_csv(OUTPUT_CSV, rows, a.source_name)
    info = write_dataset_info(OUTPUT_CSV, DATASET_INFO_JSON)
    print(f"Ingested {len(rows)} rows from {a.source_name}; conversion stats: {stats}")
    print(f"Training CSV now: {total} rows, {info['num_subjects']} subjects, {info['num_clips']} clips")
    print(f"Per-label: {info['frames_per_label']}  | subjects per label: {info['subjects_per_label']}")


if __name__ == "__main__":
    main()
