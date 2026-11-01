"""Modelo de la vivienda: validación, normalización de medidas y cálculo de superficies."""
import copy
import math

TIPOS_INTERIORES = {"dormitorio", "bano", "vestidor", "pasillo", "estar", "cocina", "comedor", "cocina_comedor", "lavadero", "escritorio", "deposito", "hall", "otro"}
TIPOS_EXTERIORES = {"galeria", "cochera", "jardin", "patio", "vereda", "terraza"}
SINONIMOS = {"baño": "bano", "bano": "bano", "wc": "bano", "toilette": "bano", "sanitario": "bano", "dormitorios": "dormitorio", "habitacion": "dormitorio", "habitación": "dormitorio",
             "living": "estar", "sala": "estar", "estar_comedor": "estar", "cocina-comedor": "cocina_comedor", "cocinacomedor": "cocina_comedor", "garage": "cochera", "garaje": "cochera",
             "quincho": "galeria", "porche": "galeria", "corredor": "pasillo", "circulacion": "pasillo", "circulación": "pasillo", "playroom": "estar", "oficina": "escritorio",
             "lavanderia": "lavadero", "lavandería": "lavadero", "placard": "vestidor", "despensa": "deposito", "patio": "patio", "jardín": "jardin"}
LADOS = ("N", "S", "E", "W")


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _nombre(s):
    """Primera línea en MAYÚSCULAS; las siguientes (aclaraciones) se respetan tal cual."""
    partes = str(s).strip().split("\n")
    return "\n".join([partes[0].upper()] + partes[1:])


def _tipo(t, exterior):
    t = str(t or "").strip().lower().replace(" ", "_")
    t = SINONIMOS.get(t, t)
    ok = TIPOS_EXTERIORES if exterior else TIPOS_INTERIORES
    if t in ok:
        return t
    if t in TIPOS_EXTERIORES | TIPOS_INTERIORES:
        return t
    return "jardin" if exterior else "otro"


def _agrupar(vals, tol):
    """Une valores casi iguales (±tol) en un único valor para que los muros contiguos coincidan."""
    vs = sorted(set(round(v, 3) for v in vals))
    grupos, cur = [], [vs[0]] if vs else []
    for v in vs[1:]:
        if v - cur[-1] <= tol:
            cur.append(v)
        else:
            grupos.append(cur); cur = [v]
    if cur:
        grupos.append(cur)
    mapa = {}
    for g in grupos:
        m = round(sum(g) / len(g) / 0.05) * 0.05
        for v in g:
            mapa[v] = round(m, 2)
    return mapa


