import discord
from discord.ext import commands
import json
import requests
import random
import string
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime, timedelta
import asyncio
from discord.utils import utcnow
from config import BOT_TOKEN, STEAM_API_KEY, BOT_VERSION
from info import info
from discord.ext import tasks


intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None, case_insensitive=True)

DATA_FILE = 'users_data.json'

GUILDS_FILE = 'guilds.json'
MUTES_FILE = 'mutes.json'

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def update_guild_data(guild):
    data = load_json(GUILDS_FILE)
    guild_id = str(guild.id)
    if guild_id not in data:
        data[guild_id] = {
            "name": guild.name,
            "member_count": guild.member_count,
            "messages": 0
        }
    save_json(GUILDS_FILE, data)

def increment_guild_messages(guild_id):
    data = load_json(GUILDS_FILE)
    gid = str(guild_id)
    if gid not in data:
        return
    data[gid]["messages"] += 1
    save_json(GUILDS_FILE, data)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_mutes():
    return load_json(MUTES_FILE)

def save_mutes(data):
    save_json(MUTES_FILE, data)

async def apply_mute(member, duration_seconds, reason):
    muted_role = discord.utils.get(member.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await member.guild.create_role(name="Muted")
        for channel in member.guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False)

    await member.add_roles(muted_role, reason=reason)

    await asyncio.sleep(duration_seconds)

    # Проверка на актуальность
    mutes = load_mutes()
    guild_id = str(member.guild.id)
    user_id = str(member.id)

    if guild_id in mutes and user_id in mutes[guild_id]:
        del mutes[guild_id][user_id]
        save_mutes(mutes)
        await member.remove_roles(muted_role, reason="Mute expired")

def register_user(user):
    data = load_data()
    user_id = str(user.id)

    if user_id not in data:
        data[user_id] = {
            "first_name": user.name,
            "last_name": None,
            "username": user.name,
            "steam": None,
            "twitch": None,

            "wallet_balance": 100,
            "bank_balance": 0,
            "transaction_history": [],

            "clan": None,
            "bot_lang": "ru",
            "bot_theme": 0,

            "level": 1,
            "xp": 0,
            "rank_title": "Новичок",

            "casino_stats": {
                "games_played": 0,
                "games_won": 0,
                "games_lost": 0,
                "total_winnings": 0,
                "total_losses": 0,
            },

            "daily_activity": {
                "commands_used": 0,
                "messages_sent": 0,
                "games_played": 0,
                "last_active": None,
            },
            "weekly_activity": {
                "messages_sent": 0,
            },
            "achievements": [],
            "last_claim": None,
        }
    else:
        data[user_id]["daily_activity"]["messages_sent"] += 1
        data[user_id]["daily_activity"]["last_active"] = datetime.utcnow().isoformat()

    save_data(data)


def extract_steam_id(profile_url):
    if "steamcommunity.com/profiles/" in profile_url:
        return profile_url.split("/")[-1]
    elif "steamcommunity.com/id/" in profile_url:
        custom_id = profile_url.split("/")[-1]
        r = requests.get(
            f"http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?key={STEAM_API_KEY}&vanityurl={custom_id}"
        )
        res = r.json()
        if res["response"]["success"] == 1:
            return res["response"]["steamid"]
    return None


def get_steam_summary(steam_id):
    r = requests.get(
        f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}"
    )
    data = r.json()
    if "players" in data["response"] and data["response"]["players"]:
        return data["response"]["players"][0]
    return None

@tasks.loop(minutes=1)
async def reset_activity():
    moscow = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow)

    if now.hour == 0 and now.minute == 0:
        with open("users_data.json", "r") as f:
            users_data = json.load(f)

        for user_id in users_data:
            users_data[user_id]["daily_activity"] = {
                "commands_used": 0,
                "messages_sent": 0
            }

            if now.weekday() == 0:  
                users_data[user_id]["weekly_activity"] = {
                    "commands_used": 0,
                    "messages_sent": 0
                }

        with open("users_data.json", "w") as f:
            json.dump(users_data, f, indent=4)

        print("✅ Статистика сброшена: daily" + (" и weekly" if now.weekday() == 0 else ""))

from discord.ui import Select, View, select, Button

