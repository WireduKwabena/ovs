# backend/apps/applications/management/commands/generate_test_data.py
# Management command to generate test data

from django.core.management.base import BaseCommand
from apps.auth_actions import User, AdminUser
from apps.applications.models import VettingCase
from apps.rubrics.models import VettingRubric, RubricCriteria
import random

class Command(BaseCommand):
    help = 'Generate test data for development'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=10,
            help='Number of test users to create'
        )
        parser.add_argument(
            '--applications',
            type=int,
            default=20,
            help='Number of test applications to create'
        )
    
    def handle(self, *args, **options):
        num_users = options['users']
        num_applications = options['applications']
        
        self.stdout.write('Creating test data...')
        
        # Create admin user
        admin, created = AdminUser.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@test.com',
                'role': 'admin'
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS('✓ Admin user created'))
        
        # Create HR manager
        hr_manager, created = AdminUser.objects.get_or_create(
            username='hr_manager',
            defaults={
                'email': 'hr@test.com',
                'role': 'hr_manager'
            }
        )
        if created:
            hr_manager.set_password('hr123')
            hr_manager.save()
            self.stdout.write(self.style.SUCCESS('✓ HR manager created'))
        
        # Create test users
        users = []
        for i in range(num_users):
            user, created = User.objects.get_or_create(
                email=f'user{i}@test.com',
                defaults={
                    'full_name': f'Test User {i}',
                    'phone_number': f'+233{random.randint(100000000, 999999999)}',
                    'date_of_birth': '1990-01-01'
                }
            )
            if created:
                user.set_password('test123')
                user.save()
                users.append(user)
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(users)} test users'))
        
        # Create test applications
        statuses = ['pending', 'under_review', 'approved', 'rejected']
        app_types = ['employment', 'background', 'credential', 'education']
        priorities = ['low', 'medium', 'high', 'urgent']
        
        applications = []
        for i in range(num_applications):
            user = random.choice(users) if users else User.objects.first()
            
            if user:
                app = VettingCase.objects.create(
                    applicant=user,
                    status=random.choice(statuses),
                    application_type=random.choice(app_types),
                    priority=random.choice(priorities),
                    consistency_score=random.uniform(60, 95),
                    fraud_risk_score=random.uniform(0.05, 0.3)
                )
                applications.append(app)
        
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(applications)} test applications'))
        
        # Create test rubric
        rubric, created = VettingRubric.objects.get_or_create(
            rubric_id='TEST-RUB-001',
            defaults={
                'name': 'Test Employment Rubric',
                'description': 'Test rubric for development',
                'rubric_type': 'employment',
                'created_by': hr_manager,
                'passing_score': 70,
                'auto_approve_threshold': 90,
                'auto_reject_threshold': 50,
                'status': 'active'
            }
        )
        
        if created:
            # Add criteria
            RubricCriteria.objects.create(
                rubric=rubric,
                name='Document Authenticity',
                criteria_type='document_authenticity',
                weight=40,
                minimum_score=70,
                is_mandatory=True,
                order=1
            )
            
            RubricCriteria.objects.create(
                rubric=rubric,
                name='Data Consistency',
                criteria_type='data_consistency',
                weight=30,
                minimum_score=60,
                is_mandatory=True,
                order=2
            )
            
            RubricCriteria.objects.create(
                rubric=rubric,
                name='Fraud Risk',
                criteria_type='fraud_score',
                weight=30,
                minimum_score=70,
                is_mandatory=False,
                order=3
            )
            
            self.stdout.write(self.style.SUCCESS('✓ Created test rubric with criteria'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Test data generation complete!'))
        self.stdout.write('Login credentials:')
        self.stdout.write('  Admin: admin / admin123')
        self.stdout.write('  HR Manager: hr_manager / hr123')
        self.stdout.write('  Test User: user0@test.com / test123')