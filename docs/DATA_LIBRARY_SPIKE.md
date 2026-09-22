# Data Library spike — 2026-09-13

## Update: acquisition resolved / 更新：下载问题已解决

With the user-authorized contact identity supplied via SEC_USER_AGENT, the single-file request succeeded with HTTP 200. All 17 new originals and their images were then acquired sequentially, with at least 0.6 seconds between requests. Together with the existing FY2025 snapshot, 18 filings are locally available: four 10-Ks (FY2022–2025) and fourteen 10-Qs (2022–2025 Q1–Q3; 2026 Q1–Q2). Contact information is not hard-coded into source code.

使用用户授权的联系身份后，单份请求返回 200；随后低频串行获取新增 17 份原文及图片。加上原有 FY2025 共 18 份。以下初始受阻记录保留作历史，不再代表当前获取状态。

- Canonical URL / 独立地址: `/companies/alphabet/documents/{accession}/indexes/{version}`; original HTML and image routes are scoped underneath the same path. Old `/document-index` redirects to the frozen FY2025 version.
- Annual candidates remain `v0.1-candidate`; quarterly candidates are `v0.2-candidate`, parser `sec-source-blocks-v0.1.2-quarterly`, recognizing `PART I. FINANCIAL INFORMATION` and `PART II. OTHER INFORMATION`. Old artifacts are retained.
- 季报新增标题模式识别；不进行语义层级推断、不接入 LLM、不修改已冻结索引。
- All acquired files have SHA checks; table/image counts and emitted node identity, range and anchor checks pass across all 18 documents. Suite: 86 tests passed. Browser verified a Q2 2026 Item 2 click scrolls to and highlights the matching original heading.
- All quarterly sources retain a diagnostic because Item 1 title and page links differ. Q1 2023 additionally has an unresolved Item 5: the TOC target `_208` does not exist in the acquired HTML and the deterministic body-heading fallback did not resolve it. No node was fabricated. These remain candidate indexes requiring review, not fully approved indexes.
- 所有季报保留目录链接冲突诊断；2023 Q1 的 Item 5 目录锚点在原文中不存在、回退未定位，明确保留未解决问题。页面可展开查看诊断，不宣称零错误。
- Supplementary releases, calls and peer reports remain outside this completed filing download step.

## Initial state / 初始状态（历史）

## Delivered / 已完成

- Company list → company detail → filing record; Data page separates raw materials, document structure and business-semantic outputs.
- 公司列表 → 公司详情 → 文档记录；Data 页面区分原始材料、文档结构、业务语义结果。
- SEC submissions metadata identifies 18 Alphabet 10-K/10-Q filings with reporting periods in 2022–2026. Filing date is a separate field.
- 按报告期识别 18 份申报，提交日期独立保存。FY2026 年报尚未发布，不要求第四季度独立 10-Q。
- The existing FY2025 frozen snapshot is reused without changing its index or evidence.
- 复用 FY2025 冻结快照，不修改既有索引、Evidence 或审核结果。

## Blocked / 未完成

- The official IR connection failed. SEC metadata downloads succeeded, but all 17 new original HTML requests returned HTTP 403. They are discovered, not acquired or indexed.
- 官网连接失败；SEC 元数据获取成功，但新增 17 份原文全部返回 HTTP 403，不计作已下载或已索引。
- Earnings releases, transcripts and competitor reports are acquisition targets only, not a completed collection. No claim of complete 2022–2026 supplementary coverage.
- 财报发布稿、电话会逐字稿、竞争对手报告仅列出待采集入口，尚未完成获取。
- Multi-document index viewing beyond the existing FY2025 source remains pending actual source acquisition and parser validation. Do not claim cross-company or 10-Q generalization has passed.
- 多文档索引展示仍待取得来源并验证解析；不能声称 10-Q 或跨公司泛化已验证。

## Next / 下一步

Obtain official original files through an available authorized source or user uploads; preserve source URL, accession, SHA and acquisition time. Validate candidate indexes per document before publishing links. Collect call prepared remarks plus Q&A and distinguish peer evidence from Alphabet disclosures. Keep unavailable periods and sources explicit.

通过可用的官方来源或用户上传取得原文，保存来源、申报号、SHA 与获取时间；逐文档验证候选索引后再开放。补齐电话会发言与 Q&A，竞争对手资料单独归属，持续显示未覆盖的时期和来源。
