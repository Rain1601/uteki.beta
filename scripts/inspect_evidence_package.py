"""Render a validated evidence package as a new, readable Markdown report."""
import argparse
from collections import Counter
import html
from pathlib import Path
import json

from uteki.domain.research_data.evidence_package import EvidencePackage


KIND_LABELS = {
    "source_text": "原始文本", "source_table": "原始表格", "source_quote": "来源引语",
    "image_reference": "图片引用", "normalized_record": "归一化记录",
    "computed_scalar": "确定性计算", "model_extract": "模型原始提取输出", "model_summary": "模型摘要",
}
COVERAGE_LABELS = {
    "body_returned": ("正文已返回", "仅列出的完整文本/表格块已经返回；不能据此推断全文或语义完整。"),
    "provenance_only": ("仅来源追溯", "保留出处或引语；不能据此声称周边正文已读。"),
    "navigation_only": ("仅导航", "目录或搜索定位信息；不计入正文阅读。"),
    "image_reference_only": ("仅图片引用", "只有图片引用或字节校验信息；不代表已执行 OCR 或视觉理解。"),
}


def _cell(value):
    """Keep source strings as text rather than interpreting Markdown or HTML."""
    if value is None:
        return "未知"
    text = html.escape(str(value), quote=False)
    for old, new in (("\\", "\\\\"), ("|", "\\|"), ("`", "\\`"), ("[", "\\["),
                     ("]", "\\]"), ("*", "\\*"), ("_", "\\_")):
        text = text.replace(old, new)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _joined(values, empty="未记录"):
    return "、".join(dict.fromkeys(str(value) for value in values if value is not None)) or empty


def _pages(locators):
    reported = _joined(loc.reported_page for loc in locators)
    pdf = _joined(loc.pdf_page for loc in locators)
    return f"原刊页：{reported}；PDF 页：{pdf}"


