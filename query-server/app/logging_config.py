# Structured (JSON) request logging, set up once at import time.
# JSON from day one so this data is directly machine-readable for Phase 5's
# evaluation / A/B analysis, instead of needing a log-scraping step later.
import json
import logging
import sys
import time

LOGGER_NAME = "search_engine"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # per-call structured fields, passed in via log_request()'s `extra=`
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            payload.update(extra_fields)
        return json.dumps(payload)


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:  # avoid duplicate handlers if called more than once
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # don't also hand records to the root logger
    return logger


# one call site for every endpoint's per-request log line, e.g.
# log_request(logger, query="python", latency_ms=4.2, result_count=32, cache_hit=False)
def log_request(logger: logging.Logger, **fields) -> None:
    logger.info("request", extra={"extra_fields": fields})
