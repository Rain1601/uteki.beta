# Data Agent 证据包检查报告

证据包：bundle-6769e9b1e1f7a18acfa6ab33；协议：retrieval-evidence-v1。

快照：query-c9e2d02426106321794973a3；知识截止：2026-09-22；候选数据访问：已允许（不代表研究采纳）。

**语义完整性：未评估。** 本报告区分原文、提取、归一化和计算；不会把工具返回成功解释成全文已读或分析已完成。

## 产物一览

| 类型 | 数量 | 来源 | 页码 |
| --- | --- | --- | --- |
| 原始文本 · source\_text | 9 | alphabet-2025-10k-c2f63010、alphabet-2025q4-call-8e3678d5138e | 原刊页：3、86、60；PDF 页：2、13 |
| 原始表格 · source\_table | 3 | alphabet-2025-10k-c2f63010 | 原刊页：87、60；PDF 页：未记录 |
| 来源引语 · source\_quote | 7 | alphabet-2025-10k-c2f63010、alphabet-2025q4-call-8e3678d5138e | 原刊页：87、60；PDF 页：2、13 |
| 图片引用 · image\_reference | 1 | alphabet-2025-10k-c2f63010 | 原刊页：26；PDF 页：未记录 |
| 归一化记录 · normalized\_record | 4 | alphabet-2025q4-call-8e3678d5138e、alphabet-2025-10k-c2f63010 | 原刊页：87、60；PDF 页：2、13 |
| 确定性计算 · computed\_scalar | 1 | alphabet-2025-10k-c2f63010 | 原刊页：未记录；PDF 页：未记录 |
| 模型原始提取输出 · model\_extract | 2 | alphabet-2025q4-call-8e3678d5138e | 原刊页：未记录；PDF 页：2、13 |
| 模型摘要 · model\_summary | 0 | 未记录 | 原刊页：未记录；PDF 页：未记录 |

## 来源范围

| 来源版本 | 公司 | 披露可用日期 | 来源哈希 | 原始链接 |
| --- | --- | --- | --- | --- |
| alphabet-2025-10k-c2f63010 | alphabet | 2026-02-05 | c2f6301004f35411a20611c14ff01d80a85c0bcbab6053c80d8cc7f6fc747161 | https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm |
| alphabet-2025q4-call-8e3678d5138e | alphabet | 2026-02-04 | 8e3678d5138e30a0ee9065cdf54ae790937b9e27194ffae223a0c438c4928cd5 | https://s206.q4cdn.com/479360582/files/doc\_events/2026/Feb/04/2025\_Q4\_Earnings\_Transcript.pdf |

未记录的页码、日期或坐标保持未知；报告不会根据文件名、材料顺序或其它来源补全。

## 阅读覆盖如何理解

| 覆盖类型 | 含义 |
| --- | --- |
| 正文已返回 · body\_returned | 仅列出的完整文本/表格块已经返回；不能据此推断全文或语义完整。 |
| 仅来源追溯 · provenance\_only | 保留出处或引语；不能据此声称周边正文已读。 |
| 仅导航 · navigation\_only | 目录或搜索定位信息；不计入正文阅读。 |
| 仅图片引用 · image\_reference\_only | 只有图片引用或字节校验信息；不代表已执行 OCR 或视觉理解。 |

| 来源 | 节点 | 覆盖类型 | 块 ID |
| --- | --- | --- | --- |
| alphabet-2025-10k-c2f63010 | didx-028173790917c679-part-i-item-1 | 正文已返回 | block-000056-5c0c0c66、block-000057-d4b1ea57、block-000058-0c6683ca、block-000059-ab2556c8 |
| alphabet-2025-10k-c2f63010 | didx-028173790917c679-document | 仅图片引用 | block-000371-f7cf83f3 |
| alphabet-2025q4-call-8e3678d5138e | document | 正文已返回 | block-000019-229fa8b5 |
| alphabet-2025-10k-c2f63010 | 未知 | 仅来源追溯 | block-000914-d9c3ca1b、block-000912-68dbd7dd、block-000913-2f8c99ac |
| alphabet-2025-10k-c2f63010 | 未知 | 仅来源追溯 | block-000790-942753de、block-000789-3cd01564 |
| alphabet-2025q4-call-8e3678d5138e | 未知 | 仅来源追溯 | block-000019-229fa8b5 |
| alphabet-2025q4-call-8e3678d5138e | 未知 | 仅来源追溯 | block-000153-938fcda2 |
| alphabet-2025q4-call-8e3678d5138e | 未知 | 仅来源追溯 | block-000151-be80bd28 |
| alphabet-2025-10k-c2f63010 | 未知 | 仅导航 | 未记录 |

