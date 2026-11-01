"""Exportación del plano a DXF (AutoCAD): capas separadas para muros, aberturas, cotas, textos y terreno. Unidades: metros."""
import math
from pathlib import Path

import ezdxf

from .dibujo import calcular_aberturas, espesor, segmentos_muro


def exportar_dxf(m, ruta):
    H = m["lote"]["alto"]
    Wl = m["lote"]["ancho"]
    doc = ezdxf.new("R2010")
    doc.units = 6   # metros
    for nom, col in (("TERRENO", 8), ("MUROS", 7), ("PUERTAS", 1), ("VENTANAS", 5), ("COTAS", 3), ("TEXTOS", 2), ("AMBIENTES", 4), ("EXTERIORES", 94)):
        doc.layers.add(nom, color=col)
    msp = doc.modelspace()
    Y = lambda y: H - y                                   # el DXF tiene Y hacia arriba
    msp.add_lwpolyline([(0, Y(0)), (Wl, Y(0)), (Wl, Y(H)), (0, Y(H))], close=True, dxfattribs={"layer": "TERRENO"})
    for r in m["exteriores"]:
        msp.add_lwpolyline([(r["x"], Y(r["y"])), (r["x"] + r["w"], Y(r["y"])), (r["x"] + r["w"], Y(r["y"] + r["h"])), (r["x"], Y(r["y"] + r["h"]))], close=True, dxfattribs={"layer": "EXTERIORES"})
    segs = segmentos_muro(m)
    for s in segs:
        t = espesor(m, s)
        if s["o"] == "H":
            pts = [(s["a"] - t / 2, Y(s["c"] - t / 2)), (s["b"] + t / 2, Y(s["c"] - t / 2)), (s["b"] + t / 2, Y(s["c"] + t / 2)), (s["a"] - t / 2, Y(s["c"] + t / 2))]
        else:
            pts = [(s["c"] - t / 2, Y(s["a"] - t / 2)), (s["c"] + t / 2, Y(s["a"] - t / 2)), (s["c"] + t / 2, Y(s["b"] + t / 2)), (s["c"] - t / 2, Y(s["b"] + t / 2))]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "MUROS"})
        h = msp.add_hatch(color=7, dxfattribs={"layer": "MUROS"}); h.set_solid_fill(color=7); h.paths.add_polyline_path(pts, is_closed=True)
    for o in calcular_aberturas(m, segs):
        t = o["t"]; (x0, y0), (x1, y1) = o["p0"], o["p1"]
        if o["tipo"] == "ventana":
            if o["ori"] == "H":
                pts = [(x0, Y(o["c"] - t / 2)), (x1, Y(o["c"] - t / 2)), (x1, Y(o["c"] + t / 2)), (x0, Y(o["c"] + t / 2))]
                msp.add_line((x0, Y(o["c"])), (x1, Y(o["c"])), dxfattribs={"layer": "VENTANAS"})
            else:
                pts = [(o["c"] - t / 2, Y(y0)), (o["c"] + t / 2, Y(y0)), (o["c"] + t / 2, Y(y1)), (o["c"] - t / 2, Y(y1))]
                msp.add_line((o["c"], Y(y0)), (o["c"], Y(y1)), dxfattribs={"layer": "VENTANAS"})
            msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "VENTANAS"})
        elif o["tipo"] == "puerta":
            n = o["n"] if o["giro"] == "adentro" else (-o["n"][0], -o["n"][1])
            hinge, other = ((x0, y0), (x1, y1)) if o["bisagra"] == "izq" else ((x1, y1), (x0, y0))
            a = o["a"]
            end = (hinge[0] + a * n[0], hinge[1] + a * n[1])
            msp.add_line((hinge[0], Y(hinge[1])), (end[0], Y(end[1])), dxfattribs={"layer": "PUERTAS"})
            v1 = (n[0], -n[1]); v2 = (other[0] - hinge[0], -(other[1] - hinge[1]))      # vectores en coordenadas DXF
            a1, a2 = math.degrees(math.atan2(v1[1], v1[0])), math.degrees(math.atan2(v2[1], v2[0]))
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            s1, s2 = (a1, a2) if cross > 0 else (a2, a1)
            msp.add_arc((hinge[0], Y(hinge[1])), a, s1 % 360, s2 % 360, dxfattribs={"layer": "PUERTAS"})
    # textos de ambientes
    for r in m["ambientes"] + m["exteriores"]:
        cx, cy = r["x"] + r["w"] / 2, Y(r["y"] + r["h"] / 2)
        nombre = r["nombre"].replace("\n", " ")
        msp.add_text(nombre, height=0.16, dxfattribs={"layer": "AMBIENTES", "insert": (cx, cy + 0.1)}).set_placement((cx, cy + 0.1), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        if r["tipo"] not in ("pasillo", "hall", "jardin", "patio"):
            msp.add_text(f"{r['w']:.2f} x {r['h']:.2f}", height=0.13, dxfattribs={"layer": "AMBIENTES"}).set_placement((cx, cy - 0.15), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    # cotas simples (cadena superior y lateral izquierda)
    xs = sorted({0.0, Wl} | {r["x"] for r in m["ambientes"]} | {r["x"] + r["w"] for r in m["ambientes"]})
    ys = sorted({0.0, H} | {r["y"] for r in m["ambientes"]} | {r["y"] + r["h"] for r in m["ambientes"]})
    for a, b in zip(xs, xs[1:]):
        if b - a >= 0.5:
            msp.add_line((a, Y(-0.9)), (b, Y(-0.9)), dxfattribs={"layer": "COTAS"})
            msp.add_text(f"{b-a:.2f}", height=0.14, dxfattribs={"layer": "COTAS"}).set_placement(((a + b) / 2, Y(-0.9) + 0.1), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
    for a, b in zip(ys, ys[1:]):
        if b - a >= 0.5:
            msp.add_line((-0.9, Y(a)), (-0.9, Y(b)), dxfattribs={"layer": "COTAS"})
            t = msp.add_text(f"{b-a:.2f}", height=0.14, rotation=90, dxfattribs={"layer": "COTAS"}); t.set_placement((-1.0, (Y(a) + Y(b)) / 2), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
    msp.add_text(f"{m['titulo']} - {m['subtitulo']}", height=0.3, dxfattribs={"layer": "TEXTOS"}).set_placement((0, Y(H) - 1.0), align=ezdxf.enums.TextEntityAlignment.LEFT)
    doc.saveas(str(ruta))
    return Path(ruta)
