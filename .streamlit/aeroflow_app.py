import random, pandas as pd, streamlit as st
from typing import List

# ---------- CONFIG ----------
ROLES = [
    "Airport Operations",     # ramp crew boss
    "Airline Control Center", # dispatch desk
    "Aircraft Maintenance"    # tech crew
]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Baseline minutes
GATE_PVT, GATE_SHR = 10, 10
CREW_NB,  CREW_B10 = 30, 40
MX_FIX,   MX_DEF   = 20, 0

# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway - shooing birds burns minutes!", 8),
    ("Fuel truck stuck in traffic - thirsty jet waits.", 12),
    ("Half the ramp crew called in sick - slow loading.", 9),
    ("Snow squall - de-icing bath commences.", 15),
    ("Baggage belt jam - bags everywhere.", 7),
    ("Gate power outage - lights out until breaker flips.", 10),
    ("Catering cart dumps tomato soup on luggage.", 6),
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
        st.session_state.timeline = [None] * ROUNDS
        st.session_state.kpi      = pd.DataFrame(index=ROLES,
                                   columns=["Delay","Cost"]).fillna(0)
        st.session_state.round    = 1
init_state()

# ---------- LOGIC ----------
def everyone_done(i): return all(st.session_state.data[r].at[i,"Decision"]!="-" for r in ROLES)

def build_timeline(i):
    evt_txt, evt_delay = st.session_state.events[i]
    rows, start = [], 0

    ap = st.session_state.data[ROLES[0]].loc[i]; ap_end = start + ap.Duration + evt_delay
    rows.append([ROLES[0], start, ap_end])

    ac = st.session_state.data[ROLES[1]].loc[i]; ac_end = ap_end + ac.Duration
    rows.append([ROLES[1], ap_end, ac_end])

    mx = st.session_state.data[ROLES[2]].loc[i]; mx_end = ac_end + mx.Duration
    rows.append([ROLES[2], ac_end, mx_end])

    st.session_state.timeline[i] = pd.DataFrame(rows, columns=["Role","Start","End"])

    overshoot = max(mx_end - ON_TIME_MIN, 0)
    fine = overshoot * FINE_PER_MIN
    if fine:
        for r in ROLES: st.session_state.data[r].at[i,"Cost"] += fine / 3

    for r in ROLES:
        df = st.session_state.data[r]
        st.session_state.kpi.at[r,"Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r,"Cost"]  = df["Cost"].sum()

def record(role, idx, choice):
    df = st.session_state.data[role]
    # Airport Ops
    if role == ROLES[0]:
        dur,cost,note = (GATE_PVT,GATE_FEE,"Private gate") if choice=="Private Gate" else (GATE_SHR,0,"Shared gate")
        if choice=="Shared Gate" and random.random()<0.5:
            dur += 10; note += " (+10 clash)"
    # Airline Control
    elif role == ROLES[1]:
        dur,cost,note = (CREW_NB,0,"No buffer") if choice=="No Buffer" else (CREW_B10,0,"Buffer 10")
        if choice=="No Buffer" and random.random()<0.4:
            dur += 15; note += " (+15 late crew)"
    # Maintenance
    else:
        if choice=="Fix Now": dur,cost,note = MX_FIX, MX_FIX_COST, "Fixed now"
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

def latest_time():
    boards = [b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

# ---------- UI HELPERS ----------
def sidebar(role,rnd):
    st.sidebar.header(f"Round {rnd} - {role}")
    st.sidebar.text(
        f"Goal <= {ON_TIME_MIN} min\n"
        f"Delay fine ${FINE_PER_MIN}/min\n"
        f"Gate fee ${GATE_FEE}\n"
        f"Fix-now ${MX_FIX_COST}\n"
        f"Defer risk 40% > ${MX_PENALTY}")
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"): st.session_state.round=min(rnd+1,ROUNDS); st.experimental_rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.experimental_rerun()

def kpi_strip():
    tot = st.session_state.kpi["Cost"].sum()
    lat = latest_time()
    c1,c2 = st.columns(2)
    c1.metric("Team Cost", f"${tot:,.0f}")
    c2.metric("Latest Ground Time", f"{lat} min", delta=f"{lat-ON_TIME_MIN:+}")

def decision_options(role):
    return ("Private Gate","Shared Gate") if role==ROLES[0] else \
           ("No Buffer","Buffer 10")      if role==ROLES[1] else ("Fix Now","Defer")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫", layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

# Put How-to left, Play right
tab_help, tab_play = st.tabs(["How to Play","Play"])

with tab_help:
    st.header("Meet the Crew")
    st.markdown(
        "- Airport Operations: Ramp ringleader. Drives belt-loaders, dodges rogue seagulls, and shouts \"Clear to push!\".\n"
        "  * Private Gate (no conflict, $500)\n"
        "  * Shared Gate (free, 50% +10-min clash)\n\n"
        "- Airline Control Center: Dispatch DJ. Juggles crew schedules like flaming batons.\n"
        "  * No Buffer (fast, 40% +15-min risk)\n"
        "  * Buffer 10 (safe, adds 10 min)\n\n"
        "- Aircraft Maintenance: Wrench wizard. Duct tape hero with a clipboard.\n"
        "  * Fix Now (+20 min, $300)\n"
        "  * Defer (0 min, 40% $1k penalty)\n\n"
        f"Remember: every minute beyond **{ON_TIME_MIN}** costs the team **${FINE_PER_MIN}** (split across all roles)."
    )

with tab_play:
    rnd  = st.session_state.round
    role = st.sidebar.selectbox("Your Role", ROLES)
    sidebar(role,rnd); kpi_strip()

    evt_txt, evt_delay = st.session_state.events[rnd-1]
    st.warning(f"{evt_txt}\n(+{evt_delay} min)")

    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice = st.radio("Choose:", decision_options(role))
        if st.button("Submit"):
            record(role, rnd-1, choice)
            st.experimental_rerun()
    else:
        st.info("Decision already submitted.")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"))

    st.subheader("Timeline Board")
    board = st.session_state.timeline[rnd-1]
    if board is not None:
        st.dataframe(board)
    else:
        st.info("Waiting for other roles...")

    if all(b is not None for b in st.session_state.timeline):
        st.balloons()
        st.success("GAME OVER")
        for r in ROLES:
            st.write(f"### {r}")
            st.dataframe(st.session_state.data[r])
        final_cost = st.session_state.kpi["Cost"].sum()
        final_time = latest_time()
        st.info(f"Final Cost ${final_cost:,.0f}   |   Ground Time {final_time} min")
