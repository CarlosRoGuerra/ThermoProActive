# 24 — Validação independente (Agente 4)

Data: 03/11/2026 · HEAD: `143042f` · Linha de base: git tree `1507fd6368301bcc42b865ecc6edaf165ea1f520`
Escopo: diff dos três agentes (175 arquivos, +13.795 / −147 linhas contra a base). Nenhum código de produção foi alterado.
Único arquivo criado: `backend/apps/core/test_validacao_agente4.py` (9 provas, todas passando; cada uma confirma um defeito).

---

## 00. Fechamento (coordenação, 03/11/2026) — V-08 e V-09 corrigidos

| ID | Correção | Evidência |
|---|---|---|
| **V-08** (crítico) | `select_for_update(of=("self",))` em `apps/osp/services.py` (`transicionar`) e `apps/laudos/services.py` (`emitir_laudo`) — trava só a linha principal; o PostgreSQL não aceita `FOR UPDATE` no lado anulável do `LEFT JOIN`. | Suíte completa no PostgreSQL: de 165 erros para 5 (todos V-09). |
| **V-09** CNPJ de teste | Dados de teste com CNPJ de 19 caracteres (`111.111.111/0001-11`) corrigidos para 18 em `coletas/test_alinhamento.py`, `test_termografia_criterio.py`, `test_termografia_sistemas.py`. | Os 3 `setUpClass` passam no PostgreSQL. |
| **V-09** append-only | `core/test_auditoria.py::AppendOnlyNoBancoTests` passa a esperar `DatabaseError` (SQLite → `IntegrityError`; PostgreSQL → `InternalError`); a asserção de que o valor não muda continua. | 2 testes passam nos dois bancos. |
| **V-09** mídia (`streaming_content`) e PAdES (`PathBuildingError`) | Não se reproduziram na suíte completa após a correção do V-08. | Ver resultado abaixo. |

Resultado final, mesmo código, suíte completa com `--parallel 1`:

```
PostgreSQL 16 (descartável)   Ran 1123 tests   OK (skipped=2)
SQLite                        Ran 1123 tests   OK (skipped=6)
makemigrations --check        No changes detected
manage.py check               System check identified no issues
npx tsc --noEmit              sem erros
```

**Recomendação permanente:** a suíte deve rodar também em PostgreSQL antes de cada deploy, porque o SQLite não detectou o V-08.
**Resíduos aceitos/abertos:**
* V-01: janela teórica de DNS rebinding, severidade baixa.
* V-05: papel do banco com permissão de dono pode desligar o trigger; requer papéis separados, ação de operação.
* V-06: CSV entregue intacto, risco aceito.
* V-07: pré-existente.

**Percentuais finais** (§ "Percentuais" abaixo, cenário "após corrigir V-08"):

| Tópico | Percentual |
|---|---|
| Módulos funcionais §2 | **100%** (150/150; ver nota de recontagem abaixo) |
| Login 2.1 + Laudos 2.5 + Portal 2.7 + Dashboards 2.8 | 100% |
| Análise preditiva 2.4 | 100% (matriz de risco provisória) |
| Contrato completo | ≈ 84% (83,7) |
| Só o sistema | ≈ 93% |

**Nota de recontagem da Coleta (2.3):** a rodada 2 deu 32,5/33 porque somou +1,5 para "2.3.2.6/7/10", tratando o Ultrassom como um item. No contrato ele tem dois subitens folha (2.3.2.6.1.1 Elétrica e 2.3.2.6.1.2 Mecânica), cada um P (0,5) no `docs/20` e C agora. O ganho correto é +2, e a Coleta fecha em **33/33**. Recontagem item a item: recursos 7/7 (IoT fora); vibração 3, termografia 4, fluidos 7, transformadores 3, motores 1, ultrassom 2, espessura 1, corretiva 3, sensitiva 1, qualidade de energia 1 = 26/26. Os 0,3 ponto que faltavam no §2 eram esse erro de soma. O geral muda pouco: o §2 sobe 0,3 ponto × 65%, e a arquitetura e o banco seguem em 96,8% por causa do 3.1.22 parcial (V-05).

---

## 0. Rodada 2 (03/11/2026, revalidação das correções)

Escopo: as correções reportadas pelos agentes (V-01 a V-06, V-04 nos sensores/dados técnicos/componentes) e os itens não verificados da rodada 1. Os testes da rodada 1 foram reexaminados e invertidos para o comportamento seguro; a prova de V-05 foi ajustada para aceitar a exceção real do PostgreSQL. Nenhuma prova foi enfraquecida: a asserção de que o valor não muda continua. O código de produção não foi alterado nesta rodada.

### 0.1 Veredito por defeito

