import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import re
import os
from functools import wraps

# ================= التوكن والإعدادات =================
TOKEN = "8600057182:AAGImzI3A7IjGSoEPT2JUpg2-QJ1ukNkbAA"
ADMIN_ID = 6599083480
SUPPORT_USERNAME = "asoom993"
UPDATES_CHANNEL = "talemathackr3"
DEV_CHANNEL = "asoom_993"
BOT_USERNAME = ""
START_IMAGE_URL = "https://i.postimg.cc/Mpc5Ssmt/IMG-20260430-084401-176.jpg"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# حالات المستخدمين المؤقتة
user_states = {}

# ================= إنشاء قاعدة البيانات =================
def get_db():
    conn = sqlite3.connect("contest_bot.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # جدول الإعدادات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY,
        vote_channel TEXT,
        auto_approve INTEGER DEFAULT 1
    )
    """)
    
    # جدول المسابقات
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
    
    # جدول المشاركين
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
    
    # جدول التصويتات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id INTEGER,
        voter_id INTEGER,
        contestant_id INTEGER,
        UNIQUE(contest_id, voter_id)
    )
    """)
    
    # جدول المحظورين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bans (
        user_id INTEGER PRIMARY KEY,
        reason TEXT
    )
    """)
    
    # جدول الأدمن
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )
    """)
    
    # جدول المستخدمين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        join_date TEXT
    )
    """)
    
    # جدول قنوات الاشتراك الإجباري
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS force_subs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        channel_username TEXT
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ تم تجهيز قاعدة البيانات")

init_db()

# ================= التحقق من الاشتراك الإجباري =================
def check_force_sub(user_id):
    conn = get_db()
    channels = conn.execute("SELECT channel_id, channel_username FROM force_subs").fetchall()
    conn.close()
    
    if not channels:
        return True, []
    
    not_subscribed = []
    for ch in channels:
        try:
            member = bot.get_chat_member(int(ch[0]), user_id)
            if member.status not in ["member", "administrator", "creator"]:
                not_subscribed.append(ch)
        except:
            not_subscribed.append(ch)
    
    return len(not_subscribed) == 0, not_subscribed

def force_sub_required(func):
    @wraps(func)
    def wrapper(message_or_call):
        user_id = None
        if isinstance(message_or_call, types.Message):
            user_id = message_or_call.from_user.id
        else:
            user_id = message_or_call.from_user.id
        
        if user_id == ADMIN_ID:
            return func(message_or_call)
        
        subscribed, channels = check_force_sub(user_id)
        if not subscribed:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for ch in channels:
                keyboard.add(types.InlineKeyboardButton(f"📢 اشترك في القناة", url=f"https://t.me/{ch[1]}"))
            keyboard.add(types.InlineKeyboardButton("🔄 تحقق", callback_data="check_sub"))
            
            msg = "❌ يجب الاشتراك في القنوات التالية أولاً:\n\n"
            for ch in channels:
                msg += f"• @{ch[1]}\n"
            
            if isinstance(message_or_call, types.Message):
                bot.send_message(message_or_call.chat.id, msg, reply_markup=keyboard)
            else:
                bot.edit_message_text(msg, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=keyboard)
            return None
        
        return func(message_or_call)
    return wrapper

# ================= الأزرار الرئيسية =================
def main_keyboard(user_id):
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
    keyboard.add(
        types.InlineKeyboardButton("📣 قنوات التواصل", callback_data="channels")
    )
    
    conn = get_db()
    is_admin = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if is_admin or str(user_id) == str(ADMIN_ID):
        keyboard.add(types.InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel"))
    
    return keyboard

def send_main_menu(chat_id, user_id):
    text = """🌟 <b>مرحباً بك في بوت المسابقات!</b> 🌟

▫️ البوت يدير المسابقات بشكل تلقائي
▫️ يمكن للمستخدمين المشاركة والتصويت
▫️ يتم حذف المسابقات بعد 24 ساعة

👨‍💻 <b>مطور البوت:</b> عصوم الشامي

