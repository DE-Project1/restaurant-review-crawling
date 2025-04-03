from typing import List, Dict

TARGET_DISTRICT = "서대문구"
MAX_PLACE_COUNT = 100
MIN_REVIEW_COUNT = 100
MIN_RATING = 4.2

def fetch_places(district: str) -> List[Dict]:
    """
    네이버 지도를 통해 지역 음식점 목록을 가져오고 맛집 조건을 부여함.
    """

    try:
        from service.naver_api import search_naver_map  # 필요 시 이 위치에 import
    except ImportError:
        print("❗search_naver_map 함수를 찾을 수 없습니다.")
        return []

    places: List[Dict] = search_naver_map(district, MAX_PLACE_COUNT)

    for place in places:
        place["is_matjip"] = is_matjip(place)

    return places

def is_matjip(place: Dict) -> bool:
    """
    리뷰 수와 평점 기준으로 맛집 여부 판별
    """
    reviews = int(place.get("review_count", 0))
    rating = float(place.get("rating", 0.0))

    return reviews >= MIN_REVIEW_COUNT and rating >= MIN_RATING

def is_general_restaurant(place: Dict) -> bool:
    """
    업종 카테고리에 '일반음식점'이 포함되는지 확인
    """
    category = place.get("category", "")
    return "일반음식점" in category
