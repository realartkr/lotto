"""적용 필터별로 전체 조합과 역대 당첨번호를 얼마나 걸러내는지 계산해 FILTER_STATS.md를 만든다.

data/draws.json을 먼저 갱신(update_history.py)한 뒤 실행한다.
사용법: python3 scripts/filter_stats.py
"""
import datetime
import json
import os

import numpy as np

from filters import FILTERS, TOTAL, all_combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWS = os.path.join(ROOT, "data", "draws.json")
LOG = os.path.join(ROOT, "data", "stats_history.json")
DOC = os.path.join(ROOT, "FILTER_STATS.md")
KST = datetime.timezone(datetime.timedelta(hours=9))


def pct(n, total):
    return f"{n / total * 100:.2f}%"


def mark(ok):
    return "⭕ 통과" if ok else "❌ 탈락"


def compute(draws):
    combos = all_combinations()
    hist = np.array([d["numbers"] for d in draws], dtype=np.int16)
    rows, cum_c, cum_h = [], np.ones(len(combos), bool), np.ones(len(hist), bool)
    for f in FILTERS:
        pc, ph = f["check"](combos), f["check"](hist)
        cum_c &= pc
        cum_h &= ph
        rows.append({"filter": f, "combo_pass": int(pc.sum()), "hist_pass": int(ph.sum()),
                     "combo_cum": int(cum_c.sum()), "hist_cum": int(cum_h.sum())})
    return rows


def render(draws, rows, log, today):
    last, nh = draws[-1], len(draws)
    ns = last["numbers"]
    latest = [(f, bool(f["check"](np.array([ns]))[0])) for f in FILTERS]
    names = " · ".join(f"{f['no']} {f['name']}" for f in FILTERS)
    span = f"1 ~ {FILTERS[-1]['no']}"
    out = [
        "# 📊 필터 통계",
        "",
        f"> 기준: {last['round']}회 ({last['date']}) · 마지막 갱신: {today}",
        f"> 적용 필터: [FILTERS.md](FILTERS.md)의 ✅ {span}번 ({names})",
        "> 매주 일요일 오후 3시(한국 시간) 당첨번호 갱신 후 다시 계산합니다.",
        "",
        "---",
        "",
        f"## 🎯 이번 회차 ({last['round']}회)",
        "",
        f"**{', '.join(map(str, ns))}** + 보너스 {last['bonus']}",
        "",
        "| # | 필터 | 결과 | 내용 |",
        "|:-:|------|:----:|------|",
    ]
    out += [f"| {f['no']} | {f['name']} | {mark(ok)} | {f['detail'](ns)} |" for f, ok in latest]
    out += [f"| | **{span} 모두** | **{mark(all(ok for _, ok in latest))}** | |", ""]

    out += [
        "## 🧮 필터별 걸러내는 비율",
        "",
        "### 필터 하나만 적용했을 때 걸러내는 비율",
        "",
        f"| # | 필터 | 전체 조합 ({TOTAL:,}개) | 역대 당첨번호 ({nh:,}회) |",
        "|:-:|------|------:|------:|",
    ]
    for r in rows:
        f, dc, dh = r["filter"], TOTAL - r["combo_pass"], nh - r["hist_pass"]
        out.append(f"| {f['no']} | {f['name']} | {pct(dc, TOTAL)} ({dc:,}개) | {pct(dh, nh)} ({dh:,}회) |")
    out += [
        "",
        "### 1번부터 차례로 적용했을 때 남는 비율",
        "",
        "| 적용 | 전체 조합 남음 | 역대 당첨번호 남음 |",
        "|------|------:|------:|",
    ]
    for i, r in enumerate(rows):
        label = " + ".join(str(x["filter"]["no"]) for x in rows[: i + 1])
        out.append(f"| {label} | {r['combo_cum']:,}개 ({pct(r['combo_cum'], TOTAL)}) "
                   f"| {r['hist_cum']:,}회 ({pct(r['hist_cum'], nh)}) |")
    out += [
        "",
        "> 전체 조합 비율은 필터를 바꾸지 않는 한 매주 같습니다. 역대 당첨번호 비율은 회차가 쌓이며 조금씩 바뀝니다.",
        "",
        "---",
        "",
        "## 📝 주간 기록",
        "",
        "| 갱신일 | 회차 | 당첨번호 | " + " | ".join(f"{f['no']} {f['name']}" for f in FILTERS) + f" | 역대 {span} 통과율 |",
        "|:--:|:--:|------|" + ":--:|" * len(FILTERS) + "------:|",
    ]
    for e in reversed(log):
        marks = " | ".join({True: "⭕", False: "❌"}.get(e["results"].get(f["name"]), "-") for f in FILTERS)
        out.append(f"| {e['updated']} | {e['round']} | {', '.join(map(str, e['numbers']))} | {marks} "
                   f"| {pct(e['hist_pass'], e['hist_total'])} ({e['hist_pass']:,}/{e['hist_total']:,}) |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    draws = json.load(open(DRAWS))
    rows = compute(draws)
    today = datetime.datetime.now(KST).date().isoformat()
    last = draws[-1]
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    log = [e for e in log if e["round"] != last["round"]]
    log.append({"updated": today, "round": last["round"], "numbers": last["numbers"],
                "results": {f["name"]: bool(f["check"](np.array([last["numbers"]]))[0]) for f in FILTERS},
                "hist_pass": rows[-1]["hist_cum"], "hist_total": len(draws)})
    with open(LOG, "w") as fp:
        fp.write("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in log) + "\n]\n")
    open(DOC, "w").write(render(draws, rows, log, today))
    print(f"{last['round']}회 기준 통계 갱신 · 1~{FILTERS[-1]['no']} 모두 통과: 조합 {pct(rows[-1]['combo_cum'], TOTAL)}, "
          f"역대 {pct(rows[-1]['hist_cum'], len(draws))}")
