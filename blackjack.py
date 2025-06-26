# main.py
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

# Card and Game Classes
class Suit(Enum):
    HEARTS = "♥️"
    DIAMONDS = "♦️"
    CLUBS = "♣️"
    SPADES = "♠️"

class Card:
    def __init__(self, rank: str, suit: Suit):
        self.rank = rank
        self.suit = suit
        self.is_ace = rank == 'A'
    
    def value(self) -> int:
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11
        else:
            return int(self.rank)
    
    def __str__(self):
        return f"{self.rank}{self.suit.value}"

class Deck:
    def __init__(self):
        self.cards = []
        self.reset()
    
    def reset(self):
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        suits = [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]
        self.cards = [Card(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(self.cards)
    
    def deal(self) -> Card:
        if len(self.cards) < 10:  # Reshuffle if running low
            self.reset()
        return self.cards.pop()

class GameState(Enum):
    WAITING = "waiting"
    BETTING = "betting"
    PLAYING = "playing"
    FINISHED = "finished"

@dataclass
class Hand:
    """Represents a single hand (for splits)"""
    cards: List[Card] = field(default_factory=list)
    bet: int = 0
    is_bust: bool = False
    is_blackjack: bool = False
    is_natural_blackjack: bool = False
    has_doubled: bool = False
    is_finished: bool = False
    
    def hand_value(self) -> int:
        value = 0
        ace_count = 0
        
        for card in self.cards:
            if card.rank in ['J', 'Q', 'K']:
                value += 10
            elif card.rank == 'A':
                ace_count += 1
            else:
                value += int(card.rank)
        
        # Add ace values
        for _ in range(ace_count):
            if value + 11 <= 21:
                value += 11
            else:
                value += 1
        
        self.is_blackjack = value == 21
        self.is_natural_blackjack = self.is_blackjack and len(self.cards) == 2

        if self.is_blackjack:
            self.is_finished = True

        return value
    
    def cards_str(self) -> str:
        return ' '.join(str(card) for card in self.cards)
    
    def can_split(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

@dataclass
class Player:
    user_id: int
    username: str
    hands: List[Hand] = field(default_factory=lambda: [Hand()])
    current_hand_index: int = 0
    has_bet: bool = False
    
    @property
    def current_hand(self) -> Hand:
        return self.hands[self.current_hand_index] if self.current_hand_index < len(self.hands) else None
    
    def total_bet(self) -> int:
        return sum(hand.bet for hand in self.hands)

    def reset(self):
        """Resets the player for a new round."""
        self.hands = [Hand()]
        self.current_hand_index = 0
        self.has_bet = False
    
    
    
    def next_hand(self):
        self.current_hand_index += 1
    
    def has_more_hands(self) -> bool:
        return self.current_hand_index < len(self.hands)
    
    def all_hands_finished(self) -> bool:
        return all(hand.is_finished or hand.is_bust or hand.is_blackjack for hand in self.hands)

@dataclass
class BlackjackTable:
    table_id: str
    guild_id: int
    channel_id: int
    game_channel_id: int
    lobby_channel_id: Optional[int] = None
    lobby_message_id: Optional[int] = None
    message_id: Optional[int] = None
    players: List[Player] = field(default_factory=list)
    dealer_cards: List[Card] = field(default_factory=list)
    deck: Deck = field(default_factory=Deck)
    current_player_index: int = 0
    state: GameState = GameState.WAITING
    
    def add_player(self, user_id: int, username: str) -> bool:
        if len(self.players) >= 6:  # Max 6 players
            return False
        if any(p.user_id == user_id for p in self.players):
            return False
        
        self.players.append(Player(user_id, username))
        return True
    
    def remove_player(self, user_id: int) -> bool:
        initial_player_count = len(self.players)
        self.players = [p for p in self.players if p.user_id != user_id]
        return len(self.players) < initial_player_count
    
    def get_current_player(self) -> Optional[Player]:
        if 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        return None

    def reset_round(self):
        """Resets the table for a new round of betting."""
        self.deck.reset()
        self.dealer_cards = []
        self.current_player_index = 0
        self.state = GameState.BETTING
        self.message_id = None
        for player in self.players:
            player.reset()
    
    def next_player(self):
        """Moves to the next player."""
        if self.current_player_index < len(self.players):
            self.current_player_index += 1
    
    def dealer_hand_value(self) -> int:
        value = 0
        ace_count = 0
        
        for card in self.dealer_cards:
            if card.rank in ['J', 'Q', 'K']:
                value += 10
            elif card.rank == 'A':
                ace_count += 1
            else:
                value += int(card.rank)
        
        # Add ace values
        for _ in range(ace_count):
            if value + 11 <= 21:
                value += 11
            else:
                value += 1
        
        return value
    
    def dealer_cards_str(self, hide_hole_card: bool = True) -> str:
        if hide_hole_card and len(self.dealer_cards) > 1 and self.state == GameState.PLAYING:
            return f"{self.dealer_cards[0]} 🂠"
        return ' '.join(str(card) for card in self.dealer_cards)
