"""
Test_Scenario.py
─────────────────────────────────────────────────────────────────────────────
테스트 시나리오 명세 및 메타데이터 정의
 - 실행 파일 아님 (pytest 수집 대상 아님)
 - 테스트 케이스 파일에서 import하여 ID·설명 관리
─────────────────────────────────────────────────────────────────────────────

[테스트 환경]
  - 대상 URL  : https://www.oliveyoung.co.kr
  - 디바이스  : PC Chrome DevTools > iPhone 14 Pro Max 에뮬레이션
                (viewport 430×932, scale 3x, Mobile UA)
  - 실행 주기 : 매일 KST 08:00 (GitHub Actions cron)
  - 결과 전송 : 카카오톡 나에게 보내기

[파일 역할]
  - Test_Scenario.py      : 시나리오 명세 (본 파일)
  - Test_Case_main_pg.py  : TC-01 ~ TC-02 (메인 페이지)
  - Test_Case_event_pg.py : TC-03 (이벤트 페이지)
  - conftest.py           : 브라우저 픽스처 + 카카오 결과 전송
  - refresh_token.py      : 카카오 토큰 갱신 (YML STEP 5에서 실행)
─────────────────────────────────────────────────────────────────────────────
"""

# ── URL 상수 ──────────────────────────────────────────────────────────────
OLIVEYOUNG_MAIN_URL  = "https://www.oliveyoung.co.kr/store/main/getMains.do"
# 이벤트 페이지 URL은 테스트 실행 중 메인에서 동적으로 획득

# ── 검증 텍스트 상수 ──────────────────────────────────────────────────────
# 메인 페이지
# ※ DOM 확인: <h3><strong>인기 행사만 모았어요!</strong></h3> → 공백 없음
SECTION_TITLE        = "인기 행사만 모았어요!"         # TC-01, TC-02
# ※ DOM 확인: data-banner-name="미쟝센X포차코", data-attr="...^미쟝센X포차코^1"
#             strong.tit = "포차코도 탐낸 / 그 머릿결"
EVENT_NAME           = "포차코"                        # TC-02 (배너명 포함 여부로 식별)
# ※ DOM 확인: <strong class="tit">포차코도 탐낸\n</strong><strong class="tit">그 머릿결\n</strong>
#             tit이 2개의 strong으로 분리됨 → 첫 번째 또는 부모 a의 텍스트로 검증
EVENT_TITLE_TEXT     = "포차코도 탐낸"                 # TC-02-2: strong.tit 첫 번째
# ※ DOM 확인: <span class="desc">미쟝센 콜라보 한정판, 품절 전 선점!</span>
EVENT_SUBTITLE_TEXT  = "미쟝센 콜라보 한정판"          # TC-02-3: span.desc (부분 일치)

# 이벤트 페이지
# ※ DOM 확인: <h1 id="planTitle">빛나는 머릿결에 포차코도 GET!</h1>
EVENT_PAGE_TITLE     = "빛나는 머릿결에 포차코도 GET!"  # TC-03: h1#planTitle
EVENT_PLANSHOP_NO    = "500000100017555"                # 기획전 번호 (URL 식별용)

# 이벤트 페이지 섹션 정보 (ul.plan-menu#move1 기준)
# data-ref-dispcatno="" → 전체 / 나머지 3개는 개별 섹션
EVENT_SECTION_CATNOS = [
    "",                      # 전체 (dispcatno 없음)
    "5000001000175550001",   # 포차코 파우치/헤어롤 증정 기획!
    "5000001000175550002",   # 미쟝센 BEST 더보기
    "5000001000175550003",   # 인기BEST 미쟝센 염모제 모음!
]

# ── 상품 UI 검증 항목 (ISTQB: 기능 + 비기능 체크포인트) ──────────────────
PRODUCT_UI_CHECKLIST = [
    "product_image",    # 상품 이미지
    "product_name",     # 상품명
    "brand_name",       # 브랜드명
    "tag",              # 태그
    "original_price",   # 정가 (회색 + 취소선)
    "discount_price",   # 할인가 (붉은 글씨)
]

