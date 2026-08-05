# AGENTS.md — Standing Rules & User Preferences

## Standing Rules

1. **Мониторинг фоновых процессов и долгих задач**:
   - При запуске любых фоновых команд (`run_command`), долгих тестовых сюит, сборки или деплой-скриптов всегда использовать инструмент `schedule` (с `TimerCondition` на ID задачи или `TimerCondition="any"`), чтобы устанавливать контрольный таймер выполнения.
   - Это гарантирует своевременную проверку логов и исключает подвисание задач без контроля.

2. **Документация и архитектура**:
   - Поддерживать документацию [`README.md`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/README.md) и [`docs/TECHNICAL_DOCS.md`](file:///c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/docs/TECHNICAL_DOCS.md) в актуальном состоянии при любом изменении контрактов API, БД или бота.

3. **Тестирование перед завершением**:
   - Обязательно прогонять юнит-тесты (`pytest backend/tests`) перед заявлением о завершении задач.
