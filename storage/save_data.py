import csv
import os

PLACE_INFO_DIR = "data/place_info"
PLACE_REVIEW_DIR = "data/reviews"
PLACE_INFO_FIELDS = [
    "place_id", "adm_dong_code", "name", "category",
    "address", "opening_hours", "services", "naver_rating",
    "visitor_review_count", "blog_review_count", "badges", "crawled_at"
]
REVIEW_FIELDS = [
    "place_id", "nickname", "content", "date",
    "situations", "keywords", "review_count", "visit_count"
]

os.makedirs(PLACE_INFO_DIR, exist_ok=True)
os.makedirs(PLACE_REVIEW_DIR, exist_ok=True)

def save_place_info_csv(info: dict, adm_dong_code):
    path = os.path.join(PLACE_INFO_DIR, f"place_info_{adm_dong_code}.csv")
    file_empty = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PLACE_INFO_FIELDS)
        if file_empty:
            writer.writeheader()
        writer.writerow(info)

def save_reviews_csv(reviews: list[dict], adm_dong_code):
    if not reviews:
        return
    path = os.path.join(PLACE_REVIEW_DIR, f"reviews_{adm_dong_code}.csv")
    file_empty = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        if file_empty:
            writer.writeheader()
        writer.writerows([{k: v for k, v in r.items() if k in REVIEW_FIELDS} for r in reviews])
