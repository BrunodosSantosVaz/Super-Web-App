# Super WebApp

Plataforma desktop para criar e administrar WebApps modernos no Linux com foco em isolamento, integração nativa e produtividade. Construído em **Python 3.11+**, **GTK 4/libadwaita** e **WebKitGTK 6**, o Super WebApp combina técnicas de navegadores modernos com fluxo de trabalho de aplicativos desktop independentes.

## 💡 Sobre o Projeto

Este projeto foi desenvolvido por um profissional de produto, não por um programador experiente. Minha pouca experiência com codigo inclui trabalhos com Python para análise de dados e desenvolvimento web com HTML, CSS, JavaScript e PHP. No entanto, este projeto foi construído com o apoio intensivo de inteligência artificial (Claude Code e OpenAI Codex), através de um processo iterativo de pesquisa, experimentação e aprendizado.

Como minha area é **Produtos**, minha força está em visualizar funcionalidades, entender necessidades dos usuários e projetar experiências. A qualidade técnica do código pode não refletir as melhores práticas de engenharia de software em todos os aspectos, e reconheço que há espaço para melhorias arquiteturais e de performance.

**Convido a comunidade** a abraçar a ideia deste sistema e contribuir com melhorias! Se você é um desenvolvedor experiente e vê potencial no projeto, sua colaboração será muito bem-vinda. Juntos, podemos transformar esta ferramenta em algo ainda mais robusto e profissional.

> 🤝 **Contribuições são extremamente bem-vindas!** Seja para refatoração, otimização, correção de bugs ou novas funcionalidades. Vamos construir algo incrível juntos!