def _quote(text):
    # Every source line remains present. Escaping is presentation-only.
    return "\n".join("> " + _cell(line) for line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _fields(value, prefix=""):
    """Show model payload fields without embedding an opaque JSON document."""
    if isinstance(value, dict):
        if not value:
            yield prefix or "输出", "空对象"
        for key, item in value.items():
            yield from _fields(item, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, (list, tuple)):
        if not value:
            yield prefix or "输出", "空列表"
        for index, item in enumerate(value):
            yield from _fields(item, f"{prefix}[{index}]")
    else:
        yield prefix or "输出", "null（模型原输出）" if value is None else value


def _period(record):
    if record.period is None:
        return record.period_resolution
    period = record.period
    dates = f"{period.start} → {period.end}" if period.start is not None else str(period.end)
    return f"{period.kind} · {dates}"


def _value(record):
    value = record.value_decimal
    if record.value_relation == "range":
        return f"{value} 至 {record.upper_decimal}"
    if value is None:
        return f"无数值（{record.value_relation}）"
    if record.value_relation == "unresolved":
        return f"{value}（关系 unresolved）"
    return {"eq": "", "approx": "约 ", "gt": "> ", "gte": "≥ "}.get(record.value_relation, "") + value


def render_package(package: dict) -> str:
    """Validate first; render only supplied artifacts and declared metadata."""
    bundle = EvidencePackage.model_validate(package)
    counts = Counter(artifact.kind for artifact in bundle.artifacts)
    lines = ["# Data Agent 证据包检查报告", "",
        f"证据包：{_cell(bundle.bundle_id)}；协议：{_cell(bundle.schema_version)}。", "",
        f"快照：{_cell(bundle.scope.snapshot_id)}；知识截止：{bundle.scope.knowledge_cutoff}；"
        f"候选数据访问：{'已允许（不代表研究采纳）' if bundle.scope.include_candidates else '未允许'}。", "",
        "**语义完整性：未评估。** 本报告区分原文、提取、归一化和计算；不会把工具返回成功解释成全文已读或分析已完成。", "",
        "## 产物一览", "",
        _table(("类型", "数量", "来源", "页码"), [
            (f"{label} · {kind}", counts[kind],
             _joined(sid for item in bundle.artifacts if item.kind == kind for sid in item.source_snapshot_ids),
             _pages([loc for item in bundle.artifacts if item.kind == kind for loc in item.locators]))
            for kind, label in KIND_LABELS.items()]), "",
        "## 来源范围", "",
        _table(("来源版本", "公司", "披露可用日期", "来源哈希", "原始链接"), [
            (sid, bundle.source_companies[sid],
             _joined(loc.available_at for item in bundle.artifacts for loc in item.locators if loc.source_snapshot_id == sid),
             _joined(loc.source_sha256 for item in bundle.artifacts for loc in item.locators if loc.source_snapshot_id == sid),
             _joined(loc.source_url for item in bundle.artifacts for loc in item.locators if loc.source_snapshot_id == sid))
            for sid in bundle.scope.source_snapshot_ids]), "",
        "未记录的页码、日期或坐标保持未知；报告不会根据文件名、材料顺序或其它来源补全。", "",
        "## 阅读覆盖如何理解", "",
        _table(("覆盖类型", "含义"), [(f"{label} · {mode}", description)
               for mode, (label, description) in COVERAGE_LABELS.items()]), "",
    ]
    if bundle.coverage:
        lines += [_table(("来源", "节点", "覆盖类型", "块 ID"), [
            (entry.source_snapshot_id, entry.node_id, COVERAGE_LABELS[entry.mode][0], _joined(entry.block_ids))
            for entry in bundle.coverage]), ""]
    else:
        lines += ["包内未提供阅读覆盖条目。", ""]

    records = [item for item in bundle.artifacts if item.kind == "normalized_record"]
    lines += ["## 归一化记录", "", "下表的摘要是归一化记录字段，**不是原文引语**；数值、区间和单位按输入包原样显示。", ""]
    if records:
        lines += [_table(("产物 / 记录", "实体 / 指标", "期间", "值 / 单位", "value_relation", "性质 / 口径", "分母 / 模态", "处理来源", "摘要（非原文引语）", "父产物"), [
            (f"{item.artifact_id} / {item.payload.record.record_id}",
             f"{item.payload.record.entity_id} / {item.payload.record.metric_id}", _period(item.payload.record),
             f"{_value(item.payload.record)} / {item.payload.record.unit or '未提供单位'}",
             item.payload.record.value_relation,
             f"{item.payload.record.value_kind} / {item.payload.record.accounting_basis}",
             f"{item.payload.record.denominator or '未声明'} / {item.payload.record.modality or '未声明'}",
             item.payload.origin_kind, item.payload.record.summary, _joined(item.derived_from)) for item in records]), ""]
    else:
        lines += ["本包没有归一化记录。", ""]

    computed = [item for item in bundle.artifacts if item.kind == "computed_scalar"]
    lines += ["## 确定性计算", "", "以下值来自包内已记录的计算结果；本报告不重算或推导新数值。", ""]
    if computed:
        lines += [_table(("产物", "公式", "计算值 / 展示值", "单位", "父记录 ID", "父产物 ID"), [
            (item.artifact_id, item.payload.fact.get("formula_id"),
             f"{item.payload.fact['value_decimal']} / {item.payload.fact['display_decimal']}",
             item.payload.fact.get("unit"), _joined(item.payload.fact["operand_record_ids"]), _joined(item.derived_from))
            for item in computed]), ""]
    else:
        lines += ["本包没有计算结果。", ""]

    models = [item for item in bundle.artifacts if item.kind in ("model_extract", "model_summary")]
    lines += ["## 模型原输出与归一化分开查看", "", "这里展示包内保留的模型提取或摘要；它们与上方归一化记录、来源原文是不同产物。", ""]
    if models:
        for item in models:
            provenance = item.provenance
            lines += [f"### {_cell(item.artifact_id)} · {KIND_LABELS[item.kind]}", "",
                _table(("字段", "记录值"), [("Provider", provenance.provider), ("模型", provenance.model),
                    ("Prompt 哈希", provenance.prompt_sha256), ("处理方法", provenance.method_id),
                    ("验证状态", provenance.verification), ("父产物", _joined(item.derived_from))]), ""]
            if item.kind == "model_extract":
                lines += [_table(("模型输出字段", "模型原输出值"), list(_fields(item.payload.extraction))), ""]
            else:
                lines += ["模型摘要原输出（不是来源原话）：", "", _quote(item.payload.text), ""]
    else:
        lines += ["本包没有独立模型产物；不能从记录摘要推断存在模型调用。", ""]

    images = [item for item in bundle.artifacts if item.kind == "image_reference"]
    lines += ["## 图片与多模态状态", ""]
    if images:
        lines += [_table(("产物 / 图片 ID", "原始替代文字", "字节状态 / SHA-256", "OCR", "视觉理解", "页码"), [
            (f"{item.artifact_id} / {item.payload.image_asset_id or '未知'}", item.payload.alt_text,
             f"{item.payload.bytes_status} / {item.payload.bytes_sha256 or '未校验字节'}",
             item.payload.ocr_status, item.payload.vision_status, _pages(item.locators)) for item in images]), "",
            "metadata_only / unresolved 不能证明已取得图片字节；verified_local 也不代表已经识别图片内容。", ""]
    else:
        lines += ["本包没有图片引用。", ""]

    quotes = [item for item in bundle.artifacts if item.kind == "source_quote"]
    lines += ["## 来源引语", ""]
    if quotes:
        lines += [_table(("产物", "完整引语", "来源 / 页码", "验证状态", "来源父产物"), [
            (item.artifact_id, item.payload.text, f"{_joined(item.source_snapshot_ids)} / {_pages(item.locators)}",
             item.provenance.verification, _joined(item.derived_from, "无；仅保留快照引语，参见缺口")) for item in quotes]), ""]
    else:
        lines += ["本包没有单独引语产物。", ""]

    texts = [item for item in bundle.artifacts if item.kind == "source_text"]
    paragraphs = [item for item in texts if item.payload.block.get("type") == "paragraph"]
    examples = (paragraphs or texts)[:2]
    lines += ["## 完整原文示例", "",
        "按证据包顺序展示最多两段完整原文（优先段落）；未展示的正文、表格单元格和完整元数据仍保留在输入证据包中。"
        "这里的选段不替代原包，也不表示其它块已被阅读。", ""]
    if examples:
        for item in examples:
            lines += [f"### {_cell(item.artifact_id)}", "",
                f"来源：{_cell(_joined(item.source_snapshot_ids))}；{_cell(_pages(item.locators))}；"
                f"块：{_cell(_joined(loc.block_id for loc in item.locators))}。", "", _quote(item.payload.text), ""]
    else:
        lines += ["本包没有可展示的完整原文块。", ""]

    lines += ["## 缺口与未完成项", ""]
    if bundle.gaps:
        lines += [_table(("缺口 ID", "原因", "关联来源", "关联产物", "说明"), [
            (gap.gap_id, gap.reason, _joined(gap.source_snapshot_ids), _joined(gap.artifact_ids), gap.detail)
            for gap in bundle.gaps]), ""]
    else:
        lines += ["包内未记录 gap；这不等于全文覆盖或语义完整性已通过验证。", ""]
    lines += ["## 原执行 ID 到证据产物", ""]
    if bundle.bindings:
        lines += [_table(("原执行 ID", "证据产物 ID"), [(key, _joined(value)) for key, value in bundle.bindings.items()]), ""]
    else:
        lines += ["本包未提供原执行 ID 映射。", ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, dest="package_path")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.suffix.lower() != ".md":
        parser.error("--output must name a new .md report")
    report = render_package(json.loads(args.package_path.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
