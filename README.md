<div align="center">

# ShadowRealms AI

![ShadowRealms AI Logo](assets/logos/logo-3.png)

### The Ultimate AI-Powered Tabletop RPG Experience

[![Version](https://img.shields.io/badge/version-0.6.4-blue.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Phase 2](https://img.shields.io/badge/phase-2%20complete-green.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Phase 3A](https://img.shields.io/badge/phase-3A%20complete-green.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Phase 3B](https://img.shields.io/badge/phase-3B%20next-blue.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Status](https://img.shields.io/badge/status-login%20%26%20theme%20active-yellow.svg)](https://github.com/Somnius/shadowrealms-ai)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

---

## Enter a World Where AI Becomes Your Dungeon Master

*Experience the future of tabletop RPG gaming with intelligent AI assistance, persistent world memory, and seamless multi-language support.*

---

</div>

## What is ShadowRealms AI?

ShadowRealms AI is a revolutionary platform that transforms traditional tabletop RPG gaming by integrating advanced AI technology. Our system acts as an intelligent Dungeon Master, providing dynamic storytelling, character development, and world-building assistance while maintaining complete campaign continuity through advanced memory systems.

### Key Features

<div align="center">

| **AI Dungeon Master** | **Persistent Worlds** | **Smart Dice System** |
|:---:|:---:|:---:|
| Intelligent NPC behavior and dynamic storytelling | ChromaDB-powered memory for campaign continuity | Automated dice rolling with context awareness |

| **Multi-Language** | **Real-time Performance** | **Secure & Private** |
|:---:|:---:|:---:|
| Global accessibility with translation pipelines | Optimized for 5-10s responses, 30-60s for complex tasks | Local AI processing, no data leaves your system |

</div>

---

## Documentation

For comprehensive documentation, detailed setup instructions, and complete feature overview, please refer to our complete documentation:

**[View Complete Documentation](https://github.com/Somnius/shadowrealms-ai/blob/main/SHADOWREALMS_AI_COMPLETE.md)**

### Additional Resources

- **[Testing Guide](frontend/TESTING.md)** - Comprehensive testing documentation
- **[Contributing Guidelines](docs/CONTRIBUTING.md)** - How to contribute to the project
- **[Changelog](docs/CHANGELOG.md)** - Detailed version history and updates
- **[Docker Setup Guide](docs/DOCKER_ENV_SETUP.md)** - Environment configuration
- **[Books Sync Guide](books/README.md)** - World of Darkness books synchronization
- **[Test Suite Guide](tests/README.md)** - Comprehensive test documentation
- **[Documentation Index](docs/README.md)** - Complete documentation index

---

## Quick Start

<div align="center">

### One Command to Rule Them All

```bash
git clone https://github.com/Somnius/shadowrealms-ai.git
cd shadowrealms-ai
docker-compose up -d
```

**Access Points:**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **ChromaDB**: http://localhost:8000

</div>

---

## Technology Stack

<div align="center">

### Backend & Infrastructure

![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)

### AI & Machine Learning

![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B6B?style=for-the-badge&logo=vector-database&logoColor=white)
![LM Studio](https://img.shields.io/badge/LM%20Studio-FF6B6B?style=for-the-badge&logo=local-llm&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-FF6B6B?style=for-the-badge&logo=ollama&logoColor=white)
![RAG](https://img.shields.io/badge/RAG-4CAF50?style=for-the-badge&logo=artificial-intelligence&logoColor=white)

### Frontend & UI

![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white)
![Material-UI](https://img.shields.io/badge/Material--UI-0081CB?style=for-the-badge&logo=material-ui&logoColor=white)

### Development & Monitoring

![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-000000?style=for-the-badge&logo=json-web-tokens&logoColor=white)

</div>

---

## Current Development Status

<div align="center">

### Version 0.6.4 - Responsive Design & Navigation Fixes 📱

**Last Updated**: `2025-10-24`
**Progress**: `Full Mobile Support - Touch-Optimized, Navigation Fixed`

**⚠️ Current Reality Check:**
- ✅ **Working**: Login/Register, Admin Panel, Gothic Theme, Campaign Editing, **Mobile UI**
- ✅ **New**: Campaign name/description editing, Game-specific emojis & colors
- 🚧 **In Progress**: Chat interface, Character creation, Full CRUD wiring
- 📋 **Planned**: WebSocket chat, AI integration, Character system

</div>

### Phase 2 Complete ✅

<div align="center">

| **Foundation** | **AI Services** | **Web Interface** |
|:---:|:---:|:---:|
| Complete Docker environment with all 6 services stable | Both LM Studio (3 models) and Ollama (1 model) fully working | React application serving through nginx proxy |
| Backend API with authentication and RAG integration | ChromaDB vector memory system fully functional | Production-ready reverse proxy configuration |
| SQLite schema with ChromaDB fully operational | Smart Model Router for intelligent model selection | JWT-based user management with role-based access |
| Campaign Management API | Memory Search & Context Retrieval | RAG-Powered AI Responses |
| Vector Embeddings | Persistent AI Memory | Context-Aware Generation |
| API Response Consistency | Character Creation Schema | 100% User Experience Tests |
| Rule Book Integration | WoD Books Processing | PDF Parser + RAG Import |
| Invite System | Quick Import Tools | Integration Testing Suite |

</div>

### Phase 3A Status 🚧 (v0.6.0 - Frontend Foundation)

<div align="center">

| **✅ WORKING NOW** | **🚧 UI EXISTS (Not Wired)** | **📋 TODO** |
|:---:|:---:|:---:|
| **Login/Register** - Fully functional | Character creation form (no backend) | Character system wiring |
| **Admin Panel** - User management works | Location chat UI (static) | WebSocket real-time chat |
| **Invite System** - Secure registration | AI chat interface (placeholder) | LM Studio integration |
| **Gothic Theme** - Immersive atmosphere | Rule book search UI (no data) | ChromaDB RAG hookup |
| **Campaign Editing** - Name/desc updates | Character selection (no chars) | Full gameplay loop |
| Campaign list with themes | Message history display (mock) | Session management |
| Role-based access (admin/player) | OOC chat room (not live) | Campaign deletion |
| JWT authentication | Campaign details page | NPC/Character management |
| User bans (temp/permanent) | Location management UI | Dice rolling system |
| Password reset by admin | Game-specific emojis/colors | Advanced features |
| **👑 Admin Panel** (v0.6.1) | **User Moderation** (v0.6.1) | **Character Management** (v0.6.1) |
| Admin-only panel UI (720 lines) | Temporary & permanent bans | Convert character to NPC |
| User table with status | Ban duration tracking | Kill character with death types |
| Edit user profiles | Password reset by admin | Character moderation log |
| Moderation audit log | Auto-expiring temp bans | Soft/Mid/Horrible death options |
| Refactored architecture | All actions logged | Admin-controlled NPCs |
| **🦇 Gothic Horror Theme** (v0.6.2) | **Theme-Specific Effects** (v0.6.2) | **Immersive Atmosphere** (v0.6.2) |
| Complete CSS theme (352 lines) | Vampire: Dripping blood | Gothic fonts (Cinzel/Crimson Text) |
| GothicBox components (194 lines) | Mage: Magic sparkles | Clean login/register screens |
| Gothic Showcase (546 lines) | Werewolf: Bite marks | Campaign-aware theming |
| Dark fantasy aesthetics | Theme auto-switches by game | Larger logo with glow |
| GPU-accelerated animations | Effects only when appropriate | No emojis on buttons |
| **📝 Campaign Editing** (v0.6.3) | **Game System Themes** (v0.6.3) | **Enhanced UI** (v0.6.3) |
| Edit campaign names (inline) | 🩸 Vampire - Blood Red | Click-to-edit interface |
| Edit descriptions (textarea) | ✨ Mage - Mystic Purple | Game-specific emojis |
| Permission checks (creator/admin) | 🐺 Werewolf - Amber Gold | Color-coded campaign cards |
| Real-time UI updates | 🧚 Changeling - Fae Green | Save/cancel buttons |
| Backend PUT endpoint working | 🏹 Hunter - Silver | Instant save feedback |
| **📱 Responsive Design** (v0.6.4) | **Navigation Fixes** (v0.6.4) | **Mobile Optimization** (v0.6.4) |
| Full mobile support (315 lines CSS) | Browser back button fixed | Touch-friendly UI (44px targets) |
| Collapsible sidebars on mobile | Exit confirmation dialogs | Viewport meta tag configured |
| Mobile-first breakpoints | Proper navigation history | Safe area insets (notches) |
| Tablet & desktop layouts | Character exit warnings | Hamburger menu navigation |
| Responsive chat interface | Page state preservation | Swipeable panels |

</div>

### Documentation Reorganization ✅

<div align="center">

| **docs/ Directory** | **11 Files** | **3,701 Lines** |
|:---:|:---:|:---:|
| Complete documentation index | Version history (CHANGELOG.md) | Contribution guidelines |
| Docker setup guide | GitHub collaboration guide | Phase completion reports |
| Frontend/Backend audit | System status reports | Manual testing guides |
| Professional structure | Cleaner project root | Easy navigation |

</div>

---

## Development Roadmap

<div align="center">

### Phase 3B - Enhanced Frontend Features (NEXT) 🎯

| **Real-Time Features** | **Advanced UI/UX** | **Mobile Experience** |
|:---:|:---:|:---:|
| WebSocket integration | Advanced character sheet builder | Mobile-responsive design |
| Live player status updates | Drag-and-drop dice rolling | Touch-optimized controls |
| Instant notifications | Combat tracker interface | Progressive Web App (PWA) |
| Real-time message delivery | Inventory management UI | Offline capabilities |
| Typing indicators | Quest tracking system | Mobile navigation |

### Phase 4 - RPG Mechanics Integration

| **White Wolf Character System** | **Narrative Combat** | **World Building with Admin Control** |
|:---:|:---:|:---:|
| Advanced WoD character sheets | Turn-based narrative combat | Location & NPC management |
| d10 dice pools with difficulty | XP cost AI assistance | Admin verification system |
| Character progression tracking | Environmental factors | Procedural generation with approval |
| Skill checks and modifiers | Initiative system | World state management |

### Phase 5 - Advanced Features

| **Multiplayer Support** | **Advanced AI** | **Content Creation** |
|:---:|:---:|:---:|
| Real-time collaboration | Enhanced NPC behavior | Custom rule system support |
| Session management | Dynamic world events | Community content sharing |
| Voice integration | Advanced storytelling | Mod support |
| Video chat for remote play | Multi-language support | Campaign templates |

</div>

---

## Architecture Overview

<div align="center">

```mermaid
graph TB
    A[Frontend React App] --> B[Nginx Reverse Proxy]
    B --> C[Flask Backend API]
    C --> D[Smart Model Router]
    C --> E[RAG Service]
    C --> F[SQLite Database]
    C --> G[Redis Cache]
    E --> H[ChromaDB Vector DB]
    D --> I[LM Studio Models]
    D --> J[Ollama Models]
    K[GPU Monitor] --> C
    L[System Monitor] --> C
```

</div>

---

## Game Systems Supported

<div align="center">

| **D&D 5e** | **White Wolf** | **Custom Systems** |
|:---:|:---:|:---:|
| Complete D20 system integration | D10 dice pool mechanics | Flexible rule system support |
| Character classes and races | Vampire, Werewolf, Mage support | Custom dice mechanics |
| Spell and ability management | Storytelling system integration | Homebrew rule compatibility |

</div>

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- 16GB+ RAM (recommended)
- NVIDIA GPU with 16GB+ VRAM (for optimal AI performance)
- Linux/macOS/Windows with WSL2

### Installation

```bash
# Clone the repository
git clone https://github.com/Somnius/shadowrealms-ai.git
cd shadowrealms-ai

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

### First Steps

1. **Access the Frontend**: Open http://localhost:3000
2. **Create Your Campaign**: Set up your first RPG campaign
3. **Configure AI Models**: Ensure LM Studio and Ollama are running
4. **Start Playing**: Begin your AI-assisted RPG adventure!

---

## Contributing

<div align="center">

We welcome contributions from the RPG and AI communities! Whether you're a developer, game designer, or AI enthusiast, there's a place for you in ShadowRealms AI.

[![Contributing](https://img.shields.io/badge/Contributing-Welcome-green.svg)](CONTRIBUTING.md)
[![Issues](https://img.shields.io/badge/Issues-Report-red.svg)](https://github.com/Somnius/shadowrealms-ai/issues)
[![Discussions](https://img.shields.io/badge/Discussions-Join-blue.svg)](https://github.com/Somnius/shadowrealms-ai/discussions)

</div>

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

### Star this repository if you find it helpful!

**Made with ❤️ for the RPG community**

[![GitHub stars](https://img.shields.io/github/stars/Somnius/shadowrealms-ai?style=social)](https://github.com/Somnius/shadowrealms-ai)
[![GitHub forks](https://img.shields.io/github/forks/Somnius/shadowrealms-ai?style=social)](https://github.com/Somnius/shadowrealms-ai)

</div>