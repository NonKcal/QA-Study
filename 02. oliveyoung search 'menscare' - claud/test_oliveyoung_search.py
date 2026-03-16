"""
올리브영 맨즈케어 검색 자동화 테스트
─────────────────────────────────────────────
단일 책임: 테스트 실행 + 카카오톡 결과 전송만 담당
실행 시점: YML STEP 6 → refresh_token.py 실행 후

ISTQB 기반:
  - Functional Testing
  - Equivalence Partitioning (동치 분할)
  - Boundary Value Analysis (경계값 분석)
테스트 레벨: Component Integration Testing
실행 환경: GitHub Actions (매일 KST 06~11시 자동 스케줄)
위치: C:\QA_Study\02. oliveyoung search 'menscare' - claud

필요 환경변수 (GitHub Secrets):
  KAKAO_ACCESS_TOKEN  : 카카오 액세스 토큰 (refresh_token.py 가 갱신 완료한 값)
  KAKAO_REST_API_KEY  : 카카오 REST API 키
  KAKAO_CLIENT_SECRET : 카카오 클라이언트 시크릿
  KAKAO_REFRESH_TOKEN : 카카오 리프레시 토큰
"""

import asyncio
import os
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# KST 타임존 — GitHub Actions 서버는 UTC 기준이므로 표시용 변환
KST = timezone(timedelta(hours=9))


