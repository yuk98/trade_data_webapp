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
        font-family: ' Pretendard', sans-serif;
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
        cursor: pointer;
        width: 100%;
        height: 40px; /* 고정 높이 */
    }
    .toggle-option {
        flex: 1;
        text-align: center;
        padding: 5px 0;
        border-radius: 16px;
        font-weight: 500;
        transition: all 0.3s ease-in-out;
        color: #495057;
    }
    .toggle-option.active {
        background-color: #ffffff;
        color: #0d6efd;
        font-weight: 700;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* 기간 선택 버튼 */
    div.stButton > button {
        border-radius: 0.5rem;
    }
    /* 선택된 기간 버튼 강조 (JavaScript 필요하여 CSS만으로는 한계가 있음, st.rerun으로 유사 효과 구현) */

</style>
""", unsafe_allow_html=True)


# --- 데이터 생성 및 로드 함수 (캐싱) ---
@st.cache_data
def generate_country_data(start_year, end_year, country_name, base_export, base_import):
    data_list = []
    current_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 5, 1) # Stop at May for the end_year

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
        # 날짜 증가 로직 수정
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
        st.info(f"'{csv_file_name}' 파일을 찾을 수 없어 더미 무역 데이터를 생성합니다.")
        df_total = generate_country_data(2000, 2025, '총합', 10_000_000_000, 9_000_000_000)
        df_us = generate_country_data(2000, 2025, '미국', 2_500_000_000, 2_600_000_000)
        df_china = generate_country_data(2000, 2025, '중국', 2_000_000_000, 1_800_000_000)
        trade_df = pd.concat([df_total, df_us, df_china], ignore_index=True)
        trade_df.to_csv(csv_file_name, index=False)

    trade_df['year_month'] = pd.to_datetime(trade_df['year_month'])
    trade_df = trade_df.sort_values(by=['country_name', 'year_month']).reset_index(drop=True)

    # 12개월 누적 및 YoY 성장률 계산
    for col in ['export_amount', 'import_amount', 'trade_balance']:
        # 12개월 누적
        trade_df[f'{col}_trailing_12m'] = trade_df.groupby('country_name')[col].rolling(window=12, min_periods=12).sum().reset_index(level=0, drop=True)
        # 월별 데이터 YoY
        trade_df[f'{col}_yoy_growth'] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
        # 12개월 누적 데이터 YoY
        trade_df[f'{col}_trailing_12m_yoy_growth'] = trade_df.groupby('country_name')[f'{col}_trailing_12m'].pct_change(periods=12) * 100

    trade_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return trade_df

# --- 데이터 로드 ---
trade_data_processed = load_and_transform_data()

# --- 세션 상태 초기화 ---
if 'selected_country' not in st.session_state:
    st.session_state.selected_country = '총합'
if 'is_12m_trailing' not in st.session_state:
    st.session_state.is_12m_trailing = False
if 'show_yoy_growth' not in st.session_state:
    st.session_state.show_yoy_growth = False
if 'selected_period' not in st.session_state:
    st.session_state.selected_period = '전체 기간'
if 'start_date' not in st.session_state:
    st.session_state.start_date = trade_data_processed['year_month'].min()
if 'end_date' not in st.session_state:
    st.session_state.end_date = trade_data_processed['year_month'].max()

# --- UI 레이아웃 ---
st.title('📊 월별 무역 데이터 대시보드')
st.markdown("국가별 월간 무역 데이터를 시각화하고 분석합니다. 아래 컨트롤 패널에서 옵션을 변경하여 데이터를 탐색해보세요.")


# --- 컨트롤 패널 ---
with st.container():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    
    # 1행: 국가 선택 및 기간 필터
    c1, c2 = st.columns([1.5, 3.5])
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
        st.markdown('**기간 선택**')
        period_options = {'1년': 1, '3년': 3, '5년': 5, '10년': 10, '전체 기간': 99}
        period_cols = st.columns(len(period_options))

        for i, (label, offset_years) in enumerate(period_options.items()):
            if period_cols[i].button(label, key=f'period_{label}', use_container_width=True):
                st.session_state.selected_period = label
                end_date = trade_data_processed['year_month'].max()
                if label == '전체 기간':
                    start_date = trade_data_processed['year_month'].min()
                else:
                    start_date = end_date - pd.DateOffset(years=offset_years)
                st.session_state.start_date = start_date
                st.session_state.end_date = end_date
                st.rerun()

    # 2행: 데이터 변환 토글
    st.markdown('<hr style="margin: 10px 0;">', unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    with c3:
        st.markdown('**데이터 형태**')
        is_12m_trailing = st.session_state.is_12m_trailing
        # HTML을 사용한 커스텀 토글
        toggle_html_12m = f"""
        <div class="toggle-container" onclick="this.querySelector('input').click()">
            <input type="checkbox" style="display:none" id="toggle12m" {'checked' if is_12m_trailing else ''}>
            <div class="toggle-option {'active' if not is_12m_trailing else ''}">월별 데이터</div>
            <div class="toggle-option {'active' if is_12m_trailing else ''}">12개월 누적</div>
        </div>
        """
        if st.checkbox('Toggle12m', value=is_12m_trailing, key='toggle_12m_cb', label_visibility="collapsed"):
            if not st.session_state.is_12m_trailing:
                st.session_state.is_12m_trailing = True
                st.rerun()
        else:
            if st.session_state.is_12m_trailing:
                st.session_state.is_12m_trailing = False
                st.rerun()
        st.markdown(toggle_html_12m, unsafe_allow_html=True)


    with c4:
        st.markdown('**표시 단위**')
        show_yoy_growth = st.session_state.show_yoy_growth
        toggle_html_yoy = f"""
        <div class="toggle-container" onclick="this.querySelector('input').click()">
            <input type="checkbox" style="display:none" id="toggleyoy" {'checked' if show_yoy_growth else ''}>
            <div class="toggle-option {'active' if not show_yoy_growth else ''}">금액 (백만$)</div>
            <div class="toggle-option {'active' if show_yoy_growth else ''}">YoY 성장률 (%)</div>
        </div>
        """
        if st.checkbox('ToggleYoY', value=show_yoy_growth, key='toggle_yoy_cb', label_visibility="collapsed"):
            if not st.session_state.show_yoy_growth:
                st.session_state.show_yoy_growth = True
                st.rerun()
        else:
            if st.session_state.show_yoy_growth:
                st.session_state.show_yoy_growth = False
                st.rerun()
        st.markdown(toggle_html_yoy, unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)


# --- 데이터 필터링 ---
filtered_df = trade_data_processed[
    (trade_data_processed['country_name'] == st.session_state.selected_country) &
    (trade_data_processed['year_month'] >= st.session_state.start_date) &
    (trade_data_processed['year_month'] <= st.session_state.end_date)
].copy()

# --- 메트릭 카드 표시 ---
latest_data = filtered_df.sort_values('year_month').iloc[-1]
prev_month_data = filtered_df.sort_values('year_month').iloc[-2] if len(filtered_df) > 1 else latest_data

def format_value(value):
    return f"{value / 1_000_000:,.0f}M"

def get_delta(current, previous):
    delta = current - previous
    delta_str = f"{delta / 1_000_000:,.0f}M"
    color = "green" if delta >= 0 else "red"
    symbol = "▲" if delta >= 0 else "▼"
    return f'<span class="delta" style="color:{color};">{symbol} {delta_str} (전월 대비)</span>'

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <h3>최신 수출액 ({latest_data['year_month'].strftime('%Y-%m')})</h3>
        <p>{format_value(latest_data['export_amount'])}</p>
        {get_delta(latest_data['export_amount'], prev_month_data['export_amount'])}
    </div>
    """, unsafe_allow_html=True)
