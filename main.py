import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="일별 박스오피스", page_icon="🎬", layout="wide"
)

# ==========================================
# 2. 날짜 계산 (한국 시간 기준 '어제')
# ==========================================
# 배포 서버 시계(UTC) 대신 한국 표준시(KST)를 기준으로 설정합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday = now_kst - datetime.timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.title(f"🎬 {display_date} 박스오피스")
st.caption(
    "영화진흥위원회(KOBIS) Open API 데이터를 기반으로 제공되는 일별 박스오피스 순위입니다."
)

# ==========================================
# 3. API Key 및 데이터 요청
# ==========================================
# Streamlit Cloud의 Secrets에 저장된 KOBIS_KEY를 안전하게 불러옵니다.
api_key = st.secrets.get("KOBIS_KEY")

if not api_key:
    st.error("🔑 API 인증키가 설정되지 않았습니다.")
    st.info(
        "**확인 사항:**\n"
        "Streamlit Cloud 앱 설정의 `App settings -> Secrets` 항목에 아래와 같이 인증키를 추가했는지 확인해 주세요.\n\n"
        "```toml\n"
        'KOBIS_KEY = "발급받은_KOBIS_API_키"\n'
        "```"
    )
    st.stop()

# KOBIS 일별 박스오피스 API 요청 주소
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()  # HTTP 상태 코드 4xx, 5xx 에러 체크
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error("📡 API 서버와의 통신 중 오류가 발생했습니다.")
    st.info(
        "**확인 사항:**\n"
        "- 네트워크 연결 상태를 확인해 주세요.\n"
        "- KOBIS API 서비스가 점검 중인지 확인해 주세요.\n"
        f"- 상세 오류: `{e}`"
    )
    st.stop()

# ==========================================
# 4. API 응답 데이터 예외 처리
# ==========================================
# KOBIS API는 인증키 오류 시에도 HTTP 200 상태코드와 함께 'faultInfo'를 반환합니다.
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
    st.error("⚠️ API 오류가 발생했습니다.")
    st.info(
        "**확인 사항:**\n"
        "- Streamlit Secrets에 입력한 `KOBIS_KEY`가 올바른지 확인해 주세요.\n"
        f"- KOBIS 전달 메시지: `{fault_msg}`"
    )
    st.stop()

# 박스오피스 목록 데이터 추출
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있는 경우 처리
if not daily_list:
    st.warning("ℹ️ 조회된 영화 목록이 없습니다.")
    st.info(
        "**확인 사항:**\n"
        f"- 조회 기준일({display_date})의 박스오피스 데이터가 아직 집계되지 않았을 수 있습니다.\n"
        "- KOBIS 홈페이지에서 해당 날짜의 박스오피스가 정상 개시되었는지 확인해 주세요."
    )
    st.stop()

# ==========================================
# 5. 데이터 전처리
# ==========================================
df = pd.DataFrame(daily_list)

# API 응답 결과는 문자열 형태로 제공되므로, 숫자로 형변환을 수행합니다.
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# ==========================================
# 6. UI 시각화 - 1위 영화 지표 카드
# ==========================================
top_movie = df.iloc[0]

st.markdown("### 🏆 어제의 1위 영화")
st.subheader(f"**{top_movie['movieNm']}**")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="일일 관객수", value=f"{int(top_movie['audiCnt']):,} 명"
    )
with col2:
    st.metric(
        label="누적 관객수", value=f"{int(top_movie['audiAcc']):,} 명"
    )
with col3:
    st.metric(
        label="스크린수", value=f"{int(top_movie['scrnCnt']):,} 개"
    )

st.divider()

# ==========================================
# 7. UI 시각화 - 관객수 상위 5편 막대그래프
# ==========================================
st.markdown("### 📊 관객수 상위 5개 영화")
top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()
top5_df.columns = ["영화명", "관객수"]

# Streamlit 내장 막대그래프로 시각화
st.bar_chart(data=top5_df, x="영화명", y="관객수", use_container_width=True)

st.divider()

# ==========================================
# 8. UI 시각화 - 박스오피스 전체 표
# ==========================================
st.markdown("### 📋 박스오피스 순위 목록")

# 표 출력을 위한 데이터 프레임 정제
table_df = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 화면 전체 너비를 활용하는 데이터 표 출력 (숫자 세파레이터 자동 적용)
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(format="%d"),
        "관객수": st.column_config.NumberColumn(format="%d 명"),
        "누적관객": st.column_config.NumberColumn(format="%d 명"),
        "스크린수": st.column_config.NumberColumn(format="%d 개"),
    },
)
