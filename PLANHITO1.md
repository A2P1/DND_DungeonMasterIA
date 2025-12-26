# Plan Completo: Hito 1 - Campaña D&D con Arquitectura ReAct Multi-Agente

Implementar MVP funcional donde el jugador interactúa por CLI con una mini campaña D&D orquestada. Arquitectura basada en clase `BaseReActAgent` con herencia para narrador y combate, preparada para agregar tools en futuro. El orquestador detecta y cambia entre agentes automáticamente, persistiendo todo en game_state.json.

---

## **FASE 1: INFRAESTRUCTURA BASE**

### **Paso 1: Configurar Dependencias y Archivos Faltantes**

**1.1** Crear archivo `.env` en raíz del proyecto
   - Agregar línea: `OPENAI_API_KEY=tu-clave-aqui`
   - Documentar en README.md cómo obtener la key

**1.2** Poblar [requerimientos.py](backend/requerimientos.py)
   - Agregar dependencias:
     ```
     langchain==0.1.0
     langchain-openai==0.0.2
     python-dotenv==1.0.0
     pydantic==2.5.0
     ```

**1.3** Crear archivos `__init__.py` faltantes
   - Crear [backend/agents/__init__.py](backend/agents/__init__.py) vacío
   - Crear [backend/utils/__init__.py](backend/utils/__init__.py) vacío

**1.4** Validación rápida de API key
   - Crear archivo temporal `test_openai.py` en raíz
   - Hacer una llamada simple: `ChatOpenAI(model="gpt-3.5-turbo").invoke("Di hola")`
   - Verificar que responde correctamente
   - Eliminar archivo temporal

---

### **Paso 2: Implementar Sistema de Configuración**

**2.1** Escribir [config.py](backend/config.py) - Gestión de entorno
   ```python
   from dotenv import load_dotenv
   import os
   
   def load_env():
       """Carga variables de entorno"""
       load_dotenv()
       if not os.getenv("OPENAI_API_KEY"):
           raise ValueError("OPENAI_API_KEY no encontrada")
   ```

**2.2** Agregar factory de LLMs en [config.py](backend/config.py)
   ```python
   from langchain_openai import ChatOpenAI
   
   LLM_CONFIGS = {
       "narrator": {"model": "gpt-4o-mini", "temperature": 0.8, "max_tokens": 500},
       "combat": {"model": "gpt-3.5-turbo", "temperature": 0.3, "max_tokens": 400}
   }
   
   def get_llm(agent_type: str) -> ChatOpenAI:
       """Retorna LLM configurado según tipo de agente"""
       config = LLM_CONFIGS.get(agent_type)
       return ChatOpenAI(**config)
   ```

**2.3** Agregar función para instanciar agentes
   ```python
   def get_agent(agent_type: str):
       """Factory de agentes (implementar después de crear clases)"""
       # Placeholder por ahora
       pass
   ```

---

## **FASE 2: ARQUITECTURA ReAct CON HERENCIA**

### **Paso 3: Crear Modelos Pydantic para ReAct y Respuestas**

**3.1** Extender [esquema.py](backend/utils/esquema.py) - Modelo de pensamiento ReAct
   ```python
   from pydantic import BaseModel, Field
   from typing import Optional, List
   
   class ThoughtStep(BaseModel):
       """Paso de razonamiento ReAct"""
       thought: str = Field(description="Razonamiento interno del agente")
       action: str = Field(description="'continue' para seguir pensando, 'final_answer' para terminar")
       observation: Optional[str] = Field(default=None, description="Auto-reflexión sobre el pensamiento")
       final_answer: Optional[str] = Field(default=None, description="Respuesta final si action='final_answer'")
   ```

**3.2** Agregar modelo de respuesta del narrador
   ```python
   class NarratorResponse(BaseModel):
       """Respuesta estructurada del narrador con señales de routing"""
       narration: str = Field(description="Texto narrativo para mostrar al jugador")
       scene_updates: dict = Field(default_factory=dict, description="Cambios en la escena actual")
       switch_to_agent: Optional[str] = Field(default=None, description="'combat' si debe activarse combate")
       reasoning_steps: List[str] = Field(default_factory=list, description="Pasos de pensamiento ReAct")
   ```

