"""
Initialize the database for django-tenants. 
This handles the chicken-egg problem of migrations depending on tenant tables.
"""
from django.core.management.base import BaseCommand
from django.db import connection
import subprocess
import sys
import os


class Command(BaseCommand):
    help = "Initialize database with proper django-tenants setup"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Database Initialization ===\n"))

        # Step 1: Create basic Django tables using syncdb
        self.stdout.write("Step 1: Synchronizing base Django tables...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
            
            # Use raw SQL to create tenants tables first (bypass migrations)
            self.stdout.write("  Creating tenants schema...")
            result = subprocess.run(
                [sys.executable, 'manage.py', 'sqlmigrate', 'tenants', '0001_initial'],
                capture_output=True, text=True, cwd=os.getcwd()
            )
            if result.returncode == 0:
                sql = result.stdout
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                self.stdout.write(self.style.SUCCESS("    ✓ Tenants schema created"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    ⚠ {str(e)[:100]}"))

        # Step 2: Create public organization entry
        self.stdout.write("\nStep 2: Creating public organization...")
        try:
            from apps.tenants.models import Organization
            from django_tenants.utils import get_public_schema_name

            public_schema_name = get_public_schema_name()
            org, created = Organization.objects.get_or_create(
                schema_name=public_schema_name,
                defaults={'name': 'Public Schema', 'code': 'public', 'is_active': True}
            )
            self.stdout.write(self.style.SUCCESS(f"✓ Public org: {org}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠ {e}"))

        # Step 3: Run migrations app-by-app in order (using migrate_schemas to handle tenants)
        self.stdout.write("\nStep 3: Running migrations in dependency order...")
        
        migration_order = [
            'contenttypes',
            'auth', 
            'users',
            'sites',
            'sessions',
            'django_celery_beat',
            'django_celery_results',
            'rest_framework_simplejwt.token_blacklist',
            'admin',
            'core',
            'authentication',
            'applications',
        ]

        for app in migration_order:
            try:
                self.stdout.write(f"  {app}...", ending='')
                result = subprocess.run(
                    [sys.executable, 'manage.py', 'migrate', app, '--noinput'],
                    capture_output=True, text=True, timeout=30, cwd=os.getcwd()
                )
                if result.returncode == 0:
                    self.stdout.write(self.style.SUCCESS(" ✓"))
                else:
                    self.stdout.write(self.style.WARNING(f" ⚠\n    {result.stderr[:100]}"))
            except subprocess.TimeoutExpired:
                self.stdout.write(self.style.WARNING(f" ⚠ (timeout)"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f" ⚠ ({str(e)[:50]})"))

        # Final: Migrate everything to catch remaining apps
        self.stdout.write("\n\n  Running final migration pass...")
        try:
            result = subprocess.run(
                [sys.executable, 'manage.py', 'migrate', '--noinput'],
                capture_output=True, text=True, timeout=60, cwd=os.getcwd()
            )
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("✓ All migrations complete"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Final pass incomplete:\n{result.stderr[:200]}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Final pass failed: {e}"))

        self.stdout.write(self.style.SUCCESS("\n✓ Database initialization complete!"))

    def _create_demo_tenants(self):
        """Create demo tenant organizations and domains."""
        from apps.tenants.models import Organization, Domain
        from django_celery_beat.models import PeriodicTask
        
        demo_tenants = [
            {'name': 'Demo Organization', 'code': 'demo', 'schema': 'demo_schema'},
        ]
        
        for tenant_config in demo_tenants:
            org, created = Organization.objects.get_or_create(
                code=tenant_config['code'],
                defaults={
                    'name': tenant_config['name'],
                    'schema_name': tenant_config['schema'],
                    'is_active': True,
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created demo tenant: {org.name}"))
                
                # Create domain
                domain, created = Domain.objects.get_or_create(
                    tenant=org,
                    defaults={'domain': f"{tenant_config['code']}.localhost"}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"  - Domain: {domain.domain}"))
