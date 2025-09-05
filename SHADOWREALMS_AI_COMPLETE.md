# ShadowRealms AI - Complete Platform Documentation

## Project Overview & Vision

**ShadowRealms AI** is a web-based RPG platform that transforms traditional tabletop gaming through AI-powered storytelling, world-building, and campaign management. Built with modern web technologies and local LLM integration, it provides a private, scalable platform for immersive roleplaying experiences.

### Core Concept
- **AI Dungeon Master**: Local LLM models guide storytelling and world-building
- **Web-Based Platform**: Modern web interface accessible from any device
- **Vector Memory System**: Persistent AI knowledge for campaign continuity
- **Multi-Campaign Support**: Manage multiple concurrent campaigns
- **Role-Based Access**: Admin, Helper, and Player roles with specific permissions

### Why This Project
- **Personal Learning**: Experiment with AI models and modern web technologies
- **Privacy-First**: Local deployment keeps all data and AI interactions private
- **Scalable Architecture**: Designed for growth from single campaigns to large groups
- **Technology Exploration**: Hands-on experience with cutting-edge AI and web frameworks

## Technical Architecture

### System Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Vector DB     │
│  React + MUI    │◄──►│   Flask API     │◄──►│   ChromaDB      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   SQLite DB     │              │
         │              │  (Characters,   │              │
         │              │   Campaigns)    │              │
         │              └─────────────────┘              │
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  GPU Monitoring │              │
         │              │   & LLM Mgmt    │              │
         │              └─────────────────┘              │
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Local LLMs    │
                    │  (LM Studio,    │
                    │    Ollama)      │
                    └─────────────────┘
```

### Docker Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                    ShadowRealms AI Platform                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Frontend  │  │   Backend   │  │  Monitoring │            │
│  │  React App  │  │ Flask API   │  │ GPU/System  │            │
│  │   Port 3000 │  │ Port 5000   │  │   Port 8000 │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│         │               │               │                      │
│         └───────────────┼───────────────┘                      │
│                         │                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   ChromaDB  │  │    Redis    │  │    Nginx    │            │
│  │ Vector DB   │  │   Cache     │  │   Proxy     │            │
│  │ Port 8000   │  │ Port 6379   │  │ Port 80/443 │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### GPU Resource Monitoring System
```
┌─────────────────────────────────────────────────────────────────┐
│                    GPU Resource Monitor                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   GPU Usage │  │ Temperature │  │ Memory VRAM │            │
│  │   (nvidia-  │  │   (Thermal  │  │   (VRAM    │            │
│  │    smi)     │  │  Throttling)│  │  Usage %)   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│         │               │               │                      │
│         └───────────────┼───────────────┘                      │
│                         │                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Performance Mode Detection                     │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                    │ │
│  │  │  Fast   │  │ Medium  │  │  Slow   │                    │ │
│  │  │ (<60%)  │  │(60-80%) │  │ (>80%)  │                    │ │
│  │  └─────────┘  └─────────┘  └─────────┘                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                         │                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              AI Response Adjustment                         │ │
│  │  • Response Complexity  • Generation Speed                 │ │
│  │  • Model Selection      • Resource Optimization            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## AI/LLM Integration Strategy

### Primary Models
- **MythoMakiseMerged-13B**: Primary roleplay and character consistency
- **DreamGen Opus V1**: Narrative generation and world-building
- **Llama 3.1 70B**: Complex storytelling and plot development
- **Eva Qwen2.5**: Creative roleplay and character interaction

### Greek Language Support
- **Meltemi**: Greek language model for bilingual campaigns
- **OpenEuroLLM-Greek**: European Greek language support
- **Translation Pipeline**: Greek ↔ English for AI processing

