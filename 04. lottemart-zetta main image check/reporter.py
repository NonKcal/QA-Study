"""
테스트 중 수집한 상품/행사 배너 관찰 데이터를 누적하고
세션 종료 시 요약/아티팩트로 출력하기 위한 보조 모듈.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))

_products: list[dict] = []
_banners: list[dict] = []
_product_keys: set[tuple] = set()
_banner_keys: set[tuple] = set()


def _normalize(v: str) -> str:
    return (v or "").replace("\n", " ").replace("\r", " ").strip()


def record_product(
    *,
    case_id: str,
    product_name: str,
    product_code: str,
    product_price: int | None,
    discount_amount: int | None,
    image_ok: bool,
    source_url: str,
    promotion_type: str | None,
) -> None:
    """
    상품 관찰 데이터를 중복 없이 기록한다.
    """
    key = (case_id, product_code, source_url)
    if key in _product_keys:
        return
    _product_keys.add(key)

    _products.append(
        {
            "case_id": _normalize(case_id),
            "product_name": _normalize(product_name),
            "product_code": _normalize(product_code),
            "product_price": product_price,
            "discount_amount": discount_amount,
            "image_ok": bool(image_ok),
            "source_url": _normalize(source_url),
            "promotion_type": _normalize(promotion_type or ""),
        }
    )


def record_banner(
    *,
    case_id: str,
    banner_name: str,
    image_ok: bool,
    source_url: str,
) -> None:
    """
    행사/배너 관찰 데이터를 중복 없이 기록한다.
    """
    key = (case_id, banner_name, source_url)
    if key in _banner_keys:
        return
    _banner_keys.add(key)

    _banners.append(
        {
            "case_id": _normalize(case_id),
            "banner_name": _normalize(banner_name),
            "image_ok": bool(image_ok),
            "source_url": _normalize(source_url),
        }
    )


def get_counts() -> dict:
    return {
        "product_count": len(_products),
        "banner_count": len(_banners),
    }


def build_count_line() -> str:
    c = get_counts()
    return f"수집 집계 | 상품 {c['product_count']}건 | 행사/배너 {c['banner_count']}건"


def build_console_lines(
    *,
    max_products: int = 20,
    max_banners: int = 20,
) -> list[str]:
    """
    Actions 로그에 바로 보일 수 있도록 라인 단위 문자열을 생성한다.
    """
    lines: list[str] = []
    lines.append("[상세 수집 결과]")
    lines.append(build_count_line())

    lines.append("- 상품 상세")
    for item in _products[:max_products]:
        price_txt = "N/A" if item["product_price"] is None else f"{item['product_price']:,}원"
        discount_txt = (
            "N/A" if item["discount_amount"] is None else f"{item['discount_amount']:,}원"
        )
        image_txt = "OK" if item["image_ok"] else "NG"
        promo_txt = item["promotion_type"] or "미분류"
        lines.append(
            f"  [{item['case_id']}] {item['product_name']} "
            f"(코드:{item['product_code']}) | 금액:{price_txt} | 할인금액:{discount_txt} | "
            f"이미지:{image_txt} | 행사유형:{promo_txt}"
        )

    if len(_products) > max_products:
        lines.append(f"  ... 외 {len(_products) - max_products}건")

    lines.append("- 행사/배너 상세")
    for item in _banners[:max_banners]:
        image_txt = "OK" if item["image_ok"] else "NG"
        lines.append(
            f"  [{item['case_id']}] {item['banner_name']} | 이미지:{image_txt} | URL:{item['source_url']}"
        )

    if len(_banners) > max_banners:
        lines.append(f"  ... 외 {len(_banners) - max_banners}건")

    return lines


def write_artifacts(artifact_dir: Path) -> None:
    """
    수집 결과를 JSON/Markdown으로 저장해 Actions 아티팩트로 확인 가능하게 한다.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "counts": get_counts(),
        "products": _products,
        "banners": _banners,
    }

    json_path = artifact_dir / "observation-summary.json"
    md_path = artifact_dir / "observation-summary.md"

    with json_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    lines = ["# Observation Summary", ""]
    lines.append(f"- {build_count_line()}")
    lines.append("")
    lines.append("## Products")
    if _products:
        for p in _products:
            lines.append(
                f"- [{p['case_id']}] {p['product_name']} | "
                f"code={p['product_code']} | price={p['product_price']} | "
                f"discount_amount={p['discount_amount']} | image_ok={p['image_ok']} | "
                f"promotion_type={p['promotion_type']}"
            )
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("## Banners")
    if _banners:
        for b in _banners:
            lines.append(
                f"- [{b['case_id']}] {b['banner_name']} | image_ok={b['image_ok']} | url={b['source_url']}"
            )
    else:
        lines.append("- (none)")

    md_path.write_text("\n".join(lines), encoding="utf-8")