| ID | Severidade (r1) | Veredito r2 | Evidência e comentário |
|---|---|---|---|
| V-01 SSRF push | ALTO | **CORRIGIDO**; resíduo **BAIXO** | `apps/notificacoes/seguranca_push.py`: https, sem credenciais, porta 443, sem IP literal, allowlist de provedores (FCM, Mozilla, Apple, WNS), DNS revalidado antes de cada envio, `allow_redirects=False`. Provas `V01` passam em SQLite e PostgreSQL. Resíduo: DNS rebinding teoricamente possível entre a checagem e a conexão. Na prática o atacante não controla o DNS dos provedores da allowlist, então a severidade é baixa. Fixar o IP resolvido (adaptador de conexão) elimina a janela; recomendado, não bloqueia. Resíduo menor: caminho arbitrário dentro de `fcm.googleapis.com` etc., com corpo fixo, e o código HTTP do destino volta em `erros` (oráculo restrito a hosts da allowlist) |
| V-02 zip bomb | MÉDIO | **CORRIGIDO** | `apps/coletas/anexos.py` `_ler_ooxml`: mede o descompactado real em streaming, teto de 100 MB, teto de 2000 entradas, razão > 200 acima de 10 MB. Prova `V02` passa (recusa o DOCX de 101 MB com cabeçalho falso) |
| V-03 dados na trilha | ALTO | **CORRIGIDO** no código e nos testes; saneamento **não exercitado** com dados reais | `core/auditoria.py`: binário e arquivo fora; `CertificadoA1` com campos excluídos; e-mail mascarado (também no ator); `core/0002` chama `sanear_registros`. Prova `V03` passa. A cópia de produção tinha **1** registro de auditoria (seed da matriz), sem dado sensível, então o saneamento de registros antigos não foi testado com dado real. Resíduo BAIXO: `ip` do ator continua na trilha (dado pessoal indireto) |
| V-04 setor na preditiva/sensores | ALTO | **CORRIGIDO** | `preditiva/views.py`: `restringe_setor` em todas as views de dado por equipamento (inclusive `RankingRiscoView`, `TendenciaView`, `AceitacaoSugestaoViewSet`). `cadastros/views.py`: `SensorViewSet`, `DadosTecnicosMotor`, `DadosTecnicosTransformador` e `ComponenteViewSet` via `_RestricaoSetorEquipamentoMixin` (lista e detalhe). Provas `V04` passam em SQLite e PostgreSQL. Ponto a conferir: a mesma alteração troca a permissão de `EmpresaViewSet` para `IsInterno` (cadastro do prestador), **fora do escopo do V-04**; é mudança de comportamento para o Portal e precisa de confirmação |
| V-05 append-only no banco | MÉDIO | **PARCIAL** (resíduo MÉDIO) | Trigger BEFORE UPDATE/DELETE funciona no PostgreSQL (provado: UPDATE e DELETE diretos falham; `purgar_auditoria` remove o registro antigo). **Bypass comprovado**: o mesmo papel da aplicação altera `core_auditoria_controle.modo` para 2, faz UPDATE na trilha e volta o modo; também pode dropar o trigger, por ser dono da tabela. O trigger protege contra erro de código, não contra credencial comprometida. Correção: papel da aplicação só com `INSERT`/`SELECT` na trilha e sem acesso à tabela de modo; expurgo e saneamento por papel separado de manutenção |
| V-06 macros e links externos | BAIXO | **CORRIGIDO** | `_recusar_macros_e_links`: `vbaProject.bin`, `xl/externalLinks/`, content types habilitados para macro e `TargetMode="External"` são recusados |
| V-06 CSV com fórmula | BAIXO | **RISCO ACEITO** (BAIXO) | Decisão dos autores: bytes intactos (SHA-256 confere), download `attachment` com `nosniff`. Aceitável porque o upload é restrito a interno (`InternoEditaClienteVisualiza`, `coletas/views.py:573`): o vetor é interno para interno, não cliente para interno. Recomendação: orientação de uso e aviso no download |
| V-07 Tailwind alpha | BAIXO (pré-existente) | NÃO REVALIDADO | Fora do escopo desta rodada |
| **V-08 lock FOR UPDATE no PostgreSQL** | **CRÍTICO** (novo, pré-existente na base `143042f`) | **ABERTO: bloqueia produção PostgreSQL** | Ver seção 0.2 |
| V-09 testes e portabilidade (novo) | MÉDIO (qualidade) | **ABERTO** | Ver seção 0.3 |

### 0.2 V-08 — defeito crítico que a suíte SQLite não enxerga

`select_for_update()` combinado com `select_related()` em FKs anuláveis gera `LEFT OUTER JOIN` no lado nulo, e o PostgreSQL recusa com `NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join`. Afeta:

* `apps/osp/services.py:224` (`transicionar`, usada por `apps/osp/views.py:136`): toda mudança de status de OSP, inclusive a de finalização do checklist e a de apontamento de tempo.
* `apps/laudos/services.py:141` (`emitir_laudo`, usada por `apps/laudos/views.py:119`): toda emissão de laudo.

O código é do commit base `143042f`. Não foi introduzido pelos agentes. A suíte local roda em SQLite, que ignora `select_for_update`, por isso não acusou. Reprodução (`scratchpad/repro_lock.py`, PostgreSQL 16.14): as duas consultas atuais falham; com `select_for_update(of=("self",))` a consulta compila.

Prova da correção (cópia em `scratchpad/backend-fix`, só essas duas linhas alteradas, sem tocar no repositório): `apps.osp + apps.laudos + apps.notificacoes` no PostgreSQL = **265 OK, 2 skips, 0 erros**.

Suíte completa no PostgreSQL com o código atual: 1031 executados, **165 erros**. Desses, a grande maioria é V-08 (`test_matriz_completa_de_transicoes`, `ChecklistTests`, `TempoExecucaoTests`, `ConformidadeDocumentosTest`, etc.). Os demais estão listados em 0.3.

Correção recomendada: `select_for_update(of=("self",))` nos dois pontos, e uma suíte de CI com PostgreSQL. Enquanto isso, não há homologação possível no banco de produção para emissão de laudo e transição de OSP.

### 0.3 V-09 — testes e portabilidade

| Teste | Erro no PostgreSQL | Natureza |
|---|---|---|
| `apps/core/test_auditoria.py::AppendOnlyNoBancoTests` (2 testes) | Espera `IntegrityError`; o PostgreSQL devolve `ProgrammingError` | Teste, não produto (o trigger bloqueia). Trocar por `DatabaseError`. Não editei: arquivo dos autores |
| setUpClass de `apps.coletas.test_alinhamento.AlinhamentoApiTest` (e casos semelhantes de termografia) | `value too long for type character varying(18)` (campo CNPJ, `max_length=18`) | Provável dado de teste acima do limite; SQLite não impõe o tamanho. Origem exata por triar |
| `apps/core/test_seguranca_midia.py::test_foto_de_achado_respeita_o_cliente` | `AttributeError: 'HttpResponse' object has no attribute 'streaming_content'` | Não triado. Passa em SQLite. Pode ser diferença de armazenamento ou de caminho de mídia no PostgreSQL. **Em aberto** |
| Um teste com certificado de teste (traceback de `pyhanko_certvalidator`, `PathBuildingError`) | Certificado autoassinado sem raiz na cadeia | Módulo de origem não identificado nesta triagem. Passa em SQLite. Pode depender de configuração de raiz ou de ordem de testes. **Em aberto** |

### 0.4 Itens que ficaram sem verificação na rodada 1

