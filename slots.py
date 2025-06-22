import random
from collections import Counter

class SlotMachine:
    def __init__(self):
        self.reels = [
            ['🍒', '🍋', '🍊', '🍉', '⭐', '🔔', 'BAR'],
            ['🍒', '🍋', '🍊', '🍉', '⭐', '🔔', 'BAR'],
            ['🍒', '🍋', '🍊', '🍉', '⭐', '🔔', 'BAR']
        ]
        self.payouts = {
            ('🍒', 3): 10,
            ('🍋', 3): 15,
            ('🍊', 3): 20,
            ('🍉', 3): 25,
            ('⭐', 3): 50,
            ('🔔', 3): 75,
            ('BAR', 3): 100,
            ('🍒', 2): 2,
        }

    def pull_lever(self) -> list[str]:
        """Simulates pulling the lever and returns the result of the three reels."""
        return [random.choice(reel) for reel in self.reels]

    def calculate_winnings(self, result: list[str], bet: int) -> int:
        """Calculates the winnings based on the slot result and the initial bet."""
        counts = Counter(result)
        for symbol, count in counts.items():
            if (symbol, count) in self.payouts:
                return bet * self.payouts[(symbol, count)]
        return 0
