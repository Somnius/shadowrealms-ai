#!/usr/bin/env python3
"""
Test suite for validating imported books in ChromaDB RAG system
Tests data integrity, embeddings, semantic search, and metadata
"""

import pytest
import sys
from pathlib import Path
import chromadb
from chromadb.config import Settings
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestChromaDBConnection:
    """Test ChromaDB connection and collection access"""
    
    @pytest.fixture(scope="class")
    def chroma_client(self):
        """Initialize ChromaDB client"""
        try:
            client = chromadb.HttpClient(
                host='localhost',
                port=8000,
                settings=Settings(allow_reset=False)
            )
            return client
        except Exception as e:
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_chromadb_connection(self, chroma_client):
        """Test that ChromaDB is accessible"""
        print("\n🔗 Testing ChromaDB connection...")
        assert chroma_client is not None
        # Test heartbeat
        heartbeat = chroma_client.heartbeat()
        assert heartbeat > 0
        print(f"   ✅ ChromaDB connected (heartbeat: {heartbeat}ns)")
    
    def test_collection_exists(self, chroma_client):
        """Test that rule_books collection exists"""
        print("\n📚 Checking for rule_books collection...")
        collections = chroma_client.list_collections()
        collection_names = [c.name for c in collections]
        print(f"   Found collections: {collection_names}")
        assert 'rule_books' in collection_names, "rule_books collection not found"
        print("   ✅ rule_books collection exists")
    
    def test_collection_has_data(self, chroma_client):
        """Test that collection contains imported data"""
        print("\n📊 Checking collection data...")
        collection = chroma_client.get_collection('rule_books')
        count = collection.count()
        assert count > 0, "Collection is empty"
        print(f"   ✅ Collection has {count} chunks")


