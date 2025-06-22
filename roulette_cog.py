import discord
from discord.ext import commands
from typing import Dict

from roulette import RouletteGame, BetType
from token_manager import token_manager

class RouletteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games: Dict[int, RouletteGame] = {}

    @commands.command(name='roulette')
    async def start_roulette(self, ctx):
        """Starts a new roulette game in the channel."""
        channel_id = ctx.channel.id
        if channel_id in self.games:
            await ctx.send("A roulette game is already in progress in this channel.")
            return
        
        self.games[channel_id] = RouletteGame()
        await ctx.send("**New Roulette Game Started!**\nPlace your bets with `!rbet <amount> <bet_type> [number]`\nExample: `!rbet 100 red` or `!rbet 10 straight_up 23`\nType `!bet_types` for all options. Once all bets are in, an admin can `!spin` the wheel!")

    @commands.command(name='bet_types')
    async def list_bet_types(self, ctx):
        """Lists all available bet types for roulette."""
        embed = discord.Embed(title="Roulette Bet Types", color=0xff0000)
        bet_info = ""
        for bet in BetType:
            bet_info += f"- **{bet.name.lower()}**: {bet.value}\n"
        embed.description = bet_info
        await ctx.send(embed=embed)

    @commands.command(name='rbet')
    async def place_bet(self, ctx, amount: int, bet_type_str: str, bet_value: str = None):
        """Places a bet on the roulette table."""
        channel_id = ctx.channel.id
        if channel_id not in self.games:
            await ctx.send("No roulette game in progress. Start one with `!roulette`.")
            return

        try:
            bet_type = BetType[bet_type_str.upper()]
        except KeyError:
            await ctx.send(f"Invalid bet type: `{bet_type_str}`. Use `!bet_types` to see valid options.")
            return

        user_id = ctx.author.id
        if token_manager.get_chips(user_id) < amount:
            await ctx.send("You don't have enough chips for that bet.")
            return

        game = self.games[channel_id]
        
        # For bets that require a number
        if bet_type == BetType.STRAIGHT_UP:
            if bet_value is None or not bet_value.isdigit() or not (0 <= int(bet_value) <= 36):
                await ctx.send("A `straight_up` bet requires a number between 0 and 36.")
                return
            value_to_bet = int(bet_value)
        else:
            value_to_bet = None # For color, even/odd, etc.

        token_manager.add_chips(user_id, -amount)
        game.place_bet(user_id, bet_type, value_to_bet, amount)
        await ctx.send(f"{ctx.author.display_name} has placed a bet of {amount} chips on `{bet_type_str.lower()}`.")

    @commands.command(name='spin')
    @commands.has_permissions(manage_guild=True)
    async def spin_wheel(self, ctx):
        """Spins the roulette wheel and resolves all bets."""
        channel_id = ctx.channel.id
        if channel_id not in self.games:
            await ctx.send("No roulette game in progress.")
            return

        game = self.games[channel_id]
        if not game.players_bets:
            await ctx.send("No bets have been placed. The wheel spins for nothing.")
            del self.games[channel_id]
            return
        
        winnings, winning_number, winning_color = game.resolve_bets()

        color_emoji = ":red_circle:" if winning_color == 'red' else ":black_circle:"
        if winning_color == 'green':
            color_emoji = ":green_circle:"

        result_embed = discord.Embed(
            title="The Wheel has Spun!",
            description=f"The winning number is **{winning_number}** {color_emoji}",
            color=discord.Color.gold()
        )

        winners_str = ""
        for user_id, amount_won in winnings.items():
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if amount_won > 0:
                winners_str += f"{user.mention} won **{amount_won}** chips!\n"
                token_manager.add_chips(user_id, amount_won)
            else:
                 winners_str += f"{user.mention} lost **{-amount_won}** chips.\n"

        if not winners_str:
            winners_str = "No winners this round. The house wins!"

        result_embed.add_field(name="Results", value=winners_str, inline=False)
        await ctx.send(embed=result_embed)

        del self.games[channel_id]

async def setup(bot):
    await bot.add_cog(RouletteCog(bot))
