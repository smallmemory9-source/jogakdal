import streamlit as st
import pandas as pd
import hashlib
import time
from datetime import datetime, date, timedelta
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# --- [0. 기본 설정] ---
st.set_page_config(
    page_title="조각달과자점 파트너", 
    page_icon="🥐", 
    layout="wide", 
    initial_sidebar_state="collapsed" 
)

# --- [1. 디자인 & CSS] ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
    html, body, [class*="css"]  { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; }
    .stApp { background-color: #FFF3E0; }
    
    /* 헤더 설정 */
    header { visibility: visible !important; background: transparent !important; }
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stStatusWidget"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    .block-container { padding-top: 50px !important; }
    
    /* 버튼 스타일 */
    .stButton>button {
        background-color: #8D6E63; color: white; border-radius: 12px; border: none;
        padding: 0.5rem; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #6D4C41; color: #FFF8E1; }
    
    /* 댓글 및 박스 스타일 */
    .comment-box { background-color: #F5F5F5; padding: 10px; border-radius: 8px; margin-top: 5px; font-size: 0.9rem; }
    .warning-banner {
        background-color: #FFEBEE; border: 1px solid #FFCDD2; color: #C62828; 
        padding: 15px; border-radius: 10px; margin-bottom: 20px; font-weight: bold; text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 구글 시트 데이터 관리 (캐싱 적용)] ---
conn = st.connection("gsheets", type=GSheetsConnection)

SHEET_NAMES = {
    "users": "users",
    "posts": "posts",
    "comments": "comments",
    "routine_def": "routine_def",
    "routine_log": "routine_log"
}

# [핵심] 60초(ttl=60) 동안은 데이터를 메모리에 기억해둠 (구글 API 보호)
@st.cache_data(ttl=60)
def load_data(key):
    try:
        return conn.read(worksheet=SHEET_NAMES[key])
    except Exception:
        return pd.DataFrame()

def load(key):
    return load_data(key)

def save(key, df):
    try:
        conn.update(worksheet=SHEET_NAMES[key], data=df)
        # 중요: 저장을 했으면 기억해둔 데이터(캐시)를 지워서 최신화
        load_data.clear()
    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ 구글 시트 사용량이 많아 잠시 대기 중입니다. 1분 뒤 다시 시도해주세요.")
        else:
            st.error(f"저장 실패: {e}")

def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def init_db():
    try:
        users = load("users")
        # 데이터가 없으면 초기화
        if users.empty or "username" not in users.columns:
            admin_pw = hash_password("1234")
            init_users = pd.DataFrame([{"username": "admin", "password": admin_pw, "name": "사장님", "role": "Manager"}])
            save("users", init_users)
        
        # 다른 테이블도 한 번씩 호출하여 캐시에 등록
        load("posts")
        load("routine_def")
    except:
        pass

init_db()

# --- [3. 날짜 계산 로직] ---
def is_task_due(start_date_str, cycle_type, interval_val):
    try:
        if pd.isna(start_date_str) or str(start_date_str).strip() == "": return False
        
        # 날짜 형식이 다양할 수 있어 처리
        try:
            start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
        except:
            return False

        today = date.today()
        if today < start_date: return False
        
        delta_days = (today - start_date).days
        
        if cycle_type == "매일": return True
        elif cycle_type == "매주": return delta_days % 7 == 0
        elif cycle_type == "매월": return today.day == start_date.day
        elif cycle_type == "N일 간격": return delta_days % int(interval_val) == 0
        return False
    except: return False

def get_pending_routines():
    defs = load("routine_def")
    logs = load("routine_log")
    if defs.empty: return []

    today_str = date.today().strftime("%Y-%m-%d")
    pending_tasks = []
    
    for _, task in defs.iterrows():
        if is_task_due(task.get("start_date"), task.get("cycle_type"), task.get("interval_val", 1)):
            # 완료 여부 체크
            if not logs.empty:
                # 안전하게 문자열로 변환하여 비교
                done = logs[(logs["task_id"].astype(str) == str(task["id"])) & (logs["done_date"] == today_str)]
                if done.empty:
                    pending_tasks.append(task["task_name"])
            else:
                pending_tasks.append(task["task_name"])
                
    return pending_tasks

# --- [4. 페이지 구성] ---

def login_page():
    st.markdown("<br><h1 style='text-align:center;'>🥐 조각달 업무수첩</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("입장"):
                users = load("users")
                hashed_pw = hash_password(upw)
                if not users.empty:
                    user = users[(users["username"] == uid) & (users["password"] == hashed_pw)]
                    if not user.empty:
                        st.session_state.update({"logged_in": True, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                        st.session_state["show_login_alert"] = True
                        st.rerun()
                    else: st.error("정보가 올바르지 않습니다.")
                else: st.error("사용자 데이터가 없습니다.")

    with tab2:
        with st.form("signup"):
            nid = st.text_input("희망 아이디")
            npw = st.text_input("희망 비밀번호", type="password")
            nname = st.text_input("이름 (실명)")
            if st.form_submit_button("가입 신청"):
                users = load("users")
                if not users.empty and nid in users["username"].values: 
                    st.warning("이미 존재하는 아이디입니다.")
                elif nid and npw and nname:
                    new_user = pd.DataFrame([{"username": nid, "password": hash_password(npw), "name": nname, "role": "Staff"}])
                    if users.empty: save("users", new_user)
                    else: save("users", pd.concat([users, new_user], ignore_index=True))
                    st.success("가입 완료! 로그인 해주세요.")

def page_board(board_name, icon):
    st.header(f"{icon} {board_name} 게시판")
    
    with st.expander("✏️ 글 쓰기"):
        with st.form(f"write_{board_name}"):
            title = st.text_input("제목")
            content = st.text_area("내용")
            if st.form_submit_button("등록"):
                df = load("posts")
                new_id = 1
                if not df.empty and "id" in df.columns: new_id = pd.to_numeric(df["id"]).max() + 1
                
                new_post = pd.DataFrame([{"id": new_id, "board_type": board_name, "title": title, "content": content, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])
                
                if df.empty: save("posts", new_post)
                else: save("posts", pd.concat([df, new_post], ignore_index=True))
                st.rerun()

    posts = load("posts")
    comments = load("comments")
    
    if posts.empty:
        st.info("작성된 글이 없습니다.")
    else:
        # 해당 게시판 글만 필터링
        my_posts = posts[posts["board_type"] == board_name]
        # ID 기준 내림차순 정렬 (최신글 위로)
        if not my_posts.empty:
            my_posts = my_posts.sort_values("id", ascending=False)
        
        for _, row in my_posts.iterrows():
            with st.container():
                st.markdown(f"### {row['title']}")
                st.caption(f"{row['author']} | {row['date']}")
                st.write(row['content'])
                
                st.markdown("---")
                if not comments.empty:
                    post_comments = comments[comments["post_id"].astype(str) == str(row["id"])]
                    for _, c in post_comments.iterrows():
                        st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {c['content']} <span style='color:#aaa; font-size:0.8em;'>({c['date']})</span></div>", unsafe_allow_html=True)
                
                with st.form(f"comment_{row['id']}"):
                    c1, c2 = st.columns([4, 1])
                    c_txt = c1.text_input("댓글", label_visibility="collapsed", placeholder="댓글 달기")
                    if c2.form_submit_button("전송"):
                        new_comment = pd.DataFrame([{"post_id": row["id"], "author": st.session_state["name"], "content": c_txt, "date": datetime.now().strftime("%m-%d %H:%M")}])
                        if comments.empty: save("comments", new_comment)
                        else: save("comments", pd.concat([comments, new_comment], ignore_index=True))
                        st.rerun()
                st.divider()

def page_routine():
    st.header("🔄 반복 업무 관리")
    
    defs = load("routine_def")
    logs = load("routine_log")
    
    if not defs.empty and "id" not in defs.columns: defs["id"] = range(1, len(defs)+1)
    
    today_str = date.today().strftime("%Y-%m-%d")

    tab_list, tab_log = st.tabs(["📝 오늘의 업무", "📜 업무 기록"])

    with tab_list:
        # [관리자 전용 설정]
        if st.session_state["role"] in ["Manager", "관리자"]:
            with st.expander("⚙️ 업무 추가/삭제 (관리자)"):
                with st.form("add_routine"):
                    c1, c2 = st.columns(2)
                    r_name = c1.text_input("업무명")
                    r_start = c2.date_input("시작일", date.today())
                    
                    c3, c4 = st.columns(2)
                    r_cycle = c3.selectbox("주기", ["매일", "매주", "매월", "N일 간격"])
                    r_interval = 1
                    if r_cycle == "N일 간격":
                        r_interval = c4.number_input("간격(일)", 1, 365, 3)
                    
                    if st.form_submit_button("추가"):
                        new_id = 1
                        if not defs.empty and "id" in defs.columns: 
                            new_id = pd.to_numeric(defs["id"]).max() + 1
                        
                        new_row = pd.DataFrame([{
                            "id": new_id, "task_name": r_name, 
                            "start_date": r_start.strftime("%Y-%m-%d"), 
                            "cycle_type": r_cycle, "interval_val": r_interval
                        }])
                        if defs.empty: save("routine_def", new_row)
                        else: save("routine_def", pd.concat([defs, new_row], ignore_index=True))
                        st.success("추가됨")
                        st.rerun()
                
                if not defs.empty:
                    st.markdown("---")
                    for _, r in defs.iterrows():
                        col_a, col_b = st.columns([4,1])
                        col_a.text(f"• {r['task_name']} ({r['cycle_type']})")
                        if col_b.button("삭제", key=f"del_{r['id']}"):
                            save("routine_def", defs[defs["id"] != r['id']])
                            st.rerun()
        
        st.divider()
        
        # [오늘 할 일 표시]
        if defs.empty:
            st.info("등록된 반복 업무가 없습니다.")
        else:
            due_tasks = []
            for _, task in defs.iterrows():
                if is_task_due(task.get("start_date"), task.get("cycle_type"), task.get("interval_val", 1)):
                    due_tasks.append(task)
            
            if not due_tasks:
                st.info("오늘 예정된 업무가 없습니다.")
            else:
                pending_cnt = 0
                for task in due_tasks:
                    is_done = False
                    if not logs.empty:
                        done_rec = logs[(logs["task_id"].astype(str) == str(task["id"])) & (logs["done_date"] == today_str)]
                        if not done_rec.empty: is_done = True
                    
                    if not is_done: pending_cnt += 1
                    
                    with st.container():
                        bg = "#E8F5E9" if is_done else "#FFEBEE"
                        bd = "#C8E6C9" if is_done else "#FFCDD2"
                        st.markdown(f"""
                        <div style="padding:15px; border-radius:10px; border:1px solid {bd}; background-color:{bg}; margin-bottom:10px;">
                            <h4 style="margin:0;">{task['task_name']}</h4>
                        </div>""", unsafe_allow_html=True)
                        
                        c1, c2 = st.columns([1, 4])
                        if is_done:
                            worker = done_rec.iloc[0]['worker']
                            st.success(f"✅ {worker} 완료")
                        else:
                            if st.button("완료하기", key=f"do_{task['id']}"):
                                new_log = pd.DataFrame([{
                                    "task_id": task["id"], "done_date": today_str, 
                                    "worker": st.session_state["name"], 
                                    "created_at": datetime.now().strftime("%H:%M")
                                }])
                                if logs.empty: save("routine_log", new_log)
                                else: save("routine_log", pd.concat([logs, new_log], ignore_index=True))
                                st.rerun()
                
                if pending_cnt == 0:
                    st.balloons()
                    st.success("🎉 오늘 업무 끝!")

    with tab_log:
        if logs.empty:
            st.info("기록이 없습니다.")
        else:
            if not defs.empty:
                # 병합을 위해 타입 통일
                logs["task_id"] = logs["task_id"].astype(str)
                defs["id"] = defs["id"].astype(str)
                merged = pd.merge(logs, defs, left_on="task_id", right_on="id", how="left")
                merged = merged.sort_values(["done_date", "created_at"], ascending=False)
                st.dataframe(merged[["done_date", "created_at", "task_name", "worker"]], use_container_width=True, hide_index=True)

# --- [5. 메인 실행] ---
def main():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
    else:
        with st.sidebar:
            st.title("🥐 조각달")
            st.write(f"**{st.session_state['name']}**님")
            menu = option_menu("메뉴", ["🏠 본점 공지", "🏭 작업장 공지", "🔄 반복 업무", "로그아웃"],
                icons=['house', 'tools', 'repeat', 'box-arrow-right'],
                menu_icon="cast", default_index=0,
                styles={"container": {"background-color": "#FFF3E0"}, "nav-link-selected": {"background-color": "#8D6E63"}})
            
            if menu == "로그아웃":
                st.session_state.logged_in = False
                st.rerun()

        # 알림 로직
        pending = get_pending_routines()
        
        if st.session_state.get("show_login_alert", False):
            if pending:
                st.toast(f"오늘 할 일 {len(pending)}건!", icon="🚨")
                time.sleep(1)
            st.session_state["show_login_alert"] = False
            
        if pending:
            st.markdown(f"""
            <div class="warning-banner">
                🚨 미완료 {len(pending)}건! <span style='font-size:0.8em; font-weight:normal;'>({pending[0]} 등)</span>
            </div>""", unsafe_allow_html=True)

        if menu == "🏠 본점 공지": page_board("본점", "🏠")
        elif menu == "🏭 작업장 공지": page_board("작업장", "🏭")
        elif menu == "🔄 반복 업무": page_routine()

if __name__ == "__main__":
    main()
