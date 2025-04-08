import csv
import asyncio
import os
from playwright.async_api import async_playwright
from service.place_data_collector import crawl_reviews
from storage.save_data import save_reviews_csv

INPUT_DIR = "data/failed_places"  # 수정된 디렉토리
OUTPUT_DIR = "data/failed_places"  # 동일 경로에 저장

async def only_review_crawling_batch():
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".csv")]
    if not files:
        print("❌ 처리할 실패 파일이 없습니다.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        for filename in files:
            input_path = os.path.join(INPUT_DIR, filename)
            print(f"\n📂 처리 중: {filename}")

            with open(input_path, newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                targets = [
                    (row['adm_dong_code'], row['pname'], row['pid'], row)
                    for row in rows if row.get('adm_dong_code') and row.get('pname') and row.get('pid')
                ]

            succeeded_pids = set()

            for adm_dong_code, pname, pid, row in targets:
                page = await context.new_page()
                try:
                    print(f"🔍 리뷰 수집 시작: {pname} ({pid})")
                    reviews = await asyncio.wait_for(
                        crawl_reviews(page, pid, pname),
                        timeout=120
                    )
                    if reviews:
                        save_reviews_csv(reviews, adm_dong_code)
                        succeeded_pids.add(pid)
                        print(f"✅ 리뷰 저장 완료: {pname} | 리뷰 수: {len(reviews)}")
                    else:
                        print(f"⚠️ 리뷰 없음: {pname}")
                except asyncio.TimeoutError:
                    print(f"[ERROR] Timeout - {pname} ({pid})")
                except Exception as e:
                    print(f"[ERROR] 예외 발생 - {pname} ({pid}): {e}")
                finally:
                    await page.close()

            # 실패한 row만 다시 저장
            failed_rows = [row for _, _, pid, row in targets if pid not in succeeded_pids]
            if failed_rows:
                fieldnames = failed_rows[0].keys()
                failed_path = os.path.join(OUTPUT_DIR, f"failed_places_{failed_rows[0]['adm_dong_code']}.csv")
                with open(failed_path, "w", newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(failed_rows)
                print(f"📌 실패 {len(failed_rows)}개를 {failed_path}에 저장 완료")
            else:
                print("🎉 모든 장소 리뷰 수집 성공!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(only_review_crawling_batch())
