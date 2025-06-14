import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px # 이 부분은 사용하지 않으므로 필요에 따라 제거하거나 활용 가능

# CSV 파일 경로
CSV_FILE_PATH = 'trade_data.csv'

@st.cache_data
def load_data():
    """
    데이터를 로드하고 필요한 전처리를 수행합니다.
    Streamlit의 캐싱 기능을 사용하여 데이터를 한 번만 로드하도록 최적화합니다.
    """
    try:
        df = pd.read_csv(CSV_FILE_PATH)
        # 'year_month' 컬럼을 datetime 형식으로 변환하여 정렬 및 시각화에 용이하게 합니다.
        # errors='coerce'를 사용하여 변환할 수 없는 값은 NaT (Not a Time)으로 처리합니다.
        df['year_month'] = pd.to_datetime(df['year_month'], errors='coerce')

        # NaT 값 제거 (선택 사항, 데이터 품질에 따라 결정)
        df.dropna(subset=['year_month'], inplace=True)

        # 필요한 숫자 컬럼들이 숫자로 변환되었는지 확인합니다.
        for col in ['export_amount', 'import_amount', 'trade_balance']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0) # 변환 실패 시 0으로 채움

        return df
    except FileNotFoundError:
        st.error(f"Error: '{CSV_FILE_PATH}' 파일을 찾을 수 없습니다. 파일이 올바른 위치에 있는지 확인해주세요.")
        return pd.DataFrame() # 빈 DataFrame 반환
    except Exception as e:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

def create_monthly_chart(df_filtered, country_name):
    """
    월별 수출, 수입, 무역수지 그래프를 생성합니다.
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df_filtered['year_month'], y=df_filtered['export_amount'],
                             mode='lines+markers', name='수출액',
                             hovertemplate='<b>%{x|%Y-%m}</b><br>수출액: %{y:,.0f}'))
    fig.add_trace(go.Scatter(x=df_filtered['year_month'], y=df_filtered['import_amount'],
                             mode='lines+markers', name='수입액',
                             hovertemplate='<b>%{x|%Y-%m}</b><br>수입액: %{y:,.0f}'))
    fig.add_trace(go.Scatter(x=df_filtered['year_month'], y=df_filtered['trade_balance'],
                             mode='lines+markers', name='무역수지',
                             hovertemplate='<b>%{x|%Y-%m}</b><br>무역수지: %{y:,.0f}'))

    fig.update_layout(
        title=f'<span style="font-size: 24px;"><b>{country_name}</b> 월별 수출, 수입, 무역수지</span>',
        xaxis_title='<span style="font-size: 16px;">날짜</span>',
        yaxis_title='<span style="font-size: 16px;">금액</span>',
        hovermode='x unified', # 마우스 오버 시 x축에 해당하는 모든 트레이스의 데이터 표시
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14)),
        template="plotly_white", # 깔끔한 배경 템플릿 적용
        margin=dict(l=50, r=50, t=80, b=50) # 여백 조정
    )
    return fig

def main():
    st.set_page_config(layout="wide", page_title="국가별 무역 데이터 시각화")

    st.title("🌏 국가별 월별 무역 데이터 시각화")
    st.markdown("---") # 구분선 추가

    df = load_data()

    if not df.empty:
        # '총합'을 제외한 고유 국가 목록 가져오기
        countries = df[df['country_name'] != '총합']['country_name'].unique()
        # 정렬하여 사용자에게 보기 좋게 제공
        countries.sort()
        selected_country = st.selectbox("👇 데이터를 보고 싶은 **국가**를 선택하세요:", countries)

        if selected_country:
            df_country = df[df['country_name'] == selected_country].copy()
            # 'year_month' 기준으로 오름차순 정렬
            df_country = df_country.sort_values(by='year_month')

            if not df_country.empty:
                st.subheader(f"📊 **{selected_country}** 월별 무역 동향")
                fig = create_monthly_chart(df_country, selected_country)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"선택하신 국가 '**{selected_country}**'에 대한 데이터가 없습니다. 다른 국가를 선택해주세요.")
    else:
        st.info("데이터를 로드하는 데 실패했거나 데이터 파일이 비어 있습니다. `trade_data.csv` 파일을 확인해주세요.")

if __name__ == '__main__':
    main()