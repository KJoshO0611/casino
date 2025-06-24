import json
import os
from typing import Dict, Optional

# Use the persistent data directory
DATA_DIR = "/app/data"
CHIPS_FILE = os.path.join(DATA_DIR, "casino_chips.json")
MAX_LOAN = 5000

class TokenManager:
    def __init__(self, file_path: str = CHIPS_FILE):
        self.file_path = file_path
        self._ensure_data_directory()
        self.data: Dict[str, Dict[str, int]] = self._load_data()

    def _ensure_data_directory(self) -> None:
        """Ensure the data directory exists."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def _load_data(self) -> Dict[str, Dict[str, int]]:
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist, check for default file and copy it
            default_file = "/app/data/casino_chips.json.default"
            if os.path.exists(default_file):
                try:
                    with open(default_file, 'r') as f:
                        data = json.load(f)
                        # Save the default data to the actual file
                        with open(self.file_path, 'w') as out_f:
                            json.dump(data, out_f, indent=4)
                        return data
                except (json.JSONDecodeError, IOError):
                    pass
            return {}

    def _save_data(self) -> None:
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except IOError as e:
            print(f"Error saving data to {self.file_path}: {e}")
            # Could implement fallback or retry logic here

    def _get_user_data(self, user_id: int) -> Dict[str, int]:
        user_id = str(user_id)
        user_data = self.data.get(user_id)

        if not isinstance(user_data, dict):
            # If data is malformed (e.g. an int) or doesn't exist, create a new entry.
            # We can try to preserve the old chip count if it was an int.
            current_chips = user_data if isinstance(user_data, int) else 1000
            self.data[user_id] = {'chips': current_chips, 'loan': 0}
        else:
            # Ensure the required keys are present.
            if 'chips' not in user_data:
                user_data['chips'] = 1000
            if 'loan' not in user_data:
                user_data['loan'] = 0
        
        return self.data[user_id]

    def get_chips(self, user_id: int) -> int:
        return self._get_user_data(user_id)['chips']

    def set_chips(self, user_id: int, amount: int) -> Optional[str]:
        user_data = self._get_user_data(user_id)
        user_data['chips'] = amount
        repayment_message = self._check_loan_repayment(user_id)
        self._save_data()
        return repayment_message

    def add_chips(self, user_id: int, amount: int) -> Optional[str]:
        user_data = self._get_user_data(user_id)
        user_data['chips'] += amount
        repayment_message = self._check_loan_repayment(user_id)
        self._save_data()
        return repayment_message

    def get_loan(self, user_id: int) -> int:
        return self._get_user_data(user_id).get('loan', 0)

    def grant_loan(self, user_id: int, amount: int) -> tuple:
        if amount <= 0:
            return False, "You must request a positive amount of chips for a loan."

        user_data = self._get_user_data(user_id)
        current_loan = user_data.get('loan', 0)

        if current_loan >= MAX_LOAN:
            return False, f"You have already reached your loan limit of {MAX_LOAN:,} chips and cannot borrow more."

        if current_loan + amount > MAX_LOAN:
            remaining_loan = MAX_LOAN - current_loan
            return False, f"This loan would exceed your {MAX_LOAN:,} chip limit. You can borrow up to {remaining_loan:,} more."

        user_data['loan'] += amount
        # self.add_chips calls _save_data(), so the change to 'loan' will be persisted.
        self.add_chips(user_id, amount)
        
        return True, f"Granted a loan of {amount:,} chips. Your total outstanding loan is now {user_data['loan']:,}."

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