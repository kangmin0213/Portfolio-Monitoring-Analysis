import streamlit as st
import requests
from datetime import datetime, timedelta
import anthropic
import os
import json
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── 페이지 설정
st.set_page_config(
    page_title="Crypto Asset Management Agent",
    page_icon="🤖",
    layout="wide"
)

# ── 세션 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "holdings" not in st.session_state:
    st.session_state.holdings = {}
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []

# ── 보유 코인 설정
PORTFOLIO = {
    "BTC":  {"name": "Bitcoin",     "sector": "메이저"},
    "ETH":  {"name": "Ethereum",    "sector": "메이저"},
    "SOL":  {"name": "Solana",      "sector": "메이저"},
    "AAVE": {"name": "Aave",        "sector": "DeFi"},
    "SEI":  {"name": "Sei",         "sector": "DeFi"},
    "DOGE": {"name": "Dogecoin",    "sector": "밈코인"},
    "PEPE": {"name": "Pepe",        "sector": "밈코인"},
    "RIF":  {"name": "Rifampicin",  "sector": "DeSci"},
    "URO":  {"name": "Urolithin A", "sector": "DeSci"},
}

COINGECKO_IDS = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "SOL":  "solana",
    "AAVE": "aave",
    "SEI":  "sei-network",
    "DOGE": "dogecoin",
    "PEPE": "pepe",
    "RIF":  "rifampicin",
    "URO":  "urolithin-a",
}

# ══════════════════════════════════════════════
# 데이터 레이어: API 호출 함수들
# ══════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_prices():
    """CoinGecko 현재 가격 (5분 캐시)"""
    ids = ",".join(COINGECKO_IDS.values())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except:
        return {}

@st.cache_data(ttl=3600)
def get_historical_prices(coin_id, days=90):
    """CoinGecko 과거 가격 (1시간 캐시)"""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
    try:
        res = requests.get(url, timeout=15)
        data = res.json()
        return data.get("prices", [])
    except:
        return []

@st.cache_data(ttl=600)
def get_fear_greed_index():
    """Fear & Greed Index (10분 캐시)"""
    url = "https://api.alternative.me/fng/?limit=90&format=json"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        return data.get("data", [])
    except:
        return []

@st.cache_data(ttl=600)
def get_crypto_news(currencies=None):
    """CryptoPanic 뉴스 (10분 캐시)"""
    api_key = os.getenv("CRYPTOPANIC_API_KEY", "")
    if not api_key:
        return []
    
    url = f"https://cryptopanic.com/api/free/v1/posts/?auth_token={api_key}&public=true"
    if currencies:
        url += f"&currencies={currencies}"
    
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        return data.get("results", [])[:15]
    except:
        return []

@st.cache_data(ttl=600)
def get_trending_coins():
    """CoinGecko 트렌딩 코인 (10분 캐시)"""
    url = "https://api.coingecko.com/api/v3/search/trending"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        return data.get("coins", [])[:7]
    except:
        return []

# ── 데이터 로드
prices = get_prices()