اختر الإجراء المناسب:"""
    
    if START_IMAGE_URL:
        try:
            bot.send_photo(chat_id, START_IMAGE_URL, caption=text, reply_markup=main_keyboard(user_id))
            return
        except:
            pass
    
    bot.send_message(chat_id, text, reply_markup=main_keyboard(user_id))

# ================= بدء البوت =================
@bot.message_handler(commands=['start'])
@force_sub_required
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (id, username, join_date) VALUES (?, ?, ?)", (user_id, username, join_date))
    conn.commit()
    
    # التحقق من حظر
    banned = conn.execute("SELECT user_id FROM bans WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if banned:
        bot.send_message(message.chat.id, "🚫 حسابك محظور من استخدام البوت!")
        return
    
    # التحقق من رابط مسابقة
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
                    "🎯 <b>المشاركة في المسابقة</b>\n\nأرسل اسمك الآن للمشاركة:",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel")
                    )
                )
                return
    
    send_main_menu(message.chat.id, user_id)

# ================= زر الإلغاء =================
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

# ================= زر القائمة الرئيسية =================
@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu_callback(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    send_main_menu(call.message.chat.id, call.from_user.id)

# ================= قنوات التواصل =================
@bot.callback_query_handler(func=lambda call: call.data == "channels")
def channels_callback(call):
    text = f"""📣 <b>قنوات التواصل</b>

📢 <b>قناة التحديثات:</b> @{UPDATES_CHANNEL}
👨‍💻 <b>قناة المطور:</b> @{DEV_CHANNEL}
🆘 <b>الدعم الفني:</b> @{SUPPORT_USERNAME}

تابعنا ليصلك كل جديد!"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

# ================= التحقق من الاشتراك =================
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    subscribed, channels = check_force_sub(call.from_user.id)
    if subscribed:
        bot.answer_callback_query(call.id, "✅ تم التحقق! أنت مشترك في جميع القنوات.", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_main_menu(call.message.chat.id, call.from_user.id)
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات بعد!", show_alert=True)

# ================= عداد تنازلي =================
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

def get_time_until_end(created_at):
    try:
        created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        end = created + timedelta(days=1)
        now = datetime.now()
        
        if now >= end:
            return 0
        
        remaining = end - now
        return remaining.total_seconds()
    except:
        return 86400

# ============================== دوال المسابقات ==============================

# إنشاء مسابقة
@bot.callback_query_handler(func=lambda call: call.data == "create_contest")
@force_sub_required
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
    
    if not title or len(title) < 3:
        bot.send_message(message.chat.id, "❌ عنوان غير صالح (يجب أن يكون 3 أحرف على الأقل)")
        return
    
    user_states[user_id] = {"title": title}
    msg = bot.send_message(message.chat.id, "📝 أرسل وصف المسابقة والجوائز:")
    bot.register_next_step_handler(msg, get_contest_desc)

def get_contest_desc(message):
    user_id = message.from_user.id
    desc = message.text.strip()
    title = user_states[user_id]["title"]
    
    if not desc or len(desc) < 5:
        bot.send_message(message.chat.id, "❌ وصف غير صالح (يجب أن يكون 5 أحرف على الأقل)")
        return
    
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
        keyboard.add(types.InlineKeyboardButton("📤 مشاركة المشاركة", url=contest_link))
        
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

# تعيين قناة التصويت
@bot.callback_query_handler(func=lambda call: call.data == "set_channel")
@force_sub_required
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
        
        if chat.type not in ["channel", "supergroup"]:
            bot.send_message(message.chat.id, "❌ هذا ليس قناة!")
            return
        
        # التحقق من صلاحيات البوت
        bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
        if bot_member.status != "administrator":
            bot.send_message(message.chat.id, "❌ البوت ليس مشرفاً في هذه القناة!\nيرجى رفع البوت مشرف أولاً.")
            return
        
        # التحقق من أن المستخدم مشرف
        user_member = bot.get_chat_member(chat.id, user_id)
        if user_member.status not in ["administrator", "creator"] and str(user_id) != str(ADMIN_ID):
            bot.send_message(message.chat.id, "❌ يجب أن تكون مشرفاً في القناة لتعيينها!")
            return
        
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (user_id, vote_channel) VALUES (?, ?)", (user_id, str(chat.id)))
        conn.commit()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ تم تعيين القناة بنجاح!\n\n📢 <b>{chat.title}</b>\n🆔 `{chat.id}`",
            parse_mode="Markdown"
        )
        send_main_menu(message.chat.id, user_id)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}\nتأكد من صحة الرابط وأن البوت مضاف للقناة.")

