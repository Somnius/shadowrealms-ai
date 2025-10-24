#!/usr/bin/env python3
"""
Smart Book Import to RAG/Vector Database
Manages selective book imports based on campaign needs
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings

# Book set configurations for different campaign types
CAMPAIGN_BOOK_SETS = {
    'core_only': {
        'name': 'Core Rules Only',
        'description': 'Essential WoD mechanics only',
        'books': ['wod_2nd_ed'],
        'priority': 1
    },
    'vampire_full': {
        'name': 'Vampire: The Masquerade (Full)',
        'description': 'Complete Vampire game',
        'books': ['wod_2nd_ed', 'vampire_core', 'guide_to_camarilla', 'guide_to_sabbat'],
        'priority': 2
    },
    'vampire_basic': {
        'name': 'Vampire: The Masquerade (Basic)',
        'description': 'Core Vampire rules',
        'books': ['wod_2nd_ed', 'vampire_core'],
        'priority': 2
    },
    'werewolf_full': {
        'name': 'Werewolf: The Apocalypse (Full)',
        'description': 'Complete Werewolf game',
        'books': ['wod_2nd_ed', 'werewolf_core', 'tribal_guides', 'umbra_guide'],
        'priority': 2
    },
    'mage_basic': {
        'name': 'Mage: The Ascension (Basic)',
        'description': 'Core Mage rules',
        'books': ['wod_2nd_ed', 'mage_core'],
        'priority': 2
    },
    'crossover': {
        'name': 'Crossover Campaign',
        'description': 'Multiple WoD game lines',
        'books': ['wod_2nd_ed'],  # Start with core, add others as needed
        'priority': 1
    }
}


class SmartBookImporter:
    """Manages intelligent book imports to vector database"""
    
    def __init__(self, parsed_dir: Path, chromadb_host='localhost', chromadb_port=8000):
        self.parsed_dir = parsed_dir
        self.client = chromadb.HttpClient(
            host=chromadb_host,
            port=chromadb_port,
            settings=Settings(allow_reset=True)
        )
        self.collection_name = 'rule_books'
        
    def list_available_books(self) -> List[Dict[str, Any]]:
        """List all parsed books available for import"""
        books = []
        
        for json_file in self.parsed_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                books.append({
                    'file': json_file.name,
                    'filename': data['metadata']['filename'],
                    'system': data['metadata']['system'],
                    'category': data['metadata']['category'],
                    'pages': data['processing_info']['total_pages'],
                    'chunks': data['processing_info']['total_chunks'],
                    'has_embeddings': data['processing_info'].get('embeddings_generated', False),
                    'path': str(json_file)
                })
            except Exception as e:
                print(f"Error reading {json_file}: {e}")
                
        return sorted(books, key=lambda x: (x['system'], x['filename']))
    
    def import_book(self, json_path: Path, book_id: str, campaign_id: int = 0,
                    batch_size: int = 100) -> bool:
        """
        Import a single book to ChromaDB
        
        Args:
            json_path: Path to parsed JSON file
            book_id: Unique identifier for this book
            campaign_id: 0 for global, >0 for campaign-specific
            batch_size: Number of chunks to insert at once
        """
        try:
            print(f"\n📚 Importing book: {json_path.name}")
            
            # Load parsed data
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = data['metadata']
            chunks = data['chunks']
            has_embeddings = data['processing_info'].get('embeddings_generated', False)
            
            print(f"   System: {metadata['system']}")
            print(f"   Chunks: {len(chunks)}")
            print(f"   Embeddings: {'✓' if has_embeddings else '✗'}")
            
            # Get or create collection
            try:
                collection = self.client.get_collection(self.collection_name)
            except:
                collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "World of Darkness rule books"}
                )
            
            # Prepare data for batch insert
            ids = []
            documents = []
            metadatas = []
            embeddings = [] if has_embeddings else None
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{book_id}_{campaign_id}_{chunk['chunk_id']}"
                ids.append(chunk_id)
                documents.append(chunk['text'])
                
                chunk_metadata = {
                    'book_id': book_id,
                    'campaign_id': campaign_id,
                    'filename': metadata['filename'],
                    'system': metadata['system'],
                    'category': metadata['category'],
                    'page_number': chunk['page_number'],
                    'chunk_id': chunk['chunk_id'],
                    'word_count': chunk['word_count']
                }
                metadatas.append(chunk_metadata)
                
                if has_embeddings:
                    embeddings.append(chunk['embedding'])
            
            # Insert in batches
            total_inserted = 0
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i+batch_size]
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                
                if has_embeddings:
                    batch_emb = embeddings[i:i+batch_size]
                    collection.add(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_meta,
                        embeddings=batch_emb
                    )
                else:
                    collection.add(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_meta
                    )
                
                total_inserted += len(batch_ids)
                print(f"   Inserted {total_inserted}/{len(ids)} chunks", end='\r')
            
            print(f"\n   ✓ Successfully imported {total_inserted} chunks")
            return True
            
        except Exception as e:
            print(f"   ✗ Error importing book: {e}")
            return False
    
    def import_book_set(self, set_name: str, campaign_id: int = 0) -> Dict[str, Any]:
        """Import a predefined set of books for a campaign type"""
        if set_name not in CAMPAIGN_BOOK_SETS:
            print(f"❌ Unknown book set: {set_name}")
            print(f"Available sets: {', '.join(CAMPAIGN_BOOK_SETS.keys())}")
            return {'success': False, 'imported': 0}
        
        book_set = CAMPAIGN_BOOK_SETS[set_name]
        print(f"\n{'='*80}")
        print(f"Importing Book Set: {book_set['name']}")
        print(f"Description: {book_set['description']}")
        print(f"Campaign ID: {campaign_id}")
        print(f"{'='*80}")
        
        available_books = self.list_available_books()
        imported_count = 0
        failed_count = 0
        
        for book_pattern in book_set['books']:
            # Find matching books
            matches = [b for b in available_books 
                      if book_pattern.lower() in b['filename'].lower()
                      or book_pattern.lower() in b['file'].lower()]
            
            if not matches:
                print(f"\n⚠️  No match found for: {book_pattern}")
                failed_count += 1
                continue
            
            # Use first match (could be improved with better matching)
            book = matches[0]
            success = self.import_book(
                Path(book['path']),
                book_id=book_pattern,
                campaign_id=campaign_id
            )
            
            if success:
                imported_count += 1
            else:
                failed_count += 1
        
        print(f"\n{'='*80}")
        print(f"Import Complete!")
        print(f"Imported: {imported_count} books")
        print(f"Failed:   {failed_count} books")
        print(f"{'='*80}")
        
        return {
            'success': failed_count == 0,
            'imported': imported_count,
            'failed': failed_count
        }
    
    def list_imported_books(self, campaign_id: int = None) -> List[Dict[str, Any]]:
        """List books currently in ChromaDB"""
        try:
            collection = self.client.get_collection(self.collection_name)
            
            # Get all documents
            results = collection.get(
                include=['metadatas']
            )
            
            # Extract unique books
            books = {}
            for metadata in results['metadatas']:
                if campaign_id is not None and metadata.get('campaign_id') != campaign_id:
                    continue
                
                book_id = metadata.get('book_id', 'unknown')
                if book_id not in books:
                    books[book_id] = {
                        'book_id': book_id,
                        'filename': metadata.get('filename', 'Unknown'),
                        'system': metadata.get('system', 'Unknown'),
                        'campaign_id': metadata.get('campaign_id', 0),
                        'chunk_count': 0
                    }
                books[book_id]['chunk_count'] += 1
            
            return sorted(books.values(), key=lambda x: (x['campaign_id'], x['book_id']))
            
        except Exception as e:
            print(f"Error listing imported books: {e}")
            return []


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Smart Book Import to RAG/Vector Database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available parsed books
  python import_to_rag.py --list
  
  # List available book sets
  python import_to_rag.py --list-sets
  
  # Import a book set for a campaign
  python import_to_rag.py --import-set vampire_basic --campaign-id 1
  
  # Import core rules globally (available to all campaigns)
  python import_to_rag.py --import-set core_only --campaign-id 0
  
  # List what's currently in the database
  python import_to_rag.py --list-imported
  
  # List books for a specific campaign
  python import_to_rag.py --list-imported --campaign-id 1
        """
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available parsed books'
    )
    parser.add_argument(
        '--list-sets',
        action='store_true',
        help='List available book sets'
    )
    parser.add_argument(
        '--import-set',
        type=str,
        help='Import a predefined book set'
    )
    parser.add_argument(
        '--campaign-id',
        type=int,
        default=0,
        help='Campaign ID (0=global, >0=campaign-specific)'
    )
    parser.add_argument(
        '--list-imported',
        action='store_true',
        help='List books currently in ChromaDB'
    )
    parser.add_argument(
        '--parsed-dir',
        type=str,
        default=None,
        help='Directory with parsed JSON files'
    )
    
    args = parser.parse_args()
    
    # Determine parsed directory
    if args.parsed_dir:
        parsed_dir = Path(args.parsed_dir)
    else:
        parsed_dir = Path(__file__).parent / 'parsed'
    
    if not parsed_dir.exists():
        print(f"❌ Parsed directory not found: {parsed_dir}")
        print("   Run parse_books.py first to generate parsed books")
        sys.exit(1)
    
    # Create importer
    importer = SmartBookImporter(parsed_dir)
    
    # Handle commands
    if args.list:
        print("\n📚 Available Parsed Books:")
        print("=" * 80)
        books = importer.list_available_books()
        
        if not books:
            print("No parsed books found. Run parse_books.py first.")
        else:
            current_system = None
            for book in books:
                if book['system'] != current_system:
                    current_system = book['system']
                    print(f"\n{current_system}:")
                
                emb = "📊" if book['has_embeddings'] else "📄"
                print(f"  {emb} {book['filename']}")
                print(f"     {book['pages']} pages, {book['chunks']} chunks")
    
    elif args.list_sets:
        print("\n📦 Available Book Sets:")
        print("=" * 80)
        for set_name, set_info in CAMPAIGN_BOOK_SETS.items():
            print(f"\n{set_name}:")
            print(f"  Name: {set_info['name']}")
            print(f"  Description: {set_info['description']}")
            print(f"  Books: {', '.join(set_info['books'])}")
    
    elif args.import_set:
        importer.import_book_set(args.import_set, args.campaign_id)
    
    elif args.list_imported:
        print("\n📚 Books in ChromaDB:")
        print("=" * 80)
        books = importer.list_imported_books(
            campaign_id=args.campaign_id if args.campaign_id > 0 else None
        )
        
        if not books:
            print("No books imported yet.")
        else:
            current_campaign = None
            for book in books:
                if book['campaign_id'] != current_campaign:
                    current_campaign = book['campaign_id']
                    scope = "Global" if current_campaign == 0 else f"Campaign {current_campaign}"
                    print(f"\n{scope}:")
                
                print(f"  📚 {book['filename']} ({book['system']})")
                print(f"     ID: {book['book_id']}, Chunks: {book['chunk_count']}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

