"""Lee un boceto (foto a mano alzada) y/o una descripción y devuelve el modelo de la vivienda (JSON) usando Gemini."""
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageOps

from gemini_rest import ErrorGemini, generar_texto

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = json.loads((RAIZ / "ejemplos" / "ejemplo_vivienda.json").read_text(encoding="utf-8"))

SISTEMA = """Sos un arquitecto asistente que convierte bocetos de plantas a mano alzada en un modelo geométrico de vivienda.
Respondés ÚNICAMENTE con un objeto JSON válido (sin texto antes ni después, sin bloques de código)."""

REGLAS = """TAREA
Analizá el/los boceto(s) y la descripción del usuario y devolvé el modelo de la planta con la estructura del EJEMPLO.

REGLAS
1. Unidades: metros. Ejes: x hacia la derecha, y hacia abajo; el origen (0,0) es la esquina superior izquierda del lote. El norte está arriba salvo que se indique otra cosa (norte_grados: giro horario en grados).
2. Cada ambiente es un RECTÁNGULO {id, nombre, tipo, x, y, w, h} (x,y = esquina superior izquierda; w = ancho en x; h = alto en y).
   Tipos de ambientes interiores: dormitorio, bano, vestidor, pasillo, hall, estar, cocina, comedor, cocina_comedor, lavadero, escritorio, deposito, otro.
   Tipos de espacios exteriores (van en "exteriores"): galeria, cochera, jardin, patio, vereda, terraza.
3. Los ambientes que comparten pared deben compartir EXACTAMENTE el mismo valor de coordenada en ese borde (sin huecos ni superposiciones). Si un ambiente tiene forma de L, dividilo en rectángulos con nombres distintos.
4. Usá las medidas escritas en el boceto. Si no hay medidas, estimalas con proporciones del dibujo y medidas habituales (dormitorio 3 x 3,5 m; baño 2 x 2,2 m; cocina-comedor 4 x 5 m; cochera 3 x 5 m por auto) y, si el usuario dio una medida de referencia, usala para calibrar la escala de todo el plano.
5. Nombres en español, en MAYÚSCULAS (las aclaraciones entre paréntesis, en una segunda línea separada por \\n, pueden ir en minúsculas).
6. "aberturas": lista de {tipo, ambiente, lado, pos, ancho, giro, bisagra, etiqueta}.
   - tipo: "puerta" (con hoja), "paso" (vano sin hoja) o "ventana".
   - ambiente: id del ambiente al que pertenece el muro; lado: N (arriba), S (abajo), E (derecha) o W (izquierda/oeste) del rectángulo del ambiente.
   - pos: posición del centro a lo largo de ese lado como fracción 0 a 1 (en N/S de izquierda a derecha; en E/W de arriba hacia abajo); ancho en metros (puerta 0,8–1,0; ventana 0,6–2,4).
   - giro: "adentro" o "afuera" respecto del ambiente; bisagra: "izq" o "der". La puerta de acceso lleva etiqueta "ACCESO\\nPRINCIPAL".
   - Cada ambiente cerrado debe tener acceso por una puerta o paso hacia otro ambiente o hacia el exterior; los baños y dormitorios que dan al exterior llevan ventana.
7. "lote": {ancho, alto} del terreno si se conoce; si no, el rectángulo que contiene la construcción con un margen.
8. "titulo" (ej. "VIVIENDA UNIFAMILIAR"), "subtitulo" (ej. "PLANTA BAJA"), "notas" (hasta 4 frases útiles) y "pie" (frase breve opcional).
9. Si hay algo ilegible, hacé la mejor estimación razonable; no inventes ambientes que no estén en el boceto o en la descripción."""


def preparar_foto(datos):
    """Corrige la orientación, mejora el contraste y reduce el tamaño del boceto (JPEG)."""
    im = Image.open(io.BytesIO(datos))
    im = ImageOps.exif_transpose(im).convert("RGB")
    im = ImageOps.autocontrast(im, cutoff=1)
    im.thumbnail((1800, 1800))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _json(texto):
    texto = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip(), flags=re.M).strip()
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini < 0 or fin < 0:
        raise ValueError("La respuesta de la IA no contiene un JSON.")
    return json.loads(texto[ini:fin + 1])


def _b64(datos, mime="image/jpeg"):
    return {"inline_data": {"mime_type": mime, "data": base64.standard_b64encode(datos).decode()}}


def _llamar(clave, modelo, partes):
    for intento in (1, 2):
        texto = generar_texto(clave, modelo, partes, sistema=SISTEMA, json_salida=True, temperatura=0.2, max_tokens=24000)
        try:
            return _json(texto)
        except (ValueError, json.JSONDecodeError):
            if intento == 2:
                raise ErrorGemini(200, "La IA devolvió una respuesta que no se pudo leer. Probá de nuevo o simplificá el boceto.")


def interpretar(clave, modelo, fotos, detalles="", ancho_ref=None, titulo="", subtitulo=""):
    texto = REGLAS + "\n\nEJEMPLO DE SALIDA (otra vivienda; es solo para mostrar el formato):\n" + json.dumps(EJEMPLO, ensure_ascii=False)
    texto += "\n\nDATOS DEL USUARIO"
    texto += f"\n- Descripción / medidas: {detalles.strip() or '(sin descripción: guiate por el boceto)'}"
    if ancho_ref:
        texto += f"\n- Medida de referencia: el ancho total de la construcción (dimensión horizontal del boceto) es {ancho_ref} m."
    if titulo:
        texto += f"\n- Título del plano: {titulo}"
    if subtitulo:
        texto += f"\n- Subtítulo: {subtitulo}"
    texto += f"\n- Cantidad de imágenes de boceto adjuntas: {len(fotos)}"
    partes = [{"text": texto}] + [_b64(preparar_foto(f)) for f in fotos]
    return _llamar(clave, modelo, partes)


def ajustar(clave, modelo, actual, instruccion):
    texto = (REGLAS + "\n\nMODELO ACTUAL (JSON):\n" + json.dumps(actual, ensure_ascii=False) + "\n\nINSTRUCCIÓN DEL USUARIO PARA MODIFICARLO:\n" + instruccion.strip()
             + "\n\nDevolvé el JSON COMPLETO con los cambios aplicados, manteniendo las coordenadas y aberturas que no se pidió cambiar y respetando la regla de bordes compartidos.")
    return _llamar(clave, modelo, [{"text": texto}])
