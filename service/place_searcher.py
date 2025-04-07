from typing import List, Dict
import re, asyncio
from playwright.async_api import async_playwright

# 허용되는 음식점 카테고리 목록
ACCEPTED_CATEGORIES = [
    # 한식 계열
    "한식", "쌈밥", "보리밥", "비빔밥", "국밥", "찌개,전골", "곰탕,설렁탕", "김치찌개", "부대찌개", "청국장",
    "추어탕", "감자탕", "해장국", "갈비탕", "두부요리", "칼국수,만두", "전,빈대떡", "백반,가정식", "한식뷔페", "한정식",
    "국수", "냉면", "막국수", "삼계탕",

    # 고기 계열
    "육류,고기요리", "닭발", "고기뷔페", "돼지고기구이", "족발,보쌈", "곱창,막창,양", "고기요리", "소고기구이", "닭요리", "삼겹살",

    # 분식 계열
    "딤섬,중식만두", "종합분식", "김밥", "떡볶이", "라면", "만두", "호떡", "주먹밥", "분식",

    # 일식 계열
    "일식당", "돈가스", "샤브샤브", "오니기리", "오므라이스", "초밥,롤", "우동,소바", "일본식라면",
    "일식튀김,꼬치", "카레", "일식", "이자카야", "참치회", "회전초밥",

    # 중식 계열
    "중식당", "양꼬치", "마라탕", "게요리", "딤섬", "중식", "중화요리",

    # 양식 계열
    "스페인음식", "프랑스음식", "터키음식", "브런치", "스테이크,립", "피자", "파스타", "패밀리레스토랑",
    "경양식", "스파게티", "브런치카페", "이탈리안", "양식", "독일음식",

    # 세계 음식
    "아프리카음식", "멕시코,남미음식", "베트남음식", "태국음식", "인도음식", "아시아음식",
    "멕시칸,브라질", "퓨전음식",

    # 그 외 음식점
    "푸드트럭", "푸드코트", "토스트", "햄버거", "죽", "도시락", "샐러드", "샌드위치", "핫도그", "후렌치후라이",
    "다이어트,샐러드", "채식,샐러드뷔페", "덮밥", "철판요리", "치킨", "패스트푸드",

    # 주점
    "요리주점", "술집", "포장마차", "바(BAR)", "와인바", "칵테일바", "일반주점",

    # 기타
    "야식", "사철,영양탕", "사찰음식", "기사식당", "향토음식", "이북음식", "1인용", "레스토랑", "자연담은화로", "기타"
]

# 설정값들
MAX_PLACES = 100
MIN_REVIEW_COUNT = 100
MIN_RATING = 4.1

async def fetch_places(district: str) -> List[Dict]:
    """특정 지역의 맛집을 검색하고 크롤링하는 함수"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        search_word = district + " 맛집"
        search_url = f"https://map.naver.com/p/search/{search_word}"
        
        await page.goto(search_url)
        await page.wait_for_timeout(1500)

        results = []
        current_page = 1
        MAX_PAGES = 5

        while current_page <= MAX_PAGES:
            try:
                print(f"\n=== {current_page}페이지 크롤링 시작 ===")
                
                iframe_element = await page.wait_for_selector("iframe#searchIframe", timeout=5000)
                if not iframe_element:
                    print("❌ iframe_element 프레임을 찾지 못했습니다.")
                    break
                else:
                    print("iframe_element 완료")
                
                search_frame = await iframe_element.content_frame()
                if not search_frame:
                    print("❌ searchIframe 프레임을 찾지 못했습니다.")
                    break
                else:
                    print("searchIframe 완료")

                scroll_container = await search_frame.wait_for_selector("div#_pcmap_list_scroll_container", timeout=10000)
                if not scroll_container:
                    print("❌ scroll container를 찾지 못했습니다.")
                    break

                previous_height = 0
                while True:
                    current_height = await scroll_container.evaluate("(el) => el.scrollHeight")
                    await scroll_container.evaluate("(el) => el.scrollTo(0, el.scrollHeight)")
                    await page.wait_for_timeout(800)

                    if current_height == previous_height:
                        break
                    previous_height = current_height

                items = await search_frame.query_selector_all("li.UEzoS.rTjJo")
                print(f"✅ {current_page}페이지에서 {len(items)}개 장소 발견")

                for i, item in enumerate(items):
                    try:
                        print(f"번호 - {i + 1}")
                        place_name_el = await item.query_selector("span.TYaxT")
                        place_name = await place_name_el.text_content() if place_name_el else "N/A"

                        category_el = await item.query_selector("span.KCMnt")
                        category = await category_el.text_content() if category_el else "N/A"
                        if category not in ACCEPTED_CATEGORIES:
                            print(f"🚫 카테고리 제외: {category}")
                            continue

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

                        rating = None
                        rating_el = await item.query_selector("span.h69bs.orXYY")
                        rating_text = await rating_el.text_content() if rating_el else None
                        if rating_text:
                            match_rating = re.search(r"[\d.]+", rating_text)
                            rating = float(match_rating.group()) if match_rating else 0.0
                            if rating < MIN_RATING:
                                print(f"🚫 별점 낮음: {rating}")
                                continue

                        click_target = await item.query_selector("div.place_bluelink")
                        if click_target:
                            await click_target.click()
                            await page.wait_for_timeout(1000)
                            detail_url = page.url
                            match = re.search(r'/place/(\d+)', detail_url)
                            if match:
                                place_id = match.group(1)
                                print(f"✅ {len(results) + 1}번째 장소 ID: {place_id}")
                                results.append({
                                    "id": place_id,
                                    "name": place_name,
                                    "category": category,
                                    "review_count": review_count,
                                    "rating": rating,
                                })
                            else:
                                print("❌ place_id 추출 실패")

                    except Exception as e:
                        print(f"[ERROR] 항목 처리 중 오류: {e}")
                        continue

                current_page += 1

            except Exception as e:
                print(f"[ERROR] 페이지 처리 중 오류: {e}")
                break

        await browser.close()
        return results 