# مسابقاتي
@bot.callback_query_handler(func=lambda call: call.data == "my_contests")
@force_sub_required
def my_contests_callback(call):
    user_id = call.from_user.id
    page = user_states.get(user_id, {}).get("contests_page", 1)
    per_page = 5
    
    conn = get_db()
    contests = conn.execute("""
        SELECT * FROM contests 
        WHERE owner_id = ? AND active = 1 
        ORDER BY id DESC 
        LIMIT ? OFFSET ?
    """, (user_id, per_page, (page - 1) * per_page)).fetchall()
    
    total = conn.execute("SELECT COUNT(*) FROM contests WHERE owner_id = ? AND active = 1", (user_id,)).fetchone()[0]
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    conn.close()
    
    if not contests:
        bot.edit_message_text(
            "📋 لا توجد مسابقات نشطة.\n\n🎯 اضغط على 'إنشاء مسابقة' لبدء مسابقة جديدة",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🎯 إنشاء مسابقة", callback_data="create_contest"),
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
    
    text += f"📄 الصفحة {page} من {total_pages}"
    
    keyboard = types.InlineKeyboardMarkup()
    
    # أزرار التنقل بين الصفحات
    if page > 1:
        keyboard.add(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"contests_page_{page-1}"))
    if page < total_pages:
        keyboard.add(types.InlineKeyboardButton("التالي ➡️", callback_data=f"contests_page_{page+1}"))
    
    keyboard.add(types.InlineKeyboardButton("➕ مسابقة جديدة", callback_data="create_contest"))
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("contests_page_"))
def contests_page_callback(call):
    page = int(call.data.replace("contests_page_", ""))
    user_states[call.from_user.id] = {"contests_page": page}
    
    # إعادة عرض المسابقات
    my_contests_callback(call)

# جدول المتصدرين
@bot.callback_query_handler(func=lambda call: call.data == "leaderboard")
@force_sub_required
def leaderboard_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    contests = conn.execute("SELECT id, title FROM contests WHERE owner_id = ? AND active = 1", (user_id,)).fetchall()
    conn.close()
    
    if not contests:
        bot.answer_callback_query(call.id, "لا توجد مسابقات نشطة!", show_alert=True)
        return
    
    text = "🏆 <b>اختر المسابقة لعرض جدول المتصدرين</b>\n\n"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for contest in contests:
        keyboard.add(types.InlineKeyboardButton(f"🎯 {contest['title']}", callback_data=f"show_leaderboard_{contest['id']}"))
    
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
    
    contest = conn.execute("SELECT title, created_at FROM contests WHERE id = ?", (contest_id,)).fetchone()
    conn.close()
    
    time_left = get_time_remaining(contest["created_at"]) if contest else ""
    
    if not contestants:
        text = f"🏆 <b>{contest['title']}</b>\n{time_left}\n\n📊 لا يوجد مشاركين بعد"
    else:
        text = f"🏆 <b>{contest['title']}</b>\n{time_left}\n\n"
        medals = ["🥇", "🥈", "🥉"]
        
        for i, c in enumerate(contestants, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            text += f"{medal} <b>{c['name']}</b> — {c['votes']} صوت\n"
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh_leaderboard_{contest_id}"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="leaderboard")
    )
    
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
    
    contest = conn.execute("SELECT title, created_at FROM contests WHERE id = ?", (contest_id,)).fetchone()
    conn.close()
    
    time_left = get_time_remaining(contest["created_at"])
    
    text = f"🏆 <b>{contest['title']}</b>\n{time_left}\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, c in enumerate(contestants, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} <b>{c['name']}</b> — {c['votes']} صوت\n"
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh_leaderboard_{contest_id}"),
        types.InlineKeyboardButton("↩️ رجوع", callback_data="leaderboard")
    )
    
    bot.answer_callback_query(call.id, "✅ تم تحديث جدول المتصدرين")
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

# ============================== المشاركة والتصويت ==============================

