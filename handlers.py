import re
import random
import asyncio
from api_handlers import *

# ========== راهنمای کامل (پررنگ) ==========
async def send_full_help(chat_id):
    await send_message(chat_id, 
"""❄️ **به ربات یخی خوش آمدید** 🤖

**برای شروع کار با ربات، مراحل زیر را دنبال کنید:**

**1️⃣** ربات را به گروه خود اضافه کنید

**2️⃣** به ربات نقش **ادمین** (با دسترسی کامل) بدهید

**3️⃣** در گروه دستور **فعال** را ارسال کنید

📚 **راهنمای کامل دستورات** :
https://rubika.ir/IceBotGuide/BHEEABDCBFFEJEAB

❄️ با ربات یخی، گروهی امن داشته باشید""")

# ========== پنل مدیریت (پررنگ) ==========
async def send_admin_panel(chat_id):
    await send_message(chat_id, 
"""🔐 **پنل مدیریت ربات یخی**

**🔹 آمار کلی ربات**
**🔹 پیام همگانی به همه گروه‌ها**
**🔹 بستن پنل**

📌 برای استفاده، یکی از گزینه‌های بالا را انتخاب کنید.""")

# ========== پردازش پیوی ==========
async def handle_private(chat_id, user_id, text):
    try:
        await db_execute("INSERT OR IGNORE INTO private_chats (chat_id) VALUES (?)", (str(chat_id),))
    except:
        pass
    
    is_owner = (user_id == OWNER_ID)
    
    if text == '/start':
        if is_owner:
            await send_admin_panel(chat_id)
        else:
            await send_full_help(chat_id)
        return
    
    if text == '/admin':
        if is_owner:
            await send_admin_panel(chat_id)
        else:
            await send_full_help(chat_id)
        return
    
    if is_owner:
        if text == 'آمار':
            total = (await db_fetchone("SELECT COUNT(*) FROM groups"))[0]
            active = (await db_fetchone("SELECT COUNT(*) FROM groups WHERE active=1"))[0]
            private = (await db_fetchone("SELECT COUNT(*) FROM private_chats"))[0]
            await send_message(chat_id, 
f"""📊 **آمار ربات یخی**
━━━━━━━━━━━━━━━━━━━━━━
📌 **کل گروه‌های ثبت شده** : {total}
✅ **گروه‌های فعال** : {active}
👤 **چت‌های خصوصی** : {private}
━━━━━━━━━━━━━━━━━━━━━━
🧊 ربات فعال""")
            return
        
        if text.startswith('پیام همگانی '):
            bc = text[12:].strip()
            if not bc:
                await send_message(chat_id, "❌ **متن پیام را وارد کنید**")
                return
            groups = await db_fetchall("SELECT group_id FROM groups")
            all_groups = [row[0] for row in groups]
            privates = await db_fetchall("SELECT chat_id FROM private_chats")
            all_priv = [row[0] for row in privates]
            total_targets = len(all_groups) + len(all_priv)
            if total_targets == 0:
                await send_message(chat_id, "⚠️ **هیچ گروه یا چت خصوصی‌ای یافت نشد**")
                return
            await send_message(chat_id, 
f"""📢 **شروع ارسال همگانی**...
👥 **گروه‌ها** : {len(all_groups)}
👤 **پیوی‌ها** : {len(all_priv)}""")
            semaphore = asyncio.Semaphore(50)
            async def send_to_chat(chat_id):
                async with semaphore:
                    try:
                        await send_message(chat_id, bc)
                        return True
                    except:
                        return False
            tasks = [send_to_chat(gid) for gid in all_groups] + [send_to_chat(pid) for pid in all_priv]
            results = await asyncio.gather(*tasks)
            success = sum(results)
            await send_message(chat_id, 
f"""✅ **پیام همگانی ارسال شد**
━━━━━━━━━━━━━━━━━
📢 **موفق** : {success} از {total_targets}""")
            return
        
        if text == 'بستن':
            await send_message(chat_id, "❌ **پنل بسته شد**")
            return
    
    await send_full_help(chat_id)

