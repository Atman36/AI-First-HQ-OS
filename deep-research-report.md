# Чем реально занимаются топовые CMO, CPO, Growth и SEO-специалисты в 2024–2026

## Контекст и ограничения исследования

**Контекст (не указан пользователем, поэтому фиксирую как “unknown”):**
- Тип бизнеса: не указан (часть практик ниже ориентирована на digital‑продукты, особенно B2B SaaS / подписочные модели).
- Стадия: не указана (в примерах артефактов и метрик отмечаю различия 0→1 / PMF / Scale).
- Гео/язык: ru‑RU, дата анализа 2026‑02‑16 (Europe/Berlin).
- Каналы: не указаны (в блоках Growth/CMO/SEO рассматриваю гибрид: SEO + paid + partnerships + sales/PLG).
- Ограничения: не указаны (в “best practices” отдельно учитываю комплаенс/приватность и регулирование ИИ в ЕС).

**Что считаю “топовой работой” в этом исследовании:** не “ведение канала”, а **управление системой**: выбор моделей роста/ценности, постановка измерений, управление рисками (включая комплаенс), и обеспечение межфункциональной исполнимости через артефакты и ритмы. Это напрямую отражено в актуальных источниках по маркетинг‑лидерству, измерению и SEO‑политикам. citeturn3search1turn3search5turn24view1turn12search0turn9search2

**Основные “живые” источники, на которые опираюсь (приоритет):** официальная документация и блоги entity["company","Google","search and ads company"] (Search Central, Ads/Tag docs), entity["company","Microsoft","software and cloud company"] (Bing Webmaster), entity["organization","European Commission","eu executive body"] (EU AI Act), entity["organization","NIST","us standards agency"] (CSF/AI RMF), а также признанные практики/плейбуки entity["organization","Silicon Valley Product Group","product management firm"], entity["company","Amplitude","product analytics company"], entity["company","Reforge","growth education firm"], entity["company","Gartner","research and advisory firm"], entity["company","Forrester","research and advisory firm"], entity["organization","The CMO Survey","marketing benchmark survey"], отраслевые бенчмарки и стандарты entity["company","SBI Growth","pricing consultancy"], entity["company","Bessemer Venture Partners","venture capital firm"], entity["company","Meta","social media company"] (Conversions API), entity["company","Apple","consumer electronics company"] (AdAttributionKit), entity["organization","DORA","devops research program"], entity["company","McKinsey & Company","management consulting firm"], entity["organization","AICPA","accounting profession org"] (SOC 2), entity["organization","International Organization for Standardization","standards body"] (ISO 27001), entity["company","IBM","enterprise tech company"] (data governance), entity["company","Gainsight","customer success company"] (CS metrics), а также разборы/интервью операторов (например, подкасты и материалы Search Central и др.). citeturn22view0turn22view1turn22view2turn1search0turn5search2turn5search3turn26search0turn14search0turn10search0turn10search1turn14search2

(Для продуктовой части как опорные “операторские” практики использую подходы entity["people","Marty Cagan","product management author"] и entity["people","Teresa Torres","product discovery author"], т.к. это де‑факто стандартные референсы для discovery/delivery и continuous discovery, активно обсуждаемые и обновляемые в 2024–2025 публичных выступлениях/эфирах.) citeturn2search18turn2search9turn2search13turn2search6

## Executive summary

- В 2024–2026 “топ” в маркетинге и росте — это **доказуемая причинность** влияния на выручку/пайплайн и устойчивость к потере сигналов (privacy): рост роли **incrementality‑экспериментов**, серверных/first‑party измерений (Consent Mode v2, Enhanced Conversions, Conversions API). citeturn9search2turn26search3turn9search0turn9search1turn7search12turn9search3
- Данные entity["organization","The CMO Survey","marketing benchmark survey"] показывают давление на бюджеты и перераспределение: маркетинг‑расходы как доля общего бюджета снижаются (Spring 2024: 10.2% бюджета; 10.1% выручки), а также фиксируется использование generative AI (в среднем 7% времени) при умеренной уверенности в управлении рисками (bias/безопасность/понимание решений). citeturn17view1turn17view0turn17view2turn17view3
- Для SEO 2024–2026 ключевое — **политики качества/спама и их enforcement**, а не “лайфхаки”: March 2024 core update + новые spam policies (expired domain abuse, scaled content abuse, site reputation abuse), и уточнение site reputation abuse в Nov 2024. citeturn24view1turn24view0turn12search4
- “Паразитное SEO” (site reputation abuse) стало не только технической темой, но и **управленческим риском** (каноникал/редиректы не спасают от policy‑нарушений; важен контроль third‑party контента). citeturn24view0turn24view1turn0news39
- Для крупных и динамичных сайтов Google отдельно акцентирует **crawl budget** и то, что большинству сайтов он не критичен; базовая норма — поддерживать sitemap и контролировать index coverage. (Crawl budget guidance обновлялась 19 Dec 2025.) citeturn22view2turn0search1turn6search7
- В индексации “топ”‑практика — управлять **сигналами каноникализации** системно: rel=canonical + внутренние ссылки на canonical + sitemap как сигнал canonical; при “удалении дублей” быстрее всего работают server‑side 3xx. citeturn22view0turn22view1turn21view0
- Sitemaps в 2025‑12‑10 редакции документации: Google игнорирует `<priority>` и `<changefreq>`, а `<lastmod>` использует, если он **стабильно проверяемо точен**. citeturn21view1turn21view0
- Robots.txt в официальной трактовке — инструмент для управления crawl‑нагрузкой, **не** для скрытия страниц из поиска; для исключения из индекса нужны `noindex`/аутентификация. citeturn1search6turn1search14
- В продукте лидеры (CPO) и сильные команды выстраивают операционную модель, где одна кросс‑функциональная команда отвечает и за discovery, и за delivery; product discovery проверяет value/usability/feasibility/viability. citeturn13search1turn2search18turn2search6
- Align‑метрика уровня компании (North Star Metric) описывается как leading indicator customer value и устойчивых бизнес‑результатов; сильные организации связывают customer value ↔ продукт ↔ бизнес через NSM и связанные input‑метрики. citeturn2search1turn2search4turn2search7
- В росте “лупы” всё чаще используются как модель, превосходящая воронку для системного роста: петля — замкнутая система, где output реинвестируется во вход; важна количественная модель, чтобы сравнивать рычаги. citeturn2search5turn2search2turn2search15
- На уровне CTO/engineering “топ”‑метрики исполнения — семейство DORA (throughput + stability); DORA подчёркивает их как отраслевой стандарт, а в 2026 опубликованы обновлённые определения метрик. citeturn5search12turn5search1
- В комплаенсе и безопасности усилилась регуляторика ИИ: EU AI Act вступил в силу 1 Aug 2024; NIST выпустил GenAI Profile к AI RMF 26 Jul 2024, а CSF 2.0 добавил функцию Govern и рамку для risk governance. citeturn5search3turn5search2turn25view3turn25view1

## Сводная таблица по ролям

Таблица — “сжатая карта” ownership‑зон, метрик и артефактов, собранная по официальным докам поисковиков/маркет‑платформ и признанным playbooks по продукту/росту/операциям. citeturn13search9turn3search1turn12search0turn22view0turn22view2turn5search1turn4search2turn25view3

| Роль | Scope (за что отвечает) | KPI (ядро) | Артефакты (выходы) | Ключевые решения |
|---|---|---|---|---|
| CMO | Бренд + спрос + lifecycle + маркет‑система | Pipeline/Revenue impact, CAC/efficiency, Brand lift | GTM‑план, бюджет/микс, messaging, dashboard | Канальный микс, позиционирование, измерение/атрибуция |
| CPO | Стратегия продукта, discovery/delivery, ценность | NSM, retention/churn, adoption, outcomes | Product strategy, discovery backlog, roadmap, PRD/briefs | Приоритет проблем, trade‑offs value/feasibility, метрики ценности |
| Head of Growth | Эксперименты, growth‑model, петли | Activation, retention, LTV/CAC, incrementality | Growth model, experiment backlog, learnings | Выбор луп/рычагов, дизайн экспериментов, scale winners |
| SEO Redirect/Canonical Expert | Каноникализация, редиректы, миграции | Indexation correctness, dupes rate, traffic stability | Redirect map, canonical rules, migration runbook | 301/302/308 политика, canonical стратегия, anti‑patterns |
| SEO Indexing & Crawl Budget Expert | Crawl/index управление, sitemaps, robots | Crawl stats, index coverage, time‑to‑index | Crawl/index dashboard, log analysis, sitemap strategy | Crawl budget приоритизация, блокировки, IndexNow |
| SEO Content Quality Expert | Качество контента, anti‑spam, E‑E‑A‑T/YMYL | Organic quality signals, penalty risk, engagement | Content guidelines, audit, обновления, QA чек‑листы | Что удалять/сливать/переписывать, политика AI‑контента |
| Growth/Traffic Strategy Expert | Микс SEO + paid + партнёрки | Incremental revenue, blended CAC, share of voice | Channel portfolio, MMM/experiments plan | Аллокация бюджета, “где причинность”, офферы/лендинги |
| CRO (Revenue) | Весь revenue cycle, выручка end‑to‑end | ARR growth, NRR/GRR, forecast accuracy | Revenue plan, coverage model, comp principles | ICP, сегментация, квоты/компенсации, pipeline governance |
| CTO | Платформа разработки/скорость/качество/риски | DORA, reliability, security posture | Tech strategy, architecture, eng metrics | Build vs buy, roadmap платформы, SLO/SLA |
| COO | Исполнение стратегии в операциях | Unit economics ops, throughput ops, SLA по процессам | Operating cadence, process maps, OKR ops | Оргдизайн, приоритеты инициатив, scaling процессов |
| CFO | Финансовая модель, капитал‑эффективность | Rule of 40/X, burn multiple, gross margin | FP&A model, budget, board pack | Инвестиции, pricing guardrails, risk appetite |
| CISO | Risk management, комплаенс, security governance | CSF maturity, incidents, audit readiness | Security policies, threat model, IR plan | Control framework, vendor risk, AI risk governance |
| Head of RevOps | Единый revenue‑движок (данные+процессы) | Data quality, funnel conversion, SLA handoffs | GTM taxonomy, dashboards, process playbooks | Definition of pipeline, routing, tooling architecture |
| Head of Data/Analytics | Data governance, метрики, доступность данных | Data quality, adoption, time‑to‑insight | Metric layer, data contracts, governance | Single source of truth, privacy, data product priorities |
| Head of CS | Удержание/расширение, value realization | NRR/GRR, churn, health score | CS playbooks, QBRs, adoption programs | Segmentation, renewal motion, escalation policies |

