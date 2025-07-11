import discord
from discord.ext import commands
import asyncio
from typing import Dict, List, Optional
import random
from dataclasses import dataclass, field
from enum import Enum
from token_manager import TokenManager

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables: Dict[str, BlackjackTable] = {}
        self.token_manager = TokenManager()

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables: Dict[str, BlackjackTable] = {}

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
        
        # Check for natural blackjack
        if len(self.cards) == 2 and value == 21:
            self.is_blackjack = True
            self.is_finished = True
        
        return value
    
    def cards_str(self) -> str:
        return ' '.join(str(card) for card in self.cards)
    
    def can_split(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

@dataclass
class Player:
    user: discord.Member
    hands: List[Hand] = field(default_factory=lambda: [Hand()])
    current_hand_index: int = 0
    has_bet: bool = False
    
    @property
    def current_hand(self) -> Hand:
        return self.hands[self.current_hand_index] if self.current_hand_index < len(self.hands) else None
    
    def total_bet(self) -> int:
        return sum(hand.bet for hand in self.hands)
    
    def get_user_tokens(self) -> int:
        return user_tokens.get(str(self.user.id), 0)
    
    def can_afford_bet(self, amount: int) -> bool:
        return self.get_user_tokens() >= amount
    
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
    channel_id: Optional[int] = None
    game_channel_id: Optional[int] = None
    players: List[Player] = field(default_factory=list)
    dealer_cards: List[Card] = field(default_factory=list)
    deck: Deck = field(default_factory=Deck)
    current_player_index: int = 0
    state: GameState = GameState.WAITING
    dealer_embed_message: Optional[discord.Message] = None
    player_embed_messages: Dict[int, discord.Message] = field(default_factory=dict)
    betting_embed_message: Optional[discord.Message] = None
    
    def add_player(self, user: discord.Member) -> bool:
        if len(self.players) >= 6:  # Max 6 players
            return False
        if any(p.user.id == user.id for p in self.players):
            return False
        
        self.players.append(Player(user))
        return True
    
    def remove_player(self, user_id: int) -> bool:
        self.players = [p for p in self.players if p.user.id != user_id]
        return True
    
    def get_current_player(self) -> Optional[Player]:
        if 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        return None
    
    def next_player(self):
        current_player = self.get_current_player()
        if current_player:
            current_player.next_hand()
            if not current_player.has_more_hands():
                self.current_player_index += 1
                if self.current_player_index < len(self.players):
                    self.players[self.current_player_index].current_hand_index = 0
        else:
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

# Global storage
tables: Dict[str, BlackjackTable] = {}

# Token management functions
def get_user_tokens(user_id: int) -> int:
    return user_tokens.get(str(user_id), 0)

def set_user_tokens(user_id: int, amount: int):
    user_tokens[str(user_id)] = max(0, amount)
    save_user_tokens(user_tokens)

def add_user_tokens(user_id: int, amount: int):
    current = get_user_tokens(user_id)
    set_user_tokens(user_id, current + amount)

def remove_user_tokens(user_id: int, amount: int) -> bool:
    current = get_user_tokens(user_id)
    if current >= amount:
        set_user_tokens(user_id, current - amount)
        return True
    return False

# Utility functions
def calculate_winnings(hand: Hand, dealer_value: int, dealer_blackjack: bool) -> float:
    """Calculate winnings multiplier for a hand"""
    player_value = hand.hand_value()
    
    if hand.is_bust:
        return 0  # Lose bet
    elif hand.is_blackjack and not dealer_blackjack:
        return 2.5  # Blackjack pays 3:2
    elif player_value > 21:
        return 0  # Bust
    elif dealer_value > 21:
        return 2  # Dealer bust, player wins
    elif player_value > dealer_value:
        return 2  # Player wins
    elif player_value == dealer_value:
        return 1  # Push, return bet
    else:
        return 0  # Dealer wins

def create_betting_embed(table: BlackjackTable) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎰 Betting Phase - Table {table.table_id}",
        description="Place your bets! Use the buttons below or type `!bet <amount>`",
        color=0xffd700
    )
    
    players_info = []
    for player in table.players:
        tokens = get_user_tokens(player.user.id)
        bet_info = f"💰 {tokens} tokens"
        if player.has_bet:
            bet_info += f" | Bet: {player.total_bet()}"
        players_info.append(f"{player.user.display_name}: {bet_info}")
    
    if players_info:
        embed.add_field(name="Players", value="\n".join(players_info), inline=False)
    
    return embed

