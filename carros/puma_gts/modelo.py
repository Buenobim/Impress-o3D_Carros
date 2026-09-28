# -*- coding: utf-8 -*-
"""
Puma GTS conversivel (1973-1981, fibra de vidro, mecanica VW 1600 a ar, motor traseiro) - 1:32

ARQUITETURA (diferente do Gol): carroceria INTEIRICA impressa EM PE.
Num conversivel o cockpit e aberto; com duas metades deitadas ele viraria balanco.
Em pe, o cockpit e um bolsao aberto para cima (paredes verticais) e a carroceria sai sem suporte.
Pecas encaixadas: bancos, para-brisa (so a moldura), capota recolhida, grade do motor,
farois, lanternas, placas, laminas de para-choque, rodas e eixos passantes.

Fontes: ver referencias.csv desta pasta.
"""
import os
import numpy as np
from mathutils import Vector, Matrix
from kitcard.nucleo import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
NAME_TEXT = "PUMA GTS"
KEEP_ORIENT = ("carroceria",)

# =============================================================================
# REFERENCIA DO VEICULO (mm reais)  - Wikipedia: 4000 x 1665 x 1200, entre-eixos 2150
# =============================================================================
S = 1 / 32
REAL_LEN, REAL_W, REAL_H, WHEELBASE = 4000.0, 1665.0, 1200.0, 2150.0
LEN = 3925.0                          # carroceria; laminas de para-choque completam ~4000
AX_F = 962.0                          # balanco dianteiro ~1000 mm (estimado da foto lateral)
AX_R = AX_F + WHEELBASE               # motor traseiro: balanco traseiro ~850 mm
TRACK_F, TRACK_R = 1340.0, 1380.0     # ESTIMADAS (plataforma VW; sem fonte primaria)
ZB = 180.0                            # fundo da carroceria
TIRE_D, TIRE_W_REAL = 14 * 25.4 + 2 * 0.70 * 175, 175.0   # 175/70 R14 (aro 14 confirmado; medida estimada)
TIRE_R, TIRE_W = TIRE_D / 2 * S, TIRE_W_REAL * S
COCKPIT_X = (1440.0, 2960.0)
COCKPIT_FLOOR = 330.0
WS_BASE_X, WS_BASE_Z, WS_TOP_X, WS_TOP_Z = 1380.0, 815.0, 1800.0, 1125.0
LEN_MM, HEIGHT_MM = LEN * S, 950 * S

# perfis longitudinais: centro (capo/tampa), crista dos para-lamas, meia-largura
ZC = [(0, 500), (100, 575), (500, 680), (962, 745), (1330, 790), (1480, 775), (2950, 775),
      (3250, 800), (3600, 770), (3860, 660), (LEN, 630)]
ZF = [(0, 540), (160, 650), (600, 810), (962, 865), (1330, 815), (1560, 770), (2750, 770),
      (AX_R, 875), (3450, 835), (3800, 700), (LEN, 650)]      # para-lamas acima da linha da porta
WP = [(520, 820), (962, 832), (1500, 795), (2700, 795), (AX_R, 832), (3500, 815), (LEN, 700)]

def _interp(prof, x, radii=None):
    return float(np.interp(x, [p[0] for p in prof], [p[1] for p in prof]))

_WPR = round_poly(WP, [0, 350, 350, 350, 350, 300, 0], 16)

def zc(x): return _interp(ZC, x)

def zb(x):
    """fundo: plano no meio; chanfro de 45 graus no bico e na traseira (imprime sem suporte em pe)"""
    return ZB + max(0.0, 110.0 - x) + max(0.0, x - (LEN - 90.0))
def zf(x): return _interp(ZF, x)

def wmax(x):
    if x < 520:
        return 380 + 440 * math.sqrt(max(0.0, 1 - (1 - x / 520) ** 2))
    return float(np.interp(x, _WPR[:, 0], _WPR[:, 1]))

