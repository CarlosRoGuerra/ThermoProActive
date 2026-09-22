# Issues de segurança — ThermoProActive / Pred Ativos

Geradas a partir da auditoria de 20 de setembro de 2026 (revisão cac2513 + ajustes de 21/09). Uma issue por bloco.

--- ISSUE 1 ---

# [Segurança] Endpoints JWT legados /api/auth/login/ e /api/auth/refresh/ contornam MFA, bloqueio de conta e revogação de sessão

**Labels sugeridas:** `security`, `severidade:crítica`

**Achado(s) da auditoria:** A-06

---

**Problema**

TokenObtainPairView do SimpleJWT declara permission_classes = () e não define throttle_classes; como REST_FRAMEWORK não define DEFAULT_THROTTLE_CLASSES (settings.py:135-140 define apenas as RATES), a rota fica pública e sem limite de tentativas. LoginSerializer (accounts/serializers.py:70-78) apenas chama super().validate() e anexa o usuário — não replica NENHUMA das travas do fluxo endurecido LoginContextualView (auth_views.py:143-206). O token emitido não carrega a claim 'sid', e CookieJWTAuthentication.authenticate (authentication.py:26-28) devolve super().authenticate(request) assim que há cabeçalho Authorization, saindo ANTES do enforce_csrf e da consulta a SessaoAutenticacao das linhas 45-52. O resultado é uma família de tokens invisível para todo o subsistema de sessões.

O endpoint contorna, uma a uma, as seguintes proteções:

- MFA/TOTP obrigatório (auth_views.py:178-194)
- Bloqueio após 8 tentativas, campo bloqueado_ate (auth_views.py:151-156 e 169-171)
- Estado da conta SUSPENDED/BLOCKED/PENDING (auth_serializers.py:61-62)
- Separação portal × admin (auth_views.py:173-176)
- Throttle de 10 logins/minuto (auth_views.py:145 + throttles.py:4-5)
- CSRF e a checagem de sessão viva (authentication.py:45-52)
- Logout, “encerrar outras sessões” e a revogação automática na troca/reset de senha (auth_views.py:249-258, 475-479 e 309)

**Evidência**

Arquivos: `backend/config/urls.py:16-17`, `backend/apps/accounts/views.py:26-29`

```python
backend/config/urls.py
16:    path("api/auth/login/",   LoginView.as_view(),        name="login"),
17:    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

backend/apps/accounts/views.py
26: class LoginView(TokenObtainPairView):
29:     serializer_class = LoginSerializer   # só acrescenta o usuário ao payload
```

Prova de conceito reproduzida (`manage.py test` com `APIClient`):

```text
Teste executado contra a API (django test + APIClient):
  HARDENED /api/auth/admin/login/ -> 428  (exige código MFA)
  LEGACY   /api/auth/login/       -> 200  ['access','refresh','user']
  conta SUSPENSA + BLOQUEADA: hardened -> 429 | legado -> 200
  Bearer legado em /api/auth/me/  -> 200 alvo@thermoproactive.com
  sessoes registradas no banco: 0
  apos troca de senha + revogacao de TODAS as sessoes, Bearer legado -> 200
```

**Impacto**

Qualquer pessoa com um par e-mail/senha válido entra sem o segundo fator, sem limite de tentativas para adivinhar a senha e sem que o bloqueio automático de conta se aplique. Uma vez dentro, o token sobrevive ao logout, ao “encerrar outras sessões” e à própria redefinição de senha — e /api/auth/refresh/ o renova indefinidamente (ROTATE_REFRESH_TOKENS com 7 dias de vida). É a rota de persistência ideal depois de um vazamento de credencial.

**Sugestão de correção**

Remover as duas linhas de config/urls.py e a classe LoginView de accounts/views.py: o frontend nunca as usa (frontend/src/lib/api.ts:167 chama /auth/{area}/login/ e :56 chama /auth/session/refresh/). Se um token Bearer for necessário para integração máquina-a-máquina, criar um endpoint próprio que emita 'sid', grave SessaoAutenticacao e aplique MFA + throttle.

**Critérios de aceite**

- [ ] path('api/auth/login/') e path('api/auth/refresh/') removidos de backend/config/urls.py
- [ ] Classe LoginView e LoginSerializer removidas (ou reescritas com sid + MFA + throttle)
- [ ] Teste automatizado: POST /api/auth/login/ devolve 404
- [ ] Teste automatizado: conta com MFA ativo não obtém token por nenhuma rota sem o código TOTP
- [ ] Teste automatizado: token obtido antes de _revogar_todas() devolve 401 depois dela
- [ ] Sessões existentes revogadas e novo login forçado após o deploy da correção

