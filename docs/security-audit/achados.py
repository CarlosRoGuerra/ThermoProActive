# -*- coding: utf-8 -*-
"""
Dados da auditoria de segurança do ThermoProActive (Pred Ativos).

Separado do gerador para que o relatório possa ser regerado depois de editar
apenas os achados. Cada achado foi verificado no código real; os marcados com
`poc=True` foram reproduzidos com teste executável contra a própria API.
"""

PROJETO = "ThermoProActive / Pred Ativos"
DATA_AUDITORIA = "20 de setembro de 2026"
#: Preenchida quando os achados são revisados depois da emissão. `None` = 1ª emissão.
DATA_REVISAO = "21 de setembro de 2026"
REVISAO = "cac2513 + ajustes de 21/09"

ESCOPO = [
    "backend/ — Django 5.1 + Django REST Framework (105 módulos Python; .venv e migrations fora do escopo)",
    "frontend/ — Next.js 15 (App Router) + React 19 + TypeScript (src/ completo)",
    "Deploy — docker-compose.yml, docker-compose.prod.yml, docker-compose.http.yml, "
    "backend/Dockerfile, frontend/Dockerfile, deploy/nginx/*.conf",
    "Segredos — .gitignore, .env.prod.example, backend/.env.example, frontend/.env.local.example "
    "e os 138 commits do histórico do repositório",
]

METODOLOGIA = [
    ("Stack detectada",
     "Backend Django 5.1 + DRF, ORM do Django (sem SQL cru), autenticação JWT por cookie HttpOnly "
     "(SimpleJWT + CSRF + sessão materializada no banco). Frontend Next.js 15 App Router, React 19, "
     "sem biblioteca de sanitização de HTML. PostgreSQL 16 em produção, SQLite no dev. Deploy por "
     "Docker Compose atrás de Nginx. Não há Supabase, Helm, Terraform nem pipeline de CI no repositório."),
    ("1. Banco sem tranca",
     "Não existe RLS: o isolamento de inquilino é feito por FILTRO MANUAL no ORM, em duas implementações "
     "irmãs — escopo_cliente() em apps/coletas/views.py e o atributo campo_cliente de BaseCadastroViewSet "
     "em apps/cadastros/views.py. A auditoria mapeou todo ViewSet que expõe dado de cliente e verificou "
     "se declara o filtro, se o filtro falha fechado e se existe contraparte de escrita "
     "(impedir_cross_tenant) no caminho de criação e de reatribuição."),
    ("2. Permissão no navegador",
     "O front declara a matriz de papéis em frontend/src/lib/permissions.ts (função can() + REGRAS_ROTA). "
     "Cada habilidade foi cruzada com a permission_class DRF do endpoint correspondente "
     "(apps/accounts/permissions.py)."),
    ("3. IDOR",
     "Percorridos TODOS os handlers de rota do backend — 9 módulos de urls.py, 31 ViewSets/APIViews e "
     "cada @action detail=True — verificando se a busca do objeto passa por um get_queryset() escopado "
     "ou por um get_object_or_404 solto."),
    ("4. Chaves expostas",
     "Varredura de settings, composes, Dockerfiles, scripts de seed, configs de Nginx, arquivos de "
     "exemplo e do histórico git completo (git rev-list --all). Atenção especial a defaults públicos "
     "que viram segredo real e à ausência de validação de startup que os recuse."),
    ("5. Inputs sem tratamento (XSS)",
     "Grep exaustivo no front por dangerouslySetInnerHTML, innerHTML, eval, new Function, document.write "
     "e por URLs controladas por usuário em href/src; no back por mark_safe, format_html, "
     "render_to_string, templates HTML próprios e HTML em corpo de e-mail."),
]

