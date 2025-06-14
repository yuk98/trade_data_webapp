import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import numpy as np
import yfinance as yf
import os

# --- 페이지 설정 (가장 먼저 호출) ---
st.set_page_config(layout="wide", page_title="무역 & KOSPI 대시보드", page_icon="📈")

# --- 커스텀 CSS 스타일 ---
st.markdown("""
<style>
    body { font-family: 'Pretendard', sans-serif; }
    .metric-container {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
        transition: box-shadow 0.3s ease-in-out;
    }
    .metric-container:hover {
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .metric-label {
        font-size: 1rem;
        font-weight: 500;
        color: #4A4A4A;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1E1E1E;
        margin-bottom: 8px;
    }
    .metric-delta-group {
        font-size: 0.85rem;
        text-align: right;
        color: #555;
    }
    .delta-positive {
        color: #D32F2F; /* Red for positive (import/trade deficit are negative indicators) */
        font-weight: 500;
    }
    .delta-negative {
        color: #388E3C; /* Green for negative */
        font-weight: 500;
    }
    /* Inverting colors for export and trade balance */
    .delta-positive.good {
        color: #388E3C;
    }
    .delta-negative.good {
        color: #D32F2F;
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 로드 및 관리 함수들 ---

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
            return hist_daily, None
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
                return updated_df, None
            else:
                return existing_df, None
        except Exception as e:
            return existing_df, f"KOSPI 데이터 업데이트 중 오류 발생: {e} (기존 데이터를 사용합니다.)"
    else:
        return existing_df, None

def process_kospi_for_chart(daily_df):
    """
    일별 KOSPI 데이터를 월말(Month-End) 기준 월별 데이터로 전처리합니다.
    """
    if daily_df is None:
        return None
    kospi_monthly = daily_df.copy()
    kospi_monthly['Date'] = pd.to_datetime(kospi_monthly['Date'])
    kospi_monthly = kospi_monthly.set_index('Date').resample('M').last().reset_index()
    return kospi_monthly[['Date', 'Close']].rename(columns={'Close': 'kospi_price'})


# --- 메인 앱 로직 시작 ---

# 데이터 로드 및 유효성 검사
trade_data_processed = load_trade_data()
daily_kospi_data, kospi_status_msg = get_and_update_kospi_data()

if kospi_status_msg:
    st.warning(kospi_status_msg)

if trade_data_processed is None:
    st.error("🚨 무역 데이터 파일('trade_data.csv') 로딩 실패: 스크립트와 동일한 폴더에 파일이 있는지 확인해주세요.")
    st.stop()
if daily_kospi_data is None:
    st.error("🚨 KOSPI 데이터 로딩 또는 업데이트에 실패했습니다. 인터넷 연결을 확인해주세요.")
    st.stop()

kospi_data_processed = process_kospi_for_chart(daily_kospi_data)

# 세션 상태 초기화
if 'init_done' not in st.session_state:
    st.session_state.selected_country = '총합'
    st.session_state.is_12m_trailing = False
    st.session_state.show_yoy_growth = False
    st.session_state.selected_period = '전체 기간'
    st.session_state.start_date = trade_data_processed['Date'].min()
    st.session_state.end_date = trade_data_processed['Date'].max()
    st.session_state.init_done = True

st.title('📈 무역 데이터 & KOSPI 200 대시보드')

# 데이터 필터링 및 통합
trade_filtered_df = trade_data_processed[
    (trade_data_processed['country_name'] == st.session_state.selected_country) &
    (trade_data_processed['Date'] >= st.session_state.start_date) &
    (trade_data_processed['Date'] <= st.session_state.end_date)
].copy()
trade_filtered_df['Date'] = pd.to_datetime(trade_filtered_df['Date']) + pd.offsets.MonthEnd(0)
display_df = pd.merge(trade_filtered_df, kospi_data_processed, on='Date', how='left')

# 메트릭 카드 UI
if not display_df.empty:
    latest_date = display_df['Date'].max()
    prev_month_date = latest_date - pd.DateOffset(months=1)
    prev_year_date = latest_date - pd.DateOffset(years=1)
    
    latest_data = display_df[display_df['Date'] == latest_date]
    prev_month_data = display_df[display_df['Date'] == prev_month_date]
    prev_year_data = display_df[display_df['Date'] == prev_year_date]

    metrics_to_show = {
        '수출액': ('export_amount', 'good'),
        '수입액': ('import_amount', 'bad'),
        '무역수지': ('trade_balance', 'good')
    }
    cols = st.columns(3)
    for i, (metric_label, (col_name, delta_type)) in enumerate(metrics_to_show.items()):
        with cols[i]:
            with st.container():
                st.markdown('<div class="metric-container">', unsafe_allow_html=True)
                
                current_value = latest_data[col_name].iloc[0] if not latest_data.empty else 0
                
                st.markdown(f"<div class='metric-label'>{latest_date.strftime('%Y년 %m월')} {metric_label}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-value'>${current_value/1e9:.2f}B</div>", unsafe_allow_html=True)

                # 전월 대비(MoM) 계산
                prev_month_value = prev_month_data[col_name].iloc[0] if not prev_month_data.empty else None
                mom_delta_str = "---"
                if prev_month_value is not None and prev_month_value != 0:
                    mom_pct = ((current_value - prev_month_value) / abs(prev_month_value)) * 100
                    color_class = "delta-positive" if mom_pct > 0 else "delta-negative"
                    if delta_type == 'good':
                        color_class += " good"
                    mom_delta_str = f'<span class="{color_class}">{mom_pct:+.1f}%</span>'

                # 전년 동기 대비(YoY) 계산
                prev_year_value = prev_year_data[col_name].iloc[0] if not prev_year_data.empty else None
                yoy_delta_str = "---"
                if prev_year_value is not None and prev_year_value != 0:
                    yoy_pct = ((current_value - prev_year_value) / abs(prev_year_value)) * 100
                    color_class = "delta-positive" if yoy_pct > 0 else "delta-negative"
                    if delta_type == 'good':
                        color_class += " good"
                    yoy_delta_str = f'<span class="{color_class}">{yoy_pct:+.1f}%</span>'
                
                st.markdown(f"""
                <div class="metric-delta-group">
                    전월 대비: <b>{mom_delta_str}</b><br>
                    전년 대비: <b>{yoy_delta_str}</b>
                </div>
                """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)


# 차트 생성
if not display_df.empty:
    base_col_names = ['export_amount', 'import_amount', 'trade_balance']
    if st.session_state.is_12m_trailing:
        if st.session_state.show_yoy_growth: cols_to_use = [f'{c}_trailing_12m_yoy_growth' for c in base_col_names]
        else: cols_to_use = [f'{c}_trailing_12m' for c in base_col_names]
    else:
        if st.session_state.show_yoy_growth: cols_to_use = [f'{c}_yoy_growth' for c in base_col_names]
        else: cols_to_use = base_col_names
    export_col, import_col, balance_col = cols_to_use

    nearest_selection = alt.selection_point(nearest=True, on='mouseover', fields=['Date'], empty=False)
    x_axis_scale = alt.Scale(domain=[st.session_state.start_date, st.session_state.end_date])

    tooltip_layer = alt.Chart(display_df).mark_rule(color='transparent').encode(
        x='Date:T',
        tooltip=[
            alt.Tooltip('Date:T', title='날짜', format='%Y-%m'),
            alt.Tooltip('kospi_price:Q', title='KOSPI 200', format=',.2f'),
            alt.Tooltip(export_col, title=f"수출 ({st.session_state.selected_country})", format=f"{',' if not st.session_state.show_yoy_growth else ''}.2f"),
            alt.Tooltip(import_col, title=f"수입 ({st.session_state.selected_country})", format=f"{',' if not st.session_state.show_yoy_growth else ''}.2f"),
            alt.Tooltip(balance_col, title=f"무역수지 ({st.session_state.selected_country})", format=f"{',' if not st.session_state.show_yoy_growth else ''}.2f")
        ]
    ).add_params(nearest_selection)

    kospi_line = alt.Chart(display_df).mark_line(color='#FF9900', strokeWidth=2).encode(
        x=alt.X('Date:T', title=None, axis=alt.Axis(labels=False), scale=x_axis_scale),
        y=alt.Y('kospi_price:Q', title='KOSPI 200', axis=alt.Axis(tickCount=5, grid=False)),
    )
    kospi_points = kospi_line.mark_circle(size=35).encode(opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    kospi_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)
    kospi_chart = alt.layer(kospi_line, kospi_points, kospi_rule, tooltip_layer).properties(height=150, title="KOSPI 200 지수")

    trade_melted_df = display_df.melt(id_vars=['Date'], value_vars=cols_to_use, var_name='지표', value_name='값')
    col_map = {export_col: '수출', import_col: '수입', balance_col: '무역수지'}
    trade_melted_df['지표'] = trade_melted_df['지표'].map(col_map)
    
    if st.session_state.show_yoy_growth: y_title_trade, y_title_balance = "수출·수입 YoY 성장률 (%)", "무역수지 YoY 성장률 (%)"
    else: y_title_trade, y_title_balance = "수출·수입 금액", "무역수지 금액"
    if st.session_state.is_12m_trailing: y_title_trade, y_title_balance = f"12개월 누적 {y_title_trade}", f"12개월 누적 {y_title_balance}"

    color_scheme = alt.Color('지표:N', scale=alt.Scale(domain=['수출', '수입', '무역수지'], range=['#0d6efd', '#dc3545', '#198754']), legend=alt.Legend(title="구분", orient="top-left"))
    trade_base_chart = alt.Chart(trade_melted_df)
    
    trade_line = trade_base_chart.mark_line(strokeWidth=2.5, clip=True).encode(x=alt.X('Date:T', title=None, axis=alt.Axis(format='%Y-%m', labelAngle=-45), scale=x_axis_scale), y=alt.Y('값:Q', title=y_title_trade, axis=alt.Axis(tickCount=5, grid=False)), color=color_scheme,).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['수출', '수입']))
    trade_bar = trade_base_chart.mark_bar(opacity=0.7, clip=True).encode(x=alt.X('Date:T', scale=x_axis_scale), y=alt.Y('값:Q', title=y_title_balance, axis=alt.Axis(tickCount=5, grid=False)), color=color_scheme,).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['무역수지']))
    trade_points = trade_base_chart.mark_circle(size=35).encode(color=color_scheme, opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    trade_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)
    trade_chart = alt.layer(trade_line, trade_bar, trade_rule, trade_points, tooltip_layer).resolve_scale(y='independent').properties(height=350, title=f"{st.session_state.selected_country} 무역 데이터")

    final_combined_chart = alt.vconcat(kospi_chart, trade_chart, spacing=5).resolve_legend(color="independent").configure_view(strokeWidth=0).configure_title(fontSize=16, anchor="start", subtitleFontSize=12)
    st.altair_chart(final_combined_chart, use_container_width=True)

# 컨트롤 패널 UI
st.markdown("---")
st.markdown("##### ⚙️ 데이터 보기 옵션")
control_cols = st.columns(3)
with control_cols[0]:
    selected_country = st.selectbox('**국가 선택**', options=['총합', '미국', '중국'], index=['총합', '미국', '중국'].index(st.session_state.selected_country))
    if selected_country != st.session_state.selected_country:
        st.session_state.selected_country = selected_country
        st.rerun()
with control_cols[1]:
    options_12m = ['월별', '12개월 누적']
    selected_12m = st.radio('**데이터 형태 (무역)**', options_12m, index=1 if st.session_state.is_12m_trailing else 0, horizontal=True)
    new_is_12m_trailing = (selected_12m == '12개월 누적')
    if new_is_12m_trailing != st.session_state.is_12m_trailing:
        st.session_state.is_12m_trailing = new_is_12m_trailing
        st.rerun()
with control_cols[2]:
    options_yoy = ['금액', 'YoY']
    selected_yoy = st.radio('**표시 단위 (무역)**', options_yoy, index=1 if st.session_state.show_yoy_growth else 0, horizontal=True)
    new_show_yoy_growth = (selected_yoy == 'YoY')
    if new_show_yoy_growth != st.session_state.show_yoy_growth:
        st.session_state.show_yoy_growth = new_show_yoy_growth
        st.rerun()

# 기간 설정 UI
st.markdown("---")
st.markdown('**기간 설정**')
period_options = {'1년': 1, '3년': 3, '5년': 5, '10년': 10, '20년': 20, '전체 기간': 99}
period_cols = st.columns(len(period_options))
for i, (label, offset_years) in enumerate(period_options.items()):
    btn_type = "primary" if st.session_state.selected_period == label else "secondary"
    if period_cols[i].button(label, key=f'period_{label}', use_container_width=True, type=btn_type):
        end_date = trade_data_processed['Date'].max()
        if label == '전체 기간': start_date = trade_data_processed['Date'].min()
        else: start_date = end_date - pd.DateOffset(years=offset_years)
        st.session_state.start_date, st.session_state.end_date = start_date, end_date
        st.session_state.selected_period = label
        st.rerun()

# 데이터 출처 정보
st.markdown("---")
with st.container(border=True):
    st.subheader("데이터 출처 정보")
    st.markdown("""
    - **무역 데이터**: `trade_data.csv` 파일에서 로드합니다.
    - **KOSPI 200 데이터**: `yfinance` 라이브러리를 통해 **Yahoo Finance**에서 실시간으로 가져와 `kospi200.csv` 파일로 관리 및 업데이트합니다.
    - **원본 데이터 참조**: [관세청 품목별 수출입 실적 (OpenAPI)](https://www.data.go.kr/data/15101612/openapi.do)
    """)
