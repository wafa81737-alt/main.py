#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gift of Life — Full Extractor v3 (iframe-aware)
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

# ═══════════════════════════════════════════════════
BOT_TOKEN = "8647240736:AAEGXuwmtZkUvAfbURX2BcyyuoWD-TekP_0"
CHAT_ID = 6843321125

BD_HOST = "brd.superproxy.io"
BD_PORT = "9222"
BD_USER = "brd-customer-hl_24c8058e-zone-scraping_browser1"
BD_PASS = "eyr0v46j28pi"

TARGET_URL = "https://gift-of-life.org/make-a-donation/"


def tg_msg(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text[:4000], "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as e:
        print(f"TG msg error: {e}", flush=True)


def tg_photo(path, caption=""):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": caption[:1000]},
                files={"photo": f},
                timeout=30
            )
    except Exception as e:
        print(f"TG photo error: {e}", flush=True)


def send_long(label, data):
    """يبعت JSON طويل على أجزاء"""
    txt = json.dumps(data, indent=1, ensure_ascii=False)
    if not txt.strip() or txt == "[]":
        tg_msg(f"{label}: <i>(empty)</i>")
        return
    chunks = [txt[i:i+3200] for i in range(0, len(txt), 3200)]
    for i, ch in enumerate(chunks):
        tg_msg(f"{label} ({i+1}/{len(chunks)}):\n<pre>{ch}</pre>")


EXTRACT_JS = """
() => {
    const out = { inputs: [], selects: [], textareas: [], buttons: [],
                  checkboxes: [], radios: [], labels: [], iframes: [], scripts: [] };

    document.querySelectorAll('input').forEach(el => {
        const t = (el.type || '').toLowerCase();
        const rec = {
            id: el.id || '', name: el.name || '', type: t,
            placeholder: el.placeholder || '', value: el.value || '',
            required: el.required, checked: el.checked,
            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
        };
        if (t === 'checkbox') out.checkboxes.push(rec);
        else if (t === 'radio') out.radios.push(rec);
        else out.inputs.push(rec);
    });

    document.querySelectorAll('select').forEach(el => {
        out.selects.push({
            id: el.id || '', name: el.name || '',
            options: Array.from(el.options).map(o => ({v: o.value, t: o.text})).slice(0, 30)
        });
    });

    document.querySelectorAll('textarea').forEach(el => {
        out.textareas.push({ id: el.id || '', name: el.name || '',
                             placeholder: el.placeholder || '' });
    });

    document.querySelectorAll('button, input[type=submit], input[type=button], a.button, a.btn').forEach(el => {
        out.buttons.push({
            id: el.id || '', name: el.name || '',
            type: el.type || el.tagName.toLowerCase(),
            text: (el.innerText || el.value || '').trim().slice(0, 60),
            class: (el.className || '').toString().slice(0, 80),
            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
        });
    });

    document.querySelectorAll('label').forEach(el => {
        out.labels.push({
            for: el.htmlFor || '',
            text: (el.innerText || '').trim().slice(0, 80)
        });
    });

    document.querySelectorAll('iframe').forEach(el => {
        out.iframes.push({
            id: el.id || '', name: el.name || '',
            src: (el.src || '').slice(0, 200),
            title: el.title || ''
        });
    });

    document.querySelectorAll('script[src]').forEach(el => {
        out.scripts.push((el.src || '').slice(0, 200));
    });

    return out;
}
"""


def extract_from_scope(scope, label):
    """يستخرج كل العناصر من page أو frame"""
    try:
        data = scope.evaluate(EXTRACT_JS)
    except Exception as e:
        tg_msg(f"⚠️ Extract failed on {label}: {str(e)[:150]}")
        return None

    total = sum(len(v) for v in data.values())
    tg_msg(f"📦 <b>{label}</b> — total elements: {total}")

    for key, items in data.items():
        if items:
            send_long(f"📋 {label} / {key.upper()}", items)
    return data


