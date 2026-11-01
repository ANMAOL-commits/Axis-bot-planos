"""Dibujo del plano de planta (matplotlib): muros, aberturas, mobiliario, cotas y cuadro lateral. Salida PNG / PDF / SVG."""
import math
import random
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Arc, Circle, Ellipse, FancyBboxPatch, Polygon, Rectangle
from PIL import Image

from .modelo import superficies

NAVY, ORANGE = "#022960", "#E0510A"
COL = dict(pasto="#8CAE66", pasto2="#6E9350", muro="#1B1B1B", piso="#EEE8DD", bano="#D2D8DC", dorm="#EFE6D8", estar="#ECE3D5", galeria="#E4DACB", grava="#B7B7B1", vereda="#CFD2CC",
           madera="#8B6B4B", madera2="#B39170", tela="#CBD0D8", tela2="#9097A1", blanco="#F7F7F5", mesada="#D9D9D6", agua="#D7E9F4")
OP = {"N": "S", "S": "N", "E": "W", "W": "E"}
INTERIORES_SIN_COTA = ("pasillo", "hall")


# ------------------------------------------------------------------ geometría
def segmentos_muro(m):
    lines = {}
    for r in m["ambientes"]:
        x0, y0, x1, y1 = r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]
        for o, c, a, b in (("H", y0, x0, x1), ("H", y1, x0, x1), ("V", x0, y0, y1), ("V", x1, y0, y1)):
            lines.setdefault((o, round(c, 2)), []).append((a, b))
    segs = []
    for (o, c), ivs in lines.items():
        pts = sorted({round(p, 3) for iv in ivs for p in iv})
        for a, b in zip(pts, pts[1:]):
            n = sum(1 for lo, hi in ivs if lo <= a + 1e-6 and hi >= b - 1e-6)
            if n > 0:
                segs.append(dict(o=o, c=c, a=a, b=b, n=n))
    return segs


def espesor(m, seg):
    return m["espesor_muro_int"] if seg["n"] >= 2 else m["espesor_muro_ext"]


def lado_info(r, lado):
    """(orientación, coord. del muro, inicio, largo, u, n_interior)"""
    if lado == "N":
        return "H", r["y"], r["x"], r["w"], (1, 0), (0, 1)
    if lado == "S":
        return "H", r["y"] + r["h"], r["x"], r["w"], (1, 0), (0, -1)
    if lado == "W":
        return "V", r["x"], r["y"], r["h"], (0, 1), (1, 0)
    return "V", r["x"] + r["w"], r["y"], r["h"], (0, 1), (-1, 0)


def marco(r, lado):
    """Sistema local: u a lo largo del muro 'lado', v hacia el interior. Devuelve (largo_muro, profundidad, place)."""
    if lado == "N":
        return r["w"], r["h"], lambda u, v, wu, wv: (r["x"] + u, r["y"] + v, wu, wv)
    if lado == "S":
        return r["w"], r["h"], lambda u, v, wu, wv: (r["x"] + u, r["y"] + r["h"] - v - wv, wu, wv)
    if lado == "W":
        return r["h"], r["w"], lambda u, v, wu, wv: (r["x"] + v, r["y"] + u, wv, wu)
    return r["h"], r["w"], lambda u, v, wu, wv: (r["x"] + r["w"] - v - wv, r["y"] + u, wv, wu)


def rect(ax, x, y, w, h, fc, ec="#4a4a4a", lw=0.5, z=4, r=0.0, alpha=1.0):
    if r > 0:
        p = FancyBboxPatch((x + r, y + r), w - 2 * r, h - 2 * r, boxstyle=f"round,pad={r},rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=z, alpha=alpha)
    else:
        p = Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=z, alpha=alpha)
    ax.add_patch(p)
    return p


# ------------------------------------------------------------------ aberturas
def calcular_aberturas(m, segs):
    amb = {r["id"]: r for r in m["ambientes"]}
    out = []
    for o in m["aberturas"]:
        r = amb[o["ambiente"]]
        ori, c, start, largo, u, n = lado_info(r, o["lado"])
        a = min(o["ancho"], largo - 0.4)
        centro = o["pos_m"] if o["pos_m"] is not None else o["pos"] * largo
        centro = min(max(centro, a / 2 + 0.2), largo - a / 2 - 0.2)
        p0 = (r["x"] if ori == "H" else c, c if ori == "H" else r["y"])
        p0 = (p0[0] + u[0] * (centro - a / 2), p0[1] + u[1] * (centro - a / 2))
        p1 = (p0[0] + u[0] * a, p0[1] + u[1] * a)
        t = max([espesor(m, s) for s in segs if s["o"] == ori and abs(s["c"] - c) < 0.03 and s["a"] - 1e-6 <= centro + start <= s["b"] + 1e-6] or [m["espesor_muro_ext"]])
        out.append(dict(o, r=r, ori=ori, c=c, p0=p0, p1=p1, u=u, n=n, a=a, t=t, centro=centro + start))
    return out


