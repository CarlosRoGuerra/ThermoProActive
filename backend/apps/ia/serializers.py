from rest_framework import serializers

from .models import DESCRICAO_RECURSO, RECURSOS_IMPLEMENTADOS, AtivacaoIA, ChaveApiIA, ProvedorIA


class ChaveApiIASerializer(serializers.ModelSerializer):
    """
    A chave entra por `chave` (só escrita) e NUNCA sai: a resposta traz `chave_mascarada`
    (os 4 últimos caracteres). Na edição, `chave` é opcional — sem ela, a gravada fica.
    """

    chave = serializers.CharField(
        write_only=True, required=False, min_length=8, max_length=500, trim_whitespace=True,
        style={"input_type": "password"},
    )
    chave_mascarada = serializers.CharField(source="mascarada", read_only=True)
    provedor_display = serializers.CharField(source="get_provedor_display", read_only=True)
    # Falso depois de trocar a chave de cifra do servidor: a chave precisa ser cadastrada de novo.
    legivel = serializers.BooleanField(read_only=True)
    em_uso = serializers.SerializerMethodField()

    class Meta:
        model = ChaveApiIA
        fields = [
            "id", "provedor", "provedor_display", "rotulo", "chave", "chave_mascarada",
            "modelo_padrao", "url_base", "legivel", "em_uso", "criado_em", "atualizado_em",
        ]
        read_only_fields = ["criado_em", "atualizado_em"]

    def get_em_uso(self, obj) -> list:
        """Recursos habilitados que usam esta chave (o aviso de quem para se ela for removida)."""
        return [a.get_recurso_display() for a in obj.ativacoes.all() if a.habilitado]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("chave"):
            raise serializers.ValidationError({"chave": "Informe a chave de API."})
        provedor = attrs.get("provedor", getattr(self.instance, "provedor", ""))
        url_base = attrs.get("url_base", getattr(self.instance, "url_base", ""))
        if provedor == ProvedorIA.OUTRO and not url_base:
            raise serializers.ValidationError({"url_base": "Informe o endereço da API deste provedor."})
        return attrs

    def create(self, validated_data):
        chave = validated_data.pop("chave")
        instancia = ChaveApiIA(**validated_data)
        instancia.definir_chave(chave)
        instancia.save()
        return instancia

    def update(self, instance, validated_data):
        chave = validated_data.pop("chave", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if chave:
            instance.definir_chave(chave)
        instance.save()
        return instance


class AtivacaoIASerializer(serializers.ModelSerializer):
    recurso_display = serializers.CharField(source="get_recurso_display", read_only=True)
    descricao = serializers.SerializerMethodField()
    # Falso = a função ainda não existe no sistema: a ativação fica gravada e nada é enviado.
    implementado = serializers.SerializerMethodField()
    credencial_rotulo = serializers.SerializerMethodField()
    modelo_efetivo = serializers.CharField(read_only=True)

    class Meta:
        model = AtivacaoIA
        fields = [
            "recurso", "recurso_display", "descricao", "implementado", "habilitado",
            "credencial", "credencial_rotulo", "modelo", "modelo_efetivo", "atualizado_em",
        ]
        read_only_fields = ["recurso", "atualizado_em"]

    def get_descricao(self, obj) -> str:
        return DESCRICAO_RECURSO.get(obj.recurso, "")

    def get_implementado(self, obj) -> bool:
        return obj.recurso in RECURSOS_IMPLEMENTADOS

    def get_credencial_rotulo(self, obj) -> str:
        return str(obj.credencial) if obj.credencial_id else ""

    def validate(self, attrs):
        habilitado = attrs.get("habilitado", getattr(self.instance, "habilitado", False))
        credencial = attrs.get("credencial", getattr(self.instance, "credencial", None))
        if habilitado and credencial is None:
            raise serializers.ValidationError({"credencial": "Escolha a chave de API antes de habilitar o recurso."})
        if habilitado and not credencial.legivel:
            raise serializers.ValidationError(
                {"credencial": "Esta chave não pôde ser lida pelo servidor. Cadastre-a de novo antes de habilitar."}
            )
        return attrs
