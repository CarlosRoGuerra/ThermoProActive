# 27 — Termografia elétrica pelo modelo RT.TE e área administrativa de IA

Rodada de 16/11/2026. Dois pedidos do cliente (áudios do Fabrício):

1. o relatório de **Termografia Infravermelha em Sistemas Elétricos** deve seguir o modelo
   `RT.TE-2026.05.18.02326` (Acco Brands – Foroni), para ele começar a usar o sistema;
2. a área administrativa precisa de **um lugar para as chaves das APIs de IA e outro para
   ativar o uso delas**.

## 1. Termografia elétrica

O desenho das folhas (capa, contracapas, timbrado, geometria da OSP) continua o do sistema,
igual ao dos outros relatórios. O que passou a seguir o RT.TE é o **conteúdo e a ordem** dele.

### 1.1 O que mudou

| Parte | Antes | Agora (como no RT.TE) |
|---|---|---|
| Carta, item 2 | 2 datas | 3 datas: entra "Upload das OSP´s" |
| Carta, item 4 | lista simples | "4.1. instrumento" (Marca \| Modelo, calibração em mês/ano) e "4.2. Softwares de Análises" |
| Carta, item 6 | 6.1–6.10 | + **6.11 Fluxo de Trabalho** (6.11.1–6.11.7) |
| Carta, itens 7 e 8 | 7 Definição da Técnica, 8 Considerações | **7 Considerações Importantes** (não há Definição da Técnica) |
| Seção C | Área só pelo nome; ordem por TAG | Área "001 - SP1930 [Matriz]", na ordem do código; painéis por nome |
| Seção C longa | folha única que transbordava sem timbrado | repartida em folhas A4, todas com timbrado |
| OSP, imagens | foto à esquerda, térmica à direita | **térmica à esquerda, foto à direita** |
| OSP, medições | 2 colunas na metade da folha | 3 grupos na largura da folha: temperaturas \| I(R), I(S), I(T), I(N) \| % Carga, T. Medida Corrigida, T. Delta Corrigida |
| Cadastro de equipamento | TAG obrigatória e única no setor | TAG opcional; pode repetir no setor com outro nome |

Só o módulo `TERMOGRAFIA` muda. Vibração, balanceamento e os demais mantêm a carta e a OSP de
antes — as opções são declaradas no módulo (`relatorio_tecnico/modulos.py`):
`carta_definicao_tecnica`, `carta_instrumentacao_numerada`, `carta_data_osps`, `secao_c_ordem`
e, no front, `imagensLadoALado`.

Valem para **todos** os relatórios: a Área com código (é o formato do cadastro,
`Area.identificacao`), a ordem das Áreas pelo código e a Seção C repartida em folhas com linhas
de 5 mm.

### 1.2 Decisões tomadas sem o cliente (a confirmar)

- **Fluxo de Trabalho (6.11):** o RT.TE cita o "e-MasterSys®", o sistema anterior. O texto do
  relatório usa "Pred Ativos", o nome desta plataforma (`PLATAFORMA` em
  `relatorio_tecnico/termografia.py`).
- **Data "Upload das OSP´s":** campo novo `Relatorio.data_upload_osps`, na tela do relatório.
  Em branco, a carta usa o dia em que a última OSP do relatório foi gerada no sistema; sem OSP
  e sem data, a linha não aparece.
- **Correção pela carga (C.T.M.):** implementada com a fórmula do Fabrício — ver §1.7. Os
  pontos que o documento dele não define estão lá.
- **Seção B (KPIs):** mantida. No PDF do RT.TE a seção tem só a contracapa.
- **Detalhe do componente:** continua de uso interno (não sai na OSP), como definido antes. No
  RT.TE ele aparece ("Detalhe: [QDG]").

### 1.3 O que continua diferente do PDF, de propósito

São partes do desenho do sistema, travadas pelos gabaritos do cliente (AVSMD):

