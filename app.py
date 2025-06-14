import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import numpy as np

# --- 페이지 설정 (가장 먼저 호출) ---
st.set_page_config(layout="wide", page_title="무역 데이터 대시보드", page_icon="📊")

# --- 커스텀 CSS 스타일 ---
st.markdown("""
<style>
    /* 전체 폰트 및 배경 */
    body {
        font-family: 'Pretendard', sans-serif;
    }

    /* 컨트롤 패널 스타일 */
    .control-panel {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 20px;
    }

    /* 메트릭 카드 스타일 */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
        height: 100%; /* 카드의 높이를 동일하게 설정 */
    }
    .metric-card h3 {
        font-size: 1.1rem;
        color: #495057;
        margin-bottom: 5px;
    }
    .metric-card p {
        font-size: 1.5rem;
        font-weight: 600;
        color: #212529;
    }
    .metric-card .delta {
        font-size: 0.9rem;
        font-weight: 500;
    }

    /* 커스텀 토글 스위치 */
    .toggle-container {
        display: flex;
        align-items: center;
        background-color: #e9ecef;
        border-radius: 20px;
        padding: 4px;
        width: 100%;
        height: 40px; /* 고정 높이 */
    }
    .toggle-container a { /* 링크 스타일 초기화 */
        text-decoration: none;
        flex: 1;
    }
    .toggle-option {
        text-align: center;
        padding: 5px 0;
        border-radius: 16px;
        font-weight: 500;
        transition: all 0.3s ease-in-out;
        color: #495057;
        cursor: pointer;
    }
    .toggle-option.active {
        background-color: #ffffff;
        color: #0d6efd;
        font-weight: 700;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 생성 및 로드 함수 (캐싱) ---
@st.cache_data
def generate_country_data(start_year, end_year, country_name, base_export, base_import):
    data_list = []
    current_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 5, 1)

    while current_date <= end_date:
        growth_factor_export = 1 + (current_date.year - start_year) * 0.03 + (current_date.month / 12 * 0.01)
        growth_factor_import = 1 + (current_date.year - start_year) * 0.025 + (current_date.month / 12 * 0.005)
        seasonal_factor = 1 + (np.sin(current_date.month * 2 * np.pi / 12) * 0.05)

        export_val = base_export * growth_factor_export * seasonal_factor
        import_val = base_import * growth_factor_import * seasonal_factor
        trade_balance_val = export_val - import_val

        data_list.append({
            'export_amount': int(export_val),
            'import_amount': int(import_val),
            'trade_balance': int(trade_balance_val),
            'country_name': country_name,
            'year_month': current_date.strftime('%Y-%m')
        })
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    return pd.DataFrame(data_list)

@st.cache_data
def load_and_transform_data():
    csv_file_name = 'trade_data.csv'
    try:
        trade_df = pd.read_csv(csv_file_name)
    except FileNotFoundError:
        df_total = generate_country_data(2000, 2025, '총합', 10_000_000_000, 9_000_000_000)
        df_us = generate_country_data(2000, 2025, '미국', 2_500_000_000, 2_600_000_000)
        df_china = generate_country_data(2000, 2025, '중국', 2_000_000_000, 1_800_000_000)
        trade_df = pd.concat([df_total, df_us, df_china], ignore_index=True)
        trade_df.to_csv(csv_file_name, index=False)

    trade_df['year_month'] = pd.to_datetime(trade_df['year_month'])
    trade_df = trade_df.sort_values(by=['country_name', 'year_month']).reset_index(drop=True)

    for col in ['export_amount', 'import_amount', 'trade_balance']:
        trade_df[f'{col}_trailing_12m'] = trade_df.groupby('country_name')[col].rolling(window=12, min_periods=12).sum().reset_index(level=0, drop=True)
        trade_df[f'{col}_yoy_growth'] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
        trade_df[f'{col}_trailing_12m_yoy_growth'] = trade_df.groupby('country_name')[f'{col}_trailing_12m'].pct_change(periods=12) * 100

    trade_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return trade_df

# --- 데이터 로드 ---
trade_data_processed = load_and_transform_data()


# --- 세션 상태 및 URL 파라미터 처리 ---
if 'init_done' not in st.session_state:
    st.session_state.selected_country = '총합'
    st.session_state.is_12m_trailing = False
    st.session_state.show_yoy_growth = False
    st.session_state.selected_period = '전체 기간'
    st.session_state.start_date = trade_data_processed['year_month'].min()
    st.session_state.end_date = trade_data_processed['year_month'].max()
    st.session_state.init_done = True

params = st.query_params
if "toggle_12m" in params:
    st.session_state.is_12m_trailing = params.get("toggle_12m") == "True"
    st.query_params.clear()
    st.rerun()

if "toggle_yoy" in params:
    st.session_state.show_yoy_growth = params.get("toggle_yoy") == "True"
    st.query_params.clear()
    st.rerun()


# --- UI 레이아웃 ---
st.title('📊 월별 무역 데이터 대시보드')
st.markdown("국가별 월간 무역 데이터를 시각화하고 분석합니다. 아래 컨트롤 패널에서 옵션을 변경하여 데이터를 탐색해보세요.")

with st.container(border=True):
    c1, c2, c3 = st.columns([1.5, 2, 2])
    with c1:
        new_country = st.selectbox(
            '**국가 선택**',
            options=['총합', '미국', '중국'],
            index=['총합', '미국', '중국'].index(st.session_state.selected_country),
            key='country_select'
        )
        if new_country != st.session_state.selected_country:
            st.session_state.selected_country = new_country
            st.rerun()

    with c2:
        st.markdown('**데이터 형태**')
        is_12m = st.session_state.is_12m_trailing
        toggle_12m_html = f"""
        <div class="toggle-container">
            <a href="?toggle_12m=False" target="_self"><div class="toggle-option {'active' if not is_12m else ''}">월별 데이터</div></a>
            <a href="?toggle_12m=True" target="_self"><div class="toggle-option {'active' if is_12m else ''}">12개월 누적</div></a>
        </div>"""
        st.markdown(toggle_12m_html, unsafe_allow_html=True)

    with c3:
        st.markdown('**표시 단위**')
        is_yoy = st.session_state.show_yoy_growth
        toggle_yoy_html = f"""
        <div class="toggle-container">
            <a href="?toggle_yoy=False" target="_self"><div class="toggle-option {'active' if not is_yoy else ''}">금액 (백만$)</div></a>
            <a href="?toggle_yoy=True" target="_self"><div class="toggle-option {'active' if is_yoy else ''}">YoY 성장률 (%)</div></a>
        </div>"""
        st.markdown(toggle_yoy_html, unsafe_allow_html=True)

filtered_df = trade_data_processed[
    (trade_data_processed['country_name'] == st.session_state.selected_country) &
    (trade_data_processed['year_month'] >= st.session_state.start_date) &
    (trade_data_processed['year_month'] <= st.session_state.end_date)
].copy()

if not filtered_df.empty:
    latest_data = filtered_df.sort_values('year_month').iloc[-1]
    prev_month_data = filtered_df.sort_values('year_month').iloc[-2] if len(filtered_df) > 1 else latest_data

    def format_value(value): return f"{value / 1_000_000:,.0f}M"
    def get_delta(current, previous):
        delta = current - previous
        delta_str = f"{delta / 1_000_000:,.0f}M"
        color = "green" if delta >= 0 else "red"
        symbol = "▲" if delta >= 0 else "▼"
        return f'<span class="delta" style="color:{color};">{symbol} {delta_str} (전월 대비)</span>'

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""<div class="metric-card">
            <h3>최신 수출액 ({latest_data['year_month'].strftime('%Y-%m')})</h3>
            <p>{format_value(latest_data['export_amount'])}</p>
            {get_delta(latest_data['export_amount'], prev_month_data['export_amount'])}
        </div>""", unsafe_allow_html=True)
    with m2:
         st.markdown(f"""<div class="metric-card">
            <h3>최신 수입액 ({latest_data['year_month'].strftime('%Y-%m')})</h3>
            <p>{format_value(latest_data['import_amount'])}</p>
            {get_delta(latest_data['import_amount'], prev_month_data['import_amount'])}
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="metric-card">
            <h3>최신 무역수지 ({latest_data['year_month'].strftime('%Y-%m')})</h3>
            <p>{format_value(latest_data['trade_balance'])}</p>
            {get_delta(latest_data['trade_balance'], prev_month_data['trade_balance'])}
        </div>""", unsafe_allow_html=True)

