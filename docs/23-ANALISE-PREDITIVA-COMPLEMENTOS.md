# Análise preditiva — complementos (Anexo I 2.4.1.3, 2.4.1.5, 2.4.2.4)

Complemento do documento 13. Implementado no app `backend/apps/preditiva`, sem
serviço externo, sem IA obrigatória e sem biblioteca nova (estatística em
`statistics`/`math`).

## Princípios que valem para tudo abaixo

- Tendência de medição não é previsão de falha. Nenhum número aqui é probabilidade
  de falha, vida útil remanescente ou diagnóstico.
- Sem limite cadastrado e validado, não há data estimada. Sem critério, não há
  classificação nova.
- Todo parâmetro que decide um número ou uma sugestão é cadastro do Master, com
  origem, fonte e vigência. O que o sistema traz é marcado como
  **PROVISÓRIO — a confirmar pelo cliente**.
- A sugestão nunca é aplicada sozinha: o analista aceita, edita ou rejeita, e a
  decisão é registrada.

## 1. Tendência até o limite de alarme (2.4.1.3)

Endpoint: `GET /api/preditiva/tendencias/{vibracao|termografia|tecnica}/{id}/`
Só leitura. Respeita o escopo de cliente (`escopo_cliente`). Nada é gravado.

### Série comparável

Mesmo contexto exato do histórico do motor atual (`coletas/analise_preditiva.py`):
mesmo equipamento, componente, instrumento, ponto, direção/parâmetro/regime e
parâmetros. Entram apenas leituras anteriores à medição analisada e de data de
inspeção não posterior. Valor ausente ou inválido não vira zero.
A janela é a última N leituras (padrão 8), incluindo a analisada.

### Modelos

- Linear: `y = a + b·x`, `x` em dias reais desde a primeira leitura (datas desiguais
  são tratadas pelo tempo real).
- Exponencial (log-linear): `ln y = a + b·x`, só se todos os valores forem > 0.
  O R² ajustado é medido na escala original, para comparar com a linear pela mesma
  variável dependente.
- Critério de escolha: o exponencial só é usado se seu R² ajustado superar o linear
  em pelo menos a margem (padrão 0,05). Caso contrário, linear.

### Regras de status

| Status | Quando |
| --- | --- |
| `INSUFICIENTE` | menos pontos que o mínimo (padrão 4), ou leitura inválida |
| `SERIE_CONSTANTE` | todos os valores iguais |
| `SEM_TENDENCIA` | inclinação não significativa a 95% (|t| ≤ t crítico), ou R² ajustado abaixo do mínimo (padrão 0,50) |
| `TENDENCIA` | inclinação significativa a 95% e R² ajustado suficiente; sentido SOBE ou DESCE |

Inclinação significativa: `t = b / EP(b)` com gl = n − 2; t crítico bilateral de
95% da tabela de Student (para gl > 30 usa o valor de gl = 30, 2,042, mais largo
que o assintótico, de forma conservadora). Erro-padrão nulo (ajuste exato) é
tratado como significativo se b ≠ 0.

### Projeção por limite

Para cada limite aplicável (ALERTA e CRITICO):

- `ATINGIDO`: a última leitura observada já cruzou o limite.
- `NAO_CONVERGE`: a inclinação se afasta do limite (ou o limite não é representável
  no modelo, p.ex. ≤ 0 no exponencial).
- `ESTIMADO`: data em que a reta de tendência cruza o limite, com intervalo de
  confiança de 95% da reta. O início do intervalo usa a borda da banda que se
  aproxima do limite primeiro; o fim, a borda oposta. Cruzamento fora da banda
  dentro do horizonte aparece como data indefinida no fim do intervalo.
- `FORA_DO_HORIZONTE`: cruzamento além do horizonte configurado (padrão 365 dias).

O intervalo é da RETA de tendência (média), não de uma nova medição.
Limite inferior (sentido INFERIOR) é tratado com o mesmo cálculo no sentido
oposto.

### Fontes de limite

- **Vibração**: critério normativo vigente (`CriterioSeveridadeVibracao`, com as
  mesmas condições de aplicabilidade da classificação). ALERTA = limite B/C;
  CRITICO = limite C/D. Critério LEGADO ou base (G1/G2) não informada → sem limite.
- **Termografia e demais técnicas**: `LimiteAlarmeSerie` do cadastro, só com
  situação VALIDADA e fonte. Sem isso, a série é descrita, mas nenhuma data é dada
  (`limite_nao_validado` ou `sem_limite_cadastrado`).