- cabeçalho das páginas (timbrado do prestador em vez de "Seção C/D" em vermelho);
- número do relatório com hífens (`RT-TI-SE-2026-05-18-00123`) e nomes das contracapas;
- na OSP: nº da OSP no topo esquerdo, "Diagnóstico" (no RT.TE, "Anomalia"), Recomendação e
  Observação acima das imagens, Planejamento antes da tabela "Retorno de Informação" (no
  RT.TE, "Avaliação de Resultados");
- Seção C: um bloco por Área/Setor com um total geral; no RT.TE cada rota abre uma página com
  o próprio total, e a coluna da condição tem a data como título.

### 1.4 Cadastro que precisa de atenção

- O RT.TE usa a condição **NM** (Não Monitorado). O cadastro tem **MNR** (Medição Não
  Realizada) e "MP — Medição Prejudicada" (no RT.TE, "Monitoramento Prejudicado"). É dado do
  cadastro "Condição do equipamento": ajustar lá se a sigla deve ser a do relatório.
- Componentes, anomalias e recomendações da termografia elétrica ainda não estão no catálogo
  (pendência do docs/10): digitados como texto, cada variação vira uma categoria nos KPIs.
- A base da Foroni tem 391 painéis. Não há importação de equipamentos por planilha.

### 1.5 Como foi conferido

Réplica local do RT.TE montada a partir do próprio PDF (394 linhas em 7 rotas, 13 OSPs com as
imagens), só no cliente de teste local: relatório **89** (`/relatorios-inspecao/89`). O PDF do
sistema sai com 36 páginas (o do cliente tem 35) e foi comparado página a página.

Testes: `apps/coletas/test_termografia_eletrica_modelo.py`.

### 1.6 Defeito antigo corrigido nesta rodada

Relatório com alguma OSP cuja tabela "Retorno de Informação" estivesse preenchida **quebrava
inteiro**, na tela e no PDF (`e.trim is not a function`). O dossiê manda as medições e os custos
como número JSON (o encoder do DRF converte Decimal em float), e a folha da OSP chamava `.trim()`
no valor como se fosse texto. O código com o defeito é o que está na produção (commit 4747294).
Corrigido em `modulos/inspecao/folha-osp.tsx`; o teste de PDF com Chromium real
(`laudos/test_pdf_layout.py`) agora tem uma OSP com custos.

### 1.7 Correção da temperatura pela carga (C.T.M.)

Fórmula do documento "Calculo correção de temperatura em função da carga" (Fabrício, 16/11/2026):

    ΔT1 = TM − TA            (medida − ambiente)
    I2  = 0,90 × In          (90 % da corrente nominal)
    ΔT2 = ΔT1 × (I2 ÷ I1)²   (efeito Joule: P ∝ I², ΔT ∝ P)
    T2  = TA + ΔT2           → T. Medida Corrigida da OSP

Exemplo do documento, que é o primeiro teste: In 100 A, I1 70 A, TM 100 °C, TA 30 °C →
T2 = 145,7 °C.

Onde está: `apps/coletas/correcao_carga.py` (fonte única), chamado em `Achado.save()` como o ΔT.
O formulário da análise mostra uma prévia com as mesmas regras (`correcaoCargaPreview` em
`frontend/src/lib/inspecoes.ts`); o que vale é o do backend. Campos novos na análise:
**temperatura ambiente** e **fase da anomalia**. "T. medida corrigida", "ΔT corrigido" e
"T. referência corrigida" deixaram de ser digitados (migração coletas/0019, que também recalcula
as análises já gravadas; no banco local, só 3 do cliente fictício mudaram).

O documento não diz o que segue. As regras de I1, carga, ΔT corrigido e carga mínima foram
confirmadas pelo Fabrício em 18/11/2026:

- **% de carga** = I1 ÷ In quando a nominal e a de trabalho foram medidas (o digitado deixa de
  valer); sem correntes, vale o % digitado. O fator é (90 ÷ carga%)², o mesmo que (I2 ÷ I1)².
- **Qual corrente é a I1** com várias fases medidas: a da fase da anomalia (confirmado); com uma
  fase só, ela; "todas as fases" = a maior. Várias fases sem escolha → não corrige e pede a fase.