# ========== ارسال اخطار (پررنگ) ==========
async def send_warning(chat_id, user_id, warn_type, warn_count, max_warns, is_manual=False):
    if is_manual:
        first_line = f"⌫⌥ [کاربر]({user_id}) **اخطار دستی دریافت کرد** 〆"
    else:
        if warn_type == "link":
            first_line = f"⌫⌥ [کاربر]({user_id}) **لینک ممنوع است** 〆"
        elif warn_type == "forward":
            first_line = f"⌫⌥ [کاربر]({user_id}) **فوروارد ممنوع است** 〆"
        elif warn_type == "hung":
            first_line = f"⌫⌥ [کاربر]({user_id}) **کد هنگی ممنوع است** 〆"
        elif warn_type == "spam":
            first_line = f"⌫⌥ [کاربر]({user_id}) **اسپم ممنوع است** 〆"
        elif warn_type == "gif":
            first_line = f"⌫⌥ [کاربر]({user_id}) **گیف ممنوع است** 〆"
        elif warn_type == "video":
            first_line = f"⌫⌥ [کاربر]({user_id}) **فیلم ممنوع است** 〆"
        elif warn_type == "curse":
            first_line = f"⌫⌥ [کاربر]({user_id}) **فحش ممنوع است** 〆"
        else:
            first_line = f"⌫⌥ [کاربر]({user_id}) **تخلف کرد** 〆"
    second_line = f"›› شما **[ {warn_count}/{max_warns} ] اخطار دریافت کردید.**"
    await send_message(chat_id, f"{first_line}\n\n{second_line}")

# ========== پیام‌های قفل/باز (پررنگ) ==========
async def send_lock_msg(chat_id, lock_type):
    await send_message(chat_id, f"◎ **قفل {lock_type} با موفقیت فعال شد** ↺")

async def send_unlock_msg(chat_id, lock_type):
    await send_message(chat_id, f"◎ **{lock_type} → باز شد** ↻")

# ========== پیام‌های بن/سیک (پررنگ) ==========
async def send_ban_msg(chat_id, user_id):
    await send_message(chat_id, f"[کاربر]({user_id})\n\n›› **از گروه مسدود شد**")

async def send_kick_msg(chat_id, user_id):
    msgs = [
        f"[کاربر]({user_id})\n\n›› **شرش کم شد**",
        f"[کاربر]({user_id})\n\n›› **با جفت پا شوت شد بیرون**",
        f"[کاربر]({user_id})\n\n›› **سیکش زده شد**",
        f"[کاربر]({user_id})\n\n›› **به درک واصل شد**",
        f"[کاربر]({user_id})\n\n›› **گورشو گم کرد**"
    ]
    await send_message(chat_id, random.choice(msgs))

async def send_unban_msg(chat_id, user_id):
    await send_message(chat_id, f"[کاربر]({user_id})\n\n›› **از حالت بن خارج شد**")

async def send_unkick_msg(chat_id, user_id):
    await send_message(chat_id, f"[کاربر]({user_id})\n\n›› **به گروه برگردانده شد**")

# ========== فعال‌سازی (پررنگ) ==========
async def send_activation_msg(chat_id, user_id):
    await send_message(chat_id, 
"""🧊 **ربات یخی (Ice Bot) فعال شد** ↺

**دسترسی شما با موفقیت ثبت شد**

**وضعیت : فعال و در حال نظارت** 🤖

**قدرت مدیریت در دستان شماست**

🔗 https://rubika.ir/IceBotGuide/BHEEABDCBFFEJEAB

❄️ نظم در دمای انجماد""")

async def send_auto_help(chat_id):
    await send_message(chat_id, 
"""📚 **کانال دستورات** : 
https://rubika.ir/IceBotGuide/BHEEABDCBFFEJEAB""")

# ========== آمار شما (پررنگ) ==========
async def get_user_rank(chat_id, user_id):
    rows = await db_fetchall(
        "SELECT user_id, message_count FROM user_stats WHERE chat_id=? ORDER BY message_count DESC",
        (chat_id,)
    )
    for idx, (uid, cnt) in enumerate(rows, 1):
        if uid == user_id:
            return idx, cnt
    return None, 0

