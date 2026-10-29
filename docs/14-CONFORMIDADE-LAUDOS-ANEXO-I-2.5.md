# Conformidade de laudos — Anexo I, item 2.5

Auditoria e implementação de 22/10/2026. A referência de aceite é o requisito
fornecido pelo cliente nesta solicitação, confrontado com os modelos, serviços,
serializers, views, layouts e testes do repositório. Não foi presumida uma regra
contratual de assinatura criptográfica, retenção documental ou alçada profissional.

## Restrição expressa: manter o design dos PDFs

O PDF usa as mesmas páginas HTML, CSS, gráficos, capas, timbrados e componentes
que já existiam: `/laudos/[id]/relatorio` e `/imprimir/[id]`, esta com `paged.js`.
O renderer Chromium imprime essas páginas; não existe um layout alternativo em
ReportLab nem fallback silencioso para outro desenho. Os marcadores de conclusão
da renderização são invisíveis. Novas evidências usam folhas adicionais com o
mesmo componente de folha/timbrado; não substituem a capa ou as fichas existentes.
Textos editados ocupam os espaços de conteúdo existentes.

A emissão armazena os bytes finais. Uma atualização futura de CSS, fontes,
cadastro, imagem ou medição não refaz o PDF emitido. Impressão de uma consulta ou
do relatório de origem continua sendo uma consulta; o documento emitido é o
arquivo guardado, consultado pelo download autorizado.

## Matriz de cobertura e lacunas

| Requisito | Situação encontrada | Implementação e limite atual |
| --- | --- | --- |
| Geração automática | Inspeção direta gerava texto consolidado; dossiê de rotas tinha fluxo separado | Laudo tem exatamente uma origem: `Inspecao` ou `Relatorio` de rotas; dossiê original permanece funcional |
| Fidelidade da fonte | PDF e payload eram recalculados com dados vivos | Snapshot completo na emissão, sem filtros de prévia, identificação da origem, contexto e medições; PDF privado persistido |
| Identificação | Dados de cliente/responsável podiam mudar após emissão | Identidade e conselho congelados; cliente documental fixado no laudo; reparentear a origem não transfere o documento ao novo cliente |
| Diagnóstico/criticidade | Textos consolidados e OSPs existentes; ausência de OSP podia aparecer como normal | Texto técnico editável no rascunho; classificação pendente não vira diagnóstico definitivo; removidas referências genéricas sem critério aplicado |
| Templates | Layouts existentes, sem cadastro declarativo | Cadastro com escopo de cliente/modalidade e versão; título e rodapé em texto simples; sem HTML/código arbitrário |
| Design dos templates | Layouts aprovados e específicos por modalidade | Ordem e seções permanecem fixas; rodapé personalizado bloqueado no modular, que não tem esse espaço; fonte e geometria preservadas |
| Fotos e evidências | Fotos em achados de rotas; ausência de anexo no laudo direto | Anexos privados de imagem com autoria, legenda, MIME e hash; imagens locais incorporadas ao snapshot; arquivo ausente/corrompido bloqueia emissão |
| Gráficos/comparações | Gráficos nas páginas de relatório existentes | Reutilizados os gráficos existentes e congelados seus dados; proveniência preditiva preservada no envelope; não se inventam curvas ou prognósticos |
| PDF/impressão | Impressão do navegador sem arquivo emitido preservado | Chromium usa os layouts atuais, espera fontes/imagens/paginação; falha mantém rascunho; download retorna exatamente os bytes armazenados |
| Versões | Campo `versao` sem revisão imutável | Revisão cria novo rascunho numerado, com anterior/raiz/motivo; emissão anterior preservada; cancelamento com motivo não apaga o arquivo |
| Histórico | Atualização direta sem trilha documental dedicada | Eventos de geração, edição, anexos, emissão, revisão e cancelamento, com autor/data/hash; eventos não editáveis pela API |
| Assinatura | Campo de assinatura de usuário era imagem | Imagem é representação visual; aprovação eletrônica interna registra usuário autenticado, conselho, instante e método; assinatura digital criptográfica **não implementada** |
| Autorização | Ações genéricas podiam alterar status/conteúdo | Emissão só pelo responsável interno ativo com conselho; revisão interna; cancelamento responsável/Master; templates alterados por Master interno; portal somente documentos já emitidos do cliente |
| Escopo de unidade | Usuário é vinculado a `Cliente`, sem ACL específica por unidade | Isolamento por cliente e contexto dos equipamentos preservado; acesso independente por unidade depende de definir/cadastrar esse vínculo |
| Legado | Emitidos antigos não possuem snapshot/PDF original no banco | Migração preserva registros; download/reconstrução do legado sem base é bloqueado. Recuperar original e aprovar saneamento, sem recriar um falso original |

## Fluxo e integridade

1. Gerar rascunho a partir de uma origem; editar conteúdo, datas, responsável e
   template válido; adicionar/remover evidências com trilha.
2. Responsável autenticado aprova e emite. Serviço transacional congela dados e
   imagens, calcula SHA-256 e renderiza o PDF antes de persistir o estado emitido.
3. Repetir emissão de um documento emitido não cria novo evento, aviso ou arquivo.
4. Edição do emitido é bloqueada. Revisão com motivo cria outra versão; anexos
   privados são copiados para a revisão sem alterar os anteriores.
5. JSON congelado e download verificam seus hashes. Hash não é assinatura digital
   nem impede adulteração por um administrador com acesso completo ao banco.
6. O arquivo é um `BinaryField` privado; não há URL pública em `MEDIA_URL` para o
   PDF ou para anexos privados. Originais das fotos da coleta conservam seu fluxo
   de armazenamento existente; a versão emitida incorpora os bytes necessários.