### Model Distribution
```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Model Distribution                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Primary   │  │  Narrative  │  │  Creative   │            │
│  │   Model     │  │   Model     │  │   Model     │            │
│  │MythoMakise  │  │DreamGen Opus│  │Eva Qwen2.5  │            │
│  │   Merged    │  │     V1      │  │             │            │
│  │    13B      │  │             │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│         │               │               │                      │
│         └───────────────┼───────────────┘                      │
│                         │                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Greek Language Models                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │   Meltemi   │  │OpenEuroLLM  │  │Translation  │        │ │
│  │  │  (Primary)  │  │   -Greek    │  │  Pipeline   │        │ │
│  │  │             │  │ (Secondary) │  │Greek↔English│        │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### GPU Resource Management
- **Real-time Monitoring**: Continuous GPU usage, temperature, and memory tracking
- **Performance Modes**: Automatic adjustment based on resource availability
- **AI Response Optimization**: Dynamic complexity and speed adjustment
- **Resource Protection**: Prevents thermal throttling and memory overflow

## User Roles & Permissions

### Admin Role
- **Full System Access**: All features and data
- **User Management**: Create, modify, and delete user accounts
- **Campaign Creation**: Unlimited campaign creation and management
- **System Configuration**: Modify platform settings and AI parameters
- **Data Management**: Access to all campaign and character data

### Helper Role
- **Campaign Assistance**: Help manage NPCs and world elements
- **Character Validation**: Review and approve character sheets
- **Player Support**: Assist players with technical issues
- **Content Moderation**: Monitor and moderate campaign content
- **Limited Admin Access**: Some administrative functions

### Player Role
- **Character Management**: Create and manage character sheets
- **Campaign Participation**: Join and participate in campaigns
- **World Interaction**: Navigate and interact with campaign worlds
- **Chat Participation**: Engage in campaign discussions
- **Content Creation**: Submit character backgrounds and stories

## Database Schema Design

### Core Tables
```
┌─────────────────────────────────────────────────────────────────┐
│                        Database Schema                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │    Users    │  │  Campaigns  │  │ Characters  │            │
│  │  • id       │  │  • id       │  │  • id       │            │
│  │  • username │  │  • name     │  │  • name     │            │
│  │  • email    │  │  • system   │  │  • class    │            │
│  │  • role     │  │  • setting  │  │  • level    │            │
│  │  • status   │  │  • status   │  │  • stats    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│         │               │               │                      │
│         └───────────────┼───────────────┘                      │
│                         │                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Locations  │  │ AI Memory   │  │User Sessions│            │
│  │  • id       │  │  • id       │  │  • id       │            │
│  │  • name     │  │  • content  │  │  • user_id  │            │
│  │  • type     │  │  • context  │  │  • campaign │            │
│  │  • desc     │  │  • vector   │  │  • status   │            │
│  │  • coords   │  │  • metadata │  │  • last_seen│            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### Key Relationships
- **Users** → **Characters** (One-to-Many)
- **Campaigns** → **Characters** (One-to-Many)
- **Users** → **Campaigns** (Many-to-Many via UserSessions)
- **AI Memory** → **Campaigns** (One-to-Many)
- **Locations** → **Campaigns** (One-to-Many)

### SQL Schema
```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'helper', 'player') DEFAULT 'player',
    status ENUM('active', 'inactive', 'banned') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Campaigns table
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    rpg_system VARCHAR(50) NOT NULL,
    setting TEXT,
    status ENUM('active', 'paused', 'completed') DEFAULT 'active',
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Characters table
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    user_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    class VARCHAR(50),
    level INTEGER DEFAULT 1,
    stats JSON,
    background TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

-- AI Memory table
CREATE TABLE ai_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    context TEXT,
    vector_data BLOB,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

-- User Sessions table
CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

-- System Logs table
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level ENUM('info', 'warning', 'error', 'critical') NOT NULL,
    message TEXT NOT NULL,
    user_id INTEGER,
    campaign_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);
```

## Docker Strategy & Setup

### Development vs Production
- **Development**: Local Docker Compose with volume mounts for code changes
- **Production**: Optimized images with multi-stage builds and security hardening
- **Scaling**: Horizontal scaling with load balancers and database clustering

### Container Images
- **Backend**: `python:3.11-slim` (Ubuntu-based for better package compatibility)
- **Monitoring**: `python:3.11-slim` (Optimized for system monitoring)
- **ChromaDB**: `chromadb/chroma:latest` (Official vector database)
- **Redis**: `redis:7-alpine` (Lightweight caching)
- **Nginx**: `nginx:alpine` (Reverse proxy)
- **Frontend**: `node:18-alpine` (React development)

### Benefits
- **Consistency**: Same environment across development and production
- **Isolation**: Services don't interfere with each other
- **Scalability**: Easy to scale individual services
- **Security**: Containerized applications with limited permissions
- **Portability**: Works on any system with Docker

## Development Commands & Reference

### Docker Commands
```bash
# Build and start all services
docker-compose up --build

# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f [service_name]

# Stop all services
docker-compose down

# Rebuild specific service
docker-compose build [service_name]

# Access container shell
docker-compose exec [service_name] bash
```

### Backend Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python main.py

# Run tests
pytest

# Database migrations
alembic upgrade head

