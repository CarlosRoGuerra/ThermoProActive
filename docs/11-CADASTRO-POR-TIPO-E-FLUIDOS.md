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

## 11. Alinhamento ao relatório-modelo da Midori (03/10/2026)

Comparação item a item com o modelo `2016-11-0882 - AO - Midori.pdf` e o que foi feito.

| Item do modelo | Situação | Onde |
| --- | --- | --- |
| Normas dos métodos (D6595, E2412, D2270, ISO 11171; D4951, D974, D4377, D4055) | **Cadastradas**, junto com as da especificação (D445, D664, D6304, D5185, ISO 4406). O método usado em cada valor fica em `ValorParametro.metodo` e sai na ficha; o Master desliga em Normas as que o laboratório não usa | `ensaios/0007` |
| Norma D4055 nos insolúveis em pentano | Feito | `ensaios/0007` |
| TBN (número de base) | Novo parâmetro da FQ, logo depois do TAN, informativo | `ensaios/0007` |
| Boro | Passou a **contaminante** (como no modelo: Si, Na, B, K); a ordem acompanha o grupo | `ensaios/0007` |
| Volume (L) do reservatório | Novo campo da coleta, no formulário e na ficha | `ensaios/0006` |
| Instrumentação (item 4 da carta) | Os 6 itens do modelo cadastrados em Instrumentação, **só pelo tipo**, ligados à tecnologia; marca, modelo, série e calibração são do laboratório e o Master preenche. "Validade" só sai quando há data de calibração | `ensaios/0007`, `shell/carta.tsx`, `carta_docx.py` |
| Glossário (O.S.P., GR-1 a GR-4 com prazos, MP, NM, OK, PDM, PDP; FQ, EF e CP detalhados) e considerações | Texto do modelo, em 4 folhas A4 | `ensaios/carta.py` |
| Grau de Risco | Calculado por amostra (seção 11.1) | `ensaios/grau_risco_fluidos.py` |
| Gráficos da Seção B | 5 novos, em 2 folhas A4 (seção 11.2) | `fluidos/gerenciais.tsx` |
| Diagnóstico da ficha (STATUS, GR, observações) e legenda OK / ATENÇÃO / INTERVIR | Em cada ficha de ensaio | `fluidos/fichas.tsx` |
| Observações analíticas automáticas | Geradas **só com as referências cadastradas** (um item por parâmetro fora); a conclusão continua sendo do analista | `relatorio_fluidos.observacoes_geradas` |

### 11.1 Regra do Grau de Risco (do glossário do modelo)

| GR | Quando | Prazo |
| --- | --- | --- |
| GR-1 | anomalia vista a olho nu — decisão do inspetor, marcada como a **condição** do equipamento na folha de campo | 3 dias |
| GR-2 | anomalias em mais de 2 ensaios | 30 dias |
| GR-3 | anomalias em 2 ensaios | 60 dias |
| GR-4 | anomalia em 1 ensaio | 90 dias (parada programada) |
| OK / GR-0 | nenhum ensaio com anomalia | nova inspeção em até 3 meses |

"Anomalia" = ensaio (FQ, EF ou CP) com algum parâmetro em Alerta ou Crítica pelas referências **cadastradas**. Ensaio sem referência não conta; se nenhum ensaio pôde ser avaliado, não há GR. O modelo diz "em até 02 ensaios" (GR-3) e "apenas 01" (GR-4): interpretado como exatamente 2 e exatamente 1. O GR **não substitui** Rotina/Alerta/Crítica — os dois aparecem.

### 11.2 Gráficos gerenciais (Seção B)

Status das Condições (GR), dos Componentes (tipo do equipamento) e das Anomalias (parâmetros fora da referência; no CP, o código ISO 4406); Graus de Risco por mês (o pior GR do equipamento no mês); Equipamentos monitorados × anomalias por mês; Controle das O.S.P.'s. Os meses vêm das coletas anteriores de cada equipamento, **avaliadas pelas referências da época**.

Controle das O.S.P.'s — derivado, nada é digitado: compara cada equipamento com a coleta anterior. **Aberta** = anomalia nova; **Corrigida** = tinha anomalia e voltou ao normal; **Reincidente** = a anomalia continua; **Não reavaliada** = tinha anomalia e não foi avaliada neste ciclo. A coluna "Ret. Inf." do modelo (retorno de informação do cliente) **não existe**: exige um registro que o sistema ainda não tem.

### 11.3 Exemplos no sistema local

