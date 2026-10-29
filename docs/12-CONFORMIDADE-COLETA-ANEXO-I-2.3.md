# Conformidade da coleta técnica — Anexo I, item 2.3

Auditoria de 21–22/10/2026. Escopo: coleta direta (`Inspecao`/`Medicao*`), coleta por rota
(`Carregamento`/`ItemInspecao`/`Achado`), ensaios laboratoriais e serviços corretivos,
com regressão de análise, laudos e OSP.

## Conclusão e fontes

As dez categorias têm mapeamento abaixo. Isso **não equivale à implementação
completa dos estudos e fichas de todos os subtipos**. ODS, alinhamentos, motores,
ultrassom, espessura e qualidade de energia ainda têm coleta parcial, detalhada nas
linhas e pendências. A existência de um seletor ou de JSON não comprova cobertura
técnica completa.

Fontes efetivamente disponíveis:

* [Contrato](../contrato.txt), Anexo I 2.3.1 e 2.3.2, páginas 5–6: enumera as
  modalidades, inspeções, medições manuais, arquivos/imagens, histórico,
  geolocalização e data/hora. Sensores IoT estão expressamente marcados como futuro.
  **Não define campos específicos, unidades obrigatórias, normas, faixas ou fórmulas.**
* [Discovery técnico](01-DISCOVERY-modulos-tecnicos.md): proposta de campos e perguntas.
  Seu próprio aviso exige confirmar os limiares com o cliente; não é homologação.
* [Cadastro por tipo e fluidos](11-CADASTRO-POR-TIPO-E-FLUIDOS.md), seções 4–7:
  registra decisões anteriores, referências por escopo e relatórios de exemplo.
  A referência ao acordo de vibração Classe II consta desse documento; a auditoria
  não verificou a norma original nem a aprovação externa.
* [Discovery corretivo](04-DISCOVERY-balanceamento-e-economia.md) e
  [análise técnica de balanceamento](07-analise-tecnica-balanceamento.md): serviço
  existente, massas, fases, corridas e economia.
* Código e migrações de `apps/coletas`, `apps/ensaios`, `apps/servicos`,
  `apps/laudos` e `apps/osp`; formulários e testes correspondentes. As fichas PDF
  citadas nos documentos não foram novamente homologadas nesta auditoria.

## Leitura da matriz

**D** = modelo dedicado existente; **G** = leitura genérica com subtipo explícito,
grandeza, valor, unidade, referência opcional e JSON; **P** = pendência de definição
ou implementação. Unidades abaixo descrevem a implementação e as fontes internas,
sem conferir caráter normativo. Campos obrigatórios da API são escolhas de
implementação; sua obrigatoriedade contratual específica depende de homologação.

Contexto comum da coleta direta: inspeção, cliente, técnico responsável, equipamento,
ponto, instrumento/componente opcionais, data/hora de criação, autor da coleta e
autor da alteração. Coordenadas pertencem à inspeção. Na coleta por rota, o item
vincula equipamento, carregamento, relatório, analista e instrumento. Nos ensaios,
resultado vincula item, ensaio, instrumento/laboratório, origem, datas e conclusão.

## Matriz de cobertura por subtipo contratado

