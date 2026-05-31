import streamlit as st
import pandas as pd

st.set_page_config(page_title="Network Loss Impact", layout="wide")

st.title("💸 Network Loss Impact Dashboard")
st.write("Pantau *lost payload*, *revenue*, dan trend berdasarkan *availability* secara periodik.")

# --- 1. LOAD MAPPING SITE ANAKAN DARI FILE LOKAL (BACKGROUND) ---
@st.cache_data
def load_site_mapping():
    try:
        # Web otomatis baca file Dapot di folder yang sama tanpa perlu user upload
        df_dapot = pd.read_excel("Dapot site kalimantan.xlsx", engine="openpyxl")
        
        # Bikin kamus (dictionary): Site ID -> Site Id Anakan
        mapping = dict(zip(
            df_dapot['Site ID'].astype(str).str.strip().str.upper(), 
            df_dapot['Site Id Anakan'].astype(str)
        ))
        return mapping
    except Exception as e:
        st.warning("⚠️ File 'Dapot site kalimantan.xlsx' tidak ditemukan di folder lokal. Fitur Site Anakan dinonaktifkan.")
        return {}

site_mapping = load_site_mapping()

# --- 2. LOGIC KALKULASI ---
def calculate_loss(df, site_id, mapping):
    # Cari list anakan dari dictionary
    child_sites_str = mapping.get(site_id, '')
    if child_sites_str == 'nan' or child_sites_str == '':
        child_list = []
    else:
        child_list = [x.strip().upper() for x in str(child_sites_str).split(',')]
    
    # Gabungin parent & child, lalu filter datanya
    all_related_sites = list(set([site_id] + child_list))
    filtered_df = df[df['Site_ID'].isin(all_related_sites)].copy()
    
    if filtered_df.empty:
        return pd.DataFrame()
        
    filtered_df['Lost_Revenue'] = filtered_df.apply(
        lambda row: (row['Actual_Revenue'] / row['Availability']) - row['Actual_Revenue'] if row['Availability'] > 0 else row['Actual_Revenue'], axis=1
    )
    filtered_df['Lost_Payload'] = filtered_df.apply(
        lambda row: (row['Actual_Payload'] / row['Availability']) - row['Actual_Payload'] if row['Availability'] > 0 else row['Actual_Payload'], axis=1
    )
    filtered_df['Type'] = filtered_df['Site_ID'].apply(lambda x: 'Parent' if x == site_id else 'Child')
    
    return filtered_df

# --- 3. BIKIN UI STREAMLIT (UPLOAD REVENUE & AVAILABILITY) ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    file_rev = st.file_uploader("📂 1. Upload Data Revenue Harian", type=["csv", "xlsx", "xls"])
with col_up2:
    file_avail = st.file_uploader("📂 2. Upload Data Availability U2000", type=["csv", "xlsx", "xls"])

