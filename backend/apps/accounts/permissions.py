"""Permissões por perfil — controle de acesso por setor/privilégio (item 2.1.1.6)."""
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


class InternoEditaClienteVisualiza(BasePermission):
    """
    Interno: leitura+escrita. Cliente: somente leitura (Portal — item 2.7).
    Usada nos recursos técnicos (coletas, laudos).
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.perfil in PERFIS_INTERNOS
