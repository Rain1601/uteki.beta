from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/alphabet_2025_business_map/v0.2-candidate"
TARGET = ROOT / "benchmarks/alphabet_2025_business_map/v0.3-candidate"


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def business_nodes() -> list[dict[str, Any]]:
    return [
        {
            "id": "google-subscriptions",
            "name": "Google subscriptions",
            "kind": "offering_group",
            "description": "Consumer subscription activities within Google Services, including YouTube subscription offerings and Google One.",
            "products_services": ["YouTube TV", "YouTube Music and Premium", "NFL Sunday Ticket", "Google One"],
            "customers": ["consumers"],
            "monetization": [
                {
                    "description": "consumer subscription fees",
                    "basis": "explicit",
                    "evidence_ids": ["e-subscriptions"],
                }
            ],
            "importance_signals": ["included in a combined revenue line; no separate revenue disclosed"],
            "evidence_ids": ["e-services-other-revenue", "e-subscriptions", "e-revenue-table"],
            "review_status": "candidate",
        },
        {
            "id": "google-platforms",
            "name": "Google platforms",
            "kind": "offering_group",
            "description": "Platform activity within Google Services, including Google Play app sales and in-app purchases.",
            "products_services": ["Google Play"],
            "customers": ["consumers", "app developers"],
            "monetization": [
                {
                    "description": "Google Play app sales and in-app purchases",
                    "basis": "explicit",
                    "evidence_ids": ["e-platforms"],
                }
            ],
            "importance_signals": ["included in a combined revenue line; no separate revenue disclosed"],
            "evidence_ids": ["e-services-other-revenue", "e-platforms", "e-revenue-table"],
            "review_status": "candidate",
        },
        {
            "id": "google-devices",
            "name": "Google devices",
            "kind": "offering_group",
            "description": "Device activity within Google Services, including sales of the Pixel family of devices.",
            "products_services": ["Pixel devices"],
            "customers": ["consumers"],
            "monetization": [
                {
                    "description": "sales of the Pixel family of devices",
                    "basis": "explicit",
                    "evidence_ids": ["e-devices"],
                }
            ],
            "importance_signals": ["included in a combined revenue line; no separate revenue disclosed"],
            "evidence_ids": ["e-services-other-revenue", "e-devices", "e-revenue-table"],
            "review_status": "candidate",
        },
        {
            "id": "google-spd-revenue",
            "name": "Google subscriptions, platforms, and devices",
            "kind": "revenue_line",
            "description": "A combined financial disclosure line for Google Services revenue beyond advertising; it is not modeled as one operating business.",
            "products_services": [],
            "customers": [],
            "monetization": [],
            "importance_signals": ["2025 revenue: $48.030B"],
            "evidence_ids": [
                "e-services-other-revenue",
                "e-subscriptions",
                "e-platforms",
                "e-devices",
                "e-revenue-table",
            ],
            "review_status": "candidate",
        },
    ]


def business_relationships() -> list[dict[str, Any]]:
    relationships = [
        (
            "google-subscriptions",
            "google-services",
            "part_of",
            "Google subscriptions is a distinct non-advertising commercial activity described within Google Services.",
            ["e-services-other-revenue", "e-subscriptions"],
        ),
        (
            "google-platforms",
            "google-services",
            "part_of",
            "Google platforms is a distinct non-advertising commercial activity described within Google Services.",
            ["e-services-other-revenue", "e-platforms"],
        ),
        (
            "google-devices",
            "google-services",
            "part_of",
            "Google devices is a distinct non-advertising commercial activity described within Google Services.",
            ["e-services-other-revenue", "e-devices"],
        ),
        (
            "google-spd-revenue",
            "google-services",
            "revenue_component_of",
            "Subscriptions, platforms, and devices is a combined Google Services revenue line.",
            ["e-revenue-table"],
        ),
        (
            "google-subscriptions",
            "google-spd-revenue",
            "supports",
            "Subscription activity contributes to the combined subscriptions, platforms, and devices revenue line.",
            ["e-subscriptions", "e-revenue-table"],
        ),
        (
            "google-platforms",
            "google-spd-revenue",
            "supports",
            "Platform activity contributes to the combined subscriptions, platforms, and devices revenue line.",
            ["e-platforms", "e-revenue-table"],
        ),
        (
            "google-devices",
            "google-spd-revenue",
            "supports",
            "Device activity contributes to the combined subscriptions, platforms, and devices revenue line.",
            ["e-devices", "e-revenue-table"],
        ),
    ]
    return [
        {
            "source_id": source,
            "target_id": target,
            "kind": kind,
            "description": description,
            "evidence_ids": evidence_ids,
            "review_status": "candidate",
        }
        for source, target, kind, description, evidence_ids in relationships
    ]