st.write("")

if not filtered_df.empty:
    # --- 차트 설정 및 데이터 준비 ---
    data_type_suffix = '_trailing_12m' if st.session_state.is_12m_trailing else ''
    unit_suffix = '_yoy_growth' if st.session_state.show_yoy_growth else ''

    export_col, import_col, balance_col = [f'{c}{data_type_suffix}{unit_suffix}' for c in ['export_amount', 'import_amount', 'trade_balance']]

    if st.session_state.show_yoy_growth:
        y_title_trade, y_title_balance = "수출·수입 YoY 성장률 (%)", "무역수지 YoY 성장률 (%)"
        tooltip_format = ".2f"
    else:
        y_title_trade, y_title_balance = "수출·수입 금액", "무역수지 금액"
        tooltip_format = ",.0f"
        
    if st.session_state.is_12m_trailing:
        y_title_trade, y_title_balance = f"12개월 누적 {y_title_trade}", f"12개월 누적 {y_title_balance}"

    all_melted_df = filtered_df.melt(id_vars=['year_month'], value_vars=[export_col, import_col, balance_col], var_name='지표', value_name='값')
    col_map = {export_col: '수출', import_col: '수입', balance_col: '무역수지'}
    all_melted_df['지표'] = all_melted_df['지표'].map(col_map)

    # --- 차트 레이어 생성 ---
    base_chart = alt.Chart(all_melted_df)
    
    # 상호작용을 위한 Selection 생성
    nearest_selection = alt.selection_point(nearest=True, on='mouseover', fields=['year_month'], empty=False)

    # 공유 색상 설정
    color_scheme = alt.Color('지표:N', scale=alt.Scale(domain=['수출', '수입', '무역수지'], range=['#0d6efd', '#dc3545', '#198754']), legend=alt.Legend(title="구분", orient="top-left"))

    # Layer 1: 수출, 수입 라인
    line_layer = base_chart.mark_line(strokeWidth=2.5, clip=True).encode(
        x=alt.X('year_month:T', title=None, axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
        y=alt.Y('값:Q', title=y_title_trade, axis=alt.Axis(tickCount=5)),
        color=color_scheme,
    ).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['수출', '수입']))

    # Layer 2: 무역수지 바
    bar_layer = base_chart.mark_bar(opacity=0.7, clip=True).encode(
        x=alt.X('year_month:T'),
        y=alt.Y('값:Q', title=y_title_balance, axis=alt.Axis(tickCount=5)),
        color=color_scheme,
    ).transform_filter(alt.FieldOneOfPredicate(field='지표', oneOf=['무역수지']))

    # Layer 3: 마우스 오버 시 나타나는 강조점
    points_layer = base_chart.mark_circle(size=35).encode(
        color=color_scheme,
        opacity=alt.condition(nearest_selection, alt.value(1), alt.value(0))
    )

    # Layer 4: 수직 보조선
    vert_rule_layer = alt.Chart(filtered_df).mark_rule(color='gray', strokeDash=[3,3]).encode(
        x='year_month:T'
    ).transform_filter(nearest_selection)

    # Layer 5: 통합 툴팁을 제공하는 투명한 이벤트 감지 레이어
    tooltip_layer = alt.Chart(filtered_df).mark_rule(color='transparent').encode(
        x='year_month:T',
        tooltip=[
            alt.Tooltip('year_month:T', title='날짜'),
            alt.Tooltip(export_col, title=col_map[export_col], format=tooltip_format),
            alt.Tooltip(import_col, title=col_map[import_col], format=tooltip_format),
            alt.Tooltip(balance_col, title=col_map[balance_col], format=tooltip_format)
        ]
    ).add_params(nearest_selection)

    # --- 모든 레이어 결합 ---
    final_chart = alt.layer(
        line_layer, bar_layer, vert_rule_layer, points_layer, tooltip_layer
    ).resolve_scale(
        y='independent'
    ).properties(
        title={"text": f"{st.session_state.selected_country} 무역 데이터 추이", "fontSize": 20, "anchor": "start"},
        height=450
    )
    
    st.altair_chart(final_chart, use_container_width=True)

