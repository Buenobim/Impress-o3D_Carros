# -*- coding: utf-8 -*-
"""
Kit Card - VW Gol 1980 (1a geracao) em escala 1:32
Gera todas as pecas, o cartao (moldura + canais) e renders de previa.

Rodar (sem abrir o Blender):
  blender -b -P gol_kitcard.py

Saida em ./saida :
  gol_card_<cor>.stl   -> importar todos juntos no Bambu Studio (1 objeto, varias partes)
  render_*.png         -> previas
"""
import bpy, bmesh, math, os, struct
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "saida")
os.makedirs(OUT, exist_ok=True)

# ----------------------------------------------------------------------------
# PARAMETROS (mexa aqui)
# ----------------------------------------------------------------------------
S = 1 / 32                 # escala
NAME_TEXT = "GOL 1980"     # texto da plaquinha
HOLE_EXTRA = 0.20          # folga no diametro dos furos dos pinos (calibrar com o teste)
PLATE_CLR = 0.10           # folga lateral de vidros nos rebaixos
PIN_D = 2.5                # diametro dos pinos
POCKET = 1.0               # profundidade do rebaixo dos vidros = espessura do vidro
CARD_W = 172.0             # largura do cartao (A1 mini = 180)
FRAME_H = 1.6              # altura da moldura
GATE_W, GATE_H = 0.8, 0.8  # pontos de destaque

# filamento (slot do AMS) : nome, cor p/ render
COLORS = {
    1: ("vermelho", (0.62, 0.03, 0.03)),
    2: ("preto",    (0.04, 0.04, 0.04)),
    3: ("prata",    (0.72, 0.74, 0.78)),
    4: ("branco",   (0.95, 0.95, 0.92)),
}
RED, BLACK, SILVER, WHITE = 1, 2, 3, 4

# ----------------------------------------------------------------------------
# DADOS DO CARRO (mm reais) - Gol L 1980: 3790 x 1601 x 1375, entre-eixos 2358
# ----------------------------------------------------------------------------
LEN = 3650.0               # carroceria sem para-choques
ZB = 220.0                 # assoalho
ZBELT = 940.0              # linha de cintura
ROOFZ = 1350.0             # referencia do teto p/ inclinacao das laterais
WROOF = 600.0              # meia-largura no teto (tumblehome)
CROWN = 8.0
AX_F, AX_R = 680.0, 680.0 + 2358.0
TRACK = 1350.0
TIRE_R = (13 * 25.4 / 2 + 124) * S   # 155/80 R13
TIRE_W = 155 * S

# perfil lateral (topo) : x, z  + raio de arredondamento de cada vertice
WS_A, WS_B = (1330.0, 925.0), (1910.0, 1340.0)   # linha do para-brisa
TOP = [(0, 770), (70, 815), WS_A, WS_B, (2050, 1372), (2400, 1376),
       (2780, 1360), (3480, 995), (3600, 950), (LEN, 900)]
TOP_R = [0, 50, 60, 90, 120, 0, 120, 80, 40, 0]

# ----------------------------------------------------------------------------
# utilidades 2D
# ----------------------------------------------------------------------------
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
        w -= 70 * ((x - 3450) / 200) ** 2
    return w

def ws_x(z):
    return WS_A[0] + (z - WS_A[1]) * (WS_B[0] - WS_A[0]) / (WS_B[1] - WS_A[1])

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
    floor_t = trim(floor, 0, d1)
    side_t = trim(side, d1, 0)
    d2 = min(60.0, 0.45 * cumlen(gh)[-1], 0.45 * cumlen(top)[-1])
    c2 = bez(point_at(gh, cumlen(gh)[-1] - d2), K, point_at(top, d2), 12)
    gh_t = trim(gh, 0, d2)
    top_t = trim(top, d2, 0)

    segs = [floor_t, c1, side_t, gh_t, c2, top_t]
    out = resample(segs[0], NSEG[0])
    for sg, n in zip(segs[1:], NSEG[1:]):
        out = np.vstack([out, resample(sg, n)[1:]])
    return out

I_SIDE0 = NSEG[0] - 1
I_SIDE1 = sum(n - 1 for n in NSEG[:5])

_sec_cache = {}
def y_surf(x, z):
    """y da superficie externa (mm reais) no ponto lateral (x,z)"""
    k = round(x, 1)
    if k not in _sec_cache:
        _sec_cache[k] = section(x)
    P = _sec_cache[k][I_SIDE0:I_SIDE1 + 1]
    return float(np.interp(z, P[:, 1], P[:, 0]))

