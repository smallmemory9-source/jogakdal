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
    initial_sidebar_state="expanded" # 항상 펼침 상태 유지
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

# --- [1. CSS 스타일 (메뉴 고정 및 비율 조정)] ---
# [핵심 수정] 사이드바 너비 33%(1/3)로 확대, 글씨 크기 축소
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; }
    .stApp { background-color: #FFF3E0; }
    
    header { background-color: transparent !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    
    /* [수정] 사이드바 너비를 20% -> 33% (약 130px~150px)로 확대 */
    section[data-testid="stSidebar"] {
        width: 33% !important;
        min-width: 120px !important; 
        max-width: 33% !important;
        background-color: #FFF3E0;
        border-right: 1px solid #ddd;
    }
    
    /* [수정] 모바일 화면 레이아웃 조정 */
    @media (max-width: 768px) {
        section[data-testid="stSidebar"] {
            display: block !important;
            z-index: 9999 !important;
            position: fixed !important; /* 화면에 고정 */
            height: 100vh !important;
        }
        
        /* 메인 콘텐츠를 오른쪽으로 33% 밀어냄 (사이드바와 겹치지 않게) */
        .block-container {
            margin-left: 33% !important;
            width: 67% !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 67% !important;
        }
        
        /* 사이드바 접기/펼치기 화살표 완전 제거 (항상 고정) */
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
    }

    /* 버튼 스타일 */
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
        font-size: 0.9rem; /* 버튼 글씨도 살짝 줄임 */
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }
    
    .comment-box { background-color: #F5F5F5; padding: 10px; border-radius: 8px; margin-top: 5px; font-size: 0.8rem; }
    
    .logo-title-container {
        display: flex; align-items: center; justify-content: center; margin-bottom: 20px;
    }
    .logo-title-container h1 { margin: 0 0 0 10px; font-size: 2.0rem; }
    
    /* 사이드바 로고 컨테이너 */
    .sidebar-logo-container {
        display: flex; align-items: center; margin-bottom: 5px;
        flex-direction: column; 
        text-align: center;
    }
    
    /* 토스트 메시지 등 팝업이 사이드바 위에 뜨도록 조정 */
    .stToast {
        z-index: 10000 !important;
        left: 35% !important; /* 사이드바 피해서 오른쪽으로 이동 */
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
        if "429" in str(e): st.error("⚠️ 연결량 초과. 잠시 후 시도.")
        else: st.error(f"저장 실패: {e}")

def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def check_approved(val):
    v = str(val).strip().lower()
    return v in ["true", "1", "1.0", "yes", "y", "t"]

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

@st.dialog("🚨 오늘의 할 일")
def show_notification_popup(tasks):
    st.write(f"미완료 업무 **{len(tasks)}건**")
    for t in tasks:
        st.error(f"• {t['task_name']}")
    if st.button("확인"):
        st.rerun()

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

    tab1, tab2 = st.tabs(["로그인", "가입신청"])
    
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
                        if check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"]})
                            st.session_state["show_popup_on_login"] = True 
                            if auto:
                                cookies["auto_login"] = "true"
                                cookies["uid"] = uid
                                cookies["upw"] = hpw
                                cookies.save() 
                            else:
                                if cookies.get("auto_login"): 
                                    cookies["auto_login"] = "false"
                                    cookies.save()
                            st.rerun()
                        else: st.warning("승인 대기 중")
                    else: st.error("정보 불일치")
                else: st.error("DB 오류")

    with tab2:
        with st.form("signup"):
            st.write("가입 후 승인 대기")
            new_id = st.text_input("아이디")
            new_pw = st.text_input("비밀번호", type="password")
            new_name = st.text_input("이름")
            if st.form_submit_button("신청"):
                users = load("users")
                if not users.empty and new_id in users["username"].values:
                    st.error("중복 ID")
                elif new_id and new_pw and new_name:
                    new_user = pd.DataFrame([{
                        "username": new_id, "password": hash_password(new_pw), 
                        "name": new_name, "role": "Staff", "approved": "False"
                    }])
                    if users.empty: save("users", new_user)
                    else: save("users", pd.concat([users, new_user], ignore_index=True))
                    st.success("신청 완료")
                else: st.warning("빈칸 확인")

def page_staff_mgmt():
    st.header("👥 직원 관리")
    users = load("users")
    if users.empty: return
    if "approved" not in users.columns: users["approved"] = "False"
    users["is_approved_bool"] = users["approved"].apply(check_approved)
    
    pending = users[users["is_approved_bool"] == False]
    if not pending.empty:
        st.info(f"승인 대기: {len(pending)}명")
        for _, r in pending.iterrows():
            c1,c2 = st.columns([3,1])
            c1.write(f"{r['name']}")
            with c2:
                if st.button("✅", key=f"ok_{r['username']}"):
                    users.loc[users["username"]==r["username"], "approved"]="True"
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users); st.rerun()
                if st.button("❌", key=f"no_{r['username']}"):
                    users=users[users["username"]!=r["username"]]
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users); st.rerun()
    
    st.divider()
    active = users[users["is_approved_bool"] == True]
    if not active.empty:
        for _, r in active.iterrows():
            c1,c2 = st.columns([3,1])
            c1.write(f"**{r['name']}** ({r['role']})")
            if r['username'] != "admin" and r['username'] != st.session_state['name']:
                if c2.button("삭제", key=f"del_{r['username']}"):
                    users=users[users["username"]!=r["username"]]
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users); st.rerun()

