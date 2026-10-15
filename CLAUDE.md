# CLAUDE.md — Molde de miniaturas em Kit Card

Este repositório gera **miniaturas de carros em kit card**: todas as peças saem presas numa moldura, na **Bambu Lab A1 mini + AMS lite** (4 cores), e o cliente destaca e monta.

Cada carro é uma pasta em `carros/`. O motor comum fica em `kitcard/`. Para fazer um carro novo, siga o **Fluxo** abaixo. O pedido do dono chega pelo `PROMPT_NOVO_CARRO.md`.

Idioma: responda e documente em **português do Brasil**.

## Estrutura

```
kitcard/fabricacao.py   folgas, mesa, cartão, cores do AMS — COMUNS a todos os carros (calibradas pelo cupom)
kitcard/nucleo.py       geometria, booleanos Manifold, Part, cartão, pontos de destaque,
                        exportação por cor + validação do STL reaberto, renders, gerar(mod)
kitcard/gerar.py        blender -b --factory-startup --python-exit-code 1 -P kitcard/gerar.py -- <carro>
carros/<carro>/modelo.py        o carro: referência (mm reais), carroceria, peças, build_parts()
carros/<carro>/referencias.csv  fontes, com o que foi usado de cada uma e o nível de confiança
carros/<carro>/README.md        decisões, peças, montagem e pendências do carro
carros/<carro>/VALIDACAO.md     o que foi verificado, em que nível
carros/<carro>/saida/           gerado: STLs por cor, kitcard_A1mini.3mf, renders, cartao.json, fatiamento.json
calibracao/cupom.py             cupom de folgas (imprimir 1x; valores vão para kitcard/fabricacao.py)
bambu_perfis.py                 extrai os perfis oficiais da A1 mini (inherits + include) e confere o G-code
fatiar.py <carro>|cupom         fatia numa pasta temporária curta e verifica o G-code
gerar.ps1 <carro>|cupom         faz tudo em sequência e para em qualquer falha
```

**Carros de referência. Antes de modelar, copie o mais parecido:**

| Carro | Arquitetura | Quando usar |
|---|---|---|
| `carros/gol_1980` | **A: duas metades** deitadas na face de corte, vidros em rebaixos, 3 pinos | carros **fechados** (com teto). Não tem balanço nenhum |
| `carros/puma_gts` | **B: carroceria inteiriça em pé**, cockpit aberto para cima, interior encaixado | **conversíveis**, picapes, abertos. Com duas metades, o cockpit viraria balanço |

## Interface de um carro (`carros/<carro>/modelo.py`)

- `from kitcard.nucleo import *`
- **Constantes:**
  - `OUT` (pasta `saida`), `NAME_TEXT`, `LEN_MM`, `HEIGHT_MM` (para as câmeras) e `S` (escala, padrão 1/32);
  - opcional: `KEEP_ORIENT` (prefixos de peças que não giram no cartão).
- **Função:** `build_parts()` → lista de `Part`. Cada `Part` tem:
  - a lista de `(objeto, cor)`;
  - `down=` (vetor da face que vai apoiada na mesa, em coordenadas do carro) **ou** `asm=` (matriz impressão→carro);
  - `explode=` (deslocamento na vista explodida).
- **Coordenadas do carro:**
  - x = frente → trás (0 na frente da carroceria);
  - y = esquerda (+) / direita (−);
  - z = chão para cima.

  Referência em **mm reais**; multiplique por `S` para ter mm impressos. Folgas e espessuras de `fabricacao.py` já estão em **mm impressos**. Não escale esses valores.

## Fluxo para um carro novo (com pontos de aprovação)

1. **Identificar a versão exata** (ano, versão, carroceria). Não misture fases: reestilizações mudam faróis, lanternas, para-choques e rodas.
2. **Pesquisar e registrar em `referencias.csv`:**
   - URL, origem, ano/versão, vista, o que foi usado, confiança, divergências e restrição de uso.
   - Medidas: comprimento, largura, altura, entre-eixos, bitolas, aro/pneu. Ficha técnica é fonte secundária; declare a incerteza.
   - Proporções a partir de fotos: balanços, base e topo do para-brisa, colunas, linha de cintura, pontos altos dos para-lamas. **Foto em perspectiva não é desenho ortogonal.** Use a roda (tamanho conhecido) como régua e desconfie de alturas quando a câmera está alta.
   - Fotos de terceiros **não** entram no repositório.
   - Para ver imagens: o navegador do app exibe a imagem dentro da própria página (`document.body.innerHTML = '<img ...>'`). Ampliar com `transform`, não com scroll.
3. **Escolher a arquitetura (A ou B)** e justificar no README do carro.
4. **Modelar a forma sem detalhes. Gerar e mostrar ao dono:** render 3/4, **vista lateral ortográfica** e traseira. ⏸ **Aprovação da forma**: o dono precisa reconhecer o carro pela silhueta.
5. **Detalhes:**
   - frente, traseira, vidros e rodas (a roda certa faz muita diferença);
   - vincos: portas, capô, tampa;
   - piscas, placas, frisos.
