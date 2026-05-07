# Generated migration for extended CaseInfoRequest functionality
# Adds: CaseInfoRequestTemplate, CaseInfoRequestResponse, new fields on CaseInfoRequest

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0009_add_info_requested_and_case_info_request'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create CaseInfoRequestTemplate model
        migrations.CreateModel(
            name='CaseInfoRequestTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(choices=[('identity', 'Identity/Verification'), ('address', 'Address Proof'), ('employment', 'Employment History'), ('education', 'Education Credentials'), ('financial', 'Financial Information'), ('references', 'References'), ('other', 'Other')], max_length=20)),
                ('title', models.CharField(help_text="e.g., 'Proof of Current Address'", max_length=100)),
                ('description', models.TextField(help_text='Template text for the request')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Info Request Template',
                'verbose_name_plural': 'Info Request Templates',
                'ordering': ['category', 'title'],
            },
        ),

        # Add new fields to CaseInfoRequest
        migrations.AddField(
            model_name='caseinforequest',
            name='template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='used_in_requests', to='applications.caseinforequesttemplate'),
        ),
        migrations.AddField(
            model_name='caseinforequest',
            name='category',
            field=models.CharField(choices=[('identity', 'Identity/Verification'), ('address', 'Address Proof'), ('employment', 'Employment History'), ('education', 'Education Credentials'), ('financial', 'Financial Information'), ('references', 'References'), ('other', 'Other')], default='other', help_text='Categorize the type of information requested', max_length=20),
        ),
        migrations.AddField(
            model_name='caseinforequest',
            name='due_by',
            field=models.DateTimeField(blank=True, help_text='When the applicant should respond by', null=True),
        ),
        migrations.AddField(
            model_name='caseinforequest',
            name='reopened_at',
            field=models.DateTimeField(blank=True, help_text='When request was reopened for revision', null=True),
        ),
        migrations.AddField(
            model_name='caseinforequest',
            name='reopened_count',
            field=models.IntegerField(default=0, help_text='Number of times request was reopened'),
        ),
        migrations.AddField(
            model_name='caseinforequest',
            name='escalated_at',
            field=models.DateTimeField(blank=True, help_text='When request was auto-escalated due to overdue response', null=True),
        ),

        # Alter status field to add new choices
        migrations.AlterField(
            model_name='caseinforequest',
            name='status',
            field=models.CharField(
                choices=[('open', 'Open'), ('responded', 'Responded'), ('revision_requested', 'Revision Requested'), ('closed', 'Closed')],
                db_index=True,
                default='open',
                max_length=25
            ),
        ),

        migrations.AddIndex(
            model_name='caseinforequest',
            index=models.Index(fields=['status', 'due_by'], name='app_cir_status_due_idx'),
        ),

        # Create CaseInfoRequestResponse model
        migrations.CreateModel(
            name='CaseInfoRequestResponse',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file', models.FileField(help_text='Supporting document or file', upload_to='info_requests')),
                ('filename', models.CharField(editable=False, max_length=255)),
                ('file_size', models.BigIntegerField(editable=False, help_text='File size in bytes')),
                ('file_type', models.CharField(editable=False, help_text='MIME type', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('info_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='response_attachments', to='applications.caseinforequest')),
            ],
            options={
                'verbose_name': 'Info Request Response Attachment',
                'verbose_name_plural': 'Info Request Response Attachments',
                'ordering': ['created_at'],
            },
        ),
    ]
