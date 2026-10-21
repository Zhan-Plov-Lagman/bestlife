# MASTER DEVELOPMENT PROMPT
## Autonomous Solana Trading Intelligence System — Initial Release v1.0

### ТВОЯ РОЛЬ

Ты — Principal Software Architect, Senior Quantitative Developer, ML Engineer, Solana Infrastructure Engineer, Security Engineer, Performance Engineer и Senior Full-Stack Developer.

Твоя задача — **не просто составить план или сгенерировать макет, а разработать работающее первоначальное приложение** для автономного анализа рынка мемкоинов Solana и симуляции торговых решений.

Это персональная система для одного пользователя, торгующего преимущественно через Axiom Trade.

**Главные приоритеты в порядке убывания:**

1. Безопасность капитала и отсутствие несанкционированных реальных сделок.
2. Корректность данных, решений, расчётов и торговой симуляции.
3. Оптимизация CPU, RAM, сетевого трафика, задержек и количества API-запросов.
4. Архитектурная модульность и возможность масштабирования.
5. Надёжность, наблюдаемость и восстановление после сбоев.
6. Качество алгоритмов, статистических моделей и тестирования.
7. Профессиональный интерфейс и удобное управление.

Не жертвуй первыми шестью требованиями ради декоративного frontend.

Не создавай фальшивые торговые результаты, псевдо-ML, фиктивные API-интеграции или неработающие элементы управления.

Если внешние данные недоступны, явно показывай Offline/Demo, а не подделывай Live.

---

# 1. ПРОДУКТОВАЯ КОНЦЕПЦИЯ

Создай автономную торгово-аналитическую платформу, способную:

- Наблюдать за токенами Solana.
- Получать и нормализовать рыночные данные.
- Анализировать ликвидность, объёмы и движения цен.
- Собирать доступные данные об активности кошельков.
- Выявлять потенциальные признаки манипуляций.
- Определять текущий рыночный режим.
- Переключаться между специализированными торговыми моделями.
- Рассчитывать статистическую привлекательность сделки.
- Независимо оценивать риски.
- Самостоятельно открывать и закрывать **виртуальные** позиции.
- Сохранять историю всех решений.
- Оценивать результативность после торговых издержек.
- Отслеживать ухудшение качества стратегии.
- Подготавливать новые версии моделей для тестирования.
- Работать продолжительное время без постоянного участия человека.

**Критически важно:** система не должна оптимизироваться только на максимальную прибыль.

Главная цель — устойчивость торговых решений, проверяемое положительное математическое ожидание и ограничение потенциальных потерь.

Не допускается предполагать, что какая-либо стратегия обеспечивает гарантированный доход.

---

# 2. ФИНАНСОВЫЕ ОГРАНИЧЕНИЯ

Реальный депозит пользователя: $70.

Первоначальный виртуальный депозит: $70.

Настройки должны быть конфигурируемыми, а не жёстко зашитыми в алгоритмы.

Первоначальная версия:

- PAPER_TRADING = true
- LIVE_TRADING_ENABLED = false
- REAL_WALLET_ACCESS = false
- AUTOMATIC_REAL_ORDERS = false
- PAID_LLM_ENABLED = false

Никаких запросов seed phrase, приватных ключей или cookie-сессий Axiom.

Не пытайся использовать недокументированные приватные API Axiom или обходить его защиту.

Предусмотри абстрактный ExecutionAdapter, но реализуй только PaperExecutionAdapter.

Любой код реального исполнения должен оставаться за пределами первоначальной версии.

---

# 3. ТЕХНОЛОГИЧЕСКИЙ СТЕК

## Backend

- Python 3.12+ с проверкой совместимости зависимостей.
- FastAPI.
- Pydantic v2.
- asyncio.
- httpx для асинхронных HTTP-запросов.
- WebSocket-клиенты для потоковых данных.
- SQLAlchemy 2.x.
- Alembic для миграций.
- PostgreSQL как целевая база данных.
- SQLite как упрощённый локальный режим разработки при необходимости.

## ML и аналитика

- NumPy.
- Polars для обработки больших наборов данных.
- scikit-learn.
- LightGBM как кандидат для табличных моделей.
- joblib или другой безопасно контролируемый механизм сохранения моделей.

Не загружай недоверенные сериализованные модели.

Не используй PyTorch, TensorFlow, тяжёлые LLM и GPU-вычисления без доказанной необходимости.

## Frontend

