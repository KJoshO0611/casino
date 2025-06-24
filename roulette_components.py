import discord
from discord import Button, ButtonStyle
from typing import Optional
from .roulette import BetType

class BetTypeButton(Button):
    def __init__(self, bet_type: BetType, row: int):
        super().__init__(
            label=bet_type.value,
            style=ButtonStyle.primary,
            custom_id=f"bet_{bet_type.name}",
            row=row
        )
        self.bet_type = bet_type

class BetAmountModal(discord.ui.Modal):
    def __init__(self, bet_type: BetType, max_amount: int):
        super().__init__(title=f"Place {bet_type.value} Bet")
        self.bet_type = bet_type
        self.max_amount = max_amount
        
        self.amount = discord.ui.TextInput(
            label=f"Amount (1-{max_amount} chips)",
            placeholder="Enter your bet amount...",
            min_length=1,
            max_length=len(str(max_amount))
        )
        
        if bet_type == BetType.STRAIGHT_UP:
            self.number = discord.ui.TextInput(
                label="Number (0-36)",
                placeholder="Enter a number between 0 and 36...",
                min_length=1,
                max_length=2,
                required=True
            )
            self.add_item(self.number)
        
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount < 1 or amount > self.max_amount:
                await interaction.response.send_message(
                    f"Please enter an amount between 1 and {self.max_amount}.", 
                    ephemeral=True
                )
                return
                
            if self.bet_type == BetType.STRAIGHT_UP:
                try:
                    number = int(self.number.value)
                    if number < 0 or number > 36:
                        raise ValueError
                except ValueError:
                    await interaction.response.send_message(
                        "Please enter a valid number between 0 and 36.",
                        ephemeral=True
                    )
                    return
                
                await self.place_bet(interaction, amount, number)
            else:
                await self.place_bet(interaction, amount)
                
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.",
                ephemeral=True
            )
    
    async def place_bet(self, interaction: discord.Interaction, amount: int, number: Optional[int] = None):
        # This will be implemented in the main cog
        pass
