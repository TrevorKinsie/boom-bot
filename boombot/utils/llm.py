import logging
import re

import requests

from boombot.core.config import (
    LLM_API_KEY,
    LLM_APP_NAME,
    LLM_FOLLOW_MODEL_HINTS,
    LLM_MODELS,
    LLM_REFERER,
    LLM_TIMEOUT,
)

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# When a model is retired or moved off the free tier, OpenRouter 404s with the
# replacement slug in the message, e.g. "This model is unavailable for free. The
# paid version is available now - use this slug instead: deepseek/deepseek-chat-v3-0324".
SLUG_HINT_PATTERN = re.compile(r"use this slug instead:?\s*([\w./:-]+)")

# A salvaged verdict is a one-line call, not a paragraph of deliberation.
MAX_SALVAGED_VERDICT_CHARS = 400
VERDICT_PREFIX_PATTERN = re.compile(
    r"^(?:final\s+answer|final|answer|verdict|response|output)\s*[:\-—]\s*",
    re.IGNORECASE,
)
LAST_SENTENCE_PATTERN = re.compile(r"[^.!?]*[.!?]+[\"'”]?")

# Reasoning models otherwise spend the whole token budget thinking, leaving
# `content` empty. `enabled: false` turns thinking off where the model supports
# it; `exclude: true` keeps the trace out of the response for the models where
# it cannot be turned off.
REASONING_PARAMS = {"enabled": False, "exclude": True}

# Enough headroom that a model which reasons anyway can still finish and emit
# an actual answer instead of being cut off mid-thought.
MAX_TOKENS = 800

SYSTEM_PROMPT = (
    "You are a ringside announcer for absurd hypothetical matchups. "
    "Always name a concrete winner. Never refuse, never hedge, never ask for "
    "clarification, never explain that the fight is hypothetical -- just call "
    "the fight. Reply with the battle summary line and nothing else -- no "
    "preamble, no reasoning, no notes about how you decided."
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


def _as_text(value) -> str | None:
    """Normalise a message field to non-empty text, if it holds any."""
    if isinstance(value, list):
        # Some providers return content as a list of typed parts.
        value = "".join(
            part.get("text", "")
            for part in value
            if isinstance(part, dict)
        )
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _salvage_verdict(reasoning: str, finish_reason: str | None) -> str | None:
    """Pull the final call out of a reasoning trace, or give up.

    `reasoning` is the model's private deliberation, never an answer, so it must
    not be forwarded as-is -- that is how users ended up reading "Okay, the user
    wants a dramatic one-line battle summary...". A trace that ran to completion
    does normally end on the verdict it settled on, so take that last line and
    nothing else. A truncated trace stopped mid-thought and has no verdict to
    take.
    """
    if finish_reason not in ("stop", "end_turn"):
        return None

    lines = [line.strip() for line in reasoning.splitlines() if line.strip()]
    if not lines:
        return None

    candidate = lines[-1]
    if len(candidate) > MAX_SALVAGED_VERDICT_CHARS:
        # A trailing wall of text: keep only the last complete sentence, which
        # is where the trace lands on its answer.
        sentences = LAST_SENTENCE_PATTERN.findall(candidate)
        candidate = sentences[-1].strip() if sentences else ""

    # Strip the decoration before the label, so "**Verdict: ...**" is matched.
    candidate = candidate.strip().strip("*").strip("\"'“”").strip()
    candidate = VERDICT_PREFIX_PATTERN.sub("", candidate)
    candidate = candidate.strip().strip("*").strip("\"'“”").strip()
    if not candidate or len(candidate) > MAX_SALVAGED_VERDICT_CHARS:
        return None
    return candidate


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

    finish_reason = first.get("finish_reason")

    content = _as_text(message.get("content"))
    if content:
        return content

    # Reasoning models sometimes leave `content` empty and put everything in
    # `reasoning`. Salvage the verdict off the end of it if there is one;
    # otherwise treat the model as having said nothing and move down the chain.
    reasoning = _as_text(message.get("reasoning"))
    if reasoning:
        verdict = _salvage_verdict(reasoning, finish_reason)
        if verdict:
            logger.info(
                "Model returned no content; salvaged the verdict from its "
                "reasoning trace."
            )
            return verdict
        logger.warning(
            "Discarding a reasoning trace with no usable verdict "
            f"(finish_reason={finish_reason!r})"
        )
        return None

    logger.warning(f"Empty completion (finish_reason={finish_reason!r})")
    return None


def _suggested_model(detail: str | None, model: str) -> str | None:
    """Pull a replacement slug out of an OpenRouter error message, if it names one."""
    if not detail:
        return None
    match = SLUG_HINT_PATTERN.search(detail)
    if not match:
        return None
    suggestion = match.group(1).rstrip(".,")
    return suggestion if suggestion != model else None


def _complete(model: str, question: str) -> tuple[str | None, str | None]:
    """Ask a single model.

    Returns a (answer, replacement_model) pair. The answer is None if the model
    errors out or says nothing; the replacement is set only when OpenRouter's
    error names another slug to use instead.
    """
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
                "max_tokens": MAX_TOKENS,
                "reasoning": REASONING_PARAMS,
            },
            timeout=LLM_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning(f"OpenRouter request failed for model '{model}': {e}")
        return None, None

    try:
        payload = response.json()
    except ValueError:
        logger.warning(
            f"OpenRouter returned non-JSON for model '{model}' "
            f"(HTTP {response.status_code}): {response.text[:500]}"
        )
        return None, None

    if not isinstance(payload, dict):
        logger.warning(
            f"Unexpected OpenRouter payload for model '{model}': {payload!r}"
        )
        return None, None

    # OpenRouter reports model/rate-limit problems as an `error` object, which
    # previously surfaced only as a KeyError on 'choices' with no explanation.
    error = payload.get("error")
    if error or not response.ok:
        detail = error.get("message") if isinstance(error, dict) else error
        if not isinstance(detail, str):
            detail = None
        logger.warning(
            f"OpenRouter error for model '{model}' "
            f"(HTTP {response.status_code}): {detail or response.text[:500]}"
        )
        return None, _suggested_model(detail, model)

    return _extract_text(payload), None


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

    pending = list(LLM_MODELS)
    tried: set[str] = set()

    while pending:
        model = pending.pop(0)
        if model in tried:
            continue
        tried.add(model)

        answer, replacement = _complete(model, question)
        if answer:
            logger.info(f"Battle verdict came from model '{model}'")
            return answer

        # A retired model usually points at its own replacement, so try that
        # before falling further down the configured chain.
        if replacement and replacement not in tried:
            if LLM_FOLLOW_MODEL_HINTS:
                logger.info(
                    f"OpenRouter suggested '{replacement}' in place of '{model}'; "
                    "trying that next."
                )
                pending.insert(0, replacement)
            else:
                logger.info(
                    f"OpenRouter suggests '{replacement}' in place of '{model}'. "
                    "Set LLM_FOLLOW_MODEL_HINTS=true to follow suggestions like "
                    "this automatically -- note the replacement is usually the "
                    "paid model."
                )

        if pending:
            logger.warning(
                f"Model '{model}' gave no usable answer, trying the next one."
            )
        else:
            logger.warning(f"Model '{model}' gave no usable answer.")

    logger.error(f"Every configured model failed for question: {question!r}")
    return UNREACHABLE_REPLY
