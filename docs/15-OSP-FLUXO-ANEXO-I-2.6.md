# OSP — fluxo completo (Anexo I, item 2.6)

Estado em 2026-10-26. Cobre geração automática, máquina de estados com permissão por
perfil, histórico, SLA, escopo por cliente e integração com notificações, laudos e painéis.
Corrigido de forma incremental sobre `apps/osp` — nenhum módulo foi reescrito.

## 1. Requisitos × implementação

| Item | Requisito | Situação | Onde |
|---|---|---|---|
| 2.6.1.1.1 | Gera OS ao identificar problema | **Atendido** — medição CRÍTICA (via evento preditivo) e análise confirmada (`gerar_de_achado`) | `osp/services.py::gerar_osp_de_medicao`, `osp/models.py::gerar_de_achado` |
| 2.6.1.1.2 | Define prioridade | **Atendido** — CRÍTICO → ALTA, GR-2; editável e auditado | `services.py`, `aplicar_edicao` |
| 2.6.1.1.3/4 | Vincula equipamento e técnico responsável | **Atendido** — responsável = técnico da inspeção; quem assume a análise vira responsável se vazio; responsável precisa ser interno | `services.py`, `serializers.py::validate_responsavel` |
| 2.6.1.1.5 | Define SLA | **Atendido** — `sla_data` + `sla_origem` (GRAU_RISCO / PRIORIDADE / MANUAL / LEGADO) + `sla_iniciado_em` | `models.py::calcular_sla` |
| 2.6.1.1.6 | Envia notificações | **Atendido** — nova OSP, aprovação pendente, mudança de status, SLA vencendo/vencido; sem duplicidade | `notificacoes/signals.py`, `services._notificar_transicao`, `services.verificar_slas` |
| 2.6.2.1 / 2.6.3 | Status operacional e os 6 status | **Atendido** — 8 valores (6 do Anexo I + Planejada/Executada da reunião de 22/07), 20 transições válidas | `models.py::TRANSICOES` |
| 2.6.2.3 | Histórico completo | **Atendido** — `HistoricoOSP`, somente acréscimo, `GET /api/osps/{id}/historico/` | `models.py::HistoricoOSP` |
| 2.6.2.4 | Evidências fotográficas | **Parcial** — expõe as imagens do achado de origem (`evidencias`); upload direto na OSP **não** foi criado (ver §4) | `serializers.py` |
| 2.6.2.5 | Aprovação da execução | **Atendido, com premissa** — registro eletrônico (usuário, perfil, instante) por perfil autorizado (§4, item 1) | `services.transicionar` |
| 2.6.2.2 | Checklist técnico | **Não implementado** — fluxo não confirmado (§4) | — |
| 2.6.2.6 | Assinatura do cliente | **Não implementado** — fluxo não confirmado (§4) | — |
| 2.6.2.7 | Controle de peças | **Não implementado** como lista; existe só o valor de material (`pred_material_valor`) | — |
| 2.6.2.8 | Tempo de execução | **Parcial** — datas planejado/executado, horas de mão de obra do cliente (`pred_mao_obra_h`) e `tempo_ciclo_horas` (abertura→finalização); sem apontamento por técnico | `models.py` |

## 2. Regras implementadas

**Geração e idempotência** (3 camadas, mais retentativa de numeração)
1. Lock da linha do equipamento (efetivo no PostgreSQL) serializa eventos simultâneos.
2. Consulta das OSPs abertas da mesma ocorrência (equipamento + inspeção).
3. Restrição única parcial no banco `uniq_osp_automatica_aberta_por_ocorrencia`; se a corrida escapar das duas primeiras, o `IntegrityError` é convertido na OSP vencedora.
4. `gerar_de_achado` trava o achado, e `achado` é `OneToOne`; conflito devolve a OSP existente.
5. `numero`, `sequencial_global` e `(cliente, sequencial_cliente)` ganharam unicidade no banco; colisão de numeração (`max+1`) gera nova tentativa (até 5).
6. Falha parcial: a gravação da medição, o evento preditivo, a OSP e as notificações estão na mesma transação — se algo cai, nada fica pela metade e o reenvio gera exatamente uma OSP. Envio por e-mail/WhatsApp/push só sai depois do commit.