# ----------------------------------------------------------------------------
# utilidades Blender
# ----------------------------------------------------------------------------
def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)

WORK = None
BOOL_SOLVER = "MANIFOLD"

def new_obj(name, verts, faces, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (coll or WORK).objects.link(ob)
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

def circle(r, n=64, cx=0, cy=0):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def cyl(r, z0, z1, n=64, name="cyl"):
    return prism(circle(r, n), z0, z1, name)

def revolve(profile, n=96, name="rev"):
    """profile: lista (r,z) com r>0, de baixo p/ cima; tampas planas nas pontas"""
    m = len(profile)
    v = []
    for i in range(n):
        a = 2 * math.pi * i / n
        for r, z in profile:
            v.append((r * math.cos(a), r * math.sin(a), z))
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
    pts = []
    for nn in (n0, n1):
        for (u, w) in poly_uv:
            pts.append(origin + U * u + V * w + N * nn)
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
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bm.to_mesh(me)
    bm.free()
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    if not keep:
        bpy.data.objects.remove(cutter, do_unlink=True)
    return target

def copy_obj(ob, name=None):
    o2 = ob.copy()
    o2.data = ob.data.copy()
    o2.name = name or ob.name + "_c"
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
    ob = bpy.data.objects.new("text", me)
    WORK.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return ob

def bbox(ob, M=None):
    M = M or Matrix.Identity(4)
    co = np.array([tuple(M @ v.co) for v in ob.data.vertices])
    return co.min(0), co.max(0)

# ----------------------------------------------------------------------------
# CARROCERIA
# ----------------------------------------------------------------------------
def build_body_half():
    xs = np.linspace(0, LEN, 366)
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

    rot_y = Matrix.Rotation(math.radians(-90), 4, "X")  # eixo z -> +y

    # caixas de roda + furo do eixo
    for ax in (AX_F, AX_R):
        c = xform(cyl(TIRE_R + 1.3, 18.0, 40), rot_y @ Matrix.Identity(4))
        # cyl ao longo de z [18,40] -> apos rot: y em [18,40]
        xform(c, Matrix.Translation((ax * S, 0, TIRE_R)))
        boolean(body, c)
        h = xform(cyl((PIN_D + HOLE_EXTRA) / 2, 18.0 - 4.5, 18.5, 32), rot_y)
        xform(h, Matrix.Translation((ax * S, 0, TIRE_R)))
        boolean(body, h)

    # furos dos pinos na face de corte
    for (px, pz) in ((1100, 560), (2300, 800), (3250, 640)):
        h = xform(cyl((PIN_D + HOLE_EXTRA) / 2, -1, 4.5, 32), rot_y)
        xform(h, Matrix.Translation((px * S, 0, pz * S)))
        boolean(body, h)

    # rebaixos frente / traseira / para-choques
    L = LEN * S
    boolean(body, box(-1, 0.8, -21, 21, 480 * S, 700 * S))       # frente (grade+farois)
    boolean(body, box(-1, 0.5, -30, 30, 330 * S, 450 * S))       # para-choque diant.
    boolean(body, box(L - 0.8, L + 1, -21, 21, 560 * S, 860 * S))  # painel traseiro
    boolean(body, box(L - 0.5, L + 1, -30, 30, 330 * S, 450 * S))  # para-choque tras.

    # vincos (portas, friso, macaneta)
    wA = ws_x
    grooves = [
        ((wA(950) + 50, 260), (wA(950) + 50, 950)),
        ((wA(950) + 50, 950), (wA(1295) + 50, 1295)),
        ((wA(1295) + 50, 1295), (2440, 1295)),
        ((2440, 1295), (2440, 260)),
        ((2440, 260), (wA(950) + 50, 260)),
        ((50, 560), (3600, 560)),
        ((2290, 885), (2390, 885)),
    ]
    for g in grooves:
        boolean(body, groove_cutter(g))

    # rebaixos dos vidros
    for gp in glass_defs():
        cut = frame_prism(gp["o"], gp["U"], gp["V"], gp["N"], gp["poly"], -POCKET, 4.0, "cutglass")
        boolean(body, cut)
    return body

def groove_cutter(seg, width=13.0, depth=11.0):
    p0, p1 = np.array(seg[0], float), np.array(seg[1], float)
    t = (p1 - p0) / np.linalg.norm(p1 - p0)
    nrm = np.array([-t[1], t[0]])
    p0 = p0 - t * width / 2
    p1 = p1 + t * width / 2
    n = max(2, int(np.linalg.norm(p1 - p0) / 15) + 1)
    verts, faces = [], []
    for i, s in enumerate(np.linspace(0, 1, n)):
        p = p0 + (p1 - p0) * s
        ring = []
        for sgn in (1, -1):
            q = p + nrm * sgn * width / 2
            ys = y_surf(q[0], q[1])
            ring.append((q[0], ys - depth, q[1]))
        l_in, r_in = ring
        verts += [l_in, r_in, (r_in[0], r_in[1] + 150, r_in[2]), (l_in[0], l_in[1] + 150, l_in[2])]
    for i in range(n - 1):
        a, b = 4 * i, 4 * (i + 1)
        for k in range(4):
            faces.append((a + k, a + (k + 1) % 4, b + (k + 1) % 4, b + k))
    faces.append((0, 1, 2, 3))
    faces.append(tuple(4 * (n - 1) + k for k in (3, 2, 1, 0)))
    verts = [(x * S, y * S, z * S) for x, y, z in verts]
    return new_obj("groove", verts, faces)

def glass_defs():
    """vidros: origem, eixos U,V (no plano), N (normal p/ fora), poligono (u,v) em mm de escala"""
    out = []
    # para-brisa
    A = np.array([WS_A[0], 0, WS_A[1]]); d = np.array([WS_B[0] - WS_A[0], 0, WS_B[1] - WS_A[1]])
    U = d / np.linalg.norm(d); N = np.cross(U, [0, 1, 0])
    sin_t = U[2]
    def hw(u, pillar):
        z = A[2] + u * sin_t
        return ygh(z - CROWN) - 60 - pillar
    u0, u1 = 75, cumlen(np.array([WS_A, WS_B]))[-1] - 105
    poly = [(u0, -hw(u0, 50)), (u1, -hw(u1, 50)), (u1, hw(u1, 50)), (u0, hw(u0, 50))]
    out.append(dict(name="parabrisa", o=A * S, U=U, V=(0, 1, 0), N=N,
                    poly=[(u * S, v * S) for u, v in poly]))
    # vidro traseiro
    C = np.array([2780, 0, 1360.0]); d = np.array([700, 0, -365.0])
    U = d / np.linalg.norm(d); N = np.cross(U, [0, 1, 0])
    def hw2(u):
        z = C[2] + u * U[2]
        return ygh(z - CROWN) - 60 - 70
    u0, u1 = 140, 690
    poly = [(u0, hw2(u0)), (u1, hw2(u1)), (u1, -hw2(u1)), (u0, -hw2(u0))]
    out.append(dict(name="vidro_tras", o=C * S, U=U, V=(0, 1, 0), N=N,
                    poly=[(u * S, v * S) for u, v in poly]))
    # laterais (plano inclinado do "tumblehome")
    O = np.array([0, 785.0, ZBELT])
    W = np.array([0, -185.0, 410.0]); W /= np.linalg.norm(W)
    Nn = np.array([0, 410.0, 185.0]); Nn /= np.linalg.norm(Nn)
    kz = 1 / W[2]
    fx = lambda z: ws_x(z) + 90
    door = [(fx(955), 955), (2400, 955), (2400, 1265), (fx(1265), 1265)]
    quarter = [(2490, 955), (2930, 955), (2715, 1265), (2490, 1265)]
    for nm, pl in (("vidro_porta", door), ("vidro_fixo", quarter)):
        out.append(dict(name=nm, o=O * S, U=(1, 0, 0), V=W, N=Nn,
                        poly=[(x * S, (z - ZBELT) * kz * S) for x, z in pl]))
    return out

def inset_convex(poly, d):
    """encolhe poligono convexo (anti-horario ou horario) d mm"""
    P = np.array(poly, float)
    n = len(P)
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
    sgn = 1 if area > 0 else -1
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        t = (b - a) / np.linalg.norm(b - a)
        nin = sgn * np.array([-t[1], t[0]])
        lines.append((a + nin * d, t))
    out = []
    for i in range(n):
        (p1, t1), (p2, t2) = lines[i - 1], lines[i]
        A = np.array([t1, -t2]).T
        s = np.linalg.solve(A, p2 - p1)
        out.append(p1 + t1 * s[0])
    return [tuple(p) for p in out]

# ----------------------------------------------------------------------------
# PECAS
# ----------------------------------------------------------------------------
class Part:
    def __init__(self, name, objs, down=None, asm=True):
        self.name = name
        self.objs = objs          # lista (obj, cor)
        self.asm = Matrix.Identity(4) if asm else None
        if down is not None:
            self.to_print(Vector(down))

    def to_print(self, down):
        R = down.normalized().rotation_difference(Vector((0, 0, -1))).to_matrix().to_4x4()
        for ob, _ in self.objs:
            xform(ob, R)
        lo, hi = self.bounds()
        T = Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))
        for ob, _ in self.objs:
            xform(ob, T)
        if self.asm is not None:
            self.asm = (T @ R).inverted()

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
        """gira 90 graus no plano se ficar mais baixa (menos altura na linha do cartao)"""
        w, h = self.dims()
        if h > w:
            self.apply_local(Matrix.Rotation(math.radians(90), 4, "Z"))

