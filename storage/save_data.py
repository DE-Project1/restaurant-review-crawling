import csv
import os

PLACE_INFO_PATH = "data/place_info.csv"
PLACE_REVIEW_PATH = "data/reviews.csv"
PLACE_INFO_FIELDS = [
    "place_id", "adm_dong_code", "name", "category",
    "address", "opening_hours", "services", "naver_rating",
    "visitor_review_count", "blog_review_count", "badges", "crawled_at"
]
REVIEW_FIELDS = [
    "place_id", "nickname", "content", "date",
    "situations", "keywords", "review_count", "visit_count"
]

def save_place_info_csv(info: dict):
    file_exists = os.path.exists(PLACE_INFO_PATH)
    with open(PLACE_INFO_PATH, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PLACE_INFO_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(info)

def save_reviews_csv(reviews: list[dict]):
    if not reviews:
        return
    file_exists = os.path.exists(PLACE_REVIEW_PATH)
    with open(PLACE_REVIEW_PATH, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(reviews)