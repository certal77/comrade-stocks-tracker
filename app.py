import streamlit as st
import yfinance as yf
from datetime import date
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(page_title="📈 Comrade Stocks Tracker", layout="wide")

st.title("📈 Comrade Stocks Tracker")
st.write("Analisa o teu investimento e vê a tendência do mercado — versão camarada 💪")

ticker_input = st.text_input("Ticker (ex: AAPL, TSLA, MSFT):").strip().upper()

if ticker_input:
    invest_date = st.date_input("Data do investimento:", value=date.today())
    invested_price = st.number_input("Preço por ação (€):", min_value=0.0, step=0.01, format="%.2f")
    invested_amount = st.number_input("Montante investido (€):", min_value=0.0, step=1.0, format="%.2f")

    if st.button("Analisar"):
        if invested_price <= 0 or invested_amount <= 0:
            st.warning("Define um preço e montante válidos.")
        else:
            try:
                ticker = yf.Ticker(ticker_input)
                hist = ticker.history(period="6mo")
                if hist.empty:
                    st.error("Ticker inválido ou sem histórico.")
                else:
                    current_price = hist['Close'].iloc[-1]
                    shares = invested_amount / invested_price
                    current_value = shares * current_price
                    profit = current_value - invested_amount
                    roi = (profit / invested_amount) * 100

                    st.subheader("📊 Resultados")
                    st.write(f"Preço atual: **{current_price:.2f} €**")
                    st.write(f"Valor atual do investimento: **{current_value:.2f} €**")
                    st.write(f"Lucro/Prejuízo: **{profit:.2f} € ({roi:.2f}%)**")

                    st.subheader("📈 Gráfico (últimos 6 meses)")
                    fig, ax = plt.subplots()
                    ax.plot(hist.index, hist['Close'])
                    ax.set_title(ticker_input)
                    ax.set_xlabel("Data")
                    ax.set_ylabel("Preço (€)")
                    st.pyplot(fig)

                    st.subheader("🧠 Análise automática")
                    if roi > 10:
                        st.success("Alta forte 📈 — provável otimismo no mercado.")
                    elif roi < -10:
                        st.error("Queda significativa 📉 — possível risco ou resultados fracos.")
                    else:
                        st.warning("Variação moderada 📊 — estabilidade ou espera de notícias.")
            except Exception as e:
                st.error(f"Erro: {e}")
else:
    st.info("Insere o símbolo da ação para começar.")

st.sidebar.write("Feito com ❤️ por Comrade GPT")

