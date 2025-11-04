# WebApps Manager

Plataforma desktop para criar e administrar WebApps modernos no Linux com foco em isolamento, integração nativa e produtividade. Construído em **Python 3.11+**, **GTK 4/libadwaita** e **WebKitGTK 6**, o WebApps Manager combina técnicas de navegadores modernos com fluxo de trabalho de aplicativos desktop independentes.

## Índice
- [Motivação](#motivação)
- [Principais recursos](#principais-recursos)
- [Tecnologias e arquitetura](#tecnologias-e-arquitetura)
- [Compatibilidade de licenças](#compatibilidade-de-licenças)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
  - [Pacotes do sistema](#pacotes-do-sistema)
  - [Flatpak (experimental)](#flatpak-experimental)
  - [Código-fonte](#código-fonte)
- [Como usar](#como-usar)
  - [Interface principal](#interface-principal)
  - [Bandeja do sistema](#bandeja-do-sistema)
  - [Linha de comando](#linha-de-comando)
  - [Integração com Super Download](#integração-com-super-download)
- [Configuração e armazenamento](#configuração-e-armazenamento)
- [Desenvolvimento](#desenvolvimento)
- [Roadmap](#roadmap)
- [Licença](#licença)

## Motivação

As soluções de WebApps existentes atendem bem a casos gerais, mas nenhuma cobria exatamente o fluxo que eu buscava.  
Eu apreciava:
- a forma como o **Brave** organiza WebApps com abas independentes;
- a estética e a gestão do **BigLinux Web Apps**;
- e o comportamento de minimizar para bandeja do **Teams for Linux**.

Inspirado por elementos de cada um, reuni o que era essencial no meu dia a dia: perfis WebKit isolados, interface moderna, atalhos nativos, abas dinâmicas e um mecanismo confiável para rodar em segundo plano — tudo sem depender dos navegadores já instalados no sistema. O WebApps Manager nasceu dessa necessidade específica e evoluiu para uma ferramenta geral pronta para produção.

## Principais recursos

- **Catálogo central de WebApps** com criação, edição e exclusão via interface libadwaita.
- **Abas dinâmicas** com integração à barra de título, limite configurável e títulos em tempo real.
- **Perfis isolados por WebApp** (cookies, armazenamento e permissões em diretórios dedicados).
- **Minimização e restauração via bandeja** usando StatusNotifierItem/DBus, com menu para abrir ou encerrar rapidamente.
- **Instalador desktop automático**: gera arquivos `.desktop`, ícones e scripts de lançamento.
- **Download helpers**: opção por WebApp para encaminhar downloads ao Super Download ou salvar localmente.
- **Suporte multilíngue (pt-BR/en)** com preferências persistentes.
- **Logs, banco SQLite, diretórios XDG** e perfis WebKit tratados automaticamente.
- **CLI integrada** para lançar WebApps específicos, abrir preferências e fechar instâncias em execução.

## Tecnologias e arquitetura

| Camada | Tecnologia | Responsabilidade |
| ------ | ---------- | ---------------- |
| UI | GTK 4 + libadwaita (PyGObject) | Janela principal, diálogos, tabs, bandeja |
| Core | Python | Regras de negócio, orquestração de WebApps, integração desktop |
| Web Engine | WebKitGTK 6 | Renderização, perfis isolados, controle de permissões |
| Dados | SQLite + JSON | Catálogo de WebApps, ajustes de idioma e preferências |
| Utilidades | requests, BeautifulSoup, Pillow, validators | Captura de metadados, download e tratamento de ícones |
| Tray | StatusNotifierItem (DBus) | Minimizar/restaurar independente do shell |

Estrutura em camadas (dentro de `app/`):

```
ui/            -> GTK/libadwaita (MainWindow, dialogs, widgets)
core/          -> WebAppManager, DesktopIntegration, orquestração
webengine/     -> WebView Manager, ProfileManager, política de segurança
data/          -> Database, modelos, migrações
utils/         -> XDG, i18n, logging, helper de downloads
standalone/    -> Launchers para WebApps isolados
```

## Compatibilidade de licenças

O projeto é distribuído sob **GNU GPL v3 ou posterior**. Dependências diretas e sua compatibilidade:

| Pacote | Licença | Compatível com GPLv3? | Observações |
| ------ | ------- | --------------------- | ----------- |
| PyGObject | LGPL-2.1-or-later | ✔️ | Linkagem dinâmica permitida por aplicativos GPLv3. |
| WebKitGTK | LGPL-2.1-or-later | ✔️ | Distribuído como biblioteca do sistema. |
| requests | Apache-2.0 | ✔️ | Requer preservação de avisos e arquivo NOTICE (já embedado). |
| beautifulsoup4 | MIT | ✔️ | Permissiva. |
| Pillow | HPND (PIL license) | ✔️ | Licença permissiva compatível. |
| validators | MIT | ✔️ | Permissiva. |

Nenhuma dependência impõe restrições adicionais além das obrigações usuais (manter avisos de copyright/licença).

## Requisitos

- Linux com Wayland ou X11 e suporte a GTK 4/libadwaita.
- Python **3.11** ou **3.12**.
- WebKitGTK 6 (`gir1.2-webkit-6.0` nos sistemas Debian/Ubuntu).
- `libayatana-appindicator` não é mais necessário — usamos StatusNotifierItem puro via DBus.
- Para integração com Super Download: instalar o aplicativo [Super Download](../Super-Download) ou outro comando compatível.

## Instalação

### Pacotes do sistema

Arch/Manjaro:
```bash
sudo pacman -S python gtk4 libadwaita webkitgtk aria2
```

Ubuntu/Debian:
```bash
sudo apt install python3 python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0 \
                 libayatana-appindicator3-dev sqlite3 aria2
```

### Flatpak (experimental)

```
cd flatpak
flatpak-builder --user --install --force-clean build br.com.infinity.webapps.yml
flatpak run br.com.infinity.webapps
```

Revise o manifesto para ajustar permissões (acesso ao XDG_CONFIG_HOME, downloads, etc.) conforme sua distribuição.

### Código-fonte

```
git clone https://github.com/seu-usuario/Super-Web-App.git
cd Super-Web-App
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m app.main --debug
```

## Como usar

### Interface principal

- **Adicionar WebApp**: clique em “Novo WebApp”, informe URL, título, categoria e ícone (pode ser baixado automaticamente).
- **Abas**: use o botão “+” para novas abas; limite padrão de 10 por WebApp, com ajustes automáticos de largura.
- **Preferências**: defina idioma, comportamento padrão de downloads, tema escuro/claro (herdado do sistema) e limites de abas.
- **Logs**: ativar `--debug` exibe mais detalhes no console e em `~/.local/state/br.com.infinity.webapps/log.txt`.

### Bandeja do sistema

O minimizador usa StatusNotifierItem/DBus:
- Fechar a janela principal oculta a aplicação (continua rodando).
- O ícone da bandeja permite **Abrir WebApps Manager** ou **Sair**.
- Disponível nativamente em Plasma, XFCE, Cinnamon, MATE; no GNOME requer extensão *AppIndicator and KStatusNotifierItem Support*.

### Linha de comando

```
webapps-manager --webapp <id>
webapps-manager --show-main-window
webapps-manager --preferences
webapps-manager --quit
```

As ações são roteadas para a instância existente (Gio.Application `HANDLES_COMMAND_LINE`), evitando múltiplos processos.

### Integração com Super Download

A aba “Downloads” nas preferências de cada WebApp permite selecionar:
- **Manter no WebApp** (WebKit padrão),
- **Abrir automaticamente** (para arquivos suportados),
- **Encaminhar ao Super Download** (executa `super-download` com a URL e metadados).  
Também é possível definir o comando customizado via variável `SUPER_DOWNLOAD_COMMAND`.

## Configuração e armazenamento

- Configurações globais: `~/.config/br.com.infinity.webapps/config.json`
- Banco de dados (SQLite): `~/.local/share/br.com.infinity.webapps/webapps.db`
- Perfis WebKit: `~/.local/share/br.com.infinity.webapps/webapps/<id>`
- Logs: `~/.local/state/br.com.infinity.webapps/log.txt`
- Arquivos `.desktop` e ícones: instalados em `~/.local/share/applications` e `~/.local/share/icons/hicolor/*/apps`

## Desenvolvimento

Scripts úteis:
```
ruff check app tests
black app tests
pytest
python -m compileall app
```

O diretório `tests/` contém cenários iniciais para garantir que a infraestrutura de banco e perfis se comporte corretamente (expanda-os conforme adicionar novas features).

## Roadmap

Itens planejados nas próximas versões (vide `plano.txt`):
- Restauração de abas entre sessões e atalhos avançados (Ctrl+T/Ctrl+W/Ctrl+Tab).
- Suporte a gestos, user-scripts e temas personalizados.
- API D-Bus para controle externo e modo quiosque.
- Sincronização de catálogo e perfis entre máquinas.
- Monitoramento de downloads com feedback direto na UI.

## Licença

Copyright (C) 2025 Bruno Vaz  
Distribuído sob **GNU General Public License v3.0 ou posterior**.  
Inclua os avisos das dependências listadas em [Compatibilidade de licenças](#compatibilidade-de-licenças) ao redistribuir.
