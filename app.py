import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
import io
import datetime
import gc
import re
from sqlalchemy import text

st.set_page_config(page_title="Network Loss Impact Analyzer", layout="wide")

# --- INJEKSI KUSTOM CSS ---
st.markdown("""
<style>
    .stApp > header { background-color: transparent; border-top: 5px solid #EC2028; }
    
    /* STYLING METRIC CARDS MENGGUNAKAN METRIC-CONTAINER */
    div[data-testid="metric-container"] { 
        padding: 15px 20px; 
        border-radius: 10px; 
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08); 
        transition: transform 0.2s ease-in-out; 
    }
    div[data-testid="metric-container"]:hover { transform: translateY(-5px); }
    
    /* TEMA KOLOM 1: POTENSI (SOFT GREEN) */
    div[data-testid="column"]:nth-of-type(1) div[data-testid="metric-container"] { 
        background-color: #e8f5e9 !important; 
        border-left: 5px solid #28a745 !important; 
    }
    
    /* TEMA KOLOM 2: LOSS (SOFT RED) */
    div[data-testid="column"]:nth-of-type(2) div[data-testid="metric-container"] { 
        background-color: #fde0dc !important; 
        border-left: 5px solid #EC2028 !important; 
    }
    
    /* TEMA KOLOM 3: AKTUAL (SOFT BLUE) */
    div[data-testid="column"]:nth-of-type(3) div[data-testid="metric-container"] { 
        background-color: #e3f2fd !important; 
        border-left: 5px solid #0056b3 !important; 
    }
    
    [data-testid="stFileUploadDropzone"] { border: 2px dashed #EC2028; border-radius: 10px; background-color: #FCF4F4; }
</style>
""", unsafe_allow_html=True)

# --- HEADER LOGO ---
col_title, col_logo = st.columns([15, 1])
with col_title:
    st.markdown("<h1 style='margin-top: -15px;'>💸📉 Network Loss Impact Analyzer</h1>", unsafe_allow_html=True)
with col_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=60)
    else: st.markdown("<h1 style='margin-top: -15px; color: #EC2028; text-align: right;'>🔴</h1>", unsafe_allow_html=True)

st.write("Analisis Aktual, Potensi (Gain), dan Nilai Kerugian (Lost) Performa Site Secara Real-Time.")

... (rest of the code identically updated)