# severidade: critica | alta | media | baixa
ACHADOS = [
    dict(
        id="A-06", severidade="critica", categoria="3. IDOR / controle de acesso",
        titulo="Endpoints JWT legados contornam MFA, bloqueio de conta e revogação de sessão",
        arquivos=["backend/config/urls.py:16-17", "backend/apps/accounts/views.py:26-29"],
        trecho=(
            'backend/config/urls.py\n'
            '16:    path("api/auth/login/",   LoginView.as_view(),        name="login"),\n'
            '17:    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),\n'
            '\n'
            'backend/apps/accounts/views.py\n'
            '26: class LoginView(TokenObtainPairView):\n'
            '29:     serializer_class = LoginSerializer   # só acrescenta o usuário ao payload'
        ),
        porque=(
            "TokenObtainPairView do SimpleJWT declara permission_classes = () e não define throttle_classes; "
            "como REST_FRAMEWORK não define DEFAULT_THROTTLE_CLASSES (settings.py:135-140 define apenas as "
            "RATES), a rota fica pública e sem limite de tentativas. LoginSerializer "
            "(accounts/serializers.py:70-78) apenas chama super().validate() e anexa o usuário — não replica "
            "NENHUMA das travas do fluxo endurecido LoginContextualView (auth_views.py:143-206). O token "
            "emitido não carrega a claim 'sid', e CookieJWTAuthentication.authenticate "
            "(authentication.py:26-28) devolve super().authenticate(request) assim que há cabeçalho "
            "Authorization, saindo ANTES do enforce_csrf e da consulta a SessaoAutenticacao das linhas 45-52. "
            "O resultado é uma família de tokens invisível para todo o subsistema de sessões."
        ),
        bypassa=[
            "MFA/TOTP obrigatório (auth_views.py:178-194)",
            "Bloqueio após 8 tentativas, campo bloqueado_ate (auth_views.py:151-156 e 169-171)",
            "Estado da conta SUSPENDED/BLOCKED/PENDING (auth_serializers.py:61-62)",
            "Separação portal × admin (auth_views.py:173-176)",
            "Throttle de 10 logins/minuto (auth_views.py:145 + throttles.py:4-5)",
            "CSRF e a checagem de sessão viva (authentication.py:45-52)",
            "Logout, “encerrar outras sessões” e a revogação automática na troca/reset de senha "
            "(auth_views.py:249-258, 475-479 e 309)",
        ],
        poc=True,
        poc_texto=(
            "Teste executado contra a API (django test + APIClient):\n"
            "  HARDENED /api/auth/admin/login/ -> 428  (exige código MFA)\n"
            "  LEGACY   /api/auth/login/       -> 200  ['access','refresh','user']\n"
            "  conta SUSPENSA + BLOQUEADA: hardened -> 429 | legado -> 200\n"
            "  Bearer legado em /api/auth/me/  -> 200 alvo@thermoproactive.com\n"
            "  sessoes registradas no banco: 0\n"
            "  apos troca de senha + revogacao de TODAS as sessoes, Bearer legado -> 200"
        ),
        impacto=(
            "Qualquer pessoa com um par e-mail/senha válido entra sem o segundo fator, sem limite de "
            "tentativas para adivinhar a senha e sem que o bloqueio automático de conta se aplique. Uma vez "
            "dentro, o token sobrevive ao logout, ao “encerrar outras sessões” e à própria redefinição de "
            "senha — e /api/auth/refresh/ o renova indefinidamente (ROTATE_REFRESH_TOKENS com 7 dias de "
            "vida). É a rota de persistência ideal depois de um vazamento de credencial."
        ),
        correcao=(
            "Remover as duas linhas de config/urls.py e a classe LoginView de accounts/views.py: o frontend "
            "nunca as usa (frontend/src/lib/api.ts:167 chama /auth/{area}/login/ e :56 chama "
            "/auth/session/refresh/). Se um token Bearer for necessário para integração máquina-a-máquina, "
            "criar um endpoint próprio que emita 'sid', grave SessaoAutenticacao e aplique MFA + throttle."
        ),
        criterios=[
            "path('api/auth/login/') e path('api/auth/refresh/') removidos de backend/config/urls.py",
            "Classe LoginView e LoginSerializer removidas (ou reescritas com sid + MFA + throttle)",
            "Teste automatizado: POST /api/auth/login/ devolve 404",
            "Teste automatizado: conta com MFA ativo não obtém token por nenhuma rota sem o código TOTP",
            "Teste automatizado: token obtido antes de _revogar_todas() devolve 401 depois dela",
            "Sessões existentes revogadas e novo login forçado após o deploy da correção",
        ],
    ),
    dict(
        id="A-03", severidade="alta", categoria="1. Isolamento de inquilino",
        titulo="/media/ é servido sem autenticação e expõe evidências técnicas e assinaturas digitais",
        arquivos=[
            "deploy/nginx/app.conf.template:61-65", "deploy/nginx/app.http.conf:21-25",
            "backend/apps/coletas/models.py:614", "backend/apps/accounts/models.py:108-110",
            "backend/apps/cadastros/models.py:355", "backend/apps/cadastros/models.py:418",
            "backend/config/urls.py:33-34",
        ],
        trecho=(
            'deploy/nginx/app.conf.template\n'
            '61:    location /media/ {\n'
            '62:        alias /var/www/media/;\n'
            '63:        access_log off;\n'
            '64:        expires 30d;\n'
            '65:    }\n'
            '\n'
            'backend/apps/coletas/models.py\n'
            '614:    arquivo = models.ImageField("Arquivo", upload_to="achados/")\n'
            '\n'
            'backend/apps/accounts/models.py\n'
            '108:    assinatura_digital = models.ImageField(\n'
            '109:        "Assinatura digital", upload_to="assinaturas/", null=True, blank=True\n'
            '110:    )'
        ),
        porque=(
            "Todo o esforço de multi-tenant do projeto vive na camada DRF; os arquivos, porém, saem pelo "
            "Nginx direto do volume, sem passar pelo Django — não há auth_request, nem X-Accel-Redirect, nem "
            "token assinado na URL. O nome do arquivo é o nome original enviado pelo usuário "
            "(FileSystemStorage só acrescenta sufixo em caso de colisão), então os caminhos são curtos e "
            "enumeráveis: /media/achados/IMG_0042.jpg, /media/assinaturas/joao.png. O access_log off apaga "
            "até o rastro da tentativa. Vale nos dois composes de deploy e, em DEBUG, também no próprio "
            "Django (config/urls.py:33-34)."
        ),
        bypassa=[],
        poc=False,
        impacto=(
            "Vazamento cross-tenant sem sequer precisar de conta: as fotos de termografia e vibração são a "
            "evidência técnica das anomalias de cada cliente (o que quebrou, onde, em que ativo), e as "
            "placas de identificação trazem fabricante, modelo e número de série do parque alheio. Pior, "
            "/media/assinaturas/ guarda a imagem da assinatura do responsável técnico usada para assinar "
            "laudos — baixá-la permite forjar um laudo com aparência legítima."
        ),
        correcao=(
            "Servir mídia por uma view Django autenticada que reaplique escopo_cliente sobre o dono do "
            "arquivo e delegue a entrega ao Nginx via X-Accel-Redirect (location internal), ou usar "
            "auth_request apontando para um endpoint de autorização. Em paralelo, trocar o nome do arquivo "
            "por UUID (upload_to com função) para eliminar a enumeração, e reativar o access_log."
        ),
        criterios=[
            "GET /media/achados/<arquivo> sem cookie de sessão devolve 401/403",
            "GET /media/achados/<arquivo> autenticado como cliente de OUTRO tenant devolve 403/404",
            "location /media/ marcada como 'internal' no Nginx (ou protegida por auth_request)",
            "upload_to de achados, assinaturas e placas gera nome aleatório (UUID)",
            "access_log reativado para /media/",
        ],
    ),
    dict(
        id="A-02", severidade="baixa", categoria="1. Isolamento de inquilino",
        titulo="Rota aceita equipamento de outro cliente (vetor do Portal fechado em 21/09)",
        arquivos=[
            "backend/apps/cadastros/views.py:117-139", "backend/apps/cadastros/views.py:325-331",
            "backend/apps/cadastros/models.py:735", "backend/apps/coletas/serializers.py:426-434",
        ],
        trecho=(
            'backend/apps/cadastros/views.py  (_impedir_apontar_para_outro_cliente)\n'
            '129:        primeiro_campo, _, resto = self.campo_cliente.partition("__")\n'
            '130:        if primeiro_campo not in validated_data:\n'
            '131:            return   # <- só o 1o campo do caminho é validado\n'
            '\n'
            '317: class RotaViewSet(BaseCadastroViewSet):\n'
            '318:     campo_cliente = "cliente"     # <- o M2M equipamentos fica de fora\n'
            '     (a permissão herdada passou a ser InternoEditaClienteVisualiza em 21/09)\n'
            '\n'
            'backend/apps/coletas/serializers.py  (CarregamentoSerializer.create)\n'
            '428:            equipamentos = carregamento.rota.equipamentos.order_by(...)\n'
            '431:            ItemInspecao.objects.bulk_create([\n'
            '432:                ItemInspecao(carregamento=carregamento, equipamento=eq, ordem=i)\n'
            '433:                for i, eq in enumerate(equipamentos, start=1)\n'
            '434:            ])   # <- copia TODOS, sem checar de quem são'
        ),
        porque=(
            "A guarda de escrita valida apenas campo_cliente.partition('__')[0], isto é, o campo 'cliente' "
            "da própria Rota. O ManyToMany 'equipamentos' (cadastros/models.py:735) nunca é conferido. "
            "Quando o Portal escrevia em /api/rotas/, isso era uma quebra direta de inquilino: o Master de "
            "um cliente gravava IDs de equipamentos de qualquer outro, e o vazamento se materializava no "
            "carregamento da rota — CarregamentoSerializer.create copia todos os equipamentos para "
            "ItemInspecao sem checar o dono, e o Carregamento resultante pertence a quem montou a rota, "
            "então /api/itens-inspecao/ devolvia o item alheio como se fosse dele."
        ),
        bypassa=[],
        poc=True,
        poc_texto=(
            "PoC de 20/09, quando o Portal ainda escrevia em /api/rotas/:\n"
            "  POST /api/rotas/ com equipamento do cliente B  -> 201\n"
            "  interno carrega a rota                         -> 201\n"
            "  Master do cliente A le /api/itens-inspecao/    -> 200\n"
            "     VAZOU: TAG-SECRETA-B-001 | Turbina confidencial da vitima |\n"
            "            Area secreta B / Setor secreto B\n"
            "\n"
            "Mesmo POST apos a mudanca de 21/09 (apps/osp/test_retorno_cliente.py):\n"
            "  POST /api/rotas/ como Master do cliente       -> 403"
        ),
        condicoes=(
            "O VETOR FOI FECHADO em 21/09/2026: RotaViewSet voltou a "
            "InternoEditaClienteVisualiza, e nenhum perfil de cliente escreve mais em /api/rotas/ — "
            "coberto por apps/osp/test_retorno_cliente.py::PortalSoConsulta::test_nao_cria_rota. "
            "O que permanece é a LACUNA ESTRUTURAL: a guarda continua cega a relações ManyToMany, e "
            "CarregamentoSerializer.create continua copiando equipamentos sem conferir o dono. Hoje só a "
            "equipe interna alcança esse caminho, e ela tem escopo global por desenho — então não há "
            "quebra de inquilino, só risco de contaminação de dado por engano. Se a escrita do cliente "
            "voltar a ser liberada, como já foi em 18/09, o achado volta a ser ALTA sem nenhum aviso."
        ),
        impacto=(
            "Com o Portal somente-consulta, o impacto residual é de integridade e não de confidencialidade: "
            "um analista interno pode, por engano, montar uma rota do Cliente A com um equipamento do "
            "Cliente B, contaminando a folha de campo, os relatórios e o indicador de cobertura de ativos. "
            "O risco relevante é de regressão — o código não impede o cenário grave, apenas deixou de "
            "oferecer a porta por onde se chegava a ele."
        ),
        correcao=(
            "Validar o M2M na escrita, agora pelo dono da ROTA e não pelo usuário: em "
            "RotaSerializer.validate, recusar qualquer equipamento cujo setor__area__cliente_id seja "
            "diferente do cliente da rota — vale para interno e para cliente, e é exatamente a checagem "
            "que servicos/atividades.py:52-53 já faz no fluxo corretivo. Em defesa em profundidade, "
            "replicar o filtro em CarregamentoSerializer.create."
        ),
        criterios=[
            "PATCH/POST /api/rotas/ com equipamento de outro cliente devolve 400, inclusive para interno",
            "CarregamentoSerializer.create ignora (ou recusa) equipamento fora do cliente do carregamento",
            "Teste de regressão em apps/cadastros/test_escopo_cliente.py cobrindo o M2M de Rota",
            "Auditoria única dos demais M2M do projeto em busca do mesmo padrão",
        ],
    ),
    dict(
        id="A-07", severidade="alta", categoria="4. Chaves expostas",
        titulo="Segredos padrão embutidos no código, sem validação de startup que os recuse",
        arquivos=[
            "backend/config/settings.py:16-18", "backend/config/settings.py:33",
            "docker-compose.yml:18", "docker-compose.yml:31", "docker-compose.yml:34",
            "backend/apps/core/management/commands/seed_demo.py:69-72",
            "backend/apps/core/management/commands/seed_demo.py:88",
            "backend/Dockerfile:25", "backend/apps/accounts/security.py:151-153",
        ],
        trecho=(
            'backend/config/settings.py\n'
            '16:    DEBUG=(bool, True),\n'
            '17:    SECRET_KEY=(str, "dev-insecure-change-me-em-producao"),\n'
            '18:    ALLOWED_HOSTS=(list, ["*"]),\n'
            '33: SECRET_KEY = env("SECRET_KEY")   # nunca levanta erro: o default cobre a ausência\n'
            '\n'
            'docker-compose.yml\n'
            '18:      POSTGRES_PASSWORD: thermo\n'
            '31:      SECRET_KEY: docker-dev-secret-troque-em-producao\n'
            '34:      DATABASE_URL: postgres://thermo:thermo@db:5432/thermoproactive\n'
            '\n'
            'backend/apps/core/management/commands/seed_demo.py\n'
            '69:            "admin@thermoproactive.com": (\n'
            '71:                {"is_staff": True, "is_superuser": True, "nivel": "MASTER"},\n'
            '88:                user.set_password("thermo123")\n'
            '\n'
            'backend/Dockerfile\n'
            "25: CMD [... \"&& { python manage.py seed_demo || echo 'seed_demo ignorado'; } && exec gunicorn ...\"]"
        ),
        porque=(
            "django-environ só usa o default quando a variável está AUSENTE — e é exatamente esse o caso "
            "perigoso: subir em produção sem SECRET_KEY não quebra nada, o Django simplesmente assume a "
            "string pública do repositório. Não há nenhum django.core.checks nem assert de boot que recuse "
            "o valor conhecido, e o mesmo vale para DEBUG=True e ALLOWED_HOSTS=['*'] como defaults. "
            "O impacto é amplificado porque accounts/security.py:151-153 deriva a chave Fernet que cifra os "
            "segredos TOTP do MFA a partir do SECRET_KEY, e security.py:30-31 usa o mesmo valor como chave "
            "HMAC dos ip_hash. Por fim, o CMD padrão da imagem backend roda seed_demo, que cria "
            "admin@thermoproactive.com com is_superuser=True e senha 'thermo123'."
        ),
        bypassa=[],
        poc=False,
        condicoes=(
            "Os composes de produção (docker-compose.prod.yml:44-47 e docker-compose.http.yml:43-46) "
            "sobrescrevem o command e NÃO rodam seed_demo, e usam ${POSTGRES_PASSWORD} sem default — o "
            "caminho documentado de deploy está correto. O risco se concretiza quando alguém sobe a imagem "
            "fora desses composes, usa o docker-compose.yml de desenvolvimento num host alcançável, ou "
            "esquece SECRET_KEY no .env.prod."
        ),
        impacto=(
            "Com o SECRET_KEY conhecido um atacante forja tokens JWT de qualquer usuário, assina cookies de "
            "sessão, falsifica tokens CSRF, decifra os segredos TOTP de MFA guardados no banco e reverte os "
            "ip_hash do log de segurança. Com 'thermo123' presente, há um superusuário Django com senha "
            "pública; com DEBUG=True, qualquer erro devolve stack trace e settings."
        ),
        correcao=(
            "1) Remover o default de SECRET_KEY (env('SECRET_KEY') sem default levanta ImproperlyConfigured) "
            "ou adicionar um django.core.checks que falhe o boot quando DEBUG=False e o valor for um dos "
            "conhecidos. 2) DEBUG default False e ALLOWED_HOSTS sem '*'. 3) Trocar os valores literais do "
            "docker-compose.yml por ${VAR:?erro} lendo um .env local. 4) Fazer seed_demo recusar rodar com "
            "DEBUG=False e sortear a senha, imprimindo-a no log. 5) Derivar a chave Fernet do MFA de uma "
            "variável própria (MFA_ENCRYPTION_KEY), desacoplando-a do SECRET_KEY."
        ),
        criterios=[
            "Boot com DEBUG=False e SECRET_KEY ausente/default falha com mensagem clara",
            "settings.py: DEBUG default False e ALLOWED_HOSTS sem '*'",
            "docker-compose.yml sem senha ou chave literal (usa ${VAR:?} + .env)",
            "seed_demo recusa rodar com DEBUG=False e não usa senha fixa",
            "Segredo do MFA derivado de variável própria, não do SECRET_KEY",
            "Chave de produção rotacionada depois da correção (a antiga está no repositório)",
        ],
    ),
    dict(
        id="A-01", severidade="media", categoria="1. Isolamento de inquilino",
        titulo="_escopo() do motor de relatórios falha ABERTO e entrega dados de todos os clientes",
        arquivos=["backend/apps/relatorios/reports.py:29-33",
                  "backend/apps/relatorios/reports.py:243-251",
                  "backend/apps/relatorios/views.py:56-82"],
        trecho=(
            'backend/apps/relatorios/reports.py\n'
            '29: def _escopo(qs, user, campo_cliente):\n'
            '30:     """Perfis cliente: restringe ao próprio cliente."""\n'
            '31:     if user.is_cliente and user.cliente_id:\n'
            '32:         return qs.filter(**{campo_cliente: user.cliente_id})\n'
            '33:     return qs          # <- FAIL-OPEN: cliente sem vínculo recebe TUDO\n'
            '\n'
            'comparar com backend/apps/coletas/views.py:49-53  (fail-closed, correto)\n'
            '49:     if user.is_cliente:\n'
            '50:         if not user.cliente_id:\n'
            '51:             return qs.none()\n'
            '52:         return qs.filter(**{campo_cliente: user.cliente_id})'
        ),
        porque=(
            "O projeto tem três implementações do mesmo filtro de tenant e duas delas documentam "
            "explicitamente a falha fechada (“Falha fechada: cliente sem cliente_id não vê nada, em vez de "
            "cair no qs inteiro sem filtro”). A do módulo relatorios não seguiu a regra: o “and "
            "user.cliente_id” transforma a ausência de vínculo em ausência de filtro. Atinge os cinco "
            "relatórios liberados ao cliente (técnico, gerencial, equipamento, falhas, histórico — "
            "reports.py:244-250), em JSON, CSV, XLSX e PDF, via GET /api/relatorios/<key>/?formato=…"
        ),
        bypassa=[],
        poc=True,
        poc_texto=(
            "Teste executado contra a API (django test + APIClient), usuario CLIENTE_PCM sem vinculo:\n"
            "  cliente_id do usuario: None\n"
            "  _escopo(reports.py) devolveu 1 clientes -> ['Cliente B (vitima)']\n"
            "  GET /api/relatorios/gerencial/ -> 200 linhas: [['Cliente B (vitima)', 0, 0, 0, '0%', 0]]"
        ),
        condicoes=(
            "Exige uma conta de perfil CLIENTE_* com o campo cliente vazio. Não é um estado que o atacante "
            "produza sozinho, mas é alcançável: User.cliente é null=True (accounts/models.py:90-98) e o "
            "campo é editável por PATCH /api/usuarios/ (UserWriteSerializer, serializers.py:47-51), então "
            "basta um erro de cadastro ou a desvinculação de um cliente para a conta virar uma "
            "chave-mestra silenciosa."
        ),
        impacto=(
            "Um único usuário mal cadastrado enxerga e EXPORTA o parque, as medições, as anomalias, as "
            "ordens de serviço e o histórico de manutenção de todos os clientes da plataforma, em planilha "
            "pronta. Como o próprio módulo oferece download em CSV/XLSX/PDF, o vazamento é de base inteira, "
            "não de registro isolado."
        ),
        correcao=(
            "Fazer _escopo devolver qs.none() quando user.is_cliente e não há cliente_id, alinhando com "
            "coletas/views.py:49-53. Melhor ainda: extrair as três cópias para uma única função em "
            "apps/core e importá-la nos três módulos, para a regra não poder divergir de novo."
        ),
        criterios=[
            "_escopo devolve queryset vazio para usuário cliente sem cliente_id",
            "Teste: usuário CLIENTE_* sem vínculo recebe 0 linhas em cada um dos 5 relatórios abertos",
            "Filtro de tenant unificado num único helper compartilhado",
            "apps/servicos/views.py e apps/servicos/atividades.py migrados para o mesmo helper (ver A-04)",
        ],
    ),
    dict(
        id="A-04", severidade="baixa", categoria="1. Isolamento de inquilino",
        titulo="Duas cópias do filtro de tenant divergem do padrão fail-closed",
        arquivos=["backend/apps/servicos/views.py:26-30", "backend/apps/servicos/atividades.py:96-97"],
        trecho=(
            'backend/apps/servicos/views.py\n'
            '26: def escopo_cliente(qs, user, campo_cliente="cliente"):\n'
            '27:     """Perfis cliente só enxergam os próprios serviços (Portal - item 2.7)."""\n'
            '28:     if user.is_cliente:\n'
            '29:         return qs.filter(**{campo_cliente: user.cliente_id})   # sem guarda de None\n'
            '30:     return qs\n'
            '\n'
            'backend/apps/servicos/atividades.py\n'
            '96:         if self.request.user.is_cliente:\n'
            '97:             qs = qs.filter(cliente_id=self.request.user.cliente_id)'
        ),
        porque=(
            "Ao contrário de A-01, aqui NÃO há vazamento hoje: cliente_id None vira “cliente_id IS NULL” e "
            "ServicoCampo.cliente (servicos/models.py:48) e Carregamento.cliente são NOT NULL, então o "
            "resultado é vazio por acidente, não por desenho. O risco é de manutenção: qualquer futura "
            "coluna de tenant que aceite NULL, ou a reutilização deste helper com outro campo_cliente, "
            "transforma o acidente em vazamento."
        ),
        bypassa=[],
        poc=False,
        impacto=(
            "Nenhum impacto explorável no código atual. Dívida técnica de segurança: a quarta cópia da mesma "
            "regra, com semântica diferente das outras três, aumenta a chance de a próxima alteração repetir "
            "o erro de A-01."
        ),
        correcao=(
            "Importar o helper único (ver A-01) em apps/servicos/views.py e apps/servicos/atividades.py e "
            "apagar as cópias locais."
        ),
        criterios=[
            "apps/servicos não define mais escopo_cliente próprio",
            "AtividadeCorretivaViewSet.get_queryset usa o helper compartilhado",
            "Teste: usuário cliente sem vínculo recebe lista vazia em /api/servicos/ e "
            "/api/atividades-corretivas/",
        ],
    ),
    dict(
        id="A-05", severidade="baixa", categoria="2. Permissão definida no navegador",
        titulo="Tela de Prestadores é escondida por papel no front, mas /api/empresas/ é legível "
               "por qualquer conta",
        arquivos=[
            "frontend/src/lib/permissions.ts:142-143", "frontend/src/lib/permissions.ts:220",
            "frontend/src/app/(admin)/prestadores/prestador-form.tsx:190-192",
            "backend/apps/cadastros/views.py:142-145", "backend/apps/accounts/permissions.py:55-66",
        ],
        trecho=(
            'frontend/src/lib/permissions.ts\n'
            '142:     case "prestadores:gerenciar":\n'
            '143:       return interno;\n'
            '220:   { prefixo: "/prestadores", exige: "prestadores:gerenciar" },\n'
            '\n'
            'frontend/src/app/(admin)/prestadores/prestador-form.tsx\n'
            '190:         await api(`/empresas/${prestadorId}/`, { method: "PATCH", body });\n'
            '\n'
            'backend/apps/cadastros/views.py\n'
            '142: class EmpresaViewSet(BaseCadastroViewSet):   # herda InternoEditaClienteVisualiza\n'
            '143:     queryset = Empresa.objects.ativos()      # campo_cliente = None (sem escopo)\n'
            '\n'
            'backend/apps/accounts/permissions.py  (InternoEditaClienteVisualiza)\n'
            '59:         if request.method in SAFE_METHODS:\n'
            '60:             return True            # <- qualquer autenticado LÊ'
        ),
        porque=(
            "A rota /prestadores só aparece para usuário interno, mas ela é apenas um rótulo: a API por trás "
            "é /api/empresas/, cujo ViewSet herda a permissão padrão de BaseCadastroViewSet, que libera "
            "leitura a qualquer autenticado, e não declara campo_cliente. A escrita está corretamente "
            "bloqueada (PATCH/POST/DELETE exigem perfil interno)."
        ),
        bypassa=[],
        poc=True,
        poc_texto=(
            "Teste executado contra a API, usuario CLIENTE_MANUT / JUNIOR do Portal:\n"
            "  GET  /api/empresas/ -> 200\n"
            "     {'nome': 'ThermoProActive Servicos Ltda', 'cnpj': '39.923.567/0001-75',\n"
            "      'email': 'financeiro@thermoproactive.com', 'telefone': '(19) 99999-0000',\n"
            "      'contato_gestor': 'Diretor Tecnico'}\n"
            "  POST /api/empresas/ (escrita) -> 403   (corretamente bloqueado)"
        ),
        impacto=(
            "Exposição limitada: Empresa é o cadastro da própria CONTRATADA (razão social, CNPJ, inscrição "
            "estadual, endereço, e-mail, telefone e nome do gestor), dados que já aparecem no timbre dos "
            "relatórios entregues. Não há dado de outro inquilino aqui. Vale corrigir porque o endpoint "
            "também alimenta o cabeçalho de laudos e pode crescer com campos sensíveis."
        ),
        correcao=(
            "Trocar a permission_class de EmpresaViewSet para IsInterno (leitura e escrita), alinhando com o "
            "gate 'prestadores:gerenciar' do front. Se o Portal precisar do nome/logo do prestador para o "
            "cabeçalho, expor um endpoint público mínimo com apenas esses campos."
        ),
        criterios=[
            "GET /api/empresas/ como usuário CLIENTE_* devolve 403",
            "Cabeçalho de relatório no Portal continua funcionando (endpoint dedicado ou dado já embutido)",
        ],
    ),
]

