import streamlit as st
import pandas as pd
import re

# --- 1. LOGIC KALKULASI LOST REVENUE & PAYLOAD ---
def calculate_loss(df, site_id):
    parent_data = df[df['Site_ID'] == site_id]
    if parent_data.empty:
        return None, None
        
    # Cek anakannya kalau kolomnya tersedia
    child_sites_str = parent_data['Child_Sites'].values[0] if 'Child_Sites' in df.columns else ''
    child_list = [x.strip() for x in str(child_sites_str).split(',')] if pd.notna(child_sites_str) and child_sites_str != '' else []
    
    all_related_sites = [site_id] + child_list
    filtered_df = df[df['Site_ID'].isin(all_related_sites)].copy()
    
    # Kalkulasi loss berdasarkan Availability
    filtered_df['Lost_Revenue'] = filtered_df.apply(
        lambda row: (row['Actual_Revenue'] / row['Availability']) - row['Actual_Revenue'] if row['Availability'] > 0 else row['Actual_Revenue'], axis=1
    )
    filtered_df['Lost_Payload'] = filtered_df.apply(
        lambda row: (row['Actual_Payload'] / row['Availability']) - row['Actual_Payload'] if row['Availability'] > 0 else row['Actual_Payload'], axis=1
    )
    filtered_df['Type'] = filtered_df['Site_ID'].apply(lambda x: 'Parent' if x == site_id else 'Child')
    
    return parent_data, filtered_df

# --- 2. BIKIN UI STREAMLIT ---
st.set_page_config(page_title="Network Loss Impact", layout="wide")

st.title("💸 Network Loss Impact Dashboard")
st.write("Pantau *lost payload* dan *revenue* berdasarkan *availability* harian.")

# Bikin 2 kolom uploader biar enak
col_up1, col_up2 = st.columns(2)
with col_up1:
    file_rev = st.file_uploader("📂 1. Upload Data Revenue (a4_npac...)", type=["csv", "xlsx", "xls"])
with col_up2:
    file_avail = st.file_uploader("📂 2. Upload Data Availability (1-28 may...)", type=["csv", "xlsx", "xls"])