def make_wheel(side):
    prof = [(TIRE_R - 0.4, 0), (TIRE_R, 0.4), (TIRE_R, TIRE_W - 0.4), (TIRE_R - 0.4, TIRE_W)]
    tire = revolve(prof, 96, "pneu")
    ring = lambda z0, z1: boolean(cyl(3.95, z0, z1, 64), cyl(3.6, z0 - 1, z1 + 1, 64))
    hub = boolean(cyl(5.3, 0, 0.4, 64, "calota"), ring(-1, 1))
    hubcut = boolean(cyl(5.3, -0.5, 0.4, 64), ring(-1, 1))
    boolean(tire, hubcut)
    boolean(tire, cyl((PIN_D + HOLE_EXTRA) / 2, TIRE_W - 3.0, TIRE_W + 1, 32))
    # local: face externa em z=0 -> montar no carro
    y_out = TRACK / 2 * S + TIRE_W / 2
    if side > 0:
        M = Matrix.Translation((0, y_out, TIRE_R)) @ Matrix.Rotation(math.radians(90), 4, "X")
    else:
        M = Matrix.Translation((0, -y_out, TIRE_R)) @ Matrix.Rotation(math.radians(-90), 4, "X")
    return [(tire, BLACK), (hub, SILVER)], M

def make_front():
    L0, L1 = -0.4, 0.8          # x (1.2 de espessura, 0.8 dentro do rebaixo)
    hw, z0, z1 = 660 * S - PLATE_CLR, 480 * S + PLATE_CLR, 700 * S - PLATE_CLR
    plate = box(L0, L1, -hw, hw, z0, z1, "frente")
    lights = []
    for sy in (-1, 1):
        cy, cz = sy * 520 * S, 590 * S
        lights.append(box(L0 - 0.1, L0 + 0.4, cy - 3.5, cy + 3.5, cz - 2.2, cz + 2.2, "farol"))
    # frisos cromados da grade
    bars = [box(L0 - 0.1, L0 + 0.4, -370 * S, 370 * S, (520 + 45 * k) * S, (520 + 45 * k) * S + 0.35, "grade")
            for k in range(4)]
    whites, silvers = [], []
    for l in lights:
        c = copy_obj(l)
        boolean(plate, c)
        boolean(l, box(L0, L1, -30, 30, -10, 60), "INTERSECT")
        whites.append(l)
    for b in bars:
        c = copy_obj(b)
        boolean(plate, c)
        boolean(b, box(L0, L1, -30, 30, -10, 60), "INTERSECT")
        silvers.append(b)
    objs = [(plate, BLACK)] + [(w, WHITE) for w in whites] + [(s, SILVER) for s in silvers]
    return Part("frente", objs, down=(-1, 0, 0))

