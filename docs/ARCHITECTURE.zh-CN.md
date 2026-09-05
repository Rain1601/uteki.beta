# 架构——模块化单体

## 状态

已于 2026-09-06 批准进入实施计划。中文文件为规范性文件，必须与英文配套文件保持语义一致。

## 决策

Uteki Beta 从一个仓库、一个本地可部署应用开始，同时保持严格的模块边界。M0 中 Agent 执行端和评测端在逻辑上分开，但不拆成不同仓库或服务。

评测端可以通过 Agent 的公开接口调用 Agent。Agent 绝不能依赖 Benchmark、Gold Answer、Scorer、Review 或 Experiment。

## 仓库目录

```text
uteki.beta/
├── apps/
│   ├── review_workbench/       # 极简本地人工审核界面
│   └── cli/                    # 本地运行和评测命令
├── src/uteki/
│   ├── domain/                 # 稳定的业务概念和契约
│   │   ├── business_map/
│   │   ├── documents/
│   │   ├── evidence/
│   │   └── runs/
│   ├── agents/                 # Agent 执行平面
│   │   └── business_map/
│   │       ├── contract/
│   │       ├── pipeline/
│   │       ├── prompts/
│   │       └── tools/
│   ├── evaluation/             # 评测与实验平面
│   │   ├── datasets/
│   │   ├── scorers/
│   │   ├── experiments/
│   │   └── error_analysis/
│   └── infrastructure/         # 可替换的外部适配器
│       ├── document_sources/
│       ├── model_providers/
│       └── storage/
├── data/
│   ├── source_documents/       # 原始或规范化的研究资料
│   ├── agent_runs/             # 输入、输出、Trace、成本和延迟
│   └── evaluation/             # Gold、Review、Score 和 Experiment
├── benchmarks/                 # 冻结并纳入版本控制的发布版本
├── experiments/                # 人类可读的实验记录
├── tests/
│   ├── unit/
│   ├── contract/
│   └── integration/
└── docs/
```

只有当第一个真实文件需要某个目录时才创建它。空目录架构脚手架不算进展。

## 模块职责

### Domain

负责定义 Business Map、Business、Relationship、Evidence、Document、Agent Run、Review Decision 及相关标识符的含义。它不依赖模型、数据库、Web、Benchmark 或 Experiment。

### Agent 执行平面

接收有版本的请求与配置，读取允许使用的源材料，生成 Business Map Candidate 和可复现的运行记录。它不知道这次运行属于 Benchmark、Experiment 还是生产任务。

### 评测与实验平面

负责 Dataset、Gold Answer、Scorer、实验对比、错误分类和评测报告。它通过 Agent 公开契约调用 Agent，不进入 Agent 内部实现。

### Review Workbench

属于评测端。它展示原始证据和 Agent Candidate，并记录接受、修改、拒绝、歧义和遗漏补充等决策。它是面向当前工作流的界面，不是通用标注平台。

### Infrastructure

实现可替换的 SEC 文档、模型服务和存储适配器。Provider SDK 对象不能进入 Domain 或 Agent 契约。

## 允许的依赖方向

```text
apps/review_workbench -> evaluation -> agents -> domain
                                \----> domain
apps/cli ------------> evaluation / agents
infrastructure ------> 实现 domain 或调用模块拥有的端口
```

规则：

1. `domain` 不导入任何其他 Uteki 模块。
2. `agents` 可以导入 `domain`，但不能导入 `evaluation` 或 `apps`。
3. `evaluation` 可以导入 Agent 公开契约和 `domain`，但不能导入 Agent Pipeline 内部实现。
4. `apps` 负责组织模块，不包含业务规则或评分规则。
5. `infrastructure` 通过显式 Port 或 Adapter 使用。
6. 只有出现两个真实使用方时才增加共享工具；不建立推测性的 `common` 垃圾场。

## Agent 公开契约

在概念上，M0 只暴露一个操作：

```text
BusinessMapRequest + AgentConfig
                ↓
        BusinessMapAgent.run
                ↓
BusinessMapCandidate + AgentRunRecord
```

Request 标识文档和任务契约。Configuration 记录模型、Prompt 版本、工具和运行参数。Result 包含结构化判断与证据。Run Record 包含可复现信息、Trace、成本、延迟、警告和失败。

Gold Answer 和 Benchmark 身份绝不能出现在 Agent Request 中。

## 数据隔离

M0 可以使用同一种本地存储技术，但数据命名空间保持分离：

- `source_documents`：报告内容和稳定来源定位；
- `agent_runs`：不可变的执行输入、配置、原始输出和 Trace；
- `evaluation`：Candidate 与 Gold 的比较、人工 Review、Score 和 Experiment；
- `benchmarks`：适合通过 Git 审核的冻结发布版本。

Agent 可以读取批准的源文件并写入运行产物。执行期间不能读取 Gold Answer 或 Evaluation Decision。

## 配置与密钥

纳入版本控制的配置只包含 Provider 名称、模型标识、Prompt 版本和非敏感参数。API Key 与凭证在运行时从环境变量或被忽略的本地密钥文件读取。归档仓库中的密钥可以在本地配置时被引用，但绝不能复制到源码、文档、运行产物或 Git 历史中。

## 拆分规则

在真实边界证明需要拆分之前，保持模块化单体。只有多个 Agent Team 共享评测系统、执行需要独立扩缩容、Benchmark 权限需要安全隔离、模块所有权分离，或者发布节奏已经独立时，才考虑拆成不同 Package 或 Service。

