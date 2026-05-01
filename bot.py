import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import re
import os
import random
from functools import wraps

# ================= التوكن والإعدادات =================
TOKEN = "8600057182:AAGImzI3A7IjGSoEPT2JUpg2-QJ1ukNkbAA"
ADMIN_ID = 6599083480
SUPPORT_USERNAME = "asoom993"
UPDATES_CHANNEL = "talemathackr3"
DEV_CHANNEL = "asoom_993"
START_IMAGE_URL = "https://i.postimg.cc/Mpc5Ssmt/IMG-20260430-084401-176.jpg"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# حالات المستخدمين المؤقتة
user_states = {}
user_languages = {}

# ================= إنشاء قاعدة البيانات =================
def get_db():
    conn = sqlite3.connect("contest_bot.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY,
        vote_channel TEXT,
        theme TEXT DEFAULT 'default',
        sound INTEGER DEFAULT 1
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
        active INTEGER DEFAULT 1,
        target_votes INTEGER DEFAULT 0,
        winner_id INTEGER DEFAULT NULL,
        winner_name TEXT DEFAULT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contestants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id INTEGER,
        user_id INTEGER,
        name TEXT,
        votes INTEGER DEFAULT 0,
        post_id INTEGER
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id INTEGER,
        voter_id INTEGER,
        contestant_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(contest_id, voter_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bans (
        user_id INTEGER PRIMARY KEY,
        reason TEXT,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        join_date TEXT,
        language TEXT DEFAULT 'ar',
        badge_level INTEGER DEFAULT 0,
        total_votes INTEGER DEFAULT 0,
        total_contests INTEGER DEFAULT 0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS force_subs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        channel_username TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS badges (
        user_id INTEGER,
        badge_type TEXT,
        earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, badge_type)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad_text TEXT,
        ad_url TEXT,
        views INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS polls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        options TEXT,
        votes TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS poll_votes (
        poll_id INTEGER,
        user_id INTEGER,
        option_index INTEGER,
        PRIMARY KEY (poll_id, user_id)
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ تم تجهيز قاعدة البيانات")

init_db()

# ================= التحقق من الاشتراك =================
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
                try:
                    bot.edit_message_text(msg, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=keyboard)
                except:
                    bot.send_message(message_or_call.message.chat.id, msg, reply_markup=keyboard)
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
        types.InlineKeyboardButton("🏅 شاراتي", callback_data="my_badges")
    )
    keyboard.add(
        types.InlineKeyboardButton("📊 استطلاع رأي", callback_data="poll_menu"),
        types.InlineKeyboardButton("🌍 اللغة", callback_data="language_menu")
    )
    keyboard.add(
        types.InlineKeyboardButton("📖 المساعدة", callback_data="help"),
        types.InlineKeyboardButton("📣 قنوات التواصل", callback_data="channels")
    )
    
    conn = get_db()
    is_admin = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if is_admin or str(user_id) == str(ADMIN_ID):
        keyboard.add(types.InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel"))
    
    return keyboard

def send_main_menu(chat_id, user_id):
    text = "🌟 مرحباً بك في بوت المسابقات!\n\nاختر الإجراء المناسب:\n\n👨‍💻 مطور البوت: عصوم الشامي"
    
    if START_IMAGE_URL:
        try:
            bot.send_photo(chat_id, START_IMAGE_URL, caption=text, reply_markup=main_keyboard(user_id))
            return
        except:
            pass
    
    bot.send_message(chat_id, text, reply_markup=main_keyboard(user_id))

# ================= بدء البوت =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (id, username, join_date) VALUES (?, ?, ?)", (user_id, username, join_date))
    conn.commit()
    
    banned = conn.execute("SELECT user_id FROM bans WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if banned:
        bot.send_message(message.chat.id, "🚫 حسابك محظور من استخدام البوت!")
        return
    
    if user_id not in user_languages:
        user_languages[user_id] = 'ar'
    
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
                    "🎯 المشاركة في المسابقة\n\nأرسل اسمك الآن للمشاركة:",
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

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    subscribed, channels = check_force_sub(call.from_user.id)
    if subscribed:
        bot.answer_callback_query(call.id, "✅ تم التحقق! أنت مشترك في جميع القنوات.", show_alert=True)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        send_main_menu(call.message.chat.id, call.from_user.id)
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات بعد!", show_alert=True)

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

# ================= قائمة اللغات =================
@bot.callback_query_handler(func=lambda call: call.data == "language_menu")
def language_menu_callback(call):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
    )
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text("🌍 اختر لغتك / Choose your language", 
                            call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, "🌍 اختر لغتك", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def set_language_callback(call):
    user_id = call.from_user.id
    lang = call.data.replace("set_lang_", "")
    user_languages[user_id] = lang
    
    conn = get_db()
    conn.execute("UPDATE users SET language = ? WHERE id = ?", (lang, user_id))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ تم تغيير اللغة")
    send_main_menu(call.message.chat.id, user_id)

# ================= شاراتي =================
@bot.callback_query_handler(func=lambda call: call.data == "my_badges")
def my_badges_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    badges = conn.execute("SELECT badge_type FROM badges WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    
    if not badges:
        text = "🏅 لا توجد شارات حتى الآن\n\nشارك في المسابقات للحصول على شارات!"
    else:
        badge_names = {
            'first_win': '🏆 الفائز الأول',
            'voter': '🗳️ المصوت النشط',
            'creator': '🎯 منشئ المسابقات'
        }
        
        text = "🏅 <b>شاراتي</b>\n\n"
        for badge in badges:
            name = badge_names.get(badge['badge_type'], badge['badge_type'])
            text += f"• {name}\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

def award_badge(user_id, badge_type):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO badges (user_id, badge_type) VALUES (?, ?)", (user_id, badge_type))
    conn.commit()
    conn.close()

# ================= نظام التسليم التلقائي =================
def check_winner(contest_id, contestant_id, new_votes):
    conn = get_db()
    
    contest = conn.execute("SELECT target_votes, winner_id FROM contests WHERE id = ?", (contest_id,)).fetchone()
    
    if not contest or contest['winner_id'] is not None:
        conn.close()
        return False
    
    target_votes = contest['target_votes']
    if target_votes > 0 and new_votes >= target_votes:
        contestant = conn.execute("SELECT user_id, name FROM contestants WHERE id = ?", (contestant_id,)).fetchone()
        
        if contestant:
            conn.execute("UPDATE contests SET winner_id = ?, winner_name = ? WHERE id = ?", 
                        (contestant['user_id'], contestant['name'], contest_id))
            conn.commit()
            
            try:
                bot.send_message(contestant['user_id'], f"🏆 مبروك! لقد فزت في المسابقة!")
            except:
                pass
            
            award_badge(contestant['user_id'], 'first_win')
            conn.close()
            return True
    
    conn.close()
    return False

# ================= نظام الاستطلاعات =================
def create_poll(question, options, created_by):
    options_json = ",".join(options)
    votes_json = ",".join(["0"] * len(options))
    
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO polls (question, options, votes, created_by)
        VALUES (?, ?, ?, ?)
    """, (question, options_json, votes_json, created_by))
    poll_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return poll_id

def vote_in_poll(poll_id, user_id, option_index):
    conn = get_db()
    
    existing = conn.execute("SELECT * FROM poll_votes WHERE poll_id = ? AND user_id = ?", (poll_id, user_id)).fetchone()
    if existing:
        conn.close()
        return False
    
    conn.execute("INSERT INTO poll_votes (poll_id, user_id, option_index) VALUES (?, ?, ?)", (poll_id, user_id, option_index))
    
    poll = conn.execute("SELECT votes FROM polls WHERE id = ?", (poll_id,)).fetchone()
    votes_list = poll['votes'].split(",")
    votes_list[option_index] = str(int(votes_list[option_index]) + 1)
    conn.execute("UPDATE polls SET votes = ? WHERE id = ?", (",".join(votes_list), poll_id))
    
    conn.commit()
    conn.close()
    return True

def get_poll_results(poll_id):
    conn = get_db()
    poll = conn.execute("SELECT question, options, votes FROM polls WHERE id = ?", (poll_id,)).fetchone()
    conn.close()
    
    if not poll:
        return None
    
    options = poll['options'].split(",")
    votes = poll['votes'].split(",")
    total = sum(int(v) for v in votes)
    
    results = []
    for i, (opt, v) in enumerate(zip(options, votes)):
        percentage = (int(v) / total * 100) if total > 0 else 0
        results.append(f"{i+1}. {opt} — {v} صوت ({percentage:.1f}%)")
    
    return {
        'question': poll['question'],
        'results': results,
        'total_votes': total
    }

def get_active_polls():
    conn = get_db()
    polls = conn.execute("SELECT id, question FROM polls WHERE active = 1 ORDER BY id DESC").fetchall()
    conn.close()
    return polls

@bot.callback_query_handler(func=lambda call: call.data == "poll_menu")
def poll_menu_callback(call):
    polls = get_active_polls()
    
    if not polls:
        text = "📊 لا توجد استطلاعات حالياً"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=keyboard)
        return
    
    text = "📊 الاستطلاعات المتاحة\n\nاختر استطلاعاً للمشاركة:"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for poll in polls:
        keyboard.add(types.InlineKeyboardButton(f"📋 {poll['question'][:30]}", callback_data=f"show_poll_{poll['id']}"))
    
    keyboard.add(types.InlineKeyboardButton("➕ إنشاء استطلاع", callback_data="create_poll"))
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("show_poll_"))
def show_poll_callback(call):
    poll_id = int(call.data.replace("show_poll_", ""))
    user_id = call.from_user.id
    
    conn = get_db()
    poll = conn.execute("SELECT question, options FROM polls WHERE id = ? AND active = 1", (poll_id,)).fetchone()
    
    if not poll:
        conn.close()
        bot.answer_callback_query(call.id, "❌ الاستطلاع غير موجود", show_alert=True)
        return
    
    existing = conn.execute("SELECT * FROM poll_votes WHERE poll_id = ? AND user_id = ?", (poll_id, user_id)).fetchone()
    conn.close()
    
    options = poll['options'].split(",")
    
    text = f"📊 {poll['question']}\n\nاختر إجابتك:"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for i, opt in enumerate(options):
        keyboard.add(types.InlineKeyboardButton(f"{opt}", callback_data=f"poll_vote_{poll_id}_{i}"))
    
    if existing:
        keyboard.add(types.InlineKeyboardButton("📊 عرض النتائج", callback_data=f"poll_results_{poll_id}"))
    
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="poll_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("poll_vote_"))
def poll_vote_callback(call):
    parts = call.data.split("_")
    poll_id = int(parts[2])
    option_index = int(parts[3])
    user_id = call.from_user.id
    
    success = vote_in_poll(poll_id, user_id, option_index)
    
    if success:
        bot.answer_callback_query(call.id, "✅ تم تسجيل تصويتك!", show_alert=True)
        show_poll_results(call, poll_id)
    else:
        bot.answer_callback_query(call.id, "❌ لقد قمت بالتصويت مسبقاً!", show_alert=True)

def show_poll_results(call, poll_id):
    results = get_poll_results(poll_id)
    if not results:
        return
    
    text = f"📊 نتائج الاستطلاع\n\n{results['question']}\n\n"
    text += "\n".join(results['results'])
    text += f"\n\n📊 إجمالي المصوتين: {results['total_votes']}"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="poll_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "create_poll")
def create_poll_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    is_admin = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not is_admin and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية!", show_alert=True)
        return
    
    msg = bot.send_message(call.message.chat.id, "📝 أرسل سؤال الاستطلاع:")
    bot.register_next_step_handler(msg, get_poll_question)

def get_poll_question(message):
    user_id = message.from_user.id
    question = message.text.strip()
    user_states[user_id] = {"action": "poll_question", "question": question}
    msg = bot.send_message(message.chat.id, "📝 أرسل خيارات الاستطلاع (كل خيار في سطر جديد):")
    bot.register_next_step_handler(msg, get_poll_options)

def get_poll_options(message):
    user_id = message.from_user.id
    options = [opt.strip() for opt in message.text.split("\n") if opt.strip()]
    
    if len(options) < 2:
        bot.send_message(message.chat.id, "❌ يجب أن يكون هناك خياران على الأقل")
        return
    
    question = user_states[user_id]["question"]
    poll_id = create_poll(question, options, user_id)
    
    bot.send_message(message.chat.id, f"✅ تم إنشاء الاستطلاع بنجاح!")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("poll_results_"))
def poll_results_only_callback(call):
    poll_id = int(call.data.replace("poll_results_", ""))
    show_poll_results(call, poll_id)

# ================= الإعدادات =================
@bot.callback_query_handler(func=lambda call: call.data == "settings")
def settings_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    setting = conn.execute("SELECT theme, sound FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not setting:
        setting = {'theme': 'default', 'sound': 1}
    
    theme_icon = "🎨" if setting['theme'] == 'default' else "🌙" if setting['theme'] == 'dark' else "🌈"
    sound_icon = "🔊" if setting['sound'] else "🔇"
    
    text = f"""⚙️ <b>إعدادات البوت</b>

{theme_icon} <b>الثيم:</b> {setting['theme']}
{sound_icon} <b>المؤثرات الصوتية:</b> {'مفعلة' if setting['sound'] else 'معطلة'}

اختر الإعداد الذي تريد تعديله:"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(f"{theme_icon} تغيير الثيم", callback_data="change_theme"),
        types.InlineKeyboardButton(f"{sound_icon} الصوتيات", callback_data="toggle_sound")
    )
    keyboard.add(
        types.InlineKeyboardButton("⛔ حظر عضو", callback_data="ban_user"),
        types.InlineKeyboardButton("✅ فك حظر", callback_data="unban_user"),
        types.InlineKeyboardButton("📋 المحظورين", callback_data="banned_list")
    )
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

def get_user_theme(user_id):
    conn = get_db()
    setting = conn.execute("SELECT theme FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return setting['theme'] if setting else 'default'

def apply_theme(user_id, text):
    theme = get_user_theme(user_id)
    if theme == 'dark':
        return f"🌙 {text}"
    elif theme == 'colorful':
        return f"🌈 {text}"
    return text

@bot.callback_query_handler(func=lambda call: call.data == "change_theme")
def change_theme_callback(call):
    user_id = call.from_user.id
    themes = ['default', 'dark', 'colorful']
    current_theme = get_user_theme(user_id)
    next_theme = themes[(themes.index(current_theme) + 1) % len(themes)]
    
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (user_id, theme, sound) VALUES (?, ?, COALESCE((SELECT sound FROM settings WHERE user_id = ?), 1))", 
                 (user_id, next_theme, user_id))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"✅ تم تغيير الثيم إلى {next_theme}")
    settings_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_sound")
def toggle_sound_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    current = conn.execute("SELECT sound FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    new_sound = 0 if (current and current['sound']) else 1
    conn.execute("INSERT OR REPLACE INTO settings (user_id, theme, sound) VALUES (?, COALESCE((SELECT theme FROM settings WHERE user_id = ?), 'default'), ?)", 
                 (user_id, user_id, new_sound))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"✅ {'تم تفعيل' if new_sound else 'تم تعطيل'} المؤثرات الصوتية")
    settings_callback(call)

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
        bot.send_message(message.chat.id, f"✅ تم حظر العضو {user_id}")
        send_main_menu(message.chat.id, message.from_user.id)
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
        bot.send_message(message.chat.id, f"✅ تم فك الحظر عن العضو {user_id}")
        send_main_menu(message.chat.id, message.from_user.id)
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
            text += f"🆔 {b['user_id']}\n⚖️ {b['reason']}\n\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="settings"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

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

🏅 <b>الشارات:</b>
• الفائز الأول - عند الفوز بأول مسابقة
• المصوت النشط - عند التصويت 10 مرات
• منشئ المسابقات - عند إنشاء 5 مسابقات

📊 <b>الاستطلاعات:</b>
يمكنك إنشاء استطلاعات رأي والمشاركة فيها

🌍 <b>اللغة:</b>
يمكنك تغيير لغة البوت من قائمة الإعدادات

🎨 <b>التخصيص:</b>
يمكنك تغيير ثيم البوت (عادي/داكن/ملون)

⏰ <b>ملاحظة:</b> يتم حذف المسابقات تلقائياً بعد 24 ساعة

👨‍💻 <b>مطور البوت:</b> عصوم الشامي"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

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
        
        sent = bot.send_message(int(channel_id), post_text, reply_markup=keyboard)
        
        conn = get_db()
        conn.execute("UPDATE contests SET post_id = ? WHERE id = ?", (sent.message_id, contest_id))
        conn.commit()
        conn.close()
        
        msg = bot.send_message(
            message.chat.id,
            f"✅ تم إنشاء المسابقة بنجاح!\n\n📌 {title}\n🆔 #{contest_id}\n⏰ تنتهي بعد 24 ساعة\n\n🎯 أرسل عدد الأصوات المطلوبة للفوز (0 لتعطيل):"
        )
        bot.register_next_step_handler(msg, set_target_votes, contest_id)
        
        award_badge(user_id, 'creator')
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}")

def set_target_votes(message, contest_id):
    user_id = message.from_user.id
    try:
        target = int(message.text.strip())
        if target < 0:
            target = 0
    except:
        target = 0
    
    conn = get_db()
    conn.execute("UPDATE contests SET target_votes = ? WHERE id = ?", (target, contest_id))
    conn.commit()
    conn.close()
    
    if target > 0:
        bot.send_message(message.chat.id, f"✅ تم تعيين الهدف: {target} صوت للفوز")
    else:
        bot.send_message(message.chat.id, f"✅ تم تعطيل نظام التسليم التلقائي")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

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
        
        if chat.type not in ["channel", "supergroup"]:
            bot.send_message(message.chat.id, "❌ هذا ليس قناة!")
            return
        
        bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
        if bot_member.status != "administrator":
            bot.send_message(message.chat.id, "❌ البوت ليس مشرفاً في هذه القناة!")
            return
        
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (user_id, vote_channel) VALUES (?, ?)", (user_id, str(chat.id)))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم تعيين القناة بنجاح!\n\n📢 {chat.title}")
        send_main_menu(message.chat.id, user_id)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}")

# ================= مسابقاتي =================
@bot.callback_query_handler(func=lambda call: call.data == "my_contests")
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
        target_text = f"🎯 الهدف: {contest['target_votes']} صوت" if contest['target_votes'] > 0 else "🎯 تسليم تلقائي: معطل"
        text += f"🔹 <b>{contest['title']}</b>\n"
        text += f"   🆔 #{contest['id']}\n"
        text += f"   {time_left}\n"
        text += f"   {target_text}\n\n"
    
    text += f"📄 الصفحة {page} من {total_pages}"
    
    keyboard = types.InlineKeyboardMarkup()
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ السابق", callback_data=f"contests_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton("التالي ➡️", callback_data=f"contests_page_{page+1}"))
    
    if nav_buttons:
        keyboard.row(*nav_buttons)
    
    keyboard.add(types.InlineKeyboardButton("➕ مسابقة جديدة", callback_data="create_contest"))
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("contests_page_"))
def contests_page_callback(call):
    page = int(call.data.replace("contests_page_", ""))
    if "contests_page" not in user_states.get(call.from_user.id, {}):
        user_states[call.from_user.id] = {}
    user_states[call.from_user.id]["contests_page"] = page
    my_contests_callback(call)

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
    
    contest = conn.execute("SELECT title, created_at, target_votes FROM contests WHERE id = ?", (contest_id,)).fetchone()
    conn.close()
    
    time_left = get_time_remaining(contest["created_at"]) if contest else ""
    
    if not contestants:
        text = f"🏆 <b>{contest['title']}</b>\n{time_left}\n🎯 الهدف: {contest['target_votes']} صوت\n\n📊 لا يوجد مشاركين بعد"
    else:
        text = f"🏆 <b>{contest['title']}</b>\n{time_left}\n🎯 الهدف: {contest['target_votes']} صوت\n\n"
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
    
    contest = conn.execute("SELECT title, created_at, target_votes FROM contests WHERE id = ?", (contest_id,)).fetchone()
    conn.close()
    
    time_left = get_time_remaining(contest["created_at"]) if contest else ""
    
    text = f"🏆 <b>{contest['title']}</b>\n{time_left}\n🎯 الهدف: {contest['target_votes']} صوت\n\n"
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

