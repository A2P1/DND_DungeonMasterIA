from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Literal

class AgentInput(BaseModel):
    player_input: str
    state: Dict[str, Any]

class WorldUpdate(BaseModel):
    """Campos del mundo que el narrador puede proponer.

    IMPORTANTE: permitimos campos extra para que el prompt pueda evolucionar
    sin romper el parseo (pydantic extra=allow).
    """

    player_hp: Optional[int] = None
    location: Optional[str] = None
    add_visited_location: Optional[str] = None

    # Movimiento / mapa (opcionales)
    propose_location: Optional[Dict[str, Any]] = None
    clear_pending_locations: Optional[bool] = None
    add_location: Optional[Dict[str, Any]] = None
    connect_locations: Optional[List[str]] = None

    class Config:
        extra = "allow"

class MemoryUpdate(BaseModel):
    append_event: Optional[str] = None
    summary: Optional[str] = None

class SceneUpdate(BaseModel):
    type: Optional[Literal["exploration", "combat_pending", "combat", "dialogue"]] = None
    active_enemy_ids: Optional[List[str]] = None

    # Opcionales para que el orquestador pueda spawnear enemigos
    pending_enemy_type: Optional[str] = None
    pending_enemy_count: Optional[int] = None

    class Config:
        extra = "allow"

class AgentOutput(BaseModel):
    text: str
    memory: Optional[MemoryUpdate] = None
    world: Optional[WorldUpdate] = None
    scene: Optional[SceneUpdate] = None
    debug: Optional[Dict[str, Any]] = None

