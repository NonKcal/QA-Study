"""
Test_Case_main_pg.py
─────────────────────────────────────────────────────────────────────────────
대상: 올리브영 메인 페이지
케이스:
  TC-01  메인 페이지 '인기 행사만 모았어요!' 영역 노출 확인
  TC-02  '포차코' 행사 노출 및 클릭 동작 확인 (TC-02-1 ~ TC-02-9)

공통 조건:
  - PC Chrome DevTools → iPhone 14 Pro Max 에뮬레이션 (conftest.py)
  - 스크롤 복원 허용 오차: ±50px
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from Test_Scenario import (
    OLIVEYOUNG_MAIN_URL,
    SECTION_TITLE,
    EVENT_NAME,
    EVENT_SUBTITLE_TEXT,
    PRODUCT_UI_CHECKLIST,
)

# ── 셀렉터 상수 ───────────────────────────────────────────────────────────
# ※ 실제 DOM 확정 (개발자도구 + HTML 전문 분석)
#
# 섹션 전체 래퍼:
#   <div class="main_plan_banner ty02">
#     <h3 class="main_sub_tit"><strong>인기 행사만 모았어요!</strong></h3>
#     <div class="banner_wrap"> ... </div>
#   </div>

# 섹션 헤더: h3.main_sub_tit (class명 확정)
SEL_SECTION_HEADER   = "h3.main_sub_tit"

# 섹션 전체 래퍼 (슬라이더 포함 영역)
SEL_SECTION_WRAP     = "div.main_plan_banner.ty02"

# 슬라이더 전체 컨테이너
SEL_SLIDER           = "#mainPlanSlider"

# 포차코 카드 식별:
#   data-banner-name="미쟝센X포차코" 확정
SEL_EVENT_CARD       = "a[data-banner-name*='포차코']"

# 행사 배너 이미지:
#   <div class="plan_banner" style="background-image:url(...)">
#   ※ <img> 없음 — CSS background-image 방식
SEL_PLAN_BANNER_DIV  = ".plan_banner"

# 행사 타이틀: <strong class="tit">포차코도 탐낸</strong>
SEL_EVENT_TITLE      = ".plan_banner a strong.tit"

# 행사 서브타이틀: <span class="desc">미쟝센 콜라보 한정판, 품절 전 선점!</span>
SEL_EVENT_SUBTITLE   = ".plan_banner a span.desc"

# 행사 링크 (클릭 대상):
#   href="javascript:common.link.movePlanShop('500000100017555', ...)"
SEL_EVENT_LINK       = ".plan_banner a"

# 상품 래퍼: ul.cate_prd_list > li > div.prd_info
SEL_PRODUCT_WRAP     = "ul.cate_prd_list li div.prd_info"

# 상품 이미지: a.prd_thumb > img (실제 <img> 태그 존재)
SEL_PRODUCT_IMG      = "a.prd_thumb img"

# 상품명: p.tx_name
SEL_PRODUCT_NAME     = "p.tx_name"

# 브랜드명: span.tx_brand
SEL_BRAND_NAME       = "span.tx_brand"

# 태그: p.prd_flag > span.icon_flag
SEL_TAG              = "p.prd_flag span.icon_flag"

# 정가: span.tx_org (취소선+회색 CSS로 적용)
SEL_ORIGINAL_PRICE   = "p.prd_price span.tx_org"

# 할인가: span.tx_cur (붉은색 CSS로 적용)
SEL_DISCOUNT_PRICE   = "p.prd_price span.tx_cur"

TIMEOUT = 15_000  # ms


# ═══════════════════════════════════════════════════════════════════════════
# 헬퍼
# ═══════════════════════════════════════════════════════════════════════════

def _go_main(page: Page) -> None:
    """
    메인 페이지 이동 + 콘텐츠 로드 확인
    ─────────────────────────────────────────────────────────────────────
    봇 감지 차단 시: 페이지는 로드되나 실제 콘텐츠 영역이 비어있음
    → #Container 존재 여부로 정상 로드 판별
    → 이후 점진적 스크롤로 lazy load 트리거 (최대 15회)
    """
    page.goto(OLIVEYOUNG_MAIN_URL, wait_until="domcontentloaded", timeout=30_000)

    # networkidle 대신 실제 콘텐츠 컨테이너 대기 (더 빠르고 신뢰성 높음)
    try:
        page.wait_for_selector("#Container", timeout=15_000)
    except Exception:
        # #Container 없으면 차단 페이지 가능성 — 그래도 진행 (이후 케이스에서 FAIL)
        page.wait_for_timeout(3_000)

    # 점진적 스크롤로 Lazy Load 트리거
    # h3.main_sub_tit 가 attached 될 때까지 반복
    for step in range(15):
        found = page.evaluate(
            "() => !!document.querySelector('h3.main_sub_tit')"
        )
        if found:
            break
        # 뷰포트 1배씩 내려가며 Intersection Observer 트리거
        page.evaluate(f"() => window.scrollBy(0, window.innerHeight)")
        page.wait_for_timeout(300)

    # 스크롤 초기화
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(500)


def _scroll_to_section(page: Page) -> None:
    """
    '인기 행사만 모았어요!' 섹션 스크롤 + slick 초기화 완료 대기
    ─────────────────────────────────────────────────────────────
    1단계: h3.main_sub_tit 스크롤
    2단계: slick-initialized 클래스 확인 (슬라이더 JS 초기화 완료)
    3단계: 포차코 카드(data-banner-name*='포차코') DOM 진입 대기
    """
    # 1단계: 섹션 헤더로 스크롤
    try:
        section = page.locator(SEL_SECTION_HEADER).first
        section.wait_for(state="attached", timeout=15_000)
        section.scroll_into_view_if_needed(timeout=10_000)
    except Exception:
        page.evaluate("""
            () => {
                const el = document.querySelector('div.main_plan_banner.ty02')
                       || document.querySelector('#mainPlanSlider')
                       || document.querySelector('.banner_wrap');
                if (el) el.scrollIntoView({behavior: 'instant', block: 'center'});
            }
        """)

    # 2단계: slick 초기화 완료 대기
    # slick.js는 DOM 삽입 후 JS가 초기화하면서 slick-initialized 클래스 추가
    try:
        page.wait_for_selector(
            "#mainPlanSlider.slick-initialized",
            timeout=10_000,
        )
    except Exception:
        pass  # 이미 초기화된 경우 또는 구조 변경 시 무시

    # 3단계: 포차코 카드가 DOM에 존재할 때까지 대기 (최대 10초)
    try:
        page.wait_for_selector(
            "a[data-banner-name*='포차코']",
            timeout=10_000,
        )
    except Exception:
        pass  # 행사 종료 등으로 포차코 카드 없는 경우 — 이후 케이스에서 FAIL 처리

    page.wait_for_timeout(500)  # 슬라이더 위치 안정화


def _get_pochacho_card(page: Page):
    """
    포차코 행사 카드의 plan_banner > a 로케이터 반환
    ※ count()는 Headless에서 대기 없이 즉시 반환 → JS evaluate로 DOM 직접 확인
    """
    # JS로 DOM 존재 여부 즉시 확인 후 우선순위대로 반환
    selector = page.evaluate("""
        () => {
            // 1순위: slick-current (현재 활성)
            if (document.querySelector(
                '.slider_unit.slick-current a[data-banner-name*="포차코"]'))
                return 'current';
            // 2순위: slick-active (뷰포트 내)
            if (document.querySelector(
                '.slider_unit.slick-active a[data-banner-name*="포차코"]'))
                return 'active';
            // 3순위: cloned 제외 전체
            if (document.querySelector(
                '.slider_unit:not(.slick-cloned) a[data-banner-name*="포차코"]'))
                return 'notcloned';
            return 'any';
        }
    """)

    if selector == 'current':
        return page.locator(
            ".slider_unit.slick-current a[data-banner-name*='포차코']"
        ).first
    if selector == 'active':
        return page.locator(
            ".slider_unit.slick-active a[data-banner-name*='포차코']"
        ).first
    if selector == 'notcloned':
        return page.locator(
            ".slider_unit:not(.slick-cloned) a[data-banner-name*='포차코']"
        ).first
    # 최후 폴백: 모든 포차코 링크 중 첫 번째
    return page.locator("a[data-banner-name*='포차코']").first


def _get_pochacho_slider_unit(page: Page):
    """
    포차코 카드가 속한 slider_unit div 반환 (상품 목록 접근용)
    ※ _get_pochacho_card()와 동일한 우선순위 전략 적용
    """
    selector = page.evaluate("""
        () => {
            if (document.querySelector(
                '.slider_unit.slick-current:has(a[data-banner-name*="포차코"])'))
                return 'current';
            if (document.querySelector(
                '.slider_unit.slick-active:has(a[data-banner-name*="포차코"])'))
                return 'active';
            if (document.querySelector(
                '.slider_unit:not(.slick-cloned):has(a[data-banner-name*="포차코"])'))
                return 'notcloned';
            return 'any';
        }
    """)

    if selector == 'current':
        return page.locator(
            ".slider_unit.slick-current:has(a[data-banner-name*='포차코'])"
        ).first
    if selector == 'active':
        return page.locator(
            ".slider_unit.slick-active:has(a[data-banner-name*='포차코'])"
        ).first
    if selector == 'notcloned':
        return page.locator(
            ".slider_unit:not(.slick-cloned):has(a[data-banner-name*='포차코'])"
        ).first
    return page.locator(
        "div:has(> div.plan_top > div.plan_banner a[data-banner-name*='포차코'])"
    ).first


def _get_scroll_y(page: Page) -> int:
    return int(page.evaluate("() => window.scrollY"))


def _click_and_verify_navigation(
    page: Page,
    clickable_locator,
    expected_url_fragment: str,
) -> int:
    """
    요소 클릭 → URL 변경 확인 → 클릭 전 scrollY 반환
    ※ href="javascript:common.link.movePlanShop(...)" 방식이므로
       expect_navigation 대신 wait_for_url 로 처리
    """
    scroll_before = _get_scroll_y(page)
    clickable_locator.click()
    page.wait_for_url(f"**{expected_url_fragment}**", timeout=15_000)
    assert expected_url_fragment in page.url, (
        f"예상 URL 미포함: '{expected_url_fragment}' ← 실제: {page.url}"
    )
    return scroll_before


def _verify_scroll_restored(page: Page, expected_y: int, tolerance: int = 50) -> None:
    """
    뒤로가기 후 스크롤 위치 검증
    tolerance: 허용 오차 (px) — 기본값 50px
      브라우저 history.scrollRestoration, 모바일 에뮬레이션,
      동적 콘텐츠 로딩 등으로 인해 일반적으로 ±50px 오차 발생 가능
    """
    page.go_back(wait_until="domcontentloaded", timeout=15_000)
    page.wait_for_load_state("networkidle", timeout=10_000)
    actual_y = _get_scroll_y(page)
    assert abs(actual_y - expected_y) <= tolerance, (
        f"스크롤 복원 불일치 — 기대: {expected_y}px / 실제: {actual_y}px "
        f"/ 허용 오차: ±{tolerance}px"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-01: '인기 행사만 모았어요!' 영역 노출 확인
# ═══════════════════════════════════════════════════════════════════════════

class TestTC01SectionVisibility:

    def test_tc01_section_is_visible(self, page: Page):
        """
        TC-01 | '인기 행사만 모았어요!' 섹션 노출 확인
        DOM 확정: <h3 class="main_sub_tit"><strong>인기 행사만 모았어요!</strong></h3>
        → h3.main_sub_tit 노출 + 텍스트 포함 여부 검증
        """
        _go_main(page)
        section = page.locator(SEL_SECTION_HEADER).first
        expect(section).to_be_visible(timeout=TIMEOUT)
        # 텍스트 내용 추가 검증
        text = (section.text_content() or "").strip()
        assert "인기 행사만 모았어요" in text, (
            f"h3.main_sub_tit 텍스트 불일치 — 실제: '{text}'"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-02: '포차코' 행사 노출 및 클릭 동작 확인
# ═══════════════════════════════════════════════════════════════════════════

class TestTC02PochachoEvent:

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """각 TC-02 케이스 실행 전 메인 페이지 → 섹션 스크롤"""
        _go_main(page)
        _scroll_to_section(page)
        self.page        = page
        self.banner_link = _get_pochacho_card(page)    # plan_banner > a
        self.unit        = _get_pochacho_slider_unit(page)  # slider_unit div

    # ── TC-02-1: 배너 이미지 노출 ────────────────────────────────────────
    def test_tc02_1_event_image_visible(self, page: Page):
        """
        TC-02-1 | 포차코 행사 이미지 노출 확인
        ※ DOM 구조: <div class="plan_banner" style="background-image:url(...)">
           <img> 태그 없음 — CSS background-image 방식
           → div.plan_banner 노출 + background-image URL 존재 여부로 검증
        """
        banner_div = self.unit.locator(SEL_PLAN_BANNER_DIV).first
        expect(banner_div).to_be_visible(timeout=TIMEOUT)

        bg_image = banner_div.evaluate(
            "el => getComputedStyle(el).backgroundImage"
        )
        assert bg_image and bg_image != "none", (
            f"plan_banner 배경 이미지 없음: {bg_image}"
        )
        assert "url(" in bg_image, (
            f"background-image URL 형식 아님: {bg_image}"
        )

    # ── TC-02-2: 타이틀 노출 ─────────────────────────────────────────────
    def test_tc02_2_event_title_visible(self, page: Page):
        """
        TC-02-2 | 포차코 행사 타이틀 노출 확인
        DOM: <strong class="tit">포차코도 탐낸</strong>
             <strong class="tit">그 머릿결</strong>  (2줄 분리)
        → 첫 번째 strong.tit 에 EVENT_TITLE_TEXT 포함 여부 검증
        """
        title = self.unit.locator(SEL_EVENT_TITLE).first
        expect(title).to_be_visible(timeout=TIMEOUT)
        text = (title.text_content() or "").strip()
        assert EVENT_TITLE_TEXT in text, (
            f"타이틀에 '{EVENT_TITLE_TEXT}' 텍스트 없음 — 실제: '{text}'"
        )

    # ── TC-02-3: 서브타이틀 노출 ─────────────────────────────────────────
    def test_tc02_3_event_subtitle_visible(self, page: Page):
        """
        TC-02-3 | 포차코 행사 서브타이틀 노출 확인
        DOM: <span class="desc">미쟝센 콜라보 한정판, 품절 전 선점!</span>
        """
        subtitle = self.unit.locator(SEL_EVENT_SUBTITLE).first
        expect(subtitle).to_be_visible(timeout=TIMEOUT)
        text = (subtitle.text_content() or "").strip()
        assert EVENT_SUBTITLE_TEXT in text, (
            f"서브타이틀에 '{EVENT_SUBTITLE_TEXT}' 텍스트 없음 — 실제: '{text}'"
        )

    # ── TC-02-4: 상품 영역 UI 노출 ───────────────────────────────────────
    def test_tc02_4_product_area_visible(self, page: Page):
        """
        TC-02-4 | 포차코 행사 상품 영역 UI 노출 확인 (첫 번째 상품)
        DOM:
          ul.cate_prd_list > li > div.prd_info
            a.prd_thumb > img              ← 상품 이미지 (<img> 실제 존재)
            div.prd_name > a
              span.tx_brand                ← 브랜드명
              p.tx_name                    ← 상품명
            p.prd_price
              span.tx_org > span.tx_num    ← 정가
              span.tx_cur > span.tx_num    ← 할인가
            p.prd_flag > span.icon_flag    ← 태그
        """
        product = self.unit.locator(SEL_PRODUCT_WRAP).first

        checklist_selectors = {
            "product_image":  (SEL_PRODUCT_IMG,      "상품 이미지"),
            "product_name":   (SEL_PRODUCT_NAME,     "상품명"),
            "brand_name":     (SEL_BRAND_NAME,       "브랜드명"),
            "tag":            (SEL_TAG,              "태그"),
            "original_price": (SEL_ORIGINAL_PRICE,   "정가"),
            "discount_price": (SEL_DISCOUNT_PRICE,   "할인가"),
        }

        for key in PRODUCT_UI_CHECKLIST:
            sel, label = checklist_selectors[key]
            elem = product.locator(sel).first
            expect(elem).to_be_visible(timeout=TIMEOUT), f"{label} 미노출"

            # 정가(tx_org): 회색 글씨색 + 취소선 CSS 검증
            if key == "original_price":
                text_deco = elem.evaluate(
                    "el => getComputedStyle(el).textDecorationLine"
                )
                assert "line-through" in text_deco, "정가 취소선 미적용"
                color = elem.evaluate("el => getComputedStyle(el).color")
                _assert_gray_color(color, label="정가")

            # 할인가(tx_cur): 붉은 글씨색 CSS 검증
            if key == "discount_price":
                color = elem.evaluate("el => getComputedStyle(el).color")
                _assert_red_color(color, label="할인가")

    # ── TC-02-5: 타이틀 클릭 → 이벤트 페이지 + 스크롤 복원 ──────────────
    def test_tc02_5_title_click_navigation(self, page: Page):
        """
        TC-02-5 | 포차코 타이틀 클릭 → 이벤트 페이지 이동 + 뒤로가기 스크롤 복원
        DOM: strong.tit 클릭 → 부모 a[href="javascript:movePlanShop(...)"] 동작
        ※ href가 javascript: 방식이므로 plan_banner > a 를 클릭
        이동 URL 패턴: /store/planshop/getPlanShopDetail.do?dispCatNo=500000100017555
        """
        link = self.unit.locator(SEL_EVENT_LINK).first
        scroll_before = _click_and_verify_navigation(
            page, link, expected_url_fragment="planShop"
        )
        _verify_scroll_restored(page, expected_y=scroll_before)

    # ── TC-02-6: 서브타이틀 클릭 → 이벤트 페이지 + 스크롤 복원 ──────────
    def test_tc02_6_subtitle_click_navigation(self, page: Page):
        """
        TC-02-6 | 포차코 서브타이틀 클릭 → 이벤트 페이지 이동 + 뒤로가기 스크롤 복원
        DOM: span.desc 클릭 → 부모 a 동작 (타이틀과 동일한 링크)
        """
        link = self.unit.locator(SEL_EVENT_LINK).first
        scroll_before = _click_and_verify_navigation(
            page, link, expected_url_fragment="planShop"
        )
        _verify_scroll_restored(page, expected_y=scroll_before)

    # ── TC-02-7: 상품 이미지 클릭 → 상품상세 + 스크롤 복원 ──────────────
    def test_tc02_7_product_image_click(self, page: Page):
        """
        TC-02-7 | 포차코 상품이미지 클릭 → 상품상세 이동 + 뒤로가기 스크롤 복원
        DOM: a.prd_thumb[href="...getGoodsDetail.do?goodsNo=..."] > img
        → a.prd_thumb 클릭 (img는 a 내부)
        """
        product   = self.unit.locator(SEL_PRODUCT_WRAP).first
        prd_thumb = product.locator("a.prd_thumb").first
        scroll_before = _click_and_verify_navigation(
            page, prd_thumb, expected_url_fragment="getGoodsDetail"
        )
        _verify_scroll_restored(page, expected_y=scroll_before)

    # ── TC-02-8: 상품명 클릭 → 상품상세 + 스크롤 복원 ───────────────────
    def test_tc02_8_product_name_click(self, page: Page):
        """
        TC-02-8 | 포차코 상품명 클릭 → 상품상세 이동 + 뒤로가기 스크롤 복원
        DOM: div.prd_name > a[href="...getGoodsDetail.do?goodsNo=..."] > p.tx_name
        → div.prd_name > a 클릭
        """
        product      = self.unit.locator(SEL_PRODUCT_WRAP).first
        name_link    = product.locator("div.prd_name a").first
        scroll_before = _click_and_verify_navigation(
            page, name_link, expected_url_fragment="getGoodsDetail"
        )
        _verify_scroll_restored(page, expected_y=scroll_before)

    # ── TC-02-9: 브랜드명 클릭 → 상품상세 + 스크롤 복원 ─────────────────
    def test_tc02_9_brand_name_click(self, page: Page):
        """
        TC-02-9 | 포차코 브랜드명 클릭 → 상품상세 이동 + 뒤로가기 스크롤 복원
        DOM: div.prd_name > a > span.tx_brand ("미쟝센")
             span.tx_brand 는 a 내부에 있어 a 클릭으로 동일하게 처리
        ※ 브랜드명 단독 링크가 없으므로 부모 a (prd_name > a) 클릭
        """
        product      = self.unit.locator(SEL_PRODUCT_WRAP).first
        brand_link   = product.locator("div.prd_name a").first
        scroll_before = _click_and_verify_navigation(
            page, brand_link, expected_url_fragment="getGoodsDetail"
        )
        _verify_scroll_restored(page, expected_y=scroll_before)


# ═══════════════════════════════════════════════════════════════════════════
# CSS 색상 검증 헬퍼
# ═══════════════════════════════════════════════════════════════════════════

def _parse_rgb(color_str: str) -> tuple[int, int, int]:
    """
    'rgb(R, G, B)' 또는 'rgba(R, G, B, A)' → (R, G, B)
    파싱 실패 시 AssertionError
    """
    import re
    m = re.search(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color_str)
    assert m, f"색상 파싱 불가: {color_str}"
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _assert_gray_color(color_str: str, label: str = "") -> None:
    """
    회색 판별 기준:
      - R, G, B 채널의 최대-최소 차이 ≤ 30 (채도 낮음)
      - 밝기(평균) ≤ 180 (너무 흰색 아님)
    올리브영 정가 색상 #999, #aaa 계열 대응
    """
    r, g, b = _parse_rgb(color_str)
    diff    = max(r, g, b) - min(r, g, b)
    bright  = (r + g + b) / 3
    assert diff <= 30,  f"{label} 회색 채도 초과 (diff={diff}): {color_str}"
    assert bright <= 180, f"{label} 색상이 너무 밝음 (avg={bright:.0f}): {color_str}"


def _assert_red_color(color_str: str, label: str = "") -> None:
    """
    붉은색 판별 기준:
      - R 채널이 G, B 보다 유의미하게 높음 (R - max(G,B) ≥ 60)
    올리브영 할인가 색상 #f00, #e8000d 계열 대응
    """
    r, g, b = _parse_rgb(color_str)
    assert r - max(g, b) >= 60, (
        f"{label} 붉은색 아님 — RGB({r},{g},{b}): {color_str}"
    )