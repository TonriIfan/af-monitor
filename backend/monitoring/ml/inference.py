from __future__ import annotations

import pickle
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings

from .features import extract_ppg_features


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _quantize(value: float) -> Decimal:
    return Decimal(str(round(value, 4))).quantize(Decimal('0.01'))


def _feature_vector(features: dict[str, float], feature_names: list[str] | None = None) -> list[float]:
    ordered_names = feature_names or list(features.keys())
    return [float(features.get(name, 0.0)) for name in ordered_names]


def _heuristic_probability(features: dict[str, float], quality_score: float) -> float:
    irregularity = (
        min(features.get('ibi_cv', 0.0) / 0.25, 1.0) * 0.35
        + min(features.get('rmssd', 0.0) / 0.18, 1.0) * 0.30
        + min(features.get('pnn50', 0.0) / 0.60, 1.0) * 0.20
        + (1 - min(abs(features.get('autocorr_lag1', 0.0)), 1.0)) * 0.15
    )
    return _clamp((irregularity * 0.8) + ((1 - quality_score) * 0.2))


def _quality_score(features: dict[str, float], duration_seconds: float) -> float:
    expected_peaks = duration_seconds / 0.85 if duration_seconds else 0.0
    peak_ratio = min(features.get('peak_count', 0.0) / expected_peaks, 1.0) if expected_peaks else 0.0
    range_score = min(features.get('signal_range', 0.0) / 4.5, 1.0)
    flat_penalty = min(features.get('flat_ratio', 0.0), 1.0)
    return _clamp((peak_ratio * 0.45) + (range_score * 0.35) + ((1 - flat_penalty) * 0.20))


def _load_model_artifact(model_path: Path) -> dict[str, Any] | None:
    if not model_path.exists():
        return None
    try:
        with model_path.open('rb') as handle:
            return pickle.load(handle)
    except Exception:
        return None


def analyze_ppg_samples(samples: list[float], sample_rate_hz: float) -> dict[str, Any]:
    features, diagnostics = extract_ppg_features(samples, sample_rate_hz)
    duration_seconds = features['duration_seconds']
    quality_score = _quality_score(features, duration_seconds)
    quality_pass = quality_score >= 0.45 and features.get('peak_count', 0.0) >= max(duration_seconds * 0.5, 4)

    artifact = _load_model_artifact(Path(settings.DEFAULT_PPG_AF_MODEL_PATH))
    probability = 0.0
    model_version = 'heuristic-v1'
    model_source = 'heuristic'

    if quality_pass and artifact is not None:
        estimator = artifact.get('estimator')
        feature_names = artifact.get('feature_names')
        decision_threshold = float(artifact.get('decision_threshold', 0.5))
        vector = _feature_vector(features, feature_names)
        try:
            if hasattr(estimator, 'predict_proba'):
                probability = float(estimator.predict_proba([vector])[0][1])
            else:
                decision = float(estimator.decision_function([vector])[0])
                probability = 1.0 / (1.0 + (2.718281828 ** (-decision)))
            model_version = artifact.get('model_version', 'ppg-af-model')
            model_source = 'trained'
        except Exception:
            probability = _heuristic_probability(features, quality_score)
            decision_threshold = 0.5
    else:
        probability = _heuristic_probability(features, quality_score) if quality_pass else 0.0
        decision_threshold = 0.5

    af_label = quality_pass and probability >= decision_threshold
    return {
        'quality_pass': quality_pass,
        'quality_score': _quantize(quality_score),
        'af_probability': _quantize(probability),
        'af_label': af_label,
        'decision_threshold': _quantize(decision_threshold),
        'model_version': model_version,
        'model_source': model_source,
        'features': features,
        'diagnostics': {
            'peak_count': len(diagnostics['peaks']),
            'ibi_count': len(diagnostics['ibis']),
        },
    }
