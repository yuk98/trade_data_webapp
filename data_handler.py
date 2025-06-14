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
    이제 'Date' 컬럼을 기준으로 처리합니다.
    """
    try:
        trade_df = pd.read_csv(filename)
    except FileNotFoundError:
        return None

    # 'year_month' 대신 'Date' 컬럼을 사용
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
    KOSPI 200 데이터를 관리하는 함수. (이전과 동일)
    """
    today = pd.Timestamp.now().strftime('%Y-%m-%d')
    ticker = yf.Ticker("^KS200")

    if not os.path.exists(filename):
        status_message = f"'{filename}' 파일을 찾을 수 없어 2000년부터 현재까지 전체 데이터를 다운로드합니다..."
        try:
            hist_daily = ticker.history(start='2000-01-01', end=today, interval="1d").reset_index()
            if hist_daily.empty:
                return None, "KOSPI 데이터 다운로드에 실패했습니다. 티커를 확인해주세요."
            hist_daily.to_csv(filename, index=False)
            return hist_daily, f"{status_message}\n\nKOSPI 데이터 다운로드 및 파일 생성 완료!"
        except Exception as e:
            return None, f"KOSPI 데이터 다운로드 중 오류 발생: {e}"

    existing_df = pd.read_csv(filename)
    existing_df['Date'] = pd.to_datetime(existing_df['Date']).dt.tz_localize(None)
    last_date_in_file = existing_df['Date'].max()

    if last_date_in_file.date() < pd.Timestamp(today).date():
        status_message = f"기존 KOSPI 데이터가 최신이 아닙니다. '{last_date_in_file.strftime('%Y-%m-%d')}' 이후 데이터를 업데이트합니다..."
        start_for_update = (last_date_in_file + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        try:
            new_data = ticker.history(start=start_for_update, end=today, interval="1d").reset_index()
            if not new_data.empty:
                new_data['Date'] = pd.to_datetime(new_data['Date']).dt.tz_localize(None)
                updated_df = pd.concat([existing_df, new_data]).drop_duplicates(subset=['Date'], keep='last')
                updated_df.to_csv(filename, index=False)
                return updated_df, f"{status_message}\n\nKOSPI 데이터 업데이트 완료!"
            else:
                return existing_df, "KOSPI 데이터가 이미 최신입니다. (추가할 데이터 없음)"
        except Exception as e:
            return existing_df, f"KOSPI 데이터 업데이트 중 오류 발생: {e} (기존 데이터를 사용합니다.)"
    else:
        return existing_df, "KOSPI 데이터가 이미 최신입니다."

def process_kospi_for_chart(daily_df):
    """
    일별 KOSPI 데이터를 월말 종가 기준 월별 대표 날짜('year_month') 데이터로 전처리합니다.
    """
    if daily_df is None:
        return None
    kospi_monthly = daily_df.copy()
    kospi_monthly['Date'] = pd.to_datetime(kospi_monthly['Date'])
    kospi_monthly = kospi_monthly.set_index('Date').resample('M').last().reset_index()
    # 'year_month' 컬럼 생성
    kospi_monthly['year_month'] = pd.to_datetime(kospi_monthly['Date'])
    return kospi_monthly[['year_month', 'Close']].rename(columns={'Close': 'kospi_price'})
