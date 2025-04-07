import asyncio
from playwright.async_api import async_playwright
from service.place_searcher import fetch_places
from service.place_data_collector import collect_place_data
from storage.save_data import save_place_info_csv, save_reviews_csv

DISTRICT_BATCH_SIZE = 2  # 몇 개 동을 동시에 검색할지
TABS_PER_DISTRICT_BATCH = 5 # 동마다 식당 동시 크롤링 위해 최대 몇 개 탭을 띄울지

# 동 목록 예시
DISTRICT_LIST = [
    "서대문구 창천동", "마포구 합정동", "서대문구 대현동",
    "마포구 서교동", "서대문구 신촌동", "마포구 망원동"
]

async def run():
    # 동 리스트를 batch로 나누기
    district_batches = [DISTRICT_LIST[i:i + DISTRICT_BATCH_SIZE] for i in range(0, len(DISTRICT_LIST), DISTRICT_BATCH_SIZE)]

    # 동시에 5개의 탭만 허용하고, 나머지는 대기
    sema = asyncio.Semaphore(TABS_PER_DISTRICT_BATCH)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        for batch in district_batches:
            print(f"\nBatch: {batch}")
            places = await process_district_batch(batch)

            tasks = [
                collect_with_semaphore(context, place, sema) for place in places
            ]
            await asyncio.gather(*tasks)

        await browser.close()

# 장소 수집 배치
async def process_district_batch(batch):
    places = []
    for district in batch:
        fetched = await fetch_places(district)
        places.extend(fetched)
    return places

# 탭 수를 세마포어로 하며 음식점 수집
async def collect_with_semaphore(context, place, sema):
    async with sema:
        page = await context.new_page()
        pname = place['name']
        pid = place['id']
        try:

            print(f"📌 크롤링 시작: {pname} ({pid})")
            info, reviews = await asyncio.wait_for(
                collect_place_data(page, pname, pid),
                timeout=120  # 120초를 타임아웃으로 설정
            )
            save_place_info_csv(info)
            save_reviews_csv(reviews)
            print(f"✅ 저장 완료: {pname} | 리뷰 수: {len(reviews)}")
        except asyncio.TimeoutError:
            print(f"[ERROR] Timeout - {pname} ({pid})")
            
        except Exception as e:
            print(f"[ERROR] 예외 발생 - {pname} ({pid}): {e}")

        finally:
            await page.close()