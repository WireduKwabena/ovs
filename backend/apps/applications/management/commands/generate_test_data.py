"""Generate lightweight development fixtures for the vetting pipeline."""

from __future__ import annotations

import random

from django.core.management.base import BaseCommand

from apps.applications.models import VettingCase
from apps.users.models import User
from apps.rubrics.models import RubricCriteria, VettingRubric


class Command(BaseCommand):
    help = "Generate test users, vetting cases, and a baseline rubric"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=10, help="Number of applicant users to create")
        parser.add_argument("--cases", type=int, default=20, help="Number of vetting cases to create")

    def handle(self, *args, **options):
        requested_users = options["users"]
        requested_cases = options["cases"]

        self.stdout.write("Creating test data...")

        admin, created = User.objects.get_or_create(
            email="admin@test.com",
            defaults={
                "first_name": "System",
                "last_name": "Admin",
                "user_type": "admin",
                "is_staff": True,
                "is_superuser": True,
                "email_verified": True,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Created admin user (admin@test.com)"))

        internal, created = User.objects.get_or_create(
            email="internal@test.com",
            defaults={
                "first_name": "Internal",
                "last_name": "Reviewer",
                "user_type": "internal",
                "is_staff": True,
                "email_verified": True,
            },
        )
        if created:
            internal.set_password("internal123")
            internal.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("Created internal reviewer (internal@test.com)"))

        applicants: list[User] = []
        for index in range(requested_users):
            user, user_created = User.objects.get_or_create(
                email=f"user{index}@test.com",
                defaults={
                    "first_name": "Test",
                    "last_name": f"User{index}",
                    "user_type": "applicant",
                    "phone_number": f"+233{random.randint(100000000, 999999999)}",
                    "email_verified": True,
                },
            )
            if user_created:
                user.set_password("test123")
                user.save(update_fields=["password"])
            applicants.append(user)
        self.stdout.write(self.style.SUCCESS(f"Prepared {len(applicants)} applicant users"))

        statuses = ["pending", "document_upload", "document_analysis", "under_review", "approved", "rejected"]
        priorities = ["low", "medium", "high", "urgent"]
        positions = [
            "Software Engineer",
            "Data Analyst",
            "People Operations Associate",
            "Finance Officer",
            "Operations Manager",
        ]

        created_cases = 0
        for _ in range(requested_cases):
            applicant = random.choice(applicants)
            VettingCase.objects.create(
                applicant=applicant,
                position_applied=random.choice(positions),
                department=random.choice(["Technology", "Operations", "Finance", "People Operations"]),
                status=random.choice(statuses),
                priority=random.choice(priorities),
                document_authenticity_score=round(random.uniform(60.0, 98.0), 2),
                consistency_score=round(random.uniform(55.0, 95.0), 2),
                fraud_risk_score=round(random.uniform(5.0, 55.0), 2),
            )
            created_cases += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created_cases} vetting cases"))

        rubric, rubric_created = VettingRubric.objects.get_or_create(
            name="Test General Rubric",
            defaults={
                "description": "Baseline rubric for local development fixtures.",
                "rubric_type": "general",
                "is_active": True,
                "is_default": True,
                "created_by": internal,
            },
        )

        if rubric_created or rubric.criteria.count() == 0:
            RubricCriteria.objects.get_or_create(
                rubric=rubric,
                name="Document Authenticity",
                defaults={
                    "description": "Assesses authenticity signals across submitted documents.",
                    "criteria_type": "document",
                    "scoring_method": "ai_score",
                    "weight": 40,
                    "minimum_score": 70,
                    "is_mandatory": True,
                    "display_order": 1,
                },
            )
            RubricCriteria.objects.get_or_create(
                rubric=rubric,
                name="Cross-document Consistency",
                defaults={
                    "description": "Checks consistency of identity/profile fields across documents.",
                    "criteria_type": "consistency",
                    "scoring_method": "ai_score",
                    "weight": 30,
                    "minimum_score": 65,
                    "is_mandatory": True,
                    "display_order": 2,
                },
            )
            RubricCriteria.objects.get_or_create(
                rubric=rubric,
                name="Interview Performance",
                defaults={
                    "description": "Scores candidate interview outcomes and communication quality.",
                    "criteria_type": "interview",
                    "scoring_method": "ai_score",
                    "weight": 30,
                    "minimum_score": 60,
                    "is_mandatory": False,
                    "display_order": 3,
                },
            )
            self.stdout.write(self.style.SUCCESS("Prepared baseline rubric criteria"))

        self.stdout.write(self.style.SUCCESS("Test data generation complete."))
        self.stdout.write("Login credentials:")
        self.stdout.write("  Admin: admin@test.com / admin123")
        self.stdout.write("  Internal Reviewer: internal@test.com / internal123")
        self.stdout.write("  Applicant: user0@test.com / test123")

