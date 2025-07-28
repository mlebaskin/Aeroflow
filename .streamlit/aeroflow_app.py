"""MMIS 494 Aviation MIS Simulation – Integrated Timeline (v1.3)

Adds:
• Loud GAME-OVER recap with role ledgers + team totals
• Notes column shown during play (penalty / no-penalty, clashes, etc.)
"""

import random
from typing import Dict, List

import pandas as pd
import streamlit as st

# ───────── Config ───────── #
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
    ("Yikes! Wildlife picnic on the runway—bird-shooing takes time!", 8),
    ("Fuel truck hit gridlock—driver’s still downtown!", 12),
    ("Half the ground crew called in sick—slow going.", 9),
    ("Snow squall—de-icing trucks coat the jet in minty glycol.", 15),
    ("Baggage belt jam—suitcases raining onto the ramp!", 7),
    ("Power outage! Gate lights go dark until a breaker flips.", 10),
    ("Disaster! Catering cart dumps tomato soup on bags.", 6),
    ("Lightning dance overhead—ramp ops halt until clear.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ───────── Helpers ───────── #
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

def all_decided(idx):
    return all(st.session_state.round_data[r].at[idx, "Decision"] != "-" for r in ROLES)

def build_timeline(idx):
    start = 0
    rows = []
    evt_text, evt_delay = st.session_state.events[idx]

    ap = st.session_state.round_data["Airport_Ops"].loc[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append(["Airport_Ops", start, ap_end])

    al = st.session_state.round_data["Airline_Control"].loc[idx]
    al_end = ap_end + al.Duration
    rows.append(["Airline_Control", ap_end, al_end])

    mx = st.session_state.round_data["Maintenance"].loc[idx]
    mx_end = al_end + mx.Duration
    rows.append(["Maintenance", al_end, mx_end])

    st.session_state.timeline[idx] = pd.DataFrame(rows, columns=["Role", "Start", "End"])

    extra = max(mx_end - ON_TIME_MIN, 0)
    fine = extra * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.round_data[r].at[idx, "Cost"] += fine / 3

    # update KPI
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

    df.loc[idx, ["Decision", "Duration", "Cost", "Notes"]] = [decision, dur, cost, note]

    if all_decided(idx):
        build_timeline(idx)
        st.session_state.current_round = min(idx + 2, ROUNDS)

def latest_ground_time():
    for board in reversed(st.session_state.timeline):
        if board is not None:
            return board["End"].max()
    return 0

def game_over():
    if st.session_state.current_round < ROUNDS:
        return False
    return all("-" not in df["Decision"].values for df in
               st.session_state.round_data.values())

# ───────── UI pieces ───────── #
def kpi_meters():
    total_cost = st.session_state.kpi["Cost"].sum()
    col1, col2 = st.columns(2)
    col1.metric("💸 Team Cost", f"${total_cost:,.0f}")
    col2.metric("⏱️ Last Ground Time",
                f"{latest_ground_time()} min",
                delta=f"{latest_ground_time() - ON_TIME_MIN:+}")

def sidebar(role, rnd):
    st.sidebar.header("Game Facts")
    st.sidebar.markdown(
        f"- On-time goal: **{ON_TIME_MIN} min**\n"
        f"- Delay fine: **${FINE_PER_MIN}/min** over goal\n"
        f"- Gate fee: **${GATE_FEE}** • Fix-now: **${MX_FIX_COST}**\n"
        f"- Defer risk: **40 % → ${MX_PENALTY}**"
    )
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Pwd", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Skip to Next Round"):
                st.session_state.current_round = min(rnd + 1, ROUNDS)
                st.rerun()
            if st.button("Reset Game"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

def decision_widget(role, idx):
    if role == "Airport_Ops":
        choice = st.radio("Gate choice",
                          ["Private Gate", "Shared Gate"])
    elif role == "Airline_Control":
        choice = st.radio("Crew choice",
                          ["No Buffer", "Buffer 10"])
    else:
        choice = st.radio("Maintenance choice",
                          ["Fix Now", "Defer"])
    if st.button("Submit"):
        record(role, idx, choice)
        st.rerun()

# ───────── Main app ───────── #
def main():
    st.set_page_config(page_title="MMIS 494 Aviation MIS Simulation",
                       page_icon="🛫", layout="wide")
    st.title("🛫 MMIS 494 Aviation MIS Simulation")
    init_state()

    tab_play, tab_guide = st.tabs(["Play the Game", "How to Play"])

    with tab_guide:
        st.header("Quick Rules")
        st.markdown(
            f"""
1. Each round pick an option for your role.  
2. Tasks run **Airport → Airline → Maintenance**.  
3. If total ground time > {ON_TIME_MIN} min, everyone shares the delay fine.  
4. Lowest total cost after {ROUNDS} rounds wins.
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
            decision_widget(role, rnd - 1)
        else:
            st.info("You already submitted.")

        st.markdown("#### Your Role Ledger")
        st.dataframe(st.session_state.round_data[role]
                     .drop(columns="Round"), height=200)

        st.markdown("#### Round Timeline")
        board = st.session_state.timeline[rnd - 1]
        if board is not None:
            st.dataframe(board)
        else:
            st.info("Waiting for other roles…")

        if game_over():
            st.balloons()
            st.success("🏁 GAME OVER – Final Results")
            for r in ROLES:
                st.write(f"##### {r}")
                st.dataframe(st.session_state.round_data[r]
                             .style.format({\"Cost\": \"${:,.0f}\"}))
            total_cost = st.session_state.kpi[\"Cost\"].sum()
            final_time = st.session_state.timeline[-1][\"End\"].max()
            st.info(f\"**Team Cost:** ${total_cost:,.0f}   |   "
                    f\"**Ground Time:** {final_time} min\")

if __name__ == \"__main__\":\n    main()\n```

### What’s back + new

* **Notes column** visible while playing (penalty hits, clashes, etc.).
* **Obvious GAME OVER** banner (confetti balloons 🎈) with each role’s ledger and final team totals.
* **KPI meters** stay at top, no scrolling.
* Event cards keep their new dramatic flair.

Push → commit → rerun and you should have personality *and* clarity.
::contentReference[oaicite:0]{index=0}
