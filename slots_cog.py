import discord
from discord.ext import commands
import asyncio
import discord

from slots import SlotMachine
from token_manager import token_manager
from collections import Counter
from slots_ui import SlotsView

class SlotsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.machine = SlotMachine()

    @commands.command(name='slots')
    async def play_slots(self, ctx):
        """Displays the interactive slot machine UI."""
        view = SlotsView(self)
        embed = view.create_embed(ctx.author)
        await ctx.send(embed=embed, view=view)

    async def execute_spin(self, interaction: discord.Interaction, amount: int, spins: int):
        user_id = interaction.user.id
        total_cost = amount * spins

        if token_manager.get_chips(user_id) < total_cost:
            await interaction.followup.send("You don't have enough chips for this bet.", ephemeral=True)
            return

        token_manager.remove_chips(user_id, total_cost, destination_id=token_manager.CASINO_POOL_ID)

        if spins == 1:
            # Single spin with animation
            reels_message = await interaction.followup.send(f"**{interaction.user.display_name} bets {amount:,} chips and pulls the lever...**\n\n[ 🎰 | 🎰 | 🎰 ]")
            await asyncio.sleep(1)

            result = self.machine.pull_lever(user_id)
            await reels_message.edit(content=f"**{interaction.user.display_name} bets {amount:,} chips and pulls the lever...**\n\n[ {result[0]} | 🎰 | 🎰 ]")
            await asyncio.sleep(1)

            await reels_message.edit(content=f"**{interaction.user.display_name} bets {amount:,} chips and pulls the lever...**\n\n[ {result[0]} | {result[1]} | 🎰 ]")
            await asyncio.sleep(1)

            await reels_message.edit(content=f"**{interaction.user.display_name} bets {amount:,} chips and pulls the lever...**\n\n[ {result[0]} | {result[1]} | {result[2]} ]")

            winnings = self.machine.calculate_winnings(user_id, result, amount)

            if winnings > 0:
                is_jackpot = Counter(result)['BAR'] == 3
                pool_balance = token_manager.get_pool_balance()
                max_win = int(pool_balance * 0.10)
                
                capped = False
                if not is_jackpot and winnings > max_win:
                    winnings = max_win
                    capped = True

                repayment_message = token_manager.add_chips(user_id, winnings, source_id=token_manager.CASINO_POOL_ID)
                if repayment_message:
                    await interaction.followup.send(repayment_message, ephemeral=True)
                
                win_message = self.machine.get_win_description(user_id, winnings, amount, result)
                if capped:
                    win_message += f"\n*(Your winnings were capped to 10% of the casino's pool to ensure economic stability.)*"
                await interaction.followup.send(win_message)
            else:
                loss_message = self.machine.get_win_description(user_id, winnings, amount, result)
                await interaction.followup.send(loss_message)
        else:
            # Animated multi-spin logic
            embed = discord.Embed(
                title="🎰 Multi-Spin in Progress... 🎰",
                description=f"Running {spins} spins for {interaction.user.display_name}...",
                color=discord.Color.blue()
            )
            progress_message = await interaction.followup.send(embed=embed, wait=True)

            total_winnings = 0
            jackpots_won = 0

            for i in range(spins):
                result = self.machine.pull_lever(user_id)
                winnings = self.machine.calculate_winnings(user_id, result, amount)
                
                spin_win = 0
                is_jackpot = Counter(result)['BAR'] == 3

                if winnings > 0:
                    if is_jackpot:
                        jackpots_won += 1
                    
                    pool_balance = token_manager.get_pool_balance()
                    max_win = int(pool_balance * 0.10)
                    if not is_jackpot and winnings > max_win:
                        winnings = max_win
                    
                    spin_win = winnings
                    total_winnings += winnings

                spin_embed = discord.Embed(
                    title=f"Spin {i + 1}/{spins}",
                    description=f"**[ {result[0]} | {result[1]} | {result[2]} ]**",
                    color=discord.Color.gold() if spin_win > 0 else discord.Color.dark_grey()
                )
                
                if is_jackpot:
                    spin_embed.add_field(name="Result", value=f"🏆 JACKPOT! You won {spin_win:,}! 🏆", inline=False)
                elif spin_win > 0:
                    spin_embed.add_field(name="Result", value=f"You won {spin_win:,} chips!", inline=False)
                else:
                    spin_embed.add_field(name="Result", value="No win.", inline=False)

                spin_embed.add_field(name="Total Won So Far", value=f"{total_winnings:,}", inline=True)
                spin_embed.set_footer(text=f"Player: {interaction.user.display_name}")

                await progress_message.edit(embed=spin_embed)
                await asyncio.sleep(1.5 if spins <= 10 else 1.0)

            if total_winnings > 0:
                repayment_message = token_manager.add_chips(user_id, total_winnings, source_id=token_manager.CASINO_POOL_ID)
                if repayment_message:
                    await interaction.followup.send(repayment_message, ephemeral=True)
            
            net_result = total_winnings - total_cost
            final_embed = discord.Embed(
                title="🎰 Multi-Spin Finished 🎰",
                color=discord.Color.green() if net_result >= 0 else discord.Color.red(),
                description=f"All {spins} spins are complete."
            )
            final_embed.add_field(name="Total Bet", value=f"{total_cost:,}", inline=True)
            final_embed.add_field(name="Total Winnings", value=f"{total_winnings:,}", inline=True)
            final_embed.add_field(name="Net Result", value=f"**{net_result:+,} chips**", inline=False)
            
            if jackpots_won > 0:
                final_embed.description += f"\n\n**🏆 CONGRATULATIONS! You hit the JACKPOT {jackpots_won} time(s)! 🏆**"
            
            final_embed.set_footer(text=f"Player: {interaction.user.display_name}")
            await progress_message.edit(embed=final_embed)

    @commands.command(name='jackpot')
    async def show_jackpot(self, ctx):
        """Displays the current progressive jackpot pool."""
        jackpot_value = self.machine.jackpot_pool
        await ctx.send(f"💰 The current progressive jackpot is **{jackpot_value:,.0f}** chips! 💰")

async def setup(bot):
    await bot.add_cog(SlotsCog(bot))
