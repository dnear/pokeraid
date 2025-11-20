# bot.py
# Pokémon GO Raid Bot - aiogram v2 (Termux / Railway friendly)
# Requirements: aiogram==2.25.1, aiosqlite, python-dotenv

import os
import logging
import asyncio
import aiosqlite
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("ERROR: BOT_TOKEN not set. Set BOT_TOKEN in env variables.")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DB = "database.db"

# ---------- Database init ----------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                ign TEXT,
                trainer_code TEXT,
                level INTEGER,
                team TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS raids (
                raid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                creator_id INTEGER,
                pokemon TEXT,
                boosted TEXT,
                invite_minutes INTEGER,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS raid_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raid_id INTEGER,
                user_id INTEGER,
                status TEXT,
                plus_one INTEGER DEFAULT 0,
                UNIQUE(raid_id, user_id)
            )
        """)
        await db.commit()

# ---------- Utilities ----------
def build_raid_keyboard(raid_id):
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"join:{raid_id}:yes"),
        InlineKeyboardButton("❌ No", callback_data=f"join:{raid_id}:no"),
        InlineKeyboardButton("🤔 Maybe", callback_data=f"join:{raid_id}:maybe"),
    )
    kb.add(InlineKeyboardButton("➕ +1", callback_data=f"plus:{raid_id}"))
    return kb

async def build_raid_summary(db, raid_row):
    # raid_row is a dict-like (we fetch by column index)
    raid_id = raid_row[0]
    pokemon = raid_row[4]
    boosted = raid_row[5]
    minutes = raid_row[6]

    cur = await db.execute("SELECT status, plus_one FROM raid_players WHERE raid_id=?", (raid_id,))
    rows = await cur.fetchall()
    yes = sum(1 for r in rows if r[0] == "yes")
    maybe = sum(1 for r in rows if r[0] == "maybe")
    no = sum(1 for r in rows if r[0] == "no")
    plus = sum(r[1] for r in rows)

    text = (
        f"🔥 <b>RAID #{raid_id}</b>\n"
        f"<b>Pokémon:</b> {pokemon}\n"
        f"<b>Boosted:</b> {boosted}\n"
        f"<b>Invite Window:</b> {minutes} menit\n\n"
        f"👥 <b>Players</b>\n"
        f"✅ Yes: {yes}\n"
        f"🤔 Maybe: {maybe}\n"
        f"❌ No: {no}\n"
        f"➕ +1: {plus}\n\n"
        f"Gunakan tombol untuk join / leave / +1"
    )
    return text

# ---------- Command Handlers ----------
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.reply("Halo! Bot Raid aktif. Gunakan /help untuk perintah.")

@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    text = (
        "📋 <b>Perintah</b>\n\n"
        "/nickname <IGN> <trainer code>\n"
        "/gamer <level> <team>\n"
        "/newraid <Pokemon> <boosted|not> <minutes>\n\n"
        "Hashtag cepat: #help #rules #raid"
    )
    await message.reply(text)

@dp.message_handler(commands=["rules"])
async def cmd_rules(message: types.Message):
    text = (
        "📜 <b>RULES</b>\n"
        "1. Hanya command (/ atau #) yang diperbolehkan di grup.\n"
        "2. Registrasi wajib: /nickname & /gamer\n"
        "3. Gunakan /newraid untuk membuat raid.\n"
        "Bot akan menghapus pesan lain otomatis."
    )
    await message.reply(text)

@dp.message_handler(commands=["adminlist"])
async def cmd_adminlist(message: types.Message):
    admins = await bot.get_chat_administrators(message.chat.id)
    s = "👮 Admins:\n"
    for a in admins:
        s += f"- {a.user.full_name} (id: {a.user.id})\n"
    await message.reply(s)

# Registration
@dp.message_handler(commands=["nickname"])
async def cmd_nickname(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("Format: /nickname <IGN> <trainer code>\nContoh: /nickname MyIGN 1234 5678 9012")
        return
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Format: /nickname <IGN> <trainer code>")
        return
    ign = parts[0].strip()
    trainer_code = parts[1].strip()
    uid = message.from_user.id
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR REPLACE INTO users(user_id, ign, trainer_code) VALUES(?,?,?)", (uid, ign, trainer_code))
        await db.commit()
    await message.reply(f"Nickname set: {ign}\nTrainer Code: {trainer_code}")

@dp.message_handler(commands=["gamer"])
async def cmd_gamer(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("Format: /gamer <level> <team>\nContoh: /gamer 40 Yellow")
        return
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Format: /gamer <level> <team>")
        return
    try:
        level = int(parts[0])
    except:
        await message.reply("Level harus angka.")
        return
    team = parts[1].strip()
    uid = message.from_user.id
    async with aiosqlite.connect(DB) as db:
        # insert if not exists, else update
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
        await db.execute("UPDATE users SET level=?, team=? WHERE user_id=?", (level, team, uid))
        await db.commit()
    await message.reply(f"✅ Gamer terupdate: level {level}, team {team}")

# /newraid
@dp.message_handler(commands=["newraid"])
async def cmd_newraid(message: types.Message):
    # allowed in groups only
    if message.chat.type == "private":
        await message.reply("Gunakan /newraid di grup.")
        return

    args = message.get_args()
    if not args:
        await message.reply("Format: /newraid <Pokemon> <boosted|not> <minutes>\nContoh: /newraid Heatran boosted 5")
        return
    parts = args.split()
    if len(parts) < 3:
        await message.reply("Format: /newraid <Pokemon> <boosted|not> <minutes>")
        return

    # parse
    pokemon = parts[0]
    boosted = parts[1]
    try:
        minutes = int(parts[2])
    except:
        await message.reply("Invite minutes harus angka (mis. 5).")
        return

    creator = message.from_user

    # insert raid to DB
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT INTO raids(chat_id, creator_id, pokemon, boosted, invite_minutes) VALUES (?,?,?,?,?)",
            (message.chat.id, creator.id, pokemon, boosted, minutes)
        )
        await db.commit()
        raid_id = cur.lastrowid

    # build message like screenshot (initiator + show contact placeholder)
    raid_text = (
        f"🔥 <b>Raid #{raid_id}</b>\n"
        f"<b>Pokemon:</b> {pokemon}\n"
        f"<b>Boosted:</b> {boosted}\n"
        f"<b>Invite Window:</b> {minutes} menit\n\n"
        f"Initiator: {creator.full_name}"
    )

    kb = build_raid_keyboard(raid_id)
    sent = await message.reply(raid_text, reply_markup=kb)

    # save message_id
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE raids SET message_id=? WHERE raid_id=?", (sent.message_id, raid_id))
        await db.commit()

    # try DM initiator (works only if user started bot)
    try:
        await bot.send_message(creator.id, f"Raid kamu berhasil dibuat di grup {message.chat.title} (ID {raid_id}).")
    except Exception:
        pass

    # done
    return

# ---------- Callback queries for join / plus ----------
@dp.callback_query_handler(lambda c: c.data and (c.data.startswith("join:") or c.data.startswith("plus:")))
async def callbacks(call: types.CallbackQuery):
    data = call.data.split(":")
    action = data[0]
    raid_id = int(data[1])
    user_id = call.from_user.id

    async with aiosqlite.connect(DB) as db:
        # fetch raid
        rcur = await db.execute("SELECT * FROM raids WHERE raid_id=?", (raid_id,))
        rrow = await rcur.fetchone()
        if not rrow:
            await call.answer("Raid tidak ditemukan.", show_alert=True)
            return

        if action == "join":
            status = data[2]  # yes/no/maybe
            # upsert
            try:
                await db.execute("INSERT INTO raid_players(raid_id, user_id, status) VALUES(?,?,?)", (raid_id, user_id, status))
            except aiosqlite.IntegrityError:
                # already exists -> update
                await db.execute("UPDATE raid_players SET status=?, plus_one=0 WHERE raid_id=? AND user_id=?", (status, raid_id, user_id))
            await db.commit()
            await call.answer("Status terupdate.")

        elif action == "plus":
            # increment plus_one
            cur = await db.execute("SELECT id FROM raid_players WHERE raid_id=? AND user_id=?", (raid_id, user_id))
            row = await cur.fetchone()
            if row:
                await db.execute("UPDATE raid_players SET plus_one = plus_one + 1 WHERE id=?", (row[0],))
            else:
                await db.execute("INSERT INTO raid_players(raid_id, user_id, status, plus_one) VALUES(?,?,?,1)", (raid_id, user_id, "yes"))
            await db.commit()
            await call.answer("+1 ditambahkan.")

        # rebuild summary and edit original message
        rcur = await db.execute("SELECT * FROM raids WHERE raid_id=?", (raid_id,))
        rrow = await rcur.fetchone()
        summary = await build_raid_summary(db, rrow)

        chat_id = rrow[1]
        msg_id = rrow[2]
        kb = build_raid_keyboard(raid_id)
        try:
            await bot.edit_message_text(summary, chat_id=chat_id, message_id=msg_id, reply_markup=kb, parse_mode="HTML")
        except Exception:
            # fallback: try updating call.message
            try:
                await bot.edit_message_text(summary, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass

# ---------- Auto-delete non-command messages (enforce rules) ----------
@dp.message_handler(lambda m: m.chat.type != "private")
async def enforce_group_rules(message: types.Message):
    # Allow bot messages, admins, and commands/hastags
    try:
        if message.from_user.is_bot:
            return
    except:
        pass

    text = (message.text or "").strip()
    # allow if starts with "/" or "#"
    if text.startswith("/") or text.startswith("#"):
        # handle quick hashtags
        if text.lower().startswith("#help"):
            await cmd_help(message)
            return
        if text.lower().startswith("#rules"):
            await cmd_rules(message)
            return
        if text.lower().startswith("#raid"):
            await message.reply("Contoh: /newraid Heatran boosted 5")
            return
        # let actual slash commands be handled by command handlers
        return

    # else delete message
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except Exception:
        # if cannot delete (no permission) -> warn and do nothing
        try:
            await message.reply("Hanya diperbolehkan mengirim command (/ atau #). Pesan akan dihapus oleh bot jika saya admin.")
        except Exception:
            pass

# ---------- Startup ----------
async def on_startup(_):
    await init_db()
    logging.info("Database ready. Bot starting...")

if __name__ == "__main__":
    # run
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
