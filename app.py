import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
from datetime import datetime, date
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection
from streamlit_cookies_manager import CookieManager
from PIL import Image

# --- [이미지 처리 함수] ---
def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

@st.cache_data
def get_processed_logo(image_path, icon_size=(40, 40)):
    try:
        img = Image.open(image_path).convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        img = img.resize(icon_size, Image.LANCZOS)
        return img
    except Exception:
        return None

# --- [0. 기본 설정] ---
st.set_page_config(
    page_title="조각달과자점 파트너", 
    page_icon="logo.png", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

processed_icon = get_processed_logo("logo.png", icon_size=(192, 192))
if processed_icon:
    icon_base64 = image_to_base64(processed_icon)
    st.markdown(
        f"""
        <head>
            <link rel="apple-touch-icon" sizes="180x180" href="data:image/png;base64,{icon_base64}">
            <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,{icon_base64}">
            <link rel="icon" type="image/png" sizes="192x192" href="data:image/png;base64,{icon_base64}">
        </head>
        """,
        unsafe_allow_html=True
    )

# --- [1. CSS 스타일] ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; }
    .stApp { background-color: #FFF3E0; }
    
    section[data-testid="stSidebar"] {
        background-color: #FFF3E0;
        border-right: 1px solid #ddd;
    }
    
    header { background-color: transparent !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        visibility: visible !important;
        color: #4E342E !important;
        background-color: rgba(255, 255, 255, 0.5) !important;
        border-radius: 8px;
        padding: 5px;
        z-index: 1000002 !important;
        top: 10px !important;
        left: 10px !important;
    }
    
    .block-container { padding-top: 50px !important; }
    
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }
    
    .comment-box { background-color: #F5F5F5; padding: 10px; border-radius: 8px; margin-top: 5px; font-size: 0.9rem; }
    
    .streamlit-expanderHeader {
        background-color: #FFEBEE !important;
        color: #C62828 !important;
        border: 1px solid #FFCDD2;
        border-radius: 10px;
        font-weight: bold;
    }
    
    .logo-title-container {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 20px;
    }
    .logo-title-container h1 {
        margin: 0 0 0 10px;
        font-size: 2.5rem;
    }
    
    .sidebar-logo-container {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [쿠키 매니저] ---
cookies = CookieManager()

# --- [2. 구글 시트 연결] ---
conn = st.connection("gsheets", type=GSheetsConnection)

SHEET_NAMES = {
    "users": "users",
    "posts": "posts",
    "comments": "comments",
    "routine_def": "routine_def",
    "routine_log": "routine_log"
}

@st.cache_data(ttl=60)
def load_data(key):
    try:
        return conn.read(worksheet=SHEET_NAMES[key], ttl=0)
    except Exception:
        return pd.DataFrame()

def load(key): return load_data(key)

def save(key, df):
    try:
        conn.update(worksheet=SHEET_NAMES[key], data=df)
        load_data.clear()
    except Exception as e:
        if "429" in str(e): st.error("⚠️ 구글 연결량 초과. 1분 뒤 시도해주세요.")
        else: st.error(f"저장 실패: {e}")

def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def init_db():
    try:
        users = load("users")
        if users.empty or "username" not in users.columns:
            admin_pw = hash_password("1234")
            init_users = pd.DataFrame([{
                "username": "admin", 
                "password": admin_pw, 
                "name": "사장님", 
                "role": "Master",
                "approved": "True" 
            }])
            save("users", init_users)
        load("posts")
        load("routine_def")
    except: pass

init_db()

# --- [3. 로직 함수] ---
def is_task_due(start_date_str, cycle_type, interval_val):
    try:
        if pd.isna(start_date_str) or str(start_date_str).strip() == "": return False
        try: start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
        except: return False
        
        today = date.today()
        if today < start_date: return False
        delta_days = (today - start_date).days
        
        if cycle_type == "매일": return True
        elif cycle_type == "매주": return delta_days % 7 == 0
        elif cycle_type == "매월": return today.day == start_date.day
        elif cycle_type == "N일 간격": return delta_days % int(interval_val) == 0
        return False
    except: return False

def get_pending_tasks_list():
    defs = load("routine_def")
    logs = load("routine_log")
    if defs.empty: return []

    today_str = date.today().strftime("%Y-%m-%d")
    pending = []
    
    for _, task in defs.iterrows():
        if is_task_due(task.get("start_date"), task.get("cycle_type"), task.get("interval_val", 1)):
            is_done = False
            if not logs.empty:
                done = logs[(logs["task_id"].astype(str) == str(task["id"])) & (logs["done_date"] == today_str)]
                if not done.empty: is_done = True
            if not is_done: pending.append(task)
    return pending

# [핵심 수정] 천하무적 승인 체크 함수
def check_approved(val):
    # 값을 문자로 바꾸고, 공백 제거하고, 소문자로 바꿈
    v = str(val).strip().lower()
    # True, true, 1, 1.0, yes 등 긍정의 의미면 모두 통과!
    return v in ["true", "1", "1.0", "yes", "y", "t"]

# --- [4. 화면 구성] ---

def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    processed_logo = get_processed_logo("logo.png", icon_size=(80, 80))
    if processed_logo:
        st.markdown("""
            <div class="logo-title-container">
                <img src="data:image/png;base64,{}" style="max-height: 80px; width: auto;">
                <h1>업무수첩</h1>
            </div>
        """.format(image_to_base64(processed_logo)), unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align:center;'>업무수첩</h1>", unsafe_allow_html=True)

    try:
        if cookies.get("auto_login") == "true":
            sid, spw = cookies.get("uid"), cookies.get("upw")
            if sid and spw:
                users = load("users")
                if not users.empty:
                    users["username"] = users["username"].astype(str)
                    users["password"] = users["password"].astype(str)
                    u = users[(users["username"] == sid) & (users["password"] == spw)]
                    if not u.empty:
                        if check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"], "show_login_alert": True})
                            st.rerun()
    except: pass

    tab1, tab2 = st.tabs(["로그인", "회원가입 요청"])
    
    with tab1:
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            auto = st.checkbox("자동 로그인")
            if st.form_submit_button("입장"):
                users = load("users")
                hpw = hash_password(upw)
                if not users.empty:
                    users["username"] = users["username"].astype(str)
                    users["password"] = users["password"].astype(str)
                    u = users[(users["username"] == uid) & (users["password"] == hpw)]
                    if not u.empty:
                        # 디버깅용: 실제 값을 못 읽어오면 화면에 표시 (오류 해결 후엔 주석 처리 가능)
                        # st.write(f"DB값: {u.iloc[0].get('approved')}") 
                        
                        if check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"], "show_login_alert": True})
                            if auto:
                                cookies["auto_login"] = "true"
                                cookies["uid"] = uid
                                cookies["upw"] = hpw
                                cookies.save()
                            else:
                                if cookies.get("auto_login"): cookies["auto_login"] = "false"; cookies.save()
                            st.rerun()
                        else:
                            st.warning("⏳ 아직 승인 대기 중입니다. (Master 승인 필요)")
                    else: st.error("아이디 또는 비밀번호가 틀렸습니다.")
                else: st.error("DB 접속 오류")

    with tab2:
        with st.form("signup"):
            st.write("가입을 신청하면 Master 승인 후 이용 가능합니다.")
            new_id = st.text_input("희망 아이디")
            new_pw = st.text_input("희망 비밀번호", type="password")
            new_name = st.text_input("이름 (실명)")
            
            if st.form_submit_button("가입 신청"):
                users = load("users")
                if not users.empty and new_id in users["username"].values:
                    st.error("이미 존재하는 아이디입니다.")
                elif new_id and new_pw and new_name:
                    new_user = pd.DataFrame([{
                        "username": new_id, 
                        "password": hash_password(new_pw), 
                        "name": new_name, 
                        "role": "Staff", 
                        "approved": "False"
                    }])
                    if users.empty: save("users", new_user)
                    else: save("users", pd.concat([users, new_user], ignore_index=True))
                    st.success("✅ 신청 완료! 사장님 승인을 기다려주세요.")
                else:
                    st.warning("모든 항목을 입력해주세요.")

def page_staff_mgmt():
    st.header("👥 직원 관리 (Master 전용)")
    
    users = load("users")
    if users.empty:
        st.info("데이터가 없습니다.")
        return

    if "approved" not in users.columns:
        users["approved"] = "False"

    # 승인 대기 목록 (천하무적 함수 활용)
    # pandas apply로 필터링
    users["is_approved_bool"] = users["approved"].apply(check_approved)
    
    # 승인 안 된 사람들 (False인 행)
    pending_users = users[users["is_approved_bool"] == False]
    
    if not pending_users.empty:
        st.subheader("⏳ 승인 대기 요청")
        st.info(f"{len(pending_users)}명의 가입 요청이 있습니다.")
        
        for index, row in pending_users.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                c1.write(f"**{row['name']}** ({row['role']})")
                c2.write(f"ID: {row['username']}")
                
                if c3.button("수락", key=f"approve_{row['username']}"):
                    users.loc[users["username"] == row["username"], "approved"] = "True"
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users)
                    st.rerun()
                
                if c4.button("거절", key=f"reject_{row['username']}"):
                    users = users[users["username"] != row["username"]]
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users)
                    st.rerun()
        st.divider()

    st.subheader("✅ 정식 직원 목록")
    active_users = users[users["is_approved_bool"] == True]
    
    if not active_users.empty:
        for index, row in active_users.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.write(f"**{row['name']}**")
                c2.write(f"ID: {row['username']}")
                c3.write(f"Role: {row['role']}")
                
                if row['username'] != "admin" and row['username'] != st.session_state['name']: 
                    if c4.button("삭제", key=f"del_active_{row['username']}"):
                        new_df = users[users["username"] != row['username']]
                        if "is_approved_bool" in new_df.columns: del new_df["is_approved_bool"]
                        save("users", new_df)
                        st.rerun()
    else:
        st.info("등록된 직원이 없습니다.")

def page_board(b_name, icon):
    st.header(f"{icon} {b_name} 게시판")
    user_role = st.session_state['role']

    if user_role in ["Master", "Manager"]:
        with st.expander("✏️ 글 쓰기 (Master/Manager)"):
            with st.form(f"w_{b_name}"):
                tt = st.text_input("제목")
                ct = st.text_area("내용")
                if st.form_submit_button("등록"):
                    df = load("posts")
                    nid = 1
                    if not df.empty and "id" in df.columns: nid = pd.to_numeric(df["id"], errors='coerce').fillna(0).max() + 1
                    np = pd.DataFrame([{"id": nid, "board_type": b_name, "title": tt, "content": ct, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])
                    if df.empty: save("posts", np)
                    else: save("posts", pd.concat([df, np], ignore_index=True))
                    st.rerun()
    elif user_role == "Staff":
        st.info("💡 Staff는 글을 읽고 댓글로 수정 요청을 할 수 있습니다.")

    posts = load("posts")
    cmts = load("comments")
    
    if posts.empty: st.info("게시글이 없습니다.")
    else:
        if "board_type" in posts.columns:
            mp = posts[posts["board_type"].astype(str).str.strip() == b_name]
            if mp.empty: st.info("게시글이 없습니다.")
            else:
                mp = mp.sort_values("id", ascending=False)
                for _, r in mp.iterrows():
                    lbl = f"{r['title']}   (✍️ {r['author']} | 📅 {r['date']})"
                    with st.expander(lbl):
                        edit_key = f"edit_mode_{r['id']}"
                        if edit_key not in st.session_state: st.session_state[edit_key] = False

                        if st.session_state[edit_key]:
                            with st.form(f"edit_form_{r['id']}"):
                                new_title = st.text_input("제목 수정", value=r['title'])
                                new_content = st.text_area("내용 수정", value=r['content'])
                                c_save, c_cancel = st.columns(2)
                                if c_save.form_submit_button("저장"):
                                    posts.loc[posts["id"] == r["id"], "title"] = new_title
                                    posts.loc[posts["id"] == r["id"], "content"] = new_content
                                    save("posts", posts)
                                    st.session_state[edit_key] = False
                                    st.rerun()
                                if c_cancel.form_submit_button("취소"):
                                    st.session_state[edit_key] = False
                                    st.rerun()
                        else:
                            st.write(r['content'])
                            st.markdown("---")
                            
                            btn_cols = st.columns([1, 1, 6])
                            if user_role in ["Master", "Manager"]:
                                if btn_cols[0].button("수정", key=f"btn_edit_{r['id']}"):
                                    st.session_state[edit_key] = True
                                    st.rerun()
                            
                            if user_role == "Master":
                                if btn_cols[1].button("삭제", key=f"btn_del_{r['id']}"):
                                    posts = posts[posts["id"] != r["id"]]
                                    save("posts", posts)
                                    st.rerun()

                            if not cmts.empty:
                                pcmts = cmts[cmts["post_id"].astype(str) == str(r["id"])]
                                for _, c in pcmts.iterrows():
                                    st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {c['content']} <span style='color:#aaa;font-size:0.8em;'>({c['date']})</span></div>", unsafe_allow_html=True)
                            
                            with st.form(f"c_{r['id']}"):
                                c1, c2 = st.columns([4,1])
                                ctxt = c1.text_input("댓글 (수정 요청 등)", label_visibility="collapsed", placeholder="댓글을 입력하세요")
                                if c2.form_submit_button("등록"):
                                    nc = pd.DataFrame([{"post_id": r["id"], "author": st.session_state["name"], "content": ctxt, "date": datetime.now().strftime("%m-%d %H:%M")}])
                                    if cmts.empty: save("comments", nc)
                                    else: save("comments", pd.concat([cmts, nc], ignore_index=True))
                                    st.rerun()

def page_routine():
    st.header("🔄 반복 업무")
    defs = load("routine_def")
    logs = load("routine_log")
    if not defs.empty and "id" not in defs.columns: defs["id"] = range(1, len(defs)+1)
    today = date.today().strftime("%Y-%m-%d")
    user_role = st.session_state['role']
    
    t1, t2 = st.tabs(["오늘의 업무", "기록"])
    with t1:
        if user_role in ["Master", "Manager"]:
            with st.expander("⚙️ 업무 추가/삭제 (Master/Manager)"):
                with st.form("new_r"):
                    c1,c2 = st.columns(2)
                    rn = c1.text_input("업무명")
                    rs = c2.date_input("시작일")
                    c3,c4 = st.columns(2)
                    rc = c3.selectbox("주기", ["매일","매주","매월","N일 간격"])
                    ri = 1
                    if rc=="N일 간격": ri = c4.number_input("간격",1,365,3)
                    if st.form_submit_button("추가"):
                        nid = 1
                        if not defs.empty: nid = pd.to_numeric(defs["id"], errors='coerce').fillna(0).max()+1
                        nr = pd.DataFrame([{"id": nid, "task_name": rn, "start_date": rs.strftime("%Y-%m-%d"), "cycle_type": rc, "interval_val": ri}])
                        if defs.empty: save("routine_def", nr)
                        else: save("routine_def", pd.concat([defs, nr], ignore_index=True))
                        st.rerun()
                if not defs.empty:
                    for _, r in defs.iterrows():
                        c1, c2 = st.columns([4,1])
                        c1.text(f"• {r['task_name']}")
                        if c2.button("삭제", key=f"d_{r['id']}"):
                            save("routine_def", defs[defs["id"]!=r['id']])
                            st.rerun()
        
        st.divider()
        ptasks = get_pending_tasks_list()
        if not ptasks: st.info("오늘 예정된 업무가 없습니다.")
        else:
            for t in ptasks:
                with st.container():
                    st.markdown(f"<div style='padding:10px; border:1px solid #FFCDD2; background:#FFEBEE; border-radius:10px; margin-bottom:5px;'><b>{t['task_name']}</b></div>", unsafe_allow_html=True)
                    if st.button("완료", key=f"do_{t['id']}"):
                        nl = pd.DataFrame([{"task_id": t["id"], "done_date": today, "worker": st.session_state["name"], "created_at": datetime.now().strftime("%H:%M")}])
                        if logs.empty: save("routine_log", nl)
                        else: save("routine_log", pd.concat([logs, nl], ignore_index=True))
                        st.rerun()
    with t2:
        if logs.empty: st.info("기록 없음")
        else:
            if not defs.empty:
                logs["task_id"] = logs["task_id"].astype(str)
                defs["id"] = defs["id"].astype(str)
                m = pd.merge(logs, defs, left_on="task_id", right_on="id", how="left")
                m = m.sort_values(["done_date", "created_at"], ascending=False)
                st.dataframe(m[["done_date", "task_name", "worker"]], use_container_width=True, hide_index=True)

def main():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
    else:
        with st.sidebar:
            processed_logo_sidebar = get_processed_logo("logo.png", icon_size=(80, 80))
            if processed_logo_sidebar:
                st.markdown("""
                    <div class="sidebar-logo-container">
                        <img src="data:image/png;base64,{}" style="max-height: 80px; width: auto;">
                    </div>
                """.format(image_to_base64(processed_logo_sidebar)), unsafe_allow_html=True)
                
            st.write(f"**{st.session_state['name']}**님 ({st.session_state['role']})")
            
            menu_options = ["본점 공지", "작업장 공지", "반복 업무"]
            menu_icons = ['house', 'tools', 'repeat']
            
            if st.session_state['role'] == "Master":
                menu_options.insert(0, "직원 관리")
                menu_icons.insert(0, "people")
                
            menu_options.append("로그아웃")
            menu_icons.append("box-arrow-right")

            m = option_menu("메뉴", menu_options, icons=menu_icons, menu_icon="cast", default_index=0, styles={"container": {"background-color": "#FFF3E0"}, "nav-link-selected": {"background-color": "#8D6E63"}})
            
            if m=="로그아웃":
                st.session_state.logged_in=False
                cookies["auto_login"]="false"
                cookies.save()
                st.rerun()
        
        pt = get_pending_tasks_list()
        if st.session_state.get("show_login_alert", False):
            if pt: st.toast(f"할 일 {len(pt)}건!", icon="🚨"); time.sleep(1)
            st.session_state["show_login_alert"] = False
        
        if m == "직원 관리": page_staff_mgmt()
        elif m == "본점 공지": page_board("본점", "🏠")
        elif m == "작업장 공지": page_board("작업장", "🏭")
        elif m == "반복 업무": page_routine()

if __name__ == "__main__":
    main()
