"""
Bot de planos – de un boceto a mano alzada (foto) a un plano arquitectónico.
Flask + Gemini (lectura del boceto) + dibujo vectorial propio (PNG / PDF / SVG / DXF para AutoCAD).
"""
import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

from gemini_rest import ErrorGemini
from plano import imagen_ia, interpretar
from plano.dibujo import dibujar, guardar
from plano.dxf import exportar_dxf
from plano.modelo import normalizar, superficies

BASE = Path(__file__).parent.resolve()
load_dotenv(BASE / ".env", override=True)
API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
MODELO = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
MODELO_IMAGEN = os.getenv("GEMINI_IMAGEN_MODELO", "gemini-2.5-flash-image").strip()
EMPRESA = os.getenv("EMPRESA", "Axis Ingeniería").strip()
SALIDA = BASE / "salida"
SALIDA.mkdir(exist_ok=True)
LOGO = BASE / "static" / "logo.png"
BLOQUEO = threading.Lock()          # matplotlib no es seguro con varios hilos

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024


class ErrorBot(Exception):
    pass


def hay_clave():
    return bool(API_KEY) and "PEGA" not in API_KEY.upper()


def exigir_clave():
    if not hay_clave():
        raise ErrorBot("No hay clave de Gemini cargada. Creá el archivo .env junto a app.py con GEMINI_API_KEY=tu_clave (ver README).")


def traducir(e):
    if e.clave_invalida:
        return "Google rechazó la clave de Gemini. Verificá que esté completa en el archivo .env y reiniciá el programa."
    if e.codigo == 429:
        return "Se alcanzó el límite de uso de Gemini. Esperá un minuto y probá de nuevo."
    if e.codigo == 404:
        return f"El modelo no existe para tu clave. Revisá GEMINI_MODEL / GEMINI_IMAGEN_MODELO en el archivo .env. Detalle: {e.mensaje}"
    return f"Error de Gemini ({e.codigo}): {e.mensaje}"


def opciones_dibujo(f):
    on = lambda k, d=True: (str(f.get(k, "on" if d else "")).lower() in ("on", "true", "1", "si", "sí"))
    return dict(muebles=on("muebles"), vegetacion=on("vegetacion"), cotas=on("cotas"), cuadro=on("cuadro"), formato=("A4" if f.get("formato") == "A4" else "A3"), empresa=EMPRESA, logo=str(LOGO) if LOGO.exists() else None)