**3.3** Agregar modelo de respuesta de combate
   ```python
   class CombatResponse(BaseModel):
       """Respuesta estructurada del agente de combate"""
       narration: str = Field(description="Descripción de acciones de combate")
       combat_updates: dict = Field(default_factory=dict, description="Cambios en HP, estados, etc")
       combat_ended: bool = Field(default=False, description="True si el combate terminó")
       reasoning_steps: List[str] = Field(default_factory=list, description="Pasos ReAct del combate")
   ```

---

### **Paso 4: Implementar Clase Base ReActAgent**

**4.1** Crear [base_agent.py](backend/agents/base_agent.py) - Estructura abstracta
   ```python
   from abc import ABC, abstractmethod
   from langchain_openai import ChatOpenAI
   from typing import List, Optional
   from backend.utils.esquema import ThoughtStep
   
   class BaseReActAgent(ABC):
       """Clase base para todos los agentes con patrón ReAct"""
       
       def __init__(self, llm: ChatOpenAI, max_reasoning_steps: int = 3):
           self.llm = llm
           self.max_reasoning_steps = max_reasoning_steps
           self.tools = []  # Preparado para futuras tools
           self.agent_name = self.__class__.__name__
   ```

**4.2** Implementar método de razonamiento ReAct en [base_agent.py](backend/agents/base_agent.py)
   ```python
   def _react_loop(self, game_state: dict, player_input: str) -> List[ThoughtStep]:
       """Ejecuta loop de razonamiento ReAct sin tools"""
       thoughts = []
       context = self._build_context(game_state, player_input)
       
       for step in range(self.max_reasoning_steps):
           prompt = self._build_react_prompt(context, thoughts)
           structured_llm = self.llm.with_structured_output(ThoughtStep)
           thought = structured_llm.invoke(prompt)
           thoughts.append(thought)
           
           if thought.action == "final_answer":
               break
               
       return thoughts
   ```

**4.3** Agregar métodos abstractos y helpers
   ```python
   @abstractmethod
   def _build_context(self, game_state: dict, player_input: str) -> str:
       """Subclases deben extraer contexto relevante del estado"""
       pass
   
   @abstractmethod
   def _build_react_prompt(self, context: str, history: List[ThoughtStep]) -> str:
       """Subclases deben construir prompt específico para ReAct"""
       pass
   
   @abstractmethod
   def execute(self, game_state: dict, player_input: str) -> dict:
       """Método principal que cada agente debe implementar"""
       pass
   ```

**4.4** Agregar método preparado para tools futuras
   ```python
   def add_tool(self, tool):
       """Agrega una tool al agente (para fase posterior)"""
       self.tools.append(tool)
       # TODO: Inyectar en prompt cuando se implementen
   ```

---

## **FASE 3: AGENTE NARRADOR CON INTELIGENCIA DE ROUTING**

### **Paso 5: Diseñar Sistema de Prompts para Narrador**

**5.1** Crear [sistema_narrador.py](backend/prompts/sistema_narrador.py) - Prompt base ReAct
   ```python
   NARRATOR_REACT_SYSTEM = """Eres el Dungeon Master de una campaña D&D siguiendo patrón ReAct.

Tu trabajo es:
1. ANALIZAR la acción del jugador y el estado del mundo
2. RAZONAR paso a paso qué debe ocurrir
3. DECIDIR si la situación requiere cambiar a combate
4. GENERAR narrativa inmersiva

PATRÓN ReAct (sin tools externas por ahora):
- Thought: Tu razonamiento interno
- Action: 'continue' para seguir pensando, 'final_answer' cuando tengas la respuesta
- Observation: Reflexiona sobre tu pensamiento

DETECCIÓN DE COMBATE:
Si el jugador dice "atacar/luchar/pelear" O hay enemigos hostiles presentes:
- En tu respuesta final, marca switch_to_agent: "combat"
- Actualiza scene.type a "combat" en scene_updates
"""
   ```

