#!/usr/bin/env python3
"""
Test suite for Core Old World of Darkness Books in RAG System
Tests the three imported books: Vampire, Werewolf, and Mage
"""

import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_chromadb_connection():
    """Test that ChromaDB is accessible"""
    print("\n=== TESTING CHROMADB CONNECTION ===")
    try:
        client = chromadb.HttpClient(host='localhost', port=8000)
        heartbeat = client.heartbeat()
        print(f"✅ ChromaDB connected (heartbeat: {heartbeat}ns)")
        return client
    except Exception as e:
        print(f"❌ ChromaDB connection failed: {e}")
        sys.exit(1)

def test_rule_books_collection(client):
    """Test that rule_books collection exists and has data"""
    print("\n=== TESTING RULE_BOOKS COLLECTION ===")
    try:
        collection = client.get_collection('rule_books')
        count = collection.count()
        print(f"✅ rule_books collection exists")
        print(f"📊 Total chunks: {count}")
        
        if count == 0:
            print(f"❌ Collection is empty!")
            sys.exit(1)
        
        return collection
    except Exception as e:
        print(f"❌ rule_books collection error: {e}")
        sys.exit(1)

def test_core_books_imported(collection):
    """Test that all three core books are present"""
    print("\n=== TESTING CORE BOOKS ===")
    
    # Sample the collection to find book names
    sample = collection.get(limit=100)
    
    if not sample or 'metadatas' not in sample:
        print("❌ Could not retrieve collection metadata")
        sys.exit(1)
    
    # Extract unique book filenames
    books = set()
    for meta in sample['metadatas']:
        if 'filename' in meta:
            books.add(meta['filename'])
    
    print(f"📚 Books found in collection:")
    for book in sorted(books):
        print(f"   • {book}")
    
    # Check for the three core books
    required_books = {
        'Vampire -  the Masquerade - Revised.pdf',
        'Werewolf the Apocalypse Core (Revised).pdf',
        'Mage the Ascension Revised.pdf'
    }
    
    found_books = books & required_books
    missing_books = required_books - books
    
    if missing_books:
        print(f"\n⚠️  Missing books: {missing_books}")
    
    if len(found_books) == 3:
        print(f"\n✅ All three core books imported!")
    else:
        print(f"\n⚠️  Only {len(found_books)}/3 core books found")
    
    return len(found_books) == 3

def test_semantic_search(collection):
    """Test semantic search across all three books"""
    print("\n=== TESTING SEMANTIC SEARCH ===")
    
    test_queries = [
        {
            'query': 'What are the vampire clans in the Camarilla?',
            'expected_book': 'Vampire',
            'expected_system': 'vampire'
        },
        {
            'query': 'How does rage work for werewolves?',
            'expected_book': 'Werewolf',
            'expected_system': 'werewolf'
        },
        {
            'query': 'What are the nine spheres of magick?',
            'expected_book': 'Mage',
            'expected_system': 'mage'
        }
    ]
    
    all_passed = True
    
    for test in test_queries:
        query = test['query']
        print(f"\n🔍 Query: {query}")
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=5
            )
            
            if not results or 'metadatas' not in results or not results['metadatas']:
                print(f"   ❌ No results returned")
                all_passed = False
                continue
            
            # Check if any result is from the expected book
            found_expected = False
            for i, meta in enumerate(results['metadatas'][0][:3]):
                book = meta.get('filename', 'unknown')
                page = meta.get('page_number', '?')
                distance = results['distances'][0][i] if 'distances' in results else 'N/A'
                
                print(f"   {i+1}. {book} (p.{page}) - distance: {distance}")
                
                if test['expected_book'] in book:
                    found_expected = True
            
            if found_expected:
                print(f"   ✅ Found relevant content from {test['expected_book']}")
            else:
                print(f"   ⚠️  Expected {test['expected_book']} but not in top results")
                all_passed = False
                
        except Exception as e:
            print(f"   ❌ Query failed: {e}")
            all_passed = False
    
    return all_passed

def test_chunk_quality(collection):
    """Test the quality of stored chunks"""
    print("\n=== TESTING CHUNK QUALITY ===")
    
    # Get a sample of chunks
    sample = collection.get(limit=10)
    
    if not sample or 'documents' not in sample:
        print("❌ Could not retrieve documents")
        return False
    
    print(f"📄 Analyzing {len(sample['documents'])} sample chunks...")
    
    for i, (doc, meta) in enumerate(zip(sample['documents'], sample['metadatas'])):
        word_count = len(doc.split())
        book = meta.get('filename', 'unknown')
        page = meta.get('page_number', '?')
        
        if i < 2:  # Show first two as examples
            print(f"\n   Chunk {i+1}: {book} (p.{page})")
            print(f"   Words: {word_count}")
            print(f"   Preview: {doc[:100]}...")
        
        if word_count < 10:
            print(f"   ⚠️  Chunk {i+1} seems too short ({word_count} words)")
    
    print(f"\n✅ Chunk quality check complete")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  OLD WORLD OF DARKNESS CORE BOOKS - RAG SYSTEM TEST")
    print("="*70)
    
    # Run tests
    client = test_chromadb_connection()
    collection = test_rule_books_collection(client)
    books_ok = test_core_books_imported(collection)
    search_ok = test_semantic_search(collection)
    quality_ok = test_chunk_quality(collection)
    
    # Summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    print(f"✅ ChromaDB Connection: PASS")
    print(f"✅ Rule Books Collection: PASS")
    print(f"{'✅' if books_ok else '⚠️ '} Core Books Imported: {'PASS' if books_ok else 'PARTIAL'}")
    print(f"{'✅' if search_ok else '❌'} Semantic Search: {'PASS' if search_ok else 'FAIL'}")
    print(f"{'✅' if quality_ok else '❌'} Chunk Quality: {'PASS' if quality_ok else 'FAIL'}")
    
    if books_ok and search_ok and quality_ok:
        print("\n🎉 ALL TESTS PASSED! RAG system is ready for gameplay!")
        return 0
    else:
        print("\n⚠️  Some tests failed or incomplete")
        return 1

if __name__ == '__main__':
    sys.exit(main())

