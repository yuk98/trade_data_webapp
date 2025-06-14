# app.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import data_handler

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="무역 & KOSPI 대시보드", page_icon="📈")

# --- 커스텀 CSS ---
st.markdown("""
<style>
    body { font-family: 'Pretendard', sans-serif; }
    /* 컨트롤 패널과 메트릭 카드 스타일은 유지 */
    .control-panel { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #e9ecef; margin-top: 20px; margin-bottom: 20px; }
    .metric-card { background-color: #ffffff; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.04); height: 100%; }
    .metric-card h3 { font-size: 1.1rem; color: #495057; margin-bottom: 5px; }
    .metric-card p { font-size: 1.5rem; font-weight: 600; color: #212529; }
</style>
""", unsafe_allow_html=True)


# --- 데이터 로드 및 유효성 검사 ---
trade_data_processed = data_handler.load_trade_data()
daily_kospi_data, kospi_status_msg = data_handler.get_and_update_kospi_data()

if kospi_status_msg:
    st.warning(kospi_status_msg)

if trade_data_processed is None:
    st.error("🚨 무역 데이터 파일('trade_data.csv') 로딩 실패: 스크립트와 동일한 폴더에 파일이 있는지 확인해주세요.")
    st.stop()
if daily_kospi_data is None:
    st.error("🚨 KOSPI 데이터 로딩 또는 업데이트에 실패했습니다. 인터넷 연결을 확인해주세요.")
    st.stop()

kospi_data_processed = data_handler.process_kospi_for_chart(daily_kospi_data)

# --- 세션 상태 초기화 ---
if 'init_done' not in st.session_state:
    st.session_state.selected_country = '총합'
    st.session_state.is_12m_trailing = False
    st.session_state.show_yoy_growth = False
    st.session_state.selected_period = '전체 기간'
    st.session_state.start_date = trade_data_processed['Date'].min()
    st.session_state.end_date = trade_data_processed['Date'].max()
    st.session_state.init_done = True

st.title('📈 무역 데이터 & KOSPI 200 대시보드')

# --- 데이터 필터링 및 통합 ---
trade_filtered_df = trade_data_processed[
    (trade_data_processed['country_name'] == st.session_state.selected_country) &
    (trade_data_processed['Date'] >= st.session_state.start_date) &
    (trade_data_processed['Date'] <= st.session_state.end_date)
].copy()
trade_filtered_df['Date'] = pd.to_datetime(trade_filtered_df['Date']) + pd.offsets.MonthEnd(0)
display_df = pd.merge(trade_filtered_df, kospi_data_processed, on='Date', how='left')

# --- 메트릭 카드 UI ---
if not display_df.empty:
    latest_trade_data = display_df.dropna(subset=['export_amount']).sort_values('Date').iloc[-1]
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("최신 수출액", f"${latest_trade_data['export_amount']/1e9:.2f}B")
    with m2:
        st.metric("최신 수입액", f"${latest_trade_data['import_amount']/1e9:.2f}B")
    with m3:
        st.metric("최신 무역수지", f"${latest_trade_data['trade_balance']/1e9:.2f}B")

