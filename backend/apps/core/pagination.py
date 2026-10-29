from rest_framework.pagination import PageNumberPagination


class PaginacaoPadrao(PageNumberPagination):
    """
    Paginação padrão da API: 20 por página, `?page_size=` aceito até 500.

    O `PageNumberPagination` puro ignora `?page_size=` em silêncio: as telas que
    pediam 300/500 recebiam 20 e calculavam contagens (OSPs abertas, vencidas)
    sobre uma fração dos dados. O teto impede uma requisição de puxar a base
    inteira; acima dele, a resposta traz `next` e a tela avisa que há mais.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500
