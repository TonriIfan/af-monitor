from __future__ import annotations

from math import sqrt
from statistics import fmean, pstdev


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def normalize_samples(samples: list[float]) -> list[float]:
    raw = [float(item) for item in samples]
    if not raw:
        return []
    mean_value = fmean(raw)
    std_value = pstdev(raw) or 1.0
    return [(item - mean_value) / std_value for item in raw]


def detect_peaks(samples: list[float], sample_rate_hz: float) -> list[int]:
    if len(samples) < 3:
        return []
    threshold = _percentile(samples, 0.65)
    min_distance = max(1, int(sample_rate_hz * 0.35))
    peaks: list[int] = []
    last_peak = -min_distance
    for index in range(1, len(samples) - 1):
        current = samples[index]
        if current < threshold:
            continue
        if current < samples[index - 1] or current <= samples[index + 1]:
            continue
        if index - last_peak < min_distance:
            continue
        peaks.append(index)
        last_peak = index
    return peaks


def _safe_std(values: list[float]) -> float:
    return pstdev(values) if len(values) > 1 else 0.0


def _safe_mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def _derive_ibi_from_heart_rate(heart_rates: list[float]) -> list[float]:
    return [60.0 / value for value in heart_rates if value > 0]


def _derive_hr_from_ibi(ibis: list[float]) -> list[float]:
    return [60.0 / value for value in ibis if value > 0]


