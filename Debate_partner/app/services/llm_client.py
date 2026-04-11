from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from openai import OpenAI
from dotenv import load_dotenv


def _extract_json_block(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("LLM returned empty content.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        return json.loads(text[first : last + 1])

    raise ValueError("LLM did not return valid JSON content.")


class MiniMaxLLMClient:
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        dotenv_path = os.path.join(project_root, ".env")
        load_dotenv(dotenv_path=dotenv_path, override=False)

        self.model = model or os.getenv("MINIMAX_MODEL", "MiniMax-M2.5")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for MiniMax API calls.")

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 1.0,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            extra_body={"reasoning_split": True},
        )
        content = response.choices[0].message.content or ""
        return str(content).strip()

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 1.0,
    ) -> Dict[str, Any]:
        text = self.chat_text(system_prompt=system_prompt, user_prompt=user_prompt, temperature=temperature)
        return _extract_json_block(text)
