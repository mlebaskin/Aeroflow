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
# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway – AODB triggers “bird hazard”.", 8),
    ("Fuel truck stuck in traffic – stand occupancy extends.", 12),
    ("Half the ramp crew called in sick – loading slowed.", 9),
    ("Snow squall – de-icing entry added to AODB.", 15),
    ("Baggage belt jam – bags everywhere.", 7),
    ("Gate power outage – stand unavailable in AODB.", 10),
    ("Catering cart spills tomato soup on luggage.", 6),
    ("Lightning overhead – ground ops paused.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ---------- STATE ----------
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {r: pd.DataFrame({
            "Round": range(1, ROUNDS+1),
            "Decision": ["-"]*ROUNDS,
            "Duration": [0]*ROUNDS,
            "Cost": [0]*ROUNDS,
            "Notes": [""]*ROUNDS}) for r in ROLES}
        st.session_state.events   = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline = [None]*ROUNDS
        st.session_state.round    = 1
        st.session_state.role_idx = 0          # default picker index
init_state()

# ---------- LOGIC ----------
def everyone_done(i): 
    return all(st.session_state.data[r].at[i,"Decision"]!="-" for r in ROLES)

def build_timeline(i):
    txt, delay = st.session_state.events[i]
    rows, start = [], 0
    ap = st.session_state.data[ROLES[0]].loc[i]; ap_end = start + ap.Duration + delay
    rows.append([ROLES[0], start, ap_end])
    ac = st.session_state.data[ROLES[1]].loc[i]; ac_end = ap_end + ac.Duration
    rows.append([ROLES[1], ap_end, ac_end])
    mx = st.session_state.data[ROLES[2]].loc[i]; mx_end = ac_end + mx.Duration
    rows.append([ROLES[2], ac_end, mx_end])
    st.session_state.timeline[i] = pd.DataFrame(rows, columns=["Role","Start","End"])
    over = max(mx_end-ON_TIME_MIN, 0)
    fine = over * FINE_PER_MIN
    for r in ROLES:
        st.session_state.data[r].at[i,"Cost"] += fine

def record(role,i,choice):
    df = st.session_state.data[role]
    if role == ROLES[0]:                                    # Airport Ops
        if "Dedicated" in choice:
            dur,cost,note = GATE_PVT,GATE_FEE,"Reserved stand"
        else:
            extra = random.randint(5,20)
            dur,cost,note = GATE_SHR,0,f"Shared stand (+{extra} clash)" if random.random()<0.5 else ("Shared stand",0,"Shared stand – no clash")[2]
            if "clash" in note: dur += extra
    elif role == ROLES[1]:                                  # Airline Control
        if "Quick" in choice:
            extra = random.randint(5,25)
            dur,cost,note = CREW_NB,0,"Quick swap"
            if random.random()<0.4: dur += extra; note += f" (+{extra} crew delay)"
        else:
            dur,cost,note = CREW_B10,0,"Buffered swap"
    else:                                                   # Maintenance
        if "Fix Now" in choice:
            dur,cost,note = MX_FIX, MX_FIX_COST, "Immediate fix"
        else:
            dur,cost,note = MX_DEF, 0, "Deferred"
            if random.random()<MX_PEN_PROB:
                cost += MX_PENALTY; note += " penalty $1k"
            else: note += " no penalty"
    df.loc[i,["Decision","Duration","Cost","Notes"]] = [choice,dur,int(cost),note]
    if everyone_done(i):
        build_timeline(i)
        st.session_state.round = min(i+2, ROUNDS)
        st.session_state.role_idx = 0      # reset picker to Airport Ops

def latest_time():
    boards=[b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

# ---------- UI HELPERS ----------
def sidebar(role,rnd):
    st.sidebar.header(f"Flight {rnd} – {role}")
    st.sidebar.text(
        f"On-time target  {ON_TIME_MIN} min\n"
        f"Fine            ${FINE_PER_MIN}/min\n"
        f"Gate fee        ${GATE_FEE}\n"
        f"Fix-now         ${MX_FIX_COST}\n"
        f"Defer risk      40 % → ${MX_PENALTY}"
    )
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password",type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Flight"):
                st.session_state.round = min(rnd+1,ROUNDS); st.session_state.role_idx=0; st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()): del st.session_state[k]; st.rerun()

def kpi_strip(role):
    st.metric("Your Cost", f"${int(st.session_state.data[role]['Cost'].sum()):,}")
    last = latest_time()
    st.metric("Latest Ground Time", f"{last} min",
              delta=f"{last-ON_TIME_MIN:+}")

