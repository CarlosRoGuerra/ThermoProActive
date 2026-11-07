# 20 — Auditoria de escopo: contrato × sistema atual

> **Atualização de 03/11/2026.** Os percentuais abaixo são os de 31/10. A situação mudou depois disso:
> * **Implementação:** três agentes implementaram os itens das seções 2 e 3 (`docs/21`, `docs/22`, `docs/23`).
> * **Validação:** um validador independente revisou o trabalho em duas rodadas (`docs/24`). Os defeitos V-01 a V-09 foram corrigidos ou aceitos com resíduo documentado.
> * **Regressão:** a suíte completa rodou com 1123 testes OK em PostgreSQL 16 e em SQLite.
>
> Percentuais atuais, mesmo método e mesmos pesos (detalhe em `docs/24` §0.6 e §00):
>
> | Tópico | Percentual |
> |---|---|
> | Módulos funcionais §2 | **100%** (150/150; recontagem da Coleta em `docs/24` §00) |
> | Login/acesso + Laudos + Portal + Dashboards | **100%** |
> | Análise preditiva | **100%** (matriz de risco provisória, a confirmar pelo cliente) |
> | Contrato completo | **≈ 84%** |
> | Só o sistema | **≈ 93%** |
>
> O que segura o geral:
> * site institucional (0%, peso 10%);
> * HTTPS e backup externo na VPS (Cl. 4.1, dependem da contratante);
> * entrega e homologação ainda não publicadas.

Data: 31/10/2026 · Base: `main` (`143042f`) + alterações da auditoria de 29/10 (working tree, não commitadas).

Fontes:

* **Contrato:** `contrato.txt` (Cláusulas 2–13 e Anexo I).
* **Conformidade por módulo:** `docs/12` a `docs/17`.
* **Rastreabilidade e segurança:** QA de 29/10, com `docs/security-audit/2026-10/qa-report.md` §2 e `docs/18`.
* **Leitura direta dos models:** por exemplo, `cadastros.ModuloTecnico` e `MODULOS_PLANEJADOS`.

## Método

Cada item folha do contrato recebe uma nota:

| Nota | Situação | Peso |
|---|---|---|
| **C** | Completo | 1 |
| **P** | Parcial | 0,5 |
| **N** | Não implementado | 0 |

Regras de pontuação:

* **IoT (2.3.1.5)** fica fora da conta, porque o contrato o marca como "futuro".
* **Regra de negócio pendente.** O item conta como **C** quando funciona com um padrão documentado e só falta o
  cliente confirmar a regra (ex.: quem aprova a OSP).
* **Captura sem relatório ou ficha.** O item conta como **P** quando o sistema só grava o dado, sem relatório
  ou ficha dedicada, ou sem critério de classificação.

O percentual geral depende dos pesos entre os blocos. Os pesos usados estão explícitos na seção 3.

## 1. Resultado por bloco

| Bloco | Itens | Pontos | % |
|---|---|---|---|
| Anexo I §1 — Arquitetura (painéis, portal, responsivo, back, front, BD, cloud, APIs) | 9 | 8,5 | **94%** |
| Anexo I §2.1 — Login e acesso | 13 | 12,5 | **96%** |
| Anexo I §2.2 — Cadastros | 18 | 18 | **100%** |
| Anexo I §2.3 — Coleta de dados (8 recursos − IoT + 26 tipos) | 33 | 27 | **82%** |
| Anexo I §2.4 — Análise preditiva | 10 | 8,5 | **85%** |
| Anexo I §2.5 — Laudos | 13 | 12,5 | **96%** |
| Anexo I §2.6 — OSP | 20 | 16 | **80%** |
| Anexo I §2.7 — Portal do cliente | 8 | 7,5 | **94%** |
| Anexo I §2.8 — Dashboards/BI | 16 | 15,5 | **97%** |
| Anexo I §2.9 — Relatórios | 10 | 10 | **100%** |
| Anexo I §2.10 — Notificações | 9 | 8 | **89%** |
| **Anexo I §2 — total funcional** | **150** | **135,5** | **90%** |
| Anexo I §3 — Entidades do banco | 22 | 20 | **91%** |
| Cl. 4.1 — Segurança (acesso, autenticação segura, logs, backups) | 4 | 3 | **75%** |
| Cl. 2.2 — Site institucional | 1 | 0 | **0%** |
| Cl. 9 — Entrega para homologação | — | — | código auditado; **não publicado nem homologado** |

## 2. O que falta, item a item

**Não implementado (N):**

