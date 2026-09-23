"""Replay an explicitly scripted retrieval example offline; never call a model."""
import argparse
import asyncio
import json
from pathlib import Path

from uteki.agents.data_query.agent import DataQueryAgent
from uteki.agents.data_query.artifacts import write_new
from uteki.domain.research_data.scoped_agent_query import ScopedAgentQuery
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort

ROOT = Path(__file__).resolve().parents[1]


class ReplayPlanner:
    """Test orchestration only. These steps never enter a production model prompt."""

    def __init__(self, steps):
        self.steps = iter(steps)

    async def decide(self, packet):
        step = next(self.steps)
        if len(step) != 1:
            raise ValueError("each replay step requires exactly one operation")
        if "decision" in step:
            return step["decision"]
        previous = packet["history"][-1]["result"]
        if "continue_read" in step:
            if not previous.get("next_cursor") or previous["next_cursor"]["kind"] != "read":
                raise ValueError("previous result has no read continuation")
            return {"action": "read_source", "read": {
                "source_snapshot_id": previous["source_snapshot_id"], "node_id": previous["node_id"],
                "cursor": previous["next_cursor"], "count": step["continue_read"]["count"]}}
        if "read_search_hit" in step:
            item = step["read_search_hit"]
            hit = previous["hits"][item["hit_index"]]
            return {"action": "read_source", "read": {
                "source_snapshot_id": previous["source_snapshot_id"], "node_id": previous["node_id"],
                "start_block_id": hit["block_id"], "count": item["count"]}}
        if "finish_references" not in step:
            raise ValueError("unknown replay operation")
        refs = {key: [] for key in ("record_ids", "computed_ids", "context_ids", "gap_ids")}
        for turn in packet["history"]:
            value = turn["result"]
            for target, collection, key in (("record_ids", "records", "record_id"),
                    ("computed_ids", "computed_facts", "computed_id"),
                    ("context_ids", "contexts", "context_id"), ("gap_ids", "gaps", "gap_id")):
                refs[target].extend(row[key] for row in value.get(collection, []) if key in row)
            if value.get("context_id"):
                refs["context_ids"].append(value["context_id"])
        return {"action": "finish", "answer_parts": [{
            "requested_information": step["finish_references"],
            **{key: list(dict.fromkeys(ids)) for key, ids in refs.items()}}]}


def markdown_report(result):
    lines = ["# 来源范围与章节阅读：离线回放", "",
        "这是预设步骤的工具验证，没有模型调用，也不是完整业务/风险分析验收。", "",
        f"- 问题：{result['request']['question']}",
        f"- 来源：`{'`, `'.join(result['request']['scope']['source_snapshot_ids'])}`",
        f"- 结果状态：`{result['status']}`；仅表示引用型工具回路的状态。",
        "- 候选数据没有被采纳；原始快照未改写。", "",
        "| Step | 工具 | 实际结果 |", "| --- | --- | --- |"]
    for turn in result["trace"]:
        detail = turn.get("status", "完成")
        if turn.get("result_file"):
            value = turn["value"]
            if turn["tool"] == "outline_source":
                detail = f"{len(value.get('nodes', []))} 个目录节点；未读正文"
            elif turn["tool"] == "read_source":
                detail = f"{len(value.get('blocks', []))} 个完整块；仍有续读：{'是' if value.get('next_cursor') else '否'}"
            elif turn["tool"] == "search_source":
                detail = f"{value.get('total', 0)} 个字面命中；摘要仅用于定位"
            elif turn["tool"] == "query":
                detail = f"{len(value['records'])} 条原记录；{len(value['computed_facts'])} 个确定性计算；{len(value['gaps'])} 个缺口"
        lines.append(f"| {turn['step']} | `{turn['tool']}` | {detail} |")
    lines += ["", "## 返回的原文", "", "以下摘录来自实际读取的完整块；每一步的完整输出见 session/turn-*/tool-result.json。", ""]
    for ctx in result["contexts"]:
        lines += [f"- 来源 `{ctx['source_snapshot_id']}`，节点 `{ctx.get('node_id', '')}`；{len(ctx['blocks'])} 个块。"]
        block = next((b for b in ctx["blocks"] if b["type"] == "paragraph"), ctx["blocks"][0])
        lines += [f"  - `{block['block_id']}`，原文页码 {block.get('reported_page')}：{block['text']}"]
    lines += ["", "## 返回的计算", ""]
    for fact in result["computed_facts"]:
        lines += [f"- `{fact['entity_id']}` / `{fact['formula_id']}`：{fact['display_decimal']} {fact['unit']}。",
                  f"  - 依赖记录：{', '.join('`' + rid + '`' for rid in fact['operand_record_ids'])}。"]
    lines += ["", "## 范围与未完成项", "",
        "只读取了上述正文批次，搜索命中与目录节点不计入已读正文。未声称读完选定章节，未检查全部相关章节与附注，也未输出研究结论。",
        "统一证据包、任务覆盖台账和真实模型分析验收属于后续步骤。", "",
        "`verification.json` 记录只读快照校验和产物哈希；`session/` 保存输入、决策、SQL、正文、游标与引用结果。", ""]
    return "\n".join(lines)


async def replay(spec_path, output):
    spec = json.loads(spec_path.read_text())
    if spec["schema_version"] != "scoped-retrieval-replay-v1":
        raise ValueError("unknown offline replay spec version")
    request = ScopedAgentQuery.model_validate(spec["request"])
    dataset = ROOT / spec["dataset"]
    if output.resolve().is_relative_to(dataset.resolve()):
        raise ValueError("verification output must not be inside the immutable dataset")
    before = {str(p.relative_to(dataset)): digest(p.read_bytes()) for p in dataset.rglob("*") if p.is_file()}
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "spec.json", spec)
    with QueryDataPort(dataset) as port:
        result = await DataQueryAgent(port, ReplayPlanner(spec["steps"]), max_steps=len(spec["steps"]),
            max_packet_bytes=400000).run_scoped(request, output=output / "session")
    after = {str(p.relative_to(dataset)): digest(p.read_bytes()) for p in dataset.rglob("*") if p.is_file()}
    if before != after:
        raise RuntimeError("snapshot changed during read-only verification")
    if result["status"] not in ("answered", "partial"):
        raise RuntimeError("offline replay did not reach a reference-based finish")
    for turn in result["trace"]:
        if turn.get("result_file"):
            turn["value"] = json.loads((output / "session" / turn["result_file"]).read_text())
    with (output / "README.md").open("x") as stream:
        stream.write(markdown_report(result))
    write_new(output / "verification.json", {"mode": "scripted_offline_tools", "model_calls": 0,
        "snapshot_unchanged": True, "snapshot_file_hashes": before,
        "files": {str(p.relative_to(output)): digest(p.read_bytes()) for p in output.rglob("*") if p.is_file()}})
    print(json.dumps({"status": result["status"], "model_calls": 0, "snapshot_unchanged": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(replay(args.spec, args.output))