def dibujar_aberturas(ax, ab):
    for o in ab:
        t, ori = o["t"], o["ori"]
        (x0, y0), (x1, y1) = o["p0"], o["p1"]
        if ori == "H":
            ax.add_patch(Rectangle((x0, o["c"] - t / 2 - 0.01), o["a"], t + 0.02, fc=COL["piso"], ec="none", zorder=7))
        else:
            ax.add_patch(Rectangle((o["c"] - t / 2 - 0.01, y0), t + 0.02, o["a"], fc=COL["piso"], ec="none", zorder=7))
        if o["tipo"] == "ventana":
            if ori == "H":
                ax.add_patch(Rectangle((x0, o["c"] - t / 2), o["a"], t, fc=COL["agua"], ec="#2b2b2b", lw=0.6, zorder=8))
                ax.plot([x0, x1], [o["c"], o["c"]], color="#2b2b2b", lw=0.5, zorder=8)
            else:
                ax.add_patch(Rectangle((o["c"] - t / 2, y0), t, o["a"], fc=COL["agua"], ec="#2b2b2b", lw=0.6, zorder=8))
                ax.plot([o["c"], o["c"]], [y0, y1], color="#2b2b2b", lw=0.5, zorder=8)
        elif o["tipo"] == "puerta":
            n = o["n"] if o["giro"] == "adentro" else (-o["n"][0], -o["n"][1])
            hinge, other = ((x0, y0), (x1, y1)) if o["bisagra"] == "izq" else ((x1, y1), (x0, y0))
            a = o["a"]
            end = (hinge[0] + a * n[0], hinge[1] + a * n[1])
            ax.plot([hinge[0], end[0]], [hinge[1], end[1]], color="#222", lw=1.3, zorder=9, solid_capstyle="butt")
            v1 = math.degrees(math.atan2(n[1], n[0]))
            v2 = math.degrees(math.atan2(other[1] - hinge[1], other[0] - hinge[0]))
            cross = n[0] * (other[1] - hinge[1]) - n[1] * (other[0] - hinge[0])
            t1, t2 = (v1, v2) if cross > 0 else (v2, v1)
            if t2 < t1:
                t2 += 360
            ax.add_patch(Arc(hinge, 2 * a, 2 * a, theta1=t1, theta2=t2, color="#555", lw=0.6, zorder=9))


# ------------------------------------------------------------------ vegetación y suelos
def arbol(ax, cx, cy, rad, rnd):
    for k in range(7):
        ang = rnd.uniform(0, 2 * math.pi)
        d = rad * rnd.uniform(0.0, 0.55)
        rr = rad * rnd.uniform(0.45, 0.75)
        ax.add_patch(Circle((cx + d * math.cos(ang), cy + d * math.sin(ang)), rr, fc=rnd.choice(["#4C7A3A", "#5C8B45", "#3E6B31", "#6A9A52"]), ec="none", alpha=0.95, zorder=3))
    ax.add_patch(Circle((cx - rad * 0.2, cy - rad * 0.2), rad * 0.3, fc="#86B06A", ec="none", alpha=0.6, zorder=3))


def dentro(x, y, r, pad=0.0):
    return r["x"] - pad <= x <= r["x"] + r["w"] + pad and r["y"] - pad <= y <= r["y"] + r["h"] + pad


def suelos(ax, m, rnd, vegetacion):
    W, H = m["lote"]["ancho"], m["lote"]["alto"]
    ax.add_patch(Rectangle((0, 0), W, H, fc=COL["pasto"], ec="#7a7a7a", lw=0.8, zorder=0))
    if vegetacion:
        xs, ys = np.array([rnd.uniform(0, W) for _ in range(int(W * H * 14))]), np.array([rnd.uniform(0, H) for _ in range(int(W * H * 14))])
        ax.scatter(xs, ys, s=2.2, c=COL["pasto2"], alpha=0.35, linewidths=0, zorder=1)
    for r in m["exteriores"]:
        t = r["tipo"]
        if t in ("galeria", "terraza"):
            rect(ax, r["x"], r["y"], r["w"], r["h"], COL["galeria"], ec="none", z=1.5)
            for i in range(1, int(r["w"] / 0.6)):
                ax.plot([r["x"] + i * 0.6] * 2, [r["y"], r["y"] + r["h"]], color="#d5c9b8", lw=0.3, zorder=1.6)
        elif t == "cochera":
            rect(ax, r["x"], r["y"], r["w"], r["h"], COL["grava"], ec="none", z=1.5)
            xs = np.array([rnd.uniform(r["x"], r["x"] + r["w"]) for _ in range(int(r["w"] * r["h"] * 40))]); ys = np.array([rnd.uniform(r["y"], r["y"] + r["h"]) for _ in range(int(r["w"] * r["h"] * 40))])
            ax.scatter(xs, ys, s=1.2, c=["#9a9a94" if rnd.random() < 0.5 else "#d0d0ca" for _ in xs], linewidths=0, zorder=1.6)
        elif t == "vereda":
            rect(ax, r["x"], r["y"], r["w"], r["h"], COL["vereda"], ec="#b9bcb5", lw=0.4, z=1.5)
    for r in m["ambientes"]:
        c = {"bano": COL["bano"], "lavadero": COL["bano"], "dormitorio": COL["dorm"], "estar": COL["estar"]}.get(r["tipo"], COL["piso"])
        rect(ax, r["x"], r["y"], r["w"], r["h"], c, ec="none", z=2)
        if r["tipo"] in ("bano", "lavadero", "cocina", "cocina_comedor"):
            step = 0.5
            for i in range(1, int(r["w"] / step) + 1):
                ax.plot([r["x"] + i * step] * 2, [r["y"], r["y"] + r["h"]], color="#ffffff", lw=0.25, alpha=0.7, zorder=2.1)
            for j in range(1, int(r["h"] / step) + 1):
                ax.plot([r["x"], r["x"] + r["w"]], [r["y"] + j * step] * 2, color="#ffffff", lw=0.25, alpha=0.7, zorder=2.1)
    if vegetacion:
        libres = []
        for _ in range(400):
            x, y = rnd.uniform(0.4, W - 0.4), rnd.uniform(0.4, H - 0.4)
            if any(dentro(x, y, r, 1.0) for r in m["ambientes"]) or any(dentro(x, y, r, 0.6) for r in m["exteriores"] if r["tipo"] in ("galeria", "cochera", "vereda", "terraza")):
                continue
            if any(math.hypot(x - a, y - b) < 1.6 for a, b in libres):
                continue
            libres.append((x, y))
            if len(libres) >= 14:
                break
        for x, y in libres:
            arbol(ax, x, y, rnd.uniform(0.5, 0.95), rnd)


