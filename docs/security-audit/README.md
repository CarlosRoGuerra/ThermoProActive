# Auditoria de segurança — ThermoProActive / Pred Ativos

Auditoria de 20/09/2026 sobre a revisão `cac2513` (branch `main`).

| Arquivo | O que é |
| --- | --- |
| `relatorio-auditoria-seguranca.pdf` | **O relatório.** Capa, resumo executivo com gráficos, pontos fortes e fracos, tabela de achados por categoria, detalhamento técnico, recomendações priorizadas e as issues em Markdown. |
| `issues-github.md` | As mesmas issues da seção 7 do PDF, em Markdown nativo — copiar daqui evita a sujeira de copiar de um PDF. |
| `achados.py` | **Os dados.** Um dicionário por achado (severidade, arquivo:linha, trecho, prova de conceito, impacto, correção, critérios de aceite), mais pontos fortes, pontos fracos, recomendações e metodologia. Edite aqui e regere. |
| `issues.py` | Monta o Markdown das issues a partir de `achados.py`. `GRUPOS` define o agrupamento (achados triviais do mesmo tema viram uma issue só). |
| `gerar_relatorio.py` | Monta o PDF (reportlab) e os gráficos (matplotlib). |
| `_graficos/` | PNGs intermediários dos gráficos; recriados a cada execução. |

## Regerar o relatório

Nada é instalado globalmente — use um ambiente virtual:

```bash
# Windows
python -m venv .venv
.venv/Scripts/python -m pip install reportlab matplotlib
.venv/Scripts/python docs/security-audit/gerar_relatorio.py

# Linux / macOS
python3 -m venv .venv
.venv/bin/python -m pip install reportlab matplotlib
.venv/bin/python docs/security-audit/gerar_relatorio.py
```

O script pode ser executado de qualquer diretório: os caminhos são resolvidos a
partir do próprio arquivo. `matplotlib` também fornece as fontes DejaVu usadas
no PDF (cobertura Unicode completa); sem elas o reportlab cai em Helvetica/Courier.

Para conferir o resultado visualmente, rasterize as páginas:

```bash
.venv/Scripts/python -m pip install pypdfium2
.venv/Scripts/python -c "import pypdfium2 as p; d=p.PdfDocument('docs/security-audit/relatorio-auditoria-seguranca.pdf'); [d[i].render(scale=1.6).to_pil().save(f'p{i+1:02d}.png') for i in range(len(d))]"
```

## Convenções

- **Severidades e cores:** crítica `#B91C1C`, alta `#EA580C`, média `#D97706`,
  baixa `#2563EB`, ponto forte `#059669`. Definidas em `COR` (gerar_relatorio.py).
- **Somente achados verificados.** Nenhum item do relatório é especulativo;
  os marcados com `poc=True` foram reproduzidos com teste executável
  (`manage.py test` + `APIClient`) e a saída real está transcrita no PDF.
- **Categorias sem achado são declaradas como tal.** A categoria 5 (XSS) não
  gerou achados; em vez de forçar um, o relatório traz a tabela do que foi
  inspecionado e está correto (`VERIFICADO_XSS` em `achados.py`).

## Ao corrigir um achado

1. Aplique a correção e marque os critérios de aceite da issue correspondente.
2. Em `achados.py`, remova o achado (ou registre a data da correção).
3. Regere o PDF — contagens, gráficos, tabelas e issues se atualizam sozinhos.