def replacement_claims() -> list[dict[str, Any]]:
    return [
        {
            "id": "subscriptions-identity-parent",
            "business_id": "google-subscriptions",
            "field": "identity_parent",
            "label_en": "Identity & parent",
            "label_zh": "身份与归属",
            "value_en": "Consumer subscriptions are modeled as a distinct Google Services commercial activity.",
            "value_zh": "消费者订阅作为 Google Services 下独立的商业活动建模。",
            "basis": "derived",
            "evidence_ids": ["e-subscriptions"],
        },
        {
            "id": "subscriptions-description",
            "business_id": "google-subscriptions",
            "field": "description",
            "label_en": "Products and services",
            "label_zh": "产品与服务",
            "value_en": "YouTube TV · YouTube Music and Premium · NFL Sunday Ticket · Google One",
            "value_zh": "YouTube TV · YouTube Music and Premium · NFL Sunday Ticket · Google One",
            "basis": "explicit",
            "evidence_ids": ["e-subscriptions"],
        },
        {
            "id": "subscriptions-monetization",
            "business_id": "google-subscriptions",
            "field": "monetization",
            "label_en": "Monetization",
            "label_zh": "变现方式",
            "value_en": "Consumer subscription revenue from YouTube services and Google One.",
            "value_zh": "来自 YouTube 服务和 Google One 的消费者订阅收入。",
            "basis": "explicit",
            "evidence_ids": ["e-subscriptions"],
        },
        {
            "id": "platforms-identity-parent",
            "business_id": "google-platforms",
            "field": "identity_parent",
            "label_en": "Identity & parent",
            "label_zh": "身份与归属",
            "value_en": "Platforms are modeled as a distinct Google Services commercial activity.",
            "value_zh": "平台业务作为 Google Services 下独立的商业活动建模。",
            "basis": "derived",
            "evidence_ids": ["e-platforms"],
        },
        {
            "id": "platforms-description",
            "business_id": "google-platforms",
            "field": "description",
            "label_en": "Products and services",
            "label_zh": "产品与服务",
            "value_en": "Google Play app sales and in-app purchases.",
            "value_zh": "Google Play 应用销售和应用内购买。",
            "basis": "explicit",
            "evidence_ids": ["e-platforms"],
        },
        {
            "id": "platforms-monetization",
            "business_id": "google-platforms",
            "field": "monetization",
            "label_en": "Monetization",
            "label_zh": "变现方式",
            "value_en": "Revenue from Google Play app sales and in-app purchases.",
            "value_zh": "来自 Google Play 应用销售和应用内购买的收入。",
            "basis": "explicit",
            "evidence_ids": ["e-platforms"],
        },
        {
            "id": "devices-identity-parent",
            "business_id": "google-devices",
            "field": "identity_parent",
            "label_en": "Identity & parent",
            "label_zh": "身份与归属",
            "value_en": "Devices are modeled as a distinct Google Services commercial activity.",
            "value_zh": "设备业务作为 Google Services 下独立的商业活动建模。",
            "basis": "derived",
            "evidence_ids": ["e-devices"],
        },
        {
            "id": "devices-description",
            "business_id": "google-devices",
            "field": "description",
            "label_en": "Products and services",
            "label_zh": "产品与服务",
            "value_en": "Pixel family of devices.",
            "value_zh": "Pixel 系列设备。",
            "basis": "explicit",
            "evidence_ids": ["e-devices"],
        },
        {
            "id": "devices-monetization",
            "business_id": "google-devices",
            "field": "monetization",
            "label_en": "Monetization",
            "label_zh": "变现方式",
            "value_en": "Revenue from sales of the Pixel family of devices.",
            "value_zh": "来自 Pixel 系列设备销售的收入。",
            "basis": "explicit",
            "evidence_ids": ["e-devices"],
        },
        {
            "id": "spd-revenue-line-identity-parent",
            "business_id": "google-spd-revenue",
            "field": "identity_parent",
            "label_en": "Financial disclosure identity",
            "label_zh": "财务披露身份",
            "value_en": "Subscriptions, platforms, and devices is one combined Google Services revenue line, not one operating business.",
            "value_zh": "Subscriptions、Platforms and Devices 是 Google Services 的合并收入披露线，而不是单一经营业务。",
            "basis": "derived",
            "evidence_ids": ["e-services-other-revenue", "e-revenue-table"],
        },
        {
            "id": "spd-revenue-line-composition",
            "business_id": "google-spd-revenue",
            "field": "description",
            "label_en": "Disclosed composition",
            "label_zh": "披露组成",
            "value_en": "Consumer subscriptions · platforms · devices · other products and services",
            "value_zh": "消费者订阅 · 平台 · 设备 · 其他产品与服务",
            "basis": "explicit",
            "evidence_ids": ["e-services-other-revenue", "e-subscriptions", "e-platforms", "e-devices"],
        },
        {
            "id": "spd-revenue-line-revenue-2025",
            "business_id": "google-spd-revenue",
            "field": "revenue_2025",
            "label_en": "2025 combined revenue",
            "label_zh": "2025 年合并收入",
            "value_en": "$48.030B",
            "value_zh": "$48.030B",
            "basis": "explicit",
            "evidence_ids": ["e-revenue-table"],
        },
    ]


