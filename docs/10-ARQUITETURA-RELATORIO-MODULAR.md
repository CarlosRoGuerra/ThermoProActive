# Relatório técnico modular — shell comum + módulos por tecnologia

Depois da Termografia, o sistema vai receber dois módulos de transformadores: **análise
de óleo isolante** e **ensaios elétricos**. Eles não se misturam com a Termografia,
mas usam a mesma estrutura de relatório. A pedido do cliente (especificação de
24/09/2026), o relatório foi separado em um **shell comum** e **módulos técnicos**,
para que uma tecnologia nova entre criando só a sua parte, sem reescrever capa, carta,
KPIs, relação de equipamentos, paginação, PDF e portal.

A primeira etapa (seções 1 a 9) fez a separação e analisou os PDFs de referência dos
transformadores (seção 7). A segunda etapa (seção 10, 25/09/2026) implementou os dois
módulos de transformador sobre esse shell — **óleo isolante** e **ensaios elétricos** —
e criou no sistema local o exemplo TRF-001 dos PDFs.

## 1. Sequência do relatório e quem responde por cada parte

```
CAPA → CARTA AO CLIENTE → KPIs → EQUIPAMENTOS MONITORADOS → FICHAS TÉCNICAS → CONCLUSÕES
```

| Parte | Responsável | Observação |
| --- | --- | --- |
| Capa, contracapas, página A4 com timbrado | shell | `shell/folhas.tsx` |
| Carta ao Cliente — itens 1 a 8, assinatura | shell | desenho e itens comuns (`shell/carta.tsx`, `carta_docx.py`) |
| Carta — seções do relatório (3), tabela normativa (5), glossário (6), parágrafo do que foi apurado (7), considerações (8) | módulo | `ConteudoCarta` |
| KPIs — contracapa e folha | shell | |
| KPIs — quais indicadores | módulo | primitivas visuais comuns em `shell/kpis.tsx` |
| Relação de Equipamentos Monitorados | shell | a partir de `ItemInspecao` (Área → Setor) |
| Fichas técnicas (hoje: folhas de OSP) | módulo | com as próprias contracapas |
| Conclusões consolidadas | módulo, opcional | nenhum módulo usa hoje; a última página continua sendo a última OSP |
| Impressão simples, PDF (paged.js), carta avulsa | shell | rotas `/relatorios-inspecao/[id]`, `/imprimir/[id]`, `/carta/[id]` |

Regra: **o shell nunca lê dado do módulo**. O módulo pode ler dado do shell. Não há
`if tecnologia` no shell — a escolha é feita uma vez, no registro de módulos.

## 2. Como o módulo é escolhido

Pelo campo explícito **`TecnologiaAnalise.modulo_tecnico`** (`ModuloTecnico`:
`VIBRACAO`, `TERMOGRAFIA`, `OLEO_ISOLANTE`, `ENSAIO_ELETRICO`; vazio = layout padrão), editável em Cadastros → Tecnologias
de análise → "Módulo técnico do relatório". Mesmo padrão de `tipo_corretiva` e
`TipoEquipamento.categoria_tecnica`: nunca deduzido pelo nome. O nome não serve para
isso: "Análise de Fluídos Isolantes Minerais" e "Análise de Fluídos Lubrificantes e
Hidráulicos" terão relatórios diferentes.

A migração `cadastros/0026` preencheu as tecnologias existentes com a **mesma regra por
nome que o front usava** (`tecnologiaTipo`), para nenhum relatório mudar na virada. No
catálogo atual: AVSMD, AVSME e AVODS → Vibração; TI-PI, TI-SE, TI-SMD e TI-SME →
Termografia; as demais → padrão.

O backend devolve a chave em `modulo` no payload do dossiê; o front escolhe o módulo
por ela.

## 3. Backend — `apps/coletas/relatorio_tecnico/`

| Arquivo | Conteúdo |
| --- | --- |
| `__init__.py` | `montar_dossie(rel, request)`: junta shell + módulo |
| `shell.py` | `cabecalho`, `secao_c` (com `equip_monitorados`) e o `ContextoRelatorio` (itens da rota carregados uma vez, reaproveitados pelo módulo) |
| `inspecao.py` | Família "inspeção por rota": `secao_b` (KPIs), `secao_d` (folhas de OSP), textos padrão da carta (modelo Word) e o parágrafo das anomalias |
| `termografia.py` | Glossário e considerações da carta de termografia, transcritos do RT.TE-2026.02.12.02307 |
| `modulos.py` | Registro `MODULOS` e `modulo_da_tecnologia()`; módulos `VIBRACAO`, `TERMOGRAFIA`, `PADRAO` e os de transformador (`OLEO_ISOLANTE`, `ENSAIO_ELETRICO`, definidos em `apps/ensaios/relatorio.py` — seção 10) |

`RelatorioViewSet.dossie()` só chama `montar_dossie`. `carta_docx.py` ficou só com o
layout do modelo Word: pede ao módulo o conteúdo técnico e desenha as tabelas que o
módulo lista em `tabelas_normativas` (registro `TABELAS_NORMATIVAS`, hoje só
`"ISO_10816"`).

Contrato de um módulo no backend:

- `chave` — igual a `ModuloTecnico`;
- `montar(ctx) -> dict` — a parte técnica do payload (na inspeção por rota: `secao_b`
  e `secao_d`);
- `textos_carta(tecnico)` — seções, glossário, quebras de folha do glossário,
  considerações e `paragrafos` (item 7, quando o texto sai do backend: o módulo põe um
  `resumo` no que `montar` devolve); vai no payload como `carta` e é a mesma fonte da
  carta .docx (antes esses textos estavam duplicados em TypeScript e Python);
