import discord
from discord.ext import commands
import os
import dotenv
from token_manager import TokenManager

dotenv.load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize token manager
token_manager = TokenManager()

# Load cogs
async def load_extensions():
    extensions = [
        'blackjack',
        'poker',
        'roulette',
        'slots',
        'token_commands',
        'help'
    ]
    
    for extension in extensions:
        try:
            await discord_bot.load_extension(extension)
            print(f"Loaded extension: {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}: {e}")

# Run the bot
@discord_bot.event
async def on_ready():
    print(f'Bot is ready as {discord_bot.user.name}')
    await load_extensions()

if __name__ == "__main__":
    discord_bot.run(os.getenv('TOKEN'))
