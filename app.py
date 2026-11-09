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


def default_team_table():
    rows = []
    for school, tiers, players in SCHOOLS:
        for t in tiers:
            if t in BRACKET_TIERS:
                rows.append({"Team": f"{school} {t}", "School": school, "Tier": t,
                             "Est. players": round(players / len(tiers))})
    df = (pd.DataFrame(rows)
          .sort_values(["Est. players", "Tier"], ascending=[False, True], kind="stable")
          .reset_index(drop=True))
    df["Seed"] = range(1, len(df) + 1)
    return df


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


def make_schedule(matches, key_of, picks, locked, trials=600):
    """Slot-by-slot scheduler: 2 courts per slot, and nobody (school or team, per `key_of`)
    may play in two consecutive slots or twice in one slot. For games whose players aren't
    known yet it assumes EVERY team that could reach it, so the rule holds whoever wins.
    `picks` (entered winners) narrow those sets; `locked` games (already played) keep their slot."""
    poss = {}

    def P(o):
        return {key_of[o[1]]} if o[0] == "team" else poss[o[1]]

    for mid in sorted(matches):
        poss[mid] = ({key_of[picks[mid]]} if picks.get(mid)
                     else P(matches[mid]["a"]) | P(matches[mid]["b"]))
    deps = {mid: [o[1] for o in (m["a"], m["b"]) if o[0] == "match"] for mid, m in matches.items()}

    rng = random.Random(7)
    best = None
    for trial in range(trials):
        w = [0, 0.5, 1.5, 100][trial % 4]
        pri = {mid: mid[0] * w + rng.random() for mid in matches}
        slot_of, slots, remaining, prev = {}, [], set(matches), []
        while remaining:
            t = len(slots)
            chosen = [m for m in remaining if locked.get(m) == t]
            avail = sorted((m for m in remaining if m not in locked and
                            all(d in slot_of for d in deps[m])), key=pri.get)
            for m in avail:
                if len(chosen) >= COURTS:
                    break
                if any(poss[m] & poss[x] for x in prev + chosen):
                    continue
                chosen.append(m)
            slots.append(chosen)
            for m in chosen:
                slot_of[m] = t
                remaining.discard(m)
            prev = chosen
        # trailing empty slots never happen; score = total slots, then idle slots
        score = (len(slots), sum(1 for x in slots if not x))
        if best is None or score < best[0]:
            best = (score, slots)
    return best[1]


def round_name(r, total):
    return {1: "Final", 2: "Semifinals", 3: "Quarterfinals"}.get(total - r, f"Round {r + 1}")


# ================================================================ UI
st.set_page_config(page_title="B/C Playoff Bracket", page_icon="🏆", layout="wide")
st.title("🏆 B/C Team Playoff Bracket")
st.caption("One combined bracket · B and C teams mix · 2 courts · no school plays back-to-back")

if "table" not in st.session_state:
    st.session_state.table = default_team_table()


def clear_results():
    for k in [k for k in st.session_state if k.startswith("win_")]:
        del st.session_state[k]


with st.sidebar:
    st.header("Setup")
    st.dataframe(pd.DataFrame([{"School": s, "Teams": "/".join(t), "Players": p}
                               for s, t, p in SCHOOLS]),
                 hide_index=True, use_container_width=True)
    st.caption(f"Total players ≈ {sum(p for _, _, p in SCHOOLS)}")

    method = st.radio("Seeding", ["By team size", "Random", "Manual (edit Seed column)"])
    if st.button("Apply seeding"):
        if method == "By team size":
            st.session_state.table = default_team_table()
        elif method == "Random":
            df = st.session_state.table.copy()
            seeds = list(range(1, len(df) + 1))
            random.shuffle(seeds)
            df["Seed"] = seeds
            st.session_state.table = df
        clear_results()
        st.rerun()
    avoid = st.checkbox("Keep same-school teams apart", value=True)
    rest_rule = st.radio("No back-to-back games for…", ["Whole school", "Same team only"])

    st.subheader("Schedule")
    start = st.time_input("First game", value=datetime.strptime("09:00", "%H:%M").time())
    minutes = st.number_input("Minutes per game", 15, 120, 45, step=5)

    if st.button("Reset all results"):
        clear_results()
        st.rerun()

