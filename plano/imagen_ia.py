"""Render realista OPCIONAL del plano con un modelo de imágenes de Gemini (experimental: puede alterar textos y medidas)."""
import base64

import gemini_rest
from gemini_rest import ErrorGemini

PROMPT = """Transformá este plano de planta 2D en un plano arquitectónico renderizado de alta calidad, en vista cenital (estilo de plano comercial de inmobiliaria):
muros negros gruesos, pisos de madera y cerámica, muebles detallados, jardín con césped y árboles, autos en la cochera, ventanas celestes y cuadro de datos a la derecha.
CONSERVÁ EXACTAMENTE la distribución, la cantidad y la posición de los ambientes, las proporciones, los textos, las cotas y las superficies del plano recibido.
No agregues ni quites ambientes. Mantené el panel lateral con título, superficies, ambientes, notas, norte y escala gráfica."""


def render_realista(clave, modelo, png_bytes, indicaciones=""):
    partes = [{"text": PROMPT + ("\nIndicaciones adicionales: " + indicaciones.strip() if indicaciones.strip() else "")},
              {"inline_data": {"mime_type": "image/png", "data": base64.standard_b64encode(png_bytes).decode()}}]
    cuerpo = {"contents": [{"role": "user", "parts": partes}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
    datos = gemini_rest._pedir(f"{gemini_rest.BASE_URL}/models/{modelo}:generateContent", clave, cuerpo, timeout=300)
    return extraer_imagen(datos)


def extraer_imagen(datos):
    for cand in datos.get("candidates") or []:
        for p in (cand.get("content") or {}).get("parts", []):
            d = p.get("inlineData") or p.get("inline_data")
            if d and d.get("data"):
                return base64.b64decode(d["data"]), (d.get("mimeType") or d.get("mime_type") or "image/png")
    raise ErrorGemini(200, "El modelo no devolvió una imagen (puede que no esté habilitado para tu clave o que haya bloqueado la solicitud).")