# ------------------------------------------------------------------ mobiliario
def lados_puerta(m, ab):
    res = {r["id"]: set() for r in m["ambientes"]}
    for o in ab:
        if o["tipo"] in ("puerta", "paso"):
            res[o["r"]["id"]].add(o["lado"])
            cx, cy = o["p0"][0] + (o["p1"][0] - o["p0"][0]) / 2, o["p0"][1] + (o["p1"][1] - o["p0"][1]) / 2
            for r2 in m["ambientes"]:
                if r2["id"] == o["r"]["id"]:
                    continue
                for lado in "NSEW":
                    ori, c, start, largo, u, n = lado_info(r2, lado)
                    ok = abs(c - o["c"]) < 0.03 and ori == o["ori"] and start - 0.05 <= (cx if ori == "H" else cy) <= start + largo + 0.05
                    if ok:
                        res[r2["id"]].add(lado)
    return res


def mejor_lado(r, puertas, preferir_largo=True, evitar=()):
    libres = [s for s in "NSEW" if s not in puertas and s not in evitar] or [s for s in "NSEW" if s not in puertas] or list("NSEW")
    key = (lambda s: -(r["w"] if s in "NS" else r["h"])) if preferir_largo else (lambda s: 0)
    opuestos = [s for s in libres if OP[s] in puertas]
    return sorted(opuestos or libres, key=key)[0]


def silla(ax, x, y, s=0.42):
    rect(ax, x - s / 2, y - s / 2, s, s, COL["madera2"], ec="#6b5238", lw=0.4, z=4.2, r=0.06)


def mesa_con_sillas(ax, cx, cy, w, h, n_lado=3, horizontal=True):
    rect(ax, cx - w / 2, cy - h / 2, w, h, COL["madera"], ec="#5a4330", lw=0.6, z=4.1, r=0.04)
    if horizontal:
        for i in range(n_lado):
            x = cx - w / 2 + w * (i + 0.5) / n_lado
            silla(ax, x, cy - h / 2 - 0.28); silla(ax, x, cy + h / 2 + 0.28)
    else:
        for i in range(n_lado):
            y = cy - h / 2 + h * (i + 0.5) / n_lado
            silla(ax, cx - w / 2 - 0.28, y); silla(ax, cx + w / 2 + 0.28, y)


