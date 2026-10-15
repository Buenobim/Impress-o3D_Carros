# -*- coding: utf-8 -*-
"""
Kit Card - VW Gol 1300 L 1980 (1a geracao, "quadrado") - escala 1:32 - v2
Gera as pecas, o cartao (moldura + pontos de destaque), valida as malhas
exportadas e faz os renders (montado, ortograficas, explodida, raio-x, cartao).

Rodar (sem abrir o Blender):
  blender -b --factory-startup -P gol_kitcard.py

Referencia visual: Gol 1300 L 1980 vermelho da Garagem Volkswagen
(ver referencias/manifesto.csv). Medidas: ficha tecnica Gol L 1.3 1980.
"""
import bpy, bmesh, math, os, struct, json
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "saida")

# =============================================================================
# 1. REFERENCIA DO VEICULO (mm reais)
# =============================================================================
S = 1 / 32
REAL_LEN, REAL_W, REAL_H, WHEELBASE = 3790.0, 1601.0, 1375.0, 2358.0
TRACK_F, TRACK_R = 1350.0, 1366.0
BUMPER_OUT = 1.6                                # para-choque avanca 1,6 mm (impresso)
LEN = REAL_LEN - 2 * BUMPER_OUT / S             # carroceria sem para-choques (~3688)
AX_F = 930.0 - BUMPER_OUT / S                   # balanco dianteiro ~930 mm (motor longitudinal a frente do eixo)
AX_R = AX_F + WHEELBASE
ZB = 220.0                                      # assoalho
ZBELT = 940.0                                   # linha de cintura
ROOFZ = 1350.0                                  # referencia p/ inclinacao das laterais
WROOF = 600.0                                   # meia-largura no teto
CROWN = 8.0
TIRE_R = (13 * 25.4 / 2 + 124) * S              # 155/80 R13 -> Ø 18,1 mm
TIRE_W = 155 * S

# perfil lateral (x a partir da frente da carroceria, z do chao)
WS_A, WS_B = (1300.0, 925.0), (1850.0, 1340.0)  # base e topo do para-brisa
HATCH_A, HATCH_B = (3060.0, 1356.0), (3660.0, 880.0)  # topo e pe da tampa traseira
TOP = [(0, 760), (60, 800), WS_A, WS_B, (1990, 1372), (2600, 1378),
       HATCH_A, HATCH_B, (LEN, 858)]
TOP_R = [0, 50, 60, 90, 120, 0, 120, 30, 0]
REAR_GLASS_BOTTOM_Z = 1050.0                    # abaixo disso a tampa e chapa vermelha

# =============================================================================
# 2. FABRICACAO (mm impressos) - calibrar com teste_folgas.stl
# =============================================================================
NAME_TEXT = "GOL 1980"
PIN_D = 2.5
HOLE_EXTRA = 0.20        # pinos da carroceria (justo) - acrescimo no DIAMETRO
AXLE_D = 2.5
AXLE_BODY_EXTRA = 0.35   # eixo gira livre na carroceria - DIAMETRO
AXLE_WHEEL_EXTRA = 0.10  # roda presa no eixo (pressao) - DIAMETRO
PLATE_CLR = 0.10         # folga POR LADO de vidros/frente/traseira nos rebaixos
POCKET = 1.0             # rebaixo dos vidros = espessura do vidro
CARD_W = 172.0
CARD_X0 = 4.0            # afasta o cartao 4 mm da borda esquerda da mesa
FRAME_H = 1.6
GATE_W, GATE_H = 0.8, 0.8
GROOVE_W, GROOVE_D = 0.45, 0.30   # vincos (mm impressos)
BED = 180.0

COLORS = {
    1: ("vermelho", (0.62, 0.03, 0.03)),
    2: ("preto",    (0.04, 0.04, 0.04)),
    3: ("prata",    (0.72, 0.74, 0.78)),
    4: ("branco",   (0.95, 0.95, 0.92)),
}
RED, BLACK, SILVER, WHITE = 1, 2, 3, 4

# =============================================================================
# 3. GEOMETRIA 2D
# =============================================================================
def bez(p0, p1, p2, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2

def round_poly(pts, radii, n=12):
    pts = [np.array(p, float) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        A, B, C = pts[i - 1], pts[i], pts[i + 1]
        r = radii[i]
        if r <= 0:
            out.append(B)
            continue
        ab, bc = np.linalg.norm(A - B), np.linalg.norm(C - B)
        d = min(r, 0.45 * ab, 0.45 * bc)
        out.extend(bez(B + (A - B) / ab * d, B, B + (C - B) / bc * d, n))
    out.append(pts[-1])
    return np.array(out)

def cumlen(P):
    return np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])