# ══════════════════════════════════════════════
# 사이드바: 포트폴리오 관리
# ══════════════════════════════════════════════
with st.sidebar:
    st.header("💼 포트폴리오 관리")

    # ── 보유 수량 & 매수가 입력
    st.subheader("📝 보유 현황 입력")
    with st.expander("코인별 보유 수량 / 평균 매수가 설정", expanded=False):
        for symbol, info in PORTFOLIO.items():
            st.markdown(f"**{symbol}** ({info['name']})")
            col1, col2 = st.columns(2)
            with col1:
                qty = st.number_input(
                    f"수량",
                    min_value=0.0,
                    value=st.session_state.holdings.get(symbol, {}).get("qty", 0.0),
                    format="%.6f",
                    key=f"qty_{symbol}"
                )
            with col2:
                avg_price = st.number_input(
                    f"평균 매수가 ($)",
                    min_value=0.0,
                    value=st.session_state.holdings.get(symbol, {}).get("avg_price", 0.0),
                    format="%.8f",
                    key=f"avg_{symbol}"
                )
            st.session_state.holdings[symbol] = {"qty": qty, "avg_price": avg_price}
            st.divider()

    # ── 매수/매도 기록 추가
    st.subheader("📒 매매 기록 추가")
    with st.expander("새 매매 기록 입력", expanded=False):
        trade_coin = st.selectbox("코인", list(PORTFOLIO.keys()), key="trade_coin")
        trade_type = st.radio("유형", ["매수", "매도"], horizontal=True, key="trade_type")
        trade_date = st.date_input("날짜", value=datetime.now(), key="trade_date")
        trade_qty = st.number_input("수량", min_value=0.0, format="%.6f", key="trade_qty")
        trade_price = st.number_input("가격 ($)", min_value=0.0, format="%.8f", key="trade_price")

        if st.button("기록 추가", type="primary"):
            if trade_qty > 0 and trade_price > 0:
                st.session_state.trade_history.append({
                    "date": trade_date.strftime("%Y-%m-%d"),
                    "coin": trade_coin,
                    "type": trade_type,
                    "qty": trade_qty,
                    "price": trade_price,
                    "total": trade_qty * trade_price
                })
                st.success(f"✅ {trade_coin} {trade_type} 기록 추가됨!")
            else:
                st.warning("수량과 가격을 입력해주세요.")

    # ── 매매 기록 보기
    if st.session_state.trade_history:
        st.subheader("📋 매매 기록")
        for i, trade in enumerate(reversed(st.session_state.trade_history)):
            emoji = "🟢" if trade["type"] == "매수" else "🔴"
            st.caption(
                f"{emoji} {trade['date']} | {trade['coin']} {trade['type']} "
                f"{trade['qty']:.4f} @ ${trade['price']:.4f} "
                f"(${trade['total']:.2f})"
            )

# ══════════════════════════════════════════════
# 메인 영역
# ══════════════════════════════════════════════
st.title("🤖 Crypto Asset Management Agent")
st.caption(f"v0.3 — Portfolio · Charts · News · AI Advisor | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ── 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📊 대시보드", "📈 자산 추이", "📰 뉴스 & 트렌드", "💬 AI 채팅"])

# ══════════════════════════════════════════════
# TAB 1: 대시보드
# ══════════════════════════════════════════════
with tab1:
    total_invested = 0
    total_current = 0
    portfolio_data = []

    for symbol, info in PORTFOLIO.items():
        cg_id = COINGECKO_IDS.get(symbol)
        data = prices.get(cg_id, {})
        current_price = data.get("usd") or 0
        change_24h = data.get("usd_24h_change") or 0
        holding = st.session_state.holdings.get(symbol, {})
        qty = holding.get("qty", 0)
        avg_price = holding.get("avg_price", 0)

        invested = qty * avg_price
        current_value = qty * current_price
        pnl = current_value - invested
        pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0

        total_invested += invested
        total_current += current_value

        portfolio_data.append({
            "symbol": symbol, "name": info["name"], "sector": info["sector"],
            "price": current_price, "change_24h": change_24h,
            "qty": qty, "avg_price": avg_price,
            "invested": invested, "current_value": current_value,
            "pnl": pnl, "pnl_pct": pnl_pct,
        })

    total_pnl = total_current - total_invested
    total_pnl_pct = ((total_current / total_invested) - 1) * 100 if total_invested > 0 else 0

    # ── 포트폴리오 총 요약
    st.subheader("💰 포트폴리오 요약")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("총 투자금", f"${total_invested:,.2f}")
    with c2:
        st.metric("현재 평가액", f"${total_current:,.2f}")
    with c3:
        arrow = "▲" if total_pnl >= 0 else "▼"
        st.metric("총 손익", f"${total_pnl:,.2f}", delta=f"{arrow} {abs(total_pnl_pct):.2f}%")
    with c4:
        fng_data = get_fear_greed_index()
        if fng_data:
            fng_value = int(fng_data[0].get("value", 0))
            fng_label = fng_data[0].get("value_classification", "N/A")
            fng_emoji = "😱" if fng_value < 25 else "😰" if fng_value < 45 else "😐" if fng_value < 55 else "😊" if fng_value < 75 else "🤑"
            st.metric("공포·탐욕 지수", f"{fng_emoji} {fng_value}", delta=fng_label)
        else:
            st.metric("보유 코인 수", f"{sum(1 for p in portfolio_data if p['qty'] > 0)}개")

    st.divider()

    # ── 섹터별 가격 + 보유 현황
    sectors = {}
    for item in portfolio_data:
        s = item["sector"]
        if s not in sectors:
            sectors[s] = []
        sectors[s].append(item)

    for sector, items in sectors.items():
        icon = {"메이저": "🔵", "DeFi": "🟡", "밈코인": "🟢", "DeSci": "🔴"}.get(sector, "⚪")
        st.subheader(f"{icon} {sector}")
        cols = st.columns(len(items))
        for i, item in enumerate(items):
            with cols[i]:
                price = item["price"]
                change = item["change_24h"]
                arrow = "▲" if change >= 0 else "▼"

                if price == 0:
                    st.metric(label=item["symbol"], value="데이터 없음", delta="-")
                elif price < 0.0001:
                    st.metric(label=item["symbol"], value=f"${price:.8f}", delta=f"{arrow} {abs(change):.2f}%")
                elif price < 1:
                    st.metric(label=item["symbol"], value=f"${price:.4f}", delta=f"{arrow} {abs(change):.2f}%")
                else:
                    st.metric(label=item["symbol"], value=f"${price:,.2f}", delta=f"{arrow} {abs(change):.2f}%")

                if item["qty"] > 0:
                    pnl_color = "🟢" if item["pnl"] >= 0 else "🔴"
                    st.caption(
                        f"보유: {item['qty']:.4f}개\n"
                        f"평가: ${item['current_value']:,.2f}\n"
                        f"{pnl_color} PnL: ${item['pnl']:,.2f} ({item['pnl_pct']:+.2f}%)"
                    )

