import streamlit as st
import pandas as pd
import os
import hashlib
import time
from datetime import datetime, date, timedelta
from streamlit_option_menu import option_menu

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
    
    /* [수정됨] 헤더 설정: 화살표는 보이고, 잡다한 메뉴는 숨김 */
    header { 
        visibility: visible !important; 
        background: transparent !important; 
    }
    
    /* 우측 상단 메뉴(점 3개, Deploy 버튼)와 상단 데코레이션 바 숨기기 */
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stStatusWidget"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    
    /* 모바일 최적화 여백 */
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

# --- [2. 데이터 관리 함수] ---
FILES = {
    "users": "users.csv",
    "posts": "posts.csv",
    "comments": "comments.csv",
    "routine_def": "routine_def.csv", # 정의 파일
    "routine_log": "routine_log.csv"  # 기록 파일
}

def load(key):
    try:
        if not os.path.exists(FILES[key]): return pd.DataFrame()
        return pd.read_csv(FILES[key])
    except: return pd.DataFrame()

def save(key, df):
    df.to_csv(FILES[key], index=False)

def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def init_db():
    if not os.path.exists(FILES["users"]):
        admin_pw = hash_password("1234")
        pd.DataFrame({"username": ["admin"], "password": [admin_pw], "name": ["사장님"], "role": ["Manager"]}).to_csv(FILES["users"], index=False)
    
    if not os.path.exists(FILES["posts"]):
        pd.DataFrame(columns=["id", "board_type", "title", "content", "author", "date"]).to_csv(FILES["posts"], index=False)
        
    if not os.path.exists(FILES["comments"]):
        pd.DataFrame(columns=["post_id", "author", "content", "date"]).to_csv(FILES["comments"], index=False)
    
    # [변경됨] 반복 업무 정의: 시작일(start_date)과 주기값(interval) 추가
    if not os.path.exists(FILES["routine_def"]):
        pd.DataFrame(columns=["id", "task_name", "start_date", "cycle_type", "interval_val"]).to_csv(FILES["routine_def"], index=False)
        
    if not os.path.exists(FILES["routine_log"]):
        pd.DataFrame(columns=["task_id", "done_date", "worker", "created_at"]).to_csv(FILES["routine_log"], index=False)

init_db()

# --- [3. 핵심 로직: 날짜 계산] ---
def is_task_due(start_date_str, cycle_type, interval_val):
    """
    오늘이 업무를 해야 하는 날인지 계산하는 함수
    """
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        today = date.today()
        
        # 시작일 이전이면 아직 아님
        if today < start_date:
            return False
        
        delta_days = (today - start_date).days
        
        if cycle_type == "매일":
            return True
        elif cycle_type == "매주":
            # 시작일로부터 7일 간격 (같은 요일)
            return delta_days % 7 == 0
        elif cycle_type == "매월":
            # 단순화: 일(Day)이 같으면 수행 (예: 1월 15일 시작 -> 2월 15일)
            return today.day == start_date.day
        elif cycle_type == "N일 간격":
            # 시작일로부터 N일 마다
            return delta_days % int(interval_val) == 0
            
        return False
    except:
        return False

def get_pending_routines():
    """오늘 날짜 기준으로 안 한 업무 리스트 반환"""
    defs = load("routine_def")
    logs = load("routine_log")
    if defs.empty: return []

    today_str = date.today().strftime("%Y-%m-%d")
    pending_tasks = []
    
    for _, task in defs.iterrows():
        # 1. 오늘이 해야 하는 날인지 체크
        if is_task_due(task["start_date"], task["cycle_type"], task["interval_val"]):
            # 2. 오늘 이미 했는지 체크
            done = logs[(logs["task_id"] == task["id"]) & (logs["done_date"] == today_str)]
            if done.empty:
                pending_tasks.append(task["task_name"])
                
    return pending_tasks

# --- [4. 페이지별 구성] ---

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
                user = users[(users["username"] == uid) & (users["password"] == hashed_pw)]
                if not user.empty:
                    st.session_state.update({"logged_in": True, "name": user.iloc[0]["name"], "role": user.iloc[0]["role"]})
                    # 로그인 직후 알림 플래그 설정
                    st.session_state["show_login_alert"] = True
                    st.rerun()
                else: st.error("정보가 올바르지 않습니다.")

    with tab2:
        with st.form("signup"):
            nid = st.text_input("희망 아이디")
            npw = st.text_input("희망 비밀번호", type="password")
            nname = st.text_input("이름 (실명)")
            if st.form_submit_button("가입 신청"):
                users = load("users")
                if nid in users["username"].values: st.warning("중복된 아이디")
                elif nid and npw and nname:
                    new_user = pd.DataFrame([{"username": nid, "password": hash_password(npw), "name": nname, "role": "Staff"}])
                    save("users", pd.concat([users, new_user], ignore_index=True))
                    st.success("가입 완료! 로그인 해주세요.")

