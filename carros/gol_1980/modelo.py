# -*- coding: utf-8 -*-
"""
VW Gol 1300 L 1980 (1a geracao, "quadrado") - escala 1:32
Arquitetura: carroceria em DUAS METADES deitadas na face de corte (sem suporte),
vidros/frente/traseira em rebaixos, eixos passantes. Ver README.md desta pasta.
"""
import os
import numpy as np
from mathutils import Vector, Matrix
from kitcard.nucleo import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
NAME_TEXT = "GOL 1980"
KEEP_ORIENT = ("carroceria",)

# ---- referencia do veiculo (mm reais) ----
S = 1 / 32
REAL_LEN, REAL_W, REAL_H, WHEELBASE = 3790.0, 1601.0, 1375.0, 2358.0
TRACK_F, TRACK_R = 1350.0, 1366.0
BUMPER_OUT = 1.6                                # para-choque avanca 1,6 mm (impresso)
LEN = REAL_LEN - 2 * BUMPER_OUT / S             # carroceria sem para-choques (~3688)
AX_F = 930.0 - BUMPER_OUT / S                   # balanco dianteiro ~930 mm (motor longitudinal a frente do eixo)
AX_R = AX_F + WHEELBASE
ZB = 220.0
ZBELT = 940.0
ROOFZ = 1350.0
WROOF = 600.0
CROWN = 8.0
TIRE_R = (13 * 25.4 / 2 + 124) * S              # 155/80 R13 -> 18,1 mm
TIRE_W = 155 * S
LEN_MM, HEIGHT_MM = LEN * S, REAL_H * S

WS_A, WS_B = (1300.0, 925.0), (1850.0, 1340.0)
HATCH_A, HATCH_B = (3060.0, 1356.0), (3660.0, 880.0)
TOP = [(0, 760), (60, 800), WS_A, WS_B, (1990, 1372), (2600, 1378),
       HATCH_A, HATCH_B, (LEN, 858)]
TOP_R = [0, 50, 60, 90, 120, 0, 120, 30, 0]
REAR_GLASS_BOTTOM_Z = 1050.0
TOPP = round_poly(TOP, TOP_R)
ws_x = lambda z: line_x(WS_A, WS_B, z)
hatch_x = lambda z: line_x(HATCH_A, HATCH_B, z)
NSEG = (4, 6, 20, 8, 6, 10)
I_SIDE0 = NSEG[0] - 1
I_SIDE1 = sum(n - 1 for n in NSEG[:5])
I_TOP0 = sum(n - 1 for n in NSEG[:5])
_sec = {}
BODY_PINS = [(1250, 560), (2300, 800), (3050, 650)]
FRONT_Z = (495.0, 705.0)
FBUMP_Z = (300.0, 470.0)
REAR_Z = (540.0, 850.0)
RBUMP_Z = (330.0, 440.0)
FRONT_HW = 685.0
REAR_HW = 690.0

def ztop(x):
    return float(np.interp(x, TOPP[:, 0], TOPP[:, 1]))

def wmax(x):
    w = 800.0
    if x < 220:
        w -= 80 * (1 - x / 220) ** 2
    if x > 3450:
        w -= 60 * ((x - 3450) / (LEN - 3450)) ** 2
    return w

def ygh(z, wbelt=785.0):
    return wbelt - (wbelt - WROOF) * max(0.0, z - ZBELT) / (ROOFZ - ZBELT)

def section(x):
    """meia secao transversal (y>=0) na estacao x -> array (y,z)"""
    zt = ztop(x)
    wm = wmax(x)
    wbot, wbelt = wm - 75, wm - 15
    zsh = min(ZBELT, zt - 70)

    def ylow(z):
        s = (z - ZB) / 260
        if s <= 1:
            return wm - 75 * (1 - s) ** 2
        return wm + (wbelt - wm) * (z - (ZB + 260)) / (ZBELT - (ZB + 260))

    side = np.array([(ylow(z), z) for z in np.linspace(ZB, zsh, 60)])
    zK = zt - CROWN
    K = np.array([ygh(zK, wbelt), zK])
    gh = np.array([side[-1], K])
    top = np.array([(y, zt - CROWN * (y / K[0]) ** 2) for y in np.linspace(K[0], 0, 30)])
    floor = np.array([(0.0, ZB), (wbot, ZB)])
    d1 = 30.0
    c1 = bez(point_at(floor, cumlen(floor)[-1] - d1), floor[-1], point_at(side, d1), 12)
    d2 = min(60.0, 0.45 * cumlen(gh)[-1], 0.45 * cumlen(top)[-1])
    c2 = bez(point_at(gh, cumlen(gh)[-1] - d2), K, point_at(top, d2), 12)
    segs = [trim(floor, 0, d1), c1, trim(side, d1, 0), trim(gh, 0, d2), c2, trim(top, d2, 0)]
    out = resample(segs[0], NSEG[0])
    for sg, n in zip(segs[1:], NSEG[1:]):
        out = np.vstack([out, resample(sg, n)[1:]])
    return out