* **Mídia com restrição de setor.** `apps/core/midia.py:65-73` aplica restrição por prefixo (achados, ensaios, placas, anexos, evidências e assinaturas de OSP). **Código confirmado; sem teste dedicado de setor**, e o teste existente de mídia falha no PostgreSQL (acima). PARCIAL.
* **Peças e ROI.** `apps/osp/execucao.py:151-170` grava `custo_material_real` e `custo_real`. `apps/osp/models.py` define `retorno_investimento = total_emergencial - total_preditiva`, que não lê `custo_real`. **ROI não alterado: CONFIRMADO por código**.
* **S-24 (cliente não lê rascunho).** `apps/core/test_homologacao_perfis.py:198` (`test_rascunhos_internos_ficam_fora_da_api_do_cliente`) e `:415` (`test_rascunho_invisivel_ao_cliente`). Passam em SQLite e não aparecem na lista de falhas do PostgreSQL. **CONFIRMADO por teste**.
* **`check --deploy` triado.** Com `DATABASE_URL` ausente, o `DEBUG` vira `True` (artefato do meu comando; W018 não vale para produção). Os avisos são de dois tipos: `drf_spectacular.W001/W002` (252, documentação de schema, sem risco de segurança) e `security.W004/W008/W012/W016` (HSTS, redirect SSL, cookies seguros), coerentes com a VPS atual só em HTTP (condição C1 de `docs/18`). **Triado: nenhum aviso novo de segurança além dos já conhecidos.**

### 0.5 Migrações e suíte nesta rodada

| Verificação | Resultado |
|---|---|
| `manage.py check` | OK (exit 0) |
| `makemigrations --check --dry-run` (SQLite e PostgreSQL) | Sem pendência (exit 0) |
| Suíte SQLite, 1ª execução | **1120 OK, 3 skipped** |
| Suíte SQLite, 2ª execução (determinismo) | **1123 OK, 6 skipped** (+3 provas PostgreSQL-only skipadas no SQLite) |
| Suíte PostgreSQL completa | 1031 executados, **165 erros** (V-08 e V-09) |
| Provas `test_validacao_agente4` | 14 OK no SQLite (3 skip); 14 OK no PostgreSQL |
| `migrate` do zero, PostgreSQL 16.14 | 146 aplicadas, 0 pendentes |
| `migrate` sobre a cópia dos dados reais (volume `thermopeoactive_pgdata` copiado em leitura) | 19 pendentes → 0 (`core.0002` aplicada). Tabelas de negócio com contagem idêntica (3377 linhas antes; só crescem tabelas de sistema) |
| Trigger no PostgreSQL | UPDATE e DELETE diretos falham; `purgar_auditoria` remove registro de 400 dias; bypass pelo papel da aplicação comprovado (V-05) |

### 0.6 Percentuais (rodada 2)

Regra: a mesma da rodada 1 (C = 1, P = 0,5), com estas exceções explícitas:

* Enquanto V-08 estiver aberto, a emissão de laudo (2.5) e a transição de OSP (2.6) não funcionam no PostgreSQL de produção. Por isso os blocos 2.5 e 2.6 ficam em **50%** no estado atual. Esse 50% é uma estimativa de bloqueio, não uma contagem item a item; o valor exato depende de mapear cada item de 2.5 e 2.6 à função afetada.
* V-01 corrigido: 2.10.1.3 vira C. Tempo real (2.7.1.1.8 e 2.8.1.3.4) passa a C, porque depende do push já corrigido.
* V-04 corrigido: 2.1.1.6 vira C.
* 3.1.22 segue P (resíduo V-05).

| Bloco | Rodada 1 | Rodada 2 (estado atual, V-08 aberto) | Rodada 2 (após corrigir V-08) |
|---|---|---|---|
| 2.1 Login e acesso (13) | 12,5 | **13 (100%)** | 13 |
| 2.2 Cadastros (18) | 18 | 18 | 18 |
| 2.3 Coleta sem IoT (33) | 32,5 | 32,5 (98%) | 32,5 |
| 2.4 Análise preditiva (10) | 10 | **10 (100%)** | 10 |
| 2.5 Laudos (13) | 13 | **6,5 (50%)** | 13 |
| 2.6 OSP (20) | 20 | **10 (50%)** | 20 |
| 2.7 Portal (8) | 7,5 | **8 (100%)** | 8 |
| 2.8 Dashboards (16) | 15,5 | **16 (100%)** | 16 |
| 2.9 Relatórios (10) | 10 | 10 | 10 |
| 2.10 Notificações (9) | 8,5 | **9 (100%)** | 9 |
| **Módulos funcionais §2 (150)** | 98,3% | **88,7% (133/150)** | **99,7% (149,5/150)** |
| **Login 2.1 + Laudos 2.5 + Portal 2.7 + Dashboards 2.8** | 97% | **87% (43,5/50)** | **100% (50/50)** |
| **Análise preditiva 2.4** | 100% | **100%** | 100% |
| **Geral: contrato completo** | ≈ 83% | **≈ 76%** (76,4) | **≈ 84%** (83,5) |
| **Geral: só o sistema (sem site, peso 90%)** | ≈ 92% | **≈ 85%** | **≈ 93%** |

Cálculo do geral (pesos do `docs/20` §3): §2 × 65%; arquitetura e banco (§1 e §3, 21,5/22 e 8,5/9, = 96,8%) × 10%; segurança Cl. 4.1 em 75% (não reavaliada) × 10%; site 0% × 10%; entrega 30% × 5%.

### 0.7 O que ainda bloqueia a homologação

1. **V-08** (crítico): emissão de laudo e transição de OSP falham no PostgreSQL. Bloqueia.
2. **V-09**: triagem de três falhas no PostgreSQL (mídia, pyhanko, CNPJ de teste). Bloqueia até triagem, porque o banco de produção é PostgreSQL e a suíte em PostgreSQL não passa.
3. **V-05**: resíduo de append-only (papel da aplicação dono da tabela). Não bloqueia a funcionalidade, mas o requisito "append-only de fato" só fica cumprido com separação de papéis.
4. Conferir a permissão de `EmpresaViewSet` (mudança fora do escopo do V-04).

Os defeitos V-01, V-02, V-03, V-04 e V-06 (macros e links) estão corrigidos e provados em SQLite e PostgreSQL, com os resíduos descritos acima.