@bot.command(name="help")
async def custom_help(ctx):
    embed = discord.Embed(
        title="🧠 Помощь по VelionBot",
        description="Добро пожаловать! Вот список доступных команд:",
        color=discord.Color.green()
    )

    embed.add_field(name="👤 Профиль", value="`!profile` — Показать твой профиль", inline=False)
    embed.add_field(name="🎮 Привязки", value="`!bind_steam <url>` — Привязать Steam\n`!bind_twitch <url>` — Привязать Twitch", inline=False)
    embed.add_field(name="🔒 Модерация", value="`!mute @пользователь время причина` — Выдать тайм-аут\n`!unmute @пользователь` — Снять тайм-аут", inline=False)
    embed.add_field(name="📊 Статистика", value="`!serverinfo` — Информация о сервере", inline=False)
    embed.set_footer(text="VelionBot | Введи !help для повторного вызова помощи")

    view = View()
    view.add_item(Button(label="🌐 Сайт", url="https://velion.onrender.com"))
    view.add_item(Button(label="🌐 ТГ версия", url="https://veliongamesbot.t.me"))

    await ctx.send(embed=embed, view=view)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = message.author
    user_id = str(user.id)

    data = load_data()
    if user_id not in data:
        register_user(user)
        data = load_data()

    user_data = data[user_id]

    user_data["xp"] += 0.1

    level = user_data["level"]
    xp = user_data["xp"]

    if xp >= level * 100:
        user_data["level"] += 1
        user_data["xp"] = 0

    if "daily_activity" not in user_data:
        user_data["daily_activity"] = {}

    user_data["daily_activity"]["messages_sent"] = user_data["daily_activity"].get("messages_sent", 0) + 1

    if message.content.startswith("!"):
        user_data["daily_activity"]["commands_used"] = user_data["daily_activity"].get("commands_used", 0) + 1

    save_data(data)
    update_guild_data(message.guild)
    increment_guild_messages(message.guild.id)


    await bot.process_commands(message)