def _section_cached(x):
    k = round(x, 1)
    if k not in _sec:
        _sec[k] = section(x)
    return _sec[k]

def y_surf(x, z):
    P = _section_cached(x)[I_SIDE0:I_SIDE1 + 1]
    return float(np.interp(z, P[:, 1], P[:, 0]))

def z_surf_top(x, y):
    P = _section_cached(x)[I_TOP0:][::-1]      # y crescente
    return float(np.interp(y, P[:, 0], P[:, 1]))

def build_body_half():
    xs = np.linspace(0, LEN, 370)
    secs = [section(x) for x in xs]
    N, M = len(secs[0]), len(xs)
    verts = [(x * S, y * S, z * S) for x, sec in zip(xs, secs) for (y, z) in sec]
    idx = lambda i, j: i * N + j
    faces = [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1))
             for i in range(M - 1) for j in range(N - 1)]
    faces.append(tuple(idx(0, j) for j in range(N)))
    faces.append(tuple(idx(M - 1, j) for j in reversed(range(N))))
    faces.append(tuple([idx(i, 0) for i in range(M)] + [idx(i, N - 1) for i in reversed(range(M))]))
    body = new_obj("carroceria_E", verts, faces)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(body.data)
    bm.free()

    rot_y = Matrix.Rotation(math.radians(-90), 4, "X")   # eixo z do cilindro -> +y

    for ax in (AX_F, AX_R):
        c = xform(cyl(TIRE_R + 1.3, 18.0, 40), rot_y)
        xform(c, Matrix.Translation((ax * S, 0, TIRE_R)))
        boolean(body, c)
        # eixo passante: atravessa a metade inteira (gira livre)
        h = xform(cyl((AXLE_D + AXLE_BODY_EXTRA) / 2, -1, 18.5, 32), rot_y)
        xform(h, Matrix.Translation((ax * S, 0, TIRE_R)))
        boolean(body, h)

    for (px, pz) in BODY_PINS:
        h = xform(cyl((PIN_D + HOLE_EXTRA) / 2, -1, 4.5, 32), rot_y)
        xform(h, Matrix.Translation((px * S, 0, pz * S)))
        boolean(body, h)

    L = LEN * S
    boolean(body, box(-1, 0.8, -FRONT_HW * S, FRONT_HW * S, FRONT_Z[0] * S, FRONT_Z[1] * S))       # frente
    boolean(body, box(-1, 0.5, -30, 30, FBUMP_Z[0] * S, FBUMP_Z[1] * S))       # para-choque d.
    boolean(body, box(L - 0.8, L + 1, -REAR_HW * S, REAR_HW * S, REAR_Z[0] * S, REAR_Z[1] * S))  # painel traseiro
    boolean(body, box(L - 0.5, L + 1, -30, 30, RBUMP_Z[0] * S, RBUMP_Z[1] * S))  # para-choque t.

    for g in side_grooves():
        boolean(body, groove_side(g))
    for g in top_grooves():
        boolean(body, groove_top(g))
    for gp in glass_defs():
        boolean(body, frame_prism(gp["o"], gp["U"], gp["V"], gp["N"], gp["poly"], -POCKET, 4.0))
    return body

def side_grooves():
    door_f = ws_x(950) + 50
    return [
        ((door_f, 300), (door_f, 950)),                     # porta: frente
        ((door_f, 950), (ws_x(1300) + 50, 1300)),           # porta: coluna A
        ((ws_x(1300) + 50, 1300), (2600, 1300)),            # porta: topo
        ((2600, 1300), (2600, 300)),                        # porta: traseira (coluna B)
        ((AX_F * 1 + 345, 300), (AX_R - 345, 300)),         # soleira (friso cromado)
        ((40, 800), (LEN - 40, 800)),                       # friso lateral (altura da macaneta)
        ((2390, 855), (2520, 855)),                         # macaneta
    ]

def top_grooves():
    return [((40, 600), (1245, 600)),                       # capo: lateral
            ((1245, -10), (1245, 600))]                     # capo: junto ao para-brisa

