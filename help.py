import discord
from discord.ext import commands
from discord import app_commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction):
        """Show help menu with all available commands"""
        embed = discord.Embed(
            title="🎲 Casino Bot Help",
            description="Welcome to the Casino Bot! Here are all the available commands:",
            color=discord.Color.gold()
        )

        # Token Commands
        token_commands = [
            "`!addtokens <amount> [user]` - Admin: Add tokens to a player",
            "`!removetokens <amount> [user]` - Admin: Remove tokens from a player",
            "`!settokens <amount> [user]` - Admin: Set a player's token balance",
            "`!checktokens [user]` - Check your or another player's token balance",
            "`!tokensleaderboard [limit]` - Show token leaderboard",
            "`!dailytokens` - Claim daily token bonus (1000 tokens)"
        ]
        embed.add_field(
            name="💰 Token Commands",
            value="\n".join(token_commands),
            inline=False
        )

        # Blackjack Commands
        blackjack_commands = [
            "`!create_table [id]` - Create a new blackjack table",
            "`!start_betting [id]` - Admin: Start betting phase",
            "`!start_game [id]` - Admin: Start the game",
            "`!deal_new_hand [id]` - Admin: Deal new hands",
            "`!close_table [id]` - Admin: Close a table",
            "`!list_tables` - List all active tables"
        ]
        embed.add_field(
            name="🃏 Blackjack Commands",
            value="\n".join(blackjack_commands),
            inline=False
        )

        # Poker Commands
        poker_commands = [
            "`!poker [small_blind] [big_blind]` - Create a new poker table",
            "`!start` - Start the poker game",
            "`!call` - Match the current bet",
            "`!raise <amount>` - Raise the bet",
            "`!fold` - Fold your hand",
            "`!check` - Check (bet nothing)"
        ]
        embed.add_field(
            name="♠️ Poker Commands",
            value="\n".join(poker_commands),
            inline=False
        )

        # Roulette Commands
        roulette_commands = [
            "`/roulette <amount> [number] [color]` - Place a bet on roulette",
            "`/spin` - Admin: Spin the roulette wheel"
        ]
        embed.add_field(
            name="roulette Commands",
            value="\n".join(roulette_commands),
            inline=False
        )

        # Slots Commands
        slots_commands = [
            "`/slots <amount>` - Play the slots machine"
        ]
        embed.add_field(
            name="🎰 Slots Commands",
            value="\n".join(slots_commands),
            inline=False
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
