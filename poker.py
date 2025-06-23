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
    def __init__(self, original_channel_id: int, private_channel_id: int, small_blind: int = 10, big_blind: int = 20):
        self.original_channel_id = original_channel_id
        self.private_channel_id = private_channel_id
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.players: List[Player] = []
        self.deck = Deck()
        self.community_cards: List[Card] = []
        self.state = GameState.WAITING
        self.dealer_position: int = -1
        self.current_player_index: int = 0
        self.game_active: bool = False
        self.last_raiser: Optional[Player] = None
        self.game_events: List[str] = []
        self.showdown_hands: List = []
        self.pot = 0
        self.current_bet = 0

    def add_player(self, user_id: int, username: str, chips: int) -> bool:
        if self.game_active or len(self.players) >= 9:
            return False
        if any(p.user_id == user_id for p in self.players):
            return False
        self.players.append(Player(user_id=user_id, username=username, chips=chips))
        return True

    def get_player(self, user_id: int) -> Optional[Player]:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def remove_player(self, user_id: int) -> bool:
        player_to_remove = next((p for p in self.players if p.user_id == user_id), None)
        if not player_to_remove:
            return False

        if self.game_active:
            if not player_to_remove.folded:
                player_to_remove.folded = True
                self.game_events.append(f"{player_to_remove.username} left the game and folded.")
                self._check_for_winner_by_folding()
        
        try:
            player_index = self.players.index(player_to_remove)
            self.players.remove(player_to_remove)
            if self.game_active and self.players:
                if self.dealer_position >= player_index:
                    self.dealer_position = (self.dealer_position - 1) % len(self.players)
                if self.current_player_index >= player_index:
                    self.current_player_index = (self.current_player_index - 1) % len(self.players)
        except ValueError:
            return False
        return True

    def start_game(self) -> Tuple[bool, str]:
        # Remove players with no chips from the previous hand
        self.players = [p for p in self.players if p.chips > 0]

        if self.game_active:
            return False, "A game is already in progress."
        if len(self.players) < 2:
            return False, f"Not enough players to start (need at least 2, have {len(self.players)})."

        self.game_active = True
        self.state = GameState.PREFLOP
        self.pot = 0
        self.current_bet = 0
        self.deck.reset()
        self.community_cards = []
        self.showdown_hands = []
        self.last_raiser = None
        self.game_events = ["--- New Hand Starting ---"]

        for player in self.players:
            player.cards = [self.deck.deal(), self.deck.deal()]
            player.folded = False
            player.all_in = False
            player.acted = False
            player.current_bet = 0
            player.total_bet = 0
            player.hand_rank = None
            player.tiebreakers = None

        if self.dealer_position == -1 or self.dealer_position >= len(self.players):
             self.dealer_position = random.randint(0, len(self.players) - 1)
        else:
             self.dealer_position = (self.dealer_position + 1) % len(self.players)

        self._start_betting_round()
        return True, "Game started!"

    def player_action(self, user_id: int, action: str, amount: int = 0) -> Tuple[bool, str]:
        player = self.players[self.current_player_index]
        if player.user_id != user_id:
            return False, "Not your turn."

        action = action.lower()
        player.acted = True

        if action == 'fold':
            player.folded = True
            self.game_events.append(f"{player.username} folds.")
        elif action == 'check':
            if self.current_bet > player.current_bet:
                return False, f"Cannot check. Current bet is {self.current_bet}. You must call or raise."
            self.game_events.append(f"{player.username} checks.")
        elif action == 'call':
            call_amount = self.current_bet - player.current_bet
            if call_amount <= 0:
                return False, "Nothing to call. You can check."
            
            actual_call = min(call_amount, player.chips)
            player.chips -= actual_call
            self.pot += actual_call
            player.current_bet += actual_call
            self.game_events.append(f"{player.username} calls {actual_call}.")
            if player.chips == 0:
                player.all_in = True
                self.game_events.append(f"{player.username} is all-in!")
        elif action in ['bet', 'raise']:
            min_raise_amount = self.current_bet + self.big_blind
            if self.current_bet == 0: # This is a 'bet'
                if amount < self.big_blind:
                    return False, f"The minimum bet is {self.big_blind}."
            else: # This is a 'raise'
                if amount < min_raise_amount:
                    return False, f"Minimum raise is to {min_raise_amount}."

            if amount > player.chips + player.current_bet:
                return False, "You don't have enough chips for that."

            bet_amount = amount - player.current_bet
            player.chips -= bet_amount
            self.pot += bet_amount
            player.current_bet = amount
            self.current_bet = amount
            self.last_raiser = player
            
            if player.chips == 0:
                player.all_in = True
                self.game_events.append(f"{player.username} raises to {amount} and is all-in!")
            else:
                self.game_events.append(f"{player.username} raises to {amount}.")
        else:
            return False, "Invalid action."

        self._advance_turn()
        return True, ""

    def _start_betting_round(self):
        self.current_bet = 0
        self.last_raiser = None
        
        active_players = [p for p in self.players if not p.folded]
        for p in active_players:
            p.current_bet = 0
            p.acted = False

        if self.state == GameState.PREFLOP:
            self._post_blinds()
            num_players = len(self.players)
            if num_players == 2: # Heads-up
                self.current_player_index = self.dealer_position
            else:
                self.current_player_index = (self.dealer_position + 3) % num_players
        else:
            self.current_player_index = self._get_next_active_player_index(self.dealer_position)

    def _post_blinds(self):
        num_players = len(self.players)
        sb_pos = (self.dealer_position + 1) % num_players
        bb_pos = (self.dealer_position + 2) % num_players

        if num_players == 2: # Heads-up
            sb_pos = self.dealer_position
            bb_pos = (self.dealer_position + 1) % num_players

        # Small Blind
        sb_player = self.players[sb_pos]
        sb_amount = min(self.small_blind, sb_player.chips)
        sb_player.chips -= sb_amount
        sb_player.current_bet = sb_amount
        self.pot += sb_amount
        self.game_events.append(f"{sb_player.username} posts small blind of {sb_amount}.")
        if sb_player.chips == 0:
            sb_player.all_in = True

        # Big Blind
        bb_player = self.players[bb_pos]
        bb_amount = min(self.big_blind, bb_player.chips)
        bb_player.chips -= bb_amount
        bb_player.current_bet = bb_amount
        self.pot += bb_amount
        self.game_events.append(f"{bb_player.username} posts big blind of {bb_amount}.")
        if bb_player.chips == 0:
            bb_player.all_in = True

        self.current_bet = self.big_blind
        self.last_raiser = bb_player

    def _get_next_active_player_index(self, start_index: int) -> int:
        next_index = (start_index + 1) % len(self.players)
        while next_index != start_index:
            player = self.players[next_index]
            if not player.folded and not player.all_in:
                return next_index
            next_index = (next_index + 1) % len(self.players)
        return start_index # Should not happen in a valid game state

    def _advance_turn(self):
        if self._is_betting_over():
            self._advance_state()
            return

        self.current_player_index = self._get_next_active_player_index(self.current_player_index)

    def _is_betting_over(self) -> bool:
        active_players = [p for p in self.players if not p.folded]
        if len(active_players) <= 1:
            return True

        players_to_act = [p for p in active_players if not p.all_in]
        if not players_to_act: # All remaining players are all-in
            return True

        # Check if all players who need to act have acted and matched the current bet
        for p in players_to_act:
            if not p.acted:
                return False
            if p.current_bet < self.current_bet:
                return False
        
        # Special case: Big blind can raise if no one else did
        bb_pos = (self.dealer_position + 2) % len(self.players)
        if len(self.players) == 2:
            bb_pos = (self.dealer_position + 1) % len(self.players)
        bb_player = self.players[bb_pos]
        if self.state == GameState.PREFLOP and self.last_raiser == bb_player and self.current_bet == self.big_blind:
             if not bb_player.acted:
                 return False

        return True

    def _advance_state(self):
        # Collect bets into total bets for each player for side pot calculations
        for p in self.players:
            p.total_bet += p.current_bet
        
        active_players = [p for p in self.players if not p.folded]
        if len(active_players) == 1:
            winner = active_players[0]
            self.game_events.append(f"{winner.username} wins {self.pot} as the last remaining player.")
            winner.chips += self.pot
            self._reset_hand()
            return

        # Check if we should deal remaining cards automatically
        non_all_in_players = [p for p in active_players if not p.all_in]
        
        if len(non_all_in_players) < 2:
            # All remaining players are all-in, or only one is not. Deal all cards.
            while self.state != GameState.RIVER:
                if self.state == GameState.PREFLOP:
                    self.state = GameState.FLOP
                    self.community_cards.extend([self.deck.deal() for _ in range(3)])
                elif self.state == GameState.FLOP:
                    self.state = GameState.TURN
                    self.community_cards.append(self.deck.deal())
                elif self.state == GameState.TURN:
                    self.state = GameState.RIVER
                    self.community_cards.append(self.deck.deal())
            self.state = GameState.SHOWDOWN
            self._handle_showdown()
            return

        # Normal state progression
        if self.state == GameState.PREFLOP:
            self.state = GameState.FLOP
            self.community_cards.extend([self.deck.deal() for _ in range(3)])
        elif self.state == GameState.FLOP:
            self.state = GameState.TURN
            self.community_cards.append(self.deck.deal())
        elif self.state == GameState.TURN:
            self.state = GameState.RIVER
            self.community_cards.append(self.deck.deal())
        elif self.state == GameState.RIVER:
            self.state = GameState.SHOWDOWN
            self._handle_showdown()
            return
        
        if self.state != GameState.SHOWDOWN:
            self.game_events.append(f"--- Starting {self.state.value.upper()} ---")
            self.game_events.append(f"Community Cards: {' '.join(map(str, self.community_cards))}")
            self._start_betting_round()

    def _handle_showdown(self):
        # In an all-in situation, the final bets might not have been collected yet.
        # Collect all current bets into the pot and player totals before showdown.
        for p in self.players:
            self.pot += p.current_bet
            p.total_bet += p.current_bet

        self.game_events.append("--- SHOWDOWN ---")
        showdown_players = [p for p in self.players if not p.folded]

        for player in showdown_players:
            hand_rank, tiebreakers = HandEvaluator.evaluate_hand(player.cards + self.community_cards)
            hand_name = HandEvaluator.get_hand_name(hand_rank)
            player.hand_rank = hand_rank
            player.tiebreakers = tiebreakers
            self.game_events.append(f"{player.username} shows {' '.join(map(str, player.cards))} for a {hand_name}")

        self._distribute_pots()

        # Reset current bets for display purposes before ending the hand
        for p in self.players:
            p.current_bet = 0
        
        self.game_active = False
        self.state = GameState.ENDED
        self.game_events.append("--- Hand Over ---")

    def _distribute_pots(self):
        showdown_players = [p for p in self.players if not p.folded]
        
        # Create a list of all players who contributed to the pot for sorting
        pot_contributors = sorted([p for p in self.players if p.total_bet > 0], key=lambda p: p.total_bet)
        
        while sum(p.total_bet for p in pot_contributors) > 0:
            all_in_amount = next((p.total_bet for p in pot_contributors if p.all_in and p.total_bet > 0), float('inf'))
            
            side_pot_level = min(all_in_amount, min(p.total_bet for p in pot_contributors if p.total_bet > 0))
            
            side_pot = 0
            eligible_players = []

            for p in self.players:
                contribution = min(p.total_bet, side_pot_level)
                side_pot += contribution
                p.total_bet -= contribution
                if contribution > 0:
                    eligible_players.append(p)
            
            if not eligible_players:
                break

            # Determine winner(s) for this pot
            best_rank = -1
            best_tiebreakers = []
            winners = []

            for p in eligible_players:
                if p in showdown_players:
                    if p.hand_rank > best_rank:
                        best_rank = p.hand_rank
                        best_tiebreakers = p.tiebreakers
                        winners = [p]
                    elif p.hand_rank == best_rank and p.tiebreakers == best_tiebreakers:
                        winners.append(p)
            
            if not winners and eligible_players:
                 # This can happen if the only eligible player(s) folded earlier
                 # The pot should go to the last remaining player from this eligible group
                 last_active = [p for p in eligible_players if not p.folded]
                 if last_active:
                     winners = last_active

            if winners:
                winnings = side_pot // len(winners)
                for winner in winners:
                    winner.chips += winnings
                    self.game_events.append(f"{winner.username} wins {winnings} from a pot of {side_pot}.")
                # Give remainder to the first winner
                remainder = side_pot % len(winners)
                if remainder > 0:
                    winners[0].chips += remainder

            pot_contributors = [p for p in pot_contributors if p.total_bet > 0]



    def get_game_state(self):
        player_states = []
        for i, p in enumerate(self.players):
            hand_name = HandEvaluator.get_hand_name(p.hand_rank) if p.hand_rank is not None else None
            player_states.append({
                "username": p.username,
                "chips": p.chips,
                "folded": p.folded,
                "all_in": p.all_in,
                "current_bet": p.current_bet,
                "cards": [str(c) for c in p.cards],
                "is_dealer": i == self.dealer_position,
                "is_current_turn": i == self.current_player_index and self.game_active,
                "hand_name": hand_name
            })

        return {
            "game_active": self.game_active,
            "state": self.state.value,
            "pot": self.pot,
            "current_bet": self.current_bet,
            "community_cards": [str(c) for c in self.community_cards],
            "players": player_states,
            "dealer_position": self.dealer_position,
            "events": self.game_events[-10:]
        }
        
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