import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time
from multiprocessing.dummy import Pool as ThreadPool

# --- 1. 網頁基礎配置 ---
st.set_page_config(page_title="台股 2026 AI 旗艦智報", layout="wide")

# --- 2. 市場位階判定 (自動大盤判斷與門檻調整) ---
def get_market_context():
    try:
        twii = yf.Ticker("^TWII").history(period="1y")
        if twii.empty: return 75, "⚠️ 數據延遲", 0
        curr_idx = twii['Close'].iloc[-1]
        ma240 = twii['Close'].rolling(240).mean().iloc[-1]
        
        if curr_idx > ma240 * 1.05:
            return 65, "🔥 多頭市場 (順勢模式)", curr_idx
        elif curr_idx < ma240 * 0.95:
            return 85, "❄️ 空頭市場 (防禦模式)", curr_idx
        else:
            return 75, "☁️ 震盪市場 (標準模式)", curr_idx
    except:
        return 75, "⚠️ 取得大盤失敗", 0

# --- 3. 核心技術指標運算 (涵蓋各項關鍵技術指標) ---
def calculate_indicators(df):
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))
    
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    low_min = df['Low'].rolling(9).min()
    high_max = df['High'].rolling(9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Up'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Low'] = df['BB_Mid'] - (df['BB_Std'] * 2)
    
    df['Vol_Ratio'] = df['Volume'] / df['Volume'].rolling(5).mean().replace(0, np.nan)
    return df

# --- 4. 核心診斷與權重評分系統 (優劣勢雙向診斷版) ---
def analyze_stock(symbol, cost=None):
    try:
        symbol = symbol.strip().upper()
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        if df.empty or len(df) < 60: return None 
        
        df = calculate_indicators(df)
        info = ticker.info
        curr_p = df['Close'].iloc[-1]
        
        # 取得實際數值
        ma20_val = round(df['MA20'].iloc[-1], 1)
        rsi_val = round(df['RSI'].iloc[-1], 1)
        vol_ratio = round(df['Vol_Ratio'].iloc[-1], 2)
        k_val = round(df['K'].iloc[-1], 1)
        macd_val = round(df['MACD'].iloc[-1], 2)
        eps = info.get('trailingEps', 0)
        
        # --- 動態評分與優劣勢分析 ---
        score = 0
        diag_pos = [] # 優勢
        diag_neg = [] # 劣勢
        
        # 月線
        ma20_status = "📉 跌破"
        if curr_p > df['MA20'].iloc[-1]: 
            score += 25; ma20_status = f"📈 站上({ma20_val})"; diag_pos.append("站上月線")
        else: diag_neg.append("跌破月線")
            
        # 季線
        ma60_status = "⚠️ 弱勢"
        if curr_p > df['MA60'].iloc[-1]: 
            score += 15; ma60_status = "🏛️ 多頭"; diag_pos.append("季線支撐")
        else: diag_neg.append("跌破季線")
            
        # MACD
        macd_status = "死叉"
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: 
            score += 15; macd_status = f"🚀 金叉({macd_val})"; diag_pos.append("MACD翻紅")
        else: diag_neg.append("MACD死叉")
            
        # KD
        kd_status = "死叉"
        if df['K'].iloc[-1] > df['D'].iloc[-1]: 
            score += 15; kd_status = f"⚡ 金叉({k_val})"; diag_pos.append("KD走強")
        else: diag_neg.append("KD走弱")
            
        # RSI
        if rsi_val < 30: 
            score += 10; diag_pos.append("RSI超賣(低接區)")
        elif rsi_val > 75: 
            score -= 10; diag_neg.append("RSI過熱(追高風險)")
            
        # 量能
        vol_status = "正常"
        if vol_ratio > 1.5: 
            score += 10; vol_status = f"🔥 {vol_ratio}倍"; diag_pos.append("帶量攻擊")
        elif vol_ratio < 0.6:
            diag_neg.append("量能萎縮")
        
        # 基本面
        eps_status = "無"
        if eps and eps > 0: 
            score += 10; eps_status = f"💰 {eps}"; diag_pos.append("具基本面(獲利)")
        else: diag_neg.append("基本面偏弱")

        action = "🚀 強力買進" if score >= 80 else ("📈 偏多佈局" if score >= 65 else "🟡 觀望等待")

        # --- 持股狀態 ---
        status = "未持有"
        sl = tp = "N/A"
        if cost:
            sl = max(cost * 0.93, df['MA20'].iloc[-1] * 0.98)
            tp = df['BB_Up'].iloc[-1] 
            if curr_p <= sl: status = "🛑 建議停損"
            elif curr_p >= tp: status = "💰 建議獲利"
            elif curr_p < cost: status = "📉 套牢觀察"
            else: status = "✅ 持續持有"

        raw_name = info.get('shortName') or symbol
        short_name = raw_name[:12] + '..' if len(raw_name) > 12 else raw_name

        return {
            "股名": short_name, "代碼": symbol, "現價": round(curr_p, 2), "評分": score, 
            "行動": action, "月線": ma20_status, "季線": ma60_status, "MACD": macd_status, 
            "KD": kd_status, "RSI": round(rsi_val, 1), "量能": vol_status, "EPS": eps_status,
            "優勢": diag_pos, "劣勢": diag_neg, 
            "df": df, "成本": cost, "狀態": status, "新聞": ticker.news[:5],
            "停損點": round(sl, 2) if isinstance(sl, float) else sl, "停利點": round(tp, 2) if isinstance(tp, float) else tp
        }
    except Exception as e: return None

