import re
import random
import time
import httpx
import asyncio
from database import db_fetchone, db_fetchall, db_execute

# ===== تنظیمات =====
TOKEN = "BIBJAA0TEYWZAACJNBNFHUXZEDSUKTEMTHVJYTNVEYZYOYXBVROLYCKNURDHSXMQ"
OWNER_ID = "u0KIsuK0e84761d2e0d5e7c8bd819099"
CREATOR_ID = "@Robat_Yakhi"
CHANNEL_LINK = "@Robat_Yakhi"
API_BASE = "https://botapi.rubika.ir/v3"

# ========== تابع ارسال پیام با پشتیبانی از پررنگ ==========
async def send_message(chat_id, text, parse_mode="Markdown"):
    try:
        url = f"{API_BASE}/{TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload)
            print(f"✅ ارسال شد: {response.status_code}")  # برای دیباگ
            return response.json()
    except Exception as e:
        print(f"❌ send_message error: {e}")
        return None

# ========== حذف پیام ==========
async def delete_message(chat_id, message_id):
    try:
        url = f"{API_BASE}/{TOKEN}/deleteMessage"
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"chat_id": chat_id, "message_id": message_id})
    except:
        pass

# ========== بن ==========
async def ban_user(chat_id, user_id):
    try:
        url = f"{API_BASE}/{TOKEN}/banChatMember"
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"chat_id": chat_id, "user_id": user_id})
    except:
        pass

# ========== آن بن ==========
async def unban_user(chat_id, user_id):
    try:
        url = f"{API_BASE}/{TOKEN}/unbanChatMember"
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"chat_id": chat_id, "user_id": user_id})
    except:
        pass

# ========== سیک ==========
async def mute_user(chat_id, user_id):
    try:
        url = f"{API_BASE}/{TOKEN}/restrictChatMember"
        permissions = {
            "can_send_messages": False,
            "can_send_media_messages": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "user_id": user_id,
                "permissions": permissions
            })
    except:
        pass

# ========== آن سیک ==========
async def unmute_user(chat_id, user_id):
    try:
        url = f"{API_BASE}/{TOKEN}/restrictChatMember"
        permissions = {
            "can_send_messages": True,
            "can_send_media_messages": True,
            "can_send_other_messages": True,
            "can_add_web_page_previews": True
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "user_id": user_id,
                "permissions": permissions
            })
    except:
        pass

# ========== توابع کمکی ==========
curse_words = ['کص', 'کصی', 'کصو', 'کیر', 'کون', 'کیری', 'کله کیری', 'مادر جنده', 'ننه جنده', 'کص ننت', 'کص مادرت', 'کونی', 'حرومی', 'حروم زاده', 'قیندی', 'ننه کصو', 'مادرتو گاییدم', 'پدر سگ', 'اوبی', 'اوب', 'جنده', 'کص خواهرت', 'کصخل', 'کصکش', 'کونکش', 'کیرکش', 'پدرسگ', 'خارکصه', 'جاکش', 'گوه', 'گوز', 'گاییدم']

def contains_curse(text):
    text_lower = text.lower()
    for w in curse_words:
        if w in text_lower:
            return True
    return False

def contains_link(text):
    pattern = r'(https?://|www\.|t\.me/|@[\w]+|[\w-]+\.(ir|com|org|net|info|xyz|club|site|online|tech|space|me|link|bid|cf|ga|gq|ml|tk|io|ai|app|dev|pro|live|news|today|world|store|shop|blog|co|uk|us|ru|de|fr|it|es|nl|pl|tr|ae|sa|in|id|my|ph|vn|th|kr|jp|cn|tw|hk|sg))\b'
    return bool(re.search(pattern, text, re.I))

def is_hung_code(text):
    patterns = [r'(\.\s*){40,}', r'(\d\.){5,}', r'Filter', r'Ban', r'report', r'Spam', r'(.)\1{30,}', r'(\d{1,3}\.){4,}\d{1,3}']
    return any(re.search(p, text, re.I) for p in patterns)

def contains_bio_check(text):
    return any(re.search(p, text.lower()) for p in [r'بیو\s*چک', r'بیوگرافی\s*چک', r'بیوچک'])