- **Fluidos** (`apps/preditiva/fluidos.py`, `GET /api/preditiva/tendencias/fluidos/{resultado}/{codigo}/`):
  série das campanhas anteriores do MESMO equipamento, ensaio e parâmetro, com o mesmo
  `comparacao_fluido` registrado no resultado, mesma unidade e mesmo método. Limite: a
  referência vigente do escopo da coleta (`ResolvedorReferencias`), só dos tipos MÁXIMO e
  MÍNIMO com valor numérico. Sem contexto registrado → INSUFICIENTE
  (`contexto_historico_nao_registrado`); sem referência fixa (variação %, código ISO,
  qualitativo) → `sem_limite_fixo_para_projetar`. Campanhas antigas sem contexto não são
  projetadas (é o mesmo critério da tendência contextual já existente em ensaios).

### Parâmetros estatísticos (cadastro `ConfiguracaoTendencia`)

| Parâmetro | Padrão provisório | Papel |
| --- | --- | --- |
| Pontos mínimos | 4 | abaixo disso, insuficiente |
| Janela | 8 | últimas N leituras |
| R² ajustado mínimo | 0,50 | ajuste abaixo disso não projeta |
| Horizonte (dias) | 365 | cruzamento além disso não gera data |
| Margem do exponencial | 0,05 | critério de escolha do modelo |

São parâmetros estatísticos, não limites de alarme. O cliente confirma.

### Pontos atípicos

Marcados pelo z modificado (Iglewicz-Hoaglin, |z| > 3,5, com MAD). **Não são
removidos**: permanecem na regressão e aparecem marcados na resposta.

### Texto obrigatório

"Estimativa estatística da medição, não probabilidade de falha, vida útil
remanescente ou diagnóstico. Depende de série comparável e do limite cadastrado."

## 2. Índice de risco por equipamento (2.4.1.5)

Endpoint: `GET /api/preditiva/risco/ranking/` (`?area=`, `?setor=`, `?cliente=` para
a equipe interna). Escopo de cliente aplicado: o Portal só vê o próprio cliente.

### Fórmula

    p = w_sev · (s − 1)/2 + w_tend · (t − 1)/2        proxy de probabilidade, 0–1
    c = consequência[criticidade do ativo] / máximo    0–1
    índice = 100 · p · c                               0–100

- `s` = severidade: pior criticidade CLASSIFICADA entre as últimas leituras de cada
  série do equipamento (NORMAL=1, ALERTA=2, CRITICO=3).
- `t` = tendência: pior entre as séries (ATINGIDO/ESTIMADO=3, TENDENCIA=2,
  SEM_TENDENCIA/SERIE_CONSTANTE=1; INSUFICIENTE não entra).
- `c`: criticidade A/B/C do cadastro do equipamento, via mapa da matriz.

Sem `s`, `t` ou criticidade do ativo, o índice é **None** (incompleto), com as
pendências listadas. Não se assume "normal" no lugar de dado ausente. Equipamentos
completos vêm primeiro, por índice; os incompletos depois.

### Matriz (cadastro `MatrizRisco`)

Pesos (somam 1), mapa de consequência A/B/C (inteiros 1–10), faixas crescentes
terminando em 100. Escolha: a do cliente antes da global; dentro da vigência.
Sem cadastro, vale a reserva do sistema.

Padrão do sistema (migração `0002`): pesos 0,60/0,40; consequência A=3, B=2, C=1;
faixas BAIXO ≤25, MODERADO ≤50, ALTO ≤75, MUITO ALTO ≤100. Situação
**PROVISÓRIA — a confirmar pelo cliente**.

O índice é priorização, não probabilidade. A resposta traz esse aviso e a matriz
usada (nome, origem, situação).

### Decomposição

Cada item traz severidade, tendência e criticidade com seus scores e contribuições,
a fórmula, a matriz, e as séries com a projeção de cada uma. Assim se vê por que o
equipamento tem aquele risco.

## 3. Sugestões técnicas assistidas (2.4.2.4)

Endpoints (equipe interna):

- `GET /api/preditiva/sugestoes/?achado={id}`: lista de sugestões e motivo quando vazia.
- `POST /api/preditiva/aceitacoes-sugestao/`: registra decisão `ACEITA`, `EDITADA`
  (exige outra recomendação final) ou `REJEITADA`. Recusa sugestão que não existe
  mais no achado.
- `GET /api/preditiva/aderencia-sugestoes/`: taxa de aderência por origem, usando a
  última decisão de cada (achado, sugestão, origem). Taxa = (aceitas + editadas) / total.

### Fonte 1 — regra cadastrada (`RegraSugestao`, Master)

Tecnologia + tipo de anomalia + componente (opcional) + criticidade mínima do
equipamento (NORMAL, ALERTA ou CRITICO) → recomendação do catálogo
`TipoRecomendacao`. Aplica-se só com criticidade **conhecida**: sem condição
classificada, a regra não dispara. Ordenada por prioridade.

