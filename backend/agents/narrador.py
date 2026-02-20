from __future__ import annotations

import json
from typing import Any, Dict

from agents.base import BaseReActAgent
from models.agent_io import AgentInput, AgentOutput
from utils.prompt_loader import load_prompt

# Hace un resumen compacto del estado para que el narrador pueda usarlo a modo de información histórica
def _compact_context(state: Dict[str, Any]) -> Dict[str, Any]:
    meta = state.get("meta", {}) #Turnos
    player = state.get("player", {}) #Stats
    world = state.get("world", {}) #Escena actual
    mem = state.get("narrative_memory", {}) #Resummen y eventos previos

    #Almacena la información de la escena actual y la ubicación del jugador para que la historia pueda mantener la coherencia
    current_scene = world.get("current_scene", {}) or {}
    locations = world.get("locations", {}) or {}

    current_location_id = (
        current_scene.get("location")
        or player.get("location")
        or "inicio"
    )
    current_location_info = locations.get(current_location_id, {}) or {}
    # Devolvemos un dict con la info necesaria para que el narrador sepa en qué punto de la historia se encuentra
    return {
        # Enviamos únicamente la información importante del jugador
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
        # Información del estado del mundo, así como la localización, ambiente, enemigos, etc.
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
        # Po último, un resumen de la memoria narrativa y los últimos eventos detectados
        "memory": {
            "summary": mem.get("summary", ""),
            "last_events": (mem.get("last_events", []) or [])[-5:],
        },
    }


# Esta clase hereda de BaseReActAgent
class NarratorAgent(BaseReActAgent):
    def __init__(self):
        super().__init__(role="narrator")
    # Cargamos el prompt del narrador que es un fichero txt
    def system_prompt(self) -> str:
        return load_prompt("sistema_narrador.txt")

    #Función para el turno del usuario de hablar
    def user_prompt(self, inp: AgentInput) -> str:
        context = _compact_context(inp.state)

        return (
            # Primero, cargamos un resumen de la historia al narrador hasta el momento, para que sepa en qué punto se encuentra
            # Si no le pasamos un resumen, cada vez que le toque hablar al narrador, contaría una cosa distinta sin sentido alguno
            "ESTADO ACTUAL (resumen):\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            # Después, el usuario escribe su texto, y le damos una serie de indicaciones para que cuente una historia a partir de lo que ha escrito el usuario, coherente a lo que ha pasado hasta ahora
            "ACCIÓN DEL JUGADOR:\n"
            f"{inp.player_input}\n\n"
            "Instrucciones:\n"
            "- Continúa la historia de forma coherente.\n"
            "- Si el jugador se mueve, usa world.location (id del lugar) y world.add_visited_location.\n"
            "- Si introduces un encuentro hostil, usa scene.type='combat_pending' y pregunta (sí/no).\n"
            "- NO inventes active_enemy_ids ni enemies; eso lo hará el orquestador.\n"
            "- Añade un evento a memory.append_event que resuma el turno.\n" 
            # Volvemos a resumir lo que ha comentado el narrador, para su próxima interacción 
        )


# Función que adapta todas las funciones del narrador a un formato que el orquestador actual pueda entender. Esta es la función que el orquestador va a llamar cada vez que quiera dar paso al narrador
def narrador_agent(game_state: dict, player_input: str) -> dict:

    # Creamos el agente narrador cada vez que se le llama, después se ejecuta
    agent = NarratorAgent()
    out: AgentOutput = agent.invoke(AgentInput(player_input=player_input, state=game_state))

    # Se inicializa la variable de turnos
    turn = game_state.get("meta", {}).get("turn", 0)
    updates: Dict[str, Any] = {}

   
    # Actualizamos la memoria narrativa del agente, para construir una historia coherente.
    if out.memory and out.memory.append_event:
        updates.setdefault("narrative_memory", {})["last_events_append"] = out.memory.append_event
    else:
        updates.setdefault("narrative_memory", {})["last_events_append"] = f"Turno {turn}: jugador -> {player_input}"

    if out.memory and out.memory.summary:
        updates.setdefault("narrative_memory", {})["summary"] = out.memory.summary

   
    # Si el jugador se mueve, se actualiza el mundo y la localización del jugador.
    if out.world and out.world.location:
       # location afecta tanto a player.location como a current_scene.location (mantener coherencia)
        updates.setdefault("player", {})["location"] = out.world.location
        updates.setdefault("world", {}).setdefault("current_scene", {})["location"] = out.world.location

        
    # Si el jugador visita una localización ya visitada, esta se añade a visited_locations para que no se "redescubra" la localización (No es mejor comprobar si ya se ha visitado la localización y no hacer nada, en vez de añadir tanto espacio?)
    if out.world and out.world.add_visited_location:
        updates.setdefault("world", {})["visited_locations_append"] = out.world.add_visited_location

    # Guardamos en "propose_location" la localización que ha mencionado el narrador. 
    # A veces pasaba que si el narrador mencionaba un "bosque" y el jugador dice "Entro en el bosque", el narrador lo interpreta como una localización que no estaba ahí.
    # Por eso, guardamos la localización mencionada, para que el narrador no se vuelva loco
    if out.world and getattr(out.world, "propose_location", None):
        updates.setdefault("world", {})["propose_location"] = out.world.propose_location

    # Cuando el jugador decide si ir a la localización propuesta, se elimina la localización de "propose_location" y se añade a "localización_actual"
    # Si el jugador decide NO ir a la localización propuesta, no se elimina la localización de "propose_location", en caso de que el jugador quiera volver a ese sitio propuesto más adelante
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