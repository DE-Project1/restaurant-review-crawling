import json
import os
from typing import List, Dict

PLACE_INFO_DIR = "json_data/place_info"
REVIEWS_DIR = "json_data/reviews"
FAILED_PLACES_DIR = "json_data/failed_places"
RAW_DATA_DIR = "raw_data"

def _load_json_list(path: str) -> List[Dict]:
    """JSON 파일을 불러오거나 없으면 빈 리스트를 반환"""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return []

def _save_json_list(path: str, data: List[Dict]) -> None:
    """리스트 데이터를 JSON으로 저장"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_place_info_json(place_info: Dict, adm_dong_code: int) -> None:
    """장소 정보를 JSON으로 저장"""
    os.makedirs(PLACE_INFO_DIR, exist_ok=True)
    path = os.path.join(PLACE_INFO_DIR, f"place_info_{adm_dong_code}.json")
    data = _load_json_list(path)
    data.append(place_info)
    _save_json_list(path, data)

def save_reviews_json(reviews: List[Dict], adm_dong_code: int) -> None:
    """리뷰 정보를 JSON으로 저장"""
    if not reviews:
        return
    os.makedirs(REVIEWS_DIR, exist_ok=True)
    path = os.path.join(REVIEWS_DIR, f"reviews_{adm_dong_code}.json")
    data = _load_json_list(path)
    data.extend(reviews)  # 리뷰는 리스트라 extend로 추가
    _save_json_list(path, data)

def save_failed_places_json(place_id: str, adm_dong_code: int) -> None:
    """실패한 장소 정보를 JSON으로 저장"""
    os.makedirs(FAILED_PLACES_DIR, exist_ok=True)
    path = os.path.join(FAILED_PLACES_DIR, f"failed_places_{adm_dong_code}.json")
    data = _load_json_list(path)
    data.append({"adm_dong_code": adm_dong_code, "place_id": place_id})
    _save_json_list(path, data)

def save_place_raw_html(place_id: str, adm_dong_code: int, html_data: dict) -> None:
    """HTML 데이터를 저장 (이미 있으면 저장하지 않음)"""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    html_path = os.path.join(RAW_DATA_DIR, f"adc_{adm_dong_code}_place_rawdata_{place_id}.html")
    # 이미 HTML 저장됨 → 스킵
    if os.path.exists(html_path):
        return
    try:
        with open(html_path, "w", encoding="utf-8-sig") as f:
            f.write("===== HOME =====\n")
            f.write(html_data.get("home_html") or "")
            f.write("\n\n===== INFO =====\n")
            f.write(html_data.get("info_html") or "")
            f.write("\n\n===== REVIEWS =====\n")
            f.write(html_data.get("reviews_html") or "")
    except Exception as e:
        print(f"[ERROR] HTML 저장 실패 (PlaceID: {place_id}) - {e}")