6. **Gerar:** `.\gerar.ps1 <carro>`. Tudo tem que passar (ver Portões).
7. **Documentar:** README do carro (decisões, peças, montagem, limitações), VALIDACAO.md e referências. Atualize o README geral (galeria) e o CHANGELOG.
8. **Entregar numa branch com PR.** Não mexer na `main` sem aprovação. Nunca dizer "pronto para vender" sem impressão física.

## Portões (automáticos — o processo PARA se falhar)

- **Perfis:** G-code de máquina idêntico aos templates oficiais da A1 mini (`bambu_perfis.py`).
- **Malhas:**
  - cada cor é unida num sólido;
  - o STL é **reaberto** e precisa ter 0 arestas não-manifold, 0 mal orientadas e 0 triângulos degenerados;
  - o cartão precisa caber na mesa.
- **Cartão:** altura ≤ `CARD_MAX_H` (141 mm), para a torre de purga caber atrás.
- **Fatiamento:**
  - start G-code com 334/334 linhas fixas do template oficial;
  - mesa Textured PEI a `M190 S65`;
  - trajetórias com extrusão dentro de 180 × 180 mm.

## Regras de projeto (aprendidas — não repetir os erros)

**Impressão sem suporte:**
- **A:** metades deitadas na face de corte, com a superfície externa como campo de alturas.
- **B:** peça em pé. Cavidades abertas para cima; recolhimentos e chanfros ≤ 45° da vertical; furos horizontais em **gota** (`teardrop_hole_y`).

**Cores e trocas (custo):**
- Cada camada com duas cores custa pelo menos uma troca de filamento.
- **Peças altas de outra cor multiplicam as trocas.** Deite ou divida. No Puma, os encostos em pé davam 120 trocas; deitados, 50.
- **Detalhes coloridos:** face-down, para o acabamento liso da mesa (ex.: cromado dos para-choques do Gol), ou face-up com relevo (faróis, lanternas, rodas). Mantenha as faixas de cor nas mesmas alturas entre as peças.
- **4 cores fixas no AMS:** 1 vermelho, 2 preto, 3 prata, 4 branco. Uma 5ª cor (ex.: âmbar dos piscas) não existe; documente a limitação.

**Booleanos:**
- Nunca deixe faces **coplanares** entre cortador e peça: o cortador deve passar da face (ex.: lente do farol do Puma).
- Os cilindros de furos não devem ter vértices alinhados com os de outro corte. Use `phase=` e contagem de segmentos diferente.
- `boolean()` do núcleo refaz o corte girando o cortador se abrir a malha, mas conserte a causa.

**Vincos:** não termine um vinco em cima de uma quina (ex.: borda do cockpit); pare antes.

**Encaixes:** cada função tem sua folga (`fabricacao.py`):
- pino justo (`HOLE_EXTRA`);
- eixo que gira (`AXLE_BODY_EXTRA`);
- roda na pressão (`AXLE_WHEEL_EXTRA`);
- placa em rebaixo, **por lado** (`PLATE_CLR`).

Os eixos são **passantes**: a roda fica justa em cada ponta e segura o eixo. Pinos e eixos aparecem na montagem (raio-X).

**Cartão:**
- 172 mm de largura; altura máxima de 141 mm.
- Se passar da altura, o gerador lista as linhas. Reduza a peça que ocupa uma linha sozinha.
- Plaquinha: `make_nameplate(NAME_TEXT, H=12)` quando faltar espaço.

**Fatiamento:**
- **Torre de purga:** fica atrás, à esquerda do cartão. O canto traseiro direito (x>156, y>152) é a zona `head_wrap_detect_zone` da A1 mini. Na linha de comando, o Bambu reserva ~35 mm para a torre.
- **Sem brim automático.**
- **Perfis:** gerados por `bambu_perfis.py`. Nunca "achatar" perfis sem resolver `include`: foi assim que a v1 do Gol saiu com G-code de outra impressora.

**Windows:**
- Caminhos acima de 260 caracteres quebram o Blender e o Bambu Studio.
- Pastas de carro com **nome curto** (≤ 10 caracteres, ex.: `puma_gts`).
- `fatiar.py` já trabalha numa pasta temporária curta.
- Rode o Blender com `--python-exit-code 1`, senão erros de Python não interrompem o `gerar.ps1`.

**Honestidade:**
- Registre em que nível cada coisa foi verificada: **código**, **malha**, **fatiador** ou **físico**.
- Tempos e pesos do fatiador são **estimativas**.
- Marca e logo: não modele emblemas; avise sobre marca registrada e sobre o enquadramento no Inmetro antes de vender.
