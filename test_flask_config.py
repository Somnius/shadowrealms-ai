#!/usr/bin/env python3
"""
ShadowRealms AI - Flask Configuration Test
Test that Flask configuration properly loads environment variables
"""

import os
import sys

def test_env_loading():
    """Test environment variable loading"""
    print("🔧 Testing Flask Configuration Environment Variables")
    print("=" * 60)
    
    # Test if .env file exists
    if os.path.exists('.env'):
        print("✅ .env file found")
        
        # Load .env file manually for testing
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key == 'FLASK_SECRET_KEY':
                        if value == 'your-super-secret-key-here-change-this':
                            print("⚠️  FLASK_SECRET_KEY still has default value")
                        else:
                            print(f"✅ FLASK_SECRET_KEY loaded: {value[:20]}...")
                    elif key == 'JWT_SECRET_KEY':
                        if value == 'your-jwt-secret-key-here-change-this':
                            print("⚠️  JWT_SECRET_KEY still has default value")
                        else:
                            print(f"✅ JWT_SECRET_KEY loaded: {value[:20]}...")
    else:
        print("❌ .env file not found")
        print("   Create it from template: cp env.template .env")
    
    print("\n📋 Environment Variables Check:")
    print("-" * 40)
    
    # Check critical Flask variables
    flask_vars = [
        'FLASK_SECRET_KEY',
        'FLASK_HOST',
        'FLASK_PORT',
        'FLASK_DEBUG',
        'JWT_SECRET_KEY'
    ]
    
    for var in flask_vars:
        value = os.environ.get(var)
        if value:
            if 'change-this' in value or 'your-' in value:
                print(f"⚠️  {var}: {value[:30]}... (needs updating)")
            else:
                print(f"✅ {var}: {value[:30]}...")
        else:
            print(f"❌ {var}: Not set")
    
    print("\n🧪 Testing Flask Config Import:")
    print("-" * 40)
    
    try:
        # Try to import the config
        sys.path.append('backend')
        from config import Config
        
        print("✅ Config module imported successfully")
        
        # Test secret key loading
        secret_key = Config.SECRET_KEY
        if secret_key and secret_key != 'dev-secret-key-change-in-production':
            print(f"✅ Flask SECRET_KEY loaded: {secret_key[:20]}...")
        else:
            print("⚠️  Flask SECRET_KEY using fallback value")
        
        # Test JWT secret key
        jwt_key = Config.JWT_SECRET_KEY
        if jwt_key and jwt_key != 'jwt-secret-key-change-in-production':
            print(f"✅ JWT_SECRET_KEY loaded: {jwt_key[:20]}...")
        else:
            print("⚠️  Flask JWT_SECRET_KEY using fallback value")
        
        # Test other Flask config
        print(f"✅ Flask Host: {Config.FLASK_HOST}")
        print(f"✅ Flask Port: {Config.FLASK_PORT}")
        print(f"✅ Flask Debug: {Config.FLASK_DEBUG}")
            
    except ImportError as e:
        print(f"❌ Failed to import config: {e}")
    except Exception as e:
        print(f"❌ Error testing config: {e}")
    
    print("\n💡 Next Steps:")
    print("-" * 20)
    
    if not os.path.exists('.env'):
        print("1. Create .env file: cp env.template .env")
        print("2. Generate secret keys: python generate_secret_key.py")
        print("3. Update .env with generated keys")
    else:
        print("1. Generate secret keys: python generate_secret_key.py")
        print("2. Update .env with generated keys")
        print("3. Test Flask app: cd backend && python main.py --run")
    
    print("\n🔒 Security Checklist:")
    print("-" * 25)
    print("☐ FLASK_SECRET_KEY is unique and secure")
    print("☐ JWT_SECRET_KEY is unique and secure")
    print("☐ .env file is in .gitignore")
    print("☐ No sensitive keys in version control")

if __name__ == "__main__":
    test_env_loading()
