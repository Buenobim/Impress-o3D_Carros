# -*- coding: utf-8 -*-
"""
Plaquinha de teste de folgas (imprimir ANTES do cartao, ~10 min, 1 cor).
  blender -b -P teste_folgas.py   ->  saida/teste_folgas.stl

- 5 furos com folga 0.10 / 0.15 / 0.20 / 0.25 / 0.30 mm (numero gravado ao lado: 10..30)
- 2 pinos iguais aos do kit (achatados embaixo)
- 1 plaquinha presa por ponto de destaque (testa se solta facil com o dedo)
Escolha o furo em que o pino entra firme, com pressao de dedo, e sem folga:
esse valor vai em HOLE_EXTRA no gol_kitcard.py.
"""
import os, sys, math
sys.argv = [sys.argv[0]]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "gol_kitcard.py"), encoding="utf-8-sig").read()
src = src.replace("\nmain()", "\n")
exec(compile(src, "gol_kitcard.py", "exec"))

def build_test():
    global WORK
    clear_scene()
    WORK = bpy.data.collections.new("WORK")
    bpy.context.scene.collection.children.link(WORK)
    globals()["WORK"] = WORK
    clrs = [0.10, 0.15, 0.20, 0.25, 0.30]
    blk = box(0, 50, 0, 14, 0, 6, "bloco")
    for i, c in enumerate(clrs):
        x = 6 + i * 9.5
        boolean(blk, cyl((PIN_D + c) / 2, 1.5, 7, 48))
        t = text_mesh(f"{int(round(c * 100))}", 3.2, 0.6)
        lo, hi = bbox(t)
        xform(t, Matrix.Translation((x - (lo[0] + hi[0]) / 2, 10.8 - (lo[1] + hi[1]) / 2, 6 - 0.4 - lo[2])))
        boolean(blk, t)
    obs = [blk]
    for k in range(2):
        p = make_pin(8.6, "pino")
        ob = p.objs[0][0]
        lo, hi = bbox(ob)
        xform(ob, Matrix.Translation((6 + k * 12 - lo[0], 18 - lo[1], -lo[2])))
        obs.append(ob)
    # teste do ponto de destaque
    bar = box(30, 50, 16, 17.2, 0, FRAME_H, "barra")
    tab = box(34, 46, 19, 27, 0, 1.2, "plaquinha")
    gate = box(40 - GATE_W / 2, 40 + GATE_W / 2, 16.9, 19.3, 0, GATE_H, "ponto")
    obs += [bar, tab, gate]
    n = write_stl(os.path.join(OUT, "teste_folgas.stl"), [(o, Matrix.Identity(4)) for o in obs])
    print("teste_folgas.stl:", n, "triangulos")

build_test()
