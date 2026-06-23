import requests
import os
import sys
import time

# ===== دریافت توکن از متغیر محیطی یا استفاده از مقدار پیش‌فرض =====
TOKEN = os.getenv("RUBIKA_TOKEN", "BHJDEE0PRUSZOEDQRURMLYODBRJYJRBWYVVDDIMEXGFSZEOSTZIESECHRMSPWCLK")
WEBHOOK_URL = "https://yakhii.ir/webhook"  # آدرس وب‌هوک شما

# ===== اندپوینت‌های مختلف روبیکا =====
ENDPOINTS = [
    "ReceiveUpdate",          # پیام‌های معمولی
    "ReceiveInlineMessage",   # پیام‌های اینلاین (کلیک روی دکمه‌ها)
    "ReceiveQuery",           # کوئری‌ها
    "GetSelectionItem",       # انتخاب آیتم
    "SearchSelectionItems"    # جستجوی آیتم‌ها
]

# ===== آدرس API روبیکا =====
API_URL = f"https://botapi.rubika.ir/v3/{TOKEN}/updateBotEndpoints"

# ============================================================
# ========== تابع چک کردن سرور ==========
def check_server():
    """بررسی می‌کند که آیا سرور وب‌هوک در دسترس است یا خیر."""
    print("🔄 در حال بررسی سرور...")
    try:
        response = requests.get(WEBHOOK_URL, timeout=5)
        if response.status_code == 200:
            print(f"✅ سرور در دسترس است (وضعیت: {response.status_code})")
            return True
        else:
            print(f"⚠️ سرور پاسخ داد اما وضعیت غیرمنتظره: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ خطا: نمی‌توان به {WEBHOOK_URL} متصل شد. مطمئن شوید سرور در حال اجراست.")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ خطا: زمان اتصال به {WEBHOOK_URL} به پایان رسید.")
        return False
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در بررسی سرور: {e}")
        return False

# ============================================================
# ========== تابع ثبت وب‌هوک ==========
def register_webhook():
    """ثبت وب‌هوک برای تمام اندپوینت‌های مشخص شده."""
    print("=" * 60)
    print("🔧 شروع ثبت وب‌هوک در روبیکا...")
    print(f"📡 آدرس وب‌هوک: {WEBHOOK_URL}")
    print(f"🤖 توکن: {TOKEN[:10]}...{TOKEN[-10:]}")
    print("=" * 60)

    # چک کردن سرور قبل از ثبت
    if not check_server():
        print("\n❌ ثبت وب‌هوک لغو شد. ابتدا سرور را راه‌اندازی کنید.")
        return False

    success_count = 0
    failed_endpoints = []

    for endpoint in ENDPOINTS:
        payload = {
            "url": WEBHOOK_URL,
            "type": endpoint
        }
        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"✅ {endpoint}: ثبت شد (وضعیت: {response.status_code})")
                success_count += 1
            else:
                print(f"❌ {endpoint}: خطا! وضعیت: {response.status_code} - {response.text[:100]}")
                failed_endpoints.append(endpoint)
        except requests.exceptions.Timeout:
            print(f"❌ {endpoint}: زمان اتصال به سرور به پایان رسید.")
            failed_endpoints.append(endpoint)
        except Exception as e:
            print(f"❌ {endpoint}: خطای غیرمنتظره: {e}")
            failed_endpoints.append(endpoint)

    # ===== گزارش نهایی =====
    print("=" * 60)
    print("📊 گزارش ثبت وب‌هوک:")
    print(f"✅ موفق: {success_count} از {len(ENDPOINTS)}")
    if failed_endpoints:
        print(f"❌ ناموفق: {', '.join(failed_endpoints)}")
    else:
        print("🎉 همه اندپوینت‌ها با موفقیت ثبت شدند!")

    if failed_endpoints:
        print("\n💡 نکات عیب‌یابی:")
        print("  1. مطمئن شوید ربات در روبیکا فعال است.")
        print("  2. توکن را بررسی کنید (در متغیر محیطی RUBIKA_TOKEN یا داخل کد).")
        print("  3. مطمئن شوید سرور وب‌هوک در حال اجراست و آدرس درست است.")
        print(f"  4. آدرس وب‌هوک: {WEBHOOK_URL} باید HTTPS باشد.")
        return False

    print("=" * 60)
    print("✅ ثبت وب‌هوک کامل شد!")
    return True

# ============================================================
# ========== اجرای مستقیم ==========
if __name__ == "__main__":
    try:
        register_webhook()
    except KeyboardInterrupt:
        print("\n⏹️ عملیات توسط کاربر متوقف شد.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {e}")
        sys.exit(1)