NS = (4, 5, 12, 6, 10, 14)   # piso, canto, recolhimento, lateral, rolagem, topo

def half_section(x):
    """meia secao (y>=0) de baixo (y=0,ZB) ate o topo no centro (y=0, zc) -> array (y,z)"""
    w = wmax(x)
    ZB = zb(x)
    yf = max(w - 170.0, 0.45 * w)
    zcx, zfx = zc(x), zf(x)
    zst = zfx - 0.30 * (zfx - ZB)          # topo da lateral vertical
    zw = zst - 0.25 * (zst - ZB)           # nivel da largura maxima
    tuck = 70.0
    wb = w - tuck
    floor = np.array([(0.0, ZB), (wb - 25, ZB)])
    pt = np.array([w - tuck * ((zw - (ZB + 25)) / (zw - ZB)) ** 2, ZB + 25])
    corner = bez(np.array([wb - 25, ZB]), np.array([wb, ZB]), pt, 8)
    zz = np.linspace(ZB + 25, zw, 20)
    tuckc = np.array([(w - tuck * ((zw - z) / (zw - ZB)) ** 2, z) for z in zz])
    side = np.array([(w, zw), (w, zst)])
    tt = np.linspace(0, math.pi / 2, 20)
    roll = np.array([(yf + (w - yf) * math.cos(t), zst + (zfx - zst) * math.sin(t)) for t in tt])
    yy = np.linspace(yf, 0, 30)
    top = np.array([(y, zcx + (zfx - zcx) * (1 - math.cos(math.pi * y / yf)) / 2) for y in yy])
    segs = [floor, corner, tuckc, side, roll, top]
    out = resample(segs[0], NS[0])
    for sg, n in zip(segs[1:], NS[1:]):
        out = np.vstack([out, resample(sg, n)[1:]])
    return out

I_SIDE = (NS[0] - 1, sum(n - 1 for n in NS[:5]))       # canto..rolagem (z crescente)
I_TOP = sum(n - 1 for n in NS[:5])                      # inicio do topo

_hs = {}
def _half(x):
    k = round(x, 1)
    if k not in _hs:
        _hs[k] = half_section(x)
    return _hs[k]

def y_side(x, z):
    P = _half(x)[I_SIDE[0]:I_SIDE[1] + 1]
    return float(np.interp(z, P[:, 1], P[:, 0]))

def z_top(x, y):
    P = _half(x)[sum(n - 1 for n in NS[:4]):][::-1]   # rolagem+topo, y crescente
    return float(np.interp(abs(y), P[:, 0], P[:, 1]))

def full_loop(x):
    h = _half(x)
    mirror = [(-y, z) for (y, z) in h[1:-1][::-1]]
    return np.array([tuple(p) for p in h] + mirror)

# =============================================================================
# CARROCERIA INTEIRICA
# =============================================================================
def cockpit_outline():
    xs = np.linspace(COCKPIT_X[0], COCKPIT_X[1], 40)
    r = 150.0
    pts = []
    for x in xs:
        hw = wmax(x) - 75.0
        # cantos arredondados
        dx = min(x - COCKPIT_X[0], COCKPIT_X[1] - x)
        if dx < r:
            hw -= r - math.sqrt(max(0.0, r * r - (r - dx) ** 2))
        pts.append((x, hw))
    right = [(x, -h) for x, h in pts]
    left = [(x, h) for x, h in pts[::-1]]
    return [(x * S, y * S) for x, y in right + left]