with m2:
     st.markdown(f"""
    <div class="metric-card">
        <h3>최신 수입액 ({latest_data['year_month'].strftime('%Y-%m')})</h3>
        <p>{format_value(latest_data['import_amount'])}</p>
        {get_delta(latest_data['import_amount'], prev_month_data['import_amount'])}
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div class="metric-card">
        <h3>최신 무역수지 ({latest_data['year_month'].strftime('%Y-%m')})</h3>
        <p>{format_value(latest_data['trade_balance'])}</p>
        {get_delta(latest_data['trade_balance'], prev_month_data['trade_balance'])}
    </div>
    """, unsafe_allow_html=True)

st.write("") # 여백

# --- 차트 생성 ---
# 동적 컬럼 및 타이틀 설정
base_cols = {'export': 'export_amount', 'import': 'import_amount', 'balance': 'trade_balance'}
y_titles = {'export': '수출', 'import': '수입', 'balance': '무역수지'}
chart_cols = {}
final_y_titles = {}

data_type_suffix = '_trailing_12m' if st.session_state.is_12m_trailing else ''
unit_suffix = '_yoy_growth' if st.session_state.show_yoy_growth else ''

for key, val in base_cols.items():
    chart_cols[key] = f"{val}{data_type_suffix}{unit_suffix}"