- Next.js с App Router.
- TypeScript в strict mode.
- Tailwind CSS.
- shadcn/ui.
- lucide-react.
- Lightweight Charts для рыночных графиков.
- TanStack Query для серверного состояния.
- Zustand только для небольшого локального UI-состояния.

Используй совместимые актуальные стабильные версии. Проверь документацию и совместимость перед установкой.

## Infrastructure

- Docker Compose для локальной среды.
- Структурированное логирование.
- pytest, pytest-asyncio.
- Ruff.
- mypy.
- Vitest.
- Playwright для ключевых пользовательских сценариев.

Начальная архитектура — modular monolith, а не множество дорогостоящих микросервисов.

Логические подсистемы должны быть изолированы интерфейсами, но могут работать в одном backend-процессе.

Не запускай шесть отдельных LLM-агентов ради визуального эффекта.

---

# 4. ГЛОБАЛЬНАЯ АРХИТЕКТУРА

Реализуй следующую структуру:

```text
DATA PROVIDERS
   |
   v
MARKET SCANNER
   |
   v
NORMALIZATION & VALIDATION
   |
   v
FEATURE ENGINE
   |
   v
MARKET REGIME DETECTOR
   |
   v
ML STRATEGY DISPATCHER
   |
   +----------+----------+
   |          |          |
   v          v          v
AGGRESSOR  SCALPING   GUARDIAN
   |          |          |
   +----------+----------+
              |
              v
       DECISION COUNCIL
              |
              v
       CAPITAL ALLOCATOR
              |
              v
          RISK ENGINE
              |
       +------+------+
       |             |
       v             v
  APPROVED        REJECTED
       |             |
       v             v
 PAPER EXECUTION   SKIP TRADE
       |             |
       +------+------+
              |
              v
       EVENT JOURNAL
              |
              v
     FEEDBACK & LEARNING
              |
              v
        META GOVERNOR
              |
              v
     OFFLINE MODEL REVIEW
```

Важное изменение:

GUARDIAN должен быть одновременно специализированным защитным аналитическим режимом и источником дополнительных предупреждений.

Но обязательные правила Risk Engine всегда работают независимо от Guardian.

Meta Governor не должен напрямую менять торговые лимиты в сторону увеличения или автоматически выпускать переобученную модель в production.

---

# 5. MARKET DATA INFRASTRUCTURE

Создай универсальный интерфейс MarketDataProvider.

Реализуй минимум:

1. DemoMarketDataProvider.
2. DexScreenerMarketDataProvider.
3. SolanaRPCProvider с доступными read-only методами.

Архитектура должна поддерживать будущие дополнительные источники, но не имитировать интеграции, которых нет.

Обеспечь:

- HTTP pooling.
- WebSocket reconnect с exponential backoff и jitter.
- Rate limiting для каждого провайдера.
- Общий ограничитель конкурентных запросов.
- Connection health monitoring.
- Дедупликацию событий.
- Проверку timestamp.
- Ограничение допустимой устарелости данных.
- TTL-кэширование.
- Batch-запросы, где они поддерживаются.
- Circuit breaker.
- Отслеживание расходов на запросы.
- Graceful degradation при отказе источника.

Не используй DEX Screener как будто он предоставляет полноценный низколатентный поток всех on-chain сделок.

Если реальные признаки нельзя получить из бесплатного источника, помечай их unavailable и не выдумывай значения.

Не открывай сделку при отсутствии критически необходимых данных.

---

# 6. DATA NORMALIZATION

Создай строгие внутренние модели:

- Token.
- Pool.
- MarketSnapshot.
- MarketEvent.
- WalletActivity.
- LiquiditySnapshot.
- TradeTick.
- OHLCVBar.
- FeatureVector.
- Prediction.
- StrategySignal.
- RiskAssessment.
- TradeDecision.
- PaperOrder.
- PaperFill.
- Position.
- PortfolioSnapshot.
- ModelVersion.
- SystemEvent.

Для денежных величин используй Decimal либо целочисленные минимальные единицы.

Для расчётов статистики допускаются float, но конвертация денежных значений должна быть явной.

Обязательно сохраняй:

- event_time.
- received_time.
- processing_time.
- provider.
- provider_event_id при наличии.
- chain.
- token_mint.
- pool_address.
- data_quality_status.

При конфликте источников не усредняй значения вслепую.

---

# 7. FEATURE ENGINE

Создай расширяемую систему вычисления признаков.

Категории:

