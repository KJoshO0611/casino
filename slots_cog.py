import discord
from discord.ext import commands
import asyncio

from slots import SlotMachine
from token_manager import token_manager

class SlotsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.machine = SlotMachine()

    @commands.command(name='slots')
    async def play_slots(self, ctx, amount: int):
        """Plays the slot machine for a given amount."""
        user_id = ctx.author.id

        if amount <= 0:
            await ctx.send("You must bet a positive amount of chips.")
            return

        if token_manager.get_chips(user_id) < amount:
            await ctx.send("You don't have enough chips to play.")
            return

        token_manager.add_chips(user_id, -amount)

        reels_message = await ctx.send(f"**{ctx.author.display_name} bets {amount} chips and pulls the lever...**\n\n[ 🎰 | 🎰 | 🎰 ]")
        await asyncio.sleep(1)

        result = self.machine.pull_lever()
        await reels_message.edit(content=f"**{ctx.author.display_name} bets {amount} chips and pulls the lever...**\n\n[ {result[0]} | 🎰 | 🎰 ]")
        await asyncio.sleep(1)

        await reels_message.edit(content=f"**{ctx.author.display_name} bets {amount} chips and pulls the lever...**\n\n[ {result[0]} | {result[1]} | 🎰 ]")
        await asyncio.sleep(1)

        await reels_message.edit(content=f"**{ctx.author.display_name} bets {amount} chips and pulls the lever...**\n\n[ {result[0]} | {result[1]} | {result[2]} ]")

        winnings = self.machine.calculate_winnings(result, amount)

        if winnings > 0:
            token_manager.add_chips(user_id, winnings + amount) # Return original bet + winnings
            await ctx.send(f"🎉 **Congratulations!** You won **{winnings}** chips! 🎉")
        else:
            await ctx.send("Sorry, not a winning spin. Better luck next time!")

async def setup(bot):
    await bot.add_cog(SlotsCog(bot))
