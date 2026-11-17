import asyncio
from playwright.async_api import async_playwright

EMAIL = "wghio89@example.com"
PASSWORD = "brobroT879"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False)
        ctx = await b.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            locale="ar-AE",
        )
        page = await ctx.new_page()
        await page.goto("https://dashboard.webshare.io/register?source=login_signup_link")
        await page.fill('input[type="email"]', EMAIL)
        await page.fill('input[type="password"]', PASSWORD)
        # وافق على الشروط
        cb = await page.query_selector('input[type="checkbox"]')
        if cb: await cb.check()
        # سيب reCAPTCHA v3/invisible يشتغل لوحده
        await page.wait_for_timeout(5000)
        await page.click('button[type="submit"]')
        await page.wait_for_url("**/proxylist**", timeout=90000)
        # جيب API key
        await page.goto("https://dashboard.webshare.io/userapi/keys")
        await page.wait_for_timeout(3000)
        key = await page.input_value('input[name="api_key"]')
        print("API KEY:", key)
        await b.close()

asyncio.run(main())
