import csv
from pathlib import Path

import h5py
import numpy as np
from django.core.management.base import BaseCommand, CommandError

from monitoring.ml.features import extract_structured_features_from_ppg


def _decode_char_dataset(dataset) -> str:
    values = np.array(dataset).astype('uint16').flatten()
    return ''.join(chr(int(item)) for item in values if int(item) != 0)


def _decode_header_strings(file_handle, dataset_path: str) -> list[str]:
    refs = file_handle[dataset_path][:]
    return [_decode_char_dataset(file_handle[ref]) for ref in refs.flatten()]


def _absolute_start_seconds(file_handle) -> int:
    day_token = _decode_char_dataset(file_handle['recording_startday']) or '0'
    time_token = _decode_char_dataset(file_handle['recording_starttime']) or '00:00:00'
    hours, minutes, seconds = [int(part) for part in time_token.split(':')]
    return ((int(day_token) - 1) * 86400) + (hours * 3600) + (minutes * 60) + seconds


def _build_ecg_index(ecg_path: Path) -> dict[str, np.ndarray | float | int]:
    with h5py.File(ecg_path, 'r') as handle:
        qrs_index = np.asarray(handle['QRSindex']).reshape(-1)
        af_annotation = np.asarray(handle['AF_annotation']).reshape(-1)
        absolute_start = _absolute_start_seconds(handle)
    if len(qrs_index) != len(af_annotation) + 1:
        raise RuntimeError(f'{ecg_path.name} 的 QRSindex 与 AF_annotation 长度不匹配。')
    return {
        'interval_starts': absolute_start + (qrs_index[:-1] / 500.0),
        'af_annotation': af_annotation,
    }


