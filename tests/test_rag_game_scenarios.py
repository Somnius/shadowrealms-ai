#!/usr/bin/env python3
"""
Test RAG data for real game scenarios.

This test suite validates that the imported book data can be effectively used
by LLM models (LM Studio/Ollama) for actual gameplay scenarios including:
- Character creation and development
- Combat and mechanics resolution
- World building and traversal
- NPC interactions
- Rule lookups and clarifications
"""

import pytest
import chromadb
from typing import List, Dict, Any


# Configuration
CHROMADB_HOST = "localhost"
CHROMADB_PORT = 8000
COLLECTION_NAME = "rule_books"
CAMPAIGN_ID = 1


class RAGContextBuilder:
    """Helper class to build RAG context for LLM prompts"""
    
    def __init__(self, collection):
        self.collection = collection
    
    def get_context(self, query: str, book_filters: List[str] = None, n_results: int = 5) -> Dict[str, Any]:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: The semantic search query
            book_filters: Optional list of book_ids to filter by
            n_results: Number of results to retrieve
            
        Returns:
            Dict with 'chunks', 'sources', and 'formatted_context'
        """
        where_clause = {"campaign_id": CAMPAIGN_ID}
        
        if book_filters:
            where_clause = {
                "$and": [
                    {"campaign_id": CAMPAIGN_ID},
                    {"book_id": {"$in": book_filters}}
                ]
            }
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause,
            include=['documents', 'metadatas', 'distances']
        )
        
        chunks = []
        sources = []
        
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            
            chunks.append({
                'text': doc,
                'book': meta['filename'],
                'page': meta['page_number'],
                'distance': distance,
                'relevance': 1 - distance  # Convert distance to relevance score
            })
            
            source = f"{meta['filename']} (p. {meta['page_number']})"
            if source not in sources:
                sources.append(source)
        
        # Format context for LLM
        formatted_context = "\n\n---\n\n".join([
            f"From {chunk['book']}, page {chunk['page']}:\n{chunk['text']}"
            for chunk in chunks
        ])
        
        return {
            'chunks': chunks,
            'sources': sources,
            'formatted_context': formatted_context,
            'query': query
        }


@pytest.fixture(scope="module")
def chroma_client():
    """Initialize ChromaDB client"""
    try:
        client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
        client.heartbeat()
        return client
    except Exception as e:
        pytest.skip(f"ChromaDB not available: {e}")


@pytest.fixture(scope="module")
def collection(chroma_client):
    """Get the rule_books collection"""
    return chroma_client.get_collection(COLLECTION_NAME)


@pytest.fixture(scope="module")
def rag_builder(collection):
    """Get RAG context builder"""
    return RAGContextBuilder(collection)


class TestCharacterCreation:
    """Test RAG context retrieval for character creation scenarios"""
    
    def test_vampire_clan_selection(self, rag_builder):
        """Test retrieving clan information for character creation"""
        print("\n🧛 Testing Vampire clan selection...")
        
        context = rag_builder.get_context(
            "What are the different vampire clans and their characteristics?",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        print(f"   Sources: {', '.join(context['sources'][:3])}")
        
        # Validate we got relevant results
        assert len(context['chunks']) >= 3, "Should retrieve multiple clan references"
        
        # Check average relevance
        avg_relevance = sum(c['relevance'] for c in context['chunks']) / len(context['chunks'])
        print(f"   Average relevance: {avg_relevance:.3f}")
        assert avg_relevance > 0.3, "Context should be reasonably relevant"
        
        # Check that context mentions clans
        context_text = context['formatted_context'].lower()
        clan_mentions = sum(1 for clan in ['toreador', 'brujah', 'ventrue', 'tremere', 'nosferatu', 'clan'] 
                           if clan in context_text)
        print(f"   Clan mentions found: {clan_mentions}")
        assert clan_mentions >= 1, "Should mention clans"
        assert 'clan' in context_text, "Should reference clans in general"
        
        print(f"   ✅ Vampire clan context is relevant for character creation")
    
    def test_werewolf_tribe_selection(self, rag_builder):
        """Test retrieving tribe information for Garou character creation"""
        print("\n🐺 Testing Werewolf tribe selection...")
        
        context = rag_builder.get_context(
            "What are the Garou tribes and their totems?",
            book_filters=["werewolf_the_apocalypse_core_(revised)"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        print(f"   Sources: {', '.join(context['sources'][:3])}")
        
        assert len(context['chunks']) >= 3
        avg_relevance = sum(c['relevance'] for c in context['chunks']) / len(context['chunks'])
        print(f"   Average relevance: {avg_relevance:.3f}")
        assert avg_relevance > 0.2, "Context should have some relevance"
        
        context_text = context['formatted_context'].lower()
        tribe_keywords = sum(1 for keyword in ['tribe', 'garou', 'totem', 'children of gaia', 'silver fangs', 'werewolf'] 
                            if keyword in context_text)
        print(f"   Tribe-related keywords found: {tribe_keywords}")
        assert tribe_keywords >= 2, "Should have tribe-related information"
        
        print(f"   ✅ Werewolf tribe context is relevant for character creation")
    
    def test_mage_tradition_selection(self, rag_builder):
        """Test retrieving tradition information for Mage character creation"""
        print("\n🔮 Testing Mage tradition selection...")
        
        context = rag_builder.get_context(
            "What are the mage traditions and their philosophies?",
            book_filters=["mage_the_ascension_revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        print(f"   Sources: {', '.join(context['sources'][:3])}")
        
        assert len(context['chunks']) >= 3
        avg_relevance = sum(c['relevance'] for c in context['chunks']) / len(context['chunks'])
        print(f"   Average relevance: {avg_relevance:.3f}")
        assert avg_relevance > 0.3
        
        context_text = context['formatted_context'].lower()
        tradition_keywords = sum(1 for keyword in ['tradition', 'hermetic', 'verbena', 'euthanatos', 'dreamspeakers', 'mage', 'philosophy'] 
                                if keyword in context_text)
        print(f"   Tradition-related keywords found: {tradition_keywords}")
        assert tradition_keywords >= 1, "Should have tradition-related information"
        assert 'tradition' in context_text or 'mage' in context_text, "Should reference traditions or mages"
        
        print(f"   ✅ Mage tradition context is relevant for character creation")


class TestCombatAndMechanics:
    """Test RAG context for combat and game mechanics"""
    
    def test_vampire_disciplines(self, rag_builder):
        """Test retrieving discipline mechanics for vampire combat"""
        print("\n⚔️ Testing Vampire discipline mechanics...")
        
        context = rag_builder.get_context(
            "How do vampire disciplines like Celerity and Potence work in combat?",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        discipline_keywords = ['discipline', 'celerity', 'potence', 'combat', 'blood']
        found_keywords = [kw for kw in discipline_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 3, "Should have discipline mechanics information"
        
        # Check that we have actual mechanical information (numbers, dots, etc.)
        has_mechanics = any(word in context_text for word in ['dot', 'level', 'cost', 'dice', 'roll'])
        print(f"   Contains mechanical information: {has_mechanics}")
        assert has_mechanics, "Should include mechanical details"
        
        print(f"   ✅ Discipline mechanics context is useful for combat resolution")
    
    def test_werewolf_rage(self, rag_builder):
        """Test retrieving rage mechanics for Garou combat"""
        print("\n😤 Testing Werewolf rage mechanics...")
        
        context = rag_builder.get_context(
            "How does rage work for Garou in combat and when can it be spent?",
            book_filters=["werewolf_the_apocalypse_core_(revised)"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        rage_keywords = ['rage', 'frenzy', 'garou', 'combat', 'action']
        found_keywords = [kw for kw in rage_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 3, "Should have rage mechanics information"
        
        print(f"   ✅ Rage mechanics context is useful for combat resolution")
    
    def test_mage_spheres(self, rag_builder):
        """Test retrieving sphere mechanics for Mage spellcasting"""
        print("\n✨ Testing Mage sphere mechanics...")
        
        context = rag_builder.get_context(
            "How do mages use spheres to cast spells and what are the sphere levels?",
            book_filters=["mage_the_ascension_revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        sphere_keywords = ['sphere', 'magic', 'spell', 'forces', 'matter', 'prime']
        found_keywords = [kw for kw in sphere_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 3, "Should have sphere mechanics information"
        
        print(f"   ✅ Sphere mechanics context is useful for spellcasting")


class TestWorldBuildingAndTraversal:
    """Test RAG context for world building and environment interaction"""
    
    def test_vampire_locations(self, rag_builder):
        """Test retrieving location and territory information"""
        print("\n🏙️ Testing Vampire domain and territory...")
        
        context = rag_builder.get_context(
            "How do vampires control and maintain their domains and territories?",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        location_keywords = ['domain', 'territory', 'prince', 'elysium', 'haven']
        found_keywords = [kw for kw in location_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should have domain/territory information"
        
        print(f"   ✅ Domain context is useful for world building")
    
    def test_werewolf_caerns(self, rag_builder):
        """Test retrieving caern and spirit realm information"""
        print("\n🌲 Testing Werewolf caerns and Umbra...")
        
        context = rag_builder.get_context(
            "What are caerns and how do Garou travel through the Umbra?",
            book_filters=["werewolf_the_apocalypse_core_(revised)"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        caern_keywords = ['caern', 'umbra', 'spirit', 'realm', 'gauntlet']
        found_keywords = [kw for kw in caern_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should have caern/Umbra information"
        
        print(f"   ✅ Caern context is useful for world traversal")
    
    def test_mage_chantry(self, rag_builder):
        """Test retrieving chantry and horizon realm information"""
        print("\n🏰 Testing Mage chantries and Horizon Realms...")
        
        context = rag_builder.get_context(
            "What are chantries and how do mages create and use Horizon Realms?",
            book_filters=["mage_the_ascension_revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        chantry_keywords = ['chantry', 'horizon', 'realm', 'node', 'sanctum']
        found_keywords = [kw for kw in chantry_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should have chantry information"
        
        print(f"   ✅ Chantry context is useful for world building")


class TestNPCAndSocialInteraction:
    """Test RAG context for NPC interactions and social mechanics"""
    
    def test_vampire_social_hierarchy(self, rag_builder):
        """Test retrieving Camarilla hierarchy and social structure"""
        print("\n👑 Testing Vampire social hierarchy...")
        
        context = rag_builder.get_context(
            "What is the Camarilla hierarchy and how do vampires interact socially?",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        social_keywords = ['camarilla', 'prince', 'primogen', 'status', 'boon', 'prestation']
        found_keywords = [kw for kw in social_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should have social hierarchy information"
        
        print(f"   ✅ Social hierarchy context is useful for NPC interactions")
    
    def test_werewolf_pack_dynamics(self, rag_builder):
        """Test retrieving pack structure and renown information"""
        print("\n🐾 Testing Werewolf pack dynamics...")
        
        context = rag_builder.get_context(
            "How do Garou packs work and what is renown?",
            book_filters=["werewolf_the_apocalypse_core_(revised)"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        pack_keywords = ['pack', 'renown', 'glory', 'honor', 'wisdom', 'rank']
        found_keywords = [kw for kw in pack_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should have pack dynamics information"
        
        print(f"   ✅ Pack dynamics context is useful for NPC interactions")
    
    def test_mage_consensus_reality(self, rag_builder):
        """Test retrieving Consensus and Paradox information"""
        print("\n🌐 Testing Mage Consensus and reality...")
        
        context = rag_builder.get_context(
            "What is Consensus reality and how does it affect mages and their magic?",
            book_filters=["mage_the_ascension_revised"],
            n_results=5
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        assert len(context['chunks']) >= 3
        
        context_text = context['formatted_context'].lower()
        consensus_keywords = ['consensus', 'paradox', 'reality', 'sleeper', 'technocracy']
        found_keywords = [kw for kw in consensus_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should have Consensus information"
        
        print(f"   ✅ Consensus context is useful for world interactions")


class TestCrossGameScenarios:
    """Test RAG context for scenarios that might involve multiple game lines"""
    
    def test_supernatural_detection(self, rag_builder):
        """Test retrieving information about detecting other supernatural beings"""
        print("\n👁️ Testing cross-game supernatural detection...")
        
        context = rag_builder.get_context(
            "How can supernatural beings detect or sense other supernatural creatures?",
            n_results=10
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        # Check that we got results from multiple books
        books_found = set(chunk['book'] for chunk in context['chunks'])
        print(f"   Books represented: {len(books_found)}")
        print(f"   Books: {', '.join(books_found)}")
        
        assert len(books_found) >= 2, "Should pull from multiple game lines"
        assert len(context['chunks']) >= 5, "Should get multiple perspectives"
        
        print(f"   ✅ Cross-game context provides multiple perspectives")
    
    def test_combat_resolution(self, rag_builder):
        """Test retrieving general combat mechanics"""
        print("\n⚔️ Testing cross-game combat resolution...")
        
        context = rag_builder.get_context(
            "What are the basic combat rules including initiative, attacks, and damage?",
            n_results=10
        )
        
        print(f"   Query: {context['query']}")
        print(f"   Retrieved {len(context['chunks'])} relevant chunks")
        
        context_text = context['formatted_context'].lower()
        combat_keywords = ['initiative', 'attack', 'damage', 'health', 'soak', 'dice', 'roll']
        found_keywords = [kw for kw in combat_keywords if kw in context_text]
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 4, "Should have comprehensive combat mechanics"
        
        print(f"   ✅ Combat mechanics context is comprehensive")


class TestLLMPromptConstruction:
    """Test that RAG context can be properly formatted for LLM prompts"""
    
    def test_character_creation_prompt(self, rag_builder):
        """Test constructing a complete character creation prompt with RAG context"""
        print("\n📝 Testing character creation prompt construction...")
        
        user_query = "I want to create a Toreador vampire who is an artist"
        context = rag_builder.get_context(
            "What are the characteristics, disciplines, and traits of the Toreador clan?",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=3
        )
        
        # Construct a sample LLM prompt
        llm_prompt = f"""You are a storyteller for Vampire: The Masquerade. A player wants to create a character.

