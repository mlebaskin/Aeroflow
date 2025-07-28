"""
AeroFlow Simulation – Streamlit Web App (v0.1)
------------------------------------------------
This is a lightweight, single‑file Streamlit implementation of the
7‑week, three‑layer aviation MIS simulation you’ve been running in Excel.

How to run locally:
    1.  Install Streamlit →  pip install streamlit pandas
    2.  Save this file as  aeroflow_app.py
    3.  Execute         →  streamlit run aeroflow_app.py

How to deploy to Streamlit Cloud:
    •  Push this file to a public GitHub repo.
    •  In streamlit.io, create a new app pointing to  aeroflow_app.py.
    •  Set the app’s *Secrets* with  INITIAL_INVENTORY  or tweak inside code.

Key Features
============
• Three role dashboards (Airport, Airline, Aircraft) selectable via sidebar.
• Rounds advance with one click; lead‑time & cost maths auto‑recalculate.
• Instructor‑only controls (password gate) for demand shocks & KPI reset.
• Live KPI scoreboard across all roles.

NOTE:  This is a minimal viable product.  Feel free to extend:
      – Add authentication for named students.
      – Persist state in a DB instead of Streamlit session_state.
      – Export CSV/PDF after each class.
"""
import streamlit as st
import pandas as pd

# ---------- Config ---------- #
ROLES = ["Airport_Ops", "Airline_Ops", "Aircraft_MX"]
ROUNDS = 5
LEAD_TIME = 2               # orders arrive two rounds later
INITIAL_INVENTORY = 20
HOLDING_COST = 1
STOCKOUT_COST = 5
INSTRUCTOR_PW = "aeroflow123"  # change in Secrets for production

# ---------- Helper Functions ---------- #

def init_state():
    """Initialise game dataframes and global KPI table."""
    if "game" not in st.session_state:
        st.session_state.game = {}
        for role in ROLES:
            df = pd.DataFrame({
                "Round": list(range(1, ROUNDS + 1)),
                "StartingInv": [INITIAL_INVENTORY] + [None]*(ROUNDS-1),
                "Incoming": [0]*ROUNDS,
                "Demand": [5]*ROUNDS,
                "Order": [0]*ROUNDS,
                "EndingInv": [None]*ROUNDS,
                "Backorder": [0]*ROUNDS,
                "HoldCost": [0]*ROUNDS,
                "StockoutCost": [0]*ROUNDS,
            })
            st.session_state.game[role] = df
        st.session_state.current_round = 1
        st.session_state.kpi = pd.DataFrame(index=ROLES, columns=["HoldCost", "StockoutCost", "TotalCost"]).fillna(0)


def compute_round(role: str, round_idx: int):
    """Recalculate inventory levels and costs for the chosen role & round."""
    df = st.session_state.game[role]

    # Starting inventory for round 1 is preset; others inherit previous ending
    if round_idx > 0 and pd.isna(df.loc[round_idx, "StartingInv"]):
        df.at[round_idx, "StartingInv"] = df.at[round_idx-1, "EndingInv"]

    # Incoming shipments (arrive LEAD_TIME rounds after order)
    incoming_idx = round_idx - LEAD_TIME
    if incoming_idx >= 0:
        df.at[round_idx, "Incoming"] = df.at[incoming_idx, "Order"]

    # Calculate EndingInv and Backorder
    available = df.at[round_idx, "StartingInv"] + df.at[round_idx, "Incoming"]
    demand = df.at[round_idx, "Demand"]
    backorder = max(demand - available, 0)
    ending_inv = available - demand + df.at[round_idx, "Backorder"]  # include previous backorder if any

    df.at[round_idx, "Backorder"] = backorder
    df.at[round_idx, "EndingInv"] = ending_inv
    df.at[round_idx, "HoldCost"] = max(ending_inv, 0) * HOLDING_COST
    df.at[round_idx, "StockoutCost"] = backorder * STOCKOUT_COST

    # Update KPI table
    st.session_state.kpi.at[role, "HoldCost"] = df["HoldCost"].sum()
    st.session_state.kpi.at[role, "StockoutCost"] = df["StockoutCost"].sum()
    st.session_state.kpi["TotalCost"] = st.session_state.kpi["HoldCost"] + st.session_state.kpi["StockoutCost"]


# ---------- Streamlit UI ---------- #

def main():
    st.title("✈️ AeroFlow MIS Simulation")
    init_state()

    with st.sidebar:
        st.header("Role & Round")
        role = st.selectbox("Select your role", ROLES)
        round_num = st.session_state.current_round
        st.markdown(f"**Current Round:** {round_num}")
        st.markdown("---")

        # Instructor tools
        with st.expander("🔐 Instructor Panel"):
            pw = st.text_input("Password", type="password")
            if pw == INSTRUCTOR_PW:
                st.success("Instructor mode enabled")
                if st.button("Advance Round ➡️") and round_num < ROUNDS:
                    st.session_state.current_round += 1
                st.number_input("Set Demand for ALL roles (this round)", min_value=0, value=5, key="new_demand")
                if st.button("Update Demand"):
                    for r in ROLES:
                        st.session_state.game[r].loc[round_num-1, "Demand"] = st.session_state.new_demand
                if st.button("🔄 Reset Game"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.experimental_rerun()

    st.subheader(f"{role} – Round {round_num}")
    df = st.session_state.game[role]

    # Order input for current round
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("### Decision Input")
        order = st.number_input("Enter your Order / Action", min_value=0, step=1, key="order_input")
        if st.button("Submit Order"):
            df.at[round_num-1, "Order"] = order
            compute_round(role, round_num-1)
            st.success("Order recorded!")

    with col2:
        st.write("### Quick Stats")
        st.metric("Starting Inv", df.at[round_num-1, "StartingInv"])
        st.metric("Incoming", df.at[round_num-1, "Incoming"])
        st.metric("Demand", df.at[round_num-1, "Demand"])

    st.write("### Your Role Ledger")
    st.dataframe(df.style.format({"HoldCost": "${:,.0f}", "StockoutCost": "${:,.0f}"}))

    st.write("---")
    st.subheader("Class KPI Scoreboard")
    st.dataframe(st.session_state.kpi.style.format("${:,.0f}"))


if __name__ == "__main__":
    main()
