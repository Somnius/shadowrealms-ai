# 🐳 Docker Environment Variables Setup

This guide explains how environment variables work in the ShadowRealms AI Docker setup and how to configure them properly.

## 🔍 **How It Works**

### **1. Local Development (.env file)**
- `.env` file contains your local configuration
- Used when running Flask directly (not in Docker)
- Contains sensitive information (API keys, secret keys)

### **2. Docker Containers (docker-compose.yml)**
- Environment variables are passed from host to containers
- Uses `${VARIABLE_NAME:-default_value}` syntax
- Falls back to default values if not set

### **3. Flask Application (config.py)**
- Reads environment variables using `os.environ.get()`
- Has fallback values for development
- Logs configuration for debugging

## 🚀 **Quick Setup**

### **Step 1: Generate Secret Keys**
```bash
# Generate secure keys
python scripts/generate_secret_key.py

# Copy the hex key (most secure)
# Example: 7e99881cf6559187c323f08a1f3332cceccc7ceb2f641bab97b6f4fa73773e4e
```

### **Step 2: Create .env File**
```bash
# Copy template
cp env.template .env

# Edit .env with your keys
nano .env

# Update these lines:
FLASK_SECRET_KEY=your-generated-secret-key-from-generate-script
JWT_SECRET_KEY=your-jwt-secret-key-here
```

### **Step 3: Test Configuration**
```bash
# Test local environment
python3 tests/test_flask_config.py

# Test Docker configuration
python3 tests/test_docker_env.py
```

### **Step 4: Start Docker**

**Option A — root helper script (recommended)**  
From the **repository root**, `docker-up.sh` changes to that directory and runs `docker compose up -d` so every service starts in detached mode:

```bash
chmod +x docker-up.sh   # only needed once if the file is not executable
./docker-up.sh
```

Extra Compose CLI arguments are forwarded (for example rebuild images before starting):

```bash
./docker-up.sh --build
```

**Option B — Compose CLI**  
Equivalent manual commands:

```bash
# Build and start containers (foreground; add -d for detached)
docker compose up --build

# Check logs for environment variable loading
docker compose logs backend
```

Requires Docker with the **Compose V2** plugin (`docker compose`).

## 🗄️ PostgreSQL Schema Initialization (Tables)

If you are using PostgreSQL (`DATABASE_TYPE=postgresql`), the **database tables must exist** before login/registration/campaign features will work.

### Minimum required tables (fresh install)

At minimum (for login + create campaign + OOC room), PostgreSQL must have:

- `users`
- `campaigns`
- `campaign_players`
- `locations`

For the broader app/admin UI to function without “relation does not exist” errors, you should also have:

- `characters`
- `character_locations`
- `messages`
- `user_moderation_log`
- `ai_interactions`
- `ai_memory`
- `dice_rolls`
- `dice_roll_templates`
- `npcs`
- `npc_messages`
- `location_deletion_log`

### Verify tables exist

```bash
docker compose exec postgresql psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt'
```

If you see **no relations**, PostgreSQL started without initializing the schema.

### Why this happens after cloning

`docker-compose.yml` mounts an init SQL file into Postgres:

- `./backend/init_postgresql_schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro`

If `backend/init_postgresql_schema.sql` is missing or not a valid SQL **file**, Postgres will come up empty.

### Fix (re-run init script)

1. Ensure `backend/init_postgresql_schema.sql` is present as a **file**
2. Recreate the Postgres volume so init scripts run:

```bash
docker compose down
docker volume rm shadowrealms-ai_postgresql_data
docker compose up -d postgresql
docker compose exec postgresql psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt'
```

## 🔧 **Environment Variable Flow**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   .env file     │    │ docker-compose  │    │ Flask Container │
│   (local)       │───►│   .yml          │───►│   (config.py)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Example Flow:**
1. **`.env` file**: `FLASK_SECRET_KEY=abc123...`
2. **docker-compose.yml**: `FLASK_SECRET_KEY=${FLASK_SECRET_KEY:-default}`
3. **Container**: Gets `abc123...` from host environment
4. **Flask app**: Reads `FLASK_SECRET_KEY` from container environment

## 📋 **Required Environment Variables**

### **Critical (Must Set):**
```bash
FLASK_SECRET_KEY=your-secure-key-here
JWT_SECRET_KEY=your-jwt-key-here
```

### **Important (Should Set):**
```bash
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
DATABASE=/app/data/shadowrealms.db
CHROMADB_HOST=chromadb
REDIS_HOST=redis
```

### **Optional (Have Defaults):**
```bash
GPU_THRESHOLD_HIGH=80
GPU_THRESHOLD_MEDIUM=60
LOG_LEVEL=INFO
```

## 🧪 **Testing Environment Variables**

### **Test Local Configuration:**
```bash
python3 tests/test_flask_config.py
```

### **Test Docker Configuration:**
```bash
python3 tests/test_docker_env.py
```

### **Test Running Container:**
```bash
# Check environment variables in container
docker-compose exec backend env | grep FLASK

# Test Flask config in container
docker-compose exec backend python -c "from config import Config; Config.debug_env_vars()"

# Check container health
curl http://localhost:5000/health
```

## 🔒 **Security Best Practices**

### **✅ Do:**
- Generate unique secret keys for each environment
- Use different keys for development vs production
- Keep `.env` file in `.gitignore`
- Rotate keys periodically in production

### **❌ Don't:**
- Use default secret keys in production
- Commit `.env` files to version control
- Share secret keys between team members
- Use the same keys for different projects

## 🐛 **Troubleshooting**

### **Problem: Environment variables not loading in Docker**
```bash
# Check if .env file exists
ls -la .env

# Verify docker-compose.yml has environment section
grep -A 20 "environment:" docker-compose.yml

# Check container logs
docker-compose logs backend

# Test environment variables in container
docker-compose exec backend env | grep FLASK
```

### **Problem: Secret keys still using defaults**
```bash
# Generate new keys
python scripts/generate_secret_key.py

# Update .env file
nano .env

# Restart containers
docker-compose down
docker-compose up --build
```

### **Problem: Configuration not loading**
```bash
# Test local config
python3 tests/test_flask_config.py

# Test Docker config
python3 tests/test_docker_env.py

# Check Python path in container
docker-compose exec backend python -c "import sys; print(sys.path)"
```

## 📚 **Advanced Configuration**

### **Multiple Environment Files:**
```bash
# Development
cp env.template .env.development

# Production
cp env.template .env.production

# Use specific file
docker-compose --env-file .env.production up
```

### **Environment-Specific Docker Compose:**
```yaml
# docker-compose.override.yml (development)
services:
  backend:
    environment:
      - FLASK_DEBUG=true
      - LOG_LEVEL=DEBUG

# docker-compose.prod.yml (production)
services:
  backend:
    environment:
      - FLASK_DEBUG=false
      - LOG_LEVEL=WARNING
```

## 🎯 **Next Steps**

1. **Generate secure keys** using `scripts/generate_secret_key.py`
2. **Update .env file** with your keys
3. **Test configuration** using test scripts
4. **Start Docker containers** with `docker-compose up --build`
5. **Verify environment variables** are loaded correctly

---

**Your Docker environment is now properly configured for secure Flask development! 🚀**