## Маркетинг и рост

**Роль: CMO**

A) **За что отвечает (scope/ownership).** CMO — корпоративный лидер, отвечающий за маркетинговую функцию с основным ожиданием влияния на выручку через бренд, коммуникации, исследования, product marketing и управление каналами/ценой/клиентским опытом (в зависимости от орг‑дизайна). citeturn13search9turn3search5turn3search1

B) **Топ типовых задач и решений (как выглядит работа).**
1) Переформулировать/подтвердить позиционирование и message hierarchy под ICP/сегменты и текущие GTM‑реалии. citeturn13search9turn3search5  
2) Собрать/обновить channel portfolio (paid/owned/earned, включая SEO) и правила аллокации бюджетов. citeturn3search9turn9search2  
3) Настроить систему доказательства влияния маркетинга на pipeline/revenue (в т.ч. через incrementality). citeturn3search12turn9search2turn26search3  
4) Утвердить “measurement architecture” под privacy: consent signals, modeled conversions, server‑side/first‑party интеграции. citeturn9search0turn9search1turn7search12  
5) Управлять брендом как активом: исследования, brand tracking, share‑of‑search/voice и связь с коммерческими метриками. citeturn3search5turn3search1  
6) Сформировать GTM‑планы по ключевым продуктам/сегментам (совместно с CPO/CRO): оффер, упаковка, каналы, enablement. citeturn13search9turn18view0  
7) Построить lifecycle‑маркетинг: onboarding/activation, побуждение к value realization, win‑back. citeturn2search4turn14search0  
8) Удерживать баланс “рост сейчас vs построение спроса в будущем” при давлении бюджета и ожиданий ROI. citeturn3search1turn17view0  
9) Внедрить GenAI в процессы с контролем рисков (bias, безопасность данных, explainability) и экономическим эффектом. citeturn17view2turn17view3turn5search3  
10) Управлять MOPS/MarTech: процессы, качество данных, сквозная аналитика, интеграции. citeturn13search2turn4search2  

C) **KPI/метрики: leading + lagging (и что НЕ считать успехом).**
- **Leading:** brand search/share‑of‑search (как прокси awareness), MQL→SQL скорость/конверсия (если релевантно), activation rate или “aha‑момент”, доля first‑party идентифицируемых событий, покрытие incrementality‑тестами/экспериментами, скорость запуска кампаний (marketing ops throughput). citeturn2search4turn9search2turn13search2  
- **Lagging:** sourced/influenced pipeline, revenue impact, CAC и CAC payback, LTV:CAC, NRR/retention (особенно в PLG/подписке), gross margin contribution. citeturn3search12turn4search15turn14search4turn10search6  
- **Не считать успехом:** “трафик/клики любой ценой”, рост MQL без валидной конверсии в revenue, атрибуция без проверки причинности (last click/biased MTA), GenAI‑контент, который увеличивает объём, но рождает риск санкций/падение доверия. citeturn9search2turn24view1turn12search0  

D) **Артефакты/документы.**
GTM‑план на квартал/полугодие; media mix plan; бренд‑платформа/позиционирование; KPI tree; маркетинг‑dashboard; спецификация измерений/consent; campaign briefs; growth calendar; martech roadmap; годовой бюджет и сценарии. citeturn13search2turn9search0turn17view0turn3search12

E) **Инструменты/стек (категории).**
CRM + marketing automation; CDP/identity; product analytics; BI; attribution/MMM/incrementality; ad platforms; consent/CMP; experimentation; SEO toolset; data warehouse + ETL/ELT; creative/PM tools. citeturn9search2turn9search0turn4search2  

F) **Best practices 2024–2026 (как делают сильные).**
1) **Строят measurement вокруг причинности:** регулярная программа incrementality‑тестов, а не разовые “кейсы”. (Google называет incrementality “gold standard” для privacy‑first измерения; в 2025–2026 Google расширяет доступность/встроенность таких тестов.) citeturn9search2turn26search3turn26search11  
2) **Переносят измерения в first‑party и server‑side:** Consent Mode v2 для EEA‑трафика + Enhanced Conversions (хэширование first‑party данных) + CAPI‑подход “redundant events” (pixel+server). citeturn9search0turn9search1turn7search12  
3) **Управляют MarTech как продуктом:** процессы/данные/технологии под эффективность и воспроизводимость (marketing ops как “backbone”). citeturn13search2turn4search2  
4) **Синхронизируют brand и demand под бюджетное давление:** Gartner фиксирует, что CMOs под давлением ROI/AI‑инвестиций и ожиданий роста ищут способы доказать ценность и обеспечить устойчивый рост при ограничениях. citeturn3search1turn3search5  
5) **Формализуют AI‑governance в маркетинге:** учитывают риск bias/безопасности/объяснимости (такие проблемы прямо отражены в CMO Survey как зоны низкой уверенности). citeturn17view3turn17view2turn5search3  
6) **Сближают CMO↔CPO↔CRO на уровне “единых определений”:** единая таксономия лидов/пайплайна/NRR и ясные handoffs — типовая логика RevOps‑модели. citeturn4search2turn3search12  
7) **Не масштабируют каналы без контроля качества контента и комплаенса:** особенно при росте AI‑контента и ужесточении spam policies (SEO‑риски становятся рисками бренда/дохода). citeturn24view1turn12search0turn6news39  

G) **Частые ошибки/антипаттерны.**
- “Sourced pipeline” как единственная истина (Forrester отмечает доминирование sourcing‑метрик на дашбордах, но это не равно измерению реального влияния). citeturn3search12  
- Сведение measurement к атрибуции без экспериментального контроля (нет инкрементальности). citeturn9search2turn26search11  
- AI‑масштабирование креатива/контента без brand safety и без политики данных. citeturn17view3turn24view1  
- Разрыв между “стратегией” и “операциями” маркетинга (отсутствие MOPS‑ритма). citeturn13search2turn3search5  
- Ставка на рост spend без доказанной экономической эффективности при снижении бюджетной доли/давлении ROI. citeturn17view0turn3search1  

H) **Как взаимодействует с другими ролями (RACI/стыки решений).**
- **Позиционирование/бренд‑обещание:** A=CMO, R=Brand/PMM, C=CPO/CRO/CS, I=CEO/COO. citeturn13search9  
- **Measurement architecture (consent/first‑party):** A=CMO, R=Head of Marketing Ops/Analytics, C=Head of Data/CISO/CTO, I=CFO. citeturn9search0turn4search2turn25view3  
- **GTM по сегменту:** A=CMO+CRO (совместно), R=PMM+Sales leaders, C=CPO/RevOps, I=COO/CFO. citeturn4search2turn13search9  

**Роль: Head of Growth / Growth Lead**

A) **За что отвечает.** Growth Lead владеет системой роста: формирует модель (воронки/петли), управляет портфелем экспериментов и масштабирует “победителей” через продуктовые, маркетинговые и GTM‑изменения. citeturn2search5turn2search2turn2search4

B) **Топ типовых задач и решений.**
1) Собрать growth model: ключевые входы/выходы, ограничения, target metrics. citeturn2search2turn2search15  
2) Определить North Star + input metrics (activation/retention/proxy value). citeturn2search4turn2search1  
3) Построить/выбрать growth loops (referral/content/usage/paid‑powered) и критерии качества лупа. citeturn2search5turn2search15  
4) Запустить experiment cadence: backlog → дизайн → запуск → анализ → decision → rollout. citeturn9search2turn26search11  
5) Настроить “guardrails”: качество, безопасность, бренд‑риски, уязвимость к спаму/манипуляциям. citeturn24view1turn12search0turn25view3  
6) Построить growth analytics: когортный анализ, влияние на retention/NRR, incremental impact. citeturn9search2turn4search15  
7) Согласовать с продуктом “где рост решается продуктом, а где — каналом”. citeturn13search1turn2search18  
8) Согласовать с маркетингом и RevOps правила lead→PQL→SQL, routing и SLAs. citeturn4search2turn2search20  
9) Перевести часть роста в автоматизацию/AI с контролем качества и комплаенса. citeturn17view2turn5search3  
10) После победы — стандартизировать: playbook, инструментирование, мониторинг деградации. citeturn2search15turn5search1  

C) **KPI/метрики.**
- **Leading:** activation/aha rate, time‑to‑value, loop conversion rates, experiment win‑rate и “impact per experiment”, доля трафика/выручки с доказанной инкрементальностью. citeturn2search4turn9search2turn2search2  
- **Lagging:** рост активной базы, retention/NRR, LTV:CAC, CAC payback, ARR/Revenue uplift. citeturn4search15turn14search4turn10search6  
- **Не считать успехом:** частоту экспериментов без “learning quality”, улучшение “прокси‑метрик” при ухудшении удержания/репутации, рост paid без контроля LTV/CAC. citeturn2search7turn9search2turn24view1  

D) **Артефакты.**
Growth model map; KPI tree; experiment backlog; readouts; decision log; instrumentation spec; cohort dashboards; “growth loop scorecards”; playbooks (activation, referral, expansion). citeturn2search2turn2search15turn2search4  

