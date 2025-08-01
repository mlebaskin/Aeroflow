import random
import pandas as pd
import streamlit as st

# ---------- CONFIG ----------
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
TARGET_MIN = 45
FINE_PER_MIN = 100

# Durations (minutes)
GATE_PVT, GATE_SHR = 10, 10
CREW_NB, CREW_B10  = 30, 40
MX_FIX,  MX_DEF    = 20, 0

# Costs ($)
GATE_FEE     = 500
MX_FIX_COST  = 300
MX_PENALTY   = 1000
MX_PEN_PROB  = 0.4

EVENT_CARDS = [
    ("Wildlife on the runway - bird hazard.", 8),
    ("Fuel truck stuck in traffic - stand blocked.", 12),
    ("Half the ramp crew called in sick - slow loading.", 9),
    ("Snow squall - extra de-icing.", 15),
    ("Baggage belt jam - bags everywhere.", 7),
    ("Gate power outage - stand dark.", 10),
    ("Catering cart spills tomato soup on luggage.", 6),
    ("Lightning overhead - ground ops paused.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ---------- STATE ----------
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {
            r: pd.DataFrame({
                "Round":    range(1, ROUNDS+1),
                "Decision": ["-"]*ROUNDS,
                "Duration": [0]*ROUNDS,
                "Cost":     [0]*ROUNDS,
                "Notes":    [""]*ROUNDS
            }) for r in ROLES
        }
        st.session_state.events   = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline = [None]*ROUNDS
        st.session_state.round    = 1
        st.session_state.role_pick= ROLES[0]
init_state()

# ---------- LOGIC ----------
def everyone_done(idx):
    return all(st.session_state.data[r].at[idx,"Decision"] != "-" for r in ROLES)

def build_timeline(idx):
    txt, delay = st.session_state.events[idx]
    rows, start = [], 0
    for role in ROLES:
        dur = st.session_state.data[role].loc[idx,"Duration"]
        end = start + dur + (delay if role==ROLES[0] else 0)
        rows.append([role, start, end])
        start = end
    st.session_state.timeline[idx] = pd.DataFrame(rows, columns=["Role","Start","End"])

def record(role, idx, choice):
    df = st.session_state.data[role]
    if role==ROLES[0]:
        if "Dedicated" in choice:
            dur,cost,note = GATE_PVT, GATE_FEE, "Reserved stand"
        else:
            extra, clash = random.randint(5,20), random.random()<0.5
            dur = GATE_SHR + (extra if clash else 0)
            cost,note = 0, f"Shared stand{' +'+str(extra)+' wait' if clash else ''}"
    elif role==ROLES[1]:
        if "Quick" in choice:
            extra, late = random.randint(5,25), random.random()<0.4
            dur = CREW_NB + (extra if late else 0)
            cost,note = 0, f"Quick swap{' +'+str(extra) if late else ''}"
        else:
            dur,cost,note = CREW_B10,0,"Buffered swap"
    else:
        if "Fix Now" in choice:
            dur,cost,note = MX_FIX, MX_FIX_COST, "Immediate fix"
        else:
            dur,cost,note = MX_DEF,0,"Deferred"
            if random.random()<MX_PEN_PROB:
                cost+=MX_PENALTY; note+=" penalty 1000"
    df.loc[idx,["Decision","Duration","Cost","Notes"]] = [choice,dur,cost,note]
    if everyone_done(idx):
        build_timeline(idx)
        st.session_state.round     = min(idx+2,ROUNDS)
        st.session_state.role_pick = ROLES[0]

def compute_time_fines(upto=None):
    total=0
    last = upto if upto is not None else len(st.session_state.timeline)
    for i in range(last):
        df = st.session_state.timeline[i]
        if df is None: break
        end = df["End"].max()
        total += max(end-TARGET_MIN,0)*FINE_PER_MIN
    return total

def latest_time():
    boards=[b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

def current_ground_time():
    idx=st.session_state.round-1
    base=st.session_state.events[idx][1]
    return base + sum(st.session_state.data[r].at[idx,"Duration"] for r in ROLES)

def option_labels(role):
    if role==ROLES[0]:
        return ("AODB: Dedicated Stand ($500 - gate always available)",
                "AODB: Shared Stand (free - 50 % risk +5-20 min)")
    if role==ROLES[1]:
        return ("CRS: Quick Crew Swap (30 min - 40 % risk +5-25 min)",
                "CRS: Buffered Crew Swap (40 min - guaranteed on-time)")
    return ("MEL: Fix Now (+20 min, $300)",
            "MEL: Defer (0 min - 40 % risk $1,000)")

# ---------- PAGE ----------
st.set_page_config("MMIS 494 Aviation MIS Simulation","🛫",layout="wide")
st.title("🛫 MMIS 494 Aviation MIS Simulation")

tab_help, tab_play = st.tabs(["How to Play","Play"])

# ----- HOW TO PLAY TAB (approved wording) -----
with tab_help:
    st.header("Your Mission")
    st.markdown(
        "Turn five delayed flights while keeping the time down and cost low.  \n"
        "Each flight, you will update three information systems: AODB gate allocation, CRS crew plan, and MEL defect log.  \n"
        "Perfect ground time is 45 minutes; every extra minute costs $100.  \n"
        "Spend money to avoid time—or gamble and hope delays stay short."
    )
    st.subheader("Each Round, step by step")
    st.markdown(
        '''
        <ul style="font-family: sans-serif; font-size:1rem;">
          <li><strong>AODB stand</strong> – Dedicated Stand (pay $500, gate always available) or Shared Stand (free, but 50% risk the gate is busy; if busy, wait 5–20 min randomly).</li>
          <li><strong>CRS crew</strong> – Quick Swap (30 min, 40% chance relief crew is late +5–25 min) or Buffered Swap (40 min, guaranteed on-time).</li>
          <li><strong>MEL decision</strong> – Fix Now (add 20 min & $300) or Defer (0 min now, but 40% chance a compliance audit fines you $1,000 later).</li>
          <li><strong>Flight Event</strong> – Weather, wildlife, or equipment surprise adds the banner delay.</li>
          <li>Click <strong>Submit Decision</strong> to update all systems, see the timeline, and start the next flight.</li>
        </ul>
        ''', unsafe_allow_html=True
    )
    st.subheader("Acronym Glossary")
    st.write("AODB – Airport Operational Data Base")
    st.write("CRS  – Crew Rostering System")
    st.write("MEL  – Minimum Equipment List (defect log)")

# ----- PLAY TAB -----
with tab_play:
    # Final banner + airplanes if done
    finished = all(df is not None for df in st.session_state.timeline)
    if finished:
        st.markdown("<p style='font-size:2rem; text-align:center;'>✈️ ✈️ ✈️ ✈️ ✈️</p>", unsafe_allow_html=True)
        st.success(
            "GAME OVER!\n\n"
            "Your MIS choices led to these outcomes:\n"
            "- Immediate costs (gates, fixes, audit penalties)\n"
            "- Time fines (every minute past 45)\n\n"
            "Review your decisions and reset to try for faster, cheaper turnarounds!",
            icon="✅"
        )

    # KPIs: either per-flight or cumulative
    if finished:
        total_immediate = sum(st.session_state.data[r]["Cost"].sum() for r in ROLES)
        total_fines     = compute_time_fines()
        total_ground    = sum(st.session_state.timeline[i]["End"].max() for i in range(ROUNDS))
        c1, c2, c3 = st.columns(3)
        c1.metric("Immediate Cost (all flights)", f"${total_immediate:,}")
        c2.metric("Time Fines (all flights)", f"${total_fines:,}")
        c3.metric("Total Ground Time", f"{total_ground} min")
    else:
        immediate = sum(st.session_state.data[r]["Cost"].sum() for r in ROLES)
        fines     = compute_time_fines(upto=st.session_state.round-1)
        gt        = latest_time() if st.session_state.timeline[st.session_state.round-1] is not None else current_ground_time()
        c1, c2, c3 = st.columns(3)
        c1.metric("Immediate Cost", f"${immediate:,}")
        c2.metric("Time Fines", f"${fines:,}")
        c3.metric("Ground Time", f"{gt} min", delta=f"{gt-TARGET_MIN:+}")

    st.header(f"Flight {st.session_state.round}")

    role = st.selectbox("Select your role for this update", ROLES,
                        index=ROLES.index(st.session_state.role_pick))
    st.session_state.role_pick = role

    evt,delay = st.session_state.events[st.session_state.round-1]
    st.warning(f"Flight Event – {evt} (+{delay} min)")

    if st.session_state.data[role].at[st.session_state.round-1,"Decision"]=="-":
        choice = st.radio("Choose your MIS update", option_labels(role))
        if st.button("Submit Decision"):
            record(role, st.session_state.round-1, choice)
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
        st.info("Waiting for first flight...")

    with st.expander("Instructor controls"):
        pw = st.text_input("Password", type="password")
        if pw==INSTRUCTOR_PW:
            if st.button("Next Flight"):
                st.session_state.round     = min(st.session_state.round+1,ROUNDS)
                st.session_state.role_pick = ROLES[0]
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()): del st.session_state[k]
                st.rerun()

    if finished:
        rows=[]
        for r in ROLES:
            imm = int(st.session_state.data[r]["Cost"].sum())
            tf  = sum(max(st.session_state.timeline[i]["End"].max()-TARGET_MIN,0)*FINE_PER_MIN for i in range(ROUNDS))
            rows.append((r, imm, tf, imm+tf))
        summary = pd.DataFrame(rows,columns=["Role","Immediate Cost","Time Fines","Total"])
        st.table(summary.sort_values("Total").reset_index(drop=True))
