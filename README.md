# 🎮 ShadowRealms AI

**AI-Powered Tabletop RPG Platform** - Transform your tabletop gaming with local AI Dungeon Masters, vector memory, and immersive storytelling.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18+-blue?logo=react)](https://reactjs.org/)
[![AI](https://img.shields.io/badge/AI-Local%20LLMs-orange?logo=openai)](https://github.com/features/copilot)

## 🌟 Features

- **🤖 AI Dungeon Master**: Local LLM models guide storytelling and world-building
- **🧠 Vector Memory System**: Persistent AI knowledge for campaign continuity
- **🎭 Role-Based Access**: Admin, Helper, and Player roles with JWT authentication
- **📱 Modern Web Interface**: React + Material-UI frontend
- **🐳 Docker Ready**: Complete containerized development and production environment
- **🔍 GPU Monitoring**: Smart AI response optimization based on system resources
- **🌐 Multi-Language Support**: Greek ↔ English translation pipeline
- **💾 Automated Backups**: Comprehensive backup system with verification

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU (optional, for AI acceleration)
- 8GB+ RAM recommended

### Installation
```bash
# Clone the repository
git clone https://github.com/Somnius/shadowrealms-ai.git
cd shadowrealms-ai

# Start all services
docker-compose up --build

# Access the platform
# Frontend: http://localhost:3000
# Backend API: http://localhost:5000
# ChromaDB: http://localhost:8000
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  Flask Backend  │    │   ChromaDB      │
│   (Port 3000)   │◄──►│   (Port 5000)   │◄──►│  Vector Memory  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │    │ GPU Monitoring  │    │   Redis Cache   │
│   (Port 80)     │    │   Service       │    │   (Port 6379)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ Technology Stack

### Backend
- **Python 3.11+** with Flask framework
- **SQLite** for user data and campaigns
- **ChromaDB** for vector memory and AI knowledge
- **JWT Authentication** with role-based access control
- **GPU Monitoring** for AI performance optimization

### Frontend
- **React 18** with Material-UI components
- **WebSocket** support for real-time updates
- **Responsive Design** for all devices

### AI/ML
- **Local LLM Integration** (LM Studio, Ollama)
- **Vector Embeddings** with sentence-transformers
- **Performance Optimization** based on GPU usage

### Infrastructure
- **Docker** for containerization
- **Nginx** reverse proxy
- **Redis** for caching and sessions
- **Automated Backup** system with verification

## 📁 Project Structure

```
shadowrealms-ai/
├── backend/                 # Flask API server
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic
│   └── config.py           # Configuration
├── frontend/               # React application
│   ├── src/                # Source code
│   └── public/             # Static assets
├── monitoring/             # GPU and system monitoring
├── nginx/                  # Reverse proxy configuration
├── assets/                 # Logos and static files
├── backup/                 # Automated backups
├── docker-compose.yml      # Service orchestration
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 Development

### Local Development Setup
```bash
# Backend development
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Frontend development
cd frontend
npm install
npm start
```

### Testing
```bash
# Run all module tests
python test_modules.py

# Test individual components
cd backend && python services/gpu_monitor.py
cd backend && python database.py
cd backend && python main.py --run
```

### Backup System
```bash
# Create automated backup
./backup.sh

# Backup includes: source code, documentation, configuration
# Excludes: backup/, books/, data/, .git/
```

## 🎯 Use Cases

### For RPG Players
- **AI Dungeon Master**: Get intelligent, responsive storytelling
- **Campaign Management**: Organize characters, campaigns, and sessions
- **World Building**: AI-assisted creation of immersive settings
- **Character Development**: Intelligent NPC behavior and interactions

### For Developers
- **AI Integration**: Learn local LLM integration patterns
- **Modern Web Stack**: Experience with Docker, Flask, React
- **Vector Databases**: Work with ChromaDB and embeddings
- **Performance Optimization**: GPU-aware application development

### For Educators
- **Teaching AI**: Demonstrate AI integration concepts
- **Software Architecture**: Show modern development practices
- **Testing Strategies**: Comprehensive testing approaches
- **DevOps Practices**: Docker and deployment workflows

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Phases
- **✅ Phase 1**: Foundation & Docker Environment (Complete)
- **🚧 Phase 2**: AI Integration & Testing (In Progress)
- **📋 Phase 3**: Frontend Development (Planned)
- **📋 Phase 4**: Advanced AI Features (Planned)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Local LLM Community** for open-source AI models
- **Docker Community** for containerization tools
- **Flask & React Communities** for excellent frameworks
- **RPG Community** for inspiration and feedback

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Somnius/shadowrealms-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Somnius/shadowrealms-ai/discussions)
- **Documentation**: [Wiki](https://github.com/Somnius/shadowrealms-ai/wiki)

---

**Built with ❤️ for the RPG and AI communities**

*Transform your tabletop adventures with the power of local AI!* 🎲✨