E) **Инструменты/стек.**
Product analytics, experimentation, feature flags, BI/warehouse, CRM/MA (для PQL/SQL), paid platforms, attribution/incrementality, survey tools. citeturn9search2turn4search2turn2search4  

F) **Best practices 2024–2026.**
1) Сдвиг фокуса “от воронки к лупам” и количественная модель лупов для приоритизации. citeturn2search5turn2search2  
2) Центральная метрика ценности (North Star) как leading indicator и связка customer‑value↔growth. citeturn2search1turn2search4  
3) Эксперименты как инструмент причинности (incrementality), особенно на paid и крупных изменениях. citeturn9search2turn26search11  
4) Privacy‑устойчивость измерений: first‑party/server‑side сигналы (Consent Mode v2, Enhanced Conversions, CAPI). citeturn9search0turn9search1turn7search12  
5) “Guardrail metrics” закреплены в дизайне эксперимента (качество/спам/brand). citeturn24view1turn12search0  
6) Пост‑экспериментная стандартизация: артефакты, мониторинг, “дрейф” эффектов. citeturn5search1turn2search15  
7) Граница Growth↔Product оформлена через единый discovery/delivery цикл в кросс‑функциональной команде. citeturn13search1turn2search18  

G) **Ошибки.**
- “Эксперименты ради экспериментов”: нет модели роста и связи с ценностью. citeturn2search4turn2search2  
- Слишком сильная зависимость от last‑click атрибуции. citeturn9search2  
- Игнорирование контент/SEO‑политик (риски спама/санкций). citeturn24view1turn24view0  
- Оптимизация acquisition при провале activation/retention. citeturn2search4turn14search0  

H) **Взаимодействие (RACI).**
- **Выбор North Star:** A=CPO (обычно), R=Growth+Product Analytics, C=CMO/CRO, I=CEO. citeturn2search4turn2search18  
- **Эксперименты на paid:** A=CMO, R=Growth, C=Data/RevOps, I=CFO. citeturn9search2turn4search2  
- **Изменения onboarding/activation:** A=CPO, R=Growth+Product team, C=CS, I=CMO/CRO. citeturn13search1turn14search0  

## Продукт

**Роль: CPO**

A) **За что отвечает.** CPO отвечает за продуктовую стратегию (какие проблемы решаем и почему), за модель discovery/delivery, и за метрики ценности/результатов — так, чтобы команды решали “правильные проблемы” и создавали ценность, влияющую на устойчивые бизнес‑результаты. citeturn2search6turn2search18turn2search4

B) **Топ типовых задач и решений.**
1) Сформировать/обновить product vision и product strategy, связать её с бизнес‑целями и ограничениями. citeturn13search4turn2search6  
2) Определить/пересмотреть North Star Metric и дерево метрик (leading/lagging). citeturn2search4turn2search7  
3) Организовать discovery как непрерывный процесс (исследования, тесты, opportunity mapping). citeturn2search18turn2search13turn2search9  
4) Установить единый цикл discovery/delivery в кросс‑функциональных командах. citeturn13search1turn2search0  
5) Решить “портфельный” вопрос: какие bets делаем, какие закрываем, сколько инвестируем в core vs new. citeturn2search6turn13search0  
6) Утвердить правила приоритизации (outcomes‑first), включая “не делать” и deprecation. citeturn2search6turn2search18  
7) Управлять операционной моделью продукта: роли, полномочия, взаимодействие с дизайном/инжинирингом. citeturn2search3turn13search5  
8) Интегрировать комплаенс и AI‑risk в продуктовые решения (особенно при GenAI‑фичах). citeturn5search3turn5search2turn25view2  
9) Проводить “качество доставки”: связь product outcomes с инженерными метриками, предсказуемость релизов. citeturn5search1turn5search12  
10) Развивать команду PM/Design и практики (коучинг, стандарты артефактов). citeturn13search5turn2search18  

C) **KPI/метрики.**
- **Leading:** North Star metric, activation/time‑to‑value, adoption ключевых workflows, доля решений с evidence (discovery confidence), leading indicators retention/expansion. citeturn2search4turn2search18turn2search7  
- **Lagging:** retention, churn, NRR, revenue per account, win‑rate ключевых сегментов, customer satisfaction/loyalty (NPS — осторожно). citeturn14search4turn14search0turn10search7  
- **Не считать успехом:** output‑метрики (количество фич/релизов) без доказанного outcome, vanity engagement без связи с ценностью, metric gaming. citeturn2search7turn2search4turn2search18  

D) **Артефакты/документы.**
Product vision narrative; product strategy / bets; North Star workshop outputs; discovery repository (инсайты, записи интервью); opportunity/solution mapping; PRD / product briefs; roadmap (outcome‑based); decision log; deprecation plan. citeturn13search4turn2search18turn2search10turn2search9  

E) **Инструменты/стек.**
Product analytics; user research tooling; experimentation; roadmap/portfolio tools; feedback systems; BI/warehouse; feature flagging; documentation/knowledge base. citeturn2search18turn2search13turn9search2  

F) **Best practices 2024–2026.**
1) **Операционная модель продукта**: единые принципы discovery (value/usable/feasible/viable) + empowerment кросс‑функциональных команд. citeturn2search18turn2search3  
2) **Одна команда = discovery + delivery**, а не “отдельные discovery‑группы”, иначе теряется ответственность за результат. citeturn13search1turn2search0  
3) **North Star как связка customer value ↔ business outcomes**, плюс input‑метрики под команды/сегменты. citeturn2search4turn2search1  
4) **Continuous discovery как системная привычка** (регулярные customer conversations, структурирование возможностей). citeturn2search9turn2search13  
5) **AI‑и комплаенс‑by‑design**: учитывать требования EU AI Act и практики NIST по управлению AI‑рисками там, где продукт использует/встраивает GenAI. citeturn5search3turn5search2  
6) **Связка outcomes↔engineering performance:** CPO не “меряет DORA”, но использует её, чтобы понимать ограничение delivery‑системы. citeturn5search1turn5search12  
7) **Портфельные решения документируются**: стратегия отвечает на вопрос “какие проблемы решаем” и “почему”, а не “какие фичи делаем”. citeturn2search6turn13search0  

G) **Ошибки.**
- Roadmap как список фич без outcome‑гипотез. citeturn2search6turn2search18  
- Метрика North Star = выручка “в лоб” (часто лагging), без прокси customer value. citeturn2search4turn2search7  
- Discovery без связи с delivery (handoff, потеря learning). citeturn13search1turn2search0  
- Игнор комплаенса/безопасности в AI‑фичах до “перед релизом”. citeturn5search3turn25view3  

H) **Взаимодействие (RACI).**
- **Product strategy:** A=CPO, R=Group PMs, C=CEO/CFO/CRO/CTO, I=CMO/COO. citeturn2search6turn10search2  
- **North Star:** A=CPO, R=Product Analytics+PM, C=CMO/Growth/CRO/CS, I=CEO. citeturn2search4turn14search0  
- **AI‑risk governance в продукте:** A=CISO (policy), R=CPO+CTO (implementation), C=Legal/Head of Data, I=CEO/CFO. citeturn25view3turn5search2turn5search3  

## SEO: техника, индексация, качество контента

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["growth loop diagram product growth","rel=canonical vs 301 redirect SEO diagram","Google Search Console crawl stats report screenshot","IndexNow protocol diagram"],"num_per_query":1}

**Роль: SEO Redirect/Canonical Expert**

A) **За что отвечает.** Владелец каноникализации и редирект‑логики: устраняет дубли, управляет миграциями/переездами, обеспечивает корректную передачу сигналов (canonical target), минимизируя потери трафика/индексации. citeturn22view0turn22view1turn23view0turn1search0

B) **Топ типовых задач и решений.**
1) Проектировать canonical strategy: какие URL должны быть “представителями” контента, где допускаются вариации. citeturn22view0turn0search7  
2) Настраивать rel=canonical (HTML и при необходимости HTTP header) и проверять конфликты/ошибки. citeturn22view0  
3) Устанавливать правила: когда canonical vs когда redirect (Google и Bing подчёркивают, что canonical не заменяет корректный редирект при переезде). citeturn22view0turn1search0  
4) Проектировать redirect policy (301/302/308 и др.), избегать цепочек/петель. citeturn22view1turn23view0  
5) Делать migration runbook: mapping old→new, порядок работ, мониторинг, rollback. citeturn23view0  
6) Управлять параметрами URL (tracking параметры, session IDs) через canonical/переадресацию/внутренние ссылки. citeturn22view0turn22view1  
7) Нормализовать внутреннюю линковку на canonical URL (важный signal). citeturn22view0  
8) Координировать hreflang‑кластеры и canonical “внутри языка”. citeturn22view0  
9) Проверять эффект через Search Console (indexing/canonical chosen by Google), лог‑анализ и выборочные инспекции URL. citeturn6search0turn6search7  
10) Обучать разработку/контент‑команду анти‑паттернам: “redirect на home”, “canonical на всё подряд”, “JS меняет canonical”. citeturn23view0turn22view0  

C) **KPI/метрики.**
- **Leading:** доля URL с “правильным” canonical (по данным инспекции/отчётов), количество redirect chains, доля параметрического мусора, время обработки миграции (в неделях). citeturn22view0turn23view0turn6search0  
- **Lagging:** стабильность органического трафика/видимости после миграций, восстановление индекса, снижение дублей в индексе. citeturn23view0turn6search7  
- **Не считать успехом:** “всё 301‑м на главную”, “noindex вместо canonical”, “canonical без переезда при фактическом переносе”. citeturn23view0turn22view0  

D) **Артефакты.**
Redirect map (таблица соответствий); canonical rules/spec; migration checklist; regression test suite (URL samples); monitoring dashboard; post‑mortem. citeturn23view0turn22view0  