## Índice
- [💡 Sobre o Projeto](#-sobre-o-projeto)
- [Motivação](#motivação)
- [Principais recursos](#principais-recursos)
  - [🔔 Sistema de Notificações](#-sistema-de-notificações)
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
  - [Configurando notificações](#configurando-notificações)
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

Inspirado por elementos de cada um, reuni o que era essencial no meu dia a dia: perfis WebKit isolados, interface moderna, atalhos nativos, abas dinâmicas e um mecanismo confiável para rodar em segundo plano — tudo sem depender dos navegadores já instalados no sistema. O Super WebApp nasceu dessa necessidade específica e evoluiu para uma ferramenta geral pronta para produção.

## Principais recursos

- **Catálogo central de WebApps** com criação, edição e exclusão via interface libadwaita.
- **Abas dinâmicas** com integração à barra de título, limite configurável e títulos em tempo real.
- **Perfis isolados por WebApp** (cookies, armazenamento e permissões em diretórios dedicados).
- **🔔 Notificações nativas automáticas** - Permissões concedidas automaticamente quando habilitadas, com integração total ao sistema de notificações do Linux (KDE, GNOME, XFCE, etc).
- **Minimização e restauração via bandeja** usando StatusNotifierItem/DBus, com menu para abrir ou encerrar rapidamente.
- **Instalador desktop automático**: gera arquivos `.desktop`, ícones e scripts de lançamento.
- **Download helpers**: opção por WebApp para encaminhar downloads ao Super Download ou salvar localmente.
- **Suporte multilíngue (pt-BR/en)** com preferências persistentes.
- **Logs, banco SQLite, diretórios XDG** e perfis WebKit tratados automaticamente.
- **CLI integrada** para lançar WebApps específicos, abrir preferências e fechar instâncias em execução.

### 🔔 Sistema de Notificações

O Super WebApp implementa um **sistema de notificações totalmente automático** que integra perfeitamente aplicações web com o sistema de notificações do Linux:

#### Como Funciona

1. **Permissão Automática**: Ao marcar a opção **"Permitir notificações"** nas configurações do WebApp, as permissões são concedidas **automaticamente e permanentemente** - sem popups ou prompts adicionais.

2. **Interceptação Inteligente**: Um script JavaScript é injetado que:
   - Sobrescreve a API `Notification` do navegador
   - Força `Notification.permission` para sempre retornar `"granted"`
   - Intercepta todas as tentativas de criar notificações
   - Envia os dados para o sistema nativo via WebKit message handlers

3. **Integração Nativa**: As notificações aparecem diretamente no centro de notificações do seu desktop Linux usando `notify-send`:
   - **Compatível** com KDE Plasma, GNOME, XFCE, Cinnamon, MATE e outros
   - **Persistentes** entre reinicializações
   - **Identificadas** com o nome "Super WebApp" e o nome do webapp
   - **Com ícone** do webapp quando disponível

#### Casos de Uso

Perfeito para aplicações como:
- **WhatsApp Web** - Receba notificações de mensagens automaticamente
- **Gmail / Outlook** - Notificações de novos emails
- **Discord / Slack** - Mensagens e menções
- **Telegram Web** - Mensagens instantâneas
- **Google Calendar** - Lembretes de eventos

#### Comportamento

- **Com notificações ATIVADAS**: Permissão concedida automaticamente, notificações aparecem no sistema
- **Com notificações DESATIVADAS**: Permissões negadas, nenhuma notificação é exibida
- **Persistência**: A configuração é salva em `~/.local/share/br.com.infinity.webapps/profiles/{webapp-id}/permissions.json`
- **Reinicialização**: Funciona imediatamente após reiniciar o webapp ou o sistema

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
- O ícone da bandeja permite **Abrir Super WebApp** ou **Sair**.
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

A aba "Downloads" nas preferências de cada WebApp permite selecionar:
- **Manter no WebApp** (WebKit padrão),
- **Abrir automaticamente** (para arquivos suportados),
- **Encaminhar ao Super Download** (executa `super-download` com a URL e metadados).
Também é possível definir o comando customizado via variável `SUPER_DOWNLOAD_COMMAND`.

### Configurando notificações

Para habilitar notificações em um WebApp:

1. **Ao criar novo WebApp**:
   - Marque a caixa ✅ **"Permitir notificações"**
   - Pronto! As notificações funcionarão automaticamente

2. **Em WebApp existente**:
   - Clique com botão direito no WebApp → **"Editar"**
   - Marque ✅ **"Permitir notificações"**
   - Salve as alterações
   - **Importante**: Feche e reabra o WebApp para aplicar

3. **Testando**:
   - Abra o WebApp (ex: WhatsApp Web)
   - A permissão já estará concedida automaticamente
   - Peça para alguém te enviar uma mensagem
   - A notificação aparecerá no seu desktop! 🔔

#### Requisitos do Sistema

- **notify-send** deve estar instalado (geralmente já vem por padrão)
- Ambiente desktop com suporte a notificações D-Bus (KDE, GNOME, XFCE, etc)

Verifique se está instalado:
```bash
which notify-send
# Deve retornar: /usr/bin/notify-send ou /usr/sbin/notify-send
```

Teste manualmente:
```bash
notify-send "Teste" "Testando notificação"
```

## Configuração e armazenamento

- **Configurações globais**: `~/.config/br.com.infinity.webapps/config.json`
- **Banco de dados (SQLite)**: `~/.config/br.com.infinity.webapps/webapps.db`
- **Perfis WebKit**: `~/.local/share/br.com.infinity.webapps/profiles/<webapp-id>/`
  - Cookies, LocalStorage, IndexedDB
  - Cache HTTP em `profiles/<webapp-id>/cache/`
  - **Permissões** em `profiles/<webapp-id>/permissions.json`
- **Ícones dos WebApps**: `~/.local/share/br.com.infinity.webapps/icons/`
- **Logs**: `~/.local/state/br.com.infinity.webapps/log.txt`
- **Arquivos `.desktop`**: `~/.local/share/applications/br.com.infinity.webapps.webapp_*.desktop`
- **Ícones no sistema**: `~/.local/share/icons/hicolor/*/apps/br.com.infinity.webapps.webapp_*.png`

### Estrutura de Permissões

Cada WebApp possui um arquivo `permissions.json` que armazena decisões de permissão:

```json
{
  "notifications": true,
  "geolocation": false,
  "camera": false,
  "microphone": false
}
```

Este arquivo é **persistente** e mantém as configurações mesmo após reinicializações.

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
- ✅ **Sistema de notificações nativas** (implementado!)
- Restauração de abas entre sessões e atalhos avançados (Ctrl+T/Ctrl+W/Ctrl+Tab).
- Suporte a gestos, user-scripts e temas personalizados.
- API D-Bus para controle externo e modo quiosque.
- Sincronização de catálogo e perfis entre máquinas.
- Monitoramento de downloads com feedback direto na UI.
- Gerenciamento de outras permissões web (câmera, microfone, geolocalização).

## Contribuindo

Este projeto foi criado com paixão e com a ajuda de IA, mas há muito espaço para melhorias! Se você é desenvolvedor e quer contribuir:

### Como Contribuir

1. **Fork** o projeto
2. Crie uma **branch** para sua feature (`git checkout -b feature/MinhaFeature`)
3. **Commit** suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. **Push** para a branch (`git push origin feature/MinhaFeature`)
5. Abra um **Pull Request**

### Áreas que Precisam de Ajuda

- 🏗️ **Refatoração arquitetural** - Melhorar organização e padrões de código
- ⚡ **Performance** - Otimizar uso de memória e processamento
- 🧪 **Testes** - Expandir cobertura de testes unitários e de integração
- 📚 **Documentação** - Melhorar docs técnicas e comentários no código
- 🐛 **Correção de bugs** - Resolver issues abertas
- ✨ **Novas features** - Implementar itens do roadmap

### Código de Conduta

- Seja respeitoso e construtivo
- Critique código, não pessoas
- Ajude a construir uma comunidade acolhedora

Toda contribuição, por menor que seja, é valorizada! 💙

## Licença

Copyright (C) 2025 Bruno Vaz  
Distribuído sob **GNU General Public License v3.0 ou posterior**.  
Inclua os avisos das dependências listadas em [Compatibilidade de licenças](#compatibilidade-de-licenças) ao redistribuir.