---

## 1. Resumo executivo (rodada 1, mantido como histórico)

* **Regressão limpa e determinística.** Suíte completa 2 vezes: 1082 OK + 3 skips na primeira execução; 1087 OK + 3 skips na segunda (os 5 testes de prova já estavam incluídos). `manage.py check` e `makemigrations --check` sem pendência. `tsc --noEmit` e `npm run build` passam.
* **Migrações OK**: do zero em Postgres 16 (146 migrações, 0 pendentes); sobre cópia dos dados reais (18 pendentes aplicadas, 0 restantes, tabelas de negócio com contagem idêntica).
* **Três defeitos ALTOS que impedem homologação**, todos provados por teste:
  * **V-01 (ALTO)** SSRF no Web Push: o servidor faz POST para qualquer `https://` informado pelo usuário, inclusive IPs internos.
  * **V-03 (ALTO)** A trilha de auditoria grava em claro o `arquivo_cifrado` do certificado A1 (PFX cifrado com a chave da aplicação) e o e-mail dos usuários.
  * **V-04 (ALTO)** A restrição de setor (2.1.1.6) não é aplicada na análise preditiva (ranking de risco, tendência) nem em `/api/sensores/`.
* **Percentuais reais, recalculados com o método do `docs/20`:**

| Tópico | Antes (docs/20) | Agora (real) |
|---|---|---|
| Módulos funcionais do Anexo I §2 (150 itens) | 90% (135,5) | **98,3%** (147,5/150) |
| Login/acesso 2.1 + Laudos 2.5 + Portal 2.7 + Dashboards 2.8 | 96% (48/50) | **97%** (48,5/50) |
| Análise preditiva 2.4 | 85% (8,5/10) | **100%** (10/10), com ressalva do V-04 |
| **Geral do contrato completo** (pesos do docs/20 §3) | ≈ 77% | **≈ 83%** |
| Geral só do sistema (sem site institucional) | ≈ 85% | **≈ 92%** |

A diferença do geral vem sobretudo do §2 (+8 pontos percentuais no bloco de 65%). O site institucional continua em 0% e pesa 10%. Os defeitos ALTOS estão descontados nos itens de origem pela regra da seção 4 (2.10.1.3 rebaixado para P por V-01; 3.1.22 segue P por V-03; 2.1.1.6 segue P por V-04). Eles não foram tratados como bloqueadores globais de entrega, e o percentual não foi recalculado nessa hipótese.

---

## 2. Tabela de verificação por entrega

Legenda: **CONFIRMADO** (evidência reproduzível), **PARCIAL** (funciona, mas com lacuna ou sem evidência completa), **REFUTADO** (defeito provado), **NÃO VERIFICADO** (fora do alcance desta rodada).

### 2.1 Agente 1 — módulos funcionais

| Entrega | Veredito | Evidência |
|---|---|---|
| Upload de documentos: validação por conteúdo (PDF `%PDF-`, OOXML ZIP, CSV sem controle) | CONFIRMADO | `backend/apps/coletas/anexos.py:58-95`; `test_anexos_documento.py` na suíte (OK) |
| Upload: extensão trocada, tamanho máximo, sanitização de nome | CONFIRMADO | `anexos.py:45-54, 96-118` (limite `ANEXOS_MAX_BYTES`, padrão 20 MB) |
| Upload: proteção contra zip bomb | REFUTADO | V-02. `anexos.py:75` soma `file_size` do diretório central (valor forjável). Prova: `test_validacao_agente4.V02ZipBombDeclaradoTests` |
| Upload: macro/DOCX/XLSX com conteúdo externo e CSV com fórmula | PARCIAL | Leitura do código: não há rejeição de `vbaProject.bin`, `externalLink` nem neutralização de `=`, `+`, `-`, `@` no CSV (V-06). Não provado por teste |
| Sensores (`cadastros.Sensor`, `/api/sensores/`) com escopo de cliente | CONFIRMADO | `cadastros/views.py:219-225`; `models.py` (Sensor, 3.1.11) |
| Sensores: isolamento por setor | REFUTADO | V-04. Prova: `test_sensor_de_outro_setor_aparece_na_lista` |
| OSP: checklist com bloqueio de finalização | CONFIRMADO | `osp/execucao.py:112-131`; `osp/test_execucao.py` (OK na suíte) |
| OSP: evidências, apontamentos de tempo | CONFIRMADO | `osp/execucao.py:224-230`; `osp/views.py:256-322` |
| OSP: assinatura do cliente imutável com SHA-256 | CONFIRMADO | `osp/execucao.py:311-345` (hash em `estado_sha256`); `osp/models.py:784-789` (`save` e `delete` levantam `ValueError` para registro existente); `test_execucao.py:390 test_assinatura_e_imutavel` |
| OSP: Manutentor (interno) não assina | CONFIRMADO | `osp/views.py:192-202` (`ClienteAprovadorAssina`: só cliente aprovador); `test_execucao.py:407 test_perfil_que_nao_aprova_e_interno_nao_assinam` |
| OSP: peças alimentam custo de material sem mexer no ROI | NÃO VERIFICADO | Não auditado nesta rodada |
| Filtro `?criticidade_origem` nas OSPs | CONFIRMADO | `osp/test_filtro_criticidade.py` (OK na suíte) |
| OSP/anexos/mídia com restrição de setor | CONFIRMADO (OSP e anexos) / NÃO VERIFICADO (mídia) | `osp/views.py:264, 292, 322, 349`; `coletas/views.py:584` |
| Gráficos interativos e auto-atualização do portal | PARCIAL | Arquivos existem e compilam (`tsc`, build OK). Comportamento visual não verificado (sem navegador) |

### 2.2 Agente 2 — login, acesso, laudos, portal, BI

