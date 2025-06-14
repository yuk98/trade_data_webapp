# app.py

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import data_handler  # data_handler.py 파일을 임포트

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="무역 & KOSPI 대시보드", page_icon="📈")

# --- [수정] URL 쿼리 파라미터 처리 로직 추가 ---
# 토글 버튼 클릭 시 발생하는 URL 변경을 감지하여 세션 상태를 업데이트합니다.
params = st.query_params
if "toggle_12m" in params:
    st.session_state.is_12m_trailing = params.get("toggle_12m") == "True"
    st.rerun()

if "toggle_yoy" in params:
    st.session_state.show_yoy_growth = params.get("toggle_yoy") == "True"
    st.rerun()


# --- 커스텀 CSS ---
st.markdown("""
<style>
    body { font-family: 'Pretendard', sans-serif; }
    .control-panel { background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #e9ecef; margin-bottom: 20px; margin-top: 20px; }
    /* ... (이전과 동일한 CSS 코드) ... */
</style>
""", unsafe_allow_html=True)

# --- 데이터 로드 ---
trade_data_processed = data_handler.load_trade_data()
daily_kospi_data, kospi_status_msg = data_handler.get_and_update_kospi_data()
st.info(kospi_status_msg)

if trade_data_processed is None:
    st.error("🚨 무역 데이터 파일('trade_data.csv') 로딩 실패: 파일명과 'Date' 컬럼이 존재하는지 확인해주세요.")
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
trade_filtered_df['Date'] = pd.to_datetime(trade_filtered_df['Date']).dt.to_period('M').dt.to_timestamp('S')
display_df = pd.merge(trade_filtered_df, kospi_data_processed, on='Date', how='left')

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
        y=alt.Y('kospi_price:Q', title='KOSPI 200', axis=alt.Axis(tickCount=4)),
    )
    kospi_points = kospi_line.mark_circle(size=35).encode(opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    kospi_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)
    
    kospi_chart = alt.layer(
        kospi_line, kospi_points, kospi_rule, tooltip_layer
    ).properties(height=100, title="KOSPI 200 지수")

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
    
    trade_chart = alt.layer(
        trade_line, trade_bar, trade_rule, trade_points, tooltip_layer
    ).resolve_scale(y='independent').properties(height=350, title=f"{st.session_state.selected_country} 무역 데이터")

    final_combined_chart = alt.vconcat(
        kospi_chart,
        trade_chart,
        spacing=5
    ).resolve_legend(
        color="independent"
    ).configure_view(
        strokeWidth=0
    ).configure_title(
        fontSize=16, anchor="start", subtitleFontSize=12
    )
    
    st.altair_chart(final_combined_chart, use_container_width=True)

# --- [이동] 컨트롤 패널 UI 위치 변경 ---
st.markdown('<div class="control-panel">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1.5, 2, 2])
with c1:
    new_country = st.selectbox('**국가 선택**', options=['총합', '미국', '중국'], index=['총합', '미국', '중국'].index(st.session_state.selected_country), key='country_select_bottom')
    if new_country != st.session_state.selected_country:
        st.session_state.selected_country = new_country
        st.rerun()
with c2:
    st.markdown('**데이터 형태 (무역)**')
