"""
Abstraktes LLM-Interface für OpenAI und Google Gemini.
Provider-Auswahl via LLM_PROVIDER in .env ("openai" oder "gemini").
"""
import os
from typing import Protocol


class LLMClient(Protocol):
    def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str: ...


class OpenAIClient:
    def __init__(self) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        response = self._client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class GeminiClient:
    def __init__(self) -> None:
        from google import genai
        self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def chat(self, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
        from google.genai import types
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text or ""


def get_client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "gemini":
        return GeminiClient()
    return OpenAIClient()
