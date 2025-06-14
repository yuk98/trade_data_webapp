import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from typing import Tuple, Dict, Any, List

# 가정: data_handler.py는 별도의 파일로 존재하며 필요한 함수들을 포함합니다.
import data_handler

# --- 상수 정의 ---
PRIMARY_COLOR = "#0d6efd"
SECONDARY_COLOR = "#dc3545"
TERTIARY_COLOR = "#198754"
KOSPI_COLOR = "#FF9900"

COUNTRY_OPTIONS = ['총합', '미국', '중국']

class Dashboard:
    """
    무역 & KOSPI 대시보드 애플리케이션 클래스.
    데이터 로딩, 처리, 시각화 로직을 캡슐화합니다.
    """

    def __init__(self):
        st.set_page_config(layout="wide", page_title="무역 & KOSPI 대시보드", page_icon="📈")
        if 'init_done' not in st.session_state:
            self._initialize_session_state()

    def _initialize_session_state(self):
        """세션 상태를 초기화합니다."""
        st.session_state.selected_country = '총합'
        st.session_state.is_12m_trailing = True
        st.session_state.show_yoy_growth = False
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

    def _get_display_df(self, trade_data: pd.DataFrame, kospi_data: pd.DataFrame) -> pd.DataFrame:
        """선택된 옵션에 따라 최종적으로 표시할 데이터프레임을 생성합니다."""
        country = st.session_state.selected_country
        
        trade_filtered = trade_data[trade_data['country_name'] == country].copy()
        trade_filtered['Date'] = pd.to_datetime(trade_filtered['Date']) + pd.offsets.MonthEnd(0)

        display_df = pd.merge(
            trade_filtered, kospi_data, on='Date', how='outer'
        ).sort_values(by='Date').reset_index(drop=True)
        
        return display_df

    def _render_header_and_metrics(self, df: pd.DataFrame):
        """페이지 제목과 주요 메트릭 카드를 렌더링합니다."""
        st.title('📈 무역 데이터 & KOSPI 200 대시보드')

        latest_trade_date = df.dropna(subset=['export_amount'])['Date'].max()
        if pd.isna(latest_trade_date):
            st.warning("선택된 기간에 표시할 무역 데이터가 없습니다.")
            return

        latest_data = df[df['Date'] == latest_trade_date]
        prev_month_data = df[df['Date'] == latest_trade_date - pd.DateOffset(months=1)]
        prev_year_data = df[df['Date'] == latest_trade_date - pd.DateOffset(years=1)]

        metrics_map = {'수출액': 'export_amount', '수입액': 'import_amount', '무역수지': 'trade_balance'}
        cols = st.columns(len(metrics_map))

        for i, (label, col_name) in enumerate(metrics_map.items()):
            with cols[i]:
                with st.container(border=True):
                    current_val = latest_data[col_name].iloc[0] if not latest_data.empty else 0
                    
                    # MoM 계산
                    prev_month_val = prev_month_data[col_name].iloc[0] if not prev_month_data.empty else 0
                    mom_delta = ((current_val - prev_month_val) / abs(prev_month_val)) * 100 if prev_month_val else 0
                    
                    # YoY 계산
                    prev_year_val = prev_year_data[col_name].iloc[0] if not prev_year_data.empty else 0
                    yoy_delta = ((current_val - prev_year_val) / abs(prev_year_val)) * 100 if prev_year_val else 0

                    st.metric(label=f"{latest_trade_date.strftime('%Y년 %m월')} {label}", value=f"${current_val/1e9:.2f}B")
                    st.markdown(f"""
                    <div style="font-size: 0.8rem; text-align: right; color: #555;">
                        전월 대비: <b style="color:{'red' if mom_delta < 0 else 'green'};">{mom_delta:+.1f}%</b><br>
                        전년 대비: <b style="color:{'red' if yoy_delta < 0 else 'green'};">{yoy_delta:+.1f}%</b>
                    </div>
                    """, unsafe_allow_html=True)

    def _render_charts(self, df: pd.DataFrame):
        """데이터를 기반으로 Altair 차트를 생성하고 렌더링합니다."""
        # --- 차트 설정 및 변수 ---
        brush = alt.selection_interval(encodings=['x'])
        nearest = alt.selection_point(encodings=['x'], nearest=True, empty=False)
        
        base_cols = ['export_amount', 'import_amount', 'trade_balance']
        trailing = '_trailing_12m' if st.session_state.is_12m_trailing else ''
        growth = '_yoy_growth' if st.session_state.show_yoy_growth else ''
        cols_to_use = [f"{col}{trailing}{growth}" for col in base_cols]
        export_col, import_col, balance_col = cols_to_use

        # --- 베이스 차트 ---
        base_chart = alt.Chart(df).encode(x=alt.X('Date:T', title=None))
        
        # --- 툴팁 레이어 ---
        tooltip_layer = base_chart.mark_rule(color='gray').encode(
            opacity=alt.condition(nearest, alt.value(0.3), alt.value(0)),
            tooltip=[
                alt.Tooltip('Date:T', title='날짜', format='%Y-%m'),
                alt.Tooltip('kospi_price:Q', title='KOSPI 200', format=',.2f'),
                alt.Tooltip(export_col, title=f"수출", format=',.2f' if not growth else '.2f'),
                alt.Tooltip(import_col, title=f"수입", format=',.2f' if not growth else '.2f'),
                alt.Tooltip(balance_col, title=f"무역수지", format=',.2f' if not growth else '.2f'),
            ]
        ).add_params(nearest)
        
        # --- KOSPI 차트 ---
        kospi_chart = base_chart.mark_line(color=KOSPI_COLOR).encode(
            y=alt.Y('kospi_price:Q', title='KOSPI 200', axis=alt.Axis(tickCount=4, grid=False)),
            opacity=alt.condition(brush, alt.value(1.0), alt.value(0.8))
        ).properties(
            height=150, title=alt.TitleParams("KOSPI 200 지수", anchor='start', fontSize=16)
        )

        # --- 무역 데이터 Melt ---
        trade_df = df.dropna(subset=cols_to_use).melt(
            id_vars=['Date'], value_vars=cols_to_use, var_name='지표', value_name='값'
        )
        col_map = {export_col: '수출', import_col: '수입', balance_col: '무역수지'}
        trade_df['지표'] = trade_df['지표'].map(col_map)
        
        # --- 무역 차트 ---
        y_axis_format = "format(datum.value / 1e9, '.0f') + 'B'" if not growth else '.0f'
        
        trade_base = alt.Chart(trade_df).encode(
            x=alt.X('Date:T', title=None, axis=alt.Axis(format='%Y-%m', labelAngle=-45)),
            color=alt.Color('지표:N', scale=alt.Scale(
                domain=['수출', '수입', '무역수지'], 
                range=[PRIMARY_COLOR, SECONDARY_COLOR, TERTIARY_COLOR]),
                legend=alt.Legend(title="구분", orient='top-left')
            )
        )
        
        line_chart = trade_base.transform_filter(
            alt.datum.지표 != '무역수지'
        ).mark_line(strokeWidth=2.5).encode(
            y=alt.Y('값:Q', title="금액 (수출입)" if not growth else "YoY 성장률 (%)", axis=alt.Axis(labelExpr=y_axis_format))
        )
        
        area_chart = trade_base.transform_filter(
            alt.datum.지표 == '무역수지'
        ).mark_area(opacity=0.4, line={'color': TERTIARY_COLOR}).encode(
            y=alt.Y('값:Q', title="금액 (무역수지)" if not growth else "YoY 성장률 (%)", axis=alt.Axis(labelExpr=y_axis_format))
        )
        
        trade_chart = alt.layer(line_chart, area_chart).resolve_scale(y='independent').properties(
            height=350, title=alt.TitleParams(f"{st.session_state.selected_country} 무역 데이터", anchor='start', fontSize=16)
        )
        
        # --- 탐색기 차트 (Overview) ---
        overview = base_chart.mark_area(color='lightgray', opacity=0.5).encode(
            y=alt.Y('kospi_price:Q', title=None, axis=None),
        ).properties(
            height=80, title='전체 기간 탐색기'
        ).add_params(brush)

        # --- 최종 차트 결합 ---
        detail_view = alt.layer(kospi_chart, trade_chart, tooltip_layer).resolve_scale(y='independent')
        
        final_chart = alt.vconcat(
            detail_view, overview, bounds='flush', spacing=20
        ).resolve_legend(
            color="independent"
        ).configure_view(stroke=None)
        
        st.altair_chart(final_chart, use_container_width=True)

    def _render_controls(self):
        """데이터 보기 옵션을 위한 컨트롤 패널을 렌더링합니다."""
        with st.expander("⚙️ 데이터 보기 옵션", expanded=False):
            st.selectbox(
                '**국가 선택**', COUNTRY_OPTIONS, key='selected_country'
            )
            st.radio(
                '**데이터 형태 (무역)**', ['월별', '12개월 누적'], 
                index=1 if st.session_state.is_12m_trailing else 0,
                key='data_form', horizontal=True
            )
            st.radio(
                '**표시 단위 (무역)**', ['금액', 'YoY'], 
                index=1 if st.session_state.show_yoy_growth else 0,
                key='unit_form', horizontal=True
            )
            
            # 라디오 버튼 값에 따라 세션 상태 업데이트
            st.session_state.is_12m_trailing = (st.session_state.data_form == '12개월 누적')
            st.session_state.show_yoy_growth = (st.session_state.unit_form == 'YoY')

    def run(self):
        """대시보드 애플리케이션을 실행합니다."""
        with st.spinner('데이터를 불러오는 중입니다...'):
            trade_data, kospi_data, kospi_msg = self._load_and_prepare_data()

        if trade_data is None or kospi_data is None:
            st.error("데이터 로딩에 실패했습니다. 파일을 확인하거나 인터넷 연결을 점검해주세요.")
            if kospi_msg: st.warning(kospi_msg)
            return
            
        self._render_controls()
        
        display_df = self._get_display_df(trade_data, kospi_data)
        
        if display_df.empty:
            st.warning("표시할 데이터가 없습니다. 옵션을 변경해보세요.")
            return
            
        self._render_header_and_metrics(display_df)
        self._render_charts(display_df)

        with st.container(border=True):
            st.subheader("데이터 출처 정보")
            st.markdown(
                "- **수출입 데이터**: `trade_data.csv` (원본: [관세청 수출입 실적](https://www.data.go.kr/data/15101211/openapi.do))\n"
                "- **KOSPI 200 데이터**: `yfinance` (원본: **Yahoo Finance**)"
            )

if __name__ == "__main__":
    app = Dashboard()
    app.run()
