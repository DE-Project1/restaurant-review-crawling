import asyncio
import re
import random
import os
import time
from playwright.async_api import async_playwright, Page, Locator
from datetime import datetime

CONCURRENT_PAGES = 4  # 동시 탭 개수
MAX_SEARCH_SCROLLS = 20
MAX_REVIEW_CLICKS = 11
MAX_REVIEWS = 100
DEFAULT_TIMEOUT = 15000  # 15초

def log(status, place_id, adm_dong_code=None, extra=None):
    now = datetime.now().strftime("%H:%M:%S")
    msg = f"[{now}] [{status}] PlaceID: {place_id}"
    if adm_dong_code:
        msg += f" (Dong: {adm_dong_code})"
    if extra:
        msg += f" - {extra}"
    print(msg)

# ========== 🔵 유틸리티 함수 추가 ==========
async def safe_click(locator: Locator | None, timeout=DEFAULT_TIMEOUT):
    if locator:
        try:
            await locator.click(timeout=timeout)
            return True
        except Exception as e:
            print(f"[WARNING] Could not click element. Error: {e}")
    return False

async def safe_page_content(page: Page, timeout=10):
    try:
        return await asyncio.wait_for(page.content(), timeout=timeout)
    except asyncio.TimeoutError:
        print("❌ page.content() timeout")
        return None

# ==========================================

async def scroll_to_bottom(container: Locator, max_scrolls: int):
    if not await container.is_visible():
        print("[WARNING] Scroll container not visible.")
        return

    previous_height = -1
    for i in range(max_scrolls):
        current_height = await container.evaluate("el => el.scrollHeight")
        await container.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        await asyncio.sleep(0.5)

        if current_height == previous_height:
            print(f"  - Scrolling finished after {i+1} scrolls.")
            break
        previous_height = current_height
    else:
        print(f"  - Reached max scrolls ({max_scrolls}).")

async def scroll_page_to_bottom(page: Page, max_scrolls=6):
    for _ in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)

async def load_all_reviews(page: Page):
    for _ in range(MAX_REVIEW_CLICKS):
        review_items = await page.query_selector_all("li.place_apply_pui")
        if len(review_items) >= MAX_REVIEWS:
            break

        await page.mouse.wheel(0, 5000)
        await page.wait_for_timeout(1000)

        prev_count = len(review_items)
        more_btn = await page.query_selector("a.fvwqf")
        if more_btn:
            try:
                await more_btn.click()
                await page.wait_for_timeout(1000)

                for _ in range(2):
                    new_items = await page.query_selector_all("li.place_apply_pui")
                    if len(new_items) > prev_count:
                        break
                    await page.wait_for_timeout(1.0)
            except Exception as e:
                print(f"⚠️ 더보기 클릭 실패: {e}")
                break
        else:
            break

async def scrape_place_details_html(page: Page, place_id: str) -> dict | None:
    log("START", place_id)
    start_time = time.time()
    data = {"place_id": place_id, "home_html": None, "info_html": None, "reviews_html": None}

    try:
        home_url = f"https://m.place.naver.com/restaurant/{place_id}/home?entry=ple&reviewSort=recent"
        await page.goto(home_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state('domcontentloaded', timeout=DEFAULT_TIMEOUT)
        target_toggle = await page.query_selector(
            '//div[contains(@class, "A_cdD") and contains(., "영업")]//following::span[contains(@class, "_UCia")][1]'
        )
        if target_toggle:
            try:
                await target_toggle.scroll_into_view_if_needed()
                await page.wait_for_timeout(300)
                await target_toggle.click(timeout=1000)
            except Exception as e:
                print(f"⚠️ 영업중 토글 클릭 실패: {e}")
                try:
                    await target_toggle.click(force=True)
                except Exception as e2:
                    print(f"⚠️ 강제 클릭도 실패: {e2}")

        data["home_html"] = await safe_page_content(page, timeout=10)

        info_url = f"https://m.place.naver.com/restaurant/{place_id}/information?entry=ple&reviewSort=recent"
        await page.goto(info_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state('domcontentloaded', timeout=DEFAULT_TIMEOUT)
        await scroll_page_to_bottom(page, MAX_SEARCH_SCROLLS)
        data["info_html"] = await safe_page_content(page, timeout=10)

        review_url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
        await page.goto(review_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state('domcontentloaded', timeout=DEFAULT_TIMEOUT)
        await load_all_reviews(page)
        data["reviews_html"] = await safe_page_content(page, timeout=15)

        elapsed = time.time() - start_time
        log("SAVED", place_id, extra=f"{elapsed:.1f} sec")
        return data

    except Exception as e:
        log("ERROR", place_id, extra=str(e))
        return None

# ========== 🔵 retry 추가 ==========
async def scrape_with_retry(page: Page, place_id: str, retries=3):
    for attempt in range(retries):
        result = await scrape_place_details_html(page, place_id)
        if result:
            return result
        print(f"🔁 Retry {attempt+1}/{retries} for PlaceID: {place_id}")
        await asyncio.sleep(3)  # 재시도 간 짧은 대기
    print(f"❌ Failed after {retries} retries for PlaceID: {place_id}")
    return None
# ===================================

async def crawl_place_ids_worker(page, queue, results):
    while True:
        place_id = await queue.get()
        if place_id is None:
            break  # 종료 신호

        html = await scrape_with_retry(page, place_id)
        if html:
            results.append(html)

        queue.task_done()

async def crawl_from_place_ids(place_ids: list[str]):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--window-size=400,300"])
        context = await browser.new_context(
            viewport={"width": 400, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        queue = asyncio.Queue()

        for place_id in place_ids:
            queue.put_nowait(place_id)

        for _ in range(CONCURRENT_PAGES):
            queue.put_nowait(None)

        tasks = []
        for _ in range(CONCURRENT_PAGES):
            page = await context.new_page()
            task = asyncio.create_task(crawl_place_ids_worker(page, queue, results))
            tasks.append(task)

        await queue.join()

        for task in tasks:
            await task

        await browser.close()

    return results
