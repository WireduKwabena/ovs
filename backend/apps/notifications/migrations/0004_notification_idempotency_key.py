from django.db import migrations, models


def backfill_notification_idempotency_keys(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    seen: set[tuple[str, str, str]] = set()
    updates = []

    for notification in Notification.objects.all().order_by("created_at", "id").iterator():
        metadata = notification.metadata if isinstance(notification.metadata, dict) else {}
        raw_key = metadata.get("idempotency_key")
        normalized_key = str(raw_key).strip() if raw_key not in (None, "") else None
        if not normalized_key:
            continue

        dedupe_key = (
            str(notification.recipient_id),
            str(notification.notification_type),
            normalized_key,
        )
        notification.idempotency_key = None if dedupe_key in seen else normalized_key
        seen.add(dedupe_key)
        updates.append(notification)

    if updates:
        Notification.objects.bulk_update(updates, ["idempotency_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_rename_notificatio_recipie_f7f57e_idx_notificatio_recipie_b9dbed_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="idempotency_key",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.RunPython(
            backfill_notification_idempotency_keys,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=("recipient", "notification_type", "idempotency_key"),
                name="uq_notification_recipient_type_idempotency",
            ),
        ),
    ]
