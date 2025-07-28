"""MMIS 494 Aviation MIS Simulation – Integrated Timeline (v1.6.1)

Bug-fix: no Styler objects sent to Streamlit (no more DeltaGenerator dumps).
UI: plain sidebar, round banner, KPI strip, tidy DataFrames, GAME OVER recap.
"""

import random, pandas as pd, streamlit as st
from typing import List

# ---------- CONFIG ----------
ROLES = [
    "Airport Operations",     # gate & ramp
    "Airline Control Center", # crews & dispatch
    "Aircraft Maintenance"    # tech crew
]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Minutes for baseline tasks
GATE_PVT, GATE_SHR = 10, 10
CREW_NB, CREW_B10  = 30, 40
MX_FIX,  MX_DEF    = 20, 0

# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway—bird-shooing takes time!", 8),
    ("Fuel truck stuck in traffic—jet waits thirsty.", 12),
    ("Half the ramp crew called in sick—slow loading.", 9),
    ("Snow squall—de-icing bath in minty glycol.", 15),
    ("Baggage belt jam—bags raining onto the ramp!", 7),
    ("Gate power outage—technicians flip breakers.", 10),
    ("Catering cart dumps tomato soup on luggage.", 6),
    ("Lightning overhead—ramp ops paused until clear.", 11),
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
        st.session_state.timeline = [None] * ROUNDS      # round → DataFrame
        st.session_state.kpi      = pd.DataFrame(index=ROLES,
                                   columns=["Delay","Cost"]).fillna(0)
        st.session_state.round    = 1
init_state()

# ---------- CORE LOGIC ----------
def everyone_done(idx:int)->bool:
    return all(st.session_state.data[r].at[idx,"Decision"]!="-" for r in ROLES)

def build_timeline(idx:int):
    evt_txt,evt_delay = st.session_state.events[idx]
    rows = []
    start = 0

    ap = st.session_state.data[ROLES[0]].loc[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append([ROLES[0], start, ap_end])

    ac = st.session_state.data[ROLES[1]].loc[idx]
    ac_end = ap_end + ac.Duration
    rows.append([ROLES[1], ap_end, ac_end])

    mx = st.session_state.data[ROLES[2]].loc[idx]
    mx_end = ac_end + mx.Duration
    rows.append([ROLES[2], ac_end, mx_end])

    board = pd.DataFrame(rows, columns=["Role","Start","End"])
    st.session_state.timeline[idx] = board

    excess = max(mx_end - ON_TIME_MIN, 0)
    fine   = excess * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.data[r].at[idx,"Cost"] += fine / 3

    for r in ROLES:
        df = st.session_state.data[r]
        st.session_state.kpi.at[r,"Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r,"Cost"]  = df["Cost"].sum()

def record_decision(role:str, idx:int, choice:str):
    df = st.session_state.data[role]

    if role == ROLES[0]:  # Airport Ops
        dur,cost,note = (GATE_PVT,GATE_FEE,"Private gate") if choice=="Private Gate" \
                     else (GATE_SHR,0,"Shared gate")
        if choice=="Shared Gate" and random.random()<0.5:
            dur += 10; note += " (+10 clash)"
    elif role == ROLES[1]:  # Airline Control
        dur,cost,note = (CREW_NB,0,"No buffer") if choice=="No Buffer" \
                     else (CREW_B10,0,"Buffer 10")
        if choice=="No Buffer" and random.random()<0.4:
            dur += 15; note += " (+15 late crew)"
    else:  # Maintenance
        if choice=="Fix Now":
            dur,cost,note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur,cost,note = MX_DEF, 0, "Defer"
            if random.random()<MX_PEN_PROB:
                cost += MX_PENALTY; note += " – Penalty $1k"
            else:
                note += " – No penalty"

    df.loc[idx,["Decision","Duration","Cost","Notes"]] = [choice,dur,cost,note]

    if everyone_done(idx):
        build_timeline(idx)
        st.session_state.round = min(idx+2, ROUNDS)

def latest_ground_time()->int:
    boards=[b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

def game_over()->bool:
    if st.session_state.round <= ROUNDS-1: return False
    return all("-" not in df["Decision"].values for df in st.session_state.data.values())

# ---------- UI HELPERS ----------
def sidebar(role:str,rnd:int):
    st.sidebar.header(f"Round {rnd} – {role}")
    st.sidebar.write(
        f"Goal ≤ {ON_TIME_MIN} min    |    Delay fine ${FINE_PER_MIN}/min\n"
        f"Gate fee ${GATE_FEE}  |  Fix-now ${MX_FIX_COST}\n"
        f"Defer risk 40 % → ${MX_PENALTY}")
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Pwd", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"): st.session_state.round = min(rnd+1,ROUNDS); st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()): del st.session_state[k]; st.rerun()

def kpi_strip():
    tot_cost = st.session_state.kpi["Cost"].sum()
    col1,col2 = st.columns(2)
    col1.metric("💸 Team Cost", f"${tot_cost:,.0f}")
    col2.metric("⏱️ Last Ground Time", f"{latest_ground_time()} min",
                delta=f"{latest_ground_time()-ON_TIME_MIN:+}")

# ---------- STREAMLIT PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_play, tab_help = st.tabs(["Play","How to Play"])

with tab_help:
    st.header("Role Briefs")
    st.markdown(
        "- **Airport Operations** – ramp & gate tasks  \n"
        "  • Private Gate (no conflict, $500)  \n"
        "  • Shared Gate (free, 50% +10 min)\n\n"
        "- **Airline Control Center** – crews & dispatch  \n"
        "  • No Buffer (fast, 40% +15 min)  \n"
        "  • Buffer 10 (safe, +10 min)\n\n"
        "- **Aircraft Maintenance** – mechanical fixes  \n"
        "  • Fix Now (+20 min, $300)  \n"
        "  • Defer (0 min, 40% $1k)\n\n"
        f"Delay over **{ON_TIME_MIN} min** costs the team **${FINE_PER_MIN}** per minute."
    )

with tab_play:
    rnd  = st.session_state.round
    role = st.sidebar.selectbox("Your Role", ROLES)
    sidebar(role,rnd); kpi_strip()

    evt_txt,evt_delay = st.session_state.events[rnd-1]
    st.warning(f"{evt_txt}\n\n(+{evt_delay} min)")

    # Decision area
    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        opts = ("Private Gate","Shared Gate") if role==ROLES[0] else \
               ("No Buffer","Buffer 10")       if role==ROLES[1] else \
               ("Fix Now","Defer")
        choice = st.radio("Choose:", opts, key="choice")
        if st.button("Submit Decision"):
            record_decision(role, rnd-1, choice)
            st.rerun()
    else:
        st.info("Decision already submitted.")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role]
                 .drop(columns="Round"), height=200)

    st.subheader("Timeline Board")
    board = st.session_state.timeline[rnd-1]
    st.dataframe(board) if board is not None else st.info("Waiting for other roles...")

    # Game over recap
    if game_over():
        st.balloons()
        st.success("🏁 GAME OVER")
        for r in ROLES:
            st.write(f"#### {r}")
            st.dataframe(st.session_state.data[r])
        tot = st.session_state.kpi["Cost"].sum()
        fin_time = latest_ground_time()
        st.info(f"Final Team Cost: ${tot:,.0f} | Final Ground Time: {fin_time} min")
