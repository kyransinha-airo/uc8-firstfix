"""One way to make a structured model call: live, recorded, or replayed.

Agent and model calls go through structured_call(). It returns the model's output parsed
into a Pydantic schema, and the replay key that identifies the call. In replay mode nothing
reaches a model: the output saved for the same agent, prompt version and messages is
returned, so the demo and CI run the same every time (docs/architecture.md, "Replay").

The key hashes the agent, prompt version, schema name and the exact message text. Prompts
carry document ids and page text only, never database ids, so a recording made on one
database replays on another loaded with the same mock data.

Saved outputs live in settings.replay_dir/<agent>/<key>.json. Record, review the outputs
(screen figures and verdicts rest on them), then commit them. Record mode reuses an output
already saved for the same input; delete the directory to record from scratch.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.llm import LLMConfigurationError, get_llm

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class CallResult(Generic[T]):
    output: T
    key: str
    source: str  # "live", "replay" or "injected"
    attempts: int


def replay_key(
    agent: str,
    prompt_version: str,
    schema: type[BaseModel],
    messages: list[BaseMessage],
    vote: int | None = None,
) -> str:
    payload = {
        "agent": agent,
        "prompt_version": prompt_version,
        "schema": schema.__name__,
        "messages": [[m.type, m.content] for m in messages],
    }
    if vote is not None:
        payload["vote"] = vote
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def replay_path(agent: str, key: str, replay_dir: Path | None = None) -> Path:
    return (replay_dir or settings.replay_dir) / agent / f"{key}.json"


def structured_call(
    agent: str,
    prompt_version: str,
    schema: type[T],
    messages: list[BaseMessage],
    *,
    model: Runnable | None = None,
    check: Callable[[T], list[str]] | None = None,
    mode: str | None = None,
    vote: int | None = None,
) -> CallResult[T]:
    """Call the model (or a replay) and parse into schema.

    check, if given, returns problems with an output (a quote not found, say). On a live
    call with problems the model is asked once more with the problems listed; whatever
    comes back is returned and the caller decides what the remaining problems mean.
    model: an injected fake (tests); never recorded or replayed.
    vote: for repeated independent calls on the same input (self-consistency); each vote
    is its own recording.
    """
    mode = mode or settings.llm_mode
    key = replay_key(agent, prompt_version, schema, messages, vote)

    if model is not None:
        return CallResult(_invoke(model, schema, messages), key, "injected", 1)

    path = replay_path(agent, key)
    # record reuses an output already saved for the same input, so one recording never
    # holds two answers to one question.
    if mode == "replay" or (mode == "record" and path.is_file()):
        if not path.is_file():
            raise AppError(
                ErrorCode.NOT_CONFIGURED,
                f"no recorded {agent} output for this input. LLM_MODE=replay only runs"
                " recorded inputs: use the mock data unchanged, or set LLM_MODE=live to"
                " call the model",
                {"agent": agent, "key": key, "path": str(path)},
            )
        saved = json.loads(path.read_text(encoding="utf-8"))
        return CallResult(schema.model_validate(saved["output"]), key, "replay", 1)

    try:
        live = get_llm().with_structured_output(schema)
    except LLMConfigurationError as e:
        raise AppError(ErrorCode.NOT_CONFIGURED, str(e)) from e

    attempts = 1
    output = _invoke_live(live, schema, messages, agent)
    problems = check(output) if check else []
    if problems:
        attempts = 2
        log.info("%s: retrying once: %s", agent, "; ".join(problems))
        retry = [
            *messages,
            HumanMessage(
                "Your previous answer had these problems:\n- "
                + "\n- ".join(problems)
                + "\nAnswer again, fixing them. Quotes must be copied exactly from the text."
            ),
        ]
        output = _invoke_live(live, schema, retry, agent)

    if mode == "record":
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "agent": agent,
            "prompt_version": prompt_version,
            "schema": schema.__name__,
            "model": settings.azure_openai_deployment,
            "attempts": attempts,
            "output": output.model_dump(mode="json"),
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return CallResult(output, key, "live", attempts)


def _invoke(model: Runnable, schema: type[T], messages: list[BaseMessage]) -> T:
    out = model.invoke(messages)
    return out if isinstance(out, schema) else schema.model_validate(out)


def _invoke_live(model: Runnable, schema: type[T], messages: list[BaseMessage], agent: str) -> T:
    """One live call; a reply that does not fit the schema is retried once."""
    last: Exception | None = None
    for _ in range(2):
        try:
            return _invoke(model, schema, messages)
        except (ValidationError, ValueError) as e:
            last = e
            log.warning("%s: output did not fit %s: %s", agent, schema.__name__, e)
        except Exception as e:  # network, auth, rate limit: surfaced as one error type
            raise AppError(
                ErrorCode.UPSTREAM_ERROR, f"{agent}: model call failed: {type(e).__name__}: {e}"
            ) from e
    raise AppError(
        ErrorCode.UPSTREAM_ERROR, f"{agent}: model output did not fit the schema: {last}"
    )
