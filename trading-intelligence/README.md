# Meridian — Solana Trading Intelligence

Локальное приложение для исследования **виртуальной** торговли. Начальный виртуальный баланс — $70. Реальные средства, кошельки, приватные ключи, Axiom cookies и исполнение on-chain отсутствуют. Это рабочий первоначальный вертикальный срез, **не полный релиз всех 32 разделов исходной спецификации**.

## Запуск в Windows

Проверено на Python 3.14.3 и Node 24.14.0. Для Docker предусмотрен Python 3.12. Нужны Python 3.12+ и Node 20.9+.

Из папки `trading-intelligence`:

```powershell
python -m venv .venv
python -m pip --python .venv/Scripts/python.exe install -r backend/requirements.lock.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
```

Если `venv` создал Python, но не смог выполнить ensurepip, вторая команда устанавливает зависимости через системный pip непосредственно в `.venv`.

Backend, отдельный терминал:

```powershell
cd backend
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Frontend, второй терминал:

```powershell
cd frontend
npm.cmd run start
```

Открыть [терминал](http://127.0.0.1:3000). [OpenAPI](http://127.0.0.1:8000/docs). После установки/сборки можно использовать `powershell -File scripts/start.ps1`; Ctrl+C останавливает запущенный этим скриптом backend.

Система запускается с остановленными входами. Demo-сканер наблюдает три **вымышленных** токена. Нажмите **Start paper trading**, подождите накопления признаков и сигнала. Вход появится только на следующем наблюдении, после повторной проверки риска. В Portfolio доступны позиции и запрос выходов; Decision journal раскрывает признаки и каждую проверку. Pause отменяет pending-ордера; защитные выходы продолжаются. Kill switch блокирует новые входы, но не обещает мгновенную ликвидацию. Clear halt оставляет торговлю остановленной.

## Что реализовано

- FastAPI, Pydantic v2, SQLAlchemy, Alembic, SQLite WAL; PostgreSQL-compatible схема и Compose.
- Общий scanner → rolling features → baseline regime → Aggressor / Scalping / Guardian → Council → allocation → independent risk → delayed paper fill → ledger / journal.
- Decimal учёт с фиксированной денежной точностью, комиссии входа/выхода, slippage и impact, net liquidation equity, realized/unrealized P&L, drawdown.
- Идемпотентность событий и fills через первичные ключи; транзакционный commit всей обработки; откат и halt при сбое записи.
- Восстановление портфеля и журнала после перезапуска. Pending-ордера отменяются, автоматический рестарт входов запрещён.
- Настройки, performance modes, журнал, explorer, portfolio, status WebSocket с reconnect/backoff/jitter, монитор CPU/RAM/очереди/задержек.
- HTTP pooling, timeouts, ограничение запросов, TTL-cache, 429 backoff, circuit breaker, bounded queue/backpressure.
- Offline chronological split/purge/embargo, walk-forward splits, leakage checks, Brier/precision/recall/calibration metrics. JSON-only candidate evaluation; **обученных моделей нет**.
- Governor приостанавливает стратегии после трёх подряд закрытых убыточных сделок; самостоятельно лимиты не повышает.

## Источники данных

**Demo** работает без интернета. Это детерминированный тестовый сценарий, не исторический backtest и не доказательство доходности.

**DexScreener** использует документированный batch endpoint `/tokens/v1/solana/{mints}`. В Settings остановленного пустого портфеля выберите DEXSCREENER и задайте до 30 mint-адресов. Выбирается самый ликвидный доступный pool, цены разных pools не усредняются. Источник не сообщает надёжное время исходной цены, holder concentration или исполнимую котировку. Поэтому качество `UNAVAILABLE`, сделки fail closed. Нельзя трактовать время HTTP-наблюдения как время on-chain сделки. Смена provider создаёт отдельную session, история Demo не смешивается с ней.

**Solana RPC**: read-only adapter с allowlist `getHealth`, `getSlot`, `getTokenSupply`, `getAccountInfo`; UI-проверка доступности не запускается автоматически. `/api/rpc-health` делает read-only запрос к публичному endpoint. Wallet intelligence ещё не реализован.

Внешняя доступность и фактические результаты проверок перечислены в [VERIFICATION.md](docs/VERIFICATION.md). Нет платных LLM или облачных GPU. Нет интеграции Axiom.

## Проверки

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q --basetemp=./.test-local
..\.venv\Scripts\python -m ruff check app tests
..\.venv\Scripts\python -m mypy app
..\.venv\Scripts\python -m alembic current
cd ../frontend
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build
npm.cmd run e2e
npm.cmd audit
cd ..
.\.venv\Scripts\python benchmarks/run.py --events 1000
```

E2E требует работающих серверов и установленного Edge. Он меняет только текущую виртуальную сессию (start/stop/kill/clear-halt). В ограниченной Windows-песочнице asyncio socketpair и процессы сборщика могут блокироваться: проверки выполнялись с разрешённым локальным доступом. Для сборки используется Webpack: установленный Turbopack завершался внутренней ошибкой дочернего процесса.

## Docker / PostgreSQL

Скопируйте `.env.example` в `.env`, задайте локальный `POSTGRES_PASSWORD` (URL-safe, не используйте пароль от других сервисов), затем:

```powershell
docker compose up --build
```

Сервисы публикуются только на `127.0.0.1`. PostgreSQL не публикует порт наружу. Миграция выполняется до старта backend. **Compose и PostgreSQL runtime здесь не проверены: Docker в среде отсутствует.** Не запускайте больше одного backend worker: v1 использует одного writer и процессный lock.

## Offline evaluation

```powershell
.\.venv\Scripts\python scripts/evaluate_candidate.py dataset.json --horizon 60 --embargo 10 --version candidate-1 --output candidate-1.json
```

Вход: список объектов `time`, `feature_time`, `label` (0/1), `out_of_sample_probability`. Метрики считаются на последнем временном сегменте; происхождение out-of-sample прогнозов обязан подтвердить исследователь. Никаких моделей из pickle/joblib не загружается, автоматического promotion нет.

## Ограничения и продолжение

Подробности: [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md), [PERFORMANCE.md](PERFORMANCE.md), [план продолжения](docs/ROADMAP.md), оригинальное задание [PROJECT_SPEC.md](PROJECT_SPEC.md).

Тестовая модель исполнения all-or-none, без partial fills и order-book. Нет гарантии исполнения stop-loss при отсутствии данных. Mark-to-market может устаревать; показано время последнего mark. Baseline heuristic не является доказательством положительного ожидания. ML training, полноценная нормализованная реляционная схема, историческая выборка, автоматическая retention и sustained 1000 events/s остаются незавершёнными.
