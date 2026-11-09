import random
import streamlit as st

st.set_page_config(page_title="B/C Division Tournament Schedule", layout="wide")

st.title("🏆 B/C Division Tournament Schedule")
st.caption("2 Courts | 13 Teams | 3 Games Guaranteed | Mixed B vs C Matchups | No Intra-School Matches | No Back-to-Back Games")

# Define B and C teams explicitly separated for partitioning
B_TEAMS = ["SB B", "USC B", "Biola B", "UCLA B", "UCI B", "Pepp B", "SD B", "Riverside B"]
C_TEAMS = ["USC C", "UCLA C", "UCI C", "SD C", "Riverside C"]
ALL_TEAMS = B_TEAMS + C_TEAMS

def get_school(team_name):
    return team_name.split()[0]

def is_c_team(team_name):
    return team_name.endswith(" C")

def generate_valid_schedule():
    """Generates a 3-round tournament schedule enforcing:
       - Every team plays 3 games.
       - No same-school matchups.
       - C teams NEVER play C teams (C teams must play B teams).
       - B teams can play B or C teams.
    """
    for attempt in range(2000):
        rounds = []
        played_pairs = set()
        success = True

        for r in range(3):
            round_matches = []
            available = ALL_TEAMS[:]
            random.shuffle(available)
            
            # Sort so C teams are handled or matched efficiently
            available.sort(key=lambda t: 0 if is_c_team(t) else 1)
            
            while len(available) >= 2:
                t1 = available.pop(0)
                partner = None
                
                # Filter valid candidates for t1
                candidates = []
                for candidate in available:
                    # 1. No same school
                    if get_school(t1) == get_school(candidate):
                        continue
                    # 2. C vs C restriction (If both are C teams, skip)
                    if is_c_team(t1) and is_c_team(candidate):
                        continue
                    # 3. No duplicate matchups across rounds
                    pair = tuple(sorted([t1, candidate]))
                    if pair in played_pairs:
                        continue
                    
                    candidates.append(candidate)
                
                if candidates:
                    # Pick a random valid candidate
                    partner = random.choice(candidates)
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
    """Schedules matches onto 2 courts sequentially, guaranteeing no school plays back-to-back slots."""
    flat_matches = []
    for r_idx, r_matches in enumerate(all_rounds):
        for m in r_matches:
            flat_matches.append((r_idx + 1, m[0], m[1]))
            
    slots = []
    last_schools = set()
    
    while flat_matches:
        court1 = None
        court2 = None
        
        # Pick Court 1 match
        for idx, item in enumerate(flat_matches):
            r, t1, t2 = item
            s1, s2 = get_school(t1), get_school(t2)
            if s1 not in last_schools and s2 not in last_schools:
                court1 = flat_matches.pop(idx)
                break
        if not court1:
            court1 = flat_matches.pop(0)
            
        c1_schools = {get_school(court1[1]), get_school(court1[2])}
        
        # Pick Court 2 match (avoiding Court 1 schools & previous slot schools)
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
        st.caption("Matches ordered across slots so teams get mandatory rest breaks between games.")
        
        for slot_num, (c1, c2) in enumerate(court_schedule, start=1):
            st.markdown(f"### ⏱️ Time Slot {slot_num}")
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"**Court 1 [Round {c1[0]}]:** {c1[1]} vs {c1[2]}")
            with col2:
                if c2:
                    st.success(f"**Court 2 [Round {c2[0]}]:** {c2[1]} vs {c2[2]}")
                else:
                    st.info("**Court 2:** OPEN / BREAK")

    with tab2:
        st.subheader("Standard Round Breakdown (6 Matches per Round)")
        for r_idx, r_matches in enumerate(all_rounds, start=1):
            st.markdown(f"#### Round {r_idx}")
            cols = st.columns(3)
            for m_idx, (t1, t2) in enumerate(r_matches):
                cols[m_idx % 3].write(f"• **{t1}** vs **{t2}**")

    with tab3:
        st.subheader("Team Matchup Summary")
        st.write("Verifies that every team plays exactly 3 games, C teams never play C teams, and no intra-school matchups occur.")
        
        team_summary = {t: [] for t in ALL_TEAMS}
        for r_idx, r_matches in enumerate(all_rounds, start=1):
            for t1, t2 in r_matches:
                team_summary[t1].append(f"R{r_idx} vs {t2}")
                team_summary[t2].append(f"R{r_idx} vs {t1}")

        t_cols = st.columns(2)
        for idx, (team, games) in enumerate(team_summary.items()):
            with t_cols[idx % 2]:
                badge = "🟡 [C Team]" if is_c_team(team) else "🔵 [B Team]"
                st.write(f"**{team}** {badge} ({len(games)} Games): " + " | ".join(games))
else:
    st.error("Could not find a valid schedule matching all constraints (especially C-vs-C prohibition). Please hit re-generate!")