def groove_side(seg):
    w, d = GROOVE_W / S, GROOVE_D / S
    return ribbon(seg, w, lambda q: (q[0], y_surf(q[0], q[1]) - d, q[1]), np.array([0, 150.0, 0]), S)

def groove_top(seg):
    w, d = GROOVE_W / S, GROOVE_D / S
    return ribbon(seg, w, lambda q: (q[0], q[1], z_surf_top(q[0], abs(q[1])) - d), np.array([0, 0, 150.0]), S)

def glass_defs():
    out = []
    # para-brisa
    A = np.array([WS_A[0], 0, WS_A[1]]); d = np.array([WS_B[0] - WS_A[0], 0, WS_B[1] - WS_A[1]])
    U = d / np.linalg.norm(d); N = np.cross(U, [0, 1, 0])
    hw = lambda u: ygh(A[2] + u * U[2] - CROWN) - 60 - 50
    u0, u1 = 75, np.linalg.norm(d) - 105
    poly = [(u0, -hw(u0)), (u1, -hw(u1)), (u1, hw(u1)), (u0, hw(u0))]
    out.append(dict(name="parabrisa", o=A * S, U=U, V=(0, 1, 0), N=N, poly=[(u * S, v * S) for u, v in poly]))
    # vidro traseiro (so a parte de cima da tampa; embaixo e chapa vermelha)
    C = np.array([HATCH_A[0], 0, HATCH_A[1]]); d = np.array([HATCH_B[0] - HATCH_A[0], 0, HATCH_B[1] - HATCH_A[1]])
    U = d / np.linalg.norm(d); N = np.cross(U, [0, 1, 0])
    hw2 = lambda u: ygh(C[2] + u * U[2] - CROWN) - 60 - 60
    u0, u1 = 140, (HATCH_A[1] - REAR_GLASS_BOTTOM_Z) / -U[2]
    poly = [(u0, hw2(u0)), (u1, hw2(u1)), (u1, -hw2(u1)), (u0, -hw2(u0))]
    out.append(dict(name="vidro_tras", o=C * S, U=U, V=(0, 1, 0), N=N, poly=[(u * S, v * S) for u, v in poly]))
    # laterais (plano inclinado)
    O = np.array([0, 785.0, ZBELT])
    W = np.array([0, -185.0, 410.0]); W /= np.linalg.norm(W)
    Nn = np.array([0, 410.0, 185.0]); Nn /= np.linalg.norm(Nn)
    kz = 1 / W[2]
    door = [(ws_x(955) + 90, 955), (2560, 955), (2560, 1265), (ws_x(1265) + 90, 1265)]
    quarter = [(2650, 955), (hatch_x(955) - 135, 955), (hatch_x(1265) - 110, 1265), (2650, 1265)]
    for nm, pl in (("vidro_porta", door), ("vidro_traseiro_lateral", quarter)):
        out.append(dict(name=nm, o=O * S, U=(1, 0, 0), V=W, N=Nn,
                        poly=[(x * S, (z - ZBELT) * kz * S) for x, z in pl]))
    return out

