"""
카카오 토큰 갱신 + GitHub Secrets 자동 업데이트.

역할:
  1) KAKAO_REFRESH_TOKEN 으로 Access Token 갱신
  2) 갱신 결과를 GitHub Secrets에 반영
     - KAKAO_ACCESS_TOKEN: 항상 업데이트
     - KAKAO_REFRESH_TOKEN: 카카오가 새 값 반환한 경우만 업데이트
"""

from __future__ import annotations

import os
import sys

import requests
from nacl import encoding, public

from kakao_oauth import refresh_access_token


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


def _get_repo_public_key(repo: str, headers: dict) -> dict:
    """GitHub Actions Secret 암호화를 위한 저장소 공개키를 조회한다."""
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _encrypt_secret(public_key_str: str, secret_value: str) -> str:
    """
    GitHub Secret 업로드 요구사항에 맞춰 libsodium sealed box 로 암호화한다.
    평문 토큰을 네트워크로 직접 전송하지 않기 위해 반드시 암호화 과정을 거친다.
    """
    public_key = public.PublicKey(public_key_str.encode(), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode(), encoding.Base64Encoder())
    return encrypted.decode()


def update_github_secret(secret_name: str, secret_value: str) -> None:
    """단일 GitHub Secret 값을 안전하게 업데이트한다."""
    repo = _required_env("GH_REPO")
    token = _required_env("GH_PAT")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Accept": "application/vnd.github+json",
    }

    pub_key_data = _get_repo_public_key(repo, headers)
    encrypted = _encrypt_secret(pub_key_data["key"], secret_value)

    resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={
            "encrypted_value": encrypted,
            "key_id": pub_key_data["key_id"],
        },
        timeout=15,
    )
    resp.raise_for_status()
    print(f"[GitHub] {secret_name} 업데이트 완료")


def main() -> int:
    try:
        token_data = refresh_access_token(
            rest_api_key=_required_env("KAKAO_REST_API_KEY"),
            client_secret=_required_env("KAKAO_CLIENT_SECRET"),
            refresh_token=_required_env("KAKAO_REFRESH_TOKEN"),
        )
        print("[Kakao] Access Token 갱신 성공")

        update_github_secret("KAKAO_ACCESS_TOKEN", token_data["access_token"])

        if "refresh_token" in token_data and token_data["refresh_token"]:
            update_github_secret("KAKAO_REFRESH_TOKEN", token_data["refresh_token"])
            print("[Kakao] Refresh Token 갱신분 반영 완료")
        else:
            print("[Kakao] Refresh Token 유지 (변경 없음)")

        return 0

    except Exception as exc:
        print(f"[오류] refresh_token.py 실패: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
