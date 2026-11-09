import random
import pandas as pd
import streamlit as st

st.set_page_config(page_title="B/C Team Playoff Bracket", page_icon="🏆", layout="wide")

# ---------------------------------------------------------------- data
SCHOOLS = [
    # name, tiers, approx players
    ("SB", ["A", "B"], 25),
    ("USC", ["A", "B", "C"], 25),
    ("Biola", ["A", "B"], 16),
    ("UCLA", ["A", "B", "C"], 35),
    ("UCI", ["A", "B", "C"], 44),
    ("Pepp", ["A", "B"], 25),
    ("SD", ["A", "B", "C"], 27),
    ("Riverside", ["A", "B", "C"], 35),
]
BRACKET_TIERS = ["B", "C"]


def default_team_table():
    rows = []
    for tier in BRACKET_TIERS:
        eligible = [(s, p, len(t)) for s, t, p in SCHOOLS if tier in t]
        eligible.sort(key=lambda x: -x[1] / x[2])  # biggest avg team first
        for seed, (school, players, n) in enumerate(eligible, 1):
            rows.append({"Tier": tier, "Team": f"{school} {tier}", "School": school,
                         "Est. players": round(players / n), "Seed": seed})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- bracket logic
def seed_order(n):
    order = [1]
    while len(order) < n:
        size = len(order) * 2
        order = [x for s in order for x in (s, size + 1 - s)]
    return order


def round_name(r, total):
    left = total - r
    return {1: "Final", 2: "Semifinals", 3: "Quarterfinals"}.get(left, f"Round {r + 1}")


def build_and_render(tier, teams, key_prefix):
    """teams: list of team names in seed order. Renders bracket and returns champion."""
    n = len(teams)
    if n < 2:
        st.info("Need at least 2 teams.")
        return None
    size = 1
    while size < n:
        size *= 2
    total_rounds = size.bit_length() - 1
    order = seed_order(size)
    slots = [teams[s - 1] if s <= n else None for s in order]

    results = st.session_state.setdefault("results", {})
    cols = st.columns(total_rounds + 1)
    current = slots
    champion = None

    for r in range(total_rounds):
        nxt = []
        with cols[r]:
            st.markdown(f"**{round_name(r, total_rounds)}**")
            for m in range(len(current) // 2):
                a, b = current[2 * m], current[2 * m + 1]
                if a is None or b is None:
                    w = a or b
                    if r == 0:
                        with st.container(border=True):
                            st.caption(f"🛌 {w} — bye")
                    nxt.append(w)
                    continue
                k = f"{key_prefix}_{r}_{m}"
                options = ["TBD"] + [x for x in (a, b) if x != "TBD"]
                # drop stale picks when earlier results change
                if results.get(k, "TBD") not in options:
                    results[k] = "TBD"
                if st.session_state.get(k, "TBD") not in options:
                    st.session_state[k] = "TBD"
                with st.container(border=True):
                    st.write(f"{a}  \nvs  \n{b}")
                    pick = st.selectbox("Winner", options, key=k,
                                        label_visibility="collapsed")
                results[k] = pick
                nxt.append(None if pick == "TBD" else pick)
                if pick == "TBD":
                    nxt[-1] = "TBD"
        current = [None if x is None else x for x in nxt]
        # TBD teams should not auto-advance as byes
        current = ["TBD" if x == "TBD" else x for x in current]
        # a "TBD" slot facing a real team must wait, so treat it as a real (unknown) team
        if r == total_rounds - 1:
            champion = current[0]

    with cols[total_rounds]:
        st.markdown("**Champion**")
        with st.container(border=True):
            if champion and champion != "TBD":
                st.success(f"🏆 {champion}")
            else:
                st.write("TBD")
    return champion if champion != "TBD" else None


# ---------------------------------------------------------------- UI
st.title("🏆 B/C Team Playoff Bracket")
st.caption("Single elimination · B bracket and C bracket · top seeds get byes when the field isn't a power of 2")

if "table" not in st.session_state:
    st.session_state.table = default_team_table()

with st.sidebar:
    st.header("Setup")
    st.markdown("**Schools & rosters**")
    st.dataframe(
        pd.DataFrame([{"School": s, "Teams": "/".join(t), "Players": p} for s, t, p in SCHOOLS]),
        hide_index=True, use_container_width=True,
    )
    st.caption(f"Total players ≈ {sum(p for _, _, p in SCHOOLS)}")
    method = st.radio("Seeding", ["By team size", "Random", "Manual (edit Seed column)"])
    rnd = st.number_input("Random seed", 0, 9999, 42) if method == "Random" else None
    if st.button("Apply seeding"):
        if method == "By team size":
            st.session_state.table = default_team_table()
        elif method == "Random":
            rng = random.Random(rnd)
            df = st.session_state.table.copy()
            for t in BRACKET_TIERS:
                idx = df.index[df.Tier == t].tolist()
                seeds = list(range(1, len(idx) + 1))
                rng.shuffle(seeds)
                df.loc[idx, "Seed"] = seeds
            st.session_state.table = df
        st.session_state.results = {}
        st.rerun()
    if st.button("Reset all results"):
        st.session_state.results = {}
        for k in [k for k in st.session_state if k.startswith(("B_", "C_"))]:
            del st.session_state[k]
        st.rerun()

with st.expander("Teams & seeding (editable)", expanded=False):
    edited = st.data_editor(
        st.session_state.table, hide_index=True, use_container_width=True,
        disabled=["Tier", "Team", "School"], key="editor",
    )
    st.session_state.table = edited

tabs = st.tabs(["B Bracket", "C Bracket", "Summary"])
champs = {}
for tab, tier in zip(tabs[:2], BRACKET_TIERS):
    with tab:
        df = st.session_state.table
        df = df[df.Tier == tier].sort_values("Seed", kind="stable")
        teams = df.Team.tolist()
        st.subheader(f"{tier} Team Bracket — {len(teams)} teams")
        st.caption("Seeds: " + " · ".join(f"{i}. {t}" for i, t in enumerate(teams, 1)))
        champs[tier] = build_and_render(tier, teams, tier)

with tabs[2]:
    c1, c2 = st.columns(2)
    c1.metric("B Champion", champs.get("B") or "TBD")
    c2.metric("C Champion", champs.get("C") or "TBD")
    st.dataframe(st.session_state.table.sort_values(["Tier", "Seed"]),
                 hide_index=True, use_container_width=True)
    st.download_button("Download seeding (CSV)",
                       st.session_state.table.to_csv(index=False), "bc_seeding.csv")
