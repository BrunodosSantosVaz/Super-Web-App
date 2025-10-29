# WebApps Manager

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)

Transform your favorite websites into native desktop applications with full isolation and desktop integration.

## Features

- 🚀 **Create WebApps** from any website with just a URL
- 🔒 **Isolated Profiles** - Each webapp has its own cookies, cache, and storage (similar to Firefox profiles)
- 🎨 **Desktop Integration** - Automatic launcher entries and system tray support
- 🔔 **Native Notifications** - Full control over which webapps can send notifications
- 📑 **Multiple Tabs** - Browse multiple pages within a single webapp
- 🎭 **Popup Handling** - Intelligent popup management (open as tabs or windows)
- ⚡ **Resource Efficient** - Shared network process saves ~40MB per webapp
- 🌐 **Modern UI** - Built with GTK4 and libadwaita for a native GNOME experience

## Architecture

WebApps Manager follows Clean Code principles with a layered architecture:

```
┌─────────────────────────────────────┐
│  UI Layer (GTK4 + libadwaita)      │
├─────────────────────────────────────┤
│  Core Layer (Business Logic)       │
├─────────────────────────────────────┤
│  WebEngine Layer (WebKitGTK)       │
├─────────────────────────────────────┤
│  Data Layer (SQLite + Profiles)    │
└─────────────────────────────────────┘
```

### Key Design Decisions

- **Shared WebContext**: All webapps share a network process for efficiency
- **Isolated Profiles**: Each webapp has its own WebsiteDataManager for privacy
- **SQLite for Metadata**: Fast queries for webapp information
- **File-based Profiles**: Easy backup and portability
- **Type Safety**: Full type hints throughout the codebase
- **Clean Code**: Small, focused functions with clear responsibilities

## Requirements

### Runtime Dependencies

- Python 3.11+
- GTK4 4.12+
- libadwaita 1.5+
- WebKitGTK 6.0+
- PyGObject 3.46+

### Optional Dependencies

- StatusNotifier support (for system tray)
- xdg-desktop-portal (for background apps and notifications)

## Installation

### From Flatpak (Recommended)

```bash
# Build the Flatpak
cd webapps-manager/flatpak
flatpak-builder --user --install --force-clean build br.com.infinity.webapps.yml

# Run
flatpak run br.com.infinity.webapps
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/webapps-manager.git
cd webapps-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .[dev]

# Run
python -m app.main
```

## Usage

### Creating a WebApp

1. Click "New WebApp" in the main window
2. Enter a name and URL
3. Optionally fetch the website's icon automatically
4. Configure settings (tabs, notifications, etc.)
5. Click "Create"

The webapp will appear in your application launcher and can be launched directly.

### Managing WebApps

- **Launch**: Click the play button or double-click the webapp
- **Edit**: Click the settings button to modify configuration
- **Delete**: Right-click and select "Remove"
- **Search**: Use the search bar to filter webapps by name

### WebApp Settings

Each webapp can be configured with:

- **Allow Multiple Tabs**: Enable tabbed browsing
- **Allow Popups**: Control popup window behavior
- **Allow Notifications**: Grant notification permission
- **Show in System Tray**: Add icon to system tray
- **Run in Background**: Keep running when window is closed

## Development

### Project Structure

```
webapps-manager/
├── app/
│   ├── ui/              # GTK4/Adwaita UI components
│   ├── core/            # Business logic
│   ├── webengine/       # WebKit management
│   ├── data/            # Database and models
│   ├── utils/           # Utilities (XDG, logging, validation)
│   ├── application.py   # Main GTK Application
│   └── main.py          # Entry point
├── flatpak/             # Flatpak packaging files
├── tests/               # Unit tests
├── docs/                # Documentation
├── pyproject.toml       # Project configuration
└── README.md
```

### Code Quality

The project follows strict code quality standards:

- **Type Hints**: All functions have complete type annotations
- **Docstrings**: Google-style docstrings for all public APIs
- **Line Length**: Maximum 100 characters
- **Testing**: Pytest with >80% coverage goal
- **Linting**: flake8, mypy, black, isort

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_webapp_manager.py
```

### Code Formatting

```bash
# Format code
black app/

# Sort imports
isort app/

# Type checking
mypy app/

# Linting
flake8 app/
```

## Technical Details

### Profile Isolation

Each webapp gets its own isolated profile directory:

```
~/.local/share/br.com.infinity.webapps/profiles/<webapp-id>/
├── cookies.db
├── localstorage/
├── indexeddb/
├── cache/
└── permissions.json
```

This ensures:
- No cookie/session sharing between webapps
- Multiple accounts on the same website
- Easy backup (copy the profile directory)
- Clean removal (delete the profile directory)

### Resource Sharing

WebApps Manager uses a shared WebKit network process across all webapps:

- **Saves Memory**: ~30-50MB per webapp
- **Maintains Security**: Each webapp still has isolated data
- **Improves Stability**: Crash in one webapp doesn't affect others

### Desktop Integration

Automatic `.desktop` file creation provides:
- Launcher integration (GNOME, KDE, XFCE)
- Search integration
- Custom icons
- Quick actions (New Window, Preferences)

## Troubleshooting

### WebApp not loading

Check the logs:
```bash
tail -f ~/.cache/br.com.infinity.webapps/logs/app.log
```

### Icons not downloading

Ensure you have network access and the website has a favicon. You can manually set an icon in the webapp settings.

### Notifications not working

Make sure:
1. Notifications are enabled in webapp settings
2. xdg-desktop-portal is installed
3. Your desktop environment supports notifications

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes following the code style
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the GPL-3.0-or-later license. See [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [GTK4](https://gtk.org/) and [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)
- Powered by [WebKitGTK](https://webkitgtk.org/)
- Inspired by Franz, Ferdi, and GNOME Web

## Roadmap

### v1.0 (Current)
- [x] Basic webapp management
- [x] Isolated profiles
- [x] Desktop integration
- [x] System tray support
- [x] Native notifications

### v1.5 (Planned)
- [ ] User scripts (custom JavaScript injection)
- [ ] Basic ad-blocking
- [ ] Custom themes
- [ ] Touchpad gestures

### v2.0 (Future)
- [ ] Cloud sync between devices
- [ ] Backup/restore configurations
- [ ] Plugin system
- [ ] Browser extension support
- [ ] PWA (Progressive Web App) support

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/webapps-manager/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/webapps-manager/discussions)

---

Made with ❤️ by Bruno Vaz
