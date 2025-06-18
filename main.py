import discord
from discord.ext import commands
from discord import app_commands, Interaction, Embed, ButtonStyle
from discord.ui import Button, View
import random
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Global Configurations
MAX_PAYOUT_MULTIPLIER = 5

SLOT_SYMBOLS = ['🍒', '🍋', '7️⃣', '🍊', '⭐', '🍇']

ROULETTE_NUMBERS = [
    {'num': 0, 'color': 'green'},
] + [
    {'num': i, 'color': 'red' if i in [
        1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'black'} for i in range(1, 37)
]

def random_chance(percent: float) -> bool:
    return random.random() < percent / 100

# Slots Game
@bot.tree.command(name="slots", description="Play the slots game")
async def slots(interaction: Interaction):
    spins = 10
    spin_delay = 0.35  # seconds

    embed = Embed(title="🎰 Slots Machine 🎰", description="Spinning...", color=0x5865F2)
    message = await interaction.response.send_message(embed=embed)
    # To edit we fetch message
    message = await interaction.original_response()

    result_symbols = []

    for i in range(spins):
        frame_symbols = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        await message.edit(embed=Embed(
            title="🎰 Slots Machine 🎰",
            description=f"| {frame_symbols[0]} | {frame_symbols[1]} | {frame_symbols[2]} |",
            color=0x5865F2,
        ).set_footer(text=f"Spinning {i+1}/{spins}..."))
        await asyncio.sleep(spin_delay)
        if i == spins - 1:
            result_symbols = frame_symbols

    # Determine win
    win = False
    payout = 0
    if result_symbols[0] == result_symbols[1] == result_symbols[2]:
        win = True
        if result_symbols[0] == '7️⃣':
            payout = 100
        elif result_symbols[0] == '⭐':
            payout = 50
        else:
            payout = 20
    elif (result_symbols[0] == result_symbols[1] or 
          result_symbols[1] == result_symbols[2] or 
          result_symbols[0] == result_symbols[2]):
        win = True
        payout = 5

    # Win % limitation: 40% chance to win
    if win and not random_chance(40):
        win = False
        payout = 0

    result_desc = f"| {result_symbols[0]} | {result_symbols[1]} | {result_symbols[2]} |\n\n"
    if win:
        result_desc += f"You won **{payout}** coins!"
        color = 0x43B581  # Green
    else:
        result_desc += "No win this time, try again!"
        color = 0xF04747  # Red

    await message.edit(embed=Embed(
        title="🎰 Slots Machine Result 🎰",
        description=result_desc,
        color=color
    ))

# Roulette Game
def get_roulette_color_hex(color: str) -> int:
    if color == "red":
        return 0xF44336
    elif color == "black":
        return 0x212121
    elif color == "green":
        return 0x4CAF50
    return 0x5865F2

@bot.tree.command(name="roulette", description="Play roulette")
@app_commands.describe(color="Color to bet on: red, black, green")
@app_commands.choices(color=[
    app_commands.Choice(name="Red", value="red"),
    app_commands.Choice(name="Black", value="black"),
    app_commands.Choice(name="Green", value="green"),
])
async def roulette(interaction: Interaction, color: app_commands.Choice[str]):
    bet_color = color.value
    embed = Embed(title="🎡 Roulette 🎡",
                  description=f"Spinning the wheel on **{bet_color}**...", color=0x5865F2)
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    spin_count = 12
    spin_speed = 0.3

    current_index = 0
    for _ in range(spin_count):
        number_obj = ROULETTE_NUMBERS[current_index]
        desc = (f"Number: **{number_obj['num']}** 🟥🟩🟦 Color: **{number_obj['color']}**\n\nSpinning...")
        await message.edit(embed=Embed(
            title="🎡 Roulette Spinning 🎡",
            description=desc,
            color=get_roulette_color_hex(number_obj['color'])
        ))
        await asyncio.sleep(spin_speed)
        current_index = (current_index + 1) % len(ROULETTE_NUMBERS)

    final_number_obj = ROULETTE_NUMBERS[(current_index - 1) % len(ROULETTE_NUMBERS)]

    win = False
    payout = 0
    if final_number_obj['color'] == bet_color:
        # 50% chance for win due to house edge
        win = random_chance(50)
        payout = 2 if win else 0

    desc = (f"Result: **{final_number_obj['num']}** (**{final_number_obj['color']}**)\n\n" +
            (f"You won **{payout}x** your bet!" if win else "You lost this round, try again!"))
    color_code = 0x43B581 if win else 0xF04747

    await message.edit(embed=Embed(
        title="🎡 Roulette Result 🎡",
        description=desc,
        color=color_code
    ))

# Blackjack Game

def create_deck():
    suits = ['♠', '♥', '♦', '♣']
    values = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
    return [{'suit': s, 'val': v} for s in suits for v in values]

def shuffle_deck(deck):
    array = deck[:]
    random.shuffle(array)
    return array

def card_value(card):
    if card['val'] == 'A':
        return 11
    if card['val'] in ['J','Q','K']:
        return 10
    return int(card['val'])

def hand_value(hand):
    val = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c['val'] == 'A')
    while val > 21 and aces > 0:
        val -= 10
        aces -= 1
    return val

