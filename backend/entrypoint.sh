#!/bin/bash
set -e

# ShadowRealms AI Backend Entrypoint Script

echo "🚀 Starting ShadowRealms AI Backend..."

# Wait for ChromaDB to be ready
echo "⏳ Waiting for ChromaDB to be ready..."
echo "   Testing ChromaDB connection..."
# Use CHROMADB_HOST environment variable (defaults to chromadb for Docker)
CHROMADB_HOST=${CHROMADB_HOST:-chromadb}
CHROMADB_PORT=${CHROMADB_PORT:-8000}
echo "   Connecting to http://${CHROMADB_HOST}:${CHROMADB_PORT}..."

# Wait up to 30 seconds for ChromaDB to be ready
for i in {1..30}; do
    if curl -sf "http://${CHROMADB_HOST}:${CHROMADB_PORT}/api/v2/heartbeat" > /dev/null 2>&1; then
        echo "✅ ChromaDB is ready!"
        break
    fi
    echo "   Attempt $i: ChromaDB not ready yet, waiting..."
    sleep 1
done

# Wait for monitoring service to be ready
echo "⏳ Waiting for monitoring service to be ready..."
until [ -f /app/logs/system_status.json ]; do
    echo "   Monitoring service not ready yet, waiting..."
    sleep 2
done
echo "✅ Monitoring service is ready!"

# Initialize database
echo "🗄️  Initializing database..."
if [ -f /app/data/shadowrealms.db ]; then
    echo "✅ Database already exists"
else
    echo "📝 Creating new database..."
    python -c "from database import init_db; init_db()"
    echo "✅ Database created successfully"
fi

# Start Flask application
echo "🌐 Starting Flask application..."
exec python main.py --run
