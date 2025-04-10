import asyncio
from playwright.async_api import async_playwright
from service.place_searcher import fetch_places
from service.place_data_collector import collect_place_data
from storage.save_to_s3 import save_place_info_to_s3, save_reviews_to_s3

DISTRICT_LIST = [
    "서대문구 창천동", "마포구 합정동", "서대문구 대현동",
    "마포구 서교동", "서대문구 신촌동", "마포구 망원동",
    "용산구 이태원동", "성동구 성수동", "종로구 청운동", "중구 신당동"
]

BATCH_SIZE = 10
TABS_PER_DISTRICT_BATCH = 5

async def run():
    person_id = 2  # 여기를 사용자가 직접 변경
    batch_groups = [DISTRICT_LIST[i:i+BATCH_SIZE] for i in range(0, len(DISTRICT_LIST), BATCH_SIZE)]
    sema = asyncio.Semaphore(TABS_PER_DISTRICT_BATCH)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        for batch_index, batch in enumerate(batch_groups, start=1):
            print(f"🔄 Processing batch {batch_index}: {batch}")
            places = await process_district_batch(batch)
            place_info_batch = []
            reviews_batch = []

            for place in places:
                async with sema:
                    page = await context.new_page()
                    pname = place['name']
                    pid = place['id']

                    try:
                        print(f"📌 크롤링 시작: {pname} ({pid})")
                        info, reviews = await asyncio.wait_for(
                            collect_place_data(page, pname, pid),
                            timeout=120
                        )
                        place_info_batch.append(info)
                        reviews_batch.extend(reviews)
                        print(f"✅ 완료: {pname} | 리뷰 수: {len(reviews)}")
                    except Exception as e:
                        print(f"[ERROR] {pname} ({pid}) - {e}")
                    finally:
                        await page.close()

            save_place_info_to_s3(person_id, batch_index, place_info_batch)
            save_reviews_to_s3(person_id, batch_index, reviews_batch)

        await browser.close()
