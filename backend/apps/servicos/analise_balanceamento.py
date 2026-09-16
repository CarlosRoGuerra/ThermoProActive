"""Catálogos e análise técnica do balanceamento, sempre no contexto do item da rota."""
from decimal import Decimal
from django.db.models import Q
from rest_framework import serializers

from apps.cadastros.models import Condicao, TipoAnomalia, TipoComponente, TipoRecomendacao
from apps.coletas.models import Achado, StatusCarregamento
from .models import TipoServico


def validar_servico_balanceamento(servico):
    if not servico.ativo or servico.tipo != TipoServico.BALANCEAMENTO:
        raise serializers.ValidationError("O serviço deve ser um balanceamento ativo.")
    if servico.item_id:
        atividade = servico.item.carregamento
        if not servico.item.ativo or not atividade.ativo or atividade.status != StatusCarregamento.EM_CAMPO:
            raise serializers.ValidationError("A atividade não está aberta para edição.")
        if atividade.tipo_corretiva != TipoServico.BALANCEAMENTO:
            raise serializers.ValidationError("A atividade não é de balanceamento.")


def catalogos_balanceamento(tecnologia_id, anomalia_id=None):
    componentes = TipoComponente.objects.ativos().filter(tecnologias=tecnologia_id)
    anomalias = TipoAnomalia.objects.ativos().filter(tecnologias=tecnologia_id)
    recomendacoes = TipoRecomendacao.objects.ativos().filter(tecnologias=tecnologia_id)
    if anomalia_id:
        # "Anomalias compatíveis" é metadado OPCIONAL de curadoria (2026-09-16): uma
        # recomendação sem nenhuma anomalia vinculada continua valendo pra qualquer
        # anomalia (universal) — só quando JÁ existe um vínculo explícito é que a
        # recomendação fica restrita a ele. Antes disso, uma recomendação sem curadoria
        # nenhuma sumia da lista inteira, bloqueando o técnico por falta de cadastro.
        recomendacoes = recomendacoes.filter(Q(anomalias__isnull=True) | Q(anomalias__pk=anomalia_id))
    return componentes, anomalias, recomendacoes.distinct()


class AnaliseBalanceamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achado
        fields = [
            "id", "condicao", "tipo_componente", "componente_texto", "detalhe",
            "tipo_anomalia", "recomendacao", "anomalia_texto", "recomendacao_texto", "observacoes",
        ]
        extra_kwargs = {
            campo: {"required": True, "allow_null": False}
            for campo in ("condicao", "tipo_componente", "tipo_anomalia", "recomendacao")
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tecnologia_id = self.context["item"].carregamento.tecnologia_id
        componentes, anomalias, _ = catalogos_balanceamento(tecnologia_id)
        self.fields["condicao"].queryset = Condicao.objects.ativos()
        self.fields["tipo_componente"].queryset = componentes
        self.fields["tipo_anomalia"].queryset = anomalias
        self.fields["recomendacao"].queryset = TipoRecomendacao.objects.ativos().filter(tecnologias=tecnologia_id)

    def validate(self, attrs):
        # Valida o estado final também em PATCH: trocar só a anomalia não pode
        # manter uma recomendação incompatível que já estava gravada.
        atual = lambda campo: attrs.get(campo, getattr(self.instance, campo, None))
        for campo in ("condicao", "tipo_componente", "tipo_anomalia", "recomendacao"):
            valor = atual(campo)
            if valor is None or not self.fields[campo].queryset.filter(pk=valor.pk).exists():
                raise serializers.ValidationError({campo: "Selecione uma opção ativa compatível com a tecnologia da atividade."})
        # "Anomalias compatíveis" é opcional (ver catalogos_balanceamento acima): só
        # bloqueia quando a recomendação JÁ tem algum vínculo cadastrado e a anomalia
        # atual não está nele — sem vínculo nenhum, a recomendação vale pra qualquer
        # anomalia.
        recomendacao = atual("recomendacao")
        if recomendacao.anomalias.exists() and not recomendacao.anomalias.filter(pk=atual("tipo_anomalia").pk).exists():
            raise serializers.ValidationError({"recomendacao": "Recomendação incompatível com a anomalia selecionada."})
        return attrs


class CabecalhoBalanceamentoSerializer(serializers.Serializer):
    rotacao_hz = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0"), allow_null=True, required=False)
