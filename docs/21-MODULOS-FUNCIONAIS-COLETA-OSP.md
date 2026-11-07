# 21 — Módulos funcionais (coleta e OSP): item do contrato × implementação

Data: 02/11/2026 · Base: `main` (`143042f`) + alterações não commitadas do working tree.
Escopo deste documento: itens 2.3.1.3, 3.1.11 e demais itens da lista do Agente 1, com o
que ficou **implementado**, **parcial** e **pendente**. Nada aqui foi commitado.

## 1. Situação por item

| Item do contrato | Situação | Implementação | Tela | Endpoint | Testes |
|---|---|---|---|---|---|
| **2.3.1.3 Upload de arquivos** | **Concluído** | `coletas/anexos.py`, `coletas.AnexoDocumento` (migração `coletas/0017_anexo_documento`), `core/midia.py`, `features/inspecoes/anexos-documentos.tsx` | Painel "Documentos" no cadastro do equipamento (`app/(admin)/equipamentos`) e na folha de campo da inspeção (`app/(admin)/inspecoes/campo/[id]`, vinculado ao relatório) | `/api/anexos-documentos/` (CRUD) · download `/api/media/anexos/documentos/<uuid>.<ext>` | `coletas/test_anexos_documento.py` |
| **3.1.11 Sensores** | **Concluído (cadastro)** | `cadastros.Sensor` (migração `cadastros/0037_sensor`, criada antes da mudança de dono de `cadastros`), `SensorSerializer`, `SensorViewSet`, catálogo "Sensores" em `features/cadastros/catalogos.ts`, painel `features/cadastros/sensores-do-equipamento.tsx` | Catálogo "Sensores" em `/cadastros`; lista no cadastro do equipamento | `/api/sensores/` | `cadastros/test_sensores.py` |
| **S-24 aplicado à mídia** | Concluído | `core/midia.py` (`FILTRO_EXTRA_CLIENTE`): foto de achado só sai ao cliente com `achado.visivel_cliente=True` | — | `/api/media/achados/...` | `coletas/test_anexos_documento.py::MidiaAchadoLiberacaoTests` |
| 2.3.2.2.2–4 Termografia mecânica/processos | **Não iniciado** | — | — | — | — |
| 2.3.2.8.1.1–2 Alinhamento a laser | **Não iniciado** | — | — | — | — |
| 2.3.2.5 RxI motores · 2.3.2.6 Ultrassom · 2.3.2.7 Espessura · 2.3.2.10 QE | **Não iniciado** | — | — | — | — |
| **2.6.2.2 Checklist técnico** | **Concluído** | `osp.ModeloChecklist`, `ItemModeloChecklist`, `RespostaChecklist`; `osp/execucao.py`; `services.transicionar` bloqueia FINALIZADA com item obrigatório pendente (`checklist_pendente`) | Painel "Checklist técnico" em `app/(admin)/osps` (equipe) e `app/portal/ordens-servico/editar` (cliente, só leitura) | `/api/osp-checklists/` (Master) · `/api/osp-checklist-itens/` (Master) · `/api/osps/{id}/checklist/` (GET; POST equipe) | `osp/test_execucao.py::ChecklistTests` |
| **2.6.2.4 Evidências fotográficas** | **Concluído** | `osp.EvidenciaOSP` (fases antes/durante/depois/outra); validação por conteúdo (Pillow); regra `osp/evidencias/` em `core/midia.py` | Painel "Evidências fotográficas" (equipe envia; cliente vê as da própria OSP) | `/api/osp-evidencias/` | `osp/test_execucao.py::EvidenciasTests` |
| **2.6.2.6 Assinatura do cliente** | **Concluído** | `osp.AssinaturaOSP` (OneToOne, imutável: `save`/`delete` levantam erro); canvas no Portal; hash SHA-256 canônico do estado (`execucao.estado_sha256`); IP via `accounts.security.ip_do_cliente`; registro em `HistoricoOSP` (tipo `ASSINATURA`); regra `osp/assinaturas/` em `core/midia.py` | Painel "Assinatura do cliente" em `app/portal/ordens-servico/editar/[id]` | `/api/osp-assinaturas/` (POST: CLIENTE_CORP/LOCAL/PCM da própria OSP; só em EXECUTADA/AGUARDANDO_APROVACAO/FINALIZADA) | `osp/test_execucao.py::AssinaturaTests` |
| **2.6.2.7 Controle de peças** | **Concluído** | `osp.PecaOSP` (descrição, código, quantidade, unidade, custo unitário); `OrdemServico.custo_material_real` = soma das peças; **custo real** = estimativa sem material + material aplicado; **ROI não muda** (continua em `total_preditiva`/`total_emergencial`) | Painel "Peças e materiais aplicados" | `/api/osp-pecas/` | `osp/test_execucao.py::PecasTests` |
| **2.6.2.8 Tempo de execução** | **Concluído** | `osp.ApontamentoExecucao`: abre ao entrar em EM_EXECUCAO e fecha ao sair (inclusive a rejeição, que conta como retrabalho); apontamento manual com início/fim validados; `tempo_execucao_min` no serializer | Painel "Tempo de execução" | `/api/osp-apontamentos/` | `osp/test_execucao.py::TempoExecucaoTests` |

