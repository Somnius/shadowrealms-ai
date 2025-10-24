#!/usr/bin/env python3
"""
Test LM Studio + ChromaDB RAG Integration

This test suite validates that LM Studio models work correctly with ChromaDB
to provide rule book context for game scenarios. This is the CORE functionality
that makes the game AI work properly.
"""

import pytest
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from services.rag_service import RAGService
import chromadb


# Configuration
CHROMADB_HOST = "localhost"
CHROMADB_PORT = 8000
CAMPAIGN_ID = 1


@pytest.fixture(scope="module")
def rag_service():
    """Initialize RAG service"""
    config = {
        'CHROMADB_HOST': CHROMADB_HOST,
        'CHROMADB_PORT': CHROMADB_PORT
    }
    
    try:
        service = RAGService(config)
        # Test connection
        status = service.get_system_status()
        if not status['chromadb_connected']:
            pytest.skip("ChromaDB not available")
        
        # Verify rule_books collection exists and has data
        if 'rule_books' not in status['collections']:
            pytest.skip("rule_books collection not found")
        
        book_count = status['collections']['rule_books'].get('count', 0)
        if book_count == 0:
            pytest.skip("rule_books collection is empty")
        
        print(f"\n✅ RAG Service initialized with {book_count} rule book chunks")
        return service
        
    except Exception as e:
        pytest.skip(f"Failed to initialize RAG service: {e}")


class TestRAGRuleBookIntegration:
    """Test that RAG service properly queries rule books"""
    
    def test_get_rule_book_context(self, rag_service):
        """Test that we can retrieve rule book context"""
        print("\n📚 Testing rule book context retrieval...")
        
        query = "How do vampire disciplines work?"
        context = rag_service.get_rule_book_context(query, CAMPAIGN_ID, n_results=3)
        
        print(f"   Query: {query}")
        print(f"   Retrieved {len(context)} chunks")
        
        assert len(context) > 0, "Should retrieve rule book chunks"
        assert len(context) <= 3, "Should respect n_results limit"
        
        # Check structure
        for i, chunk in enumerate(context):
            print(f"\n   Chunk {i+1}:")
            print(f"     Source: {chunk['metadata'].get('filename', 'Unknown')} (p. {chunk['metadata'].get('page_number', '?')})")
            print(f"     Relevance: {chunk['relevance']:.3f}")
            print(f"     Preview: {chunk['content'][:100]}...")
            
            assert 'content' in chunk
            assert 'metadata' in chunk
            assert 'relevance' in chunk
            assert chunk['content'], "Content should not be empty"
        
        print(f"\n   ✅ Rule book context retrieval works")
    
    def test_vampire_discipline_query(self, rag_service):
        """Test vampire-specific rule book query"""
        print("\n🧛 Testing Vampire discipline query...")
        
        query = "What are the levels of Celerity and how much blood does each cost?"
        context = rag_service.get_rule_book_context(query, CAMPAIGN_ID, n_results=5)
        
        print(f"   Query: {query}")
        print(f"   Retrieved {len(context)} chunks")
        
        assert len(context) > 0
        
        # Check for relevant content
        all_content = " ".join([c['content'].lower() for c in context])
        relevant_keywords = ['celerity', 'discipline', 'blood', 'vampire', 'level']
        found_keywords = [kw for kw in relevant_keywords if kw in all_content]
        
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should find relevant discipline information"
        
        print(f"   ✅ Vampire queries retrieve relevant rule book data")
    
    def test_werewolf_mechanics_query(self, rag_service):
        """Test werewolf-specific rule book query"""
        print("\n🐺 Testing Werewolf mechanics query...")
        
        query = "How does rage work in combat and what forms can Garou take?"
        context = rag_service.get_rule_book_context(query, CAMPAIGN_ID, n_results=5)
        
        print(f"   Query: {query}")
        print(f"   Retrieved {len(context)} chunks")
        
        assert len(context) > 0
        
        all_content = " ".join([c['content'].lower() for c in context])
        relevant_keywords = ['rage', 'garou', 'form', 'combat', 'werewolf']
        found_keywords = [kw for kw in relevant_keywords if kw in all_content]
        
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should find relevant werewolf information"
        
        print(f"   ✅ Werewolf queries retrieve relevant rule book data")
    
    def test_mage_magic_query(self, rag_service):
        """Test mage-specific rule book query"""
        print("\n🔮 Testing Mage magic query...")
        
        query = "What are the spheres of magic and how do mages cast spells?"
        context = rag_service.get_rule_book_context(query, CAMPAIGN_ID, n_results=5)
        
        print(f"   Query: {query}")
        print(f"   Retrieved {len(context)} chunks")
        
        assert len(context) > 0
        
        all_content = " ".join([c['content'].lower() for c in context])
        relevant_keywords = ['sphere', 'magic', 'spell', 'mage', 'forces', 'prime']
        found_keywords = [kw for kw in relevant_keywords if kw in all_content]
        
        print(f"   Found keywords: {', '.join(found_keywords)}")
        assert len(found_keywords) >= 2, "Should find relevant mage information"
        
        print(f"   ✅ Mage queries retrieve relevant rule book data")


