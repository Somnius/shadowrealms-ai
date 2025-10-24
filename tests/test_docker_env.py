#!/usr/bin/env python3
"""
ShadowRealms AI - Docker Environment Test
Test environment variable configuration for Docker containers
"""

import os
import subprocess
import sys

def test_local_env():
    """Test local environment variables"""
    print("🔧 Testing Local Environment Variables")
    print("=" * 50)
    
    # Check if .env file exists
    if os.path.exists('.env'):
        print("✅ .env file found")
        
        # Load and display key variables
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if 'SECRET' in key or 'KEY' in key:
                        print(f"   {key}: {value[:20]}...")
                    else:
                        print(f"   {key}: {value}")
    else:
        print("❌ .env file not found")
        print("   Create it from template: cp env.template .env")
    
    print()

def test_docker_compose_env():
    """Test Docker Compose environment configuration"""
    print("🐳 Testing Docker Compose Environment Configuration")
    print("=" * 50)
    
    # Check docker-compose.yml
    if os.path.exists('docker-compose.yml'):
        print("✅ docker-compose.yml found")
        
        # Parse environment variables from docker-compose.yml
        with open('docker-compose.yml', 'r') as f:
            content = f.read()
            
        # Look for environment variables
        env_vars = []
        lines = content.split('\n')
        in_backend_env = False
        
        for line in lines:
            if 'backend:' in line:
                in_backend_env = False
            if 'environment:' in line:
                in_backend_env = True
                continue
            if in_backend_env and line.strip().startswith('-'):
                if '=' in line:
                    env_vars.append(line.strip())
                elif line.strip() == '-':
                    in_backend_env = False
        
        if env_vars:
            print("✅ Environment variables configured in docker-compose.yml:")
            for var in env_vars:
                print(f"   {var}")
        else:
            print("❌ No environment variables found in docker-compose.yml")
    else:
        print("❌ docker-compose.yml not found")
    
    print()

def test_docker_build():
    """Test Docker build configuration"""
    print("🔨 Testing Docker Build Configuration")
    print("=" * 50)
    
    # Check backend Dockerfile
    if os.path.exists('backend/Dockerfile'):
        print("✅ backend/Dockerfile found")
        
        with open('backend/Dockerfile', 'r') as f:
            content = f.read()
            
        # Check for environment variable handling
        if 'ENV' in content:
            print("✅ Dockerfile has ENV instructions")
        else:
            print("⚠️  Dockerfile missing ENV instructions")
            
        # Check for python-dotenv
        if 'python-dotenv' in content:
            print("✅ python-dotenv handling found")
        else:
            print("⚠️  python-dotenv handling not found")
    else:
        print("❌ backend/Dockerfile not found")
    
    print()

def test_config_loading():
    """Test configuration loading"""
    print("⚙️  Testing Configuration Loading")
    print("=" * 50)
    
    try:
        # Add backend to path
        sys.path.insert(0, '../backend')
        
        # Import config
        from config import Config
        
        print("✅ Config module imported successfully")
        
        # Test environment variable loading
        print(f"   FLASK_SECRET_KEY: {'*' * 10 if Config.SECRET_KEY != 'dev-secret-key-change-in-production' else 'DEFAULT'}")
        print(f"   JWT_SECRET_KEY: {'*' * 10 if Config.JWT_SECRET_KEY != 'jwt-secret-key-change-in-production' else 'DEFAULT'}")
        print(f"   FLASK_HOST: {Config.FLASK_HOST}")
        print(f"   FLASK_PORT: {Config.FLASK_PORT}")
        print(f"   FLASK_DEBUG: {Config.FLASK_DEBUG}")
        print(f"   DATABASE: {Config.DATABASE}")
        print(f"   CHROMADB_HOST: {Config.CHROMADB_HOST}")
        
    except ImportError as e:
        print(f"❌ Failed to import config: {e}")
    except Exception as e:
        print(f"❌ Error testing config: {e}")
    
    print()

def show_docker_commands():
    """Show Docker commands for testing"""
    print("🚀 Docker Testing Commands")
    print("=" * 50)
    
    print("1. Build and start containers:")
    print("   docker-compose up --build")
    print()
    
    print("2. Check container logs:")
    print("   docker-compose logs backend")
    print()
    
    print("3. Check environment variables in container:")
    print("   docker-compose exec backend env | grep FLASK")
    print()
    
    print("4. Test Flask app in container:")
    print("   docker-compose exec backend python -c \"from config import Config; Config.debug_env_vars()\"")
    print()
    
    print("5. Check container health:")
    print("   curl http://localhost:5000/health")
    print()

def main():
    print("🔐 ShadowRealms AI - Docker Environment Test")
    print("=" * 60)
    print()
    
    test_local_env()
    test_docker_compose_env()
    test_docker_build()
    test_config_loading()
    show_docker_commands()
    
    print("💡 Next Steps:")
    print("-" * 20)
    print("1. Generate secret keys: python generate_secret_key.py")
    print("2. Update .env file with generated keys")
    print("3. Test Docker build: docker-compose up --build")
    print("4. Check container logs for environment variable loading")

if __name__ == "__main__":
    main()