def build_body():
    xs = np.linspace(0, LEN, 330)
    body = loft_closed("carroceria", xs, [full_loop(x) for x in xs], S)

    # cockpit aberto (bolsao vertical)
    boolean(body, prism(cockpit_outline(), COCKPIT_FLOOR * S, 60))

    # caixas de roda (dos dois lados) + eixo passante com topo em 45 graus
    rot = Matrix.Rotation(math.radians(-90), 4, "X")
    for ax, tr in ((AX_F, TRACK_F), (AX_R, TRACK_R)):
        y_in = tr / 2 * S - TIRE_W / 2 - 0.7
        for sgn in (1, -1):
            c = xform(cyl(TIRE_R + 1.2, y_in, 60, 72), rot)
            if sgn < 0:
                xform(c, Matrix.Scale(-1, 4, (0, 1, 0)))
                c.data.flip_normals()
            xform(c, Matrix.Translation((ax * S, 0, TIRE_R)))
            boolean(body, c)
        boolean(body, teardrop_hole_y(ax * S, TIRE_R, (AXLE_D + AXLE_BODY_EXTRA) / 2, -40, 40))

    # vincos: portas, capo (porta-malas), tampa do motor, macanetas
    for seg in side_grooves():
        for sgn in (1, -1):
            g = groove_side(seg)
            if sgn < 0:
                mirror_y(g)
            boolean(body, g)
    for seg in top_grooves():
        boolean(body, groove_top(seg))

    # rebaixos para as pecas encaixadas
    for cut in insert_cutters():
        boolean(body, cut)
    return body

def side_grooves():
    return [((1470, 270), (1470, 700)), ((2760, 270), (2760, 700)),   # para abaixo da borda do cockpit (~740)
            ((1470, 270), (2760, 270)), ((2600, 690), (2700, 690))]

def top_grooves():
    return [((140, -430), (140, 430)), ((140, 430), (1250, 430)), ((140, -430), (1250, -430)),
            ((1250, -430), (1250, 430)),                                    # capo dianteiro
            ((3290, -480), (3290, 480)), ((3290, 480), (3880, 480)),
            ((3290, -480), (3880, -480)), ((3880, -480), (3880, 480))]      # tampa do motor

def groove_side(seg):
    w, d = GROOVE_W / S, GROOVE_D / S
    return ribbon(seg, w, lambda q: (q[0], y_side(q[0], q[1]) - d, q[1]), np.array([0, 150.0, 0]), S)

def groove_top(seg):
    w, d = GROOVE_W / S, GROOVE_D / S
    return ribbon(seg, w, lambda q: (q[0], q[1], z_top(q[0], q[1]) - d), np.array([0, 0, 150.0]), S)

# ---- posicoes das pecas encaixadas (mm reais) ----
HEAD = dict(x=210.0, y=545.0, r=3.3)            # farol (mm impresso no raio)
HEAD_N = np.array([-0.80, 0.25, 0.55])
TAIL = dict(z0=470.0, z1=570.0, y0=390.0, y1=650.0)
PLATE_R = dict(z0=395.0, z1=525.0, hw=200.0)
PLATE_F = dict(z0=345.0, z1=475.0, hw=200.0)
LOUVER = dict(x0=3330.0, x1=3530.0, hw=420.0, ztop=800.0)
TOP_BOOT = dict(x0=2960.0, x1=3280.0, hw=640.0, zb=790.0, zt=905.0)
FBUMP_Z = (350.0, 430.0)
RBUMP_Z = (350.0, 430.0)

def head_frame(sgn):
    N = HEAD_N * np.array([1, sgn, 1]); N = N / np.linalg.norm(N)
    x, y = HEAD["x"], HEAD["y"] * sgn
    c = np.array([x, y, z_top(x, y)]) * S
    U = np.cross(N, [0, 0, 1.0]); U /= np.linalg.norm(U)
    V = np.cross(N, U)
    return c, U, V, N

