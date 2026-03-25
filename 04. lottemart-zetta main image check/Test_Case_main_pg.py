"""
롯데마트 제타 메인 페이지 상품 노출 상세 검증.

요구 반영:
  - 상품 이미지
  - 상품명
  - 상품금액
  - 행사 여부
  - 행사 종류 분류 (n+n, n개 담기 시 할인, 상품할인, 금액조건 할인)
  - 할인행사의 원 상품가/행사상품가 구분
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from playwright.sync_api import Page, expect

from Test_Scenario import (
    LOTTE_ZETTA_MAIN_URL,
    MIN_PRODUCT_CARD_COUNT,
    PRODUCT_SECTION_TITLE,
    PROMOTION_TYPES,
    WELCOME_TITLE,
)


TIMEOUT_MS = 20_000

# 금액 토큰: 1,000원 / 25900원 형태 모두 허용
PRICE_RE = re.compile(r"\d{1,3}(?:,\d{3})*원|\d{4,}원")
# 퍼센트 할인 표기
PERCENT_DISCOUNT_RE = re.compile(r"\d{1,2}\s*%\s*할인")
# n+n 표기
N_PLUS_N_RE = re.compile(r"\b\d+\s*\+\s*\d+\b")
# n개 담기/구매 시 할인 표기
COUNT_CONDITION_RE = re.compile(r"\d+\s*개\s*(?:담기|구매)\s*시")
# 금액 조건 할인 표기
AMOUNT_CONDITION_RE = re.compile(r"(?:\d+\s*만원?\s*이상|[0-9,]+\s*원\s*이상).*(?:할인|최대)")


def _go_main(page: Page) -> None:
    """
    메인 진입 + 초기 렌더링 대기.
    운영환경 배너/캐러셀은 lazy load가 많아 짧은 안정화 시간을 둔다.
    """
    page.goto(LOTTE_ZETTA_MAIN_URL, wait_until="domcontentloaded", timeout=40_000)
    page.wait_for_timeout(2_000)


def _scroll_until_text_visible(page: Page, text: str, max_steps: int = 20) -> None:
    """
    모바일 에뮬레이션에서 lazy loading 트리거를 위해 단계 스크롤을 사용한다.
    """
    for _ in range(max_steps):
        found = page.evaluate("(t) => document.body.innerText.includes(t)", text)
        if found:
            return
        page.evaluate("() => window.scrollBy(0, Math.floor(window.innerHeight * 0.9))")
        page.wait_for_timeout(300)


def _extract_product_cards(page: Page, section_title: str) -> list[dict]:
    """
    특정 섹션 아래에서 상품 카드 메타데이터를 수집한다.

    수집 필드:
      - href: 카드 링크
      - title_text: 카드 노출 텍스트(상품명/행사문구)
      - image_alt: 이미지 alt
      - image_src: 이미지 src
      - text_blob: 분류/가격 추출용 통합 텍스트
    """
    return page.evaluate(
        """
        (sectionTitle) => {
          const normalize = (v) => (v || "").replace(/\\s+/g, " ").trim();
          const headingCandidates = [...document.querySelectorAll("h1,h2,h3,h4")];
          const heading = headingCandidates.find((h) =>
            normalize(h.textContent).includes(normalize(sectionTitle))
          );
          if (!heading) return [];

          // 섹션 컨테이너를 탐색하며 상품 링크(/products/*/details) 비중이 높은 곳을 선택.
          let container = heading.closest("section,article,div");
          let walker = container;
          for (let i = 0; i < 6 && walker; i += 1) {
            const productLinks = walker.querySelectorAll('a[href*="/products/"][href*="/details"]').length;
            if (productLinks >= 3) {
              container = walker;
              break;
            }
            walker = walker.parentElement;
          }
          container = container || heading.parentElement || document.body;

          const anchors = [...container.querySelectorAll('a[href*="/products/"][href*="/details"]')];
          const cards = anchors.map((a) => {
            const img = a.querySelector("img");
            const titleNode = a.querySelector("span, p, h3, h4") || a;
            const titleText = normalize(titleNode.textContent);
            const imageAlt = normalize(img ? img.getAttribute("alt") || "" : "");
            const imageSrc = img ? (img.getAttribute("src") || "") : "";
            const ariaLabel = normalize(a.getAttribute("aria-label") || "");
            const textBlob = normalize([titleText, imageAlt, ariaLabel].join(" | "));
            return {
              href: a.getAttribute("href") || "",
              title_text: titleText,
              image_alt: imageAlt,
              image_src: imageSrc,
              text_blob: textBlob,
            };
          });

          // 동일 href 중복 제거
          const dedup = [];
          const seen = new Set();
          for (const card of cards) {
            if (!card.href || seen.has(card.href)) continue;
            seen.add(card.href);
            dedup.push(card);
          }
          return dedup;
        }
        """,
        section_title,
    )


def _classify_promotion(text_blob: str) -> str | None:
    """
    요청된 4개 행사 유형으로 분류한다.
    우선순위가 높은 규칙부터 매칭해 중복 분류를 방지한다.
    """
    normalized = re.sub(r"\s+", " ", text_blob or "").strip()
    if not normalized:
        return None

    if N_PLUS_N_RE.search(normalized):
        return "n+n"
    if COUNT_CONDITION_RE.search(normalized):
        return "n개 담기 시 할인"
    if AMOUNT_CONDITION_RE.search(normalized):
        return "금액조건 할인"
    if PERCENT_DISCOUNT_RE.search(normalized) or "할인" in normalized:
        return "상품할인"
    return None


def _extract_prices(text_blob: str) -> list[int]:
    """
    텍스트에서 가격 토큰을 추출해 정수 원 단위 리스트로 반환한다.
    """
    prices = []
    for token in PRICE_RE.findall(text_blob or ""):
        digits = re.sub(r"[^\d]", "", token)
        if digits:
            prices.append(int(digits))
    return prices


class TestLotteMartZettaMainProductValidation:
    def test_tc01_welcome_area_visible(self, page: Page):
        """
        TC-01:
          - 환영 헤드라인 + 로그인 링크 노출
        """
        _go_main(page)
        expect(page.get_by_role("heading", name=WELCOME_TITLE)).to_be_visible(timeout=TIMEOUT_MS)
        expect(page.get_by_role("link", name="로그인").first).to_be_visible(timeout=TIMEOUT_MS)

    def test_tc02_product_area_fields_visible(self, page: Page):
        """
        TC-02:
          상품 노출 영역에서 아래 필드 검증
          - 상품 이미지
          - 상품명
          - 상품금액
          - 행사 여부(행사 유형 4종 중 하나로 분류 가능)
        """
        _go_main(page)
        _scroll_until_text_visible(page, PRODUCT_SECTION_TITLE)
        cards = _extract_product_cards(page, PRODUCT_SECTION_TITLE)

        assert len(cards) >= MIN_PRODUCT_CARD_COUNT, (
            f"상품 카드 수 부족: 기대 >= {MIN_PRODUCT_CARD_COUNT}, 실제={len(cards)}"
        )

        inspected = 0
        for card in cards:
            full_href = urljoin(LOTTE_ZETTA_MAIN_URL, card["href"])
            text_blob = card["text_blob"]
            prices = _extract_prices(text_blob)
            promo_type = _classify_promotion(text_blob)

            # 이미지 검증: src가 있거나 alt가 존재해야 한다.
            assert (card["image_src"] or card["image_alt"]), (
                f"상품 이미지 정보 누락: href={full_href}"
            )
            # 상품명 검증: title 텍스트 최소 길이 2자
            assert len((card["title_text"] or "").strip()) >= 2, (
                f"상품명 누락: href={full_href}"
            )
            # 상품금액 검증: 카드 텍스트/alt 중 최소 1개 가격 토큰
            assert len(prices) >= 1, (
                f"상품금액 누락: href={full_href} | text='{text_blob}'"
            )
            # 행사 여부/종류 검증: 4종 중 하나로 분류 가능해야 함
            assert promo_type in PROMOTION_TYPES, (
                f"행사유형 분류 실패: href={full_href} | text='{text_blob}'"
            )
            inspected += 1

        assert inspected >= MIN_PRODUCT_CARD_COUNT

    def test_tc03_promotion_type_grouping(self, page: Page):
        """
        TC-03:
          행사 유형을 요청된 4개 그룹으로 분류했을 때
          - 최소 2개 이상 유형이 실제 카드에서 확인되는지 검증
          - 전체 분류 결과가 허용된 그룹 목록 안에 있는지 검증
        """
        _go_main(page)
        _scroll_until_text_visible(page, PRODUCT_SECTION_TITLE)
        cards = _extract_product_cards(page, PRODUCT_SECTION_TITLE)

        seen_types: set[str] = set()
        for card in cards:
            promo_type = _classify_promotion(card["text_blob"])
            if promo_type:
                seen_types.add(promo_type)

        assert seen_types, "행사 유형을 하나도 식별하지 못했습니다."
        assert seen_types.issubset(set(PROMOTION_TYPES)), (
            f"허용되지 않은 행사 유형 감지: {seen_types - set(PROMOTION_TYPES)}"
        )
        # 운영상품 변경을 고려해 모든 유형 강제 대신 최소 2개 유형 노출을 기준으로 둔다.
        assert len(seen_types) >= 2, f"행사 유형 다양성 부족: 감지 유형={sorted(seen_types)}"

    def test_tc04_discount_price_distinction(self, page: Page):
        """
        TC-04:
          할인행사의 원 상품가/행사상품가 구분 검증.

        검증 방식:
          1) 메인 카드에서 할인 행사 카드 후보 추출
          2) 해당 상품 상세 페이지로 이동
          3) 본문 텍스트에서 가격 토큰 2개 이상(서로 다른 값) 확인
             -> 원가/행사가 구분 노출로 판단
        """
        _go_main(page)
        _scroll_until_text_visible(page, PRODUCT_SECTION_TITLE)
        cards = _extract_product_cards(page, PRODUCT_SECTION_TITLE)

        discount_candidates = []
        for card in cards:
            promo_type = _classify_promotion(card["text_blob"])
            if promo_type in PROMOTION_TYPES:
                discount_candidates.append(card)

        assert discount_candidates, "할인행사 카드 후보를 찾지 못했습니다."

        success_cases = 0
        checked_samples: list[str] = []
        for card in discount_candidates[:5]:
            product_url = urljoin(LOTTE_ZETTA_MAIN_URL, card["href"])
            checked_samples.append(product_url)

            page.goto(product_url, wait_until="domcontentloaded", timeout=40_000)
            page.wait_for_timeout(2_500)

            # 상세 페이지 본문에서 가격 토큰 수집
            detail_text = page.evaluate(
                """
                () => {
                  const main = document.querySelector("main") || document.body;
                  return (main.innerText || "").replace(/\\s+/g, " ").trim();
                }
                """
            )
            price_values = _extract_prices(detail_text)
            unique_prices = sorted(set(price_values))

            # 원가/행사가 구분은 최소 2개 이상의 서로 다른 가격으로 판단
            if len(unique_prices) >= 2 and unique_prices[0] < unique_prices[-1]:
                success_cases += 1
                break

        assert success_cases >= 1, (
            "할인행사에서 원가/행사가 구분(서로 다른 2개 가격)을 확인하지 못했습니다. "
            f"확인 URL 샘플={checked_samples}"
        )
