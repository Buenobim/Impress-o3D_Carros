# -*- coding: utf-8 -*-
"""
Fatia no Bambu Studio (linha de comando) com os perfis OFICIAIS da A1 mini e
confere cada resultado. Falha (codigo 1) se qualquer checagem nao passar.

  1) saida/teste_folgas_A1mini.3mf   (cupom, 1 cor - imprimir primeiro)
  2) saida/gol_kitcard_A1mini.3mf    (cartao, 4 cores)

Uso:  python fatiar.py
Pre-requisitos: python bambu_perfis.py ; blender -b -P gol_kitcard.py ; blender -b -P teste_folgas.py
"""
import hashlib, json, os, re, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "saida")
CFG = os.path.join(HERE, "bambu_cfg")
BAMBU = r"C:\Program Files\Bambu Studio\bambu-studio.exe"
BBL = r"C:\Program Files\Bambu Studio\resources\profiles\BBL"
CARD_STLS = ["gol_card_1_vermelho.stl", "gol_card_2_preto.stl", "gol_card_3_prata.stl", "gol_card_4_branco.stl"]
BED = 180.0
TOWER_W = 30.0
# Na linha de comando o Bambu reserva ~35 mm para a torre (estimativa conservadora).
# O canto traseiro direito (x>156, y>152) e a zona 'head_wrap_detect_zone' da A1 mini.

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def slice_(stls, ids, out3mf, proc_extra):
    proc = json.load(open(os.path.join(CFG, "process.json"), encoding="utf-8"))
    proc["brim_type"] = "no_brim"      # a moldura ja da base larga; o cartao vai ate a borda da mesa
    proc.update(proc_extra)
    tmp = os.path.join(OUT, "_process_fatiamento.json")
    json.dump(proc, open(tmp, "w", encoding="utf-8"), indent=1)
    fil = ";".join(f"../bambu_cfg/f{i}.json" for i in range(1, 5))
    cmd = [BAMBU, "--slice", "0", "--arrange", "0"] + (["--assemble"] if len(stls) > 1 else []) + [
        "--load-settings", f"../bambu_cfg/machine.json;{os.path.basename(tmp)}",
        "--load-filaments", fil, "--load-filament-ids", ids,
        "--outputdir", ".", "--export-3mf", out3mf] + stls
    r = subprocess.run(cmd, cwd=OUT, capture_output=True, text=True, errors="ignore")
    os.remove(tmp)
    p = os.path.join(OUT, "plate_1.gcode")
    if os.path.exists(p):
        os.remove(p)
    if r.returncode != 0 or not os.path.exists(os.path.join(OUT, out3mf)):
        msg = [l.split("error_message=")[-1] for l in (r.stdout + r.stderr).splitlines() if "error_message" in l]
        sys.exit(f"FATIAMENTO FALHOU ({out3mf}): {msg[:1]}")