def _rmssd(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    diffs = [values[index] - values[index - 1] for index in range(1, len(values))]
    return sqrt(fmean([item * item for item in diffs])) if diffs else 0.0


def _pnn50(ibis: list[float]) -> float:
    if len(ibis) < 2:
        return 0.0
    diffs = [abs(ibis[index] - ibis[index - 1]) for index in range(1, len(ibis))]
    return sum(1 for item in diffs if item > 0.05) / len(diffs) if diffs else 0.0


def _irregular_ratio(ibis: list[float]) -> float:
    if len(ibis) < 2:
        return 0.0
    diffs = [abs(ibis[index] - ibis[index - 1]) for index in range(1, len(ibis))]
    return sum(1 for item in diffs if item > 0.08) / len(diffs) if diffs else 0.0


def _successive_change_ratio(values: list[float], threshold: float) -> float:
    if len(values) < 2:
        return 0.0
    diffs = [abs(values[index] - values[index - 1]) for index in range(1, len(values))]
    return sum(1 for item in diffs if item >= threshold) / len(diffs) if diffs else 0.0


def _diff_stats(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return 0.0, 0.0
    diffs = [abs(values[index] - values[index - 1]) for index in range(1, len(values))]
    return _safe_mean(diffs), _safe_std(diffs)


def _flat_ratio_from_samples(samples: list[float], tolerance: float = 0.01) -> float:
    if len(samples) < 2:
        return 1.0
    normalized_diffs = [abs(samples[index] - samples[index - 1]) < tolerance for index in range(1, len(samples))]
    return sum(1 for item in normalized_diffs if item) / len(normalized_diffs) if normalized_diffs else 1.0


def extract_structured_features_from_heart_rate_series(
    heart_rates: list[float],
    duration_seconds: float,
    flat_ratio: float = 0.0,
) -> dict[str, float]:
    clean_heart_rates = [float(value) for value in heart_rates if value and value > 0]
    ibis = _derive_ibi_from_heart_rate(clean_heart_rates)

    hr_mean = _safe_mean(clean_heart_rates)
    hr_std = _safe_std(clean_heart_rates)
    ibi_mean = _safe_mean(ibis)
    ibi_std = _safe_std(ibis)
    ibi_cv = ibi_std / ibi_mean if ibi_mean else 0.0
    hr_min = min(clean_heart_rates) if clean_heart_rates else 0.0
    hr_max = max(clean_heart_rates) if clean_heart_rates else 0.0
    hr_range = hr_max - hr_min
    hr_diff_mean, hr_diff_std = _diff_stats(clean_heart_rates)
    estimated_peak_count = (hr_mean * duration_seconds / 60.0) if hr_mean and duration_seconds else float(len(clean_heart_rates))

    return {
        'duration_seconds': round(duration_seconds, 4),
        'hr_mean': round(hr_mean, 4),
        'hr_min': round(hr_min, 4),
        'hr_max': round(hr_max, 4),
        'hr_std': round(hr_std, 4),
        'hr_range': round(hr_range, 4),
        'hr_range_ratio': round(hr_range / hr_mean, 4) if hr_mean else 0.0,
        'hr_variation_index': round(hr_std / hr_mean, 4) if hr_mean else 0.0,
        'hr_diff_mean': round(hr_diff_mean, 4),
        'hr_diff_std': round(hr_diff_std, 4),
        'ibi_mean': round(ibi_mean, 4),
        'ibi_std': round(ibi_std, 4),
        'ibi_cv': round(ibi_cv, 4),
        'rmssd': round(_rmssd(ibis), 4),
        'pnn50': round(_pnn50(ibis), 4),
        'tachycardia_ratio': round(
            sum(1 for value in clean_heart_rates if value > 110) / len(clean_heart_rates),
            4,
        )
        if clean_heart_rates
        else 0.0,
        'bradycardia_ratio': round(
            sum(1 for value in clean_heart_rates if value < 50) / len(clean_heart_rates),
            4,
        )
        if clean_heart_rates
        else 0.0,
        'irregular_ratio': round(_irregular_ratio(ibis), 4),
        'instability_index': round(ibi_cv + _pnn50(ibis) + _irregular_ratio(ibis), 4),
        'successive_change_ratio': round(_successive_change_ratio(clean_heart_rates, 8.0), 4),
        'extreme_hr_ratio': round(
            sum(1 for value in clean_heart_rates if value > 120 or value < 45) / len(clean_heart_rates),
            4,
        )
        if clean_heart_rates
        else 0.0,
        'valid_sample_count': float(len(clean_heart_rates)),
        'peak_count': round(estimated_peak_count, 4),
        'peak_density': round(estimated_peak_count / duration_seconds, 4) if duration_seconds else 0.0,
        'flat_ratio': round(flat_ratio, 4),
    }


def extract_structured_features_from_rr_intervals(
    ibis: list[float],
    duration_seconds: float,
    flat_ratio: float = 0.0,
) -> dict[str, float]:
    clean_ibis = [float(value) for value in ibis if value and value > 0]
    heart_rates = _derive_hr_from_ibi(clean_ibis)
    hr_mean = _safe_mean(heart_rates)
    hr_std = _safe_std(heart_rates)
    ibi_mean = _safe_mean(clean_ibis)
    ibi_std = _safe_std(clean_ibis)
    ibi_cv = ibi_std / ibi_mean if ibi_mean else 0.0
    hr_min = min(heart_rates) if heart_rates else 0.0
    hr_max = max(heart_rates) if heart_rates else 0.0
    hr_range = hr_max - hr_min
    hr_diff_mean, hr_diff_std = _diff_stats(heart_rates)
    estimated_peak_count = (hr_mean * duration_seconds / 60.0) if hr_mean and duration_seconds else float(len(clean_ibis))

    return {
        'duration_seconds': round(duration_seconds, 4),
        'hr_mean': round(hr_mean, 4),
        'hr_min': round(hr_min, 4),
        'hr_max': round(hr_max, 4),
        'hr_std': round(hr_std, 4),
        'hr_range': round(hr_range, 4),
        'hr_range_ratio': round(hr_range / hr_mean, 4) if hr_mean else 0.0,
        'hr_variation_index': round(hr_std / hr_mean, 4) if hr_mean else 0.0,
        'hr_diff_mean': round(hr_diff_mean, 4),
        'hr_diff_std': round(hr_diff_std, 4),
        'ibi_mean': round(ibi_mean, 4),
        'ibi_std': round(ibi_std, 4),
        'ibi_cv': round(ibi_cv, 4),
        'rmssd': round(_rmssd(clean_ibis), 4),
        'pnn50': round(_pnn50(clean_ibis), 4),
        'tachycardia_ratio': round(sum(1 for value in heart_rates if value > 110) / len(heart_rates), 4) if heart_rates else 0.0,
        'bradycardia_ratio': round(sum(1 for value in heart_rates if value < 50) / len(heart_rates), 4) if heart_rates else 0.0,
        'irregular_ratio': round(_irregular_ratio(clean_ibis), 4),
        'instability_index': round(ibi_cv + _pnn50(clean_ibis) + _irregular_ratio(clean_ibis), 4),
        'successive_change_ratio': round(_successive_change_ratio(heart_rates, 8.0), 4),
        'extreme_hr_ratio': round(sum(1 for value in heart_rates if value > 120 or value < 45) / len(heart_rates), 4) if heart_rates else 0.0,
        'valid_sample_count': float(len(heart_rates)),
        'peak_count': round(estimated_peak_count, 4),
        'peak_density': round(estimated_peak_count / duration_seconds, 4) if duration_seconds else 0.0,
        'flat_ratio': round(flat_ratio, 4),
    }


def _autocorr_lag1(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = fmean(values)
    centered = [value - mean_value for value in values]
    numerator = sum(centered[index] * centered[index + 1] for index in range(len(centered) - 1))
    denominator = sum(value * value for value in centered)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def extract_ppg_features(samples: list[float], sample_rate_hz: float) -> tuple[dict[str, float], dict[str, object]]:
    normalized = normalize_samples(samples)
    duration_seconds = len(normalized) / sample_rate_hz if sample_rate_hz else 0.0
    peaks = detect_peaks(normalized, sample_rate_hz)
    ibis = [
        (peaks[index] - peaks[index - 1]) / sample_rate_hz
        for index in range(1, len(peaks))
        if sample_rate_hz
    ]
    diffs = [ibis[index] - ibis[index - 1] for index in range(1, len(ibis))]
    abs_diffs = [abs(item) for item in diffs]
    flat_ratio = _flat_ratio_from_samples(normalized)

    ibi_mean = fmean(ibis) if ibis else 0.0
    ibi_std = _safe_std(ibis)
    rmssd = sqrt(fmean([item * item for item in diffs])) if diffs else 0.0
    pnn50 = sum(1 for item in abs_diffs if item > 0.05) / len(abs_diffs) if abs_diffs else 0.0
    signal_std = _safe_std(normalized)
    signal_range = (max(normalized) - min(normalized)) if normalized else 0.0
    peak_density = len(peaks) / duration_seconds if duration_seconds else 0.0
    ibi_cv = ibi_std / ibi_mean if ibi_mean else 0.0
    amplitude_p90 = _percentile([abs(item) for item in normalized], 0.90) if normalized else 0.0

    features = {
        'duration_seconds': round(duration_seconds, 4),
        'peak_count': float(len(peaks)),
        'peak_density': round(peak_density, 4),
        'ibi_mean': round(ibi_mean, 4),
        'ibi_std': round(ibi_std, 4),
        'ibi_cv': round(ibi_cv, 4),
        'rmssd': round(rmssd, 4),
        'pnn50': round(pnn50, 4),
        'signal_std': round(signal_std, 4),
        'signal_range': round(signal_range, 4),
        'flat_ratio': round(flat_ratio, 4),
        'autocorr_lag1': round(_autocorr_lag1(normalized), 4),
        'amplitude_p90': round(amplitude_p90, 4),
    }
    diagnostics = {
        'peaks': peaks,
        'ibis': ibis,
        'normalized_samples': normalized,
    }
    return features, diagnostics


def extract_structured_features_from_ppg(samples: list[float], sample_rate_hz: float) -> tuple[dict[str, float], dict[str, object]]:
    normalized = normalize_samples(samples)
    duration_seconds = len(normalized) / sample_rate_hz if sample_rate_hz else 0.0
    peaks = detect_peaks(normalized, sample_rate_hz)
    ibis = [
        (peaks[index] - peaks[index - 1]) / sample_rate_hz
        for index in range(1, len(peaks))
        if sample_rate_hz
    ]
    heart_rates = _derive_hr_from_ibi(ibis)
    flat_ratio = _flat_ratio_from_samples(normalized)
    features = extract_structured_features_from_heart_rate_series(heart_rates, duration_seconds, flat_ratio=flat_ratio)
    diagnostics = {
        'peaks': peaks,
        'ibis': ibis,
        'normalized_samples': normalized,
        'heart_rates': heart_rates,
    }
    return features, diagnostics
