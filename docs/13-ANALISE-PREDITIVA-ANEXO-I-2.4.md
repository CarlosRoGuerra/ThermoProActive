# Análise preditiva — Anexo I, itens 2.4.1 e 2.4.2

Auditoria de 22/10/2026. Escopo: medições diretas, ensaios laboratoriais e serviços
corretivos existentes, com preservação das integrações com laudos, indicadores e OSP.

## Conclusão e alcance

O contrato enumera análise comparativa, histórico, tendências, anomalias, risco,
alertas, regras, criticidade, diagnóstico assistido e sugestões. **Não especifica
limiares, probabilidades, horizonte de previsão, janelas estatísticas ou uso obrigatório
de IA.** Uma série crescente não demonstra uma causa de falha nem sua probabilidade.

A cobertura é parcial por modalidade. Classificação automática só deve concluir uma
condição quando existe critério aplicável; séries e cálculos descritivos podem existir
mesmo quando o parecer técnico permanece pendente. Não há modelo de IA obrigatório,
serviço externo novo ou cálculo de probabilidade de falha nesta entrega.

## Fontes e precedência das decisões

| Fonte interna efetivamente lida | O que fundamenta | Limite da evidência |
| --- | --- | --- |
| [Contrato](../contrato.txt), Anexo I 2.4.1.1–2.4.2.4 | As dez funções contratadas | Não define regra numérica nem norma aplicável |
| [Discovery dos módulos](01-DISCOVERY-modulos-tecnicos.md) e [perguntas](03-perguntas-ao-cliente.md) | Levantamento inicial de grandezas, faixas e questões | Os próprios documentos dizem que faixas/heurísticas precisam de confirmação; não homologam 1,5×, crista >5 ou limites universais |
| [Discovery de balanceamento/economia](04-DISCOVERY-balanceamento-e-economia.md) | Decodificação das planilhas fornecidas e hipóteses dos cálculos | Fórmula reproduzida não comprova aplicabilidade universal ou qualidade do serviço |
| [Cadastro e fluidos](11-CADASTRO-POR-TIPO-E-FLUIDOS.md), §4.1 e §12–12.4 | Registro interno de respostas técnicas datadas, critérios e versões mais recentes | Não constitui nova certificação de norma, instrumento ou acervo legado |
| [Conformidade da coleta](12-CONFORMIDADE-COLETA-ANEXO-I-2.3.md) | Campos, subtipos, critérios pendentes e preservação histórica já implementados | Registro pontual/JSON não equivale a ficha completa ou estudo de todas as técnicas |

As respostas datadas do documento 11 prevalecem sobre perguntas iniciais quando tratam
da mesma decisão: base da viscosidade passou a ser óleo novo; critérios de vibração
passaram a distinguir grupo/base; respostas de EF e potássio são posteriores. As
confirmações são atribuídas ao registro interno, sem afirmar que esta auditoria
consultou ou homologou os textos normativos originais.

Há uma inconsistência documental específica: o documento 11 §4.1 chama evolução de
procedimento customizado mantido; os documentos 01/03 pedem confirmação expressa de
fator/janela. Sem evidência específica de aprovação, a evolução automática nova fica
desabilitada até validação com fonte. Isso não altera resultados históricos gravados.

## Matriz dos requisitos

