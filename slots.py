import discord
from discord import app_commands
from discord.ext import commands
import random
from token_manager import TokenManager

class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.symbols = ["🍒", "🍊", "🍇", "💎", "💰", "7️⃣"]
        self.symbol_values = {
            "🍒": 1,
            "🍊": 2,
            "🍇": 3,
            "💎": 4,
            "💰": 5,
            "7️⃣": 10
        }
        self.token_manager = TokenManager()

    @app_commands.command(name="slots", description="Play slots machine")
    @app_commands.describe(amount="Amount to bet")
    async def slots(self, interaction: discord.Interaction, amount: int):
        """Play the slots machine"""
        user_id = str(interaction.user.id)
        chips = user_tokens.get(user_id, 1000)
        
        if chips < amount:
            await interaction.response.send_message(f"❌ You don't have enough chips! You have {chips} chips.", ephemeral=True)
            return

        # Spin the reels
        reels = [random.choice(self.symbols) for _ in range(3)]
        
        # Calculate winnings
        winnings = 0
        if reels[0] == reels[1] == reels[2]:  # All matching
            winnings = amount * self.symbol_values[reels[0]] * 10
        elif reels[0] == reels[1] or reels[1] == reels[2]:  # Two matching
            winnings = amount * self.symbol_values[reels[1]] * 2

        # Update chip balance
        user_tokens[user_id] -= amount
        if winnings > 0:
            user_tokens[user_id] += winnings
        save_user_tokens(user_tokens)

        # Create embed
        embed = discord.Embed(
            title="🎰 Slots Machine",
            description="""```
[ {} | {} | {} ]
```""".format(*reels),
            color=discord.Color.gold() if winnings > 0 else discord.Color.red()
        )

        if winnings > 0:
            embed.add_field(
                name="💰 You Won!",
                value=f"You won {winnings} chips!",
                inline=False
            )
        else:
            embed.add_field(
                name=" HOUSE WINS",
                value="Better luck next time!",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Slots(bot))