- `instrumentos_adicionais(ctx)` — instrumentação além da dos carregamentos (item 4 da
  carta; nos ensaios elétricos, um instrumento por ensaio);
- `carta_conteudo`, `carta_glossario`, `carta_consideracoes`, `tabelas_normativas` e
  `paragrafos_carta(rel)` — o conteúdo técnico da carta .docx.

Vibração e Termografia são a mesma família (`ModuloInspecaoRota`) e diferem em
`medias` (grandezas do KPI "Média dos Valores de Diagnóstico"),
`tabelas_normativas` e, na termografia, glossário, considerações e
`carta_quebras_glossario`.

## 4. Frontend — `frontend/src/features/relatorio-inspecao/`

```
tipos.ts                 payload: DossieShell (shell) + DadosInspecao | DadosTransformador
dossie.tsx               tela: impressão simples, link do PDF, painel de finalização
shell/documento.tsx      RelatorioCorpo (a sequência da seção 1) e CartaDoRelatorio
shell/folhas.tsx         capa, contracapa, página interna A4 + timbrado
shell/carta.tsx          Carta ao Cliente, itens 1–8, com os encaixes do módulo
shell/equipamentos.tsx   Relação de Equipamentos Monitorados
shell/kpis.tsx           primitivas: StatTile, GraficoDistribuicao, Medidor, paleta
shell/formato.ts         datas e números
modulos/contrato.ts      ModuloRelatorio e ConteudoCarta (tabela normativa e parágrafos do item 7)
modulos/index.ts         registro (espelho de modulos.py) e o módulo padrão
modulos/inspecao/        família inspeção por rota: KPIs, folha da OSP, parágrafo das anomalias
modulos/vibracao.tsx     amplitudes, quadros Tendência/Espectro, tabela ISO‑10816
modulos/termografia.tsx  medições do RT.TE (temperaturas, carga, corrigidas, correntes), quadro Imagem Térmica
modulos/transformador/   família transformador: peças das fichas, tabelas, gráficos, KPIs (seção 10)
modulos/oleo.tsx         registro da coleta + inspeção visual; fichas FQ, CR, PCB, 2-FAL
modulos/eletrico.tsx     registro dos ensaios; fichas R×T, R×I, R×O
corretiva-*.tsx          corpos da OSP corretiva (usados pela folha da OSP)
```

`ModuloRelatorio<D>` = `chave` + `carta(d)` + `Kpis` + `Fichas` + `Conclusoes?`, onde
`D` é o payload que o backend monta para aquela chave (`DossieInspecao`,
`DossieTransformador`); o shell e as rotas só conhecem o `DossieShell`. Na
família inspeção por rota, cada tecnologia declara só três coisas
(`TecnologiaInspecao`): o bloco de medições da OSP, os quadros de imagem da coluna
direita e a tabela normativa da carta.

Os textos da carta vêm prontos do backend em `d.carta`. Cada folha da carta é uma A4
fixa: um glossário longo continua em outra folha a partir dos termos listados em
`quebras_glossario` (termografia: 6.3).

Os módulos devolvem fragmentos: toda página precisa ser filha direta de `.print-area`,
porque a quebra de página da "Impressão simples" depende disso.

## 5. O que mudou na saída

Decisões do Carlos em 24/09/2026:

- **Tecnologia sem módulo próprio** (Sensitiva, Balanceamento, Qualidade de Energia…):
  **mantém o layout de sempre**, que é o da vibração (tabela ISO‑10816 na carta, bloco
  de amplitudes na OSP). Agora isso é uma escolha explícita do módulo padrão, não um
  acoplamento do shell.
- **Termografia**: a folha da OSP mostra a **imagem térmica** no quadro da direita, no
  lugar de Tendência/Espectro (antes a imagem térmica enviada na Análise final nunca
  aparecia). A carta da termografia não traz a tabela de severidade de vibração.
  Ainda não há relatório de termografia na produção, então nada já emitido muda.

Com o relatório de referência RT.TE-2026.02.12.02307 (mesmo dia), a termografia passou
a seguir o conteúdo do cliente:

- **Carta**: glossário 6.1–6.10 do RT.TE (T.M., T.R., ΔT, M.T.A., C.T.M., I(t), I(n),
  U(t), U(n), OSP, GR com os critérios de ΔT, IC, MP, NM, OK, PDM, PDP), em duas folhas,
  e as duas considerações do RT.TE. O 6.11 (Fluxo de Trabalho) ficou de fora: cita o
  e-MasterSys e, no modelo novo, o fluxo sai no item 7, cadastrado na tecnologia.
- **OSP**: Temp. Medida, Temp. Referência, Temp. Delta, % Carga, T. Medida Corrigida,
  T. Delta Corrigida e I(R), I(S), I(T), I(N). Valor não medido sai "—" (no RT.TE saía
  0,00). As corrigidas ficam vazias até a fórmula da C.T.M. ser definida.

Também mudou:

- O payload ganhou `modulo`, `secao_c.equip_monitorados`, `carta` e, em cada folha,
  `temperatura_medida_corrigida` e `delta_t_corrigido`. O shell passou a ler o próprio
  total de equipamentos, em vez do total dos KPIs.
- A tabela ISO‑10816 da carta em PDF usava 2,80 mm/s no limite da Classe II; agora usa
  4,49, igual ao cálculo e à carta .docx (commit `2ab0ce0`). As faixas impressas não
  mudam: nenhuma linha da tabela fica entre 2,80 e 4,49.

## 6. Como adicionar uma tecnologia com relatório próprio

Backend:

