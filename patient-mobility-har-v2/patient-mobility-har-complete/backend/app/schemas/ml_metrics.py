from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class PerClassMetrics(BaseModel):
    precision: float
    recall: float
    f1_score: float
    support: int


class MLMetricsOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    trained_at: Optional[str] = None
    data_source: Optional[str] = None
    split_method: Optional[str] = None
    held_out_subjects: Optional[List[str]] = None
    n_train_samples: Optional[int] = None
    n_test_samples: Optional[int] = None
    n_total_samples: Optional[int] = None
    labels: Optional[List[str]] = None
    accuracy: Optional[float] = None
    precision_macro: Optional[float] = None
    recall_macro: Optional[float] = None
    f1_macro: Optional[float] = None
    precision_weighted: Optional[float] = None
    recall_weighted: Optional[float] = None
    f1_weighted: Optional[float] = None
    per_class: Optional[Dict[str, PerClassMetrics]] = None
    confusion_matrix: Optional[List[List[int]]] = None
    confusion_matrix_labels: Optional[List[str]] = None
    model_type: Optional[str] = None
    model_params: Optional[Dict[str, Any]] = None
    feature_names: Optional[List[str]] = None
    dataset_info: Optional[Dict[str, Any]] = None
    # Added with the subject-wise evaluation (all optional; older metrics.json files still validate).
    generalization_evidence: Optional[str] = None
    feature_schema_version: Optional[int] = None
    n_subjects: Optional[int] = None
    n_clips: Optional[int] = None
    train_subjects: Optional[List[str]] = None
    validation_subjects: Optional[List[str]] = None
    test_subjects: Optional[List[str]] = None
    samples_per_label: Optional[Dict[str, int]] = None
    top_confusions: Optional[List[Dict[str, Any]]] = None
    evaluation: Optional[Dict[str, Any]] = None
    limitations: Optional[List[str]] = None
