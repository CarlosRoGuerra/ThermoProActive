# Reconstrução da experiência front-end — ThermoProActive

> Escrito para: quem vai manter e continuar este front-end.
> Referência: Contrato Guerra IT × Thermoproactive e **Anexo I — Escopo Funcional**.

Este documento registra **o que mudou, por quê, e o que ficou de fora**. Não é um
plano: descreve o estado atual do código.

---

## 1. Diagnóstico — o que estava realmente errado

A interface anterior não era um "template genérico": já tinha tokens CSS, tema
claro/escuro, `framer-motion` respeitando `prefers-reduced-motion`, skeletons e
sidebar responsiva. O problema não era pintura. Era estrutura.

| # | Problema encontrado | Natureza |
|---|---|---|
| 1 | **Vazamento multi-tenant no backend**: `apps/cadastros` não filtrava por cliente. Um usuário do Portal listava `/api/equipamentos/` e `/api/clientes/` e recebia o parque, o CNPJ e os contatos de **todos** os clientes da base. | Segurança |
| 2 | Portais não separados: um único shell servia equipe e cliente. Cliente que digitava `/clientes` ou `/cadastros` abria tela que chama API administrativa → 403 silencioso, tela vazia. | Arquitetura |
| 3 | Nenhum *route guard*. O RBAC existia só como "esconder botão". | Segurança / UX |
| 4 | `/api/usuarios/` (CRUD completo, restrito a Master) **sem nenhuma tela**. Conceder acesso só era possível pelo admin do Django. | Funcionalidade faltante |
| 5 | `pageWindow()` (paginação) duplicado em 4 arquivos; busca, ordenação e exclusão reescritas em cada listagem. | Dívida técnica |
| 6 | `.then(setData).finally(...)` sem `catch`: falha de rede deixava a tela **eternamente vazia sem explicar nada**. | UX |
| 7 | `window.confirm()` em 10 lugares e `alert()` em 1: não dizem *o que* será apagado, não seguem o tema, travam a aba. | UX |
| 8 | Login com **credenciais de demonstração escritas na página** e senha pré-preenchida no código. | Segurança |
| 9 | Nenhum arquivo de logo (`public/` vazio); a marca era um quadrado com a letra "T". | Identidade |
| 10 | Sem Modal, Tabs, Tooltip, Dropdown, Breadcrumb, Alert, Toast, ErrorState, DataTable, Switch, Checkbox. | Design System incompleto |
| 11 | Dashboards com números sem referência ("Medições: 1.847"). | Produto |
| 12 | Sem onboarding, sem trilha de navegação, sem estado de erro nem de permissão. | UX |
| 13 | `page_size=1000` em 38 chamadas: baixa tudo e filtra no navegador. | Performance |

---

## 2. Correção de segurança no backend (obrigatória)

`apps/cadastros/views.py` — `BaseCadastroViewSet` ganhou `campo_cliente`:

```python
class BaseCadastroViewSet(viewsets.ModelViewSet):
    campo_cliente = None          # None = tabela de referência global

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.campo_cliente and getattr(user, "is_cliente", False):
            if not user.cliente_id:
                return qs.none()  # falha fechada
            return qs.filter(**{self.campo_cliente: user.cliente_id})
        return qs
```

Escopo declarado em cada ViewSet de dado de cliente:

| ViewSet | `campo_cliente` |
|---|---|
| `ClienteViewSet` | `id` |
| `AreaViewSet` | `cliente` |
| `SetorViewSet` | `area__cliente` |
| `EquipamentoViewSet` | `setor__area__cliente` |
| `ComponenteViewSet` | `equipamento__setor__area__cliente` |
| `DadosTecnicosMotor/Transformador` | `equipamento__setor__area__cliente` |
| `RotaViewSet` | `cliente` |

Catálogos globais (normas, tipos, criticidades, instrumentação) seguem visíveis a
qualquer autenticado — é o comportamento correto: são tabelas de referência.

**Regressão coberta por teste:** `apps/cadastros/test_escopo_cliente.py` (9 casos)
— cliente vê só a própria empresa, não acessa equipamento de outro por id
(404), cliente sem vínculo não vê nada, interno continua vendo tudo, catálogo
global permanece visível, cliente não escreve (403).

Verificado também em execução, com o `seed_demo`:

```
usuário cliente  → clientes: 1   equipamentos: 1
usuário interno  → clientes: 2   equipamentos: 4
```

### Campo aditivo no endpoint do portal

