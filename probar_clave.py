"""Prueba aislada de la clave de Gemini (sin SDK). Ejecutar: python probar_clave.py"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from gemini_rest import ErrorGemini, generar_texto, listar_modelos

BASE = Path(__file__).parent.resolve()
env = BASE / ".env"
print(f"Python               : {sys.version.split()[0]}")
print(f"Carpeta del programa : {BASE}")
print(f"¿Existe el .env?     : {'SÍ' if env.exists() else 'NO  <-- creá el archivo .env (copiá .env.example)'}")
load_dotenv(env, override=True)

clave = os.getenv("GEMINI_API_KEY", "")
limpia = clave.strip().strip('"').strip("'")
print(f"Largo de la clave    : {len(limpia)}")
print(f"Empieza con          : {limpia[:3]!r}   (las claves nuevas de AI Studio empiezan con 'AQ.', las viejas con 'AIza'; ambas pueden ser válidas)")
print(f"Termina con          : {limpia[-4:]!r}")
if clave != limpia:
    print("AVISO: la clave tenía comillas o espacios; el bot los quita solo.")
if not limpia or "PEGA" in limpia.upper():
    raise SystemExit("\nERROR: la clave está vacía o es el texto de ejemplo. Pegá tu clave real en el archivo .env")
if os.getenv("GOOGLE_API_KEY"):
    print("AVISO: hay una variable de sistema GOOGLE_API_KEY; este bot la ignora y usa la del .env.")

print("\n1) Pidiendo la lista de modelos a Google...")
try:
    modelos = listar_modelos(limpia)
except ErrorGemini as e:
    print(f"   ERROR {e.codigo}: {e.mensaje}")
    if e.clave_invalida:
        print("\n→ Google no aceptó esta clave. Revisá:")
        print("  • Que esté COMPLETA (las claves AQ. son largas, ~50 caracteres) y sin espacios en el .env")
        print("  • Que sea la clave de 'bot informes' en https://aistudio.google.com/api-keys")
        print("  • Si hace falta, creá otra clave nueva y reemplazala")
    raise SystemExit(1)
preferidos = [m for m in modelos if "flash" in m and "preview" not in m and "latest" in m] or [m for m in modelos if "flash" in m]
print(f"   OK. Modelos 'flash' disponibles (primeros 8): {', '.join([m for m in modelos if 'flash' in m][:8])}")

modelo = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
print(f"\n2) Probando generar texto con '{modelo}'...")
try:
    print("   Respuesta:", generar_texto(limpia, modelo, [{"text": "Respondé solamente: OK"}], json_salida=False, max_tokens=2048).strip())
    print("\n✔ Todo funciona. Ya podés ejecutar: python app.py")
except ErrorGemini as e:
    print(f"   ERROR {e.codigo}: {e.mensaje}")
    if e.codigo == 404:
        print(f"\n→ El modelo '{modelo}' no está disponible. Poné uno de la lista de arriba en GEMINI_MODEL dentro del .env (ej.: {preferidos[0] if preferidos else 'gemini-flash-latest'}).")
    raise SystemExit(1)