# --- 5. UI 介面架構 ---
st.sidebar.title("🤖 2026 AI 旗艦導航")
search_symbol = st.sidebar.text_input("🔍 個股即時診斷 (例如: 2603.TW)", "").upper()

st.sidebar.divider()
auto_mode = st.sidebar.toggle("啟用市場動態門檻", value=True)
threshold, market_status, m_idx = get_market_context() if auto_mode else (st.sidebar.slider("手動門檻", 50, 95, 75), "手動模式", 0)

if auto_mode: st.sidebar.info(f"大盤指數：{int(m_idx)}\n狀態：{market_status}\n進場標準：{threshold} 分")

st.sidebar.divider()
portfolio_raw = st.sidebar.text_area("💼 持股成本驗證 (代碼,成本)", "2330.TW,950\n2317.TW,180")
run_scan = st.sidebar.button("🚀 執行 0050 全清單掃描")

# ==========================================
# A. 個股詳情診斷 (含優劣勢解析與新聞備援)
# ==========================================
if search_symbol:
    with st.spinner('正在獲取最新資料與新聞...'):
        res = analyze_stock(search_symbol)
        
    if res:
        st.header(f"📊 {res['股名']} ({search_symbol}) AI 深度報告")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前現價", f"{res['現價']} 元")
        c2.metric("趨勢總分", f"{res['評分']} / 100")
        c3.metric("AI 建議行動", f"{res['行動']}")
        c4.metric("量能變化", f"{res['量能']}")
        
        # 明確列出多空優劣勢
        st.success(f"**✅ 多方優勢：** {', '.join(res['優勢']) if res['優勢'] else '無明顯多方訊號'}")
        st.error(f"**⚠️ 空方弱勢：** {', '.join(res['劣勢']) if res['劣勢'] else '無明顯空方訊號'}")

        c_chart, c_news = st.columns([1.8, 1.2])
        with c_chart:
            df_p = res['df'].tail(80)
            fig = go.Figure(data=[
                go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'], name='K線'),
                go.Scatter(x=df_p.index, y=df_p['MA20'], name='月線(MA20)', line=dict(color='orange', width=2)),
                go.Scatter(x=df_p.index, y=df_p['BB_Up'], name='布林上軌', line=dict(color='rgba(128,128,128,0.5)', dash='dash'))
            ])
            fig.update_layout(height=450, xaxis_rangeslider_visible=False, margin=dict(t=30))
            st.plotly_chart(fig, use_container_width=True)
        
        # 新聞與 Google 備援
        with c_news:
            st.subheader("📰 相關新聞與動態")
            if res['新聞']:
                st.caption("以下為 Yahoo 財經英文原文：")
                for item in res['新聞']:
                    pub_time = datetime.fromtimestamp(item.get('providerPublishTime', time.time())).strftime('%m/%d')
                    sentiment = "💡 中性"
                    title = item.get('title', '')
                    if any(w in title for w in ['漲', '高', '利', '創', '增', '多', '買', '強', '飆', 'Up', 'Growth']): sentiment = "🚀 利多"
                    elif any(w in title for w in ['跌', '降', '災', '減', '壓', '空', '賣', '損', '弱', '逃', 'Down', 'Loss']): sentiment = "⚠️ 警訊"
                        
                    st.markdown(f"🔗 **[{title}]({item.get('link', '#')})**")
                    st.markdown(f"> **AI 速讀：** {sentiment} | {item.get('publisher', '新聞')} ({pub_time})")
                    st.write("---")
            else:
                stock_code_only = search_symbol.split('.')[0]
                st.warning("⚠️ Yahoo API 暫無此檔股票的即時新聞。")
                google_news_url = f"https://news.google.com/search?q={stock_code_only}+股票&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
                st.markdown(f"👉 **[點此直接前往 Google 新聞查看 {res['股名']} 最新動態]({google_news_url})**")
                
    else: st.error("查無資料，請確認代碼格式 (如 2603.TW)。")