def format_hand(hand):
    return ' '.join(f"{c['val']}{c['suit']}" for c in hand)

# Table data structures
class TableJoinView(discord.ui.View):
    def __init__(self, table_id: str):
        super().__init__(timeout=None)
        self.table_id = table_id

    @discord.ui.button(label="Join Table", style=discord.ButtonStyle.primary)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in player_to_table:
            await interaction.response.send_message("You're already at a table!", ephemeral=True)
            return

        table = active_tables.get(self.table_id)
        if not table or not table.active:
            await interaction.response.send_message("This table doesn't exist or is closed!", ephemeral=True)
            return

        # Move user to the table channel
        channel = bot.get_channel(table.channel_id)
        if channel:
            await interaction.user.move_to(channel)

        # Add player to table
        if table.add_player(interaction.user.id):
            player_to_table[interaction.user.id] = self.table_id
            await interaction.response.send_message(f"Joined table {self.table_id}! Welcome to the game!", ephemeral=True)
        else:
            await interaction.response.send_message("You're already at this table!", ephemeral=True)

@bot.tree.command(name="join-table", description="Join a blackjack table")
async def join_table(interaction: Interaction, table_id: str):
    # Defer the response first
    await interaction.response.defer(ephemeral=True)
    
    # Build the response message
    response_message = ""
    
    # Check if user is already at a table
    if interaction.user.id in player_to_table:
        response_message = "You're already at a table!"
    else:
        # Get the table
        table = active_tables.get(table_id)
        if not table or not table.active:
            response_message = "This table doesn't exist or is closed!"
        else:
            # Move user to the table channel
            channel = bot.get_channel(table.channel_id)
            if channel:
                # Send direct message with channel link
                await interaction.user.send(f"Join the table at: {channel.mention}")
            
            # Add player to table
            if table.add_player(interaction.user.id):
                player_to_table[interaction.user.id] = table_id
                response_message = f"Joined table {table_id}! Welcome to the game!"
            else:
                response_message = "You're already at this table!"
    
    # Send the final response
    await interaction.followup.send(response_message, ephemeral=True)

class BlackjackTable:
    def __init__(self, admin_id: int, table_id: str):
        self.admin_id = admin_id
        self.table_id = table_id  # Store the table ID
        self.players = set()  # Set of player IDs
        self.current_game = None  # Current game state
        self.deck = None
        self.dealer_hand = None
        self.active = True
        self.channel_id = None  # Store channel ID

    def add_player(self, player_id: int):
        # Check if player is already at any table
        if player_id in player_to_table:
            return False
            
        self.players.add(player_id)
        player_to_table[player_id] = self.table_id
        return True

    def remove_player(self, player_id: int):
        if player_id in self.players:
            self.players.remove(player_id)
            return True
        return False

    def is_player_at_table(self, player_id: int):
        return player_id in self.players

    def is_admin(self, user_id: int):
        return user_id == self.admin_id

