from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Literal

class AgentInput(BaseModel):
    player_input: str
    state: Dict[str, Any]

class WorldUpdate(BaseModel):
    player_hp: Optional[int] = None
    location: Optional[str] = None
    add_visited_location: Optional[str] = None

    # --- Movimiento 100% IA (mapa + pending) ---
    # Propuesta de localización nueva (pendiente) para que el jugador la elija.
    propose_location: Optional[Dict[str, Any]] = None

    # Si el jugador ha elegido entrar a una localización propuesta, limpiamos pendientes.
    clear_pending_locations: Optional[bool] = None

    # Creación de una localización en el mapa (si no existía).
    add_location: Optional[Dict[str, Any]] = None

    # Conexión bidireccional entre dos localizaciones del mapa.
    connect_locations: Optional[List[str]] = None

class MemoryUpdate(BaseModel):
    append_event: Optional[str] = None
    summary: Optional[str] = None

class SceneUpdate(BaseModel):
    type: Optional[Literal["exploration", "combat", "dialogue"]] = None
    active_enemy_ids: Optional[List[str]] = None

class AgentOutput(BaseModel):
    text: str
    memory: Optional[MemoryUpdate] = None
    world: Optional[WorldUpdate] = None
    scene: Optional[SceneUpdate] = None
    debug: Optional[Dict[str, Any]] = None