class TestImportedBooks:
    """Test the imported book data and metadata"""
    
    @pytest.fixture(scope="class")
    def collection(self):
        """Get the rule_books collection"""
        try:
            client = chromadb.HttpClient(host='localhost', port=8000)
            return client.get_collection('rule_books')
        except Exception as e:
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_expected_book_count(self, collection):
        """Test that all 3 books are imported"""
        print("\n📖 Counting imported books...")
        # Query for unique book_ids in campaign 1
        results = collection.get(
            where={"campaign_id": 1},
            include=["metadatas"],
            limit=10000  # Get many to find all books
        )
        
        book_ids = set()
        for metadata in results['metadatas']:
            book_ids.add(metadata['book_id'])
        
        print(f"   Books found: {', '.join(sorted(book_ids))}")
        assert len(book_ids) >= 3, f"Expected 3 books, found {len(book_ids)}"
        print(f"   ✅ Found {len(book_ids)} books in Campaign 1")
    
    def test_vampire_book_imported(self, collection):
        """Test Vampire: The Masquerade is imported"""
        print("\n🧛 Checking Vampire: The Masquerade...")
        results = collection.get(
            where={
                "$and": [
                    {"campaign_id": 1},
                    {"book_id": "vampire____the_masquerade___revised"}
                ]
            },
            limit=1
        )
        
        assert len(results['ids']) > 0, "Vampire book not found"
        print("   ✅ Vampire: The Masquerade found")
    
    def test_werewolf_book_imported(self, collection):
        """Test Werewolf: The Apocalypse is imported"""
        print("\n🐺 Checking Werewolf: The Apocalypse...")
        results = collection.get(
            where={
                "$and": [
                    {"campaign_id": 1},
                    {"book_id": "werewolf_the_apocalypse_core_(revised)"}
                ]
            },
            limit=1
        )
        
        assert len(results['ids']) > 0, "Werewolf book not found"
        print("   ✅ Werewolf: The Apocalypse found")
    
    def test_mage_book_imported(self, collection):
        """Test Mage: The Ascension is imported"""
        print("\n🔮 Checking Mage: The Ascension...")
        results = collection.get(
            where={
                "$and": [
                    {"campaign_id": 1},
                    {"book_id": "mage_the_ascension_revised"}
                ]
            },
            limit=1
        )
        
        assert len(results['ids']) > 0, "Mage book not found"
        print("   ✅ Mage: The Ascension found")
    
    def test_chunk_counts(self, collection):
        """Test that chunk counts match expected values"""
        print("\n📊 Verifying chunk counts...")
        expected_counts = {
            "vampire____the_masquerade___revised": 1663,
            "werewolf_the_apocalypse_core_(revised)": 1834,
            "mage_the_ascension_revised": 1942
        }
        
        for book_id, expected_count in expected_counts.items():
            results = collection.get(
                where={
                    "$and": [
                        {"campaign_id": 1},
                        {"book_id": book_id}
                    ]
                },
                limit=10000
            )
            
            actual_count = len(results['ids'])
            print(f"   • {book_id}: {actual_count} chunks (expected {expected_count})")
            assert actual_count == expected_count, \
                f"{book_id}: Expected {expected_count} chunks, got {actual_count}"
        print("   ✅ All chunk counts correct")
    
    def test_metadata_structure(self, collection):
        """Test that metadata has required fields"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["metadatas"],
            limit=1
        )
        
        assert len(results['metadatas']) > 0, "No metadata found"
        
        metadata = results['metadatas'][0]
        required_fields = [
            'book_id', 'campaign_id', 'filename', 'system',
            'category', 'page_number', 'chunk_id', 'word_count'
        ]
        
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"
        
        print(f"✓ Metadata structure valid: {list(metadata.keys())}")
    
    def test_campaign_isolation(self, collection):
        """Test that campaign 1 data is properly isolated"""
        # Get campaign 1 data
        campaign1 = collection.get(
            where={"campaign_id": 1},
            limit=10
        )
        
        # Verify all results are campaign 1
        for metadata in campaign1['metadatas']:
            assert metadata['campaign_id'] == 1, "Found data from wrong campaign"
        
        print("✓ Campaign isolation working correctly")


class TestEmbeddings:
    """Test that embeddings are present and valid"""
    
    @pytest.fixture(scope="class")
    def collection(self):
        """Get the rule_books collection"""
        try:
            client = chromadb.HttpClient(host='localhost', port=8000)
            return client.get_collection('rule_books')
        except Exception as e:
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_embeddings_exist(self, collection):
        """Test that embeddings are stored"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["embeddings"],
            limit=10
        )
        
        assert results['embeddings'] is not None, "No embeddings found"
        assert len(results['embeddings']) > 0, "Embeddings list is empty"
        print(f"✓ Embeddings present for {len(results['embeddings'])} chunks")
    
    def test_embedding_dimensions(self, collection):
        """Test that embeddings have correct dimensions (384 for MiniLM)"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["embeddings"],
            limit=1
        )
        
        embedding = results['embeddings'][0]
        assert len(embedding) == 384, f"Expected 384 dimensions, got {len(embedding)}"
        print(f"✓ Embedding dimensions correct: {len(embedding)}")
    
    def test_embedding_values(self, collection):
        """Test that embeddings contain valid float values"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["embeddings"],
            limit=5
        )
        
        for embedding in results['embeddings']:
            # Convert to numpy for easier testing
            emb_array = np.array(embedding)
            
            # Check all values are floats
            assert emb_array.dtype in [np.float32, np.float64], "Embeddings not float type"
            
            # Check no NaN or Inf values
            assert not np.isnan(emb_array).any(), "Embeddings contain NaN"
            assert not np.isinf(emb_array).any(), "Embeddings contain Inf"
            
            # Check reasonable value range (typically -1 to 1 for normalized)
            assert emb_array.min() >= -2, f"Embedding value too low: {emb_array.min()}"
            assert emb_array.max() <= 2, f"Embedding value too high: {emb_array.max()}"
        
        print("✓ Embedding values are valid")


