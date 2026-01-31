from __future__ import annotations

import json
from typing import Any, Dict

from agents.base import BaseReActAgent
from models.agent_io import AgentInput, AgentOutput


def _compact_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reducimos el estado para no mandar un JSON enorme al modelo.
    """
    meta = state.get("meta", {})
    player = state.get("player", {})
    world = state.get("world", {})
    mem = state.get("narrative_memory", {})

    return {
        "turn": meta.get("turn", 0),
        "player": {
            "name": player.get("name", "Jugador"),
            "hp": player.get("hp", 0),
            "location": player.get("location", "inicio"),
            "inventory": player.get("inventory", []),
        },
        "visited_locations": world.get("visited_locations", []),
        "flags": state.get("flags", {}),
        "current_scene": world.get("current_scene", {"type": "exploration"}),
        "memory_summary": mem.get("summary", ""),
        "last_events": (mem.get("last_events", [])[-5:]),
        "known_enemies": list((world.get("enemies", {}) or {}).keys()),
        "quests": world.get("quests", []),
    }


class NarratorAgent(BaseReActAgent):
    def __init__(self):
        super().__init__(role="narrator")

    def system_prompt(self) -> str:
        # Forzamos formato JSON (AgentOutput)
        return (
            "Eres el NARRADOR de una partida de rol inspirada en Dungeons & Dragons.\n"
            "Tu misión es narrar de forma inmersiva y COHERENTE con el estado del juego.\n\n"
            "REGLAS IMPORTANTES:\n"
            "- Escribe siempre en español.\n"
            "- No menciones prompts, sistema ni que eres una IA.\n"
            "- No contradigas el estado: lugares visitados, enemigos conocidos, flags.\n"
            "- Responde en 2–5 párrafos y termina con una pregunta: '¿Qué haces?'\n\n"
            "FORMATO DE SALIDA OBLIGATORIO:\n"
            "Devuelve EXCLUSIVAMENTE un JSON válido con esta forma:\n"
            "{\n"
            '  "text": "string",\n'
            '  "memory": {"append_event": "string opcional", "summary": "string opcional"},\n'
            '  "world": {"location": "string opcional", "add_visited_location": "string opcional"},\n'
            '  "scene": {"type": "exploration|combat|dialogue opcional", "active_enemy_ids": ["id"]},\n'
            '  "debug": {"any": "optional"}\n'
            "}\n"
            "No añadas texto fuera del JSON."
        )

    def user_prompt(self, inp: AgentInput) -> str:
        context = _compact_context(inp.state)
        return (
            "ESTADO ACTUAL (resumen):\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "ACCIÓN DEL JUGADOR:\n"
            f"{inp.player_input}\n\n"
            "Instrucciones:\n"
            "- Continúa la historia de forma coherente.\n"
            "- Si el jugador se mueve a un nuevo lugar, puedes proponer 'world.location' y 'world.add_visited_location'.\n"
            "- Si introduces un encuentro hostil, puedes activar scene.type='combat' y añadir un enemy_id en active_enemy_ids.\n"
            "- Añade un evento a memory.append_event para registrar lo importante del turno.\n"
        )


def narrador_agent(game_state: dict, player_input: str) -> dict:
    """
    Adaptador para mantener compatibilidad con el orquestador actual:
    devuelve un dict con keys: text, updates
    """
    agent = NarratorAgent()
    out: AgentOutput = agent.invoke(AgentInput(player_input=player_input, state=game_state))

    # Convertimos AgentOutput -> updates (formato que ya entiende vuestro apply_updates)
    turn = game_state.get("meta", {}).get("turn", 0)
    updates = {}

    # memory
    if out.memory and out.memory.append_event:
        updates.setdefault("narrative_memory", {})["last_events_append"] = out.memory.append_event
    else:
        # mínimo: siempre guardamos algo
        updates.setdefault("narrative_memory", {})["last_events_append"] = f"Turno {turn}: jugador -> {player_input}"

    if out.memory and out.memory.summary:
        updates.setdefault("narrative_memory", {})["summary"] = out.memory.summary

    # world
    if out.world and out.world.location:
        updates.setdefault("player", {})["location"] = out.world.location
    if out.world and out.world.add_visited_location:
        updates.setdefault("world", {})["visited_locations_append"] = out.world.add_visited_location

    # scene
    if out.scene and out.scene.type:
        updates.setdefault("world", {}).setdefault("current_scene", {})["type"] = out.scene.type
    if out.scene and out.scene.active_enemy_ids is not None:
        updates.setdefault("world", {}).setdefault("current_scene", {})["active_enemy_ids"] = out.scene.active_enemy_ids

    # debug opcional
    if out.debug:
        updates.setdefault("debug", {})["narrator"] = out.debug

    return {"text": out.text, "updates": updates}
