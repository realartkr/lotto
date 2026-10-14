"""FILTERS.md의 ✅ 적용 필터. FILTERS.md를 바꾸면 이 파일도 같이 바꾼다.

각 필터의 check는 (N, 6) 정수 배열(오름차순 번호)을 받아 통과 여부 (N,) bool 배열을 돌려주고,
detail은 번호 6개 한 조합을 받아 결과 설명 문자열을 돌려준다.
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


FILTERS = [
    {"no": 1, "name": "홀짝 비율", "check": odd_even, "detail": odd_even_detail},
    {"no": 2, "name": "9궁도", "check": nine_palace, "detail": nine_palace_detail},
    {"no": 3, "name": "용지 가로·세로", "check": slip, "detail": slip_detail},
    {"no": 4, "name": "연속번호", "check": no_quad_run, "detail": no_quad_run_detail},
]


# FILTERS.md 99번 보류 필터. 생성에는 쓰지 않고 통계만 참고로 낸다.
def sum_range(c):
    s = c.sum(axis=1)
    return (s >= 95) & (s <= 180)


def zones(c):
    return _max_per_group((c - 1) // 10, 5) <= 3


def last_digit(c):
    return _max_per_group(c % 10, 10) <= 2


RESERVE = [
    {"no": "99-1", "name": "합계 범위 (95 ~ 180)", "check": sum_range},
    {"no": "99-2", "name": "구간 분포 (구간당 최대 3개)", "check": zones},
    {"no": "99-3", "name": "끝자리 중복 (최대 2개)", "check": last_digit},
]


def all_combinations():
    flat = chain.from_iterable(combinations(range(1, 46), 6))
    return np.fromiter(flat, dtype=np.int16, count=TOTAL * 6).reshape(TOTAL, 6)
