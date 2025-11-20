import time
import requests
import os
import sqlite3

TOKEN = os.getenv("BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"

db = sqlite3.connect("data.db", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, nickname TEXT, gamer TEXT)")
db.commit()

def send(chat, text):
    requests.post(API + "/sendMessage", json={"chat_id": chat, "text": text})

def handle_message(msg):
    chat = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/nickname"):
        try:
            _, ign, tc1, tc2, tc3 = text.split()
            tc = f"{tc1} {tc2} {tc3}"
            cur.execute("INSERT OR REPLACE INTO users(id, nickname) VALUES (?,?)", (chat, ign))
            db.commit()
            send(chat, f"Nickname set: {ign}\nTrainer Code: {tc}")
        except:
            send(chat, "Format salah!\nContoh:\n/nickname MyName 1234 5678 9012")

    elif text.startswith("/gamer"):
        try:
            _, level, team = text.split()
            cur.execute("UPDATE users SET gamer=? WHERE id=?", (f"{level} {team}", chat))
            db.commit()
            send(chat, f"Registered: Level {level}, Team {team}")
        except:
            send(chat, "Format salah!\nContoh:\n/gamer 40 Yellow")

    elif text.startswith("/newraid"):
        send(chat, f"Raid dibuat:\n{text}")

    else:
        send(chat, "Gunakan perintah /nickname, /gamer, /newraid")

def run():
    last_update = 0
    while True:
        try:
            data = requests.get(API + "/getUpdates", params={"offset": last_update + 1}).json()
            for upd in data.get("result", []):
                last_update = upd["update_id"]
                if "message" in upd:
                    handle_message(upd["message"])
        except Exception as e:
            print("Error:", e)
        time.sleep(1)

run()
