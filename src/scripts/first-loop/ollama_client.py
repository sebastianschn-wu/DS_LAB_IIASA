"""Start/check the local Ollama server and call the model."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any

import requests

from constants import (
    OLLAMA_CHAT_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MISSING_MESSAGE,
    OLLAMA_NUM_PREDICT,
    OLLAMA_PULL_CHECK_TIMEOUT,
    OLLAMA_SEED,
    OLLAMA_START_TIMEOUT_SECONDS,
    OLLAMA_TAGS_TIMEOUT,
)


def server_is_up(host: str) -> bool:
    try:
        return requests.get(f"{host}/api/tags", timeout=OLLAMA_TAGS_TIMEOUT).ok
    except requests.RequestException:
        return False


def installed_models(host: str) -> list[str]:
    response = requests.get(f"{host}/api/tags", timeout=OLLAMA_PULL_CHECK_TIMEOUT)
    response.raise_for_status()
    names: list[str] = []
    for item in response.json().get("models", []):
        for key in ("name", "model"):
            name = item.get(key, "")
            if name and name not in names:
                names.append(name)
    return names


def resolve_model(model: str, installed: list[str]) -> str | None:
    """Return the exact installed tag to use for ``model``, or None if it must be pulled.

    ``qwen2.5`` means ``qwen2.5:latest`` to Ollama. If only another tag of the same
    model is installed (e.g. ``qwen2.5:7b``), that tag is used. The old version
    accepted the other tag as "present" but still called ``qwen2.5``, which fails
    with "model not found".
    """
    wanted = model if ":" in model else f"{model}:latest"
    if wanted in installed or model in installed:
        return wanted if wanted in installed else model
    base = model.split(":", 1)[0]
    if ":" not in model:
        same_base = sorted(name for name in installed if name.split(":", 1)[0] == base)
        if same_base:
            return same_base[0]
    return None


def ensure_ollama(host: str, model: str) -> str:
    """Make sure the server runs and the model exists. Returns the model tag to call."""
    if shutil.which("ollama") is None:
        raise SystemExit(OLLAMA_MISSING_MESSAGE)

    if server_is_up(host):
        print(f"Ollama is already running at {host}")
    else:
        print("Starting Ollama locally...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.time() + OLLAMA_START_TIMEOUT_SECONDS
        while time.time() < deadline:
            if server_is_up(host):
                print("Ollama is ready.")
                break
            time.sleep(0.5)
        else:
            raise SystemExit(f"Ollama did not become ready at {host}")

    resolved = resolve_model(model, installed_models(host))
    if resolved:
        print(f"Using local model {resolved}")
        return resolved
    print(f"Pulling {model}...")
    subprocess.run(["ollama", "pull", model], check=True)
    return model


def call_model(
    host: str,
    model: str,
    instructions: str,
    user_prompt: str,
    num_ctx: int,
    temperature: float,
    response_format: Any = "json",
) -> str:
    """Send one chat request and return the raw message content.

    ``response_format`` is either "json" (any JSON object) or a JSON schema dict
    (Ollama >= 0.5 then only produces output that matches the schema).
    """
    response = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": response_format,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "seed": OLLAMA_SEED,
                "num_ctx": num_ctx,
                "num_predict": OLLAMA_NUM_PREDICT,
            },
        },
        timeout=OLLAMA_CHAT_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    content = body.get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"empty model response: {json.dumps(body)[:400]}")
    return content
