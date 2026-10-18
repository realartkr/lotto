"""적용 필터별로 전체 조합과 역대 당첨번호를 얼마나 걸러내는지 계산해 FILTER_STATS.md를 만든다.

data/draws.json을 먼저 갱신(update_history.py)한 뒤 실행한다.
사용법: python3 scripts/filter_stats.py
"""
import datetime
import json
import math
import os

import numpy as np

from filters import FILTERS, RESERVE, TOTAL, all_combinations, check, contexts, detail, row_ctx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWS = os.path.join(ROOT, "data", "draws.json")
LOG = os.path.join(ROOT, "data", "stats_history.json")
DOC = os.path.join(ROOT, "FILTER_STATS.md")
KST = datetime.timezone(datetime.timedelta(hours=9))


def pct(n, total):
    return f"{n / total * 100:.2f}%"


def gap(combo_rate, hist_rate):
    """첫째 − 둘째 (%p). 걸러냄은 (조합, 당첨번호), 남음은 (당첨번호, 조합) 순으로 넘겨 +가 좋은 쪽이 되게 한다.
    좋음(+)은 🟩, 나쁨(−)은 🟥를 붙인다."""
    v = round((combo_rate - hist_rate) * 100, 2)
    return f"{'🟩' if v > 0 else '🟥' if v < 0 else '⬜'} {v:+.2f}%p"


def noise(rate, n):
    """무작위 추첨이어도 95% 확률로 생길 수 있는 차이"""
    return f"±{1.96 * math.sqrt(rate * (1 - rate) / n) * 100:.2f}%p"


def mark(ok):
    return "⭕ 통과" if ok else "❌ 탈락"


SAMPLE_PER_DRAW = 1000  # 지난 기록을 쓰는 필터의 조합 비율을 회차마다 무작위 조합 이만큼으로 잰다


def compute(draws):
    """조합 비율은 당첨번호와 같은 기준(각 회차 직전 시점)으로 잰다.
    지난 기록을 안 쓰는 필터는 전체 조합으로 정확히, 쓰는 필터는 회차마다 무작위 조합을 뽑아 평균을 낸다.
    다음 회차 생성에 실제로 남는 조합 수(next_cum)는 따로 전체 조합으로 센다."""
    combos = all_combinations()
    hist = np.array([d["numbers"] for d in draws], dtype=np.int16)
    ctx_h, ctx_c = contexts(hist)
    n = len(hist)
    week = np.repeat(np.arange(n), SAMPLE_PER_DRAW)
    sample = combos[np.random.default_rng(0).integers(0, len(combos), len(week))]
    ctx_s = {k: v if k.startswith("seen_") else v[week] for k, v in ctx_h.items()}
    rows, cum_n, cum_s, cum_h = [], np.ones(len(combos), bool), np.ones(len(sample), bool), np.ones(n, bool)
    exact = True  # 지금까지 적용한 필터가 모두 지난 기록을 안 쓰면 전체 조합으로 센 정확한 값을 쓴다
    for f in FILTERS:
        pn, ph = check(f, combos, ctx_c), check(f, hist, ctx_h)
        ps = check(f, sample, ctx_s)
        exact &= not f.get("uses_ctx")
        cum_n &= pn
        cum_s &= ps
        cum_h &= ph
        rows.append({"filter": f, "hist_pass": int(ph.sum()), "hist_cum": int(cum_h.sum()),
                     "combo_rate": float(ps.mean()) if f.get("uses_ctx") else float(pn.mean()),
                     "combo_count": None if f.get("uses_ctx") else int(pn.sum()),
                     "combo_cum_rate": float(cum_n.mean()) if exact else float(cum_s.mean()),
                     "next_cum": int(cum_n.sum())})
    reserve = []
    for f in RESERVE:
        pn = f["check"](combos)
        reserve.append({"filter": f, "combo_rate": float(pn.mean()), "combo_count": int(pn.sum()),
                        "hist_pass": int(f["check"](hist).sum())})
    return rows, reserve


STAT_HEAD = [
    "| # | 필터 | 전체 조합 | 역대 당첨번호 ({nh:,}회) | 차이 | 우연 범위 |",
    "|:-:|------|------:|------:|------:|------:|",
]