| Item | Categoria / subtipo | Dados existentes e situação inicial | Complemento e validação nesta entrega | Cobertura restante / homologação |
| --- | --- | --- | --- | --- |
| 2.3.2.1.1 | Vibração — mecânicos dinâmicos | **D** `MedicaoVibracao`: mancal, H/V/A, parâmetro, RPM, velocidade RMS mm/s, aceleração g, deslocamento pico a pico µm, fator de crista, temperatura °C; sem subtipo | `MEC_DINAMICO`; amplitudes não negativas; campos antes ocultos disponíveis; critério vigente na data da inspeção e sua origem registrados; sem classe/critério/suporte aplicável fica pendente | FFT/envelope como dados estruturados e condição operacional ainda incompletos; confirmar edição, classe/grupo, suporte e procedimento de tendência |
| 2.3.2.1.2 | Vibração — ODS | Sem identificação própria; somente dados globais e imagens da rota | `ODS`; frequência Hz e fase graus no JSON, números finitos, frequência ≥ 0 e fase em [0,360); nenhuma severidade rotativa aplicada | **P** malha/coordenadas, referência de fase, amplitude por vetor, sincronização, arquivos e reconstrução/animação; frequência/fase continuam opcionais até ficha homologada |
| 2.3.2.1.3 | Vibração — mecânicos estáticos | Mesma medição de vibração dinâmica | `MEC_ESTATICO`; amplitudes e frequência/fase registráveis; classificação pendente | **P** deslocamentos/ressonâncias, critérios por estrutura e ficha específica; o formulário pontual não substitui estudo estrutural |
| 2.3.2.2.1 | Termografia — elétricos | **D** `MedicaoTermografia.sistema`; temperaturas do ponto/referência/ambiente °C, emissividade, carga %, ΔT | Emissividade explícita em novas coletas e 0 < ε ≤ 1; carga não negativa; carga mostrada só no elétrico; ΔT aritmético preservado e sem classificação genérica | Confirmar método da referência, corrente/carga, emissividade, norma/edição e faixas aplicáveis; sobrecarga >100% não é recusada por limite artificial |
| 2.3.2.2.2 | Termografia — mecânicos dinâmicos | **D** sistema já disponível, mesmos campos térmicos | Campos pertinentes condicionais; ΔT sem diagnóstico automático universal | **P** regime/carga mecânica, atrito, lubrificação e critérios da aplicação |
| 2.3.2.2.3 | Termografia — mecânicos estáticos | **D** sistema já disponível, mesmos campos térmicos | Emissividade/temperaturas validadas; sem regra elétrica aplicada | **P** isolamento, revestimento, geometria, referência e critérios próprios |
| 2.3.2.2.4 | Termografia — processos industriais | **D** sistema já disponível, mesmos campos térmicos | Seleção explícita; carga elétrica ocultada; classificação pendente | **P** produto, etapa, regime, temperatura esperada e limites do processo |
| 2.3.2.3.1.1 | Fluidos hidráulicos/lubrificantes — FQ | **D** `ColetaFluido`, `ProdutoFluido`, ensaio FQ e parâmetros: viscosidade cSt, água ppm, TAN mgKOH/g, densidade e demais parâmetros ativos do catálogo | **G** direto distingue aplicações `HIDRAULICO`/`LUBRIFICANTE` e `ensaio=FQ`; fluxo rico conserva unidades/métodos; valores, revisões e critérios registrados no lançamento | Confirmar painel por produto/aplicação, óleo novo, obrigatoriedade, fonte e vigência de cada referência |
| 2.3.2.3.1.2 | Fluidos hidráulicos/lubrificantes — CR | Contrato diz CR; fluxo rico existente oferece **EF** (elementos em ppm). Não há equivalência contratual demonstrada | **G** `ensaio=CR`, grandeza e unidade informadas conforme laboratório, pendente de critério; não renomeia EF nem migra resultados | **P** cliente deve definir CR nesta família e confirmar se corresponde a EF; ficha própria/importação dependem dessa decisão |
| 2.3.2.3.1.3 | Fluidos hidráulicos/lubrificantes — partículas | **D** CP: contagens >4, >6, >14 e opcionais >21, >38, >70 µm(c)/mL, ISO 4406 e NAS informada pelo laboratório | **G** direto coleta contagem por tamanho em part./mL; deixa de representar código ISO como decimal; família/ensaio e concentração não negativa validados; referência/base preservadas no dedicado | Confirmar meta por equipamento/aplicação e método; cálculo ISO permanece no módulo rico, não é inventado para uma contagem isolada |
| 2.3.2.3.2.1 | Minerais isolantes — FQ | **D** `ColetaOleo`, inspeção visual, ensaio FQ: viscosidade, densidade, fator de potência, neutralização, água, rigidez dielétrica, tensão interfacial, cor/aparência | **G** `MINERAL_ISOLANTE`/FQ; parâmetros/catálogo do dedicado registrados para novos resultados; estados de valor e datas validados | Referências/normas sem edição ou origem suficiente do catálogo antigo precisam de confirmação de aplicabilidade; não são prescritas pelo contrato |
| 2.3.2.3.2.2 | Minerais isolantes — CR | **D** cromatografia: H2/O2/N2/CH4/CO/CO2/C2H4/C2H6/C2H2 ppm; TG/TGC calculados pelo motor existente | Identificação explícita da família; snapshot dos parâmetros; sem aplicar limite genérico de fluidos ao registro direto | Confirmar método, tratamento de resultado censurado e critérios dos gases conforme tipo/condição do transformador |
| 2.3.2.3.2.3 | Minerais isolantes — PCB | **D** parâmetro PCB mg/kg; estado e LD/LQ | **G** PCB só na família isolante; mg/kg/ppm e concentração não negativa; não detectado/abaixo de LD sem evidência suficiente não vira automaticamente conforme | Confirmar método, LD/LQ e fonte/aplicabilidade do limite do catálogo; a auditoria não certifica conformidade legal |
| 2.3.2.3.2.4 | Minerais isolantes — 2-FAL | **D** 2FAL, 2FOL, 5HMF, 2ACF, 5MEF mg/kg e GP; cálculo De Pablo já existente | **G** 2FAL só no isolante; unidades/concentrações validadas; valores e critérios novos preservados | Confirmar método, validade da estimativa de GP e seus pressupostos; fórmula existente não foi criada ou homologada por esta auditoria |
| 2.3.2.4.1.1 | Transformadores — TTR / RxT | **D** registro elétrico: TAP/tensão/temperaturas/umidade; RXT: nominal, medida por série, erro % calculado | **G** `TRANSFORMADOR_TTR`: relação adimensional separada do desvio %; relação não negativa; dedicado registra placa/TAP/parâmetros no contexto histórico | Confirmar conexões, fases, grupo, relação nominal, tensão e tolerância por norma/edição; sem equivaler TTR ao percentual de erro |
| 2.3.2.4.1.2 | Transformadores — RxI | **D** tensão V, resistência MΩ, série/ligação, tempo s; IP/IA existentes | **G** `TRANSFORMADOR_RI`; resistência não negativa, unidade de resistência coerente; tempo não negativo e chave parâmetro/série/posição única no dedicado | Confirmar tensão/duração, temperatura, IP/IA e edição/aplicabilidade do critério existente |
| 2.3.2.4.1.3 | Transformadores — RxO | **D** pares AT em Ω/BT em mΩ, correção térmica existente, placa/TAP/temperatura | **G** `TRANSFORMADOR_RO`; resistência não negativa, Ω/mΩ/µΩ; contexto de cálculo do dedicado preservado | Confirmar material, referência térmica, ligação e comparação entre fases; não aplicar tolerância percentual universal |
| 2.3.2.5.1.1 | Motores — resistência de isolação | Somente **G** sem identificação de motor | `MOTOR_RI`, resistência não negativa e unidade Ω/kΩ/MΩ/GΩ; pendente de classificação | **P** ficha dedicada com tensão de ensaio, tempos, ligações, temperatura/umidade e índices aplicáveis; não herda ficha/critério de transformador |
| 2.3.2.6.1.1 | Ultrassom — elétrico | **G**, um nível sem subtipo, antes comparado com limiar universal | `ELETRICO`, unidade dB/dBµV, frequência opcional; sem diagnóstico automático por dB genérico | **P** frequência/faixa do instrumento, ganho, distância, ruído/base, tipo de evidência e fenômeno; dB de instrumentos distintos não são comparados automaticamente |
| 2.3.2.6.1.2 | Ultrassom — mecânico | **G**, mesmo limiar universal | `MECANICO`, unidade validada e pendente de critério | **P** regime/carga, baseline, localização, frequência/ganho e classificação por aplicação |
| 2.3.2.7 | Espessura | **G** espessura e referência, antiga classificação por perda percentual universal | `ESPESSURA`, mm e valor ≥0; não calcula vida remanescente ou severidade sem dados suficientes | **P** material, método/velocidade sônica, malha, nominal/mínima, revestimento, incerteza e datas para corrosão; zero não é automaticamente diagnóstico |
| 2.3.2.8.1.1 | Corretiva — laser entre eixos | `ServicoCampo` aceita tipo; ficha rica/relatório de alinhamento ainda planejados; **G** sem modalidade | `ALINHAMENTO_EIXOS`, leitura/unidade/referência e registro pendente | **P** antes/depois, plano H/V, angular/paralelo, distância dos pés, correções, RPM/tolerância do fabricante e evidência do laser; registro pontual não conclui serviço completo |
| 2.3.2.8.1.2 | Corretiva — laser entre polias | Mesma limitação de alinhamentos | `ALINHAMENTO_POLIAS`, leitura identificada e sem limite herdado do alinhamento de eixos | **P** geometria, deslocamento/ângulo, polias/correias, antes/depois, tolerância e ficha/relatório específicos |
| 2.3.2.8.1.3 | Corretiva — balanceamento em campo | **D** `ServicoCampo`, planos, massas g, ângulos graus, Reference/Trial/Trim mm/s/fase, resultados, economia, OSP e análise técnica | **G** `BALANCEAMENTO` para leitura avulsa com unidade própria, sem limiar de alinhamento; fluxo rico existente preservado e testado | Homologar critérios de qualidade/rotação/residual e hipóteses de economia do serviço; motor independente de balanceamento ainda possui critérios legados, não certificáveis por esta auditoria |
| 2.3.2.9 | Inspeção sensitiva | **G** parecer em JSON e fluxo `Achado` qualitativo por rota | `SENSITIVA`, parecer explícito NORMAL/ALERTA/CRITICO ou pendente; observação; não é inferido de limiar numérico | Checklist e condições obrigatórias por aplicação dependem do cliente; não substitui medições quantitativas por zero fictício |
| 2.3.2.10 | Qualidade de energia | **G** valor/grandeza/unidade, antigo limite universal | Modalidade explícita; THD tensão, THD corrente e desequilíbrio identificados; nenhum limiar comum aplicado | **P** tensão/corrente por fase, frequência, FP, harmônicos, demanda, eventos, janela/agregação e importação do analisador; sem série temporal não constitui estudo completo |

