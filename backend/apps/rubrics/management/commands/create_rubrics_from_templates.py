# backend/apps/rubrics/management/commands/create_rubrics_from_templates.py
# Command to create rubrics from templates

from django.core.management.base import BaseCommand
from apps.rubrics.templates import RUBRIC_TEMPLATES, create_rubric_from_template
from apps.auth_actions import AdminUser

class Command(BaseCommand):
    help = 'Create rubrics from pre-defined templates'
    
    def handle(self, *args, **options):
        # Get or create HR manager
        hr_manager = AdminUser.objects.filter(role='hr_manager').first()
        
        if not hr_manager:
            self.stdout.write(self.style.ERROR('No HR manager found. Creating default...'))
            hr_manager = AdminUser.objects.create_user(
                username='hr_manager',
                email='hr@system.com',
                password='hr123',
                role='hr_manager'
            )
        
        self.stdout.write('Creating rubrics from templates...')
        
        created_count = 0
        for template_key in RUBRIC_TEMPLATES.keys():
            try:
                rubric = create_rubric_from_template(
                    template_key,
                    created_by=hr_manager
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {rubric.name}')
                )
                created_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to create {template_key}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Successfully created {created_count} rubrics')
        )