E) **Инструменты/стек.**
Лог‑анализ, crawler/сканеры, Search Console URL Inspection + API (при необходимости), правила на уровне CDN/edge/server, QA‑инструменты, мониторинг 4xx/5xx. citeturn6search0turn6search4turn23view0  

F) **Best practices 2024–2026.**
1) Использовать **stacked signals** canonicalization (canonical + internal links + sitemap), понимая, что это рекомендации, а выбор canonical остаётся за поисковиком. citeturn22view0turn21view0  
2) Для “удаления дубля” — **server‑side 3xx** даёт самый быстрый эффект; Google отмечает различия по времени распознавания методов редиректа. citeturn22view0turn22view1  
3) **Сокращать redirect chains** (в migration guidance Google рекомендует избегать цепочек, держать их короткими). citeturn23view0  
4) В миграциях “не всё сразу”: менять домен/CMС/дизайн поэтапно (практика из официального migration guidance). citeturn23view0  
5) Не бояться “потери PageRank из‑за 301/302”: Google прямо указывает, что server‑side redirects не приводят к потере PageRank. citeturn23view0  
6) Canonical **в head**, абсолютные URL; JS не должен “ломать” canonical сигнал. citeturn22view0  
7) Учитывать Bing‑рекомендации: canonical не должен подменять редирект при переезде. citeturn1search0  

G) **Ошибки.**
- Canonical на нерелевантную страницу (или один canonical на множество неэквивалентных страниц). citeturn22view0turn1search3  
- Redirect‑петли/цепочки, массовые soft‑404 через редирект на нерелевантную цель. citeturn23view0  
- Попытка решать canonicalization через `noindex` (Google не рекомендует “noindex ради каноникализации”). citeturn22view0  
- Переезд + блокировки robots/noindex забыли снять. citeturn23view0turn1search6  

H) **Взаимодействие (RACI).**
- **Redirect/canonical политика:** A=SEO Redirect/Canonical Expert, R=Web/Platform Eng, C=CTO, I=CMO/CPO. citeturn23view0turn22view0  
- **Site move:** A=CTO (delivery), R=SEO+Eng, C=CMO (коммуникации/кампании), I=COO/CRO. citeturn23view0  

**Роль: SEO Indexing & Crawl Budget Expert**

A) **За что отвечает.** Управляет тем, как бот обнаруживает/краулит сайт и как страницы попадают в индекс: sitemaps, robots, crawl stats, приоритизация важных URL; на больших сайтах — оптимизация crawl budget. citeturn22view2turn21view0turn6search1turn6search7turn1search1

B) **Топ типовых задач и решений.**
1) Оценить, нужен ли вообще crawl budget management (Google: только для очень больших/часто обновляемых сайтов). citeturn22view2turn0search1  
2) Настроить и поддерживать sitemap‑стратегию (разбиение, индекс‑файлы, coverage по разделам). citeturn6search2turn21view0  
3) Ввести дисциплину `<lastmod>`: использовать только если он точный и отражает существенные изменения. citeturn21view1turn21view0  
4) Управлять robots.txt и robots meta/X‑Robots‑Tag (разделять crawl‑контроль и index‑контроль). citeturn1search6turn1search14turn1search2  
5) Настроить мониторинг Crawl Stats и диагностику проблем сервера (латентность/ошибки). citeturn6search1turn6search14  
6) Использовать Page indexing report и URL Inspection для triage причин “не в индексе”. citeturn6search7turn6search0  
7) Лог‑анализ ботов: распределение по хостам, статусы, waste (параметры, бесконечные фильтры). citeturn22view2turn6search1  
8) Для быстро меняющегося контента — рассмотреть push‑механизмы/протоколы (IndexNow у поддерживающих поисковиков). citeturn1search1turn1search5  
9) Совместно с Eng устранить “crawler traps”, дубли, soft‑404, неправильные status codes. citeturn23view0turn6search7  
10) При изменениях документации/политик — оперативно обновлять internal SOP (Google публикует ленту doc updates; в Feb 2026 уточнялись file size limits). citeturn11view0  

C) **KPI/метрики.**
- **Leading:** crawl requests/day, avg response time, доля 5xx/4xx для бота, распределение crawl по приоритетным директориям, time‑to‑discover/time‑to‑index, waste ratio (crawl на низкоценные URL). citeturn6search1turn22view2turn6search7  
- **Lagging:** рост числа валидных indexed URLs (по Page indexing), стабильность органического трафика на ключевые кластеры, снижение “discovered/crawled currently not indexed”. citeturn6search7turn0search14  
- **Не считать успехом:** рост crawl‑объёма сам по себе, индексация “всего подряд”, блокировка robots как “security”. citeturn1search6turn22view2  

D) **Артефакты.**
Crawl/index dashboard; sitemap architecture doc; robots policy; log audit report; backlog тех‑исправлений; “indexing playbook” (как заводим новые разделы). citeturn6search1turn21view0turn6search7  

E) **Инструменты/стек.**
Search Console (Crawl Stats, Page indexing, URL Inspection), Search Console API, server logs, edge/CDN, monitoring/APM, sitemap generators, IndexNow endpoints (если применимо). citeturn6search1turn6search4turn1search5turn21view0  

F) **Best practices 2024–2026.**
1) Следовать принципу Google: если сайт не “очень большой и частый”, достаточно держать sitemap актуальным и мониторить index coverage. citeturn22view2  
2) Делать sitemaps “каноникальными”: включать URL, которые вы хотите видеть в выдаче; понимать, что sitemap — “hint”, не гарантия. citeturn21view0  
3) Использовать `<lastmod>` только при доказуемой точности; иначе он теряет ценность. citeturn21view1turn21view0  
4) Разделять robots.txt (crawl) и noindex (index): robots.txt не убирает страницу из индекса по замыслу Google. citeturn1search6turn1search14  
5) Для диагностики — Crawl Stats report как источник проблем сервера/доступности при обходе. citeturn6search1  
6) Использовать push‑нотификацию (IndexNow) там, где это реально сокращает discovery‑лаг и поддерживается движками. citeturn1search1turn1search5  
7) Следить за doc‑updates: Google публично фиксирует изменения документации (например, Feb 2026 — file size limits). citeturn11view0  

G) **Ошибки.**
- Считать robots.txt способом скрыть контент (security by obscurity). citeturn1search6  
- Sitemaps с “мусорными” URL и фальшивым lastmod. citeturn21view1turn21view0  
- Бороться с индексацией без логов/без Crawl Stats (стреляют “вслепую”). citeturn6search1  
- Резко увеличивать параметрические URL (crawl traps) без каноникализации/ограничений. citeturn22view0turn22view2  

H) **Взаимодействие (RACI).**
- **Robots/sitemaps:** A=SEO Indexing Expert, R=Platform/Eng, C=CTO/CISO (если затрагивает доступ), I=CPO/CMO. citeturn1search6turn21view0turn25view3  
- **IndexNow:** A=SEO Indexing Expert, R=Eng (интеграция), C=Head of Data (логирование), I=CMO/Growth. citeturn1search5turn4search2  

**Роль: SEO Content Quality Expert**

A) **За что отвечает.** За систему качества контента и соответствие поисковым политикам: снижает риск санкций/manual actions, строит “people‑first” контент‑стратегию, управляет AI‑контентом, и обеспечивает воспроизводимую редакционную/QA‑практику. citeturn12search1turn12search4turn24view1turn20view0

B) **Топ типовых задач и решений.**
1) Сформировать внутренние Search Essentials‑совместимые принципы (technical requirements + spam policies). citeturn12search0turn12search4  
2) Сегментировать контент‑пул: keep/update/merge/remove (особенно после апдейтов). citeturn24view1turn12search1  
3) Настроить process контроля AI‑контента: что допустимо, какие проверки обязательны, где запрещено масштабирование. citeturn24view1turn12search5  
4) Управлять E‑E‑A‑T/YMYL рисками (повышенные стандарты качества для YMYL). citeturn20view1turn20view2turn12search5  
5) Контролировать third‑party контент и размещения (site reputation abuse риск). citeturn24view0turn24view1  
6) Ввести контент‑QA чек‑листы (источники, авторство, факт‑чекинг, UX). citeturn12search1turn20view2  
7) Настроить мониторинг “качества в органике” (падения, ручные меры, индикаторы спама). citeturn24view0turn6search7  
8) Проводить пост‑апдейтные разборы: какие типы страниц просели/выросли и почему. citeturn24view1turn26search1  
9) Совместно с CMO — балансировать контент‑объём и бренд‑доверие (особенно при AI Overviews/изменениях SERP). citeturn6news39turn24view1  
10) Обучать редакторов/PM/SEO тому, что “политика важнее трюков” (anti‑spam posture). citeturn12search4turn24view1  

C) **KPI/метрики.**
- **Leading:** доля страниц, прошедших QA; coverage экспертных атрибутов (авторы/источники/обновления); уровень “тонкого/дублированного” контента; доля страниц с высокой удовлетворённостью. citeturn12search1turn20view2  
- **Lagging:** устойчивость органического трафика после core/spam updates, отсутствие manual actions, рост видимости по информационным кластерам. citeturn24view1turn24view0  
- **Не считать успехом:** “AI‑контент как фабрика объёма”, паразитирование на доменных сигналах, “перелив трафика” через third‑party секции. citeturn24view1turn24view0turn6news39  

D) **Артефакты.**
Content quality guidelines; AI policy; YMYL playbook; audit reports; контент‑матрица решений; редакционный календарь; templates (brief, outline, fact sheet); post‑update incident review. citeturn12search1turn20view0turn24view1  

E) **Инструменты/стек.**
Content intelligence, SERP monitoring, GSC, QA‑workflow, fact‑checking services, редакционные системы, structured data testing (если нужно), эксперименты на контент‑группах. citeturn6search7turn11view0turn9search2  