## Momentum

- Price returns.
- Return acceleration.
- Volume change.
- Buy/sell imbalance.
- Momentum consistency.
- Short-term volatility.

## Liquidity

- Liquidity size.
- Liquidity changes.
- Liquidity-to-volume ratio.
- Pool depth proxies.
- Price impact estimate.

## Wallet Intelligence

- Unique buyers/sellers.
- Wallet activity changes.
- Concentration metrics.
- Repeated coordinated activity.
- Historical wallet behavior.

## Risk

- Extreme price discontinuities.
- Rapid liquidity withdrawals.
- Suspicious token authority settings.
- Holder concentration.
- Abnormal transaction patterns.

## Execution

- Estimated slippage.
- Network fees.
- Priority fees.
- Expected execution delay.
- Expected round-trip trading cost.

Каждый признак должен иметь:

- название;
- версию;
- единицы измерения;
- формулу;
- источник данных;
- окно наблюдения;
- timestamp;
- признак доступности;
- тест корректности.

Нельзя использовать данные из будущего при расчёте признаков.

---

# 8. MARKET REGIME DETECTOR

Создай отдельный модуль определения рыночного режима.

Режимы:

- MOMENTUM_EXPANSION.
- SHORT_TERM_OPPORTUNITY.
- DEFENSIVE.
- UNCLASSIFIED.
- NO_TRADE.

Первоначально реализуй прозрачный rule-based baseline.

Затем добавь интерфейс для ML-классификатора.

Не создавай фиктивную обученную модель.

Если исторических размеченных данных недостаточно, система обязана работать на baseline-правилах, явно указывая режим BASELINE.

Результат детектора:

```json
{
  "regime": "DEFENSIVE",
  "confidence": 0.72,
  "model_version": "baseline-v1",
  "data_quality": "VALID",
  "reason_codes": [
    "HIGH_VOLATILITY",
    "LIQUIDITY_DECLINE"
  ]
}
```

Confidence должен иметь понятную семантику.

Если он не откалиброван статистически, показывай его как score, а не как достоверную вероятность.

При низком качестве данных выбирай NO_TRADE.

---

# 9. AGGRESSOR STRATEGY

Цель: выявлять подтверждённые импульсные возможности.

Aggressor не должен покупать токен исключительно потому, что его цена резко выросла.

Проверяй:

- силу и устойчивость импульса;
- качество объёма;
- ликвидность;
- возможную синхронную активность связанных кошельков;
- степень запаздывания входа;
- предполагаемые торговые издержки;
- возможные сценарии выхода.

Выход стратегии:

- WAIT;
- PROPOSE_ENTRY;
- PROPOSE_EXIT;
- REJECT.

Каждое решение сопровождается численными признаками и reason codes.

Aggressor не имеет права увеличивать допустимый риск самостоятельно.

---

# 10. SCALPING STRATEGY

Цель: проверять краткосрочные возможности на микроизменениях цены.

Обязательно:

- учитывать spread/price impact, если доступны;
- учитывать round-trip fees;
- учитывать latency;
- запрещать сделки, у которых ожидаемое преимущество меньше совокупных издержек и установленного запаса неопределённости;
- ограничивать время жизни сигнала;
- прекращать использование устаревших сигналов;
- избегать постоянных покупок и продаж без положительного ожидания.

Нельзя моделировать мгновенный гарантированный выход по последней наблюдаемой цене.

---

# 11. GUARDIAN STRATEGY

Guardian оценивает неблагоприятные условия.

Он должен обнаруживать:

- резкое ухудшение ликвидности;
- экстремальную волатильность;
- подозрительную концентрацию;
- аномалии в потоке торгов;
- некорректность рыночных данных;
- невозможность надёжно оценить исполнение;
- критические признаки потенциальной манипуляции.

Guardian может рекомендовать:

- NORMAL;
- CAUTION;
- DEFENSIVE;
- BLOCK.

Guardian не должен создавать ложное впечатление, что все мошеннические токены можно обнаружить автоматически.

---

# 12. DECISION COUNCIL

Создай отдельный механизм согласования решений.

На вход поступают:

- regime assessment;
- strategy signals;
- Guardian assessment;
- data quality;
- model confidence;
- expected trading costs.

Council обязан формировать воспроизводимое решение.

Не использовать свободный LLM-текст в качестве команды покупки.

Каждому решению присваивать уникальный ID.

Пример результата:

```json
{
  "decision_id": "uuid",
  "action": "SKIP",
  "strategy": "AGGRESSOR",
  "reason_codes": [
    "UNFAVORABLE_EXECUTION_COST",
    "GUARDIAN_WARNING"
  ],
  "model_version": "baseline-v1",
  "risk_approval": false
}
```

Запретить использование неподтверждённых вероятностей в качестве гарантированных прогнозов.

---

# 13. CAPITAL ALLOCATOR

Отдельная подсистема управления капиталом.

Начальное состояние:

- Virtual balance: $70.
- Real capital exposure: $0.
- No leverage.
- No borrowing.
- No martingale.
- No averaging down by default.
- No automatic position escalation after profits.
- No increase in risk after a loss.

Размер позиции не должен зависеть исключительно от названия стратегии.

Используй общие ограничения:

- максимальный размер одной позиции;
- максимальная суммарная экспозиция;
- максимальное количество одновременных позиций;
- максимальный дневной убыток;
- максимальная просадка;
- лимит расходов на исполнение.

Создай конфигурируемые параметры без заявления, что какие-то конкретные проценты безопасны.

Для первоначального тестирования размер виртуальной позиции может быть ограничен консервативными настройками, но эти значения не должны выдаваться за оптимальные.

Если минимальные расходы делают сделку экономически бессмысленной, система обязана пропускать её.

---

# 14. RISK ENGINE

Это самый приоритетный компонент торговой логики.

Реализуй независимые жёсткие проверки:

1. Data Freshness Gate.
2. Data Quality Gate.
3. Market Liquidity Gate.
4. Estimated Execution Cost Gate.
5. Portfolio Exposure Gate.
6. Maximum Drawdown Gate.
7. Daily Loss Gate.
8. Strategy Health Gate.
9. Provider Health Gate.
10. Kill Switch.
11. Suspicious Token Gate.
12. Position Concentration Gate.
13. Duplicate Order Gate.
14. Trading Session State Gate.

Если обязательная проверка не может выполниться, используется принцип FAIL CLOSED.

Risk Engine возвращает:

- APPROVED;
- REJECTED;
- SYSTEM_HALTED.

Каждый отказ фиксируется в Event Journal.

Для kill switch обеспечь немедленный запрет на новые виртуальные входы.

Продумай отдельные состояния остановки торговли и аварийного управления уже открытыми виртуальными позициями.

Никакая стратегия не должна обходить Risk Engine.

---

# 15. PAPER EXECUTION ENGINE

Реализуй полноценный виртуальный торговый движок.

Сущности:

- Order.
- Fill.
- Position.
- Portfolio.
- ExecutionCost.
- ExecutionReport.

Поддерживаемые состояния:

- CREATED;
- VALIDATED;
- REJECTED;
- PENDING;
- PARTIALLY_FILLED;
- FILLED;
- CANCELLED;
- EXPIRED;
- FAILED.

Для первой версии допускается упрощённая модель исполнения, но все упрощения должны быть документированы.

Симуляция учитывает:

- задержку между сигналом и исполнением;
- наблюдаемую доступную цену;
- комиссии сети;
- предполагаемые platform/trading fees;
- проскальзывание;
- оценку price impact;
- неудачные исполнения;
- истечение времени действия сигнала.

Вход и выход должны оцениваться независимо.

Не рассчитывай P&L только по последней цене токена.

Отдельно показывай:

- realized P&L;
- unrealized P&L;
- gross P&L;
- net P&L;
- fees paid;
- estimated execution costs.

Если отсутствуют данные, необходимые для честной симуляции, сделка должна отклоняться либо использовать явно отмеченную консервативную тестовую модель.

Демонстрационные результаты не должны смешиваться с результатами реального рыночного paper trading.

---

# 16. EVENT JOURNAL

Все важные события должны быть сохранены.

Записывай:

- наблюдение рынка;
- вычисление признаков;
- определение режима;
- выбор модели;
- предложение сделки;
- решение Council;
- результат Risk Engine;
- создание ордера;
- исполнение;
- закрытие позиции;
- изменение состояния стратегии;
- ошибки провайдеров;
- изменение конфигурации;
- остановку системы.

Добавь correlation ID и decision ID.

Обеспечь idempotency, чтобы повторная обработка одного события не создавала дублирующую сделку.

Используй отдельные ограничения уникальности в БД.

---

# 17. FEEDBACK & LEARNING

Система должна анализировать свои решения, но не изменять торговую стратегию бесконтрольно.

