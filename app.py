"""
Comrade Stocks — People's Investment Bureau (Streamlit)
- Guarda localmente em 'portfolio.csv' (bom para correr localmente)
- OU guarda no Supabase (definindo SUPABASE_URL e SUPABASE_KEY nas secrets do Streamlit Cloud)
- Interface em português, tema vermelho, gráficos, downloads e nota 1-10.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import date
import os

# Optional supabase client
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except Exception:
    SUPABASE_AVAILABLE = False

# ---------- CONFIG ----------
st.set_page_config(page_title="🚩 People's Investment Bureau", layout="wide", initial_sidebar_state="expanded")
DATA_FILE = "portfolio.csv"

# ---------- THEME ----------
st.markdown("""
<style>
.stApp { background-color: #0b0b0b; color: #eee; }
.stButton>button { background-color: #b21d1d; border: none; color: white; }
.stDownloadButton>button { background-color: #d33; color: white; }
.stMetric { background-color: rgba(178,29,29,0.08); border-radius: 8px; padding: 8px; }
h1, h2, h3 { color: #ffdddd; }
</style>
""", unsafe_allow_html=True)

st.title("🚩 People's Investment Bureau")
st.caption("Gabinete do Investidor Popular — guarda posições, analisa e pontua (1–10).")

# ---------- SUPABASE ----------
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")

use_supabase = False
supabase = None

if SUPABASE_URL and SUPABASE_KEY and SUPABASE_AVAILABLE:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            res = supabase.table("portfolio").select("*").limit(1).execute()
            if res.data is not None:
                use_supabase = True
        except Exception as e:
            st.warning(f"Supabase conectado, mas tabela 'portfolio' inacessível: {e}")
    except Exception as e:
        st.error(f"Não foi possível conectar ao Supabase: {e}")
else:
    st.info("Supabase não configurado. O app usará armazenamento local.")

# ---------- HELPERS ----------
def local_load_portfolio():
    if os.path.exists(DATA_FILE):
        try:
            return pd.read_csv(DATA_FILE, parse_dates=["invest_date"])
        except:
            return pd.DataFrame(columns=["ticker","invest_date","price","amount"])
    else:
        return pd.DataFrame(columns=["ticker","invest_date","price","amount"])

def local_save_portfolio(df):
    df.to_csv(DATA_FILE, index=False)

def supabase_load_portfolio():
    try:
        res = supabase.table("portfolio").select("*").execute()
        data = res.data
        if not data:
            return pd.DataFrame(columns=["ticker","invest_date","price","amount"])
        df = pd.DataFrame(data)
        df.columns = [c.lower() for c in df.columns]
        if "invest_date" in df.columns:
            df["invest_date"] = pd.to_datetime(df["invest_date"], errors="coerce")
        return df[["ticker","invest_date","price","amount"]]
    except:
        return pd.DataFrame(columns=["ticker","invest_date","price","amount"])

def supabase_save_row(row: dict):
    try:
        supabase.table("portfolio").insert(row).execute()
        return True
    except:
        return False

def supabase_delete_row(ticker, invest_date, price, amount):
    try:
        supabase.table("portfolio").delete().match({
            "ticker": ticker,
            "invest_date": invest_date if isinstance(invest_date,str) else str(invest_date),
            "price": price,
            "amount": amount
        }).execute()
        return True
    except:
        return False

def fetch_history(ticker, period="6mo"):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return None
        hist = hist.reset_index()
        hist.columns = hist.columns.str.lower()
        return hist[["date","close"]]
    except:
        return None

def plot_history_png(hist, ticker):
    fig, ax = plt.subplots(figsize=(7,3.2))
    ax.plot(hist["date"], hist["close"], color="#ff4d4d", linewidth=2)
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
    shares = invested_amount / invested_price if invested_price!=0 else 0
    current_value = shares * current_price
    profit = current_value - invested_amount
    roi = (profit / invested_amount)*100 if invested_amount!=0 else 0
    return current_price, shares, current_value, profit, roi

def auto_review_text(hist, roi):
    start = hist["close"].iloc[0]
    end = hist["close"].iloc[-1]
    pct = (end-start)/start*100
    vol = hist["close"].pct_change().std()*100
    trend = "estável"
    if pct>8: trend="forte alta"
    elif pct>2: trend="alta"
    elif pct<-8: trend="forte queda"
    elif pct<-2: trend="queda"
    vol_text = "alta volatilidade" if vol>2 else "baixa volatilidade"
    score = 10 if roi>=30 else 9 if roi>=15 else 8 if roi>=10 else 7 if roi>=5 else 6 if roi>=0 else 5 if roi>=-5 else 4 if roi>=-10 else 3 if roi>=-20 else 1
    text = f"A ação apresenta {trend} ({pct:.2f}% no período). Observa-se {vol_text}. Índice de desempenho popular: {score}/10. Esta é uma análise automática."
    return text, score

def df_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

# ---------- SESSION STATE ----------
if "portfolio_df" not in st.session_state:
    st.session_state["portfolio_df"] = supabase_load_portfolio() if use_supabase else local_load_portfolio()
if "last_stock" not in st.session_state:
    st.session_state["last_stock"] = None

def update_portfolio(new_df):
    st.session_state["portfolio_df"] = new_df
    if use_supabase:
        pass  # Already saved individually
    else:
        local_save_portfolio(new_df)

# ---------- SIDEBAR ----------
st.sidebar.markdown("## Configuração")
st.sidebar.write(f"Storage: **{'Supabase' if use_supabase else 'Local'}**")
st.sidebar.markdown("---")
st.sidebar.write("Dicas: experimenta tickers como `AAPL`, `NVDA`, `TSLA`, `MSFT`.")

# ---------- PAGES ----------
page = st.sidebar.radio("Ir para", ["Analisar ação","Portfólio","Export/Import"])

# ---------- ANÁLISE DE AÇÃO ----------
if page=="Analisar ação":
    st.header("📈 Analisar ação")
    with st.form("analisar_form"):
        ticker = st.text_input("Símbolo / ticker (ex: AAPL, NVDA):").strip().upper()
        invested_price = st.number_input("Preço por ação na compra (€):", min_value=0.0, step=0.01)
        invested_amount = st.number_input("Montante total investido (€):", min_value=0.0, step=1.0)
        invest_date = st.date_input("Data do investimento:", value=date.today())
        submitted = st.form_submit_button("🔎 Obter dados")

    if submitted:
        hist = fetch_history(ticker)
        if hist is None:
            st.error("Ticker inválido ou sem dados.")
        else:
            current, shares, current_value, profit, roi = calc_metrics(hist, invested_price, invested_amount)
            st.metric("Preço atual", f"€{current:.2f}")
            st.metric("Valor atual", f"€{current_value:.2f}")
            st.metric("Lucro / Prejuízo", f"€{profit:.2f} ({roi:.2f}%)")
            st.image(plot_history_png(hist, ticker))
            review_text, score = auto_review_text(hist, roi)
            st.subheader("🧠 Análise automática")
            st.write(review_text)
            st.markdown(f"### 🔥 Nota Popular: **{score}/10**")

            st.session_state["last_stock"] = {
                "ticker": ticker,
                "invest_date": invest_date.strftime("%Y-%m-%d"),
                "price": invested_price,
                "amount": invested_amount
            }

    if st.session_state["last_stock"]:
        if st.button("➕ Adicionar ao portfólio"):
            row = st.session_state["last_stock"]
            new_df = pd.concat([st.session_state["portfolio_df"], pd.DataFrame([row])], ignore_index=True)
            if use_supabase:
                if supabase_save_row(row):
                    st.success(f"{row['ticker']} adicionado ao Supabase!")
                else:
                    st.error("Erro ao gravar no Supabase.")
                update_portfolio(supabase_load_portfolio())
            else:
                update_portfolio(new_df)
                st.success(f"{row['ticker']} adicionado localmente!")
            st.session_state["last_stock"] = None

# ---------- PORTFÓLIO ----------
elif page=="Portfólio":
    st.header("📂 Portfólio do Povo")
    portfolio_df = st.session_state["portfolio_df"]
    if portfolio_df.empty:
        st.info("Portfólio vazio — adiciona posições na página 'Analisar ação'.")
    else:
        total_invested = portfolio_df["amount"].sum()
        total_now = 0.0
        total_profit = 0.0
        for idx,r in portfolio_df.iterrows():
            hist = fetch_history(r["ticker"])
            if hist is not None:
                _,_,current_value,profit,_ = calc_metrics(hist,r["price"],r["amount"])
                total_now += current_value
                total_profit += profit
        st.metric("Total investido", f"€{total_invested:.2f}")
        st.metric("Valor atual total (estimado)", f"€{total_now:.2f}")
        st.metric("Lucro total (estimado)", f"€{total_profit:.2f}")
        st.markdown("---")
        for idx,row in portfolio_df.iterrows():
            ticker = row["ticker"]
            price = row["price"]
            amount = row["amount"]
            invest_date = row["invest_date"]
            hist = fetch_history(ticker)
            with st.expander(f"🔖 {ticker} — Investido €{amount:.2f}"):
                if hist is None:
                    st.write("Sem dados históricos.")
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
                    c1,c2 = st.columns([1,1])
                    c1.download_button("📥 Baixar gráfico", data=buf.getvalue(), file_name=f"{ticker}_hist.png", mime="image/png")
                    if c2.button("🗑️ Remover", key=f"rm_{idx}"):
                        new_df = portfolio_df.drop(idx).reset_index(drop=True)
                        if use_supabase:
                            if supabase_delete_row(ticker, invest_date, price, amount):
                                st.success("Removido do Supabase.")
                                update_portfolio(supabase_load_portfolio())
                        else:
                            update_portfolio(new_df)
                            st.success("Removido localmente.")

        st.markdown("---")
        st.download_button("⬇️ Exportar portfólio (CSV)", data=df_to_csv_bytes(portfolio_df), file_name="portfolio.csv", mime="text/csv")

# ---------- EXPORT / IMPORT ----------
elif page=="Export/Import":
    st.header("📦 Exportar / Importar")
    st.write("Exporta CSV ou importa CSV com colunas: ticker,invest_date,price,amount")
    if st.button("Exportar CSV"):
        st.download_button("Descarregar CSV", data=df_to_csv_bytes(st.session_state["portfolio_df"]),
                           file_name="portfolio.csv", mime="text/csv")
    uploaded = st.file_uploader("Importar CSV", type=["csv"])
    if uploaded:
        try:
            df_new = pd.read_csv(uploaded, parse_dates=["invest_date"])
            if not {"ticker","invest_date","price","amount"}.issubset(df_new.columns):
                st.error("CSV inválido.")
            else:
                if use_supabase:
                    count=0
                    for _,r in df_new.iterrows():
                        row = {"ticker":r["ticker"].upper(),"invest_date":str(r["invest_date"]),
                               "price":float(r["price"]),"amount":float(r["amount"])}
                        if supabase_save_row(row):
                            count+=1
                    st.success(f"{count} linhas importadas no Supabase")
                    update_portfolio(supabase_load_portfolio())
                else:
                    new_df2 = pd.concat([st.session_state["portfolio_df"], df_new], ignore_index=True)
                    update_portfolio(new_df2)
                    st.success("CSV importado localmente")
        except Exception as e:
            st.error(f"Erro a importar CSV: {e}")

st.markdown("---")
st.caption("Feito em solidariedade — Comrade GPT 🚩")
