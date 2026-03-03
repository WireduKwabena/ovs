from __future__ import annotations

from django.apps import apps
from django.core.checks import Error, register
from django.db import models


@register()
def enforce_uuid_primary_keys(app_configs, **kwargs):
    """
    Enforce UUID primary keys for all managed project models.
    """
    errors = []

    for model in apps.get_models():
        module_name = getattr(model, "__module__", "")
        if not module_name.startswith("apps."):
            continue

        if model._meta.abstract or model._meta.proxy or not model._meta.managed:
            continue

        pk_field = model._meta.pk
        if isinstance(pk_field, models.UUIDField):
            continue

        errors.append(
            Error(
                f"{model._meta.label} uses non-UUID primary key "
                f"({pk_field.__class__.__name__}).",
                hint="Set `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`.",
                obj=model,
                id="core.E001",
            )
        )

    return errors