# ================= إضافة وخصم الأصوات =================
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
        conn.close()
        
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
        
        new_votes = conn.execute("SELECT votes FROM contestants WHERE id = ?", (contestant_id,)).fetchone()["votes"]
        
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
        
        check_winner(info['contest_id'], contestant_id, new_votes)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إرسال عدد صحيح")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

# ================= المشاركة في المسابقة والتصويت =================
@bot.message_handler(func=lambda m: m.from_user.id in user_states and user_states[m.from_user.id].get("action") == "join_contest")
def handle_join_contest(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    contest_id = state["contest_id"]
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        bot.send_message(message.chat.id, "❌ الاسم يجب أن يكون بين 2 و 50 حرفاً")
        return
    
    if re.search(r'@|http|t\.me|bit\.ly|\.com', name, re.IGNORECASE):
        bot.send_message(message.chat.id, "❌ الاسم لا يمكن أن يحتوي على روابط أو يوزرات")
        return
    
    conn = get_db()
    
    contest = conn.execute("SELECT * FROM contests WHERE id = ? AND active = 1", (contest_id,)).fetchone()
    
    if not contest:
        conn.close()
        bot.send_message(message.chat.id, "❌ هذه المسابقة غير متاحة")
        del user_states[user_id]
        return
    
    existing = conn.execute("SELECT id FROM contestants WHERE contest_id = ? AND user_id = ?", (contest_id, user_id)).fetchone()
    if existing:
        conn.close()
        bot.send_message(message.chat.id, "❌ لقد شاركت في هذه المسابقة من قبل!")
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

👇 للتصويت اضغط على الزر أدناه:

⚠️ يجب الاشتراك في القناة للتصويت!"""
        
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
            f"✅ تمت المشاركة بنجاح!\n\n👤 اسمك: {name}\n📢 تم نشر اسمك في القناة"
        )
        
        conn = get_db()
        conn.execute("UPDATE users SET total_contests = total_contests + 1 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ: {str(e)}")
    
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
def vote_callback(call):
    user_id = call.from_user.id
    parts = call.data.split("_")
    contest_id = int(parts[1])
    contestant_id = int(parts[2])
    
    conn = get_db()
    
    contestant = conn.execute("SELECT user_id FROM contestants WHERE id = ?", (contestant_id,)).fetchone()
    
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
        bot.answer_callback_query(call.id, "❌ لقد قمت بالتصويت في هذه المسابقة من قبل!", show_alert=True)
        return
    
    conn.execute("INSERT INTO votes (contest_id, voter_id, contestant_id) VALUES (?, ?, ?)", (contest_id, user_id, contestant_id))
    conn.execute("UPDATE contestants SET votes = votes + 1 WHERE id = ?", (contestant_id,))
    conn.commit()
    
    new_votes = conn.execute("SELECT votes FROM contestants WHERE id = ?", (contestant_id,)).fetchone()["votes"]
    
    info = conn.execute("""
        SELECT c.votes, c.post_id, co.channel_id 
        FROM contestants c 
        JOIN contests co ON c.contest_id = co.id 
        WHERE c.id = ?
    """, (contestant_id,)).fetchone()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ تم التصويت بنجاح!", show_alert=True)
    
    check_winner(contest_id, contestant_id, new_votes)
    
    if info and info["post_id"]:
        try:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(f"👍 تصويت ({info['votes']})", callback_data=f"vote_{contest_id}_{contestant_id}"),
                types.InlineKeyboardButton("🎯 المشاركة", url=f"https://t.me/{bot.get_me().username}?start=contest_{contest_id}")
            )
            bot.edit_message_reply_markup(int(info["channel_id"]), info["post_id"], reply_markup=keyboard)
        except:
            pass
    
    conn = get_db()
    votes_count = conn.execute("SELECT COUNT(*) FROM votes WHERE voter_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    if votes_count >= 10:
        award_badge(user_id, 'voter')

# ================= حذف المسابقات التلقائي =================
def auto_delete_contests():
    while True:
        try:
            time.sleep(3600)
            
            conn = get_db()
            one_day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            
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
                        f"🗑️ <b>تم حذف المسابقة</b>\n\n📌 {contest['title']}\n⏰ بعد 24 ساعة"
                    )
                except:
                    pass
            
            conn.close()
            
        except Exception as e:
            print(f"خطأ في الحذف التلقائي: {e}")

delete_thread = threading.Thread(target=auto_delete_contests, daemon=True)
delete_thread.start()

# ================= لوحة تحكم الأدمن =================
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    is_admin = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not is_admin and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية!", show_alert=True)
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
        types.InlineKeyboardButton("📢 إدارة الإعلانات", callback_data="ads_menu")
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
    polls_count = conn.execute("SELECT COUNT(*) FROM polls WHERE active = 1").fetchone()[0]
    conn.close()
    
    text = f"""📊 <b>إحصائيات البوت</b>

👥 المستخدمين: {users_count}
🎯 المسابقات: {contests_count}
🏆 المتسابقين: {contestants_count}
👍 التصويتات: {votes_count}
📊 الاستطلاعات: {polls_count}
⏰ الحذف التلقائي: مفعل"""
    
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
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ تم إضافة العضو {user_id} كأدمن")
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
        bot.send_message(message.chat.id, f"✅ تم حذف العضو {user_id} من الأدمن")
        send_main_menu(message.chat.id, message.from_user.id)
    except:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")

@bot.callback_query_handler(func=lambda call: call.data == "admin_force_subs")
def admin_force_subs_callback(call):
    text = "📢 <b>إدارة قنوات الاشتراك الإجباري</b>\n\nيمكنك إضافة قنوات يجب الاشتراك فيها قبل استخدام البوت."
    
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
        
        bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
        if bot_member.status != "administrator":
            bot.send_message(message.chat.id, "❌ البوت ليس مشرفاً في هذه القناة!")
            return
        
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO force_subs (channel_id, channel_username) VALUES (?, ?)", 
                     (str(chat.id), chat.username))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ تم إضافة القناة @{chat.username}")
        send_main_menu(message.chat.id, message.from_user.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "remove_force_sub")
def remove_force_sub_callback(call):
    conn = get_db()
    channels = conn.execute("SELECT id, channel_username FROM force_subs").fetchall()
    conn.close()
    
    if not channels:
        bot.answer_callback_query(call.id, "لا توجد قنوات!", show_alert=True)
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
    
    bot.answer_callback_query(call.id, "✅ تم الحذف", show_alert=True)
    admin_force_subs_callback(call)

@bot.callback_query_handler(func=lambda call: call.data == "list_force_subs")
def list_force_subs_callback(call):
    conn = get_db()
    channels = conn.execute("SELECT channel_username FROM force_subs").fetchall()
    conn.close()
    
    if not channels:
        text = "📋 لا توجد قنوات"
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

# ================= إدارة الإعلانات =================
def get_random_ad():
    conn = get_db()
    ad = conn.execute("SELECT id, ad_text, ad_url FROM ads WHERE active = 1 ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return ad

def record_ad_view(ad_id):
    conn = get_db()
    conn.execute("UPDATE ads SET views = views + 1 WHERE id = ?", (ad_id,))
    conn.commit()
    conn.close()

def add_ad(ad_text, ad_url):
    conn = get_db()
    conn.execute("INSERT INTO ads (ad_text, ad_url) VALUES (?, ?)", (ad_text, ad_url))
    conn.commit()
    conn.close()

def get_ads_list():
    conn = get_db()
    ads = conn.execute("SELECT id, ad_text, views, clicks FROM ads WHERE active = 1").fetchall()
    conn.close()
    return ads

def delete_ad(ad_id):
    conn = get_db()
    conn.execute("UPDATE ads SET active = 0 WHERE id = ?", (ad_id,))
    conn.commit()
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "ads_menu")
def ads_menu_callback(call):
    user_id = call.from_user.id
    
    conn = get_db()
    is_admin = conn.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not is_admin and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية!", show_alert=True)
        return
    
    text = "📢 <b>إدارة الإعلانات</b>\n\nاختر الإجراء المناسب:"
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة إعلان", callback_data="add_ad"),
        types.InlineKeyboardButton("📋 قائمة الإعلانات", callback_data="list_ads"),
        types.InlineKeyboardButton("🗑 حذف إعلان", callback_data="delete_ad")
    )
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="admin_panel"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "add_ad")
def add_ad_callback(call):
    msg = bot.send_message(call.message.chat.id, "📝 أرسل نص الإعلان:")
    bot.register_next_step_handler(msg, get_ad_text)

def get_ad_text(message):
    user_id = message.from_user.id
    ad_text = message.text.strip()
    user_states[user_id] = {"action": "ad_text", "ad_text": ad_text}
    msg = bot.send_message(message.chat.id, "🔗 أرسل رابط الإعلان (اتركه فارغاً إذا لا يوجد):")
    bot.register_next_step_handler(msg, get_ad_url)

def get_ad_url(message):
    user_id = message.from_user.id
    ad_url = message.text.strip()
    ad_text = user_states[user_id]["ad_text"]
    
    add_ad(ad_text, ad_url if ad_url else None)
    
    bot.send_message(message.chat.id, "✅ تم إضافة الإعلان بنجاح!")
    del user_states[user_id]
    send_main_menu(message.chat.id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "list_ads")
def list_ads_callback(call):
    ads = get_ads_list()
    
    if not ads:
        text = "📋 لا توجد إعلانات"
    else:
        text = "📋 <b>قائمة الإعلانات</b>\n\n"
        for ad in ads:
            text += f"🆔 #{ad['id']}\n📝 {ad['ad_text'][:50]}\n👁️ مشاهدات: {ad['views']} | 👆 نقرات: {ad['clicks']}\n\n"
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="ads_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "delete_ad")
def delete_ad_callback(call):
    ads = get_ads_list()
    
    if not ads:
        bot.answer_callback_query(call.id, "لا توجد إعلانات!", show_alert=True)
        return
    
    text = "🗑 <b>اختر الإعلان لحذفه:</b>\n\n"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for ad in ads:
        keyboard.add(types.InlineKeyboardButton(f"📢 #{ad['id']} - {ad['ad_text'][:30]}", callback_data=f"delete_ad_id_{ad['id']}"))
    
    keyboard.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="ads_menu"))
    
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_ad_id_"))
def delete_ad_id_callback(call):
    ad_id = int(call.data.replace("delete_ad_id_", ""))
    delete_ad(ad_id)
    
    bot.answer_callback_query(call.id, "✅ تم حذف الإعلان", show_alert=True)
    list_ads_callback(call)

# ================= تشغيل البوت =================
if __name__ == "__main__":
    print("🚀 تشغيل بوت المسابقات المتطور...")
    print("✅ نظام الحماية من الغش")
    print("✅ نظام الإعلانات المدفوعة")
    print("✅ نظام الشارات والميداليات")
    print("✅ نظام متعدد اللغات")
    print("✅ نظام الاستطلاعات")
    print("✅ نظام تخصيص البوت")
    print("✅ نظام التسليم التلقائي")
    
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()
    
    # حذف الويب هوك لتجنب الخطأ 409
    print("🔄 جاري حذف أي Webhook سابق...")
    bot.delete_webhook()
    time.sleep(2)
    
    try:
        print("✅ بدء تشغيل البوت...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ خطأ: {e}")
        time.sleep(3)
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