# ── 시나리오 메타데이터 ───────────────────────────────────────────────────
SCENARIOS: list[dict] = [
    # ── TC-01 ─────────────────────────────────────────────────────────────
    {
        "id":       "TC-01",
        "module":   "Test_Case_main_pg",
        "summary":  "메인 페이지 '인기 행사만 모았어요!' 영역 노출 확인",
        "priority": "High",
        "type":     "Functional / UI Visibility",
    },

    # ── TC-02 ─────────────────────────────────────────────────────────────
    {
        "id":       "TC-02",
        "module":   "Test_Case_main_pg",
        "summary":  "메인 페이지 '인기 행사만 모았어요!' 영역 내 '포차코' 행사 노출 확인",
        "priority": "High",
        "type":     "Functional / UI Visibility",
        "children": [
            {"id": "TC-02-1", "summary": "포차코 행사 이미지 노출 확인"},
            {"id": "TC-02-2", "summary": "포차코 행사 타이틀 노출 확인"},
            {"id": "TC-02-3", "summary": "포차코 행사 서브타이틀 노출 확인"},
            {"id": "TC-02-4", "summary": "포차코 행사 상품 영역 노출 확인 (이미지/상품명/브랜드/태그/정가/할인가)"},
            {"id": "TC-02-5", "summary": "포차코 행사 타이틀 클릭 → 이벤트 페이지 이동 / 뒤로가기 스크롤 0px 복원"},
            {"id": "TC-02-6", "summary": "포차코 행사 서브타이틀 클릭 → 이벤트 페이지 이동 / 뒤로가기 스크롤 0px 복원"},
            {"id": "TC-02-7", "summary": "포차코 행사 상품이미지 클릭 → 상품상세 이동 / 뒤로가기 스크롤 0px 복원"},
            {"id": "TC-02-8", "summary": "포차코 행사 상품명 클릭 → 상품상세 이동 / 뒤로가기 스크롤 0px 복원"},
            {"id": "TC-02-9", "summary": "포차코 행사 브랜드명 클릭 → 상품상세 이동 / 뒤로가기 스크롤 0px 복원"},
        ],
    },

    # ── TC-03 ─────────────────────────────────────────────────────────────
    {
        "id":       "TC-03",
        "module":   "Test_Case_event_pg",
        "summary":  "'빛나는 머릿결에 포차코도 GET!' 이벤트 페이지 확인",
        "priority": "High",
        "type":     "Functional / UI Visibility",
        "children": [
            {"id": "TC-03-1", "summary": "이벤트 이미지 노출 확인"},
            {"id": "TC-03-2", "summary": "기획전 상세 섹션바 노출 확인"},
            {"id": "TC-03-2-1", "summary": "섹션바 각 섹션 클릭 시 섹션 페이지 갱신 확인"},
            {"id": "TC-03-2-2", "summary": "섹션 상품 UI 확인 (이미지/상품명/브랜드/태그/정가/할인가) — 첫 번째 상품 기준"},
        ],
    },
]


def get_scenario(tc_id: str) -> dict | None:
    """TC ID로 시나리오 메타데이터 반환"""
    for s in SCENARIOS:
        if s["id"] == tc_id:
            return s
        for child in s.get("children", []):
            if child["id"] == tc_id:
                return child
    return None


if __name__ == "__main__":
    # 시나리오 목록 출력 (명세 확인용)
    print("=" * 60)
    print("  올리브영 이벤트 QA — 테스트 시나리오 목록")
    print("=" * 60)
    for s in SCENARIOS:
        print(f"\n[{s['id']}] {s['summary']}")
        print(f"  모듈    : {s['module']}")
        print(f"  우선순위: {s['priority']}")
        print(f"  유형    : {s['type']}")
        for child in s.get("children", []):
            print(f"  ├ [{child['id']}] {child['summary']}")