# المشاركة في المسابقة
@bot.message_handler(func=lambda m: m.from_user.id in user_states and user_states[m.from_user.id].get("action") == "join_contest")
@force_sub_required
def handle_join_contest(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    contest_id = state["contest_id"]
    name = message.text.strip()
    
    # التحقق من الاسم
    if len(name) < 2 or len(name) > 50:
        bot.send_message(message.chat.id, "❌ الاسم يجب أن يكون بين 2 و 50 حرفاً")
        return
    
    if re.search(r'@|http|t\.me|bit\.ly|\.com', name, re.IGNORECASE):
        bot.send_message(message.chat.id, "❌ الاسم لا يمكن أن يحتوي على روابط أو يوزرات")
        return
    
    conn = get_db()
    
    # التحقق من وجود المسابقة
    contest = conn.execute("SELECT * FROM contests WHERE id = ? AND active = 1", (contest_id,)).fetchone()
    
    if not contest:
        conn.close()
        bot.send_message(message.chat.id, "❌ هذه المسابقة غير متاحة")
        del user_states[user_id]
        return
    
    # التحقق من المشاركة السابقة
    existing = conn.execute("SELECT id FROM contestants WHERE contest_id = ? AND user_id = ?", (contest_id, user_id)).fetchone()
    if existing:
        conn.close()
        bot.send_message(message.chat.id, "❌ لقد شاركت في هذه المسابقة من قبل!")
        del user_states[user_id]
        return
    
    # إضافة المتسابق
    cursor = conn.execute("""
        INSERT INTO contestants (contest_id, user_id, name)
        VALUES (?, ?, ?)
    """, (contest_id, user_id, name))
    
    contestant_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إنشاء منشور المشارك في القناة
    try:
        bot_username = bot.get_me().username
        contest_link = f"https://t.me/{bot_username}?start=contest_{contest_id}"
        
        post_text = f"""🎯 <b>{contest['title']}</b>

👤 <b>{name}</b>

👇 للتصويت اضغط على الزر أدناه:

⚠️ يجب الاشتراك في القناة للتصويت!"""
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(f"👍 تصويت (0)", callback_data=f"vote_{contest_id}_{contestant_id}"),
            types.InlineKeyboardButton("🎯 المشاركة", url=contest_link)
        )
        keyboard.add(types.InlineKeyboardButton("📤 مشاركة المنشور", switch_inline_query=f"اشترك في مسابقة {contest['title']}"))
        
        sent = bot.send_message(int(contest['channel_id']), post_text, reply_markup=keyboard)
        
        conn = get_db()
        conn.execute("UPDATE contestants SET post_id = ? WHERE id = ?", (sent.message_id, contestant_id))
        conn.commit()
        conn.close()
        
        private_link = f"https://t.me/{bot_username}?start=contest_{contest_id}"
        
        bot.send_message(
            message.chat.id,
            f"✅ تمت المشاركة بنجاح!\n\n"
            f"👤 <b>اسمك:</b> {name}\n"
            f"📢 <b>تم نشر اسمك في القناة</b>\n\n"
            f"🔗 <b>رابط المشاركة:</b>\n{private_link}\n\n"
            f"👍 شارك الرابط مع أصدقائك ليصوتوا لك!"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ في النشر: {str(e)}")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

# التصويت
@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
@force_sub_required
def vote_callback(call):
    user_id = call.from_user.id
    parts = call.data.split("_")
    contest_id = int(parts[1])
    contestant_id = int(parts[2])
    
    # التحقق من أن المصوت ليس نفسه
    conn = get_db()
    contestant = conn.execute("SELECT user_id, name, contest_id FROM contestants WHERE id = ?", (contestant_id,)).fetchone()
    
    if not contestant:
        conn.close()
        bot.answer_callback_query(call.id, "❌ المشارك غير موجود", show_alert=True)
        return
    
    if contestant["user_id"] == user_id:
        conn.close()
        bot.answer_callback_query(call.id, "🚫 لا يمكنك التصويت لنفسك!", show_alert=True)
        return
    
    # التحقق من التصويت المكرر
    existing = conn.execute("SELECT id FROM votes WHERE contest_id = ? AND voter_id = ?", (contest_id, user_id)).fetchone()
    if existing:
        conn.close()
        bot.answer_callback_query(call.id, "❌ لقد صوتت في هذه المسابقة من قبل!", show_alert=True)
        return
    
    # تسجيل التصويت
    conn.execute("INSERT INTO votes (contest_id, voter_id, contestant_id) VALUES (?, ?, ?)", (contest_id, user_id, contestant_id))
    conn.execute("UPDATE contestants SET votes = votes + 1 WHERE id = ?", (contestant_id,))
    conn.commit()
    
    # الحصول على العدد الجديد ومعلومات المنشور
    info = conn.execute("""
        SELECT c.votes, c.post_id, co.channel_id 
        FROM contestants c 
        JOIN contests co ON c.contest_id = co.id 
        WHERE c.id = ?
    """, (contestant_id,)).fetchone()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ تم التصويت!", show_alert=True)
    
    # تحديث الزر
    if info and info["post_id"]:
        try:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(f"👍 تصويت ({info['votes']})", callback_data=f"vote_{contest_id}_{contestant_id}"),
                types.InlineKeyboardButton("🎯 المشاركة", url=f"https://t.me/{bot.get_me().username}?start=contest_{contest_id}")
            )
            keyboard.add(types.InlineKeyboardButton("📤 مشاركة المنشور", switch_inline_query=f"صوت للمشارك {contestant['name']}"))
            bot.edit_message_reply_markup(int(info["channel_id"]), info["post_id"], reply_markup=keyboard)
        except:
            pass

