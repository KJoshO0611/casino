import discord
from discord.ext import commands

from token_manager import token_manager

class ScoresCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='leaderboard')
    async def show_leaderboard(self, ctx, top_n=10):
        """Displays the top players with the most chips across all games."""
        all_chips = token_manager.get_all_chips()
        
        if not all_chips:
            await ctx.send("The leaderboard is currently empty.")
            return

        # Sort players by chip count in descending order
        sorted_players = sorted(all_chips.items(), key=lambda item: item[1], reverse=True)
        
        embed = discord.Embed(title="🏆 Casino Leaderboard 🏆", color=discord.Color.gold())
        
        description = ""
        for i, (user_id, chips) in enumerate(sorted_players[:top_n]):
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name
            except discord.NotFound:
                username = f"User ID: {user_id}"
            
            rank = i + 1
            emoji = ""
            if rank == 1:
                emoji = "🥇"
            elif rank == 2:
                emoji = "🥈"
            elif rank == 3:
                emoji = "🥉"
            
            description += f"{rank}. {emoji} **{username}** - {chips:,} chips\n"
            
        embed.description = description
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ScoresCog(bot))
