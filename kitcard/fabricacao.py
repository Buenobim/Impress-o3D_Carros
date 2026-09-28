# -*- coding: utf-8 -*-
"""
PARAMETROS DE FABRICACAO (mm impressos) - COMPARTILHADOS POR TODOS OS CARROS.

Sao da impressora/filamento, nao do carro. Calibre UMA vez com o cupom
(calibracao/teste_folgas_A1mini.3mf) e todos os carros passam a usar os mesmos valores.
Nunca escale estes valores junto com a escala do carro.
"""
# maquina (A1 mini)
BED = 180.0
CARD_W = 172.0           # largura maxima do cartao
CARD_X0 = 4.0            # afastamento do cartao da borda esquerda da mesa
CARD_MAX_H = 141.0       # altura maxima: sobra ~39 mm atras para a torre de purga (o CLI reserva ~35 mm)

# encaixes (acrescimos no DIAMETRO, salvo indicacao)
PIN_D = 2.5
HOLE_EXTRA = 0.20        # pino justo (carroceria)
AXLE_D = 2.5
AXLE_BODY_EXTRA = 0.35   # eixo gira livre na carroceria
AXLE_WHEEL_EXTRA = 0.10  # roda presa no eixo (pressao)
PLATE_CLR = 0.10         # folga POR LADO de placas em rebaixos (vidros, frentes, lanternas)
POCKET = 1.0             # profundidade padrao de rebaixo de placa (= espessura da placa)

# cartao
FRAME_H = 1.6
GATE_W, GATE_H = 0.8, 0.8

# detalhes
GROOVE_W, GROOVE_D = 0.45, 0.30   # vincos
MIN_WALL = 1.2                    # parede minima de carroceria oca/cockpit

# cores = slots do AMS (iguais para todos os carros, para nao trocar bobina)
COLORS = {
    1: ("vermelho", (0.62, 0.03, 0.03)),
    2: ("preto",    (0.04, 0.04, 0.04)),
    3: ("prata",    (0.72, 0.74, 0.78)),
    4: ("branco",   (0.95, 0.95, 0.92)),
}
RED, BLACK, SILVER, WHITE = 1, 2, 3, 4