`PortalVisaoGeralView` passou a devolver `estado_equipamentos`:

```json
"estado_equipamentos": {
  "BBA-101": { "criticidade": "CRITICO", "medicoes": 6, "ultima_medicao": "2026-09-18T05:17:50Z" }
}
```

Motivo: a lista de equipamentos do Portal precisa dizer **como está** cada
máquina. Sem isso a tela teria de inventar um estado — ou mostrar "Normal" para
equipamento nunca medido, o que é falso. A pior criticidade é resolvida em
Python porque `Max()` num `CharField` ordenaria alfabeticamente e "NORMAL"
venceria "CRITICO". Nenhum campo existente mudou de forma.

---

## 3. Separação dos portais

Route groups do App Router, **sem mudar nenhuma URL interna**:

```
src/app/
├── (admin)/           → equipe interna. URLs na raiz: /dashboard, /clientes, …
│   └── layout.tsx     → RouteGuard area="admin" + AppShell + ClienteSwitcher
├── portal/            → cliente. URLs sob /portal/*
│   └── layout.tsx     → RouteGuard area="portal" + AppShell
├── login/  carta/  imprimir/   → fora dos shells (auth e documentos)
└── error.tsx  not-found.tsx    → anteparos globais
```

### Portal do Cliente (novo, 9 telas)

| Rota | Responde a |
|---|---|
| `/portal` | "O que está acontecendo com a minha operação?" + primeiros passos |
| `/portal/equipamentos` | "Como está cada máquina minha?" |
| `/portal/inspecoes` `[id]` | "O que foi medido, quando, com que resultado?" |
| `/portal/ordens-servico` | "O que precisa de intervenção e até quando?" |
| `/portal/laudos` `[id]` `[id]/relatorio` | "Onde está o documento assinado?" |
| `/portal/relatorios` | "Como levo isso para a reunião?" |
| `/portal/alertas` | "O que exige decisão minha?" |
| `/portal/ajuda` | "Como uso este portal?" |
| `/portal/perfil` | "Quem eu sou no sistema?" |

Telas compartilhadas viraram **features**, usadas pelos dois portais com props
diferentes — o documento é o mesmo, só as ações mudam:

```
src/features/
├── laudos/{laudo-documento,lista-laudos,relatorio-tecnico,graficos}.tsx
├── alertas/lista-alertas.tsx
├── relatorios/painel-relatorios.tsx
├── relatorio-inspecao/dossie.tsx      (movido de dentro de uma rota)
├── perfil/meu-perfil.tsx
├── portal/onboarding.tsx
├── usuarios/formulario-usuario.tsx
├── cadastros/{catalogos.ts,formulario-catalogo.tsx}
└── clientes/exige-cliente-ativo.tsx
```

### Links antigos continuam funcionando

Um cliente que abre `/laudos/12` (favorito, e-mail antigo) é levado a
`/portal/laudos/12`, com o `:id` preservado — ver `destinoNoPortal()` em
`src/lib/permissions.ts`. Não é erro na cara do usuário: é tradução de rota.

---

## 4. RBAC de verdade

`src/lib/permissions.ts` é o espelho da matriz do backend
(`apps/accounts/permissions.py`), com 20 habilidades declaradas
(`usuarios:gerenciar`, `dados-sistema:curar`, `laudos:assinar`, …).

```ts
can(user, "laudos:assinar")   // exige conselho de classe (Anexo I 3.1.2)
podeAcessarRota(user, "/cadastros")
rotaInicial(user)             // cliente → /portal · interno → /dashboard
```

**Isto é navegação, não segurança.** A autorização real continua no DRF. O
guarda existe para (a) ninguém chegar a uma tela que só saberia devolver 403 e
(b) o menu montar apenas o que a pessoa pode.

Três desfechos:

1. sem sessão → `/login?proximo=<rota>` (volta ao destino depois de entrar);
2. área errada → redireciona ao portal correto, traduzindo a rota;
3. rota certa, nível insuficiente → `PermissionDenied` **explicando o que falta**,
   com o menu e a saída no lugar.

Menu, ações e itens de menu contextual derivam das mesmas habilidades. Ação
indisponível por nível fica desabilitada **com o motivo no `title`** — em vez de
desaparecer e deixar a pessoa sem entender.

---

## 5. Design System

`src/components/ds/` — 12 arquivos, um `index.ts` como porta única.
`src/components/ui.tsx` (a biblioteca antiga) foi apagado: **zero** imports
restantes.