def replacement_spans() -> list[dict[str, str]]:
    short = {
        "e-services-other-revenue": (
            "products and services beyond advertising, including:",
            "广告以外的产品和服务中获得收入，包括：",
        ),
        "e-subscriptions": ("consumer subscriptions", "消费者订阅"),
        "e-platforms": ("platforms", "平台"),
        "e-devices": ("devices", "设备"),
        "e-revenue-table": (
            "Google subscriptions, platforms, and devices 40,340 48,030",
            "Google subscriptions, platforms, and devices 40,340 48,030",
        ),
    }
    full = {
        "e-subscriptions": (
            "YouTube TV, YouTube Music and Premium, and NFL Sunday Ticket, as well as Google One",
            "YouTube TV、YouTube Music and Premium 和 NFL Sunday Ticket 等 YouTube 服务的收入，以及 Google One 的收入",
        ),
        "e-platforms": (
            "Google Play sales of apps and in-app purchases",
            "Google Play 的应用销售和应用内购买收入",
        ),
        "e-devices": (
            "sales of the Pixel family of devices",
            "Pixel 系列设备的销售",
        ),
    }
    mapping = {
        "subscriptions-identity-parent": [("e-subscriptions", short["e-subscriptions"])],
        "subscriptions-description": [("e-subscriptions", full["e-subscriptions"])],
        "subscriptions-monetization": [("e-subscriptions", full["e-subscriptions"])],
        "platforms-identity-parent": [("e-platforms", short["e-platforms"])],
        "platforms-description": [("e-platforms", full["e-platforms"])],
        "platforms-monetization": [("e-platforms", full["e-platforms"])],
        "devices-identity-parent": [("e-devices", short["e-devices"])],
        "devices-description": [("e-devices", full["e-devices"])],
        "devices-monetization": [("e-devices", full["e-devices"])],
        "spd-revenue-line-identity-parent": [
            ("e-services-other-revenue", short["e-services-other-revenue"]),
            ("e-revenue-table", short["e-revenue-table"]),
        ],
        "spd-revenue-line-composition": [
            ("e-services-other-revenue", short["e-services-other-revenue"]),
            ("e-subscriptions", short["e-subscriptions"]),
            ("e-platforms", short["e-platforms"]),
            ("e-devices", short["e-devices"]),
        ],
        "spd-revenue-line-revenue-2025": [("e-revenue-table", short["e-revenue-table"])],
    }
    return [
        {"claim_id": claim_id, "evidence_id": evidence_id, "quote_en": quote[0], "quote_zh": quote[1]}
        for claim_id, items in mapping.items()
        for evidence_id, quote in items
    ]