def make_rear():
    L = LEN * S
    L0, L1 = L - 0.8, L + 0.4
    hw, z0, z1 = 660 * S - PLATE_CLR, 560 * S + PLATE_CLR, 860 * S - PLATE_CLR
    plate = box(L0, L1, -hw, hw, z0, z1, "traseira")
    parts = []
    for sy in (-1, 1):
        cy = sy * 470 * S
        parts.append((box(L1 - 0.4, L1 + 0.1, cy - 5.2, cy + 5.2, 640 * S, 820 * S, "lanterna"), RED))
    parts.append((box(L1 - 0.4, L1 + 0.1, -6.2, 6.2, 590 * S, 590 * S + 4.0, "placa"), WHITE))
    objs = [(plate, BLACK)]
    for ob, col in parts:
        boolean(plate, copy_obj(ob))
        boolean(ob, box(L0, L1, -30, 30, -10, 60), "INTERSECT")
        objs.append((ob, col))
    return Part("traseira", objs, down=(1, 0, 0))

def make_bumper(front=True):
    L = LEN * S
    hw = 760 * S
    z0, z1 = 330 * S + PLATE_CLR, 450 * S - PLATE_CLR
    if front:
        x0, x1 = -1.1, 0.5
        face = box(x0, x0 + 0.4, -hw + 1.2, hw - 1.2, z0, z1, "cromado")
        down = (-1, 0, 0)
    else:
        x0, x1 = L - 0.5, L + 1.1
        face = box(x1 - 0.4, x1, -hw + 1.2, hw - 1.2, z0, z1, "cromado")
        down = (1, 0, 0)
    bar = box(x0, x1, -hw, hw, z0, z1, "parachoque")
    boolean(bar, copy_obj(face))
    objs = [(bar, BLACK), (face, SILVER)]
    if front:  # placa "GOL" no para-choque dianteiro
        pl = box(x0 - 0.1, x0 + 0.4, -3.6, 3.6, z0 + 0.5, z1 - 0.5, "placa")
        boolean(face, copy_obj(pl))
        boolean(pl, box(x0, x1, -30, 30, -10, 60), "INTERSECT")
        objs.append((pl, WHITE))
    return Part("parachoque_" + ("diant" if front else "tras"), objs, down=down)

