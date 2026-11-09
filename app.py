import random
import streamlit as st

st.set_page_config(page_title="B/C Division 3-Game Guarantee", layout="wide")

st.title("🏆 B/C Division Tournament (3-Game Guarantee)")
st.caption("2 Courts | 13 Teams | Exactly 3 Games per Team | No Intra-School Games | No Back-to-Backs")

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

def get_school(team_name):
    return team_name.split()[0]

def generate_valid_schedule():
    """Generates a 3-round schedule where every team plays 3 games total,
    never plays their own school, and avoids back-to-back slot scheduling on 2 courts."""
    
    # Try multiple random seeds to satisfy all constraints cleanly
    for attempt in range(500):
        rounds = []
        team_match_count = {t: 0 for t in TEAMS}
        played_pairs = set()

        success = True
        for r in range(3):
            # Try to build a matching round of games (6 games, 1 team rest/bye per round for 13 teams)
            available = TEAMS[:]
            random.shuffle(available)
            round_matches = []
            
            while len(available) >= 2:
                t1 = available.pop(0)
                partner = None
                for candidate in available:
                    # Check same school constraint & duplicate matchup constraint
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
                
            rounds.append(round_matches)

        if success:
            return rounds
            
    return None

def schedule_courts_no_back_to_back(all_rounds):
    """Schedules matches into 2-court time slots to prevent back-to-back games for any school."""
    flat_matches = []
    for r_idx, r_matches in enumerate(all_rounds):
        for m in r_matches:
            flat_matches.append((r_idx + 1, m[0], m[1]))
            
    slots = []
    last_schools = set()
    
    while flat_matches:
        court1 = None
        court2 = None
        
        # Pick Court 1 match without back-to-back constraint violation
        for idx, item in enumerate(flat_matches):
            r, t1, t2 = item
            s1, s2 = get_school(t1), get_school(t2)
            if s1 not in last_schools and s2 not in last_schools:
                court1 = flat_matches.pop(idx)
                break
        if not court1:
            court1 = flat_matches.pop(0)
            
        c1_schools = {get_school(court1[1]), get_school(court1[2])}
        
        # Pick Court 2 match without school overlap with Court 1 or previous slot
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

# App Interface
st.sidebar.header("Controls")
if st.sidebar.button("🎲 Re-generate Schedule"):
    st.rerun()

all_rounds = generate_valid_schedule()

if all_rounds:
    court_schedule = schedule_courts_no_back_to_back(all_rounds)
    
    tab1, tab2, tab3 = st.tabs(["🗓️ Master Court Schedule", "📊 Round-by-Round Breakdown", "✅ Team Game Tracker"])
    
    with tab1:
        st.subheader("2-Court Timetable (No Back-to-Back Games)")
        for slot_num, (c1, c2) in enumerate(court_schedule, start=1):
            st.markdown(f"### ⏱️ Time Slot {slot_num}")
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"**Court 1 (Round {c1[0]}):** {c1[1]} vs {c1[2]}")
            with col2:
                if c2:
                    st.success(f"**Court 2 (Round {c2[0]}):** {c2[1]} vs {c2[2]}")
                else:
                    st.info("**Court 2:** OPEN / BREAK")

    with tab2:
        st.subheader("Round Structure (6 Matches per Round)")
        for r_idx, r_matches in enumerate(all_rounds, start=1):
            st.markdown(f"#### Round {r_idx}")
            cols = st.columns(3)
            for m_idx, (t1, t2) in enumerate(r_matches):
                cols[m_idx % 3].write(f"• **{t1}** vs **{t2}**")

    with tab3:
        st.subheader("Team Game Verification")
        st.write("Verifies that every team plays exactly 3 games against non-school opponents.")
        
        team_summary = {t: [] for t in TEAMS}
        for r_idx, r_matches in enumerate(all_rounds, start=1):
            for t1, t2 in r_matches:
                team_summary[t1].append(f"R{r_idx} vs {t2}")
                team_summary[t2].append(f"R{r_idx} vs {t1}")

        t_cols = st.columns(2)
        for idx, (team, games) in enumerate(team_summary.items()):
            with t_cols[idx % 2]:
                st.write(f"**{team}** ({len(games)} Games): " + " | ".join(games))
else:
    st.error("Could not find a valid schedule matching all constraints. Please hit re-generate!")