1. Nova opção em `ModuloTecnico` (+ migração de `choices`).
2. Um objeto com `chave`, `montar(ctx)`, `textos_carta()`, `paragrafos_carta(rel)` e o
   conteúdo da carta; registrado em `MODULOS` (`relatorio_tecnico/modulos.py`).
3. Se a carta tiver uma tabela normativa própria, a função que a desenha no .docx entra
   em `TABELAS_NORMATIVAS`.
4. Testes do payload e da carta (modelo: `apps/coletas/test_relatorio_tecnico.py`).

Frontend:

1. Tipos da parte técnica em `tipos.ts`.
2. Um arquivo em `modulos/` exportando um `ModuloRelatorio` (carta, KPIs, fichas e, se
   houver, conclusões).
3. Uma linha em `MODULOS` (`modulos/index.ts`) e a opção no cadastro
   (`features/cadastros/catalogos.ts`).

Nada disso toca `shell/`, `dossie.tsx`, `/imprimir`, `/carta` nem o CSS de impressão.

## 7. Transformadores — PDFs de referência × domínio atual

Referências do cliente: `2025-12_TRF-001_Óleo.pdf` (5 folhas: coleta, FQ, CR, PCB,
2‑FAL) e `2025-12_TRF-001_ENDe.pdf` (4 folhas: registro, R×T, R×I, R×O). Esta seção é
a análise da primeira etapa, mantida como registro; o que foi implementado a partir dela
está na seção 10.

### 7.1 Dados do cliente e do equipamento

| Campo no PDF | Exemplo | Onde está hoje | Situação |
| --- | --- | --- | --- |
| Cliente [CNPJ] | Novaprom Food Ingredients Ltda [02.916.265/0219-14] | `Cliente.nome`, `cnpj` | existe |
| Endereço | Av. Paulo Xavier Ribeiro, 495 - Guaiçara-SP [16.430-000] | `Cliente` (endereço) | existe |
| Contato, Departamento, Telefone, E-mail | Marcelo, PCM… | `Cliente.contato_gestor`, `departamento`, `telefone`, `email` | existe |
| Local da instalação | SE-01 - Subestação Caldeira/Kelco | `Setor` (código + nome) | existe — confirmar se é Setor ou Área |
| Identificação do equipamento | TRF-001 - Transformador Trifásico | `Equipamento.tag`, `nome` | existe |
| Número de série | 91839 | `Equipamento.numero_serie` | existe |
| Número de patrimônio | (vazio) | — | **falta** |
| Fabricante | MEGA | `Equipamento.fabricante` | existe |
| Ano de fabricação | 1996 | — | **falta** |
| Tipo de equipamento | 1- TPA Trafo de Potência | `Equipamento.tipo_equipamento` | existe |
| Tipo | TFC-500,1 | `Equipamento.modelo` | existe — confirmar |
| Potência | 500 kVA | `DadosTecnicosTransformador.potencia_kva` | existe |
| Tensão primário | 11,400 kV (óleo) / 13,8 kV (ensaios) | `tensao_primaria_v` | existe — **os PDFs divergem** |
| Tensão secundário | 380,0 / 220,0 V | `tensao_secundaria_v` (um valor) | **falta** a tensão fase‑neutro |
| Impedância | 4,49 % | `impedancia_pct` | existe |
| Tipo de ligação | DYn1 | `grupo_ligacao` | existe |
| Quantidade de óleo | 540,0 L | — | **falta** |
| Tanque de expansão | itens de checklist "exclusivos para equipamentos com tanque de expansão" | — | **falta** um indicador |

### 7.2 Dados da coleta e do registro do ensaio (não existem hoje)

- **Óleo**: temperatura da amostra (°C), temperatura ambiente (°C), umidade relativa
  (%), data da coleta, amostrador, ponto de coleta (ex.: "Dreno Inferior Lado AT"),
  tipo de fluido (ex.: "Óleo Mineral B [Paranínfico]"), ensaios solicitados (FQ, CR,
  PCB, 2‑FAL) e a inspeção visual: 20 itens em dois grupos, estados OK / NC / NA.
- **Ensaios elétricos**: TAP (5), tensão do TAP (11,4 kV), temperatura do óleo (°C),
  temperatura ambiente (°C), umidade relativa (%), data do ensaio, analista e ensaios
  solicitados (R×T, R×I, R×O).

### 7.3 Estrutura das fichas de resultado

