import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import sqlite3
import datetime
import re
import asyncio
import time
import sys
import traceback

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Token bot Anda
BOT_TOKEN = '8222235353:AAHycT7I4AypcwFfrl730NoOhzqtDEx-sDc'

# Inisialisasi database dengan error handling
def init_db():
    try:
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
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        logger.error(f"Database init error: {e}")
        return False

# Fungsi untuk menghapus pesan setelah delay
async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 30):
    """Hapus pesan setelah delay tertentu (default 2 menit untuk command benar)"""
    try:
        await asyncio.sleep(delay)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} after {delay} seconds")
    except Exception as e:
        logger.warning(f"Could not delete message {message_id}: {e}")

# Fungsi untuk menghapus pesan secara langsung (untuk command salah)
async def delete_message_immediately(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    """Hapus pesan secara langsung"""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} immediately")
    except Exception as e:
        logger.warning(f"Could not delete message {message_id}: {e}")

# Fungsi untuk membersihkan raid yang sudah expired
def cleanup_expired_raids():
    """Hapus raid yang sudah melewati waktu invite_time"""
    try:
        conn = sqlite3.connect('raids.db')
        c = conn.cursor()
        
        # Hapus raid yang created_at + invite_time sudah lewat dari waktu sekarang
        c.execute("""
            DELETE FROM raids 
            WHERE datetime(created_at, '+' || invite_time || ' minutes') < datetime('now')
        """)
        
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired raids")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up expired raids: {e}")
        return 0

# Handler untuk member baru yang join group
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim welcome message ketika ada member baru join"""
    try:
        # Cek jika ada member baru yang join
        for member in update.message.new_chat_members:
            welcome_text = f"""
👋 **Welcome {member.first_name} to Pokémon Go Remote Raids!** 👋

☀️🔥☁️ **REMOTE RAIDS INVITES** ☀️🔥☁️

📝 **REGISTRATION IS MANDATORY**

‼️ **To get started, register first:**
➡️ `/nickname <your in-game name> <trainer code>`
➡️ `/gamer <Trainer level> <team colour>`

💡 **Example:**
`/nickname AshKetchum 1234 5678 9012`
`/gamer 40 Yellow`

🎯 **CREATE RAID:**
`/newraid <Pokémon> <boosted> <time>`
💡 **Example:** `/newraid Heatran yes 5`

📋 **OTHER COMMANDS:**
• `/help` - Show all commands
• `/myprofile` - Check your registration
• `/list` - Show active raids

🚫 **RULES:**
• Only raid commands allowed
• Registration required before raiding
• Stay online during raids
• No spam or unrelated messages

Happy raiding! 🎉
            """
            
            # Kirim welcome message
            welcome_msg = await update.message.reply_text(
                welcome_text,
                parse_mode='Markdown',
                reply_to_message_id=update.message.message_id
            )
            
            # Hapus welcome message setelah 10 menit
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, welcome_msg.message_id, 600))
            
            logger.info(f"Sent welcome message to new member: {member.first_name} (ID: {member.id})")
    
    except Exception as e:
        logger.error(f"Error in welcome_new_member: {e}")

# Handler untuk member yang leave group
async def goodbye_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ketika member leave group"""
    try:
        if update.message.left_chat_member:
            # Optional: bisa tambahkan log atau action lain
            logger.info(f"Member left: {update.message.left_chat_member.first_name} (ID: {update.message.left_chat_member.id})")
    except Exception as e:
        logger.error(f"Error in goodbye_member: {e}")

