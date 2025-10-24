#!/usr/bin/env python3
"""
Quick Import Script for Core WoD Books
Imports the three core Revised books into ChromaDB
"""

import json
import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings

def main():
    print("🚀 ShadowRealms AI - Core Books Import")
    print("=" * 60)
    
    # Connect to ChromaDB
    try:
        client = chromadb.HttpClient(
            host='localhost',
            port=8000,
            settings=Settings(allow_reset=False)
        )
        print("✅ Connected to ChromaDB")
    except Exception as e:
        print(f"❌ Failed to connect to ChromaDB: {e}")
        return 1
    
    # Check current status
    try:
        collection = client.get_collection('rule_books')
        current_count = collection.count()
        print(f"📚 Current rule_books collection: {current_count} chunks")
        
        if current_count > 0:
            # Check what's already there
            sample = collection.peek(limit=5)
            existing_books = set()
            if sample and 'metadatas' in sample:
                existing_books = set([m.get('filename', 'unknown') for m in sample['metadatas']])
            print(f"   Existing books: {existing_books}")
    except:
        print("📚 rule_books collection doesn't exist yet")
        collection = client.create_collection(
            name='rule_books',
            metadata={"description": "World of Darkness rule books"}
        )
        current_count = 0
        print("✅ Created rule_books collection")
    
    # Core books to import
    core_books = [
        'core_books/parsed/Vampire -  the Masquerade - Revised.json',
        'core_books/parsed/Werewolf the Apocalypse Core (Revised).json',
        'core_books/parsed/Mage the Ascension Revised.json'
    ]
    
    # Import each book
    total_imported = 0
    for book_path in core_books:
        path = Path(book_path)
        if not path.exists():
            print(f"⚠️  {path.name} not found, skipping")
            continue
        
        print(f"\n📖 Processing: {path.name}")
        
        try:
            # Load parsed book data
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data['metadata']
            chunks = data['chunks']
            
            print(f"   System: {metadata['system']}")
            print(f"   Chunks: {len(chunks)}")
            print(f"   Processing...")
            
            # Prepare batch data (ChromaDB has max batch size)
            batch_size = 500
            imported = 0
            
            for batch_start in range(0, len(chunks), batch_size):
                batch_end = min(batch_start + batch_size, len(chunks))
                batch_chunks = chunks[batch_start:batch_end]
                
                ids = []
                documents = []
                metadatas = []
                
                for i, chunk in enumerate(batch_chunks):
                    chunk_id = f"{metadata['filename']}_{campaign_id}_{batch_start + i}"
                    ids.append(chunk_id)
                    documents.append(chunk['text'])
                    
                    chunk_metadata = {
                        'book_id': metadata['filename'],
                        'campaign_id': 0,  # Global access
                        'filename': metadata['filename'],
                        'system': metadata['system'],
                        'category': metadata['category'],
                        'page_number': chunk['page_number'],
                        'chunk_id': chunk['chunk_id'],
                        'word_count': chunk['word_count']
                    }
                    metadatas.append(chunk_metadata)
                
                # Import batch
                try:
                    collection.add(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                    imported += len(batch_chunks)
                    print(f"   Progress: {imported}/{len(chunks)} chunks", end='\r')
                except Exception as e:
                    print(f"\n   ⚠️  Batch error (might already exist): {str(e)[:100]}")
                    continue
            
            print(f"\n   ✅ Imported {imported} chunks from {path.name}")
            total_imported += imported
            
        except Exception as e:
            print(f"   ❌ Error processing {path.name}: {e}")
            continue
    
    # Final status
    print(f"\n{'='*60}")
    print(f"📊 Import Summary:")
    print(f"   Total chunks imported: {total_imported}")
    final_count = collection.count()
    print(f"   Final collection size: {final_count}")
    print(f"\n✅ Import complete!")
    
    return 0

if __name__ == '__main__':
    # Fix campaign_id variable
    campaign_id = 0  # Global access
    sys.exit(main())