Comum a todas: **número do laudo por ensaio** (FQ 20260109001, CR …002, PCB …003; R×T
20251226011, R×I …012, R×O …013), **criticidade** ("Rotina" — não é GR), data da
análise, data da próxima coleta/análise; ao fim, conclusão (nos ensaios elétricos,
"Observações"), recomendação e informações adicionais (nos elétricos, "Instrumentação
Utilizada", com um instrumento por ensaio). A tabela tem **uma linha por campanha**
(até 6 datas): é um histórico do mesmo transformador.

| Ficha | Conteúdo | Gráfico |
| --- | --- | --- |
| FQ | 9 parâmetros com unidade, norma, referência e tipo de limite: Viscosidade a 40 °C (cSt, NBR‑10441, 50,00 Máx.), Densidade (NBR‑7148, 0,90 Máx.), Fator de Potência a 100 °C (%, NBR‑12133, 3,00 Máx.), Índice de Neutralização (mgKOH/g, NBR‑14248, 0,30 Máx.), Teor de Água (ppm, NBR‑10710, 40,00 Máx.), Rigidez Dielétrica (kV/2,5 mm, NBR‑60156, 40,00 Mín.), Tensão Interfacial a 25 °C (dina/cm, NBR‑6234, 20,00 Mín.), Cor (NBR‑14483, sem referência), Aparência (Visual, "Límpido") | barras "% Máximo" (eixo esquerdo) e "% Mínimo" (eixo direito), linhas Ref. Máx./Ref. Mín. |
| CR | 9 gases em ppm (H2, O2, N2, CH4, CO, CO2, C2H4, C2H6, C2H2), duas normas por gás (NBR‑7070 e NBR‑7274), referência de 200,0 a 80.000,0; TG e TGC dentro da conclusão | "Valor Análise (%)" × "Valor Máx. (%)" |
| PCB | Teor de PCB (mg/kg, NBR‑13882, 50,0 Máx.) + nota "Somatória de Aroclor 1242/1254/1260 — LD = 2,0 mg/kg" | "% Máximo" × "Ref. Máx." |
| 2‑FAL | 5 compostos furânicos (mg/kg, 0,010 Máx.) e Grau de Polimerização (GP, 800,00 Mín.), NBR‑5356:7; 4 notas técnicas; exemplo com "Amostra não coletada!" | máximos e mínimos, como no FQ |
| R×T | relação nominal + 3 fases (H1‑H2/X0‑X2, H2‑H3/X0‑X3, H3‑H1/X0‑X1) com medido e erro %; erro máximo admitido ±0,5 % (ANSI NETA ATS 2009) | — |
| R×I | 13 tempos (15 s a 600 s) × 3 configurações (AT‑BT‑Massa e AT‑Massa‑BT a 5000 V; BT‑Massa‑AT a 500 V), em MΩ; linha de 60 s em destaque | 3 curvas MΩ × tempo |
| R×O | TAP + 6 pares (H1\|H2, H1\|H3, H2\|H3 em Ω; X0\|X1, X0\|X2, X0\|X3 em mΩ), cada um em Medido, Calculado e Corrigido | — |

### 7.4 `MedicaoTecnica` atende? Não, sem virar estrutura frágil

- Está ligada à `Inspecao` legada, não ao fluxo `Relatorio → Carregamento →
  ItemInspecao` de onde o relatório sai.
- `valor` é decimal obrigatório: não representa "não coletado", "não realizado",
  "abaixo do LD", "indisponível" nem resultado qualitativo ("Límpido"). Zero medido e
  ausência de amostra ficariam iguais.
- Não agrupa por ensaio: faltam laudo, datas, criticidade, conclusão, recomendação,
  informações adicionais e instrumento por ensaio.
- A referência é um número sem tipo de limite (máximo, mínimo, faixa) e sem norma por
  parâmetro.
- `grandeza` é texto livre: sem catálogo de parâmetros, o histórico entre campanhas
  depende de o texto ser digitado igual.
- R×T, R×I e R×O são séries (fases, tempos, medido/calculado/corrigido); caberiam só
  empurrando tudo para o JSON `parametros`.
- A criticidade calculada (NORMAL/ALERTA/CRÍTICO por desvio de 20 %/50 % em
  `rules_tecnicas.py`) não corresponde à metodologia dos laudos — não deve ser usada
  para óleo.

### 7.5 Menor extensão proposta (implementada na seção 10)

Reaproveita `Relatorio` (número e datas), `Carregamento` (a rota de transformadores e o
analista), `ItemInspecao` (um por transformador, com a condição que aparece na Relação
de Equipamentos), `Equipamento`, `DadosTecnicosTransformador`, `Instrumento` e `Norma`.
Assim o shell funciona sem mudança nenhuma.

Acréscimos:

1. `Equipamento`: `numero_patrimonio`, `ano_fabricacao` — dados gerais do ativo, como
   `numero_serie` e `fabricante`, que já estão lá.
2. `DadosTecnicosTransformador`: `tensao_secundaria_fase_v`, `volume_oleo_l`,
   `possui_tanque_expansao` e `tipo_fluido` (padrão para as coletas).
3. Catálogos editáveis: `TipoFluido`, `PontoColeta`, `ItemChecklistVisual` (nome, grupo,
   ordem, se exige tanque de expansão), `Ensaio` (FQ, CR, PCB, 2‑FAL, R×T, R×I, R×O —
   com rótulos da ficha e nota técnica configurável) e `ParametroEnsaio` (ensaio,
   nome, símbolo, unidade, normas, tipo de limite MAX/MIN/FAIXA/QUALITATIVO/INFORMATIVO,
   limites, referência qualitativa, casas decimais, ordem, eixo do gráfico).
4. `ColetaOleo` e `RegistroEnsaioEletrico`, 1‑para‑1 com o `ItemInspecao`: as
   condições da coleta/ensaio e os ensaios solicitados; `ChecklistColeta` com estado
   OK/NC/NA, observação e foto opcionais.
5. `ResultadoEnsaio` (item × ensaio): número do laudo, criticidade, data da análise,
   data da próxima coleta, **situação** (REALIZADO, NAO_COLETADO, NAO_REALIZADO,
   SEM_RESULTADO), conclusão, recomendação, informações adicionais, instrumento e
   origem do dado (manual, planilha, API, arquivo).
6. `ValorParametro` (resultado × parâmetro, com `serie` e `posicao` opcionais para
   fases, tempos e medido/calculado/corrigido): valor decimal **nulo quando não há
   número**, valor como recebido do laboratório (texto), **estado** (MEDIDO,
   ABAIXO_LD, ABAIXO_LQ, NAO_DETECTADO, INDISPONIVEL) e limite de detecção.

A classificação automática entra depois, parâmetro a parâmetro, a partir de
`ParametroEnsaio` — só com os critérios validados pelo cliente. Os gráficos saem
desses mesmos dados, nunca de imagem.

### 7.6 O que os números dos PDFs indicam (confirmado na seção 10.3)

- **% do gráfico** = valor ÷ referência × 100, tanto para máximos quanto para mínimos.
  FQ: 40/50 = 80,0; 0,85/0,90 = 94,4; 63/40 = 157,5 (mínimo); 24/20 = 120,0 (mínimo).
  CR: 10/200 = 5,0 … 5.000/5.000 = 100,0. PCB: 0,5/50 = 1,0. O acetileno tem
  referência 0,0: a divisão não existe e o PDF mostra 0 — precisa de tratamento
  explícito.
- **TG** = soma dos 9 gases = 60.044,5, impresso "60.044"; **TGC** = H2 + CH4 + CO +
  C2H4 + C2H6 + C2H2 = 544,5, impresso "544". A composição bate; o arredondamento
  parece ser para baixo.
- **R×T**: erro % = (medido − nominal) ÷ nominal × 100 dá −0,23, −0,42 e −0,36, como
  no PDF. A relação nominal 51,818 é 11.400 V (TAP 5, AT em triângulo) ÷ 220 V (fase
  da BT em estrela, ligação DYn1) — ver 10.3.
- **R×O**: Calculado = Medido × 1,5 no lado H (3,51 → 5,27; 3,60 → 5,40; 3,65 → 5,48).
  Corrigido = valor × (234,5 + 75) ÷ (234,5 + 45), com 45 °C = temperatura do óleo
  (fator ≈ 1,107; bate nos seis pares). A correção parte do valor calculado sem
  arredondar (5,265 → 5,83, e não 5,27 → 5,84): a precisão precisa ser preservada
  entre as etapas.

### 7.7 Perguntas para o cliente

Publicadas para o Fabrício responder no doc "Dúvidas — relatórios de óleo e ensaios
elétricos" (https://claude.ai/artifact/FQdiWQzEYQ3zkmBvywscc1 — privado até ser
compartilhado). Mesma numeração lá e aqui.