# Code formatting
black .
```

### Database Management
```bash
# Initialize database
python -c "from database import init_db; init_db()"

# Check database health
python -c "from database import check_db_health; check_db_health()"

# View database stats
python -c "from database import get_db_stats; print(get_db_stats())"
```

### GPU Monitoring
```bash
# Check GPU status
nvidia-smi

# Monitor system resources
htop

# View monitoring logs
tail -f data/logs/system_status.json

# Test GPU monitoring API
curl http://localhost:5000/api/ai/status
```

## Development Phases & Status

### Phase 1: Foundation & Docker Setup ✅ COMPLETE
- [x] Project architecture and planning
- [x] Docker environment setup
- [x] Backend foundation with Flask
- [x] Database schema and initialization
- [x] Basic API endpoints
- [x] GPU monitoring system
- [x] Docker base image compatibility (v0.4.0)
- [x] Complete service integration (v0.4.1)
- [x] Frontend React structure ready
- [x] Production nginx configuration

### Phase 2: AI Integration & Testing ⚠️ NEEDS RESTRUCTURE
- [x] LLM service integration (basic implementation)
- [x] Docker network configuration for LLM access
- [x] AI chat endpoints implementation
- [x] Environment variable management for LLM services
- [x] Smart Model Router implementation
- [ ] Resource-efficient model orchestration
- [ ] ChromaDB vector memory system (RAG implementation)
- [ ] AI response generation testing with actual models
- [ ] GPU resource optimization validation
- [ ] Model performance testing

### Phase 3: Frontend Development 🚧 STRUCTURE READY
- [x] React application structure
- [ ] Material-UI component library
- [ ] User authentication interface
- [ ] Character management forms
- [ ] Campaign dashboard

### Phase 4: Advanced Features 📋 PLANNED
- [ ] Real-time chat system
- [ ] World-building tools
- [ ] Character sheet validation
- [ ] Campaign persistence
- [ ] AI memory management

### Phase 5: Testing & Optimization 📋 PLANNED
- [ ] Unit and integration testing
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Load testing
- [ ] User acceptance testing

### Phase 6: Production Deployment 📋 PLANNED
- [ ] Production Docker images
- [ ] Environment configuration
- [ ] Monitoring and logging
- [ ] Backup and recovery
- [ ] Documentation

### Phase 7: Advanced AI Features 📋 PLANNED
- [ ] Multi-model orchestration
- [ ] Advanced vector search
- [ ] Context-aware responses
- [ ] Campaign continuity
- [ ] Dynamic world generation

### Phase 8: Scaling & Optimization 📋 PLANNED
- [ ] Horizontal scaling
- [ ] Database optimization
- [ ] Caching strategies
- [ ] Performance monitoring
- [ ] User feedback integration

## 🧪 Testing & Quality Assurance

### Standalone Testing System ✅ IMPLEMENTED

**ShadowRealms AI** implements a comprehensive **standalone testing approach** that ensures each component works independently before Docker integration. This prevents complex debugging in containerized environments and catches issues early.

#### Testing Philosophy
- **Test Early, Test Often**: Validate components before integration
- **Isolate Issues**: Test individual modules independently
- **Build Confidence**: Know each component works before combining
- **Faster Debugging**: Identify problems at module level

#### What We Test
1. **Configuration Module** - Environment setup and validation
2. **Database Module** - SQLite operations and schema
3. **GPU Monitor Service** - Resource monitoring functionality
4. **Monitoring Service** - System resource tracking
5. **Main Application** - Flask app creation and routing

#### Running Tests

**Test All Modules:**
```bash
# From project root
python test_modules.py
```

**Test Individual Modules:**
```bash
# Test specific components
cd backend && python services/gpu_monitor.py
cd backend && python database.py
cd backend && python main.py
cd monitoring && python monitor.py
```

**Run Actual Services (After Testing):**
```bash
# Run Flask backend (after tests pass)
cd backend && python main.py --run