--- FIM ISSUE 1 ---

--- ISSUE 2 ---

# [Segurança] /media/ é servido sem autenticação e expõe evidências técnicas e assinaturas digitais

**Labels sugeridas:** `security`, `severidade:alta`

**Achado(s) da auditoria:** A-03

---

**Problema**

Todo o esforço de multi-tenant do projeto vive na camada DRF; os arquivos, porém, saem pelo Nginx direto do volume, sem passar pelo Django — não há auth_request, nem X-Accel-Redirect, nem token assinado na URL. O nome do arquivo é o nome original enviado pelo usuário (FileSystemStorage só acrescenta sufixo em caso de colisão), então os caminhos são curtos e enumeráveis: /media/achados/IMG_0042.jpg, /media/assinaturas/joao.png. O access_log off apaga até o rastro da tentativa. Vale nos dois composes de deploy e, em DEBUG, também no próprio Django (config/urls.py:33-34).

**Evidência**

Arquivos: `deploy/nginx/app.conf.template:61-65`, `deploy/nginx/app.http.conf:21-25`, `backend/apps/coletas/models.py:614`, `backend/apps/accounts/models.py:108-110`, `backend/apps/cadastros/models.py:355`, `backend/apps/cadastros/models.py:418`, `backend/config/urls.py:33-34`

```python
deploy/nginx/app.conf.template
61:    location /media/ {
62:        alias /var/www/media/;
63:        access_log off;
64:        expires 30d;
65:    }

backend/apps/coletas/models.py
614:    arquivo = models.ImageField("Arquivo", upload_to="achados/")

backend/apps/accounts/models.py
108:    assinatura_digital = models.ImageField(
109:        "Assinatura digital", upload_to="assinaturas/", null=True, blank=True
110:    )
```

**Impacto**

Vazamento cross-tenant sem sequer precisar de conta: as fotos de termografia e vibração são a evidência técnica das anomalias de cada cliente (o que quebrou, onde, em que ativo), e as placas de identificação trazem fabricante, modelo e número de série do parque alheio. Pior, /media/assinaturas/ guarda a imagem da assinatura do responsável técnico usada para assinar laudos — baixá-la permite forjar um laudo com aparência legítima.

**Sugestão de correção**

Servir mídia por uma view Django autenticada que reaplique escopo_cliente sobre o dono do arquivo e delegue a entrega ao Nginx via X-Accel-Redirect (location internal), ou usar auth_request apontando para um endpoint de autorização. Em paralelo, trocar o nome do arquivo por UUID (upload_to com função) para eliminar a enumeração, e reativar o access_log.

**Critérios de aceite**

- [ ] GET /media/achados/<arquivo> sem cookie de sessão devolve 401/403
- [ ] GET /media/achados/<arquivo> autenticado como cliente de OUTRO tenant devolve 403/404
- [ ] location /media/ marcada como 'internal' no Nginx (ou protegida por auth_request)
- [ ] upload_to de achados, assinaturas e placas gera nome aleatório (UUID)
- [ ] access_log reativado para /media/

--- FIM ISSUE 2 ---

--- ISSUE 3 ---

# [Segurança] Rota aceita equipamento de outro cliente e vaza o parque alheio na folha de campo

**Labels sugeridas:** `security`, `severidade:alta`

**Achado(s) da auditoria:** A-02

---

**Problema**

A guarda de escrita valida apenas campo_cliente.partition('__')[0], isto é, o campo 'cliente' da própria Rota. O ManyToMany 'equipamentos' (cadastros/models.py:735) nunca é conferido. Quando o Portal escrevia em /api/rotas/, isso era uma quebra direta de inquilino: o Master de um cliente gravava IDs de equipamentos de qualquer outro, e o vazamento se materializava no carregamento da rota — CarregamentoSerializer.create copia todos os equipamentos para ItemInspecao sem checar o dono, e o Carregamento resultante pertence a quem montou a rota, então /api/itens-inspecao/ devolvia o item alheio como se fosse dele.

**Evidência**

