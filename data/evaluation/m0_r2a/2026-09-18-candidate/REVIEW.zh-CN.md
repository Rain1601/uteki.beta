# M0 G0 人工试标包

状态：待人工审阅；这是新候选，不是 Gold 或已采纳研究。

固定来源：[sec-0001652044-26-000018](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm)

新来源快照：`sec-0001652044-26-000018-candidate-a24107da17e93e3e`

## 来源核查

完整来源的全部段落参与校验；以下计数仅表示来源一致性，不表示主张语义正确。

- 旧证据定位：22/22。
- 旧精确英文引文：65/65。
- 旧摘录逐段一致：20/21。

旧文件均未覆盖。差异、前后文本、输入指纹见 `legacy_audit.json`；新的 `review_excerpt.json` 直接来自已校验完整来源。

完整来源及附件保存在 `source_snapshot/`，原候选输入按原字节保存在 `legacy_inputs/`。本包可复制到其他目录独立校验，无须原工作区资料。

## 小节试标：Google Services 的非广告收入

### 第 88 段

In addition, Google Services generates revenues from products and services beyond advertising, including:

文本指纹：`b1521a490872d564cbed15ae19081309d0df87b94f8a93d66b3c6b61cddadbe9`

### 第 89 段

• consumer subscriptions, which primarily include revenues from YouTube services, such as YouTube TV, YouTube Music and Premium, and NFL Sunday Ticket, as well as Google One, which offers access to our most capable Gemini models;

文本指纹：`45e9babba13e2f041ac8642c159891c0e58098c5c4daf356108d531737c65699`

### 第 90 段

• platforms , which primarily include revenues from Google Play sales of apps and in-app purchases; and

文本指纹：`2e86b1ceb5f574619bc1b27515bb8ac52df965b71257bae7dd0834bdf5ce9cc4`

### 第 91 段

• devices, which primarily include sales of the Pixel family of devices.

文本指纹：`1e6fa25f5550ffd1954f20c62be388edaca2df8f2eb8711f1071c4a98dbfd976`

## 请记录研究判断

以下是待裁决的问题，不是已批准的标注规则。可直接在讨论中回答，由执行者据实记录为新的审核版本；本准备包保持不可变。

- **G0-P1**：Google Services 下的订阅、平台、设备，应如何表达为业务节点与收入类别，才能有用且不重复？
- **G0-P2**：Google Play、Google One、YouTube 与 Pixel 在本段应作为产品/服务，哪些有足够依据提升为独立业务节点？
- **G0-P3**：本段仅披露收入来源，是否同意把各类收入占比、利润率和独立性保留为未知，并要求每项推导写明规则？
- **G0-P4**：是否确认采用新来源快照及第 90 段原文，旧摘录和旧审核身份继续保留？

完整候选也已附在本目录。一次小节试标不替代完整 Gold 的逐项审核与独立遗漏搜索。

## 下一步

人工试用规则后更新 G0；再冻结来源/运行契约与 baseline 设计，进入完整 Gold。付费 baseline 的模型及预算尚未确定。
