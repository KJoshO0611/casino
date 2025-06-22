import discord
from discord.ext import commands
from poker import PokerTable
from token_manager import token_manager
from typing import Optional

class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tables = {} # Maps original_channel_id -> PokerTable instance

    def _get_table(self, channel_id: int) -> Optional[PokerTable]:
        """Finds a poker table from a channel ID, which can be the original or private game channel."""
        table = self.tables.get(channel_id)
        if table:
            return table

        for t in self.tables.values():
            if t.private_channel_id == channel_id:
                return t
        
        return None

    @commands.command(name='poker')
    async def create_poker_table(self, ctx):
        """Creates a new poker table in the current channel."""
        for table in self.tables.values():
            if table.private_channel_id == ctx.channel.id:
                await ctx.send("You cannot create a poker table inside an existing game channel.")
                return

        if ctx.channel.id in self.tables:
            await ctx.send("A poker table already exists for this channel.")
            return

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        private_channel = await ctx.guild.create_text_channel(f"poker-game-{ctx.channel.name}", overwrites=overwrites)

        self.tables[ctx.channel.id] = PokerTable(ctx.channel.id, private_channel.id)
        await ctx.send(f"Poker table created! Game will be played in {private_channel.mention}")

    @commands.command(name='join')
    async def join_game(self, ctx):
        """Join the poker game. Can be used in the original or private game channel."""
        table = self._get_table(ctx.channel.id)
        if not table:
            await ctx.send("No poker table found for this channel. Use `!poker` to create one.")
            return

        user_id = ctx.author.id
        username = ctx.author.display_name
        chips = token_manager.get_chips(user_id)

        if table.add_player(user_id, username, chips):
            await ctx.send(f"{username} has joined the game with {chips} chips.")
        else:
            await ctx.send("You have already joined the game.")

    @commands.command(name='leave')
    async def leave_game(self, ctx):
        """Leave the poker game. Can be used in the original or private game channel."""
        table = self._get_table(ctx.channel.id)
        if not table:
            await ctx.send("No poker table found for this channel.")
            return

        user_id = ctx.author.id
        if table.remove_player(user_id):
            await ctx.send(f"{ctx.author.display_name} has left the game.")
        else:
            await ctx.send("You are not in the game.")

    @commands.command(name='start')
    async def start_game(self, ctx):
        """Start the poker game. Can be used in the original or private game channel."""
        table = self._get_table(ctx.channel.id)
        if not table:
            await ctx.send("No poker table found for this channel. Use `!poker` to create one.")
            return

        if table.start_game():
            private_channel = self.bot.get_channel(table.private_channel_id)
            await ctx.send(f"Game started! Check the private poker channel: {private_channel.mention}")
        else:
            await ctx.send("Not enough players to start.")

    @commands.command(name='call')
    async def call_action(self, ctx):
        """Call the current bet."""
        await self.handle_player_action(ctx, "call")

    @commands.command(name='raise')
    async def raise_action(self, ctx, amount: int):
        """Raise the bet."""
        await self.handle_player_action(ctx, "raise", amount)

    @commands.command(name='fold')
    async def fold_action(self, ctx):
        """Fold your hand."""
        await self.handle_player_action(ctx, "fold")

    @commands.command(name='check')
    async def check_action(self, ctx):
        """Check (bet nothing)."""
        await self.handle_player_action(ctx, "check")

    async def handle_player_action(self, ctx, action: str, amount: int = 0):
        table = self._get_table(ctx.channel.id)
        if not table:
            await ctx.send("This is not a valid poker game channel.")
            return
        
        if ctx.channel.id != table.private_channel_id:
            private_channel = self.bot.get_channel(table.private_channel_id)
            await ctx.send(f"Game actions must be performed in the private channel: {private_channel.mention}")
            return

        success, message = table.player_action(ctx.author.id, action, amount)
        if success:
            await ctx.send(f"{ctx.author.display_name} chose to {action}.")
        else:
            await ctx.send(message)

async def setup(bot):
    await bot.add_cog(PokerCog(bot))
