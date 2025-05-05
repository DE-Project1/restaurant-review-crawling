from typing import List
import re
from playwright.async_api import async_playwright
from service.utils import block_unnecessary_resources, scroll_until_no_more

# 수집 대상인 음식점 카테고리 리스트
ACCEPTED_CATEGORIES = [
    # 한식 계열
    "한식", "쌈밥", "보리밥", "비빔밥", "국밥", "찌개,전골", "곰탕,설렁탕", "김치찌개", "부대찌개", "청국장",
    "추어탕", "감자탕", "해장국", "갈비탕", "두부요리", "칼국수,만두", "전,빈대떡", "백반,가정식", "한식뷔페", "한정식",
    "국수", "냉면", "막국수", "삼계탕", "주꾸미요리", "순대,순댓국", "백숙,삼계탕", "치킨,닭강정", "생선구이",
    # 고기 계열
    "육류,고기요리", "닭발", "고기뷔페", "돼지고기구이", "족발,보쌈", "곱창,막창,양", "고기요리", "소고기구이", "닭요리", "삼겹살",
    # 분식 계열
    "딤섬,중식만두", "종합분식", "김밥", "떡볶이", "라면", "만두", "주먹밥", "분식",
    # 일식 계열
    "일식당", "돈가스", "샤브샤브", "오니기리", "오므라이스", "초밥,롤", "우동,소바", "일본식라면",
    "일식튀김,꼬치", "카레", "일식", "이자카야", "참치회", "회전초밥",
    # 중식 계열
    "중식당", "양꼬치", "마라탕", "게요리", "딤섬", "중식", "중화요리",
    # 양식 계열
    "브런치", "스테이크,립", "피자", "파스타", "패밀리레스토랑",
    "경양식", "스파게티", "브런치카페", "양식", "독일음식", "스파게티,파스타전문",
    # 세계 음식
    "이탈리아음식", "스페인음식", "프랑스음식", "터키음식", "아프리카음식",
    "멕시코,남미음식", "베트남음식", "태국음식", "인도음식", "아시아음식",
    "멕시칸,브라질", "퓨전음식",
    # 주점
    "요리주점", "술집", "포장마차", "바(BAR)", "와인바", "와인", "맥주,호프", "칵테일바", "이자카야",
    # 그 외 음식점
    "푸드트럭", "푸드코트", "토스트", "햄버거", "죽", "도시락", "샐러드", "샌드위치", "핫도그", "후렌치후라이",
    "다이어트,샐러드", "채식,샐러드뷔페", "덮밥", "철판요리", "치킨", "패스트푸드",
    "야식", "사철,영양탕", "사찰음식", "기사식당", "향토음식", "이북음식", "레스토랑",
    "해물,생선요리", "일식,초밥뷔페", "해산물뷔페", "생선회", "도시락,컵밥", "찜닭", "조개요리", "오리요리", "아귀찜,해물찜", "바닷가재요리"
]

MIN_REVIEW_COUNT = 140  # 방문자 리뷰
MIN_RATING = 4.1        # 최소 별점 기준

# 장소 검색 및 ID 리스트 크롤링 함수
# 특정 지역에서 조건을 만족하는 장소 최대 max_places개까지 수집 (place_id만)
async def search_and_fetch_place_ids(district: str, max_places: int) -> List[str]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--window-size=400,800"])
        context = await browser.new_context(
            viewport={"width": 400, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await block_unnecessary_resources(page)
        # 페이지 이동
        search_word = district + " 맛집"
        await page.goto(f"https://map.naver.com/p/search/{search_word}")
        await page.wait_for_timeout(2000)  # 초기 로딩 대기
        # place_ids에 장소 ID 수집
        place_ids = []
        current_page = 1
        while current_page <= 5 and len(place_ids) < max_places: # 최대 페이지 번호 5; 장소 수 max_places 이하여야
            try:
                print(f"\n=== {current_page}페이지 크롤링 시작 ===")
                iframe_element = await page.wait_for_selector("iframe#searchIframe", timeout=5000)
                search_frame = await iframe_element.content_frame()
                scroll_container = await search_frame.wait_for_selector("div#_pcmap_list_scroll_container", timeout=10000)
                await scroll_until_no_more(scroll_container) # 스크롤 다운으로 전체 아이템 로딩
                place_items = await search_frame.query_selector_all("li.UEzoS.rTjJo")
                print(f"✅ {current_page}페이지에서 {len(place_items)}개 장소 발견")
                # place_items에서 장소 new_ids 얻어 place_ids에 추가
                new_ids = await parse_places_from_items(place_items, page, max_places)
                place_ids.extend(new_ids)
                if len(place_ids) >= max_places:
                    break
                # 다음 페이지 넘기기
                next_btn = search_frame.locator('a.eUTV2:has(span.place_blind:text("다음페이지"))').first
                if await next_btn.count() == 0:
                    print("❌ 다음페이지 버튼 못 찾음. 종료")
                    return False
                # 비활성화 상태인지 확인
                if await next_btn.get_attribute("aria-disabled") == "true":
                    print("⛔ 다음 페이지 버튼이 비활성화됨. 종료")
                    return False
                # 클릭 후 대기
                current_page += 1
                await next_btn.click()
                await page.wait_for_timeout(1500)
            except Exception as e:
                print(f"[ERROR] 페이지 처리 중 오류: {e}")
                break
        await context.close()
        await browser.close()
        return place_ids

async def parse_places_from_items(items, page, max_places: int) -> List[str] :
    place_ids: List[str] = []
    for item in items:
        if len(place_ids) >= max_places:
            break
        try:
            # 카테고리
            category_el = await item.query_selector("span.KCMnt")
            category = await category_el.text_content() if category_el else "N/A"
            if category not in ACCEPTED_CATEGORIES:
                print(f"🚫 카테고리 제외: {category}")
                continue
            # 방문자 리뷰
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
            # 별점
            rating_el = await item.query_selector("span.h69bs.orXYY")
            rating_text = await rating_el.text_content() if rating_el else None
            if rating_text:
                match_rating = re.search(r"[\d.]+", rating_text)
                rating = float(match_rating.group()) if match_rating else 0.0
                if rating < MIN_RATING:
                    print(f"🚫 별점 낮음: {rating}")
                    continue
            # 상세 페이지 이동 후 ID 추출
            click_target = await item.query_selector("div.place_bluelink")
            if click_target:
                await click_target.click()
                await page.wait_for_timeout(1500)
                detail_url = page.url
                match = re.search(r'/place/(\d+)', detail_url)
                if match:
                    place_id = match.group(1)
                    print(f"✅ {len(place_ids) + 1}번째 장소 ID: {place_id}")
                    place_ids.append(place_id)
                else:
                    print("❌ place_id 추출 실패")
        except Exception as e:
            print(f"[ERROR] 항목 처리 중 오류: {e}")
            continue
    return place_ids