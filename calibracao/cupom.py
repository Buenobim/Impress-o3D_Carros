# -*- coding: utf-8 -*-
"""
Cupom de calibracao (imprimir ANTES do cartao; 1 cor; ~20 min).
  blender -b --factory-startup -P calibracao/cupom.py   ->  calibracao/teste_folgas.stl
Vale para TODOS os carros: os valores calibrados vao em kitcard/fabricacao.py.

A) FUROS: 7 furos cegos, acrescimo no DIAMETRO de 0.10 a 0.40 mm (gravado 10..40).
   Use os 3 pinos soltos (iguais aos do kit, Ø2,5 achatados embaixo):
     - furo onde o pino entra FIRME com pressao de dedo  -> HOLE_EXTRA e AXLE_WHEEL_EXTRA (kitcard/fabricacao.py)
     - furo onde o pino GIRA LIVRE sem folga visivel     -> AXLE_BODY_EXTRA
B) REBAIXOS: 3 rebaixos com folga POR LADO 0.10 / 0.15 / 0.20 e 1 plaquinha 10x6x1 mm
   (igual aos vidros) -> PLATE_CLR = o menor que encaixa sem forcar.
C) PONTOS DE DESTAQUE: 3 abas presas por pontos de 0.6 / 0.8 / 1.0 mm -> GATE_W.
D) VINCOS: 3 sulcos 0.35 / 0.45 / 0.55 mm de largura, 0.30 de profundidade -> GROOVE_W.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import bpy
from mathutils import Matrix
import kitcard.nucleo as g

HOLES = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
POCKETS = [0.10, 0.15, 0.20]
GATES = [0.6, 0.8, 1.0]
GROOVES = [0.35, 0.45, 0.55]

def label(txt, x, y, z_top, size=2.6, depth=0.4):
    t = g.text_mesh(txt, size, depth + 0.2)
    lo, hi = g.bbox(t)
    g.xform(t, Matrix.Translation((x - (lo[0] + hi[0]) / 2, y - (lo[1] + hi[1]) / 2, z_top - depth - lo[2])))
    return t

def build():
    g.clear_scene()
    g.new_work()
    obs = []
    # A) furos
    blk = g.box(0, 66, 0, 14, 0, 6, "bloco_furos")
    centers = []
    for i, c in enumerate(HOLES):
        x = 5 + i * 9.3
        hole = g.cyl((g.PIN_D + c) / 2, 1.5, 7, 48)
        g.xform(hole, Matrix.Translation((x, 5.0, 0)))
        g.boolean(blk, hole)
        g.boolean(blk, label(f"{int(round(c * 100))}", x, 11.2, 6.0))
        centers.append((x, 5.0, g.PIN_D + c))
    obs.append(blk)
    for k in range(3):
        p = g.make_pin(8.6, "pino", (0, 0))
        ob = p.objs[0][0]
        lo, _ = g.bbox(ob)
        g.xform(ob, Matrix.Translation((70 - lo[0], 1 + k * 4.2 - lo[1], 0)))
        obs.append(ob)
    # B) rebaixos + plaquinha
    pb = g.box(0, 44, 18, 30, 0, 2.2, "bloco_rebaixos")
    for i, c in enumerate(POCKETS):
        x = 7.5 + i * 14.5
        g.boolean(pb, g.box(x - 5 - c, x + 5 + c, 21 - c, 27 + c, 2.2 - g.POCKET, 5))
    obs.append(pb)
    obs.append(g.box(48, 58, 21, 27, 0, g.POCKET, "plaquinha_vidro"))
    # C) pontos de destaque
    obs.append(g.box(0, 44, 33, 34.6, 0, g.FRAME_H, "barra"))
    for i, w in enumerate(GATES):
        x = 7 + i * 15
        obs.append(g.box(x - 5, x + 5, 36.6, 42.6, 0, 1.2, "aba"))
        obs.append(g.box(x - w / 2, x + w / 2, 34.4, 36.8, 0, g.GATE_H, "ponto"))
    # D) vincos
    vb = g.box(48, 76, 33, 43, 0, 2.0, "bloco_vincos")
    for i, w in enumerate(GROOVES):
        y = 35.5 + i * 3.0
        g.boolean(vb, g.box(49.5, 74.5, y - w / 2, y + w / 2, 2.0 - g.GROOVE_D, 3))
    obs.append(vb)

    u = g.union_all(obs, "cupom")
    g._clean(u.data, 2e-4)
    g.fix_slivers(u.data)
    g.xform(u, Matrix.Translation((90 - 39.3, 90 - 21.5, 0)))   # centro da mesa
    path = os.path.join(HERE, "teste_folgas.stl")
    g.write_stl(path, g.mesh_tris(u, Matrix.Identity(4)))
    rep = g.validate_stl(path)
    print(rep)

    # verificacao dos furos: cada centro tem que estar vazio e as paredes entre furos cheias
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector
    bvh = BVHTree.FromPolygons([v.co[:] for v in u.data.vertices], [p.vertices[:] for p in u.data.polygons])
    erros = []
    for x, y, d in [(cx + 90 - 39.3, cy + 90 - 21.5, dd) for cx, cy, dd in centers]:
        # raio vertical descendo no centro do furo: primeira superficie = fundo do furo (z=1.5)
        hit = bvh.ray_cast(Vector((x, y, 10)), Vector((0, 0, -1)))
        if hit[0] is None or abs(hit[0].z - 1.5) > 0.05:
            erros.append(f"furo em x={x:.1f} nao encontrado (z={None if hit[0] is None else round(hit[0].z, 2)})")
        # raio horizontal a partir do centro: parede a d/2
        hit = bvh.ray_cast(Vector((x, y, 4)), Vector((1, 0, 0)))
        if hit[0] is None or abs((hit[0].x - x) - d / 2) > 0.03:
            erros.append(f"diametro do furo em x={x:.1f} diferente de {d:.2f}")
    if erros or not rep["ok"]:
        raise SystemExit("CUPOM FALHOU: " + "; ".join(erros))
    print(f"CUPOM OK: {len(centers)} furos conferidos (centro, profundidade 4.5 mm e diametro)")
    u.color = (*g.COLORS[g.RED][1], 1)
    g.setup_render()
    g.render(os.path.join(HERE, "render_teste_folgas.png"), (90, 90, 0), (90, 9, 95), lens=40)

if __name__ == "__main__":
    build()
