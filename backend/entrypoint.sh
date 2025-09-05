#!/bin/bash
set -e

# ShadowRealms AI Backend Entrypoint Script

echo "🚀 Starting ShadowRealms AI Backend..."

# Wait for ChromaDB to be ready
echo "⏳ Waiting for ChromaDB to be ready..."
echo "   Testing ChromaDB connection..."
curl -v http://localhost:8000/api/v2/heartbeat || echo "   ChromaDB connection failed"
echo "   Testing with timeout..."
timeout 5 curl -f http://localhost:8000/api/v2/heartbeat && echo "   ChromaDB is ready!" || echo "   ChromaDB still not ready, continuing anyway..."

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
