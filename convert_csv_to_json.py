import os
import glob
import csv
import json

# 설정
INPUT_DIR = '/Users/leeseohyun/Downloads/de-s3'
OUTPUT_DIR = './json-data'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 모든 CSV 파일 처리
for csv_path in glob.glob(os.path.join(INPUT_DIR, '*/*.csv')):
    base_name = os.path.splitext(os.path.basename(csv_path))[0]
    json_path = os.path.join(OUTPUT_DIR, f'{base_name}.json')

    with open(csv_path, 'r', encoding='utf-8') as f_csv, \
         open(json_path, 'w', encoding='utf-8') as f_json:

        reader = csv.DictReader(f_csv)
        records = []
        for row in reader:
            # 빈값/Null인 필드는 제외
            filtered = {
                key: value
                for key, value in row.items()
                if value not in (None, '', 'null', 'None')
            }
            records.append(filtered)

        # JSON 파일로 저장
        json.dump(records, f_json, ensure_ascii=False, indent=2)

    print(f'Converted: {csv_path} -> {json_path}')