### Tokens (`src/app/globals.css` + `tailwind.config.ts`)

Regras da casa, escritas no próprio arquivo:

1. Componente nunca escreve cor literal. Só token.
2. Cor de **marca** (`primary`) é separada de cor de **estado**
   (`success/warning/danger/info`). Num produto de monitoramento, confundir os
   dois é erro de leitura.
3. **Chrome** (sidebar/topbar) tem tokens próprios: aço escuro nos dois temas.
   Separa navegação de conteúdo e dá cara de software de operação, em vez de
   painel administrativo comprado pronto.
4. Todo estado é comunicado por ícone + texto + forma, nunca só por cor.

O accent indigo genérico deu lugar a um **azure calibrado** (`#1257c2` claro /
`#4a90f7` escuro), distinto do esmeralda (ok), do âmbar (atenção) e do vermelho
(crítico) — para não competir com a semântica de estado. Os aliases `--accent-*`
continuam apontando para `--primary-*`, então nada que não foi migrado quebrou.

Escalas completas: tipografia (com `line-height` e `tracking` amarrados ao
tamanho), espaçamento, raio, sombra, **z-index nomeado** (`z-modal`, `z-toast` —
fim do `z-[9999]`), breakpoints incluindo `xs: 375px`, animações e durações.

### Componentes

`Button` `IconButton` `ButtonGroup` · `Field` `Input` `Textarea` `Select`
`SearchInput` `Checkbox` `Switch` `RadioGroup` `FormSection` `FormGrid`
`FormActions` · `Badge` `EstadoBadge` `EstadoPonto` `LegendaEstados`
`StatusBadge` `PriorityBadge` `ClasseAtivoBadge` `SemDado` `DicaSelo` ·
`Card` `CardHeader` `CardSection` `MetricCard` `DescriptionList` ·
`PageHeader` `SectionHeader` `Breadcrumb` `Toolbar` `PageBody` `MetricGrid`
`SplitLayout` · `Alert` `Spinner` `Skeleton` `LoadingState` `TableSkeleton`
`EmptyState` `ErrorState` `ErrorCard` `PermissionDenied` `OfflineBanner`
`Resultado` · `Modal` `Drawer` `ConfirmDialog` `DropdownMenu` `Tooltip` ·
`ToastProvider` `useToast` · `Tabs` `TabsLink` `SegmentedControl` ·
`Table` `Pagination` `DataTable` · `Logo` `Simbolo` · `Avatar` `ThemeToggle`
`BarMeter` `ProgressBar` `Timeline`.

Destaques de contrato:

- **`Field`** faz a amarração de acessibilidade sozinho: `label`↔controle,
  `aria-describedby` (ajuda + erro), `aria-invalid`, `aria-required`. Nenhuma
  tela precisa lembrar — e nenhuma esquece.
- **`IconButton`** exige `label`. Ícone solto sem nome acessível não compila.
- **`DataTable`** resolve busca, ordenação, paginação, estados e ações em menu.
  Abaixo de `md` **deixa de ser tabela** e vira lista de fichas, usando as
  colunas marcadas como `titulo`/`subtitulo`/`meta`. Não é `overflow-x` como
  única resposta mobile.
- **`ConfirmDialog`** substitui `window.confirm()`: diz o nome do registro, avisa
  quando a ação não tem volta, mostra o progresso do envio, prende o foco.
- **`MetricCard`** aceita `contexto` e `dica`. "Total: 321" não passa: o número
  declara em relação a quê existe.

### Marca

A marca oficial (`logotipoPredAtivos.png`, na raiz do repositório) foi instalada
em 18/09/2026, substituindo o símbolo provisório.

**Arranjo:** o SÍMBOLO (engrenagem + setas) entra como imagem; o NOME
("ThermoProActive") continua **texto HTML**. Decisão do cliente: o logotipo traz
o wordmark "PRED ATIVOS", mas o nome escrito na interface permanece
ThermoProActive. Vantagens de manter o nome em texto: acompanha o tema
claro/escuro e a sidebar escura sem precisar de três variantes de arquivo, é
selecionável, e o leitor de tela lê o nome do produto em vez de "imagem".

Derivados gerados a partir do PNG original, todos em `frontend/public/`:

| Arquivo | Tamanho | Onde é usado |
|---|---|---|
| `brand/mark.png` | 112² | Interface: sidebar, login, avisos de carregamento |
| `brand/logo.png` | 309×406 | Lockup vertical completo (documentos, impressão) |
| `brand/logo-horizontal.png` | 386×160 | Lockup horizontal (cabeçalhos baixos) |
| `favicon.ico` | 16+32+48 | Aba do navegador, atalho do Windows |
| `favicon-16x16.png` `favicon-32x32.png` | 16², 32² | Navegadores que procuram pelo nome |
| `icon-256.png` | 256² | Favicon moderno em alta resolução |
| `apple-touch-icon.png` | 180² | "Adicionar à tela de início" no iOS |
| `brand/icon-192.png` `brand/icon-512.png` | 192², 512² | PWA / Android (manifesto) |
| `brand/icon-maskable-512.png` | 512² | Android adaptativo (22% de folga) |
| `brand/mstile-150.png` | 150² | Azulejo do Windows |
| `site.webmanifest` | — | Instalação como aplicativo |

Decisões que valem registro:

- **Ícones de toque recebem fundo branco.** Transparência vira preto no iOS e
  cinza no Android, e a marca é escura.
- **O maskable tem 22% de folga.** Sem isso o recorte circular do Android come
  as pontas da engrenagem.
- **`mark.png` tem 112 px, não 512.** O maior uso na tela é 56 px; 112 cobre
  telas 2x. Na primeira geração o arquivo saiu com 512 px / 255 KB e viajava em
  toda navegação — agora são 22 KB.
- **Os ícones são declarados por inteiro em `metadata.icons`, com os arquivos em
  `public/`.** Declarar `metadata.icons` SUPRIME a convenção `app/icon.png` do
  App Router; no primeiro passe isso derrubou silenciosamente o ícone do iOS.
  Com tudo explícito, o que está no código é o que sai no HTML.
- **Não há `mask-icon` (pinned tab do Safari).** Ele exige SVG vetorial de uma
  cor só; a marca recebida é raster. Um PNG ali simplesmente não funciona, e uma
  aproximação desenhada à mão distorceria a marca. Para fazer certo é preciso o
  arquivo vetorial original (.ai/.svg/.eps).
- **A paleta não mudou.** O azul-marinho `#0B385F` e o laranja `#F0582F` da
  marca ficaram fora dos tokens por decisão do cliente: o azure `#1257C2` já
  está validado em WCAG AA nos 21 pares de cor. Registrado também que o laranja
  da marca não deve virar token de estado — ele fica perto do vermelho de
  "crítico" e do âmbar de "alerta".

**Trocar a marca:** substituir os arquivos em `public/brand/` e regerar os
derivados. Nenhuma tela precisa ser editada; se `mark.png` sumir, o `Logo` cai
num desenho embutido e nada quebra.

**Pendência:** a capa do Relatório Técnico e o timbrado usam
`Empresa.logomarca` — um campo de DADO, preenchido pela tela de Prestadores, e
que está vazio. Enquanto não for enviado por lá, o relatório sai sem a marca
lateral da capa.

---

## 6. Camada de dados

| Arquivo | Papel |
|---|---|
| `lib/api.ts` | `AbortSignal`, erro de conexão como `ApiError(0)`, **refresh single-flight** |
| `lib/recurso.ts` | `useRecurso` / `useLista` / `useMutacao` |
| `lib/erros.ts` | traduz falha técnica → frase que o usuário entende |
| `lib/format.ts` | datas, números, moeda, CNPJ/CPF/telefone, `plural`, comparador pt-BR |
| `lib/permissions.ts` | RBAC + guarda de rota + tradução de rota |
| `lib/nav.ts` | navegação declarativa dos dois portais + trilha |
| `lib/alertas.ts` | contador de não lidos: pausa em aba oculta, desiste após 3 falhas |

O refresh *single-flight* corrigiu um bug real: várias telas carregando em
paralelo podiam receber 401 ao mesmo tempo, cada uma disparava
`POST /auth/refresh/`, e o `simplejwt` com rotação invalidava o refresh das
demais — derrubando a sessão do usuário.

`useRecurso` fechou o buraco do item 6 do diagnóstico em um lugar só: cancela
no desmonte, traduz a falha e expõe `recarregar()` para o botão "Tentar
novamente".

O usuário **nunca** lê "Erro 500", "resource" ou stack trace. O detalhe técnico
vai para o console via `registrarFalha()` — ponto único caso o projeto passe a
enviar erros para telemetria.

---

## 7. Onboarding do cliente

Não é tour guiado (ninguém completa). É um cartão de orientação em `/portal` que:

- diz onde a pessoa está e o que o portal responde;
- lista as 4 coisas que ela precisa saber achar, com link direto;
- **marca sozinho o que ela já visitou** (`useRegistrarVisita` nas páginas);
- ensina a escala de estados — o vocabulário do produto — de uma vez;
- desaparece quando o checklist termina, e reabre em "Como usar o portal".

Os estados vazios do portal também ensinam: além do título e da explicação,
trazem `comoFunciona` — os 3 passos de como aquele dado chega ali.

---

## 8. Semântica de monitoramento

Escala única, em `ds/badge.tsx`:

| Grau | Rótulo | Ícone (forma) | Origem |
|---|---|---|---|
| `NORMAL` | Normal | círculo ✓ | `Criticidade` do backend |
| `ATENCAO` | Atenção | círculo ! | derivado na interface |
| `ALERTA` | Alerta | **triângulo** ! | `Criticidade` do backend |
| `CRITICO` | Crítico | **octógono** ! | `Criticidade` do backend |
| `OFFLINE` | Sem comunicação | wifi cortado | **reservado** (ver abaixo) |
| `SEM_DADOS` | Sem medição | círculo − | ausência de medição |

A forma muda de propósito conforme a gravidade sobe — círculo → triângulo →
octógono, como a sinalização viária. Funciona em monocromático, impresso e para
quem não distingue vermelho de verde.

**`OFFLINE` está definido mas nenhuma tela o usa.** Ele existe para a coleta
automática por sensor/IoT prevista no Anexo I 2.3.1.5. Este sistema faz inspeção
por rota, com técnico e instrumento calibrado: equipamento não fica "online". Usar
o grau agora seria inventar dado.

---

## 9. Acessibilidade

Meta: **WCAG 2.2 AA**.

- **Contraste — verificado por cálculo, não por impressão.** Os 21 pares de cor
  que a interface usa passam nos dois temas. Menores margens: texto auxiliar
  3,32:1 (mínimo 3,0 para texto grande/secundário) e selos de estado ≥ 5,1:1.
- Foco visível com `outline` de 2px + offset, nunca removido.
- `Modal`/`Drawer`/`ConfirmDialog`: `role="dialog"`, `aria-modal`, Esc fecha,
  foco aprisionado e **devolvido a quem abriu**, fundo sem rolagem (sem deslocar
  o layout).
- `Tabs` com padrão ARIA completo (←/→, Home/End, só a aba ativa tabulável).
- Tabelas com `<caption>` oculta e `aria-sort` nas colunas ordenáveis.
- Landmarks (`banner`/`navigation`/`main`), um `<h1>` por página, skip-link.
- Toast em região `aria-live="polite"`; erro não desaparece sozinho.
- `maximumScale: 5` — a interface é operada em campo, no celular: o zoom
  continua disponível.
- **Nenhum botão só-ícone sem nome acessível** (verificado por varredura).

---

## 10. Responsividade

Verificada de 320px a 1920px. Decisões:

- Sidebar: trilho de ícones (68px) que expande no hover, ou fixada (256px) com
  preferência salva. No celular não existe: vira Drawer.
- Tabelas: fichas abaixo de `md`, com título/subtítulo/meta declarados por coluna.
- `FormActions` gruda no rodapé no celular — o usuário não rola até o fim para
  achar "Salvar".
- Toast: topo no celular (onde o polegar não cobre e não briga com a barra de
  ações), canto inferior direito no desktop.
- Indicadores: 2 colunas no celular, 4 no desktop, nunca mais de 5 por faixa.

---

## 10.1 Documentos: revertidos e isolados

Os documentos entregues ao cliente (Relatório Técnico e dossiê de inspeção) têm
layout **aprovado** e foram devolvidos ao conteúdo original em 18/09/2026, a
pedido. Três arquivos são hoje byte a byte idênticos ao que estava versionado:

| Arquivo | Estado |
|---|---|
| `(admin)/laudos/[id]/relatorio/page.tsx` | idêntico ao original |
| `(admin)/laudos/[id]/relatorio/graficos.tsx` | idêntico ao original |
| `features/relatorio-inspecao/dossie.tsx` | idêntico ao original (só mudou de pasta) |

Para que isso compile sem editar os arquivos, voltaram dois apoios de
compatibilidade, ambos documentados no próprio código: `src/components/ui.tsx`
(reexporta o Design System com os mesmos nomes) e os tokens `--accent-*`
(apelidos de `primary`, mesma cor).

### O que realmente havia mudado no documento

