import csv
import asyncio
from playwright.async_api import async_playwright
import re
import datetime
import random

async def crawl_place_info():
    url = f"https://m.place.naver.com/restaurant/{place_id}/home?entry=ple&reviewSort=recent"
    await page.goto(url)

    info = {}

    try:
        name_el = await page.query_selector('span.Fc1rA')  # 장소 이름
        category_el = await page.query_selector('span.DJJvD')  # 업종
        address_el = await page.query_selector('span.LDgIH')  # 주소
        phone_el = await page.query_selector('span.xlx7Q')  # 전화번호

        info["place_id"] = place_id
        info["name"] = await name_el.text_content() if name_el else "N/A"
        info["category"] = await category_el.text_content() if category_el else "N/A"
        info["address"] = await address_el.text_content() if address_el else "N/A"
        info["phone"] = await phone_el.text_content() if phone_el else "N/A"

    except Exception as e:
        print(f"[{place_id}] Error crawling place info: {e}")

    return info
    
    
async def crawl_reviews(page, place_id, place_name):
    url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent"
    await page.goto(url)
    await page.wait_for_timeout(random.randint(1500, 2000))

    for _ in range(30):
        try:
            more_btn = await page.query_selector('a.fvwqf')
            if more_btn:
                await more_btn.click()
                await page.wait_for_timeout(random.randint(400, 700))
            else:
                break
        except:
            break

    await page.wait_for_timeout(1000)

    review_items = await page.query_selector_all("li.place_apply_pui")
    print(f"[{place_name}] 리뷰 수집 대상: {len(review_items)}개")

    result = []
    for r in review_items[:100]: # 리뷰 갯수
        try:
            nickname_el = await r.query_selector("div.pui__JiVbY3 span.pui__uslU0d span.pui__NMi-Dp")
            content_el = await r.query_selector("div.pui__vn15t2 a")
            date_el = await r.query_selector("div.pui__QKE5Pr > span.pui__gfuUIT > span.pui__blind")
            revisit_el = await r.query_selector("div.pui__QKE5Pr > span:nth-child(2)")

            nickname = await nickname_el.text_content() if nickname_el else "N/A"
            content = await content_el.text_content() if content_el else "N/A"
            date = await date_el.text_content() if date_el else "N/A"
            revisit = await revisit_el.text_content() if revisit_el else "N/A"

            # 날짜 파싱
            if date != "N/A":
                m = re.search(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일", date)
                if m:
                    y, mth, d = m.groups()
                    date = f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

            print("✅ nickname:", nickname)
            print("✅ content:", content)
            print("✅ date:", date)
            print("✅ revisit:", revisit)

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

            result.append({
                "place_name": place_name,
                "nickname": nickname.strip(),
                "content": content.strip(),
                "date": date.strip(),
                "revisit": revisit.strip(),
                "situations": situations_str,
                "keywords": keywords_str,
            })
        except Exception as e:
            print(f"[{place_id}] Error parsing review: {e}")
    return result


async def collect_place_data(page, place_name: str, place_id: int):
    info = await crawl_place_info(page, place_id)
    reviews = await crawl_reviews(page, place_id, place_name)
    return info, reviews