| Entrega | Veredito | Evidência |
|---|---|---|
| S-25 MFA obrigatório via sessão restrita `mfa_pendente` | CONFIRMADO | `accounts/authentication.py:73, 96` (sessão restrita devolve anônimo fora de `ROTAS_COM_MFA_PENDENTE`); `accounts/test_mfa_obrigatorio.py` (7 testes, OK) |
| S-24 cliente não lê rascunho | NÃO VERIFICADO | Sem prova dinâmica nesta rodada |
| S-26 `DJANGO_ADMIN_ENABLED` = DEBUG | NÃO VERIFICADO | Sem prova dinâmica nesta rodada |
| 2.1.1.6 restrição por setor (`core/escopo.py`, `RestricaoSetorUsuario`) | PARCIAL | Aplicada em OSP, anexos, equipamentos e medições (`core/test_escopo_setor.py`, OK). **Não aplicada na preditiva e em sensores** (V-04) |
| 3.1.2 dados pessoais da equipe | CONFIRMADO | `accounts/models.py:318+` (campos: nascimento, RG, CTPS, estado civil, filhos, endereço); `accounts/views.py:294-306` (só próprio usuário ou Master interno); excluído da trilha (`core/auditoria.py:35`) |
| 3.1.22 trilha de auditoria: só Master lê | CONFIRMADO | `core/views.py:14-22` (`IsMaster`, somente leitura) |
| 3.1.22 trilha sem segredos e sem dados pessoais | REFUTADO | V-03 (`arquivo_cifrado`, `titular`, e-mail gravados). Prova: `V03AuditoriaGravaSegredoCifradoTests` |
| 3.1.22 append-only | PARCIAL | Vale no ORM (`core/models.py:33-36, 82-83`), mas `QuerySet.update()` não é bloqueado e não há trigger no banco (V-05). Prova: `V05AuditoriaNaoEAppendOnlyNoBancoTests` |
| 2.5.1.3 assinatura PAdES com certificado A1 | CONFIRMADO | `laudos/assinatura.py`; `accounts/certificados.py:47-52` (Fernet); `laudos/test_assinatura_pades.py` (17 testes, OK), incluindo `test_upload_valida_senha_guarda_cifrado_e_nao_guarda_senha` (senha não é campo do modelo) e `test_adulteracao_quebra_a_integridade` |
| 2.5.1.3 cadeia ICP-Brasil real | NÃO VERIFICADO | Testado com certificado de teste. Confiança depende de `ASSINATURA_RAIZES_PEM` configurado na VPS |
| Web Push VAPID: ENVIADO só com 2xx | CONFIRMADO | `notificacoes/channels.py` (`PUSH_ACEITOS = {200, 201, 202}`); `notificacoes/test_web_push.py` (OK) |
| Web Push: validação do endpoint (SSRF) | REFUTADO | V-01. `notificacoes/views.py:100` só exige `https://`; `channels.py:198` faz o POST. Prova: `V01SsrfEndpointPushTests` |
| Web Push: pywebpush sem modificação | CONFIRMADO | Comentário em `channels.py` e `requirements.txt` (`pywebpush==2.0.3`) |
| Telas: auditoria, certificado, assinar/verificar laudo, push, setores | CONFIRMADO (por leitura) | `lib/nav.ts:155` (auditoria, `auditoria:ver`); `lib/permissions.ts:127` (só `interno && master`); componentes montados em `perfil/certificado-a1.tsx`, `laudos/assinatura-laudo.tsx`, `push/aviso-push.tsx`, `usuarios/setores-restritos.tsx`. Sem navegador |

### 2.3 Agente 3 — análise preditiva e fichas técnicas

| Entrega | Veredito | Evidência |
|---|---|---|
| Tendência linear/log-linear com IC e data até o limite validado | CONFIRMADO | `preditiva/tendencia.py`; `preditiva/test_estatistica_tendencia.py` (OK) |
| Tendência com aviso "não é probabilidade de falha" | CONFIRMADO | `preditiva/tendencia.py:17, 37` |
| Matriz de risco provisória, configurável, nunca probabilidade | CONFIRMADO | `preditiva/migrations/0002_matriz_risco_provisoria.py` (`validacao="PROVISORIA"`); `preditiva/models.py:37, 145-147`; `preditiva/risco.py:3, 147` ("Índice de priorização, não probabilidade de falha") |
| Sugestões por regra e por histórico com aceite | PARCIAL | `preditiva/views.py:252-256` (aceite só `IsInterno`); `sugestoes.py:9, 100` (aviso de frequência, não probabilidade). Ausência de sugestão genérica verificada só por leitura |
| Resultados históricos congelados não mudam | PARCIAL | Só verificado para vibração: snapshot e replay em `coletas/analise_preditiva.py:1-3, 133-139` ("Não consulta critérios mutáveis no replay"). Demais modalidades não verificadas |
| Módulos de coleta/relatório: espessura, RxI, ultrassom, energia, alinhamento, termografia de sistemas | CONFIRMADO | Arquivos `coletas/relatorio_tecnico/*.py` existem; nenhuma marca "não implementado" restante. Ausência de critério resulta em PENDENTE: `alinhamento.py:15, 166-168`; `ultrassom.py`; `qualidade_energia.py`; `espessura.py`; `motor_rxi.py`. Termografia de sistemas trata ΔT como aritmética sem classificar sem critério (`termografia_sistemas.py:10-11`) |
| ΔT classificado só por `LimiteAlarmeSerie` validado | CONFIRMADO | `coletas/models.py:446` ("Sem ele, pendente") |
| Isolamento da preditiva por cliente | CONFIRMADO | `preditiva/views.py` usa `escopo_cliente`/`recorte_cliente` |
| Isolamento da preditiva por setor | REFUTADO | V-04. `preditiva/views.py` não contém nenhuma chamada a `restringe_setor` (0 ocorrências). Provas: `test_ranking_de_risco_vaza_equipamento_de_outro_setor`, `test_tendencia_de_medicao_de_outro_setor_responde_200` |

### 2.4 Regras do projeto (seção 3 da tarefa)