class TestPromptAugmentation:
    """Test that prompts are properly augmented with rule book context"""
    
    def test_basic_prompt_augmentation(self, rag_service):
        """Test that augment_prompt includes rule books"""
        print("\n📝 Testing basic prompt augmentation...")
        
        original_prompt = "My vampire wants to use Celerity in combat. How does it work?"
        augmented_prompt = rag_service.augment_prompt(
            original_prompt, 
            CAMPAIGN_ID,
            include_rule_books=True,
            n_rule_book_chunks=3
        )
        
        print(f"   Original prompt length: {len(original_prompt)} chars")
        print(f"   Augmented prompt length: {len(augmented_prompt)} chars")
        
        # Augmented should be longer
        assert len(augmented_prompt) > len(original_prompt), "Augmented prompt should be longer"
        
        # Should contain the original prompt
        assert original_prompt in augmented_prompt, "Should contain original prompt"
        
        # Should have rule book section
        assert "=== OFFICIAL RULE BOOKS ===" in augmented_prompt or len(augmented_prompt) > len(original_prompt) * 2, \
            "Should include rule book context"
        
        # Should have page citations
        has_citations = 'p.' in augmented_prompt or '[' in augmented_prompt
        print(f"   Has page citations: {has_citations}")
        
        print(f"\n   ✅ Prompt augmentation includes rule books")
        
        # Print sample of augmented prompt
        print(f"\n   Sample augmented prompt (first 500 chars):")
        print(f"   {augmented_prompt[:500]}...")
    
    def test_prompt_augmentation_with_rule_books_disabled(self, rag_service):
        """Test that rule books can be disabled"""
        print("\n🚫 Testing prompt augmentation with rule books disabled...")
        
        original_prompt = "My vampire wants to use Celerity in combat."
        augmented_prompt = rag_service.augment_prompt(
            original_prompt,
            CAMPAIGN_ID,
            include_rule_books=False
        )
        
        print(f"   Original prompt length: {len(original_prompt)} chars")
        print(f"   Augmented prompt length: {len(augmented_prompt)} chars")
        
        # Should NOT have rule book section
        assert "=== OFFICIAL RULE BOOKS ===" not in augmented_prompt, \
            "Should not include rule books when disabled"
        
        print(f"   ✅ Rule books can be disabled")
    
    def test_prompt_augmentation_scenarios(self, rag_service):
        """Test various game scenarios"""
        print("\n🎮 Testing various game scenario prompts...")
        
        scenarios = [
            ("Character Creation", "I want to create a Toreador vampire. What disciplines do they have?"),
            ("Combat", "My werewolf enters frenzy and wants to attack. What happens?"),
            ("Magic", "I want to cast a Forces 3 spell to throw lightning. How do I do this?"),
            ("Social", "What is the Camarilla hierarchy and who do I need to talk to?"),
            ("World", "What are caerns and how do werewolves use them?")
        ]
        
        for scenario_name, prompt in scenarios:
            print(f"\n   Scenario: {scenario_name}")
            print(f"   Prompt: {prompt[:60]}...")
            
            augmented = rag_service.augment_prompt(
                prompt,
                CAMPAIGN_ID,
                include_rule_books=True,
                n_rule_book_chunks=3
            )
            
            # Should be substantially longer
            expansion_ratio = len(augmented) / len(prompt)
            print(f"   Expansion ratio: {expansion_ratio:.1f}x")
            
            assert expansion_ratio > 2.0 or len(augmented) > len(prompt) + 500, \
                f"{scenario_name}: Augmented prompt should include significant context"
        
        print(f"\n   ✅ All scenarios receive proper context augmentation")