**Transições** (`TRANSICOES`; tudo fora disso → 409)

```
ABERTA        → EM_ANALISE, PLANEJADA, CANCELADA
EM_ANALISE    → EM_EXECUCAO, PLANEJADA, CANCELADA
PLANEJADA     → EM_EXECUCAO, EXECUTADA, CANCELADA
EM_EXECUCAO   → EXECUTADA, AGUARDANDO_APROVACAO, CANCELADA
EXECUTADA     → AGUARDANDO_APROVACAO, FINALIZADA, CANCELADA
AGUARDANDO_APROVACAO → FINALIZADA (aprovar), EM_EXECUCAO (rejeitar, motivo), CANCELADA
FINALIZADA / CANCELADA → ABERTA (reabertura, motivo)
```

**Quem pode** (`status` é somente leitura no `PATCH` genérico; só `PATCH /api/osps/{id}/status/` muda)

| Ato | Perfis |
|---|---|
| Avançar no fluxo (análise, execução, planejada, executada, pedir aprovação) | ADMIN, GESTOR, TECNICO |
| Aprovar/finalizar e rejeitar aprovação | ADMIN, GESTOR (+ PCM, Gestor Corp./Local do cliente **só** se `OSP_APROVACAO_PELO_CLIENTE=true`, e só da própria empresa) |
| Cancelar e reabrir | ADMIN, GESTOR |
| Manutentor do cliente | nunca move status |
| Alterar `sla_data` à mão | ADMIN, GESTOR |

A permissão é checada antes da validade da transição (quem não pode não descobre o fluxo pelo erro), dentro da transação com a linha travada. Pedir o status em que a OSP já está é *no-op* (`alterado: false`), sem histórico nem aviso duplicado. O escopo por cliente vem do queryset (404 fora do escopo) e é rechecado no serviço.

**Cancelamento** — exige motivo; mantém todo o histórico; a OSP fica imutável (editar → 409); não é excluída (`DELETE` → 405; a FK do histórico é `PROTECT`); sai de totais, taxas, laudo e Seção B (continua em `osps_por_status` e `osps_canceladas`).

**Reabertura** — exige motivo; volta a ABERTA; zera finalização/aprovação (valores anteriores ficam gravados na linha de histórico); o SLA recomeça na data da reabertura. Se já existir outra OSP automática aberta da mesma ocorrência, 409 `conflito_ocorrencia`.

**Rejeição de aprovação** — exige motivo; volta a EM_EXECUCAO; avisa o responsável.

**SLA** — prazo pelo Grau de Risco quando há GR (3/10/20/30 dias), senão pela prioridade (1/3/7/15). Mudar prioridade/GR recalcula (exceto prazo `MANUAL`). **Vencido** = aberta com `sla_data` < hoje: só sinaliza (`sla_vencido`, filtro `?sla_vencido=true`, contadores nos painéis); não muda o status. `verificar_slas` (cron) avisa **uma vez** em "vencendo" e **uma vez** em "vencido" por prazo; mudar o prazo zera as marcas; falha de envio desfaz a marca. Finalizada registra `sla_cumprido`.

**Painéis/laudos** — dashboard operacional, executivo e portal ganharam `osps_sla_vencido`; executivo ganhou `osps_canceladas` e `sla_cumprido_pct`; laudo (Seção D) e estatísticas (Seção B) ignoram OSP cancelada.

## 3. Evidências

- `apps/osp/test_fluxo.py` (53 testes, 1 só em PostgreSQL) + 1 teste em `apps/servicos/test_relatorio_corretivo.py`: matriz completa 8×8 de transições, permissões por perfil, motivo obrigatório, histórico, SLA, idempotência do `verificar_slas`, escopo entre clientes, painéis, corrida simulada e falha parcial.
- Suíte completa do backend: **503 testes OK** (3 pulados).
- Migração `osp/0010` aplicada sobre cópia do banco local (5 OSPs): todas ganharam linha de criação (`LEGADO`) e `sla_iniciado_em`.
- `tsc --noEmit` do front sem erros.