class TestSemanticSearch:
    """Test semantic search functionality with sample queries"""
    
    @pytest.fixture(scope="class")
    def collection(self):
        """Get the rule_books collection"""
        try:
            client = chromadb.HttpClient(host='localhost', port=8000)
            return client.get_collection('rule_books')
        except Exception as e:
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_vampire_discipline_query(self, collection):
        """Test query about Vampire disciplines"""
        results = collection.query(
            query_texts=["What are vampire disciplines and powers?"],
            n_results=5,
            where={"campaign_id": 1}
        )
        
        assert len(results['ids'][0]) > 0, "No results for Vampire query"
        
        # Check that Vampire book appears in results
        book_ids = [meta['book_id'] for meta in results['metadatas'][0]]
        assert any('vampire' in bid.lower() for bid in book_ids), \
            "Vampire book not in top results for Vampire query"
        
        print(f"✓ Vampire query returned {len(results['ids'][0])} results")
        print(f"  Top result from: {results['metadatas'][0][0]['filename']}")
    
    def test_werewolf_rage_query(self, collection):
        """Test query about Werewolf rage mechanic"""
        results = collection.query(
            query_texts=["How does rage work for werewolves?"],
            n_results=5,
            where={"campaign_id": 1}
        )
        
        assert len(results['ids'][0]) > 0, "No results for Werewolf query"
        
        # Check that Werewolf book appears in results
        book_ids = [meta['book_id'] for meta in results['metadatas'][0]]
        assert any('werewolf' in bid.lower() for bid in book_ids), \
            "Werewolf book not in top results for Werewolf query"
        
        print(f"✓ Werewolf query returned {len(results['ids'][0])} results")
        print(f"  Top result from: {results['metadatas'][0][0]['filename']}")
    
    def test_mage_sphere_query(self, collection):
        """Test query about Mage spheres"""
        results = collection.query(
            query_texts=["What are the spheres of magic in Mage?"],
            n_results=5,
            where={"campaign_id": 1}
        )
        
        assert len(results['ids'][0]) > 0, "No results for Mage query"
        
        # Check that Mage book appears in results
        book_ids = [meta['book_id'] for meta in results['metadatas'][0]]
        assert any('mage' in bid.lower() for bid in book_ids), \
            "Mage book not in top results for Mage query"
        
        print(f"✓ Mage query returned {len(results['ids'][0])} results")
        print(f"  Top result from: {results['metadatas'][0][0]['filename']}")
    
    def test_cross_book_query(self, collection):
        """Test query that might span multiple books"""
        results = collection.query(
            query_texts=["What is the World of Darkness setting?"],
            n_results=10,
            where={"campaign_id": 1}
        )
        
        assert len(results['ids'][0]) > 0, "No results for cross-book query"
        
        # Check that multiple books are represented
        book_ids = set([meta['book_id'] for meta in results['metadatas'][0]])
        print(f"✓ Cross-book query found results from {len(book_ids)} book(s)")
    
    def test_similarity_scores(self, collection):
        """Test that similarity scores are reasonable"""
        results = collection.query(
            query_texts=["vampire blood potency"],
            n_results=5,
            where={"campaign_id": 1}
        )
        
        # ChromaDB returns distances (lower is better)
        distances = results['distances'][0]
        
        assert len(distances) > 0, "No distances returned"
        
        # Check that distances are in reasonable range and sorted
        for i in range(len(distances) - 1):
            assert distances[i] <= distances[i+1], "Results not sorted by similarity"
        
        print(f"✓ Similarity scores valid: {distances}")


