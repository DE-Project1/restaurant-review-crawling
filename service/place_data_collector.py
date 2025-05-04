import re
from datetime import datetime
import random

# 장소 상세 정보 수집
async def crawl_place_info(page, place_id, adm_dong_code):
    # 홈 페이지로 이동
    url = f"https://m.place.naver.com/restaurant/{place_id}/home?entry=ple&reviewSort=recent"
    await page.goto(url)
    await page.wait_for_timeout(1000)

    info = {}

    try:
        # 상호명, 카테고리, 주소
        name_el = await page.query_selector('span.GHAhO')
        category_el = await page.query_selector('span.lnJFt')
        address_el = await page.query_selector('span.LDgIH')

        await page.wait_for_timeout(random.randint(1000, 1500))

        # 영업시간 클릭해 펼치기
        toggle_el = await page.query_selector('a.gKP9i[aria-expanded="false"]')
        if toggle_el:
            await toggle_el.click()
            await page.wait_for_timeout(random.randint(800, 1200))  # 약간 대기

        # 서비스
        service_el = await page.query_selector('div.xPvPE')

        # 별점
        rating_el = await page.query_selector('span.PXMot.LXIwF')
        rating_text = await rating_el.text_content() if rating_el else None
        naver_rating = re.search(r"[\d.]+", rating_text).group() if rating_text else "N/A"

        # 방문자 리뷰 수, 블로그 리뷰 수
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

        # 수집 시각
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
        info["adm_dong_code"] = adm_dong_code

    except Exception as e:
        print(f"[{place_id}] Error crawling place info: {e}")

    return info

# 리뷰 크롤링
async def crawl_reviews(page, place_id):
    url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
    await page.goto(url)
    await page.wait_for_timeout(1000)

    # 리뷰 수 조건 먼저 체크
    review_url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
    await page.goto(review_url)
    await page.wait_for_timeout(1000)

    MAX_REVIEWS = 100
    review_header = await page.query_selector('div.place_section_header_title')
    if review_header:
        review_html = await review_header.inner_html()
        match = re.search(r'<em class="place_section_count">(\d+)</em>', review_html)
        if match:
            total_reviews = int(match.group(1))
            if total_reviews < MAX_REVIEWS:
                print(f"❌ 리뷰 수 부족: {total_reviews}개 → 수집 제외")
                return Exception

    # 스크롤/더보기 버튼 통해 최대한 리뷰 로딩 (최대 MAX_REVIEWS개)
    for _ in range(10): # 더보기 버튼 클릭 최대 횟수
        review_items = await page.query_selector_all("li.place_apply_pui")
        if len(review_items) >= MAX_REVIEWS:
            break

        await page.mouse.wheel(0, 5000)
        await page.wait_for_timeout(500)

        prev_count = len(review_items)
        more_btn = await page.query_selector("a.fvwqf") # 더보기 버튼
        if more_btn:
            try:
                await more_btn.click()
                await page.wait_for_timeout(1000)

                # 더보기 클릭 후 리뷰 수가 늘어났는지 확인
                for _ in range(2):  # 최대 2회 재시도
                    new_items = await page.query_selector_all("li.place_apply_pui")
                    if len(new_items) > prev_count:
                        break
                    await page.wait_for_timeout(60000) # 1분 대기
            except Exception as e:
                print(f"⚠️ 더보기 클릭 실패: {e}")
                break
        else:
            break
    await page.wait_for_timeout(1000)

    review_items = await page.query_selector_all("li.place_apply_pui")

    review_count = len(review_items)
    if review_count < MAX_REVIEWS:
        print(f"리뷰 수 부족({review_count}개), 크롤링 생략")
        return Exception
    else:
        print(f"리뷰 수집 대상: {review_count}개")

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

            # 방문 상황 키워드(점심, 데이트, 바로 입장 등)
            situation_els = await r.query_selector_all("a.pui__uqSlGl > span.pui__V8F9nN")
            situations = [await el.text_content() for el in situation_els]
            situations_str = ", ".join([s.strip() for s in situations])

            #  리뷰 키워드(맛, 분위기 등)
            keyword_els = await r.query_selector_all("div.pui__HLNvmI > span.pui__jhpEyP")
            keywords = [await el.text_content() for el in keyword_els]
            keywords_str = ", ".join([k.strip() for k in keywords])

            # 리뷰 개수 및 방문 차수 추출
            review_count_el = await r.query_selector("div.pui__RuLAax > span:nth-child(1)")
            visit_count_el = await r.query_selector("div.pui__QKE5Pr > span.pui__gfuUIT:nth-child(2)")
            review_count = await review_count_el.text_content() if review_count_el else "N/A"
            visit_count = await visit_count_el.text_content() if visit_count_el else "N/A"

            # 리뷰 수: "리뷰 14" → 14
            review_count = re.sub(r"[^\d]", "", review_count)
            # 방문 차수: "1번째 방문" → 1
            visit_count = re.sub(r"[^\d]", "", visit_count)

            review_data = {
                "place_id": place_id,
                "nickname": nickname.strip(),
                "content": content.strip(),
                "date": date.strip(),
                "situations": situations_str,
                "keywords": keywords_str,
                "review_count": review_count,
                "visit_count": visit_count
            }
            print(f"수집 완료: {review_data}")
            result.append(review_data)
        except Exception as e:
            print(f"[{place_id}] Error parsing review: {e}")
    return result

# 영업시간 파싱
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

        # 요일 구성일 경우 월~일 순으로 정렬해 문자열로 병합
        KOR_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
        sorted_hours = [weekly_dict[day] for day in KOR_WEEKDAYS if day in weekly_dict]
        return " ".join(sorted_hours)

    except Exception as e:
        print(f"Error parsing opening hours: {e}")
        return "N/A"