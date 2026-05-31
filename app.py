import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Network Loss Impact", layout="wide")

# --- INJEKSI KUSTOM CSS TEMA TELKOMSEL & HIJAU POTENSI ---
st.markdown("""
<style>
    .stApp > header {
        background-color: transparent;
        border-top: 5px solid #EC2028;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border-left: 5px solid #EC2028;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease-in-out;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 15px rgba(236, 32, 40, 0.2);
    }
    [data-testid="stMetricValue"] {
        color: #EC2028;
        font-weight: 800;
    }
    [data-testid="column"]:nth-of-type(2) [data-testid="stMetric"] {
        border-left: 5px solid #28a745 !important;
    }
    [data-testid="column"]:nth-of-type(2) [data-testid="stMetric"]:hover {
        box-shadow: 0 6px 15px rgba(40, 167, 69, 0.2) !important;
    }
    [data-testid="column"]:nth-of-type(2) [data-testid="stMetricValue"] {
        color: #28a745 !important;
    }
    [data-testid="stFileUploadDropzone"] {
        border: 2px dashed #EC2028;
        border-radius: 10px;
        background-color: #FCF4F4;
    }
</style>
""", unsafe_allow_html=True)

st.title("💸 Network Loss Impact Dashboard")
st.write("Pantau Aktual, Potensi (Gain), dan *Lost* performa site berdasarkan kualitas *network*.")

# --- 1. LOAD MAPPING SITE ANAKAN & NAMA SITE DARI FILE LOKAL ---
@st.cache_data
def load_site_mapping():
    try:
        df_dapot = pd.read_excel("Dapot site kalimantan.xlsx", engine="openpyxl")
        df_dapot['Site ID'] = df_dapot['Site ID'].astype(str).str.strip().str.upper()
        
        mapping_anakan = dict(zip(df_dapot['Site ID'], df_dapot['Site Id Anakan'].astype(str)))
        mapping_name = dict(zip(df_dapot['Site ID'], df_dapot['SITE NAME'].astype(str)))
        
        return mapping_anakan, mapping_name
    except Exception as e:
        st.warning("⚠️ File 'Dapot site kalimantan.xlsx' tidak ditemukan. Fitur nama site dinonaktifkan.")
        return {}, {}

site_mapping, name_mapping = load_site_mapping()

# --- 2. LOGIC KALKULASI ---
def calculate_loss(df, site_id, mapping):
    child_sites_str = mapping.get(site_id, '')
    if child_sites_str == 'nan' or child_sites_str == '':
        child_list = []
    else:
        child_list = [x.strip().upper() for x in str(child_sites_str).split(',')]
    
    all_related_sites = list(set([site_id] + child_list))
    filtered_df = df[df['Site_ID'].isin(all_related_sites)].copy()
    
    if filtered_df.empty:
        return pd.DataFrame()
        
    def calc_potential(row, col_name):
        avail = row['Availability']
        pl = row['Packet_Loss']
        actual = row[col_name]
        
        if avail > 0 and pl < 1:
            success_rate = avail * (1 - pl)
            return actual / success_rate
        return actual
    
    filtered_df['Potential_Revenue'] = filtered_df.apply(lambda r: calc_potential(r, 'Actual_Revenue'), axis=1)
    filtered_df['Potential_Payload'] = filtered_df.apply(lambda r: calc_potential(r, 'Actual_Payload'), axis=1)
    
    filtered_df['Lost_Revenue'] = -1 * (filtered_df['Potential_Revenue'] - filtered_df['Actual_Revenue'])
    filtered_df['Lost_Payload'] = -1 * (filtered_df['Potential_Payload'] - filtered_df['Actual_Payload'])
    
    filtered_df['Availability_Pct'] = filtered_df['Availability'] * 100
    filtered_df['Packet_Loss_Pct'] = filtered_df['Packet_Loss'] * 100
    filtered_df['Type'] = filtered_df['Site_ID'].apply(lambda x: 'Parent' if x == site_id else 'Child')
    
    return filtered_df