Os áudios do Fabrício de 24/09 responderam em parte a 1 (um relatório de óleo e um de
ensaios elétricos, cada um com capa, carta, gráficos, lista de equipamentos e depois as
fichas) e a 4 (haverá gráficos no mesmo padrão; faltam os indicadores). Disseram também
que a termografia segue uns 80% da vibração.

**Organização do relatório**

1. Cada ensaio é uma tecnologia no catálogo (AFIM‑FQ, AFIM‑CR, AFIM‑PCB, AFIM‑2FAL;
   EE‑RXT, EE‑RXI, EE‑RXO), mas cada PDF reúne todos os ensaios de uma coleta. Uma
   tecnologia por família no relatório e os ensaios como lista? (Define o número RT e
   o ícone da capa.)
2. Ficha de ensaio não solicitado deve sair? A folha 2‑FAL sai com "Amostra não
   coletada!" com o 2‑FAL desmarcado. Sugestão: sai se foi solicitado ou se há
   recomendação registrada.
3. As linhas por data de cada ficha são as últimas 6 campanhas do mesmo transformador?
4. Quais KPIs entram nesses relatórios?
5. Óleo e ensaios elétricos geram OSP/Grau de Risco por transformador, ou terminam na
   conclusão e recomendação de cada ensaio?

**Cadastro do transformador**

6. Tensão primária: 11,400 kV no PDF de óleo e 13,8 kV (TAP 5 = 11,4 kV) no de ensaios
   elétricos. Qual vai no cadastro e qual na ficha de óleo?
7. "Local da instalação" (SE‑01 - Subestação Caldeira/Kelco) é o Setor ou a Área?
8. "Tipo" (TFC‑500,1) é o modelo? A tensão secundária tem sempre dois valores (380 /
   220 V)?

**Coleta da amostra**

9. Coleta em 26/12/2026 com análise em 07/01/2026 e linha da tabela em 26/12/2025: erro
   de digitação? O sistema vai exigir coleta ≤ análise.
10. O amostrador é sempre um analista da Thermoproactive, ou pode ser terceiro ou o
    laboratório?
11. Criticidade ("Rotina" em todas as fichas): quais valores existem e quem define?

**Resultados do óleo**

12. Resultado abaixo do LD (PCB 0,5 mg/kg com LD = 2,0 mg/kg): registrar e imprimir
    como "< 2,0", "ND" ou o número do laboratório?
13. TG e TGC: a composição e o arredondamento da seção 7.6 estão certos, ou vêm prontos
    do laboratório?
14. A referência dos furânicos (0,010 mg/kg = LQ da nota 2) é limite de aceitação ou só
    o LQ?
15. As notas 2 a 4 do 2‑FAL (cortadas na página impressa) devem sair no relatório?
16. O percentual dos gráficos é valor ÷ referência × 100, inclusive nos mínimos? E o
    acetileno, com referência 0,0?

**Ensaios elétricos**

17. R×T: a relação nominal é informada ou calculada? O erro é (medido − nominal) ÷
    nominal × 100?
18. R×O: Calculado = Medido × 1,5 e correção a 75 °C (234,5, cobre) pela temperatura do
    óleo? Qual norma e critério de aceitação?
19. R×I: os 5000 MΩ repetidos de 180 s a 600 s (AT‑Massa‑BT) são leitura ou fundo de
    escala? Há critério de aceitação (índice de polarização)? O motor genérico atual usa
    IP ≥ 2 (IEEE 43), que não aparece no PDF.

**Termografia — etapa atual (RT.TE-2026.02.12.02307)**