# ============================== إدارة الأصوات ==============================

# إضافة/خصم أصوات
@bot.callback_query_handler(func=lambda call: call.data in ["add_votes", "remove_votes"])
@force_sub_required
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
        conn.close()
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ رابط غير صحيح: {str(e)}")

@bot.message_handler(func=lambda m: m.from_user.id in user_states and user_states[m.from_user.id].get("action", "").startswith("votes_"))
@force_sub_required
def process_votes_amount(message):
    user_id = message.from_user.id
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ عدد غير صحيح (يجب أن يكون أكبر من 0)")
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
        
        # تحديث المنشور
        info = conn.execute("""
            SELECT c.votes, c.post_id, co.channel_id, co.id as contest_id
            FROM contestants c 
            JOIN contests co ON c.contest_id = co.id 
            WHERE c.id = ?
        """, (contestant_id,)).fetchone()
        
        if info and info["post_id"]:
            try:
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    types.InlineKeyboardButton(f"👍 تصويت ({info['votes']})", callback_data=f"vote_{info['contest_id']}_{contestant_id}"),
                    types.InlineKeyboardButton("🎯 المشاركة", url=f"https://t.me/{bot.get_me().username}?start=contest_{info['contest_id']}")
                )
                bot.edit_message_reply_markup(int(info["channel_id"]), info["post_id"], reply_markup=keyboard)
            except:
                pass
        
        conn.close()
        bot.send_message(message.chat.id, f"✅ تم {action_text} {amount} صوت بنجاح!")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إرسال عدد صحيح")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

# ============================== الإعدادات ==============================

@bot.callback_query_handler(func=lambda call: call.data == "settings")
@force_sub_required
def settings_callback(call):
    text = """⚙️ <b>إعدادات البوت</b>

🔹 <b>الإعدادات المتاحة:</b>
• تعيين قناة التصويت
• حظر المستخدمين
• عرض المحظورين

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
@force_sub_required
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
        send_main_menu(message.chat.id, message.from_user.id)
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "unban_user")
@force_sub_required
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
        send_main_menu(message.chat.id, message.from_user.id)
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "banned_list")
@force_sub_required
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

# ============================== المساعدة والمميزات ==============================

@bot.callback_query_handler(func=lambda call: call.data == "help")
@force_sub_required
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
1️⃣ اشترك في قناة المسابقة
2️⃣ اضغط على زر 'تصويت' تحت اسم المشارك

➕ <b>إضافة أصوات:</b>
1️⃣ اضغط على '➕ إضافة أصوات'
2️⃣ أرسل رابط منشور المشارك
3️⃣ أرسل عدد الأصوات

⏰ <b>ملاحظة:</b> يتم حذف المسابقات تلقائياً بعد 24 ساعة

👨‍💻 <b>مطور البوت:</b> عصوم الشامي"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "features")
@force_sub_required
def features_callback(call):
    text = """⚡ <b>مميزات بوت المسابقات</b>

