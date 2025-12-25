from playwright.sync_api import sync_playwright
import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()
# CI 환경에서는 GitHub Secret에서 가져오고, 로컬에서는 .env에서 가져옵니다.
REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
TOKEN_FILE = "kakao_token.json"

# --- [토큰 갱신 및 메시지 전송 함수는 기존과 동일 (생략하지 말고 그대로 두세요)] ---
# (지면 관계상 핵심 로직인 run 함수만 보여드립니다. 위쪽 함수들은 유지해주세요!)

# ---------------------------------------------------------
# [기능 1] 토큰 갱신 함수 (핵심!)
# ---------------------------------------------------------
def refresh_access_token():
    print(">> 🔄 토큰 만료 감지! 자동 갱신을 시도합니다...")
    
    # 1. 기존 토큰 파일에서 리프레시 토큰 꺼내기
    with open(TOKEN_FILE, "r") as fp:
        tokens = json.load(fp)
    
    refresh_token = tokens.get("refresh_token")
    
    if not refresh_token:
        print(">> ❌ 리프레시 토큰이 없습니다. auth.py를 다시 실행해 주세요.")
        return None

    # 2. 카카오에게 "새 액세스 토큰 줘" 요청
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": refresh_token
    }
    
    response = requests.post(url, data=data)
    new_tokens = response.json()
    
    # 3. 갱신 성공 시 파일 업데이트
    if "access_token" in new_tokens:
        # 기존 토큰 정보에 새 정보 덮어쓰기 (리프레시 토큰이 바뀔 수도, 안 바뀔 수도 있음)
        tokens.update(new_tokens)
        
        with open(TOKEN_FILE, "w") as fp:
            json.dump(tokens, fp)
            
        print(">> ✅ 토큰 갱신 성공! 새로운 수명(6시간)을 얻었습니다.")
        send_kakao_msg("✅ 토큰 갱신 성공! 새로운 수명(6시간)을 얻었습니다.")

        return tokens["access_token"]
    else:
        print(f">> ❌ 토큰 갱신 실패 (로그인이 필요합니다): {new_tokens}")
        return None

# ---------------------------------------------------------
# [기능 2] 카카오톡 전송 (자동 갱신 로직 포함)
# ---------------------------------------------------------
def send_kakao_msg(text):
    try:
        # 1. 현재 토큰 읽기
        with open(TOKEN_FILE, "r") as fp:
            tokens = json.load(fp)
        access_token = tokens["access_token"]
        
        # 2. 전송 시도
        url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
        headers = {"Authorization": "Bearer " + access_token}
        data = {
            "template_object": json.dumps({
                "object_type": "text",
                "text": text,
                "link": {
                    "web_url": "https://map.kakao.com",
                    "mobile_web_url": "https://map.kakao.com"
                }
            })
        }
        
        res = requests.post(url, headers=headers, data=data)
        res_code = res.json().get('result_code')

        # 3. 실패 시 처리 (특히 -401 에러)
        if res_code != 0:
            error_code = res.json().get('code')
            print(f">> ⚠️ 전송 실패 (코드: {error_code})")
            
            # [핵심] 토큰 만료 에러(-401)라면? -> 갱신 후 재시도!
            if error_code == -401:
                new_token = refresh_access_token()
                if new_token:
                    # 재시도 (재귀 호출)
                    print(">> 🔄 갱신된 토큰으로 메시지 재전송 시도...")
                    headers["Authorization"] = "Bearer " + new_token
                    res = requests.post(url, headers=headers, data=data)
                    if res.json().get('result_code') == 0:
                        print(f">> 🔔 [재시도 성공] 알림 발송 완료")
                    else:
                        print(">> ❌ 재시도 실패")
            else:
                print(f">> ❌ 알 수 없는 오류로 전송 실패: {res.json()}")
        else:
            print(f">> 🔔 [성공] 알림 발송 완료")
            
    except Exception as e:
        print(f">> ❌ 시스템 에러: {e}")

