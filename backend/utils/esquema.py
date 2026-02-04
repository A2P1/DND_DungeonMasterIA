from datetime import datetime

def initial_game_state():
    return {
        "meta": {
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "turn": 0
        },

        "player": {
            "id": "player_1",
            "name": "Jugador",
            "class": "Aventurero",
            "level": 1,
            "hp": 20,
            "max_hp": 20,
            # --- Combate (MVP Hito 1) ---
            # Mantenemos "stats" por compatibilidad con versiones anteriores,
            # pero el sistema de combate nuevo usa estos campos:
            "ac": 12,
            "dc": 12,
            "attack_bonus": 2,
            "damage_normal": 5,
            "damage_strong": 9,
            "stats": {
                "attack": 5,
                "defense": 2
            },
            "inventory": [],
            "gold": 0,
            "location": "inicio",
            "status_effects": []  # ej: "poisoned"
        },

        "world": {
            "current_scene": {
                "type": "exploration",  # exploration | combat | dialogue
                "location": "inicio",
                "active_enemy_ids": [],
                "active_npc_ids": []
            },

            "visited_locations": ["inicio"],

            # Lugares propuestos por el narrador en el turno anterior para que el jugador los elija.
            # Formato de cada item: {"id","name","description","connected_from"}
            "pending_locations": [],

            "locations": {
                "inicio": {
                    "name": "Punto de partida",
                    "description": "Un lugar tranquilo donde empieza la aventura.",
                    "connected_to": []
                }
            },

            "enemies": {},     # {"goblin_1": {...}}
            "npcs": {},        # {"npc_1": {...}}
            "items": {},       # {"item_1": {...}}

            "quests": {
                "active": [],
                "completed": []
            }
        },

        "flags": {
            # "boss_bosque_derrotado": False
        },

        "narrative_memory": {
            "summary": "La aventura acaba de comenzar.",
            "last_events": [],
            "important_facts": []  # cosas que NUNCA deben cambiar
        },

        "logs": {
            "actions": []  # historial breve de inputs del jugador
        }
    }