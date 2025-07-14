import os
from logging import ERROR as LOG_ERROR

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

# Only initialize Sentry if DSN is provided and not in test environment
sentry_dsn = os.getenv("SENTRY_DSN")
is_test_env = os.getenv("CI") == "true" or os.getenv("ENVIRONMENT") == "test"

if sentry_dsn and not sentry_dsn.startswith("<PUT-YOUR-") and not is_test_env:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=None, event_level=LOG_ERROR),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACE_RATE", "0.20")),
        environment=os.getenv("LF_ENV", "local"),
        release=os.getenv("GIT_SHA", "dev"),
    )