| Item | Evidência existente e complemento | Lacuna / condição de aceite técnico |
| --- | --- | --- |
| 2.4.1.1 Comparativa | Zonas de vibração por critério; referências de laboratório; redução antes/depois; comparação numérica da série direta | Não extrapolar mesma referência a unidades, instrumentos ou regimes diferentes |
| 2.4.1.2 Histórico evolutivo | Medições/ensaios vinculados ao ativo, revisões e critérios congelados; série direta selecionada pelo contexto | Acervo sem critério original permanece identificado; não reconstruir aprovação retroativa |
| 2.4.1.3 Tendência de falhas | Variação, média e inclinação descritivas da série direta; variação entre campanhas dos fluidos; evolução configurada de vibração | Tendência de medição não é previsão de falha, vida restante ou probabilidade; demais modelos dependem de definição técnica |
| 2.4.1.4 Anomalias automáticas | Superação de faixa específica de vibração e referências laboratoriais; condição sensitiva explícita | ΔT e grandezas genéricas sem critério não geram diagnóstico automático |
| 2.4.1.5 Indicadores de risco | Criticidade por faixa; GR do relatório-modelo de fluidos; contagens e evolução nos indicadores existentes | GR não é probabilidade; painel pode ter parâmetros não avaliados, devendo explicitar incompletude |
| 2.4.1.6 Alertas preventivos | Evento interno rastreável por ocorrência de medição, associado à decisão e à OSP quando aplicável | Confirmar política de recorrência, destinatários e notificações externas; sem evento em consulta |
| 2.4.2.1 Regras automáticas | Funções determinísticas e regras condicionais, com parâmetros e base registrada | Técnicas sem critério permanecem pendentes; sem serviço externo obrigatório |
| 2.4.2.2 Criticidade | Zonas A/B → NORMAL, C → ALERTA, D → CRITICO; evolução apenas se habilitada/validada; sensitiva informada | Mapeamento zona/criticidade é procedimento do produto, separado da origem normativa da faixa |
| 2.4.2.3 Diagnóstico assistido | Explicação de grandeza, faixa, comparação histórica e dados usados; parecer do técnico e catálogos existentes | Sem identificação causal por espectro/ODS ou IA; crista isolada não diagnostica rolamento |
| 2.4.2.4 Sugestões técnicas | Orientação para revisão técnica e critério aplicável, além das recomendações já selecionadas pelo técnico | Não gera receita de reparo, peça, prazo ou técnica de intervenção sem regra aprovada |

## Inventário de regras, entradas e saídas

### Regras determinísticas

| ID / implementação | Entradas e unidade | Saída / fronteira | Fonte e situação |
| --- | --- | --- | --- |
| VIB-ZONA — `coletas/rules.py`, cadastro de critérios | Velocidade RMS mm/s; grupo/classe; base quando exigida; cliente, data e faixas A/B/C vigentes | Limites superiores inclusivos: ≤A → A; ≤B → B; ≤C → C; >C → D; criticidade e explicação | Critério cadastrado com origem/edição/vigência, sem fallback genérico no fluxo direto novo; origem LEGADO ou base necessária ausente impede classificação |
| VIB-EVOLUCAO — configuração do critério de vibração | Velocidade atual; janela de valores anteriores comparáveis; fator; aprovação/fonte | Atual estritamente > fator × média anterior pode elevar um nível, limitado a CRITICO; não reduz a zona original | Heurística customizada. Desabilitada por padrão; fator/janela herdados não representam aprovação automática; exige ativação validada com fonte |
| VIB-DESLOCAMENTO — função pura/fluxo de campo existente | Deslocamento **RMS** µm e faixas RMS aplicáveis | Pior zona entre velocidade e deslocamento quando ambos aplicáveis | Não comparar `MedicaoVibracao.deslocamento_pp` com limites RMS; sem presumir forma de onda ou conversão |
| TERMO-DELTA — `coletas/rules.py` | Temperatura do ponto e referência, °C; sistema identificado | ΔT = ponto − referência, mantendo sinal; classificação pendente | Aritmética; método de referência e faixas por sistema não homologados; nenhum 3/15 °C universal novo |
| SENS-PARECER — `coletas/rules_tecnicas.py` | Parecer NORMAL/ALERTA/CRITICO e observação | Criticidade explícita do responsável; não inferida de valor fictício | Avaliação humana identificada como tal; ausência de parecer deixa pendente |
| GENERICO-PENDENTE — `coletas/rules_tecnicas.py` | Modalidade/subtipo, grandeza, valor, unidade e contexto | Preserva leitura e informa necessidade de critério; criticidade vazia | Fluidos/ensaios no cadastro genérico, ultrassom, espessura, qualidade de energia, alinhamentos e balanceamento avulso não herdam limite universal |
| FLU-REFERENCIA — `ensaios/calculos_fluidos.py` | Valor/estado, referência de escopo vigente, base do óleo novo quando pertinente | Máximo/mínimo estritos; variação absoluta %, queda %, aumento, qualitativo ou código ISO; ROTINA/ALERTA/CRITICA/sem avaliação | Referências por equipamento, tipo de equipamento, fluido, cliente/aplicação; origem/fonte/vigência e contexto preservados para novos lançamentos |
| FLU-ISO — `ensaios/calculos_fluidos.py` | Contagens >4, >6, >14 µm(c)/mL | Código ISO 4406 pela tabela existente; sem três contagens não inventa código completo; meta por referência | Tabela implementada anteriormente/documento 11; código de limpeza não define sozinho condição universal |
| FLU-GR — `ensaios/grau_risco_fluidos.py` | Estados por ensaio e condição de campo | GR-1 por decisão visual; 1/2/>2 ensaios anômalos → GR-4/3/2; nenhum anômalo entre avaliados → GR-0; nenhum avaliado → sem GR | Modelo laboratorial 2016-11-0882 e prazos citados no documento 11; GR sobre painel parcial não prova avaliação completa; confirmar apresentação da Seção C |
| TRF-CALCULOS — `ensaios/calculos.py` | Tensões/grupo/TAP, relação medida; R/t/ligação; gases; 2-FAL | Relação nominal/erro %, resistência por fase/corrigida, IP/IA, TG/TGC e GP estimado | Fórmulas existentes dos relatórios do cliente; aritmética e estimativa de GP não equivalem a diagnóstico definitivo ou homologação geral |
| TRF-REFERENCIA — `ensaios/calculos.py::avaliar` | Valor/estado, máximo/mínimo/faixa/texto e LD/LQ | Dentro/fora/sem avaliação; máximo/mínimo/faixa incluem a igualdade | Catálogo/método aplicável; censura analítica não é zero e exige evidência LD/LQ compatível |
| COR-REDUCAO — `servicos/rules.py` | Reference e Trim, mm/s no mesmo ponto | Residual = Trim/Reference ×100; redução =100−residual, Reference >0 | Planilha fornecida; classificação residual e eficácia legada precisam de homologação específica |
| COR-ECONOMIA — `servicos/rules.py` | V, correntes antes/depois A, FP, horas/dia, dias/ano, custo kWh, investimento | ΔI, ΔkW, kWh/ano, R$/ano, payback se economia/investimento positivos | Hipóteses trifásicas, regime e medição comparável explicitadas; economia negativa é resultado possível, não probabilidade de falha |

