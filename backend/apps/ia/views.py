"""
API da área administrativa de IA — só Master interno, em leitura e em escrita.

  /ia/chaves/              chaves de API dos provedores (a chave nunca é devolvida)
  /ia/ativacoes/           um item por recurso do sistema, ligado ou desligado
  /ia/ativacoes/<recurso>/ liga/desliga o recurso e escolhe a chave e o modelo
"""
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMaster

from .models import AtivacaoIA, ChaveApiIA, RecursoIA
from .serializers import AtivacaoIASerializer, ChaveApiIASerializer


class ChaveApiIAViewSet(viewsets.ModelViewSet):
    """Configuração da plataforma (não é dado de cliente): não há escopo por cliente a aplicar."""

    queryset = ChaveApiIA.objects.prefetch_related("ativacoes")
    serializer_class = ChaveApiIASerializer
    permission_classes = [IsMaster]
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user, atualizado_por=self.request.user)

    def perform_update(self, serializer):
        serializer.save(atualizado_por=self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        # Recurso que usava a chave não pode ficar "ligado" sem credencial: desliga antes.
        for ativacao in instance.ativacoes.all():
            ativacao.habilitado = False
            ativacao.credencial = None
            ativacao.atualizado_por = self.request.user
            ativacao.save()
        # Exclusão de verdade (sem inativar): o segredo sai do banco.
        instance.delete()


def _ativacao(recurso) -> AtivacaoIA:
    """O registro do recurso, ou um em memória (desligado) quando ele nunca foi configurado."""
    return (
        AtivacaoIA.objects.select_related("credencial").filter(recurso=recurso).first()
        or AtivacaoIA(recurso=recurso)
    )


class AtivacoesIAView(APIView):
    permission_classes = [IsMaster]

    def get(self, request):
        return Response(AtivacaoIASerializer([_ativacao(r) for r in RecursoIA.values], many=True).data)


class AtivacaoIAView(APIView):
    permission_classes = [IsMaster]

    def _recurso(self, recurso):
        if recurso not in RecursoIA.values:
            raise NotFound("Recurso de IA desconhecido.")
        return _ativacao(recurso)

    def get(self, request, recurso):
        return Response(AtivacaoIASerializer(self._recurso(recurso)).data)

    def patch(self, request, recurso):
        serializer = AtivacaoIASerializer(self._recurso(recurso), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(atualizado_por=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
