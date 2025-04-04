from typing import List, Dict
import re, asyncio
from playwright.async_api import async_playwright

ACCEPTED_CATEGORIES = [
    "야식", "푸드트럭", "아프리카음식", "한식", "사철,영양탕", "사찰음식", "기사식당", "향토음식",
    "이북음식", "1인용", "딤섬,중식만두", "스페인음식", "프랑스음식", "터키음식", "종합분식",
    "김밥", "떡볶이", "라면", "만두", "호떡", "주먹밥", "베이글", "푸드코트", "이탈리아음식",
    "토스트", "햄버거", "한정식", "육류,고기요리", "닭발", "쌈밥", "보리밥", "비빔밥", "죽",
    "국밥", "국수", "냉면", "막국수", "찌개,전골", "김치찌개", "부대찌개", "청국장", "추어탕",
    "감자탕", "해장국", "곰탕,설렁탕", "갈비탕", "두부요리", "칼국수,만두", "전,빈대떡",
    "해물,생선요리", "일식당", "일본식라면", "돈가스", "샤브샤브", "오니기리", "오므라이스",
    "우동,소바", "일식튀김,꼬치", "초밥,롤", "카레", "중식당", "양꼬치", "멕시코,남미음식",
    "브런치", "스테이크,립", "피자", "샌드위치", "핫도그", "후렌치후라이", "한식뷔페",
    "백반,가정식", "요리주점", "덮밥", "독일음식", "다이어트,샐러드", "고기뷔페", "해산물뷔페",
    "일식,초밥뷔페", "채식,샐러드뷔페", "브런치카페", "마라탕", "게요리", "양식", "돼지고기구이", "족발,보쌈", "베트남음식",
    "곱창,막창,양", "패밀리레스토랑", "자연담은화로"
]

MAX_PLACE_COUNT = 100
MIN_REVIEW_COUNT = 100
MIN_RATING = 4.1

async def fetch_places(district: str) -> List[Dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        search_word = district + " 맛집"
        search_url = f"https://map.naver.com/p/search/{search_word}"
        await page.goto(search_url)
        await page.wait_for_timeout(1500)

        # iframe 로딩 대기 후 프레임 접근
        try:
            iframe_element = await page.wait_for_selector("iframe#searchIframe", timeout=5000)
            if not iframe_element:
                print("❌ iframe_element 프레임을 찾지 못했습니다.")
                return []
            else:
                print("iframe_element 완료")
            search_frame = await iframe_element.content_frame()
            if not search_frame:
                print("❌ searchIframe 프레임을 찾지 못했습니다.")
                return []
            else:
                print("searchIframe 완료: " + str(search_frame))

            # Lazy Loading을 위한 scroll container 선택
            scroll_container = await search_frame.wait_for_selector("div#_pcmap_list_scroll_container", timeout=10000)
            if not scroll_container:
                print("❌ scroll container를 찾지 못했습니다.")
                return []

            # Lazy Loading 대응: 끝까지 스크롤
            previous_height = 0
            while True:
                current_height = await scroll_container.evaluate("(el) => el.scrollHeight")
                await scroll_container.evaluate("(el) => el.scrollTo(0, el.scrollHeight)")
                await page.wait_for_timeout(800)

                if current_height == previous_height:
                    break
                previous_height = current_height

        except Exception as e:
            print(f"로딩 실패: {e}")
            return []

        # 리스트 아이템 가져오기
        items = await search_frame.query_selector_all("li.UEzoS.rTjJo")
        print(f"✅ 총 {len(items)}개 장소 발견")

        results = []

        for i, item in enumerate(items[:MAX_PLACE_COUNT]):
            try:
                print(f"번호 - {i + 1}")
                # 이름 확인
                place_name_el = await item.query_selector("span.TYaxT")  # 가게명 클래스
                place_name = await place_name_el.text_content() if place_name_el else "N/A"

                # 카테고리 확인
                category_el = await item.query_selector("span.KCMnt")
                category = await category_el.text_content() if category_el else "N/A"
                if category not in ACCEPTED_CATEGORIES:
                    print(f"🚫 카테고리 제외: {category}")
                    continue

                # 리뷰 수 확인
                review_el = await item.query_selector_all("span.h69bs")
                review_count = 0
                for span in review_el:
                    text = await span.inner_text()
                    if "리뷰" in text:
                        digits = re.search(r"(\d+)", text)
                        if digits:
                            review_count = int(digits.group(1))
                        break
                if review_count < MIN_REVIEW_COUNT:
                    print(f"🚫 리뷰 수 부족: {review_count}")
                    continue
                else:
                    print(f"리뷰 수: {review_count}")

                # 별점 확인 (존재할 경우에만)
                rating = None
                rating_el = await item.query_selector("span.h69bs.orXYY")
                rating_text = await rating_el.text_content() if rating_el else None
                if rating_text:
                    match_rating = re.search(r"[\d.]+", rating_text)
                    rating = float(match_rating.group()) if match_rating else 0.0
                    if rating < MIN_RATING:
                        print(f"🚫 별점 낮음: {rating}")
                        continue

                # 클릭 후 상세 페이지로 이동
                print("상세 페이지로 이동")
                click_target = await item.query_selector("div.place_bluelink")
                if click_target:
                    await click_target.click()
                    await page.wait_for_timeout(1000)
                    # place_id 추출
                    detail_url = page.url
                    match = re.search(r'/place/(\d+)', detail_url)
                    if match:
                        place_id = match.group(1)
                        print(f"✅ {i + 1}번째 장소 ID: {place_id}")
                        results.append({
                            "id": place_id,
                            "name": place_name,
                            "category": category,
                            "review_count": review_count,
                            "rating": rating,
                        })
                    else:
                        print("❌ place_id 추출 실패")
                # print(results)
            except Exception as e:
                print(f"[ERROR] {i + 1}번째 항목 처리 중 오류: {e}")
                return []
        return results

# 리뷰 수와 평점 기준으로 맛집 여부 판별
def is_matjip(place: Dict) -> bool:
    reviews = int(place.get("review_count", MIN_REVIEW_COUNT))
    rating = float(place.get("rating", MIN_RATING))
    return reviews >= MIN_REVIEW_COUNT and rating >= MIN_RATING

# 업종 카테고리에 '일반음식점'이 포함되는지 확인
def is_general_restaurant(place: Dict) -> bool:
    category = place.get("category", "")
    return "일반음식점" in category
