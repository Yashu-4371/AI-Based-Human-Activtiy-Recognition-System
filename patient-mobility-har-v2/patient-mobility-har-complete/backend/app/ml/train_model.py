"""
Offline training + evaluation for the Random Forest activity classifier.

    python -m app.ml.train_model              # train on real data (training_features.csv)
    python -m app.ml.train_model --synthetic  # placeholder model, NOT evidence of accuracy

Data: app/ml/data/training_features.csv, built by
  extract_features_from_clips.py (video) and/or ingest_skeleton_dataset.py
  (converted public skeleton datasets). It never falls back to synthetic
  data silently: without a CSV this script stops and tells you what to do.

Evaluation is chosen from how many REAL subjects (people) the CSV contains.
A person never appears in both training and evaluation folds:

  >= 6 subjects  "subject_wise_holdout": ~20% of subjects are held out as a
                 TEST set (never used for fitting or tuning). The remaining
                 subjects are the train+validation pool; validation = pooled
                 leave-one-subject-out (LOSO). Headline metrics = held-out test.
  2-5 subjects   "subject_wise_loso_limited": pooled LOSO only, no separate
                 test set. Headline metrics = pooled LOSO. Flagged as limited.
  1 subject      "none_random_split": random frame split. NOT a
                 generalization estimate (frames of one person are near
                 duplicates). Reported as such.
  --synthetic    "none_synthetic": random split of generated data.

The deployed model is finally fit on ALL subjects; the reported metrics come
from models that did not see the evaluated subjects. Random Forest
hyperparameters are unchanged from the original project: no real multi-subject
data existed to justify tuning them. class_weight="balanced" is only switched
on when the data itself is imbalanced (largest/smallest class > 1.5x).
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.config import settings
from app.ml.activity_classifier import MODEL_FILENAME, SCALER_FILENAME
from app.ml.activity_smoother import ActivitySmoother
from app.ml.data.dataset_io import COLUMNS, VALID_LABELS
from app.ml.feature_extractor import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.utils.logger import get_logger

logger = get_logger(__name__)

DATA_PATH = Path(__file__).parent / "data" / "training_features.csv"
DATASET_INFO_PATH = Path(__file__).parent / "data" / "dataset_info.json"
METRICS_FILENAME = "metrics.json"

RF_PARAMS = {"n_estimators": 200, "max_depth": 12, "min_samples_leaf": 3}
MIN_SUBJECTS_FOR_TEST_SET = 6
TEST_SUBJECT_FRACTION = 0.2
SEED = 42


# ------------------------------------------------------------------ data

def load_training_data(synthetic: bool) -> Tuple[pd.DataFrame, str]:
    if synthetic:
        from app.ml.data.generate_synthetic_data import generate_dataset

        logger.warning("Training on SYNTHETIC placeholder data. Metrics are NOT evidence of real accuracy.")
        return generate_dataset(), "synthetic"

    if not DATA_PATH.exists():
        raise SystemExit(
            f"No training data at {DATA_PATH}.\n"
            "Build it first (see docs/activity_recognition.md):\n"
            "  python -m app.ml.data.record_clips --subject s1 --label walking   (repeat per activity/person)\n"
            "  python -m app.ml.data.extract_features_from_clips\n"
            "  python -m app.ml.data.ingest_skeleton_dataset --csv ... (public skeleton datasets)\n"
            "or, only to get the app running with a placeholder model:  python -m app.ml.train_model --synthetic"
        )
    df = pd.read_csv(DATA_PATH)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(
            f"{DATA_PATH.name} does not match the current feature schema (v{FEATURE_SCHEMA_VERSION}); "
            f"missing columns: {missing}. Rebuild it with the extraction/ingestion scripts."
        )
    bad = sorted(set(df["activity_label"]) - set(VALID_LABELS))
    if bad:
        raise SystemExit(f"Unknown activity labels in CSV: {bad}")
    return df, "real"


# ------------------------------------------------------------------ helpers

def _fit(X: np.ndarray, y: np.ndarray, class_weight: Optional[str]):
    scaler = StandardScaler()
    model = RandomForestClassifier(**RF_PARAMS, class_weight=class_weight, random_state=SEED, n_jobs=-1)
    model.fit(scaler.fit_transform(X), y)
    return scaler, model


def _top_confusions(cm: np.ndarray, labels: List[str], k: int = 5) -> List[dict]:
    out = []
    for i, actual in enumerate(labels):
        row_total = cm[i].sum()
        for j, predicted in enumerate(labels):
            if i != j and cm[i, j] > 0:
                out.append({
                    "actual": actual, "predicted": predicted, "count": int(cm[i, j]),
                    "fraction_of_actual": float(cm[i, j] / row_total) if row_total else 0.0,
                })
    return sorted(out, key=lambda d: d["count"], reverse=True)[:k]


def _class_metrics(y_true, y_pred, labels: List[str]) -> dict:
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "n_samples": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(report["macro avg"]["precision"]),
        "recall_macro": float(report["macro avg"]["recall"]),
        "f1_macro": float(report["macro avg"]["f1-score"]),
        "precision_weighted": float(report["weighted avg"]["precision"]),
        "recall_weighted": float(report["weighted avg"]["recall"]),
        "f1_weighted": float(report["weighted avg"]["f1-score"]),
        "per_class": {
            lbl: {
                "precision": float(report[lbl]["precision"]),
                "recall": float(report[lbl]["recall"]),
                "f1_score": float(report[lbl]["f1-score"]),
                "support": int(report[lbl]["support"]),
            }
            for lbl in labels
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": labels,
        "top_confusions": _top_confusions(cm, labels),
    }


def choose_test_subjects(df: pd.DataFrame) -> List[str]:
    """Deterministic held-out subject choice; prefers a split where the test set has all four labels
    and the remaining (train) subjects still cover all four labels."""
    subjects = sorted(df["subject_id"].unique())
    n_test = max(1, int(round(len(subjects) * TEST_SUBJECT_FRACTION)))
    label_sets = {s: set(df.loc[df["subject_id"] == s, "activity_label"]) for s in subjects}
    first = None
    for seed in range(SEED, SEED + 300):
        rng = np.random.default_rng(seed)
        test = sorted(rng.choice(subjects, size=n_test, replace=False).tolist())
        train = [s for s in subjects if s not in test]
        first = first or test
        test_labels = set().union(*(label_sets[s] for s in test))
        train_labels = set().union(*(label_sets[s] for s in train))
        if test_labels >= set(VALID_LABELS) and train_labels >= set(VALID_LABELS):
            return test
    logger.warning("Could not find a held-out subject set covering all four activities; using the first draw.")
    return first


def loso_predictions(df: pd.DataFrame, class_weight: Optional[str]):
    """Leave-one-subject-out. Returns (y_true, y_pred, proba, classes, per_subject_accuracy)."""
    subjects = sorted(df["subject_id"].unique())
    X = df[FEATURE_NAMES].values
    y = df["activity_label"].values
    classes = sorted(set(y))
    y_pred = np.empty(len(df), dtype=object)
    proba = np.zeros((len(df), len(classes)))
    per_subject = {}
    for subj in subjects:
        test_mask = (df["subject_id"] == subj).values
        scaler, model = _fit(X[~test_mask], y[~test_mask], class_weight)
        p = model.predict_proba(scaler.transform(X[test_mask]))
        aligned = np.zeros((p.shape[0], len(classes)))  # a fold may lack a class entirely
        for k, c in enumerate(model.classes_):
            aligned[:, classes.index(c)] = p[:, k]
        proba[test_mask] = aligned
        y_pred[test_mask] = np.array(classes)[aligned.argmax(axis=1)]
        per_subject[subj] = float(accuracy_score(y[test_mask], y_pred[test_mask]))
    return y, y_pred, proba, classes, per_subject


def smoothed_eval(df_eval: pd.DataFrame, proba: np.ndarray, classes: List[str]) -> dict:
    """Offline replay of the live ActivitySmoother over held-out clips, in time order."""
    correct = total = unknown = raw_correct = 0
    ts = df_eval["timestamp_sec"].values
    truth_all = df_eval["activity_label"].values
    for _, idx in df_eval.groupby("source_clip").indices.items():
        idx = idx[np.argsort(ts[idx])]
        smoother = ActivitySmoother(
            settings.ACTIVITY_SMOOTHING_WINDOW_SEC, settings.ACTIVITY_CONFIDENCE_MIN, settings.ACTIVITY_SWITCH_MARGIN
        )
        for i in idx:
            total += 1
            raw_correct += classes[int(np.argmax(proba[i]))] == truth_all[i]
            res = smoother.update(dict(zip(classes, proba[i])), float(ts[i]))
            if res is None:
                unknown += 1  # counted as incorrect - never silently replaced by the raw label
            else:
                correct += res[0] == truth_all[i]
    return {
        "window_sec": settings.ACTIVITY_SMOOTHING_WINDOW_SEC,
        "raw_frame_accuracy": raw_correct / total if total else None,
        "smoothed_accuracy": correct / total if total else None,
        "fraction_no_decision": unknown / total if total else None,
    }


# ------------------------------------------------------------------ main flow

def train(synthetic: bool = False) -> dict:
    df, data_source = load_training_data(synthetic)
    labels_all = sorted(df["activity_label"].unique())
    X = df[FEATURE_NAMES].values
    y = df["activity_label"].values

    counts = df["activity_label"].value_counts()
    imbalance = float(counts.max() / counts.min())
    class_weight = "balanced" if imbalance > 1.5 else None
    limitations: List[str] = []
    if set(labels_all) != set(VALID_LABELS):
        limitations.append(f"Activities missing from the data: {sorted(set(VALID_LABELS) - set(labels_all))}.")

    evaluation: Dict = {}
    n_subjects = 0
    train_subjects: List[str] = []
    validation_subjects: List[str] = []
    test_subjects: List[str] = []
    smoothing = None
    per_fold = None

    if data_source == "synthetic":
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
        scaler, model = _fit(Xtr, ytr, class_weight)
        headline = _class_metrics(yte, model.predict(scaler.transform(Xte)), labels_all)
        method, evidence = "random_stratified", "none_synthetic"
        n_train, n_test = len(Xtr), len(Xte)
        limitations.append("Synthetic placeholder data: no real people, no subject-wise evaluation possible; "
                           "the metrics are meaningless for real-world accuracy.")
    else:
        n_subjects = int(df["subject_id"].nunique())
        evaluation["subjects_per_label"] = {
            l: int(df.loc[df.activity_label == l, "subject_id"].nunique()) for l in labels_all
        }
        for lbl, n in evaluation["subjects_per_label"].items():
            if n < 3:
                limitations.append(f"Only {n} subject(s) contribute '{lbl}' data - too few to trust that class.")
        if imbalance > 1.5:
            limitations.append(f"Class imbalance {imbalance:.1f}x (largest/smallest); class_weight='balanced' was used.")

        if n_subjects >= MIN_SUBJECTS_FOR_TEST_SET:
            test_subjects = choose_test_subjects(df)
            pool = df[~df["subject_id"].isin(test_subjects)].reset_index(drop=True)
            train_subjects = validation_subjects = sorted(pool["subject_id"].unique())

            yv, pv, probav, cls_v, per_fold = loso_predictions(pool, class_weight)
            validation = _class_metrics(yv, pv, labels_all)
            validation["per_held_out_subject_accuracy"] = per_fold
            validation["smoothing_offline"] = smoothed_eval(pool, probav, cls_v)
            evaluation["validation_loso"] = validation

            scaler, model = _fit(pool[FEATURE_NAMES].values, pool["activity_label"].values, class_weight)
            test_df = df[df["subject_id"].isin(test_subjects)].reset_index(drop=True)
            probat = model.predict_proba(scaler.transform(test_df[FEATURE_NAMES].values))
            y_pred = np.array(model.classes_)[probat.argmax(axis=1)]
            headline = _class_metrics(test_df["activity_label"].values, y_pred, labels_all)
            smoothing = smoothed_eval(test_df, probat, list(model.classes_))
            method, evidence = "subject_wise_holdout", "subject_wise_holdout"
            n_train, n_test = len(pool), len(test_df)
            if n_subjects < 10:
                limitations.append(
                    f"Only {n_subjects} subjects: the held-out test set has {len(test_subjects)} person(s), so the "
                    "test metrics have wide uncertainty. Treat them as a rough indication, not a guarantee."
                )
        elif n_subjects >= 2:
            yv, pv, probav, cls_v, per_fold = loso_predictions(df, class_weight)
            headline = _class_metrics(yv, pv, labels_all)
            smoothing = smoothed_eval(df, probav, cls_v)
            train_subjects = validation_subjects = sorted(df["subject_id"].unique())
            method, evidence = "subject_wise_loso_limited", "subject_wise_cv_limited"
            n_test = len(df)                       # every sample is evaluated once, by a model that never saw its subject
            n_train = int(len(df) * (n_subjects - 1) / n_subjects)  # approx. per-fold training size
            limitations.append(
                f"Only {n_subjects} subjects: leave-one-subject-out only, no separate untouched test set. "
                "Do not treat this as proof of generalization to new people."
            )
        else:
            Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
            scaler, model = _fit(Xtr, ytr, class_weight)
            headline = _class_metrics(yte, model.predict(scaler.transform(Xte)), labels_all)
            method, evidence = "random_stratified", "none_random_split"
            n_train, n_test = len(Xtr), len(Xte)
            limitations.append("Single subject: random frame split. Frames of one person are near-duplicates, so this "
                               "accuracy does NOT measure generalization to unseen people.")

        if df["source_dataset"].nunique() == 1:
            limitations.append("All data come from one source/environment; camera, lighting and background "
                               "diversity is limited.")

    # Deployed model: fit on ALL data (evaluation above used models that excluded the evaluated subjects).
    scaler_all, model_all = _fit(X, y, class_weight)
    settings.models_path.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_all, settings.models_path / MODEL_FILENAME)
    joblib.dump(scaler_all, settings.models_path / SCALER_FILENAME)

    dataset_info = {}
    if data_source == "real" and DATASET_INFO_PATH.exists():
        try:
            dataset_info = json.loads(DATASET_INFO_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_source": data_source,
        "split_method": method,
        "generalization_evidence": evidence,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "held_out_subjects": test_subjects or None,
        "n_subjects": n_subjects,
        "n_clips": int(df["source_clip"].nunique()) if data_source == "real" else 0,
        "train_subjects": train_subjects,
        "validation_subjects": validation_subjects,
        "test_subjects": test_subjects,
        "n_train_samples": int(n_train),
        "n_test_samples": int(n_test),
        "n_total_samples": int(len(df)),
        "samples_per_label": {k: int(v) for k, v in counts.items()},
        "labels": labels_all,
        **{k: headline[k] for k in [
            "accuracy", "precision_macro", "recall_macro", "f1_macro",
            "precision_weighted", "recall_weighted", "f1_weighted",
            "per_class", "confusion_matrix", "confusion_matrix_labels", "top_confusions"]},
        "evaluation": {**evaluation, "smoothing_offline": smoothing, "per_held_out_subject_accuracy": per_fold},
        "limitations": limitations,
        "model_type": "RandomForestClassifier",
        "model_params": {**RF_PARAMS, "class_weight": class_weight},
        "feature_names": FEATURE_NAMES,
        "dataset_info": dataset_info,
    }
    with open(settings.models_path / METRICS_FILENAME, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    _print_report(metrics)
    return metrics


def _print_report(m: dict) -> None:
    bar = "=" * 70
    print(f"\n{bar}\nEVALUATION METHOD: {m['split_method']}   (evidence: {m['generalization_evidence']})\n{bar}")
    print(f"Data source: {m['data_source']} | subjects: {m['n_subjects']} | clips: {m['n_clips']} | "
          f"samples: {m['n_total_samples']}")
    print(f"Samples per activity: {m['samples_per_label']}")
    print(f"Train subjects: {m['train_subjects']}\nValidation (LOSO) subjects: {m['validation_subjects']}\n"
          f"Test subjects: {m['test_subjects']}")
    print(f"Train samples: {m['n_train_samples']} | Eval samples: {m['n_test_samples']}")
    print(f"\nAccuracy {m['accuracy']:.4f} | macro P {m['precision_macro']:.4f} R {m['recall_macro']:.4f} "
          f"F1 {m['f1_macro']:.4f}")
    for lbl, c in m["per_class"].items():
        print(f"  {lbl:9s} P {c['precision']:.3f}  R {c['recall']:.3f}  F1 {c['f1_score']:.3f}  n={c['support']}")
    print("Confusion matrix (rows=actual, cols=predicted)", m["confusion_matrix_labels"])
    for row in m["confusion_matrix"]:
        print("  ", row)
    print("Most common confusions:", [(c["actual"], c["predicted"], c["count"]) for c in m["top_confusions"]] or "none")
    smoothing = m["evaluation"].get("smoothing_offline")
    if smoothing:
        print(f"Offline smoothing replay: raw {smoothing['raw_frame_accuracy']:.4f} -> "
              f"smoothed {smoothing['smoothed_accuracy']:.4f} (no decision: {smoothing['fraction_no_decision']:.3f})")
    print("\nLimitations:")
    for lim in m["limitations"] or ["(none recorded)"]:
        print(" -", lim)
    if m["generalization_evidence"] != "subject_wise_holdout":
        print("\n*** These numbers are NOT evidence of accuracy on unseen people. ***")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--synthetic", action="store_true", help="Train a placeholder model on synthetic data")
    args = parser.parse_args()
    train(synthetic=args.synthetic)


if __name__ == "__main__":
    main()
