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
    Usada nos recursos técnicos (coletas, laudos) e nos catálogos internos
    (Prestador, Instrumentação, dados de sistema) — nenhum deles é "dado do
    cliente" que ele deva escrever. Para o que o cliente PODE escrever, ver
    `InternoOuClienteMasterEdita`.
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


class InternoOuClienteMasterEdita(BasePermission):
    """
    Interno: leitura+escrita, exclusão exige nível Master ou Sênior (igual
    `InternoEditaClienteVisualiza`).

    Cliente: o Master da própria empresa TAMBÉM cria/edita/exclui (decisão de
    2026-09-18 — até então o Portal era só leitura, item 2.7 do Anexo I).
    Os demais níveis do cliente (Sênior/Pleno/Júnior — PCM/Local/Manutentor)
    continuam só lendo: do lado do cliente não é o nível que decide quem
    exclui, é especificamente o Master — o mesmo usuário que já podia
    convidar o resto da equipe (`SouDoCliente`/`PodeConvidar`).

    Usada SÓ onde faz sentido o cliente escrever: o cadastro do próprio parque
    (Cliente/Área/Setor/Equipamento/Componente/Dados técnicos/Rota), Ordens de
    Serviço e Achados/análises. NÃO é usada em Prestador, Instrumentação nem
    nos catálogos globais (normas, tipos, condições) — esses continuam com
    `InternoEditaClienteVisualiza`, porque editá-los afetaria todos os
    clientes, não só quem está logado.

    O ESCOPO por cliente continua em `get_queryset()` de cada ViewSet
    (`escopo_cliente`/`campo_cliente`) — esta classe só decide "pode escrever
    ALGUMA coisa neste tipo de recurso", nunca "em qual cliente".
    """

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
        if user.is_cliente and user.is_master:
            return True
        self.message = (
            "Seu perfil só tem leitura. Peça ao Master da sua empresa para criar, "
            "editar ou excluir este registro."
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
