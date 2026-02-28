"""Unit tests for social profile checker."""

from __future__ import annotations

from django.test import SimpleTestCase

from ai_ml_services.social.profile_checker import SocialProfileChecker


class TestSocialProfileChecker(SimpleTestCase):
    def test_requires_consent_when_enabled(self):
        checker = SocialProfileChecker(require_consent=True, verify_urls=False)

        result = checker.check_profiles(
            profiles=[{"platform": "linkedin", "url": "https://linkedin.com/in/user"}],
            consent_provided=False,
            case_id="CASE-SOC-4",
        )

        self.assertEqual(result["case_id"], "CASE-SOC-4")
        self.assertFalse(result["consent_provided"])
        self.assertEqual(result["recommendation"], "MANUAL_REVIEW")
        self.assertFalse(result["automated_decision_allowed"])
        codes = {item["code"] for item in result["decision_constraints"]}
        self.assertIn("social_consent_missing", codes)

    def test_valid_profile_with_consent(self):
        checker = SocialProfileChecker(require_consent=True, verify_urls=False)

        result = checker.check_profiles(
            profiles=[{"platform": "linkedin", "url": "https://linkedin.com/in/jane-doe"}],
            consent_provided=True,
            case_id="CASE-SOC-5",
        )

        self.assertEqual(result["profiles_checked"], 1)
        self.assertEqual(result["profiles"][0]["platform"], "linkedin")
        self.assertEqual(result["profiles"][0]["username"], "jane-doe")
        self.assertFalse(result["automated_decision_allowed"])
        self.assertEqual(result["recommendation"], "MANUAL_REVIEW")

    def test_unknown_platform_is_flagged(self):
        checker = SocialProfileChecker(require_consent=False, verify_urls=False)

        result = checker.check_profiles(
            profiles=[{"platform": "myspace", "username": "user_name"}],
            consent_provided=True,
            case_id="CASE-SOC-6",
        )

        self.assertEqual(result["profiles_checked"], 1)
        findings = set(result["profiles"][0]["findings"])
        self.assertIn("platform_not_allowed", findings)