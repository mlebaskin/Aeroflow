"""MMIS 494 Aviation MIS Simulation – Integrated Timeline (v1.2)

• Spicy, story-style event cards
• Top-of-screen KPI meters (money + time) – always visible
• Simplified page (no bar charts) so the live numbers pop
"""

import random
from typing import Dict, List

import pandas as pd
import streamlit as st

# ────────── Config ────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5

ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Baseline task times (minutes)
AIRPORT_PRIVATE = 10
AIRPORT_SHARED = 10
CREW_NO_BUFFER = 30
CREW_BUFFER_10 = 40
MX_FIX = 20
MX_DEFER = 0

# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY = 1000
MX_PENALTY_PROB = 0.4  # 40 %

# Big-personality events (text, delay)
EVENT_CARDS = [
    ("Yikes! Wildlife is having a picnic on the runway – shooing birds takes time!", 8),
    ("Fuel truck hit gridlock! The driver’s listening to traffic radio instead of refueling you.", 12),
    ("Half the ground crew called in sick. The remaining team is hustling double-time.", 9),
    ("Snow squall! De-icing trucks roll in and coat the jet in minty glycol goodness.", 15),
    ("Oh no! The baggage belt jammed and suitcases are raining onto the ramp.", 7),
    ("Blackout! Gate power just fizzled – lights out until maintenance flips a breaker.", 10),
    ("Disaster! Soup spilled from the catering cart – dozens of bags now bathed in tomato bisque.", 6),
    ("Lightning dance overhead – ramp ops halt until Mother Nature calms down.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ────────── Helpers ────────── #
def init_state():
    if "round_data" not in st.session_state:
        st.session_state.round_data = {
            r: pd.DataFrame(
                {
                    "Round": range(1, ROUNDS + 1),
                    "Decision": ["-"] * ROUNDS,
                    "Duration": [0] * ROUNDS,
                    "Cost": [0] * ROUNDS,
                    "Notes": [""] * ROUNDS,
                }
            )
            for r in ROLES
        }
        st.session_state.events = random.sample(EVENT_CARDS, k=ROUNDS)
        st.session_state.current_round = 1
        st.session_state.timeline: List[pd.DataFrame] = [None] * ROUNDS
        st.session_state.kpi = pd.DataFrame(index=ROLES,
                                            columns=["Delay", "Cost"]).fillna(0)

def decisions_done(idx):  # all roles decided this round?
    return all(st.session_state.round_data[r].at[idx, "Decision"] != "-"
               for r in ROLES)

def build_timeline(idx):
    # Build sequential board & shared fine
    start = 0
    rows = []
    evt_text, evt_delay = st.session_state.events[idx]

    ap = st.session_state.round_data["Airport_Ops"].loc[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append(["Airport_Ops", start, ap_end])

    al = st.session_state.round_data["Airline_Control"].loc[idx]
    al_start, al_end = ap_end, ap_end + al.Duration
    rows.append(["Airline_Control", al_start, al_end])

    mx = st.session_state.round_data["Maintenance"].loc[idx]
    mx_start, mx_end = al_end, al_end + mx.Duration
    rows.append(["Maintenance", mx_start, mx_end])

    board = pd.DataFrame(rows, columns=["Role", "Start", "End"])
    st.session_state.timeline[idx] = board

    extra = max(mx_end - ON_TIME_MIN, 0)
    fine = extra * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.round_data[r].at[idx, "Cost"] += fine / 3

    # Update cumulative KPI
    for r in ROLES:
        df = st.session_state.round_data[r]
        st.session_state.kpi.at[r, "Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r, "Cost"] = df["Cost"].sum()

def record(role, idx, decision):
    df = st.session_state.round_data[role]

    if role == "Airport_Ops":
        if decision == "Private Gate":
            dur, cost, note = AIRPORT_PRIVATE, GATE_FEE, "Private gate"
        else:
            dur, cost, note = AIRPORT_SHARED, 0, "Shared gate"
            if random.random() < 0.5:
                dur += 10
                note += " (+10 clash)"
    elif role == "Airline_Control":
        if decision == "No Buffer":
            dur, cost, note = CREW_NO_BUFFER, 0, "No buffer"
            if random.random() < 0.4:
                dur += 15
                note += " (+15 late crew)"
        else:
            dur, cost, note = CREW_BUFFER_10, 0, "Buffer 10"
    else:  # Maintenance
        if decision == "Fix Now":
            dur, cost, note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur, cost, note = MX_DEFER, 0, "Defer"
            if random.random() < MX_PENALTY_PROB:
                cost += MX_PENALTY
                note += " – Penalty $1k"
            else:
                note += " – No penalty"

    df.loc[idx, ["Decision", "Duration", "Cost", "Notes"]] = [decision,
                                                              dur, cost, note]

    if decisions_done(idx):
        build_timeline(idx)
        st.session_state.current_round = min(idx + 2, ROUNDS)

def game_over():
    if st.session_state.current_round < ROUNDS:
        return False
    return all("-" not in df["Decision"].values for df in
               st.session_state.round_data.values())

# ────────── UI components ────────── #
def kpi_meters():
    total_cost = st.session_state.kpi["Cost"].sum()
    total_delay = st.session_state.timeline[st.session_state.current_round - 2]["End"].max() if st.session_state.timeline[st.session_state.current_round - 2] is not None else 0
    col1, col2 = st.columns(2)
    col1.metric("💸 Team Cost so far", f"${total_cost:,.0f}")
    col2.metric("⏱️ Ground Time this round",
                f"{total_delay} min", delta=f"{total_delay - ON_TIME_MIN:+}")

def sidebar(role, round_num):
    st.sidebar.header("Game Facts")
    st.sidebar.markdown(
        f"- On-time goal: **{ON_TIME_MIN} min**\n"
        f"- Delay fine: **${FINE_PER_MIN}/min**\n"
        f"- Private gate fee: **${GATE_FEE}**\n"
        f"- Fix-now cost: **${MX_FIX_COST}**\n"
        f"- Defer penalty: **${MX_PENALTY}** (40 % risk)"
    )
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Pwd", type="password", key="pw")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"):
                st.session_state.current_round = min(round_num + 1, ROUNDS)
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

def decision_ui(role, idx):
    if role == "Airport_Ops":
        opt = st.radio("Gate choice",
                       ["Private Gate", "Shared Gate"])
    elif role == "Airline_Control":
        opt = st.radio("Crew choice",
                       ["No Buffer", "Buffer 10"])
    else:
        opt = st.radio("Maintenance",
                       ["Fix Now", "Defer"])
    if st.button("Submit"):
        record(role, idx, opt)
        st.rerun()

# ────────── Main app ────────── #
def main():
    st.set_page_config(page_title="MMIS 494 Aviation MIS Simulation",
                       page_icon="🛫", layout="wide")
    st.title("🛫 MMIS 494 Aviation MIS Simulation")
    init_state()

    tab_play, tab_guide = st.tabs(["Play the Game", "How to Play"])

    with tab_guide:
        st.header("How to Play")
        st.markdown(
            """
1. **Choose** an option for your role each round.  
2. Tasks run in order: *Airport ➜ Airline ➜ Maintenance*.  
3. If total ground time > 45 min, everyone shares the delay fine.  
4. Lowest total cost after 5 rounds wins.
"""
        )

    with tab_play:
        rnd = st.session_state.current_round
        role = st.selectbox("Select your role", ROLES)
        sidebar(role, rnd)
        kpi_meters()

        st.subheader(f"Round {rnd} – {role}")
        evt_text, evt_delay = st.session_state.events[rnd - 1]
        st.warning(f"{evt_text}\n\n*(+{evt_delay} min)*")

        if st.session_state.round_data[role].at[rnd - 1, "Decision"] == "-":
            decision_ui(role, rnd - 1)
        else:
            st.info("Decision already submitted.")

        st.markdown("### Round Timeline")
        if st.session_state.timeline[rnd - 1] is not None:
            st.dataframe(st.session_state.timeline[rnd - 1])
        else:
            st.info("Waiting for all roles…")

        if game_over():
            st.success("🎉 Game Over")
            total_cost = st.session_state.kpi["Cost"].sum()
            total_delay = st.session_state.timeline[-1]["End"].max()
            st.metric("Final Cost", f"${total_cost:,.0f}")
            st.metric("Final Ground Time", f"{total_delay} min")


if __name__ == "__main__":
    main()
