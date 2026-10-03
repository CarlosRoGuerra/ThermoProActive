# Cadastro técnico por tipo, fim do fallback da vibração e Análise de Fluidos

Especificação de 30/09/2026 (36 seções), com os PDFs de referência
RT.TE-2026.02.12.02307 (termografia), 2016-11-0882 (AO Midori, óleo lubrificante) e
2025-12_TRF-001 (óleo isolante). Implementado em 01/10/2026. Complementa o
[doc 10](10-ARQUITETURA-RELATORIO-MODULAR.md) (shell + módulos).

## 1. Causa raiz do problema do transformador

1. O formulário de equipamento escolhia os dados técnicos por `categoria_tecnica` do
   tipo, mas **tipo sem categoria caía no bloco genérico de motor** (potência kW, RPM,
   FP, Classe ISO). No banco de produção o tipo "Transformador" estava sem categoria,
   então o transformador recebia ficha de motor.
2. Mesmo com categoria, o bloco "Classe ISO" ficava fora do datasheet e aparecia para
   qualquer tipo.
3. No relatório, tecnologia com `modulo_tecnico` vazio caía no **módulo padrão**, que
   era o layout da vibração (tabela ISO‑10816 na carta, amplitudes na OSP).

## 2. Cadastro técnico por tipo de equipamento

- **Quem decide é o catálogo**: `TipoEquipamento.categoria_tecnica` (datasheet) e o novo
  `TipoEquipamento.analise_vibracao` (o tipo é avaliado por severidade de vibração).
  Nenhuma regra em tempo de execução olha o nome do tipo.
- Formulário (`equipamento-form.tsx`) em quatro seções: **Localização**,
  **Identificação**, **Classificação operacional** (criticidade) e **Dados técnicos**
  (só o datasheet da categoria). Severidade de vibração aparece só quando
  `analise_vibracao`. Tipo sem categoria mostra aviso de onde configurar e nenhum campo
  de motor.
- Backend valida, sem confiar no front:
  - datasheet de outra categoria é recusado (`_DatasheetSerializer`);
  - `classe_iso` é limpa em tipos que não são avaliados por vibração;
  - catálogo: transformador não pode ter `analise_vibracao`; a categoria não pode ser
    trocada se já existem equipamentos com datasheet da categoria antiga.
- Campos legados do `Equipamento` (`potencia_kw`, `rpm`, `tensao_nominal`,
  `fator_potencia`…) continuam no banco e sincronizados pelo datasheet de motor — o
  Balanceamento/Economia lê deles (seção 8). Em tipo sem categoria aparecem só como
  leitura, quando já preenchidos.
- **Migração `cadastros/0029`** (só preenche o que está vazio, nada é apagado):
  categoria por **evidência** (equipamentos do tipo já têm datasheet de uma só
  categoria) ou por **nome exato** de uma lista fechada ("Transformador",
  "Motor elétrico"…) — uma decisão registrada uma vez, a mesma que o Master tomaria no
  catálogo. `analise_vibracao` só com evidência (categoria motor, ou tipo já medido em
  rota de vibração, balanceamento ou medição antiga); transformador nunca.

## 3. Fim do fallback da vibração

`TecnologiaAnalise.modulo_tecnico` é a única fonte. Resultado:

| Situação | Antes | Agora |
| --- | --- | --- |
| Módulo explícito implementado | módulo correto | módulo correto |
| Inspeção genérica deliberada | layout da vibração | `INSPECAO_GENERICA`: OSP sem amplitudes, carta sem tabela ISO, glossário neutro |
| Balanceamento | layout da vibração (por acaso) | `BALANCEAMENTO`: o mesmo layout, por escolha declarada (o serviço mede vibração) |
| Módulo vazio | layout da vibração | aviso "tecnologia sem módulo técnico" — HTTP 409 no dossiê, no PDF e na carta .docx; tela mostra a mensagem |
| Módulo planejado (alinhamento, TC/TP/DJ…) | layout da vibração | aviso "módulo ainda não implementado" (HTTP 409) |

