from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0001_initial'),
        ('monitoring', '0004_pushdeviceregistration_symptomfeedback'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PpgAnalysisRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('collected_at', models.DateTimeField()),
                ('source', models.CharField(default='app_upload', max_length=64)),
                ('sample_rate_hz', models.FloatField()),
                ('window_seconds', models.DecimalField(decimal_places=2, max_digits=6)),
                ('sample_count', models.PositiveIntegerField()),
                ('samples', models.JSONField(blank=True, default=list)),
                ('quality_pass', models.BooleanField(default=False)),
                ('quality_score', models.DecimalField(decimal_places=2, default=0, max_digits=4)),
                ('af_probability', models.DecimalField(decimal_places=2, default=0, max_digits=4)),
                ('af_label', models.BooleanField(default=False)),
                ('model_version', models.CharField(default='heuristic-v1', max_length=64)),
                ('model_source', models.CharField(default='heuristic', max_length=16)),
                ('features', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ppg_analysis_records', to='devices.device')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ppg_analysis_records', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-collected_at', '-id'],
            },
        ),
    ]
