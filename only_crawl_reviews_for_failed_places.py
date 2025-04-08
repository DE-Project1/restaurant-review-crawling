import csv
import asyncio
import os
from playwright.async_api import async_playwright
from service.place_data_collector import crawl_reviews, crawl_place_info
from storage.save_data import save_place_info_csv, save_reviews_csv, save_failed_case

INPUT_DIR = "data/failed_places"
OUTPUT_DIR = "data/failed_places"

async def only_review_crawling_batch():
    files = ["failed_places_1171055000.csv"]  # 또는 os.listdir(INPUT_DIR)

    if not files:
        print("❌ 처리할 실패 파일이 없습니다.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--window-size=400,800"])
        context = await browser.new_context(
            viewport={"width": 400, "height": 800},
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
                    print(f"🔍 리뷰 + 정보 수집 시작: {pname} ({pid})")

                    info = await asyncio.wait_for(
                        crawl_place_info(page, pid, adm_dong_code),
                        timeout=120
                    )
                    if info is None:
                        print(f"⚠️ 조건 무효: {pname} ({pid})")
                        continue

                    review_task = crawl_reviews(page, pid, pname)
                    reviews = await asyncio.wait_for(review_task, timeout=120)

                    if reviews:
                        save_place_info_csv(info, adm_dong_code)
                        print(f"✅ 장소 정보 저장 완료: {pname} ({pid})")

                        save_reviews_csv(reviews, adm_dong_code)
                        print(f"✅ 리뷰 저장 완료: {pname} | 리뷰 수: {len(reviews)}")
                        succeeded_pids.add(pid)
                    else:
                        print(f"⚠️ 리뷰 없음: {pname}")

                except asyncio.TimeoutError:
                    print(f"[ERROR] Timeout - {pname} ({pid})")
                    save_failed_case(pname, pid, adm_dong_code)
                except Exception as e:
                    print(f"[ERROR] 예외 발생 - {pname} ({pid}): {e}")
                    save_failed_case(pname, pid, adm_dong_code)
                finally:
                    await page.close()

            failed_rows = [row for _, _, pid, row in targets if pid not in succeeded_pids]
            if failed_rows:
                fieldnames = failed_rows[0].keys()
                failed_path = os.path.join(OUTPUT_DIR, f"failed_places_{failed_rows[0]['adm_dong_code']}.csv")
                with open(failed_path, "w", newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(failed_rows)
                print(f"실패했던 {len(failed_rows)}개를 {failed_path}에 저장 완료")
            else:
                print("모든 장소 데이터 수집 성공")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(only_review_crawling_batch())