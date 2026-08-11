import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from boombot.utils import llm


def make_response(payload=None, status_code=200, text=None):
    """Build a stand-in for a requests.Response."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.ok = 200 <= status_code < 400
    if payload is None:
        response.text = text if text is not None else ""
        response.json.side_effect = ValueError("no json")
    else:
        response.text = text if text is not None else json.dumps(payload)
        response.json.return_value = payload
    return response


def completion(content, finish_reason="stop", key="content"):
    return {"choices": [{"finish_reason": finish_reason, "message": {key: content}}]}


@pytest.fixture(autouse=True)
def api_key():
    with patch.object(llm, "LLM_API_KEY", "test-key"):
        yield


@pytest.fixture
def single_model():
    with patch.object(llm, "LLM_MODELS", ["model-a"]):
        yield


# --- Happy path ---

def test_returns_content(single_model):
    with patch.object(llm.requests, "post", return_value=make_response(completion("Lions win!"))) as post:
        assert llm.get_openrouter_response("lions vs tigers?") == "Lions win!"

    kwargs = post.call_args.kwargs
    # The body must be sent as JSON with the matching Content-Type; sending a
    # bare string body without the header is what OpenRouter rejects.
    assert kwargs["json"]["model"] == "model-a"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["timeout"] == llm.LLM_TIMEOUT
    assert "data" not in kwargs


def test_falls_back_to_reasoning_when_content_empty(single_model):
    payload = completion("", finish_reason="length")
    payload["choices"][0]["message"]["reasoning"] = "The gorilla wins."
    with patch.object(llm.requests, "post", return_value=make_response(payload)):
        assert llm.get_openrouter_response("q") == "The gorilla wins."


def test_joins_structured_content_parts(single_model):
    payload = completion([{"type": "text", "text": "One "}, {"type": "text", "text": "gorilla."}])
    with patch.object(llm.requests, "post", return_value=make_response(payload)):
        assert llm.get_openrouter_response("q") == "One gorilla."


# --- Failure handling ---

def test_no_api_key():
    with patch.object(llm, "LLM_API_KEY", None):
        assert "API key not configured" in llm.get_openrouter_response("q")


@pytest.mark.parametrize(
    "response",
    [
        make_response({"error": {"code": 404, "message": "No endpoints found"}}, status_code=404),
        make_response({"error": {"code": 429, "message": "Rate limit exceeded"}}, status_code=429),
        make_response(status_code=502, text="<html>bad gateway</html>"),
        make_response({"choices": []}),
        make_response(completion("   ")),
    ],
    ids=["model-gone", "rate-limited", "non-json", "no-choices", "blank-content"],
)
def test_single_model_failures_return_fallback(single_model, response):
    with patch.object(llm.requests, "post", return_value=response):
        assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY


def test_network_error_returns_fallback(single_model):
    with patch.object(llm.requests, "post", side_effect=requests.Timeout("timed out")):
        assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY


# --- Model fallback chain ---

def test_falls_through_to_next_model():
    responses = [
        make_response({"error": {"message": "No endpoints found for model"}}, status_code=404),
        make_response(completion("The gorilla wins.")),
    ]
    with patch.object(llm, "LLM_MODELS", ["dead-model", "live-model"]):
        with patch.object(llm.requests, "post", side_effect=responses) as post:
            assert llm.get_openrouter_response("q") == "The gorilla wins."

    assert [call.kwargs["json"]["model"] for call in post.call_args_list] == [
        "dead-model",
        "live-model",
    ]


def test_stops_at_first_working_model():
    with patch.object(llm, "LLM_MODELS", ["model-a", "model-b"]):
        with patch.object(llm.requests, "post", return_value=make_response(completion("Done."))) as post:
            assert llm.get_openrouter_response("q") == "Done."
    assert post.call_count == 1


def test_all_models_exhausted():
    with patch.object(llm, "LLM_MODELS", ["a", "b", "c"]):
        response = make_response({"error": {"message": "nope"}}, status_code=429)
        with patch.object(llm.requests, "post", return_value=response) as post:
            assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY
    assert post.call_count == 3


# --- Retired models that name their replacement ---

RETIRED = make_response(
    {
        "error": {
            "code": 404,
            "message": (
                "This model is unavailable for free. The paid version is available "
                "now - use this slug instead: deepseek/deepseek-chat-v3-0324"
            ),
        }
    },
    status_code=404,
)


@pytest.fixture
def follow_hints():
    """Following slug hints is opt-in, because the replacement is usually paid."""
    with patch.object(llm, "LLM_FOLLOW_MODEL_HINTS", True):
        yield


def test_follows_suggested_slug(follow_hints):
    responses = [RETIRED, make_response(completion("The gorilla wins."))]
    with patch.object(llm, "LLM_MODELS", ["deepseek/deepseek-chat-v3-0324:free"]):
        with patch.object(llm.requests, "post", side_effect=responses) as post:
            assert llm.get_openrouter_response("q") == "The gorilla wins."

    assert [call.kwargs["json"]["model"] for call in post.call_args_list] == [
        "deepseek/deepseek-chat-v3-0324:free",
        "deepseek/deepseek-chat-v3-0324",
    ]


def test_suggested_slug_is_tried_before_the_rest_of_the_chain(follow_hints):
    responses = [RETIRED, make_response(completion("Paid model answers."))]
    with patch.object(llm, "LLM_MODELS", ["deepseek/deepseek-chat-v3-0324:free", "model-z"]):
        with patch.object(llm.requests, "post", side_effect=responses) as post:
            assert llm.get_openrouter_response("q") == "Paid model answers."

    assert [call.kwargs["json"]["model"] for call in post.call_args_list] == [
        "deepseek/deepseek-chat-v3-0324:free",
        "deepseek/deepseek-chat-v3-0324",
    ]


def test_suggested_slug_is_ignored_by_default():
    """Nothing should silently start billing the paid model."""
    with patch.object(llm, "LLM_MODELS", ["deepseek/deepseek-chat-v3-0324:free"]):
        with patch.object(llm.requests, "post", return_value=RETIRED) as post:
            assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY

    assert post.call_count == 1


def test_suggested_slug_is_not_retried_when_already_in_the_chain(follow_hints):
    """The hint must not make us call a model we have already ruled out."""
    with patch.object(
        llm,
        "LLM_MODELS",
        ["deepseek/deepseek-chat-v3-0324", "deepseek/deepseek-chat-v3-0324:free"],
    ):
        with patch.object(llm.requests, "post", return_value=RETIRED) as post:
            assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY

    assert [call.kwargs["json"]["model"] for call in post.call_args_list] == [
        "deepseek/deepseek-chat-v3-0324",
        "deepseek/deepseek-chat-v3-0324:free",
    ]


def test_duplicate_models_are_only_called_once():
    with patch.object(llm, "LLM_MODELS", ["model-a", "model-a"]):
        response = make_response({"error": {"message": "nope"}}, status_code=429)
        with patch.object(llm.requests, "post", return_value=response) as post:
            assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY
    assert post.call_count == 1


@pytest.mark.parametrize(
    "message",
    ["No endpoints found for google/gemini-2.0-flash-001.", "Rate limit exceeded", ""],
)
def test_errors_without_a_slug_hint_do_not_add_models(follow_hints, message):
    with patch.object(llm, "LLM_MODELS", ["model-a"]):
        response = make_response({"error": {"message": message}}, status_code=404)
        with patch.object(llm.requests, "post", return_value=response) as post:
            assert llm.get_openrouter_response("q") == llm.UNREACHABLE_REPLY
    assert post.call_count == 1
