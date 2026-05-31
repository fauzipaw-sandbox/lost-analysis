import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="Network Loss Impact", layout="wide")

# --- INJEKSI KUSTOM CSS ---
st.markdown("""
<style>
    .stApp > header {
        background-color: transparent;
        border-top: 5px solid #EC2028;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease-in-out;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
    }
    
    /* KOLOM 1: AKTUAL (BIRU) */
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"],
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] {
        border-left: 5px solid #0056b3 !important;
    }
    [data-testid="column"]:nth-child(1) [data-testid="stMetricValue"],
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetricValue"] {
        color: #0056b3 !important;
    }
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"]:hover,
    [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"]:hover {
        box-shadow: 0 6px 15px rgba(0, 86, 179, 0.2) !important;
    }
    
    /* KOLOM 2: POTENSI GAIN (HIJAU) */
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"],
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {
        border-left: 5px solid #28a745 !important;
    }
    [data-testid="column"]:nth-child(2) [data-testid="stMetricValue"],
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetricValue"] {
        color: #28a745 !important;
    }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"]:hover,
    [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"]:hover {
        box-shadow: 0 6px 15px rgba(40, 167, 69, 0.2) !important;
    }
    
    /* KOLOM 3: LOST (MERAH) */
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"],
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {
        border-left: 5px solid #EC2028 !important;
    }
    [data-testid="column"]:nth-child(3) [data-testid="stMetricValue"],
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetricValue"] {
        color: #EC2028 !important;
    }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"]:hover,
    [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"]:hover {
        box-shadow: 0 6px 15px rgba(236, 32, 40, 0.2) !important;
    }
    
    [data-testid="stFileUploadDropzone"] {
        border: 2px dashed #EC2028;
        border-radius: 10px;
        background-color: #FCF4F4;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER DENGAN LOGO TELKOMSEL ---
col_logo, col_title = st.columns([1, 15])
with col_logo:
    # Menggunakan logo Telkomsel resmi dari link public
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Telkomsel_2021_icon.svg/512px-Telkomsel_2021_icon.svg.png", width=60)
with col_title:
    st.markdown("<h1 style='margin-top: -15px;'>💸📉 Network Loss Impact Analyzer</h1>", unsafe_allow_html=True)


st.write("Pantau Aktual, Potensi (Gain), dan *Lost* performa site berdasarkan Availability Network.")
st.markdown("""
<div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 20px; border-left: 3px solid #0056b3;'>
    ℹ️ <b>Sumber Data:</b><br>
    Untuk data "Revenue & Payload" ambil disini: <a href="MASUKIN_LINK_URL_NDM_ASLINYA_DISINI" target="_blank">Payload Traffic Revenue NDM</a> <br>
    Untuk data "Availability & Packet loss" ambil disini: <a href="MASUKIN_LINK_URL_UME_ASLINYA_DISINI" target="_blank">Payload Traffic Revenue UME</a>
</div>
""", unsafe_allow_html=True)

# --- 1. LOAD MAPPING SITE & FILTER NOP PALANGKARAYA ---
@st.cache_data
def load_dapot():
    try:
        df_dapot = pd.read_excel("Dapot site kalimantan.xlsx", engine="openpyxl")
        # FILTER: Cuma ambil yang DEPARTEMEN-nya NOP PALANGKARAYA biar enteng!
        df_dapot = df_dapot[df_dapot['DEPARTEMEN'].astype(str).str.contains('NOP PALANGKARAYA', case=False, na=False)]
        df_dapot['Site ID'] = df_dapot['Site ID'].astype(str).str.strip().str.upper()
        return df_dapot
    except Exception as e:
        st.warning("⚠️ File 'Dapot site kalimantan.xlsx' tidak ditemukan. Fitur nama site dinonaktifkan.")
        return pd.DataFrame()

df_dapot = load_dapot()
if not df_dapot.empty:
    site_mapping = dict(zip(df_dapot['Site ID'], df_dapot['Site Id Anakan'].astype(str)))
    name_mapping = dict(zip(df_dapot['Site ID'], df_dapot['SITE NAME'].astype(str)))
else:
    site_mapping = {}
    name_mapping = {}

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
    
    filtered_df['Keterangan'] = filtered_df['Site_ID'].apply(lambda x: 'Induk (Parent)' if x == site_id else 'Anakan (Child)')
    
    return filtered_df

# --- 3. BIKIN UI STREAMLIT MULTI UPLOAD ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    file_rev = st.file_uploader("📂 1. Upload Data Revenue (Bisa banyak file)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
with col_up2:
    file_avail = st.file_uploader("📂 2. Upload Data Availability (Bisa banyak file)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

if len(file_rev) > 0 and len(file_avail) > 0:
    try:
        with st.spinner("Mengekstrak dan menggabungkan data dari semua file..."):
            
            # BACA SEMUA FILE REVENUE
            dfs_rev = []
            for f in file_rev:
                if f.name.endswith('.csv'):
                    df_temp = pd.read_csv(f)
                else:
                    df_temp = pd.read_excel(f)
                df_temp.columns = df_temp.columns.str.strip()
                dfs_rev.append(df_temp)
            df_rev = pd.concat(dfs_rev, ignore_index=True)
            
            # BACA SEMUA FILE AVAILABILITY
            dfs_avail = []
            for f in file_avail:
                if f.name.endswith('.csv'):
                    df_temp = pd.read_csv(f)
                else:
                    xls_avail = pd.ExcelFile(f)
                    sheet_target = xls_avail.sheet_names[0] 
                    for sheet in xls_avail.sheet_names:
                        df_cek = pd.read_excel(xls_avail, sheet_name=sheet, nrows=1)
                        if any('Begin Time' in col for col in df_cek.columns):
                            sheet_target = sheet
                            break
                    df_temp = pd.read_excel(xls_avail, sheet_name=sheet_target)
                df_temp.columns = df_temp.columns.str.strip()
                dfs_avail.append(df_temp)
            df_avail = pd.concat(dfs_avail, ignore_index=True)
            
            # PREPROCESSING
            df_rev['Date'] = pd.to_datetime(df_rev['date'], format='mixed').dt.date
            df_rev['Site_ID'] = df_rev['site_id'].astype(str).str.strip().str.upper()
            
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

            df_rev = df_rev.drop_duplicates(subset=['Site_ID', 'Date'])
            df_avail = df_avail.drop_duplicates(subset=['Site_ID', 'Date'])

            df_merged = pd.merge(
                df_rev, 
                df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']], 
                on=['Site_ID', 'Date'], 
                how='left'
            )

            # EKSKLUSIF: Saring hanya site yang masuk NOP Palangkaraya (Sesuai Dapot)
            if not df_dapot.empty:
                df_merged = df_merged[df_merged['Site_ID'].isin(df_dapot['Site ID'])]
            
        st.success("✅ Data NOP Palangkaraya berhasil digabungkan!")
        
        st.divider()
        st.write("### ⚙️ Filter Analisis")
        
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            all_sites = sorted(df_merged['Site_ID'].dropna().unique().tolist())
            dropdown_options = ["-- Pilih Site --"] + [f"{site} - {name_mapping.get(site, 'Unknown')}" for site in all_sites]
            search_site_selection = st.selectbox("🔍 Cari & Pilih Site Induk:", options=dropdown_options)
            
        with col_f2:
            min_date = df_merged['Date'].min()
            max_date = df_merged['Date'].max()
            selected_dates = st.date_input(
                "📅 Pilih Periode Tanggal (Rentang):", 
                value=(min_date, max_date), 
                min_value=min_date, 
                max_value=max_date
            )

        if search_site_selection != "-- Pilih Site --":
            search_site = search_site_selection.split(" - ")[0]
            
            if len(selected_dates) == 2:
                start_date, end_date = selected_dates
            else:
                start_date = end_date = selected_dates[0]
                
            df_periode = df_merged[(df_merged['Date'] >= start_date) & (df_merged['Date'] <= end_date)]
            
            impact_df = calculate_loss(df_periode, search_site, site_mapping)
            
            if impact_df.empty:
                st.warning(f"Data untuk Site {search_site} gak ketemu di rentang tanggal tersebut.")
            else:
                if not df_dapot.empty:
                    dapot_cols = ['Site ID', 'SITE NAME', 'SITE CLASS', 'Kota/Kab', 'Kecamatan', 'PLN / NON PLN', 'POWER CLASSIFICATION', 'POWER TYPE', 'SITE SIMPUL', 'Grid Category New', 'Hub site']
                    dapot_cols = [c for c in dapot_cols if c in df_dapot.columns]
                    impact_df = pd.merge(impact_df, df_dapot[dapot_cols], left_on='Site_ID', right_on='Site ID', how='left')
                else:
                    impact_df['SITE NAME'] = 'Unknown'
                    impact_df['SITE CLASS'] = '-'

                st.write("---")
                
                list_site_terlibat = sorted(impact_df['Site_ID'].unique().tolist())
                opsi_fokus = [f"{s} - {name_mapping.get(s, 'Unknown')}" for s in list_site_terlibat]
                
                fokus_site_selection = st.multiselect(
                    "🎯 Pilih Spesifik Site (Bisa lebih dari satu):", 
                    options=opsi_fokus, 
                    default=opsi_fokus
                )
                
                if not fokus_site_selection:
                    st.info("⚠️ Silakan pilih minimal satu site dari kotak di atas untuk melihat hasilnya.")
                else:
                    site_fokus_ids = [s.split(" - ")[0] for s in fokus_site_selection]
                    impact_df = impact_df[impact_df['Site_ID'].isin(site_fokus_ids)]
                    
                    st.write(f"### 📈 Ringkasan Performa ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
                    
                    tot_act_rev = impact_df['Actual_Revenue'].sum()
                    tot_pot_rev = impact_df['Potential_Revenue'].sum()
                    tot_lost_rev = impact_df['Lost_Revenue'].sum()
                    
                    tot_act_pay = impact_df['Actual_Payload'].sum()
                    tot_pot_pay = impact_df['Potential_Payload'].sum()
                    tot_lost_pay = impact_df['Lost_Payload'].sum()
                    
                    pct_gain_rev = ((tot_pot_rev - tot_act_rev) / tot_act_rev * 100) if tot_act_rev > 0 else 0
                    pct_lost_rev = (tot_lost_rev / tot_pot_rev * 100) if tot_pot_rev > 0 else 0
                    
                    pct_gain_pay = ((tot_pot_pay - tot_act_pay) / tot_act_pay * 100) if tot_act_pay > 0 else 0
                    pct_lost_pay = (tot_lost_pay / tot_pot_pay * 100) if tot_pot_pay > 0 else 0
                    
                    gain_rev_str = f"+{pct_gain_rev:,.2f}% Kenaikan" if pct_gain_rev > 0 else "0% Kenaikan"
                    gain_rev_col = "normal" if pct_gain_rev > 0 else "off"
                    loss_rev_str = f"{pct_lost_rev:,.2f}% Loss" if pct_lost_rev < 0 else "0% Loss"
                    loss_rev_col = "normal" if pct_lost_rev < 0 else "off"

                    gain_pay_str = f"+{pct_gain_pay:,.2f}% Kenaikan" if pct_gain_pay > 0 else "0% Kenaikan"
                    gain_pay_col = "normal" if pct_gain_pay > 0 else "off"
                    loss_pay_str = f"{pct_lost_pay:,.2f}% Loss" if pct_lost_pay < 0 else "0% Loss"
                    loss_pay_col = "normal" if pct_lost_pay < 0 else "off"
                    
                    st.write("##### 💰 Analisis Revenue")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Pendapatan Aktual", f"Rp {tot_act_rev:,.0f}")
                    c2.metric("🌟 Potensi Gain (100% Ok)", f"Rp {tot_pot_rev:,.0f}", gain_rev_str, delta_color=gain_rev_col)
                    c3.metric("📉 Lost Revenue", f"Rp {tot_lost_rev:,.0f}", loss_rev_str, delta_color=loss_rev_col)
                    
                    st.write("##### 📦 Analisis Payload")
                    c4, c5, c6 = st.columns(3)
                    c4.metric("Traffic Aktual", f"{tot_act_pay:,.0f} GB")
                    c5.metric("🚀 Potensi Traffic (100% Ok)", f"{tot_pot_pay:,.0f} GB", gain_pay_str, delta_color=gain_pay_col)
                    c6.metric("📉 Lost Payload", f"{tot_lost_pay:,.0f} GB", loss_pay_str, delta_color=loss_pay_col)
                    
                    st.divider()
                    
                    st.write("### 📊 Trend Grafik Harian")
                    
                    trend_df = impact_df.groupby(['Date', 'Site_ID']).agg({
                        'Actual_Revenue': 'sum',
                        'Potential_Revenue': 'sum',
                        'Lost_Revenue': 'sum',
                        'Actual_Payload': 'sum',
                        'Potential_Payload': 'sum',
                        'Lost_Payload': 'sum',
                        'Availability_Pct': 'mean',
                        'Packet_Loss_Pct': 'mean'
                    }).reset_index()
                    
                    # HITUNG PERSENTASE GAIN & LOSS UNTUK TOOLTIP GRAFIK
                    trend_df['Pct_Gain_Rev'] = trend_df.apply(lambda r: ((r['Potential_Revenue'] - r['Actual_Revenue']) / r['Actual_Revenue'] * 100) if r['Actual_Revenue'] > 0 else 0, axis=1)
                    trend_df['Pct_Loss_Rev'] = trend_df.apply(lambda r: (r['Lost_Revenue'] / r['Potential_Revenue'] * 100) if r['Potential_Revenue'] > 0 else 0, axis=1)
                    
                    trend_df['Pct_Gain_Pay'] = trend_df.apply(lambda r: ((r['Potential_Payload'] - r['Actual_Payload']) / r['Actual_Payload'] * 100) if r['Actual_Payload'] > 0 else 0, axis=1)
                    trend_df['Pct_Loss_Pay'] = trend_df.apply(lambda r: (r['Lost_Payload'] / r['Potential_Payload'] * 100) if r['Potential_Payload'] > 0 else 0, axis=1)
                    
                    trend_df['Date_Str'] = trend_df['Date'].astype(str)
                    
                    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                        "Gain Rev (Potensi)", "Lost Rev", 
                        "Gain Payload (Potensi)", "Lost Payload", 
                        "Availability", "Packet Loss"
                    ])
                    
                    # --- TOOLTIP GRAFIK KOMPLIT (Avail, PL, %, Potensi, Loss, Aktual) ---
                    def buat_grafik_rev(df, x_col, y_col):
                        fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline',
                                      custom_data=['Potential_Revenue', 'Lost_Revenue', 'Actual_Revenue', 'Availability_Pct', 'Packet_Loss_Pct', 'Pct_Gain_Rev', 'Pct_Loss_Rev'])
                        fig.update_traces(
                            hovertemplate="<b>%{x}</b><br><br>" +
                                          "📡 Availability: %{customdata[3]:.2f}%<br>" +
                                          "⚠️ Packet Loss: %{customdata[4]:.2f}%<br><br>" +
                                          "🌟 Potensi Gain: Rp %{customdata[0]:,.0f} (+%{customdata[5]:.2f}%)<br>" +
                                          "📉 Loss: Rp %{customdata[1]:,.0f} (%{customdata[6]:.2f}%)<br>" +
                                          "💰 Aktual: Rp %{customdata[2]:,.0f}<extra></extra>",
                            line=dict(width=3), marker=dict(size=8)
                        )
                        fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False, linecolor='lightgray'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
                        return fig

                    def buat_grafik_pay(df, x_col, y_col):
                        fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline',
                                      custom_data=['Potential_Payload', 'Lost_Payload', 'Actual_Payload', 'Availability_Pct', 'Packet_Loss_Pct', 'Pct_Gain_Pay', 'Pct_Loss_Pay'])
                        fig.update_traces(
                            hovertemplate="<b>%{x}</b><br><br>" +
                                          "📡 Availability: %{customdata[3]:.2f}%<br>" +
                                          "⚠️ Packet Loss: %{customdata[4]:.2f}%<br><br>" +
                                          "🚀 Potensi Gain: %{customdata[0]:,.0f} GB (+%{customdata[5]:.2f}%)<br>" +
                                          "📉 Loss: %{customdata[1]:,.0f} GB (%{customdata[6]:.2f}%)<br>" +
                                          "📦 Aktual: %{customdata[2]:,.0f} GB<extra></extra>",
                            line=dict(width=3), marker=dict(size=8)
                        )
                        fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False, linecolor='lightgray'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
                        return fig

                    def buat_grafik_pct(df, x_col, y_col):
                        fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline')
                        fig.update_traces(
                            hovertemplate="<b>%{x}</b><br>Nilai: %{y:.2f}%<extra></extra>",
                            line=dict(width=3), marker=dict(size=8)
                        )
                        fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False, linecolor='lightgray'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
                        return fig

                    with tab1:
                        st.plotly_chart(buat_grafik_rev(trend_df, 'Date_Str', 'Potential_Revenue'), use_container_width=True)
                    with tab2:
                        st.plotly_chart(buat_grafik_rev(trend_df, 'Date_Str', 'Lost_Revenue'), use_container_width=True)
                    with tab3:
                        st.plotly_chart(buat_grafik_pay(trend_df, 'Date_Str', 'Potential_Payload'), use_container_width=True)
                    with tab4:
                        st.plotly_chart(buat_grafik_pay(trend_df, 'Date_Str', 'Lost_Payload'), use_container_width=True)
                    with tab5:
                        st.plotly_chart(buat_grafik_pct(trend_df, 'Date_Str', 'Availability_Pct'), use_container_width=True)
                    with tab6:
                        st.plotly_chart(buat_grafik_pct(trend_df, 'Date_Str', 'Packet_Loss_Pct'), use_container_width=True)

                    st.divider()
                    
                    st.write("### 🗄️ Detail Data Harian Aktual vs Potensi")
                    
                    base_cols = [
                        'Date', 'Site_ID', 'SITE NAME', 'Keterangan', 'SITE CLASS', 
                        'Availability', 'Packet_Loss', 
                        'Actual_Revenue', 'Potential_Revenue', 'Lost_Revenue', 
                        'Actual_Payload', 'Potential_Payload', 'Lost_Payload'
                    ]
                    extra_cols = [
                        'Kota/Kab', 'Kecamatan', 'PLN / NON PLN', 'POWER CLASSIFICATION', 
                        'POWER TYPE', 'SITE SIMPUL', 'Grid Category New', 'Hub site'
                    ]
                    
                    base_cols = [c for c in base_cols if c in impact_df.columns]
                    extra_cols = [c for c in extra_cols if c in impact_df.columns]
                    
                    col_t1, col_t2 = st.columns([1, 1])
                    with col_t1:
                        tampilkan_detail = st.toggle("🔍 Tampilkan Kolom Detail Ekstra (Expand)")
                        display_cols = base_cols + extra_cols if tampilkan_detail else base_cols
                    
                    with col_t2:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            impact_df.drop(columns=['Site ID'], errors='ignore').to_excel(writer, index=False, sheet_name='Data_Loss')
                        
                        st.download_button(
                            label="📥 Download Full Data (Excel)",
                            data=buffer.getvalue(),
                            file_name="Data_Loss_Impact_Full.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    def get_red_maroon_style(ratio):
                        ratio = max(0, min(1, ratio)) 
                        r = int(255 - (255 - 128) * ratio)
                        g = int(153 - (153 - 0) * ratio)
                        b = int(153 - (153 - 0) * ratio)
                        bg_color = f'#{r:02x}{g:02x}{b:02x}'
                        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                        txt_color = 'white' if lum < 0.5 else 'black'
                        return f'background-color: {bg_color}; color: {txt_color}; font-weight: bold;'

                    def color_availability(s):
                        styles = []
                        min_val = s.min()
                        for val in s:
                            if pd.isna(val) or isinstance(val, str):
                                styles.append('')
                            elif val >= 0.99:
                                styles.append('background-color: #d4edda; color: #155724; font-weight: bold;')
                            else:
                                ratio = (val - 0.99) / (min_val - 0.99) if min_val < 0.99 else 0
                                styles.append(get_red_maroon_style(ratio))
                        return styles

                    def color_loss(s):
                        styles = []
                        min_val = s.min()
                        for val in s:
                            if pd.isna(val) or isinstance(val, str):
                                styles.append('')
                            elif val >= 0:
                                styles.append('background-color: #d4edda; color: #155724; font-weight: bold;')
                            else:
                                ratio = (val - 0) / (min_val - 0) if min_val < 0 else 0
                                styles.append(get_red_maroon_style(ratio))
                        return styles

                    def color_packet_loss(s):
                        styles = []
                        max_val = s.max()
                        for val in s:
                            if pd.isna(val) or isinstance(val, str):
                                styles.append('')
                            elif val <= 0.01:
                                styles.append('background-color: #d4edda; color: #155724; font-weight: bold;')
                            else:
                                ratio = (val - 0.01) / (max_val - 0.01) if max_val > 0.01 else 0
                                styles.append(get_red_maroon_style(ratio))
                        return styles
                    
                    styled_df = impact_df[display_cols].sort_values(by=['Date', 'Site_ID']).style.format({
                        'Availability': '{:.2%}',
                        'Packet_Loss': '{:.2%}',
                        'Actual_Revenue': 'Rp {:,.0f}',
                        'Potential_Revenue': 'Rp {:,.0f}',
                        'Lost_Revenue': 'Rp {:,.0f}',
                        'Actual_Payload': '{:,.0f} GB',
                        'Potential_Payload': '{:,.0f} GB',
                        'Lost_Payload': '{:,.0f} GB'
                    }).apply(
                        color_availability, subset=['Availability']
                    ).apply(
                        color_packet_loss, subset=['Packet_Loss']
                    ).apply(
                        color_loss, subset=['Lost_Revenue', 'Lost_Payload']
                    ).background_gradient(
                        cmap='Greens', subset=['Potential_Revenue', 'Potential_Payload']
                    )
                    
                    st.dataframe(styled_df, use_container_width=True)

    except Exception as e:
        st.error(f"Gagal memproses file. Pastikan format kolom sama. Error: {e}")

# --- FOOTER HAK CIPTA ---
st.markdown("""
<div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #eaeaea; color: #888888; font-size: 14px;">
    © 2026 | Created with ❤️ by Fauzi Ramdani - 97122
</div>
""", unsafe_allow_html=True)