| Regra | Veredito | Evidência |
|---|---|---|
| Nenhum limite normativo, tolerância ou fórmula inventado | CONFIRMADO (por leitura) | Módulos novos usam critério cadastrado e validado; sem critério → PENDENTE (ver 2.3) |
| Tailwind sem `/NN` sobre cores do DS em arquivos novos | CONFIRMADO | Varredura regex nos arquivos `.ts/.tsx` do diff. Os dois achados são linhas **pré-existentes** na base (V-07) |
| Layout aprovado dos PDFs não mudou | CONFIRMADO (por diff) | `git diff --numstat` em `coletas/relatorio_tecnico/` e `laudos/views.py`: só adições em módulos novos; `modulos.py` ganhou um módulo na tupla de registro; `laudos/views.py` e `relatorios/filtros.py` tiveram uma linha removida cada (import e filtro). Sem comparação byte a byte dos PDFs gerados |
| Dependências novas com licença compatível | CONFIRMADO (com ressalva) | `pywebpush==2.0.3` e `py-vapid 1.9.6`: MPL-2.0 (uso sem modificação é compatível). `pyhanko==0.38.0`: o metadado local não traz licença; a MIT é declarada upstream, não confirmada aqui |
| Sem commit de segredos e sem fallback silencioso de segurança | CONFIRMADO | `settings` recusou boot sem `SECRET_KEY`/`ALLOWED_HOSTS` (ver seção 5) |

### 2.5 Contrato — itens N e P de `docs/20` §2

| Item (docs/20) | Nota anterior | Nota agora | Justificativa |
|---|---|---|---|
| Cl. 2.2 Site institucional | N | **N** | Fora do escopo dos três agentes |
| 2.3.1.3 Upload de arquivos não-imagem | N | **C** | `anexos.py`; V-02 e V-06 são endurecimentos pendentes, não ausência da função |
| 2.6.2.2 Checklist técnico da OSP | N | **C** | `osp/execucao.py`; regra "pendente do cliente conta C" |
| 2.6.2.6 Assinatura do cliente na OSP | N | **C** | `osp/execucao.py:311-345`; imutável |
| 2.6.2.7 Controle de peças | N | **C** | `PecaOSPViewSet` (`osp/views.py:256`) |
| 2.10.1.3 Push notification | N | **P** | Funciona, mas o endpoint aceita SSRF (V-01). Vira C após a correção |
| 3.1.11 Entidade Sensores | N | **C** | `cadastros.Sensor` com CRUD e tela; isolamento por setor pendente (V-04, registrado em 2.1.1.6) |
| 2.1.1.6 Restrição por setor | P | **P** | Aplicada em OSP, anexos e medições; ausente na preditiva e em sensores (V-04) |
| 2.3.2.2.2–4 Termografia mecânica/processos | P | **C** | Módulo de relatório existente; ΔT só com critério validado |
| 2.3.2.5 Ensaios em motores (RxI) | P | **C** | `coletas/relatorio_tecnico/motor_rxi.py` e `coletas/motor_rxi.py` |
| 2.3.2.6 / 2.3.2.7 / 2.3.2.10 Ultrassom, espessura, qualidade de energia | P | **C** | Módulos com classificação por critério validado; sem critério → PENDENTE |
| 2.3.2.8.1.1–2 Alinhamento a laser | P | **C** | `relatorio_tecnico/alinhamento.py` |
| 2.4.1.3 Tendência descritiva | P | **C** | `preditiva/tendencia.py` com aviso |
| 2.4.1.5 Indicadores de risco | P | **C** | Matriz provisória e configurável, com aviso (pela regra de padrão documentado) |
| 2.4.2.4 Sugestões técnicas | P | **C** | Regra e histórico com aceite; sem genérico |
| 2.5.1.3 Assinatura digital (ICP-Brasil) | P | **C** | PAdES com A1 implementado e testado; cadeia real NÃO VERIFICADA |
| 2.6.2.4 Evidências da OSP | P | **C** | `EvidenciaOSPViewSet` com upload |
| 2.6.2.8 Tempo de execução | P | **C** | `ApontamentoExecucao` (`osp/execucao.py:224-230`) |
| 2.7.1.1.8 / 2.8.1.3.4 "Tempo real" | P | **P** | Auto-atualização a cada 60 s existe; push ainda depende de V-01 |
| 1.1.5 / Cl. 4.1 VPS HTTP, backup externo | P | **P** | Fora dos três agentes; não reavaliado |
| 3.1.2 Equipe técnica (campos pessoais) | P | **C** | Todos os campos listados no docs/20 existem em `DadosPessoaisUsuario` |
| 3.1.22 Trilha de alterações de cadastro | P | **P** | Implementada, mas com V-03 (dado sensível gravado) e V-05 (não append-only no banco) |

---

## 3. Defeitos encontrados

