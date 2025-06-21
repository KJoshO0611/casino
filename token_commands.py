import discord
from discord.ext import commands
from token_manager import TokenManager
from typing import Optional

class TokenCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token_manager = TokenManager()

    @commands.command(name='addtokens')
    @commands.has_permissions(manage_guild=True)
    async def add_tokens(self, ctx, amount: int, user: Optional[discord.Member] = None):
        """Add tokens to a player's balance. If no user is specified, adds to the command author."""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        self.token_manager.add_tokens(user_id, amount)
        
        await ctx.send(f"💰 Added {amount} tokens to {user.display_name}'s balance!\nNew balance: {self.token_manager.get_tokens(user_id)} tokens")

    @commands.command(name='removetokens')
    @commands.has_permissions(manage_guild=True)
    async def remove_tokens(self, ctx, amount: int, user: Optional[discord.Member] = None):
        """Remove tokens from a player's balance. If no user is specified, removes from the command author."""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        success = self.token_manager.remove_tokens(user_id, amount)
        
        if success:
            await ctx.send(f"💰 Removed {amount} tokens from {user.display_name}'s balance!\nNew balance: {self.token_manager.get_tokens(user_id)} tokens")
        else:
            await ctx.send(f"❌ {user.display_name} doesn't have enough tokens!")

    @commands.command(name='settokens')
    @commands.has_permissions(manage_guild=True)
    async def set_tokens(self, ctx, amount: int, user: Optional[discord.Member] = None):
        """Set a player's token balance. If no user is specified, sets the command author's balance."""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        self.token_manager.set_tokens(user_id, amount)
        
        await ctx.send(f"💰 Set {user.display_name}'s balance to {amount} tokens")

    @commands.command(name='checktokens')
    async def check_tokens(self, ctx, user: Optional[discord.Member] = None):
        """Check token balance"""
        if user is None:
            user = ctx.author
        
        user_id = str(user.id)
        balance = self.token_manager.get_tokens(user_id)
        await ctx.send(f"💰 {user.display_name} has {balance} tokens")

    @commands.command(name='tokensleaderboard')
    async def tokens_leaderboard(self, ctx, limit: int = 10):
        """Show token leaderboard"""
        if limit > 50:
            limit = 50
        
        leaderboard = self.token_manager.get_leaderboard(limit)
        embed = discord.Embed(
            title="💰 Token Leaderboard",
            color=discord.Color.gold()
        )
        
        for i, (user_id, tokens) in enumerate(leaderboard, 1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                embed.add_field(
                    name=f"#{i} {user.name}",
                    value=f"{tokens} tokens",
                    inline=False
                )
            except discord.NotFound:
                continue
        
        await ctx.send(embed=embed)

    @commands.command(name='dailytokens')
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily_tokens(self, ctx):
        """Claim daily token bonus"""
        user_id = str(ctx.author.id)
        amount = 1000  # Daily bonus amount
        self.token_manager.add_tokens(user_id, amount)
        
        await ctx.send(f"💰 Claimed daily bonus! Added {amount} tokens to your balance!\nNew balance: {self.token_manager.get_tokens(user_id)} tokens")

async def setup(bot):
    await bot.add_cog(TokenCommands(bot))
