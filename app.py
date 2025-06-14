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
        trade_df[f'{col}_trailing_12m'] = trade_df.groupby('country_name')[col].rolling(window=12, min_periods=12).sum().reset_index(level=0, drop=True)

    # Calculate YoY growth rate for raw data
    for col in ['export_amount', 'import_amount', 'trade_balance']:
        trade_df[f'{col}_yoy_growth'] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
        trade_df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Calculate YoY growth rate for 12-month trailing data
    for col in ['export_amount_trailing_12m', 'import_amount_trailing_12m', 'trade_balance_trailing_12m']:
        base_col = col.replace('_trailing_12m', '') # e.g., 'export_amount'
        trade_df[f'{base_col}_trailing_12m_yoy_growth'] = trade_df.groupby('country_name')[col].pct_change(periods=12) * 100
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
    st.session_state.selected_period = '전체 기간' # Default to '전체 기간'
if 'start_date' not in st.session_state:
    st.session_state.start_date = trade_data_processed['year_month'].min()
if 'end_date' not in st.session_state:
    st.session_state.end_date = trade_data_processed['year_month'].max()

# Custom CSS for button styling based on selection
st.markdown("""
<style>
div.stButton > button {
    background-color: #f0f2f6; /* Default light gray background */
    color: black;
    border: 1px solid #d3d3d3;
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;
    margin: 0 0.2rem;
}
div.stButton > button:hover {
    border-color: #007bff; /* Hover border */
    color: #007bff; /* Hover text color */
}
/* This custom class is added via JavaScript/HTML, not directly by st.button */
/* For a true "grayed out" effect, more advanced techniques (components or JS) are needed. */
/* The current approach relies on Streamlit's default re-rendering. */
</style>
""", unsafe_allow_html=True)

# Function to update period and selected_period in session state
def update_period(period_label, offset_years):
    st.session_state.selected_period = period_label
    end_of_data = trade_data_processed['year_month'].max()
    if period_label == '전체 기간':
        st.session_state.start_date = trade_data_processed['year_month'].min()
    else:
        st.session_state.start_date = end_of_data - pd.DateOffset(years=offset_years)
    st.session_state.end_date = end_of_data
    st.rerun() # Force rerun to update the chart and potentially button styling


# --- Period Selection Buttons ABOVE Chart ---
period_options = {
    '1년': 1,
    '3년': 3,
    '5년': 5,
    '10년': 10,
    '20년': 20,
    '전체 기간': None # Special case for full range
}

# Create columns for period buttons
period_buttons_cols = st.columns(len(period_options))

for i, (label, offset_years) in enumerate(period_options.items()):
    with period_buttons_cols[i]:
        # Using a direct Streamlit button. The "active" styling (gray background)
        # is difficult with native Streamlit buttons without custom components.
        # We'll rely on the functional update and the general style.
        if st.button(label, key=f'{label}_button', use_container_width=True):
            update_period(label, offset_years)


# --- Altair Chart ---
# Filter data based on selected country and date range FIRST
filtered_df_for_chart = trade_data_processed[
    (trade_data_processed['country_name'] == selected_country) &
    (trade_data_processed['year_month'] >= st.session_state.start_date) &
    (trade_data_processed['year_month'] <= st.session_state.end_date)
].copy()

# Determine which column names to use based on transformation selections
# This creates dynamic column names like 'export_amount_yoy_growth' or 'trade_balance_trailing_12m'
chart_export_col = 'export_amount'
chart_import_col = 'import_amount'
chart_trade_balance_col = 'trade_balance'

if st.session_state.is_12m_trailing:
    chart_export_col = f'{chart_export_col}_trailing_12m'
    chart_import_col = f'{chart_import_col}_trailing_12m'
    chart_trade_balance_col = f'{chart_trade_balance_col}_trailing_12m'

if st.session_state.show_yoy_growth:
    chart_export_col = f'{chart_export_col}_yoy_growth'
    chart_import_col = f'{chart_import_col}_yoy_growth'
    chart_trade_balance_col = f'{chart_trade_balance_col}_yoy_growth'

# Determine Y-axis titles for each metric based on current transformation state
export_y_title = '수출 금액'
import_y_title = '수입 금액'
trade_balance_y_title = '무역 수지'

if st.session_state.show_yoy_growth:
    export_y_title = '수출 YoY 성장률 (%)'
    import_y_title = '수입 YoY 성장률 (%)'
    trade_balance_y_title = '무역 수지 YoY 성장률 (%)'
elif st.session_state.is_12m_trailing:
    export_y_title = '수출 12개월 누적 금액'
    import_y_title = '수입 12개월 누적 금액'
    trade_balance_y_title = '무역 수지 12개월 누적 금액'