if file_rev is not None and file_avail is not None:
    try:
        with st.spinner("Mengekstrak dan menggabungkan data..."):
            
            # === 1. LOAD DATA REVENUE ===
            if file_rev.name.endswith('.csv'):
                df_rev = pd.read_csv(file_rev)
            else:
                df_rev = pd.read_excel(file_rev)
            df_rev.columns = df_rev.columns.str.strip() # Bersihin spasi nyempil di nama kolom
            
            # === 2. LOAD DATA AVAILABILITY (DENGAN AUTO-DETECT SHEET) ===
            if file_avail.name.endswith('.csv'):
                df_avail = pd.read_csv(file_avail)
            else:
                xls_avail = pd.ExcelFile(file_avail)
                sheet_target = xls_avail.sheet_names[0] # Default sheet pertama
                
                # Looping nyari sheet mana yang punya kolom 'Begin Time'
                for sheet in xls_avail.sheet_names:
                    df_cek = pd.read_excel(xls_avail, sheet_name=sheet, nrows=1)
                    if any('Begin Time' in col for col in df_cek.columns):
                        sheet_target = sheet
                        break
                        
                df_avail = pd.read_excel(xls_avail, sheet_name=sheet_target)
                
            df_avail.columns = df_avail.columns.str.strip() # Bersihin spasi
            
            # === 3. PREPROCESSING REVENUE ===
            df_rev['Date'] = pd.to_datetime(df_rev['date'], format='mixed').dt.strftime('%Y-%m-%d')
            df_rev['Site_ID'] = df_rev['site_id'].astype(str).str.upper()
            
            df_rev.rename(columns={
                'revenue': 'Actual_Revenue',
                'total_payload_mbyte': 'Actual_Payload'
            }, inplace=True)
            
            df_rev['Actual_Revenue'] = pd.to_numeric(df_rev['Actual_Revenue'], errors='coerce').fillna(0)
            df_rev['Actual_Payload'] = pd.to_numeric(df_rev['Actual_Payload'], errors='coerce').fillna(0)
            
            # === 4. PREPROCESSING AVAILABILITY ===
            df_avail['Date'] = pd.to_datetime(df_avail['Begin Time'], format='mixed').dt.strftime('%Y-%m-%d')
            
            # Ngambil 3 huruf & 3 angka (misal KKP326) dari nama Managed Element
            df_avail['Site_ID'] = df_avail['Managed Element'].astype(str).str.extract(r'([A-Z]{3}\d{3})')
            
            # Nyapu semua kolom yang ada kata 'Availability'
            avail_cols = [c for c in df_avail.columns if 'Availability' in c]
            df_avail[avail_cols] = df_avail[avail_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Availability'] = df_avail[avail_cols].bfill(axis=1).iloc[:, 0].fillna(1.0)
            
            # Nyapu semua kolom yang ada kata 'Loss'
            loss_cols = [c for c in df_avail.columns if 'Loss' in c]
            df_avail[loss_cols] = df_avail[loss_cols].apply(pd.to_numeric, errors='coerce')
            df_avail['Packet_Loss'] = df_avail[loss_cols].bfill(axis=1).iloc[:, 0].fillna(0.0)

            # === 5. MERGE (JOIN) KEDUA DATA BERDASARKAN SITE & TANGGAL ===
            df_merged = pd.merge(
                df_rev, 
                df_avail[['Site_ID', 'Date', 'Availability', 'Packet_Loss']].drop_duplicates(subset=['Site_ID', 'Date']), 
                on=['Site_ID', 'Date'], 
                how='left'
            )
            
            if 'Child_Sites' not in df_merged.columns:
                df_merged['Child_Sites'] = ''

        st.success("✅ Data berhasil digabungkan!")
        
        # --- 4. TAMPILAN DASHBOARD ---
        # Bikin filter tanggal, karena data availability lo isinya berhari-hari
        tanggal_list = sorted(df_merged['Date'].dropna().unique(), reverse=True)
        selected_date = st.selectbox("📅 Pilih Tanggal Analisis:", tanggal_list)
        
        df_harian = df_merged[df_merged['Date'] == selected_date]

        search_site = st.text_input("🔍 Masukkan Site ID (Contoh: AMT001, KKP027):").strip().upper()

        if search_site:
            parent_info, impact_df = calculate_loss(df_harian, search_site)
            
            if impact_df is None or impact_df.empty:
                st.warning(f"Wah, Site ID {search_site} gak ketemu di tanggal {selected_date}. Coba cek typo.")
            else:
                st.subheader(f"Hasil Analisis: {search_site} & Site Anakannya")
                
                total_lost_rev = impact_df['Lost_Revenue'].sum()
                total_lost_payload = impact_df['Lost_Payload'].sum()
                
                col1, col2 = st.columns(2)
                col1.metric("📉 Total Lost Revenue (IDR)", f"Rp {total_lost_rev:,.0f}")
                # Datanya dalam MB, dibagi 1024 biar nampil GB di card utama
                col2.metric("📦 Total Lost Payload", f"{(total_lost_payload / 1024):,.2f} GB")
                
                st.divider()
                st.write("### 📊 Breakdown Loss per Site (Parent vs Child)")
                
                col3, col4 = st.columns(2)
                with col3:
                    st.write("**Lost Revenue Breakdown**")
                    st.bar_chart(data=impact_df, x='Site_ID', y='Lost_Revenue', color='#FF4B4B')
                    
                with col4:
                    st.write("**Lost Payload Breakdown (MB)**")
                    st.bar_chart(data=impact_df, x='Site_ID', y='Lost_Payload', color='#45B6FE')
                    
                st.write("### 🗄️ Detail Data Site")
                display_cols = ['Site_ID', 'Type', 'Availability', 'Packet_Loss', 'Actual_Revenue', 'Lost_Revenue', 'Lost_Payload']
                st.dataframe(impact_df[display_cols].style.format({
                    'Availability': '{:.2%}',
                    'Packet_Loss': '{:.2%}',
                    'Actual_Revenue': 'Rp {:,.0f}',
                    'Lost_Revenue': 'Rp {:,.0f}',
                    'Lost_Payload': '{:,.2f} MB'
                }), use_container_width=True)

    except Exception as e:
        st.error(f"Gagal memproses file. Error: {e}")
else:
    st.info("👈 Silakan upload file Revenue dan file Availability di kolom atas...")