## 归一化记录

下表的摘要是归一化记录字段，**不是原文引语**；数值、区间和单位按输入包原样显示。

| 产物 / 记录 | 实体 / 指标 | 期间 | 值 / 单位 | value_relation | 性质 / 口径 | 分母 / 模态 | 处理来源 | 摘要（非原文引语） | 父产物 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| art-3a5e0f238149d7af0ac5f78d / qr-5c90abeef861a377e479ea26 | alphabet / capex\_guidance | year · 2026-01-01 → 2026-12-31 | 175000000000 至 185000000000 / USD | range | management\_guidance / management\_disclosure | 未声明 / 未声明 | model\_assisted | Alphabet expects 2026 CapEx of $175-185 billion to meet customer demand and capitalize on AI opportunities. | art-dc3a0eda1ba17797d403c872、art-df6a78c78a632091882b6d40、art-efef6649cdb6f19349a75e97 |
| art-a9920a3498aebe32215743c9 / qr-79a8181cb9085d4723695e7e | alphabet / capex\_guidance | year · 2026-01-01 → 2026-12-31 | 175000000000 至 185000000000 / USD | range | management\_guidance / management\_disclosure | 未声明 / 未声明 | model\_assisted | CFO reiterates full-year 2026 CapEx guidance of $175-185 billion, with investments ramping through the year. | art-082a6dea85361e1d90ec014b、art-60c628743fc963a0674e6340、art-f46d688456edff5d605c0300 |
| art-dc3e7bca87aa1eb675ce4d0c / obs-f51dd84adc17ae267734 | google-cloud / revenue | year · 2025-01-01 → 2025-12-31 | 58705000000 / USD | eq | actual / reported\_segment | 未声明 / 未声明 | deterministic | google-cloud revenue | art-09fc27e45eaacb0e5d8aad01、art-d334e660c5d77b48b6a52f9c |
| art-4c2f8133cc7bd217e1d0805e / obs-fcb8161acafe09b0a0ce | google-cloud / operating\_income | year · 2025-01-01 → 2025-12-31 | 13910000000 / USD | eq | actual / reported\_segment | 未声明 / 未声明 | deterministic | google-cloud operating\_income | art-9a0cd0d5d2cf19e0f3d4c0d6 |

## 确定性计算

以下值来自包内已记录的计算结果；本报告不重算或推导新数值。

| 产物 | 公式 | 计算值 / 展示值 | 单位 | 父记录 ID | 父产物 ID |
| --- | --- | --- | --- | --- | --- |
| art-35bc2558bec4cd5d7970fe65 | operating\_margin-v1 | 23.694745 / 23.69 | percent | obs-f51dd84adc17ae267734、obs-fcb8161acafe09b0a0ce | art-4c2f8133cc7bd217e1d0805e、art-dc3e7bca87aa1eb675ce4d0c |

## 模型原输出与归一化分开查看

这里展示包内保留的模型提取或摘要；它们与上方归一化记录、来源原文是不同产物。

### art-df6a78c78a632091882b6d40 · 模型原始提取输出

| 字段 | 记录值 |
| --- | --- |
| Provider | 未知 |
| 模型 | 未知 |
| Prompt 哈希 | 未知 |
| 处理方法 | alphabet-call-reviewed-v1 |
| 验证状态 | snapshot\_verified |
| 父产物 | art-dc3a0eda1ba17797d403c872、art-efef6649cdb6f19349a75e97 |

| 模型输出字段 | 模型原输出值 |
| --- | --- |
| kind | guidance |
| entity | alphabet |
| metric | capex\_guidance |
| period | FY2026 |
| value | 175 |
| upper | 185 |
| unit | USD\_billions |
| summary | Alphabet expects 2026 CapEx of $175-185 billion to meet customer demand and capitalize on AI opportunities. |
| speaker | Sundar Pichai, CEO, Alphabet and Google |
| evidence\[0\].block\_id | block-000019-229fa8b5 |
| evidence\[0\].quote | our 2026 CapEx investments are anticipated to be in the range of $175 billion to $185 billion |
| qualifiers\[0\].block\_id | block-000019-229fa8b5 |
| qualifiers\[0\].quote | To meet customer demand and capitalize on the growing opportunities ahead of us |
| question\_refs | 空列表 |

