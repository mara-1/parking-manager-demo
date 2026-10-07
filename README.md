# ParkingManager

[![CI](https://github.com/mara-1/parking-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/mara-1/parking-manager/actions/workflows/ci.yml)
[![Commit messages](https://github.com/mara-1/parking-manager/actions/workflows/commitlint.yml/badge.svg)](https://github.com/mara-1/parking-manager/actions/workflows/commitlint.yml)

Десктоп-приложение для учёта и управления автомобильной парковкой.
Курсовой проект по дисциплине «Конструирование программного обеспечения».

**Стек:** C#, .NET 8, WPF (MVVM), EF Core + SQLite, QuestPDF, ClosedXML, xUnit.

## Структура репозитория

```
src/ParkingManager/          WPF-приложение: Views, ViewModels (ParkingManager.exe)
src/Parking.Core/            бизнес-логика (Services) и доступ к данным (DataAccess)
tests/Parking.Core.Tests/        модульные тесты
tests/Parking.IntegrationTests/  интеграционные тесты (EF Core + SQLite)
scripts/                     создание решения, сбор метрик
.github/workflows/           пайплайны CI/CD
.githooks/                   локальная проверка сообщений коммитов
```

## Начало работы

```bash
git clone https://github.com/mara-1/parking-manager.git
cd parking-manager
git config core.hooksPath .githooks
dotnet build
dotnet test
```

Правила оформления коммитов, ветвления, слияния и релизов — в [CONTRIBUTING.md](CONTRIBUTING.md).

Перед каждым коммитом рекомендуется выполнять `dotnet format`.