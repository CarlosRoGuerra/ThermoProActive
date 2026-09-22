# -*- coding: utf-8 -*-
"""
Monta o texto Markdown das issues do GitHub a partir de `achados.py`.

Achados triviais do mesmo tema são agrupados numa issue só (ver GRUPOS), para
não gerar spam de issues no repositório.
"""
from achados import ACHADOS

LABEL_SEVERIDADE = {
    "critica": "severidade:crítica",
    "alta": "severidade:alta",
    "media": "severidade:média",
    "baixa": "severidade:baixa",
}

# Cada entrada vira UMA issue. `ids` com mais de um achado = agrupamento.
GRUPOS = [
    dict(
        ids=["A-06"],
        titulo="Endpoints JWT legados /api/auth/login/ e /api/auth/refresh/ contornam MFA, "
               "bloqueio de conta e revogação de sessão",
        severidade="critica",
    ),
    dict(
        ids=["A-03"],
        titulo="/media/ é servido sem autenticação e expõe evidências técnicas e assinaturas digitais",
        severidade="alta",
    ),
    dict(
        ids=["A-02"],
        titulo="Rota aceita equipamento de outro cliente e vaza o parque alheio na folha de campo",
        severidade="alta",
    ),
    dict(
        ids=["A-07"],
        titulo="Segredos padrão embutidos no código, sem validação de startup que os recuse",
        severidade="alta",
    ),
    dict(
        ids=["A-01"],
        titulo="_escopo() do motor de relatórios falha aberto e entrega dados de todos os clientes",
        severidade="media",
    ),
    dict(
        ids=["A-04", "A-05"],
        titulo="Higiene de controle de acesso: filtro de tenant duplicado e /api/empresas/ "
               "legível por qualquer conta",
        severidade="baixa",
        nota=(
            "Agrupa dois achados de baixa severidade e mesmo tema (permissão/escopo declarados fora do "
            "padrão do projeto). Nenhum dos dois é explorável para vazamento entre inquilinos hoje; ambos "
            "são dívida técnica de segurança que barateia a próxima regressão."
        ),
    ),
]

_por_id = {a["id"]: a for a in ACHADOS}


def _bloco_achado(a, numerar_titulo=False):
    """Corpo em Markdown de um achado dentro de uma issue."""
    L = []
    if numerar_titulo:
        L.append(f"### {a['id']} — {a['titulo']}")
        L.append("")
    L.append("**Problema**")
    L.append("")
    L.append(a["porque"])
    L.append("")
    if a.get("bypassa"):
        L.append("O endpoint contorna, uma a uma, as seguintes proteções:")
        L.append("")
        for b in a["bypassa"]:
            L.append(f"- {b}")
        L.append("")
    L.append("**Evidência**")
    L.append("")
    L.append("Arquivos: " + ", ".join(f"`{f}`" for f in a["arquivos"]))
    L.append("")
    L.append("```python")
    L.extend(a["trecho"].split("\n"))
    L.append("```")
    L.append("")
    if a.get("poc") and a.get("poc_texto"):
        L.append("Prova de conceito reproduzida (`manage.py test` com `APIClient`):")
        L.append("")
        L.append("```text")
        L.extend(a["poc_texto"].split("\n"))
        L.append("```")
        L.append("")
    if a.get("condicoes"):
        L.append("**Condições de explorabilidade**")
        L.append("")
        L.append(a["condicoes"])
        L.append("")
    L.append("**Impacto**")
    L.append("")
    L.append(a["impacto"])
    L.append("")
    L.append("**Sugestão de correção**")
    L.append("")
    L.append(a["correcao"])
    L.append("")
    return L


def montar_issues():
    """Devolve [(numero, titulo_curto, texto_markdown_completo), ...]."""
    saida = []
    for n, grupo in enumerate(GRUPOS, start=1):
        achados = [_por_id[i] for i in grupo["ids"]]
        L = []
        L.append(f"# [Segurança] {grupo['titulo']}")
        L.append("")
        L.append(f"**Labels sugeridas:** `security`, `{LABEL_SEVERIDADE[grupo['severidade']]}`")
        L.append("")
        L.append(f"**Achado(s) da auditoria:** {', '.join(grupo['ids'])}")
        L.append("")
        if grupo.get("nota"):
            L.append(f"> {grupo['nota']}")
            L.append("")
        L.append("---")
        L.append("")
        varios = len(achados) > 1
        for a in achados:
            L.extend(_bloco_achado(a, numerar_titulo=varios))
            if varios:
                L.append("---")
                L.append("")
        L.append("**Critérios de aceite**")
        L.append("")
        for a in achados:
            if varios:
                L.append(f"_{a['id']}_")
            for c in a["criterios"]:
                L.append(f"- [ ] {c}")
            if varios:
                L.append("")
        saida.append((n, grupo["titulo"], "\n".join(L)))
    return saida


if __name__ == "__main__":
    for n, titulo, texto in montar_issues():
        print(f"--- ISSUE {n} ---")
        print(texto)
        print(f"--- FIM ISSUE {n} ---")
        print()
