"""Client OpenRouter (SDK OpenAI) + helper d'appel JSON validé Pydantic."""
from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

import config

_client: OpenAI | None = None
T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _strip_fences(raw: str) -> str:
    """Retire un éventuel bloc ```json ... ``` (certains modèles n'honorent pas
    strictement response_format)."""
    s = (raw or "").strip()
    m = _FENCE.match(s)
    return m.group(1).strip() if m else s


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.require("OPENROUTER_API_KEY", config.OPENROUTER_API_KEY),
            default_headers={
                # Attribution OpenRouter (facultatif mais recommandé).
                "HTTP-Referer": "https://le-declic.ghost.io",
                "X-Title": "Newsletter BRVM",
            },
        )
    return _client


def complete_text(model: str, system: str, user: str, temperature: float = 0.7) -> str:
    """Appel texte libre (utilisé pour la rédaction HTML)."""
    resp = client().chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def complete_json(
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    temperature: float = 0.2,
    retries: int = 2,
) -> T:
    """Appel structuré : force un objet JSON, valide contre `schema`.

    Réessaie en réinjectant l'erreur de parsing/validation dans le prompt.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err = ""
    for attempt in range(retries + 1):
        resp = client().chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = _strip_fences(resp.choices[0].message.content or "")
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = str(e)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    f"La réponse précédente est invalide : {last_err}\n"
                    f"Renvoie UNIQUEMENT un objet JSON conforme au schéma demandé, "
                    f"sans texte autour."
                ),
            })
    raise RuntimeError(f"Sortie JSON invalide après {retries + 1} tentatives : {last_err}")
