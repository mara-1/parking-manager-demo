#!/usr/bin/env python3
"""Сбор метрик качества проекта ParkingManager.

Запускается в GitHub Actions (.github/workflows/metrics.yml) при создании
релиза в конце каждого этапа разработки или вручную. Результат сохраняется
в metrics.json (для обработки) и metrics.md (для чтения человеком).
"""

import argparse
import glob
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from statistics import mean, median

# Соответствие версий релизов этапам графика работ (ЛР3, Таблица 2)
STAGES = {
    "v0.0.1": "1. Архитектура",
    "v0.1.0": "2. Прототип",
    "v0.2.0": "3. Реализация I",
    "v0.3.0": "4. Реализация II",
    "v0.4.0": "5. Реализация III",
    "v0.9.0": "6. Тестирование",
    "v1.0.0": "7. Доработка и релиз",
}

WARNING_RE = re.compile(
    r"^\s*(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\): warning (?P<code>[A-Z]+\d+):",
    re.MULTILINE,
)
TRX_NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


def run(cmd):
    """Выполнить команду и вернуть stdout или None при ошибке."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
        return res.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_time(value):
    """ISO-время из TRX (7 знаков долей секунды) -> datetime."""
    value = re.sub(r"(\.\d{6})\d+", r"\1", value)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------- 1. Статический анализ ----------

def linter_metrics(build_log):
    if not build_log or not os.path.exists(build_log):
        return {"warnings_total": None, "warnings_by_group": {}}
    text = open(build_log, encoding="utf-8", errors="replace").read()
    unique = {(m["file"].strip(), m["line"], m["col"], m["code"]) for m in WARNING_RE.finditer(text)}
    groups = {}
    for *_, code in unique:
        prefix = re.match(r"[A-Z]+", code).group(0)
        groups[prefix] = groups.get(prefix, 0) + 1
    return {"warnings_total": len(unique), "warnings_by_group": dict(sorted(groups.items()))}


def complexity_metrics(raw_cobertura_files):
    """Цикломатическая сложность методов из отчётов coverlet (без дублей)."""
    methods = {}
    for path in raw_cobertura_files:
        root = ET.parse(path).getroot()
        for cls in root.iter("class"):
            for m in cls.iter("method"):
                c = m.get("complexity")
                if c is None:
                    continue
                key = (cls.get("name"), m.get("name"), m.get("signature"))
                methods[key] = max(methods.get(key, 0), float(c))
    values = list(methods.values())
    if not values:
        return {"complexity_max": None, "complexity_avg": None, "methods_over_10": None, "methods_total": 0}
    return {
        "complexity_max": int(max(values)),
        "complexity_avg": round(mean(values), 2),
        "methods_over_10": sum(v > 10 for v in values),
        "methods_total": len(values),
    }


# ---------- 2. Тестирование ----------

def coverage_metrics(merged_cobertura, raw_files):
    path = merged_cobertura if merged_cobertura and os.path.exists(merged_cobertura) else None
    if path is None and raw_files:
        path = raw_files[0]
    if path is None:
        return {"line_coverage": None, "branch_coverage": None}
    root = ET.parse(path).getroot()

    def pct(covered, valid, rate):
        c, v = root.get(covered), root.get(valid)
        if c is not None and v is not None and float(v) > 0:
            return round(100 * float(c) / float(v), 1)
        r = root.get(rate)
        return round(100 * float(r), 1) if r is not None and (v is None or float(v) > 0) else None

    return {
        "line_coverage": pct("lines-covered", "lines-valid", "line-rate"),
        "branch_coverage": pct("branches-covered", "branches-valid", "branch-rate"),
    }


def test_metrics(trx_dir):
    files = glob.glob(os.path.join(trx_dir, "**", "*.trx"), recursive=True) if trx_dir else []
    if not files:
        return {"tests_total": None, "tests_passed": None, "tests_failed": None, "tests_duration_s": None}
    total = passed = failed = 0
    duration = 0.0
    for path in files:
        root = ET.parse(path).getroot()
        counters = root.find(".//t:ResultSummary/t:Counters", TRX_NS)
        if counters is not None:
            total += int(counters.get("total", 0))
            passed += int(counters.get("passed", 0))
            failed += int(counters.get("failed", 0))
        times = root.find("t:Times", TRX_NS)
        if times is not None and times.get("start") and times.get("finish"):
            duration += (parse_time(times.get("finish")) - parse_time(times.get("start"))).total_seconds()
    return {"tests_total": total, "tests_passed": passed, "tests_failed": failed,
            "tests_duration_s": round(duration, 1)}


# ---------- 3. Процесс разработки (git) ----------

def git_metrics(ref):
    prev = run(["git", "describe", "--tags", "--abbrev=0", f"{ref}^"])
    prev = prev.strip() if prev else None
    rng = f"{prev}..{ref}" if prev else ref

    dates = run(["git", "log", "--no-merges", "--format=%cI", rng]) or ""
    dates = [datetime.fromisoformat(d) for d in dates.split()]
    if prev:
        start = datetime.fromisoformat(run(["git", "log", "-1", "--format=%cI", prev]).strip())
    else:
        start = min(dates) if dates else None
    end = datetime.fromisoformat(run(["git", "log", "-1", "--format=%cI", ref]).strip())
    days = max((end - start).total_seconds() / 86400, 1) if start else None

    sizes = []
    stat = run(["git", "log", "--no-merges", "--shortstat", "--format=tformat:@@", rng]) or ""
    for chunk in stat.split("@@")[1:]:
        ins = re.search(r"(\d+) insertion", chunk)
        dels = re.search(r"(\d+) deletion", chunk)
        sizes.append((int(ins.group(1)) if ins else 0) + (int(dels.group(1)) if dels else 0))

    total_commits = run(["git", "rev-list", "--count", "--no-merges", ref])
    return {
        "period_from": prev or "начало репозитория",
        "commits_in_period": len(dates),
        "commits_total": int(total_commits) if total_commits else None,
        "commits_per_week": round(len(dates) / days * 7, 1) if days else None,
        "commit_size_avg": round(mean(sizes), 1) if sizes else None,
        "commit_size_median": median(sizes) if sizes else None,
    }


def loc_metric():
    lines = 0
    for path in glob.glob("src/**/*.cs", recursive=True):
        if os.sep + "obj" + os.sep in path or "/obj/" in path:
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            lines += sum(1 for line in f if line.strip())
    return {"loc_src": lines}


# ---------- 4. GitHub: PR, релизы, пайплайны ----------

def github_metrics():
    out = {"pr_open": None, "pr_merged": None, "pr_closed_unmerged": None,
           "releases_total": None, "ci_runs": None, "ci_success_rate": None, "ci_duration_avg_min": None}

    prs = run(["gh", "pr", "list", "--state", "all", "--limit", "500", "--json", "state"])
    if prs is not None:
        states = [p["state"] for p in json.loads(prs)]
        out.update(pr_open=states.count("OPEN"), pr_merged=states.count("MERGED"),
                   pr_closed_unmerged=states.count("CLOSED"))

    rel = run(["gh", "release", "list", "--limit", "100", "--json", "tagName"])
    if rel is not None:
        out["releases_total"] = len(json.loads(rel))

    runs = run(["gh", "run", "list", "--workflow", "ci.yml", "--limit", "200",
                "--json", "status,conclusion,startedAt,updatedAt"])
    if runs is not None:
        done = [r for r in json.loads(runs)
                if r["status"] == "completed" and r["conclusion"] not in ("skipped", "cancelled")]
        if done:
            ok = sum(r["conclusion"] == "success" for r in done)
            durations = [(parse_time(r["updatedAt"]) - parse_time(r["startedAt"])).total_seconds() / 60
                         for r in done if r.get("startedAt") and r.get("updatedAt")]
            out.update(ci_runs=len(done), ci_success_rate=round(100 * ok / len(done), 1),
                       ci_duration_avg_min=round(mean(durations), 1) if durations else None)
    return out


# ---------- Отчёт ----------

def fmt(value, suffix=""):
    return "н/д" if value is None else f"{value}{suffix}"


def to_markdown(m):
    groups = ", ".join(f"{k}: {v}" for k, v in m["warnings_by_group"].items()) or "—"
    rows = [
        ("Статический анализ", "Предупреждения анализаторов (всего)", fmt(m["warnings_total"])),
        ("Статический анализ", "Предупреждения по группам", groups),
        ("Статический анализ", "Цикломатическая сложность: максимум / среднее",
         f"{fmt(m['complexity_max'])} / {fmt(m['complexity_avg'])}"),
        ("Статический анализ", "Методов со сложностью > 10", fmt(m["methods_over_10"])),
        ("Тестирование", "Покрытие строк", fmt(m["line_coverage"], " %")),
        ("Тестирование", "Покрытие ветвлений", fmt(m["branch_coverage"], " %")),
        ("Тестирование", "Тесты: всего / пройдено / упало",
         f"{fmt(m['tests_total'])} / {fmt(m['tests_passed'])} / {fmt(m['tests_failed'])}"),
        ("Тестирование", "Время выполнения тестов", fmt(m["tests_duration_s"], " с")),
        ("Процесс", f"Коммитов за этап (с {m['period_from']})", fmt(m["commits_in_period"])),
        ("Процесс", "Частота коммитов", fmt(m["commits_per_week"], " в неделю")),
        ("Процесс", "Размер коммита: среднее / медиана, строк",
         f"{fmt(m['commit_size_avg'])} / {fmt(m['commit_size_median'])}"),
        ("Процесс", "Pull request: открыто / слито / закрыто без слияния",
         f"{fmt(m['pr_open'])} / {fmt(m['pr_merged'])} / {fmt(m['pr_closed_unmerged'])}"),
        ("Процесс", "Релизов (развёртываний) всего", fmt(m["releases_total"])),
        ("Процесс", "Строк кода в src (без пустых)", fmt(m["loc_src"])),
        ("CI/CD", "Доля успешных запусков CI", fmt(m["ci_success_rate"], " %")),
        ("CI/CD", "Среднее время выполнения CI", fmt(m["ci_duration_avg_min"], " мин")),
    ]
    lines = [f"## Метрики качества — {m['stage']} ({m['ref']}, {m['collected_at']})", "",
             "| Группа | Метрика | Значение |", "|---|---|---|"]
    lines += [f"| {g} | {n} | {v} |" for g, n, v in rows]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-log", default="build.log")
    ap.add_argument("--trx-dir", default="TestResults")
    ap.add_argument("--coverage", default="coveragereport/Cobertura.xml",
                    help="объединённый отчёт покрытия (ReportGenerator)")
    ap.add_argument("--out", default="metrics")
    args = ap.parse_args()

    ref = os.environ.get("GITHUB_REF_NAME") or (run(["git", "describe", "--tags", "--always"]) or "HEAD").strip()
    stage = os.environ.get("STAGE") or STAGES.get(ref, "промежуточный замер")
    raw = glob.glob(os.path.join(args.trx_dir, "**", "coverage.cobertura.xml"), recursive=True)

    metrics = {"stage": stage, "ref": ref,
               "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    metrics.update(linter_metrics(args.build_log))
    metrics.update(complexity_metrics(raw))
    metrics.update(coverage_metrics(args.coverage, raw))
    metrics.update(test_metrics(args.trx_dir))
    metrics.update(git_metrics("HEAD"))
    metrics.update(loc_metric())
    metrics.update(github_metrics())

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "metrics.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(metrics))
    print(to_markdown(metrics))


if __name__ == "__main__":
    main()
