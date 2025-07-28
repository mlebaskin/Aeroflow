"""MMIS 494 Aviation MIS Simulation – Integrated Timeline (v1.5)

Clean UI: sidebar, round banner, KPI meters, tidy tables, GAME OVER recap.
"""

import random
from typing import Dict, List
import pandas as pd
import streamlit as st

# ───── Config ───── #
ROLES = ["Airport Operations", "Airline Control Center", "Aircraft Maintenance"]
ROUNDS = 5
ON_TIME_MIN = 45
FINE_PER_MIN = 100

# Baseline task minutes
GATE_PVT, GATE_SHR = 10, 10
CREW_NB, CREW_B10 = 30, 40
MX_FIX, MX_DEF = 20, 0

# Costs
GATE_FEE = 500
MX_FIX_COST = 300
MX_PENALTY = 1000
MX_PENALTY_PROB = 0.4

EVENT_CARDS = [
    ("Wildlife picnic on the runway—bird-shooing takes time!", 8),
    ("Fuel truck stuck in traffic—driver’s still downtown!", 12),
    ("Half the ramp crew called in sick—slow loading.", 9),
    ("Snow squall—de-icing trucks coat the jet in minty glycol.", 15),
    ("Baggage belt jam—bags raining onto the ramp!", 7),
    ("Power outage! Gate lights go dark until a breaker flips.", 10),
    ("Catering cart dumps tomato soup on suitcases—messy cleanup!", 6),
    ("Lightning boogie overhead—ramp ops pause until clear.", 11),
]

INSTRUCTOR_PW = st.secrets.get("INSTRUCTOR_PW", "flight123")

# ───── Helpers ───── #
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {
            r: pd.DataFrame(
                {"Round": range(1, ROUNDS + 1),
                 "Decision": ["-"] * ROUNDS,
                 "Duration": [0] * ROUNDS,
                 "Cost": [0] * ROUNDS,
                 "Notes": [""] * ROUNDS}
            ) for r in ROLES
        }
        st.session_state.events = random.sample(EVENT_CARDS, ROUNDS)
        st.session_state.timeline: List[pd.DataFrame] = [None] * ROUNDS
        st.session_state.kpi = pd.DataFrame(index=ROLES,
                                            columns=["Delay", "Cost"]).fillna(0)
        st.session_state.round = 1

def everyone_done(idx):
    return all(st.session_state.data[r].at[idx, "Decision"] != "-" for r in ROLES)

def build_board(idx):
    rows, start = [], 0
    evt_text, evt_delay = st.session_state.events[idx]

    ap = st.session_state.data[ROLES[0]].loc[idx]
    ap_end = start + ap.Duration + evt_delay
    rows.append([ROLES[0], start, ap_end])

    ac = st.session_state.data[ROLES[1]].loc[idx]
    ac_end = ap_end + ac.Duration
    rows.append([ROLES[1], ap_end, ac_end])

    mx = st.session_state.data[ROLES[2]].loc[idx]
    mx_end = ac_end + mx.Duration
    rows.append([ROLES[2], ac_end, mx_end])

    st.session_state.timeline[idx] = pd.DataFrame(rows, columns=["Role", "Start", "End"])

    extra = max(mx_end - ON_TIME_MIN, 0)
    fine = extra * FINE_PER_MIN
    if fine:
        for r in ROLES:
            st.session_state.data[r].at[idx, "Cost"] += fine / 3

    for r in ROLES:
        df = st.session_state.data[r]
        st.session_state.kpi.at[r, "Delay"] = df["Duration"].sum()
        st.session_state.kpi.at[r, "Cost"] = df["Cost"].sum()

def record(role, idx, choice):
    df = st.session_state.data[role]
    if role == ROLES[0]:
        if choice == "Private Gate":
            dur, cost, note = GATE_PVT, GATE_FEE, "Private gate"
        else:
            dur, cost, note = GATE_SHR, 0, "Shared gate"
            if random.random() < 0.5:
                dur += 10
                note += " (+10 clash)"
    elif role == ROLES[1]:
        if choice == "No Buffer":
            dur, cost, note = CREW_NB, 0, "No buffer"
            if random.random() < 0.4:
                dur += 15
                note += " (+15 late crew)"
        else:
            dur, cost, note = CREW_B10, 0, "Buffer 10"
    else:
        if choice == "Fix Now":
            dur, cost, note = MX_FIX, MX_FIX_COST, "Fixed now"
        else:
            dur, cost, note = MX_DEF, 0, "Defer"
            if random.random() < MX_PENALTY_PROB:
                cost += MX_PENALTY
                note += " – Penalty $1k"
            else:
                note += " – No penalty"
    df.loc[idx, ["Decision", "Duration", "Cost", "Notes"]] = [choice, dur, cost, note]

    if everyone_done(idx):
        build_board(idx)
        st.session_state.round = min(idx + 2, ROUNDS)