**5.2** Agregar función generadora de prompt contextual
   ```python
   def get_narrator_prompt(game_state: dict, player_input: str, thought_history: List) -> str:
       """Construye prompt con contexto completo"""
       current_scene = game_state['world']['scenes'][game_state['player']['location']]
       nearby_enemies = [e for e in game_state['world']['enemies'] 
                         if e.get('location') == game_state['player']['location']]
       
       prompt = f"""{NARRATOR_REACT_SYSTEM}

ESTADO ACTUAL:
- Ubicación: {game_state['player']['location']}
- Escena: {current_scene.get('description', 'Unknown')}
- Tipo actual: {current_scene.get('type', 'exploration')}
- HP Jugador: {game_state['player']['hp']}/{game_state['player']['max_hp']}
- Enemigos cercanos: {[e['name'] for e in nearby_enemies]}

HISTORIAL NARRATIVO:
{game_state['narrative_memory']['summary']}

ACCIÓN DEL JUGADOR:
"{player_input}"

PASOS PREVIOS DE PENSAMIENTO:
{thought_history}

Piensa paso a paso y genera tu respuesta final."""
       return prompt
   ```

---

### **Paso 6: Implementar NarratorAgent Heredando de Base**

**6.1** Reescribir [narrador.py](backend/agents/narrador.py) - Estructura de clase
   ```python
   from backend.agents.base_agent import BaseReActAgent
   from backend.utils.esquema import NarratorResponse, ThoughtStep
   from backend.prompts.sistema_narrador import get_narrator_prompt
   from typing import List
   
   class NarratorAgent(BaseReActAgent):
       """Agente narrador con capacidad de routing a otros agentes"""
       
       def __init__(self, llm, max_reasoning_steps=3):
           super().__init__(llm, max_reasoning_steps)
   ```

**6.2** Implementar métodos abstractos del narrador
   ```python
   def _build_context(self, game_state: dict, player_input: str) -> str:
       """Extrae ubicación, escena, enemigos cercanos"""
       location = game_state['player']['location']
       scene = game_state['world']['scenes'].get(location, {})
       enemies = [e for e in game_state['world']['enemies'] 
                  if e.get('location') == location and e.get('is_alive', True)]
       
       return f"Location: {location}, Scene: {scene}, Enemies: {enemies}, Input: {player_input}"
   
   def _build_react_prompt(self, context: str, history: List[ThoughtStep]) -> str:
       """Delega a la función del módulo de prompts"""
       # Parsear context de vuelta a componentes (temporal, mejorar después)
       return get_narrator_prompt(self.cached_state, self.cached_input, history)
   ```

**6.3** Implementar execute() principal del narrador
   ```python
   def execute(self, game_state: dict, player_input: str) -> NarratorResponse:
       """Ejecuta razonamiento ReAct y genera respuesta con posible routing"""
       # Cachear para use en _build_react_prompt
       self.cached_state = game_state
       self.cached_input = player_input
       
       # Ejecutar loop ReAct
       thoughts = self._react_loop(game_state, player_input)
       
       # Parsear respuesta final estructurada
       final_prompt = self._build_final_answer_prompt(game_state, player_input, thoughts)
       structured_llm = self.llm.with_structured_output(NarratorResponse)
       response = structured_llm.invoke(final_prompt)
       
       # Agregar pasos de razonamiento a la respuesta
       response.reasoning_steps = [t.thought for t in thoughts]
       
       return response
   ```

**6.4** Agregar prompt para respuesta final estructurada
   ```python
   def _build_final_answer_prompt(self, game_state, player_input, thoughts):
       """Prompt para generar NarratorResponse estructurada"""
       thought_summary = "\n".join([f"- {t.thought}" for t in thoughts])
       
       return f"""Basándote en tu razonamiento previo, genera la respuesta final estructurada.

TUS PENSAMIENTOS:
{thought_summary}

GENERA:
- narration: Texto inmersivo para el jugador (2-4 frases)
- scene_updates: Dict con cambios (ej: {{"type": "combat"}} si procede)
- switch_to_agent: "combat" SOLO si detectaste situación de combate
- reasoning_steps: Lista vacía (se llenará automáticamente)

Estado: {game_state['player']['location']}
Input: "{player_input}"
"""
   ```

---

## **FASE 4: AGENTE DE COMBATE**

### **Paso 7: Diseñar Sistema de Prompts para Combate**

