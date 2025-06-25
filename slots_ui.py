import discord
import asyncio

# Modal for custom bet input
class CustomBetModal(discord.ui.Modal, title='Custom Bet'):
    bet_amount = discord.ui.TextInput(
        label='Enter your bet amount',
        placeholder='e.g., 123',
        style=discord.TextStyle.short,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Defer to prevent interaction failure
        await interaction.response.defer()

# The main view for the slot machine UI
class SlotsView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=180.0)
        self.cog = cog
        self.bet_amount = 10
        self.spin_multiplier = 1

    # --- Bet Amount Buttons ---
    @discord.ui.button(label='10 Chips', style=discord.ButtonStyle.green, row=0)
    async def bet_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bet_amount = 10
        await self.update_message(interaction)

    @discord.ui.button(label='50 Chips', style=discord.ButtonStyle.green, row=0)
    async def bet_50(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bet_amount = 50
        await self.update_message(interaction)

    @discord.ui.button(label='100 Chips', style=discord.ButtonStyle.green, row=0)
    async def bet_100(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bet_amount = 100
        await self.update_message(interaction)

    @discord.ui.button(label='Custom', style=discord.ButtonStyle.grey, row=0)
    async def custom_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CustomBetModal()
        modal.on_submit = self.on_custom_bet_submit(modal, interaction)
        await interaction.response.send_modal(modal)

    def on_custom_bet_submit(self, modal, original_interaction):
        async def callback(interaction: discord.Interaction):
            try:
                bet_val = int(modal.bet_amount.value)
                if bet_val > 0:
                    self.bet_amount = bet_val
                    await self.update_message(original_interaction, interaction)
                else:
                    await interaction.response.send_message("Bet must be a positive number.", ephemeral=True)
            except ValueError:
                await interaction.response.send_message("Invalid number format.", ephemeral=True)
        return callback

    # --- Spin Multiplier Buttons ---
    @discord.ui.button(label='1x Spin', style=discord.ButtonStyle.blurple, row=1)
    async def spins_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.spin_multiplier = 1
        await self.update_message(interaction)

    @discord.ui.button(label='10x Spins', style=discord.ButtonStyle.blurple, row=1)
    async def spins_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.spin_multiplier = 10
        await self.update_message(interaction)

    @discord.ui.button(label='50x Spins', style=discord.ButtonStyle.blurple, row=1)
    async def spins_50(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.spin_multiplier = 50
        await self.update_message(interaction)

    # --- Spin Action Button ---
    @discord.ui.button(label='Spin!', style=discord.ButtonStyle.red, row=2)
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer() # Acknowledge interaction
        # Disable buttons after spinning
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        # Execute the spin logic from the cog
        await self.cog.execute_spin(interaction, self.bet_amount, self.spin_multiplier)

    # --- Helper Methods ---
    def create_embed(self, user):
        total_cost = self.bet_amount * self.spin_multiplier
        embed = discord.Embed(
            title="🎰 Slot Machine 🎰",
            description=f"Set your bet and number of spins.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Current Bet", value=f"{self.bet_amount:,} chips", inline=True)
        embed.add_field(name="Spins", value=f"{self.spin_multiplier}x", inline=True)
        embed.add_field(name="Total Cost", value=f"{total_cost:,} chips", inline=True)
        embed.set_footer(text=f"Player: {user.display_name}")
        return embed

    async def update_message(self, interaction: discord.Interaction, modal_interaction: discord.Interaction = None):
        embed = self.create_embed(interaction.user)
        if modal_interaction:
            # If coming from a modal, the original interaction is what we edit
            await interaction.message.edit(embed=embed, view=self)
            # And we need to acknowledge the modal's interaction
            await modal_interaction.response.defer()
        else:
            await interaction.response.edit_message(embed=embed, view=self)
