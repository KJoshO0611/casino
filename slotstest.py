import random
from collections import Counter
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import json
from enum import Enum


class WinLevel(Enum):
    """Enumeration for different win levels"""
    NO_WIN = 0
    SMALL_WIN = 1
    NICE_WIN = 2
    BIG_WIN = 3
    MEGA_JACKPOT = 4


@dataclass
class SlotConfig:
    """Configuration class for slot machine settings"""
    SYMBOLS: List[str] = None
    SYMBOL_WEIGHTS: Dict[str, int] = None
    PAYOUTS: Dict[Tuple[str, int], int] = None
    BIG_WIN_MULTIPLIER: float = 15.0
    
    def __post_init__(self):
        if self.SYMBOLS is None:
            self.SYMBOLS = ['🍒', '🍋', '🍊', '🍉', '⭐', '🔔', '💎', 'BAR']
        
        if self.SYMBOL_WEIGHTS is None:
            # Adjusted weights: rare symbols less frequent
            self.SYMBOL_WEIGHTS = {
                '🍒': 250,
                '🍋': 180,
                '🍊': 120,
                '🍉': 80,
                '⭐': 12,     # Medium rare
                '🔔': 8,      # Rare
                '💎': 2,      # Very rare
                'BAR': 2      # Ultra rare
            }

        if self.PAYOUTS is None:
            self.PAYOUTS = {
                # Common fruits
                ('🍒', 2): 0.5,
                ('🍒', 3): 1.2,
                ('🍋', 2): 0.8,
                ('🍋', 3): 2.0,
                ('🍊', 2): 1.0,
                ('🍊', 3): 2.5,
                ('🍉', 2): 1.2,
                ('🍉', 3): 3.0,

                # Premiums
                ('⭐', 2): 1.5,
                ('⭐', 3): 6.0,      # ↑ small boost for 8x+ excitement
                ('🔔', 2): 2.5,
                ('🔔', 3): 10.0,     # ↑ to allow 8x+ range
                ('💎', 2): 3.0,
                ('💎', 3): 12.0,     # ↓ keeps balance but allows big win range
                ('BAR', 2): 10.0,
                ('BAR', 3): 25.0,    # ↓ from 30 but more accessible

                # Mixed combinations
                ('ANY_FRUIT_2', 2): 0.3,
                ('ANY_FRUIT_3', 3): 1.0,
                ('ANY_PREMIUM_2', 2): 1.0,
                ('ANY_PREMIUM_3', 3): 2.0,
                ('MIXED_HIGH', 3): 1.5   # ↑ a bit for fun without impacting RTP much
            }


@dataclass
class PlayerStats:
    """Player statistics and history tracking"""
    total_spins: int = 0
    total_bet: int = 0
    total_winnings: int = 0
    biggest_win: int = 0
    biggest_win_multiplier: float = 0.0
    spin_history: List[Dict] = None
    
    def __post_init__(self):
        if self.spin_history is None:
            self.spin_history = []
    
    def add_spin(self, result: List[str], bet: int, winnings: int):
        """Add a spin to the player's history"""
        multiplier = winnings / bet if bet > 0 else 0.0
        
        spin_record = {
            'result': result,
            'bet': bet,
            'winnings': winnings,
            'multiplier': multiplier,
            'spin_number': self.total_spins + 1
        }
        
        self.spin_history.append(spin_record)
        self.total_spins += 1
        self.total_bet += bet
        self.total_winnings += winnings
        
        if winnings > self.biggest_win:
            self.biggest_win = winnings
            self.biggest_win_multiplier = multiplier
    
    def get_rtp(self) -> float:
        """Calculate player's actual return-to-player percentage"""
        if self.total_bet == 0:
            return 0.0
        return (self.total_winnings / self.total_bet) * 100
    
    def get_recent_spins(self, count: int = 10) -> List[Dict]:
        """Get the most recent spins"""
        return self.spin_history[-count:] if len(self.spin_history) >= count else self.spin_history


