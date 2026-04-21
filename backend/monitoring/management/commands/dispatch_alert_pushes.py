from django.core.management.base import BaseCommand

from monitoring.services import dispatch_pending_alert_pushes


class Command(BaseCommand):
    help = 'Dispatch pending alert push notifications.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='最多处理的待发送推送数量。',
        )

    def handle(self, *args, **options):
        summary = dispatch_pending_alert_pushes(limit=options['limit'])
        self.stdout.write(
            self.style.SUCCESS(
                '推送处理完成：'
                f"processed={summary['processed']} "
                f"sent={summary['sent']} "
                f"pending={summary['pending']} "
                f"failed={summary['failed']} "
                f"skipped={summary['skipped']}"
            )
        )
