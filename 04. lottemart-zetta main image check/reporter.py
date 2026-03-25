"""
테스트 중 수집한 상품/행사 배너 관찰 데이터를 누적하고
세션 종료 시 요약/아티팩트로 출력하기 위한 보조 모듈.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))

_products: list[dict] = []
_banners: list[dict] = []
_product_keys: set[tuple] = set()
_banner_keys: set[tuple] = set()


def _normalize(v: str) -> str:
    return (v or "").replace("\n", " ").replace("\r", " ").strip()


def _safe_tsv(v) -> str:
    return str(v if v is not None else "").replace("\t", " ").replace("\n", " ").replace("\r", " ")


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
    """상품 관찰 데이터를 중복 없이 기록한다."""
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
    """행사/배너 관찰 데이터를 중복 없이 기록한다."""
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


def get_case_counts() -> dict:
    bucket: dict[str, dict] = defaultdict(lambda: {"products": 0, "banners": 0})

    for p in _products:
        bucket[p["case_id"]]["products"] += 1
    for b in _banners:
        bucket[b["case_id"]]["banners"] += 1

    return dict(bucket)


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
    엑셀 붙여넣기를 위해 TSV 헤더/행도 함께 출력한다.
    """
    lines: list[str] = []
    lines.append("[상세 수집 결과]")
    lines.append(build_count_line())

    case_counts = get_case_counts()
    lines.append("[케이스 집계]")
    if case_counts:
        lines.append("case_id\tproduct_count\tbanner_count")
        for case_id in sorted(case_counts):
            row = case_counts[case_id]
            lines.append(f"{case_id}\t{row['products']}\t{row['banners']}")
    else:
        lines.append("(none)")

    lines.append("[상품 TSV]")
    lines.append(
        "case_id\tproduct_name\tproduct_code\tproduct_price\tdiscount_amount\timage_ok\tpromotion_type\tsource_url"
    )
    for item in _products[:max_products]:
        lines.append(
            "\t".join(
                [
                    _safe_tsv(item["case_id"]),
                    _safe_tsv(item["product_name"]),
                    _safe_tsv(item["product_code"]),
                    _safe_tsv(item["product_price"]),
                    _safe_tsv(item["discount_amount"]),
                    _safe_tsv(item["image_ok"]),
                    _safe_tsv(item["promotion_type"] or "미분류"),
                    _safe_tsv(item["source_url"]),
                ]
            )
        )
    if len(_products) > max_products:
        lines.append(f"...외 {len(_products) - max_products}건")

    lines.append("[행사배너 TSV]")
    lines.append("case_id\tbanner_name\timage_ok\tsource_url")
    for item in _banners[:max_banners]:
        lines.append(
            "\t".join(
                [
                    _safe_tsv(item["case_id"]),
                    _safe_tsv(item["banner_name"]),
                    _safe_tsv(item["image_ok"]),
                    _safe_tsv(item["source_url"]),
                ]
            )
        )
    if len(_banners) > max_banners:
        lines.append(f"...외 {len(_banners) - max_banners}건")

    return lines


def write_artifacts(artifact_dir: Path) -> None:
    """
    수집 결과를 JSON/Markdown/CSV로 저장해 Actions 아티팩트로 확인 가능하게 한다.
    """
    artifact_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "counts": get_counts(),
        "case_counts": get_case_counts(),
        "products": _products,
        "banners": _banners,
    }

    json_path = artifact_dir / "observation-summary.json"
    md_path = artifact_dir / "observation-summary.md"
    csv_path = artifact_dir / "observation-summary.csv"

    with json_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    # Markdown
    lines = ["# Observation Summary", ""]
    lines.append(f"- {build_count_line()}")
    lines.append("")
    lines.append("## Case Counts")
    lines.append("| case_id | product_count | banner_count |")
    lines.append("|---|---:|---:|")
    case_counts = get_case_counts()
    if case_counts:
        for case_id in sorted(case_counts):
            row = case_counts[case_id]
            lines.append(f"| {case_id} | {row['products']} | {row['banners']} |")
    else:
        lines.append("| - | 0 | 0 |")

    lines.append("")
    lines.append("## Products")
    lines.append("| case_id | product_name | product_code | product_price | discount_amount | image_ok | promotion_type | source_url |")
    lines.append("|---|---|---|---:|---:|---|---|---|")
    if _products:
        for p in _products:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _safe_tsv(p["case_id"]),
                        _safe_tsv(p["product_name"]),
                        _safe_tsv(p["product_code"]),
                        _safe_tsv(p["product_price"]),
                        _safe_tsv(p["discount_amount"]),
                        _safe_tsv(p["image_ok"]),
                        _safe_tsv(p["promotion_type"]),
                        _safe_tsv(p["source_url"]),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | - | - | - | - | - | - |")

    lines.append("")
    lines.append("## Banners")
    lines.append("| case_id | banner_name | image_ok | source_url |")
    lines.append("|---|---|---|---|")
    if _banners:
        for b in _banners:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _safe_tsv(b["case_id"]),
                        _safe_tsv(b["banner_name"]),
                        _safe_tsv(b["image_ok"]),
                        _safe_tsv(b["source_url"]),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | - | - |")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    # CSV (엑셀 바로 열기용)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "record_type",
                "case_id",
                "name",
                "product_code",
                "product_price",
                "discount_amount",
                "image_ok",
                "promotion_type",
                "source_url",
            ]
        )
        for p in _products:
            writer.writerow(
                [
                    "product",
                    p["case_id"],
                    p["product_name"],
                    p["product_code"],
                    p["product_price"],
                    p["discount_amount"],
                    p["image_ok"],
                    p["promotion_type"],
                    p["source_url"],
                ]
            )
        for b in _banners:
            writer.writerow(
                [
                    "banner",
                    b["case_id"],
                    b["banner_name"],
                    "",
                    "",
                    "",
                    b["image_ok"],
                    "",
                    b["source_url"],
                ]
            )