## Regras corrigidas e compatibilidade

1. Novas medições genéricas sem critério confirmado ficam `PENDENTE`, com
   `criticidade=""`. ODS/estáticas não passam por faixas de máquinas rotativas.
   Novas termografias conservam o cálculo de ΔT, sem regra elétrica universal.
  Parecer sensitivo explícito continua classificando e gerando OSP quando crítico.
  Sensitiva aceita valor nulo; ODS/estática exigem ao menos uma amplitude medida
  entre velocidade, aceleração ou deslocamento, sem preencher velocidade fictícia.
  Vibração dinâmica continua exigindo velocidade RMS.
2. `LEGADO` identifica classificações antigas da coleta direta, sem inventar a
   base original. Alterar metadados ou cadastrar outro critério não reclassifica
   essas linhas. Edição técnica arquiva o estado anterior e registra a nova base.
   Critérios/situação/histórico são somente leitura na API.
3. Novos resultados de ensaios pela API/admin registram `contexto_tecnico`:
   parâmetros/unidades/métodos/limites, referências por escopo, base do óleo novo,
   data da campanha e placa/registro elétrico pertinentes. Consulta, histórico e
   fichas usam esse contexto; cadastrar/editar referências não muda sua avaliação.
   Metadados preservam os critérios; reenviar valores/situação registra nova base,
   com revisão do estado anterior, autor e data/hora. Exclusão de resultado pela
   API é lógica e conserva valores/revisões.