20. Na OSP, I(N) é a corrente de neutro ou a nominal? O glossário (6.2.2) define I(n)
    como nominal, mas na OSP I(N) aparece junto de I(R), I(S) e I(T). Hoje o sistema
    mostra a corrente nominal.
21. Qual é a fórmula da correção da temperatura (C.T.M.) que gera T. Medida Corrigida e
    T. Delta Corrigida? O glossário diz quando aplicar, não a fórmula.
22. O sistema pode sugerir o Grau de Risco pelo ΔT (GR-1 > 100 °C; GR-2 60–100 °C; GR-3
    20–60 °C; GR-4 ≤ 20 °C), com o analista podendo mudar? As 10 OSPs seguem essa regra.
23. Qual texto do Fluxo de Trabalho vai na carta nova? O 6.11 do RT.TE cita o e-MasterSys.
24. De onde vem a data "Upload das OSP´s" da carta? Hoje o sistema não registra essa data.
25. Corrente e % de carga não medidas podem sair "—" em vez de 0,00?

## 8. Pendências encontradas (anteriores a esta etapa)

- **Visibilidade no portal**: `visivel_cliente` não é aplicado para usuários do portal
  em `/relatorios-inspecao/{id}/dossie/` nem em `/achados/`. O escopo por cliente
  funciona; a flag de liberação não. Precisa ser resolvido antes de o relatório entrar
  no portal (hoje o portal não mostra o relatório técnico).
- **Carta da vibração estoura a folha do item 5**: com várias normas cadastradas, normas +
  tabela ISO‑10816 ocupam 322 mm numa folha de 297 mm. No relatório 2 o PDF sai com 15
  páginas em vez de 14 (a sobra vai para uma página sem timbrado).
- **MTBF (proxy)** conta o intervalo entre OSPs do mesmo equipamento, inclusive as do
  mesmo relatório: várias análises num equipamento dão intervalo ≈ 0 (o caso local
  mostra "0 d").
- **Catálogo de termografia**: faltam as anomalias e recomendações que o RT.TE usa
  ("Mau contato no(s) terminal(ais) prensado(s)", "Mau contato na(s) conexão(ões)",
  "Substituir terminal(ais) prensado(s).", "Limpar, reapertar conexão(ões)…"). Em texto
  livre, cada variação vira uma categoria no KPI "Status das Anomalias".
- **TAG**: é obrigatória e única por setor; no RT.TE a maioria dos painéis não tem TAG.
- **Área no relatório**: sai só o nome ("SP1930 [Matriz]"); o RT.TE mostra código + nome
  ("001 - SP1930 [Matriz]").
- **Banco local (cópia da produção de 20/09)**: as sequências de ID de Cliente e de
  Classificação de inspeção estavam atrás do maior ID — cadastrar cliente falhava.
  Corrigido no local em 24/09; vale conferir na produção. O cadastro de normas da TI-SE
  tem a ISO-10880:2017 duplicada.
- Os formulários da folha de campo e da Análise final ainda deduzem a tecnologia pelo
  nome (`tecnologiaTipo` em `lib/inspecoes.ts`). Deveriam ler `modulo_tecnico`.
- Carta em PDF × carta .docx: o título da tabela ISO é "ISO‑10816‑1" no PDF e
  "ISO‑20816‑3" no .docx; os rótulos do item 2 e a distribuição por Grau de Risco do
  item 7 também diferem.
- Os corpos da OSP corretiva (`corretiva-*.tsx`) ficaram na raiz da feature; o lugar
  natural é `modulos/inspecao/`.

## 9. Como a refatoração foi validada

Com os 12 relatórios do banco local (cópia da produção), antes e depois:

- JSON do dossiê: idêntico, exceto os campos novos;
- carta .docx (`word/document.xml`): idêntica;
- relatório e carta em HTML, renderizados com o código real dos componentes: idênticos
  byte a byte (inclusive depois de os textos da carta passarem a vir do backend).

Além disso: 179 testes de backend (9 novos em `apps/coletas/test_relatorio_tecnico.py`),
`tsc` e `next build`.

### Caso local de termografia

Réplica das 10 OSPs do RT.TE-2026.02.12.02307 criada pelas mesmas APIs do app (carregar
rota → condição → análises → transferir → imagens → confirmar):

- cliente **Acco Brands Brasil Ltda – Foroni** (CNPJ 44.990.901/0009-09), áreas "SP1930
  [Matriz]" e "SP2001 [Filial]", 5 setores, 10 equipamentos com a condição da Seção C do
  PDF;
- relatório **RT-TI-SE-2026-02-12-00012**, 10 análises com as temperaturas, os
  componentes e as fotos (térmica e real) das folhas 22–31 do PDF; as OSPs foram geradas
  na confirmação;
- conferido no app: carta com 6 folhas de 297 mm e PDF (paged.js) com 22 páginas.

Valores que o PDF não traz ficaram vazios. O analista é a conta de teste local, e os
números de OSP são os do sistema novo.

## 10. Módulos de transformador — óleo isolante e ensaios elétricos

Pedido de 24/09/2026: o relatório segue o **formato do nosso relatório final** (capa →
carta → KPIs → equipamentos → fichas, com o shell de sempre); o conteúdo das fichas vem
dos PDFs de referência e o que eles não definem, de pesquisa. Um exemplo foi criado no
sistema local (10.5).

| Relatório | Tecnologia (exemplo local) | Seção D — por transformador |
| --- | --- | --- |
| Óleo isolante | Análise de Fluídos Isolantes Minerais (AFIM) → `OLEO_ISOLANTE` | Registro da coleta + inspeção visual → FQ → CR → PCB → 2‑FAL |
| Ensaios elétricos | Ensaios Elétricos em Transformadores (EE) → `ENSAIO_ELETRICO` | Registro dos ensaios → R×T → R×I → R×O |

