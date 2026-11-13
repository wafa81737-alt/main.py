#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Authorize.Net Payment Bot — Telegram (Fixed)
"""

import os
import sys
import time
import asyncio
import traceback
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ═══════════════════════════════════════════════════════════
#  إعدادات
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = "8407490230:AAEhaQd1CAsCH8qRaaFCQ65o9RVAf8EdTiA"
ADMIN_CHAT_ID = 6843321125

ORDER_PAY_URL = "https://www.beyondlimitsriding.org/checkout/order-pay/27296/?key=wc_order_vuSkXmwK1gF7T"

CARD = {
    'number': '4472270012028906',
    'expiry': '12/27',
    'cvv': '123',
    'first_name': 'Wafa',
    'last_name': 'Bro',
    'address': 'W356 W456',
    'city': 'Carifnia',
    'state': 'WI',
    'zip': '90011',
    'email': 'wafabro9870@gmail.com',
    'phone': '44985367122',
}

SCREENSHOT_DIR = "/app/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════
#  Logging
# ═══════════════════════════════════════════════════════════
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════
def save_screenshot(page, prefix="error"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCREENSHOT_DIR, f"{prefix}_{ts}.png")
    try:
        page.screenshot(path=path, full_page=True)
        return path
    except Exception:
        try:
            page.screenshot(path=path)
            return path
        except Exception:
            return None


async def send_screenshot_to_admin(bot, path, caption=""):
    if not path or not os.path.exists(path):
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ خطأ (مفيش سكرين شوت)\n{caption[:1000]}",
        )
        return
    try:
        with open(path, 'rb') as f:
            await bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=f,
                caption=f"📸 خطأ:\n{caption[:900]}",
            )
    except Exception as e:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ فشل إرسال السكرين شوت: {e}\n{caption[:500]}",
        )


# ═══════════════════════════════════════════════════════════
#  Payment logic (sync — will run in executor)
# ═══════════════════════════════════════════════════════════
def run_payment():
    result = {
        'success': False,
        'status': 'unknown',
        'message': '',
        'url': '',
        'screenshot': None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu',
            ],
        )
        context = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
            ),
            viewport={'width': 412, 'height': 915},
            locale='en-US',
        )
        page = context.new_page()

        try:
            try:
                page.goto(ORDER_PAY_URL, wait_until='networkidle', timeout=60000)
            except PWTimeout:
                page.goto(ORDER_PAY_URL, wait_until='domcontentloaded', timeout=60000)

            result['url'] = page.url

            pay_selectors = [
                'button#place_order',
                'button[name="woocommerce_checkout_place_order"]',
                'input#place_order',
                'button:has-text("Pay")',
                'button:has-text("Place order")',
                'button:has-text("Donate")',
                'input[type="submit"]',
            ]
            pay_button = None
            for sel in pay_selectors:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        pay_button = el
                        break
                except Exception:
                    continue

            if not pay_button:
                raise RuntimeError("مفيش زرار دفع ظاهر")

            for sel, val in [
                ('input[name*="card_number"], input[autocomplete="cc-number"]', CARD['number']),
                ('input[name*="expiry"], input[autocomplete="cc-exp"]', CARD['expiry']),
                ('input[name*="cvv"], input[autocomplete="cc-csc"]', CARD['cvv']),
            ]:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        el.fill(val)
                except Exception:
                    pass

            pay_button.click(timeout=15000)

            start = time.time()
            authorize_frame = None
            while time.time() - start < 60:
                for frame in page.frames:
                    if 'authorize.net' in (frame.url or '').lower():
                        authorize_frame = frame
                        break
                if authorize_frame:
                    break
                if 'authorize.net' in page.url.lower():
                    break
                time.sleep(1)

            if not authorize_frame and 'authorize.net' not in page.url.lower():
                path = save_screenshot(page, "no_authorize")
                raise RuntimeError(f"مفيش Authorize.Net ظهر. URL: {page.url}")

            target = authorize_frame if authorize_frame else page

            try:
                target.wait_for_load_state('networkidle', timeout=30000)
            except Exception:
                pass

            fields = {
                'input[name="x_card_num"], input#x_card_num': CARD['number'],
                'input[name="x_exp_date"], input#x_exp_date': CARD['expiry'].replace('/', ''),
                'input[name="x_first_name"], input#x_first_name': CARD['first_name'],
                'input[name="x_last_name"], input#x_last_name': CARD['last_name'],
                'input[name="x_address"], input#x_address': CARD['address'],
                'input[name="x_city"], input#x_city': CARD['city'],
                'input[name="x_state"], input#x_state': CARD['state'],
                'input[name="x_zip"], input#x_zip': CARD['zip'],
                'input[name="x_email"], input#x_email': CARD['email'],
                'input[name="x_phone"], input#x_phone': CARD['phone'],
            }
            for sel, val in fields.items():
                try:
                    el = target.locator(sel).first
                    if el.count() > 0:
                        el.fill(val)
                except Exception:
                    pass

            submit_selectors = [
                'input[type="submit"][value*="Submit"]',
                'input[type="submit"]',
                'button[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Pay")',
            ]
            submit_btn = None
            for sel in submit_selectors:
                try:
                    el = target.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        submit_btn = el
                        break
                except Exception:
                    continue

            if not submit_btn:
                path = save_screenshot(page, "no_submit")
                raise RuntimeError("مفيش Submit في فورم Authorize.Net")

            submit_btn.click(timeout=15000)

            try:
                page.wait_for_load_state('networkidle', timeout=60000)
            except PWTimeout:
                pass
            time.sleep(3)

            result['url'] = page.url
            path = save_screenshot(page, "result")
            result['screenshot'] = path

            try:
                text = page.locator('body').inner_text(timeout=10000)
            except Exception:
                text = ""

            result['message'] = text[:1000]
            low = text.lower()

            if any(k in low for k in ['approved', 'thank you', 'success', 'receipt', 'confirmed']):
                result['success'] = True
                result['status'] = 'approved'
            elif any(k in low for k in ['declined', 'failed', 'error', 'invalid', 'incorrect']):
                result['status'] = 'declined'
            else:
                result['status'] = 'unknown'

        except Exception as e:
            path = save_screenshot(page, "exception")
            result['screenshot'] = path
            result['message'] = f"{type(e).__name__}: {e}"
            result['status'] = 'exception'
            raise
        finally:
            try:
                browser.close()
            except Exception:
                pass

    return result


# ═══════════════════════════════════════════════════════════
#  Command handlers
# ═══════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start from {update.effective_chat.id}")
    await update.message.reply_text(
        "🤖 Authorize.Net Payment Bot\n\n"
        "/pay — ابدأ محاولة الدفع\n"
        "/status — حالة البوت\n"
        "/screenshot — آخر سكرين شوت\n"
        "/help — المساعدة"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/status from {update.effective_chat.id}")
    await update.message.reply_text(
        f"✅ البوت شغال\n"
        f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🎯 Target: {ORDER_PAY_URL[:80]}..."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/help from {update.effective_chat.id}")
    await update.message.reply_text(
        "استخدم /pay عشان تبدأ محاولة دفع.\n"
        "لو حصل خطأ، هيوصلك سكرين شوت هنا أوتوماتيك."
    )


async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/screenshot from {update.effective_chat.id}")
    files = sorted(
        [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith('.png')],
        key=lambda x: os.path.getmtime(os.path.join(SCREENSHOT_DIR, x)),
        reverse=True,
    )
    if not files:
        await update.message.reply_text("مفيش سكرين شوت لسه.")
        return
    latest = os.path.join(SCREENSHOT_DIR, files[0])
    with open(latest, 'rb') as f:
        await update.message.reply_photo(photo=f, caption=f"آخر سكرين شوت: {files[0]}")


async def cmd_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/pay from {update.effective_chat.id}")
    await update.message.reply_text("⏳ جاري تشغيل محاولة الدفع...")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, run_payment)

        if result['success']:
            await update.message.reply_text(
                f"✅ APPROVED\n\n{result['message'][:800]}"
            )
        else:
            await update.message.reply_text(
                f"⚠️ status: {result['status']}\n\n{result['message'][:800]}"
            )

        if result.get('screenshot'):
            await send_screenshot_to_admin(
                context.bot,
                result['screenshot'],
                f"نتيجة /pay: {result['status']}\nURL: {result['url']}",
            )

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"/pay error: {e}\n{tb}")
        await update.message.reply_text(f"❌ خطأ:\n{e}")

        files = sorted(
            [f for f in os.listdir(SCREENSHOT_DIR) if f.startswith('exception_')],
            key=lambda x: os.path.getmtime(os.path.join(SCREENSHOT_DIR, x)),
            reverse=True,
        )
        if files:
            path = os.path.join(SCREENSHOT_DIR, files[0])
            await send_screenshot_to_admin(
                context.bot,
                path,
                f"{type(e).__name__}: {e}\n\n{tb[-800:]}",
            )
        else:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ خطأ بدون سكرين شوت:\n{e}\n\n{tb[-800:]}",
            )


# ═══════════════════════════════════════════════════════════
#  Main — async properly
# ═══════════════════════════════════════════════════════════
async def main_async():
    logger.info("Starting bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))
    app.add_handler(CommandHandler("pay", cmd_pay))

    logger.info("Bot handlers registered. Starting polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # خلي البوت شغال
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def main():
    print("=" * 60)
    print("Authorize.Net Payment Bot")
    print("=" * 60)
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.error(f"Fatal: {e}\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == '__main__':
    main()
