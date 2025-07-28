"""Flight-Turn Simulation – Streamlit App (v0.2)
Teams coordinate one flight turnaround across Airport Ops,
Airline Control, and Maintenance.  Lowest total cost after
five rounds wins.  Now includes an in-app “How to Play” tab.
"""

import random
from typing import Dict

import pandas as pd
import streamlit as st

# ─────────────────────────── Config ──────────────────────────────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45            # scheduled ground time (minutes)
COST_PER_DELAY_MIN = 100    # $ per minute over 45
GATE_FEE = 500              # $ for dedicated gate
MEL_FIX_COST = 300          # $ labour if fixing now
MEL_PENALTY = 1000          # $ risk if deferring

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

EVENT_CARDS = [
    ("Smooth turn", 0),
    ("Mild ramp congestion", 5),
    ("Catering late", 10),
    ("Thunderstorm nearby", 15),
]

# ─────────────────────── Session-State Setup ─────────────────────────── #
def init_state():
    if "turn_data" not in st.session_state:
        st.session_state.turn_data: Dict[str, pd.DataFrame] = {}
        for role in ROLES:
            df = pd.DataFrame(
                {
                    "Round": list(range(1, ROUNDS + 1)),
                    "Decision": ["-"] * ROUNDS,
                    "RoleDelay": [0] * ROUNDS,
                    "RoleCost": [0] * ROUNDS,
                }
            )
            st.session_state.turn_data[role] = df

        st.session_state.events = random.choices(EVENT_CARDS, k=ROUNDS)
        st.session_state.current_round = 1
        st.session_state.kpi = pd.DataFrame(
            index=ROLES, columns=["Delay", "Cost"]
        ).fillna(0)

# ──────────────────────── Decision Calculator ────────────────────────── #
def apply_decision(role: str, decision: str):
    """Return delay minutes and cost produced by a role’s decision."""
    delay = 0
    cost = 0

    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
            cost += GATE_FEE
        else:  # Shared Gate
            if random.random() < 0.5:
                delay += 10

    elif role == "Airline_Control":
        if decision == "No Buffer":
            delay += 30
            if random.random() < 0.4:
                delay += 15
        else:  # Buffer 10
            delay += 40

    elif role == "Maintenance":
        if decision == "Fix Now":
            delay += 20
            cost += MEL_FIX_COST
        else:  # Defer
            if random.random() < 0.2:
                cost += MEL_PENALTY

    return delay, cost


def update_kpi(role: str):
    df = st.session_state.turn_data[role]
    st.session_state.kpi.at[role, "Delay"] = df["RoleDelay"].sum()
    st.session_state.kpi.at[role, "Cost"] = df["RoleCost"].sum()

# ───────────────────────── Simulation UI ─────────────────────────────── #
def simulation_ui():
    role = st.sidebar.selectbox("Role", ROLES)
    round_num = st.session_state.current_round
    st.sidebar.markdown(f"**Current Round:** {round_num}")

    # Instructor controls
    with st.sidebar.expander("Instructor Panel", expanded=False):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            st.success("Instructor mode enabled")
            if st.button("Advance Round ➡️") and round_num < ROUNDS:
                st.session_state.current_round += 1
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.experimental_rerun()

    st.subheader(f"{role} – Round {round_num}")
    df_role = st.session_state.turn_data[role]

    if df_role.at[round_num - 1, "Decision"] == "-":
        # Decision input widgets
        if role == "Airport_Ops":
            decision = st.radio("Gate Strategy", ["Dedicated Gate", "Shared Gate"])
        elif role == "Airline_Control":
            decision = st.radio("Crew Buffer", ["No Buffer", "Buffer 10"])
        else:  # Maintenance
            decision = st.radio("MEL Decision", ["Fix Now", "Defer"])

        if st.button("Submit Decision"):
            delay, cost = apply_decision(role, decision)

            # Event delay applies via Airport Ops record (simplest)
            event_label, event_delay = st.session_state.events[round_num - 1]
            if role == "Airport_Ops":
                delay += event_delay

            total_cost = cost + max(delay - ON_TIME_MIN, 0) * COST_PER_DELAY_MIN

            df_role.loc[round_num - 1, ["Decision", "RoleDelay", "RoleCost"]] = [
                decision,
                delay,
                total_cost,
            ]
            update_kpi(role)
            st.success("Decision recorded!")
            st.experimental_rerun()
    else:
        st.info("Decision already submitted for this round.")

    st.write("### Role Ledger")
    st.dataframe(df_role, use_container_width=True)

    st.write("### Current Event Card")
    st.write(st.session_state.events[round_num - 1][0])

    st.write("---")
    st.subheader("Class KPI Scoreboard (cumulative)")
    st.dataframe(st.session_state.kpi, use_container_width=True)

# ───────────────────────────── Main App ───────────────────────────────── #
def main():
    st.set_page_config(
        page_title="Flight Turn Simulation", page_icon="🛫", layout="wide"
    )
    st.title("🛫 MMIS 494 Flight-Turn Simulation")
    init_state()

    tab_how, tab_play = st.tabs(["How to Play", "Simulation"])

    # -------- How to Play tab -------- #
    with tab_how:
        st.header("How to Play")
        st.markdown(
            """
**Goal**  
Push Flight 283 out on time (≤ 45 min ground) for 5 turns while spending the least money.

| Role            | Option A | Option B | Trade-off |
|-----------------|----------|----------|-----------|
| **Airport Ops** | Dedicated Gate (+\$500, no delay) | Shared Gate (\$0, 50% risk +10 min) | Fee vs. conflict |
| **Airline Control** | No Buffer (30 min, 40 % risk +15 min) | Buffer 10 (40 min, no risk) | Time vs. overtime |
| **Maintenance** | Fix Now (+20 min, +\$300) | Defer (20 % risk \$1 000 penalty) | Delay vs. penalty |

**Round loop**  
1. Instructor reveals the *Event Card* (0–15 min disruption).  
2. Each role chooses a decision and clicks **Submit Decision**.  
3. Instructor clicks **Advance Round**.  
4. Ledgers and KPI scoreboard update.

**Scoring**  
*Role Cost* = decision cost + (delay – 45) × \$100 (only if delay > 45)  
*Team Cost* = sum of all role costs after 5 rounds – lowest wins.

Watch the KPI board: which role is driving total cost? What shared data would help you turn the flight faster next time?
"""
        )

    # -------- Simulation tab -------- #
    with tab_play:
        simulation_ui()


if __name__ == "__main__":
    main()