def page_board(board_name, icon):
    st.header(f"{icon} {board_name} 게시판")
    
    with st.expander("✏️ 글 쓰기"):
        with st.form(f"write_{board_name}"):
            title = st.text_input("제목")
            content = st.text_area("내용")
            if st.form_submit_button("등록"):
                df = load("posts")
                new_id = 1 if df.empty else df["id"].max() + 1
                new_post = pd.DataFrame([{"id": new_id, "board_type": board_name, "title": title, "content": content, "author": st.session_state["name"], "date": datetime.now().strftime("%Y-%m-%d")}])
                save("posts", pd.concat([df, new_post], ignore_index=True))
                st.rerun()

    posts = load("posts")
    comments = load("comments")
    my_posts = posts[posts["board_type"] == board_name].sort_values("id", ascending=False)
    
    if my_posts.empty:
        st.info("아직 게시글이 없습니다.")
    else:
        for _, row in my_posts.iterrows():
            with st.container():
                st.markdown(f"### {row['title']}")
                st.caption(f"{row['author']} | {row['date']}")
                st.write(row['content'])
                
                st.markdown("---")
                if not comments.empty:
                    post_comments = comments[comments["post_id"] == row["id"]]
                    for _, c in post_comments.iterrows():
                        st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {c['content']} <span style='color:#aaa; font-size:0.8em;'>({c['date']})</span></div>", unsafe_allow_html=True)
                
                with st.form(f"comment_{row['id']}"):
                    c1, c2 = st.columns([4, 1])
                    c_txt = c1.text_input("댓글 달기", label_visibility="collapsed", placeholder="의견 남기기")
                    if c2.form_submit_button("전송"):
                        new_comment = pd.DataFrame([{"post_id": row["id"], "author": st.session_state["name"], "content": c_txt, "date": datetime.now().strftime("%m-%d %H:%M")}])
                        save("comments", pd.concat([comments, new_comment], ignore_index=True))
                        st.rerun()
                st.divider()