def page_board(b_name, icon):
    st.header(f"{icon} {b_name}")
    user_role = st.session_state['role']
    can_write = (user_role in ["Master", "Manager"]) or (b_name == "건의사항")
    
    if can_write:
        with st.expander("✏️ 글쓰기"):
            with st.form(f"w_{b_name}"):
                tt = st.text_input("제목")
                ct = st.text_area("내용")
                if st.form_submit_button("등록"):
                    df = load("posts")
                    nid = 1 if df.empty else pd.to_numeric(df["id"], errors='coerce').fillna(0).max()+1
                    np = pd.DataFrame([{"id": nid, "board_type": b_name, "title": tt, "content": ct, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])
                    if df.empty: save("posts", np)
                    else: save("posts", pd.concat([df, np], ignore_index=True))
                    st.rerun()
    
    posts = load("posts")
    cmts = load("comments")
    if posts.empty: st.info("글 없음")
    else:
        mp = posts[posts["board_type"].astype(str).str.strip() == b_name] if "board_type" in posts.columns else pd.DataFrame()
        if mp.empty: st.info("글 없음")
        else:
            mp = mp.sort_values("id", ascending=False)
            for _, r in mp.iterrows():
                can_delete = (user_role == "Master") or (r['author'] == st.session_state["name"])
                with st.expander(f"{r['title']} ({r['author']})"):
                    st.write(r['content'])
                    if can_delete and st.button("삭제", key=f"del_{r['id']}"):
                        posts = posts[posts["id"] != r["id"]]; save("posts", posts); st.rerun()
                    if not cmts.empty:
                        for _, c in cmts[cmts["post_id"].astype(str) == str(r["id"])].iterrows():
                            st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {c['content']}</div>", unsafe_allow_html=True)
                    with st.form(f"c_{r['id']}"):
                        c1,c2 = st.columns([4,1])
                        ctxt = c1.text_input("댓글", label_visibility="collapsed")
                        if c2.form_submit_button("등록"):
                            nc = pd.DataFrame([{"post_id": r["id"], "author": st.session_state["name"], "content": ctxt, "date": datetime.now().strftime("%m-%d %H:%M")}])
                            if cmts.empty: save("comments", nc)
                            else: save("comments", pd.concat([cmts, nc], ignore_index=True))
                            st.rerun()

def page_routine():
    st.header("🔄 업무")
    defs = load("routine_def"); logs = load("routine_log")
    if not defs.empty and "id" not in defs.columns: defs["id"] = range(1, len(defs)+1)
    today = date.today().strftime("%Y-%m-%d")
    
    t1, t2 = st.tabs(["오늘", "기록"])
    with t1:
        if st.session_state['role'] in ["Master", "Manager"]:
            with st.expander("관리"):
                with st.form("new_r"):
                    c1,c2 = st.columns(2); rn = c1.text_input("업무명"); rs = c2.date_input("시작일")
                    c3,c4 = st.columns(2); rc = c3.selectbox("주기", ["매일","매주","매월","N일 간격"]); ri = 1
                    if rc=="N일 간격": ri = c4.number_input("간격",1,365,3)
                    if st.form_submit_button("추가"):
                        nid = 1 if defs.empty else pd.to_numeric(defs["id"], errors='coerce').fillna(0).max()+1
                        nr = pd.DataFrame([{"id": nid, "task_name": rn, "start_date": rs.strftime("%Y-%m-%d"), "cycle_type": rc, "interval_val": ri}])
                        if defs.empty: save("routine_def", nr)
                        else: save("routine_def", pd.concat([defs, nr], ignore_index=True))
                        st.rerun()
                if not defs.empty:
                    for _, r in defs.iterrows():
                        c1,c2 = st.columns([4,1])
                        c1.text(f"• {r['task_name']}")
                        if c2.button("삭제", key=f"d_{r['id']}"):
                            save("routine_def", defs[defs["id"]!=r['id']]); st.rerun()
        st.divider()
        ptasks = get_pending_tasks_list()
        if not ptasks: st.info("완료!")
        else:
            for t in ptasks:
                st.markdown(f"<div style='padding:10px; border:1px solid #FFCDD2; background:#FFEBEE; border-radius:10px; margin-bottom:5px; font-size:0.9rem;'><b>{t['task_name']}</b></div>", unsafe_allow_html=True)
                if st.button("완료", key=f"do_{t['id']}"):
                    nl = pd.DataFrame([{"task_id": t["id"], "done_date": today, "worker": st.session_state["name"], "created_at": datetime.now().strftime("%H:%M")}])
                    if logs.empty: save("routine_log", nl)
                    else: save("routine_log", pd.concat([logs, nl], ignore_index=True))
                    st.rerun()
    with t2:
        if not logs.empty and not defs.empty:
            logs["task_id"] = logs["task_id"].astype(str); defs["id"] = defs["id"].astype(str)
            m = pd.merge(logs, defs, left_on="task_id", right_on="id", how="left").sort_values(["done_date", "created_at"], ascending=False)
            st.dataframe(m[["done_date", "task_name", "worker"]], use_container_width=True, hide_index=True)

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        try:
            if cookies.get("auto_login") == "true":
                sid, spw = cookies.get("uid"), cookies.get("upw")
                if sid and spw:
                    users = load("users")
                    if not users.empty:
                        users["username"] = users["username"].astype(str)
                        users["password"] = users["password"].astype(str)
                        u = users[(users["username"] == sid) & (users["password"] == spw)]
                        if not u.empty and check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"]})
                            cookies.save()
        except: pass

    if not st.session_state.logged_in:
        login_page()
    else:
        with st.sidebar:
            processed_logo_sidebar = get_processed_logo("logo.png", icon_size=(50, 50))
            if processed_logo_sidebar:
                st.markdown("""
                    <div class="sidebar-logo-container">
                        <img src="data:image/png;base64,{}" style="max-height: 50px; width: auto;">
                    </div>
                """.format(image_to_base64(processed_logo_sidebar)), unsafe_allow_html=True)
            
            # 이름 작게 표시
            st.markdown(f"<div style='text-align:center; font-size:0.8rem; margin-bottom:10px;'><b>{st.session_state['name']}</b></div>", unsafe_allow_html=True)
            
            menu_opts = ["본점", "작업장", "건의", "업무"]
            menu_icons = ['house', 'tools', 'lightbulb', 'check-square']
            if st.session_state['role'] == "Master":
                menu_opts.insert(0, "관리")
                menu_icons.insert(0, "people")
            menu_opts.append("나가기")
            menu_icons.append("box-arrow-right")
            
            # [수정] 메뉴 글씨 크기(12px) 및 패딩 조절로 좁은 사이드바에 맞춤
            m = option_menu(None, menu_opts, icons=menu_icons, menu_icon="cast", default_index=0, 
                            styles={
                                "container": {"padding": "0!important", "background-color": "#FFF3E0"},
                                "icon": {"color": "#4E342E", "font-size": "14px"}, 
                                "nav-link": {"font-size": "12px", "text-align": "left", "margin":"0px", "--hover-color": "#eee", "padding": "10px 5px"},
                                "nav-link-selected": {"background-color": "#8D6E63"},
                            })
            
            if m=="나가기":
                st.session_state.logged_in=False; cookies["auto_login"]="false"; cookies.save(); st.rerun()

        pt = get_pending_tasks_list()
        if st.session_state.get("show_popup_on_login", False):
            if pt:
                show_notification_popup(pt)
            st.session_state["show_popup_on_login"] = False

        if m == "관리": page_staff_mgmt()
        elif m == "본점": page_board("본점", "🏠")
        elif m == "작업장": page_board("작업장", "🏭")
        elif m == "건의": page_board("건의사항", "💡")
        elif m == "업무": page_routine()

if __name__ == "__main__":
    main()