def create_dealer_embed(table: BlackjackTable) -> discord.Embed:
    """Create dealer's embed showing their cards"""
    embed = discord.Embed(
        title=" Dealer's Hand ",
        description="",
        color=0x0099ff
    )
    
    # Show dealer's cards (showing only one card during play)
    dealer_cards = table.dealer_cards
    if table.state == GameState.PLAYING and len(dealer_cards) > 0:
        # Show both cards if dealer has natural blackjack
        dealer_value = sum([10 if card.rank in ['J', 'Q', 'K'] else 11 if card.rank == 'A' else int(card.rank) 
                          for card in dealer_cards[:2]])
        if dealer_value != 21:
            dealer_cards = [dealer_cards[0], Card('?', '?')]  # Hide second card
        else:
            dealer_cards = dealer_cards[:2]  # Show both cards if dealer has natural blackjack
        if current_player:
            hand_info = f"Hand {current_player.current_hand_index + 1}"
            if len(current_player.hands) > 1:
                hand_info += f" of {len(current_player.hands)}"
            embed.add_field(
                name="🎯 Current Turn",
                value=f"{current_player.user.mention} - {hand_info}\nValue: {current_player.current_hand.hand_value()} | Bet: {current_player.current_hand.bet}",
                inline=False
            )
        elif table.current_player_index >= len(table.players):
            embed.add_field(name="🎯 Current Turn", value="Dealer's Turn", inline=False)
    
    # Show all players and their hands
    players_info = []
    for player in table.players:
        player_line = f"👤 **{player.user.display_name}**"
        for i, hand in enumerate(player.hands):
            status = ""
            if hand.is_bust:
                status = " (💥 BUST)"
            elif hand.is_blackjack:
                status = " (🃏 BLACKJACK)"
            elif table.state == GameState.FINISHED:
                dealer_value = table.dealer_hand_value()
                dealer_blackjack = len(table.dealer_cards) == 2 and dealer_value == 21
                multiplier = calculate_winnings(hand, dealer_value, dealer_blackjack)
                if multiplier == 0:
                    status = " (❌ LOSE)"
                elif multiplier == 1:
                    status = " (🤝 PUSH)"
                elif multiplier == 2.5:
                    status = " (🃏 BLACKJACK WIN)"
                else:
                    status = " (✅ WIN)"
            
            hand_label = f"Hand {i+1}" if len(player.hands) > 1 else "Hand"
            players_info.append(f"  {hand_label}: {hand.hand_value()}{status} (Bet: {hand.bet})")
        
        if not player.hands:
            players_info.append(f"  No hands")
    
    if players_info:
        embed.add_field(name="👥 Players", value="\n".join(players_info), inline=False)
    
    return embed

def create_player_embed(player: Player, table: BlackjackTable) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎲 {player.user.display_name}'s Hands",
        color=0x0099ff
    )
    embed.set_thumbnail(url=player.user.display_avatar.url)
    
    tokens = get_user_tokens(player.user.id)
    embed.add_field(name="💰 Tokens", value=str(tokens), inline=True)
    embed.add_field(name="🎯 Total Bet", value=str(player.total_bet()), inline=True)
    embed.add_field(name="🃏 Hands", value=str(len(player.hands)), inline=True)
    
    for i, hand in enumerate(player.hands):
        hand_value = hand.hand_value()
        status = ""
        if hand.is_bust:
            status = " - 💥 BUST!"
        elif hand.is_blackjack:
            status = " - 🃏 BLACKJACK!"
        elif hand_value == 21:
            status = " - 🎯 21!"
        
        current_indicator = "🎯 " if i == player.current_hand_index and table.state == GameState.PLAYING else ""
        hand_label = f"Hand {i+1}" if len(player.hands) > 1 else "Hand"
        
        embed.add_field(
            name=f"{current_indicator}{hand_label} (Value: {hand_value}{status}) - Bet: {hand.bet}",
            value=hand.cards_str() or "No cards",
            inline=False
        )
    
    return embed

