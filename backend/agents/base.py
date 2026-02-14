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

# Ajuste de cómo se va a inicializar cada agente.
    def __init__(self, role: str): 
        self.role = role
        self.llm = get_llm(role=role)

#Obligamos a cada agente a definir su system prompt y user prompt, para que cada uno pueda tener su personalidad y estilo de respuesta.
    @abstractmethod
    def system_prompt(self) -> str:
        ...

    @abstractmethod
    def user_prompt(self, inp: AgentInput) -> str:
        ...


    def invoke(self, inp: AgentInput) -> AgentOutput:
        #Importamos mensajes de LangChain aquí para evitar importaciones circulares al cargar el módulo.
        from langchain_core.messages import SystemMessage, HumanMessage # SystemMessage es para el prompt de sistema, HumanMessage para el prompt de usuario.

        system = self.system_prompt() # Define las reglas y el formato de respuesta esperado.
        user = self.user_prompt(inp) # Incluye la información concreta de cada turno

        response = self.llm.invoke([ # No lo entiendo
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])

#Intentamos extraer la información del modelo en formato JSON. SI hya información adicional, hacemos limieza para quedarnos solo con el JSON y evitar errores de parseo.
        raw = response.content if hasattr(response, "content") else str(response)
        raw = (raw or "").strip()

#Intentamos normalizar el formato de respuesta, eliminando posibles markdown fences y quedándonos solo con el bloque JSON quitando información adicional que no nos aporta información útil.
        if raw.startswith("```"):
            # Quitamos los markdown fences (¿Qué es Markdown fences?) 
            lines = [ln for ln in raw.splitlines()]
            # drop first fence
            if lines:
                lines = lines[1:]
            # drop last fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        # Quitamos cualquier texto antes del primer { y después del último }
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first : last + 1].strip()

        # Intentamos parsear y validar el JSON. Esta info se le pasa al orquestador, para ello debe estar en un formato concreto para que no sea todo muy caótico.
        try:
            data = json.loads(raw)
            return AgentOutput(**data)
# Si no se puede parsear ni validar, hacemos un except para que no reviente el sistema.
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