def verify(out3mf, stls):
    path3mf = os.path.join(OUT, out3mf)
    z = zipfile.ZipFile(path3mf)
    gcode = z.read("Metadata/plate_1.gcode").decode("utf-8", "ignore")
    proj = json.loads(z.read("Metadata/project_settings.config").decode("utf-8"))
    info = z.read("Metadata/slice_info.config").decode("utf-8")
    checks, erros = {}, []
    tpl = json.load(open(os.path.join(BBL, "machine", "Bambu Lab A1 mini 0.4 nozzle template machine_start_gcode.json"),
                         encoding="utf-8"))["machine_start_gcode"]
    fixed = [l.strip() for l in tpl.splitlines() if l.strip() and not l.strip().startswith(";")
             and "{" not in l and "[" not in l]
    pos = found = 0
    for l in fixed:
        i = gcode.find(l, pos)
        if i >= 0:
            found += 1
            pos = i + len(l)
    checks["start_gcode_linhas_fixas_do_template_oficial_em_ordem"] = f"{found}/{len(fixed)}"
    if found != len(fixed):
        erros.append("start G-code difere do template oficial da A1 mini")
    checks["printer_model"] = proj.get("printer_model")
    checks["printable_area"] = proj.get("printable_area")
    checks["curr_bed_type"] = proj.get("curr_bed_type")
    checks["zona_reservada_head_wrap"] = proj.get("head_wrap_detect_zone")
    if proj.get("printer_model") != "Bambu Lab A1 mini":
        erros.append("printer_model nao e A1 mini")
    if proj.get("curr_bed_type") != "Textured PEI Plate":
        erros.append("mesa nao e Textured PEI Plate")
    beds = sorted(set(re.findall(r"^M190 S(\d+)", gcode, re.M)))
    checks["M190_temperatura_mesa"] = beds
    if beds != ["65"]:
        erros.append(f"temperatura da mesa inesperada: {beds}")
    body = gcode.split("; MACHINE_START_GCODE_END", 1)[-1].split("; MACHINE_END_GCODE_START", 1)[0]
    x = y = None
    absolute, in_change = True, False
    lo, hi = [1e9, 1e9], [-1e9, -1e9]
    for line in body.splitlines():
        s = line.split(";", 1)[0].strip()
        if "M620 S" in s:
            in_change = True
        if s.startswith("M621"):
            in_change = False
        if s == "G90":
            absolute = True
        elif s == "G91":
            absolute = False
        if not re.match(r"G[01]\s", s):
            continue
        mx, my, me = re.search(r"X(-?[\d.]+)", s), re.search(r"Y(-?[\d.]+)", s), re.search(r"E(-?[\d.]+)", s)
        if absolute:
            x = float(mx.group(1)) if mx else x
            y = float(my.group(1)) if my else y
        if me and float(me.group(1)) > 0 and (mx or my) and x is not None and y is not None and not in_change:
            lo = [min(lo[0], x), min(lo[1], y)]
            hi = [max(hi[0], x), max(hi[1], y)]
    checks["trajetorias_impressao_xy_min"] = [round(v, 2) for v in lo]
    checks["trajetorias_impressao_xy_max"] = [round(v, 2) for v in hi]
    if lo[0] < 0 or lo[1] < 0 or hi[0] > BED or hi[1] > BED:
        erros.append("trajetoria de impressao fora da mesa 180x180")
    loads = len(re.findall(r"^M620 S\d+A", gcode, re.M))
    checks["cargas_de_filamento_M620"] = loads
    checks["trocas_de_cor"] = max(0, loads - 1)
    t = re.search(r"total estimated time: ([^\n;]+)", gcode)
    w = re.search(r"total filament weight \[g\] : ([^\n]+)", gcode)
    checks["tempo_estimado_fatiador"] = t.group(1).strip() if t else None
    checks["peso_g_por_filamento_fatiador"] = w.group(1).strip() if w else None
    checks["cores_por_faixa_de_camadas"] = [{"filamentos": a, "camadas": b}
                                           for a, b in re.findall(r'filament_list="([^"]+)" layer_ranges="([^"]+)"', info)]
    ver = re.search(r"BambuStudio[- ]?([\d.]+)", gcode)
    return dict(arquivo=out3mf, status="ok" if not erros else "FALHOU", erros=erros,
                bambu_studio=ver.group(1) if ver else None, checagens=checks,
                sha256={os.path.basename(p): sha(p) for p in [path3mf] + [os.path.join(OUT, s) for s in stls]})

def main():
    card = json.load(open(os.path.join(OUT, "cartao.json"), encoding="utf-8"))
    cw, ch = card["cartao_mm"]
    if ch + 3.7 + 35 > BED:
        sys.exit(f"cartao alto demais ({ch:.1f} mm): nao sobra espaco para a torre de purga")
    reps = []
    # 1) cupom (1 cor, vermelho, sem torre)
    slice_(["teste_folgas.stl"], "1", "teste_folgas_A1mini.3mf", {"enable_prime_tower": "0"})
    reps.append(verify("teste_folgas_A1mini.3mf", ["teste_folgas.stl"]))
    # 2) cartao 4 cores; torre atras do cartao, a esquerda (longe da zona reservada)
    slice_(CARD_STLS, "1,2,3,4", "gol_kitcard_A1mini.3mf",
           {"prime_tower_width": str(int(TOWER_W)), "wipe_tower_x": ["10"], "wipe_tower_y": [str(round(ch + 3.7, 1))]})
    reps.append(verify("gol_kitcard_A1mini.3mf", CARD_STLS))
    rep = dict(perfis=dict(maquina="Bambu Lab A1 mini 0.4 nozzle", processo="0.20mm Standard @BBL A1M",
                           filamento="Bambu PLA Basic @BBL A1M", mesa="Textured PEI Plate"),
               resultados=reps,
               observacao="Estimativas do fatiador; NAO sao medicoes de impressao fisica.")
    json.dump(rep, open(os.path.join(OUT, "fatiamento.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for r in reps:
        c = r["checagens"]
        print(f"{r['arquivo']}: {r['status']} | {c['tempo_estimado_fatiador']} | g {c['peso_g_por_filamento_fatiador']}"
              f" | trocas {c['trocas_de_cor']} | start {c['start_gcode_linhas_fixas_do_template_oficial_em_ordem']}"
              f" | xy {c['trajetorias_impressao_xy_min']}..{c['trajetorias_impressao_xy_max']} {r['erros']}")
    z = zipfile.ZipFile(os.path.join(OUT, "gol_kitcard_A1mini.3mf"))
    open(os.path.join(OUT, "bambu_placa.png"), "wb").write(z.read("Metadata/plate_1.png"))
    if any(r["erros"] for r in reps):
        sys.exit(1)

if __name__ == "__main__":
    main()