Arquivos: `backend/apps/cadastros/views.py:117-139`, `backend/apps/cadastros/views.py:325-331`, `backend/apps/cadastros/models.py:735`, `backend/apps/coletas/serializers.py:426-434`

```python
backend/apps/cadastros/views.py  (_impedir_apontar_para_outro_cliente)
129:        primeiro_campo, _, resto = self.campo_cliente.partition("__")
130:        if primeiro_campo not in validated_data:
131:            return   # <- só o 1o campo do caminho é validado

317: class RotaViewSet(BaseCadastroViewSet):
318:     campo_cliente = "cliente"     # <- o M2M equipamentos fica de fora
     (a permissão herdada passou a ser InternoEditaClienteVisualiza em 21/09)

backend/apps/coletas/serializers.py  (CarregamentoSerializer.create)
428:            equipamentos = carregamento.rota.equipamentos.order_by(...)
431:            ItemInspecao.objects.bulk_create([
432:                ItemInspecao(carregamento=carregamento, equipamento=eq, ordem=i)
433:                for i, eq in enumerate(equipamentos, start=1)
434:            ])   # <- copia TODOS, sem checar de quem são
```

Prova de conceito reproduzida (`manage.py test` com `APIClient`):

```text
PoC de 20/09, quando o Portal ainda escrevia em /api/rotas/:
  POST /api/rotas/ com equipamento do cliente B  -> 201
  interno carrega a rota                         -> 201
  Master do cliente A le /api/itens-inspecao/    -> 200
     VAZOU: TAG-SECRETA-B-001 | Turbina confidencial da vitima |
            Area secreta B / Setor secreto B

Mesmo POST apos a mudanca de 21/09 (apps/osp/test_retorno_cliente.py):
  POST /api/rotas/ como Master do cliente       -> 403
```

**Condições de explorabilidade**

O VETOR FOI FECHADO em 21/09/2026: RotaViewSet voltou a InternoEditaClienteVisualiza, e nenhum perfil de cliente escreve mais em /api/rotas/ — coberto por apps/osp/test_retorno_cliente.py::PortalSoConsulta::test_nao_cria_rota. O que permanece é a LACUNA ESTRUTURAL: a guarda continua cega a relações ManyToMany, e CarregamentoSerializer.create continua copiando equipamentos sem conferir o dono. Hoje só a equipe interna alcança esse caminho, e ela tem escopo global por desenho — então não há quebra de inquilino, só risco de contaminação de dado por engano. Se a escrita do cliente voltar a ser liberada, como já foi em 18/09, o achado volta a ser ALTA sem nenhum aviso.

**Impacto**

Com o Portal somente-consulta, o impacto residual é de integridade e não de confidencialidade: um analista interno pode, por engano, montar uma rota do Cliente A com um equipamento do Cliente B, contaminando a folha de campo, os relatórios e o indicador de cobertura de ativos. O risco relevante é de regressão — o código não impede o cenário grave, apenas deixou de oferecer a porta por onde se chegava a ele.

**Sugestão de correção**

Validar o M2M na escrita, agora pelo dono da ROTA e não pelo usuário: em RotaSerializer.validate, recusar qualquer equipamento cujo setor__area__cliente_id seja diferente do cliente da rota — vale para interno e para cliente, e é exatamente a checagem que servicos/atividades.py:52-53 já faz no fluxo corretivo. Em defesa em profundidade, replicar o filtro em CarregamentoSerializer.create.

**Critérios de aceite**

- [ ] PATCH/POST /api/rotas/ com equipamento de outro cliente devolve 400, inclusive para interno
- [ ] CarregamentoSerializer.create ignora (ou recusa) equipamento fora do cliente do carregamento
- [ ] Teste de regressão em apps/cadastros/test_escopo_cliente.py cobrindo o M2M de Rota
- [ ] Auditoria única dos demais M2M do projeto em busca do mesmo padrão

--- FIM ISSUE 3 ---

--- ISSUE 4 ---

# [Segurança] Segredos padrão embutidos no código, sem validação de startup que os recuse

**Labels sugeridas:** `security`, `severidade:alta`

**Achado(s) da auditoria:** A-07

---

**Problema**