def cama(ax, r, puertas):
    lado = mejor_lado(r, puertas)
    L, D, P = marco(r, lado)
    mm = 0.2
    area = r["w"] * r["h"]
    if area <= 11.6:
        camas, ancho = 2, 0.9
    else:
        camas, ancho = 1, 1.6 if min(r["w"], r["h"]) >= 3.0 else 1.4
    largo = 2.0 if D > 3.0 else 1.9
    gap = 0.45
    total = camas * ancho + (gap if camas == 2 else 0) + 2 * 0.42
    u0 = (L - total) / 2 + 0.42 if camas == 1 else (L - (2 * ancho + gap)) / 2
    for k in range(camas):
        u = u0 + k * (ancho + gap)
        x, y, w, h = P(u, mm, ancho, largo)
        rect(ax, x, y, w, h, COL["tela"], z=4.1, r=0.03)
        # cobertor y almohadas
        xv, yv, wv, hv = P(u, mm + largo * 0.38, ancho, largo * 0.62)
        rect(ax, xv, yv, wv, hv, COL["tela2"], ec="#6c727c", lw=0.4, z=4.15, r=0.03)
        for j in range(2 if ancho > 1.2 else 1):
            pw = ancho / (2 if ancho > 1.2 else 1) - 0.12
            xp, yp, wp, hp = P(u + 0.06 + j * (pw + 0.12), mm + 0.06, pw, 0.3)
            rect(ax, xp, yp, wp, hp, "#FBFBFB", ec="#8c8c8c", lw=0.4, z=4.2, r=0.05)
    nt = [(u0 - 0.45, 0.4), (u0 + camas * ancho + (gap if camas == 2 else 0) + 0.05, 0.4)] if camas == 1 else [(u0 + ancho + 0.02, 0.4)]
    for u, w in nt:
        if 0 <= u <= L - 0.4:
            x, y, ww, hh = P(u, mm, w, 0.4)
            rect(ax, x, y, ww, hh, COL["madera2"], ec="#5a4330", lw=0.5, z=4.1)
    # placard en otra pared libre
    lado2 = [s for s in "NSEW" if s not in puertas and s != lado and s != OP[lado]]
    if r["tipo"] == "dormitorio" and lado2 and area > 11.0:
        L2, D2, P2 = marco(r, lado2[0])
        x, y, w, h = P2(max(0.4, L2 / 2 - 0.9), mm, 1.8, 0.45) if L2 > 2.6 else P2(0.3, mm, min(1.5, L2 - 0.6), 0.45)
        rect(ax, x, y, w, h, COL["madera"], ec="#5a4330", lw=0.5, z=4.1)


def inodoro(ax, P, u, mm):
    x, y, w, h = P(u, mm, 0.38, 0.22); rect(ax, x, y, w, h, "#FFFFFF", ec="#555", lw=0.5, z=4.2, r=0.03)
    x, y, w, h = P(u + 0.03, mm + 0.2, 0.32, 0.42)
    ax.add_patch(Ellipse((x + w / 2, y + h / 2), w, h, fc="#FFFFFF", ec="#555", lw=0.5, zorder=4.2))


def bano(ax, r, puertas):
    lado = mejor_lado(r, puertas)
    L, D, P = marco(r, lado)
    mm = 0.2
    inodoro(ax, P, 0.3, mm)
    x, y, w, h = P(1.0, mm, 0.55, 0.45) if L >= 1.7 else P(0.8, mm, 0.45, 0.4)
    rect(ax, x, y, w, h, "#FFFFFF", ec="#555", lw=0.5, z=4.2, r=0.05)
    ax.add_patch(Ellipse((x + w / 2, y + h / 2), w * 0.6, h * 0.6, fc=COL["agua"], ec="#555", lw=0.4, zorder=4.3))
    if L >= 1.9 and D >= 1.8:
        x, y, w, h = P(L - 0.95 - mm, mm, 0.9, 0.9)
        rect(ax, x, y, w, h, "#E8EEF2", ec="#555", lw=0.6, z=4.1)
        ax.plot([x, x + w], [y, y + h], color="#9bb", lw=0.4, zorder=4.2); ax.plot([x + w, x], [y, y + h], color="#9bb", lw=0.4, zorder=4.2)
        ax.add_patch(Circle((x + w / 2, y + h / 2), 0.05, fc="#777", ec="none", zorder=4.3))


def estar(ax, r, puertas):
    lado = mejor_lado(r, puertas)
    L, D, P = marco(r, lado)
    mm = 0.22
    sofa = min(2.6, L - 1.0)
    u = (L - sofa) / 2 - (0.45 if D >= 3.0 else 0)
    x, y, w, h = P(max(0.3, u - 1.1), 1.0, min(L - 0.6, sofa + 1.6), min(2.0, D - 1.3)); rect(ax, x, y, w, h, "#C7C9CC", ec="none", z=3.2, alpha=0.8)  # alfombra
    x, y, w, h = P(u, mm, sofa, 0.9); rect(ax, x, y, w, h, "#E9E9E6", ec="#7a7a7a", lw=0.6, z=4.1, r=0.06)
    for k in range(3):
        xk, yk, wk, hk = P(u + 0.08 + k * (sofa - 0.16) / 3, mm + 0.08, (sofa - 0.16) / 3 - 0.04, 0.72); rect(ax, xk, yk, wk, hk, "#F6F6F4", ec="#9a9a9a", lw=0.3, z=4.15, r=0.05)
    if D >= 3.0:
        x, y, w, h = P(u + sofa - 0.9 if u + sofa + 0.1 < L else u + sofa - 0.9, mm + 0.9, 0.9, 1.4); rect(ax, x, y, w, h, "#E9E9E6", ec="#7a7a7a", lw=0.6, z=4.1, r=0.06)
        x, y, w, h = P(u + 0.3, mm + 1.5, 1.0, 0.6); rect(ax, x, y, w, h, COL["madera"], ec="#5a4330", lw=0.6, z=4.2, r=0.03)
        ax.plot([x + 0.2, x + w - 0.2], [y + h / 2, y + h / 2], color="#d4b27a", lw=0.5, zorder=4.3)