# ==========================================
# B. 全清單掃描與驗證
# ==========================================
if run_scan:
    STOCKS_0050 = [
        "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2881.TW", "2882.TW", "2382.TW", "2412.TW",
        "2357.TW", "3711.TW", "2603.TW", "2891.TW", "2303.TW", "2886.TW", "2884.TW", "2892.TW",
        "1216.TW", "2880.TW", "2002.TW", "3008.TW", "2379.TW", "5880.TW", "2301.TW", "3034.TW",
        "2885.TW", "2327.TW", "2890.TW", "3231.TW", "4938.TW", "2408.TW", "2609.TW", "2615.TW",
        "1301.TW", "1303.TW", "5871.TW", "5876.TW", "2345.TW", "6669.TW", "3037.TW", "3045.TW",
        "2409.TW", "1326.TW", "2912.TW", "1101.TW", "2395.TW", "2883.TW", "4958.TW", "2354.TW",
        "1402.TW", "9910.TW", "2610.TW", "2618.TW" 
    ]
    
    st.write("### 🚀 系統正在安全獲取數據，請稍候...")
    progress_bar = st.progress(0)
    status_text = st.empty()
    all_res = []
    
    for i, symbol in enumerate(STOCKS_0050):
        status_text.text(f"正在解析: {symbol} ({i+1}/{len(STOCKS_0050)})")
        res = analyze_stock(symbol)
        if res: all_res.append(res)
        time.sleep(0.1) 
        progress_bar.progress((i + 1) / len(STOCKS_0050))
        
    status_text.empty()
    progress_bar.empty()
        
    if all_res:
        res_df = pd.DataFrame(all_res).sort_values(by="評分", ascending=False)
        st.subheader(f"🎯 AI 推薦進場清單 (得分 >= {threshold})")
        pick_df = res_df[res_df['評分'] >= threshold]
        
        if not pick_df.empty:
            display_cols = ['股名', '代碼', '現價', '行動', '評分', '月線', '季線', 'MACD', 'KD', 'RSI', '量能', 'EPS']
            st.dataframe(pick_df[display_cols], use_container_width=True, hide_index=True)
        else: st.info(f"目前無股票達到 {threshold} 分門檻。")

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
            my_df = pd.DataFrame(my_list)
            my_cols = ['股名', '代碼', '成本', '現價', '停利點', '停損點', '狀態', '行動', '評分']
            st.dataframe(my_df[my_cols], use_container_width=True, hide_index=True)
        else: st.info("尚未輸入有效的持股資料。")
    else: st.error("網路連線異常，無法取得股票數據，請稍後再試。")

elif not search_symbol:
    st.warning(f"👈 請點擊左側「執行掃描」來獲取 {datetime.now().strftime('%Y/%m/%d')} 的最新市場解析。")
