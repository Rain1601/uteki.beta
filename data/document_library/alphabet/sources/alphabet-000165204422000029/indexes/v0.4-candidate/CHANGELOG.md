# v0.4 Candidate / 候选索引

Recursively unwrap layout/XBRL containers into paragraphs, headings and list items. Tables remain atomic. Mixed direct-text containers are conservatively retained; no semantic hierarchy or cross-page joining.

递归展开布局及 XBRL 容器，保留段落、标题、列表和表格。混合直接文本的容器暂保守保留；不推断语义层级，不合并跨页段落。Block IDs change; old evidence remains on old indexes.

```json
{
  "previous_index_folder": "data/document_library/alphabet/sources/alphabet-000165204422000029/indexes/v0.3-candidate",
  "index_id": "didx-5fe880f213dbfe63",
  "counts": {
    "blocks": 655,
    "tables": 114,
    "images": 0,
    "parts": 2,
    "items": 8,
    "diagnostics": 0
  },
  "diagnostics": []
}
```