### art-082a6dea85361e1d90ec014b · 模型原始提取输出

| 字段 | 记录值 |
| --- | --- |
| Provider | 未知 |
| 模型 | 未知 |
| Prompt 哈希 | 未知 |
| 处理方法 | alphabet-call-reviewed-v1 |
| 验证状态 | snapshot\_verified |
| 父产物 | art-60c628743fc963a0674e6340、art-f46d688456edff5d605c0300 |

| 模型输出字段 | 模型原输出值 |
| --- | --- |
| kind | guidance |
| entity | alphabet |
| metric | capex\_guidance |
| period | FY2026 |
| value | 175 |
| upper | 185 |
| unit | USD\_billions |
| summary | CFO reiterates full-year 2026 CapEx guidance of $175-185 billion, with investments ramping through the year. |
| speaker | Anat Ashkenazi, SVP and CFO, Alphabet and Google |
| evidence\[0\].block\_id | block-000151-be80bd28 |
| evidence\[0\].quote | For the full year 2026, we expect CapEx to be in the range of $175 billion to $185 billion, with investments ramping over the course of the year. |
| qualifiers\[0\].block\_id | block-000153-938fcda2 |
| qualifiers\[0\].quote | Keep in mind that the availability of supply, pricing of components, and timing of cash payments can cause some variability in the reported CapEx number. |
| question\_refs | 空列表 |

## 图片与多模态状态

| 产物 / 图片 ID | 原始替代文字 | 字节状态 / SHA-256 | OCR | 视觉理解 | 页码 |
| --- | --- | --- | --- | --- | --- |
| art-8a35e15f75a336d08db1a525 / asset-1abac7a8524c | 2949 | metadata\_only / 未校验字节 | not\_run | not\_run | 原刊页：26；PDF 页：未记录 |

metadata_only / unresolved 不能证明已取得图片字节；verified_local 也不代表已经识别图片内容。

## 来源引语

| 产物 | 完整引语 | 来源 / 页码 | 验证状态 | 来源父产物 |
| --- | --- | --- | --- | --- |
| art-d334e660c5d77b48b6a52f9c | 58,705 | alphabet-2025-10k-c2f63010 / 原刊页：87；PDF 页：未记录 | source\_verified | art-3e536eeb63ddfb740d245073、art-8644e58b693974e2b3264869、art-fd2a1c902c19f413846a4cc0 |
| art-09fc27e45eaacb0e5d8aad01 | 58,705 | alphabet-2025-10k-c2f63010 / 原刊页：60；PDF 页：未记录 | source\_verified | art-0bb900e5bf5f3da963d1a557、art-2aa1a9c72477009490d95d08 |
| art-9a0cd0d5d2cf19e0f3d4c0d6 | 13,910 | alphabet-2025-10k-c2f63010 / 原刊页：87；PDF 页：未记录 | source\_verified | art-3e536eeb63ddfb740d245073、art-8644e58b693974e2b3264869、art-fd2a1c902c19f413846a4cc0 |
| art-efef6649cdb6f19349a75e97 | To meet customer demand and capitalize on the growing opportunities ahead of us | alphabet-2025q4-call-8e3678d5138e / 原刊页：未记录；PDF 页：2 | source\_verified | art-c3bec937ad16d4c4614dfdb5 |
| art-60c628743fc963a0674e6340 | Keep in mind that the availability of supply, pricing of components, and timing of cash payments can cause some variability in the reported CapEx number. | alphabet-2025q4-call-8e3678d5138e / 原刊页：未记录；PDF 页：13 | source\_verified | art-608427b29e42bb91810ac998 |
| art-f46d688456edff5d605c0300 | For the full year 2026, we expect CapEx to be in the range of $175 billion to $185 billion, with investments ramping over the course of the year. | alphabet-2025q4-call-8e3678d5138e / 原刊页：未记录；PDF 页：13 | source\_verified | art-ce3c993378383a4e37792c9e |
| art-dc3a0eda1ba17797d403c872 | our 2026 CapEx investments are anticipated to be in the range of $175 billion to $185 billion | alphabet-2025q4-call-8e3678d5138e / 原刊页：未记录；PDF 页：2 | source\_verified | art-c3bec937ad16d4c4614dfdb5 |

## 完整原文示例