# Command handlers - SEMUA COMMAND YANG BENAR
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
        message = await update.message.reply_text(welcome_text)
        
        # Hapus pesan perintah setelah 2 menit (120 detik)
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
        # Hapus pesan balasan setelah 2 menit
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 120))
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
        message = await update.message.reply_text(help_text)
        
        # Hapus setelah 2 menit
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        conn = sqlite3.connect('raids.db')
        c = conn.cursor()
        
        c.execute("SELECT in_game_name, trainer_code, trainer_level, team_color FROM users WHERE user_id = ?", (user.id,))
        user_data = c.fetchone()
        conn.close()
        
        if not user_data:
            profile_text = """
❌ **You are not registered!**

📝 **REGISTRATION IS MANDATORY**

‼️ To register use:
➡️ /nickname <in-game name> <trainer code>
➡️ /gamer <level> <team color>

💡 **Example:**
/nickname Ash 1234 5678 9012
/gamer 40 Yellow
            """
        else:
            in_game_name, trainer_code, trainer_level, team_color = user_data
            
            if trainer_level and team_color:
                status = "✅ **Registration Complete**"
            else:
                status = "❌ **Registration Incomplete**"
            
            profile_text = f"""
👤 **YOUR PROFILE**

• In-Game Name: {in_game_name}
• Trainer Code: {trainer_code}
• Trainer Level: {trainer_level if trainer_level else 'Not set'}
• Team: {team_color if team_color else 'Not set'}

{status}

{"🎯 You can create and join raids!" if trainer_level and team_color else "📝 Complete registration with /gamer <level> <team>"}
            """
        
        message = await update.message.reply_text(profile_text)
        
        # Hapus setelah 2 menit
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
        
    except Exception as e:
        logger.error(f"Error in myprofile command: {e}")

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
            message = await update.message.reply_text(
                "❌ You must complete registration before creating raids!\n\n"
                "Use /myprofile to check your registration status."
            )
            # Untuk command salah, hapus langsung
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 120))
            return
        
        if len(context.args) < 3:
            message = await update.message.reply_text(
                "❌ Invalid format! Use: /newraid <Pokemon> <boosted> <time>\nExample: /newraid Heatran yes 5"
            )
            # Untuk command salah, hapus langsung
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 120))
            return
        
        pokemon_name = context.args[0].capitalize()
        is_boosted = context.args[1].lower()
        invite_time_str = context.args[2]
        
        # Validasi boosted
        if is_boosted not in ['yes', 'no', 'y', 'n']:
            message = await update.message.reply_text("❌ Boosted must be 'yes' or 'no'!")
            # Untuk command salah, hapus langsung
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 120))
            return
        
        # Validasi time
        try:
            time_numbers = re.findall(r'\d+', invite_time_str)
            if not time_numbers:
                raise ValueError("No numbers found")
            
            invite_time = int(time_numbers[0])
            if invite_time <= 0 or invite_time > 60:
                message = await update.message.reply_text("❌ Time must be between 1 and 60 minutes!")
                # Untuk command salah, hapus langsung
                asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 120))
                return
                
        except ValueError:
            message = await update.message.reply_text("❌ Time must be a number!")
            # Untuk command salah, hapus langsung
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
            return
        
        # Konversi boosted ke boolean
        is_boosted_bool = is_boosted in ['yes', 'y']
        
        raid_id = f"raid_{int(time.time())}_{user.id}"
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
        
        # Hapus pesan perintah setelah 2 menit (command benar)
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 2))
        
        logger.info(f"Raid created: {raid_id}")
        
    except Exception as e:
        logger.error(f"Error in newraid: {e}")
        try:
            error_msg = await update.message.reply_text("❌ Error creating raid!")
            # Hapus pesan perintah langsung (command error)
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, error_msg.message_id, 30))
        except:
            pass
    finally:
        if conn:
            conn.close()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user = query.from_user
        
        if data.startswith(('join_', 'leave_', 'maybe_', 'plus1_')):
            action, raid_id = data.split('_', 1)
            
            conn = sqlite3.connect('raids.db')
            c = conn.cursor()
            
            # Cek apakah user terdaftar
            c.execute("SELECT in_game_name, trainer_code, trainer_level, team_color FROM users WHERE user_id = ?", (user.id,))
            user_data = c.fetchone()
            
            if not user_data or not user_data[2]:
                await query.edit_message_text("❌ Please complete registration first!")
                conn.close()
                return
            
            # Query dengan kolom yang eksplisit
            c.execute("""
                SELECT 
                    r.raid_id, r.pokemon_name, r.is_boosted, r.invite_time, r.created_at,
                    u.in_game_name, u.trainer_code, u.trainer_level, u.team_color
                FROM raids r 
                JOIN users u ON r.initiator_id = u.user_id 
                WHERE r.raid_id = ?
            """, (raid_id,))
            raid_data = c.fetchone()
            
            if not raid_data:
                await query.edit_message_text("❌ Raid not found!")
                conn.close()
                return
            
            # Extract data dengan nama variabel yang jelas
            (raid_id, pokemon_name, is_boosted, invite_time, created_at,
             initiator_name, initiator_code, initiator_level, initiator_team) = raid_data
            
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
            
            # Ambil daftar peserta terbaru
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
            
            boosted_text = "☀️ BOOSTED" if is_boosted else "⚡ NORMAL"
            
            raid_text = f"""
**{raid_id}:** {pokemon_name} {boosted_text}

**Initiator:** {initiator_name} (Lvl {initiator_level} {initiator_team})
**Trainer Code:** `{initiator_code}`
**Invites in:** {invite_time} minutes

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
        
    except Exception as e:
        logger.error(f"Error in button handler: {e}")

async def list_raids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Bersihkan raid yang sudah expired
        cleanup_expired_raids()
        
        conn = sqlite3.connect('raids.db')
        c = conn.cursor()
        
        # Hanya tampilkan raid yang masih aktif
        c.execute("""
            SELECT r.raid_id, r.pokemon_name, r.is_boosted, r.invite_time, u.in_game_name,
                   COUNT(p.id) as participant_count,
                   datetime(r.created_at, '+' || r.invite_time || ' minutes') as expire_time
            FROM raids r
            JOIN users u ON r.initiator_id = u.user_id
            LEFT JOIN participants p ON r.raid_id = p.raid_id AND p.status = 'going'
            WHERE datetime(r.created_at, '+' || r.invite_time || ' minutes') > datetime('now')
            GROUP BY r.raid_id
            ORDER BY r.created_at DESC
            LIMIT 10
        """)
        
        raids = c.fetchall()
        conn.close()
        
        if not raids:
            message = await update.message.reply_text("📭 No active raids found!")
        else:
            raids_text = "🔥 **ACTIVE RAIDS** 🔥\n\n"
            
            for raid in raids:
                raid_id, pokemon_name, is_boosted, invite_time, initiator, count, expire_time = raid
                boosted_emoji = "☀️" if is_boosted else "⚡"
                
                # Hitung sisa waktu
                expire_datetime = datetime.datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
                now = datetime.datetime.now()
                time_left = expire_datetime - now
                minutes_left = max(0, int(time_left.total_seconds() / 60))
                
                raids_text += f"**{raid_id}:** {pokemon_name} {boosted_emoji}\n"
                raids_text += f"By: {initiator} | ⏰ {minutes_left}min left | 👥 {count} participants\n\n"
            
            message = await update.message.reply_text(raids_text, parse_mode='Markdown')
        
        # Hapus pesan setelah 2 menit (command benar)
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
        
    except Exception as e:
        logger.error(f"Error in list_raids: {e}")

async def nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            message = await update.message.reply_text(
                "❌ Format: /nickname <in-game name> <trainer code>\nExample: /nickname Ash 1234 5678 9012"
            )
            # Untuk command salah, hapus langsung
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
        else:
            in_game_name = context.args[0]
            trainer_code = " ".join(context.args[1:])
            
            if not re.match(r'^[\d\s]+$', trainer_code):
                message = await update.message.reply_text("❌ Trainer code must contain only numbers and spaces!")
                # Untuk command salah, hapus langsung
                asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
            else:
                user = update.effective_user
                conn = sqlite3.connect('raids.db')
                c = conn.cursor()
                
                try:
                    c.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
                    existing_user = c.fetchone()
                    
                    if existing_user:
                        c.execute("""
                            UPDATE users 
                            SET in_game_name = ?, trainer_code = ?, username = ?
                            WHERE user_id = ?
                        """, (in_game_name, trainer_code, user.username or user.first_name, user.id))
                        response_text = "✅ Profile updated!"
                    else:
                        c.execute("""
                            INSERT INTO users (user_id, username, in_game_name, trainer_code)
                            VALUES (?, ?, ?, ?)
                        """, (user.id, user.username or user.first_name, in_game_name, trainer_code))
                        response_text = "✅ Registered! Now use: /gamer <level> <team>"
                    
                    conn.commit()
                    message = await update.message.reply_text(response_text)
                    
                    # Untuk command benar, hapus setelah 2 menit
                    asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
                    asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
                    
                except Exception as e:
                    message = await update.message.reply_text("❌ Error saving data!")
                    logger.error(f"Error in nickname: {e}")
                    # Untuk command error, hapus langsung
                    asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                    asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
                finally:
                    conn.close()
        
    except Exception as e:
        logger.error(f"Error in nickname: {e}")

async def gamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            message = await update.message.reply_text("❌ Format: /gamer <level> <team>\nExample: /gamer 40 Yellow")
            # Untuk command salah, hapus langsung
            asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
            asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
        else:
            try:
                trainer_level = int(context.args[0])
                team_color = context.args[1].capitalize()
                
                if team_color not in ['Red', 'Blue', 'Yellow']:
                    message = await update.message.reply_text("❌ Team must be Red, Blue, or Yellow!")
                    # Untuk command salah, hapus langsung
                    asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                    asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
                elif trainer_level < 1 or trainer_level > 50:
                    message = await update.message.reply_text("❌ Level must be 1-50!")
                    # Untuk command salah, hapus langsung
                    asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                    asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
                else:
                    user = update.effective_user
                    conn = sqlite3.connect('raids.db')
                    c = conn.cursor()
                    
                    c.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
                    if not c.fetchone():
                        message = await update.message.reply_text("❌ Register first with /nickname")
                        # Untuk command salah, hapus langsung
                        asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 120))
                    else:
                        c.execute("UPDATE users SET trainer_level = ?, team_color = ? WHERE user_id = ?",
                                 (trainer_level, team_color, user.id))
                        conn.commit()
                        message = await update.message.reply_text(f"✅ Level {trainer_level} {team_color} team set!")
                        
                        # Untuk command benar, hapus setelah 2 menit
                        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
                        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
                    
                    conn.close()
                    
            except ValueError:
                message = await update.message.reply_text("❌ Level must be a number!")
                # Untuk command salah, hapus langsung
                asyncio.create_task(delete_message_immediately(context, update.effective_chat.id, update.message.message_id))
                asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
        
    except Exception as e:
        logger.error(f"Error in gamer: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua pesan yang bukan command atau command yang salah"""
    try:
        if update.message.chat.type in ['group', 'supergroup']:
            # Skip jika ini adalah pesan join/leave
            if update.message.new_chat_members or update.message.left_chat_member:
                return
                
            # Hapus pesan yang bukan command atau command yang tidak dikenali
            if not update.message.text or not update.message.text.startswith('/'):
                # Hapus pesan langsung
                await delete_message_immediately(context, update.effective_chat.id, update.message.message_id)
                
                warning_msg = await update.message.reply_text(
                    "⚠️ **Only raid commands are allowed!**\n\n"
                    "📋 **Available Commands:**\n"
                    "• /start - Start bot\n"
                    "• /help - Show help\n"
                    "• /nickname <name> <code> - Register\n"
                    "• /gamer <level> <team> - Set level & team\n"
                    "• /myprofile - Check profile\n"
                    "• /newraid <pokemon> <boosted> <time> - Create raid\n"
                    "• /list - Show active raids\n\n"
                    "💡 **Example:** /newraid Heatran yes 5"
                )
                # Hapus pesan warning setelah 10 detik
                await asyncio.sleep(10)
                await warning_msg.delete()
            else:
                # Jika itu adalah command yang tidak dikenali, hapus dan beri panduan
                command = update.message.text.split()[0]
                known_commands = ['/start', '/help', '/nickname', '/gamer', '/myprofile', '/newraid', '/list', '/myraids', '/adminlist', '/rules', '/raid']
                
                if command not in known_commands:
                    # Hapus pesan command tidak dikenal langsung
                    await delete_message_immediately(context, update.effective_chat.id, update.message.message_id)
                    
                    warning_msg = await update.message.reply_text(
                        f"❌ **Unknown command: {command}**\n\n"
                        "📋 **Available Commands:**\n"
                        "• /start - Start bot\n"
                        "• /help - Show help\n"
                        "• /nickname <name> <code> - Register\n"
                        "• /gamer <level> <team> - Set level & team\n"
                        "• /myprofile - Check profile\n"
                        "• /newraid <pokemon> <boosted> <time> - Create raid\n"
                        "• /list - Show active raids\n\n"
                        "💡 **Use /help for more info**"
                    )
                    # Hapus pesan warning setelah 10 detik
                    await asyncio.sleep(10)
                    await warning_msg.delete()
                    
    except Exception as e:
        logger.warning(f"Could not handle message: {e}")

