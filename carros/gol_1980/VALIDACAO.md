# Relatório de validação — v2

Cada afirmação traz o nível em que foi comprovada:

| Nível | Significa |
|---|---|
| **código** | Verificado lendo o código-fonte |
| **malha** | Medido automaticamente no STL exportado e reaberto |
| **fatiador** | Medido no G-code/3MF gerado pelo Bambu Studio 2.05.00.66 (linha de comando) |
| **físico** | Validado em impressão real |

> **Nenhum item desta versão foi validado em impressão física.** Não há promessa de encaixe garantido, montagem sem cola, ausência de defeitos ou aptidão comercial.

## 1. Perfis e G-code (P0-01, P0-02)

| Checagem | Resultado | Nível |
|---|---|---|
| G-code de máquina (start, end, troca, camada, timelapse) igual aos templates oficiais da A1 mini 0.4 | idêntico (`bambu_perfis.py` falha se diferir) | código |
| Linhas fixas do start G-code oficial presentes, em ordem, no G-code gerado | 334/334 (cupom e cartão) | fatiador |
| `printer_model` / `printable_area` | Bambu Lab A1 mini / 0x0–180x180 | fatiador |
| Mesa | Textured PEI Plate, `M190 S65` | fatiador |
| Trajetórias **com extrusão**, fora das trocas de filamento: cartão | x 4,21–175,79 / y 0,21–174,26 mm | fatiador |
| Trajetórias com extrusão: cupom | x 50,9–129,1 / y 68,7–111,3 mm | fatiador |
| Torre de purga fora da zona reservada (x>156, y>152) | torre em x=10, y=144,7 | fatiador |

Movimentos de manutenção do template oficial (limpeza, corte, descarte) podem sair da área de 180 mm. Eles não são checados como erro, porque são do perfil oficial.

## 2. Malhas exportadas (P0-04)

Os STLs são reabertos depois da gravação, com os vértices fundidos em uma grade de 0,1 µm:

| Arquivo | Triângulos | Cascas | Não-manifold | Mal orientadas | Degenerados | Caixa (mm) |
|---|---|---|---|---|---|---|
| card_1_vermelho.stl | 84.732 | 1 | 0 | 0 | 0 | 172 × 141 × 25 |
| card_2_preto.stl | 15.848 | 24 | 0 | 0 | 0 | 158,8 × 124,1 × 4,84 |
| card_3_prata.stl | 5.032 | 8 | 0 | 0 | 0 | 145,6 × 120,2 × 4,84 |
| card_4_branco.stl | 96 | 8 | 0 | 0 | 0 | 106,7 × 17,1 × 1,45 |
| teste_folgas.stl | 10.100 | 8 | 0 | 0 | 0 | 78,6 × 43 × 6 |

O vermelho ter **1 casca** comprova que todas as peças vermelhas estão ligadas à moldura (**malha**). As peças de outra cor são tocadas por pontos vermelhos, sem sobreposição de volume (**código**).

## 3. Cupom de calibração (P0-03)

| Checagem | Resultado | Nível |
|---|---|---|
| 7 furos separados, com centro correto | ok (raio vertical no centro de cada furo encontra o fundo a z=1,5) | malha |
| Diâmetros 2,60 / 2,65 / … / 2,90 mm | ok (raio horizontal, ±0,03 mm) | malha |
| Número gravado ao lado do furo correspondente | posição definida no código | código |
| Legibilidade dos números, encaixe e ruptura dos pontos | **pendente** | físico |

## 4. Fatiamento (estimativas, não medições)

| | Cupom | Cartão |
|---|---|---|
| Tempo estimado | 23 min | 3h17 |
| Filamento estimado (g) | 6,3 | 66,3 vermelho · 9,7 preto · 2,3 prata · 1,8 branco |
| Trocas de cor (cargas M620 − 1) | 0 | 35 |
| Cores por camada | só vermelho | 4 cores nas camadas 0–1 e 6; 3 nas 7 e 20–23; 2 nas 2–5 e 8–19; só vermelho da 24 em diante |

O peso informado pelo fatiador pode não incluir todo o filamento descartado na purga. Custo por unidade aprovada depende de medições reais (ver pendências).

## 5. Geometria e fidelidade

| Checagem | Resultado | Nível |
|---|---|---|
| Comprimento total com para-choques | 3688 + 2 × 51 = 3790 mm → 118,4 mm | código |
| Entre-eixos / bitolas | 73,7 mm / 42,2 e 42,7 mm | código |
| Pneu | Ø18,1 × 4,84 mm | código |
| Pinos e eixos na montagem digital, sem interferência visível | render de raio-X | render (inspeção visual) |
| Semelhança com o Gol 1300 L 1980 | comparação visual com as fotos de referência (manifesto) | **aprovação do proprietário pendente** |

## Pendências

1. **Impressão física do cupom** (`teste_folgas_A1mini.3mf`). Anotar:
   - o furo justo e o furo em que o pino gira livre;
   - o rebaixo que encaixa;
   - a largura de ponto de destaque que solta limpa;
   - o vinco que aparece bem.

   Depois, ajustar `HOLE_EXTRA`, `AXLE_*`, `PLATE_CLR`, `GATE_W` e `GROOVE_W` e regerar.
2. **Confirmar o equipamento:** bico 0,4, mesa texturizada, AMS lite com vermelho/preto/prata/branco nos slots 1–4 e PLA Basic.
3. **Primeiro cartão completo:** conferir rodas girando sem raspar, retenção dos vidros (sem cola ou com cola), marcas dos pontos, cores e emendas.
4. **Aprovação da forma** pelo proprietário (e pelo pai dele) **antes** dos microdetalhes.
5. **Ainda não modelados:**
   - retrovisor (só lado do motorista), limpadores, calhas do teto, tampa de combustível (lado não confirmado);
   - piscas em âmbar (hoje brancos: exigiriam uma 5ª cor ou troca manual);
   - numeração das peças na moldura e manual de montagem ilustrado.
6. **Custo por unidade aprovada:** material + purga medida + perdas + horas de máquina + energia + mão de obra + embalagem.
7. **Venda:** marca "Gol"/VW, direitos das fotos e enquadramento no Inmetro (brinquedo × objeto de coleção).