async def send_my_stats(chat_id, user_id, is_admin, is_creator):
    msg_count = await get_user_message_count(chat_id, user_id)
    total_warns = await get_warn_count(chat_id, user_id)
    max_warns = await get_max_warns(chat_id)
    
    rank, _ = await get_user_rank(chat_id, user_id)
    rank_text = f"〔 {rank} 〕" if rank else "〔 - 〕"
    
    today = await get_user_message_count_today(chat_id, user_id)
    week = await get_user_message_count_week(chat_id, user_id)
    month = await get_user_message_count_month(chat_id, user_id)
    
    if user_id == OWNER_ID or is_creator:
        role = "⌬ **مالک ربات**"
    elif is_admin:
        role = "⌬ **ادمین ربات**"
    else:
        role = "⌬ کاربر عادی"
    
    msg = (f"**آمار شما** 📊\n\n"
           f"{role}\n\n"
           f"› **رتبه** :{rank_text}\n\n"
           f"📅 **امروز** :  {today}\n"
           f"📆 **هفته** :  {week}\n"
           f"🌙 **ماه** :  {month}\n\n"
           f"⌧ **اخطارها**  :  {total_warns}/{max_warns}")
    
    await send_message(chat_id, msg)

# ========== وضعیت گروه (پررنگ) ==========
async def send_group_status(chat_id, settings, is_admin, is_creator):
    active = settings.get("active", 0)
    antilink = settings.get("antilink", 0)
    speaker = settings.get("speaker", 1)
    max_warns = settings.get("max_warns", 3)
    block_forward = settings.get("block_forward", 0)
    anti_hung = settings.get("anti_hung", 0)
    game_mode = settings.get("game_mode", 1)
    anti_spam = settings.get("anti_spam", 1)
    anti_gif = settings.get("anti_gif", 0)
    anti_video = settings.get("anti_video", 0)
    anti_curse = settings.get("anti_curse", 0)
    creator_id = settings.get("creator_id")
    is_locked = await is_group_locked(chat_id)
    
    lock_emoji = lambda x: "🔒" if x else "🔓"
    
    status_line = (f"**❖ وضعیت پیشرفته**\n\n"
                   f"›› **قفل** / **باز** ↺\n\n"
                   f"◎ **لینک** › {lock_emoji(antilink)}\n"
                   f"◎ **فوروارد** ›{lock_emoji(block_forward)}\n"
                   f"◎ **فحش** ›{lock_emoji(anti_curse)}\n"
                   f"◎ **هنگی** ›{lock_emoji(anti_hung)}\n"
                   f"◎ **اسپم** ›{lock_emoji(anti_spam)}\n"
                   f"◎ **گیف** ›{lock_emoji(anti_gif)}\n"
                   f"◎ **فیلم** ›{lock_emoji(anti_video)}\n"
                   f"◎ **گروه** ›{lock_emoji(is_locked)}\n"
                   f"◎ **سخنگو** ›{lock_emoji(not speaker)}\n"
                   f"◎ **گیم بات** ›{lock_emoji(not game_mode)}\n\n"
                   f"⬡ **حد اخطار** : {max_warns}\n\n"
                   f"⌬ **وضعیت ربات** {'فعال' if active else 'غیرفعال'} در حال نظارت ↺")
    
    await send_message(chat_id, status_line)

# ========== آمار گروه (پررنگ) ==========
async def send_group_stats(chat_id, settings):
    total_msgs = await get_group_total_messages(chat_id)
    today_msgs = await get_today_total_messages(chat_id)
    week_msgs = await get_week_total_messages(chat_id)
    month_msgs = await get_month_total_messages(chat_id)
    top = await get_top_users(chat_id, 3)
    active = settings.get("active", 0)
    
    top_text = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, cnt) in enumerate(top):
        nick = await get_nickname(chat_id, uid)
        name = nick if nick else f"[کاربر]({uid})"
        top_text += f"⌯ {name}\n"
    if not top_text:
        top_text = "⌯ هنوز کاربری نیست"
    
    msg = (f"**⌬ گزارش آمار گروه**\n\n"
           f"◍ **3 کاربر برتر**\n\n"
           f"{top_text}\n\n"
           f"◎ **وضعیت** : {'فعال' if active else 'غیرفعال'}\n\n"
           f"◈ **امروز** : {today_msgs:,} پیام\n"
           f"◈ **این هفته** : {week_msgs:,} پیام\n"
           f"◈ **این ماه** : {month_msgs:,} پیام")
    
    await send_message(chat_id, msg)

