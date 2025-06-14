import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import data_handler

# --- 페이지 설정 ---
st.set_page_config(layout="wide", page_title="무역 & KOSPI 대시보드", page_icon="📈")

# --- 데이터 로드 및 유효성 검사 ---
# data_handler.py가 별도 파일로 존재한다고 가정합니다.
# 만약 없다면 이 부분을 실제 데이터 로딩 코드로 대체해야 합니다.
try:
    trade_data_processed = data_handler.load_trade_data()
    daily_kospi_data, kospi_status_msg = data_handler.get_and_update_kospi_data()
except Exception as e:
    st.error(f"데이터 핸들러 로딩 중 오류 발생: {e}")
    st.info("`data_handler.py` 파일이 `app.py`와 동일한 폴더에 있는지, 필요한 함수(`load_trade_data`, `get_and_update_kospi_data`, `process_kospi_for_chart`)가 모두 정의되어 있는지 확인해주세요.")
    st.stop()


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
    st.session_state.is_12m_trailing = True
    st.session_state.show_yoy_growth = False
    st.session_state.init_done = True

st.title('📈 무역 데이터 & KOSPI 200 대시보드')

# --- 데이터 필터링 및 통합 ---
trade_filtered_df = trade_data_processed[
    (trade_data_processed['country_name'] == st.session_state.selected_country)
].copy()
trade_filtered_df['Date'] = pd.to_datetime(trade_filtered_df['Date']) + pd.offsets.MonthEnd(0)
display_df = pd.merge(trade_filtered_df, kospi_data_processed, on='Date', how='left').dropna(subset=['Date', 'kospi_price'])

# --- 메트릭 카드 UI ---
if not display_df.empty:
    latest_date = display_df['Date'].max()
    prev_month_date = latest_date - pd.DateOffset(months=1)
    prev_year_date = latest_date - pd.DateOffset(years=1)
    latest_data = display_df[display_df['Date'] == latest_date]
    prev_month_data = display_df[display_df['Date'] == prev_month_date]
    prev_year_data = display_df[display_df['Date'] == prev_year_date]
    metrics_to_show = {'수출액': 'export_amount', '수입액': 'import_amount', '무역수지': 'trade_balance'}
    cols = st.columns(3)
    for i, (metric_label, col_name) in enumerate(metrics_to_show.items()):
        with cols[i]:
            with st.container(border=True):
                current_value = latest_data[col_name].iloc[0] if not latest_data.empty else 0
                prev_month_value = prev_month_data[col_name].iloc[0] if not prev_month_data.empty else None
                mom_delta_str = "---"
                if prev_month_value is not None and prev_month_value != 0:
                    mom_pct = ((current_value - prev_month_value) / abs(prev_month_value)) * 100
                    mom_delta_str = f"{mom_pct:+.1f}%"
                prev_year_value = prev_year_data[col_name].iloc[0] if not prev_year_data.empty else None
                yoy_delta_str = "---"
                if prev_year_value is not None and prev_year_value != 0:
                    yoy_pct = ((current_value - prev_year_value) / abs(prev_year_value)) * 100
                    yoy_delta_str = f"{yoy_pct:+.1f}%"
                st.metric(label=f"{latest_date.strftime('%Y년 %m월')} {metric_label}", value=f"${current_value/1e9:.2f}B")
                st.markdown(f"""
                <div style="font-size: 0.8rem; text-align: right; color: #555;">
                    전월 대비: <b>{mom_delta_str}</b><br>
                    전년 대비: <b>{yoy_delta_str}</b>
                </div>
                """, unsafe_allow_html=True)

