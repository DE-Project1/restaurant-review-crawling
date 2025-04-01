# import asyncio
# from controller.run_pipeline import run

# if __name__ == "__main__":
#     asyncio.run(run())

import asyncio
from playwright.async_api import async_playwright
from service.place_data_collector import collect_place_data  # 너의 collect_place_data가 있는 위치
from storage.save_data import save_place_info_csv, save_reviews_csv  # 저장까지 테스트할 경우

place_dict = {
    "소녀방앗간_이화여대점": 38232807,
    "슬로우캘리_이대점": 1751348952,
    "까이식당": 37792177,
    "어바웃샤브_이대점": 12047074,
    "다이코쿠야": 1385509809,
}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for name, pid in place_dict.items():
            print(f"📌 크롤링 시작: {name} ({pid})")
            info, reviews = await collect_place_data(page, name, pid)

            print("✅ 장소 정보:")
            print(info)
            print(f"✅ 리뷰 수: {len(reviews)}")

            # 저장까지 테스트하고 싶을 경우
            save_place_info_csv(info)
            save_reviews_csv(reviews)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