Реализуй:

- trade outcome attribution;
- signal quality analysis;
- execution cost analysis;
- regime classification review;
- strategy performance tracking;
- model prediction tracking;
- drift monitoring;
- retraining candidate queue.

Особенно важно сохранять не только результаты совершённых сделок, но и отклонённые сигналы.

Не превращай прибыльность отклонённых сигналов в искусственно точную оценку того, что произошло бы при реальном исполнении.

Переобучение должно выполняться отдельно от критического торгового контура.

Новая модель получает статус CANDIDATE и не может автоматически заменить активную.

---

# 18. ML TRAINING & VALIDATION

Создай полноценную инфраструктуру ML.

Сначала baseline, затем проверяемые обученные модели.

Раздели данные хронологически.

Используй:

- temporal train/validation/test;
- walk-forward validation;
- purge/embargo при пересекающихся целевых окнах;
- out-of-sample tests;
- comparison against simple baselines;
- class imbalance analysis;
- probability calibration;
- feature leakage detection;
- feature importance analysis;
- performance per market regime.

Не оценивай качество только по accuracy или win rate.

Считай:

- precision/recall там, где применимо;
- Brier score для вероятностных прогнозов;
- calibration error;
- expected value;
- net P&L;
- max drawdown;
- profit factor;
- turnover;
- transaction cost sensitivity;
- risk of ruin estimates с оговорками о модельных предположениях.

Проверяй устойчивость результатов к увеличению комиссий, проскальзывания и задержки исполнения.

Не допускать survivorship bias.

Не использовать признаки, появившиеся после момента торгового решения.

Не утверждай, что модель обучена на тысячах токенов, если реальных данных нет.

---

# 19. META GOVERNOR

Meta Governor — подсистема контроля здоровья торговой архитектуры.

Функции:

- strategy performance monitor;
- prediction calibration monitor;
- drift detection;
- error rate monitoring;
- data provider reliability assessment;
- execution quality assessment;
- safe mode activation;
- strategy suspension;
- model version registry.

При ухудшении статистики система может снижать активность либо полностью приостанавливать стратегию.

Но Meta Governor не должен самостоятельно увеличивать риск.

Новые модели проходят отдельный процесс проверки и явно фиксируемого утверждения версии.

---

# 20. АРХИТЕКТУРА БАЗЫ ДАННЫХ

Спроектируй нормализованную схему PostgreSQL.

Минимальные таблицы:

- tokens
- pools
- market_snapshots
- market_events
- wallet_observations
- feature_snapshots
- market_regimes
- strategy_signals
- decisions
- risk_assessments
- paper_orders
- paper_fills
- paper_positions
- portfolio_snapshots
- model_versions
- model_evaluations
- backtest_runs
- system_events
- provider_health
- app_settings

Создай миграции и необходимые индексы.

Продумай retention policy для высокочастотных данных.

Не сохраняй огромные необработанные payload в PostgreSQL без необходимости.

Для исторических массивов допускается Parquet с метаданными в базе.

---

# 21. FRONTEND — PREMIUM TRADING TERMINAL

Создай полностью адаптивный интерфейс.

Дизайн:

- Premium dark trading terminal.
- Почти чёрный фон.
- Сдержанные графитовые панели.
- Минималистичные тонкие границы.
- Акцентный emerald green.
- Amber для Aggressor.
- Cyan для Scalping.
- Green для Guardian.
- Red исключительно для критических ошибок и убытков.
- Фиолетовый для аналитики и ML.

Вдохновение: современные профессиональные торговые терминалы и интерфейсы FOMO × GROK.

Не копируй чужой фирменный дизайн буквально.

Избегай чрезмерных анимаций, blur-эффектов и тяжёлых canvas-сцен.

## Dashboard

Показывай:

- Virtual Balance.
- Realized P&L.
- Unrealized P&L.
- Net P&L.
- Win Rate.
- Maximum Drawdown.
- Active Strategy.
- System Health.
- Data Provider Status.
- Number of Decisions.
- Skipped Trades.
- Fees & Execution Costs.
- Paper Trading Status.

Все показатели должны поступать из backend.

## Trading Floor

Создай визуализацию архитектуры:

Market Scanner → ML Dispatcher → Strategies → Decision Council → Risk Engine → Execution.

Карточки трёх стратегий:

AGGRESSOR  
SCALPING  
GUARDIAN

У каждой:

- active/inactive/suspended;
- score;
- last decision;
- reason codes;
- market regime;
- historical performance;
- current health.

## Token Explorer

- список токенов;
- поиск;
- сортировка;
- фильтрация;
- рыночные признаки;
- карточка токена;
- график цены;
- ликвидность;
- объём;
- доступные признаки риска.

## Portfolio

- виртуальные позиции;
- история входов и выходов;
- P&L;
- расходы;
- график equity curve.

## Decision Journal

Показывай причинно-следственную цепочку каждого решения.

Пользователь должен понимать, почему система купила, продала или отказалась от сделки.

## ML Laboratory

- model registry;
- version;
- validation status;
- evaluation metrics;
- drift alerts;
- comparison against baseline;
- retraining status.

## System Monitor

- CPU;
- RAM;
- process health;
- event loop lag;
- provider requests;
- API errors;
- rate-limit events;
- processing latency;
- cache hit ratio;
- queue depth;
- dropped/coalesced noncritical updates.

## Settings

- virtual balance reset;
- paper trading start/stop;
- risk parameters;
- provider configuration;
- strategy configuration;
- performance settings;
- log retention;
- kill switch.

Все интерактивные элементы должны реально работать.

Никаких декоративных кнопок без функциональности.

---

# 22. ОПТИМИЗАЦИЯ — АБСОЛЮТНЫЙ ПРИОРИТЕТ

Это важнейшая инженерная часть задания.

Система будет запускаться преимущественно на пользовательском ноутбуке.

Не допускай неоправданной загрузки CPU, RAM и GPU.

## Backend Optimization

- Event-driven architecture.
- Async I/O.
- Bounded queues.
- Backpressure.
- Connection pooling.
- Batched database writes.
- Controlled concurrency.
- Cache with TTL.
- Avoid busy polling.
- Avoid repeated feature recalculation.
- Incremental rolling calculations.
- Vectorized batch analysis.
- Timeouts.
- Memory profiling.
- Efficient serialization.
- Graceful shutdown.

Не создавай отдельный тяжёлый процесс для каждого агента.

Все три стратегии должны использовать общие данные, а не трижды запрашивать одни и те же API.

## ML Optimization

- CPU-first inference.
- Models loaded once.
- Shared feature vectors.
- Inference batching where appropriate.
- Model warmup.
- Prediction caching only when valid.
- Separate training and inference workflows.

Обучение не должно незаметно запускаться во время торговой обработки.

## Frontend Optimization

- WebSocket updates instead of aggressive polling.
- Throttled visual updates.
- React memoization where justified.
- List virtualization.
- Limited chart history in memory.
- Lazy-loaded heavy panels.
- Dynamic imports.
- Avoid unnecessary rerenders.
- Avoid oversized bundles.
- Avoid continuous high-cost animations.

Ограничение частоты перерисовки UI не должно приводить к пропуску критических рыночных событий в backend.

## Performance Modes

Добавь три режима:

ECO:
- минимальное фоновое потребление ресурсов;
- редкие обновления второстепенных элементов UI;
- ограниченная параллельная обработка.

BALANCED:
- разумный компромисс скорости и нагрузки.

PERFORMANCE:
- повышенная частота обработки и обновления данных при наличии ресурсов.

Это режимы производительности, а не торговые стратегии.

Выбор ECO не должен менять математическую логику риска и принятия решений.

---

# 23. PERFORMANCE BENCHMARKS

Создай воспроизводимые тесты производительности.

Целевые ориентиры первоначальной версии на заранее задокументированном локальном оборудовании:

- Idle backend CPU: стремиться к менее 2% одного логического ядра без активного потока данных.
- Idle backend RAM: целевой ориентир менее 300 MB без тяжёлых загруженных моделей.
- Обработка синтетического потока: тест на 1000 событий/сек с измерением задержек и потерь.
- Измерять p50/p95/p99 processing latency.
- Измерять event loop lag.
- Измерять memory growth.
- Проверять восстановление после разрыва WebSocket.
- Проверять устойчивость к rate limiting.
- Проверять отсутствие дублированных виртуальных сделок.

Это целевые показатели, а не гарантия.

Если ориентир не достигнут, покажи фактические метрики и объясни bottleneck.

Не заявляй, что система оптимизирована, без профилирования.

---

# 24. COST OPTIMIZATION

Цель: использовать доступные бесплатные инструменты и по возможности избежать постоянных расходов.

