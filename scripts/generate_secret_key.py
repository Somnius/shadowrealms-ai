#!/usr/bin/env python3
"""
ShadowRealms AI - Secret Key Generator
Generate secure Flask secret keys for your application
"""

import secrets
import string
import hashlib
import os
import uuid

def generate_random_key(length=32):
    """Generate a random secret key using secrets module"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_hex_key(length=32):
    """Generate a random hex key"""
    return secrets.token_hex(length)

def generate_urlsafe_key(length=32):
    """Generate a URL-safe random key"""
    return secrets.token_urlsafe(length)

def generate_uuid_based():
    """Generate a key based on UUID"""
    return str(uuid.uuid4()).replace('-', '')

def generate_hash_based():
    """Generate a key based on system information hash"""
    system_info = f"{os.getpid()}{os.getuid()}{os.uname()}"
    return hashlib.sha256(system_info.encode()).hexdigest()

def main():
    print("🔐 ShadowRealms AI - Secret Key Generator")
    print("=" * 50)
    
    print("\n📋 Generated Secret Keys:")
    print("-" * 30)
    
    # Method 1: Random characters
    key1 = generate_random_key(32)
    print(f"1. Random Characters (32 chars):")
    print(f"   {key1}")
    
    # Method 2: Hex key
    key2 = generate_hex_key(32)
    print(f"\n2. Hex Key (64 chars):")
    print(f"   {key2}")
    
    # Method 3: URL-safe key
    key3 = generate_urlsafe_key(32)
    print(f"\n3. URL-Safe Key (43 chars):")
    print(f"   {key3}")
    
    # Method 4: UUID-based
    key4 = generate_uuid_based()
    print(f"\n4. UUID-Based Key (32 chars):")
    print(f"   {key4}")
    
    # Method 5: Hash-based
    key5 = generate_hash_based()
    print(f"\n5. Hash-Based Key (64 chars):")
    print(f"   {key5}")
    
    print("\n💡 Recommendations:")
    print("- Use Method 2 (Hex Key) or Method 3 (URL-Safe) for Flask")
    print("- Method 2 is most secure and random")
    print("- Method 3 is good for URLs and cookies")
    print("- Copy the key you want to use")
    
    print("\n📝 Usage:")
    print("Copy one of the keys above and paste it in your .env file:")
    print("FLASK_SECRET_KEY=your-generated-key-here")
    print("")
    print("Example .env file:")
    print("FLASK_SECRET_KEY=7e99881cf6559187c323f08a1f3332cceccc7ceb2f641bab97b6f4fa73773e4e")
    
    print("\n⚠️  Security Notes:")
    print("- Never share your secret key")
    print("- Use different keys for development and production")
    print("- Store keys securely (not in version control)")
    print("- Rotate keys periodically in production")

if __name__ == "__main__":
    main()
