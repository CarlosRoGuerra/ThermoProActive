# 22 — Acesso, laudos, portal e BI (Agente 2)

Status de cada item do Anexo I atribuído ao Agente 2. Cada linha diz o que foi feito,
onde está, quais endpoints/telas e qual teste cobre. O que não foi concluído está em
**Pendentes**, com o motivo.

## Concluídos

| Item | Implementação | Tela / Endpoint | Teste |
|---|---|---|---|
| **S-24** rascunhos internos fora da API do cliente | `apps/core/escopo.py::liberado_ao_cliente`. Cliente: `Carregamento` e `ItemInspecao` só com `status=TRANSFERIDA`; `Achado` só `visivel_cliente=True`; `AchadoImagem` só `achado__visivel_cliente=True`; dados de ensaio (coletas e resultados) só de relatório com `data_finalizacao`; `laudos/{id}/eventos` e `/historico` dão 403 para cliente. Internos não passam por filtro. Falha fechada. | `/api/carregamentos/`, `/api/itens-inspecao/`, `/api/achados/`, `/api/achados-imagens/`, `/api/coletas-oleo|fluido/`, `/api/registros-ensaio-eletrico/`, `/api/resultados-ensaio/`, `/api/laudos/{id}/eventos/`, `/historico/` | `apps/core/test_homologacao_perfis.py` (`test_rascunhos_internos_ficam_fora_da_api_do_cliente`, `_liberar_para_cliente`); `apps/core/test_revisao_independente.py::S24RascunhoInvisivelAoCliente` |
| **S-25** MFA obrigatório sem trancar a conta | `SessaoAutenticacao.mfa_pendente` (migração `accounts/0004`). Login de conta com `mfa_obrigatorio=True` sem MFA confirmado cria sessão restrita. `CookieJWTAuthentication` trata a requisição como anônima fora de `ROTAS_COM_MFA_PENDENTE` (`mfa/setup`, `mfa/confirm`, `logout`, `session/refresh`, `csrf`, `me`). Confirmar o MFA zera o flag da sessão atual. | `POST /api/auth/{admin,portal}/login/` (devolve `mfa_setup_required`), `POST /api/auth/mfa/setup/`, `POST /api/auth/mfa/confirm/` | `apps/accounts/test_mfa_obrigatorio.py` (7 casos) |
| **S-26** `/django-admin/` desligado em produção | `DJANGO_ADMIN_ENABLED` padrão = `DEBUG` (`config/settings.py`). | `/django-admin/` | Sem teste automatizado (flag lida no import). Verificação manual: `DEBUG=False` sem a variável → `/django-admin/` não existe. |
| **2.1.1.6** permissões por setor | Estendido: inspeções (`/api/inspecoes/`: aparece se alguma medição de qualquer tipo cai num setor permitido) e laudos (só de inspeção nesses setores; laudo de relatório de rotas fica de fora para quem tem restrição, falha fechada). `accounts/models.py::RestricaoSetorUsuario` (usuário × setor, migração `accounts/0005`). Sem linhas = cliente inteiro (compatível). Com linhas = só os setores listados. `apps/core/escopo.py::restringe_setor` e `restringe_setor_por_filho` (para carregamento, que agrega itens). Configuração: Master interno, ou Master do mesmo cliente (nunca sobre si mesmo); setores precisam ser do cliente do alvo. | `GET/PUT /api/usuarios/{id}/setores/` (Master interno); `GET/PUT /api/minha-equipe/{id}/setores/` (Master do cliente). Aplicado em `/api/equipamentos/`, `/api/itens-inspecao/`, `/api/achados/`, `/api/achados-imagens/`, `/api/carregamentos/`, medições de vibração/termografia/técnica, ensaios de dados (coleta/resultado), `dashboard/portal/visao-geral` (equipamentos). | `apps/core/test_escopo_setor.py` (12 casos: leitura, medições, interno não restringido, cross-cliente, quem configura, setor de outro cliente recusado) |
| **3.1.2** campos da equipe técnica | `accounts/models.py::DadosPessoaisUsuario` (1-para-1, opcional): data de nascimento, RG, CTPS, estado civil, quantidade de filhos, endereço (logradouro, número, complemento, bairro, cidade, UF, CEP). CPF, cargo e conselho já existiam em `User`. Finalidade declarada no docstring do modelo. Não entra em `UserSerializer`, listas nem exports. Valores nunca vão para o log (só nomes de campos). | `GET/PUT /api/auth/dados-pessoais/` (próprio usuário); `GET/PUT /api/usuarios/{id}/dados-pessoais/` (Master interno) | `apps/accounts/test_dados_pessoais.py` (7 casos, inclusive "não aparece em listas" e "não vai para o log") |
| **3.1.22** trilha de auditoria | `apps/core/auditoria.py`: sinais `pre_save`/`post_save`/`post_delete` nos apps de negócio (cadastros, coletas, ensaios, servicos, osp, laudos, relatorios, notificacoes, preditiva, e modelos não sensíveis de accounts). `ContextoAuditoriaMiddleware` leva a requisição. `apps/core/models.py::RegistroAuditoria` é append-only (save/delete levantam erro; só `purgar_antigos` apaga). Grava quem (id e e-mail), quando, IP, método, rota, modelo, id e campos alterados (antes/depois). Só registra o que mudou (ignora `atualizado_em`). Campos com nome sensível (senha, segredo, token, código, hash, RG, CPF, CTPS, nascimento, endereço) saem como `***`. Modelos de segurança ficam fora. Retenção: `AUDITORIA_RETENCAO_DIAS` (padrão 1825) + `manage.py purgar_auditoria [--dias N]`. | `GET /api/auditoria/` (Master interno; filtros `modelo`, `acao`, `usuario`, `objeto_id`, `criado_em`) | `apps/core/test_auditoria.py` (10 casos: criar/alterar/excluir, sem mudança não grava, senha mascarada, segurança fora, quem/IP/rota, append-only, consulta só Master, retenção) |
| **2.5.1.3** assinatura PAdES | `apps/laudos/assinatura.py` (pyHanko 0.38.0, MIT): `assinar_pades` (assinatura incremental **invisível**: `/Rect [ 0 0 0 0 ]`, sem aparência, layout aprovado intacto) e `verificar_pades` (integridade, validade e confiança). Certificado A1 (PKCS#12) em `accounts/models.py::CertificadoA1`: arquivo **cifrado em repouso** (`accounts/security._fernet`, mesma chave do MFA). **Senha do .pfx nunca guardada**: validada no upload e pedida de novo a cada assinatura. `.pfx` é carregado a partir dos bytes (sem arquivo temporário). Hash do PDF assinado e dados do certificado (titular, emissor, série, SHA-256) gravados no laudo. Sem certificado: 409 `SEM_CERTIFICADO`, e a aprovação eletrônica continua. | `POST/GET/DELETE /api/auth/certificado-a1/` (interno); `POST /api/laudos/{id}/assinar-digitalmente/` (só o responsável do laudo); `GET /api/laudos/{id}/pdf-assinado/`; `GET /api/laudos/{id}/verificar-assinatura/` | `apps/laudos/test_assinatura_pades.py` (17 casos: assinar/verificar, adulteração quebra integridade, sem raiz não é confiável, PDF ilegível tratado, upload com senha errada, vencido, cliente não assina, duplicidade, sem certificado) |
| **2.10.1.3** push + **2.7.1.1.8** tempo real (push) | Web Push VAPID. `apps/notificacoes/channels.py::enviar_push`: `ENVIADO` **só** com 200/201/202 do push service; 404/410 desativa a assinatura; 5xx/429/rede = falha temporária; sem chaves ou sem `NOTIFICACOES_PUSH_ENABLED` = `NAO_CONFIGURADO`. Assinaturas por dispositivo (`notificacoes/AssinaturaPush`, migração `notificacoes/0005`). Service worker `frontend/public/sw.js`. Registro no navegador: `frontend/src/lib/push.ts` (`ativarPush`, `desativarPush`). Polling de 60 s continua como fallback. Gerador de chaves: `manage.py gerar_vapid_keys`. | `GET /api/notificacoes/push/chave/`; `POST`/`DELETE /api/notificacoes/push/assinatura/` | `apps/notificacoes/test_web_push.py` (14 casos, com `webpush` mockado: 2xx, 410, 5xx, 400, inativa, sem chave, rotas, comando). `apps/notificacoes/test_entregas.py` segue passando. |
| **2.8.1.3.4** indicadores em tempo real (atualização automática) | Painéis operacional e executivo (60 s). `frontend/src/lib/recurso.ts::useRecurso(caminho, contexto, { atualizarACadaMs })`: busca silenciosa (não pisca "carregando"), pausa com a aba oculta, mantém o último dado válido se a busca falhar. Aplicado ao painel operacional (60 s). **Escolha de transporte**: polling, não WebSocket. O backend roda gunicorn síncrono (`--workers 3`, ver `docs/18`); WebSocket exigiria ASGI e canal de broker, fora do escopo e do ambiente de deploy atual. | Painel operacional `/dashboard` | `npx tsc --noEmit` (sem teste automatizado de UI) |

### Variáveis de ambiente novas (também em `.env.prod.example` quando aplicável)

| Variável | Uso | Padrão |
|---|---|---|
| `DJANGO_ADMIN_ENABLED` | liga `/django-admin/` (S-26) | = `DEBUG` |
| `AUDITORIA_RETENCAO_DIAS` | dias de retenção da trilha (3.1.22) | `1825` |
| `ASSINATURA_RAIZES_PEM` | caminho de PEM com raízes de confiança (ex.: AC ICP-Brasil) para avaliar a cadeia do A1 | vazio (cadeia não avaliada como confiável) |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | chaves do Web Push; gerar com `manage.py gerar_vapid_keys` | vazio = `NAO_CONFIGURADO` |
| `VAPID_CONTATO` | `sub` do VAPID (mailto) | `mailto:suporte@example.com` |
| `NOTIFICACOES_PUSH_ENABLED` | liga o canal PUSH (já existia) | `False` |

`VAPID_PRIVATE_KEY` é segredo: o comando imprime uma linha só, com `\n` escapado. Não grave em repositório nem em log.

### Migrações (novas)
- `accounts/0004_sessao_mfa_pendente`
- `accounts/0005_restricao_setor_usuario`
- `accounts/0006_dados_pessoais_usuario`
- `accounts/0007_certificado_a1_assinatura` (`CertificadoA1`)
- `core/0001_registro_auditoria`
- `laudos/0006_certificado_a1_assinatura` (campos da assinatura no laudo)
- `notificacoes/0005_assinatura_push`

### Dependências novas (todas fixadas em `backend/requirements.txt`)

| Pacote | Versão | Licença | Observação |
|---|---|---|---|
| `pyhanko` | 0.38.0 | MIT | assinatura PAdES (2.5.1.3) |
| `pywebpush` | 2.0.3 | MPL-2.0 | Web Push (2.10.1.3). **Usada sem modificação**; MPL-2.0 permite. Arrasta `py-vapid` (MPL-2.0, sem modificação) e `http-ece` (MIT) |

Nenhuma dependência nova no frontend.

| **2.1.1.6** painéis, relatórios, portal, notificações e mídia | Filtro central em `apps/relatorios/filtros.py` (`aplicar`, `inspecoes`, `equipamentos`, `laudos`): operacional, executivo, relatórios e exports herdam a restrição. `/api/dashboard/` e `/api/dashboard/executivo/` passam por esses filtros. Visão geral do portal (`PortalVisaoGeralView`) restringe inspeções, medições e OSP. Notificações: aviso de equipamento de outro setor some para o restrito (`NotificacaoViewSet`); eventos preditivos filtrados (`EventoPreditivoViewSet`). Mídia (`core/midia.py::pode_ver`, edição pontual): foto de equipamento/achado só dos setores permitidos; documento e OSP ficam fechados. | `/api/dashboard/`, `/api/dashboard/executivo/`, `/api/relatorios/*`, `/api/dashboard/portal/visao-geral/`, `/api/notificacoes/`, `/api/eventos-preditivos/`, `/api/media/<arquivo>` | `apps/core/test_escopo_setor.py` (`IndicadoresPorSetorTests`, `NotificacoesPorSetorTests`, `VarreduraSetorListasTests`); `apps/core/test_seguranca_midia.py` segue passando |

## Telas (frontend)

| Item | Tela | Arquivo | Ligação com a API |
|---|---|---|---|
| 3.1.22 consulta da auditoria | Administração → Auditoria (só Master interno, habilidade `auditoria:ver`) | `frontend/src/features/auditoria/tela-auditoria.tsx`, `app/(admin)/auditoria/page.tsx`, `lib/nav.ts`, `lib/permissions.ts` | `GET /api/auditoria/` (filtros de ação e modelo) |
| 2.5.1.3 cadastro do A1 | Perfil → "Certificado digital A1" (só interno) | `features/perfil/certificado-a1.tsx` (montado em `features/perfil/meu-perfil.tsx`) | `GET/POST/DELETE /api/auth/certificado-a1/` (multipart; senha não guardada) |
| 2.5.1.3 assinar e verificar | Laudo emitido → "Assinatura digital" (só o responsável; a verificação aparece para quem vê o laudo) | `features/laudos/assinatura-laudo.tsx` (montado em `features/laudos/laudo-gestao.tsx`) | `POST /api/laudos/{id}/assinar-digitalmente/`, `GET .../verificar-assinatura/`, `GET .../pdf-assinado/` |
| 2.10.1.3 push (admin e portal) | Alertas → "Avisos neste dispositivo" (mesma tela nos dois portais) | `features/push/aviso-push.tsx` (montado em `features/alertas/lista-alertas.tsx`) | `GET /api/notificacoes/push/chave/`, `POST/DELETE /api/notificacoes/push/assinatura/` |
| 2.1.1.6 setores do usuário | Usuários → editar acesso → "Setores permitidos" (só usuário de cliente) | `features/usuarios/setores-restritos.tsx` (montado em `features/usuarios/formulario-usuario.tsx`) | `GET/PUT /api/usuarios/{id}/setores/` |
| 2.1.1.6 setores (Minha Equipe) | Portal → Equipe → "Setores" de cada colega (só Master do cliente) | `features/usuarios/setores-restritos.tsx` (montado em `app/portal/equipe/page.tsx`) | `GET/PUT /api/minha-equipe/{id}/setores/` |

O filtro de setor dos painéis é só de backend (`apps/relatorios/filtros.py`, `apps/relatorios/indicadores.py`): a tela recebe o que o servidor calcula.

## Pendentes

| Item | Situação e motivo |
|---|---|
| **2.1.1.6 — notificações (aviso de sistema)** | Avisos com equipamento respeitam o setor; avisos sem equipamento (sistema) continuam para quem é o destinatário, como previsto. |
| **2.1.1.6 — OSP** | `osp/evidencias/` e `osp/assinaturas/` ficam FECHADOS para usuário com restrição (falha fechada, `core/midia.py::SETOR_CLIENTE` sem o prefixo). A listagem da OSP (`/api/osps/`) não recebeu filtro de setor: ficou com o Agente 1, que está com a rota `osp-assinaturas` em andamento. As somas de OSP nos painéis já passam por `apps/relatorios/filtros.py`. |
| **2.1.1.6 — documentos e anexos** | `anexos/documentos/` fica FECHADO para usuário com restrição (não tem equipamento). |
| **2.1.1.6 — varredura em `test_seguranca_isolamento.py`** | Não estendida ali. A varredura por setor está em `apps/core/test_escopo_setor.py` (`VarreduraSetorListasTests`, `IndicadoresPorSetorTests`, `NotificacoesPorSetorTests`). |
| **Gráficos interativos (2.8.1.3.1) e atualização automática do portal (2.8.1.3.4)** | Passaram ao Agente 1 por decisão de escopo. Não foram iniciados por este agente. |
| **Painéis executivo e relatórios** | Atualização automática do executivo foi acrescentada (60 s), mas o restante dos painéis de relatório não tem atualização automática. |
| **Testes de UI** | Não há testes automatizados de front nesta entrega (verificação por `tsc --noEmit`). |
| **Raízes de confiança do A1** | `ASSINATURA_RAIZES_PEM` depende de decisão sobre a autoridade certificadora. Sem ela, a verificação informa "cadeia não avaliada". |

## Correções do validador independente (docs/24)

Os defeitos V-01, V-03 e V-05 foram corrigidos. As provas em `backend/apps/core/test_validacao_agente4.py`
agora afirmam o comportamento seguro. V-02 e V-04 seguem fora desta rodada.

| ID | Defeito (resumo) | Correção | Onde | Teste |
|---|---|---|---|---|
| V-01 (ALTO) | SSRF no Web Push: endpoint era qualquer `https://`, e o servidor fazia POST para ele | Registro só aceita `https`, host na allowlist de serviços de push (FCM, Mozilla, Apple, WNS), sem IP literal, sem credenciais, porta 443. No envio revalida tudo, resolve o DNS e recusa IP não público (privado, loopback, link-local, reservado). A sessão não segue redirecionamento. Endpoint inválido é desativado, sem chamar o destino. | `apps/notificacoes/seguranca_push.py`, `channels.py::enviar_push`, `views.py::PushAssinaturaView` | `test_validacao_agente4.py::V01...`, `apps/notificacoes/test_seguranca_push.py` (9 casos) |
| V-03 (ALTO) | Trilha gravava PKCS#12 cifrado do A1, titular e e-mails em claro | Campo binário ou de arquivo sai da trilha. Campos com nome de certificado, cifrado, pfx, pem, CPF, RG, CTPS, nascimento e endereço saem. Segredos (senha, token, chave, hash) aparecem só como `***`. Titular, emissor e nome mascarados. E-mail sai mascarado (`p***@v***.test`), inclusive o do ator. Lista negativa global e por modelo (`MODELO_EXCLUIR`). Registros antigos são saneados pela migração `core/0002` e pelo comando `sanear_auditoria` (idempotente). | `apps/core/auditoria.py`, `apps/core/migrations/0002_auditoria_append_only.py`, `apps/core/management/commands/sanear_auditoria.py` | `test_validacao_agente4.py::V03...`, `apps/core/test_auditoria.py::SaneamentoDaTrilhaTests` |
| V-05 (MÉDIO) | Append-only só no ORM: `QuerySet.update()` alterava a trilha e não havia trigger | `update()` levanta `PermissionError`. Trigger no banco (PostgreSQL: função plpgsql; SQLite: `RAISE(ABORT)`), criado pela migração `core/0002` condicionado ao vendor. UPDATE só em modo de saneamento, DELETE só em modo de retenção. Os modos são abertos por `modo_manutencao()` na transação. `purgar_auditoria` usa o modo de retenção. A ligação com o usuário passou a `DO_NOTHING` sem FK no banco, para que apagar um usuário não tente um UPDATE. | `apps/core/models.py` (`RegistroAuditoriaQuerySet`, `modo_manutencao`), migração `core/0002` | `test_validacao_agente4.py::V05...`, `apps/core/test_auditoria.py::AppendOnlyNoBancoTests` |

### Limites residuais (honestos)
- **V-01, DNS rebinding:** a checagem de DNS é feita antes da conexão. Ainda há uma janela pequena entre a resolução
  e o connect. O risco fica reduzido porque o host precisa estar na allowlist, e esses domínios são de provedores
  de push, não de quem assina. Fixar o IP na conexão exigiria mexer no pool do urllib3, e isso não foi feito.
- **V-05, bloqueio no banco:** o bloqueio depende da tabela `core_auditoria_controle`. Quem tem permissão de
  escrita direta no banco pode mudar o modo ou desligar o trigger. A proteção forte exige separação de papéis no banco
  (o usuário da aplicação sem UPDATE/DELETE na trilha, e o expurgo com outro papel). Isso é de operação, não de código.
- **V-03, dados já gravados:** o saneamento é a única alteração permitida à trilha. Ele roda em modo de manutenção,
  está documentado no código e é idempotente.

### Configuração nova
| Variável | Uso | Padrão |
|---|---|---|
| `PUSH_HOSTS_PERMITIDOS` | serviços de push aceitos como destino (lista separada por vírgula). Vazio = padrão | vazio (FCM, Mozilla, Apple, WNS) |

## Falhas conhecidas fora do escopo deste agente

- `apps/ensaios/test_fluidos.py::test_cliente_consulta_mas_nao_altera_resultado` e `apps/ensaios/tests.py::test_portal_so_consulta_os_ensaios_da_propria_empresa` falham por causa do S-24: a fixture não tem `data_finalizacao`. Já repassado ao Agente 1.
- Erros `no such table: preditiva_*` (app `apps.preditiva`, Agente 3), em suítes que criam dados de cliente. Não são deste trabalho.