def make_glass(gp):
    poly = inset_convex(gp["poly"], PLATE_CLR)
    ob = frame_prism(gp["o"], gp["U"], gp["V"], gp["N"], poly, -POCKET, 0.0, gp["name"])
    return ob

def make_pin(length, name):
    r = PIN_D / 2
    ob = xform(cyl(r, -length / 2, length / 2, 32, name), Matrix.Rotation(math.radians(90), 4, "Y"))
    boolean(ob, box(-20, 20, -5, 5, -5, -r + 0.3))   # achatado embaixo
    return Part(name, [(ob, RED)], down=(0, 0, -1), asm=False)

def make_nameplate():
    W, H, T = 58.0, 15.0, 1.6
    plate = box(-W / 2, W / 2, -H / 2, H / 2, 0, T, "plaquinha")
    txt = text_mesh(NAME_TEXT, 8.0, 0.4)
    lo, hi = bbox(txt)
    k = min((W - 8) / (hi[0] - lo[0]), (H - 5) / (hi[1] - lo[1]))
    xform(txt, Matrix.Diagonal((-k, k, 1, 1)))    # espelhado: face de baixo e a vista
    txt.data.flip_normals()
    lo, hi = bbox(txt)
    xform(txt, Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, 0.2 - (lo[2] + hi[2]) / 2)))
    cut = copy_obj(txt)
    xform(cut, Matrix.Translation((0, 0, -0.1)) @ Matrix.Diagonal((1, 1, 1.25, 1)))
    boolean(plate, cut)
    # borda preta
    frame = boolean(box(-W / 2 + 1.0, W / 2 - 1.0, -H / 2 + 1.0, H / 2 - 1.0, 0, 0.4),
                    box(-W / 2 + 1.6, W / 2 - 1.6, -H / 2 + 1.6, H / 2 - 1.6, -1, 1))
    boolean(plate, copy_obj(frame))
    p = Part("plaquinha", [(plate, RED), (txt, BLACK), (frame, BLACK)], down=(0, 0, -1))
    # em pe, na frente do carro (so p/ render)
    Mst = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    p.asm = Matrix.Translation((-22, 22, H / 2 + 1.6)) @ Matrix.Rotation(math.radians(-35), 4, "Z") @ Mst
    return p

def make_foot():
    ob = box(-24, 24, -5, 5, 0, 6, "pezinho")
    slot = box(-30, 30, -0.95, 0.95, 1.6, 12)
    xform(slot, Matrix.Rotation(math.radians(-12), 4, "X"))
    boolean(ob, slot)
    p = Part("pezinho", [(ob, RED)], down=(0, 0, -1))
    p.asm = Matrix.Translation((-22, 22, 0)) @ Matrix.Rotation(math.radians(-35 + 90), 4, "Z")
    return p

