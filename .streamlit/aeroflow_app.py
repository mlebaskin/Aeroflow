"""MMIS 494 Flight Turn Simulation – Streamlit App (v0.4b)

Teams coordinate one flight turnaround across Airport Ops,
Airline Control, and Maintenance.  Lowest total cost after
five rounds wins.  Uses st.rerun() for Streamlit ≥1.27.
"""

import random
from typing import Dict

import pandas as pd
import streamlit as st

# ─────────────────────────── Config ──────────────────────────────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45            # minutes allowed on the ground
COST_PER_DELAY_MIN = 100    # dollars for each extra minute
GATE_FEE = 500              # dollars for a private (dedicated) gate
MEL_FIX_COST = 300          # dollars when fixing right away
MEL_PENALTY = 1000          # dollars if a deferred item becomes a problem

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

EVENT_CARDS = [
    ("Smooth turn", 0),
    ("Busy ramp", 5),
    ("Catering truck late", 10),
    ("Thunderstorm nearby", 15),
]

# ─────────────────────── Session-State Setup ─────────────────────────── #
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
def apply_decision(role: str, decision: str):
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
    role = st.sidebar.selectbox("Choose your role", ROLES)
    round_num = st.session_state.current_round
    st.sidebar.markdown(f"**Round:** {round_num} of {ROUNDS}")

    st.sidebar.markdown(
        "### Game Facts\n"
        f"• On-time goal: **{ON_TIME_MIN} min** or less\n\n"
        f"• Delay fine: **${COST_PER_DELAY_MIN}** per minute over {ON_TIME_MIN}\n\n"
        f"• Private gate fee: **${GATE_FEE}**\n\n"
        f"• Fix-now cost: **${MEL_FIX_COST}**\n\n"
        f"• Deferred item penalty: **${MEL_PENALTY}**"
    )

    # ─ Instructor controls
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
    st.warning(f"EVENT: {event_label}  (+{event_delay} minutes)")

    df_role = st.session_state.turn_data[role]

    if df_role.at[round_num - 1, "Decision"] == "-":
        # Cheat-sheets and decision inputs
        if role == "Airport_Ops":
            st.markdown(
                "• **Private Gate** costs $500 but adds **0** delay.\n"
                "• **Shared Gate** is free but has a 50 % risk of **+10 min**."
            )
            decision = st.radio("Pick your gate plan:",
                                ["Dedicated Gate", "Shared Gate"])

        elif role == "Airline_Control":
            st.markdown(
                "• **No Buffer**: 30 min swap, 40 % risk of **+15 min**.\n"
                "• **Buffer 10**: 40 min swap, no risk."
            )
            decision = st.radio("Pick your crew plan:",
                                ["No Buffer", "Buffer 10"])

        else:  # Maintenance
            st.markdown(
                "**MEL = Minimum Equipment List.** It lists parts a"
                " plane can temporarily fly without.\n\n"
                "• **Fix Now** → +20 min and $300, problem solved.\n"
                "• **Defer**   → 0 delay now, 20 % risk of $1 000 later."
            )
            decision = st.radio("Fix now or defer?",
                                ["Fix Now", "Defer"])

        if st.button("Submit Decision"):
            delay, cost = apply_decision(role, decision)
            if role == "Airport_Ops":
                delay += event_delay
            total_cost = cost + max(delay - ON_TIME_MIN, 0) * COST_PER_DELAY_MIN

            df_role.loc[
                round_num - 1, ["Decision", "RoleDelay", "RoleCost"]
            ] = [decision, delay, total_cost]
            update_kpi(role)

            st.info(f"You added **{delay} min** and **${total_cost}** cost.")
            st.success("Decision saved!")
            st.rerun()
    else:
        st.info("Decision already made for this round.")

    st.write("### Your Role Ledger")
    st.dataframe(df_role, use_container_width=True)

    st.write("---")
    st.subheader("Class Scoreboard so far")
    st.dataframe(st.session_state.kpi, use_container_width=True)

# ─────────────────────────── Main Page ───────────────────────────────── #
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
**Goal** – Keep the plane on the ground **{ON_TIME_MIN} min or less** and spend the least money.

| Role | Choice A | Choice B | Risk |
|------|----------|----------|------|
| Airport Ops | Private Gate ($500, 0 min) | Shared Gate ($0, 50 % +10 min) | Gate clash |
| Airline Control | No Buffer (30 min, 40 % +15 min) | Buffer 10 (40 min, safe) | Crew late |
| Maintenance | Fix Now (+20 min, $300) | Defer (20 % $1 000) | Extra cost later |

**Each Round**  
1. Read the **EVENT** banner.  
2. Make your choice and press **Submit Decision**.  
3. Instructor clicks **Next Round**.  
4. Watch the scoreboard change.

**Scoring**  
Any delay over {ON_TIME_MIN} min costs **${COST_PER_DELAY_MIN}** per minute.  
After {ROUNDS} rounds, the team with the lowest total cost wins.
"""
        )

    with tab_play:
        simulation_ui()


if __name__ == "__main__":
    main()