Os valores confirmados internamente estão no documento 11 com suas datas: acordo
classe II de 16/09/2026 (B/C 4,49 mm/s, explicitamente distinto da norma), critérios
de vibração de 07 e 08/10/2026, viscosidade/água e TAN, base óleo novo e metas de
limpeza, EF de 13/10 e potássio de 21/10. A seleção usa o cadastro vigente; não se
codifica esta lista como um novo limite universal nesta auditoria.

### Estatística descritiva e funcionalidades de IA

| Cálculo | Entradas / tratamento | Interpretação permitida |
| --- | --- | --- |
| Série direta | Leituras anteriores do mesmo ativo, modalidade, ponto, componente, instrumento e contexto operacional documentado, em sequência temporal | Histórico comparável pelos dados disponíveis; contexto omitido não prova equivalência física |
| Diferença absoluta/percentual | Atual versus anterior ou média; divisor zero impede percentual | Mudança observada na grandeza, sem diagnóstico causal |
| Média e inclinação temporal | Valores finitos e datas comparáveis; insuficiência de pontos fica inconclusiva | Resumo e direção da medição; inclinação não equivale a tempo até a falha |
| Tendência de fluidos | Valores medidos finitos de campanhas anteriores e atual, ordenados; contexto da amostra, instrumento, produto, aplicação, ponto, regime, intervenções, unidade e método compatíveis; percentual indefinido se base zero | SOBE/DESCE/ESTAVEL do parâmetro; subir pode ser bom ou ruim conforme a grandeza; amostras excluídas ficam identificadas |
| IA / aprendizado de máquina | Não há modelo treinado, conjunto validado, métricas ou implantação homologada localizados | Não implementados como exigência. Análise espectral causal, prognóstico e probabilidade permanecem lacunas explícitas |

## Cobertura por modalidade contratada

