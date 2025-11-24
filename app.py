import streamlit as st
import pandas as pd
import os
import math
import base64
from datetime import datetime, date # datetime과 date 모듈 모두 사용
from streamlit_option_menu import option_menu
try:
    from streamlit_cookies_manager import CookieManager
except ImportError:
    st.error("필수 라이브러리 누락: requirements.txt를 확인해주세요.")
    st.stop()

# --- [0. 기본 설정] ---
st.set_page_config(
    page_title="조각달과자점", 
    page_icon="🥐", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- [1. 디자인 & CSS] ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Noto Sans KR', sans-serif;
        color: #4E342E;
    }
    .stApp { background-color: #FFF3E0; }
    
    /* 상단 헤더 및 메뉴 버튼 */
    header { visibility: visible !important; background-color: transparent !important; }
    [data-testid="stHeader"] button { color: #4E342E !important; }

    /* 불필요 요소 숨김 */
    #MainMenu, .stDeployButton, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
        visibility: hidden; display: none;
    }

    /* 모바일 최적화 */
    @media (max-width: 768px) {
        /* 사이드바 너비 축소 */
        section[data-testid="stSidebar"] { width: 150px !important; }
        [data-testid="stSidebarCollapseButton"] { display: block !important; color: #4E342E !important; }
        .block-container { padding-bottom: 400px !important; padding-left: 10px !important; padding-right: 10px !important;}
        
        /* 기본 글씨 크기 조정 */
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
    }

    /* 버튼 스타일 */
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 15px; border: none;
        padding: 0.6rem; font-weight: bold; width: 100%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }

    /* 입력창 스타일 */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stDateInput>div>div>input, .stTimeInput>div>div>input {
        border-radius: 10px; border: 1px solid #BCAAA4; background-color: #FFFFFF; height: 45px;
    }
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        background-color: #FFFFFF; padding: 15px; border-radius: 15px;
        border: 1px solid #EFEBE9; margin-bottom: 10px;
    }
    .logo-container {
        display: flex; flex-direction: column; justify-content: center; align-items: center; margin-bottom: 20px;
    }
    .logo-container img { width: 120px; height: auto; margin-bottom: 10px; }
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
    with open(file, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

def load(key): return pd.read_csv(FILES[key])
def save(key, df): df.to_csv(FILES[key], index=False)

# 데이터 파일 초기화
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
        pd.DataFrame({"item_name": ["홀케이크", "소금빵 세트"]}).to.csv(FILES["reservation_menu"], index=False)
    if not os.path.exists(FILES["reservations"]):
        pd.DataFrame(columns=["id", "date", "time", "item", "count", "customer_name", "customer_phone", "created_by", "created_at"]).to_csv(FILES["reservations"], index=False)
    if not os.path.exists(FILES["reservation_logs"]):
        pd.DataFrame(columns=["res_id", "modifier", "modified_at", "details"]).to.csv(FILES["reservation_logs"], index=False)

init_db()

# 쿠키 매니저
cookies = CookieManager()
if not cookies.ready(): st.stop()

# --- [3. 페이지별 기능] ---

def login_page():
    st.markdown("<style>.stApp {background-color: #FFFFFF;}</style>", unsafe_allow_html=True)
    st.write("")
    
    if cookies.get("auto_login") == "true":
        saved_id, saved_pw = cookies.get("saved_id"), cookies.get("saved_pw")
        if saved_id and saved_pw:
            users = load("users")
            user = users[(users["username"] == saved_id) & (users["password"] == saved_pw)]
            if not user.empty:
                st.session_state.update({"logged_in": True, "username": saved_id, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                st.rerun()

    logo_html = f'<img src="data:image/png;base64,{get_img_as_base64("logo.png")}">' if os.path.exists("logo.png") else "<h1>🥐</h1>"
    st.markdown(f"""<div class="logo-container">{logo_html}<h2 style='color: #4E342E; margin-top: 10px;'>조각달과자점</h2><p style='color: #8D6E63; font-size: 0.9rem;'>따뜻한 마음을 굽는 업무 공간</p></div>""", unsafe_allow_html=True)

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
                    else: st.error("정보를 확인해주세요.")
        with tab2:
            with st.form("signup_form"):
                new_id = st.text_input("희망 아이디")
                new_pw = st.text_input("희망 비밀번호", type="password")
                new_name = st.text_input("이름 (실명)")
                if st.form_submit_button("가입 신청"):
                    users = load("users")
                    if new_id in users["username"].values: st.warning("이미 존재하는 아이디.")
                    else:
                        save("users", pd.concat([users, pd.DataFrame([{"username": new_id, "password": new_pw, "name": new_name, "role": "Staff"}])], ignore_index=True))
                        st.success("가입완료! 로그인해주세요.")

def page_board(category_name, emoji):
    st.header(f"{emoji} {category_name}")
    if "edit_post_id" not in st.session_state: st.session_state.edit_post_id = None
    
    if is_admin():
        with st.expander("➕ 새 글 작성"):
            with st.form(f"write_{category_name}"):
                title = st.text_input("제목")
                content = st.text_area("내용")
                if st.form_submit_button("등록"):
                    df = load("posts")
                    new_id = 1 if df.empty else df["id"].max() + 1
                    save("posts", pd.concat([df, pd.DataFrame([{"id": new_id, "category": category_name, "sub_category": "-", "title": title, "content": content, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])], ignore_index=True))
                    st.rerun()

    df = load("posts")
    df = df[df["category"] == category_name].sort_values(by="id", ascending=False)
    
    ITEMS_PER_PAGE = 10
    total_pages = math.ceil(len(df) / ITEMS_PER_PAGE) if len(df) > 0 else 1
    page_key = f"page_{category_name}"
    if page_key not in st.session_state: st.session_state[page_key] = 1
    
    start_idx = (st.session_state[page_key] - 1) * ITEMS_PER_PAGE
    page_df = df.iloc[start_idx : start_idx + ITEMS_PER_PAGE]
    
    if not page_df.empty:
        for idx, row in page_df.iterrows():
            label = f"[{row['date']}] {row['title']} ({row['author']})"
            with st.expander(label, expanded=(st.session_state.edit_post_id == row['id'])):
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
                        st.divider()
                        c1, c2 = st.columns([1, 9])
                        if c1.button("수정", key=f"edt_{row['id']}"):
                            st.session_state.edit_post_id = row['id']
                            st.rerun()
                        if c2.button("삭제", key=f"del_{row['id']}"):
                            df_all = load("posts")
                            save("posts", df_all[df_all["id"] != row['id']])
                            st.rerun()
        if total_pages > 1:
            st.divider()
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
    today_log = log_df[log_df["date"] == today]
    
    tab1, tab2 = st.tabs(["☀️ 오픈", "🌙 마감"])
    
    def render_check(check_type):
        items = items_df[items_df["type"] == check_type]["item"].tolist()
        done = len(today_log[(today_log["type"] == check_type) & (today_log["item"].isin(items))])
        if items: st.progress(done / len(items), text=f"진행률: {done}/{len(items)}")
        
        for item in items:
            is_done = not today_log[(today_log["type"] == check_type) & (today_log["item"] == item)].empty
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{item}**")
            if is_done:
                rec = today_log[(today_log["type"] == check_type) & (today_log["item"] == item)].iloc[0]
                c2.success(f"{rec['user']}")
            else:
                if c2.button("완료", key=f"{check_type}_{item}"):
                    save("checklist_log", pd.concat([log_df, pd.DataFrame([{"date": today, "type": check_type, "item": item, "user": st.session_state["name"], "time": datetime.now().strftime("%H:%M")}])], ignore_index=True))
                    st.rerun()
    with tab1: render_check("오픈")
    with tab2: render_check("마감")

# --- [스케줄 페이지 (달력 안정화)] ---
def page_schedule():
    st.header("📅 근무표")
    if "selected_date" not in st.session_state: st.session_state.selected_date = datetime.now().strftime("%Y-%m-%d")
    if "edit_sch_id" not in st.session_state: st.session_state.edit_sch_id = None

    sched_df = load("schedule")
    if "id" not in sched_df.columns: sched_df["id"] = range(1, len(sched_df) + 1); save("schedule", sched_df)

    # 1. [상단] 날짜 선택기 (클릭 달력 대체)
    sel_date_obj = datetime.strptime(st.session_state.selected_date, "%Y-%m-%d").date()
    
    # st.date_input을 달력처럼 사용
    new_sel_date_obj = st.date_input(
        "날짜 선택", 
        value=sel_date_obj,
        key="sch_date_picker_main"
    )
    
    # 선택된 날짜가 바뀌면 세션에 저장하고 새로고침
    if new_sel_date_obj != sel_date_obj:
        st.session_state.selected_date = new_sel_date_obj.strftime("%Y-%m-%d")
        st.rerun()

    sel_date = st.session_state.selected_date
    st.subheader(f"📌 {sel_date} 근무")

    if is_admin():
        with st.expander(f"➕ {sel_date} 근무 추가", expanded=True):
            with st.form("add_sch"):
                users = load("users")
                # [안정화] 날짜 입력창은 고정된 날짜 선택기를 참조
                c_date = st.date_input("날짜", datetime.strptime(sel_date, "%Y-%m-%d"), key=f"sch_d_{sel_date}")
                s_user = st.selectbox("직원", users["name"].unique())
                times = [f"{h:02d}:00" for h in range(6, 24)]
                c1, c2 = st.columns(2)
                s_start = c1.selectbox("출근", times, index=3)
                s_end = c2.selectbox("퇴근", times, index=12)
                s_color = st.color_picker("색상", "#8D6E63")
                
                if st.form_submit_button("추가"):
                    new_id = 1 if sched_df.empty else sched_df["id"].max() + 1
                    save("schedule", pd.concat([sched_df, pd.DataFrame([{"id": new_id, "date": str(c_date), "user": s_user, "start_time": s_start, "end_time": s_end, "role": s_color}])], ignore_index=True))
                    st.rerun()

    daily = sched_df[sched_df["date"] == sel_date].sort_values(by="start_time")
    if not daily.empty:
        for idx, row in daily.iterrows():
            if st.session_state.edit_sch_id == row['id']:
                with st.container(border=True):
                    with st.form(f"edit_sch_{row['id']}"):
                        times = [f"{h:02d}:00" for h in range(6, 24)]
                        try: s_idx, e_idx = times.index(row['start_time']), times.index(row['end_time'])
                        except: s_idx, e_idx = 3, 12
                        
                        c1, c2 = st.columns(2)
                        n_s = c1.selectbox("출근", times, index=s_idx)
                        n_e = c2.selectbox("퇴근", times, index=e_idx)
                        n_c = st.color_picker("색상", row['role'])
                        
                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("저장"):
                            sched_df.loc[sched_df["id"] == row['id'], ["start_time", "end_time", "role"]] = [n_s, n_e, n_c]
                            save("schedule", sched_df)
                            st.session_state.edit_sch_id = None
                            st.rerun()
                        if b2.form_submit_button("취소"):
                            st.session_state.edit_sch_id = None
                            st.rerun()
            else:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([0.5, 4, 2])
                    c1.markdown(f"<div style='width:20px;height:20px;background-color:{row['role']};border-radius:50%;margin-top:10px;'></div>", unsafe_allow_html=True)
                    c2.markdown(f"**{row['user']}** ({row['start_time']}~{row['end_time']})")
                    if is_admin():
                        with c3:
                            b1, b2 = st.columns(2)
                            if b1.button("수정", key=f"es_{row['id']}"): st.session_state.edit_sch_id = row['id']; st.rerun()
                            if b2.button("삭제", key=f"ds_{row['id']}"): save("schedule", sched_df[sched_df["id"] != row['id']]); st.rerun()
    else:
        st.info("근무 내역이 없습니다.")

    st.divider()
    st.subheader("월간 근무표 (참조용)")
    
    # [새로운 달력] st.date_input을 활용한 안정적인 달력
    
    # 임시 달력 기능: 이 부분은 차후 재구현 필요 시 Streamlit Calendar 라이브러리를 사용하지 않고 
    # HTML과 JS를 직접 주입하는 방식으로 개선해야 합니다.
    # 현재는 안정적인 st.date_input으로 대체되었습니다.
    
    # st.date_input을 다시 호출하여 달력 영역 제공
    st.date_input(
        "날짜 이동", 
        value=sel_date_obj,
        key="sch_date_picker_bottom"
    )
    st.caption("위 달력으로 날짜를 선택하면 상단 리스트가 자동으로 바뀝니다.")


# --- [예약 현황 페이지 (달력 안정화)] ---
def page_reservation():
    st.header("📅 예약 현황")
    if "res_selected_date" not in st.session_state: st.session_state.res_selected_date = datetime.now().strftime("%Y-%m-%d")
    if "edit_res_id" not in st.session_state: st.session_state.edit_res_id = None

    res_df = load("reservations")
    res_logs = load("reservation_logs")
    res_menu = load("reservation_menu")
    menu_list = res_menu["item_name"].tolist()

    if "id" not in res_df.columns: res_df["id"] = range(1, len(res_df) + 1); save("reservations", res_df)

    # 1. [상단] 날짜 선택기
    sel_date_obj = datetime.strptime(st.session_state.res_selected_date, "%Y-%m-%d").date()

    # st.date_input을 달력처럼 사용
    new_sel_date_obj = st.date_input(
        "날짜 선택", 
        value=sel_date_obj,
        key="res_date_picker_main"
    )
    
    if new_sel_date_obj != sel_date_obj:
        st.session_state.res_selected_date = new_sel_date_obj.strftime("%Y-%m-%d")
        st.rerun()

    sel_date = st.session_state.res_selected_date
    st.subheader(f"🍰 {sel_date} 예약")

    with st.expander(f"➕ {sel_date} 예약 등록", expanded=True):
        with st.form("add_res"):
            if not menu_list:
                st.error("등록된 메뉴가 없습니다.")
                st.form_submit_button("불가")
            else:
                c_date = st.date_input("날짜", datetime.strptime(sel_date, "%Y-%m-%d"), key=f"res_d_{sel_date}")
                c1, c2 = st.columns(2)
                r_item = c1.selectbox("메뉴", menu_list)
                r_count = c2.number_input("개수", min_value=1, value=1)
                c3, c4 = st.columns(2)
                r_time = c3.time_input("시간", datetime.strptime("12:00", "%H:%M"))
                r_name = c4.text_input("고객명")
                r_phone = st.text_input("전화번호")

                if st.form_submit_button("등록"):
                    new_id = 1 if res_df.empty else res_df["id"].max() + 1
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save("reservations", pd.concat([res_df, pd.DataFrame([{"id": new_id, "date": str(c_date), "time": str(r_time)[:5], "item": r_item, "count": r_count, "customer_name": r_name, "customer_phone": r_phone, "created_by": st.session_state["name"], "created_at": now_str}])], ignore_index=True))
                    save("reservation_logs", pd.concat([res_logs, pd.DataFrame([{"res_id": new_id, "modifier": st.session_state["name"], "modified_at": now_str, "details": "최초 등록"}])], ignore_index=True))
                    st.rerun()

    daily = res_df[res_df["date"] == sel_date].sort_values(by="time")
    if not daily.empty:
        for idx, row in daily.iterrows():
            with st.container(border=True):
                if st.session_state.edit_res_id == row['id']:
                    st.info("수정 중")
                    with st.form(f"edit_res_{row['id']}"):
                        u_item = st.selectbox("메뉴", menu_list, index=menu_list.index(row['item']) if row['item'] in menu_list else 0)
                        u_count = st.number_input("개수", value=int(row['count']))
                        u_time = st.time_input("시간", value=datetime.strptime(row['time'], "%H:%M").time())
                        u_name = st.text_input("고객명", value=row['customer_name'])
                        u_phone = st.text_input("전화번호", value=row['customer_phone'])
                        
                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("저장"):
                            res_df.loc[res_df["id"] == row['id'], ["item", "count", "time", "customer_name", "customer_phone"]] = [u_item, u_count, str(u_time)[:5], u_name, u_phone]
                            save("reservations", res_df)
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                            save("reservation_logs", pd.concat([res_logs, pd.DataFrame([{"res_id": row['id'], "modifier": st.session_state["name"], "modified_at": now_str, "details": f"수정 (메뉴:{u_item}, 시간:{str(u_time)[:5]})"}])], ignore_index=True))
                            st.session_state.edit_res_id = None
                            st.rerun()
                        if b2.form_submit_button("취소"):
                            st.session_state.edit_res_id = None
                            st.rerun()
                else:
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f"**[{row['time']}] {row['customer_name']}**")
                        st.write(f"🛍️ {row['item']} ({row['count']}개) | 📞 {row['customer_phone']}")
                        with st.expander("수정 이력"):
                            logs = res_logs[res_logs["res_id"] == row['id']].sort_values(by="modified_at", ascending=False)
                            for _, l in logs.iterrows(): st.text(f"{l['modified_at']} {l['modifier']}: {l['details']}")
                    with c2:
                        if st.button("수정", key=f"re_ed_{row['id']}"): st.session_state.edit_res_id = row['id']; st.rerun()
                        if st.button("삭제", key=f"re_del_{row['id']}"): save("reservations", res_df[res_df["id"] != row['id']]); st.rerun()
    else:
        st.info("예약 내역이 없습니다.")

    st.divider()
    st.subheader("월간 예약 현황 (참조용)")
    
    # st.date_input을 다시 호출하여 달력 영역 제공
    st.date_input(
        "날짜 이동", 
        value=sel_date_obj,
        key="res_date_picker_bottom"
    )
    st.caption("위 달력으로 날짜를 선택하면 상단 리스트가 자동으로 바뀝니다.")


def page_admin():
    st.header("⚙️ 관리자 설정")
    if "admin_unlocked" not in st.session_state: st.session_state.admin_unlocked = False

    if not st.session_state.admin_unlocked:
        st.warning("🔒 관리자 메뉴는 비밀번호가 필요합니다.")
        with st.form("admin_pw"):
            if st.form_submit_button("확인"):
                if st.text_input("비밀번호", type="password") == "army1214": st.session_state.admin_unlocked = True; st.rerun()
                else: st.error("비밀번호 불일치")
        return

    if st.button("🔒 잠그기"): st.session_state.admin_unlocked = False; st.rerun()

    tab1, tab2, tab3 = st.tabs(["직원 권한", "체크리스트", "예약 메뉴"])
    with tab1:
        users = load("users")
        edited = st.data_editor(users, column_config={"role": st.column_config.SelectboxColumn("권한", options=["Staff", "Manager"], required=True)}, hide_index=True, use_container_width=True)
        if st.button("권한 저장"): save("users", edited); st.success("저장됨")
    with tab2:
        checklist = load("checklist_def")
        edited_list = st.data_editor(checklist, num_rows="dynamic", use_container_width=True)
        if st.button("체크리스트 저장"): save("checklist_def", edited_list); st.success("저장됨")
    with tab3:
        res_menu = load("reservation_menu")
        edited_menu = st.data_editor(res_menu, num_rows="dynamic", use_container_width=True)
        if st.button("메뉴 저장"): save("reservation_menu", edited_menu); st.success("저장됨")

# --- [6. 메인 앱 실행] ---
def main_app():
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png", width=100)
        st.write(f"안녕하세요, **{st.session_state['name']}**님!")
        
        menu = option_menu(menu_title=None, options=["공지사항", "스케줄", "예약 현황", "체크리스트", "매뉴얼", "관리자"], icons=['megaphone', 'calendar-week', 'calendar-check', 'check2-square', 'journal-text', 'gear'], menu_icon="cast", default_index=0, styles={"container": {"padding": "0!important", "background-color": "#F5E6D3"}, "icon": {"color": "#5D4037", "font-size": "14px"}, "nav-link": {"font-size": "13px", "text-align": "left", "margin":"0px", "--hover-color": "#D7CCC8", "color": "#4E342E"}, "nav-link-selected": {"background-color": "#8D6E63", "color": "white"}})
        
        if st.button("로그아웃", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["admin_unlocked"] = False 
            if cookies.get("auto_login"): cookies["auto_login"] = "false"; cookies.save()
            st.rerun()

    if menu == "공지사항": page_board("공지사항", "📢")
    elif menu == "스케줄": page_schedule()
    elif menu == "예약 현황": page_reservation()
    elif menu == "체크리스트": page_checklist()
    elif menu == "매뉴얼": page_board("회사 매뉴얼", "📘")
    elif menu == "관리자": page_admin()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login_page()
else: main_app()