def point_at(P, d):
    s = cumlen(P)
    return np.array([np.interp(d, s, P[:, 0]), np.interp(d, s, P[:, 1])])

def trim(P, d0, d1):
    s = cumlen(P)
    L = s[-1]
    mid = [P[i] for i in range(len(P)) if d0 < s[i] < L - d1]
    return np.array([point_at(P, d0)] + mid + [point_at(P, L - d1)])

def resample(P, n):
    s = cumlen(P)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], 1)

TOPP = round_poly(TOP, TOP_R)

def ztop(x):
    return float(np.interp(x, TOPP[:, 0], TOPP[:, 1]))

def wmax(x):
    w = 800.0
    if x < 220:
        w -= 80 * (1 - x / 220) ** 2
    if x > 3450:
        w -= 60 * ((x - 3450) / (LEN - 3450)) ** 2
    return w

def line_x(A, B, z):
    return A[0] + (z - A[1]) * (B[0] - A[0]) / (B[1] - A[1])

ws_x = lambda z: line_x(WS_A, WS_B, z)
hatch_x = lambda z: line_x(HATCH_A, HATCH_B, z)

def ygh(z, wbelt=785.0):
    return wbelt - (wbelt - WROOF) * max(0.0, z - ZBELT) / (ROOFZ - ZBELT)

NSEG = (4, 6, 20, 8, 6, 10)   # piso, canto inf, lateral, vidro lateral, canto sup, teto

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

I_SIDE0 = NSEG[0] - 1
I_SIDE1 = sum(n - 1 for n in NSEG[:5])
I_TOP0 = sum(n - 1 for n in NSEG[:5])

_sec = {}
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

# =============================================================================
# 4. UTILIDADES BLENDER
# =============================================================================
WORK = None
BOOL_SOLVER = "MANIFOLD"

def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)

def new_work():
    global WORK
    WORK = bpy.data.collections.new("WORK")
    bpy.context.scene.collection.children.link(WORK)
    return WORK

def _clean(me, dist=1e-5):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, dist=dist, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()