def opts(role):
    if role == ROLES[0]:
        return ("AODB: Dedicated Stand ($500 – guaranteed gate)",
                "AODB: Shared Stand (free – 50 % chance +5-20 min wait)")
    if role == ROLES[1]:
        return ("CRS: Quick Crew Swap (30 min – 40 % +5-25 min)",
                "CRS: Buffered Crew Swap (40 min – delay-proof)")
    return ("MEL: Fix Now (+20 min, $300)",
            "MEL: Defer (0 min – 40 % $1k)")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play","Play"])

# ----- HELP TAB ----
with tab_help:
    st.header("Your Mission")
    st.markdown(
        "Turn five delayed flights **fast _and_ cheap**.  \n"
        "– Each flight, you update three live systems:  **AODB** stand allocation, **CRS** crew plan, "
        "and **MEL** defect list.  \n"
        "– Perfect ground time is **45 min**; every extra minute costs **$100**.  \n"
        "Balance resource fees against unpredictable delay fines."
    )

    st.subheader("Each Round, step-by-step")
    st.markdown(
        "1. **AODB stand assignment** – Dedicated Stand (pay $500, guaranteed gate) **or** "
        "Shared Stand (free, 50 % chance the stand is still occupied; if so you wait **+5-20 min**).  \n"
        "2. **CRS crew plan** – Quick Swap (30 min; 40 % chance the relief crew is late **+5-25 min**) "
        "or Buffered Swap (40 min, no risk).  \n"
        "3. **MEL decision** – Fix Now (+20 min & $300) **or** Defer (0 min now; 40 % chance of "
        "$1 000 compliance penalty).  \n"
        "4. A **📀 Flight Event** (weather, wildlife, etc.) adds extra delay.  \n"
        "5. Click **Submit Decision** – timeline shows the total ground time and you move to the next flight."
    )

    st.header("Roles & Options")
    st.markdown(
        "- **Airport Operations – Ramp Ringleader**  \n"
        "  Updates the *StandOccupancy* table in **AODB**.  \n"
        "  • Dedicated Stand – pay $500, zero clash.  \n"
        "  • Shared Stand – free, 50 % chance +5-20 min wait.\n\n"
        "- **Airline Control Center – Dispatch DJ**  \n"
        "  Writes crew swaps to **CRS**.  \n"
        "  • Quick Swap – 30 min, 40 % chance +5-25 min delay.  \n"
        "  • Buffered Swap – always 40 min; delay-proof.\n\n"
        "- **Aircraft Maintenance – Wrench Wizards**  \n"
        "  Logs actions in the **MEL** defect DB.  \n"
        "  - Fix Now – +20 min & $300.  \n"
        "  - Defer – 0 min now; 40 % chance of $1 000 penalty."
    )

    st.subheader("Acronyms Cheat-Sheet")
    st.markdown(
        "- **AODB** – Airport Operational Data Base  \n"
        "- **CRS** – Crew Rostering System  \n"
        "- **MEL** – Minimum Equipment List"
    )
    st.markdown(f"*Every minute past **{ON_TIME_MIN}** costs **you** "
                f"**${FINE_PER_MIN}**.*")

# ----- PLAY TAB ----
with tab_play:
    rnd = st.session_state.round
    role = st.sidebar.selectbox("Your Role", ROLES, index=st.session_state.role_idx)
    sidebar(role,rnd); kpi_strip(role)

    evt_txt, evt_delay = st.session_state.events[rnd-1]
    st.warning(f"📀 **Flight Event:** {evt_txt}\n(+{evt_delay} min)")

    if st.session_state.data[role].at[rnd-1,"Decision"] == "-":
        choice = st.radio("Make your MIS update:", opts(role))
        st.caption("This update cascades to the next system.")
        if st.button("Submit Decision"):
            record(role,rnd-1,choice)
            st.session_state.role_idx = ROLES.index(role)  # remember picker pos
            st.rerun()
    else:
        st.info("Decision already submitted.")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"))

    st.subheader("Timeline Board")
    board = next((b for b in reversed(st.session_state.timeline) if b is not None), None)
    if board is not None:
        st.dataframe(board)
    else:
        st.info("Waiting for first flight to finish...")

    if all(b is not None for b in st.session_state.timeline):
        st.balloons(); st.success("GAME OVER")
        summary = pd.DataFrame({
            "Role": ROLES,
            "Total $": [int(st.session_state.data[r]["Cost"].sum()) for r in ROLES]
        }).sort_values("Total $").reset_index(drop=True)
        st.table(summary)