Migrações de `osp`: `0011_checklist_evidencias_pecas_execucao_assinatura` (inclui
`TipoHistorico.ASSINATURA` e `OrdemServico.custo_material_real`).

Os itens das fichas técnicas (2.3.2.x) passaram para o Agente 3. Nesta entrega, o que
ficou fora é esse bloco técnico e a parte de relatório modular.

## 2. Upload de documentos (2.3.1.3)

**Modelo** `coletas.AnexoDocumento` (`BaseModel`): `cliente` (obrigatório), `inspecao`,
`equipamento`, `relatorio` (ao menos um vínculo), `categoria`, `arquivo`, `nome_original`,
`tamanho_bytes`, `sha256`, `descricao`, `visivel_cliente` (padrão `False`), `enviado_por`.

**Validação pelo conteúdo** (`coletas/anexos.py::conferir_conteudo`):

- PDF: assinatura `%PDF-`; recusa `/JavaScript`, `/Launch` e `/EmbeddedFile` em texto
  (heurística; não substitui antivírus).
- XLSX/DOCX: contêiner ZIP com `[Content_Types].xml` e `xl/workbook.xml` ou `word/document.xml`;
  limite de 100 MB descompactados (proteção contra zip bomb).
- CSV: sem bytes de controle; decodifica em UTF-8 (com BOM) ou cp1252.
- Extensão fora de PDF/XLSX/DOCX/CSV (inclui `.xlsm`) é recusada.

**Limite:** `ANEXOS_MAX_BYTES` (env, padrão 20 MB), em `config/settings.py`.

**Disco:** o nome gravado é `anexos/documentos/<uuid><ext>` (`ArmazenamentoAnexo`); o nome do
usuário só aparece sanitizado em `nome_original` (sem caminho, aspas, controle; máx. 120).

**Vínculo:** todos os vínculos (inspeção, equipamento, relatório) têm de pertencer ao mesmo
`cliente`, senão 400. O arquivo não é trocado após o envio; a exclusão apaga o arquivo do
disco só após o commit.

**Download** (`core/midia.py`): sempre `Content-Disposition: attachment` com nome UTF-8
(RFC 6266), `nosniff` e CSP `sandbox`. Nunca `inline`. Cliente só baixa o que tem
`visivel_cliente=True` do próprio cliente; fora do escopo = 404.

**Permissões:** interno (ADMIN/GESTOR/TÉCNICO) cria e edita; exclusão exige nível Master.
Cliente só lê, e só os visíveis do próprio cliente. Sem login = 401/403.

## 3. Sensores (3.1.11)

`cadastros.Sensor`: equipamento (obrigatório), ponto de instalação, tipo (acelerômetro,
velocímetro, termopar, PT100, transdutor de pressão/corrente/tensão, outro), fabricante,
modelo, nº de série, grandeza, unidade, faixa mín./máx., datas de instalação e última
calibração, status (ativo, em manutenção, inativo, desinstalado), `identificador_externo`
(reservado ao IoT futuro) e observações.

- Escopo por cliente: `campo_cliente = "equipamento__setor__area__cliente"` (`BaseCadastroViewSet`).
- Validações: faixa mínima ≤ máxima; datas não futuras.
- Exclusão lógica (`ativo=False`), como os demais cadastros.
- **Sem ingestão automática.** O contrato marca a coleta IoT (2.3.1.5) como futura.

Os tipos de sensor e os status são opções de cadastro do sistema, não limites normativos.

## 4. Parametrização que depende do cliente

- **Critérios de avaliação** dos novos ensaios (RxI, ultrassom, espessura, QE) e de
  termografia mecânica: sem critério cadastrado, o resultado deve ficar PENDENTE. Nenhum
  limite foi inventado. Dependem de normas/acordos informados pelo cliente.
- **Modelos de checklist da OSP** (2.6.2.2): conteúdo definido pelo cliente, por tecnologia.
- **Forma de assinatura do cliente** (2.6.2.6): se basta a assinatura desenhada ou se exige
  certificado (ICP-Brasil). Hoje a assinatura é aprovação eletrônica interna.
- **Escopo de peças** (2.6.2.7): campos de descrição, código, unidade e custo.
- **Restrição por setor/unidade** (2.1.1.6): não implementada; depende de confirmação.

