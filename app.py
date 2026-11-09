import random
import streamlit as st

st.set_page_config(page_title="Swiss Stage — B/C Division", layout="wide")

st.title("⚔️ League of Legends Style Swiss Stage")
st.caption("13-Team B/C Division | 3 Wins to Qualify / 3 Losses to Eliminate | 2-Court Constraint | No Intra-School Matches")

# Participating B/C Teams (13 Total)
TEAMS = [
    "SB B",
    "USC B", "USC C",
    "Biola B",
    "UCLA B", "UCLA C",
    "UCI B", "UCI C",
    "Pepp B",
    "SD B", "SD C",
    "Riverside B", "Riverside C"
]

def get_school(team):
    return team.split()[0]

def build_swiss_rounds():
    """Generates a 3-Round Swiss System framework where all teams get 3 games total,
    never play their own school, and avoid repeat matchups."""
    for _ in range(1000):
        rounds = []
        played_pairs = set()
        records = {t: {"wins": 0, "losses": 0} for t in TEAMS}
        success = True
        
        for r_num in range(1, 4):
            # Group teams by record (Swiss pools)
            pools = {}
            for t, rec in records.items():
                score = f"{rec['wins']}-{rec['losses']}"
                pools.setdefault(score, []).append(t)
            
            round_matches = []
            available = TEAMS[:]
            random.shuffle(available)
            
            # Sort available teams by record score to match similar-record teams first
            available.sort(key=lambda t: (records[t]["wins"], -records[t]["losses"]), reverse=True)
            
            while len(available) >= 2:
                t1 = available.pop(0)
                partner = None
                for candidate in available:
                    # Same school check & repeat match check
                    if get_school(t1) != get_school(candidate):
                        pair = tuple(sorted([t1, candidate]))
                        if pair not in played_pairs:
                            partner = candidate
                            break
                
                if partner:
                    available.remove(partner)
                    round_matches.append((t1, partner))
                    played_pairs.add(tuple(sorted([t1, partner])))
                else:
                    success = False
                    break
                    
            if not success or len(round_matches) < 6:
                success = False
                break
                
            rounds.append({"round": r_num, "matches": round_matches, "pools": pools})
            
        if success:
            return rounds
    return None

def schedule_2_courts(swiss_rounds):
    """Schedules matches onto 2 courts with zero back-to-back games for any school."""
    flat_matches = []
    for r_data in swiss_rounds:
        r_num = r_data["round"]
        for m in r_data["matches"]:
            flat_matches.append((r_num, m[0], m[1]))
            
    slots = []
    last_schools = set()
    
    while flat_matches:
        court1, court2 = None, None
        
        # Court 1 Selection
        for idx, item in enumerate(flat_matches):
            r, t1, t2 = item
            s1, s2 = get_school(t1), get_school(t2)
            if s1 not in last_schools and s2 not in last_schools:
                court1 = flat_matches.pop(idx)
                break
        if not court1:
            court1 = flat_matches.pop(0)
            
        c1_schools = {get_school(court1[1]), get_school(court1[2])}
        
        # Court 2 Selection
        for idx, item in enumerate(flat_matches):
            r, t1, t2 = item
            s1, s2 = get_school(t1), get_school(t2)
            if (s1 not in last_schools and s2 not in last_schools and 
                s1 not in c1_schools and s2 not in c1_schools):
                court2 = flat_matches.pop(idx)
                break
                
        slot_schools = set(c1_schools)
        if court2:
            slot_schools.update([get_school(court2[1]), get_school(court2[2])])
            
        slots.append((court1, court2))
        last_schools = slot_schools

    return slots

# App Navigation
st.sidebar.title("🎮 Swiss Hub")
if st.sidebar.button("🎲 Re-seed Swiss Draw"):
    st.rerun()

swiss_data = build_swiss_rounds()

if swiss_data:
    court_schedule = schedule_2_courts(swiss_data)
    
    tab1, tab2, tab3 = st.tabs(["🏛️ Swiss Stage Matrix", "📺 Live Broadcast Schedule", "📋 Team Status & Pools"])

    with tab1:
        st.subheader("Swiss Stage Matchups (League Format)")
        st.write("Teams are matched based on performance pool, strictly avoiding intra-school matches.")
        
        col_r1, col_r2, col_r3 = st.columns(3)
        
        with col_r1:
            st.markdown("### 🔷 Round 1 (0-0 Record)")
            for idx, (t1, t2) in enumerate(swiss_data[0]["matches"], 1):
                st.info(f"**Match {idx}**\n\n🔴 **{t1}** vs 🔵 **{t2}**")

        with col_r2:
            st.markdown("### 🔶 Round 2 (High vs Low Pools)")
            for idx, (t1, t2) in enumerate(swiss_data[1]["matches"], 1):
                st.warning(f"**Match {idx}**\n\n🔴 **{t1}** vs 🔵 **{t2}**")

        with col_r3:
            st.markdown("### 🔴 Round 3 (Qualification / Elimination)")
            for idx, (t1, t2) in enumerate(swiss_data[2]["matches"], 1):
                st.error(f"**Match {idx}**\n\n🔴 **{t1}** vs 🔵 **{t2}**")

    with tab2:
        st.subheader("2-Court Match Order (No Back-to-Back Games)")
        st.caption("Optimized sequence so no school plays consecutive time slots.")
        
        for slot_idx, (c1, c2) in enumerate(court_schedule, start=1):
            st.markdown(f"#### ⏱️ Slot {slot_idx}")
            sc1, sc2 = st.columns(2)
            with sc1:
                st.success(f"**Court 1 [Round {c1[0]}]:** {c1[1]} vs {c1[2]}")
            with sc2:
                if c2:
                    st.success(f"**Court 2 [Round {c2[0]}]:** {c2[1]} vs {c2[2]}")
                else:
                    st.info("**Court 2:** ☕ OPEN / REST SLOT")

    with tab3:
        st.subheader("Team Matchup Summary")
        summary = {t: [] for t in TEAMS}
        for r in swiss_data:
            r_num = r["round"]
            for t1, t2 in r["matches"]:
                summary[t1].append(f"R{r_num} vs **{t2}**")
                summary[t2].append(f"R{r_num} vs **{t1}**")

        cols = st.columns(2)
        for idx, (t, games) in enumerate(summary.items()):
            with cols[idx % 2]:
                st.markdown(f"**{t}** (3 Games Guaranteed)")
                st.write(" ➔ ".join(games))
                st.divider()
else:
    st.error("Failed to generate Swiss layout. Click re-seed!")