### Fonte 2 — histórico (escolhas dos técnicos)

Recomendações escolhidas nos achados do MESMO CLIENTE com a mesma tecnologia,
componente e anomalia. Só aparece quando a escolha ocorreu pelo menos
`MIN_OCORRENCIAS` = 3 vezes; mostra contagem (n de N) e frequência. A frequência
não é probabilidade de acerto. Até 3 sugestões de histórico.

### Vazio

Sem regra aplicável nem histórico, a lista é vazia com motivo
(`sem_regra_nem_historico`, `sem_condicao_classificada_e_sem_historico`,
`anomalia_nao_classificada`). Nunca há texto genérico.

### Justificativa

Cada sugestão traz a justificativa (regra e situação, ou contagem histórica). A
evidência do momento da decisão (contagem, total, criticidade, situação da regra) é
gravada em `AceitacaoSugestao.evidencia`.

## Cadastros e permissões

| Cadastro | Leitura | Escrita |
| --- | --- | --- |
| ConfiguracaoTendencia | equipe interna | Master |
| LimiteAlarmeSerie | equipe interna | Master |
| MatrizRisco | equipe interna | Master |
| RegraSugestao | equipe interna | Master |
| AceitacaoSugestao | equipe interna | equipe interna (não-Master) |

Exclusão é lógica (`ativo = False`), para não apagar o histórico que citou o parâmetro.
Validação: `Model.clean()` roda na API (mesma regra do admin): pesos, consequência
e faixas da matriz; ordem dos limites; janela ≥ pontos mínimos; situação VALIDADA
exige fonte.

## Limites honestos de cada método

- Regressão linear/exponencial sobre poucos pontos (4 a 8) tem intervalo largo. Por
  isso o mínimo e a janela são cadastro.
- A significância testa só a inclinação; não testa a forma (linearidade) nem
  autocorrelação. Séries com oscilação periódica (ex.: carga) podem parecer tendência.
- Não há tratamento de sazonalidade, mudança de regime nem troca de componente
  além do que o contexto exato separa.
- A projeção é extrapolação da reta. Fora do intervalo de medição, o valor é menos
  confiável; por isso o horizonte é limitado.
- O índice de risco combina componentes de escalas diferentes com pesos
  cadastrados. Mudar pesos ou faixas muda a ordem do ranking; não há calibração
  contra falhas reais.
- Histórico de sugestões depende do que os técnicos registraram; com poucos achados
  por combinação, não há sugestão (por design).

## Parâmetros que o cliente deve confirmar

1. Pontos mínimos, janela, R² mínimo, horizonte e margem do modelo (padrões acima).
2. Matriz de risco: pesos, mapa de consequência A/B/C e faixas do índice.
3. Limites de alarme para termografia e demais técnicas (`LimiteAlarmeSerie`), com
   fonte. Sem isso, essas séries não têm data estimada.
4. Regras de sugestão (tecnologia/anomalia/componente/criticidade → recomendação),
   cada uma com fonte e aprovação.
5. Mínimo de ocorrências para sugestão por histórico (padrão 3).

## Pendências desta entrega

- **Laudo**: o texto de tendência e projeção ainda não entra no laudo. O laudo é do
  Agente 2 (`apps/laudos`); a integração fica para uma passagem dele usando
  `apps.preditiva.tendencia.analisar_medicao`.
- **Telas (inserções mínimas)**:
  - Sugestões: `components/achado-campos.tsx` recebe `achadoId` opcional e mostra
    `features/preditiva/sugestoes-achado.tsx` abaixo da Recomendação. Usado na análise
    final (`inspecoes/final/[id]`) e no modal de análise de campo. Aceitar/editar/rejeitar
    grava a decisão; a recomendação só vai ao achado quando a análise é salva.
  - Tendência por medição: `inspecoes/[id]/page.tsx`, dentro de `DadosColeta`, abre sob
    demanda `features/preditiva/tendencia-expansivel.tsx` com o aviso obrigatório.
  - Ranking de risco: página `/risco` (menu Análise, operacional:ver).
  - A página do equipamento é só o formulário de cadastro; por isso a tendência ficou no
    histórico de medições da inspeção.
- **Fluidos na tela**: o endpoint existe, mas não há painel de fluidos nas fichas. As
  fichas de fluidos (`features/relatorio-inspecao/modulos/fluidos`, `ensaios/cartao-ensaio`)
  são o caminho do laudo/relatório, fora do escopo desta entrega.
- **Laudo**: o texto de tendência e projeção não entra no laudo/PDF (design aprovado;
  Agente 2).
- **Prognóstico/IA**: não implementado (AP10 do doc 13).
