"""Unit tests for case social-profile extraction helpers."""

from __future__ import annotations

from django.test import TestCase

from ai_ml_services.social.case_profiles import extract_case_social_profiles
from apps.applications.models import VettingCase
from apps.users.models import User
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment, CandidateSocialProfile


class TestCaseSocialProfiles(TestCase):
    def setUp(self):
        self.internal_user = User.objects.create_user(
            email="social_case_internal@example.com",
            password="Pass1234!",
            first_name="Internal",
            last_name="Reviewer",
            user_type="internal",
        )
        self.applicant = User.objects.create_user(
            email="social_case_applicant@example.com",
            password="Pass1234!",
            first_name="Case",
            last_name="Applicant",
            user_type="applicant",
        )

    def test_extracts_candidate_social_profiles_and_consent(self):
        campaign = VettingCampaign.objects.create(name="Campaign", initiated_by=self.internal_user)
        candidate = Candidate.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="social_case_candidate@example.com",
            consent_ai_processing=True,
        )
        enrollment = CandidateEnrollment.objects.create(
            campaign=campaign,
            candidate=candidate,
            status="in_progress",
            metadata={
                "social_profiles": [
                    {"platform": "linkedin", "url": "https://linkedin.com/in/jane-doe"},
                    {"platform": "github", "url": "https://github.com/jane-doe"},
                ]
            },
        )

        CandidateSocialProfile.objects.create(
            candidate=candidate,
            platform="linkedin",
            url="https://linkedin.com/in/jane-doe",
            username="jane-doe",
            is_primary=True,
        )
        CandidateSocialProfile.objects.create(
            candidate=candidate,
            platform="github",
            url="https://github.com/jane-doe",
            username="jane-doe",
            is_primary=False,
        )

        case = VettingCase.objects.create(
            applicant=self.applicant,
            candidate_enrollment=enrollment,
            position_applied="Analyst",
            department="Ops",
            priority="medium",
            status="document_analysis",
        )

        profiles, consent = extract_case_social_profiles(case)

        self.assertTrue(consent)
        self.assertGreaterEqual(len(profiles), 2)
        platforms = {item.get("platform") for item in profiles}
        self.assertIn("linkedin", platforms)
        self.assertIn("github", platforms)

    def test_returns_empty_when_case_has_no_candidate_enrollment(self):
        case = VettingCase.objects.create(
            applicant=self.applicant,
            position_applied="Analyst",
            department="Ops",
            priority="medium",
            status="document_analysis",
        )

        profiles, consent = extract_case_social_profiles(case)

        self.assertEqual(profiles, [])
        self.assertFalse(consent)
