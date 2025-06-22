import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import json
import os
from datetime import datetime

# Poker game classes and enums
class Suit(Enum):
    HEARTS = "♥️"
    DIAMONDS = "♦️"
    CLUBS = "♣️"
    SPADES = "♠️"

class Rank(Enum):
    TWO = (2, "2")
    THREE = (3, "3")
    FOUR = (4, "4")
    FIVE = (5, "5")
    SIX = (6, "6")
    SEVEN = (7, "7")
    EIGHT = (8, "8")
    NINE = (9, "9")
    TEN = (10, "10")
    JACK = (11, "J")
    QUEEN = (12, "Q")
    KING = (13, "K")
    ACE = (14, "A")
    
    def __init__(self, numeric_value, display):
        self.numeric_value = numeric_value
        self.display = display

class GameState(Enum):
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    ENDED = "ended"

@dataclass
class Card:
    rank: Rank
    suit: Suit
    
    def __str__(self):
        return f"{self.rank.display}{self.suit.value}"

@dataclass
class Player:
    user_id: int
    username: str
    chips: int = 1000
    current_bet: int = 0
    total_bet: int = 0
    cards: List[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    acted: bool = False

class Deck:
    def __init__(self):
        self.cards = []
        self.reset()
    
    def reset(self):
        self.cards = [Card(rank, suit) for rank in Rank for suit in Suit]
        random.shuffle(self.cards)
    
    def deal(self) -> Card:
        return self.cards.pop()

class HandEvaluator:
    @staticmethod
    def evaluate_hand(cards: List[Card]) -> Tuple[int, List[int]]:
        """Returns (hand_rank, tiebreakers) where higher is better"""
        if len(cards) < 5:
            return (0, [])
        
        # Sort cards by rank (high to low)
        sorted_cards = sorted(cards, key=lambda c: c.rank.numeric_value, reverse=True)
        ranks = [c.rank.numeric_value for c in sorted_cards]
        suits = [c.suit for c in sorted_cards]
        
        # Count ranks
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        # Check for flush
        suit_counts = {}
        for suit in suits:
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
        is_flush = max(suit_counts.values()) >= 5
        
        # Check for straight
        unique_ranks = sorted(set(ranks), reverse=True)
        is_straight = False
        straight_high = 0
        
        # Check for regular straight
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                is_straight = True
                straight_high = unique_ranks[i]
                break
        
        # Check for A-2-3-4-5 straight (wheel)
        if not is_straight and set([14, 5, 4, 3, 2]).issubset(set(unique_ranks)):
            is_straight = True
            straight_high = 5  # 5-high straight
        
        # Sort rank counts
        counts = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
        
        # Determine hand type
        if is_straight and is_flush:
            return (8, [straight_high])  # Straight flush
        elif counts[0][1] == 4:
            return (7, [counts[0][0], counts[1][0]])  # Four of a kind
        elif counts[0][1] == 3 and counts[1][1] == 2:
            return (6, [counts[0][0], counts[1][0]])  # Full house
        elif is_flush:
            flush_cards = [c.rank.numeric_value for c in sorted_cards if suits.count(c.suit) >= 5][:5]
            return (5, flush_cards)  # Flush
        elif is_straight:
            return (4, [straight_high])  # Straight
        elif counts[0][1] == 3:
            kickers = [c[0] for c in counts[1:3]]
            return (3, [counts[0][0]] + kickers)  # Three of a kind
        elif counts[0][1] == 2 and counts[1][1] == 2:
            kicker = counts[2][0]
            return (2, [max(counts[0][0], counts[1][0]), min(counts[0][0], counts[1][0]), kicker])  # Two pair
        elif counts[0][1] == 2:
            kickers = [c[0] for c in counts[1:4]]
            return (1, [counts[0][0]] + kickers)  # One pair
        else:
            return (0, unique_ranks[:5])  # High card

    @staticmethod
    def get_hand_name(hand_rank: int) -> str:
        """Convert hand rank to readable name"""
        hand_names = {
            8: "Straight Flush",
            7: "Four of a Kind", 
            6: "Full House",
            5: "Flush",
            4: "Straight",
            3: "Three of a Kind",
            2: "Two Pair",
            1: "One Pair",
            0: "High Card"
        }
        return hand_names.get(hand_rank, "Unknown")

    @staticmethod
    def get_best_hand(all_cards: List[Card]) -> List[Card]:
        """Get the best 5-card hand from 7 cards"""
        from itertools import combinations
        
        if len(all_cards) <= 5:
            return all_cards
        
        best_hand = []
        best_rank = -1
        best_tiebreakers = []
        
        # Try all combinations of 5 cards
        for combo in combinations(all_cards, 5):
            rank, tiebreakers = HandEvaluator.evaluate_hand(list(combo))
            if rank > best_rank or (rank == best_rank and tiebreakers > best_tiebreakers):
                best_rank = rank
                best_tiebreakers = tiebreakers
                best_hand = list(combo)
        
        return best_hand

class PokerTable:
    def __init__(self, small_blind: int = 10, big_blind: int = 20):
        self.players: List[Player] = []
        self.deck = Deck()
        self.community_cards: List[Card] = []
        self.pot = 0
        self.current_bet = 0
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.dealer_position = 0
        self.current_player = 0
        self.state = GameState.WAITING
        self.side_pots = []
        self.game_active = False
    
    def add_player(self, user_id: int, username: str, chips: int) -> bool:
        if len(self.players) >= 9 or any(p.user_id == user_id for p in self.players):
            return False
        
        player = Player(user_id, username, chips)
        self.players.append(player)
        return True
    
    def remove_player(self, user_id: int) -> bool:
        if self.game_active:
            # Mark as folded if game is active
            for player in self.players:
                if player.user_id == user_id:
                    player.folded = True
                    return True
            return False
        else:
            # Remove from table if no active game
            self.players = [p for p in self.players if p.user_id != user_id]
            return True
    
    def start_game(self):
        if len(self.players) < 2:
            return False
        
        self.game_active = True
        self.deck.reset()
        self.community_cards = []
        self.pot = 0
        self.current_bet = 0
        self.side_pots = []
        
        # Reset player states
        for player in self.players:
            player.cards = []
            player.current_bet = 0
            player.total_bet = 0
            player.folded = False
            player.all_in = False
            player.acted = False
        
        # Deal hole cards
        for _ in range(2):
            for player in self.players:
                if not player.folded:
                    player.cards.append(self.deck.deal())
        
        # Post blinds
        self.post_blinds()
        self.state = GameState.PREFLOP
        self.current_player = (self.dealer_position + 3) % len(self.players)
        
        return True
    
    def post_blinds(self):
        if len(self.players) == 2:
            # Heads up: dealer posts small blind
            sb_pos = self.dealer_position
            bb_pos = (self.dealer_position + 1) % len(self.players)
        else:
            sb_pos = (self.dealer_position + 1) % len(self.players)
            bb_pos = (self.dealer_position + 2) % len(self.players)
        
        # Small blind
        sb_amount = min(self.small_blind, self.players[sb_pos].chips)
        self.players[sb_pos].chips -= sb_amount
        self.players[sb_pos].current_bet = sb_amount
        self.players[sb_pos].total_bet = sb_amount
        self.pot += sb_amount
        
        # Big blind
        bb_amount = min(self.big_blind, self.players[bb_pos].chips)
        self.players[bb_pos].chips -= bb_amount
        self.players[bb_pos].current_bet = bb_amount
        self.players[bb_pos].total_bet = bb_amount
        self.pot += bb_amount
        
        self.current_bet = bb_amount
    
    def get_active_players(self) -> List[Player]:
        return [p for p in self.players if not p.folded and p.chips > 0]
    
    def player_action(self, user_id: int, action: str, amount: int = 0) -> Tuple[bool, str]:
        if not self.game_active or self.state == GameState.ENDED:
            return False, "No active game"
        
        current_player = self.players[self.current_player]
        if current_player.user_id != user_id:
            return False, "Not your turn"
        
        if current_player.folded or current_player.all_in:
            return False, "You cannot act (folded/all-in)"
        
        if action == "fold":
            current_player.folded = True
            current_player.acted = True
        
        elif action == "call":
            call_amount = min(self.current_bet - current_player.current_bet, current_player.chips)
            current_player.chips -= call_amount
            current_player.current_bet += call_amount
            current_player.total_bet += call_amount
            self.pot += call_amount
            current_player.acted = True
            
            if current_player.chips == 0:
                current_player.all_in = True
        
        elif action == "raise":
            # Calculate the minimum raise amount
            min_raise = self.current_bet * 2 - current_player.current_bet
            max_raise = current_player.chips + current_player.current_bet
            
            if amount < min_raise:
                return False, f"Minimum raise is {min_raise} total"
            
            if amount > max_raise:
                amount = max_raise  # Cap at all-in amount
            
            # Calculate how much more the player needs to put in
            additional_amount = amount - current_player.current_bet
            
            if additional_amount > current_player.chips:
                additional_amount = current_player.chips  # All-in
            
            current_player.chips -= additional_amount
            current_player.current_bet += additional_amount
            current_player.total_bet += additional_amount
            self.pot += additional_amount
            self.current_bet = current_player.current_bet
            current_player.acted = True
            
            # Reset other players' acted status only if this is a real raise
            if current_player.current_bet > self.current_bet:
                for p in self.players:
                    if p.user_id != user_id and not p.folded and not p.all_in:
                        p.acted = False
            
            if current_player.chips == 0:
                current_player.all_in = True
        
        elif action == "check":
            if current_player.current_bet < self.current_bet:
                return False, "Cannot check, must call or fold"
            current_player.acted = True
        
        else:
            return False, "Invalid action"
        
        # Check if betting round is complete before advancing
        if self.is_betting_round_complete():
            self.advance_game_state()
        else:
            self.advance_to_next_player()
        
        return True, f"Action successful: {action}"
    
    def advance_to_next_player(self):
        active_players = [p for p in self.players if not p.folded]
        if len(active_players) <= 1:
            self.advance_game_state()
            return
        
        # Count players who can still act
        players_who_can_act = [p for p in active_players if not p.all_in and p.chips > 0]
        
        if len(players_who_can_act) == 0:
            # No one can act, advance game state
            self.advance_game_state()
            return
        
        start_pos = self.current_player
        attempts = 0
        max_attempts = len(self.players)
        
        while attempts < max_attempts:
            self.current_player = (self.current_player + 1) % len(self.players)
            current = self.players[self.current_player]
            attempts += 1
            
            # Player can act if they're not folded, not all-in, and have chips
            if not current.folded and not current.all_in and current.chips > 0:
                break
                
            # If we've checked all players and none can act, advance game state
            if self.current_player == start_pos:
                self.advance_game_state()
                return

    def is_betting_round_complete(self) -> bool:
        active_players = [p for p in self.players if not p.folded]
        
        if len(active_players) <= 1:
            return True
        
        # Count players who can still act (not folded, not all-in, have chips)
        players_who_can_act = [p for p in active_players if not p.all_in and p.chips > 0]
        
        # If no one can act, round is complete
        if len(players_who_can_act) == 0:
            return True
        
        # If only one player can act and they've acted, round is complete
        if len(players_who_can_act) == 1 and players_who_can_act[0].acted:
            return True
        
        # Get the highest bet amount among active players (including all-ins)
        max_bet = max(p.current_bet for p in active_players) if active_players else 0
        
        # Check if all players who can act have acted and matched the highest bet
        for player in players_who_can_act:
            if not player.acted or player.current_bet < max_bet:
                return False
        
        return True
    
    def advance_game_state(self):
        # Check if game should end early (only one non-folded player)
        active_players = [p for p in self.players if not p.folded]
        if len(active_players) <= 1:
            self.state = GameState.SHOWDOWN
            self.determine_winner()
            return
        
        # Reset current bets and acted status
        for player in self.players:
            player.current_bet = 0
            player.acted = False
        
        self.current_bet = 0
        
        # Check if all remaining players are all-in (except possibly one)
        players_with_chips = [p for p in active_players if p.chips > 0]
        all_in_situation = len(players_with_chips) <= 1
        
        if self.state == GameState.PREFLOP:
            # Deal flop
            self.deck.deal()  # Burn card
            for _ in range(3):
                self.community_cards.append(self.deck.deal())
            self.state = GameState.FLOP
        
        elif self.state == GameState.FLOP:
            # Deal turn
            self.deck.deal()  # Burn card
            self.community_cards.append(self.deck.deal())
            self.state = GameState.TURN
        
        elif self.state == GameState.TURN:
            # Deal river
            self.deck.deal()  # Burn card
            self.community_cards.append(self.deck.deal())
            self.state = GameState.RIVER
        
        elif self.state == GameState.RIVER:
            self.state = GameState.SHOWDOWN
            self.determine_winner()
            return
        
        # If all remaining players are all-in, skip betting and continue dealing
        if all_in_situation:
            # Recursively call to deal next card immediately
            self.advance_game_state()
            return
        
        # Set current player to first active player who can act after dealer
        self.current_player = (self.dealer_position + 1) % len(self.players)
        
        # Find the first player who can actually act
        attempts = 0
        while attempts < len(self.players):
            current = self.players[self.current_player]
            attempts += 1
            
            # Player can act if they're not folded, not all-in, and have chips
            if not current.folded and not current.all_in and current.chips > 0:
                break
                
            # If we've checked all players and none can act, advance game state
            if self.current_player == (self.dealer_position + 1) % len(self.players):
                self.advance_game_state()
                return

    def should_end_game_early(self) -> bool:
        """Check if the game should end early (only one non-folded player)"""
        active_players = [p for p in self.players if not p.folded]
        return len(active_players) <= 1

    def determine_winner(self):
        active_players = [p for p in self.players if not p.folded]
        
        if len(active_players) == 1:
            # Only one player left
            winner = active_players[0]
            winner.chips += self.pot
            self.pot = 0
            self.showdown_hands = []  # No showdown needed
        else:
            # Evaluate hands and show them
            player_hands = []
            for player in active_players:
                all_cards = player.cards + self.community_cards
                hand_rank, tiebreakers = HandEvaluator.evaluate_hand(all_cards)
                player_hands.append((player, hand_rank, tiebreakers, all_cards))
            
            # Sort by hand strength
            player_hands.sort(key=lambda x: (x[1], x[2]), reverse=True)
            
            # Store showdown info for display
            self.showdown_hands = player_hands
            
            # Distribute pot (simplified - doesn't handle side pots properly)
            best_hand = player_hands[0]
            winners = [ph for ph in player_hands if ph[1] == best_hand[1] and ph[2] == best_hand[2]]
            
            winnings_per_player = self.pot // len(winners)
            for winner, _, _, _ in winners:
                winner.chips += winnings_per_player
            
            self.pot = 0
        
        self.state = GameState.ENDED
        self.game_active = False
        
        # Move dealer button
        self.dealer_position = (self.dealer_position + 1) % len(self.players)

# Database management
class ChipDatabase:
    def __init__(self, filename="chips.json"):
        self.filename = filename
        self.data = self.load_data()
    
    def load_data(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {"players": {}, "tips": {}}
    
    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_player_chips(self, user_id: int) -> int:
        return self.data["players"].get(str(user_id), 1000)
    
    def set_player_chips(self, user_id: int, chips: int):
        self.data["players"][str(user_id)] = chips
        self.save_data()
    
    def add_tip(self, user_id: int, amount: int):
        user_str = str(user_id)
        if user_str not in self.data["tips"]:
            self.data["tips"][user_str] = 0
        self.data["tips"][user_str] += amount
        self.save_data()
    
    def get_tips(self, user_id: int) -> int:
        return self.data["tips"].get(str(user_id), 0)