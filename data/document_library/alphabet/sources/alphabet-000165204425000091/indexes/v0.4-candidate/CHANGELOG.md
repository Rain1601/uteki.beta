# v0.4 Candidate / 候选索引

Recursively unwrap layout/XBRL containers into paragraphs, headings and list items. Tables remain atomic. Mixed direct-text containers are conservatively retained; no semantic hierarchy or cross-page joining.

递归展开布局及 XBRL 容器，保留段落、标题、列表和表格。混合直接文本的容器暂保守保留；不推断语义层级，不合并跨页段落。Block IDs change; old evidence remains on old indexes.

```json
{
  "previous_index_folder": "data/document_library/alphabet/sources/alphabet-000165204425000091/indexes/v0.3-candidate",
  "index_id": "didx-67c30ac139edb2cb",
  "counts": {
    "blocks": 727,
    "tables": 90,
    "images": 0,
    "parts": 2,
    "items": 9,
    "diagnostics": 0
  },
  "diagnostics": []
}
```