F) **Best practices 2024–2026.**
1) Опираться на Search Essentials и spam policies как “конституцию” контента. citeturn12search0turn12search4  
2) Учитывать March 2024 изменения: crackdown на scaled content abuse, site reputation abuse; AI/automation допустимы, если цель — не манипулирование ранжированием. citeturn24view1turn12search5  
3) После Nov 2024 уточнения: third‑party контент может нарушать policy независимо от “первичного участия”; важно governance и намерение (abuse ranking signals). citeturn24view0turn0news39  
4) Для YMYL — повышать стандарты доверия: QRG подчёркивает более строгие требования к YMYL и важность trust/репутации. citeturn20view1turn20view2  
5) Регулярно пересматривать внутренние правила под обновления QRG (change log фиксирует пересмотры YMYL и выравнивание с web spam policies в 2025). citeturn20view0  
6) Делать “контент‑сигналы” измеримыми: обновления, источники, качество основного контента, отсутствие обмана/вреда. citeturn20view1turn12search1  
7) Учитывать изменения выдачи из‑за AI‑фич: требования к бренду/дистрибуции растут, а выдача может перераспределять вниманием (AI Overviews — предмет антимонопольных жалоб издателей). citeturn6news39turn26news40  

G) **Ошибки.**
- “Секции‑паразиты”/white‑label контент, который не соответствует основному назначению сайта. citeturn24view0turn24view1  
- Масштабирование “почти дублей” под SEO (scaled content abuse). citeturn24view1  
- Оставлять “вредный/обманный” контент, рассчитывая на бренд‑авторитет домена (QRG отдельно предупреждает про вред даже на “официальных” сайтах). citeturn20view1turn20view2  

H) **Взаимодействие (RACI).**
- **Content policy / AI policy:** A=SEO Content Quality Expert + CMO (совместно), R=Editor/Content leads, C=CISO/Legal, I=CPO/CRO. citeturn24view1turn25view3turn5search3  
- **Реакция на update/penalty:** A=SEO Quality Expert, R=SEO+Content+Eng (если тех‑часть), C=CMO, I=CEO. citeturn24view0turn6search7  

**Роль: Growth/Traffic Strategy Expert (SEO + paid + partnerships mix)**

A) **За что отвечает.** За портфель acquisition‑каналов и их совместную экономику: объединяет SEO/paid/партнёрки в одну систему, где успех определяется **incremental revenue** и устойчивостью к изменениям приватности/выдачи. citeturn9search2turn7search12turn24view1turn6news40

B) **Топ типовых задач и решений.**
1) Собрать channel portfolio и “правила инвестиций” (микс, минимальные тест‑бюджеты, stop‑loss). citeturn3search9turn26search3  
2) Дизайн экспериментов на каналах (geo holdouts, platform lift, SEO‑интервенции) и readout. citeturn9search2turn26search11  
3) Устойчивое измерение: Consent Mode v2, Enhanced Conversions, Meta CAPI, Apple AdAttributionKit (для app‑контекста). citeturn9search0turn9search1turn7search12turn7search5  
4) Управление “обменом сигналами” между каналами (brand ↔ search demand ↔ retargeting) при ограничениях cookies. citeturn7search13turn7search0turn9search2  
5) Продуктовые/лендинговые оптимизации для конверсий и ценности, а не только для кликов. citeturn2search4turn9search2  
6) Партнёрский growth: совместные офферы, co‑marketing, marketplace размещения — но с контролем качества/репутации. citeturn24view0turn3search5  
7) SEO‑риски (spam policies) рассматриваются как риск воронки/выручки. citeturn24view1turn12search0  
8) Управление поисковой выдачей в эпоху AI‑интерфейсов (AI Overviews/Web Guide): переработка контента/структуры “под видимость”. citeturn6news39turn6news40  
9) Построение blended CAC и правил приписывания затрат/дохода по каналам (finance alignment). citeturn10search6turn26search3  
10) Общая карта “что масштабируем, что защищаем”: brand, SEO‑активы, paid‑плейбуки. citeturn3search1turn24view1  

C) **KPI/метрики.**
- **Leading:** tested budget share (доля бюджета в экспериментах), lift‑метрики, conversion rate по ключевым путям, доля first‑party match (enhanced/capi), SEO: индексируемость ключевых страниц. citeturn9search2turn9search1turn6search7  
- **Lagging:** incremental revenue, blended CAC, CAC payback, NRR (если PLG/подписка), pipeline contribution. citeturn4search15turn14search4turn3search12  
- **Не считать успехом:** рост ROAS/CPA по платформе без lift, рост органики на “паразитных” разделах с риском санкций. citeturn9search2turn24view0turn24view1  

D) **Артефакты.**
Channel portfolio doc; experimentation plan; measurement spec; partner playbook; landing page canon; KPI dashboard; бюджетные сценарии. citeturn9search0turn26search3turn4search2  

E) **Инструменты/стек.**
Attribution/MMM + incrementality; ad платформы; SEO stack; CDP/warehouse; CMP/consent; server‑side tracking; partner CRM. citeturn9search2turn9search0turn7search12  

F) **Best practices 2024–2026.**
1) “Lift‑first”: верифицировать причинность (incrementality) и только потом масштабировать spend. citeturn9search2turn26search11  
2) Measurement под privacy: Consent Mode v2 (EEA), Enhanced Conversions, CAPI (pixel+server redundancy). citeturn9search0turn9search1turn7search12  
3) Учитывать стратегические изменения вокруг third‑party cookies (Google в 2025 отказался от standalone prompt; Privacy Sandbox статус меняется). citeturn7search13turn7search0turn7news40  
4) В app‑экосистеме — опираться на privacy‑preserving атрибуцию Apple (AdAttributionKit) и принимать ограничения signal loss. citeturn7search5turn7search2  
5) Учитывать SEO‑политику anti‑spam как ограничение (особенно site reputation abuse). citeturn24view0turn24view1  
6) Держать единые определения метрик и handoffs через RevOps. citeturn4search2  
7) Перепроектировать контент/лендинги под AI‑слои выдачи (AI Overviews/Web Guide) и риски издателей. citeturn6news39turn6news40  

G) **Ошибки.**
- Канальное “локальное” оптимизирование без единой экономики и без lift. citeturn9search2  
- Игнорирование consent/комплаенса в измерениях. citeturn9search0turn5search3  
- Партнёрки/affiliate‑контент без контроля “site reputation abuse” рисков. citeturn24view0turn0news39  

H) **Взаимодействие (RACI).**
- **Measurement:** A=CMO, R=Traffic Strategy+Analytics, C=Head of Data/CISO, I=CFO. citeturn9search0turn14search2turn25view3  
- **Channel portfolio:** A=CMO+CRO, R=Traffic Strategy, C=RevOps, I=CEO. citeturn4search2turn13search9  

## Консилиум C-level и смежные хеды

**Роль: CRO (Revenue)**

A) **За что отвечает.** CRO отвечает за рост выручки по всему revenue cycle, обычно синхронизируя Sales, Marketing и Customer Success в единый revenue‑движок. citeturn13search3turn4search2

B) **Топ типовых задач и решений.**
1) Определить ICP/сегментацию и стратегию роста выручки по сегментам. citeturn13search3turn4search2  
2) Установить правила pipeline governance: стадии, exit criteria, качество данных. citeturn4search2turn3search12  
3) Управлять прогнозированием (forecast) и ритмом (weekly/monthly). citeturn4search2turn13search16  
4) Определить coverage model (pipeline coverage), квоты, territories. citeturn26search6turn26search2  
5) Связать компенсации с правильными outcome (в т.ч. NRR, net retention). citeturn8search11turn14search4  
6) Согласовать Marketing↔Sales handoffs, SLA по лид‑обработке. citeturn4search2  
7) Принять решения по pricing/packaging комитету и частоте изменений (вместе с CPO/CFO). citeturn18view0turn18view1  
8) Выстроить expansion motion и вместе с CS владеть NRR/GRR. citeturn14search4turn14search0  
9) Запустить/эволюционировать RevOps как систему (данные/процессы/технологии). citeturn4search2  
10) Управлять рисками “перегиба” в growth‑целях (продажи любой ценой → churn/репутация). citeturn14search8turn14search4  

C) **KPI/метрики.**
- **Leading:** win‑rate, sales cycle, pipeline coverage, conversion rates по стадиям, SLA lead response. citeturn26search6turn4search2  
- **Lagging:** ARR growth, NRR/GRR, gross retention, churn, forecast accuracy. citeturn14search4turn14search0  
- **Не считать успехом:** рост bookings при падающем GRR (потеря “здоровья базы”). citeturn14search8  

D) **Артефакты.**
Revenue plan; segmentation/ICP; pipeline definitions; comp plan principles; forecast pack; QBR templates; GTM dashboards. citeturn4search2turn13search3  

E) **Инструменты/стек.**
CRM, CPQ/billing, revenue intelligence, BI, enablement, forecasting, RevOps toolchain. citeturn4search2turn14search4  

F) **Best practices 2024–2026.**
1) Управлять revenue как end‑to‑end системой, а не функциями по отдельности (RevOps модель). citeturn4search2  
2) Сдвиг мотивации в сторону качества сделок и retention (компенсации, завязанные на net retention). citeturn8search11turn14search4  
3) Pricing/packaging обновлять регулярно и через комитет/процесс (в 2024 наблюдается частая корректировка pricing). citeturn18view0turn18view1  
4) Поддерживать единые определения метрик и данных, иначе forecast и ROI‑дискуссии деградируют. citeturn4search2turn3search12  
5) Align с маркетинговыми best practices измерения причинности (incrementality) для аллокации бюджета. citeturn9search2turn26search11  
6) Учитывать рыночные бенчмарки GTM как sanity check (ICONIQ‑разборы/бенчмарки). citeturn26search6turn26search2  
7) Фиксировать “анти‑ресурсы”: что не делаем (сегменты/каналы) ради эффективности. citeturn10search2  

