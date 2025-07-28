import random, pandas as pd, streamlit as st
from typing import List

# ---------- CONFIG ----------
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Task baselines (minutes)
GATE_PVT, GATE_SHR = 10, 10
CREW_NB, CREW_B10  = 30, 40
MX_FIX,  MX_DEF    = 20, 0

# Costs ($)
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4      # 40 % risk when deferring

EVENT_CARDS = [
    ("Wildlife on the runway – AODB triggers ‘bird hazard’ flag.", 8),
    ("Fuel truck stuck in traffic – AODB stand occupancy extends.", 12),
    ("Half the ramp crew called in sick – Ops delays loading.", 9),
    ("Snow squall – De-icing record added to AODB.", 15),
    ("Baggage belt jam – bags everywhere.", 7),
    ("Gate power outage – stand unavailable in AODB.", 10),
    ("Catering cart spills tomato soup on luggage.", 6),
    ("Lightning overhead – ground ops paused.", 11),
]

# Instructor secret
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
        st.session_state.round    = 1
init_state()

# ---------- LOGIC ----------
def everyone_done(i): 
    return all(st.session_state.data[r].at[i,"Decision"]!="-"
               for r in ROLES)

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
    fine  =excess*FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.data[r].at[i,"Cost"]+=fine  # each role pays

def record(role,i,choice):
    df=st.session_state.data[role]
    if role==ROLES[0]:  # Airport Ops
        if "Dedicated" in choice:
            dur,cost,note = GATE_PVT,GATE_FEE,"AODB reserved stand"
        else:
            dur,cost,note = GATE_SHR,0,"AODB shared stand"
            if random.random()<0.5:
                dur+=10; note+=" (+10 clash)"
    elif role==ROLES[1]:  # Airline Control
        if "Quick" in choice:
            dur,cost,note = CREW_NB,0,"CRS quick swap"
            if random.random()<0.4: dur+=15; note+=" (+15 crew delay)"
        else:
            dur,cost,note = CREW_B10,0,"CRS buffered swap"
    else:  # Maintenance
        if "Fix Now" in choice:
            dur,cost,note = MX_FIX,MX_FIX_COST,"MEL immediate fix"
        else:
            dur,cost,note = MX_DEF,0,"MEL defer"
            if random.random()<MX_PEN_PROB:
                cost+=MX_PENALTY; note+=" penalty $1k"
            else: note+=" no penalty"
    df.loc[i,["Decision","Duration","Cost","Notes"]] = [choice,dur,int(cost),note]
    if everyone_done(i): build_timeline(i); st.session_state.round=min(i+2,ROUNDS)

def latest_time():
    boards=[b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

# ---------- UI HELPERS ----------
def sidebar(role,rnd):
    st.sidebar.header(f"Round {rnd} – {role}")
    st.sidebar.text(
        f"On-time target  {ON_TIME_MIN} min\n"
        f"Fine            ${FINE_PER_MIN}/min\n"
        f"Gate fee        ${GATE_FEE}\n"
        f"Fix-now         ${MX_FIX_COST}\n"
        f"Defer risk      40 % → ${MX_PENALTY}"
    )
    with st.sidebar.expander("Instructor"):
        pw=st.text_input("Password",type="password")
        if pw==INSTRUCTOR_PW:
            if st.button("Next Round"):
                st.session_state.round=min(rnd+1,ROUNDS); st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.rerun()

def kpi_strip(role):
    st.metric("Your Cost", f"${int(st.session_state.data[role]['Cost'].sum()):,}")
    st.metric("Latest Ground Time", f"{latest_time()} min",
              delta=f"{latest_time()-ON_TIME_MIN:+}")

# Choice labels
def opts(role):
    if role==ROLES[0]:
        return ("AODB: Dedicated Stand  ($500)",
                "AODB: Shared Stand     (50 % +10 min)")
    if role==ROLES[1]:
        return ("CRS: Quick Crew Swap   (40 % +15 min)",
                "CRS: Buffered Swap     (+10 min)")
    return ("MEL: Fix Now (+20 min, $300)",
            "MEL: Defer   (40 % $1k penalty)")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play","Play"])

# -----  HELP  -----
with tab_help:
    st.header("Your Mission")
    st.markdown(
        "Five inbound jets are **late**. For **five rounds** you’ll update real aviation MIS systems:  \n"
        "**AODB** (Airport Operational Data Base), **CRS** (Crew Rostering System), and the **MEL** "
        "(Minimum Equipment List). Every minute beyond **45** slaps **you** with a $100 fine. "
        "Finish Round 5 with the lowest bill."
    )
    st.subheader("Each Round")
    st.markdown(
        "1. Reserve a stand in **AODB**.  \n"
        "2. Pick a crew plan in **CRS**.  \n"
        "3. Decide **Fix/Defer** in the **MEL**.  \n"
        "4. Click **Submit Decision** → timeline refreshes."
    )
    st.header("Roles & Options")
    st.markdown(
        "- **Airport Operations – Ramp Ringleader**  \n"
        "  Updates AODB stand records and chases wildlife.  \n"
        "  • AODB: Dedicated Stand – pay $500, zero clash.  \n"
        "  • AODB: Shared Stand – free, 50 % chance of a +10-min stand clash.\n\n"
        "- **Airline Control Center – Dispatch DJ**  \n"
        "  Writes crew swaps to CRS.  \n"
        "  • CRS: Quick Crew Swap – 30 min, 40 % chance of +15 min delay.  \n"
        "  • CRS: Buffered Swap – 40 min, delay-proof.\n\n"
        "- **Aircraft Maintenance – Wrench Wizards**  \n"
        "  Logs actions in the MEL database.  \n"
        "  - MEL: Fix Now – add 20 min and pay $300.  \n"
        "  - MEL: Defer – 0 min now, 40 % chance of a $1 000 penalty."
    )
    st.subheader("Acronyms Cheat-Sheet")
    st.markdown(
        "- **AODB** – Airport Operational Data Base (gates, stands, resources).  \n"
        "- **CRS** – Crew Rostering / Scheduling System.  \n"
        "- **MEL** – Minimum Equipment List database for deferred defects."
    )
    st.markdown(f"*Delay past **{ON_TIME_MIN}** min costs **you** **${FINE_PER_MIN}** per minute.*")

# -----  PLAY  -----
with tab_play:
    rnd=st.session_state.round
    role=st.sidebar.selectbox("Your Role", ROLES)
    sidebar(role,rnd); kpi_strip(role)

    evt_txt,evt_delay=st.session_state.events[rnd-1]
    st.warning(f"{evt_txt}\n(+{evt_delay} min)")

    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice = st.radio("Make your MIS update:", opts(role))
        st.caption("Your write propagates to the next role’s system.")
        if st.button("Submit Decision"):
            record(role,rnd-1,choice); st.rerun()
    else:
        st.info("Decision already submitted.")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"))

    st.subheader("Timeline Board")
    board=st.session_state.timeline[rnd-1]
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