django-environ só usa o default quando a variável está AUSENTE — e é exatamente esse o caso perigoso: subir em produção sem SECRET_KEY não quebra nada, o Django simplesmente assume a string pública do repositório. Não há nenhum django.core.checks nem assert de boot que recuse o valor conhecido, e o mesmo vale para DEBUG=True e ALLOWED_HOSTS=['*'] como defaults. O impacto é amplificado porque accounts/security.py:151-153 deriva a chave Fernet que cifra os segredos TOTP do MFA a partir do SECRET_KEY, e security.py:30-31 usa o mesmo valor como chave HMAC dos ip_hash. Por fim, o CMD padrão da imagem backend roda seed_demo, que cria admin@thermoproactive.com com is_superuser=True e senha 'thermo123'.

**Evidência**

Arquivos: `backend/config/settings.py:16-18`, `backend/config/settings.py:33`, `docker-compose.yml:18`, `docker-compose.yml:31`, `docker-compose.yml:34`, `backend/apps/core/management/commands/seed_demo.py:69-72`, `backend/apps/core/management/commands/seed_demo.py:88`, `backend/Dockerfile:25`, `backend/apps/accounts/security.py:151-153`

```python
backend/config/settings.py
16:    DEBUG=(bool, True),
17:    SECRET_KEY=(str, "dev-insecure-change-me-em-producao"),
18:    ALLOWED_HOSTS=(list, ["*"]),
33: SECRET_KEY = env("SECRET_KEY")   # nunca levanta erro: o default cobre a ausência

docker-compose.yml
18:      POSTGRES_PASSWORD: thermo
31:      SECRET_KEY: docker-dev-secret-troque-em-producao
34:      DATABASE_URL: postgres://thermo:thermo@db:5432/thermoproactive

backend/apps/core/management/commands/seed_demo.py
69:            "admin@thermoproactive.com": (
71:                {"is_staff": True, "is_superuser": True, "nivel": "MASTER"},
88:                user.set_password("thermo123")

backend/Dockerfile
25: CMD [... "&& { python manage.py seed_demo || echo 'seed_demo ignorado'; } && exec gunicorn ..."]
```

**Condições de explorabilidade**

Os composes de produção (docker-compose.prod.yml:44-47 e docker-compose.http.yml:43-46) sobrescrevem o command e NÃO rodam seed_demo, e usam ${POSTGRES_PASSWORD} sem default — o caminho documentado de deploy está correto. O risco se concretiza quando alguém sobe a imagem fora desses composes, usa o docker-compose.yml de desenvolvimento num host alcançável, ou esquece SECRET_KEY no .env.prod.

**Impacto**

Com o SECRET_KEY conhecido um atacante forja tokens JWT de qualquer usuário, assina cookies de sessão, falsifica tokens CSRF, decifra os segredos TOTP de MFA guardados no banco e reverte os ip_hash do log de segurança. Com 'thermo123' presente, há um superusuário Django com senha pública; com DEBUG=True, qualquer erro devolve stack trace e settings.

**Sugestão de correção**

1) Remover o default de SECRET_KEY (env('SECRET_KEY') sem default levanta ImproperlyConfigured) ou adicionar um django.core.checks que falhe o boot quando DEBUG=False e o valor for um dos conhecidos. 2) DEBUG default False e ALLOWED_HOSTS sem '*'. 3) Trocar os valores literais do docker-compose.yml por ${VAR:?erro} lendo um .env local. 4) Fazer seed_demo recusar rodar com DEBUG=False e sortear a senha, imprimindo-a no log. 5) Derivar a chave Fernet do MFA de uma variável própria (MFA_ENCRYPTION_KEY), desacoplando-a do SECRET_KEY.

**Critérios de aceite**

- [ ] Boot com DEBUG=False e SECRET_KEY ausente/default falha com mensagem clara
- [ ] settings.py: DEBUG default False e ALLOWED_HOSTS sem '*'
- [ ] docker-compose.yml sem senha ou chave literal (usa ${VAR:?} + .env)
- [ ] seed_demo recusa rodar com DEBUG=False e não usa senha fixa
- [ ] Segredo do MFA derivado de variável própria, não do SECRET_KEY
- [ ] Chave de produção rotacionada depois da correção (a antiga está no repositório)

--- FIM ISSUE 4 ---

--- ISSUE 5 ---

# [Segurança] _escopo() do motor de relatórios falha aberto e entrega dados de todos os clientes

**Labels sugeridas:** `security`, `severidade:média`

**Achado(s) da auditoria:** A-01

---

**Problema**

