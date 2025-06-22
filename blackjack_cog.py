import discord
from discord.ext import commands
import asyncio
import json
import os
from typing import Dict, List, Optional

from blackjack import BlackjackTable, Player, Hand, GameState, Deck, Card, Suit
from token_manager import token_manager

class BlackjackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables: Dict[str, BlackjackTable] = {}

    async def _get_table_from_context(self, ctx) -> Optional[BlackjackTable]:
        for table in self.tables.values():
            if table.game_channel_id == ctx.channel.id:
                return table
        await ctx.send("This is not a game channel.")
        return None

    # --- Game State Display --- #
    async def send_game_state_embed(self, guild: discord.Guild, table: BlackjackTable, hide_dealer_card=True):
        game_channel = guild.get_channel(table.game_channel_id)
        if not game_channel:
            return

        embed = discord.Embed(title=f"Blackjack Table: {table.table_id}", color=0x0099ff)
        embed.add_field(name="Dealer's Hand", value=table.dealer_cards_str(hide_dealer_card), inline=False)

        for player in table.players:
            player_info = ""
            for i, hand in enumerate(player.hands):
                hand_id = f"Hand {i+1}"
                hand_value = hand.hand_value()
                status = " (Bust!) " if hand.is_bust else ""
                player_info += f"> {hand_id}: {hand.cards_str()} ({hand_value}){status}\n"
            embed.add_field(name=f"{player.username}'s Hand(s) - Bet: {player.total_bet()}", value=player_info, inline=True)

        current_player = table.get_current_player()
        if current_player:
            embed.set_footer(text=f"Turn: {current_player.username}")

        view = GameView(self, table)
        if table.message_id:
            try:
                message = await game_channel.fetch_message(table.message_id)
                await message.edit(embed=embed, view=view)
            except discord.NotFound:
                message = await game_channel.send(embed=embed, view=view)
                table.message_id = message.id
        else:
            message = await game_channel.send(embed=embed, view=view)
            table.message_id = message.id

    # --- Game Logic Handlers --- #
    async def handle_action(self, interaction: discord.Interaction, table: BlackjackTable, action: str):
        player = table.get_current_player()
        if not player or player.user_id != interaction.user.id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        hand = player.current_hand
        if hand.is_finished:
            await interaction.response.send_message("This hand is already finished.", ephemeral=True)
            return

        if action == 'hit':
            hand.cards.append(table.deck.deal())
            if hand.hand_value() > 21:
                hand.is_bust = True
                hand.is_finished = True
                await interaction.response.send_message(f"You hit and busted with {hand.hand_value()}!", ephemeral=True)
            else:
                await interaction.response.defer()

        elif action == 'stand':
            hand.is_finished = True
            await interaction.response.defer()

        elif action == 'double':
            if token_manager.get_chips(player.user_id) < hand.bet:
                await interaction.response.send_message("You can't afford to double!", ephemeral=True)
                return
            token_manager.add_chips(player.user_id, -hand.bet)
            hand.bet *= 2
            hand.cards.append(table.deck.deal())
            hand.has_doubled = True
            hand.is_finished = True
            if hand.hand_value() > 21:
                hand.is_bust = True
            await interaction.response.defer()

        elif action == 'split':
            if not hand.can_split() or token_manager.get_chips(player.user_id) < hand.bet:
                await interaction.response.send_message("You cannot split this hand!", ephemeral=True)
                return
            
            add_user_tokens(player.user_id, -hand.bet)
            new_hand = Hand(bet=hand.bet)
            new_hand.cards.append(hand.cards.pop())
            hand.cards.append(table.deck.deal())
            new_hand.cards.append(table.deck.deal())
            player.hands.insert(player.current_hand_index + 1, new_hand)
            await interaction.response.defer()

        if hand.is_finished and player.has_more_hands():
            player.next_hand()
        elif hand.is_finished and player.all_hands_finished():
            table.next_player()

        if table.state == GameState.PLAYING and not table.get_current_player():
            await self.dealer_turn(interaction.guild, table)
        else:
            await self.send_game_state_embed(interaction.guild, table)

    async def dealer_turn(self, guild: discord.Guild, table: BlackjackTable):
        table.state = GameState.FINISHED
        while table.dealer_hand_value() < 17:
            table.dealer_cards.append(table.deck.deal())
            await asyncio.sleep(1)
            await self.send_game_state_embed(guild, table, hide_dealer_card=False)

        await self.resolve_bets(guild, table)

    async def resolve_bets(self, guild: discord.Guild, table: BlackjackTable):
        dealer_value = table.dealer_hand_value()
        dealer_bust = dealer_value > 21
        results = []

        for player in table.players:
            player_result = f"**{player.username}'s Results:**\n"
            for i, hand in enumerate(player.hands):
                hand_id = f"Hand {i+1}"
                if hand.is_bust:
                    winnings = -hand.bet
                    player_result += f"- {hand_id}: Bust! Lost {hand.bet} tokens.\n"
                elif dealer_bust or hand.hand_value() > dealer_value:
                    winnings = int(hand.bet * 1.5 if hand.is_natural_blackjack else hand.bet)
                    token_manager.add_chips(player.user_id, hand.bet + winnings)
                    player_result += f"- {hand_id}: Win! Gained {winnings} tokens.\n"
                elif hand.hand_value() == dealer_value:
                    token_manager.add_chips(player.user_id, hand.bet)
                    player_result += f"- {hand_id}: Push! Bet of {hand.bet} returned.\n"
                else:
                    player_result += f"- {hand_id}: Lose! Lost {hand.bet} tokens.\n"
            results.append(player_result)

        game_channel = guild.get_channel(table.game_channel_id)
        await game_channel.send("\n".join(results))
        await game_channel.send("Round finished! Use `!start_betting` for the next round.")

    async def start_game_logic(self, guild: discord.Guild, table: BlackjackTable):
        table.state = GameState.PLAYING
        table.deck.reset()

        for _ in range(2):
            for player in table.players:
                player.current_hand.cards.append(table.deck.deal())
            table.dealer_cards.append(table.deck.deal())

        for player in table.players:
            if player.current_hand.hand_value() == 21:
                player.current_hand.is_natural_blackjack = True
                player.current_hand.is_finished = True

        table.current_player_index = 0
        await self.send_game_state_embed(guild, table)

    # --- Commands --- #
    @commands.command(name='join_table')
    async def join_table(self, ctx, table_id: str):
        if table_id not in self.tables:
            await ctx.send(f"Table '{table_id}' not found!")
            return
        table = self.tables[table_id]
        if table.state != GameState.WAITING and table.state != GameState.BETTING:
            await ctx.send("You can't join a game that has already started.")
            return
        if table.add_player(ctx.author.id, ctx.author.display_name):
            await ctx.send(f"{ctx.author.display_name} has joined table '{table_id}'.")
            game_channel = self.bot.get_channel(table.game_channel_id)
            if game_channel:
                await game_channel.send(f"{ctx.author.display_name} has joined the table.")
        else:
            await ctx.send("You are already at the table or the table is full.")

    @commands.command(name='bjbet')
    async def bjbet(self, ctx, amount: int):
        table = await self._get_table_from_context(ctx)
        if not table: return

        if table.state != GameState.BETTING:
            await ctx.send("Betting is not open right now.")
            return

        player = next((p for p in table.players if p.user_id == ctx.author.id), None)
        if not player:
            await ctx.send("You are not at this table!")
            return
        if player.has_bet:
            await ctx.send("You have already placed your bet.")
            return
        if token_manager.get_chips(player.user_id) < amount:
            await ctx.send("You don't have enough tokens for that bet.")
            return

        player.current_hand.bet = amount
        player.has_bet = True
        token_manager.add_chips(player.user_id, -amount)
        await ctx.send(f"{ctx.author.display_name} has bet {amount} tokens.")

        if all(p.has_bet for p in table.players):
            await ctx.send("All players have bet! Starting game...")
            await self.start_game_logic(ctx.guild, table)

    @commands.command(name='create_table')
    @commands.has_permissions(administrator=True)
    async def create_table(self, ctx, table_id: str = None):
        if table_id is None:
            table_id = f"table-{len(self.tables) + 1}"
        if table_id in self.tables:
            await ctx.send(f"Table '{table_id}' already exists!")
            return

        try:
            game_channel = await ctx.guild.create_text_channel(f"blackjack-{table_id}")
            table = BlackjackTable(table_id=table_id, guild_id=ctx.guild.id, channel_id=ctx.channel.id, game_channel_id=game_channel.id)
            self.tables[table_id] = table
            await ctx.send(f"Blackjack table '{table_id}' created in {game_channel.mention}")
            await game_channel.send(f"Welcome to Blackjack Table {table_id}! Use `!join_table {table_id}` in the main channel to join.")
        except discord.Forbidden:
            await ctx.send("I don't have permissions to create a text channel.")

    @commands.command(name='start_betting')
    @commands.has_permissions(administrator=True)
    async def start_betting(self, ctx, table_id: str):
        if table_id not in self.tables:
            await ctx.send(f"Table '{table_id}' not found!")
            return
        table = self.tables[table_id]
        table.state = GameState.BETTING
        game_channel = self.bot.get_channel(table.game_channel_id)
        await game_channel.send("Betting is now open! Use `!bjbet <amount>` in this channel.")

    @commands.command(name='start_game')
    @commands.has_permissions(administrator=True)
    async def start_game(self, ctx, table_id: str):
        if table_id not in self.tables:
            await ctx.send(f"Table '{table_id}' not found!")
            return
        table = self.tables[table_id]
        if not all(p.has_bet for p in table.players):
            await ctx.send("Not all players have placed their bets yet.")
            return
        await self.start_game_logic(ctx.guild, table)

    @commands.command(name='close_table')
    @commands.has_permissions(administrator=True)
    async def close_table(self, ctx, table_id: str):
        if table_id not in self.tables:
            await ctx.send(f"Table '{table_id}' not found!")
            return
        table = self.tables[table_id]
        for player in table.players:
            for hand in player.hands:
                if hand.bet > 0:
                    token_manager.add_chips(player.user_id, hand.bet)
        if table.game_channel_id:
            game_channel = self.bot.get_channel(table.game_channel_id)
            if game_channel:
                await game_channel.delete()
        del self.tables[table_id]
        await ctx.send(f"Table {table_id} closed! All bets have been returned.")