| Modalidade / subtipos | Cobertura de análise | Pendência |
| --- | --- | --- |
| Vibração dinâmica | Zona/criticidade por critério específico e histórico descritivo; evolução só quando validada | Fonte da heurística, contexto de operação, calibração e estudo espectral; assinatura 1×/2×/BPFO/BPFI descrita em discovery não é motor implementado |
| Vibração ODS / estática | Série de grandeza registrada quando comparável; sem faixa rotativa | Malha, fase, modelo/arquivos e critérios estruturais; sem reconstrução de ODS |
| Termografia elétrica / mecânica dinâmica / estática / processos | ΔT e histórico, separados por sistema/contexto; estado pendente | Referência física, regime/carga, método, faixas e recomendações próprios de cada aplicação |
| Hidráulico/lubrificante FQ, EF/CR e CP | Módulo rico tem referências, óleo novo, ISO, GR e tendência conservadora por contexto congelado, sem misturar instrumentos/produtos/métodos | CR contratual não foi equiparado a EF; não estender critérios ao ponto genérico; homologar contexto mínimo e equivalência entre instrumentos/laboratórios |
| Óleo mineral isolante FQ/CR/PCB/2-FAL | Fichas/cálculos e avaliação por catálogo/contexto existentes | Hipóteses de gases/GP, fonte e aplicabilidade; acervo sem snapshot; não afirmar conformidade legal geral de PCB |
| Transformador TTR/RxT, RxI, RxO | Fórmulas e referências por ensaio/registro elétrico existentes | Homologar temperatura/material, conexão, tensão, duração e tolerâncias; não aplicar a motores automaticamente |
| Motor RxI | Registro básico e série genérica | Ficha/tensão/tempo/temperatura e critérios próprios; sem classificação por limite universal de resistência |
| Ultrassom elétrico/mecânico | Série de leitura apenas quando instrumento/contexto comparáveis | Baseline, frequência, ganho, distância/ruído, fenômeno e regra; dB de instrumentos distintos não comparados |
| Espessura | Série em mm; sem percentual de perda como severidade automática | Material, nominal/mínima, malha e metodologia; taxa de corrosão/vida restante não implementadas |
| Alinhamento de eixos/polias | Leitura avulsa e serviço existente parcial | Ficha antes/depois, geometria e tolerâncias por fabricante/rotação; sem sugestão de correção automática |
| Balanceamento em campo | Redução, fase/vetores, economia e análise/OSP existentes | Limiar legado de eficácia 50% e hipóteses do residual não homologados por esta auditoria; não confundir cálculo com certificação do serviço |
| Inspeção sensitiva | Parecer humano, criticidade, laudo e OSP; série numérica não exigida | Checklist por ativo e responsabilidade técnica; ausência de número é legítima |
| Qualidade de energia | Série avulsa por grandeza/contexto; sem severidade universal | Importação, fases, janela/agregação, eventos, norma/edição e critérios; não é estudo completo de energia |

## Rastreabilidade, histórico e eventos

O complemento de medições diretas registra a base da análise em
`criterio_aplicado.analise_preditiva`: versão do motor, entradas, contexto, identificadores
e datas das leituras usadas, parâmetros e cálculos. A consulta da análise deve ler a
base armazenada; cadastrar novos critérios, editar um instrumento ou inserir campanha
posterior não altera o resultado anterior. Alteração técnica cria revisão; edição
de metadados conserva a classificação. Um resultado LEGADO sem snapshot não recebe
explicação histórica fabricada por consulta.

Versões implementadas: `vibracao_v2` para classificação dinâmica reproduzível,
`termografia_delta_v2`, `sensitiva_manual_v2`, `tecnica_pendente_v2`,
`coleta_pendente_v2` (ODS/estática/ausência de critério) e
`historico_descritivo_v1` para estatística. A configuração de evolução contém `evolucao_habilitada` (padrão falso),
`evolucao_fator`, `evolucao_janela` (1–1000), `evolucao_validacao` e `evolucao_fonte`.
Habilitação exige `VALIDADO` e fonte; janela incompleta não eleva criticidade.
O fator 1,5 e janela 3 são valores iniciais do legado, sem autorização implícita.

Instrumento desconhecido ou alterado interrompe a comparação automática conservadora;
não se pressupõe intercambialidade de calibração. As amostras devem ser estritamente
anteriores, com equipamento/cliente e campos de contexto coerentes. Mesmo contexto
em JSON não substitui ficha técnica completa, controle de calibração ou avaliação
do responsável sobre a comparabilidade. Vibração exige RPM informado ou
`parametros.contexto_operacional`; termografia exige carga e temperatura ambiente;
demais técnicas exigem `parametros.contexto_operacional`. Uma chave como `ensaio`
isoladamente não demonstra regime operacional. O formulário genérico atual não tem
campo dedicado a esse contexto, uma lacuna de usabilidade para habilitar comparação
de técnicas além da vibração/termografia pela UI.