# Command sederhana lainnya
async def simple_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handler untuk command sederhana"""
    try:
        message = await update.message.reply_text(text)
        # Untuk command benar, hapus setelah 2 menit
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, update.message.message_id, 5))
        asyncio.create_task(delete_message_after_delay(context, update.effective_chat.id, message.message_id, 30))
    except Exception as e:
        logger.error(f"Error in simple command: {e}")

async def raid_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await simple_command(update, context, """
🔍 **NEW RAID COMMAND EXAMPLE:**

To start a new raid:
`/newraid Heatran yes 5`

**Parameters:**
• **Pokémon**: Name of the raid boss
• **Boosted**: "yes" or "no" 
• **Time**: Minutes until invites (5 minutes)
    """)

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await simple_command(update, context, """
📖 **GROUP RULES**

• Registration is MANDATORY
• Only raid commands allowed
• No spam or unrelated messages
• Be respectful to other trainers
• Stay online during raids
    """)

async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await simple_command(update, context, "🛠️ Contact @admin for assistance")

async def my_raids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await simple_command(update, context, "🎯 Use /list to see active raids you've joined")

def main():
    # Inisialisasi database
    if not init_db():
        return
    
    cleanup_expired_raids()
    
    # Buat application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers - HARUS DENGAN URUTAN YANG BENAR
    
    # 1. Handler untuk member join/leave (harus pertama)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_member))
    
    # 2. Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myprofile", myprofile))
    application.add_handler(CommandHandler("newraid", newraid))
    application.add_handler(CommandHandler("list", list_raids))
    application.add_handler(CommandHandler("nickname", nickname))
    application.add_handler(CommandHandler("gamer", gamer))
    application.add_handler(CommandHandler("raid", raid_example))
    application.add_handler(CommandHandler("rules", rules))
    application.add_handler(CommandHandler("adminlist", adminlist))
    application.add_handler(CommandHandler("myraids", my_raids))
    
    # 3. Button handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # 4. Message handler untuk mencegah pesan biasa di group - HARUS DITEMPATKAN TERAKHIR
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 5. Handler untuk command yang tidak dikenali - HARUS DITEMPATKAN PALING TERAKHIR
    application.add_handler(MessageHandler(filters.TEXT & filters.COMMAND, handle_message))
    
    # Start bot
    print("🤖 Pokemon Go Raid Bot Starting...")
    print("✅ Database initialized")
    print("👋 Welcome message enabled for new members")
    print("⏰ Command timing: Correct=2min, Wrong=Immediate")
    print("🔄 Starting polling...")
    print("🚀 Bot is ready!")
    
    try:
        application.run_polling()
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        logger.error(f"Bot crashed: {e}")
        # Restart dalam 10 detik
        print("🔄 Restarting in 10 seconds...")
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()

