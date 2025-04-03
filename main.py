# import asyncio
# from controller.crawler_pipeline import run
#
# if __name__ == "__main__":
#     asyncio.run(run())

# place_data_collector.py 테스트용 main

import asyncio
from playwright.async_api import async_playwright
from service.place_data_collector import collect_place_data
from storage.save_data import save_place_info_csv, save_reviews_csv

place_dict = {
    # "소녀방앗간_이화여대점": 38232807,
    # "슬로우캘리_이대점": 1751348952,
    # "까이식당": 37792177,
    # "어바웃샤브_이대점": 12047074,
    # "다이코쿠야": 1385509809,
    # "아민 이화": 37792625,
    # "제주도로담": 36797304,
    # "비밀베이커리 이대점": 36271566,
    # "이대 불밥": 11594306,
    # "비아37 신촌본점": 11853181,
    "등촌샤브칼국수 신촌점": 1969187632,
    "연어초밥": 1221500434,
    "아건 이대본점": 13155014,
    "아콘스톨": 1946223191,
    "가야가야": 13507856,
    "오마카세 오사이초밥 신촌점": 1442263918,
    "보어드앤헝그리 마포": 1563548722,
    "미스터서왕만두": 36670196
}

CONCURRENT_TABS = 5  # 탭 최대 개수 제한

async def collect_with_semaphore(context, name, pid, sema):
    async with sema:
        page = await context.new_page()
        print(f"📌 크롤링 시작: {name} ({pid})")
        info, reviews = await collect_place_data(page, name, pid)
        await page.close()

        print("✅ 장소 정보:")
        print(info)
        print(f"✅ 리뷰 수: {len(reviews)}")

        save_place_info_csv(info)
        save_reviews_csv(reviews)

async def main():
    sema = asyncio.Semaphore(CONCURRENT_TABS)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        tasks = [
            collect_with_semaphore(context, name, pid, sema)
            for name, pid in place_dict.items()
        ]

        await asyncio.gather(*tasks)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
