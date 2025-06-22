import json
import os
from typing import Dict

CHIPS_FILE = "casino_chips.json"

class TokenManager:
    def __init__(self, file_path: str = CHIPS_FILE):
        self.file_path = file_path
        self.user_chips: Dict[str, int] = self._load_chips()

    def _load_chips(self) -> Dict[str, int]:
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_chips(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.user_chips, f, indent=4)

    def get_chips(self, user_id: int) -> int:
        return self.user_chips.get(str(user_id), 1000)  # Default to 1000 chips

    def set_chips(self, user_id: int, amount: int):
        self.user_chips[str(user_id)] = amount
        self._save_chips()

    def add_chips(self, user_id: int, amount: int):
        current_chips = self.get_chips(user_id)
        self.set_chips(user_id, current_chips + amount)

    def get_all_chips(self) -> Dict[str, int]:
        """Returns the entire dictionary of user IDs and their chip counts."""
        return self.user_chips

# Singleton instance to be used across cogs
token_manager = TokenManager()