else:
    st.warning("선택된 기간에 해당하는 데이터가 없습니다. 기간을 다시 설정해주세요.")

st.markdown("---")
st.markdown('**기간 빠르게 탐색하기**')
period_options = {'1년': 1, '3년': 3, '5년': 5, '10년': 10, '전체 기간': 99}
period_cols = st.columns(len(period_options))

for i, (label, offset_years) in enumerate(period_options.items()):
    btn_type = "primary" if st.session_state.selected_period == label else "secondary"
    if period_cols[i].button(label, key=f'period_{label}', use_container_width=True, type=btn_type):
        st.session_state.selected_period = label
        end_date = trade_data_processed['year_month'].max()
        if label == '전체 기간':
            start_date = trade_data_processed['year_month'].min()
        else:
            start_date = end_date - pd.DateOffset(years=offset_years)
        st.session_state.start_date = start_date
        st.session_state.end_date = end_date
        st.rerun()

st.markdown("---")
with st.container(border=True):
    st.subheader("데이터 출처 정보")
    st.markdown("""
    본 대시보드는 공공데이터포털에서 제공하는 **관세청의 품목별 수출입 실적** OpenAPI 데이터의 구조를 참조하여 생성된 샘플 데이터를 시각화하고 있습니다.
    실시간 데이터가 아닌, 데모용으로 생성된 더미(dummy) 데이터임을 참고해주시기 바랍니다.

    - **원본 데이터**: [관세청 품목별 수출입 실적 (OpenAPI)](https://www.data.go.kr/data/15101612/openapi.do)
    - **제공 기관**: 관세청
    - **데이터 포털**: [공공데이터포털 (data.go.kr)](https://www.data.go.kr)
    """)