- Никаких обязательных платных LLM API.
- Никаких обязательных облачных GPU.
- Никаких дорогостоящих автономных LLM-циклов.
- Максимально переиспользуй данные.
- Учитывай rate limits провайдеров.
- Предусмотри ограничение количества запросов.
- Показывай источник каждой цены/метрики.
- Не обещай бесплатный круглосуточный доступ к данным без проверки лимитов.

Если поставщик требует платный тариф для конкретной функции, пометь функцию как Optional / Requires Provider.

---

# 25. SECURITY

Обязательные требования:

- local-only по умолчанию;
- отсутствие внешнего доступа без явной настройки;
- secrets только через env или защищённый механизм;
- не коммитить env, ключи, токены и credentials;
- не хранить пароли и приватные ключи кошельков;
- CORS allowlist;
- проверка всех входных данных;
- безопасные SQL-запросы;
- ограничение административных endpoints;
- защита WebSocket;
- отказ от выполнения произвольного кода из внешних данных;
- безопасная загрузка ML-моделей;
- dependency auditing;
- API rate limiting;
- журнал изменения настроек.

Никакие данные из сообщений, названий токенов или внешних источников не должны восприниматься как команды приложению.

---

# 26. FAULT TOLERANCE

Система должна корректно обрабатывать:

- отключение интернета;
- недоступность API;
- ошибку WebSocket;
- 429 responses;
- повреждённый payload;
- пропущенные данные;
- остановку PostgreSQL;
- перезапуск backend;
- повторную доставку событий;
- зависшие запросы;
- несоответствие состояния ордеров;
- переполнение очередей;
- ошибки модели;
- недостаток памяти.

При невозможности подтвердить корректность состояния исполнения система должна прекращать создание новых ордеров.

После перезапуска восстанови состояние виртуальных позиций и журнал решений.

---

# 27. TESTING

Напиши тесты для:

- нормализации данных;
- точности денежных вычислений;
- расчёта признаков;
- определения рыночных режимов;
- Strategy Dispatcher;
- Aggressor;
- Scalping;
- Guardian;
- Decision Council;
- Risk Engine;
- Capital Allocator;
- Paper Execution;
- комиссий;
- проскальзывания;
- stop-loss simulation;
- P&L;
- drawdown;
- idempotency;
- kill switch;
- provider failures;
- ML validation;
- model versioning;
- восстановления после перезапуска.

Добавь интеграционный тест полного цикла:

Market Event → Feature Engine → Regime Detection → Strategy → Risk → Paper Order → Fill → Portfolio → Journal.

Добавь E2E тесты запуска paper trading, остановки системы и просмотра истории решений.

---

# 28. PROJECT STRUCTURE

Используй понятную монорепозиторную структуру:

```text
trading-intelligence/
  frontend/
    app/
    components/
    features/
    hooks/
    lib/
    tests/

  backend/
    app/
      api/
      core/
      config/
      data/
        providers/
        normalization/
        ingestion/
      features/
      regimes/
      strategies/
        aggressor/
        scalping/
        guardian/
      dispatcher/
      council/
      allocation/
      risk/
      execution/
        paper/
      portfolio/
      journal/
      learning/
      governance/
      monitoring/
      database/
      schemas/
    tests/
    migrations/

  ml/
    datasets/
    features/
    training/
    evaluation/
    registry/

  benchmarks/
  docs/
  scripts/
  docker-compose.yml
  .env.example
  README.md
  PROJECT_SPEC.md
  ARCHITECTURE.md
  SECURITY.md
  PERFORMANCE.md
```

Не создавай пустые каталоги ради имитации масштаба.

Каждая реализованная подсистема должна иметь конкретную функцию, интерфейсы и тесты.

---

# 29. INITIAL RELEASE SCOPE

Первый релиз должен быть реально работоспособным.

Обязательные функции v1:

1. FastAPI backend.
2. Next.js frontend.
3. PostgreSQL migrations.
4. Demo provider.
5. По возможности рабочий DexScreener provider.
6. Market Scanner.
7. Feature Engine с базовыми признаками.
8. Rule-based Regime Detector.
9. Рабочий Strategy Dispatcher.
10. Три стратегии с объяснимыми baseline-правилами.
11. Decision Council.
12. Capital Allocator.
13. Risk Engine.
14. Paper Execution.
15. Portfolio Accounting.
16. Event Journal.
17. System Monitoring.
18. Premium Dashboard.
19. Strategy Cards.
20. Token Explorer.
21. Paper Portfolio.
22. Decision History.
23. Settings.
24. Kill Switch.
25. Unit tests.
26. Integration tests.
27. Benchmark suite.
28. Docker Compose.
29. README с командами запуска.

