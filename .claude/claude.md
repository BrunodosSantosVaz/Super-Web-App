# WebApps Manager - Documentação Técnica para Claude Code

## Informações Gerais

- **Nome**: WebApps Manager
- **Versão**: 1.0.0
- **Autor**: Bruno Vaz
- **Licença**: GPL-3.0-or-later
- **App ID**: br.com.infinity.webapps
- **Linguagem**: Python 3.11+
- **Stack**: GTK 4 (4.12+) + libadwaita 1.5+ + WebKitGTK 6.0+

## Estrutura do Projeto

```
/home/brunovaz/projetos/Super Web App/webapps-manager/
├── app/
│   ├── main.py                    - Entry point, CLI parser
│   ├── application.py             - WebAppsApplication (Adw.Application)
│   ├── standalone_webapp.py       - Webapp isolado em processo separado
│   │
│   ├── ui/
│   │   ├── main_window.py         - Janela principal do gerenciador
│   │   ├── webapp_window.py       - Janela de cada webapp (com TabView/TabBar)
│   │   ├── add_dialog.py          - Diálogo criar/editar webapp (linha 179-187: switch "Ativar Abas")
│   │   ├── preferences_dialog.py  - Preferências globais
│   │   └── tray.py               - System tray integration
│   │
│   ├── core/
│   │   ├── webapp_manager.py      - Gerenciador central de webapps
│   │   ├── desktop_integration.py - .desktop files, autostart
│   │   └── icon_fetcher.py        - Download de favicons
│   │
│   ├── webengine/
│   │   ├── webview_manager.py     - Criação e configuração de WebViews
│   │   ├── profile_manager.py     - Perfis isolados (WebKit.NetworkSession)
│   │   ├── popup_handler.py       - Gerenciamento de popups
│   │   └── security_handler.py    - Permissões e segurança
│   │
│   ├── data/
│   │   ├── database.py            - SQLite operations (linha 93: allow_tabs column)
│   │   ├── models.py              - Dataclasses (linha 77: allow_tabs field)
│   │   └── migrations.py          - Database migrations
│   │
│   └── utils/
│       ├── i18n.py                - Sistema de traduções pt/en (linha 52, 120)
│       ├── logger.py              - Logging configurável
│       └── xdg.py                 - XDG directory handling
│
├── requirements.txt               - PyGObject, requests, bs4, Pillow, etc.
└── pyproject.toml                 - Black, mypy, flake8, isort, pytest config
```

## Componentes Principais

### 1. Application (application.py)

**Classe**: `WebAppsApplication(Adw.Application)`

- **do_startup()**: Inicializa database, ProfileManager, WebAppManager
- **do_activate()**: Cria e exibe MainWindow
- **do_shutdown()**: Limpeza de recursos

**CLI Arguments**:
- `--webapp <id>`: Abre webapp específico
- `--preferences`: Abre preferências
- `--show-main-window`: Força exibição da janela principal
- `--debug`: Ativa logs detalhados

### 1.5. TabManager (ui/tab_manager.py) **[NOVO - 2025-10-30]**

**Classe**: `TabManager`

Gerenciador completo de abas dinâmicas para webapps.

**Responsabilidades**:
- Criar/fechar abas dinamicamente
- Gerenciar múltiplos WebViews (um por aba)
- Controlar limite de 10 abas
- Atualizar títulos dinamicamente via `document.title`
- Exibir diálogos de limite em i18n

**Métodos Principais**:
- `create_new_tab(uri)`: Cria nova aba com WebView isolado
- `close_tab(page)`: Fecha aba (mantém pelo menos 1 aberta)
- `get_active_webview()`: Retorna WebView da aba ativa
- `can_create_tab()`: Verifica se pode criar mais abas (< 10)
- `_update_tab_widths()`: Log de mudanças (redimensionamento é nativo GTK)

**Sinais Conectados**:
- `close-page`: Gerencia fechamento de abas
- `page-attached`: Atualiza quando aba é adicionada
- `page-detached`: Cria nova se última aba foi removida
- `notify::title` (WebView): Atualiza título da aba
- `load-changed` (WebView): Gerencia estado de carregamento

### 2. WebAppWindow (ui/webapp_window.py)

**Estrutura Atual**:
```
Adw.ApplicationWindow
├── Adw.ToolbarView
│   ├── Header Bar (top)
│   │   ├── Navigation buttons (Back/Forward/Reload)
│   │   └── Title
│   ├── TabBar (se allow_tabs) ← AQUI PRECISA IMPLEMENTAR TABS DINÂMICAS
│   └── TabView (se allow_tabs) ← AQUI PRECISA IMPLEMENTAR TABS DINÂMICAS
│       └── WebView content
└── Optional: System Tray Icon
```

**Linhas 161-172**: Criação do TabView/TabBar se `allow_tabs = True`
**IMPORTANTE**: Atualmente cria estrutura básica mas não implementa funcionalidade completa de abas!

### 3. Sistema de Abas Atual (INCOMPLETO)