| Item | O que falta | Depende de |
|---|---|---|
| Cl. 2.2 | **Site institucional**: não iniciado | Materiais da contratante (`docs/03` §8): logo, textos, serviços, fotos, contatos |
| 2.3.1.3 | Upload de arquivos não-imagem (PDF de laboratório, planilhas); hoje só imagens | Nada: só desenvolvimento |
| 2.6.2.2 | Checklist técnico da OSP | Cliente definir o conteúdo do checklist (`docs/03` §3) |
| 2.6.2.6 | Assinatura do cliente na OSP | Cliente definir a forma de assinatura |
| 2.6.2.7 | Controle de peças | Cliente definir o escopo (só existe o valor de material) |
| 2.10.1.3 | Push notification (responde `NAO_CONFIGURADO`) | Desenvolvimento (Web Push com VAPID é open-source) |
| 3.1.11 | Entidade "Sensores" | Ligada ao IoT futuro; o cadastro simples pode ser feito |

**Parcial (P):**

| Item | Situação atual | Para completar |
|---|---|---|
| 2.1.1.6 | Privilégios por perfil + nível + cliente; **sem ACL por setor/unidade** | Confirmar se o cliente exige restrição por setor |
| 2.3.2.2.2–4 | Termografia mecânica (dinâmica/estática) e processos: dado capturado, relatório marcado "não implementado" | Módulo de relatório + critério de ΔT do cliente |
| 2.3.2.5 | Ensaios em motores (RxI): captura genérica, sem ficha dedicada | Ficha + critérios |
| 2.3.2.6 / 2.3.2.7 / 2.3.2.10 | Ultrassom, espessura, qualidade de energia: captura genérica, sem classificação | Critérios normativos do cliente (`docs/12`) |
| 2.3.2.8.1.1–2 | Alinhamento a laser (eixos e polias): relatório marcado "não implementado" | Módulo de relatório (balanceamento já completo) |
| 2.4.1.3 / 2.4.1.5 / 2.4.2.4 | Tendência descritiva, indicadores de risco e sugestões técnicas sem prescrição genérica | Decisão consciente (`docs/13`); ampliar só com regra do cliente |
| 2.5.1.3 | Assinatura digital = aprovação eletrônica interna; **sem certificado criptográfico** (ICP-Brasil) | Definir se o cliente exige certificado |
| 2.6.2.4 / 2.6.2.8 | Evidências da OSP vêm da análise (sem upload direto); tempo de execução parcial | Upload na OSP; métrica de execução |
| 2.7.1.1.8 / 2.8.1.3.4 | "Tempo real" = consulta a cada 60 s, não push/WebSocket | Depende do push (2.10.1.3) |
| 1.1.5 / Cl. 4.1 | VPS só em HTTP, backup implementado mas sem cópia externa e não ativado na VPS | Domínio + credenciais da contratante; deploy (`docs/18` C1–C4) |
| 3.1.2 | Equipe técnica: faltam DN, RG, CTPS, estado civil, filhos e endereço completo (CPF, cargo, conselho e assinatura existem) | Confirmar necessidade (são dados pessoais sensíveis à LGPD; coletar só se houver finalidade) |
| 3.1.22 | Logs: há trilha de segurança, histórico de OSP, eventos de laudo e logs de aplicação; **sem trilha genérica de alterações de cadastro** | Auditoria de alterações (ex.: tabela de eventos por modelo) |

## 3. Percentual geral

Pesos usados, por esforço e valor no contrato:

| Bloco | Peso | Resultado | Contribuição |
|---|---|---|---|
| Módulos funcionais (Anexo I §2) | 65% | 90% | 58,7 |
| Arquitetura + banco (Anexo I §1 e §3) | 10% | 92% | 9,2 |
| Segurança/infra (Cl. 4.1) | 10% | 75% | 7,5 |
| Site institucional (Cl. 2.2) | 10% | 0% | 0 |
| Entrega e homologação (Cl. 9) | 5% | 30% (auditado, falta publicar e homologar) | 1,5 |
| **Contrato completo** | 100% | | **≈ 77%** |
| **Só o sistema** (sem o site) | 90% | | **≈ 85%** |

Com outros pesos razoáveis o total fica entre **75% e 80%**. O fator dominante é o site institucional, ainda em 0%.

## 4. Observações contratuais

* Pela Cl. 11.2, os itens parciais e não implementados acima são **escopo contratado**, não aditivo. A exceção é
  o IoT (2.3.1.5), marcado como "futuro".
* Vários itens dependem de respostas da contratante (`docs/03`: OSP 🔴, laudos 🔴, site 🔴). Pela Cl. 5.3, o
  atraso no envio de materiais ou decisões ajusta o cronograma pelo período correspondente. Convém registrar
  por escrito a data de cada pedido feito (Cl. 15.2).
* Há 54 arquivos da auditoria de 29/10 sem commit. Eles precisam ser commitados e publicados para que a VPS
  reflita o estado descrito aqui.