class SlotMachine:
    """
    A slot machine game with weighted symbols, payout calculations, and balanced for ~85% RTP.
    """
    
    def __init__(self, config: Optional[SlotConfig] = None):
        """
        Initialize the slot machine.
        
        Args:
            config: Optional configuration object. If None, uses default configuration.
        """
        self.config = config or SlotConfig()
        self.players: Dict[int, PlayerStats] = {}
        self._validate_configuration()
        self._precompute_weights()
        
        # Define symbol sets for mixed combinations
        self.fruit_symbols = {'🍒', '🍋', '🍊', '🍉'}
        self.premium_symbols = {'⭐', '🔔', '💎'}
        self.high_value_symbols = {'⭐', '🔔', '💎', 'BAR'}
    
    def _validate_configuration(self) -> None:
        """Validate the slot machine configuration"""
        if not self.config.SYMBOLS:
            raise ValueError("SYMBOLS list cannot be empty")
        
        if len(self.config.SYMBOLS) != len(set(self.config.SYMBOLS)):
            raise ValueError("SYMBOLS must be unique")
        
        for symbol in self.config.SYMBOLS:
            if symbol not in self.config.SYMBOL_WEIGHTS:
                raise ValueError(f"Symbol '{symbol}' missing from SYMBOL_WEIGHTS")
        
        for weight in self.config.SYMBOL_WEIGHTS.values():
            if weight <= 0:
                raise ValueError("All symbol weights must be positive")
    
    def _precompute_weights(self) -> None:
        """Precompute base weights for performance optimization"""
        self._base_weights = [self.config.SYMBOL_WEIGHTS[symbol] for symbol in self.config.SYMBOLS]
    
    def _get_or_create_player(self, player_id: int) -> PlayerStats:
        """Get existing player stats or create new ones"""
        if player_id not in self.players:
            self.players[player_id] = PlayerStats()
        return self.players[player_id]
    
    def pull_lever(self, player_id: int) -> List[str]:
        """
        Simulate pulling the slot machine lever.
        
        Args:
            player_id: Unique identifier for the player
            
        Returns:
            List of three symbols representing the reel results
        """
        if not isinstance(player_id, int):
            raise TypeError("player_id must be an integer")
        
        result = random.choices(self.config.SYMBOLS, weights=self._base_weights, k=3)
        return result
    
    def calculate_winnings(self, player_id: int, result: List[str], bet: int) -> int:
        """
        Calculate winnings and update player statistics.
        
        Args:
            player_id: Unique identifier for the player
            result: List of three symbols from the reels
            bet: Amount bet on this spin
            
        Returns:
            Winnings amount (bet * payout_multiplier)
        """
        if bet <= 0:
            raise ValueError("Bet must be positive")
        
        if not isinstance(result, list) or len(result) != 3:
            raise ValueError("Result must be a list of exactly 3 symbols")
        
        for symbol in result:
            if symbol not in self.config.SYMBOLS:
                raise ValueError(f"Invalid symbol in result: '{symbol}'")
        
        player_stats = self._get_or_create_player(player_id)
        counts = Counter(result)
        winnings = 0
        winning_combination = None
        
        # FIXED: Check for the HIGHEST paying combination, not just the first match
        max_winnings = 0
        best_combination = None
        
        # Check for exact symbol matches first (highest priority)
        for (symbol, count), payout_multiplier in self.config.PAYOUTS.items():
            if not symbol.startswith('ANY_') and not symbol.startswith('MIXED_'):
                if counts[symbol] >= count:
                    potential_winnings = int(bet * payout_multiplier)
                    if potential_winnings > max_winnings:
                        max_winnings = potential_winnings
                        best_combination = f"{count} × {symbol}"
        
        # Check for combination wins if they pay more
        combo_winnings, combo_description = self._check_combination_wins(result, bet)
        if combo_winnings > max_winnings:
            max_winnings = combo_winnings
            best_combination = combo_description
        
        winnings = max_winnings
        winning_combination = best_combination
        
        # Update player statistics
        player_stats.add_spin(result, bet, winnings)
        
        return winnings
    
    def _check_combination_wins(self, result: List[str], bet: int) -> Tuple[int, Optional[str]]:
        """
        Check for mixed combination wins.
        
        Args:
            result: List of three symbols from the reels
            bet: Amount bet on this spin
            
        Returns:
            Tuple of (winnings, winning_combination_description)
        """
        result_set = set(result)
        counts = Counter(result)
        max_winnings = 0
        best_combo = None
        
        # Check for 3 different premium symbols (highest combo payout)
        premium_in_result = result_set.intersection(self.premium_symbols)
        if len(premium_in_result) == 3 and len(result_set) == 3:
            payout = self.config.PAYOUTS.get(('ANY_PREMIUM_3', 3), 0)
            if payout > 0:
                potential_winnings = int(bet * payout)
                if potential_winnings > max_winnings:
                    max_winnings = potential_winnings
                    best_combo = "3 Different Premium"
        
        # Check for 3 different fruits
        fruit_in_result = result_set.intersection(self.fruit_symbols)
        if len(fruit_in_result) == 3 and len(result_set) == 3:
            payout = self.config.PAYOUTS.get(('ANY_FRUIT_3', 3), 0)
            if payout > 0:
                potential_winnings = int(bet * payout)
                if potential_winnings > max_winnings:
                    max_winnings = potential_winnings
                    best_combo = "3 Different Fruits"
        
        # Check for mixed high-value combinations (any 3 high-value symbols)
        high_value_in_result = result_set.intersection(self.high_value_symbols)
        if len(high_value_in_result) == 3 and len(result_set) == 3:
            payout = self.config.PAYOUTS.get(('MIXED_HIGH', 3), 0)
            if payout > 0:
                potential_winnings = int(bet * payout)
                if potential_winnings > max_winnings:
                    max_winnings = potential_winnings
                    best_combo = "3 High-Value Mixed"
        
        # Check for 2 of the same premium symbol
        for symbol in self.premium_symbols:
            if counts[symbol] == 2:
                payout = self.config.PAYOUTS.get(('ANY_PREMIUM_2', 2), 0)
                if payout > 0:
                    potential_winnings = int(bet * payout)
                    if potential_winnings > max_winnings:
                        max_winnings = potential_winnings
                        best_combo = f"2 × {symbol}"
        
        # Check for 2 of the same fruit
        for symbol in self.fruit_symbols:
            if counts[symbol] == 2:
                payout = self.config.PAYOUTS.get(('ANY_FRUIT_2', 2), 0)
                if payout > 0:
                    potential_winnings = int(bet * payout)
                    if potential_winnings > max_winnings:
                        max_winnings = potential_winnings
                        best_combo = f"2 × {symbol}"
        
        return max_winnings, best_combo
    
    def get_win_description(self, winnings: int, bet: int) -> str:
        """Get descriptive text for different win levels."""
        if bet <= 0:
            return "Invalid bet"
        
        multiplier = winnings / bet
        
        if multiplier >= 75:
            return "🎰💰 MEGA JACKPOT! 💰🎰"
        elif multiplier >= 25:
            return "💎💎 DIAMOND WIN! 💎💎"
        elif multiplier >= 15:
            return "🔥🔥 BIG WIN! 🔥🔥"
        elif multiplier >= 8:
            return "⭐ SUPER WIN! ⭐"
        elif multiplier >= 4:
            return "🎉 Nice Win! 🎉"
        elif multiplier > 1:
            return "✨ Winner! ✨"
        else:
            return "Better luck next time!"
    
    def get_win_level(self, winnings: int, bet: int) -> WinLevel:
        """Get the win level enum for programmatic use."""
        if bet <= 0:
            return WinLevel.NO_WIN
        
        multiplier = winnings / bet
        
        if multiplier >= 75:
            return WinLevel.MEGA_JACKPOT
        elif multiplier >= 15:
            return WinLevel.BIG_WIN
        elif multiplier >= 4:
            return WinLevel.NICE_WIN
        elif multiplier > 1:
            return WinLevel.SMALL_WIN
        else:
            return WinLevel.NO_WIN
    
    def calculate_theoretical_rtp(self) -> float:
        """
        Calculate the theoretical Return-to-Player percentage using Monte Carlo simulation.
        """
        total_bet = 0
        total_winnings = 0
        simulations = 500000  # Increased for better accuracy
        
        for _ in range(simulations):
            result = random.choices(self.config.SYMBOLS, weights=self._base_weights, k=3)
            bet = 100  # Use consistent bet amount
            
            # Use the same logic as calculate_winnings but without player tracking
            counts = Counter(result)
            max_winnings = 0
            
            # Check exact matches first
            for (symbol, count), payout_multiplier in self.config.PAYOUTS.items():
                if not symbol.startswith('ANY_') and not symbol.startswith('MIXED_'):
                    if counts[symbol] >= count:
                        potential_winnings = int(bet * payout_multiplier)
                        max_winnings = max(max_winnings, potential_winnings)
            
            # Check combination wins
            combo_winnings, _ = self._check_combination_wins(result, bet)
            max_winnings = max(max_winnings, combo_winnings)
            
            total_bet += bet
            total_winnings += max_winnings
        
        return (total_winnings / total_bet) * 100 if total_bet > 0 else 0.0
    
    def get_player_stats(self, player_id: int) -> Optional[PlayerStats]:
        """Get player statistics."""
        return self.players.get(player_id)
    
    def save_player_state(self, player_id: int) -> Optional[Dict]:
        """Serialize player state for persistence."""
        player_stats = self.players.get(player_id)
        if not player_stats:
            return None
        
        return {
            'total_spins': player_stats.total_spins,
            'total_bet': player_stats.total_bet,
            'total_winnings': player_stats.total_winnings,
            'biggest_win': player_stats.biggest_win,
            'biggest_win_multiplier': player_stats.biggest_win_multiplier,
            'spin_history': player_stats.spin_history[-100:]
        }
    
    def load_player_state(self, player_id: int, state: Dict) -> None:
        """Restore player state from saved data."""
        player_stats = PlayerStats(
            total_spins=state.get('total_spins', 0),
            total_bet=state.get('total_bet', 0),
            total_winnings=state.get('total_winnings', 0),
            biggest_win=state.get('biggest_win', 0),
            biggest_win_multiplier=state.get('biggest_win_multiplier', 0.0),
            spin_history=state.get('spin_history', [])
        )
        self.players[player_id] = player_stats
    
    def reset_player_stats(self, player_id: int) -> None:
        """Reset all statistics for a player."""
        if player_id in self.players:
            self.players[player_id] = PlayerStats()


