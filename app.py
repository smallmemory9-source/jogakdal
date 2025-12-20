import streamlit as st
import pandas as pd
import os
import math
import base64
import hashlib
import time
from datetime import datetime, date, timedelta
from calendar import monthrange
from streamlit_option_menu import option_menu
from filelock import FileLock  # 설치 필요: pip install filelock

# --- [0. 라이브러리 설치 안내] ---
# 터미널에서 다음 명령어를 실행하세요:
# pip install streamlit pandas streamlit-option-menu streamlit-cookies-manager filelock

# 쿠키 매니저
try:
    from streamlit_cookies_manager import CookieManager
except ImportError:
    st.error("필수 라이브러리 누락: 'streamlit-cookies-manager'를 설치해주세요.")
    st.stop()

# --- [1. 기본 설정] ---
st.set_page_config(
    page_title="조각달과자점 파트너", 
    page_icon="🥐", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- [2. 디자인 & CSS] ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; }
    .stApp { background-color: #FFF3E0; }
    
    /* 모바일 최적화 및 헤더 숨김 */
    header { visibility: hidden !important; }
    .block-container { padding-top: 20px !important; }
    
    /* 버튼 스타일 */
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }
    
    /* 카드 스타일 */
    .card {
        background-color: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px; border: 1px solid #E0E0E0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [3. 데이터 관리 (보안/안전성 강화)] ---
FILES = {
    "users": "users.csv",
    "checklist_def": "checklist_def.csv", 
    "checklist_log": "checklist_log.csv", 
    "schedule": "schedule.csv",
    "posts": "posts.csv",
    "reservation_menu": "reservation_menu.csv",
    "reservations": "reservations.csv",
    "reservation_logs": "reservation_logs.csv"
}

# 비밀번호 해싱 함수 (보안)
def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

# 파일 잠금 로드 (동시성 제어)
def load(key): 
    lock = FileLock(f"{FILES[key]}.lock")
    with lock:
        try:
            if not os.path.exists(FILES[key]): return pd.DataFrame()
            return pd.read_csv(FILES[key])
        except Exception:
            return pd.DataFrame()

# 파일 잠금 저장
def save(key, df): 
    lock = FileLock(f"{FILES[key]}.lock")
    with lock:
        df.to_csv(FILES[key], index=False)

def init_db():
    if not os.path.exists(FILES["users"]):
        # 초기 관리자 (비번: 1234 -> 해시됨)
        admin_pw = hash_password("1234")
        pd.DataFrame({"username": ["admin"], "password": [admin_pw], "name": ["사장님"], "role": ["Manager"], "hourly_wage": [0]}).to_csv(FILES["users"], index=False)
    
    # 필요한 파일들 초기화 (기존 코드 유지하되 급여 정보 컬럼 추가 등)
    if not os.path.exists(FILES["posts"]):
        pd.DataFrame(columns=["id", "category", "title", "content", "author", "date"]).to_csv(FILES["posts"], index=False)
    if not os.path.exists(FILES["schedule"]):
        pd.DataFrame(columns=["id", "date", "user", "start_time", "end_time", "role"]).to_csv(FILES["schedule"], index=False)
    if not os.path.exists(FILES["reservations"]):
        pd.DataFrame(columns=["id", "date", "time", "item", "count", "customer_name", "customer_phone", "created_by"]).to_csv(FILES["reservations"], index=False)

init_db()
cookies = CookieManager()
if not cookies.ready(): st.stop()

def is_admin(): return st.session_state.get("role") in ["Manager", "관리자"]

# --- [4. 유틸리티 함수] ---
def calculate_hours(start_str, end_str):
    """시간 차이 계산 (휴게시간 고려 X, 단순 계산)"""
    fmt = "%H:%M"
    try:
        tdelta = datetime.strptime(end_str, fmt) - datetime.strptime(start_str, fmt)
        return tdelta.seconds / 3600
    except:
        return 0

# --- [5. 페이지 컴포넌트] ---

# (달력 렌더링 함수는 기존 로직이 훌륭하여 그대로 사용하되 스타일만 조금 다듬습니다)
def render_monthly_calendar_stable(sched_df, res_df, mode="sch"):
    now = datetime.now()
    c1, c2 = st.columns([1, 1])
    with c1: year = st.selectbox("Year", [now.year, now.year+1], key=f"y_{mode}")
    with c2: month = st.selectbox("Month", range(1, 13), index=now.month-1, key=f"m_{mode}")
    
    _, num_days = monthrange(year, month)
    start_date, end_date = f"{year}-{month:02d}-01", f"{year}-{month:02d}-{num_days}"
    
    df_filtered = pd.DataFrame()
    if mode == "sch" and not sched_df.empty:
        df_filtered = sched_df[(sched_df['date'] >= start_date) & (sched_df['date'] <= end_date)]
    elif mode == "res" and not res_df.empty:
        df_filtered = res_df[(res_df['date'] >= start_date) & (res_df['date'] <= end_date)]

    st.markdown("---")
    days = ["월", "화", "수", "목", "금", "토", "일"]
    cols = st.columns(7)
    for i, d in enumerate(days): cols[i].markdown(f"<div style='text-align:center; color:gray; font-size:0.8rem;'>{d}</div>", unsafe_allow_html=True)
    
    first_weekday = date(year, month, 1).weekday()
    current_col = 0
    row_cols = st.columns(7)
    
    for _ in range(first_weekday): 
        row_cols[current_col].write("")
        current_col += 1
        
    for d in range(1, num_days + 1):
        target_date = f"{year}-{month:02d}-{d:02d}"
        with row_cols[current_col]:
            st.markdown(f"**{d}**")
            html = ""
            if mode == "sch" and not df_filtered.empty:
                workers = df_filtered[df_filtered['date'] == target_date]
                for _, w in workers.iterrows():
                    html += f"<div style='font-size:0.75rem; background-color:{w.get('role', '#eee')}20; border-left:3px solid {w.get('role', '#8D6E63')}; padding-left:2px; margin-bottom:1px; white-space:nowrap; overflow:hidden;'>{w['user']}</div>"
            elif mode == "res" and not df_filtered.empty:
                cnt = len(df_filtered[df_filtered['date'] == target_date])
                if cnt > 0: html += f"<div style='font-size:0.75rem; background:#FFCCBC; border-radius:4px; text-align:center;'>예약 {cnt}</div>"
            if html: st.markdown(html, unsafe_allow_html=True)
            
        current_col += 1
        if current_col > 6:
            current_col = 0; row_cols = st.columns(7)

# --- [6. 페이지별 로직] ---

def login_page():
    st.markdown("<br><h1 style='text-align:center;'>🥐 조각달과자점</h1>", unsafe_allow_html=True)
    
    # 자동 로그인 확인
    if cookies.get("auto_login") == "true" and cookies.get("saved_id"):
        users = load("users")
        user = users[users["username"] == cookies.get("saved_id")]
        # 주의: 실제 운영시 쿠키에 비번 저장보다 토큰 방식 권장. 편의상 유지하되 비번 검증 생략(이미 검증됨 간주)
        if not user.empty:
             st.session_state.update({"logged_in": True, "username": user.iloc[0]["username"], "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
             st.rerun()

    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    with tab1:
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            auto = st.checkbox("자동 로그인")
            if st.form_submit_button("입장"):
                users = load("users")
                hashed_pw = hash_password(upw)
                user = users[(users["username"] == uid) & (users["password"] == hashed_pw)]
                if not user.empty:
                    st.session_state.update({"logged_in": True, "username": uid, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                    if auto:
                        cookies["auto_login"] = "true"; cookies["saved_id"] = uid; cookies.save()
                    st.rerun()
                else: st.error("정보가 올바르지 않습니다.")
    
    with tab2:
        with st.form("signup"):
            nid = st.text_input("희망 아이디")
            npw = st.text_input("희망 비밀번호", type="password")
            nname = st.text_input("이름")
            nwage = st.number_input("시급 (원)", value=10030, step=100)
            if st.form_submit_button("가입 신청"):
                users = load("users")
                if nid in users["username"].values: st.warning("중복된 아이디")
                elif nid and npw and nname:
                    new_user = pd.DataFrame([{"username": nid, "password": hash_password(npw), "name": nname, "role": "Staff", "hourly_wage": nwage}])
                    save("users", pd.concat([users, new_user], ignore_index=True))
                    st.success("가입 완료! 로그인 해주세요.")

def page_schedule():
    st.header("📅 근무표 & 급여")
    sched = load("schedule")
    if "id" not in sched.columns: sched["id"] = range(1, len(sched)+1)
    
    # 탭 구분
    tab_view, tab_calc = st.tabs(["근무표 보기", "💰 급여 계산기"])
    
    with tab_view:
        with st.expander("🗓️ 월간 달력 펼치기", expanded=True):
            render_monthly_calendar_stable(sched, pd.DataFrame(), "sch")
            
        st.divider()
        sel_date = st.date_input("날짜 상세 조회", value=date.today())
        date_str = sel_date.strftime("%Y-%m-%d")
        
        # 근무 추가 (관리자)
        if is_admin():
            with st.expander("➕ 근무 추가"):
                with st.form("add_sch"):
                    users = load("users")
                    u_name = st.selectbox("직원", users["name"].unique())
                    t_start = st.selectbox("출근", [f"{h:02d}:00" for h in range(6,24)], index=3)
                    t_end = st.selectbox("퇴근", [f"{h:02d}:00" for h in range(6,24)], index=12)
                    color = st.color_picker("색상", "#8D6E63")
                    if st.form_submit_button("등록"):
                        new_id = 1 if sched.empty else sched["id"].max() + 1
                        new_row = pd.DataFrame([{"id": new_id, "date": date_str, "user": u_name, "start_time": t_start, "end_time": t_end, "role": color}])
                        save("schedule", pd.concat([sched, new_row], ignore_index=True))
                        st.rerun()

        daily = sched[sched["date"] == date_str].sort_values("start_time")
        if not daily.empty:
            for _, row in daily.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="card" style="border-left: 5px solid {row['role']};">
                        <b>{row['user']}</b> <span style="float:right; color:#888;">{row['start_time']} ~ {row['end_time']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if is_admin() and st.button("삭제", key=f"d_{row['id']}"):
                        save("schedule", sched[sched["id"] != row['id']])
                        st.rerun()
        else:
            st.info("등록된 근무가 없습니다.")

    with tab_calc:
        st.subheader("💰 이번 달 예상 급여")
        if is_admin():
            target_user = st.selectbox("조회할 직원", load("users")["name"].unique())
        else:
            target_user = st.session_state["name"]
            st.markdown(f"**{target_user}**님의 근무 내역입니다.")

        this_month = date.today().strftime("%Y-%m")
        calc_month = st.selectbox("기준 월", [this_month], index=0) # 필요시 리스트 확장
        
        # 해당 월, 해당 직원 필터링
        my_sched = sched[(sched["user"] == target_user) & (sched["date"].str.startswith(calc_month))]
        
        if not my_sched.empty:
            total_hours = 0
            for _, row in my_sched.iterrows():
                h = calculate_hours(row["start_time"], row["end_time"])
                total_hours += h
            
            # 시급 정보 가져오기
            users = load("users")
            wage = users[users["name"] == target_user]["hourly_wage"].iloc[0] if "hourly_wage" in users.columns else 10030
            
            c1, c2, c3 = st.columns(3)
            c1.metric("총 근무일", f"{len(my_sched)}일")
            c2.metric("총 근무시간", f"{total_hours:.1f}시간")
            c3.metric("예상 급여", f"{int(total_hours * wage):,}원")
            
            with st.expander("상세 내역"):
                st.dataframe(my_sched[["date", "start_time", "end_time"]], use_container_width=True)
        else:
            st.info("근무 내역이 없습니다.")

def page_checklist():
    st.header("✅ 체크리스트")
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # 탭: 오픈/마감/지난기록
    tab1, tab2, tab3 = st.tabs(["☀️ 오픈", "🌙 마감", "📅 기록 조회"])
    
    def render_chk_tab(ctype):
        defs = load("checklist_def")
        if defs.empty: st.info("설정된 항목이 없습니다."); return
        items = defs[defs["type"] == ctype]["item"].tolist()
        
        logs = load("checklist_log")
        today_logs = logs[(logs["date"] == today_str) & (logs["type"] == ctype)]
        
        # 진행률
        done_cnt = len(today_logs[today_logs["item"].isin(items)])
        total_cnt = len(items)
        if total_cnt > 0:
            st.progress(done_cnt/total_cnt, text=f"{done_cnt}/{total_cnt} 완료")
        
        for item in items:
            done_row = today_logs[today_logs["item"] == item]
            is_done = not done_row.empty
            
            with st.container():
                cols = st.columns([0.1, 0.7, 0.2])
                cols[0].checkbox("", value=is_done, key=f"chk_{ctype}_{item}", disabled=True)
                cols[1].markdown(f"**{item}**")
                
                if is_done:
                    rec = done_row.iloc[0]
                    cols[2].caption(f"{rec['user']}\n{rec['time']}")
                else:
                    if cols[2].button("완료", key=f"btn_{ctype}_{item}"):
                        new_log = pd.DataFrame([{"date": today_str, "type": ctype, "item": item, "user": st.session_state["name"], "time": now.strftime("%H:%M")}])
                        save("checklist_log", pd.concat([logs, new_log], ignore_index=True))
                        st.rerun()
            st.markdown("<hr style='margin:5px 0;'>", unsafe_allow_html=True)

    with tab1: render_chk_tab("오픈")
    with tab2: render_chk_tab("마감")
    with tab3:
        st.caption("지난 날짜의 체크리스트 기록을 확인합니다.")
        search_date = st.date_input("날짜 선택", date.today() - timedelta(days=1))
        s_date_str = search_date.strftime("%Y-%m-%d")
        logs = load("checklist_log")
        past_logs = logs[logs["date"] == s_date_str]
        if not past_logs.empty:
            st.dataframe(past_logs[["type", "item", "user", "time"]], use_container_width=True)
        else:
            st.info("기록이 없습니다.")

def page_reservation():
    st.header("🎂 예약 관리")
    res_df = load("reservations")
    if "id" not in res_df.columns: res_df["id"] = range(1, len(res_df)+1)
    
    # 탭: 리스트 뷰 / 캘린더 뷰
    t1, t2 = st.tabs(["리스트 보기", "캘린더 보기"])
    
    with t1:
        sel_date = st.date_input("예약 날짜", date.today(), key="res_date")
        s_date_str = sel_date.strftime("%Y-%m-%d")
        
        with st.expander("➕ 예약 등록하기", expanded=True):
            with st.form("new_res"):
                c1, c2 = st.columns(2)
                menu_opts = load("reservation_menu")["item_name"].tolist() if os.path.exists(FILES["reservation_menu"]) else ["직접 입력"]
                r_item = c1.selectbox("상품", menu_opts)
                r_cnt = c2.number_input("수량", 1, 100, 1)
                c3, c4 = st.columns(2)
                r_name = c3.text_input("고객명")
                r_time = c4.time_input("픽업시간", datetime.strptime("12:00", "%H:%M"))
                r_phone = st.text_input("연락처")
                
                if st.form_submit_button("예약 확정"):
                    new_id = 1 if res_df.empty else res_df["id"].max() + 1
                    new_row = pd.DataFrame([{"id": new_id, "date": s_date_str, "time": str(r_time)[:5], "item": r_item, "count": r_cnt, "customer_name": r_name, "customer_phone": r_phone, "created_by": st.session_state["name"]}])
                    save("reservations", pd.concat([res_df, new_row], ignore_index=True))
                    st.success("등록되었습니다!")
                    time.sleep(0.5)
                    st.rerun()

        st.subheader(f"{s_date_str} 예약 리스트")
        day_res = res_df[res_df["date"] == s_date_str].sort_values("time")
        if not day_res.empty:
            for _, row in day_res.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h4 style="margin:0;">{row['customer_name']} 님 <span style="font-size:0.8rem; color:#888;">({row['time']})</span></h4>
                                <div style="color:#5D4037;">🛍️ {row['item']} {row['count']}개</div>
                                <div style="font-size:0.8rem; color:#aaa;">📞 {row['customer_phone']}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("예약 취소(삭제)", key=f"rdel_{row['id']}"):
                        save("reservations", res_df[res_df["id"] != row['id']])
                        st.rerun()
        else:
            st.info("예약이 없습니다.")

    with t2:
        render_monthly_calendar_stable(pd.DataFrame(), res_df, "res")

# --- [7. 메인 앱 실행] ---
def main():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
    else:
        with st.sidebar:
            st.title("🥐 조각달")
            st.write(f"안녕하세요, **{st.session_state['name']}**님")
            menu = option_menu("메뉴", ["스케줄/급여", "체크리스트", "예약 관리", "로그아웃"],
                icons=['calendar', 'check-square', 'book', 'box-arrow-right'],
                menu_icon="cast", default_index=0,
                styles={"container": {"background-color": "#FFF3E0"}, "nav-link-selected": {"background-color": "#8D6E63"}})
            
            if menu == "로그아웃":
                st.session_state.logged_in = False
                cookies["auto_login"] = "false"
                cookies.save()
                st.rerun()

        if menu == "스케줄/급여": page_schedule()
        elif menu == "체크리스트": page_checklist()
        elif menu == "예약 관리": page_reservation()

if __name__ == "__main__":
    main()
