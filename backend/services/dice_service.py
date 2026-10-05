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
    def roll_d10_pool(
        pool_size: int,
        difficulty: int = 6,
        specialty: bool = False,
        leniency_floor: int | None = None,
        willpower: bool = False,
        rng=None,
        reroll_ones_cancel: bool = False,
    ) -> Dict:
        """
        Roll a classic (oWoD Revised) d10 pool. Delegates to services.wod_dice so the
        app has one classic implementation.

        Args:
            pool_size: Number of d10s to roll
            difficulty: Target number for success (2-10, default 6)
            specialty: natural 10s count and are rerolled (rerolled 10s explode again)
            leniency_floor: room leniency floor (2-10) or None
            willpower: +1 automatic success that 1s cannot cancel
            rng: optional random.Random for deterministic tests
            reroll_ones_cancel: 1s on specialty rerolls cancel successes (Mage;
                services.rules_edition.reroll_ones_cancel)
        """
        from services.wod_dice import roll_classic

        if pool_size < 1:
            return {
                'rules_edition': 'classic',
                'results': [],
                'successes': 0,
                'is_botch': False,
                'is_critical': False,
                'is_exceptional': False,
                'difficulty': difficulty,
                'specialty': specialty,
                'willpower': willpower,
                'message': 'No dice to roll'
            }

        if difficulty < 2 or difficulty > 10:
            difficulty = 6  # Default to 6 if invalid

        r = roll_classic(
            pool_size,
            difficulty,
            specialty=specialty,
            willpower=willpower,
            leniency_floor=leniency_floor,
            rng=rng,
            reroll_ones_cancel=reroll_ones_cancel,
        )
        return DiceService.classic_result_dict(r)

    @staticmethod
    def classic_result_dict(r) -> Dict:
        """Turn a wod_dice.StorytellerRollResult into the API roll_result dict."""
        successes = r.net_successes
        if r.botch:
            message = "**BOTCH!** No die succeeded and a 1 showed."
        elif successes == 0:
            message = "**Failure** - No successes"
        elif r.exceptional:
            message = f"**Exceptional success!** {successes} successes"
        elif successes == 1:
            message = f"Success ({successes} success)"
        else:
            message = f"Success ({successes} successes)"
        return {
            'rules_edition': 'classic',
            'results': list(r.dice),
            'specialty_rerolls': list(r.specialty_rerolls),
            'reroll_ones_cancel': r.reroll_ones_cancel,
            'successes': successes,
            'raw_successes': r.raw_successes,
            'is_botch': r.botch,
            # Kept for older clients: for classic this means "exceptional" (5+ successes).
            'is_critical': r.exceptional,
            'is_exceptional': r.exceptional,
            'difficulty': r.difficulty,
            'specialty': r.specialty,
            'willpower': r.willpower,
            'ones_count': r.ones,
            'message': message,
            'leniency_floor': r.leniency_floor,
        }

    @staticmethod
    def roll_v5_pool(
        pool_size: int,
        hunger: int = 0,
        difficulty: int = 1,
        v5_leniency: Dict | None = None,
        rng=None,
    ) -> Dict:
        """Roll a V5 pool (services.v5_dice) and add a chat-friendly message.

        v5_leniency: the room's V5 switches (no_bestial / no_messy / min_successes) or None.
        """
        from services.v5_dice import roll_v5

        res = roll_v5(pool_size, hunger, difficulty, v5_leniency=v5_leniency, rng=rng)
        res['message'] = DiceService.v5_message(res)
        return res

    @staticmethod
    def v5_message(res: Dict) -> str:
        from services.v5_dice import outcome_label

        label = outcome_label(res)
        n = res['successes']
        succ = f"{n} success{'es' if n != 1 else ''}"
        return f"**{label}** ({succ} vs difficulty {res['difficulty']})"

    @staticmethod
    def format_v5_roll_for_chat(roll_data: Dict, character_name: str = None,
                                action_description: str = None) -> str:
        header = "**Dice Roll** (V5)"
        if character_name:
            header = f"**{character_name}** rolls (V5)"
        if action_description:
            header += f" for **{action_description}**"
        from services.v5_dice import describe_v5_leniency

        lenient = describe_v5_leniency(roll_data.get('v5_leniency'))
        if lenient:
            where = "first roll only; the reroll is plain" if roll_data.get('rerolled') else "this roll"
            header += f"\n_Room leniency (V5, {where}): {lenient}._\n"

        def show(d, hunger):
            if d >= 6:
                return f"[✓{d}]"
            if hunger and d == 1:
                return f"[✗{d}]"
            return f"[{d}]"

        normal = " ".join(show(d, False) for d in roll_data.get('normal_dice', []))
        hunger = " ".join(show(d, True) for d in roll_data.get('hunger_dice', []))
        lines = [header, f"Dice: {normal}" + (f" | Hunger: {hunger}" if hunger else "")]
        if roll_data.get('rerolled'):
            line = f"Willpower reroll of dice #{', '.join(str(i + 1) for i in roll_data.get('rerolled_indices', []))}"
            cost = roll_data.get('willpower_cost')
            if cost == 'superficial':
                line += " · Willpower −1"
            elif cost == 'aggravated':
                line += " · Willpower −1 (track full: a Superficial box turned Aggravated)"
            lines.append(line)
        lines.append(
            f"Difficulty: {roll_data['difficulty']} | Successes: {roll_data['successes']} | Margin: {roll_data['margin']:+d}"
        )
        lines.append(roll_data.get('message') or DiceService.v5_message(roll_data))
        return "\n".join(lines)

    @staticmethod
    def roll_contested(attacker_pool: int, defender_pool: int,
                      difficulty: int = 6, rules_edition: str = 'classic',
                      attacker_hunger: int = 0, defender_hunger: int = 0,
                      rng=None) -> Dict:
        """
        Roll a contested action (both sides roll, compare successes)
        
        Args:
            attacker_pool: Attacker's dice pool
            defender_pool: Defender's dice pool
            difficulty: Target number (same for both); ignored for V5
            rules_edition: 'classic' or 'v5'
            rng: optional random.Random for deterministic tests

        V5 (core p. 123): the attacker is the acting character and wins ties, i.e. the
        attacker wins when attacker successes >= defender successes. Each side's outcome,
        critical, messy critical and bestial failure are then set from the contest result
        (see DiceService.v5_contest_side), not from a difficulty.
        
        Returns:
            Dict with both rolls and winner determination
        """
        if rules_edition == 'v5':
            return DiceService._roll_contested_v5(
                attacker_pool, defender_pool, attacker_hunger, defender_hunger, rng
            )

        attacker_roll = DiceService.roll_d10_pool(attacker_pool, difficulty, rng=rng)
        defender_roll = DiceService.roll_d10_pool(defender_pool, difficulty, rng=rng)
        
        # Determine winner
        attacker_success = attacker_roll['successes']
        defender_success = defender_roll['successes']
        
        if attacker_roll['is_botch']:
            winner = 'defender'
            margin = defender_success
            message = "Attacker botched! Defender wins automatically!"
        elif defender_roll['is_botch']:
            winner = 'attacker'
            margin = attacker_success
            message = "Defender botched! Attacker wins automatically!"
        elif attacker_success > defender_success:
            winner = 'attacker'
            margin = attacker_success - defender_success
            message = f"Attacker wins by {margin} success{'es' if margin != 1 else ''}!"
        elif defender_success > attacker_success:
            winner = 'defender'
            margin = defender_success - attacker_success
            message = f"Defender wins by {margin} success{'es' if margin != 1 else ''}!"
        else:
            winner = 'tie'
            margin = 0
            message = "Tie! Both sides have equal successes."
        
        return {
            'rules_edition': 'classic',
            'attacker_roll': attacker_roll,
            'defender_roll': defender_roll,
            'winner': winner,
            'margin': margin,
            'message': message
        }

    @staticmethod
    def v5_contest_side(res: Dict, won: bool, opponent_successes: int) -> Dict:
        """
        Re-label one side of a V5 contest from the contest result (pure; mutates and
        returns ``res``). A side that won is a win, critical when it has a pair of 10s,
        messy when one of those 10s is a Hunger die. A side that lost is a failure,
        bestial when any Hunger die shows a 1. ``difficulty`` stays 0 (contests have
        no difficulty); ``margin`` is successes minus the opponent's successes.
        """
        pairs = res.get('critical_pairs', 0)
        hunger_tens = sum(1 for d in res.get('hunger_dice', []) if d == 10)
        res['outcome'] = 'win' if won else 'fail'
        res['is_critical'] = bool(won and pairs >= 1)
        res['is_messy_critical'] = bool(res['is_critical'] and hunger_tens > 0)
        res['is_bestial_failure'] = bool(
            (not won) and any(d == 1 for d in res.get('hunger_dice', []))
        )
        res['is_total_failure'] = res['successes'] == 0
        res['contest_won'] = bool(won)
        res['opponent_successes'] = opponent_successes
        res['margin'] = res['successes'] - opponent_successes
        from services.v5_dice import outcome_label

        label = outcome_label(res)
        if res['is_total_failure'] and won:
            label = 'Win (0 successes)'
        n = res['successes']
        res['message'] = (
            f"**{label}** ({n} success{'es' if n != 1 else ''} "
            f"vs {opponent_successes})"
        )
        return res

    @staticmethod
    def _roll_contested_v5(attacker_pool, defender_pool, attacker_hunger, defender_hunger, rng=None) -> Dict:
        attacker_roll = DiceService.roll_v5_pool(attacker_pool, attacker_hunger, 0, rng=rng)
        defender_roll = DiceService.roll_v5_pool(defender_pool, defender_hunger, 0, rng=rng)
        return DiceService.resolve_contested_v5(attacker_roll, defender_roll)

    @staticmethod
    def resolve_contested_v5(attacker_roll: Dict, defender_roll: Dict) -> Dict:
        """Decide a V5 contest from two resolved rolls (pure). Ties go to the attacker."""
        a, d = attacker_roll['successes'], defender_roll['successes']
        attacker_wins = a >= d
        DiceService.v5_contest_side(attacker_roll, attacker_wins, d)
        DiceService.v5_contest_side(defender_roll, not attacker_wins, a)
        if attacker_wins:
            winner, margin = 'attacker', a - d
            if margin == 0:
                message = "Tie on successes: the attacker (acting character) wins with margin 0."
            else:
                message = f"Attacker wins by {margin} success{'es' if margin != 1 else ''}!"
        else:
            winner, margin = 'defender', d - a
            message = f"Defender wins by {margin} success{'es' if margin != 1 else ''}!"
        extras = []
        for side, r in (('Attacker', attacker_roll), ('Defender', defender_roll)):
            if r['is_messy_critical']:
                extras.append(f"{side}: messy critical")
            elif r['is_critical']:
                extras.append(f"{side}: critical win")
            if r['is_bestial_failure']:
                extras.append(f"{side}: bestial failure")
        if extras:
            message += " (" + "; ".join(extras) + ")"
        return {
            'rules_edition': 'v5',
            'attacker_roll': attacker_roll,
            'defender_roll': defender_roll,
            'winner': winner,
            'margin': margin,
            'message': message,
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
                    'message': f"**BOTCH on roll {roll_num}!** Extended action failed!"
                }
            
            total_successes += roll_result['successes']
            
            if total_successes >= target_successes:
                return {
                    'rolls': rolls,
                    'total_successes': total_successes,
                    'target_reached': True,
                    'botched': False,
                    'roll_count': roll_num,
                    'message': f"Success! Reached {total_successes} successes in {roll_num} roll{'s' if roll_num != 1 else ''}!"
                }
        
        # Ran out of rolls
        return {
            'rolls': rolls,
            'total_successes': total_successes,
            'target_reached': False,
            'botched': False,
            'roll_count': max_rolls,
            'message': f"Failed to reach target. Only {total_successes}/{target_successes} successes after {max_rolls} rolls."
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
        header = "**Dice Roll**"
        if character_name:
            header = f"**{character_name}** rolls"
        if action_description:
            header += f" for **{action_description}**"

        lf = roll_data.get('leniency_floor')
        leniency_line = ""
        if lf is not None:
            leniency_line = (
                f"\n_Leniency floor **{lf}** (Classic: no 1s; with 2+ dice, one die ≥ {lf})._\n"
            )
        
        # Format dice results with color coding
        dice_display = []
        for die in roll_data['results']:
            if die == 1:
                dice_display.append(f"[✗{die}]")  # Botch
            elif die == 10:
                dice_display.append(f"[✓{die}]")  # Perfect
            elif die >= roll_data['difficulty']:
                dice_display.append(f"[✓{die}]")  # Success
            else:
                dice_display.append(f"[{die}]")  # Failure
        
        dice_str = " ".join(dice_display)
        rerolls = roll_data.get('specialty_rerolls') or []
        if rerolls:
            dice_str += " | specialty rerolls: " + " ".join(f"[{d}]" for d in rerolls)
        if roll_data.get('willpower'):
            dice_str += " | Willpower +1"
        
        result = [
            header + leniency_line,
            f"Dice: {dice_str}",
            f"Difficulty: {roll_data['difficulty']} | Successes: {roll_data['successes']}",
            roll_data['message']
        ]
        
        return "\n".join(result)


# Singleton instance
dice_service = DiceService()

