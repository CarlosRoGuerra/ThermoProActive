# 26 — Alinhamento a laser e termografia mecânica: fluxo, critérios e pendências

Escopo: Alinhamento a laser entre eixos (`ALINHAMENTO_EIXOS`), entre polias (`ALINHAMENTO_POLIAS`),
termografia de sistemas mecânicos dinâmicos e estáticos (`TERMOGRAFIA_MECANICA`) e termografia de
processos industriais (`TERMO_PROCESSOS`). Complementa os docs 10, 12, 21 (§7) e 23.

## 1. Regra que não muda

- Nenhuma tolerância de alinhamento e nenhum ΔT fixo existe no código ou no catálogo global.
- Um critério só classifica se estiver cadastrado em `preditiva.LimiteAlarmeSerie` com situação
  **VALIDADA** (e fonte preenchida). Sem isso, a condição sai **PENDENTE** e o relatório diz o que falta.
- A origem (norma, acordo, critério do responsável técnico, legado) e a fonte do critério aparecem no
  relatório. Um acordo com o cliente nunca sai como norma.

## 2. Fluxo, por tecnologia

| Tecnologia (sigla) | Módulo | Lançamento | Classificação | Relatório |
|---|---|---|---|---|
| Alinhamento entre eixos (ALEE) | `ALINHAMENTO_EIXOS` | Ficha antes/depois na inspeção (`MedicaoTecnica`, subtipo `ALINHAMENTO_EIXOS`) | Desalinhamento angular e paralelo do depois, contra o critério da grandeza | Folha com antes, depois, reduções, critérios e pendências |
| Alinhamento entre polias (ALEP) | `ALINHAMENTO_POLIAS` | Mesma ficha, subtipo `ALINHAMENTO_POLIAS` | Igual à de eixos | Igual à de eixos |
| Termografia mecânica dinâmica (TI-SMD) | `TERMOGRAFIA_MECANICA` | Análise (`Achado`) com temperatura medida e de referência | ΔT contra o critério `delta_t`, sistema `MEC_DINAMICO` (ou sem sistema) | Folha com ΔT, condição pelo critério, origem e fonte |
| Termografia mecânica estática (TI-SME) | `TERMOGRAFIA_MECANICA` | Igual à dinâmica | Critério de `MEC_ESTATICO` ou sem sistema | Igual |
| Termografia de processos (TI-PI) | `TERMO_PROCESSOS` | Igual | Critério de `PROCESSO` ou sem sistema | Igual |

Ficha de alinhamento (campos, todos obrigatórios, exceto onde indicado): fase (antes/depois),
desalinhamento paralelo e angular nos planos vertical e horizontal (com sinal), rpm (> 0), correções nos
pés e distância aos pés (opcionais). O valor da medição é o maior desalinhamento angular dos dois planos,
e a API recusa valor que não bata com os planos. A redução é (antes − depois) ÷ antes × 100, só com
antes positivo.

O glossário da termografia mecânica é próprio (`relatorio_tecnico/termografia_sistemas.py`): sem
grandezas elétricas, sem Grau de Risco por faixa de ΔT e sem carga/IC, que são do sistema elétrico.

## 3. Critérios cadastráveis pela tela

Tela: **Cadastros → Dados do sistema → Limites de alarme (termografia, alinhamento)**. Só o Master
edita (a API também exige o nível Master). Campos:

- Análise: Manutenção corretiva (alinhamento) ou Termografia.
- Grandeza e unidade exatas, iguais às da medição:
  - Alinhamento angular: `Desalinhamento angular` / `mm/100mm`, sentido superior.
  - Alinhamento paralelo: `Desalinhamento paralelo` / `mm`, sentido superior.
  - Termografia: `delta_t` / `°C`, sentido superior. Sistema: mecânico dinâmico, mecânico estático,
    processo, ou vazio (todos).
- Limites de alerta e crítico (pelo menos um; em sentido superior, alerta ≤ crítico).
- Origem: norma, critério do responsável técnico, acordo com o cliente, legado.
- Fonte: obrigatória para validar.
- Situação: "Padrão provisório" (não classifica) ou "Validada pelo responsável técnico" (classifica).
- Escopo: cliente, tipo de equipamento e equipamento (vazio = todos), e vigência.

Escolha do critério: equipamento antes de sistema, sistema antes de cliente, vigência mais recente.
Critério de outro cliente, provisório ou fora de vigência não vale.

## 4. Catálogo (comando idempotente)

`python manage.py ajustar_catalogo_termo_alinhamento [--dry-run]`

- `TI-SMD` e `TI-SME` passam a `TERMOGRAFIA_MECANICA`; `TI-PI` passa a `TERMO_PROCESSOS`. Antes
  apontavam para `TERMOGRAFIA` (elétrica).
- Cria a tecnologia `ALEP` (alinhamento entre polias) com `ALINHAMENTO_POLIAS`, se não existir. O
  `tipo_corretiva` é o mesmo da tecnologia de eixos (`ALEE`), lido do banco no momento da execução.
- Não cria critérios, não altera medições e não apaga nada. Segunda execução: "Catálogo já está ajustado".
- O comando busca por sigla e módulo e reaproveita o registro mais antigo (catálogos com nomes repetidos).

**Produção:** não rodar sem autorização do responsável pelo projeto. Local: rodado em 16/11/2026.

Migração `cadastros/0040_rotulos_ensaios_eletricos_implementados`: só altera os rótulos de
`ModuloTecnico` (tirou "(não implementado)" dos cinco `ENSAIO_ELETRICO_*`). Aditiva, sem efeito em dados.