for key, val in y_titles.items():
    title = val
    if st.session_state.is_12m_trailing:
        title += " (12개월 누적)"
    if st.session_state.show_yoy_growth:
        title += " YoY 성장률 (%)"
    else:
        title += " (금액)"
    final_y_titles[key] = title

# 차트 생성
if not filtered_df.empty:
    base_chart = alt.Chart(filtered_df).encode(
        x=alt.X('year_month:T', title='연-월', axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
    ).properties(
         height=400
    )

    chart_export = base_chart.mark_line(color='#0d6efd', strokeWidth=2.5, point=alt.OverlayMarkDef(color="#0d6efd", size=40, filled=True, fillOpacity=0.1)).encode(
        y=alt.Y(chart_cols['export'], title=final_y_titles['export'], axis=alt.Axis(titleColor='#0d6efd')),
        tooltip=[alt.Tooltip('year_month:T', title='날짜'), alt.Tooltip(chart_cols['export'], title=final_y_titles['export'], format=',.2f')]
    )

    chart_import = base_chart.mark_line(color='#dc3545', strokeWidth=2.5, point=alt.OverlayMarkDef(color="#dc3545", size=40, filled=True, fillOpacity=0.1)).encode(
        y=alt.Y(chart_cols['import'], title=final_y_titles['import'], axis=alt.Axis(titleColor='#dc3545')),
        tooltip=[alt.Tooltip('year_month:T', title='날짜'), alt.Tooltip(chart_cols['import'], title=final_y_titles['import'], format=',.2f')]
    )

    chart_trade_balance = base_chart.mark_bar(color='#198754', opacity=0.6).encode(
        y=alt.Y(chart_cols['balance'], title=final_y_titles['balance'], axis=alt.Axis(titleColor='#198754')),
        tooltip=[alt.Tooltip('year_month:T', title='날짜'), alt.Tooltip(chart_cols['balance'], title=final_y_titles['balance'], format=',.2f')]
    )

    # 차트 결합 및 해상도 설정
    final_chart = alt.layer(
        chart_export,
        chart_import,
        chart_trade_balance
    ).resolve_scale(
        y='independent'
    ).properties(
        title={
            "text": f"{st.session_state.selected_country} 무역 데이터 추이",
            "subtitle": f"기간: {st.session_state.selected_period}",
            "fontSize": 20,
            "subtitleFontSize": 14,
            "anchor": "start"
        }
    ).interactive()

    st.altair_chart(final_chart, use_container_width=True)

else:
    st.warning("선택된 기간에 해당하는 데이터가 없습니다. 기간을 다시 설정해주세요.")


# --- 사용 방법 안내 ---
with st.expander("ℹ️ 대시보드 사용 방법"):
    st.markdown(f"""
    - **현재 선택된 옵션**: `{st.session_state.selected_country}` | `{st.session_state.selected_period}` | `{'12개월 누적' if st.session_state.is_12m_trailing else '월별 데이터'}` | `{'YoY 성장률' if st.session_state.show_yoy_growth else '금액'}`

    1.  **국가/기간/데이터 형태 선택**: 상단의 컨트롤 패널에서 원하는 옵션을 선택하세요.
    2.  **토글 스위치**: '데이터 형태'와 '표시 단위'는 클릭하여 두 가지 상태를 전환할 수 있습니다. 활성화된 옵션은 파란색 배경으로 표시됩니다.
    3.  **핵심 지표**: 차트 위의 카드는 가장 최신 월의 수출/수입/무역수지 금액과 전월 대비 증감을 보여줍니다.
    4.  **차트 상호작용**:
        - **확대/축소**: 차트 위에서 마우스 휠을 사용하거나, 특정 영역을 드래그하여 확대할 수 있습니다.
        - **이동**: 차트를 좌우로 드래그하여 기간을 이동할 수 있습니다.
        - **초기화**: 차트를 더블 클릭하면 원래 크기로 돌아옵니다.
        - **상세 정보**: 선이나 막대 위에 마우스를 올리면 정확한 수치를 확인할 수 있습니다.
    """)
