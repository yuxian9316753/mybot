import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 網頁配置 ---
st.set_page_config(page_title="台股 0050 全維度 AI 監測站", layout="wide")

# --- 2. 核心名單與指標計算 ---
STOCKS_0050 = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2882.TW", "2382.TW", "2412.TW",
    "2357.TW", "3711.TW", "2603.TW", "2891.TW", "2303.TW", "2886.TW", "2884.TW", "2892.TW",
    "1216.TW", "2880.TW", "2002.TW", "3008.TW", "2379.TW", "5880.TW", "2301.TW", "3034.TW",
    "2885.TW", "2327.TW", "2890.TW", "3231.TW", "4938.TW", "2408.TW", "2609.TW", "2615.TW",
    "1301.TW", "1303.TW", "5871.TW", "5876.TW", "2345.TW", "6669.TW", "3037.TW", "3045.TW",
    "2409.TW", "1326.TW", "2912.TW", "1101.TW", "2395.TW", "2883.TW", "4958.TW", "2354.TW",
    "1402.TW", "9910.TW", "009816.TW", "2610.TW", "2618.TW", "txff.TW", "pow00.TW"
]

def get_indicators(df):
    # MA 判斷 (5, 20, 60)
    df['5MA'] = df['Close'].rolling(5).mean()
    df['20MA'] = df['Close'].rolling(20).mean()
    df['60MA'] = df['Close'].rolling(60).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + gain/loss))
    
    # MACD (12, 26, 9)
    df['EMA12'] = df['Close'].ewm(span=12).mean()
    df['EMA26'] = df['Close'].ewm(span=26).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    
    # KD (9, 3)
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    
    # Bollinger Bands
    df['BB_Mid'] = df['Close'].rolling(20).mean()
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Up'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Low'] = df['BB_Mid'] - (df['BB_Std'] * 2)
    
    # 量能變化 (今日量 vs 5日均量)
    df['Vol_MA5'] = df['Volume'].rolling(5).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA5']
    
    return df

# --- 3. 核心診斷邏輯 ---
def analyze_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        if len(df) < 60: return None
        df = get_indicators(df)
        
        info = ticker.info
        curr_p = df['Close'].iloc[-1]
        
        # 市場恐慌指數 (VIX 濾網)
        vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
        
        # 評分系統 (基礎分 0)
        score = 0
        reasons = []

        # 1. MA 趨勢 (20分)
        if curr_p > df['20MA'].iloc[-1] > df['60MA'].iloc[-1]:
            score += 20; reasons.append("✅ 均線多頭排列")
        
        # 2. MACD (15分)
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]:
            score += 15; reasons.append("✅ MACD 黃金交叉")
            
        # 3. KD/RSI (15分)
        if df['K'].iloc[-1] < 30: 
            score += 15; reasons.append("🔥 KD 低檔超賣區轉強")
        elif df['RSI'].iloc[-1] < 70:
            score += 10; reasons.append("✅ RSI 位於健康區間")

        # 4. 布林位置 (10分)
        if df['BB_Mid'].iloc[-1] < curr_p < df['BB_Up'].iloc[-1]:
            score += 10; reasons.append("✅ 股價位於布林強勢通道")

        # 5. 量能與法人影子 (15分)
        if df['Vol_Ratio'].iloc[-1] > 1.3:
            score += 15; reasons.append("💎 量能異常爆發 (疑似法人進場)")

        # 6. 基本面 (25分)
        eps = info.get('trailingEps', 0)
        pe = info.get('trailingPE', 99)
        if eps > 0 and pe < 25:
            score += 25; reasons.append(f"💰 基本面穩健 (EPS:{eps}, PE:{pe})")

        # 7. VIX 市場修正 (扣分項)
        if vix > 25:
            score -= 20; reasons.append("⚠️ 市場恐慌情緒高 (VIX > 25)")

        return {
            "股名": info.get('shortName', symbol), "代碼": symbol, "現價": round(curr_p, 1),
            "評分": max(0, score), "診斷結果": reasons, "df": df, "VIX": round(vix, 1)
        }
    except: return None

# --- 4. UI 介面 ---
st.title("🏛️ 0050 全維度 AI 投資診斷系統 (2026 旗艦版)")
st.sidebar.header("📊 參數控制")
if st.sidebar.button("🚀 開始全指標掃描"):
    with st.spinner('AI 正在解構各項技術指標...'):
        results = [analyze_stock(s) for s in STOCKS_0050]
        results = [r for r in results if r]
        st.session_state['results'] = results

if 'results' in st.session_state:
    res_df = pd.DataFrame(st.session_state['results'])
    
    # --- 儀表板主表 ---
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("✅ 綜合建議買入清單")
        st.dataframe(res_df[res_df['評分'] >= 70].sort_values('評分', ascending=False)[['股名', '代碼', '現價', '評分']], use_container_width=True)
    
    with col2:
        st.subheader("⚠️ 高風險清單")
        st.dataframe(res_df[res_df['評分'] < 50][['股名', '代碼', '評分']], use_container_width=True)

    # --- AI 個股深度診斷 ---
    st.divider()
    st.header("🔬 個股 AI 深度診斷")
    selected_stock = st.selectbox("選擇一檔股票查看詳細診斷報告：", res_df['股名'].tolist())
    
    detail = next(x for x in st.session_state['results'] if x['股名'] == selected_stock)
    
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        st.metric("當前總分", f"{detail['評分']} 分")
        st.markdown("### 📝 AI 診斷分析：")
        for r in detail['診斷結果']:
            st.write(r)
    
    with d_col2:
        # 簡單 K 線與均線圖
        df_p = detail['df'].tail(60)
        fig = go.Figure(data=[go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線')])
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['20MA'], name='20MA', line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p['BB_Up'], name='布林上軌', line=dict(dash='dash', color='gray')))
        fig.update_layout(height=400, margin=dict(l=0, r=0, b=0, t=0))
        st.plotly_chart(fig, use_container_width=True)
