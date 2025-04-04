import re
from datetime import datetime
import random

async def parse_opening_hours(page):
    try:
        schedule_blocks = await page.query_selector_all('div.w9QyJ')
        weekly_dict = {}

        for block in schedule_blocks:
            day_el = await block.query_selector('span.i8cJw')
            detail_el = await block.query_selector('div.H3ua4')

            day = await day_el.text_content() if day_el else ""
            detail = await detail_el.inner_text() if detail_el else ""

            if day and detail:
                day = day.strip()
                detail = detail.replace("\n", ", ").strip()
                weekly_dict[day] = f"{day} {detail}"

        # "매일"만 있는 경우는 그대로 반환
        if "매일" in weekly_dict:
            return weekly_dict["매일"]

        # 요일 구성일 경우 월~일 순으로 정렬
        KOR_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
        sorted_hours = [weekly_dict[day] for day in KOR_WEEKDAYS if day in weekly_dict]
        return " ".join(sorted_hours)

    except Exception as e:
        print(f"Error parsing opening hours: {e}")
        return "N/A"


async def crawl_place_info(page, place_id):
    url = f"https://m.place.naver.com/restaurant/{place_id}/home?entry=ple&reviewSort=recent"
    await page.goto(url)

    info = {}

    try:
        name_el = await page.query_selector('span.GHAhO')
        category_el = await page.query_selector('span.lnJFt')
        address_el = await page.query_selector('span.LDgIH')

        # 🔽 영업시간 영역 클릭 (펼쳐보기)
        toggle_el = await page.query_selector('a.gKP9i[aria-expanded="false"]')
        if toggle_el:
            await toggle_el.click()
            await page.wait_for_timeout(500)  # 약간 대기

        service_el = await page.query_selector('div.xPvPE')

        # ⬇️ 별점
        rating_el = await page.query_selector('span.PXMot.LXIwF')
        rating_text = await rating_el.text_content() if rating_el else None
        naver_rating = re.search(r"[\d.]+", rating_text).group() if rating_text else "N/A"

        # ⬇️ 리뷰 수
        visitor_review_el = await page.query_selector('a[href*="/review/visitor"]')
        blog_review_el = await page.query_selector('a[href*="/review/ugc"]')

        visitor_review_text = await visitor_review_el.text_content() if visitor_review_el else ""
        blog_review_text = await blog_review_el.text_content() if blog_review_el else ""

        visitor_review_count = int(re.sub(r"[^\d]", "", visitor_review_text)) if visitor_review_text else 0
        blog_review_count = int(re.sub(r"[^\d]", "", blog_review_text)) if blog_review_text else 0
        if isinstance(blog_review_count, tuple):
            blog_review_count = blog_review_count[0]

        # 뱃지
        badge_els = await page.query_selector_all('div.XtBbS')
        badges = []

        for el in badge_els:
            text = await el.text_content()
            if text:
                badges.append(text.strip())

        # ⬇️ 수집 시각
        crawled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        info["place_id"] = place_id
        info["name"] = await name_el.text_content() if name_el else "N/A"
        info["category"] = await category_el.text_content() if category_el else "N/A"
        info["address"] = await address_el.text_content() if address_el else "N/A"
        info["opening_hours"] = await parse_opening_hours(page)
        info["services"] = await service_el.text_content() if service_el else "N/A"

        info["naver_rating"] = naver_rating
        info["visitor_review_count"] = visitor_review_count
        info["blog_review_count"] = blog_review_count
        info["badges"] = ", ".join(badges) if badges else "N/A"
        info["crawled_at"] = crawled_at

    except Exception as e:
        print(f"[{place_id}] Error crawling place info: {e}")

    return info


async def crawl_reviews(page, place_id, place_name):
    url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
    await page.goto(url)
    await page.wait_for_timeout(random.randint(1500, 2000))
    # 스크롤 기반 자동 로딩 방식
    MAX_REVIEWS = 100

    # 리뷰 최대 로딩 유도
    for _ in range(50):  # 더 많은 반복 허용
        review_items = await page.query_selector_all("li.place_apply_pui")
        if len(review_items) >= MAX_REVIEWS:
            break

        await page.mouse.wheel(0, 5000)  # 하단까지 스크롤
        await page.wait_for_timeout(random.randint(800, 1200))

        more_btn = await page.query_selector("a.fvwqf")
        if more_btn:
            await more_btn.click()
            await page.wait_for_timeout(random.randint(800, 1200))
        else:
            break

    await page.wait_for_timeout(1500)

    review_items = await page.query_selector_all("li.place_apply_pui")
    print(f"[{place_name}] 리뷰 수집 대상: {len(review_items)}개")

    result = []
    for r in review_items[:MAX_REVIEWS]:
        try:
            nickname_el = await r.query_selector("div.pui__JiVbY3 span.pui__uslU0d span.pui__NMi-Dp")
            content_el = await r.query_selector("div.pui__vn15t2 a")

            nickname = await nickname_el.text_content() if nickname_el else "N/A"
            content = await content_el.text_content() if content_el else "N/A"

            # 날짜 element들 모두 찾기
            date_els = await r.query_selector_all("div.pui__QKE5Pr > span.pui__gfuUIT > span.pui__blind")
            date_raw = await date_els[1].text_content() if len(date_els) > 1 else "N/A"

            # 날짜 파싱
            date = "N/A"
            if date_raw != "N/A":
                m = re.search(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일", date_raw)
                if m:
                    y, mth, d = m.groups()
                    date = f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

            print("✅ nickname:", nickname)
            print("✅ content:", content)
            print("✅ date:", date)

            # 방문 상황 키워드(점심, 데이트, 바로 입장 등)
            situation_els = await r.query_selector_all("a.pui__uqSlGl > span.pui__V8F9nN")
            situations = [await el.text_content() for el in situation_els]
            situations_str = ", ".join([s.strip() for s in situations])
            print("✅ situations:", situations_str)

            #  리뷰 키워드(맛, 분위기 등)
            keyword_els = await r.query_selector_all("div.pui__HLNvmI > span.pui__jhpEyP")
            keywords = [await el.text_content() for el in keyword_els]
            keywords_str = ", ".join([k.strip() for k in keywords])
            print("✅ keywords:", keywords_str)

            # 리뷰 개수 및 방문 차수 추출
            review_count_el = await r.query_selector("div.pui__RuLAax > span:nth-child(1)")
            visit_count_el = await r.query_selector("div.pui__QKE5Pr > span.pui__gfuUIT:nth-child(2)")
            review_count = await review_count_el.text_content() if review_count_el else "N/A"
            visit_count = await visit_count_el.text_content() if visit_count_el else "N/A"

            # 리뷰 수: "리뷰 14" → 14
            review_count = re.sub(r"[^\d]", "", review_count)
            # 방문 차수: "1번째 방문" → 1
            visit_count = re.sub(r"[^\d]", "", visit_count)

            result.append({
                "place_id": place_id,
                "nickname": nickname.strip(),
                "content": content.strip(),
                "date": date.strip(),
                "situations": situations_str,
                "keywords": keywords_str,
                "review_count": review_count,
                "visit_count": visit_count
            })
        except Exception as e:
            print(f"[{place_id}] Error parsing review: {e}")
    return result


async def collect_place_data(page, place_name: str, place_id: int):
    reviews = await crawl_reviews(page, place_id, place_name)
    if len(reviews) < 100:
        print(f"[{place_name}] 리뷰 수 부족({len(reviews)}개), 크롤링 생략")
        return None, None

    info = await crawl_place_info(page, place_id)
    return info, reviews