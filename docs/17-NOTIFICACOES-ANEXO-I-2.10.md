# Notificações (Anexo I, item 2.10)

Estado em 2026-10-27. Código em `backend/apps/notificacoes/`: `services.notificar` (eventos e
destinatários), `entregas.py` (fila, retentativa, rastreio), `channels.py` (adaptadores) e os
comandos `agendador`, `processar_notificacoes`, `verificar_canais` e `verificar_slas`.

## 1. Como funciona

1. Um evento chama `notificar(evento, destinatários, …, chave=…, cliente=…)` **dentro da transação** da operação.
2. Para cada destinatário permitido, grava o **alerta interno** (`Notificacao`). Grava também uma `EntregaNotificacao` PENDENTE por canal externo ligado na preferência do usuário.
3. Se a operação sofrer rollback, alerta e entregas somem junto e nada é enviado.
4. Depois do commit, faz uma tentativa imediata (`NOTIFICACOES_ENVIO_IMEDIATO`). Uma falha de canal nunca volta para a operação, que já está gravada.
5. O serviço **`agendador`** (novo nos composes de produção) roda `processar_pendentes` a cada 60 s e `verificar_slas` a cada 60 min.
6. Retentativa: só para erro temporário (timeout, queda, 5xx, 429), com espera de 1, 5, 15, 60 e 240 min, até `NOTIFICACOES_MAX_TENTATIVAS` (padrão 5). Erro definitivo (recusa do destinatário, credencial, 4xx) vira FALHOU na hora.
7. Reprocessamento seguro: `processar_notificacoes --reprocessar [--canal X]` ou a ação do admin. Só FALHOU e NAO_CONFIGURADO voltam à fila. **ENVIADO nunca é reenviado.**

**Idempotência.** `chave` única por destinatário, garantida no banco: a mesma ocorrência não gera um segundo aviso. Cada entrega é reivindicada com lock e uma reserva de 10 min. O envio de rede acontece fora da transação, então dois processos não enviam a mesma entrega. A entrega externa é "pelo menos uma vez": se o processo cair entre o aceite e o registro, há reenvio após a reserva. O cabeçalho `Idempotency-Key`/`X-Notificacao-Id` permite ao provedor descartar a repetição.

**Estados de entrega.**

| Estado | Significa |
|---|---|
| PENDENTE | aguardando tentativa (ou reservada por um processo) |
| ENVIADO | o provedor **aceitou** (SMTP OK / gateway 2xx sem recusa). Recebimento e leitura não são rastreados |
| SIMULADO | backend de e-mail de desenvolvimento (console/locmem/arquivo): nada saiu do servidor |
| FALHOU | erro definitivo ou tentativas esgotadas; o motivo fica em `ultimo_erro`, sem segredo |
| NAO_CONFIGURADO | canal desligado ou sem credencial; reprocessável depois de configurar |
| IGNORADO | destinatário sem e-mail/celular válido, ou conta inativa/suspensa no momento do envio |

O alerta interno é sempre gravado. A preferência `interno` ficou somente leitura na API (ver §5). `canais_enviados` agora lista só os canais com status ENVIADO.

## 2. Matriz evento × canal × destinatário × estado × teste

Testes: `E` = `apps/notificacoes/test_entregas.py`, `P` = `apps/notificacoes/test_eventos_preditivos.py`,
`O` = `apps/osp/test_fluxo.py`, `L` = `apps/laudos/test_conformidade_documentos.py`.

