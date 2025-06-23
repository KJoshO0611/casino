import discord
from discord.ext import commands
from poker import PokerTable, GameState
from token_manager import token_manager
from typing import Optional

class PokerLobbyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _find_table_by_interaction(self, cog: "PokerCog", interaction: discord.Interaction) -> Optional[PokerTable]:
        for table in cog.tables.values():
            if table.lobby_message_id == interaction.message.id:
                return table
        return None

    async def _update_lobby_message(self, cog: "PokerCog", interaction: discord.Interaction, table: PokerTable):
        lobby_channel = interaction.guild.get_channel(table.lobby_channel_id)
        if not lobby_channel:
            return

        try:
            message = await lobby_channel.fetch_message(table.lobby_message_id)
            embed = cog.create_lobby_embed(table)
            await message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden) as e:
            print(f"Failed to update lobby message for table: {e}")

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="poker_join_persistent")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cog: PokerCog = interaction.client.get_cog("PokerCog")
        if not cog:
            await interaction.followup.send("The poker game is currently unavailable.", ephemeral=True)
            return

        table = self._find_table_by_interaction(cog, interaction)
        if not table:
            await interaction.followup.send("This table seems to be closed.", ephemeral=True)
            return

        if table.game_active:
            await interaction.followup.send("You can't join a game that has already started.", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name
        chips = token_manager.get_chips(user_id)

        if chips <= 0:
            await interaction.followup.send("You have no chips to join the game with!", ephemeral=True)
            return

        if table.add_player(user_id, username, chips):
            await self._update_lobby_message(cog, interaction, table)
            await interaction.followup.send(f"You have joined the game with {chips} chips.", ephemeral=True)
        else:
            await interaction.followup.send("You have already joined the game or the table is full.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="poker_leave_persistent")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cog: PokerCog = interaction.client.get_cog("PokerCog")
        if not cog:
            await interaction.followup.send("The poker game is currently unavailable.", ephemeral=True)
            return

        table = self._find_table_by_interaction(cog, interaction)
        if not table:
            await interaction.followup.send("This table seems to be closed.", ephemeral=True)
            return

        player = table.get_player(interaction.user.id)
        if player:
            token_manager.set_chips(player.user_id, player.chips)
            table.remove_player(interaction.user.id)
            await self._update_lobby_message(cog, interaction, table)
            await interaction.followup.send(f"You have left the game. Your final chip count is {player.chips}.", ephemeral=True)
        else:
            await interaction.followup.send("You are not in this game.", ephemeral=True)

class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables = {}  # Maps original_channel_id -> PokerTable instance
        self.lobby_view = PokerLobbyView()

    def cog_load(self):
        self.bot.add_view(self.lobby_view)

    def _get_table_by_lobby(self, channel_id: int) -> Optional[PokerTable]:
        return self.tables.get(channel_id)

    def _get_table_by_game_channel(self, channel_id: int) -> Optional[PokerTable]:
        for table in self.tables.values():
            if table.private_channel_id == channel_id:
                return table
        return None

    def create_lobby_embed(self, table: PokerTable) -> discord.Embed:
        embed = discord.Embed(title="Poker Table", description=f"Game will be played in <#{table.private_channel_id}>", color=discord.Color.blue())
        players = "\n".join([p.username for p in table.players]) if table.players else "No players yet."
        embed.add_field(name="Players", value=players, inline=False)
        embed.set_footer(text=f"Game State: {table.state.value.upper()}")
        return embed

    async def update_lobby_message(self, table: PokerTable):
        lobby_channel = self.bot.get_channel(table.lobby_channel_id)
        if not lobby_channel:
            return

        try:
            message = await lobby_channel.fetch_message(table.lobby_message_id)
            embed = self.create_lobby_embed(table)
            await message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden) as e:
            print(f"Failed to update lobby message for table {table.original_channel_id}: {e}")

    async def send_private_hands(self, table: PokerTable):
        for player in table.players:
            if not player.folded:
                try:
                    user = await self.bot.fetch_user(player.user_id)
                    hand_str = ' '.join(map(str, player.cards))
                    embed = discord.Embed(title="Your Hand", description=hand_str, color=discord.Color.green())
                    await user.send(embed=embed)
                except (discord.Forbidden, discord.NotFound):
                    private_channel = self.bot.get_channel(table.private_channel_id)
                    await private_channel.send(f"Could not send hand to {player.username}. Please check your DMs are open.")

    async def send_game_state(self, table: PokerTable, channel: discord.TextChannel):
        game_state = table.get_game_state()
        embed = discord.Embed(title="Poker Game State", color=discord.Color.blue())
        
        # Add recent game events to the embed description
        if game_state['events']:
            embed.description = "\n".join(game_state['events'])

        community_cards_str = ' '.join(game_state['community_cards']) if game_state['community_cards'] else "Not dealt yet."
        embed.add_field(name="Community Cards", value=community_cards_str, inline=False)
        
        embed.add_field(name="Pot", value=str(game_state['pot']))
        embed.add_field(name="Current Bet", value=str(game_state['current_bet']))

        player_statuses = []
        num_players = len(game_state['players'])
        if num_players > 0:
            dealer_pos = game_state['dealer_position']
            sb_pos = (dealer_pos + 1) % num_players
            bb_pos = (dealer_pos + 2) % num_players
            if num_players == 2:
                sb_pos = dealer_pos
                bb_pos = (dealer_pos + 1) % num_players

            for i, player in enumerate(game_state['players']):
                status = ""
                # At the end of the hand, show cards and hand rank for players who didn't fold
                if game_state['state'] == 'ended' and not player['folded']:
                    cards_str = ' '.join(player['cards'])
                    hand_name_str = f" - {player['hand_name']}" if player['hand_name'] else ""
                    status += f" ({cards_str}{hand_name_str})"

                if player['folded']:
                    status += " (Folded)"
                elif player['all_in']:
                    status += " (All-in)"
                
                if i == dealer_pos:
                    status += " (D)"
                if i == sb_pos:
                    status += " (SB)"
                if i == bb_pos:
                    status += " (BB)"

                player_line = f"{player['username']}: {player['chips']} chips"
                if player['current_bet'] > 0:
                    player_line += f" (Bet: {player['current_bet']})"
                player_line += status
                player_statuses.append(player_line)

        if not player_statuses:
            player_statuses.append("No players at the table.")

        embed.add_field(name="Players", value="\n".join(player_statuses), inline=False)
        
        if game_state['game_active']:
            current_player = next((p for p in game_state['players'] if p['is_current_turn']), None)
            if current_player:
                embed.set_footer(text=f"It's {current_player['username']}'s turn to act.")

        await channel.send(embed=embed)

    @commands.command(name='poker')
    async def create_poker_table(self, ctx):
        if ctx.channel.id in self.tables:
            await ctx.send("A poker table already exists for this channel.")
            return
        category_name = "Poker Tables"
        category = discord.utils.get(ctx.guild.categories, name=category_name)
        if category is None:
            category = await ctx.guild.create_category(category_name)
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        private_channel = await ctx.guild.create_text_channel(
            f"poker-game-{ctx.channel.name}", 
            overwrites=overwrites, 
            category=category
        )
        table = PokerTable(ctx.channel.id, private_channel.id)
        table.lobby_channel_id = ctx.channel.id
        self.tables[ctx.channel.id] = table
        embed = self.create_lobby_embed(table)
        lobby_message = await ctx.send(embed=embed, view=self.lobby_view)
        table.lobby_message_id = lobby_message.id

    @commands.command(name='start')
    async def start_game(self, ctx):
        table = self._get_table_by_lobby(ctx.channel.id)
        if not table:
            await ctx.send("No poker table found for this channel. Use `!poker` to create one.")
            return
        if table.start_game():
            private_channel = self.bot.get_channel(table.private_channel_id)
            await ctx.send(f"Game started! Check the private poker channel: {private_channel.mention} and your DMs for your cards.")
            await self.update_lobby_message(table)
            await self.send_private_hands(table)
            await self.send_game_state(table, private_channel)
        else:
            await ctx.send("Not enough players to start.")

    @commands.command(name='call')
    async def call_action(self, ctx):
        await self.handle_player_action(ctx, "call")

    @commands.command(name='raise')
    async def raise_action(self, ctx, amount: int):
        await self.handle_player_action(ctx, "raise", amount)

    @commands.command(name='fold')
    async def fold_action(self, ctx):
        await self.handle_player_action(ctx, "fold")

    @commands.command(name='check')
    async def check_action(self, ctx):
        await self.handle_player_action(ctx, "check")

    async def handle_player_action(self, ctx, action: str, amount: int = 0):
        table = self._get_table_by_game_channel(ctx.channel.id)
        if not table:
            await ctx.send("This command can only be used in a private poker game channel.", ephemeral=True)
            return

        success, message = table.player_action(ctx.author.id, action, amount)
        private_channel = self.bot.get_channel(table.private_channel_id)
        if success:
            await self.send_game_state(table, private_channel)
            # If the hand is over, save everyone's chips
            if table.state == GameState.ENDED:
                for player in table.players:
                    token_manager.set_chips(player.user_id, player.chips)
                await private_channel.send("All player chip counts have been saved.")
        else:
            await ctx.send(message, ephemeral=True)

async def setup(bot):
    await bot.add_cog(PokerCog(bot))
