# Первоначальное создание решения и проектов. Запускать ОДИН раз из корня
# репозитория в PowerShell. Нужен .NET SDK 8 (входит в Visual Studio 2022);
# версия SDK зафиксирована файлом global.json.
# Структура проектов соответствует диаграммам компонентов и развёртывания (ЛР4).

$ErrorActionPreference = 'Stop'

dotnet new sln -n ParkingManager

# ParkingManager.exe — слой представления (Views, ViewModels)
dotnet new wpf -n ParkingManager -o src/ParkingManager -f net8.0
# Parking.Core.dll — бизнес-логика (Services) и доступ к данным (DataAccess)
dotnet new classlib -n Parking.Core -o src/Parking.Core -f net8.0
# Модульные и интеграционные тесты
dotnet new xunit -n Parking.Core.Tests -o tests/Parking.Core.Tests -f net8.0
dotnet new xunit -n Parking.IntegrationTests -o tests/Parking.IntegrationTests -f net8.0

dotnet sln add src/ParkingManager src/Parking.Core tests/Parking.Core.Tests tests/Parking.IntegrationTests

dotnet add src/ParkingManager reference src/Parking.Core
dotnet add tests/Parking.Core.Tests reference src/Parking.Core
dotnet add tests/Parking.IntegrationTests reference src/Parking.Core

dotnet restore

dotnet add src/Parking.Core package Microsoft.EntityFrameworkCore.Sqlite --version 8.*
dotnet add src/Parking.Core package QuestPDF
dotnet add src/Parking.Core package ClosedXML

Remove-Item src/Parking.Core/Class1.cs
New-Item -ItemType Directory -Force src/Parking.Core/Services, src/Parking.Core/DataAccess, src/ParkingManager/Views, src/ParkingManager/ViewModels | Out-Null

# Приведение шаблонного кода к правилам .editorconfig
dotnet format

# Подключение локальной проверки сообщений коммитов
git config core.hooksPath .githooks

Write-Host 'Готово. Проверьте сборку: dotnet build; тесты: dotnet test'