class BettingView(discord.ui.View):
    def __init__(self, table: BlackjackTable):
        super().__init__(timeout=120)
        self.table = table
    
    @discord.ui.button(label="Bet 10", style=discord.ButtonStyle.primary, custom_id="bet_10")
    async def bet_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, 10)
    
    @discord.ui.button(label="Bet 25", style=discord.ButtonStyle.primary, custom_id="bet_25")
    async def bet_25(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, 25)
    
    @discord.ui.button(label="Bet 50", style=discord.ButtonStyle.primary, custom_id="bet_50")
    async def bet_50(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, 50)
    
    @discord.ui.button(label="Bet 100", style=discord.ButtonStyle.primary, custom_id="bet_100")
    async def bet_100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, 100)
    
    @discord.ui.button(label="All In", style=discord.ButtonStyle.danger, custom_id="bet_all_in")
    async def all_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = next((p for p in self.table.players if p.user.id == interaction.user.id), None)
        if player:
            tokens = get_user_tokens(player.user.id)
            await self.place_bet(interaction, tokens)
        else:
            await interaction.response.send_message("You're not in this game!", ephemeral=True)
    
    async def place_bet(self, interaction: discord.Interaction, amount: int):
        if self.table.state != GameState.BETTING:
            await interaction.response.send_message("Betting phase is over!", ephemeral=True)
            return
        
        player = next((p for p in self.table.players if p.user.id == interaction.user.id), None)
        if not player:
            await interaction.response.send_message("You're not in this game!", ephemeral=True)
            return
        
        if player.has_bet:
            await interaction.response.send_message("You've already placed a bet!", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("Bet must be a positive number!", ephemeral=True)
            return
        
        if not player.can_afford_bet(amount):
            tokens = get_user_tokens(player.user.id)
            await interaction.response.send_message(f"Not enough tokens! You have {tokens}, need {amount}.", ephemeral=True)
            return
        
        # Place the bet
        player.hands[0].bet = amount
        player.has_bet = True
        remove_user_tokens(player.user.id, amount)
        
        # Update betting embed
        betting_embed = create_betting_embed(self.table)
        await self.table.betting_embed_message.edit(embed=betting_embed, view=self)
        
        await interaction.response.send_message(f"Bet placed: {amount} tokens!", ephemeral=True)

class BlackjackView(discord.ui.View):
    def __init__(self, table: BlackjackTable):
        super().__init__(timeout=300)
        self.table = table
    
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="action_hit", emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "hit")
    
    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="action_stand", emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "stand")
    
    @discord.ui.button(label="Double", style=discord.ButtonStyle.success, custom_id="action_double", emoji="📈")
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "double")
    
    @discord.ui.button(label="Split", style=discord.ButtonStyle.primary, custom_id="action_split", emoji="✂️")
    async def split(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "split")
    
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.danger, custom_id="action_leave", emoji="🚪")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "leave")
    
    async def handle_action(self, interaction: discord.Interaction, action: str):
        if self.table.state != GameState.PLAYING:
            await interaction.response.send_message("Game is not in progress!", ephemeral=True)
            return
        
        current_player = self.table.get_current_player()
        if not current_player or current_player.user.id != interaction.user.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return
        
        current_hand = current_player.current_hand
        if not current_hand or current_hand.is_finished:
            await interaction.response.send_message("This hand is already finished!", ephemeral=True)
            return
        
        if action == "hit":
            await self.handle_hit(interaction, current_player, current_hand)
        elif action == "stand":
            await self.handle_stand(interaction, current_player, current_hand)
        elif action == "double":
            await self.handle_double(interaction, current_player, current_hand)
        elif action == "split":
            await self.handle_split(interaction, current_player, current_hand)
        elif action == "leave":
            await self.handle_leave(interaction, current_player)
    
    async def handle_hit(self, interaction: discord.Interaction, player: Player, hand: Hand):
        card = self.table.deck.deal()
        hand.cards.append(card)
        
        # Check for natural blackjack after first hit
        if len(hand.cards) == 2 and hand.hand_value() == 21:
            hand.is_blackjack = True
            hand.is_finished = True
            self.table.next_player()
            await self.update_game_display(interaction)
            await self.check_game_end()
            return
        
        if hand.hand_value() > 21:
            hand.is_bust = True
            hand.is_finished = True
        elif hand.hand_value() == 21:
            hand.is_finished = True
        
        if hand.is_finished:
            self.table.next_player()
            await self.update_game_display(interaction)
            await self.check_game_end()
            return
        
        # Update display without checking game end if not finished
        await self.update_game_display(interaction)
    
    async def handle_stand(self, interaction: discord.Interaction, player: Player, hand: Hand):
        hand.is_finished = True
        self.table.next_player()
        await self.update_game_display(interaction)
        await self.check_game_end()
    
    async def handle_double(self, interaction: discord.Interaction, player: Player, hand: Hand):
        if len(hand.cards) != 2:
            await interaction.response.send_message("You can only double on your first turn!", ephemeral=True)
            return
        
        if hand.has_doubled:
            await interaction.response.send_message("You have already doubled!", ephemeral=True)
            return
        
        if not player.can_afford_bet(hand.bet):
            await interaction.response.send_message("Not enough tokens to double!", ephemeral=True)
            return
        
        # Double the bet
        remove_user_tokens(player.user.id, hand.bet)
        hand.bet *= 2
        hand.has_doubled = True
        
        # Deal one card and finish hand
        card = self.table.deck.deal()
        hand.cards.append(card)
        
        if hand.hand_value() > 21:
            hand.is_bust = True
        
        hand.is_finished = True
        self.table.next_player()
        
        await self.update_game_display(interaction)
        await self.check_game_end()
    
    async def handle_split(self, interaction: discord.Interaction, player: Player, hand: Hand):
        if not hand.can_split():
            await interaction.response.send_message("You can only split matching pairs!", ephemeral=True)
            return
        
        if len(player.hands) >= 4:  # Limit splits
            await interaction.response.send_message("Maximum 4 hands allowed!", ephemeral=True)
            return
        
        if not player.can_afford_bet(hand.bet):
            await interaction.response.send_message("Not enough tokens to split!", ephemeral=True)
            return
        
        # Create new hand with second card
        new_hand = Hand()
        new_hand.cards.append(hand.cards.pop())
        new_hand.bet = hand.bet
        
        # Remove tokens for split bet
        remove_user_tokens(player.user.id, hand.bet)
        
        # Deal new cards to both hands
        hand.cards.append(self.table.deck.deal())
        new_hand.cards.append(self.table.deck.deal())
        
        # Insert new hand after current hand
        player.hands.insert(player.current_hand_index + 1, new_hand)
        
        # Check for blackjacks (only if splitting aces)
        if hand.cards[0].rank == 'A':
            if hand.hand_value() == 21:
                hand.is_blackjack = True
                hand.is_finished = True
            if new_hand.hand_value() == 21:
                new_hand.is_blackjack = True
                new_hand.is_finished = True
        
        await self.update_game_display(interaction)
        
        # If current hand is finished, move to next
        if hand.is_finished:
            self.table.next_player()
            await self.check_game_end()
    
    async def handle_leave(self, interaction: discord.Interaction, player: Player):
        # Return all bets
        for hand in player.hands:
            add_user_tokens(player.user.id, hand.bet)
        
        self.table.remove_player(player.user.id)
        
        # Remove player from game channel
        if self.table.game_channel_id:
            game_channel = bot.get_channel(self.table.game_channel_id)
            if game_channel:
                await game_channel.set_permissions(player.user, read_messages=False)
        
        # Remove player's embed
        if player.user.id in self.table.player_embed_messages:
            try:
                await self.table.player_embed_messages[player.user.id].delete()
                del self.table.player_embed_messages[player.user.id]
            except:
                pass
        
        if len(self.table.players) == 0:
            await self.end_game()
            await interaction.response.send_message("You left the table. Game ended.", ephemeral=True)
        else:
            if self.table.current_player_index >= len(self.table.players):
                self.table.current_player_index = 0
            await self.update_game_display(interaction)
            await interaction.response.send_message("You left the table and got your bets back.", ephemeral=True)
    
    async def update_game_display(self, interaction: discord.Interaction):
        # Update dealer embed
        dealer_embed = create_dealer_embed(self.table)
        try:
            await self.table.dealer_embed_message.edit(embed=dealer_embed, view=self)
        except:
            pass
        
        # Update player embeds
        for player in self.table.players:
            if player.user.id in self.table.player_embed_messages:
                player_embed = create_player_embed(player, self.table)
                try:
                    await self.table.player_embed_messages[player.user.id].edit(embed=player_embed)
                except:
                    pass
        
        # Only defer if the interaction hasn't been responded to yet
        if not interaction.response.is_done():
            try:
                await interaction.response.defer()
            except (discord.errors.NotFound, discord.errors.HTTPException):
                pass
    
    async def check_game_end(self):
        # Check if all players are done with all hands
        all_done = True
        for player in self.table.players:
            if not player.all_hands_finished():
                all_done = False
                break
        
        if all_done or self.table.current_player_index >= len(self.table.players):
            await self.dealer_play()
            await self.end_game()
    
    async def dealer_play(self):
        # Dealer plays
        while self.table.dealer_hand_value() < 17:
            card = self.table.deck.deal()
            self.table.dealer_cards.append(card)
            await asyncio.sleep(1)  # Add some suspense
    
    async def end_game(self):
        self.table.state = GameState.FINISHED
        
        # Calculate and distribute winnings
        dealer_value = self.table.dealer_hand_value()
        dealer_blackjack = len(self.table.dealer_cards) == 2 and dealer_value == 21
        
        winnings_report = []
        
        for player in self.table.players:
            player_winnings = 0
            for i, hand in enumerate(player.hands):
                multiplier = calculate_winnings(hand, dealer_value, dealer_blackjack)
                winnings = int(hand.bet * multiplier)
                player_winnings += winnings
                
                if winnings > 0:
                    add_user_tokens(player.user.id, winnings)
            
            net_change = player_winnings - player.total_bet()
            if net_change > 0:
                winnings_report.append(f"🎉 {player.user.display_name}: +{net_change} tokens")
            elif net_change == 0:
                winnings_report.append(f"🤝 {player.user.display_name}: Break even")
            else:
                winnings_report.append(f"💸 {player.user.display_name}: {net_change} tokens")
        
        # Update all displays
        dealer_embed = create_dealer_embed(self.table)
        try:
            await self.table.dealer_embed_message.edit(embed=dealer_embed, view=None)
        except:
            pass
        
        for player in self.table.players:
            if player.user.id in self.table.player_embed_messages:
                player_embed = create_player_embed(player, self.table)
                try:
                    await self.table.player_embed_messages[player.user.id].edit(embed=player_embed)
                except:
                    pass
        
        # Send winnings report
        if winnings_report and self.table.game_channel_id:
            game_channel = bot.get_channel(self.table.game_channel_id)
            if game_channel:
                embed = discord.Embed(
                    title="🎊 Game Results",
                    description="\n".join(winnings_report),
                    color=0xffd700
                )
                await game_channel.send(embed=embed)

