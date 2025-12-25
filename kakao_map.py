import json
import requests
import unittest
import sys
import os
import test_site  # 👈 분리해둔 test_site.py 파일을 불러옵니다

# ---------------------------------------------------------
# [설정] 파일 경로 및 API 키
# ---------------------------------------------------------
TOKEN_FILE = "kakao_token.json"
# GitHub Secrets에 등록된 키를 환경변수로 받거나, 없으면 직접 입력
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")

# ---------------------------------------------------------
# [기능 1] 토큰 자동 갱신 (전체 코드 포함)
# ---------------------------------------------------------
def refresh_access_token():
    print(">> 🔄 토큰 만료 감지! 자동 갱신을 시도합니다...")
    
    try:
        # 1. 기존 파일에서 리프레시 토큰 읽기
        with open(TOKEN_FILE, "r") as fp:
            tokens = json.load(fp)
        
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            print(">> ❌ 리프레시 토큰이 없습니다.")
            return None

        # 2. 카카오 서버에 갱신 요청
        url = "https://kauth.kakao.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": REST_API_KEY,
            "refresh_token": refresh_token
        }
        
        response = requests.post(url, data=data)
        new_tokens = response.json()
        
        # 3. 갱신 성공 시 파일 저장
        if "access_token" in new_tokens:
            tokens.update(new_tokens) # 기존 값에 새 값 덮어쓰기
            with open(TOKEN_FILE, "w") as fp:
                json.dump(tokens, fp)
            print(">> ✅ 토큰 갱신 성공! (새로운 수명 6시간)")
            return tokens["access_token"]
        else:
            print(f">> ❌ 토큰 갱신 실패: {new_tokens}")
            return None
            
    except Exception as e:
        print(f">> ❌ 토큰 갱신 중 시스템 에러: {e}")
        return None

# ---------------------------------------------------------
# [기능 2] 카카오톡 전송 (갱신 로직 연동)
# ---------------------------------------------------------
def send_kakao_msg(text):
    try:
        # 1. 현재 토큰으로 전송 시도
        with open(TOKEN_FILE, "r") as fp:
            tokens = json.load(fp)
        access_token = tokens["access_token"]
        
        url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
        headers = {"Authorization": "Bearer " + access_token}
        data = {
            "template_object": json.dumps({
                "object_type": "text",
                "text": text,
                "link": {
                    "web_url": "https://github.com",
                    "mobile_web_url": "https://github.com"
                }
            })
        }
        
        res = requests.post(url, headers=headers, data=data)
        res_code = res.json().get('result_code')

        # 2. 실패 시 처리 (특히 -401 토큰 만료)
        if res_code != 0:
            error_code = res.json().get('code')
            print(f">> ⚠️ 전송 실패 (코드: {error_code})")
            
            if error_code == -401: # 토큰 만료 에러
                print(">> 🚨 401 에러 발생! 갱신 로직을 가동합니다.")
                new_token = refresh_access_token()
                
                if new_token:
                    print(">> 🔄 갱신된 토큰으로 재전송 시도...")
                    headers["Authorization"] = "Bearer " + new_token
                    res = requests.post(url, headers=headers, data=data)
                    
                    if res.json().get('result_code') == 0:
                        print(f">> 🔔 [재시도 성공] 알림 발송 완료")
                    else:
                        print(">> ❌ 재시도 실패")
            else:
                print(f">> ❌ 전송 실패 (원인 불명): {res.json()}")
        else:
            print(f">> 🔔 [성공] 알림 발송 완료")
            
    except Exception as e:
        print(f">> ❌ 메시지 전송 시스템 에러: {e}")

# ---------------------------------------------------------
# [메인] 테스트 실행 및 결과 보고
# ---------------------------------------------------------
if __name__ == "__main__":
    print(">> 🚀 [Step 1] 테스트 파일(test_site.py)을 로드합니다...")
    
    # 1. test_site.py 안에 있는 모든 테스트 케이스를 불러옴
    suite = unittest.TestLoader().loadTestsFromModule(test_site)
    runner = unittest.TextTestRunner(verbosity=2)
    
    print(">> 🚀 [Step 2] 테스트를 실행합니다...")
    # 2. 실제 테스트 수행
    result = runner.run(suite)
    
    print(">> 🚀 [Step 3] 결과를 집계하여 알림을 보냅니다...")
    # 3. 결과 분석
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    is_success = result.wasSuccessful()

    # 4. 메시지 내용 구성
    if is_success:
        status_msg = "✅ [QA 성공] 모든 테스트 통과"
        detail_msg = f"총 {total}개의 테스트가 정상 수행되었습니다."
    else:
        status_msg = "❌ [QA 실패] 문제가 발생했습니다"
        detail_msg = f"실패: {failures}건 / 에러: {errors}건 (총 {total}건)"

    final_msg = f"{status_msg}\n------------------\n{detail_msg}\n------------------\n로그를 확인해주세요."

    # 5. 카카오톡 발송
    send_kakao_msg(final_msg)
    
    # 6. GitHub Actions 빌드 상태 설정 (실패 시 빨간불 Exit)
    if not is_success:
        sys.exit(1)