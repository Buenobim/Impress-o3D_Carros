# Validação — Puma GTS conversível

Níveis: **código**, **malha** (STL reaberto), **fatiador** (Bambu Studio 2.05.00.66, linha de comando) e **físico**.

> **Nada foi validado em impressão física.**

## Malhas exportadas

| Arquivo | Triângulos | Cascas | Não-manifold | Mal orientadas | Degenerados | Caixa (mm) |
|---|---|---|---|---|---|---|
| card_1_vermelho.stl | 56.188 | 3 | 0 | 0 | 0 | 172 × 138,8 × 21,7 |
| card_2_preto.stl | 14.616 | 22 | 0 | 0 | 0 | 162,3 × 129,2 × 5,47 |
| card_3_prata.stl | 5.992 | 10 | 0 | 0 | 0 | 107,2 × 65,1 × 5,47 |
| card_4_branco.stl | 336 | 4 | 0 | 0 | 0 | 24,6 × 52,3 × 1,2 |

O vermelho tem 3 cascas: moldura + carroceria + pontos (1), mais as 2 lentes vermelhas, que ficam presas nas molduras pretas das lanternas (**malha**).

## Fatiamento (estimativas)

| Checagem | Resultado |
|---|---|
| Start G-code oficial da A1 mini | 334/334 linhas fixas, em ordem |
| Mesa | Textured PEI, `M190 S65` |
| Trajetórias com extrusão | x 4,21–175,79 / y 0,21–172,22 mm |
| Tempo / filamento | 3h24 / 46,5 + 13,7 + 5,3 + 1,7 g |
| Trocas de cor | 50 |
| Cores por camada | 4 cores nas camadas 0–5; 3 nas 6–12 e 23–26; 2 nas 13–22; só vermelho da 27 à 107 |

## Geometria

| Checagem | Resultado | Nível |
|---|---|---|
| Comprimento / entre-eixos | 122,7 mm de carroceria + lâminas ≈ 125 / 67,2 mm | código |
| Carroceria sem balanço acima de 45° (exceto a curva de cima das caixas de roda, que é ponte) | por construção (seções com recolhimento ≤ 26°, chanfros de 45°, furos em gota) | código |
| Eixos passantes, sem cruzar o cockpit | raio-X | render |
| Semelhança com o Puma GTS | comparação visual com as fotos de referência | **aprovação do dono pendente** |

## Pendências

Ver [README.md](README.md#limitações-e-pendências).
