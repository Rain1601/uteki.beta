"""Presentation-only, assistant-translated quotes (v1, pending human review).

Exact normalized English matching only: never substitute a whole block's meaning
for a different quote, and never change source citations or validation status.
New unmatched quotes deliberately fall back to English with a missing label.
"""
import re


def normalize_quote(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().strip('“”"')


TRANSLATIONS = {
    'Alphabet is a collection of businesses — the largest of which is Google. We report Google in two segments, Google Services and Google Cloud, and all non-Google businesses collectively as Other Bets. Supporting these businesses, we have centralized certain AI-related research and development focused on advanced research in AI and developing the frontier models that serve our businesses, which is reported in Alphabet-level activities. For further details on our segments, see Part I, Item 1 Business and Note 15 of the Notes to Consolidated Financial Statements included in Item 8 of this Annual Report on Form 10-K.':
    'Alphabet 由一系列业务组成，其中最大的是 Google。我们将 Google 分为 Google Services（谷歌服务）和 Google Cloud（谷歌云）两个分部进行报告，并将所有非 Google 业务统称为 Other Bets（其他业务）。为支持这些业务，我们集中开展部分人工智能相关研发，重点是人工智能前沿研究，以及开发服务于旗下业务的前沿模型；这些活动计入 Alphabet 层面的活动。有关分部的进一步说明，请参阅本年度 10-K 报告第一部分第 1 项“业务”，以及第 8 项所含合并财务报表附注 15。',
    'Increasing Revenues Beyond Advertising: Revenues from cloud, consumer subscriptions, platforms, and devices, which may have differing characteristics than our advertising revenues, have grown over time. Certain of these revenues have been growing at a rate higher than our advertising revenues, becoming a larger percentage of our consolidated revenues, and we expect this trend to continue. The margins on these revenues vary significantly and are generally lower than the margins on our advertising revenues.':
    '广告以外的收入增长：云、消费者订阅、平台和设备收入持续增长，其特征可能不同于广告收入。其中部分收入的增速高于广告收入，占合并收入的比例不断上升，我们预计这一趋势将持续。这些收入的利润率差异很大，总体上低于广告收入的利润率。',
    'Year Ended December 31,20242025Google Search & other$198,084 $224,532 YouTube ads36,147 40,367 Google Network30,359 29,792 Google advertising264,590 294,691 Google subscriptions, platforms, and devices40,340 48,030 Google Services total304,930 342,721 Google Cloud43,229 58,705 Other Bets1,648 1,537 Hedging gains (losses)211 (127)Total revenues$350,018 $402,836':
    '截至 12 月 31 日的年度；以下每行依次为 2024 年、2025 年的表内数值（本段摘录未包含金额单位）：\nGoogle 搜索及其他：$198,084 / $224,532\nYouTube 广告：36,147 / 40,367\nGoogle 广告网络：30,359 / 29,792\nGoogle 广告合计：264,590 / 294,691\nGoogle 订阅、平台和设备：40,340 / 48,030\nGoogle Services 合计：304,930 / 342,721\nGoogle Cloud：43,229 / 58,705\nOther Bets：1,648 / 1,537\n套期保值收益（损失）：211 / (127)\n总收入：$350,018 / $402,836',
    'Expanded AI Offerings in our Products and Services: The continuing evolution of the online world has contributed to the growth of our business. We expect that this evolution, including user engagement with AI products and services, will continue to benefit our business and our revenues. As we continue to incorporate AI into our products and services, such as with AI Overviews and AI Mode in Search, and with enterprise AI solutions on our Google Cloud Platform, we may monetize differently than our historical consumer and enterprise offerings which could affect revenue growth rates and margin trends. When developing new products and services we generally focus first on user experience and then on monetization. At the same time, we face increasing competition, including from other developers and providers of AI products and services, which may affect our revenues.':
    '扩展产品和服务中的 AI 功能：互联网世界的持续演进促进了我们的业务增长。我们预计，包括用户使用 AI 产品和服务在内的这一演进，将继续惠及我们的业务和收入。随着我们持续将 AI 融入产品和服务，例如搜索中的 AI Overviews 和 AI Mode，以及 Google Cloud Platform 上的企业 AI 解决方案，其变现方式可能不同于以往的消费者和企业产品，这可能影响收入增速和利润率趋势。开发新产品和服务时，我们通常先关注用户体验，再考虑变现。与此同时，我们面临日益激烈的竞争，包括来自其他 AI 产品和服务开发商及供应商的竞争，这可能影响收入。',
    'We generate a significant portion of our revenues from advertising. Reduced spending by advertisers, a loss of partners, shifts in online advertising, new and evolving advertising formats, or new or existing technologies that block ads online or affect our ability to personalize ads could harm our business.':
    '我们的收入有很大一部分来自广告。广告主减少支出、合作伙伴流失、在线广告发生变化、新兴或不断演进的广告形式，以及屏蔽在线广告或影响我们提供个性化广告能力的新旧技术，都可能损害我们的业务。',
    'We generated more than 70% of total revenues from online advertising in 2025. Many of our advertisers, companies that distribute our products and services, digital publishers, and content providers can terminate their contracts with us at any time. These partners may not continue to do business with us if we do not create more value (such as increased numbers of users or customers, new sales leads, increased brand awareness, or more effective monetization) than their available alternatives.':
    '2025 年，我们超过 70% 的总收入来自在线广告。许多广告主、分销我们产品和服务的公司、数字出版商及内容提供商，可以随时终止与我们的合同。如果我们创造的价值不及他们可选择的其他方案，例如增加用户或客户、带来新销售线索、提高品牌知名度或更有效地变现，这些合作伙伴可能不再与我们合作。',
    'We believe AI is quickly reshaping the advertising industry, including how ads are delivered online, and we and our competitors are constantly adjusting to meet this shift and provide new and evolving advertising formats. There is no assurance that we will adapt effectively and competitively to meet this shift, and that such advertising formats, strategies, and offerings will be successful.':
    '我们认为 AI 正在迅速重塑广告行业，包括在线广告的投放方式。我们和竞争对手不断调整，以应对这一变化，并提供新兴和不断演进的广告形式。我们无法保证能以有效且具竞争力的方式适应这一变化，也无法保证这些广告形式、策略和产品能够成功。',
    "Changes to our advertising policies and data privacy practices, as well as changes to other companies' advertising or data privacy practices have in the past, and may in the future, affect the advertising services that we are able to provide. In addition, technologies have been developed that make personalized ads more difficult, or that block the display of ads altogether, and some providers of online services have integrated technologies that could impair the availability and functionality of third-party digital advertising. Failing to provide superior value or deliver advertisements effectively and competitively could harm our business, reputation, financial condition, and operating results.":
    '我们自身广告政策和数据隐私实践的变化，以及其他公司广告或数据隐私实践的变化，过去已经、未来也可能影响我们能够提供的广告服务。此外，已有技术使个性化广告更难实现，或完全屏蔽广告展示；一些在线服务提供商也已集成可能损害第三方数字广告可用性和功能的技术。若无法提供更高价值，或无法以有效且具竞争力的方式投放广告，可能损害我们的业务、声誉、财务状况及经营业绩。',
    'Expenditures by advertisers tend to correlate with overall economic conditions. Adverse macroeconomic conditions have affected, and may in the future affect, the demand for advertising, resulting in fluctuations in the amounts our advertisers spend on advertising, which could harm our financial condition and operating results.':
    '广告主的支出往往与整体经济状况相关。不利的宏观经济状况过去已经、未来也可能影响广告需求，导致广告主的广告支出波动，进而可能损害我们的财务状况和经营业绩。',
    'Increased Investment in Technical Infrastructure: We continue to invest in capital expenditures as we scale our technical infrastructure, in particular for AI, to meet the demand of our users and enterprise customers and to support research internally. We invested heavily in capital expenditures in 2025 and in 2026, we expect to significantly increase, relative to 2025, our investment in our technical infrastructure, including servers and network equipment, and data centers. The costs associated with operating our technical infrastructure - depreciation, energy, equipment, and network capacity - are expected to significantly increase as developing and serving AI offerings require more compute power than our historical consumer and enterprise offerings. While our technical infrastructure costs increase, we expect to continue to drive efficiencies in our data centers, for example, through the design of our AI models and our TPU and GPU-based technical infrastructure.':
    '增加技术基础设施投资：我们持续进行资本开支，扩大技术基础设施，尤其是 AI 相关设施，以满足用户和企业客户需求，并支持内部研究。2025 年我们投入了大量资本开支，预计 2026 年将较 2025 年显著增加技术基础设施投资，包括服务器、网络设备和数据中心。由于开发和提供 AI 产品所需算力高于以往的消费者和企业产品，运行技术基础设施涉及的折旧、能源、设备及网络容量成本预计将显著增加。在成本上升的同时，我们预计将继续提高数据中心效率，例如通过 AI 模型设计，以及基于 TPU 和 GPU 的技术基础设施设计来实现。',
    '•Capital expenditures, which primarily reflected investments in technical infrastructure, were $91.4 billion for the year ended December 31, 2025.':
    '截至 2025 年 12 月 31 日的年度，资本开支为 914 亿美元，主要用于技术基础设施投资。',
    '•Operating cash flow was $164.7 billion for the year ended December 31, 2025.':
    '截至 2025 年 12 月 31 日的年度，经营现金流为 1,647 亿美元。',
    '•In 2025, we entered into definitive agreements to acquire Wiz, a leading cloud security platform, for $32.0 billion, and Intersect, a provider of data center and energy infrastructure solutions, for $4.8 billion in cash plus the assumption of debt. Both acquisitions are expected to close in 2026, subject to customary closing conditions, including the receipt of regulatory approvals.':
    '2025 年，我们签订最终协议，以 320 亿美元收购领先的云安全平台 Wiz，并以 48 亿美元现金加承接债务的方式收购数据中心及能源基础设施解决方案提供商 Intersect。两项收购预计于 2026 年完成，但须满足惯常交割条件，包括获得监管批准。',
    '•Other Bets operating loss of $7.5 billion for the year ended December 31, 2025 included a $2.1 billion employee compensation charge recognized in the fourth quarter for Waymo, primarily reflected in research and development expenses, based on estimated stock valuation. In February 2026, Waymo announced an investment round of $16.0 billion, the significant majority of which was funded by Alphabet.':
    '截至 2025 年 12 月 31 日的年度，Other Bets 经营亏损为 75 亿美元，其中包括第四季度基于估计股票估值确认的 21 亿美元 Waymo 员工薪酬费用，主要计入研发费用。2026 年 2 月，Waymo 宣布完成一轮 160 亿美元融资，绝大部分由 Alphabet 提供。',
    '•Repurchases of Class A and Class C shares were $6.5 billion and $38.9 billion, respectively, totaling $45.4 billion for the year ended December 31, 2025.':
    '截至 2025 年 12 月 31 日的年度，A 类及 C 类股票回购金额分别为 65 亿美元和 389 亿美元，合计 454 亿美元。',
    'Our operations and financial results are subject to various risks and uncertainties, including but not limited to those described below, which could harm our business, reputation, financial condition, and operating results, and may affect the trading price and price volatility of our Class A and Class C stock.':
    '我们的运营和财务业绩面临各种风险和不确定性，包括但不限于下述事项。这些因素可能损害我们的业务、声誉、财务状况及经营业绩，并可能影响 A 类和 C 类股票的交易价格及价格波动。',
    'Google Services total 342,721': 'Google Services 合计 342,721',
    'Google Cloud 58,705': 'Google Cloud（谷歌云）58,705',
    'Other Bets1,537': 'Other Bets（其他业务）1,537',
    'more than 70% of total revenues from online advertising in 2025': '2025 年超过 70% 的总收入来自在线广告',
    'Google Search & other revenues increased $26.4 billion': 'Google 搜索及其他收入增加 264 亿美元',
    'increases in search queries': '搜索查询量增加',
    'growth in advertiser spending': '广告主支出增长',
    'improvements ... in ad formats and delivery': '广告形式及投放方面的……改进',
    'AI is quickly reshaping the advertising industry': 'AI 正在迅速重塑广告行业',
    'AI Overviews and AI Mode in Search': '搜索中的 AI 概览和 AI 模式',
    'enterprise AI solutions on our Google Cloud Platform': 'Google Cloud Platform 上的企业 AI 解决方案',
    'we may monetize differently': '我们可能采用不同的变现方式',
    'could affect revenue growth rates and margin trends': '可能影响收入增速和利润率趋势',
    'growing at a rate higher than our advertising revenues': '增速高于我们的广告收入',
    'becoming a larger percentage of our consolidated revenues': '占合并收入的比例不断上升',
    'Google Cloud revenues are comprised of the following': 'Google Cloud 收入由以下部分组成',
    'consumption-based fees and subscriptions': '按用量收费和订阅',
    'changes in customer usage, demand, and supply availability': '客户使用量、需求及供应可用性的变化',
    'margins ... are generally lower': '利润率……总体较低',
    'significantly increase ... investment in our technical infrastructure': '显著增加……技术基础设施投资',
    'depreciation, energy, equipment, and network capacity': '折旧、能源、设备和网络容量',
    'technologies have been developed that make personalized ads more difficult': '已有技术使个性化广告更难实现',
    'Adverse macroeconomic conditions': '不利的宏观经济状况',
    'changes in our advertising policies and data privacy practices': '我们广告政策及数据隐私实践的变化',
    'evolving regulatory environment': '不断变化的监管环境',
    'we may continue to incur fines': '我们可能继续面临罚款',
    'increased costs associated with compliance': '合规相关成本增加',
    'TAC rate will continue to be affected': '流量获取成本（TAC）率将继续受到影响',
    'TAC paid to our distribution partners': '支付给分销合作伙伴的流量获取成本（TAC）',
    'credit support ... to certain infrastructure related counterparties': '向某些基础设施相关交易对手提供的……信用支持',
    'YouTube ads revenues increased $4.2 billion': 'YouTube 广告收入增加 42 亿美元',
    'growth in paid subscriptions across both YouTube services and Google One': 'YouTube 服务和 Google One 的付费订阅均增长',
    'YouTube ads36,147 40,367': 'YouTube 广告：36,147 / 40,367',
    'We believe AI is quickly reshaping the advertising industry': '我们认为 AI 正在迅速重塑广告行业',
    'We expect that this evolution ... will continue to benefit our business': '我们预计这一演进……将继续惠及业务',
    'limitations on our ability to pursue certain business practices': '限制我们开展某些商业活动的能力',
    'Alphabet is a collection of businesses — the largest of which is Google.': 'Alphabet 由一系列业务组成，其中最大的是 Google。',
    'We report Google in two segments, Google Services and Google Cloud; we also report all non-Google businesses collectively as Other Bets.': '我们将 Google 分为 Google Services 和 Google Cloud 两个分部进行报告，并将所有非 Google 业务统称为 Other Bets。',
    'Google Search helps people find information... YouTube provides... Google Cloud helps customers solve today’s business challenges': 'Google 搜索帮助人们查找信息……YouTube 提供……Google Cloud 帮助客户应对当今的业务挑战',
    'Google advertising 237,855 264,590': 'Google 广告：237,855 / 264,590',
    'Google Services total 272,543 304,930': 'Google Services 合计：272,543 / 304,930',
    'Google Services $95,858 $121,263': 'Google Services：$95,858 / $121,263',
    'Google Cloud 1,716 6,112': 'Google Cloud：1,716 / 6,112',
    'Google Search & other revenues increased $23.1 billion from 2023 to 2024.': '2023 至 2024 年，Google 搜索及其他收入增加 231 亿美元。',
    'driven by... increases in search queries... growth in advertiser spending; and improvements... in ad formats and delivery.': '由……搜索查询量增加……广告主支出增长，以及广告形式和投放方面的……改进所驱动。',
    'YouTube ads revenues increased $4.6 billion from 2023 to 2024.': '2023 至 2024 年，YouTube 广告收入增加 46 亿美元。',
    'benefited from increased spending by our advertisers.': '受益于广告主增加支出。',
    'an increase of 14% year over year, primarily driven by... Google Services revenues... 12%, and... Google Cloud revenues... 31%.': '同比增长 14%，主要由……Google Services 收入……12%，以及……Google Cloud 收入……31% 所驱动。',
    'Google Cloud revenues are comprised of the following:': 'Google Cloud 收入由以下部分组成：',
    'solutions such as AI offerings including our AI infrastructure, Vertex AI': '诸如 AI 产品等解决方案，包括我们的 AI 基础设施、Vertex AI',
    'we face increasing competition... including from other developers and providers of AI products and services': '我们面临日益激烈的竞争……包括来自其他 AI 产品和服务开发商及供应商的竞争',
    'our implementation of AI systems could subject us to competitive harm, regulatory action, legal liability': '我们部署 AI 系统可能使我们面临竞争方面的损害、监管行动及法律责任',
    'may result in claims, lawsuits, brand or reputational harm, and increased regulatory scrutiny': '可能导致索赔、诉讼、品牌或声誉受损，以及更严格的监管审查',
    'systems and control failures, security breaches... could result in regulatory and legal exposure': '系统和控制失效、安全漏洞……可能导致监管和法律风险',
    'Changes to our advertising policies and data privacy practices... related to third-party cookies': '我们广告政策及数据隐私实践的变化……与第三方 Cookie 相关',
    'could harm our business, reputation, financial condition, and operating results': '可能损害我们的业务、声誉、财务状况及经营业绩',
    'Data privacy and security concerns... could harm our reputation, cause us to incur significant liability': '数据隐私和安全方面的担忧……可能损害我们的声誉，使我们承担重大责任',
    'several antitrust lawsuits about various aspects of our business': '涉及我们业务多个方面的数起反垄断诉讼',
    'Google violated antitrust laws relating to Search and Search advertising': 'Google 违反了涉及搜索和搜索广告的反垄断法',
    'ordered a variety of alterations to our business models and operations': '责令对我们的商业模式和运营作出多项调整',
    'we anticipate that they will continue to affect our future results': '我们预计这些因素将继续影响未来业绩',
    'at a slower pace than we have experienced historically': '速度慢于我们的历史水平',
    'new advertising formats that may benefit our revenues but adversely affect our margins': '可能有利于收入、但不利于利润率的新广告形式',
    'primarily driven by an increase in Google Services revenues... and an increase in Google Cloud revenues': '主要由 Google Services 收入增长……以及 Google Cloud 收入增长所驱动',
    'Google Services $121,263': 'Google Services：$121,263',
    'Google Cloud 6,112': 'Google Cloud：6,112',
    'could face signif': '可能面临……〔原始引用在 signif 处截断〕',
    'could subject us to competitive harm, regulatory action, legal liability': '可能使我们面临竞争方面的损害、监管行动及法律责任',
    'could harm our reputation, cause us to incur significant liability': '可能损害我们的声誉，使我们承担重大责任',
    'may benefit our revenues but adversely affect our margins': '可能有利于收入，但不利于利润率',
    'The following long-term trends have contributed to the results of our consolidated operations, and we anticipate that they will continue to affect our future results:': '以下长期趋势对我们的合并经营业绩产生了影响，我们预计它们将继续影响未来业绩：',
    '•As we continue to grow our business and meet the evolving behaviors and needs of our users and customers, our revenue growth and mix along with our cost and margin profiles are being influenced by a number of factors, including:': '随着我们持续发展业务，满足用户和客户不断变化的行为及需求，我们的收入增长和构成，以及成本和利润率状况，正受到多种因素影响，包括：',
    '•Revenues were $402.8 billion, an increase of 15% year over year, primarily driven by an increase in Google Services revenues of $37.8 billion, or 12%, and an increase in Google Cloud revenues of $15.5 billion, or 36%.': '收入为 4,028 亿美元，同比增长 15%，主要由 Google Services 收入增加 378 亿美元（增长 12%），以及 Google Cloud 收入增加 155 亿美元（增长 36%）所驱动。',
    'Description of the MatterThe Company is subject to claims, lawsuits, regulatory and government inquiries and investigations, other proceedings, and consent orders. As described in Note 10 to the consolidated financial statements, such claims, lawsuits, regulatory and government inquiries and investigations, other proceedings, and consent orders could result in adverse consequences.Significant judgment is required to determine both the likelihood and the estimated amount of a loss related to such matters. Auditing management’s accounting for and disclosure of loss contingencies from these matters involved challenging and subjective auditor judgment in assessing the Company’s evaluation of the probability of a loss, and the estimated amount or range of loss.How We Addressed the Matter in Our AuditWe tested relevant controls over the identified risks associated with management’s accounting for and disclosure of these matters. This included controls over management’s assessment of the probability of incurrence of a loss and whether the loss or range of loss was reasonably estimable and the development of related disclosures.Our audit procedures included, among others, gaining an understanding of previous rulings and the status of ongoing lawsuits, reviewing letters from internal and external legal counsel addressing the matters, meeting with internal legal counsel to discuss the allegations, and obtaining a representation letter from management on these matters. We also evaluated the Company’s disclosures in relation to these matters.':
    '事项说明\n公司面临索赔、诉讼、监管及政府问询与调查、其他法律程序以及同意令。如合并财务报表附注 10 所述，这些事项可能产生不利后果。判断相关损失发生的可能性及估计金额，需要作出重大判断。在审计管理层对此类或有损失的会计处理和披露时，审计师需要运用具有挑战性且主观的判断，以评估公司对损失发生概率及预计损失金额或范围的判断。\n我们在审计中如何应对\n我们测试了与管理层对此类事项的会计处理和披露所涉已识别风险相关的控制，包括管理层评估损失发生概率、损失金额或范围能否合理估计，以及编制相关披露的控制。我们的审计程序包括了解既有裁决及在审诉讼状态，审阅内部及外部法律顾问就这些事项出具的函件，与内部法律顾问会面讨论相关指控，并就这些事项取得管理层声明书。我们还评估了公司的相关披露。',
    'To meet the compute capacity demands of AI training and inference, as well as traditional cloud computing services, we are entering into significant leasing arrangements with third party operators, which may increase costs and operational complexity. We also have a number of large, long-duration commercial agreements, which could increase our liabilities and obligations in the event of nonperformance by us, our counterparties, or vendors. In such nonperformance or an industry downturn, we may incur additional liabilities, have excess capacity that we cannot easily redeploy, and not receive payments from our counterparties or customers.':
    '为满足 AI 训练和推理以及传统云计算服务的算力需求，我们正在与第三方运营商签订重大租赁安排，这可能增加成本及运营复杂性。我们还签有多项大规模、长期商业协议；如果我们、交易对手或供应商未履约，可能增加我们的负债及义务。在此类未履约情形或行业低迷时，我们可能承担额外负债，出现难以重新调配的过剩容量，并且无法收到交易对手或客户的付款。',
    'Google Cloud operating income increased $7.8 billion': 'Google Cloud 经营利润增加 78 亿美元',
}


def translated_quote(citation):
    return TRANSLATIONS.get(normalize_quote(citation.get('quote')), '')
