from rest_framework.permissions import SAFE_METHODS, BasePermission


class InternoLeMasterEdita(BasePermission):
    """Cadastros de análise preditiva: equipe interna lê; só Master escreve (dado de sistema)."""

    message = "Apenas usuários de nível Master podem alterar parâmetros de análise preditiva."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_interno):
            return False
        return request.method in SAFE_METHODS or user.is_master