def insert_cutters():
    L = LEN * S
    cuts = []
    # farois
    for sgn in (1, -1):
        c, U, V, N = head_frame(sgn)
        cuts.append(frame_prism(c, U, V, N, circle(HEAD["r"], 40), -1.2, 6.0, "furo_farol"))
    # lanternas e placa traseira (face traseira plana)
    for sgn in (1, -1):
        y0, y1 = sorted((sgn * TAIL["y0"] * S, sgn * TAIL["y1"] * S))
        cuts.append(box(L - 0.8, L + 1, y0, y1, TAIL["z0"] * S, TAIL["z1"] * S))
    cuts.append(box(L - 0.8, L + 1, -PLATE_R["hw"] * S, PLATE_R["hw"] * S, PLATE_R["z0"] * S, PLATE_R["z1"] * S))
    # placa dianteira (frente plana do bico)
    cuts.append(box(-1, 0.8, -PLATE_F["hw"] * S, PLATE_F["hw"] * S, PLATE_F["z0"] * S, PLATE_F["z1"] * S))
    # grade do motor
    cuts.append(box(LOUVER["x0"] * S, LOUVER["x1"] * S, -LOUVER["hw"] * S, LOUVER["hw"] * S,
                    LOUVER["ztop"] * S - POCKET, 60))
    # assento da capota recolhida
    cuts.append(box(TOP_BOOT["x0"] * S, TOP_BOOT["x1"] * S, -TOP_BOOT["hw"] * S, TOP_BOOT["hw"] * S,
                    TOP_BOOT["zb"] * S, 60))
    # encaixes das pernas do para-brisa
    for leg in windshield_legs(clearance=PLATE_CLR):
        cuts.append(leg)
    # rebaixos das laminas de para-choque
    for front in (True, False):
        for sgn in (1, -1):
            cuts.append(bumper_band(front, sgn, d_in=-0.5 - PLATE_CLR, d_out=2.0, zpad=PLATE_CLR))
    return cuts

# ---- para-brisa (so moldura, preta) ----
def ws_frame():
    A = np.array([WS_BASE_X, 0, WS_BASE_Z]); B = np.array([WS_TOP_X, 0, WS_TOP_Z])
    U = (B - A) / np.linalg.norm(B - A)
    N = np.cross(U, [0, 1.0, 0])
    return A * S, U, np.array([0, 1.0, 0]), N, np.linalg.norm(B - A) * S

def windshield_legs(clearance=0.0):
    o, U, V, N, Lw = ws_frame()
    legs = []
    for sgn in (1, -1):
        v0 = sgn * (600 * S - 0.9)
        poly = [(-3.2, v0 - 0.8 - clearance), (0.2, v0 - 0.8 - clearance),
                (0.2, v0 + 0.8 + clearance), (-3.2, v0 + 0.8 + clearance)]
        legs.append(frame_prism(o, U, V, N, poly, -0.6 - clearance, 0.6 + clearance, "perna_parabrisa"))
    return legs

def make_windshield():
    o, U, V, N, Lw = ws_frame()
    hb, ht = 600 * S, 560 * S
    outer = [(0, -hb), (Lw, -ht), (Lw, ht), (0, hb)]
    inner = inset_convex(outer, 1.3)
    inner = [(max(u, 1.6), v) for u, v in inner]
    frame = frame_prism(o, U, V, N, outer, -0.6, 0.6, "moldura_parabrisa")
    boolean(frame, frame_prism(o, U, V, N, inner, -2, 2))
    for leg in windshield_legs():
        boolean(frame, leg, "UNION")
    return Part("parabrisa", [(frame, BLACK)], down=-Vector(N), explode=tuple(Vector(N) * 12))

# ---- laminas de para-choque (prata, impressas em pe) ----
def bumper_path(front, sgn):
    z = (FBUMP_Z[0] + FBUMP_Z[1]) / 2
    if front:
        pts = [(0.0, 240.0), (0.0, y_side(0.0, z))]
        pts += [(x, y_side(x, z)) for x in np.linspace(15, 520, 16)]
    else:
        pts = [(LEN, 260.0), (LEN, y_side(LEN, z))]
        pts += [(x, y_side(x, z)) for x in np.linspace(LEN - 15, LEN - 380, 12)]
    pts = np.array(pts)
    if sgn < 0:
        pts[:, 1] *= -1
    # sentido de percurso com o lado de FORA a esquerda
    need_flip = (front and sgn < 0) or ((not front) and sgn > 0)
    return pts[::-1] if need_flip else pts