Backend: `relatorio_tecnico/modulos.py` (exceções `ModuloNaoConfigurado`,
`ModuloNaoImplementado`), `generico.py`, `coletas/views.py` (`_modulo_indisponivel`).
Front: `modulos/index.ts` sem padrão, `shell/documento.tsx` (`SemModulo`),
`lib/inspecoes.ts` (`tecnologiaTipo(modulo)` — Análise Final e modal só tratam como
vibração o que é `VIBRACAO`).

Migrações `cadastros/0030` (novas opções) e `0031` (associação das tecnologias que caíam
no padrão, só onde vazio). No banco local: ASSE → `INSPECAO_GENERICA`; BALDC e BALT →
`BALANCEAMENTO`; AFLH → `FLUIDO_LUBRIFICANTE`; ALEE → `ALINHAMENTO_EIXOS` (planejado).
**Ficaram vazias, à espera do Master**: AECME, AFMME, AQEN, ARIMEG, SIRM, TNMT — os
relatórios delas avisam em vez de sair com conteúdo de vibração.

## 4. Perfil normativo da vibração

Novo `CriterioSeveridadeVibracao` (Cadastros → Critérios de severidade de vibração,
`/api/criterios-vibracao/`, só equipe interna lê, só Master altera): norma, edição,
classe/grupo, tipo de suporte, limites A/B, B/C, C/D, **origem** (`NORMA`,
`ACORDO_CLIENTE`, `LEGADO`), fonte, cliente (vazio = global) e vigência.

Precedência (`cadastros/criterios.py`, `criterio_vigente`): critério do cliente >
global; `ACORDO_CLIENTE` > `NORMA` > `LEGADO`; vigência mais recente. Classificação da
rota (`classificar_vibracao`), do balanceamento (`avaliar_ponto`), da medição antiga e a
tabela da carta (PDF e .docx) leem daqui. Sem critério cadastrado, usam
`FAIXAS_ISO_VRMS` (LEGADO) — o número não muda em silêncio.

A carta passa a dizer de onde vem cada limite. Ex.: *"Classe II: limite
Satisfatório/Alerta de 4,49 mm/s (a ISO 10816-1:1995 publica 2,80 mm/s) — por acordo com
o cliente."* O 4,49 nunca é apresentado como ISO.

### 4.1 Auditoria da vibração

| Regra | Valor no sistema | Classificação | Ação |
| --- | --- | --- | --- |
| Faixas Classe I | 0,71 / 1,80 / 4,50 mm/s | NORMA — ISO 10816-1:1995, Anexo B | Cadastrada com edição e fonte |
| Faixas Classe II | 1,12 / **4,49** / 7,10 mm/s | **CUSTOMIZADO** — B/C da norma é 2,80; 4,49 confirmado com o cliente em 16/09/2026 | Cadastrado como `ACORDO_CLIENTE` (prevalece; classificação inalterada) + o critério da norma ao lado; nota na carta |
| Faixas Classe III | 1,80 / 4,50 / 11,20 mm/s | NORMA — ISO 10816-1:1995 | Cadastrada |
| Faixas Classe IV | 2,80 / 7,10 / 18,00 mm/s | NORMA — ISO 10816-1:1995 | Cadastrada |
| Edição da norma | ISO 10816-1:1995 | LEGADO — substituída pela ISO 20816-1:2016; máquinas industriais em campo: ISO 10816-3 → ISO 20816-3:2022 | **Não alterado.** Adotar a edição atual é decisão técnica do responsável: novo critério com vigência; o histórico continua com o critério da época |
| Classe pela potência (≤15 kW I; 15–75 II; >75 III/IV pela base) | `cadastros/rules.py` | NORMA (grupos da 10816-1) | Mantida; só para tipos com `analise_vibracao` |
| Equipamento sem classe | usa as faixas da Classe II | LEGADO | Mantido para não mudar laudos; agora o diagnóstico avisa "classe não definida" |
| Zona → criticidade (A/B → rotina, C → alerta, D → crítica) e regra de evolução | `coletas/rules.py` | CUSTOMIZADO (procedimento do cliente, itens 2.4.1.x) | Mantido |
| Tabela da carta | texto fixo | LEGADO | Passa a sair dos critérios vigentes, com nota da origem |

## 5. Análise de Fluidos Lubrificantes e Hidráulicos

