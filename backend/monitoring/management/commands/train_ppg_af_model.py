from django.core.management.base import BaseCommand, CommandError

from monitoring.ml.training import train_ppg_af_model


class Command(BaseCommand):
    help = '使用窗口级 CSV 数据训练 PPG AF 二分类模型并保存为后端可加载的模型文件。'

    def add_arguments(self, parser):
        parser.add_argument('--csv', required=True, help='训练数据 CSV 路径，至少包含 label、sample_rate_hz、samples 列。')
        parser.add_argument('--output', help='模型输出路径，默认写入 settings.DEFAULT_PPG_AF_MODEL_PATH。')

    def handle(self, *args, **options):
        try:
            result = train_ppg_af_model(options['csv'], options.get('output'))
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('PPG AF 模型训练完成'))
        self.stdout.write(f"model_name: {result['model_name']}")
        self.stdout.write(f"model_version: {result['model_version']}")
        self.stdout.write(f"output_path: {result['output_path']}")
        self.stdout.write(f"metrics: {result['metrics']}")
