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
        # Pity system state
        self.pity_counters = {}
        self.pity_eligible_symbols = ['🍒', '🍋', '🍊', '🍉', '⭐', '🔔']

    def pull_lever(self, player_id: int) -> list[str]:
        """Simulates pulling the lever and returns the result of the three reels, considering player pity."""
        pity_level = self.pity_counters.get(player_id, 0)

        # First reel is always random
        reel1_result = random.choice(self.reels[0])
        
        # If the first symbol is eligible for pity, subsequent reels are weighted
        if reel1_result in self.pity_eligible_symbols:
            reel2_weights = [1] * len(self.reels[1])
            reel3_weights = [1] * len(self.reels[2])
            try:
                # Increase weight for matching symbol
                reel2_weights[self.reels[1].index(reel1_result)] += pity_level
                reel3_weights[self.reels[2].index(reel1_result)] += pity_level
            except ValueError:
                pass # Should not happen with current config
            
            reel2_result = random.choices(self.reels[1], weights=reel2_weights, k=1)[0]
            reel3_result = random.choices(self.reels[2], weights=reel3_weights, k=1)[0]
        else:
            # No pity for 'BAR'
            reel2_result = random.choice(self.reels[1])
            reel3_result = random.choice(self.reels[2])

        return [reel1_result, reel2_result, reel3_result]

    def calculate_winnings(self, player_id: int, result: list[str], bet: int) -> int:
        """Calculates the winnings and updates the player's pity counter."""
        counts = Counter(result)
        winnings = 0
        
        # Sort payouts by payout amount descending to ensure we check for the best win first
        sorted_payouts = sorted(self.payouts.items(), key=lambda item: item[1], reverse=True)

        for (symbol, count), payout_multiplier in sorted_payouts:
            if counts[symbol] >= count:
                winnings = bet * payout_multiplier
                break # Found the best win, no need to check for lesser wins

        if winnings > 0:
            # Reset pity counter on a win
            self.pity_counters[player_id] = 0
        else:
            # Increment pity counter on a loss
            self.pity_counters[player_id] = self.pity_counters.get(player_id, 0) + 1
            
        return winnings
