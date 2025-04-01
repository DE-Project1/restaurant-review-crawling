
TARGET_DISTRICT = "마포구"
MAX_PLACE_COUNT = 400

def fetch_places(district: str, limit: int) -> List[Dict]:
    places = search_naver_map(district, limit)

    for place in places:
        place["is_matjip"] = is_matjip(place)
    return places

def is_matjip(place: dict) -> bool:
    # 예시 기준: 리뷰 수 ≥ 100, 평점 ≥ 4.2, 키워드 포함 등
    reviews = int(place.get("review_count", 0))
    rating = float(place.get("rating", 0.0))

    return reviews >= 100 and rating >= 4.2

def is_general_restaurant(place: dict) -> bool:
    category = place.get("category", "")
    return "일반음식점" in category
