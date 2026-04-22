import streamlit as st
import requests
from datetime import datetime
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

# ── 페이지 설정
st.set_page_config(page_title="Simon's Crypto Dashboard", page_icon="📊", layout="wide")
st.title("📊 Simon's Crypto Portfolio Dashboard")
st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 데이터: CoinGecko")

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

# ── 가격 데이터
@st.cache_data(ttl=300)
def get_prices():
    ids = ",".join(COINGECKO_IDS.values())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except:
        return {}

# ── 가격 표시
prices = get_prices()

sectors = {}
for symbol, info in PORTFOLIO.items():
    s = info["sector"]
    if s not in sectors:
        sectors[s] = []
    sectors[s].append(symbol)

for sector, symbols in sectors.items():
    icon = {"메이저": "🔵", "DeFi": "🟡", "밈코인": "🟢", "DeSci": "🔴"}.get(sector, "⚪")
    st.subheader(f"{icon} {sector}")
    cols = st.columns(len(symbols))
    for i, symbol in enumerate(symbols):
        cg_id = COINGECKO_IDS.get(symbol)
        data = prices.get(cg_id, {})
        price = data.get("usd") or 0
        change = data.get("usd_24h_change") or 0
        arrow = "▲" if change >= 0 else "▼"
        with cols[i]:
            if price == 0:
                st.metric(label=symbol, value="데이터 없음", delta="-")
            elif price < 0.0001:
                st.metric(label=symbol, value=f"${price:.8f}", delta=f"{arrow} {abs(change):.2f}%")
            elif price < 1:
                st.metric(label=symbol, value=f"${price:.4f}", delta=f"{arrow} {abs(change):.2f}%")
            else:
                st.metric(label=symbol, value=f"${price:,.2f}", delta=f"{arrow} {abs(change):.2f}%")

st.divider()

# ── AI 분석 섹션
st.subheader("🤖 AI 포트폴리오 분석")
st.caption("Claude AI가 현재 포트폴리오를 분석해드립니다 (API 비용 발생)")

if st.button("🔍 AI 분석 시작", type="primary"):
    with st.spinner("Claude가 분석 중입니다..."):

        price_summary = []
        for symbol, info in PORTFOLIO.items():
            cg_id = COINGECKO_IDS.get(symbol)
            data = prices.get(cg_id, {})
            price = data.get("usd") or 0
            change = data.get("usd_24h_change") or 0
            price_summary.append(f"{symbol}({info['sector']}): ${price:.6f} | 24h: {change:.2f}%")
        price_text = "\n".join(price_summary)

        prompt = f"""
너는 크립토 포트폴리오 분석 전문가야.

아래는 Simon의 현재 보유 포트폴리오 현황이야 (CoinGecko 실시간 데이터):
{price_text}

Simon의 투자 전략:
- BTC/ETH/SOL: 장기 보유 메이저 코인
- AAVE/SEI: DeFi 섹터 알트코인
- DOGE/PEPE: 밈코인 (사이클 트레이딩)
- RIF/URO: DeSci 소액 고위험 포지션

다음을 분석해줘:

## 📊 섹터별 24시간 성과
각 섹터 (메이저/DeFi/밈코인/DeSci) 성과를 간결하게 요약해줘.

## 🔍 주목할 코인
가장 주목할 코인 1~2개와 이유를 알려줘.

## ⚠️ 주의할 점
현재 포트폴리오에서 주의할 점 1가지.

## ✅ 긍정적 신호
현재 긍정적인 신호 1가지.

## 💡 한 줄 요약
Simon을 위한 한 줄 요약.

한국어로 간결하고 직접적으로 작성해줘.
"""

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        st.success("분석 완료!")
        st.markdown(message.content[0].text)

st.divider()
st.caption("💡 가격 데이터: CoinGecko API (5분 캐시) | AI 분석: Claude API")