PONTOS_FORTES = [
    ("Filtro de tenant aplicado e com falha fechada nos 3 módulos principais",
     "apps/coletas/views.py:42-53 e apps/cadastros/views.py:94-102 devolvem qs.none() quando o usuário é "
     "cliente e não tem vínculo. Declarado em todos os ViewSets de dado de cliente: Cliente(id), Área, "
     "Setor, Equipamento, Componente, DadosTecnicosMotor/Transformador, Rota, Inspeção, as 3 Medições, "
     "Relatório, Carregamento, ItemInspeção, Achado, AchadoImagem, Laudo, OrdemServiço, ServiçoCampo, "
     "BalanceamentoPlano/Ponto e EconomiaEnergética."),
    ("Guardas de escrita cross-tenant presentes nos caminhos de criação e reatribuição",
     "apps/coletas/views.py:56-79 (impedir_cross_tenant), apps/cadastros/views.py:117-139, "
     "apps/osp/views.py:29-46 e apps/coletas/serializers.py:158-173 (AchadoSerializer.validate_item) "
     "recusam apontar um registro para outro cliente — inclusive no caminho indireto pelo equipamento. "
     "A lacuna conhecida é o M2M de Rota (A-02), hoje sem vetor pelo Portal."),
    ("Portal reduzido a consulta, com a única escrita recortada campo a campo",
     "Decisão de 2026-09-21: apps/accounts/permissions.py:69-110 "
     "(InternoEditaClienteResponde) libera ao cliente só PATCH/PUT, nunca POST nem DELETE, e apenas na "
     "Ordem de Serviço. QUAIS campos ele pode tocar está em "
     "apps/osp/serializers.py:6-45 (CAMPOS_RETORNO_CLIENTE); o __init__ do serializer marca todo o resto "
     "como somente-leitura, então a trava não depende de o formulário esconder o campo. A FK de "
     "'quem executou' tem o queryset recortado para a própria equipe, fechando o vazamento de nome "
     "entre inquilinos que o campo abriria. 22 testes em apps/osp/test_retorno_cliente.py e "
     "apps/coletas/test_dashboard_cliente.py prendem a regra."),
    ("Nenhum handler detail=True busca objeto fora do queryset escopado",
     "Os 31 ViewSets/APIViews foram percorridos um a um: todo @action detail=True usa self.get_object(). "
     "Os três get_object_or_404 do projeto são seguros — laudos/views.py:34 está sob IsInterno (escopo "
     "global por desenho) e servicos/atividades.py:105-108 e :138 amarram o objeto ao carregamento já "
     "escopado."),
    ("Autenticação endurecida no fluxo que o frontend realmente usa",
     "apps/accounts/auth_views.py:143-206: cookie HttpOnly + SameSite=Lax com path restrito, CSRF "
     "obrigatório (authentication.py:11-21), sessão materializada em SessaoAutenticacao e conferida a cada "
     "request, TOTP com janela de 1 passo e anti-replay via ultimo_passo_usado (security.py:177-186), "
     "códigos de recuperação com hash, bloqueio após 8 tentativas, throttles por escopo, rotação e "
     "blacklist de refresh. O problema é o endpoint legado paralelo (A-06), não este fluxo."),
    ("Tokens de uso único e convites tratados corretamente",
     "apps/accounts/security.py:54-80: token opaco de 48 bytes, apenas o SHA-256 vai ao banco, invalidação "
     "dos anteriores ao emitir um novo, expiração curta e consumo único. Convites expiram em 72h e "
     "CriarConviteSerializer.validate (auth_serializers.py:131-138) impede o Master de um cliente convidar "
     "alguém com perfil interno — fechando a escalada de privilégio mais óbvia."),
    ("Nenhum segredo real no histórico do repositório",
     ".gitignore:7,9,10,18 cobre backend/.env, .env.prod, .env.*.local e frontend/.env.local. A varredura "
     "de git rev-list --all nos 138 commits não encontrou nenhum .env, .pem ou chave privada. Os composes "
     "de produção usam ${VAR} sem default, e os .example só contêm placeholders."),
    ("Bundle do frontend não carrega segredo",
     "frontend/Dockerfile:15-16 injeta apenas NEXT_PUBLIC_API_URL. frontend/src/lib/api.ts:1-4 documenta e "
     "implementa a decisão de nunca expor token ao JavaScript: a sessão vive só em cookie HttpOnly e o "
     "único valor que o JS manipula é o token CSRF."),
    ("Superfície de XSS praticamente nula",
     "Um único dangerouslySetInnerHTML em todo o projeto (frontend/src/app/layout.tsx:89), com constante "
     "literal estática definida na linha 83. Zero eval/new Function/document.write. Nenhum markdown ou HTML "
     "renderizado a partir de dado do usuário. No backend, zero mark_safe/format_html/render_to_string, "
     "TEMPLATES.DIRS vazio e e-mails em texto puro (security.py:87-148)."),
    ("Cabeçalhos e cookies de produção configurados com critério",
     "backend/config/settings.py:220-235 aplica HSTS (só quando há TLS de fato), nosniff, X-Frame-Options "
     "DENY e Referrer-Policy quando DEBUG=False. COOKIES_SECURE (:158) é opt-out consciente e documentado "
     "para o cenário de VPS por IP, com o padrão seguro."),
    ("Banco não exposto e testes de escopo já existentes",
     "docker-compose.prod.yml:28 deixa o PostgreSQL sem 'ports', só na rede interna do compose. "
     "apps/cadastros/test_escopo_cliente.py cobre 9 cenários de isolamento, incluindo "
     "test_cliente_sem_vinculo_nao_ve_nada e test_cliente_nao_acessa_equipamento_de_outro_por_id."),
]

