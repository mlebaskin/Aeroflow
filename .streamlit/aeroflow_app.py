"""Flight-Turn Simulation - Streamlit App (v0.1)

Aviation-specific Beer Game replacement.  Teams play Airport Ops,
Airline Control, and Maintenance to push one flight out on time.

See in-code comments for setup and gameplay.
"""

import random
from typing import Dict

import pandas as pd
import streamlit as st

# ------------------------------ Config ----------------------------------- #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45  # scheduled ground time
COST_PER_DELAY_MIN = 100
GATE_FEE = 500
MEL_FIX_COST = 300
MEL_PENALTY = 1000
INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

EVENT_CARDS = [
    ("Smooth turn", 0),
    ("Mild ramp congestion", 5),
    ("Catering late", 10),
    ("Thunderstorm nearby", 15),
]

# -------------------------- Init Session State --------------------------- #
def init_state():
    if "turn_data" not in st.session_state:
        st.session_state.turn_data: Dict[str, pd.DataFrame] = {}
        for role in ROLES:
            df = pd.DataFrame(
                {
                    "Round": list(range(1, ROUNDS + 1)),
                    "Decision": [""] * ROUNDS,
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

# ---------------------------- Logic Helpers ------------------------------ #
def apply_decision(role: str, decision: str):
    delay = 0
    cost = 0

    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
            cost += GATE_FEE
        else:  # Shared
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


# ------------------------------ UI --------------------------------------- #
def main():
    st.set_page_config(
        page_title="Flight Turn Simulation", page_icon="🛫", layout="wide"
    )
    st.title("🛫 Flight-Turn MIS Simulation")
    init_state()

    with st.sidebar:
        st.header("Select Role & Round")
        role = st.selectbox("Role", ROLES)
        round_num = st.session_state.current_round
        st.markdown(f"**Current Round:** {round_num}")

        with st.expander("🔐 Instructor Panel"):
            pw = st.text_input("Password", type="password")
            if pw == INSTRUCTOR_PW:
                st.success("Instructor mode active")
                if st.button("Advance Round ➡️") and round_num < ROUNDS:
                    st.session_state.current_round += 1
                if st.button("Reset Game"):
                    for k in list(st.session_state.keys()):
                        del st.session_state[k]
                    st.experimental_rerun()

    st.subheader(f"{role} – Round {round_num}")
    df_role = st.session_state.turn_data[role]

    if df_role.at[round_num - 1, "Decision"] == "":
        if role == "Airport_Ops":
            decision = st.radio("Gate Strategy", ["Dedicated Gate", "Shared Gate"])
        elif role == "Airline_Control":
            decision = st.radio("Crew Buffer", ["No Buffer", "Buffer 10"])
        else:
            decision = st.radio("MEL Decision", ["Fix Now", "Defer"])

        if st.button("Submit Decision"):
            delay, cost = apply_decision(role, decision)

            # Add event delay to Airport Ops record for simplicity
            event_label, event_delay = st.session_state.events[round_num - 1]
            if role == "Airport_Ops":
                delay += event_delay

            # Compute total cost (role cost + delay over 45 min)
            total_cost = cost + max(delay - ON_TIME_MIN, 0) * COST_PER_DELAY_MIN

            df_role.at[round_num - 1, "Decision"] = decision
            df_role.at[round_num - 1, "RoleDelay"] = delay
            df_role.at[round_num - 1, "RoleCost"] = total_cost
            update_kpi(role)
            st.success("Decision recorded!")
            st.experimental_rerun()
    else:
        st.info("Decision already submitted for this round.")

    st.write("### Role Ledger")
    st.dataframe(df_role)

    st.write("### Current Event Card")
    st.write(st.session_state.events[round_num - 1][0])

    st.write("---")
    st.subheader("Class KPI Scoreboard (cumulative)")
    st.dataframe(st.session_state.kpi)


if __name__ == "__main__":
    main()