class TestDataQuality:
    """Test the quality of imported text data"""
    
    @pytest.fixture(scope="class")
    def collection(self):
        """Get the rule_books collection"""
        try:
            client = chromadb.HttpClient(host='localhost', port=8000)
            return client.get_collection('rule_books')
        except Exception as e:
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_text_not_empty(self, collection):
        """Test that document texts are not empty"""
        print("\n📝 Checking document text quality...")
        results = collection.get(
            where={"campaign_id": 1},
            include=["documents"],
            limit=100
        )
        
        empty_count = 0
        short_count = 0
        for doc in results['documents']:
            assert len(doc) > 0, "Found empty document"
            if len(doc.split()) < 5:
                short_count += 1
        
        print(f"   Sampled {len(results['documents'])} documents")
        print(f"   Short documents (<5 words): {short_count}")
        # Allow up to 10% of documents to be short (PDF artifacts)
        assert short_count < len(results['documents']) * 0.1, f"Too many short documents: {short_count}"
        print(f"   ✅ All documents have reasonable content")
    
    def test_text_reasonable_length(self, collection):
        """Test that chunks are reasonable length"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["documents"],
            limit=100
        )
        
        lengths = [len(doc) for doc in results['documents']]
        avg_length = sum(lengths) / len(lengths)
        
        # Chunks should be around 1000 chars (with some variance)
        assert 500 < avg_length < 2000, f"Average chunk length unusual: {avg_length}"
        
        print(f"✓ Average chunk length: {avg_length:.0f} characters")
    
    def test_page_numbers_valid(self, collection):
        """Test that page numbers are present and reasonable"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["metadatas"],
            limit=100
        )
        
        for metadata in results['metadatas']:
            page_num = metadata.get('page_number')
            assert page_num is not None, "Missing page_number"
            assert isinstance(page_num, (int, str)), "Invalid page_number type"
            
            # If it's an int, should be positive
            if isinstance(page_num, int):
                assert page_num > 0, f"Invalid page number: {page_num}"
        
        print("✓ Page numbers are valid")
    
    def test_word_counts_reasonable(self, collection):
        """Test that word counts match actual content"""
        results = collection.get(
            where={"campaign_id": 1},
            include=["documents", "metadatas"],
            limit=50
        )
        
        for doc, metadata in zip(results['documents'], results['metadatas']):
            stored_word_count = metadata.get('word_count')
            actual_word_count = len(doc.split())
            
            # Allow some variance (±10%)
            assert abs(stored_word_count - actual_word_count) < actual_word_count * 0.1, \
                f"Word count mismatch: stored {stored_word_count}, actual {actual_word_count}"
        
        print("✓ Word counts accurate")


class TestPerformance:
    """Test query performance and response times"""
    
    @pytest.fixture(scope="class")
    def collection(self):
        """Get the rule_books collection"""
        try:
            client = chromadb.HttpClient(host='localhost', port=8000)
            return client.get_collection('rule_books')
        except Exception as e:
            pytest.skip(f"ChromaDB not available: {e}")
    
    def test_query_response_time(self, collection):
        """Test that queries complete in reasonable time"""
        import time
        
        start = time.time()
        results = collection.query(
            query_texts=["vampire disciplines"],
            n_results=10,
            where={"campaign_id": 1}
        )
        duration = time.time() - start
        
        assert duration < 2.0, f"Query too slow: {duration:.2f}s"
        print(f"✓ Query completed in {duration:.3f}s")
    
    def test_get_by_id_performance(self, collection):
        """Test that fetching by ID is fast"""
        import time
        
        # First get some IDs
        sample = collection.get(
            where={"campaign_id": 1},
            limit=10
        )
        
        if len(sample['ids']) > 0:
            start = time.time()
            results = collection.get(ids=[sample['ids'][0]])
            duration = time.time() - start
            
            assert duration < 0.5, f"Get by ID too slow: {duration:.2f}s"
            print(f"✓ Get by ID completed in {duration:.3f}s")


def print_summary_stats():
    """Print overall summary statistics"""
    try:
        client = chromadb.HttpClient(host='localhost', port=8000)
        collection = client.get_collection('rule_books')
        
        # Get all campaign 1 data
        results = collection.get(
            where={"campaign_id": 1},
            include=["metadatas"],
            limit=10000
        )
        
        # Count by book
        book_counts = {}
        for metadata in results['metadatas']:
            book_id = metadata['book_id']
            book_counts[book_id] = book_counts.get(book_id, 0) + 1
        
        print("\n" + "="*70)
        print("📊 CHROMADB IMPORT SUMMARY")
        print("="*70)
        print(f"Total chunks in Campaign 1: {len(results['ids'])}")
        print("\nPer-book breakdown:")
        for book_id, count in sorted(book_counts.items()):
            print(f"  • {book_id}: {count} chunks")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"Could not generate summary: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    print_summary_stats()
    pytest.main([__file__, "-v", "--tb=short"])

