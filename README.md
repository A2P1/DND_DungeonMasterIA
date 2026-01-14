# DND_DungeonMasterIA

Sistema de Dungeon Master con IA para campañas de D&D 5e usando arquitectura multi-agente ReAct.

## Configuración Inicial

### 1. Obtener API Key de OpenAI

1. Ve a [OpenAI Platform](https://platform.openai.com/api-keys)
2. Inicia sesión o crea una cuenta
3. Navega a "API Keys" en el menú lateral
4. Haz clic en "Create new secret key"
5. Copia la clave generada (solo se muestra una vez)

### 2. Configurar Variables de Entorno

1. Abre el archivo `.env` en la raíz del proyecto
2. Reemplaza `tu-clave-aqui` con tu API key real:
   ```
   OPENAI_API_KEY=sk-proj-tu-clave-real-aqui
   ```
3. Guarda el archivo

**⚠️ IMPORTANTE:** 
- Nunca compartas tu API key
- El archivo `.env` ya está en `.gitignore` para proteger tu clave
- Si accidentalmente expones tu clave, revócala inmediatamente en OpenAI

### 3. Instalar Dependencias

```bash
pip install -r backend/requirements.txt
```

### 4. Validar API Key (Opcional pero Recomendado)

Antes de empezar, puedes validar que tu API key funcione:

```bash
python test_openai.py
```

Si la validación es exitosa, puedes eliminar el archivo `test_openai.py`.

### 5. Ejecutar el Juego

```bash
cd backend
python test.py
```

## Estructura del Proyecto

```
DND_DungeonMasterIA/
├── backend/
│   ├── agents/          # Agentes IA (narrador, combate)
│   ├── prompts/         # Sistemas de prompts
│   ├── state/           # Estado persistente del juego
│   └── utils/           # Utilidades (almacenamiento, esquemas)
├── frontend/            # Interfaz web (futuro)
└── .env                 # Configuración de entorno (NO SUBIR A GIT)
```

## Características

- 🎲 Sistema de combate D&D 5e con tiradas de dados
- 🤖 Agentes IA con razonamiento ReAct
- 💾 Persistencia automática de estado
- 🔄 Switching automático entre modos (exploración/combate)
- 📖 Memoria narrativa contextual