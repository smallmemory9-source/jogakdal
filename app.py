import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
import pytz
from datetime import datetime, date, timedelta
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection
from streamlit_cookies_manager import CookieManager
from PIL import Image
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# ============================================================
# [0. 상수 및 설정]
# ============================================================
KST = pytz.timezone('Asia/Seoul')

def get_now():
    return datetime.now(KST)

def get_today_str():
    return get_now().strftime("%Y-%m-%d")

SHEET_NAMES = {
    "users": "users",
    "posts": "posts",
    "comments": "comments",
    "routine_def": "routine_def",
    "routine_log": "routine_log",
    "inform_notes": "inform_notes",
    "inform_logs": "inform_logs"
}

DEPARTMENTS = ["전체", "본점", "작업장"]

# ============================================================
# [1. 데이터 클래스]
# ============================================================
@dataclass
class LoadResult:
    data: pd.DataFrame
    success: bool
    error_msg: str = ""

@dataclass
class SaveResult:
    success: bool
    error_msg: str = ""

# ============================================================
# [2. 이미지 처리]
# ============================================================
def image_to_base64(img) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

@st.cache_data
def get_processed_logo(image_path: str, icon_size: tuple = (40, 40)):
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
    except:
        return None

# ============================================================
# [3. 페이지 설정 및 스타일]
# ============================================================
st.set_page_config(
    page_title="조각달과자점 파트너", 
    page_icon="logo.png", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

processed_icon = get_processed_logo("logo.png", icon_size=(192, 192))
if processed_icon:
    icon_base64 = image_to_base64(processed_icon)
    st.markdown(f"""
        <head>
            <link rel="apple-touch-icon" sizes="180x180" href="data:image/png;base64,{icon_base64}">
            <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,{icon_base64}">
        </head>
    """, unsafe_allow_html=True)

# CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');

/* 텍스트 요소만 선택적으로 스타일 적용 */
h1, h2, h3, h4, h5, h6, p, label, 
.stMarkdown p, .stMarkdown li,
.stTextInput input, .stTextArea textarea, 
.stSelectbox > div > div,
[data-testid="stMarkdownContainer"] p {
    font-family: 'Noto Sans KR', sans-serif !important;
    color: #333333 !important;
}

/* 아이콘 폰트 보호 */
.material-icons, [data-testid="stExpanderToggleIcon"] {
    font-family: inherit !important;
}

/* 버튼 스타일 */
.stButton > button {
    background-color: #8D6E63 !important; 
    color: white !important; 
    border-radius: 12px !important; 
    border: none !important;
    font-weight: bold !important; 
}
.stButton > button:hover { 
    background-color: #6D4C41 !important; 
}

/* 확인 버튼 */
.confirm-btn button { background-color: #2E7D32 !important; }
.confirm-btn button:hover { background-color: #1B5E20 !important; }

/* 재시도 버튼 */
.retry-btn button { background-color: #E65100 !important; }

/* 배경색 */
.stApp { background-color: #FFF3E0 !important; }

/* 헤더 숨김 */
header { background-color: transparent !important; }
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }

/* 네비게이션 */
.nav-link-selected { background-color: #8D6E63 !important; color: white !important; }

/* 카드 스타일 */
.dashboard-card {
    background: white;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.dashboard-card h3, .dashboard-card h1 { color: #333333 !important; margin: 0 !important; }
.dashboard-card-urgent { border-left: 4px solid #D32F2F; }
.dashboard-card-warning { border-left: 4px solid #FFA000; }
.dashboard-card-success { border-left: 4px solid #388E3C; }

/* 배지 */
.urgent-badge { 
    background: #D32F2F; color: white !important; 
    padding: 2px 8px; border-radius: 4px; 
    font-size: 0.8rem; font-weight: bold; 
}
.normal-badge { 
    background: #757575; color: white !important; 
    padding: 2px 8px; border-radius: 4px; 
    font-size: 0.8rem; 
}

/* 인폼 카드 */
.inform-card { 
    border: 1px solid #ddd; 
    padding: 15px; 
    border-radius: 10px; 
    background-color: white; 
    margin-bottom: 10px; 
    color: #333333 !important;
}
.inform-card-urgent { 
    border: 2px solid #D32F2F; 
    background-color: #FFEBEE; 
}

/* 멘션 */
.mention { 
    background: #E3F2FD; 
    color: #1565C0 !important; 
    padding: 1px 4px; 
    border-radius: 4px; 
}

/* 로고 타이틀 */
.logo-title-container { 
    display: flex; 
    align-items: center; 
    justify-content: center; 
    margin-bottom: 10px; 
}
.logo-title-container h1 { 
    margin: 0 0 0 10px !important; 
    font-size: 1.8rem !important; 
    color: #333333 !important;
}

/* 네트워크 상태 */
.network-status { 
    position: fixed; 
    top: 60px; 
    right: 10px; 
    padding: 8px 12px; 
    border-radius: 8px; 
    font-size: 0.85rem; 
    z-index: 1000; 
}
.network-error { background: #FFE0B2; color: #E65100 !important; }

/* 댓글 박스 */
.comment-box {
    background: #F5F5F5;
    padding: 8px 12px;
    border-radius: 8px;
    margin: 5px 0;
    color: #333333 !important;
}

/* Expander 헤더 */
.streamlit-expanderHeader { color: #333333 !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# [4. 쿠키 및 DB 연결]
# ============================================================
cookies = CookieManager()
conn = st.connection("gsheets", type=GSheetsConnection)

def safe_get_cookie(key):
    try:
        return cookies.get(key)
    except:
        return None

# ============================================================
# [5. 세션 상태 초기화]
# ============================================================
def init_state():
    defaults = {
        "logged_in": False,
        "name": "",
        "role": "",
        "department": "전체",
        "show_popup_on_login": False,
        "pending_saves": [],
        "data_cache": {},
        "cache_time": {},
        "dashboard_view": None,
        "inform_date": get_now().date(),
        "show_search": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ============================================================
# [6. 데이터 매니저 - 동시성 안전]
# ============================================================
class DataManager:
    CACHE_TTL = 30  # 30초 캐시
    
    @staticmethod
    def _is_cache_valid(key: str) -> bool:
        cache_time = st.session_state.get("cache_time", {}).get(key)
        if not cache_time:
            return False
        return (get_now() - cache_time).total_seconds() < DataManager.CACHE_TTL
    
    @staticmethod
    def _get_cache(key: str) -> Optional[pd.DataFrame]:
        if DataManager._is_cache_valid(key):
            return st.session_state.get("data_cache", {}).get(key)
        return None
    
    @staticmethod
    def _set_cache(key: str, df: pd.DataFrame):
        if "data_cache" not in st.session_state:
            st.session_state["data_cache"] = {}
        if "cache_time" not in st.session_state:
            st.session_state["cache_time"] = {}
        st.session_state["data_cache"][key] = df.copy()
        st.session_state["cache_time"][key] = get_now()
    
    @staticmethod
    def clear_cache(key: str = None):
        if key:
            st.session_state.get("data_cache", {}).pop(key, None)
            st.session_state.get("cache_time", {}).pop(key, None)
        else:
            st.session_state["data_cache"] = {}
            st.session_state["cache_time"] = {}
    
    @staticmethod
    def load(key: str, force_refresh: bool = False) -> LoadResult:
        if not force_refresh:
            cached = DataManager._get_cache(key)
            if cached is not None:
                return LoadResult(data=cached, success=True)
        
        for i in range(3):
            try:
                df = conn.read(worksheet=SHEET_NAMES[key], ttl=0)
                if df is not None:
                    if not df.empty:
                        df.columns = df.columns.str.strip()
                    DataManager._set_cache(key, df)
                    return LoadResult(data=df, success=True)
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower():
                    time.sleep(1 + i)
                    continue
                break
        
        cached = st.session_state.get("data_cache", {}).get(key)
        if cached is not None:
            return LoadResult(data=cached, success=True, error_msg="캐시 사용")
        return LoadResult(data=pd.DataFrame(), success=False, error_msg="로드 실패")
    
    @staticmethod
    def save(key: str, df: pd.DataFrame, desc: str = "") -> SaveResult:
        if key == "users":
            cached = st.session_state.get("data_cache", {}).get(key)
            if cached is not None and not cached.empty:
                if len(df) < len(cached) * 0.5 and len(cached) >= 3:
                    return SaveResult(False, "대량 삭제 감지")
        
        for i in range(3):
            try:
                conn.update(worksheet=SHEET_NAMES[key], data=df)
                DataManager._set_cache(key, df)
                return SaveResult(True)
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower():
                    time.sleep(1 + i)
                    continue
                break
        
        pending = st.session_state.get("pending_saves", [])
        pending.append({"key": key, "data": df.to_dict(), "desc": desc, "time": get_now().isoformat()})
        st.session_state["pending_saves"] = pending[-10:]
        return SaveResult(False, "저장 실패")
    
    @staticmethod
    def append_row(key: str, new_row: dict, id_col: str = "id", desc: str = "") -> SaveResult:
        """동시성 안전 행 추가 (ID 중복 방지 강화)"""
        for _ in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success and result.data.empty:
                time.sleep(0.5)
                continue
            
            df = result.data
            
            # [수정됨] ID가 이미 new_row에 있으면 자동생성 건너뜀
            if id_col and id_col not in new_row:
                if df.empty:
                    new_row[id_col] = 1
                else:
                    try:
                        max_id = pd.to_numeric(df[id_col], errors='coerce').fillna(0).max()
                        new_row[id_col] = int(max_id) + 1
                    except:
                        new_row[id_col] = len(df) + 1
            
            new_df = pd.DataFrame([new_row])
            updated = pd.concat([df, new_df], ignore_index=True) if not df.empty else new_df
            
            save_result = DataManager.save(key, updated, desc)
            if save_result.success:
                return save_result
            time.sleep(0.5)
        
        return SaveResult(False, "추가 실패")
    
    @staticmethod
    def update_row(key: str, match_col: str, match_val: Any, updates: dict, desc: str = "") -> SaveResult:
        for _ in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(0.5)
                continue
            
            df = result.data.copy()
            mask = df[match_col].astype(str) == str(match_val)
            if not mask.any():
                return SaveResult(False, "대상 없음")
            
            for col, val in updates.items():
                df.loc[mask, col] = val
            
            save_result = DataManager.save(key, df, desc)
            if save_result.success:
                return save_result
            time.sleep(0.5)
        
        return SaveResult(False, "수정 실패")
    
    @staticmethod
    def delete_row(key: str, match_col: str, match_val: Any, desc: str = "") -> SaveResult:
        for _ in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(0.5)
                continue
            
            df = result.data.copy()
            df = df[df[match_col].astype(str) != str(match_val)]
            
            save_result = DataManager.save(key, df, desc)
            if save_result.success:
                return save_result
            time.sleep(0.5)
        
        return SaveResult(False, "삭제 실패")
    
    @staticmethod
    def retry_pending() -> Tuple[int, int]:
        pending = st.session_state.get("pending_saves", [])
        if not pending:
            return (0, 0)
        
        success = 0
        still_pending = []
        for item in pending:
            df = pd.DataFrame(item["data"])
            res = DataManager.save(item["key"], df, item["desc"])
            if res.success:
                success += 1
            else:
                still_pending.append(item)
        
        st.session_state["pending_saves"] = still_pending
        return (success, len(still_pending))

# ============================================================
# [7. 유틸리티]
# ============================================================
def hash_pw(pw: str) -> str:
    return hashlib.sha256(str(pw).encode()).hexdigest()

def check_approved(val) -> bool:
    v = str(val).strip().lower()
    return v in ["true", "1", "1.0", "yes"]

def highlight_mentions(text: str) -> str:
    import re
    return re.sub(r'@(\S+)', r'<span class="mention">@\1</span>', str(text))

def is_task_due(start_str, cycle, interval) -> bool:
    try:
        if pd.isna(start_str) or not str(start_str).strip():
            return False
        start = datetime.strptime(str(start_str).strip(), "%Y-%m-%d").date()
        today = get_now().date()
        if today < start:
            return False
        delta = (today - start).days
        if cycle == "매일":
            return True
        elif cycle == "매주":
            return delta % 7 == 0
        elif cycle == "매월":
            return today.day == start.day
        elif cycle == "N일 간격":
            return delta % int(interval) == 0
        return False
    except:
        return False

# ============================================================
# [8. 비즈니스 로직]
# ============================================================
def get_pending_tasks() -> List[dict]:
    defs = DataManager.load("routine_def").data
    logs = DataManager.load("routine_log").data
    if defs.empty:
        return []
    
    today = get_today_str()
    pending = []
    for _, t in defs.iterrows():
        if is_task_due(t.get("start_date"), t.get("cycle_type"), t.get("interval_val", 1)):
            done = False
            if not logs.empty:
                done = not logs[(logs["task_id"].astype(str) == str(t["id"])) & (logs["done_date"] == today)].empty
            if not done:
                pending.append(dict(t))
    return pending

def get_unconfirmed_informs(username: str) -> List[dict]:
    notes = DataManager.load("inform_notes").data
    logs = DataManager.load("inform_logs").data
    if notes.empty:
        return []
    
    today = get_today_str()
    today_notes = notes[notes["target_date"] == today]
    if today_notes.empty:
        return []
    
    unconfirmed = []
    for _, n in today_notes.iterrows():
        confirmed = False
        if not logs.empty:
            confirmed = not logs[(logs["note_id"].astype(str) == str(n["id"])) & (logs["username"] == username)].empty
        if not confirmed:
            unconfirmed.append(dict(n))
    return unconfirmed

def get_new_comments(username: str) -> int:
    posts = DataManager.load("posts").data
    comments = DataManager.load("comments").data
    if posts.empty or comments.empty:
        return 0
    
    my_posts = posts[posts["author"] == username]["id"].astype(str).tolist()
    today_mm = get_now().strftime("%m-%d")
    new_cmts = comments[
        (comments["post_id"].astype(str).isin(my_posts)) &
        (comments["date"].astype(str).str.contains(today_mm, na=False)) &
        (comments["author"] != username)
    ]
    return len(new_cmts)

def get_mentions(username: str) -> List[dict]:
    comments = DataManager.load("comments").data
    if comments.empty:
        return []
    return [dict(c) for _, c in comments.iterrows() if f"@{username}" in str(c.get("content", ""))]

def search_content(query: str) -> Dict[str, List[dict]]:
    results = {"inform": [], "posts": []}
    q = query.lower().strip()
    if not q:
        return results
    
    informs = DataManager.load("inform_notes").data
    if not informs.empty:
        for _, r in informs.iterrows():
            if q in str(r.get("content", "")).lower():
                results["inform"].append(dict(r))
    
    posts = DataManager.load("posts").data
    if not posts.empty:
        for _, r in posts.iterrows():
            if q in str(r.get("title", "")).lower() or q in str(r.get("content", "")).lower():
                results["posts"].append(dict(r))
    
    return results

# ============================================================
# [9. UI 컴포넌트]
# ============================================================
def show_network_status():
    pending = st.session_state.get("pending_saves", [])
    if pending:
        st.markdown(f'<div class="network-status network-error">⚠️ 저장 대기: {len(pending)}건</div>', unsafe_allow_html=True)

def show_retry_button():
    pending = st.session_state.get("pending_saves", [])
    if pending:
        with st.expander(f"⚠️ 저장 실패 ({len(pending)}건)", expanded=True):
            for item in pending:
                st.caption(f"• {item['desc']}")
            st.markdown('<div class="retry-btn">', unsafe_allow_html=True)
            if st.button("🔄 재시도"):
                ok, fail = DataManager.retry_pending()
                if ok:
                    st.success(f"✅ {ok}건 완료")
                if fail:
                    st.error(f"❌ {fail}건 실패")
                time.sleep(1)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

@st.dialog("🚨 알림")
def show_popup(tasks, informs):
    urgent = [n for n in informs if n.get("priority") == "긴급"]
    if urgent:
        st.error(f"🚨 긴급 인폼 {len(urgent)}건")
        for n in urgent[:3]:
            st.write(f"• {n['content'][:50]}...")
    if tasks:
        st.warning(f"🔄 미완료 업무 {len(tasks)}건")
        for t in tasks[:3]:
            st.write(f"• {t['task_name']}")
    if st.button("확인", use_container_width=True):
        st.rerun()

# ============================================================
# [10. 대시보드]
# ============================================================
def show_dashboard():
    username = st.session_state['name']
    
    with st.spinner("로딩..."):
        tasks = get_pending_tasks()
        informs = get_unconfirmed_informs(username)
        comments = get_new_comments(username)
        mentions = get_mentions(username)
    
    st.subheader("📊 오늘의 현황")
    
    c1, c2, c3 = st.columns(3)
    urgent = [i for i in informs if i.get("priority") == "긴급"]
    
    with c1:
        cls = "dashboard-card-urgent" if urgent else "dashboard-card-warning" if informs else "dashboard-card-success"
        st.markdown(f'''
            <div class="dashboard-card {cls}">
                <h3 style="color:#333333 !important;">📢 미확인 인폼</h3>
                <h1 style="color:#333333 !important;">{len(informs)}</h1>
            </div>
        ''', unsafe_allow_html=True)
        if informs and st.button("확인하기", key="dash_inform", use_container_width=True):
            st.session_state["dashboard_view"] = "inform"
            st.rerun()
    
    with c2:
        cls = "dashboard-card-warning" if tasks else "dashboard-card-success"
        st.markdown(f'''
            <div class="dashboard-card {cls}">
                <h3 style="color:#333333 !important;">🔄 미완료 업무</h3>
                <h1 style="color:#333333 !important;">{len(tasks)}</h1>
            </div>
        ''', unsafe_allow_html=True)
        if tasks and st.button("처리하기", key="dash_task", use_container_width=True):
            st.session_state["dashboard_view"] = "task"
            st.rerun()
    
    with c3:
        total = comments + len(mentions)
        cls = "dashboard-card-warning" if total else "dashboard-card-success"
        st.markdown(f'''
            <div class="dashboard-card {cls}">
                <h3 style="color:#333333 !important;">💬 새 알림</h3>
                <h1 style="color:#333333 !important;">{total}</h1>
            </div>
        ''', unsafe_allow_html=True)
        if total and st.button("알림보기", key="dash_notif", use_container_width=True):
            st.session_state["dashboard_view"] = "notif"
            st.rerun()
    
    st.markdown("---")
    
    # 상세 뷰
    view = st.session_state.get("dashboard_view")
    if view:
        if st.button("← 돌아가기"):
            st.session_state["dashboard_view"] = None
            st.rerun()
        
        if view == "inform":
            page_inform()
        elif view == "task":
            page_routine()
        elif view == "notif":
            st.subheader("💬 알림")
            if mentions:
                st.write("**나를 멘션한 댓글:**")
                for m in mentions:
                    st.markdown(f'<div class="comment-box">{m["author"]}: {highlight_mentions(m["content"])}</div>', unsafe_allow_html=True)
            else:
                st.info("새 알림이 없습니다.")

def show_search():
    st.subheader("🔍 검색")
    q = st.text_input("검색어")
    if q:
        res = search_content(q)
        total = len(res["inform"]) + len(res["posts"])
        st.write(f"결과: {total}건")
        if res["inform"]:
            with st.expander(f"인폼 ({len(res['inform'])})"):
                for i in res["inform"]:
                    st.write(f"[{i['target_date']}] {i['content'][:50]}...")
        if res["posts"]:
            with st.expander(f"게시글 ({len(res['posts'])})"):
                for p in res["posts"]:
                    st.write(f"[{p['board_type']}] {p['title']}")

# ============================================================
# [11. 페이지: 로그인]
# ============================================================
def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    logo = get_processed_logo("logo.png", icon_size=(80, 80))
    if logo:
        st.markdown(f'''
            <div class="logo-title-container">
                <img src="data:image/png;base64,{image_to_base64(logo)}" style="max-height:80px;">
                <h1>업무수첩</h1>
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.title("업무수첩")
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            auto = st.checkbox("자동 로그인")
            
            if st.form_submit_button("입장", use_container_width=True):
                res = DataManager.load("users", force_refresh=True)
                if res.success and not res.data.empty:
                    users = res.data
                    hpw = hash_pw(upw)
                    u = users[(users["username"].astype(str) == uid) & (users["password"].astype(str) == hpw)]
                    
                    if not u.empty:
                        if check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({
                                "logged_in": True,
                                "name": u.iloc[0]["name"],
                                "role": u.iloc[0]["role"],
                                "department": u.iloc[0].get("department", "전체"),
                                "show_popup_on_login": True
                            })
                            if auto:
                                try:
                                    cookies["auto_login"] = "true"
                                    cookies["uid"] = uid
                                    cookies["upw"] = hpw
                                    cookies.save()
                                except:
                                    pass
                            st.rerun()
                        else:
                            st.warning("⏳ 승인 대기 중")
                    else:
                        st.error("정보가 일치하지 않습니다.")
                else:
                    st.error("서버 연결 실패")
    
    with tab2:
        with st.form("signup"):
            nid = st.text_input("희망 아이디")
            npw = st.text_input("희망 비밀번호", type="password")
            nname = st.text_input("이름")
            ndept = st.selectbox("근무지", DEPARTMENTS)
            
            if st.form_submit_button("신청", use_container_width=True):
                if nid and npw and nname:
                    res = DataManager.load("users", force_refresh=True)
                    users = res.data if res.success else pd.DataFrame()
                    
                    if not users.empty and nid in users["username"].astype(str).values:
                        st.error("이미 사용 중인 아이디입니다.")
                    else:
                        new_user = {
                            "username": nid,
                            "password": hash_pw(npw),
                            "name": nname,
                            "role": "Staff",
                            "approved": "False",
                            "department": ndept
                        }
                        new_df = pd.DataFrame([new_user])
                        final = pd.concat([users, new_df], ignore_index=True) if not users.empty else new_df
                        DataManager.save("users", final, "회원가입")
                        st.success("✅ 신청 완료! 승인을 기다려주세요.")
                else:
                    st.warning("모든 항목을 입력해주세요.")

# ============================================================
# [12. 페이지: 인폼]
# ============================================================
def page_inform():
    st.subheader("📢 인폼노트")
    
    # 날짜 네비게이션
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("◀ 이전", use_container_width=True):
            st.session_state["inform_date"] -= timedelta(days=1)
            st.rerun()
    with c2:
        st.session_state["inform_date"] = st.date_input(
            "날짜", 
            value=st.session_state.get("inform_date", get_now().date()),
            label_visibility="collapsed"
        )
    with c3:
        if st.button("다음 ▶", use_container_width=True):
            st.session_state["inform_date"] += timedelta(days=1)
            st.rerun()
    
    sel_date = st.session_state["inform_date"].strftime("%Y-%m-%d")
    username = st.session_state['name']
    role = st.session_state['role']
    
    # 작성 (관리자만)
    if role in ["Master", "Manager"]:
        with st.expander("📝 인폼 작성"):
            with st.form("new_inform"):
                target = st.date_input("날짜", value=st.session_state["inform_date"])
                priority = st.radio("중요도", ["일반", "긴급"], horizontal=True)
                content = st.text_area("내용", placeholder="@이름으로 멘션 가능")
                
                if st.form_submit_button("등록", use_container_width=True):
                    if content.strip():
                        DataManager.append_row("inform_notes", {
                            "target_date": target.strftime("%Y-%m-%d"),
                            "content": content,
                            "author": username,
                            "priority": priority,
                            "created_at": get_now().strftime("%Y-%m-%d %H:%M")
                        }, "id", "인폼 등록")
                        st.success("✅ 등록 완료")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("내용을 입력해주세요.")
    
    # 목록 표시
    notes = DataManager.load("inform_notes").data
    logs = DataManager.load("inform_logs").data
    
    if notes.empty:
        st.info("등록된 인폼이 없습니다.")
        return
    
    daily = notes[notes["target_date"] == sel_date]
    if daily.empty:
        st.info(f"{sel_date}의 인폼이 없습니다.")
        return
    
    # 긴급 먼저 정렬
    daily_list = sorted(daily.to_dict('records'), key=lambda x: 0 if x.get('priority') == '긴급' else 1)
    
    for note in daily_list:
        nid = str(note['id'])
        is_urgent = note.get('priority') == '긴급'
        cls = "inform-card-urgent" if is_urgent else "inform-card"
        badge = '<span class="urgent-badge">긴급</span>' if is_urgent else '<span class="normal-badge">일반</span>'
        
        st.markdown(f'''
            <div class="{cls}">
                <div style="display:flex; justify-content:space-between; color:#333333;">
                    <b style="color:#333333;">{note["author"]}</b> {badge}
                </div>
                <div style="margin-top:10px; white-space:pre-wrap; color:#333333;">
                    {highlight_mentions(note["content"])}
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        # 확인자 목록
        confirmed = []
        if not logs.empty:
            confirmed = logs[logs["note_id"].astype(str) == nid]["username"].tolist()
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if username not in confirmed:
                st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
                if st.button("확인함 ✅", key=f"confirm_{nid}", use_container_width=True):
                    DataManager.append_row("inform_logs", {
                        "note_id": nid,
                        "username": username,
                        "confirmed_at": get_now().strftime("%m-%d %H:%M")
                    }, None, "인폼 확인")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.success("✅ 확인됨")
        
        with col2:
            with st.expander(f"확인자 ({len(confirmed)}명)"):
                st.write(", ".join(confirmed) if confirmed else "-")
        
        st.markdown("---")

# ============================================================
# [13. 페이지: 업무 체크]
# ============================================================
def page_routine():
    st.subheader("🔄 업무 체크")
    username = st.session_state['name']
    role = st.session_state['role']
    
    t1, t2 = st.tabs(["📋 오늘 업무", "📊 기록"])
    
    with t1:
        # 1. 관리자: 업무 추가 (ID 중복 방지 - 타임스탬프 사용)
        if role in ["Master", "Manager"]:
            with st.expander("➕ 업무 추가"):
                with st.form("new_task"):
                    name = st.text_input("업무명")
                    start = st.date_input("시작일", value=get_now().date())
                    cycle = st.selectbox("주기", ["매일", "매주", "매월", "N일 간격"])
                    interval = 1
                    if cycle == "N일 간격":
                        interval = st.number_input("간격(일)", 1, 365, 3)
                    
                    if st.form_submit_button("추가", use_container_width=True):
                        if name.strip():
                            # [핵심] ID에 현재 시간(초)을 사용하여 절대 중복되지 않게 함
                            unique_id = int(time.time())
                            DataManager.append_row("routine_def", {
                                "id": unique_id, 
                                "task_name": name, 
                                "start_date": start.strftime("%Y-%m-%d"),
                                "cycle_type": cycle, 
                                "interval_val": interval
                            }, "id", "업무 추가")
                            st.rerun()
        
        # 2. 오늘 할 일
        tasks = get_pending_tasks()
        if not tasks:
            st.success("🎉 오늘의 모든 업무가 완료되었습니다!")
        else:
            st.write(f"**오늘 할 일: {len(tasks)}건**")
            for t in tasks:
                st.markdown(f'''
                    <div style="padding:12px; border:1px solid #FFCDD2; background:#FFEBEE; 
                         border-radius:10px; margin-bottom:8px; color:#333333;">
                        <b style="color:#333333;">{t['task_name']}</b>
                        <span style="color:#888;"> ({t['cycle_type']})</span>
                    </div>
                ''', unsafe_allow_html=True)
                
                with st.form(f"complete_{t['id']}"):
                    memo = st.text_input("메모", placeholder="특이사항 (선택)", key=f"memo_{t['id']}")
                    if st.form_submit_button("✅ 완료", use_container_width=True):
                        DataManager.append_row("routine_log", {
                            "task_id": t['id'],
                            "done_date": get_today_str(),
                            "worker": username,
                            "memo": memo,
                            "created_at": get_now().strftime("%H:%M")
                        }, None, "업무 완료")
                        st.success(f"✅ '{t['task_name']}' 완료!")
                        time.sleep(0.5)
                        st.rerun()
        
        st.markdown("---")

        # [신규 기능] 3. 전체 업무 리스트 (주기별 보기)
        with st.expander("📂 전체 업무 리스트 확인 (주기별 모아보기)"):
            res_defs = DataManager.load("routine_def")
            res_logs = DataManager.load("routine_log")
            
            if res_defs.success and not res_defs.data.empty:
                df_defs = res_defs.data
                df_logs = res_logs.data if res_logs.success else pd.DataFrame()
                
                # 오늘 완료된 업무 ID 확인
                today_done_ids = []
                if not df_logs.empty:
                    today_logs = df_logs[df_logs["done_date"] == get_today_str()]
                    today_done_ids = today_logs["task_id"].astype(str).tolist()
                
                # 주기별 탭 생성
                cycles = ["매일", "매주", "매월", "N일 간격"]
                tabs = st.tabs(cycles)
                
                for i, cy in enumerate(cycles):
                    with tabs[i]:
                        subset = df_defs[df_defs["cycle_type"] == cy]
                        if subset.empty:
                            st.caption("해당 주기의 업무가 없습니다.")
                        else:
                            for _, row in subset.iterrows():
                                is_done = str(row['id']) in today_done_ids
                                icon = "✅" if is_done else "⬜"
                                status = "(완료됨)" if is_done else "(미완료)"
                                st.markdown(f"""
                                    <div style="padding:10px; border-bottom:1px solid #eee;">
                                        {icon} <b>{row['task_name']}</b> <small style='color:#888;'>{status}</small>
                                        <br><small>시작일: {row['start_date']}</small>
                                    </div>
                                """, unsafe_allow_html=True)

                                # 관리자용 수정/삭제 버튼
                                if role in ["Master", "Manager"]:
                                    with st.expander(f"⚙️ 관리 ({row['task_name']})"):
                                        with st.form(f"edit_task_{row['id']}"):
                                            nn = st.text_input("수정: 업무명", value=row['task_name'])
                                            try:
                                                s_dt = datetime.strptime(str(row['start_date']), "%Y-%m-%d").date()
                                            except:
                                                s_dt = get_now().date()
                                            ns = st.date_input("수정: 시작일", value=s_dt)
                                            
                                            c_idx = cycles.index(row['cycle_type']) if row['cycle_type'] in cycles else 0
                                            nc = st.selectbox("수정: 주기", cycles, index=c_idx)
                                            
                                            c_up, c_del = st.columns(2)
                                            if c_up.form_submit_button("💾 수정 저장"):
                                                DataManager.update_row("routine_def", "id", row['id'], {
                                                    "task_name": nn,
                                                    "start_date": ns.strftime("%Y-%m-%d"),
                                                    "cycle_type": nc
                                                }, "업무 수정")
                                                st.rerun()
                                            
                                            if c_del.form_submit_button("🗑️ 삭제"):
                                                DataManager.delete_row("routine_def", "id", row['id'], "업무 삭제")
                                                st.rerun()
            else:
                st.info("등록된 업무가 없습니다.")

    with t2:
        logs = DataManager.load("routine_log").data
        defs = DataManager.load("routine_def").data
        
        if not logs.empty and not defs.empty:
            logs['task_id'] = logs['task_id'].astype(str)
            defs['id'] = defs['id'].astype(str)
            merged = pd.merge(logs, defs, left_on='task_id', right_on='id', how='left')
            merged = merged.sort_values('done_date', ascending=False)
            
            cols = ['done_date', 'task_name', 'worker']
            if 'memo' in merged.columns:
                cols.append('memo')
            
            st.dataframe(merged[cols].head(50), hide_index=True, use_container_width=True)
        else:
            st.info("기록이 없습니다.")

# ============================================================
# [14. 페이지: 게시판]
# ============================================================
def page_board(board_name: str, icon: str):
    st.subheader(f"{icon} {board_name}")
    username = st.session_state['name']
    role = st.session_state['role']
    
    can_write = role in ["Master", "Manager"] or board_name == "건의사항"
    
    if can_write:
        with st.expander("✏️ 글쓰기"):
            with st.form(f"write_{board_name}"):
                title = st.text_input("제목")
                content = st.text_area("내용", placeholder="@이름으로 멘션 가능")
                
                if st.form_submit_button("등록", use_container_width=True):
                    if title.strip() and content.strip():
                        DataManager.append_row("posts", {
                            "board_type": board_name,
                            "title": title,
                            "content": content,
                            "author": username,
                            "date": get_now().strftime("%Y-%m-%d")
                        }, "id", "글 등록")
                        st.rerun()
                    else:
                        st.warning("제목과 내용을 입력해주세요.")
    
    # 글 목록
    posts = DataManager.load("posts").data
    comments = DataManager.load("comments").data
    
    if posts.empty or "board_type" not in posts.columns:
        st.info("등록된 글이 없습니다.")
        return
    
    board_posts = posts[posts["board_type"].astype(str).str.strip() == board_name]
    if board_posts.empty:
        st.info("등록된 글이 없습니다.")
        return
    
    board_posts = board_posts.sort_values("id", ascending=False)
    
    for _, post in board_posts.iterrows():
        pid = str(post['id'])
        can_delete = role == "Master" or post['author'] == username
        
        with st.expander(f"📄 {post['title']} ({post['author']} | {post['date']})"):
            st.markdown(f"<div style='white-space:pre-wrap; color:#333333;'>{highlight_mentions(post['content'])}</div>", unsafe_allow_html=True)
            
            if can_delete:
                if st.button("🗑️ 삭제", key=f"del_{pid}"):
                    DataManager.delete_row("posts", "id", post['id'], "글 삭제")
                    st.rerun()
            
            # 댓글
            if not comments.empty:
                post_cmts = comments[comments["post_id"].astype(str) == pid]
                for _, c in post_cmts.iterrows():
                    st.markdown(f'<div class="comment-box"><b>{c["author"]}</b> ({c["date"]}): {highlight_mentions(c["content"])}</div>', unsafe_allow_html=True)
            
            with st.form(f"cmt_{pid}"):
                cmt_text = st.text_input("댓글", label_visibility="collapsed", placeholder="댓글 입력...")
                if st.form_submit_button("등록"):
                    if cmt_text.strip():
                        DataManager.append_row("comments", {
                            "post_id": post['id'],
                            "author": username,
                            "content": cmt_text,
                            "date": get_now().strftime("%m-%d %H:%M")
                        }, None, "댓글 등록")
                        st.rerun()

# ============================================================
# [15. 페이지: 직원 관리]
# ============================================================
def page_staff():
    st.subheader("👥 직원 관리")
    
    users = DataManager.load("users", force_refresh=True).data
    if users.empty:
        st.warning("데이터를 불러올 수 없습니다.")
        return
    
    # 승인 대기
    pending = users[~users["approved"].apply(check_approved)]
    if not pending.empty:
        st.info(f"🔔 승인 대기: {len(pending)}명")
        for _, u in pending.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.write(f"**{u['name']}** ({u['username']}) - {u.get('department', '전체')}")
            if col2.button("✅ 승인", key=f"ap_{u['username']}"):
                DataManager.update_row("users", "username", u['username'], {"approved": "True"}, "직원 승인")
                st.rerun()
            if col3.button("❌ 거절", key=f"rj_{u['username']}"):
                DataManager.delete_row("users", "username", u['username'], "직원 거절")
                st.rerun()
    
    st.divider()
    
    # 승인된 직원
    active = users[users["approved"].apply(check_approved)]
    st.write(f"**승인된 직원: {len(active)}명**")
    
    for _, u in active.iterrows():
        if u['username'] == st.session_state['name']:
            continue
        
        with st.expander(f"👤 {u['name']} ({u['role']} / {u.get('department', '전체')})"):
            with st.form(f"edit_{u['username']}"):
                col1, col2 = st.columns(2)
                roles = ["Staff", "Manager", "Master"]
                idx = roles.index(u['role']) if u['role'] in roles else 0
                new_role = col1.selectbox("직급", roles, index=idx)
                new_dept = col2.selectbox("근무지", DEPARTMENTS, 
                                          index=DEPARTMENTS.index(u.get('department', '전체')) if u.get('department', '전체') in DEPARTMENTS else 0)
                
                col3, col4 = st.columns(2)
                if col3.form_submit_button("수정", use_container_width=True):
                    DataManager.update_row("users", "username", u['username'], 
                                           {"role": new_role, "department": new_dept}, "직원 수정")
                    st.success("✅ 수정 완료")
                    time.sleep(0.5)
                    st.rerun()
                if col4.form_submit_button("삭제", use_container_width=True):
                    DataManager.delete_row("users", "username", u['username'], "직원 삭제")
                    st.warning("삭제됨")
                    time.sleep(0.5)
                    st.rerun()

# ============================================================
# [16. 메인]
# ============================================================
def main():
    init_state()
    
    # 자동 로그인
    if not st.session_state.get("logged_in"):
        try:
            if safe_get_cookie("auto_login") == "true":
                uid = safe_get_cookie("uid")
                upw = safe_get_cookie("upw")
                if uid and upw:
                    res = DataManager.load("users")
                    if res.success and not res.data.empty:
                        users = res.data
                        u = users[(users["username"].astype(str) == uid) & (users["password"].astype(str) == upw)]
                        if not u.empty and check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({
                                "logged_in": True,
                                "name": u.iloc[0]["name"],
                                "role": u.iloc[0]["role"],
                                "department": u.iloc[0].get("department", "전체")
                            })
        except:
            pass
    
    # 비로그인
    if not st.session_state.get("logged_in"):
        login_page()
        return
    
    # 로그인 상태
    show_network_status()
    
    # 헤더
    c1, c2, c3, c4 = st.columns([0.8, 4, 0.8, 0.8])
    with c1:
        logo = get_processed_logo("logo.png", icon_size=(35, 35))
        if logo:
            st.image(logo, width=35)
    with c2:
        st.markdown(f"**{st.session_state['name']}**님 ({st.session_state.get('department', '전체')})")
    with c3:
        if st.button("🔍"):
            st.session_state["show_search"] = not st.session_state.get("show_search", False)
            st.rerun()
    with c4:
        if st.button("🔄"):
            DataManager.clear_cache()
            st.rerun()
    
    # 검색
    if st.session_state.get("show_search"):
        show_search()
        st.divider()
    
    # 재시도 버튼
    show_retry_button()
    
    # 메뉴
    menu = ["홈", "인폼", "본점", "작업", "건의", "체크"]
    icons = ["house-fill", "megaphone-fill", "shop", "tools", "chat-dots", "check2-square"]
    
    if st.session_state['role'] == "Master":
        menu.append("관리")
        icons.append("people-fill")
    
    menu.append("로그아웃")
    icons.append("box-arrow-right")
    
    selected = option_menu(
        None, menu, icons=icons,
        default_index=0, orientation="horizontal",
        styles={
            "container": {"padding": "0", "background-color": "#FFF3E0"},
            "nav-link": {"font-size": "10px", "padding": "8px 5px", "color": "#333333"},
            "nav-link-selected": {"background-color": "#8D6E63", "color": "white"}
        }
    )
    
    # 로그아웃
    if selected == "로그아웃":
        st.session_state["logged_in"] = False
        try:
            cookies["auto_login"] = "false"
            cookies.save()
        except:
            pass
        DataManager.clear_cache()
        st.rerun()
    
    # 페이지 라우팅
    if selected == "홈":
        show_dashboard()
    elif selected == "인폼":
        page_inform()
    elif selected == "본점":
        page_board("본점", "🏠")
    elif selected == "작업":
        page_board("작업장", "🏭")
    elif selected == "건의":
        page_board("건의사항", "💡")
    elif selected == "체크":
        page_routine()
    elif selected == "관리":
        page_staff()
    
    # 로그인 팝업
    if st.session_state.get("show_popup_on_login"):
        tasks = get_pending_tasks()
        informs = get_unconfirmed_informs(st.session_state['name'])
        if tasks or informs:
            show_popup(tasks, informs)
        st.session_state["show_popup_on_login"] = False

if __name__ == "__main__":
    main()
