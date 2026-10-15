# -*- coding: utf-8 -*-
"""
NUCLEO DO KIT CARD - funcoes comuns a todos os carros:
geometria 2D, utilidades Blender (solidos, booleanos Manifold, texto), classe Part
(pecas no sistema de impressao + matriz de montagem), cartao (moldura, linhas,
pontos de destaque), exportacao por cor com VALIDACAO do STL reaberto, renders e
a funcao gerar(mod) que produz tudo para um carro.
"""
import bpy, bmesh, math, os, struct, json
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from .fabricacao import *

WORK = None
BOOL_SOLVER = "MANIFOLD"

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

def line_x(A, B, z):
    return A[0] + (z - A[1]) * (B[0] - A[0]) / (B[1] - A[1])

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

def open_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return n

def _bool_once(target, cutter, op):
    mod = target.modifiers.new("B", "BOOLEAN")
    mod.operation = op
    mod.object = cutter
    mod.solver = BOOL_SOLVER
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.remove(mod)
    _clean(me)
    return me

def boolean(target, cutter, op="DIFFERENCE", keep=False):
    """booleano Manifold. Se o resultado abrir a malha (vertices coincidentes por azar),
    repete com o cortador girado de uma fracao de grau em torno do proprio centro."""
    me = _bool_once(target, cutter, op)
    if open_edges(me) and not open_edges(target.data):
        lo, hi = bbox(cutter)
        c = Vector(((lo + hi) / 2).tolist())
        for k in range(1, 4):
            bpy.data.meshes.remove(me)
            J = Matrix.Translation(c) @ Matrix.Rotation(math.radians(0.37 * k), 4, "Z") @ Matrix.Translation(-c)
            cutter.data.transform(J)
            me = _bool_once(target, cutter, op)
            if not open_edges(me):
                break
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

def ribbon(pts_center, width, inner_fn, outer_off, scale):
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
    return new_obj("vinco", [tuple(v * scale) for v in verts], faces)

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
# FORMAS GENERICAS (reutilizaveis por qualquer carro)
# =============================================================================
def loft_closed(name, xs, loops, scale):
    """Solido a partir de secoes transversais FECHADAS (mesmo numero de pontos, sentido
    anti-horario visto de +x) nas estacoes xs. loops[i] = array (N,2) de (y,z) em mm reais."""
    N, M = len(loops[0]), len(xs)
    verts = [(x * scale, y * scale, z * scale) for x, lp in zip(xs, loops) for (y, z) in lp]
    idx = lambda i, j: i * N + (j % N)
    faces = [(idx(i, j), idx(i, j + 1), idx(i + 1, j + 1), idx(i + 1, j))
             for i in range(M - 1) for j in range(N)]
    faces.append(tuple(idx(0, j) for j in range(N)))
    faces.append(tuple(idx(M - 1, j) for j in reversed(range(N))))
    ob = new_obj(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob

def offset_polyline(P, d):
    """desloca uma polilinha 2D aberta de d (positivo = lado esquerdo do sentido de percurso)"""
    P = np.asarray(P, float)
    out = []
    for i in range(len(P)):
        a = P[max(i - 1, 0)]
        b = P[min(i + 1, len(P) - 1)]
        t = (b - a) / np.linalg.norm(b - a)
        n = np.array([-t[1], t[0]])
        k = 1.0
        if 0 < i < len(P) - 1:   # esquina: compensa o angulo (meia-esquadria)
            t1 = (P[i] - P[i - 1]) / np.linalg.norm(P[i] - P[i - 1])
            n1 = np.array([-t1[1], t1[0]])
            k = 1.0 / max(0.5, float(np.dot(n, n1)))
        out.append(P[i] + n * d * k)
    return np.array(out)

def band_prism(path_xy, d_in, d_out, z0, z1, name="faixa"):
    """faixa (ex.: lamina de para-choque) ao longo de uma polilinha em planta"""
    inner = offset_polyline(path_xy, d_in)
    outer = offset_polyline(path_xy, d_out)
    poly = [tuple(p) for p in inner] + [tuple(p) for p in outer[::-1]]
    return prism(poly, z0, z1, name)

def teardrop_hole_y(cx, cz, r, y0, y1, name="furo_gota"):
    """furo horizontal ao longo de y com topo em 45 graus (imprime sem suporte com a peca em pe)"""
    pts = [(cx + r * math.cos(a), cz + r * math.sin(a)) for a in np.linspace(-math.pi * 0.25, math.pi * 1.25, 28)]
    pts.append((cx, cz + r * math.sqrt(2)))
    ob = prism(pts, y0, y1, name)            # prisma em xz extrudado em "z" -> girar para y
    xform(ob, Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
    ob.data.flip_normals()
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(ob.data); bm.free()
    return ob

# =============================================================================
# PECAS GENERICAS DO KIT (plaquinha + pezinho)
# =============================================================================
def make_nameplate(text, at=(-24, 20), rot_deg=-35, H=15.0):
    W, T = 58.0, 1.2
    plate = box(-W / 2, W / 2, -H / 2, H / 2, 0, T, "plaquinha")
    txt = text_mesh(text, 8.0, 0.4)
    lo, hi = bbox(txt)
    k = min((W - 9) / (hi[0] - lo[0]), (H - 5.5) / (hi[1] - lo[1]))
    xform(txt, Matrix.Diagonal((k, k, 1, 1)))
    lo, hi = bbox(txt)
    xform(txt, Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, T + 0.2 - (lo[2] + hi[2]) / 2)))
    frame = boolean(box(-W / 2 + 1.0, W / 2 - 1.0, -H / 2 + 1.0, H / 2 - 1.0, T, T + 0.4),
                    box(-W / 2 + 1.6, W / 2 - 1.6, -H / 2 + 1.6, H / 2 - 1.6, 0, 2))
    Mst = Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    asm = Matrix.Translation((at[0], at[1], H / 2 + 1.6)) @ Matrix.Rotation(math.radians(rot_deg), 4, "Z") @ Mst
    return Part("plaquinha", [(plate, RED), (txt, BLACK), (frame, BLACK)], asm=asm)

