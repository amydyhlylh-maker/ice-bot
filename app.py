import asyncio
import re
import sqlite3
import random
import json
import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask, request, Response

# ===== کتابخانه rubka =====
from rubka.asynco import Robot
from rubka.context import Message

logging.getLogger('rubka').setLevel(logging.ERROR)

# ===== توکن و اطلاعات (همانند setup_webhook.py) =====
TOKEN = os.getenv("RUBIKA_TOKEN", "BHJDEE0PRUSZOEDQRURMLYODBRJYJRBWYVVDDIMEXGFSZEOSTZIESECHRMSPWCLK")
OWNER_ID = "u0KIsuK0e84761d2e0d5e7c8bd819099"
BOT_NAME = "ربات یخی مدیریت گروه"
BOT_FULL_NAME = "🧊 **ربات یخی مدیریت گروه** 🧊"
CHANNEL_LINK = "@Robat_Yakhi"
CREATOR_ID = "@Robat_Yakhi"

bot = Robot(TOKEN)

# ========== دیتابیس ==========
DB_NAME = 'ice_bot_final.db'
conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# ========== ایجاد جداول ==========
c.execute('''CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY,
    name TEXT,
    active INTEGER DEFAULT 0,
    antilink INTEGER DEFAULT 0,
    speaker INTEGER DEFAULT 1,
    max_warns INTEGER DEFAULT 3,
    creator_id TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS private_chats (chat_id TEXT PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS assistant_admins (chat_id TEXT, user_id TEXT, PRIMARY KEY (chat_id, user_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS messages (chat_id TEXT, message_id TEXT, sender_id TEXT, timestamp INTEGER, PRIMARY KEY (chat_id, message_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS user_stats (chat_id TEXT, user_id TEXT, message_count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS mutes (chat_id TEXT, user_id TEXT, PRIMARY KEY (chat_id, user_id))''')
c.execute('''CREATE TABLE IF NOT EXISTS group_locks (chat_id TEXT PRIMARY KEY, is_locked INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS user_warns (
    chat_id TEXT, user_id TEXT, warn_type TEXT,
    warn_count INTEGER DEFAULT 0, last_warn_time INTEGER,
    PRIMARY KEY (chat_id, user_id, warn_type)
)''')
c.execute('''CREATE TABLE IF NOT EXISTS user_ranks (
    chat_id TEXT, user_id TEXT, nickname TEXT, title TEXT,
    PRIMARY KEY (chat_id, user_id)
)''')
conn.commit()