def is_gif(msg):
    try:
        mime = msg.get('mime_type', '')
        if mime and mime.lower() == 'image/gif':
            return True
        doc = msg.get('document', {})
        if doc and doc.get('mime_type', '').lower() == 'image/gif':
            return True
        return msg.get('is_gif', False)
    except:
        return False

def is_video(msg):
    try:
        mime = msg.get('mime_type', '')
        if mime and 'video' in mime.lower() and 'gif' not in mime.lower():
            return True
        if msg.get('video'):
            return True
        if msg.get('is_video', False):
            return True
        doc = msg.get('document', {})
        if doc and 'video' in doc.get('mime_type', '').lower():
            return True
        return False
    except:
        return False

def is_forward(msg):
    try:
        if msg.get('forward_date') and msg.get('forward_date') is not None:
            return True
        if msg.get('forward_from') and msg.get('forward_from') is not None:
            return True
        if msg.get('forward_sender_name'):
            return True
        if msg.get('forward_chat') and msg.get('forward_chat') is not None:
            return True
        if msg.get('forward_signature'):
            return True
        if msg.get('forward') and msg.get('forward') is not None:
            return True
        if msg.get('is_forwarded', False):
            return True
        return False
    except:
        return False

def dice_art(n):
    return {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}.get(n, "⚀")

spam_tracker = {}
SPAM_INTERVAL = 5
SPAM_LIMIT = 4

def check_spam(chat_id, user_id):
    key = f"{chat_id}:{user_id}"
    now = time.time()
    if key not in spam_tracker:
        spam_tracker[key] = []
    timestamps = spam_tracker[key]
    timestamps = [t for t in timestamps if now - t < SPAM_INTERVAL]
    timestamps.append(now)
    spam_tracker[key] = timestamps
    return len(timestamps) > SPAM_LIMIT

# ========== توابع مدیریت گروه ==========
async def get_group_settings(chat_id):
    row = await db_fetchone("SELECT active, antilink, speaker, max_warns, creator_id, block_forward, anti_hung, game_mode, anti_spam, anti_gif, anti_video, anti_curse FROM groups WHERE group_id=?", (chat_id,))
    if row is None:
        await db_execute("INSERT INTO groups (group_id, name, active, antilink, speaker, max_warns, block_forward, anti_hung, game_mode, anti_spam, anti_gif, anti_video, anti_curse, creator_id, created_at) VALUES (?,?,0,0,1,3,0,0,1,1,0,0,0,NULL,?)", (chat_id, "گروه", int(time.time())))
        row = (0, 0, 1, 3, None, 0, 0, 1, 1, 0, 0, 0)
    return {"active": row[0], "antilink": row[1], "speaker": row[2], "max_warns": row[3], "creator_id": row[4], "block_forward": row[5], "anti_hung": row[6], "game_mode": row[7], "anti_spam": row[8], "anti_gif": row[9], "anti_video": row[10], "anti_curse": row[11]}

async def update_group_settings(chat_id, key, value):
    await db_execute(f"UPDATE groups SET {key}=? WHERE group_id=?", (value, chat_id))