# ──────────────────────────────────────────────
# 카카오톡 전송 유틸
# ──────────────────────────────────────────────
class KakaoNotifier:
    """
    카카오톡 '나에게 보내기' 전송 전담 클래스
    토큰 갱신 로직 없음 → refresh_token.py 에서 사전 처리됨
    """

    SEND_ME_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    def __init__(self):
        self.access_token = os.environ.get("KAKAO_ACCESS_TOKEN", "")

    def send(self, text: str) -> bool:
        """카카오톡 나에게 보내기"""
        if not self.access_token:
            print("[카카오] ACCESS_TOKEN 없음 → 전송 스킵")
            return False

        template = {
            "object_type": "text",
            "text": text[:2000],    # 카카오 최대 2000자
            "link": {
                "web_url":        "https://www.oliveyoung.co.kr",
                "mobile_web_url": "https://www.oliveyoung.co.kr",
            },
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        payload = {"template_object": json.dumps(template)}

        try:
            resp = requests.post(
                self.SEND_ME_URL, headers=headers, data=payload, timeout=10
            )
            resp.raise_for_status()
            print("[카카오] 전송 성공 ✅")
            return True
        except Exception as e:
            print(f"[카카오] 전송 실패: {e}")
            return False


# ──────────────────────────────────────────────
# 테스트 케이스 정의
# ISTQB EP(동치 분할) + BVA(경계값 분석) 기반 설계
# ──────────────────────────────────────────────
TEST_CASES = [
    # (test_id, keyword,      category,  description)
    ("TC_001", "맨즈케어",   "Valid",   "정상 검색어 - 카테고리명 일치"),
    ("TC_002", "샴푸",        "Valid",   "정상 검색어 - 관련 상품명"),
    ("TC_003", "삼퓨",        "Typo",    "오타 - 받침 혼동 (샴→삼)"),
    ("TC_004", "샤ㅁ푸",      "Typo",    "오타 - 자음/모음 분리 입력"),
    ("TC_005", "샴ㅍ",        "Typo",    "오타 - 불완전 입력 (미완성 글자)"),
    ("TC_006", "ㅅㅍ",        "Typo",    "오타 - 초성 검색"),
    ("TC_007", "menscare",    "English", "영문 검색어"),
    ("TC_008", "men's care",  "English", "영문 검색어 - 공백/특수문자 포함"),
    ("TC_009", "!@#$%",       "Special", "특수문자만 입력 - 비정상"),
    ("TC_010", " ",           "Edge",    "공백만 입력 - 경계값"),
]

TARGET_URL  = "https://www.oliveyoung.co.kr"
SEARCH_LIMIT = 10


# ──────────────────────────────────────────────
# 검색 실행
# ──────────────────────────────────────────────
async def search_oliveyoung(page, keyword: str) -> list[dict]:
    """
    올리브영 검색 수행 후 상위 N개 상품 정보 반환
    반환 필드: rank, name, brand, price, url
    """
    products = []
    try:
        search_url = (
            "https://www.oliveyoung.co.kr/store/search/getSearchMain.do"
            f"?query={requests.utils.quote(keyword)}"
        )
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

        # 팝업/레이어 닫기
        try:
            close_btn = page.locator(
                ".gy-pop-close, .pop-close, [aria-label='닫기']"
            ).first
            if await close_btn.is_visible(timeout=3000):
                await close_btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

        # 상품 카드 대기
        await page.wait_for_selector(
            ".prd-itemname, .name, .goods-name", timeout=15000
        )

        # 상품 목록 수집
        items = await page.query_selector_all(".prd-item, .item, .goods-li")
        if not items:
            items = await page.query_selector_all(
                "[class*='prd-item'], [class*='goods']"
            )

        for i, item in enumerate(items[:SEARCH_LIMIT], 1):
            try:
                name_el  = await item.query_selector(".prd-itemname, .goods-name, .name")
                brand_el = await item.query_selector(".prd-brandname, .brand, .txt-brand")
                price_el = await item.query_selector(".price-1, .price, .cost")
                link_el  = await item.query_selector("a")

                name  = (await name_el.inner_text()).strip()  if name_el  else "N/A"
                brand = (await brand_el.inner_text()).strip() if brand_el else "N/A"
                price = (await price_el.inner_text()).strip() if price_el else "N/A"
                href  = await link_el.get_attribute("href")   if link_el  else ""
                url   = href if href.startswith("http") else TARGET_URL + href

                products.append({
                    "rank": i, "name": name, "brand": brand,
                    "price": price, "url": url,
                })
            except Exception:
                continue

    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        print(f"  [오류] '{keyword}' 검색 중 예외: {e}")

    return products


# ──────────────────────────────────────────────
# 단일 TC 실행
# ──────────────────────────────────────────────
async def run_test_case(page, tc: tuple) -> dict:
    """단일 테스트 케이스 실행 및 결과 반환"""
    tc_id, keyword, category, desc = tc
    print(f"\n{'─'*55}")
    print(f"▶ {tc_id} | [{category}] {desc}")
    print(f"  검색어: '{keyword}'")

    start    = datetime.now()
    products = await search_oliveyoung(page, keyword)
    elapsed  = (datetime.now() - start).total_seconds()

    # ── 판정 ──
    # Special/Edge: 결과 없음이 예상 동작 → PASS
    # 그 외       : 결과 있음이 예상 동작 → PASS
    if category in ("Special", "Edge"):
        verdict = "PASS" if len(products) == 0 else "FAIL"
        note    = "결과 없음(예상 동작)" if verdict == "PASS" \
                  else f"예상치 못한 {len(products)}건 결과"
    else:
        verdict = "PASS" if len(products) > 0 else "FAIL"
        note    = f"상위 {len(products)}건 수집" if products else "검색 결과 없음"

    icon = "✅" if verdict == "PASS" else "❌"
    print(f"  결과: {icon} {verdict} | {note} | {elapsed:.1f}s")
    for p in products:
        price_clean = re.sub(r'\s+', ' ', p['price'])
        print(f"    #{p['rank']:02d} {p['brand']} - {p['name']} | {price_clean}")

    return {
        "tc_id":       tc_id,
        "keyword":     keyword,
        "category":    category,
        "description": desc,
        "verdict":     verdict,
        "note":        note,
        "elapsed":     elapsed,
        "products":    products,
    }


# ──────────────────────────────────────────────
# 카카오톡 리포트 포맷
# ──────────────────────────────────────────────
def build_kakao_report(results: list[dict]) -> str:
    """테스트 결과를 카카오톡 메시지로 포맷"""
    now       = datetime.now(KST).strftime("%Y-%m-%d %H:%M (KST)")
    total     = len(results)
    passed    = sum(1 for r in results if r["verdict"] == "PASS")
    failed    = total - passed
    pass_rate = (passed / total * 100) if total else 0

    lines = [
        "🧪 올리브영 맨즈케어 검색 자동화 테스트",
        f"📅 실행시각: {now}",
        f"📊 결과: {passed}/{total} PASS ({pass_rate:.0f}%)",
        "─" * 30,
    ]

    for r in results:
        icon = "✅" if r["verdict"] == "PASS" else "❌"
        lines.append(f"{icon} {r['tc_id']} [{r['category']}] '{r['keyword']}'")
        lines.append(f"   → {r['note']} ({r['elapsed']:.1f}s)")

        for p in r["products"][:3]:
            price_clean = re.sub(r'\s+', ' ', p['price'])
            lines.append(f"   #{p['rank']} {p['name']} {price_clean}")

        if len(r["products"]) > 3:
            lines.append(f"   ... 외 {len(r['products'])-3}건")

    lines += [
        "─" * 30,
        f"🔴 FAIL: {failed}건" if failed else "🟢 전체 PASS",
        "📌 QA Study | Playwright + Python",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 메인 엔트리
# ──────────────────────────────────────────────
async def main():
    now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')
    print("=" * 55)
    print("  올리브영 맨즈케어 검색 자동화 테스트 시작")
    print(f"  실행 시각: {now_kst}")
    print("=" * 55)

    results  = []
    notifier = KakaoNotifier()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",            # GitHub Actions (Linux) 필수
                "--disable-dev-shm-usage", # 메모리 부족 방지
                "--disable-gpu",
                "--window-size=1400,900",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # 사이트 초기 접근 (쿠키/세션 확보)
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1000)

        for tc in TEST_CASES:
            result = await run_test_case(page, tc)
            results.append(result)
            await page.wait_for_timeout(1500)  # 요청 간 간격 (anti-bot 대응)

        # 실패 케이스 스크린샷 저장
        if any(r["verdict"] == "FAIL" for r in results):
            await page.screenshot(path="error_capture.png", full_page=True)
            print("[스크린샷] error_capture.png 저장됨")

        await browser.close()

    # ── 최종 요약 ──
    total  = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"\n{'='*55}")
    print(f"  최종: {passed}/{total} PASS  |  {total-passed} FAIL")
    print(f"{'='*55}")

    # ── 카카오톡 전송 ──
    report = build_kakao_report(results)
    print("\n[카카오톡 리포트 미리보기]\n")
    print(report)
    notifier.send(report)


if __name__ == "__main__":
    asyncio.run(main())
