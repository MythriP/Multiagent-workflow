# ─── llm.py ──────────────────────────────────────────────────────────────────
# Unified LLM caller for narrative + scene_writer steps. Three modes:
#
#   mode = "openai"  → calls OpenAI Chat Completions (GPT-4o by default).
#                      Default mode for now since we have an OpenAI key.
#                      Fully automated, no pauses.
#
#   mode = "api"     → calls Anthropic Claude API directly. Used when an
#                      ANTHROPIC_API_KEY is configured. Fully automated.
#
#   mode = "manual"  → writes prompt to a file, waits for the user to paste
#                      a response back. Useful for ad-hoc dev/debug runs.
#                      Pipeline pauses until the response file is written.

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_MODE = os.environ.get("CLAUDE_MODE", "openai").strip().lower()
DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")


# ─── Manual mode ──────────────────────────────────────────────────────────────

def _save_prompt_for_manual(
    label: str,
    system: str,
    user: str,
    out_dir: Path,
) -> tuple[Path, Path]:
    prompt_path = out_dir / f"{label}_PROMPT.md"
    response_path = out_dir / f"{label}_RESPONSE.json"

    content = f"""# Manual prompt — {label}

> Run this prompt in Cursor (or any LLM session).
> Save the JSON output to: `{response_path}`
> Then return to the terminal and press Enter.

---

## SYSTEM PROMPT

{system}

---

## USER MESSAGE

{user}

---

## OUTPUT REQUIREMENTS

- Return ONLY valid JSON. No markdown fences. No commentary.
- Save the raw JSON to: `{response_path}`
"""
    prompt_path.write_text(content)
    return prompt_path, response_path


# ─── API callers ──────────────────────────────────────────────────────────────

# Models we'll try in order when the requested model returns 529 for
# multiple attempts. The fallbacks are the same family but smaller /
# less-loaded variants — same prompt, no behavioral changes needed.
_ANTHROPIC_FALLBACK_CHAIN = {
    "claude-sonnet-4-5": ["claude-sonnet-4-5", "claude-haiku-4-5"],
    "claude-sonnet-4-6": ["claude-sonnet-4-6", "claude-sonnet-4-5", "claude-haiku-4-5"],
    "claude-opus-4-5":   ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
    "claude-opus-4-7":   ["claude-opus-4-7", "claude-opus-4-5", "claude-sonnet-4-5"],
}


