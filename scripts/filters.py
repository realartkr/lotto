"""FILTERS.md의 ✅ 적용 필터. FILTERS.md를 바꾸면 이 파일도 같이 바꾼다.

각 필터의 check는 (N, 6) 정수 배열(오름차순 번호)을 받아 통과 여부 (N,) bool 배열을 돌려주고,
detail은 번호 6개 한 조합을 받아 결과 설명 문자열을 돌려준다.
uses_ctx가 있는 필터는 지난 회차 기록(ctx: prev 직전 회차 번호, gaps 번호별 연속으로 안 나온 회차 수,
t 회차 순번과 seen_keys/seen_first 역대 당첨 조합)도 함께 받는다. ctx는 contexts()로 만들고,
한 회차분은 row_ctx()로 꺼내며, 호출은 check()/detail()로 한다.
"""
from collections import Counter
from itertools import chain, combinations

import numpy as np

TOTAL = 8145060  # 45C6


def _max_per_group(groups, k):
    m = np.zeros(len(groups), dtype=np.int8)
    for g in range(k):
        m = np.maximum(m, (groups == g).sum(axis=1).astype(np.int8))
    return m


def _most(keys, label):
    """가장 많이 몰린 그룹과 그 번호들"""
    key, n = Counter(keys.values()).most_common(1)[0]
    members = "·".join(str(x) for x, k in keys.items() if k == key)
    return n, f"{label(key)}: {members}"


def odd_even(c):
    odd = (c % 2).sum(axis=1)
    return (odd >= 2) & (odd <= 4)


def odd_even_detail(ns):
    odd = sum(x % 2 for x in ns)
    return f"홀:짝 = {odd}:{6 - odd}"


def nine_palace(c):
    return _max_per_group(c % 9, 9) <= 2


def nine_palace_detail(ns):
    n, where = _most({x: (x - 1) % 9 + 1 for x in ns}, lambda k: f"{k}궁")
    return f"한 궁 최대 {n}개" + (f" ({where})" if n > 1 else "")


