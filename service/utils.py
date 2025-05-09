import asyncio
import random
from datetime import datetime

from playwright.async_api import Page, Locator

# 비동기 랜덤 대기
async def async_random_delay(min_ms=300, max_ms=800):
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

# 타임스탬프 포함된 로깅
def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# 특수 문자 제거 (파일 이름용 등)
def clean_filename(text: str):
    return ''.join(c for c in text if c.isalnum() or c in (' ', '-', '_')).rstrip()

def log(status, place_id, extra=None):
    now = datetime.now().strftime("%H:%M:%S")
    msg = f"[{now}] [{status}] PlaceID: {place_id}"
    if extra:
        msg += f" - {extra}"
    print(msg)

async def block_unnecessary_resources(page):
    async def route_intercept(route):
        if route.request.resource_type in ["image", "stylesheet", "font"]:
            await route.abort()
        else:
            await route.continue_()
    await page.route("**/*", route_intercept)

async def safe_page_content(page: Page, timeout=10):
    try:
        return await asyncio.wait_for(page.content(), timeout=timeout)
    except asyncio.TimeoutError:
        print("❌ page.content() timeout")
        return None

# 페이지나 스크롤 가능한 엘리먼트에서 더 이상 높이가 늘어나지 않을 때까지 스크롤
async def scroll_until_no_more(page_or_element, wait_time=0.7, max_attempts=30) -> None:
    previous_height = -1
    for attempt in range(max_attempts):
        current_height = await page_or_element.evaluate("(el) => el.scrollHeight")
        await page_or_element.evaluate("(el) => el.scrollTo(0, el.scrollHeight)")
        await asyncio.sleep(wait_time)
        if current_height == previous_height:
            break
        previous_height = current_height
