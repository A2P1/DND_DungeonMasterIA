from __future__ import annotations

import json
from typing import Any, Dict

from agents.base import BaseReActAgent
from models.agent_io import AgentInput, AgentOutput
from utils.prompt_loader import load_prompt


def _compact_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reducimos el estado para no mandar un JSON enorme al modelo.
    Se adapta a la estructura real: world.current_scene, world.locations, etc.
    """
    meta = state.get("meta", {})
    player = state.get("player", {})
    world = state.get("world", {})
    mem = state.get("narrative_memory", {})

    current_scene = world.get("current_scene", {}) or {}
    locations = world.get("locations", {}) or {}

    # Para no mandar un mapa enorme, enviamos solo info del lugar actual (si existe)
    current_location_id = current_scene.get("location") or player.get("location", "inicio")
    current_location_info = locations.get(current_location_id, {})

    return {
        "turn": meta.get("turn", 0),

        "player": {
            "id": player.get("id", "player_1"),
            "name": player.get("name", "Jugador"),
            "hp": player.get("hp", 0),
            "max_hp": player.get("max_hp", player.get("hp", 0)),
            "location": player.get("location", "inicio"),
            "inventory": player.get("inventory", []),
            "gold": player.get("gold", 0),
            "status_effects": player.get("status_effects", []),
        },

        "world": {
            "current_scene": {
                "type": current_scene.get("type", "exploration"),
                "location": current_location_id,
                "active_enemy_ids": current_scene.get("active_enemy_ids", []),
                "active_npc_ids": current_scene.get("active_npc_ids", []),
            },

            "visited_locations": world.get("visited_locations", []),

            # solo el lugar actual para que el modelo no se pierda
            "current_location_info": {
                "id": current_location_id,
                "name": current_location_info.get("name", current_location_id),
                "description": current_location_info.get("description", ""),
                "connected_to": current_location_info.get("connected_to", []),
            },

            "known_enemy_ids": list((world.get("enemies", {}) or {}).keys()),
            "known_npc_ids": list((world.get("npcs", {}) or {}).keys()),

            "quests_active": (world.get("quests", {}) or {}).get("active", []),
            "quests_completed": (world.get("quests", {}) or {}).get("completed", []),
        },

        "flags": state.get("flags", {}),

        "narrative_memory": {
            "summary": mem.get("summary", ""),
            "last_events": (mem.get("last_events", [])[-5:]),
            "important_facts": mem.get("important_facts", []),
        }
    }


class NarratorAgent(BaseReActAgent):
    def __init__(self):
        super().__init__(role="narrator")

    def system_prompt(self) -> str:
        # Sigue en código (si luego quieres pasarlo a .txt, lo cambiamos en 2 líneas)
        return load_prompt("sistema_narrador.txt")

    def user_prompt(self, inp: AgentInput) -> str:
        context = _compact_context(inp.state)

        return (
            "ESTADO ACTUAL (resumen):\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "ACCIÓN DEL JUGADOR:\n"
            f"{inp.player_input}\n\n"
            "Instrucciones:\n"
            "- Continúa la historia de forma coherente.\n"
            "- Si el jugador se mueve, usa world.location (id del lugar) y world.add_visited_location.\n"
            "- Si introduces un encuentro hostil y quieres pasar a combate, pon scene.type='combat' y añade enemy_id(s) a active_enemy_ids.\n"
            "- Añade un evento a memory.append_event que resuma el turno.\n"
        )


def narrador_agent(game_state: dict, player_input: str) -> dict:
    """
    Adaptador para mantener compatibilidad con el orquestador actual:
    devuelve dict con keys: text, updates
    """
    agent = NarratorAgent()
    out: AgentOutput = agent.invoke(AgentInput(player_input=player_input, state=game_state))

    turn = game_state.get("meta", {}).get("turn", 0)
    updates: Dict[str, Any] = {}

    # ---- Memoria ----
    if out.memory and out.memory.append_event:
        updates.setdefault("narrative_memory", {})["last_events_append"] = out.memory.append_event
    else:
        updates.setdefault("narrative_memory", {})["last_events_append"] = f"Turno {turn}: jugador -> {player_input}"

    if out.memory and out.memory.summary:
        updates.setdefault("narrative_memory", {})["summary"] = out.memory.summary

    # ---- Movimiento / mundo ----
    if out.world and out.world.location:
        # location afecta tanto a player.location como a current_scene.location (mantener coherencia)
        updates.setdefault("player", {})["location"] = out.world.location
        updates.setdefault("world", {}).setdefault("current_scene", {})["location"] = out.world.location

    if out.world and out.world.add_visited_location:
        updates.setdefault("world", {})["visited_locations_append"] = out.world.add_visited_location

    # ---- Escena ----
    if out.scene and out.scene.type:
        updates.setdefault("world", {}).setdefault("current_scene", {})["type"] = out.scene.type

    if out.scene and out.scene.active_enemy_ids is not None:
        updates.setdefault("world", {}).setdefault("current_scene", {})["active_enemy_ids"] = out.scene.active_enemy_ids

    # debug opcional
    if out.debug:
        updates.setdefault("debug", {})["narrator"] = out.debug

    return {"text": (out.text or "").strip(), "updates": updates}
