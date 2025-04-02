# service/naver_api.py

def search_naver_map(district: str, limit: int):
    print(f"[MOCK] '{district}'에서 {limit}개의 장소를 검색 중...")
    return [
        {
            "id": 38232807,
            "name": "소녀방앗간",
            "category": "일반음식점",
            "review_count": 150,
            "rating": 4.6,
        },
        {
            "id": 456,
            "name": "슬로우캘리",
            "category": "일반음식점",
            "review_count": 90,
            "rating": 3.8,
        },
    ]