if file_rev is not None and file_avail is not None:
    try:
        with st.spinner("Mengekstrak dan menggabungkan data..."):
            
            # === LOAD REVENUE ===
            if file_rev.name.endswith('.csv'):
                df_rev = pd.read_csv(file_rev)
            else:
                df_rev = pd.read_excel(file_rev)
            df_rev.columns = df_rev.columns.str.strip() 
            
            # === LOAD AVAILABILITY DGN AUTO-DETECT SHEET ===
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
            
            # === PREPROCESSING ===
            # Ambil Date (hanya tanggal) biar rentangnya enak
            df_rev['Date'] = pd.to_datetime(df_rev['date'], format='mixed').dt.date
            df_rev['Site_ID'] = df_rev['site_id'].astype(str).str.upper()
            
            # Deteksi dinamis nama kolom revenue & payload
            rev_col = [c for c in df_rev.columns if 'revenue' in c.lower()][0]
            payload_col = [c for c in df_rev.columns if 'payload' in c.lower()][0]
            
            df_rev.rename(columns={rev_col: 'Actual_Revenue', payload_col: 'Actual_Payload'}, inplace=True)
            df_rev['Actual_Revenue'] = pd.to_numeric(df_rev['Actual_Revenue'], errors='coerce').fillna(0)
            df_rev['Actual_Payload'] = pd.to_numeric(df_rev['Actual_Payload'], errors='coerce').fillna(0)
            
            df_avail['Date'] = pd.to_datetime(df_avail['Begin Time'], format='mixed').dt.date
            df_avail['Site_ID'] = df_avail['Managed Element'].astype(str).str.extract(r'([A-Z]{3}\d{3})')
            
            avail_cols = [c for c in df_avail.columns if 'Availability' in c]
            df_avail[avail_cols] = df_avail[avail_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Availability'] = df_avail[avail_cols].bfill(axis=1).iloc[:, 0].fillna(1.0)
            
            loss_cols = [c for c in df_avail.columns if 'Loss' in c]
            df_avail[loss_cols] = df_avail[loss_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Packet_Loss'] = df_avail[loss_cols].bfill(axis=1).iloc[:, 0].fillna(0.0)

            # === MERGE ===
            df_merged = pd.merge(
                df_rev, 
                df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']].drop_duplicates(subset=['Site_ID', 'Date']), 
                on=['Site_ID', 'Date'], 
                how='left'
            )
            
        st.success("✅ Data berhasil digabungkan!")
        
        # --- 4. TAMPILAN DASHBOARD (SEARCH DROP-DOWN & DATE RANGE) ---
        st.divider()
        st.write("### ⚙️ Filter Analisis")
        
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            # Dropdown Search untuk Site ID
            all_sites = sorted(df_merged['Site_ID'].dropna().unique().tolist())
            search_site = st.selectbox("🔍 Cari & Pilih Site ID:", options=["-- Pilih Site --"] + all_sites)
            
        with col_f2:
            # Pilihan Rentang Tanggal (Date Range)
            min_date = df_merged['Date'].min()
            max_date = df_merged['Date'].max()
            
            selected_dates = st.date_input(
                "📅 Pilih Periode Tanggal (Rentang):", 
                value=(min_date, max_date), 
                min_value=min_date, 
                max_value=max_date
            )

        # Proses Analisis berjalan jika rentang tanggal udah dipilih & Site udah di-select
        if search_site != "-- Pilih Site --":
            # Streamlit date_input ngeluarin tuple 1 (jika baru klik start) atau 2 (start & end)
            if len(selected_dates) == 2:
                start_date, end_date = selected_dates
            else:
                start_date = end_date = selected_dates[0]
                
            # Filter Data by Date
            df_periode = df_merged[(df_merged['Date'] >= start_date) & (df_merged['Date'] <= end_date)]
            
            # Hitung Loss & Ambil Site Anakannya
            impact_df = calculate_loss(df_periode, search_site, site_mapping)
            
            if impact_df.empty:
                st.warning(f"Wah, Data untuk Site {search_site} gak ketemu di rentang tanggal tersebut, Zi.")
            else:
                st.write(f"### 📈 Hasil Analisis: {search_site} & Site Anakannya ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
                
                # TOTAL METRICS DARI PERIODE TERSEBUT
                total_lost_rev = impact_df['Lost_Revenue'].sum()
                total_lost_payload = impact_df['Lost_Payload'].sum()
                
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("📉 Total Lost Revenue (IDR)", f"Rp {total_lost_rev:,.0f}")
                col_m2.metric("📦 Total Lost Payload", f"{(total_lost_payload / 1024):,.2f} GB")
                
                st.divider()
                
                # --- 5. GRAFIK TREND (TIME SERIES) ---
                st.write("### 📊 Trend Grafik Harian")
                
                # Mengelompokkan data berdasarkan Tanggal & Site
                trend_df = impact_df.groupby(['Date', 'Site_ID']).agg({
                    'Lost_Revenue': 'sum',
                    'Lost_Payload': 'sum',
                    'Availability': 'mean', # Availability & Loss pakai Mean biar logis
                    'Packet_Loss': 'mean'
                }).reset_index()
                
                trend_df['Date_Str'] = trend_df['Date'].astype(str)
                
                # Bikin Tab untuk tiap jenis Grafik
                tab1, tab2, tab3, tab4 = st.tabs(["Lost Revenue", "Lost Payload", "Availability", "Packet Loss"])
                
                def plot_trend(tab, y_col, title):
                    with tab:
                        # Bikin Pivot Table supaya tiap Site punya garis grafiknya sendiri-sendiri
                        pivot_df = trend_df.pivot(index='Date_Str', columns='Site_ID', values=y_col)
                        st.line_chart(pivot_df)

                plot_trend(tab1, 'Lost_Revenue', 'Lost Revenue (IDR)')
                plot_trend(tab2, 'Lost_Payload', 'Lost Payload (MB)')
                plot_trend(tab3, 'Availability', 'Availability (%)')
                plot_trend(tab4, 'Packet_Loss', 'Packet Loss (%)')

                st.divider()
                
                # --- 6. TABEL RAW DATA ---
                st.write("### 🗄️ Detail Data Harian")
                display_cols = ['Date', 'Site_ID', 'Type', 'Availability', 'Packet_Loss', 'Actual_Revenue', 'Lost_Revenue', 'Lost_Payload']
                st.dataframe(impact_df[display_cols].sort_values(by=['Date', 'Site_ID']).style.format({
                    'Availability': '{:.2%}',
                    'Packet_Loss': '{:.2%}',
                    'Actual_Revenue': 'Rp {:,.0f}',
                    'Lost_Revenue': 'Rp {:,.0f}',
                    'Lost_Payload': '{:,.2f} MB'
                }), use_container_width=True)

    except Exception as e:
        st.error(f"Gagal memproses file. Pastikan format kolom sama. Error: {e}")
