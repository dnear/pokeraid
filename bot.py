# ============================================================
#  Pokémon GO Raid Bot (Telegram) – Full Version
#  Dibuat sesuai permintaan user (mirip PokéRaider)
#  Fitur:
#   ✔ /nickname
#   ✔ /gamer
#   ✔ /newraid
#   ✔ Tombol Yes / No / Maybe / +1
#   ✔ Auto-delete pesan non-command
#   ✔ #help #rules #raid
#   ✔ Simpan data ke SQLite
#   ✔ Bot jalan 24 jam di Railway
# ============================================================

import os
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv

# ------------------------------------------------------------
# Load TOKEN
# ------------------------------------------------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN belum di-set! Tambahkan di Railway → Variables.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

DB = "database.db"

# ------------------------------------------------------------
# INIT DATABASE
# ------------------------------------------------------------
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
                invite_minutes INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS raid_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raid_id INTEGER,
                user_id INTEGER,
                status TEXT,
                plus_one INTEGER DEFAULT 0
            )
        """)

        await db.commit()


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def format_summary(raid, players):
    yes = [p for p in players if p["status"] == "yes"]
    no = [p for p in players if p["status"] == "no"]
    maybe = [p for p in players if p["status"] == "maybe"]
    plus = sum([p["plus_one"] for p in players])

    return (
        f"🔥 <b>Raid #{raid['raid_id']}</b>\n\n"
        f"<b>Pokémon:</b> {raid['pokemon']}\n"
        f"<b>Boosted:</b> {raid['boosted']}\n"
        f"<b>Invite Window:</b> {raid['invite_minutes']} menit\n\n"
        f"👥 <b>Players:</b>\n"
        f"✅ Yes: {len(yes)}\n"
        f"❌ No: {len(no)}\n"
        f"🤔 Maybe: {len(maybe)}\n"
        f"➕ +1: {plus}\n"
        f"\nGunakan tombol untuk join."
    )


# ------------------------------------------------------------
# /start & /help
# ------------------------------------------------------------
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    await msg.reply("Halo! Bot raid aktif.\nGunakan /help di grup.")


@dp.message(Command("help"))
async def help_cmd(msg: types.Message):
    await msg.reply(
        "📋 <b>COMMANDS</b>\n\n"
        "/nickname <ign> <trainer code>\n"
        "/gamer <level> <team>\n"
        "/newraid <pokemon> <boosted|not> <minutes>\n\n"
        "Hashtag cepat:\n"
        "#help #rules #raid"
    )


@dp.message(Command("rules"))
async def rules_cmd(msg: types.Message):
    await msg.reply(
        "📜 <b>RULES:</b>\n"
        "• Hanya command yang boleh dikirim.\n"
        "• Semua chat biasa dihapus bot.\n"
        "• Gunakan /newraid untuk membuat raid."
    )


# ------------------------------------------------------------
# /nickname
# ------------------------------------------------------------
@dp.message(Command("nickname"))
async def nickname_cmd(msg: types.Message):
    args = msg.text.split(maxsplit=2)
    if len(args) < 3:
        await msg.reply("Format:\n/nickname <IGN> <trainer code>")
        return

    ign = args[1]
    code = args[2]
    uid = msg.from_user.id

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users(user_id, ign, trainer_code) VALUES(?,?,?)",
            (uid, ign, code)
        )
        await db.commit()

    await msg.reply(f"✅ Terdaftar: <b>{ign}</b> — {code}")


# ------------------------------------------------------------
# /gamer
# ------------------------------------------------------------
@dp.message(Command("gamer"))
async def gamer_cmd(msg: types.Message):
    args = msg.text.split(maxsplit=2)
    if len(args) < 3:
        await msg.reply("Format:\n/gamer <level> <team>")
        return

    try:
        level = int(args[1])
    except:
        await msg.reply("Level harus angka.")
        return

    team = args[2]
    uid = msg.from_user.id

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET level=?, team=? WHERE user_id=?",
            (level, team, uid)
        )
        await db.commit()

    await msg.reply(f"🎮 Gamer Updated: Level {level}, Team {team}")


# ------------------------------------------------------------
# /newraid
# ------------------------------------------------------------
@dp.message(Command("newraid"))
async def newraid_cmd(msg: types.Message):
    args = msg.text.split(maxsplit=4)
    if len(args) < 4:
        await msg.reply("Format:\n/newraid <pokemon> <boosted|not> <minutes>")
        return

    pokemon = args[1]
    boosted = args[2]
    minutes = int(args[3])

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            INSERT INTO raids(chat_id, creator_id, pokemon, boosted, invite_minutes)
            VALUES(?,?,?,?,?)
        """, (msg.chat.id, msg.from_user.id, pokemon, boosted, minutes))
        await db.commit()
        raid_id = cur.lastrowid

    # BUTTONS
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"join:{raid_id}:yes"),
            InlineKeyboardButton("❌ No", callback_data=f"join:{raid_id}:no"),
            InlineKeyboardButton("🤔 Maybe", callback_data=f"join:{raid_id}:maybe"),
        ],
        [InlineKeyboardButton("➕ +1", callback_data=f"plus:{raid_id}")]
    ])

    sent = await msg.answer(
        f"🔥 <b>Raid #{raid_id}</b>\n<b>Pokemon:</b> {pokemon}\n<b>Boosted:</b> {boosted}\n<b>Invite:</b> {minutes} menit",
        reply_markup=kb
    )

    # save message id
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE raids SET message_id=? WHERE raid_id=?", (sent.message_id, raid_id))
        await db.commit()


