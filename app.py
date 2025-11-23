import streamlit as st
import pandas as pd
import os
import math
from datetime import datetime
from streamlit_calendar import calendar
from streamlit_option_menu import option_menu # 네비게이션 메뉴 라이브러리

# --- [0. 기본 설정] 앱 이름 및 아이콘 ---
st.set_page_config(
    page_title="조각달과자점", 
    page_icon="🥐", 
    layout="wide", 
    initial_sidebar_state="collapsed" # 모바일 친화적: 시작할 때 사이드바 숨김
)

# --- [1. 디자인: 모바일 최적화 & 따뜻한 테마 CSS] ---
st.markdown("""
    <style>
    /* 폰트 설정 (Noto Sans KR) */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Noto Sans KR', sans-serif;
        color: #4E342E;
    }

    /* 전체 배경색 */
    .stApp {
        background-color: #FFF3E0;
    }

    /* [모바일 최적화 핵심] 화면이 좁을 때 여백을 줄여서 넓게 쓰기 */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 2rem !important; /* 상단 버튼 가리지 않게 여백 확보 */
            max-width: 100% !important;
        }
        /* 모바일에서 폰트 크기 조절 */
        h1 { font-size: 1.8rem !important; }
        h2 { font-size: 1.5rem !important; }
        h3 { font-size: 1.2rem !important; }
    }

    /* 버튼 디자인 (모바일 터치하기 좋게) */
    .stButton>button {
        background-color: #8D6E63;
        color: white;
        border-radius: 15px;
        border: none;
        padding: 0.6rem 1rem; /* 터치 영역 확보 */
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s;
        width: 100%; /* 버튼을 항상 가로로 꽉 차게 */
    }
    .stButton>button:hover {
        background-color: #6D4C41;
        color: #FFF8E1;
        transform: translateY(-1px);
    }

    /* 입력창 스타일 */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stDateInput>div>div>input, .stTimeInput>div>div>input {
        border-radius: 10px;
        border: 1px solid #BCAAA4;
        background-color: #FFFFFF;
        height: 45px; /* 터치하기 좋게 높이 키움 */
    }

    /* 컨테이너 (카드) 스타일 */
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        background-color: #FFFFFF;
        padding: 15px; /* 모바일 고려 패딩 축소 */
        border-radius: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #EFEBE9;
        margin-bottom: 10px;
    }

    /* 상단 헤더 스타일 (메뉴 버튼 보이게 수정됨) */
    header[data-testid="stHeader"] {
        background-color: transparent;
    }
    /* 햄버거 메뉴 버튼 색상 조정 (배경과 어울리게) */
    .css-14xtw13 {
        color: #4E342E;
    }
    
    /* 불필요한 Streamlit 요소 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* 탭 디자인 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #F5E6D3;
        border-radius: 10px 10px 0 0;
        color: #5D4037;
        flex: 1; /* 탭이 화면 너비를 꽉 채우도록 */
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #FFFFFF;
        font-weight: bold;
        color: #3E2723;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 데이터 파일 정의] ---
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

# --- [3. 유틸리티 함수] ---
def is_admin():
    return st.session_state.get("role") in ["Manager", "관리자"]

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

def load(key): 
    df = pd.read_csv(FILES[key])
    if key == "posts" and "sub_category" not in df.columns:
        df["sub_category"] = "기타"
        save("posts", df)
    return df

def save(key, df): df.to_csv(FILES[key], index=False)

init_db()

# --- [5. 페이지별 기능 함수] ---

def login_page():
    # 배경을 흰색으로 설정하고, 이미지를 강제로 중앙 정렬하는 CSS 추가
    st.markdown("""
        <style>
        .stApp {background-color: #FFFFFF;}
        /* 이미지(로고) 중앙 정렬을 위한 CSS */
        div[data-testid="stImage"] {
            display: block;
            margin-left: auto;
            margin-right: auto;
            text-align: center;
        }
        div[data-testid="stImage"] > img {
            margin: 0 auto;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # 모바일에서 가운데 정렬을 확실하게 하기 위해 컬럼 대신 컨테이너 사용
    with st.container():
        st.write("") # 상단 여백
        
        # [로고 이미지] - CSS로 자동 중앙 정렬됨
        if os.path.exists("logo.png"):
            st.image("logo.png", width=120)
        else:
            st.markdown("<h1 style='text-align: center;'>🥐</h1>", unsafe_allow_html=True)
            
        st.markdown("<h2 style='text-align: center; color: #4E342E; margin-top: 10px;'>조각달과자점</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #8D6E63;'>따뜻한 마음을 굽는 업무 공간</p>", unsafe_allow_html=True)
        st.write("")

        # 로그인 폼도 중앙에 좁게 배치하기 위해 컬럼 사용
        lc1, lc2, lc3 = st.columns([1, 8, 1]) # 모바일에서는 꽉 차게, PC에서는 적당하게
        with lc2:
            tab1, tab2 = st.tabs(["로그인", "회원가입"])
            with tab1:
                with st.form("login_form"):
                    user_id = st.text_input("아이디")
                    user_pw = st.text_input("비밀번호", type="password")
                    submit = st.form_submit_button("입장하기")
                    if submit:
                        users = load("users")
                        user = users[(users["username"] == user_id) & (users["password"] == user_pw)]
                        if not user.empty:
                            st.session_state.update({"logged_in": True, "username": user_id, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                            st.rerun()
                        else:
                            st.error("정보를 확인해주세요.")
            with tab2:
                with st.form("signup_form"):
                    new_id = st.text_input("희망 아이디")
                    new_pw = st.text_input("희망 비밀번호", type="password")
                    new_name = st.text_input("이름 (실명)")
                    submit = st.form_submit_button("가입 신청")
                    if submit:
                        users = load("users")
                        if new_id in users["username"].values:
                            st.warning("이미 존재하는 아이디입니다.")
                        else:
                            new_row = pd.DataFrame([{"username": new_id, "password": new_pw, "name": new_name, "role": "Staff"}])
                            save("users", pd.concat([users, new_row], ignore_index=True))
                            st.success("가입되었습니다! 로그인해주세요.")

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
    page_key = f"page_{category_name}"
    if page_key not in st.session_state: st.session_state[page_key] = 1
    current_page = st.session_state[page_key]
    start_idx = (current_page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_df = df.iloc[start_idx:end_idx]
    
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
                            df_all.loc[df_all["id"] == row['id'], "title"] = e_title
                            df_all.loc[df_all["id"] == row['id'], "content"] = e_content
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
                            df_all = df_all[df_all["id"] != row['id']]
                            save("posts", df_all)
                            st.rerun()
        if total_pages > 1:
            st.divider()
            cols = st.columns(total_pages + 2)
            for i in range(1, total_pages + 1):
                if cols[i].button(str(i), key=f"pg_{category_name}_{i}", disabled=(i==current_page)):
                    st.session_state[page_key] = i
                    st.rerun()
    else:
        st.info("등록된 글이 없습니다.")

def page_recipe():
    st.header("🥐 레시피")
    RECIPE_CATS = ["빵", "케이크", "구움과자", "음료", "기타"]
    if "edit_post_id" not in st.session_state: st.session_state.edit_post_id = None
    
    if is_admin():
        with st.expander("➕ 레시피 등록"):
            with st.form("write_recipe"):
                r_cat = st.selectbox("종류", RECIPE_CATS)
                r_title = st.text_input("제품명")
                r_content = st.text_area("레시피 내용")
                if st.form_submit_button("저장"):
                    df = load("posts")
                    new_id = 1 if df.empty else df["id"].max() + 1
                    new_row = pd.DataFrame([{
                        "id": new_id, "category": "레시피", "sub_category": r_cat,
                        "title": r_title, "content": r_content, "author": st.session_state["name"],
                        "date": datetime.now().strftime("%Y-%m-%d")
                    }])
                    save("posts", pd.concat([df, new_row], ignore_index=True))
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
                                c1, c2 = st.columns([1, 9])
                                if c1.button("수정", key=f"er_{row['id']}"):
                                    st.session_state.edit_post_id = row['id']
                                    st.rerun()
                                if c2.button("삭제", key=f"dr_{row['id']}"):
                                    df_all = load("posts")
                                    df_all = df_all[df_all["id"] != row['id']]
                                    save("posts", df_all)
                                    st.rerun()
            else:
                st.caption("등록된 레시피가 없습니다.")

def page_checklist():
    st.header("✅ 체크리스트")
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

def page_schedule():
    st.header("📅 근무표")
    if "selected_date" not in st.session_state: st.session_state.selected_date = datetime.now().strftime("%Y-%m-%d")
    if "edit_sch_id" not in st.session_state: st.session_state.edit_sch_id = None

    sched_df = load("schedule")
    if "id" not in sched_df.columns:
        sched_df["id"] = range(1, len(sched_df) + 1)
        save("schedule", sched_df)

    events = []
    if not sched_df.empty:
        for idx, row in sched_df.iterrows():
            color = row['role'] if str(row['role']).startswith("#") else "#8D6E63"
            events.append({
                "title": f"{row['start_time']} {row['user']}",
                "start": f"{row['date']}", "end": f"{row['date']}",
                "backgroundColor": color, "borderColor": color, "allDay": True
            })

    cal_output = calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "selectable": True, "dateClick": True}, callbacks=['dateClick'], key="sch_cal")
    
    if cal_output.get("dateClick"):
        clicked = cal_output["dateClick"]["date"]
        if st.session_state.selected_date != clicked:
            st.session_state.selected_date = clicked
            st.rerun()

    st.divider()
    sel_date = st.session_state.selected_date
    st.subheader(f"📌 {sel_date} 근무")

    if is_admin():
        with st.expander(f"➕ {sel_date} 근무 추가", expanded=True):
            with st.form("add_sch"):
                users = load("users")
                c_date = st.date_input("날짜", datetime.strptime(sel_date, "%Y-%m-%d"), key=f"sch_dt_{sel_date}")
                s_user = st.selectbox("직원", users["name"].unique())
                times = [f"{h:02d}:00" for h in range(6, 24)]
                c1, c2 = st.columns(2)
                s_start = c1.selectbox("출근", times, index=3)
                s_end = c2.selectbox("퇴근", times, index=12)
                s_color = st.color_picker("색상", "#8D6E63")
                
                if st.form_submit_button("추가"):
                    new_id = 1 if sched_df.empty else sched_df["id"].max() + 1
                    new_row = pd.DataFrame([{
                        "id": new_id, "date": str(c_date), "user": s_user, 
                        "start_time": s_start, "end_time": s_end, "role": s_color
                    }])
                    save("schedule", pd.concat([sched_df, new_row], ignore_index=True))
                    st.rerun()

    daily = sched_df[sched_df["date"] == sel_date].sort_values(by="start_time")
    if not daily.empty:
        for idx, row in daily.iterrows():
            if st.session_state.edit_sch_id == row['id']:
                with st.container(border=True):
                    with st.form(f"edit_sch_{row['id']}"):
                        times = [f"{h:02d}:00" for h in range(6, 24)]
                        try: s_idx = times.index(row['start_time'])
                        except: s_idx = 3
                        try: e_idx = times.index(row['end_time'])
                        except: e_idx = 12
                        
                        c1, c2 = st.columns(2)
                        n_start = c1.selectbox("출근", times, index=s_idx)
                        n_end = c2.selectbox("퇴근", times, index=e_idx)
                        n_color = st.color_picker("색상", row['role'])
                        
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
                    color = row['role'] if str(row['role']).startswith("#") else "#8D6E63"
                    c1.markdown(f"<div style='width:20px;height:20px;background-color:{color};border-radius:50%;margin-top:10px;'></div>", unsafe_allow_html=True)
                    c2.markdown(f"**{row['user']}** ({row['start_time']}~{row['end_time']})")
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
        st.info("근무 내역이 없습니다.")

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
            events.append({
                "title": f"{row['time']} {row['customer_name']} ({row['item']})",
                "start": f"{row['date']}", "end": f"{row['date']}",
                "backgroundColor": "#D7CCC8", "borderColor": "#8D6E63", "allDay": True, "textColor": "#3E2723"
            })

    cal_output = calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "selectable": True, "dateClick": True}, callbacks=['dateClick'], key="res_cal")
    
    if cal_output.get("dateClick"):
        clicked = cal_output["dateClick"]["date"]
        if st.session_state.res_selected_date != clicked:
            st.session_state.res_selected_date = clicked
            st.rerun()

    st.divider()
    sel_date = st.session_state.res_selected_date
    st.subheader(f"🍰 {sel_date} 예약")

    with st.expander(f"➕ {sel_date} 예약 등록", expanded=True):
        with st.form("add_res"):
            if not menu_list:
                st.error("등록된 메뉴가 없습니다.")
                st.form_submit_button("불가")
            else:
                c_date = st.date_input("날짜", datetime.strptime(sel_date, "%Y-%m-%d"), key=f"res_dt_{sel_date}")
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
                    new_row = pd.DataFrame([{
                        "id": new_id, "date": str(c_date), "time": str(r_time)[:5], 
                        "item": r_item, "count": r_count, "customer_name": r_name, "customer_phone": r_phone,
                        "created_by": st.session_state["name"], "created_at": now_str
                    }])
                    save("reservations", pd.concat([res_df, new_row], ignore_index=True))
                    
                    log_row = pd.DataFrame([{
                        "res_id": new_id, "modifier": st.session_state["name"], 
                        "modified_at": now_str, "details": "최초 등록"
                    }])
                    save("reservation_logs", pd.concat([res_logs, log_row], ignore_index=True))
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
                            res_df.loc[res_df["id"] == row['id'], "item"] = u_item
                            res_df.loc[res_df["id"] == row['id'], "count"] = u_count
                            res_df.loc[res_df["id"] == row['id'], "time"] = str(u_time)[:5]
                            res_df.loc[res_df["id"] == row['id'], "customer_name"] = u_name
                            res_df.loc[res_df["id"] == row['id'], "customer_phone"] = u_phone
                            save("reservations", res_df)
                            
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                            log_msg = f"수정 (메뉴:{u_item}, 시간:{str(u_time)[:5]})"
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
                        st.markdown(f"**[{row['time']}] {row['customer_name']}**")
                        st.write(f"{row['item']} ({row['count']}개) | 📞 {row['customer_phone']}")
                        with st.expander("수정 이력"):
                            logs = res_logs[res_logs["res_id"] == row['id']].sort_values(by="modified_at", ascending=False)
                            for _, l in logs.iterrows():
                                st.text(f"{l['modified_at']} {l['modifier']}: {l['details']}")
                    with c2:
                        if st.button("수정", key=f"re_ed_{row['id']}"):
                            st.session_state.edit_res_id = row['id']
                            st.rerun()
                        if st.button("삭제", key=f"re_del_{row['id']}"):
                            res_df = res_df[res_df["id"] != row['id']]
                            save("reservations", res_df)
                            st.rerun()
    else:
        st.info("예약 내역이 없습니다.")

def page_admin():
    st.header("⚙️ 관리자 설정")
    
    if "admin_unlocked" not in st.session_state:
        st.session_state.admin_unlocked = False

    if not st.session_state.admin_unlocked:
        st.warning("🔒 관리자 메뉴는 비밀번호가 필요합니다.")
        with st.form("admin_pw"):
            pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("확인"):
                if pw == "army1214":
                    st.session_state.admin_unlocked = True
                    st.rerun()
                else:
                    st.error("비밀번호 불일치")
        return

    if st.button("🔒 잠그기"):
        st.session_state.admin_unlocked = False
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["직원 권한", "체크리스트", "예약 메뉴"])
    with tab1:
        users = load("users")
        edited = st.data_editor(users, column_config={"role": st.column_config.SelectboxColumn("권한", options=["Staff", "Manager"], required=True)}, hide_index=True, use_container_width=True)
        if st.button("권한 저장"):
            save("users", edited)
            st.success("저장됨")
    with tab2:
        checklist = load("checklist_def")
        edited_list = st.data_editor(checklist, num_rows="dynamic", use_container_width=True)
        if st.button("체크리스트 저장"):
            save("checklist_def", edited_list)
            st.success("저장됨")
    with tab3:
        res_menu = load("reservation_menu")
        edited_menu = st.data_editor(res_menu, num_rows="dynamic", use_container_width=True)
        if st.button("메뉴 저장"):
            save("reservation_menu", edited_menu)
            st.success("저장됨")

# --- [6. 메인 앱 실행] ---
def main_app():
    with st.sidebar:
        # 로고 이미지 삭제 요청 반영
        st.write(f"안녕하세요, **{st.session_state['name']}**님!")
        st.caption(f"직책: {st.session_state['role']}")
        
        menu = option_menu(
            menu_title=None,
            options=["공지사항", "스케줄", "예약 현황", "체크리스트", "레시피", "매뉴얼", "관리자"],
            icons=['megaphone', 'calendar-week', 'calendar-check', 'check2-square', 'book', 'journal-text', 'gear'],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#F5E6D3"},
                "icon": {"color": "#5D4037", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#D7CCC8", "color": "#4E342E"},
                "nav-link-selected": {"background-color": "#8D6E63", "color": "white"},
            }
        )
        
        if st.button("로그아웃", use_container_width=True):
            st.session_state["logged_in"] = False
            st.session_state["admin_unlocked"] = False 
            st.rerun()

    if menu == "공지사항": page_board("공지사항", "📢")
    elif menu == "스케줄": page_schedule()
    elif menu == "예약 현황": page_reservation()
    elif menu == "체크리스트": page_checklist()
    elif menu == "레시피": page_recipe()
    elif menu == "매뉴얼": page_board("회사 매뉴얼", "📘")
    elif menu == "관리자": page_admin()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login_page()
else: main_app()
