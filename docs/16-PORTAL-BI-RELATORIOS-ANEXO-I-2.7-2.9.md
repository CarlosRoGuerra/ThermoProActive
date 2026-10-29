# Portal do cliente, BI e relatórios (Anexo I, itens 2.7, 2.8 e 2.9)

Auditoria e correções de 2026-10-27. As fórmulas dos painéis vivem num módulo só,
`backend/apps/relatorios/indicadores.py`. Tela e exportação chamam as mesmas funções,
então o número do arquivo é o número da tela. Os filtros vivem em `apps/relatorios/filtros.py`.

## 1. Matriz requisito × tela × endpoint × teste

Testes: `R` = `apps/relatorios/tests.py`, `D` = `apps/coletas/test_dashboard_cliente.py`,
`O` = `apps/osp/test_fluxo.py`, `L` = `apps/laudos/test_conformidade_documentos.py`.

| Item | Requisito | Tela | Endpoint | Testes | Situação |
|---|---|---|---|---|---|
| 2.7.1.1.1 | Acompanhamento de inspeções | `/portal/inspecoes`, `/portal/inspecoes/[id]` | `GET /api/inspecoes/` | R `Isolamento.test_listas_do_portal_respeitam_o_escopo` | Atendido |
| 2.7.1.1.2 | Visualização de laudos | `/portal/laudos`, `/portal/laudos/[id]` | `GET /api/laudos/` | L `test_portal_ve_emitido_proprio_mas_nao_rascunho`, `test_portal_outro_cliente_…`; R `test_portal_conta_os_laudos_do_fluxo_novo` | Atendido (corrigido: o portal não contava laudos do fluxo novo) |
| 2.7.1.1.3 | Download de relatórios | `/portal/relatorios` | `GET /api/relatorios/{key}/?formato=` | R `Isolamento.test_cliente_nunca_ve_dado_de_outro_em_nenhum_formato`, `test_relatorios_e_painel_internos_bloqueados_…` | Atendido |
| 2.7.1.1.4 | Acompanhamento de OS | `/portal/ordens-servico` | `GET/PATCH /api/osps/` | O `EscopoPorClienteTest`; R `test_listas_…` | Atendido |
| 2.7.1.1.5 | Histórico de serviços | `/portal` (bloco Histórico) | `GET /api/portal/visao-geral/` | R `test_painel_e_portal_do_cliente_so_com_o_proprio_parque` | Atendido |
| 2.7.1.1.6 | Dashboard personalizado | `/portal` (`/portal/dashboard` é alias) | `GET /api/portal/visao-geral/` | idem | Atendido |
| 2.7.1.1.7 | Indicadores de desempenho | `/portal` (cartões) | idem | R `test_conta_de_cliente_sem_empresa_nao_ve_nada` | Atendido; disponibilidade é proxy (§4) |
| 2.7.1.1.8 | Notificações em tempo real | `/portal/alertas`, sino | `GET /api/notificacoes/`, `/resumo/` | R `test_notificacoes_sao_so_do_proprio_usuario` | Parcial: atualização por consulta a cada 60 s, não push (§4) |
| 2.8.1.1.1 | Quantidade de inspeções | `/dashboard` (Operacional) | `GET /api/dashboard/` | R `PrecisaoDosIndicadores.*` | Atendido |
| 2.8.1.1.2 | Equipamentos críticos | idem | idem | R `test_operacional_do_cliente_a` | Atendido (corrigido: agregava pela TAG e contava desativados) |
| 2.8.1.1.3 | Falhas recorrentes | idem | idem | R `test_operacional_do_cliente_a` | **Novo**, proxy (§4) |
| 2.8.1.1.4 | SLA de atendimento | idem | idem | R `test_operacional_do_cliente_a`; O `PaineisTest` | **Novo** |
| 2.8.1.1.5 | OS abertas | idem | idem | O `PaineisTest`; R `test_periodo_restringe_…` | Atendido |
| 2.8.1.1.6 | Índice de disponibilidade | idem e `/portal` | idem e `/api/portal/visao-geral/` | R `test_operacional_do_cliente_a`, `test_ausencia_…` | **Novo no operacional**, proxy (§4) |
| 2.8.1.2.1 | KPIs operacionais | `/dashboard` (Executivo) | `GET /api/dashboard/executivo/` (só interno) | R `test_executivo_do_cliente_a` | Atendido |
| 2.8.1.2.2 | Custos de manutenção | idem | idem | R `test_executivo_…`, `test_ausencia_…`, `test_financeiro_…` | Corrigido: a "economia" (estimado − real) era fórmula inventada (§3) |
| 2.8.1.2.3 | MTBF | idem | idem | R `test_executivo_do_cliente_a` | Atendido, proxy (§4) |
| 2.8.1.2.4 | MTTR | idem | idem | idem | Atendido |
| 2.8.1.2.5 | Performance por unidade | idem | idem | idem | Atendido (unidade = cliente) |
| 2.8.1.2.6 | Evolução histórica | idem | idem | idem | Atendido |
| 2.8.1.3.1 | Gráficos interativos | `/dashboard` | — | — | Parcial: barras com dica; sem drill-down/zoom |
| 2.8.1.3.2 | Filtros avançados | `/dashboard` (período), cliente ativo | `?cliente=&data_inicio=&data_fim=&area=&setor=&equipamento=` | R `FiltrosNoServidor.*`, `test_recorte_de_parque`; D `RecorteDoPainel` | Atendido no servidor; a tela ainda não expõe área/setor/equipamento |
| 2.8.1.3.3 | Exportação Excel/PDF | botões no `/dashboard` | `GET /api/relatorios/painel-operacional/`, `/painel-executivo/` | R `test_tela_e_exportacao_saem_da_mesma_conta`, `test_json_csv_e_xlsx_…` | **Novo** |
| 2.8.1.3.4 | Indicadores em tempo real | `/dashboard` | — | — | Recalculado a cada abertura da tela; sem atualização automática |
| 2.9.1.1–7 | Os 7 relatórios | `/relatorios`, `/portal/relatorios` | `GET /api/relatorios/{tecnico,gerencial,equipamento,falhas,financeiro,produtividade,historico}/` | R `FiltrosNoServidor.*`, `ExportacaoEPaginacao.*`, `Isolamento.*` | Atendido; financeiro e produtividade só interno |
| 2.9.2.1–3 | PDF, Excel, CSV | botões da prévia | `?formato=pdf|xlsx|csv` | R `test_json_csv_e_xlsx_trazem_as_mesmas_linhas`, `test_pdf_carrega_o_conteudo_do_escopo`, `test_texto_que_parece_formula_e_neutralizado` | Atendido |

