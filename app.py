import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Network Loss Impact", layout="wide")

st.title("💸 Network Loss Impact Dashboard")
st.write("Pantau *lost payload*, *revenue*, dan trend berdasarkan *availability* secara periodik.")

# --- 1. LOAD MAPPING SITE ANAKAN & NAMA SITE DARI FILE LOKAL ---
@st.cache_data
def load_site_mapping():
    try:
        df_dapot = pd.read_excel("Dapot site kalimantan.xlsx", engine="openpyxl")
        df_dapot['Site ID'] = df_dapot['Site ID'].astype(str).str.strip().str.upper()
        
        # Bikin dua dictionary: satu buat anakan, satu buat nama site
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
        
    # Kalkulasi dibikin MINUS (-) biar kelihatan kalau itu Loss
    filtered_df['Lost_Revenue'] = filtered_df.apply(
        lambda row: -1 * ((row['Actual_Revenue'] / row['Availability']) - row['Actual_Revenue']) if row['Availability'] > 0 else -1 * row['Actual_Revenue'], axis=1
    )
    filtered_df['Lost_Payload'] = filtered_df.apply(
        lambda row: -1 * ((row['Actual_Payload'] / row['Availability']) - row['Actual_Payload']) if row['Availability'] > 0 else -1 * row['Actual_Payload'], axis=1
    )
    
    # Kolom bantuan buat pop-up chart Plotly
    filtered_df['Availability_Pct'] = filtered_df['Availability'] * 100
    filtered_df['Packet_Loss_Pct'] = filtered_df['Packet_Loss'] * 100
    filtered_df['Type'] = filtered_df['Site_ID'].apply(lambda x: 'Parent' if x == site_id else 'Child')
    
    return filtered_df

# --- 3. BIKIN UI STREAMLIT ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    file_rev = st.file_uploader("📂 1. Upload Data Revenue Harian", type=["csv", "xlsx", "xls"])
with col_up2:
    file_avail = st.file_uploader("📂 2. Upload Data Availability U2000", type=["csv", "xlsx", "xls"])

