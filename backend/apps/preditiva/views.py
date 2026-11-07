from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsInterno
from apps.cadastros.models import Equipamento
from apps.coletas.models import Achado, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao
from apps.coletas.views import escopo_cliente, recorte_cliente
from apps.core.escopo import restringe_setor
from apps.ensaios.models import ResultadoEnsaio

from .models import AceitacaoSugestao
from .permissions import InternoLeMasterEdita
from .risco import ranking_equipamentos
from .serializers import (
    AceitacaoSugestaoSerializer,
    ConfiguracaoTendenciaSerializer,
    LimiteAlarmeSerieSerializer,
    MatrizRiscoSerializer,
    RegraSugestaoSerializer,
)
from .sugestoes import aderencia, registrar_decisao, sugestoes_para_achado
from .fluidos import analisar_valor_fluido
from .tendencia import analisar_medicao

AVISO_INDICE = "Índice de priorização a partir de condição, tendência e criticidade do ativo. Não é probabilidade de falha."


class TendenciaView(APIView):
    """Tendência e projeção até o limite de UMA medição. Só leitura: nada é gravado."""

    permission_classes = [IsAuthenticated]
    MODELOS = {"vibracao": MedicaoVibracao, "termografia": MedicaoTermografia, "tecnica": MedicaoTecnica}

    def get(self, request, modalidade, pk):
        modelo = self.MODELOS.get(modalidade)
        if modelo is None:
            raise NotFound("Modalidade desconhecida.")
        qs = escopo_cliente(
            modelo.objects.select_related("equipamento__setor__area", "inspecao", "componente", "instrumento"),
            request.user, campo_cliente="inspecao__cliente",
        )
        qs = restringe_setor(qs, request.user, "equipamento__setor")  # 2.1.1.6: fora do setor → 404
        medicao = get_object_or_404(qs, pk=pk)
        return Response(analisar_medicao(medicao))


class TendenciaFluidoView(APIView):
    """Tendência de um parâmetro de fluido numa campanha. Só leitura."""

    permission_classes = [IsAuthenticated]

    def get(self, request, resultado_id, codigo):
        qs = escopo_cliente(
            ResultadoEnsaio.objects.filter(ativo=True).select_related(
                "item__carregamento", "item__equipamento__tipo_equipamento", "item__coleta_fluido", "ensaio",
            ),
            request.user, campo_cliente="item__carregamento__cliente",
        )
        qs = restringe_setor(qs, request.user, "item__equipamento__setor")  # 2.1.1.6: fora do setor → 404
        resultado = get_object_or_404(qs, pk=resultado_id)
        return Response(analisar_valor_fluido(resultado, codigo))