def cocina_c(ax, r, puertas):
    lado = mejor_lado(r, puertas)
    L, D, P = marco(r, lado)
    mm = 0.2
    cl = min(L - 0.4, 4.2)
    u0 = L - cl - 0.2 if cl < L - 0.5 else 0.2
    x, y, w, h = P(u0, mm, cl, 0.6); rect(ax, x, y, w, h, COL["mesada"], ec="#555", lw=0.6, z=4.1)
    x, y, w, h = P(u0 + 0.35, mm + 0.07, 0.65, 0.46); rect(ax, x, y, w, h, "#EDEDED", ec="#555", lw=0.5, z=4.2, r=0.04)
    x, y, w, h = P(u0 + cl * 0.55, mm + 0.03, 0.58, 0.54); rect(ax, x, y, w, h, "#2f2f2f", ec="#111", lw=0.5, z=4.2)
    for du, dv in ((0.15, 0.15), (0.43, 0.15), (0.15, 0.39), (0.43, 0.39)):
        xx, yy, ww, hh = P(u0 + cl * 0.55 + du - 0.06, mm + 0.03 + dv - 0.06, 0.12, 0.12); ax.add_patch(Circle((xx + 0.06, yy + 0.06), 0.06, fc="#888", ec="#ddd", lw=0.3, zorder=4.3))
    x, y, w, h = P(u0 + cl - 0.7, mm, 0.7, 0.65); rect(ax, x, y, w, h, "#EEF1F3", ec="#555", lw=0.6, z=4.3)


def comedor_c(ax, r, puertas, cocina_tambien):
    cx, cy = r["x"] + r["w"] * (0.35 if cocina_tambien else 0.5), r["y"] + r["h"] * 0.55
    horiz = r["w"] >= r["h"] * 0.9
    mesa_con_sillas(ax, cx, cy, 2.0 if horiz else 0.95, 0.95 if horiz else 2.0, 3, horiz)
    if cocina_tambien and r["w"] * r["h"] >= 16:
        ix, iy = r["x"] + r["w"] * 0.7, r["y"] + r["h"] * 0.5
        rect(ax, ix - 0.5, iy - 0.9, 1.0, 1.8, "#F1F1EE", ec="#555", lw=0.6, z=4.1)
        ax.add_patch(Circle((ix, iy), 0.22, fc="#9a9a96", ec="#333", lw=0.4, zorder=4.3))
        for k in (-0.6, 0, 0.6):
            ax.add_patch(Circle((ix + 0.68, iy + k), 0.15, fc="#FFFFFF", ec="#555", lw=0.4, zorder=4.2))


def vestidor(ax, r, puertas):
    libres = [s for s in "NSEW" if s not in puertas]
    for s in sorted(libres, key=lambda s: -(r["w"] if s in "NS" else r["h"]))[:2]:
        L, D, P = marco(r, s)
        x, y, w, h = P(0.2, 0.2, L - 0.4, 0.5); rect(ax, x, y, w, h, COL["madera"], ec="#5a4330", lw=0.5, z=4.1)
        for k in range(int((L - 0.4) / 0.12)):
            xx, yy, ww, hh = P(0.2 + k * 0.12 + 0.03, 0.24, 0.03, 0.42); rect(ax, xx, yy, ww, hh, "#3b2a1b", ec="none", z=4.2)


def lavadero(ax, r, puertas):
    L, D, P = marco(r, mejor_lado(r, puertas))
    x, y, w, h = P(0.2, 0.2, 0.6, 0.6); rect(ax, x, y, w, h, "#FFFFFF", ec="#555", lw=0.5, z=4.2, r=0.04); ax.add_patch(Circle((x + w / 2, y + h / 2), 0.2, fc=COL["agua"], ec="#555", lw=0.4, zorder=4.3))
    if L > 1.6:
        x, y, w, h = P(1.0, 0.2, 0.8, 0.5); rect(ax, x, y, w, h, "#EDEDED", ec="#555", lw=0.5, z=4.2, r=0.05)


def escritorio(ax, r, puertas):
    L, D, P = marco(r, mejor_lado(r, puertas))
    x, y, w, h = P(max(0.2, L / 2 - 0.7), 0.2, 1.4, 0.7); rect(ax, x, y, w, h, COL["madera"], ec="#5a4330", lw=0.5, z=4.1)
    x, y, w, h = P(max(0.2, L / 2 - 0.2), 0.95, 0.45, 0.45); rect(ax, x, y, w, h, "#555", ec="#222", lw=0.5, z=4.2, r=0.08)


def galeria(ax, r):
    mesa_con_sillas(ax, r["x"] + r["w"] * 0.5, r["y"] + r["h"] * 0.45, 2.0, 0.95, 3, True)
    rect(ax, r["x"] + r["w"] - 0.62, r["y"] + 0.1, 0.52, min(r["h"] - 0.3, 2.6), "#2d2d2d", ec="#111", lw=0.5, z=4.1)
    rect(ax, r["x"] + r["w"] - 0.5, r["y"] + 0.25, 0.28, 0.5, "#EDEDED", ec="#555", lw=0.4, z=4.2)


