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

async def scrape_place_details_html(context, place_id: str, output_path: str):
    log("START", place_id)
    start_time = time.time()
    data = {"place_id": place_id, "home_html": None, "info_html": None, "reviews_html": None}

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


        try:
            with open(output_path, "w", encoding="utf-8-sig") as f:
                f.write("===== HOME =====\n")
                f.write(data["home_html"] or "")
                f.write("\n\n===== INFO =====\n")
                f.write(data["info_html"] or "")
                f.write("\n\n===== REVIEWS =====\n")
                f.write(data["reviews_html"] or "")
        except Exception as e:
            print(f"⚠️ 저장 실패 (PlaceID: {place_id}) - {e}")
        finally:
            # 페이지 닫기 (여기가 포인트)
            await home_page.close()
            await info_page.close()
            await review_page.close()

    except Exception as e:
        log("ERROR", place_id, extra=str(e))
    return data

# ---- Main Entry ----

from itertools import islice

async def crawl_from_place_ids(place_ids: list[str], RAW_DIR, adm_dong_code):
    results = []

    async with async_playwright() as p:
        place_ids = list(place_ids)

        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 400, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        # 4개씩 처리
        for i in range(0, len(place_ids), 4):
            batch = place_ids[i:i + 4]

            tasks = []
            for place_id in batch:
                output_path = f"{RAW_DIR}/adc_{adm_dong_code}_place_rawdata_{place_id}.html"
                if os.path.exists(output_path):
                    print(f"⏭️ 이미 파일 있음 → 스킵 (PlaceID: {place_id})")
                    continue
                tasks.append(scrape_place_details_html(context, place_id, output_path))

            # 동시에 실행
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 저장
            for result in batch_results:
                if isinstance(result, dict):
                    results.append(result)

        await context.close()
        await browser.close()

    return results
