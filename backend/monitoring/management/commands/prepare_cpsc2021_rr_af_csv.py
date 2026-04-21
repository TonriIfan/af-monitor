import csv
from bisect import bisect_right
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from monitoring.ml.features import extract_structured_features_from_rr_intervals


AF_LABELS = {'AFIB', 'AFL'}
BEAT_SYMBOLS = {'N', 'L', 'R', 'A', 'a', 'J', 'S', 'V', 'F', 'e', 'j', 'E', '/', 'f', 'Q'}


def _import_wfdb():
    try:
        import wfdb
        from wfdb import processing
    except ImportError as exc:
        raise RuntimeError('缺少 wfdb 依赖，请先安装 backend/requirements.txt。') from exc
    return wfdb, processing


def _normalize_rhythm_label(value: str | bytes | None) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='ignore')
    token = value.strip().strip('\x00').strip('()').upper()
    if 'AFIB' in token:
        return 'AFIB'
    if token == 'AFL' or 'AFL' in token:
        return 'AFL'
    if token in {'N', 'NSR', 'NORMAL'}:
        return 'N'
    return token


def _discover_record_paths(data_dir: Path) -> list[Path]:
    candidates = []
    for hea_path in data_dir.rglob('*.hea'):
        parts = {part.lower() for part in hea_path.parts}
        if 'training_set_i' in parts or 'training_set_ii' in parts:
            candidates.append(hea_path.with_suffix(''))
    if not candidates:
        candidates = [path.with_suffix('') for path in data_dir.rglob('*.hea')]
    return sorted(set(candidates))


def _annotation_beat_samples(annotation) -> list[int]:
    return [
        int(sample)
        for sample, symbol in zip(annotation.sample, annotation.symbol)
        if symbol in BEAT_SYMBOLS
    ]


def _detect_r_peaks(wfdb_processing, record, annotation) -> list[int]:
    annotated_beats = _annotation_beat_samples(annotation)
    if len(annotated_beats) >= 3:
        return annotated_beats

    signal = record.p_signal[:, 0]
    peaks = wfdb_processing.xqrs_detect(sig=signal, fs=record.fs, verbose=False)
    return [int(item) for item in peaks]


def _rhythm_segments(annotation, fs: float, duration_seconds: float) -> list[tuple[float, float, str]]:
    change_points: list[tuple[float, str]] = []
    aux_notes = getattr(annotation, 'aux_note', None) or []
    for sample, aux_note in zip(annotation.sample, aux_notes):
        label = _normalize_rhythm_label(aux_note)
        if label:
            change_points.append((float(sample) / fs, label))

    if not change_points:
        return [(0.0, duration_seconds, 'N')]

    change_points = sorted(change_points)
    if change_points[0][0] > 0:
        change_points.insert(0, (0.0, change_points[0][1]))

    segments: list[tuple[float, float, str]] = []
    for index, (start, label) in enumerate(change_points):
        end = change_points[index + 1][0] if index + 1 < len(change_points) else duration_seconds
        if end > start:
            segments.append((start, end, label))
    return segments or [(0.0, duration_seconds, 'N')]


def _af_ratio_for_window(segments: list[tuple[float, float, str]], window_start: float, window_end: float) -> float:
    overlap_seconds = 0.0
    af_seconds = 0.0
    for segment_start, segment_end, label in segments:
        overlap_start = max(window_start, segment_start)
        overlap_end = min(window_end, segment_end)
        overlap = max(0.0, overlap_end - overlap_start)
        if overlap <= 0:
            continue
        overlap_seconds += overlap
        if label in AF_LABELS:
            af_seconds += overlap
    return af_seconds / overlap_seconds if overlap_seconds else 0.0


def _rr_window_values(peak_times: list[float], window_start: float, window_end: float) -> list[float]:
    if len(peak_times) < 2:
        return []
    end_times = peak_times[1:]
    ibis = [peak_times[index] - peak_times[index - 1] for index in range(1, len(peak_times))]
    start_index = bisect_right(end_times, window_start)
    end_index = bisect_right(end_times, window_end)
    return ibis[start_index:end_index]


