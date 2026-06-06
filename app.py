import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
from sqlalchemy import text

st.set_page_config(page_title="Network Loss Impact Analyzer", layout="wide")

# --- INJEKSI KUSTOM CSS ---
st.markdown("""
<style>
    .stApp > header { background-color: transparent; border-top: 5px solid #EC2028; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 15px 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08); transition: transform 0.2s ease-in-out; }
    [data-testid="stMetric"]:hover { transform: translateY(-5px); }
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"] { border-left: 5px solid #28a745 !important; }
    [data-testid="column"]:nth-child(1) [data-testid="stMetricValue"] { color: #28a745 !important; }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"] { border-left: 5px solid #EC2028 !important; }
    [data-testid="column"]:nth-child(2) [data-testid="stMetricValue"] { color: #EC2028 !important; }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { border-left: 5px solid #0056b3 !important; }
    [data-testid="column"]:nth-child(3) [data-testid="stMetricValue"] { color: #0056b3 !important; }
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

st.write("Pantau Aktual, Potensi (Gain), dan *Lost* performa site secara real-time.")

# --- KONEKSI SISTEM (DISAMARKAN) ---
conn = st.connection("supabase", type="sql")
engine = conn.engine

# --- FUNGSI PEMBERSIH NAMA KOLOM ---
def clean_column_names(df):
    cols = df.columns.astype(str).str.lower()
    cols = cols.str.replace(' ', '_')
    cols = cols.str.replace(r'[^a-zA-Z0-9_]', '', regex=True)
    return cols

# --- 1. FITUR UPLOAD (UI GENERIK) ---
with st.expander("⚙️ Update Data Master"):
    st.info("Silakan upload file data terbaru di sini untuk memperbarui sistem.")
    
    col_up1, col_up2, col_up3 = st.columns(3)
    with col_up1:
        file_rev = st.file_uploader("📂 1. Data Revenue", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    with col_up2:
        file_avail = st.file_uploader("📂 2. Data Availability", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    with col_up3:
        file_dapot = st.file_uploader("📂 3. Data Dapot Master", type=["csv", "xlsx", "xls"])
    
    if st.button("💾 Simpan Data", type="primary"):
        with st.spinner("Memproses dan menyimpan data..."):
            try:
                # PROSES REVENUE
                if len(file_rev) > 0:
                    dfs_rev = [pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f) for f in file_rev]
                    df_rev_upload = pd.concat(dfs_rev, ignore_index=True)
                    df_rev_upload.columns = clean_column_names(df_rev_upload)
                    with engine.connect() as con:
                        try:
                            con.execute(text("TRUNCATE TABLE revenue_data;"))
                            con.commit()
                        except: pass
                    df_rev_upload.to_sql('revenue_data', engine, if_exists='append', index=False)
                
                # PROSES AVAILABILITY
                if len(file_avail) > 0:
                    dfs_avail = []
                    for f in file_avail:
                        if f.name.endswith('.csv'):
                            df_temp = pd.read_csv(f)
                        else:
                            xls_avail = pd.ExcelFile(f)
                            sheet_target = xls_avail.sheet_names[0] 
                            for sheet in xls_avail.sheet_names:
                                df_cek = pd.read_excel(xls_avail, sheet_name=sheet, nrows=1)
                                if any('Begin Time' in col or 'begin' in str(col).lower() for col in df_cek.columns):
                                    sheet_target = sheet
                                    break
                            df_temp = pd.read_excel(xls_avail, sheet_name=sheet_target)
                        dfs_avail.append(df_temp)
                    df_avail_upload = pd.concat(dfs_avail, ignore_index=True)
                    df_avail_upload.columns = clean_column_names(df_avail_upload)
                    with engine.connect() as con:
                        try:
                            con.execute(text("TRUNCATE TABLE availability_data;"))
                            con.commit()
                        except: pass
                    df_avail_upload.to_sql('availability_data', engine, if_exists='append', index=False)

                # PROSES DAPOT
                if file_dapot is not None:
                    df_dapot_upload = pd.read_csv(file_dapot) if file_dapot.name.endswith('.csv') else pd.read_excel(file_dapot, engine="openpyxl")
                    df_dapot_upload.columns = clean_column_names(df_dapot_upload)
                    with engine.connect() as con:
                        try:
                            con.execute(text("TRUNCATE TABLE dapot_data;"))
                            con.commit()
                        except: pass
                    df_dapot_upload.to_sql('dapot_data', engine, if_exists='append', index=False)
                
                st.success("✅ Data berhasil diperbarui!")
                st.cache_data.clear() 
                st.rerun() 
            except Exception as e:
                st.error("Gagal memproses data. Pastikan format file sudah benar.")

st.divider()

# --- 2. LOAD MAPPING SITE DAPOT ---
@st.cache_data(ttl="1h")
def load_dapot():
    try:
        df_dapot = conn.query("SELECT * FROM dapot_data;", ttl="1h")
        if 'site_id' in df_dapot.columns:
            df_dapot['site_id'] = df_dapot['site_id'].astype(str).str.strip().str.upper()
        return df_dapot
    except Exception as e:
        return pd.DataFrame()

df_dapot = load_dapot()

if not df_dapot.empty:
    col_anakan = [c for c in df_dapot.columns if 'anakan' in c.lower()][0] if any('anakan' in c.lower() for c in df_dapot.columns) else None
    site_mapping = dict(zip(df_dapot['site_id'], df_dapot[col_anakan].astype(str))) if col_anakan else {}
    col_name = [c for c in df_dapot.columns if 'name' in c.lower()][0] if any('name' in c.lower() for c in df_dapot.columns) else 'site_id'
    name_mapping = dict(zip(df_dapot['site_id'], df_dapot[col_name].astype(str)))
else:
    site_mapping = {}
    name_mapping = {}

# --- 3. AUTO-LOAD DATA SISTEM ---
try:
    with st.spinner("Memuat data sistem..."):
        df_rev = conn.query("SELECT * FROM revenue_data", ttl="10m")
        df_avail = conn.query("SELECT * FROM availability_data", ttl="10m")
        
        if df_rev.empty or df_avail.empty:
            st.warning("Data sistem masih kosong. Gunakan menu 'Update Data Master' di atas untuk inisiasi awal.")
            st.stop()
            
        # 🛠️ DEBUG MODE: Buka expander ini di web buat ngecek raw data lo!
        with st.expander("🛠️ DEBUG: Cek Data Mentah Database"):
            st.write("Tabel Revenue Asli:", df_rev.head())
            st.write("Tabel Availability Asli:", df_avail.head())
            
        # --- PERBAIKAN 1: PENCARIAN KOLOM TANGGAL LEBIH AKURAT ---
        date_cols_rev = [c for c in df_rev.columns if 'periode' in c.lower() or 'tanggal' in c.lower() or 'date' in c.lower()]
        date_col_rev = date_cols_rev[0] if date_cols_rev else df_rev.columns[0]
        # Pake errors='coerce' biar ga error kalau ada teks nyasar
        df_rev['Date'] = pd.to_datetime(df_rev[date_col_rev], errors='coerce').dt.date
        
        site_col_rev = [c for c in df_rev.columns if 'site' in c.lower()][0]
        df_rev['Site_ID'] = df_rev[site_col_rev].astype(str).str.strip().str.upper()
        
        rev_col = [c for c in df_rev.columns if 'revenue' in c.lower()][0]
        payload_col = [c for c in df_rev.columns if 'payload' in c.lower()][0]
        df_rev.rename(columns={rev_col: 'Actual_Revenue', payload_col: 'Actual_Payload'}, inplace=True)
        df_rev['Actual_Revenue'] = pd.to_numeric(df_rev['Actual_Revenue'], errors='coerce').fillna(0)
        df_rev['Actual_Payload'] = pd.to_numeric(df_rev['Actual_Payload'], errors='coerce').fillna(0) / 1024
        
        # Tanggal Availability
        time_cols_avail = [c for c in df_avail.columns if 'begin' in c.lower() or 'time' in c.lower() or 'date' in c.lower()]
        time_col_avail = time_cols_avail[0] if time_cols_avail else df_avail.columns[0]
        df_avail['Date'] = pd.to_datetime(df_avail[time_col_avail], errors='coerce').dt.date
        
        if 'managed_element' in df_avail.columns:
            df_avail['Site_ID'] = df_avail['managed_element'].astype(str).str.extract(r'([A-Z]{3}\d{3})')
        else:
            site_col_avail_list = [c for c in df_avail.columns if ('element' in c.lower() or 'site' in c.lower()) and 'id' not in c.lower()]
            site_col_avail = site_col_avail_list[0] if site_col_avail_list else df_avail.columns[0]
            df_avail['Site_ID'] = df_avail[site_col_avail].astype(str).str.extract(r'([A-Z]{3}\d{3})')
        
        avail_cols = [c for c in df_avail.columns if 'availability' in c.lower() or 'avail' in c.lower()]
        if avail_cols:
            df_avail[avail_cols] = df_avail[avail_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Availability'] = df_avail[avail_cols].bfill(axis=1).iloc[:, 0].fillna(1.0)
        
        loss_cols = [c for c in df_avail.columns if 'loss' in c.lower()]
        if loss_cols:
            df_avail[loss_cols] = df_avail[loss_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Packet_Loss'] = df_avail[loss_cols].bfill(axis=1).iloc[:, 0].fillna(0.0)

        df_rev = df_rev.drop_duplicates(subset=['Site_ID', 'Date'])
        df_avail = df_avail.drop_duplicates(subset=['Site_ID', 'Date'])

        # --- PERBAIKAN 2: PAKE OUTER JOIN! ---
        # Ini biar kalau salah satu data bolong di bulan tertentu, bulan itu tetep nongol
        df_merged = pd.merge(df_rev, df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']], on=['Site_ID', 'Date'], how='outer')
        
        df_merged['Actual_Revenue'] = df_merged['Actual_Revenue'].fillna(0)
        df_merged['Actual_Payload'] = df_merged['Actual_Payload'].fillna(0)
        df_merged['Availability'] = df_merged['Availability'].fillna(1.0)
        df_merged['Packet_Loss'] = df_merged['Packet_Loss'].fillna(0.0)
        
        # Buang yang tanggalnya gak jelas/error
        df_merged = df_merged.dropna(subset=['Date'])

        # Filter Dapot tetap jalan biar site Kalimantan aja yang masuk
        if not df_dapot.empty:
            df_merged = df_merged[df_merged['Site_ID'].isin(df_dapot['site_id'])]
except Exception as e:
    st.error("Gagal memuat data sistem.")
    st.stop()

# --- 4. LOGIC KALKULASI & UI DASHBOARD ---
def calculate_loss(df, parent_sites, mapping):
    all_related_sites = set()
    for site_id in parent_sites:
        child_sites_str = mapping.get(site_id, '')
        child_list = [] if pd.isna(child_sites_str) or child_sites_str == 'nan' or child_sites_str == '' else [x.strip().upper() for x in str(child_sites_str).split(',')]
        all_related_sites.add(site_id)
        all_related_sites.update(child_list)
    
    filtered_df = df[df['Site_ID'].isin(all_related_sites)].copy()
    if filtered_df.empty: return pd.DataFrame()
        
    def calc_potential(row, col_name):
        avail, pl, actual = row['Availability'], row['Packet_Loss'], row[col_name]
        return actual / (avail * (1 - pl)) if avail > 0 and pl < 1 else actual
    
    filtered_df['Potential_Revenue'] = filtered_df.apply(lambda r: calc_potential(r, 'Actual_Revenue'), axis=1)
    filtered_df['Potential_Payload'] = filtered_df.apply(lambda r: calc_potential(r, 'Actual_Payload'), axis=1)
    filtered_df['Lost_Revenue'] = -1 * (filtered_df['Potential_Revenue'] - filtered_df['Actual_Revenue'])
    filtered_df['Lost_Payload'] = -1 * (filtered_df['Potential_Payload'] - filtered_df['Actual_Payload'])
    filtered_df['Availability_Pct'] = filtered_df['Availability'] * 100
    filtered_df['Packet_Loss_Pct'] = filtered_df['Packet_Loss'] * 100
    filtered_df['Keterangan'] = filtered_df['Site_ID'].apply(lambda x: 'Induk (Parent)' if x in parent_sites else 'Anakan (Child)')
    
    return filtered_df

st.write("### ⚙️ Filter Analisis Site (Kalimantan)")
col_f1, col_f2 = st.columns(2)

with col_f1:
    all_sites = sorted(df_merged['Site_ID'].dropna().unique().tolist())
    dropdown_options = [f"{site} - {name_mapping.get(site, 'Unknown')}" for site in all_sites]
    search_sites_selection = st.multiselect("🔍 Cari & Pilih Site Induk (Bisa lebih dari 1):", options=dropdown_options)
    
with col_f2:
    min_date = df_merged['Date'].min()
    max_date = df_merged['Date'].max()
    selected_dates = st.date_input("📅 Pilih Periode Tanggal (Rentang):", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if search_sites_selection:
    selected_parents = [s.split(" - ")[0] for s in search_sites_selection]
    start_date, end_date = selected_dates if len(selected_dates) == 2 else (selected_dates[0], selected_dates[0])
    df_periode = df_merged[(df_merged['Date'] >= start_date) & (df_merged['Date'] <= end_date)]
    impact_df = calculate_loss(df_periode, selected_parents, site_mapping)
    
    if impact_df.empty:
        st.warning("⚠️ Data untuk Site yang dipilih tidak ditemukan di rentang tanggal tersebut.")
    else:
        if not df_dapot.empty:
            dapot_cols = ['site_id', 'site_name', 'site_class', 'kotakab', 'kecamatan', 'pln__non_pln', 'power_classification', 'power_type', 'site_simpul', 'grid_category_new', 'hub_site']
            dapot_cols = [c for c in dapot_cols if c in df_dapot.columns]
            impact_df = pd.merge(impact_df, df_dapot[dapot_cols], left_on='Site_ID', right_on='site_id', how='left')
        
        st.write("---")
        list_site_terlibat = sorted(impact_df['Site_ID'].unique().tolist())
        opsi_fokus = [f"{s} - {name_mapping.get(s, 'Unknown')}" for s in list_site_terlibat]
        
        fokus_site_selection = st.multiselect("🎯 Pilih Spesifik Site (Induk/Anakan) yang Ingin Dianalisis:", options=opsi_fokus, default=opsi_fokus)
        
        if not fokus_site_selection:
            st.info("⚠️ Silakan pilih minimal satu site dari kotak di atas.")
        else:
            site_fokus_ids = [s.split(" - ")[0] for s in fokus_site_selection]
            impact_df = impact_df[impact_df['Site_ID'].isin(site_fokus_ids)]
            
            st.write(f"### 📈 Ringkasan Performa ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
            
            tot_act_rev, tot_pot_rev, tot_lost_rev = impact_df['Actual_Revenue'].sum(), impact_df['Potential_Revenue'].sum(), impact_df['Lost_Revenue'].sum()
            tot_act_pay, tot_pot_pay, tot_lost_pay = impact_df['Actual_Payload'].sum(), impact_df['Potential_Payload'].sum(), impact_df['Lost_Payload'].sum()
            
            pct_gain_rev = ((tot_pot_rev - tot_act_rev) / tot_act_rev * 100) if tot_act_rev > 0 else 0
            pct_lost_rev = (tot_lost_rev / tot_pot_rev * 100) if tot_pot_rev > 0 else 0
            pct_gain_pay = ((tot_pot_pay - tot_act_pay) / tot_act_pay * 100) if tot_act_pay > 0 else 0
            pct_lost_pay = (tot_lost_pay / tot_pot_pay * 100) if tot_pot_pay > 0 else 0
            
            gain_rev_str, gain_rev_col = (f"+{pct_gain_rev:,.2f}% Kenaikan", "normal") if pct_gain_rev > 0 else ("0% Kenaikan", "off")
            loss_rev_str, loss_rev_col = (f"{pct_lost_rev:,.2f}% Loss", "normal") if pct_lost_rev < 0 else ("0% Loss", "off")
            gain_pay_str, gain_pay_col = (f"+{pct_gain_pay:,.2f}% Kenaikan", "normal") if pct_gain_pay > 0 else ("0% Kenaikan", "off")
            loss_pay_str, loss_pay_col = (f"{pct_lost_pay:,.2f}% Loss", "normal") if pct_lost_pay < 0 else ("0% Loss", "off")
            
            st.write("##### 💰 Analisis Revenue")
            c1, c2, c3 = st.columns(3)
            c1.metric("🌟 Potensi Gain (100% Ok)", f"Rp {tot_pot_rev:,.0f}", gain_rev_str, delta_color=gain_rev_col)
            c2.metric("📉 Lost Revenue", f"Rp {tot_lost_rev:,.0f}", loss_rev_str, delta_color=loss_rev_col)
            c3.metric("Pendapatan Aktual", f"Rp {tot_act_rev:,.0f}")
            
            st.write("##### 📦 Analisis Payload")
            c4, c5, c6 = st.columns(3)
            c4.metric("🚀 Potensi Traffic (100% Ok)", f"{tot_pot_pay:,.0f} GB", gain_pay_str, delta_color=gain_pay_col)
            c5.metric("📉 Lost Payload", f"{tot_lost_pay:,.0f} GB", loss_pay_str, delta_color=loss_pay_col)
            c6.metric("Traffic Aktual", f"{tot_act_pay:,.0f} GB")
            
            st.divider()
            st.write("### 📊 Trend Grafik Harian")
            
            trend_df = impact_df.groupby(['Date', 'Site_ID']).agg({
                'Actual_Revenue': 'sum', 'Potential_Revenue': 'sum', 'Lost_Revenue': 'sum',
                'Actual_Payload': 'sum', 'Potential_Payload': 'sum', 'Lost_Payload': 'sum',
                'Availability_Pct': 'mean', 'Packet_Loss_Pct': 'mean'
            }).reset_index()
            
            trend_df['Pct_Gain_Rev'] = trend_df.apply(lambda r: ((r['Potential_Revenue'] - r['Actual_Revenue']) / r['Actual_Revenue'] * 100) if r['Actual_Revenue'] > 0 else 0, axis=1)
            trend_df['Pct_Loss_Rev'] = trend_df.apply(lambda r: (r['Lost_Revenue'] / r['Potential_Revenue'] * 100) if r['Potential_Revenue'] > 0 else 0, axis=1)
            trend_df['Pct_Gain_Pay'] = trend_df.apply(lambda r: ((r['Potential_Payload'] - r['Actual_Payload']) / r['Actual_Payload'] * 100) if r['Actual_Payload'] > 0 else 0, axis=1)
            trend_df['Pct_Loss_Pay'] = trend_df.apply(lambda r: (r['Lost_Payload'] / r['Potential_Payload'] * 100) if r['Potential_Payload'] > 0 else 0, axis=1)
            trend_df['Date_Str'] = trend_df['Date'].astype(str)
            
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Gain Rev (Potensi)", "Lost Rev", "Gain Payload (Potensi)", "Lost Payload", "Availability", "Packet Loss"])
            
            def buat_grafik(df, x_col, y_col, tipe):
                if tipe == 'rev':
                    fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline', custom_data=['Potential_Revenue', 'Lost_Revenue', 'Actual_Revenue', 'Availability_Pct', 'Packet_Loss_Pct', 'Pct_Gain_Rev', 'Pct_Loss_Rev'])
                    template = "<b>%{x}</b><br><br>📡 Availability: %{customdata[3]:.2f}%<br>⚠️ Packet Loss: %{customdata[4]:.2f}%<br><br>🌟 Potensi Gain: Rp %{customdata[0]:,.0f} (+%{customdata[5]:.2f}%)<br>📉 Loss: Rp %{customdata[1]:,.0f} (%{customdata[6]:.2f}%)<br>💰 Aktual: Rp %{customdata[2]:,.0f}<extra></extra>"
                elif tipe == 'pay':
                    fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline', custom_data=['Potential_Payload', 'Lost_Payload', 'Actual_Payload', 'Availability_Pct', 'Packet_Loss_Pct', 'Pct_Gain_Pay', 'Pct_Loss_Pay'])
                    template = "<b>%{x}</b><br><br>📡 Availability: %{customdata[3]:.2f}%<br>⚠️ Packet Loss: %{customdata[4]:.2f}%<br><br>🚀 Potensi Gain: %{customdata[0]:,.0f} GB (+%{customdata[5]:.2f}%)<br>📉 Loss: %{customdata[1]:,.0f} GB (%{customdata[6]:.2f}%)<br>📦 Aktual: %{customdata[2]:,.0f} GB<extra></extra>"
                else:
                    fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline')
                    template = "<b>%{x}</b><br>Nilai: %{y:.2f}%<extra></extra>"
                
                fig.update_traces(hovertemplate=template, line=dict(width=3), marker=dict(size=8))
                fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False, linecolor='lightgray'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
                return fig

            with tab1: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Potential_Revenue', 'rev'), use_container_width=True)
            with tab2: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Lost_Revenue', 'rev'), use_container_width=True)
            with tab3: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Potential_Payload', 'pay'), use_container_width=True)
            with tab4: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Lost_Payload', 'pay'), use_container_width=True)
            with tab5: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Availability_Pct', 'pct'), use_container_width=True)
            with tab6: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Packet_Loss_Pct', 'pct'), use_container_width=True)

            st.divider()
            st.write("### 🗄️ Detail Data Harian Aktual vs Potensi")
            
            base_cols = ['Date', 'Site_ID', 'SITE NAME', 'Keterangan', 'SITE CLASS', 'Availability', 'Packet_Loss', 'Potential_Revenue', 'Lost_Revenue', 'Actual_Revenue', 'Potential_Payload', 'Lost_Payload', 'Actual_Payload']
            extra_cols = ['kotakab', 'kecamatan', 'pln__non_pln', 'power_classification', 'power_type', 'site_simpul', 'grid_category_new', 'hub_site']
            base_cols = [c for c in base_cols if c in impact_df.columns]
            extra_cols = [c for c in extra_cols if c in impact_df.columns]
            
            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                display_cols = base_cols + extra_cols if st.toggle("🔍 Tampilkan Kolom Detail Ekstra (Expand)") else base_cols
            with col_t2:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    impact_df.drop(columns=['site_id'], errors='ignore').to_excel(writer, index=False, sheet_name='Data_Loss')
                st.download_button("📥 Download Full Data (Excel)", data=buffer.getvalue(), file_name="Data_Loss_Impact_Full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            def get_red_maroon_style(ratio):
                ratio = max(0, min(1, ratio)) 
                r, g, b = int(255 - 127 * ratio), int(153 - 153 * ratio), int(153 - 153 * ratio)
                txt_color = 'white' if ((0.299 * r + 0.587 * g + 0.114 * b) / 255) < 0.5 else 'black'
                return f'background-color: #{r:02x}{g:02x}{b:02x}; color: {txt_color}; font-weight: bold;'

            styled_df = impact_df[display_cols].sort_values(by=['Date', 'Site_ID']).style.format({
                'Availability': '{:.2%}', 'Packet_Loss': '{:.2%}', 'Potential_Revenue': 'Rp {:,.0f}', 'Lost_Revenue': 'Rp {:,.0f}',
                'Actual_Revenue': 'Rp {:,.0f}', 'Potential_Payload': '{:,.0f} GB', 'Lost_Payload': '{:,.0f} GB', 'Actual_Payload': '{:,.0f} GB'
            }).apply(lambda s: ['background-color: #d4edda; color: #155724; font-weight: bold;' if v >= 0.99 else get_red_maroon_style((v - 0.99) / (s.min() - 0.99) if s.min() < 0.99 else 0) if pd.notna(v) else '' for v in s], subset=['Availability']
            ).apply(lambda s: ['background-color: #d4edda; color: #155724; font-weight: bold;' if v < 0.001 else get_red_maroon_style((v - 0.001) / (s.max() - 0.001) if s.max() > 0.001 else 0) if pd.notna(v) else '' for v in s], subset=['Packet_Loss']
            ).apply(lambda s: ['background-color: #d4edda; color: #155724; font-weight: bold;' if v >= 0 else get_red_maroon_style((v - 0) / (s.min() - 0) if s.min() < 0 else 0) if pd.notna(v) else '' for v in s], subset=['Lost_Revenue', 'Lost_Payload'])
            
            st.dataframe(styled_df, use_container_width=True)

# --- FOOTER ---
st.markdown('<div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #eaeaea; color: #888888; font-size: 14px;">© 2026 | Created with ❤️ by Fauzi Ramdani - 97122</div>', unsafe_allow_html=True)