if file_rev is not None and file_avail is not None:
    try:
        with st.spinner("Mengekstrak dan menggabungkan data..."):
            
            # LOAD REVENUE
            if file_rev.name.endswith('.csv'):
                df_rev = pd.read_csv(file_rev)
            else:
                df_rev = pd.read_excel(file_rev)
            df_rev.columns = df_rev.columns.str.strip() 
            
            # LOAD AVAILABILITY
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
            
            # PREPROCESSING
            df_rev['Date'] = pd.to_datetime(df_rev['date'], format='mixed').dt.date
            df_rev['Site_ID'] = df_rev['site_id'].astype(str).str.upper()
            
            rev_col = [c for c in df_rev.columns if 'revenue' in c.lower()][0]
            payload_col = [c for c in df_rev.columns if 'payload' in c.lower()][0]
            
            df_rev.rename(columns={rev_col: 'Actual_Revenue', payload_col: 'Actual_Payload'}, inplace=True)
            df_rev['Actual_Revenue'] = pd.to_numeric(df_rev['Actual_Revenue'], errors='coerce').fillna(0)
            
            # Langsung ubah Payload dari MB ke GB di awal
            df_rev['Actual_Payload'] = pd.to_numeric(df_rev['Actual_Payload'], errors='coerce').fillna(0) / 1024
            
            df_avail['Date'] = pd.to_datetime(df_avail['Begin Time'], format='mixed').dt.date
            df_avail['Site_ID'] = df_avail['Managed Element'].astype(str).str.extract(r'([A-Z]{3}\d{3})')
            
            avail_cols = [c for c in df_avail.columns if 'Availability' in c]
            df_avail[avail_cols] = df_avail[avail_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Availability'] = df_avail[avail_cols].bfill(axis=1).iloc[:, 0].fillna(1.0)
            
            loss_cols = [c for c in df_avail.columns if 'Loss' in c]
            df_avail[loss_cols] = df_avail[loss_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Packet_Loss'] = df_avail[loss_cols].bfill(axis=1).iloc[:, 0].fillna(0.0)

            # MERGE
            df_merged = pd.merge(
                df_rev, 
                df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']].drop_duplicates(subset=['Site_ID', 'Date']), 
                on=['Site_ID', 'Date'], 
                how='left'
            )
            
        st.success("✅ Data berhasil digabungkan!")
        
        # --- 4. TAMPILAN DASHBOARD ---
        st.divider()
        st.write("### ⚙️ Filter Analisis")
        
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            all_sites = sorted(df_merged['Site_ID'].dropna().unique().tolist())
            # Format Dropdown: Site ID - Site Name
            dropdown_options = ["-- Pilih Site --"] + [f"{site} - {name_mapping.get(site, 'Unknown')}" for site in all_sites]
            search_site_selection = st.selectbox("🔍 Cari & Pilih Site ID:", options=dropdown_options)
            
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
            # Ekstrak Site ID asli dari string dropdown
            search_site = search_site_selection.split(" - ")[0]
            
            if len(selected_dates) == 2:
                start_date, end_date = selected_dates
            else:
                start_date = end_date = selected_dates[0]
                
            df_periode = df_merged[(df_merged['Date'] >= start_date) & (df_merged['Date'] <= end_date)]
            impact_df = calculate_loss(df_periode, search_site, site_mapping)
            
            if impact_df.empty:
                st.warning(f"Wah, Data untuk Site {search_site} gak ketemu di rentang tanggal tersebut.")
            else:
                st.write(f"### 📈 Hasil Analisis: {search_site_selection} & Site Anakannya ({start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')})")
                
                total_lost_rev = impact_df['Lost_Revenue'].sum()
                total_lost_payload = impact_df['Lost_Payload'].sum()
                
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("📉 Total Lost Revenue (IDR)", f"Rp {total_lost_rev:,.0f}")
                col_m2.metric("📦 Total Lost Payload", f"{total_lost_payload:,.2f} GB")
                
                st.divider()
                
                # --- 5. GRAFIK TREND (PLOTLY) ---
                st.write("### 📊 Trend Grafik Harian")
                
                trend_df = impact_df.groupby(['Date', 'Site_ID']).agg({
                    'Lost_Revenue': 'sum',
                    'Lost_Payload': 'sum',
                    'Availability_Pct': 'mean',
                    'Packet_Loss_Pct': 'mean'
                }).reset_index()
                
                trend_df['Date_Str'] = trend_df['Date'].astype(str)
                
                tab1, tab2, tab3, tab4 = st.tabs(["Lost Revenue", "Lost Payload", "Availability", "Packet Loss"])
                
                with tab1:
                    fig1 = px.line(trend_df, x='Date_Str', y='Lost_Revenue', color='Site_ID', markers=True)
                    fig1.update_traces(hovertemplate='Tanggal: %{x}<br>Loss: Rp %{y:,.0f}')
                    st.plotly_chart(fig1, use_container_width=True)
                with tab2:
                    fig2 = px.line(trend_df, x='Date_Str', y='Lost_Payload', color='Site_ID', markers=True)
                    fig2.update_traces(hovertemplate='Tanggal: %{x}<br>Loss: %{y:,.2f} GB')
                    st.plotly_chart(fig2, use_container_width=True)
                with tab3:
                    fig3 = px.line(trend_df, x='Date_Str', y='Availability_Pct', color='Site_ID', markers=True)
                    fig3.update_traces(hovertemplate='Tanggal: %{x}<br>Availability: %{y:.2f}%')
                    st.plotly_chart(fig3, use_container_width=True)
                with tab4:
                    fig4 = px.line(trend_df, x='Date_Str', y='Packet_Loss_Pct', color='Site_ID', markers=True)
                    fig4.update_traces(hovertemplate='Tanggal: %{x}<br>Packet Loss: %{y:.2f}%')
                    st.plotly_chart(fig4, use_container_width=True)

                st.divider()
                
                # --- 6. TABEL RAW DATA DENGAN GRADIENT WARNA ---
                st.write("### 🗄️ Detail Data Harian")
                display_cols = ['Date', 'Site_ID', 'Type', 'Availability', 'Packet_Loss', 'Actual_Revenue', 'Lost_Revenue', 'Lost_Payload']
                
                # Set Warna: Good to Worst
                # Availability: Hijau (1.0) ke Merah (0.0) -> RdYlGn
                # Packet Loss: Hijau (0.0) ke Merah (1.0) -> RdYlGn_r (Reversed)
                # Lost Rev & Payload: Hijau (0) ke Merah (-Minus Besar) -> RdYlGn (Karena angka minus lebih kecil dari 0)
                
                styled_df = impact_df[display_cols].sort_values(by=['Date', 'Site_ID']).style.format({
                    'Availability': '{:.2%}',
                    'Packet_Loss': '{:.2%}',
                    'Actual_Revenue': 'Rp {:,.0f}',
                    'Lost_Revenue': 'Rp {:,.0f}',
                    'Lost_Payload': '{:,.2f} GB'
                }).background_gradient(
                    cmap='RdYlGn', subset=['Availability']
                ).background_gradient(
                    cmap='RdYlGn_r', subset=['Packet_Loss']
                ).background_gradient(
                    cmap='RdYlGn', subset=['Lost_Revenue']
                ).background_gradient(
                    cmap='RdYlGn', subset=['Lost_Payload']
                )
                
                st.dataframe(styled_df, use_container_width=True)

    except Exception as e:
        st.error(f"Gagal memproses file. Pastikan format kolom sama. Error: {e}")
