"""
OOC (Out of Character) Monitoring Service
Monitors OOC rooms for in-character discussions and warns/bans players
"""

import logging
from typing import Dict, Tuple
from services.llm_service import LLMService
from database import get_db
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OOCMonitor:
    """Monitors OOC rooms for rule violations"""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.warning_threshold = 3  # 3 warnings = temp ban
        self.ban_duration_hours = 24  # 24 hour ban
    
    def check_message(self, message: str, user_id: int, campaign_id: int, location_type: str) -> Tuple[bool, str, bool]:
        """
        Check if a message violates OOC rules
        
        Args:
            message: The message content
            user_id: User ID who sent the message
            campaign_id: Campaign ID
            location_type: Type of location ('ooc' or other)
        
        Returns:
            Tuple of (is_violation, warning_message, should_ban)
        """
        
        # Only monitor OOC rooms
        if location_type != 'ooc':
            return (False, '', False)
        
        # Check if message is in-character using AI
        is_violation = self._detect_ic_content(message, campaign_id)
        
        if not is_violation:
            return (False, '', False)
        
        # Log the violation
        warning_count = self._log_violation(user_id, campaign_id)
        
        # Determine action
        should_ban = warning_count >= self.warning_threshold
        
        if should_ban:
            # Issue temporary ban
            self._issue_temp_ban(user_id, campaign_id)
            warning_msg = (
                f"⚠️ **OOC VIOLATION - TEMPORARY BAN ISSUED**\n\n"
                f"You have been temporarily banned from this campaign for {self.ban_duration_hours} hours.\n\n"
                f"**Reason:** Multiple violations of OOC rules (3+ warnings).\n\n"
                f"The OOC (Out of Character) Lobby is for discussing the game as players, not roleplaying as characters. "
                f"Please keep in-character discussions to the game locations.\n\n"
                f"Your ban will expire at: {self._get_ban_expiry()}"
            )
        else:
            warnings_left = self.warning_threshold - warning_count
            warning_msg = (
                f"⚠️ **OOC VIOLATION WARNING ({warning_count}/{self.warning_threshold})**\n\n"
                f"Your message appears to contain in-character content. "
                f"The OOC (Out of Character) Lobby is for discussing the game as players, not roleplaying as characters.\n\n"
                f"**Please keep in-character discussions to the game locations.**\n\n"
                f"You have **{warnings_left} warning(s)** remaining before a temporary ban is issued."
            )
        
        logger.warning(f"OOC violation by user {user_id} in campaign {campaign_id}. Warning count: {warning_count}")
        
        return (True, warning_msg, should_ban)
    
    def _detect_ic_content(self, message: str, campaign_id: int) -> bool:
        """
        Use AI to detect if message contains in-character content
        
        Returns:
            True if message is in-character, False if it's OOC
        """
        
        try:
            # Get campaign context
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, description, game_system
                FROM campaigns
                WHERE id = %s
            """, (campaign_id,))
            
            campaign = cursor.fetchone()
            if not campaign:
                return False
            
            campaign_name = campaign[0]
            campaign_desc = campaign[1]
            game_system = campaign[2]
            
            # Build AI prompt to detect IC content
            prompt = f"""You are monitoring an OOC (Out of Character) chat room for the campaign "{campaign_name}" ({game_system} system).

The OOC room is for players to discuss the game as themselves, ask questions, coordinate schedules, and chat about non-game topics.

IN-CHARACTER content (roleplay) should NOT be in the OOC room and is a violation.

Analyze this message and determine if it contains in-character roleplay:

Message: "{message}"

Is this message in-character roleplay? Answer with ONLY "YES" or "NO" followed by a brief reason.

Examples of VIOLATIONS (in-character):
- "I draw my sword and attack the vampire!"
- "*sneaks through the shadows*"
- "My character says 'We should investigate the temple'"
- Describing character actions in first person as if playing the character

Examples of ACCEPTABLE (out-of-character):
- "What time are we playing tonight?"
- "I think my character should investigate the temple next session"
- "Does anyone know the rules for combat?"
- "Hey, I'll be late for the next game"
- "That was a great session last time!"

