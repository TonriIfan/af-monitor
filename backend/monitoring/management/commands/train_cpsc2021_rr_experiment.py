from django.core.management.base import BaseCommand, CommandError

from monitoring.ml.training import train_cpsc2021_rr_experiment


class Command(BaseCommand):
    help = '使用 CPSC2021 RR 结构化窗口 CSV 训练补充实验模型并输出报告。'

    def add_arguments(self, parser):
        parser.add_argument('--csv', required=True, help='CPSC2021 RR 结构化训练 CSV 路径。')
        parser.add_argument('--output', required=True, help='实验模型输出路径。')
        parser.add_argument('--report', help='可选：JSON 训练报告路径。')

    def handle(self, *args, **options):
        try:
            result = train_cpsc2021_rr_experiment(
                csv_path=options['csv'],
                output_path=options['output'],
                report_path=options.get('report'),
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('CPSC2021 RR 补充实验模型训练完成'))
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
