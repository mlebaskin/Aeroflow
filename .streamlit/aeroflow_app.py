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
    ("Wildlife on the runway – AODB triggers ‘bird hazard’ flag.", 8),
    ("Fuel truck stuck in traffic – AODB stand occupancy extends.", 12),
    ("Half the ramp crew called in sick – Ops delays loading.", 9),
    ("Snow squall – De-icing entry added to AODB.", 15),
    ("Baggage belt jam – bags everywhere.", 7),
    ("Gate power outage – stand unavailable in AODB.", 10),
    ("Catering cart spills tomato soup on luggage.", 6),
    ("Lightning overhead – ground ops paused.", 11),
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
        st.session_state.round    = 1
init_state()

# ---------- LOGIC ----------
def everyone_done(i): 
    return all(st.session_state.data[r].at[i,"Decision"]!="-" for r in ROLES)

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
            st.session_state.data[r].at[i,"Cost"] += fine

def record(role,i,choice):
    df=st.session_state.data[role]
    if role==ROLES[0]:
        if "Dedicated" in choice:
            dur,cost,note = GATE_PVT,GATE_FEE,"Reserved stand"
        else:
            dur,cost,note = GATE_SHR,0,"Shared stand"
            if random.random()<0.5: dur+=10; note+=" (+10 clash)"
    elif role==ROLES[1]:
        if "Quick" in choice:
            dur,cost,note = CREW_NB,0,"Quick swap"
            if random.random()<0.4: dur+=15; note+=" (+15 crew delay)"
        else:
            dur,cost,note = CREW_B10,0,"Buffered swap"
    else:
        if "Fix Now" in choice:
            dur,cost,note = MX_FIX, MX_FIX_COST, "Immediate fix"
        else:
            dur,cost,note = MX_DEF, 0, "Deferred"
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
        f"Target {ON_TIME_MIN} min  |  Fine ${FINE_PER_MIN}/min\n"
        f"Gate fee ${GATE_FEE}  |  Fix-now ${MX_FIX_COST}\n"
        f"Defer risk 40 % → ${MX_PENALTY}"
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

def opts(role):
    if role==ROLES[0]:
        return ("AODB: Dedicated Stand ($500 – guaranteed gate)",
                "AODB: Shared Stand (free – 50 % chance +10 min wait)")
    if role==ROLES[1]:
        return ("CRS: Quick Crew Swap (30 min – 40 % chance +15 min)",
                "CRS: Buffered Crew Swap (40 min – delay-proof)")
    return ("MEL: Fix Now (+20 min, $300)",
            "MEL: Defer (0 min – 40 % $1k penalty)")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play","Play"])

with tab_help:
    st.header("Your Mission")
    st.markdown(
        "Turn five delayed flights **fast _and_ cheap**.  \n"
        "• Each round you update three live information systems:  **AODB** (gate/stand), "
        "**CRS** (crew rostering), and the **MEL** (defect log).  \n"
        "• A perfect turnaround is **45 minutes**.  Go over and every extra minute "
        "adds **$100** to _your_ bill.  \n"
        "Paying fees can prevent delay—but spend too freely and you’ll go broke. "
        "Find the sweet spot!"
    )

    st.subheader("Each Round, step by step")
    st.markdown(
        "1. **AODB stand assignment** – Reserve a **Dedicated Stand** (you pay for a private gate; "
        "no waiting) or choose **Shared Stand** (free, but there’s a 50 % chance another plane is "
        "still there, forcing you to wait **+10 min**).  \n"
        "2. **CRS crew plan** – **Quick Swap** schedules a tight 30-minute crew change; fast, "
        "but if the relief crew runs late (40 % chance) you lose **+15 min**.  "
        "**Buffered Swap** blocks 40 minutes, adding a built-in buffer so delay can’t happen.  \n"
        "3. **MEL decision** – **Fix Now** means mechanics spend 20 min and \$300 to clear the "
        "defect; safe but slower.  **Defer** logs the defect in the MEL: zero minutes now, "
        "but there’s a 40 % chance compliance audits fine you **\$1 000** later.  \n"
        "4. Click **Submit Decision** – your MIS writes flow to the next role and the timeline "
        "shows the combined ground time."
    )

    st.header("Roles & Options")
    st.markdown(
        "- **Airport Operations – Ramp Ringleader**  \n"
        "  Updates the *StandOccupancy* table in **AODB** and manages ground equipment.  \n"
        "  • AODB: Dedicated Stand – pay $500, zero conflict.  \n"
        "  • AODB: Shared Stand – free, 50 % chance another flight bumps you (+10 min).\n\n"
        "- **Airline Control Center – Dispatch DJ**  \n"
        "  Writes crew records to **CRS** and files the flight plan.  \n"
        "  • CRS: Quick Crew Swap – 30 min, 40 % chance of relief-crew delay (+15 min).  \n"
        "  • CRS: Buffered Swap – always 40 min; no last-minute surprises.\n\n"
        "- **Aircraft Maintenance – Wrench Wizards**  \n"
        "  Logs actions in the **MEL** defect database.  \n"
        "  - MEL: Fix Now – add 20 min and pay $300.  \n"
        "  - MEL: Defer – 0 min now, 40 % chance of a $1 000 penalty."
    )

    st.subheader("Acronyms Cheat-Sheet")
    st.markdown(
        "- **AODB** – Airport Operational Data Base (gate/stand records)  \n"
        "- **CRS** – Crew Rostering System (who flies which leg)  \n"
        "- **MEL** – Minimum Equipment List (approved deferred defects)"
    )
    st.markdown(f"*Every minute past **{ON_TIME_MIN}** costs **you** **${FINE_PER_MIN}**.*")

with tab_play:
    rnd=st.session_state.round
    role=st.sidebar.selectbox("Your Role", ROLES)
    sidebar(role,rnd); kpi_strip(role)

    evt_txt,evt_delay=st.session_state.events[rnd-1]
    st.warning(f"{evt_txt}\n(+{evt_delay} min)")

    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice=st.radio("Make your MIS update:", opts(role))
        st.caption("This update cascades to the next system in sequence.")
        if st.button("Submit Decision"):
            record(role,rnd-1,choice); st.rerun()
    else:
        st.info("Decision already submitted.")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"))

    st.subheader("Timeline Board")
    board=next((b for b in reversed(st.session_state.timeline) if b is not None), None)
    if board is not None:
        st.dataframe(board)
    else:
        st.info("Waiting for first round to complete...")

    if all(b is not None for b in st.session_state.timeline):
        st.balloons(); st.success("GAME OVER")
        summary=pd.DataFrame({
            "Role":ROLES,
            "Total $":[int(st.session_state.data[r]["Cost"].sum()) for r in ROLES]
        }).sort_values("Total $").reset_index(drop=True)
        st.table(summary)
