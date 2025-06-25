import discord
import uuid
from discord.ext import commands
import importlib
import poker
importlib.reload(poker)
from poker import PokerTable, GameState, HandEvaluator
from token_manager import token_manager
from typing import Optional, Dict

class PokerLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _find_table_by_interaction(self, cog: "PokerCog", interaction: discord.Interaction) -> Optional[PokerTable]:
        if not interaction.message.embeds:
            return None
        embed = interaction.message.embeds[0]
        if not embed.footer or "Table ID:" not in embed.footer.text:
            return None
        
        try:
            footer_parts = embed.footer.text.split('|')
            table_id_part = footer_parts[0].strip()
            table_id = table_id_part.replace("Table ID:", "").strip()
            return cog.tables.get(table_id)
        except (IndexError, ValueError):
            return None

    async def _update_lobby_message(self, cog: "PokerCog", interaction: discord.Interaction, table: PokerTable):
        lobby_channel = interaction.guild.get_channel(table.lobby_channel_id)
        if lobby_channel:
            try:
                message = await lobby_channel.fetch_message(table.lobby_message_id)
                embed = cog.create_lobby_embed(table)
                await message.edit(embed=embed)
            except (discord.NotFound, discord.Forbidden):
                pass

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="poker_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PokerCog")
        if not cog:
            await interaction.response.send_message("Poker cog not loaded.", ephemeral=True)
            return

        table = self._find_table_by_interaction(cog, interaction)
        if not table:
            await interaction.response.send_message("This poker table is no longer available.", ephemeral=True)
            return

        if table.state != GameState.WAITING:
            await interaction.response.send_message("You can't join a game that has already started.", ephemeral=True)
            return

        chips = token_manager.get_chips(interaction.user.id)
        if chips < table.big_blind * 50: # Example: require 50 big blinds to join
            await interaction.response.send_message("You don't have enough chips to join this table.", ephemeral=True)
            return

        if table.add_player(interaction.user.id, interaction.user.name, chips):
            private_channel = interaction.guild.get_channel(table.private_channel_id)
            if private_channel:
                await private_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"{interaction.user.name} has joined table `{table.table_id}`.", ephemeral=False)
            await self._update_lobby_message(cog, interaction, table)
        else:
            await interaction.response.send_message("You are already at the table or the table is full.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="poker_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PokerCog")
        if not cog:
            await interaction.response.send_message("Poker cog not loaded.", ephemeral=True)
            return

        table = self._find_table_by_interaction(cog, interaction)
        if not table:
            await interaction.response.send_message("This poker table is no longer available.", ephemeral=True)
            return

        if table.state != GameState.WAITING:
            await interaction.response.send_message("You can't leave a game that has already started.", ephemeral=True)
            return

        if table.remove_player(interaction.user.id):
            private_channel = interaction.guild.get_channel(table.private_channel_id)
            if private_channel:
                await private_channel.set_permissions(interaction.user, overwrite=None)
            await interaction.response.send_message(f"{interaction.user.name} has left table `{table.table_id}`.", ephemeral=False)
            await self._update_lobby_message(cog, interaction, table)
        else:
            await interaction.response.send_message("You are not at this table.", ephemeral=True)

class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables: Dict[str, PokerTable] = {}
        self.lobby_view = PokerLobbyView()

    def cog_load(self):
        self.bot.add_view(self.lobby_view)

    def _get_table_by_id(self, table_id: str) -> Optional[PokerTable]:
        return self.tables.get(table_id)

    def _get_table_by_game_channel(self, channel_id: int) -> Optional[PokerTable]:
        for table in self.tables.values():
            if table.private_channel_id == channel_id:
                return table
        return None

    def create_lobby_embed(self, table: PokerTable) -> discord.Embed:
        embed = discord.Embed(title="Poker Table", description=f"A new poker table is open for players!", color=discord.Color.blue())
        embed.add_field(name="Game Channel", value=f"<#{table.private_channel_id}>", inline=False)
        player_list = "\n".join([p.username for p in table.players]) if table.players else "No players yet."
        embed.add_field(name=f"Players ({len(table.players)}/{table.max_players})", value=player_list, inline=False)
        embed.set_footer(text=f"Table ID: {table.table_id} | Game State: {table.state.value.upper()}")
        return embed

    async def update_lobby_message(self, table: PokerTable):
        lobby_channel = self.bot.get_channel(table.lobby_channel_id)
        if lobby_channel:
            try:
                message = await lobby_channel.fetch_message(table.lobby_message_id)
                embed = self.create_lobby_embed(table)
                await message.edit(embed=embed)
            except (discord.NotFound, discord.Forbidden):
                pass

    async def send_private_hands(self, table: PokerTable):
        for player in table.players:
            user = self.bot.get_user(player.user_id)
            if user:
                hand_str = ", ".join(map(str, player.cards))
                await user.send(f"Your hand for Table `{table.table_id}`: {hand_str}")

    async def send_game_state(self, table: PokerTable, channel: discord.TextChannel):
        game_state = table.get_game_state()
        embed = discord.Embed(title=f"Poker Game State - Table {table.table_id}", color=discord.Color.dark_green())
        
        community_cards = " ".join(map(str, game_state['community_cards'])) or "Not dealt yet."
        embed.add_field(name="Community Cards", value=community_cards, inline=False)
        embed.add_field(name="Pot", value=str(game_state['pot']), inline=True)
        embed.add_field(name="Current Bet", value=str(game_state['current_bet']), inline=True)
        
        player_statuses = []
        for p_state in game_state['players']:
            status_icon = "\n- "
            if p_state['is_dealer']: status_icon = "(D) "
            if p_state['is_sb']: status_icon = "(SB) "
            if p_state['is_bb']: status_icon = "(BB) "

            player_info = f"{status_icon}{p_state['username']}: {p_state['chips']} chips"
            if p_state['folded']:
                player_info += " (Folded)"
            if p_state['is_all_in']:
                player_info += " (All-in)"
            if p_state['current_bet'] > 0:
                player_info += f" - Bet: {p_state['current_bet']}"
            player_statuses.append(player_info)

        if not player_statuses:
            player_statuses.append("No players at the table.")

        embed.add_field(name=f"Players ({len(game_state['players'])}/{table.max_players})", value="\n".join(player_statuses), inline=False)
        
        if game_state['game_active']:
            current_player = next((p for p in game_state['players'] if p['is_current_turn']), None)
            if current_player:
                embed.set_footer(text=f"Current turn: {current_player['username']}")
        else:
            embed.set_footer(text="Game is not active.")

        await channel.send(embed=embed)

    @commands.command(name='poker')
    async def create_poker_table(self, ctx):
        table_id = str(uuid.uuid4())[:6]
        category_name = "Poker Tables"
        category = discord.utils.get(ctx.guild.categories, name=category_name)
        if category is None:
            category = await ctx.guild.create_category(category_name)
        
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        private_channel = await ctx.guild.create_text_channel(
            f"poker-table-{table_id}", 
            overwrites=overwrites, 
            category=category
        )
        
        table = PokerTable(table_id, ctx.channel.id, private_channel.id)
        self.tables[table.table_id] = table
        
        embed = self.create_lobby_embed(table)
        lobby_message = await ctx.send(embed=embed, view=self.lobby_view)
        table.lobby_message_id = lobby_message.id

    @commands.command(name='start')
    async def start_game(self, ctx, table_id: Optional[str] = None):
        table = None
        if table_id:
            table = self._get_table_by_id(table_id)
        else:
            table = self._get_table_by_game_channel(ctx.channel.id)

        if not table:
            if not table_id:
                await ctx.send("You are in the lobby. Please provide a Table ID to start a game, e.g., `!start <table_id>`.")
            else:
                await ctx.send(f"No poker table found with ID `{table_id}`.")
            return
        
        success, message = table.start_game()
        if success:
            private_channel = self.bot.get_channel(table.private_channel_id)
            await ctx.send(f"Game at Table `{table.table_id}` started! Check {private_channel.mention} and your DMs for your cards.")
            
            await self.update_lobby_message(table)
            await self.send_private_hands(table)
            await self.send_game_state(table, private_channel)
        else:
            await ctx.send(f"Could not start game at Table `{table.table_id}`: {message}")

    @commands.command(name='close')
    @commands.has_permissions(manage_channels=True)
    async def close_table(self, ctx, table_id: Optional[str] = None):
        """Closes a specific poker table and deletes its private channel."""
        table = None
        if table_id:
            table = self._get_table_by_id(table_id)
        else:
            table = self._get_table_by_game_channel(ctx.channel.id)

        if not table:
            if not table_id:
                await ctx.send("Please provide a Table ID to close, e.g., `!close <table_id>`.")
            else:
                await ctx.send(f"No poker table found with ID `{table_id}`.")
            return

        # Delete the private channel
        private_channel = self.bot.get_channel(table.private_channel_id)
        if private_channel:
            try:
                await private_channel.delete(reason=f"Poker table {table.table_id} closed by {ctx.author}.")
            except (discord.Forbidden, discord.HTTPException) as e:
                await ctx.send(f"Failed to delete channel: {e}")

        # Delete the lobby message
        lobby_channel = self.bot.get_channel(table.lobby_channel_id)
        if lobby_channel:
            try:
                lobby_message = await lobby_channel.fetch_message(table.lobby_message_id)
                await lobby_message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        # Remove the table from tracking
        if table.table_id in self.tables:
            del self.tables[table.table_id]

        await ctx.send(f"Poker table `{table.table_id}` has been closed.")

    @commands.command(name='call')
    async def call_action(self, ctx):
        await self._process_player_action(ctx, 'call')

    @commands.command(name='raise')
    async def raise_action(self, ctx, amount: int):
        await self._process_player_action(ctx, 'raise', amount=amount)

    @commands.command(name='fold')
    async def fold_action(self, ctx):
        await self._process_player_action(ctx, 'fold')

    @commands.command(name='check')
    async def check_action(self, ctx):
        await self._process_player_action(ctx, 'check')

    @commands.command(name='allin')
    async def allin_action(self, ctx):
        await self._process_player_action(ctx, 'allin')

    async def _process_player_action(self, ctx, action_name: str, amount: int = 0):
        table = self._get_table_by_game_channel(ctx.channel.id)
        if not table or not table.game_active:
            await ctx.send("There is no active game in this channel.")
            return

        if action_name == 'allin':
            player = table.get_player(ctx.author.id)
            if not player:
                await ctx.send("You are not a player at this table.")
                return
            amount = player.chips + player.current_bet
            action_name = 'raise' if table.current_bet > 0 else 'bet'

        if action_name in ['raise', 'bet']:
            success, message = table.player_action(ctx.author.id, action_name, amount)
        else:
            success, message = table.player_action(ctx.author.id, action_name)

        if not success:
            await ctx.send(f"{ctx.author.mention}, {message}")
            return

        # On success, check if the round ends, then send one state update.
        round_ended, showdown = await self.check_round_end(table)

        private_channel = self.bot.get_channel(table.private_channel_id)
        if private_channel:
            # Showdown has its own message handler, so we don't send the generic state
            if not showdown and table.game_active:
                await self.send_game_state(table, private_channel)


    async def check_round_end(self, table: PokerTable) -> tuple[bool, bool]:
        """
        Checks if the betting round is over. If so, advances the game state.
        Returns a tuple of (round_ended, is_showdown).
        """
        if table.state in [GameState.PREFLOP, GameState.FLOP, GameState.TURN, GameState.RIVER]:
            if table._is_betting_over():
                table._advance_state()
                if table.state == GameState.SHOWDOWN:
                    private_channel = self.bot.get_channel(table.private_channel_id)
                    if private_channel:
                        await self.handle_showdown(table, private_channel)
                    return True, True
                return True, False
        return False, False

    async def handle_showdown(self, table: PokerTable, channel: discord.TextChannel):
        embed = discord.Embed(title="Showdown Results", color=discord.Color.gold())

        # Display hands from showdown_hands
        if table.showdown_hands:
            showdown_text = []
            for player, hand_rank, tiebreakers, all_cards in table.showdown_hands:
                if not player.folded:
                    hand_name = HandEvaluator.get_hand_name(hand_rank)
                    best_hand_cards = HandEvaluator.get_best_hand(all_cards)
                    hand_str = ' '.join(map(str, best_hand_cards))
                    showdown_text.append(f"{player.username}: {hand_name} (`{hand_str}`)")
            if showdown_text:
                embed.add_field(name="Hands", value="\n".join(showdown_text), inline=False)

        # Display game events for pot distribution
        if table.game_events:
            embed.add_field(name="Winnings", value="\n".join(table.game_events), inline=False)

        await channel.send(embed=embed)

        # Transfer rake to the casino pool
        if table.house_rake > 0:
            token_manager.add_chips(token_manager.CASINO_POOL_ID, table.house_rake)
            await channel.send(f"The house collected a rake of {table.house_rake} chips.")

        # The game state is now ENDED. A new game can be started.
        # Update the lobby to reflect the table is available again or concluded.
        await self.update_lobby_message(table)

async def setup(bot):
    await bot.add_cog(PokerCog(bot))