**Cadeia Completa**:
1. **UI**: `add_dialog.py:179-187` - Adw.SwitchRow "Ativar Abas"
2. **i18n**: `i18n.py:52,120` - Traduções pt/en
3. **Model**: `models.py:77` - `allow_tabs: bool = True`
4. **Database**: `database.py:93` - `allow_tabs BOOLEAN DEFAULT 1`
5. **Window**: `webapp_window.py:161-172` - Cria TabView/TabBar

**O QUE FALTA IMPLEMENTAR**:
- Sistema completo de tabs dinâmicas (criar, fechar, alternar)
- Múltiplos WebViews (um por aba)
- Atualização dinâmica de títulos (document.title)
- Botão "+" para nova aba
- Botão "X" para fechar aba
- Limite de 10 abas
- Redimensionamento automático
- Mensagens i18n para limite

### 4. WebViewManager (webengine/webview_manager.py)

**Função Principal**: `create_webview(profile: WebKit.NetworkSession, webapp: WebApp) -> WebKit.WebView`

Responsabilidades:
- Cria WebView com perfil isolado
- Aplica configurações de segurança
- Conecta sinais: load-changed, notify::title, notify::favicon
- Configurações: JavaScript, storage, media, notifications

### 5. ProfileManager (webengine/profile_manager.py)

**Isolamento de Perfis**:
- Cada webapp tem `WebKit.NetworkSession` isolado
- Diretório: `~/.local/share/br.com.infinity.webapps/profiles/<webapp-id>/`
- Storage isolado: cookies, cache, localStorage, IndexedDB

### 6. Sistema i18n (utils/i18n.py)

**Estrutura**:
```python
translations = {
    "pt": {
        "tabs": {
            "label": "Permitir múltiplas abas",
            "description": "Permite abrir várias abas do mesmo aplicativo"
        }
    },
    "en": {
        "tabs": {
            "label": "Allow multiple tabs",
            "description": "Allows opening multiple tabs of the same application"
        }
    }
}
```

**Funções**:
- `gettext(key)`: Traduz chave
- `set_language(lang)`: Muda idioma
- `subscribe(callback)`: Observer pattern para mudanças

**PRECISA ADICIONAR**:
```python
"tabs": {
    "limitReached": {
        "pt": "Limite máximo de abas atingido (10). Feche uma aba para abrir outra.",
        "en": "Maximum tab limit reached (10). Please close a tab to open a new one."
    }
}
```

## Banco de Dados

**Localização**: `~/.config/br.com.infinity.webapps/webapps.db`

**Tabela `webapps`**:
```sql
CREATE TABLE webapps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    icon_path TEXT,
    created_at TEXT,
    updated_at TEXT
)
```

**Tabela `webapp_settings`**:
```sql
CREATE TABLE webapp_settings (
    webapp_id TEXT PRIMARY KEY,
    allow_tabs BOOLEAN DEFAULT 1,      -- ← Campo relevante
    allow_popups BOOLEAN DEFAULT 0,
    enable_notifications BOOLEAN DEFAULT 1,
    window_width INTEGER DEFAULT 1200,
    window_height INTEGER DEFAULT 800,
    window_maximized BOOLEAN DEFAULT 0,
    FOREIGN KEY (webapp_id) REFERENCES webapps(id)
)
```

## Arquivos de Dados

- **Perfis**: `~/.local/share/br.com.infinity.webapps/profiles/<id>/`
- **Ícones**: `~/.local/share/br.com.infinity.webapps/icons/<id>.png`
- **Desktop**: `~/.local/share/applications/webapp-<id>.desktop`
- **Config**: `~/.config/br.com.infinity.webapps/`

## Padrões de Código

- **Formatação**: Black (100 char line length)
- **Type Checking**: mypy strict mode
- **Linting**: flake8
- **Import Sorting**: isort
- **Testing**: pytest

## Sinais GTK Importantes

**WebView Signals**:
- `notify::title` → Título da página mudou (document.title)
- `notify::favicon` → Favicon mudou
- `load-changed` → Estado de carregamento mudou
- `create` → Nova janela/aba solicitada
- `decide-policy` → Decisões de navegação/permissões

**TabView Signals** (para implementar):
- `page-attached` → Nova aba adicionada
- `page-detached` → Aba removida
- `create-window` → Nova janela solicitada
- `close-page` → Fechar aba solicitado

## Implementação Necessária: Sistema de Abas Dinâmicas

### Objetivo
Implementar sistema completo de tabs igual a navegadores modernos, com:
- Múltiplas abas do mesmo webapp
- Criação/fechamento dinâmico
- Limite de 10 abas
- Títulos dinâmicos (document.title)
- Redimensionamento automático
- UI integrada à barra de título

### Componentes a Criar/Modificar

1. **webapp_window.py** (modificar):
   - Expandir criação de TabView/TabBar (linhas 161-172)
   - Adicionar gerenciamento de múltiplos WebViews
   - Implementar botões + e X
   - Conectar sinais de título

