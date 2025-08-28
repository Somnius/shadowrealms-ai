#!/bin/bash

# ShadowRealms AI - Docker Environment Test Script

echo "🚀 ShadowRealms AI - Docker Environment Test"
echo "=============================================="

# Check if Docker is running
echo "🐳 Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi
echo "✅ Docker is running"

# Check if Docker Compose is available
echo "🔧 Checking Docker Compose..."
if ! docker-compose --version > /dev/null 2>&1; then
    echo "❌ Docker Compose is not available"
    exit 1
fi
echo "✅ Docker Compose is available"

# Check project structure
echo "📁 Checking project structure..."
required_files=(
    "docker-compose.yml"
    "backend/Dockerfile"
    "backend/main.py"
    "backend/requirements.txt"
    "monitoring/Dockerfile"
    "monitoring/monitor.py"
    "monitoring/requirements.txt"
    "SHADOWREALMS_AI_COMPLETE.md"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file is missing"
        exit 1
    fi
done

# Check directories
required_dirs=(
    "backend"
    "frontend" 
    "monitoring"
    "data/logs"
    "data/uploads"
    "data/vector_db"
    "assets/logos"
)

for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir/ directory exists"
    else
        echo "❌ $dir/ directory is missing"
        exit 1
    fi
done

echo ""
echo "🎉 All checks passed! Ready to start Docker environment."
echo ""
echo "Next steps:"
echo "1. Run: docker-compose up --build"
echo "2. Wait for all services to start"
echo "3. Test the API at: http://localhost:5000"
echo "4. Check GPU monitoring at: http://localhost:5000/api/ai/status"
echo ""
echo "🚀 ShadowRealms AI is ready to launch! 🎮✨"
