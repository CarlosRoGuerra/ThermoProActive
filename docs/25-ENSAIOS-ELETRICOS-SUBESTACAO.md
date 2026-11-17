# 25 — Ensaios elétricos de subestação (TC, TP, DJ, CS e RP)

Status: implementado em 16/11/2026 — catálogo, lançamento (campo e Análise final), cálculos,
fichas do relatório e exemplos de seed. **Os critérios e a lista de ensaios são propostas
técnicas: validar com o responsável técnico do cliente** (seção 6). Não há ficha de referência
do cliente para estes equipamentos, diferente do TRF (docs/10 §7).

## 1. Arquitetura

Reaproveita o motor do transformador (`apps/ensaios`): `Ensaio` e `ParametroEnsaio` (catálogos),
`ResultadoEnsaio` (um laudo por equipamento e ensaio), `ValorParametro` (valor por série e
posição) e o contexto técnico gravado no lançamento. O que é específico:

| Peça | Onde | Conteúdo |
| --- | --- | --- |
| `Ensaio.forma` | `ensaios/models.py` | `TABELA` (óleo, fluidos, R×T/R×I/R×O), `MEDICAO` (uma linha por série: fase, polo, núcleo ou função), `CURVA` (tensão × corrente por núcleo) |
| `DadosPlacaSubestacao` | `ensaios/models.py` | extensão 1-para-1 de `Equipamento`: tensão e corrente nominais, relação de placa e relação nominal (primário ÷ secundário), classe de exatidão, carga, núcleos, polaridade, polos, capacidade de interrupção, mecanismo, funções de proteção do relé |
| `RegistroEnsaioSubestacao` | `ensaios/models.py` | registro de campo (1-para-1 com `ItemInspecao`): data, analista, temperaturas, umidade e ensaios solicitados |
| Catálogos | `ensaios/migrations/0021_catalogos_subestacao.py` | ensaios e parâmetros dos cinco equipamentos (idempotente, `update_or_create`) |
| Migração de schema | `ensaios/migrations/0020_subestacao_schema.py` | campo `forma`, as duas tabelas novas; inclui `AlterField` de rótulos de `modulo` (sem efeito no banco) e depende de `cadastros.0040` |
| Cálculos | `ensaios/calculos_subestacao.py` | funções puras, cada uma com a fonte |
| Relatório | `ensaios/relatorio_subestacao.py` | `ModuloTC`, `ModuloTP`, `ModuloDJ`, `ModuloCS`, `ModuloRP` (família `ModuloEnsaioSubestacao`) |
| Carta | `ensaios/carta_subestacao.py` | glossário, conteúdo e considerações propostos |
| Registro de módulos | `cadastros/models.py` (`MODULOS_PLANEJADOS` vazio) e `coletas/relatorio_tecnico/modulos.py` | os cinco módulos saem de "não implementado" |

Módulos: `ENSAIO_ELETRICO_TC`, `ENSAIO_ELETRICO_TP`, `ENSAIO_ELETRICO_DJ`, `ENSAIO_ELETRICO_CS`,
`ENSAIO_ELETRICO_RP` (escolhidos em `TecnologiaAnalise.modulo_tecnico`).

API (`apps/ensaios/urls.py`):

- `/api/dados-placa-subestacao/` — placa do equipamento (escrita só da equipe interna; cliente vê só os próprios equipamentos; `campo_cliente = equipamento__setor__area__cliente`);
- `/api/registros-ensaio-subestacao/` — registro de campo; recusa item de rota que não é de subestação e ensaios de outro equipamento;
- `/api/subestacao-inspecao/` — fila do lançamento (somente leitura), com a situação de cada ensaio;
- `/api/resultados-ensaio/` — o mesmo endpoint do TRF; a avaliação devolve `tipo` (`MEDICAO` ou `CURVA`), `linhas`, `criterio`, `indicadores` ou `joelhos`. Medição exige série; curva exige tensão.

Tela:

- campo: folha da rota (`?item=`) abre `EditorSubestacao` quando o módulo é de subestação;
- escritório: aba "Ensaios de subestação" na Análise final e `/inspecoes/final/subestacao/[id]`;
- editor (`features/ensaios/`): `registro-subestacao.tsx` (registro e placa), `valores-subestacao.tsx`
  (grade por série e curva), `editor-subestacao.tsx`, `fila-subestacao.tsx`.

## 2. Ensaios e parâmetros por equipamento

Proposta de comissionamento e manutenção, a partir de ANSI/NETA ATS, IEC e IEEE. Todos os
parâmetros são informativos, salvo os calculados (seção 3).

