import aiofiles
import csv
import os

PLACE_INFO_PATH = "data/place_info.csv"
PLACE_REVIEW_PATH = "data/place_reviews.csv"

async def save_place_info_csv(info: dict):
    file_exists = os.path.exists(PLACE_INFO_PATH)

    async with aiofiles.open(PLACE_INFO_PATH, mode="a", encoding="utf-8-sig", newline="") as f:
        f_writer = await f.__aenter__()
        fieldnames = info.keys()
        writer = csv.DictWriter(f_writer, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()
        writer.writerow(info)

async def save_reviews_csv(reviews: list[dict]):
    if not reviews:
        return

    file_exists = os.path.exists(PLACE_REVIEW_PATH)

    async with aiofiles.open(PLACE_REVIEW_PATH, mode="a", encoding="utf-8-sig", newline="") as f:
        f_writer = await f.__aenter__()
        fieldnames = reviews[0].keys()
        writer = csv.DictWriter(f_writer, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()
        writer.writerows(reviews)