from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

st.set_page_config(
    page_title="Paris Explorer | Global Culture Access Explorer",
    page_icon="🇫🇷",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.city_page import render_city_explorer

render_city_explorer("Paris")