| Equip. | Sigla | Ensaio | Forma | Parâmetros (código · unidade) | Norma ou método citado |
| --- | --- | --- | --- | --- | --- |
| TC | RELA | Relação de transformação e polaridade | MEDICAO | RELACAO_MEDIDA · –; ERRO_RELACAO · % (calc.); POLARIDADE · texto | IEC 61869-2; ANSI/NETA ATS (ensaios de TC) |
| TC | EXC | Saturação (curva de excitação) | CURVA | CORRENTE_EXCITACAO · mA; tensão em V; joelho calc. | IEEE C57.13 |
| TC | ISO | Resistência de isolação | MEDICAO | TENSAO_ENSAIO · V; RESISTENCIA · MΩ | leitura informativa |
| TC | OHM | Resistência ôhmica do enrolamento | MEDICAO | RESISTENCIA · Ω | leitura informativa |
| TP | RELA | Relação de transformação e polaridade | MEDICAO | RELACAO_MEDIDA; ERRO_RELACAO (calc.); POLARIDADE | IEC 61869-3 |
| TP | ISO | Resistência de isolação | MEDICAO | TENSAO_ENSAIO; RESISTENCIA · MΩ | leitura informativa |
| TP | OHM | Resistência ôhmica do enrolamento | MEDICAO | RESISTENCIA · Ω | leitura informativa |
| DJ | RCON | Resistência de contatos | MEDICAO (por polo) | RESISTENCIA · µΩ | ANSI/NETA ATS; critério do fabricante |
| DJ | ISO | Resistência de isolação | MEDICAO (por polo) | TENSAO_ENSAIO; RESISTENCIA · MΩ | ANSI/NETA ATS |
| DJ | TEMP | Tempos de abertura e fechamento | MEDICAO (por polo) | TEMPO_ABERTURA · ms; TEMPO_FECHAMENTO · ms; simultaneidade calc. | IEC 62271-100; ANSI C37.09; critério do fabricante |
| CS | RCON | Resistência de contatos | MEDICAO (por fase) | RESISTENCIA · µΩ | ANSI/NETA ATS; critério do fabricante |
| CS | ISO | Resistência de isolação | MEDICAO (por fase) | TENSAO_ENSAIO; RESISTENCIA · MΩ | ANSI/NETA ATS |
| RP | PICK | Corrente de pickup das funções | MEDICAO (por função) | AJUSTE · A; ESPERADO · A; MEDIDO · A; TOLERANCIA · % (informada); ERRO · % (calc.) | IEC 60255-151 (método) |
| RP | TEMP | Tempo de atuação das funções | MEDICAO (por função) | ESPERADO · s; MEDIDO · s; TOLERANCIA · % (informada); ERRO · % (calc.) | IEC 60255-151 (método) |

Funções do relé (ANSI 50, 51, 50N, 51N…) são linhas digitadas; o nome da série é livre.

## 3. Cálculos e fontes

Cada função está em `calculos_subestacao.py` (ou em `calculos.py`, quando é o mesmo cálculo do TRF).

| Cálculo | Fórmula | Fonte | Critério |
| --- | --- | --- | --- |
| Erro de relação | (medido − nominal) ÷ nominal × 100; nominal = relação de placa (primário ÷ secundário) | IEC 61869-2 (TC), IEC 61869-3 (TP) | erro admissível pela classe da placa (abaixo) |
| Erro admissível por classe (TC) | medição 0,1 · 0,2 · 0,5 · 1 · 3 · 5 → ± a classe; proteção 5P → ± 1 %; 10P → ± 3 % | IEC 61869-2 (tabela de erro de relação) | classe fora da tabela → sem critério |
| Erro admissível por classe (TP) | medição 0,1 · 0,2 · 0,5 · 1 · 3 → ± a classe; proteção 3P → ± 3 %; 6P → ± 6 % | IEC 61869-3 | idem |
| Erro de pickup | (medido − esperado) ÷ esperado × 100 | IEC 60255-151 (método) | \|erro\| ≤ tolerância informada na linha; sem tolerância → sem critério |
| Erro de tempo | (medido − esperado) ÷ esperado × 100 | idem | idem |
| Simultaneidade entre polos | máx − mín dos tempos de abertura (ou de fechamento), em ms | IEC 62271-100 e ANSI C37.09 (método) | critério do fabricante: sem limite universal |
| Tensão de joelho | primeira tensão V em que I(1,10·V) ≥ 1,50 · I(V), com I interpolado linearmente entre os pontos lançados; devolve o ponto lançado | IEEE C57.13 (joelho: +10 % de tensão exige +50 % de corrente) | informativo |
| Polaridade | igual à polaridade declarada na placa (texto, sem tolerância) | placa do equipamento | sem placa com polaridade → sem critério |

Valor ausente é nulo, nunca zero. Resistências de isolação, ôhmica e de contatos não têm cálculo:
a leitura sai como medida, com "sem critério definido".

