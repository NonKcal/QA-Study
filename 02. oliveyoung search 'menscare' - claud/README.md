# 올리브영 맨즈케어 검색 자동화 테스트

> **QA Study** | Playwright + Python | 카카오톡 결과 알림

---

## 📁 프로젝트 구조

```
C:\QA_Study\02. oliveyoung search 'menscare' - claud\
├── test_oliveyoung_search.py   ← 메인 테스트 코드
├── requirements.txt
├── .env.example                ← 환경변수 샘플 (커밋 OK)
├── .gitignore
└── .github/
    └── workflows/
        └── oliveyoung-test.yml ← GitHub Actions CI
```

---

## 🧪 테스트 케이스 설계 (ISTQB EP + BVA)

| TC ID | 검색어 | 분류 | 설명 | 기대 결과 |
|-------|--------|------|------|-----------|
| TC_001 | 맨즈케어 | Valid | 정상 검색어 | 결과 있음 PASS |
| TC_002 | 샴푸 | Valid | 관련 상품명 | 결과 있음 PASS |
| TC_003 | 삼퓨 | Typo | 받침 혼동 오타 | 결과 있음 PASS |
| TC_004 | 샤ㅁ푸 | Typo | 자음/모음 분리 | 결과 있음 PASS |
| TC_005 | 샴ㅍ | Typo | 미완성 글자 | 결과 있음 PASS |
| TC_006 | ㅅㅍ | Typo | 초성 검색 | 결과 있음 PASS |
| TC_007 | menscare | English | 영문 검색 | 결과 있음 PASS |
| TC_008 | men's care | English | 영문+특수문자 | 결과 있음 PASS |
| TC_009 | !@#$% | Special | 특수문자만 | 결과 없음 PASS |
| TC_010 | (공백) | Edge | 공백만 입력 | 결과 없음 PASS |

---

## ⚡ 로컬 실행 방법

```bash
# 1. 의존성 설치 (Playwright는 이미 설치됨 가정)
pip install -r requirements.txt
python -m playwright install chromium

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 실제 카카오 토큰 값 입력

# 3. 실행
python test_oliveyoung_search.py
```

> 💡 `.env` 파일을 자동 로드하려면 `pip install python-dotenv` 후
> 메인 파일 상단에 `from dotenv import load_dotenv; load_dotenv()` 추가

---

## 🔑 카카오 토큰 발급 방법

1. [카카오 Developers](https://developers.kakao.com) 접속 → 내 애플리케이션 생성
2. **REST API 키** 복사 → `KAKAO_REST_API_KEY`
3. [토큰 발급 도구](https://developers.kakao.com/tool/rest-api/open/get/v2-user-me) 에서 Access/Refresh Token 발급
4. GitHub → Settings → Secrets and variables → Actions 에 등록

---

## 📲 카카오톡 알림 예시

```
🧪 올리브영 맨즈케어 검색 자동화 테스트
📅 실행시각: 2025-01-15 10:00
📊 결과: 8/10 PASS (80%)
──────────────────────────────
✅ TC_001 [Valid] '맨즈케어'
   → 상위 10건 수집 (3.2s)
   #1 브랜드A - 상품명A 12,000원
   ...
❌ TC_009 [Special] '!@#$%'
   → 예상치 못한 3건 결과 (1.1s)
──────────────────────────────
🔴 FAIL: 2건
📌 QA Study | Playwright + Python
```