def auto(ax, cx, cy, color, rnd):
    """Auto visto desde arriba, orientado hacia arriba."""
    w, l = 1.85, 4.4
    rect(ax, cx - w / 2, cy - l / 2, w, l, color, ec="#222", lw=0.7, z=4.1, r=0.35)
    rect(ax, cx - w / 2 + 0.2, cy - l / 2 + 1.05, w - 0.4, 0.95, "#1d2530", ec="#111", lw=0.4, z=4.2, r=0.15)       # parabrisas
    rect(ax, cx - w / 2 + 0.22, cy + 0.25, w - 0.44, 0.7, "#1d2530", ec="#111", lw=0.4, z=4.2, r=0.12)                # luneta
    rect(ax, cx - w / 2 + 0.15, cy - 0.7, w - 0.3, 0.95, "#cfd3d8" if color == "#F2F2F0" else "#4a4f57", ec="none", z=4.2, r=0.1)  # techo
    rect(ax, cx - w / 2 - 0.12, cy - l / 2 + 1.05, 0.14, 0.28, color, ec="#222", lw=0.4, z=4.2)
    rect(ax, cx + w / 2 - 0.02, cy - l / 2 + 1.05, 0.14, 0.28, color, ec="#222", lw=0.4, z=4.2)


def cochera(ax, r, rnd):
    n = 2 if r["w"] >= 4.2 else 1
    for i in range(n):
        cx = r["x"] + r["w"] * (i + 0.5) / n
        auto(ax, cx, r["y"] + r["h"] / 2, "#F2F2F0" if i % 2 == 0 else "#5A5F67", rnd)


def mobiliario(ax, m, ab, rnd):
    puertas = lados_puerta(m, ab)
    for r in m["ambientes"]:
        p, t = puertas[r["id"]], r["tipo"]
        if t == "dormitorio":
            cama(ax, r, p)
        elif t == "bano":
            bano(ax, r, p)
        elif t == "estar":
            estar(ax, r, p)
        elif t == "cocina_comedor":
            cocina_c(ax, r, p); comedor_c(ax, r, p, True)
        elif t == "cocina":
            cocina_c(ax, r, p)
        elif t == "comedor":
            comedor_c(ax, r, p, False)
        elif t == "vestidor":
            vestidor(ax, r, p)
        elif t == "lavadero":
            lavadero(ax, r, p)
        elif t == "escritorio":
            escritorio(ax, r, p)
    for r in m["exteriores"]:
        if r["tipo"] in ("galeria", "terraza"):
            galeria(ax, r)
        elif r["tipo"] == "cochera":
            cochera(ax, r, rnd)


# ------------------------------------------------------------------ cotas y rótulos
def cota_h(ax, x0, x1, y, txt, ext_y=None, fs=7.5):
    ax.plot([x0, x1], [y, y], color="#222", lw=0.6, zorder=10)
    for x in (x0, x1):
        ax.plot([x - 0.1, x + 0.1], [y + 0.1, y - 0.1], color="#222", lw=0.8, zorder=10)
        if ext_y is not None:
            ax.plot([x, x], [y - 0.12, ext_y], color="#8a8a8a", lw=0.3, zorder=9)
    ax.text((x0 + x1) / 2, y - 0.14, txt, ha="center", va="bottom", fontsize=fs, zorder=11, color="#111")


def cota_v(ax, y0, y1, x, txt, ext_x=None, fs=7.5):
    ax.plot([x, x], [y0, y1], color="#222", lw=0.6, zorder=10)
    for y in (y0, y1):
        ax.plot([x - 0.1, x + 0.1], [y + 0.1, y - 0.1], color="#222", lw=0.8, zorder=10)
        if ext_x is not None:
            ax.plot([x - 0.12, ext_x], [y, y], color="#8a8a8a", lw=0.3, zorder=9)
    ax.text(x - 0.14, (y0 + y1) / 2, txt, ha="right", va="center", rotation=90, fontsize=fs, zorder=11, color="#111")


def fmt(v):
    return f"{v:.2f}"