def run():
    tg_msg("🚀 Gift of Life Extractor v3 — Start")

    cdp_url = f"wss://{BD_USER}:{BD_PASS}@{BD_HOST}:{BD_PORT}"

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp(cdp_url, timeout=120000)
        tg_msg("✅ Connected to BrightData")
    except Exception as e:
        tg_msg(f"❌ Connect failed: {str(e)[:200]}")
        return

    context = browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent=("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"),
        locale="en-US",
    )
    page = context.new_page()
    page.set_default_timeout(60000)

    # ═══ 1. افتح الصفحة ═══
    tg_msg("🔄 [1] Opening page...")
    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(8)
        tg_msg(f"✅ Loaded: {page.title()[:80]}")
    except Exception as e:
        tg_msg(f"❌ Load failed: {str(e)[:200]}")
        return

    # ═══ 2. استخرج من الصفحة الرئيسية ═══
    tg_msg("🔄 [2] Extracting MAIN page...")
    extract_from_scope(page, "MAIN")

    # ═══ 3. استنى الـ iframes تتحمّل ═══
    tg_msg("🔄 [3] Waiting for iframes to load...")
    time.sleep(12)

    frames = page.frames
    tg_msg(f"🔎 Total frames found: {len(frames)}")

    # ═══ 4. عدد الـ iframes وروابطها ═══
    frame_info = []
    for i, f in enumerate(frames):
        try:
            frame_info.append({
                "index": i,
                "url": (f.url or "")[:200],
                "name": f.name or "",
                "is_main": f == page.main_frame,
            })
        except Exception:
            pass
    send_long("🖼️ FRAMES LIST", frame_info)

    # ═══ 5. استخرج من كل iframe ═══
    for i, f in enumerate(frames):
        if f == page.main_frame:
            continue
        try:
            url = f.url or ""
        except Exception:
            continue
        if not url or url.startswith("about:"):
            continue

        tg_msg(f"🔄 [4.{i}] Extracting from frame #{i}\n<code>{url[:150]}</code>")
        extract_from_scope(f, f"FRAME#{i}")

    # ═══ 6. Screenshot للفورم الرئيسي ═══
    try:
        page.screenshot(path="/tmp/main.png", full_page=True)
        tg_photo("/tmp/main.png", "📸 MAIN page")
    except Exception as e:
        tg_msg(f"⚠️ main screenshot: {e}")

    # ═══ 7. Screenshot لأي iframe ظاهر ═══
    try:
        iframes_loc = page.locator("iframe")
        cnt = iframes_loc.count()
        tg_msg(f"🔎 Visible iframes in DOM: {cnt}")
        for j in range(cnt):
            try:
                el = iframes_loc.nth(j)
                if el.is_visible():
                    el.screenshot(path=f"/tmp/iframe_{j}.png")
                    tg_photo(f"/tmp/iframe_{j}.png", f"📸 iframe #{j}")
            except Exception as e:
                tg_msg(f"⚠️ iframe #{j} screenshot: {str(e)[:100]}")
    except Exception as e:
        tg_msg(f"⚠️ iframe screenshots: {e}")

    # ═══ 8. HTML snippets (لو حابب) ═══
    try:
        main_html = page.content()
        tg_msg(f"📄 MAIN page HTML length: {len(main_html)}")

        # دوّر على كلمات مهمة
        for keyword in ["card", "cvv", "expir", "donat", "amount", "first", "last", "email"]:
            count = main_html.lower().count(keyword)
            if count:
                tg_msg(f"   • '{keyword}' appears {count}x in main HTML")

        # ابعت أول 3000 حرف من body innerText
        body_text = page.evaluate("document.body.innerText")
        if body_text:
            tg_msg(f"📝 MAIN body text:\n<pre>{body_text[:3000]}</pre>")
    except Exception as e:
        tg_msg(f"⚠️ HTML/text: {str(e)[:150]}")

    # ═══ 9. استخرج من كل iframe كمان HTML خام ═══
    for i, f in enumerate(frames):
        if f == page.main_frame:
            continue
        try:
            url = f.url or ""
            if not url or url.startswith("about:"):
                continue
            html = f.content()
            tg_msg(f"📄 FRAME#{i} HTML length: {len(html)}")
            # ابحث عن حقول مشهورة
            for kw in ["card-number", "cardNumber", "cvv", "cc-number", "donation-amount"]:
                if kw in html:
                    tg_msg(f"   ✅ FRAME#{i} contains '{kw}'")
        except Exception as e:
            tg_msg(f"⚠️ FRAME#{i} HTML: {str(e)[:100]}")

    tg_msg("✅ EXTRACTION DONE")

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
