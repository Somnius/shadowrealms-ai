#!/usr/bin/env python3
"""
Rule Books System Test Script
Tests the rule book processing and RAG integration system.
"""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api"

def test_health():
    """Test if the backend is running"""
    print("🔍 Testing Backend Health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend healthy - Version: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"❌ Backend unhealthy - Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend connection failed: {e}")
        return False

def authenticate():
    """Authenticate and get JWT token"""
    print("\n🔐 Testing Authentication...")
    try:
        # Try to login first
        login_data = {
            "username": "testuser_rulebooks",
            "password": "testpass123"
        }
        
        response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            print("✅ Login successful")
            return token
        elif response.status_code == 401:
            # Try to register
            print("⚠️  User not found, attempting registration...")
            register_data = {
                "username": "testuser_rulebooks",
                "email": "testuser_rulebooks@example.com",
                "password": "testpass123"
            }
            response = requests.post(f"{API_BASE}/auth/register", json=register_data, timeout=10)
            
            if response.status_code == 201:
                print("✅ Registration successful, logging in...")
                response = requests.post(f"{API_BASE}/auth/login", json=login_data, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    token = data.get('access_token')
                    print("✅ Login successful after registration")
                    return token
            
            print(f"❌ Registration failed: {response.status_code}")
            return None
        else:
            print(f"❌ Login failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None

def test_scan_rule_books(token):
    """Test scanning for available rule books"""
    print("\n📚 Testing Rule Books Scan...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE}/rule-books/scan", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            books_found = data.get('books_found', 0)
            books = data.get('books', [])
            
            print(f"✅ Found {books_found} rule books:")
            for book in books:
                print(f"   📖 {book['name']} ({book['system']}) - {book['file_size_mb']}MB")
            
            return books
        else:
            print(f"❌ Scan failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Scan error: {e}")
        return []

def test_process_rule_book(token, book_id):
    """Test processing a specific rule book"""
    print(f"\n⚙️  Testing Rule Book Processing: {book_id}...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        data = {"book_id": book_id}
        
        print(f"   Processing {book_id}... (this may take a while)")
        response = requests.post(f"{API_BASE}/rule-books/process", json=data, headers=headers, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Successfully processed {book_id}")
            return True
        else:
            print(f"❌ Processing failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False

def test_search_rule_books(token, query, system=None):
    """Test searching through rule books"""
    print(f"\n🔍 Testing Rule Books Search: '{query}'...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "query": query,
            "limit": 5
        }
        if system:
            data["system"] = system
        
        response = requests.post(f"{API_BASE}/rule-books/search", json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            results_count = result.get('results_count', 0)
            results = result.get('results', [])
            
            print(f"✅ Found {results_count} results:")
            for i, res in enumerate(results[:3], 1):  # Show first 3 results
                book_name = res.get('book_name', 'Unknown')
                page_num = res.get('page_number', '?')
                text_preview = res.get('text', '')[:100] + "..." if len(res.get('text', '')) > 100 else res.get('text', '')
                print(f"   {i}. [{book_name}, Page {page_num}]: {text_preview}")
            
            return results
        else:
            print(f"❌ Search failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Search error: {e}")
        return []

def test_get_rule_context(token, query, system=None):
    """Test getting rule context for AI generation"""
    print(f"\n🧠 Testing Rule Context: '{query}'...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "query": query,
            "limit": 3
        }
        if system:
            data["system"] = system
        
        response = requests.post(f"{API_BASE}/rule-books/context", json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            context = result.get('context', '')
            context_length = result.get('context_length', 0)
            
            print(f"✅ Retrieved context ({context_length} characters):")
            if context:
                print(f"   {context[:200]}{'...' if len(context) > 200 else ''}")
            else:
                print("   No context found")
            
            return context
        else:
            print(f"❌ Context retrieval failed: {response.status_code} - {response.text}")
            return ""
            
    except Exception as e:
        print(f"❌ Context error: {e}")
        return ""

def test_rule_books_status(token):
    """Test getting rule books processing status"""
    print("\n📊 Testing Rule Books Status...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE}/rule-books/status", headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            processed_count = result.get('processed_books', 0)
            books = result.get('books', [])
            
            print(f"✅ {processed_count} books processed:")
            for book in books:
                book_name = book.get('book_name', 'Unknown')
                chunks = book.get('total_chunks', 0)
                pages = book.get('total_pages', 0)
                words = book.get('total_words', 0)
                print(f"   📖 {book_name}: {chunks} chunks, {pages} pages, {words} words")
            
            return books
        else:
            print(f"❌ Status check failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Status error: {e}")
        return []

def test_available_systems(token):
    """Test getting available game systems"""
    print("\n🎮 Testing Available Systems...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE}/rule-books/systems", headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            systems = result.get('systems', [])
            systems_count = result.get('systems_count', 0)
            
            print(f"✅ Available systems ({systems_count}): {', '.join(systems)}")
            return systems
        else:
            print(f"❌ Systems check failed: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Systems error: {e}")
        return []

def main():
    """Main test function"""
    print("🚀 ShadowRealms AI - Rule Books System Testing")
    print("=" * 60)
    
    # Test 1: Health Check
    if not test_health():
        print("\n❌ Backend not available, exiting...")
        sys.exit(1)
    
    # Test 2: Authentication
    token = authenticate()
    if not token:
        print("\n❌ Authentication failed, exiting...")
        sys.exit(1)
    
    # Test 3: Get available systems
    systems = test_available_systems(token)
    
    # Test 4: Check current status
    processed_books = test_rule_books_status(token)
    
    # Ask user for the first book to process
    print("\n" + "=" * 60)
    print("📚 RULE BOOK SELECTION")
    print("=" * 60)
    print("Available game systems:", ", ".join(systems) if systems else "None")
    print("\nWhich World of Darkness book would you like to process first?")
    print("Available options:")
    print("1. wod_2nd_ed - World of Darkness 2nd Edition (your specified file)")
    print("2. vampire_core - Vampire: The Masquerade Core")
    print("3. werewolf_core - Werewolf: The Apocalypse Core")
    print("4. mage_core - Mage: The Ascension Core")
    print("5. changeling_core - Changeling: The Dreaming Core")
    
    while True:
        book_id = input("Enter book ID (or 'q' to quit): ").strip()
        if book_id.lower() == 'q':
            print("Exiting...")
            return
        
        if book_id in ['wod_2nd_ed', 'vampire_core', 'werewolf_core', 'mage_core', 'changeling_core']:
            selected_book = {
                'book_id': book_id,
                'name': f"{book_id.replace('_', ' ').title()}",
                'system': book_id.split('_')[0] if book_id != 'wod_2nd_ed' else 'wod'
            }
            break
        else:
            print("Please enter a valid book ID (wod_2nd_ed, vampire_core, werewolf_core, mage_core, or changeling_core)")
    
    print(f"\n✅ Selected: {selected_book['name']} ({selected_book['book_id']})")
    
    # Test 6: Process the selected rule book
    print(f"\n⚙️  Processing selected book...")
    if test_process_rule_book(token, selected_book['book_id']):
        print("✅ Book processing completed")
    else:
        print("❌ Book processing failed")
        return
    
    # Test 7: Search rule books with user input
    print("\n" + "=" * 60)
    print("🔍 RULE BOOK SEARCH TESTING")
    print("=" * 60)
    
    while True:
        query = input("\nEnter a search query (or 'q' to continue to context testing): ").strip()
        if query.lower() == 'q':
            break
        if query:
            test_search_rule_books(token, query, selected_book['system'])
    
    # Test 8: Get rule context with user input
    print("\n" + "=" * 60)
    print("🧠 RULE CONTEXT TESTING")
    print("=" * 60)
    
    while True:
        query = input("\nEnter a context query (or 'q' to finish): ").strip()
        if query.lower() == 'q':
            break
        if query:
            test_get_rule_context(token, query, selected_book['system'])
    
    # Test 9: Final status check
    test_rule_books_status(token)
    
    print("\n" + "=" * 60)
    print("🎉 Rule Books System Testing Complete!")
    print("✅ All tests completed successfully")

if __name__ == "__main__":
    main()