2. **tab_manager.py** (novo):
   - Classe TabManager
   - Lógica de criação/fechamento
   - Controle de limite (10 tabs)
   - Redimensionamento automático

3. **i18n.py** (modificar):
   - Adicionar mensagens de limite de abas

### Especificações Técnicas

**Limite**: 10 abas máximo
**Redimensionamento**:
- 1-3 abas: 180px
- 4-6 abas: 130px
- 7-10 abas: 100px

**Altura da barra**: ~38px integrada à header bar

**Sinais a conectar**:
```python
webview.connect("notify::title", self._on_title_changed)
tab_view.connect("page-attached", self._on_page_attached)
tab_view.connect("page-detached", self._on_page_detached)
tab_view.connect("close-page", self._on_close_page)
```

## Fluxo de Criação de WebApp

1. Usuário clica "Novo WebApp" → `add_dialog.py`
2. Preenche nome, URL, marca "Ativar Abas" → `allow_tabs = True`
3. Salva no database → `database.py:save_webapp()`
4. Cria entrada `webapp_settings` → `allow_tabs` column
5. Ao abrir webapp → `webapp_window.py` lê `allow_tabs`
6. Se True → cria TabView/TabBar (PRECISA IMPLEMENTAR LÓGICA COMPLETA)

## Referências Úteis

- **GTK4 Docs**: https://docs.gtk.org/gtk4/
- **Adwaita Docs**: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/
- **WebKitGTK**: https://webkitgtk.org/reference/webkit2gtk/stable/
- **PyGObject**: https://pygobject.readthedocs.io/

## Comandos Úteis

```bash
# Executar aplicação
python -m app.main

# Abrir webapp específico
python -m app.main --webapp <id>

# Modo debug
python -m app.main --debug

# Testes
pytest tests/

# Formatação
black app/
isort app/

# Type checking
mypy app/
```

## Notas Importantes

- Aplicação usa **processo separado** para cada webapp (standalone_webapp.py)
- TabView/TabBar já existem mas funcionalidade não está completa
- Sistema i18n funciona com observer pattern (real-time language switching)
- Perfis WebKit são completamente isolados por webapp
- Database usa migrações automáticas (migrations.py)

## Status Atual: Sistema de Abas

**✅ IMPLEMENTADO E FUNCIONAL** (2025-10-30):

### Arquivos Principais:
- `app/ui/tab_manager.py` - Gerenciador completo de abas (420 linhas)
- `app/ui/webapp_window.py` - Integração com janela e header bar
- `app/utils/i18n.py` - Traduções PT/EN para mensagens de abas

### Funcionalidades Implementadas:
- ✅ UI toggle "Ativar Abas" no diálogo de criação
- ✅ Campo database `allow_tabs` e model `allow_tabs: bool`
- ✅ TabManager com criação dinâmica de múltiplas abas
- ✅ Múltiplos WebViews isolados (um por aba)
- ✅ Botão "+" funcional para criar novas abas
- ✅ Botão "X" por aba (padrão do Adw.TabBar)
- ✅ Limite de 10 abas com diálogo de alerta multilíngue
- ✅ Mensagens de erro i18n (PT: "Limite máximo...", EN: "Maximum tab limit...")
- ✅ Atualização dinâmica de títulos via `document.title`
- ✅ Redimensionamento proporcional automático (GTK nativo)
- ✅ Abas integradas na barra de título (entre navegação e controles)
- ✅ Sempre mantém pelo menos 1 aba aberta
- ✅ Lógica completa de gerenciamento de estado

### Arquitetura Implementada:
```
HeaderBar (Adw.HeaderBar)
├── [◀] [▶] [⟳]  (botões de navegação - pack_start)
├── TabBar (center - set_title_widget)
│   ├── [Aba 1] [Aba 2] [Aba 3]... (tabs)
│   └── [+] (botão nova aba - end_action_widget)
└── [_] [□] [✕]  (controles da janela - automático)

TabView (conteúdo)
└── WebViews isolados (um por aba)
```

### Configurações Aplicadas:
```python
self.tab_bar.set_autohide(False)       # Sempre visível
self.tab_bar.set_expand_tabs(True)     # Redimensionamento proporcional
header_bar.set_title_widget(tab_bar)   # Integrada ao header bar
```

### Tradução i18n:
```python
"webapp.tab.new_tooltip": "Nova aba" / "New tab"
"webapp.tab.close_tooltip": "Fechar aba" / "Close tab"
"webapp.tab.limit_reached": "Limite máximo..." / "Maximum tab limit..."
```

### Melhorias Futuras (Planejadas):
- Persistência de abas entre sessões
- Atalhos de teclado (Ctrl+T, Ctrl+W, Ctrl+Tab)
- Arrastar e soltar para reordenar
- Favicon nas abas (`notify::favicon`)
- Menu de contexto (clique direito)
- Busca em abas

---

**Última atualização**: 2025-10-30
**Status**: Sistema completo e funcional em produção
**Por**: Claude Code