Capa, carta, contracapas, relação de equipamentos, paginação e PDF são os do shell, sem
nenhuma mudança de comportamento para as outras tecnologias (10.6).

### 10.1 Backend — app `apps/ensaios`

| Arquivo | Conteúdo |
| --- | --- |
| `models.py` | Catálogos `TipoFluido`, `PontoColeta`, `ItemChecklistVisual`, `Ensaio`, `ParametroEnsaio`; dados `ColetaOleo` (+ `InspecaoVisualColeta`), `RegistroEnsaioEletrico`, `ResultadoEnsaio`, `ValorParametro` — a extensão da seção 7.5 |
| `migrations/0002_catalogos.py` | Ensaios e parâmetros (unidade, norma, referência, tipo de limite, casas decimais), checklist de 20 itens, ponto de coleta e fluido, transcritos dos PDFs. Editáveis no admin |
| `calculos.py` | Funções puras, cada uma com a fonte (10.3) |
| `relatorio.py` | `ModuloOleoIsolante` e `ModuloEnsaioEletrico`: payload `transformadores`, `kpis`, `contato_cliente` e o resumo do item 7 da carta |
| `carta.py` | Seções, glossário e considerações da carta (os PDFs não têm carta — proposta a validar) |
| `serializers.py`, `views.py`, `urls.py`, `admin.py` | API e admin |

Cadastro (`cadastros/0027`): `Equipamento.numero_patrimonio` e `ano_fabricacao`;
`DadosTecnicosTransformador.tensao_secundaria_fase_v`, `volume_oleo_l` e
`possui_tanque_expansao`. As telas de equipamento e de dados técnicos do transformador
já têm os campos.

| Rota | Uso |
| --- | --- |
| `/api/ensaios/?modulo=` | catálogo de ensaios com os parâmetros |
| `/api/tipos-fluido/`, `/api/pontos-coleta/`, `/api/itens-checklist-visual/` | catálogos |
| `/api/coletas-oleo/` | coleta; `inspecao_visual` enviada substitui o checklist inteiro |
| `/api/registros-ensaio-eletrico/` | registro dos ensaios elétricos |
| `/api/resultados-ensaio/` | um por transformador × ensaio; `valores` enviados substituem todos — o mesmo contrato para digitação, planilha ou integração (campo `origem`) |

Escrita só da equipe interna; o portal consulta o que é da própria empresa
(`item__carregamento__cliente`). Validações: o transformador tem de estar numa rota da
tecnologia do módulo certo, o parâmetro tem de ser do ensaio, parâmetro calculado não se
digita e a próxima data não pode ser anterior à análise.

**Ainda não há tela de lançamento** para coleta, registro e resultados: hoje o
lançamento é pela API ou pelo admin do Django (`/django-admin/`, valores em linha). É o
próximo passo natural.

### 10.2 Frontend

`modulos/oleo.tsx` e `modulos/eletrico.tsx` declaram a ficha de registro, os rótulos
e o terceiro quadro de texto; o resto é da família (`modulos/transformador/`): folha e
quadros das fichas (`folha.tsx`), fichas de parâmetros (`fichas-oleo.tsx`), R×T/R×I/R×O
(`fichas-eletricas.tsx`), gráficos (`graficos.tsx`), KPIs (`kpis.tsx`) e a fábrica do
módulo (`modulo.tsx`). Números com as casas do catálogo, arredondados meio para cima
sobre o valor sem arredondar (`formato.ts`: 5,265 → 5,27, e não 5,26 como faria
`toFixed`).

### 10.3 Cálculos — fórmula, fonte e conferência com os PDFs

| Grandeza | Fórmula | Fonte | PDF |
| --- | --- | --- | --- |
| TG | soma dos 9 gases, truncada | ficha CR (60.044,5 → "60.044") | 60.044 ✓ |
| TGC | H2 + CH4 + CO + C2H4 + C2H6 + C2H2, truncada | IEEE C57.104 (TDCG) | 544 ✓ |
| % da referência | valor ÷ referência × 100; referência 0 → sem barra | fichas FQ/CR/PCB | 80,0; 94,4; 157,5… ✓ |
| Relação nominal (R×T) | tensão do enrolamento de AT ÷ a do de BT; triângulo = tensão de linha, estrela = tensão de fase (a de placa, ou linha ÷ √3) | o TTR mede a relação por fase | 11.400 ÷ 220 = 51,818 ✓ |
| Erro da relação | (medida − nominal) ÷ nominal × 100; conforme de −0,5 a +0,5 | ANSI/NETA ATS (tolerância da ficha) | −0,23; −0,42; −0,36 ✓ |
| R×O calculado | triângulo medido entre linhas: 1,5 × leitura; estrela a partir do neutro: a leitura; estrela entre linhas: leitura ÷ 2 | circuito do enrolamento | 5,27; 5,40; 5,48 ✓ |
| R×O corrigido | R × (234,5 + 75) ÷ (234,5 + temperatura do óleo) | IEEE C57.12.90 (cobre, 75 °C) | 5,83; 5,98; 6,06; 1,62; 1,61; 1,63 ✓ |
| IP e IA (R×I) | R(600 s) ÷ R(60 s) e R(60 s) ÷ R(30 s); IP conforme a partir de 1,0 | ANSI/NETA ATS | IP 1,11; 1,25; 1,22 (o PDF não imprime) |
| GP estimado (2‑FAL) | 7100 ÷ (8,88 + 2‑furfural em mg/kg), só quando o laboratório não manda o GP | De Pablo (nota 3 da ficha) | — |

