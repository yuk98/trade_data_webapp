# data_handler.py

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import os
from datetime import datetime

@st.cache_data
def load_trade_data(filename="trade_data.csv"):
    """
    무역 데이터를 로드하고 모든 파생 지표를 계산합니다.
    """
    try:
        trade_df = pd.read_csv(filename)
    except FileNotFoundError:
        return None

    trade_df['Date'] = pd.to_datetime(trade_df['Date'])
    trade_df = trade_df.sort_values(by=['country_name', 'Date']).reset_index(drop=True)

    for col in ['export_amount', 'import_amount', 'trade_balance']:
        trade_df[f'{col}_trailing_12m'] = trade_df.groupby('country_name')[col].rolling(window=12, min_periods=12).sum().reset_index(level=0, drop=True)
        trade_df[f'{col}_yoy_growth'] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
        trade_df[f'{col}_trailing_12m_yoy_growth'] = trade_df.groupby('country_name')[f'{col}_trailing_12m'].pct_change(periods=12) * 100

    trade_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return trade_df

@st.cache_data
def get_and_update_kospi_data(filename="kospi200.csv"):
    """
    KOSPI 200 데이터를 관리하며, 성공 시에는 메시지를 반환하지 않습니다.
    """
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    ticker = yf.Ticker("^KS200")

    if not os.path.exists(filename):
        try:
            hist_daily = ticker.history(start='1991-01-01', end=today, interval="1d").reset_index()
            if hist_daily.empty:
                return None, "KOSPI 데이터 다운로드에 실패했습니다. 티커나 인터넷 연결을 확인해주세요."
            
            hist_daily['Date'] = pd.to_datetime(hist_daily['Date']).dt.tz_localize(None)
            hist_daily.to_csv(filename, index=False)
            return hist_daily, None  # [수정] 성공 시 메시지 없음
        except Exception as e:
            return None, f"KOSPI 데이터 다운로드 중 오류 발생: {e}"

    existing_df = pd.read_csv(filename)
    existing_df['Date'] = pd.to_datetime(existing_df['Date']).dt.tz_localize(None)
    last_date_in_file = existing_df['Date'].max()

    if last_date_in_file.date() < pd.Timestamp.now().date():
        start_for_update = (last_date_in_file + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        try:
            new_data = ticker.history(start=start_for_update, end=today, interval="1d").reset_index()
            if not new_data.empty:
                new_data['Date'] = pd.to_datetime(new_data['Date']).dt.tz_localize(None)
                updated_df = pd.concat([existing_df, new_data]).drop_duplicates(subset=['Date'], keep='last')
                updated_df.to_csv(filename, index=False)
                return updated_df, None  # [수정] 성공 시 메시지 없음
            else:
                return existing_df, None  # [수정] 성공 시 메시지 없음
        except Exception as e:
            return existing_df, f"KOSPI 데이터 업데이트 중 오류 발생: {e} (기존 데이터를 사용합니다.)"
    else:
        return existing_df, None  # [수정] 성공 시 메시지 없음

def process_kospi_for_chart(daily_df):
    """
    일별 KOSPI 데이터를 월말(Month-End) 기준 월별 데이터로 전처리합니다.
    """
    if daily_df is None:
        return None
    kospi_monthly = daily_df.copy()
    kospi_monthly['Date'] = pd.to_datetime(kospi_monthly['Date'])
    # [수정] 월초('MS') 기준 -> 월말('M') 기준으로 변경
    kospi_monthly = kospi_monthly.set_index('Date').resample('M').last().reset_index()
    return kospi_monthly[['Date', 'Close']].rename(columns={'Close': 'kospi_price'})