# ----------------------------------------------------------------------------
# CARTAO (moldura, canais e pontos de destaque)
# ----------------------------------------------------------------------------
def layout_card(parts):
    """First-fit decreasing em linhas; pecas baixas podem ser empilhadas (2 por celula)."""
    gap, bar_w, border = 1.8, 1.2, 3.0
    inner = CARD_W - 2 * border - 2 * gap
    items = sorted(parts, key=lambda p: -p.dims()[1])
    rows = []   # dict(h, used, cells=[dict(w, parts=[...], used_h)])
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
                off = (x + (cell["w"] - pw) / 2 - lo[0], py - lo[1])
                placed.append((p, off, ri, gates))
            x += cell["w"] + gap
        y_next = y + h + gap
        bars.append((y_next, y_next + bar_w))
        y = y_next + bar_w + gap
    card_h = bars[-1][0] + border
    bars[-1] = (card_h - border, card_h)      # ultima barra = borda superior
    return placed, bars, card_h, rows

def build_frame(placed, bars, card_h, coll):
    border = 3.0
    obs = []
    obs.append(box(0, CARD_W, 0, border, 0, FRAME_H, "borda"))
    obs.append(box(0, CARD_W, card_h - border, card_h, 0, FRAME_H, "borda"))
    obs.append(box(0, border, 0, card_h, 0, FRAME_H, "borda"))
    obs.append(box(CARD_W - border, CARD_W, 0, card_h, 0, FRAME_H, "borda"))
    for (y0, y1) in bars[:-1]:
        obs.append(box(0, CARD_W, y0, y1, 0, FRAME_H, "barra"))
    lower = [(0, border)] + bars[:-1]
    upper = bars
    # pontos de destaque
    for p, off, ri, gates in placed:
        lo, hi = p.bounds()
        w = hi[0] - lo[0]
        fr = [0.5] if w < 30 else [0.22, 0.78]
        trees = []
        for ob, col in p.objs:
            me = ob.data
            trees.append((BVHTree.FromPolygons([v.co[:] for v in me.vertices],
                                               [pl.vertices[:] for pl in me.polygons]), col))
        for f in fr:
            gx = lo[0] + w * f
            for direction in gates:
                ybar = lower[ri][1] if direction > 0 else upper[ri][0]
                start = Vector((gx, ybar - off[1], min(GATE_H / 2, 0.4)))
                best = None
                for t, col in trees:
                    hit = t.ray_cast(start, Vector((0, direction, 0)), 200)
                    if hit[0] is not None and (best is None or hit[3] < best[0]):
                        best = (hit[3], col)
                if best is None:
                    continue
                ov = 0.3 if best[1] == RED else 0.08
                yh = ybar + direction * (best[0] + ov)
                ya, yb = sorted((ybar - direction * 0.2, yh))
                obs.append(box(gx + off[0] - GATE_W / 2, gx + off[0] + GATE_W / 2, ya, yb, 0, GATE_H, "ponto"))
    for o in obs:
        WORK.objects.unlink(o)
        coll.objects.link(o)
    return obs

# ----------------------------------------------------------------------------
# EXPORTACAO
# ----------------------------------------------------------------------------
def write_stl(path, obs_mats):
    tris = []
    for ob, M in obs_mats:
        me = ob.data
        me.calc_loop_triangles()
        co = np.array([tuple(M @ v.co) for v in me.vertices])
        for lt in me.loop_triangles:
            tris.append(co[list(lt.vertices)])
    with open(path, "wb") as f:
        f.write(b"Gol kit card".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            n = np.cross(t[1] - t[0], t[2] - t[0])
            ln = np.linalg.norm(n)
            n = n / ln if ln > 0 else n
            f.write(struct.pack("<12fH", *n, *t[0], *t[1], *t[2], 0))
    return len(tris)

# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
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

def render(path, target, loc, lens=50, ortho=None):
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)

def instance(coll, ob, M, col, name=None):
    o = bpy.data.objects.new(name or ob.name, ob.data)
    o.matrix_world = M
    o.color = (*COLORS[col][1], 1)
    coll.objects.link(o)
    return o

