# ThermoProActive — Arquitetura da Solução (ADR)

> Documento de decisões de arquitetura. Referência: Contrato Guerra IT × Thermoproactive
> Serviços Ltda e **Anexo I — Escopo Funcional Completo**.

## 1. Princípios norteadores

| # | Princípio | Origem |
|---|-----------|--------|
| 1 | Stack 100% open-source, **sem mecanismo de bloqueio ou dependência tecnológica obrigatória** | Cláusula **12.4** |
| 2 | Portabilidade total: código-fonte, banco, APIs e infra transferíveis à CONTRATANTE | Cláusula 12.2 / 12.3 |
| 3 | Backend Python + Django, banco PostgreSQL, infra VPS Linux/Cloud | Cláusula 4.1 / 4.2 |
| 4 | Arquitetura **modular corporativa** | Cláusula 4.2 |
| 5 | LGPD: dados pessoais tratados com segurança, logs e backups | Cláusula 13.2 |

## 2. Decisões

### 2.1. Backend — Django 5 + Django REST Framework
- **API REST desacoplada** (DRF) em vez de monolito com templates. Permite múltiplos
  front-ends (web, futuramente mobile/IoT — item 2.3.1.5 do Anexo I) sobre a mesma API.
- **JWT** (`djangorestframework-simplejwt`) — exigido no item 2.1.1.3.
- **PostgreSQL** em produção; **SQLite** como fallback de desenvolvimento (zero-config para
  rodar local). A escolha é feita por `DATABASE_URL` — nenhum código depende do SGBD.
- Documentação automática da API via **OpenAPI/Swagger** (`drf-spectacular`).

### 2.2. Frontend — Next.js 15 + React + TypeScript + Tailwind
- A Cláusula 4.1 cita "HTML5/CSS3/JS/Bootstrap"; a Cláusula **4.2 autoriza expressamente**
  o uso de "bibliotecas, componentes e frameworks complementares". Next.js/React/Tailwind são
  open-source (MIT), sem lock-in — **compatível com a Cláusula 12.4**.
- **SSR/SSG** do Next atende tanto o **sistema** (painéis autenticados) quanto o **site
  institucional** público com SEO (Cláusula 2.2).

### 2.3. Por que isto NÃO viola a Cláusula 12.4 (anti-lock-in)
- Todas as dependências são licenças permissivas (MIT/BSD/Apache/PSF) — sem licença
  proprietária, sem SaaS obrigatório, sem chave de fornecedor.
- Banco padrão SQL (PostgreSQL), sem extensões proprietárias.
- Deploy em qualquer VPS Linux com Docker/gunicorn/nginx — sem fornecedor cloud específico.
- A CONTRATANTE pode hospedar, modificar e contratar terceiros sem autorização (Cláusula 12.3).

## 3. Estrutura de pastas

```
ThermoProActive/
├── backend/                  # API Django + DRF
│   ├── config/               # projeto Django (settings, urls, wsgi/asgi)
│   ├── apps/
│   │   ├── core/             # base abstrata (timestamps, soft-delete, auditoria)
│   │   ├── accounts/         # User customizado + 7 perfis + JWT (Anexo I 2.1)
│   │   ├── cadastros/        # locais, equipamentos + catálogos + rotas (2.2)
│   │   ├── coletas/          # inspeções + Vibração + Termografia (2.3) + dashboard (2.8) + portal (2.7)
│   │   ├── osp/              # Ordens de Serviço Preditivas + auto-geração via signals (2.6)
│   │   ├── laudos/           # laudos técnicos a partir das coletas (2.5)
│   │   ├── notificacoes/     # eventos + canais (e-mail/WhatsApp/push/interno) (2.10)
│   │   └── relatorios/       # 7 relatórios + export PDF/Excel/CSV (2.9)
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   └── docker-compose.yml    # PostgreSQL local
├── frontend/                 # Next.js (App Router) + TS + Tailwind
└── docs/                     # ADR + discovery + modelo de prompts
```

## 4. Mapa Anexo I → Implementação (estado nesta entrega)

| Anexo I | Módulo | Status |
|---------|--------|--------|
| 2.1 | Login e Controle de Acesso (7 perfis, JWT) | ✅ Implementado |
| 2.2 | Cadastros (principais + catálogos + rotas) | ✅ **Completo** — apps `cadastros` (18 entidades) |
| 2.3 | Coleta de Dados — **10 de 10 categorias** | ✅ Vibração e Termografia dedicadas; fluidos, ensaios elétricos, ultrassom, espessura, qualidade de energia, sensitiva e corretiva via `MedicaoTecnica` |
| 2.4 | Análise Preditiva (regras de criticidade) | ✅ Motores: vibração (ISO), termografia (ΔT) e técnicos (`rules_tecnicas`) |
| 2.5 | Laudos Técnicos | ✅ Geração consolidada (todos os tipos de medição) |
| 2.6 | OSP — Ordem de Serviço Preditiva | ✅ **Implementado** — geração automática + SLA + fluxo de status |
| 2.7 | Portal do Cliente | ✅ **Implementado** — home dedicada (`/portal`): dashboard personalizado, indicadores de desempenho (incl. índice de disponibilidade), histórico de serviços e acesso rápido; escopo por cliente, somente leitura |
| 2.8 | Dashboards/BI | ✅ Operacional + **Executivo** (MTBF, MTTR, custos, evolução, performance) |
| 2.10 | Notificações (4 canais, 5 eventos automáticos) | ✅ **Implementado** — app `notificacoes` |
| 2.9 | Relatórios (7 relatórios + export PDF/Excel/CSV) | ✅ **Implementado** — app `relatorios` |

## 5. Como rodar — ver `README.md` na raiz.
