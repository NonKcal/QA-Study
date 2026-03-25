"""
롯데마트 제타 메인 노출 점검 시나리오 명세.
ISTQB 관점에서 "기능(Functional) + UI 가시성(UI Visibility)" 검증에 초점을 둔다.
"""

from __future__ import annotations

# 테스트 대상 URL
LOTTE_ZETTA_MAIN_URL = "https://lottemartzetta.com/"

# 메인 핵심 안내 헤드라인
WELCOME_TITLE = "롯데마트 제타에 오신걸 환영합니다."

# 상품 상세 검증 대상 섹션
PRODUCT_SECTION_TITLE = "이번 주 행사상품을 만나보세요"
MIN_PRODUCT_CARD_COUNT = 5
MAX_PRODUCT_LOG_COUNT = 10

# 행사 배너 수집 대상 섹션 (운영 구조상 배너형 타일이 자주 노출되는 영역)
BANNER_SECTION_TITLES = [
    "쉽고 편리한 스마트 장보기",
    "어디서도 볼 수 없는 알뜰 쇼핑 찬스",
    "매일 새로운 스마트 장보기",
]
MAX_BANNER_LOG_COUNT = 10

# 행사 유형(요청사항 고정 분류)
PROMOTION_TYPES = [
    "n+n",
    "n개 담기 시 할인",
    "상품할인",
    "금액조건 할인",
]

# 시나리오 메타데이터 (추적성 확보용)
SCENARIOS = [
    {
        "id": "TC-01",
        "summary": "메인 환영 영역(헤드라인/로그인 링크) 노출 확인",
        "type": "Functional / UI Visibility",
        "priority": "High",
    },
    {
        "id": "TC-02",
        "summary": "상품 노출 영역에서 상품 카드(이미지/상품명/상품코드/금액/할인금액) 확인",
        "type": "Functional / UI Visibility / Data Validation",
        "priority": "High",
    },
    {
        "id": "TC-03",
        "summary": "상품 카드의 행사 유형 분류 확인 (4종: n+n, n개 담기 시 할인, 상품할인, 금액조건 할인)",
        "type": "Functional / Business Rule Validation",
        "priority": "High",
    },
    {
        "id": "TC-04",
        "summary": "할인행사 카드에서 원 상품가와 행사상품가 구분 노출 확인",
        "type": "Functional / Price Validation",
        "priority": "High",
    },
]
