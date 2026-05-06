import uuid
from django.db import migrations, models


def _populate_guest_tokens(apps, schema_editor):
    VideoMeetingParticipant = apps.get_model('video_calls', 'VideoMeetingParticipant')
    for participant in VideoMeetingParticipant.objects.all():
        participant.guest_token = uuid.uuid4()
        participant.save(update_fields=['guest_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('video_calls', '0008_cross_schema_fk_no_db_constraints'),
    ]

    operations = [
        # Step 1: add column without unique constraint, nullable so existing rows get NULL
        migrations.AddField(
            model_name='videomeetingparticipant',
            name='guest_token',
            field=models.UUIDField(null=True, blank=True, editable=False, db_index=True),
        ),
        # Step 2: fill each existing row with its own unique UUID
        migrations.RunPython(_populate_guest_tokens, migrations.RunPython.noop),
        # Step 3: make it non-nullable + unique
        migrations.AlterField(
            model_name='videomeetingparticipant',
            name='guest_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True),
        ),
    ]