`apps/ensaios/tests.py` reproduz todos os números da coluna "PDF".

### 10.4 Decisões tomadas para implementar (a validar)

Pela numeração das perguntas da seção 7.7:

| # | Decisão implementada | Base |
| --- | --- | --- |
| 1 | Um relatório por família: tecnologias AFIM e EE com o módulo. As tecnologias por ensaio do catálogo (AFIM‑FQ, EE‑RXT…) ficaram como estão, sem módulo | áudios + PDFs |
| 2 | A ficha sai se o ensaio foi solicitado ou tem resultado registrado (o 2‑FAL "Amostra não coletada" sai) | PDF |
| 3 | Até 6 campanhas do mesmo transformador por ficha, em ordem cronológica, a atual em negrito por último; no R×O as anteriores entram só com o valor corrigido | PDF (6 linhas) |
| 4 | KPIs: transformadores, ensaios realizados, parâmetros avaliados e fora da referência, próxima coleta, status dos ensaios, inspeção visual (óleo), maior erro de relação e menor IP (elétricos), resultado por ensaio | proposta |
| 5 | Sem OSP/Grau de Risco: cada ensaio termina na conclusão e na recomendação; na Seção C vai a condição do item da rota | PDF |
| 6 | Cadastro com 13,8 kV; a ficha de óleo mostra o cadastro | ficha de ensaios |
| 7 | "Local da instalação" = Setor | PDF |
| 8 | "Tipo" = modelo; tensão secundária linha / fase (campo novo) | PDF |
| 9 | Coleta em 26/12/2025 no exemplo | ordem das datas |
| 10 | Amostrador em texto livre | pode ser terceiro |
| 11 | Criticidade Rotina / Alerta / Crítica, escolhida pelo analista, separada do Grau de Risco | PDF só mostra "Rotina" |
| 12 | O valor é registrado como veio (PCB 0,5); o modelo aceita "abaixo do LD/LQ" sem número | — |
| 13 | TG e TGC calculados pelo sistema | 10.3 |
| 14 | 0,010 mg/kg tratado como referência máxima, como na ficha | PDF |
| 15 | As 4 notas do 2‑FAL saem | PDF |
| 16 | % = valor ÷ referência; acetileno (referência 0,0) sem barra | 10.3 |
| 17 | Relação nominal calculada, ou a informada quando vier | 10.3 |
| 18 | R×O calculado e corrigido como em 10.3, **sem critério de aceitação** ("sem critério definido") | o critério NETA de 2 % entre fases reprovaria o próprio PDF (3,51 × 3,65 Ω = 4 %), que diz "em conformidade" |
| 19 | 5.000 MΩ registrado como leitura; IP a partir de 1,0 (NETA) | IEEE 43 (IP ≥ 2) é para máquinas girantes |

Diferenças deliberadas em relação aos PDFs:

- **Gráficos com um eixo só**, em % da referência, com a referência em 100% para
  máximos e mínimos. No PDF, FQ e 2‑FAL têm dois eixos (máximos à esquerda, mínimos à
  direita, com escalas diferentes), o que põe as duas referências em alturas diferentes.
- **Transparência dos cálculos**: a ficha R×I mostra IP e IA; R×T e R×O têm uma nota de
  como o valor foi calculado.
- **Grafia**: "Tensão Primária/Secundária", "Tipo de Fluido" e "Tempo [s]" (nos PDFs:
  "Tensão Primário", "Tipo de Fluído", "Time [s]").
- **Carta**: conteúdo, glossário e considerações são proposta (os PDFs não têm carta).
  No óleo o item 4 sai "Não informada" (análise de laboratório) — falta decidir se entra
  o laboratório ou o equipamento dele.
- **Normas do exemplo**: códigos como impressos nas fichas, com a descrição do uso no
  relatório, não o título oficial.

### 10.5 Exemplo no sistema local (TRF-001)

Criado por script, pelas mesmas APIs do app (rota → carregamento → condição →
transferência → coleta/registro → resultados → finalização):

- cliente **Novaprom Food Ingredients Ltda** (CNPJ 02.916.265/0219-14, Guaiçara‑SP),
  área "Subestações", setor "SE-01 - Subestação Caldeira/Kelco", equipamento
  **TRF-001** com a placa dos PDFs (500 kVA, 13,8 kV, 380/220 V, 4,49 %, DYn1, 540 L,
  sem tanque de expansão);
- **RT-AFIM-2025-12-26-00013** (relatório 16): coleta de 26/12/2025, inspeção visual
  12 OK + 8 NA, FQ, CR e PCB com os laudos do PDF e 2‑FAL "Amostra não coletada";
- **RT-EE-2025-12-26-00014** (relatório 17): TAP 5 (11,4 kV), óleo a 45 °C, R×T, R×I e
  R×O com os laudos e os três instrumentos Instrum do PDF;
- 14 normas no óleo e 2 nos elétricos (as citadas nas fichas e as das fórmulas).

### 10.6 Validação

- 199 testes de backend (20 novos em `apps/ensaios/tests.py`: cálculos com os números
  dos PDFs, payload dos dois módulos, carta .docx, API e escopo do portal).
- Os 13 relatórios que já existiam (12 da produção + o caso de termografia): carta
  .docx idêntica; relatório e carta em HTML idênticos; JSON do dossiê só com a chave
  nova `carta.paragrafos` (vazia).
- No app: óleo com 17 folhas e elétricos com 16, todas com 297 mm; PDF (paged.js) com 17
  e 16 páginas. A termografia continua com 22.
- `tsc` e `next build`.