Principais endpoints: `/api/laudos/gerar/`, `/{id}/documento/`,
`/{id}/relatorio-tecnico/`, `/{id}/anexos/`, `/{id}/emitir/`, `/{id}/revisar/`,
`/{id}/cancelar/`, `/{id}/versoes/`, `/{id}/eventos/`, `/{id}/pdf/` e
`/api/templates-laudo/`. A aprovação é parte explícita da emissão; não existe um
endpoint que alegue produzir assinatura criptográfica.

## Dependências locais e implantação

- Python/Pillow existentes; Node 22 e Playwright/Chromium 1.63.0 para imprimir o
  frontend. Nenhum serviço pago ou API externa de IA/assinatura foi introduzido.
- Desenvolvimento aproveita `frontend/node_modules/playwright` instalado por
  `npm ci`; instalar o navegador com `npx playwright install chromium` no frontend.
- `LAUDOS_FRONTEND_URL` aponta para o frontend disponível: padrão
  `http://127.0.0.1:3000`; testes usam `http://127.0.0.1:3100`. Somente loopback ou
  o serviço Docker `frontend` são aceitos. Não recebe URL do usuário.
- O subprocesso recebe o snapshot por stdin. Browser isolado sem cookies reais;
  chamadas de API são respondidas exclusivamente pelo snapshot. Recursos externos
  são bloqueados; assets do frontend local continuam disponíveis.
- Dockerfile backend inclui Node/Chromium; os três composes configuram a origem
  privada `http://frontend:3000`. Frontend precisa subir antes da primeira emissão.
  Gunicorn/nginx têm 120 s, frente ao timeout interno padrão de 90 s. Se aumentar
  o timeout do renderer, ajustar também o servidor/proxy.
- Limites operacionais configuráveis, sem valor normativo: imagem 10 MiB, total
  de imagens 40 MiB, PDF 50 MiB, 1.000 folhas lógicas e timeout 90 s. Imagens
  animadas, corrompidas ou excessivas são recusadas; não são omitidas em silêncio.
- `requirements-dev.txt` adiciona pypdf/pypdfium2 para ler/rasterizar PDFs reais nos
  testes. Esses pacotes não fazem parte da API de produção.
- Migrações novas: laudos `0003` (integridade/versões/aprovação), `0004` (anexos
  privados), `0005` (cliente documental preservado). Não aplicadas ao banco
  operacional nesta tarefa; os testes usam banco isolado.

## Arquivos alterados nesta etapa

| Grupo | Arquivos |
| --- | --- |
| Domínio/API | `backend/apps/laudos/{models,serializers,views,services,urls,admin,relatorio,estatisticas}.py` |
| Snapshot/template/render | `backend/apps/laudos/{snapshots,templates,pdf}.py`, `render-layout.cjs` |
| Migrações | `backend/apps/laudos/migrations/0003_integridade_versoes_aprovacao.py`, `0004_anexos_privados.py`, `0005_cliente_documental_preservado.py` |
| Frontend | `features/laudos/{laudo-documento,lista-laudos,editor-rascunho,editor-template,laudo-gestao}.tsx`, `features/relatorio-inspecao/dossie.tsx`, `src/lib/types.ts`, páginas de detalhe/impressão e componentes de documento existentes |
| Testes | `backend/apps/laudos/test_conformidade_documentos.py`, `test_pdf.py`, `test_pdf_layout.py`; `frontend/tests/e2e/laudos-documentais.spec.ts` |
| Configuração | `backend/config/settings.py`, `backend/.env.example`, `backend/requirements-dev.txt`, `backend/Dockerfile`, composes principal/prod/http, nginx HTTP/TLS, `.gitignore`, `README.md` |

Existem alterações anteriores de coleta, análise preditiva e do próprio usuário
na árvore de trabalho; esta lista não atribui essas alterações ao módulo 2.5.

## Evidências de verificação

Resultados finais e inspeção dos PDFs reais registrados ao concluir a integração.
Os testes de domínio usam renderer simulado para validar transações, estados e
acesso; os testes opt-in de layout usam Chromium real, sem simular o PDF.

## Validações que precisam do cliente

1. **Assinatura criptográfica:** certificado aceito, titular, cadeia de confiança,
   custódia da chave, eventual carimbo de tempo e política de verificação. Aprovação
   interna, imagem e hash não satisfazem esse mecanismo nem comprovam ICP-Brasil.
2. **Alçadas profissionais:** habilitação e conselho por modalidade, responsável
   substituto e necessidade de aprovação por segundo técnico. O cadastro de conselho
   é requisito de fluxo atual, sem validação externa da habilitação profissional.
3. **Legado e retenção:** localização dos originais, importação auditável, política
   de guarda, expurgo e tratamento de documentos já assinados fora da plataforma.
4. **Escopo por unidade:** se unidades da mesma empresa precisam de autorizações
   separadas; o modelo atual autentica o cliente, não uma ACL por unidade.
5. **Textos e critérios técnicos:** validar diagnósticos, recomendações, referências
   e critérios específicos ainda pendentes nas auditorias 2.3/2.4. Emitir documento
   não transforma uma classificação inconclusiva em diagnóstico confirmado.
6. **Templates:** homologar títulos/rodapés permitidos dentro dos espaços atuais;
   mudanças estruturais de layout exigem decisão expressa, pois o design deve permanecer.

O item 2.5 fica **parcial quanto à assinatura digital criptográfica** e às decisões
acima. Essas pendências não são apresentadas como funcionalidades concluídas.