# Create individual charts for layering
# Y-axis will auto-fit by default because no 'domain' is explicitly set in alt.Y()
# Each chart now uses the dynamically chosen column name
chart_export = alt.Chart(filtered_df_for_chart).mark_line(color='blue').encode(
    x=alt.X('year_month:T', title='연-월'),
    y=alt.Y(chart_export_col, title=export_y_title),
    tooltip=[
        alt.Tooltip('year_month:T', title='연-월', format='%Y-%m'),
        alt.Tooltip(chart_export_col, title=export_y_title, format=',.2f')
    ]
)

chart_import = alt.Chart(filtered_df_for_chart).mark_line(color='red').encode(
    x=alt.X('year_month:T', title=''), # No title to avoid redundancy
    y=alt.Y(chart_import_col, title=import_y_title),
    tooltip=[
        alt.Tooltip('year_month:T', title='연-월', format='%Y-%m'),
        alt.Tooltip(chart_import_col, title=import_y_title, format=',.2f')
    ]
)

chart_trade_balance = alt.Chart(filtered_df_for_chart).mark_line(color='green').encode(
    x=alt.X('year_month:T', title=''), # No title to avoid redundancy
    y=alt.Y(chart_trade_balance_col, title=trade_balance_y_title),
    tooltip=[
        alt.Tooltip('year_month:T', title='연-월', format='%Y-%m'),
        alt.Tooltip(chart_trade_balance_col, title=trade_balance_y_title, format=',.2f')
    ]
)

# Combine charts with independent y-scales and interactive X-axis
final_chart = alt.layer(
    chart_export,
    chart_import,
    chart_trade_balance
).resolve_scale(
    y='independent' # Key for independent Y-axes
).properties(
    title=f'{selected_country} - 무역 데이터 추이'
).interactive(
    # This enables the brush selection (transparent box) on the X-axis
    # and also general zoom/pan functionality.
    alt.selection_interval(encodings=['x'])
)

st.altair_chart(final_chart, use_container_width=True)


# --- Data Options AFTER Chart and BEFORE Usage Instructions ---
st.subheader('데이터 보기 옵션:')
col1_after_chart, col2_after_chart, col3_after_chart = st.columns([0.3, 0.3, 0.4])

with col1_after_chart:
    if st.button('12개월 누적' if not st.session_state.is_12m_trailing else '월별 데이터', key='12m_toggle_bottom'):
        st.session_state.is_12m_trailing = not st.session_state.is_12m_trailing
with col2_after_chart:
    st.session_state.show_yoy_growth = st.checkbox('YoY 성장률', value=st.session_state.show_yoy_growth, key='yoy_toggle_bottom')
with col3_after_chart:
    # Country selection dropdown - moved here as per new request
    country_selection_list_bottom = ['미국', '중국', '총합']
    current_country_index = country_selection_list_bottom.index(selected_country) if selected_country in country_selection_list_bottom else 0
    selected_country_bottom = st.selectbox(
        '국가 선택:',
        options=country_selection_list_bottom,
        index=current_country_index, # Default to the current selected country
        key='country_select_bottom'
    )
    # If the user selects a country from this dropdown, update the main selected_country.
    # This will trigger a rerun.
    if selected_country_bottom != selected_country:
        st.session_state.selected_country = selected_country_bottom # Store in session state if you want to remember across reruns
        st.rerun() # Force rerun to update chart with new country


st.markdown("""
---
### **사용 방법:**
현재 선택된 기간: **{}**
1.  **국가 선택**: 차트 아래의 드롭다운에서 '미국', '중국', '총합' 중 하나를 선택하세요.
2.  **"12개월 누적" 버튼**: 차트 아래의 버튼을 클릭하여 월별 데이터와 12개월 누적 데이터 간에 전환합니다. 버튼 텍스트도 그에 따라 변경됩니다.
3.  **"YoY 성장률" 체크박스**: 차트 아래의 체크박스를 체크하면 현재 활성화된 데이터(월별 또는 12개월 누적)의 YoY 성장률을 보여줍니다. 체크를 해제하면 다시 절대 금액으로 돌아갑니다.
4.  **기간 선택 버튼**: 차트 위에 있는 버튼을 클릭하여 X축 기간을 '1년', '3년', '5년', '10년', '20년', '전체 기간'으로 빠르게 조정할 수 있습니다.
5.  **확대/축소 및 이동**: 마우스 스크롤 또는 터치패드를 사용하여 그래프를 확대/축소하고, **X축 영역에서 마우스를 드래그하여 원하는 구간을 선택하거나 이동할 수 있습니다.**
""".format(st.session_state.selected_period))