def bumper_band(front, sgn, d_in=-0.4, d_out=0.9, zpad=0.0):
    zr = FBUMP_Z if front else RBUMP_Z
    path = bumper_path(front, sgn) * S
    return band_prism(path, d_in, d_out, zr[0] * S - zpad, zr[1] * S + zpad, "lamina")

def make_bumper(front, sgn):
    band = bumper_band(front, sgn)
    nm = f"parachoque_{'diant' if front else 'tras'}_{'E' if sgn > 0 else 'D'}"
    ex = (-14 if front else 14, 6 * sgn, 0)
    return Part(nm, [(band, SILVER)], down=(0, 0, -1), explode=ex)

# ---- bancos + tunel (preto, em pe) ----
SEAT_Y = (90.0, 570.0)
BACK_X = (2610.0, 2730.0)        # encosto: 120 mm reais = 3,75 mm (impresso DEITADO)
SOCKET_X = (2560.0, 2780.0)

def make_seats():
    """base dos bancos (baixa, em pe): assentos + tunel + soquetes dos encostos.
    Os encostos sao pecas separadas impressas deitadas: pecas altas de outra cor
    multiplicariam as trocas de cor (uma por camada)."""
    fz = COCKPIT_FLOOR * S
    base = prism(inset_convex_poly(cockpit_outline(), 0.4), fz, fz + 0.8, "base_bancos")
    parts = [base]
    top = fz + 0.8
    for sgn in (1, -1):
        y0, y1 = sorted((sgn * SEAT_Y[0] * S, sgn * SEAT_Y[1] * S))
        parts.append(box(2150 * S, SOCKET_X[0] * S, y0, y1, top - 0.01, 440 * S, "assento"))
        sock = box(SOCKET_X[0] * S, SOCKET_X[1] * S, y0, y1, top - 0.01, 440 * S, "soquete")
        boolean(sock, box(BACK_X[0] * S - PLATE_CLR, BACK_X[1] * S + PLATE_CLR,
                          y0 + 0.8 - PLATE_CLR, y1 - 0.8 + PLATE_CLR, top, 20))
        parts.append(sock)
    parts.append(box(1700 * S, 2560 * S, -60 * S, 60 * S, top - 0.01, 430 * S, "tunel"))
    seats = union_all(parts, "bancos")
    return Part("bancos", [(seats, BLACK)], down=(0, 0, -1), explode=(0, 0, 22))

