"""MMIS 494 Flight Turn Simulation – Streamlit App (v0.6)

Adds:
• End-of-game recap banner after Round 5
• Visible maintenance penalty note when Defer risk triggers
"""

import random
from typing import Dict

import pandas as pd
import streamlit as st

# ───────────────────────── Config ───────────────────────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
COST_PER_DELAY_MIN = 100
GATE_FEE = 500
MEL_FIX_COST = 300
MEL_PENALTY = 1000
PENALTY_PROB = 0.2  # 20 % risk

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

EVENT_CARDS = [
    ("Smooth turn", 0),
    ("Busy ramp", 5),
    ("Catering truck late", 10),
    ("Thunderstorm nearby", 15),
]

# ───────────────────── Session-state init ───────────────────── #
def init_state():
    if "turn_data" not in st.session_state:
        st.session_state.turn_data = {}
        for role in ROLES:
            st.session_state.turn_data[role] = pd.DataFrame(
                {
                    "Round": list(range(1, ROUNDS + 1)),
                    "Decision": ["-"] * ROUNDS,
                    "RoleDelay": [0] * ROUNDS,
                    "RoleCost": [0] * ROUNDS,
                    "Notes": [""] * ROUNDS,
                }
            )
        st.session_state.events = random.choices(EVENT_CARDS, k=ROUNDS)
        st.session_state.current_round = 1
        st.session_state.kpi = pd.DataFrame(index=ROLES,
                                            columns=["Delay", "Cost"]).fillna(0)

# ───────────────────── Decision logic ──────────────────────── #
def apply_decision(role, decision):
    delay = 0
    cost = 0
    note = ""

    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
            cost += GATE_FEE
        else:
            if random.random() < 0.5:
                delay += 10
                note = "+10 ramp clash"
    elif role == "Airline_Control":
        if decision == "No Buffer":
            delay += 30
            if random.random() < 0.4:
                delay += 15
                note = "+15 crew late"
        else:
            delay += 40
    else:  # Maintenance
        if decision == "Fix Now":
            delay += 20
            cost += MEL_FIX_COST
        else:
            if random.random() < PENALTY_PROB:
                cost += MEL_PENALTY
                note = "Penalty $1 000"

    return delay, cost, note


def update_kpi(role):
    df = st.session_state.turn_data[role]
    st.session_state.kpi.at[role, "Delay"] = df["RoleDelay"].sum()
    st.session_state.kpi.at[role, "Cost"] = df["RoleCost"].sum()

# ──────────────────── Helper: game over? ───────────────────── #
def game_finished():
    if st.session_state.current_round < ROUNDS:
        return False
    for df in st.session_state.turn_data.values():
        if "-" in df["Decision"].values:
            return False
    return True

# ───────────────────── Simulation UI ──────────────────────── #
def simulation_ui():
    role = st.sidebar.selectbox("Choose your role", ROLES)
    round_num = st.session_state.current_round
    st.sidebar.markdown(f"**Round:** {round_num} / {ROUNDS}")

    # Instructor controls
    with st.sidebar.expander("Instructor", False):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            st.success("Instructor mode")
            if st.button("Next Round ➡️") and round_num < ROUNDS:
                st.session_state.current_round += 1
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

    st.subheader(f"{role} – Round {round_num}")

    # Event banner
    evt_label, evt_delay = st.session_state.events[round_num - 1]
    st.warning(f"EVENT: {evt_label} (+{evt_delay} min)")

    df_role = st.session_state.turn_data[role]

    if df_role.at[round_num - 1, "Decision"] == "-":
        # Choices
        if role == "Airport_Ops":
            st.markdown("- Private Gate: $500, 0 delay\n"
                        "- Shared Gate: $0, 50% risk +10 min")
            decision = st.radio("Gate plan:", ["Dedicated Gate", "Shared Gate"])
        elif role == "Airline_Control":
            st.markdown("- No Buffer: 30 min, 40% risk +15\n"
                        "- Buffer 10: 40 min, safe")
            decision = st.radio("Crew plan:", ["No Buffer", "Buffer 10"])
        else:  # Maintenance
            st.markdown("**MEL = Minimum Equipment List**\n"
                        "- Fix Now: +20 min, $300\n"
                        "- Defer: 0 delay, 20% risk $1 000")
            decision = st.radio("Maintenance:", ["Fix Now", "Defer"])

        if st.button("Submit Decision"):
            delay, cost, note = apply_decision(role, decision)
            if role == "Airport_Ops":
                delay += evt_delay
            total_cost = cost + max(delay - ON_TIME_MIN, 0) * COST_PER_DELAY_MIN
            df_role.loc[round_num - 1,
                        ["Decision", "RoleDelay", "RoleCost", "Notes"]] = [
                            decision, delay, total_cost, note]
            update_kpi(role)
            st.success(f"Saved: +{delay} min, +${total_cost}")
            st.rerun()
    else:
        st.info("Decision already submitted.")

    st.write("### Role Ledger")
    st.dataframe(df_role, use_container_width=True)

    st.write("---")
    st.subheader("KPI – Cumulative Totals")
    st.dataframe(st.session_state.kpi.style.format({"Cost": "${:,.0f}"}))

    st.bar_chart(st.session_state.kpi["Cost"])
    st.bar_chart(st.session_state.kpi["Delay"])

    # Total cost trend
    totals = [sum(df["RoleCost"].iloc[i] for df in
             st.session_state.turn_data.values()) for i in range(ROUNDS)]
    trend_df = pd.DataFrame({"Round": range(1, ROUNDS + 1),
                             "Total Cost": totals})
    st.line_chart(trend_df.set_index("Round"))

    # End-of-game recap
    if game_finished():
        st.success("🎉 Game Over – final results below")
        for r in ROLES:
            st.write(f"#### {r}")
            st.dataframe(st.session_state.turn_data[r]
                         .drop(columns="Round")
                         .style.format({"RoleCost": "${:,.0f}"}))
        grand_cost = st.session_state.kpi["Cost"].sum()
        grand_delay = st.session_state.kpi["Delay"].sum()
        st.info(f"**Team Final Cost: ${grand_cost:,.0f}  |  "
                f"Total Delay: {grand_delay} min**")

# ───────────────────────── Main Page ──────────────────────── #
def main():
    st.set_page_config(page_title="MMIS 494 Flight Turn Simulation",
                       page_icon="🛫", layout="wide")
    st.title("🛫 MMIS 494 Flight Turn Simulation")
    init_state()

    tab_how, tab_play = st.tabs(["How to Play", "Play the Game"])
    with tab_how:
        st.write("See sidebar for game facts. Lowest cost after 5 rounds wins.")
    with tab_play:
        simulation_ui()


if __name__ == "__main__":
    main()