```
cd backend
.venv\Scripts\python.exe manage.py test apps.osp apps.notificacoes apps.servicos
```

## 4. Regras que dependem de confirmação do cliente

Cada uma já tem teste fixando o comportamento atual — se a regra mudar, o teste muda junto.

1. **Quem aprova a execução / finaliza.** `docs/03` perguntou "cliente? gestor?" e não houve resposta. Padrão adotado: só a gestão da CONTRATADA; `OSP_APROVACAO_PELO_CLIENTE=true` estende a PCM/Gestores do cliente. A reunião de 22/07 diz que o PCM "faz a finalização", mas a decisão de 21/09 (portal só devolve informação) manda no momento.
2. **Checklist técnico** — o cliente tem modelo/padrão? Nada foi criado.
3. **Controle de peças** — lista de peças (código, quantidade, custo) ou só o valor de material que já existe?
4. **Tempo de execução** — basta horas de mão de obra + datas, ou apontamento por técnico/cronômetro?
5. **Assinatura do cliente** — gráfica (imagem) ou ICP-Brasil? Quem assina? O que existe hoje é aprovação eletrônica interna (usuário + perfil + instante), **não** assinatura.
6. **Evidências fotográficas** — quem anexa (equipe interna? cliente?) e em que etapa. Hoje só aparecem as fotos do achado de origem. Atenção: `/media/` é servido sem autenticação (já registrado em `docs/security-audit/`), então fotos novas só devem entrar depois dessa correção.
7. **Quais prazos de SLA.** Hoje o Grau de Risco prevalece sobre a prioridade: medição CRÍTICA → ALTA (3 dias) **e** GR-2 (10 dias) → vale 10. Confirmar se o SLA contratual é por prioridade (1/3/7/15) ou por GR (3/10/20/30), e se conta dias corridos ou úteis.
8. **Alerta também gera OSP?** (`docs/03`) Hoje só CRÍTICO gera.
9. **SLA vencido** — apenas sinalizar e avisar (gestão + responsável), sem escalonamento e sem avisar o PCM do cliente. Existe escalonamento? O prazo do SLA é da CONTRATADA ou do cliente?
10. **Reabertura** — só gestão; reinicia o SLA a partir da reabertura. Pode haver limite de reaberturas/prazo após finalizar?
11. **Cancelamento** — só gestão, com motivo; some do laudo e dos totais. O cliente quer ver as canceladas no portal/relatório?
12. **Mapeamento dos dois ciclos.** Executada → Finalizada direto é permitido (para quem aprova); Aguardando aprovação é opcional. Finalizar não exige custos preenchidos (a reunião diz que a finalização é "o input de valores e custos").
13. **Prazo manual** — só gestão altera `sla_data`; exigir motivo?
14. **Responsável vazio** — se a inspeção não tem técnico, a OSP nasce sem responsável e o primeiro a assumir a análise vira responsável. Existe fila/regra de distribuição?

## 5. Limites desta entrega

- O teste de concorrência com threads (`GeracaoConcorrenteTest`) só roda em PostgreSQL e **não foi executado** (sem PostgreSQL local). No SQLite, a corrida foi simulada (leitura velha + restrição única).
- A tela de OSPs foi ajustada (só transições permitidas, modal de motivo) e compila, mas **não foi exercitada no navegador**.
- A migração `osp/0010` falha com mensagem clara se o banco tiver duplicatas de OSP automática aberta, `sequencial_global` ou `(cliente, sequencial_cliente)`. Rodar a checagem na VPS antes do deploy.
- O admin do Django (superusuário) continua capaz de editar campos fora da trilha de auditoria; status e exclusão foram bloqueados lá.
