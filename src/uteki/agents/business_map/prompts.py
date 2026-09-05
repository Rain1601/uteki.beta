SYSTEM_PROMPT_V0_1 = """You create a decision-useful Company Business Map from one fixed 10-K section.

Use only the supplied numbered paragraphs. Identify major businesses, their economics, useful relationships, importance signals, and material unknowns. Do not build an exhaustive product catalog. Do not infer internal organization. Every factual item must cite evidence using the supplied paragraph ordinal and text_hash. Preserve unknowns instead of guessing.

Return one JSON object matching the supplied contract. Do not include prose outside JSON.
"""


def render_user_prompt(document_id: str, source_url: str, paragraphs: tuple) -> str:
    rendered = "\n".join(f"[{p.ordinal}|{p.text_hash}] {p.text}" for p in paragraphs)
    return f"""document_id: {document_id}
source_url: {source_url}

Required top-level fields:
schema_version, company_id, document_id, summary, businesses, relationships, unknowns, evidence

Business kind: company | reportable_segment | business | offering_group
Relationship kind: reported_under | part_of | supports
Review status for all candidates: candidate
Monetization basis: explicit | derived | unknown

SOURCE PARAGRAPHS
{rendered}
"""