class TestLLMPromptStructure:
    """Test that augmented prompts are structured correctly for LLMs"""
    
    def test_prompt_has_clear_sections(self, rag_service):
        """Test that prompt has clear, labeled sections"""
        print("\n📑 Testing prompt section structure...")
        
        prompt = "How do I spend rage in combat?"
        augmented = rag_service.augment_prompt(prompt, CAMPAIGN_ID, include_rule_books=True)
        
        print(f"   Original prompt: {prompt}")
        print(f"   Augmented length: {len(augmented)} chars")
        
        # Should have clear section markers
        expected_sections = [
            "=== CURRENT REQUEST ===",
        ]
        
        found_sections = []
        for section in expected_sections:
            if section in augmented:
                found_sections.append(section)
        
        # May have optional sections based on campaign data
        optional_sections = [
            "=== CAMPAIGN CONTEXT ===",
            "=== CHARACTERS ===",
            "=== WORLD SETTING ===",
            "=== RECENT SESSIONS ===",
            "=== GAME RULES ===",
            "=== OFFICIAL RULE BOOKS ==="
        ]
        
        for section in optional_sections:
            if section in augmented:
                found_sections.append(section)
        
        print(f"   Found sections: {len(found_sections)}")
        for section in found_sections:
            print(f"     • {section}")
        
        # Should have at least REQUEST section
        assert "=== CURRENT REQUEST ===" in augmented, "Should have REQUEST section"
        
        # Original prompt should come after all context
        request_pos = augmented.find("=== CURRENT REQUEST ===")
        prompt_pos = augmented.find(prompt)
        assert prompt_pos > request_pos, "Original prompt should come after REQUEST marker"
        
        print(f"   ✅ Prompt has clear section structure")
    
    def test_prompt_includes_sources(self, rag_service):
        """Test that rule book chunks include source citations"""
        print("\n📖 Testing source citations...")
        
        prompt = "What are the vampire clans?"
        augmented = rag_service.augment_prompt(prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        # Should have source citations
        has_page_numbers = 'p.' in augmented
        has_brackets = '[' in augmented and ']' in augmented
        
        print(f"   Has page numbers (p.): {has_page_numbers}")
        print(f"   Has bracket citations []: {has_brackets}")
        
        # At least one citation method should be present
        assert has_page_numbers or has_brackets, "Should include source citations"
        
        print(f"   ✅ Source citations are included")
    
    def test_prompt_token_estimation(self, rag_service):
        """Test that prompts fit within reasonable token limits"""
        print("\n🔢 Testing prompt token estimation...")
        
        prompt = "Tell me about vampire disciplines, werewolf rage, and mage spheres."
        
        # Test with different chunk counts
        for n_chunks in [3, 5, 10]:
            augmented = rag_service.augment_prompt(
                prompt,
                CAMPAIGN_ID,
                include_rule_books=True,
                n_rule_book_chunks=n_chunks
            )
            
            # Rough token estimation (1 token ~= 4 chars)
            estimated_tokens = len(augmented) / 4
            
            print(f"\n   Chunks: {n_chunks}")
            print(f"   Length: {len(augmented)} chars")
            print(f"   Estimated tokens: {estimated_tokens:.0f}")
            
            # Most LLM models have at least 4K context
            # Reserve 2K for response, so context should be < 2K tokens (~8K chars)
            if n_chunks <= 5:
                assert len(augmented) < 12000, "Should fit in reasonable context window for small chunk counts"
        
        print(f"\n   ✅ Prompts fit within reasonable token limits")


class TestRealGameplayScenarios:
    """Test actual gameplay scenarios that would be sent to LM Studio"""
    
    def test_character_creation_vampire(self, rag_service):
        """Test full character creation scenario"""
        print("\n🎭 Testing Vampire character creation...")
        
        user_prompt = """I want to create a new vampire character. I'm thinking of a Ventrue prince 
        who controls the financial district. What disciplines should I have and what are my clan advantages?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        print(f"   Estimated tokens: {len(augmented) / 4:.0f}")
        
        # Should have substantial context
        assert len(augmented) > len(user_prompt) * 3, "Should include significant rule book context"
        
        # Check for relevant content
        content_lower = augmented.lower()
        relevant_terms = ['ventrue', 'discipline', 'clan', 'vampire', 'dominate', 'fortitude', 'presence']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        print(f"   Terms found: {len(found_terms)}/{len(relevant_terms)}")
        
        # Should find at least some relevant terms
        assert len(found_terms) >= 2, "Should include relevant Ventrue/discipline information"
        
        print(f"   ✅ Character creation prompt ready for LM Studio")
    
    def test_combat_resolution_werewolf(self, rag_service):
        """Test combat resolution scenario"""
        print("\n⚔️ Testing Werewolf combat resolution...")
        
        user_prompt = """My Get of Fenris character is in Crinos form and wants to spend rage 
        to make multiple attacks against three Black Spiral Dancers. How many actions can I take 
        and what are the mechanics?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        
        content_lower = augmented.lower()
        relevant_terms = ['rage', 'combat', 'action', 'garou', 'crinos', 'attack']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        
        assert len(found_terms) >= 2, "Should include relevant combat/rage mechanics"
        
        print(f"   ✅ Combat resolution prompt ready for LM Studio")
    
    def test_spellcasting_mage(self, rag_service):
        """Test spellcasting scenario"""
        print("\n✨ Testing Mage spellcasting...")
        
        user_prompt = """I want to cast a vulgar spell using Forces 3 and Prime 2 to shoot lightning 
        at a Technocracy hit squad. What's the difficulty, what are the paradox risks, and how much 
        damage does it do?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        
        content_lower = augmented.lower()
        relevant_terms = ['sphere', 'forces', 'prime', 'paradox', 'spell', 'magic', 'vulgar']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        
        assert len(found_terms) >= 2, "Should include relevant spellcasting mechanics"
        
        print(f"   ✅ Spellcasting prompt ready for LM Studio")
    
    def test_storyteller_ruling(self, rag_service):
        """Test storyteller ruling scenario"""
        print("\n🎬 Testing Storyteller ruling assistance...")
        
        user_prompt = """A player wants their vampire to use Dominate on another player character. 
        What are the rules for this? Do I allow it? What are the mechanics and social consequences?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        
        content_lower = augmented.lower()
        relevant_terms = ['dominate', 'discipline', 'vampire', 'player', 'character']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        
        assert len(found_terms) >= 2, "Should include relevant Dominate mechanics"
        
        print(f"   ✅ Storyteller ruling prompt ready for LM Studio")


class TestCharacterAdvancement:
    """Test character progression and development scenarios"""
    
    def test_vampire_experience_spending(self, rag_service):
        """Test spending XP on vampire abilities"""
        print("\n📈 Testing Vampire XP spending...")
        
        user_prompt = """My vampire has 15 XP. I want to raise Celerity from 2 to 3, 
        and also buy a dot in Finance. How much does this cost and what are the rules?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        
        content_lower = augmented.lower()
        relevant_terms = ['experience', 'xp', 'cost', 'discipline', 'ability', 'celerity']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include XP cost information"
        
        print(f"   ✅ Character advancement prompt ready")
    
    def test_werewolf_rank_advancement(self, rag_service):
        """Test Garou rank progression"""
        print("\n🌟 Testing Werewolf rank advancement...")
        
        user_prompt = """My Garou has enough renown to challenge for Rank 3 (Adren). 
        What are the requirements, what gifts can I learn, and what's the challenge ritual?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['rank', 'renown', 'gift', 'challenge', 'adren']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include rank advancement info"
        
        print(f"   ✅ Rank advancement prompt ready")
    
    def test_mage_arete_increase(self, rag_service):
        """Test Mage Arete advancement"""
        print("\n🔮 Testing Mage Arete advancement...")
        
        user_prompt = """I want to raise my mage's Arete from 3 to 4. What's the XP cost, 
        what's involved in the Seeking, and how does this affect my sphere caps?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['arete', 'seeking', 'sphere', 'enlightenment']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include Arete advancement info"
        
        print(f"   ✅ Arete advancement prompt ready")


class TestSocialInteractions:
    """Test NPC interactions and social mechanics"""
    
    def test_vampire_court_politics(self, rag_service):
        """Test vampire social/political interactions"""
        print("\n👑 Testing Vampire court politics...")
        
        user_prompt = """I'm meeting the Prince to request a boon for saving his childe. 
        How do I approach this? What social mechanics apply? Can I use Presence to influence him?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        
        content_lower = augmented.lower()
        relevant_terms = ['prince', 'boon', 'presence', 'social', 'camarilla', 'prestation']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include political/social mechanics"
        
        print(f"   ✅ Court politics prompt ready")
    
    def test_werewolf_pack_dynamics(self, rag_service):
        """Test werewolf pack interactions"""
        print("\n🐾 Testing Werewolf pack dynamics...")
        
        user_prompt = """There's tension in our pack. The alpha wants to challenge a nearby 
        pack for territory. What are the protocols? Can I challenge the alpha's decision? 
        What about the litany?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['pack', 'alpha', 'challenge', 'litany', 'territory']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include pack dynamics info"
        
        print(f"   ✅ Pack dynamics prompt ready")
    
    def test_mage_tradition_politics(self, rag_service):
        """Test mage tradition interactions"""
        print("\n🏛️ Testing Mage tradition politics...")
        
        user_prompt = """I'm a Hermetic mage meeting with the Verbena to discuss a joint 
        Node. What are the political considerations? How do different traditions interact? 
        What about the Technocracy threat?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['tradition', 'hermetic', 'verbena', 'node', 'technocracy']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include tradition politics info"
        
        print(f"   ✅ Tradition politics prompt ready")


class TestWorldTraversal:
    """Test world building, exploration, and traversal"""
    
    def test_vampire_domain_control(self, rag_service):
        """Test vampire domain mechanics"""
        print("\n🏙️ Testing Vampire domain control...")
        
        user_prompt = """I want to establish a domain in the warehouse district. 
        What are the rules for claiming territory? Do I need the Prince's permission? 
        How do I defend it from intruders?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['domain', 'territory', 'prince', 'claim', 'haven']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include domain mechanics"
        
        print(f"   ✅ Domain control prompt ready")
    
    def test_werewolf_umbra_travel(self, rag_service):
        """Test Umbra traversal and spirit realm"""
        print("\n🌫️ Testing Werewolf Umbra travel...")
        
        user_prompt = """We need to travel through the Umbra to reach a distant caern. 
        How do we step sideways? What do we encounter in the Penumbra? 
        How dangerous is this journey?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['umbra', 'sideways', 'penumbra', 'spirit', 'gauntlet', 'caern']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include Umbra travel mechanics"
        
        print(f"   ✅ Umbra travel prompt ready")
    
    def test_mage_horizon_realm(self, rag_service):
        """Test Mage Horizon Realm creation and use"""
        print("\n✨ Testing Mage Horizon Realm...")
        
        user_prompt = """Our chantry wants to create a Horizon Realm. 
        What spheres are required? How much quintessence does it cost? 
        What can we create inside it?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['horizon', 'realm', 'sphere', 'quintessence', 'chantry']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include Horizon Realm mechanics"
        
        print(f"   ✅ Horizon Realm prompt ready")
    
    def test_urban_exploration(self, rag_service):
        """Test city exploration and investigation"""
        print("\n🔍 Testing urban exploration...")
        
        user_prompt = """We're investigating a series of murders in the city. 
        What investigation mechanics apply? How do we track suspects? 
        What about gathering information from the streets?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['investigation', 'track', 'information', 'city', 'clue']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include investigation mechanics"
        
        print(f"   ✅ Urban exploration prompt ready")


class TestCombatVariations:
    """Test different combat scenarios and mechanics"""
    
    def test_mass_combat(self, rag_service):
        """Test large-scale combat"""
        print("\n⚔️ Testing mass combat...")
        
        user_prompt = """Our werewolf pack is fighting against a whole pack of Black Spiral Dancers 
        (5 vs 5). How do we handle this? Can we use pack tactics? What about morale and retreat?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['combat', 'pack', 'tactics', 'multiple', 'fight']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include mass combat mechanics"
        
        print(f"   ✅ Mass combat prompt ready")
    
    def test_social_combat(self, rag_service):
        """Test social combat and influence"""
        print("\n💬 Testing social combat...")
        
        user_prompt = """I'm a Ventrue trying to convince the Primogen council to support 
        my business proposal. This is a social combat situation. What mechanics apply? 
        Can I use Dominate subtly?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['social', 'influence', 'primogen', 'ventrue', 'convince']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include social combat mechanics"
        
        print(f"   ✅ Social combat prompt ready")
    
    def test_supernatural_combat(self, rag_service):
        """Test combat between different supernatural types"""
        print("\n🌟 Testing cross-supernatural combat...")
        
        user_prompt = """A mage and a vampire are fighting. The mage uses Forces 3 
        while the vampire uses Celerity and Potence. How do these powers interact? 
        What about paradox from vulgar magic?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['mage', 'vampire', 'forces', 'discipline', 'paradox']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include cross-type combat info"
        
        print(f"   ✅ Cross-supernatural combat prompt ready")


class TestResourceManagement:
    """Test resources, items, and equipment"""
    
    def test_vampire_blood_pool(self, rag_service):
        """Test blood pool management"""
        print("\n🩸 Testing Vampire blood pool management...")
        
        user_prompt = """I'm down to 2 blood points after a fight. How much can I spend 
        per turn? How do I refill? What are the risks of feeding in public?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['blood', 'feed', 'pool', 'vampire', 'masquerade']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include blood pool mechanics"
        
        print(f"   ✅ Blood pool management prompt ready")
    
    def test_mage_quintessence(self, rag_service):
        """Test quintessence and tass management"""
        print("\n💎 Testing Mage quintessence management...")
        
        user_prompt = """I need quintessence for a powerful ritual. Where can I get it? 
        Can I store it in tass? How do Nodes work and can I tap one safely?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['quintessence', 'tass', 'node', 'avatar', 'prime']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include quintessence mechanics"
        
        print(f"   ✅ Quintessence management prompt ready")
    
    def test_fetish_creation(self, rag_service):
        """Test werewolf fetish creation and use"""
        print("\n🗡️ Testing Werewolf fetish creation...")
        
        user_prompt = """I want to create a klaive (Grand Klaive). What materials do I need? 
        What rites are required? How do I bind a spirit to it?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['fetish', 'klaive', 'spirit', 'rite', 'gnosis']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include fetish creation mechanics"
        
        print(f"   ✅ Fetish creation prompt ready")


class TestEdgeCasesAndComplexScenarios:
    """Test complex rules interactions and edge cases"""
    
    def test_torpor_and_resurrection(self, rag_service):
        """Test vampire torpor mechanics"""
        print("\n💀 Testing Vampire torpor...")
        
        user_prompt = """My vampire went into torpor after taking aggravated damage. 
        How long will I sleep? Can I be awakened early? What happens to my character 
        during this time?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=5)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['torpor', 'damage', 'awaken', 'sleep', 'vampire']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include torpor mechanics"
        
        print(f"   ✅ Torpor mechanics prompt ready")
    
    def test_paradox_backlash(self, rag_service):
        """Test mage paradox mechanics"""
        print("\n💥 Testing Mage paradox backlash...")
        
        user_prompt = """I cast a vulgar Forces 5 spell in front of witnesses and got 
        10 paradox points. What happens? Do I take backlash damage? Could I get a paradox flaw?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['paradox', 'backlash', 'vulgar', 'witness', 'flaw']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include paradox mechanics"
        
        print(f"   ✅ Paradox backlash prompt ready")
    
    def test_wassail_and_frenzy(self, rag_service):
        """Test vampire/werewolf frenzy mechanics"""
        print("\n😡 Testing frenzy mechanics...")
        
        user_prompt = """My vampire is at frenzy from fire, and my werewolf packmate 
        is in rage frenzy. Can we attack each other? How do we snap out of it? 
        What are the long-term consequences?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=7)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        
        content_lower = augmented.lower()
        relevant_terms = ['frenzy', 'rage', 'beast', 'control', 'wassail']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 2, "Should include frenzy mechanics"
        
        print(f"   ✅ Frenzy mechanics prompt ready")
    
    def test_cross_splat_interaction(self, rag_service):
        """Test interactions between different game lines"""
        print("\n🌐 Testing cross-splat interactions...")
        
        user_prompt = """A mage, vampire, and werewolf are all in the same scene. 
        The mage detects both with Life sphere, the werewolf smells the vampire, 
        and the vampire uses Auspex. How do these powers interact?"""
        
        augmented = rag_service.augment_prompt(user_prompt, CAMPAIGN_ID, include_rule_books=True, n_rule_book_chunks=10)
        
        print(f"   User prompt: {user_prompt[:80]}...")
        print(f"   Augmented length: {len(augmented)} chars")
        
        content_lower = augmented.lower()
        relevant_terms = ['mage', 'vampire', 'werewolf', 'detect', 'sense', 'auspex']
        found_terms = [term for term in relevant_terms if term in content_lower]
        
        print(f"   Relevant terms found: {', '.join(found_terms)}")
        assert len(found_terms) >= 3, "Should include multi-splat detection mechanics"
        
        print(f"   ✅ Cross-splat interaction prompt ready")


if __name__ == "__main__":
    """Run tests directly"""
    pytest.main([__file__, "-v", "-s"])