**7.1** Crear [sistema_combate.py](backend/prompts/sistema_combate.py) - Prompt ReAct de combate
   ```python
   COMBAT_REACT_SYSTEM = """Eres el sistema de combate D&D 5e siguiendo patrón ReAct.

MECÁNICAS D&D 5e:
- Tiradas de ataque: d20 + modificador vs AC del objetivo
- Daño: Dado específico del arma + modificador
- Crítico: Natural 20 = daño x2
- Fallo crítico: Natural 1 = fallo automático

PATRÓN ReAct:
- Thought: Analiza la acción de combate y stats
- Action: 'continue' o 'final_answer'
- Observation: Reflexiona sobre resultado

FINALIZACIÓN:
Marca combat_ended=True cuando:
- Todos los enemigos HP <= 0
- Jugador HP <= 0
- Jugador huye exitosamente
"""
   ```

**7.2** Agregar función generadora de prompt de combate
   ```python
   def get_combat_prompt(game_state: dict, player_input: str, thought_history: List) -> str:
       """Construye prompt de combate con stats"""
       player = game_state['player']
       location = player['location']
       enemies_in_combat = [e for e in game_state['world']['enemies'] 
                            if e.get('location') == location and e.get('is_alive', True)]
       
       prompt = f"""{COMBAT_REACT_SYSTEM}

COMBATIENTES:
Jugador:
- HP: {player['hp']}/{player['max_hp']}
- Nivel: {player.get('level', 1)}
- Bonificador ATK: +{player.get('attack_bonus', 2)}
- Arma: {player.get('weapon', 'espada corta')} (daño: 1d6+2)

Enemigos:
{_format_enemies(enemies_in_combat)}

TURNO ANTERIOR:
{game_state.get('narrative_memory', {}).get('events', [])[-1] if game_state.get('narrative_memory', {}).get('events') else 'Inicio de combate'}

ACCIÓN DEL JUGADOR:
"{player_input}"

PENSAMIENTOS PREVIOS:
{thought_history}

Resuelve la acción paso a paso."""
       return prompt
   
   def _format_enemies(enemies):
       """Formatea lista de enemigos para el prompt"""
       return "\n".join([f"- {e['name']}: HP {e.get('hp', 7)}/{e.get('max_hp', 7)}, AC {e.get('ac', 13)}, ATK +{e.get('attack_bonus', 4)} (dmg: {e.get('damage', '1d6+2')})"
                         for e in enemies])
   ```

---

### **Paso 8: Implementar CombatAgent Heredando de Base**

**8.1** Escribir [combate.py](backend/agents/combate.py) - Estructura de clase
   ```python
   from backend.agents.base_agent import BaseReActAgent
   from backend.utils.esquema import CombatResponse, ThoughtStep
   from backend.prompts.sistema_combate import get_combat_prompt
   from typing import List
   import random
   
   class CombatAgent(BaseReActAgent):
       """Agente de combate con mecánicas D&D 5e"""
       
       def __init__(self, llm, max_reasoning_steps=2):
           super().__init__(llm, max_reasoning_steps)
           self.max_combat_turns = 20
           self.turn_counter = 0
   ```

**8.2** Implementar métodos abstractos del combate
   ```python
   def _build_context(self, game_state: dict, player_input: str) -> str:
       """Extrae stats de combatientes"""
       player_hp = game_state['player']['hp']
       enemies = [e for e in game_state['world']['enemies'] 
                  if e.get('location') == game_state['player']['location'] 
                  and e.get('is_alive', True)]
       return f"Player HP: {player_hp}, Enemies: {len(enemies)}, Action: {player_input}"
   
   def _build_react_prompt(self, context: str, history: List[ThoughtStep]) -> str:
       """Delega a función de prompts"""
       return get_combat_prompt(self.cached_state, self.cached_input, history)
   ```

**8.3** Implementar execute() con resolución de combate
   ```python
   def execute(self, game_state: dict, player_input: str) -> CombatResponse:
       """Ejecuta turno de combate con ReAct"""
       self.cached_state = game_state
       self.cached_input = player_input
       
       # Incrementar contador anti-loop
       self.turn_counter += 1
       
       # ReAct loop para analizar acción
       thoughts = self._react_loop(game_state, player_input)
       
       # Generar respuesta estructurada
       final_prompt = self._build_combat_result_prompt(game_state, player_input, thoughts)
       structured_llm = self.llm.with_structured_output(CombatResponse)
       response = structured_llm.invoke(final_prompt)
       
       # Forzar fin si excede turnos máximos
       if self.turn_counter >= self.max_combat_turns:
           response.combat_ended = True
           response.narration += "\n[El combate se alarga demasiado. Ambos combatientes se separan exhaustos.]"
       
       # Procesar turno de enemigos si el combate continúa
       if not response.combat_ended:
           enemy_actions = self._process_enemy_turns(game_state)
           response.narration += "\n\n" + enemy_actions
       
       response.reasoning_steps = [t.thought for t in thoughts]
       return response
   ```

