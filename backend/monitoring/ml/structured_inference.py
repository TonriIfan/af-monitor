from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from django.conf import settings

from .features import extract_structured_features_from_heart_rate_series


def _load_model_artifact(model_path: Path) -> dict[str, Any] | None:
    if not model_path.exists():
        return None
    try:
        with model_path.open('rb') as handle:
            return pickle.load(handle)
    except Exception:
        return None


def _feature_vector(features: dict[str, float], feature_names: list[str]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in feature_names]


def build_structured_features_from_measurements(measurements: list[Any], duration_seconds: float) -> dict[str, float]:
    heart_rates = [float(item.heart_rate) for item in measurements if getattr(item, 'heart_rate', None) is not None]
    if len(heart_rates) < 2:
        return {}
    flat_ratio = 0.0
    if len(heart_rates) > 1:
        flat_ratio = sum(
            1 for index in range(1, len(heart_rates)) if abs(heart_rates[index] - heart_rates[index - 1]) < 1.0
        ) / (len(heart_rates) - 1)
    return extract_structured_features_from_heart_rate_series(
        heart_rates,
        duration_seconds,
        flat_ratio=flat_ratio,
    )


def analyze_structured_measurement_window(measurements: list[Any], duration_seconds: float) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'enabled': True,
        'available': False,
        'model_name': '',
        'model_version': '',
        'probability': 0.0,
        'decision_threshold': 0.0,
        'label': False,
        'feature_source': 'measurement_window',
        'skip_reason': '',
        'features': {},
    }
    if len(measurements) < settings.STRUCTURED_AF_MIN_HISTORY_SAMPLES:
        payload['skip_reason'] = 'insufficient_history'
        return payload

    features = build_structured_features_from_measurements(measurements, duration_seconds)
    if not features:
        payload['skip_reason'] = 'insufficient_valid_values'
        return payload

    payload['features'] = features
    artifact = _load_model_artifact(Path(settings.DEFAULT_STRUCTURED_AF_MODEL_PATH))
    if artifact is None:
        payload['skip_reason'] = 'model_not_found'
        return payload

    estimator = artifact.get('estimator')
    feature_names = artifact.get('feature_names')
    if not estimator or not feature_names:
        payload['skip_reason'] = 'model_invalid'
        return payload

    vector = _feature_vector(features, feature_names)
    try:
        if hasattr(estimator, 'predict_proba'):
            probability = float(estimator.predict_proba([vector])[0][1])
        else:
            decision = float(estimator.decision_function([vector])[0])
            probability = 1.0 / (1.0 + (2.718281828 ** (-decision)))
    except Exception:
        payload['skip_reason'] = 'prediction_failed'
        return payload

    threshold = float(artifact.get('decision_threshold', 0.5))
    payload.update(
        {
            'available': True,
            'model_name': artifact.get('model_name', 'structured-af-model'),
            'model_version': artifact.get('model_version', ''),
            'probability': round(probability, 4),
            'decision_threshold': round(threshold, 4),
            'label': probability >= threshold,
            'skip_reason': '',
        }
    )
    return payload
