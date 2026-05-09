from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import logging
import time
import httpx

from .base import BackgroundCheckProvider, ProviderResult, ProviderSubmission


logger = logging.getLogger(__name__)


class HttpBackgroundCheckProvider(BackgroundCheckProvider):
    key = "http"

    def _base_url(self) -> str:
        base_url = str(getattr(settings, "BACKGROUND_CHECK_HTTP_BASE_URL", "")).strip().rstrip("/")
        if not base_url:
            raise ValueError("BACKGROUND_CHECK_HTTP_BASE_URL is required for http provider.")
        return base_url

    def _timeout(self) -> float:
        return float(getattr(settings, "BACKGROUND_CHECK_HTTP_TIMEOUT", 15.0))

    def _max_retries(self) -> int:
        return max(0, int(getattr(settings, "BACKGROUND_CHECK_HTTP_MAX_RETRIES", 2)))

    def _retry_backoff_seconds(self) -> float:
        return max(0.0, float(getattr(settings, "BACKGROUND_CHECK_HTTP_RETRY_BACKOFF_SECONDS", 0.75)))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = str(getattr(settings, "BACKGROUND_CHECK_HTTP_API_KEY", "")).strip()
        if api_key:
            auth_header = str(getattr(settings, "BACKGROUND_CHECK_HTTP_AUTH_HEADER", "Authorization")).strip()
            auth_scheme = str(getattr(settings, "BACKGROUND_CHECK_HTTP_AUTH_SCHEME", "Bearer")).strip()
            headers[auth_header] = f"{auth_scheme} {api_key}" if auth_scheme else api_key
        return headers

    def _submit_url(self) -> str:
        path = str(getattr(settings, "BACKGROUND_CHECK_HTTP_SUBMIT_PATH", "/checks")).strip()
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url()}{path}"

    def _refresh_url(self, external_reference: str) -> str:
        template = str(
            getattr(
                settings,
                "BACKGROUND_CHECK_HTTP_REFRESH_PATH_TEMPLATE",
                "/checks/{external_reference}",
            )
        ).strip()
        path = template.format(external_reference=external_reference)
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url()}{path}"

    @staticmethod
    def _parse_json(response) -> dict:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return payload if isinstance(payload, dict) else {"value": payload}

    @staticmethod
    def _to_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_datetime(value):
        if not value:
            return None
        if isinstance(value, str):
            parsed = parse_datetime(value)
            if parsed is not None:
                return parsed
        if hasattr(value, "isoformat"):
            return value
        return None

    def _request_with_retries(self, *, method: str, url: str, **kwargs):
        max_attempts = self._max_retries() + 1
        delay = self._retry_backoff_seconds()
        last_error = None

        for attempt in range(1, max_attempts + 1):
            start = time.monotonic()
            try:
                response = httpx.request(method, url, **kwargs)
                response.raise_for_status()
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "background_check.provider_call provider=%s method=%s status=%s attempt=%s duration_ms=%s",
                    self.key,
                    method,
                    response.status_code,
                    attempt,
                    duration_ms,
                )
                return response
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response is not None else 0
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning(
                    "background_check.provider_call_error provider=%s method=%s status=%s attempt=%s duration_ms=%s",
                    self.key,
                    method,
                    status_code,
                    attempt,
                    duration_ms,
                )
                retryable = status_code >= 500
                if not retryable or attempt >= max_attempts:
                    raise
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                last_error = exc
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.warning(
                    "background_check.provider_call_error provider=%s method=%s status=network_error attempt=%s duration_ms=%s",
                    self.key,
                    method,
                    attempt,
                    duration_ms,
                )
                if attempt >= max_attempts:
                    raise

            time.sleep(delay * attempt)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected provider HTTP retry state.")

    def submit_check(self, check) -> ProviderSubmission:
        source_payload = check.request_payload if isinstance(check.request_payload, dict) else {}
        payload = dict(source_payload)
        payload.setdefault("check_type", check.check_type)
        payload.setdefault("case_id", check.case.case_id)
        payload.setdefault("internal_check_id", str(check.id))
        payload.setdefault(
            "subject",
            {
                "email": check.case.applicant.email,
                "first_name": check.case.applicant.first_name,
                "last_name": check.case.applicant.last_name,
            },
        )

        response = self._request_with_retries(
            method="POST",
            url=self._submit_url(),
            json=payload,
            headers=self._headers(),
            timeout=self._timeout(),
        )
        data = self._parse_json(response)

        external_reference = data.get("external_reference") or data.get("reference") or data.get("id")
        if not external_reference:
            raise ValueError("Provider submit response missing external_reference.")

        status = str(data.get("status", "submitted")).lower()
        return ProviderSubmission(
            status=status,
            external_reference=str(external_reference),
            raw_payload=data,
        )

    def refresh_check(self, check) -> ProviderResult:
        if not check.external_reference:
            raise ValueError("Cannot refresh check without external_reference.")

        response = self._request_with_retries(
            method="GET",
            url=self._refresh_url(check.external_reference),
            headers=self._headers(),
            timeout=self._timeout(),
        )
        data = self._parse_json(response)

        status = str(data.get("status", "in_progress")).lower()
        return ProviderResult(
            status=status,
            raw_payload=data,
            score=self._to_float(data.get("score")),
            risk_level=data.get("risk_level"),
            recommendation=data.get("recommendation"),
            completed_at=self._to_datetime(data.get("completed_at"))
            or (timezone.now() if status in {"completed", "manual_review"} else None),
        )

    def parse_webhook(self, payload: dict[str, object]) -> ProviderResult:
        status = str(payload.get("status", "completed")).lower()
        return ProviderResult(
            status=status,
            raw_payload={k: v for k, v in payload.items()},
            score=self._to_float(payload.get("score")),
            risk_level=payload.get("risk_level"),
            recommendation=payload.get("recommendation"),
            completed_at=self._to_datetime(payload.get("completed_at"))
            or (timezone.now() if status in {"completed", "manual_review"} else None),
        )
