from datetime import datetime

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import exporters
from .filtros import FiltroInvalido, ler_filtros
from .reports import REPORTS

#: Prévia (JSON) é paginada; o arquivo exportado leva TODAS as linhas do filtro.
PREVIA_POR_PAGINA = 100
PREVIA_MAXIMO_POR_PAGINA = 500


def _inteiro_positivo(valor, padrao):
    return int(valor) if valor and str(valor).isdigit() and int(valor) > 0 else padrao


class RelatorioListView(APIView):
    """Catálogo de relatórios disponíveis ao usuário (Anexo I 2.9.1)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        disponiveis = [
            {
                "key": key,
                "nome": rep["nome"],
                "descricao": rep["descricao"],
                "categoria": rep["categoria"],
                "interno_only": rep["interno_only"],
                "aceita_parque": rep["aceita_parque"],
            }
            for key, rep in REPORTS.items()
            if not (rep["interno_only"] and not request.user.is_interno)
        ]
        return Response(disponiveis)


class RelatorioGerarView(APIView):
    """
    Gera um relatório. ?formato=json (prévia paginada) | csv | xlsx | pdf (arquivo).

    Filtros (validados — 400 se malformados): ?cliente= &data_inicio=AAAA-MM-DD
    &data_fim=AAAA-MM-DD &area= &setor= &equipamento=. Prévia: ?page= &page_size=
    (máx. 500). Prévia e arquivo saem do mesmo builder com os mesmos filtros.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        rep = REPORTS.get(key)
        if not rep:
            return Response({"detail": "Relatório não encontrado."}, status=404)
        if rep["interno_only"] and not request.user.is_interno:
            return Response({"detail": "Acesso restrito à equipe interna."}, status=403)
        formato = request.query_params.get("formato", "json")
        if formato != "json" and formato not in exporters.EXPORTERS:
            return Response({"detail": "Formato inválido (use json, csv, xlsx ou pdf)."}, status=400)
        try:
            filtros = ler_filtros(request.query_params)
        except FiltroInvalido as erro:
            return Response(erro.erros, status=400)
        if filtros.recorte_de_parque and not rep["aceita_parque"]:
            return Response(
                {"detail": "Este relatório não pode ser recortado por área, setor ou equipamento."},
                status=400,
            )

        relatorio = rep["builder"](request.user, filtros)

        if formato == "json":
            tamanho = min(_inteiro_positivo(request.query_params.get("page_size"), PREVIA_POR_PAGINA),
                          PREVIA_MAXIMO_POR_PAGINA)
            total = len(relatorio.linhas)
            paginas = max(1, -(-total // tamanho))
            pagina = min(_inteiro_positivo(request.query_params.get("page"), 1), paginas)
            inicio = (pagina - 1) * tamanho
            return Response({
                "titulo": relatorio.titulo,
                "colunas": relatorio.colunas,
                "linhas": relatorio.linhas[inicio:inicio + tamanho],
                "total_linhas": total,
                "pagina": pagina,
                "paginas": paginas,
                "page_size": tamanho,
                "filtros": filtros.como_dict(),
            })

        conteudo = exporters.EXPORTERS[formato](relatorio)
        resp = HttpResponse(conteudo, content_type=exporters.CONTENT_TYPES[formato])
        nome = f"relatorio_{key}_{datetime.now():%Y%m%d}"
        resp["Content-Disposition"] = f'attachment; filename="{nome}.{formato}"'
        return resp
