import streamlit as st
import pandas as pd

# --- 1. LOGIC KALKULASI LOST REVENUE & PAYLOAD ---
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

# --- 2. BIKIN UI STREAMLIT ---
st.set_page_config(page_title="Network Loss Impact", layout="wide")

st.title("💸 Network Loss Impact Dashboard")
st.write("Pantau *lost payload* dan *revenue* berdasarkan *availability* site. **Upload file operasional lo di bawah.**")

# --- 3. FITUR UPLOAD FILE ---
uploaded_file = st.file_uploader("📂 Taruh file CSV atau Excel lo di sini:", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    # Cek tipe file yang diupload
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success(f"File {uploaded_file.name} berhasil dimuat!")
        
        # --- 4. TAMPILAN DASHBOARD ---
        search_site = st.text_input("🔍 Masukkan Site ID (Contoh: SITE-001):").strip().upper()

        if search_site:
            parent_info, impact_df = calculate_loss(df, search_site)
            
            if impact_df is None or impact_df.empty:
                st.warning(f"Wah, Site ID {search_site} gak ketemu di data. Coba cek typo.")
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

    except Exception as e:
        st.error(f"Gagal memproses file. Pastikan format datanya bener ya. Error: {e}")
else:
    st.info("👈 Menunggu file data dimasukkan...")