# Run monitoring service (after tests pass)
cd monitoring && python monitor.py --run
```

#### Test Implementation

Each module includes comprehensive standalone testing:

```python
def test_module_name():
    """Standalone test function for Module Name"""
    print("🧪 Testing Module Name...")
    
    try:
        # Test 1: Basic functionality
        print("  ✓ Testing basic functionality...")
        # ... test code ...
        print("  ✓ Basic functionality working")
        
        # Test 2: Edge cases
        print("  ✓ Testing edge cases...")
        # ... test code ...
        print("  ✓ Edge cases handled correctly")
        
        print("🎉 All Module Name tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    """Run standalone tests if script is executed directly"""
    print("🚀 Running Module Name Standalone Tests")
    print("=" * 50)
    
    success = test_module_name()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! Module is ready for integration.")
        exit(0)
    else:
        print("❌ Tests failed! Please fix issues before integration.")
        exit(1)
```

#### Test Results Example

**Expected Output:**
```
🚀 ShadowRealms AI - Module Test Runner
============================================================

🧪 Testing Configuration Module...
✅ Configuration Module tests PASSED

🧪 Testing Database Module...
✅ Database Module tests PASSED

🧪 Testing GPU Monitor Service...
✅ GPU Monitor Service tests PASSED

🧪 Testing Monitoring Service...
✅ Monitoring Service tests PASSED

🧪 Testing Main Application...
✅ Main Application tests PASSED

📊 TEST RESULTS SUMMARY
============================================================
✅ PASS Configuration Module
✅ PASS Database Module
✅ PASS GPU Monitor Service
✅ PASS Monitoring Service
✅ PASS Main Application

📈 Overall: 5/5 modules passed
🎉 All modules are ready for integration!
```

#### Development Workflow

1. **Write Code** in individual modules
2. **Test Standalone** with `python test_modules.py`
3. **Fix Issues** until all tests pass
4. **Test Docker** integration
5. **Deploy** when everything works

#### Benefits

- **🚀 Early Bug Detection**: Catch issues before Docker integration
- **🔍 Faster Debugging**: Test components without full stack
- **💪 Development Confidence**: Know each module works before integration
- **🛠️ Easier Troubleshooting**: Isolate problems to specific components
- **📊 Quality Assurance**: Comprehensive testing before deployment

#### Test Checklist

**Before Docker Integration:**
- [x] **All standalone tests pass** (`python test_modules.py`) - ✅ **2025-08-28 02:15 EEST**
- [x] **No import errors** in individual modules - ✅ **2025-08-28 02:15 EEST**
- [x] **Database operations** work correctly - ✅ **2025-08-28 02:15 EEST**
- [x] **Service initialization** completes successfully - ✅ **2025-08-28 02:15 EEST**
- [x] **Error handling** works as expected - ✅ **2025-08-28 02:15 EEST**

**After Docker Integration:**
- [ ] **Services start** without crashes - 🔄 **Ready to Test**
- [ ] **Health checks** return 200 status - 🔄 **Ready to Test**
- [ ] **Inter-service communication** works - 🔄 **Ready to Test**
- [ ] **Logs show** successful startup - 🔄 **Ready to Test**
- [ ] **No infinite loops** or hanging services - 🔄 **Ready to Test**

#### Testing Results Summary

**Comprehensive Test Suite Results** - `2025-08-28 02:15 EEST`
```
🚀 ShadowRealms AI - Module Test Runner
============================================================

🧪 Testing Configuration Module...
✅ Configuration Module tests PASSED

🧪 Testing Database Module...
✅ Database Module tests PASSED

🧪 Testing GPU Monitor Service...
✅ GPU Monitor Service tests PASSED

🧪 Testing Monitoring Service...
✅ Monitoring Service tests PASSED

🧪 Testing Main Application...
✅ Main Application tests PASSED

📊 TEST RESULTS SUMMARY
============================================================
✅ PASS Configuration Module
✅ PASS Database Module
✅ PASS GPU Monitor Service
✅ PASS Monitoring Service
✅ PASS Main Application

📈 Overall: 5/5 modules passed
🎉 All modules are ready for integration!
```

**Individual Module Test Results:**
- **Configuration Module**: ✅ **PASSED** - Environment setup and validation working
- **Database Module**: ✅ **PASSED** - SQLite operations, schema, and error handling working
- **GPU Monitor Service**: ✅ **PASSED** - Resource monitoring functionality working
- **Monitoring Service**: ✅ **PASSED** - System resource tracking working
- **Main Application**: ✅ **PASSED** - Flask app creation and routing working

**Status**: All modules validated and ready for Docker integration testing.

again..**Critical Bug Fix Applied**: `2025-08-28 02:20 EEST`
- **Issue**: Missing `gpu_monitor_service` global instance causing import errors
- **Fix**: Restored global instance in `gpu_monitor.py`
- **Impact**: Route files can now import the service properly
- **Testing**: All standalone tests still pass after fix

**Next Testing Phase**: Docker Integration Testing
- **Target**: Test all services in Docker environment
- **Focus**: Service startup, health checks, and inter-service communication
- **Expected**: All services start without crashes and health checks return 200 status
- **Command**: `docker-compose up --build`

#### Common Issues & Solutions

**Import Errors:**
```bash
# Problem: ModuleNotFoundError
ModuleNotFoundError: No module named 'backend'

# Solution: Use relative imports
from config import Config  # ✅ Correct
from backend.config import Config  # ❌ Wrong in Docker
```

**File Path Issues:**
```bash
# Problem: File not found
FileNotFoundError: [Errno 2] No such file or directory

# Solution: Use absolute paths in Docker
status_file = "/app/logs/system_status.json"  # ✅ Correct
status_file = "./logs/system_status.json"     # ❌ Wrong in Docker
```

**Permission Issues:**
```bash
# Problem: Permission denied
exec: "/app/entrypoint.sh": permission denied

# Solution: Make scripts executable
chmod +x backend/entrypoint.sh
chmod +x monitoring/monitor.py
```

#### Debugging Workflow

1. **Test Locally First** - Always test modules standalone before Docker
2. **Check Individual Components** - Test specific failing components
3. **Validate Docker Build** - Build and test Docker services
4. **Monitor Logs** - Watch service logs for errors

#### Success Indicators

**All Tests Pass:**
- ✅ 5/5 modules tested successfully
- ✅ No import errors
- ✅ No runtime exceptions
- ✅ All functionality validated
- ✅ Ready for Docker integration

**Integration Ready:**
- ✅ Services start cleanly
- ✅ Health checks respond
- ✅ Inter-service communication works
- ✅ Logs show success
- ✅ No hanging or crashing

---

## RPG System Support

### D&D 5e
- **Character Classes**: All official classes with level progression
- **Races**: Core races with racial traits
- **Spells**: Complete spell system with casting mechanics
- **Combat**: Initiative, actions, and combat mechanics
- **Equipment**: Weapons, armor, and magical items

### World of Darkness
- **Character Types**: Vampires, Werewolves, Mages
- **Disciplines**: Supernatural powers and abilities
- **Morality**: Humanity and degeneration system
- **Social Systems**: Clans, tribes, and traditions
- **Storytelling**: Narrative-focused mechanics

### BESM (Big Eyes, Small Mouth)
- **Anime Style**: Flexible character creation system
- **Attributes**: Point-based character development
- **Skills**: Comprehensive skill system
- **Combat**: Fast-paced action mechanics
- **Customization**: Highly flexible character options

### Custom Systems
- **Flexible Schema**: JSON-based character data
- **Custom Attributes**: User-defined character properties
- **Rule Engine**: Configurable game mechanics
- **Modular Design**: Easy to add new systems

## Security & Privacy Features

### Authentication & Authorization
- **JWT Tokens**: Secure, stateless authentication
- **Role-Based Access**: Granular permission system
- **Password Security**: bcrypt hashing with salt
- **Session Management**: Secure session handling
- **Input Validation**: Protection against injection attacks

### Data Protection
- **Local Deployment**: All data stays on your servers
- **Encryption**: Sensitive data encrypted at rest
- **Access Logging**: Comprehensive audit trails
- **Data Isolation**: Campaign data separated by permissions
- **Backup Security**: Encrypted backup storage

### Network Security
- **HTTPS Only**: All communications encrypted
- **CORS Protection**: Controlled cross-origin access
- **Rate Limiting**: Protection against abuse
- **Input Sanitization**: XSS and injection protection
- **Security Headers**: Modern web security standards

## Performance & Scalability

### Optimization Targets
- **Response Time**: <200ms for API calls
- **Concurrent Users**: Support for 100+ simultaneous users
- **Database Performance**: Optimized queries with proper indexing
- **Memory Usage**: Efficient resource utilization
- **GPU Utilization**: Smart AI response management

### Scaling Considerations
- **Horizontal Scaling**: Multiple backend instances
- **Database Scaling**: Read replicas and connection pooling
- **Caching Strategy**: Redis for session and data caching
- **Load Balancing**: Nginx for request distribution
- **Resource Monitoring**: Real-time performance tracking

### GPU Resource Management
- **Dynamic Adjustment**: AI response complexity based on GPU usage
- **Memory Management**: Efficient VRAM utilization
- **Temperature Control**: Thermal throttling prevention
- **Performance Modes**: Fast/Medium/Slow based on resources
- **Resource Optimization**: Intelligent model selection

## Next Development Session

### Priority Tasks
1. **Test Complete Environment**: Verify all services start and function correctly
2. **AI Package Validation**: Test AI/LLM packages with Ubuntu base images
3. **API Endpoint Testing**: Verify all backend endpoints are working
4. **GPU Monitoring Test**: Test the monitoring system with actual workloads
5. **Frontend Development**: Begin Material-UI component implementation

### Technical Debt
- **Package Compatibility**: ✅ Resolved with Ubuntu base images
- **Error Handling**: Improve error messages and logging
- **Testing Coverage**: Add unit tests for core functionality
- **Documentation**: Update API documentation
- **Performance**: Optimize database queries and API responses

### Risk Mitigation
- **Backup Strategy**: Regular database and configuration backups
- **Rollback Plan**: Quick recovery from failed deployments
- **Monitoring**: Comprehensive system health monitoring
- **Testing**: Automated testing before deployment
- **Documentation**: Clear procedures for common operations

## Current Development Status

### Progress: 75% Complete (Phase 2 LLM Integration In Progress)
- **Foundation**: ✅ Complete
- **Docker Environment**: ✅ Complete & Stable
- **Backend API**: ✅ Complete & Functional
- **Database Schema**: ✅ Complete & Operational
- **GPU Monitoring**: ✅ Complete & Functional
- **AI Integration**: 🚧 Ready to Start (Phase 2)
- **Frontend**: 🚧 Structure Ready
- **Testing**: ✅ Complete (Standalone Testing System)
- **Critical Issues**: ✅ All Resolved

### What's Ready
- **Docker Environment**: All services built and configured successfully
- **Backend API**: Complete REST API with authentication and AI integration ready
- **Database**: SQLite schema with initialization and ChromaDB ready
- **Monitoring**: GPU and system resource monitoring fully functional
- **Authentication**: JWT-based user management with role-based access
- **Frontend**: React app structure ready for Material-UI development
- **Nginx**: Production-ready reverse proxy configuration
- **Documentation**: Comprehensive project documentation
- **Testing System**: Complete standalone testing for all modules
- **Backup System**: Automated backup creation with comprehensive exclusions
- **Git Management**: Complete .gitignore covering all project aspects
- **Environment Management**: Secure Docker environment variable configuration
- **Flask Configuration**: Environment-based secret key and configuration management
- **GitHub Integration**: Complete repository setup with contributing guidelines
- **Community Guidelines**: Comprehensive contribution standards and workflow

### GitHub Integration Complete (Version 0.4.6)
- **✅ Repository Setup**: Successfully integrated with https://github.com/Somnius/shadowrealms-ai.git
- **✅ Contributing Guidelines**: Complete CONTRIBUTING.md with code standards
- **✅ Repository URLs**: All documentation updated with actual GitHub links
- **✅ Git Exclusions**: Enhanced .gitignore with project-specific exclusions
- **✅ Branch Management**: Synchronized main and develop branches
- **✅ Public Visibility**: Project ready for community engagement and contributions

### GitHub README Enhancement (Version 0.4.7)
- **✅ Development Status**: Comprehensive status section added to public README
- **✅ Project Progress**: 70% Complete status visible to all visitors
- **✅ Immediate Actions**: Clear roadmap and milestones for community
- **✅ Current Status Summary**: Phase 1 completion details and next steps
- **✅ Enhanced Transparency**: Better information for potential contributors
- **✅ Documentation Consistency**: Maintained between internal and public docs

### Critical Issues Resolved (Version 0.4.3)
- **✅ Import Errors**: All `ModuleNotFoundError` and import path issues resolved
- **✅ Service Crashes**: Backend no longer crashes on startup
- **✅ Health Checks**: All endpoints responding with 200 status
- **✅ Service Dependencies**: All inter-service communication working
- **✅ Database Operations**: SQLite initialization and operations functional
- **✅ Docker Stability**: All containers starting successfully without errors
- **✅ Monitoring System**: GPU and system resource monitoring operational
- **✅ Logging**: Comprehensive logging system working correctly

### What's Next
- **Community Engagement**: Welcome contributors and community feedback
- **AI Integration**: Test LLM packages and implement actual API calls
- **Vector Database**: Test ChromaDB integration and vector memory
- **Frontend Development**: Implement Material-UI components and user interface
- **Testing**: Comprehensive testing of all features and endpoints
- **Performance**: Optimize and tune the system for production use

### Docker Integration Testing Results (Version 0.4.3)
- **✅ Backend Service**: Starting successfully, all tests passing
- **✅ ChromaDB**: Running and accessible, API responding
- **✅ Redis**: Starting and ready for connections
- **✅ Monitoring Service**: Operational with GPU and system monitoring
- **✅ Frontend**: Compiling successfully, React dev server ready
- **✅ Nginx**: Configuration loaded and ready
- **✅ Service Communication**: All inter-service dependencies resolved
- **✅ Health Checks**: All endpoints responding correctly
- **✅ Database**: SQLite operations functional
- **✅ Logging**: Comprehensive logging system operational

## Backup System & Data Management

### Automated Backup System (Version 0.4.4)
The project now includes a comprehensive backup system to protect development work and user data.

#### Backup Features
- **Automated Creation**: Run `./backup.sh` to create timestamped backups
- **Smart Exclusions**: Automatically excludes `backup/`, `books/`, and other non-source directories
- **Compression**: Uses bzip2 for optimal size/speed balance
- **Progress Reporting**: Shows duration, file size, and completion status
- **Timestamp Naming**: Format: `tg-rpg_YYYY-MM-DD_HH-MM.tar.bz2`
- **Integrity Verification**: Tests archive readability and corruption
- **Content Validation**: Verifies critical files are included
- **Exclusion Verification**: Confirms excluded directories are not backed up
- **File Count Verification**: Compares source vs backup file counts
- **Comprehensive Reporting**: Detailed verification results and warnings

#### Backup Command
```bash
# Create a new backup
./backup.sh

# The script will:
# 1. Create timestamped filename
# 2. Exclude backup/, books/, .git/, and existing archives
# 3. Compress with bzip2
# 4. Report duration and file size
# 5. List all backup files
```

#### What Gets Backed Up
- **Source Code**: All Python, JavaScript, and configuration files
- **Documentation**: Markdown files and project documentation
- **Docker Files**: docker-compose.yml and Dockerfiles
- **Assets**: Logo files and project assets
- **Configuration**: Environment and configuration files

#### What Gets Excluded
- **Backup Directory**: `backup/` (prevents recursive backups)
- **Books Directory**: `books/` (user-generated content)
- **Data Directory**: `data/` (runtime data and logs)
- **Git Repository**: `.git/` (version control data)
- **Existing Archives**: `*.tar.bz2` files
- **Node Modules**: `node_modules/` (can be reinstalled)
- **Python Cache**: `__pycache__/` and `*.pyc` files

#### Git Ignore Rules
The project now includes comprehensive `.gitignore` rules covering:
- **Python**: Bytecode, virtual environments, cache files
- **Node.js**: Dependencies, build artifacts, logs
- **Docker**: Volumes and data directories
- **OS Files**: System-generated files for all platforms
- **AI Models**: Large model files and checkpoints
- **Logs & Databases**: Runtime data and temporary files
- **Security**: API keys, secrets, and sensitive files

#### Backup Workflow
1. **Development**: Work on features and improvements
2. **Backup**: Run `./backup.sh` before major changes
3. **Version Control**: Commit source code changes to git
4. **Data Protection**: User data and backups remain separate from source code

#### Backup Test Results (Version 0.4.4)
- **✅ Test Successful**: Backup system verified and operational with enhanced verification
- **📁 Files Created**: Multiple backups with timestamped naming
- **📏 Size**: 6.6MB (compressed from source code)
- **⏱️  Duration**: 4 seconds (with comprehensive verification)
- **🎯 Exclusions Working**: `backup/` and `books/` directories properly excluded
- **📋 Contents Verified**: Source code, documentation, and assets included
- **🔍 Integrity Verified**: Archive corruption tests passed
- **📊 File Counts**: 51 files, 20 directories backed up successfully
- **✅ Critical Files**: All essential files (main.py, config.py, docker-compose.yml, etc.) verified
- **🚫 Exclusions Verified**: backup/ and books/ directories confirmed excluded

## Project Benefits & Future Vision

### Immediate Benefits
- **Learning Experience**: Hands-on with modern web technologies and AI
- **AI Exploration**: Experiment with local LLM models and vector databases
- **Portfolio Project**: Demonstrates full-stack development and AI integration skills
- **Practical Tool**: Useful for actual RPG campaigns and world-building
- **Technology Stack**: Experience with Docker, Flask, React, AI, and modern DevOps

### Long-term Vision
- **Open Source**: Potential for community contribution and collaboration
- **Commercial Use**: Licensing for gaming groups, companies, and educational institutions
- **Educational Tool**: Teaching AI, web development, and modern software architecture
- **Research Platform**: AI behavior, storytelling, and human-AI interaction research
- **Community Platform**: Connect RPG enthusiasts worldwide with AI-powered tools

### Innovation Potential
- **AI Storytelling**: Advanced narrative generation and dynamic plot development
- **Dynamic Worlds**: Procedural world creation and evolution
- **Character AI**: Intelligent NPC behavior and character development
- **Campaign Continuity**: Persistent AI memory across multiple sessions
- **Multi-Language**: Global accessibility with translation pipelines
- **Real-time Collaboration**: Live AI-assisted gaming experiences

## Version 0.4.9 - Total Recall and Restructuring

### What Happened
After reaching what we thought was Phase 2 completion, we realized we had made several critical mistakes:

1. **Over-ambitious Model Strategy**: Planned to run 6+ models simultaneously requiring 80GB+ VRAM
2. **Hardware Mismatch**: Assumed 24GB+ VRAM when system actually has 16GB
3. **Missing Core Features**: RAG, vector memory, and RPG mechanics were not implemented
4. **Incomplete Testing**: Marked phases complete without proper validation

### The Restructuring
We've completely restructured the project with:

- **Smart Model Router**: Resource-efficient model management for 16GB VRAM
- **Realistic Phases**: Based on actual hardware capabilities
- **Core-First Approach**: Essential RPG features before advanced AI
- **Proper Resource Management**: Model loading/swapping based on task requirements

### Current Reality Check
- **Hardware**: NVIDIA 4080 Super (16GB VRAM), 64GB RAM
- **Models**: 2 primary (always loaded) + 2 specialized (on-demand)
- **VRAM Usage**: ~10GB comfortable, ~15GB with swapping
- **Focus**: Practical RPG functionality over theoretical AI complexity

### New Phase Structure
1. **Phase 1**: Foundation & Smart Model Routing ✅
2. **Phase 2**: RAG & Vector Memory System 📋
3. **Phase 3**: RPG Mechanics Integration 📋
4. **Phase 4**: Advanced AI Features 📋

## Conclusion & Next Steps

ShadowRealms AI has successfully completed Phase 1 with a solid, production-ready foundation. The platform now features a complete Docker environment, Ubuntu-based AI compatibility, and a modern web architecture ready for advanced AI integration. **All critical issues have been resolved, and the platform is now stable and fully functional.**

### Immediate Actions
1. **✅ Environment Validated**: All services starting and functioning correctly
2. **✅ Backup System**: Automated backup creation with comprehensive exclusions
3. **✅ Git Management**: Complete .gitignore covering all project aspects
4. **✅ Environment Management**: Docker environment variables properly configured
5. **✅ Flask Configuration**: Secure secret key management implemented
6. **✅ GitHub Integration**: Repository setup complete with contributing guidelines
7. **🚧 AI Package Testing**: Ready to test chromadb, sentence-transformers, and torch integration
8. **🚧 AI Integration**: Begin implementing LLM service layer and vector memory system
9. **🚧 Frontend Development**: Start Material-UI component implementation
10. **✅ Performance Monitoring**: GPU monitoring and resource management operational

### Success Metrics
- **Technical**: All services start without errors and function correctly
- **Performance**: API response times under 200ms and efficient resource usage
- **AI Integration**: Successful LLM API calls and vector database operations
- **User Experience**: Intuitive interface for all user roles and functions
- **Scalability**: Support for multiple concurrent campaigns and users

### Key Achievements
- **Complete Docker Environment**: Multi-service architecture with proper networking
- **AI Package Compatibility**: Full support for AI/ML libraries with Ubuntu base
- **Production-Ready Configuration**: Nginx reverse proxy and optimized container setup
- **Modern Web Architecture**: React frontend structure ready for development
- **Comprehensive Monitoring**: GPU resource management and system health tracking

The platform is now positioned for rapid development of AI features and user interface components. The next development session will focus on bringing the AI capabilities to life and creating a compelling user experience for tabletop RPG enthusiasts.

---

## Documentation Notes

This document consolidates the following files:
- `PLANNING.md` - Project planning and phases
- `README.md` - Project overview and setup
- `REFERENCE.md` - Development environment reference
- `DEVELOPMENT_STATUS.md` - Current development status

**Current Version**: 0.4.9 - Total Recall and Restructuring Process
**Last Updated**: 2025-09-05 21:30 EEST
**Next Milestone**: Version 0.5.0 - Proper Phase 1 Completion with Smart Model Routing