PONTOS_FRACOS = [
    ("Existe uma porta de entrada paralela a toda a autenticação endurecida",
     "Todo o investimento em MFA, bloqueio de conta, sessão revogável e CSRF fica sem efeito enquanto "
     "/api/auth/login/ continuar publicado. É o único achado crítico — e o de correção mais barata: duas "
     "linhas de urls.py."),
    ("O isolamento depende de o desenvolvedor lembrar de declarar o filtro, em quatro cópias diferentes",
     "Não há RLS nem middleware de tenant: cada ViewSet precisa declarar campo_cliente ou chamar "
     "escopo_cliente à mão, e o helper foi copiado quatro vezes com semânticas divergentes. A-01 e A-04 são "
     "consequência direta disso. Um esquecimento não quebra nada visivelmente — só vaza."),
    ("A fronteira de inquilino para de existir na camada de arquivos",
     "O Django protege as linhas do banco; o Nginx entrega as imagens. Evidências técnicas e assinaturas "
     "digitais ficam fora de qualquer controle de acesso (A-03)."),
    ("Defaults de desenvolvimento são seguros por acaso, não por desenho",
     "SECRET_KEY, DEBUG e ALLOWED_HOSTS têm default permissivo e nenhuma checagem de boot recusa esses "
     "valores em produção. O acerto atual depende de o operador não esquecer uma variável (A-07)."),
    ("Guardas de escrita cobrem ForeignKey, mas não relações ManyToMany",
     "O padrão impedir_cross_tenant só inspeciona o primeiro segmento do caminho ORM; qualquer M2M passa "
     "livre. Hoje isso atinge Rota.equipamentos (A-02), e o mesmo padrão se repetiria em qualquer M2M novo."),
    ("A superfície de escrita do Portal já mudou duas vezes em três dias",
     "Só leitura até 18/09; parque inteiro liberado ao Master do cliente em 18-19/09; de volta a consulta "
     "em 21/09. A-02 era ALTA e virou BAIXA só por causa dessa última virada — nada no código impede a "
     "próxima. É o argumento mais forte a favor do teste de fumaça de autorização (P3): a regra precisa "
     "estar presa por teste, não por comentário."),
]

