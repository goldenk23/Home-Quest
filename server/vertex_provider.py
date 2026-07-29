"""One-request Vertex AI Gemini bridge for the Node floor-plan server."""
from __future__ import annotations

import json
import os
import sys

MAX_INPUT_BYTES = 2 * 1024 * 1024


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def main() -> None:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed; run: python -m pip install -r server/requirements-vertex.txt") from exc

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("provider request exceeds 2 MB")
    payload = json.loads(raw)
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty array")

    system: list[str] = []
    contents: list[types.Content] = []
    for message in messages:
        role, text = message.get("role"), message.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(text, str) or not text.strip():
            raise ValueError("each message requires a supported role and non-empty content")
        if role == "system":
            system.append(text)
        else:
            contents.append(types.Content(role="model" if role == "assistant" else "user", parts=[types.Part.from_text(text=text)]))

    client = genai.Client(vertexai=True, project=required_env("GOOGLE_CLOUD_PROJECT"), location=required_env("GOOGLE_CLOUD_LOCATION"))
    response = client.models.generate_content(
        model=required_env("AI_MODEL"),
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction="\n\n".join(system), temperature=0.2,
            max_output_tokens=int(payload.get("maxOutputTokens", 16000)),
            response_mime_type="application/json",
        ),
    )
    if not response.text or not response.text.strip():
        raise RuntimeError("Gemini returned no text content")
    sys.stdout.write(json.dumps({"content": response.text}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