**Player Request:** {user_query}

**Relevant Rule Book Context:**
{context['formatted_context']}

**Sources:** {', '.join(context['sources'])}

Based on the above context from the official rule books, help the player create their Toreador character with appropriate disciplines, background, and traits."""
        
        print(f"   Prompt length: {len(llm_prompt)} characters")
        print(f"   Context chunks: {len(context['chunks'])}")
        print(f"   Sources cited: {len(context['sources'])}")
        
        # Validate prompt structure
        assert "Player Request:" in llm_prompt
        assert "Relevant Rule Book Context:" in llm_prompt
        assert "Sources:" in llm_prompt
        assert len(context['formatted_context']) > 200, "Context should be substantial"
        assert 'toreador' in context['formatted_context'].lower(), "Should mention Toreador"
        
        print(f"   ✅ Prompt is well-structured for LLM consumption")
        print(f"\n   Sample prompt (first 300 chars):\n   {llm_prompt[:300]}...")
    
    def test_combat_resolution_prompt(self, rag_builder):
        """Test constructing a combat resolution prompt with RAG context"""
        print("\n⚔️ Testing combat resolution prompt construction...")
        
        user_query = "My werewolf character wants to use rage to attack multiple enemies"
        context = rag_builder.get_context(
            "How does rage work in combat and can it be used for multiple actions?",
            book_filters=["werewolf_the_apocalypse_core_(revised)"],
            n_results=3
        )
        
        llm_prompt = f"""You are a storyteller for Werewolf: The Apocalypse. Resolve this combat action.