**8.4** Implementar lógica de turnos enemigos
   ```python
   def _process_enemy_turns(self, game_state: dict) -> str:
       """Simula turnos de todos los enemigos vivos"""
       player = game_state['player']
       location = player['location']
       enemies = [e for e in game_state['world']['enemies'] 
                  if e.get('location') == location and e.get('is_alive', True)]
       
       narratives = []
       for enemy in enemies:
           # Tirada de ataque
           roll = random.randint(1, 20)
           atk_bonus = enemy.get('attack_bonus', 4)
           total = roll + atk_bonus
           player_ac = player.get('ac', 15)
           
           if roll == 1:
               narratives.append(f"{enemy['name']} falla estrepitosamente su ataque!")
           elif roll == 20 or total >= player_ac:
               # Calcular daño
               damage_dice = enemy.get('damage', '1d6+2')
               damage = self._roll_damage(damage_dice)
               if roll == 20:
                   damage *= 2
               narratives.append(f"{enemy['name']} impacta (tirada: {roll}+{atk_bonus}={total}) causando {damage} de daño!")
               # Actualizar HP en combat_updates (se hará en orquestador)
           else:
               narratives.append(f"{enemy['name']} ataca pero falla (tirada: {roll}+{atk_bonus}={total} vs AC {player_ac}).")
       
       return " ".join(narratives)
   
   def _roll_damage(self, notation: str) -> int:
       """Parsea notación XdY+Z y retorna daño"""
       # Simplificado: solo soporta formato "1d6+2"
       import re
       match = re.match(r'(\d+)d(\d+)\+(\d+)', notation)
       if match:
           num_dice, die_size, bonus = map(int, match.groups())
           return sum(random.randint(1, die_size) for _ in range(num_dice)) + bonus
       return 1
   ```

**8.5** Agregar prompt para respuesta final de combate
   ```python
   def _build_combat_result_prompt(self, game_state, player_input, thoughts):
       """Prompt para generar CombatResponse estructurada"""
       thought_summary = "\n".join([f"- {t.thought}" for t in thoughts])
       enemies_alive = len([e for e in game_state['world']['enemies'] 
                           if e.get('location') == game_state['player']['location'] 
                           and e.get('is_alive', True)])
       
       return f"""Genera el resultado estructurado del turno de combate.

TUS ANÁLISIS:
{thought_summary}

GENERA:
- narration: Descripción cinematográfica del ataque/acción (2-3 frases)
- combat_updates: Dict con cambios (ej: {{"enemy_goblin_hp": 2, "player_hp": 8}})
- combat_ended: True SI todos enemigos muertos O jugador muerto O jugador huyó
- reasoning_steps: Lista vacía

Acción jugador: "{player_input}"
Enemigos vivos: {enemies_alive}
"""
   ```

---

## **FASE 5: ORQUESTACIÓN INTELIGENTE**

### **Paso 9: Actualizar Config con Factory de Agentes**

**9.1** Completar función `get_agent()` en [config.py](backend/config.py)
   ```python
   from backend.agents.narrador import NarratorAgent
   from backend.agents.combate import CombatAgent
   
   def get_agent(agent_type: str):
       """Factory que retorna instancia del agente apropiado"""
       llm = get_llm(agent_type)
       
       if agent_type == "narrator":
           return NarratorAgent(llm, max_reasoning_steps=3)
       elif agent_type == "combat":
           return CombatAgent(llm, max_reasoning_steps=2)
       else:
           raise ValueError(f"Tipo de agente desconocido: {agent_type}")
   ```

---

### **Paso 10: Implementar Lógica de Switching en Orquestador**

**10.1** Refactorizar [orquestador.py](backend/orquestador.py) - Agregar imports
   ```python
   from backend.config import load_env, get_agent
   from backend.utils.esquema import NarratorResponse, CombatResponse
   import logging
   
   # Configurar logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   ```

