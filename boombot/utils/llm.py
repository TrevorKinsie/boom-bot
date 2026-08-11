import logging

import requests

from boombot.core.config import (
    LLM_API_KEY,
    LLM_APP_NAME,
    LLM_MODELS,
    LLM_REFERER,
    LLM_TIMEOUT,
)

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a ringside announcer for absurd hypothetical matchups. "
    "Always name a concrete winner. Never refuse, never hedge, never ask for "
    "clarification, never explain that the fight is hypothetical -- just call "
    "the fight."
)

UNREACHABLE_REPLY = (
    "The battle remains undecided. (My battle vision is down right now.)"
)


def _build_headers() -> dict[str, str]:
    """Headers for the OpenRouter chat completions endpoint."""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    if LLM_REFERER:
        headers["HTTP-Referer"] = LLM_REFERER
    if LLM_APP_NAME:
        headers["X-Title"] = LLM_APP_NAME
    return headers


def _extract_text(payload: dict) -> str | None:
    """Pull the assistant text out of a chat completion payload, if there is any."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first = choices[0]
    if not isinstance(first, dict):
        return None

    message = first.get("message")
    if not isinstance(message, dict):
        return None

    # Reasoning models sometimes leave `content` empty and put the answer in
    # `reasoning`, so fall back to it rather than reporting a failure.
    for key in ("content", "reasoning"):
        value = message.get(key)
        if isinstance(value, list):
            # Some providers return content as a list of typed parts.
            value = "".join(
                part.get("text", "")
                for part in value
                if isinstance(part, dict)
            )
        if isinstance(value, str) and value.strip():
            return value.strip()

    logger.warning(
        f"Empty completion (finish_reason={first.get('finish_reason')!r})"
    )
    return None


def _complete(model: str, question: str) -> str | None:
    """Ask a single model. Returns None if it errors out or says nothing."""
    try:
        response = requests.post(
            url=OPENROUTER_URL,
            headers=_build_headers(),
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Provide a concrete answer to the question in the form "
                            "of a battle summary in a single line, being extremely "
                            f"dramatic: '{question}'"
                        ),
                    },
                ],
                "temperature": 0.9,
                "max_tokens": 300,
            },
            timeout=LLM_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning(f"OpenRouter request failed for model '{model}': {e}")
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.warning(
            f"OpenRouter returned non-JSON for model '{model}' "
            f"(HTTP {response.status_code}): {response.text[:500]}"
        )
        return None

    if not isinstance(payload, dict):
        logger.warning(
            f"Unexpected OpenRouter payload for model '{model}': {payload!r}"
        )
        return None

    # OpenRouter reports model/rate-limit problems as an `error` object, which
    # previously surfaced only as a KeyError on 'choices' with no explanation.
    error = payload.get("error")
    if error or not response.ok:
        detail = error.get("message") if isinstance(error, dict) else error
        logger.warning(
            f"OpenRouter error for model '{model}' "
            f"(HTTP {response.status_code}): {detail or response.text[:500]}"
        )
        return None

    return _extract_text(payload)


def get_openrouter_response(question: str) -> str:
    """Get a response from OpenRouter API for the given question.

    Args:
        question: The question or prompt to send to the LLM

    Returns:
        The LLM's response as a string
    """
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY not set in environment variables")
        return f"Unable to process: '{question}' - API key not configured"

    for model in LLM_MODELS:
        answer = _complete(model, question)
        if answer:
            logger.info(f"Battle verdict came from model '{model}'")
            return answer
        logger.warning(f"Model '{model}' gave no usable answer, trying the next one.")

    logger.error(f"Every configured model failed for question: {question!r}")
    return UNREACHABLE_REPLY