# Enhanced multi-player simulation with better reporting
def simulate_multiple_players_variable_spins(slot_machine, player_spins: List[int], bet_amount=100):
    """
    Simulate multiple players on the same slot machine with varying spin counts.
    
    Args:
        slot_machine: Instance of SlotMachine
        player_spins: List of spin counts per player
        bet_amount: Fixed bet per spin
    """
    print("🎰 VARIABLE SPIN SLOT SIMULATION 🎰")
    print(f"Theoretical RTP: {slot_machine.calculate_theoretical_rtp():.2f}%")
    print(f"Simulating {len(player_spins)} players with varying spin counts")
    print("=" * 60)

    player_results = []
    all_big_wins = []

    for i, spins in enumerate(player_spins, 1):
        player_id = i
        print(f"\n👤 PLAYER {player_id} - {spins} Spins:")
        print("-" * 40)

        big_wins = []
        super_wins = []
        nice_wins = []

        for spin_num in range(spins):
            result = slot_machine.pull_lever(player_id)
            winnings = slot_machine.calculate_winnings(player_id, result, bet_amount)
            multiplier = winnings / bet_amount if bet_amount > 0 else 0

            if multiplier >= 15:
                big_wins.append({'spin': spin_num + 1, 'result': result, 'winnings': winnings, 'multiplier': multiplier, 'player': player_id})
                all_big_wins.append(big_wins[-1])
            elif multiplier >= 8:
                super_wins.append({'spin': spin_num + 1, 'result': result, 'winnings': winnings, 'multiplier': multiplier})
            elif multiplier >= 4:
                nice_wins.append({'spin': spin_num + 1, 'result': result, 'winnings': winnings, 'multiplier': multiplier})

        stats = slot_machine.get_player_stats(player_id)
        net_result = stats.total_winnings - stats.total_bet

        print(f"\n📊 Final Results:")
        print(f"  Total Bet: ${stats.total_bet:,}")
        print(f"  Total Won: ${stats.total_winnings:,}")
        print(f"  Net Result: ${net_result:,} {'🟢' if net_result > 0 else '🔴'}")
        print(f"  RTP: {stats.get_rtp():.2f}%")
        print(f"  Biggest Win: ${stats.biggest_win} ({stats.biggest_win_multiplier:.1f}x)")
        print(f"  Big Wins: {len(big_wins)} | Super Wins: {len(super_wins)} | Nice Wins: {len(nice_wins)}")

        player_results.append({
            'player_id': player_id,
            'spins': spins,
            'total_bet': stats.total_bet,
            'total_winnings': stats.total_winnings,
            'net_result': net_result,
            'rtp': stats.get_rtp(),
            'biggest_win': stats.biggest_win,
            'biggest_multiplier': stats.biggest_win_multiplier,
            'big_wins': len(big_wins),
            'super_wins': len(super_wins),
            'nice_wins': len(nice_wins)
        })

    # Summary
    print("\n" + "=" * 60)
    print("📈 OVERALL SUMMARY")
    print("=" * 60)

    total_bet_all = sum(p['total_bet'] for p in player_results)
    total_won_all = sum(p['total_winnings'] for p in player_results)
    overall_rtp = (total_won_all / total_bet_all) * 100
    positive_players = sum(1 for p in player_results if p['net_result'] > 0)

    print(f"🎯 Players with Positive Results: {positive_players}/{len(player_spins)}")
    print(f"💰 Overall RTP: {overall_rtp:.2f}%")
    print(f"💸 Total Wagered: ${total_bet_all:,}")
    print(f"🎰 Total Payouts: ${total_won_all:,}")
    print(f"🏠 House Edge: ${total_bet_all - total_won_all:,}")
    print(f"🎉 Excitement Factor: Big Wins: {sum(p['big_wins'] for p in player_results)}, Super Wins: {sum(p['super_wins'] for p in player_results)}, Nice Wins: {sum(p['nice_wins'] for p in player_results)}")

    if all_big_wins:
        print("\n🏆 TOP BIG WINS:")
        for i, win in enumerate(sorted(all_big_wins, key=lambda x: x['multiplier'], reverse=True)[:5], 1):
            print(f"{i}. Player {win['player']}, Spin {win['spin']}: {' '.join(win['result'])} → ${win['winnings']} ({win['multiplier']:.1f}x)")



# Test the balanced slot machine
if __name__ == "__main__":
    slot_machine = SlotMachine()
    
    # Simulate players with varying spin counts
    spin_distribution = [10000000]
    simulate_multiple_players_variable_spins(slot_machine, player_spins=spin_distribution, bet_amount=10)
