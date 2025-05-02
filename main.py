import os
import csv
import time
import glob
import asyncio
from crawl_place_info_html import crawl_from_place_ids

RAW_DIR = "raw_data"
PLACE_CSV_DIR = "data/place_info"
ADM_DONG_CODES = ["1111", "1114", "1120"]

from itertools import chain

async def crawl_missing_place_ids():
    os.makedirs(RAW_DIR, exist_ok=True)

    csv_files = list(chain.from_iterable(
        glob.glob(f"{PLACE_CSV_DIR}/place_info_{dong_code}*.csv") for dong_code in ADM_DONG_CODES
    ))

    for csv_path in csv_files:
        global_start = time.time()
        adm_dong_code = os.path.splitext(os.path.basename(csv_path))[0].split("_")[-1]

        place_ids_to_crawl = set()

        # 수집해야 할 place_id 찾기
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                place_id = row.get("place_id")
                if not place_id:
                    continue
                output_path = f"{RAW_DIR}/adc_{adm_dong_code}_place_rawdata_{place_id}.txt"
                if os.path.exists(output_path):
                    continue  # 이미 있으면 skip
                place_ids_to_crawl.add(place_id)

        if not place_ids_to_crawl:
            print(f"✅ {adm_dong_code}: 모두 수집됨 (skip)")
            continue

        # 크롤링 실행
        try:
            print(f"🚀 {adm_dong_code}: {len(place_ids_to_crawl)}개 수집 시작")
            await crawl_from_place_ids(list(place_ids_to_crawl), RAW_DIR, adm_dong_code)
        except Exception as e:
            print(f"❌ [ERROR] 크롤링 중 오류 발생 - {e}")


        global_elapsed = time.time() - global_start
        print(f"✅ 전체 소요시간: {global_elapsed:.1f} sec\n")

if __name__ == "__main__":
    asyncio.run(crawl_missing_place_ids())