def _process_record(
    record_path: Path,
    options: dict[str, Any],
    writer,
    feature_names: list[str] | None,
    class_counts: dict[int, int],
) -> tuple[int, list[str] | None]:
    wfdb, wfdb_processing = _import_wfdb()
    record_name = str(record_path)
    record = wfdb.rdrecord(record_name, channels=[0])
    annotation = wfdb.rdann(record_name, 'atr')
    fs = float(record.fs)
    duration_seconds = float(record.sig_len) / fs
    r_peaks = _detect_r_peaks(wfdb_processing, record, annotation)
    peak_times = [float(sample) / fs for sample in sorted(r_peaks)]
    segments = _rhythm_segments(annotation, fs, duration_seconds)

    rows_written = 0
    window_seconds = float(options['window_seconds'])
    stride_seconds = float(options['stride_seconds'])
    positive_threshold = float(options['positive_threshold'])
    negative_threshold = float(options['negative_threshold'])
    min_rr_intervals = int(options['min_rr_intervals'])
    max_windows_per_class = int(options['max_windows_per_class'])

    window_start = 0.0
    while window_start + window_seconds <= duration_seconds:
        if max_windows_per_class and class_counts[0] >= max_windows_per_class and class_counts[1] >= max_windows_per_class:
            break

        window_end = window_start + window_seconds
        af_ratio = _af_ratio_for_window(segments, window_start, window_end)
        if af_ratio >= positive_threshold:
            label = 1
        elif af_ratio <= negative_threshold:
            label = 0
        else:
            window_start += stride_seconds
            continue

        if max_windows_per_class and class_counts[label] >= max_windows_per_class:
            window_start += stride_seconds
            continue

        ibis = _rr_window_values(peak_times, window_start, window_end)
        if len(ibis) < min_rr_intervals:
            window_start += stride_seconds
            continue

        features = extract_structured_features_from_rr_intervals(ibis, window_seconds)
        if feature_names is None:
            feature_names = list(features.keys())
            writer.fieldnames = [
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
            ]
            writer.writeheader()

        row = {
            'patient_id': record_path.stem,
            'group_id': record_path.stem,
            'record_id': record_path.stem,
            'window_start_sec': round(window_start, 4),
            'window_end_sec': round(window_end, 4),
            'sample_rate_hz': round(fs, 4),
            'label': label,
            'af_ratio': round(af_ratio, 4),
            'ambiguous_ratio': 0.0,
        }
        row.update(features)
        writer.writerow(row)
        rows_written += 1
        class_counts[label] += 1
        window_start += stride_seconds

    return rows_written, feature_names


class Command(BaseCommand):
    help = '将 PhysioNet CPSC2021 ECG 数据转换为 RR 结构化 AF 补充实验 CSV。'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', required=True, help='CPSC2021 解压后的数据目录。')
        parser.add_argument('--output', required=True, help='输出 CSV 路径。')
        parser.add_argument('--window-seconds', type=int, default=30)
        parser.add_argument('--stride-seconds', type=int, default=30)
        parser.add_argument('--positive-threshold', type=float, default=0.8)
        parser.add_argument('--negative-threshold', type=float, default=0.05)
        parser.add_argument('--min-rr-intervals', type=int, default=10)
        parser.add_argument('--max-windows-per-class', type=int, default=0)

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir']).resolve()
        output_path = Path(options['output']).resolve()
        if not data_dir.exists():
            raise CommandError(f'数据目录不存在: {data_dir}')

        record_paths = _discover_record_paths(data_dir)
        if not record_paths:
            raise CommandError(f'在 {data_dir} 未找到 WFDB .hea 文件。')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows_written = 0
        feature_names: list[str] | None = None
        class_counts = {0: 0, 1: 0}

        with output_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=[])
            for record_path in record_paths:
                try:
                    record_rows, feature_names = _process_record(
                        record_path=record_path,
                        options=options,
                        writer=writer,
                        feature_names=feature_names,
                        class_counts=class_counts,
                    )
                except Exception as exc:
                    self.stderr.write(f'跳过记录 {record_path.name}: {exc}')
                    continue
                rows_written += record_rows

        if rows_written == 0:
            raise CommandError('没有生成任何可用窗口，请检查 CPSC2021 数据目录或调整窗口参数。')

        self.stdout.write(self.style.SUCCESS('CPSC2021 RR 结构化 AF 实验 CSV 已生成'))
        self.stdout.write(f'output: {output_path}')
        self.stdout.write(f'rows: {rows_written}')
        self.stdout.write(f'positive: {class_counts[1]}')
        self.stdout.write(f'negative: {class_counts[0]}')
        self.stdout.write(f'positive_ratio: {round(class_counts[1] / rows_written, 4)}')
