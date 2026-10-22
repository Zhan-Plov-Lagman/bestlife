# Meridian v1.1 — локальный исследовательский терминал

Бумажная торговля с начальным виртуальным балансом $70. Кошельков, ключей и настоящих транзакций нет. Этот этап завершает основные исправления P0 и часть P1; Testing Gateway, Shadow UI и ML registry остаются отдельным этапом. [Инженерный отчёт](docs/V1_1_CHANGELOG.md).

## Windows 11: запуск без Docker

Нужны Python 3.12+ и Node.js 20.9+. Проверено: Python 3.14.3, Node 24.14.0. Из папки приложения:

```powershell
.\scripts\setup.ps1
.\scripts\dev.ps1
# По окончании:
.\scripts\stop.ps1
```

Скрипты находят приложение относительно собственного пути, независимо от текущей папки терминала. `setup.ps1 -BackendOnly` и `dev.ps1 -BackendOnly` не требуют frontend/Node. `dev.ps1` запускает собранный Next.js, поэтому после изменений UI выполните сборку или setup. `start.ps1` оставлен как совместимый вход в dev.ps1.

Открыть [терминал](http://127.0.0.1:3000), [OpenAPI](http://127.0.0.1:8000/docs). Backend слушает только 127.0.0.1:8000. Скрипт stop проверяет PID, время создания процесса и путь программы, затем запрашивает graceful shutdown. Чужие процессы не завершаются. Второй writer той же SQLite БД отклоняется OS-lock. Журналы запуска — `.run/`.

Торговля после старта приостановлена. Demo показывает вымышленные токены. Start paper trading разрешает входы после накопления признаков и проверки риска. Pause и Kill отменяют BUY, сохраняя выходы SELL. После restart BUY отменяются, SELL требуют нового наблюдения и повторной проверки. Несогласованный ledger блокирует торговлю; Clear halt не обходит сверку. Reset создаёт новую сессию, сохраняя историю.

## Реализовано

- FastAPI, Next.js, SQLite WAL + FULL, Alembic; SQLAlchemy сохраняет конфигурацию PostgreSQL через DATABASE_URL, но PostgreSQL runtime не проверен.
- Атомарный бумажный ledger на Decimal, идемпотентные события/fills, комиссии, slippage/impact, сверка fills → cash/positions → snapshots.
- Независимые правила Aggressor и Scalping; постоянный Guardian и отдельные ограничения входа/выхода Risk Engine. Версии baseline-v1 и baseline-v1.1 — правила, не обученные модели.
- Последовательная обработка batch до 16 событий в runtime (жёсткий предел 32), bounded queue 256, диагностика этапов, backpressure без ослабления durability.
- Локальная защита Origin/Host, истекающие session tokens, лимиты HTTP/WS, независимые read/control credentials в выключенном по умолчанию remote mode.
- Изолированный offline replay с виртуальным временем, хешем входных данных и финансового результата, явными синтетическими стресс-сценариями.

## Источники и достоверность

Demo — SYNTHETIC. DexScreener использует документированный `/tokens/v1/solana/{mints}` и остаётся observation-only: исходные timestamps, token safety и исполнимая котировка недоступны. Никакие observed fills не выдумываются. Solana RPC read-only: getHealth, getSlot, getTokenSupply, getAccountInfo. Нет Axiom integration и платных LLM API. Предыдущие проверки внешних endpoint сохранены в docs/provider-check.json; в этом этапе они повторно не выполнялись.

## Проверки и replay

```powershell
.\scripts\test.ps1
.\scripts\dev.ps1
.\scripts\test.ps1 -E2E
.\scripts\stop.ps1
.\scripts\benchmark.ps1 -Seconds 30
.\.venv\Scripts\python scripts/replay.py dataset.jsonl --output research/run-001 --scenario ADVERSE
```

E2E использует установленный Edge и меняет только виртуальную сессию. Replay требует JSONL объектов MarketSnapshot, отдельный новый каталог и пока принимает только явно синтетический DEMO источник. Сценарии BASE, ADVERSE и ILLIQUID; подробности в [TESTING_GATEWAY.md](docs/TESTING_GATEWAY.md). Старый offline evaluate_candidate.py сохранён; он не обучает и не продвигает модели.

## Документация

[Архитектура](ARCHITECTURE.md) · [Безопасность](SECURITY.md) · [Измерения](PERFORMANCE.md) · [Проверки](docs/VERIFICATION.md) · [Ограничения](docs/KNOWN_LIMITATIONS.md) · [План](docs/ROADMAP.md) · [Linux systemd](docs/NATIVE_DEPLOYMENT.md).

Docker/Compose-файлы сохранены только как необязательные примеры совместимости; Docker и WSL2 для запуска не нужны. Реальный облачный деплой не выполнялся.
