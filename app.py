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

st.write("Pantau Aktual, Potensi (Gain), dan *Lost* performa site secara real-time dari seluruh area.")

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
with st.expander("⚙️ Update Data Harian / Master"):
    st.info("Upload file data harian terbaru di sini. Data akan otomatis ditambahkan ke historis yang sudah ada.")
    
    col_up1, col_up2, col_up3 = st.columns(3)
    with col_up1:
        file_rev = st.file_uploader("📂 1. Data Revenue (Harian)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    with col_up2:
        file_avail = st.file_uploader("📂 2. Data Availability (Harian)", type=["csv", "xlsx", "xls"], accept_multiple_files=True)
    with col_up3:
        file_dapot = st.file_uploader("📂 3. Data Dapot Master", type=["csv", "xlsx", "xls"])
    
    if st.button("💾 Simpan Data", type="primary"):
        with st.spinner("Memproses dan menyimpan data... (Ini mungkin memakan waktu untuk data besar)"):
            try:
                if len(file_rev) > 0:
                    for f in file_rev:
                        df_temp = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
                        df_temp.columns = clean_column_names(df_temp)
                        df_temp.to_sql('revenue_data', engine, if_exists='append', index=False, chunksize=5000)
                
                if len(file_avail) > 0:
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
                        
                        df_temp.columns = clean_column_names(df_temp)
                        df_temp.to_sql('availability_data', engine, if_exists='append', index=False, chunksize=5000)

                if file_dapot is not None:
                    df_dapot_upload = pd.read_csv(file_dapot) if file_dapot.name.endswith('.csv') else pd.read_excel(file_dapot, engine="openpyxl")
                    df_dapot_upload.columns = clean_column_names(df_dapot_upload)
                    with engine.connect() as con:
                        try:
                            con.execute(text("TRUNCATE TABLE dapot_data;"))
                            con.commit()
                        except: pass
                    df_dapot_upload.to_sql('dapot_data', engine, if_exists='append', index=False, chunksize=5000)
                
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
            
        date_cols_rev = [c for c in df_rev.columns if 'periode' in c.lower() or 'tanggal' in c.lower() or 'date' in c.lower()]
        date_col_rev = date_cols_rev[0] if date_cols_rev else df_rev.columns[0]
        df_rev['Date'] = pd.to_datetime(df_rev[date_col_rev], errors='coerce').dt.date
        
        site_col_rev = [c for c in df_rev.columns if 'site' in c.lower()][0]
        df_rev['Site_ID'] = df_rev[site_col_rev].astype(str).str.strip().str.upper()
        
        rev_col = [c for c in df_rev.columns if 'revenue' in c.lower()][0]
        payload_col = [c for c in df_rev.columns if 'payload' in c.lower()][0]
        df_rev.rename(columns={rev_col: 'Actual_Revenue', payload_col: 'Actual_Payload'}, inplace=True)
        df_rev['Actual_Revenue'] = pd.to_numeric(df_rev['Actual_Revenue'], errors='coerce').fillna(0)
        df_rev['Actual_Payload'] = pd.to_numeric(df_rev['Actual_Payload'], errors='coerce').fillna(0) / 1024
        
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

        df_rev = df_rev.drop_duplicates(subset=['Site_ID', 'Date'], keep='last')
        df_avail = df_avail.drop_duplicates(subset=['Site_ID', 'Date'], keep='last')

        df_merged = pd.merge(df_rev, df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']], on=['Site_ID', 'Date'], how='outer')
        
        df_merged['Actual_Revenue'] = df_merged['Actual_Revenue'].fillna(0)
        df_merged['Actual_Payload'] = df_merged['Actual_Payload'].fillna(0)
        df_merged['Availability'] = df_merged['Availability'].fillna(1.0)
        df_merged['Packet_Loss'] = df_merged['Packet_Loss'].fillna(0.0)
        
        df_merged = df_merged.dropna(subset=['Date'])

        # --- GABUNGKAN DATA DAPOT UTAMA (KAB, KEC) ---
        if not df_dapot.empty:
            dapot_cols = ['site_id', 'site_name', 'kotakab', 'kecamatan', 'site_class', 'pln__non_pln', 'power_classification', 'site_simpul', 'hub_site']
            dapot_cols = [c for c in dapot_cols if c in df_dapot.columns]
            df_merged = pd.merge(df_merged, df_dapot[dapot_cols], left_on='Site_ID', right_on='site_id', how='left')
            df_merged = df_merged[df_merged['Site_ID'].isin(df_dapot['site_id'])]
            
            # Bersihkan nilai NaN buat filter
            if 'kotakab' in df_merged.columns: df_merged['kotakab'] = df_merged['kotakab'].fillna('UNKNOWN')
            if 'kecamatan' in df_merged.columns: df_merged['kecamatan'] = df_merged['kecamatan'].fillna('UNKNOWN')

        # --- SUPER FAST CALCULATION (VECTORIZED) ---
        mask = (df_merged['Availability'] > 0) & (df_merged['Packet_Loss'] < 1)
        
        df_merged['Potential_Revenue'] = df_merged['Actual_Revenue']
        df_merged.loc[mask, 'Potential_Revenue'] = df_merged['Actual_Revenue'] / (df_merged['Availability'] * (1 - df_merged['Packet_Loss']))
        df_merged['Lost_Revenue'] = df_merged['Potential_Revenue'] - df_merged['Actual_Revenue']
        
        df_merged['Potential_Payload'] = df_merged['Actual_Payload']
        df_merged.loc[mask, 'Potential_Payload'] = df_merged['Actual_Payload'] / (df_merged['Availability'] * (1 - df_merged['Packet_Loss']))
        df_merged['Lost_Payload'] = df_merged['Potential_Payload'] - df_merged['Actual_Payload']
        
        df_merged['Availability_Pct'] = df_merged['Availability'] * 100
        df_merged['Packet_Loss_Pct'] = df_merged['Packet_Loss'] * 100

except Exception as e:
    st.error(f"Gagal memuat data sistem: {e}")
    st.stop()

# --- 4. UI: FILTER MULTILEVEL ---
st.write("### ⚙️ Filter Analisis Area & Site")

col_f1, col_f2, col_f3, col_f4 = st.columns(4)

with col_f1:
    min_date = df_merged['Date'].min()
    max_date = df_merged['Date'].max()
    selected_dates = st.date_input("📅 Periode Tanggal:", value=(min_date, max_date), min_value=min_date, max_value=max_date)

start_date, end_date = selected_dates if len(selected_dates) == 2 else (selected_dates[0], selected_dates[0])
df_periode = df_merged[(df_merged['Date'] >= start_date) & (df_merged['Date'] <= end_date)].copy()

with col_f2:
    if 'kotakab' in df_periode.columns:
        list_kab = sorted(df_periode['kotakab'].unique().tolist())
        selected_kab = st.multiselect("🏙️ Filter Kabupaten:", options=list_kab)
    else: selected_kab = []

if selected_kab: df_periode = df_periode[df_periode['kotakab'].isin(selected_kab)]

with col_f3:
    if 'kecamatan' in df_periode.columns:
        list_kec = sorted(df_periode['kecamatan'].unique().tolist())
        selected_kec = st.multiselect("🏘️ Filter Kecamatan:", options=list_kec)
    else: selected_kec = []

if selected_kec: df_periode = df_periode[df_periode['kecamatan'].isin(selected_kec)]

with col_f4:
    list_sites = sorted(df_periode['Site_ID'].dropna().unique().tolist())
    dropdown_options = [f"{s} - {name_mapping.get(s, 'Unknown')}" for s in list_sites]
    selected_sites = st.multiselect("🔍 Filter Spesifik Site:", options=dropdown_options)

# --- 5. LOGIC PROCESSING & ANAKAN INCLUSION ---
if selected_sites:
    all_related = set()
    for s in selected_sites:
        site_code = s.split(" - ")[0]
        all_related.add(site_code)
        anak_str = site_mapping.get(site_code, '')
        list_anak = [] if pd.isna(anak_str) or anak_str == '' else [x.strip().upper() for x in str(anak_str).split(',')]
        all_related.update(list_anak)
    impact_df = df_periode[df_periode['Site_ID'].isin(all_related)].copy()
    
    # Tandai Induk/Anakan khusus jika ada site yang dipilih
    parent_codes = [s.split(" - ")[0] for s in selected_sites]
    impact_df['Keterangan'] = impact_df['Site_ID'].apply(lambda x: 'Induk (Parent)' if x in parent_codes else 'Anakan (Child)')
else:
    impact_df = df_periode.copy()
    impact_df['Keterangan'] = 'Terfilter dari Area'

if impact_df.empty:
    st.warning("⚠️ Data tidak ditemukan untuk filter yang dipilih.")
    st.stop()

# --- 6. DASHBOARD WORST CONTRIBUTOR ---
st.write("---")
st.write(f"### 🚨 Top Worst Contributor ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
st.caption("Site dengan nilai **Lost Revenue** paling besar yang menyumbang kerugian perusahaan.")

col_w1, col_w2, col_w3 = st.columns(3)

with col_w1:
    if 'kotakab' in impact_df.columns:
        worst_kab = impact_df.groupby('kotakab')['Lost_Revenue'].sum().nlargest(5).sort_values()
        fig_kab = px.bar(worst_kab, x=worst_kab.values, y=worst_kab.index, orientation='h', 
                         title='Top 5 Worst Kabupaten', labels={'x':'Lost Revenue (Rp)', 'y':''}, color_discrete_sequence=['#EC2028'])
        fig_kab.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor='white')
        st.plotly_chart(fig_kab, use_container_width=True)

with col_w2:
    if 'kecamatan' in impact_df.columns:
        worst_kec = impact_df.groupby('kecamatan')['Lost_Revenue'].sum().nlargest(5).sort_values()
        fig_kec = px.bar(worst_kec, x=worst_kec.values, y=worst_kec.index, orientation='h', 
                         title='Top 5 Worst Kecamatan', labels={'x':'Lost Revenue (Rp)', 'y':''}, color_discrete_sequence=['#ff7f0e'])
        fig_kec.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor='white')
        st.plotly_chart(fig_kec, use_container_width=True)

with col_w3:
    worst_site = impact_df.groupby('Site_ID')['Lost_Revenue'].sum().nlargest(5).sort_values()
    fig_site = px.bar(worst_site, x=worst_site.values, y=worst_site.index, orientation='h', 
                      title='Top 5 Worst Site', labels={'x':'Lost Revenue (Rp)', 'y':''}, color_discrete_sequence=['#d62728'])
    fig_site.update_layout(height=350, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor='white')
    st.plotly_chart(fig_site, use_container_width=True)


# --- 7. DASHBOARD SUMMARY ---
st.write("---")
st.write(f"### 📈 Ringkasan Performa Keseluruhan Area Terpilih")

tot_act_rev, tot_pot_rev, tot_lost_rev = impact_df['Actual_Revenue'].sum(), impact_df['Potential_Revenue'].sum(), impact_df['Lost_Revenue'].sum()
tot_act_pay, tot_pot_pay, tot_lost_pay = impact_df['Actual_Payload'].sum(), impact_df['Potential_Payload'].sum(), impact_df['Lost_Payload'].sum()

pct_gain_rev = ((tot_pot_rev - tot_act_rev) / tot_act_rev * 100) if tot_act_rev > 0 else 0
pct_lost_rev = (tot_lost_rev / tot_pot_rev * 100) if tot_pot_rev > 0 else 0
pct_gain_pay = ((tot_pot_pay - tot_act_pay) / tot_act_pay * 100) if tot_act_pay > 0 else 0
pct_lost_pay = (tot_lost_pay / tot_pot_pay * 100) if tot_pot_pay > 0 else 0

gain_rev_str, gain_rev_col = (f"+{pct_gain_rev:,.2f}% Kenaikan", "normal") if pct_gain_rev > 0 else ("0% Kenaikan", "off")
loss_rev_str, loss_rev_col = (f"{pct_lost_rev:,.2f}% Loss", "normal") if pct_lost_rev > 0 else ("0% Loss", "off")
gain_pay_str, gain_pay_col = (f"+{pct_gain_pay:,.2f}% Kenaikan", "normal") if pct_gain_pay > 0 else ("0% Kenaikan", "off")
loss_pay_str, loss_pay_col = (f"{pct_lost_pay:,.2f}% Loss", "normal") if pct_lost_pay > 0 else ("0% Loss", "off")

st.write("##### 💰 Analisis Revenue")
c1, c2, c3 = st.columns(3)
c1.metric("🌟 Potensi Gain (100% Ok)", f"Rp {tot_pot_rev:,.0f}", gain_rev_str, delta_color=gain_rev_col)
c2.metric("📉 Lost Revenue", f"Rp {tot_lost_rev:,.0f}", f"-{loss_rev_str}", delta_color="inverse")
c3.metric("Pendapatan Aktual", f"Rp {tot_act_rev:,.0f}")

st.write("##### 📦 Analisis Payload")
c4, c5, c6 = st.columns(3)
c4.metric("🚀 Potensi Traffic (100% Ok)", f"{tot_pot_pay:,.0f} GB", gain_pay_str, delta_color=gain_pay_col)
c5.metric("📉 Lost Payload", f"{tot_lost_pay:,.0f} GB", f"-{loss_pay_str}", delta_color="inverse")
c6.metric("Traffic Aktual", f"{tot_act_pay:,.0f} GB")

st.divider()

# --- 8. TREND GRAFIK HARIAN ---
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
    if len(df['Site_ID'].unique()) > 20: 
        # Kalau sitenya terlalu banyak (misal lihat se-kabupaten), grafiknya kita gabung aja biar gak pusing
        df = df.groupby(x_col).sum().reset_index()
        df['Site_ID'] = 'TOTAL AGREGAT'
        
    if tipe == 'rev':
        fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline')
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Nilai: Rp %{y:,.0f}<extra></extra>")
    elif tipe == 'pay':
        fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline')
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Nilai: %{y:,.0f} GB<extra></extra>")
    else:
        fig = px.line(df, x=x_col, y=y_col, color='Site_ID', markers=True, line_shape='spline')
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Nilai: %{y:.2f}%<extra></extra>")
    
    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False, linecolor='lightgray'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
    return fig

with tab1: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Potential_Revenue', 'rev'), use_container_width=True)
with tab2: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Lost_Revenue', 'rev'), use_container_width=True)
with tab3: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Potential_Payload', 'pay'), use_container_width=True)
with tab4: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Lost_Payload', 'pay'), use_container_width=True)
with tab5: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Availability_Pct', 'pct'), use_container_width=True)
with tab6: st.plotly_chart(buat_grafik(trend_df, 'Date_Str', 'Packet_Loss_Pct', 'pct'), use_container_width=True)

st.divider()

# --- 9. DETAIL DATAFRAME ---
st.write("### 🗄️ Detail Data Harian Aktual vs Potensi")

base_cols = ['Date', 'Site_ID', 'site_name', 'Keterangan', 'kotakab', 'kecamatan', 'Availability', 'Packet_Loss', 'Potential_Revenue', 'Lost_Revenue', 'Actual_Revenue', 'Potential_Payload', 'Lost_Payload', 'Actual_Payload']
display_cols = [c for c in base_cols if c in impact_df.columns]

col_t1, col_t2 = st.columns([1, 1])
with col_t1:
    st.caption("Gunakan fitur Download untuk mengekspor data yang sedang di-filter.")
with col_t2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        impact_df.drop(columns=['site_id'], errors='ignore').to_excel(writer, index=False, sheet_name='Data_Loss')
    st.download_button("📥 Download Excel (Filtered)", data=buffer.getvalue(), file_name="Data_Loss_Impact_Area.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
).apply(lambda s: ['background-color: #d4edda; color: #155724; font-weight: bold;' if v <= 0 else get_red_maroon_style((v - 0) / (s.max() - 0) if s.max() > 0 else 0) if pd.notna(v) else '' for v in s], subset=['Lost_Revenue', 'Lost_Payload'])

st.dataframe(styled_df, use_container_width=True)

# --- FOOTER ---
st.markdown('<div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #eaeaea; color: #888888; font-size: 14px;">© 2026 | Created with ❤️ by Fauzi Ramdani - 97122</div>', unsafe_allow_html=True)
