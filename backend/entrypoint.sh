#!/bin/bash
set -e

if [ "${RUN_INIT:-false}" = "true" ]; then
    echo "=== OVS Backend / Init Startup ==="

    MIGRATIONS_COMPLETE=$(PGPASSWORD=postgres psql -h db -U postgres -d vetai_db -tc \
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='django_site' AND table_schema='public');" \
        2>/dev/null || echo "false")

    if [ "$MIGRATIONS_COMPLETE" != "t" ] && [ "$MIGRATIONS_COMPLETE" != "true" ]; then
        echo "Running database initialization..."

        export DJANGO_SKIP_POST_MIGRATE_SIGNALS=1

        echo "  Step 1a: Running core framework migrations (dependency order)..."
        # Order matters: contenttypes and auth first, then users (creates users_user),
        # then admin (admin.0001_initial has FK → users_user and will fail if run
        # before users_user exists), then the remaining framework apps.
        python manage.py migrate_schemas --schema=public contenttypes --noinput
        python manage.py migrate_schemas --schema=public auth --noinput

        echo "  Step 1b: Running users migration..."
        python manage.py migrate_schemas --schema=public users --noinput

        echo "  Step 1b2: Running admin migration (requires users_user)..."
        python manage.py migrate_schemas --schema=public admin --noinput

        echo "  Step 1b3: Running remaining framework migrations..."
        python manage.py migrate_schemas --schema=public sites --noinput
        python manage.py migrate_schemas --schema=public sessions --noinput

        echo "  Step 1c: Running tenants migration..."
        python manage.py migrate_schemas --schema=public tenants --noinput

        echo "  Step 1d: Running all remaining migrations..."
        python manage.py migrate_schemas --schema=public --noinput

        unset DJANGO_SKIP_POST_MIGRATE_SIGNALS

        echo "  Step 2: Creating public organization..."
        python manage.py shell << 'ENDSHELL'
from apps.tenants.models import Organization
from django_tenants.utils import get_public_schema_name

schema = get_public_schema_name()
org, created = Organization.objects.get_or_create(
    schema_name=schema,
    defaults={'name': 'Public Schema', 'code': 'public', 'is_active': True}
)
print(f"✓ Organization: {org}")
ENDSHELL

        echo "  Step 3: Creating Site entries for localhost..."
        python manage.py shell << 'ENDSHELL'
from django.contrib.sites.models import Site

Site.objects.all().delete()
domains = ['127.0.0.1:8000', 'localhost:8000', 'localhost', '127.0.0.1']
for idx, domain in enumerate(domains):
    Site.objects.create(pk=idx+1, domain=domain, name=domain)
print(f"✓ Created {len(domains)} Site entries for localhost")
ENDSHELL

        echo "✓ Database initialization complete"

    else
        echo "✓ Database already initialized, checking for new migrations..."

        export DJANGO_SKIP_POST_MIGRATE_SIGNALS=1
        # Run users before admin to ensure users_user exists before admin.0001_initial
        # tries to create its FK constraint (this is a no-op if already applied).
        python manage.py migrate_schemas --schema=public users --noinput
        python manage.py migrate_schemas --schema=public admin --noinput
        python manage.py migrate_schemas --schema=public --noinput

        python manage.py shell << 'ENDSHELL'
from django.contrib.sites.models import Site
if not Site.objects.exists():
    domains = ['127.0.0.1:8000', 'localhost:8000', 'localhost', '127.0.0.1']
    for idx, domain in enumerate(domains):
        Site.objects.create(pk=idx+1, domain=domain, name=domain)
    print(f"✓ Created missing Site entries")
else:
    print(f"✓ Site entries OK ({Site.objects.count()} entries)")
ENDSHELL

        unset DJANGO_SKIP_POST_MIGRATE_SIGNALS
        echo "✓ Migrations up to date"
    fi  # ← closes the MIGRATIONS_COMPLETE if/else

else
    echo "=== OVS Backend Startup (passthrough) ==="
fi  # ← closes the RUN_INIT if/else

if [ "${RUN_INIT:-false}" = "true" ]; then
    echo ""
    echo "Running system checks..."
    python manage.py check
fi

echo ""
echo "Executing: $@"
exec "$@"