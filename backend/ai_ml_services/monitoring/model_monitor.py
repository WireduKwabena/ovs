"""Model performance monitoring with Redis or in-memory fallback."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import statistics
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    redis = None

try:
    from django.conf import settings as django_settings
except Exception:  # pragma: no cover - used outside Django context
    django_settings = None

logger = logging.getLogger(__name__)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    if np is not None:
        return float(np.mean(values))
    return float(statistics.fmean(values))


def _min(values: list[float]) -> float:
    if not values:
        return 0.0
    if np is not None:
        return float(np.min(values))
    return float(min(values))


def _max(values: list[float]) -> float:
    if not values:
        return 0.0
    if np is not None:
        return float(np.max(values))
    return float(max(values))


def _uniform(low: float, high: float) -> float:
    if np is not None:
        return float(np.random.uniform(low, high))
    return float(random.uniform(low, high))


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _get_setting(name: str, default: Any = None) -> Any:
    if django_settings is not None:
        try:
            if getattr(django_settings, "configured", False) and hasattr(
                django_settings, name
            ):
                return getattr(django_settings, name)
        except Exception:
            pass
    return os.getenv(name, default)


def _with_redis_db(redis_url: str, db: int) -> str:
    try:
        parsed = urlparse(redis_url)
        if parsed.scheme not in {"redis", "rediss"}:
            return redis_url
        return urlunparse(parsed._replace(path=f"/{db}"))
    except Exception:
        return redis_url


class ModelMonitor:
    """Monitor model predictions, latency, and errors."""

    def __init__(
        self,
        window_size: Optional[int] = None,
        min_confidence_threshold: Optional[float] = None,
        max_processing_time: Optional[float] = None,
        drift_window_size: Optional[int] = None,
        drift_threshold: Optional[float] = None,
        redis_url: Optional[str] = None,
        use_redis: Optional[bool] = None,
        enabled: Optional[bool] = None,
        redis_socket_timeout: float = 1.5,
    ):
        self.window_size = int(
            window_size
            if window_size is not None
            else _get_setting("AI_ML_MONITOR_WINDOW_SIZE", 1000)
        )
        self.min_confidence_threshold = float(
            min_confidence_threshold
            if min_confidence_threshold is not None
            else _get_setting("AI_ML_MONITOR_MIN_CONFIDENCE_THRESHOLD", 0.7)
        )
        self.max_processing_time = float(
            max_processing_time
            if max_processing_time is not None
            else _get_setting("AI_ML_MONITOR_MAX_PROCESSING_TIME", 5.0)
        )
        self.drift_window_size = int(
            drift_window_size
            if drift_window_size is not None
            else _get_setting("AI_ML_MONITOR_DRIFT_WINDOW_SIZE", 100)
        )
        self.drift_threshold = float(
            drift_threshold
            if drift_threshold is not None
            else _get_setting("AI_ML_MONITOR_DRIFT_THRESHOLD", 0.1)
        )
        self.redis_socket_timeout = float(redis_socket_timeout)

        default_use_redis = _as_bool(_get_setting("USE_REDIS", True), True)
        self.enabled = _as_bool(
            enabled if enabled is not None else _get_setting("AI_ML_MONITOR_ENABLED", True),
            True,
        )
        self.use_redis = _as_bool(
            use_redis
            if use_redis is not None
            else _get_setting("AI_ML_MONITOR_USE_REDIS", default_use_redis),
            default_use_redis,
        )

        base_redis_url = str(_get_setting("REDIS_URL", "redis://localhost:6379/0"))
        default_monitor_redis = _with_redis_db(base_redis_url, 2)
        self.redis_url = redis_url or str(
            _get_setting("AI_ML_MONITOR_REDIS_URL", default_monitor_redis)
        )

        self.redis_client = None
        self.backend = "memory"

        # In-memory fallback structures
        self._predictions_mem: list[Any] = []
        self._confidences_mem: list[float] = []
        self._processing_times_mem: list[float] = []
        self._errors_mem: list[Dict[str, Any]] = []

        if not self.enabled:
            logger.info("AI model monitoring is disabled by configuration.")
            return

        if not self.use_redis:
            logger.info("AI model monitor Redis backend disabled; using in-memory backend.")
            return

        if redis is None:
            logger.warning(
                "redis package is not installed; AI model monitor will run in-memory."
            )
            return

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                socket_connect_timeout=self.redis_socket_timeout,
                socket_timeout=self.redis_socket_timeout,
                retry_on_timeout=True,
            )
            self.redis_client.ping()
            self.backend = "redis"
            logger.info("AI model monitor connected to Redis: %s", self.redis_url)
        except Exception as exc:  # pragma: no cover - connection depends on env
            logger.warning(
                "AI model monitor Redis unavailable (%s). Falling back to in-memory backend.",
                exc,
            )
            self.redis_client = None
            self.backend = "memory"

    @staticmethod
    def _get_current_timestamp() -> float:
        return time.time()

    def log_prediction(
        self,
        prediction: Any,
        confidence: float,
        processing_time: float,
        model_name: str = "default",
    ) -> None:
        """Log a model prediction event."""
        if not self.enabled:
            return

        timestamp = self._get_current_timestamp()
        event_suffix = str(time.time_ns())

        if self.redis_client:
            try:
                conf_member = f"{event_suffix}:{float(confidence)}"
                proc_member = f"{event_suffix}:{float(processing_time)}"
                pred_member = f"{event_suffix}:{str(prediction)}"

                self.redis_client.zadd(
                    f"monitor:{model_name}:confidences", {conf_member: timestamp}
                )
                self.redis_client.zadd(
                    f"monitor:{model_name}:processing_times", {proc_member: timestamp}
                )
                self.redis_client.zadd(
                    f"monitor:{model_name}:predictions", {pred_member: timestamp}
                )

                # Keep only latest `window_size` entries.
                self.redis_client.zremrangebyrank(
                    f"monitor:{model_name}:confidences", 0, -self.window_size - 1
                )
                self.redis_client.zremrangebyrank(
                    f"monitor:{model_name}:processing_times", 0, -self.window_size - 1
                )
                self.redis_client.zremrangebyrank(
                    f"monitor:{model_name}:predictions", 0, -self.window_size - 1
                )
            except Exception as exc:  # pragma: no cover - connection depends on env
                logger.warning(
                    "AI model monitor Redis write failed (%s). Using in-memory fallback.",
                    exc,
                )
                self._log_prediction_in_memory(prediction, confidence, processing_time)
        else:
            self._log_prediction_in_memory(prediction, confidence, processing_time)

        self._check_alerts(confidence, processing_time, model_name)

    def _log_prediction_in_memory(
        self, prediction: Any, confidence: float, processing_time: float
    ) -> None:
        self._predictions_mem.append(prediction)
        self._confidences_mem.append(float(confidence))
        self._processing_times_mem.append(float(processing_time))
        if len(self._predictions_mem) > self.window_size:
            self._predictions_mem.pop(0)
            self._confidences_mem.pop(0)
            self._processing_times_mem.pop(0)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        model_name: str = "default",
    ) -> None:
        """Log an error event."""
        if not self.enabled:
            return

        error_event = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": error_message,
        }
        if self.redis_client:
            try:
                self.redis_client.lpush(
                    f"monitor:{model_name}:errors", json.dumps(error_event)
                )
                self.redis_client.ltrim(
                    f"monitor:{model_name}:errors", 0, self.window_size - 1
                )
            except Exception as exc:  # pragma: no cover - connection depends on env
                logger.warning(
                    "AI model monitor Redis error write failed (%s). Using in-memory fallback.",
                    exc,
                )
                self._log_error_in_memory(error_type, error_message)
        else:
            self._log_error_in_memory(error_type, error_message)

    def _log_error_in_memory(self, error_type: str, error_message: str) -> None:
        self._errors_mem.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": error_type,
                "message": error_message,
            }
        )
        if len(self._errors_mem) > self.window_size:
            self._errors_mem.pop(0)

    def _check_alerts(self, confidence: float, processing_time: float, model_name: str) -> None:
        if confidence < self.min_confidence_threshold:
            logger.warning(
                "[%s] Low confidence prediction alert: %.3f (threshold %.3f)",
                model_name,
                confidence,
                self.min_confidence_threshold,
            )

        if processing_time > self.max_processing_time:
            logger.warning(
                "[%s] High processing time alert: %.3fs (threshold %.3fs)",
                model_name,
                processing_time,
                self.max_processing_time,
            )

    def get_metrics(self, model_name: str = "default") -> Dict[str, Any]:
        """Return current performance metrics."""
        if not self.enabled:
            return {"status": "disabled", "model_name": model_name, "backend": "disabled"}

        if self.redis_client:
            try:
                confidences_data = self._parse_float_members(
                    self.redis_client.zrange(
                        f"monitor:{model_name}:confidences", 0, -1, withscores=False
                    )
                )
                processing_times_data = self._parse_float_members(
                    self.redis_client.zrange(
                        f"monitor:{model_name}:processing_times", 0, -1, withscores=False
                    )
                )
                errors_data = [
                    json.loads(item.decode() if isinstance(item, bytes) else item)
                    for item in self.redis_client.lrange(f"monitor:{model_name}:errors", 0, 4)
                ]
            except Exception as exc:  # pragma: no cover - connection depends on env
                logger.warning(
                    "AI model monitor Redis read failed (%s). Returning in-memory metrics.",
                    exc,
                )
                return self._get_metrics_in_memory(model_name)
        else:
            return self._get_metrics_in_memory(model_name)

        if not confidences_data:
            return {"status": "no_data", "model_name": model_name, "backend": self.backend}

        return {
            "model_name": model_name,
            "backend": self.backend,
            "total_predictions": len(confidences_data),
            "avg_confidence": _mean(confidences_data),
            "min_confidence": _min(confidences_data),
            "max_confidence": _max(confidences_data),
            "avg_processing_time": _mean(processing_times_data)
            if processing_times_data
            else 0.0,
            "max_processing_time": _max(processing_times_data)
            if processing_times_data
            else 0.0,
            "error_count": len(errors_data),
            "recent_errors": errors_data,
        }

    def _get_metrics_in_memory(self, model_name: str) -> Dict[str, Any]:
        if not self._confidences_mem:
            return {"status": "no_data", "model_name": model_name, "backend": "memory"}

        return {
            "model_name": model_name,
            "backend": "memory",
            "total_predictions": len(self._confidences_mem),
            "avg_confidence": _mean(self._confidences_mem),
            "min_confidence": _min(self._confidences_mem),
            "max_confidence": _max(self._confidences_mem),
            "avg_processing_time": _mean(self._processing_times_mem)
            if self._processing_times_mem
            else 0.0,
            "max_processing_time": _max(self._processing_times_mem)
            if self._processing_times_mem
            else 0.0,
            "error_count": len(self._errors_mem),
            "recent_errors": self._errors_mem[-5:],
        }

    def check_data_drift(self, model_name: str = "default") -> Dict[str, Any]:
        """Detect potential confidence drift via historical vs recent averages."""
        if not self.enabled:
            return {"status": "disabled", "model_name": model_name, "drift_detected": False}

        if self.redis_client:
            try:
                confidences_data = self._parse_float_members(
                    self.redis_client.zrange(
                        f"monitor:{model_name}:confidences", 0, -1, withscores=False
                    )
                )
            except Exception as exc:  # pragma: no cover - connection depends on env
                logger.warning(
                    "AI model monitor Redis read failed during drift check (%s). Using in-memory data.",
                    exc,
                )
                confidences_data = self._confidences_mem
        else:
            confidences_data = self._confidences_mem

        if len(confidences_data) < self.drift_window_size * 2:
            return {
                "drift_detected": False,
                "reason": "Insufficient data",
                "model_name": model_name,
            }

        recent = confidences_data[-self.drift_window_size :]
        historical = confidences_data[: -self.drift_window_size]

        recent_avg = _mean(recent)
        historical_avg = _mean(historical)
        confidence_drop = historical_avg - recent_avg
        drift_detected = confidence_drop > self.drift_threshold

        if drift_detected:
            logger.warning(
                "[%s] Data drift detected (historical %.3f -> recent %.3f).",
                model_name,
                historical_avg,
                recent_avg,
            )

        return {
            "model_name": model_name,
            "drift_detected": drift_detected,
            "recent_avg_confidence": recent_avg,
            "historical_avg_confidence": historical_avg,
            "confidence_drop": confidence_drop,
            "recommendation": "Retrain model" if drift_detected else "Model performing well",
        }

    @staticmethod
    def _parse_float_members(members: list[Any]) -> list[float]:
        values: list[float] = []
        for member in members:
            text = member.decode() if isinstance(member, bytes) else str(member)
            if ":" in text:
                text = text.rsplit(":", 1)[1]
            try:
                values.append(float(text))
            except ValueError:
                continue
        return values


model_monitor = ModelMonitor()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run model monitor diagnostics.")
    parser.add_argument(
        "--window_size",
        type=int,
        default=1000,
        help="Number of events to keep in monitoring window.",
    )
    parser.add_argument(
        "--min_confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for alerts.",
    )
    parser.add_argument(
        "--max_proc_time",
        type=float,
        default=5.0,
        help="Maximum processing time threshold for alerts (seconds).",
    )
    parser.add_argument(
        "--drift_window",
        type=int,
        default=100,
        help="Window size for data drift detection.",
    )
    parser.add_argument(
        "--drift_threshold",
        type=float,
        default=0.1,
        help="Threshold for average confidence drop to detect drift.",
    )
    parser.add_argument(
        "--redis_url",
        type=str,
        default=None,
        help="Redis URL for monitoring (optional).",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="default",
        help="Name of the model to monitor.",
    )
    parser.add_argument(
        "--use_redis",
        type=str,
        default=None,
        help="Override monitor redis backend usage (true/false).",
    )
    parser.add_argument(
        "--enabled",
        type=str,
        default=None,
        help="Override monitor enabled state (true/false).",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    monitor = ModelMonitor(
        window_size=args.window_size,
        min_confidence_threshold=args.min_confidence,
        max_processing_time=args.max_proc_time,
        drift_window_size=args.drift_window,
        drift_threshold=args.drift_threshold,
        redis_url=args.redis_url,
        use_redis=_as_bool(args.use_redis, True) if args.use_redis is not None else None,
        enabled=_as_bool(args.enabled, True) if args.enabled is not None else None,
    )

    logger.info(
        "Initialized ModelMonitor for '%s' (backend=%s).",
        args.model_name,
        monitor.backend,
    )

    for idx in range(10):
        conf = _uniform(0.6, 0.95)
        proc_time = _uniform(0.1, 6.0)
        monitor.log_prediction(f"pred_{idx}", conf, proc_time, model_name=args.model_name)
        if idx % 3 == 0:
            monitor.log_error(
                "SimulatedError",
                f"Error during prediction {idx}",
                model_name=args.model_name,
            )

    logger.info("Current metrics: %s", monitor.get_metrics(model_name=args.model_name))
    logger.info("Drift status: %s", monitor.check_data_drift(model_name=args.model_name))


if __name__ == "__main__":
    main()
