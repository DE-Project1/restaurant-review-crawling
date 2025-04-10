import pandas as pd
import os

# 확인할 district 리스트
target_districts = ["송파구", "서초구", "성동구", "구로구", "중구"]

# 파일 경로 포맷
formats = {
    "place_info": "data/place_info/place_info_{}.csv",
    "reviews": "data/reviews/reviews_{}.csv",
}

# adm_dong_list.csv 불러오기
df = pd.read_csv("data/adm_dong_list.csv", dtype=str)

# 대상 district에 해당하는 행 필터링
filtered_df = df[df["district"].isin(target_districts)]

count = 0

# 누락된 파일을 기록할 리스트
for _, row in filtered_df.iterrows():
    adm_dong_code = row["adm_dong_code"]
    missing = []
    for label, path_fmt in formats.items():
        file_path = path_fmt.format(adm_dong_code)
        if not os.path.isfile(file_path):
            missing.append(label)
    count += 1
    if missing:
        print(f"[누락] adm_dong_code: {adm_dong_code}, city: {row['city']}, "
              f"district: {row['district']}, neighborhood: {row['neighborhood']}")
        print(f"→ 누락된 파일 형식: {', '.join(missing)}\n")
if count is not 0:
    print("누락된 동이 없습니다.")