按证据包顺序展示最多两段完整原文（优先段落）；未展示的正文、表格单元格和完整元数据仍保留在输入证据包中。这里的选段不替代原包，也不表示其它块已被阅读。

### art-ff9031f68bf09749158a5ce3

来源：alphabet-2025-10k-c2f63010；原刊页：3；PDF 页：未记录；块：block-000058-0c6683ca。

> As our founders Larry and Sergey wrote in the original founders' letter, "Google is not a conventional company. We do not intend to become one." That unconventional spirit has been a driving force throughout our history, inspiring us to tackle big problems and invest in moonshots. It led us to be a pioneer in the development of artificial intelligence (AI) and, since 2016, be an AI-first company. We continue this work under the leadership of Alphabet and Google CEO, Sundar Pichai.

### art-699a9b97153f5c6a59d9f845

来源：alphabet-2025-10k-c2f63010；原刊页：3；PDF 页：未记录；块：block-000059-ab2556c8。

> Alphabet is a collection of businesses — the largest of which is Google. We report Google in two segments, Google Services and Google Cloud, and all non-Google businesses collectively as Other Bets. Supporting these businesses, we have centralized certain AI-related research and development focused on advanced research in AI and developing the frontier models that serve our businesses, which is reported in Alphabet-level activities. Alphabet's structure is about helping each of our businesses prosper through strong leaders and independence.

## 缺口与未完成项

| 缺口 ID | 原因 | 关联来源 | 关联产物 | 说明 |
| --- | --- | --- | --- | --- |
| egap-ea528993c5be70f58709375b | image\_bytes\_unavailable | alphabet-2025-10k-c2f63010 | art-8a35e15f75a336d08db1a525 | Only the indexed image reference is packaged. Alt text is not OCR; no image understanding ran. |
| egap-5a180a0d06c1f9d94a7ddf96 | region\_units\_unverified | alphabet-2025q4-call-8e3678d5138e | 未记录 | Indexed block bounding box is retained; units are not independently declared here and the box is not quote-tight. |
| egap-e9076ff4b71b4d19ce46283f | model\_metadata\_unavailable | alphabet-2025q4-call-8e3678d5138e | art-df6a78c78a632091882b6d40 | The frozen extraction lacks provider/model/prompt hashes. No new model ran and these fields are not guessed. |
| egap-f44a81ca76f1054688749008 | model\_metadata\_unavailable | alphabet-2025q4-call-8e3678d5138e | art-082a6dea85361e1d90ec014b | The frozen extraction lacks provider/model/prompt hashes. No new model ran and these fields are not guessed. |

## 原执行 ID 到证据产物

| 原执行 ID | 证据产物 ID |
| --- | --- |
| context:ctx-add317dd247d02a370c53de4 | art-5fcb1683a814e5802064d77a、art-246a4d82bb215f06b8d0ab8f、art-ff9031f68bf09749158a5ce3、art-699a9b97153f5c6a59d9f845 |
| context:ctx-c2c22edc9756b413084df3f6 | art-8a35e15f75a336d08db1a525 |
| context:ctx-72ea42029cb3eff0296a2e29 | art-c3bec937ad16d4c4614dfdb5 |
| evidence:ev-1e58da8fe124ac7d814a | art-d334e660c5d77b48b6a52f9c |
| evidence:ev-32c07a89c883c178198c | art-09fc27e45eaacb0e5d8aad01 |
| evidence:ev-6c2ea74e3c9b4ab8853e | art-9a0cd0d5d2cf19e0f3d4c0d6 |
| evidence:qev-21c0cde823765aa8b1fa4dfe | art-efef6649cdb6f19349a75e97 |
| evidence:qev-5edd372d7c8307c3aa7c0f8d | art-60c628743fc963a0674e6340 |
| evidence:qev-a899d943511fa9b30740a435 | art-f46d688456edff5d605c0300 |
| evidence:qev-f139b8e08893143bb295bab8 | art-dc3a0eda1ba17797d403c872 |
| record:qr-5c90abeef861a377e479ea26 | art-3a5e0f238149d7af0ac5f78d |
| record:qr-79a8181cb9085d4723695e7e | art-a9920a3498aebe32215743c9 |
| record:obs-f51dd84adc17ae267734 | art-dc3e7bca87aa1eb675ce4d0c |
| record:obs-fcb8161acafe09b0a0ce | art-4c2f8133cc7bd217e1d0805e |
| computed:calc-a85c2f7b0a473b72aef2267a | art-35bc2558bec4cd5d7970fe65 |