A seleção exclui timestamp igual/futuro e campanha com data posterior à inspeção,
usa as últimas N leituras elegíveis e devolve-as em ordem cronológica. Valores não
finitos/ausentes não viram zero. A média anterior zero impede o percentual e a regra
multiplicativa. Estatística `COMPARAVEL` declara apenas comparabilidade pelos campos
registrados; `INCONCLUSIVA` traz o motivo e não vira normalidade.

Fórmulas do histórico direto: média = soma/N; diferença anterior = atual−anterior;
diferença média = atual−média; variação = (atual−média)/|média| ×100, se média ≠0.
Inclinação OLS usa histórico mais leitura atual, x = dias reais desde o primeiro
timestamp, y = grandeza, e b = Σ[(x−média x)(y−média y)]/Σ[(x−média x)²]. Não há
extrapolação de data de falha. O fingerprint identifica a base descritiva registrada,
sem substituir assinatura digital ou comprovação metrológica.

Eventos implementados:

* `EstadoEventoPreditivo` é cursor único por modelo/ID da medição, bloqueado na escrita.
  `EventoPreditivo` tem unicidade modelo/ID/sequência e congela estado anterior/atual,
  versão, evidências, equipamento, inspeção, autoria e OSP vinculada.
* A entrada em ALERTA/CRITICO gera evento/notificação. Saída desses estados também
  registra transição; não encerra OSP automaticamente. A mesma severidade não gera
  outro evento por edição, recálculo ou repetição, mesmo se a OSP anterior foi fechada.
  Uma transição real de saída e retorno pode representar recorrência. Uma **nova
  medição** tem identidade própria e pode originar evento próprio, mesmo no mesmo ativo.
* ALERTA é preventivo e não abre OSP; CRITICO cria ou vincula OSP aberta do mesmo
  equipamento/inspeção, com bloqueio transacional do equipamento. Prioridade/GR/SLA
  da OSP continuam políticas existentes, não novas faixas normativas homologadas.
* Notificação interna é única por evento/destinatário. Canais externos são agendados
  após commit; consulta, cadastro de critério e rollback não devem disparar entrega.
  Canais já confirmados não são enviados outra vez por callback repetido. O acervo
  sem versão de motor registrada não dispara alerta retroativo ao salvar metadados.
  Registro interno não comprova recebimento por e-mail/WhatsApp/push, e a entrega
  externa não é prometida como exatamente uma vez em falhas do provedor. Os callbacks
  são locais ao processo, sem fila persistente de retentativas: se o processo cair
  após commit, o evento e a notificação interna permanecem, mas a entrega externa
  pode não ocorrer. Não foi contratado nem introduzido fornecedor adicional.

Consultas disponíveis:

| Rota | Resultado e segurança |
| --- | --- |
| `GET /api/medicoes-vibracao/{id}/analise-preditiva/` | Snapshot e replay determinístico v2, sem reler critérios mutáveis para classificar |
| `GET /api/medicoes-termografia/{id}/analise-preditiva/` | Base/descritiva registrada, sem fabricar critério térmico |
| `GET /api/medicoes-tecnicas/{id}/analise-preditiva/` | Base/descritiva ou parecer registrado, sem transformar inconclusivo em diagnóstico |
| `GET /api/eventos-preditivos/` | Eventos, evidências e vínculo de OSP; somente leitura, filtros e isolamento por cliente |

O GET de análise usa o mesmo escopo/permissões da medição e nunca reclassifica nem
gera evento/OSP. Replay v2 devolve zona, criticidade e explicação com entradas e
parâmetros congelados. Snapshot legado sem entradas/versão compatível não recebe
replay fictício. As rotas de consulta não constituem uma tela nova de prognóstico.

O replay também reconhece `termografia_delta_v2`, `sensitiva_manual_v2` e
`tecnica_pendente_v2`: reproduz respectivamente o diferencial sem severidade
presumida, o parecer original e a conclusão pendente. `coleta_pendente_v2` e versões
desconhecidas mantêm a base registrada, sem prometer reexecução não implementada.
O laudo identifica a versão e a medição, critério e IDs de histórico utilizados;
suas orientações pedem revisão técnica, sem prescrever intervenção imediata genérica.

Os ensaios ricos têm `contexto_tecnico` e revisões para novos lançamentos, conforme
documento 12. O legado sem esse contexto ainda pode depender do catálogo atual;
parâmetros/código de cálculo e seleção das séries laboratoriais não são abrangidos
automaticamente pelo novo motor de medições diretas. Mudanças futuras exigem governança
de versão e saneamento específico. Serviços corretivos mantêm motor próprio: não se
declara que todo serviço/GR passou a ter o mesmo snapshot novo de `Medicao*`.

