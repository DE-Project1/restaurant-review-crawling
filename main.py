import os
import csv
import time
import glob
import asyncio
from crawl_place_info_html import crawl_from_place_ids

RAW_DIR = "raw_data"
PLACE_CSV_DIR = "data/place_info"

async def crawl_missing_place_ids():
    os.makedirs(RAW_DIR, exist_ok=True)

    csv_files = glob.glob(f"{PLACE_CSV_DIR}/place_info_*.csv")

    for csv_path in csv_files:
        global_start = time.time()
        adm_dong_code = os.path.splitext(os.path.basename(csv_path))[0].split("_")[-1]  # e.g. '11110'

        place_ids_to_crawl = set()

        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                place_id = row.get("place_id")
                if not place_id:
                    continue
                output_path = f"{RAW_DIR}/adc_{adm_dong_code}_place_rawdata_{place_id}.txt"
                if os.path.exists(output_path):
                    continue  # 이미 존재하는 파일이면 skip
                place_ids_to_crawl.add(place_id)

        if not place_ids_to_crawl:
            print(f"✅ {adm_dong_code}: 모두 수집됨 (skip)")
            continue

        print(f"🚀 {adm_dong_code}: {len(place_ids_to_crawl)}개 수집 시작")
        results = await crawl_from_place_ids(place_ids_to_crawl)

        for data in results:
            output_path = f"{RAW_DIR}/adc_{adm_dong_code}_place_rawdata_{data['place_id']}.txt"
            if os.path.exists(output_path):
                continue  # 이미 생긴 파일이 있으면 중복 방지
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("===== HOME =====\n")
                f.write(data["home_html"] or "")
                f.write("\n\n===== INFO =====\n")
                f.write(data["info_html"] or "")
                f.write("\n\n===== REVIEWS =====\n")
                f.write(data["reviews_html"] or "")
        global_elapsed = time.time() - global_start
        print(f"✅ {adm_dong_code}: 저장 완료 ({len(results)}개) - 전체 소요시간: {global_elapsed:.1f} sec")

if __name__ == "__main__":
    asyncio.run(crawl_missing_place_ids())

# async def main():
#     # # ① 검색어 기반
#     # search_results = await search_and_scrape_raw_html("강남역 맛집", max_places=5)
#     # print(f"Search-based: Found {len(search_results)} places.")
#
#     # ② 직접 지정한 place_id 기반 (예: CSV 대체)
#     place_ids = ["37637684", "1185221694"]  # ← 여기에 직접 지정하거나 CSV에서 읽도록 변경 가능
#     id_results = await crawl_from_place_ids(place_ids)
#     print(f"ID-based: Found {len(id_results)} places.")