import streamlit as st
import pandas as pd
import os
import math
import base64
from datetime import datetime, date, timedelta
from calendar import monthrange
from streamlit_option_menu import option_menu

# 쿠키 매니저 (설치 필요: pip install streamlit-cookies-manager)
try:
    from streamlit_cookies_manager import CookieManager
except ImportError:
    st.error("필수 라이브러리 누락: 'streamlit-cookies-manager'를 설치해주세요.")
    st.stop()

# --- [0. 기본 설정] ---
st.set_page_config(
    page_title="조각달과자점", 
    page_icon="🥐", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- [1. 디자인 & CSS (모바일 최적화)] ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Noto Sans KR', sans-serif;
        color: #4E342E;
    }
    .stApp { background-color: #FFF3E0; }
    
    /* 헤더 및 불필요 요소 숨김 */
    header { visibility: hidden !important; }
    #MainMenu, .stDeployButton, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
        visibility: hidden; display: none;
    }

    /* 모바일 최적화 */
    @media (max-width: 768px) {
        section[data-testid="stSidebar"] { width: 200px !important; }
        .block-container { padding-top: 20px !important; padding-left: 10px !important; padding-right: 10px !important;}
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
    }

    /* 버튼 스타일 */
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }

    /* 카드 스타일 (데이터 표시용) */
    div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
        border-radius: 10px; border: 1px solid #E0E0E0;
    }
    
    /* 로고 컨테이너 */
    .logo-container {
        display: flex; flex-direction: column; justify-content: center; align-items: center; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 데이터 파일 정의 및 유틸리티] ---
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

def is_admin(): return st.session_state.get("role") in ["Manager", "관리자"]

