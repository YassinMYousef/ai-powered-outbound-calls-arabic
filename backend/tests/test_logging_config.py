import json
import logging

from app.logging_config import JsonFormatter, request_id_context


def test_json_formatter_includes_request_correlation() -> None:
    token = request_id_context.set("request-123")
    try:
        record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert payload["message"] == "hello world"
    assert payload["request_id"] == "request-123"
    assert payload["level"] == "INFO"
