# Perguntas de Validação ao Cliente (ThermoProActive)

> Lista de **decisões e premissas** assumidas na implementação que precisam de confirmação
> da ThermoProActive antes da homologação. Organizada por prioridade. Onde está escrito
> "hoje o sistema usa…", é um valor de referência de engenharia que pode ser ajustado sem
> alterar arquitetura (os limiares são parametrizáveis — Cláusula 12.4).

Legenda: 🔴 bloqueante para go-live · 🟡 importante · 🟢 refinamento.

---

## 1. Regras técnicas e limiares (impactam a correção de TODA classificação)

### 1.1 Vibração (2.3.2.1) 🔴
- Qual norma é o padrão de vocês: **ISO 10816, ISO 20816 ou NBR** específica? Os limiares por classe são os da norma ou vocês têm tabela própria?
- Hoje o sistema usa as faixas A/B/C/D por **classe I–IV** (≤15kW / 15–75kW / rígida / flexível). A **classe é cadastrada por equipamento** — está correto, ou ela varia por ponto/condição?
- Regra de tendência atual: eleva 1 nível se Vrms > **1,5×** a média das **3 últimas** coletas. Confirmam o fator e a janela?
- Guardam o **espectro FFT completo** (vetor de pontos) ou só as grandezas globais + picos? Hoje guardamos as grandezas globais.

### 1.2 Termografia (2.3.2.2) 🔴
- Classificam por **ΔT do ponto vs. ponto de referência** (similar saudável/fase equivalente) ou ΔT vs. ambiente? Hoje é **vs. referência**.
- Limiares atuais (NETA/NBR 15572): ΔT ≤ 3°C Normal · 3–15°C Alerta · > 15°C Crítico. Confirmam?

### 1.3 Ensaios Elétricos (2.3.2.4 / 2.3.2.5) 🔴
- Resistência de isolação: hoje **< 100 MΩ = Crítico**, **< 1000 MΩ = Alerta**. E o **Índice de Polarização** (IEEE 43): < 1 Crítico, 1–2 Alerta, ≥ 2 OK. Corrigir os valores?
- TTR (relação de transformação) e resistência ôhmica: hoje classificamos por **desvio % vs. referência** (1% / 2%). Qual a tolerância real de vocês?

### 1.4 Análise de Fluidos (2.3.2.3) 🔴 — *o mais carente de critérios*
- Precisamos dos **critérios laboratoriais reais** por ensaio: FQ (viscosidade, TAN/TBN, água em ppm), CR (espectrometria Fe/Cu/Si em ppm), **contagem de partículas (códigos ISO 4406)**, PCB, 2-FAL. Hoje há apenas um classificador genérico por desvio %.
- Vocês recebem o **laudo do laboratório** (PDF) e lançam manualmente, ou importam um arquivo?

### 1.5 Demais análises 🟡
- **Ultrassom** (dB): limiar absoluto hoje 6/12 dB acima da linha de base. Vocês trabalham com dB absoluto ou variação sobre baseline por ponto?
- **Espessura**: perda hoje 10%/20% sobre a espessura nominal. Confirmam? Calculam **taxa de corrosão** (mm/ano)?
- **Qualidade de Energia** (THD): hoje 5%/8% (IEEE 519). Seguem IEEE 519 ou **PRODIST Módulo 8**?
- **Corretiva** (alinhamento/balanceamento): tolerâncias de desalinhamento e de balanceamento residual — quais valores?
- **Sensitiva**: é qualitativa (condição informada pelo técnico). Vocês têm um **checklist padrão** (ruído, folga, vazamento, odor)?

### 1.6 Normas (cadastro) 🟡
- Qual a **lista oficial de NBRs/normas** que vocês citam nos laudos? (cadastramos 3 exemplos)

---

## 2. Coleta de dados — fluxo operacional 🟡