def make_seatback(sgn):
    fz = COCKPIT_FLOOR * S + 0.8
    y0, y1 = sorted((sgn * SEAT_Y[0] * S, sgn * SEAT_Y[1] * S))
    y0, y1 = y0 + 0.8, y1 - 0.8
    zt = 950 * S
    r = 2.0
    prof = [(y0, fz), (y1, fz)]                                   # contorno em y-z com topo arredondado
    prof += [(y1 - r + r * math.cos(a), zt - r + r * math.sin(a)) for a in np.linspace(0, math.pi / 2, 6)]
    prof += [(y0 + r + r * math.cos(a), zt - r + r * math.sin(a)) for a in np.linspace(math.pi / 2, math.pi, 6)]
    ob = prism(prof, BACK_X[0] * S, BACK_X[1] * S, "encosto")    # (y,z) extrudado em "z" -> girar
    xform(ob, Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(ob.data); bm.free()
    return Part(f"encosto_{'E' if sgn > 0 else 'D'}", [(ob, BLACK)], down=(1, 0, 0), explode=(6, 0, 26))

def inset_convex_poly(poly, d):
    """encolhe um contorno quase convexo (cockpit) deslocando pelo centroide"""
    P = np.array(poly)
    c = P.mean(0)
    out = []
    for p in P:
        v = p - c
        n = np.linalg.norm(v)
        out.append(tuple(p - v / n * d))
    return out

# ---- capota recolhida (preta) ----
def make_soft_top():
    t = TOP_BOOT
    xs = np.linspace(t["x0"], t["x1"], 24)
    prof = [(x * S, (t["zb"] + (t["zt"] - t["zb"]) * math.sin(math.pi * (x - t["x0"]) / (t["x1"] - t["x0"])) ** 0.7) * S)
            for x in xs]
    poly = [(t["x0"] * S + PLATE_CLR, t["zb"] * S)] + [(x, z) for x, z in prof[1:-1]] + [(t["x1"] * S - PLATE_CLR, t["zb"] * S)]
    ob = prism(poly, -t["hw"] * S + PLATE_CLR, t["hw"] * S - PLATE_CLR, "capota")
    xform(ob, Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(ob.data); bm.free()
    return Part("capota_recolhida", [(ob, BLACK)], down=(0, 0, -1), explode=(0, 0, 18))

# ---- grade de ventilacao do motor (preta, face-up) ----
def make_louver():
    l = LOUVER
    x0, x1 = l["x0"] * S + PLATE_CLR, l["x1"] * S - PLATE_CLR
    hw = l["hw"] * S - PLATE_CLR
    z1 = l["ztop"] * S
    ob = box(x0, x1, -hw, hw, z1 - POCKET, z1 + 0.2, "grade_motor")
    for k in range(7):
        xx = x0 + 0.7 + k * (x1 - x0 - 1.4) / 6
        boolean(ob, box(xx - 0.2, xx + 0.2, -hw + 0.6, hw - 0.6, z1 - 0.2, z1 + 1))
    return Part("grade_motor", [(ob, BLACK)], down=(0, 0, -1), explode=(0, 0, 16))

# ---- farois (prata + lente branca, face-up) ----
def make_headlight(sgn):
    c, U, V, N = head_frame(sgn)
    r = HEAD["r"] - PLATE_CLR
    ring = frame_prism(c, U, V, N, circle(r, 40), -1.2, 0.0, "farol")
    lens = frame_prism(c, U, V, N, circle(r - 1.0, 40), -0.4, 0.0, "lente")
    boolean(ring, frame_prism(c, U, V, N, circle(r - 1.0, 40), -0.4, 1.0))   # cortador passa da face (sem coplanar)
    return Part(f"farol_{'E' if sgn > 0 else 'D'}", [(ring, SILVER), (lens, WHITE)], down=-Vector(N),
                explode=tuple(Vector(N) * 10))

# ---- lanternas (moldura preta + lente vermelha, face-up) ----
def make_taillight(sgn):
    L = LEN * S
    y0, y1 = sorted((sgn * TAIL["y0"] * S, sgn * TAIL["y1"] * S))
    y0, y1 = y0 + PLATE_CLR, y1 - PLATE_CLR
    z0, z1 = TAIL["z0"] * S + PLATE_CLR, TAIL["z1"] * S - PLATE_CLR
    frame = box(L - 0.8, L + 0.3, y0, y1, z0, z1, "lanterna")
    lens = box(L - 0.8, L + 0.3, y0 + 0.5, y1 - 0.5, z0 + 0.5, z1 - 0.5, "lente_vermelha")
    boolean(frame, copy_obj(lens))
    return Part(f"lanterna_{'E' if sgn > 0 else 'D'}", [(frame, BLACK), (lens, RED)], down=(-1, 0, 0),
                explode=(12, 0, 0))

# ---- placas (branca com moldura preta, face-up) ----
def make_plate(front):
    L = LEN * S
    p = PLATE_F if front else PLATE_R
    hw = p["hw"] * S - PLATE_CLR
    z0, z1 = p["z0"] * S + PLATE_CLR, p["z1"] * S - PLATE_CLR
    if front:
        xa, xb, down, ex = -0.3, 0.8, (1, 0, 0), (-12, 0, 0)
    else:
        xa, xb, down, ex = L - 0.8, L + 0.3, (-1, 0, 0), (12, 0, 0)
    border = box(xa, xb, -hw, hw, z0, z1, "moldura_placa")
    white = box(xa, xb, -hw + 0.4, hw - 0.4, z0 + 0.4, z1 - 0.4, "placa")
    boolean(border, copy_obj(white))
    return Part(f"placa_{'diant' if front else 'tras'}", [(border, BLACK), (white, WHITE)], down=down, explode=ex)

# ---- rodas de liga leve aro 14 (6 janelas) ----
def make_wheel(axle_x, side, track):
    W, R = TIRE_W, TIRE_R
    tire = revolve([(R - 0.6, 0), (R, 0.6), (R, W - 0.6), (R - 0.6, W)], 96, "pneu")
    for zc_ in (W * 0.33, W * 0.67):
        boolean(tire, boolean(cyl(R + 1, zc_ - 0.2, zc_ + 0.2, 96), cyl(R - 0.25, zc_ - 1, zc_ + 1, 96)))
    RR, t0 = 5.9, W - 0.8
    boolean(tire, cyl(RR, t0, W + 1, 96))
    rim = cyl(RR, t0, W, 96, "roda_liga")
    boolean(rim, cyl(5.2, W - 0.3, W + 1, 96))                  # borda do aro em destaque
    boolean(rim, cyl(2.1, t0 + 0.2, W - 0.15, 48), "UNION")     # cubo
    for k in range(6):                                          # 6 janelas
        a = 2 * math.pi * k / 6
        win = prism([(2.7, -0.7), (4.6, -1.15), (4.6, 1.15), (2.7, 0.7)], t0 - 0.01, W + 1)
        xform(win, Matrix.Rotation(a, 4, "Z"))
        boolean(rim, win)
    boolean(rim, cyl(0.7, t0 - 0.01, W + 1, 32, phase=0.05))
    boolean(tire, cyl((AXLE_D + AXLE_WHEEL_EXTRA) / 2, -1, 3.2, 32))
    y_in = track / 2 * S - W / 2
    if side > 0:
        M = Matrix.Translation((axle_x * S, y_in, TIRE_R)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    else:
        M = Matrix.Translation((axle_x * S, -y_in, TIRE_R)) @ Matrix.Rotation(math.radians(90), 4, "X")
    return Part("roda", [(tire, BLACK), (rim, SILVER)], asm=M, explode=(0, 14 * side, 0))

# =============================================================================
def build_parts():
    parts = [Part("carroceria", [(build_body(), RED)], down=(0, 0, -1))]
    for ax, tr in ((AX_F, TRACK_F), (AX_R, TRACK_R)):
        for side in (1, -1):
            p = make_wheel(ax, side, tr)
            p.name = f"roda_{'diant' if ax == AX_F else 'tras'}_{'E' if side > 0 else 'D'}"
            parts.append(p)
        y_in = tr / 2 * S - TIRE_W / 2
        parts.append(make_pin(2 * (y_in + 3.0), f"eixo_{'diant' if ax == AX_F else 'tras'}",
                              (ax * S, TIRE_R), AXLE_D, explode=(0, 0, -10)))
    parts += [make_windshield(), make_seats(), make_seatback(1), make_seatback(-1), make_soft_top(), make_louver()]
    for sgn in (1, -1):
        parts += [make_headlight(sgn), make_taillight(sgn), make_bumper(True, sgn), make_bumper(False, sgn)]
    parts += [make_plate(True), make_plate(False), make_nameplate(NAME_TEXT, H=12.0), make_foot()]
    return parts