def normalizar(m):
    """Devuelve (modelo normalizado, avisos)."""
    m = copy.deepcopy(m)
    avisos = []
    m["titulo"] = str(m.get("titulo") or "VIVIENDA UNIFAMILIAR").upper()
    m["subtitulo"] = str(m.get("subtitulo") or "PLANTA BAJA").upper()
    m["espesor_muro_ext"] = min(0.5, max(0.1, _f(m.get("espesor_muro_ext"), 0.25)))
    m["espesor_muro_int"] = min(0.3, max(0.07, _f(m.get("espesor_muro_int"), 0.12)))
    m["norte_grados"] = _f(m.get("norte_grados"), 0.0)
    m["notas"] = [str(n) for n in (m.get("notas") or [])][:8]
    m["pie"] = str(m.get("pie") or "")
    amb, ext, usados = [], [], set()
    for lista, dest, exterior in ((m.get("ambientes") or [], amb, False), (m.get("exteriores") or [], ext, True)):
        for i, a in enumerate(lista):
            w, h = _f(a.get("w")), _f(a.get("h"))
            if w <= 0.3 or h <= 0.3:
                avisos.append(f"Se omitió '{a.get('nombre') or a.get('id')}' por tener medidas no válidas.")
                continue
            idr = str(a.get("id") or f"{'e' if exterior else 'a'}{i+1}")
            while idr in usados:
                idr += "_"
            usados.add(idr)
            dest.append(dict(id=idr, nombre=_nombre(a.get("nombre") or idr), tipo=_tipo(a.get("tipo"), exterior), x=_f(a.get("x")), y=_f(a.get("y")), w=w, h=h))
    if not amb:
        raise ValueError("El plano no tiene ambientes: revisá la imagen o describí los ambientes con sus medidas.")
    # alinear bordes casi coincidentes (tolerancia 12 cm) y redondear a 5 cm
    todos = amb + ext
    mx = _agrupar([r["x"] for r in todos] + [r["x"] + r["w"] for r in todos], 0.12)
    my = _agrupar([r["y"] for r in todos] + [r["y"] + r["h"] for r in todos], 0.12)
    for r in todos:
        x0, x1 = mx[round(r["x"], 3)], mx[round(r["x"] + r["w"], 3)]
        y0, y1 = my[round(r["y"], 3)], my[round(r["y"] + r["h"], 3)]
        r["x"], r["y"], r["w"], r["h"] = x0, y0, round(x1 - x0, 2), round(y1 - y0, 2)
    # desplazar para que el origen sea (0,0) si hay coordenadas negativas
    minx, miny = min(r["x"] for r in todos), min(r["y"] for r in todos)
    if minx < 0 or miny < 0:
        dx, dy = -min(0, minx), -min(0, miny)
        for r in todos:
            r["x"] = round(r["x"] + dx, 2); r["y"] = round(r["y"] + dy, 2)
    maxx, maxy = max(r["x"] + r["w"] for r in todos), max(r["y"] + r["h"] for r in todos)
    lote = m.get("lote") or {}
    lw, lh = _f(lote.get("ancho")), _f(lote.get("alto"))
    m["lote"] = dict(ancho=round(lw if (lw > 0 and maxx <= lw + 0.01) else maxx + 0.5, 2), alto=round(lh if (lh > 0 and maxy <= lh + 0.01) else maxy + 0.5, 2))
    # superposiciones entre ambientes interiores
    for i in range(len(amb)):
        for j in range(i + 1, len(amb)):
            a, b = amb[i], amb[j]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > 0.2 and oy > 0.2:
                avisos.append(f"Los ambientes '{a['nombre']}' y '{b['nombre']}' se superponen ({ox:.2f} × {oy:.2f} m): revisá sus coordenadas.")
    ids = {r["id"] for r in amb}
    ab = []
    for o in m.get("aberturas") or []:
        t = str(o.get("tipo") or "").lower()
        t = {"door": "puerta", "window": "ventana", "arco": "paso", "abertura": "paso"}.get(t, t)
        lado = {"O": "W"}.get(str(o.get("lado", "")).upper()[:1], str(o.get("lado", "")).upper()[:1])
        if t not in ("puerta", "ventana", "paso") or o.get("ambiente") not in ids or lado not in LADOS:
            avisos.append(f"Se omitió una abertura no válida: {o}")
            continue
        ab.append(dict(tipo=t, ambiente=o["ambiente"], lado=lado, pos=_f(o.get("pos"), 0.5), pos_m=(None if o.get("pos_m") is None else _f(o.get("pos_m"))),
                       ancho=min(4.0, max(0.5, _f(o.get("ancho"), 0.9 if t != "ventana" else 1.2))), giro=("afuera" if str(o.get("giro", "")).lower().startswith("af") else "adentro"),
                       bisagra=("der" if str(o.get("bisagra", "")).lower().startswith("d") else "izq"), etiqueta=str(o.get("etiqueta") or "")))
    m["ambientes"], m["exteriores"], m["aberturas"] = amb, ext, ab
    if not ab:
        m["aberturas"] = auto_aberturas(m)
        avisos.append("El modelo no traía puertas ni ventanas: se colocaron automáticamente (revisalas).")
    return m, avisos


def _lados_compartidos(a, b, tol=0.03):
    """Lado de 'a' que comparte pared con 'b' y longitud (m) del tramo compartido -> (lado, largo, centro_en_a_m)."""
    res = []
    for lado, (c, a0, a1) in {"N": (a["y"], a["x"], a["x"] + a["w"]), "S": (a["y"] + a["h"], a["x"], a["x"] + a["w"]), "W": (a["x"], a["y"], a["y"] + a["h"]), "E": (a["x"] + a["w"], a["y"], a["y"] + a["h"])}.items():
        if lado in "NS":
            cb = b["y"] + b["h"] if lado == "N" else b["y"]
            b0, b1 = b["x"], b["x"] + b["w"]
        else:
            cb = b["x"] + b["w"] if lado == "W" else b["x"]
            b0, b1 = b["y"], b["y"] + b["h"]
        if abs(c - cb) <= tol:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo > 0.5:
                res.append((lado, hi - lo, (lo + hi) / 2 - a0))
    return res


