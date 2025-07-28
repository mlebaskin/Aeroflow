import random, pandas as pd, streamlit as st
from typing import List

# ---------- CONFIG ----------
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100  # full fine now charged to each role
GATE_PVT, GATE_SHR = 10, 10
CREW_NB, CREW_B10  = 30, 40
MX_FIX,  MX_DEF    = 20, 0
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4  # 40 % chance of penalty

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
                "Round": range(1, ROUNDS+1),
                "Decision": ["-"]*ROUNDS,
                "Duration": [0]*ROUNDS,
                "Cost": [0]*ROUNDS,
                "Notes": [""]*ROUNDS
            }) for r in ROLES
        }
        st.session_state.events   = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline = [None]*ROUNDS
        st.session_state.round    = 1
init_state()

# ---------- LOGIC ----------
def everyone_done(i): 
    return all(st.session_state.data[r].at[i,"Decision"] != "-" for r in ROLES)

def build_timeline(i):
    evt_txt, evt_delay = st.session_state.events[i]
    rows,start=[],0
    ap=st.session_state.data[ROLES[0]].loc[i]; ap_end=start+ap.Duration+evt_delay
    rows.append([ROLES[0],start,ap_end])
    ac=st.session_state.data[ROLES[1]].loc[i]; ac_end=ap_end+ac.Duration
    rows.append([ROLES[1],ap_end,ac_end])
    mx=st.session_state.data[ROLES[2]].loc[i]; mx_end=ac_end+mx.Duration
    rows.append([ROLES[2],ac_end,mx_end])
    st.session_state.timeline[i]=pd.DataFrame(rows,columns=["Role","Start","End"])

    excess=max(mx_end-ON_TIME_MIN,0)
    fine=int(excess*FINE_PER_MIN)  # whole dollars
    if fine:
        for r in ROLES: st.session_state.data[r].at[i,"Cost"] += fine  # full fine to each role

def record(role,i,choice):
    df=st.session_state.data[role]
    if role==ROLES[0]:
        dur,cost,note=(GATE_PVT,GATE_FEE,"Private gate") if choice=="Private Gate" else (GATE_SHR,0,"Shared gate")
        if choice=="Shared Gate" and random.random()<0.5: dur+=10; note+=" (+10 clash)"
    elif role==ROLES[1]:
        dur,cost,note=(CREW_NB,0,"No buffer") if choice=="No Buffer" else (CREW_B10,0,"Buffer 10")
        if choice=="No Buffer" and random.random()<0.4: dur+=15; note+=" (+15 late crew)"
    else:
        if choice=="Fix Now": dur,cost,note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur,cost,note = MX_DEF, 0, "Defer"
            if random.random()<MX_PEN_PROB: cost+=MX_PENALTY; note+=" Penalty $1k"
            else: note+=" No penalty"
    df.loc[i,["Decision","Duration","Cost","Notes"]] = [choice,dur,int(cost),note]
    if everyone_done(i): build_timeline(i); st.session_state.round = min(i+2,ROUNDS)

def latest_time():
    boards=[b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

# ---------- UI ----------
def sidebar(role,rnd):
    st.sidebar.header(f"Round {rnd} - {role}")
    st.sidebar.text(
        f"Goal <= {ON_TIME_MIN} min\n"
        f"Late fine ${FINE_PER_MIN}/min (each)\n"
        f"Gate fee ${GATE_FEE}\n"
        f"Fix-now ${MX_FIX_COST}\n"
        f"Defer risk 40% -> ${MX_PENALTY}")
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"): st.session_state.round=min(rnd+1,ROUNDS); st.rerun()
            if st.button("Reset Game"): 
                for k in list(st.session_state.keys()): del st.session_state[k]; st.rerun()

def kpi_strip(role):
    my_cost = st.session_state.data[role]["Cost"].sum()
    last_time = latest_time()
    c1,c2 = st.columns(2)
    c1.metric("Your Cost", f"${my_cost:,.0f}")
    c2.metric("Latest Ground Time", f"{last_time} min", delta=f"{last_time-ON_TIME_MIN:+}")

def opts(role):
    return ("Private Gate","Shared Gate") if role==ROLES[0] else \
           ("No Buffer","Buffer 10") if role==ROLES[1] else ("Fix Now","Defer")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play","Play"])

with tab_help:
    st.header("Your Mission:")
    st.markdown(
        "Turn **five** delayed flights fast while spending the least money. "
        "Every minute beyond 45 triggers a $100 fine — **charged to you**."
    )
    st.markdown(
        "**How to play:**\n"
        "1. Pick an option for your role each round.\n"
        "2. Airport Ops runs first, then Airline Control, then Maintenance.\n"
        "3. Watch delays stack on the timeline board.\n"
        "4. After Round 5, lowest total dollars wins bragging rights.\n"
    )
    st.header("Meet the Crew")
    st.markdown(
        "- Airport Ops – Ramp ringleader.\n"
        "  - Private Gate ($500, zero conflict)\n"
        "  - Shared Gate ($0, 50 % chance of +10 min)\n\n"
        "- Airline Control – Dispatch DJ.\n"
        "  - No Buffer (fast, 40 % chance of +15 min)\n"
        "  - Buffer 10 (safe, adds 10 min)\n\n"
        "- Aircraft Maintenance – Wrench wizard.\n"
        "  - Fix Now (+20 min, $300)\n"
        "  - Defer (0 min, 40 % chance of $1 000 penalty)\n\n"
        f"*Delay past {ON_TIME_MIN} min costs **you** ${FINE_PER_MIN} per minute.*"
    )

with tab_play:
    rnd=st.session_state.round
    role=st.sidebar.selectbox("Your Role", ROLES)
    sidebar(role,rnd); kpi_strip(role)

    evt_txt, evt_delay = st.session_state.events[rnd-1]
    st.warning(f"{evt_txt}\n(+{evt_delay} min)")

    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice = st.radio("Choose:", opts(role))
        if st.button("Submit Decision"): 
            record(role, rnd-1, choice); st.rerun()
    else: st.info("Decision submitted")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"), height=200)

    st.subheader("Timeline Board")
    board=st.session_state.timeline[rnd-1]
    st.dataframe(board) if board is not None else st.info("Waiting for others...")

    if all(b is not None for b in st.session_state.timeline):
        st.balloons(); st.success("GAME OVER")
        # Scoreboard
        summary = pd.DataFrame({
            "Role": ROLES,
            "Total $": [int(st.session_state.data[r]["Cost"].sum()) for r in ROLES]
        }).sort_values("Total $")
        st.table(summary.reset_index(drop=True))
