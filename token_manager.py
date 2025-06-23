import json
import os
from typing import Dict

CHIPS_FILE = "casino_chips.json"

class TokenManager:
    def __init__(self, file_path: str = CHIPS_FILE):
        self.file_path = file_path
        self.data: Dict[str, Dict[str, int]] = self._load_data()

    def _load_data(self) -> Dict[str, Dict[str, int]]:
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_data(self) -> None:
        with open(self.file_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def _get_user_data(self, user_id: int) -> Dict[str, int]:
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {'chips': 1000, 'loan': 0}
        return self.data[user_id]

    def get_chips(self, user_id: int) -> int:
        return self._get_user_data(user_id).get('chips', 0)

    def set_chips(self, user_id: int, amount: int) -> None:
        user_data = self._get_user_data(user_id)
        user_data['chips'] = amount
        repayment_message = self._check_loan_repayment(user_id)
        self._save_data()
        return repayment_message

    def add_chips(self, user_id: int, amount: int) -> str:
        user_data = self._get_user_data(user_id)
        current_chips = user_data.get('chips', 0)
        user_data['chips'] = current_chips + amount
        repayment_message = self._check_loan_repayment(user_id)
        self._save_data()
        return repayment_message

    def get_loan(self, user_id: int) -> int:
        return self._get_user_data(user_id).get('loan', 0)

    def grant_loan(self, user_id: int, amount: int) -> tuple:
        user_data = self._get_user_data(user_id)
        if user_data.get('loan', 0) > 0:
            return False, "You already have an outstanding loan."
        
        user_data['loan'] = amount
        self.add_chips(user_id, amount)
        self._save_data()
        return True, f"Granted a loan of {amount:,} chips."

    def _check_loan_repayment(self, user_id: int) -> str:
        user_data = self._get_user_data(user_id)
        loan = user_data.get('loan', 0)
        if loan <= 0:
            return None

        chips = user_data.get('chips', 0)
        if chips >= loan * 1.1:
            user_data['chips'] -= loan
            user_data['loan'] = 0
            self._save_data()
            return f"Your loan of {loan:,} chips has been automatically repaid!"
        return None

    def repay_loan(self, user_id, amount):
        user_data = self._get_user_data(user_id)
        loan = user_data.get('loan', 0)

        if loan <= 0:
            return False, "You don't have an outstanding loan."

        if amount > user_data['chips']:
            return False, "You don't have enough chips to repay that amount."
        
        if amount > loan:
            amount = loan

        user_data['chips'] -= amount
        user_data['loan'] -= amount
        self._save_data()

        if user_data['loan'] == 0:
            return True, f"You have fully repaid your loan!"
        else:
            return True, f"You have repaid {amount:,} chips. Your remaining loan is {user_data['loan']:,} chips."

    def get_all_chips(self) -> Dict[str, int]:
        """Returns the entire dictionary of user IDs and their chip counts."""
        return {user_id: user_data['chips'] for user_id, user_data in self.data.items()}

# Singleton instance to be used across cogs
token_manager = TokenManager()
