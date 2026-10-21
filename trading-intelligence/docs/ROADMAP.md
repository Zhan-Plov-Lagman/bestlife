# Проверяемый план продолжения

Это перечень незавершённых требований, а не список уже реализованных функций.

1. **Состояние и риск:** reconciliation портфеля по fills; отдельный writer lease; restore pending exits после crash; property-based бухгалтерские инварианты и стресс граничных Decimal значений. Блокировка новых входов при stale marks уже реализована и проверена.
2. **Данные:** реальные timestamp/slot, исполнимые quotes и документированный источник holder/authority/кошельковых признаков. До этого market-data paper trading остаётся observation-only. OHLCV, TradeTick, WalletActivity и полный feature registry не представлены как готовые.
3. **БД:** полноценные нормализованные таблицы/внешние ключи; проверка на PostgreSQL, остановка/восстановление PostgreSQL, архивирование Parquet и retention с сохранением dedup/audit. Backup/restore тест. Начальная миграция уже независима от текущих ORM metadata.
4. **Производительность:** batching без потери порядка, профиль CPU/I/O, 1000 events/s sustained тест, долгий soak, bounded history pagination/virtualization и межсессионный просмотр архива. Текущая UI история ограничена 100–200 записями.
5. **Исполнение:** частичные fills и распределение задержек на проверенных данных, расходы network/platform из явных источников, учёт неисполнения, stress cost/latency, единый deterministic replay clock.
6. **ML:** подлинная историческая выборка без survivorship bias, dataset hashes, полноценные persisted model registry/evaluations, обучение CPU-модели, temporal out-of-sample net performance, per-regime attribution, drift статистика, calibration, явное ручное утверждение candidate. Сейчас есть только helpers, базовая схема и offline JSON evaluation.
7. **UI:** подробная карточка стратегии с её историческими результатами, фильтры рисков/режимов, поля доступности и версии каждого признака, русская локализация, stale-mark UI, reconnect stress и мобильный E2E.
8. **Release gate:** прогон Compose/PostgreSQL, зависимостей Python 3.12, всех failure scenarios, headless browser flow после cold start, опубликованный отчёт измерений. Только затем оценивать полноту Initial Release v1.0.

Реальное исполнение, кошельки и автоматическое увеличение риска не входят в этот план первоначального приложения.