Complemento dos fluidos ricos: `comparacao_fluido_v1` exige contexto histórico
registrado, instrumento, ponto, regime e produto/fluido informado. Na tendência,
exclui campanhas de outro instrumento, laboratório, produto, aplicação, ponto,
regime, troca/intervenção, unidade ou método; mantém suas colunas no histórico.
Ausência de contexto/valor medido e amostras futuras/do mesmo dia não são convertidas
em zero nem usadas para afirmar tendência. A API devolve status/motivo, versão,
IDs usados e excluídos em `linhas[].comparacao`. Alterar posteriormente a ficha
da coleta não reescreve esse contexto congelado. O acervo sem esse contexto
específico passa a exibir tendência inconclusiva; dados e referências permanecem.
Os cálculos antigos de ensaios elétricos e de GR conservam suas limitações de fonte
e completude; não foi criado replay geral para os motores laboratoriais/corretivos.

## Validações técnicas pendentes para o cliente

| ID | Decisão a encaminhar | Comportamento enquanto pendente |
| --- | --- | --- |
| AP01 | Confirmar se deseja evolução de vibração; fator, janela mínima, regimes, prazo, autoridade e documento de aprovação | Evolução nova desabilitada; estatística descritiva disponível sem elevar criticidade |
| AP02 | Definir contexto mínimo por técnica (carga/regime, RPM, ponto, ligação, produto, método e baseline), política de troca de instrumento/calibração e data/hora efetiva da medição versus registro tardio | Comparação conservadora; sem contexto/instrumento fica inconclusivo; inclinação usa os timestamps registrados, sem estimar data de falha |
| AP03 | Aprovar cada perfil normativo/edição/aplicabilidade e o mapeamento para criticidade; revisar grupos/bases sem cadastro completo | Sem base/critério aplicável, pendente; critérios históricos não sobrescritos |
| AP04 | Validar referências de termografia por sistema e método, ultrassom, espessura, energia e motores RxI | Sem regras universais ou sugestões de intervenção presumidas |
| AP05 | Definir CR de hidráulicos/lubrificantes e painéis mínimos; confirmar Seção C com GR, limites de atenção de água/viscosidade e completude mínima | EF não é renomeado; sem referência não conta como normal; GR parcial não é risco global validado |
| AP06 | Homologar diagnóstico assistido: quais evidências permitem qual sugestão, grau de incerteza e aprovação humana | Explica condição/faixa; não afirma causa, probabilidade, peça ou prazo automático |
| AP07 | Confirmar política de evento/recorrência/resolução, alerta para ALERTA, OSP para CRITICO, prioridade/SLA e destinatários | Política técnica atual documentada; não cria periodicidade/provedor pago |
| AP08 | Decidir saneamento do legado e revisão/reemissão de laudos quando critério, referência ou programa de cálculo mudar | Preserva acervo e revisões; não inventa regra original nem migra diagnóstico retroativamente |
| AP09 | Homologar qualidade do balanceamento, tolerâncias de alinhamento e hipóteses de economia | Cálculos existentes mantidos com limitação explícita; redução ≥50% não promovida a norma |
| AP10 | Definir eventual prognóstico/IA: objetivo, dados rotulados, métricas, validação, operação e orçamento, somente se desejado | Nenhum modelo/serviço externo obrigatório; sem probabilidade de falha ou vida restante |

## Implementação e verificação desta entrega

Arquivos alterados/criados neste complemento:

* `backend/apps/cadastros/models.py`, `serializers.py` e
  `migrations/0036_evolucao_vibracao_homologada.py`: configuração e validação da evolução.
* `backend/apps/coletas/analise_preditiva.py`, `models.py`, `rules.py`, `views.py` e
  `migrations/0016_instante_medicao_reproduzivel.py`: comparabilidade, estatística,
  replay, snapshots, atomicidade, contexto e timestamp reproduzível.
* `backend/apps/ensaios/contexto.py` e `relatorio_fluidos.py`: contexto congelado e
  tendência de fluido sem comparação entre amostras incompatíveis.
* `backend/apps/notificacoes/models.py`, `preditivos.py`, `services.py`, `signals.py`,
  `serializers.py`, `views.py`, `urls.py` e
  `migrations/0002_eventos_preditivos_idempotentes.py`: eventos, unicidade, consulta
  por cliente e despacho após commit.
