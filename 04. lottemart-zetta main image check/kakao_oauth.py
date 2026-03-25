"""
카카오 OAuth 공통 유틸.
보안 원칙:
  - 토큰은 파일에 강제 저장하지 않고 메모리/환경변수 중심으로 처리
  - 민감정보는 반드시 환경변수에서만 읽는다
"""

from __future__ import annotations

import requests


KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"


def build_kakao_login_url(
    rest_api_key: str,
    redirect_uri: str,
    scope: str = "talk_message",
) -> str:
    """카카오 로그인/동의 화면 진입 URL을 생성한다."""
    params = {
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
    }
    req = requests.Request("GET", KAKAO_AUTHORIZE_URL, params=params).prepare()
    return req.url


def extract_authorization_code(redirected_url: str) -> str:
    """리다이렉트 URL에서 인가코드(code)를 안전하게 추출한다."""
    if "code=" not in redirected_url:
        raise ValueError("리다이렉트 URL에 code 파라미터가 없습니다.")

    code_part = redirected_url.split("code=", 1)[1]
    code = code_part.split("&", 1)[0].strip()
    if not code:
        raise ValueError("인가코드(code)가 비어 있습니다.")
    return code


def exchange_authorization_code(
    rest_api_key: str,
    client_secret: str,
    redirect_uri: str,
    authorization_code: str,
) -> dict:
    """인가코드를 Access/Refresh 토큰으로 교환한다."""
    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": rest_api_key,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": authorization_code,
        },
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise RuntimeError(f"인가코드 교환 실패 ({resp.status_code}): {data}")
    return data


def refresh_access_token(
    rest_api_key: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """
    Refresh Token으로 Access Token을 갱신한다.
    반환 예시:
      {"access_token": "...", "expires_in": 21599, "refresh_token": "...?"}
    """
    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise RuntimeError(f"토큰 갱신 실패 ({resp.status_code}): {data}")
    return data
