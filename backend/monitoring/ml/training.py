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


@dataclass
class DatasetSplit:
    x_train: list[list[float]]
    x_test: list[list[float]]
    y_train: list[int]
    y_test: list[int]


def _import_sklearn():
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
        from sklearn.model_selection import GroupShuffleSplit, train_test_split
    except ImportError as exc:
        raise RuntimeError('缺少 scikit-learn 依赖，请先安装 backend/requirements.txt。') from exc
    return {
        'HistGradientBoostingClassifier': HistGradientBoostingClassifier,
        'LogisticRegression': LogisticRegression,
        'f1_score': f1_score,
        'precision_score': precision_score,
        'recall_score': recall_score,
        'roc_auc_score': roc_auc_score,
        'GroupShuffleSplit': GroupShuffleSplit,
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
                if feature_names is None:
                    feature_names = [name for name in reader.fieldnames if name not in excluded]
                rows.append([float(record[name]) for name in feature_names])
            labels.append(label)
            groups.append(record.get('group_id') or record.get('patient_id') or record.get('record_id') or str(len(groups)))

    if not rows or feature_names is None:
        raise RuntimeError('训练集为空，无法训练 AF 模型。')
    return PreparedDataset(feature_names=feature_names, rows=rows, labels=labels, groups=groups)


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


def _split_dataset(dataset: PreparedDataset, sklearn: dict[str, Any]) -> DatasetSplit:
    if len(set(dataset.groups)) > 1:
        splitter = sklearn['GroupShuffleSplit'](n_splits=1, test_size=0.2, random_state=42)
        train_index, test_index = next(splitter.split(dataset.rows, dataset.labels, dataset.groups))
        split = DatasetSplit(
            x_train=[dataset.rows[index] for index in train_index],
            y_train=[dataset.labels[index] for index in train_index],
            x_test=[dataset.rows[index] for index in test_index],
            y_test=[dataset.labels[index] for index in test_index],
        )
    else:
        x_train, x_test, y_train, y_test = sklearn['train_test_split'](
            dataset.rows,
            dataset.labels,
            test_size=0.2,
            random_state=42,
            stratify=dataset.labels,
        )
        split = DatasetSplit(x_train=x_train, x_test=x_test, y_train=y_train, y_test=y_test)

    if len(set(split.y_train)) < 2 or len(set(split.y_test)) < 2:
        x_train, x_test, y_train, y_test = sklearn['train_test_split'](
            dataset.rows,
            dataset.labels,
            test_size=0.2,
            random_state=42,
            stratify=dataset.labels,
        )
        split = DatasetSplit(x_train=x_train, x_test=x_test, y_train=y_train, y_test=y_test)
    return split


def _score_estimator(estimator, x_test: list[list[float]]) -> list[float]:
    if hasattr(estimator, 'predict_proba'):
        return [float(item) for item in estimator.predict_proba(x_test)[:, 1]]
    return [float(item) for item in estimator.decision_function(x_test)]


def _evaluate_thresholds(y_test: list[int], y_score: list[float], sklearn: dict[str, Any]) -> tuple[float, dict[str, float]]:
    threshold_candidates = [round(item, 2) for item in np.arange(0.05, 0.96, 0.05)]
    threshold_metrics: dict[float, dict[str, float]] = {}
    for threshold in threshold_candidates:
        y_pred = [1 if float(score) >= threshold else 0 for score in y_score]
        threshold_metrics[threshold] = {
            'f1': float(sklearn['f1_score'](y_test, y_pred, zero_division=0)),
            'precision': float(sklearn['precision_score'](y_test, y_pred, zero_division=0)),
            'recall': float(sklearn['recall_score'](y_test, y_pred, zero_division=0)),
        }
    chosen_threshold = max(
        threshold_metrics,
        key=lambda threshold: (
            threshold_metrics[threshold]['f1'],
            threshold_metrics[threshold]['recall'],
            -threshold,
        ),
    )
    metrics = {
        'auroc': float(sklearn['roc_auc_score'](y_test, y_score)),
        'f1': threshold_metrics[chosen_threshold]['f1'],
        'precision': threshold_metrics[chosen_threshold]['precision'],
        'recall': threshold_metrics[chosen_threshold]['recall'],
    }
    return float(chosen_threshold), metrics


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
