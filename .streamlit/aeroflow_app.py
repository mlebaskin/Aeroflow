"""MMIS 494 Flight Turn Simulation – Integrated Timeline (v1.1)

• How-to-Play tab restored
• KPI table + bar charts + cost trend line on Play tab
• Integrated timeline, shared fine, spicy events, visible MEL penalties
"""

import random
from typing import Dict, List

import pandas as pd
import streamlit as st

# ─────────── Config ─────────── #
ROLES = ["Airport_Ops", "Airline_Control", "Maintenance"]
ROUNDS = 5

ON_TIME_MIN = 45
FINE_PER_MIN = 100

AIRPORT_PRIVATE = 10
AIRPORT_SHARED = 10
CREW_NO_BUFFER = 30
CREW_BUFFER_10 = 40
MX_FIX = 20
MX_DEFER = 0

GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY = 1000
MX_PENALTY_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife on runway – crews chase birds", 8),
    ("Fuel truck stuck in traffic", 12),
    ("Ground-crew shortage", 9),
    ("De-icing needed", 15),
    ("Baggage belt jam", 7),
    ("Gate power outage", 10),
    ("Catering cart spills soup", 6),
    ("Thunderstorm cell overhead", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ─────────── Helpers ─────────── #
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
        st.session_state.shared_fines = [0] * ROUNDS
        st.session_state.kpi = pd.DataFrame(index=ROLES,
                                            columns=["Delay", "Cost"]).fillna(0)


def decisions_done(idx: int) -> bool:
    return all(
        st.session_state.round_data[r].at[idx, "Decision"] != "-" for r in ROLES
    )


def build_timeline(idx: int):
    """Create start/end board and apply shared fine."""
    start = 0
    rows = []
    # Airport
    ap = st.session_state.round_data["Airport_Ops"].loc[idx]
    evt_label, evt_delay = st.session_state.events[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append(["Airport_Ops", start, ap_end])

    # Airline
    al = st.session_state.round_data["Airline_Control"].loc[idx]
    al_start, al_end = ap_end, ap_end + al.Duration
    rows.append(["Airline_Control", al_start, al_end])

    # Maintenance
    mx = st.session_state.round_data["Maintenance"].loc[idx]
    mx_start, mx_end = al_end, al_end + mx.Duration
    rows.append(["Maintenance", mx_start, mx_end])

    board = pd.DataFrame(rows, columns=["Role", "Start", "End"])
    st.session_state.timeline[idx] = board

    total_time = mx_end
    excess = max(total_time - ON_TIME_MIN, 0)
    fine = excess * FINE_PER_MIN
    st.session_state.shared_fines[idx] = fine
    if fine:
        for r in ROLES:
            st.session_state.round_data[r].at[idx, "Cost"] += fine / 3
    # Update KPI
    for r in ROLES:
        df = st.session_state.round_data[r]
        st.session_state.kpi.at[r, "Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r, "Cost"] = df["Cost"].sum()


def record(role: str, idx: int, decision: str):
    df = st.session_state.round_data[role]
    # Map decision to outcomes
    if role == "Airport_Ops":
        if decision == "Dedicated Gate":
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

    df.loc[idx, ["Decision", "Duration", "Cost", "Notes"]] = [
        decision,
        dur,
        cost,
        note,
    ]

    # When all roles decided build timeline & advance round
    if decisions_done(idx):
        build_timeline(idx)
        st.session_state.current_round = min(idx + 2, ROUNDS)


def game_over() -> bool:
    if st.session_state.current_round < ROUNDS:
        return False
    return all("-" not in df["Decision"].values for df in
               st.session_state.round_data.values())

# ─────────── UI building blocks ─────────── #
def sidebar(role, rnd):
    st.sidebar.header("Round info")
    st.sidebar.markdown(f"**Round:** {rnd} / {ROUNDS}")
    st.sidebar.markdown(
        f"- Private gate fee: ${GATE_FEE}\n"
        f"- Fix-now cost: ${MX_FIX_COST}\n"
        f"- Defer penalty: ${MX_PENALTY} (40 % risk)\n"
        f"- Delay fine: ${FINE_PER_MIN}/min over {ON_TIME_MIN}"
    )
    # Instructor
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            st.success("Instructor mode")
            if st.button("Next Round", key="next"):
                st.session_state.current_round = min(rnd + 1, ROUNDS)
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

def decision_form(role: str, idx: int):
    if role == "Airport_Ops":
        choice = st.radio("Gate option:",
                          ["Dedicated Gate", "Shared Gate"], key="pick")
    elif role == "Airline_Control":
        choice = st.radio("Crew option:",
                          ["No Buffer", "Buffer 10"], key="pick")
    else:
        choice = st.radio("Maintenance option:",
                          ["Fix Now", "Defer"], key="pick")
    if st.button("Submit"):
        record(role, idx, choice)
        st.rerun()

def kpi_section():
    st.markdown("### Cumulative KPI")
    kpi = st.session_state.kpi.copy()
    kpi_fmt = kpi.copy()
    kpi_fmt["Cost"] = kpi_fmt["Cost"].apply(lambda x: f"${x:,.0f}")
    st.dataframe(kpi_fmt)
    st.bar_chart(kpi["Cost"])
    st.bar_chart(kpi["Delay"])

    # Trend line
    total_costs = [
        sum(df.at[i, "Cost"] for df in st.session_state.round_data.values())
        for i in range(ROUNDS)
    ]
    st.line_chart(pd.DataFrame({"Total Cost": total_costs}))

# ─────────── Main app ─────────── #
def main():
    st.set_page_config(page_title="MMIS 494 Flight Turn Simulation",
                       page_icon="🛫", layout="wide")
    st.title("🛫 MMIS 494 Flight Turn Simulation – Integrated Timeline")
    init_state()

    tab_play, tab_guide = st.tabs(["Play the Game", "How to Play"])

    # ---------- Guide tab ----------
    with tab_guide:
        st.header("How to Play")
        st.markdown(
            f"""
**Roles & Choices**

| Role | Option A | Option B |
|------|----------|----------|
| Airport Ops | Private Gate ($500, 0 min) | Shared Gate ($0, 50 % +10 min) |
| Airline Control | No Buffer (30 min, 40 % +15 min) | Buffer 10 (40 min, safe) |
| Maintenance | Fix Now (+20 min, $300) | Defer (40 % $1 000) |

1. Everyone picks a choice for the round.  
2. Tasks run one after another **in the order Airport → Airline → Maintenance**.  
3. If the whole turnaround takes more than **45 min** the extra minutes are fined at **$100/min** and split between the three roles.  
4. Lowest total cost after 5 rounds wins.
"""
        )

    # ---------- Play tab ----------
    with tab_play:
        rnd = st.session_state.current_round
        role = st.selectbox("Select your role", ROLES, key="role_pick")
        sidebar(role, rnd)

        st.subheader(f"Round {rnd} decision – {role}")
        lbl, dly = st.session_state.events[rnd - 1]
        st.warning(f"**EVENT**\n{lbl}\n(+{dly} min)")

        if st.session_state.round_data[role].at[rnd - 1, "Decision"] == "-":
            decision_form(role, rnd - 1)
        else:
            st.info("You already submitted this round.")

        st.write("### Round Timeline")
        if st.session_state.timeline[rnd - 1] is not None:
            st.dataframe(st.session_state.timeline[rnd - 1])
        else:
            st.info("Waiting for all roles to decide…")

        kpi_section()

        if game_over():
            st.success("🎉 Game Over – Final Results")
            for i in range(ROUNDS):
                st.write(f"#### Timeline Round {i + 1}")
                st.dataframe(st.session_state.timeline[i])
            total_cost = st.session_state.kpi["Cost"].sum()
            total_delay = st.session_state.timeline[-1]["End"].max()
            st.info(f"**Team Cost:** ${total_cost:,.0f}   |   "
                    f"**Ground Time:** {total_delay} min")

if __name__ == "__main__":
    main()
