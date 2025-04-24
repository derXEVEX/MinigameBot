import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import re
import asyncio
import random
import time
from discord.ui import Button, View




intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

LEVELS_FILE = "levels.json"
LEVEL_ROLES = {
    5: 1359444763216052224,
    10: 1359444787257675838,
    20: 1359444810502508604,
    30: 1359444833978290236
}

XP_COOLDOWN = 0
LEVEL_UP_CHANNEL_ID = 1359445179651850412
xp_cooldowns = {}



def load_level_data():
    if not os.path.exists(LEVELS_FILE) or os.path.getsize(LEVELS_FILE) == 0:
        return {}
    with open(LEVELS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_level_data(data):
    with open(LEVELS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_level_info(xp):
    level = 1
    xp_needed = 5
    total_needed = 0
    while xp >= total_needed + xp_needed:
        total_needed += xp_needed
        level += 1
        xp_needed += 5
    current_xp = xp - total_needed
    to_next_level = xp_needed - current_xp
    return level, current_xp, to_next_level

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)
    print(f"{bot.user} ist online!")

# ===== XP System =================0================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    now = time.time()

    if user_id in xp_cooldowns and now - xp_cooldowns[user_id] < XP_COOLDOWN:
        return

    data = load_level_data()
    if user_id not in data:
        data[user_id] = {"xp": 0}

    data[user_id]["xp"] += 1
    xp_cooldowns[user_id] = now

    old_level, _, _ = get_level_info(data[user_id]["xp"] - 1)
    new_level, _, _ = get_level_info(data[user_id]["xp"])

    if new_level > old_level:
        channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        await channel.send(f"🎉 {message.author.mention} ist nun Level {new_level}!")

    save_level_data(data)
    await bot.process_commands(message)

@tree.command(name="getlevel", description="Zeigt das Level und XP eines Benutzers")
@app_commands.describe(user="Der Benutzer")
async def getlevel(interaction: discord.Interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    user_id = str(user.id)
    data = load_level_data()
    if user_id not in data:
        await interaction.response.send_message(f"{user.mention} hat noch keine XP!", ephemeral=False)
        return
    xp = data[user_id]["xp"]
    level, current_xp, to_next = get_level_info(xp)
    await interaction.response.send_message(
        f"📊 {user.mention} ist Level {level}\n"
        f"🔹 XP: {current_xp} / {current_xp + to_next} (Noch {to_next} XP bis Level {level+1})",
        ephemeral=False
    )

@tree.command(name="xp", description="XP vergeben oder entfernen")
@app_commands.describe(user="Der User", amount="XP (positiv oder negativ)")
async def xp(interaction: discord.Interaction, user: discord.User, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Keine Berechtigung", ephemeral=True)
        return
    user_id = str(user.id)
    data = load_level_data()
    if user_id not in data:
        data[user_id] = {"xp": 0}
    old_level = get_level_info(data[user_id]["xp"])[0]
    data[user_id]["xp"] += amount
    if data[user_id]["xp"] < 0:
        data[user_id]["xp"] = 0
    new_level = get_level_info(data[user_id]["xp"])[0]
    save_level_data(data)
    member = interaction.guild.get_member(user.id)
    if member:
        await update_user_role(member, new_level)
    await interaction.response.send_message(
        f"✅ {user.mention} hat jetzt {data[user_id]['xp']} XP (Level {new_level})",
        ephemeral=False
    )

@tree.command(name="leaderboard", description="Top 10 User levels")
async def leaderboard(interaction: discord.Interaction):
    data = load_level_data()
    if not data:
        await interaction.response.send_message("Keine Einträge vorhanden")
        return
    leaderboard = sorted(data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Leaderboard", description="Top 10", color=discord.Color.gold())
    for i, (uid, entry) in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(int(uid))
        level, current_xp, to_next = get_level_info(entry["xp"])
        embed.add_field(name=f"#{i} {user.name}", value=f"📈 Level **{level}**\n🔹 **{entry['xp']} XP**", inline=False)
    embed.set_footer(text="Level System 🤖")
    await interaction.response.send_message(embed=embed)

@tree.command(name="levelinfo", description="Level System Hilfe")
async def levelinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="📘 XP Guide", color=discord.Color.blue())
    embed.add_field(name="🇩🇪 Wie funktioniert das XP-System?", value=(
        "• Du bekommst XP für Nachrichten 💬\n"
        "• Längere Nachrichten geben **mehr XP** ✨\n"
        "• Bilder, Links oder Anhänge geben **zusätzliche XP** 🖼️🔗\n"
        "• **Spam zählt nicht** ❌\n"
        "• XP haben einen Cooldown ⏳\n"
        "• Ab bestimmten Leveln bekommst du **besondere Rollen** 🏅"
    ), inline=False)
    await interaction.response.send_message(embed=embed)

async def update_user_role(member: discord.Member, new_level: int):
    guild = member.guild
    role_to_add = None
    for level, role_id in sorted(LEVEL_ROLES.items()):
        if new_level >= level:
            role_to_add = guild.get_role(role_id)
    for level, role_id in LEVEL_ROLES.items():
        role = guild.get_role(role_id)
        if role and role != role_to_add and role in member.roles:
            await member.remove_roles(role)
    if role_to_add and role_to_add not in member.roles:
        await member.add_roles(role_to_add)

active_games = {}

class MiningButton(Button):
    def __init__(self, x, y, player: discord.User):
        super().__init__(emoji="⬛", row=y, style=discord.ButtonStyle.secondary)
        self.x = x
        self.y = y
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("❌ Du darfst dieses Spiel nicht spielen!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        game = active_games.get(user_id)

        if not game:
            await interaction.response.send_message("❌ Du hast kein aktives Spiel!", ephemeral=True)
            return

        if (self.x, self.y) in game["clicked"]:
            await interaction.response.send_message("⛏️ Dieses Feld hast du schon angeklickt!", ephemeral=True)
            return

        game["clicked"].add((self.x, self.y))

        if (self.x, self.y) in game["bombs"]:
            self.emoji = discord.PartialEmoji(name="mcTNT", id=1359492693516091554)
            self.style = discord.ButtonStyle.danger

            for child in self.view.children:
                child.disabled = True

            await interaction.response.edit_message(
                content="💥 Boom! Du hast eine Bombe getroffen! Kein XP gewonnen.",
                view=self.view
            )
            del active_games[user_id]
            return

        self.emoji = discord.PartialEmoji(name="diamond", id=1359492674331213965)
        self.style = discord.ButtonStyle.success
        game["score"] += game["xp_per_diamond"]

        await interaction.response.edit_message(view=self.view)

# TIC TAC TOE MINIGAME _--------------------------------------------------------------------

class TicTacToeGame:
    def __init__(self, player1, player2):
        self.player1 = player1
        self.player2 = player2
        self.turn = player1  # Player1 beginnt
        self.board = [' '] * 9  # Ein Tic-Tac-Toe-Board (9 Felder)
        self.view = View(timeout=None)
        self.message = None  # Platzhalter für die Nachricht

    def update_board(self, position, symbol):
        self.board[position] = symbol

    def is_winner(self, symbol):
        win_conditions = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Reihen
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Spalten
            [0, 4, 8], [2, 4, 6]              # Diagonalen
        ]
        for condition in win_conditions:
            if all(self.board[i] == symbol for i in condition):
                return True
        return False

    def is_draw(self):
        return ' ' not in self.board  # Wenn keine leeren Felder mehr da sind

    def get_board_display(self):
        return f"{self.board[0]} | {self.board[1]} | {self.board[2]}\n" \
               f"---------\n" \
               f"{self.board[3]} | {self.board[4]} | {self.board[5]}\n" \
               f"---------\n" \
               f"{self.board[6]} | {self.board[7]} | {self.board[8]}"

active_ttt_games = {}

async def tictactoe_command(interaction: discord.Interaction, opponent: discord.User):
    # Stelle sicher, dass der Befehl von einem Benutzer kommt
    if interaction.user == opponent:
        await interaction.response.send_message("❌ Du kannst nicht gegen dich selbst spielen!", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    if user_id in active_ttt_games:
        await interaction.response.send_message("❌ Du hast bereits ein aktives Tic-Tac-Toe-Spiel!", ephemeral=True)
        return

    game = TicTacToeGame(interaction.user, opponent)
    active_ttt_games[user_id] = game

    game.message = await interaction.response.send_message(
        f"🎮 Tic-Tac-Toe-Spiel gestartet! {opponent.mention} ist dran.",
        view=game.view
    )

    async def timeout_handler():
        await asyncio.sleep(180)  # 3 Minuten warten
        if user_id in active_ttt_games:
            for child in game.view.children:
                child.disabled = True
            await interaction.edit_original_response(
                content="⏰ Zeit abgelaufen! Das Spiel ist beendet, du kannst nichts mehr anklicken.",
                view=game.view
            )
            del active_ttt_games[user_id]

    await interaction.response.send_message(
        "Das Spiel wird automatisch nach 3 Minuten beendet, falls keine Aktion erfolgt.",
        ephemeral=True
    )

    asyncio.create_task(timeout_handler())

def game_button_callback(game: TicTacToeGame, button: Button):
    async def callback(interaction: discord.Interaction):
        if interaction.user != game.turn:
            await interaction.response.send_message("❌ Es ist nicht dein Zug!", ephemeral=True)
            return

        if game.board[int(button.custom_id)] != ' ':
            await interaction.response.send_message("❌ Dieses Feld ist bereits besetzt!", ephemeral=True)
            return

        symbol = 'X' if game.turn == game.player1 else 'O'
        game.update_board(int(button.custom_id), symbol)

        if game.is_winner(symbol):
            await interaction.response.send_message(f"🎉 {game.turn.mention} hat gewonnen!", ephemeral=True)
            await interaction.edit_original_response(
                content=f"Spiel beendet! {game.turn.mention} gewinnt!\n\n{game.get_board_display()}",
                view=game.view
            )
            del active_ttt_games[str(game.turn.id)]
            return

        if game.is_draw():
            await interaction.response.send_message("Unentschieden! Es gibt keinen Gewinner.", ephemeral=True)
            await interaction.edit_original_response(
                content=f"Spiel beendet! Unentschieden!\n\n{game.get_board_display()}",
                view=game.view
            )
            del active_ttt_games[str(game.turn.id)]
            return

        game.turn = game.player2 if game.turn == game.player1 else game.player1
        await interaction.edit_original_response(
            content=f"🎮 Tic-Tac-Toe-Spiel läuft! Jetzt ist {game.turn.mention} dran.\n\n{game.get_board_display()}",
            view=game.view
        )

    return callback
@bot.tree.command(name="tictactoe", description="Starte ein Tic-Tac-Toe-Spiel gegen einen anderen Spieler!")
@app_commands.describe(opponent="Der Spieler, gegen den du Tic-Tac-Toe spielen möchtest")
async def tictactoe(interaction: discord.Interaction, opponent: discord.User):
    await tictactoe_command(interaction, opponent)





bot.run("TOKEN")