# Maps table IDs to BlackjackTable objects
active_tables = {}

# Maps user IDs to table IDs (to enforce one table per player)
player_to_table = {}

class BlackjackView(discord.ui.View):
    def __init__(self, user_id: int, table: BlackjackTable):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.table = table

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("These buttons are not for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: Interaction, button: discord.ui.Button):
        # Get table and player's game state
        if self.user_id not in player_to_table:
            await interaction.response.send_message("You're not at a table!", ephemeral=True)
            return

        table_id = player_to_table[self.user_id]
        table = active_tables[table_id]
        if not table:
            await interaction.response.send_message("Table not found!", ephemeral=True)
            return

        game = table.current_game.get(self.user_id)
        if not game or game['finished']:
            await interaction.response.send_message("No active game found or game finished.", ephemeral=True)
            return

        game['hand'].append(table.deck.pop())
        player_val = hand_value(game['hand'])
        if player_val > 21:
            game['finished'] = True
            embed = generate_blackjack_embed({
                'dealer_hand': table.dealer_hand,
                'player_hand': game['hand'],
                'finished': True
            }, reveal_dealer=True, status_text="You busted! Dealer wins.")
            await game['message'].edit(embed=embed, view=None)
            await interaction.response.defer()
            return
        else:
            embed = generate_blackjack_embed({
                'dealer_hand': table.dealer_hand,
                'player_hand': game['hand'],
                'finished': False
            }, reveal_dealer=False, status_text="You drew a card. Your move.")
            await game['message'].edit(embed=embed)
            await interaction.response.defer()

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: Interaction, button: discord.ui.Button):
        # Get table and player's game state
        if self.user_id not in player_to_table:
            await interaction.response.send_message("You're not at a table!", ephemeral=True)
            return

        table_id = player_to_table[self.user_id]
        table = active_tables[table_id]
        if not table:
            await interaction.response.send_message("Table not found!", ephemeral=True)
            return

        game = table.current_game.get(self.user_id)
        if not game or game['finished']:
            await interaction.response.send_message("No active game found or game finished.", ephemeral=True)
            return

        game['stand'] = True

        # Dealer hits until 17+
        while hand_value(table.dealer_hand) < 17:
            table.dealer_hand.append(table.deck.pop())

        player_val = hand_value(game['hand'])
        dealer_val = hand_value(table.dealer_hand)

        # Check for busts first
        if player_val > 21:
            result_text = 'You busted! Dealer wins.'
        elif dealer_val > 21:
            result_text = 'Dealer busted! You win!'
        elif dealer_val > player_val:
            result_text = 'Dealer wins!'
        elif dealer_val < player_val:
            result_text = 'You win!'
        else:
            result_text = "It's a tie!"

        # Win% limitation: 50% chance official win payout
        payout = 0
        if 'win' in result_text.lower():
            if not random_chance(50):
                result_text = "House wins this time!"
            else:
                payout = 2

        embed = generate_blackjack_embed({
            'dealer_hand': table.dealer_hand,
            'player_hand': game['hand'],
            'finished': True
        }, reveal_dealer=True, status_text=result_text)
        game['finished'] = True
        await game['message'].edit(embed=embed, view=None)
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: Interaction, button: discord.ui.Button):
        # Get table and player's game state
        if self.user_id not in player_to_table:
            await interaction.response.send_message("You're not at a table!", ephemeral=True)
            return

        table_id = player_to_table[self.user_id]
        table = active_tables[table_id]
        if not table:
            await interaction.response.send_message("Table not found!", ephemeral=True)
            return

        game = table.current_game.get(self.user_id)
        if game:
            del table.current_game[self.user_id]
            if game['message']:
                await game['message'].edit(view=None)
        await interaction.response.defer()