async def is_group_admin(chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    row = await db_fetchone("SELECT creator_id FROM groups WHERE group_id=?", (chat_id,))
    if row and row[0] == user_id:
        return True
    row = await db_fetchone("SELECT 1 FROM assistant_admins WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return row is not None

async def is_group_creator(chat_id, user_id):
    row = await db_fetchone("SELECT creator_id FROM groups WHERE group_id=?", (chat_id,))
    return row and row[0] == user_id

async def add_warn(chat_id, user_id, warn_type="general"):
    t = int(time.time())
    await db_execute("INSERT INTO user_warns (chat_id, user_id, warn_type, warn_count, last_warn_time) VALUES (?,?,?,1,?) ON CONFLICT(chat_id, user_id, warn_type) DO UPDATE SET warn_count = warn_count + 1, last_warn_time = ?", (chat_id, user_id, warn_type, t, t))
    row = await db_fetchone("SELECT warn_count FROM user_warns WHERE chat_id=? AND user_id=? AND warn_type=?", (chat_id, user_id, warn_type))
    return row[0] if row else 1

async def get_warn_count(chat_id, user_id):
    row = await db_fetchone("SELECT SUM(warn_count) FROM user_warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return row[0] if row and row[0] else 0

async def get_max_warns(chat_id):
    row = await db_fetchone("SELECT max_warns FROM groups WHERE group_id=?", (chat_id,))
    return row[0] if row else 3

async def clear_warns(chat_id, user_id):
    await db_execute("DELETE FROM user_warns WHERE chat_id=? AND user_id=?", (chat_id, user_id))

async def is_muted(chat_id, user_id):
    row = await db_fetchone("SELECT 1 FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return row is not None

async def is_group_locked(chat_id):
    row = await db_fetchone("SELECT is_locked FROM group_locks WHERE chat_id=?", (chat_id,))
    return row and row[0] == 1

async def get_nickname(chat_id, user_id):
    row = await db_fetchone("SELECT nickname FROM user_ranks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return row[0] if row else None

async def get_title(chat_id, user_id):
    row = await db_fetchone("SELECT title FROM user_ranks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return row[0] if row else None

async def inc_message_count(chat_id, user_id):
    await db_execute("INSERT OR IGNORE INTO user_stats (chat_id, user_id, message_count) VALUES (?,?,0)", (chat_id, user_id))
    await db_execute("UPDATE user_stats SET message_count = message_count + 1 WHERE chat_id=? AND user_id=?", (chat_id, user_id))

async def get_user_message_count(chat_id, user_id):
    row = await db_fetchone("SELECT message_count FROM user_stats WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    return row[0] if row else 0

async def get_user_message_count_today(chat_id, user_id):
    from datetime import datetime
    today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    row = await db_fetchone("SELECT COUNT(*) FROM messages WHERE chat_id=? AND sender_id=? AND timestamp >= ?", (chat_id, user_id, today_start))
    return row[0] if row else 0

async def get_user_message_count_week(chat_id, user_id):
    from datetime import datetime, timedelta
    week_start = int((datetime.now() - timedelta(days=7)).timestamp())
    row = await db_fetchone("SELECT COUNT(*) FROM messages WHERE chat_id=? AND sender_id=? AND timestamp >= ?", (chat_id, user_id, week_start))
    return row[0] if row else 0

async def get_user_message_count_month(chat_id, user_id):
    from datetime import datetime, timedelta
    month_start = int((datetime.now() - timedelta(days=30)).timestamp())
    row = await db_fetchone("SELECT COUNT(*) FROM messages WHERE chat_id=? AND sender_id=? AND timestamp >= ?", (chat_id, user_id, month_start))
    return row[0] if row else 0

async def get_group_total_messages(chat_id):
    row = await db_fetchone("SELECT SUM(message_count) FROM user_stats WHERE chat_id=?", (chat_id,))
    return row[0] if row else 0

async def get_today_total_messages(chat_id):
    from datetime import datetime
    today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    row = await db_fetchone("SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp >= ?", (chat_id, today_start))
    return row[0] if row else 0

async def get_week_total_messages(chat_id):
    from datetime import datetime, timedelta
    week_start = int((datetime.now() - timedelta(days=7)).timestamp())
    row = await db_fetchone("SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp >= ?", (chat_id, week_start))
    return row[0] if row else 0

async def get_month_total_messages(chat_id):
    from datetime import datetime, timedelta
    month_start = int((datetime.now() - timedelta(days=30)).timestamp())
    row = await db_fetchone("SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp >= ?", (chat_id, month_start))
    return row[0] if row else 0

async def get_top_users(chat_id, limit=3):
    rows = await db_fetchall("SELECT user_id, message_count FROM user_stats WHERE chat_id=? ORDER BY message_count DESC LIMIT ?", (chat_id, limit))
    return rows

async def save_message(chat_id, message_id, user_id):
    await db_execute("INSERT OR REPLACE INTO messages (chat_id, message_id, sender_id, timestamp) VALUES (?,?,?,?)", (str(chat_id), str(message_id), str(user_id), int(time.time())))