def _call_anthropic_api(
    system: str, user: str, model: str, api_key: str, max_tokens: int,
    *, max_retries_per_model: int = 6,
) -> str:
    """
    Call Anthropic with exponential backoff on transient errors:
    529 overloaded_error, 503 service_unavailable, 502/504, network blips.
    Permanent errors (400/401/403/422) raise immediately.

    If `model` is one of the known sonnet/opus models, we'll fall back to
    smaller siblings after exhausting retries — Anthropic regularly has
    sonnet overloaded while haiku is healthy.
    """
    import time
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    # Adaptive thinking is currently Opus-only. Sonnet/Haiku 400 with
    # "adaptive thinking is not supported on this model" — only enable it
    # when the model name contains "opus".
    base_kwargs: dict = dict(
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    chain = _ANTHROPIC_FALLBACK_CHAIN.get(model, [model])
    last_exc: Exception | None = None

    for model_idx, current_model in enumerate(chain):
        kwargs = {**base_kwargs, "model": current_model}
        if "opus" in current_model.lower():
            kwargs["thinking"] = {"type": "adaptive"}

        if model_idx > 0:
            log.warning(
                "Anthropic falling back to model %r (previous %r exhausted)",
                current_model, chain[model_idx - 1],
            )

        delay = 4.0
        for attempt in range(1, max_retries_per_model + 1):
            try:
                # Use the non-streaming path: streaming SSE responses can
                # raise overloaded_error mid-stream from inside the
                # context-manager exit handler, which sometimes escapes
                # the try/except below in stranger ways than a plain call
                # to .messages.create().
                msg = client.messages.create(**kwargs)
                for block in msg.content:
                    if block.type == "text":
                        return block.text
                return ""
            except Exception as exc:
                last_exc = exc
                cls_name = type(exc).__name__
                status = getattr(exc, "status_code", None)
                err_type = ""
                body = getattr(exc, "body", None)
                if isinstance(body, dict):
                    err_type = ((body.get("error") or {}).get("type") or "")
                else:
                    try:
                        err_type = (
                            (exc.response.json().get("error") or {}).get("type") or ""
                        )
                    except Exception:
                        pass
                transient = (
                    status in (408, 425, 429, 500, 502, 503, 504, 529)
                    or err_type in ("overloaded_error", "rate_limit_error", "api_error")
                    or cls_name in ("APIConnectionError", "APITimeoutError")
                )
                if not transient:
                    raise
                if attempt >= max_retries_per_model:
                    log.warning(
                        "Anthropic transient %s on %r exhausted after %d "
                        "attempts; trying next model in chain.",
                        err_type or cls_name, current_model, attempt,
                    )
                    break  # outer loop tries next model
                wait = delay
                log.warning(
                    "Anthropic transient error (%s status=%s type=%r) on "
                    "%r attempt %d/%d — sleeping %.0fs and retrying",
                    cls_name, status, err_type or "unknown",
                    current_model, attempt, max_retries_per_model, wait,
                )
                time.sleep(wait)
                delay = min(delay * 1.7, 60.0)

    # Every model exhausted — re-raise the last error so the caller sees it.
    if last_exc is not None:
        raise last_exc
    return ""


def _call_openai_api(
    system: str,
    user: str,
    model: str,
    api_key: str,
    max_tokens: int,
    expect_json: bool = True,
) -> str:
    """
    Call OpenAI Chat Completions. When expect_json is True we use JSON-mode;
    otherwise we let the model return free-form text (used by the freeform
    narrative pass).
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    if expect_json:
        # JSON mode requires "json" mentioned in messages — JSON-output prompts
        # already demand JSON, so this is satisfied. Add a reminder regardless.
        messages = [
            {
                "role": "system",
                "content": system + "\n\nRespond with valid JSON only.",
            },
            {"role": "user", "content": user},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            response_format={"type": "json_object"},
        )
    else:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.85,
        )
    return response.choices[0].message.content or ""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


# ─── Entry point ──────────────────────────────────────────────────────────────

def call_claude(
    *,
    label: str,
    system: str,
    user: str,
    out_dir: Path,
    model: str = "",
    max_tokens: int = 4096,
    mode: str | None = None,
    anthropic_api_key: str = "",
    openai_api_key: str = "",
    openai_model: str = "",
    expect_json: bool = True,
) -> str:
    """
    Invoke an LLM and return the raw text response (with code fences stripped).
    Function name kept as call_claude for backwards compatibility, but it
    routes to OpenAI / Anthropic / manual depending on `mode`.

    Args:
      label: short tag like "narrative" or "scene_writer" — used in filenames
      system: system prompt
      user: user message
      out_dir: where to save prompt / response (manual mode) or audit logs
      model: Anthropic model id (used only when mode == "api")
      max_tokens: max output tokens (used in api / openai modes)
      mode: "openai" | "api" | "manual" (falls back to env CLAUDE_MODE)
      anthropic_api_key: required when mode == "api"
      openai_api_key: required when mode == "openai"
      openai_model: optional OpenAI model override (defaults to env OPENAI_MODEL or gpt-4o)
      expect_json: True (default) → enforce JSON output (OpenAI JSON mode,
        Anthropic prompt-level). False → free-form prose (used by pass-1
        narrative monologue).
    """
    mode = (mode or DEFAULT_MODE or "openai").lower()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Always save the assembled prompt for debugging
    audit_path = out_dir / f"{label}_PROMPT.md"
    if not audit_path.exists():
        _save_prompt_for_manual(label, system, user, out_dir)

    # File extension for saved raw response: .txt for free-form, .json for JSON.
    response_ext = "json" if expect_json else "txt"

    # ── OpenAI mode ──────────────────────────────────────────────────────────
    if mode == "openai":
        if not openai_api_key:
            raise ValueError("openai mode requires openai_api_key (set OPENAI_API_KEY)")
        m = openai_model or DEFAULT_OPENAI_MODEL
        log.info("🤖 Calling OpenAI (%s, expect_json=%s)...", m, expect_json)
        raw = _call_openai_api(system, user, m, openai_api_key, max_tokens, expect_json=expect_json)
        (out_dir / f"{label}_RESPONSE.{response_ext}").write_text(raw)
        return _strip_fences(raw) if expect_json else (raw or "").strip()

    # ── Anthropic API mode ───────────────────────────────────────────────────
    if mode == "api":
        if not anthropic_api_key:
            raise ValueError("api mode requires anthropic_api_key (set ANTHROPIC_API_KEY)")
        log.info("🤖 Calling Anthropic API (%s, expect_json=%s)...", model, expect_json)
        raw = _call_anthropic_api(system, user, model, anthropic_api_key, max_tokens)
        (out_dir / f"{label}_RESPONSE.{response_ext}").write_text(raw)
        return _strip_fences(raw) if expect_json else (raw or "").strip()

    # ── Manual mode ──────────────────────────────────────────────────────────
    _, response_path = _save_prompt_for_manual(label, system, user, out_dir)

    print()
    print("━" * 70)
    print(f"  ⏸  MANUAL LLM STEP — {label}")
    print("━" * 70)
    print(f"  1. Open this file: {audit_path}")
    print(f"  2. Ask any LLM to execute the prompt.")
    print(f"  3. Save the JSON response to: {response_path}")
    print(f"  4. Press Enter when ready.")
    print("━" * 70)

    while True:
        try:
            input("  ▶ Press Enter when response file is ready... ")
        except EOFError:
            raise RuntimeError("Manual LLM step aborted (stdin closed)")

        if response_path.exists() and response_path.stat().st_size > 0:
            raw = response_path.read_text()
            log.info("✅ Read manual response from %s", response_path.name)
            return _strip_fences(raw)

        print(f"  ✗ File not found or empty: {response_path}")