## 4. Relatório

- Shell comum (capa, carta, KPIs, relação de equipamentos, PDF). Módulo por equipamento.
- Por equipamento: ficha 1 "Registro de dados dos ensaios elétricos" (cliente, cadastro,
  dados de placa, condições do ensaio, tipos de ensaio ■/□). Depois, uma ficha por ensaio
  solicitado ou com resultado.
- Ficha `MEDICAO`: uma linha por série; colunas digitadas e calculadas; linha de unidades e de
  norma; cores pela referência. Abaixo, o erro admitido com a classe e a relação nominal, a
  simultaneidade (DJ) e a nota "sem critério definido" quando for o caso.
- Ficha `CURVA`: tabela de tensão × corrente por núcleo, gráfico SVG e tensão de joelho.
- KPIs: equipamentos, ensaios realizados, medições avaliadas e fora da referência, próxima
  análise, **maior erro por ensaio** (relação, pickup ou tempo) e maior simultaneidade do DJ,
  com o erro admitido quando há critério.
- Resumo do item 7 da carta gerado pelo backend: "… 0 ensaios ficaram dentro das referências e
  1 fora delas (RELA)"; sem nenhum critério no ciclo, a frase diz que os resultados são
  informativos.
- O laudo guarda a placa e o registro do momento do lançamento (`contexto_tecnico`): trocar a
  placa depois não muda o laudo já lançado (teste `test_laudo_guarda_a_placa_do_lancamento`).

## 5. Decisões provisórias

1. **Sem limite numérico cadastrado** para resistências, tempos de DJ e tempos de relé. O
   critério sai "sem critério definido", nunca "conforme".
2. **Erro de relação pela classe da placa**, com a tabela das normas IEC citadas. É a única
   regra que aplica um limite sem o cliente cadastrar nada; a tabela deve ser conferida com a
   edição da norma que o cliente adota (ver perguntas 1 e 2).
3. **Tolerância do relé lançada em cada linha**, nunca constante no código.
4. **Joelho pelo critério IEEE C57.13**, só informativo, calculado sobre os pontos lançados
   (sem interpolar o resultado).
5. **Sem histórico de campanhas nas fichas** (o TRF mostra até seis). A ficha mostra a campanha
   lançada; o histórico é pendente.
6. **Séries livres** (nome digitado): fase, polo, núcleo ou função não têm catálogo próprio.
7. **Dados de placa no app `ensaios`** (`DadosPlacaSubestacao`), não em `cadastros`, por
   divisão de arquivos com o outro agente. Sem migração no `cadastros` neste trabalho.
8. **Textos da carta propostos** (`carta_subestacao.py`): validar antes de emitir laudo real.

## 6. Perguntas para o responsável técnico do cliente

1. Qual edição e tabela de erro de relação o cliente adota para TC e TP (IEC 61869-2/-3, ou
   ANSI C57.13 com as classes C e T)? Confirmar as classes 5P, 10P, 3P e 6P.
2. Quais ensaios o cliente exige em cada equipamento (a lista da seção 2 é proposta)?
3. Qual critério de resistência de isolação vale: mínimo do fabricante, da ANSI/NETA ATS ou do
   cliente? Qual tensão de ensaio padrão por equipamento?
4. Resistência de contatos de DJ e CS: máximo por fabricante ou por tipo? Cadastrar por modelo?
5. Tempos de abertura e fechamento do DJ e simultaneidade entre polos: limites por fabricante e
   modelo?
6. Relé: qual tolerância padrão e qual método (IEC 60255-151 ou o do fabricante)? A tolerância
   é lançada por linha ou fica no ajuste?
7. Curva de excitação: o critério de joelho é o IEEE C57.13, ou o cliente usa outro (ex.: ponto
   de 50 % de corrente, ou a norma nacional)?
8. A polaridade declarada vem sempre da placa, ou o cliente registra a polaridade do ensaio
   como critério separado?
9. As fichas de subestação devem ter histórico de campanhas, como as do transformador?
10. Os textos da carta (glossário, considerações) estão adequados? Quem assina a conformidade
    dos critérios no relatório?
11. Os equipamentos de subestação vêm do mesmo inventário do cadastro de equipamentos, ou o
    cliente tem base própria (com tag e número de patrimônio)?

## 7. O que ficou de fora

- Histórico de campanhas nas fichas de subestação (decisão 5).
- Critérios de aceitação de isolação, contatos e tempos (dependem das respostas 3 a 5).
- Importação de planilha ou de arquivo do laboratório/equipamento para os ensaios de subestação
  (só lançamento manual, como no TRF).
- Verificação visual de cada ficha no PDF e no navegador — ver o relatório de entrega para o que
  foi de fato verificado.