| Evento | Gatilho | Destinatários | Chave de idempotência | Testes |
|---|---|---|---|---|
| 2.10.2.1 Nova OS (`NOVA_OSP`) | criação da OSP (signal) | PCM do cliente da OSP + técnico responsável | `nova_osp:{osp}` | E `CincoEventos.test_nova_osp_…`; O `test_medicao_critica_gera_osp_completa_…` |
| 2.10.2.2 Equipamento crítico (`EQUIPAMENTO_CRITICO`) | classificação passa a CRÍTICO | PCM do cliente + técnico da inspeção | `evento_preditivo:{evento}` | E `test_equipamento_critico_…`; P (17 testes, inclusive rollback e repetição) |
| 2.10.2.3 Laudo concluído (`LAUDO_CONCLUIDO`) | emissão do laudo | Gestor Corp., Gestor Local e PCM do cliente do laudo | `laudo_emitido:{laudo}` | E `test_laudo_concluido_…`; L `test_emissao_repetida_e_idempotente_…`, `test_falha_pdf_reverte_…` |
| 2.10.2.4 SLA vencendo (`SLA_VENCENDO`) | `agendador` → `verificar_slas` (janela de 2 dias) | ADMIN/GESTOR + técnico responsável | `sla:{osp}:{vencendo|vencido}:{data}` mais a marca na OSP | E `test_sla_vencendo_…` (agendador 3×); O `SlaTest.test_verificar_slas_e_idempotente_…`, `…falha_de_envio_nao_consome_o_aviso` |
| 2.10.2.5 Aprovação pendente (`APROVACAO_PENDENTE`) | OSP → Aguardando aprovação | ADMIN/GESTOR (+ PCM/Corp./Local do cliente se `OSP_APROVACAO_PELO_CLIENTE`) | `osp_transicao:{histórico}` | E `test_aprovacao_pendente_*` (2); O `test_repetir_a_mesma_requisicao_…` |
| extra: Alerta preditivo, Status da OSP | ALERTA; demais transições | PCM + técnico; PCM + responsável (+ gestão em cancelar/reabrir/rejeitar) | idem | P, O |

| Canal | Estado neste ambiente (`verificar_canais`) | Implementação | Testes |
|---|---|---|---|
| 2.10.1.4 Alerta interno | **Operacional** | `Notificacao` + `/api/notificacoes/` (o sino consulta a cada 60 s) | E `Destinatarios.*`; `apps/relatorios/tests.py` `test_notificacoes_sao_so_do_proprio_usuario` |
| 2.10.1.1 E-mail | **Não configurado** (backend console, modo dev) | SMTP do Django com timeout; ENVIADO só com aceite | E `CanalEmail.*` (aceite, simulado, queda com backoff até FALHOU, recusa definitiva, backend que não confirma, sem e-mail) |
| 2.10.1.2 WhatsApp | **Não configurado** (desligado) | gateway HTTP genérico, Bearer e Idempotency-Key | E `CanalWhatsApp.*` (aceite com id, 2xx com recusa, 5xx/timeout temporário, 4xx definitivo sem vazar token, celular inválido, sem URL) |
| 2.10.1.3 Push | **Não implementado** | adaptador responde NAO_CONFIGURADO | E `CanalWhatsAppDesligadoEPush.*` |

Garantias transversais (`E IdempotenciaEFalhas`, `Destinatarios`, `Credenciais`):
- Mesma chave não duplica.
- Entrega reservada não é enviada por outro processo.
- Rollback não envia.
- E-mail fora do ar não interrompe a operação gravada.
- Adaptador com defeito não derruba o lote.
- Reprocessar não toca no ENVIADO.
- Usuário do Portal de outra empresa nunca recebe; conta inativa/suspensa não recebe.
- Diagnóstico e logs sem credencial, e-mail ou telefone.

Suíte completa do backend: **563 testes OK** (3 pulados, só PostgreSQL).

## 3. Correções feitas

1. **WhatsApp e Push declaravam entrega sem enviar nada:** gravavam log com o celular e devolviam "enviado".
2. **E-mail com `fail_silently=True` sempre "enviado":** mesmo com o SMTP recusando. Também não tinha timeout.
3. **Sem rastreio por canal:** não havia estado, tentativas, erro, datas ou id do provedor. Não havia retentativa nem reprocessamento.
4. **Ninguém rodava `verificar_slas`:** o README pedia um cron que o deploy não tinha. Agora existe o serviço `agendador`.
5. **Avisos repetidos:** a idempotência existia só para eventos preditivos e para o SLA. Agora todos os eventos têm chave.
6. **Destinatários sem filtro de estado nem de empresa:** só se olhava `is_active`, e conta suspensa/bloqueada recebia. Um usuário do Portal entraria em evento de outra empresa se aparecesse na lista. Agora `destinatario_permitido` checa estado e empresa, e repete a checagem no momento do envio.
7. **Logs com dados pessoais:** o e-mail e o celular do destinatário iam para o log, e mensagens de erro podiam conter credenciais. Agora `sanitizar` remove segredos configurados, tokens, e-mails e telefones.