| ID | Severidade | Onde (arquivo:linha) | Descrição | Prova | Correção sugerida | Responsável |
|---|---|---|---|---|---|---|
| **V-01** | **ALTO** | `backend/apps/notificacoes/views.py:100`; `backend/apps/notificacoes/channels.py:198` | SSRF no Web Push. `PushAssinaturaView` só exige `https://`. Qualquer usuário autenticado, inclusive cliente, registra endpoint interno (127.0.0.1, rede Docker, 169.254.169.254) e o servidor faz POST nele. O status HTTP do alvo volta em `erros` ("HTTP <código>") | `apps/core/test_validacao_agente4.py::V01SsrfEndpointPushTests` (passa) | Lista de hosts dos push services conhecidos (FCM, Mozilla, WNS, Apple) com validação do host por sufixo; resolver DNS e rejeitar IPs privados, loopback e link-local; não seguir redirecionamentos; rejeitar portas não padrão. Até corrigir, manter `NOTIFICACOES_PUSH_ENABLED=False` em produção | Agente 2 (notificações) |
| **V-02** | MÉDIO | `backend/apps/coletas/anexos.py:75` | Proteção contra zip bomb confia no `file_size` do diretório central, que o próprio arquivo declara. Um DOCX de 101 MB reais, com cabeçalho declarando 1000 bytes, passa | `V02ZipBombDeclaradoTests` (passa, e mede 101 MB reais com `zlib`) | Contar bytes reais durante a leitura de cada membro (com limite), ao invés de somar o valor declarado | Agente 1 (anexos) |
| **V-03** | **ALTO** | `backend/apps/core/auditoria.py:32-38` (`APPS_RASTREADOS`, `_PADROES_SENSIVEIS`); `backend/apps/accounts/models.py:350-359` (`CertificadoA1`) | A trilha grava `arquivo_cifrado` (PFX cifrado com a chave da aplicação), `titular`, `numero_serie` e o e-mail dos usuários (`accounts.User`). `CertificadoA1` não está em `MODELOS_EXCLUIDOS` e o nome `arquivo_cifrado` não casa com `_PADROES_SENSIVEIS`. A trilha é append-only, então o cifrado não pode ser removido por API | `V03AuditoriaGravaSegredoCifradoTests` (passa, para `arquivo_cifrado` e e-mail) | Adicionar `accounts.CertificadoA1` a `MODELOS_EXCLUIDOS`; incluir `arquivo`, `cifrado` e `email` em `_PADROES_SENSIVEIS` ou mascarar o modelo inteiro; avaliar purga dos registros já gravados (`purgar_auditoria`) | Agente 2 (auditoria) |
| **V-04** | **ALTO** | `backend/apps/preditiva/views.py:31-45` (`TendenciaView`), `:219-237` (`RankingRiscoView`), demais views (0 chamadas a `restringe_setor`); `backend/apps/cadastros/views.py:74` (`BaseCadastroViewSet`), `:219-225` (`SensorViewSet`) | Cliente restrito ao Setor 1 vê ranking de risco de equipamentos do Setor 2, tendência de medições do Setor 2 (HTTP 200) e sensores do Setor 2. A restrição 2.1.1.6 não chega a esses módulos | `V04RestricaoSetorNaoAplicadaNaPreditivaTests` (3 testes, passam) | Aplicar `restringe_setor` com o caminho ORM até o setor (`equipamento__setor`, `inspecao__...`) em todas as views de preditiva e em `BaseCadastroViewSet` quando o modelo tiver `equipamento`. Acrescentar teste de regressão | Agente 3 (preditiva) e Agente 2 (escopo) |
| **V-05** | MÉDIO | `backend/apps/core/models.py:33-36` (`RegistroAuditoriaQuerySet`), `:77-83` | "Append-only" só no ORM. `QuerySet.update()` altera registros sem bloqueio e não há trigger ou `REVOKE UPDATE, DELETE` no PostgreSQL | `V05AuditoriaNaoEAppendOnlyNoBancoTests` (passa) | Sobrescrever `update()` no QuerySet; no banco, criar trigger `BEFORE UPDATE OR DELETE` que lance exceção, ou dar à aplicação somente `INSERT`/`SELECT` na tabela | Agente 2 (auditoria) |
| **V-06** | BAIXO | `backend/apps/coletas/anexos.py:58-95` | Por leitura do código: XLSX/DOCX aceitos com `vbaProject.bin` ou `externalLink`; CSV com `=`, `+`, `-`, `@` no início de célula não é neutralizado (injeção de fórmula ao abrir no Excel). Não provado por teste | Não provado (leitura) | Rejeitar partes de macro e links externos no OOXML; prefixar com `'` células CSV que começam com caracteres de fórmula na exportação | Agente 1 (anexos) |
| **V-07** | BAIXO (pré-existente) | `frontend/src/app/(admin)/inspecoes/campo/[id]/folha-campo.tsx:874` (`bg-surface/95`); `frontend/src/features/alertas/lista-alertas.tsx:204` (`hover:bg-surface-muted/60`) | Opacidade sobre cor do DS definida como `var(--...)`, que pode não gerar CSS. Ambas as linhas já existiam na base; não foram introduzidas nesta rodada. Não verificado no CSS gerado | Presença confirmada na base (`git show 1507fd6`) | Conferir o CSS gerado no build; se faltar, usar cor com `<alpha-value>` ou `color-mix` | Frontend (base) |

---

## 4. Método de pontuação e percentuais

Método do `docs/20` §1 (C = 1, P = 0,5, N = 0). Base dos blocos: a §1 do `docs/20` (valores antigos); soma-se o ganho de cada item que mudou de nota. Não reescrevi a pontuação de blocos que não mudaram.

Regra adicional desta validação: defeito ALTO **na própria funcionalidade** do item rebaixa C para P até corrigir. Por isso 2.10.1.3 (V-01) e 3.1.22 (V-03) ficaram P. V-04 foi atribuído ao item 2.1.1.6 (restrição por setor), que é o requisito violado, e não aos itens de preditiva, que funcionam dentro do próprio escopo de cliente.

### 4.1 Módulos funcionais, Anexo I §2 (150 itens)

| Bloco | Itens | Antes | Agora | % |
|---|---|---|---|---|
| 2.1 Login e acesso | 13 | 12,5 | 12,5 | 96% |
| 2.2 Cadastros | 18 | 18 | 18 | 100% |
| 2.3 Coleta (sem IoT) | 33 | 27 | **32,5** | **98%** |
| 2.4 Análise preditiva | 10 | 8,5 | **10** | **100%** |
| 2.5 Laudos | 13 | 12,5 | **13** | **100%** |
| 2.6 OSP | 20 | 16 | **20** | **100%** |
| 2.7 Portal | 8 | 7,5 | 7,5 | 94% |
| 2.8 Dashboards/BI | 16 | 15,5 | 15,5 | 97% |
| 2.9 Relatórios | 10 | 10 | 10 | 100% |
| 2.10 Notificações | 9 | 8 | **8,5** | **94%** |
| **Total §2** | **150** | **135,5** | **147,5** | **98,3%** |

Ganho em 2.3 (+5,5): 2.3.1.3 (+1), 2.3.2.2.2–4 (+1,5), 2.3.2.5 (+0,5), 2.3.2.6/7/10 (+1,5), 2.3.2.8.1.1–2 (+1).
Observação: a soma por item de 2.3 descrita no `docs/20` §2 dá 27,5 e não 27. Usei a pontuação da §1 como base.

### 4.2 Login (2.1) + Laudos (2.5) + Portal (2.7) + Dashboards (2.8)

(12,5 + 13 + 7,5 + 15,5) / (13 + 13 + 8 + 16) = 48,5 / 50 = **97%** (antes 96%).

### 4.3 Análise preditiva (2.4)

10 / 10 = **100%** (antes 85%). Ressalva: V-04 (vazamento por setor na preditiva) e matriz de risco marcada como provisória, o que o contrato trata como padrão a confirmar pelo cliente.

### 4.4 Geral (pesos do `docs/20` §3)