def generate_blackjack_embed(game_state, reveal_dealer=False, status_text=''):
    dealer_hand = game_state['dealer_hand']
    player_hand = game_state['player_hand']
    if reveal_dealer:
        dealer_display = f"{format_hand(dealer_hand)} ({hand_value(dealer_hand)})"
    else:
        dealer_display = f"{dealer_hand[0]['val']}{dealer_hand[0]['suit']} ??"
    player_display = f"{format_hand(player_hand)} ({hand_value(player_hand)})"
    embed = Embed(title="♠️ Blackjack ♠️", color=0x5865F2)
    embed.add_field(name="Dealer Hand", value=dealer_display, inline=False)
    embed.add_field(name="Your Hand", value=player_display, inline=False)
    embed.add_field(name='\u200B', value=status_text, inline=False)
    return embed

@bot.tree.command(name="blackjack", description="Play blackjack")
async def blackjack(interaction: Interaction):
    if interaction.user.id not in player_to_table:
        await interaction.response.send_message("You're not at a table!", ephemeral=True)
        return

    table_id = player_to_table[interaction.user.id]
    table = active_tables[table_id]
    if not table.active:
        await interaction.response.send_message("This table is closed!", ephemeral=True)
        return

    if table.current_game and not table.current_game['finished']:
        await interaction.response.send_message("A game is already in progress!", ephemeral=True)
        return

    # Create new game state
    deck = shuffle_deck(create_deck())
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Check for natural blackjack
    player_val = hand_value(player_hand)
    dealer_val = hand_value(dealer_hand)
    
    if player_val == 21:
        if dealer_val == 21:
            result_text = "It's a tie! Both have natural blackjack!"
        else:
            result_text = "Natural blackjack! You win!"
            table.current_game = None
            await interaction.response.send_message(result_text, ephemeral=True)
            return

    # Initialize game state
    player_state = {
        'hand': player_hand,
        'stand': False,
        'finished': False,
        'message': None
    }
    
    table.current_game = {
        'deck': deck,
        'dealer_hand': dealer_hand,
        'player_hand': player_hand,  # Add this for compatibility with embed generator
        'dealer_value': hand_value(dealer_hand),
        'player_value': hand_value(player_hand),
        'players': {interaction.user.id: player_state},
        'finished': False,
        'message': None
    }

    # Create and send embed with buttons
    embed = generate_blackjack_embed(table.current_game, reveal_dealer=False)
    view = BlackjackView(interaction.user.id, table)
    message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    table.current_game['message'] = message
    table.current_game['players'][interaction.user.id]['message'] = message

@bot.tree.command(name="create-table", description="Create a new blackjack table (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def create_table(interaction: Interaction):
    # Defer the response first
    await interaction.response.defer(ephemeral=True)
    
    # Check if user is already at a table
    if interaction.user.id in player_to_table:
        await interaction.followup.send("You're already at a table!", ephemeral=True)
        return

    # Generate unique table ID
    table_id = f"table_{len(active_tables) + 1}"
    while table_id in active_tables:
        table_id = f"table_{len(active_tables) + 1}"

    # Create a temporary channel for the table
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True)
    }
    
    channel = await guild.create_text_channel(
        name=f"blackjack-{table_id}",
        overwrites=overwrites,
        reason="Blackjack table channel"
    )
    
    table = BlackjackTable(interaction.user.id, table_id)
    table.channel_id = channel.id
    active_tables[table_id] = table
    player_to_table[interaction.user.id] = table_id

    # Create and send join embed with button
    embed = discord.Embed(
        title=f"Blackjack Table {table_id}",
        description="Click the button below to join this table!",
        color=discord.Color.green()
    )
    embed.add_field(name="Admin", value=f"<@{interaction.user.id}>")
    embed.set_footer(text="Game will start when players join")

    view = TableJoinView(table_id)
    await interaction.followup.send(
        "Created a new blackjack table! Check the channel I created for the game.",
        ephemeral=True
    )
    await channel.send(embed=embed, view=view)