# ========== ایندکس‌ها برای سرعت ==========
c.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_user_stats_chat_id ON user_stats(chat_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_user_warns_chat_id ON user_warns(chat_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_mutes_chat_id ON mutes(chat_id)")
conn.commit()

# اضافه کردن ستون‌ها
c.execute("PRAGMA table_info(groups)")
cols = [row[1] for row in c.fetchall()]
for col, default in [('anti_spam',1), ('block_forward',0), ('anti_hung',0), ('game_mode',1), ('anti_gif',0), ('anti_video',0), ('anti_curse',0)]:
    if col not in cols:
        try:
            c.execute(f"ALTER TABLE groups ADD COLUMN {col} INTEGER DEFAULT {default}")
            conn.commit()
        except: pass
print(f"✅ دیتابیس: {DB_NAME}")

# ========== کش تنظیمات گروه (TTL 600 ثانیه) ==========
GROUP_CACHE = {}
CACHE_TTL = 600

async def get_group_settings(chat_id):
    now = time.time()
    if chat_id in GROUP_CACHE and GROUP_CACHE[chat_id]["expire"] > now:
        return GROUP_CACHE[chat_id]["data"]
    row = c.execute("SELECT active, antilink, speaker, max_warns, creator_id, block_forward, anti_hung, game_mode, anti_spam, anti_gif, anti_video, anti_curse FROM groups WHERE group_id=?", (chat_id,)).fetchone()
    if row is None:
        name = await get_group_name(chat_id)
        c.execute("INSERT INTO groups (group_id, name, active, antilink, speaker, max_warns, block_forward, anti_hung, game_mode, anti_spam, anti_gif, anti_video, anti_curse, creator_id) VALUES (?,?,0,0,1,3,0,0,1,1,0,0,0,NULL)", (chat_id, name))
        conn.commit()
        row = (0, 0, 1, 3, None, 0, 0, 1, 1, 0, 0, 0)
    GROUP_CACHE[chat_id] = {"data": row, "expire": now + CACHE_TTL}
    return row

def invalidate_group_cache(chat_id):
    if chat_id in GROUP_CACHE:
        del GROUP_CACHE[chat_id]

# ========== لیست فحش ==========
curse_words = [
    'کص','کصی','کصو','کیر','کون','کیری','کله کیری','مادر جنده','ننه جنده','کص ننت','کص مادرت',
    'کونی','حرومی','حروم زاده','قیندی','ننه کصو','مادرتو گاییدم','پدر سگ','اوبی','اوب','جنده',
    'کص خواهرت','کصخل','کصکش','کونکش','کیرکش','پدرسگ','خارکصه','جاکش','گوه','گوز','گاییدم'
]
def contains_curse(text):
    text_lower = text.lower()
    for w in curse_words:
        if w in text_lower: return True
    return False

# ========== ضد اسپم ==========
spam_tracker = defaultdict(lambda: defaultdict(list))
SPAM_INTERVAL = 5
SPAM_LIMIT = 4
async def check_spam(chat_id, user_id):
    now = time.time()
    timestamps = spam_tracker[chat_id][user_id]
    timestamps = [t for t in timestamps if now - t < SPAM_INTERVAL]
    timestamps.append(now)
    spam_tracker[chat_id][user_id] = timestamps
    return len(timestamps) > SPAM_LIMIT

# ========== yad.json ==========
yad_data = {}
def load_yad_json():
    global yad_data
    try:
        if os.path.exists('yad.json'):
            with open('yad.json','r',encoding='utf-8') as f:
                yad_data = json.load(f)
            print(f"✅ yad.json بارگذاری شد - {len(yad_data)} دسته")
            return True
        else:
            print("⚠️ فایل yad.json پیدا نشد!")
            return False
    except Exception as e:
        print(f"⚠️ خطا در بارگذاری yad.json: {e}")
        return False
def get_yad_response(text):
    if not yad_data: return None
    text_clean = text.strip().lower()
    if text_clean == 'چالش':
        return random.choice(yad_data.get('چالش', ["🎯 یه کار خوب امروز انجام بده!"]))
    if text_clean == 'جوک':
        return random.choice(yad_data.get('جوک', ["😂 جوک: چرا مرغ از جاده رد شد؟ برای اینکه به اون طرف برسه!"]))
    if text_clean == 'فال':
        return random.choice(yad_data.get('فال', ["🌸 روزت پر از خبرهای خوب خواهد بود!"]))
    for key, responses in yad_data.items():
        if key.lower() in text_clean and key not in ['چالش','جوک','فال']:
            if isinstance(responses, list) and responses:
                return random.choice(responses)
            elif isinstance(responses, str):
                return responses
    return None
load_yad_json()

def is_hung_code(text):
    patterns = [r'(\.\s*){40,}', r'(\d\.){5,}', r'Filter', r'Ban', r'report', r'Spam', r'(.)\1{30,}', r'(\d{1,3}\.){4,}\d{1,3}']
    return any(re.search(p, text, re.I) for p in patterns)
def contains_link(text):
    pattern = r'(https?://|www\.|t\.me/|@[\w]+|[\w-]+\.(ir|com|org|net|info|xyz|club|site|online|tech|space|me|link|bid|cf|ga|gq|ml|tk|io|ai|app|dev|pro|live|news|today|world|store|shop|blog|co|uk|us|ru|de|fr|it|es|nl|pl|tr|ae|sa|in|id|my|ph|vn|th|kr|jp|cn|tw|hk|sg))\b'
    return bool(re.search(pattern, text, re.I))
def contains_bio_check(text):
    return any(re.search(p, text.lower()) for p in [r'بیو\s*چک', r'بیوگرافی\s*چک', r'بیوچک'])

def is_gif(msg):
    try:
        mime = getattr(msg, 'mime_type', None)
        if mime and mime.lower() == 'image/gif':
            return True
        doc = getattr(msg, 'document', None)
        if doc and getattr(doc, 'mime_type', '').lower() == 'image/gif':
            return True
        return getattr(msg, 'is_gif', False)
    except:
        return False

def is_video(msg):
    try:
        mime = getattr(msg, 'mime_type', None)
        if mime and 'video' in mime.lower() and 'gif' not in mime.lower():
            return True
        if getattr(msg, 'video', None):
            return True
        if getattr(msg, 'is_video', False):
            return True
        doc = getattr(msg, 'document', None)
        if doc and 'video' in getattr(doc, 'mime_type', '').lower():
            return True
        return False
    except:
        return False

def dice_art(n): return {1:"⚀",2:"⚁",3:"⚂",4:"⚃",5:"⚄",6:"⚅"}.get(n,"⚀")

async def get_group_name(gid):
    try:
        name = await bot.get_name(gid)
        return str(name) if name else 'بدون نام'
    except: return 'بدون نام'

async def is_group_admin(chat_id, user_id):
    if user_id == OWNER_ID: return True
    c.execute("SELECT creator_id FROM groups WHERE group_id=?", (chat_id,))
    row = c.fetchone()
    if row and row[0] == user_id: return True
    c.execute("SELECT 1 FROM assistant_admins WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return c.fetchone() is not None
async def is_group_creator(chat_id, user_id):
    c.execute("SELECT creator_id FROM groups WHERE group_id=?", (chat_id,))
    row = c.fetchone()
    return row and row[0] == user_id

async def add_warn(chat_id, user_id, warn_type="general"):
    t = int(time.time())
    c.execute("INSERT INTO user_warns (chat_id, user_id, warn_type, warn_count, last_warn_time) VALUES (?,?,?,1,?) ON CONFLICT(chat_id, user_id, warn_type) DO UPDATE SET warn_count = warn_count + 1, last_warn_time = ?", (chat_id, user_id, warn_type, t, t))
    conn.commit()
    c.execute("SELECT warn_count FROM user_warns WHERE chat_id=? AND user_id=? AND warn_type=?", (chat_id, user_id, warn_type))
    return c.fetchone()[0]
async def remove_warn(chat_id, user_id, warn_type=None):
    if warn_type:
        c.execute("DELETE FROM user_warns WHERE chat_id=? AND user_id=? AND warn_type=?", (chat_id, user_id, warn_type))
    else:
        c.execute("DELETE FROM user_warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()
async def get_warn_count(chat_id, user_id, warn_type=None):
    if warn_type:
        c.execute("SELECT warn_count FROM user_warns WHERE chat_id=? AND user_id=? AND warn_type=?", (chat_id, user_id, warn_type))
        row = c.fetchone()
        return row[0] if row else 0
    else:
        c.execute("SELECT SUM(warn_count) FROM user_warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        row = c.fetchone()
        return row[0] if row and row[0] else 0
async def get_max_warns(chat_id):
    row = c.execute("SELECT max_warns FROM groups WHERE group_id=?", (chat_id,)).fetchone()
    return row[0] if row else 3
async def clear_warns(chat_id, user_id, warn_type=None):
    if warn_type:
        c.execute("DELETE FROM user_warns WHERE chat_id=? AND user_id=? AND warn_type=?", (chat_id, user_id, warn_type))
    else:
        c.execute("DELETE FROM user_warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()
async def set_max_warns(chat_id, max_warns):
    c.execute("UPDATE groups SET max_warns=? WHERE group_id=?", (max_warns, chat_id))
    conn.commit()
    invalidate_group_cache(chat_id)

async def mute_user(chat_id, user_id):
    c.execute("INSERT OR REPLACE INTO mutes (chat_id, user_id) VALUES (?,?)", (chat_id, user_id))
    conn.commit()
async def unmute_user(chat_id, user_id):
    c.execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()
async def is_muted(chat_id, user_id):
    c.execute("SELECT 1 FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return c.fetchone() is not None

async def lock_group(chat_id):
    c.execute("INSERT OR REPLACE INTO group_locks (chat_id, is_locked) VALUES (?,1)", (chat_id,))
    conn.commit()
async def unlock_group(chat_id):
    c.execute("INSERT OR REPLACE INTO group_locks (chat_id, is_locked) VALUES (?,0)", (chat_id,))
    conn.commit()
async def is_group_locked(chat_id):
    c.execute("SELECT is_locked FROM group_locks WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    return row and row[0] == 1

async def inc_message_count(chat_id, user_id):
    c.execute("INSERT OR IGNORE INTO user_stats (chat_id, user_id, message_count) VALUES (?,?,0)", (chat_id, user_id))
    c.execute("UPDATE user_stats SET message_count = message_count + 1 WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    conn.commit()
async def get_user_message_count(chat_id, user_id):
    c.execute("SELECT message_count FROM user_stats WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    row = c.fetchone()
    return row[0] if row else 0
async def get_user_message_count_today(chat_id, user_id):
    today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=? AND sender_id=? AND timestamp >= ?", (chat_id, user_id, today_start))
    row = c.fetchone()
    return row[0] if row else 0
async def get_user_message_count_week(chat_id, user_id):
    week_start = int((datetime.now() - timedelta(days=7)).timestamp())
    c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=? AND sender_id=? AND timestamp >= ?", (chat_id, user_id, week_start))
    row = c.fetchone()
    return row[0] if row else 0
async def get_user_message_count_month(chat_id, user_id):
    month_start = int((datetime.now() - timedelta(days=30)).timestamp())
    c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=? AND sender_id=? AND timestamp >= ?", (chat_id, user_id, month_start))
    row = c.fetchone()
    return row[0] if row else 0
async def get_group_total_messages(chat_id):
    c.execute("SELECT SUM(message_count) FROM user_stats WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    return row[0] if row else 0
async def get_today_total_messages(chat_id):
    today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp >= ?", (chat_id, today_start))
    row = c.fetchone()
    return row[0] if row else 0
async def get_week_total_messages(chat_id):
    week_start = int((datetime.now() - timedelta(days=7)).timestamp())
    c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp >= ?", (chat_id, week_start))
    row = c.fetchone()
    return row[0] if row else 0
async def get_month_total_messages(chat_id):
    month_start = int((datetime.now() - timedelta(days=30)).timestamp())
    c.execute("SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp >= ?", (chat_id, month_start))
    row = c.fetchone()
    return row[0] if row else 0
async def get_top_users(chat_id, limit=3):
    c.execute("SELECT user_id, message_count FROM user_stats WHERE chat_id=? ORDER BY message_count DESC LIMIT ?", (chat_id, limit))
    return c.fetchall()

# ========== تنظیم فیلترها ==========
async def set_antilink(chat_id, locked): c.execute("UPDATE groups SET antilink=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_antilink(chat_id): row = await get_group_settings(chat_id); return row[1]==1 if row else 0
async def set_block_forward(chat_id, locked): c.execute("UPDATE groups SET block_forward=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_block_forward(chat_id): row = await get_group_settings(chat_id); return row[5]==1 if row else 0
async def set_anti_hung(chat_id, locked): c.execute("UPDATE groups SET anti_hung=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_anti_hung(chat_id): row = await get_group_settings(chat_id); return row[6]==1 if row else 0
async def set_anti_spam(chat_id, locked): c.execute("UPDATE groups SET anti_spam=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_anti_spam(chat_id): row = await get_group_settings(chat_id); return row[8]==1 if row else 0
async def set_game_mode(chat_id, enabled): c.execute("UPDATE groups SET game_mode=? WHERE group_id=?", (1 if enabled else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def get_game_mode(chat_id): row = await get_group_settings(chat_id); return row[7]==1 if row else 1
async def set_speaker(chat_id, enabled): c.execute("UPDATE groups SET speaker=? WHERE group_id=?", (1 if enabled else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def get_speaker(chat_id): row = await get_group_settings(chat_id); return row[2]==1 if row else 1
async def set_anti_gif(chat_id, locked): c.execute("UPDATE groups SET anti_gif=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_anti_gif(chat_id): row = await get_group_settings(chat_id); return row[9]==1 if row else 0
async def set_anti_video(chat_id, locked): c.execute("UPDATE groups SET anti_video=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_anti_video(chat_id): row = await get_group_settings(chat_id); return row[10]==1 if row else 0
async def set_anti_curse(chat_id, locked): c.execute("UPDATE groups SET anti_curse=? WHERE group_id=?", (1 if locked else 0, chat_id)); conn.commit(); invalidate_group_cache(chat_id)
async def is_anti_curse(chat_id): row = await get_group_settings(chat_id); return row[11]==1 if row else 0

# ========== حذف پیام با سرعت بالا ==========
async def delete_messages_with_status(chat_id, count, status_msg_id=None, bot_obj=None):
    c.execute("SELECT message_id FROM messages WHERE chat_id=? ORDER BY timestamp DESC LIMIT ?", (chat_id, count))
    msgs = c.fetchall()
    deleted = 0
    total = len(msgs)
    if total == 0: return 0
    for i, (mid,) in enumerate(msgs):
        try:
            await bot.delete_message(chat_id, mid)
            deleted += 1
            if status_msg_id and bot_obj and (i+1) % 30 == 0:
                try: await bot_obj.edit_message_text(chat_id, status_msg_id, f"⏳ در حال حذف... ({i+1}/{total})", parse_mode="Markdown")
                except: pass
            await asyncio.sleep(0.005)
        except: pass
    return deleted

async def set_nickname(chat_id, user_id, nickname):
    c.execute("INSERT OR REPLACE INTO user_ranks (chat_id, user_id, nickname, title) VALUES (?,?,?, COALESCE((SELECT title FROM user_ranks WHERE chat_id=? AND user_id=?), ''))", (chat_id, user_id, nickname, chat_id, user_id))
    conn.commit()
async def set_title(chat_id, user_id, title):
    c.execute("INSERT OR REPLACE INTO user_ranks (chat_id, user_id, title, nickname) VALUES (?,?,?, COALESCE((SELECT nickname FROM user_ranks WHERE chat_id=? AND user_id=?), ''))", (chat_id, user_id, title, chat_id, user_id))
    conn.commit()
async def get_nickname(chat_id, user_id):
    c.execute("SELECT nickname FROM user_ranks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    row = c.fetchone()
    return row[0] if row else None
async def get_title(chat_id, user_id):
    c.execute("SELECT title FROM user_ranks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    row = c.fetchone()
    return row[0] if row else None
async def transfer_ownership(chat_id, from_user, to_user):
    c.execute("UPDATE groups SET creator_id=? WHERE group_id=?", (to_user, chat_id))
    conn.commit()
    invalidate_group_cache(chat_id)

# ========== تشخیص فوروارد (قوی و کامل) ==========
def is_forward(msg):
    try:
        if hasattr(msg, 'forward_date') and msg.forward_date is not None:
            return True
        if hasattr(msg, 'forward_from') and msg.forward_from is not None:
            return True
        if hasattr(msg, 'forward_sender_name') and msg.forward_sender_name:
            return True
        if hasattr(msg, 'forward_chat') and msg.forward_chat is not None:
            return True
        if hasattr(msg, 'forward_signature') and msg.forward_signature:
            return True
        if hasattr(msg, 'forward') and msg.forward is not None:
            return True
        if hasattr(msg, 'is_forwarded') and msg.is_forwarded:
            return True
        return False
    except:
        return False

# ========== پیام‌های قفل/باز ==========
async def send_lock_msg(chat_id, lock_type, bot_obj):
    msg = f"• **قفل {lock_type} با موفقیت فعال شد.** ↺"
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass
async def send_unlock_msg(chat_id, lock_type, bot_obj):
    msg = f"• **{lock_type} → باز شد.** ↻"
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

# ========== پیام‌های هشدار ==========
async def send_warning(chat_id, user_id, warn_type, warn_count, max_warns, bot_obj, is_manual=False):
    if is_manual:
        first_line = f"› **[کاربر]({user_id})** 〆"
    else:
        if warn_type == "link": first_line = f"› **[کاربر]({user_id}) لینک ممنوع است.** 〆"
        elif warn_type == "forward": first_line = f"› **[کاربر]({user_id}) فوروارد ممنوع است.** 〆"
        elif warn_type == "hung": first_line = f"› **[کاربر]({user_id}) کد هنگی ممنوع است.** 〆"
        elif warn_type == "spam": first_line = f"› **[کاربر]({user_id}) اسپم ممنوع است.** 〆"
        elif warn_type == "gif": first_line = f"› **[کاربر]({user_id}) گیف ممنوع است.** 〆"
        elif warn_type == "video": first_line = f"› **[کاربر]({user_id}) فیلم ممنوع است.** 〆"
        elif warn_type == "curse": first_line = f"› **[کاربر]({user_id}) فحش ممنوع است.** 〆"
        else: first_line = f"› **[کاربر]({user_id}) تخلف کرد.** 〆"
    second_line = f"›› **شما [ {warn_count}/{max_warns} ] اخطار دریافت کردید.**"
    msg = f"{first_line}\n\n{second_line}"
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

# ========== پیام‌های بن، سیک، آن بن، آن سیک ==========
async def send_ban_msg(chat_id, user_id, bot_obj):
    msg = f"› **[کاربر]({user_id})** \n\n›› **از گروه مسدود شد!**"
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

async def send_kick_msg(chat_id, user_id, bot_obj):
    msgs = [
        f"› **[کاربر]({user_id})** \n\n›› **شرش کم شد.**",
        f"› **[کاربر]({user_id})** \n\n›› **با جفت پا شوت شد بیرون.**",
        f"› **[کاربر]({user_id})** \n\n›› **سیکش زده شد.**",
        f"› **[کاربر]({user_id})** \n\n›› **به درک واصل شد!**",
        f"› **[کاربر]({user_id})** \n\n›› **گورشو گم کرد.**"
    ]
    msg = random.choice(msgs)
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

async def send_unban_msg(chat_id, user_id, bot_obj):
    msg = f"› **[کاربر]({user_id})** \n\n›› **از حالت بن خارج شد.**"
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

async def send_unkick_msg(chat_id, user_id, bot_obj):
    msg = f"› **[کاربر]({user_id})** \n\n›› **به گروه برگردانده شد.**"
    try: await bot_obj.send_message(chat_id, msg, parse_mode="Markdown")
    except: pass

# ========== متغیر سراسری GUID ==========
BOT_GUID = None
async def get_bot_guid():
    global BOT_GUID
    if BOT_GUID is None:
        me = await bot.get_me()
        BOT_GUID = me.get('guid')
    return BOT_GUID

# ============================================================
# ========== کلاس SimpleMessage برای تبدیل دیکشنری ==========
class SimpleMessage:
    def __init__(self, data):
        self.chat_id = data.get('chat_id')
        self.message_id = data.get('message_id')
        self.sender_id = data.get('sender_id')
        self.text = data.get('text', '')
        self.reply_to_message_id = data.get('reply_to_message_id')
        self.reply_to_message = None
        self.mime_type = data.get('mime_type')
        self.document = data.get('document')
        self.video = data.get('video')
        self.is_gif = data.get('is_gif', False)
        self.is_video = data.get('is_video', False)
        self.forward_date = data.get('forward_date')
        self.forward_from = data.get('forward_from')
        self.forward_sender_name = data.get('forward_sender_name')
        self.forward_chat = data.get('forward_chat')
        self.forward_signature = data.get('forward_signature')
        self.forward = data.get('forward')
        self.is_forwarded = data.get('is_forwarded', False)
        self.new_chat_members = data.get('new_chat_members', [])
        self.reply_to_message = data.get('reply_to_message')

# ============================================================
# ========== پردازش پیام خصوصی ==========
async def handle_private_message(bot_obj, msg_data):
    try:
        chat_id = msg_data['chat_id']
        text = msg_data.get('text', '').strip()
        user_id = msg_data['sender_id']
        c.execute("INSERT OR IGNORE INTO private_chats (chat_id) VALUES (?)", (str(chat_id),))
        conn.commit()
        if user_id != OWNER_ID:
            await send_private_help(chat_id)
            return
        if text == '/admin':
            await bot_obj.send_message(chat_id, "**🔐 پنل مدیریت**\n• آمار\n• پیام همگانی متن\n• بستن", parse_mode="Markdown")
        elif text == 'آمار':
            total = c.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            active = c.execute("SELECT COUNT(*) FROM groups WHERE active=1").fetchone()[0]
            private = c.execute("SELECT COUNT(*) FROM private_chats").fetchone()[0]
            await bot_obj.send_message(chat_id, f"**📊 آمار ربات یخی**\n━━━━━━━━━━━━━━━━━━━━━━\n📌 **کل گروه‌های ثبت شده:** {total}\n✅ **گروه‌های فعال:** {active}\n👤 **چت‌های خصوصی:** {private}\n━━━━━━━━━━━━━━━━━━━━━━\n🧊 **ربات فعال**", parse_mode="Markdown")
        elif text.startswith('پیام همگانی '):
            bc = text[12:].strip()
            if not bc:
                await bot_obj.send_message(chat_id, "**❌ متن پیام را وارد کنید.**", parse_mode="Markdown")
                return
            bc = re.sub(r'<([^>]+)>', r'**\1**', bc)
            all_groups = [r[0] for r in c.execute("SELECT group_id FROM groups").fetchall()]
            all_priv = [r[0] for r in c.execute("SELECT chat_id FROM private_chats").fetchall()]
            total_targets = len(all_groups) + len(all_priv)
            if total_targets == 0:
                await bot_obj.send_message(chat_id, "**⚠️ هیچ گروه یا چت خصوصی‌ای یافت نشد.**", parse_mode="Markdown")
                return
            await bot_obj.send_message(chat_id, f"**📢 شروع ارسال همگانی...**\n👥 گروه‌ها: {len(all_groups)}\n👤 پیوی‌ها: {len(all_priv)}", parse_mode="Markdown")
            semaphore = asyncio.Semaphore(50)
            async def send_to_chat(chat_id):
                async with semaphore:
                    try:
                        await bot_obj.send_message(chat_id, bc, parse_mode="Markdown")
                        return True
                    except:
                        return False
            tasks = [send_to_chat(gid) for gid in all_groups] + [send_to_chat(pid) for pid in all_priv]
            results = await asyncio.gather(*tasks)
            success = sum(results)
            await bot_obj.send_message(chat_id, f"**✅ پیام همگانی ارسال شد.**\n━━━━━━━━━━━━━━━━━\n📢 **موفق:** {success} از {total_targets}", parse_mode="Markdown")
        elif text == 'بستن':
            await bot_obj.remove_keypad(chat_id)
            await bot_obj.send_message(chat_id, "**❌ پنل بسته شد.**", parse_mode="Markdown")
        else:
            await bot_obj.send_message(chat_id, "**📋 دستورات:**\n• /admin\n• آمار\n• پیام همگانی متن\n• بستن", parse_mode="Markdown")
    except Exception as e:
        print(f"خطا در private: {e}")

# ============================================================
# ========== پردازش پیام گروه ==========
async def handle_group_message(bot_obj, msg_data):
    try:
        chat_id = str(msg_data['chat_id'])
        text = msg_data.get('text', '').strip()
        user_id = msg_data['sender_id']
        message_id = msg_data.get('message_id')
        reply_to_message_id = msg_data.get('reply_to_message_id')

        # ===== ثبت خودکار گروه هنگام اضافه شدن ربات =====
        if 'new_chat_members' in msg_data and msg_data['new_chat_members']:
            bot_guid = await get_bot_guid()
            for member in msg_data['new_chat_members']:
                if member == bot_guid:
                    c.execute("INSERT OR IGNORE INTO groups (group_id, name, active) VALUES (?,?,0)", (chat_id, await get_group_name(chat_id)))
                    conn.commit()
                    try: await bot_obj.send_message(chat_id, "🧊 **ربات یخی به گروه اضافه شد.**\nبرای فعال‌سازی کامل، دستور `فعال` را ارسال کنید.", parse_mode="Markdown")
                    except: pass
                    break

        # ===== تشخیص ریپلای به دیگران =====
        is_reply_to_others = False
        if reply_to_message_id:
            try:
                if 'reply_to_message' in msg_data and msg_data['reply_to_message']:
                    replied_sender = msg_data['reply_to_message'].get('sender_id')
                    if replied_sender is not None:
                        bot_guid = await get_bot_guid()
                        if str(replied_sender) != str(bot_guid):
                            is_reply_to_others = True
                    else:
                        is_reply_to_others = True
                else:
                    c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id)))
                    row = c.fetchone()
                    bot_guid = await get_bot_guid()
                    if row:
                        if str(row[0]) != str(bot_guid):
                            is_reply_to_others = True
                    else:
                        is_reply_to_others = True
            except:
                is_reply_to_others = True

        await inc_message_count(chat_id, user_id)

        # ===== دریافت تنظیمات گروه =====
        settings = await get_group_settings(chat_id)
        if not settings: return
        active, antilink, speaker, max_warns, creator_id, block_forward, anti_hung, game_mode, anti_spam, anti_gif, anti_video, anti_curse = settings

        is_admin = await is_group_admin(chat_id, user_id)
        is_creator = await is_group_creator(chat_id, user_id)

        # ============================================================
        # ===== اولویت ۱: ضد لینک =====
        if antilink and contains_link(text):
            if not (is_admin or is_creator):
                try:
                    await bot_obj.delete_message(chat_id, message_id)
                except:
                    pass
                wc = await add_warn(chat_id, user_id, "link")
                mw = await get_max_warns(chat_id)
                await send_warning(chat_id, user_id, "link", wc, mw, bot_obj, is_manual=False)
                if wc >= mw:
                    try:
                        await bot_obj.ban_member_chat(chat_id, user_id)
                        await clear_warns(chat_id, user_id, "link")
                    except:
                        pass
                return

        # ===== اولویت ۲: ضد فوروارد =====
        msg_obj = SimpleMessage(msg_data)
        if block_forward and is_forward(msg_obj):
            if not (is_admin or is_creator):
                try:
                    await bot_obj.delete_message(chat_id, message_id)
                except:
                    pass
                wc = await add_warn(chat_id, user_id, "forward")
                mw = await get_max_warns(chat_id)
                await send_warning(chat_id, user_id, "forward", wc, mw, bot_obj, is_manual=False)
                if wc >= mw:
                    try:
                        await bot_obj.ban_member_chat(chat_id, user_id)
                        await clear_warns(chat_id, user_id, "forward")
                    except:
                        pass
                return

        # ===== yad.json (چالش، جوک، فال) =====
        if not is_reply_to_others:
            yad_resp = get_yad_response(text)
            if yad_resp:
                try: await bot_obj.send_message(chat_id, yad_resp, parse_mode="Markdown", reply_to_message_id=message_id)
                except: pass
                return

        # ===== راهنما، بیو چک، سازنده =====
        if text in ['راهنما','help','کمک']:
            try: await send_auto_help(chat_id)
            except: pass
            return
        if contains_bio_check(text):
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            wc = await add_warn(chat_id, user_id, "bio")
            mw = await get_max_warns(chat_id)
            try: await bot_obj.send_message(chat_id, f"**⚠️ [کاربر]({user_id}) اخطار {wc}/{mw} (بیو چک ممنوع)**", parse_mode="Markdown")
            except: pass
            if wc >= mw:
                try:
                    await bot_obj.ban_member_chat(chat_id, user_id)
                    await clear_warns(chat_id, user_id, "bio")
                except: pass
            return
        if text in ['سازنده','مالک ربات','خالق']:
            try: await bot_obj.send_message(chat_id, f"**👨‍💻 سازنده:** {CREATOR_ID}\n\n**📢 کانال:** {CHANNEL_LINK}", parse_mode="Markdown")
            except: pass
            return

        # ===== آمار گروه =====
        if text == 'آمار گروه' and (is_admin or is_creator):
            total_msgs = await get_group_total_messages(chat_id)
            today_msgs = await get_today_total_messages(chat_id)
            week_msgs = await get_week_total_messages(chat_id)
            month_msgs = await get_month_total_messages(chat_id)
            top = await get_top_users(chat_id, 3)
            out = f"**📊 آمار گروه**\n━━━━━━━━━━━━━━━━━━━━━━\n📝 **کل پیام‌ها:** {total_msgs}\n📅 **امروز:** {today_msgs}\n📆 **هفته:** {week_msgs}\n🌙 **ماه:** {month_msgs}\n━━━━━━━━━━━━━━━━━━━━━━\n🏆 **سه کاربر برتر:**\n"
            medals = ["🥇","🥈","🥉"]
            for i,(uid,cnt) in enumerate(top):
                nick = await get_nickname(chat_id, uid)
                out += f"{medals[i]} {nick if nick else f'[کاربر]({uid})'} — {cnt} پیام\n"
            try: await bot_obj.send_message(chat_id, out, parse_mode="Markdown")
            except: pass
            return

        # ===== آمارم =====
        if text in ['آمارم','امارم']:
            msg_count = await get_user_message_count(chat_id, user_id)
            msg_today = await get_user_message_count_today(chat_id, user_id)
            msg_week = await get_user_message_count_week(chat_id, user_id)
            msg_month = await get_user_message_count_month(chat_id, user_id)
            total_warns = await get_warn_count(chat_id, user_id)
            if user_id == OWNER_ID or is_creator: role = "👑 **مالک ربات**"
            elif is_admin: role = "🛡️ **ادمین ربات**"
            else: role = "👤 **کاربر عادی**"
            nickname = await get_nickname(chat_id, user_id)
            title = await get_title(chat_id, user_id)
            nick_txt = f"🏷️ **لقب:** {nickname}" if nickname else ""
            title_txt = f"🪪 **اصل:** {title}" if title else ""
            try:
                await bot_obj.send_message(chat_id, f"**📊 آمار شما**\n━━━━━━━━━━━━━━━━━━━━━━\n{role}\n\n{nick_txt}\n{title_txt}\n\n📅 **امروز:** {msg_today}\n📆 **هفته:** {msg_week}\n🌙 **ماه:** {msg_month}\n\n📝 **کل پیام‌ها:** {msg_count}\n━━━━━━━━━━━━━━━━━━━━━━\n🧊 ⚠️ **اخطارها:** {total_warns}/{max_warns}\n━━━━━━━━━━━━━━━━━━━━━━\n🧊 **ربات یخی**", parse_mode="Markdown")
            except: pass
            return

        # ===== ضد اسپم =====
        if anti_spam and await check_spam(chat_id, user_id) and not (is_admin or is_creator):
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            wc = await add_warn(chat_id, user_id, "spam")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "spam", wc, mw, bot_obj, is_manual=False)
            if wc >= mw:
                try:
                    await bot_obj.ban_member_chat(chat_id, user_id)
                    await clear_warns(chat_id, user_id, "spam")
                except: pass
            return

        # ===== قفل گروه و سکوت =====
        if await is_group_locked(chat_id) and not is_admin:
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            return
        if await is_muted(chat_id, user_id) and not is_admin:
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            return

        # ===== ضد فحش =====
        if anti_curse and contains_curse(text) and not (is_admin or is_creator):
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            wc = await add_warn(chat_id, user_id, "curse")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "curse", wc, mw, bot_obj, is_manual=False)
            if wc >= mw:
                try:
                    await bot_obj.ban_member_chat(chat_id, user_id)
                    await clear_warns(chat_id, user_id, "curse")
                except: pass
            return

        # ===== ضد گیف =====
        if anti_gif and is_gif(msg_obj) and not (is_admin or is_creator):
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            wc = await add_warn(chat_id, user_id, "gif")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "gif", wc, mw, bot_obj, is_manual=False)
            if wc >= mw:
                try:
                    await bot_obj.ban_member_chat(chat_id, user_id)
                    await clear_warns(chat_id, user_id, "gif")
                except: pass
            return

        # ===== ضد فیلم =====
        if anti_video and is_video(msg_obj) and not (is_admin or is_creator):
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            wc = await add_warn(chat_id, user_id, "video")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "video", wc, mw, bot_obj, is_manual=False)
            if wc >= mw:
                try:
                    await bot_obj.ban_member_chat(chat_id, user_id)
                    await clear_warns(chat_id, user_id, "video")
                except: pass
            return

        # ===== ضد هنگی =====
        if anti_hung and is_hung_code(text) and not (is_admin or is_creator):
            try: await bot_obj.delete_message(chat_id, message_id)
            except: pass
            wc = await add_warn(chat_id, user_id, "hung")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "hung", wc, mw, bot_obj, is_manual=False)
            if wc >= mw:
                try:
                    await bot_obj.ban_member_chat(chat_id, user_id)
                    await clear_warns(chat_id, user_id, "hung")
                except: pass
            return

        # ===== فعال‌سازی ربات =====
        if text == 'فعال':
            if active:
                try: await bot_obj.send_message(chat_id, "**🧊 ربات از قبل فعال است.**", parse_mode="Markdown")
                except: pass
                return
            if creator_id is None:
                c.execute("UPDATE groups SET active=1, creator_id=? WHERE group_id=?", (user_id, chat_id))
            else:
                c.execute("UPDATE groups SET active=1 WHERE group_id=?", (chat_id,))
            conn.commit()
            invalidate_group_cache(chat_id)
            try:
                await send_activation_message(chat_id, await get_group_name(chat_id), user_id)
                await send_auto_help(chat_id)
            except: pass
            return

        if not active:
            return

        # ===== حذف پیام با عدد =====
        del_match = re.match(r'حذف\s+(\d+)', text)
        if del_match and is_admin:
            count = int(del_match.group(1))
            if 1 <= count <= 200:
                status = await bot_obj.send_message(chat_id, f"⏳ در حال حذف {count} پیام...", parse_mode="Markdown")
                deleted = await delete_messages_with_status(chat_id, count, status.get('message_id'), bot_obj)
                try: await bot_obj.edit_message_text(chat_id, status.get('message_id'), f"**✅ {deleted} پیام از {count} با موفقیت حذف شد.**", parse_mode="Markdown")
                except: pass
            else:
                try: await bot_obj.send_message(chat_id, "**❌ تعداد باید 1 تا 200 باشد.**", parse_mode="Markdown")
                except: pass
            return

        # ===== تنظیم لقب و اصل =====
        if text.startswith('تنظیم لقب') and (is_admin or is_creator):
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            parts = text.split(' ', 2)
            if len(parts) < 3:
                try: await bot_obj.send_message(chat_id, "**❌ فرمت: تنظیم لقب (ریپلای) متن لقب**", parse_mode="Markdown")
                except: pass
                return
            nick = parts[2].strip()
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                await set_nickname(chat_id, row[0], nick)
                try: await bot_obj.send_message(chat_id, f"**✅ لقب «{nick}» تنظیم شد.**", parse_mode="Markdown")
                except: pass
            return
        if text.startswith('تنظیم اصل') and (is_admin or is_creator):
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            parts = text.split(' ', 2)
            if len(parts) < 3:
                try: await bot_obj.send_message(chat_id, "**❌ فرمت: تنظیم اصل (ریپلای) متن اصل**", parse_mode="Markdown")
                except: pass
                return
            tit = parts[2].strip()
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                await set_title(chat_id, row[0], tit)
                try: await bot_obj.send_message(chat_id, f"**✅ اصل «{tit}» تنظیم شد.**", parse_mode="Markdown")
                except: pass
            return

        # ===== انتقال مالکیت =====
        if text.startswith('انتقال مالکیت') and is_creator:
            parts = text.split()
            if len(parts) < 2:
                try: await bot_obj.send_message(chat_id, "**❌ فرمت: انتقال مالکیت @ایدی**", parse_mode="Markdown")
                except: pass
                return
            target = parts[1].replace('@','')
            await transfer_ownership(chat_id, user_id, target)
            try: await bot_obj.send_message(chat_id, f"**✅ مالکیت به {target} منتقل شد.**", parse_mode="Markdown")
            except: pass
            return

        # ===== اخطار دستی =====
        if text == 'اخطار' and is_admin:
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                target = row[0]
                target_is_admin = await is_group_admin(chat_id, target)
                target_is_creator = await is_group_creator(chat_id, target)
                if target == user_id or target_is_admin or target_is_creator:
                    try: await bot_obj.send_message(chat_id, "**❗ نمی‌توان به ادمین یا خودتان اخطار داد.**", parse_mode="Markdown")
                    except: pass
                    return
                wc = await add_warn(chat_id, target, "manual")
                mw = await get_max_warns(chat_id)
                await send_warning(chat_id, target, "manual", wc, mw, bot_obj, is_manual=True)
                if wc >= mw:
                    try:
                        await bot_obj.ban_member_chat(chat_id, target)
                        await clear_warns(chat_id, target, "manual")
                    except: pass
            return

        # ===== کاهش اخطار =====
        if text == 'کاهش اخطار' and is_admin:
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                await remove_warn(chat_id, row[0])
                try: await bot_obj.send_message(chat_id, f"**✅ اخطارهای کاربر پاک شد.**", parse_mode="Markdown")
                except: pass
            return

        # ===== بن =====
        if text == 'بن' and is_admin:
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                target = row[0]
                if target == creator_id:
                    try: await bot_obj.send_message(chat_id, "**⚠️ نمی‌توان مالک گروه را بن کرد!**", parse_mode="Markdown")
                    except: pass
                    return
                try:
                    await bot_obj.ban_member_chat(chat_id, target)
                    await send_ban_msg(chat_id, target, bot_obj)
                except Exception as e:
                    try: await bot_obj.send_message(chat_id, f"**❌ خطا: {e}**", parse_mode="Markdown")
                    except: pass
            return

        # ===== سیک =====
        if text == 'سیک' and is_admin:
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                target = row[0]
                if target == creator_id:
                    try: await bot_obj.send_message(chat_id, "**⚠️ نمی‌توان مالک گروه را سیک کرد!**", parse_mode="Markdown")
                    except: pass
                    return
                try:
                    await bot_obj.ban_member_chat(chat_id, target)
                    await asyncio.sleep(0.5)
                    await bot_obj.unban_chat_member(chat_id, target)
                    await send_kick_msg(chat_id, target, bot_obj)
                except Exception as e:
                    try: await bot_obj.send_message(chat_id, f"**❌ خطا: {e}**", parse_mode="Markdown")
                    except: pass
            return

        # ===== آن بن =====
        if text == 'آن بن' and is_admin:
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                target = row[0]
                try:
                    await bot_obj.unban_chat_member(chat_id, target)
                    await send_unban_msg(chat_id, target, bot_obj)
                except Exception as e:
                    try: await bot_obj.send_message(chat_id, f"**❌ خطا: {e}**", parse_mode="Markdown")
                    except: pass
            return

        # ===== آن سیک =====
        if text == 'آن سیک' and is_admin:
            if not reply_to_message_id:
                try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                except: pass
                return
            row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
            if row:
                target = row[0]
                try:
                    await bot_obj.unban_chat_member(chat_id, target)
                    await send_unkick_msg(chat_id, target, bot_obj)
                except Exception as e:
                    try: await bot_obj.send_message(chat_id, f"**❌ خطا: {e}**", parse_mode="Markdown")
                    except: pass
            return

        # ===== بازی‌ها =====
        if game_mode:
            if text in ['شانس','شانس من']:
                ch = random.randint(0,100)
                bar = '▓'*(ch//10)+'░'*(10-ch//10)
                desc = "💔 افسوس" if ch<30 else "👍 بد نیست" if ch<70 else "🎉 عالیه" if ch<90 else "🔥 شگفت‌انگیز"
                try: await bot_obj.send_message(chat_id, f"**🎯 شانس شما:** {ch}%\n┌━━━━━━━━━━━━━━━━━━━━━━┐\n│ 📊 {bar}\n│ 📝 {desc}\n└━━━━━━━━━━━━━━━━━━━━━━┘", parse_mode="Markdown")
                except: pass
                return
            if text == 'تاس':
                num = random.randint(1,6)
                try: await bot_obj.send_message(chat_id, f"**🎲 پرتاب تاس:** {dice_art(num)}  عدد {num}", parse_mode="Markdown")
                except: pass
                return
            if text == 'پرتاب':
                try: await bot_obj.send_message(chat_id, f"**🪙 پرتاب سکه:** {random.choice(['🦁 شیر', '🪙 خط'])}", parse_mode="Markdown")
                except: pass
                return

        # ===== دستورات ادمین (قفل/باز) =====
        if is_admin or is_creator:
            if text.startswith('تنظیم اخطار'):
                match = re.search(r'(\d+)', text)
                if match:
                    new_limit = int(match.group(1))
                    if 1 <= new_limit <= 10:
                        await set_max_warns(chat_id, new_limit)
                        try: await bot_obj.send_message(chat_id, f"**✅ حد اخطار به {new_limit} تغییر یافت.**", parse_mode="Markdown")
                        except: pass
                return

            # لینک
            if text in ['لینک قفل','قفل لینک']:
                await set_antilink(chat_id, True)
                await send_lock_msg(chat_id, "لینک", bot_obj)
                return
            if text in ['لینک باز','باز لینک']:
                await set_antilink(chat_id, False)
                await send_unlock_msg(chat_id, "لینک", bot_obj)
                return
            # فوروارد
            if text in ['فوروارد قفل','قفل فوروارد']:
                await set_block_forward(chat_id, True)
                await send_lock_msg(chat_id, "فوروارد", bot_obj)
                return
            if text in ['فوروارد باز','باز فوروارد']:
                await set_block_forward(chat_id, False)
                await send_unlock_msg(chat_id, "فوروارد", bot_obj)
                return
            # هنگی
            if text in ['هنگی قفل','قفل هنگی']:
                await set_anti_hung(chat_id, True)
                await send_lock_msg(chat_id, "هنگی", bot_obj)
                return
            if text in ['هنگی باز','باز هنگی']:
                await set_anti_hung(chat_id, False)
                await send_unlock_msg(chat_id, "هنگی", bot_obj)
                return
            # اسپم
            if text in ['اسپم قفل','قفل اسپم']:
                await set_anti_spam(chat_id, True)
                await send_lock_msg(chat_id, "اسپم", bot_obj)
                return
            if text in ['اسپم باز','باز اسپم']:
                await set_anti_spam(chat_id, False)
                await send_unlock_msg(chat_id, "اسپم", bot_obj)
                return
            # گیف
            if text in ['گیف قفل','قفل گیف']:
                await set_anti_gif(chat_id, True)
                await send_lock_msg(chat_id, "گیف", bot_obj)
                return
            if text in ['گیف باز','باز گیف']:
                await set_anti_gif(chat_id, False)
                await send_unlock_msg(chat_id, "گیف", bot_obj)
                return
            # فیلم
            if text in ['فیلم قفل','قفل فیلم']:
                await set_anti_video(chat_id, True)
                await send_lock_msg(chat_id, "فیلم", bot_obj)
                return
            if text in ['فیلم باز','باز فیلم']:
                await set_anti_video(chat_id, False)
                await send_unlock_msg(chat_id, "فیلم", bot_obj)
                return
            # فحش
            if text in ['فحش قفل','قفل فحش']:
                await set_anti_curse(chat_id, True)
                await send_lock_msg(chat_id, "فحش", bot_obj)
                return
            if text in ['فحش باز','باز فحش']:
                await set_anti_curse(chat_id, False)
                await send_unlock_msg(chat_id, "فحش", bot_obj)
                return
            # گیم بات
            if text in ['گیم بات قفل','قفل گیم بات']:
                await set_game_mode(chat_id, False)
                try: await bot_obj.send_message(chat_id, "**🔒 گیم بات قفل شد.**", parse_mode="Markdown")
                except: pass
                return
            if text in ['گیم بات باز','باز گیم بات']:
                await set_game_mode(chat_id, True)
                try: await bot_obj.send_message(chat_id, "**🎮 گیم بات باز شد.**", parse_mode="Markdown")
                except: pass
                return
            # سخنگو
            if text in ['سخنگو قفل','قفل سخنگو']:
                await set_speaker(chat_id, False)
                try: await bot_obj.send_message(chat_id, "**🔇 سخنگو قفل شد.**", parse_mode="Markdown")
                except: pass
                return
            if text in ['سخنگو باز','باز سخنگو']:
                await set_speaker(chat_id, True)
                try: await bot_obj.send_message(chat_id, "**🔊 سخنگو باز شد.**", parse_mode="Markdown")
                except: pass
                return
            # قفل گروه
            if text == 'قفل گروه':
                await lock_group(chat_id)
                await send_lock_msg(chat_id, "گروه", bot_obj)
                return
            if text in ['باز کردن گروه','باز گروه']:
                await unlock_group(chat_id)
                await send_unlock_msg(chat_id, "گروه", bot_obj)
                return

            # ===== سکوت =====
            if text == 'سکوت':
                if not reply_to_message_id:
                    try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                    except: pass
                    return
                row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
                if row and row[0] != user_id:
                    await mute_user(chat_id, row[0])
                    try: await bot_obj.send_message(chat_id, f"**🔇 [کاربر]({row[0]}) سکوت شد.**", parse_mode="Markdown")
                    except: pass
                return
            if text == 'حذف سکوت':
                if not reply_to_message_id:
                    try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                    except: pass
                    return
                row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
                if row:
                    await unmute_user(chat_id, row[0])
                    try: await bot_obj.send_message(chat_id, f"**🔊 سکوت [کاربر]({row[0]}) برداشته شد.**", parse_mode="Markdown")
                    except: pass
                return
            if text == 'لیست سکوت':
                muted_list = c.execute("SELECT user_id FROM mutes WHERE chat_id=?", (chat_id,)).fetchall()
                if muted_list:
                    out = "**🔇 لیست سکوت:**\n" + "\n".join(f"• [کاربر]({m[0]})" for m in muted_list)
                    try: await bot_obj.send_message(chat_id, out, parse_mode="Markdown")
                    except: pass
                else:
                    try: await bot_obj.send_message(chat_id, "**🔇 هیچ کاربری سکوت نشده است.**", parse_mode="Markdown")
                    except: pass
                return
            if text == 'پاکسازی سکوت':
                c.execute("DELETE FROM mutes WHERE chat_id=?", (chat_id,))
                conn.commit()
                try: await bot_obj.send_message(chat_id, "**✅ لیست سکوت پاک شد.**", parse_mode="Markdown")
                except: pass
                return

            # ===== افزودن/حذف ادمین =====
            if text == 'افزودن ادمین' and is_creator:
                if not reply_to_message_id:
                    try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                    except: pass
                    return
                row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
                if row:
                    c.execute("INSERT OR IGNORE INTO assistant_admins (chat_id, user_id) VALUES (?,?)", (chat_id, row[0]))
                    conn.commit()
                    try: await bot_obj.send_message(chat_id, f"**✅ [کاربر]({row[0]}) ادمین کمکی شد.**", parse_mode="Markdown")
                    except: pass
                return
            if text == 'حذف ادمین' and is_creator:
                if not reply_to_message_id:
                    try: await bot_obj.send_message(chat_id, "**❗ روی پیام کاربر ریپلای کنید.**", parse_mode="Markdown")
                    except: pass
                    return
                row = c.execute("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(reply_to_message_id))).fetchone()
                if row:
                    c.execute("DELETE FROM assistant_admins WHERE chat_id=? AND user_id=?", (chat_id, row[0]))
                    conn.commit()
                    try: await bot_obj.send_message(chat_id, f"**❌ [کاربر]({row[0]}) از ادمین‌ها حذف شد.**", parse_mode="Markdown")
                    except: pass
                return
            if text == 'لیست ادمین':
                admins = c.execute("SELECT user_id FROM assistant_admins WHERE chat_id=?", (chat_id,)).fetchall()
                if admins:
                    out = "**🛡️ ادمین‌های کمکی:**\n" + "\n".join(f"• [کاربر]({a[0]})" for a in admins)
                    try: await bot_obj.send_message(chat_id, out, parse_mode="Markdown")
                    except: pass
                else:
                    try: await bot_obj.send_message(chat_id, "**❌ ادمین کمکی وجود ندارد.**", parse_mode="Markdown")
                    except: pass
                return

            # ===== وضعیت گروه =====
            if text == 'وضعیت':
                is_locked = await is_group_locked(chat_id)
                total_msgs = await get_group_total_messages(chat_id)
                top = await get_top_users(chat_id, 3)
                medals = ["🥇","🥈","🥉"]
                top_text = "\n".join([f"   {medals[i]} [کاربر]({uid}) – {cnt} پیام" for i,(uid,cnt) in enumerate(top)]) if top else "   - هنوز پیامی نیست"
                creator_name = creator_id if creator_id else "تنظیم نشده"
                status_items = [
                    f"فعال: {'✅' if active else '❌'}",
                    f"لینک: {'🔒 قفل' if antilink else '🔓 باز'}",
                    f"سخنگو: {'🔊 روشن' if speaker else '🔇 خاموش'}",
                    f"فوروارد: {'🔒' if block_forward else '🔓'}",
                    f"هنگی: {'🔒' if anti_hung else '🔓'}",
                    f"اسپم: {'🔒' if anti_spam else '🔓'}",
                    f"گیف: {'🔒' if anti_gif else '🔓'}",
                    f"فیلم: {'🔒' if anti_video else '🔓'}",
                    f"فحش: {'🔒' if anti_curse else '🔓'}",
                    f"گیم‌بات: {'🎮 روشن' if game_mode else '❌ خاموش'}",
                    f"قفل گروه: {'🔒' if is_locked else '🔓'}"
                ]
                status_line = " | ".join(status_items)
                out = (f"**📊 وضعیت پیشرفته گروه**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"🔹 **شناسه:** `{chat_id}`\n🔹 **سازنده:** `{creator_name}`\n🔹 **کل پیام‌ها:** {total_msgs}\n"
                       f"🔹 **۳ کاربر برتر:**\n{top_text}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{status_line}\nحد اخطار: {max_warns}")
                try: await bot_obj.send_message(chat_id, out, parse_mode="Markdown")
                except: pass
                return

            # ===== فونت =====
            if text.startswith('فونت '):
                word = text[5:].strip()
                if word:
                    fonts = {
                        'کاپیتال': str.maketrans('abcdefghijklmnopqrstuvwxyz', 'ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ'),
                        'دایره': str.maketrans('abcdefghijklmnopqrstuvwxyz', 'ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ'),
                        'بولت': str.maketrans('abcdefghijklmnopqrstuvwxyz', '𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇'),
                        'ماتیس': str.maketrans('abcdefghijklmnopqrstuvwxyz', '𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳')
                    }
                    res = f"**✨ فونت‌های «{word}» ✨**\n━━━━━━━━━━━━━━━━━\n"
                    for name, trans in fonts.items():
                        res += f"🔹 **{name}:** {word.lower().translate(trans)}\n"
                    try: await bot_obj.send_message(chat_id, res, parse_mode="Markdown")
                    except: pass
                return

        # ===== سخنگو (آخرین اولویت) =====
        if speaker and not is_reply_to_others:
            low = text.lower()
            if low == 'سلام':
                try: await bot_obj.send_message(chat_id, "**سلام خوبی؟؟ 😊**", parse_mode="Markdown")
                except: pass
            elif any(w in low for w in ['درود','سلامتی']):
                try: await bot_obj.send_message(chat_id, "**سلام! خوبی؟ 😊**", parse_mode="Markdown")
                except: pass
            elif any(w in low for w in ['چطوری','خوبی','حالت چطوره']):
                try: await bot_obj.send_message(chat_id, "**خوبم! تو چطوری؟ 🤖**", parse_mode="Markdown")
                except: pass
            elif any(w in low for w in ['خداحافظ','بای','فعلا']):
                try: await bot_obj.send_message(chat_id, "**خداحافظ! 👋**", parse_mode="Markdown")
                except: pass
            elif 'ربات' in low or 'ربات یخی' in low or 'یخی' in low:
                try: await bot_obj.send_message(chat_id, "**🧊 بله جانم! ربات یخی در خدمت شماست.**", parse_mode="Markdown")
                except: pass
    except Exception as e:
        print(f"⚠️ خطا در پردازش گروه {chat_id}: {e}")

# ============================================================
# ========== توابع ارسال پیام‌های خوش‌آمدگویی و راهنما ===========
async def send_activation_message(chat_id, group_name, user_id):
    try:
        await bot.send_message(chat_id, "**🧊 ربات یخی (Ice Bot) فعال شد..↺**\n\n**✅️دسترسی شما با موفقیت ثبت شد.**\n\n**↺وضعیت : فعال و در حال نظارت«🤖** \n\n**قدرتِ مدیریت در دستان شماست.**\n\n🔗 [https://rubika.ir/IceBotGuide/BHEEABDCBFFEJEAB]\n\n**❄️ نظم در دمای انجماد.**", parse_mode="Markdown")
    except: pass
async def send_private_help(chat_id):
    try:
        await bot.send_message(chat_id, "**❄️راه اندازی ربات یخی (Ice Bot)🤖**\n\n**برای شروع به کار و فعال‌سازی قابلیت‌های امنیتی، لطفاً مراحل زیر را دنبال کنید:**\n\n**1️⃣ افزودن: ربات را به گروه خود اضافه کنید.**\n\n**2️⃣ مدیریت: به ربات نقش «ادمین» (با دسترسی کامل ) بدهید.**\n\n**3️⃣ فعال‌سازی: در گروه دستور «فعال» را ارسال کنید تا شما به عنوان ادمین گروه ثبت شوید.**\n\n🌐 آموزش و دستورات پیشرفته: \n[https://rubika.ir/IceBotGuide/BHEEABDCBFFEJEAB]\n\n**❄️با ربات یخی، گروهی امن داشته باشید.**", parse_mode="Markdown")
    except: pass
async def send_auto_help(chat_id):
    try:
        await bot.send_message(chat_id, "**✅️کانال دستورات:** \nhttps://rubika.ir/IceBotGuide/BHEEABDCBFFEJEAB", parse_mode="Markdown")
    except: pass

# ============================================================
# ========== راه‌اندازی Flask =================================
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return Response("Invalid request", status=400)

        msg_type = data.get("type")
        if msg_type == "ReceiveUpdate":
            message_data = data.get("message")
            if not message_data:
                return Response("OK", status=200)

            chat_id = message_data.get("chat_id")
            if not chat_id:
                return Response("OK", status=200)

            chat_type = message_data.get("chat_type")  # "private" یا "group"
            # اجرای توابع async با یک event loop جدید
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if chat_type == "private":
                loop.run_until_complete(handle_private_message(bot, message_data))
            else:
                loop.run_until_complete(handle_group_message(bot, message_data))
            loop.close()
        # در صورت نیاز به سایر نوع‌ها (ReceiveInlineMessage و ...) می‌توانید اضافه کنید

        return Response("OK", status=200)
    except Exception as e:
        print(f"خطا در وب‌هوک: {e}")
        return Response("Error", status=500)

# ========== اجرا در صورت مستقیم ==========
if __name__ == "__main__":
    print("✅ سرور Flask برای وب‌هوک راه‌اندازی شد.")
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
