import discord
from discord import app_commands
from discord.ext import commands
import random
from token_manager import TokenManager

class Roulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bets = {}
        self.current_game = None
        self.wheel = list(range(0, 37))
        self.colors = {0: "green", **{n: "red" if n % 2 == 1 else "black" for n in range(1, 37)}}
        self.token_manager = TokenManager()

    @app_commands.command(name="roulette", description="Play roulette")
    @app_commands.describe(amount="Amount to bet", number="Number to bet on (0-36)", color="Color to bet on (red/black)")
    async def roulette(self, interaction: discord.Interaction, amount: int, number: int = None, color: str = None):
        """Place a bet on roulette"""
        if not number and not color:
            await interaction.response.send_message("❌ You must bet on either a number or a color!", ephemeral=True)
            return

        if number and (number < 0 or number > 36):
            await interaction.response.send_message("❌ Number must be between 0 and 36!", ephemeral=True)
            return

        if color and color.lower() not in ["red", "black"]:
            await interaction.response.send_message("❌ Color must be either 'red' or 'black'!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        chips = user_tokens.get(user_id, 1000)
        
        if chips < amount:
            await interaction.response.send_message(f"❌ You don't have enough chips! You have {chips} chips.", ephemeral=True)
            return

        if self.current_game:
            await interaction.response.send_message("❌ A game is already in progress!", ephemeral=True)
            return

        # Create new game
        self.current_game = {
            "number": None,
            "color": None,
            "bets": [],
            "players": set()
        }

        bet = {
            "user_id": user_id,
            "amount": amount,
            "number": number,
            "color": color
        }

        self.current_game["bets"].append(bet)
        self.current_game["players"].add(user_id)

        user_tokens[user_id] -= amount
        save_user_tokens(user_tokens)

        await interaction.response.send_message(
            f"💰 Bet placed! {amount} chips on {number if number else color}",
            ephemeral=True
        )

    @app_commands.command(name="spin", description="Spin the roulette wheel")
    @app_commands.checks.has_permissions(administrator=True)
    async def spin(self, interaction: discord.Interaction):
        """Spin the roulette wheel (admin only)"""
        if not self.current_game:
            await interaction.response.send_message("❌ No game in progress!", ephemeral=True)
            return

        # Spin the wheel
        winning_number = random.choice(self.wheel)
        winning_color = self.colors[winning_number]

        # Determine winners
        winners = []
        total_winnings = 0
        for bet in self.current_game["bets"]:
            if (bet["number"] == winning_number) or (bet["color"] and bet["color"].lower() == winning_color):
                multiplier = 35 if bet["number"] == winning_number else 1
                winnings = bet["amount"] * multiplier
                user_tokens[bet["user_id"]] += winnings
                total_winnings += winnings
                winners.append((bet["user_id"], winnings))

        save_user_tokens(user_tokens)

        # Create embed
        embed = discord.Embed(
            title="roulette 🎰",
            description=f"The wheel landed on {winning_number} {winning_color}!",
            color=discord.Color.gold()
        )

        if winners:
            embed.add_field(
                name="Winners!",
                value="\n".join(f"<@{user_id}> won {winnings} chips!" for user_id, winnings in winners),
                inline=False
            )
        else:
            embed.add_field(
                name="House Wins!",
                value="No winners this round!",
                inline=False
            )

        await interaction.response.send_message(embed=embed)
        self.current_game = None

async def setup(bot):
    await bot.add_cog(Roulette(bot))
