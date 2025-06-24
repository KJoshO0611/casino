import discord
from discord.ui import Button
from discord import ButtonStyle
from typing import Optional, List
from roulette import BetType

class BetTypeButton(Button):
    def __init__(self, bet_type: BetType, row: int):
        super().__init__(
            label=bet_type.value,
            style=ButtonStyle.primary,
            custom_id=f"bet_{bet_type.name}",
            row=row
        )
        self.bet_type = bet_type

class BetAmountModal(discord.ui.Modal, title='Place Your Bet'):
    BETS_WITH_NUMBERS = {
        BetType.STRAIGHT_UP: (1, "Number (0-36)", "e.g., 13"),
        BetType.SPLIT: (2, "Numbers (comma-separated)", "e.g., 8,9"),
        BetType.STREET: (3, "Numbers (comma-separated)", "e.g., 7,8,9"),
        BetType.CORNER: (4, "Numbers (comma-separated)", "e.g., 25,26,28,29"),
        BetType.LINE: (6, "Numbers (comma-separated)", "e.g., 13,14,15,16,17,18"),
    }

    def __init__(self, bet_type: BetType, max_amount: int):
        super().__init__()
        self.bet_type = bet_type
        self.max_amount = max_amount

        self.amount = discord.ui.TextInput(
            label=f"Amount (Max: {max_amount})",
            placeholder="Enter your bet amount...",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.amount)

        if self.bet_type in self.BETS_WITH_NUMBERS:
            _, label, placeholder = self.BETS_WITH_NUMBERS[self.bet_type]
            self.numbers_input = discord.ui.TextInput(
                label=label,
                placeholder=placeholder,
                required=True,
                style=discord.TextStyle.short
            )
            self.add_item(self.numbers_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if not (1 <= amount <= self.max_amount):
                await interaction.response.send_message(f"Enter an amount between 1 and {self.max_amount}.", ephemeral=True)
                return

            numbers = None
            if self.bet_type in self.BETS_WITH_NUMBERS:
                num_count, _, _ = self.BETS_WITH_NUMBERS[self.bet_type]
                try:
                    numbers = [int(n.strip()) for n in self.numbers_input.value.split(',')]
                    if any(not (0 <= n <= 36) for n in numbers):
                        raise ValueError("Numbers must be between 0 and 36.")
                    if len(numbers) != num_count:
                        raise ValueError(f"This bet requires exactly {num_count} numbers.")
                except ValueError as e:
                    await interaction.response.send_message(f"Invalid input: {e}", ephemeral=True)
                    return

            await self.place_bet(interaction, self.bet_type, amount, numbers)

        except ValueError:
            await interaction.response.send_message("Please enter a valid number for the amount.", ephemeral=True)

    async def place_bet(self, interaction: discord.Interaction, bet_type: BetType, amount: int, numbers: Optional[List[int]] = None):
        # This will be implemented in the main cog
        pass
