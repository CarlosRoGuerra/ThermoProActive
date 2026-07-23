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
    """Apenas o nível Master (concede acessos e cura os dados de sistema)."""

    message = "Apenas usuários de nível Master podem executar esta ação."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_master)


class InternoEditaClienteVisualiza(BasePermission):
    """
    Interno: leitura+escrita. Cliente: somente leitura (Portal — item 2.7).
    Exclusão exige nível Master ou Sênior — Júnior/Pleno alimentam mas não apagam.
    Usada nos recursos técnicos (coletas, laudos).
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
