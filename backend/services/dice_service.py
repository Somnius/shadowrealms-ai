"""
ShadowRealms AI - Dice Rolling Service
Old World of Darkness d10 Pool Mechanics
"""

import random
import json
from typing import List, Dict, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DiceService:
    """Service for handling World of Darkness dice rolls"""
    
    @staticmethod
    def roll_d10_pool(pool_size: int, difficulty: int = 6, specialty: bool = False) -> Dict:
        """
        Roll a pool of d10s using old World of Darkness mechanics
        
        Args:
            pool_size: Number of d10s to roll
            difficulty: Target number for success (default 6)
            specialty: If True, 10s count as 2 successes (specialty roll)
        
        Returns:
            Dict with roll results and analysis
        """
        if pool_size < 1:
            return {
                'results': [],
                'successes': 0,
                'is_botch': False,
                'is_critical': False,
                'difficulty': difficulty,
                'specialty': specialty,
                'message': 'No dice to roll'
            }
        
        if difficulty < 2 or difficulty > 10:
            difficulty = 6  # Default to 6 if invalid
        
        # Roll the dice
        results = [random.randint(1, 10) for _ in range(pool_size)]
        
        # Count successes and ones
        successes = 0
        ones_count = 0
        
        for die in results:
            if die == 1:
                ones_count += 1
                successes -= 1  # 1s cancel successes
            elif die >= difficulty:
                if die == 10 and specialty:
                    successes += 2  # Specialty: 10s count as 2 successes
                else:
                    successes += 1
        
        # Determine outcome
        is_botch = (successes < 0 or (successes == 0 and ones_count > 0))
        is_critical = successes >= 5  # 5+ successes is exceptional
        
        # Generate message
        if is_botch:
            message = "💀 **BOTCH!** Critical failure!"
        elif successes == 0:
            message = "❌ **Failure** - No successes"
        elif is_critical:
            message = f"🌟 **CRITICAL SUCCESS!** {successes} successes!"
        elif successes == 1:
            message = f"✅ Success ({successes} success)"
        else:
            message = f"✅ Success ({successes} successes)"
        
        return {
            'results': results,
            'successes': max(0, successes),  # Don't show negative
            'is_botch': is_botch,
            'is_critical': is_critical,
            'difficulty': difficulty,
            'specialty': specialty,
            'ones_count': ones_count,
            'message': message
        }
    
    @staticmethod
    def roll_contested(attacker_pool: int, defender_pool: int, 
                      difficulty: int = 6) -> Dict:
        """
        Roll a contested action (both sides roll, compare successes)
        
        Args:
            attacker_pool: Attacker's dice pool
            defender_pool: Defender's dice pool
            difficulty: Target number (same for both)
        
        Returns:
            Dict with both rolls and winner determination
        """
        attacker_roll = DiceService.roll_d10_pool(attacker_pool, difficulty)
        defender_roll = DiceService.roll_d10_pool(defender_pool, difficulty)
        
        # Determine winner
        attacker_success = attacker_roll['successes']
        defender_success = defender_roll['successes']
        
        if attacker_roll['is_botch']:
            winner = 'defender'
            margin = defender_success
            message = "💀 Attacker botched! Defender wins automatically!"
        elif defender_roll['is_botch']:
            winner = 'attacker'
            margin = attacker_success
            message = "💀 Defender botched! Attacker wins automatically!"
        elif attacker_success > defender_success:
            winner = 'attacker'
            margin = attacker_success - defender_success
            message = f"⚔️ Attacker wins by {margin} success{'es' if margin != 1 else ''}!"
        elif defender_success > attacker_success:
            winner = 'defender'
            margin = defender_success - attacker_success
            message = f"🛡️ Defender wins by {margin} success{'es' if margin != 1 else ''}!"
        else:
            winner = 'tie'
            margin = 0
            message = "⚖️ Tie! Both sides have equal successes."
        
        return {
            'attacker_roll': attacker_roll,
            'defender_roll': defender_roll,
            'winner': winner,
            'margin': margin,
            'message': message
        }
    
    @staticmethod
    def roll_extended(pool_size: int, difficulty: int, target_successes: int,
                     max_rolls: int = 10) -> Dict:
        """
        Roll an extended action (accumulate successes over multiple rolls)
        
        Args:
            pool_size: Dice pool size
            difficulty: Target number
            target_successes: Total successes needed
            max_rolls: Maximum number of rolls allowed
        
        Returns:
            Dict with all rolls and whether target was reached
        """
        rolls = []
        total_successes = 0
        
        for roll_num in range(1, max_rolls + 1):
            roll_result = DiceService.roll_d10_pool(pool_size, difficulty)
            rolls.append(roll_result)
            
            if roll_result['is_botch']:
                # Botch ends the extended action in failure
                return {
                    'rolls': rolls,
                    'total_successes': total_successes,
                    'target_reached': False,
                    'botched': True,
                    'roll_count': roll_num,
                    'message': f"💀 **BOTCH on roll {roll_num}!** Extended action failed!"
                }
            
            total_successes += roll_result['successes']
            
            if total_successes >= target_successes:
                return {
                    'rolls': rolls,
                    'total_successes': total_successes,
                    'target_reached': True,
                    'botched': False,
                    'roll_count': roll_num,
                    'message': f"✅ Success! Reached {total_successes} successes in {roll_num} roll{'s' if roll_num != 1 else ''}!"
                }
        
        # Ran out of rolls
        return {
            'rolls': rolls,
            'total_successes': total_successes,
            'target_reached': False,
            'botched': False,
            'roll_count': max_rolls,
            'message': f"❌ Failed to reach target. Only {total_successes}/{target_successes} successes after {max_rolls} rolls."
        }
    
    @staticmethod
    def calculate_difficulty_modifier(base_difficulty: int, modifiers: List[Dict]) -> int:
        """
        Calculate final difficulty based on modifiers
        
        Args:
            base_difficulty: Starting difficulty
            modifiers: List of modifier dicts with 'type' and 'value'
        
        Returns:
            Final difficulty (clamped between 2 and 10)
        """
        final_difficulty = base_difficulty
        
        for mod in modifiers:
            if mod.get('type') == 'difficulty':
                final_difficulty += mod.get('value', 0)
        
        # Clamp between 2 and 10
        return max(2, min(10, final_difficulty))
    
    @staticmethod
    def ai_determine_pool(action_type: str, context: Dict) -> Tuple[int, int]:
        """
        AI determines appropriate dice pool and difficulty for an action
        
        Args:
            action_type: Type of action ('npc_attack', 'weather', 'event', etc.)
            context: Dict with relevant context (npc_power_level, difficulty_level, etc.)
        
        Returns:
            Tuple of (pool_size, difficulty)
        """
        # Base values
        pool_size = 5
        difficulty = 6
        
        # Adjust based on action type
        if action_type == 'npc_attack':
            # NPC combat action
            power_level = context.get('npc_power_level', 'average')
            if power_level == 'weak':
                pool_size = random.randint(2, 4)
            elif power_level == 'average':
                pool_size = random.randint(4, 6)
            elif power_level == 'strong':
                pool_size = random.randint(7, 10)
            elif power_level == 'legendary':
                pool_size = random.randint(10, 15)
        
        elif action_type == 'npc_social':
            # NPC social interaction
            charisma_level = context.get('charisma', 'average')
            if charisma_level == 'low':
                pool_size = random.randint(2, 4)
            elif charisma_level == 'average':
                pool_size = random.randint(4, 7)
            elif charisma_level == 'high':
                pool_size = random.randint(7, 10)
        
        elif action_type == 'weather':
            # Weather randomness
            severity = context.get('severity', 'moderate')
            pool_size = random.randint(3, 6)
            if severity == 'mild':
                difficulty = 4
            elif severity == 'severe':
                difficulty = 8
        
        elif action_type == 'event':
            # Random event occurrence
            probability = context.get('probability', 'moderate')
            if probability == 'unlikely':
                difficulty = 8
            elif probability == 'likely':
                difficulty = 4
            pool_size = random.randint(4, 8)
        
        elif action_type == 'mystery':
            # Clue discovery or mystery resolution
            complexity = context.get('complexity', 'moderate')
            if complexity == 'simple':
                difficulty = 5
                pool_size = random.randint(3, 5)
            elif complexity == 'complex':
                difficulty = 7
                pool_size = random.randint(5, 8)
            elif complexity == 'arcane':
                difficulty = 9
                pool_size = random.randint(6, 10)
        
        return (pool_size, difficulty)
    
    @staticmethod
    def format_roll_for_chat(roll_data: Dict, character_name: str = None, 
                            action_description: str = None) -> str:
        """
        Format a dice roll for display in chat
        
        Args:
            roll_data: Roll results from roll_d10_pool
            character_name: Name of character rolling (optional)
            action_description: Description of the action (optional)
        
        Returns:
            Formatted string for chat display
        """
        header = "🎲 **Dice Roll**"
        if character_name:
            header = f"🎲 **{character_name}** rolls"
        if action_description:
            header += f" for **{action_description}**"
        
        # Format dice results with color coding
        dice_display = []
        for die in roll_data['results']:
            if die == 1:
                dice_display.append(f"[💀{die}]")  # Botch
            elif die == 10:
                dice_display.append(f"[⭐{die}]")  # Perfect
            elif die >= roll_data['difficulty']:
                dice_display.append(f"[✓{die}]")  # Success
            else:
                dice_display.append(f"[{die}]")  # Failure
        
        dice_str = " ".join(dice_display)
        
        result = [
            header,
            f"Dice: {dice_str}",
            f"Difficulty: {roll_data['difficulty']} | Successes: {roll_data['successes']}",
            roll_data['message']
        ]
        
        return "\n".join(result)


# Singleton instance
dice_service = DiceService()

