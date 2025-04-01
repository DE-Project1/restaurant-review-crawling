import asyncio
from playwright.async_api import async_playwright
from service.place_searcher import fetch_places
from service.place_data_collector import collect_place_data
from io.save_data import save_place_info_csv, save_reviews_csv

async def run():
    places = fetch_places()
    """
    place_dict = {
        "소녀방앗간_이화여대점": 38232807,
        "슬로우캘리_이대점": 1751348952,
        "까이식당": 37792177,
        "어바웃샤브_이대점": 12047074,
        "다이코쿠야": 1385509809,
    }
    """

    async with asyncio.TaskGroup() as tg:  # 동시성 위한 TaskGroup
        for place in places:
            if not place["is_matjip"]:
                continue

            tg.create_task(process_place(place))


async def process_place(place):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            info, reviews = await collect_place_data(page, place["name"], place["id"])
            await save_place_info_csv(info)
            await save_reviews_csv(reviews)
        except Exception as e:
            print(f"[ERROR] Failed to collect/save for {place['name']}: {e}")

        await browser.close()