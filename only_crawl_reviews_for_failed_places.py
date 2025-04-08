import csv
import asyncio
from playwright.async_api import async_playwright
from service.place_data_collector import crawl_reviews
from storage.save_data import save_reviews_csv

INPUT_PATH = "data/failed_places.csv"  # CSV 파일: pname, pid, adm_dong_code 컬럼

async def only_review_crawling_batch(input_path):
    # CSV 파일 로드
    with open(input_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        targets = [
            (row['adm_dong_code'], row['pname'], row['pid'])
            for row in reader if row.get('adm_dong_code') and row.get('pname') and row.get('pid')
        ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        for adm_dong_code, pname, pid in targets:
            page = await context.new_page()
            try:
                print(f"🔍 리뷰 수집 시작: {pname} ({pid})")
                reviews = await asyncio.wait_for(
                    crawl_reviews(page, pid, pname),
                    timeout=120
                )
                if reviews:
                    save_reviews_csv(reviews, adm_dong_code)
                    print(f"✅ 리뷰 저장 완료: {pname} | 리뷰 수: {len(reviews)}")
                else:
                    print(f"⚠️ 리뷰 없음: {pname}")
            except asyncio.TimeoutError:
                print(f"[ERROR] Timeout - {pname} ({pid})")
            except Exception as e:
                print(f"[ERROR] 예외 발생 - {pname} ({pid}): {e}")
            finally:
                await page.close()

        await browser.close()

if __name__ == "__main__":
    asyncio.run(only_review_crawling_batch(INPUT_PATH))