# модераторская хуйня
@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, time: str, *, reason: str = "Без причины"):
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = time[-1]
        number = int(time[:-1])
        seconds = number * units[unit]
    except:
        embed = discord.Embed(
            title="❌ Неверный формат времени",
            description="Пример: `10m`, `2h`, `1d`, `30s`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    until = utcnow() + timedelta(seconds=seconds)
    await member.timeout(until, reason=reason)

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    mutes = load_mutes()

    if guild_id not in mutes:
        mutes[guild_id] = {}

    mutes[guild_id][user_id] = {
        "reason": reason,
        "until": until.isoformat()
    }

    save_mutes(mutes)

    embed = discord.Embed(
        title="🔇 Тайм-аут выдан",
        description=f"{member.mention} замучен на `{time}`",
        color=discord.Color.green()
    )
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.set_footer(text=f"Модератор: {ctx.author}", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None, reason="Размут")

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    mutes = load_mutes()

    if user_id not in data:
        register_user(user)
        data = load_data()

    if guild_id in mutes and user_id in mutes[guild_id]:
        del mutes[guild_id][user_id]
        save_mutes(mutes)

    embed = discord.Embed(
        title="🔈 Размут выполнен",
        description=f"{member.mention} теперь снова может говорить.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Модератор: {ctx.author}", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Без причины"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="🔨 Пользователь забанен",
            description=f"{member.mention} был **забанен**.",
            color=discord.Color.red()
        )
        embed.add_field(name="Причина", value=reason, inline=False)
        embed.set_footer(text=f"Модератор: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Ошибка при бане",
            description=f"Не удалось забанить {member.mention}\n`{e}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)

    try:
        await ctx.guild.unban(user)

        embed = discord.Embed(
            title="🔓 Пользователь разбанен",
            description=f"{user.mention} (`{user_id}`) был **разбанен**.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Модератор: {ctx.author}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    except discord.NotFound:
        embed = discord.Embed(
            title="❌ Пользователь не в бан-листе",
            description=f"Пользователь с ID `{user_id}` не найден в списке банов.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        embed = discord.Embed(
            title="❌ Ошибка при разбане",
            description=f"Не удалось разбанить пользователя `{user_id}`\n`{e}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Без причины"):
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="🥾 Пользователь кикнут",
            description=f"{member.mention} был **кикнут** с сервера.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Причина", value=reason, inline=False)
        embed.set_footer(text=f"Модератор: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Ошибка при кике",
            description=f"Не удалось кикнуть {member.mention}\n`{e}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command()
async def bind_steam(ctx, profile_url: str = None):
    if profile_url is None:
        embed = discord.Embed(
            title="Привязка Steam-профиля",
            description="🟢 Укажите ссылку на свой профиль Steam.\n\nПример:\n`/bind_steam https://steamcommunity.com/id/yourname`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        return
    
    user_id = str(ctx.author.id)
    data = load_data()


    if "steamcommunity.com" not in profile_url:
        embed = discord.Embed(
            title="Неверная ссылка",
            description="🔗 Укажите корректную ссылку на профиль Steam (https://steamcommunity.com/...).",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        return

    if user_id not in data:
        register_user(ctx.author)
        data = load_data() 

    data[user_id]["steam"] = profile_url
    save_data(data)

    embed = discord.Embed(
        title="✅ Профиль привязан",
        description=f"Ваш Steam-профиль успешно привязан:\n{profile_url}",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    bot_avatar = bot.user.avatar.url if bot.user.avatar else None

    embed.set_author(
        name="VelionBot • Интеграции",
        icon_url=bot_avatar
    )

    embed.set_footer(text="©VelionTeam - 2025")
    await ctx.send(embed=embed)

@bot.command(name='bind_twitch')
async def bind_twitch(ctx, twitch_url=None):
    user_id = str(ctx.author.id)
    data = load_data()

    if user_id not in data:
        register_user(ctx.author)
        data = load_data()

    if not twitch_url:
        embed = discord.Embed(
            title="❌ Привязка Twitch",
            description="Пожалуйста, укажи ссылку на твой Twitch-профиль.\n\nПример: `/bind_twitch https://twitch.tv/твой_ник`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not twitch_url.startswith("https://twitch.tv/") and not twitch_url.startswith("https://www.twitch.tv/"):
        embed = discord.Embed(
            title="❌ Неверная ссылка",
            description="Убедись, что ты указал **полную ссылку** на Twitch.\n\nПример: `https://twitch.tv/твой_ник`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    data[user_id]['twitch'] = twitch_url
    save_data(data)

    embed = discord.Embed(
        title="✅ Twitch успешно привязан!",
        description=f"Твой профиль: [смотреть]({twitch_url})",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    bot_avatar = bot.user.avatar.url if bot.user.avatar else None

    embed.set_author(
        name="VelionBot • Интеграции",
        icon_url=bot_avatar
    )

    embed.set_footer(text="©VelionTeam - 2025")

    await ctx.send(embed=embed)


@bot.command()
async def profile(ctx):
    user_id = str(ctx.author.id)
    data = load_data()

    if user_id not in data:
        register_user(ctx.author)
        data = load_data()

    with open("users_data.json", "r") as f:
        users_data = json.load(f)

    user_data = data[user_id]
    daily = user_data.get("daily_activity", {})
    
    level = user_data.get("level", 1)
    xp = user_data.get("xp", 0)
    next_level_xp = level * 100
    progress = int((xp / next_level_xp) * 10)
    progress_bar = "🟩" * progress + "⬜" * (10 - progress)

    wallet = user_data.get("wallet_balance", 0)
    bank = user_data.get("bank_balance", 0)

    steam = user_data.get("steam", "Не привязано")
    twitch = user_data.get("twitch", "Не привязано")
    daily_data = users_data.get(user_id, {}).get("daily_activity", {})
    commands_used = daily_data.get("commands_used", 0)
    messages_sent = daily_data.get("messages_sent", 0)
    

    embed = discord.Embed(
        title=f"👤 Профиль {ctx.author.display_name}",
        description=f"`{user_data.get('username', ctx.author.name)}`",
        color=discord.Color.green()
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    embed.add_field(
        name="📈 Уровень и опыт",
        value=(
            f"Уровень: `{level}`\n"
            f"Опыт: `{xp} / {next_level_xp}`\n"
            f"{progress_bar}"
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Финансы",
        value=(
            f"Кошелёк: `{wallet}` 💸\n"
            f"Банк: `{bank}` 🏦"
        ),
        inline=False
    )

    embed.add_field(
        name="🔗 Привязки",
        value=(
            f"{'[Steam](' + steam + ')' if steam and steam != 'Не привязано' else 'Steam: Не привязано'}\n"
            f"{'[Twitch](' + twitch + ')' if twitch and twitch != 'Не привязано' else 'Twitch: Не привязано'}"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Активность",
        value=(
            f"Сообщений за день: `{messages_sent}`\n"
            f"Команд использовано: `{commands_used}`"
        ),
        inline=False
    )
    bot_avatar = bot.user.avatar.url if bot.user.avatar else None

    embed.set_author(
        name="VelionBot • Профиль",
        icon_url=bot_avatar
    )

    embed.set_footer(text="©VelionTeam - 2025")

    await ctx.send(embed=embed)

@bot.command()
async def about(ctx):
    embed = discord.Embed(
        title=f"🤖 О боте — {info.BOTNAME}",
        description=info.DESCRIPTION,
        color=discord.Color(0x55ff99)
    )

    embed.add_field(name="👨‍💻 Разработчик", value=info.AUTHOR, inline=True)
    embed.add_field(name="🛠 Версия", value=info.VERSION, inline=True)
    embed.add_field(name="📅 Обновление", value=info.LAST_UPDATE, inline=True)

    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else "")
    embed.set_footer(text="Спасибо за использование Velion Bot!")
    bot_avatar = bot.user.avatar.url if bot.user.avatar else None

    embed.set_author(
        name="VelionBot • О боте",
        icon_url=bot_avatar
    )

    embed.set_footer(text="©VelionTeam - 2025")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="🌐 Сайт", url=info.WEBSITE))
    view.add_item(discord.ui.Button(label="💻 Основной сервер", url=info.SUPPORT_SERVER))
    view.add_item(discord.ui.Button(label="🆘 Поддержка", url=info.SUPPORT_SERVER))

    await ctx.send(embed=embed, view=view)
    
@bot.command()
async def server(ctx):
    guild = ctx.guild
    embed = discord.Embed(
        title=guild.name,
        description="Информация о сервере",
        color=discord.Color.from_rgb(88, 255, 150)  # светло-зелёный VelionBot
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)

    embed.add_field(name="🆔 ID сервера", value=guild.id, inline=True)
    embed.add_field(name="👑 Владелец", value=guild.owner.mention, inline=True)
    embed.add_field(name="👥 Участников", value=guild.member_count, inline=True)
    embed.add_field(name="📅 Создан", value=guild.created_at.strftime("%d.%m.%Y %H:%M:%S"), inline=False)
    embed.add_field(name="💬 Кол-во каналов", value=f"Текст: {len(guild.text_channels)}, Голос: {len(guild.voice_channels)}", inline=True)
    embed.add_field(name="🌍 Регион", value=guild.preferred_locale or "Не указан", inline=True)

    embed.set_author(
        name="VelionBot • Инфо о сервере",
        icon_url=bot.user.avatar.url if bot.user.avatar else None
    )
    embed.set_footer(text="© VelionTeam - 2025")

    await ctx.send(embed=embed)

@bot.command(name="stats")
async def stats(ctx):
    total_users = sum(guild.member_count for guild in bot.guilds)
    total_guilds = len(bot.guilds)
    total_commands = len(bot.commands)

    embed = discord.Embed(
        title="📊 Статистика VelionBot",
        description=f"Общее количество серверов: **{total_guilds}**\n"
                    f"Пользователей: **{total_users}**\n"
                    f"Команд: **{total_commands}**",
        color=discord.Color.from_rgb(88, 255, 152)
    )
    embed.set_author(name="VelionBot • Статистика", icon_url=bot.user.avatar.url)
    embed.set_footer(text="© VelionTeam - 2025")
    await ctx.send(embed=embed)

@bot.command(name="invite")
async def invite(ctx):
    invite_url = f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(
        title="🔗 Пригласить VelionBot",
        description=f"[Нажмите здесь, чтобы пригласить бота на сервер]({invite_url})",
        color=discord.Color.from_rgb(88, 255, 152)
    )
    embed.set_author(name="VelionBot • Приглашение", icon_url=bot.user.avatar.url)
    embed.set_footer(text="© VelionTeam - 2025")
    await ctx.send(embed=embed)

@bot.command(name="support")
async def support(ctx):
    support_link = "https://discord.gg/VelionSupport"  # замени на свою ссылку
    embed = discord.Embed(
        title="🛠️ Сервер Поддержки VelionBot",
        description=f"[Перейти на сервер поддержки]({support_link})",
        color=discord.Color.from_rgb(88, 255, 152)
    )
    embed.set_author(name="VelionBot • Поддержка", icon_url=bot.user.avatar.url)
    embed.set_footer(text="© VelionTeam - 2025")
    await ctx.send(embed=embed)

@bot.command(name="daily")
async def daily(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)

    with open("users_data.json", "r") as f:
        users_data = json.load(f)

    daily_data = users_data.get(user_id, {}).get("daily_activity", {})
    commands_used = daily_data.get("commands_used", 0)
    messages_sent = daily_data.get("messages_sent", 0)

    embed = discord.Embed(
        title="📅 Ежедневная активность",
        description=f"Пользователь {member.mention} сегодня:\n"
                    f"🟢 Использовал команд: **{commands_used}**\n"
                    f"💬 Отправил сообщений: **{messages_sent}**",
        color=discord.Color.from_rgb(88, 255, 152)
    )
    embed.set_author(name="VelionBot • Активность", icon_url=bot.user.avatar.url)
    embed.set_footer(text="© VelionTeam - 2025")
    await ctx.send(embed=embed)

@bot.command(name="top")
async def top_users(ctx):
    with open("users_data.json", "r", encoding="utf-8") as f:
        users_data = json.load(f)

    user_id = str(member.id)
    
    if user_id not in data:
        register_user(user)
        data = load_data()

    leaderboard = sorted(
        users_data.items(),
        key=lambda x: x[1].get("total_activity", {}).get("messages_sent", 0),
        reverse=True
    )

    embed = discord.Embed(
        title="🏆 Топ 10 пользователей VelionBot",
        description="По количеству сообщений за всё время",
        color=discord.Color.from_rgb(100, 255, 100) 
    )
    embed.set_author(
        name="VelionBot • Топ пользователей",
        icon_url=bot.user.avatar.url if bot.user.avatar else discord.Embed.Empty
    )
    embed.set_footer(text="© VelionTeam - 2025")

    for idx, (user_id, data) in enumerate(leaderboard[:10], start=1):
        user = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
        messages = data.get("total_activity", {}).get("messages_sent", 0)
        embed.add_field(
            name=f"{idx}. {user.name if user else 'Неизвестный пользователь'}",
            value=f"📨 Сообщений: `{messages}`",
            inline=False
        )

    await ctx.send(embed=embed)

# VelionBank

def load_bank_data():
    if not os.path.exists("bank.json"):
        with open("bank.json", "w") as f:
            json.dump({}, f)
    with open("bank.json", "r") as f:
        return json.load(f)

def save_bank_data(data):
    with open("bank.json", "w") as f:
        json.dump(data, f, indent=4)

def generate_bank_id():
    return f"VEL-{random.randint(100000, 999999)}"

def generate_card_number():
    return f"VISA {random.randint(4000,4999)} {random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"

def get_limit(card_type):
    return {
        "Basic": 10000,
        "Red": 50000,
        "Green": 100000
    }[card_type]

@bot.command(aliases=["vb", "vb_info"])
async def velionbank(ctx):
    user_id = str(ctx.author.id)
    bank_data = load_bank_data()

    if user_id in bank_data:
        data = bank_data[user_id]
        embed = discord.Embed(
            title="💳 VelionBank — Профиль",
            description=f"**Держатель:** {data['holder']}\n"
                        f"**Логин:** `{data['username']}`\n"
                        f"**Тип карты:** {data['card_type']}\n"
                        f"**Номер карты:** `{data['card']}`\n"
                        f"**Банк-ID:** `{data['bank_id']}`\n"
                        f"**Баланс:** 💠 `{data['balance']} К-Э`\n"
                        f"**Лимит:** `{data['limit']} К-Э`",
            color=discord.Color.green()
        )
        embed.set_author(name="VelionBank • Ваш счёт", icon_url=ctx.bot.user.avatar.url)
        embed.set_footer(text="© VelionTeam - 2025")
        embed.set_thumbnail(url="attachment://VelionBank.png")
        file = discord.File("imgs/VelionBank.png", filename="VelionBank.png")

        class BankButtons(View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="Пополнить", style=discord.ButtonStyle.green, custom_id="deposit_button")
            async def deposit(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message("💸 Введите сумму для пополнения:", ephemeral=True)

                def check(msg):
                    return msg.author == interaction.user and msg.channel == interaction.channel

                try:
                    msg = await bot.wait_for("message", check=check, timeout=30.0)
                    amount = int(msg.content)
                    data = load_data()
                    bank = load_bank_data()

                    if data.get(user_id, {}).get("wallet_balance", 0) < amount:
                        return await interaction.followup.send("❌ Недостаточно средств в кошельке.", ephemeral=True)

                    data[user_id]["wallet_balance"] -= amount
                    bank[user_id]["balance"] += amount
                    save_data(data)
                    save_bank_data(bank)
                    await interaction.followup.send(f"✅ Переведено {amount} К-Э в банк.", ephemeral=True)

                except:
                    await interaction.followup.send("❌ Время ожидания истекло или введено неверное значение.", ephemeral=True)

            @discord.ui.button(label="Вывести", style=discord.ButtonStyle.blurple, custom_id="withdraw_button")
            async def withdraw(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message("🏦 Введите сумму для вывода:", ephemeral=True)

                def check(msg):
                    return msg.author == interaction.user and msg.channel == interaction.channel

                try:
                    msg = await bot.wait_for("message", check=check, timeout=30.0)
                    amount = int(msg.content)
                    data = load_data()
                    bank = load_bank_data()

                    if bank.get(user_id, {}).get("balance", 0) < amount:
                        return await interaction.followup.send("❌ Недостаточно средств в банке.", ephemeral=True)

                    bank[user_id]["balance"] -= amount
                    data[user_id]["wallet_balance"] += amount
                    save_data(data)
                    save_bank_data(bank)
                    await interaction.followup.send(f"✅ Выведено {amount} К-Э на кошелёк.", ephemeral=True)

                except:
                    await interaction.followup.send("❌ Время ожидания истекло или введено неверное значение.", ephemeral=True)

        await ctx.send(embed=embed, view=BankButtons(), file=file)

    else:
        embed = discord.Embed(
            title="🏦 VelionBank — Добро пожаловать!",
            description="💠 **VelionBank** — надёжный банк Этерии, предоставляющий кристально чистый сервис 💚\n"
                        "Создайте счёт, выбрав подходящую карту:\n\n"
                        "💳 **Basic** — Бесплатно | Лимит: 10000 К-Э\n"
                        "💼 **Red** — 500 К-Э | Лимит: 50000 К-Э\n"
                        "👑 **Green** — 1500 К-Э | Лимит: 100000 К-Э\n\n"
                        "Нажмите кнопку ниже, чтобы создать счёт.",
            color=discord.Color.green()
        )
        embed.set_author(name="VelionBank • О банке", icon_url=ctx.bot.user.avatar.url)
        embed.set_footer(text="© VelionTeam - 2025")
        embed.set_thumbnail(url="attachment://VelionBank.png")
        file = discord.File("imgs/VelionBank.png", filename="VelionBank.png")

        class CardTypeSelect(Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Basic", description="Бесплатно. Лимит: 10000 К-Э", emoji="💳"),
                    discord.SelectOption(label="Red", description="500 К-Э. Лимит: 50000 К-Э", emoji="💼"),
                    discord.SelectOption(label="Green", description="1500 К-Э. Лимит: 100000 К-Э", emoji="👑")
                ]
                super().__init__(placeholder="Выберите тип карты...", min_values=1, max_values=1, options=options)

            async def callback(self, interaction: discord.Interaction):
                selected = self.values[0]
                users_data = load_data()
                user_wallet = users_data.get(user_id, {}).get("wallet_balance", 0)

                cost = {"Basic": 0, "Red": 500, "Green": 1500}[selected]
                if user_wallet < cost:
                    await interaction.response.send_message(f"❌ У вас недостаточно К-Э (требуется {cost}).", ephemeral=True)
                    return

                if user_id not in users_data:
                    users_data[user_id] = {"wallet_balance": 0}
                users_data[user_id]["wallet_balance"] -= cost
                save_data(users_data)

                bank_data[user_id] = {
                    "bank_id": generate_bank_id(),
                    "card": generate_card_number(),
                    "holder": str(ctx.author),
                    "username": ctx.author.name,
                    "balance": 0,
                    "card_type": selected,
                    "limit": get_limit(selected)
                }
                save_bank_data(bank_data)

                await interaction.response.send_message(f"✅ Счёт с картой **{selected}** успешно создан!", ephemeral=True)

        class CreateAccountView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(CardTypeSelect())

        await ctx.send(embed=embed, view=CreateAccountView(), file=file)

@bot.command()
async def transfer(ctx, target: str = None, amount: int = None):
    user_id = str(ctx.author.id)
    bank_data = load_bank_data()

    if user_id not in bank_data:
        return await ctx.send("❌ У вас нет счёта в VelionBank. Используйте `!vb`, чтобы создать его.")

    if not target or not amount or amount <= 0:
        return await ctx.send("❌ Использование: `!transfer [@пользователь | номер карты | bank_id] [сумма]`")

    sender = bank_data[user_id]
    card_type = sender["card_type"]
    limits = {"Basic": 2000, "Red": 10000, "Green": 50000}
    transfer_limit = limits.get(card_type, 0)

    if amount > transfer_limit:
        return await ctx.send(f"❌ Лимит перевода для вашей карты ({card_type}) — `{transfer_limit} К-Э`.")

    if sender["balance"] < amount:
        return await ctx.send("❌ Недостаточно средств для перевода.")

    target_user_id = None
    target_account = None

    if target.startswith("<@") and target.endswith(">"):
        mentioned_id = target.strip("<@!>")
        if mentioned_id in bank_data:
            target_user_id = mentioned_id
            target_account = bank_data[mentioned_id]

    if not target_account and target.isdigit() and len(target) == 16:
        for uid, data in bank_data.items():
            card_number = ''.join(data.get("card", "").split())  
            if card_number.endswith(target):
                target_user_id = uid
                target_account = data
                break

    if not target_account:
        for uid, data in bank_data.items():
            if data.get("bank_id") == target:
                target_user_id = uid
                target_account = data
                break

    if not target_account:
        return await ctx.send("❌ Получатель не найден по карте, Bank-ID или упоминанию.")

    if target_user_id == user_id:
        return await ctx.send("❌ Вы не можете перевести средства самому себе.")

    sender["balance"] -= amount
    target_account["balance"] += amount
    save_bank_data(bank_data)

    embed = discord.Embed(
        title="💸 Перевод выполнен",
        description=(
            f"✅ **{ctx.author.name}** перевёл **{amount} К-Э** пользователю **{target_account['holder']}**\n"
            f"💳 Счёт отправителя: `{sender['card']}`\n"
            f"🏦 Счёт получателя: `{target_account['card']}`"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="VelionBank • Перевод средств")
    embed.set_author(name="💠 VelionBank", icon_url=ctx.bot.user.avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def mycard(ctx):
    user_id = str(ctx.author.id)
    bank_data = load_bank_data()

    if user_id not in bank_data:
        return await ctx.send("❌ У вас нет счёта в VelionBank. Используйте `!vb`, чтобы создать его.")

    user_bank = bank_data[user_id]
    card_type = user_bank["card_type"]
    card_number = user_bank["card"].replace(" ", "") 
    balance = user_bank["balance"]
    holder = user_bank["holder"]
    bank_id = user_bank["bank_id"]

    card_icons = {
        "Basic": "imgs/basic_card.png",
        "Red": "imgs/red_card.png",
        "Green": "imgs/green_card.png"
    }

    icon_path = card_icons.get(card_type, "imgs/basic_card.png")

    file = discord.File(icon_path, filename="card_icon.png")

    embed = discord.Embed(
        title="💳 Моя Карта VelionBank",
        color=discord.Color.from_rgb(33, 150, 83),
        description=(
            f"👤 **Держатель:** `{holder}`\n"
            f"💼 **Тип карты:** `{card_type}`\n"
            f"🏦 **Bank-ID:** `{bank_id}`\n"
            f"💰 **Баланс:** `{balance} К-Э`\n"
            f"📥 **Макс. перевод:** `{['2000','10000','50000'][['Basic','Red','Green'].index(card_type)]} К-Э`\n"
        )
    )
    embed.set_thumbnail(url="attachment://card_icon.png")
    embed.set_footer(text=f"Номер карты: {card_number}")
    embed.set_author(name="VelionBank • Карта", icon_url=ctx.bot.user.avatar.url)

    await ctx.send(embed=embed, file=file)

def load_users_data():
    try:
        with open("users_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users_data(data):
    with open("users_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_privileges():
    try:
        with open("privileges.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_privileges(data):
    with open("privileges.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

shop_items = {
    "VIP": {
        "base_price": 10000,
        "description": "🎉 VIP — бонус к опыту +20%, бонус к заработкам +25%, кулдауны быстрее на 15%."
    },
    "Elite": {
        "base_price": 15000,
        "description": "👑 Elite — бонус к опыту +50%, бонус к заработкам +35%, кулдауны быстрее на 30%."
    },
    "Green": {
        "base_price": 25000,
        "description": "💚 Green — всё из Elite + быстрая поддержка и бонусы 55%."
    }
}

durations = {
    "Неделя": 7,
    "Месяц": 30,
    "Навсегда": None
}

class DurationSelect(Select):
    def __init__(self, privilege_name, user_id):
        options = []
        for key, days in durations.items():
            multiplier = 0.5 if key == "Неделя" else 1 if key == "Месяц" else 3
            price = int(shop_items[privilege_name]["base_price"] * multiplier) if days is not None else "—"
            desc = f"{price} К-Э" if price != "—" else "Неограниченно"
            emoji = "⏳" if days is not None else "♾️"
            options.append(discord.SelectOption(label=key, description=desc, emoji=emoji))
        self.privilege_name = privilege_name
        self.user_id = user_id
        super().__init__(placeholder="Выберите срок действия", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        base_price = shop_items[self.privilege_name]["base_price"]
        multiplier = 0.5 if choice == "Неделя" else 1 if choice == "Месяц" else 3
        price = int(base_price * multiplier)

        bank_data = load_bank_data()
        users_data = load_users_data()
        privileges = load_privileges()

        user_bank_balance = bank_data.get(self.user_id, {}).get("balance", 0)
        user_wallet_balance = users_data.get(self.user_id, {}).get("wallet_balance", 0)
        total_funds = user_bank_balance + user_wallet_balance

        if total_funds < price:
            await interaction.response.send_message(f"❌ Недостаточно средств ({total_funds} К-Э), нужно {price} К-Э.", ephemeral=True)
            return

        # Списание средств: сначала с банка, потом с кошелька
        remaining = price
        if user_bank_balance >= remaining:
            bank_data[self.user_id]["balance"] -= remaining
            remaining = 0
        else:
            remaining -= user_bank_balance
            bank_data[self.user_id]["balance"] = 0
            users_data.setdefault(self.user_id, {})
            users_data[self.user_id]["wallet_balance"] = users_data[self.user_id].get("wallet_balance", 0) - remaining

        save_bank_data(bank_data)
        save_users_data(users_data)

        expires_at = None
        if durations[choice]:
            expires_at = (datetime.utcnow() + timedelta(days=durations[choice])).isoformat()

        privileges[self.user_id] = {
            "privilege": self.privilege_name,
            "expires_at": expires_at
        }
        save_privileges(privileges)

        await interaction.response.send_message(
            f"✅ Привилегия **{self.privilege_name}** успешно куплена на срок **{choice}**!",
            ephemeral=True
        )
        # Можно отключить выбор после покупки
        self.view.clear_items()
        await interaction.message.edit(view=self.view)

class PrivilegeSelect(Select):
    def __init__(self, user_id):
        options = []
        for key, data in shop_items.items():
            options.append(discord.SelectOption(label=key, description=data["description"], emoji="💠"))
        self.user_id = user_id
        super().__init__(placeholder="Выберите привилегию для покупки", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        view = View(timeout=60)
        view.add_item(DurationSelect(selected, self.user_id))
        await interaction.response.send_message(
            f"Вы выбрали привилегию **{selected}**.\nТеперь выберите срок действия:",
            ephemeral=True,
            view=view
        )

class ShopView(View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.add_item(PrivilegeSelect(user_id))

@bot.command()
async def shop(ctx):
    user_id = str(ctx.author.id)
    bank_data = load_bank_data()
    users_data = load_users_data()

    if user_id not in bank_data:
        await ctx.send("❌ У вас нет счёта в VelionBank. Создайте его командой `!vb`.")
        return

    embed = discord.Embed(
        title="🛒 Магазин VelionBank",
        description="Выберите привилегию для покупки из списка ниже. Оплата будет списана с вашего баланса в банке и кошельке.",
        color=discord.Color.green()
    )
    embed.set_footer(text="VelionBank • Магазин")

    await ctx.send(embed=embed, view=ShopView(user_id))

PRIVILEGES = {
    'vip': {'bonus_percent': 0.20, 'cd_reduction': 0.15},
    'elite': {'bonus_percent': 0.35, 'cd_reduction': 0.30},
    'green': {'bonus_percent': 0.55, 'cd_reduction': 0.55},
}

BASE_AMOUNT = 30
BASE_COOLDOWN_HOURS = 10

@bot.command()
async def timely(ctx):
    user_id = str(ctx.author.id)
    data = load_data()  # твоя функция загрузки баланса и времени
    privileges = load_privileges()

    # Инициализация данных пользователя, если нет
    if user_id not in data:
        data[user_id] = {
            'wallet_balance': 0,
            'last_claim': '1970-01-01T00:00:00'
        }

    # Проверяем есть ли у пользователя привилегия и не истекла ли она
    now = datetime.utcnow()
    user_priv = privileges.get(user_id)
    if user_priv:
        expires_at = datetime.fromisoformat(user_priv.get('expires_at'))
        if expires_at < now:
            # Привилегия истекла — считаем как без привилегии
            user_privilege = None
        else:
            user_privilege = user_priv.get('privilege').lower()  # приводим к нижнему регистру для словаря PRIVILEGES
    else:
        user_privilege = None

    # Получаем бонус и кулдаун
    bonus_percent = PRIVILEGES[user_privilege]['bonus_percent'] if user_privilege in PRIVILEGES else 0
    cd_reduction = PRIVILEGES[user_privilege]['cd_reduction'] if user_privilege in PRIVILEGES else 0

    bonus = int(BASE_AMOUNT * (1 + bonus_percent))
    cooldown = timedelta(hours=BASE_COOLDOWN_HOURS * (1 - cd_reduction))

    last_claim_str = data[user_id]['last_claim']
    last_claim = datetime.fromisoformat(last_claim_str)
    time_passed = now - last_claim

    if time_passed < cooldown:
        remaining = cooldown - time_passed
        total_seconds = int(remaining.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(f"⏳ Ты сможешь получить следующий бонус через {hours}ч {minutes}м {seconds}с.")
        return

    # Выдаём бонус и обновляем время
    data[user_id]['wallet_balance'] += bonus
    data[user_id]['last_claim'] = now.isoformat()

    save_data(data)

    await ctx.send(f"✅ {ctx.author.mention}, ты получил {bonus} к-э! Сейчас у тебя на балансе: {data[user_id]['wallet_balance']} к-э.")

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!help для помощи"
        ),
        status=discord.Status.idle
    )

    save_json("mutes.json", mutes)
    reset_activity.start()
    print(f"🔌 Бот {bot.user} запущен и готов к работе.")

bot.run(BOT_TOKEN)
