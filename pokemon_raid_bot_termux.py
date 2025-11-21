import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import sqlite3
import datetime
import re
import asyncio

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token bot Anda
BOT_TOKEN = '8222235353:AAHycT7I4AypcwFfrl730NoOhzqtDEx-sDc'

# Inisialisasi database dengan error handling
def init_db():
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    # Tabel untuk user terdaftar
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER UNIQUE,
                  username TEXT,
                  in_game_name TEXT,
                  trainer_code TEXT,
                  trainer_level INTEGER,
                  team_color TEXT,
                  registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabel untuk raid aktif
    c.execute('''CREATE TABLE IF NOT EXISTS raids
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  raid_id TEXT UNIQUE,
                  pokemon_name TEXT,
                  is_boosted BOOLEAN DEFAULT 0,
                  invite_time INTEGER DEFAULT 5,
                  initiator_id INTEGER,
                  status TEXT DEFAULT 'active',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabel untuk peserta raid
    c.execute('''CREATE TABLE IF NOT EXISTS participants
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  raid_id TEXT,
                  user_id INTEGER,
                  status TEXT,
                  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
☀️🔥☁️ WELCOME TO REMOTE RAIDS INVITES ☀️🔥☁️

This is a global Group for Raid Invites, please follow the points below⬇️

✅ Please use this bot to coordinate raids

❗️ Use /help to see how to register📋
❗️ Use /raid to see an example of what the command should look like🔍
❗️ Use /rules to check the rules📖
❗️✅ Share your code ONLY after the raid has been organised✅❗️

📝 **REGISTRATION IS MANDATORY**

‼️ To register use:
➡️ Format: /nickname <your in-game name> <trainer code>
⭕️ E.g.: /nickname MyInGameName 1234 5678 9012

➡️ Format: /gamer <Trainer level> <team colour>
⭕️ E.g.: /gamer 40 Yellow

Type /help to get started!
    """
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🆘 **HOW TO USE THE BOT** 🆘

📋 **REGISTRATION (MANDATORY):**
• Use `/nickname <in-game name> <trainer code>` - Register your basic info
• Use `/gamer <level> <team color>` - Register your level and team
• Use `/myprofile` - Check your registration status

🎯 **RAID COMMANDS:**
• Use `/newraid <Pokémon> <boosted> <time>` - Create new raid
• Use `/list` - See active raids
• Use `/myraids` - See your joined raids

🔍 **RAID FORMAT EXAMPLE:**
`/newraid Heatran yes 5`

📖 **Important Rules:**
• Registration is mandatory
• Writing for anything other than creating raid & registering is not allowed
• Share your Trainer code ONLY during registration
• Don't enroll into more than one raid at a time
• Stay active and online in game during raid
• English only in this group
• No spoofing promotion

Use /adminlist for any help
    """
    await update.message.reply_text(help_text)

async def raid_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    example_text = """
🔍 **NEW RAID COMMAND EXAMPLE:**

To start a new raid:
`/newraid Heatran yes 5`

**Parameters:**
• **Pokémon**: Name of the raid boss
• **Boosted**: "yes" or "no" 
• **Time**: Minutes until invites (5 minutes)

**Other Examples:**
`/newraid Mega Charizard X no 5`
`/newraid Rayquaza yes 5`

The bot will create a raid post with interactive buttons.
    """
    await update.message.reply_text(example_text)

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📖 **GROUP RULES** 📖

ℹ️ Writing for anything other than creating raid & registering is not allowed.
All other messages will get deleted automatically.

📝 **REGISTRATION IS MANDATORY**

‼️ To register use ⬇️⬇️⬇️
➡️ Format: /nickname <your in-game name> <trainer code>
⭕️ E.g.: /nickname MyInGameName 1234 5678 9012

➡️ Format: /gamer <Trainer level> <team colour>
⭕️ E.g.: /gamer 40 Yellow

🎯 **RAID RULES:**
• Use raidbot ONLY to create raids
• Format: /newraid <Pokemon> <boosted (or not)> <time to invites 5 minutes>
• Direct message the raid initiator for any raid specific details
• Don't enroll into more than one raid at a time

✅ **DO:**
• Use English only
• Stay active and stay online in game during raids
• Listen to Admins

❌ **DON'T:**
• Don't abuse anyone
• Don't promote spoofing
• Don't send messages other than raid commands and registration

⚠️ **WARNINGS:**
• Not listening to Admins may result in a Warning ⛔️
• Promoting spoofing may result in warning/ban
• Unregistered users cannot join raids

ℹ️ Use /adminlist for any help
ℹ️ Enjoy the raids 😊
    """
    await update.message.reply_text(rules_text)

async def nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format!\n\n"
            "‼️ To register use:\n"
            "➡️ Format: /nickname <your in-game name> <trainer code>\n"
            "⭕️ E.g.: /nickname MyInGameName 1234 5678 9012"
        )
        return
    
    in_game_name = context.args[0]
    trainer_code = " ".join(context.args[1:])
    
    # Validasi trainer code (harus angka dan spasi)
    if not re.match(r'^[\d\s]+$', trainer_code):
        await update.message.reply_text("❌ Trainer code must contain only numbers and spaces!")
        return
    
    user = update.effective_user
    
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    try:
        # Cek apakah user sudah registrasi
        c.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
        existing_user = c.fetchone()
        
        if existing_user:
            # Update existing user
            c.execute("""
                UPDATE users 
                SET in_game_name = ?, trainer_code = ?, username = ?
                WHERE user_id = ?
            """, (in_game_name, trainer_code, user.username or user.first_name, user.id))
            message = "✅ Your nickname and trainer code updated successfully!"
        else:
            # Insert new user
            c.execute("""
                INSERT INTO users (user_id, username, in_game_name, trainer_code)
                VALUES (?, ?, ?, ?)
            """, (user.id, user.username or user.first_name, in_game_name, trainer_code))
            message = "✅ Nickname and trainer code registered successfully!\n\nNow register your level and team with:\n/gamer <level> <team color>"
        
        conn.commit()
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text("❌ Error registering your information!")
        logger.error(f"Error in nickname: {e}")
    finally:
        conn.close()

async def gamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Invalid format!\n\n"
            "‼️ To register use:\n"
            "➡️ Format: /gamer <Trainer level> <team colour>\n"
            "⭕️ E.g.: /gamer 40 Yellow"
        )
        return
    
    try:
        trainer_level = int(context.args[0])
        team_color = context.args[1].capitalize()
        
        # Validasi team color
        valid_teams = ['Red', 'Blue', 'Yellow']
        if team_color not in valid_teams:
            await update.message.reply_text("❌ Team color must be Red, Blue, or Yellow!")
            return
        
        # Validasi level
        if trainer_level < 1 or trainer_level > 50:
            await update.message.reply_text("❌ Trainer level must be between 1 and 50!")
            return
            
    except ValueError:
        await update.message.reply_text("❌ Trainer level must be a number!")
        return
    
    user = update.effective_user
    
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    try:
        # Cek apakah user sudah registrasi nickname
        c.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
        existing_user = c.fetchone()
        
        if not existing_user:
            await update.message.reply_text(
                "❌ Please register your nickname and trainer code first!\n\n"
                "Use: /nickname <in-game name> <trainer code>"
            )
            return
        
        # Update user dengan level dan team
        c.execute("""
            UPDATE users 
            SET trainer_level = ?, team_color = ?
            WHERE user_id = ?
        """, (trainer_level, team_color, user.id))
        
        conn.commit()
        
        # Tampilkan profil lengkap
        c.execute("SELECT in_game_name, trainer_code, trainer_level, team_color FROM users WHERE user_id = ?", (user.id,))
        user_data = c.fetchone()
        
        profile_text = f"""
✅ **REGISTRATION COMPLETE!**

👤 **Player Profile:**
• In-Game Name: {user_data[0]}
• Trainer Code: {user_data[1]}
• Trainer Level: {user_data[2]}
• Team: {user_data[3]}

🎯 You can now create and join raids!
Use /newraid to create your first raid.
        """
        
        await update.message.reply_text(profile_text)
        
    except Exception as e:
        await update.message.reply_text("❌ Error updating your information!")
        logger.error(f"Error in gamer: {e}")
    finally:
        conn.close()

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    c.execute("SELECT in_game_name, trainer_code, trainer_level, team_color FROM users WHERE user_id = ?", (user.id,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        await update.message.reply_text(
            "❌ You are not registered!\n\n"
            "📝 **REGISTRATION IS MANDATORY**\n\n"
            "‼️ To register use:\n"
            "➡️ /nickname <in-game name> <trainer code>\n"
            "➡️ /gamer <level> <team color>"
        )
        return
    
    in_game_name, trainer_code, trainer_level, team_color = user_data
    
    profile_text = f"""
👤 **YOUR PROFILE**

• In-Game Name: {in_game_name}
• Trainer Code: {trainer_code}
• Trainer Level: {trainer_level if trainer_level else 'Not set'}
• Team: {team_color if team_color else 'Not set'}

{'✅ **Registration Complete** - You can join raids!' if trainer_level and team_color else '❌ **Registration Incomplete** - Use /gamer to complete registration'}
    """
    
    await update.message.reply_text(profile_text)

async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_text = """
🛠️ **ADMIN HELP**

For any assistance, please contact our admins:

👤 **Admin 1**: @admin1
👤 **Admin 2**: @admin2  
👤 **Admin 3**: @admin3

📧 **For urgent issues:**
• Raid coordination problems
• User behavior reports
• Technical issues with bot

ℹ️ Please be patient and wait for admin response.

Enjoy the raids! 😊
    """
    await update.message.reply_text(admin_text)

async def newraid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = None
    try:
        # Cek registrasi user
        user = update.effective_user
        conn = sqlite3.connect('raids.db')
        c = conn.cursor()
        
        c.execute("SELECT in_game_name, trainer_code, trainer_level, team_color FROM users WHERE user_id = ?", (user.id,))
        user_data = c.fetchone()
        
        if not user_data or not user_data[2] or not user_data[3]:
            await update.message.reply_text(
                "❌ You must complete registration before creating raids!\n\n"
                "Use /myprofile to check your registration status.\n"
                "Use /help for registration instructions."
            )
            return
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Invalid format!\n\n"
                "‼️ To create raid use:\n"
                "➡️ Format: /newraid <Pokemon> <boosted (yes/no)> <time to invites (minutes)>\n"
                "⭕️ E.g.: /newraid Heatran yes 5\n\n"
                "💡 **Example:** `/newraid Pikachu no 5`"
            )
            return
        
        pokemon_name = context.args[0].capitalize()
        is_boosted = context.args[1].lower()
        invite_time_str = context.args[2]
        
        # Validasi boosted
        if is_boosted not in ['yes', 'no', 'y', 'n']:
            await update.message.reply_text(
                "❌ Boosted must be 'yes' or 'no'!\n\n"
                "💡 **Examples:**\n"
                "• `/newraid Heatran yes 5`\n"
                "• `/newraid Pikachu no 5`"
            )
            return
        
        # Validasi time - hanya ambil angka pertama
        try:
            # Ekstrak angka dari string (misal: "5" atau "5 minutes" -> 5)
            time_numbers = re.findall(r'\d+', invite_time_str)
            if not time_numbers:
                raise ValueError("No numbers found")
            
            invite_time = int(time_numbers[0])
            if invite_time <= 0 or invite_time > 60:
                await update.message.reply_text("❌ Time must be between 1 and 60 minutes!")
                return
                
        except ValueError:
            await update.message.reply_text(
                "❌ Time must be a number!\n\n"
                "💡 **Examples:**\n"
                "• `/newraid Heatran yes 5`\n"
                "• `/newraid Pikachu no 10`"
            )
            return
        
        # Konversi boosted ke boolean
        is_boosted_bool = is_boosted in ['yes', 'y']
        
        raid_id = f"raid_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{user.id}"
        boosted_text = "☀️ BOOSTED" if is_boosted_bool else "⚡ NORMAL"
        
        # Simpan raid ke database
        c.execute("""
            INSERT INTO raids (raid_id, pokemon_name, is_boosted, invite_time, initiator_id)
            VALUES (?, ?, ?, ?, ?)
        """, (raid_id, pokemon_name, is_boosted_bool, invite_time, user.id))
        
        # Tambah initiator sebagai peserta
        c.execute("INSERT INTO participants (raid_id, user_id, status) VALUES (?, ?, ?)",
                 (raid_id, user.id, "going"))
        
        conn.commit()
        
        # Dapatkan info user lengkap
        in_game_name, trainer_code, trainer_level, team_color = user_data
        
        # Buat keyboard untuk raid
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"join_{raid_id}"),
                InlineKeyboardButton("❌ No", callback_data=f"leave_{raid_id}"),
                InlineKeyboardButton("❓ Maybe", callback_data=f"maybe_{raid_id}"),
                InlineKeyboardButton("👥 +1", callback_data=f"plus1_{raid_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        raid_text = f"""
**{raid_id}:** {pokemon_name} {boosted_text}

**Initiator:** {in_game_name} (Lvl {trainer_level} {team_color})
**Trainer Code:** `{trainer_code}`
**Invites in:** {invite_time} minutes
**Status:** Organizing - Stay online!

✅ **Going:**
• {in_game_name} ✅ Lvl {trainer_level} {team_color} - `{trainer_code}`

Use buttons below to join the raid!
        """
        
        # Kirim pesan raid
        raid_message = await update.message.reply_text(raid_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Hapus pesan perintah setelah raid berhasil dibuat
        try:
            await update.message.delete()
            logger.info(f"Deleted command message for raid {raid_id}")
        except Exception as e:
            logger.warning(f"Could not delete command message: {e}")
        
        logger.info(f"Raid created successfully: {raid_id} by user {user.id}")
        
    except sqlite3.IntegrityError:
        await update.message.reply_text("❌ Raid already exists! Please try again.")
        logger.error("Raid already exists")
    except Exception as e:
        await update.message.reply_text("❌ Error creating raid! Please check the format and try again.")
        logger.error(f"Unexpected error in newraid: {e}")
    finally:
        if conn:
            conn.close()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # Cek apakah user terdaftar
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    c.execute("SELECT in_game_name, trainer_code, trainer_level, team_color FROM users WHERE user_id = ?", (user.id,))
    user_data = c.fetchone()
    
    if not user_data or not user_data[2] or not user_data[3]:
        await query.edit_message_text(
            "❌ You must complete registration before joining raids!\n\n"
            "Use /myprofile to check your registration status."
        )
        conn.close()
        return
    
    in_game_name, trainer_code, trainer_level, team_color = user_data
    
    if data.startswith(('join_', 'leave_', 'maybe_', 'plus1_')):
        action, raid_id = data.split('_', 1)
        
        # Cek apakah raid exists
        c.execute("""
            SELECT r.*, u.in_game_name, u.trainer_code, u.trainer_level, u.team_color 
            FROM raids r 
            JOIN users u ON r.initiator_id = u.user_id 
            WHERE r.raid_id = ?
        """, (raid_id,))
        raid = c.fetchone()
        
        if not raid:
            await query.edit_message_text("❌ Raid not found!")
            conn.close()
            return
        
        # Hapus partisipasi sebelumnya user ini di raid ini
        c.execute("DELETE FROM participants WHERE raid_id = ? AND user_id = ?", (raid_id, user.id))
        
        # Tambah partisipasi baru berdasarkan action
        status_map = {
            'join': 'going',
            'maybe': 'maybe', 
            'plus1': 'plus1'
        }
        
        if action != 'leave':
            status = status_map.get(action, 'going')
            c.execute("INSERT INTO participants (raid_id, user_id, status) VALUES (?, ?, ?)",
                     (raid_id, user.id, status))
        
        # Ambil daftar peserta terbaru dengan info user lengkap (termasuk trainer code)
        c.execute("""
            SELECT u.in_game_name, u.trainer_code, u.trainer_level, u.team_color, p.status
            FROM participants p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.raid_id = ?
            ORDER BY p.joined_at
        """, (raid_id,))
        
        participants = c.fetchall()
        conn.commit()
        
        # Format ulang pesan raid
        going_text = "✅ **Going:**\n"
        maybe_text = "❓ **Maybe:**\n" 
        plus1_text = "👥 **+1:**\n"
        
        for participant in participants:
            p_name, p_code, p_level, p_team, p_status = participant
            emoji = "✅" if p_status == "going" else "❓" if p_status == "maybe" else "👥"
            
            participant_line = f"• {p_name} {emoji} Lvl {p_level} {p_team} - `{p_code}`\n"
            
            if p_status == "going":
                going_text += participant_line
            elif p_status == "maybe":
                maybe_text += participant_line
            elif p_status == "plus1":
                plus1_text += participant_line
        
        boosted_text = "☀️ BOOSTED" if raid[3] else "⚡ NORMAL"
        
        raid_text = f"""
**{raid_id}:** {raid[2]} {boosted_text}

**Initiator:** {raid[7]} (Lvl {raid[9]} {raid[10]})
**Trainer Code:** `{raid[8]}`
**Invites in:** {raid[4]} minutes
**Status:** Organizing - Stay online!

{going_text}
{maybe_text if "❓" in maybe_text else ""}
{plus1_text if "👥" in plus1_text else ""}
        """
        
        # Buat keyboard baru
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"join_{raid_id}"),
                InlineKeyboardButton("❌ No", callback_data=f"leave_{raid_id}"),
                InlineKeyboardButton("❓ Maybe", callback_data=f"maybe_{raid_id}"),
                InlineKeyboardButton("👥 +1", callback_data=f"plus1_{raid_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(raid_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    conn.close()

async def list_raids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    c.execute("""
        SELECT r.raid_id, r.pokemon_name, r.is_boosted, r.invite_time, u.in_game_name,
               COUNT(p.id) as participant_count
        FROM raids r
        JOIN users u ON r.initiator_id = u.user_id
        LEFT JOIN participants p ON r.raid_id = p.raid_id AND p.status = 'going'
        WHERE r.status = 'active'
        GROUP BY r.raid_id
        ORDER BY r.created_at DESC
        LIMIT 10
    """)
    
    raids = c.fetchall()
    conn.close()
    
    if not raids:
        await update.message.reply_text("📭 No active raids found!")
        return
    
    raids_text = "🔥 **ACTIVE RAIDS** 🔥\n\n"
    
    for raid in raids:
        raid_id, pokemon_name, is_boosted, invite_time, initiator, count = raid
        boosted_emoji = "☀️" if is_boosted else "⚡"
        raids_text += f"**{raid_id}:** {pokemon_name} {boosted_emoji}\n"
        raids_text += f"By: {initiator} | ⏰ {invite_time}min | 👥 {count} participants\n\n"
    
    await update.message.reply_text(raids_text, parse_mode='Markdown')

async def my_raids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    conn = sqlite3.connect('raids.db')
    c = conn.cursor()
    
    c.execute("""
        SELECT r.raid_id, r.pokemon_name, p.status, r.is_boosted
        FROM raids r
        JOIN participants p ON r.raid_id = p.raid_id
        WHERE p.user_id = ? AND r.status = 'active'
        ORDER BY r.created_at DESC
    """, (user.id,))
    
    my_raids = c.fetchall()
    conn.close()
    
    if not my_raids:
        await update.message.reply_text("📭 You haven't joined any active raids!")
        return
    
    raids_text = "🎯 **YOUR ACTIVE RAIDS** 🎯\n\n"
    
    for raid in my_raids:
        raid_id, pokemon_name, status, is_boosted = raid
        status_emoji = "✅" if status == "going" else "❓" if status == "maybe" else "👥"
        boosted_emoji = "☀️" if is_boosted else "⚡"
        raids_text += f"**{raid_id}:** {pokemon_name} {boosted_emoji} {status_emoji}\n"
    
    await update.message.reply_text(raids_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cegah pengiriman pesan biasa di group
    if update.message.chat.type in ['group', 'supergroup']:
        # Izinkan hanya command yang diawali dengan slash
        if not update.message.text or not update.message.text.startswith('/'):
            try:
                await update.message.delete()
                warning_msg = await update.message.reply_text(
                    "⚠️ Writing for anything other than creating raid & registering is not allowed.\n"
                    "All other messages will get deleted automatically."
                )
                # Hapus warning setelah 5 detik
                await asyncio.sleep(5)
                await warning_msg.delete()
            except Exception as e:
                logger.warning(f"Could not delete message: {e}")

def main():
    # Inisialisasi database
    init_db()
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("raid", raid_example))
        application.add_handler(CommandHandler("rules", rules))
        application.add_handler(CommandHandler("nickname", nickname))
        application.add_handler(CommandHandler("gamer", gamer))
        application.add_handler(CommandHandler("newraid", newraid))
        application.add_handler(CommandHandler("list", list_raids))
        application.add_handler(CommandHandler("myraids", my_raids))
        application.add_handler(CommandHandler("myprofile", myprofile))
        application.add_handler(CommandHandler("adminlist", adminlist))
        
        # Button handler
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Message handler untuk mencegah pesan biasa di group
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Start bot
        print("🤖 Pokemon Go Raid Bot Starting...")
        print("✅ Database initialized")
        print("🔄 Starting polling...")
        print("📍 Running on Termux")
        print("🚀 Bot is ready!")
        
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        logging.error(f"Bot startup failed: {e}")

if __name__ == '__main__':
    main()
