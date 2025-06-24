import discord
from discord.ext import commands
import asyncio
import random
import json
import os
from typing import Dict, List, Optional

from blackjack import BlackjackTable, Player, Hand, GameState, Deck, Card, Suit
from token_manager import token_manager


class GameView(discord.ui.View):
    def __init__(self, cog: "BlackjackCog", table: BlackjackTable):
        super().__init__(timeout=180)
        self.cog = cog
        self.table = table
        self.update_buttons()

    def update_buttons(self):
        player = self.table.get_current_player()
        if not player or not player.current_hand or player.current_hand.is_finished:
            self.disable_all_buttons()
            return

        hand = player.current_hand
        can_afford_double = token_manager.get_chips(player.user_id) >= hand.bet
        can_afford_split = token_manager.get_chips(player.user_id) >= hand.bet

        self.double_button.disabled = not (len(hand.cards) == 2 and can_afford_double)
        self.split_button.disabled = not (hand.can_split() and can_afford_split)

    def disable_all_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'hit')

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'stand')

    @discord.ui.button(label="Double", style=discord.ButtonStyle.blurple)
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'double')

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary)
    async def split_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_action(interaction, self.table, 'split')


class LobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _find_table_by_interaction(self, cog: "BlackjackCog", interaction: discord.Interaction) -> Optional[BlackjackTable]:
        for table in cog.tables.values():
            if table.lobby_message_id == interaction.message.id:
                return table
        return None

    async def _update_lobby_message(self, cog: "BlackjackCog", interaction: discord.Interaction, table: BlackjackTable):
        lobby_channel = interaction.guild.get_channel(table.lobby_channel_id)
        if not lobby_channel:
            return

        try:
            message = await lobby_channel.fetch_message(table.lobby_message_id)
            embed = cog.create_lobby_embed(table)
            await message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.Forbidden) as e:
            print(f"Failed to update lobby message for table {table.table_id}: {e}")

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="bj_join_persistent")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: BlackjackCog = interaction.client.get_cog("BlackjackCog")
        if not cog:
            return await interaction.response.send_message("The blackjack game is currently unavailable.", ephemeral=True)

        table = self._find_table_by_interaction(cog, interaction)
        if not table:
            return await interaction.response.send_message("This table seems to be closed.", ephemeral=True)

        if table.state not in [GameState.WAITING, GameState.BETTING]:
            return await interaction.response.send_message("You can't join a game that has already started.", ephemeral=True)

        if table.add_player(interaction.user.id, interaction.user.display_name):
            game_channel = interaction.guild.get_channel(table.game_channel_id)
            if game_channel:
                await game_channel.set_permissions(interaction.user, read_messages=True)
                await game_channel.send(f"{interaction.user.display_name} has joined the table.")

            await self._update_lobby_message(cog, interaction, table)
            await interaction.response.send_message(f"You have joined table '{table.table_id}'.", ephemeral=True)
        else:
            await interaction.response.send_message("You are already at the table or the table is full.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="bj_leave_persistent")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: BlackjackCog = interaction.client.get_cog("BlackjackCog")
        if not cog:
            return await interaction.response.send_message("The blackjack game is currently unavailable.", ephemeral=True)

        table = self._find_table_by_interaction(cog, interaction)
        if not table:
            return await interaction.response.send_message("This table seems to be closed.", ephemeral=True)

        if table.state not in [GameState.WAITING, GameState.BETTING]:
            return await interaction.response.send_message("You can't leave a game that has already started.", ephemeral=True)

        if table.remove_player(interaction.user.id):
            game_channel = interaction.guild.get_channel(table.game_channel_id)
            if game_channel:
                await game_channel.set_permissions(interaction.user, overwrite=None)
                await game_channel.send(f"{interaction.user.display_name} has left the table.")

            await self._update_lobby_message(cog, interaction, table)
            await interaction.response.send_message(f"You have left table '{table.table_id}'.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not at this table.", ephemeral=True)


class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Persist tables dict across cog reloads
        if not hasattr(bot, 'blackjack_tables'):
            bot.blackjack_tables = {}
        self.tables: Dict[str, BlackjackTable] = bot.blackjack_tables
        bot.add_view(LobbyView())

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

        # Defer the interaction response immediately, handle messages later
        await interaction.response.defer()

        if action == 'hit':
            hand.cards.append(table.deck.deal())
            if hand.hand_value() > 21:
                hand.is_bust = True
                hand.is_finished = True

        elif action == 'stand':
            hand.is_finished = True

        elif action == 'double':
            if token_manager.get_chips(player.user_id) < hand.bet:
                await interaction.followup.send("You can't afford to double!", ephemeral=True)
                return
            token_manager.add_chips(player.user_id, -hand.bet)
            hand.bet *= 2
            hand.cards.append(table.deck.deal())
            hand.has_doubled = True
            hand.is_finished = True
            if hand.hand_value() > 21:
                hand.is_bust = True

        elif action == 'split':
            if not hand.can_split() or token_manager.get_chips(player.user_id) < hand.bet:
                await interaction.followup.send("You can't afford to split!", ephemeral=True)
                return
            token_manager.add_chips(player.user_id, -hand.bet)
            
            new_hand = Hand(bet=hand.bet)
            new_hand.cards.append(hand.cards.pop())
            player.hands.insert(player.current_hand_index + 1, new_hand)
            
            hand.cards.append(table.deck.deal())
            new_hand.cards.append(table.deck.deal())

        # This is the core logic that was missing
        await self._advance_game(interaction.guild, table)

    async def _advance_game(self, guild: discord.Guild, table: BlackjackTable):
        """Checks the game state and moves to the next player, hand, or dealer's turn."""
        player = table.get_current_player()

        # Always update the view first to show the result of the last action.
        await self.send_game_state_embed(guild, table)

        if not player:
            # All players have played
            await asyncio.sleep(1.5) # Pause to show the final player's hand
            await self.dealer_turn(guild, table)
            return

        # If the current hand is finished, we need to pause and then advance.
        if player.current_hand and player.current_hand.is_finished:
            await asyncio.sleep(1.5) # Pause so the user can see the result (e.g., a bust)
            
            player.next_hand() # Move to the player's next hand

            if not player.has_more_hands(): # If no more hands for this player
                table.next_player()
            
            # After advancing the state, recursively call to continue the game flow.
            await self._advance_game(guild, table)

    async def dealer_turn(self, guild: discord.Guild, table: BlackjackTable):
        """Handles the dealer's turn, revealing their card and drawing until 17 or more."""
        table.state = GameState.FINISHED
        
        # Reveal the hidden card first
        await self.send_game_state_embed(guild, table, hide_dealer_card=False)
        await asyncio.sleep(1.5)

        # Dealer hits on 16 or less
        while table.dealer_hand_value() < 17:
            table.dealer_cards.append(table.deck.deal())
            await self.send_game_state_embed(guild, table, hide_dealer_card=False)
            await asyncio.sleep(1.5)

        # Final state before resolving bets
        await self.send_game_state_embed(guild, table, hide_dealer_card=False)
        await asyncio.sleep(1)
        
        await self.resolve_bets(guild, table)

    async def resolve_bets(self, guild: discord.Guild, table: BlackjackTable):
        dealer_value = table.dealer_hand_value()
        dealer_bust = dealer_value > 21
        results = []
        game_channel = guild.get_channel(table.game_channel_id)

        # Disable buttons on the game embed
        if game_channel and table.message_id:
            try:
                message = await game_channel.fetch_message(table.message_id)
                view = GameView(self, table)
                view.disable_all_buttons()
                await message.edit(view=view)
            except (discord.NotFound, discord.Forbidden) as e:
                print(f"Error updating game message {table.message_id}: {e}")

        for player in table.players:
            player_result = f"**{player.username}'s Results:**\n"
            for i, hand in enumerate(player.hands):
                hand_id = f"Hand {i+1}"
                if hand.is_bust:
                    player_result += f"- {hand_id}: Bust! Lost {hand.bet} tokens.\n"
                elif dealer_bust or hand.hand_value() > dealer_value:
                    winnings = int(hand.bet * 1.5 if hand.is_natural_blackjack else hand.bet)
                    # Return original bet + winnings
                    repayment_message = token_manager.add_chips(player.user_id, hand.bet + winnings)
                    if repayment_message and game_channel:
                        await game_channel.send(repayment_message)
                    player_result += f"- {hand_id}: Win! Gained {winnings} tokens.\n"
                elif hand.hand_value() == dealer_value:
                    # Return original bet
                    repayment_message = token_manager.add_chips(player.user_id, hand.bet)
                    if repayment_message and game_channel:
                        await game_channel.send(repayment_message)
                    player_result += f"- {hand_id}: Push! Bet of {hand.bet} returned.\n"
                else: # Lost
                    player_result += f"- {hand_id}: Lose! Lost {hand.bet} tokens.\n"
            results.append(player_result)

        if game_channel:
            await game_channel.send("\n".join(results))
            await game_channel.send("Round finished! Use `!start_betting` for the next round.")
        
        table.state = GameState.WAITING
        await self.update_lobby_embed(table)

    async def start_game_logic(self, guild: discord.Guild, table: BlackjackTable):
        table.state = GameState.PLAYING
        await self.update_lobby_embed(table)
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
        await self._advance_game(guild, table)

    # --- Commands --- #
    def create_lobby_embed(self, table: BlackjackTable) -> discord.Embed:
        state_info = {
            GameState.WAITING: ("Lobby is open! Players can join or leave.", discord.Color.green()),
            GameState.BETTING: ("Betting is now open!", discord.Color.blue()),
            GameState.PLAYING: ("Game in progress.", discord.Color.red()),
        }
        description, color = state_info.get(table.state, ("Unknown State", discord.Color.default()))

        embed = discord.Embed(
            title=f"Blackjack Table: {table.table_id}",
            description=description,
            color=color
        )

        player_list = "\n".join([f"<@{p.user_id}>" for p in table.players]) or "No players yet."
        embed.add_field(name=f"Players ({len(table.players)}/6)", value=player_list, inline=True)
        embed.add_field(name="Status", value=f"**{table.state.value.upper()}**", inline=True)
        embed.set_footer(text=f"Table ID: {table.table_id}")
        return embed

    async def update_lobby_embed(self, table: BlackjackTable):
        lobby_channel = self.bot.get_channel(table.lobby_channel_id)
        if not lobby_channel or not table.lobby_message_id:
            return

        try:
            message = await lobby_channel.fetch_message(table.lobby_message_id)
            embed = self.create_lobby_embed(table)
            await message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden):
            pass # Ignore if message is gone or we can't edit

    @commands.command(name='start_betting')
    @commands.has_permissions(administrator=True)
    async def start_betting(self, ctx):
        table = await self._get_table_from_context(ctx)
        if not table:
            return

        if len(table.players) == 0:
            await ctx.send("Cannot start the game with no players.")
            return

        table.reset_round()
        await self.update_lobby_embed(table)
        await ctx.send("New round! Betting is now open! Use `!bjbet <amount>` in this channel.")

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

    @commands.command(name='create_table', aliases=['blackjack'])
    @commands.has_permissions(administrator=True)
    async def create_table(self, ctx, table_id: str = None):
        
        await asyncio.sleep(1)
        await ctx.message.delete()

        if table_id is None:
            table_id = f"bj-{random.randint(1000, 9999)}"
        if table_id in self.tables:
            await ctx.send(f"Table '{table_id}' already exists!", delete_after=10)
            return

        guild = ctx.guild
        lobby_channel = ctx.channel
        category_name = "Blackjack Tables"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                category = await guild.create_category(category_name)
            except discord.Forbidden:
                return await ctx.send("I need permissions to create categories.", delete_after=10)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        try:
            game_channel = await guild.create_text_channel(
                f"bj-{table_id}",
                category=category,
                overwrites=overwrites
            )
        except discord.Forbidden:
            return await ctx.send("I need permissions to create private channels.", delete_after=10)

        table = BlackjackTable(
            table_id=table_id,
            guild_id=guild.id,
            channel_id=ctx.channel.id,
            game_channel_id=game_channel.id,
            lobby_channel_id=lobby_channel.id
        )
        self.tables[table_id] = table

        embed = self.create_lobby_embed(table)
        view = LobbyView()
        
        try:
            lobby_message = await lobby_channel.send(embed=embed, view=view)
            table.lobby_message_id = lobby_message.id
        except discord.Forbidden:
            await game_channel.delete()
            del self.tables[table_id]
            return await ctx.send(f"I don't have permission to send messages in {lobby_channel.mention}.", delete_after=10)

        await ctx.message.delete()
        await game_channel.send(f"Welcome to Blackjack Table **{table_id}**! Please wait for the game to start.")

    async def _get_table_from_context(self, ctx):
        """Finds the table associated with the current channel."""
        channel_id = ctx.channel.id
        for table in self.tables.values():
            if table.game_channel_id == channel_id:
                return table
        await ctx.send("This command can only be used in a blackjack game channel.")
        return None



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
                    repayment_message = token_manager.add_chips(player.user_id, hand.bet)
                    if repayment_message:
                        await ctx.send(repayment_message)
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
