"""
Comrade Stocks — People's Investment Bureau (Streamlit)
- Guarda localmente em 'portfolio.csv' (bom para correr localmente)
- OU guarda no Supabase (definindo SUPABASE_URL e SUPABASE_KEY nas secrets do Streamlit Cloud)
- Interface em português, tema vermelho, gráficos, downloads e nota 1-10.
Requerências: ver requirements.txt
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import date
import os
import base64

# Optional supabase client (only used if credentials provided)
try:
    from supabase import create_client, Client as SupabaseClient
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False

# ---------- CONFIG ----------
st.set_page_config(page_title="🚩 People's Investment Bureau", layout="wide",
                   initial_sidebar_state="expanded")

DATA_FILE = "portfolio.csv"  # fallback local file (works locally; on some cloud hosts filesystem may be ephemeral)

# Small CSS for communist-looking theme (red accents)
st.markdown(
    """
    <style>
    .stApp { background-color: #0b0b0b; color: #eee; }
    .css-18e3th9 { padding-top: 0.5rem; }
    .stButton>button { background-color: #b21d1d; border: none; color: white; }
    .stDownloadButton>button { background-color: #d33; color: white; }
    .stMetric { background-color: rgba(178,29,29,0.08); border-radius: 8px; padding: 8px; }
    .block-container { padding: 1.25rem 1rem; }
    h1, h2, h3 { color: #ffdddd; }
    .sidebar .stButton>button { background-color: #b21d1d; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚩 People's Investment Bureau")
st.caption("Gabinete do Investidor Popular — guarda posições, analisa e pontua (1–10).")

# ---------- Supabase setup if provided ----------
# ---------- Supabase setup ----------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

use_supabase = False
supabase = None

if SUPABASE_URL and SUPABASE_KEY and SUPABASE_AVAILABLE:
    try:
        # create client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # quick test: try to fetch 1 row from portfolio table
        try:
            res = supabase.table("portfolio").select("*").limit(1).execute()
            if res.data is not None:
                use_supabase = True
            else:
                st.warning("Supabase conectado, mas tabela 'portfolio' está vazia.")
        except Exception as table_err:
            st.error(f"Erro ao acessar tabela 'portfolio': {table_err}")
            use_supabase = False

    except Exception as conn_err:
        st.error(f"Não foi possível conectar ao Supabase: {conn_err}")
        use_supabase = False
else:
    st.info("Supabase não configurado. O app usará armazenamento local.")


# ---------- Helpers ----------
def local_load_portfolio():
    if os.path.exists(DATA_FILE):
        try:
            return pd.read_csv(DATA_FILE, parse_dates=["invest_date"])
        except Exception:
            return pd.DataFrame(columns=["ticker", "invest_date", "price", "amount"])
    else:
        return pd.DataFrame(columns=["ticker", "invest_date", "price", "amount"])

def local_save_portfolio(df):
    df.to_csv(DATA_FILE, index=False)

def supabase_load_portfolio():
    # expects table 'portfolio' with columns: ticker (text), invest_date (date/text), price (numeric), amount (numeric)
    try:
        res = supabase.table("portfolio").select("*").execute()
        data = res.data
        if not data:
            return pd.DataFrame(columns=["ticker", "invest_date", "price", "amount"])
        df = pd.DataFrame(data)
        # normalize column names
        df.columns = [c.lower() for c in df.columns]
        if "invest_date" in df.columns:
            try:
                df["invest_date"] = pd.to_datetime(df["invest_date"])
            except:
                pass
        return df[["ticker", "invest_date", "price", "amount"]]
    except Exception:
        return pd.DataFrame(columns=["ticker", "invest_date", "price", "amount"])

def supabase_save_row(row: dict):
    try:
        supabase.table("portfolio").insert(row).execute()
        return True
    except Exception:
        return False

def supabase_delete_row(ticker, invest_date, price, amount):
    # attempt deletion with match on all fields (requires appropriate permissions)
    try:
        supabase.table("portfolio").delete().match({
            "ticker": ticker,
            "invest_date": invest_date if isinstance(invest_date, str) else str(invest_date),
            "price": price,
            "amount": amount
        }).execute()
        return True
    except Exception:
        return False

def fetch_history(ticker, period="6mo"):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist is None or hist.empty:
            return None
        hist = hist.reset_index()
        hist.columns = hist.columns.str.lower()
        if "close" not in hist.columns:
            return None
        return hist[["date", "close"]]
    except Exception:
        return None

def plot_history_png(hist, ticker):
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.plot(hist["date"], hist["close"], linewidth=2, color="#ff4d4d")
    ax.set_title(f"{ticker} — últimos 6 meses")
    ax.set_xlabel("Data")
    ax.set_ylabel("Preço")
    ax.grid(alpha=0.2)
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf

def calc_metrics(hist, invested_price, invested_amount):
    current_price = float(hist["close"].iloc[-1])
    shares = invested_amount / invested_price if invested_price != 0 else 0
    current_value = shares * current_price
    profit = current_value - invested_amount
    roi = (profit / invested_amount) * 100 if invested_amount != 0 else 0
    return current_price, shares, current_value, profit, roi

def auto_review_text(hist, roi):
    start = hist["close"].iloc[0]
    end = hist["close"].iloc[-1]
    pct = (end - start) / start * 100
    vol = hist["close"].pct_change().std() * 100
    vol_text = "alta volatilidade" if vol > 2 else "baixa volatilidade"
    if pct > 8:
        trend = "forte alta"
    elif pct > 2:
        trend = "alta"
    elif pct < -8:
        trend = "forte queda"
    elif pct < -2:
        trend = "queda"
    else:
        trend = "estável"

    # score 1-10 from roi
    if roi >= 30:
        score = 10
    elif roi >= 15:
        score = 9
    elif roi >= 10:
        score = 8
    elif roi >= 5:
        score = 7
    elif roi >= 0:
        score = 6
    elif roi >= -5:
        score = 5
    elif roi >= -10:
        score = 4
    elif roi >= -20:
        score = 3
    else:
        score = 1

    text = (f"A ação apresenta {trend} ({pct:.2f}% no período). Observa-se {vol_text}. "
            f"Índice de desempenho popular: {score}/10. Esta é uma análise automática em português.")
    return text, score

def df_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------- STORAGE: choose backend ----------
if use_supabase:
    storage_backend = "supabase"
    portfolio_df = supabase_load_portfolio()
else:
    storage_backend = "local"
    portfolio_df = local_load_portfolio()

st.sidebar.markdown("## Configuração")
st.sidebar.write(f"Storage: **{storage_backend}**")
if storage_backend == "supabase":
    st.sidebar.write("A app está a usar Supabase (persistência online).")
else:
    st.sidebar.write("A app guarda num ficheiro `portfolio.csv` (local). On Streamlit Cloud a persistência local pode ser volátil).")

st.sidebar.markdown("---")
st.sidebar.write("Dicas: experimenta tickers como `AAPL`, `NVDA`, `TSLA`, `MSFT`.")
st.sidebar.markdown("---")

# ---------- UI: pages ----------
page = st.sidebar.radio("Ir para", ["Analisar ação", "Portfólio", "Export/Import"])

if page == "Analisar ação":
    st.header("📈 Analisar ação")
    col1, col2 = st.columns([2, 1])
    with col1:
        ticker = st.text_input("Símbolo / ticker (ex: AAPL, NVDA):").strip().upper()
        invested_price = st.number_input("Preço por ação na compra (€):", min_value=0.0, step=0.01, format="%.2f")
        invested_amount = st.number_input("Montante total investido (€):", min_value=0.0, step=1.0, format="%.2f")
        invest_date = st.date_input("Data do investimento:", value=date.today())
    with col2:
        st.markdown("### Como usar")
        st.write("- Introduz o ticker e os dados do teu investimento.")
        st.write("- Clica em **Obter dados** para ver análise e gráfico.")
        st.write("- Podes adicionar ao portfólio para guardar.")
    if st.button("🔎 Obter dados"):
        if not ticker or invested_price <= 0 or invested_amount <= 0:
            st.warning("Preenche ticker, preço e montante corretamente.")
        else:
            hist = fetch_history(ticker)
            if hist is None:
                st.error("Não consegui obter histórico para esse ticker. Verifica o símbolo.")
            else:
                current_price, shares, current_value, profit, roi = calc_metrics(hist, invested_price, invested_amount)
                st.metric("Preço atual", f"€{current_price:.2f}")
                st.metric("Valor atual", f"€{current_value:.2f}")
                st.metric("Lucro / Prejuízo", f"€{profit:.2f} ({roi:.2f}%)")
                buf = plot_history_png(hist, ticker)
                st.image(buf)
                st.download_button("📥 Baixar gráfico (PNG)", buf.getvalue(), file_name=f"{ticker}_hist.png", mime="image/png")
                review_text, score = auto_review_text(hist, roi)
                st.subheader("🧠 Análise automática")
                st.write(review_text)
                st.markdown(f"### 🔥 Nota Popular: **{score}/10**")

                # Add to portfolio
                if st.button("➕ Adicionar ao portfólio"):
                    row = {"ticker": ticker, "invest_date": invest_date.strftime("%Y-%m-%d"),
                           "price": invested_price, "amount": invested_amount}
                    if storage_backend == "supabase":
                        ok = supabase_save_row(row)
                        if ok:
                            st.success("Posição adicionada ao Supabase (persistida).")
                            portfolio_df = supabase_load_portfolio()
                        else:
                            st.error("Falha ao gravar no Supabase.")
                    else:
                        portfolio_df = pd.concat([portfolio_df, pd.DataFrame([row])], ignore_index=True)
                        local_save_portfolio(portfolio_df)
                        st.success("Posição adicionada ao ficheiro local.")

elif page == "Portfólio":
    st.header("📂 Portfólio do Povo")
    if portfolio_df.empty:
        st.info("Portfólio vazio — adiciona posições na página 'Analisar ação'.")
    else:
        # show aggregated totals
        total_invested = portfolio_df["amount"].sum()
        # compute current total safely
        total_now = 0.0
        total_profit = 0.0
        summary_rows = []
        for idx, r in portfolio_df.iterrows():
            ticker = str(r["ticker"]).strip().upper()
            price = float(r["price"])
            amount = float(r["amount"])
            hist = fetch_history(ticker)
            if hist is None:
                current = None
                profit = None
                roi = None
            else:
                current, shares, current_value, profit, roi = calc_metrics(hist, price, amount)
                total_now += current_value
                total_profit += profit
            summary_rows.append({
                "ticker": ticker, "invested": amount, "current_value": current_value if hist is not None else None,
                "profit": profit if hist is not None else None, "roi": roi if hist is not None else None
            })
        st.metric("Total investido", f"€{total_invested:.2f}")
        st.metric("Valor atual total (estimado)", f"€{total_now:.2f}")
        st.metric("Lucro total (estimado)", f"€{total_profit:.2f}")

        st.markdown("---")
        # individual cards
        for idx, row in portfolio_df.iterrows():
            ticker = str(row["ticker"]).strip().upper()
            price = float(row["price"])
            amount = float(row["amount"])
            invest_date = row.get("invest_date", "")
            hist = fetch_history(ticker)
            with st.expander(f"🔖 {ticker} — Investido €{amount:.2f}"):
                if hist is None:
                    st.write("Sem dados históricos (ticker inválido ou sem dados).")
                else:
                    current, shares, current_value, profit, roi = calc_metrics(hist, price, amount)
                    st.write(f"🗓️ Investido em: {invest_date}")
                    st.write(f"💵 Preço na compra: €{price:.2f}")
                    st.write(f"📈 Preço atual: €{current:.2f}")
                    st.write(f"🔢 Ações aproximadas: {shares:.4f}")
                    st.write(f"💰 Lucro total: €{profit:.2f} ({roi:.2f}%)")
                    buf = plot_history_png(hist, ticker)
                    st.image(buf)
                    review_text, score = auto_review_text(hist, roi)
                    st.write(review_text)
                    st.markdown(f"**Nota Popular:** {score}/10")
                    c1, c2 = st.columns([1, 1])
                    if c1.download_button("📥 Baixar gráfico", data=buf.getvalue(), file_name=f"{ticker}_hist.png", mime="image/png"):
                        pass
                    # remove button
                    if c2.button("🗑️ Remover", key=f"remove_{idx}"):
                        # remove in backend
                        if storage_backend == "supabase":
                            ok = supabase_delete_row(ticker, invest_date, price, amount)
                            if ok:
                                st.success("Removido do Supabase.")
                                portfolio_df = supabase_load_portfolio()
                                st.experimental_rerun()
                            else:
                                st.error("Falha ao remover no Supabase (ver permissões).")
                        else:
                            portfolio_df = portfolio_df.drop(index=idx).reset_index(drop=True)
                            local_save_portfolio(portfolio_df)
                            st.success("Removido do ficheiro local.")
                            st.experimental_rerun()

        st.markdown("---")
        st.download_button("⬇️ Exportar portfólio (CSV)", data=df_to_csv_bytes(portfolio_df), file_name="portfolio.csv", mime="text/csv")

elif page == "Export/Import":
    st.header("📦 Exportar / Importar")
    st.write("Exporta CSV ou importa um CSV com colunas: ticker,invest_date,price,amount")
    if st.button("Exportar CSV"):
        st.download_button("Descarregar CSV", data=df_to_csv_bytes(portfolio_df), file_name="portfolio.csv", mime="text/csv")
    uploaded = st.file_uploader("Importar CSV", type=["csv"])
    if uploaded:
        try:
            df_new = pd.read_csv(uploaded, parse_dates=["invest_date"])
            expected = {"ticker", "invest_date", "price", "amount"}
            if not expected.issubset(set(df_new.columns)):
                st.error("CSV inválido: garantir colunas ticker,invest_date,price,amount")
            else:
                # append
                if storage_backend == "supabase":
                    # insert rows to supabase
                    inserted = 0
                    for _, r in df_new.iterrows():
                        row = {"ticker": str(r["ticker"]).upper(), "invest_date": str(r["invest_date"]), "price": float(r["price"]), "amount": float(r["amount"])}
                        if supabase_save_row(row):
                            inserted += 1
                    st.success(f"{inserted} linhas importadas para Supabase.")
                else:
                    portfolio_df = pd.concat([portfolio_df, df_new], ignore_index=True)
                    local_save_portfolio(portfolio_df)
                    st.success("CSV importado para ficheiro local.")
        except Exception as e:
            st.error(f"Erro a importar CSV: {e}")

st.markdown("---")
st.caption("Feito em solidariedade — Comrade GPT 🚩")
