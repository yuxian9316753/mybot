import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool

# --- 1. 網頁基礎配置 ---
st.set_page_config(page_title="台股 2026 AI 旗艦智報", layout="wide")

# --- 2. 市場位階判定 (自動偵測牛熊並調整進場嚴格度) ---
def get_market_context():
    """自動判斷大盤狀態並給予門檻建議"""
    try:
        twii = yf.Ticker("^TWII").history(period="1y")
        if twii.empty: return 75, "⚠️ 數據延遲", 0
        curr_idx = twii['Close'].iloc[-1]
        ma240 = twii['Close'].rolling(240).mean().iloc[-1] # 年線基準
        
        # 邏輯：多頭時機會多(門檻65)；空頭時需嚴格過濾以防接刀(門檻85)
        if curr_idx > ma240 * 1.05:
            return 65, "🔥 多頭市場 (順勢模式)", curr_idx
        elif curr_idx < ma240 * 0.95:
            return 85, "❄️ 空頭市場 (防禦模式)", curr_idx
        else:
            return 75, "☁️ 震盪市場 (標準模式)", curr_idx
    except:
        return 75, "⚠️ 取得失敗", 0

# --- 3. 核心技術指標運算 (RSI, MACD, KD, Bollinger, Vol) ---
def calculate_indicators(df):
    # MA 均線
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    # MACD (12, 26, 9)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # KD (9, 3, 3)
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    # 布林通道 (Bollinger Bands)
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Up'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Low'] = df['BB_Mid'] - (df['BB_Std'] * 2)
    
    # 量能比 (Vol_Ratio)
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(5).mean().replace(0, np.nan)
    return df

# --- 4. 核心診斷與權重評分系統 ---
def analyze_stock(symbol, cost=None):
    try:
        symbol = symbol.strip().upper()
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        if df.empty or len(df) < 60: return None # 確保有足夠資料計算 MA60
        
        df = calculate_indicators(df)
        info = ticker.info
        curr_p = df['Close'].iloc[-1]
        
        # --- 動態評分系統 (100分制) ---
        score = 0
        diag = []
        
        # 1. 趨勢權重 (40分)
        if curr_p > df['MA20'].iloc[-1]: 
            score += 25; diag.append("📈 月線上")
        if curr_p > df['MA60'].iloc[-1]: 
            score += 15; diag.append("🏛️ 季線上")
            
        # 2. 動能權重 (30分)
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: 
            score += 15; diag.append("🚀 MACD金叉")
        if df['K'].iloc[-1] > df['D'].iloc[-1]: 
            score += 15; diag.append("⚡ KD金叉")
            
        # 3. 逆勢與超買修正 (10分)
        rsi = df['RSI'].iloc[-1]
        if rsi < 30: 
            score += 10; diag.append("💎 RSI超賣(低接訊號)")
        elif rsi > 75: 
            score -= 10; diag.append("⚠️ RSI過熱(追高風險)")
            
        # 4. 量能與基本面 (20分)
        if df['Vol_Ratio'].iloc[-1] > 1.5: 
            score += 10; diag.append("🔥 帶量攻擊")
        if info.get('trailingEps', 0) > 0: 
            score += 10; diag.append("💰 獲利公司")

        # --- 進場/持有狀態驗證 ---
        status = "觀察中"
        sl = "N/A"
        tp = "N/A"
        
        if cost:
            # 專業移動停損：取 [成本*0.93] 與 [月線*0.98] 較大值
            sl = max(cost * 0.93, df['MA20'].iloc[-1] * 0.98)
            tp = df['BB_Up'].iloc[-1] # 停利參考布林上軌
            
            if curr_p <= sl: status = "🛑 建議停損"
            elif curr_p >= tp: status = "💰 建議獲利"
            elif curr_p < cost: status = "📉 套牢觀察"
            else: status = "✅ 持續持有"

        return {
            "股名": info.get('shortName', symbol), "代碼": symbol, "現價": round(curr_p, 2),
            "評分": score, "診斷": " | ".join(diag), "df": df, "成本": cost, 
            "狀態": status, "新聞": ticker.news[:3], "RSI": round(rsi, 1),
            "停損點": round(sl, 2) if isinstance(sl, float) else sl,
            "停利點": round(tp, 2) if isinstance(tp, float) else tp
        }
    except Exception as e:
        return None

# --- 5. UI 介面架構 ---
st.sidebar.title("🤖 2026 AI 旗艦導航")
search_symbol = st.sidebar.text_input("🔍 個股即時診斷 (例如: 2330.TW)", "").upper()

