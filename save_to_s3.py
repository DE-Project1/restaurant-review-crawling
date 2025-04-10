import boto3
import os
import io
import csv
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION")
)
BUCKET_NAME = os.getenv("BUCKET_NAME")

PLACE_INFO_FIELDS = [
    "place_id", "name", "category", "address",
    "opening_hours", "services", "naver_rating",
    "visitor_review_count", "blog_review_count",
    "badges", "crawled_at"
]

REVIEW_FIELDS = [
    "place_id", "nickname", "content", "date",
    "situations", "keywords", "review_count", "visit_count"
]

def upload_csv_to_s3(data_list: list[dict], key: str, fields: list[str]):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(data_list)
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=buffer.getvalue().encode("utf-8-sig"))

def save_place_info_to_s3(person_id: int, batch_number: int, place_info_batch: list[dict]):
    key = f"place_info/place_info_{person_id}_{batch_number}.csv"
    upload_csv_to_s3(place_info_batch, key, PLACE_INFO_FIELDS)

def save_reviews_to_s3(person_id: int, batch_number: int, reviews_batch: list[dict]):
    key = f"reviews/reviews_{person_id}_{batch_number}.csv"
    upload_csv_to_s3(reviews_batch, key, REVIEW_FIELDS)
