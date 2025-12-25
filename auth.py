import requests
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

rest_api_key = os.getenv("KAKAO_REST_API_KEY")
redirect_uri = "https://localhost:3000/oauth"

# --- [디버깅 코드 추가] ---
print(f">> 현재 로드된 API 키 상태: {rest_api_key}")

if rest_api_key is None:
    print(">> 🚨 에러: .env 파일을 찾지 못했거나 내용이 비어있습니다!")
    print(">> 1. .env 파일이 auth.py와 같은 폴더에 있는지 확인하세요.")
    print(">> 2. .env 파일 안에 KAKAO_REST_API_KEY=... 라고 오타 없이 적혔는지 확인하세요.")
    print(">> 3. 파일 저장(Ctrl+S)을 했는지 확인하세요.")
    exit() # 프로그램 강제 종료
# ------------------------

def get_token():
    # 1. 인가 코드(Authorize Code) 발급을 위한 URL 생성
    login_url = f"https://kauth.kakao.com/oauth/authorize?client_id={rest_api_key}&redirect_uri={redirect_uri}&response_type=code&scope=talk_message"
    
    print("----------------------------------------------------------------")
    print("아래 링크를 복사해서 브라우저 주소창에 붙여넣고 엔터를 치세요!")
    print("로그인하고 동의하면, '사이트에 연결할 수 없음' 페이지가 뜰 겁니다.")
    print("그때 주소창에 있는 전체 URL을 복사해서 아래에 붙여넣어 주세요.")
    print("----------------------------------------------------------------")
    print(login_url)
    print("----------------------------------------------------------------")
    
    # 2. 사용자에게 리다이렉트된 URL 입력받기
    url = input(">> 이동된 전체 URL을 붙여넣으세요: ")
    
    # URL에서 'code=' 뒷부분(인가 코드)만 잘라내기
    try:
        authorize_code = url.split("code=")[1]
    except IndexError:
        print(">> ❌ URL 형식이 잘못되었습니다. code= 부분이 안 보입니다.")
        return

    # 3. 토큰 발급 요청 (인가 코드 -> 액세스 토큰 교환)
    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "code": authorize_code,
    }

    response = requests.post(token_url, data=data)
    tokens = response.json()

    # 4. 결과 저장
    if "access_token" in tokens:
        import json
        # 나중에 쓰기 위해 파일로 저장해둡니다.
        with open("kakao_token.json", "w") as fp:
            json.dump(tokens, fp)
        print(">> ✅ 토큰 발급 성공! 'kakao_token.json' 파일이 생성되었습니다.")
    else:
        print(">> ❌ 토큰 발급 실패")
        print(tokens)

if __name__ == "__main__":
    get_token()