**10.2** Modificar `handle_turn()` para usar clases de agentes
   ```python
   def handle_turn(player_input: str) -> str:
       """Gestiona turno con switching automático entre agentes"""
       # Cargar configuración
       load_env()
       
       # Cargar estado
       state = cargar_estado()
       state['meta']['turno'] += 1
       current_turn = state['meta']['turno']
       
       # Log de turno
       logger.info(f"[TURN {current_turn}] Input: {player_input}")
       agregar_log(state, f"Turno {current_turn}: {player_input}")
       
       # Determinar agente inicial
       current_scene_type = state['world']['scenes'][state['player']['location']].get('type', 'exploration')
       initial_agent = "combat" if current_scene_type == "combat" else "narrator"
       logger.info(f"[ORCHESTRATOR] Initial agent: {initial_agent}")
       
       # Obtener y ejecutar agente
       agent = get_agent(initial_agent)
       response = agent.execute(state, player_input)
       
       # Procesar respuesta y aplicar cambios
       output_text = response.narration
       changes = {}
       
       if isinstance(response, NarratorResponse):
           changes = response.scene_updates
           logger.info(f"[NARRATOR] Reasoning: {response.reasoning_steps}")
           
           # Detectar switch a combate
           if response.switch_to_agent == "combat":
               logger.info(f"[ORCHESTRATOR] Switching from narrator to combat")
               state['flags']['current_agent'] = 'combat'
               
               # Aplicar cambios del narrador primero
               aplicar_cambios(state, changes)
               
               # Ejecutar agente de combate en el mismo turno
               combat_agent = get_agent("combat")
               combat_response = combat_agent.execute(state, player_input)
               
               # Combinar outputs
               output_text += "\n\n--- INICIO DE COMBATE ---\n" + combat_response.narration
               changes.update(combat_response.combat_updates)
               logger.info(f"[COMBAT] Reasoning: {combat_response.reasoning_steps}")
               
               # Revisar si el combate terminó inmediatamente
               if combat_response.combat_ended:
                   state['flags']['current_agent'] = 'narrator'
                   logger.info(f"[ORCHESTRATOR] Combat ended, returning to narrator")
       
       elif isinstance(response, CombatResponse):
           changes = response.combat_updates
           logger.info(f"[COMBAT] Reasoning: {response.reasoning_steps}")
           
           # Detectar fin de combate
           if response.combat_ended:
               logger.info(f"[ORCHESTRATOR] Combat ended, switching to narrator")
               state['flags']['current_agent'] = 'narrator'
               changes['scene_type'] = 'exploration'
               output_text += "\n\n--- FIN DE COMBATE ---"
       
       # Aplicar cambios finales al estado
       aplicar_cambios(state, changes)
       
       # Actualizar memoria narrativa
       agregar_a_memoria(state, player_input, output_text)
       
       # Guardar estado
       guardar_estado(state)
       
       logger.info(f"[TURN {current_turn}] Completed. Current agent: {state['flags'].get('current_agent', 'narrator')}")
       return output_text
   ```

**10.3** Agregar función helper para actualizar memoria
   ```python
   def agregar_a_memoria(state: dict, player_input: str, response: str):
       """Agrega evento a memoria narrativa"""
       event = f"Player: {player_input} | DM: {response[:100]}..."
       if 'narrative_memory' not in state:
           state['narrative_memory'] = {'summary': '', 'events': []}
       state['narrative_memory']['events'].append(event)
       
       # Mantener solo últimos 10 eventos
       if len(state['narrative_memory']['events']) > 10:
           state['narrative_memory']['events'] = state['narrative_memory']['events'][-10:]
   ```

---

### **Paso 11: Mejorar Función de Aplicación de Cambios**

**11.1** Extender `aplicar_cambios()` en [almacenamiento.py](backend/utils/almacenamiento.py)
   ```python
   def aplicar_cambios(state: dict, cambios: dict):
       """Aplica cambios estructurados al estado del juego"""
       if not cambios:
           return
       
       # Cambios en flags
       if 'current_agent' in cambios:
           if 'flags' not in state:
               state['flags'] = {}
           state['flags']['current_agent'] = cambios['current_agent']
       
       # Cambios en escena
       if 'scene_type' in cambios:
           location = state['player']['location']
           state['world']['scenes'][location]['type'] = cambios['scene_type']
       
       if 'scene_description' in cambios:
           location = state['player']['location']
           state['world']['scenes'][location]['description'] = cambios['scene_description']
       
       # Cambios en HP del jugador
       if 'player_hp' in cambios:
           state['player']['hp'] = max(0, cambios['player_hp'])
       
       # Cambios en enemigos (formato: enemy_<id>_hp)
       for key, value in cambios.items():
           if key.startswith('enemy_') and key.endswith('_hp'):
               enemy_id = key.replace('enemy_', '').replace('_hp', '')
               for enemy in state['world']['enemies']:
                   if enemy['id'] == enemy_id:
                       enemy['hp'] = max(0, value)
                       if enemy['hp'] == 0:
                           enemy['is_alive'] = False
       
       # Cambios genéricos en world
       if 'world_updates' in cambios:
           state['world'].update(cambios['world_updates'])
   ```

