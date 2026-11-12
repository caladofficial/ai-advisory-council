"""Quota Manager and strict Zero-Paid-Use cost policy enforcement."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from app.config import get_providers_config, get_settings


class CostPolicyViolationError(RuntimeError):
    """Raised if a call attempts to use a paid model or violates zero_paid mode."""


class QuotaManager:
    """Tracks per-provider RPM/RPD budgets and cooldown windows in-process."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._minute_requests: dict[str, deque[float]] = defaultdict(deque)
        self._daily_counts: dict[str, int] = defaultdict(int)
        self._day_marker: str = time.strftime("%Y-%m-%d", time.gmtime())
        self._cooldown_until: dict[str, float] = {}

    def _reset_day_if_needed(self) -> None:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if today != self._day_marker:
            self._day_marker = today
            self._daily_counts.clear()

    def assert_zero_paid_allowed(self, provider: str, model_id: str) -> None:
        """Guarantee that no paid provider or paid OpenRouter route is ever called in zero_paid mode."""
        settings = get_settings()
        if settings.cost_policy_mode != "zero_paid" and settings.allow_paid_providers:
            return

        providers = get_providers_config().get("providers", {})
        cfg = providers.get(provider)
        if cfg is None and provider != "ollama":
            raise CostPolicyViolationError(
                f"Provider {provider!r} is not verified in zero_paid providers.yaml"
            )
        if cfg:
            if not cfg.get("is_free_tier", False):
                raise CostPolicyViolationError(f"Provider {provider!r} is not marked as free tier")
            if cfg.get("requires_credit_card", False) and not settings.allow_credit_card_fallback:
                raise CostPolicyViolationError(
                    f"Provider {provider!r} requires credit card fallback, forbidden by zero_paid policy"
                )
            req_suffix = cfg.get("free_model_suffix_required")
            if req_suffix and not model_id.endswith(req_suffix):
                raise CostPolicyViolationError(
                    f"Model {model_id!r} on {provider!r} must carry {req_suffix!r} in zero_paid mode"
                )

    def can_dispatch(self, provider: str) -> tuple[bool, str]:
        """Return whether provider currently has free quota & is outside cooldown."""
        now = time.time()
        providers = get_providers_config().get("providers", {})
        cfg = providers.get(provider, {})
        rpm_limit = int(cfg.get("default_rpm", 30))
        rpd_limit = int(cfg.get("default_rpd", 1000))

        with self._lock:
            self._reset_day_if_needed()
            cooldown = self._cooldown_until.get(provider, 0.0)
            if now < cooldown:
                return False, f"Provider {provider} in cooldown for {cooldown - now:.1f}s"

            q = self._minute_requests[provider]
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= rpm_limit:
                return False, f"RPM limit ({rpm_limit}) reached for {provider}"

            if self._daily_counts[provider] >= rpd_limit and not get_settings().allow_over_quota_requests:
                return False, f"Daily free quota ({rpd_limit}) reached for {provider}"
        return True, "ok"

    def record_request(self, provider: str) -> None:
        now = time.time()
        with self._lock:
            self._reset_day_if_needed()
            self._minute_requests[provider].append(now)
            self._daily_counts[provider] += 1

    def trigger_cooldown(self, provider: str, seconds: float = 30.0) -> None:
        with self._lock:
            self._cooldown_until[provider] = time.time() + max(5.0, seconds)

    def snapshot_usage(self) -> dict[str, int]:
        with self._lock:
            self._reset_day_if_needed()
            return dict(self._daily_counts)


quota_manager = QuotaManager()
