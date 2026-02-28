import uuid

from django.utils import timezone

from .base import BackgroundCheckProvider, ProviderResult, ProviderSubmission


class MockBackgroundCheckProvider(BackgroundCheckProvider):
    key = "mock"

    def submit_check(self, check) -> ProviderSubmission:
        external_reference = f"mock-{check.check_type}-{uuid.uuid4().hex[:10]}"
        return ProviderSubmission(
            status="submitted",
            external_reference=external_reference,
            raw_payload={
                "provider": self.key,
                "external_reference": external_reference,
                "submitted": True,
            },
        )

    def refresh_check(self, check) -> ProviderResult:
        score_map = {
            "kyc_aml": 93.0,
            "employment": 82.0,
            "education": 85.0,
            "criminal": 74.0,
            "identity": 88.0,
        }
        score = score_map.get(check.check_type, 80.0)

        if score >= 85:
            risk_level = "low"
            recommendation = "clear"
        elif score >= 70:
            risk_level = "medium"
            recommendation = "review"
        else:
            risk_level = "high"
            recommendation = "review"

        return ProviderResult(
            status="completed",
            score=score,
            risk_level=risk_level,
            recommendation=recommendation,
            completed_at=timezone.now(),
            raw_payload={
                "provider": self.key,
                "external_reference": check.external_reference,
                "status": "completed",
                "score": score,
                "risk_level": risk_level,
                "recommendation": recommendation,
            },
        )

    def parse_webhook(self, payload: dict[str, object]) -> ProviderResult:
        status = str(payload.get("status", "completed")).lower()

        score_value = payload.get("score")
        try:
            score = float(score_value) if score_value is not None else None
        except (TypeError, ValueError):
            score = None

        risk_level = payload.get("risk_level")
        recommendation = payload.get("recommendation")

        return ProviderResult(
            status=status,
            score=score,
            risk_level=str(risk_level).lower() if risk_level else None,
            recommendation=str(recommendation).lower() if recommendation else None,
            completed_at=timezone.now() if status in {"completed", "manual_review"} else None,
            raw_payload={k: v for k, v in payload.items()},
        )