# --- 3. BIKIN UI STREAMLIT ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    file_rev = st.file_uploader("📂 1. Upload/Drag & Drop Data Revenue", type=["csv", "xlsx", "xls"])
with col_up2:
    file_avail = st.file_uploader("📂 2. Upload/Drag & Drop Data Availability", type=["csv", "xlsx", "xls"])

if file_rev is not None and file_avail is not None:
    try:
        with st.spinner("Mengekstrak dan menggabungkan data..."):
            
            if file_rev.name.endswith('.csv'):
                df_rev = pd.read_csv(file_rev)
            else:
                df_rev = pd.read_excel(file_rev)
            df_rev.columns = df_rev.columns.str.strip() 
            
            if file_avail.name.endswith('.csv'):
                df_avail = pd.read_csv(file_avail)
            else:
                xls_avail = pd.ExcelFile(file_avail)
                sheet_target = xls_avail.sheet_names[0] 
                for sheet in xls_avail.sheet_names:
                    df_cek = pd.read_excel(xls_avail, sheet_name=sheet, nrows=1)
                    if any('Begin Time' in col for col in df_cek.columns):
                        sheet_target = sheet
                        break
                df_avail = pd.read_excel(xls_avail, sheet_name=sheet_target)
            df_avail.columns = df_avail.columns.str.strip() 
            
            df_rev['Date'] = pd.to_datetime(df_rev['date'], format='mixed').dt.date
            df_rev['Site_ID'] = df_rev['site_id'].astype(str).str.upper()
            
            rev_col = [c for c in df_rev.columns if 'revenue' in c.lower()][0]
            payload_col = [c for c in df_rev.columns if 'payload' in c.lower()][0]
            
            df_rev.rename(columns={rev_col: 'Actual_Revenue', payload_col: 'Actual_Payload'}, inplace=True)
            df_rev['Actual_Revenue'] = pd.to_numeric(df_rev['Actual_Revenue'], errors='coerce').fillna(0)
            df_rev['Actual_Payload'] = pd.to_numeric(df_rev['Actual_Payload'], errors='coerce').fillna(0) / 1024
            
            df_avail['Date'] = pd.to_datetime(df_avail['Begin Time'], format='mixed').dt.date
            df_avail['Site_ID'] = df_avail['Managed Element'].astype(str).str.extract(r'([A-Z]{3}\d{3})')
            
            avail_cols = [c for c in df_avail.columns if 'Availability' in c]
            df_avail[avail_cols] = df_avail[avail_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Availability'] = df_avail[avail_cols].bfill(axis=1).iloc[:, 0].fillna(1.0)
            
            loss_cols = [c for c in df_avail.columns if 'Loss' in c]
            df_avail[loss_cols] = df_avail[loss_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Packet_Loss'] = df_avail[loss_cols].bfill(axis=1).iloc[:, 0].fillna(0.0)

            df_merged = pd.merge(
                df_rev, 
                df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']].drop_duplicates(subset=['Site_ID', 'Date']), 
                on=['Site_ID', 'Date'], 
                how='left'
            )
            
        st.success("✅ Data berhasil digabungkan!")
        
        st.divider()
        st.write("### ⚙️ Filter Analisis")
        
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            all_sites = sorted(df_merged['Site_ID'].dropna().unique().tolist())
            dropdown_options = ["-- Pilih Site --"] + [f"{site} - {name_mapping.get(site, 'Unknown')}" for site in all_sites]
            search_site_selection = st.selectbox("🔍 Cari & Pilih Site ID:", options=dropdown_options)
            
        with col_f2:
            min_date = df_merged['Date'].min()
            max_date = df_merged['Date'].max()
            selected_dates = st.date_input(
                "📅 Pilih Periode Tanggal (Rentang):", 
                value=(min_date, max_date),
