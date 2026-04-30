
import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import re
import os
from functools import wraps
from flask import Flask, request

# ================= التوكن والإعدادات =================
TOKEN = "8600057182:AAGImzI3A7IjGSoEPT2JUpg2-QJ1ukNkbAA"
ADMIN_ID = 6599083480

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# حالات المستخدمين المؤقتة
user_states = {}

# إنشاء تطبيق Flask
app = Flask(__name__)

# ================= إنشاء قاعدة البيانات =================
def get_db():
    conn = sqlite3.connect("contest_bot.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY,
        vote_channel TEXT,
        auto_approve INTEGER DEFAULT 1
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        title TEXT,
        description TEXT,
        channel_id TEXT,
        channel_name TEXT,
        post_id INTEGER,
        created_at TEXT,
        active INTEGER DEFAULT 1
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contestants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id INTEGER,
        user_id INTEGER,
        name TEXT,
        votes INTEGER DEFAULT 0,
        post_id INTEGER,
        FOREIGN KEY (contest_id) REFERENCES contests (id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id INTEGER,
        voter_id INTEGER,
        contestant_id INTEGER,
        UNIQUE(contest_id, voter_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bans (
        user_id INTEGER PRIMARY KEY,
        reason TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ تم تجهيز قاعدة البيانات")

init_db()

# ================= الأزرار الرئيسية =================
def main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎯 إنشاء مسابقة", callback_data="create_contest"),
        types.InlineKeyboardButton("📢 قناة التصويت", callback_data="set_channel")
    )
    keyboard.add(
        types.InlineKeyboardButton("🏆 مسابقاتي", callback_data="my_contests"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
    )
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة أصوات", callback_data="add_votes"),
        types.InlineKeyboardButton("➖ خصم أصوات", callback_data="remove_votes")
    )
    keyboard.add(
        types.InlineKeyboardButton("📊 جدول المتصدرين", callback_data="leaderboard"),
        types.InlineKeyboardButton("📖 المساعدة", callback_data="help")
    )
    return keyboard

def send_main_menu(chat_id, user_id):
    text = """🌟 <b>مرحباً بك في بوت المسابقات!</b> 🌟

▫️ البوت يدير المسابقات بشكل تلقائي
▫️ يمكن للمستخدمين المشاركة والتصويت
▫️ يتم حذف المسابقات بعد 24 ساعة

📌 <b>مطور البوت:</b> عصوم الشامي

اختر الإجراء المناسب:"""
    
    bot.send_message(chat_id, text, reply_markup=main_keyboard())

# ================= بدء البوت =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith("contest_"):
            contest_id = int(param.replace("contest_", ""))
            
            conn = get_db()
            contest = conn.execute("SELECT * FROM contests WHERE id = ? AND active = 1", (contest_id,)).fetchone()
            conn.close()
            
            if contest:
                user_states[user_id] = {"action": "join_contest", "contest_id": contest_id}
                bot.send_message(
                    message.chat.id,
                    f"🎯 <b>المشاركة في المسابقة</b>\n\nأرسل اسمك الآن للمشاركة:",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
                    )
                )
                return
    
    send_main_menu(message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_callback(call):
    user_id = call.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_main_menu(call.message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu_callback(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_main_menu(call.message.chat.id, call.from_user.id)

# ================= إنشاء مسابقة =================
@bot.callback_query_handler(func=lambda call: call.data == "create_contest")
def create_contest_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    setting = conn.execute("SELECT vote_channel FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not setting or not setting["vote_channel"]:
        bot.answer_callback_query(call.id, "❌ يرجى تعيين قناة التصويت أولاً!", show_alert=True)
        return
    
    msg = bot.send_message(call.message.chat.id, "🎯 أرسل عنوان المسابقة:")
    bot.register_next_step_handler(msg, get_contest_title)

def get_contest_title(message):
    user_id = message.from_user.id
    title = message.text.strip()
    user_states[user_id] = {"title": title}
    msg = bot.send_message(message.chat.id, "📝 أرسل وصف المسابقة والجوائز:")
    bot.register_next_step_handler(msg, get_contest_desc)

def get_contest_desc(message):
    user_id = message.from_user.id
    desc = message.text.strip()
    title = user_states[user_id]["title"]
    
    conn = get_db()
    setting = conn.execute("SELECT vote_channel FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    channel_id = setting["vote_channel"]
    
    try:
        chat = bot.get_chat(int(channel_id))
        channel_name = chat.title
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor = conn.execute("""
            INSERT INTO contests (owner_id, title, description, channel_id, channel_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, title, desc, channel_id, channel_name, created_at))
        
        contest_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        bot_username = bot.get_me().username
        contest_link = f"https://t.me/{bot_username}?start=contest_{contest_id}"
        
        post_text = f"""🎯 <b>مسابقة جديدة!</b>

📌 <b>العنوان:</b> {title}

{desc}

⏰ <b>تنتهي المسابقة بعد 24 ساعة</b>

👇 اضغط للمشاركة:"""
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🎯 المشاركة في المسابقة", url=contest_link))
        
        sent = bot.send_message(int(channel_id), post_text, reply_markup=keyboard)
        
        conn = get_db()
        conn.execute("UPDATE contests SET post_id = ? WHERE id = ?", (sent.message_id, contest_id))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم إنشاء المسابقة بنجاح!\n\n📌 {title}\n🆔 #{contest_id}\n⏰ تنتهي بعد 24 ساعة"
        )
        
        del user_states[user_id]
        send_main_menu(message.chat.id, user_id)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}")

# ================= تعيين قناة التصويت =================
@bot.callback_query_handler(func=lambda call: call.data == "set_channel")
def set_channel_callback(call):
    msg = bot.send_message(call.message.chat.id, "📢 أرسل رابط القناة أو معرفها (@username):")
    bot.register_next_step_handler(msg, save_channel)

def save_channel(message):
    user_id = message.from_user.id
    channel_input = message.text.strip()
    
    if "t.me/" in channel_input:
        username = "@" + channel_input.split("t.me/")[1].split("/")[0]
    else:
        username = channel_input if channel_input.startswith("@") else "@" + channel_input
    
    try:
        chat = bot.get_chat(username)
        bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
        
        if bot_member.status != "administrator":
            bot.send_message(message.chat.id, "❌ البوت ليس مشرفاً في هذه القناة!")
            return
        
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (user_id, vote_channel) VALUES (?, ?)", (user_id, str(chat.id)))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم تعيين القناة بنجاح!\n📢 {chat.title}",
            reply_markup=main_keyboard()
        )
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}")

# ================= مسابقاتي =================
@bot.callback_query_handler(func=lambda call: call.data == "my_contests")
def my_contests_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    contests = conn.execute("SELECT * FROM contests WHERE owner_id = ? AND active = 1 ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    
    if not contests:
        bot.edit_message_text(
            "📋 لا توجد مسابقات نشطة.\n\n🎯 اضغط على 'إنشاء مسابقة' لبدء مسابقة جديدة",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu")
            )
        )
        return
    
    text = "🏆 <b>مسابقاتي النشطة</b>\n\n"
    for contest in contests:
        time_left = get_time_remaining(contest["created_at"])
        text += f"🔹 <b>{contest['title']}</b>\n"
        text += f"   🆔 #{contest['id']}\n"
        text += f"   {time_left}\n\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

def get_time_remaining(created_at):
    try:
        created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        end = created + timedelta(days=1)
        now = datetime.now()
        
        if now > end:
            return "⏰ انتهت"
        
        remaining = end - now
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        
        return f"⏳ متبقي: {hours:02d}:{minutes:02d}"
    except:
        return "⏳ حساب الوقت..."

# ================= جدول المتصدرين =================
@bot.callback_query_handler(func=lambda call: call.data == "leaderboard")
def leaderboard_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    contests = conn.execute("SELECT id, title FROM contests WHERE owner_id = ? AND active = 1", (user_id,)).fetchall()
    conn.close()
    
    if not contests:
        bot.answer_callback_query(call.id, "لا توجد مسابقات نشطة!", show_alert=True)
        return
    
    text = "🏆 <b>اختر المسابقة لعرض المتصدرين</b>\n\n"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for contest in contests:
        keyboard.add(types.InlineKeyboardButton(f"🔹 {contest['title']}", callback_data=f"show_leaderboard_{contest['id']}"))
    
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("show_leaderboard_"))
def show_leaderboard(call):
    contest_id = int(call.data.replace("show_leaderboard_", ""))
    
    conn = get_db()
    contestants = conn.execute("""
        SELECT name, votes FROM contestants 
        WHERE contest_id = ? 
        ORDER BY votes DESC 
        LIMIT 10
    """, (contest_id,)).fetchall()
    
    contest = conn.execute("SELECT title FROM contests WHERE id = ?", (contest_id,)).fetchone()
    conn.close()
    
    if not contestants:
        text = f"🏆 <b>{contest['title']}</b>\n\n📊 لا يوجد مشاركين بعد"
    else:
        text = f"🏆 <b>{contest['title']}</b>\n\n"
        medals = ["🥇", "🥈", "🥉"]
        
        for i, c in enumerate(contestants, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            text += f"{medal} <b>{c['name']}</b> — {c['votes']} صوت\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh_leaderboard_{contest_id}"))
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="leaderboard"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("refresh_leaderboard_"))
def refresh_leaderboard(call):
    contest_id = int(call.data.replace("refresh_leaderboard_", ""))
    
    conn = get_db()
    contestants = conn.execute("""
        SELECT name, votes FROM contestants 
        WHERE contest_id = ? 
        ORDER BY votes DESC 
        LIMIT 10
    """, (contest_id,)).fetchall()
    
    contest = conn.execute("SELECT title FROM contests WHERE id = ?", (contest_id,)).fetchone()
    conn.close()
    
    text = f"🏆 <b>{contest['title']}</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, c in enumerate(contestants, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} <b>{c['name']}</b> — {c['votes']} صوت\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh_leaderboard_{contest_id}"))
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="leaderboard"))
    
    bot.answer_callback_query(call.id, "✅ تم التحديث")
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

# ================= المشاركة في المسابقة =================
@bot.message_handler(func=lambda m: m.from_user.id in user_states and user_states[m.from_user.id].get("action") == "join_contest")
def handle_join_contest(message):
    user_id = message.from_user.id
    contest_id = user_states[user_id]["contest_id"]
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        bot.send_message(message.chat.id, "❌ الاسم يجب أن يكون بين 2 و 50 حرفاً")
        return
    
    if re.search(r'@|http|t\.me', name):
        bot.send_message(message.chat.id, "❌ الاسم لا يمكن أن يحتوي على روابط")
        return
    
    conn = get_db()
    
    existing = conn.execute("SELECT id FROM contestants WHERE contest_id = ? AND user_id = ?", (contest_id, user_id)).fetchone()
    if existing:
        conn.close()
        bot.send_message(message.chat.id, "❌ لقد شاركت في هذه المسابقة من قبل!")
        del user_states[user_id]
        return
    
    contest = conn.execute("SELECT * FROM contests WHERE id = ? AND active = 1", (contest_id,)).fetchone()
    
    if not contest:
        conn.close()
        bot.send_message(message.chat.id, "❌ هذه المسابقة غير متاحة")
        del user_states[user_id]
        return
    
    cursor = conn.execute("""
        INSERT INTO contestants (contest_id, user_id, name)
        VALUES (?, ?, ?)
    """, (contest_id, user_id, name))
    
    contestant_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    try:
        bot_username = bot.get_me().username
        contest_link = f"https://t.me/{bot_username}?start=contest_{contest_id}"
        
        post_text = f"""🎯 <b>{contest['title']}</b>

👤 <b>{name}</b>

👇 للتصويت اضغط على الزر:"""
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(f"👍 تصويت (0)", callback_data=f"vote_{contest_id}_{contestant_id}"),
            types.InlineKeyboardButton("🎯 المشاركة", url=contest_link)
        )
        
        sent = bot.send_message(int(contest['channel_id']), post_text, reply_markup=keyboard)
        
        conn = get_db()
        conn.execute("UPDATE contestants SET post_id = ? WHERE id = ?", (sent.message_id, contestant_id))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تمت المشاركة بنجاح!\n👤 {name}\n📢 تم نشر اسمك في القناة"
        )
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ: {str(e)}")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

# ================= التصويت =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
def vote_callback(call):
    user_id = call.from_user.id
    parts = call.data.split("_")
    contest_id = int(parts[1])
    contestant_id = int(parts[2])
    
    conn = get_db()
    
    contestant = conn.execute("SELECT user_id, name FROM contestants WHERE id = ?", (contestant_id,)).fetchone()
    if not contestant:
        conn.close()
        bot.answer_callback_query(call.id, "❌ المشارك غير موجود", show_alert=True)
        return
    
    if contestant["user_id"] == user_id:
        conn.close()
        bot.answer_callback_query(call.id, "🚫 لا يمكنك التصويت لنفسك!", show_alert=True)
        return
    
    existing = conn.execute("SELECT id FROM votes WHERE contest_id = ? AND voter_id = ?", (contest_id, user_id)).fetchone()
    if existing:
        conn.close()
        bot.answer_callback_query(call.id, "❌ لقد صوتت في هذه المسابقة من قبل!", show_alert=True)
        return
    
    conn.execute("INSERT INTO votes (contest_id, voter_id, contestant_id) VALUES (?, ?, ?)", (contest_id, user_id, contestant_id))
    conn.execute("UPDATE contestants SET votes = votes + 1 WHERE id = ?", (contestant_id,))
    conn.commit()
    
    new_votes = conn.execute("SELECT votes FROM contestants WHERE id = ?", (contestant_id,)).fetchone()["votes"]
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ تم التصويت!", show_alert=True)
    
    try:
        contest = conn.execute("SELECT channel_id FROM contests WHERE id = ?", (contest_id,)).fetchone()
        if contest:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(f"👍 تصويت ({new_votes})", callback_data=f"vote_{contest_id}_{contestant_id}"),
                types.InlineKeyboardButton("🎯 المشاركة", url=f"https://t.me/{bot.get_me().username}?start=contest_{contest_id}")
            )
            bot.edit_message_reply_markup(int(contest["channel_id"]), call.message.message_id, reply_markup=keyboard)
    except:
        pass

# ================= إضافة/خصم أصوات =================
@bot.callback_query_handler(func=lambda call: call.data in ["add_votes", "remove_votes"])
def votes_action_callback(call):
    user_id = call.from_user.id
    action = call.data
    
    msg = bot.send_message(call.message.chat.id, "📎 أرسل رابط منشور المشارك:")
    bot.register_next_step_handler(msg, get_post_link, action)

def get_post_link(message, action):
    user_id = message.from_user.id
    link = message.text.strip()
    
    try:
        parts = link.split('/')
        username = parts[-2].replace("@", "")
        post_id = int(parts[-1])
        
        conn = get_db()
        contestant = conn.execute("""
            SELECT c.id, c.name, co.owner_id, co.id as contest_id
            FROM contestants c
            JOIN contests co ON c.contest_id = co.id
            WHERE c.post_id = ? AND co.channel_name = ?
        """, (post_id, username)).fetchone()
        
        if not contestant:
            conn.close()
            bot.send_message(message.chat.id, "❌ لم يتم العثور على المشارك")
            return
        
        if contestant["owner_id"] != user_id:
            conn.close()
            bot.send_message(message.chat.id, "⚠️ ليس لديك صلاحية لتعديل هذا المشارك")
            return
        
        user_states[user_id] = {
            "action": f"votes_{action}",
            "contestant_id": contestant["id"],
            "name": contestant["name"]
        }
        
        bot.send_message(message.chat.id, f"👤 {contestant['name']}\n🔢 أرسل عدد الأصوات:")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ رابط غير صحيح: {str(e)}")

@bot.message_handler(func=lambda m: m.from_user.id in user_states and user_states[m.from_user.id].get("action", "").startswith("votes_"))
def process_votes_amount(message):
    user_id = message.from_user.id
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ عدد غير صحيح")
            return
        
        state = user_states[user_id]
        action = state["action"]
        contestant_id = state["contestant_id"]
        
        conn = get_db()
        
        if action == "votes_add_votes":
            conn.execute("UPDATE contestants SET votes = votes + ? WHERE id = ?", (amount, contestant_id))
            action_text = "إضافة"
        else:
            conn.execute("UPDATE contestants SET votes = MAX(0, votes - ?) WHERE id = ?", (amount, contestant_id))
            action_text = "خصم"
        
        conn.commit()
        
        new_votes = conn.execute("SELECT votes, contest_id, post_id, channel_id FROM contestants c JOIN contests co ON c.contest_id = co.id WHERE c.id = ?", (contestant_id,)).fetchone()
        conn.close()
        
        if new_votes:
            try:
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    types.InlineKeyboardButton(f"👍 تصويت ({new_votes['votes']})", callback_data=f"vote_{new_votes['contest_id']}_{contestant_id}"),
                    types.InlineKeyboardButton("🎯 المشاركة", url=f"https://t.me/{bot.get_me().username}?start=contest_{new_votes['contest_id']}")
                )
                bot.edit_message_reply_markup(int(new_votes['channel_id']), new_votes['post_id'], reply_markup=keyboard)
            except:
                pass
        
        bot.send_message(message.chat.id, f"✅ تم {action_text} {amount} صوت")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إرسال عدد صحيح")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

# ================= الإعدادات =================
@bot.callback_query_handler(func=lambda call: call.data == "settings")
def settings_callback(call):
    text = """⚙️ <b>إعدادات البوت</b>

✅ يمكنك تعديل الإعدادات حسب رغبتك

🔹 <b>الإعدادات المتاحة:</b>
• تعيين قناة التصويت
• إدارة المسابقات
• حظر المستخدمين

➡️ استخدم الأزرار أدناه:"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📢 تغيير القناة", callback_data="set_channel"),
        types.InlineKeyboardButton("⛔ حظر عضو", callback_data="ban_user")
    )
    keyboard.add(
        types.InlineKeyboardButton("✅ فك حظر", callback_data="unban_user"),
        types.InlineKeyboardButton("📋 المحظورين", callback_data="banned_list")
    )
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "ban_user")
def ban_user_callback(call):
    msg = bot.send_message(call.message.chat.id, "⛔ أرسل ID العضو للحظر:")
    bot.register_next_step_handler(msg, process_ban)

def process_ban(message):
    try:
        user_id = int(message.text.strip())
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO bans (user_id, reason) VALUES (?, ?)", (user_id, "تم حظره بواسطة المشرف"))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ تم حظر العضو `{user_id}`", parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "unban_user")
def unban_user_callback(call):
    msg = bot.send_message(call.message.chat.id, "✅ أرسل ID العضو لفك الحظر:")
    bot.register_next_step_handler(msg, process_unban)

def process_unban(message):
    try:
        user_id = int(message.text.strip())
        conn = get_db()
        conn.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ تم فك الحظر عن العضو `{user_id}`", parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "banned_list")
def banned_list_callback(call):
    conn = get_db()
    banned = conn.execute("SELECT user_id, reason FROM bans").fetchall()
    conn.close()
    
    if not banned:
        text = "📋 لا يوجد أعضاء محظورين"
    else:
        text = "📋 <b>قائمة المحظورين</b>\n\n"
        for b in banned:
            text += f"🆔 `{b['user_id']}`\n⚖️ {b['reason']}\n\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="settings"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode="Markdown")

# ================= المساعدة =================
@bot.callback_query_handler(func=lambda call: call.data == "help")
def help_callback(call):
    text = """📖 <b>دليل استخدام البوت</b>

🚀 <b>للمشرفين:</b>
1️⃣ ارفع البوت مشرفاً في قناتك
2️⃣ اضغط على '📢 قناة التصويت' لتعيين القناة
3️⃣ اضغط على '🎯 إنشاء مسابقة' لبدء مسابقة جديدة

🏆 <b>للمشاركين:</b>
1️⃣ اضغط على رابط المشاركة
2️⃣ أرسل اسمك
3️⃣ سيتم نشر اسمك في القناة

👍 <b>للتصويت:</b>
اضغط على زر 'تصويت' تحت اسم المشارك

⏰ <b>ملاحظة:</b> يتم حذف المسابقات تلقائياً بعد 24 ساعة

👨‍💻 <b>مطور البوت:</b> عصوم الشامي"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

# ================= حذف المسابقات التلقائي =================
def auto_delete_contests():
    while True:
        try:
            time.sleep(3600)
            
            one_day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            
            conn = get_db()
            old_contests = conn.execute("""
                SELECT id, channel_id, post_id, title, owner_id 
                FROM contests 
                WHERE active = 1 AND created_at < ?
            """, (one_day_ago,)).fetchall()
            
            for contest in old_contests:
                try:
                    bot.delete_message(int(contest["channel_id"]), contest["post_id"])
                except:
                    pass
                
                conn.execute("UPDATE contests SET active = 0 WHERE id = ?", (contest["id"],))
                conn.commit()
                
                try:
                    bot.send_message(
                        contest["owner_id"],
                        f"🗑️ <b>تم حذف المسابقة</b>\n\n📌 {contest['title']}\n⏰ بعد 24 ساعة من إنشائها"
                    )
                except:
                    pass
            
            conn.close()
            
        except Exception as e:
            print(f"Error in auto delete: {e}")

delete_thread = threading.Thread(target=auto_delete_contests, daemon=True)
delete_thread.start()

# ================= مسار الويب هوك =================
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def home():
    return "✅ Bot is running on Railway!"

# ================= تشغيل البوت =================
if __name__ == "__main__":
    print("🚀 تشغيل البوت على Railway...")
    
    # حذف أي ويب هوك سابق
    bot.delete_webhook()
    time.sleep(1)
    
    # تعيين الويب هوك الجديد
    PORT = int(os.environ.get('PORT', 8080))
    WEBHOOK_URL = f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost')}/{TOKEN}"
    
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"✅ Webhook set to: {WEBHOOK_URL}")
    
    # إضافة الأدمن الأساسي
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()
    
    print("✅ البوت جاهز للعمل!")
    
    app.run(host='0.0.0.0', port=PORT)