# --- 차트 생성 ---
if not display_df.empty:
    zoom = alt.selection_interval(bind='scales', encodings=['x'])
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
        x=alt.X('Date:T', title=None, axis=None),
        y=alt.Y('kospi_price:Q', title='KOSPI 200', scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=5, grid=False)),
    )
    kospi_points = kospi_line.mark_circle(size=35).encode(opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    kospi_vertical_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)
    kospi_horizontal_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(y='kospi_price:Q').transform_filter(nearest_selection)

    kospi_chart = alt.layer(
        kospi_line, kospi_points, kospi_vertical_rule, kospi_horizontal_rule, tooltip_layer
    ).transform_filter(
        zoom
    ).properties(
        height=120,
        title=alt.TitleParams(text="KOSPI 200 지수", anchor="start", fontSize=16)
    )

    trade_melted_df = display_df.melt(id_vars=['Date'], value_vars=cols_to_use, var_name='지표', value_name='값')
    col_map = {export_col: '수출', import_col: '수입', balance_col: '무역수지'}
    trade_melted_df['지표'] = trade_melted_df['지표'].map(col_map)

    if st.session_state.show_yoy_growth:
        y_title_trade, y_title_balance = "수출·수입 YoY 성장률 (%)", "무역수지 YoY 성장률 (%)"
    else:
        y_title_trade, y_title_balance = "수출·수입 금액", "무역수지 금액"
    if st.session_state.is_12m_trailing:
        y_title_trade, y_title_balance = f"12개월 누적 {y_title_trade}", f"12개월 누적 {y_title_balance}"

    if st.session_state.show_yoy_growth:
        y_axis_config = alt.Axis(tickCount=5, grid=False, format='.0f')
    else:
        label_expr = "format(datum.value / 1000000000, '.0f') + 'B'"
        y_axis_config = alt.Axis(tickCount=5, grid=False, labelExpr=label_expr)

    color_scheme = alt.Color('지표:N', scale=alt.Scale(domain=['수출', '수입', '무역수지'], range=['#0d6efd', '#dc3545', '#198754']), legend=alt.Legend(title="구분", orient="top-left"))

    trade_base_chart = alt.Chart(trade_melted_df)

    trade_line = trade_base_chart.mark_line(strokeWidth=2.5, clip=False).encode(
        x=alt.X('Date:T', title=None, axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
        y=alt.Y('값:Q', title=y_title_trade, axis=y_axis_config),
        color=color_scheme
    ).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['수출', '수입']))

    trade_area = trade_base_chart.mark_area(opacity=0.5, clip=False, line={'color': '#198754'}).encode(
        x=alt.X('Date:T'),
        y=alt.Y('값:Q', title=y_title_balance, axis=y_axis_config),
        color=color_scheme
    ).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['무역수지']))

    trade_points = trade_base_chart.mark_circle(size=35).encode(color=color_scheme, opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0)))
    trade_rule = alt.Chart(display_df).mark_rule(color='gray', strokeDash=[3,3]).encode(x='Date:T').transform_filter(nearest_selection)

    trade_chart = alt.layer(
        trade_line, trade_area, trade_rule, trade_points, tooltip_layer
    ).properties(
        height=350,
        title=alt.TitleParams(text=f"{st.session_state.selected_country} 무역 데이터", anchor="start", fontSize=16)
    ).resolve_scale(
        y='independent'
    )

    # [수정] 잘못된 'align' 파라미터를 삭제했습니다.
    final_combined_chart = alt.vconcat(
        kospi_chart, trade_chart, spacing=50, bounds='flush'
    ).add_params(
        zoom
    ).resolve_legend(
        color="independent"
    ).resolve_scale(
        x='shared',
        y='independent'
    ).configure_view(
        strokeWidth=0
    )

    st.altair_chart(final_combined_chart, use_container_width=True)

# --- 컨트롤 패널 UI ---
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

st.info("""
**💡 차트 사용법**
- **확대/축소 (Zoom)**: 차트 위에 마우스 커서를 놓고 **마우스 휠**을 위/아래로 움직여 보세요.
- **이동 (Pan)**: 차트를 **클릭 후 드래그**하여 원하는 구간으로 이동할 수 있습니다.
- **초기화**: 차트 아무 곳이나 **더블 클릭**하면 전체 기간으로 돌아갑니다.
""")

# --- 데이터 출처 정보 ---
st.markdown("---")
with st.container(border=True):
    st.subheader("데이터 출처 정보")
    st.markdown("""
    - **수출입 데이터**: `trade_data.csv` (원본: [관세청 수출입 실적](https://www.data.go.kr/data/15101211/openapi.do))
    - **KOSPI 200 데이터**: `yfinance` (원본: **Yahoo Finance**)
    """)
