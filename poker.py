import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from typing import Dict, List, Optional, Tuple
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
import math
from token_manager import TokenManager

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

class Poker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables: Dict[int, PokerTable] = {}
        self.token_manager = TokenManager()
        
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
    def __init__(self, channel_id: int, private_channel_id: int, small_blind: int = 10, big_blind: int = 20):
        self.channel_id = channel_id
        self.private_channel_id = private_channel_id
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
        self.lobby_message_id = None
    
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
            if not current.folded and not current.all_in and current.chips > 0:
                break
            self.current_player = (self.current_player + 1) % len(self.players)
            attempts += 1
        
        # If no one can act, go to showdown
        if attempts >= len(self.players):
            self.state = GameState.SHOWDOWN
            self.determine_winner()
    
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
            print(f"DEBUG: Showdown hands set: {len(self.showdown_hands)} hands")  # Debug line
            
            # Distribute pot (simplified - doesn't handle side pots properly)
            best_hand = player_hands[0]
            winners = [ph for ph in player_hands if ph[1] == best_hand[1] and ph[2] == best_hand[2]]
            
            winnings_per_player = self.pot // len(winners)
            for winner, _, _, _ in winners:
                winner.chips += winnings_per_player
                user_tokens[str(winner.user_id)] = winner.chips
                save_user_tokens(user_tokens)
            
            self.pot = 0
        
        self.state = GameState.ENDED
        self.game_active = False
        
        # Move dealer button
        self.dealer_position = (self.dealer_position + 1) % len(self.players)

