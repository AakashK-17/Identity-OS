import os
from contextlib import contextmanager


try:
    import sentry_sdk
except Exception:  # pragma: no cover - monitoring must never block app startup
    sentry_sdk = None


_INITIALIZED = False


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def init_monitoring(service_name: str = "hone-backend") -> bool:
    global _INITIALIZED
    if _INITIALIZED:
        return True
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn or sentry_sdk is None:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
        release=os.environ.get("SENTRY_RELEASE") or os.environ.get("RENDER_GIT_COMMIT") or None,
        traces_sample_rate=_float_env("SENTRY_TRACES_SAMPLE_RATE", 0.2),
        profiles_sample_rate=_float_env("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        send_default_pii=False,
        enable_logs=True,
    )
    sentry_sdk.set_tag("service", service_name)
    _INITIALIZED = True
    return True


def monitoring_enabled() -> bool:
    return bool(_INITIALIZED and sentry_sdk is not None)


def set_monitoring_context(**values) -> None:
    if not monitoring_enabled():
        return
    for key, value in values.items():
        if value is not None:
            sentry_sdk.set_tag(key, str(value)[:120])


@contextmanager
def monitor_transaction(name: str, op: str = "task", **data):
    if not monitoring_enabled():
        yield None
        return
    with sentry_sdk.start_transaction(name=name, op=op) as transaction:
        for key, value in data.items():
            if value is not None:
                transaction.set_data(key, value)
        yield transaction


@contextmanager
def monitor_span(op: str, description: str, **data):
    if not monitoring_enabled():
        yield None
        return
    with sentry_sdk.start_span(op=op, description=description) as span:
        for key, value in data.items():
            if value is not None:
                span.set_data(key, value)
        yield span


def capture_monitoring_exception(error: Exception, **data) -> None:
    if not monitoring_enabled():
        return
    with sentry_sdk.push_scope() as scope:
        for key, value in data.items():
            if value is not None:
                scope.set_extra(key, value)
        sentry_sdk.capture_exception(error)


def add_monitoring_breadcrumb(message: str, category: str = "hone", level: str = "info", **data) -> None:
    if not monitoring_enabled():
        return
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data={key: value for key, value in data.items() if value is not None},
    )
