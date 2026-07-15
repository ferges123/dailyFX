from app.utils.safe_logging import redact_sensitive, redact_url


def test_redact_url_removes_query_credentials_and_telegram_bot_token():
    value = "https://api.telegram.org/bot123456:secret/sendMessage?chat_id=42&token=query-secret"

    result = redact_url(value)

    assert "123456:secret" not in result
    assert "query-secret" not in result
    assert "chat_id=42" in result


def test_redact_sensitive_removes_bearer_tokens_and_credentials_from_errors():
    value = "Request failed for https://example.test/hook?api_key=abc: Bearer super-secret"

    result = redact_sensitive(value)

    assert "abc" not in result
    assert "super-secret" not in result
    assert "[REDACTED]" in result