def producir(id_, modelo, opciones):
    """Normaliza el modelo, dibuja y guarda PNG, PDF, SVG, DXF y JSON. Devuelve el diccionario de respuesta."""
    carpeta = SALIDA / id_
    carpeta.mkdir(exist_ok=True)
    m, avisos = normalizar(modelo)
    with BLOQUEO:
        fig = dibujar(copy.deepcopy(m), opciones)
        guardar(fig, carpeta, "plano")
        exportar_dxf(m, carpeta / "plano.dxf")
    (carpeta / "modelo.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    v = int(datetime.now().timestamp())
    u = lambda n: f"/salida/{id_}/{n}?v={v}"
    sup = superficies(m)
    return dict(ok=True, id=id_, png=u("plano.png"), pdf=u("plano.pdf"), svg=u("plano.svg"), dxf=u("plano.dxf"), json=u("modelo.json"), modelo=json.dumps(m, ensure_ascii=False, indent=1), avisos=avisos,
                resumen=dict(ambientes=len(m["ambientes"]), cubierta=round(sup["cubierta"], 1), total=round(sup["total"], 1), lote=m["lote"]))


def id_valido(x):
    if not isinstance(x, str) or not re.fullmatch(r"[\w-]+", x):
        raise ErrorBot("Identificador de plano inválido.")
    return x


@app.get("/")
def index():
    return render_template("index.html", empresa=EMPRESA, hay_clave=hay_clave())


@app.get("/ejemplo.json")
def ejemplo():
    return jsonify(interpretar.EJEMPLO)


@app.post("/generar")
def generar():
    try:
        f = request.form
        id_ = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
        (SALIDA / id_).mkdir()
        fotos = [a.read() for a in request.files.getlist("fotos") if a and a.filename]
        detalles = f.get("detalles", "").strip()
        avisos_extra = []
        if f.get("usar_ejemplo") == "on":
            modelo = copy.deepcopy(interpretar.EJEMPLO)
        else:
            if not fotos and not detalles:
                raise ErrorBot("Subí una foto del boceto o escribí una descripción con las medidas de los ambientes.")
            exigir_clave()
            for i, b in enumerate(fotos):
                (SALIDA / id_ / f"boceto_{i+1}.jpg").write_bytes(interpretar.preparar_foto(b))
            try:
                ref = float(f.get("ancho_ref", "").replace(",", ".")) if f.get("ancho_ref", "").strip() else None
            except ValueError:
                ref = None
            try:
                modelo = interpretar.interpretar(API_KEY, MODELO, fotos, detalles, ref, f.get("titulo", ""), f.get("subtitulo", ""))
            except ErrorGemini as e:
                raise ErrorBot(traducir(e))
        if f.get("titulo", "").strip():
            modelo["titulo"] = f["titulo"].strip().upper()
        if f.get("subtitulo", "").strip():
            modelo["subtitulo"] = f["subtitulo"].strip().upper()
        try:
            res = producir(id_, modelo, opciones_dibujo(f))
        except ValueError as e:
            raise ErrorBot(str(e))
        res["avisos"] += avisos_extra
        return jsonify(res)
    except ErrorBot as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception as e:
        app.logger.exception("Error inesperado")
        return jsonify(ok=False, error=f"Error inesperado ({type(e).__name__}): {e}. El detalle está en la consola donde corre app.py."), 500


@app.post("/redibujar")
def redibujar():
    try:
        d = request.get_json(force=True)
        id_ = id_valido(d.get("id"))
        try:
            modelo = json.loads(d.get("modelo") or "{}") if isinstance(d.get("modelo"), str) else d.get("modelo")
        except json.JSONDecodeError as e:
            raise ErrorBot(f"El JSON editado no es válido (línea {e.lineno}, columna {e.colno}): {e.msg}")
        try:
            return jsonify(producir(id_, modelo, opciones_dibujo(d.get("opciones") or {})))
        except ValueError as e:
            raise ErrorBot(str(e))
    except ErrorBot as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception as e:
        app.logger.exception("Error inesperado")
        return jsonify(ok=False, error=f"Error inesperado ({type(e).__name__}): {e}"), 500


@app.post("/ajustar")
def ajustar():
    try:
        d = request.get_json(force=True)
        id_ = id_valido(d.get("id"))
        instruccion = (d.get("instruccion") or "").strip()
        if not instruccion:
            raise ErrorBot("Escribí qué querés cambiar.")
        exigir_clave()
        actual = json.loads(d["modelo"]) if isinstance(d.get("modelo"), str) else d.get("modelo")
        try:
            nuevo = interpretar.ajustar(API_KEY, MODELO, actual, instruccion)
            return jsonify(producir(id_, nuevo, opciones_dibujo(d.get("opciones") or {})))
        except ErrorGemini as e:
            raise ErrorBot(traducir(e))
        except ValueError as e:
            raise ErrorBot(str(e))
    except ErrorBot as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception as e:
        app.logger.exception("Error inesperado")
        return jsonify(ok=False, error=f"Error inesperado ({type(e).__name__}): {e}"), 500


@app.post("/render-ia")
def render_ia():
    try:
        d = request.get_json(force=True)
        id_ = id_valido(d.get("id"))
        png = SALIDA / id_ / "plano.png"
        if not png.exists():
            raise ErrorBot("Primero generá el plano.")
        exigir_clave()
        try:
            datos, mime = imagen_ia.render_realista(API_KEY, MODELO_IMAGEN, png.read_bytes(), d.get("indicaciones", ""))
        except ErrorGemini as e:
            raise ErrorBot(traducir(e))
        ext = "jpg" if "jpeg" in mime else "png"
        (SALIDA / id_ / f"render_ia.{ext}").write_bytes(datos)
        return jsonify(ok=True, imagen=f"/salida/{id_}/render_ia.{ext}?v={int(datetime.now().timestamp())}")
    except ErrorBot as e:
        return jsonify(ok=False, error=str(e)), 400
    except Exception as e:
        app.logger.exception("Error inesperado")
        return jsonify(ok=False, error=f"Error inesperado ({type(e).__name__}): {e}"), 500


@app.get("/salida/<id_>/<path:archivo>")
def descargar(id_, archivo):
    if not re.fullmatch(r"[\w-]+", id_):
        return "No encontrado", 404
    return send_from_directory(SALIDA / id_, archivo)


if __name__ == "__main__":
    print("=" * 60)
    print(f" Bot de planos – {EMPRESA}")
    print(f" Clave de Gemini: {'cargada (' + API_KEY[:4] + '…' + API_KEY[-4:] + ')' if hay_clave() else 'FALTA (solo funciona el ejemplo sin IA)'}")
    print(f" Modelo de lectura: {MODELO}  |  modelo de imágenes: {MODELO_IMAGEN}")
    print(" Abrí en el navegador: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
