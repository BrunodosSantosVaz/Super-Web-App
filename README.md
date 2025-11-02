# WebApps Manager

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)

Gerencie seus sites favoritos como aplicativos desktop isolados no Linux, com integração aos padrões do ecossistema GNOME.

## Visão Geral

O WebApps Manager é um aplicativo GTK4/libadwaita escrito em Python 3 que transforma páginas web em aplicações independentes. Cada webapp roda em um processo separado, com perfil WebKit isolado, configurações próprias e atalhos de desktop gerados automaticamente. A aplicação principal mantém um catálogo de webapps em SQLite e oferece ferramentas para criar, editar, iniciar e remover cada entrada.

## Funcionalidades disponíveis

- Criação, edição e exclusão de webapps com validação de URL, categorias predefinidas e suporte a ícones personalizados ou baixados automaticamente (`app/ui/add_dialog.py`:52).
- **Sistema de abas dinâmicas** integrado à barra de título, com comportamento idêntico a navegadores modernos (`app/ui/tab_manager.py`):
  - Até 10 abas simultâneas por webapp com redimensionamento automático e proporcional
  - Abas integradas na barra de título (entre botões de navegação e controles da janela)
  - Títulos dinâmicos que refletem mudanças do `document.title` em tempo real
  - Botão "+" para criar novas abas e botão "X" para fechar abas individuais
  - Sempre mantém pelo menos uma aba aberta (cria nova automaticamente ao fechar a última)
  - Mensagens multilíngues ao atingir o limite de abas (PT/EN)
- Perfis totalmente isolados por webapp, com diretórios próprios e `WebKit.NetworkSession` dedicado (`app/webengine/profile_manager.py`:48).
- Execução de cada webapp em processo separado via `app.standalone_webapp`, incluindo registro de PID e integração com a linha de comando (`app/standalone_webapp.py`:21).
- Integração com o desktop: geração de arquivos `.desktop`, scripts de lançamento e instalação dos ícones dimensionados (48/64/128px) (`app/core/desktop_integration.py`:19).
- Configurações por webapp para abas, popups, bandeja, permissões de notificação e zoom; idioma global com preferências dedicadas (`app/ui/preferences_dialog.py`:15).
- Encaminhamento opcional de downloads para o aplicativo **Super Download**: ao ativar esta opção nas configurações do webapp, links de download (inclusive popups e `<a download>`) são enviados automaticamente para o gerenciador de downloads centralizado. Basta manter o Super Download instalado (Flatpak ou sistema) ou configurar `SUPER_DOWNLOAD_COMMAND` com o executável desejado.
- Bandeja opcional implementada com AppIndicator através de um helper externo para abrir ou fechar o webapp rapidamente (`app/ui/system_tray.py`:15).
- UI principal em libadwaita com busca em tempo real, ações para lançar/editar/remover e suporte a atalhos (`app/ui/main_window.py`:21).
- Internacionalização simples em `pt` e `en`, com arquivo de traduções gravado em `~/.config/br.com.infinity.webapps` (`app/utils/i18n.py`:16).
- Logger central com rotação de arquivos em diretório XDG e modo debug habilitável via parâmetro `--debug` (`app/utils/logger.py`:8, `app/main.py`:24).

## Como implementamos

A base segue arquitetura em camadas bem definidas:

```
┌─────────────────────────────────────┐
│  UI (GTK4/libadwaita)               │  app/ui
├─────────────────────────────────────┤
│  Core (regras de negócio)          │  app/core
├─────────────────────────────────────┤
│  WebEngine (WebKitGTK 6)           │  app/webengine
├─────────────────────────────────────┤
│  Data (SQLite + perfis WebKit)     │  app/data
├─────────────────────────────────────┤
│  Utils (XDG, i18n, logging, etc.)  │  app/utils
└─────────────────────────────────────┘
```

- A camada `core` coordena banco, perfis e integração com o desktop (`app/core/webapp_manager.py`:19).
- `webengine` concentra o gerenciamento do `WebContext`, restrições de segurança, manipulação de popups e sessões (`app/webengine/webview_manager.py`:20).
- A camada de dados usa SQLite com migrações automáticas e mapeamento via dataclasses (`app/data/database.py`:18, `app/data/models.py`:15).
- Utilitários XDG garantem que dados, perfis e logs sejam gravados nos diretórios corretos do usuário (`app/utils/xdg.py`:13).

## Tecnologias

- Python 3.11+
- GTK4 4.12+ e libadwaita 1.5+
- WebKitGTK 6.0+ via PyGObject 3.46
- SQLite (módulo padrão) para metadados
- Requests + BeautifulSoup + Pillow para busca e processamento de ícones
- AppIndicator3 (libayatana-appindicator) para a bandeja
- Ferramentas de desenvolvimento configuradas em `pyproject.toml`: pytest, black, flake8, mypy, isort (`pyproject.toml`:35)

## Como executar

### Flatpak

```bash
cd flatpak
flatpak-builder --user --install --force-clean build br.com.infinity.webapps.yml
flatpak run br.com.infinity.webapps
```

### Ambiente de desenvolvimento

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m app.main --debug
```

Para abrir diretamente um webapp já cadastrado:

```bash
python -m app.main --webapp <id-do-webapp>
```

## Backlog do planejamento inicial

O documento técnico (`plano.txt`) prevê recursos que ainda não foram implementados e permanecem planejados para versões futuras:

- **Gerenciamento granular de notificações**: `NotificationManager` está desenhado, porém a interface de aprovação e a integração com WebKit ainda não estão conectadas (atualmente permissões são negadas por padrão) (`app/webengine/webview_manager.py`:198).
- **Persistência de abas entre sessões**: o sistema de abas dinâmicas está implementado e funcional, mas a restauração automática das abas ao reabrir o webapp ainda não foi concluída.
- **Execução em segundo plano**: o campo `run_background` está modelado (`app/data/models.py`), mas o comportamento ainda não está implementado.
- **Manipulação aprimorada de downloads**: o hook existe na camada WebKit, porém falta UI/fluxo para acompanhar progresso e destino (`app/webengine/webview_manager.py`:214).
- **Suite de testes automatizados e pipeline CI/CD**: o diretório `tests/` está vazio; as metas de cobertura >80% e validações contínuas ainda não foram iniciadas.
- **Melhorias planejadas para o sistema de abas**:
  - Atalhos de teclado (Ctrl+T para nova aba, Ctrl+W para fechar, Ctrl+Tab para alternar)
  - Arrastar e soltar para reordenar abas
  - Favicon nas abas (atualização dinâmica via `notify::favicon`)
  - Menu de contexto (clique direito: fechar, fechar outras, recarregar)
  - Busca em abas (pesquisar conteúdo em todas as abas abertas)
- **Funcionalidades planejadas para versões futuras** (seções 23-24 do plano):
  - v1.5: user-scripts com injeção de JS, bloqueio básico de anúncios, temas customizados e gestos de trackpad.
  - v2.0: sincronização entre dispositivos, backup/restauração de configurações, sistema de plugins/extensões e suporte completo a PWAs.
  - v2.5: perfis compartilhados opcionais, modo quiosque, controles parentais e integração com gerenciadores de senhas.

Esses itens permanecem no backlog e servirão de guia para as próximas iterações do projeto.
