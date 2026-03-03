from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db import models


@dataclass
class SchemaIssue:
    model_label: str
    table_name: str
    column_name: str
    reason: str


class Command(BaseCommand):
    help = (
        "Validate that managed project model primary key columns are UUID in the "
        "active database schema."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to validate (default: default).",
        )

    def handle(self, *args, **options):
        database_alias = options["database"]
        connection = connections[database_alias]

        if connection.vendor != "postgresql":
            raise CommandError(
                "check_uuid_schema currently supports PostgreSQL only."
            )

        issues = self._collect_issues(connection)
        if issues:
            for issue in issues:
                self.stdout.write(
                    self.style.ERROR(
                        f"{issue.model_label} -> {issue.table_name}.{issue.column_name}: "
                        f"{issue.reason}"
                    )
                )
            raise CommandError(
                f"UUID schema check failed with {len(issues)} issue(s)."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "UUID schema check passed: all managed project model PK columns are UUID."
            )
        )

    def _collect_issues(self, connection) -> list[SchemaIssue]:
        issues: list[SchemaIssue] = []

        managed_models = []
        for model in apps.get_models():
            module_name = getattr(model, "__module__", "")
            if not module_name.startswith("apps."):
                continue
            if model._meta.abstract or model._meta.proxy or not model._meta.managed:
                continue
            managed_models.append(model)

        with connection.cursor() as cursor:
            for model in managed_models:
                pk_field = model._meta.pk
                if not isinstance(pk_field, models.UUIDField):
                    issues.append(
                        SchemaIssue(
                            model_label=model._meta.label,
                            table_name=model._meta.db_table,
                            column_name=pk_field.column,
                            reason=(
                                "model primary key is not UUIDField "
                                f"({pk_field.__class__.__name__})"
                            ),
                        )
                    )
                    continue

                cursor.execute(
                    """
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                      AND column_name = %s
                    LIMIT 1
                    """,
                    [model._meta.db_table, pk_field.column],
                )
                row = cursor.fetchone()
                if not row:
                    issues.append(
                        SchemaIssue(
                            model_label=model._meta.label,
                            table_name=model._meta.db_table,
                            column_name=pk_field.column,
                            reason="column missing in database",
                        )
                    )
                    continue

                data_type, udt_name = row
                is_uuid = str(data_type).lower() == "uuid" or str(udt_name).lower() == "uuid"
                if not is_uuid:
                    issues.append(
                        SchemaIssue(
                            model_label=model._meta.label,
                            table_name=model._meta.db_table,
                            column_name=pk_field.column,
                            reason=f"database type is {data_type} (udt={udt_name})",
                        )
                    )

        return issues
