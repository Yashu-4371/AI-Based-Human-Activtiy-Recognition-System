# Activity recognition: data, training, evaluation, live test

Pipeline (unchanged): Camera → MediaPipe Pose → `FeatureExtractor` (14 features) → Random Forest →
`ActivitySmoother` (≈1 s soft vote) → displayed / recorded activity (lying, sitting, standing, walking).

## What the shipped model is

The repository ships NO real training data. `models_store/` contains a **placeholder** trained with
`--synthetic` (generated feature rows, no people). Its metrics (`data_source: synthetic`) say nothing about
real accuracy, and the backend logs a warning when it is loaded. **Train on real data before relying on it.**
A model trained on a different feature layout is refused at load time (check the backend log).

## 1. Collect / add real data (more *different people* matters more than more frames)

Subject IDs drive the evaluation, so use one stable ID per real person.

**A. Your own recordings (webcam)**
```bash
cd backend
python -m app.ml.data.record_clips --subject s01 --label lying     # repeat per label and per person
python -m app.ml.data.extract_features_from_clips                  # video -> features, same code as live
```
Per activity and per person record varied versions: lying on back/side/curled, arms and legs in different
positions; sitting upright/leaning forward/back; standing with arms up/down, legs apart/together;
walking slow/fast, toward/away/across the camera; different distances, angles, rooms and lighting.

**B. Public video clips** – put them in `app/ml/data/raw_clips/<dataset_name>/<label>/<subject>_<name>.mp4`
(`<label>` ∈ walking, standing, sitting, lying) and run the same extraction command. Subjects become
`<dataset_name>-<subject>`.

**C. Public skeleton datasets (keypoints only, no video)** – export to the long CSV described in
`app/ml/data/ingest_skeleton_dataset.py` (formats: `coco17`, `openpose_coco18`, `openpose_body25`, `mediapipe33`),
write a small JSON mapping the dataset's activity names to the four labels (anything unmapped, e.g. falls or
jumping, is dropped and counted), then:
```bash
python -m app.ml.data.ingest_skeleton_dataset --csv skeletons.csv --source-name upfall \
    --format coco17 --width 640 --height 480 --fps 18 --label-map labels.json
```
Conversion limits: only the 13 core joints are used (all 14 classifier features derive from them); missing
MediaPipe points are filled with the nearest joint; a different pose estimator has different noise than
MediaPipe, so check that held-out MediaPipe-extracted subjects still score well when such data is mixed in.
Verify which subjects/activities a file really contains from the script's printed counts; do not assume.

Each source's rows are replaced when you re-run its step; other sources are kept. The previous CSV is backed up.

## 2. Train and evaluate

```bash
cd backend
python -m app.ml.train_model              # real data, subject-wise evaluation, prints the full report
python -m app.ml.train_model --synthetic  # placeholder only (no evidence of accuracy)
```
Outputs `models_store/activity_rf.pkl`, `activity_scaler.pkl`, `metrics.json` (also served at `/api/v1/ml/metrics`).

| Real subjects | Method | `generalization_evidence` |
|---|---|---|
| ≥ 6 | ~20 % of **people** held out as test; validation = leave-one-subject-out on the rest | `subject_wise_holdout` |
| 2–5 | leave-one-subject-out only (limited, no untouched test set) | `subject_wise_cv_limited` |
| 1 | random frame split (**not** a generalization estimate) | `none_random_split` |
| synthetic | random split of generated data | `none_synthetic` |

The report lists subjects/clips/samples, per-class precision/recall/F1, confusion matrix, most common
confusions, per-held-out-subject accuracy, an offline replay of the live smoother, and the dataset limitations.
Random Forest hyperparameters are the original ones (200 trees, depth 12, min leaf 3); `class_weight="balanced"`
is enabled only if classes are imbalanced > 1.5×. No tuning was done because no real multi-subject data existed.

## 3. Feature design (schema v2)

All features are relative to the person's own torso length, so they do not depend on camera distance or
position; x is corrected by the frame aspect ratio; speed uses a 0.6 s time window (fps-independent).
Fall/inactivity detection is unaffected: it reads dedicated signals with their original definitions.

## 4. Live test with your camera

1. Backend: `cd backend && uvicorn app.main:app --reload` (first run with a newer MediaPipe downloads
   `models_store/pose_landmarker_full.task`; offline, download it manually from the URL in `pose_estimator.py`).
2. Frontend: `cd frontend && npm install && npm run dev`, log in, add a patient/camera, start monitoring.
3. Test each activity at different distances/angles; watch label + confidence in the live view. Expect a
   ~0.5–1 s delay on activity changes (smoothing). Tune `ACTIVITY_SMOOTHING_WINDOW_SEC` / `ACTIVITY_SWITCH_MARGIN`
   in `.env` if too slow or flickery.
4. Judge by the subject-wise report **and** by trying people who are not in the training data.
