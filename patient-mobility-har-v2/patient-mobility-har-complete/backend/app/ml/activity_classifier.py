"""
Loads the trained Random Forest model (and its accompanying scaler) at
startup and exposes a single predict(feature_vector) -> (label, confidence)
interface. A future LSTM/CNN model can implement this same interface
without any other module needing to change.
"""

import json
from typing import Dict, Optional, Tuple

import joblib
import numpy as np

from app.config import settings
from app.ml.feature_extractor import FEATURE_NAMES
from app.utils.logger import get_logger

logger = get_logger(__name__)

MODEL_FILENAME = "activity_rf.pkl"
SCALER_FILENAME = "activity_scaler.pkl"
LABELS = ["walking", "standing", "sitting", "lying"]


class ActivityClassifier:
    def __init__(self):
        self._model = None
        self._scaler = None
        self._load()

    def _load(self) -> None:
        model_path = settings.models_path / MODEL_FILENAME
        scaler_path = settings.models_path / SCALER_FILENAME

        if not model_path.exists():
            logger.warning(
                "Trained model not found at %s. Run app/ml/train_model.py before starting monitoring.",
                model_path,
            )
            return

        model = joblib.load(model_path)

        # Refuse a model trained on a different feature layout instead of silently
        # producing garbage predictions from mismatched columns.
        n_expected = len(FEATURE_NAMES)
        n_model = getattr(model, "n_features_in_", n_expected)
        metrics = {}
        metrics_path = settings.models_path / "metrics.json"
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metrics = {}
        saved_names = metrics.get("feature_names")
        if n_model != n_expected or (saved_names is not None and saved_names != FEATURE_NAMES):
            logger.error(
                "Model at %s was trained on a different feature schema (%s features) than the current "
                "FeatureExtractor (%s). Not loading it. Retrain: python -m app.ml.train_model",
                model_path, n_model, n_expected,
            )
            return

        self._model = model
        if scaler_path.exists():
            self._scaler = joblib.load(scaler_path)
        logger.info("Activity classifier loaded from %s", model_path)
        if metrics.get("data_source") == "synthetic":
            logger.warning(
                "The loaded activity model was trained on SYNTHETIC data only. Its metrics say nothing about "
                "real-world accuracy. Train on real multi-subject data (see docs/activity_recognition.md)."
            )

    def is_ready(self) -> bool:
        return self._model is not None

    def predict_proba(self, feature_vector: np.ndarray) -> Optional[Dict[str, float]]:
        """Per-class probabilities for one frame (input to ActivitySmoother)."""
        if not self.is_ready():
            return None

        vector = feature_vector.reshape(1, -1)
        if self._scaler is not None:
            vector = self._scaler.transform(vector)

        probabilities = self._model.predict_proba(vector)[0]
        return {str(cls): float(p) for cls, p in zip(self._model.classes_, probabilities)}

    def predict(self, feature_vector: np.ndarray) -> Optional[Tuple[str, float]]:
        """Raw single-frame prediction (no temporal smoothing)."""
        probabilities = self.predict_proba(feature_vector)
        if probabilities is None:
            return None
        label = max(probabilities, key=probabilities.get)
        return label, probabilities[label]

    def reload(self) -> None:
        """Allows hot-reloading the model after retraining without restarting the server."""
        self._load()


# Module-level singleton, loaded once at import time.
activity_classifier = ActivityClassifier()