4. Resultados de ensaios **anteriores**, sem `contexto_tecnico`, mantêm o caminho
   legado e não recebem base histórica fictícia. Sua avaliação ainda pode depender
   do catálogo atual: é necessária decisão de saneamento/baseline antes de alterar
   retroativamente referências usadas por esse acervo. Escritas diretas por ORM,
   importadores ou SQL precisam usar o serviço de registro para obter a mesma
   garantia; `bulk_create` não é um mecanismo de auditoria.
5. Estados medido/qualitativo, abaixo de LD/LQ, não detectado, acima de escala e
   indisponível não são convertidos em zero. Valor medido exige número ou texto;
   estado não medido recusa número simultâneo. LD/LQ informado deve ser positivo.
   A conformidade de um resultado censurado exige LD/LQ compatível com o critério;
   sem essa evidência, fica sem avaliação. Chaves repetidas de
   parâmetro/série/posição e datas invertidas, inclusive em PATCH, são recusadas.
6. Equipamento deve pertencer ao cliente da inspeção e componente ao equipamento;
   tipo/subtipo/ensaio devem ser compatíveis. Latitude/longitude são validadas.
   Resultado não pode ser realocado a outro item/ensaio. Cliente continua somente
   leitura e limitado ao próprio escopo. A autoria histórica desconhecida fica nula,
   sem atribuição retroativa ao usuário que roda a migração.
7. A ausência de critério não aparece como “Normal” no laudo. Conclusão/recomendação
   apontam avaliação pendente. Anomalias explicitamente identificadas continuam no
   fluxo de OSP. A classificação geral da inspeção não conclui normalidade quando
   há medições pendentes. Dashboard e portal mostram as pendências; equipamento
   com leitura normal e outra pendente não é agregado como normal. Exclusão física
   de medições e de inspeções com medições/laudos/OSP fica bloqueada até definição
   da política de retenção; consulta/edição continuam disponíveis.

