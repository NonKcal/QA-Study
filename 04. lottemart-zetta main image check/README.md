# 롯데마트 제타 메인 노출 자동화

## 1) 목적
- 대상: `https://lottemartzetta.com/`
- 환경: PC Chrome(Chromium) + DevTools iPhone 14 Pro Max 에뮬레이션
- 검증:
  - 메인 상품 영역의 상품 카드 노출
  - 상품 이미지/상품명/상품코드/상품금액/할인금액
  - 행사 유형 분류(`n+n`, `n개 담기 시 할인`, `상품할인`, `금액조건 할인`)
  - 할인행사의 원 상품가/행사상품가 구분
  - 행사 배너(행사명/행사이미지) 수집
- 알림: 실행 완료 후 카카오톡 `나에게 보내기`

## 2) 파일 구성
- `Test_Scenario.py`: 시나리오/검증 기준 상수
- `Test_Case_main_pg.py`: 메인 노출 테스트 케이스 (pytest)
- `conftest.py`: 브라우저 픽스처 + 카카오 결과 전송 + 토큰 만료 재발급 재시도
- `reporter.py`: 상품/배너 상세 데이터 기록 + 집계 + 아티팩트 생성
- `kakao_oauth.py`: 카카오 OAuth 공통 유틸
- `kakao_auth_bootstrap.py`: 최초 1회 로그인(인가코드) 기반 토큰 발급
- `refresh_token.py`: Refresh Token 갱신 + GitHub Secrets 자동 업데이트
- `requirements.txt`: 실행 의존성

## 3) GitHub Actions 시크릿
저장소 `Settings > Secrets and variables > Actions` 에 아래 키를 등록합니다.

- `GH_PAT`
- `KAKAO_ACCESS_TOKEN`
- `KAKAO_CLIENT_SECRET`
- `KAKAO_REFRESH_TOKEN`
- `KAKAO_REST_API_KEY`

`GH_PAT` 권한은 최소 `repo`, `actions:write` 권한을 권장합니다.

## 4) 최초 1회 카카오 로그인(토큰 부트스트랩)
로컬에서 아래처럼 실행합니다.

```powershell
cd "C:\QA_Study\04. lottemart-zetta main image check"
pip install -r requirements.txt
setx KAKAO_REST_API_KEY "<REST_API_KEY>"
setx KAKAO_CLIENT_SECRET "<CLIENT_SECRET>"
setx KAKAO_REDIRECT_URI "https://localhost:3000/oauth"
python kakao_auth_bootstrap.py
```

스크립트가 출력한 `access_token`, `refresh_token` 값을 GitHub Secrets에 등록합니다.

## 5) CI 동작 순서
워크플로 파일: `.github/workflows/lottemart-zetta-main-check.yml`

1. 의존성 설치
2. `refresh_token.py`로 카카오 토큰 사전 갱신 + GitHub Secrets 업데이트
3. `pytest` 실행
4. 테스트 종료 시 `conftest.py`가 카카오톡으로 결과 전송
5. 전송 시 토큰 만료(401) 발생하면 즉시 재발급 후 재전송
6. 수집 결과를 `artifacts/observation-summary.json`, `artifacts/observation-summary.md`, `artifacts/observation-summary.csv`로 저장

## 6) 실행 로그/아티팩트 확인 포인트
- Actions 콘솔 로그:
  - `[DATA][TC-02][상품] ...`
  - `[DATA][TC-03][배너] ...`
  - `[DATA][TC-04][상품] ...`
  - `[상품 TSV]`, `[행사배너 TSV]` 블록 (엑셀 붙여넣기용)
- 업로드 아티팩트:
  - `pytest-report.xml`
  - `artifacts/*.png` (실패 스크린샷)
  - `artifacts/observation-summary.json`
  - `artifacts/observation-summary.md`
  - `artifacts/observation-summary.csv`

## 7) 로컬 수동 실행
```powershell
cd "C:\QA_Study\04. lottemart-zetta main image check"
python -m pytest Test_Case_main_pg.py -v --tb=short
```
