import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import io

st.set_page_config(page_title="電力數據分析", layout="wide")
st.title("⚡ ItriGel J200 PA60互動式電力數據比對工具")

# ── 側欄署名 ──────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="text-align:center; padding: 12px 0 4px 0;">
        <a href="https://github.com/YORROY123" target="_blank">
            <img src="https://avatars.githubusercontent.com/YORROY123"
                 width="72" style="border-radius:50%; border:2px solid #4CAF50;"/>
        </a>
        <br/>
        <a href="https://github.com/YORROY123" target="_blank"
           style="color:#4CAF50; font-weight:bold; text-decoration:none; font-size:14px;">
            YORROY123
        </a>
        <p style="color:#888; font-size:11px; margin:2px 0 0 0;">Made by YORROY123</p>
    </div>
    <hr style="border-color:#333; margin: 8px 0;"/>
    """,
    unsafe_allow_html=True
)

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    if '時間' in df.columns:
        df['時間'] = pd.to_datetime(df['時間'])
        df.set_index('時間', inplace=True)
    return df

def compute_derived_columns(df):
    """計算衍生欄位，來源欄位缺失時自動跳過"""
    derived = {
        "L1_kW_total (冷庫總電)": (["L1_kW_a", "L1_kW_b", "L1_kW_c"], lambda d: d["L1_kW_a"] + d["L1_kW_b"] + d["L1_kW_c"]),
        "L2_kW_total (壓縮機總電)": (["L2_kW_a", "L2_kW_b", "L2_kW_c"], lambda d: d["L2_kW_a"] + d["L2_kW_b"] + d["L2_kW_c"]),
        "L3_kW_total (除霜電熱)": (["L3_kW_a", "L3_kW_b", "L3_kW_c"], lambda d: d["L3_kW_a"] + d["L3_kW_b"] + d["L3_kW_c"]),
        # L4 三項原始值 (W)，後面再 ×0.001 轉 kW
        "L4_除霧電熱": (["L4_V_ab", "L4_I_a"], lambda d: d["L4_V_ab"] * d["L4_I_a"] * 1.0),
        "L4_冷凝風扇": (["L4_V_bc", "L4_I_b"], lambda d: d["L4_V_bc"] * d["L4_I_b"] * 0.83),
        "L4_蒸發風扇": (["L4_V_ab", "L4_I_c"], lambda d: d["L4_V_ab"] * d["L4_I_c"] * 1.0),
    }
    for new_col, (required_cols, formula) in derived.items():
        if all(c in df.columns for c in required_cols):
            numeric = {c: pd.to_numeric(df[c], errors='coerce') for c in required_cols}
            df[new_col] = formula(numeric)
        else:
            missing = [c for c in required_cols if c not in df.columns]
            st.warning(f"⚠️ 無法計算 `{new_col}`，缺少欄位：{missing}")

    # ── 步驟 1：L4 三項 ×0.001 轉換為 kW ────────────────────────────────
    for col in ["L4_除霧電熱", "L4_冷凝風扇", "L4_蒸發風扇"]:
        if col in df.columns:
            df[col] = df[col] * 0.001

    # ── 步驟 2：驗算用的冷庫總電 (kW) ─────────────────────────────────────
    comp_cols = {
        "壓縮機": "L2_kW_total (壓縮機總電)",
        "除霜":   "L3_kW_total (除霜電熱)",
        "除霧":   "L4_除霧電熱",
        "冷凝":   "L4_冷凝風扇",
        "蒸發":   "L4_蒸發風扇",
    }
    if all(v in df.columns for v in comp_cols.values()):
        df["驗算用的冷庫總電 (kW)"] = sum(df[c] for c in comp_cols.values())
    else:
        missing = [v for v in comp_cols.values() if v not in df.columns]
        st.warning(f"⚠️ 無法計算 `驗算用的冷庫總電`，缺少欄位：{missing}")

    # ── 步驟 3：總電誤差 % ────────────────────────────────────────────────
    total_col = "L1_kW_total (冷庫總電)"
    verify_col = "驗算用的冷庫總電 (kW)"
    if total_col in df.columns and verify_col in df.columns:
        df["總電誤差 (%)"] = (df[total_col] - df[verify_col]) / df[total_col] * 100
    else:
        st.warning("⚠️ 無法計算 `總電誤差 (%)`，缺少冷庫總電或驗算用的冷庫總電")

    # ── 步驟 4：冷庫總電差值 (kW) ────────────────────────────────────────
    if total_col in df.columns and verify_col in df.columns:
        df["冷庫總電差值 (kW)"] = df[total_col] - df[verify_col]
    else:
        st.warning("⚠️ 無法計算 `冷庫總電差值 (kW)`，缺少冷庫總電或驗算用的冷庫總電")

    # ── 步驟 5：各負載累積電能 kWh（梯形積分）────────────────────────────
    kwh_targets = {
        "L1_kW_total (冷庫總電)":    "冷庫總電 累積 (kWh)",
        "L2_kW_total (壓縮機總電)":  "壓縮機 累積 (kWh)",
        "L3_kW_total (除霜電熱)":    "除霜電熱 累積 (kWh)",
        "L4_除霧電熱":               "除霧耗電 累積 (kWh)",
        "L4_冷凝風扇":               "冷凝風扇耗電 累積 (kWh)",
        "L4_蒸發風扇":               "蒸發風扇耗電 累積 (kWh)",
    }
    t_hours = df.index.astype(np.int64) / 1e9 / 3600
    for src_col, new_col in kwh_targets.items():
        if src_col in df.columns:
            power = pd.to_numeric(df[src_col], errors='coerce').fillna(0).values
            dt = np.diff(t_hours.values)
            avg_p = (power[:-1] + power[1:]) / 2
            df[new_col] = np.concatenate([[0], np.cumsum(avg_p * dt)])

    return df

PRESETS_FILE = "presets.json"
if 'presets' not in st.session_state:
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                st.session_state.presets = json.load(f)
        except:
            st.session_state.presets = {"樣式 1": [], "樣式 2": [], "樣式 3": []}
    else:
        st.session_state.presets = {"樣式 1": [], "樣式 2": [], "樣式 3": []}

uploaded_files = st.file_uploader("請上傳 CSV 資料檔 (可多選)", type="csv", accept_multiple_files=True)

if uploaded_files:
    file_dict = {f.name: f for f in uploaded_files}
    
    st.sidebar.header("📁 檔案與圖表設定")
    
    selected_files = st.sidebar.multiselect(
        "0. 選擇要分析的檔案 (可選多天進行比對)", 
        list(file_dict.keys()), 
        default=list(file_dict.keys())
    )
    st.sidebar.markdown("---")
    
    if selected_files:
        dfs = {}
        all_columns = []
        min_time = pd.Timestamp.max
        max_time = pd.Timestamp.min
        
        for fname in selected_files:
            df = load_data(file_dict[fname])
            df = compute_derived_columns(df)
            dfs[fname] = df
            for col in df.columns:
                all_columns.append(f"{fname} - {col}")
                
            if df.index.min() < min_time: min_time = df.index.min()
            if df.index.max() > max_time: max_time = df.index.max()
                
        st.sidebar.subheader("💾 常用欄位樣式")
        preset_slot = st.sidebar.radio("選擇槽位", ["樣式 1", "樣式 2", "樣式 3"], horizontal=True, label_visibility="collapsed")
        p_col1, p_col2 = st.sidebar.columns(2)

        if p_col1.button("📥 載入樣式", use_container_width=True):
            saved_cols = st.session_state.presets.get(preset_slot, [])
            matched = [c for c in all_columns if c.split(" - ", 1)[1] in saved_cols]
            st.session_state.selected_cols = matched

        if p_col2.button("💾 儲存選項", use_container_width=True):
            current_sel = st.session_state.get('selected_cols', [])
            pure_cols = list(set([c.split(" - ", 1)[1] for c in current_sel]))
            st.session_state.presets[preset_slot] = pure_cols
            with open(PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state.presets, f, ensure_ascii=False)
            st.sidebar.success(f"已覆蓋儲存至 {preset_slot}！")
            
        st.sidebar.markdown("---")

        resample_rule = st.sidebar.selectbox(
            "1. 資料抽樣頻率",
            ["每 1 分鐘平均 (推薦)", "每 5 分鐘平均", "每 10 分鐘平均", "原始資料 (較耗效能)"],
            index=0 
        )
        
        rule_map = {
            "原始資料 (較耗效能)": None,
            "每 1 分鐘平均 (推薦)": "1min",
            "每 5 分鐘平均": "5min",
            "每 10 分鐘平均": "10min"
        }
        freq = rule_map[resample_rule]

        selected_options = st.sidebar.multiselect(
            "2. 選擇要比對的資料與欄位", 
            all_columns,
            key='selected_cols' 
        )
        
        plot_mode = st.sidebar.radio("3. 顯示模式", ["分開顯示 (逐列子圖)", "合併顯示 (畫在同一張圖)"])
        
        valid_options = [opt for opt in selected_options if opt.split(" - ", 1)[0] in dfs]
        
        y_auto_min, y_auto_max = 0.0, 500.0
        
        if valid_options:
            global_min = float('inf')
            global_max = float('-inf')
            
            for option in valid_options:
                file_name, col_name = option.split(" - ", 1)
                df = dfs[file_name]
                s = pd.to_numeric(df[col_name], errors='coerce')
                
                if not s.dropna().empty:
                    s_min = s.min()
                    s_max = s.max()
                    if s_min < global_min: global_min = s_min
                    if s_max > global_max: global_max = s_max
            
            if global_min != float('inf') and global_max != float('-inf'):
                margin = (global_max - global_min) * 0.05 if global_max != global_min else 10.0
                y_auto_min = float(global_min - margin)
                y_auto_max = float(global_max + margin)

        st.sidebar.markdown("---")
        st.sidebar.subheader("📏 座標軸進階設定")
        
        min_dt = min_time.to_pydatetime().replace(microsecond=0)
        max_dt = max_time.to_pydatetime().replace(microsecond=0)
        
        selected_time = st.sidebar.slider(
            "X 軸：選擇時間範圍",
            min_value=min_dt,
            max_value=max_dt,
            value=(min_dt, max_dt)
        )
        
        enable_y_axis = st.sidebar.checkbox("開啟手動設定 Y 軸上下限")
        if enable_y_axis:
            col1, col2 = st.sidebar.columns(2)
            y_min = col1.number_input("Y 軸下限", value=y_auto_min, step=10.0)
            y_max = col2.number_input("Y 軸上限", value=y_auto_max, step=10.0)
        
        # ==========================================
        # 分頁
        # ==========================================
        tab1, tab2 = st.tabs(["📊 互動圖表", "📋 日報分析"])

        # ── Tab 1：原本的互動圖表 ──────────────────────────────────────────
        with tab1:
            if valid_options:
                if len(valid_options) > 1:
                    safe_spacing = min(0.08, 0.8 / (len(valid_options) - 1))
                else:
                    safe_spacing = 0.0

                if plot_mode == "合併顯示 (畫在同一張圖)":
                    fig = go.Figure()
                else:
                    fig = make_subplots(
                        rows=len(valid_options), cols=1,
                        shared_xaxes=True,
                        subplot_titles=valid_options,
                        vertical_spacing=safe_spacing
                    )

                for i, option in enumerate(valid_options):
                    file_name, col_name = option.split(" - ", 1)
                    df = dfs[file_name]
                    s = pd.to_numeric(df[col_name], errors='coerce')
                    if freq is not None:
                        s = s.resample(freq).mean()
                    trace = go.Scatter(x=s.index, y=s, mode='lines', name=option, line=dict(width=1.5))
                    if plot_mode == "合併顯示 (畫在同一張圖)":
                        fig.add_trace(trace)
                    else:
                        fig.add_trace(trace, row=i+1, col=1)

                fig.update_xaxes(range=[selected_time[0], selected_time[1]], showticklabels=True, title_text="時間")
                if enable_y_axis:
                    fig.update_yaxes(range=[y_min, y_max])
                if plot_mode == "合併顯示 (畫在同一張圖)":
                    fig.update_layout(height=600, hovermode="x unified", dragmode="zoom")
                else:
                    fig.update_layout(height=300 * len(valid_options), hovermode="x unified", dragmode="zoom", showlegend=False)
                    fig.update_annotations(font_size=11, font_color="gray")
                st.plotly_chart(fig, width="stretch")

        # ── Tab 2：日報分析 ────────────────────────────────────────────────
        with tab2:
            # 各欄位對應的「累積 kWh 欄」
            kwh_map = {
                "冷庫總電":   "冷庫總電 累積 (kWh)",
                "壓縮機":     "壓縮機 累積 (kWh)",
                "除霜電熱":   "除霜電熱 累積 (kWh)",
                "除霧耗電":   "除霧耗電 累積 (kWh)",
                "冷凝風扇":   "冷凝風扇耗電 累積 (kWh)",
                "蒸發風扇":   "蒸發風扇耗電 累積 (kWh)",
            }
            verify_kwh_cols = ["壓縮機", "除霜電熱", "除霧耗電", "冷凝風扇", "蒸發風扇"]

            for fname in selected_files:
                df = dfs[fname]
                st.markdown(f"### 📄 {fname}")

                # ── 取每個欄的最後一筆（累積終點）= 全天 kWh ──
                day_kwh = {}
                for label, col in kwh_map.items():
                    if col in df.columns:
                        val = pd.to_numeric(df[col], errors='coerce').dropna()
                        day_kwh[label] = val.iloc[-1] if len(val) > 0 else 0.0
                    else:
                        day_kwh[label] = 0.0

                total_l1      = day_kwh.get("冷庫總電", 0.0)
                total_verify  = sum(day_kwh[k] for k in verify_kwh_cols)
                error_pct     = (total_l1 - total_verify) / total_l1 * 100 if total_l1 > 0 else 0.0

                # ── 資訊卡 ──
                c1, c2, c3 = st.columns(3)
                c1.metric("🔵 冷庫總電 (L1)", f"{total_l1:.2f} kWh")
                c2.metric("🟢 驗算總電 (各元件)", f"{total_verify:.2f} kWh")
                c3.metric("🟠 誤差", f"{error_pct:.2f} %")

                st.markdown("---")

                # ── 圓餅圖 + 明細表 ──
                pie_labels = verify_kwh_cols
                pie_values = [day_kwh[k] for k in pie_labels]

                col_pie, col_table = st.columns([1, 1])

                with col_pie:
                    fig_pie = go.Figure(go.Pie(
                        labels=pie_labels,
                        values=pie_values,
                        hole=0.35,
                        textinfo="label+percent",
                        hovertemplate="%{label}<br>%{value:.2f} kWh<br>%{percent}<extra></extra>"
                    ))
                    fig_pie.update_layout(
                        height=380,
                        margin=dict(t=30, b=10, l=10, r=10),
                        showlegend=False,
                        title=dict(text="各元件耗電佔比", x=0.5)
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col_table:
                    st.markdown("**各元件耗電明細**")
                    rows = []
                    for label in verify_kwh_cols:
                        kwh_val = day_kwh[label]
                        pct = kwh_val / total_verify * 100 if total_verify > 0 else 0.0
                        rows.append({"元件": label, "耗電 (kWh)": f"{kwh_val:.3f}", "佔比 (%)": f"{pct:.1f}%"})
                    rows.append({"元件": "─── 合計 ───", "耗電 (kWh)": f"{total_verify:.3f}", "佔比 (%)": "100.0%"})
                    st.dataframe(rows, use_container_width=True, hide_index=True)

                st.markdown("&nbsp;")  # 多檔案間距
    else:
        st.info("👈 檔案已上傳！請在左側選單中選擇要分析的檔案。")
else:
    st.info("👈 請先上傳檔案，並從左側選單開始操作。")