import discord
from discord.ext import commands
import os
import dotenv
import logging

# Load environment variables
dotenv.load_dotenv()

# Configure intents
intents = discord.Intents.all()
intents.message_content = True
intents.members = True

# Configure logging using discord.py's utility
discord.utils.setup_logging(level=logging.INFO, root=False)

class CasinoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        """Loads all cogs."""
        await self.load_extension('poker_cog')
        print("Poker cog loaded.")
        await self.load_extension('blackjack_cog')
        print("Blackjack cog loaded.")
        await self.load_extension('roulette_cog')
        print("Roulette cog loaded.")
        await self.load_extension('slots_cog')
        print("Slots cog loaded.")
        await self.load_extension('scores_cog')
        print("Scores cog loaded.")
        await self.load_extension('chip_cog')
        print("Chip cog loaded.")
        print("------")

    async def on_ready(self):
        """Called when the bot is ready."""
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message):
        """Processes messages and commands."""
        if message.author.bot:
            return
        await self.process_commands(message)

    @commands.command()
    @commands.is_owner()
    async def reload(self, ctx, cog: str):
        """Reloads a cog."""
        try:
            await self.reload_extension(f"{cog}")
            await ctx.send(f"'{cog}' reloaded successfully.")
        except commands.ExtensionError as e:
            await ctx.send(f"Error reloading '{cog}': {e}")

if __name__ == "__main__":
    print(f"--- Starting Bot (PID: {os.getpid()}) ---")
    bot = CasinoBot()
    bot.run(os.getenv('TOKEN'))
