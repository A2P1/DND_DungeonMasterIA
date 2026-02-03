from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, Tuple

from config import get_llm
from utils.dados import d20, disadvantage
from utils.prompt_loader import load_prompt


# --- Defaults (Hito 1) ---
DEFAULT_PLAYER = {
    "hp": 20,
    "ac": 12,
    "dc": 12,
    "attack_bonus": 2,
    "damage_normal": 5,
    "damage_strong": 9,
}

DEFAULT_BANDIT = {
    "name": "Bandido",
    "hp": 12,
    "max_hp": 12,
    "ac": 10,
    "attack_bonus": 2,
    "damage_normal": 3,
    "damage_strong": 6,
    "is_alive": True,
    "escaped": False,
}


def _get_player(state: Dict[str, Any]) -> Dict[str, Any]:
    p = state.setdefault("player", {})
    # Fill defaults if missing
    for k, v in DEFAULT_PLAYER.items():
        p.setdefault(k, v)
    # Keep max_hp coherent
    p.setdefault("max_hp", p.get("hp", DEFAULT_PLAYER["hp"]))
    return p


def _ensure_scene(state: Dict[str, Any]) -> Dict[str, Any]:
    w = state.setdefault("world", {})
    scene = w.setdefault("current_scene", {})
    scene.setdefault("type", "exploration")
    scene.setdefault("location", state.get("player", {}).get("location", "inicio"))
    scene.setdefault("active_enemy_ids", [])
    scene.setdefault("active_npc_ids", [])
    # Combat status flags
    status = scene.setdefault("combat_status", {})
    status.setdefault("player_skip_next", False)
    status.setdefault("enemy_skip_next", False)
    status.setdefault("enemy_disadvantage", False)
    return scene


def _ensure_enemy(state: Dict[str, Any], enemy_id: str) -> Dict[str, Any]:
    enemies = state.setdefault("world", {}).setdefault("enemies", {})
    enemy = enemies.setdefault(enemy_id, {})
    for k, v in DEFAULT_BANDIT.items():
        enemy.setdefault(k, v)
    enemy.setdefault("id", enemy_id)
    enemy.setdefault("max_hp", enemy.get("hp", DEFAULT_BANDIT["hp"]))
    return enemy


