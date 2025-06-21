import json
import os
from typing import Dict
import dotenv

dotenv.load_dotenv()

# Token storage - In production, use a database
USER_TOKENS_FILE = "user_tokens.json"

def load_user_tokens() -> Dict[str, int]:
    """Load user tokens from file"""
    if os.path.exists(USER_TOKENS_FILE):
        with open(USER_TOKENS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_tokens(tokens_data: Dict[str, int]):
    """Save user tokens to file"""
    with open(USER_TOKENS_FILE, 'w') as f:
        json.dump(tokens_data, f, indent=2)

class TokenManager:
    def __init__(self):
        self.tokens = load_user_tokens()
        
    def get_tokens(self, user_id: str) -> int:
        """Get user's token balance"""
        return self.tokens.get(user_id, 1000)
        
    def add_tokens(self, user_id: str, amount: int) -> None:
        """Add tokens to user's balance"""
        self.tokens[user_id] = self.tokens.get(user_id, 1000) + amount
        save_user_tokens(self.tokens)
        
    def remove_tokens(self, user_id: str, amount: int) -> bool:
        """Remove tokens from user's balance"""
        if user_id not in self.tokens:
            self.tokens[user_id] = 1000
        
        if self.tokens[user_id] < amount:
            return False
            
        self.tokens[user_id] -= amount
        save_user_tokens(self.tokens)
        return True
        
    def set_tokens(self, user_id: str, amount: int) -> None:
        """Set user's token balance"""
        self.tokens[user_id] = amount
        save_user_tokens(self.tokens)
        
    def can_afford(self, user_id: str, amount: int) -> bool:
        """Check if user can afford the amount"""
        return self.tokens.get(user_id, 1000) >= amount
        
    def get_leaderboard(self, limit: int = 10) -> list:
        """Get token leaderboard"""
        sorted_users = sorted(
            self.tokens.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_users[:limit]
