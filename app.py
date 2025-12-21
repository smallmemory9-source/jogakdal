import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
from datetime import datetime, date, timedelta
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
    
    header { background-color: transparent !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    
    .nav-link-selected { background-color: #8D6E63 !important; }
    
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }
    
    .confirm-btn > button { background-color: #2E7D32 !important; }
    .confirm-btn > button:hover { background-color: #1B5E20 !important; }

    .comment-box { background-color: #F5F5F5; padding: 10px; border-radius: 8px; margin-top: 5px; font-size: 0.9rem; }
    
    .logo-title-container {
        display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
    }
    .logo-title-container h1 { margin: 0 0 0 10px; font-size: 1.8rem; }
    
    .container-xxl { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
    
    .streamlit-expanderHeader { font-weight: bold; color: #4E342E; }
    </style>
    """, unsafe_allow_html=True)

# --- [쿠키 매니저] ---
cookies = CookieManager()

# --- [2. 구글 시트 연결 및 에러 방지 로직] ---
conn = st.connection("gsheets", type=GSheetsConnection)

SHEET_NAMES = {
    "users": "users",
    "posts": "posts",
    "comments": "comments",
    "routine_def": "routine_def",
    "routine_log": "routine_log",
    "inform_notes": "inform_notes",
    "inform_logs": "inform_logs"
}

# [핵심 수정 1] ttl=2 (2초 캐시) 적용하여 과도한 호출 방지
@st.cache_data(ttl=2)
def load_data(key):
    # [핵심 수정 2] 읽기 실패 시 재시도 (Retry Logic)
    max_retries = 3
    for i in range(max_retries):
        try:
            return conn.read(worksheet=SHEET_NAMES[key], ttl=0)
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                if i < max_retries - 1:
                    time.sleep(2) # 2초 대기 후 재시도
                    continue
            return pd.DataFrame() # 최후의 경우 빈 데이터 반환하여 앱 멈춤 방지
    return pd.DataFrame()

def load(key): return load_data(key)

# [핵심 수정 3] 저장 로직도 재시도 강화
def save(key, df):
    max_retries = 3
    for i in range(max_retries):
        try:
            conn.update(worksheet=SHEET_NAMES[key], data=df)
            load_data.clear() # 저장 성공 시 캐시 비우기 (바로 반영되도록)
            return True
        except Exception as e:
            if i == max_retries - 1:
                st.error(f"저장 중 통신 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
                return False
            time.sleep(2) # 2초 대기

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
                "approved": "True",
                "department": "전체"
            }])
            save("users", init_users)
        
        # 앱 시작 시 한 번씩 로드 (연결 확인)
        for key in SHEET_NAMES:
            load(key)
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

def get_unconfirmed_inform_list(username):
    informs = load("inform_notes")
    logs = load("inform_logs")
    
    if informs.empty: return []
    
    today_str = date.today().strftime("%Y-%m-%d")
    today_informs = informs[informs["target_date"] == today_str]
    
    if today_informs.empty: return []
    
    unconfirmed = []
    for _, note in today_informs.iterrows():
        if not logs.empty:
            is_checked = logs[
                (logs["note_id"].astype(str) == str(note["id"])) & 
                (logs["username"] == username)
            ]
            if is_checked.empty: unconfirmed.append(note)
        else:
            unconfirmed.append(note)
    return unconfirmed

@st.dialog("🚨 중요 알림")
def show_notification_popup(tasks, inform_notes):
    if inform_notes:
        st.error(f"📢 **오늘의 필독 사항 ({len(inform_notes)}건)**")
        st.write("내용 확인 후 '확인' 버튼을 눌러주세요.")
        st.markdown("---")
        for note in inform_notes:
            preview = note['content'][:30] + "..." if len(note['content']) > 30 else note['content']
            st.markdown(f"**📌 {preview}**")
            st.caption("※ [인폼] 메뉴에서 전체 내용을 확인하세요.")
        st.markdown("---")

    if tasks:
        st.warning(f"🔄 **오늘의 반복 업무 ({len(tasks)}건)**")
        for t in tasks:
            st.write(f"• {t['task_name']}")
    
    st.write("")
    if st.button("확인하러 가기"):
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
                        if check_approved(u.iloc[0].get("approved", "False")):
                            dept = u.iloc[0].get("department", "전체")
                            st.session_state.update({
                                "logged_in": True, "name": u.iloc[0]["name"], 
                                "role": u.iloc[0]["role"], "department": dept,
                                "show_popup_on_login": True 
                            })
                            if auto:
                                cookies["auto_login"] = "true"; cookies["uid"] = uid; cookies["upw"] = hpw; cookies.save() 
                            else:
                                if cookies.get("auto_login"): cookies["auto_login"] = "false"; cookies.save()
                            st.rerun()
                        else: st.warning("⏳ 승인 대기 중")
                    else: st.error("정보 불일치")
                else: st.error("DB 오류")
    with tab2:
        with st.form("signup"):
            st.write("가입 신청")
            new_id = st.text_input("희망 아이디")
            new_pw = st.text_input("희망 비밀번호", type="password")
            new_name = st.text_input("이름")
            new_dept = st.selectbox("주 근무지", ["전체", "본점", "작업장"])
            if st.form_submit_button("신청"):
                users = load("users")
                if not users.empty and new_id in users["username"].values: st.error("중복 아이디")
                elif new_id and new_pw and new_name:
                    new_user = pd.DataFrame([{"username": new_id, "password": hash_password(new_pw), "name": new_name, "role": "Staff", "approved": "False", "department": new_dept}])
                    if users.empty: save("users", new_user)
                    else: save("users", pd.concat([users, new_user], ignore_index=True))
                    st.success("신청 완료")
                else: st.warning("빈칸 확인")

def page_inform():
    st.subheader("📢 인폼노트")
    selected_date = st.date_input("📅 날짜 조회", value=date.today())
    selected_date_str = selected_date.strftime("%Y-%m-%d")
    user_role = st.session_state['role']
    username = st.session_state['name']
    
    if user_role in ["Master", "Manager"]:
        with st.expander("📝 인폼 작성"):
            with st.form("new_inform"):
                target_date_input = st.date_input("업무 수행일", value=selected_date)
                ic = st.text_area("전달 내용 (필수)", height=100)
                if st.form_submit_button("등록"):
                    if ic.strip() == "":
                        st.warning("내용을 입력해주세요.")
                    else:
                        df = load("inform_notes")
                        nid = 1
                        if not df.empty and "id" in df.columns:
                            nid = pd.to_numeric(df["id"], errors='coerce').fillna(0).max() + 1
                        new_note = pd.DataFrame([{
                            "id": nid, 
                            "target_date": target_date_input.strftime("%Y-%m-%d"), 
                            "content": ic, 
                            "author": username, 
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }])
                        if df.empty: save("inform_notes", new_note)
                        else: save("inform_notes", pd.concat([df, new_note], ignore_index=True))
                        st.success("등록 완료")
                        time.sleep(1)
                        st.rerun()

    notes = load("inform_notes")
    logs = load("inform_logs")
    cmts = load("comments")
    
    if notes.empty:
        st.info("등록된 전달사항이 없습니다.")
        return

    daily_notes = notes[notes["target_date"] == selected_date_str]
    
    if daily_notes.empty:
        st.info(f"{selected_date_str} 의 인폼이 없습니다.")
    else:
        daily_notes = daily_notes.sort_values("id", ascending=False)
        for _, r in daily_notes.iterrows():
            note_id = str(r["id"])
            with st.container():
                st.markdown(f"""
                <div style="border:1px solid #ddd; padding:15px; border-radius:10px; background-color:white; margin-bottom:10px;">
                    <div style="font-size:0.9em; color:#8D6E63; font-weight:bold;">📅 {r['target_date']} | ✍️ {r['author']}</div>
                    <div style="white-space: pre-wrap; line-height:1.6; font-size:1.05em; margin-top:10px; color:#333;">{r['content']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                confirmed_users = []
                if not logs.empty:
                    l = logs[logs["note_id"].astype(str) == note_id]
                    confirmed_users = l["username"].tolist()
                
                if username not in confirmed_users:
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
                        if st.button("확인함 ✅", key=f"confirm_{note_id}"):
                            nl = pd.DataFrame([{
                                "note_id": note_id, "username": username, 
                                "confirmed_at": datetime.now().strftime("%m-%d %H:%M")
                            }])
                            if logs.empty: save("inform_logs", nl)
                            else: save("inform_logs", pd.concat([logs, nl], ignore_index=True))
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.success("✅ 확인 완료")

                with st.expander(f"👀 확인자 ({len(confirmed_users)}명)"):
                    if confirmed_users: st.write(", ".join(confirmed_users))
                    else: st.write("-")
                
                if not cmts.empty:
                    note_cmts = cmts[cmts["post_id"].astype(str) == f"inform_{note_id}"]
                    for _, c in note_cmts.iterrows():
                        st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {c['content']}</div>", unsafe_allow_html=True)
                
                with st.form(f"cmt_inform_{note_id}"):
                    c1, c2 = st.columns([4,1])
                    ctxt = c1.text_input("댓글", label_visibility="collapsed", placeholder="특이사항 작성")
                    if c2.form_submit_button("등록"):
                        if ctxt.strip():
                            nc = pd.DataFrame([{"post_id": f"inform_{note_id}", "author": username, "content": ctxt, "date": datetime.now().strftime("%m-%d %H:%M")}])
                            if cmts.empty: save("comments", nc)
                            else: save("comments", pd.concat([cmts, nc], ignore_index=True))
                            st.rerun()
                st.markdown("---")

def page_staff_mgmt():
    st.subheader("👥 직원 관리")
    users = load("users")
    if users.empty: return
    if "approved" not in users.columns: users["approved"] = "False"
    if "department" not in users.columns: users["department"] = "전체"
    users["is_approved_bool"] = users["approved"].apply(check_approved)
    
    pending = users[users["is_approved_bool"] == False]
    if not pending.empty:
        st.info(f"승인 대기: {len(pending)}명")
        for _, r in pending.iterrows():
            with st.expander(f"⏳ {r['name']} ({r['username']})"):
                st.write(f"근무지: {r['department']}")
                c1, c2 = st.columns(2)
                if c1.button("수락", key=f"ok_{r['username']}"):
                    users.loc[users["username"]==r["username"], "approved"]="True"
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users); st.rerun()
                if c2.button("거절", key=f"no_{r['username']}"):
                    users=users[users["username"]!=r["username"]]
                    if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                    save("users", users); st.rerun()
    st.divider()
    active = users[users["is_approved_bool"] == True]
    if not active.empty:
        st.write("✅ 직원 목록")
        for i, r in active.iterrows():
            if r['username'] == st.session_state['name'] or r['username'] == "admin": continue
            with st.expander(f"👤 {r['name']} ({r['role']} / {r['department']})"):
                with st.form(key=f"edit_user_{r['username']}"):
                    c1, c2 = st.columns(2)
                    new_role = c1.selectbox("직급", ["Staff", "Manager", "Master"], index=["Staff", "Manager", "Master"].index(r['role']))
                    new_dept = c2.selectbox("근무지", ["전체", "본점", "작업장"], index=["전체", "본점", "작업장"].index(r.get('department', '전체')))
                    c3, c4 = st.columns(2)
                    if c3.form_submit_button("수정", type="primary"):
                        users.loc[users["username"]==r["username"], "role"] = new_role
                        users.loc[users["username"]==r["username"], "department"] = new_dept
                        if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                        save("users", users); st.success("완료"); time.sleep(0.5); st.rerun()
                    if c4.form_submit_button("삭제", type="secondary"):
                        users = users[users["username"] != r["username"]]
                        if "is_approved_bool" in users.columns: del users["is_approved_bool"]
                        save("users", users); st.warning("삭제됨"); time.sleep(0.5); st.rerun()

def page_board(b_name, icon):
    st.subheader(f"{icon} {b_name}")
    user_role = st.session_state['role']
    can_write = (user_role in ["Master", "Manager"]) or (b_name == "건의사항")
    if can_write:
        expander_title = "✏️ 건의사항 올리기" if b_name == "건의사항" else "✏️ 글 쓰기"
        with st.expander(expander_title):
            with st.form(f"w_{b_name}"):
                tt = st.text_input("제목"); ct = st.text_area("내용")
                if st.form_submit_button("등록"):
                    df = load("posts")
                    nid = 1 if df.empty else pd.to_numeric(df["id"], errors='coerce').fillna(0).max()+1
                    np = pd.DataFrame([{"id": nid, "board_type": b_name, "title": tt, "content": ct, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])
                    if df.empty: save("posts", np)
                    else: save("posts", pd.concat([df, np], ignore_index=True))
                    st.rerun()
    elif user_role == "Staff" and b_name != "건의사항": st.info("💡 Staff는 읽기/댓글만 가능")
    
    posts = load("posts"); cmts = load("comments")
    if posts.empty: st.info("글 없음")
    else:
        mp = posts[posts["board_type"].astype(str).str.strip() == b_name] if "board_type" in posts.columns else pd.DataFrame()
        if mp.empty: st.info("글 없음")
        else:
            mp = mp.sort_values("id", ascending=False)
            for _, r in mp.iterrows():
                can_del = (user_role == "Master") or (r['author'] == st.session_state["name"])
                with st.expander(f"{r['title']} ({r['author']})"):
                    st.write(r['content'])
                    if can_del and st.button("삭제", key=f"del_{r['id']}"):
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
    st.subheader("🔄 업무 체크")
    defs = load("routine_def"); logs = load("routine_log")
    if not defs.empty and "id" not in defs.columns: defs["id"] = range(1, len(defs)+1)
    today = date.today().strftime("%Y-%m-%d")
    t1, t2 = st.tabs(["오늘 업무", "기록"])
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
                        c1,c2 = st.columns([4,1]); c1.text(f"• {r['task_name']}")
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
                            dept = u.iloc[0].get("department", "전체")
                            st.session_state.update({"logged_in": True, "name": u.iloc[0]["name"], "role": u.iloc[0]["role"], "department": dept})
                            cookies.save()
        except: pass

    if not st.session_state.logged_in:
        login_page()
    else:
        # 헤더
        processed_logo_header = get_processed_logo("logo.png", icon_size=(50, 50))
        c1, c2 = st.columns([1, 6])
        with c1:
            if processed_logo_header: st.image(processed_logo_header, width=50)
        with c2:
            st.markdown(f"<div style='padding-top:10px;'><b>{st.session_state['name']}</b>님 ({st.session_state.get('department','전체')})</div>", unsafe_allow_html=True)

        # 메뉴
        menu_opts = []
        menu_icons = []
        dept = st.session_state.get('department', '전체')
        
        menu_opts.append("인폼")
        menu_icons.append("calendar-check")
        
        if dept in ['전체', '본점']:
            menu_opts.append("본점")
            menu_icons.append("house")
        if dept in ['전체', '작업장']:
            menu_opts.append("작업장")
            menu_icons.append("tools")
            
        menu_opts.extend(["건의", "업무"])
        menu_icons.extend(["lightbulb", "check-square"])
        
        if st.session_state['role'] == "Master":
            menu_opts.insert(0, "관리")
            menu_icons.insert(0, "people")
        menu_opts.append("나가기")
        menu_icons.append("box-arrow-right")
        
        m = option_menu(None, menu_opts, icons=menu_icons, menu_icon="cast", default_index=0, 
                        orientation="horizontal",
                        styles={
                            "container": {"padding": "0!important", "background-color": "#FFF3E0", "margin": "0"},
                            "icon": {"color": "#4E342E", "font-size": "14px"}, 
                            "nav-link": {"font-size": "12px", "text-align": "center", "margin":"0px", "--hover-color": "#eee", "padding": "5px 2px"},
                            "nav-link-selected": {"background-color": "#8D6E63"},
                        })
        
        if m=="나가기":
            st.session_state.logged_in=False; cookies["auto_login"]="false"; cookies.save(); st.rerun()

        # 팝업 로직 (인폼 미확인 + 업무)
        if st.session_state.get("show_popup_on_login", False):
            pt = get_pending_tasks_list()
            unconfirmed_informs = get_unconfirmed_inform_list(st.session_state['name'])
            
            if pt or unconfirmed_informs:
                show_notification_popup(pt, unconfirmed_informs)
            st.session_state["show_popup_on_login"] = False

        if m == "관리": page_staff_mgmt()
        elif m == "인폼": page_inform()
        elif m == "본점": page_board("본점", "🏠")
        elif m == "작업장": page_board("작업장", "🏭")
        elif m == "건의": page_board("건의사항", "💡")
        elif m == "업무": page_routine()

if __name__ == "__main__":
    main()