with st.expander("Teams & seeding (editable)"):
    st.session_state.table = st.data_editor(
        st.session_state.table, hide_index=True, use_container_width=True,
        disabled=["Team", "School", "Tier", "Est. players"], key="editor")

df = st.session_state.table.sort_values("Seed", kind="stable").reset_index(drop=True)
teams = df.Team.tolist()
school_of = dict(zip(df.Team, df.School))

slots, total = arrange(teams, school_of, avoid)
matches, final_out = build_matches(slots, total)
key_of = school_of if rest_rule == "Whole school" else {t: t for t in teams}

# entered winners (read from widget state so the schedule reacts immediately)
picks = {}
for mid in sorted(matches):
    m = matches[mid]
    res = lambda o: o[1] if o[0] == "team" else picks.get(o[1])
    a_, b_ = res(m["a"]), res(m["b"])
    v = st.session_state.get(f"win_{mid}", "TBD")
    picks[mid] = v if v in (a_, b_) and v != "TBD" else None

# games already played keep their slot
st.session_state.setdefault("locked", {})
st.session_state.setdefault("last_sched", {})
locked = {mid: sl for mid, sl in st.session_state.locked.items() if picks.get(mid)}
for mid, v in picks.items():
    if v and mid not in locked and mid in st.session_state.last_sched:
        locked[mid] = st.session_state.last_sched[mid]
st.session_state.locked = locked

sched = make_schedule(matches, key_of, picks, locked)
st.session_state.last_sched = {mid: si for si, ch in enumerate(sched) for mid in ch}

game_no, where = {}, {}
g = 1
for si, chosen in enumerate(sched):
    for ci, mid in enumerate(chosen):
        game_no[mid] = g
        where[mid] = (si, ci)
        g += 1


def slot_time(si):
    t = datetime.combine(datetime.today(), start) + timedelta(minutes=minutes * si)
    return t.strftime("%I:%M %p").lstrip("0")


tab_bracket, tab_sched = st.tabs(["Bracket", "Schedule (2 courts)"])


def resolve(o):
    return o[1] if o[0] == "team" else picks.get(o[1])


def label(o):
    return o[1] if o[0] == "team" else f"Winner of Game {game_no[o[1]]}"


with tab_bracket:
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
                    pick = st.selectbox("Winner", opts, key=k, label_visibility="collapsed")
    with cols[total]:
        st.markdown("**Champion**")
        champ = resolve(final_out)
        with st.container(border=True):
            st.success(f"🏆 {champ}") if champ else st.write("TBD")
    if avoid:
        st.caption("Same-school teams sit in opposite halves, so they can only meet in the final "
                   "if both get there (unavoidable with one B and one C team per school).")

with tab_sched:
    st.subheader("Game schedule")
    rows = []
    for si, chosen in enumerate(sched):
        row = {"Slot": si + 1, "Time": slot_time(si)}
        for ci in range(COURTS):
            if ci < len(chosen):
                mid = chosen[ci]
                m = matches[mid]
                a = resolve(m["a"]) or label(m["a"])
                b = resolve(m["b"]) or label(m["b"])
                row[f"Court {ci + 1}"] = f"G{game_no[mid]} ({round_name(mid[0], total)}): {a} vs {b}"
            else:
                row[f"Court {ci + 1}"] = "—"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    byes = [slots[i] or slots[i + 1] for i in range(0, len(slots), 2)
            if (slots[i] is None) != (slots[i + 1] is None)]
    if byes:
        st.caption("First-round byes: " + ", ".join(byes))
    st.info("Rule check: the schedule leaves a gap slot whenever a school could appear in the "
            "previous slot (counting every team that could possibly reach that game), so the rest "
            "rule holds whoever wins. The projected schedule starts out cautious and tightens up "
            "as you enter winners; games with a winner entered keep their slot.")
    st.download_button("Download schedule (CSV)", pd.DataFrame(rows).to_csv(index=False),
                       "bc_schedule.csv")
