import json
import os
from typing import Dict, Optional

# Use the persistent data directory
DATA_DIR = "data" 
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    
CHIPS_FILE = os.path.join(DATA_DIR, "casino_chips.json")
MAX_LOAN = 5000
CASINO_POOL_ID = "casino_pool"
INITIAL_POOL_BALANCE = 1_000_000 # Give the pool some starting money

class TokenManager:
    def __init__(self, file_path: str = CHIPS_FILE):
        self.file_path = file_path
        self.CASINO_POOL_ID = CASINO_POOL_ID
        self._ensure_data_directory()
        self.data: Dict[str, Dict[str, int]] = self._load_data()
        self._ensure_casino_pool()

    def _ensure_data_directory(self) -> None:
        """Ensure the data directory exists."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def _load_data(self) -> Dict[str, Dict[str, int]]:
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_data(self) -> None:
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except IOError as e:
            print(f"Error saving data to {self.file_path}: {e}")

    def _ensure_casino_pool(self):
        """Ensures the casino pool account exists and has a balance."""
        if CASINO_POOL_ID not in self.data:
            self.data[CASINO_POOL_ID] = {'chips': INITIAL_POOL_BALANCE, 'loan': 0}
            self._save_data()

    def _get_user_data(self, user_id: any) -> Dict[str, int]:
        user_id = str(user_id)
        user_data = self.data.get(user_id)

        if not isinstance(user_data, dict):
            current_chips = user_data if isinstance(user_data, int) else 1000
            self.data[user_id] = {'chips': current_chips, 'loan': 0}
        else:
            if 'chips' not in user_data:
                user_data['chips'] = 1000
            if 'loan' not in user_data:
                user_data['loan'] = 0
        
        return self.data[user_id]

    def get_chips(self, user_id: int) -> int:
        return self._get_user_data(user_id)['chips']

    def get_pool_balance(self) -> int:
        """Gets the current chip balance of the casino pool."""
        return self._get_user_data(CASINO_POOL_ID)['chips']

    def set_chips(self, user_id: int, amount: int):
        user_data = self._get_user_data(user_id)
        user_data['chips'] = amount
        self._check_loan_repayment(user_id) # This saves data
        
    def add_chips(self, user_id: int, amount: int, source_id: Optional[str] = None) -> Optional[str]:
        """
        Adds chips to a user.
        If source_id is provided, it transfers from that source.
        If source_id is None, chips are magically created (e.g., for admin grants).
        """
        if source_id:
            source_data = self._get_user_data(source_id)
            if source_data['chips'] < amount:
                return "Source has insufficient chips."
            source_data['chips'] -= amount

        user_data = self._get_user_data(user_id)
        user_data['chips'] += amount
        
        repayment_message = self._check_loan_repayment(user_id)
        self._save_data()
        return repayment_message

    def remove_chips(self, user_id: int, amount: int, destination_id: str = CASINO_POOL_ID) -> bool:
        """Removes chips from a user and gives them to a destination (defaults to casino pool)."""
        user_data = self._get_user_data(user_id)
        if user_data['chips'] < amount:
            # Not enough chips, can't remove
            return False
            
        destination_data = self._get_user_data(destination_id)
        
        user_data['chips'] -= amount
        destination_data['chips'] += amount
        
        self._save_data()
        return True

    def get_loan(self, user_id: int) -> int:
        return self._get_user_data(user_id).get('loan', 0)

    def grant_loan(self, user_id: int, amount: int) -> tuple:
        if amount <= 0:
            return False, "You must request a positive amount of chips for a loan."

        user_data = self._get_user_data(user_id)
        current_loan = user_data.get('loan', 0)
        
        pool_balance = self.get_pool_balance()
        if amount > pool_balance:
            return False, "The casino pool doesn't have enough chips to grant this loan."

        if current_loan >= MAX_LOAN:
            return False, f"You have already reached your loan limit of {MAX_LOAN:,} chips and cannot borrow more."

        if current_loan + amount > MAX_LOAN:
            remaining_loan = MAX_LOAN - current_loan
            return False, f"This loan would exceed your {MAX_LOAN:,} chip limit. You can borrow up to {remaining_loan:,} more."

        # Transfer chips from pool to user
        self.add_chips(user_id, amount, source_id=CASINO_POOL_ID)
        
        # Update user's loan amount
        user_data['loan'] += amount
        self._save_data() # add_chips already saves, but this makes sure loan is saved.
        
        return True, f"Granted a loan of {amount:,} chips. Your total outstanding loan is now {user_data['loan']:,}."

    def _check_loan_repayment(self, user_id: int) -> Optional[str]:
        user_data = self._get_user_data(user_id)
        loan = user_data.get('loan', 0)
        if loan <= 0:
            return None

        # Auto-repay if user has 10% more chips than their loan amount
        if user_data['chips'] >= loan * 1.1:
            # Repay the loan fully
            self.repay_loan(user_id, loan)
            return f"Your loan of {loan:,} chips has been automatically repaid!"
        return None

    def repay_loan(self, user_id, amount: int) -> tuple:
        user_data = self._get_user_data(user_id)
        loan = user_data.get('loan', 0)

        if loan <= 0:
            return False, "You don't have an outstanding loan."

        if amount > user_data['chips']:
            return False, "You don't have enough chips to repay that amount."
        
        # Can't repay more than the loan amount
        repayment_amount = min(amount, loan)

        # Transfer chips from user to pool
        self.remove_chips(user_id, repayment_amount, destination_id=CASINO_POOL_ID)
        
        # Update user's loan
        user_data['loan'] -= repayment_amount
        self._save_data() # remove_chips already saves, but this makes sure loan is saved.

        if user_data['loan'] == 0:
            return True, f"You have fully repaid your loan!"
        else:
            return True, f"You have repaid {repayment_amount:,} chips. Your remaining loan is {user_data['loan']:,} chips."

    def get_all_chips(self) -> Dict[str, int]:
        """Returns the entire dictionary of user IDs and their chip counts."""
        return {user_id: user_data['chips'] for user_id, user_data in self.data.items() if user_id != CASINO_POOL_ID}

# Singleton instance to be used across cogs
token_manager = TokenManager()