def auto_aberturas(m):
    """Puertas y ventanas por defecto: cada ambiente se conecta al pasillo/estar y las ventanas van en muros exteriores."""
    amb = m["ambientes"]
    prioridad = ("pasillo", "hall", "estar", "cocina_comedor", "comedor", "cocina")
    out, conectados = [], set()

    def lados_ext(r):
        res = []
        for lado in LADOS:
            lon = r["w"] if lado in "NS" else r["h"]
            comp = sum(l for (ld, l, c) in [x for b in amb if b["id"] != r["id"] for x in _lados_compartidos(r, b)] if ld == lado)
            if comp < 0.3 and lon >= 1.4:
                res.append(lado)
        return res

    def add(tipo, r, lado, pos, ancho, etiqueta=""):
        out.append(dict(tipo=tipo, ambiente=r["id"], lado=lado, pos=pos, pos_m=None, ancho=ancho, giro="adentro", bisagra="izq", etiqueta=etiqueta))

    # acceso principal: ambiente de ingreso con muro exterior (preferencia: sur)
    acceso = None
    for tipo in ("hall", "estar", "cocina_comedor", "pasillo"):
        for r in amb:
            if r["tipo"] == tipo:
                ext = lados_ext(r)
                lado = next((s for s in ("S", "W", "E", "N") if s in ext), None)
                if lado:
                    acceso = (r, lado); break
        if acceso:
            break
    for r in amb:
        if r["tipo"] == "pasillo":
            continue
        cands = []
        for b in amb:
            if b["id"] == r["id"]:
                continue
            for lado, largo, centro in _lados_compartidos(r, b):
                if largo >= 0.9:
                    p = prioridad.index(b["tipo"]) if b["tipo"] in prioridad else (7 if b["tipo"] == "dormitorio" and r["tipo"] == "bano" else 9)
                    cands.append((p, -largo, lado, centro, b))
        if cands and not any(frozenset((r["id"], c[4]["id"])) in conectados for c in cands):
            cands.sort(key=lambda t: (t[0], t[1]))
            p, nl, lado, centro, b = cands[0]
            lon = r["w"] if lado in "NS" else r["h"]
            abierto = r["tipo"] in ("estar", "cocina_comedor", "comedor", "cocina") and b["tipo"] in ("pasillo", "estar", "cocina_comedor", "cocina", "comedor")
            add("paso" if abierto else "puerta", r, lado, min(0.85, max(0.15, centro / lon)), 1.6 if abierto else (0.8 if r["tipo"] in ("bano", "vestidor", "lavadero") else 0.9))
            conectados.add(frozenset((r["id"], b["id"])))
        # ventanas en muros exteriores
        for lado in lados_ext(r):
            if r["tipo"] in ("pasillo", "vestidor", "deposito"):
                break
            lon = r["w"] if lado in "NS" else r["h"]
            if acceso and acceso[0]["id"] == r["id"] and acceso[1] == lado:
                add("ventana", r, lado, 0.25, min(1.4, lon * 0.35))
            else:
                add("ventana", r, lado, 0.5, 0.6 if r["tipo"] in ("bano", "lavadero") else min(1.8, lon * 0.5))
            if r["tipo"] != "estar":
                break
    if acceso:
        add("puerta", acceso[0], acceso[1], 0.8, 1.0, "ACCESO\nPRINCIPAL")
    return out


def superficies(m):
    """Superficies aproximadas: interior + muros (cubierta) y espacios exteriores."""
    esp_e, esp_i = m["espesor_muro_ext"], m["espesor_muro_int"]
    interior = sum(r["w"] * r["h"] for r in m["ambientes"])
    perim = sum(2 * (r["w"] + r["h"]) for r in m["ambientes"])
    # los muros compartidos se cuentan una vez: estimación con el perímetro de la unión
    xs = [r["x"] for r in m["ambientes"]] + [r["x"] + r["w"] for r in m["ambientes"]]
    ys = [r["y"] for r in m["ambientes"]] + [r["y"] + r["h"] for r in m["ambientes"]]
    muros = perim * (esp_i + esp_e) / 4
    cubierta = interior + muros
    ext = {}
    for r in m["exteriores"]:
        k = {"cochera": "Cochera abierta", "galeria": "Galería"}.get(r["tipo"])
        if k:
            ext[k] = ext.get(k, 0) + r["w"] * r["h"]
    return dict(cubierta=cubierta, exteriores=ext, total=cubierta + sum(ext.values()))