## 5. Exemplos (seed)

`python manage.py seed_relatorios_exemplo` cria, no cliente fictício de CNPJ 99.888.777/0001-66,
além dos exemplos existentes:

| Relatório | Número | Id local | Resultado |
|---|---|---|---|
| Alinhamento de eixos (BMB-01) | RT-ALEE-2026-10-27-00120 | 65 | Antes 0,45 mm/100 mm; depois 0,04; condição NORMAL |
| Alinhamento de polias (VEN-02) | RT-ALEP-2026-10-29-00122 | 66 | Antes 0,60; depois 0,06; condição ALERTA |
| Termografia mecânica dinâmica (RED-03) | RT-TMEC-2026-11-01-00121 | 67 | Mancal LA ΔT 34 °C: CRITICO; mancal LOA ΔT 12 °C: ALERTA |

URLs: `/relatorios-inspecao/65`, `/relatorios-inspecao/66`, `/relatorios-inspecao/67` (carta em `/carta/<id>`).

Os critérios do seed são **de demonstração**: origem "Critério do responsável técnico", fonte começando
com "DEMONSTRAÇÃO — valor fictício…", restritos ao cliente fictício. Alinhamento: alerta 0,05 e crítico
0,1 (mm/100 mm e mm); termografia dinâmica: alerta 10 °C e crítico 20 °C. Não são tolerâncias de fabricante
nem normativas. Substituir pelo critério do responsável técnico antes de qualquer uso real.

O seed limpa, antes de recriar, os dados do cenário demo que bloqueiam a exclusão do cliente
(notificações, eventos preditivos, inspeções, sensores). Dados de outros clientes não são tocados.

## 6. O que depende do cliente

1. **Folha de campo do alinhamento.** Confirmar se os campos da ficha (planos, rpm, correções nos pés,
   distância aos pés) são os que o técnico mede e se algum outro é obrigatório.
2. **Tolerâncias de alinhamento.** Em mm/100 mm por rotação: se a tolerância depende de rpm, quais faixas,
   e se a tolerância paralela é em mm absoluto ou relativa ao diâmetro.
3. **Critério de ΔT mecânico.** Faixas de alerta e crítico por sistema (dinâmico, estático, processo), se o
   ΔT é contra a referência do mesmo ponto, e se o grau de risco deve seguir o ΔT ou a condição do inspetor.
4. **Alinhamento como serviço corretivo.** Se o alinhamento deve ter OSP, economia energética e relatório
   de intervenção como o balanceamento (ver seção 7).

## 7. Não feito (pendente)

- **Economia energética e serviço corretivo do alinhamento.** O balanceamento tem a intervenção
  (`servicos.ServicoCampo`, tipo `BALANCEAMENTO`) com planos e pontos, e a economia (`EconomiaEnergetica`)
  está ligada a `ServicoCampo`. O alinhamento tem o lançamento em `MedicaoTecnica`, sem intervenção
  própria nem economia. Vincular a economia exige o fluxo de intervenção do alinhamento, e isso ficou de
  fora desta entrega.
- **`tipo_corretiva` de ALEE e ALEP.** Estão vazios. O fluxo corretivo de `servicos` só implementa
  balanceamento (`analise_balanceamento.py` recusa outro tipo), então marcar `ALINHAMENTO` agora
  colocaria a tecnologia num fluxo sem implementação. Decisão pendente.
- **Termografia mecânica estática.** Usa o critério de `MEC_ESTATICO` ou sem sistema. Se o cliente quiser
  faixas próprias, cadastrar critério com `sistema = MEC_ESTATICO`.
- **Limites por rpm.** O critério atual não distingue rotação. Se o cliente exigir faixa por rpm, a
  seleção do critério precisa de um campo de faixa de rotação.

## 8. Defeitos encontrados e correções

- O glossário mecânico reaproveitava o elétrico inteiro (ΔT por Grau de Risco, grandezas elétricas).
  Corrigido: glossário próprio.
- A termografia mecânica não tinha critério no relatório: a folha lia só a temperatura do Achado. Corrigido:
  cada análise recebe a condição pelo critério VALIDADO do sistema, com origem, fonte e pendência.
- O alinhamento não mostrava a origem do critério nem o que faltava. Corrigido.
- Os limites saíam com quatro casas (`0.0500`). Corrigido com normalização para exibição.
- Os limites não tinham tela de cadastro (só API). Corrigido: entrada em Cadastros, com colunas de
  exibição no serializer.
- TI-SMD, TI-SME e TI-PI apontavam para a termografia elétrica. Corrigido pelo comando de catálogo.
- Não havia tecnologia de alinhamento entre polias. Criada pelo comando.
- O seed falhava na segunda execução (PROTECT de inspeção, evento preditivo, notificação e sensor).
  Corrigido com a limpeza prévia do cenário demo.

## 9. Testes

- `apps/coletas/test_alinhamento_relatorio.py`: critério validado, pendências, origem, critério de outro
  cliente ou provisório, cadastro e validação pela API (Master; técnico recusado; validar sem fonte recusado).
- `apps/coletas/test_termografia_mecanica_criterio.py`: glossário sem termos elétricos, ΔT com critério,
  escopo por sistema e cliente, e o comando de catálogo (dry-run, aplicação e idempotência).
- Testes existentes de alinhamento e termografia mecânica seguem válidos. Dois deles afirmavam que
  `ENSAIO_ELETRICO_TC` era módulo planejado; trocaram a premissa por uma chave inexistente, porque o
  módulo foi implementado.