- A coleta é **digitada manualmente** no sistema ou **importada do coletor/instrumento** (CSV/arquivo)? Quais **modelos de coletores** vocês usam?
- **Geolocalização** da coleta é necessária? (o campo existe, mas não exigimos)
- **Upload de fotos/evidências** por medição: necessário já no go-live? (previsto no Anexo, ainda não implementado)
- Controle de **calibração da instrumentação**: querem **alerta automático** quando a calibração estiver vencendo?

---

## 3. Ordem de Serviço Preditiva (OSP) 🔴

- Hoje **toda medição CRÍTICA gera OSP automática**. Está correto? Medições em **Alerta** também devem gerar OSP, ou só registrar?
- Mapeamento atual: Crítico → prioridade **Alta**. **SLA por prioridade**: Urgente 1 dia, Alta 3, Média 7, Baixa 15. Confirmam os prazos?
- Fluxo de status: Aberta → Em análise → Em execução → Aguardando aprovação → Finalizada/Cancelada. Confirma os estados e **quem aprova** (cliente? gestor?)?
- Anexo 2.6.2 prevê **checklist técnico, controle de peças, tempo de execução e assinatura do cliente**. Quais desses entram na 1ª versão? Têm modelos de checklist?
- **Custos** (estimado/real): **quem preenche e em que momento**?

---

## 4. Laudos técnicos 🔴

- Precisamos do **modelo/layout oficial do laudo** de vocês (cabeçalho, logo, seções, rodapé, campos obrigatórios). Hoje há um layout padrão.
- **Assinatura digital**: é assinatura **gráfica** (imagem) ou **certificado digital ICP-Brasil**? Quem assina (qual conselho de classe)?
- Numeração sequencial atual: `LT-AAAA-0001`. Mantém esse formato?

---

## 5. Perfis e controle de acesso 🟡

- Confirmar a **matriz de permissões** dos 7 perfis (quem registra, edita, visualiza e aprova em cada módulo).
- Escopo do **Cliente PCM**: vê **toda a planta** ou só a **unidade/área** dele? E **Gestor local** vs **Gestor corporativo**?
- Um usuário **técnico** atende **um ou vários clientes**? Um usuário cliente pode ter **várias unidades**?

---

## 6. Notificações (2.10) 🟡

- Querem **WhatsApp e Push** já no go-live? Em caso afirmativo, **qual provedor** (os adaptadores estão prontos, mas desligados)?
- Credenciais de **SMTP** (e-mail) para produção.
- Confirmar **quem recebe cada evento** (equipamento crítico, nova OSP, laudo concluído, aprovação pendente, SLA vencendo).
- Frequência da verificação de **SLA vencendo** (hoje pensada para um cron diário).

---

## 7. Dashboards / BI executivo 🟡

- Definições de **MTBF e MTTR**: hoje MTTR = média (finalização − abertura) das OSPs finalizadas; MTBF = média dos intervalos entre falhas consecutivas por equipamento. Confirmam essas definições?
- **Índice de disponibilidade** (2.8.1.1.6): requer dados de **parada/operação** dos equipamentos. Vocês registram tempo de parada? De onde virá esse dado?
- Fonte dos **custos de manutenção** para o BI (hoje vêm das OSPs).

---

## 8. Site institucional (Cláusula 2.2) 🔴

- O contrato inclui o **site institucional**, ainda não iniciado. Precisamos de: **logo, textos, serviços, fotos, contatos** e referência visual desejada.

---

## 9. Infraestrutura, dados e LGPD 🟡

- **Onde hospedar** (qual VPS/cloud) e **domínio**.
- Política de **backups** (frequência/retenção) e **retenção de dados** (LGPD).
- **Logomarcas** da contratada e dos clientes (campos já existem).
- Há **dados/históricos legados** para migrar (planilhas, sistema atual)?

---

### Como responder
Sugerimos uma reunião para fechar os itens 🔴 (regras de vibração, termografia, ensaios
elétricos e fluidos; fluxo de OSP; modelo de laudo; site). Os demais podem ser confirmados
por escrito (WhatsApp/e-mail), conforme Cláusula 15 do contrato.