class Command(BaseCommand):
    help = '将 Zenodo 5815074 的 PPG/ECG 数据转换为现网结构化时间窗模型训练 CSV。'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='解压后的 Data 目录路径。')
        parser.add_argument('--output', required=True, help='输出 CSV 路径。')
        parser.add_argument('--window-seconds', type=int, default=30)
        parser.add_argument('--stride-seconds', type=int, default=30)
        parser.add_argument('--positive-threshold', type=float, default=0.8)
        parser.add_argument('--negative-threshold', type=float, default=0.05)
        parser.add_argument('--max-windows-per-class', type=int, default=0)

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir']).resolve()
        output_path = Path(options['output']).resolve()
        window_seconds = int(options['window_seconds'])
        stride_seconds = int(options['stride_seconds'])
        positive_threshold = float(options['positive_threshold'])
        negative_threshold = float(options['negative_threshold'])
        max_windows_per_class = int(options['max_windows_per_class'])

        if not data_dir.exists():
            raise CommandError(f'数据目录不存在: {data_dir}')
        ppg_paths = sorted(data_dir.glob('*_PPG_*.mat'))
        if not ppg_paths:
            raise CommandError(f'在 {data_dir} 未找到 PPG mat 文件。')

        patient_ids = sorted({path.name.split('_')[0] for path in ppg_paths})
        ecg_index: dict[str, dict[str, np.ndarray | float | int]] = {}
        for patient_id in patient_ids:
            ecg_candidates = sorted(data_dir.glob(f'{patient_id}_ECG_*.mat'))
            if not ecg_candidates:
                raise CommandError(f'患者 {patient_id} 缺少 ECG 文件。')
            ecg_index[patient_id] = _build_ecg_index(ecg_candidates[0])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows_written = 0
        positive_count = 0
        negative_count = 0
        feature_names: list[str] | None = None

        with output_path.open('w', encoding='utf-8', newline='') as handle:
            writer = None
            for patient_id in patient_ids:
                ecg_payload = ecg_index[patient_id]
                interval_starts = ecg_payload['interval_starts']
                af_annotation = ecg_payload['af_annotation']

                for ppg_path in sorted(data_dir.glob(f'{patient_id}_PPG_*.mat')):
                    with h5py.File(ppg_path, 'r') as ppg_handle:
                        labels = _decode_header_strings(ppg_handle, 'signalHeader/signal_labels')
                        sample_rates = [
                            float(np.array(ppg_handle[ref]).reshape(-1)[0])
                            for ref in ppg_handle['signalHeader/samples_in_record'][:].flatten()
                        ]
                        try:
                            ppg_rate = sample_rates[labels.index('PPG_GREEN')]
                        except ValueError as exc:
                            raise CommandError(f'{ppg_path.name} 缺少 PPG_GREEN 通道。') from exc
                        ppg_signal = np.asarray(ppg_handle['PPG_GREEN']).reshape(-1)
                        ppg_absolute_start = _absolute_start_seconds(ppg_handle)

                    samples_per_window = int(window_seconds * ppg_rate)
                    stride_samples = int(stride_seconds * ppg_rate)
                    for window_start in range(0, len(ppg_signal) - samples_per_window + 1, stride_samples):
                        if max_windows_per_class and positive_count >= max_windows_per_class and negative_count >= max_windows_per_class:
                            break

                        absolute_window_start = ppg_absolute_start + (window_start / ppg_rate)
                        absolute_window_end = absolute_window_start + window_seconds
                        start_index = np.searchsorted(interval_starts, absolute_window_start, side='left')
                        end_index = np.searchsorted(interval_starts, absolute_window_end, side='right')
                        if end_index - start_index < 10:
                            continue

                        labels_slice = af_annotation[start_index:end_index]
                        af_ratio = float(np.mean(labels_slice == 1.0))
                        ambiguous_ratio = float(np.mean(labels_slice == 0.5))
                        if af_ratio >= positive_threshold:
                            label = 1
                            if max_windows_per_class and positive_count >= max_windows_per_class:
                                continue
                        elif af_ratio <= negative_threshold and ambiguous_ratio <= 0.10:
                            label = 0
                            if max_windows_per_class and negative_count >= max_windows_per_class:
                                continue
                        else:
                            continue

                        window_samples = ppg_signal[window_start:window_start + samples_per_window].astype(float).tolist()
                        features, _ = extract_structured_features_from_ppg(window_samples, ppg_rate)
                        if feature_names is None:
                            feature_names = list(features.keys())
                            writer = csv.DictWriter(
                                handle,
                                fieldnames=[
                                    'patient_id',
                                    'group_id',
                                    'record_id',
                                    'window_start_sec',
                                    'window_end_sec',
                                    'sample_rate_hz',
                                    'label',
                                    'af_ratio',
                                    'ambiguous_ratio',
                                    *feature_names,
                                ],
                            )
                            writer.writeheader()

                        row = {
                            'patient_id': patient_id,
                            'group_id': patient_id,
                            'record_id': ppg_path.stem,
                            'window_start_sec': round(absolute_window_start, 4),
                            'window_end_sec': round(absolute_window_end, 4),
                            'sample_rate_hz': round(ppg_rate, 4),
                            'label': label,
                            'af_ratio': round(af_ratio, 4),
                            'ambiguous_ratio': round(ambiguous_ratio, 4),
                        }
                        row.update(features)
                        writer.writerow(row)
                        rows_written += 1
                        if label == 1:
                            positive_count += 1
                        else:
                            negative_count += 1

            if rows_written == 0:
                raise CommandError('没有生成任何可用窗口，请调整阈值或检查数据目录。')

        self.stdout.write(self.style.SUCCESS('Zenodo 结构化 AF 训练 CSV 已生成'))
        self.stdout.write(f'output: {output_path}')
        self.stdout.write(f'rows: {rows_written}')
        self.stdout.write(f'positive: {positive_count}')
        self.stdout.write(f'negative: {negative_count}')
        self.stdout.write(f'positive_ratio: {round(positive_count / rows_written, 4)}')