def fix_slivers(me, passes=6):
    """elimina triangulos de area zero (vertice sobre a aresta oposta) girando a aresta longa.
    A superficie nao muda: o vertice colinear ja esta sobre a aresta."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    for _ in range(passes):
        bm.faces.ensure_lookup_table()
        edges = set()
        for f in bm.faces:
            if f.calc_area() < 1e-9:
                e = max(f.edges, key=lambda e: e.calc_length())
                if len(e.link_faces) == 2:
                    edges.add(e)
        if not edges:
            break
        bmesh.ops.rotate_edges(bm, edges=list(edges), use_ccw=False)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()

def new_obj(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], faces)
    me.validate()
    _clean(me, 1e-6)
    ob = bpy.data.objects.new(name, me)
    WORK.objects.link(ob)
    return ob

def box(x0, x1, y0, y1, z0, z1, name="box"):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return new_obj(name, v, f)

def prism(poly2d, z0, z1, name="prism"):
    n = len(poly2d)
    v = [(p[0], p[1], z0) for p in poly2d] + [(p[0], p[1], z1) for p in poly2d]
    f = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return new_obj(name, v, f)

def circle(r, n=64, cx=0.0, cy=0.0, phase=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / n + phase), cy + r * math.sin(2 * math.pi * i / n + phase))
            for i in range(n)]

def cyl(r, z0, z1, n=64, name="cyl", phase=0.0):
    return prism(circle(r, n, phase=phase), z0, z1, name)

def revolve(profile, n=96, name="rev"):
    m = len(profile)
    v = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z)
         for i in range(n) for r, z in profile]
    f = []
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(m - 1):
            f.append((i * m + j, i2 * m + j, i2 * m + j + 1, i * m + j + 1))
    f.append(tuple(i * m for i in range(n))[::-1])
    f.append(tuple(i * m + m - 1 for i in range(n)))
    return new_obj(name, v, f)

def frame_prism(origin, U, V, N, poly_uv, n0, n1, name="fprism"):
    origin, U, V, N = map(Vector, (origin, U, V, N))
    pts = [origin + U * u + V * w + N * nn for nn in (n0, n1) for (u, w) in poly_uv]
    k = len(poly_uv)
    f = [tuple(range(k))[::-1], tuple(range(k, 2 * k))]
    f += [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)]
    return new_obj(name, pts, f)

def xform(ob, M):
    ob.data.transform(M)
    ob.data.update()
    return ob

def boolean(target, cutter, op="DIFFERENCE", keep=False):
    mod = target.modifiers.new("B", "BOOLEAN")
    mod.operation = op
    mod.object = cutter
    mod.solver = BOOL_SOLVER
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.remove(mod)
    _clean(me)
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    if not keep:
        bpy.data.objects.remove(cutter, do_unlink=True)
    return target

def union_all(obs, name):
    """une varios solidos (mesma cor) num so"""
    coll = bpy.data.collections.new("U_" + name)
    bpy.context.scene.collection.children.link(coll)
    base = obs[0]
    for o in obs[1:]:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    mod = base.modifiers.new("U", "BOOLEAN")
    mod.operation = "UNION"
    mod.operand_type = "COLLECTION"
    mod.collection = coll
    mod.solver = BOOL_SOLVER
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
    base.modifiers.remove(mod)
    _clean(me)
    ob = bpy.data.objects.new(name, me)
    WORK.objects.link(ob)
    for o in list(coll.objects) + [base]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(coll)
    return ob

def copy_obj(ob, name=None):
    o2 = ob.copy()
    o2.data = ob.data.copy()
    o2.name = name or ob.name + "_c"
    for c in list(o2.users_collection):
        c.objects.unlink(o2)
    WORK.objects.link(o2)
    return o2

def mirror_y(ob):
    xform(ob, Matrix.Scale(-1, 4, (0, 1, 0)))
    ob.data.flip_normals()
    return ob

def text_mesh(txt, size, height, font="ariblk.ttf"):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = txt
    fp = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", font)
    if os.path.exists(fp):
        cu.font = bpy.data.fonts.load(fp)
    cu.size = size
    cu.extrude = height / 2
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.resolution_u = 8
    tob = bpy.data.objects.new("txt", cu)
    WORK.objects.link(tob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tob.evaluated_get(dg))
    bpy.data.objects.remove(tob, do_unlink=True)
    _clean(me)
    ob = bpy.data.objects.new("texto", me)
    WORK.objects.link(ob)
    return ob

def bbox(ob, M=None):
    M = M or Matrix.Identity(4)
    co = np.array([tuple(M @ v.co) for v in ob.data.vertices])
    return co.min(0), co.max(0)

def inlay(base, detail, clip=None):
    """recorta 'detail' da base (outra cor) e limita o detalhe a 'clip'"""
    boolean(base, copy_obj(detail))
    if clip is not None:
        boolean(detail, clip, "INTERSECT")
    return detail

# =============================================================================
# 5. CARROCERIA
# =============================================================================
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

BODY_PINS = [(1250, 560), (2300, 800), (3050, 650)]
FRONT_Z = (495.0, 705.0)   # faixa vermelha entre a grade e o para-choque
FBUMP_Z = (300.0, 470.0)
REAR_Z = (540.0, 850.0)
RBUMP_Z = (330.0, 440.0)
FRONT_HW = 685.0
REAR_HW = 690.0

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

def _ribbon(pts_center, width, inner_fn, outer_off):
    """solido fino seguindo uma polilinha 2D; inner_fn(p)->(x,y,z) e outer_off (vetor)"""
    p0, p1 = np.array(pts_center[0], float), np.array(pts_center[1], float)
    t = (p1 - p0) / np.linalg.norm(p1 - p0)
    nrm = np.array([-t[1], t[0]])
    p0, p1 = p0 - t * width / 2, p1 + t * width / 2
    n = max(2, int(np.linalg.norm(p1 - p0) / 15) + 1)
    verts, faces = [], []
    for s in np.linspace(0, 1, n):
        p = p0 + (p1 - p0) * s
        a = np.array(inner_fn(p + nrm * width / 2))
        b = np.array(inner_fn(p - nrm * width / 2))
        verts += [a, b, b + outer_off, a + outer_off]
    for i in range(n - 1):
        a, b = 4 * i, 4 * (i + 1)
        for k in range(4):
            faces.append((a + k, a + (k + 1) % 4, b + (k + 1) % 4, b + k))
    faces.append((0, 1, 2, 3))
    faces.append(tuple(4 * (n - 1) + k for k in (3, 2, 1, 0)))
    return new_obj("vinco", [tuple(v * S) for v in verts], faces)

def groove_side(seg):
    w, d = GROOVE_W / S, GROOVE_D / S
    return _ribbon(seg, w, lambda q: (q[0], y_surf(q[0], q[1]) - d, q[1]), np.array([0, 150.0, 0]))

def groove_top(seg):
    w, d = GROOVE_W / S, GROOVE_D / S
    return _ribbon(seg, w, lambda q: (q[0], q[1], z_surf_top(q[0], abs(q[1])) - d), np.array([0, 0, 150.0]))

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

def inset_convex(poly, d):
    P = np.array(poly, float)
    n = len(P)
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
    sgn = 1 if area > 0 else -1
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        t = (b - a) / np.linalg.norm(b - a)
        lines.append((a + sgn * np.array([-t[1], t[0]]) * d, t))
    out = []
    for i in range(n):
        (p1, t1), (p2, t2) = lines[i - 1], lines[i]
        s = np.linalg.solve(np.array([t1, -t2]).T, p2 - p1)
        out.append(tuple(p1 + t1 * s[0]))
    return out

# =============================================================================
# 6. PECAS
# =============================================================================
class Part:
    """objs: lista (obj, cor). Geometria final fica no sistema de IMPRESSAO
    (apoiada em z=0); self.asm leva impressao -> carro montado."""
    def __init__(self, name, objs, down=None, asm=None, explode=(0, 0, 0)):
        self.name = name
        self.objs = objs
        self.asm = asm
        self.explode = Vector(explode)
        if down is not None:
            self.asm = Matrix.Identity(4)
            self.to_print(Vector(down))

    def to_print(self, down):
        R = down.normalized().rotation_difference(Vector((0, 0, -1))).to_matrix().to_4x4()
        for ob, _ in self.objs:
            xform(ob, R)
        lo, hi = self.bounds()
        T = Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))
        for ob, _ in self.objs:
            xform(ob, T)
        self.asm = self.asm @ (T @ R).inverted()

    def bounds(self):
        los, his = zip(*[bbox(o) for o, _ in self.objs])
        return np.min(los, 0), np.max(his, 0)

    def dims(self):
        lo, hi = self.bounds()
        return hi[0] - lo[0], hi[1] - lo[1]

    def apply_local(self, M):
        for ob, _ in self.objs:
            xform(ob, M)
        if self.asm is not None:
            self.asm = self.asm @ M.inverted()

    def lay_flat_wide(self):
        w, h = self.dims()
        if h > w:
            self.apply_local(Matrix.Rotation(math.radians(90), 4, "Z"))

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

def make_pin(length, name, at, diam=PIN_D, explode=(0, 0, 0)):
    """pino deitado, achatado embaixo (0,3 mm). 'at' = (x,z) no carro, eixo ao longo de y"""
    r = diam / 2
    ob = xform(cyl(r, -length / 2, length / 2, 32, name), Matrix.Rotation(math.radians(90), 4, "Y"))
    boolean(ob, box(-50, 50, -5, 5, -5, -r + 0.3))
    xform(ob, Matrix.Translation((0, 0, r - 0.3)))
    # impressao: ao longo de x, apoiado em z=0 ; montado: ao longo de y no ponto 'at'
    asm = Matrix.Translation((at[0], 0, at[1])) @ Matrix.Rotation(math.radians(90), 4, "Z") @ \
        Matrix.Translation((0, 0, -(r - 0.3)))
    return Part(name, [(ob, RED)], asm=asm, explode=explode)

def make_nameplate():
    W, H, T = 58.0, 15.0, 1.2
    plate = box(-W / 2, W / 2, -H / 2, H / 2, 0, T, "plaquinha")
    txt = text_mesh(NAME_TEXT, 8.0, 0.4)
    lo, hi = bbox(txt)
    k = min((W - 9) / (hi[0] - lo[0]), (H - 5.5) / (hi[1] - lo[1]))
    xform(txt, Matrix.Diagonal((k, k, 1, 1)))
    lo, hi = bbox(txt)
    xform(txt, Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, T + 0.2 - (lo[2] + hi[2]) / 2)))
    frame = boolean(box(-W / 2 + 1.0, W / 2 - 1.0, -H / 2 + 1.0, H / 2 - 1.0, T, T + 0.4),
                    box(-W / 2 + 1.6, W / 2 - 1.6, -H / 2 + 1.6, H / 2 - 1.6, 0, 2))
    Mst = Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    asm = Matrix.Translation((-24, 20, H / 2 + 1.6)) @ Matrix.Rotation(math.radians(-35), 4, "Z") @ Mst
    return Part("plaquinha", [(plate, RED), (txt, BLACK), (frame, BLACK)], asm=asm)

def make_foot():
    ob = box(-18, 18, -4.5, 4.5, 0, 6, "pezinho")
    slot = box(-30, 30, -0.8, 0.8, 1.6, 12)
    boolean(ob, slot)
    asm = Matrix.Translation((-24, 20, 0)) @ Matrix.Rotation(math.radians(-35 + 90), 4, "Z")
    return Part("pezinho", [(ob, RED)], asm=asm)

# =============================================================================
# 7. CARTAO
# =============================================================================
def layout_card(parts):
    gap, bar_w, border = 1.8, 1.2, 3.0
    inner = CARD_W - 2 * border - 2 * gap
    items = sorted(parts, key=lambda p: -p.dims()[1])
    rows = []
    for p in items:
        w, h = p.dims()
        done = False
        for row in rows:
            for cell in row["cells"]:
                grow = max(0.0, w - cell["w"])
                if (len(cell["parts"]) == 1 and cell["used_h"] + gap + h <= row["h"]
                        and row["used"] + grow <= inner and grow < 12):
                    cell["parts"].append(p)
                    cell["used_h"] += gap + h
                    cell["w"] = max(cell["w"], w)
                    row["used"] += grow
                    done = True
                    break
            if done:
                break
            if row["used"] + gap + w <= inner:
                row["cells"].append(dict(w=w, parts=[p], used_h=h))
                row["used"] += gap + w
                done = True
                break
        if not done:
            rows.append(dict(h=h, used=w, cells=[dict(w=w, parts=[p], used_h=h)]))
    placed, bars = [], []
    y = border + gap
    for ri, row in enumerate(rows):
        h = row["h"]
        x = (CARD_W - row["used"]) / 2
        for cell in row["cells"]:
            ps = cell["parts"]
            for k, p in enumerate(ps):
                lo, hi = p.bounds()
                pw, ph = hi[0] - lo[0], hi[1] - lo[1]
                if len(ps) == 1:
                    py, gates = y + (h - ph) / 2, (1, -1)
                elif k == 0:
                    py, gates = y, (1,)
                else:
                    py, gates = y + h - ph, (-1,)
                placed.append((p, (x + (cell["w"] - pw) / 2 - lo[0], py - lo[1]), ri, gates))
            x += cell["w"] + gap
        y_next = y + h + gap
        bars.append((y_next, y_next + bar_w))
        y = y_next + bar_w + gap
    card_h = bars[-1][0] + border
    bars[-1] = (card_h - border, card_h)
    return placed, bars, card_h

def build_frame(placed, bars, card_h):
    border = 3.0
    obs = [box(0, CARD_W, 0, border, 0, FRAME_H, "borda"),
           box(0, CARD_W, card_h - border, card_h, 0, FRAME_H, "borda"),
           box(0, border, 0, card_h, 0, FRAME_H, "borda"),
           box(CARD_W - border, CARD_W, 0, card_h, 0, FRAME_H, "borda")]
    for (y0, y1) in bars[:-1]:
        obs.append(box(0, CARD_W, y0, y1, 0, FRAME_H, "barra"))
    lower = [(0, border)] + bars[:-1]
    upper = bars
    for p, off, ri, gates in placed:
        lo, hi = p.bounds()
        w = hi[0] - lo[0]
        fr = [0.5] if w < 30 else [0.2, 0.8]
        trees = [(BVHTree.FromPolygons([v.co[:] for v in o.data.vertices],
                                       [pl.vertices[:] for pl in o.data.polygons]), c) for o, c in p.objs]
        for f in fr:
            gx = lo[0] + w * f
            for direction in gates:
                ybar = lower[ri][1] if direction > 0 else upper[ri][0]
                start = Vector((gx, ybar - off[1], GATE_H / 2))
                best = None
                for t, col in trees:
                    hit = t.ray_cast(start, Vector((0, direction, 0)), 200)
                    if hit[0] is not None and (best is None or hit[3] < best[0]):
                        best = (hit[3], col)
                if best is None:
                    continue
                # vermelho: o ponto entra na peca (vira um solido so);
                # outras cores: o ponto so encosta (sem sobrepor volumes de cores diferentes)
                ov = 0.3 if best[1] == RED else 0.0
                yh = ybar + direction * (best[0] + ov)
                ya, yb = sorted((ybar - direction * 0.2, yh))
                obs.append(box(gx + off[0] - GATE_W / 2, gx + off[0] + GATE_W / 2, ya, yb, 0, GATE_H, "ponto"))
    return obs

# =============================================================================
# 8. EXPORTACAO E VALIDACAO
# =============================================================================
def mesh_tris(ob, M):
    me = ob.data
    me.calc_loop_triangles()
    co = np.array([tuple(M @ v.co) for v in me.vertices])
    return np.array([co[list(lt.vertices)] for lt in me.loop_triangles])

def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"Gol kit card v2 (mm)".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            n = np.cross(t[1] - t[0], t[2] - t[0])
            ln = np.linalg.norm(n)
            n = n / ln if ln > 0 else n
            f.write(struct.pack("<12fH", *n, *t[0], *t[1], *t[2], 0))

def read_stl(path):
    with open(path, "rb") as f:
        f.read(80)
        n = struct.unpack("<I", f.read(4))[0]
        data = np.frombuffer(f.read(n * 50), dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return data["v"].reshape(-1, 3, 3).astype(np.float64)

def validate_stl(path):
    """reabre o STL exportado e confere: solido fechado, orientado, sem degenerados"""
    tris = read_stl(path)
    key = np.round(tris.reshape(-1, 3) / 1e-4).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    F = inv.reshape(-1, 3)
    area = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    degenerate = int(np.sum(area < 1e-8) + np.sum((F[:, 0] == F[:, 1]) | (F[:, 1] == F[:, 2]) | (F[:, 0] == F[:, 2])))
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    und = np.sort(E, axis=1)
    _, cnt = np.unique(und, axis=0, return_counts=True)
    nonmanifold = int(np.sum(cnt != 2))
    _, dcnt = np.unique(E, axis=0, return_counts=True)
    misoriented = int(np.sum(dcnt > 1))
    # cascas (componentes conectados)
    parent = np.arange(inv.max() + 1)
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in np.concatenate([F[:, [0, 1]], F[:, [1, 2]]]):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    shells = len({find(v) for v in np.unique(F)})
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    rep = dict(arquivo=os.path.basename(path), triangulos=len(tris), cascas=shells,
               arestas_nao_manifold=nonmanifold, arestas_mal_orientadas=misoriented,
               triangulos_degenerados=degenerate, caixa_mm=[round(float(v), 2) for v in (hi - lo)],
               min_mm=[round(float(v), 2) for v in lo], max_mm=[round(float(v), 2) for v in hi])
    rep["ok"] = bool(nonmanifold == 0 and misoriented == 0 and degenerate == 0
                 and lo[2] > -1e-3 and hi[0] <= BED and hi[1] <= BED and lo[0] >= 0 and lo[1] >= 0)
    return rep

# =============================================================================
# 9. RENDER
# =============================================================================
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "OBJECT"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = True
    sh.show_specular_highlight = True
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0.93, 0.92, 0.9)
    sc.view_settings.view_transform = "Standard"

def render(path, target, loc, lens=50, ortho=None, xray=False):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.clip_end = 5000
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.display.shading.show_xray = xray
    sc.display.shading.xray_alpha = 0.35
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)

def instance(coll, ob, M, col, name=None):
    o = bpy.data.objects.new(name or ob.name, ob.data)
    o.matrix_world = M
    o.color = (*COLORS[col][1], 1)
    coll.objects.link(o)
    return o

# =============================================================================
# 10. PRINCIPAL
# =============================================================================
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
              make_nameplate(), make_foot()]
    for i, (px, pz) in enumerate(BODY_PINS):
        parts.append(make_pin(8.6, f"pino_carroceria{i+1}", (px * S, pz * S), explode=(0, 0, 10)))
    return parts

def main():
    clear_scene()
    new_work()
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.context.scene

    print("pecas...")
    parts = build_parts()
    for p in parts:
        if not p.name.startswith("carroceria") and not p.name.startswith("roda"):
            p.lay_flat_wide()

    placed, bars, card_h = layout_card(parts)
    print(f"CARTAO: {CARD_W:.1f} x {card_h:.1f} mm, {len(parts)} pecas")
    frame = build_frame(placed, bars, card_h)

    CARD = bpy.data.collections.new("CARTAO")
    ASM = bpy.data.collections.new("MONTADO")
    EXP = bpy.data.collections.new("EXPLODIDO")
    for c in (CARD, ASM, EXP):
        sc.collection.children.link(c)

    # ---- exportacao por cor (cada cor = um solido unido)
    by_color = {c: [] for c in COLORS}
    by_color[RED] += [copy_obj(o) for o in frame]
    extras = []
    for p, off, ri, _g in placed:
        T = Matrix.Translation((off[0], off[1], 0))
        for ob, col in p.objs:
            instance(CARD, ob, T, col)
            c2 = copy_obj(ob)
            xform(c2, T)
            by_color[col].append(c2)
            if p.asm is not None:
                o = instance(ASM, ob, p.asm, col)
                instance(EXP, ob, Matrix.Translation(p.explode) @ p.asm, col)
                if p.name in ("plaquinha", "pezinho"):
                    extras.append(o)
    for o in frame:
        o.color = (*COLORS[RED][1], 1)
        WORK.objects.unlink(o)
        CARD.objects.link(o)

    reports = []
    for c, lst in by_color.items():
        if not lst:
            continue
        u = union_all(lst, f"cor{c}")
        _clean(u.data, 2e-4)            # funde vertices a menos de 0,2 micron (precisao do STL float32)
        fix_slivers(u.data)
        xform(u, Matrix.Translation((CARD_X0, 0, 0)))
        path = os.path.join(OUT, f"gol_card_{c}_{COLORS[c][0]}.stl")
        write_stl(path, mesh_tris(u, Matrix.Identity(4)))
        rep = validate_stl(path)
        reports.append(rep)
        print("  ", rep)
    json.dump(dict(cartao_mm=[CARD_W, round(card_h, 2)], origem_na_mesa_mm=[CARD_X0, 0], pecas=[p.name for p in parts],
                   validacao=reports), open(os.path.join(OUT, "cartao.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    bad = [r for r in reports if not r["ok"]]
    if bad:
        raise SystemExit("VALIDACAO FALHOU: " + ", ".join(r["arquivo"] for r in bad))

    # ---- renders
    WORK.hide_render = True
    setup_render()
    L, H = LEN * S, REAL_H * S
    ctr = (L / 2, 0, 18)

    def show(*cols):
        for c in (CARD, ASM, EXP):
            c.hide_render = c not in cols

    show(ASM)
    render(os.path.join(OUT, "render_montado_34.png"), ctr, (-95, -125, 75))
    render(os.path.join(OUT, "render_montado_traseira.png"), ctr, (205, -115, 62))
    render(os.path.join(OUT, "render_raiox_pinos_eixos.png"), ctr, (-60, -140, 90), xray=True)
    for o in extras:
        o.hide_render = True
    render(os.path.join(OUT, "orto_lado.png"), (L / 2, 0, H / 2), (L / 2, -400, H / 2), ortho=135)
    render(os.path.join(OUT, "orto_frente.png"), (0, 0, H / 2), (-400, 0, H / 2), ortho=84)
    render(os.path.join(OUT, "orto_traseira.png"), (L, 0, H / 2), (L + 400, 0, H / 2), ortho=84)
    render(os.path.join(OUT, "orto_topo.png"), (L / 2, 0, 0), (L / 2, 0, 400), ortho=135)
    show(EXP)
    render(os.path.join(OUT, "render_explodida.png"), ctr, (-110, -150, 110), lens=45)
    show(CARD)
    cc = (CARD_W / 2, card_h / 2, 0)
    render(os.path.join(OUT, "render_cartao_34.png"), cc, (CARD_W / 2 - 60, card_h / 2 - 190, 170))
    render(os.path.join(OUT, "render_cartao_topo.png"), cc, (CARD_W / 2, card_h / 2, 300),
           ortho=max(CARD_W * 1.06, card_h * 1.06 * 1.6))
    WORK.hide_viewport = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "gol_kitcard.blend"))
    print("OK")

if __name__ == "__main__":
    main()
