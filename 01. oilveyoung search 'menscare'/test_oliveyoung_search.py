import os
import json
import requests
from playwright.sync_api import sync_playwright

SEARCH_KEYWORDS = ['샴푸', '삼푸', '샤ㅁ푸', '샴ㅍ', 'ㅅㅁ푸']

# 환경변수 로드
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN")

def refresh_kakao_access_token():
    """Refresh Token을 이용해 새로운 Access Token 발급"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print("[System] 카카오 Access Token 갱신 성공")
        return response.json().get("access_token")
    else:
        print(f"[Error] 토큰 갱신 실패: {response.text}")
        return None

def send_kakao_message(access_token, products):
    """카카오톡 '나에게 보내기' API를 통해 결과 전송"""
    if not access_token:
        print("[System] 유효한 액세스 토큰이 없어 전송을 취소합니다.")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    message_text = "올리브영 맨즈케어 '샴푸' 평점 TOP 3\n\n"
    for idx, item in enumerate(products, 1):
        message_text += f"{idx}. {item['name']}\n- 가격: {item['price']}\n\n"

    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": message_text.strip(),
            "link": {
                "web_url": "https://www.oliveyoung.co.kr",
                "mobile_web_url": "https://m.oliveyoung.co.kr"
            },
            "button_title": "올리브영 바로가기"
        })
    }

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        print("[System] 카카오톡 메시지 전송 성공")
    else:
        print(f"[Error] 카카오톡 전송 실패: {response.text}")

def run_test():
    # 1. 카카오 토큰 갱신 준비
    access_token = refresh_kakao_access_token()
    
    # 2. 결과 저장을 위한 디렉토리 생성
    os.makedirs("test-results", exist_ok=True)

    with sync_playwright() as p:
        # CI 환경을 위해 headless=True로 설정
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # UI 동작, 네트워크 요청을 기록하는 Tracing 시작 (매우 강력한 디버깅 도구)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()

        top_3_products = []

        for keyword in SEARCH_KEYWORDS:
            print(f"\n--- 검색어 '{keyword}' 테스트 시작 ---")
            page.goto("https://www.oliveyoung.co.kr/store/main/main.do")
            
            page.locator("input#query").fill(keyword)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")

            if keyword == '샴푸':
                # 실제 DOM 구조에 맞게 Selector 수정 필요
                # page.locator("text='맨즈케어'").click()
                # page.locator("text='평점순'").click()
                # page.wait_for_timeout(2000)

                items = page.locator(".prd_info").all()
                for i in range(min(3, len(items))):
                    name = items[i].locator(".tx_name").inner_text()
                    price = items[i].locator(".tx_cur > .tx_num").inner_text()
                    top_3_products.append({"name": name, "price": price + "원"})
                    print(f"[Rank {i+1}] {name} / {price}원")
                
                if top_3_products:
                    send_kakao_message(access_token, top_3_products)

            else:
                # 오타/잘못된 키워드의 경우: 예외 처리 UI(결과 없음) 검증
                no_result_element = page.locator(".no_data")
                if no_result_element.is_visible():
                    print(f"[Pass] '{keyword}' 검색 시 '검색결과 없음' 페이지 정상 노출")
                else:
                    item_count = page.locator(".prd_info").count()
                    if item_count > 0:
                        print(f"[Warning] '{keyword}' 검색 시 {item_count}개의 유사 결과가 노출됨 (자동 교정 추정)")
                    else:
                        print(f"[Fail] '{keyword}' 검색 예외 처리 불명확")

        # Tracing 종료 및 Artifact 파일로 저장
        context.tracing.stop(path="test-results/trace.zip")
        browser.close()

if __name__ == "__main__":
    run_test()