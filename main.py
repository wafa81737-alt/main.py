#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life Donation v18 — Deep Inspection of card fields
"""

import os
import time
import json
import requests
import traceback

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system("pip install playwright")
    os.system("playwright install chromium")
    from playwright.sync_api import sync_playwright

BOT_TOKEN = "8647240736:AAEGXuwmtZkUvAfbURX2BcyyuoWD-TekP_0"
CHAT_ID = 6843321125

BD_HOST = "brd.superproxy.io"
BD_PORT = "9222"
BD_USER = "brd-customer-hl_24c8058e-zone-scraping_browser1"
BD_PASS = "eyr0v46j28pi"

TARGET_URL = "https://gift-of-life.org/make-a-donation/"

P = "_ArrevaOnlineDonationsPortlet_WAR_ArrevaOnlineDonationsPortlet_:form1:"

def tg_msg(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text[:4000], "parse_mode": "HTML"}, timeout=15)
    except Exception as e:
        print(f"TG msg error: {e}", flush=True)

def tg_long(label, text, chunk=3500):
    tg_msg(f"{label} (len={len(text)})")
    for i in range(0, len(text), chunk):
        tg_msg(f"<pre>{text[i:i+chunk]}</pre>")
        time.sleep(0.3)

def find_donation_frame(page, total_seconds=120):
    start = time.time()
    attempt = 0
    while time.time() - start < total_seconds:
        attempt += 1
        for f in page.frames:
            try:
                if f.locator('[id*="datafirst"]').first.count() > 0:
                    return f, attempt
            except Exception:
                pass
        time.sleep(2)
    return None, attempt

def inspect_field(frame, field_suffix, label):
    """فحص عميق لحقل واحد"""
    tg_msg(f"🔍 Inspecting {label} ({field_suffix})...")
    
    result = frame.evaluate("""(id) => {
        const el = document.getElementById(id);
        if (!el) return {error: 'not found'};
        
        const info = {
            // 1. Basic
            tagName: el.tagName,
            type: el.type,
            id: el.id,
            name: el.name,
            className: el.className,
            placeholder: el.placeholder,
            value: el.value,
            maxLength: el.maxLength,
            readOnly: el.readOnly,
            disabled: el.disabled,
            
            // 2. Visibility & position
            offsetWidth: el.offsetWidth,
            offsetHeight: el.offsetHeight,
            offsetTop: el.offsetTop,
            offsetLeft: el.offsetLeft,
            
            // 3. Style
            computedStyle: (() => {
                try {
                    const cs = window.getComputedStyle(el);
                    return {
                        display: cs.display,
                        visibility: cs.visibility,
                        opacity: cs.opacity,
                        pointerEvents: cs.pointerEvents,
                        position: cs.position,
                        zIndex: cs.zIndex,
                        webkitTextSecurity: cs.webkitTextSecurity || cs.textSecurity,
                    };
                } catch(e) { return {error: String(e)}; }
            })(),
            
            // 4. Attributes
            attributes: (() => {
                const attrs = {};
                for (const a of el.attributes) {
                    attrs[a.name] = a.value;
                }
                return attrs;
            })(),
            
            // 5. HTML
            outerHTML: el.outerHTML,
            innerHTML: el.innerHTML,
            
            // 6. Parent
            parentTag: el.parentElement ? el.parentElement.tagName : null,
            parentId: el.parentElement ? el.parentElement.id : null,
            parentClass: el.parentElement ? el.parentElement.className : null,
            parentOuterHTML: el.parentElement ? el.parentElement.outerHTML.slice(0, 2000) : null,
            
            // 7. Shadow DOM
            hasShadowRoot: !!el.shadowRoot,
            shadowRootHTML: el.shadowRoot ? el.shadowRoot.innerHTML : null,
            
            // 8. Event listeners (partial - playwright can't get all)
            hasOninput: !!el.oninput,
            hasOnchange: !!el.onchange,
            hasOnkeydown: !!el.onkeydown,
            hasOnkeyup: !!el.onkeyup,
            hasOnkeypress: !!el.onkeypress,
            hasOnblur: !!el.onblur,
            hasOnfocus: !!el.onfocus,
            hasOnpaste: !!el.onpaste,
            hasOncopy: !!el.oncopy,
            hasOncut: !!el.oncut,
            
            // 9. jQuery handlers
            jqueryEvents: (() => {
                try {
                    if (typeof window.jQuery === 'undefined') return null;
                    const events = window.jQuery._data(el, 'events');
                    if (!events) return null;
                    const result = {};
                    for (const evt in events) {
                        result[evt] = events[evt].map(h => ({
                            type: h.type,
                            namespace: h.namespace,
                            selector: h.selector,
                        }));
                    }
                    return result;
                } catch(e) { return {error: String(e)}; }
            })(),
            
            // 10. React/Vue props
            reactProps: (() => {
                try {
                    const keys = Object.keys(el).filter(k => k.startsWith('__react') || k.startsWith('_react'));
                    return keys.length > 0 ? keys : null;
                } catch(e) { return null; }
            })(),
            
            // 11. DOM properties
            allOwnProps: (() => {
                try {
                    return Object.getOwnPropertyNames(el).filter(k => !k.startsWith('_') && k !== 'style');
                } catch(e) { return []; }
            })(),
            
            // 12. Custom properties (non-native)
            customProps: (() => {
                try {
                    const result = {};
                    for (const k in el) {
                        try {
                            const val = el[k];
                            if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') {
                                if (k.includes('card') || k.includes('token') || k.includes('encrypt') || 
                                    k.includes('deluxe') || k.includes('sdk') || k.includes('secure')) {
                                    result[k] = val;
                                }
                            }
                        } catch(e) {}
                    }
                    return result;
                } catch(e) { return {}; }
            })(),
        };
        
        return info;
    }""", f"{P}{field_suffix}")
    
    tg_long(f"🔍 {label} INSPECTION", json.dumps(result, indent=1, ensure_ascii=False))
    return result

def inspect_all_inputs_near(frame, field_suffix):
    """يفحص كل الـ inputs اللي حوالين حقل معين"""
    result = frame.evaluate("""(id) => {
        const el = document.getElementById(id);
        if (!el) return {error: 'not found'};
        
        const parent = el.closest('div, fieldset, tr, td') || el.parentElement;
        if (!parent) return {error: 'no parent'};
        
        const inputs = [];
        parent.querySelectorAll('input, select, textarea, iframe, [role="textbox"]').forEach(inp => {
            inputs.push({
                tag: inp.tagName,
                type: inp.type || '',
                id: inp.id || '',
                name: inp.name || '',
                className: inp.className || '',
                value: (inp.value || '').slice(0, 20),
                visible: !!(inp.offsetWidth || inp.offsetHeight || inp.getClientRects().length),
                outerHTML: (inp.outerHTML || '').slice(0, 500),
            });
        });
        return {parentHTML: parent.outerHTML.slice(0, 3000), inputs};
    }""", f"{P}{field_suffix}")
    
    return result

def test_typing_behavior(frame, field_suffix, label):
    """يختبر إيه اللي بيحصل لما نكتب بإيد"""
    tg_msg(f"⌨️ Testing typing behavior for {label}...")
    
    results = []
    
    # 1. Click + type
    try:
        el = frame.locator(f'[id="{P}{field_suffix}"]').first
        el.click(timeout=3000)
        frame.page.keyboard.type("1", delay=100)
        time.sleep(0.5)
        v1 = frame.evaluate("(id) => document.getElementById(id)?.value", f"{P}{field_suffix}")
        results.append(f"M1 click+type(1): '{v1}'")
    except Exception as e:
        results.append(f"M1 ERR: {str(e)[:80]}")
    
    # 2. Fill "1"
    try:
        el = frame.locator(f'[id="{P}{field_suffix}"]').first
        el.fill("2", timeout=3000)
        time.sleep(0.5)
        v2 = frame.evaluate("(id) => document.getElementById(id)?.value", f"{P}{field_suffix}")
        results.append(f"M2 fill(2): '{v2}'")
    except Exception as e:
        results.append(f"M2 ERR: {str(e)[:80]}")
    
    # 3. JS set "3"
    try:
        frame.evaluate("""(id) => {
            const el = document.getElementById(id);
            if (el) { el.value = '3'; el.dispatchEvent(new Event('input', {bubbles: true})); }
        }""", f"{P}{field_suffix}")
        time.sleep(0.5)
        v3 = frame.evaluate("(id) => document.getElementById(id)?.value", f"{P}{field_suffix}")
        results.append(f"M3 JS(3): '{v3}'")
    except Exception as e:
        results.append(f"M3 ERR: {str(e)[:80]}")
    
    tg_msg(f"⌨️ {label} typing results:\n" + "\n".join(results))

def check_global_objects(frame, page):
    """يفحص كل الـ globals اللي ممكن تكون بتتحكم في البطاقة"""
    tg_msg("🌐 Checking global objects...")
    
    result = frame.evaluate("""() => {
        const result = {
            window_keys: [],
            card_related_globals: {},
            iframes_in_frame: [],
            script_urls: [],
        };
        
        // 1. كل الـ window keys
        for (const k of Object.keys(window)) {
            const kl = k.toLowerCase();
            if (kl.includes('card') || kl.includes('payment') || kl.includes('token') || 
                kl.includes('encrypt') || kl.includes('secure') || kl.includes('deluxe') ||
                kl.includes('checkout') || kl.includes('sdk') || kl.includes('stripe') ||
                kl.includes('square') || kl.includes('braintree')) {
                try {
                    const v = window[k];
                    result.card_related_globals[k] = {
                        type: typeof v,
                        isFunction: typeof v === 'function',
                        isObject: typeof v === 'object',
                        keys: typeof v === 'object' && v ? Object.keys(v).slice(0, 20) : null,
                    };
                } catch(e) {
                    result.card_related_globals[k] = {error: String(e)};
                }
            }
        }
        
        // 2. iframes جوا الـ frame
        document.querySelectorAll('iframe').forEach((f, i) => {
            result.iframes_in_frame.push({
                index: i,
                id: f.id,
                name: f.name,
                src: (f.src || '').slice(0, 200),
                visible: !!(f.offsetWidth || f.offsetHeight),
            });
        });
        
        // 3. scripts
        document.querySelectorAll('script[src]').forEach(s => {
            result.script_urls.push(s.src);
        });
        
        return result;
    }""")
    
    tg_long("🌐 GLOBALS", json.dumps(result, indent=1, ensure_ascii=False))

def check_network_after_typing(page, frame):
    """يفحص network requests اللي بتحصل بعد الكتابة"""
    tg_msg("📡 Setting up network monitor for typing...")
    
    network_requests = []
    
    def on_request(req):
        url = req.url.lower()
        if any(k in url for k in ['deluxe', 'payment', 'token', 'card', 'encrypt', 'secure', 'cc']):
            network_requests.append({
                'url': req.url[:200],
                'method': req.method,
                'post_data': (req.post_data or '')[:500],
            })
    
    page.on("request", on_request)
    
    # اكتب في الحقل
    try:
        el = frame.locator(f'[id="{P}cardNumber"]').first
        el.click(timeout=3000)
        frame.page.keyboard.type("5", delay=200)
        time.sleep(2)
    except Exception as e:
        tg_msg(f"⚠️ typing error: {str(e)[:100]}")
    
    if network_requests:
        tg_long("📡 NETWORK AFTER TYPING", json.dumps(network_requests, indent=1, ensure_ascii=False))
    else:
        tg_msg("📡 NETWORK AFTER TYPING: no requests")

def run():
    tg_msg("🚀 Gift of Life v18 — DEEP INSPECTION")

    cdp_url = f"wss://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=120000)
        tg_msg("✅ Connected")
    except Exception as e:
        tg_msg(f"❌ Connect: {str(e)[:200]}")
        return

    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"),
        locale="en-US",
    )
    page = context.new_page()
    page.set_default_timeout(60000)

    # 1. افتح
    tg_msg("🔄 Opening...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(10)
    except Exception as e:
        tg_msg(f"❌ Load: {str(e)[:200]}")
        return
    tg_msg("✅ Page loaded")

    # 2. ابحث عن الـ frame
    tg_msg("🔄 Finding form...")
    frame, attempts = find_donation_frame(page, 120)
    if not frame:
        tg_msg("❌ not found")
        return
    tg_msg(f"✅ frame='{frame.name}'")
    time.sleep(5)

    # 3. فحص عميق لكل حقل
    tg_msg("🔄 [3] Deep inspection of card fields...")
    inspect_field(frame, "cardNumber", "Card Number")
    inspect_field(frame, "cardCSV", "CVV")
    inspect_field(frame, "nameOnCard", "Name on Card")

    # 4. فحص الـ inputs الحوالين
    tg_msg("🔄 [4] Inspecting nearby inputs...")
    nearby = inspect_all_inputs_near(frame, "cardNumber")
    tg_long("📋 NEARBY INPUTS", json.dumps(nearby, indent=1, ensure_ascii=False)[:8000])

    # 5. فحص globals
    tg_msg("🔄 [5] Checking globals...")
    check_global_objects(frame, page)

    # 6. اختبار الكتابة
    tg_msg("🔄 [6] Testing typing behavior...")
    test_typing_behavior(frame, "cardNumber", "Card Number")

    # 7. مراقبة network بعد الكتابة
    tg_msg("🔄 [7] Monitoring network...")
    check_network_after_typing(page, frame)

    # 8. screenshot
    try:
        page.screenshot(path="/tmp/inspect.png", full_page=True)
        with open("/tmp/inspect.png", "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": "📸 Inspection state"},
                files={"photo": f},
                timeout=30
            )
    except Exception:
        pass

    tg_msg("✅ DONE — send inspection results")
    
    try: context.close()
    except: pass
    try: browser.close()
    except: pass
    try: pw.stop()
    except: pass

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        tg_msg(f"❌ FATAL:\n{traceback.format_exc()[:3500]}")
