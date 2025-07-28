Flight‑Turn Simulation – Streamlit App (v0.1)
===========================================
Aviation‑specific replacement for the Beer Game: teams work together (or compete)
across three roles to push the *same* flight out on time for five consecutive
turns.  Decisions revolve around gate strategy, crew buffers, and maintenance
fix/deferral.  Costs are measured in delay minutes, crew overtime, gate fees,
and maintenance penalties.

Roles & Decisions
-----------------
* **Airport Ops** – Gate Strategy
    - Dedicated Gate  : +$500 fee, no gate conflict delay
    - Shared Gate     : $0 fee, 50% chance of 10‑min conflict delay

* **Airline Control** – Crew Buffer
    - No Buffer       : 30‑min crew change; 40% chance crew timeout (adds 15‑min)
    - Buffer 10       : 40‑min crew change (+10 ground minutes) but zero timeout risk

* **Maintenance** – MEL Fix vs Deferral
    - Fix Now         : +20‑min delay, +$300 labour, avoids MEL penalty
    - Defer           : 20% chance penalty $1000 if deferred item escalates

Each round has an **Event Card** adding a random disruption (e.g., ramp
congestion, weather) worth 0–15 minutes.

On‑time threshold is 45 minutes of ground time.  Every minute over 45 costs $100
(passenger comp, missed slots, etc.).  Lowest total cost after 5 rounds wins.

Deployment
----------
1.  pip install streamlit pandas
2.  streamlit run flight_turn_app.py
3.  Deploy to Streamlit Cloud exactly like aeroflow_app.py (requirements.txt is
    unchanged).
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
            df = pd.DataFrame({
                "Round": list(range(1, ROUNDS + 1)),
                "Decision": [""] * ROUNDS,
                "RoleDelay": [0] * ROUNDS,
                "RoleCost": [0] * ROUNDS,
            })
            st.session_state.turn_data[role] = df
        # event deck per round
        st.session_state.events = random.choices(EVENT_CARDS, k=ROUNDS)
        st.session_state.current_round = 1
        st.session_state.kpi = pd.DataFrame(index=ROLES, columns=["Delay", "Cost"]).fillna(0)


# ---------------------------- Logic Helpers ------------------------------ #

def apply_decision(role: str, decision: str, rnd_idx: int):
    """Return delay minutes and cost effects of the decision."""
    delay = 0
    cost = 0

    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
            cost += GATE_FEE
        elif decision == "Shared Gate":
            if random.random() < 0.5:
                delay += 10
    elif role == "Airline_Control":
        if decision == "No Buffer":
            base_delay = 30  # crew change time
            delay += base_delay
            if random.random() < 0.4:
                delay += 15  # crew timeout
        elif decision == "Buffer 10":
            delay += 40  # adds 10‑min buffer but no timeout risk
    elif role == "Maintenance":
        if decision == "Fix Now":
            delay += 20
            cost += MEL_FIX_COST
        elif decision == "Defer":
            if random.random() < 0.2:
                cost += MEL_PENALTY
    return delay, cost


def update_kpi(role: str):
    df = st.session_state.turn_data[role]
    st.session_state.kpi.at[role, "Delay"] = df["RoleDelay"].sum()
    st.session_state.kpi.at[role, "Cost"] = df["RoleCost"].sum()


# ------------------------------ UI --------------------------------------- #

def main():
    st.set_page_config(page_title="Flight Turn Simulation", page_icon="🛫", layout="wide")
    st.title("🛫 Flight‑Turn MIS Simulation")
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
                if st.button("Advance Round ➡️", key="adv") and round_num < ROUNDS:
                    st.session_state.current_round += 1
                if st.button("Reset Game", key="reset"):
                    for k in list(st.session_state.keys()):
                        del st.session_state[k]
                    st.experimental_rerun()

    st.subheader(f"{role} – Round {round_num}")
    df_role = st.session_state.turn_data[role]

    if df_role.at[round_num - 1, "Decision"] == "":
        # Decision input only if not already taken
        if role == "Airport_Ops":
            decision = st.radio("Gate Strategy", ["Dedicated Gate", "Shared Gate"])
        elif role == "Airline_Control":
            decision = st.radio("Crew Buffer", ["No Buffer", "Buffer 10"])
        else:
            decision = st.radio("MEL Decision", ["Fix Now", "Defer"])

        if st.button("Submit Decision"):
            delay, cost = apply_decision(role, decision, round_num - 1)
            # Event delay applies only once globally; attach to Airport Ops record for simplicity
            event_label, event_delay = st.session_state.events[round_num - 1]
            if role == "Airport_Ops":
                delay += event_delay

            df_role.at[round_num - 1, "Decision"] = decision
            df_role.at[round_num - 1, "RoleDelay"] = delay
            df_role.at[round_num - 1, "RoleCost"] = cost + max(delay - ON_TIME_MIN, 0) * COST_PER_DELAY_MIN
            update_kpi(role)
            st.success("Decision recorded!")
            st.experimental_rerun()
    else:
        st.info("Decision already submitted for this round.")

    st.write("### Role Ledger")
    st.dataframe(df_role)

    # Show event card for info
    st.write("### Current Event Card")
    st.write(st.session_state.events[round_num - 1][0])

    st.write("---")
    st.subheader("Class KPI Scoreboard (cumulative)")
    st.dataframe(st.session_state.kpi)


if __name__ == "__main__":
    main()