* `backend/apps/osp/services.py`, `signals.py`: transições também na edição e
  serialização da criação de OSP por equipamento/inspeção.
* `backend/apps/laudos/services.py`: rastreio de regras e orientação sem prescrever
  intervenção genérica.
* Novos testes: `backend/apps/coletas/test_analise_preditiva.py`,
  `backend/apps/ensaios/test_analise_preditiva.py`,
  `backend/apps/notificacoes/test_eventos_preditivos.py`.
* Testes existentes `coletas/test_conformidade_tecnica.py` e `ensaios/test_fluidos.py`:
  expectativas ajustadas para distinguir contexto técnico de metadados e histórico
  sem evidência de comparabilidade; demais alterações locais anteriores preservadas.
* `README.md` e este documento: cobertura parcial, regras e validações pendentes.

As alterações anteriores do documento 12 já existiam no workspace; este complemento
as preserva. Não houve alteração de frontend, instalação de dependência ou migração
do banco operacional. Aplicar as três migrações deste complemento junto ao deploy
da API, após as migrações da coleta já documentadas.

O timestamp de coleta das três medições usa `default=timezone.now` (migração
`coletas/0016_instante_medicao_reproduzivel.py`), preservando o mesmo instante na
análise e no registro persistido. Os campos continuam somente leitura pela API.
Escrita e revisão usam transação/bloqueio; alterações técnicas de instrumento,
componente, contexto ou instante fazem parte da base. Temperatura auxiliar de
vibração não usada na regra continua metadado, sem reclassificação automática.

QA do motor: `backend/apps/coletas/test_analise_preditiva.py`, **27 testes aprovados**,
0,426 s, comando no diretório `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py test apps.coletas.test_analise_preditiva --noinput --verbosity 1
```

Cobertura: ordenação/janela/corte temporal; exclusão de campanha futura; instrumentos,
componentes, pontos, RPM, direção, parâmetro, modalidade e contexto distintos;
insuficiência de histórico/regime; média zero; valores não finitos/ausentes/negativos e
faixas inválidas; evolução desabilitada/pendente/sem fonte/janela incompleta; fronteira
estrita e teto de criticidade; replay após mudanças no cadastro e inserções posteriores;
GET repetido sem escrita/evento/OSP; permissões/tenant; revisão ao trocar instrumento;
comparação térmica e espessura sem inventar severidade; sensitiva sem número fictício;
identidade temporal do snapshot/persistência e metadado sem reclassificação.

O primeiro run encontrou diferença artificial entre contexto térmico numérico criado
por ORM e o mesmo dado decimal recarregado do banco. O motor agora normaliza campos
conforme o tipo/precisão do modelo; o teste foi mantido e passou. Aviso preexistente:
diretório `staticfiles` local ausente. Os testes do documento 12 são baseline da coleta
e **não** contam como testes novos deste complemento. Fronteiras sintéticas dos testes não
constituem faixas oficiais nem aprovação do cliente.

Verificação conjunta: baseline **336 testes aprovados** antes das mudanças. Foram
acrescentados **51 testes**: 27 de regras/histórico/replay, 7 de comparação de fluidos
e 17 de eventos/integração. Na versão final, **387 testes passaram em 50,436 s**,
com verificações Django sem problemas e nenhuma migração faltante.
Os testes de eventos incluem transições, recuperação e
recorrência, repetição de consulta/recálculo/callback, autoria, isolamento de cliente,
unicidade no banco, rollback integral, ausência de canal externo antes do commit,
replay térmico/sensitivo, rastreio no laudo e indicador de criticidade no dashboard.
Os de fluidos preservam as colunas históricas enquanto recusam instrumento, produto,
método, regime, intervenção ou leitura não comparáveis.

Comandos de verificação no diretório `backend`:

```powershell
.\.venv\Scripts\python.exe manage.py test --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check
```

`git diff --check` também foi executado. O banco de testes usa SQLite; as restrições
de unicidade e os rollbacks foram exercitados. O bloqueio por linha está implementado
para PostgreSQL, mas não foi executado teste de carga concorrente nesse SGBD. Os
avisos preexistentes são a pasta `staticfiles` ausente e paginação de `Carregamento`
sem ordenação explícita. Nesta entrega, os testes de navegador não foram reexecutados:
as alterações são de backend/API e documentação.