st.sidebar.divider()
auto_mode = st.sidebar.toggle("啟用市場動態門檻", value=True)
threshold, market_status, m_idx = get_market_context() if auto_mode else (st.sidebar.slider("手動門檻", 50, 95, 75), "手動模式", 0)

if auto_mode:
    st.sidebar.info(f"大盤指數：{int(m_idx)}\n狀態：{market_status}\n進場標準：{threshold} 分")

st.sidebar.divider()
portfolio_raw = st.sidebar.text_area("💼 持股成本驗證 (代碼,成本)", "2330.TW,950\n2317.TW,180")
run_scan = st.sidebar.button("🚀 執行 0050 全清單掃描")

# A. 個股詳情診斷
if search_symbol:
    with st.spinner('正在獲取最新資料...'):
        res = analyze_stock(search_symbol)
        
    if res:
        st.header(f"📊 {res['股名']} ({search_symbol}) AI 深度報告")
        c1, c2, c3 = st.columns(3)
        c1.metric("當前現價", f"{res['現價']} 元")
        c2.metric("趨勢總分", f"{res['評分']} / 100")
        c3.info(f"**診斷結論：**\n{res['診斷']}")

        # 畫圖邏輯 (K線 + MA20 + 布林)
        df_p = res['df'].tail(80)
        fig = go.Figure(data=[
            go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'),
            go.Scatter(x=df_p.index, y=df_p['MA20'], name='月線(MA20)', line=dict(color='orange', width=2)),
            go.Scatter(x=df_p.index, y=df_p['BB_Up'], name='布林上軌', line=dict(color='rgba(128,128,128,0.5)', dash='dash'))
        ])
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=30))
        st.plotly_chart(fig, use_container_width=True)
        
        # 新聞摘要
        if res['新聞']:
            st.subheader("📰 最新相關新聞")
            for item in res['新聞']:
                st.markdown(f"[{item['title']}]({item['link']})")
    else: 
        st.error("查無資料，請確認代碼格式 (如 2330.TW)。")

# B. 全清單掃描與驗證
if run_scan:
    STOCKS_0050 = [
        "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2882.TW", "2382.TW", "2412.TW",
        "2357.TW", "3711.TW", "2603.TW", "2891.TW", "2303.TW", "2886.TW", "2884.TW", "2892.TW",
        "1216.TW", "2880.TW", "2002.TW", "3008.TW", "2379.TW", "5880.TW", "2301.TW", "3034.TW",
        "2885.TW", "2327.TW", "2890.TW", "3231.TW", "4938.TW", "2408.TW", "2609.TW", "2615.TW",
        "1301.TW", "1303.TW", "5871.TW", "5876.TW", "2345.TW", "6669.TW", "3037.TW", "3045.TW",
        "2409.TW", "1326.TW", "2912.TW", "1101.TW", "2395.TW", "2883.TW", "4958.TW", "2354.TW",
        "1402.TW", "9910.TW", "2610.TW", "2618.TW" # 已排除無效代碼
    ]
    
    with st.spinner('AI 正在計算成分股數據...'):
        pool = ThreadPool(12) 
        all_res = [r for r in pool.map(analyze_stock, STOCKS_0050) if r]
        
    if all_res:
        res_df = pd.DataFrame(all_res).sort_values(by="評分", ascending=False)
        
        st.subheader(f"🎯 AI 推薦進場清單 (得分 >= {threshold})")
        pick_df = res_df[res_df['評分'] >= threshold][['股名', '代碼', '現價', '評分', '診斷']]
        if not pick_df.empty:
            st.dataframe(pick_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"目前無股票達到 {threshold} 分門檻。")

        st.divider()
        st.subheader("💼 我的持股損益與出場預警")
        my_list = []
        for line in portfolio_raw.split('\n'):
            if ',' in line:
                try:
                    s, c = line.split(',')
                    r = analyze_stock(s.strip(), float(c.strip()))
                    if r: my_list.append(r)
                except: continue
                
        if my_list:
            my_df = pd.DataFrame(my_list)[['股名', '代碼', '成本', '現價', '停利點', '停損點', '狀態', '評分']]
            st.dataframe(my_df, use_container_width=True, hide_index=True)
        else: 
            st.info("尚未輸入有效的持股資料。")
    else:
        st.error("網路連線異常，無法取得股票數據。")

elif not search_symbol:
    st.warning(f"👈 請點擊左側「執行掃描」來獲取 {datetime.now().strftime('%Y/%m/%d')} 的最新市場解析。")