✅ <b>المميزات:</b>
1️⃣ 🎯 إنشاء مسابقات تلقائية بالكامل
2️⃣ 📊 جدول متصدرين محدث تلقائياً
3️⃣ ⏰ عداد تنازلي للوقت
4️⃣ 📄 صفحات متعددة للمسابقات
5️⃣ 🎨 أزرار ملونة وايموجيات
6️⃣ 🗑️ حذف تلقائي بعد 24 ساعة
7️⃣ 🚫 منع التصويت للنفس
8️⃣ ☝️ تصويت مرة واحدة فقط
9️⃣ 🔒 اشتراك إجباري في القنوات
🔟 👑 لوحة تحكم إدارية كاملة

🔥 <b>تم التطوير بواسطة:</b> عصوم الشامي"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

# ============================== حذف المسابقات التلقائي ==============================

def auto_delete_contests():
    while True:
        try:
            time.sleep(3600)  # كل ساعة
            
            conn = get_db()
            one_day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            
            old_contests = conn.execute("""
                SELECT id, channel_id, post_id, title, owner_id, created_at
                FROM contests 
                WHERE active = 1 AND created_at < ?
            """, (one_day_ago,)).fetchall()
            
            for contest in old_contests:
                # حذف منشور المسابقة
                try:
                    bot.delete_message(int(contest["channel_id"]), contest["post_id"])
                except:
                    pass
                
                # تحديث حالة المسابقة
                conn.execute("UPDATE contests SET active = 0 WHERE id = ?", (contest["id"],))
                conn.commit()
                
                # إشعار المالك
                try:
                    bot.send_message(
                        contest["owner_id"],
                        f"🗑️ <b>تم حذف المسابقة</b>\n\n"
                        f"📌 {contest['title']}\n"
                        f"🆔 #{contest['id']}\n"
                        f"⏰ تم الحذف بعد 24 ساعة من إنشائها"
                    )
                except:
                    pass
            
            conn.close()
            
        except Exception as e:
            print(f"خطأ في الحذف التلقائي: {e}")

delete_thread = threading.Thread(target=auto_delete_contests, daemon=True)
delete_thread.start()

# ============================== لوحة تحكم الأدمن ==============================

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
@force_sub_required
def admin_panel_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    is_admin = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not is_admin and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    text = "👑 <b>لوحة التحكم الإدارية</b>\n\nاختر الإدارة التي تريدها:"
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users")
    )
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin"),
        types.InlineKeyboardButton("🗑 حذف أدمن", callback_data="remove_admin")
    )
    keyboard.add(
        types.InlineKeyboardButton("📢 قنوات اشتراك", callback_data="admin_force_subs"),
        types.InlineKeyboardButton("📣 قنوات التواصل", callback_data="channels")
    )
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats_callback(call):
    conn = get_db()
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    contests_count = conn.execute("SELECT COUNT(*) FROM contests").fetchone()[0]
    contestants_count = conn.execute("SELECT COUNT(*) FROM contestants").fetchone()[0]
    votes_count = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    conn.close()
    
    text = f"""📊 <b>إحصائيات البوت</b>

👥 المستخدمين: {users_count}
🎯 المسابقات: {contests_count}
🏆 المتسابقين: {contestants_count}
👍 التصويتات: {votes_count}
⏰ الحذف التلقائي: مفعل (24 ساعة)"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="admin_panel"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "admin_users")
def admin_users_callback(call):
    conn = get_db()
    users = conn.execute("SELECT id, username, join_date FROM users ORDER BY join_date DESC LIMIT 20").fetchall()
    conn.close()
    
    if not users:
        text = "👥 لا يوجد مستخدمين بعد"
    else:
        text = "👥 <b>آخر المستخدمين</b>\n\n"
        for user in users:
            username = f"@{user['username']}" if user['username'] else f"🆔 {user['id']}"
            text += f"• {username}\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="admin_panel"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "add_admin")
def add_admin_callback(call):
    msg = bot.send_message(call.message.chat.id, "👨‍💼 أرسل ID العضو لإضافته كأدمن:")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    try:
        user_id = int(message.text.strip())
        user = bot.get_chat(user_id)
        
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم إضافة `@{user.username}` كأدمن", parse_mode="Markdown")
        send_main_menu(message.chat.id, message.from_user.id)
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "remove_admin")
def remove_admin_callback(call):
    msg = bot.send_message(call.message.chat.id, "🗑 أرسل ID العضو لحذفه من الأدمن:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    try:
        user_id = int(message.text.strip())
        
        if user_id == ADMIN_ID:
            bot.send_message(message.chat.id, "❌ لا يمكن حذف المطور الرئيسي")
            return
        
        conn = get_db()
        conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم حذف العضو `{user_id}` من الأدمن", parse_mode="Markdown")
        send_main_menu(message.chat.id, message.from_user.id)
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "admin_force_subs")
def admin_force_subs_callback(call):
    text = """📢 <b>إدارة قنوات الاشتراك الإجباري</b>

