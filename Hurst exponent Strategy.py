#Hurst exponent with Trend following strategy
import pandas as pd
import numpy as np
import yfinance as yf
import pyfolio as pf
import pyfolio.timeseries as ts
import pyfolio.plotting as plotting
from hurst import compute_Hc
import seaborn as sns
import matplotlib.pyplot as plt

plt.style.use('ggplot')

import warnings
warnings.filterwarnings('ignore')

# Period for data download
start_date = "2010-01-01"
end_date = "2024-02-22"

# Period for Hurst exponent calculation
He_start = '2010-01-01'
He_end = '2020-12-31'

# Period for backtest
bt_start = '2020-01-01'
bt_end = '2024-02-22'

ticker_list_nyse = [
    'IBM', 'NVDA', 'AMZN', 'GOOGL', 'GOOG', 'TSLA', 'BRK-A', 'BRK-B',
    'JNJ', 'JPM', 'V', 'PG', 'MA', 'HD', 'DIS', 'PYPL', 'BAC', 'INTC','NYA'
]

price_df = yf.download(ticker_list_nyse, start=start_date, end=end_date)['Adj Close']
price_df.index = pd.to_datetime(price_df.index)


price_df_ffill = price_df.fillna(method='ffill').fillna(method='bfill')

price_data_He = price_df_ffill.loc[He_start:He_end]

price_data = price_df_ffill.loc[bt_start:bt_end]

def get_hurst(series):
    hurst_value = compute_Hc(series, kind='price')[0]
    return hurst_value

def hurst_plot(hurst, title_name):
    plt.subplots(figsize=(10, 7))
    hurst_plot_graph = ['grey' if x < 0.80 else 'green' for x in hurst.values]
    sns.barplot(x=hurst.index, y=hurst.values, palette=hurst_plot_graph)
    plt.axhline(0.80, color="red")
    plt.title(title_name, fontsize=14)
    plt.ylabel('Hurst Values', fontsize=12)
    plt.xticks(rotation=90)
    plt.show()

hurst = price_data_He[ticker_list_nyse].apply(get_hurst)

hurst_plot(hurst.sort_values(), 'Hurst Exponent of NYSE Stocks')

filtered_hurst = hurst.loc[hurst > 0.80].sort_values(ascending=False)

print(filtered_hurst)

strategy_parameters = {
    "slow_ma": 80,
    "fast_ma": 40,
    "high_low_window": 20,
    "volatility_window": 40,
    "breakout_window": 50,
    "COT_index_threshold_long": 30,
    "COT_index_threshold_short": 70,
    "pullback_level_long": -5,
    "pullback_level_short": 5
}
#Trend following strategy implementation
def trend_following_COT(strategy_parameters, ticker, price_data, hurst_data):
    price_data['fast_ma'] = price_data[ticker].ewm(span=strategy_parameters["fast_ma"]).mean()
    price_data['slow_ma'] = price_data[ticker].ewm(span=strategy_parameters["slow_ma"]).mean()

    price_data['trend'] = price_data['fast_ma'] > price_data['slow_ma']

    price_data['volatility'] = price_data[ticker].diff().rolling(strategy_parameters["volatility_window"]).std()

    price_data['highest'] = price_data[ticker].rolling(strategy_parameters["high_low_window"]).max()
    price_data['pullback_long'] = price_data['highest'].shift(1) - price_data[ticker]
    price_data['long_entry_signal'] = (price_data['pullback_long'] <= strategy_parameters["pullback_level_long"]) & price_data['trend']

    price_data['lowest'] = price_data[ticker].rolling(strategy_parameters["high_low_window"]).min()
    price_data['pullback_short'] = price_data[ticker] - price_data['lowest'].shift(1)
    price_data['short_entry_signal'] = (price_data['pullback_short'] <= strategy_parameters["pullback_level_short"]) & (~price_data['trend'])

    price_data['long_entry_signal'] &= (hurst_data[ticker] > 0.80)
    price_data['short_entry_signal'] &= (hurst_data[ticker] > 0.80)

    price_data['strategy_returns'] = np.where(price_data['long_entry_signal'], price_data[ticker].pct_change(), 0)
    price_data['strategy_returns'] = np.where(price_data['short_entry_signal'], -price_data[ticker].pct_change(), price_data['strategy_returns'])
    
    return price_data['strategy_returns']

strategy_returns = pd.DataFrame()

for asset in filtered_hurst.index:
    strategy_returns[asset] = trend_following_COT(strategy_parameters, asset, price_data, hurst)

plt.figure(figsize=(15, 7))
plt.title('Strategy Returns for All Tickers', fontsize=14)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Strategy Returns', fontsize=12)
plt.plot(strategy_returns)
plt.legend(strategy_returns.columns)
plt.show()

##Volatility based returns
ticker_list_nyse = ['NVDA', 'AMZN', 'TSLA', 'V', 'MA', 'HD']
volatility = price_data[ticker_list_nyse].pct_change().rolling(strategy_parameters["volatility_window"]).std()

inverse_volatility = 1 / volatility

weights = inverse_volatility.div(inverse_volatility.sum(axis=1), axis=0)

ticker_contribution = strategy_returns * weights

plt.figure(figsize=(15, 7))

plt.title('Volatility Weighted Strategy Returns', fontsize=14)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Strategy Returns', fontsize=12)

plt.plot(ticker_contribution)

plt.legend(ticker_list_nyse)

plt.show()

# Calculate the portfolio returns
portfolio_returns = ticker_contribution.sum(axis=1)

cum_portfolio_returns = (portfolio_returns+1).cumprod()

plt.figure(figsize=(15, 7))

plt.title('Cumulative Returns for Trend Following Portfolio', fontsize=14)
plt.xlabel('Year', fontsize=12)
plt.ylabel('Cumulative Returns', fontsize=12)

plt.plot(cum_portfolio_returns, color='purple')

plt.show()

spx_rets = price_data['NYA'].pct_change()
benchmark_rets = spx_rets
benchmark_rets.head()

perf_stats = ts.perf_stats(portfolio_returns, factor_returns=benchmark_rets)
print(perf_stats)


nya_rets = price_data['NYA'].pct_change()
benchmark_rets = nya_rets
benchmark_rets.head()

perf_stats = ts.perf_stats(portfolio_returns, factor_returns=benchmark_rets)
print(perf_stats)

portfolio_returns.index = pd.to_datetime(portfolio_returns.index)

drawdowns = ts.gen_drawdown_table(portfolio_returns)

if not drawdowns.empty:
    valley_index = drawdowns["drawdown"].idxmin()

    if valley_index >= 0 and valley_index < len(portfolio_returns.index):
        valley_date = portfolio_returns.index[valley_index]

        print("Valley date:", valley_date)
    else:
        print("Invalid valley index:", valley_index)
else:
    print("No drawdowns found.")

annual_volatility = ts.annual_volatility(portfolio_returns)
annual_return = ts.annual_return(portfolio_returns)
annual_sharpe_ratio = ts.annual_sharpe_ratio(portfolio_returns, annualization_factor=252)

print("Annual Volatility:", annual_volatility)
print("Annual Return:", annual_return)
print("Annual Sharpe Ratio:", annual_sharpe_ratio)

plotting.plot_drawdown_periods(portfolio_returns)
plotting.plot_rolling_returns(portfolio_returns)
plotting.plot_rolling_sharpe(portfolio_returns)

