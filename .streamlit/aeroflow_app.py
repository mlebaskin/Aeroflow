"""
MMIS 494 Flight Turn Simulation – Integrated Timeline Edition (v1.0)
---------------------------------------------------------------------
A single–page Streamlit app where three student roles (Airport Ops,
Airline Control, Maintenance) coordinate the turnaround timeline for one
flight.  Tasks run **sequentially** – Airport work, then Airline crew, then
Maintenance – so every extra minute added by an early role pushes the
whole schedule and the final delay fine is shared by all.

Key Features
============
• **Event cards** – five unique disruptions per game chosen at random.
• **Integrated timeline board** – after each round students see a Gantt‑style
  table showing start & end times for every task.
• **Shared delay fine** – if total ground time exceeds 45 min the extra
  minutes are fined at $100 each and split evenly across the three roles.
• **Maintenance "Defer" now has a 40 % penalty risk; board shows whether it
  hit or missed (Notes column).
• Automatic *Game Over* recap once all roles have submitted in Round 5.

Quick Start
-----------
1.  `pip install streamlit pandas`
2.  `streamlit run mmis494_flight_turn_sim.py`
3.  Deploy to Streamlit Cloud like any single‑file app.
"""

import random
from typing import Dict, List

import pandas as pd
import streamlit as st

# ───────────────── Config ────────────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Task durations (baseline minutes)
AIRPORT_PRIVATE = 10  # dedicated gate
AIRPORT_SHARED = 10   # base + possible clash delay later
CREW_NO_BUFFER = 30   # plus possible +15
CREW_BUFFER_10 = 40
MX_FIX = 20
MX_DEFER = 0

GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY = 1000
MX_PENALTY_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on runway – crews scare birds", 8),
    ("Fuel truck stuck in traffic", 12),
    ("Ground crew shortage", 9),
    ("De‑icing needed", 15),
    ("Baggage belt jam", 7),
    ("Gate power outage", 10),
    ("Catering cart spills soup", 6),
    ("Thunderstorm cell overhead", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ─────────────── Helpers ──────────────── #

def init_state():
    if "round_data" not in st.session_state:
        # one master df per role to keep raw decisions & results
        st.session_state.round_data: Dict[str, pd.DataFrame] = {
            r: pd.DataFrame(
                {
                    "Round": range(1, ROUNDS + 1),
                    "Decision": "-",
                    "Duration": 0,
                    "Cost": 0,
                    "Notes": "",
                }
            )
            for r in ROLES
        }
        st.session_state.events = random.sample(EVENT_CARDS, k=ROUNDS)
        st.session_state.current_round = 1
        # timeline board list each round: will fill later
        st.session_state.timeline: List[pd.DataFrame] = [None] * ROUNDS
        st.session_state.shared_fines = [0] * ROUNDS


def decisions_complete(round_idx: int) -> bool:
    return all(
        st.session_state.round_data[r].at[round_idx, "Decision"] != "-"
        for r in ROLES
    )


def build_timeline(round_idx: int):
    """Compute start/end times sequentially and shared fine."""
    start = 0
    rows = []
    # Airport first
    ap_dec = st.session_state.round_data["Airport_Ops"].loc[round_idx]
    evt_label, evt_delay = st.session_state.events[round_idx]
    ap_dur = ap_dec.Duration + evt_delay
    ap_end = start + ap_dur
    rows.append(["Airport_Ops", start, ap_end])

    # Airline second
    al_dec = st.session_state.round_data["Airline_Control"].loc[round_idx]
    al_start = ap_end
    al_end = al_start + al_dec.Duration
    rows.append(["Airline_Control", al_start, al_end])

    # Maintenance last
    mx_dec = st.session_state.round_data["Maintenance"].loc[round_idx]
    mx_start = al_end
    mx_end = mx_start + mx_dec.Duration
    rows.append(["Maintenance", mx_start, mx_end])

    board = pd.DataFrame(rows, columns=["Role", "Start", "End"])

    # Shared fine if total ground time > threshold
    total_time = mx_end
    excess = max(total_time - ON_TIME_MIN, 0)
    fine = excess * FINE_PER_MIN
    st.session_state.shared_fines[round_idx] = fine
    if fine > 0:
        for r in ROLES:
            st.session_state.round_data[r].at[round_idx, "Cost"] += fine / 3
    st.session_state.timeline[round_idx] = board


def record_decision(role: str, round_idx: int, decision: str):
    evt_label, evt_delay = st.session_state.events[round_idx]
    df = st.session_state.round_data[role]

    # Airport decisions
    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
            dur, cost, note = AIRPORT_PRIVATE, GATE_FEE, "Private gate"
        else:
            dur, cost, note = AIRPORT_SHARED, 0, "Shared gate"
            if random.random() < 0.5:
                dur += 10
                note += " (+10 clash)"
    # Airline decisions
    elif role == "Airline_Control":
        if decision == "No Buffer":
            dur, cost, note = CREW_NO_BUFFER, 0, "No buffer"
            if random.random() < 0.4:
                dur += 15
                note += " (+15 late crew)"
        else:
            dur, cost, note = CREW_BUFFER_10, 0, "Buffer 10"
    # Maintenance decisions
    else:
        if decision == "Fix Now":
            dur, cost, note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur, cost, note = MX_DEFER, 0, "Defer"
            if random.random() < MX_PENALTY_PROB:
                cost += MX_PENALTY
                note += " – Penalty $1k"
            else:
                note += " – No penalty"

    df.loc[round_idx, ["Decision", "Duration", "Cost", "Notes"]] = [
        decision,
        dur,
        cost,
        note,
    ]

    # If now all three roles decided, build timeline
    if decisions_complete(round_idx):
        build_timeline(round_idx)
        st.session_state.current_round = min(round_idx + 2, ROUNDS)


# ═════════════════════ UI ════════════════════════ #

def role_panel(role: str, round_idx: int):
    df = st.session_state.round_data[role]
    if df.at[round_idx, "Decision"] != "-":
        st.info("Decision already submitted.")
        return

    if role == "Airport_Ops":
        st.radio("Choose gate plan:", ["Dedicated Gate", "Shared Gate"],
                 key="ap_pick")
    elif role == "Airline_Control":
        st.radio("Choose crew plan:", ["No Buffer", "Buffer 10"],
                 key="al_pick")
    else:
        st.radio("Maintenance decision:", ["Fix Now", "Defer"],
                 key="mx_pick")


# Main page

def main():
    st.set_page_config(page_title="MMIS 494 Flight Turn Simulation",
                       page_icon="🛫", layout="wide")
    st.title("🛫 MMIS 494 Flight Turn Simulation – Integrated Timeline")
    init_state()

    current_round = st.session_state.current_round
    round_idx = current_round - 1

    col_role, col_event = st.columns([2, 1])
    with col_role:
        role = st.selectbox("Select your role", ROLES)
        st.markdown(f"### Round {current_round} decision – {role}")

        # decision UI
        if role == "Airport_Ops":
            choice = st.radio("Gate option:", ["Dedicated Gate", "Shared Gate"])
        elif role == "Airline_Control":
            choice = st.radio("Crew option:", ["No Buffer", "Buffer 10"])
        else:
            choice = st.radio("Maintenance option:", ["Fix Now", "Defer"])
        if st.button("Submit"):
            record_decision(role, round_idx, choice)
            st.rerun()

    with col_event:
        lbl, dly = st.session_state.events[round_idx]
        st.warning(f"**EVENT**\n{lbl}\n(+{dly} min)")

    st.write("---")
    st.markdown("## Round timeline board")
    if st.session_state.timeline[round_idx] is not None:
        st.dataframe(st.session_state.timeline[round_idx])
    else:
        st.info("Waiting for all roles to decide…")

    st.write("---")
    st.markdown("## Cumulative KPIs")
    kpi = st.session_state.kpi.copy()
    kpi["Cost"] = kpi["Cost"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(kpi)

    if game_finished():
        st.success("🎉 Game Over – see final timeline and costs below")
        for i in range(ROUNDS):
            st.write(f"### Timeline Round {i+1}")
            st.dataframe(st.session_state.timeline[i])
        total_cost = sum(kpi_row for kpi_row in st.session_state.kpi["Cost"].apply(lambda x: int(x.replace("$", "").replace(",", ""))))
        total_delay = st.session_state.timeline[-1]["End"].max()
        st.info(f"Final total cost: ${total_cost:,.0f} – Final ground time: {total_delay} min")


if __name__ == "__main__":
    main()
