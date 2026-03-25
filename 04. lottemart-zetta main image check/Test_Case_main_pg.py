"""
롯데마트 제타 메인 페이지 상품/행사 노출 상세 검증.

요구 반영:
  - 상품: 상품명/상품코드/상품금액/할인금액/이미지 노출
  - 행사 배너: 행사명/행사이미지 노출
  - 행사 유형 분류: n+n, n개 담기 시 할인, 상품할인, 금액조건 할인
  - 최종 집계: 확인된 상품/행사 수를 결과에 반영
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from playwright.sync_api import Page, expect

from reporter import record_banner, record_product
from Test_Scenario import (
    BANNER_SECTION_TITLES,
    LOTTE_ZETTA_MAIN_URL,
    MAX_BANNER_LOG_COUNT,
    MAX_PRODUCT_LOG_COUNT,
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
# 카드 조건 할인(행사카드/카드 결제 시/청구할인 등)
CARD_CONDITION_RE = re.compile(
    r"(?:행사\s*카드|카드\s*결제\s*시|카드결제\s*시|카드\s*할인|청구\s*할인|즉시\s*할인)"
)
# 행사 신호 키워드: 신호가 있으면 행사 유형 분류를 강제한다.
PROMOTION_SIGNAL_RE = re.compile(
    r"(?:\+|할인|행사|증정|쿠폰|카드|구매\s*시|담기\s*시|이상\s*최대)"
)

PRODUCT_CODE_RE = re.compile(r"/products/([^/]+)/details")

# 상세 가격 조회 캐시 (동일 상품 재요청 최소화)
_DETAIL_PRICE_CACHE: dict[str, dict] = {}


def _go_main(page: Page) -> None:
    """메인 진입 + 초기 렌더링 대기."""
    page.goto(LOTTE_ZETTA_MAIN_URL, wait_until="domcontentloaded", timeout=40_000)
    page.wait_for_timeout(2_000)


def _scroll_until_text_visible(page: Page, text: str, max_steps: int = 20) -> None:
    """모바일 에뮬레이션에서 lazy loading 트리거를 위해 단계 스크롤을 사용한다."""
    for _ in range(max_steps):
        found = page.evaluate("(t) => document.body.innerText.includes(t)", text)
        if found:
            return
        page.evaluate("() => window.scrollBy(0, Math.floor(window.innerHeight * 0.9))")
        page.wait_for_timeout(300)


def _extract_section_cards(page: Page, section_title: str) -> list[dict]:
    """
    특정 섹션 내 anchor 기반 카드(상품/배너)를 수집한다.
    """
    return page.evaluate(
        """
        (sectionTitle) => {
          const normalize = (v) => (v || "").replace(/\s+/g, " ").trim();
          const headings = [...document.querySelectorAll("h1,h2,h3,h4")];
          const heading = headings.find((h) =>
            normalize(h.textContent).includes(normalize(sectionTitle))
          );
          if (!heading) return [];

          let container = heading.closest("section,article,div") || heading.parentElement || document.body;
          let walker = container;
          for (let i = 0; i < 6 && walker; i += 1) {
            const candidateCards = walker.querySelectorAll("a").length;
            if (candidateCards >= 5) {
              container = walker;
              break;
            }
            walker = walker.parentElement;
          }

          const anchors = [...container.querySelectorAll("a")];
          const cards = anchors
            .map((a) => {
              const img = a.querySelector("img");
              const titleNode = a.querySelector("span, p, h3, h4") || a;
              const titleText = normalize(titleNode.textContent);
              const imageAlt = normalize(img ? img.getAttribute("alt") || "" : "");
              const imageSrc = img ? (img.getAttribute("src") || "") : "";
              const href = a.getAttribute("href") || "";
              const ariaLabel = normalize(a.getAttribute("aria-label") || "");
              const textBlob = normalize([titleText, imageAlt, ariaLabel].join(" | "));
              const hasVisualSignal = Boolean(img) || titleText.length >= 2 || imageAlt.length >= 2;
              return {
                href,
                title_text: titleText,
                image_alt: imageAlt,
                image_src: imageSrc,
                text_blob: textBlob,
                has_visual_signal: hasVisualSignal,
              };
            })
            .filter((x) => x.has_visual_signal);

          const dedup = [];
          const seen = new Set();
          for (const card of cards) {
            const key = `${card.href}|${card.title_text}|${card.image_alt}`;
            if (seen.has(key)) continue;
            seen.add(key);
            dedup.push(card);
          }
          return dedup;
        }
        """,
        section_title,
    )


def _extract_prices(text_blob: str) -> list[int]:
    """텍스트에서 가격 토큰을 추출해 정수 원 단위 리스트로 반환한다."""
    prices = []
    for token in PRICE_RE.findall(text_blob or ""):
        digits = re.sub(r"[^\d]", "", token)
        if digits:
            prices.append(int(digits))
    return prices


def _is_product_card(href: str) -> bool:
    return "/products/" in (href or "") and "/details" in (href or "")


def _extract_product_code(href: str) -> str:
    match = PRODUCT_CODE_RE.search(href or "")
    return match.group(1) if match else "UNKNOWN"


def _classify_promotion(text_blob: str) -> str | None:
    """요청된 4개 행사 유형으로 분류한다."""
    normalized = re.sub(r"\s+", " ", text_blob or "").strip()
    if not normalized:
        return None

    if N_PLUS_N_RE.search(normalized):
        return "n+n"
    if COUNT_CONDITION_RE.search(normalized):
        return "n개 담기 시 할인"
    if AMOUNT_CONDITION_RE.search(normalized):
        return "금액조건 할인"
    if CARD_CONDITION_RE.search(normalized):
        return "금액조건 할인"
    if PERCENT_DISCOUNT_RE.search(normalized) or "할인" in normalized:
        return "상품할인"
    return None


def _has_promotion_signal(text_blob: str) -> bool:
    normalized = re.sub(r"\s+", " ", text_blob or "").strip()
    return bool(PROMOTION_SIGNAL_RE.search(normalized))


def _fetch_detail_price_info(page: Page, product_url: str) -> dict:
    """
    상품 상세 페이지에서 가격 정보를 수집한다.
    반환:
      {
        "sale_price": int|None,
        "original_price": int|None,
        "discount_amount": int|None,
      }
    """
    if product_url in _DETAIL_PRICE_CACHE:
        return _DETAIL_PRICE_CACHE[product_url]

    result = {
        "sale_price": None,
        "original_price": None,
        "discount_amount": None,
    }

    try:
        page.goto(product_url, wait_until="domcontentloaded", timeout=40_000)
        page.wait_for_timeout(2_000)
        detail_text = page.evaluate(
            """
            () => {
              const main = document.querySelector("main") || document.body;
              return (main.innerText || "").replace(/\s+/g, " ").trim();
            }
            """
        )
        prices = sorted(set(_extract_prices(detail_text)))
        if prices:
            result["sale_price"] = prices[0]
            if len(prices) >= 2:
                result["original_price"] = prices[-1]
                result["discount_amount"] = prices[-1] - prices[0]
            else:
                result["original_price"] = None
                result["discount_amount"] = 0
    except Exception:
        # 상세 페이지가 일시적으로 열리지 않아도 TC 자체가 전부 실패하지 않도록 완화
        pass

    _DETAIL_PRICE_CACHE[product_url] = result
    return result


def _fallback_price_from_card(text_blob: str) -> int | None:
    prices = sorted(set(_extract_prices(text_blob)))
    if not prices:
        return None
    return prices[0]


class TestLotteMartZettaMainProductValidation:
    def test_tc01_welcome_area_visible(self, page: Page):
        """TC-01: 환영 헤드라인 + 로그인 링크 노출"""
        _go_main(page)
        expect(page.get_by_role("heading", name=WELCOME_TITLE)).to_be_visible(timeout=TIMEOUT_MS)
        expect(page.get_by_role("link", name="로그인").first).to_be_visible(timeout=TIMEOUT_MS)

    def test_tc02_product_area_fields_visible(self, page: Page):
        """
        TC-02:
          상품 노출 영역에서 아래 필드 검증 + 상세 로그 기록
          - 상품 이미지
          - 상품명
          - 상품코드
          - 상품금액
          - 할인금액
          - 행사 신호 카드의 행사 유형 분류
        """
        _go_main(page)
        _scroll_until_text_visible(page, PRODUCT_SECTION_TITLE)

        cards = _extract_section_cards(page, PRODUCT_SECTION_TITLE)
        product_cards = [c for c in cards if _is_product_card(c["href"])]

        assert len(product_cards) >= MIN_PRODUCT_CARD_COUNT, (
            f"상품 카드 수 부족: 기대 >= {MIN_PRODUCT_CARD_COUNT}, 실제={len(product_cards)}"
        )

        inspected = 0
        promotion_signal_count = 0
        classified_promotion_count = 0

        # 수행 시간/안정성을 위해 상위 N개 중심으로 상세 기록
        target_cards = product_cards[:MAX_PRODUCT_LOG_COUNT]

        for idx, card in enumerate(target_cards):
            full_href = urljoin(LOTTE_ZETTA_MAIN_URL, card["href"])
            text_blob = card["text_blob"]
            promo_type = _classify_promotion(text_blob)
            product_code = _extract_product_code(card["href"])
            product_name = (card["title_text"] or card["image_alt"] or "상품명 미확인").strip()
            image_ok = bool(card["image_src"] or card["image_alt"])

            # 기본 가격은 카드 기준, 가능하면 상세 페이지 가격으로 보강
            detail_info = _fetch_detail_price_info(page, full_href) if idx < 6 else {
                "sale_price": None,
                "original_price": None,
                "discount_amount": None,
            }
            product_price = detail_info["sale_price"]
            if product_price is None:
                product_price = _fallback_price_from_card(text_blob)

            discount_amount = detail_info["discount_amount"]
            if discount_amount is None:
                card_prices = sorted(set(_extract_prices(text_blob)))
                if len(card_prices) >= 2:
                    discount_amount = card_prices[-1] - card_prices[0]

            # 필수 검증
            assert image_ok, f"상품 이미지 정보 누락: href={full_href}"
            assert len(product_name) >= 2, f"상품명 누락: href={full_href}"
            assert product_price is not None, f"상품금액 누락: href={full_href} | text='{text_blob}'"

            if _has_promotion_signal(text_blob):
                promotion_signal_count += 1
                assert promo_type in PROMOTION_TYPES, (
                    f"행사유형 분류 실패: href={full_href} | text='{text_blob}'"
                )
                classified_promotion_count += 1

            record_product(
                case_id="TC-02",
                product_name=product_name,
                product_code=product_code,
                product_price=product_price,
                discount_amount=discount_amount,
                image_ok=image_ok,
                source_url=full_href,
                promotion_type=promo_type,
            )
            print(
                "[DATA][TC-02][상품] "
                f"name={product_name} | code={product_code} | price={product_price} | "
                f"discount={discount_amount} | image_ok={image_ok} | promo={promo_type}"
            )
            inspected += 1

        assert inspected >= MIN_PRODUCT_CARD_COUNT
        assert promotion_signal_count >= 1, "행사 신호가 있는 상품 카드를 찾지 못했습니다."
        assert classified_promotion_count >= 1, "행사 신호 카드의 유형 분류가 모두 실패했습니다."

    def test_tc03_promotion_type_grouping(self, page: Page):
        """
        TC-03:
          - 상품 카드 행사유형 분류 집계
          - 행사 배너(비상품 카드) 상세 기록
        """
        _go_main(page)
        _scroll_until_text_visible(page, PRODUCT_SECTION_TITLE)

        cards = _extract_section_cards(page, PRODUCT_SECTION_TITLE)
        product_cards = [c for c in cards if _is_product_card(c["href"])]

        seen_types: set[str] = set()
        for card in product_cards:
            promo_type = _classify_promotion(card["text_blob"])
            if promo_type:
                seen_types.add(promo_type)

        assert seen_types, "행사 유형을 하나도 식별하지 못했습니다."
        assert seen_types.issubset(set(PROMOTION_TYPES)), (
            f"허용되지 않은 행사 유형 감지: {seen_types - set(PROMOTION_TYPES)}"
        )
        assert len(seen_types) >= 2, f"행사 유형 다양성 부족: 감지 유형={sorted(seen_types)}"

        # 배너형 카드 수집 (비상품 링크)
        banner_logged = 0
        for section_title in BANNER_SECTION_TITLES:
            _scroll_until_text_visible(page, section_title)
            section_cards = _extract_section_cards(page, section_title)
            for card in section_cards:
                if _is_product_card(card["href"]):
                    continue
                banner_name = (card["title_text"] or card["image_alt"] or "행사명 미확인").strip()
                if len(banner_name) < 2:
                    continue

                banner_url = urljoin(LOTTE_ZETTA_MAIN_URL, card["href"] or "/")
                image_ok = bool(card["image_src"] or card["image_alt"])

                record_banner(
                    case_id="TC-03",
                    banner_name=banner_name,
                    image_ok=image_ok,
                    source_url=banner_url,
                )
                print(
                    "[DATA][TC-03][배너] "
                    f"name={banner_name} | image_ok={image_ok} | url={banner_url}"
                )
                banner_logged += 1
                if banner_logged >= MAX_BANNER_LOG_COUNT:
                    break

            if banner_logged >= MAX_BANNER_LOG_COUNT:
                break

    def test_tc04_discount_price_distinction(self, page: Page):
        """
        TC-04:
          할인행사 카드에서 원가/행사가 구분 확인 + 상세 로그 기록
        """
        _go_main(page)
        _scroll_until_text_visible(page, PRODUCT_SECTION_TITLE)

        cards = _extract_section_cards(page, PRODUCT_SECTION_TITLE)
        product_cards = [c for c in cards if _is_product_card(c["href"])]

        discount_candidates = []
        for card in product_cards:
            promo_type = _classify_promotion(card["text_blob"])
            if promo_type in PROMOTION_TYPES:
                discount_candidates.append(card)

        assert discount_candidates, "할인행사 카드 후보를 찾지 못했습니다."

        success_cases = 0
        checked_samples: list[str] = []

        for card in discount_candidates[:5]:
            product_url = urljoin(LOTTE_ZETTA_MAIN_URL, card["href"])
            checked_samples.append(product_url)
            detail_info = _fetch_detail_price_info(page, product_url)

            product_code = _extract_product_code(card["href"])
            product_name = (card["title_text"] or card["image_alt"] or "상품명 미확인").strip()
            image_ok = bool(card["image_src"] or card["image_alt"])
            promo_type = _classify_promotion(card["text_blob"])

            record_product(
                case_id="TC-04",
                product_name=product_name,
                product_code=product_code,
                product_price=detail_info["sale_price"] or _fallback_price_from_card(card["text_blob"]),
                discount_amount=detail_info["discount_amount"],
                image_ok=image_ok,
                source_url=product_url,
                promotion_type=promo_type,
            )
            print(
                "[DATA][TC-04][상품] "
                f"name={product_name} | code={product_code} | sale={detail_info['sale_price']} | "
                f"original={detail_info['original_price']} | discount={detail_info['discount_amount']}"
            )

            # 원가/행사가 구분: 서로 다른 2개 가격
            if (
                detail_info["sale_price"] is not None
                and detail_info["original_price"] is not None
                and detail_info["original_price"] > detail_info["sale_price"]
            ):
                success_cases += 1
                break

        assert success_cases >= 1, (
            "할인행사에서 원가/행사가 구분(서로 다른 2개 가격)을 확인하지 못했습니다. "
            f"확인 URL 샘플={checked_samples}"
        )
