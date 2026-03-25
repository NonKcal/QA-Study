"""
pytest 공통 픽스처 + 카카오톡 결과 전송 훅.

핵심 요구사항 반영:
  - 브라우저: PC Chrome(Chromium) 기반
  - 디바이스 모드: iPhone 14 Pro Max 에뮬레이션
  - 결과 전송: 카카오 나에게 보내기
  - 토큰 만료 대응: 전송 실패(401 등) 시 refresh token으로 자동 재발급 후 재시도
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import pytest
import requests
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from kakao_oauth import refresh_access_token


KST = timezone(timedelta(hours=9))
ARTIFACT_DIR = Path(__file__).parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# PC Chrome에서 DevTools 모바일 디바이스 모드와 동일한 형태를 만들기 위한 프로파일.
IPHONE_14_PRO_MAX = {
    "viewport": {"width": 430, "height": 932},
    "device_scale_factor": 3,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "CriOS/120.0.0.0 Mobile/15E148 Safari/604.1"
    ),
}

# CI 안정성/자동화 감지 최소화를 위한 Chromium 인자.
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--window-size=430,932",
]

# 테스트 결과 집계 버퍼 (카카오 전송용)
_results: list[dict] = []


@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Generator[Browser, None, None]:
    browser_obj = playwright_instance.chromium.launch(
        headless=True,
        args=STEALTH_ARGS,
    )
    yield browser_obj
    browser_obj.close()


@pytest.fixture(scope="session")
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    context_obj = browser.new_context(
        **IPHONE_14_PRO_MAX,
        locale="ko-KR",
        extra_http_headers={
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    # 일부 사이트의 단순 자동화 탐지(navigator.webdriver) 회피.
    context_obj.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        window.chrome = window.chrome || { runtime: {} };
        """
    )
    yield context_obj
    context_obj.close()


@pytest.fixture()
def page(context: BrowserContext) -> Generator[Page, None, None]:
    test_page = context.new_page()
    yield test_page
    test_page.close()


def _collect_result(item: pytest.Item, call: pytest.CallInfo) -> None:
    status = "PASS" if call.excinfo is None else "FAIL"
    reason = ""
    if call.excinfo:
        reason = str(call.excinfo.value)

    _results.append(
        {
            "name": item.name,
            "status": status,
            "reason": textwrap.shorten(reason, width=160, placeholder="..."),
        }
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        _collect_result(item, call)

        # 실패 시점의 화면을 아티팩트로 남겨 원인 분석 시간을 줄인다.
        if report.failed:
            page_obj = item.funcargs.get("page")
            if page_obj:
                file_name = f"{item.name}.png".replace("/", "_").replace("\\", "_")
                screenshot_path = ARTIFACT_DIR / file_name
                try:
                    page_obj.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    pass


def _build_result_message() -> str:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    total = len(_results)
    passed = sum(1 for r in _results if r["status"] == "PASS")
    failed = total - passed

    lines = [
        "[롯데마트 제타] 메인 노출 자동화 결과",
        f"실행 시각: {now}",
        f"총 {total}건 | PASS {passed} | FAIL {failed}",
        "-" * 35,
    ]

    for row in _results:
        icon = "OK" if row["status"] == "PASS" else "NG"
        line = f"[{icon}] {row['name']}"
        if row["reason"]:
            line += f" | {row['reason']}"
        lines.append(line)

    return "\n".join(lines)


def _build_run_url() -> str:
    gh_repo = os.getenv("GH_REPO", "").strip()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if gh_repo and run_id:
        return f"https://github.com/{gh_repo}/actions/runs/{run_id}"
    return "https://lottemartzetta.com/"


def _send_kakao_message(access_token: str, message: str) -> requests.Response:
    template = {
        "object_type": "text",
        "text": message[:2000],  # 카카오 텍스트 템플릿 제한 대응
        "link": {
            "web_url": _build_run_url(),
            "mobile_web_url": _build_run_url(),
        },
        "button_title": "실행 결과 보기",
    }
    return requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=15,
    )


def _refresh_token_for_retry() -> str | None:
    """
    카카오 전송 실패 시 토큰을 즉시 재발급해 같은 실행 내에서 재시도한다.
    """
    rest_api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    client_secret = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("KAKAO_REFRESH_TOKEN", "").strip()
    if not (rest_api_key and client_secret and refresh_token):
        return None

    try:
        token_data = refresh_access_token(
            rest_api_key=rest_api_key,
            client_secret=client_secret,
            refresh_token=refresh_token,
        )
        os.environ["KAKAO_ACCESS_TOKEN"] = token_data["access_token"]
        if token_data.get("refresh_token"):
            os.environ["KAKAO_REFRESH_TOKEN"] = token_data["refresh_token"]
        return token_data["access_token"]
    except Exception as exc:
        print(f"[카카오] 재발급 실패: {exc}")
        return None


def _notify_to_kakao(message: str) -> None:
    access_token = os.getenv("KAKAO_ACCESS_TOKEN", "").strip()
    if not access_token:
        print("[카카오] KAKAO_ACCESS_TOKEN 미설정으로 전송 스킵")
        return

    first_resp = _send_kakao_message(access_token, message)
    if first_resp.status_code == 200:
        print("[카카오] 결과 전송 성공")
        return

    response_text = first_resp.text.lower()
    should_retry = (
        first_resp.status_code in (400, 401)
        and ("invalid_token" in response_text or "expired" in response_text)
    )

    if not should_retry:
        print(f"[카카오] 전송 실패 ({first_resp.status_code}): {first_resp.text}")
        return

    print("[카카오] 토큰 만료 의심 -> 재발급 후 재전송 시도")
    renewed_token = _refresh_token_for_retry()
    if not renewed_token:
        print("[카카오] 재전송 불가 (재발급 실패)")
        return

    second_resp = _send_kakao_message(renewed_token, message)
    if second_resp.status_code == 200:
        print("[카카오] 재발급 후 전송 성공")
    else:
        print(f"[카카오] 재전송 실패 ({second_resp.status_code}): {second_resp.text}")


def pytest_sessionfinish(session, exitstatus):
    if not _results:
        return

    message = _build_result_message()
    print("\n" + message)  # Actions 로그에서도 바로 확인 가능
    _notify_to_kakao(message)