# ══════════════════════════════════════════════
# TAB 2: 자산 추이 그래프
# ══════════════════════════════════════════════
with tab2:
    st.subheader("📈 자산 추이")

    has_holdings = any(
        st.session_state.holdings.get(s, {}).get("qty", 0) > 0
        for s in PORTFOLIO
    )

    if not has_holdings:
        st.info("👈 사이드바에서 보유 수량을 입력하면 자산 추이 그래프가 표시됩니다.")
    else:
        # ── 기간 선택
        period = st.radio(
            "기간 선택",
            ["1M", "90D", "1Y"],
            index=1,
            horizontal=True,
            key="chart_period"
        )
        days = {"1M": 30, "90D": 90, "1Y": 365}[period]

        with st.spinner("과거 가격 데이터 로딩 중..."):
            date_values = {}
            for symbol, info in PORTFOLIO.items():
                qty = st.session_state.holdings.get(symbol, {}).get("qty", 0)
                if qty <= 0:
                    continue
                cg_id = COINGECKO_IDS.get(symbol)
                hist = get_historical_prices(cg_id, days)
                for timestamp, price in hist:
                    date_str = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")
                    if date_str not in date_values:
                        date_values[date_str] = 0
                    date_values[date_str] += qty * price

            if date_values:
                df = pd.DataFrame(
                    sorted(date_values.items()),
                    columns=["날짜", "총 자산 (USD)"]
                )
                df["날짜"] = pd.to_datetime(df["날짜"])

                # ── 공포·탐욕 지수 오버레이 옵션
                show_fng = st.checkbox("📊 공포·탐욕 지수 오버레이", value=False)

                # 총 자산 추이
                st.line_chart(df, x="날짜", y="총 자산 (USD)", use_container_width=True)

                # 공포·탐욕 차트
                if show_fng:
                    fng_data = get_fear_greed_index()
                    if fng_data:
                        fng_df = pd.DataFrame([
                            {
                                "날짜": datetime.fromtimestamp(int(d["timestamp"])),
                                "공포·탐욕 지수": int(d["value"])
                            }
                            for d in fng_data
                        ])
                        fng_df = fng_df.sort_values("날짜")
                        st.caption("📊 Fear & Greed Index (0=극도 공포 → 100=극도 탐욕)")
                        st.area_chart(fng_df, x="날짜", y="공포·탐욕 지수", use_container_width=True)
                    else:
                        st.caption("공포·탐욕 데이터를 가져올 수 없습니다.")

                # 요약 통계
                first_val = df["총 자산 (USD)"].iloc[0]
                last_val = df["총 자산 (USD)"].iloc[-1]
                max_val = df["총 자산 (USD)"].max()
                min_val = df["총 자산 (USD)"].min()
                change_pct = ((last_val / first_val) - 1) * 100 if first_val > 0 else 0

                mc1, mc2, mc3, mc4 = st.columns(4)
                with mc1:
                    st.metric(f"{days}일 전", f"${first_val:,.2f}")
                with mc2:
                    st.metric("현재", f"${last_val:,.2f}")
                with mc3:
                    st.metric("기간 최고", f"${max_val:,.2f}")
                with mc4:
                    arrow = "▲" if change_pct >= 0 else "▼"
                    st.metric("수익률", f"{change_pct:+.2f}%", delta=f"{arrow} {abs(change_pct):.2f}%")

                # 코인별 추이
                st.divider()
                st.subheader("🪙 코인별 가치 추이")

                coin_dfs = {}
                for symbol, info in PORTFOLIO.items():
                    qty = st.session_state.holdings.get(symbol, {}).get("qty", 0)
                    if qty <= 0:
                        continue
                    cg_id = COINGECKO_IDS.get(symbol)
                    hist = get_historical_prices(cg_id, days)
                    if hist:
                        coin_data = []
                        for timestamp, price in hist:
                            date_str = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")
                            coin_data.append({"날짜": date_str, symbol: qty * price})
                        cdf = pd.DataFrame(coin_data)
                        cdf["날짜"] = pd.to_datetime(cdf["날짜"])
                        cdf = cdf.groupby("날짜").last().reset_index()
                        coin_dfs[symbol] = cdf

                if coin_dfs:
                    merged = None
                    for symbol, cdf in coin_dfs.items():
                        if merged is None:
                            merged = cdf
                        else:
                            merged = pd.merge(merged, cdf, on="날짜", how="outer")
                    merged = merged.sort_values("날짜").fillna(0)
                    coin_cols = [c for c in merged.columns if c != "날짜"]
                    st.line_chart(merged, x="날짜", y=coin_cols, use_container_width=True)
            else:
                st.warning("가격 데이터를 가져올 수 없습니다.")