يمكنك إضافة قنوات يجب على المستخدمين الاشتراك فيها قبل استخدام البوت."""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة قناة", callback_data="add_force_sub"),
        types.InlineKeyboardButton("🗑 حذف قناة", callback_data="remove_force_sub"),
        types.InlineKeyboardButton("📋 عرض القنوات", callback_data="list_force_subs")
    )
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="admin_panel"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "add_force_sub")
def add_force_sub_callback(call):
    msg = bot.send_message(call.message.chat.id, "📢 أرسل معرف القناة (مثال: @username):")
    bot.register_next_step_handler(msg, process_add_force_sub)

def process_add_force_sub(message):
    channel_input = message.text.strip()
    if not channel_input.startswith("@"):
        channel_input = "@" + channel_input
    
    try:
        chat = bot.get_chat(channel_input)
        
        # التحقق من أن البوت مشرف
        bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
        if bot_member.status != "administrator":
            bot.send_message(message.chat.id, "❌ البوت ليس مشرفاً في هذه القناة!")
            return
        
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO force_subs (channel_id, channel_username) VALUES (?, ?)", 
                     (str(chat.id), chat.username))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم إضافة القناة @{chat.username} إلى الاشتراك الإجباري")
        send_main_menu(message.chat.id, message.from_user.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "remove_force_sub")
def remove_force_sub_callback(call):
    conn = get_db()
    channels = conn.execute("SELECT id, channel_username FROM force_subs").fetchall()
    conn.close()
    
    if not channels:
        bot.answer_callback_query(call.id, "لا توجد قنوات مسجلة!", show_alert=True)
        return
    
    text = "🗑 <b>اختر القناة لحذفها:</b>\n\n"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for ch in channels:
        keyboard.add(types.InlineKeyboardButton(f"📢 @{ch['channel_username']}", callback_data=f"remove_channel_{ch['id']}"))
    
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="admin_force_subs"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_channel_"))
def remove_channel_callback(call):
    channel_id = int(call.data.replace("remove_channel_", ""))
    
    conn = get_db()
    conn.execute("DELETE FROM force_subs WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ تم حذف القناة من الاشتراك الإجباري", show_alert=True)
    admin_force_subs_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "list_force_subs")
def list_force_subs_callback(call):
    conn = get_db()
    channels = conn.execute("SELECT channel_id, channel_username FROM force_subs").fetchall()
    conn.close()
    
    if not channels:
        text = "📋 لا توجد قنوات اشتراك إجباري"
    else:
        text = "📋 <b>قنوات الاشتراك الإجباري</b>\n\n"
        for ch in channels:
            text += f"• @{ch['channel_username']}\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="admin_force_subs"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

# ============================== تشغيل البوت ==============================

if __name__ == "__main__":
    print("🚀 تشغيل بوت المسابقات...")
    print("✅ أزرار ملونة")
    print("✅ صفحات متعددة")
    print("✅ عداد تنازلي")
    print("✅ جدول متصدرين")
    print("✅ ايموجيات مميزة")
    print("✅ حذف تلقائي")
    print("✅ إدارة أدمن كاملة")
    print("✅ قنوات اشتراك إجباري")
    
    # إضافة الأدمن الأساسي
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ خطأ: {e}")
        time.sleep(3)
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