## 2. Fórmulas e regras de cálculo

Convenções:
- **`None` / "—"** significa sem base de cálculo no recorte. **`0`** significa medido e deu zero. Nunca convertemos um no outro.
- **Período** (`data_inicio`/`data_fim`, inclusivo) vale para volumes. As datas usadas: inspeção pela `data`; medição pela data **da inspeção**; OSP pela abertura (`criado_em`, fuso America/Sao_Paulo); laudo pela `data_emissao`.
- **Retrato do momento**: OSPs abertas, SLA vencido e inspeções em aberto ignoram o período, mas respeitam cliente e parque.
- **OSP cancelada** fica fora de toda conta, exceto `osps_canceladas` e `osps_por_status`.
- **Equipamento** conta só se estiver ativo e é agregado por id. A TAG se repete entre clientes.

| Indicador | Fórmula | Unidade |
|---|---|---|
| Inspeções no período | inspeções ativas com `data` no período | qtd |
| Medições por classificação | vibração + termografia + técnicas; `''` → PENDENTE | qtd |
| Equipamentos críticos | equipamentos ativos com ≥ 1 medição CRÍTICO no período, ordenados por nº de ocorrências | qtd |
| Disponibilidade (**proxy**) | (ativos − ativos com medição crítica) / ativos × 100; `None` sem ativos | % (1 casa) |
| Falhas recorrentes (**proxy**) | equipamentos com ≥ 2 OSPs não canceladas abertas no período; mais o nº de OSPs com `acompanhamento = REINCIDENTE` | qtd |
| SLA de atendimento | OSPs finalizadas até `sla_data` / OSPs finalizadas com prazo (abertas no período) | % |
| OSPs com SLA vencido | abertas com `sla_data` < hoje | qtd |
| Taxa de conclusão | finalizadas / não canceladas (abertas no período) | % (inteiro) |
| MTTR | média de (`finalizada_em` − `criado_em`) das finalizadas | horas (1 casa) |
| MTBF (**proxy**) | média dos intervalos entre aberturas consecutivas de OSPs do mesmo equipamento; equipamento com uma OSP não entra | dias (1 casa) |
| Custo real / estimado | soma só dos valores informados; informa quantas OSPs ficaram sem valor | R$ |
| Retorno da preditiva | Σ (total emergencial − total preditiva) das OSPs com Avaliação de Resultados (fórmula do cliente, Seção D) | R$ |
| Evolução | 6 meses terminando no fim do período (ou hoje): medições CRÍTICO (pela data da inspeção) e OSPs não canceladas abertas no mês | qtd/mês |
| Performance por unidade | por cliente: OSPs, finalizadas, medições críticas, custo real | — |
| Relatório gerencial, % crítico | críticas / medições **classificadas** (pendentes fora do denominador) | % |

## 3. Divergências encontradas e corrigidas

