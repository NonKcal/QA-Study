"""
카카오 토큰 갱신 + GitHub Secrets 자동 업데이트
─────────────────────────────────────────────
단일 책임: 토큰 갱신만 담당 (테스트 로직 없음)
실행 시점: YML STEP 5 → test_oliveyoung_search.py 보다 먼저 실행

필요 환경변수 (GitHub Secrets):
  KAKAO_REST_API_KEY   : 카카오 REST API 키
  KAKAO_CLIENT_SECRET  : 카카오 클라이언트 시크릿
  KAKAO_REFRESH_TOKEN  : 카카오 리프레시 토큰
  GH_PAT               : GitHub Personal Access Token (secrets:write 권한)
  GH_REPO              : GitHub 저장소 (github.repository 자동 주입)
"""

import os
import sys
import requests
from base64 import b64encode
from nacl import encoding, public  # PyNaCl


# ──────────────────────────────────────────────
# 카카오 토큰 갱신
# ──────────────────────────────────────────────
def refresh_kakao_token() -> dict:
    """
    Refresh Token으로 새 Access Token 발급
    반환: {"access_token": "...", "refresh_token": "..."(갱신된 경우만)}
    """
    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type":    "refresh_token",
            "client_id":     os.environ["KAKAO_REST_API_KEY"],
            "client_secret": os.environ["KAKAO_CLIENT_SECRET"],
            "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
        },
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"[카카오] 토큰 갱신 실패 {resp.status_code}: {resp.text}")
        sys.exit(1)  # 토큰 갱신 실패 시 이후 테스트 실행 의미 없음

    data = resp.json()
    print("[카카오] Access Token 갱신 성공 ✅")

    if "refresh_token" in data:
        print("[카카오] Refresh Token도 갱신됨 ✅")
    else:
        print("[카카오] Refresh Token 유효 — 유지")

    return data


# ──────────────────────────────────────────────
# GitHub Secrets 자동 업데이트
# ──────────────────────────────────────────────
def _get_repo_public_key(repo: str, headers: dict) -> dict:
    """Secrets 암호화에 필요한 저장소 공개키 조회"""
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _encrypt_secret(public_key_str: str, secret_value: str) -> str:
    """GitHub 요구사항: libsodium sealed box 방식으로 암호화"""
    pub_key = public.PublicKey(
        public_key_str.encode(), encoding.Base64Encoder()
    )
    sealed = public.SealedBox(pub_key).encrypt(
        secret_value.encode(), encoding.Base64Encoder()
    )
    return sealed.decode()


def update_github_secret(secret_name: str, secret_value: str) -> None:
    """GitHub Actions Secret 값 업데이트"""
    repo  = os.environ["GH_REPO"]
    token = os.environ["GH_PAT"]
    headers = {
        "Authorization":        f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Accept":               "application/vnd.github+json",
    }

    # 1. 저장소 공개키 조회
    pub_key_data = _get_repo_public_key(repo, headers)

    # 2. 값 암호화
    encrypted = _encrypt_secret(pub_key_data["key"], secret_value)

    # 3. Secret 업데이트
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={
            "encrypted_value": encrypted,
            "key_id":          pub_key_data["key_id"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    print(f"[GitHub] {secret_name} 업데이트 완료 ✅")


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  카카오 토큰 갱신 시작")
    print("=" * 50)

    # 1. 카카오 토큰 갱신
    token_data = refresh_kakao_token()

    # 2. Access Token → GitHub Secrets 업데이트 (항상)
    update_github_secret("KAKAO_ACCESS_TOKEN", token_data["access_token"])

    # 3. Refresh Token → 갱신된 경우에만 업데이트
    if "refresh_token" in token_data:
        update_github_secret("KAKAO_REFRESH_TOKEN", token_data["refresh_token"])

    print("=" * 50)
    print("  토큰 갱신 완료 — 테스트 실행으로 이동")
    print("=" * 50)


if __name__ == "__main__":
    main()
