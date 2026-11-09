import io
import urllib.error

import pytest

from app.llm import client


def settings():
    return client.Settings("kku-intelsphere", "https://gen.ai.kku.ac.th/api/v1", "gpt-5.6-luna", "test-secret-not-real")


def test_api_key_is_not_part_of_settings_representation():
    assert "test-secret-not-real" not in repr(settings())


def test_configuration_status_never_returns_api_key(monkeypatch):
    monkeypatch.setattr(client, "load_settings", lambda **kwargs: settings())
    status = client.configuration_status()
    assert status["configured"] is True
    assert "api_key" not in status and "test-secret-not-real" not in str(status)


def test_missing_token_usage_is_unknown_not_zero(monkeypatch):
    monkeypatch.setattr(client, "load_settings", settings)
    monkeypatch.setattr(client, "_post_json", lambda *args: {
        "model": "gpt-5.6-luna", "choices": [{"message": {"content": '{"status":"unsupported","sql":null}'}, "finish_reason": "stop"}]})
    result = client.generate({"messages": [{"role": "user", "content": "q"}]})
    assert result["input_tokens"] is result["output_tokens"] is result["cost"] is None


def test_usage_and_selected_model_are_preserved(monkeypatch):
    monkeypatch.setattr(client, "load_settings", settings)
    def call(url, payload, s):
        assert url.endswith("/api/v1/chat/completions")
        assert payload["model"] == "gpt-5.6-luna" and payload["stream"] is False
        return {"model": "gpt-5.6-luna", "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}}
    monkeypatch.setattr(client, "_post_json", call)
    result = client.generate({"messages": []})
    assert result["requested_model"] == result["returned_model"] == "gpt-5.6-luna"
    assert result["input_tokens"] == 12 and result["output_tokens"] == 3


def test_truncated_output_is_not_treated_as_complete_sql(monkeypatch):
    monkeypatch.setattr(client, "load_settings", settings)
    monkeypatch.setattr(client, "_post_json", lambda *args: {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]})
    with pytest.raises(client.LLMCallError, match="truncated"):
        client.generate({"messages": []})


@pytest.mark.parametrize("body,expected", [(b'{"error":"Invalid model"}', "Invalid model"),
                                            (b'{"error":"test-secret-not-real"}', "HTTP 401")])
def test_error_body_does_not_leak_key_and_invalid_model_is_distinct(monkeypatch, body, expected):
    class Opener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError("https://gen.ai.kku.ac.th", 401, "Unauthorized", {}, io.BytesIO(body))
    monkeypatch.setattr(client.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(client.LLMCallError) as error:
        client._post_json("https://gen.ai.kku.ac.th/api/v1/chat/completions", {}, settings())
    assert expected in str(error.value)
    assert "test-secret-not-real" not in str(error.value)