@bot.tree.command(name="leave-table", description="Leave your current table")
async def leave_table(interaction: Interaction):
    # Defer the response first
    await interaction.response.defer(ephemeral=True)
    
    if interaction.user.id not in player_to_table:
        await interaction.followup.send("You're not at a table!", ephemeral=True)
        return

    table_id = player_to_table[interaction.user.id]
    table = active_tables[table_id]
    
    if table.remove_player(interaction.user.id):
        del player_to_table[interaction.user.id]
        await interaction.followup.send(f"Left table {table_id}!", ephemeral=True)
    else:
        await interaction.followup.send("You weren't at this table!", ephemeral=True)

@bot.tree.command(name="close-table", description="Close your table (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def close_table(interaction: Interaction, table_id: str):
    # Defer the response first
    await interaction.response.defer(ephemeral=True)
    
    if table_id not in active_tables:
        await interaction.followup.send("That table doesn't exist!", ephemeral=True)
        return

    table = active_tables[table_id]
    if not table.is_admin(interaction.user.id):
        await interaction.followup.send("You're not the admin of this table!", ephemeral=True)
        return

    table.active = False
    
    # Notify all players
    for player_id in table.players.copy():
        await interaction.channel.send(f"<@{player_id}>", content="The table has been closed!")
        table.remove_player(player_id)
        if player_id in player_to_table:
            del player_to_table[player_id]

    await interaction.followup.send(f"Closed table {table_id}!", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def test_table_operations():
    # Create a test table
    test_admin_id = 123456
    test_player_id = 654321
    
    # Create table
    table_id = f"table_test"
    table = BlackjackTable(test_admin_id, table_id)
    active_tables[table_id] = table
    player_to_table[test_admin_id] = table_id
    
    # Test admin functions
    assert table.is_admin(test_admin_id) == True
    assert table.is_admin(test_player_id) == False
    
    # Test player functions
    assert table.add_player(test_player_id) == True
    assert table.is_player_at_table(test_player_id) == True
    assert table.add_player(test_player_id) == False  # Already added
    
    # Test removal
    assert table.remove_player(test_player_id) == True
    assert table.is_player_at_table(test_player_id) == False
    assert table.remove_player(test_player_id) == False  # Already removed
    
    # Test game state
    table.current_game = {
        test_admin_id: {
            'hand': [{'val': 'A', 'suit': '♥'}, {'val': 'K', 'suit': '♥'}],
            'stand': False,
            'finished': False,
            'message': None
        }
    }
    
    # Test natural blackjack
    player_val = hand_value(table.current_game[test_admin_id]['hand'])
    assert player_val == 21
    
    print("All table operation tests passed!")

async def test_multi_table():
    # Create two tables
    admin1 = 111111
    admin2 = 222222
    player1 = 333333
    player2 = 444444
    
    # Create tables
    table1_id = "table_1"
    table2_id = "table_2"
    
    table1 = BlackjackTable(admin1, table1_id)
    table2 = BlackjackTable(admin2, table2_id)
    
    active_tables[table1_id] = table1
    active_tables[table2_id] = table2
    
    player_to_table[admin1] = table1_id
    player_to_table[admin2] = table2_id
    
    # Test players can't join multiple tables
    assert table1.add_player(player1) == True
    assert table2.add_player(player1) == False  # Already at table
    
    # Test players can join different tables
    assert table2.add_player(player2) == True
    
    # Test table closure
    table1.active = False
    assert table1.active == False
    assert table2.active == True
    
    print("All multi-table tests passed!")

# Run tests
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_table_operations())
    asyncio.run(test_multi_table())

bot.run('MTM4NDcxNTY5MDQ0Mjc1MjA4MA.GdqzBL.k0_izJs-DVi5ct_Y5qyjdq8SwVM__9IQivIkbo')