## Rastreabilidade e integrações

| Requisito de 2.3.1 | Evidência / limite |
| --- | --- |
| Inspeção e inserção manual | Coleta direta e rota existentes, modalidades identificadas e testes de persistência/consulta/edição |
| Imagens | `AchadoImagem` e foto de `InspecaoVisualColeta` preservados; **sem vínculo de anexo próprio em cada `Medicao*` direta** |
| Arquivos | Não foi encontrado upload geral de arquivo bruto/documento em `Medicao*`/`ResultadoEnsaio`; **lacuna de implementação**, exige definir formatos e vínculos, sem confundir com fotos ou com a origem `ARQUIVO` |
| Histórico/autoria/data | Medição direta, contexto/revisões de ensaios e histórico por equipamento; limites do acervo legado descritos acima |
| Instrumento/equipamento | FKs existentes preservadas e instrumento exposto no formulário direto; não foi imposta obrigatoriedade/calibração sem regra aprovada |
| Geolocalização | Latitude/longitude no evento de inspeção, com limites geográficos; não há captura específica por leitura/ensaio de rota |
| IoT | Futuro conforme contrato; não declarado entregue |
| Análise/laudos/OSP | Regressões cobrem fluxos existentes e classificação pendente; os módulos planejados continuam respondendo indisponibilidade, sem herdar layout de outra técnica |

## Pendências para o cliente e decisões de implementação

| ID | Pergunta / decisão necessária | Comportamento enquanto pendente |
| --- | --- | --- |
| P01 | Qual ficha e quais campos obrigatórios devem existir para cada subtipo (incluindo não aplicável/não realizado)? | Preserva campos conhecidos e registro pontual; não declara estudo completo |
| P02 | O que significa CR em hidráulicos/lubrificantes? É EF, cromatografia ou outro ensaio? | CR permanece distinto de EF, sem migração automática |
| P03 | Quais normas, edições, fontes, aprovação técnica, escopos e vigências de cada critério? | Sem critério aplicável não há classificação automática; catálogos legados de ensaios exigem revisão, não recebem certificação por esta entrega |
| P04 | Qual malha, referência de fase, amplitude/unidade e arquivos compõem ODS? Quais critérios estruturais para estáticos? | Registro pontual parcial, sem classificação ISO de rotativos |
| P05 | Qual método térmico por sistema, referência, regime/carga, emissividade, reflexão, distância e condições ambientais? | ΔT informativo; critério específico bloqueado |
| P06 | Quais conexões, tensões, tempos, temperaturas, material e correções para ensaios elétricos, separando motor de transformador? | Motor com leitura básica; fichas de transformador e fórmulas existentes preservadas, sem tolerância universal nova |
| P07 | Quais baselines, frequências, ganho/distância para ultrassom e dados mínimos/material para espessura? | Sem diagnóstico automático nem corrosão/vida remanescente presumida |
| P08 | Quais fichas, antes/depois, tolerâncias do fabricante e evidências dos alinhamentos? Quais critérios de balanceamento/economia estão homologados? | Alinhamentos continuam parciais; balanceamento mantém serviço existente |
| P09 | Qual janela, fases, eventos e formato do analisador de energia? Qual checklist sensitivo por ativo? | Leituras avulsas/parecer, sem estudo completo de energia |
| P10 | Qual política para corrigir/reclassificar acervo sem critério original, revisar laudos emitidos e preservar a base antiga? | Sem reconstrução fictícia; resultado legado de ensaio depende de saneamento antes de mudar catálogos retroativamente |
| P11 | Quais arquivos/anexos são exigidos, formatos, vínculos, tamanho/retenção, cancelamento/exclusão e instrumentos/calibração obrigatórios? | Evidências atuais preservadas; upload geral e anexos diretos permanecem lacunas identificadas; exclusão física de medições protegida |

P01–P11 são pendências reais. Após definição técnica, ainda haverá implementação de
fichas/cálculos/importação e testes correspondentes; esta entrega não os considera
concluídos. Alterações de critérios devem criar nova base com origem/vigência,
preservando os resultados anteriormente registrados.

## Arquivos desta entrega

Backend:

