# v0.3 Candidate / 候选索引

Verify title and page link roles: matching Item title, enclosing Part, same reported page and source order. Only verified equivalent targets are accepted; real conflicts remain.

核验标题、所属 Part、页码与正文顺序后接受同页链接差异；保留真实冲突，不覆盖旧版本。

```json
{
  "previous_index_folder": "data/document_library/alphabet/sources/alphabet-000165204423000045/indexes/v0.2-candidate",
  "index_id": "didx-662a18e0b7d9c09b",
  "counts": {
    "blocks": 499,
    "tables": 114,
    "images": 0,
    "parts": 2,
    "items": 8,
    "diagnostics": 1
  },
  "diagnostics": [
    {
      "code": "item_unresolved",
      "message": "Item 5 could not be mapped to a source block.",
      "node_id": null,
      "severity": "error"
    }
  ]
}
```
