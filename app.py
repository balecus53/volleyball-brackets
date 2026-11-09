import itertools
import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

# ================================================================ DATA
SCHOOLS = [  # name, teams, approx. players
    ("SB", ["A", "B"], 25),
    ("USC", ["A", "B", "C"], 25),
    ("Biola", ["A", "B"], 16),
    ("UCLA", ["A", "B", "C"], 35),
    ("UCI", ["A", "B", "C"], 44),
    ("Pepp", ["A", "B"], 25),
    ("SD", ["A", "B", "C"], 27),
    ("Riverside", ["A", "B", "C"], 35),
]
BRACKET_TIERS = ["B", "C"]  # A teams are not in this playoff
COURTS = 2
SEEDING_GAMES_PER_SCHOOL = 3


def default_team_table():
    rows = []
    for school, tiers, players in SCHOOLS:
        for t in tiers:
            if t in BRACKET_TIERS:
                rows.append({"Team": f"{school} {t}", "School": school, "Tier": t,
                             "Est. players": round(players / len(tiers))})
    return pd.DataFrame(rows)


# ================================================================ SEEDING GAMES
def seeding_schedule(n, games=SEEDING_GAMES_PER_SCHOOL, trials=20000):
    """Every school plays `games` seeding games against different schools, 2 courts,
    and no school plays in two consecutive slots. Prefers a connected set of opponents
    (so results are comparable), then the fewest slots. Returns list of slots of (i, j)."""
    rng = random.Random(11)
    best = None
    for _ in range(trials):
        left, played, slots, prev = [games] * n, set(), [], set()
        while sum(left) > 0 and len(slots) < 16:
            avail = [s for s in range(n) if left[s] > 0 and s not in prev]
            cand = [p for p in itertools.combinations(avail, 2) if p not in played]
            rng.shuffle(cand)
            cand.sort(key=lambda p: -(left[p[0]] + left[p[1]]) + rng.random() * 1.5)
            ch, used = [], set()
            for a, b in cand:
                if len(ch) == COURTS or (len(ch) == 1 and rng.random() < 0.35):
                    break
                if a in used or b in used:
                    continue
                ch.append((a, b))
                used |= {a, b}
            slots.append(ch)
            for a, b in ch:
                left[a] -= 1
                left[b] -= 1
                played.add((a, b))
            prev = used
        if sum(left) > 0:
            continue
        par = list(range(n))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for a, b in played:
            par[find(a)] = find(b)
        connected = len({find(x) for x in range(n)}) == 1
        score = (0 if connected else 1, len(slots))
        if best is None or score < best[0]:
            best = (score, slots)
    return best[1]


# ================================================================ BRACKET LOGIC
def seed_order(n):
    order = [1]
    while len(order) < n:
        size = len(order) * 2
        order = [x for s in order for x in (s, size + 1 - s)]
    return order


def arrange(teams, school_of, avoid=True):
    """Place seeded teams in a power-of-2 bracket. Top seeds keep byes. If `avoid`,
    teams from the same school are moved so they can't meet before the final."""
    n = len(teams)
    size = 1
    while size < n:
        size *= 2
    total = size.bit_length() - 1
    order = seed_order(size)
    occupied = [i for i in range(size) if order[i] <= n]
    init = [order[i] - 1 for i in occupied]

    def cost(perm):
        dev = sum(abs(perm[k] + 1 - order[occupied[k]]) for k in range(n))
        coll = 0
        if avoid:
            for k in range(n):
                for l in range(k + 1, n):
                    if school_of[teams[perm[k]]] == school_of[teams[perm[l]]]:
                        r = (occupied[k] ^ occupied[l]).bit_length() - 1
                        coll += 1000 * (total - r)
        return coll + dev

    rng = random.Random(1)
    best, best_c = init[:], cost(init)
    starts = [init] + [rng.sample(init, n) for _ in range(40 if avoid else 0)]
    for perm in starts:
        perm = perm[:]
        c = cost(perm)
        improved = True
        while improved:
            improved = False
            for k in range(n):
                for l in range(k + 1, n):
                    perm[k], perm[l] = perm[l], perm[k]
                    c2 = cost(perm)
                    if c2 < c:
                        c, improved = c2, True
                    else:
                        perm[k], perm[l] = perm[l], perm[k]
        if c < best_c:
            best, best_c = perm[:], c
    slots = [None] * size
    for k, pos in enumerate(occupied):
        slots[pos] = teams[best[k]]
    return slots, total