O projeto tem três implementações do mesmo filtro de tenant e duas delas documentam explicitamente a falha fechada (“Falha fechada: cliente sem cliente_id não vê nada, em vez de cair no qs inteiro sem filtro”). A do módulo relatorios não seguiu a regra: o “and user.cliente_id” transforma a ausência de vínculo em ausência de filtro. Atinge os cinco relatórios liberados ao cliente (técnico, gerencial, equipamento, falhas, histórico — reports.py:244-250), em JSON, CSV, XLSX e PDF, via GET /api/relatorios/<key>/?formato=…

**Evidência**

Arquivos: `backend/apps/relatorios/reports.py:29-33`, `backend/apps/relatorios/reports.py:243-251`, `backend/apps/relatorios/views.py:56-82`

```python
backend/apps/relatorios/reports.py
29: def _escopo(qs, user, campo_cliente):
30:     """Perfis cliente: restringe ao próprio cliente."""
31:     if user.is_cliente and user.cliente_id:
32:         return qs.filter(**{campo_cliente: user.cliente_id})
33:     return qs          # <- FAIL-OPEN: cliente sem vínculo recebe TUDO

comparar com backend/apps/coletas/views.py:49-53  (fail-closed, correto)
49:     if user.is_cliente:
50:         if not user.cliente_id:
51:             return qs.none()
52:         return qs.filter(**{campo_cliente: user.cliente_id})
```

Prova de conceito reproduzida (`manage.py test` com `APIClient`):

```text
Teste executado contra a API (django test + APIClient), usuario CLIENTE_PCM sem vinculo:
  cliente_id do usuario: None
  _escopo(reports.py) devolveu 1 clientes -> ['Cliente B (vitima)']
  GET /api/relatorios/gerencial/ -> 200 linhas: [['Cliente B (vitima)', 0, 0, 0, '0%', 0]]
```

**Condições de explorabilidade**

Exige uma conta de perfil CLIENTE_* com o campo cliente vazio. Não é um estado que o atacante produza sozinho, mas é alcançável: User.cliente é null=True (accounts/models.py:90-98) e o campo é editável por PATCH /api/usuarios/ (UserWriteSerializer, serializers.py:47-51), então basta um erro de cadastro ou a desvinculação de um cliente para a conta virar uma chave-mestra silenciosa.

**Impacto**

Um único usuário mal cadastrado enxerga e EXPORTA o parque, as medições, as anomalias, as ordens de serviço e o histórico de manutenção de todos os clientes da plataforma, em planilha pronta. Como o próprio módulo oferece download em CSV/XLSX/PDF, o vazamento é de base inteira, não de registro isolado.

**Sugestão de correção**

Fazer _escopo devolver qs.none() quando user.is_cliente e não há cliente_id, alinhando com coletas/views.py:49-53. Melhor ainda: extrair as três cópias para uma única função em apps/core e importá-la nos três módulos, para a regra não poder divergir de novo.

**Critérios de aceite**

- [ ] _escopo devolve queryset vazio para usuário cliente sem cliente_id
- [ ] Teste: usuário CLIENTE_* sem vínculo recebe 0 linhas em cada um dos 5 relatórios abertos
- [ ] Filtro de tenant unificado num único helper compartilhado
- [ ] apps/servicos/views.py e apps/servicos/atividades.py migrados para o mesmo helper (ver A-04)

--- FIM ISSUE 5 ---

--- ISSUE 6 ---

# [Segurança] Higiene de controle de acesso: filtro de tenant duplicado e /api/empresas/ legível por qualquer conta

**Labels sugeridas:** `security`, `severidade:baixa`

**Achado(s) da auditoria:** A-04, A-05

> Agrupa dois achados de baixa severidade e mesmo tema (permissão/escopo declarados fora do padrão do projeto). Nenhum dos dois é explorável para vazamento entre inquilinos hoje; ambos são dívida técnica de segurança que barateia a próxima regressão.

---

### A-04 — Duas cópias do filtro de tenant divergem do padrão fail-closed

**Problema**

Ao contrário de A-01, aqui NÃO há vazamento hoje: cliente_id None vira “cliente_id IS NULL” e ServicoCampo.cliente (servicos/models.py:48) e Carregamento.cliente são NOT NULL, então o resultado é vazio por acidente, não por desenho. O risco é de manutenção: qualquer futura coluna de tenant que aceite NULL, ou a reutilização deste helper com outro campo_cliente, transforma o acidente em vazamento.

**Evidência**

Arquivos: `backend/apps/servicos/views.py:26-30`, `backend/apps/servicos/atividades.py:96-97`

