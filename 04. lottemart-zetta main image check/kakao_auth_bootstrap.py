"""
최초 1회 카카오 로그인(동의) 후 토큰 발급 보조 스크립트.

사용 목적:
  - GitHub Secrets 초기값 세팅용 Access/Refresh 토큰 확보
  - CI 환경에서 불가능한 "대화형 로그인"을 로컬에서 1회 수행
"""

from __future__ import annotations

import json
import os
import sys

from kakao_oauth import (
    build_kakao_login_url,
    exchange_authorization_code,
    extract_authorization_code,
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


def main() -> int:
    try:
        rest_api_key = _required_env("KAKAO_REST_API_KEY")
        client_secret = _required_env("KAKAO_CLIENT_SECRET")
        redirect_uri = os.getenv("KAKAO_REDIRECT_URI", "https://localhost:3000/oauth")

        login_url = build_kakao_login_url(
            rest_api_key=rest_api_key,
            redirect_uri=redirect_uri,
            scope="talk_message",
        )

        print("=" * 70)
        print("1) 아래 URL을 브라우저에 열고 카카오 로그인 + 동의를 완료하세요.")
        print(login_url)
        print("-" * 70)
        print("2) redirect_uri 로 이동한 최종 URL 전체를 복사해 붙여넣으세요.")
        print("=" * 70)

        redirected = input("Redirect URL 입력: ").strip()
        auth_code = extract_authorization_code(redirected)

        tokens = exchange_authorization_code(
            rest_api_key=rest_api_key,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            authorization_code=auth_code,
        )

        # 보안상 기본 동작은 화면 출력만 수행한다.
        # 저장이 필요하면 사용자가 의도적으로 파일 저장 옵션을 추가해 확장하도록 한다.
        print("\n[토큰 발급 성공]")
        print(json.dumps(tokens, ensure_ascii=False, indent=2))
        print("\nGitHub Secrets에 아래 값을 반영하세요:")
        print("- KAKAO_ACCESS_TOKEN")
        print("- KAKAO_REFRESH_TOKEN")
        print("- KAKAO_REST_API_KEY")
        print("- KAKAO_CLIENT_SECRET")
        return 0

    except Exception as exc:
        print(f"[오류] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
