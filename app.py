import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool

# --- 1. 網頁基礎配置 ---
st.set_page_config(page_title="台股 0050 AI 旗艦管家", layout="wide")

# --- 2. 市場位階判定與自動門檻邏輯 ---
def get_market_context():
    """自動判斷大盤牛熊並給予門檻建議"""
    try:
        twii = yf.Ticker("^TWII").history(period="1y")
        curr_idx = twii['Close'].iloc[-1]
        ma240 = twii['Close'].rolling(240).mean().iloc[-1]
        
        if curr_idx > ma240 * 1.05:
            return 80, "🔥 多頭市場 (高門檻模式)", curr_idx
        elif curr_idx < ma240 * 0.95:
            return 55, "❄️ 空頭市場 (防禦模式)", curr_idx
        else:
            return 70, "☁️ 震盪市場 (標準模式)", curr_idx
    except:
        return 70, "⚠️ 無法取得大盤數據", 0

# --- 3. 核心技術指標運算 ---
def calculate_indicators(df):
    # MA 5, 20, 60
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain/loss))
    
    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    
    # KD (9, 3)
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    
    # Bollinger Bands
    df['BB_Mid'] = df['MA20']
    df['BB_Up'] = df['BB_Mid'] + (df['Close'].rolling(20).std() * 2)
    
    # 量能比 (今日量 / 5日均量)
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(5).mean()
    
    return df

# --- 4. 核心診斷與出場邏輯 ---
def analyze_stock(symbol, cost=None):
    try:
        ticker = yf.Ticker(symbol.strip().upper())
        df = ticker.history(period="1y")
        if len(df) < 60: return None
        df = calculate_indicators(df)
        
        info = ticker.info
        curr_p = df['Close'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        bb_up = df['BB_Up'].iloc[-1]
        
        # --- 評分系統 (總分100) ---
        score = 40
        diag = []
        if curr_p > ma20: score += 15; diag.append("✅ 站上月線")
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: score += 15; diag.append("✅ MACD交叉")
        if df['K'].iloc[-1] > df['D'].iloc[-1]: score += 10; diag.append("✅ KD低檔轉強")
        if df['Vol_Ratio'].iloc[-1] > 1.2: score += 10; diag.append("💎 量能爆發")
        if info.get('trailingEps', 0) > 0: score += 10; diag.append("💰 獲利股")

        # --- 出場驗證邏輯 ---
        tp, sl, status = "N/A", "N/A", "持有中"
        if cost:
            sl = max(cost * 0.93, ma20) # 止損：7% 或 跌破月線
            tp = max(cost * 1.20, bb_up) # 止盈：20% 或 觸及布林上軌
            if curr_p <= sl: status = "🛑 強制止損"
            elif curr_p >= tp: status = "💰 獲利入袋"
            elif curr_p < cost: status = "📉 套牢中"

        return {
            "股名": info.get('shortName', symbol), "代碼": symbol, "現價": round(curr_p, 1),
            "評分": score, "診斷內容": " | ".join(diag), "成本": cost,
            "目標止盈": round(tp, 1) if isinstance(tp, float) else tp,
            "防守止損": round(sl, 1) if isinstance(sl, float) else sl,
            "出場建議": status, "df": df
        }
    except: return None

# --- 5. UI 介面實作 ---
st.title("🏛️ 台股 0050 AI 智慧管家 (2026 旗艦版)")

# 側邊欄設定
st.sidebar.title("🤖 智慧管家設定")
auto_mode = st.sidebar.toggle("啟用自動門檻模式", value=True)
if auto_mode:
    threshold, status_text, _ = get_market_context()
    st.sidebar.info(f"大盤狀態：{status_text}\n當前門檻：{threshold}")
else:
    threshold = st.sidebar.slider("手動買進門檻", 50, 90, 70)

st.sidebar.divider()
st.sidebar.subheader("💼 我的持股驗證")
portfolio_raw = st.sidebar.text_area("持股清單 (代碼,成本)", "2330.TW,950\n2317.TW,180")
run_btn = st.sidebar.button("🚀 執行全方位掃描")

# 主畫面渲染
if run_btn:
    STOCKS_0050 = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2882.TW", "2382.TW", "2412.TW", "2357.TW", "3711.TW", "2603.TW", "2891.TW", "2303.TW", "2886.TW", "2884.TW", "2892.TW", "1216.TW", "2880.TW", "2002.TW", "3008.TW", "2379.TW", "5880.TW", "2301.TW", "3034.TW", "2885.TW", "2327.TW", "2890.TW", "3231.TW", "4938.TW", "2408.TW", "2609.TW", "2615.TW", "1301.TW", "1303.TW", "5871.TW", "5876.TW", "2345.TW", "6669.TW", "3037.TW", "3045.TW", "2409.TW", "1326.TW", "2912.TW", "1101.TW", "2395.TW", "2883.TW", "4958.TW", "2354.TW", "1402.TW", "9910.TW"]
    
    with st.spinner('AI 正在同步 Yahoo Finance 數據...'):
        pool = ThreadPool(10)
        all_data = pool.map(analyze_stock, STOCKS_0050)
        res_df = pd.DataFrame([r for r in all_data if r])

    # 1. 建議買入清單 (一列排版)
    st.subheader(f"✅ AI 建議買入清單 (門檻 {threshold} 分)")
    buy_df = res_df[res_df['評分'] >= threshold].sort_values('評分', ascending=False)
    st.dataframe(buy_df[['股名', '代碼', '現價', '評分', '診斷內容']], use_container_width=True, hide_index=True)

    # 2. 持股驗證報告
    st.divider()
    st.subheader("💼 我的持股損益與出場驗證")
    my_results = []
    for line in portfolio_raw.split('\n'):
        if ',' in line:
            sym, c = line.split(',')
            r = analyze_stock(sym, float(c))
            if r: my_results.append(r)
    
    if my_results:
        my_df = pd.DataFrame(my_results)
        st.dataframe(my_df[['股名', '代碼', '現價', '成本', '目標止盈', '防守止損', '出場建議', '評分']], use_container_width=True, hide_index=True)
    
    # 3. 個股深度 K 線分析
    st.divider()
    st.subheader("🔬 個股深度趨勢分析")
    target = st.selectbox("選擇股票：", res_df['股名'].tolist())
    stock_detail = next(x for x in all_data if x and x['股名'] == target)
    df_p = stock_detail['df'].tail(60)
    
    fig = go.Figure(data=[go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線')])
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MA20'], name='月線(MA20)', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df_p.index, y=df_p['BB_Up'], name='布林上軌', line=dict(dash='dash', color='gray')))
    fig.update_layout(height=500, margin=dict(l=0, r=0, b=0, t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("💡 點擊左側按鈕開始掃描。數據來源：Yahoo Finance (延遲約15分鐘)。")