def make_wheel(axle_x, side, track):
    """roda face-up: face interna em z=0, externa (com detalhe) em cima"""
    W, R = TIRE_W, TIRE_R
    tire = revolve([(R - 0.5, 0), (R, 0.5), (R, W - 0.5), (R - 0.5, W)], 96, "pneu")
    for zc in (W * 0.36, W * 0.64):                       # sulcos da banda de rodagem
        ring = boolean(cyl(R + 1, zc - 0.2, zc + 0.2, 96), cyl(R - 0.25, zc - 1, zc + 1, 96))
        boolean(tire, ring)
    RR, t0 = 5.4, W - 0.8                                  # aro de aco
    boolean(tire, cyl(RR, t0, W + 1, 96))
    rim = cyl(RR, t0, W, 96, "roda_aco")
    boolean(rim, cyl(4.7, W - 0.35, W + 1, 96))            # prato rebaixado (sobra a borda do aro)
    boss = cyl(1.9, t0, W - 0.1, 48)
    boolean(rim, boss, "UNION")                            # cubo central
    for k in range(8):                                     # 8 fendas de ventilacao
        a = 2 * math.pi * k / 8 + math.pi / 8
        sl = box(-0.5, 0.5, -0.35, 0.35, t0 - 0.01, W + 1)
        xform(sl, Matrix.Translation((3.35 * math.cos(a), 3.35 * math.sin(a), 0)) @ Matrix.Rotation(a, 4, "Z"))
        boolean(rim, sl)
    boolean(rim, cyl(0.6, t0 - 0.01, W + 1, 24))           # centro escuro
    boolean(tire, cyl((AXLE_D + AXLE_WHEEL_EXTRA) / 2, -1, 3.2, 32))   # furo do eixo (pressao)
    y_in = track / 2 * S - W / 2
    if side > 0:
        M = Matrix.Translation((axle_x * S, y_in, TIRE_R)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    else:
        M = Matrix.Translation((axle_x * S, -y_in, TIRE_R)) @ Matrix.Rotation(math.radians(90), 4, "X")
    return Part("roda", [(tire, BLACK), (rim, SILVER)], asm=M, explode=(0, 14 * side, 0))

def make_front():
    """frente (grade + farois) face-up: fundo no rebaixo, detalhe em cima"""
    x0, x1 = -0.4, 0.8
    hw = FRONT_HW * S - PLATE_CLR
    z0, z1 = FRONT_Z[0] * S + PLATE_CLR, FRONT_Z[1] * S - PLATE_CLR
    plate = box(x0, x1, -hw, hw, z0, z1, "frente")
    objs = [(plate, BLACK)]
    zc = (z0 + z1) / 2
    lw, lh = 290 * S, 190 * S
    for sy in (-1, 1):
        cy = sy * (hw - 0.6 - lw / 2)
        bez_ = box(x0 - 0.4, x0, cy - lw / 2, cy + lw / 2, zc - lh / 2, zc + lh / 2, "aro_farol")
        lens_hole = box(x0 - 1, x0 + 1, cy - lw / 2 + 0.6, cy + lw / 2 - 0.6, zc - lh / 2 + 0.6, zc + lh / 2 - 0.6)
        boolean(bez_, copy_obj(lens_hole))
        lens = box(x0 - 0.2, x0, cy - lw / 2 + 0.6, cy + lw / 2 - 0.6,
                   zc - lh / 2 + 0.6, zc + lh / 2 - 0.6, "lente_farol")
        bpy.data.objects.remove(lens_hole, do_unlink=True)
        objs += [(bez_, SILVER), (lens, WHITE)]
    gi = hw - 1.2 - lw                                     # grade entre os farois
    for k in range(6):                                     # frisos horizontais da grade
        zz = zc - lh / 2 + 0.55 + k * (lh - 1.1) / 5
        boolean(plate, box(x0 - 1, x0 + 0.3, -gi + 0.4, gi - 0.4, zz - 0.2, zz + 0.2))
    return Part("frente", objs, down=(1, 0, 0), explode=(-16, 0, 0))

def make_rear():
    """painel traseiro vermelho (cor da carroceria) com lanternas e placa, face-up"""
    L = LEN * S
    x0, x1 = L - 0.8, L + 0.4
    hw = REAR_HW * S - PLATE_CLR
    z0, z1 = REAR_Z[0] * S + PLATE_CLR, REAR_Z[1] * S - PLATE_CLR
    plate = box(x0, x1, -hw, hw, z0, z1, "painel_traseiro")
    objs = [(plate, RED)]
    lw, lh = 300 * S, 200 * S
    lz0 = 560 * S
    for sy in (-1, 1):
        cy = sy * (hw - 0.3 - lw / 2)
        ring = box(x1, x1 + 0.4, cy - lw / 2, cy + lw / 2, lz0, lz0 + lh, "moldura_lanterna")
        inner = (cy - lw / 2 + 0.5, cy + lw / 2 - 0.5, lz0 + 0.5, lz0 + lh - 0.5)
        boolean(ring, box(x1 - 1, x1 + 1, *inner))
        ztop_band = inner[3] - 0.9                         # faixa clara (re) em cima
        white = box(x1, x1 + 0.25, inner[0], inner[1], ztop_band, inner[3], "luz_re")
        redl = box(x1 - 0.01, x1 + 0.25, inner[0], inner[1], inner[2], ztop_band - 0.3, "lente_vermelha")
        sep = box(x1, x1 + 0.3, inner[0], inner[1], ztop_band - 0.3, ztop_band, "divisor")
        objs += [(ring, BLACK), (white, WHITE), (redl, RED), (sep, BLACK)]
    pw, ph = 400 * S, 130 * S                              # placa
    pz = 590 * S
    border = box(x1, x1 + 0.35, -pw / 2, pw / 2, pz, pz + ph, "moldura_placa")
    boolean(border, box(x1 - 1, x1 + 1, -pw / 2 + 0.4, pw / 2 - 0.4, pz + 0.4, pz + ph - 0.4))
    pl = box(x1, x1 + 0.2, -pw / 2 + 0.4, pw / 2 - 0.4, pz + 0.4, pz + ph - 0.4, "placa")
    objs += [(border, BLACK), (pl, WHITE)]
    # tudo o que e vermelho vira uma peca so
    reds = [o for o, c in objs if c == RED]
    merged = union_all(reds, "painel_traseiro")
    objs = [(merged, RED)] + [(o, c) for o, c in objs if c != RED]
    return Part("painel_traseiro", objs, down=(-1, 0, 0), explode=(16, 0, 0))

def make_bumper(front=True):
    """para-choque face-down: a face cromada e a primeira camada (lisa)"""
    L = LEN * S
    hw = 740 * S
    if front:
        x0, x1, down = -BUMPER_OUT, 0.5, (-1, 0, 0)
        zlo, zhi = FBUMP_Z[0] * S + PLATE_CLR, FBUMP_Z[1] * S - PLATE_CLR
        zchrome = 380 * S
        face_x = (x0 - 0.01, x0 + 0.4)
    else:
        x0, x1, down = L - 0.5, L + BUMPER_OUT, (1, 0, 0)
        zlo, zhi = RBUMP_Z[0] * S + PLATE_CLR, RBUMP_Z[1] * S - PLATE_CLR
        zchrome = zlo
        face_x = (x1 - 0.4, x1 + 0.01)
    bar = box(x0, x1, -hw, hw, zlo, zhi, "parachoque")
    objs = [(bar, BLACK)]
    clip = lambda: box(x0, x1, -30, 30, -10, 80)
    chrome = inlay(bar, box(*face_x, -hw + 2.0, hw - 2.0, zchrome, zhi + 0.01, "cromado"), clip())
    objs.append((chrome, SILVER))
    if front:
        for sy in (-1, 1):                                 # piscas (ambar no real; aqui branco)
            cy = sy * 545 * S
            objs.append((inlay(bar, box(*face_x, cy - 2.2, cy + 2.2, 312 * S, 368 * S, "pisca"), clip()), WHITE))
        pl = box(*face_x, -200 * S, 200 * S, 335 * S, 465 * S, "placa")
        boolean(chrome, copy_obj(pl))
        objs.append((inlay(bar, pl, clip()), WHITE))
    return Part("parachoque_" + ("diant" if front else "tras"), objs, down=down,
                explode=(-26 if front else 26, 0, 0))

def make_glass(gp, mirror=False):
    poly = inset_convex(gp["poly"], PLATE_CLR)
    ob = frame_prism(gp["o"], gp["U"], gp["V"], gp["N"], poly, -POCKET, 0.0, gp["name"])
    N = Vector(gp["N"])
    if mirror:
        mirror_y(ob)
        N = Vector((N.x, -N.y, N.z))
    return Part(gp["name"], [(ob, BLACK)], down=-N, explode=tuple(N * 12))

def build_parts():
    body = build_body_half()
    body_r = mirror_y(copy_obj(body, "carroceria_D"))
    parts = [Part("carroceria_E", [(body, RED)], down=(0, -1, 0), explode=(0, 7, 0)),
             Part("carroceria_D", [(body_r, RED)], down=(0, 1, 0), explode=(0, -7, 0))]
    for ax, tr in ((AX_F, TRACK_F), (AX_R, TRACK_R)):
        for side in (1, -1):
            p = make_wheel(ax, side, tr)
            p.name = f"roda_{'diant' if ax == AX_F else 'tras'}_{'E' if side > 0 else 'D'}"
            parts.append(p)
        y_in = tr / 2 * S - TIRE_W / 2
        parts.append(make_pin(2 * (y_in + 3.0), f"eixo_{'diant' if ax == AX_F else 'tras'}",
                              (ax * S, TIRE_R), AXLE_D, explode=(0, 0, -10)))
    for gp in glass_defs():
        if gp["name"] in ("parabrisa", "vidro_tras"):
            parts.append(make_glass(gp))
        else:
            parts.append(make_glass(gp))
            parts.append(make_glass(gp, mirror=True))
    parts += [make_front(), make_rear(), make_bumper(True), make_bumper(False),
              make_nameplate(NAME_TEXT), make_foot()]
    for i, (px, pz) in enumerate(BODY_PINS):
        parts.append(make_pin(8.6, f"pino_carroceria{i+1}", (px * S, pz * S), explode=(0, 0, 10)))
    return parts

