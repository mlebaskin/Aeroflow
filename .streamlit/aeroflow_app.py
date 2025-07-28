import random, pandas as pd, streamlit as st

# ---------- CONFIG ----------
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
TARGET_MIN = 45
FINE_PER_MIN = 100

GATE_PVT, GATE_SHR = 10, 10          # minutes
CREW_NB, CREW_B10  = 30, 40
MX_FIX,  MX_DEF    = 20, 0

GATE_FEE = 500                       # dollars
MX_FIX_COST = 300
MX_PENALTY  = 1000
MX_PEN_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway – bird-hazard alert.", 8),
    ("Fuel truck stuck in traffic – stand occupancy extends.", 12),
    ("Half the ramp crew called in sick – loading slowed.", 9),
    ("Snow squall – extra de-icing logged.", 15),
    ("Baggage belt jam – bags everywhere.", 7),
    ("Gate power outage – stand unavailable.", 10),
    ("Catering cart spills tomato soup on luggage.", 6),
    ("Lightning overhead – ground ops paused.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ---------- STATE ----------
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {r: pd.DataFrame(
            {"Round": range(1, ROUNDS + 1),
             "Decision": ["-"]*ROUNDS,
             "Duration": [0]*ROUNDS,
             "Cost": [0]*ROUNDS,
             "Notes": [""]*ROUNDS}) for r in ROLES}
        st.session_state.events   = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline = [None]*ROUNDS
        st.session_state.round    = 1
        st.session_state.role_pick = ROLES[0]
init_state()

# ---------- LOGIC ----------
def everyone_done(i): 
    return all(st.session_state.data[r].at[i, "Decision"] != "-" for r in ROLES)

def build_timeline(i):
    txt, delay = st.session_state.events[i]
    rows, start = [], 0
    ap = st.session_state.data[ROLES[0]].loc[i]; ap_end = start + ap.Duration + delay
    rows.append([ROLES[0], start, ap_end])
    ac = st.session_state.data[ROLES[1]].loc[i]; ac_end = ap_end + ac.Duration
    rows.append([ROLES[1], ap_end, ac_end])
    mx = st.session_state.data[ROLES[2]].loc[i]; mx_end = ac_end + mx.Duration
    rows.append([ROLES[2], ac_end, mx_end])
    st.session_state.timeline[i] = pd.DataFrame(rows, columns=["Role", "Start", "End"])

    fine = max(mx_end - TARGET_MIN, 0) * FINE_PER_MIN
    for r in ROLES:
        st.session_state.data[r].at[i, "Cost"] += fine

def record(role, idx, choice):
    df = st.session_state.data[role]

    # Airport Ops
    if role == ROLES[0]:
        if "Dedicated" in choice:
            dur, cost, note = GATE_PVT, GATE_FEE, "Reserved stand"
        else:
            extra = random.randint(5, 20)
            clash = random.random() < 0.5
            dur  = GATE_SHR + (extra if clash else 0)
            cost = 0
            note = "Shared stand" + (f" +{extra} wait" if clash else "")
    # Airline Control
    elif role == ROLES[1]:
        if "Quick" in choice:
            extra = random.randint(5, 25)
            delay = random.random() < 0.4
            dur  = CREW_NB + (extra if delay else 0)
            cost = 0
            note = "Quick swap" + (f" +{extra}" if delay else "")
        else:
            dur, cost, note = CREW_B10, 0, "Buffered swap"
    # Maintenance
    else:
        if "Fix Now" in choice:
            dur, cost, note = MX_FIX, MX_FIX_COST, "Immediate fix"
        else:
            dur, cost, note = MX_DEF, 0, "Deferred"
            if random.random() < MX_PEN_PROB:
                cost += MX_PENALTY
                note += " penalty 1000"

    df.loc[idx, ["Decision", "Duration", "Cost", "Notes"]] = [choice, dur, int(cost), note]

    if everyone_done(idx):
        build_timeline(idx)
        st.session_state.round = min(idx + 2, ROUNDS)
        st.session_state.role_pick = ROLES[0]

def latest_time():
    boards = [b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

# ---------- UI OPTIONS ----------
def option_labels(role):
    if role == ROLES[0]:
        return (
            "AODB: Dedicated Stand ($500 – gate always free)",
            "AODB: Shared Stand (free – 50 % risk +5–20 min)",
        )
    if role == ROLES[1]:
        return (
            "CRS: Quick Crew Swap (30 min – 40 % +5–25 min)",
            "CRS: Buffered Crew Swap (40 min – delay-proof)",
        )
    return (
        "MEL: Fix Now (+20 min, $300)",
        "MEL: Defer (0 min – 40 % $1k)",
    )

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation", "🛫", layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play", "Play"])