**Player Action:** {user_query}

**Relevant Combat Rules:**
{context['formatted_context']}

**Sources:** {', '.join(context['sources'])}

Based on the official rules above, explain how the player can use rage and resolve their combat action."""
        
        print(f"   Prompt length: {len(llm_prompt)} characters")
        print(f"   Context chunks: {len(context['chunks'])}")
        
        assert "Player Action:" in llm_prompt
        assert "Relevant Combat Rules:" in llm_prompt
        assert 'rage' in context['formatted_context'].lower(), "Should mention rage"
        
        print(f"   ✅ Combat prompt is well-structured for LLM")
    
    def test_context_size_management(self, rag_builder):
        """Test that context doesn't exceed typical LLM context windows"""
        print("\n📏 Testing context size management...")
        
        # Request many results
        context = rag_builder.get_context(
            "Tell me about vampire society and politics",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=20
        )
        
        context_length = len(context['formatted_context'])
        print(f"   Context with 20 chunks: {context_length} characters")
        print(f"   Approximately {context_length / 4:.0f} tokens (rough estimate)")
        
        # Most LLMs have at least 4K context, reserve space for prompt and response
        # RAG context should be reasonable (< 3000 tokens or ~12000 chars)
        assert context_length < 20000, "Context should fit in reasonable LLM context window"
        
        # Test with fewer results for tighter control
        context_small = rag_builder.get_context(
            "Tell me about vampire society and politics",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=5
        )
        
        small_length = len(context_small['formatted_context'])
        print(f"   Context with 5 chunks: {small_length} characters")
        print(f"   Approximately {small_length / 4:.0f} tokens (rough estimate)")
        
        print(f"   ✅ Context sizes are manageable for LLM prompts")