# ══════════════════════════════════════════════
# TAB 3: 뉴스 & 트렌드
# ══════════════════════════════════════════════
with tab3:
    st.subheader("📰 크립토 뉴스 & 트렌드")

    news_col, trend_col = st.columns([2, 1])

    with news_col:
        st.markdown("### 📢 최신 뉴스")

        portfolio_symbols = ",".join(PORTFOLIO.keys())
        news_filter = st.radio(
            "필터",
            ["전체 뉴스", "내 포트폴리오 관련"],
            horizontal=True,
            key="news_filter"
        )

        if news_filter == "내 포트폴리오 관련":
            news = get_crypto_news(currencies=portfolio_symbols)
        else:
            news = get_crypto_news()

        if news:
            for article in news:
                title = article.get("title", "")
                url = article.get("url", "")
                source = article.get("source", {}).get("title", "")
                published = article.get("published_at", "")[:10]

                votes = article.get("votes", {})
                positive = votes.get("positive", 0)
                negative = votes.get("negative", 0)
                if positive > negative:
                    sentiment = "🟢"
                elif negative > positive:
                    sentiment = "🔴"
                else:
                    sentiment = "⚪"

                currencies = article.get("currencies", [])
                coin_tags = " ".join([f"`{c.get('code', '')}`" for c in currencies[:3]]) if currencies else ""

                st.markdown(f"{sentiment} **[{title}]({url})**")
                st.caption(f"{source} · {published} {coin_tags}")
        else:
            st.info("뉴스를 가져올 수 없습니다. CRYPTOPANIC_API_KEY를 Streamlit Secrets에 설정해주세요.")

    with trend_col:
        st.markdown("### 🔥 트렌딩 코인")
        trending = get_trending_coins()
        if trending:
            for i, coin in enumerate(trending):
                item = coin.get("item", {})
                name = item.get("name", "")
                symbol = item.get("symbol", "")
                rank = item.get("market_cap_rank", "?")
                st.markdown(f"**{i+1}. {name}** (`{symbol}`)")
                st.caption(f"시총 순위: #{rank}")
        else:
            st.caption("트렌딩 데이터를 가져올 수 없습니다.")

        st.markdown("---")

        # Fear & Greed 현황
        st.markdown("### 😱 공포·탐욕 지수")
        fng = get_fear_greed_index()
        if fng:
            current_fng = int(fng[0].get("value", 0))
            fng_class = fng[0].get("value_classification", "")
            if current_fng < 25:
                bar_color = "🟥"
            elif current_fng < 45:
                bar_color = "🟧"
            elif current_fng < 55:
                bar_color = "🟨"
            elif current_fng < 75:
                bar_color = "🟩"
            else:
                bar_color = "💚"
            st.markdown(f"### {bar_color} {current_fng} / 100")
            st.caption(f"상태: {fng_class}")

            if len(fng) >= 7:
                recent_fng = [int(d["value"]) for d in fng[:7]]
                recent_fng.reverse()
                st.caption(f"7일 추이: {' → '.join(map(str, recent_fng))}")

