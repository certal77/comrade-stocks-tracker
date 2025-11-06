"""
Comrade Stocks — People’s Investment Bureau
- Guarda portfólio local em 'portfolio.csv'
- Páginas: "Analisar" (single-stock) e "Portfólio" (saved stocks, auto-update)
- Reviews em português (simulados) + opção OpenAI (chave opcional)
- Download de gráfico por posição e export CSV do portfólio

Dependências:
pip install streamlit yfinance pandas matplotlib openai
(Se não queres OpenAI, não instala openai; o app funciona na boa com análise simulada.)
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date, datetime
from io import BytesIO
import os

# ---------- Config ----------
st.set_page_config(page_title="🚩 People's Investment Bureau", layout="wide")
DATA_FILE = "portfolio.csv"  # ficheiro local para guardar portfólio

# ---------- Helpers ----------
def load_portfolio():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE, parse_dates=["invest_date"])
            return df
        except Exception:
            return pd.DataFrame(columns=["ticker","invest_date","invested_price","invested_amount"])
    else:
        return pd.DataFrame(columns=["ticker","invest_date","invested_price","invested_amount"])

def save_portfolio(df):
    df.to_csv(DATA_FILE, index=False)

def fetch_history(ticker, period="6mo"):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist is None or hist.empty:
            return None
        hist = hist.reset_index()
        hist.columns = [c.lower() for c in hist.columns]  # converte todos para minúsculas
        return hist[["date", "close"]]
    except Exception:
        return None


def fetch_current_price_from_hist(hist_df):
    return float(hist_df['Close'].iloc[-1])

def compute_metrics(current_price, invested_price, invested_amount):
    if invested_price <= 0:
        return None
    shares = invested_amount / invested_price
    current_value = shares * current_price
    profit = current_value - invested_amount
    roi_pct = (profit / invested_amount) * 100
    return {"shares": shares, "current_value": current_value, "profit": profit, "roi_pct": roi_pct}

def simulated_review_portuguese(hist_close_series, invested_price, invested_amount):
    # texto em português baseado em tendência e volatilidade simples
    if hist_close_series is None or len(hist_close_series) < 2:
        return "Dados insuficientes para análise automatizada."
    start = hist_close_series.iloc[0]
    end = hist_close_series.iloc[-1]
    pct_period = (end - start) / start * 100
    recent_mean = hist_close_series[-14:].mean() if len(hist_close_series) >= 14 else hist_close_series.mean()
    vol = hist_close_series.pct_change().std() * 100
    vol_text = "alta volatilidade" if vol > 2 else "baixa volatilidade"
    if pct_period > 8:
        trend = "em forte alta"
    elif pct_period > 2:
        trend = "em alta"
    elif pct_period < -8:
        trend = "em forte queda"
    elif pct_period < -2:
        trend = "em queda"
    else:
        trend = "estável/volátil"
    reasons = []
    if end > recent_mean:
        reasons.append("momento comprador (preço acima da média recente)")
    else:
        reasons.append("pressão vendedora (preço abaixo da média recente)")
    text = (
        f"A ação está {trend} ({pct_period:.2f}% no período observado). Observa-se {vol_text}. "
        f"Possíveis razões: {', '.join(reasons)}. "
        "Esta é uma análise automatizada e não constitui aconselhamento financeiro."
    )
    return text

# Optional OpenAI analysis (only if user provides a key and openai is installed)
def ai_review_openai(key, ticker, hist_df, invested_date, invested_price, invested_amount):
    try:
        import openai
    except Exception:
        return None
    if not key:
        return None
    openai.api_key = key
    try:
        start = hist_df['date'].dt.strftime('%Y-%m-%d').iloc[0]
        end = hist_df['date'].dt.strftime('%Y-%m-%d').iloc[-1]
        latest = float(hist_df['close'].iloc[-1])
        prompt = (
            f"Tens de responder em português. És um analista conciso. Analisa a ação {ticker} "
            f"com dados de {start} a {end}. Preço atual {latest:.2f}. "
            f"O utilizador comprou em {invested_date} a {invested_price:.2f} por ação, investiu {invested_amount:.2f}. "
            "Em 3-4 frases explica possíveis razões para o comportamento do preço, um risco chave e uma previsão curta."
        )
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":prompt}],
            max_tokens=250,
            temperature=0.6
        )
        return resp['choices'][0]['message']['content'].strip()
    except Exception:
        return None

def plot_hist_png(hist_df, ticker):
    fig, ax = plt.subplots()
    ax.plot(hist_df['date'], hist_df['close'], linewidth=2)
    ax.set_title(f"{ticker} — Movimento (histórico)")
    ax.set_xlabel("Data")
    ax.set_ylabel("Preço")
    ax.grid(True)
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf

def score_from_roi(roi_pct):
    # escala 1-10
    if roi_pct is None:
        return 5
    if roi_pct >= 30: return 10
    if roi_pct >= 15: return 9
    if roi_pct >= 10: return 8
    if roi_pct >= 5: return 7
    if roi_pct >= 0: return 6
    if roi_pct >= -5: return 5
    if roi_pct >= -10: return 4
    if roi_pct >= -20: return 3
    return 1

# ---------- UI ----------
st.header("🚩 People's Investment Bureau — Portfólio do Povo")
st.write("Guarda posições, atualiza reviews automaticamente. Tudo em português e com cara socialista.")

# Sidebar / navegação
page = st.sidebar.selectbox("Navegar", ["Analisar uma ação", "Portfólio", "Exportar / Importar"])
st.sidebar.markdown("---")
st.sidebar.write("Feito com ❤️ por Comrade GPT — mantém a disciplina do proletariado.")
st.sidebar.markdown("**OpenAI (opcional):**")
openai_key = st.sidebar.text_input("Chave OpenAI (opcional)", type="password")
use_openai = st.sidebar.checkbox("Tentar análise com OpenAI (se chave válida)", value=False)

# Load portfolio
portfolio = load_portfolio()

# ---------- Page: Analisar uma ação ----------
if page == "Analisar uma ação":
    st.subheader("Analisar uma ação (adicionar ao portfólio)")
    col1, col2 = st.columns([2,1])
    with col1:
        ticker = st.text_input("Símbolo / ticker (ex: AAPL, NVDA):").strip().upper()
        invest_date = st.date_input("Data do investimento:", value=date.today())
        invested_price = st.number_input("Preço por ação na altura:", min_value=0.0, step=0.01, format="%.2f")
        invested_amount = st.number_input("Montante total investido:", min_value=0.0, step=1.0, format="%.2f")
    with col2:
        st.markdown("### Instruções")
        st.write("- Introduz o ticker e os dados do teu investimento.")
        st.write("- Podes adicionar ao portfólio com o botão abaixo.")
        st.write("- As reviews são atualizadas sempre que abres a página do portfólio.")
    if st.button("Obter dados & Mostrar análise"):
        if not ticker:
            st.warning("Insere um ticker válido.")
        elif invested_price <= 0 or invested_amount <= 0:
            st.warning("Preço e montante têm de ser maiores que zero.")
        else:
            hist = fetch_history(ticker, period="6mo")
            if hist is None:
                st.error("Não consegui obter histórico para esse ticker.")
            else:
                current_price = fetch_current_price_from_hist(hist['Close'])
                metrics = compute_metrics(current_price, invested_price, invested_amount)
                st.metric("Preço atual", f"€{current_price:.2f}")
                st.metric("Lucro / Prejuízo", f"€{metrics['profit']:.2f} ({metrics['roi_pct']:.2f}%)")
                # gráfico + download
                buf = plot_hist_png(hist, ticker)
                st.image(buf)
                st.download_button("📥 Baixar gráfico (PNG)", data=buf.getvalue(), file_name=f"{ticker}_hist.png", mime="image/png")
                # análise (OpenAI ou simulada)
                ai_text = None
                if use_openai and openai_key:
                    ai_text = ai_review_openai(openai_key, ticker, hist, invest_date.strftime("%Y-%m-%d"), invested_price, invested_amount)
                if ai_text:
                    st.subheader("Análise (OpenAI)")
                    st.write(ai_text)
                else:
                    st.subheader("Análise automática (simulada)")
                    st.write(simulated_review_portuguese(hist['close'], invested_price, invested_amount))
                st.info("Se quiseres guardar esta posição no teu portfólio, usa o botão abaixo.")
                if st.button("➕ Adicionar ao portfólio"):
                    portfolio = portfolio.append({
                        "ticker": ticker,
                        "invest_date": invest_date.strftime("%Y-%m-%d"),
                        "invested_price": invested_price,
                        "invested_amount": invested_amount
                    }, ignore_index=True)
                    save_portfolio(portfolio)
                    st.success("Posição adicionada ao portfólio.")

# ---------- Page: Portfólio ----------
elif page == "Portfólio":
    st.subheader("📂 Portfólio do Povo")
    st.write("As reviews e métricas são atualizadas ao carregar este separador.")
    if portfolio.empty:
        st.info("O teu portfólio está vazio — vai a 'Analisar uma ação' para adicionar posições.")
    else:
        # Option: refresh all
        if st.button("🔁 Atualizar todas as posições"):
            st.experimental_rerun()
        # Table view + per-stock cards
        rows = []
        for idx, row in portfolio.iterrows():
            ticker = str(row['ticker']).strip().upper()
            invest_date = row['invest_date']
            invested_price = float(row['invested_price'])
            invested_amount = float(row['invested_amount'])
            hist = fetch_history(ticker, period="6mo")
            if hist is None:
                st.warning(f"{ticker}: sem dados (talvez ticker inválido).")
                continue
            current_price = fetch_current_price_from_hist(hist['close'])
            metrics = compute_metrics(current_price, invested_price, invested_amount)
            score = score_from_roi(metrics['roi_pct'])
            # Card
            card_col = st.container()
            with card_col:
                c1, c2 = st.columns([2,3])
                with c1:
                    st.markdown(f"### 🔖 {ticker}")
                    st.write(f"🗓️ Investido: {invest_date}")
                    st.write(f"💵 Preço na compra: €{invested_price:.2f}")
                    st.write(f"💰 Montante investido: €{invested_amount:.2f}")
                    st.write(f"📈 Preço atual: €{current_price:.2f}")
                    st.write(f"🔢 Ações aproximadas: {metrics['shares']:.4f}")
                    st.metric("Lucro total", f"€{metrics['profit']:.2f}")
                    st.metric("ROI", f"{metrics['roi_pct']:.2f}%")
                    st.markdown(f"**Índice de Prosperidade Popular:** {score}/10")
                    # small actions
                    col_a, col_b, col_c = st.columns(3)
                    if col_a.button("🔄 Atualizar", key=f"upd_{idx}"):
                        st.experimental_rerun()
                    if col_b.download_button("📥 Baixar gráfico", data=plot_hist_png(hist, ticker).getvalue(),
                                             file_name=f"{ticker}_hist.png", mime="image/png"):
                        pass
                    if col_c.button("🗑️ Remover", key=f"del_{idx}"):
                        portfolio = portfolio.drop(index=idx).reset_index(drop=True)
                        save_portfolio(portfolio)
                        st.success(f"{ticker} removido do portfólio")
                        st.experimental_rerun()
                with c2:
                    # show small plot inline
                    fig, ax = plt.subplots(figsize=(6,2.8))
                    ax.plot(hist['date'], hist['close'], linewidth=2)
                    ax.set_title(f"{ticker} — últimos 6 meses")
                    ax.grid(True)
                    st.pyplot(fig)
                    # analysis text
                    ai_text = None
                    if use_openai and openai_key:
                        ai_text = ai_review_openai(openai_key, ticker, hist, invest_date, invested_price, invested_amount)
                    if ai_text:
                        st.markdown("**Análise (OpenAI):**")
                        st.write(ai_text)
                    else:
                        st.markdown("**Análise (automática):**")
                        st.write(simulated_review_portuguese(hist['close'], invested_price, invested_amount))
            st.markdown("---")

        # Export / download CSV of portfolio
        csv = portfolio.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Exportar portfólio (CSV)", data=csv, file_name="portfolio.csv", mime="text/csv")

# ---------- Page: Export / Import ----------
elif page == "Exportar / Importar":
    st.subheader("Importar / Exportar portfólio")
    st.write("Exporta ou importa um ficheiro CSV do teu portfólio.")
    if st.button("Exportar CSV (guardar local)"):
        csv = portfolio.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="portfolio.csv", mime="text/csv")
    st.write("Ou importa um CSV com colunas: ticker,invest_date,invested_price,invested_amount")
    uploaded = st.file_uploader("Carregar ficheiro CSV", type=["csv"])
    if uploaded:
        try:
            df_new = pd.read_csv(uploaded, parse_dates=["invest_date"])
            # valida colunas
            expected = {"ticker","invest_date","invested_price","invested_amount"}
            if not expected.issubset(set(df_new.columns)):
                st.error("CSV inválido — assegura as colunas: ticker,invest_date,invested_price,invested_amount")
            else:
                # append and save
                portfolio = pd.concat([portfolio, df_new], ignore_index=True)
                save_portfolio(portfolio)
                st.success("Portfólio importado com sucesso. Vai ao separador Portfólio para ver as posições.")
        except Exception as e:
            st.error(f"Erro ao importar CSV: {e}")

# ---------- end ----------
st.markdown("---")
st.caption("Esta aplicação é educativa. Não é aconselhamento financeiro. Feito com solidariedade — Comrade GPT.")

