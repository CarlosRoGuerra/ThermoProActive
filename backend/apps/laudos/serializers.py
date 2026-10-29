from rest_framework import serializers

from .models import Laudo, TemplateLaudo, EventoLaudo, AnexoLaudo


class LaudoSerializer(serializers.ModelSerializer):
    inspecao_id = serializers.IntegerField(source="inspecao.id", read_only=True)
    cliente_nome = serializers.SerializerMethodField()
    cliente_id = serializers.IntegerField(source="cliente.pk", read_only=True)
    tipo_analise = serializers.SerializerMethodField()
    responsavel_nome = serializers.CharField(source="responsavel.nome", read_only=True)
    responsavel_conselho = serializers.CharField(source="responsavel.conselho_classe", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Laudo
        fields = [
            "id", "numero", "versao", "inspecao", "inspecao_id", "relatorio_origem", "cliente_nome", "cliente_id", "tipo_analise",
            "titulo", "criticidade_geral", "diagnostico", "recomendacoes",
            "conclusao", "responsavel", "responsavel_nome", "responsavel_conselho",
            "status", "status_display", "data_emissao", "criado_em",
            "documento_raiz", "anterior", "motivo_revisao", "template", "snapshot_hash", "assinatura",
            "pdf_disponivel", "pdf_hash", "cancelado_em", "cancelado_por", "motivo_cancelamento",
            "data_medicao_campo", "data_upload_osps", "data_upload_relatorio",
        ]
        read_only_fields = ["numero", "data_emissao", "status", "versao", "criticidade_geral"]

    def get_cliente_nome(self, obj):
        return (obj.snapshot_emissao.get("laudo") or {}).get("cliente_nome", obj.cliente.nome)

    def get_tipo_analise(self, obj):
        from .services import tipo_analise_laudo
        return (obj.snapshot_emissao.get("laudo") or {}).get("tipo_analise", tipo_analise_laudo(obj))

    def to_representation(self, instance):
        dados = super().to_representation(instance)
        congelado = instance.snapshot_emissao.get("laudo") or {}
        if congelado:
            for campo in ("cliente_nome", "responsavel_nome", "responsavel_conselho"):
                if campo in congelado:
                    dados[campo] = congelado[campo]
        return dados

    def validate(self, attrs):
        from .services import validar_template
        if self.instance:
            if self.instance.status != "RASCUNHO":
                raise serializers.ValidationError("Documento emitido/cancelado é imutável. Crie uma revisão.")
            if any(campo in attrs and attrs[campo] != getattr(self.instance, campo)
                   for campo in ("inspecao", "relatorio_origem")):
                raise serializers.ValidationError("A origem do documento não pode ser alterada.")
        elif bool(attrs.get("inspecao")) == bool(attrs.get("relatorio_origem")):
            raise serializers.ValidationError("Informe exatamente uma origem: inspeção ou relatório de rotas.")
        responsavel = attrs.get("responsavel", getattr(self.instance, "responsavel", None))
        if responsavel and (not responsavel.is_interno or not responsavel.is_active):
            raise serializers.ValidationError({"responsavel": "Selecione um responsável interno ativo."})
        candidato = Laudo(**{campo: attrs.get(campo, getattr(self.instance, campo, None))
                            for campo in ("inspecao", "relatorio_origem", "template")})
        validar_template(candidato)
        return attrs


class GerarLaudoSerializer(serializers.Serializer):
    inspecao = serializers.IntegerField(required=False, min_value=1, help_text="ID da inspeção de origem.")
    relatorio_origem = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        if bool(attrs.get("inspecao")) == bool(attrs.get("relatorio_origem")):
            raise serializers.ValidationError("Informe exatamente uma origem: inspeção ou relatório de rotas.")
        return attrs


class MotivoLaudoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)


class TemplateLaudoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateLaudo
        fields = ["id", "nome", "cliente", "tipo_analise", "configuracao", "versao", "ativo", "criado_em", "atualizado_em"]
        read_only_fields = ["versao", "criado_em", "atualizado_em"]

    def validate_configuracao(self, valor):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from .templates import validar_configuracao
        try:
            return validar_configuracao(valor)
        except DjangoValidationError as erro:
            raise serializers.ValidationError(erro.messages)


class EventoLaudoSerializer(serializers.ModelSerializer):
    tipo = serializers.CharField(source="acao", read_only=True)
    usuario_nome = serializers.CharField(source="autor.nome", read_only=True)

    class Meta:
        model = EventoLaudo
        fields = ["id", "tipo", "acao", "autor", "usuario_nome", "criado_em", "motivo", "dados"]


class AnexoLaudoSerializer(serializers.ModelSerializer):
    imagem = serializers.ImageField(write_only=True)
    data_uri = serializers.CharField(read_only=True)

    class Meta:
        model = AnexoLaudo
        fields = ["id", "nome", "legenda", "mime", "sha256", "tamanho", "criado_por", "criado_em", "imagem", "data_uri"]
        read_only_fields = ["nome", "mime", "sha256", "tamanho", "criado_por", "criado_em"]

    def validate_imagem(self, imagem):
        from django.conf import settings
        from .pdf import _validar_imagem, ErroGeracaoPDF
        limite = int(getattr(settings, "LAUDOS_MAX_IMAGEM_BYTES", 10 * 1024 * 1024))
        if imagem.size > limite:
            raise serializers.ValidationError("A imagem excede o limite operacional configurado.")
        imagem.seek(0)
        try:
            self._mime_imagem = _validar_imagem(imagem.read(limite + 1))
        except ErroGeracaoPDF as erro:
            raise serializers.ValidationError(str(erro))
        imagem.seek(0)
        return imagem

    def create(self, validated_data):
        import hashlib
        imagem = validated_data.pop("imagem")
        conteudo = imagem.read()
        return AnexoLaudo.objects.create(**validated_data, nome=imagem.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255],
            mime=self._mime_imagem, conteudo=conteudo, tamanho=len(conteudo), sha256=hashlib.sha256(conteudo).hexdigest())