# ══════════════════════════════════════════════
# TAB 4: AI 채팅
# ══════════════════════════════════════════════
with tab4:
    st.subheader("💬 AI 크립토 어드바이저")
    st.caption("포트폴리오, 뉴스, 트렌드, 매매 추천, 코인 리서치 — 크립토에 관한 건 뭐든 물어보세요.")

    # ── 포트폴리오 + 뉴스 + 시장 지표 컨텍스트 생성
    def build_full_context():
        lines = []
        total_inv = 0
        total_cur = 0

        for symbol, info in PORTFOLIO.items():
            cg_id = COINGECKO_IDS.get(symbol)
            data = prices.get(cg_id, {})
            current_price = data.get("usd") or 0
            change = data.get("usd_24h_change") or 0
            holding = st.session_state.holdings.get(symbol, {})
            qty = holding.get("qty", 0)
            avg_price = holding.get("avg_price", 0)

            invested = qty * avg_price
            current_val = qty * current_price
            pnl = current_val - invested
            pnl_pct = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0

            total_inv += invested
            total_cur += current_val

            line = f"{symbol}({info['sector']}): 현재가 ${current_price:.6f} | 24h {change:+.2f}%"
            if qty > 0:
                line += f" | 보유 {qty:.4f}개 | 매수가 ${avg_price:.6f} | 평가 ${current_val:,.2f} | PnL ${pnl:,.2f} ({pnl_pct:+.2f}%)"
            lines.append(line)

        context = "[포트폴리오 현황]\n" + "\n".join(lines)
        total_pnl = total_cur - total_inv
        context += f"\n총 투자금: ${total_inv:,.2f} | 현재 평가액: ${total_cur:,.2f} | 총 PnL: ${total_pnl:,.2f}"

        if st.session_state.trade_history:
            context += "\n\n[최근 매매 기록]\n"
            for t in st.session_state.trade_history[-10:]:
                context += f"- {t['date']} {t['coin']} {t['type']} {t['qty']:.4f}개 @ ${t['price']:.4f}\n"

        # 뉴스
        news = get_crypto_news()
        if news:
            context += "\n\n[최신 크립토 뉴스 — CryptoPanic]\n"
            for article in news[:10]:
                title = article.get("title", "")
                source = article.get("source", {}).get("title", "")
                votes = article.get("votes", {})
                pos = votes.get("positive", 0)
                neg = votes.get("negative", 0)
                sentiment = "긍정" if pos > neg else "부정" if neg > pos else "중립"
                coins = [c.get("code", "") for c in article.get("currencies", [])]
                coin_str = ", ".join(coins) if coins else "일반"
                context += f"- [{sentiment}] {title} (출처: {source}, 관련: {coin_str})\n"

        # Fear & Greed
        fng = get_fear_greed_index()
        if fng:
            context += f"\n\n[공포·탐욕 지수] 현재: {fng[0].get('value', '?')} ({fng[0].get('value_classification', '?')})"
            if len(fng) >= 7:
                week_vals = [d["value"] for d in fng[:7]]
                context += f" | 최근 7일: {', '.join(week_vals)}"

        # 트렌딩
        trending = get_trending_coins()
        if trending:
            context += "\n\n[CoinGecko 트렌딩]\n"
            for coin in trending[:5]:
                item = coin.get("item", {})
                context += f"- {item.get('name', '')} ({item.get('symbol', '')}) 시총순위 #{item.get('market_cap_rank', '?')}\n"

        return context

    SYSTEM_PROMPT = """너는 Simon의 개인 크립토 전문 AI 어드바이저야. 포트폴리오 관리뿐 아니라 크립토 시장 전반에 대해 폭넓게 대화할 수 있어.

실시간 데이터가 컨텍스트에 포함되어 있어:
- CoinGecko 실시간 가격 및 24시간 변동률
- CryptoPanic 최신 뉴스 (감성 분석 포함)
- Fear & Greed Index (공포·탐욕 지수)
- CoinGecko 트렌딩 코인

다룰 수 있는 주제:
1. 포트폴리오 분석 — 보유 코인 성과, 리밸런싱, 섹터 비중 조정
2. 매매 추천 — 매수/매도 타이밍, 진입/청산 전략 (근거+리스크 필수)
3. 코인/프로젝트 리서치 — 특정 코인의 기술, 팀, 로드맵, 토큰이코노믹스 분석
4. 뉴스 해석 — 제공된 최신 뉴스를 기반으로 시장 영향 분석
5. 섹터 트렌드 — DeFi, AI, RWA, DeSci, 밈코인, L2, 모듈러 블록체인 등
6. 신규 코인/섹터 추천 — 트렌딩 데이터와 뉴스 기반으로 새로운 기회 탐색
7. 온체인 & 기술적 분석 — 기술적 지표, 온체인 메트릭 기반 분석
8. 크립토 기초 지식 — DeFi 프로토콜, NFT, DAO, 브릿지 등 개념 설명
9. 투자 전략 — DCA, 사이클 트레이딩, 리스크 관리, 포지션 사이징
10. 시장 심리 분석 — Fear & Greed 지수 해석, 시장 분위기 판단

Simon의 현재 투자 전략:
- BTC/ETH/SOL: 장기 보유 메이저 코인
- AAVE/SEI: DeFi 섹터 알트코인
- DOGE/PEPE: 밈코인 (사이클 트레이딩)
- RIF/URO: DeSci 소액 고위험 포지션

규칙:
- 항상 한국어로 답변
- 간결하고 직접적으로 (불필요한 인사 생략)
- 매매 추천 시 반드시 근거와 리스크를 함께 언급
- 뉴스 데이터를 활용할 때는 출처를 명시
- 확신에 찬 어조보다는 확률적 관점으로 설명
- 질문이 포트폴리오와 무관해도 크립토 관련이면 자유롭게 답변
- 투자는 본인 책임이라는 점을 자연스럽게 언급
"""

    # ── 채팅 표시
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── 빠른 질문 버튼
    if not st.session_state.chat_history:
        st.markdown("**💡 추천 질문:**")
        quick_cols = st.columns(3)
        quick_questions = [
            "현재 포트폴리오 전체 분석해줘",
            "요즘 핫한 크립토 섹터가 뭐야?",
            "포트폴리오에 추가할 만한 코인 추천해줘",
        ]
        for i, q in enumerate(quick_questions):
            with quick_cols[i]:
                if st.button(q, key=f"quick_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": q})
                    st.rerun()

        quick_cols2 = st.columns(3)
        quick_questions2 = [
            "최신 뉴스 기반으로 시장 분석해줘",
            "공포·탐욕 지수가 뭘 의미해?",
            "지금 트렌딩 코인들 분석해줘",
        ]
        for i, q in enumerate(quick_questions2):
            with quick_cols2[i]:
                if st.button(q, key=f"quick2_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": q})
                    st.rerun()

    # ── 채팅 입력
    if user_input := st.chat_input("크립토에 관한 건 뭐든 물어보세요..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.rerun()

    # ── AI 응답 생성 (최근 10턴만 유지 → 비용 절감)
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                full_context = build_full_context()

                recent_history = st.session_state.chat_history[-10:]

                messages = []
                for j, msg in enumerate(recent_history):
                    if msg["role"] == "user" and j == len(recent_history) - 1:
                        content = f"{full_context}\n\n[질문]\n{msg['content']}"
                    else:
                        content = msg["content"]
                    messages.append({"role": msg["role"], "content": content})

                try:
                    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=2048,
                        system=SYSTEM_PROMPT,
                        messages=messages
                    )
                    ai_response = response.content[0].text
                except Exception as e:
                    ai_response = f"⚠️ API 오류가 발생했습니다: {str(e)}\n\nANTHROPIC_API_KEY가 설정되어 있는지 확인해주세요."

                st.markdown(ai_response)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response})

    # ── 채팅 초기화
    if st.session_state.chat_history:
        if st.button("🗑️ 대화 초기화"):
            st.session_state.chat_history = []
            st.rerun()

st.divider()
st.caption("💡 CoinGecko (5분) · CryptoPanic (10분) · Fear&Greed (10분) | AI: Claude API | ⚠️ 투자 판단은 본인 책임입니다.")
