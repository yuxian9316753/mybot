import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt # 修正報錯點
from datetime import datetime

# --- 頁面配置 ---
st.set_page_config(page_title="台股自動化驗證系統", layout="wide")

# --- 核心數據：0050 名單 ---
STOCKS_0050 = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2882.TW", "2382.TW", "2412.TW", 
    "2357.TW", "3711.TW", "2603.TW", "2891.TW", "2303.TW", "2886.TW", "2884.TW", "2892.TW", 
    "1216.TW", "2880.TW", "2002.TW", "3008.TW", "2379.TW", "5880.TW", "2301.TW", "3034.TW", 
    "2885.TW", "2327.TW", "2890.TW", "3231.TW", "4938.TW", "2408.TW", "2609.TW", "2615.TW", 
    "1301.TW", "1303.TW", "5871.TW", "5876.TW", "2345.TW", "6669.TW", "3037.TW", "3045.TW", 
    "2409.TW", "1326.TW", "2912.TW", "1101.TW", "2395.TW", "2883.TW", "4958.TW", "2354.TW", 
    "1402.TW", "9910.TW"
]

# --- 側邊欄設定 ---
st.sidebar.title("🤖 自動化資料庫")
my_stocks = st.sidebar.text_input("輸入已購入代碼 (例如: 2330.TW, 2317.TW)", "").split(',')
run_scan = st.sidebar.button("🚀 開始每日掃描與驗證")

def get_perf(price, ma):
    if price > ma * 1.05: return "強"
    if price > ma * 0.95: return "中"
    return "弱"

def analyze_stock(symbol):
    ticker = yf.Ticker(symbol.strip())
    df = ticker.history(period="2y")
    if len(df) < 240: return None
    
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA240'] = df['Close'].rolling(240).mean()
    
    curr_p = df['Close'].iloc[-1]
    ma60 = df['MA60'].iloc[-1]
    ma240 = df['MA240'].iloc[-1]
    info = ticker.info
    eps = info.get('trailingEps', 0)
    
    # 評分與邏輯
    score = 60
    if curr_p > ma60 > ma240: score += 20
    if eps > 0: score += 20
    
    # 行動建議
    if curr_p > ma240 and eps > 0:
        action = "🚀 強勢買進" if score >= 90 else "📈 擇優布局"
        is_buy = True
    else:
        action = "🛑 立即出清" if eps <= 0 else "⚠️ 減碼觀望"
        is_buy = False

    return {
        "股名": info.get('shortName', symbol),
        "代碼": symbol,
        "EPS": eps,
        "當前價格": round(curr_p, 1),
        "建議賣出價": round(curr_p * 1.15, 1),
        "年線表現": get_perf(curr_p, ma240),
        "季線表現": get_perf(curr_p, ma60),
        "評分": score,
        "採取行動": action,
        "is_buy": is_buy
    }

# --- 網頁主視覺 ---
st.title("📊 0050 自動化投資分析與驗證")
st.write(f"最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

if run_scan:
    results = []
    # 掃描 0050
    with st.spinner('正在分析全成份股...'):
        for s in STOCKS_0050:
            data = analyze_stock(s)
            if data: results.append(data)
    
    all_df = pd.DataFrame(results)

    # --- 1. 建議買入 (對應草圖 1) ---
    st.header("🟢 建議買入清單 (趨勢走強股)")
    buy_df = all_df[all_df['is_buy'] == True].sort_values('評分', ascending=False)
    # 完美補齊：股名、代碼、EPS、價格、建議賣出、年線表現、季線表現、評分、採取行動
    st.dataframe(buy_df[['股名', '代碼', 'EPS', '當前價格', '建議賣出價', '年線表現', '季線表現', '評分', '採取行動']].style.background_gradient(subset=['評分'], cmap='RdYlGn'), use_container_width=True)

    # --- 2. 建議賣出 / 風險 (對應草圖 2) ---
    st.header("🔴 建議賣出 / 風險清單 (趨勢轉弱股)")
    risk_df = all_df[all_df['is_buy'] == False]
    # 完美補齊：股名、代碼、EPS、價格、風險警示(年線表現)、年線表現、季線表現、建議動作(採取行動)
    st.dataframe(risk_df[['股名', '代碼', 'EPS', '當前價格', '年線表現', '季線表現', '採取行動']], use_container_width=True)

    # --- 3. 自動化驗證 (針對你輸入的股票) ---
    if my_stocks != ['']:
        st.divider()
        st.header("💼 我的持股驗證報表")
        my_results = [analyze_stock(s) for s in my_stocks if s.strip()]
        my_df = pd.DataFrame([r for r in my_results if r])
        st.table(my_df[['股名', '代碼', '當前價格', '採取行動', '評分']])

else:
    st.info("💡 請在左側輸入你想驗證的股票，並點擊掃描按鈕。")