class GameView(discord.ui.View):
    def __init__(self, cog: BlackjackCog, table: BlackjackTable):
        super().__init__(timeout=300)
        self.cog = cog
        self.table = table
        self.update_buttons()

    def update_buttons(self):
        player = self.table.get_current_player()
        if not player or not player.current_hand:
            self.disable_all_buttons()
            return

        hand = player.current_hand
        can_afford_double = token_manager.get_chips(player.user_id) >= hand.bet
        can_afford_split = token_manager.get_chips(player.user_id) >= hand.bet

        self.hit_button.disabled = hand.is_finished
        self.stand_button.disabled = hand.is_finished
        self.double_button.disabled = not (len(hand.cards) == 2 and can_afford_double and not hand.is_finished)
        self.split_button.disabled = not (hand.can_split() and can_afford_split and not hand.is_finished)

    def disable_all_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label='Hit', style=discord.ButtonStyle.green, emoji='➕')
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'hit')

    @discord.ui.button(label='Stand', style=discord.ButtonStyle.red, emoji='✋')
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'stand')

    @discord.ui.button(label='Double', style=discord.ButtonStyle.blurple, emoji='💰')
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'double')

    @discord.ui.button(label='Split', style=discord.ButtonStyle.secondary, emoji='✌️')
    async def split_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'split')

async def setup(bot):
    await bot.add_cog(BlackjackCog(bot))