- **Corrige qualquer carga, exceto 100 %** (confirmado; a carga é comparada com uma casa, como sai
  na OSP). Acima de 90 % — inclusive acima da nominal — a projeção para 90 % baixa a temperatura;
  em 90 % o fator é 1. Até 18/11 o sistema não corrigia carga de 90 % ou mais.
- **T. Delta Corrigida** = (TM − TR) × fator (confirmado): o ΔT da OSP (TM − TR, 6.1.3) levado
  aos 90 %, igual à diferença entre a medida e a referência corrigidas. Não depende do ambiente.
- **Sem temperatura ambiente:** sai o ΔT corrigido, não a T. medida corrigida (a tela avisa).
- **Sem carga mínima** (confirmado): a fórmula extrapola sem limite (10 % de carga multiplica a
  elevação por 81). O sistema só recusa carga zero e o que não cabe no campo (> 99.999,9 °C).
- O texto do 6.1.5 (do RT.TE) diz que a C.T.M. se aplica com corrente abaixo da nominal; com a
  regra confirmada ela também sai acima da nominal. O texto do glossário não foi mudado.
- O Grau de Risco continua escolhido pelo analista; o ΔT corrigido não muda a classificação.
- A OSP do RT.TE não mostra a temperatura ambiente; a nossa também não.

## 2. Área administrativa de IA

Menu **Administração → Inteligência artificial**, só para o Master interno.

- **Chaves de API** (`/ia/chaves`): provedor (Anthropic, OpenAI, Google ou outro com endereço
  próprio), identificação, chave, modelo padrão. A chave é gravada cifrada (Fernet), não volta
  pela API (só os 4 últimos caracteres) e não entra na trilha de auditoria.
- **Ativação** (`/ia/ativacao`): um cartão por recurso do sistema, com liga/desliga, a chave
  usada e o modelo. Um recurso só liga com uma chave legível. Remover a chave desliga quem a
  usava.

Backend: app `apps/ia` (`ChaveApiIA`, `AtivacaoIA`), rotas `/api/ia/chaves/` e
`/api/ia/ativacoes/`. Variável opcional `IA_ENCRYPTION_KEY`; vazia, a cifra deriva do
`SECRET_KEY` — trocar qualquer uma das duas exige cadastrar as chaves de novo (a tela avisa).

### 2.1 O que ainda NÃO existe

Os dois recursos listados na Ativação são os pedidos pelo cliente e **não foram construídos**:

- apoio ao laudo de vibração (leitura conjunta dos espectros de um ponto);
- leitura do laudo do laboratório de fluidos para preencher os campos do ensaio.

Por isso aparecem como "Em desenvolvimento": a escolha fica gravada e **nada é enviado a
provedor nenhum**. Também não há botão para testar a chave. Quando um recurso for construído,
ele consulta `apps.ia.servico.credencial_do_recurso(...)` — única porta de entrada — e entra em
`RECURSOS_IMPLEMENTADOS`.

Antes de ligar um recurso de verdade: os dados analisados (gráficos, laudos de laboratório de
clientes) passam a sair do sistema para o provedor escolhido. Vale combinar isso com a
contratante (LGPD, Cláusula 13).

## 3. Perguntas para o Fabrício

1. Correção pela carga (§1.7): (a), (c) e (e) respondidos em 18/11/2026 — I1 da fase da
   anomalia, ΔT corrigido = (TM − TR) × fator, sem carga mínima; (b) virou "corrige qualquer
   carga, exceto 100 %". Falta só (d): 90 % como alvo para todos os equipamentos?
2. O 6.11 pode citar "Pred Ativos" no lugar do "e-MasterSys®"?
3. A data "Upload das OSP´s" pode ser a de geração das OSPs no sistema?
4. NM × MNR e o nome do MP: qual sigla e qual texto valem?
5. O "Detalhe" do componente deve sair na OSP, como no RT.TE?
6. Na Seção C, quer um bloco por rota com total próprio e a data como título da coluna?
7. Qual provedor de IA a empresa vai contratar, e qual dos dois recursos vem primeiro?