def cotas(ax, m):
    W, H = m["lote"]["ancho"], m["lote"]["alto"]
    puntos_x = sorted({0.0, W} | {round(r["x"], 2) for r in m["ambientes"] + m["exteriores"]} | {round(r["x"] + r["w"], 2) for r in m["ambientes"] + m["exteriores"]})
    puntos_y = sorted({0.0, H} | {round(r["y"], 2) for r in m["ambientes"] + m["exteriores"]} | {round(r["y"] + r["h"], 2) for r in m["ambientes"] + m["exteriores"]})

    def filtrar(pts, maximo=5):
        for minimo in (0.55, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
            out = [pts[0]]
            for p in pts[1:]:
                if p - out[-1] >= minimo:
                    out.append(p)
            if out[-1] != pts[-1]:
                out[-1] = pts[-1]
            if len(out) - 1 <= maximo:
                return out
        return out
    px, py = filtrar(puntos_x), filtrar(puntos_y)
    for a, b in zip(px, px[1:]):
        cota_h(ax, a, b, -0.9, fmt(b - a), 0.0)
    cota_h(ax, 0, W, -1.7, fmt(W), -0.9)
    for a, b in zip(py, py[1:]):
        cota_v(ax, a, b, -0.9, fmt(b - a), 0.0)
    cota_v(ax, 0, H, -1.7, fmt(H), -0.9)
    cota_h(ax, 0, W, H + 0.9, fmt(W), H)


def rotulos(ax, m):
    W, H = m["lote"]["ancho"], m["lote"]["alto"]
    pulg_m = min(0.72 * 16.54 / (W + 3.8), 0.94 * 11.69 / (H + 4.5))      # pulgadas de papel por metro (A3)
    for r in m["ambientes"] + m["exteriores"]:
        fs = max(5.2, min(8.2, 3.6 + 1.2 * min(r["w"], r["h"])))
        max_car = max(7, int((r["w"] - 0.3) * pulg_m * 72 / (fs * 0.66)))
        lineas = []
        for part in r["nombre"].split("\n"):
            lineas += textwrap.wrap(part, max_car, break_long_words=False) or [""]
        if r["tipo"] not in INTERIORES_SIN_COTA + ("jardin", "patio", "galeria", "terraza", "vereda"):
            lineas.append(f"{fmt(r['w'])} x {fmt(r['h'])}")
        cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
        ax.text(cx, cy, "\n".join(lineas), ha="center", va="center", fontsize=fs, zorder=12, color="#111", linespacing=1.15,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.55 if r["tipo"] not in ("jardin", "patio") else 0.0))
    for o in m.get("_ab", []):
        if o.get("etiqueta"):
            cx, cy = (o["p0"][0] + o["p1"][0]) / 2, (o["p0"][1] + o["p1"][1]) / 2
            n = o["n"]
            ax.text(cx - n[0] * 0.75, cy - n[1] * 0.75, o["etiqueta"], ha="center", va="center", fontsize=6.8, zorder=12, linespacing=1.1,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))


# ------------------------------------------------------------------ panel lateral
def panel(fig, ax_main, m, sup, opciones, logo_path):
    fig.canvas.draw()
    px_m = abs(ax_main.transData.transform((1, 0))[0] - ax_main.transData.transform((0, 0))[0])
    in_m = px_m / fig.dpi
    escala = 1.0 / (in_m * 0.0254)
    escala_n = int(round(escala / 25.0) * 25) or 1
    fw, fh = fig.get_size_inches()
    x0 = fw * 0.745
    pw, ph = fw - x0 - 0.25, fh - 0.5
    ax2 = fig.add_axes([x0 / fw, 0.25 / fh, pw / fw, ph / fh]); ax2.set_xlim(0, pw); ax2.set_ylim(0, ph); ax2.axis("off")
    y = ph - 0.15

    def T(s, yy, size=9, weight="normal", x=0.0, ha="left", color="#111", style="normal"):
        ax2.text(x, yy, s, fontsize=size, fontweight=weight, ha=ha, va="top", color=color, fontstyle=style)

    def linea(yy, color="#222", lw=0.8):
        ax2.plot([0, pw], [yy, yy], color=color, lw=lw)
    T(m["titulo"], y, 17, "bold", color=NAVY); y -= 0.42
    T(m["subtitulo"], y, 12.5, color="#333"); y -= 0.38
    linea(y); y -= 0.28
    T("SUPERFICIES (aprox.)", y, 10.5, "bold"); y -= 0.3; linea(y, "#aaa", 0.5); y -= 0.1
    filas = [("Superficie cubierta:", f"{sup['cubierta']:.0f} m²")] + [(k + ":", f"{v:.0f} m²") for k, v in sup["exteriores"].items()] + [("Superficie total:", f"{sup['total']:.0f} m²")]
    for k, v in filas:
        T(k, y, 9); T(v, y, 9, x=pw * 0.52); y -= 0.26
    y -= 0.2
    T("AMBIENTES", y, 10.5, "bold"); y -= 0.3; linea(y, "#aaa", 0.5); y -= 0.1
    lista = [r for r in m["ambientes"] if r["tipo"] not in INTERIORES_SIN_COTA] + [r for r in m["exteriores"] if r["tipo"] in ("cochera", "galeria")]
    for r in lista[:16]:
        T(r["nombre"].replace("\n", " ").capitalize(), y, 8.6); T(f"{r['w']:.2f} x {r['h']:.2f} m", y, 8.6, x=pw * 0.60); y -= 0.235
    y -= 0.2
    notas = m.get("notas") or []
    if notas:
        T("NOTAS", y, 10.5, "bold"); y -= 0.3; linea(y, "#aaa", 0.5); y -= 0.1
        for n in notas:
            ls = textwrap.wrap(n, 40)
            for i, l in enumerate(ls):
                T(("- " if i == 0 else "  ") + l, y, 8.6); y -= 0.22
            y -= 0.04
    # norte
    cy = 2.55
    cx = pw * 0.5
    ax2.add_patch(Circle((cx, cy), 0.3, fc="white", ec="#222", lw=0.8))
    ang = math.radians(m.get("norte_grados", 0))
    tip = (cx + 0.3 * math.sin(ang), cy + 0.3 * math.cos(ang))
    ax2.add_patch(Polygon([tip, (cx - 0.09 * math.cos(ang) - 0.12 * math.sin(ang), cy + 0.09 * math.sin(ang) - 0.12 * math.cos(ang)), (cx + 0.09 * math.cos(ang) - 0.12 * math.sin(ang), cy - 0.09 * math.sin(ang) - 0.12 * math.cos(ang))], fc="#222", ec="#222"))
    ax2.text(cx + 0.5 * math.sin(ang) * 1.2, cy + 0.52 * math.cos(ang) * 1.25, "N", ha="center", va="center", fontsize=10, fontweight="bold")
    # escala gráfica
    ys = 1.55
    ax2.text(0, ys + 0.4, "ESCALA GRÁFICA", fontsize=7, ha="left", va="center", color="#222")
    seg = 1.0 * in_m
    for i in range(5):
        ax2.add_patch(Rectangle((i * seg, ys), seg, 0.08, fc="#111" if i % 2 == 0 else "white", ec="#111", lw=0.6))
        ax2.text(i * seg, ys - 0.12, str(i), fontsize=6.5, ha="center", va="top")
    ax2.text(5 * seg, ys - 0.12, "5 m", fontsize=6.5, ha="center", va="top")
    ax2.text(pw, ys + 0.4, f"Esc. aprox. 1:{escala_n}", fontsize=7, ha="right", va="center", color="#444")
    linea(1.05, "#888", 0.6)
    pie = m.get("pie") or ""
    if logo_path and Path(logo_path).exists():
        im = Image.open(logo_path).convert("RGBA")
        h = 0.62; w = h * im.size[0] / im.size[1]
        ax2.imshow(np.asarray(im), extent=[pw - w, pw, 0.18, 0.18 + h], aspect="auto", zorder=5)
        ax2.set_xlim(0, pw); ax2.set_ylim(0, ph)
    if pie:
        ax2.text(0, 0.85, pie, fontsize=8.5, ha="left", va="top", color="#222", linespacing=1.3)
    emp = opciones.get("empresa")
    if emp:
        ax2.text(0, 0.18, emp, fontsize=7, ha="left", va="bottom", color="#555")
    # separación vertical entre plano y panel
    fig.add_artist(plt.Line2D([x0 / fw - 0.006] * 2, [0.03, 0.97], color="#999", lw=0.8))