# ----------------------------------------------------------------------------
def main():
    global WORK
    clear_scene()
    sc = bpy.context.scene
    WORK = bpy.data.collections.new("WORK")
    sc.collection.children.link(WORK)

    print("carroceria...")
    body = build_body_half()
    body_r = mirror_y(copy_obj(body, "carroceria_D"))
    parts = [Part("carroceria_E", [(body, RED)], down=(0, -1, 0)),
             Part("carroceria_D", [(body_r, RED)], down=(0, 1, 0))]

    print("rodas...")
    for i, (ax, side) in enumerate([(AX_F, 1), (AX_F, -1), (AX_R, 1), (AX_R, -1)]):
        objs, M = make_wheel(side)
        M = Matrix.Translation((ax * S, 0, 0)) @ M
        for ob, _ in objs:
            xform(ob, M)
        parts.append(Part(f"roda{i+1}", objs, down=(0, side, 0)))

    print("vidros...")
    for gp in glass_defs():
        if gp["name"].startswith("vidro_p") or gp["name"].startswith("vidro_f"):
            for sgn in (1, -1):
                g = make_glass(gp)
                if sgn < 0:
                    mirror_y(g)
                parts.append(Part(gp["name"], [(g, BLACK)], down=Vector(gp["N"]) * -1 *
                                  Vector((1, sgn, 1))))
        else:
            g = make_glass(gp)
            parts.append(Part(gp["name"], [(g, BLACK)], down=Vector(gp["N"]) * -1))

    print("frente/traseira/para-choques...")
    parts += [make_front(), make_rear(), make_bumper(True), make_bumper(False)]
    parts += [make_nameplate(), make_foot()]
    for i in range(3):
        parts.append(make_pin(8.6, f"pino_carroceria{i+1}"))
    for i in range(4):
        parts.append(make_pin(7.6, f"pino_eixo{i+1}"))

    # ---- checagem de malha (tudo tem que ser solido fechado)
    for p in parts:
        for ob, col in p.objs:
            bm = bmesh.new(); bm.from_mesh(ob.data)
            bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
            bm.free()
            if bad:
                print(f"  AVISO malha aberta: {p.name}/{ob.name}: {bad} arestas")

    # ---- cartao
    for p in parts:
        if not p.name.startswith("carroceria"):
            p.lay_flat_wide()
    placed, bars, card_h, rows = layout_card(parts)
    print(f"CARTAO: {CARD_W:.1f} x {card_h:.1f} mm, {len(rows)} linhas")
    CARD = bpy.data.collections.new("CARD")
    ASM = bpy.data.collections.new("ASM")
    sc.collection.children.link(CARD)
    sc.collection.children.link(ASM)
    frame = build_frame(placed, bars, card_h, CARD)
    for o in frame:
        o.color = (*COLORS[RED][1], 1)

    extras = []
    by_color = {c: [] for c in COLORS}
    for o in frame:
        by_color[RED].append((o, Matrix.Identity(4)))
    for p, off, ri, _g in placed:
        T = Matrix.Translation((off[0], off[1], 0))
        for ob, col in p.objs:
            instance(CARD, ob, T, col)
            by_color[col].append((ob, T))
            if p.asm is not None:
                o = instance(ASM, ob, p.asm, col)
                if p.name in ("plaquinha", "pezinho"):
                    extras.append(o)

    for c, lst in by_color.items():
        if lst:
            n = write_stl(os.path.join(OUT, f"gol_card_{c}_{COLORS[c][0]}.stl"), lst)
            print(f"  STL cor {c} ({COLORS[c][0]}): {n} triangulos")

    # ---- renders
    WORK.hide_render = True
    setup_render()
    CARD.hide_render = True
    ctr = (57, 0, 18)
    render(os.path.join(OUT, "render_montado_34.png"), ctr, (-95, -125, 75), 50)
    render(os.path.join(OUT, "render_montado_traseira.png"), ctr, (200, -110, 60), 50)
    for o in extras:
        o.hide_render = True
    render(os.path.join(OUT, "render_montado_lado.png"), ctr, (57, -260, 18), 50)
    for o in extras:
        o.hide_render = False
    CARD.hide_render = False
    ASM.hide_render = True
    cc = (CARD_W / 2, card_h / 2, 0)
    render(os.path.join(OUT, "render_cartao_34.png"), cc, (CARD_W / 2 - 60, card_h / 2 - 190, 170), 50)
    render(os.path.join(OUT, "render_cartao_topo.png"), cc, (CARD_W / 2, card_h / 2, 300), 50,
           ortho=max(CARD_W * 1.06, card_h * 1.06 * 1.6))

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "gol_kitcard.blend"))
    print("OK")

main()