def get_img_as_base64(file):
    if not os.path.exists(file): return ""
    with open(file, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

def load(key): 
    # 파일이 깨지거나 비어있을 경우 대비
    try:
        df = pd.read_csv(FILES[key])
        return df
    except Exception:
        return pd.DataFrame()

def save(key, df): df.to_csv(FILES[key], index=False)

def init_db():
    if not os.path.exists(FILES["users"]):
        pd.DataFrame({"username": ["admin"], "password": ["1234"], "name": ["사장님"], "role": ["Manager"]}).to_csv(FILES["users"], index=False)
    if not os.path.exists(FILES["posts"]):
        pd.DataFrame(columns=["id", "category", "sub_category", "title", "content", "author", "date"]).to_csv(FILES["posts"], index=False)
    if not os.path.exists(FILES["checklist_def"]):
        pd.DataFrame({"type": ["오픈", "마감"], "item": ["매장 환기", "포스기 켜기"]}).to_csv(FILES["checklist_def"], index=False)
    if not os.path.exists(FILES["checklist_log"]):
        pd.DataFrame(columns=["date", "type", "item", "user", "time"]).to_csv(FILES["checklist_log"], index=False)
    if not os.path.exists(FILES["schedule"]):
        pd.DataFrame(columns=["id", "date", "user", "start_time", "end_time", "role"]).to_csv(FILES["schedule"], index=False)
    if not os.path.exists(FILES["reservation_menu"]):
        pd.DataFrame({"item_name": ["홀케이크", "소금빵 세트"]}).to_csv(FILES["reservation_menu"], index=False)
    if not os.path.exists(FILES["reservations"]):
        pd.DataFrame(columns=["id", "date", "time", "item", "count", "customer_name", "customer_phone", "created_by", "created_at"]).to_csv(FILES["reservations"], index=False)
    if not os.path.exists(FILES["reservation_logs"]):
        pd.DataFrame(columns=["res_id", "modifier", "modified_at", "details"]).to_csv(FILES["reservation_logs"], index=False)

init_db()

# 쿠키 매니저 초기화
cookies = CookieManager()
if not cookies.ready(): st.stop()


# --- [★ 추가된 핵심 함수: 월간 달력 시각화] ---
def render_monthly_calendar_stable(sched_df, res_df, mode="sch"):
    """
    mode="sch": 스케줄 모드 (근무자 표시)
    mode="res": 예약 모드 (예약 건수 표시)
    """
    now = datetime.now()
    
    # 달력 컨트롤 (연/월 선택)
    c1, c2 = st.columns([1, 1])
    with c1: year = st.selectbox("Year", [now.year, now.year+1], key=f"cal_y_{mode}")
    with c2: month = st.selectbox("Month", range(1, 13), index=now.month-1, key=f"cal_m_{mode}")
    
    _, num_days = monthrange(year, month)
    
    # 데이터 필터링
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{num_days}"
    
    if mode == "sch" and not sched_df.empty:
        mask = (sched_df['date'] >= start_date) & (sched_df['date'] <= end_date)
        df_filtered = sched_df.loc[mask]
    elif mode == "res" and not res_df.empty:
        mask = (res_df['date'] >= start_date) & (res_df['date'] <= end_date)
        df_filtered = res_df.loc[mask]
    else:
        df_filtered = pd.DataFrame()

    # 달력 그리기 (7열 그리드)
    st.markdown("---")
    days = ["월", "화", "수", "목", "금", "토", "일"]
    cols = st.columns(7)
    for i, day in enumerate(days):
        cols[i].markdown(f"**{day}**")

    # 첫 날의 요일 구하기 (0:월요일 ~ 6:일요일)
    first_weekday = date(year, month, 1).weekday()
    
    # 날짜 채우기
    current_col = 0
    # 첫 주 공백 채우기
    row_cols = st.columns(7)
    for _ in range(first_weekday):
        row_cols[current_col].write("")
        current_col += 1
        
    for d in range(1, num_days + 1):
        target_date = f"{year}-{month:02d}-{d:02d}"
        
        with row_cols[current_col]:
            st.markdown(f"**{d}**")
            content_html = ""
            
            if mode == "sch" and not df_filtered.empty:
                # 해당 날짜 근무자 찾기
                workers = df_filtered[df_filtered['date'] == target_date]
                for _, w in workers.iterrows():
                    # 색상 원 + 이름
                    content_html += f"<div style='font-size:0.8rem; color:#4E342E; margin-bottom:2px;'><span style='color:{w['role']};'>●</span> {w['user']}</div>"
            
            elif mode == "res" and not df_filtered.empty:
                # 해당 날짜 예약 건수
                res_count = len(df_filtered[df_filtered['date'] == target_date])
                if res_count > 0:
                    content_html += f"<div style='font-size:0.8rem; background-color:#FFCCBC; border-radius:5px; text-align:center;'>예약 {res_count}건</div>"

            if content_html:
                st.markdown(content_html, unsafe_allow_html=True)
                
        current_col += 1
        if current_col > 6:
            current_col = 0
            row_cols = st.columns(7) # 다음 줄 생성


# --- [3. 페이지별 기능] ---

def login_page():
    st.markdown("<style>.stApp {background-color: #FFFFFF;}</style>", unsafe_allow_html=True)
    st.write("")
    
    # 자동 로그인 처리
    if cookies.get("auto_login") == "true":
        saved_id, saved_pw = cookies.get("saved_id"), cookies.get("saved_pw")
        if saved_id and saved_pw:
            users = load("users")
            user = users[(users["username"] == saved_id) & (users["password"] == saved_pw)]
            if not user.empty:
                st.session_state.update({"logged_in": True, "username": saved_id, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                st.rerun()

    logo_html = f'<img src="data:image/png;base64,{get_img_as_base64("logo.png")}">' if os.path.exists("logo.png") else "<h1 style='font-size:50px;'>🥐</h1>"
    st.markdown(f"""
        <div class="logo-container">
            {logo_html}
            <h2 style='color: #4E342E; margin-top: 10px;'>조각달과자점</h2>
            <p style='color: #8D6E63; font-size: 0.9rem;'>따뜻한 마음을 굽는 업무 공간</p>
        </div>
    """, unsafe_allow_html=True)

    lc1, lc2, lc3 = st.columns([1, 8, 1]) 
    with lc2:
        tab1, tab2 = st.tabs(["로그인", "회원가입"])
        with tab1:
            with st.form("login_form"):
                user_id = st.text_input("아이디")
                user_pw = st.text_input("비밀번호", type="password")
                auto_login = st.checkbox("자동 로그인")
                if st.form_submit_button("입장하기"):
                    users = load("users")
                    user = users[(users["username"] == user_id) & (users["password"] == user_pw)]
                    if not user.empty:
                        st.session_state.update({"logged_in": True, "username": user_id, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                        if auto_login:
                            cookies["auto_login"] = "true"; cookies["saved_id"] = user_id; cookies["saved_pw"] = user_pw; cookies.save()
                        else:
                            if cookies.get("auto_login"): cookies["auto_login"] = "false"; cookies.save()
                        st.rerun()
                    else: st.error("아이디 또는 비밀번호를 확인해주세요.")
        with tab2:
            with st.form("signup_form"):
                new_id = st.text_input("희망 아이디")
                new_pw = st.text_input("희망 비밀번호", type="password")
                new_name = st.text_input("이름 (실명)")
                if st.form_submit_button("가입 신청"):
                    users = load("users")
                    if new_id in users["username"].values: st.warning("이미 존재하는 아이디입니다.")
                    elif not new_id or not new_pw or not new_name: st.warning("모든 정보를 입력해주세요.")
                    else:
                        new_user = pd.DataFrame([{"username": new_id, "password": new_pw, "name": new_name, "role": "Staff"}])
                        save("users", pd.concat([users, new_user], ignore_index=True))
                        st.success("가입완료! 로그인해주세요.")

def page_board(category_name, emoji):
    st.header(f"{emoji} {category_name}")
    if "edit_post_id" not in st.session_state: st.session_state.edit_post_id = None
    
    # 관리자만 글쓰기 가능 (또는 필요시 직원도 가능하게 변경)
    if is_admin():
        with st.expander("➕ 새 글 작성"):
            with st.form(f"write_{category_name}"):
                title = st.text_input("제목")
                content = st.text_area("내용", height=150)
                if st.form_submit_button("등록"):
                    df = load("posts")
                    new_id = 1 if df.empty else df["id"].max() + 1
                    new_post = pd.DataFrame([{"id": new_id, "category": category_name, "sub_category": "-", "title": title, "content": content, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])
                    save("posts", pd.concat([df, new_post], ignore_index=True))
                    st.rerun()

    df = load("posts")
    if not df.empty:
        df = df[df["category"] == category_name].sort_values(by="id", ascending=False)
    
    ITEMS_PER_PAGE = 5 # 모바일 고려하여 페이지당 5개
    total_pages = math.ceil(len(df) / ITEMS_PER_PAGE) if len(df) > 0 else 1
    page_key = f"page_{category_name}"
    if page_key not in st.session_state: st.session_state[page_key] = 1
    
    start_idx = (st.session_state[page_key] - 1) * ITEMS_PER_PAGE
    page_df = df.iloc[start_idx : start_idx + ITEMS_PER_PAGE]
    
    if not page_df.empty:
        for idx, row in page_df.iterrows():
            # 카드 형태 디자인
            with st.container():
                st.markdown(f"#### {row['title']}")
                st.caption(f"{row['date']} | {row['author']}")
                
                # 수정 모드
                if st.session_state.edit_post_id == row['id']:
                    with st.form(f"edit_post_{row['id']}"):
                        e_title = st.text_input("제목", value=row['title'])
                        e_content = st.text_area("내용", value=row['content'])
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("저장"):
                            df_all = load("posts")
                            df_all.loc[df_all["id"] == row['id'], ["title", "content"]] = [e_title, e_content]
                            save("posts", df_all)
                            st.session_state.edit_post_id = None
                            st.rerun()
                        if c2.form_submit_button("취소"):
                            st.session_state.edit_post_id = None
                            st.rerun()
                else:
                    st.write(row['content'])
                    if is_admin():
                        c1, c2, _ = st.columns([1, 1, 5])
                        if c1.button("수정", key=f"edt_{row['id']}"):
                            st.session_state.edit_post_id = row['id']
                            st.rerun()
                        if c2.button("삭제", key=f"del_{row['id']}"):
                            df_all = load("posts")
                            save("posts", df_all[df_all["id"] != row['id']])
                            st.rerun()
                st.divider()

        # 페이지네이션
        if total_pages > 1:
            cols = st.columns(total_pages + 2)
            for i in range(1, total_pages + 1):
                if cols[i].button(str(i), key=f"pg_{category_name}_{i}", disabled=(i==st.session_state[page_key])):
                    st.session_state[page_key] = i
                    st.rerun()
    else:
        st.info("등록된 글이 없습니다.")

def page_checklist():
    st.header("✅ 체크리스트")
    today = datetime.now().strftime("%Y-%m-%d")
    items_df = load("checklist_def")
    log_df = load("checklist_log")
    
    # 컬럼이 없을 경우 대비
    if log_df.empty: log_df = pd.DataFrame(columns=["date", "type", "item", "user", "time"])
        
    today_log = log_df[log_df["date"] == today]
    
    tab1, tab2 = st.tabs(["☀️ 오픈", "🌙 마감"])
    
    def render_check(check_type):
        items = items_df[items_df["type"] == check_type]["item"].tolist() if not items_df.empty else []
        if not items:
            st.info("설정된 항목이 없습니다.")
            return

        done_items = today_log[(today_log["type"] == check_type) & (today_log["item"].isin(items))]
        done_count = len(done_items)
        
        st.progress(done_count / len(items), text=f"진행률: {done_count}/{len(items)}")
        
        for item in items:
            is_done = not today_log[(today_log["type"] == check_type) & (today_log["item"] == item)].empty
            
            with st.container():
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{item}**")
                
                if is_done:
                    rec = today_log[(today_log["type"] == check_type) & (today_log["item"] == item)].iloc[0]
                    c2.caption(f"{rec['user']}\n{rec['time']}")
                else:
                    if c2.button("완료", key=f"{check_type}_{item}"):
                        new_log = pd.DataFrame([{"date": today, "type": check_type, "item": item, "user": st.session_state["name"], "time": datetime.now().strftime("%H:%M")}])
                        save("checklist_log", pd.concat([log_df, new_log], ignore_index=True))
                        st.rerun()
            st.markdown("---") # 구분선

    with tab1: render_check("오픈")
    with tab2: render_check("마감")

def page_schedule():
    st.header("📅 근무표")
    
    sched_df = load("schedule")
    if "id" not in sched_df.columns: sched_df["id"] = range(1, len(sched_df) + 1); save("schedule", sched_df)

    # 상단: 월간 뷰 (시각화)
    with st.expander("🗓️ 월간 달력 보기", expanded=True):
        render_monthly_calendar_stable(sched_df, pd.DataFrame(), "sch")

    st.divider()

    # 하단: 일별 상세 관리
    sel_date_obj = datetime.strptime(st.session_state.selected_date, "%Y-%m-%d").date()
    new_sel_date_obj = st.date_input("날짜 상세 조회", value=sel_date_obj, key="sch_date_picker_main")
    
    if new_sel_date_obj != sel_date_obj:
        st.session_state.selected_date = new_sel_date_obj.strftime("%Y-%m-%d")
        st.rerun()

    sel_date = st.session_state.selected_date
    st.subheader(f"{sel_date} 근무자")

    if is_admin():
        with st.expander("➕ 근무 추가"):
            with st.form("add_sch"):
                users = load("users")
                s_user = st.selectbox("직원", users["name"].unique())
                times = [f"{h:02d}:00" for h in range(6, 24)]
                c1, c2 = st.columns(2)
                s_start = c1.selectbox("출근", times, index=3)
                s_end = c2.selectbox("퇴근", times, index=12)
                s_color = st.color_picker("색상(달력표시)", "#8D6E63")
                
                if st.form_submit_button("저장"):
                    new_id = 1 if sched_df.empty else sched_df["id"].max() + 1
                    new_sch = pd.DataFrame([{"id": new_id, "date": sel_date, "user": s_user, "start_time": s_start, "end_time": s_end, "role": s_color}])
                    save("schedule", pd.concat([sched_df, new_sch], ignore_index=True))
                    st.rerun()

    daily = sched_df[sched_df["date"] == sel_date].sort_values(by="start_time")
    
    if not daily.empty:
        for idx, row in daily.iterrows():
            with st.container():
                # 스타일링된 박스
                st.markdown(f"""
                <div style="padding:10px; border-radius:10px; background-color:white; border-left: 5px solid {row['role']}; margin-bottom:10px;">
                    <b>{row['user']}</b> <span style="color:gray; font-size:0.9em;">({row['start_time']} ~ {row['end_time']})</span>
                </div>
                """, unsafe_allow_html=True)
                
                if is_admin():
                   if st.button("삭제", key=f"ds_{row['id']}"):
                       save("schedule", sched_df[sched_df["id"] != row['id']])
                       st.rerun()
    else:
        st.info("근무 내역이 없습니다.")


def page_reservation():
    st.header("🎂 예약 관리")
    
    res_df = load("reservations")
    res_logs = load("reservation_logs")
    res_menu = load("reservation_menu")
    menu_list = res_menu["item_name"].tolist() if not res_menu.empty else ["메뉴 없음"]

    if "id" not in res_df.columns: res_df["id"] = range(1, len(res_df) + 1); save("reservations", res_df)
    
    # 1. 월간 달력
    with st.expander("🗓️ 월간 예약 현황", expanded=False):
        render_monthly_calendar_stable(pd.DataFrame(), res_df, "res")

    # 2. 날짜 선택 및 등록
    sel_date_obj = datetime.strptime(st.session_state.res_selected_date, "%Y-%m-%d").date()
    new_sel_date_obj = st.date_input("날짜 선택", value=sel_date_obj, key="res_date_picker_main")
    
    if new_sel_date_obj != sel_date_obj:
        st.session_state.res_selected_date = new_sel_date_obj.strftime("%Y-%m-%d")
        st.rerun()

    sel_date = st.session_state.res_selected_date
    
    # 예약 등록 폼
    with st.expander(f"➕ {sel_date} 예약 등록", expanded=True):
        with st.form("add_res"):
            c1, c2 = st.columns(2)
            r_item = c1.selectbox("메뉴", menu_list)
            r_count = c2.number_input("수량", min_value=1, value=1)
            c3, c4 = st.columns(2)
            r_time = c3.time_input("픽업 시간", datetime.strptime("12:00", "%H:%M"))
            r_name = c4.text_input("고객명")
            r_phone = st.text_input("전화번호 (뒷 4자리)")

            if st.form_submit_button("예약 등록"):
                new_id = 1 if res_df.empty else res_df["id"].max() + 1
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_res = pd.DataFrame([{"id": new_id, "date": sel_date, "time": str(r_time)[:5], "item": r_item, "count": r_count, "customer_name": r_name, "customer_phone": r_phone, "created_by": st.session_state["name"], "created_at": now_str}])
                
                save("reservations", pd.concat([res_df, new_res], ignore_index=True))
                # 로그 저장
                new_log = pd.DataFrame([{"res_id": new_id, "modifier": st.session_state["name"], "modified_at": now_str, "details": "최초 등록"}])
                save("reservation_logs", pd.concat([res_logs, new_log], ignore_index=True))
                st.rerun()

    # 3. 예약 리스트 조회
    st.divider()
    st.subheader(f"{sel_date} 예약 리스트")
    daily = res_df[res_df["date"] == sel_date].sort_values(by="time")
    
    if not daily.empty:
        for idx, row in daily.iterrows():
            with st.container():
                # 카드 디자인
                st.markdown(f"""
                <div style="border:1px solid #ddd; border-radius:10px; padding:15px; margin-bottom:10px; background-color:white;">
                    <h4 style="margin:0;">[{row['time']}] {row['customer_name']} 님</h4>
                    <p style="margin:5px 0;">🛍️ {row['item']} | {row['count']}개 | 📞 {row['customer_phone']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 1])
                if c1.button("삭제", key=f"re_del_{row['id']}"):
                    save("reservations", res_df[res_df["id"] != row['id']])
                    st.rerun()
                
                # 수정 이력 보기
                with st.expander("수정 이력 확인"):
                    logs = res_logs[res_logs["res_id"] == row['id']].sort_values(by="modified_at", ascending=False)
                    for _, l in logs.iterrows():
                        st.text(f"{l['modified_at']} {l['modifier']} : {l['details']}")
    else:
        st.info("예약이 없습니다.")

def page_admin():
    st.header("⚙️ 관리자 설정")
    if "admin_unlocked" not in st.session_state: st.session_state.admin_unlocked = False

    if not st.session_state.admin_unlocked:
        st.warning("🔒 관리자 권한 확인")
        with st.form("admin_pw"):
            pw = st.text_input("관리자 비밀번호", type="password")
            if st.form_submit_button("확인"):
                # 실제 운영 시에는 st.secrets 사용 권장
                if pw == "army1214": 
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else: 
                    st.error("비밀번호 불일치")
        return

    if st.button("🔒 관리자 로그아웃"): st.session_state.admin_unlocked = False; st.rerun()

    tab1, tab2, tab3 = st.tabs(["직원 관리", "체크리스트 설정", "예약 메뉴 설정"])
    with tab1:
        st.subheader("직원 권한 관리")
        users = load("users")
        edited = st.data_editor(users, column_config={"role": st.column_config.SelectboxColumn("권한", options=["Staff", "Manager"], required=True)}, hide_index=True, use_container_width=True)
        if st.button("직원 정보 저장"): save("users", edited); st.success("저장됨")
        
    with tab2:
        st.subheader("체크리스트 항목")
        checklist = load("checklist_def")
        edited_list = st.data_editor(checklist, num_rows="dynamic", use_container_width=True)
        if st.button("체크리스트 저장"): save("checklist_def", edited_list); st.success("저장됨")
        
    with tab3:
        st.subheader("예약 가능 메뉴")
        res_menu = load("reservation_menu")
        edited_menu = st.data_editor(res_menu, num_rows="dynamic", use_container_width=True)
        if st.button("메뉴 저장"): save("reservation_menu", edited_menu); st.success("저장됨")

def main_app():
    # 세션 상태 초기화
    if "selected_date" not in st.session_state: st.session_state.selected_date = datetime.now().strftime("%Y-%m-%d")
    if "res_selected_date" not in st.session_state: st.session_state.res_selected_date = datetime.now().strftime("%Y-%m-%d")
    if "admin_unlocked" not in st.session_state: st.session_state.admin_unlocked = False
    
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=100)
        else: st.write("🥐 **조각달**")
        
        st.write(f"반갑습니다, **{st.session_state['name']}**님!")
        
        menu = option_menu(
            menu_title=None, 
            options=["공지사항", "스케줄", "예약 현황", "체크리스트", "매뉴얼", "관리자"], 
            icons=['megaphone', 'calendar-week', 'calendar-check', 'check2-square', 'journal-text', 'gear'], 
            default_index=0, 
            styles={
                "container": {"padding": "0!important", "background-color": "#FFF3E0"},
                "icon": {"color": "#5D4037", "font-size": "14px"}, 
                "nav-link": {"font-size": "14px", "text-align": "left", "margin":"0px", "--hover-color": "#D7CCC8", "color": "#4E342E"},
                "nav-link-selected": {"background-color": "#8D6E63", "color": "white"}
            }
        )
        
        st.markdown("---")
        if st.button("로그아웃"):
            st.session_state["logged_in"] = False
            st.session_state["admin_unlocked"] = False 
            if cookies.get("auto_login"): 
                cookies["auto_login"] = "false"
                cookies.save()
            st.rerun()

    if menu == "공지사항": page_board("공지사항", "📢")
    elif menu == "스케줄": page_schedule()
    elif menu == "예약 현황": page_reservation()
    elif menu == "체크리스트": page_checklist()
    elif menu == "매뉴얼": page_board("회사 매뉴얼", "📘")
    elif menu == "관리자": page_admin()

# 앱 실행 진입점
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_page()
else:
    main_app()
