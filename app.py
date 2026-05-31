import streamlit as st
import pandas as pd
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.file import File
import io
import os

# --- 1. SETUP KONEKSI SHAREPOINT LEWAT SECRETS ---
SHAREPOINT_URL = st.secrets["sharepoint"]["url"]
SHAREPOINT_USER = st.secrets["sharepoint"]["username"]
SHAREPOINT_PWD = st.secrets["sharepoint"]["password"]
FOLDER_PATH = st.secrets["sharepoint"]["folder_path"]

# Fungsi untuk ambil daftar semua file di dalam folder SharePoint
@st.cache_data(ttl=600) # Cache daftar file selama 10 menit
def get_all_files_from_folder():
    try:
        ctx = ClientContext(SHAREPOINT_URL).with_credentials(UserCredential(SHAREPOINT_USER, SHAREPOINT_PWD))
        folder = ctx.web.get_folder_by_server_relative_url(FOLDER_PATH)
        files = folder.files
        ctx.load(files)
        ctx.execute_query()
        
        # Ambil nama file dan relative URL-nya (khusus file .csv atau .xlsx)
        file_dict = {}
        for f in files:
            name = f.properties["Name"]
            if name.endswith(('.csv', '.xlsx', '.xls')):
                file_dict[name] = f.properties["ServerRelativeUrl"]
        return file_dict
    except Exception as e:
        st.error(f"Gagal membaca folder SharePoint: {e}")
        # Dummy list buat testing di lokal jika SharePoint offline
        return {
            "Data_Availability_2026_05_29.csv": "dummy_url_1",
            "Data_Availability_2026_05_30.csv": "dummy_url_2",
            "Data_Availability_2026_05_31.csv": "dummy_url_3"
        }

# Fungsi untuk baca konten file yang dipilih
@st.cache_data(ttl=3600) 
def load_selected_file(file_url, file_name):
    # Jika mode dummy lokal
    if "dummy_url" in file_url:
        return pd.DataFrame({
            'Site_ID': ['SITE-001', 'SITE-002', 'SITE-003', 'SITE-004'],
            'Child_Sites': ['SITE-002,SITE-003', '', '', ''], 
            'Availability': [0.95, 0.90, 1.0, 0.85], 
            'Packet_Loss': [0.02, 0.05, 0.0, 0.08],
            'Actual_Revenue': [10000000, 5000000, 4000000, 8000000],
            'Actual_Payload': [500, 200, 150, 400] 
        })
        
    try:
        ctx = ClientContext(SHAREPOINT_URL).with_credentials(UserCredential(SHAREPOINT_USER, SHAREPOINT_PWD))
        response = File.open_binary(ctx, file_url)
        bytes_file_obj = io.BytesIO(response.content)
        
        if file_name.endswith('.csv'):
            df = pd.read_csv(bytes_file_obj)
        else:
            df = pd.read_excel(bytes_file_obj) # Support Excel juga kalau sewaktu-waktu formatnya ganti
        return df
    except Exception as e:
        st.error(f"Gagal memuat file {file_name}: {e}")
        return pd.DataFrame()

# --- 2. LOGIC KALKULASI LOST REVENUE & PAYLOAD ---
def calculate_loss(df, site_id):
    parent_data = df[df['Site_ID'] == site_id]
    if parent_data.empty:
        return None, None
        
    child_sites_str = parent_data['Child_Sites'].values[0]
    child_list = [x.strip() for x in str(child_sites_str).split(',')] if pd.notna(child_sites_str) and child_sites_str != '' else []
    
    all_related_sites = [site_id] + child_list
    filtered_df = df[df['Site_ID'].isin(all_related_sites)].copy()
    
    filtered_df['Lost_Revenue'] = filtered_df.apply(
        lambda row: (row['Actual_Revenue'] / row['Availability']) - row['Actual_Revenue'] if row['Availability'] > 0 else row['Actual_Revenue'], axis=1
    )
    filtered_df['Lost_Payload'] = filtered_df.apply(
        lambda row: (row['Actual_Payload'] / row['Availability']) - row['Actual_Payload'] if row['Availability'] > 0 else row['Actual_Payload'], axis=1
    )
    filtered_df['Type'] = filtered_df['Site_ID'].apply(lambda x: 'Parent' if x == site_id else 'Child')
    
    return parent_data, filtered_df

# --- 3. BIKIN UI STREAMLIT ---
st.set_page_config(page_title="Network Loss Impact", layout="wide")

st.title("💸 Network Loss Impact Dashboard")
st.write("Pantau *lost payload* dan *revenue* berdasarkan *availability* site dari file pilihan lo.")

# Step A: Ambil semua daftar file di folder
with st.spinner("Nge-list seluruh file di folder SharePoint..."):
    available_files = get_all_files_from_folder()

# Step B: Tampilin Dropdown Pilihan File di UI
if available_files:
    file_options = list(available_files.keys())
    # Urutin biar file terbaru muncul di paling atas (asumsi penamaan file pakai tanggal, misal: data_2026_05_31.csv)
    file_options.sort(reverse=True) 
    
    selected_file_name = st.selectbox("📂 Pilih File Data Operasional:", file_options)
    selected_file_url = available_files[selected_file_name]
    
    # Step C: Load data berdasarkan file yang dipilih user
    with st.spinner(f"Membaca data dari {selected_file_name}..."):
        df = load_selected_file(selected_file_url, selected_file_name)
else:
    st.error("Gak ada file (.csv/.xlsx) yang ditemukan di folder SharePoint tersebut.")
    df = pd.DataFrame()

# Input Site ID (Hanya aktif kalau data berhasil di-load)
if not df.empty:
    search_site = st.text_input("🔍 Masukkan Site ID (Contoh: SITE-001):").strip().upper()

    if search_site:
        parent_info, impact_df = calculate_loss(df, search_site)
        
        if impact_df is None or impact_df.empty:
            st.warning(f"Wah, Site ID {search_site} gak ketemu di file {selected_file_name}. Coba cek typo.")
        else:
            st.subheader(f"Hasil Analisis: {search_site} & Site Anakannya")
            
            total_lost_rev = impact_df['Lost_Revenue'].sum()
            total_lost_payload = impact_df['Lost_Payload'].sum()
            
            col1, col2 = st.columns(2)
            col1.metric("📉 Total Lost Revenue (IDR)", f"Rp {total_lost_rev:,.0f}")
            col2.metric("📦 Total Lost Payload", f"{total_lost_payload:,.2f} GB")
            
            st.divider()
            st.write("### 📊 Breakdown Loss per Site (Parent vs Child)")
            
            col3, col4 = st.columns(2)
            with col3:
                st.write("**Lost Revenue Breakdown**")
                st.bar_chart(data=impact_df, x='Site_ID', y='Lost_Revenue', color='#FF4B4B')
                
            with col4:
                st.write("**Lost Payload Breakdown**")
                st.bar_chart(data=impact_df, x='Site_ID', y='Lost_Payload', color='#45B6FE')
                
            st.write("### 🗄️ Detail Data Site")
            display_cols = ['Site_ID', 'Type', 'Availability', 'Packet_Loss', 'Lost_Revenue', 'Lost_Payload']
            st.dataframe(impact_df[display_cols].style.format({
                'Availability': '{:.1%}',
                'Packet_Loss': '{:.1%}',
                'Lost_Revenue': 'Rp {:,.0f}',
                'Lost_Payload': '{:,.2f}'
            }), use_container_width=True)