def latest_time():
    boards = [b for b in st.session_state.timeline if b is not None]
    return boards[-1]["End"].max() if boards else 0

def game_over():
    if st.session_state.round <= ROUNDS - 1:
        return False
    return all("-" not in df["Decision"].values for df in st.session_state.data.values())

# ───── UI ───── #
def sidebar(role, rnd):
    st.sidebar.write(f"### Round {rnd} – {role}")
    st.sidebar.markdown(
        f"- Goal ≤ **{ON_TIME_MIN} min**\n"
        f"- Delay fine **${FINE_PER_MIN}/min** (split)\n"
        f"- Gate fee **${GATE_FEE}** | Fix-now **${MX_FIX_COST}**\n"
        f"- Defer risk **40 % → ${MX_PENALTY}**")
    with st.sidebar.expander("Instructor"):
        pw = st.text_input("Password", type="password")
        if pw == INSTRUCTOR_PW:
            if st.button("Next Round"):
                st.session_state.round = min(rnd + 1, ROUNDS)
                st.rerun()
            if st.button("Reset Game"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

def kpi_strip():
    total_cost = st.session_state.kpi["Cost"].sum()
    col1, col2 = st.columns(2)
    col1.metric("💸 Team Cost", f"${total_cost:,.0f}")
    col2.metric("⏱️ Last Ground Time", f"{latest_time()} min",
                delta=f"{latest_time() - ON_TIME_MIN:+}")

# ───── Main ───── #
def main():
    st.set_page_config("MMIS 494 Aviation MIS Simulation", "🛫", layout="wide")
    st.title("🛫 MMIS 494 Aviation MIS Simulation")
    init_state()

    play, guide = st.tabs(["Play", "How to Play"])

    with guide:
        st.header("Role Briefs")
        st.markdown(
            """
**Airport Operations (Ramp Supervisor)**  
Loads bags, attaches jet-bridge, plans pushback.  
*Choices* → **Private Gate** (no conflict, +$500) / **Shared Gate** (free, 50 % risk +10 min)

**Airline Control Center (Dispatcher)**  
Swaps crews, files flight plan.  
*Choices* → **No Buffer** (fast but 40 % risk +15 min) / **Buffer 10** (safe, +10 min)

**Aircraft Maintenance (Tech Crew)**  
Fixes or defers defects.  
*Choices* → **Fix Now** (+20 min, +$300) / **Defer** (0 min, 40 % risk $1 000)
"""
        )

    with play:
        rnd = st.session_state.round
        role = st.sidebar.selectbox("Select your role", ROLES)
        sidebar(role, rnd)
        kpi_strip()

        # Event card
        evt_text, evt_delay = st.session_state.events[rnd - 1]
        st.warning(f"{evt_text}\n\n(+{evt_delay} min)")

        # Decision widget
        if st.session_state.data[role].at[rnd - 1, "Decision"] == "-":
            options = ("Private Gate", "Shared Gate") if role == ROLES[0] else \
                      ("No Buffer", "Buffer 10") if role == ROLES[1] else \
                      ("Fix Now", "Defer")
            choice = st.radio("Your move:", options)
            if st.button("Submit Decision"):
                record(role, rnd - 1, choice)
                st.rerun()
        else:
            st.info("Decision already submitted.")

        # Role ledger
        st.write("#### Your Ledger")
        st.table(st.session_state.data[role].drop(columns="Round"))

        # Timeline board
        st.write("#### Timeline Board")
        board = st.session_state.timeline[rnd - 1]
        st.table(board) if board is not None else st.info("Waiting for other roles…")

        # Game over
        if game_over():
            st.balloons()
            st.success("🏁 GAME OVER – Final Totals")
            for r in ROLES:
                st.write(f"##### {r}")
                st.table(st.session_state.data[r].style.format({"Cost": "${:,.0f}"}))
            tot_cost = st.session_state.kpi["Cost"].sum()
            final_time = st.session_state.timeline[-1]["End"].max()
            st.info(f"Team Cost **${tot_cost:,.0f}** | Ground Time **{final_time} min**")

if __name__ == "__main__":
    main()
