"""A1: model-directed recovery of one controlled missing value."""
import copy

from .cloud_analysis import AnalysisTools, PROMPT
from uteki.infrastructure.research_data.cloud_spike import digest, encoded
from uteki.infrastructure.research_data.cloud_recovery import recover_from_source

VERSION = "cloud-analysis-a1-v0.1"
RECOVERY_PROMPT = PROMPT.replace("no source retrieval exists", "source recovery is available via source_lookup") + """
Additional tool: source_lookup(predicate,period). Only call after facts returns
not_extracted for that exact predicate/period. Data side re-reads the pinned SEC
filing using a narrow deterministic adapter, NOT a general search engine.
It returns recovered_candidate facts with source evidence. These are newly extracted,
not human-approved. Returned facts count as retrieved; next call evidence(fact_id).
They may be used for this experimental answer, explicitly disclosing their pending
review in limitations. No need to retry facts for a recovered record.
If recovery is unsupported/not_found, report blocked or record the gap; never claim
the entire filing contains no answer. Do not invent a fact ID for missing data.
"""


class RecoveryTools(AnalysisTools):
    def __init__(self, snapshot, as_of, source_dir):
        super().__init__(snapshot, as_of)
        self.input = copy.deepcopy(snapshot)
        self.source_dir = source_dir
        self.recovered = {}
        self.recovered_evidence = {}

    def call(self, name, arguments):
        if name not in {"source_lookup", "evidence"} or (name == "evidence" and arguments.get("fact_id") not in self.recovered):
            result = super().call(name, arguments)
            if name == "manifest" and "tools" in result:
                result["tools"].append("source_lookup")
                self.trace[-1]["response"] = copy.deepcopy(result)
            return result
        try:
            if name == "source_lookup":
                predicate, period = arguments["predicate"], arguments["period"]
                if set(arguments) != {"predicate", "period"}:
                    raise ValueError("invalid source_lookup arguments")
                if not any(t["tool"] == "facts" and t["arguments"].get("predicate") == predicate and
                           t["arguments"].get("period") == period and t["response"].get("status") == "not_extracted" for t in self.trace):
                    raise ValueError("read the exact missing field before source recovery")
                result = recover_from_source(self.source_dir, self.input["source_sha256"], predicate, period)
                for f in result["results"]:
                    self.seen[f["fact_id"]] = copy.deepcopy(f)
                    self.recovered[f["fact_id"]] = copy.deepcopy(f)
                self.recovered_evidence.update(copy.deepcopy(result.get("evidence", {})))
            else:
                if set(arguments) != {"fact_id"}:
                    raise ValueError("invalid evidence arguments")
                fid = arguments["fact_id"]
                result = {"results": [self.recovered_evidence[e] for e in self.recovered[fid]["evidence_ids"]],
                          "origin": "source_recovery", "review_status": "pending"}
                self.cited.add(fid)
            result["input_snapshot_id"] = self.input["snapshot_id"]
        except (ValueError, TypeError, KeyError) as exc:
            result = {"status": "tool_error", "error": str(exc)[:180]}
        self.trace.append({"step": len(self.trace) + 1, "tool": name,
                           "arguments": copy.deepcopy(arguments), "response": copy.deepcopy(result)})
        return result

    def resolved_snapshot(self):
        result = copy.deepcopy(self.input)
        result["facts"] += list(self.recovered.values())
        result["evidence"].update(self.recovered_evidence)
        result["coverage"]["status"] = "experimental overlay; recovered data pending human review"
        result["parent_snapshot_id"] = self.input["snapshot_id"]
        result.pop("snapshot_id")
        result["snapshot_id"] = "recovery-" + digest(encoded(result))[:16]
        return result
