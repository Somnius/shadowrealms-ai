<div align="center">

# ShadowRealms AI

![ShadowRealms AI Logo](assets/logos/logo-3.png)

### The Ultimate AI-Powered Tabletop RPG Experience

[![Version](https://img.shields.io/badge/version-0.5.8-blue.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Phase](https://img.shields.io/badge/phase-2%20complete-green.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Phase 3A](https://img.shields.io/badge/phase-3A%20in%20progress-orange.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Tests](https://img.shields.io/badge/tests-61%2F61%20passing-brightgreen.svg)](https://github.com/Somnius/shadowrealms-ai)
[![Status](https://img.shields.io/badge/status-fully%20functional-brightgreen.svg)](https://github.com/Somnius/shadowrealms-ai)
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
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project
- **[Changelog](CHANGELOG.md)** - Detailed version history and updates
- **[Docker Setup Guide](DOCKER_ENV_SETUP.md)** - Environment configuration
- **[Books Sync Guide](books/README.md)** - World of Darkness books synchronization

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

### Version 0.5.8 - Books Sync System Added 📚

**Last Updated**: `2025-10-23`
**Progress**: `Phase 2 Complete - Phase 3A Frontend Development + Books Management`

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
| Rule Book Integration | WoD Books Auto-Sync | Content Retrieval System |

</div>

### Phase 3A In Progress 🚧

<div align="center">

| **Frontend Development** | **Testing Infrastructure** | **Documentation** |
|:---:|:---:|:---:|
| React component architecture | Jest testing framework setup | Comprehensive testing documentation |
| TypeScript integration | Component testing suite | API documentation updates |
| State management with Redux | Service layer testing | Development guides |
| UI/UX improvements | Authentication testing | Deployment documentation |

</div>

---

## Development Roadmap

<div align="center">

### Phase 3 - RPG Mechanics Integration

| **White Wolf Character System** | **Narrative Combat** | **World Building with Admin Control** |
|:---:|:---:|:---:|
| WoD character sheets (priority) | Turn-based narrative combat | Location & NPC management |
| d10 dice pools with difficulty | XP cost AI assistance | Admin verification system |
| Character progression tracking | Environmental factors | Procedural generation with approval |

### Phase 4 - Advanced Features

| **Multiplayer Support** | **Advanced AI** | **Content Creation** |
|:---:|:---:|:---:|
| Real-time collaboration | Enhanced NPC behavior | Custom rule system support |
| Session management | Dynamic world events | Community content sharing |
| Voice integration | Advanced storytelling | Mod support |

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