import asyncio
import re
import os
import time
from playwright.async_api import async_playwright, Page, Locator
from datetime import datetime
import subprocess
import sys

CONCURRENT_WORKERS = 4  # 동시에 처리할 식당 개수
DEFAULT_TIMEOUT = 15000
MAX_SEARCH_SCROLLS = 20
MAX_REVIEW_CLICKS = 3
MAX_REVIEWS = 20

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

async def safe_click(locator: Locator | None, timeout=DEFAULT_TIMEOUT):
    if locator:
        try:
            await locator.click(timeout=timeout)
            return True
        except Exception as e:
            print(f"[WARNING] Click failed: {e}")
    return False

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
        await page.wait_for_timeout(500)

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

# ---- 페이지별 fetch ----

async def fetch_home_page(page: Page, place_id: str):
    url = f"https://m.place.naver.com/restaurant/{place_id}/home?entry=ple&reviewSort=recent"
    await page.goto(url, timeout=DEFAULT_TIMEOUT)
    await page.wait_for_load_state('domcontentloaded', timeout=DEFAULT_TIMEOUT)

    toggle = await page.query_selector(
        '//div[contains(@class, "A_cdD") and contains(., "영업")]//following::span[contains(@class, "_UCia")][1]'
    )
    if toggle:
        try:
            await toggle.scroll_into_view_if_needed()
            await page.wait_for_timeout(300)
            await toggle.click(timeout=1000)
        except Exception:
            pass

    return await safe_page_content(page, timeout=10)

async def fetch_info_page(page: Page, place_id: str):
    url = f"https://m.place.naver.com/restaurant/{place_id}/information?entry=ple&reviewSort=recent"
    await page.goto(url, timeout=DEFAULT_TIMEOUT)
    await page.wait_for_load_state('domcontentloaded', timeout=DEFAULT_TIMEOUT)
    await scroll_page_to_bottom(page, MAX_SEARCH_SCROLLS)
    return await safe_page_content(page, timeout=10)

async def fetch_review_page(page: Page, place_id: str):
    url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
    await page.goto(url, timeout=DEFAULT_TIMEOUT)
    await page.wait_for_load_state('domcontentloaded', timeout=DEFAULT_TIMEOUT)
    await load_all_reviews(page)
    return await safe_page_content(page, timeout=15)

# ---- 식당 1개 크롤링 ----

async def scrape_place_details_html(browser, place_id: str):
    log("START", place_id)
    start_time = time.time()
    data = {"place_id": place_id, "home_html": None, "info_html": None, "reviews_html": None}

    context = await browser.new_context(
        viewport={"width": 400, "height": 800},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    )

    try:
        # 탭 열기
        home_page = await context.new_page()
        info_page = await context.new_page()
        review_page = await context.new_page()

        # 리소스 차단
        await block_unnecessary_resources(home_page)
        await block_unnecessary_resources(info_page)
        await block_unnecessary_resources(review_page)

        # 병렬 실행
        home_html, info_html, reviews_html = await asyncio.gather(
            fetch_home_page(home_page, place_id),
            fetch_info_page(info_page, place_id),
            fetch_review_page(review_page, place_id)
        )

        data["home_html"] = home_html
        data["info_html"] = info_html
        data["reviews_html"] = reviews_html

        elapsed = time.time() - start_time
        log("SAVED", place_id, extra=f"{elapsed:.1f} sec")

    except Exception as e:
        log("ERROR", place_id, extra=str(e))

    await context.close()
    return data

# ---- Worker ----

async def crawl_place_ids_worker(browser, queue, results):
    while True:
        place_id = await queue.get()
        if place_id is None:
            break

        html = await scrape_place_details_html(browser, place_id)
        if html:
            results.append(html)

        queue.task_done()

# ---- Main Entry ----

async def crawl_from_place_ids(place_ids: list[str]):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        queue = asyncio.Queue()

        for place_id in place_ids:
            queue.put_nowait(place_id)

        for _ in range(CONCURRENT_WORKERS):
            queue.put_nowait(None)

        tasks = []
        for _ in range(CONCURRENT_WORKERS):
            task = asyncio.create_task(crawl_place_ids_worker(browser, queue, results))
            tasks.append(task)

        try:
            await queue.join()

            if len(browser.contexts) == 0:
                print("❌ 브라우저 창이 열려있지 않습니다. 프로그램을 재시작합니다.")
                # 프로그램 재실행
                subprocess.Popen([sys.executable] + sys.argv)
                return []

            for task in tasks:
                await task

        except Exception as e:
            print("❌ 크롤링 중 오류 발생 → 재시작합니다.")
            subprocess.Popen([sys.executable] + sys.argv)
            return []

        await browser.close()

    return results