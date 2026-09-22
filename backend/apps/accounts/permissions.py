"""
Permissões por perfil e por NÍVEL — item 2.1.1.6 e hierarquia definida na
reunião de 22/07/2026 (Master / Sênior / Pleno / Júnior, nos ambientes
BackEnd (equipe interna) e FrontEnd (cliente)).

Matriz vigente (padrão inicial — o cliente ainda vai detalhar Sênior/Pleno/Júnior):
    Master  → cura os dados de sistema, gerencia usuários e exclui.
    Sênior  → opera (coletas/laudos/OSPs) e exclui; não mexe em dados de sistema.
    Pleno   → opera; NÃO exclui; não mexe em dados de sistema.
    Júnior  → opera; NÃO exclui; não mexe em dados de sistema.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import PERFIS_INTERNOS, Perfil


class IsInterno(BasePermission):
    """Apenas equipe da CONTRATADA (Admin/Gestor/Técnico)."""

    message = "Apenas usuários internos têm acesso a este recurso."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_interno)


class IsAdmin(BasePermission):
    message = "Apenas administradores."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.perfil == Perfil.ADMIN
        )


class IsMaster(BasePermission):
    """Apenas Master interno; Master de cliente nunca administra a plataforma."""

    message = "Apenas usuários de nível Master podem executar esta ação."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_interno and user.is_master)


class InternoEditaClienteVisualiza(BasePermission):
    """
    Interno: leitura+escrita. Cliente: somente leitura (Portal — item 2.7).
    Exclusão exige nível Master ou Sênior — Júnior/Pleno alimentam mas não apagam.

    É o padrão do Portal: vale para o parque (Cliente/Área/Setor/Equipamento/
    Componente/Dados técnicos/Rota), para os recursos técnicos (inspeções,
    medições, análises, laudos) e para os catálogos internos (Prestador,
    Instrumentação, dados de sistema). O único recurso em que o cliente escreve
    é a Ordem de Serviço, e só nos campos de retorno — ver
    `InternoEditaClienteResponde`.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if user.perfil not in PERFIS_INTERNOS:
            return False
        if request.method == "DELETE" and not user.pode_excluir:
            self.message = "Seu nível de acesso não permite excluir registros."
            return False
        return True


class InternoEditaClienteResponde(BasePermission):
    """
    Interno: leitura+escrita, exclusão exige nível Master ou Sênior (igual
    `InternoEditaClienteVisualiza`).

    Cliente: consulta + RETORNO DE INFORMAÇÃO. Ele não cria nem exclui nada —
    só atualiza (PATCH/PUT) um registro que a CONTRATADA já abriu, e apenas nos
    campos de resposta. QUAIS campos é decidido no serializer
    (`OrdemServicoSerializer.CAMPOS_RETORNO_CLIENTE`), não aqui: esta classe só
    responde "pode tocar neste tipo de recurso, e com qual verbo".

    Decisão de 2026-09-21, que substitui a de 2026-09-18: o Portal volta a ser
    somente leitura em todo o resto (parque, rotas, inspeções, medições,
    análises), como no item 2.7 do Anexo I. A única escrita que sobra é a que o
    cliente é a ÚNICA fonte: quando a corretiva foi planejada e executada, quem
    executou, o que foi feito, se a abertura da máquina confirmou o
    diagnóstico, e quanto custou de fato — números que alimentam o ROI da
    Seção D e o KPI de acerto do diagnóstico.

    O ESCOPO por cliente continua em `get_queryset()` de cada ViewSet
    (`escopo_cliente`/`campo_cliente`) — esta classe nunca decide "em qual
    cliente".
    """

    #: Verbos de retorno: alteram um registro existente, nunca criam nem apagam.
    METODOS_RETORNO = {"PATCH", "PUT"}

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if user.is_interno:
            if request.method == "DELETE" and not user.pode_excluir:
                self.message = "Seu nível de acesso não permite excluir registros."
                return False
            return True
        if user.is_cliente and request.method in self.METODOS_RETORNO:
            return True
        self.message = (
            "No Portal você consulta e devolve as informações da execução. "
            "Criar ou excluir registros é feito pela equipe da ThermoProActive."
        )
        return False


class MasterEditaDemaisVisualizam(BasePermission):
    """
    Só o Master (interno) cria/edita/remove; os demais autenticados apenas leem.
    Usada nas tabelas de referência (dados de sistema): o cliente definiu que
    Sênior/Pleno/Júnior precisam solicitar ao Master para inserir esses cadastros,
    o que evita divergência de padronização e exclusões não autorizadas.
    """

    message = "Apenas o nível Master pode alterar os dados de sistema."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.pode_curar_dados_sistema


class SouDoCliente(BasePermission):
    """
    Portal: qualquer usuário do cliente vê a própria equipe; só o Master do
    lado do cliente convida (mesma regra de PodeConvidar, em ConviteView).
    """

    message = "Apenas usuários do Portal do Cliente têm acesso a este recurso."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_cliente and user.cliente_id):
            return False
        if request.method in SAFE_METHODS:
            return True
        self.message = "Apenas o Master da sua organização pode convidar colaboradores."
        return user.is_master
