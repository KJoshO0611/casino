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
        loan = token_manager.get_loan(member.id)
        
        message = f"**{member.display_name}** has **{balance:,}** chips."
        if loan > 0:
            message += f"\nThey have an outstanding loan of **{loan:,}** chips."
        await ctx.send(message)

    @commands.command(name='pool')
    async def show_pool(self, ctx):
        """Shows the current balance of the casino's chip pool."""
        pool_balance = token_manager.get_pool_balance()
        await ctx.send(f"?? The casino pool currently has **{pool_balance:,}** chips.")

    @commands.command(name='grant')
    @commands.has_permissions(manage_guild=True)
    async def grant_chips(self, ctx, member: discord.Member, amount: int):
        """Grants a specified amount of chips to a user."""
        repayment_message = token_manager.add_chips(member.id, amount)
        new_balance = token_manager.get_chips(member.id)
        await ctx.send(f"?? Granted {amount:,} chips to **{member.display_name}**.\nNew balance: **{new_balance:,}** chips.")
        if repayment_message:
            await ctx.send(repayment_message)

    @commands.command(name='loan')
    async def loan_chips(self, ctx, amount: int):
        """Borrows a specified amount of chips from the house."""
        if amount <= 0:
            await ctx.send("You must borrow a positive amount of chips.")
            return

        if amount > 5000:
            await ctx.send("You can borrow a maximum of 5,000 chips at a time.")
            return

        success, message = token_manager.grant_loan(ctx.author.id, amount)
        
        if success:
            new_balance = token_manager.get_chips(ctx.author.id)
            await ctx.send(f"?? {message}\nYour new balance is **{new_balance:,}** chips.")
        else:
            await ctx.send(f"?? {message}")

    @commands.command(name='repay')
    async def repay_loan(self, ctx, amount: int):
        """Repay a specified amount of chips to the house."""
        if amount <= 0:
            await ctx.send("You must repay a positive amount of chips.")
            return
        
        success, message = token_manager.repay_loan(ctx.author.id, amount)
        
        if success:
            new_balance = token_manager.get_chips(ctx.author.id)
            await ctx.send(f"?? {message}\nYour new balance is **{new_balance:,}** chips.")
        else:
            await ctx.send(f"?? {message}")

async def setup(bot):
    await bot.add_cog(ChipCog(bot))
