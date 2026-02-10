from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict

from pydantic import ValidationError

from models.agent_io import AgentInput, AgentOutput
from config import get_llm


class BaseReActAgent(ABC):
    """
    Agente base:
    - Construye prompts
    - Invoca el LLM
    - Espera JSON y lo parsea a AgentOutput
    """

    def __init__(self, role: str):
        self.role = role
        self.llm = get_llm(role=role)

    @abstractmethod
    def system_prompt(self) -> str:
        ...

    @abstractmethod
    def user_prompt(self, inp: AgentInput) -> str:
        ...

    def invoke(self, inp: AgentInput) -> AgentOutput:
        from langchain_core.messages import SystemMessage, HumanMessage

        system = self.system_prompt()
        user = self.user_prompt(inp)

        response = self.llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])

        raw = response.content if hasattr(response, "content") else str(response)
        raw = (raw or "").strip()

        # --- Robust JSON cleanup ---
        # A veces el modelo devuelve el JSON dentro de un bloque ```json ...``` o
        # añade texto accidental alrededor. Para evitar que el parseo falle y que
        # el juego imprima el JSON completo, intentamos normalizarlo.
        if raw.startswith("```"):
            # remove markdown fences
            lines = [ln for ln in raw.splitlines()]
            # drop first fence
            if lines:
                lines = lines[1:]
            # drop last fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        # Trim anything before first '{' and after last '}'
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first : last + 1].strip()

        # Intentar parsear JSON -> AgentOutput
        try:
            data = json.loads(raw)
            return AgentOutput(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Fallback: devolvemos el texto tal cual, marcando debug
            return AgentOutput(
                text=raw if raw else "No he podido generar respuesta. ¿Qué haces?",
                debug={
                    "parse_error": True,
                    "error_type": type(e).__name__,
                    # guardamos solo un trocito para no llenar logs
                    "raw_preview": raw[:300],
                },
            )