def _choose_active_enemy(state: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    scene = _ensure_scene(state)
    enemies = state.get("world", {}).get("enemies", {}) or {}
    for eid in scene.get("active_enemy_ids", []) or []:
        e = enemies.get(eid)
        if e and e.get("is_alive", True) and not e.get("escaped", False):
            _ensure_enemy(state, eid)
            return eid, state["world"]["enemies"][eid]
    return None


def _parse_player_action(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["huir", "huyo", "escapar", "escapo", "corro"]):
        return "flee"
    if "empuj" in t:
        return "push"
    if any(k in t for k in ["esquivo", "esquivar", "dodge"]):
        return "dodge"
    if any(k in t for k in ["defiendo", "defender", "bloqueo", "paro"]):
        return "defend"
    if "fuerte" in t:
        return "attack_strong"
    if any(k in t for k in ["ataco", "atacar", "golpeo", "pego", "ataque"]):
        return "attack_normal"
    # Default en combate: atacar
    return "attack_normal"


def _attack_roll(attack_bonus: int, target_ac: int, strong: bool = False, with_disadvantage: bool = False) -> Tuple[int, int, bool]:
    base = disadvantage() if with_disadvantage else d20()
    penalty = 0
    if strong:
        penalty = 2  # más difícil
    total = base + attack_bonus - penalty
    hit = total >= target_ac
    return base, total, hit


def _bandit_decision(enemy: Dict[str, Any]) -> str:
    # Huye cuando HP <= 2 (según tu especificación)
    if int(enemy.get("hp", 0)) <= 2:
        return "shout_flee"
    # 25% fuerte, 75% normal
    return "attack_strong" if random.random() < 0.25 else "attack_normal"


def _cleanup_scene_after_enemy_list(state: Dict[str, Any]) -> None:
    scene = _ensure_scene(state)
    enemies = state.get("world", {}).get("enemies", {}) or {}
    alive_ids = []
    for eid in scene.get("active_enemy_ids", []) or []:
        e = enemies.get(eid)
        if not e:
            continue
        if e.get("is_alive", True) and not e.get("escaped", False):
            alive_ids.append(eid)
    scene["active_enemy_ids"] = alive_ids
    if not alive_ids and scene.get("type") == "combat":
        scene["type"] = "exploration"


def combat_step(state: Dict[str, Any], player_input: str) -> Dict[str, Any]:
    """Resuelve un turno de combate (numérico) y aplica cambios directos al state."""
    player = _get_player(state)
    scene = _ensure_scene(state)
    status = scene.setdefault("combat_status", {})
    action = _parse_player_action(player_input)

    active = _choose_active_enemy(state)
    if not active:
        return {"error": "No hay enemigo activo en la escena.", "combat_ended": True}

    enemy_id, enemy = active

    # --- Si el jugador está aturdido, pierde su acción ---
    player_skipped = False
    if status.get("player_skip_next", False):
        status["player_skip_next"] = False
        player_skipped = True
        action = "skip"

    # --- Turno del jugador ---
    player_event = {"action": action}
    combat_ended = False

    if action == "flee":
        roll = d20()
        success = roll >= int(player.get("dc", 12))
        player_event.update({"roll": roll, "success": success})
        if success:
            # Sale del combate
            scene["type"] = "exploration"
            scene["active_enemy_ids"] = []
            combat_ended = True
        # si falla, el enemigo tendrá su turno normal

    elif action in ("push", "dodge", "defend"):
        roll = d20()
        success = roll >= int(player.get("dc", 12))
        player_event.update({"roll": roll, "success": success})

        if success:
            if action == "push":
                status["enemy_skip_next"] = True
            elif action == "dodge":
                status["enemy_disadvantage"] = True
            elif action == "defend":
                status["enemy_skip_next"] = True

    elif action in ("attack_normal", "attack_strong"):
        strong = action == "attack_strong"
        base, total, hit = _attack_roll(int(player.get("attack_bonus", 2)), int(enemy.get("ac", 10)), strong=strong)
        dmg = int(player.get("damage_strong" if strong else "damage_normal", 0)) if hit else 0
        enemy["hp"] = max(0, int(enemy.get("hp", 0)) - dmg)
        if enemy["hp"] <= 0:
            enemy["is_alive"] = False
            combat_ended = True

        player_event.update({
            "attack_roll": base,
            "attack_total": total,
            "hit": hit,
            "damage": dmg,
        })

    elif action == "skip":
        player_event.update({"skipped": True})

    # --- Si el jugador ha escapado o el enemigo ha muerto, no ataca el enemigo ---
    if combat_ended:
        _cleanup_scene_after_enemy_list(state)
        return {
            "enemy_id": enemy_id,
            "enemy_name": enemy.get("name", enemy_id),
            "player": player_event,
            "enemy": None,
            "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
            "enemy_dead": not enemy.get("is_alive", True),
            "player_dead": int(player.get("hp", 0)) <= 0,
            "combat_ended": True,
            "player_skipped": player_skipped,
        }

    # --- Turno del enemigo ---
    enemy_event: Dict[str, Any] = {"action": None}
    enemy_skipped = False

    if status.get("enemy_skip_next", False):
        status["enemy_skip_next"] = False
        enemy_skipped = True
        enemy_event = {"action": "skip", "skipped": True}
    else:
        enemy_action = _bandit_decision(enemy)
        enemy_event["action"] = enemy_action

        if enemy_action == "shout_flee":
            roll = d20()
            success = roll >= int(player.get("dc", 12))
            enemy_event.update({"roll": roll, "success": success})
            if success:
                # Paraliza al jugador 1 turno y huye
                status["player_skip_next"] = True
                enemy["escaped"] = True
                scene["active_enemy_ids"] = [eid for eid in scene.get("active_enemy_ids", []) if eid != enemy_id]
                _cleanup_scene_after_enemy_list(state)
                return {
                    "enemy_id": enemy_id,
                    "enemy_name": enemy.get("name", enemy_id),
                    "player": player_event,
                    "enemy": enemy_event,
                    "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
                    "enemy_dead": False,
                    "player_dead": int(player.get("hp", 0)) <= 0,
                    "combat_ended": scene.get("type") != "combat",
                    "enemy_skipped": enemy_skipped,
                    "player_skipped": player_skipped,
                }

        elif enemy_action in ("attack_normal", "attack_strong"):
            strong = enemy_action == "attack_strong"
            with_disadv = bool(status.get("enemy_disadvantage", False))
            status["enemy_disadvantage"] = False

            # strong: un poco más difícil (penalty handled in _attack_roll)
            base, total, hit = _attack_roll(int(enemy.get("attack_bonus", 2)), int(player.get("ac", 12)), strong=strong, with_disadvantage=with_disadv)
            dmg = int(enemy.get("damage_strong" if strong else "damage_normal", 0)) if hit else 0
            player["hp"] = max(0, int(player.get("hp", 0)) - dmg)

            enemy_event.update({
                "attack_roll": base,
                "attack_total": total,
                "hit": hit,
                "damage": dmg,
                "disadvantage": with_disadv,
            })

    player_dead = int(player.get("hp", 0)) <= 0
    combat_ended = player_dead
    if player_dead:
        # Por simplicidad, salimos de combate
        scene["type"] = "exploration"
        scene["active_enemy_ids"] = []

    _cleanup_scene_after_enemy_list(state)

    return {
        "enemy_id": enemy_id,
        "enemy_name": enemy.get("name", enemy_id),
        "player": player_event,
        "enemy": enemy_event,
        "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
        "enemy_dead": not enemy.get("is_alive", True),
        "player_dead": player_dead,
        "combat_ended": scene.get("type") != "combat",
        "enemy_skipped": enemy_skipped,
        "player_skipped": player_skipped,
    }


def combat_agent(game_state: dict, player_input: str) -> dict:
    """Agente de combate:
    - Resuelve números en Python (combat_step)
    - Pide al LLM una narración usando ese resumen
    - Devuelve updates para que el orquestador persista estado
    """

    llm = get_llm(role="combat")
    summary = combat_step(game_state, player_input)

    # Prompt del narrador de combate
    system_prompt = load_prompt("sistema_combate.txt")

    user_message = f"""
RESUMEN NUMÉRICO (no inventes nada fuera de esto):
{json.dumps(summary, indent=2, ensure_ascii=False)}
"""

    from langchain_core.messages import SystemMessage, HumanMessage

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ])
    text = response.content if hasattr(response, "content") else str(response)

    turn = game_state.get("meta", {}).get("turn", 0)

    # Updates mínimos: HP jugador, current_scene completo (para no machacar campos) y memoria
    scene = game_state.get("world", {}).get("current_scene", {}) or {}
    updates = {
        "player": {"hp": game_state.get("player", {}).get("hp", 0)},
        "world": {
            "current_scene": {
                "type": scene.get("type", "exploration"),
                "location": scene.get("location", "inicio"),
                "active_enemy_ids": scene.get("active_enemy_ids", []),
                "active_npc_ids": scene.get("active_npc_ids", []),
                "combat_status": scene.get("combat_status", {})
            }
        },
        "narrative_memory": {
            "last_events_append": f"Turno {turn}: combate -> {summary.get('enemy_name','enemigo')} (HP jugador {summary.get('hp_after',{}).get('player_hp')})"
        }
    }

    return {"text": text, "updates": updates, "summary": summary}