import asyncio
import re
import random
import os
from playwright.async_api import async_playwright, Page, Locator

CONCURRENT_PAGES = 4  # 동시 탭 개수
MAX_SEARCH_SCROLLS = 20
MAX_REVIEW_CLICKS = 11
MAX_REVIEWS = 100
DEFAULT_TIMEOUT = 15000

async def safe_click(locator: Locator | None, timeout=DEFAULT_TIMEOUT):
    if locator:
        try:
            await locator.click(timeout=timeout)
            return True
        except Exception as e:
            print(f"  - Warning: Could not click element. Error: {e}")
    return False

async def scroll_to_bottom(container: Locator, max_scrolls: int):
    print("  - Scrolling...")
    if not await container.is_visible():
        print("  - Warning: Scroll container not visible.")
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
    for i in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)

async def load_all_reviews(page: Page):
    for _ in range(MAX_REVIEW_CLICKS):
        review_items = await page.query_selector_all("li.place_apply_pui")
        if len(review_items) >= MAX_REVIEWS:
            break

        await page.mouse.wheel(0, 5000)
        await page.wait_for_timeout(random.randint(1200, 1500))

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
    print(f"  - Scraping HTML for place ID: {place_id}")
    data = {"place_id": place_id, "home_html": None, "info_html": None, "reviews_html": None}

    try:
        home_url = f"https://m.place.naver.com/restaurant/{place_id}/home?entry=ple&reviewSort=recent"
        await page.goto(home_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state('domcontentloaded')

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

        data["home_html"] = await page.content()

        info_url = f"https://m.place.naver.com/restaurant/{place_id}/information?entry=ple&reviewSort=recent"
        await page.goto(info_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state('domcontentloaded')
        await scroll_page_to_bottom(page, MAX_SEARCH_SCROLLS)
        data["info_html"] = await page.content()

        review_url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
        await page.goto(review_url, timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state('domcontentloaded')
        await load_all_reviews(page)
        data["reviews_html"] = await page.content()

        os.makedirs("raw_data", exist_ok=True)
        with open(f"raw_data/raw_data_{place_id}.txt", "w", encoding="utf-8") as f:
            f.write("===== HOME =====\n")
            f.write(data["home_html"] or "")
            f.write("\n\n===== INFO =====\n")
            f.write(data["info_html"] or "")
            f.write("\n\n===== REVIEWS =====\n")
            f.write(data["reviews_html"] or "")

        print(f"  - Saved raw HTML to raw_data/raw_data_{place_id}.txt")
        return data

    except Exception as e:
        print(f"  - Error: {e}")
        return None

async def crawl_place_ids_worker(page, queue, results):
    while True:
        place_id = await queue.get()
        if place_id is None:
            break  # 종료 신호

        html = await scrape_place_details_html(page, place_id)
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

        # place_id 넣기
        for place_id in place_ids:
            queue.put_nowait(place_id)

        # 종료 신호용 None 추가 (탭 수만큼)
        for _ in range(CONCURRENT_PAGES):
            queue.put_nowait(None)

        # 병렬로 페이지 열기 (탭 열기)
        tasks = []
        for _ in range(CONCURRENT_PAGES):
            page = await context.new_page()
            task = asyncio.create_task(crawl_place_ids_worker(page, queue, results))
            tasks.append(task)

        await queue.join()

        # 종료
        for task in tasks:
            await task

        await browser.close()

    return results


async def search_and_scrape_raw_html(query: str, max_places: int):
    results = []
    scraped_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--window-size=400,300"])
        context = await browser.new_context(
            viewport={"width": 400, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(f"https://map.naver.com/p/search/{query}", timeout=DEFAULT_TIMEOUT)
            await asyncio.sleep(2)

            search_frame = page.frame(name="searchIframe")
            if not search_frame:
                print("Error: searchIframe not found.")
                return []

            scroll_container = search_frame.locator("div#_pcmap_list_scroll_container")
            await scroll_to_bottom(scroll_container, MAX_SEARCH_SCROLLS)

            list_items = await search_frame.locator("li.UEzoS").all()
            print(f"Found {len(list_items)} places.")

            for i, item in enumerate(list_items):
                if len(results) >= max_places:
                    break

                click_target = item.locator("a.tzwk0").first
                if not await safe_click(click_target):
                    continue
                await asyncio.sleep(1.5)
                match = re.search(r'/place/(\d+)',  page.url)
                place_id = match.group(1) if match else None

                if not place_id:
                    iframe = page.locator("iframe#entryIframe")
                    src = await iframe.get_attribute('src')
                    match = re.search(r'placeId=(\d+)', src or '')
                    place_id = match.group(1) if match else None

                if not place_id or place_id in scraped_ids:
                    continue

                html = await scrape_place_details_html(page, place_id)
                if html:
                    results.append(html)
                    scraped_ids.add(place_id)

        finally:
            await browser.close()

    return results