## 5. Pendências técnicas

- Itens 2.3.2.x (fichas e relatórios modulares de RxI, ultrassom, espessura, QE, termografia e
  alinhamento) passaram para o Agente 3, que é o dono de `apps/ensaios`, `coletas/relatorio_tecnico`,
  `features/relatorio-inspecao` e das migrações de `coletas`.
- Painel de execução da OSP: `features/osp/painel-execucao.tsx` (uso de `canvas` para a assinatura;
  não testado em navegador, só `tsc --noEmit`).
- Nginx: o location `/protected-media/` é `internal` e passa o `Content-Disposition` do
  upstream. O limite `client_max_body_size` deve ser conferido para uploads de até 20 MB.

## 6. Painéis: gráficos interativos e atualização automática (2.8.1.3)

| Item | Implementação | Tela | Dados (sem fórmula nova) |
|---|---|---|---|
| **2.8.1.3.1 Gráficos interativos** | `components/graficos-interativos.tsx`: `GraficoRosca` e `GraficoBarras`, em SVG próprio, sem lib nova. Tooltip com valor e percentual do que está visível; legenda que liga e desliga cada série (ao menos uma fica visível); clique ou Enter/Espaço com foco aciona o destino; alternativa textual em `sr-only` | Painel operacional (`app/(admin)/dashboard`): distribuição das medições. Clique em **Crítico** → `/osps?criticidade_origem=CRITICO` (lista de OSPs filtrada; o filtro aparece como chip com "limpar"); **Pendente** não tem destino (ver limitação); Painel executivo: evolução mensal. Clique num mês **aplica o período desse mês** no filtro da tela. Portal (`app/portal/page.tsx`, também servido em `/portal/dashboard`): "Estado do parque". Clique em **Exigem intervenção** → `/portal/equipamentos?estado=critico`; nas demais → `/portal/equipamentos` | `indicadores.py` (`operacional`, `executivo`) e `/portal/visao-geral/` |
| **2.8.1.3.4 Atualização automática (portal)** | `useRecurso(..., { atualizarACadaMs: 60_000 })` (mecanismo do Agente 2 em `lib/recurso.ts`): busca em silêncio, pausa com a aba oculta, mantém o último dado válido em erro. Indicação de "Atualizado às HH:MM" na tela | `app/portal/page.tsx` | `/portal/visao-geral/` |

Os painéis operacional e executivo já atualizavam a cada 60 s. Nada aqui calcula indicador novo: o
gráfico só mostra o que o servidor já entrega, e o percentual é a razão visível ÷ total visível.

Limitações conhecidas:

- **Filtro de OSP por criticidade de origem** (`?criticidade_origem=CRITICO|ALERTA|NORMAL`): implementado
  no backend (`OrdemServicoViewSet.get_queryset`, valor fora da lista = 400, escopo de cliente
  mantido) e na tela `app/(admin)/osps` (lê a URL e mostra o chip "limpar"). Testes em
  `apps/osp/test_filtro_criticidade.py` (6 testes).
- **Pendente de critério: sem drill-down.** O estado existe em medições (`classificacao_status =
  PENDENTE`, filtros em `/medicoes-*`), mas a análise final lista *achados*, que não têm esse estado, e
  não há tela de lista de medições. Para fechar, precisa de uma tela/filtro em `coletas` (Agente 3).
  Por isso a fatia "Pendente" da rosca não tem link.
- Nenhum gráfico foi exercitado em navegador; a verificação foi `tsc --noEmit` e os testes do backend.

## 7. Termografia mecânica/processos e alinhamento a laser (2.3.2.2.2–4, 2.3.2.8.1.1–2)

Estes módulos já existem no código, do Agente 3. Esta rodada apenas revisou o que falta.

- **Alinhamento a laser:** completo em `coletas/alinhamento.py` e `coletas/relatorio_tecnico/alinhamento.py`. A tolerância vem só de `LimiteAlarmeSerie` VALIDADA; sem critério, PENDENTE. Não criei ficha paralela em `servicos`: a versão que eu tinha começado foi removida (migração, modelos, API e testes), para não duplicar.
- **Termografia mecânica/processos:** módulo de relatório e tela existem. **Lacuna:** `coletas/rules.py::classificar_termografia` não consulta o critério `LimiteAlarmeSerie` (modalidade `TERMOGRAFIA`, grandeza `delta_t`, VALIDADA). Hoje toda ΔT fica PENDENTE. A ligação é uma mudança pequena no arquivo do Agente 3.
- **Migrações:** nenhuma migração nova nesta rodada (`makemigrations --check` sem mudanças). O rótulo "(não implementado)" de `ModuloTecnico` em `cadastros` continua; trocá-lo exige migração em `cadastros`, que é do Agente 3.