# ---------------------------------------------------------
# [메인 로직]
# ---------------------------------------------------------
def run():
    with sync_playwright() as p:
        # 1. CI 환경인지 확인 (GitHub Actions는 'CI'라는 환경변수를 true로 줍니다)
        is_ci = os.getenv("CI") == "true"
        
        # CI면 headless=True(화면 없음), 내 컴퓨터면 False(화면 있음)
        browser = p.chromium.launch(headless=is_ci, slow_mo=1000)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        
        try:
            # --- [Phase 1: 로그인 (로컬에서만 수행)] ---
            if not is_ci:
                print(">> [Local] 로그인 프로세스를 진행합니다.")
                page.goto("https://www.daum.net")
                if page.is_visible('text="카카오계정으로 로그인"'):
                    page.click('text="카카오계정으로 로그인"')
                    if page.is_visible('text="카카오로 로그인"'):
                        page.click('text="카카오로 로그인"')
                    page.click('text="QR코드 로그인"')
                    # ... (로그인 대기 로직) ...
                    page.wait_for_url("**/www.daum.net/**", timeout=60000)
            else:
                print(">> [CI Server] 로그인을 생략하고 바로 검색 테스트를 진행합니다.")

            # --- [Phase 2: 지도 데이터 수집] ---
            print(">> 2. 카카오맵 이동")
            page.goto("https://map.kakao.com/")
            
            page.wait_for_selector('#search\.keyword\.query', timeout=10000)
            
            print(">> 3. '강남역 맛집' 검색")
            page.fill('#search\.keyword\.query', "강남역 맛집")
            page.press('#search\.keyword\.query', 'Enter')
            
            page.wait_for_selector('#info\.search\.place\.list', timeout=5000)
            
            places = page.locator('.PlaceItem')
            count = places.count()
            
            print(f"✅ [테스트 성공] 맛집 {count}개 발견")
            
            # CI 환경에서 성공했을 때 알림을 받고 싶다면:
            if is_ci:
                send_kakao_msg(f"✅ [GitHub CI] 테스트 성공! 맛집 {count}개 확인됨.")

        except Exception as e:
            error_msg = f"🚨 [GitHub CI] 테스트 실패!\n\n에러: {str(e)[:50]}"
            print(error_msg)
            # 스크린샷 찍기 (GitHub Artifact로 저장 가능)
            page.screenshot(path="error_capture.png")
            send_kakao_msg(error_msg)
            
            # CI 파이프라인을 '실패'로 처리하기 위해 에러를 다시 던짐
            raise e 
            
        finally:
            browser.close()

# ---------------------------------------------------------
# [기존 메인 로직]
# ---------------------------------------------------------
# def run():
    # with sync_playwright() as p:
    #     # 브라우저 열기 (화면 크기 설정 포함)
    #     browser = p.chromium.launch(headless=False, slow_mo=1000)
    #     context = browser.new_context(viewport={'width': 1280, 'height': 720})
    #     page = context.new_page()
        
    #     try:
    #         # # --- [로그인 및 데이터 수집 로직] ---
    #         # # (테스트를 위해 일부러 에러를 내보겠습니다)
    #         # print(">> 테스트 시작: 의도적으로 에러를 발생시킵니다.")
            
    #         # # # 일부러 없는 사이트로 이동 -> 에러 발생 유도
    #         # page.goto("https://www.daum.net/없는페이지") 

    #         # --- [Phase 1: 로그인] ---
    #         print(">> 1. 다음 메인 접속 및 로그인 시도")
    #         page.goto("https://www.daum.net")
            
    #         if page.is_visible('text="카카오계정으로 로그인"'):
    #             page.click('text="카카오계정으로 로그인"')
                
    #             # [매니저님이 찾으신 추가 단계!]
    #             if page.is_visible('text="카카오로 로그인"'):
    #                 print(">> '카카오로 로그인' 버튼 클릭")
    #                 page.click('text="카카오로 로그인"')
                
    #             print(">> 'QR코드 로그인' 선택")
    #             page.click('text="QR코드 로그인"')
                
    #             print(">> 🚨 핸드폰으로 QR코드를 스캔해주세요! (60초 대기)")
                
    #             # 로그인 완료 후 메인으로 돌아올 때까지 대기
    #             page.wait_for_url("**/www.daum.net/**", timeout=60000)
    #             print(">> ✅ 로그인 성공! 메인 페이지 진입 완료")

    #         # --- [Phase 2: 지도 데이터 수집] ---
    #         print(">> 2. 카카오맵 이동")
    #         page.goto("https://map.kakao.com/")
            
    #         # 검색창이 뜰 때까지 안전하게 대기
    #         page.wait_for_selector('#search\.keyword\.query', timeout=10000)
            
    #         print(">> 3. '강남역 맛집' 검색")
    #         page.fill('#search\.keyword\.query', "강남역 맛집")
    #         page.press('#search\.keyword\.query', 'Enter')
            
    #         # 결과 리스트 로딩 대기
    #         page.wait_for_selector('#info\.search\.place\.list', timeout=5000)
            
    #         # 데이터 추출
    #         print(">> 4. 데이터 수집 중...")
    #         places = page.locator('.PlaceItem')
    #         count = places.count()
            
    #         # 결과 메시지 만들기
    #         result_msg = f"✅ [자동화 성공] 총 {count}개 맛집 발견!\n"
            
    #         for i in range(min(3, count)): # 상위 3개만
    #             name = places.nth(i).locator('.link_name').inner_text()
    #             result_msg += f"- {name}\n"
            
    #         print(result_msg)
            
    #         # (선택) 성공했을 때도 카톡을 받고 싶으면 아래 주석(#)을 지우세요
    #         send_kakao_msg(result_msg)
            
    #     except Exception as e:
    #         # 에러 발생 시 알림 전송 (여기서 토큰 만료되면 자동 갱신됨)
    #         error_msg = f"🚨 [자동갱신 테스트] QA 테스트 실패!\n\n에러 내용: {str(e)[:50]}" 
    #         print(">> ❌ 에러 감지! 알림 전송 로직을 수행합니다.")
    #         send_kakao_msg(error_msg)
            
    #     finally:
    #         page.wait_for_timeout(2000)
    #         browser.close()

if __name__ == "__main__":
    run()