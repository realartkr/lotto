"""동행복권에서 새 회차 당첨번호를 받아 data/draws.json과 WINNING_HISTORY.md를 갱신한다.

사용법: python3 scripts/update_history.py
"""
import datetime
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "draws.json")
DOC = os.path.join(ROOT, "WINNING_HISTORY.md")
API = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do?srchDir={}&srchCursorLtEpsd={}"
FIRST = datetime.date(2002, 12, 7)
KST = datetime.timezone(datetime.timedelta(hours=9))


def fetch(cursor, direction):
    """older: cursor 바로 아래 10개 회차 · latest: cursor보다 새 회차 (cursor는 실제 있는 회차여야 함)"""
    for attempt in range(10):
        try:
            req = urllib.request.Request(API.format(direction, cursor), headers={
                "User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))["data"]["list"]
        except Exception as e:
            if attempt == 9:
                raise RuntimeError(f"{direction} {cursor} 조회 실패: {e!r}")
            time.sleep(min(30 * (attempt + 1), 180))


def convert(x):
    ymd = x["ltRflYmd"]
    return {"round": x["ltEpsd"], "date": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}",
            "numbers": [x[f"tm{i}WnNo"] for i in range(1, 7)], "bonus": x["bnsWnNo"],
            "first_winners": x["rnk1WnNope"], "first_prize": x["rnk1WnAmt"]}


def load():
    if not os.path.exists(DATA):
        return {}
    return {d["round"]: d for d in json.load(open(DATA))}


def save(draws):
    with open(DATA, "w") as f:
        f.write("[\n" + ",\n".join(json.dumps(d, ensure_ascii=False) for d in draws) + "\n]\n")


def update(cache):
    """빠진 회차는 10개씩 거꾸로, 최신 회차는 마지막 회차 기준으로 받는다."""
    today = datetime.datetime.now(KST).date()
    for cursor in range(11, (today - FIRST).days // 7 + 2, 10):
        if all(n in cache for n in range(cursor - 10, cursor)):
            continue
        for x in fetch(cursor, "older"):
            cache[x["ltEpsd"]] = convert(x)
        time.sleep(3)
    while True:
        new = [x for x in fetch(max(cache), "latest") if x["ltEpsd"] not in cache]
        if not new:
            break
        for x in new:
            cache[x["ltEpsd"]] = convert(x)
        time.sleep(3)
    draws = [cache[n] for n in sorted(cache)]
    assert [d["round"] for d in draws] == list(range(1, len(draws) + 1)), "빠진 회차 있음"
    for d in draws:
        ns = d["numbers"]
        assert ns == sorted(ns) and len(set(ns)) == 6 and all(1 <= x <= 45 for x in ns), d
        assert 1 <= d["bonus"] <= 45 and d["bonus"] not in ns, d
        expected = FIRST + datetime.timedelta(days=7 * (d["round"] - 1))
        if d["date"] != expected.isoformat():
            print(f"참고: {d['round']}회 추첨일 {d['date']} (주간 계산값 {expected})", file=sys.stderr)
    return draws


HEADER = "| 회차 | 추첨일 | 당첨번호 | 보너스 | 1등 당첨자 | 1등 1인당 당첨금 |\n|:--:|:--:|:--|:--:|--:|--:|"


def row(d):
    w = d["first_winners"]
    winners = f"{w}명" if w else "0명 (이월)"
    prize = f"{d['first_prize']:,}원" if w else "-"
    return f"| {d['round']} | {d['date']} | {', '.join(map(str, d['numbers']))} | {d['bonus']} | {winners} | {prize} |"


def render(draws, today):
    last = draws[-1]
    years = sorted({d["date"][:4] for d in draws}, reverse=True)
    out = [
        "# 🏆 로또 6/45 역대 당첨번호",
        "",
        "> 출처: 동행복권 (dhlottery.co.kr) 공식 사이트",
        f"> 기간: 1회 ({draws[0]['date']}) ~ {last['round']}회 ({last['date']}) · 총 **{len(draws):,}회**",
        f"> 마지막 갱신: {today} · 매주 일요일 오후 3시(한국 시간) 자동 갱신",
        "",
        "---",
        "",
        "## 📌 최신 회차",
        "",
        HEADER,
        row(last),
        "",
        "## 📅 연도별 바로가기",
        "",
        " · ".join(f"[{y}](#{y}년)" for y in years),
        "",
        "---",
    ]
    for y in years:
        out += ["", f"## {y}년", "", HEADER]
        out += [row(d) for d in reversed(draws) if d["date"][:4] == y]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    cache = load()
    before = max(cache, default=0)
    draws = update(cache)
    save(draws)
    open(DOC, "w").write(render(draws, datetime.datetime.now(KST).date().isoformat()))
    added = draws[-1]["round"] - before
    print(f"{before}회 → {draws[-1]['round']}회 (새 회차 {added}개)")
