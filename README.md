# ThermoProActive — Sistema Web de Manutenção Preditiva

Plataforma de gestão de manutenção preditiva (inspeções técnicas, coleta de dados,
análise preditiva, laudos, ordens de serviço e portal do cliente), desenvolvida conforme o
**Contrato Guerra IT × Thermoproactive Serviços Ltda** e seu **Anexo I — Escopo Funcional**.

> **Stack:** Django 5 + DRF + PostgreSQL (backend) · Next.js 15 + React + TypeScript +
> Tailwind (frontend). 100% open-source, sem lock-in (Cláusula 12.4).

## O que já está implementado

| Módulo (Anexo I) | Entregue |
|---|---|
| 2.1 Login e Controle de Acesso (7 perfis, **JWT**) | ✅ |
| 2.2 Cadastros — principais + **catálogos** (normas, tipos, criticidade, grupos) + **rotas** | ✅ completo |
| 2.3 Coleta — **10 de 10 categorias** (vibração ISO, termografia ΔT, fluidos, ensaios elétricos, ultrassom, espessura, qualidade de energia, sensitiva, corretiva) | ✅ |
| 2.4 Análise Preditiva — motor de regras por tipo + tendência | ✅ |
| 2.5 Laudos Técnicos — geração automática consolidada, emissão, impressão/PDF | ✅ |
| 2.6 **OSP** — geração automática a partir de medição crítica + SLA + fluxo de status | ✅ |
| 2.7 Portal do Cliente — **home dedicada** (`/portal`): dashboard personalizado, índice de disponibilidade, histórico de serviços; escopo por cliente, somente leitura | ✅ |
| 2.8 Dashboards/BI — **Operacional + Executivo** (MTBF, MTTR, custos, evolução histórica, performance por unidade) | ✅ |
| 2.10 **Notificações** — 4 canais (e-mail/WhatsApp/push/interno) + 5 eventos automáticos | ✅ |
| 2.9 **Relatórios** — 7 relatórios (técnico/gerencial/equipamento/falhas/financeiro/produtividade/histórico) + export **PDF/Excel/CSV** | ✅ |

Detalhes em [`docs/00-ARQUITETURA.md`](docs/00-ARQUITETURA.md),
[`docs/01-DISCOVERY-modulos-tecnicos.md`](docs/01-DISCOVERY-modulos-tecnicos.md) e
[`docs/02-modelo-de-prompts.md`](docs/02-modelo-de-prompts.md).

## Como rodar

### Opção A — Docker (recomendado, sobe tudo com 1 comando)
Pré-requisito: Docker Desktop. Na raiz do projeto:
```bash
docker compose up --build
```
Isso sobe **PostgreSQL + API + Frontend**, aplica migrations e semeia os dados de demonstração
automaticamente. Quando aparecer `Listening at: http://0.0.0.0:8000`, acesse:
- Frontend: http://localhost:3000
- API / Swagger: http://localhost:8000/api/ · http://localhost:8000/api/docs/
- Admin Django: http://localhost:8000/admin/

Comandos úteis:
```bash
docker compose up -d        # sobe em segundo plano
docker compose logs -f      # acompanha os logs
docker compose down         # para tudo (use 'down -v' para apagar o banco)
```

### Opção B — Local (sem Docker)

#### 1. Backend (API) — porta 8000
```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  Linux/Mac:  source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # cria dados + usuários de demonstração
python manage.py runserver
```
Sem `.env`, o backend usa **SQLite** (zero configuração). Para PostgreSQL, copie
`backend/.env.example` para `backend/.env` e defina `DATABASE_URL` (suba o banco com
`docker compose -f backend/docker-compose.yml up -d`).

- API: http://127.0.0.1:8000/api/
- Documentação (Swagger): http://127.0.0.1:8000/api/docs/
- Admin Django: http://127.0.0.1:8000/admin/

#### 2. Frontend (Web) — porta 3000
```bash
cd frontend
npm install
cp .env.local.example .env.local    # NEXT_PUBLIC_API_URL aponta para a API
npm run dev
```
Acesse http://localhost:3000

### Usuários de demonstração (senha: `thermo123`)
| E-mail | Perfil |
|---|---|
| admin@thermoproactive.com | Administrador |
| tecnico@thermoproactive.com | Técnico/Analista (assina laudos) |
| cliente@exemplo.com | Cliente — PCM (portal, somente leitura) |

## Fluxo de demonstração (ponta a ponta)
1. Login como **técnico** → **Dashboard** mostra indicadores (medições críticas e OSPs abertas).
2. **Inspeções** → abra a inspeção semente (Casa de Bombas / BBA-101).
3. Registre uma **medição de vibração** → o sistema calcula **zona ISO + criticidade +
   diagnóstico** automaticamente (ex.: 9,40 mm/s numa máquina Classe II → **Crítico**).
   Há também uma inspeção de **Termografia** (ΔT) com classificação por NBR 15572 / NETA.
4. Toda medição **Crítica** gera automaticamente uma **OSP** (menu *Ordens de Serviço*),
   com prioridade e SLA — avance o status pelo fluxo (Aberta → … → Finalizada).
5. Clique **Gerar laudo** → consolida diagnóstico e recomendações → **Emitir** → **Imprimir/PDF**.
6. **Notificações** → o sino no menu mostra eventos automáticos (equipamento crítico,
   nova OSP, laudo concluído, aprovação pendente). Em dev, os e-mails são impressos no
   log do backend (`docker compose logs backend`).
7. **Cadastros** (perfil interno) → gerencie normas, tipos e criticidades.
8. Login como **cliente@exemplo.com** → cai na **home do Portal** (`/portal`): saudação,
   indicadores do próprio parque (disponibilidade, equipamentos em atenção, OSPs abertas,
   laudos disponíveis), **histórico de serviços** e acesso rápido. Vê apenas os dados do
   próprio cliente, laudos **emitidos**, suas OSPs e notificações (não consegue criar
   inspeções — HTTP 403).

> **SLA vencendo (2.10.2.4):** agende o comando para rodar diariamente (cron):
> `docker compose exec backend python manage.py verificar_slas --dias 2`

## Estrutura
```
backend/   API Django + DRF (apps modulares: core, accounts, cadastros, coletas, laudos)
frontend/  App Next.js (App Router, TS, Tailwind)
docs/      Arquitetura (ADR), Discovery dos módulos técnicos, modelo de prompts
```

## Conformidade contratual (Cláusula 12.4 — anti-lock-in)
Todas as dependências são open-source com licenças permissivas; o SGBD é selecionado por
`DATABASE_URL` (PostgreSQL/SQLite) sem acoplamento; o deploy roda em qualquer VPS Linux com
Docker/gunicorn. A CONTRATANTE pode hospedar, modificar e contratar terceiros sem
autorização prévia (Cláusulas 12.2 e 12.3).
