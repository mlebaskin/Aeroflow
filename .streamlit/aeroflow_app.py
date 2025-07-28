import random, pandas as pd, streamlit as st
from typing import List

# ---------- CONFIG ----------
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100
GATE_PVT, GATE_SHR = 10, 10
CREW_NB, CREW_B10  = 30, 40
MX_FIX,  MX_DEF    = 20, 0
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway - shooing birds takes time!", 8),
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
                "Round": range(1, ROUNDS + 1),
                "Decision": ["-"] * ROUNDS,
                "Duration": [0] * ROUNDS,
                "Cost":     [0] * ROUNDS,
                "Notes":    [""] * ROUNDS
            }) for r in ROLES
        }
        st.session_state.events   = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline = [None] * ROUNDS
        st.session_state.round    = 1
init_state()

# ---------- LOGIC ----------
def everyone_done(i): 
    return all(st.session_state.data[r].at[i,"Decision"]!="-" for r in ROLES)

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

    excess = max(mx_end - ON_TIME_MIN, 0)
    fine   = excess * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.data[r].at[i,"Cost"] += fine

def record(role, i, choice):
    df = st.session_state.data[role]
    if role == ROLES[0]:
        dur,cost,note = (GATE_PVT,GATE_FEE,"Private gate") if choice=="Private Gate" \
                        else (GATE_SHR,0,"Shared gate")
        if choice=="Shared Gate" and random.random()<0.5:
            dur += 10; note += " (+10 clash)"
    elif role == ROLES[1]:
        dur,cost,note = (CREW_NB,0,"No buffer") if choice=="No Buffer" \
                        else (CREW_B10,0,"Buffer 10")
        if choice=="No Buffer" and random.random()<0.4:
            dur += 15; note += " (+15 late crew)"
    else:
        if choice=="Fix Now": dur,cost,note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur,cost,note = MX_DEF, 0, "Defer"
            if random.random()<MX_PEN_PROB:
                cost += MX_PENALTY; note += " Penalty $1k"
            else:
                note += " No penalty"
    df.loc[i,["Decision","Duration","Cost","Notes"]] = [choice,dur,int(cost),note]
    if everyone_done(i):
        build_timeline(i)
        st.session_state.round = min(i+2, ROUNDS)

def latest_time(): 
    boards=[b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

# ---------- UI HELPERS ----------
def sidebar(role,rnd):
    st.sidebar.header(f"Round {rnd} - {role}")
    st.sidebar.text(
        f"Goal ≤ {ON_TIME_MIN} min\n"
        f"Fine ${FINE_PER_MIN}/min to YOU\n"
        f"Gate fee ${GATE_FEE}\n"
        f"Fix-now ${MX_FIX_COST}\n"
        f"Defer risk 40% → ${MX_PENALTY}"
    )
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"):
                st.session_state.round=min(rnd+1,ROUNDS); st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

def kpi_strip(role):
    st.metric("Your Cost", f"${int(st.session_state.data[role]['Cost'].sum()):,}")
    st.metric("Latest Ground Time", f"{latest_time()} min",
              delta=f"{latest_time()-ON_TIME_MIN:+}")

def opts(role):
    return ("Private Gate","Shared Gate") if role==ROLES[0] else \
           ("No Buffer","Buffer 10")      if role==ROLES[1] else ("Fix Now","Defer")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play","Play"])

with tab_help:
    st.header("Your Mission")
    st.markdown(
        "Five inbound jets are running **late**, and the CEO is glued to the delay board.  \n"
        "Across **five rounds** you’ll wear all three ground-crew hats — pick **one option for "
        "each role every round**, then watch the chaos unfold.  \n"
        "Every minute beyond **45** slaps **you** with a $100 fine. "
        "Finish Round 5 with the lowest bill and bask in eternal airport glory."
    )
    st.subheader("Each round, you will…")
    st.markdown(
        "1. Choose a **Gate** plan for Airport Ops.  \n"
        "2. Choose a **Crew** plan for Airline Control.  \n"
        "3. Choose **Fix Now / Defer** for Maintenance.  \n"
        "4. Click **Submit Decision**.  \n"
        "5. Watch the timeline board ripple—then repeat."
    )
    st.header("Roles & Options")
    st.markdown(
        "- **Airport Operations – Ramp Ringleader**  \n"
        "  You marshal the jet, hook up power, unload bags, and chase rogue geese.  \n"
        "  • **Private Gate** – pay $500, zero conflict.  \n"
        "  • **Shared Gate** – free, **50 % chance** another flight bumps you (+10 min).\n\n"
        "- **Airline Control Center – Dispatch DJ**  \n"
        "  You juggle crew calls and flight plans while sipping burnt coffee.  \n"
        "  • **No Buffer** – 30-min swap, **40 % chance** the relief crew is late (+15 min).  \n"
        "  • **Buffer 10** – safer, always 40 min (adds 10 min but no surprises).\n\n"
        "- **Aircraft Maintenance – Wrench Wizards**  \n"
        "  You tackle pilot snags, from sticky flaps to broken coffee makers.  \n"
        "  - **Fix Now** – add 20 min and pay $300.  \n"
        "  - **Defer** – zero minutes now, 40 % chance of a $1 000 penalty later."
    )
    st.markdown(f"*Every minute past **{ON_TIME_MIN}** costs **you** **${FINE_PER_MIN}**.*")

with tab_play:
    rnd = st.session_state.round
    role = st.sidebar.selectbox("Your Role", ROLES)
    sidebar(role,rnd); kpi_strip(role)

    evt_txt, evt_delay = st.session_state.events[rnd-1]
    st.warning(f"{evt_txt}\n(+{evt_delay} min)")

    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice = st.radio("Choose:", opts(role))
        if st.button("Submit Decision"):
            record(role,rnd-1,choice); st.rerun()
    else:
        st.info("Decision already submitted")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"))

    st.subheader("Timeline Board")
    board = st.session_state.timeline[rnd-1]
    if board is not None:
        st.dataframe(board)
    else:
        st.info("Waiting for remaining roles...")

    if all(b is not None for b in st.session_state.timeline):
        st.balloons(); st.success("GAME OVER")
        summary = pd.DataFrame({
            "Role": ROLES,
            "Total $": [int(st.session_state.data[r]["Cost"].sum()) for r in ROLES]
        }).sort_values("Total $").reset_index(drop=True)
        st.table(summary)