def stat_row(r, nh):
    f, rc, dh = r["filter"], 1 - r["combo_rate"], nh - r["hist_pass"]
    shown = (f"{rc * 100:.2f}% ({TOTAL - r['combo_count']:,}개)" if r["combo_count"] is not None
             else f"{rc * 100:.2f}% (역대 평균)")
    return (f"| {f['no']} | {f['name']} | {shown} | {pct(dh, nh)} ({dh:,}회) "
            f"| {gap(rc, dh / nh)} | {noise(rc, nh)} |")


def render(draws, rows, reserve, log, today):
    last, nh = draws[-1], len(draws)
    ns = last["numbers"]
    ctx_h, _ = contexts(np.array([d["numbers"] for d in draws]))
    ctx = row_ctx(ctx_h, -1)
    latest = [(f, bool(check(f, np.array([ns]), ctx)[0])) for f in FILTERS]
    names = " · ".join(f"{f['no']} {f['name']}" for f in FILTERS)
    span = f"1 ~ {FILTERS[-1]['no']}"
    head = [h.format(total=TOTAL, nh=nh) for h in STAT_HEAD]
    out = [
        "# 📊 필터 통계",
        "",
        f"> 기준: {last['round']}회 ({last['date']}) · 마지막 갱신: {today}",
        f"> 적용 필터: [FILTERS.md](FILTERS.md)의 ✅ {span}번 ({names})",
        "> 매주 일요일 오후 3시(한국 시간) 당첨번호 갱신 후 다시 계산합니다.",
        "",
        "## 📖 용어 정리",
        "",
        "**차이** = 전체 조합에서 걸러낸 비율 − 역대 당첨번호에서 걸러낸 비율",
        "",
        "- 🟩 **+ 는 좋음**: 당첨번호는 덜 버리고 후보 조합만 더 줄였다는 뜻",
        "- 🟥 **− 는 나쁨**: 후보 조합보다 당첨번호를 더 많이 버렸다는 뜻",
        "",
        "**우연 범위** = 무작위 추첨이어도 95% 확률로 생길 수 있는 차이의 크기",
        "",
        "- 좋고 나쁨이 아니라 **차이를 재는 잣대**입니다. 회차가 쌓일수록, 필터가 적게 거를수록 작아집니다.",
        "- **±는 양쪽**을 뜻합니다. ±2.00%p면 −2.00%p ~ +2.00%p 구간입니다.",
        "",
        "| 차이가 어디에 있나 | 뜻 |",
        "|------|------|",
        "| + 범위보다 큼 | 🟩 의미 있게 좋음 |",
        "| − 범위 ~ + 범위 사이 | ➖ 우연 범위 안 (좋다/나쁘다 말하기 어려움) |",
        "| − 범위보다 작음 | 🟥 의미 있게 나쁨 |",
        "",
        "---",
        "",
        f"## 🎯 이번 회차 ({last['round']}회)",
        "",
        f"**{', '.join(map(str, ns))}** + 보너스 {last['bonus']}",
        "",
        "| # | 필터 | 결과 | 내용 | 역대 통과 |",
        "|:-:|------|:----:|------|------:|",
        "| | **1군 · 적용 필터** | | | |",
    ]
    hist_pass = {r["filter"]["name"]: r["hist_pass"] for r in rows}
    for f, ok in sorted(latest, key=lambda x: (-hist_pass[x[0]["name"]], x[0]["no"])):
        hp = hist_pass[f["name"]]
        out.append(f"| {f['no']} | {f['name']} | {mark(ok)} | {detail(f, ns, ctx)} | {hp:,}회 ({pct(hp, nh)}) |")
    out.append("| | **2군 · 99번 보류 필터 (생성 미적용)** | | | |")
    for r in sorted(reserve, key=lambda r: -r["hist_pass"]):
        f, hp = r["filter"], r["hist_pass"]
        ok = bool(f["check"](np.array([ns]))[0])
        out.append(f"| {f['no']} | {f['name']} | {mark(ok)} | {f['detail'](ns)} | {hp:,}회 ({pct(hp, nh)}) |")
    out += [f"| | **1군 {span} 모두** | **{mark(all(ok for _, ok in latest))}** | "
            f"| **{rows[-1]['hist_cum']:,}회 ({pct(rows[-1]['hist_cum'], nh)})** |",
            "",
            f"> 역대 통과 = 1 ~ {nh:,}회 당첨번호 중 그 필터를 통과한 횟수. 군마다 많이 통과한 필터부터 적었습니다.",
            "> 2군 필터는 생성에 쓰지 않고 수치만 지켜봅니다. 1군으로 올리려면 FILTERS.md에서 번호를 붙여 위로 옮깁니다.",
            ""]

    out += [
        "## 🧮 필터별 걸러내는 비율",
        "",
        "> 차이 · 우연 범위 뜻은 맨 위 **📖 용어 정리** 참고",
        "",
        "### 필터 하나만 적용했을 때 걸러내는 비율",
        "",
        *head,
        *(stat_row(r, nh) for r in rows),
        "",
        "### 1번부터 차례로 적용했을 때 남는 비율",
        "",
        "| 적용 | 전체 조합 남음 | 역대 당첨번호 남음 | 차이 | 우연 범위 |",
        "|------|------:|------:|------:|------:|",
    ]
    for i, r in enumerate(rows):
        label = " + ".join(str(x["filter"]["no"]) for x in rows[: i + 1])
        rc, rh = r["combo_cum_rate"], r["hist_cum"] / nh
        out.append(f"| {label} | {rc * 100:.2f}% | {r['hist_cum']:,}회 ({pct(r['hist_cum'], nh)}) "
                   f"| {gap(rh, rc)} | {noise(rc, nh)} |")
    out += [
        "",
        f"> **다음 회차({last['round'] + 1}회) 생성 기준** {span}번을 모두 통과하는 조합: "
        f"**{rows[-1]['next_cum']:,}개 ({pct(rows[-1]['next_cum'], TOTAL)})**",
        "> 역대 당첨번호 비율은 회차가 쌓이며 조금씩 바뀝니다.",
        *([f"> 지난 회차 기록을 쓰는 필터({', '.join(str(f['no']) + '번' for f in FILTERS if f.get('uses_ctx'))})는 매주 기준이 바뀌어서, "
           f"표의 전체 조합 비율은 역대 각 회차 직전 시점 기준으로 잰 평균입니다 (회차마다 무작위 조합 {SAMPLE_PER_DRAW:,}개). "
           f"그래야 역대 당첨번호와 같은 기준으로 비교됩니다."]
          if any(f.get("uses_ctx") for f in FILTERS) else []),
        "",
        "### 🗂 99번 보류 필터 (참고 · 생성에는 미적용)",
        "",
        *head,
        *(stat_row(r, nh) for r in reserve),
        "",
        "---",
        "",
        "## 📝 주간 기록",
        "",
        "| 갱신일 | 회차 | 당첨번호 | " + " | ".join(f"{f['no']} {f['name']}" for f in FILTERS)
        + f" | 역대 {span} 통과율 | 차이 |",
        "|:--:|:--:|------|" + ":--:|" * len(FILTERS) + "------:|------:|",
    ]
    for e in reversed(log):
        marks = " | ".join({True: "⭕", False: "❌"}.get(e["results"].get(f["name"]), "-") for f in FILTERS)
        rh = e["hist_pass"] / e["hist_total"]
        base = e.get("combo_rate", e["combo_pass"] / TOTAL if "combo_pass" in e else None)
        diff = gap(rh, base) if base is not None else "-"
        out.append(f"| {e['updated']} | {e['round']} | {', '.join(map(str, e['numbers']))} | {marks} "
                   f"| {pct(e['hist_pass'], e['hist_total'])} ({e['hist_pass']:,}/{e['hist_total']:,}) | {diff} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    draws = json.load(open(DRAWS))
    rows, reserve = compute(draws)
    today = datetime.datetime.now(KST).date().isoformat()
    last = draws[-1]
    ctx_h, _ = contexts(np.array([d["numbers"] for d in draws]))
    ctx_last = row_ctx(ctx_h, -1)
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    log = [e for e in log if e["round"] != last["round"]]
    log.append({"updated": today, "round": last["round"], "numbers": last["numbers"],
                "results": {f["name"]: bool(check(f, np.array([last["numbers"]]), ctx_last)[0]) for f in FILTERS},
                "hist_pass": rows[-1]["hist_cum"], "hist_total": len(draws), "combo_rate": rows[-1]["combo_cum_rate"]})
    with open(LOG, "w") as fp:
        fp.write("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in log) + "\n]\n")
    open(DOC, "w").write(render(draws, rows, reserve, log, today))
    print(f"{last['round']}회 기준 통계 갱신 · 1~{FILTERS[-1]['no']} 모두 통과: 조합 {rows[-1]['combo_cum_rate'] * 100:.2f}% "
          f"(다음 회차 {pct(rows[-1]['next_cum'], TOTAL)}), "
          f"역대 {pct(rows[-1]['hist_cum'], len(draws))}")