Nada na marcação. O que alterou a diagramação foram decisões **globais** da
interface que vazaram para dentro do papel, porque o documento usa as mesmas
classes utilitárias:

| Classe | Original | Escala do painel | Efeito |
|---|---|---|---|
| `text-sm` | 14px | 13px | títulos de seção e rótulos menores |
| `text-lg` | 18px | 17px | valores de KPI da Seção B menores |
| `text-xs` | altura 16px | 18px | entrelinha maior |
| `text-2xl` | sem tracking | `-0.018em` | números mais apertados |
| `rounded` | 4px | 6px | cantos das caixas |
| `h1`–`h4` | quebra normal | `text-wrap: balance` | **quebra de linha diferente** |

### A proteção que ficou

Em vez de desfazer a escala do painel (35 telas a usam), os escopos de documento
— `.doc`/`.folha`, `.print-area`/`.pagina` e `.carta-doc` — passaram a **fixar os
valores originais do Tailwind** em `globals.css`.

Consequência: mexer na tipografia, no raio ou na quebra de títulos da interface
**deixa de alcançar o papel**. Para mudar o documento, edita-se o documento.

Custo assumido na reversão: o Relatório Técnico completo voltou a existir só na
área interna (`/laudos/:id/relatorio`). A rota `/portal/laudos/:id/relatorio`
saiu junto. O cliente continua abrindo o laudo e imprimindo em PDF pelo portal;
se quiser o relatório completo lá de novo, é reintroduzir a rota apontando para
a mesma página.

---

## 11. O que ficou de fora — e por quê

Honestidade sobre o estado atual:

1. **Paginação no servidor.** Reduzi `page_size=1000` → `300/500` e centralizei
   a paginação no `DataTable`, mas ela ainda é **no cliente**. Para volume alto
   (dezenas de milhares de OSPs) o certo é paginar no servidor com
   `?page=&ordering=&search=` e o `DataTable` passar a receber o total de fora.
   As chamadas que continuam em 500 são catálogos de referência — tabelas
   pequenas e limitadas por `CatalogoPagination`.
2. **Tokens JWT em `localStorage`.** A API é um serviço separado e o login
   devolve o JWT no corpo; não há cookie HttpOnly para reaproveitar. O mais
   seguro é o backend passar a emitir `HttpOnly + SameSite`, o que muda o
   contrato de `/auth/login/`. Enquanto isso: só o par access/refresh é
   guardado, nada pessoal; limpeza no logout e quando o refresh falha; nenhum
   token em log, URL ou mensagem de erro.
3. **Testes automatizados de front-end.** O projeto não tem runner de testes JS.
   A verificação desta entrega foi: `tsc --noEmit` limpo, `next build` limpo,
   as 40 rotas respondendo em servidor limpo, os 109 testes do backend passando
   (incluindo os 9 novos de escopo) e a checagem de contraste por cálculo.
   Instalar Vitest + Testing Library e cobrir `permissions.ts`, `format.ts`,
   `recurso.ts` e `DataTable` é a próxima dívida a pagar.
4. **Recuperação de senha por e-mail.** A tela de login explica o caminho atual
   (falar com o administrador) porque **não existe endpoint** de reset. Criar
   `/auth/password-reset/` no backend é pré-requisito.
5. **`/inspecoes` (coleta direta) e `/inspecoes/campo` coexistem.** São dois
   caminhos de coleta de verdade — medição pontual e fluxo campo→escritório.
   Mantive os dois, com a distinção escrita na tela, porque unificá-los é decisão
   de produto, não de interface.

---

## 12. Como continuar

**Adicionar uma tela:** `PageBody` + `PageHeader` (com `trilha`) + `Toolbar` +
`DataTable`, dados por `useLista`, ações destrutivas por `useConfirmacao` +
`ConfirmDialog`, retorno por `useToast`.

**Adicionar um item de menu:** `src/lib/nav.ts`, declarando `exige`. Se a rota
precisa de guarda, acrescente a regra em `REGRAS_ROTA` (`permissions.ts`).

**Adicionar uma tabela de referência:** um objeto em
`features/cadastros/catalogos.ts`. Lista e formulário se montam sozinhos.

**Mudar a identidade visual:** `globals.css` (tokens) e os dois SVGs em
`public/brand/`. Nada de cor literal em componente.

**Se um padrão visual aparecer em duas telas, ele vira componente no DS.** Foi
assim que `pageWindow` deixou de existir em 4 cópias.