def page_routine():
    st.header("🔄 반복 업무 관리")
    
    defs = load("routine_def")
    logs = load("routine_log")
    if "id" not in defs.columns: defs["id"] = range(1, len(defs)+1)
    
    today_str = date.today().strftime("%Y-%m-%d")

    # 탭으로 기능 분리
    tab_list, tab_log = st.tabs(["📝 오늘의 업무", "📜 업무 수행 기록"])

    # ----------------------------------------------------
    # 탭 1: 오늘의 업무 (및 관리자 설정)
    # ----------------------------------------------------
    with tab_list:
        # [관리자 전용 설정]
        if st.session_state["role"] in ["Manager", "관리자"]:
            with st.expander("⚙️ 반복 업무 추가/삭제 (관리자)"):
                with st.form("add_routine"):
                    st.write("새로운 반복 업무를 등록합니다.")
                    c1, c2 = st.columns(2)
                    r_name = c1.text_input("업무명 (예: 대청소)")
                    r_start = c2.date_input("시작 기준일", date.today())
                    
                    c3, c4 = st.columns(2)
                    r_cycle = c3.selectbox("반복 주기", ["매일", "매주", "매월", "N일 간격"])
                    r_interval = 1
                    if r_cycle == "N일 간격":
                        r_interval = c4.number_input("간격 (일)", min_value=1, value=3)
                    
                    if st.form_submit_button("업무 추가"):
                        new_id = 1 if defs.empty else defs["id"].max() + 1
                        new_row = pd.DataFrame([{
                            "id": new_id, 
                            "task_name": r_name, 
                            "start_date": r_start.strftime("%Y-%m-%d"), 
                            "cycle_type": r_cycle, 
                            "interval_val": r_interval
                        }])
                        save("routine_def", pd.concat([defs, new_row], ignore_index=True))
                        st.success("등록되었습니다.")
                        st.rerun()
                
                if not defs.empty:
                    st.markdown("---")
                    st.caption("등록된 업무 목록 (삭제 가능)")
                    for _, r in defs.iterrows():
                        info = f"{r['cycle_type']}"
                        if r['cycle_type'] == "N일 간격": info += f" ({int(r['interval_val'])}일 마다)"
                        info += f" | {r['start_date']} 부터"
                        
                        col_a, col_b = st.columns([4,1])
                        col_a.text(f"• {r['task_name']} [{info}]")
                        if col_b.button("삭제", key=f"del_{r['id']}"):
                            save("routine_def", defs[defs["id"] != r['id']])
                            st.rerun()

        st.divider()
        
        # [오늘 할 일 목록 표시]
        # 계산 로직
        due_tasks = []
        for _, task in defs.iterrows():
            if is_task_due(task["start_date"], task["cycle_type"], task["interval_val"]):
                due_tasks.append(task)
        
        if not due_tasks:
            st.info("오늘 예정된 반복 업무가 없습니다.")
        else:
            pending_count = 0
            for task in due_tasks:
                # 완료 여부 체크
                done_rec = logs[(logs["task_id"] == task["id"]) & (logs["done_date"] == today_str)]
                is_done = not done_rec.empty
                if not is_done: pending_count += 1
                
                with st.container():
                    # 스타일링
                    bg_color = "#E8F5E9" if is_done else "#FFEBEE" # 완료 초록, 미완료 빨강 배경
                    border = "#C8E6C9" if is_done else "#FFCDD2"
                    
                    st.markdown(f"""
                    <div style="padding:15px; border-radius:10px; border:1px solid {border}; background-color:{bg_color}; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h4 style="margin:0; color:#333;">{task['task_name']}</h4>
                                <span style="font-size:0.8em; color:#666;">기준일: {task['start_date']} ({task['cycle_type']})</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns([1, 4])
                    if is_done:
                        worker_name = done_rec.iloc[0]['worker']
                        done_time = done_rec.iloc[0]['created_at']
                        st.success(f"✅ {worker_name}님이 처리함 ({done_time})")
                    else:
                        if st.button("지금 완료하기", key=f"do_task_{task['id']}"):
                            now_time = datetime.now().strftime("%H:%M")
                            new_log = pd.DataFrame([{
                                "task_id": task["id"], 
                                "done_date": today_str, 
                                "worker": st.session_state["name"], 
                                "created_at": now_time
                            }])
                            save("routine_log", pd.concat([logs, new_log], ignore_index=True))
                            st.rerun()
            
            if pending_count == 0 and due_tasks:
                st.balloons()
                st.success("🎉 오늘 해야 할 모든 업무를 완료했습니다!")

    # ----------------------------------------------------
    # 탭 2: 업무 수행 기록
    # ----------------------------------------------------
    with tab_log:
        st.subheader("📜 업무 처리 내역")
        if logs.empty:
            st.info("아직 처리된 내역이 없습니다.")
        else:
            # 로그 + 업무명 병합
            merged = pd.merge(logs, defs, left_on="task_id", right_on="id", how="left")
            # 최신순 정렬
            merged = merged.sort_values(by=["done_date", "created_at"], ascending=False)
            
            # 테이블로 깔끔하게 보여주기
            display_df = merged[["done_date", "created_at", "task_name", "worker"]].copy()
            display_df.columns = ["날짜", "시간", "업무명", "처리자(직원)"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)


# --- [5. 메인 앱 실행] ---
def main():
    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        login_page()
    else:
        # --- [사이드바] ---
        with st.sidebar:
            st.title("🥐 조각달")
            st.write(f"**{st.session_state['name']}**님 환영합니다.")
            menu = option_menu("메뉴", ["🏠 본점 공지", "🏭 작업장 공지", "🔄 반복 업무", "로그아웃"],
                icons=['house', 'tools', 'repeat', 'box-arrow-right'],
                menu_icon="cast", default_index=0,
                styles={"container": {"background-color": "#FFF3E0"}, "nav-link-selected": {"background-color": "#8D6E63"}})
            
            if menu == "로그아웃":
                st.session_state.logged_in = False
                st.rerun()

        # --- [📢 알림 팝업 및 배너 로직] ---
        # 1. 오늘 해야 할 미완료 업무 조회
        pending_list = get_pending_routines()
        
        # 2. 로그인 직후 1회 팝업(Toast) 알림
        if st.session_state.get("show_login_alert", False):
            if pending_list:
                msg = f"오늘 처리해야 할 업무가 {len(pending_list)}건 있습니다!"
                st.toast(msg, icon="🚨")
                time.sleep(0.5)
            st.session_state["show_login_alert"] = False 
            
        # 3. 미완료 업무가 있다면 상단에 고정 배너 표시
        if pending_list:
            st.markdown(f"""
            <div class="warning-banner">
                🚨 [오늘의 업무] 미완료 {len(pending_list)}건! ({', '.join(pending_list[:2])} 등)<br>
                <span style='font-size:0.8em; font-weight:normal;'>메뉴 > '반복 업무' 탭에서 확인 후 완료처리 해주세요.</span>
            </div>
            """, unsafe_allow_html=True)

        # --- [페이지 라우팅] ---
        if menu == "🏠 본점 공지": page_board("본점", "🏠")
        elif menu == "🏭 작업장 공지": page_board("작업장", "🏭")
        elif menu == "🔄 반복 업무": page_routine()

if __name__ == "__main__":
    main()