Answer:"""
            
            # Call LLM with fast, lightweight model
            response = self.llm_service.generate_response(
                prompt=prompt,
                context={},
                config={
                    'model': 'llama3.2:3b',  # Fast, lightweight model
                    'temperature': 0.3,  # Low temperature for consistent detection
                    'max_tokens': 100,
                    'task_type': 'moderation'
                }
            )
            
            response_text = response.get('text', '').strip().upper()
            
            # Check if response indicates violation
            is_violation = response_text.startswith('YES')
            
            if is_violation:
                logger.info(f"IC content detected: {message[:50]}... | AI response: {response_text[:100]}")
            
            return is_violation
            
        except Exception as e:
            logger.error(f"Error detecting IC content: {e}")
            # Fail open - don't ban if AI is unavailable
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _log_violation(self, user_id: int, campaign_id: int) -> int:
        """
        Log an OOC violation and return total warning count
        
        Returns:
            Total number of warnings for this user in this campaign (last 7 days)
        """
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # Create violations table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ooc_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    violated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            """)
            
            # Log this violation
            cursor.execute("""
                INSERT INTO ooc_violations (user_id, campaign_id)
                VALUES (%s, %s)
            """, (user_id, campaign_id))
            
            # Count violations in last 7 days
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute("""
                SELECT COUNT(*)
                FROM ooc_violations
                WHERE user_id = %s 
                AND campaign_id = %s
                AND violated_at > %s
            """, (user_id, campaign_id, seven_days_ago))
            
            warning_count = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
            
            return warning_count
            
        except Exception as e:
            logger.error(f"Error logging OOC violation: {e}")
            return 0
    
    def _issue_temp_ban(self, user_id: int, campaign_id: int):
        """Issue a temporary ban to a user for OOC violations"""
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            ban_until = (datetime.now() + timedelta(hours=self.ban_duration_hours)).isoformat()
            
            cursor.execute("""
                UPDATE users
                SET banned_until = %s,
                    ban_reason = %s
                WHERE id = %s
            """, (
                ban_until,
                f"Temporary ban for repeated OOC violations in campaign ID {campaign_id}. "
                f"Please review the OOC room rules: No in-character roleplay in OOC.",
                user_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.warning(f"Issued {self.ban_duration_hours}h temp ban to user {user_id} for OOC violations")
            
        except Exception as e:
            logger.error(f"Error issuing temp ban: {e}")
    
    def _get_ban_expiry(self) -> str:
        """Get formatted ban expiry time"""
        expiry = datetime.now() + timedelta(hours=self.ban_duration_hours)
        return expiry.strftime("%Y-%m-%d %H:%M UTC")
    
    def check_user_ban(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if a user is currently banned
        
        Returns:
            Tuple of (is_banned, ban_message)
        """
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT banned_until, ban_reason
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row or not row['ban_until']:
                return (False, '')
            
            banned_until_str = row['ban_until']
            ban_reason = row['ban_reason']
            
            # Parse ban expiry
            banned_until = datetime.fromisoformat(banned_until_str)
            
            # Check if ban has expired
            if datetime.now() >= banned_until:
                # Ban expired, clear it
                self._clear_ban(user_id)
                return (False, '')
            
            # User is still banned
            time_left = banned_until - datetime.now()
            hours_left = int(time_left.total_seconds() / 3600)
            minutes_left = int((time_left.total_seconds() % 3600) / 60)
            
            ban_message = (
                f"⛔ **You are temporarily banned from this campaign.**\n\n"
                f"**Reason:** {ban_reason}\n\n"
                f"**Time remaining:** {hours_left}h {minutes_left}m\n\n"
                f"**Ban expires:** {banned_until.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            
            return (True, ban_message)
            
        except Exception as e:
            logger.error(f"Error checking user ban: {e}")
            return (False, '')
    
    def _clear_ban(self, user_id: int):
        """Clear a user's ban after it expires"""
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users
                SET banned_until = NULL,
                    ban_reason = NULL
                WHERE id = %s
            """, (user_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleared expired ban for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error clearing ban: {e}")


def create_ooc_monitor(llm_service: LLMService) -> OOCMonitor:
    """Factory function to create OOC monitor instance"""
    return OOCMonitor(llm_service)