def slip(c):
    return (_max_per_group((c - 1) // 7, 7) <= 3) & (_max_per_group((c - 1) % 7, 7) <= 2)


def slip_detail(ns):
    r, rw = _most({x: (x - 1) // 7 + 1 for x in ns}, lambda k: f"{k}행")
    c, cw = _most({x: (x - 1) % 7 + 1 for x in ns}, lambda k: f"{k}열")
    return f"가로 최대 {r}개" + (f" ({rw})" if r > 1 else "") + f" · 세로 최대 {c}개" + (f" ({cw})" if c > 1 else "")


def no_quad_run(c):
    step = np.diff(c, axis=1) == 1
    return ~(step[:, :-2] & step[:, 1:-1] & step[:, 2:]).any(axis=1)


def no_quad_run_detail(ns):
    best, run = [ns[0]], [ns[0]]
    for x in ns[1:]:
        run = run + [x] if x == run[-1] + 1 else [x]
        if len(run) > len(best):
            best = run
    return f"가장 긴 연속 {len(best)}개 ({'-'.join(map(str, best))})" if len(best) > 1 else "연속 없음"


def carryover(c, ctx):
    """ctx["prev"]가 (6,)이면 모든 행에 같은 직전 회차, (N, 6)이면 행마다 다른 직전 회차"""
    prev = np.asarray(ctx["prev"])
    if prev.ndim == 1:
        mask = np.zeros(46, bool)
        mask[prev] = True
        hits = mask[c].sum(axis=1)
    else:
        hits = (c[:, :, None] == prev[:, None, :]).any(axis=2).sum(axis=1)
    return hits <= 2


def carryover_detail(ns, ctx):
    same = [x for x in ns if x in ctx["prev"]]
    return f"직전 회차 번호 {len(same)}개" + (f" ({'·'.join(map(str, same))})" if same else "")


def _neighbor_mask(prev):
    """prev (N, 6) → (N, 46) 이웃수 표시. prev가 0인 행(직전 회차 없음)은 이웃수 없음"""
    n = len(prev)
    m = np.zeros((n, 47), bool)
    r, p = np.repeat(np.arange(n), 6), prev.ravel().astype(np.int64)
    valid = p > 0
    for s in (-1, 1):
        q = p + s
        ok = valid & (q >= 1) & (q <= 45)
        m[r[ok], q[ok]] = True
    m[r[valid], p[valid]] = False
    return m[:, :46]


def neighbors(c, ctx):
    prev = np.asarray(ctx["prev"])
    if prev.ndim == 1:
        hits = _neighbor_mask(prev[None])[0][c].sum(axis=1)
    else:
        hits = np.take_along_axis(_neighbor_mask(prev), c.astype(np.int64), axis=1).sum(axis=1)
    return hits <= 2


def neighbors_detail(ns, ctx):
    mask = _neighbor_mask(np.asarray(ctx["prev"])[None])[0]
    nb = [x for x in ns if mask[x]]
    return f"이웃수 {len(nb)}개" + (f" ({'·'.join(map(str, nb))})" if nb else "")


ABSENT = 15  # 이 회차 수 이상 연속으로 안 나온 번호를 "장기 미출현"으로 본다


def long_absent(c, ctx):
    """ctx["gaps"]가 (46,)이면 모든 행에 같은 기준, (N, 46)이면 행마다 다른 기준"""
    cold = np.asarray(ctx["gaps"]) >= ABSENT
    if cold.ndim == 1:
        hits = cold[c].sum(axis=1)
    else:
        hits = np.take_along_axis(cold, c.astype(np.int64), axis=1).sum(axis=1)
    return hits <= 2


def long_absent_detail(ns, ctx):
    cold = [x for x in ns if ctx["gaps"][x] >= ABSENT]
    return f"{ABSENT}회 이상 쉰 번호 {len(cold)}개" + (f" ({'·'.join(map(str, cold))})" if cold else "")


PRIMES = [x for x in range(2, 46) if all(x % k for k in range(2, int(x ** 0.5) + 1))]
_PRIME = np.isin(np.arange(46), PRIMES)


def primes(c):
    n = _PRIME[c].sum(axis=1)
    return (n >= 1) & (n <= 3)


def primes_detail(ns):
    ps = [x for x in ns if x in PRIMES]
    return f"소수 {len(ps)}개" + (f" ({'·'.join(map(str, ps))})" if ps else "")


def last_digit(c):
    return _max_per_group(c % 10, 10) <= 2


def last_digit_detail(ns):
    n, where = _most({x: x % 10 for x in ns}, lambda k: f"끝수 {k}")
    return f"같은 끝수 최대 {n}개" + (f" ({where})" if n > 1 else "")


def combo_key(c):
    """번호 6개 → 하나의 정수 (번호마다 비트 하나)"""
    return (np.int64(1) << np.asarray(c, dtype=np.int64)).sum(axis=-1)


def _drawn_before(c, ctx):
    q = combo_key(c)
    keys, first = ctx["seen_keys"], ctx["seen_first"]
    i = np.clip(np.searchsorted(keys, q), 0, len(keys) - 1)
    return (keys[i] == q) & (first[i] < ctx["t"])


def new_combo(c, ctx):
    return ~_drawn_before(c, ctx)


def new_combo_detail(ns, ctx):
    return "이전에 나온 적 없는 조합" if new_combo(np.array([ns]), ctx)[0] else "이전 당첨 조합과 같음"


FILTERS = [
    {"no": 1, "name": "역대 당첨 조합 제외", "check": new_combo, "detail": new_combo_detail, "uses_ctx": True},
    {"no": 2, "name": "연속번호", "check": no_quad_run, "detail": no_quad_run_detail},
    {"no": 3, "name": "장기 미출현 번호", "check": long_absent, "detail": long_absent_detail, "uses_ctx": True},
    {"no": 4, "name": "직전 회차 번호", "check": carryover, "detail": carryover_detail, "uses_ctx": True},
    {"no": 5, "name": "동일 끝수", "check": last_digit, "detail": last_digit_detail},
    {"no": 6, "name": "9궁도", "check": nine_palace, "detail": nine_palace_detail},
    {"no": 7, "name": "이웃수", "check": neighbors, "detail": neighbors_detail, "uses_ctx": True},
    {"no": 8, "name": "소수 개수", "check": primes, "detail": primes_detail},
    {"no": 9, "name": "홀짝 비율", "check": odd_even, "detail": odd_even_detail},
    {"no": 10, "name": "용지 가로·세로", "check": slip, "detail": slip_detail},
]


def check(f, c, ctx):
    return f["check"](c, ctx) if f.get("uses_ctx") else f["check"](c)


def detail(f, ns, ctx):
    return f["detail"](ns, ctx) if f.get("uses_ctx") else f["detail"](ns)


def contexts(hist):
    """hist: (N, 6) 역대 당첨번호. 각 회차 직전 시점의 ctx (prev (N, 6), gaps (N, 46))와
    다음 회차용 ctx (prev (6,), gaps (46,))를 돌려준다. 아직 한 번도 안 나온 번호는 1회부터 센다."""
    n = len(hist)
    last = np.full(46, -1)
    prev = np.zeros((n, 6), np.int16)
    gaps = np.zeros((n, 46), np.int32)
    for t in range(n):
        prev[t] = hist[t - 1] if t else 0
        gaps[t] = t - last - 1
        last[hist[t]] = t
    keys = combo_key(hist)
    seen_keys, first = np.unique(keys, return_index=True)
    seen = {"seen_keys": seen_keys, "seen_first": first}
    return ({"prev": prev, "gaps": gaps, "t": np.arange(n), **seen},
            {"prev": hist[-1], "gaps": n - last - 1, "t": n, **seen})


def row_ctx(ctx, i):
    """contexts()의 회차별 ctx에서 i번째 회차 직전 시점만 꺼낸다"""
    return {k: v if k.startswith("seen_") else v[i] for k, v in ctx.items()}


# FILTERS.md 99번 보류 필터. 생성에는 쓰지 않고 통계만 참고로 낸다.
def sum_range(c):
    s = c.sum(axis=1)
    return (s >= 95) & (s <= 180)


def sum_range_detail(ns):
    return f"합계 {sum(ns)}"


def tens(c):
    return _max_per_group(c // 10, 5) <= 3


def tens_detail(ns):
    n, where = _most({x: x // 10 for x in ns}, lambda k: f"{k}0번대" if k else "1~9")
    return f"같은 십의 자리 최대 {n}개" + (f" ({where})" if n > 1 else "")


RESERVE = [
    {"no": "99-1", "name": "합계 범위 (95 ~ 180)", "check": sum_range, "detail": sum_range_detail},
    {"no": "99-2", "name": "십의 자리 (같은 십의 자리 최대 3개)", "check": tens, "detail": tens_detail},
]


def all_combinations():
    flat = chain.from_iterable(combinations(range(1, 46), 6))
    return np.fromiter(flat, dtype=np.int16, count=TOTAL * 6).reshape(TOTAL, 6)
