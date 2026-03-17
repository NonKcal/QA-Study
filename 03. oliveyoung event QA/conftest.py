"""
conftest.py
─────────────────────────────────────────────────────────────────────────────
pytest 공통 픽스처 및 카카오톡 결과 전송 훅
 - 브라우저: Chromium (PC Chrome DevTools → iPhone 14 Pro Max 에뮬레이션)
 - 카카오톡: 전체 테스트 완료 후 나에게 보내기로 결과 전송
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import textwrap
from datetime import datetime, timezone, timedelta
from typing  import Generator

import pytest
import requests
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

# ── 상수 ──────────────────────────────────────────────────────────────────
# iPhone 14 Pro Max 디바이스 스펙 (Playwright 내장 디바이스 없으므로 수동 정의)
IPHONE_14_PRO_MAX = {
    "viewport":           {"width": 430, "height": 932},
    "device_scale_factor": 3,
    "is_mobile":          True,
    "has_touch":          True,
    "user_agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
}

KST = timezone(timedelta(hours=9))

# ── 결과 수집용 전역 컨테이너 ─────────────────────────────────────────────
_results: list[dict] = []   # {"name": ..., "status": PASS|FAIL, "reason": ...}


# ═══════════════════════════════════════════════════════════════════════════
# Playwright 픽스처 (session scope → 전체 테스트에서 브라우저 1회 기동)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Generator[Browser, None, None]:
    """Headless Chromium — CI 환경 대응"""
    br = playwright_instance.chromium.launch(headless=True)
    yield br
    br.close()


@pytest.fixture(scope="session")
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """
    iPhone 14 Pro Max 에뮬레이션 컨텍스트
    PC Chrome DevTools > 디바이스 에뮬레이션과 동일한 조건
    """
    ctx = browser.new_context(**IPHONE_14_PRO_MAX)
    yield ctx
    ctx.close()


@pytest.fixture()
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """각 테스트 함수마다 새 탭 — 컨텍스트(세션/쿠키)는 공유"""
    pg = context.new_page()
    yield pg
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# 결과 수집 훅
# ═══════════════════════════════════════════════════════════════════════════

def _collect(item: pytest.Item, call: pytest.CallInfo) -> None:
    """테스트 결과를 _results 에 누적"""
    status = "PASS" if call.excinfo is None else "FAIL"
    reason = ""
    if call.excinfo:
        reason = str(call.excinfo.value)[:120]   # 너무 길면 잘라냄

    _results.append({
        "name":   item.name,
        "status": status,
        "reason": reason,
    })


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report  = outcome.get_result()
    if report.when == "call":
        _collect(item, call)


# ═══════════════════════════════════════════════════════════════════════════
# 카카오톡 전송 (세션 종료 후 1회)
# ═══════════════════════════════════════════════════════════════════════════

def _build_message() -> str:
    """결과 요약 메시지 작성"""
    now      = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    total    = len(_results)
    passed   = sum(1 for r in _results if r["status"] == "PASS")
    failed   = total - passed

    lines = [
        f"🟢 올리브영 이벤트 QA 결과",
        f"📅 {now}",
        f"총 {total}건 | ✅ {passed} PASS | ❌ {failed} FAIL",
        "─" * 30,
    ]

    for r in _results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        line = f"{icon} {r['name']}"
        if r["reason"]:
            # 실패 사유 2줄까지만 표기 (카톡 메시지 길이 제한 고려)
            reason_short = textwrap.shorten(r["reason"], width=60, placeholder="…")
            line += f"\n   └ {reason_short}"
        lines.append(line)

    return "\n".join(lines)


def _send_kakao(message: str) -> None:
    """
    카카오 나에게 보내기 API
    ※ link 필드 요구사항:
      - web_url과 mobile_web_url 모두 등록된 도메인이어야 함
      - 카카오 개발자센터 > 앱 설정 > 플랫폼 > Web에
        해당 도메인이 등록되어 있어야 클릭 시 정상 이동
    """
    import json

    access_token = os.environ.get("KAKAO_ACCESS_TOKEN", "")
    if not access_token:
        print("[카카오] KAKAO_ACCESS_TOKEN 미설정 — 전송 스킵")
        return

    # GitHub Actions 실행 결과 URL (runs 페이지 직접 링크)
    gh_repo       = os.environ.get("GH_REPO", "")
    gh_run_id     = os.environ.get("GITHUB_RUN_ID", "")
    if gh_repo and gh_run_id:
        # GitHub Actions 실행 결과 페이지로 직접 링크
        result_url = f"https://github.com/{gh_repo}/actions/runs/{gh_run_id}"
    else:
        result_url = "https://www.oliveyoung.co.kr"

    template = {
        "object_type": "text",
        "text": message,
        "link": {
            # web_url, mobile_web_url 모두 동일 URL로 설정
            # → 카카오 개발자센터에 github.com 도메인 등록 필요
            "web_url":        result_url,
            "mobile_web_url": result_url,
        },
        "button_title": "결과 확인하기",  # 링크 버튼 텍스트
    }

    resp = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10,
    )
    if resp.status_code == 200:
        print("[카카오] 결과 전송 완료 ✅")
    else:
        print(f"[카카오] 전송 실패 {resp.status_code}: {resp.text}")


def pytest_sessionfinish(session, exitstatus):
    """모든 테스트 완료 후 카카오톡으로 결과 전송"""
    if not _results:
        return
    msg = _build_message()
    print("\n" + msg)   # GitHub Actions 로그에도 출력
    _send_kakao(msg)