Módulo `FLUIDO_LUBRIFICANTE`, sobre o **mesmo motor de ensaios** do óleo isolante
(`Ensaio` / `ParametroEnsaio` / `ResultadoEnsaio` / `ValorParametro`), separado por
`Ensaio.modulo` — o FQ de fluidos não é o FQ do óleo isolante.

### 5.1 Entidades novas (`apps/ensaios`)

| Entidade | Para quê |
| --- | --- |
| `ProdutoFluido` | Fluido cadastrado: fabricante, aplicação, grau ISO VG, viscosidades e IV do óleo novo |
| `ColetaFluido` (1‑1 com o item da rota) | Registro da amostra: aplicação, produto ou fluido informado, identificação, data, amostrador, ponto, temperaturas, condição operacional, horas do equipamento e do fluido, última troca, complemento, troca de filtro, intervenção, ensaios solicitados |
| `SolicitacaoPadraoEnsaio` | Regra acordada e editável: lubrificante → FQ + EF; hidráulico → FQ + EF + CP |
| `ReferenciaParametro` | Referência por parâmetro: tipo (máximo, mínimo, variação sobre o óleo novo, meta ISO 4406, qualitativo), alerta e crítico, escopo (equipamento, fluido, cliente, aplicação), origem (norma, fabricante do equipamento/fluido, laboratório, contrato, óleo novo), fonte e vigência |
| Campos novos | `PontoColeta.modulo`, `ParametroEnsaio.simbolo/grupo`, `ResultadoEnsaio.laboratorio`, `ValorParametro.metodo`; `Ensaio` único por (módulo, sigla) |

### 5.2 Catálogo (migrações `ensaios/0003`–`0005`)

- **FQ** — viscosidade a 40 °C e 100 °C (ASTM D445), IV, água (ASTM D6304), TAN
  (ASTM D664), densidade, oxidação, insolúveis, cor (ASTM D1500), aparência.
- **EF** — 21 elementos em ppm (ASTM D5185), agrupados em desgaste, contaminantes e
  aditivos.
- **CP** — contagens > 4, 6, 14, 21, 38 e 70 µm(c)/mL, classe NAS 1638 (informada pelo
  laboratório) e o código ISO 4406 calculado.
- Normas no catálogo (item 5 da carta): ASTM D445, D664, D6304, D5185, ISO 4406 — como
  **método**, sem limite.
- **Nenhum limite universal**: todos os parâmetros são informativos até haver uma
  referência cadastrada (teste `test_nenhum_limite_universal_no_catalogo`).

### 5.3 Regras

- **ISO 4406:2021** (`calculos_fluidos.py`): escala pela tabela da norma (limite
  superior de cada grau, > 28 acima de 2 500 000/mL); código X/Y/Z de > 4/6/14 µm(c).
  Contagem faltando → sem código (não inventa). Comparação com a meta em graus de
  excesso, só se houver meta cadastrada.
- **Classificação ROTINA / ALERTA / CRÍTICA** (`classificar`) só com o limite que a
  referência tem; sem ele, "sem referência" — nunca rotina por omissão. Abaixo do LD/LQ
  atende a um máximo. Variação calcula o % sobre o óleo novo.
- **Referência aplicada** (`ResolvedorReferencias`): entre as ativas e vigentes na data
  da coleta, a mais específica — equipamento > fluido > cliente > aplicação; empate, a
  vigência mais recente.
- **Situação do ensaio**: Realizado, Aguardando resultado, Amostra não coletada, Não
  realizado.
- **Tendência**: variação sobre a coleta anterior e a primeira, por parâmetro.
- CP num lubrificante é permitida quando contratada (a tela avisa), nunca marcada por
  padrão.

### 5.4 Endpoints

| Rota | Quem |
| --- | --- |
| `GET /api/ensaios/?modulo=FLUIDO_LUBRIFICANTE` (com `padrao_em`) | autenticado |
| `/api/parametros-ensaio/` (leitura) | autenticado |
| `/api/produtos-fluido/`, `/api/solicitacoes-padrao-ensaio/` | catálogo (Master edita) |
| `/api/referencias-parametro/` | só equipe interna; só Master altera |
| `/api/coletas-fluido/`, `/api/resultados-ensaio/` | interno edita; cliente só lê o que é seu |
| `/api/fluidos-inspecao/` | fila do lançamento, por cliente |
| `/api/fluidos-historico/?equipamento=` | histórico por equipamento; portal só vê relatório finalizado do próprio cliente |

