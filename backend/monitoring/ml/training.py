from __future__ import annotations

import csv
import json
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from django.conf import settings

from .features import extract_ppg_features


@dataclass
class PreparedDataset:
    feature_names: list[str]
    rows: list[list[float]]
    labels: list[int]
    groups: list[str]
    patients: list[str]
    records: list[str]


@dataclass
class DatasetSplit:
    x_train: list[list[float]]
    x_test: list[list[float]]
    y_train: list[int]
    y_test: list[int]
    train_groups: list[str]
    test_groups: list[str]
    split_strategy: str


def _import_sklearn():
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            average_precision_score,
            balanced_accuracy_score,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, train_test_split
    except ImportError as exc:
        raise RuntimeError('缺少 scikit-learn 依赖，请先安装 backend/requirements.txt。') from exc
    return {
        'average_precision_score': average_precision_score,
        'balanced_accuracy_score': balanced_accuracy_score,
        'confusion_matrix': confusion_matrix,
        'HistGradientBoostingClassifier': HistGradientBoostingClassifier,
        'LogisticRegression': LogisticRegression,
        'f1_score': f1_score,
        'precision_score': precision_score,
        'recall_score': recall_score,
        'roc_auc_score': roc_auc_score,
        'GroupShuffleSplit': GroupShuffleSplit,
        'StratifiedGroupKFold': StratifiedGroupKFold,
        'train_test_split': train_test_split,
    }


def _import_lightgbm():
    try:
        from lightgbm import LGBMClassifier
    except ImportError as exc:
        raise RuntimeError('缺少 lightgbm 依赖，请先安装 backend/requirements.txt。') from exc
    return LGBMClassifier


def load_training_rows(csv_path: str | Path) -> PreparedDataset:
    path = Path(csv_path)
    rows: list[list[float]] = []
    labels: list[int] = []
    groups: list[str] = []
    patients: list[str] = []
    records: list[str] = []
    feature_names: list[str] | None = None

    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError('训练集缺少表头。')
        has_raw_samples = 'samples' in reader.fieldnames and 'sample_rate_hz' in reader.fieldnames
        for record in reader:
            label = int(record['label'])
            if has_raw_samples:
                sample_rate_hz = float(record['sample_rate_hz'])
                samples = json.loads(record['samples'])
                features, _ = extract_ppg_features(samples, sample_rate_hz)
                if feature_names is None:
                    feature_names = list(features.keys())
                rows.append([float(features[name]) for name in feature_names])
            else:
                if feature_names is None:
                    feature_names = _structured_feature_names(reader.fieldnames)
                feature_values = _structured_feature_values(record)
                rows.append([float(feature_values.get(name, 0.0)) for name in feature_names])
            labels.append(label)
            groups.append(record.get('record_id') or record.get('group_id') or record.get('patient_id') or str(len(groups)))
            patients.append(record.get('patient_id') or record.get('group_id') or record.get('record_id') or str(len(patients)))
            records.append(record.get('record_id') or record.get('group_id') or record.get('patient_id') or str(len(records)))

    if not rows or feature_names is None:
        raise RuntimeError('训练集为空，无法训练 AF 模型。')
    return PreparedDataset(
        feature_names=feature_names,
        rows=rows,
        labels=labels,
        groups=groups,
        patients=patients,
        records=records,
    )


def _structured_feature_names(fieldnames: list[str]) -> list[str]:
    excluded = {
        'label',
        'group_id',
        'patient_id',
        'record_id',
        'window_start_sec',
        'window_end_sec',
        'sample_rate_hz',
        'af_ratio',
        'ambiguous_ratio',
    }
    names = [name for name in fieldnames if name not in excluded]
    for name in _derived_structured_feature_values({}).keys():
        if name not in names:
            names.append(name)
    return names