class EspessuraView(APIView):
    """Perda, taxa de corrosão e classificação de UMA medição de espessura (2.3.2.7). Só leitura."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.coletas.espessura import classificar, dias_entre, perda_percentual, taxa_corrosao
        from apps.coletas.models import TipoAnalise

        from .tendencia import analisar_medicao, limites_medicao, serie_comparavel

        qs = escopo_cliente(
            MedicaoTecnica.objects.filter(tipo=TipoAnalise.ESPESSURA).select_related(
                "equipamento__setor__area", "inspecao", "componente", "instrumento",
            ),
            request.user, campo_cliente="inspecao__cliente",
        )
        qs = restringe_setor(qs, request.user, "equipamento__setor")  # 2.1.1.6: fora do setor → 404
        medicao = get_object_or_404(qs, pk=pk)
        nominal = (medicao.parametros or {}).get("espessura_nominal_mm")
        instantes, valores, ids, _ = serie_comparavel(medicao, 2)
        anterior = taxa = dias = None
        if len(valores) >= 2:
            anterior_valor, anterior_dt = valores[-2], instantes[-2]
            dias = dias_entre(anterior_dt, instantes[-1])
            taxa = taxa_corrosao(anterior_valor, medicao.valor, dias)
            anterior = {"medicao_id": ids[-2], "valor": str(anterior_valor), "data_hora": anterior_dt.isoformat()}
        limite = limites_medicao(medicao)
        limites = {v["nivel"]: v["valor"] for v in limite["limites"]} if limite["validado"] else {}
        perda = perda_percentual(nominal, medicao.valor)
        return Response({
            "medicao_id": medicao.pk,
            "valor": str(medicao.valor), "espessura_nominal_mm": nominal,
            "perda_percentual": str(perda) if perda is not None else None,
            "anterior": anterior,
            "dias_entre_medicoes": float(dias) if dias is not None else None,
            "taxa_corrosao_mm_ano": str(taxa) if taxa is not None else None,
            "classificacao": classificar(medicao.valor, limites),
            "limite": {"validado": limite["validado"], "motivo": limite["motivo"], "fonte": limite["fonte"],
                       "valores": [{"nivel": v["nivel"], "valor": str(v["valor"])} for v in limite["limites"]]},
            "projecoes": analisar_medicao(medicao)["serie"]["projecoes"] if limite["validado"] else [],
            "aviso": "Classificação só com limite cadastrado e validado. Taxa e data estimada são aritmética "
                     "e estatística da medição, não vida útil remanescente.",
        })


class UltrassomView(APIView):
    """Condição e tendência de UMA leitura de ultrassom (2.3.2.6). Só leitura."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.coletas.models import MedicaoTecnica, TipoAnalise
        from apps.coletas.ultrassom import classificar_superior

        from .tendencia import analisar_medicao, limites_medicao

        qs = escopo_cliente(
            MedicaoTecnica.objects.filter(tipo=TipoAnalise.ULTRASSOM).select_related(
                "equipamento__setor__area", "inspecao", "componente", "instrumento",
            ),
            request.user, campo_cliente="inspecao__cliente",
        )
        qs = restringe_setor(qs, request.user, "equipamento__setor")  # 2.1.1.6: fora do setor → 404
        medicao = get_object_or_404(qs, pk=pk)
        limite = limites_medicao(medicao)
        valores = {v["nivel"]: v["valor"] for v in limite["limites"]}
        # Critério de ultrassom é de sentido superior; qualquer outro sentido fica pendente.
        superior = all(v["sentido"] == "SUPERIOR" for v in limite["limites"]) if limite["limites"] else False
        classificacao = classificar_superior(medicao.valor, valores) if (limite["validado"] and superior) else "PENDENTE"
        return Response({
            "medicao_id": medicao.pk, "valor": str(medicao.valor), "unidade": medicao.unidade,
            "grandeza": medicao.grandeza, "ganho_db": (medicao.parametros or {}).get("ganho_db"),
            "distancia_cm": (medicao.parametros or {}).get("distancia_cm"),
            "classificacao": classificacao,
            "limite": {"validado": limite["validado"], "motivo": limite["motivo"], "fonte": limite["fonte"],
                       "valores": [{"nivel": v["nivel"], "valor": str(v["valor"])} for v in limite["limites"]]},
            "projecoes": analisar_medicao(medicao)["serie"]["projecoes"] if limite["validado"] else [],
            "aviso": "Nível em dB só é comparado com o mesmo instrumento, ganho e distância. A condição depende de "
                     "critério cadastrado e validado; não há limite universal.",
        })


class QualidadeEnergiaView(APIView):
    """Condição e tendência de UMA leitura de qualidade de energia (2.3.2.10). Só leitura."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.coletas.models import MedicaoTecnica, TipoAnalise
        from apps.coletas.qualidade_energia import classificar_superior

        from .tendencia import analisar_medicao, limites_medicao

        qs = escopo_cliente(
            MedicaoTecnica.objects.filter(tipo=TipoAnalise.QUALIDADE_ENERGIA).select_related(
                "equipamento__setor__area", "inspecao", "componente", "instrumento",
            ),
            request.user, campo_cliente="inspecao__cliente",
        )
        qs = restringe_setor(qs, request.user, "equipamento__setor")  # 2.1.1.6: fora do setor → 404
        medicao = get_object_or_404(qs, pk=pk)
        limite = limites_medicao(medicao)
        valores = {v["nivel"]: v["valor"] for v in limite["limites"]}
        superior = all(v["sentido"] == "SUPERIOR" for v in limite["limites"]) if limite["limites"] else False
        classificacao = classificar_superior(medicao.valor, valores) if (limite["validado"] and superior) else "PENDENTE"
        return Response({
            "medicao_id": medicao.pk, "grandeza": medicao.grandeza, "valor": str(medicao.valor),
            "unidade": medicao.unidade, "janela_agregacao": (medicao.parametros or {}).get("janela_agregacao"),
            "classificacao": classificacao,
            "limite": {"validado": limite["validado"], "motivo": limite["motivo"], "fonte": limite["fonte"],
                       "valores": [{"nivel": v["nivel"], "valor": str(v["valor"])} for v in limite["limites"]]},
            "projecoes": analisar_medicao(medicao)["serie"]["projecoes"] if limite["validado"] else [],
            "aviso": "Não há limiar universal de THD ou de desequilíbrio: a condição depende do critério cadastrado e "
                     "validado. Não constitui estudo completo de qualidade de energia.",
        })


class AlinhamentoView(APIView):
    """Antes e depois de um alinhamento a laser, reduções e condição pela tolerância cadastrada (2.3.2.8.1.1–2). Só leitura."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.coletas.alinhamento import SUBTIPOS, analise_par

        qs = escopo_cliente(
            MedicaoTecnica.objects.filter(subtipo__in=SUBTIPOS).select_related(
                "equipamento__setor__area", "inspecao", "componente", "instrumento",
            ),
            request.user, campo_cliente="inspecao__cliente",
        )
        qs = restringe_setor(qs, request.user, "equipamento__setor")  # 2.1.1.6: fora do setor → 404
        medicao = get_object_or_404(qs, pk=pk)
        return Response({"medicao_id": medicao.pk, "subtipo": medicao.subtipo, **analise_par(medicao),
                         "aviso": "Tolerância só com critério cadastrado e validado (com a faixa de rpm na fonte). "
                                  "Não há correção de calço calculada pelo sistema."})


