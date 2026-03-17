"""
Test_Case_event_pg.py
─────────────────────────────────────────────────────────────────────────────
대상: '빛나는 머릿결에 포차코도 GET!' 이벤트 페이지
케이스:
  TC-03-1    이벤트 이미지 노출 확인
  TC-03-2    기획전 상세 섹션바 노출 확인
  TC-03-2-1  섹션바 각 섹션 클릭 시 섹션 페이지 갱신 확인
  TC-03-2-2  섹션 상품 UI 확인 (첫 번째 상품 기준)

이벤트 페이지 URL:
  메인 페이지 포차코 카드 → 타이틀 클릭으로 동적 획득
  (하드코딩 대신 동적 획득 → URL 변경에 강건)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from Test_Scenario import (
    OLIVEYOUNG_MAIN_URL,
    SECTION_TITLE,
    EVENT_NAME,
    EVENT_PAGE_TITLE,
    PRODUCT_UI_CHECKLIST,
)
from Test_Case_main_pg import (
    _go_main,
    _scroll_to_section,
    _get_pochacho_slider_unit,
    _assert_gray_color,
    _assert_red_color,
    SEL_EVENT_LINK,
    SEL_PRODUCT_WRAP,
    SEL_PRODUCT_IMG,
    SEL_PRODUCT_NAME,
    SEL_BRAND_NAME,
    SEL_TAG,
    SEL_ORIGINAL_PRICE,
    SEL_DISCOUNT_PRICE,
)

# ── 이벤트 페이지 셀렉터 (DOM 확정) ──────────────────────────────────────
# ※ 실제 기획전 상세 페이지 HTML 분석 기반

# 이벤트 타이틀: <h1 id="planTitle">빛나는 머릿결에 포차코도 GET!</h1>
SEL_EVENT_PAGE_TITLE = "h1#planTitle"

# 이벤트 대표 이미지:
#   <div class="plan-visual contEditor newPc">
#     <div class="new-pc-img-wrapper"><img src="..."></div>
SEL_EVENT_PAGE_IMG   = "div.plan-visual.newPc div.new-pc-img-wrapper img"

# 섹션바:
#   <ul class="plan-menu" id="move1">
#     <li><a href="javascript:;" data-ref-dispcatno="">전체</a></li>
#     <li><a href="javascript:;" data-ref-dispcatno="5000001000175550001">...</a></li>
SEL_SECTION_BAR      = "ul.plan-menu#move1"

# 개별 섹션 탭 아이템 (전체 포함)
SEL_SECTION_ITEM     = "ul.plan-menu#move1 li"

# 섹션 콘텐츠 — 상품 목록
#   <ul class="cate_prd_list autoFull">
SEL_SECTION_CONTENT  = "ul.cate_prd_list.autoFull"

# 섹션 헤더 (앵커 타깃):
#   <p id="5000001000175550001" class="plan-link tema section section">
SEL_SECTION_HEADER_P = "p.plan-link.section"

TIMEOUT = 15_000  # ms


# ═══════════════════════════════════════════════════════════════════════════
# 픽스처: 이벤트 페이지 진입
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="class")
def event_page(context):
    """
    메인 → 포차코 슬라이드 plan_banner a 클릭 → 이벤트(기획전) 페이지 진입
    DOM: href="javascript:common.link.movePlanShop('500000100017555', ...)"
    이동 URL: /store/planshop/getPlanShopDetail.do?dispCatNo=500000100017555
    """
    pg = context.new_page()

    _go_main(pg)
    _scroll_to_section(pg)

    unit = _get_pochacho_slider_unit(pg)
    link = unit.locator(SEL_EVENT_LINK).first

    # javascript: href 방식 → wait_for_url 사용
    link.click()
    pg.wait_for_url("**/planshop/**", timeout=15_000)
    pg.wait_for_load_state("networkidle", timeout=15_000)

    event_url = pg.url
    assert "planshop" in event_url or "planShop" in event_url, (
        f"기획전 페이지 URL 아님: {event_url}"
    )
    assert EVENT_PLANSHOP_NO in event_url, (
        f"포차코 기획전 번호({EVENT_PLANSHOP_NO}) URL 미포함: {event_url}"
    )

    yield pg
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# TC-03: 이벤트 페이지 검증
# ═══════════════════════════════════════════════════════════════════════════

class TestTC03EventPage:

    # ── TC-03-1: 이벤트 이미지 노출 ──────────────────────────────────────
    def test_tc03_1_event_image_visible(self, event_page: Page):
        """
        TC-03-1 | 이벤트 대표 이미지 노출 확인
        DOM: div.plan-visual.newPc > div.new-pc-img-wrapper > img
        """
        img = event_page.locator(SEL_EVENT_PAGE_IMG).first
        expect(img).to_be_visible(timeout=TIMEOUT)
        src = img.get_attribute("src")
        assert src and src.strip(), "이벤트 이미지 src 속성이 비어있음"

    # ── TC-03-2: 섹션바 노출 ─────────────────────────────────────────────
    def test_tc03_2_section_bar_visible(self, event_page: Page):
        """
        TC-03-2 | 기획전 상세 섹션바(ul.plan-menu#move1) 노출 확인
        DOM: <ul class="plan-menu" id="move1">
               <li><a>전체</a></li>           ← data-ref-dispcatno="" (전체)
               <li><a>포차코 파우치/...</a></li>  ← 섹션1
               <li><a>미쟝센 BEST 더보기</a></li> ← 섹션2
               <li><a>인기BEST 미쟝센 염모제</a></li> ← 섹션3
        총 4개 (전체 포함)
        """
        section_bar = event_page.locator(SEL_SECTION_BAR).first
        expect(section_bar).to_be_visible(timeout=TIMEOUT)

        count = event_page.locator(SEL_SECTION_ITEM).count()
        # 전체 탭 포함 최소 2개 이상 (실제 확인: 4개)
        assert count >= 2, f"섹션 탭 수 부족: {count}개"

    # ── TC-03-2-1: 섹션 클릭 → 콘텐츠 갱신 ──────────────────────────────
    def test_tc03_2_1_section_click_updates_content(self, event_page: Page):
        """
        TC-03-2-1 | 섹션바 각 탭 클릭 시 뷰포트 내 섹션 헤더 갱신 확인
        DOM 동작 방식:
          - 이 페이지는 SPA/탭 전환이 아닌 페이지 내 앵커 스크롤 방식
          - 탭 클릭 → 해당 p.plan-link.section 위치로 스크롤
          - 콘텐츠 자체는 항상 DOM에 존재 (숨김/표시 전환 없음)
          - 검증: 탭 클릭 후 해당 섹션 헤더가 뷰포트 내 진입했는지 확인
        ※ '전체' 탭(data-ref-dispcatno="")은 최상단 스크롤이므로 별도 처리
        """
        tabs  = event_page.locator(SEL_SECTION_ITEM)
        count = tabs.count()
        assert count >= 2, f"섹션 탭 수 부족: {count}개"

        # 섹션 헤더 p 요소 목록 (전체 제외한 개별 섹션용)
        section_headers = event_page.locator(SEL_SECTION_HEADER_P)

        for i in range(count):
            tab = tabs.nth(i)
            tab.scroll_into_view_if_needed(timeout=TIMEOUT)

            tab_dispcatno = tab.locator("a").get_attribute("data-ref-dispcatno") or ""
            tab.locator("a").click()
            event_page.wait_for_timeout(800)  # 스크롤 애니메이션 대기

            if tab_dispcatno == "":
                # '전체' 탭: 페이지 최상단으로 스크롤 → scrollY ≈ 0 확인
                scroll_y = int(event_page.evaluate("() => window.scrollY"))
                assert scroll_y <= 200, (
                    f"'전체' 탭 클릭 후 최상단 미이동 — scrollY: {scroll_y}px"
                )
            else:
                # 개별 섹션 탭: 해당 섹션 헤더 p[id=dispcatno] 가 뷰포트 근처로 스크롤
                target_id = tab_dispcatno
                target_section = event_page.locator(f"p#{target_id}")
                # 섹션이 뷰포트 기준 위 또는 근처에 있는지 확인
                # bounding_box top이 viewport height 이하이면 스크롤된 것으로 판단
                viewport_h = event_page.viewport_size["height"]
                bbox = target_section.bounding_box()
                assert bbox is not None, f"섹션 {target_id} bounding_box 없음"
                # 섹션 헤더 top이 viewport 기준 2배 이내에 위치 (느슨한 기준)
                assert bbox["y"] <= viewport_h * 2, (
                    f"섹션 탭 클릭 후 대상 섹션({target_id}) 미스크롤 "
                    f"— y: {bbox['y']}px, viewport: {viewport_h}px"
                )

    # ── TC-03-2-2: 섹션 상품 UI 확인 ─────────────────────────────────────
    def test_tc03_2_2_product_ui_in_section(self, event_page: Page):
        """
        TC-03-2-2 | 섹션별 첫 번째 상품 UI 확인 (전체 섹션 기준)
        DOM: p.plan-link.section 별로 ul.cate_prd_list.autoFull 연속 배치

        ⚠️ 정가(tx_org) 없는 상품 존재 (섹션2, 섹션3 일부)
           예: <p class="prd_price"><span class="tx_cur">17,900원</span></p>
           → tx_org 미노출 시 정가/취소선 검증 스킵 (비정상 아님, 정가 == 할인가 케이스)
        """
        # 섹션 헤더(p.plan-link.section) 기준으로 각 섹션의 첫 상품 검증
        section_headers = event_page.locator(SEL_SECTION_HEADER_P)
        section_count   = section_headers.count()
        assert section_count >= 1, "섹션 헤더(p.plan-link.section) 없음"

        checklist_selectors = {
            "product_image":  (SEL_PRODUCT_IMG,      "상품 이미지"),
            "product_name":   (SEL_PRODUCT_NAME,     "상품명"),
            "brand_name":     (SEL_BRAND_NAME,       "브랜드명"),
            "tag":            (SEL_TAG,              "태그"),
            "original_price": (SEL_ORIGINAL_PRICE,   "정가"),
            "discount_price": (SEL_DISCOUNT_PRICE,   "할인가"),
        }

        for i in range(section_count):
            header = section_headers.nth(i)
            section_id = header.get_attribute("id") or f"section_{i}"

            # 헤더 다음의 첫 번째 ul.cate_prd_list.autoFull 탐색
            # DOM: p.plan-link.section → (형제 div) → ul.cate_prd_list.autoFull
            product_list = event_page.locator(
                f"p#{section_id} ~ div ul.cate_prd_list.autoFull"
            ).first
            # fallback: 섹션 헤더 이후 전체 기준
            if product_list.count() == 0:
                product_list = event_page.locator(SEL_SECTION_CONTENT).nth(i)

            product = product_list.locator("li div.prd_info").first
            expect(product).to_be_visible(timeout=TIMEOUT)

            for key in PRODUCT_UI_CHECKLIST:
                sel, label = checklist_selectors[key]
                elem = product.locator(sel).first

                # ── 정가(tx_org): 없는 상품이 존재하므로 존재 여부 먼저 확인 ──
                if key == "original_price":
                    if elem.count() == 0:
                        # 정가 요소 없음 = 할인 없는 상품 → 검증 스킵
                        print(
                            f"[섹션 {i+1} ({section_id})] "
                            f"정가(tx_org) 없음 — 취소선 검증 스킵"
                        )
                        continue
                    expect(elem).to_be_visible(timeout=TIMEOUT), (
                        f"[섹션 {i+1}] {label} 미노출"
                    )
                    text_deco = elem.evaluate(
                        "el => getComputedStyle(el).textDecorationLine"
                    )
                    assert "line-through" in text_deco, (
                        f"[섹션 {i+1} ({section_id})] 정가 취소선 미적용"
                    )
                    color = elem.evaluate("el => getComputedStyle(el).color")
                    _assert_gray_color(color, label=f"[섹션 {i+1}] 정가")

                # ── 할인가(tx_cur): 항상 존재 ────────────────────────────────
                elif key == "discount_price":
                    expect(elem).to_be_visible(timeout=TIMEOUT), (
                        f"[섹션 {i+1}] {label} 미노출"
                    )
                    color = elem.evaluate("el => getComputedStyle(el).color")
                    _assert_red_color(color, label=f"[섹션 {i+1}] 할인가")

                # ── 나머지 항목 ───────────────────────────────────────────────
                else:
                    expect(elem).to_be_visible(timeout=TIMEOUT), (
                        f"[섹션 {i+1}] {label} 미노출"
                    )