1. **Paginação ignorada.** O `PageNumberPagination` padrão descarta `?page_size=`. Listas de OSP, inspeções e laudos (admin e portal) paravam em 20 itens, e as contagens calculadas na tela ficavam erradas. Agora existe a `PaginacaoPadrao`: aceita `page_size` até 500. O portal avisa quando há mais registros que a tela carrega.
2. **Escopo "fail-open" nos relatórios.** Uma conta de cliente sem `cliente_id` via **todos** os clientes. Agora usa `escopo_cliente` (falha fechada).
3. **Filtros ignorados.** Os relatórios "por equipamento" e "produtividade" não aplicavam o período. Parâmetro malformado (data inválida, `cliente=abc`) era descartado em silêncio. Agora é 400 com o motivo. Relatório que não aceita área/setor recusa o filtro em vez de ignorá-lo.
4. **"Economia da preditiva" = estimado − real**, fórmula que ninguém definiu. Foi trocada pelo retorno definido pelo cliente (emergencial − preditiva).
5. **Ausência virando zero.** Custos sem valor somavam 0. Taxa de conclusão sem OSP aparecia como 0% (vermelho). Disponibilidade sem equipamento aparecia como 100%. "% crítico" sem medição aparecia como "0%".
6. **Equipamentos críticos/em atenção** eram agregados pela TAG (que se repete entre clientes) e incluíam equipamentos desativados. Isso podia deixar a disponibilidade negativa.
7. **Textos que contradiziam o cálculo.** O MTBF dizia "entre ocorrências críticas", mas é calculado entre OSPs. A disponibilidade do portal dizia "na última coleta", mas usa o histórico. O alerta afirmava que todo equipamento crítico "já tem OS aberta".
8. **OSP cancelada** contava em totais, laudo e Seção B (corrigido na entrega do item 2.6).
9. **Laudos do fluxo novo** (`relatorio_origem`) não entravam na contagem nem no histórico do portal.
10. **Produtividade** contava só vibração e termografia e todos os laudos (inclusive rascunho). Agora conta os 3 tipos de medição e só laudos emitidos no período.
11. **Exportação.** Números saíam como texto no Excel. Texto começando com `=`, `+`, `-`, `@` (diagnóstico, TAG) virava fórmula na planilha (injeção de fórmula). Agora os números são tipados e esse texto é neutralizado com apóstrofo.
12. **N+1.** O relatório por equipamento fazia 6 consultas por equipamento. Agora usa consultas agrupadas. A prévia JSON é paginada (100 por página, máx. 500); o arquivo exportado leva todas as linhas.

## 4. Pendências de negócio (decisões do cliente)

1. **Índice de disponibilidade.** O que existe é um proxy de condição, não disponibilidade de produção. Para o índice real, o cliente precisa definir horas de parada/operação e a fonte desse dado.
2. **Falhas recorrentes.** Adotei "2+ OSPs no período" mais o rótulo REINCIDENTE. Confirmar o limiar, a janela e se conta por equipamento ou por equipamento + tipo de anomalia. O catálogo `FalhaRecorrente` (2.2.1.8) não está ligado a nenhuma medição/OSP.
3. **MTBF.** "Falha" foi tomada como "OSP aberta". Confirmar se deve ser falha funcional (parada) e se conta o tempo desde a instalação.
4. **MTTR.** Hoje vai da abertura da OSP à finalização (inclui a espera do cliente). Confirmar se deve ser da execução (`executado_em`) à finalização, ou só o tempo de reparo.
5. **Custos.** `custo_estimado` não tem dono definido (`docs/03`). O cliente deve ver custos? Hoje o relatório financeiro e o painel executivo são só da equipe interna.
6. **Estado do equipamento no portal.** O `estado_equipamentos` mostra a **pior** classificação do histórico, não a da última coleta. Confirmar qual o cliente espera.
7. **Escopo por unidade/setor.** O usuário do cliente é limitado só pela empresa. Não existe restrição por área/setor (pergunta aberta em `docs/03`, item 5). Os filtros de área/setor/equipamento existem no servidor, mas são recorte de visão, não permissão.
8. **"Tempo real".** Hoje o sino consulta a cada 60 s e o painel recalcula a cada abertura. Se o contrato exigir push (WebSocket/SSE), é trabalho adicional.
9. **Período padrão dos painéis.** Sem período informado, os painéis mostram todo o histórico. Confirmar se o padrão deve ser mês corrente, 12 meses etc.
10. **Unidade = cliente.** "Performance por unidade" compara clientes (tomadores). Se "unidade" for área/planta dentro do cliente, o agrupamento muda.

## 5. Limites desta verificação

- Suíte do backend: **528 testes OK** (3 pulados: os que exigem PostgreSQL).
- Front: `tsc --noEmit` sem erros. O ESLint do Next não está configurado no projeto, então não rodou. **Nenhuma tela foi aberta em navegador nem em celular.** O portal usa o shell com menu em gaveta (`lg:hidden`) e o `DataTable` com modo mobile. A verificação em dispositivo fica pendente.
- O PDF é conferido pelo texto extraído dos fluxos do ReportLab. O layout visual não foi validado.
- A tela de painéis tem filtro de período e exportação. Os filtros de área/setor/equipamento estão só na API e nos testes.
