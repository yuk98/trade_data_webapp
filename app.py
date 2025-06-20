import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from typing import Tuple

# 가정: data_handler.py는 별도의 파일로 존재하며 필요한 함수들을 포함합니다.
# 이 파일을 실행하려면 data_handler.py가 필요합니다.
# 예시: import data_handler

# --- 임시 data_handler 모듈 (실행 테스트용) ---
# [수정] 데이터 로딩과 처리를 분리하여, 여기서는 원본 데이터만 생성합니다.
class DataHandlerMock:
    def load_trade_data(self):
        # 샘플 데이터 생성
        dates = pd.to_datetime(pd.date_range(start='2014-01-01', end='2024-05-01', freq='MS'))
        data = []
        for country in ['총합', '미국', '중국']:
            for date in dates:
                export = 1e9 * (50 + 10 * (1 + 0.5 * abs((date.month - 6.5)))) + (hash(country) % 10) * 1e8
                imports = 1e9 * (45 + 8 * (1 + 0.4 * abs((date.month - 6.5)))) + (hash(country) % 8) * 1e8
                
                export *= (1 + (pd.Timestamp.now().microsecond % 1000) / 10000 - 0.05)
                imports *= (1 + (pd.Timestamp.now().microsecond % 1000) / 10000 - 0.05)
                
                data.append({
                    'Date': date, 
                    'country_name': country,
                    'export_amount': export,
                    'import_amount': imports,
                })

        df = pd.DataFrame(data)
        df['trade_balance'] = df['export_amount'] - df['import_amount']
        return df

    def get_and_update_kospi_data(self):
        # 샘플 KOSPI 데이터 생성
        dates = pd.to_datetime(pd.date_range(start='2014-01-01', end='2024-05-01', freq='MS'))
        kospi_price = [200 + i*0.5 + 20 * (1 + 0.6 * abs((d.month - 6.5))) for i, d in enumerate(dates)]
        kospi_df = pd.DataFrame({'Date': dates, 'Close': kospi_price})
        return kospi_df, "KOSPI 200 데이터를 성공적으로 불러왔습니다."

    def process_kospi_for_chart(self, kospi_data):
        kospi_data['kospi_price'] = kospi_data['Close']
        return kospi_data[['Date', 'kospi_price']]

data_handler = DataHandlerMock()
# --- 임시 data_handler 모듈 끝 ---


# --- 상수 정의 ---
PRIMARY_COLOR = "#0d6efd"
SECONDARY_COLOR = "#dc3545"
TERTIARY_COLOR = "#198754"
KOSPI_COLOR = "#FF9900"
COUNTRY_OPTIONS = ['총합', '미국', '중국']