RECOMENDACOES = [
    ("P1", "Remover /api/auth/login/ e /api/auth/refresh/ de config/urls.py", "A-06",
     "Fecha o único achado crítico. O frontend não usa essas rotas; é uma remoção de 2 linhas. "
     "Depois da remoção, revogar as sessões existentes e forçar novo login."),
    ("P1", "Colocar /media/ atrás de autenticação e escopo de cliente", "A-03",
     "View Django + X-Accel-Redirect (ou auth_request no Nginx), marcando a location como internal. "
     "Trocar os nomes de arquivo por UUID e reativar o access_log."),
    ("P3", "Validar o M2M de Rota.equipamentos na escrita", "A-02",
     "Deixou de ser P1 em 21/09, quando o Portal voltou a ser somente-consulta e o vetor sumiu. Recusar "
     "equipamento cujo dono não seja o cliente DA ROTA (vale para interno também) em "
     "RotaSerializer.validate e, em defesa em profundidade, filtrar por cliente em "
     "CarregamentoSerializer.create."),
    ("P2", "Remover os defaults de SECRET_KEY/DEBUG/ALLOWED_HOSTS e adicionar checagem de boot", "A-07",
     "Um django.core.checks que falhe com DEBUG=False + segredo conhecido. Tirar os literais do "
     "docker-compose.yml, travar seed_demo fora de DEBUG e rotacionar a chave de produção."),
    ("P2", "Unificar o filtro de tenant num único helper fail-closed em apps/core", "A-01, A-04",
     "Eliminar as quatro cópias. Corrigir o fail-open de reports.py:29-33 no mesmo passo e cobrir com "
     "teste o caso do usuário cliente sem vínculo."),
    ("P3", "Restringir /api/empresas/ a usuários internos", "A-05",
     "Trocar a permission_class para IsInterno, alinhando o backend ao gate do front."),
    ("✓", "Reconciliar a matriz de permissões do frontend com a do backend", "—",
     "FEITO em 21/09: a divergência (osp:criar, osp:mudar-status e operacional:criar mais restritos no "
     "front do que no backend) deixou de existir quando o Portal voltou a ser somente-consulta. "
     "frontend/src/lib/permissions.ts:8-30 registra a decisão e a habilidade nova osp:responder."),
    ("P3", "Adicionar um teste de fumaça de autorização ao pipeline", "—",
     "Um teste parametrizado que, para cada rota registrada nos routers, autentique como cliente de outro "
     "tenant e exija 403/404. Transforma o padrão “lembre de declarar campo_cliente” numa garantia "
     "verificada."),
]

