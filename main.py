"""
Playwright — Authorize.Net Payment Flow
- يفتح صفحة الـ order-pay
- يدوس على زرار الدفع
- يستنى الـ payment form من Authorize.Net
- يدخل بيانات البطاقة
- يدوس Submit
- يطبع النتيجة
"""

import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


# ═══════════════════════════════════════════════════════════
#  البيانات
# ═══════════════════════════════════════════════════════════
ORDER_PAY_URL = "https://www.beyondlimitsriding.org/checkout/order-pay/27296/?key=wc_order_vuSkXmwK1gF7T"

CARD = {
    'number': '4472270012028906',
    'expiry': '12/27',        # MM/YY
    'cvv': '123',             # مش موجود في الـ curl — حط الـ CVV الصح
    'first_name': 'Wafa',
    'last_name': 'Bro',
    'address': 'W356 W456',
    'city': 'Carifnia',
    'state': 'WI',
    'zip': '90011',
    'email': 'wafabro9870@gmail.com',
    'phone': '44985367122',
}

HEADLESS = False   # خليه False عشان تشوف المتصفح وتتدخل لو احتاجت


def run():
    print("=" * 60)
    print("Playwright — Authorize.Net Payment")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ],
        )

        context = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
            ),
            viewport={'width': 412, 'height': 915},
            locale='en-US',
            timezone_id='America/New_York',
        )

        page = context.new_page()

        # ─── 1. افتح صفحة الـ order-pay ───
        print("\n[1] فتح صفحة order-pay...")
        try:
            page.goto(ORDER_PAY_URL, wait_until='networkidle', timeout=60000)
        except PWTimeout:
            print("[!] الصفحة خدت وقت طويل — هكمل بـ domcontentloaded")
            page.goto(ORDER_PAY_URL, wait_until='domcontentloaded', timeout=60000)

        print(f"[+] URL: {page.url}")
        print(f"[+] Title: {page.title()}")

        # ─── 2. دوّر على زرار الدفع ───
        print("\n[2] البحث عن زرار الدفع...")
        pay_selectors = [
            'button#place_order',
            'button[name="woocommerce_checkout_place_order"]',
            'input#place_order',
            'input[name="woocommerce_checkout_place_order"]',
            'button:has-text("Pay")',
            'button:has-text("Place order")',
            'button:has-text("Donate")',
            'input[type="submit"]',
        ]

        pay_button = None
        for sel in pay_selectors:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    pay_button = el
                    print(f"[+] لقيته: {sel}")
                    break
            except Exception:
                continue

        if not pay_button:
            print("[!] مفيش زرار دفع ظاهر — هصور الصفحة وأوقف")
            page.screenshot(path='order_pay.png', full_page=True)
            browser.close()
            return

        # ─── 3. دوّر على حقول البطاقة (لو موجودة في الصفحة) ───
        print("\n[3] البحث عن حقول البطاقة...")
        card_field_found = False
        for sel in [
            'input[name*="card_number"]',
            'input[name*="cardNumber"]',
            'input[id*="card-number"]',
            'input[autocomplete="cc-number"]',
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    print(f"[+] حقل البطاقة: {sel}")
                    el.fill(CARD['number'])
                    card_field_found = True
                    break
            except Exception:
                continue

        if card_field_found:
            # املأ باقي الحقول
            for sel, value in [
                ('input[name*="expiry"], input[name*="exp_date"], input[autocomplete="cc-exp"]', CARD['expiry']),
                ('input[name*="cvv"], input[name*="cvc"], input[autocomplete="cc-csc"]', CARD['cvv']),
            ]:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0 and el.is_visible():
                        el.fill(value)
                except Exception:
                    pass

        # ─── 4. دوس على زرار الدفع ───
        print("\n[4] الضغط على زرار الدفع...")
        try:
            pay_button.click(timeout=10000)
        except Exception as e:
            print(f"[!] فشل الضغط: {e}")
            page.screenshot(path='before_click.png', full_page=True)
            browser.close()
            return

        # ─── 5. استنى الـ payment form من Authorize.Net ───
        print("\n[5] انتظار Authorize.Net...")
        start = time.time()
        authorize_frame = None
        while time.time() - start < 60:
            for frame in page.frames:
                if 'authorize.net' in (frame.url or '').lower():
                    authorize_frame = frame
                    print(f"[+] Authorize.Net frame: {frame.url[:100]}")
                    break
            if authorize_frame:
                break

            if 'authorize.net' in page.url.lower():
                print(f"[+] الصفحة اتحولت لـ Authorize.Net: {page.url[:100]}")
                break

            time.sleep(1)

        if not authorize_frame and 'authorize.net' not in page.url.lower():
            print("[!] مفيش Authorize.Net ظهر — هصور وأطبع الـ URLs")
            page.screenshot(path='no_authorize.png', full_page=True)
            print(f"[+] URL الحالي: {page.url}")
            for f in page.frames:
                print(f"    frame: {f.url[:100]}")
            browser.close()
            return

        # ─── 6. املأ بيانات البطاقة في Authorize.Net ───
        print("\n[6] ملء بيانات البطاقة...")
        target = authorize_frame if authorize_frame else page

        try:
            target.wait_for_load_state('networkidle', timeout=30000)
        except Exception:
            pass

        # حقول Authorize.Net
        field_map = {
            'input[name="x_card_num"], input#x_card_num': CARD['number'],
            'input[name="x_exp_date"], input#x_exp_date': CARD['expiry'].replace('/', ''),
            'input[name="x_first_name"], input#x_first_name': CARD['first_name'],
            'input[name="x_last_name"], input#x_last_name': CARD['last_name'],
            'input[name="x_address"], input#x_address': CARD['address'],
            'input[name="x_city"], input#x_city': CARD['city'],
            'input[name="x_state"], input#x_state': CARD['state'],
            'input[name="x_zip"], input#x_zip': CARD['zip'],
            'input[name="x_email"], input#x_email': CARD['email'],
            'input[name="x_phone"], input#x_phone': CARD['phone'],
        }

        filled = 0
        for sel, value in field_map.items():
            try:
                el = target.locator(sel).first
                if el.count() > 0:
                    el.fill(value)
                    filled += 1
                    print(f"    ✅ {sel.split(',')[0].strip()}")
            except Exception as e:
                print(f"    ⚠️  {sel.split(',')[0].strip()}: {e}")

        print(f"[+] اتملى {filled} حقل")

        # ─── 7. دوّر على Submit في Authorize.Net ───
        print("\n[7] Submit...")
        submit_selectors = [
            'input[type="submit"][value*="Submit"]',
            'input[type="submit"]',
            'button[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Pay")',
        ]

        submit_btn = None
        for sel in submit_selectors:
            try:
                el = target.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    submit_btn = el
                    print(f"[+] Submit: {sel}")
                    break
            except Exception:
                continue

        if not submit_btn:
            print("[!] مفيش Submit — هصور وأطبع الصفحة")
            try:
                target.screenshot(path='authorize_form.png', full_page=True)
            except Exception:
                page.screenshot(path='authorize_form.png', full_page=True)
            browser.close()
            return

        try:
            submit_btn.click(timeout=10000)
        except Exception as e:
            print(f"[!] فشل Submit: {e}")
            page.screenshot(path='submit_fail.png', full_page=True)
            browser.close()
            return

        # ─── 8. استنى النتيجة ───
        print("\n[8] انتظار النتيجة...")
        try:
            page.wait_for_load_state('networkidle', timeout=60000)
        except PWTimeout:
            pass

        time.sleep(3)
        page.screenshot(path='final_result.png', full_page=True)

        # اطبع نص الصفحة
        try:
            text = page.locator('body').inner_text(timeout=10000)
        except Exception:
            text = ""

        print(f"\n[+] URL النهائي: {page.url}")
        print(f"[+] عنوان الصفحة: {page.title()}")

        # ابحث عن كلمات مفتاحية
        text_lower = text.lower()
        if any(k in text_lower for k in ['approved', 'thank you', 'success', 'receipt', 'confirmed']):
            print("\n✅ ممكن يكون APPROVED — راجع final_result.png")
        elif any(k in text_lower for k in ['declined', 'failed', 'error', 'invalid', 'incorrect']):
            print("\n❌ ممكن يكون DECLINED/ERROR — راجع final_result.png")
        else:
            print("\n⚠️  نتيجة غير معروفة — راجع final_result.png")

        print(f"\n[+] أول 1500 حرف من الصفحة:\n{text[:1500]}")

        # سيب المتصفح مفتوح شوية لو عايز تتدخل
        if not HEADLESS:
            print("\n[*] المتصفح هيفضل مفتوح 60 ثانية...")
            time.sleep(60)

        browser.close()


if __name__ == '__main__':
    run()
