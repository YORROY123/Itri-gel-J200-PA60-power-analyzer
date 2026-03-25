# ⚡ ItriGel J200 PA60 互動式電力數據比對工具

一個基於 Streamlit 的互動式電力數據視覺化分析工具，支援多日 CSV 資料比對、衍生欄位計算與圖表匯出。

🔗 **線上使用**：[開啟 App](https://itri-gel-j200-pa60-power-analyzer-jwv8hmk6mvbke8ouxtzpfq.streamlit.app/)

---

## ✨ 功能特色

- 📂 支援多檔 CSV 同時上傳比對（多日資料）
- 📊 互動式 Plotly 圖表，支援縮放、Hover 查看數值
- 🔀 分開顯示（子圖）或合併顯示（同一張圖）
- ⏱️ 資料抽樣頻率可調（1 / 5 / 10 分鐘平均）
- 📏 X 軸時間範圍滑桿、Y 軸手動上下限設定
- 💾 最多 3 組常用欄位樣式儲存與載入
- 🔢 自動計算衍生欄位：
  - `L1_kW_total`（冷庫總電）
  - `L2_kW_total`（壓縮機總電）
  - `L3_kW_total`（除霜電熱）
  - `L4_除霧電熱`、`L4_冷凝風扇`、`L4_蒸發風扇`

---

## 🚀 本機執行

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## 📁 檔案說明

```
📂 repo/
├── app.py            ← 主程式
├── presets.json      ← 預存欄位樣式
├── requirements.txt  ← 套件清單
├── CITATION.cff      ← 學術引用資訊
└── LICENSE           ← MIT License
```

---

## 📦 使用套件

- [Streamlit](https://streamlit.io/)
- [Plotly](https://plotly.com/python/)
- [Pandas](https://pandas.pydata.org/)

---

## 📜 授權

本專案採用 [MIT License](LICENSE)。  
使用或修改時請保留原作者聲明。

```
Copyright (c) 2026 YORROY123
```

---

## 📖 引用

如果你在研究或專案中使用了本工具，歡迎引用：

```
YORROY123 (2026). ItriGel J200 PA60 互動式電力數據比對工具.
GitHub: https://github.com/YORROY123/Itri-gel-J200-PA60-power-analyzer
```

---

<p align="center">Made with ❤️ by <a href="https://github.com/YORROY123">YORROY123</a></p>
