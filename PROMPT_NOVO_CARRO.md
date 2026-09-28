# Prompt para um carro novo

Abra este repositório no **Claude Code**, preencha os campos abaixo e cole o bloco inteiro na conversa. As regras técnicas já estão no `CLAUDE.md`, que o Claude lê sozinho.

---

```text
Quero um novo carro no molde de kit card deste repositório.

CARRO
- Modelo e versão exata: ______________________ (ex.: "VW Fusca 1300 1972", "Chevette SL 1983")
- Carroceria: [ ] fechada  [ ] conversível/aberta  [ ] picape  [ ] outra: ________
- Cor da carroceria: ______ (o AMS tem vermelho, preto, prata e branco; outra cor = trocar a bobina 1)
- Texto da plaquinha: ______________________ (ou "nome genérico")

REFERÊNCIAS (quanto mais, melhor)
- Fotos/links: ______________________________________________
  (ideal: lateral bem de lado, frente, traseira, 3/4, detalhe das rodas)
- Exemplar específico, se houver: ___________________________

PREFERÊNCIAS
- Escala: 1:32 (padrão; outra escala só com justificativa)
- Detalhes que não podem faltar: ______________________________
- Detalhes que podem ficar de fora: ___________________________

O QUE EU ESPERO
1. Siga o fluxo do CLAUDE.md: pesquise, registre as fontes em carros/<pasta>/referencias.csv
   e escolha a arquitetura (A duas metades / B inteiriça em pé), explicando por quê.
2. Primeiro me mostre a FORMA (render 3/4 + lateral ortográfica + traseira) e espere eu aprovar.
3. Depois dos detalhes, rode .\gerar.ps1 <pasta> até tudo passar nos portões.
4. Documente (README e VALIDACAO do carro, README geral, CHANGELOG) e suba numa branch com PR.
5. Me diga tempo, filamento e trocas de cor (estimativas do fatiador), o que ficou de fora e o que depende de impressão física.
```

---

## Dicas para boas referências

- **Lateral pura** é a foto mais útil: dela saem os balanços, o para-brisa, o teto e a traseira.
- **Frente e traseira bem de frente** servem para faróis, grade, lanternas e para-choques.
- **Ano e versão importam:** o mesmo modelo muda muito entre reestilizações.
- Fotos de fabricantes, museus (ex.: Garagem VW) e anúncios de carros originais são melhores que carros modificados.