# ------------------------------------------------------------------ función principal
def dibujar(m, opciones=None):
    o = dict(muebles=True, vegetacion=True, cotas=True, cuadro=True, empresa="", logo=None, formato="A3", semilla=7)
    o.update(opciones or {})
    rnd = random.Random(o["semilla"])
    W, H = m["lote"]["ancho"], m["lote"]["alto"]
    size = (16.54, 11.69) if o["formato"] == "A3" else (11.69, 8.27)
    fig = plt.figure(figsize=size, dpi=110, facecolor="#FBFBF9")
    ax = fig.add_axes([0.012, 0.03, 0.72 if o["cuadro"] else 0.976, 0.94])
    ax.set_facecolor("#FBFBF9")
    ax.set_xlim(-2.6, W + 1.2); ax.set_ylim(H + 2.0, -2.5); ax.set_aspect("equal"); ax.axis("off")
    segs = segmentos_muro(m)
    ab = calcular_aberturas(m, segs)
    m["_ab"] = ab
    suelos(ax, m, rnd, o["vegetacion"])
    if o["muebles"]:
        mobiliario(ax, m, ab, rnd)
    for s in segs:
        t = espesor(m, s)
        if s["o"] == "H":
            ax.add_patch(Rectangle((s["a"] - t / 2, s["c"] - t / 2), s["b"] - s["a"] + t, t, fc=COL["muro"], ec="none", zorder=6))
        else:
            ax.add_patch(Rectangle((s["c"] - t / 2, s["a"] - t / 2), t, s["b"] - s["a"] + t, fc=COL["muro"], ec="none", zorder=6))
    dibujar_aberturas(ax, ab)
    rotulos(ax, m)
    if o["cotas"]:
        cotas(ax, m)
    if o["cuadro"]:
        panel(fig, ax, m, superficies(m), o, o["logo"])
    m.pop("_ab", None)
    return fig


def guardar(fig, carpeta, base="plano", dpi=170):
    carpeta = Path(carpeta)
    sal = {}
    for ext in ("png", "pdf", "svg"):
        ruta = carpeta / f"{base}.{ext}"
        fig.savefig(ruta, dpi=dpi if ext == "png" else None, facecolor=fig.get_facecolor())
        sal[ext] = ruta
    plt.close(fig)
    return sal