G) **Ошибки.**
- “Его величество pipeline” без retention‑здоровья. citeturn14search8  
- Разные определения одной метрики в разных системах. citeturn4search2  

H) **Взаимодействие.**
- С CFO — unit economics/Rule of X. citeturn10search2  
- С CPO — value metric/pricing boundaries. citeturn18view1  

**Роль: CTO**

A) **За что отвечает.** CTO отвечает за технологическую стратегию и способность компании надежно и предсказуемо поставлять изменения, управляя архитектурой, качеством, безопасностью и скоростью разработки. citeturn5search12turn5search1turn25view3  

B) **Топ типовых задач и решений.**
1) Определить технологическую стратегию и архитектурные принципы. citeturn5search12  
2) Управлять delivery system через метрики DORA и улучшения. citeturn5search1turn5search12  
3) Обеспечить reliability (SLO/SLA) и incident management. citeturn5search1turn25view3  
4) Построить secure SDLC и контроль поставщиков/инфраструктуры. citeturn25view3turn10search1  
5) Build vs buy решения (platform, data, security, martech). citeturn4search2turn10search1  
6) Поддержать SEO/маркетинг‑требования (redirect/migration, consent). citeturn23view0turn9search0  
7) Обеспечить наблюдаемость и диагностику (APM/logs). citeturn6search1turn5search1  
8) Управлять внедрением AI‑инструментов в разработке с учётом рисков (по DORA/исследованиям). citeturn5search12turn5search4  
9) Организация инженерной структуры и рост компетенций. citeturn5search12  
10) Согласование технологических рисков с CISO и комплаенса с COO/CFO. citeturn25view3turn10search6  

C) **KPI/метрики.**
- **Leading:** deployment frequency, lead time for changes, change fail rate, time to restore. citeturn5search1  
- **Lagging:** availability, incident severity, cost of downtime, скорость вывода value‑фич. citeturn5search1turn25view3  
- **Не считать успехом:** ускорение поставки при росте instability (change fail + MTTR). citeturn5search1  

D) **Артефакты.**
Tech strategy; architecture decision records; platform roadmap; SLOs; security requirements; engineering scorecards. citeturn5search1turn10search1  

E) **Инструменты/стек.**
CI/CD, observability, cloud, security tooling, feature flags, data platform. citeturn5search1turn10search1  

F) **Best practices 2024–2026.**
1) Использовать DORA‑метрики как стандарт измерения delivery performance. citeturn5search12turn5search1  
2) Баланс throughput/stability, а не “скорость любой ценой”. citeturn5search1  
3) Встраивать security governance (CSF 2.0, ISO 27001) в инженерный контур. citeturn25view3turn10search1  
4) Учитывать, что AI‑tooling может не автоматически улучшать delivery (по обзорам DORA‑исследований — тема обсуждаемая). citeturn5search4turn5search12  
5) Поддерживать комплаенс‑измерения (consent/first‑party) как “требование платформы”. citeturn9search0turn9search1  
6) Делать миграции/редиректы “по учебнику” Search Central, чтобы не терять сигнал/трафик. citeturn23view0  
7) Согласовывать AI‑фичи с AI Act/NIST AI RMF практиками. citeturn5search3turn5search2  

G) **Ошибки.**
- Непрозрачность изменений и отсутствие измерений (нет DORA). citeturn5search1  
- Перенос рисков на прод (скорость > стабильность). citeturn5search1  

H) **Взаимодействие.**
- CTO↔CPO: delivery capacity/tech feasibility. citeturn2search18turn5search1  
- CTO↔CISO: framework controls и риски. citeturn25view3turn10search1  

**Роль: COO**

A) **За что отвечает.** COO переводит стратегию в ежедневное исполнение: отвечает за эффективность операций, масштабирование процессов и организационную “пропускную способность”. citeturn14search15turn14search7  

B) **Топ типовых задач и решений.**
1) Спроектировать operating cadence (ритмы управления и исполнения). citeturn14search15  
2) Утвердить операционные KPI и dashboards по критическим процессам. citeturn14search15turn14search7  
3) Масштабировать процессы от PMF к Scale: поддержка качества и скорости. citeturn14search15  
4) Оргдизайн и ресурсное распределение (критические инициативы). citeturn14search15  
5) Управлять cross‑functional инициативами (например, миграции, комплаенс программы). citeturn23view0turn25view3  
6) Следить за unit economics в операционном разрезе. citeturn10search6turn10search2  
7) Управлять SLA внутренних сервисов (support, provisioning, onboarding). citeturn14search0  
8) Risk management совместно с CISO/Legal. citeturn25view3turn5search3  
9) Построить систему “контроля исполнения” OKR/результатов. citeturn14search15  
10) Устранение узких мест delivery/ops (совместно с CTO). citeturn5search1turn14search15  

C) **KPI/метрики.**
- **Leading:** cycle time процессов, SLA, throughput операционных команд. citeturn14search15  
- **Lagging:** cost to serve, margin impact, NRR (через качество сервиса). citeturn14search4turn10search6  
- **Не считать успехом:** “экономия” через деградацию качества/retention. citeturn14search8  

D) **Артефакты.**
Operating model; process maps; quarterly ops plan; KPI dashboards; risk register; postmortems. citeturn14search15turn25view3  

E) **Инструменты/стек.**
BPM/операционные системы, BI, project/program management, CRM/Support tooling. citeturn14search15turn14search0  

F) **Best practices 2024–2026.**
1) Управлять вниманием и временем COO как ресурсом (McKinsey формулирует COO agenda вокруг “как тратить время и взаимодействовать”). citeturn14search15  
2) Встраивать risk governance (CSF 2.0 Govern) в операционные решения. citeturn25view3turn25view1  
3) Стандартизировать handoffs между функциями (RevOps/Service ops). citeturn4search2  
4) Оперировать фактами (единые метрики/данные) — иначе операционное управление распадается. citeturn14search2turn4search2  
5) Масштабировать процессы при сохранении качества клиента (связь с retention). citeturn14search0turn14search4  
6) Учитывать комплаенс (AI Act) в операционных функциях обучения/использования ИИ. citeturn5search3turn5news39  
7) Прозрачные postmortems для крупных сбоев/миграций. citeturn23view0turn5search1  

G) **Ошибки.**
- Ритмы без данных и owner’ов. citeturn14search2turn4search2  
- “Оптимизация локально”, а не end‑to‑end. citeturn4search2  

H) **Взаимодействие.**
COO — “интегратор” C‑уровня: синхронизирует планы CMO/CPO/CRO/CTO с финансами и рисками. citeturn14search15turn4search2  

**Роль: CFO**

A) **За что отвечает.** CFO — владелец финансовой модели, капитала и экономической дисциплины: обеспечивает бюджетирование, прогнозирование и оценку эффективности роста (growth vs profitability). citeturn10search2turn10search6  

B) **Топ типовых задач и решений.**
1) Выстроить KPI “здоровья бизнеса” (cloud/saas top metrics) и board reporting. citeturn10search6  
2) Управлять бюджетом и сценариями (эффективность маркетинга/продаж). citeturn17view0turn10search2  
3) Оценивать рост через Rule of 40/X и их вариации (рост важнее, но взвешенно). citeturn10search2turn10search10  
4) Контролировать unit economics: CAC payback, gross margin, retention. citeturn4search15turn10search6turn14search4  
5) Совместно с CRO/CMO — аллокация бюджета на основе причинного эффекта (incrementality). citeturn9search2turn3search12  
6) Совместно с CPO — pricing/packaging guardrails и процесс. citeturn18view1turn18view0  
7) Управление cash/burn и инвестициями в AI/MarTech/Platform. citeturn4search0turn3search1  
8) Policy на “какие метрики можно оптимизировать” (анти‑vanity). citeturn2search7turn9search2  
9) Риск‑менеджмент (в т.ч. комплаенс затрат) совместно с CISO/Legal. citeturn5search3turn10search0  
10) Поддержка M&A/финансирования (если применимо). citeturn10search6  

C) **KPI/метрики.**
- **Leading:** pipeline efficiency, CAC payback, burn multiple (как производная), pricing win‑rate. citeturn10search6turn4search15  
- **Lagging:** growth rate, margin, Rule of X/40, cash runway. citeturn10search2turn10search10  
- **Не считать успехом:** “бумажный” ROAS/атрибуция без lift, рост revenue при падающем GRR. citeturn9search2turn14search8  

D) **Артефакты.**
Финмодель; бюджет; KPI pack; сценарии; pricing business case; board deck. citeturn10search2turn18view1  

E) **Инструменты/стек.**
FP&A, billing/ERP, BI, data warehouse, CRM‑extracts. citeturn4search2turn10search6  

F) **Best practices 2024–2026.**
1) Использовать Rule of X как развитие Rule of 40 (рост имеет больший вес в оценке эффективности). citeturn10search2  
2) Финансировать маркетинг через причинное измерение (incrementality), а не только атрибуцию. citeturn9search2turn26search11  
3) Связать pricing изменения с процессом и данными (частые обновления pricing/packaging в 2024). citeturn18view0turn18view1  
4) Держать единые определения NRR/GRR и мониторить их как основу здоровья подписочного бизнеса. citeturn14search4turn4search15  
5) Встраивать комплаенс/безопасность в оценку инвестиций (SOC 2/ISO 27001 как рыночные требования B2B). citeturn10search0turn10search1  
6) Учитывать “AI cloud moment” и изменение экономики софта (контекст инвесторских обзоров). citeturn4search0turn3search1  
7) Делать бенчмаркинг (GTM/retention) как sanity check, но не как абсолютную цель. citeturn26search2turn14search4  

G) **Ошибки.**
- Оптимизация только P&L без понимания retention‑двигателей. citeturn14search4  
- Доверие к метрикам без data governance. citeturn14search2turn4search2  