def make_foot(at=(-24, 20), rot_deg=-35):
    ob = box(-18, 18, -4.5, 4.5, 0, 6, "pezinho")
    boolean(ob, box(-30, 30, -0.8, 0.8, 1.6, 12))
    asm = Matrix.Translation((at[0], at[1], 0)) @ Matrix.Rotation(math.radians(rot_deg + 90), 4, "Z")
    return Part("pezinho", [(ob, RED)], asm=asm)

# =============================================================================
# GERACAO COMPLETA DE UM CARRO
# =============================================================================
def gerar(mod):
    """mod = carros.<carro>.modelo. Precisa ter: OUT, build_parts(), LEN_MM, HEIGHT_MM.
    Opcional: KEEP_ORIENT (prefixos de nomes de pecas que nao giram no cartao)."""
    clear_scene()
    new_work()
    os.makedirs(mod.OUT, exist_ok=True)
    sc = bpy.context.scene
    print("pecas...")
    parts = mod.build_parts()
    keep = tuple(getattr(mod, "KEEP_ORIENT", ())) + ("roda",)
    for p in parts:
        if not p.name.startswith(keep):
            p.lay_flat_wide()
    placed, bars, card_h = layout_card(parts)
    print(f"CARTAO: {CARD_W:.1f} x {card_h:.1f} mm, {len(parts)} pecas")
    if card_h > CARD_MAX_H:
        rows = {}
        for p, off, ri, g in placed:
            w, h = p.dims()
            rows.setdefault(ri, []).append(f"{p.name}({w:.0f}x{h:.1f})")
        for ri in sorted(rows):
            print(f"  linha {ri}: {', '.join(rows[ri])}")
        raise SystemExit(f"CARTAO ALTO DEMAIS: {card_h:.1f} > {CARD_MAX_H} mm (nao cabe a torre de purga)")
    frame = build_frame(placed, bars, card_h)
    CARD = bpy.data.collections.new("CARTAO")
    ASM = bpy.data.collections.new("MONTADO")
    EXP = bpy.data.collections.new("EXPLODIDO")
    for c in (CARD, ASM, EXP):
        sc.collection.children.link(c)
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
        _clean(u.data, 2e-4)
        fix_slivers(u.data)
        xform(u, Matrix.Translation((CARD_X0, 0, 0)))
        path = os.path.join(mod.OUT, f"card_{c}_{COLORS[c][0]}.stl")
        write_stl(path, mesh_tris(u, Matrix.Identity(4)))
        rep = validate_stl(path)
        reports.append(rep)
        print("  ", rep)
    json.dump(dict(cartao_mm=[CARD_W, round(card_h, 2)], origem_na_mesa_mm=[CARD_X0, 0],
                   pecas=[p.name for p in parts], validacao=reports),
              open(os.path.join(mod.OUT, "cartao.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    bad = [r for r in reports if not r["ok"]]
    if bad:
        raise SystemExit("VALIDACAO FALHOU: " + ", ".join(r["arquivo"] for r in bad))

    WORK.hide_render = True
    setup_render()
    L, H = mod.LEN_MM, mod.HEIGHT_MM
    ctr = (L / 2, 0, H * 0.42)
    out = lambda n: os.path.join(mod.OUT, n)

    def show(*cols):
        for c in (CARD, ASM, EXP):
            c.hide_render = c not in cols

    show(ASM)
    render(out("render_montado_34.png"), ctr, (L / 2 - 152, -125, 75))
    render(out("render_montado_traseira.png"), ctr, (L / 2 + 148, -115, 62))
    render(out("render_raiox_pinos_eixos.png"), ctr, (L / 2 - 117, -140, 90), xray=True)
    for o in extras:
        o.hide_render = True
    render(out("orto_lado.png"), (L / 2, 0, H / 2), (L / 2, -400, H / 2), ortho=L * 1.14)
    render(out("orto_frente.png"), (0, 0, H / 2), (-400, 0, H / 2), ortho=84)
    render(out("orto_traseira.png"), (L, 0, H / 2), (L + 400, 0, H / 2), ortho=84)
    render(out("orto_topo.png"), (L / 2, 0, 0), (L / 2, 0, 400), ortho=L * 1.14)
    show(EXP)
    render(out("render_explodida.png"), ctr, (L / 2 - 167, -150, 110), lens=45)
    show(CARD)
    cc = (CARD_W / 2, card_h / 2, 0)
    render(out("render_cartao_34.png"), cc, (CARD_W / 2 - 60, card_h / 2 - 190, 170))
    render(out("render_cartao_topo.png"), cc, (CARD_W / 2, card_h / 2, 300),
           ortho=max(CARD_W * 1.06, card_h * 1.06 * 1.6))
    WORK.hide_viewport = True
    bpy.ops.wm.save_as_mainfile(filepath=out("modelo.blend"))
    for f in os.listdir(mod.OUT):
        if f.endswith(".blend1"):
            os.remove(out(f))
    print("OK")
