# Changelog

## Molde + Puma GTS — 28/09/2026 (branch `molde-puma`)

**Repositório virou um molde para vários carros**
- **Motor comum** em `kitcard/`: `nucleo.py` com geometria, booleanos, cartão, validação e renders.
- **Folgas e cores** em `fabricacao.py`, compartilhadas por todos os carros e calibradas uma vez pelo cupom.
- **Cada carro** fica em `carros/<carro>/`.
- **Execução:** `gerar.ps1 <carro>` e `fatiar.py <carro>|cupom`.
- **Documentação do molde:**
  - `CLAUDE.md`: fluxo, interface do carro, portões e regras aprendidas;
  - `PROMPT_NOVO_CARRO.md`: formulário para pedir um carro novo.
- **Gol reorganizado** em `carros/gol_1980`. Os STLs gerados pelo motor novo são **idênticos byte a byte** aos da v2, e o fatiamento dá o mesmo resultado (3h17, 334/334).

**Robustez do motor**
- **Booleanos:** se um corte abrir a malha, o núcleo repete com o cortador levemente girado.
- **Fatiamento:** agora numa pasta temporária curta, porque caminhos acima de 260 caracteres quebravam o Bambu Studio.
- **Blender:** roda com `--python-exit-code 1`, para que erros interrompam o `gerar.ps1`.
- **Cartão alto demais:** o gerador lista as linhas, para mostrar onde otimizar.
- **Novas funções genéricas:** `loft_closed`, `offset_polyline`, `band_prism` e `teardrop_hole_y`.

**Puma GTS conversível (novo)**
- **Arquitetura B:** carroceria inteiriça impressa em pé, com cockpit aberto. Com duas metades, o cockpit viraria balanço.
- **25 peças:**
  - rodas de liga (6 janelas) e eixos passantes;
  - base dos bancos e 2 encostos deitados;
  - moldura do para-brisa com pernas encaixadas;
  - capota recolhida e grade do motor;
  - faróis, lanternas e placas;
  - 4 lâminas de para-choque;
  - plaquinha.
- **Encostos separados e deitados:** 120 → 50 trocas de cor e 5h29 → 3h24 (fatiador).

## v2 — 27/09/2026 (branch `v2`)

Resposta à auditoria "Gol V2" (relatório externo). Cada item: problema → o que mudou → como foi verificado.

### Bloqueios de impressão (P0)

| Item | Problema confirmado | Correção | Verificação |
|---|---|---|---|
| P0-01 | O `machine.json` da v1 foi "achatado" sem resolver o campo `include`. Os templates de G-code da A1 mini ficaram de fora e entraram rotinas de outro perfil (movimentos Y200/Y245/Y265). | Novo `bambu_perfis.py`: resolve `inherits` **e** `include` e **falha** se o G-code de máquina for diferente dos templates oficiais. O 3MF da v1 foi removido da `main`. | `fatiar.py` confere, no G-code gerado, as 334/334 linhas fixas do start G-code oficial, na ordem. |
| P0-02 | O 3MF da v1 dizia "Cool Plate" (mesa a 35 °C), mas o README falava em mesa texturizada. | `curr_bed_type = Textured PEI Plate`, com o perfil PLA Basic da A1 mini (65 °C). | `fatiar.py` confere `curr_bed_type` e `M190 S65`. **Confirme a mesa instalada na impressora.** |
| P0-03 | `teste_folgas.py`: os cilindros não eram deslocados, e os 5 furos saíam sobrepostos. | Cupom refeito: 7 furos posicionados (+0,10 a +0,40 mm no diâmetro), rebaixos de vidro, pontos de destaque e vincos. Virou módulo importável, sem `exec()`. | O script verifica cada furo por raio (centro, fundo a 4,5 mm e diâmetro) e falha se algum não bater. |
| P0-04 | Malha vermelha final com arestas não-manifold e 108 triângulos degenerados. A checagem só avisava. | União geométrica por cor (moldura + pontos + peças da mesma cor), fusão de vértices a menos de 0,2 µm e remoção de lascas colineares por rotação de aresta. Pontos de destaque de outras cores só **encostam** (não há volumes sobrepostos entre cores). | O STL exportado é **reaberto** e validado: 0 não-manifold, 0 mal orientadas, 0 degenerados. Qualquer falha **interrompe** a geração. |

### Fidelidade (Gol 1300 L 1980)

- **Balanços corrigidos:** o dianteiro passou para ~930 mm (motor longitudinal à frente do eixo) e o traseiro para ~500 mm. Na v1 estavam invertidos.
- **Comprimento total:** 118,4 mm (3790/32). Na v1 eram 116,3 mm.
- **Bitolas:** 1350 mm na frente e 1366 mm atrás. Na v1 as duas eram 1350.
- **Tampa traseira:** ~38°, com vidro só na parte de cima e chapa vermelha embaixo.
- **Vidro lateral traseiro:** grande, com coluna C fina.
- **Para-brisa:** reposicionado conforme a lateral de referência.
- **Frente:**
  - faróis retangulares com aro prata;
  - grade preta com 6 frisos em relevo;
  - faixa vermelha entre a grade e o para-choque;
  - para-choque cromado com pontas pretas, faixa preta inferior com piscas e placa.
- **Traseira:** a placa preta genérica saiu. Entrou o painel **vermelho**, com lanternas nos cantos (faixa clara em cima, vermelho embaixo, moldura preta) e placa central com moldura.
- **Rodas:** aço prata sem calota, com aro, prato rebaixado, 8 fendas e cubo central. Pneu com 2 sulcos.
- **Vincos:** portas, friso lateral na altura da maçaneta, soleira, maçaneta e contorno do capô.
- **README:** removida a expressão errada "Gol bola" ("bolinha" é a 2ª geração, de 1994).

### Montagem

- **Eixo passante:** o eixo atravessa as duas metades e gira livre (`AXLE_BODY_EXTRA`). As rodas entram justas no eixo (`AXLE_WHEEL_EXTRA`) e a retenção axial vem das duas rodas nas pontas. Na v1 cada roda tinha um pino curto preso.
- **Folgas separadas por função:** `HOLE_EXTRA` para os pinos da carroceria, `AXLE_BODY_EXTRA`, `AXLE_WHEEL_EXTRA` e `PLATE_CLR` (por lado).
- **Pinos e eixos na montagem digital:** agora aparecem no render de raio-X e na vista explodida.
- **Peças coloridas face-up:** a frente, o painel traseiro, as rodas e a plaquinha saem com o detalhe **em cima**, em relevo. Os para-choques continuam com a face para baixo, para a face cromada sair lisa.

### Cartão e fatiamento

- **Tamanho:** o cartão tem 172 × 141 mm e fica a 4 mm da borda esquerda da mesa.
- **Torre de purga:** fica atrás, à esquerda. Não pode ficar no canto traseiro direito, que é a zona `head_wrap_detect_zone` da A1 mini.
- **Pezinho da plaquinha:** passou de 48 para 36 mm, o que eliminou uma linha do cartão.
- **Novo `fatiar.py`:** fatia o cupom e o cartão, confere o G-code (start oficial, temperatura da mesa, trajetórias dentro de 180 × 180 mm, trocas de cor reais) e grava `saida/fatiamento.json` com os hashes SHA-256.

### Pendências (não feitas nesta versão)

Ver [VALIDACAO.md](VALIDACAO.md#pendências).

## v1 — 27/09/2026 (tag `v1-nao-liberada`)

Primeiro protótipo. **Não liberado para impressão:** G-code incompatível (P0-01), mesa divergente (P0-02) e cupom com defeito (P0-03). Está preservado só no histórico do git.