def build() -> None:
    business_map = json.loads((SOURCE / "business_map.json").read_text(encoding="utf-8"))
    business_map["schema_version"] = "0.3-candidate"
    business_map["summary"] = (
        "Alphabet reports Google through Google Services and Google Cloud, and reports non-Google businesses "
        "collectively as Other Bets. Business ontology and financial disclosure are separated: subscriptions, "
        "platforms, and devices are three commercial nodes, while their revenue remains one combined line."
    )
    old_index = next(i for i, item in enumerate(business_map["businesses"]) if item["id"] == "google-spd")
    business_map["businesses"][old_index : old_index + 1] = business_nodes()
    business_map["relationships"] = [
        item for item in business_map["relationships"] if item["source_id"] != "google-spd"
    ]
    insert_at = next(
        i for i, item in enumerate(business_map["relationships"]) if item["source_id"] == "google-cloud"
    )
    business_map["relationships"][insert_at:insert_at] = business_relationships()
    business_map["metadata"].update(
        {
            "benchmark_version": "v0.3-candidate",
            "granularity_profile": "dual_business_and_financial",
            "dual_structure_decision": "d-spd-dual-structure",
        }
    )

    claims_document = json.loads((SOURCE / "claims.json").read_text(encoding="utf-8"))
    claims_document["schema_version"] = "0.3-candidate"
    claims_document["benchmark_id"] = "alphabet-2025-business-map-v0.3-candidate"
    claims_document["claims"] = [
        item for item in claims_document["claims"] if not item["id"].startswith("spd-")
    ] + replacement_claims()

    spans_document = json.loads((SOURCE / "evidence_spans.json").read_text(encoding="utf-8"))
    spans_document["schema_version"] = "0.3-candidate"
    spans_document["spans"] = [
        item for item in spans_document["spans"] if not item["claim_id"].startswith("spd-")
    ] + replacement_spans()

    policy = json.loads((SOURCE / "benchmark_policy.json").read_text(encoding="utf-8"))
    policy["schema_version"] = "business-map-benchmark-policy-v0.3-candidate"
    policy["benchmark_id"] = "alphabet-2025-business-map-v0.3-candidate"
    replacement_policy = [
        {
            "business_id": item,
            "level": "L2",
            "requirement": "required",
            "reason": "separately described non-advertising commercial activity",
        }
        for item in ("google-subscriptions", "google-platforms", "google-devices")
    ] + [
        {
            "business_id": "google-spd-revenue",
            "level": "L3",
            "requirement": "required",
            "reason": "combined financial disclosure line; not an operating-business node",
        }
    ]
    policy_index = next(i for i, item in enumerate(policy["node_policy"]) if item["business_id"] == "google-spd")
    policy["node_policy"][policy_index : policy_index + 1] = replacement_policy
    policy["allowed_mentions"] = [item for item in policy["allowed_mentions"] if item["parent_id"] != "google-spd"]
    policy["allowed_mentions"][1:1] = [
        {
            "parent_id": "google-subscriptions",
            "names": ["YouTube TV", "YouTube Music and Premium", "NFL Sunday Ticket", "Google One"],
        },
        {"parent_id": "google-platforms", "names": ["Google Play"]},
        {"parent_id": "google-devices", "names": ["Pixel devices"]},
    ]
    policy["relationship_policy"] = {
        "hierarchy_kinds": ["reported_under", "part_of", "revenue_component_of"],
        "cross_view_kinds": ["supports"],
        "rule": "A supports edge connects a business node to a financial disclosure line and is not a parent edge.",
    }

    decisions = copy.deepcopy(json.loads((SOURCE / "review_decisions.json").read_text(encoding="utf-8")))
    decisions["benchmark_version"] = "v0.3-candidate"
    for decision in decisions["decisions"]:
        if decision["decision_id"] == "d-spd-dual-structure":
            decision["status"] = "applied_in_candidate"
            decision["applied_in_version"] = "v0.3-candidate"

    TARGET.mkdir(parents=True, exist_ok=True)
    write_json(TARGET / "business_map.json", business_map)
    write_json(TARGET / "claims.json", claims_document)
    write_json(TARGET / "evidence_spans.json", spans_document)
    write_json(TARGET / "benchmark_policy.json", policy)
    write_json(TARGET / "review_decisions.json", decisions)


if __name__ == "__main__":
    build()