# ----- HELP TAB -----
with tab_help:
    st.header("Your Mission")
    st.markdown(
        "Turn five late flights **quickly and economically** while juggling **three MIS tools**.  \n"
        "Every choice you enter in the **AODB**, **CRS**, or **MEL** ripples to the next role — "
        "a smart pick can save the whole team, a bad one can sink them.  \n"
        "A perfect turnaround is **45 minutes**; every extra minute costs **$100** on *your* ledger. "
        "Spend money to avoid time—or gamble and hope delays stay short."
    )

    st.subheader("Each Round, step by step")
    st.markdown(
        "- **AODB stand** – Dedicated Stand (pay $500, gate always free) **or** Shared Stand "
        "(free, 50 % risk the gate is occupied; wait **+5-20 min** if it is).  \n"
        "- **CRS crew** – Quick Swap (30 min; 40 % risk relief crew is late **+5-25 min**) **or** "
        "Buffered Swap (40 min, guaranteed on time).  \n"
        "- **MEL decision** – Fix Now (add 20 min and $300) **or** Defer "
        "(0 min now, 40 % chance of a $1 000 penalty).  \n"
        "- **Flight Event** – Weather, wildlife, or equipment adds the banner delay.  \n"
        "- Click **Submit Decision** to update all systems and start the next flight."
    )

# ----- PLAY TAB -----
with tab_play:
    st.header(f"Flight {st.session_state.round}")

    role = st.selectbox("Select your role for this update", ROLES,
                        index=ROLES.index(st.session_state.role_pick))
    st.session_state.role_pick = role

    # KPIs
    col1, col2 = st.columns(2)
    col1.metric("Your Cost so far",
                f"${int(st.session_state.data[role]['Cost'].sum()):,}")
    col2.metric("Latest Ground Time",
                f"{latest_time()} min",
                delta=f"{latest_time() - TARGET_MIN:+}")

    # Event banner
    evt_txt, evt_delay = st.session_state.events[st.session_state.round - 1]
    st.warning(f"Flight Event — {evt_txt}  (+{evt_delay} min)")

    # Decision widget
    if st.session_state.data[role].at[st.session_state.round - 1, "Decision"] == "-":
        choice = st.radio("Choose your MIS update", option_labels(role))
        if st.button("Submit Decision"):
            record(role, st.session_state.round - 1, choice)
            st.rerun()
    else:
        st.info("Decision already submitted for this role.")

    st.subheader("Your Ledger")
    st.dataframe(st.session_state.data[role].drop(columns="Round"))

    st.subheader("Timeline Board")
    board = next((b for b in reversed(st.session_state.timeline) if b is not None), None)
    if board is not None:
        st.dataframe(board)
    else:
        st.info("Waiting for first flight to finish...")

    # Instructor controls at bottom (out of student view)
    with st.expander("Instructor controls"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Flight"):
                st.session_state.round = min(st.session_state.round + 1, ROUNDS)
                st.session_state.role_pick = ROLES[0]
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

    # Game over summary
    if all(b is not None for b in st.session_state.timeline):
        st.balloons()
        st.success("GAME OVER")
        summary = pd.DataFrame(
            {"Role": ROLES,
             "Total $": [int(st.session_state.data[r]["Cost"].sum()) for r in ROLES]}
        ).sort_values("Total $").reset_index(drop=True)
        st.table(summary)
