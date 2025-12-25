from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # 1. 브라우저 열기
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        
        # 2. [변경점] '다음(Daum)' 메인 페이지로 접속
        # 카카오 로그인 페이지로 바로 가지 않고, 실제 서비스(다음)를 통해 진입합니다.
        print(">> 다음(Daum) 메인 페이지 접속 중...")
        page.goto("https://www.daum.net")
        
        # 3. [추가됨] 메인 화면에서 '카카오계정으로 로그인' 버튼 클릭
        print(">> 메인 화면의 로그인 버튼을 찾아서 클릭합니다.")
        page.click('text="카카오계정으로 로그인"') 
        page.click('text="카카오로 로그인"') 
        
        # 4. 이제 카카오 로그인 페이지가 정상적으로 떴을 겁니다. 'QR코드 로그인' 클릭
        print(">> QR코드 로그인 모드로 전환합니다.")
        page.click('text="QR코드 로그인"')
        
        # 5. QR 인증 대기 (60초)
        print(">> 🚨 핸드폰으로 QR코드를 스캔해주세요! (최대 60초)")
        
        try:
            # 로그인이 성공하면 다시 'www.daum.net' 메인으로 돌아옵니다.
            # URL에 'daum.net'이 포함될 때까지 기다립니다.
            page.wait_for_url("**/www.daum.net/**", timeout=60000)
            
            print(">> ✅ 로그인 성공! 메인 페이지로 복귀했습니다.")
            
            # 로그인 성공 인증샷 남기기
            page.screenshot(path="login_success.png")
            print(">> 인증샷 저장 완료: login_success.png")
            
        except:
            print(">> ❌ 시간 초과: 로그인이 완료되지 않았습니다.")
            
        # 6. 결과 확인용 대기 후 종료
        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    run()