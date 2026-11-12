"""Tracing + metering: OpenTelemetry spans when an OTLP endpoint is configured, otherwise a zero-cost no-op.

Every decorated call is also metered into ``tool_calls`` (duration / success) for the usage dashboard and chargeback.
"""
from __future__ import annotations

import contextvars
import functools
import inspect
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])
current_actor: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_actor", default=None)
current_role: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_role", default=None)
_tracer: Any = None
_initialised = False


def init_tracing() -> Optional[Any]:
    """Configure an OTLP exporter once if ``NEXUS_OTEL_EXPORTER_OTLP_ENDPOINT`` is set (Azure Monitor / Langfuse / Jaeger)."""
    global _tracer, _initialised
    if _initialised:
        return _tracer
    _initialised = True
    from app.config import get_settings

    endpoint = get_settings().otel_exporter_otlp_endpoint
    if not endpoint:
        return None
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

        provider = TracerProvider(resource=Resource.create({"service.name": "jnj-graphrag-nexus"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("nexus")
        logger.info("OpenTelemetry tracing enabled -> %s", endpoint)
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("OpenTelemetry exporter unavailable (%s); tracing disabled", exc)
        _tracer = None
    return _tracer


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Dict[str, Any]]:
    tracer = init_tracing()
    record: Dict[str, Any] = {"name": name, **attributes}
    if tracer is None:
        yield record
        return
    with tracer.start_as_current_span(name) as sp:  # pragma: no cover - requires exporter
        for k, v in attributes.items():
            if isinstance(v, (str, int, float, bool)):
                sp.set_attribute(f"nexus.{k}", v)
        yield record


def _meter(tool: str, t0: float, ok: bool) -> None:
    try:
        from app.core.db import get_db

        get_db().log_tool_call(tool, (time.perf_counter() - t0) * 1000, ok, current_actor.get())
    except Exception:  # pragma: no cover - metering must never break a request
        logger.debug("metering failed", exc_info=True)


def observe(name: Optional[str] = None, meter: bool = True) -> Callable[[F], F]:
    """Decorator: trace span + duration/success metering for sync and async callables."""

    def deco(fn: F) -> F:
        tool = name or fn.__name__
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                t0, ok = time.perf_counter(), False
                with span(tool):
                    try:
                        out = await fn(*args, **kwargs)
                        ok = True
                        return out
                    finally:
                        if meter:
                            _meter(tool, t0, ok)
            return awrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0, ok = time.perf_counter(), False
            with span(tool):
                try:
                    out = fn(*args, **kwargs)
                    ok = True
                    return out
                finally:
                    if meter:
                        _meter(tool, t0, ok)
        return wrapper  # type: ignore[return-value]

    return deco