def _float_record_value(record: dict[str, str], name: str) -> float:
    try:
        return float(record.get(name) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _derived_structured_feature_values(record: dict[str, str]) -> dict[str, float]:
    hr_mean = _float_record_value(record, 'hr_mean')
    hr_min = _float_record_value(record, 'hr_min')
    hr_max = _float_record_value(record, 'hr_max')
    hr_std = _float_record_value(record, 'hr_std')
    ibi_cv = _float_record_value(record, 'ibi_cv')
    pnn50 = _float_record_value(record, 'pnn50')
    irregular_ratio = _float_record_value(record, 'irregular_ratio')
    tachycardia_ratio = _float_record_value(record, 'tachycardia_ratio')
    bradycardia_ratio = _float_record_value(record, 'bradycardia_ratio')
    peak_count = _float_record_value(record, 'peak_count')
    hr_range = hr_max - hr_min if hr_max or hr_min else 0.0
    return {
        'hr_range': round(hr_range, 4),
        'hr_range_ratio': round(hr_range / hr_mean, 4) if hr_mean else 0.0,
        'hr_variation_index': round(hr_std / hr_mean, 4) if hr_mean else 0.0,
        'hr_diff_mean': 0.0,
        'hr_diff_std': 0.0,
        'successive_change_ratio': 0.0,
        'extreme_hr_ratio': round(tachycardia_ratio + bradycardia_ratio, 4),
        'valid_sample_count': peak_count,
        'instability_index': round(ibi_cv + pnn50 + irregular_ratio, 4),
    }


def _structured_feature_values(record: dict[str, str]) -> dict[str, float]:
    values = {
        name: _float_record_value(record, name)
        for name in record
    }
    values.update({key: value for key, value in _derived_structured_feature_values(record).items() if key not in values})
    return values


def _class_distribution(labels: list[int]) -> dict[str, float | int]:
    positive_count = sum(1 for item in labels if item == 1)
    negative_count = sum(1 for item in labels if item == 0)
    total = len(labels)
    return {
        'total': total,
        'positive': positive_count,
        'negative': negative_count,
        'positive_ratio': round(positive_count / total, 6) if total else 0.0,
    }


def _dataset_summary(dataset: PreparedDataset) -> dict[str, int]:
    return {
        'sample_count': len(dataset.labels),
        'patient_count': len(set(dataset.patients)),
        'group_count': len(set(dataset.groups)),
        'record_count': len(set(dataset.records)),
        'feature_count': len(dataset.feature_names),
    }


def _make_split(dataset: PreparedDataset, train_index, test_index, split_strategy: str) -> DatasetSplit:
    train_indices = list(train_index)
    test_indices = list(test_index)
    return DatasetSplit(
        x_train=[dataset.rows[index] for index in train_indices],
        y_train=[dataset.labels[index] for index in train_indices],
        x_test=[dataset.rows[index] for index in test_indices],
        y_test=[dataset.labels[index] for index in test_indices],
        train_groups=[dataset.groups[index] for index in train_indices],
        test_groups=[dataset.groups[index] for index in test_indices],
        split_strategy=split_strategy,
    )


def _split_has_two_classes(split: DatasetSplit) -> bool:
    return len(set(split.y_train)) >= 2 and len(set(split.y_test)) >= 2


def _split_dataset(dataset: PreparedDataset, sklearn: dict[str, Any]) -> DatasetSplit:
    if len(set(dataset.groups)) > 1 and len(dataset.labels) >= 10:
        group_fold_count = min(5, len(set(dataset.groups)))
        if group_fold_count >= 2:
            splitter = sklearn['StratifiedGroupKFold'](
                n_splits=group_fold_count,
                shuffle=True,
                random_state=42,
            )
            candidates: list[DatasetSplit] = []
            for train_index, test_index in splitter.split(dataset.rows, dataset.labels, dataset.groups):
                split = _make_split(dataset, train_index, test_index, 'stratified-group-kfold')
                if _split_has_two_classes(split):
                    candidates.append(split)
            if candidates:
                target_size = len(dataset.labels) * 0.2
                return min(candidates, key=lambda item: abs(len(item.y_test) - target_size))

        for random_state in range(42, 62):
            splitter = sklearn['GroupShuffleSplit'](n_splits=1, test_size=0.2, random_state=random_state)
            train_index, test_index = next(splitter.split(dataset.rows, dataset.labels, dataset.groups))
            split = _make_split(dataset, train_index, test_index, 'group-shuffle')
            if _split_has_two_classes(split):
                return split

    x_train, x_test, y_train, y_test = sklearn['train_test_split'](
        dataset.rows,
        dataset.labels,
        test_size=0.2,
        random_state=42,
        stratify=dataset.labels,
    )
    return DatasetSplit(
        x_train=x_train,
        x_test=x_test,
        y_train=y_train,
        y_test=y_test,
        train_groups=[],
        test_groups=[],
        split_strategy='stratified-random-fallback',
    )


def _safe_roc_auc(y_test: list[int], y_score: list[float], sklearn: dict[str, Any]) -> float:
    if len(set(y_test)) < 2:
        return 0.0
    return float(sklearn['roc_auc_score'](y_test, y_score))


def _safe_average_precision(y_test: list[int], y_score: list[float], sklearn: dict[str, Any]) -> float:
    if len(set(y_test)) < 2:
        return 0.0
    return float(sklearn['average_precision_score'](y_test, y_score))


def _confusion_metrics(y_test: list[int], y_pred: list[int], sklearn: dict[str, Any]) -> dict[str, Any]:
    matrix = sklearn['confusion_matrix'](y_test, y_pred, labels=[0, 1])
    tn, fp, fn, tp = [int(value) for value in matrix.ravel()]
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return {
        'confusion_matrix': {
            'tn': tn,
            'fp': fp,
            'fn': fn,
            'tp': tp,
        },
        'specificity': float(specificity),
        'balanced_accuracy': float(sklearn['balanced_accuracy_score'](y_test, y_pred)),
    }


def _predict_at_threshold(y_score: list[float], threshold: float) -> list[int]:
    return [1 if float(score) >= threshold else 0 for score in y_score]


def _candidate_thresholds(y_score: list[float]) -> list[float]:
    grid = {round(item, 2) for item in np.arange(0.05, 0.96, 0.05)}
    if not y_score:
        return sorted(grid)
    score_array = np.array([float(score) for score in y_score if 0.0 <= float(score) <= 1.0])
    if score_array.size == 0:
        return sorted(grid)
    percentile_based = {
        round(float(np.quantile(score_array, item)), 4)
        for item in np.arange(0.01, 1.00, 0.01)
    }
    return sorted(grid | percentile_based)


def _threshold_objective(metrics: dict[str, float]) -> tuple[float, float, float, float]:
    # 优先保证少数类 F1，其次保留召回率与特异度，最后倾向更高精度。
    return (
        metrics['f1'],
        metrics['recall'],
        metrics['specificity'],
        metrics['precision'],
    )


def _metric_values(y_test: list[int], y_pred: list[int], y_score: list[float], sklearn: dict[str, Any]) -> dict[str, float]:
    metrics = {
        'auroc': _safe_roc_auc(y_test, y_score, sklearn),
        'pr_auc': _safe_average_precision(y_test, y_score, sklearn),
        'f1': float(sklearn['f1_score'](y_test, y_pred, zero_division=0)),
        'precision': float(sklearn['precision_score'](y_test, y_pred, zero_division=0)),
        'recall': float(sklearn['recall_score'](y_test, y_pred, zero_division=0)),
    }
    metrics.update(_confusion_metrics(y_test, y_pred, sklearn))
    return metrics


def _evaluate_thresholds(y_test: list[int], y_score: list[float], sklearn: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    threshold_metrics: dict[float, dict[str, Any]] = {}
    for threshold in _candidate_thresholds(y_score):
        y_pred = _predict_at_threshold(y_score, threshold)
        threshold_metrics[threshold] = _metric_values(y_test, y_pred, y_score, sklearn)

    chosen_threshold = max(threshold_metrics, key=lambda threshold: _threshold_objective(threshold_metrics[threshold]))
    metrics = threshold_metrics[chosen_threshold]
    metrics['threshold_search'] = {
        'candidate_count': len(threshold_metrics),
        'objective': 'max_f1_then_recall_specificity_precision',
    }
    return float(chosen_threshold), metrics


def _score_estimator(estimator, x_test: list[list[float]]) -> list[float]:
    if hasattr(estimator, 'predict_proba'):
        return [float(item) for item in estimator.predict_proba(x_test)[:, 1]]
    return [float(item) for item in estimator.decision_function(x_test)]


def _fit_candidates(candidates: dict[str, Any], split: DatasetSplit, sklearn: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, estimator in candidates.items():
        estimator.fit(split.x_train, split.y_train)
        y_score = _score_estimator(estimator, split.x_test)
        threshold, metrics = _evaluate_thresholds(split.y_test, y_score, sklearn)
        results[name] = {
            'estimator': estimator,
            'decision_threshold': threshold,
            'metrics': metrics,
        }
    return results


def _baseline_metrics(results: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        name: {
            'threshold': payload['decision_threshold'],
            **payload['metrics'],
        }
        for name, payload in results.items()
    }


def _write_report(report_path: str | Path | None, report: dict[str, Any]) -> str:
    if report_path is None:
        return ''
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return str(output)


def _train_prepared_dataset(
    dataset: PreparedDataset,
    output_path: str | Path,
    model_version_prefix: str,
    dataset_name: str,
    candidates: dict[str, Any],
    selected_model_name: str | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    sklearn = _import_sklearn()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    class_distribution = _class_distribution(dataset.labels)
    if class_distribution['positive'] == 0 or class_distribution['negative'] == 0:
        raise RuntimeError('训练集至少需要同时包含 AF 与非 AF 两类样本。')

    split = _split_dataset(dataset, sklearn)
    results = _fit_candidates(candidates, split, sklearn)
    if selected_model_name is None:
        selected_model_name = max(results, key=lambda name: results[name]['metrics']['auroc'])
    if selected_model_name not in results:
        raise RuntimeError(f'指定的主模型不存在: {selected_model_name}')

    selected = results[selected_model_name]
    artifact = {
        'task': 'af_binary',
        'dataset': dataset_name,
        'model_name': selected_model_name,
        'model_version': f'{model_version_prefix}-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        'feature_names': dataset.feature_names,
        'decision_threshold': selected['decision_threshold'],
        'metrics': selected['metrics'],
        'baseline_metrics': _baseline_metrics(results),
        'class_distribution': class_distribution,
        'dataset_summary': _dataset_summary(dataset),
        'split': {
            'strategy': split.split_strategy,
            'train_groups': len(set(split.train_groups)) if split.train_groups else 0,
            'test_groups': len(set(split.test_groups)) if split.test_groups else 0,
            'train_distribution': _class_distribution(split.y_train),
            'test_distribution': _class_distribution(split.y_test),
        },
        'estimator': selected['estimator'],
    }

    with output.open('wb') as handle:
        pickle.dump(artifact, handle)

    report = {
        'output_path': str(output),
        'dataset': dataset_name,
        'model_name': selected_model_name,
        'model_version': artifact['model_version'],
        'feature_names': dataset.feature_names,
        'decision_threshold': selected['decision_threshold'],
        'metrics': selected['metrics'],
        'baseline_metrics': artifact['baseline_metrics'],
        'class_distribution': class_distribution,
        'dataset_summary': artifact['dataset_summary'],
        'split': artifact['split'],
        'train_samples': len(split.x_train),
        'test_samples': len(split.x_test),
    }
    report_output = _write_report(report_path, report)
    if report_output:
        report['report_path'] = report_output
    return report


def train_feature_csv_model(
    csv_path: str | Path,
    output_path: str | Path,
    model_version_prefix: str,
    candidates: dict[str, Any],
    selected_model_name: str | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    dataset = load_training_rows(csv_path)
    return _train_prepared_dataset(
        dataset=dataset,
        output_path=output_path,
        model_version_prefix=model_version_prefix,
        dataset_name=Path(csv_path).name,
        candidates=candidates,
        selected_model_name=selected_model_name,
        report_path=report_path,
    )


def _sklearn_baseline_candidates() -> dict[str, Any]:
    sklearn = _import_sklearn()
    return {
        'logistic-regression': sklearn['LogisticRegression'](max_iter=2000, class_weight='balanced'),
        'hist-gradient-boosting': sklearn['HistGradientBoostingClassifier'](
            max_depth=5,
            learning_rate=0.05,
            random_state=42,
        ),
    }


def _structured_candidates(scale_pos_weight: float) -> dict[str, Any]:
    LGBMClassifier = _import_lightgbm()
    candidates = {
        'lightgbm': LGBMClassifier(
            objective='binary',
            n_estimators=400,
            learning_rate=0.03,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.85,
            scale_pos_weight=scale_pos_weight,
            n_jobs=-1,
            random_state=42,
            verbosity=-1,
        ),
    }
    candidates.update(_sklearn_baseline_candidates())
    return candidates


def train_ppg_af_model(csv_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    return train_feature_csv_model(
        csv_path=csv_path,
        output_path=output_path or settings.DEFAULT_PPG_AF_MODEL_PATH,
        model_version_prefix='ppg-af',
        candidates=_sklearn_baseline_candidates(),
    )


def train_structured_af_model(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    dataset = load_training_rows(csv_path)
    class_distribution = _class_distribution(dataset.labels)
    scale_pos_weight = (
        float(class_distribution['negative']) / float(class_distribution['positive'])
        if class_distribution['positive']
        else 1.0
    )
    return _train_prepared_dataset(
        dataset=dataset,
        output_path=output_path or settings.DEFAULT_STRUCTURED_AF_MODEL_PATH,
        model_version_prefix='structured-af',
        dataset_name=Path(csv_path).name,
        candidates=_structured_candidates(scale_pos_weight),
        selected_model_name='lightgbm',
        report_path=report_path,
    )


def train_cpsc2021_rr_experiment(
    csv_path: str | Path,
    output_path: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    dataset = load_training_rows(csv_path)
    class_distribution = _class_distribution(dataset.labels)
    scale_pos_weight = (
        float(class_distribution['negative']) / float(class_distribution['positive'])
        if class_distribution['positive']
        else 1.0
    )
    return _train_prepared_dataset(
        dataset=dataset,
        output_path=output_path,
        model_version_prefix='cpsc2021-rr',
        dataset_name=Path(csv_path).name,
        candidates=_structured_candidates(scale_pos_weight),
        selected_model_name='lightgbm',
        report_path=report_path,
    )