H) **Взаимодействие.**
- CFO↔CRO: экономика revenue engine. citeturn4search2turn10search6  
- CFO↔CISO: оценка рисков/аудитов. citeturn10search0turn25view3  

**Роль: CISO**

A) **За что отвечает.** CISO отвечает за управление киберрисками и комплаенс‑готовность: политики, контрольная среда, incident response, vendor risk, и (в 2024–2026) управление рисками GenAI. citeturn25view1turn25view3turn10search1turn5search2  

B) **Топ типовых задач и решений.**
1) Выбрать рамку управления рисками (например, CSF 2.0) и целевой профиль зрелости. citeturn25view1turn25view3  
2) Построить governance (новая функция Govern в CSF 2.0) и распределение ответственности/полномочий. citeturn25view3  
3) Подготовить SOC 2/ISO 27001 readiness и поддерживать контрольную среду. citeturn10search0turn10search1  
4) Threat modeling и защита данных клиентов (privacy/security/availability). citeturn10search0turn25view1  
5) Incident response и восстановление (Respond/Recover). citeturn25view3turn5search1  
6) Supply chain risk management (в CSF 2.0 выделена категория C‑SCRM). citeturn25view3  
7) AI risk management: опираться на NIST AI RMF и GenAI Profile. citeturn5search2turn25view2  
8) Поддержать privacy‑измерения (consent mode) без утечек и нарушения регуляций. citeturn9search0turn5search3  
9) Vendor due diligence (особенно MarTech/AI vendors). citeturn10search1turn25view1  
10) Обучение персонала и security awareness (CSF Protect/Awareness). citeturn25view3turn10search1  

C) **KPI/метрики.**
- **Leading:** coverage контролей, время закрытия vuln, phishing simulation outcomes, audit findings trend. citeturn10search0turn25view3  
- **Lagging:** инциденты/severity, downtime, успешность аудитов (SOC2/ISO), потери/штрафы. citeturn10search0turn10search1  
- **Не считать успехом:** “нулевые инциденты” ценой отсутствия мониторинга/репортинга. citeturn25view3turn6search1  

D) **Артефакты.**
Security policies; CSF profiles; risk register; IR plan; vendor assessments; SOC2/ISO evidence packs; AI governance policy. citeturn25view3turn10search0turn5search2  

E) **Инструменты/стек.**
IAM, SIEM/monitoring, vuln management, GRC, secrets management, DLP, audit tooling. citeturn10search1turn25view3  

F) **Best practices 2024–2026.**
1) CSF 2.0 как основа зрелости (включая Govern). citeturn25view3turn25view1  
2) Интеграция AI‑рисков в enterprise risk (CSF 2.0 прямо связывает cybersecurity/privacy и применимость подходов к AI системам). citeturn25view2turn5search2  
3) Подготовка к регуляторным требованиям EU AI Act по фазам (вступил в силу 1 Aug 2024). citeturn5search3turn5news39  
4) SOC 2 и ISO/IEC 27001 как рыночный минимум доверия для B2B‑поставщиков. citeturn10search0turn10search1  
5) Supply chain security как отдельный слой (C‑SCRM). citeturn25view3  
6) Security support для маркетинговых измерений (consent/first‑party) без утечек данных. citeturn9search0turn9search1  
7) Связка с DORA/engineering: скорость без контроля change failure/MTTR увеличивает риск. citeturn5search1turn5search12  

G) **Ошибки.**
- “Compliance‑театр” без реального risk governance. citeturn25view3  
- Отсутствие AI‑политики при внедрении GenAI в продукт/маркетинг. citeturn5search2turn17view3  

H) **Взаимодействие.**
CISO — обязательный консультант для CPO/CMO по данным и GenAI, и co‑owner для CTO по secure SDLC. citeturn5search2turn9search0turn5search1  

**Роль: Head of RevOps**

A) **За что отвечает.** RevOps — end‑to‑end модель, объединяющая customer engagement по функциям и интегрирующая людей, процессы и технологии по всему revenue пути. citeturn4search2turn4search22  

B) **Топ типовых задач и решений.**
1) Единая таксономия funnel/pipeline/NRR и словарь метрик. citeturn4search2turn14search4  
2) Проектирование процессов handoff (Mkt→Sales→CS) и SLA. citeturn4search2  
3) Routing и scoring (lead/PQL) с контрольными точками качества. citeturn2search20turn4search2  
4) Интеграции инструментов (CRM, MA, billing, data). citeturn4search2turn14search2  
5) Data quality и governance для revenue данных. citeturn14search2turn4search2  
6) Forecasting support и pipeline hygiene. citeturn4search2turn13search16  
7) Reporting (dashboards) и business reviews. citeturn3search12turn4search2  
8) Enablement и стандарты ведения CRM “как системы записи”. citeturn4search2  
9) Эксперименты на процессе (например, новые handoffs) с измерением результата. citeturn9search2turn4search2  
10) Контроль комплаенса данных (consent, privacy signals). citeturn9search0turn14search2  

C) **KPI/метрики.**
- **Leading:** SLA, data completeness, conversion rates по стадиям, routing accuracy. citeturn4search2  
- **Lagging:** forecast accuracy, CAC/efficiency, NRR. citeturn14search4turn10search6  
- **Не считать успехом:** красивые дашборды при плохих определениях/данных. citeturn14search2turn4search2  

D) **Артефакты.**
Revenue taxonomy; process playbooks; dashboard suite; SLA docs; tooling architecture; data dictionary. citeturn4search2turn14search2  

E) **Инструменты/стек.**
CRM, MA, CS platforms, billing, warehouse/BI, routing/scoring tools, consent tooling. citeturn4search2turn9search0  

F) **Best practices 2024–2026.**
1) RevOps как end‑to‑end модель, а не “ещё один title”. citeturn4search2  
2) Единые определения pipeline/revenue, иначе теряется доверие к измерениям (проблема отмечается в B2B измерениях). citeturn3search12turn4search2  
3) Встроить privacy‑требования в data flow (consent signals). citeturn9search0turn9search4  
4) Поддерживать causal measurement (incrementality) для бюджетных решений. citeturn9search2turn26search11  
5) Связать CS метрики (NRR/GRR) с sales/marketing incentives там, где это уместно. citeturn14search4turn8search11  
6) Автоматизировать, но с governance (GenAI в RevOps процессах тоже требует контроля). citeturn25view2turn5search2  
7) Регулярные “data audits” и исправления “у источника”, а не в BI‑слое. citeturn14search2turn4search2  

G) **Ошибки.**
- “Metric soup”: десятки метрик без owner’ов и без решений, которые из них следуют. citeturn2search7turn4search2  

H) **Взаимодействие.**
RevOps — ключевой стык CMO↔CRO↔CS↔CFO. citeturn4search2turn14search4  

**Роль: Head of Data/Analytics**

A) **За что отвечает.** Владеет дисциплиной data governance (качество, безопасность, доступность) и системой метрик/аналитики, чтобы бизнес‑решения опирались на единые, корректные данные. citeturn14search2turn14search14  

B) **Топ типовых задач и решений.**
1) Построить data governance: роли, политики, стандарты. citeturn14search2  
2) Ввести “single definitions” метрик (metric layer) и data dictionary. citeturn14search14turn4search2  
3) Обеспечить privacy‑compliant измерения (consent, retention of data). citeturn9search0turn14search2  
4) Поддержка продуктовой аналитики (North Star inputs) и growth измерений (incrementality). citeturn2search4turn9search2  
5) Data quality monitoring (freshness, completeness, correctness). citeturn14search2  
6) Архитектура данных: warehouse/lakehouse, ETL/ELT, semantic models. citeturn14search2turn4search2  
7) Self‑serve аналитика для функций (CMO/CRO/CPO/CS). citeturn14search2turn3search12  
8) Поддержка AI/ML: governance и риски (AI RMF). citeturn5search2turn25view2  
9) Определить SLA аналитики (time‑to‑insight) и приоритеты data продуктов. citeturn14search14turn14search2  
10) Incident response по данным (качество/утечки) совместно с CISO/CTO. citeturn25view3turn14search2  

C) **KPI/метрики.**
- **Leading:** data quality scores, время доставки нового события/метрики, adoption BI, количество инцидентов качества данных. citeturn14search2turn14search14  
- **Lagging:** доверие к отчетности, скорость принятия решений, снижение “споров о цифрах”. citeturn14search14turn3search12  
- **Не считать успехом:** warehouse “набитый данными” без нужных метрик и без governance. citeturn14search2  

D) **Артефакты.**
Data governance charter; data catalog; metric dictionary; tracking plan; data contracts; BI dashboards; privacy policies for analytics. citeturn14search2turn9search0  

E) **Инструменты/стек.**
Warehouse, ETL/ELT, BI, catalog, observability for data, consent tooling. citeturn14search2turn9search0  

F) **Best practices 2024–2026.**
1) Основание: качество/безопасность/доступность данных как ядро data governance. citeturn14search2  
2) Единые определения метрик для RevOps и C‑уровня. citeturn4search2turn14search14  
3) Privacy‑first сбор данных (Consent Mode v2 и аналоги) как обязательный слой. citeturn9search0turn9search4  
4) Поддержка causal measurement (incrementality) как “высший стандарт” эффективности. citeturn9search2turn26search11  
5) AI risk governance (AI RMF) при использовании данных для GenAI/ML. citeturn5search2turn25view2  
6) Data observability (мониторинг “поломок” данных) как обязательная практика. citeturn14search2  
7) Договорённость о SLA доставки данных и приоритизации. citeturn14search14turn14search2  

G) **Ошибки.**
- “Отчеты вместо продукта”: BI без владельцев метрик и без тестов качества. citeturn14search2turn3search12  

H) **Взаимодействие.**
Head of Data — центральный консультант для CMO (measurement), CPO (product analytics), CRO (funnel data), CISO (privacy/security). citeturn14search2turn4search2turn9search0  