NAO_APLICAVEL = [
    ("5. Inputs sem tratamento (XSS)",
     "Categoria verificada e SEM ACHADOS — nenhuma constatação foi forçada. O projeto não renderiza "
     "markdown nem HTML vindo do usuário, não há lib de sanitização no package.json porque não existe "
     "ponto que precise de uma, e o único dangerouslySetInnerHTML usa constante literal estática. "
     "Detalhes na tabela de verificação abaixo."),
    ("RLS / Supabase",
     "Não se aplica: o projeto não usa Supabase nem Row Level Security do PostgreSQL. O equivalente na "
     "stack — filtro manual por cliente no ORM — foi auditado em profundidade na categoria 1."),
    ("CI / Helm / Terraform",
     "Não se aplica: o repositório não tem .github/workflows, charts Helm nem módulos Terraform. O deploy "
     "é Docker Compose + Nginx, ambos auditados."),
]

VERIFICADO_XSS = [
    ("frontend/src/app/layout.tsx:83,89", "dangerouslySetInnerHTML",
     "OK — __html recebe INICIAR_TEMA, constante literal sem interpolação (linha 83)."),
    ("frontend/src/app/carta/[id]/carta-client.tsx:72-73", "innerHTML",
     "OK — round-trip de DOM já renderizado pelo React para o paged.js; React escapa na escrita e a "
     "serialização preserva o escape."),
    ("frontend/src/app/imprimir/[id]/imprimir-client.tsx:80-81", "innerHTML",
     "OK — mesmo padrão do carta-client."),
    ("frontend/src/app/portal/page.tsx:244", "href com dado do servidor",
     "OK — passa por destinoNoPortal (permissions.ts:254-272), que só aceita prefixos de uma allowlist e "
     "cai em “/portal” fora dela."),
    ("frontend/src/features/alertas/lista-alertas.tsx:102", "router.push(n.url) cru p/ interno",
     "OK — Notificacao.url só é escrito por literais do servidor (notificacoes/signals.py:28,49) e o "
     "ViewSet é somente-leitura (notificacoes/views.py:11)."),
    ("frontend/src — grep global", "eval / new Function / document.write",
     "OK — zero ocorrências."),
    ("backend/apps — grep global", "mark_safe / format_html / render_to_string / templates .html",
     "OK — zero ocorrências; TEMPLATES.DIRS vazio (settings.py:84)."),
    ("backend/apps/accounts/security.py:87-148", "HTML em e-mail",
     "OK — send_mail com corpo em texto puro; nenhuma interpolação em HTML."),
    ("backend/apps/relatorios/views.py:80-81", "Content-Disposition com dado de entrada",
     "OK — “key” é validada contra o dicionário REPORTS antes de entrar no nome do arquivo (linhas 57-59)."),
    ("backend/apps/coletas/views.py:629-635", "Content-Disposition do carta-docx",
     "OK — nome sanitizado caractere a caractere na linha 630."),
]