# --- 차트 생성 ---
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
        x=alt.X('Date:T', title=None, axis=alt.Axis(labels=False)),
        y=alt.Y('kospi_price:Q', title='KOSPI 200 (Log)', scale=alt.Scale(type="log"), axis=alt.Axis(tickCount=4)),
    )
    kospi_points = kospi_line.mark_circle(size=35).encode(opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    kospi_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)
    kospi_chart = alt.layer(kospi_line, kospi_points, kospi_rule, tooltip_layer).properties(height=100, title="KOSPI 200 지수")

    trade_melted_df = display_df.melt(id_vars=['Date'], value_vars=cols_to_use, var_name='지표', value_name='값')
    col_map = {export_col: '수출', import_col: '수입', balance_col: '무역수지'}
    trade_melted_df['지표'] = trade_melted_df['지표'].map(col_map)
    
    if st.session_state.show_yoy_growth: y_title_trade, y_title_balance = "수출·수입 YoY 성장률 (%)", "무역수지 YoY 성장률 (%)"
    else: y_title_trade, y_title_balance = "수출·수입 금액", "무역수지 금액"
    if st.session_state.is_12m_trailing: y_title_trade, y_title_balance = f"12개월 누적 {y_title_trade}", f"12개월 누적 {y_title_balance}"

    color_scheme = alt.Color('지표:N', scale=alt.Scale(domain=['수출', '수입', '무역수지'], range=['#0d6efd', '#dc3545', '#198754']), legend=alt.Legend(title="구분", orient="top-left"))
    trade_base_chart = alt.Chart(trade_melted_df)
    
    trade_line = trade_base_chart.mark_line(strokeWidth=2.5, clip=True).encode(x=alt.X('Date:T', title=None, axis=alt.Axis(format='%Y-%m', labelAngle=-45)), y=alt.Y('값:Q', title=y_title_trade, axis=alt.Axis(tickCount=5)), color=color_scheme,).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['수출', '수입']))
    trade_bar = trade_base_chart.mark_bar(opacity=0.7, clip=True).encode(x=alt.X('Date:T'), y=alt.Y('값:Q', title=y_title_balance, axis=alt.Axis(tickCount=5)), color=color_scheme,).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['무역수지']))
    trade_points = trade_base_chart.mark_circle(size=35).encode(color=color_scheme, opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    trade_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)
    trade_chart = alt.layer(trade_line, trade_bar, trade_rule, trade_points, tooltip_layer).resolve_scale(y='independent').properties(height=350, title=f"{st.session_state.selected_country} 무역 데이터")

    final_combined_chart = alt.vconcat(kospi_chart, trade_chart, spacing=5).resolve_legend(color="independent").configure_view(strokeWidth=0).configure_title(fontSize=16, anchor="start", subtitleFontSize=12)
    st.altair_chart(final_combined_chart, use_container_width=True)

# --- [수정] 컨트롤 패널 UI ---
st.markdown("---")
st.markdown("##### ⚙️ 데이터 보기 옵션")

# st.radio를 사용하여 안정적인 토글 구현
control_cols = st.columns(3)
with control_cols[0]:
    # 국가 선택
    selected_country = st.selectbox(
        '**국가 선택**',
        options=['총합', '미국', '중국'],
        index=['총합', '미국', '중국'].index(st.session_state.selected_country)
    )
    if selected_country != st.session_state.selected_country:
        st.session_state.selected_country = selected_country
        st.rerun()

with control_cols[1]:
    # 데이터 형태 선택
    options_12m = ['월별', '12개월 누적']
    selected_12m = st.radio(
        '**데이터 형태 (무역)**',
        options_12m,
        index=1 if st.session_state.is_12m_trailing else 0,
        horizontal=True,
    )
    new_is_12m_trailing = (selected_12m == '12개월 누적')
    if new_is_12m_trailing != st.session_state.is_12m_trailing:
        st.session_state.is_12m_trailing = new_is_12m_trailing
        st.rerun()

with control_cols[2]:
    # 표시 단위 선택
    options_yoy = ['금액', 'YoY']
    selected_yoy = st.radio(
        '**표시 단위 (무역)**',
        options_yoy,
        index=1 if st.session_state.show_yoy_growth else 0,
        horizontal=True
    )
    new_show_yoy_growth = (selected_yoy == 'YoY')
    if new_show_yoy_growth != st.session_state.show_yoy_growth:
        st.session_state.show_yoy_growth = new_show_yoy_growth
        st.rerun()

# --- 기간 선택 UI ---
st.markdown("---")
st.markdown('**기간 빠르게 탐색하기**')
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

# --- 데이터 출처 정보 ---
st.markdown("---")
with st.container(border=True):
    st.subheader("데이터 출처 정보")
    st.markdown("""
    - **무역 데이터**: `trade_data.csv` 파일에서 로드합니다.
    - **KOSPI 200 데이터**: `yfinance` 라이브러리를 통해 **Yahoo Finance**에서 실시간으로 가져와 `kospi200.csv` 파일로 관리 및 업데이트합니다.
    - **원본 데이터 참조**: [관세청 품목별 수출입 실적 (OpenAPI)](https://www.data.go.kr/data/15101612/openapi.do)
    """)
