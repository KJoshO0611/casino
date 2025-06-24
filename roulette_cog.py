import discord
from discord.ext import commands
from typing import Dict, List, Optional
from discord import Button, ButtonStyle

from roulette import RouletteGame, BetType
from token_manager import token_manager
from roulette_components import BetTypeButton, BetAmountModal

# Update this URL with your actual roulette table image
ROULETTE_TABLE_URL = "https://cdn.discordapp.com/attachments/1386698939230584932/1386948821879230474/american-roulette-table-layout-with-bets-and-options-vector.png?ex=685b903f&is=685a3ebf&hm=d59c54df8010ff14efce1edbbc98823c37ed59b835016cca95226ebaaea2ea1a&"

class RouletteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games: Dict[int, RouletteGame] = {}
        self.active_views: Dict[int, discord.ui.View] = {}
        
    async def create_betting_interface(self, channel_id: int):
        """Creates and returns a view with betting buttons."""
        view = discord.ui.View(timeout=300)  # 5 minute timeout
        
        # Group bet types into rows
        bet_groups = [
            [BetType.STRAIGHT_UP, BetType.SPLIT, BetType.STREET, BetType.CORNER, BetType.LINE],
            [BetType.RED, BetType.BLACK, BetType.ODD, BetType.EVEN, BetType.FIRST_FOUR],
            [BetType.LOW, BetType.HIGH, BetType.DOZEN_1, BetType.DOZEN_2, BetType.DOZEN_3],
            [BetType.COLUMN_1, BetType.COLUMN_2, BetType.COLUMN_3]
        ]
        
        # Add buttons to the view
        for row, bet_group in enumerate(bet_groups):
            for bet_type in bet_group:
                button = BetTypeButton(bet_type, row)
                button.callback = self.bet_button_callback
                view.add_item(button)
        
        return view
        
    async def bet_button_callback(self, interaction: discord.Interaction):
        """Handles bet button clicks."""
        # Get the custom ID and extract bet type
        custom_id = interaction.data["custom_id"]
        bet_type_name = custom_id[4:]  # Remove 'bet_' prefix
        
        try:
            bet_type = BetType[bet_type_name]
        except KeyError:
            await interaction.response.send_message("Invalid bet type.", ephemeral=True)
            return
        
        # Check if user has enough chips
        user_chips = token_manager.get_chips(interaction.user.id)
        if user_chips <= 0:
            await interaction.response.send_message("You don't have any chips to bet!", ephemeral=True)
            return
            
        # Create and send the bet amount modal
        modal = BetAmountModal(bet_type, user_chips)
        modal.place_bet = self.place_bet_from_modal
        await interaction.response.send_modal(modal)
    
    async def place_bet_from_modal(self, interaction: discord.Interaction, bet_type: BetType, amount: int, numbers: Optional[List[int]] = None):
        """Handles the bet placement from the modal."""
        channel_id = interaction.channel_id
        if channel_id not in self.games:
            await interaction.response.send_message("No active roulette game in this channel.", ephemeral=True)
            return

        user_id = interaction.user.id
        game = self.games[channel_id]

        bet_value = numbers
        bet_type_str = bet_type.value
        if numbers:
            bet_type_str += f" on {', '.join(map(str, numbers))}"

        # Move chips to the casino pool before placing the bet
        token_manager.remove_chips(user_id, amount, destination_id=token_manager.CASINO_POOL_ID)
        game.place_bet(user_id, bet_type, bet_value, amount)

        await interaction.response.send_message(
            f"{interaction.user.mention} placed a bet of {amount} chips on {bet_type_str}.",
            ephemeral=False
        )

    @commands.command(name='roulette')
    async def start_roulette(self, ctx):
        """Starts a new roulette game in the channel with an interactive interface."""
        channel_id = ctx.channel.id
        if channel_id in self.games:
            await ctx.send("A roulette game is already in progress in this channel.")
            return
        
        # Create new game
        self.games[channel_id] = RouletteGame()
        
        # Create embed with instructions and table image
        embed = discord.Embed(
            title="🎰 Roulette Game Started! 🎰",
            description="Place your bets using the buttons below.\nClick on a bet type to place your bet.",
            color=0x00ff00
        )
        embed.set_image(url=ROULETTE_TABLE_URL)
        
        # Create and send the betting interface
        view = await self.create_betting_interface(channel_id)
        self.active_views[channel_id] = view
        
        await ctx.send(embed=embed, view=view)
        await ctx.send("🎲 **Betting is open!** Use the buttons above to place your bets. 🎲")
        
        # Store the view to prevent it from being garbage collected

    @commands.command(name='bet_types')
    async def list_bet_types(self, ctx):
        """Lists all available bet types for roulette."""
        embed = discord.Embed(title="Roulette Bet Types", color=0xff0000)
        bet_info = ""
        for bet in BetType:
            bet_info += f"- **{bet.name.lower()}**: {bet.value}\n"
        embed.description = bet_info
        await ctx.send(embed=embed)

    @commands.command(name='bet', description="Place a bet using text commands. e.g., !bet 100 split 8,9")
    async def place_bet(self, ctx, amount: int, bet_type_str: str, *, bet_value: str = None):
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
        
        value_to_bet = None
        bet_display_value = ""

        BETS_WITH_NUMBERS = {
            BetType.STRAIGHT_UP: 1,
            BetType.SPLIT: 2,
            BetType.STREET: 3,
            BetType.CORNER: 4,
            BetType.LINE: 6,
        }

        if bet_type in BETS_WITH_NUMBERS:
            if bet_value is None:
                await ctx.send(f"A `{bet_type.value}` bet requires numbers. Example: `!bet {amount} {bet_type_str.lower()} 1,2,3`")
                return
            
            try:
                numbers = [int(n.strip()) for n in bet_value.split(',')]
                if any(not (0 <= n <= 36) for n in numbers):
                    raise ValueError("Numbers must be between 0 and 36.")

                required_count = BETS_WITH_NUMBERS[bet_type]
                if len(numbers) != required_count:
                    raise ValueError(f"This bet requires exactly {required_count} number(s).")

                if bet_type == BetType.STRAIGHT_UP:
                    value_to_bet = numbers[0]
                else:
                    value_to_bet = numbers
                
                bet_display_value = f" on {', '.join(map(str, numbers))}"

            except ValueError as e:
                await ctx.send(f"Invalid input for numbers: {e}")
                return

        elif bet_type == BetType.FIRST_FOUR:
            value_to_bet = [0, 1, 2, 3]
        
        # Move chips to the casino pool before placing the bet
        token_manager.remove_chips(user_id, amount, destination_id=token_manager.CASINO_POOL_ID)
        game.place_bet(user_id, bet_type, value_to_bet, amount)
        await ctx.send(f"{ctx.author.display_name} has placed a bet of {amount} chips on `{bet_type.value}{bet_display_value}`.")

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
            # Clean up the view
            if channel_id in self.active_views:
                self.active_views[channel_id].stop()
                del self.active_views[channel_id]
            del self.games[channel_id]
            return
        
        # Disable all buttons
        if channel_id in self.active_views:
            for item in self.active_views[channel_id].children:
                item.disabled = True
            
            # Edit the original message to disable the buttons
            try:
                messages = [msg async for msg in ctx.channel.history(limit=10)]
                for msg in messages:
                    if msg.components:
                        await msg.edit(view=self.active_views[channel_id])
                        break
            except Exception as e:
                print(f"Error disabling buttons: {e}")
            
            # Clean up the view
            self.active_views[channel_id].stop()
            del self.active_views[channel_id]
        
        # Spin the wheel and get results
        payouts, winning_number, winning_color = game.resolve_bets()

        color_emoji = "🔴" if winning_color == 'red' else "⚫"
        if winning_number == 0:
            color_emoji = "🟢"

        result_embed = discord.Embed(
            title="The Wheel has Spun!",
            description=f"The winning number is **{winning_number}** {color_emoji}",
            color=discord.Color.gold()
        )

        winners_str = ""
        pool_balance = token_manager.get_pool_balance()
        max_win_per_spin = int(pool_balance * 0.15) # Cap at 15% of the pool

        for user_id, amount_won in payouts.items():
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            
            original_win = amount_won
            capped = False
            if amount_won > max_win_per_spin:
                amount_won = max_win_per_spin
                capped = True

            # Pay out winnings from the casino pool. `amount_won` from `resolve_bets` already includes the original bet.
            repayment_message = token_manager.add_chips(user_id, amount_won, source_id=token_manager.CASINO_POOL_ID)
            if repayment_message:
                await ctx.send(repayment_message)
            
            win_message = f"{user.mention} won **{amount_won:,}** chips!\n"
            if capped:
                win_message += f"*(Your winnings of {original_win:,} were capped to {amount_won:,} to ensure casino stability.)*\n"
            winners_str += win_message

        if not winners_str:
            winners_str = "No winners this round. The house wins!"

        result_embed.add_field(name="Results", value=winners_str, inline=False)
        await ctx.send(embed=result_embed)

        del self.games[channel_id]

    def cog_unload(self):
        """Clean up views when the cog is unloaded."""
        for view in self.active_views.values():
            view.stop()

async def setup(bot):
    await bot.add_cog(RouletteCog(bot))
