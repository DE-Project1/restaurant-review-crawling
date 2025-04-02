import asyncio
import random
from datetime import datetime

# 비동기 랜덤 대기
async def async_random_delay(min_ms=300, max_ms=800):
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

# 타임스탬프 포함된 로깅
def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# 특수 문자 제거 (파일 이름용 등)
def clean_filename(text: str):
    return ''.join(c for c in text if c.isalnum() or c in (' ', '-', '_')).rstrip()

# 리뷰 개수 제한 체크
def should_continue_fetching(current_count: int, max_count: int = 100):
    return current_count < max_count