```python
backend/apps/servicos/views.py
26: def escopo_cliente(qs, user, campo_cliente="cliente"):
27:     """Perfis cliente só enxergam os próprios serviços (Portal - item 2.7)."""
28:     if user.is_cliente:
29:         return qs.filter(**{campo_cliente: user.cliente_id})   # sem guarda de None
30:     return qs

backend/apps/servicos/atividades.py
96:         if self.request.user.is_cliente:
97:             qs = qs.filter(cliente_id=self.request.user.cliente_id)
```

**Impacto**

Nenhum impacto explorável no código atual. Dívida técnica de segurança: a quarta cópia da mesma regra, com semântica diferente das outras três, aumenta a chance de a próxima alteração repetir o erro de A-01.

**Sugestão de correção**

Importar o helper único (ver A-01) em apps/servicos/views.py e apps/servicos/atividades.py e apagar as cópias locais.

---

### A-05 — Tela de Prestadores é escondida por papel no front, mas /api/empresas/ é legível por qualquer conta

**Problema**

A rota /prestadores só aparece para usuário interno, mas ela é apenas um rótulo: a API por trás é /api/empresas/, cujo ViewSet herda a permissão padrão de BaseCadastroViewSet, que libera leitura a qualquer autenticado, e não declara campo_cliente. A escrita está corretamente bloqueada (PATCH/POST/DELETE exigem perfil interno).

**Evidência**

Arquivos: `frontend/src/lib/permissions.ts:142-143`, `frontend/src/lib/permissions.ts:220`, `frontend/src/app/(admin)/prestadores/prestador-form.tsx:190-192`, `backend/apps/cadastros/views.py:142-145`, `backend/apps/accounts/permissions.py:55-66`

```python
frontend/src/lib/permissions.ts
142:     case "prestadores:gerenciar":
143:       return interno;
220:   { prefixo: "/prestadores", exige: "prestadores:gerenciar" },

frontend/src/app/(admin)/prestadores/prestador-form.tsx
190:         await api(`/empresas/${prestadorId}/`, { method: "PATCH", body });

backend/apps/cadastros/views.py
142: class EmpresaViewSet(BaseCadastroViewSet):   # herda InternoEditaClienteVisualiza
143:     queryset = Empresa.objects.ativos()      # campo_cliente = None (sem escopo)

backend/apps/accounts/permissions.py  (InternoEditaClienteVisualiza)
59:         if request.method in SAFE_METHODS:
60:             return True            # <- qualquer autenticado LÊ
```

Prova de conceito reproduzida (`manage.py test` com `APIClient`):

```text
Teste executado contra a API, usuario CLIENTE_MANUT / JUNIOR do Portal:
  GET  /api/empresas/ -> 200
     {'nome': 'ThermoProActive Servicos Ltda', 'cnpj': '39.923.567/0001-75',
      'email': 'financeiro@thermoproactive.com', 'telefone': '(19) 99999-0000',
      'contato_gestor': 'Diretor Tecnico'}
  POST /api/empresas/ (escrita) -> 403   (corretamente bloqueado)
```

**Impacto**

Exposição limitada: Empresa é o cadastro da própria CONTRATADA (razão social, CNPJ, inscrição estadual, endereço, e-mail, telefone e nome do gestor), dados que já aparecem no timbre dos relatórios entregues. Não há dado de outro inquilino aqui. Vale corrigir porque o endpoint também alimenta o cabeçalho de laudos e pode crescer com campos sensíveis.

**Sugestão de correção**

Trocar a permission_class de EmpresaViewSet para IsInterno (leitura e escrita), alinhando com o gate 'prestadores:gerenciar' do front. Se o Portal precisar do nome/logo do prestador para o cabeçalho, expor um endpoint público mínimo com apenas esses campos.

---

**Critérios de aceite**

_A-04_
- [ ] apps/servicos não define mais escopo_cliente próprio
- [ ] AtividadeCorretivaViewSet.get_queryset usa o helper compartilhado
- [ ] Teste: usuário cliente sem vínculo recebe lista vazia em /api/servicos/ e /api/atividades-corretivas/

_A-05_
- [ ] GET /api/empresas/ como usuário CLIENTE_* devolve 403
- [ ] Cabeçalho de relatório no Portal continua funcionando (endpoint dedicado ou dado já embutido)


--- FIM ISSUE 6 ---

