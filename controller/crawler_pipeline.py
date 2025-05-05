import csv
from service.place_searcher import search_and_fetch_place_ids
import asyncio
import os
import time
from playwright.async_api import async_playwright
from storage.save_data import save_place_info_json, save_reviews_json, save_place_raw_html, save_failed_places_json
from service.utils import block_unnecessary_resources, log
from service.place_data_collector import fetch_home_page_and_get_place_info, fetch_review_page_and_get_reviews, fetch_info_page

RAW_DIR="raw_data"
TARGET_TXT_PATH="data/target_adm_dong_codes.txt" # 크롤링할 행정동코드
ADM_DONG_CSV_PATH="data/adm_dong_list.csv" # 행정동 csv 파일
MAX_PLACES=60

# 메인 실행 함수
async def run() -> None:
    # 파일을 입력으로 대상 행정동코드를 읽어옴
    with open(TARGET_TXT_PATH, 'r', encoding='utf-8-sig') as f:
        target_codes = set(line.strip() for line in f if line.strip())

    # 행정동코드로 구+동 정보 획득
    adm_dong_dict = {}
    with open(ADM_DONG_CSV_PATH, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            adm_dong_code = row["adm_dong_code"]
            if adm_dong_code in target_codes:
                # "구 동" 형태로 value 구성
                adm_dong_dict[adm_dong_code] = f"{row["district"]} {row["neighborhood"]}"

    for adm_dong_code in target_codes:
        global_start = time.time()
        # 크롤링 실행 (춫후 중복 확인 로직 추가)
        try:
            place_ids = await search_and_fetch_place_ids(adm_dong_dict[adm_dong_code], MAX_PLACES) # 최대 수집 장소 수
            print(f"🚀 {adm_dong_code}: {len(place_ids)}개 수집 시작")
            await crawl_from_place_ids(list(place_ids), adm_dong_code)

        except Exception as e:
            print(f"❌ [ERROR] 크롤링 중 오류 발생 - {e}")

        global_elapsed = time.time() - global_start
        print(f"✅ 전체 소요시간: {global_elapsed:.1f} sec\n")


async def crawl_from_place_ids(place_ids: list[str], adm_dong_code):
    results = []
    async with async_playwright() as p:
        place_ids = list(place_ids)

        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 400, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        # 4개씩 처리
        for i in range(0, len(place_ids), 4):
            batch = place_ids[i:i + 4]

            tasks = []
            for place_id in batch:
                output_path = f"{RAW_DIR}/adc_{adm_dong_code}_place_rawdata_{place_id}.html"
                if os.path.exists(output_path):
                    print(f"⏭️ 이미 파일 있음 → 스킵 (PlaceID: {place_id})")
                    continue
                tasks.append(scrape_place_details(context, place_id, adm_dong_code))

            # 동시에 실행
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 저장
            for result in batch_results:
                if isinstance(result, dict):
                    results.append(result)
        await context.close()
        await browser.close()

    return results

# 식당 1개 크롤링
async def scrape_place_details(context, place_id: str, adm_dong_code: int):
    log("START", place_id)
    start_time = time.time()
    html_data = {"place_id": place_id, "home_html": None, "info_html": None, "reviews_html": None}

    # 탭 열기
    home_page = await context.new_page()
    info_page = await context.new_page()
    review_page = await context.new_page()

    # 리소스 차단
    await block_unnecessary_resources(home_page)
    await block_unnecessary_resources(info_page)
    await block_unnecessary_resources(review_page)

    try:
        # 세 가지 작업을 병렬로 실행. 하나라도 예외 발생 시 전체가 예외를 던집니다.
        place_info, reviews, info_html = await asyncio.gather(
            fetch_home_page_and_get_place_info(home_page, place_id, adm_dong_code),
            fetch_review_page_and_get_reviews(review_page, place_id),
            fetch_info_page(info_page, place_id),
        )
    except Exception as e:
        # 여기로 오면 place_info, reviews, info_html 중 하나라도 실패한 것
        print(f"❌ {place_id} - 수집 불충분 → 저장 생략")
        # 필요하다면 리소스 정리 후
        await home_page.close()
        await info_page.close()
        await review_page.close()
        return  # 함수 전체 종료

    try:
        html_data["home_html"] = await home_page.content()
        html_data["info_html"] = info_html
        html_data["reviews_html"] = await review_page.content()

        save_place_info_json(place_info, adm_dong_code)
        save_reviews_json(reviews, adm_dong_code)
        save_place_raw_html(place_id, adm_dong_code, html_data)

        elapsed = time.time() - start_time
        log("SAVED", place_id, extra=f"{elapsed:.1f} sec")
    except Exception as e:
        save_failed_places_json(place_id, adm_dong_code)
        log("ERROR", place_id, extra=str(e))
    finally: # 페이지 닫기
        await home_page.close()
        await info_page.close()
        await review_page.close()