class JoinTableView(discord.ui.View):
    def __init__(self, table_id: str):
        super().__init__(timeout=None)
        self.table_id = table_id
        
        # Add the join button with the table_id
        join_button = discord.ui.Button(
            label="Join Table", 
            style=discord.ButtonStyle.success, 
            custom_id=f"join_{table_id}",
            emoji="🎰"
        )
        join_button.callback = self.join_table
        self.add_item(join_button)
    
    async def join_table(self, interaction: discord.Interaction):
        if self.table_id not in tables:
            await interaction.response.send_message("Table no longer exists!", ephemeral=True)
            return
        
        table = tables[self.table_id]
        
        if table.state not in [GameState.WAITING, GameState.BETTING]:
            await interaction.response.send_message("Game is already in progress!", ephemeral=True)
            return
        
        if not table.add_player(interaction.user):
            await interaction.response.send_message("Could not join table (full or already joined)!", ephemeral=True)
            return
        
        # Give access to game channel
        if table.game_channel_id:
            game_channel = bot.get_channel(table.game_channel_id)
            if game_channel:
                await game_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        
        await interaction.response.send_message(f"Joined table {self.table_id}! Go to the game channel to play.", ephemeral=True)

# Enhanced bot commands
@bot.command(name='create_table')
@commands.has_permissions(administrator=True)
async def create_table(ctx, table_id: str = None):
    """Create a new blackjack table (Admin only)"""
    if not table_id:
        table_id = f"table_{len(tables) + 1}"
    
    if table_id in tables:
        await ctx.send("Table ID already exists!")
        return
    
    # Create game channel
    guild = ctx.guild
    category = discord.utils.get(guild.categories, name="🎰 Blackjack Tables")
    if not category:
        category = await guild.create_category("🎰 Blackjack Tables")
    
    game_channel = await guild.create_text_channel(
        f"blackjack-{table_id}",
        category=category,
        overwrites={
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
    )
    
    # Create table
    table = BlackjackTable(
        table_id=table_id,
        guild_id=ctx.guild.id,
        channel_id=ctx.channel.id,
        game_channel_id=game_channel.id
    )
    tables[table_id] = table
    
    # Create join embed
    embed = discord.Embed(
        title=f"🎰 Blackjack Table: {table_id}",
        description=f"Click the button below to join!\nGame will take place in {game_channel.mention}",
        color=0xffd700
    )
    embed.add_field(name="Players", value="0/6", inline=True)
    embed.add_field(name="Status", value="Waiting for players", inline=True)
    embed.add_field(name="Min Bet", value="1 token", inline=True)
    
    view = JoinTableView(table_id)
    await ctx.send(embed=embed, view=view)

@bot.command(name='start_betting')
@commands.has_permissions(administrator=True)
async def start_betting(ctx, table_id: str = None):
    """Start betting phase (Admin only)"""
    if table_id is None:
        guild_tables = [tid for tid, table in tables.items() if table.guild_id == ctx.guild.id]
        if len(guild_tables) == 0:
            await ctx.send("No tables found! Create a table first with `!create_table`")
            return
        elif len(guild_tables) == 1:
            table_id = guild_tables[0]
        else:
            table_list = ", ".join(guild_tables)
            await ctx.send(f"Multiple tables found: {table_list}\nPlease specify: `!start_betting <table_id>`")
            return
    
    if table_id not in tables:
        await ctx.send(f"Table '{table_id}' not found!")
        return
    
    table = tables[table_id]
    
    if len(table.players) == 0:
        await ctx.send("No players in table!")
        return
    
    if table.state != GameState.WAITING:
        await ctx.send("Table is not waiting for betting!")
        return
    
    # Start betting phase
    table.state = GameState.BETTING
    
    # Move to game channel
    game_channel = bot.get_channel(table.game_channel_id)
    if not game_channel:
        await ctx.send("Game channel not found!")
        return
    
    # Create betting embed
    betting_embed = create_betting_embed(table)
    betting_view = BettingView(table)
    table.betting_embed_message = await game_channel.send(embed=betting_embed, view=betting_view)
    
    await ctx.send(f"Betting phase started in {game_channel.mention}!")
    await game_channel.send("🎰 **Place your bets!** Use the buttons below or type `!bet <amount>`")

@bot.command(name='bet')
async def place_bet_command(ctx, amount: int):
    """Place a bet using command"""
    # Find table for this user
    user_table = None
    for table in tables.values():
        if table.game_channel_id == ctx.channel.id:
            if any(p.user.id == ctx.author.id for p in table.players):
                user_table = table
                break
    
    if not user_table:
        await ctx.send("You're not in a game in this channel!")
        return
    
    if user_table.state != GameState.BETTING:
        await ctx.send("Betting phase is not active!")
        return
    
    player = next((p for p in user_table.players if p.user.id == ctx.author.id), None)
    if not player:
        await ctx.send("You're not in this game!")
        return
    
    if player.has_bet:
        await ctx.send("You've already placed a bet!")
        return
    
    if amount <= 0:
        await ctx.send("Bet must be a positive number!")
        return
    
    if not player.can_afford_bet(amount):
        tokens = get_user_tokens(player.user.id)
        await ctx.send(f"Not enough tokens! You have {tokens}, need {amount}.")
        return
    
    # Place the bet
    player.hands[0].bet = amount
    player.has_bet = True
    remove_user_tokens(player.user.id, amount)
    
    # Update betting embed
    if user_table.betting_embed_message:
        betting_embed = create_betting_embed(user_table)
        betting_view = BettingView(user_table)
        try:
            await user_table.betting_embed_message.edit(embed=betting_embed, view=betting_view)
        except:
            pass
    
    await ctx.send(f"✅ Bet placed: {amount} tokens!")

@bot.command(name='leave')
async def leave_table_command(ctx, table_id: str = None):
    """Leave the current table"""
    if table_id is None:
        guild_tables = [tid for tid, table in tables.items() if table.guild_id == ctx.guild.id]
        if len(guild_tables) == 0:
            await ctx.send("No tables found!")
            return
        elif len(guild_tables) == 1:
            table_id = guild_tables[0]
        else:
            table_list = ", ".join(guild_tables)
            await ctx.send(f"Multiple tables found: {table_list}\nPlease specify: `!leave <table_id>`")
            return
    
    if table_id not in tables:
        await ctx.send(f"Table '{table_id}' not found!")
        return
    
    table = tables[table_id]
    player = next((p for p in table.players if p.user.id == ctx.author.id), None)
    
    if not player:
        await ctx.send("You're not in this table!")
        return
    
    if table.state == GameState.PLAYING:
        await ctx.send("You can't leave during game play!")
        return
    
    # Check if there are other players with bets
    other_players_with_bets = any(p.has_bet for p in table.players if p.user.id != ctx.author.id)
    
    # Remove the player
    table.remove_player(ctx.author.id)
    await ctx.send(f"You've left table {table_id}!")
    
    # If other players have bets, start the game
    if other_players_with_bets:
        await start_game(ctx, table_id)

@bot.command(name='start_game')
@commands.has_permissions(administrator=True)
async def start_game(ctx, table_id: str = None):
    """Start the blackjack game after betting (Admin only)"""
    if table_id is None:
        guild_tables = [tid for tid, table in tables.items() if table.guild_id == ctx.guild.id]
        if len(guild_tables) == 0:
            await ctx.send("No tables found!")
            return
        elif len(guild_tables) == 1:
            table_id = guild_tables[0]
        else:
            table_list = ", ".join(guild_tables)
            await ctx.send(f"Multiple tables found: {table_list}\nPlease specify: `!start_game <table_id>`")
            return
    
    if table_id not in tables:
        await ctx.send(f"Table '{table_id}' not found!")
        return
    
    table = tables[table_id]
    
    # Check if all players have bet
    players_with_bets = [p for p in table.players if p.has_bet]
    if len(players_with_bets) == 0:
        await ctx.send("No players have placed bets!")
        return
    
    if table.state != GameState.BETTING:
        await ctx.send("Game is not in betting phase!")
        return
    
    # Remove players who didn't bet
    table.players = players_with_bets
    
    # Start the game
    table.state = GameState.PLAYING
    table.current_player_index = 0
    
    # Deal initial cards and check for natural blackjacks
    for _ in range(2):
        for player in table.players:
            player.hands[0].cards.append(table.deck.deal())
            # Check for natural blackjack after each card is dealt
            if len(player.hands[0].cards) == 2:
                hand_value = player.hands[0].hand_value()
                if hand_value == 21:
                    player.hands[0].is_natural_blackjack = True
                    player.hands[0].is_blackjack = True
                    player.hands[0].is_finished = True
        table.dealer_cards.append(table.deck.deal())
    
    # Check if dealer has natural blackjack
    dealer_value = sum([10 if card.rank in ['J', 'Q', 'K'] else 11 if card.rank == 'A' else int(card.rank) 
                       for card in table.dealer_cards[:2]])
    if dealer_value == 21:
        # Dealer has natural blackjack, end the game
        table.state = GameState.FINISHED
        await ctx.send("Dealer has natural blackjack! All players lose.")
        await end_game(table)
        return
    
    # Skip players with natural blackjacks
    current_player = table.get_current_player()
    while current_player:
        if not current_player.current_hand.is_natural_blackjack:
            break
        table.next_player()
        current_player = table.get_current_player()
        
        # If we've gone through all players and they all have natural blackjacks
        if table.current_player_index == 0:
            await ctx.send("All players have natural blackjacks! Moving to dealer's turn.")
            break
    
    # If no one has natural blackjack, start the game
    if not current_player:
        table.current_player_index = 0
        current_player = table.get_current_player()
    
    # Move to game channel
    game_channel = bot.get_channel(table.game_channel_id)
    if not game_channel:
        await ctx.send("Game channel not found!")
        return
    
    # Delete betting message
    if table.betting_embed_message:
        try:
            await table.betting_embed_message.delete()
        except:
            pass
    
    # Create dealer embed with buttons
    dealer_embed = create_dealer_embed(table)
    view = BlackjackView(table)
    table.dealer_embed_message = await game_channel.send(embed=dealer_embed, view=view)
    
    # Create player embeds without buttons
    for player in table.players:
        player_embed = create_player_embed(player, table)
        message = await game_channel.send(embed=player_embed)
        table.player_embed_messages[player.user.id] = message
    
    await ctx.send(f"Game started in {game_channel.mention}!")
    await game_channel.send("🃏 **Game started! Good luck everyone!** 🃏")

@bot.command(name='deal_new_hand')
@commands.has_permissions(administrator=True)
async def deal_new_hand(ctx, table_id: str = None):
    """Deal a new hand for existing players (Admin only)"""
    if table_id is None:
        guild_tables = [tid for tid, table in tables.items() if table.guild_id == ctx.guild.id]
        if len(guild_tables) == 0:
            await ctx.send("No tables found!")
            return
        elif len(guild_tables) == 1:
            table_id = guild_tables[0]
        else:
            table_list = ", ".join(guild_tables)
            await ctx.send(f"Multiple tables found: {table_list}\nPlease specify: `!deal_new_hand <table_id>`")
            return
    
    if table_id not in tables:
        await ctx.send(f"Table '{table_id}' not found!")
        return
    
    table = tables[table_id]
    
    if len(table.players) == 0:
        await ctx.send("No players in table!")
        return
    
    # Reset to betting phase
    table.state = GameState.BETTING
    table.current_player_index = 0
    table.dealer_cards = []
    table.deck.reset()  # Fresh deck
    
    # Reset all players
    for player in table.players:
        player.hands = [Hand()]
        player.current_hand_index = 0
        player.has_bet = False
    
    # Move to game channel
    game_channel = bot.get_channel(table.game_channel_id)
    if not game_channel:
        await ctx.send("Game channel not found!")
        return
    
    # Clear old messages
    if table.dealer_embed_message:
        try:
            await table.dealer_embed_message.delete()
        except:
            pass
    
    for message in table.player_embed_messages.values():
        try:
            await message.delete()
        except:
            pass
    table.player_embed_messages.clear()
    
    # Start new betting phase
    betting_embed = create_betting_embed(table)
    betting_view = BettingView(table)
    table.betting_embed_message = await game_channel.send(embed=betting_embed, view=betting_view)
    
    await ctx.send(f"New betting phase started for table {table_id}!")
    await game_channel.send("🎰 **New round! Place your bets!** 🎰")

@bot.command(name='close_table')
@commands.has_permissions(administrator=True)
async def close_table(ctx, table_id: str = None):
    """Close a blackjack table (Admin only)"""
    if table_id is None:
        guild_tables = [tid for tid, table in tables.items() if table.guild_id == ctx.guild.id]
        if len(guild_tables) == 0:
            await ctx.send("No tables found!")
            return
        elif len(guild_tables) == 1:
            table_id = guild_tables[0]
        else:
            table_list = ", ".join(guild_tables)
            await ctx.send(f"Multiple tables found: {table_list}\nPlease specify: `!close_table <table_id>`")
            return
    
    if table_id not in tables:
        await ctx.send(f"Table '{table_id}' not found!")
        return
    
    table = tables[table_id]
    
    # Return any active bets
    for player in table.players:
        for hand in player.hands:
            if hand.bet > 0:
                add_user_tokens(player.user.id, hand.bet)
    
    # Delete game channel
    if table.game_channel_id:
        game_channel = bot.get_channel(table.game_channel_id)
        if game_channel:
            await game_channel.delete()
    
    # Remove table
    del tables[table_id]
    await ctx.send(f"Table {table_id} closed! All bets have been returned.")

@bot.command(name='list_tables')
async def list_tables(ctx):
    """List all active tables"""
    if not tables:
        await ctx.send("No active tables!")
        return
    
    embed = discord.Embed(title="🎰 Active Blackjack Tables", color=0x00ff00)
    for table_id, table in tables.items():
        status_emoji = {"waiting": "⏳", "betting": "💰", "playing": "🃏", "finished": "✅"}
        embed.add_field(
            name=f"Table: {table_id}",
            value=f"Players: {len(table.players)}/6\nStatus: {status_emoji.get(table.state.value, '❓')} {table.state.value.title()}",
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f'{bot.user} has landed at the casino!')
    print(f'Bot is ready to deal some cards and tokens!')
    print(f'Loaded {len(user_tokens)} users with tokens')

async def setup(bot):
    await bot.add_cog(Blackjack(bot))