Если качественная ML-модель не может быть обучена из-за отсутствия достоверной исторической выборки, реализуй ML infrastructure и baseline.

Не заменяй отсутствующее обучение случайными предсказаниями.

---

# 30. КРИТЕРИИ ГОТОВНОСТИ

Приложение считается готовым как Initial Release, только если:

- backend запускается;
- frontend запускается;
- база создаётся миграциями;
- demo pipeline проходит полный цикл;
- пользователь видит состояние системы;
- стратегии возвращают реальные воспроизводимые решения;
- Risk Engine способен заблокировать сделку;
- виртуальная покупка изменяет портфель;
- виртуальная продажа корректно рассчитывает P&L;
- убытки и комиссии учитываются;
- журнал объясняет принятое решение;
- kill switch работает;
- данные сохраняются после перезапуска;
- переключение режимов производительности работает;
- тесты выполняются;
- benchmark можно повторить;
- README содержит все команды;
- приложение не требует приватных ключей или платной LLM.

Никаких утверждений о готовности live trading.

---

# 31. ПОРЯДОК РАЗРАБОТКИ

Работай последовательно.

PHASE 1 — исследование среды, проверка зависимостей, структура проекта, архитектура и контракт данных.

PHASE 2 — backend core, configuration, database, data providers.

PHASE 3 — Market Scanner, Feature Engine, Regime Detector.

PHASE 4 — Aggressor, Scalping, Guardian, Dispatcher.

PHASE 5 — Decision Council, Capital Allocator, Risk Engine.

PHASE 6 — Paper Execution, Portfolio, Journal.

PHASE 7 — API и потоковые обновления frontend.

PHASE 8 — полноценный Trading Dashboard и экраны управления.

PHASE 9 — ML pipeline, registry, baseline evaluation, Meta Governor foundations.

PHASE 10 — profiling, optimization, failure tests, documentation.

В каждой фазе:

- пиши рабочий код;
- проверяй типы;
- запускай тесты;
- устраняй ошибки;
- не ломай предыдущие функции;
- документируй технические компромиссы.

Если весь scope не помещается в одну сессию, оставь рабочее ядро, перечень завершённых компонентов и проверяемый план продолжения.

Не обозначай непроверенные функции как завершённые.

---

# 32. ТРЕБОВАНИЯ К ТВОЕМУ ПОВЕДЕНИЮ КАК CODEX

Ты должен действовать как самостоятельный инженер, а не как генератор псевдокода.

Не останавливайся после красивого README.

Не ограничивайся архитектурной схемой.

Не пиши frontend с фиктивной бизнес-логикой.

Не создавай искусственный P&L ради эффектного Dashboard.

Не устанавливай тяжёлые зависимости без необходимости.

Не обещай безопасность или доходность без доказательств.

Не подключай настоящий кошелёк.

Не используй реальные средства.

Не копируй секреты.

Приоритет — законченные вертикальные функциональные срезы, а не сотни пустых файлов.

Прежде чем создавать каждый сложный компонент, оцени его вычислительную стоимость.

После реализации:

1. Выполни доступные тесты.
2. Выполни сборку frontend.
3. Проверь запуск backend.
4. Проверь migrations.
5. Запусти интеграционный demo scenario.
6. Измерь потребление ресурсов.
7. Зафиксируй результаты.
8. Перечисли ограничения.
9. Объясни, какие внешние интеграции реально работают.
10. Укажи, что остаётся для следующей версии.

---

# FINAL INSTRUCTION

**Начинай создавать проект прямо сейчас.**

Цель — получить серьёзный технический фундамент автономной торговой системы, а не демонстрационную веб-страницу.

Система должна обладать следующими свойствами:

- Autonomous.
- Explainable.
- Risk-aware.
- Modular.
- CPU-efficient.
- API-efficient.
- Observable.
- Recoverable.
- Testable.
- Extensible.

Сделай сначала полноценный рабочий paper trading pipeline, затем подключи его к профессиональному frontend.

Не подменяй реальные статистические модели декоративными AI-агентами.

Не оптимизируй систему на погоню за максимальной прибылью.

**Оптимизируй её на измеримую эффективность, достоверность вычислений, устойчивость и сохранение капитала.**