# ========== پردازش گروه ==========
async def handle_group(chat_id, user_id, text, message_id, msg):
    try:
        await save_message(chat_id, message_id, user_id)
        await inc_message_count(chat_id, user_id)
        
        settings = await get_group_settings(chat_id)
        active = settings.get("active", 0)
        antilink = settings.get("antilink", 0)
        speaker = settings.get("speaker", 1)
        max_warns = settings.get("max_warns", 3)
        block_forward = settings.get("block_forward", 0)
        anti_hung = settings.get("anti_hung", 0)
        game_mode = settings.get("game_mode", 1)
        anti_spam = settings.get("anti_spam", 1)
        anti_gif = settings.get("anti_gif", 0)
        anti_video = settings.get("anti_video", 0)
        anti_curse = settings.get("anti_curse", 0)
        creator_id = settings.get("creator_id")
        
        is_admin = await is_group_admin(chat_id, user_id)
        is_creator = await is_group_creator(chat_id, user_id)
        
        # ===== فعال‌سازی ربات =====
        if text == 'فعال':
            if active:
                await send_message(chat_id, "**ربات از قبل فعال است**")
                return
            if creator_id is None:
                await db_execute("UPDATE groups SET active=1, creator_id=? WHERE group_id=?", (user_id, chat_id))
            else:
                await db_execute("UPDATE groups SET active=1 WHERE group_id=?", (chat_id,))
            await send_activation_msg(chat_id, user_id)
            await send_auto_help(chat_id)
            return
        
        if not active:
            return
        
        # ===== ضد لینک =====
        if antilink and contains_link(text):
            if not (is_admin or is_creator):
                await delete_message(chat_id, message_id)
                wc = await add_warn(chat_id, user_id, "link")
                mw = await get_max_warns(chat_id)
                await send_warning(chat_id, user_id, "link", wc, mw)
                if wc >= mw:
                    await ban_user(chat_id, user_id)
                    await clear_warns(chat_id, user_id)
                return
        
        # ===== ضد فوروارد =====
        if block_forward and is_forward(msg):
            if not (is_admin or is_creator):
                await delete_message(chat_id, message_id)
                wc = await add_warn(chat_id, user_id, "forward")
                mw = await get_max_warns(chat_id)
                await send_warning(chat_id, user_id, "forward", wc, mw)
                if wc >= mw:
                    await ban_user(chat_id, user_id)
                    await clear_warns(chat_id, user_id)
                return
        
        # ===== راهنما =====
        if text in ['راهنما', 'help', 'کمک']:
            await send_auto_help(chat_id)
            return
        
        # ===== بیو چک =====
        if contains_bio_check(text):
            await delete_message(chat_id, message_id)
            wc = await add_warn(chat_id, user_id, "bio")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "bio", wc, mw)
            if wc >= mw:
                await ban_user(chat_id, user_id)
                await clear_warns(chat_id, user_id)
            return
        
        # ===== سازنده =====
        if text in ['سازنده', 'مالک ربات', 'خالق']:
            await send_message(chat_id, f"**سازنده** : {CREATOR_ID}\n\n**کانال** : {CHANNEL_LINK}")
            return
        
        # ===== آمار گروه =====
        if text in ['آمار گروه', 'امار گروه'] and (is_admin or is_creator):
            await send_group_stats(chat_id, settings)
            return
        
        # ===== آمارم =====
        if text in ['آمارم', 'امارم']:
            await send_my_stats(chat_id, user_id, is_admin, is_creator)
            return
        
        # ===== ضد اسپم =====
        if anti_spam and check_spam(chat_id, user_id) and not (is_admin or is_creator):
            await delete_message(chat_id, message_id)
            wc = await add_warn(chat_id, user_id, "spam")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "spam", wc, mw)
            if wc >= mw:
                await ban_user(chat_id, user_id)
                await clear_warns(chat_id, user_id)
            return
        
        # ===== قفل گروه و سکوت =====
        if await is_group_locked(chat_id) and not is_admin:
            await delete_message(chat_id, message_id)
            return
        
        if await is_muted(chat_id, user_id) and not is_admin:
            await delete_message(chat_id, message_id)
            return
        
        # ===== ضد فحش =====
        if anti_curse and contains_curse(text) and not (is_admin or is_creator):
            await delete_message(chat_id, message_id)
            wc = await add_warn(chat_id, user_id, "curse")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "curse", wc, mw)
            if wc >= mw:
                await ban_user(chat_id, user_id)
                await clear_warns(chat_id, user_id)
            return
        
        # ===== ضد گیف =====
        if anti_gif and is_gif(msg) and not (is_admin or is_creator):
            await delete_message(chat_id, message_id)
            wc = await add_warn(chat_id, user_id, "gif")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "gif", wc, mw)
            if wc >= mw:
                await ban_user(chat_id, user_id)
                await clear_warns(chat_id, user_id)
            return
        
        # ===== ضد فیلم =====
        if anti_video and is_video(msg) and not (is_admin or is_creator):
            await delete_message(chat_id, message_id)
            wc = await add_warn(chat_id, user_id, "video")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "video", wc, mw)
            if wc >= mw:
                await ban_user(chat_id, user_id)
                await clear_warns(chat_id, user_id)
            return
        
        # ===== ضد هنگی =====
        if anti_hung and is_hung_code(text) and not (is_admin or is_creator):
            await delete_message(chat_id, message_id)
            wc = await add_warn(chat_id, user_id, "hung")
            mw = await get_max_warns(chat_id)
            await send_warning(chat_id, user_id, "hung", wc, mw)
            if wc >= mw:
                await ban_user(chat_id, user_id)
                await clear_warns(chat_id, user_id)
            return
        
        # ===== حذف پیام =====
        del_match = re.match(r'حذف\s+(\d+)', text)
        if del_match and is_admin:
            count = int(del_match.group(1))
            if 1 <= count <= 200:
                rows = await db_fetchall("SELECT message_id FROM messages WHERE chat_id=? ORDER BY timestamp DESC LIMIT ?", (chat_id, count))
                deleted = 0
                for (mid,) in rows:
                    try:
                        await delete_message(chat_id, mid)
                        deleted += 1
                        await asyncio.sleep(0.005)
                    except:
                        pass
                await send_message(chat_id, f"✅ **{deleted} پیام از {count} با موفقیت حذف شد**")
            else:
                await send_message(chat_id, "❌ **تعداد باید 1 تا 200 باشد**")
            return
        
        # ===== تنظیم لقب =====
        if text.startswith('تنظیم لقب') and (is_admin or is_creator):
            parts = text.split(' ', 2)
            if len(parts) < 3:
                await send_message(chat_id, "❌ **فرمت : تنظیم لقب (ریپلای) متن لقب**")
                return
            nick = parts[2].strip()
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                await db_execute("INSERT OR REPLACE INTO user_ranks (chat_id, user_id, nickname, title) VALUES (?,?,?, COALESCE((SELECT title FROM user_ranks WHERE chat_id=? AND user_id=?), ''))", (chat_id, row[0], nick, chat_id, row[0]))
                await send_message(chat_id, f"✅ **لقب «{nick}» تنظیم شد**")
            return
        
        # ===== تنظیم اصل =====
        if text.startswith('تنظیم اصل') and (is_admin or is_creator):
            parts = text.split(' ', 2)
            if len(parts) < 3:
                await send_message(chat_id, "❌ **فرمت : تنظیم اصل (ریپلای) متن اصل**")
                return
            tit = parts[2].strip()
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                await db_execute("INSERT OR REPLACE INTO user_ranks (chat_id, user_id, title, nickname) VALUES (?,?,?, COALESCE((SELECT nickname FROM user_ranks WHERE chat_id=? AND user_id=?), ''))", (chat_id, row[0], tit, chat_id, row[0]))
                await send_message(chat_id, f"✅ **اصل «{tit}» تنظیم شد**")
            return
        
        # ===== انتقال مالکیت =====
        if text.startswith('انتقال مالکیت') and is_creator:
            parts = text.split()
            if len(parts) < 2:
                await send_message(chat_id, "❌ **فرمت : انتقال مالکیت @ایدی**")
                return
            target = parts[1].replace('@', '')
            await db_execute("UPDATE groups SET creator_id=? WHERE group_id=?", (target, chat_id))
            await send_message(chat_id, f"✅ **مالکیت به {target} منتقل شد**")
            return
        
        # ===== اخطار دستی =====
        if text == 'اخطار' and is_admin:
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                target = row[0]
                target_is_admin = await is_group_admin(chat_id, target)
                target_is_creator = await is_group_creator(chat_id, target)
                if target == user_id or target_is_admin or target_is_creator:
                    await send_message(chat_id, "**❗ نمی‌توان به ادمین یا خودتان اخطار داد**")
                    return
                wc = await add_warn(chat_id, target, "manual")
                mw = await get_max_warns(chat_id)
                await send_warning(chat_id, target, "manual", wc, mw, is_manual=True)
                if wc >= mw:
                    await ban_user(chat_id, target)
                    await clear_warns(chat_id, target)
            return
        
        # ===== کاهش اخطار =====
        if text == 'کاهش اخطار' and is_admin:
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                await clear_warns(chat_id, row[0])
                await send_message(chat_id, f"✅ **اخطارهای کاربر پاک شد**")
            return
        
        # ===== بن =====
        if text == 'بن' and is_admin:
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                target = row[0]
                creator = await db_fetchone("SELECT creator_id FROM groups WHERE group_id=?", (chat_id,))
                if creator and creator[0] == target:
                    await send_message(chat_id, "⚠️ **نمی‌توان مالک گروه را بن کرد**")
                    return
                await ban_user(chat_id, target)
                await send_ban_msg(chat_id, target)
            return
        
        # ===== سیک (با mute_user - restrictChatMember) =====
        if text == 'سیک' and is_admin:
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                target = row[0]
                creator = await db_fetchone("SELECT creator_id FROM groups WHERE group_id=?", (chat_id,))
                if creator and creator[0] == target:
                    await send_message(chat_id, "⚠️ **نمی‌توان مالک گروه را سیک کرد**")
                    return
                await mute_user(chat_id, target)
                await send_kick_msg(chat_id, target)
            return
        
        # ===== آن بن =====
        if text == 'آن بن' and is_admin:
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                target = row[0]
                await unban_user(chat_id, target)
                await send_unban_msg(chat_id, target)
            return
        
        # ===== آن سیک (با unmute_user - restrictChatMember) =====
        if text == 'آن سیک' and is_admin:
            row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
            if row:
                target = row[0]
                await unmute_user(chat_id, target)
                await send_unkick_msg(chat_id, target)
            return
        
        # ===== بازی‌ها =====
        if game_mode:
            if text in ['شانس', 'شانس من']:
                ch = random.randint(0, 100)
                bar = '▓' * (ch // 10) + '░' * (10 - ch // 10)
                desc = "💔 افسوس" if ch < 30 else "👍 بد نیست" if ch < 70 else "🎉 عالیه" if ch < 90 else "🔥 شگفت‌انگیز"
                await send_message(chat_id, f"🎯 **شانس شما** : {ch}%\n┌━━━━━━━━━━━━━━━━━━━━━━┐\n│ 📊 {bar}\n│ 📝 {desc}\n└━━━━━━━━━━━━━━━━━━━━━━┘")
                return
            if text == 'تاس':
                num = random.randint(1, 6)
                await send_message(chat_id, f"🎲 **پرتاب تاس** : {dice_art(num)}  عدد {num}")
                return
            if text == 'پرتاب':
                await send_message(chat_id, f"🪙 **پرتاب سکه** : {random.choice(['🦁 شیر', '🪙 خط'])}")
                return
        
        # ===== دستورات ادمین =====
        if is_admin or is_creator:
            if text.startswith('تنظیم اخطار'):
                match = re.search(r'(\d+)', text)
                if match:
                    new_limit = int(match.group(1))
                    if 1 <= new_limit <= 10:
                        await db_execute("UPDATE groups SET max_warns=? WHERE group_id=?", (new_limit, chat_id))
                        await send_message(chat_id, f"✅ **حد اخطار به {new_limit} تغییر یافت**")
                return
            
            if text in ['لینک قفل', 'قفل لینک']:
                await update_group_settings(chat_id, "antilink", 1)
                await send_lock_msg(chat_id, "لینک")
                return
            if text in ['لینک باز', 'باز لینک']:
                await update_group_settings(chat_id, "antilink", 0)
                await send_unlock_msg(chat_id, "لینک")
                return
            if text in ['فوروارد قفل', 'قفل فوروارد']:
                await update_group_settings(chat_id, "block_forward", 1)
                await send_lock_msg(chat_id, "فوروارد")
                return
            if text in ['فوروارد باز', 'باز فوروارد']:
                await update_group_settings(chat_id, "block_forward", 0)
                await send_unlock_msg(chat_id, "فوروارد")
                return
            if text in ['هنگی قفل', 'قفل هنگی']:
                await update_group_settings(chat_id, "anti_hung", 1)
                await send_lock_msg(chat_id, "هنگی")
                return
            if text in ['هنگی باز', 'باز هنگی']:
                await update_group_settings(chat_id, "anti_hung", 0)
                await send_unlock_msg(chat_id, "هنگی")
                return
            if text in ['اسپم قفل', 'قفل اسپم']:
                await update_group_settings(chat_id, "anti_spam", 1)
                await send_lock_msg(chat_id, "اسپم")
                return
            if text in ['اسپم باز', 'باز اسپم']:
                await update_group_settings(chat_id, "anti_spam", 0)
                await send_unlock_msg(chat_id, "اسپم")
                return
            if text in ['گیف قفل', 'قفل گیف']:
                await update_group_settings(chat_id, "anti_gif", 1)
                await send_lock_msg(chat_id, "گیف")
                return
            if text in ['گیف باز', 'باز گیف']:
                await update_group_settings(chat_id, "anti_gif", 0)
                await send_unlock_msg(chat_id, "گیف")
                return
            if text in ['فیلم قفل', 'قفل فیلم']:
                await update_group_settings(chat_id, "anti_video", 1)
                await send_lock_msg(chat_id, "فیلم")
                return
            if text in ['فیلم باز', 'باز فیلم']:
                await update_group_settings(chat_id, "anti_video", 0)
                await send_unlock_msg(chat_id, "فیلم")
                return
            if text in ['فحش قفل', 'قفل فحش']:
                await update_group_settings(chat_id, "anti_curse", 1)
                await send_lock_msg(chat_id, "فحش")
                return
            if text in ['فحش باز', 'باز فحش']:
                await update_group_settings(chat_id, "anti_curse", 0)
                await send_unlock_msg(chat_id, "فحش")
                return
            if text in ['گیم بات قفل', 'قفل گیم بات']:
                await update_group_settings(chat_id, "game_mode", 0)
                await send_message(chat_id, "**گیم بات قفل شد**")
                return
            if text in ['گیم بات باز', 'باز گیم بات']:
                await update_group_settings(chat_id, "game_mode", 1)
                await send_message(chat_id, "**گیم بات باز شد**")
                return
            if text in ['سخنگو قفل', 'قفل سخنگو']:
                await update_group_settings(chat_id, "speaker", 0)
                await send_message(chat_id, "**سخنگو قفل شد**")
                return
            if text in ['سخنگو باز', 'باز سخنگو']:
                await update_group_settings(chat_id, "speaker", 1)
                await send_message(chat_id, "**سخنگو باز شد**")
                return
            if text == 'قفل گروه':
                await db_execute("INSERT OR REPLACE INTO group_locks (chat_id, is_locked) VALUES (?,1)", (chat_id,))
                await send_lock_msg(chat_id, "گروه")
                return
            if text in ['باز کردن گروه', 'باز گروه']:
                await db_execute("INSERT OR REPLACE INTO group_locks (chat_id, is_locked) VALUES (?,0)", (chat_id,))
                await send_unlock_msg(chat_id, "گروه")
                return
            
            # ===== سکوت =====
            if text == 'سکوت':
                row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
                if row and row[0] != user_id:
                    await db_execute("INSERT OR REPLACE INTO mutes (chat_id, user_id) VALUES (?,?)", (chat_id, row[0]))
                    await send_message(chat_id, f"**[کاربر]({row[0]}) سکوت شد**")
                return
            if text == 'حذف سکوت':
                row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
                if row:
                    await db_execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, row[0]))
                    await send_message(chat_id, f"**سکوت [کاربر]({row[0]}) برداشته شد**")
                return
            if text == 'لیست سکوت':
                rows = await db_fetchall("SELECT user_id FROM mutes WHERE chat_id=?", (chat_id,))
                if rows:
                    out = "**لیست سکوت** :\n" + "\n".join(f"• [کاربر]({row[0]})" for row in rows)
                    await send_message(chat_id, out)
                else:
                    await send_message(chat_id, "**هیچ کاربری سکوت نشده است**")
                return
            if text == 'پاکسازی سکوت':
                await db_execute("DELETE FROM mutes WHERE chat_id=?", (chat_id,))
                await send_message(chat_id, "**لیست سکوت پاک شد**")
                return
            
            # ===== ادمین‌های کمکی =====
            if text == 'افزودن ادمین' and is_creator:
                row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
                if row:
                    await db_execute("INSERT OR IGNORE INTO assistant_admins (chat_id, user_id) VALUES (?,?)", (chat_id, row[0]))
                    await send_message(chat_id, f"**[کاربر]({row[0]}) ادمین کمکی شد**")
                return
            if text == 'حذف ادمین' and is_creator:
                row = await db_fetchone("SELECT sender_id FROM messages WHERE chat_id=? AND message_id=?", (chat_id, str(message_id)))
                if row:
                    await db_execute("DELETE FROM assistant_admins WHERE chat_id=? AND user_id=?", (chat_id, row[0]))
                    await send_message(chat_id, f"**[کاربر]({row[0]}) از ادمین‌ها حذف شد**")
                return
            if text == 'لیست ادمین':
                rows = await db_fetchall("SELECT user_id FROM assistant_admins WHERE chat_id=?", (chat_id,))
                if rows:
                    out = "**ادمین‌های کمکی** :\n" + "\n".join(f"• [کاربر]({row[0]})" for row in rows)
                    await send_message(chat_id, out)
                else:
                    await send_message(chat_id, "**ادمین کمکی وجود ندارد**")
                return
            
            # ===== وضعیت =====
            if text == 'وضعیت':
                await send_group_status(chat_id, settings, is_admin, is_creator)
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
                    res = f"**فونت‌های «{word}»**\n━━━━━━━━━━━━━━━━━\n"
                    for name, trans in fonts.items():
                        res += f"{name} : {word.lower().translate(trans)}\n"
                    await send_message(chat_id, res)
                return
        
        # ===== سخنگو =====
        if speaker:
            low = text.lower()
            if low == 'سلام':
                await send_message(chat_id, "سلام خوبی؟ 😊")
            elif any(w in low for w in ['درود', 'سلامتی']):
                await send_message(chat_id, "سلام! خوبی؟ 😊")
            elif any(w in low for w in ['چطوری', 'خوبی', 'حالت چطوره']):
                await send_message(chat_id, "خوبم! تو چطوری؟ 🤖")
            elif any(w in low for w in ['خداحافظ', 'بای', 'فعلا']):
                await send_message(chat_id, "خداحافظ! 👋")
            elif 'ربات' in low or 'ربات یخی' in low or 'یخی' in low:
                await send_message(chat_id, "بله جانم! ربات یخی در خدمت شماست")
    
    except Exception as e:
        print(f"خطا در گروه: {e}")
