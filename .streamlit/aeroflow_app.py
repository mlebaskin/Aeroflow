"""MMIS 494 Flight Turn Simulation – Streamlit App (v0.5)

Adds bar charts for current Cost and Delay by role,
plus a line chart of total team cost across rounds.
"""

import random
from typing import Dict

import pandas as pd
import streamlit as st

# ─────────────────────────── Config ──────────────────────────────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
COST_PER_DELAY_MIN = 100
GATE_FEE = 500
MEL_FIX_COST = 300
MEL_PENALTY = 1000

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

EVENT_CARDS = [
    ("Smooth turn", 0),
    ("Busy ramp", 5),
    ("Catering truck late", 10),
    ("Thunderstorm nearby", 15),
]

# ───────────────────── Session State Init ────────────────────────────── #
def init_state():
    if "turn_data" not in st.session_state:
        st.session_state.turn_data: Dict[str, pd.DataFrame] = {}
        for role in ROLES:
            st.session_state.turn_data[role] = pd.DataFrame(
                {
                    "Round": list(range(1, ROUNDS + 1)),
                    "Decision": ["-"] * ROUNDS,
                    "RoleDelay": [0] * ROUNDS,
                    "RoleCost": [0] * ROUNDS,
                }
            )
        st.session_state.events = random.choices(EVENT_CARDS, k=ROUNDS)
        st.session_state.current_round = 1
        st.session_state.kpi = pd.DataFrame(
            index=ROLES, columns=["Delay", "Cost"]
        ).fillna(0)

# ───────────────────── Decision Logic ────────────────────────── #
def apply_decision(role, decision):
    delay = 0
    cost = 0
    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
            cost += GATE_FEE
        else:
            if random.random() < 0.5:
                delay += 10
    elif role == "Airline_Control":
        if decision == "No Buffer":
            delay += 30
            if random.random() < 0.4:
                delay += 15
        else:
            delay += 40
    else:  # Maintenance
        if decision == "Fix Now":
            delay += 20
            cost += MEL_FIX_COST
        else:
            if random.random() < 0.2:
                cost += MEL_PENALTY
    return delay, cost


def update_kpi(role):
    df = st.session_state.turn_data[role]
    st.session_state.kpi.at[role, "Delay"] = df["RoleDelay"].sum()
    st.session_state.kpi.at[role, "Cost"] = df["RoleCost"].sum()

# ───────────────────────── Simulation UI ──────────────────────────── #
def simulation_ui():
    role = st.sidebar.selectbox("Choose your role", ROLES)
    round_num = st.session_state.current_round
    st.sidebar.markdown(f"**Round:** {round_num} of {ROUNDS}")

    # Game facts panel
    st.sidebar.markdown(
        "### Game Facts\n"
        f"- On-time goal: **{ON_TIME_MIN} min** or less\n"
        f"- Delay fine: **${COST_PER_DELAY_MIN}** per extra minute\n"
        f"- Private gate fee: **${GATE_FEE}**\n"
        f"- Fix-now cost: **${MEL_FIX_COST}**\n"
        f"- Deferred penalty: **${MEL_PENALTY}**"
    )

    # Instructor controls
    with st.sidebar.expander("Instructor", expanded=False):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            st.success("Instructor mode on")
            if st.button("Next Round ➡️") and round_num < ROUNDS:
                st.session_state.current_round += 1
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

    st.subheader(f"{role} – Round {round_num}")

    # Event banner
    event_label, event_delay = st.session_state.events[round_num - 1]
    st.warning(f"EVENT: {event_label} (+{event_delay} min)")

    df_role = st.session_state.turn_data[role]

    if df_role.at[round_num - 1, "Decision"] == "-":
        # Cheat-sheets & decision radios
        if role == "Airport_Ops":
            st.markdown(
                "- Private Gate: $500, 0 delay.\n"
                "- Shared Gate: $0, 50% risk of +10 min."
            )
            decision = st.radio("Gate plan:", ["Dedicated Gate", "Shared Gate"])

        elif role == "Airline_Control":
            st.markdown(
                "- No Buffer: 30 min, 40% risk +15 min.\n"
                "- Buffer 10: 40 min, no risk."
            )
            decision = st.radio("Crew plan:", ["No Buffer", "Buffer 10"])

        else:  # Maintenance
            st.markdown(
                "**MEL = Minimum Equipment List**\n"
                "- Fix Now: +20 min, $300.\n"
                "- Defer: 0 delay, 20% risk of $1,000 later."
            )
            decision = st.radio("Maintenance:", ["Fix Now", "Defer"])

        if st.button("Submit Decision"):
            delay, cost = apply_decision(role, decision)
            if role == "Airport_Ops":
                delay += event_delay
            total_cost = cost + max(delay - ON_TIME_MIN, 0) * COST_PER_DELAY_MIN
            df_role.loc[round_num - 1, ["Decision", "RoleDelay", "RoleCost"]] = [
                decision,
                delay,
                total_cost,
            ]
            update_kpi(role)
            st.info(f"Result: +{delay} min, +${total_cost}")
            st.success("Decision saved!")
            st.rerun()
    else:
        st.info("Decision already submitted.")

    st.write("### Your Role Ledger")
    st.dataframe(df_role, use_container_width=True)

    # KPI visual section
    st.write("---")
    st.subheader("Class KPI – Cumulative")

    # Show numeric table
    st.dataframe(st.session_state.kpi.style.format({"Cost": "${:,.0f}"}))

    # Bar charts
    chart_data = st.session_state.kpi.copy()
    st.write("#### Cost by Role")
    st.bar_chart(chart_data["Cost"])

    st.write("#### Delay (minutes) by Role")
    st.bar_chart(chart_data["Delay"])

    # Line chart: total cost per round
    total_costs = []
    for i in range(ROUNDS):
        total = 0
        for df in st.session_state.turn_data.values():
            total += df.at[i, "RoleCost"]
        total_costs.append(total)
    cost_df = pd.DataFrame({"Round": list(range(1, ROUNDS + 1)),
                            "Total Cost": total_costs})
    st.write("#### Team Total Cost Over Rounds")
    st.line_chart(cost_df.set_index("Round"))

# ─────────────────────────── Main Page ──────────────────────────────── #
def main():
    st.set_page_config(page_title="MMIS 494 Flight Turn Simulation",
                       page_icon="🛫", layout="wide")
    st.title("🛫 MMIS 494 Flight Turn Simulation")
    init_state()

    tab_how, tab_play = st.tabs(["How to Play", "Play the Game"])

    with tab_how:
        st.header("Quick Guide")
        st.markdown(
            f"""
**Goal** – Keep ground time **≤ {ON_TIME_MIN} min** and spend the least money.

| Role | Choice A | Choice B |
|------|----------|----------|
| Airport Ops | Private Gate ($500, 0 min) | Shared Gate ($0, 50% +10 min) |
| Airline Control | No Buffer (30 min, 40% +15) | Buffer 10 (40 min, safe) |
| Maintenance | Fix Now (+20 min, $300) | Defer (20% $1,000) |

Delay over {ON_TIME_MIN} min costs **${COST_PER_DELAY_MIN}** per minute.
Lowest total after {ROUNDS} rounds wins.
"""
        )

    with tab_play:
        simulation_ui()


if __name__ == "__main__":
    main()
