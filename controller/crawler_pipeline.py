import asyncio
import csv
from playwright.async_api import async_playwright
from service.place_searcher import fetch_places
from service.place_data_collector import collect_place_info_and_reviews
from storage.save_data import save_place_info_csv, save_reviews_csv

TARGET_TXT_PATH = "data/target_adm_dong_codes.txt" # 크롤링할 동의 행정동코드 목록
ADM_DONG_CSV_PATH = "data/adm_dong_list.csv" # 행정동 csv 파일
MAX_PLACES = 25

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
    sema = asyncio.Semaphore(7) # 동시에 띄울 최대 탭 수를 7로 설정

    # 비동기 크롤링 진행
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
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
                places = await fetch_places(keyword, MAX_PLACES)
                success = 0

                for place in places:
                    if success >= MAX_PLACES:
                        break
                    result = await collect_place_if_valid(context, row["adm_dong_code"], place, sema)
                    if result:
                        success += 1
                print(f"✅ {keyword} 크롤링 완료 - {success}/25 수집됨")
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
            info, reviews = await asyncio.wait_for(
                collect_place_info_and_reviews(page, pname, pid, adm_dong_code),
                timeout=120
            )
            if info is None or reviews is None:
                print(f"⚠️ 조건 불충족: {pname}")
                return False

            save_place_info_csv(info)
            save_reviews_csv(reviews)
            print(f"✅ 저장 완료: {pname} | 리뷰 수: {len(reviews)}")
            return True

        except asyncio.TimeoutError:
            print(f"[ERROR] Timeout - {pname} ({pid})")
            return False
        except Exception as e:
            print(f"[ERROR] 예외 발생 - {pname} ({pid}): {e}")
            return False
        finally:
            await page.close()