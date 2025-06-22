import discord
from discord.ext import commands

from token_manager import token_manager

class ChipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='chips', aliases=['balance', 'tokens'])
    async def show_chips(self, ctx, member: discord.Member = None):
        """Checks the chip balance for a user. Defaults to yourself if no user is mentioned."""
        if member is None:
            member = ctx.author
        
        balance = token_manager.get_chips(member.id)
        await ctx.send(f"**{member.display_name}** has **{balance:,}** chips.")

    @commands.command(name='grant')
    @commands.has_permissions(manage_guild=True)
    async def grant_chips(self, ctx, member: discord.Member, amount: int):
        """Grants a specified amount of chips to a user."""
        token_manager.add_chips(member.id, amount)
        new_balance = token_manager.get_chips(member.id)
        await ctx.send(f"💰 Granted {amount:,} chips to **{member.display_name}**.\nNew balance: **{new_balance:,}** chips.")

async def setup(bot):
    await bot.add_cog(ChipCog(bot))
