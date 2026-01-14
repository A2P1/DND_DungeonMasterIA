"""
Script temporal para validar conexión con OpenAI API.
Este archivo se eliminará después de la validación.
"""

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os

def test_api_key():
    """Valida que la API key de OpenAI funcione correctamente"""
    print("🔍 Validando API key de OpenAI...")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Verificar que existe la clave
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY no encontrada en .env")
        print("\nAsegúrate de:")
        print("1. Crear archivo .env en la raíz del proyecto")
        print("2. Agregar tu API key: OPENAI_API_KEY=sk-...")
        return False
    
    if api_key == "tu-clave-aqui":
        print("❌ ERROR: Debes reemplazar 'tu-clave-aqui' con tu API key real")
        print("\nObtén tu API key en: https://platform.openai.com/api-keys")
        return False
    
    print(f"✅ API key encontrada: {api_key[:20]}...")
    
    try:
        # Hacer una llamada simple a OpenAI
        print("\n🤖 Realizando llamada de prueba a OpenAI...")
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
        response = llm.invoke("Di hola")
        
        print(f"✅ Respuesta recibida: {response.content}")
        print("\n✨ ¡Validación exitosa! Tu API key funciona correctamente.")
        print("Puedes eliminar este archivo ahora: test_openai.py")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR al conectar con OpenAI: {e}")
        print("\nPosibles causas:")
        print("- API key inválida o expirada")
        print("- Sin créditos en tu cuenta de OpenAI")
        print("- Problemas de conexión a internet")
        return False

if __name__ == "__main__":
    print("="*60)
    print("  VALIDACIÓN DE API KEY DE OPENAI")
    print("="*60 + "\n")
    
    success = test_api_key()
    
    print("\n" + "="*60)
    if success:
        print("✅ VALIDACIÓN COMPLETADA")
    else:
        print("❌ VALIDACIÓN FALLIDA")
    print("="*60)