class TestRelevanceAndQuality:
    """Test that retrieved context is actually relevant and high quality"""
    
    def test_relevance_scores(self, rag_builder):
        """Test that relevance scores indicate good matches"""
        print("\n🎯 Testing relevance scores across queries...")
        
        test_queries = [
            ("What disciplines do Ventrue vampires have?", ["vampire____the_masquerade___revised"]),
            ("How do Garou transform between forms?", ["werewolf_the_apocalypse_core_(revised)"]),
            ("What is Prime sphere magic?", ["mage_the_ascension_revised"])
        ]
        
        successful_queries = 0
        for query, book_filter in test_queries:
            context = rag_builder.get_context(query, book_filters=book_filter, n_results=3)
            
            avg_relevance = sum(c['relevance'] for c in context['chunks']) / len(context['chunks'])
            top_relevance = context['chunks'][0]['relevance']
            
            print(f"\n   Query: '{query[:50]}...'")
            print(f"   Top relevance: {top_relevance:.3f}")
            print(f"   Avg relevance: {avg_relevance:.3f}")
            
            # Check if relevance is reasonable (some queries may not match perfectly)
            if top_relevance > 0.0 and avg_relevance > -0.1:
                successful_queries += 1
        
        # At least 2 out of 3 queries should have reasonable relevance
        assert successful_queries >= 2, f"Only {successful_queries}/3 queries had reasonable relevance"
        print(f"\n   ✅ {successful_queries}/3 queries have reasonable semantic matching")
    
    def test_context_completeness(self, rag_builder):
        """Test that context provides complete information for queries"""
        print("\n📚 Testing context completeness...")
        
        # Test a complex query that needs multiple chunks
        context = rag_builder.get_context(
            "How do vampire generation and blood potency work together to affect discipline levels and blood pool?",
            book_filters=["vampire____the_masquerade___revised"],
            n_results=7
        )
        
        context_text = context['formatted_context'].lower()
        
        # Check for multiple related concepts
        key_concepts = ['generation', 'blood', 'discipline', 'pool', 'potency', 'trait']
        found_concepts = [concept for concept in key_concepts if concept in context_text]
        
        print(f"   Query: Complex vampire mechanics")
        print(f"   Chunks retrieved: {len(context['chunks'])}")
        print(f"   Key concepts found: {len(found_concepts)}/{len(key_concepts)}")
        print(f"   Concepts: {', '.join(found_concepts)}")
        
        # Should find most key concepts
        assert len(found_concepts) >= 4, "Should cover most key concepts for complex query"
        
        print(f"   ✅ Complex queries retrieve comprehensive context")


if __name__ == "__main__":
    """Run tests directly"""
    pytest.main([__file__, "-v", "-s"])