- Relatório 24 (http://localhost:3100/relatorios-inspecao/24): 7 equipamentos em 3 campanhas (jul, ago e out/2026) com todos os graus (OK, GR-1 a GR-4) e as amostras 201-COA-012 e 301-COA-001 com os números do PDF. Script: criado pelas APIs do app.
- Relatórios 20 e 21: exemplos anteriores (compressor/unidade hidráulica e teste prático).

### 11.4 Pendências desta etapa

Resolvidas na seção 12 (respostas de 07/10/2026): instrumentação, Ret. Inf. (abortado) e
GR na Seção C. Os limites de ferro, silício, TAN etc. continuam dependendo de referência.

## 12. Respostas do responsável técnico (07/10/2026)

| # | Resposta | O que foi feito |
| --- | --- | --- |
| 1 | Análise trimestral: coletas mensais (ex.: 60 amostras/trimestre = 20/mês); no mês só se enviam as fichas com desvio; no fim do trimestre, o relatório com todas as amostras e a data final do trimestre. Prazos do GR: os da carta | O trimestre é **um relatório** (1ª coleta gera o número com a data final do trimestre; as dos meses seguintes usam "Utilizar outro número"). Na tela do relatório, o painel **Envio mensal — fichas com desvio** lista cada coleta (amostras e desvios) e gera o PDF só das fichas com GR-1 a GR-4 (`/imprimir/<id>?carregamento=<rota>&somente_desvios=1`, dossiê com o mesmo filtro). Mês sem desvio: "Sem envio neste mês". Mesmo equipamento em meses diferentes do trimestre: o mês anterior vira histórico do seguinte, nunca o contrário |
| 2 | Não entendeu a pergunta | Feito como no modelo: a Seção C dos fluidos mostra o **GR calculado** de cada amostra (OK, GR-1…GR-4) no lugar da condição marcada em campo (sem GR, fica a de campo). Confirmar com exemplo (mensagem de retorno) |
| 3 | Manter as duas listas de normas | Mantidas |
| 4 | Viscosidade ±20% do grau ISO VG da amostra; água máx. 2%; TAN (texto incompleto) | Referências **gerais** (todos os clientes), origem "Critério do responsável técnico": viscosidade a 40 °C = variação com **base no grau ISO VG do fluido da coleta** (novo campo `ReferenciaParametro.base_grau_iso`; "ISO VG 68" → 68 cSt), crítico ±20%; água máx. 20.000 ppm (2%) crítico. Sem alerta (não informado). TAN: aguardando o resto do texto |
| 5 | Ret. Inf. — aborta | Não implementado |
| 6 | Laboratórios parceiros já cadastrados | Os laboratórios ("LFxx - Laboratório de Fluídos" em Instrumentação) ficam disponíveis nas tecnologias de fluidos e de óleo isolante; o analista escolhe no laudo e a carta (item 4) e a ficha mostram o escolhido. Os 6 instrumentos genéricos criados em 03/10 foram removidos (sem uso). "Validade" da calibração só sai com data |
| 7 | ISO 10816 substituída pela ISO 20816; até 15 kW crítico > 4,5; 15–300 kW Grupo 2 crítico > 7,1; > 300 kW Grupo 1 crítico > 11,0; nenhuma máquina sem classe | Novos grupos `G2` e `G1` (`ClasseISO`), regra pela potência (≤ 15 kW Classe I; ≤ 300 kW Grupo 2; > 300 kW Grupo 1, qualquer base). Critérios a partir de **07/10/2026**: Grupo 2 = 2,30 / 4,50 / 7,10 e Grupo 1 = 3,50 / 7,10 / 11,00 mm/s — o crítico é o informado; A/B e B/C são da mesma coluna da ISO 20816-3 (fundação flexível), origem "Critério do responsável técnico", com nota na carta. Classes II–IV encerradas em 06/10/2026 (relatórios antigos não mudam; medições gravadas guardam a zona da época). Equipamentos reclassificados pela potência (sem potência: II → Grupo 2; III/IV ficam para revisão). Cadastro exige o grupo em toda máquina avaliada por vibração (o motor recebe pela potência) |
| 8 | Outros modelos depois | — |
| 9 | Tensão: nominal 13,8 kV, TAP em 11,4 kV; C₂H₂ = 0 confirmado; PCB pela NBR 13882 | Os dados do TRF-001 já estavam assim (datasheet 13,8 kV; TAP 11,4 kV no registro). PCB: limite de 50 mg/kg já era o do catálogo; "< LD" atende; nota da ficha com as faixas (> 50 contaminada; 2–50 sob controle; < 2 não detectado) |

Migrações: `cadastros/0032` (escolhas), `0033` (critérios e reclassificação), `ensaios/0008`
(`base_grau_iso`, origem nova), `0009` (referências gerais, laboratórios, nota do PCB). Todas
reversíveis (testadas em ida → volta → ida).

Exemplo local: **relatório 25** — trimestre jul–set/2026 com 3 coletas mensais na mesma
numeração (julho e setembro com desvio, agosto sem), laboratório LF01 nos laudos.

### 12.1 Em aberto

1. TAN: o texto da resposta chegou cortado.
2. Vibração em base rígida: a ISO 20816-3 é mais rigorosa (Grupo 2 crítico > 4,5; Grupo 1 > 7,1). Confirmar que a coluna da fundação flexível vale para todas as máquinas.
3. Equipamentos com Classe III/IV sem potência cadastrada: escolher o grupo no cadastro.
4. Confirmar a Seção C com o GR (pergunta 2 refeita com exemplo).
