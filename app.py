import streamlit as st
import pandas as pd
import os
import math
from datetime import datetime
from streamlit_calendar import calendar

# --- [0. 디자인 설정] 앱 이름 및 아이콘 설정 ---
st.set_page_config(
    page_title="조각달과자점", 
    page_icon="logo.png", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# 🎨 전문 디자이너의 커스텀 CSS 적용 (화이트 & 브라운 테마)
st.markdown("""
    <style>
    /* 폰트 적용 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Noto Sans KR', sans-serif;
        color: #4E342E;
    }

    /* --- 전체 배경: 흰색으로 변경 --- */
    .stApp {
        background-color: #FFFFFF; 
    }

    /* --- 사이드바 --- */
    [data-testid="stSidebar"] {
        background-color: #F5E6D3;
        border-right: 1px solid #D7CCC8;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #3E2723 !important;
    }

    /* --- 버튼 디자인 --- */
    .stButton>button {
        background: linear-gradient(135deg, #8D6E63 0%, #6D4C41 100%);
        color: white !important;
        border: none;
        border-radius: 12px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(62, 39, 35, 0.2);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #A1887F 0%, #8D6E63 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(62, 39, 35, 0.3);
    }
    [data-testid="stForm"] .stButton>button {
        width: 100%;
    }

    /* --- 입력창 디자인 --- */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stTimeInput>div>div>input, .stDateInput>div>div>input {
        border: 2px solid #BCAAA4;
        border-radius: 8px;
        background-color: #FAFAFA; /* 입력창 내부 살짝 회색조 */
        color: #4E342E;
    }
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>div[data-baseweb="select"]:focus-within {
        border-color: #8D6E63;
        box-shadow: 0 0 0 3px rgba(141, 110, 99, 0.2);
    }
    
    /* --- 탭 디자인 --- */
    .stTabs [data-baseweb="tab-list"] {
        border-bottom-color: #BCAAA4;
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        border-radius: 8px 8px 0px 0px;
        background-color: #EFEBE9;
        color: #6D4C41;
        border: 1px solid transparent;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #FFFFFF; /* 탭 선택시 배경 흰색 */
        color: #3E2723;
        border-color: #BCAAA4;
        border-bottom-color: #FFFFFF;
        font-weight: bold;
    }

    /* --- 컨테이너 디자인 --- */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #EFEBE9;
    }

    /* 상단 헤더 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    header[data-testid="stHeader"] {background: transparent;}
    </style>
    """, unsafe_allow_html=True)

# --- [1. 설정] 데이터 파일 정의 ---
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

# --- [2. 유틸리티] 관리자 여부 확인 ---
def is_admin():
    return st.session_state.get("role") in ["Manager", "관리자"]

# --- [3. 초기화] 데이터 파일 생성 ---
def init_db():
    if not os.path.exists(FILES["users"]):
        df = pd.DataFrame({
            "username": ["admin", "staff1"],
            "password": ["1234", "1111"],
            "name": ["사장님", "김직원"],
            "role": ["Manager", "Staff"]
        })
        df.to_csv(FILES["users"], index=False)

    if not os.path.exists(FILES["posts"]):
        pd.DataFrame(columns=["id", "category", "sub_category", "title", "content", "author", "date"]).to_csv(FILES["posts"], index=False)

    if not os.path.exists(FILES["checklist_def"]):
        df = pd.DataFrame({
            "type": ["오픈", "오픈", "마감", "마감"],
            "item": ["매장 환기", "포스기 켜기", "재고 조사", "전기 차단 확인"]
        })
        df.to_csv(FILES["checklist_def"], index=False)

    if not os.path.exists(FILES["checklist_log"]):
        pd.DataFrame(columns=["date", "type", "item", "user", "time"]).to_csv(FILES["checklist_log"], index=False)
        
    if not os.path.exists(FILES["schedule"]):
        pd.DataFrame(columns=["id", "date", "user", "start_time", "end_time", "role"]).to_csv(FILES["schedule"], index=False)

    if not os.path.exists(FILES["reservation_menu"]):
        df = pd.DataFrame({"item_name": ["홀케이크", "소금빵 세트", "단체 주문"]})
        df.to_csv(FILES["reservation_menu"], index=False)

    if not os.path.exists(FILES["reservations"]):
        pd.DataFrame(columns=["id", "date", "time", "item", "count", "customer_name", "customer_phone", "created_by", "created_at"]).to_csv(FILES["reservations"], index=False)
    
    if not os.path.exists(FILES["reservation_logs"]):
        pd.DataFrame(columns=["res_id", "modifier", "modified_at", "details"]).to_csv(FILES["reservation_logs"], index=False)

init_db()

# --- [4. 데이터 로드/저장] ---
def load(key): 
    df = pd.read_csv(FILES[key])
    if key == "posts" and "sub_category" not in df.columns:
        df["sub_category"] = "기타"
        save("posts", df)
    return df

def save(key, df): df.to_csv(FILES[key], index=False)

# --- [5. 로그인 화면] ---
def login_page():
    # 화면을 3분할해서 가운데(c2)에 내용 배치
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        # [로고 이미지]
        # 정가운데 정렬을 위해 다시 컬럼을 나눕니다.
        l1, l2, l3 = st.columns([1, 1, 1]) 
        with l2:
            if os.path.exists("logo.png"):
                # width=120: 로고 크기를 120픽셀로 고정 (약 1/6 크기)
                st.image("logo.png", width=120) 
            else:
                st.title("🥐")
        
        # 제목 및 부제목 (가운데 정렬)
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>조각달과자점</h2>", unsafe_allow_html=True)
        st.markdown("<h5 style='text-align: center; color: #8D6E63; margin-bottom: 30px;'>따뜻한 하루를 시작하는 업무 공간</h5>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
        with tab1:
            with st.form("login_form"):
                user_id = st.text_input("아이디")
                user_pw = st.text_input("비밀번호", type="password")
                submit = st.form_submit_button("로그인", use_container_width=True)
                if submit:
                    users = load("users")
                    user = users[(users["username"] == user_id) & (users["password"] == user_pw)]
                    if not user.empty:
                        st.session_state.update({"logged_in": True, "username": user_id, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호를 확인해주세요.")
        with tab2:
            st.subheader("신규 직원 가입")
            with st.form("signup_form"):
                new_id = st.text_input("희망 아이디")
                new_pw = st.text_input("희망 비밀번호", type="password")
                new_name = st.text_input("이름 (실명)")
                submit = st.form_submit_button("가입 신청", use_container_width=True)
                if submit:
                    users = load("users")
                    if new_id in users["username"].values:
                        st.warning("이미 존재하는 아이디입니다.")
                    else:
                        new_row = pd.DataFrame([{"username": new_id, "password": new_pw, "name": new_name, "role": "Staff"}])
                        save("users", pd.concat([users, new_row], ignore_index=True))
                        st.success("가입되었습니다! 로그인해주세요.")

# --- [기능 1] 게시판 ---
def page_board(category_name, emoji):
    st.header(f"{emoji} {category_name}")
    if "edit_post_id" not in st.session_state: st.session_state.edit_post_id = None
    page_key = f"page_{category_name}"
    if page_key not in st.session_state: st.session_state[page_key] = 1

    if is_admin():
        with st.expander("➕ 새 글 작성하기"):
            with st.form(f"write_{category_name}"):
                title = st.text_input("제목")
                content = st.text_area("내용")
                if st.form_submit_button("등록", use_container_width=True):
                    df = load("posts")
                    new_id = 1 if df.empty else df["id"].max() + 1
                    new_row = pd.DataFrame([{
                        "id": new_id, "category": category_name, "sub_category": "-",
                        "title": title, "content": content, "author": st.session_state["name"],
                        "date": datetime.now().strftime("%Y-%m-%d")
                    }])
                    save("posts", pd.concat([df, new_row], ignore_index=True))
                    st.rerun()

    df = load("posts")
    df = df[df["category"] == category_name].sort_values(by="id", ascending=False)
    ITEMS_PER_PAGE = 10
    total_items = len(df)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
    current_page = st.session_state[page_key]
    start_idx = (current_page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_df = df.iloc[start_idx:end_idx]
    
    if not page_df.empty:
        for idx, row in page_df.iterrows():
            label = f"[{row['date']}] {row['title']} ({row['author']})"
            with st.expander(label, expanded=(st.session_state.edit_post_id == row['id'])):
                if st.session_state.edit_post_id == row['id']:
                    st.info("✏️ 수정 중")
                    with st.form(f"edit_post_{row['id']}"):
                        edit_title = st.text_input("제목", value=row['title'])
                        edit_content = st.text_area("내용", value=row['content'])
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("저장"):
                            df_all = load("posts")
                            df_all.loc[df_all["id"] == row['id'], "title"] = edit_title
                            df_all.loc[df_all["id"] == row['id'], "content"] = edit_content
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
                        c1, c2, c3 = st.columns([1, 1, 8])
                        if c1.button("수정", key=f"edt_p_{row['id']}"):
                            st.session_state.edit_post_id = row['id']
                            st.rerun()
                        if c2.button("삭제", key=f"del_p_{row['id']}"):
                            df_all = load("posts")
                            df_all = df_all[df_all["id"] != row['id']]
                            save("posts", df_all)
                            st.rerun()
        if total_pages > 1:
            st.divider()
            cols = st.columns(total_pages + 2)
            for i in range(1, total_pages + 1):
                if cols[i].button(str(i), key=f"btn_page_{category_name}_{i}", disabled=(i==current_page)):
                    st.session_state[page_key] = i
                    st.rerun()
            st.caption(f"Page {current_page} of {total_pages}")
    else:
        st.info("등록된 게시글이 없습니다.")

# --- [기능 1-2] 레시피 ---
def page_recipe():
    st.header("🥐 레시피 관리")
    RECIPE_CATS = ["빵 (Bread)", "케이크 (Cake)", "구움과자 (Baked)", "음료 (Beverage)", "기타"]
    if "edit_post_id" not in st.session_state: st.session_state.edit_post_id = None
    
    if is_admin():
        with st.expander("➕ 새 레시피 등록하기"):
            with st.form("write_recipe"):
                r_cat = st.selectbox("종류 선택", RECIPE_CATS)
                r_title = st.text_input("레시피 명 (제품명)")
                r_content = st.text_area("레시피 내용")
                if st.form_submit_button("레시피 저장", use_container_width=True):
                    df = load("posts")
                    new_id = 1 if df.empty else df["id"].max() + 1
                    new_row = pd.DataFrame([{
                        "id": new_id, "category": "레시피", "sub_category": r_cat,
                        "title": r_title, "content": r_content, "author": st.session_state["name"],
                        "date": datetime.now().strftime("%Y-%m-%d")
                    }])
                    save("posts", pd.concat([df, new_row], ignore_index=True))
                    st.success("등록되었습니다.")
                    st.rerun()

    tabs = st.tabs(RECIPE_CATS)
    df = load("posts")
    recipe_df = df[df["category"] == "레시피"]
    
    for i, cat_name in enumerate(RECIPE_CATS):
        with tabs[i]:
            cat_df = recipe_df[recipe_df["sub_category"] == cat_name].sort_values(by="id", ascending=False)
            if not cat_df.empty:
                for idx, row in cat_df.iterrows():
                    label = f"{row['title']} - {row['author']}"
                    with st.expander(label, expanded=(st.session_state.edit_post_id == row['id'])):
                        if st.session_state.edit_post_id == row['id']:
                            st.info("✏️ 레시피 수정 중")
                            with st.form(f"edit_recipe_{row['id']}"):
                                e_cat = st.selectbox("종류", RECIPE_CATS, index=RECIPE_CATS.index(row['sub_category']) if row['sub_category'] in RECIPE_CATS else 0)
                                e_title = st.text_input("제품명", value=row['title'])
                                e_content = st.text_area("내용", value=row['content'])
                                c1, c2 = st.columns(2)
                                if c1.form_submit_button("저장"):
                                    df_all = load("posts")
                                    df_all.loc[df_all["id"] == row['id'], "sub_category"] = e_cat
                                    df_all.loc[df_all["id"] == row['id'], "title"] = e_title
                                    df_all.loc[df_all["id"] == row['id'], "content"] = e_content
                                    save("posts", df_all)
                                    st.session_state.edit_post_id = None
                                    st.rerun()
                                if c2.form_submit_button("취소"):
                                    st.session_state.edit_post_id = None
                                    st.rerun()
                        else:
                            st.markdown(row['content'])
                            if is_admin():
                                st.divider()
                                c1, c2, c3 = st.columns([1, 1, 8])
                                if c1.button("수정", key=f"er_btn_{row['id']}"):
                                    st.session_state.edit_post_id = row['id']
                                    st.rerun()
                                if c2.button("삭제", key=f"dr_btn_{row['id']}"):
                                    df_all = load("posts")
                                    df_all = df_all[df_all["id"] != row['id']]
                                    save("posts", df_all)
                                    st.rerun()
            else:
                st.caption(f"등록된 {cat_name} 레시피가 없습니다.")

# --- [기능 2] 체크리스트 ---
def page_checklist():
    st.header("✅ 업무 체크리스트")
    today = datetime.now().strftime("%Y-%m-%d")
    items_df = load("checklist_def")
    log_df = load("checklist_log")
    today_log = log_df[log_df["date"] == today]
    
    tab1, tab2 = st.tabs(["☀️ 오픈", "🌙 마감"])
    
    def render_check(check_type):
        target_items = items_df[items_df["type"] == check_type]["item"].tolist()
        done_count = len(today_log[(today_log["type"] == check_type) & (today_log["item"].isin(target_items))])
        if len(target_items) > 0:
            st.progress(done_count / len(target_items), text=f"진행률: {done_count}/{len(target_items)}")
        
        for item in target_items:
            is_done = not today_log[(today_log["type"] == check_type) & (today_log["item"] == item)].empty
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{item}**")
            if is_done:
                rec = today_log[(today_log["type"] == check_type) & (today_log["item"] == item)].iloc[0]
                c2.success(f"{rec['user']}")
            else:
                if c2.button("완료", key=f"{check_type}_{item}"):
                    new_row = pd.DataFrame([{
                        "date": today, "type": check_type, "item": item, 
                        "user": st.session_state["name"], "time": datetime.now().strftime("%H:%M")
                    }])
                    save("checklist_log", pd.concat([log_df, new_row], ignore_index=True))
                    st.rerun()
    with tab1: render_check("오픈")
    with tab2: render_check("마감")

# --- [기능 3] 스케줄 ---
def page_schedule():
    st.header("📅 월간 근무표")
    if "selected_date" not in st.session_state: st.session_state.selected_date = datetime.now().strftime("%Y-%m-%d")
    if "edit_sch_id" not in st.session_state: st.session_state.edit_sch_id = None

    sched_df = load("schedule")
    if "id" not in sched_df.columns:
        sched_df["id"] = range(1, len(sched_df) + 1)
        save("schedule", sched_df)

    events = []
    if not sched_df.empty:
        for idx, row in sched_df.iterrows():
            color = row['role'] if str(row['role']).startswith("#") else "#3788d8"
            events.append({
                "title": f"{row['start_time']} {row['user']}",
                "start": f"{row['date']}", "end": f"{row['date']}",
                "backgroundColor": color, "borderColor": color, "allDay": True
            })

    cal_output = calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "selectable": True, "dateClick": True}, callbacks=['dateClick'], key="sch_calendar")
    
    if cal_output.get("dateClick"):
        clicked_date = cal_output["dateClick"]["date"]
        if st.session_state.selected_date != clicked_date:
            st.session_state.selected_date = clicked_date
            st.rerun()

    st.divider()
    sel_date = st.session_state.selected_date
    st.subheader(f"📌 {sel_date} 근무 관리")

    if is_admin():
        with st.expander(f"➕ {sel_date} 근무자 추가", expanded=True):
            with st.form("add_sch_form"):
                users = load("users")
                c_date = st.date_input("날짜", datetime.strptime(sel_date, "%Y-%m-%d"), key=f"sch_date_input_{sel_date}")
                s_user = st.selectbox("직원", users["name"].unique())
                times = [f"{h:02d}:00" for h in range(6, 24)]
                c1, c2 = st.columns(2)
                s_start = c1.selectbox("출근", times, index=3)
                s_end = c2.selectbox("퇴근", times, index=12)
                s_color = st.color_picker("색상", "#3788d8")
                
                if st.form_submit_button("추가", use_container_width=True):
                    new_id = 1 if sched_df.empty else sched_df["id"].max() + 1
                    new_row = pd.DataFrame([{
                        "id": new_id, "date": str(c_date), "user": s_user, 
                        "start_time": s_start, "end_time": s_end, "role": s_color
                    }])
                    save("schedule", pd.concat([sched_df, new_row], ignore_index=True))
                    st.success("추가되었습니다.")
                    st.rerun()

    daily_sched = sched_df[sched_df["date"] == sel_date].sort_values(by="start_time")
    if not daily_sched.empty:
        for idx, row in daily_sched.iterrows():
            if st.session_state.edit_sch_id == row['id']:
                with st.container(border=True):
                    with st.form(f"edit_sch_{row['id']}"):
                        times = [f"{h:02d}:00" for h in range(6, 24)]
                        try: s_idx = times.index(row['start_time'])
                        except: s_idx = 3
                        try: e_idx = times.index(row['end_time'])
                        except: e_idx = 12
                        
                        ec1, ec2 = st.columns(2)
                        n_start = ec1.selectbox("출근", times, index=s_idx)
                        n_end = ec2.selectbox("퇴근", times, index=e_idx)
                        n_color = st.color_picker("색상", row['role'] if str(row['role']).startswith("#") else "#3788d8")
                        
                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("저장"):
                            sched_df.loc[sched_df["id"] == row['id'], "start_time"] = n_start
                            sched_df.loc[sched_df["id"] == row['id'], "end_time"] = n_end
                            sched_df.loc[sched_df["id"] == row['id'], "role"] = n_color
                            save("schedule", sched_df)
                            st.session_state.edit_sch_id = None
                            st.rerun()
                        if b2.form_submit_button("취소"):
                            st.session_state.edit_sch_id = None
                            st.rerun()
            else:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([0.5, 4, 2])
                    color = row['role'] if str(row['role']).startswith("#") else "#3788d8"
                    c1.markdown(f"<div style='width:20px;height:20px;background-color:{color};border-radius:50%;margin-top:10px;'></div>", unsafe_allow_html=True)
                    c2.markdown(f"**{row['user']}** ({row['start_time']} ~ {row['end_time']})")
                    if is_admin():
                        with c3:
                            b1, b2 = st.columns(2)
                            if b1.button("수정", key=f"es_{row['id']}"):
                                st.session_state.edit_sch_id = row['id']
                                st.rerun()
                            if b2.button("삭제", key=f"ds_{row['id']}"):
                                sched_df = sched_df[sched_df["id"] != row['id']]
                                save("schedule", sched_df)
                                st.rerun()
    else:
        st.info("이 날짜에는 등록된 근무가 없습니다.")

# --- [기능 4] 예약 현황 ---
def page_reservation():
    st.header("📅 예약 현황")
    if "res_selected_date" not in st.session_state: st.session_state.res_selected_date = datetime.now().strftime("%Y-%m-%d")
    if "edit_res_id" not in st.session_state: st.session_state.edit_res_id = None

    res_df = load("reservations")
    res_logs = load("reservation_logs")
    res_menu = load("reservation_menu")
    menu_list = res_menu["item_name"].tolist()

    if "id" not in res_df.columns:
        res_df["id"] = range(1, len(res_df) + 1)
        save("reservations", res_df)

    events = []
    if not res_df.empty:
        for idx, row in res_df.iterrows():
            title = f"{row['time']} {row['customer_name']} ({row['item']})"
            events.append({
                "title": title, "start": f"{row['date']}", "end": f"{row['date']}",
                "backgroundColor": "#FF6C6C", "borderColor": "#FF6C6C", "allDay": True
            })

    cal_output = calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "selectable": True, "dateClick": True}, callbacks=['dateClick'], key="res_calendar")
    
    if cal_output.get("dateClick"):
        clicked_date = cal_output["dateClick"]["date"]
        if st.session_state.res_selected_date != clicked_date:
            st.session_state.res_selected_date = clicked_date
            st.rerun()

    st.divider()
    sel_date = st.session_state.res_selected_date
    st.subheader(f"🍰 {sel_date} 예약 리스트")

    with st.expander(f"➕ {sel_date} 예약 등록하기", expanded=True):
        with st.form("add_res_form"):
            if not menu_list:
                st.error("등록된 메뉴가 없습니다. 관리자에게 메뉴 등록을 요청하세요.")
                submit = st.form_submit_button("등록 불가")
            else:
                c_date = st.date_input("예약 날짜", datetime.strptime(sel_date, "%Y-%m-%d"), key=f"res_date_input_{sel_date}")

                c1, c2 = st.columns(2)
                r_item = c1.selectbox("메뉴 선택", menu_list)
                r_count = c2.number_input("개수", min_value=1, value=1)
                
                c3, c4 = st.columns(2)
                r_time = c3.time_input("픽업 시간", datetime.strptime("12:00", "%H:%M"))
                r_name = c4.text_input("고객 이름")
                r_phone = st.text_input("전화번호")

                if st.form_submit_button("예약 등록", use_container_width=True):
                    new_id = 1 if res_df.empty else res_df["id"].max() + 1
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    new_row = pd.DataFrame([{
                        "id": new_id, "date": str(c_date), "time": str(r_time)[:5], 
                        "item": r_item, "count": r_count, 
                        "customer_name": r_name, "customer_phone": r_phone,
                        "created_by": st.session_state["name"], "created_at": now_str
                    }])
                    save("reservations", pd.concat([res_df, new_row], ignore_index=True))
                    
                    log_row = pd.DataFrame([{
                        "res_id": new_id, "modifier": st.session_state["name"], 
                        "modified_at": now_str, "details": "최초 등록"
                    }])
                    save("reservation_logs", pd.concat([res_logs, log_row], ignore_index=True))
                    st.success("예약이 등록되었습니다.")
                    st.rerun()

    daily_res = res_df[res_df["date"] == sel_date].sort_values(by="time")
    if not daily_res.empty:
        for idx, row in daily_res.iterrows():
            with st.container(border=True):
                if st.session_state.edit_res_id == row['id']:
                    st.info("✏️ 예약 정보 수정 중")
                    with st.form(f"edit_res_{row['id']}"):
                        u_item = st.selectbox("메뉴", menu_list, index=menu_list.index(row['item']) if row['item'] in menu_list else 0)
                        u_count = st.number_input("개수", value=int(row['count']))
                        u_time_val = datetime.strptime(row['time'], "%H:%M").time()
                        u_time = st.time_input("시간", value=u_time_val)
                        u_name = st.text_input("고객명", value=row['customer_name'])
                        u_phone = st.text_input("전화번호", value=row['customer_phone'])
                        
                        b1, b2 = st.columns(2)
                        if b1.form_submit_button("수정 저장"):
                            res_df.loc[res_df["id"] == row['id'], "item"] = u_item
                            res_df.loc[res_df["id"] == row['id'], "count"] = u_count
                            res_df.loc[res_df["id"] == row['id'], "time"] = str(u_time)[:5]
                            res_df.loc[res_df["id"] == row['id'], "customer_name"] = u_name
                            res_df.loc[res_df["id"] == row['id'], "customer_phone"] = u_phone
                            save("reservations", res_df)
                            
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                            log_msg = f"수정됨 (메뉴:{u_item}, 시간:{str(u_time)[:5]}, 이름:{u_name})"
                            new_log = pd.DataFrame([{
                                "res_id": row['id'], "modifier": st.session_state["name"], 
                                "modified_at": now_str, "details": log_msg
                            }])
                            save("reservation_logs", pd.concat([res_logs, new_log], ignore_index=True))
                            st.session_state.edit_res_id = None
                            st.rerun()
                        if b2.form_submit_button("취소"):
                            st.session_state.edit_res_id = None
                            st.rerun()
                else:
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.subheader(f"[{row['time']}] {row['customer_name']} 님")
                        st.write(f"🛍️ **{row['item']}** ({row['count']}개) | 📞 {row['customer_phone']}")
                        st.caption(f"최초 입력: {row['created_by']} ({row['created_at']})")
                        my_logs = res_logs[res_logs["res_id"] == row['id']].sort_values(by="modified_at", ascending=False)
                        with st.expander("🕒 수정 이력 보기"):
                            if not my_logs.empty:
                                for l_idx, log in my_logs.iterrows():
                                    st.text(f"- {log['modified_at']} {log['modifier']}: {log['details']}")
                            else:
                                st.text("수정 이력이 없습니다.")
                    with c2:
                        if st.button("수정", key=f"re_ed_{row['id']}"):
                            st.session_state.edit_res_id = row['id']
                            st.rerun()
                        if st.button("삭제", key=f"re_del_{row['id']}"):
                            res_df = res_df[res_df["id"] != row['id']]
                            save("reservations", res_df)
                            st.rerun()
    else:
        st.info("금일 예약 내역이 없습니다.")

# --- [기능 5] 관리자 설정 ---
def page_admin():
    st.header("⚙️ 관리자 설정")
    tab1, tab2, tab3 = st.tabs(["👥 직원 권한", "✅ 체크리스트", "🛍️ 예약 메뉴"])
    with tab1:
        users = load("users")
        edited_users = st.data_editor(users, column_config={"role": st.column_config.SelectboxColumn("권한", options=["Staff", "Manager"], required=True)}, hide_index=True, use_container_width=True)
        if st.button("직원 권한 저장", use_container_width=True):
            save("users", edited_users)
            st.success("저장 완료")
    with tab2:
        checklist_def = load("checklist_def")
        edited_list = st.data_editor(checklist_def, num_rows="dynamic", use_container_width=True)
        if st.button("체크리스트 저장", use_container_width=True):
            save("checklist_def", edited_list)
            st.success("저장 완료")
    with tab3:
        st.caption("예약 현황에서 선택할 수 있는 메뉴 리스트를 관리합니다.")
        res_menu = load("reservation_menu")
        edited_menu = st.data_editor(res_menu, num_rows="dynamic", use_container_width=True, column_config={"item_name": "메뉴 이름"})
        if st.button("예약 메뉴 저장", use_container_width=True):
            save("reservation_menu", edited_menu)
            st.success("메뉴 목록이 업데이트되었습니다.")

# --- 메인 앱 ---
def main_app():
    # 사이드바 디자인 적용
    with st.sidebar:
        # 사이드바에 로고 작게 표시 (약 100px)
        if os.path.exists("logo.png"):
            st.image("logo.png", width=100)
            
        st.header(f"{st.session_state['name']}님")
        st.caption(f"직책: {st.session_state['role']}")
        st.divider()
        
        menu_options = ["📢 공지사항", "📅 스케줄", "📅 예약 현황", "✅ 체크리스트", "🥐 레시피", "📘 회사 매뉴얼"]
        if is_admin(): 
            menu_options.append("⚙️ 관리자 설정")
            
        menu = st.radio("메뉴 이동", menu_options)
        
        st.divider()
        if st.button("로그아웃"):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "📢 공지사항": page_board("공지사항", "📢")
    elif menu == "📅 스케줄": page_schedule()
    elif menu == "📅 예약 현황": page_reservation()
    elif menu == "✅ 체크리스트": page_checklist()
    elif menu == "🥐 레시피": page_recipe()
    elif menu == "📘 회사 매뉴얼": page_board("회사 매뉴얼", "📘")
    elif menu == "⚙️ 관리자 설정": page_admin()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login_page()
else: main_app()
