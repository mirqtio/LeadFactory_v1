import os
from logging import ERROR as LOG_ERROR
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        FastApiIntegration(),
        LoggingIntegration(level=None, event_level=LOG_ERROR),
    ],
    traces_sample_rate=float(os.getenv("SENTRY_TRACE_RATE", "0.20")),
    environment=os.getenv("LF_ENV", "local"),
    release=os.getenv("GIT_SHA", "dev"),
)