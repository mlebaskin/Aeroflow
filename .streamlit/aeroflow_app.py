"""MMIS 494 Aviation MIS Simulation – Integrated Timeline (v1.4)

Adds clear role narratives in the How-to-Play tab.
"""

import random
from typing import Dict, List
import pandas as pd
import streamlit as st

# ─── Config ─── #
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Task baselines
GATE_PRIVATE = 10
GATE_SHARED = 10
CREW_NO_BUFFER = 30
CREW_BUFFER_10 = 40
MX_FIX = 20
MX_DEFER = 0

# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY = 1000
MX_PENALTY_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife picnic on the runway—bird-shooing takes time!", 8),
    ("Fuel truck stuck in traffic—driver’s still downtown!", 12),
    ("Half the ramp crew called in sick—slow loading.", 9),
    ("Snow squall—de-icing trucks coat the jet in minty glycol.", 15),
    ("Baggage belt jam—bags raining onto the ramp!", 7),
    ("Power outage! Gate lights go dark until a breaker flips.", 10),
    ("Catering cart dumps tomato soup on suitcases—messy cleanup!", 6),
    ("Lightning dance overhead—ramp ops halt until clear.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ─── State init ─── #
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {
            r: pd.DataFrame(
                {"Round": range(1, ROUNDS + 1),
                 "Decision": ["-"] * ROUNDS,
                 "Duration": [0] * ROUNDS,
                 "Cost": [0] * ROUNDS,
                 "Notes": [""] * ROUNDS}
            ) for r in ROLES
        }
        st.session_state.events = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline: List[pd.DataFrame] = [None] * ROUNDS
        st.session_state.kpi = pd.DataFrame(index=ROLES,
                                            columns=["Delay", "Cost"]).fillna(0)
        st.session_state.round = 1

# ─── Logic ─── #
def everyone_decided(idx):
    return all(st.session_state.data[r].at[idx, "Decision"] != "-" for r in ROLES)

def build_board(idx):
    start = 0
    rows = []
    evt_txt, evt_delay = st.session_state.events[idx]

    ap = st.session_state.data["Airport Operations"].loc[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append(["Airport Ops", start, ap_end])

    ac = st.session_state.data["Airline Control Center"].loc[idx]
    ac_end = ap_end + ac.Duration
    rows.append(["Airline Control", ap_end, ac_end])

    mx = st.session_state.data["Aircraft Maintenance"].loc[idx]
    mx_end = ac_end + mx.Duration
    rows.append(["Maintenance", ac_end, mx_end])

    st.session_state.timeline[idx] = pd.DataFrame(rows, columns=["Role", "Start", "End"])

    extra = max(mx_end - ON_TIME_MIN, 0)
    fine = extra * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.data[r].at[idx, "Cost"] += fine / 3

    # KPI
    for r in ROLES:
        df = st.session_state.data[r]
        st.session_state.kpi.at[r, "Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r, "Cost"] = df["Cost"].sum()

def record_decision(role, idx, choice):
    df = st.session_state.data[role]
    if role == "Airport Operations":
        if choice == "Private Gate":
            dur, cost, note = GATE_PRIVATE, GATE_FEE, "Private gate"
        else:
            dur, cost, note = GATE_SHARED, 0, "Shared gate"
            if random.random() < 0.5:
                dur += 10
                note += " (+10 clash)"
    elif role == "Airline Control Center":
        if choice == "No Buffer":
            dur, cost, note = CREW_NO_BUFFER, 0, "No buffer"
            if random.random() < 0.4:
                dur += 15
                note += " (+15 late crew)"
        else:
            dur, cost, note = CREW_BUFFER_10, 0, "Buffer 10"
    else:
        if choice == "Fix Now":
            dur, cost, note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur, cost, note = MX_DEFER, 0, "Defer"
            if random.random() < MX_PENALTY_PROB:
                cost += MX_PENALTY
                note += " – Penalty $1k"
            else:
                note += " – No penalty"
    df.loc[idx, ["Decision", "Duration", "Cost", "Notes"]] = [choice, dur, cost, note]

    if everyone_decided(idx):
        build_board(idx)
        st.session_state.round = min(idx + 2, ROUNDS)

def game_over():
    if st.session_state.round <= ROUNDS - 1:
        return False
    return all("-" not in df["Decision"].values for df in st.session_state.data.values())

# ─── UI helpers ─── #
def kpi_strip():
    total_cost = st.session_state.kpi["Cost"].sum()
    last_board = next((b for b in reversed(st.session_state.timeline) if b is not None), None)
    last_time = last_board["End"].max() if last_board is not None else 0
    col1, col2 = st.columns(2)
    col1.metric("💸 Team Cost", f"${total_cost:,.0f}")
    col2.metric("⏱️ Latest Ground Time", f"{last_time} min",
                delta=f"{last_time - ON_TIME_MIN:+}")

# ─── Streamlit page ─── #
def main():
    st.set_page_config("MMIS 494 Aviation MIS Simulation", "🛫", layout="wide")
    st.title("🛫 MMIS 494 Aviation MIS Simulation")
    init_state()

    play, guide = st.tabs(["Play the Game", "How to Play"])

    # ----- Guide tab -----
    with guide:
        st.header("Who does what?")
        st.markdown(
            """
**Airport Operations (Ramp Supervisor)**  
Keeps the plane’s parking stand clear, loads bags, attaches the jet bridge, and pushes back.  
*Choice:* Pay for a **Private Gate** (no conflicts) or share a gate (risk delays).

**Airline Control Center (Dispatch)**  
Swaps the arriving crew for a fresh one and coordinates the day’s flight plan.  
*Choice:* **No Buffer** (quick swap but risk crew timeout) or **Buffer 10** (slower but safe).

**Aircraft Maintenance (Tech Crew)**  
Handles mechanical issues logged by pilots.  
*Choice:* **Fix Now** (adds 20 min, \$300) or **Defer** under the Minimum Equipment List (40 % risk \$1 000).

**Goal:** keep total ground time ≤ 45 min and spend the least money by Round 5.  
Delay fines \$100 per extra minute are split between all roles.
"""
        )

    # ----- Play tab -----
    with play:
        rnd = st.session_state.round
        role = st.selectbox("Select your role", ROLES)
        kpi_strip()

        evt_text, evt_delay = st.session_state.events[rnd - 1]
        st.warning(f"{evt_text}\n\n(+{evt_delay} min)")

        # Decision form
        if st.session_state.data[role].at[rnd - 1, "Decision"] == "-":
            options = ("Private Gate", "Shared Gate") if role == "Airport Operations" \
                else ("No Buffer", "Buffer 10") if role == "Airline Control Center" \
                else ("Fix Now", "Defer")
            choice = st.radio("Your move:", options)
            if st.button("Submit"):
                record_decision(role, rnd - 1, choice)
                st.rerun()
        else:
            st.info("Decision submitted.")

        st.dataframe(st.session_state.data[role]
                     .drop(columns="Round"), height=200)

        st.write("### Round Timeline")
        board = st.session_state.timeline[rnd - 1]
        st.dataframe(board) if board is not None else st.info("Waiting for all roles…")

        if game_over():
            st.balloons()
            st.success("🏁 GAME OVER")
            for r in ROLES:
                st.write(f"#### {r}")
                st.dataframe(st.session_state.data[r]
                             .style.format({"Cost": "${:,.0f}"}))
            total_cost = st.session_state.kpi["Cost"].sum()
            final_time = st.session_state.timeline[-1]["End"].max()
            st.info(f"Team Cost: ${total_cost:,.0f}   |   Ground Time: {final_time} min")

if __name__ == "__main__":
    main()