def build_matches(slots, total):
    """Returns matches {(round, idx): {'a': out, 'b': out}} and the final output.
    An 'out' is ('team', name) or ('match', id). Byes collapse automatically."""
    outs = [("team", t) if t else None for t in slots]
    matches = {}
    for r in range(total):
        new = []
        for m in range(len(outs) // 2):
            a, b = outs[2 * m], outs[2 * m + 1]
            if a is None or b is None:
                new.append(a or b)
            else:
                matches[(r, m)] = {"a": a, "b": b}
                new.append(("match", (r, m)))
        outs = new
    return matches, outs[0]


def make_schedule(matches, school_of, picks, locked, prev_schools=(), trials=600):
    """Playoff scheduler: 2 courts per slot; no school plays in two consecutive slots
    (including the last seeding slot) or twice in one slot. For games whose teams aren't
    known yet it assumes EVERY school that could reach the game, so the rule holds whoever
    wins. Entered winners narrow those sets; `locked` (already played) games keep their slot."""
    poss = {}

    def P(o):
        return {school_of[o[1]]} if o[0] == "team" else poss[o[1]]

    for mid in sorted(matches):
        poss[mid] = ({school_of[picks[mid]]} if picks.get(mid)
                     else P(matches[mid]["a"]) | P(matches[mid]["b"]))
    deps = {mid: [o[1] for o in (m["a"], m["b"]) if o[0] == "match"] for mid, m in matches.items()}

    rng = random.Random(7)
    best = None
    for trial in range(trials):
        w = [0, 0.5, 1.5, 100][trial % 4]
        pri = {mid: mid[0] * w + rng.random() for mid in matches}
        slot_of, slots, remaining = {}, [], set(matches)
        prev = [set(prev_schools)]
        while remaining:
            t = len(slots)
            chosen = [m for m in remaining if locked.get(m) == t]
            avail = sorted((m for m in remaining if m not in locked and
                            all(d in slot_of for d in deps[m])), key=pri.get)
            for m in avail:
                if len(chosen) >= COURTS:
                    break
                if any(poss[m] & x for x in prev) or any(poss[m] & poss[x] for x in chosen):
                    continue
                chosen.append(m)
            slots.append(chosen)
            for m in chosen:
                slot_of[m] = t
                remaining.discard(m)
            prev = [poss[x] for x in chosen]
        score = (len(slots), sum(1 for x in slots if not x))
        if best is None or score < best[0]:
            best = (score, slots)
    return best[1]


def round_name(r, total):
    return {1: "Final", 2: "Semifinals", 3: "Quarterfinals"}.get(total - r, f"Round {r + 1}")


# ================================================================ UI
st.set_page_config(page_title="B/C Playoff Bracket", page_icon="🏆", layout="wide")
st.title("🏆 B/C Team Playoff Bracket")
st.caption("Seeding games (3 per school) → combined B/C playoff · 2 courts · no school plays back-to-back")


@st.cache_data
def cached_seeding(n):
    return seeding_schedule(n)


def reset_all():
    for k in [k for k in st.session_state if k.startswith("win_")]:
        del st.session_state[k]
    for k in ("scores", "locked", "last_sched", "seed_editor"):
        st.session_state.pop(k, None)


with st.sidebar:
    st.header("Setup")
    st.dataframe(pd.DataFrame([{"School": s, "Teams": "/".join(t), "Players": p}
                               for s, t, p in SCHOOLS]),
                 hide_index=True, use_container_width=True)
    st.caption(f"Total players ≈ {sum(p for _, _, p in SCHOOLS)}")
    avoid = st.checkbox("Keep same-school teams apart in the bracket", value=True)
    st.subheader("Schedule")
    start = st.time_input("First game", value=datetime.strptime("09:00", "%H:%M").time())
    minutes = st.number_input("Minutes per game", 15, 120, 45, step=5)
    if st.button("Reset all results"):
        reset_all()
        st.rerun()

school_names = [s for s, _, _ in SCHOOLS]
players_of = {s: p for s, _, p in SCHOOLS}

# ---------------------------------------------------------------- seeding games
seed_slots = cached_seeding(len(school_names))
seed_games = []  # (slot, court, a, b)
for si, ch in enumerate(seed_slots):
    for ci, (a, b) in enumerate(ch):
        seed_games.append((si, ci, school_names[a], school_names[b]))
n_seed_slots = len(seed_slots)
n_seed_games = len(seed_games)

st.session_state.setdefault("scores", {})
scores = st.session_state.scores


def slot_time(si):
    t = datetime.combine(datetime.today(), start) + timedelta(minutes=minutes * si)
    return t.strftime("%I:%M %p").lstrip("0")


def seeding_standings():
    rec = {s: {"W": 0, "L": 0, "PD": 0, "GP": 0} for s in school_names}
    done = 0
    for i, (_, _, a, b) in enumerate(seed_games):
        sa, sb = scores.get(i, (None, None))
        if sa is None or sb is None or sa == sb:
            continue
        done += 1
        w, l = (a, b) if sa > sb else (b, a)
        rec[w]["W"] += 1
        rec[l]["L"] += 1
        rec[w]["PD"] += abs(sa - sb)
        rec[l]["PD"] -= abs(sa - sb)
        rec[a]["GP"] += 1
        rec[b]["GP"] += 1
    return rec, done


records, games_done = seeding_standings()
seeding_done = games_done == n_seed_games
ranked = sorted(school_names, key=lambda s: (-records[s]["W"], -records[s]["PD"],
                                             -players_of[s], school_names.index(s)))
school_rank = {s: i for i, s in enumerate(ranked)}

# team seeds: school rank first, then B before C
tdf = default_team_table()
tdf["rank"] = tdf.School.map(school_rank)
tdf = tdf.sort_values(["rank", "Tier"], kind="stable").reset_index(drop=True)
tdf["Seed"] = range(1, len(tdf) + 1)
teams = tdf.Team.tolist()
school_of = dict(zip(tdf.Team, tdf.School))

# ---------------------------------------------------------------- playoff structure
slots, total = arrange(teams, school_of, avoid)
matches, final_out = build_matches(slots, total)

picks = {}
for mid in sorted(matches):
    m = matches[mid]
    res = lambda o: o[1] if o[0] == "team" else picks.get(o[1])
    a_, b_ = res(m["a"]), res(m["b"])
    v = st.session_state.get(f"win_{mid}", "TBD")
    picks[mid] = v if v in (a_, b_) and v != "TBD" else None

st.session_state.setdefault("locked", {})
st.session_state.setdefault("last_sched", {})
locked = {mid: sl for mid, sl in st.session_state.locked.items() if picks.get(mid)}
for mid, v in picks.items():
    if v and mid not in locked and mid in st.session_state.last_sched:
        locked[mid] = st.session_state.last_sched[mid]
st.session_state.locked = locked

last_seed_schools = set()
if seed_slots:
    for a, b in seed_slots[-1]:
        last_seed_schools |= {school_names[a], school_names[b]}

sched = make_schedule(matches, school_of, picks, locked, last_seed_schools)
st.session_state.last_sched = {mid: si for si, ch in enumerate(sched) for mid in ch}

game_no, where = {}, {}
g = n_seed_games + 1
for si, chosen in enumerate(sched):
    for ci, mid in enumerate(chosen):
        game_no[mid] = g
        where[mid] = (n_seed_slots + si, ci)  # global slot index
        g += 1


def resolve(o):
    return o[1] if o[0] == "team" else picks.get(o[1])


def label(o):
    return o[1] if o[0] == "team" else f"Winner of Game {game_no[o[1]]}"


tab_seed, tab_bracket, tab_sched = st.tabs(["1 · Seeding games", "2 · Playoff bracket", "Full schedule"])

# ---------------------------------------------------------------- tab 1
with tab_seed:
    st.subheader(f"Seeding games — each school plays {SEEDING_GAMES_PER_SCHOOL}")
    st.caption("School vs. school (either of the school's teams can play). Enter final scores; "
               "ranking = wins, then point differential. That ranking seeds the playoff.")
    gdf = pd.DataFrame([{
        "Game": i + 1, "Time": slot_time(si), "Court": ci + 1, "School A": a, "School B": b,
        "Score A": scores.get(i, (None, None))[0], "Score B": scores.get(i, (None, None))[1],
    } for i, (si, ci, a, b) in enumerate(seed_games)])
    edited = st.data_editor(
        gdf, hide_index=True, use_container_width=True, key="seed_editor",
        disabled=["Game", "Time", "Court", "School A", "School B"],
        column_config={"Score A": st.column_config.NumberColumn(min_value=0, step=1),
                       "Score B": st.column_config.NumberColumn(min_value=0, step=1)})
    new_scores = {}
    for i, row in edited.iterrows():
        sa = None if pd.isna(row["Score A"]) else int(row["Score A"])
        sb = None if pd.isna(row["Score B"]) else int(row["Score B"])
        new_scores[i] = (sa, sb)
    if new_scores != scores:
        st.session_state.scores = new_scores
        st.rerun()
    if any(sa is not None and sa == sb for sa, sb in scores.values()):
        st.warning("A seeding game ended in a tie — enter a final (tie-broken) score.")

    st.markdown("**Standings**")
    st.dataframe(pd.DataFrame([{
        "Rank": i + 1, "School": s, "W": records[s]["W"], "L": records[s]["L"],
        "Pt diff": records[s]["PD"], "Played": f'{records[s]["GP"]}/{SEEDING_GAMES_PER_SCHOOL}'}
        for i, s in enumerate(ranked)]), hide_index=True, use_container_width=True)
    st.progress(games_done / n_seed_games, text=f"{games_done}/{n_seed_games} seeding games complete")

# ---------------------------------------------------------------- tab 2
with tab_bracket:
    if seeding_done:
        st.success("Seeds are final — entered from the seeding-game results.")
    else:
        st.info("Provisional seeds (by current standings). Winner boxes unlock when all "
                "seeding games are finished.")
    st.subheader(f"{len(teams)} teams · {sum(1 for s in slots if s is None)} first-round byes")
    st.caption("Seeds: " + " · ".join(f"{i}. {t}" for i, t in enumerate(teams, 1)))
    cols = st.columns(total + 1)
    for r in range(total):
        with cols[r]:
            st.markdown(f"**{round_name(r, total)}**")
            for mid in sorted(m for m in matches if m[0] == r):
                m = matches[mid]
                a, b = resolve(m["a"]), resolve(m["b"])
                opts = ["TBD"] + [x for x in (a, b) if x]
                k = f"win_{mid}"
                if st.session_state.get(k, "TBD") not in opts:
                    st.session_state[k] = "TBD"
                si, ci = where[mid]
                with st.container(border=True):
                    st.caption(f"Game {game_no[mid]} · {slot_time(si)} · Court {ci + 1}")
                    st.write(f"{a or label(m['a'])}  \nvs  \n{b or label(m['b'])}")
                    if a and b and school_of[a] == school_of[b]:
                        st.warning("Same school")
                    st.selectbox("Winner", opts, key=k, label_visibility="collapsed",
                                 disabled=not seeding_done)
    with cols[total]:
        st.markdown("**Champion**")
        champ = resolve(final_out)
        with st.container(border=True):
            st.success(f"🏆 {champ}") if champ else st.write("TBD")
    if avoid:
        st.caption("Same-school teams sit in opposite halves, so they can only meet in the final "
                   "if both get there (unavoidable with one B and one C team per school).")

# ---------------------------------------------------------------- tab 3
with tab_sched:
    st.subheader("Full schedule (seeding + playoffs)")
    rows = []
    for si in range(n_seed_slots + len(sched)):
        row = {"Slot": si + 1, "Time": slot_time(si),
               "Phase": "Seeding" if si < n_seed_slots else "Playoff"}
        cells = []
        if si < n_seed_slots:
            for i, (s_, ci, a, b) in enumerate(seed_games):
                if s_ == si:
                    cells.append(f"G{i + 1}: {a} vs {b}")
        else:
            for mid in sched[si - n_seed_slots]:
                m = matches[mid]
                a = resolve(m["a"]) or label(m["a"])
                b = resolve(m["b"]) or label(m["b"])
                cells.append(f"G{game_no[mid]} ({round_name(mid[0], total)}): {a} vs {b}")
        for ci in range(COURTS):
            row[f"Court {ci + 1}"] = cells[ci] if ci < len(cells) else "—"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    byes = [slots[i] or slots[i + 1] for i in range(0, len(slots), 2)
            if (slots[i] is None) != (slots[i + 1] is None)]
    if byes:
        st.caption("First-round byes: " + ", ".join(byes))
    st.info("Rule check: no school plays in two back-to-back slots, or on both courts at once. "
            "For playoff games where the teams aren't known yet, the schedule counts every school "
            "that could be in the game, so the rule holds whoever wins. It starts cautious and "
            "tightens as you enter winners; games with a winner entered keep their slot.")
    st.download_button("Download schedule (CSV)", pd.DataFrame(rows).to_csv(index=False),
                       "bc_schedule.csv")
