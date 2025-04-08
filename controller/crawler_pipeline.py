import asyncio
import csv
from playwright.async_api import async_playwright
from service.place_searcher import fetch_places
from service.place_data_collector import crawl_place_info, crawl_reviews
from storage.save_data import save_place_info_csv, save_reviews_csv, save_failed_case

TARGET_TXT_PATH = "data/target_adm_dong_codes.txt" # 크롤링할 동의 행정동코드 목록
ADM_DONG_CSV_PATH = "data/adm_dong_list.csv" # 행정동 csv 파일
MAX_PLACES = 30
MAX_TABS = 4

# 크롤링 파이프라인 실행
async def run():
    # 크롤링할 행정동코드 목록 로딩
    with open(TARGET_TXT_PATH, 'r', encoding='utf-8-sig') as f:
        target_codes = set(line.strip() for line in f if line.strip())

    # 파일에 입력되어있는 행정동코드의 행만을 추출
    adm_dong_data = [] #
    with open(ADM_DONG_CSV_PATH, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        print("📌 CSV 컬럼명:", reader.fieldnames)
        for row in reader:
            if row["adm_dong_code"] in target_codes:
                adm_dong_data.append(row)

    total = len(adm_dong_data) # 크롤링 대상 동 수
    sema = asyncio.Semaphore(MAX_TABS) # 동시에 띄울 최대 탭 수를 7로 설정

    # 비동기 크롤링 진행
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        for idx, row in enumerate(adm_dong_data, start=1):
            city = row["city"]
            district = row["district"]
            neighborhood = row["neighborhood"]
            keyword = f"{city} {district} {neighborhood}"
            print(f"\n[{idx}/{total}] {keyword} 크롤링 시작...")

            try:
                places = await fetch_places(keyword, MAX_PLACES * 2)  # 여유 있게 받아둠
                tasks = [
                    collect_place_if_valid(context, row["adm_dong_code"], place, sema)
                    for place in places
                ]
                results = await asyncio.gather(*tasks)
            except asyncio.TimeoutError:
                print(f"[ERROR] Timeout - {keyword}")
            except Exception as e:
                print(f"[ERROR] 예외 발생 - {keyword}: {e}")

        await browser.close()

# 세마포어 기반 탭 동시 처리
async def collect_place_if_valid(context, adm_dong_code, place, sema):
    async with sema:
        page = await context.new_page()
        pname = place['name']
        pid = place['id']
        try:
            print(f"📌 검증 시작: {pname} ({pid})")
            info = await asyncio.wait_for(
                crawl_place_info(page, pid, adm_dong_code),
                timeout=120
            )
            if info is None:
                print(f"⚠️ 조건 불충족: {pname} ({pid})")
                return False

            # 리뷰 크롤링 실행
            review_task = crawl_reviews(page, pid, pname)
            reviews = await asyncio.wait_for(review_task, timeout=120)

            if reviews:
                save_place_info_csv(info, adm_dong_code)
                print(f"✅ 장소 정보 저장 완료: {pname} ({pid})")
                save_reviews_csv(reviews, adm_dong_code)
                print(f"✅ 리뷰 저장 완료: {pname} | 리뷰 수: {len(reviews)}")
            else:
                print(f"⚠️ 리뷰 없음: {pname}")

            return True

        except asyncio.TimeoutError:
            print(f"[ERROR] Timeout - {pname} ({pid})")
            save_failed_case(pname, pid, adm_dong_code)
            return False
        except Exception as e:
            print(f"[ERROR] 예외 발생 - {pname} ({pid}): {e}")
            save_failed_case(pname, pid, adm_dong_code)
            return False
        finally:
            await page.close()