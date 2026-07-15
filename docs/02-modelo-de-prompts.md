# Modelo de Prompts para Geração de Código (reutilizável)

> Operacionaliza o **Princípio geral** definido pela ThermoProActive: todo prompt de
> geração de código deve conter **(1) contexto do projeto**, **(2) critérios de aceite** e
> **(3) restrições contratuais** relevantes (em especial a **Cláusula 12.4** — sem lock-in).

## Template padrão

```
CONTEXTO DO PROJETO
- Sistema: ThermoProActive (gestão de manutenção preditiva).
- Stack: Python 3.13 + Django 5 + DRF + PostgreSQL (back); Next.js 15 + React + TS +
  Tailwind (front). API REST com JWT.
- Módulo do Anexo I: [ex.: 2.3.2.2 Termografia Infravermelha].
- Padrões já adotados:
    * Apps modulares em backend/apps/<app> (models, serializers, views, urls, admin).
    * Modelos herdam de apps.core.models.BaseModel (timestamps + soft-delete `ativo`).
    * Regras de negócio técnicas ficam em <app>/rules.py (ver coletas/rules.py).
    * Permissões por perfil em apps.accounts.permissions.
    * Front consome a API via src/lib/api.ts; tipos em src/lib/types.ts.

CRITÉRIOS DE ACEITE
- [Liste o comportamento esperado, campos, validações e casos de borda.]
- [Ex.: medição com ΔT > 15°C deve classificar criticidade = CRÍTICO.]

RESTRIÇÕES CONTRATUAIS
- Cláusula 12.4: nada de mecanismo de bloqueio ou dependência tecnológica obrigatória.
  → Só bibliotecas open-source (MIT/BSD/Apache/PSF); nada de SaaS/licença proprietária;
    limiares de regra parametrizáveis em tabela (não “escondidos” no código).
- Cláusula 12.2/12.3: código, banco e APIs devem ser portáveis e transferíveis.
- LGPD (13.2): dados pessoais com auditoria e acesso controlado por perfil.
```

## Fase 1 — Discovery (detalhamento de regras por módulo)

Prompt para detalhar cada um dos 10 tipos de análise técnica do item **2.3.2** do Anexo I
(repetir um por subtipo). Resultado consolidado em `docs/01-DISCOVERY-modulos-tecnicos.md`.

```
Atue como analista de sistemas especializado em manutenção preditiva industrial.
Módulo: [COLE O TRECHO DO ANEXO I].
Para este módulo, defina:
1. Campos de dados coletados em cada tipo de medição.
2. Unidades de medida e faixas de valores típicas.
3. Regras que classificam um valor como anomalia / criticidade alta.
4. Perfis (Técnico/Analista, Cliente PCM, etc.) que registram ou visualizam.
5. Perguntas a fazer à ThermoProActive para fechar as lacunas.
```

## Próximos módulos sugeridos (ordem de implementação)

1. **2.3.2.2 Termografia** — alto valor, regra de ΔT simples e bem documentada.
2. **2.3.2.4 / 2.3.2.5 Ensaios Elétricos** — regras objetivas (TTR, isolação, PI).
3. **2.6 OSP** — disparo automático a partir de medição CRÍTICA (já há gancho no modelo).
4. **2.10 Notificações** — e-mail/WhatsApp/push nos eventos (nova OS, laudo concluído…).
5. **2.8 BI** — expandir o endpoint /dashboard com KPIs executivos (MTBF/MTTR).
```
