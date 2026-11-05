import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.config import settings
from app.models.user import User
from app.schemas.ml_metrics import MLMetricsOut

router = APIRouter(prefix="/api/v1/ml", tags=["ML Metrics"])


@router.get("/metrics", response_model=MLMetricsOut)
def get_ml_metrics(_user: User = Depends(get_current_user)):
    """
    Returns the ACTUAL measured evaluation results from the last time
    train_model.py was run (models_store/metrics.json) — never
    hand-entered or hardcoded numbers. 404s if the model hasn't been
    trained yet.
    """
    metrics_path = settings.models_path / "metrics.json"
    if not metrics_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No trained-model metrics found yet. Run `python -m app.ml.train_model` first.",
        )

    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="metrics.json is corrupted")

    return data
