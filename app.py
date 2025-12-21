import streamlit as st
import pandas as pd
import hashlib
import time
from datetime import datetime, date
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection
from streamlit_cookies_manager import CookieManager

# --- [0. 기본 설정] ---
st.set_page_config(
    page_title="조각달과자점 파트너", 
    page_icon="🥐", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- [1. 디자인 & CSS (화살표 복구)] ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; }
    .stApp { background-color: #FFF3E0; }
    
    /* 헤더 투명화 (내용은 가리되 공간은 유지) */
    header { background-color: transparent !important; }
    
    /* 불필요한 상단 데코레이션 숨김 */
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    
    /* [핵심] 사이드바 여는 화살표(>) 버튼 강제 소환 */
    section[data-testid="stSidebar"] > div > div:nth-child(2) {
        display: none; /* X버튼 숨김 방지 */
    }
    
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        visibility: visible !important;
        color: #4E342E !important; /* 진한 갈색 아이콘 */
        background-color: rgba(255, 255, 255, 0.5) !important; /* 반투명 흰색 배경 */
        border-radius: 8px;
        padding: 5px;
        z-index: 1000002 !important; /* 맨 앞으로 가져오기 */
        top: 10px !important;
        left: 10px !important;
    }
    
    /* 모바일 여백 조정 */
    .block-container { padding-top: 50px !important; }
    
    /* 버튼 스타일 */
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }
    
    /* 댓글 및 박스 스타일 */
    .comment-box { background-color: #F5F5F5; padding: 10px; border-radius: 8px; margin-top: 5px; font-size: 0.9rem; }
    
    /* 알림창(Expander) 스타일 */
    .streamlit-expanderHeader {
        background-color: #FFEBEE !important;
        color: #C62828 !important;
        border: 1px solid #FFCDD2;
        border-radius: 10px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [쿠키 매니저] ---
cookies = CookieManager()
# 모바일 흰 화면 방지용 주석 처리
# if not cookies.ready(): st.stop()

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
            init_users = pd.DataFrame([{"username": "admin", "password": admin_pw, "name": "사장님", "role": "Manager"}])
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

# --- [4. 화면 구성] ---
def login_page():
    st.markdown("<br><h1 style='text-align:center;'>🥐 조각달 업무수첩</h1>", unsafe_allow_html=True)
    
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
                        st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"], "show_login_alert": True})
                        st.rerun()
    except: pass

    tab1, tab2 = st.tabs(["로그인", "회원가입"])
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
                        st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"], "show_login_alert": True})
                        if auto:
                            cookies["auto_login"] = "true"
                            cookies["uid"] = uid
                            cookies["upw"] = hpw
                            cookies.save()
                        else:
                            if cookies.get("auto_login"): cookies["auto_login"] = "false"; cookies.save()
                        st.rerun()
                    else: st.error("아이디/비번 확인")
                else: st.error("DB 오류")
    
    with tab2:
        with st.form("signup"):
            nid = st.text_input("희망 아이디")
            npw = st.text_input("희망 비밀번호", type="password")
            nname = st.text_input("이름")
            if st.form_submit_button("가입"):
                users = load("users")
                if not users.empty and nid in users["username"].values: st.warning("중복 ID")
                elif nid and npw and nname:
                    new_u = pd.DataFrame([{"username": nid, "password": hash_password(npw), "name": nname, "role": "Staff"}])
                    if users.empty: save("users", new_u)
                    else: save("users", pd.concat([users, new_u], ignore_index=True))
                    st.success("가입 완료")

def page_board(b_name, icon):
    st.header(f"{icon} {b_name} 게시판")
    with st.expander("✏️ 글 쓰기"):
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
    
    posts = load("posts")
    cmts = load("comments")
    if posts.empty: st.info("글이 없습니다.")
    else:
        if "board_type" in posts.columns:
            mp = posts[posts["board_type"].astype(str).str.strip() == b_name]
            if mp.empty: st.info("글이 없습니다.")
            else:
                mp = mp.sort_values("id", ascending=False)
                for _, r in mp.iterrows():
                    lbl = f"{r['title']}   (✍️ {r['author']} | 📅 {r['date']})"
                    with st.expander(lbl):
                        st.write(r['content'])
                        st.markdown("---")
                        if not cmts.empty:
                            pcmts = cmts[cmts["post_id"].astype(str) == str(r["id"])]
                            for _, c in pcmts.iterrows():
                                st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {c['content']} <span style='color:#aaa;Size:0.8em;'>({c['date']})</span></div>", unsafe_allow_html=True)
                        with st.form(f"c_{r['id']}"):
                            c1, c2 = st.columns([4,1])
                            ctxt = c1.text_input("댓글", label_visibility="collapsed")
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
    
    t1, t2 = st.tabs(["오늘의 업무", "기록"])
    with t1:
        if st.session_state["role"] in ["Manager", "관리자"]:
            with st.expander("⚙️ 설정 (관리자)"):
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
        if not ptasks: st.info("할 일 없음")
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
    if not st.session_state.logged_in: login_page()
    else:
        with st.sidebar:
            st.title("🥐 조각달")
            st.write(f"**{st.session_state['name']}**님")
            m = option_menu("메뉴", ["본점 공지", "작업장 공지", "반복 업무", "로그아웃"], icons=['house','tools','repeat','box-arrow-right'], menu_icon="cast", default_index=0, styles={"container": {"background-color": "#FFF3E0"}, "nav-link-selected": {"background-color": "#8D6E63"}})
            if m=="로그아웃":
                st.session_state.logged_in=False
                cookies["auto_login"]="false"
                cookies.save()
                st.rerun()
        
        pt = get_pending_tasks_list()
        if st.session_state.get("show_login_alert", False):
            if pt: st.toast(f"할 일 {len(pt)}건!", icon="🚨"); time.sleep(1)
            st.session_state["show_login_alert"] = False
        
        if pt:
            lbl = f"🚨 미완료 {len(pt)}건! (클릭해서 처리)"
            with st.expander(lbl):
                for t in pt:
                    c1, c2 = st.columns([4,1])
                    c1.markdown(f"**{t['task_name']}**")
                    if c2.button("완료", key=f"ban_{t['id']}"):
                        nl = pd.DataFrame([{"task_id": t["id"], "done_date": date.today().strftime("%Y-%m-%d"), "worker": st.session_state["name"], "created_at": datetime.now().strftime("%H:%M")}])
                        l = load("routine_log")
                        if l.empty: save("routine_log", nl)
                        else: save("routine_log", pd.concat([l, nl], ignore_index=True))
                        st.rerun()

        if m=="본점 공지": page_board("본점", "🏠")
        elif m=="작업장 공지": page_board("작업장", "🏭")
        elif m=="반복 업무": page_routine()

if __name__ == "__main__":
    main()
