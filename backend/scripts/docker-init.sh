#!/bin/sh
set -eu

echo "Running migrations..."
python manage.py migrate --noinput

if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo "Ensuring bootstrap superuser exists..."
  python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()

email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
first_name = os.environ.get("DJANGO_SUPERUSER_FIRST_NAME", "System").strip() or "System"
last_name = os.environ.get("DJANGO_SUPERUSER_LAST_NAME", "Admin").strip() or "Admin"
reset_password = os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if not email:
    raise SystemExit("DJANGO_SUPERUSER_EMAIL must not be empty when provided.")

user, created = User.objects.get_or_create(
    email=email,
    defaults={
        "first_name": first_name,
        "last_name": last_name,
        "user_type": "admin",
        "is_staff": True,
        "is_superuser": True,
        "is_active": True,
    },
)

changed_fields = []
if not user.is_staff:
    user.is_staff = True
    changed_fields.append("is_staff")
if not user.is_superuser:
    user.is_superuser = True
    changed_fields.append("is_superuser")
if not user.is_active:
    user.is_active = True
    changed_fields.append("is_active")
if getattr(user, "user_type", None) != "admin":
    user.user_type = "admin"
    changed_fields.append("user_type")

if changed_fields:
    if hasattr(user, "updated_at"):
        changed_fields.append("updated_at")
    user.save(update_fields=changed_fields)

if created or reset_password:
    user.set_password(password)
    user.save(update_fields=["password"])
    action = "Created" if created else "Updated"
    print(f"{action} bootstrap superuser: {email}")
else:
    print(f"Bootstrap superuser already exists: {email}")
PY
else
  echo "Skipping bootstrap superuser (DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD not both set)."
fi
