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
ON_TIME_MIN = 45            # scheduled g
