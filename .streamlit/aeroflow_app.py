import random, pandas as pd, streamlit as st
from typing import List

# ---------- CONFIG ----------
ROLES = [
    "Airport Operations",
    "Airline Control Center",
    "Aircraft Maintenance"
]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Baseline task minutes
GATE_PVT, GATE_SHR = 10, 10
CREW_NB,  CREW_B10 = 30, 40
MX_FIX,   MX_DEF   = 20, 0

# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway - bird shooing takes time!", 8),
    ("Fuel truck stuck in traffic - jet waits thirsty.", 12),
    ("Half the ramp crew called in sick - slow loading.", 9),
    ("Snow squall - de-icing bath begins.", 15),
    ("Baggage belt jam - bags everywhere.", 7),
    ("Gate power outage - lights are out.", 10),
    ("Catering cart spills tomato soup on luggage.", 6),
    ("Lightning overhead - ramp ops paused.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ---------- STATE ----------
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {
            r: pd.DataFrame({
                "Round":    range(1, ROUNDS + 1),
                "Decision": ["-"] * ROUNDS,
                "Duration": [0] * ROUNDS,
                "Cost":     [0] * ROUNDS,
                "Notes":    [""] * ROUNDS
            }) for r in ROLES
        }
        st.session_state.events   = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline = [None] * ROUNDS        # list[DataFrame]
        st.session_state.kpi      = pd.DataFrame(index=ROLES,
                                   columns=["Delay","Cost"]).fillna(0)
        st.session_state.round    = 1
init_state()

# ---------- LOGIC ----------
def everyone_done(idx): 
    return all(st.session_state.data[r].at[idx,"Decision"]!="-"
               for r in ROLES)

def build_timeline(idx):
    evt_text, evt_delay = st.session_state.events[idx]
    rows, start = [], 0

    ap = st.session_state.data[ROLES[0]].loc[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append([ROLES[0], start, ap_end])

    ac = st.session_state.data[ROLES[1]].loc[idx]
    ac_end = ap_end + ac.Duration
    rows.append([ROLES[1], ap_end, ac_end])

    mx = st.session_state.data[ROLES[2]].loc[idx]
    mx_end = ac_end + mx.Duration
    rows.append([ROLES[2], ac_end, mx_end])

    st.session_state.timeline[idx] = pd.DataFrame(rows, columns=["Role","Start","End"])

    extra = max(mx_end - ON_TIME_MIN, 0)
    fine  = extra * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.data[r].at[idx,"Cost"] += fine / 3

    for r in ROLES:
        df = st.session_state.data[r]
        st.session_state.kpi.at[r,"Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r,"Cost"]  = df["Cost"].sum()

def record(role, idx, choice):
    df = st.session_state.data[role]
    if role == ROLES[0]:  # Airport Ops
        dur,cost,note = (GATE_PVT,GATE_FEE,"Private gate") \
                        if choice=="Private Gate" else (GATE_SHR,0,"Shared gate")
        if choice=="Shared Gate" and random.random()<0.5:
            dur += 10; note += " (+10 clash)"
    elif role == ROLES[1]:  # Airline Control
        dur,cost,note = (CREW_NB,0,"No buffer") \
                        if choice=="No Buffer" else (CREW_B10,0,"Buffer 10")
        if choice=="No Buffer" and random.random()<0.4:
            dur += 15; note += " (+15 late crew)"
    else:  # Maintenance
        if choice=="Fix Now":
            dur,cost,note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur,cost,note = MX_DEF, 0, "Defer"
            if random.random()<MX_PEN_PROB:
                cost += MX_PENALTY; note += " Penalty $1k"
            else:
                note += " No penalty"
    df.loc[idx,["Decision","Duration","Cost","Notes"]] = [choice,dur,cost,note]

    if everyone_done(idx):
        build_timeline(idx)
        st.session_state.round = min(idx+2, ROUNDS)

# ---------- UI HELPERS ----------
def sidebar(role, rnd):
    st.sidebar.header(f"Round {rnd} - {role}")
    st.sidebar.text(
        f"Goal ≤ {ON_TIME_MIN} min\n"
        f"Delay fine ${FINE_PER_MIN}/min (split)\n"
        f"Gate fee ${GATE_FEE}\n"
        f"Fix-now ${MX_FIX_COST}\n"
        f"Defer risk 40% → ${MX_PENALTY}"
    )
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"): 
                st.session_state.round = min(rnd+1, ROUNDS); st.experimental_rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.experimental_rerun()

def kpi_strip():
    tot_cost = st.session_state.kpi["Cost"].sum()
    last_time = max((b["End"].max() for b in st.session_state.timeline if b is not None), default=0)
    c1,c2 = st.columns(2)
    c1.metric("Team Cost", f"${tot_cost:,.0f}")
    c2.metric("Latest Ground Time", f"{last_time} min", delta=f"{last_time-ON_TIME_MIN:+}")

def decision_options(role):
    if role == ROLES[0]: return ("Private Gate","Shared Gate")
    if role == ROLES[1]: return ("No Buffer","Buffer 10")
    return ("Fix Now","Defer")

def timeline_board(idx):
    board = st.session_state.timeline[idx]
    if board is not None:
        st.dataframe(board, use_container_width=True)
    else:
        st.info("Waiting for all roles...")

# ---------- STREAMLIT PAGE ----------
st.set_page_config(page_title="MMIS 494 Aviation MIS Simulation",
                   page_icon="🛫", layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_play, tab_help = st.tabs(["Play","How to Play"])

with tab_help:
    st.header("Role Briefs")
    st.markdown(
        "- Airport Ops: Gate and ground equipment.\n"
        "- Airline Control: Crew swap and flight plan.\n"
        "- Aircraft Maintenance: Mechanical fixes or defers.\n"
        "Delay past 45 min costs the team $100 per extra minute."
    )

with tab_play:
    rnd  = st.session_state.round
    role = st.sidebar.selectbox("Your Role", ROLES, key="role_pick")
    sidebar(role, rnd)
    kpi_strip()

    evt_text, evt_delay = st.session_state.events[rnd-1]
    st.warning(f"{evt_text}\n(+{evt_delay} min)")

    # Decision block
    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice = st.radio("Choose:", decision_options(role), key="choice_radio")
        if st.button("Submit Decision"):
            record(role, rnd-1, choice)
            st.experimental_rerun()
    else:
        st.info("Decision already submitted")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"),
                 height=200, use_container_width=True)

    st.subheader("Timeline Board")
    timeline_board(rnd-1)

    # End of game recap
    if all(b is not None for b in st.session_state.timeline):
        st.balloons()
        st.success("GAME OVER")
        for r in ROLES:
            st.write(f"### {r}")
            st.dataframe(st.session_state.data[r],
                         use_container_width=True)
        total_cost = st.session_state.kpi["Cost"].sum()
        final_time = max(b["End"].max() for b in st.session_state.timeline)
        st.info(f"Final Cost ${total_cost:,.0f} | Ground Time {final_time} min")