---

## **FASE 6: ESCENARIO DE PRUEBA Y CLI**

### **Paso 12: Crear Escenario de Prueba con Combate**

**12.1** Modificar [game_state.json](backend/state/game_state.json) - Agregar enemigo
   ```json
   {
     "meta": {
       "turno": 0,
       "version": "1.0"
     },
     "player": {
       "name": "Aventurero",
       "hp": 20,
       "max_hp": 20,
       "level": 1,
       "ac": 15,
       "attack_bonus": 3,
       "weapon": "espada corta",
       "inventory": ["poción de curación", "antorcha"],
       "location": "bosque_oscuro"
     },
     "world": {
       "scenes": {
         "bosque_oscuro": {
           "name": "Bosque Oscuro",
           "description": "Un sendero brumoso se abre entre árboles retorcidos. A lo lejos escuchas gruñidos.",
           "type": "exploration"
         }
       },
       "locations": {
         "bosque_oscuro": {
           "exits": {"norte": "claro", "sur": "entrada"}
         }
       },
       "enemies": [
         {
           "id": "goblin_1",
           "name": "Goblin emboscador",
           "hp": 7,
           "max_hp": 7,
           "ac": 13,
           "attack_bonus": 4,
           "damage": "1d6+2",
           "location": "bosque_oscuro",
           "is_alive": true
         }
       ],
       "npcs": [],
       "items": [],
       "quests": []
     },
     "flags": {
       "current_agent": "narrator",
       "in_combat": false
     },
     "narrative_memory": {
       "summary": "El aventurero comienza su viaje en un bosque oscuro.",
       "events": []
     },
     "logs": []
   }
   ```

---

### **Paso 13: Mejorar CLI para Mostrar Estado**

**13.1** Refactorizar [test.py](backend/test.py) - Agregar visualización de estado
   ```python
   from backend.orquestador import handle_turn
   from backend.utils.almacenamiento import cargar_estado
   import sys
   
   def mostrar_estado():
       """Muestra información clave del estado actual"""
       state = cargar_estado()
       print("\n" + "="*60)
       print(f"TURNO {state['meta']['turno']} | AGENTE ACTIVO: {state['flags'].get('current_agent', 'narrator').upper()}")
       print(f"HP: {state['player']['hp']}/{state['player']['max_hp']} | Ubicación: {state['player']['location']}")
       
       # Mostrar tipo de escena
       scene = state['world']['scenes'].get(state['player']['location'], {})
       print(f"Escena: {scene.get('type', 'exploration').upper()}")
       
       # Mostrar enemigos vivos
       location = state['player']['location']
       enemies_alive = [e for e in state['world']['enemies'] 
                        if e.get('location') == location and e.get('is_alive', True)]
       if enemies_alive:
           print(f"Enemigos presentes: {', '.join([f\"{e['name']} (HP: {e['hp']})\" for e in enemies_alive])}")
       print("="*60 + "\n")
   
   def main():
       """Loop principal de CLI"""
       print("Bienvenido a D&D DM IA")
       print("Escribe 'salir' para terminar\n")
       
       while True:
           # Mostrar estado antes de cada turno
           mostrar_estado()
           
           # Obtener input del jugador
           user_input = input("Tu acción: ").strip()
           
           if user_input.lower() == 'salir':
               print("¡Hasta la próxima aventura!")
               break
           
           if not user_input:
               continue
           
           # Procesar turno
           try:
               response = handle_turn(user_input)
               print(f"\n{response}\n")
           except Exception as e:
               print(f"ERROR: {e}")
               import traceback
               traceback.print_exc()
   
   if __name__ == "__main__":
       main()
   ```