| Bloco | Peso | Resultado | Contribuição |
|---|---|---|---|
| Módulos funcionais §2 | 65% | 98,3% | 63,9 |
| Arquitetura + banco (§1 e §3) | 10% | 96,8% (=(8,5 + 21,5)/31) | 9,7 |
| Segurança/infra (Cl. 4.1) | 10% | 75% (não reavaliado) | 7,5 |
| Site institucional (Cl. 2.2) | 10% | 0% | 0 |
| Entrega e homologação (Cl. 9) | 5% | 30% (inalterado) | 1,5 |
| **Contrato completo** | 100% | | **≈ 83%** (82,6) |
| **Só o sistema** (sem o site, peso 90%) | 90% | | **≈ 92%** (82,6 / 90) |

Se os defeitos ALTOS forem tratados como bloqueadores de homologação, o percentual cai; esse cenário não foi calculado.

Em §3 (entidades, 22 itens): 3.1.11 (+1) e 3.1.2 (+0,5) → 21,5 / 22. Arquitetura (§1, 9 itens, 8,5) inalterada.

---

## 5. Regressão, reprodutibilidade e migrações

| Verificação | Resultado | Como reproduzir |
|---|---|---|
| Suíte completa, 1ª execução | **1082 OK, 3 skipped**, 318 s | `backend/.venv/Scripts/python.exe manage.py test` (SQLite) |
| Suíte completa, 2ª execução (determinismo) | **1087 OK, 3 skipped** (inclui as 5 provas iniciais; mesmos 1082 da 1ª) | idem |
| Provas desta validação | 9 OK (V-01 ×2, V-02 ×1, V-03 ×2, V-04 ×3, V-05 ×1) | `manage.py test apps.core.test_validacao_agente4` |
| Linha de base anterior | 755 OK, 3 skipped | Informada na tarefa (não reexecutei a base) |
| `manage.py check` | OK (exit 0) | |
| `manage.py makemigrations --check --dry-run` | Sem migração pendente (exit 0) | |
| `migrate` do zero, Postgres 16.14 descartável | 146 migrações aplicadas, 0 pendentes | container `postgres:16-alpine` vazio, `DATABASE_URL` apontando para ele |
| `migrate` sobre cópia dos dados reais | 18 pendentes → 0. Tabelas de negócio com contagem idêntica (ver nota) | Volume `thermopeoactive_pgdata` copiado com `cp -a` por container auxiliar com montagem **somente leitura**; Postgres 16 descartável sobre a cópia; `pg_dump -Fc` pré-migração salvo no scratchpad |
| `showmigrations` após migrar | 0 linhas `[ ]` | idem |
| `tsc --noEmit` (frontend) | OK, exit 0, sem saída | `cd frontend && npx tsc --noEmit` |
| `npm run build` (frontend) | OK, exit 0 | `cd frontend && npm run build`; `tsconfig.tsbuildinfo` restaurado depois |

Nota sobre a contagem da cópia: as 94 tabelas existentes na cópia mantêm contagem idêntica, exceto as de sistema (`auth_permission`, `django_content_type`, `django_migrations`), que crescem com os apps novos. A migração de dados `preditiva.0002` criou a matriz provisória global (+1 linha em `preditiva_matrizrisco`) e seu registro de auditoria (+1 em `core_registroauditoria`). Nenhuma linha de negócio foi perdida ou alterada. Migração de dados, após o `migrate`, foi conferida tabela a tabela. Dados de produção foram lidos apenas por cópia; o container `thermoproactive_db` (já parado, `Exited (255)`) não foi iniciado, parado nem recriado.

Ponto de atenção: `manage.py check --deploy` retorna 254 avisos (principalmente HSTS, cookies e SSL), esperados para a VPS atual, que é só HTTP (`docs/18`, condição C1). Não triados um a um.

---

## 6. Itens não verificados nesta rodada

* **Telas no navegador.** A presença de rotas, itens de menu e componentes foi verificada por leitura (`lib/nav.ts`, `lib/permissions.ts`, arquivos `app/` e `features/`). Não houve navegação real nem captura de tela.
* **Chamadas de API do front.** Os caminhos de `/api/...` novos foram conferidos contra os `register()` e `path()` do backend: todos existem. Não verifiquei método e corpo campo a campo.
* **Peças da OSP e ROI.** Não verificado que o custo de material das peças não altera o cálculo de ROI.
* **Mídia com restrição de setor.** Não verificado.
* **S-24 e S-26.** Sem prova dinâmica nesta rodada.
* **Resultados congelados fora da vibração.** Só o snapshot de vibração foi lido (`analise_preditiva.py`).
* **Sugestões nunca genéricas.** Verificado por leitura, não por bateria de casos.
* **PAdES com cadeia ICP-Brasil real.** Testado só com certificado de teste; a confiança depende de `ASSINATURA_RAIZES_PEM` na VPS.
* **Push real.** Sem navegador nem serviço de push real; só o contrato HTTP mockado.
* **Comparação byte a byte dos PDFs.** Layout verificado pelo diff de código, não pelo PDF gerado.
* **Cl. 4.1 e 1.1.5 (segurança/infra).** Não reavaliados; mantidos no valor do `docs/20`.
* **Licença do pyHanko 0.38.0.** MIT declarada upstream, não confirmada no metadado local.
* **Dados de produção.** A cópia foi tirada de volume do container parado; não houve verificação de que o estado é o mesmo de produção ao vivo.

---

## 7. Ordem recomendada de correção

1. **V-01** (SSRF no push): bloqueia 2.10.1.3. Enquanto isso, `NOTIFICACOES_PUSH_ENABLED=False` em produção.
2. **V-04** (setor na preditiva e sensores): afeta 2.1.1.6 e a confiança na restrição de cliente.
3. **V-03** (trilha com cifrado e e-mail): remover do log o `arquivo_cifrado`; avaliar purga dos registros gravados.
4. **V-05** (append-only real no banco) e **V-02** (zip bomb).
5. **V-06** e **V-07** (endurecimentos e pré-existente de CSS).

Após as correções, convém acrescentar testes de regressão que exijam o comportamento seguro, invertendo as provas `V01` a `V05` de `backend/apps/core/test_validacao_agente4.py`.
