import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import numpy as np

# st.set_page_config() 호출을 스크립트 최상단으로 이동합니다.
st.set_page_config(layout="wide")

# Function to generate dummy data (cached for performance)
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

        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)
    return pd.DataFrame(data_list)

# Load and transform data (cached for performance)
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

    # Calculate 12-month trailing values for 'export_amount', 'import_amount', 'trade_balance'
    for col in ['export_amount', 'import_amount', 'trade_balance']:
        trade_df['{}_trailing_12m'.format(col)] = trade_df.groupby('country_name')[col].rolling(window=12, min_periods=12).sum().reset_index(level=0, drop=True)

    # Calculate YoY growth rate for raw data
    for col in ['export_amount', 'import_amount', 'trade_balance']:
        trade_df['{}_yoy_growth'.format(col)] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
        trade_df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Calculate YoY growth rate for 12-month trailing data
    for col in ['export_amount_trailing_12m', 'import_amount_trailing_12m', 'trade_balance_trailing_12m']:
        base_col = col.replace('_trailing_12m', '') # e.g., 'export_amount'
        trade_df['{}_trailing_12m_yoy_growth'.format(base_col)] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
        trade_df.replace([np.inf, -np.inf], np.nan, inplace=True)

    return trade_df

# Load and transform the data
trade_data_processed = load_and_transform_data()

st.title('월별 무역 데이터 대시보드')

# Initialize session state for transformation modes and selected period
if 'is_12m_trailing' not in st.session_state:
    st.session_state.is_12m_trailing = False
if 'show_yoy_growth' not in st.session_state:
    st.session_state.show_yoy_growth = False
if 'selected_period' not in st.session_state:
    st.session_state.selected_period = None
if 'start_date' not in st.session_state:
    st.session_state.start_date = trade_data_processed['year_month'].min()
if 'end_date' not in st.session_state:
    st.session_state.end_date = trade_data_processed['year_month'].max()

# Control Panel
st.subheader('데이터 보기 옵션:')
col_controls = st.columns([0.3, 0.3, 0.4]) # Adjust column widths for better layout

with col_controls:
    if st.button('12개월 누적' if not st.session_state.is_12m_trailing else '월별 데이터'):
        st.session_state.is_12m_trailing = not st.session_state.is_12m_trailing
    st.session_state.show_yoy_growth = st.checkbox('YoY 성장률', value=st.session_state.show_yoy_growth)
    country_selection_list = ['미국', '중국', '총합']
    selected_country = st.selectbox(
        '국가 선택:',
        options=country_selection_list,
        index=country_selection_list.index('총합') # Default to '총합'
    )

# --- Period Selection Buttons Above Chart ---
st.subheader('') # Add some spacing
period_buttons_cols = st.columns([0.16, 0.16, 0.16, 0.16, 0.36]) # Adjust column widths for buttons

periods = {
    '1년': pd.DateOffset(years=1),
    '3년': pd.DateOffset(years=3),
    '5년': pd.DateOffset(years=5),
    '10년': pd.DateOffset(years=10),
    '20년': pd.DateOffset(years=20)
}

end_of_data = trade_data_processed['year_month'].max()

for col, (label, offset) in zip(period_buttons_cols, periods.items()):
    with col:
        button_style = ""
        if st.session_state.selected_period == label:
            button_style = "color: #808080;" # Simple way to indicate selection

        if st.button(label, key=f'{label}_button', help=f'{label} 데이터 보기', disabled=False, use_container_width=True, on_click=lambda p=label, o=offset: update_period(p, o)):
            pass # The logic is handled by the on_click callback

def update_period(period_label, offset):
    st.session_state.selected_period = period_label
    end_of_data = trade_data_processed['year_month'].max()
    st.session_state.start_date = end_of_data - offset
    st.session_state.end_date = end_of_data
    # Force a re-run to update the chart based on the new date range
    st.rerun()

# --- Altair Chart ---
metric_prefixes = ['export_amount', 'import_amount', 'trade_balance']
selected_metrics = []

for prefix in metric_prefixes:
    if st.session_state.is_12m_trailing:
        base_col = '{}_trailing_12m'.format(prefix)
    else:
        base_col = prefix

    if st.session_state.show_yoy_growth:
        selected_metrics.append('{}_yoy_growth'.format(base_col))
    else:
        selected_metrics.append(base_col)

filtered_df = trade_data_processed[(trade_data_processed['country_name'] == selected_country) &
                                   (trade_data_processed['year_month'] >= st.session_state.start_date) &
                                   (trade_data_processed['year_month'] <= st.session_state.end_date)][['year_month', 'country_name'] + selected_metrics].copy()

final_melted_df = filtered_df.melt(id_vars=['year_month', 'country_name'], value_vars=selected_metrics, var_name='metric', value_name='value').dropna(subset=['value'])

def clean_metric_name(metric_raw):
    if 'export_amount' in metric_raw: return '수출 금액'
    if 'import_amount' in metric_raw: return '수입 금액'
    if 'trade_balance' in metric_raw: return '무역 수지'
    return metric_raw

final_melted_df['display_metric'] = final_melted_df['metric'].apply(clean_metric_name)

y_axis_title = '금액'
if st.session_state.show_yoy_growth:
    y_axis_title = 'YoY 성장률 (%)'
elif st.session_state.is_12m_trailing:
    y_axis_title = '12개월 누적 금액'
else:
    y_axis_title = '월별 금액'

chart = alt.Chart(final_melted_df).mark_line().encode(
    x=alt.X('year_month:T', title='연-월', axis=alt.Axis(format='%Y-%m')),
    y=alt.Y('value:Q', title=y_axis_title),
    color=alt.Color('display_metric:N', title='지표 유형',
                    scale=alt.Scale(domain=['수출 금액', '수입 금액', '무역 수지'],
                                    range=['blue', 'red', 'green'])),
    tooltip=[
        alt.Tooltip('year_month:T', title='연-월', format='%Y-%m'),
        alt.Tooltip('display_metric:N', title='지표 유형'),
        alt.Tooltip('value:Q', title='값', format=',.2f')
    ]
).properties(
    title=f'{selected_country} - {y_axis_title} 추이'
).interactive() # Enables zoom and pan for X-axis

st.altair_chart(chart, use_container_width=True)

st.markdown("""
---
### **사용 방법:**
1.  **국가 선택**: 드롭다운에서 '미국', '중국', '총합' 중 하나를 선택하세요.
2.  **"12개월 누적" 버튼**: 클릭하여 월별 데이터와 12개월 누적 데이터 간에 전환합니다. 버튼 텍스트도 그에 따라 변경됩니다.
3.  **"YoY 성장률" 체크박스**: 체크하면 현재 활성화된 데이터(월별 또는 12개월 누적)의 YoY 성장률을 보여줍니다. 체크를 해제하면 다시 절대 금액으로 돌아갑니다.
4.  **기간 선택 버튼**: 차트 위에 있는 버튼을 클릭하여 X축 기간을 '1년', '3년', '5년', '10년', '20년'으로 빠르게 조정할 수 있습니다. 선택된 버튼은 약간 어둡게 표시됩니다.
5.  **확대/축소 및 이동**: 마우스 스크롤 또는 터치패드를 사용하여 그래프를 확대/축소하고, 드래그하여 이동할 수 있습니다.
""")