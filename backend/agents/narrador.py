from __future__ import annotations

import json
from typing import Any, Dict

from agents.base import BaseReActAgent
from models.agent_io import AgentInput, AgentOutput
from utils.prompt_loader import load_prompt


def _compact_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """Compacta el estado real para no mandar un JSON enorme al modelo."""
    meta = state.get("meta", {})
    player = state.get("player", {})
    world = state.get("world", {})
    mem = state.get("narrative_memory", {})

    current_scene = world.get("current_scene", {}) or {}
    locations = world.get("locations", {}) or {}

    current_location_id = (
        current_scene.get("location")
        or player.get("location")
        or "inicio"
    )
    current_location_info = locations.get(current_location_id, {}) or {}

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
                # campos opcionales que puede usar el orquestador
                "pending_enemy_type": current_scene.get("pending_enemy_type"),
                "pending_enemy_count": current_scene.get("pending_enemy_count"),
            },
            "visited_locations": world.get("visited_locations", []),
            "pending_locations": world.get("pending_locations", []),
            "locations_ids": list((locations or {}).keys()),
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
        "memory": {
            "summary": mem.get("summary", ""),
            "last_events": (mem.get("last_events", []) or [])[-5:],
        },
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
            "- Si introduces un encuentro hostil, usa scene.type='combat_pending' y pregunta (sí/no).\n"
            "- NO inventes active_enemy_ids ni enemies; eso lo hará el orquestador.\n"
            "- Añade un evento a memory.append_event que resuma el turno.\n"
        )


def narrador_agent(game_state: dict, player_input: str) -> dict:
    """
    Adaptador para mantener compatibilidad con el orquestador actual:
    devuelve dict con keys: text, updates
    devuelve dict con keys: text, updates
    """
    agent = NarratorAgent()
    out: AgentOutput = agent.invoke(AgentInput(player_input=player_input, state=game_state))

    turn = game_state.get("meta", {}).get("turn", 0)
    updates: Dict[str, Any] = {}
    updates: Dict[str, Any] = {}

    # ---- Memoria ----
    # ---- Memoria ----
    if out.memory and out.memory.append_event:
        updates.setdefault("narrative_memory", {})["last_events_append"] = out.memory.append_event
    else:
        updates.setdefault("narrative_memory", {})["last_events_append"] = f"Turno {turn}: jugador -> {player_input}"

    if out.memory and out.memory.summary:
        updates.setdefault("narrative_memory", {})["summary"] = out.memory.summary

    # ---- Movimiento / mundo ----
    # ---- Movimiento / mundo ----
    if out.world and out.world.location:
        # location afecta tanto a player.location como a current_scene.location (mantener coherencia)
        # location afecta tanto a player.location como a current_scene.location (mantener coherencia)
        updates.setdefault("player", {})["location"] = out.world.location
        updates.setdefault("world", {}).setdefault("current_scene", {})["location"] = out.world.location

        updates.setdefault("world", {}).setdefault("current_scene", {})["location"] = out.world.location

    if out.world and out.world.add_visited_location:
        updates.setdefault("world", {})["visited_locations_append"] = out.world.add_visited_location

    # Propuesta de nueva localización (world.propose_location -> orquestador lo mete en world.pending_locations)
    if out.world and getattr(out.world, "propose_location", None):
        updates.setdefault("world", {})["propose_location"] = out.world.propose_location

    if out.world and getattr(out.world, "clear_pending_locations", None):
        if out.world.clear_pending_locations:
            updates.setdefault("world", {})["clear_pending_locations"] = True

    # ---- Escena ----
    # ---- Escena ----
    if out.scene and out.scene.type:
        updates.setdefault("world", {}).setdefault("current_scene", {})["type"] = out.scene.type

    # Campos opcionales para combatir (combat_pending)
    if out.scene and getattr(out.scene, "pending_enemy_type", None):
        updates.setdefault("world", {}).setdefault("current_scene", {})["pending_enemy_type"] = out.scene.pending_enemy_type
    if out.scene and getattr(out.scene, "pending_enemy_count", None) is not None:
        updates.setdefault("world", {}).setdefault("current_scene", {})["pending_enemy_count"] = out.scene.pending_enemy_count


    if out.scene and out.scene.active_enemy_ids is not None:
        updates.setdefault("world", {}).setdefault("current_scene", {})["active_enemy_ids"] = out.scene.active_enemy_ids

    # debug opcional
    if out.debug:
        updates.setdefault("debug", {})["narrator"] = out.debug

    return {"text": (out.text or "").strip(), "updates": updates}