# ------------------------------------------------------------
# CALLBACKS: YES / NO / MAYBE / +1
# ------------------------------------------------------------
@dp.callback_query()
async def callback(call: types.CallbackQuery):
    data = call.data.split(":")
    action = data[0]
    raid_id = int(data[1])
    user_id = call.from_user.id

    async with aiosqlite.connect(DB) as db:
        # get raid
        r = await db.execute("SELECT * FROM raids WHERE raid_id=?", (raid_id,))
        raid = await r.fetchone()
        if not raid:
            await call.answer("Raid tidak ditemukan.")
            return

        raid_dict = {
            "raid_id": raid[0],
            "chat_id": raid[1],
            "message_id": raid[2],
            "creator_id": raid[3],
            "pokemon": raid[4],
            "boosted": raid[5],
            "invite_minutes": raid[6],
        }

        # JOIN STATUS
        if action == "join":
            status = data[2]

            # update or insert
            g = await db.execute(
                "SELECT id FROM raid_players WHERE raid_id=? AND user_id=?",
                (raid_id, user_id)
            )
            exists = await g.fetchone()

            if exists:
                await db.execute(
                    "UPDATE raid_players SET status=?, plus_one=0 WHERE id=?",
                    (status, exists[0])
                )
            else:
                await db.execute("""
                    INSERT INTO raid_players(raid_id, user_id, status)
                    VALUES (?,?,?)
                """, (raid_id, user_id, status))

            await db.commit()
            await call.answer("Updated.")

        # +1
        if action == "plus":
            g = await db.execute(
                "SELECT id FROM raid_players WHERE raid_id=? AND user_id=?",
                (raid_id, user_id)
            )
            rec = await g.fetchone()

            if rec:
                await db.execute(
                    "UPDATE raid_players SET plus_one = plus_one + 1 WHERE id=?",
                    (rec[0],)
                )
            else:
                await db.execute("""
                    INSERT INTO raid_players(raid_id, user_id, status, plus_one)
                    VALUES (?,?,?,1)
                """, (raid_id, user_id, "yes"))

            await db.commit()
            await call.answer("+1 Ditambahkan.")

        # reload summary
        p = await db.execute(
            "SELECT user_id, status, plus_one FROM raid_players WHERE raid_id=?",
            (raid_id,)
        )
        rows = await p.fetchall()

        players = []
        for u in rows:
            players.append({
                "user_id": u[0],
                "status": u[1],
                "plus_one": u[2]
            })

    # edit message
    summary = format_summary(raid_dict, players)
    try:
        await bot.edit_message_text(
            summary,
            chat_id=raid_dict["chat_id"],
            message_id=raid_dict["message_id"],
            reply_markup=call.message.reply_markup
        )
    except:
        pass


# ------------------------------------------------------------
# AUTO DELETE PESAN NON-COMMAND
# ------------------------------------------------------------
@dp.message()
async def cleanup(msg: types.Message):
    if msg.chat.type == "private":
        return

    if msg.text.startswith("/") or msg.text.startswith("#"):
        if msg.text.lower().startswith("#help"):
            await help_cmd(msg)
        if msg.text.lower().startswith("#rules"):
            await rules_cmd(msg)
        if msg.text.lower().startswith("#raid"):
            await msg.reply("Contoh: /newraid Heatran boosted 5")
        return

    try:
        await msg.delete()
    except:
        pass


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
