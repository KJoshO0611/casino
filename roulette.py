import random
from enum import Enum
from typing import Dict, List, Tuple

class BetType(Enum):
    STRAIGHT_UP = "Straight Up"
    SPLIT = "Split (2 numbers)"
    STREET = "Street (3 numbers)"
    CORNER = "Corner (4 numbers)"
    FIRST_FOUR = "First Four (0,1,2,3)"
    LINE = "Line (6 numbers)"
    RED = "Red"
    BLACK = "Black"
    ODD = "Odd"
    EVEN = "Even"
    LOW = "Low (1-18)"
    HIGH = "High (19-36)"
    DOZEN_1 = "1st Dozen (1-12)"
    DOZEN_2 = "2nd Dozen (13-24)"
    DOZEN_3 = "3rd Dozen (25-36)"
    COLUMN_1 = "1st Column"
    COLUMN_2 = "2nd Column"
    COLUMN_3 = "3rd Column"

class RouletteWheel:
    def __init__(self):
        self.numbers: Dict[int, str] = {
            0: 'green',
            **{i: 'red' for i in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]},
            **{i: 'black' for i in [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]}
        }
        self.payouts: Dict[BetType, int] = {
            BetType.STRAIGHT_UP: 35,
            BetType.SPLIT: 17,
            BetType.STREET: 11,
            BetType.CORNER: 8,
            BetType.FIRST_FOUR: 8,
            BetType.LINE: 5,
            BetType.RED: 1,
            BetType.BLACK: 1,
            BetType.ODD: 1,
            BetType.EVEN: 1,
            BetType.LOW: 1,
            BetType.HIGH: 1,
            BetType.DOZEN_1: 2,
            BetType.DOZEN_2: 2,
            BetType.DOZEN_3: 2,
            BetType.COLUMN_1: 2,
            BetType.COLUMN_2: 2,
            BetType.COLUMN_3: 2,
        }

    def spin(self) -> Tuple[int, str]:
        number = random.randint(0, 36)
        return number, self.numbers[number]

    def check_win(self, bet_type: BetType, bet_value, winning_number: int) -> bool:
        if bet_type == BetType.STRAIGHT_UP:
            return bet_value == winning_number
        
        # New bet types that take a list of numbers
        if bet_type in [BetType.SPLIT, BetType.STREET, BetType.CORNER, BetType.LINE, BetType.FIRST_FOUR]:
            return winning_number in bet_value

        # All outside bets lose on 0
        if winning_number == 0:
            return False

        winning_color = self.numbers[winning_number]

        if bet_type == BetType.RED:
            return winning_color == 'red'
        if bet_type == BetType.BLACK:
            return winning_color == 'black'
        if bet_type == BetType.ODD:
            return winning_number % 2 != 0
        if bet_type == BetType.EVEN:
            return winning_number % 2 == 0
        if bet_type == BetType.LOW:
            return 1 <= winning_number <= 18
        if bet_type == BetType.HIGH:
            return 19 <= winning_number <= 36
        if bet_type == BetType.DOZEN_1:
            return 1 <= winning_number <= 12
        if bet_type == BetType.DOZEN_2:
            return 13 <= winning_number <= 24
        if bet_type == BetType.DOZEN_3:
            return 25 <= winning_number <= 36
        if bet_type == BetType.COLUMN_1:
            return winning_number % 3 == 1
        if bet_type == BetType.COLUMN_2:
            return winning_number % 3 == 2
        if bet_type == BetType.COLUMN_3:
            return winning_number % 3 == 0
        return False

class RouletteGame:
    def __init__(self):
        self.players_bets: Dict[int, List[Tuple[BetType, any, int]]] = {}
        self.wheel = RouletteWheel()

    def place_bet(self, user_id: int, bet_type: BetType, bet_value, amount: int):
        if user_id not in self.players_bets:
            self.players_bets[user_id] = []
        self.players_bets[user_id].append((bet_type, bet_value, amount))

    def resolve_bets(self):
        winning_number, winning_color = self.wheel.spin()
        payouts: Dict[int, int] = {}

        for user_id, bets in self.players_bets.items():
            total_payout = 0
            for bet_type, bet_value, amount in bets:
                if self.wheel.check_win(bet_type, bet_value, winning_number):
                    payout_ratio = self.wheel.payouts[bet_type]
                    # Return the original bet plus the winnings
                    total_payout += (amount * payout_ratio) + amount
        
            if total_payout > 0:
                payouts[user_id] = total_payout
    
        self.players_bets.clear()
        return payouts, winning_number, winning_color