---

## **FASE 7: VALIDACIÓN END-TO-END**

### **Paso 14: Testing y Refinamiento**

**14.1** Ejecutar escenario completo de prueba
   - Iniciar CLI: `python backend/test.py`
   - **Turno 1**: Escribir "miro alrededor"
     - Verificar: Narrador describe el bosque y menciona al goblin
     - Estado: Debe permanecer en exploration
   
   - **Turno 2**: Escribir "ataco al goblin"
     - Verificar: Narrador detecta combate → Switch automático → Agente combate resuelve ataque
     - Estado: Debe cambiar a combat, current_agent=combat
   
   - **Turno 3**: Escribir "ataco de nuevo"
     - Verificar: Agente combate activo, procesa turno + turno enemigo
     - Estado: HP actualizados correctamente
   
   - **Turno 4**: (Si combate continúa) Escribir "ataco hasta matarlo"
     - Verificar: Cuando goblin.hp=0, combat_ended=True → Switch a narrator
     - Estado: scene.type=exploration, current_agent=narrator

**14.2** Verificar persistencia
   - Cerrar CLI (Ctrl+C)
   - Abrir [game_state.json](backend/state/game_state.json)
   - Verificar:
     - `meta.turno` incrementado
     - `player.hp` actualizado si fue golpeado
     - `enemies[0].hp` = 0 y `is_alive` = false
     - `narrative_memory.events` contiene historial
     - `flags.current_agent` = "narrator"

**14.3** Testing de edge cases
   - **Combate sin atacar**: Escribir "hablo con el goblin" en combat → ¿Qué hace combat agent?
   - **Huida**: Escribir "huyo" en combate → Debe terminar combate con combat_ended=True
   - **HP = 0**: Forzar HP del jugador a 0 → Combate debe terminar, verificar mensaje de derrota

**14.4** Ajustes finales de prompts
   - Si narrador no detecta combate correctamente: Fortalecer keywords en [sistema_narrador.py](backend/prompts/sistema_narrador.py)
   - Si combate nunca termina: Ya implementado contador máximo de 20 turnos
   - Si enemigos no atacan: Revisar `_process_enemy_turns()` en [combate.py](backend/agents/combate.py)

---

## **CONSIDERACIONES FINALES**

### **1. Persistencia de Contador de Turnos de Combate**
El contador `turn_counter` en CombatAgent se resetea en cada instancia. Para combates multi-turno, guardar en `state.flags.combat_turn_count` y leer en execute().

### **2. Manejo de Múltiples Enemigos**
Actualmente `_process_enemy_turns()` itera todos los enemigos en la ubicación. Si hay 3+ enemigos, la narración será larga. Considerar resumir con "Los goblins atacan en masa..."

### **3. Validación de Inputs Vacíos**
El CLI actual continúa sin error en inputs vacíos. `handle_turn()` debe validar y retornar mensaje helper si `player_input.strip() == ""`.

### **4. Migración Futura a Tools**
Cuando implementes tools (Hito 2), añadir a BaseReActAgent:
```python
def _inject_tools_in_prompt(self, prompt):
    if not self.tools:
        return prompt
    tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in self.tools])
    return prompt + f"\n\nTOOLS DISPONIBLES:\n{tool_descriptions}"
```

### **5. Versionado de Prompts para BD**
Agregar campo `prompt_version` en game_state meta cuando migres prompts a BD:
```json
"meta": {
  "turno": 10,
  "version": "1.0",
  "prompt_version": {
    "narrator": "v1.2",
    "combat": "v1.0"
  }
}
```

### **6. Logging a Archivo**
Para debugging complejo, modificar logging en [orquestador.py](backend/orquestador.py):
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('backend/logs/game.log'),
        logging.StreamHandler()
    ]
)
```

---

**✅ HITO 1 COMPLETADO CUANDO:**
- El jugador puede iniciar el CLI y jugar una mini campaña
- El narrador IA responde inmersivamente a acciones de exploración
- Al detectar combate, se cambia automáticamente al agente de combate
- El combate usa mecánicas D&D 5e (dados, HP, AC)
- Al terminar combate, vuelve al narrador automáticamente
- Todo el estado se persiste en game_state.json
- Los agentes muestran pasos de razonamiento ReAct en logs
