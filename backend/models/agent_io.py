from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

class AgentInput(BaseModel):
    player_input: str
    state: Dict[str, Any]

class WorldUpdate(BaseModel):
    player_hp: Optional[int] = None
    location: Optional[str] = None
    add_visited_location: Optional[str] = None

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