class Dashboard:
    """
    무역 & KOSPI 대시보드 애플리케이션 클래스.
    안정성과 확장성을 고려하여 객체 지향 방식으로 재설계되었습니다.
    """

    def __init__(self):
        st.set_page_config(layout="wide", page_title="무역 & KOSPI 대시보드", page_icon="📊")
        if 'init_done' not in st.session_state:
            self._initialize_session_state()

    def _initialize_session_state(self):
        """세션 상태를 초기화합니다."""
        st.session_state.selected_country = '총합'
        st.session_state.is_12m_trailing = True
        st.session_state.show_yoy_growth = False
        st.session_state.selected_period = '10년'
        st.session_state.init_done = True

    @st.cache_data
    def _load_and_prepare_data(_self) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        데이터를 로드하고 기본 전처리를 수행합니다.
        Streamlit 캐시를 사용하여 반복적인 로딩을 방지합니다.
        """
        trade_data = data_handler.load_trade_data()
        kospi_data, kospi_msg = data_handler.get_and_update_kospi_data()
        if trade_data is None or kospi_data is None:
            return None, None, kospi_msg
        kospi_processed = data_handler.process_kospi_for_chart(kospi_data)
        return trade_data, kospi_processed, kospi_msg

    def _render_header_and_metrics(self, df: pd.DataFrame):
        """페이지 제목과 주요 메트릭 카드를 렌더링합니다."""
        st.title('무역 데이터 & KOSPI 200 대시보드')
        
        latest_trade_date = df.dropna(subset=['export_amount'])['Date'].max()
        if pd.isna(latest_trade_date):
            st.warning("선택된 기간에 표시할 무역 데이터가 없습니다.")
            return

        latest_data = df[df['Date'] == latest_trade_date]
        prev_month_data = df[df['Date'] == (latest_trade_date - pd.DateOffset(months=1))]
        prev_year_data = df[df['Date'] == (latest_trade_date - pd.DateOffset(years=1))]
        
        metrics_map = {'수출액': 'export_amount', '수입액': 'import_amount', '무역수지': 'trade_balance'}
        cols = st.columns(len(metrics_map))

        for i, (label, col_name) in enumerate(metrics_map.items()):
            with cols[i]:
                with st.container(border=True):
                    current_val = latest_data[col_name].iloc[0] if not latest_data.empty else 0
                    prev_month_val = prev_month_data[col_name].iloc[0] if not prev_month_data.empty else 0
                    prev_year_val = prev_year_data[col_name].iloc[0] if not prev_year_data.empty else 0
                    
                    mom_delta = ((current_val - prev_month_val) / abs(prev_month_val)) * 100 if prev_month_val != 0 else 0
                    yoy_delta = ((current_val - prev_year_val) / abs(prev_year_val)) * 100 if prev_year_val != 0 else 0

                    st.metric(label=f"{latest_trade_date.strftime('%Y년 %m월')} {label}", value=f"${current_val/1e9:.2f}B")
                    st.markdown(f"""
                    <div style="font-size: 0.8rem; text-align: right; color: #555;">
                        전월 대비: <b style="color:{'red' if mom_delta < 0 else 'green'};">{mom_delta:+.1f}%</b><br>
                        전년 대비: <b style="color:{'red' if yoy_delta < 0 else 'green'};">{yoy_delta:+.1f}%</b>
                    </div>
                    """, unsafe_allow_html=True)

    def _render_charts(self, df: pd.DataFrame):
        """상호작용 기능이 포함된 Altair 차트를 생성하고 렌더링합니다."""
        nearest = alt.selection_point(on='mouseover', encodings=['x'], nearest=True, empty=False)
        
        base_cols = ['export_amount', 'import_amount', 'trade_balance']
        trailing = '_trailing_12m' if st.session_state.is_12m_trailing else ''
        growth = '_yoy_growth' if st.session_state.show_yoy_growth else ''
        cols_to_use = [f"{col}{trailing}{growth}" for col in base_cols]
        export_col, import_col, balance_col = cols_to_use

        vertical_rule = alt.Chart(df).mark_rule(color='gray', strokeDash=[3,3]).encode(
            x='Date:T',
            tooltip=[
                alt.Tooltip('Date:T', title='날짜', format='%Y-%m'),
                alt.Tooltip('kospi_price:Q', title='KOSPI 200', format=',.2f'),
                alt.Tooltip(export_col, title="수출", format='$,.2f'),
                alt.Tooltip(import_col, title="수입", format='$,.2f'),
                alt.Tooltip(balance_col, title="무역수지", format='$,.2f'),
            ]
        ).transform_filter(nearest)
        
        base_chart = alt.Chart(df).add_params(nearest)
        
        kospi_horizontal_rule = alt.Chart(df).mark_rule(color=KOSPI_COLOR, strokeDash=[3,3]).encode(
            y=alt.Y('kospi_price:Q')
        ).transform_filter(nearest)
        
        kospi_chart_base = base_chart.mark_line(color=KOSPI_COLOR).encode(
            x=alt.X('Date:T', title=None, axis=None),
            y=alt.Y('kospi_price:Q', title='KOSPI 200', scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=4, grid=False))
        )
        kospi_points = kospi_chart_base.mark_circle(size=60).encode(
            opacity=alt.condition(nearest, alt.value(1), alt.value(0))
        )
        kospi_chart = alt.layer(kospi_chart_base, kospi_points, kospi_horizontal_rule, vertical_rule).properties(
            height=110, title=alt.TitleParams("KOSPI 200 지수", anchor='start', fontSize=16)
        )
        
        trade_df = df.dropna(subset=cols_to_use).melt(id_vars=['Date'], value_vars=cols_to_use, var_name='지표', value_name='값')
        col_map = {export_col: '수출', import_col: '수입', balance_col: '무역수지'}
        trade_df['지표'] = trade_df['지표'].map(col_map)
        
        y_axis_format = "format(datum.value / 1e9, '.0f') + 'B'" if not growth else "format(datum.value, '.1f') + '%'"
        
        trade_base_chart = alt.Chart(trade_df).add_params(nearest).encode(
            x=alt.X('Date:T', title=None, axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
            color=alt.Color('지표:N', scale=alt.Scale(domain=['수출', '수입', '무역수지'], range=[PRIMARY_COLOR, SECONDARY_COLOR, TERTIARY_COLOR]), legend=alt.Legend(title="구분", orient='top-left'))
        )
        
        line_chart = trade_base_chart.transform_filter(alt.datum.지표 != '무역수지').mark_line(strokeWidth=2.5).encode(
            y=alt.Y('값:Q', title="금액 (수출입)", scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=y_axis_format))
        )
        area_chart = trade_base_chart.transform_filter(alt.datum.지표 == '무역수지').mark_area(opacity=0.4, line={'color': TERTIARY_COLOR}).encode(
            y=alt.Y('값:Q', title="금액 (무역수지)", scale=alt.Scale(zero=True), axis=alt.Axis(labelExpr=y_axis_format))
        )
        trade_points = trade_base_chart.mark_circle(size=60).encode(
            y='값:Q',
            opacity=alt.condition(nearest, alt.value(1), alt.value(0))
        )
        
        trade_chart = alt.layer(line_chart, area_chart, trade_points, vertical_rule).resolve_scale(y='independent').properties(
            height=280, title=alt.TitleParams(f"{st.session_state.selected_country} 무역 데이터", anchor='start', fontSize=16)
        )

        final_chart = alt.vconcat(
            kospi_chart,
            trade_chart,
            spacing=30
        ).properties(
            bounds='flush'
        ).resolve_legend(
            color="independent"
        ).configure_view(
            stroke=None
        )

        st.altair_chart(final_chart, use_container_width=True)


    def _render_controls(self, min_date: datetime, max_date: datetime):
        """컨트롤 패널을 렌더링하고 사용자 입력을 처리합니다."""
        with st.expander("데이터 보기 및 기간 설정", expanded=True):
            cols = st.columns([1, 1, 2])
            with cols[0]:
                st.selectbox('**국가 선택**', COUNTRY_OPTIONS, key='selected_country', on_change=self.update_states)
            with cols[1]:
                st.radio('**형태 (무역)**', ['월별', '12개월 누적'], index=1 if st.session_state.is_12m_trailing else 0, key='data_form', horizontal=True, on_change=self.update_states)
            with cols[2]:
                st.radio('**단위 (무역)**', ['금액', 'YoY'], index=1 if st.session_state.show_yoy_growth else 0, key='unit_form', horizontal=True, on_change=self.update_states)
            
            st.divider()

            period_options = {'1년': 1, '3년': 3, '5년': 5, '10년': 10, '전체': 99}
            period_cols = st.columns(len(period_options))
            
            for i, (label, years) in enumerate(period_options.items()):
                with period_cols[i]:
                    btn_type = "primary" if st.session_state.selected_period == label else "secondary"
                    if st.button(label, key=f"period_btn_{label}", use_container_width=True, type=btn_type, on_click=self.set_period, args=(label, years, min_date, max_date)):
                        pass

            date_cols = st.columns(2)
            date_cols[0].date_input("시작일", key="start_date_input", on_change=lambda: st.session_state.update(selected_period=None))
            date_cols[1].date_input("종료일", key="end_date_input", on_change=lambda: st.session_state.update(selected_period=None))
    
    def set_period(self, label: str, years: int, min_date: datetime, max_date: datetime):
        """기간 버튼 클릭 시 세션 상태를 업데이트하는 콜백 함수."""
        st.session_state.selected_period = label
        st.session_state.end_date_input = max_date.date()
        if label == '전체':
            st.session_state.start_date_input = min_date.date()
        else:
            st.session_state.start_date_input = (max_date - pd.DateOffset(years=years)).date()

    def update_states(self):
        """데이터 보기 옵션 변경 시 세션 상태를 업데이트하는 콜백 함수."""
        st.session_state.is_12m_trailing = (st.session_state.data_form == '12개월 누적')
        st.session_state.show_yoy_growth = (st.session_state.unit_form == 'YoY')

    def run(self):
        """대시보드 애플리케이션을 실행합니다."""
        with st.spinner('데이터를 불러오는 중입니다...'):
            trade_data_base, kospi_data, kospi_msg = self._load_and_prepare_data()

        if trade_data_base is None or kospi_data is None:
            st.error("데이터 로딩에 실패했습니다. 파일을 확인하거나 인터넷 연결을 점검해주세요.")
            if kospi_msg: st.warning(kospi_msg)
            return
        
        # [수정] 데이터 로딩 후, 메인 로직에서 파생 변수를 계산합니다.
        processed_dataframes = []
        for country in trade_data_base['country_name'].unique():
            country_df = trade_data_base[trade_data_base['country_name'] == country].sort_values('Date').copy()
            for col in ['export_amount', 'import_amount', 'trade_balance']:
                country_df[f'{col}_trailing_12m'] = country_df[col].rolling(window=12).sum()
                country_df[f'{col}_yoy_growth'] = country_df[col].pct_change(periods=12) * 100
                country_df[f'{col}_trailing_12m_yoy_growth'] = country_df[f'{col}_trailing_12m'].pct_change(periods=12) * 100
            processed_dataframes.append(country_df)
        trade_data_processed = pd.concat(processed_dataframes)
        
        min_date_for_controls = trade_data_processed['Date'].min()
        max_date_for_controls = kospi_data['Date'].max()
        
        if 'start_date_input' not in st.session_state:
            st.session_state.start_date_input = (max_date_for_controls - pd.DateOffset(years=10)).date()
        if 'end_date_input' not in st.session_state:
            st.session_state.end_date_input = max_date_for_controls.date()

        self._render_controls(min_date_for_controls, max_date_for_controls)

        trade_country_filtered = trade_data_processed[trade_data_processed['country_name'] == st.session_state.selected_country].copy()
        
        full_display_df = pd.merge(trade_country_filtered, kospi_data, on='Date', how='outer').sort_values(by='Date')
        
        display_df_filtered = full_display_df[
            (full_display_df['Date'] >= pd.to_datetime(st.session_state.start_date_input)) & 
            (full_display_df['Date'] <= pd.to_datetime(st.session_state.end_date_input))
        ]
        
        self._render_header_and_metrics(display_df_filtered)
        
        if display_df_filtered.empty:
            st.warning("선택된 기간에 표시할 데이터가 없습니다.")
        else:
            self._render_charts(display_df_filtered)
        
        st.info("""
        **차트 사용법**
        - **기간 변경**: 하단의 '데이터 보기 및 기간 설정'에서 **기간 버튼**을 누르거나, **시작일**과 **종료일**을 직접 선택하세요.
        - **상세 정보**: 차트 위를 마우스 오버(데스크톱)하거나 터치(모바일)하면 상세 데이터를 볼 수 있습니다.
        """)
        
        with st.container(border=True):
            st.subheader("데이터 출처 정보")
            st.markdown(
                "- **수출입 데이터**: `trade_data.csv` (원본: [관세청 수출입 실적](https://www.data.go.kr/data/15101211/openapi.do))\n"
                "- **KOSPI 200 데이터**: `yfinance` (원본: **Yahoo Finance**)"
            )

if __name__ == "__main__":
    app = Dashboard()
    app.run()
