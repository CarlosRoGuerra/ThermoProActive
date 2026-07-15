from datetime import datetime

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import exporters
from .reports import REPORTS


def _parse_date(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _filtros(request):
    cliente = request.query_params.get("cliente")
    return {
        "cliente": int(cliente) if cliente and cliente.isdigit() else None,
        "data_inicio": _parse_date(request.query_params.get("data_inicio")),
        "data_fim": _parse_date(request.query_params.get("data_fim")),
    }


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
            }
            for key, rep in REPORTS.items()
            if not (rep["interno_only"] and not request.user.is_interno)
        ]
        return Response(disponiveis)


class RelatorioGerarView(APIView):
    """
    Gera um relatório. ?formato=json (preview) | csv | xlsx | pdf (download).
    Filtros opcionais: ?cliente=&data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, key):
        rep = REPORTS.get(key)
        if not rep:
            return Response({"detail": "Relatório não encontrado."}, status=404)
        if rep["interno_only"] and not request.user.is_interno:
            return Response({"detail": "Acesso restrito à equipe interna."}, status=403)

        relatorio = rep["builder"](request.user, _filtros(request))
        formato = request.query_params.get("formato", "json")

        if formato == "json":
            return Response({
                "titulo": relatorio.titulo,
                "colunas": relatorio.colunas,
                "linhas": relatorio.linhas,
                "total_linhas": len(relatorio.linhas),
            })

        exporter = exporters.EXPORTERS.get(formato)
        if not exporter:
            return Response({"detail": "Formato inválido (use json, csv, xlsx ou pdf)."}, status=400)

        conteudo = exporter(relatorio)
        resp = HttpResponse(conteudo, content_type=exporters.CONTENT_TYPES[formato])
        nome = f"relatorio_{key}_{datetime.now():%Y%m%d}"
        resp["Content-Disposition"] = f'attachment; filename="{nome}.{formato}"'
        return resp
