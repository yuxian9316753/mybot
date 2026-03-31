import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool

# --- 1. 網頁基礎配置 ---
st.set_page_config(page_title="台股 0050 AI 投資管家 (終極智報版)", layout="wide")

# --- 2. 市場位階判定與自動門檻邏輯 ---
def get_market_context():
    """自動判斷大盤牛熊並給予門檻建議"""
    try:
        twii = yf.Ticker("^TWII").history(period="1y")
        if twii.empty: return 70, "⚠️ 數據延遲", 0
        curr_idx = twii['Close'].iloc[-1]
        ma240 = twii['Close'].rolling(240).mean().iloc[-1]
        
        if curr_idx > ma240 * 1.05:
            return 80, "🔥 多頭市場 (高門檻模式)", curr_idx
        elif curr_idx < ma240 * 0.95:
            return 55, "❄️ 空頭市場 (防禦模式)", curr_idx
        else:
            return 70, "☁️ 震盪市場 (標準模式)", curr_idx
    except:
        return 70, "⚠️ 取得失敗", 0

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
    df['RSI'] = 100 - (100 / (1 + (gain/loss.replace(0, np.nan))))
    
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
    
    # 量能比
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(5).mean().replace(0, np.nan)
    return df

# --- 4. 核心診斷與新聞摘要邏輯 ---
def analyze_stock(symbol, cost=None):
    try:
        symbol = symbol.strip().upper()
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        if df.empty or len(df) < 60: return None
        
        df = calculate_indicators(df)
        info = ticker.info
        curr_p = df['Close'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        bb_up = df['BB_Up'].iloc[-1]
        
        # 評分系統
        score = 40
        diag = []
        if curr_p > ma20: score += 20; diag.append("✅ 站上月線")
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: score += 20; diag.append("✅ MACD金叉")
        if info.get('trailingEps', 0) > 0: score += 20; diag.append("💰 獲利公司")
        
        # 出場驗證
        status = "持有中"
        if cost:
            sl = max(cost * 0.93, ma20)
            tp = max(cost * 1.20, bb_up)
            if curr_p <= sl: status = "🛑 強制止損"
            elif curr_p >= tp: status = "💰 獲利入袋"
            elif curr_p < cost: status = "📉 套牢中"

        return {
            "股名": info.get('shortName', symbol), "代碼": symbol, "現價": round(curr_p, 1),
            "評分": score, "診斷": " | ".join(diag), "df": df, "成本": cost, 
            "狀態": status, "新聞": ticker.news[:5]
        }
    except: return None

# --- 5. UI 介面 ---
st.sidebar.title("🤖 投資管家設定")
search_symbol = st.sidebar.text_input("🔍 個股即時快搜 (如: 2330.TW)", "").upper()

st.sidebar.divider()
auto_mode = st.sidebar.toggle("啟用自動門檻", value=True)
threshold, market_status, _ = get_market_context() if auto_mode else (st.sidebar.slider("手動門檻", 50, 90, 70), "手動模式", 0)

if auto_mode:
    st.sidebar.info(f"市場狀態：{market_status}\n當前門檻：{threshold}")

st.sidebar.divider()
portfolio_raw = st.sidebar.text_area("💼 持股驗證 (代碼,成本)", "2330.TW,950")
run_scan = st.sidebar.button("🚀 執行 0050 全掃描")

# A. 個股快搜診斷 (含 AI 新聞摘要)
if search_symbol:
    res = analyze_stock(search_symbol)
    if res:
        st.header(f"🔎 {res['股名']} ({search_symbol}) AI 深度診斷")
        col1, col2, col3 = st.columns(3)
        col1.metric("當前現價", f"{res['現價']} 元")
        col2.metric("趨勢評分", f"{res['評分']} 分")
        col3.success(f"**診斷結論：**\n{res['診斷']}")

        c_chart, c_news = st.columns([1.8, 1.2])
        with c_chart:
            st.subheader("📈 趨勢走勢圖")
            df_p = res['df'].tail(60)
            fig = go.Figure(data=[go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線')])
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p['MA20'], name='月線', line=dict(color='orange')))
            fig.update_layout(height=500, margin=dict(l=0, r=0, b=0, t=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with c_news:
            st.subheader("📰 AI 新聞智慧摘要")
            if res['新聞']:
                for item in res['新聞']:
                    pub_time = datetime.fromtimestamp(item['providerPublishTime']).strftime('%m/%d')
                    sentiment = "💡 中性"
                    if any(w in item['title'] for w in ['漲', '高', '利', '創', '增']): sentiment = "🚀 利多"
                    elif any(w in item['title'] for w in ['跌', '降', '災', '減', '壓']): sentiment = "⚠️ 警訊"
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.markdown(f"> **AI 速讀：** {sentiment} | {item['publisher']} ({pub_time})")
                    st.write("---")
    else: st.error("查無代碼，請確認格式。")

# B. 全掃描與驗證
if run_scan:
    st.divider()
    STOCKS_0050 = ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2882.TW", "2382.TW", "2412.TW", "2357.TW", "3711.TW", "2603.TW", "2891.TW", "2303.TW", "2886.TW", "2884.TW", "2892.TW", "1216.TW", "2880.TW", "2002.TW", "3008.TW", "2379.TW", "5880.TW", "2301.TW", "3034.TW", "2885.TW", "2327.TW", "2890.TW", "3231.TW", "4938.TW", "2408.TW", "2609.TW", "2615.TW", "1301.TW", "1303.TW", "5871.TW", "5876.TW", "2345.TW", "6669.TW", "3037.TW", "3045.TW", "2409.TW", "1326.TW", "2912.TW", "1101.TW", "2395.TW", "2883.TW", "4958.TW", "2354.TW", "1402.TW", "9910.TW"]
    with st.spinner('正在分析 50 檔成分股...'):
        pool = ThreadPool(10)
        all_res = [r for r in pool.map(analyze_stock, STOCKS_0050) if r]
        res_df = pd.DataFrame(all_res)
    
    st.header(f"✅ 建議買入清單 (門檻 {threshold})")
    st.dataframe(res_df[res_df['評分'] >= threshold][['股名', '代碼', '現價', '評分', '診斷']], use_container_width=True, hide_index=True)

    st.divider()
    st.header("💼 持股損益與出場驗證")
    my_list = []
    for line in portfolio_raw.split('\n'):
        if ',' in line:
            s, c = line.split(',')
            r = analyze_stock(s, float(c))
            if r: my_list.append(r)
    if my_list:
        st.dataframe(pd.DataFrame(my_list)[['股名', '代碼', '成本', '現價', '狀態', '評分']], use_container_width=True, hide_index=True)

elif not search_symbol:
    st.info("💡 歡迎使用 2026 AI 旗艦版。請在左側搜尋個股或執行全掃描。")
