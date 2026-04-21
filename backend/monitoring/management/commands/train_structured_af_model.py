from django.core.management.base import BaseCommand, CommandError

from monitoring.ml.training import train_structured_af_model


class Command(BaseCommand):
    help = '使用结构化窗口特征 CSV 训练现网主链路 AF 风险模型。'

    def add_arguments(self, parser):
        parser.add_argument('--csv', required=True, help='结构化训练 CSV 路径，至少包含 label 与特征列。')
        parser.add_argument('--output', help='模型输出路径，默认写入 settings.DEFAULT_STRUCTURED_AF_MODEL_PATH。')
        parser.add_argument('--report', help='可选：输出 JSON 训练报告路径。')

    def handle(self, *args, **options):
        try:
            result = train_structured_af_model(options['csv'], options.get('output'), options.get('report'))
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('结构化 AF 模型训练完成'))
        self.stdout.write(f"model_name: {result['model_name']}")
        self.stdout.write(f"model_version: {result['model_version']}")
        self.stdout.write(f"decision_threshold: {result['decision_threshold']}")
        self.stdout.write(f"output_path: {result['output_path']}")
        self.stdout.write(f"train_samples: {result['train_samples']}")
        self.stdout.write(f"test_samples: {result['test_samples']}")
        self.stdout.write(f"class_distribution: {result['class_distribution']}")
        self.stdout.write(f"metrics: {result['metrics']}")
        self.stdout.write(f"baseline_metrics: {result['baseline_metrics']}")
        if result.get('report_path'):
            self.stdout.write(f"report_path: {result['report_path']}")
