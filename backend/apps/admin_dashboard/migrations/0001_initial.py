import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformIssueReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('steps_to_reproduce', models.TextField(blank=True)),
                ('page_url', models.CharField(blank=True, max_length=500)),
                ('browser_info', models.CharField(blank=True, max_length=500)),
                ('category', models.CharField(choices=[('bug', 'Bug'), ('issue', 'Issue'), ('improvement', 'Improvement')], default='issue', max_length=20)),
                ('severity', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium', max_length=20)),
                ('status', models.CharField(choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved')], db_index=True, default='open', max_length=20)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reporter', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='platform_issue_reports', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_platform_issue_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='platformissuereport',
            index=models.Index(fields=['status', 'created_at'], name='adm_pr_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='platformissuereport',
            index=models.Index(fields=['severity', 'created_at'], name='adm_pr_severity_created_idx'),
        ),
        migrations.AddIndex(
            model_name='platformissuereport',
            index=models.Index(fields=['reporter', 'created_at'], name='adm_pr_reporter_created_idx'),
        ),
    ]