class MotorRxiView(APIView):
    """Índices DAR e IP do grupo de leituras de resistência de isolação de um motor (2.3.2.5.1.1). Só leitura."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from apps.coletas.motor_rxi import analise_grupo

        qs = escopo_cliente(
            MedicaoTecnica.objects.filter(subtipo="MOTOR_RI").select_related("inspecao", "equipamento", "componente",
                                                                              "instrumento"),
            request.user, campo_cliente="inspecao__cliente",
        )
        qs = restringe_setor(qs, request.user, "equipamento__setor")  # 2.1.1.6: fora do setor → 404
        medicao = get_object_or_404(qs, pk=pk)
        return Response({"medicao_id": medicao.pk, **analise_grupo(medicao),
                         "aviso": "Índices aritméticos; a condição só com critério cadastrado e validado. "
                                  "Não é diagnóstico de falha."})


class RankingRiscoView(APIView):
    """Ranking de risco dos equipamentos, com a decomposição de cada índice."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = recorte_cliente(Equipamento.objects.filter(ativo=True), request, campo_cliente="setor__area__cliente")
        qs = restringe_setor(qs, request.user, "setor")  # 2.1.1.6: equipamentos fora do setor não entram no ranking
        area = request.query_params.get("area")
        setor = request.query_params.get("setor")
        if area and area.isdigit():
            qs = qs.filter(setor__area_id=int(area))
        if setor and setor.isdigit():
            qs = qs.filter(setor_id=int(setor))
        itens = ranking_equipamentos(qs)
        return Response({"aviso": AVISO_INDICE, "total": len(itens), "itens": itens})


class SugestoesView(APIView):
    """Sugestões para um achado (regras cadastradas e histórico do mesmo cliente)."""

    permission_classes = [IsInterno]

    def get(self, request):
        achado_id = request.query_params.get("achado")
        if not (achado_id and str(achado_id).isdigit()):
            raise ValidationError({"achado": "Informe o id do achado."})
        achados = restringe_setor(
            Achado.objects.select_related("item__carregamento", "tipo_anomalia", "tipo_componente", "recomendacao"),
            request.user, "item__equipamento__setor",
        )
        achado = get_object_or_404(achados, pk=int(achado_id), ativo=True)
        return Response(sugestoes_para_achado(achado))


class AceitacaoSugestaoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Registro da decisão do analista sobre uma sugestão exibida. Nunca aplica nada sozinho."""

    serializer_class = AceitacaoSugestaoSerializer
    permission_classes = [IsInterno]

    def get_queryset(self):
        qs = AceitacaoSugestao.objects.select_related("recomendacao_sugerida", "regra", "usuario")
        achado = self.request.query_params.get("achado")
        if achado and achado.isdigit():
            qs = qs.filter(achado_id=int(achado))
        return restringe_setor(qs, self.request.user, "achado__item__equipamento__setor")

    def perform_create(self, serializer):
        dados = serializer.validated_data
        final = dados.get("recomendacao_final")
        try:
            registro = registrar_decisao(
                achado=dados["achado"], recomendacao_sugerida_id=dados["recomendacao_sugerida"].pk,
                origem=dados["origem"], decisao=dados["decisao"], usuario=self.request.user,
                recomendacao_final_id=final.pk if final else None,
                justificativa=dados.get("justificativa", ""),
            )
        except ValueError as erro:
            raise ValidationError({"detail": str(erro)})
        serializer.instance = registro


class AderenciaSugestoesView(APIView):
    permission_classes = [IsInterno]

    def get(self, request):
        return Response({"por_origem": aderencia(AceitacaoSugestao.objects.all())})


class _CadastroPreditivoViewSet(viewsets.ModelViewSet):
    """Cadastro do Master com exclusão lógica, para não apagar o histórico que citou o parâmetro."""

    permission_classes = [InternoLeMasterEdita]

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(ativo=True).order_by("-pk")

    def perform_destroy(self, instance):
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])


class ConfiguracaoTendenciaViewSet(_CadastroPreditivoViewSet):
    serializer_class = ConfiguracaoTendenciaSerializer


class LimiteAlarmeSerieViewSet(_CadastroPreditivoViewSet):
    serializer_class = LimiteAlarmeSerieSerializer


class MatrizRiscoViewSet(_CadastroPreditivoViewSet):
    serializer_class = MatrizRiscoSerializer


class RegraSugestaoViewSet(_CadastroPreditivoViewSet):
    serializer_class = RegraSugestaoSerializer
