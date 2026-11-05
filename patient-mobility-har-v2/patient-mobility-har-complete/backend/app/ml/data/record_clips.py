"""
Records short labeled webcam clips for the four target activities
(walking, standing, sitting, lying) so a REAL dataset — recorded on
your actual camera, at your actual angle/lighting — can replace the
synthetic training data.

Run locally (needs a real webcam; won't work in a headless container):

    python -m app.ml.data.record_clips --subject s1 --label walking
    python -m app.ml.data.record_clips --subject s1 --label standing
    python -m app.ml.data.record_clips --subject s1 --label sitting
    python -m app.ml.data.record_clips --subject s1 --label lying
    python -m app.ml.data.record_clips --subject s2 --label walking
    ... repeat for a few different people/subjects and a few clips per
    activity per subject. More subjects = a more honest test-set split
    later (train/test is split BY SUBJECT, not by random frame, so the
    model is evaluated on people it never saw during training).

Controls once the preview window is open:
    SPACE  start/stop recording the current clip
    n      finish current clip and start a new one (same label/subject)
    q      quit

Clips are saved as .mp4 under:
    app/ml/data/raw_clips/<label>/<subject>_<timestamp>_<index>.mp4

--subject is any short id you choose (e.g. "s1", "mom", "dad") — it's
only used to group clips for the subject-wise train/test split in
train_model.py, never stored anywhere else.
"""

import argparse
import time
from pathlib import Path

import cv2

RAW_CLIPS_DIR = Path(__file__).parent / "raw_clips"
VALID_LABELS = ["walking", "standing", "sitting", "lying"]


def record(subject: str, label: str, camera_index: int, fps: int) -> None:
    if label not in VALID_LABELS:
        raise SystemExit(f"--label must be one of {VALID_LABELS}, got {label!r}")

    out_dir = RAW_CLIPS_DIR / label
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {camera_index}. Try a different --camera-index.")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = None
    recording = False
    clip_index = 0

    print(f"Recording '{label}' clips for subject '{subject}'. SPACE=start/stop, n=new clip, q=quit.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Frame read failed — stopping.")
                break

            display = frame.copy()
            status = "RECORDING" if recording else "PAUSED"
            color = (0, 0, 255) if recording else (0, 200, 0)
            cv2.putText(display, f"{label} | {subject} | clip {clip_index} | {status}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.imshow("record_clips - SPACE start/stop, n new clip, q quit", display)

            if recording and writer is not None:
                writer.write(frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord(" "):
                if not recording:
                    height, width = frame.shape[:2]
                    filename = out_dir / f"{subject}_{int(time.time())}_{clip_index}.mp4"
                    writer = cv2.VideoWriter(str(filename), fourcc, fps, (width, height))
                    recording = True
                    print(f"Started recording -> {filename}")
                else:
                    recording = False
                    if writer is not None:
                        writer.release()
                        writer = None
                    clip_index += 1
                    print("Stopped recording.")
            elif key == ord("n"):
                if recording and writer is not None:
                    writer.release()
                    writer = None
                recording = False
                clip_index += 1
    finally:
        if writer is not None:
            writer.release()
        cap.release()
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", required=True, help="Short id for the person being recorded (e.g. s1)")
    parser.add_argument("--label", required=True, choices=VALID_LABELS)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--fps", type=int, default=15)
    args = parser.parse_args()
    record(args.subject, args.label, args.camera_index, args.fps)


if __name__ == "__main__":
    main()
