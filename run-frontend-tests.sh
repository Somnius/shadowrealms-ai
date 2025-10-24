#!/bin/bash
# ShadowRealms AI - Frontend Test Runner
# Runs all frontend tests inside the Docker container

echo "🧪 Running ShadowRealms AI Frontend Tests..."
echo "============================================"

# Check if frontend container is running
if ! docker compose ps frontend | grep -q "Up"; then
    echo "⚠️  Frontend container is not running. Starting it..."
    docker compose up -d frontend
    sleep 5
fi

echo ""
echo "📦 Running Security Tests..."
docker compose exec frontend npm test -- --testPathPattern=security.test.js --no-coverage --watchAll=false

echo ""
echo "📦 Running Integration Tests..."
docker compose exec frontend npm test -- --testPathPattern=userFlow.test.js --no-coverage --watchAll=false

echo ""
echo "📦 Running All Tests with Coverage..."
docker compose exec frontend npm test -- --coverage --watchAll=false

echo ""
echo "✅ Frontend tests completed!"
echo ""
echo "📊 Check coverage report in: frontend/coverage/"
echo ""