### 5.5 Telas

- Cadastros: Fluidos lubrificantes/hidráulicos, Ensaios padrão por aplicação,
  Referências dos parâmetros, Critérios de severidade de vibração.
- Folha de campo: a coleta de fluido abre o `EditorFluido` (aplicação marca os ensaios
  padrão).
- Análise Final → aba **Ensaios de fluidos** → `/inspecoes/final/fluido/[id]`: coleta e
  laudos FQ/EF/CP com a classificação ao vivo.
- Relatório (`modulos/fluido.tsx`): shell comum (capa, carta, equipamentos) + KPIs
  próprios (amostras, ensaios solicitados/realizados/pendentes, parâmetros em alerta,
  críticos e sem referência, limpeza dentro/fora da meta, próxima coleta) + fichas por
  amostra com tendência em pequenos múltiplos. Carta sem nenhum conteúdo de vibração.
- Portal: **Análise de fluidos** (`/portal/fluidos`) — histórico por equipamento.

### 5.6 Exemplo local

Relatório 20 (AFLH) criado pelas APIs: redutor (lubrificante, FQ + EF) e unidade
hidráulica (FQ + EF + CP), com histórico de duas coletas. Conferido em 20 folhas A4 sem
estouro.

## 6. Óleo isolante × PDF TRF-001

Valores, normas, referências, gráfico de %, TG 60.044, TGC 544, inspeção visual
(12 OK + 8 N/A) e 2-FAL "não coletada" conferem com o PDF. Pontos em aberto:

- tensão primária 11,4 kV no sistema × 13,8 kV no PDF (dado do cadastro);
- referência de C₂H₂ = 0 (qualquer traço vira alerta) — confirmar com o cliente;
- PCB: referência 0,5 ppm abaixo do LD do laboratório (2,0 ppm) — "não detectado" não
  prova atendimento;
- gráficos com um eixo por grandeza (correto); o PDF mistura escalas;
- texto da carta (proposta) aguarda validação.

## 7. Balanceamento

Sem reescrita. O módulo de relatório agora é declarado (`BALANCEAMENTO`); a avaliação
dos pontos usa o perfil normativo. A Economia lê `tensao_nominal` e `fator_potencia` do
`Equipamento` (sincronizados do datasheet de motor); em tipo sem categoria, aceita
digitação manual quando falta o dado.

## 8. Validação

- Backend: 251 testes OK (novos: `ensaios/test_fluidos.py` 29,
  `cadastros/test_categoria_vibracao.py` 12, 7 em `coletas/test_relatorio_tecnico.py`).
- e2e: 37 OK (novos: `cadastro-equipamento`, `coleta-fluido`, `relatorio-fluidos`).
- `makemigrations --check` limpo; migrações testadas em ida → volta até
  `cadastros 0027` → ida.
- Relatórios já existentes (termografia, óleo, elétricos) idênticos antes/depois;
  vibração/balanceamento mudam só a tabela da carta (agora com a nota da origem).

## 9. Pendências reais

1. Master definir `modulo_tecnico` de AECME, AFMME, AQEN, ARIMEG, SIRM, TNMT e
   `analise_vibracao` dos tipos rotativos sem evidência.
2. Cadastrar as referências de fluidos (fabricante/contrato/laboratório) — até lá, os
   laudos saem "sem referência".
3. Decidir a edição da norma de vibração (10816 × 20816) e o tratamento de equipamento
   sem classe.
4. Pontos do óleo isolante da seção 6.
5. ESLint não configurado no front (`next lint` pede configuração interativa).

## 10. Próxima tecnologia recomendada

**Alinhamento de eixos** (`ALINHAMENTO_EIXOS`): já existe no catálogo (ALEE), já está
associada ao módulo planejado e hoje mostra o aviso de "não implementado". Reaproveita
o padrão do Balanceamento (serviço de campo, antes/depois, economia) e o perfil
normativo (tolerâncias por rotação, com origem e vigência).