# Discord Bot with Views for buttons
intents.guild_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Button Views
class PokerLobbyView(discord.ui.View):
    def __init__(self, table: PokerTable):
        super().__init__(timeout=None)
        self.table = table
    
    @discord.ui.button(label='Join Table', style=discord.ButtonStyle.green, emoji='🎲')
    async def join_table(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        username = interaction.user.display_name
        
        chips = user_tokens.get(str(user_id), 1000)
        
        if self.table.add_player(user_id, username, chips):
            await interaction.response.send_message(f"🎲 {username} joined the table with {chips} chips!", ephemeral=True)
            await self.update_lobby_message(interaction)
        else:
            await interaction.response.send_message("❌ Could not join table (table full or already joined)", ephemeral=True)

    @discord.ui.button(label='Leave Table', style=discord.ButtonStyle.red, emoji='👋')
    async def leave_table(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        # Save chips before leaving
        for player in self.table.players:
            if player.user_id == user_id:
                chip_db.set_player_chips(user_id, player.chips)
                break
        
        if self.table.remove_player(user_id):
            await interaction.response.defer()
            await self.update_lobby_message(interaction)
        else:
            await interaction.response.defer()
            await self.update_lobby_message(interaction)
    
    @discord.ui.button(label='Start Game', style=discord.ButtonStyle.primary, emoji='🎮')
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.table.start_game():
            # Setup permissions for private channel
            await self.setup_private_channel_permissions(interaction.guild)
            
            await interaction.response.send_message("🎮 Game started! Check the private poker channel.", ephemeral=True)
            await self.send_game_state(interaction.guild)
            await self.send_private_cards(interaction.guild)
        else:
            await interaction.response.send_message("❌ Cannot start game (need at least 2 players)", ephemeral=True)
    
    async def update_lobby_message(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🃏 Poker Table Lobby",
            description=f"Small Blind: {self.table.small_blind} | Big Blind: {self.table.big_blind}",
            color=0x00ff00
        )
        
        if self.table.players:
            players_list = []
            for i, player in enumerate(self.table.players):
                status = "🔘 " if self.table.game_active and i == self.table.dealer_position else ""
                players_list.append(f"{status}{player.username} ({player.chips} chips)")
            embed.add_field(name=f"Players ({len(self.table.players)}/9)", value="\n".join(players_list), inline=False)
        else:
            embed.add_field(name="Players (0/9)", value="No players yet", inline=False)
        
        if self.table.game_active:
            embed.add_field(name="Status", value="🎮 Game in progress", inline=False)
        else:
            embed.add_field(name="Status", value="⏳ Waiting for players", inline=False)
        
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except:
            # If we can't edit the original response, try to edit the message
            if self.table.lobby_message_id:
                channel = interaction.guild.get_channel(self.table.channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(self.table.lobby_message_id)
                        await message.edit(embed=embed, view=self)
                    except:
                        pass
    
    async def send_game_state(self, guild: discord.Guild):
        private_channel = guild.get_channel(self.table.private_channel_id)
        if not private_channel:
            return
        
        embed = discord.Embed(
            title="🎮 Poker Game",
            description=f"**Pot:** {self.table.pot} chips\n**Current Bet:** {self.table.current_bet}",
            color=0x0099ff
        )
        
        # Show community cards
        if self.table.community_cards:
            cards_str = " ".join(str(card) for card in self.table.community_cards)
            embed.add_field(name="Community Cards", value=cards_str, inline=False)
        
        # Show players
        players_info = []
        for i, player in enumerate(self.table.players):
            status = ""
            if i == self.table.dealer_position:
                status += "🔘 "
            if i == self.table.current_player and not player.folded and self.table.state != GameState.ENDED:
                status += "▶️ "
            if player.folded:
                status += "❌ "
            if player.all_in:
                status += "🔥 "
            
            players_info.append(f"{status}{player.username}: {player.chips} chips (bet: {player.current_bet})")
        
        embed.add_field(name="Players", value="\n".join(players_info), inline=False)
        
        if self.table.state == GameState.ENDED:
            # Show showdown hands if they exist
            if hasattr(self.table, 'showdown_hands') and self.table.showdown_hands:
                showdown_text = []
                for player, hand_rank, tiebreakers, all_cards in self.table.showdown_hands:
                    # Get best 5-card hand
                    best_hand = HandEvaluator.get_best_hand(all_cards)
                    hand_name = HandEvaluator.get_hand_name(hand_rank)
                    showdown_text.append(f"**{player.username}:** {' '.join(str(c) for c in player.cards)} → {hand_name}")
                
                embed.add_field(name="🃏 Showdown", value="\n".join(showdown_text), inline=False)
            
            embed.add_field(name="Game Over", value="Game ended! Use the Start Game button to play again.", inline=False)
       
        elif self.table.state != GameState.SHOWDOWN:
            current_player = self.table.players[self.table.current_player]
            embed.add_field(name="Current Turn", value=f"{current_player.username}", inline=False)
            embed.add_field(name="Actions", value="Use the commands: `!call` `!raise <amount>` `!fold` `!check`", inline=False)
        
        await private_channel.send(embed=embed)
    
    async def send_private_cards(self, guild: discord.Guild):
        for player in self.table.players:
            if not player.folded and player.cards:
                user = guild.get_member(player.user_id)
                if user:
                    cards_str = " ".join(str(card) for card in player.cards)
                    embed = discord.Embed(
                        title="🂠 Your Hole Cards",
                        description=f"**{cards_str}**",
                        color=0xff9900
                    )
                    embed.add_field(name="Game Channel", value=f"<#{self.table.private_channel_id}>", inline=False)
                    
                    # Try to send DM first
                    dm_sent = False
                    try:
                        await user.send(embed=embed)
                        dm_sent = True
                    except discord.Forbidden:
                        print(f"Cannot send DM to {user.display_name}, trying alternative method")
                    except Exception as e:
                        print(f"Error sending DM to {user.display_name}: {str(e)}")
                    
                    # If DM failed, send in private channel with delete_after
                    if not dm_sent:
                        private_channel = guild.get_channel(self.table.private_channel_id)
                        if private_channel:
                            try:
                                # Send a message that deletes after 30 seconds
                                await private_channel.send(
                                    f"🂠 **{user.mention}** - Your hole cards: **{cards_str}**\n"
                                    f"*(This message will be deleted in 30 seconds for privacy)*",
                                    delete_after=30
                                )
                            except Exception as e:
                                print(f"Failed to send cards to private channel for {user.display_name}: {str(e)}")
                                # Last resort: send without auto-delete
                                try:
                                    await private_channel.send(
                                        f"🂠 **{user.mention}** - Your hole cards: **{cards_str}**\n"
                                        f"*(Please note this message is visible to all players)*"
                                    )
                                except Exception as e:
                                    print(f"Complete failure to send cards to {user.display_name}: {str(e)}")

    # Also add this method to help with permissions on the private channel
    async def setup_private_channel_permissions(self, guild: discord.Guild):
        """Setup permissions for the private poker channel so all players can see it"""
        private_channel = guild.get_channel(self.table.private_channel_id)
        if not private_channel:
            return
        
        # Add read permissions for all players at the table
        for player in self.table.players:
            user = guild.get_member(player.user_id)
            if user:
                try:
                    await private_channel.set_permissions(
                        user, 
                        read_messages=True, 
                        send_messages=True,
                        read_message_history=True
                    )
                except discord.Forbidden:
                    print(f"Cannot set permissions for {user.display_name}")
                except Exception as e:
                    print(f"Error setting permissions for {user.display_name}: {str(e)}")

# Global state
tables: Dict[int, PokerTable] = {}
chip_db = ChipDatabase()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='poker')
async def create_table(ctx, small_blind: int = 10, big_blind: int = 20):
    """Create a new poker table with private channel"""
    channel_id = ctx.channel.id
    guild = ctx.guild
    
    if channel_id in tables:
        await ctx.send("A poker table already exists in this channel!")
        return
    
    try:
        # Create private poker channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        private_channel = await guild.create_text_channel(
            name=f"poker-{ctx.channel.name}",
            overwrites=overwrites,
            category=ctx.channel.category,
            topic=f"Private poker game from #{ctx.channel.name}"
        )
        
        # Create table
        table = PokerTable(channel_id, private_channel.id, small_blind, big_blind)
        tables[channel_id] = table
        
        # Create lobby embed with buttons
        embed = discord.Embed(
            title="🃏 Poker Table Lobby",
            description=f"Small Blind: {small_blind} | Big Blind: {big_blind}\nPrivate Channel: {private_channel.mention}",
            color=0x00ff00
        )
        embed.add_field(name="Players (0/9)", value="No players yet", inline=False)
        embed.add_field(name="Status", value="⏳ Waiting for players", inline=False)
        
        view = PokerLobbyView(table)
        message = await ctx.send(embed=embed, view=view)
        table.lobby_message_id = message.id
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to create channels!")
    except Exception as e:
        await ctx.send(f"❌ Error creating poker table: {str(e)}")

@bot.command(name='join')
async def join_table_cmd(ctx):
    """Legacy join command - redirects to use buttons"""
    await ctx.send("Please use the **Join Table** button in the lobby message above! 🎲")

@bot.command(name='leave')
async def leave_table_cmd(ctx):
    """Legacy leave command - redirects to use buttons"""
    await ctx.send("Please use the **Leave Table** button in the lobby message above! 👋")

@bot.command(name='start')
async def start_game_cmd(ctx):
    """Legacy start command - redirects to use buttons"""
    await ctx.send("Please use the **Start Game** button in the lobby message above! 🎮")

@bot.command(name='call')
async def call_action(ctx):
    """Call the current bet"""
    await handle_player_action(ctx, "call")

@bot.command(name='raise')
async def raise_action(ctx, amount: int):
    """Raise the bet"""
    await handle_player_action(ctx, "raise", amount)

@bot.command(name='fold')
async def fold_action(ctx):
    """Fold your hand"""
    await handle_player_action(ctx, "fold")

@bot.command(name='check')
async def check_action(ctx):
    """Check (bet nothing)"""
    await handle_player_action(ctx, "check")

async def handle_player_action(ctx, action: str, amount: int = 0):
    channel_id = ctx.channel.id
    user_id = ctx.author.id
    
    # Find the table that has this private channel
    table = None
    for main_channel_id, t in tables.items():
        if t.private_channel_id == channel_id:
            table = t
            break
    
    if not table:
        await ctx.send("❌ This is not a poker game channel!")
        return
    
    success, message = table.player_action(user_id, action, amount)
    
    if success:
        # Get the lobby view to update game state
        main_channel = ctx.guild.get_channel(table.channel_id)
        if main_channel and table.lobby_message_id:
            try:
                lobby_message = await main_channel.fetch_message(table.lobby_message_id)
                view = PokerLobbyView(table)
                await view.send_game_state(ctx.guild)
                
                # Update lobby message
                embed = discord.Embed(
                    title="🃏 Poker Table Lobby",
                    description=f"Small Blind: {table.small_blind} | Big Blind: {table.big_blind}",
                    color=0x00ff00
                )
                
                if table.players:
                    players_list = []
                    for i, player in enumerate(table.players):
                        status = "🔘 " if table.game_active and i == table.dealer_position else ""
                        players_list.append(f"{status}{player.username} ({player.chips} chips)")
                    embed.add_field(name=f"Players ({len(table.players)}/9)", value="\n".join(players_list), inline=False)
                else:
                    embed.add_field(name="Players (0/9)", value="No players yet", inline=False)
                
                embed.add_field(name="Status", value="🎮 Game in progress", inline=False)
                
                await lobby_message.edit(embed=embed, view=view)
            except:
                pass
        
        # Save chips after each action
        for player in table.players:
            chip_db.set_player_chips(player.user_id, player.chips)
    else:
        await ctx.send(f"❌ {message}")

@bot.command(name='status')
async def table_status(ctx):
    """Show current table status"""
    channel_id = ctx.channel.id
    
    # Check if this is a main channel with a table
    if channel_id in tables:
        table = tables[channel_id]
    else:
        # Check if this is a private poker channel
        table = None
        for main_channel_id, t in tables.items():
            if t.private_channel_id == channel_id:
                table = t
                break
        
        if not table:
            await ctx.send("No poker table associated with this channel!")
            return
    
    embed = discord.Embed(
        title="📊 Table Status",
        color=0x9932cc
    )
    
    if table.players:
        players_info = []
        for i, player in enumerate(table.players):
            status = ""
            if table.game_active:
                if i == table.dealer_position:
                    status += "🔘 "
                if i == table.current_player and not player.folded:
                    status += "▶️ "
                if player.folded:
                    status += "❌ "
                if player.all_in:
                    status += "🔥 "
            
            players_info.append(f"{status}{player.username}: {player.chips} chips")
        
        embed.add_field(name="Players", value="\n".join(players_info), inline=False)
    else:
        embed.add_field(name="Players", value="No players at table", inline=False)
    
    if table.game_active:
        embed.add_field(name="Game State", value=table.state.value.title(), inline=True)
        embed.add_field(name="Pot", value=f"{table.pot} chips", inline=True)
        embed.add_field(name="Current Bet", value=f"{table.current_bet} chips", inline=True)
        
        if table.community_cards:
            cards_str = " ".join(str(card) for card in table.community_cards)
            embed.add_field(name="Community Cards", value=cards_str, inline=False)
    else:
        embed.add_field(name="Game State", value="Waiting for players", inline=False)
    
    private_channel = ctx.guild.get_channel(table.private_channel_id)
    if private_channel:
        embed.add_field(name="Private Channel", value=private_channel.mention, inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='chips')
async def check_chips(ctx, user: discord.Member = None):
    """Check chip balance"""
    target_user = user or ctx.author
    chips = chip_db.get_player_chips(target_user.id)
    tips = chip_db.get_tips(target_user.id)
    
    embed = discord.Embed(
        title=f"💰 {target_user.display_name}'s Casino Stats",
        color=0xffd700
    )
    embed.add_field(name="Chips", value=f"{chips:,}", inline=True)
    embed.add_field(name="Tips Given", value=f"{tips:,}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='tip')
async def tip_dealer(ctx, amount: int):
    """Tip the AI dealer"""
    user_id = ctx.author.id
    current_chips = chip_db.get_player_chips(user_id)
    
    if amount <= 0:
        await ctx.send("❌ Tip amount must be positive!")
        return
    
    if amount > current_chips:
        await ctx.send("❌ You don't have enough chips!")
        return
    
    chip_db.set_player_chips(user_id, current_chips - amount)
    chip_db.add_tip(user_id, amount)
    
    await ctx.send(f"🎰 {ctx.author.display_name} tipped the dealer {amount} chips! Thanks for keeping the games fun! 🤖")

@bot.command(name='daily')
async def daily_chips(ctx):
    """Get daily chip bonus"""
    user_id = ctx.author.id
    current_chips = chip_db.get_player_chips(user_id)
    
    if current_chips < 100:  # Only give daily bonus if low on chips
        bonus = 500
        chip_db.set_player_chips(user_id, current_chips + bonus)
        await ctx.send(f"🎁 {ctx.author.display_name} received {bonus} daily bonus chips!")
    else:
        await ctx.send(f"💰 You have {current_chips} chips, no daily bonus needed!")

# Add this to your bot code for better ephemeral message support
@bot.tree.command(name="mycards", description="Show your hole cards (private)")
async def show_my_cards(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    user_id = interaction.user.id
    
    # Find the table that has this private channel
    table = None
    for main_channel_id, t in tables.items():
        if t.private_channel_id == channel_id:
            table = t
            break
    
    if not table:
        await interaction.response.send_message("❌ This is not a poker game channel!", ephemeral=True)
        return
    
    # Find the player
    player = None
    for p in table.players:
        if p.user_id == user_id:
            player = p
            break
    
    if not player:
        await interaction.response.send_message("❌ You're not in this game!", ephemeral=True)
        return
    
    if not player.cards:
        await interaction.response.send_message("❌ You don't have any cards!", ephemeral=True)
        return
    
    cards_str = " ".join(str(card) for card in player.cards)
    embed = discord.Embed(
        title="🂠 Your Hole Cards",
        description=f"**{cards_str}**",
        color=0xff9900
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.command(name='start')
async def start_game(ctx):
    """Start the poker game in the current channel"""
    channel_id = ctx.channel.id
    
    # Find the table that has this channel
    table = tables.get(channel_id)
    if not table:
        await ctx.send("❌ No poker table exists in this channel! Use !poker to create one.")
        return
    
    if not table.game_active:
        if len(table.players) < 2:
            await ctx.send("❌ Need at least 2 players to start the game!")
            return
        
        # Start the game
        if table.start_game():
            await ctx.send("🎮 Game started! Check the private poker channel.")
            await ctx.guild.get_channel(table.private_channel_id).send("🎮 Game started!")
            await PokerLobbyView(table).send_game_state(ctx.guild)
            await PokerLobbyView(table).send_private_cards(ctx.guild)
        else:
            await ctx.send("❌ Could not start game")
    else:
        await ctx.send("❌ Game is already in progress!")

async def setup(bot):
    await bot.add_cog(Poker(bot))