Histórico: o `canais_enviados` das notificações **anteriores a 27/10/2026** não é confiável para e-mail, e para WhatsApp/push se estavam ligados.

## 4. Integrações que dependem da configuração do cliente

| Canal | O que a CONTRATANTE precisa fornecer/decidir | Variáveis (`.env.prod`, nunca no git) | Teste de integração |
|---|---|---|---|
| E-mail | Servidor SMTP e conta de envio. Domínio remetente com SPF, DKIM e DMARC (sem isso a mensagem é aceita e cai em spam) | `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `EMAIL_TIMEOUT` | Na VPS: `python manage.py verificar_canais --enviar-email-teste <e-mail da equipe>` (envio **real**) e conferir a caixa de entrada e o spam |
| WhatsApp | Provedor (API oficial da Meta via middleware, ou gateway próprio/terceiro). Na API oficial, mensagem iniciada pela empresa exige **modelo aprovado** pela Meta. Opt-in do usuário (LGPD) e celular cadastrado | `NOTIFICACOES_WHATSAPP_ENABLED=true`, `WHATSAPP_WEBHOOK_URL`, `WHATSAPP_WEBHOOK_TOKEN`, `WHATSAPP_TIMEOUT` | O gateway precisa cumprir o contrato abaixo. Testar com um número da equipe, ligando a preferência WhatsApp do próprio usuário e vendo a entrega ENVIADO com `provedor_id` |
| Push | Escolher Web Push (VAPID, sem fornecedor) ou FCM. Exige service worker no front, tela de consentimento e tabela de assinaturas por dispositivo, e nada disso existe | — | Não há o que testar até a implementação |
| Agendador | Subir o serviço `agendador` junto com o backend | `AGENDADOR_INTERVALO_SEGUNDOS`, `AGENDADOR_SLA_A_CADA_MINUTOS`, `SLA_JANELA_VENCENDO_DIAS` | `docker compose logs agendador`; `python manage.py agendador --uma-vez` |

**Contrato do gateway de WhatsApp.**
- Requisição: `POST {WHATSAPP_WEBHOOK_URL}` com `Authorization: Bearer {token}` e `Idempotency-Key: notif-{id}-WHATSAPP`.
- Corpo: `{"to": "55DDNNNNNNNNN", "title": "...", "text": "...", "idempotency_key": "..."}`.
- Resposta de aceite: `2xx` com `{"id": "<id da mensagem>"}`.
- Resposta de recusa: `{"accepted": false, "error": "..."}`.
- Repetições com a mesma chave devem ser descartadas pelo gateway.
- Números sem DDI são tratados como brasileiros (+55), uma premissa a confirmar.

**Antes da primeira subida do agendador em produção:** os avisos de SLA de todas as OSPs **já vencidas** saem de uma vez (um por OSP, por destinatário). Numa cópia do banco local foram 4.

## 5. Pendências de negócio

1. **Lembrete de SLA:** hoje sai um aviso "vencendo" e um "vencido" por prazo, sem lembrete recorrente enquanto continuar vencido. Confirmar se o cliente quer lembrete diário e se o PCM do cliente deve receber.
2. **Destinatários por evento:** confirmar se Gestor Corp./Local também recebe "Equipamento crítico" e "Nova OS" (hoje só o PCM).
3. **Alerta interno não desligável:** a preferência `interno` ficou somente leitura. Confirmar se o cliente quer poder desligá-lo.
4. **Tela de preferências:** não existe; a API existe (`/api/notificacoes/preferencias/`). Padrão atual: e-mail ligado, WhatsApp e push desligados.
5. **Provedor de WhatsApp e modelos de mensagem** (§4).
6. **Push:** decidir se entra no escopo (Web Push ou FCM).
7. **Retenção:** prazo de guarda de notificações e entregas (LGPD).
8. **"Tempo real" no sistema:** hoje é consulta a cada 60 s; push via WebSocket/SSE seria trabalho adicional.

## 6. Observações

- Esta verificação não fez nenhuma entrega real: SMTP e gateway foram substituídos nos testes. O teste real depende das credenciais do §4.
- A pasta `docs/n8n/` é de **outro projeto** (atendimento de um gabinete) e não tem relação com este sistema. Recomendo removê-la do repositório.