* `backend/apps/coletas/models.py`, `serializers.py`, `views.py`, `rules.py`,
  `rules_tecnicas.py`: modalidades, contexto, autoria, critérios e validação.
* `backend/apps/coletas/migrations/0012_medicaotecnica_classificacao_status_and_more.py`,
  `0013_medicaotecnica_coletado_por_and_more.py`, `0014_alter_medicaotecnica_valor.py`,
  `0015_alter_medicaovibracao_velocidade_rms.py`: alterações compatíveis, sem reclassificar o acervo.
* `backend/apps/ensaios/models.py`, `contexto.py`, `serializers.py`, `views.py`,
  `admin.py`, `calculos.py`, `calculos_fluidos.py`, `relatorio.py`,
  `relatorio_fluidos.py`, `migrations/0017_contexto_tecnico_revisoes.py`:
  validação e preservação de critérios/revisões.
* `backend/apps/laudos/services.py`: ausência de critério indicada no laudo.
* `backend/apps/coletas/test_conformidade_tecnica.py`,
  `backend/apps/ensaios/test_conformidade_resultados.py` e
  `backend/apps/ensaios/tests.py`: validações, histórico e regressão.

Frontend:

* `frontend/src/app/(admin)/inspecoes/[id]/page.tsx`,
  `frontend/src/app/portal/inspecoes/[id]/page.tsx`,
  `frontend/src/features/inspecoes/coleta-tecnica.ts`,
  `frontend/src/lib/types.ts`: campos condicionais, unidades, erros e consulta.
* `frontend/src/app/(admin)/dashboard/page.tsx`, `frontend/src/app/portal/page.tsx`,
  `frontend/src/app/portal/equipamentos/page.tsx`: pendências visíveis sem concluir
  normalidade ou confundir leitura pendente com equipamento nunca medido.
* `frontend/tests/e2e/coleta-tecnica.spec.ts`: fluxos de formulário no Chromium com
  API controlada pelo teste.

Documentação: este arquivo e o indicador de cobertura em `README.md`.

Já havia alterações locais em `ensaios/test_fluidos.py`, migração
`ensaios/0016_referencia_potassio.py`, `docs/11-*`, `catalogos.ts`,
`registro-fluido.tsx` e `tsconfig.tsbuildinfo`, além de arquivos não rastreados.
Foram preservadas e não são atribuídas a esta entrega. A migração nova de ensaios
depende da `0016` já existente no workspace; incluir ambas no versionamento/deploy.

## Verificação

Baseline antes das mudanças: **277 testes, OK**. Verificação final do backend:

```powershell
# Diretório backend
.\.venv\Scripts\python.exe manage.py test --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py check
```

**336 testes passaram em 53,220 s**, incluindo 59 novos testes; nenhuma migração
faltante e verificações Django sem problemas. Cobrem subtipos, persistência,
consulta/edição parcial, permissões/isolamento, autoria, retenção, unidades,
fronteiras sintéticas, não finitos, critério vigente, snapshots/revisões,
histórico sem campanhas futuras, estados LD/LQ e integração laudos/OSP/indicadores.
Os números de fronteira dos testes são critérios sintéticos de teste, não novas
regras oficiais. Avisos preexistentes: pasta `staticfiles` ausente e paginação de
`Carregamento` sem ordenação explícita.

Frontend: `tsc --noEmit --incremental false` e `npm run build` aprovados na versão
final. No build final servido localmente, **15/15 testes Chromium passaram em
3,6 s**: 7 casos novos de coleta/consulta e 8 regressões de coleta de fluidos e
relatórios de fluidos/corretiva/preditivo. Comando no diretório `frontend`:

```powershell
.\node_modules\.bin\playwright.cmd test tests/e2e/coleta-tecnica.spec.ts tests/e2e/coleta-fluido.spec.ts tests/e2e/relatorio-fluidos.spec.ts tests/e2e/relatorio-corretivo.spec.ts --project=chromium --reporter=list
```

A API é mockada nos testes de navegador:
validam interação, envio e apresentação; persistência real é verificada na suíte
Django. `git diff --check` aprovado. O arquivo `tsconfig.tsbuildinfo` preexistente
foi preservado (hash SHA256 conferido); o servidor temporário de testes foi encerrado.

As migrações são exercitadas no banco de testes isolado. O banco operacional local
não foi migrado por esta auditoria; aplicar as novas migrações junto ao deploy da
API antes de disponibilizar o frontend correspondente.