**Роль: Head of Customer Success**

A) **За что отвечает.** Владеет удержанием и ростом внутри базы (renewals/expansion), обеспечивая value realization, снижение churn и увеличение NRR/GRR. citeturn14search0turn14search4turn14search8  

B) **Топ типовых задач и решений.**
1) Сегментация клиентской базы и service tiers. citeturn14search0  
2) Построение customer health score и системы раннего предупреждения churn. citeturn14search12turn14search0  
3) Управление renewals motion и playbooks. citeturn14search0turn14search4  
4) Expansion motion (upsell/cross‑sell) совместно с CRO. citeturn14search4turn13search3  
5) QBR‑ритм и executive relationships. citeturn14search0  
6) Onboarding/adoption программы и снижение time‑to‑value. citeturn2search4turn14search0  
7) Управление support escalations и root‑cause с продуктом/инжинирингом. citeturn5search1turn14search0  
8) Voice of Customer: сбор сигналов и приоритизация проблем с CPO. citeturn2search18turn14search12  
9) Измерение лояльности/удовлетворённости (NPS как один из сигналов, но не единственный). citeturn10search7turn14search13  
10) Встраивание CS данных в RevOps и прогнозирование retention‑выручки. citeturn4search2turn14search4  

C) **KPI/метрики.**
- **Leading:** health score, продуктовая активация/использование, time‑to‑value, adoption ключевых функций. citeturn14search12turn2search4  
- **Lagging:** NRR, GRR, logo churn, expansion %, retention rate. citeturn14search0turn14search4turn14search8  
- **Не считать успехом:** высокий NRR при деградации GRR (Gainsight отмечает, что GRR лучше отражает “долгосрочное здоровье” базы, т.к. churn съедает основу expansion). citeturn14search8  

D) **Артефакты.**
CS playbooks; health score model; QBR templates; churn/renewal postmortems; adoption programs; customer education content. citeturn14search0turn14search12  

E) **Инструменты/стек.**
CS platform, CRM, support/helpdesk, product analytics, BI, customer education. citeturn14search12turn14search4  

F) **Best practices 2024–2026.**
1) Мерить удержание через NRR и GRR, понимая различия и риски. citeturn14search4turn14search8  
2) Переход от “опросных” метрик к более предиктивным outcome‑метрикам (в отрасли обсуждается уход “только NPS”). citeturn14search13turn10search7  
3) Health scoring как операционный инструмент, а не отчёт. citeturn14search12turn14search0  
4) Связка CS↔Product: VoC → discovery → delivery. citeturn2search18turn13search1  
5) QBR и value realization как стандарт для mid‑market/enterprise. citeturn14search0  
6) Стандартизированные playbooks по рискам churn и расширению. citeturn14search0turn14search12  
7) Единая revenue‑таксономия (RevOps) для корректного сведения retention‑дохода. citeturn4search2turn14search4  

G) **Ошибки.**
- CS как “поддержка”, а не драйвер value realization и retention экономики. citeturn14search0turn14search4  
- Ориентация на NPS без связки с churn/NRR. citeturn14search13turn14search4  

H) **Взаимодействие.**
Head of CS тесно связан с CRO (renewals/expansion), CPO (adoption), CMO (lifecycle), RevOps (данные). citeturn4search2turn13search3turn2search18  

## Как выглядят топ-специалисты и библиотека материалов

### Как отличить strong senior/lead в этих ролях

**Сквозные навыки топ‑уровня (по наблюдаемым практикам источников):**
- **Системное мышление и причинность:** “что меняет поведение/выручку причинно?”, а не “что коррелирует” (маркетинг: incrementality; продукт: NSM leading/lagging; инженерия: DORA stability/throughput). citeturn9search2turn2search7turn5search1  
- **Управление политиками/рисками как частью стратегии:** SEO‑спам политики, AI governance, privacy/consent, SOC2/ISO. citeturn24view1turn5search3turn10search0turn10search1turn9search0  
- **“Артефакты‑как‑интерфейсы”:** сильные лиды создают документы, по которым другие могут действовать (migration runbook, measurement spec, strategy narrative, playbooks). citeturn23view0turn13search2turn2search6turn4search2  
- **Обновляемость под “живые” изменения:** мониторинг doc updates (Google Search Central), обновления правил и процессов. citeturn11view0turn20view0  

### Как они мыслят

Чек‑лист вопросов, которые топ‑специалисты задают регулярно:
- “Какой **leading indicator** отражает customer value, и как он связан с lagging (выручкой/удержанием)?” citeturn2search4turn2search7  
- “Какая часть эффекта **инкрементальна**? Что случилось бы без вмешательства?” citeturn9search2turn26search11  
- “Какие ограничения системы: crawl budget/индексация, signal loss из‑за privacy, delivery throughput/stability?” citeturn22view2turn7search13turn5search1  
- “Какие действия повышают риск санкций/падения доверия (spam policies, site reputation abuse, AI Act)?” citeturn24view0turn24view1turn5search3  
- “Какие решения должны быть зафиксированы артефактом, чтобы команда могла действовать автономно?” citeturn2search3turn13search5  

### Как выглядит их первый месяц

**Шаблон “первого месяца” (универсально, с адаптацией под роль):**
- Неделя 1: аудит системы измерений и определений (метрики, источники данных, доверие), быстрый список рисков/дыр. citeturn14search2turn3search12turn9search0  
- Неделя 2: карту “value→метрики→рычаги” (North Star / growth loops / SEO signals) + выбрать 3–5 high‑leverage гипотез. citeturn2search4turn2search5turn22view0  
- Неделя 3: запустить 1–2 быстрых эксперимента с высокой вероятностью learning, настроив guardrails и причинное измерение (если влияние значимо). citeturn9search2turn24view1  
- Неделя 4: оформить стандарты: playbooks/SOP, владельцев метрик, weekly cadence, backlog и “stop doing list”. citeturn4search2turn13search2turn23view0  

### Примеры deliverables

Шаблоны заголовков, которые типично выдают топ‑специалисты:
- “North Star Metric & Input Metrics Tree v1.0” citeturn2search4turn2search1  
- “Growth Loops Model: Baseline, Levers, Sensitivities” citeturn2search2turn2search5  
- “Consent & First‑Party Measurement Spec (EEA‑ready)” citeturn9search0turn9search1  
- “Site Move Runbook: URL Mapping, Redirect Strategy, Monitoring” citeturn23view0  
- “Content Quality Policy: People‑First + Spam Safeguards + AI Usage” citeturn12search1turn24view1turn20view0  
- “RevOps Taxonomy: Pipeline Definitions, SLAs, Dashboards” citeturn4search2  
- “Security Governance: CSF 2.0 Profile + AI RMF GenAI Controls” citeturn25view3turn5search2  

### Must-read

1) Google Search Essentials (структура: technical requirements + spam policies). (дата на странице может не указываться). citeturn12search0  
2) Spam policies for Google Web Search. (дата на странице может не указываться). citeturn12search4  
3) March 5, 2024: core update + новые spam policies (expired domain, scaled content, site reputation abuse). citeturn24view1  
4) Nov 19, 2024: уточнение site reputation abuse policy + апдейты FAQ (Dec 6, 2024; Jan 21, 2025). citeturn24view0  
5) Canonicalization: “How to specify a canonical…” (canonical signals, redirects, JS caveats). (дата не всегда явно отображается, но актуальная редакция доступна в доках). citeturn22view0  
6) Redirects and Google Search (редиректы как сигнал canonical, типы редиректов). citeturn22view1  
7) Site move with URL changes (migration guidance, PageRank не теряется на 301/302, anti‑patterns). citeturn23view0  
8) Crawl Budget Management (обновлено 19 Dec 2025). citeturn0search1turn22view2  
9) Build and submit a sitemap (Last updated 2025‑12‑10 UTC; lastmod/priority/changefreq). citeturn21view0turn21view1  
10) Robots.txt introduction (robots ≠ noindex) и robots meta/X‑Robots‑Tag specs. citeturn1search6turn1search14  
11) Bing Webmaster Guidelines (включая рекомендации про canonical vs redirect). citeturn1search0  
12) IndexNow (протокол уведомления об изменениях URL). citeturn1search1turn1search5  
13) The CMO Survey Spring 2024 (бюджеты и GenAI использование/риски). citeturn17view0turn17view2turn17view3  
14) Forrester (May 1, 2024): критика “sourcing metrics” как доминирующих на CMO‑дашбордах. citeturn3search12  
15) Google Think: incrementality testing как основа privacy‑first measurement (контент про бюджеты 2024). citeturn9search2  
16) Consent Mode updates для EEA (Google Tag/Tag Manager help). citeturn9search0turn9search4  
17) Enhanced Conversions best practices (Google Ads Help). citeturn9search1  
18) Meta Conversions API best practices + Gateway guides. citeturn7search12turn9search3  
19) NIST CSF 2.0 (Feb 26, 2024) — особенно Govern и Core Functions. citeturn25view1turn25view3  
20) EU AI Act enters into force (Aug 1, 2024) + NIST AI RMF GenAI Profile (Jul 26, 2024). citeturn5search3turn5search2  

### Must-watch/listen

1) Search Off the Record (подкаст Google Search Central; страница с эпизодами). citeturn26search0  
2) YouTube playlist: English Google SEO Office Hours (актуальные выпуски 2024+). citeturn26search5  
3) Search Off the Record podcast playlist на YouTube. citeturn26search12  
4) SaaS Talk with the Metrics Brothers: эпизод про ICONIQ 2024 State of GTM Benchmarks (Aug 21, 2024). citeturn26search6  
5) Google Marketing Live 2025 roundup (официальный Google Ads Help: анонсы, включая упрощение incrementality testing). citeturn26search3  
6) Apple Podcasts/Art19 страница эпизода ICONIQ 2024 GTM Benchmarks (альтернативный источник/плеер). citeturn26search2turn26search6