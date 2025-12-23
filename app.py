import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
import uuid
import pytz
from datetime import datetime, date, timedelta
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection
from streamlit_cookies_manager import CookieManager
from PIL import Image
from enum import Enum
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

class UserRole(Enum):
    MASTER = "Master"
    MANAGER = "Manager"
    STAFF = "Staff"

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
# [1. 데이터 클래스 및 상태 관리]
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

class AppState:
    @staticmethod
    def init():
        defaults = {
            "logged_in": False,
            "name": "",
            "role": "",
            "department": "전체",
            "show_popup_on_login": False,
            "pending_saves": [],
            "last_error": None,
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
    except Exception:
        return None

# ============================================================
# [3. 페이지 설정 및 스타일]
# ============================================================
st.set_page_config(
    page_title="조각달 업무수첩", 
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');

/* 폰트 적용 (텍스트 요소만) */
h1, h2, h3, h4, h5, h6, p, label, textarea, input, button, .stMarkdown, .stText, .stTextInput, .stTextArea, .stSelectbox {
    font-family: 'Noto Sans KR', sans-serif !important;
    color: #333333 !important;
}

/* 아이콘 폰트 보호 */
.material-icons, [data-testid="stExpanderToggleIcon"] {
    font-family: inherit !important;
}

/* 버튼 */
.stButton > button {
    background-color: #8D6E63 !important; 
    color: white !important; 
    border-radius: 12px; 
    border: none;
    padding: 0.5rem; 
    font-weight: bold; 
    width: 100%; 
}
.confirm-btn > button { background-color: #2E7D32 !important; }
.retry-btn > button { background-color: #E65100 !important; }

/* 배경 및 헤더 */
.stApp { background-color: #FFF3E0; }
header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stStatusWidget"] { display: none; }

/* 요약 카드 (가로 스크롤) */
.summary-container {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 15px;
    overflow-x: auto;
}
.summary-card {
    flex: 1;
    background: white;
    border-radius: 12px;
    padding: 12px;
    text-align: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    min-width: 90px;
}
.summary-title { font-size: 0.8rem; color: #666; margin-bottom: 5px; }
.summary-value { font-size: 1.5rem; font-weight: bold; color: #333; }
.summary-alert { color: #D32F2F !important; }

/* 인폼 리스트 */
.inform-item {
    background: white;
    border-left: 4px solid #8D6E63;
    padding: 10px;
    margin-bottom: 8px;
    border-radius: 4px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.inform-urgent { border-left-color: #D32F2F; background-color: #FFEBEE; }

/* 로고 및 상태 */
.logo-title-container { display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.logo-title-container h1 { margin: 0 0 0 10px; font-size: 1.5rem; color: #4E342E; }
.network-status { position: fixed; top: 10px; right: 10px; padding: 5px 10px; border-radius: 20px; font-size: 0.75rem; z-index: 9999; background: #FFEBEE; color: #C62828; border: 1px solid #FFCDD2; }
button[data-baseweb="tab"] { font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# [4. 쿠키 및 DB 연결]
# ============================================================
try:
    cookies = CookieManager()
except:
    cookies = None

conn = st.connection("gsheets", type=GSheetsConnection)

def safe_get_cookie(key):
    if cookies is None: return None
    try: return cookies.get(key)
    except: return None

# ============================================================
# [5. 데이터 로드/저장 (게으른 로딩 적용)]
# ============================================================
class DataManager:
    # [속도 개선] 캐시 유지 시간을 10분으로 증가 (자주 로딩 방지)
    CACHE_TTL = 600 
    
    @staticmethod
    def _is_cache_valid(key: str) -> bool:
        cache_time = st.session_state.get("cache_time", {}).get(key)
        if cache_time is None: return False
        return (get_now() - cache_time).total_seconds() < DataManager.CACHE_TTL
    
    @staticmethod
    def _get_from_cache(key: str) -> Optional[pd.DataFrame]:
        if DataManager._is_cache_valid(key):
            return st.session_state.get("data_cache", {}).get(key)
        return None
    
    @staticmethod
    def _set_cache(key: str, df: pd.DataFrame):
        if "data_cache" not in st.session_state: st.session_state["data_cache"] = {}
        if "cache_time" not in st.session_state: st.session_state["cache_time"] = {}
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
        """
        [속도 개선] 
        1. 캐시가 있으면 무조건 캐시 반환 (0초)
        2. 없으면 구글 시트 로드
        """
        if not force_refresh:
            cached = DataManager._get_from_cache(key)
            if cached is not None: return LoadResult(data=cached, success=True)
        
        for i in range(3):
            try:
                # [참고] 데이터가 많아지면 여기서 느려짐 -> 차후 '보관함' 시트 분리 필요
                df = conn.read(worksheet=SHEET_NAMES[key], ttl=0)
                if df is not None:
                    if not df.empty:
                        df.columns = df.columns.str.strip()
                    # 헤더 검증
                    if not df.empty and key == "users" and "username" not in df.columns:
                        raise ValueError("헤더 오류")
                    DataManager._set_cache(key, df)
                    return LoadResult(data=df, success=True)
            except Exception:
                time.sleep(0.5)
                continue
            break
        
        cached = st.session_state.get("data_cache", {}).get(key)
        if cached is not None:
            return LoadResult(data=cached, success=False, error_msg="캐시 사용 (통신 실패)")
        return LoadResult(data=pd.DataFrame(), success=False, error_msg="로드 실패")
    
    @staticmethod
    def save(key: str, df: pd.DataFrame, operation_desc: str = "") -> SaveResult:
        # 안전장치
        if key == "users":
            cached = st.session_state.get("data_cache", {}).get(key)
            if cached is not None and not cached.empty:
                if len(df) < len(cached) * 0.5:
                    return SaveResult(success=False, error_msg="데이터 보호: 대량 삭제 감지")
        
        for i in range(3):
            try:
                conn.update(worksheet=SHEET_NAMES[key], data=df)
                DataManager._set_cache(key, df) # [중요] 저장 즉시 내 캐시 갱신 (리로드 방지)
                return SaveResult(success=True)
            except Exception:
                time.sleep(0.5)
                continue
            break
        
        pending = st.session_state.get("pending_saves", [])
        pending.append({
            "key": key, "data": df.to_dict(), "operation": operation_desc,
            "timestamp": get_now().isoformat()
        })
        st.session_state["pending_saves"] = pending[-10:]
        return SaveResult(success=False, error_msg="저장 실패")

    # CRUD 메서드들 (생략 없이 유지)
    @staticmethod
    def append_row(key: str, new_row: dict, id_column: str = "id", operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success and result.data.empty:
                time.sleep(0.5)
                continue
            current_df = result.data
            
            if id_column and id_column not in new_row:
                if current_df.empty: new_row[id_column] = 1
                else:
                    try:
                        max_id = pd.to_numeric(current_df[id_column], errors='coerce').fillna(0).max()
                        new_row[id_column] = int(max_id) + 1
                    except: new_row[id_column] = len(current_df) + 1
            
            new_df = pd.DataFrame([new_row])
            updated_df = pd.concat([current_df, new_df], ignore_index=True) if not current_df.empty else new_df
            save_result = DataManager.save(key, updated_df, operation_desc)
            if save_result.success: return save_result
            time.sleep(0.5)
        return SaveResult(success=False, error_msg="저장 실패")

    @staticmethod
    def update_row(key: str, match_column: str, match_value: Any, updates: dict, operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(0.5)
                continue
            current_df = result.data.copy()
            mask = current_df[match_column].astype(str) == str(match_value)
            if not mask.any(): return SaveResult(success=False, error_msg="대상 없음")
            for col, val in updates.items(): current_df.loc[mask, col] = val
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success: return save_result
            time.sleep(0.5)
        return SaveResult(success=False, error_msg="수정 실패")

    @staticmethod
    def delete_row(key: str, match_column: str, match_value: Any, operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(0.5)
                continue
            current_df = result.data.copy()
            current_df = current_df[current_df[match_column].astype(str) != str(match_value)]
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success: return save_result
            time.sleep(0.5)
        return SaveResult(success=False, error_msg="삭제 실패")
    
    @staticmethod
    def retry_pending_saves() -> Tuple[int, int]:
        pending = st.session_state.get("pending_saves", [])
        if not pending: return (0, 0)
        success_count = 0
        still_pending = []
        for item in pending:
            df = pd.DataFrame(item["data"])
            result = DataManager.save(item["key"], df, item["operation"])
            if result.success: success_count += 1
            else: still_pending.append(item)
        st.session_state["pending_saves"] = still_pending
        return (success_count, len(still_pending))

# ============================================================
# [6. 유틸리티 함수]
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode()).hexdigest()

def check_approved(val) -> bool:
    v = str(val).strip().lower()
    return v in ["true", "1", "1.0", "yes", "y", "t"]

def highlight_mentions(text: str) -> str:
    import re
    return re.sub(r'@(\S+)', r'<span style="color:#1565C0; font-weight:bold;">@\1</span>', str(text))

def is_task_due(start_date_str, cycle_type, interval_val) -> bool:
    try:
        if pd.isna(start_date_str) or str(start_date_str).strip() == "": return False
        start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
        today = get_now().date()
        if today < start_date: return False
        delta_days = (today - start_date).days
        if cycle_type == "매일": return True
        elif cycle_type == "매주": return delta_days % 7 == 0
        elif cycle_type == "매월": return today.day == start_date.day
        elif cycle_type == "N일 간격": return delta_days % int(interval_val) == 0
        return False
    except: return False

# ============================================================
# [7. 비즈니스 로직 (Lazy Loading)]
# ============================================================
def get_pending_tasks_list() -> List[dict]:
    # 필요한 것만 로드
    result_def = DataManager.load("routine_def")
    result_log = DataManager.load("routine_log")
    if not result_def.success: return []
    defs, logs = result_def.data, result_log.data
    if defs.empty: return []
    today_str = get_today_str()
    pending = []
    for _, task in defs.iterrows():
        if is_task_due(task.get("start_date"), task.get("cycle_type"), task.get("interval_val", 1)):
            is_done = False
            if not logs.empty:
                done = logs[(logs["task_id"].astype(str) == str(task["id"])) & (logs["done_date"] == today_str)]
                if not done.empty: is_done = True
            if not is_done: pending.append(dict(task))
    return pending

def get_unconfirmed_inform_list(username: str) -> List[dict]:
    # 필요한 것만 로드
    res_informs = DataManager.load("inform_notes")
    res_logs = DataManager.load("inform_logs")
    if not res_informs.success or res_informs.data.empty: return []
    informs = res_informs.data
    logs = res_logs.data if res_logs.success else pd.DataFrame()
    today_str = get_today_str()
    today_informs = informs[informs["target_date"] == today_str]
    if today_informs.empty: return []
    unconfirmed = []
    for _, note in today_informs.iterrows():
        is_checked = False
        if not logs.empty:
            is_checked = not logs[(logs["note_id"].astype(str) == str(note["id"])) & (logs["username"] == username)].empty
        if not is_checked: unconfirmed.append(dict(note))
    return unconfirmed

def get_new_comments_count(username: str) -> int:
    # 게시판 관련 데이터는 홈 화면에서 알림 숫자만 필요하지만, 
    # 로직상 posts와 comments를 다 읽어야 함. 
    # 단, 홈 화면 로딩 시에는 이것을 '비동기'나 '나중에' 할 수 없으므로 
    # 최소한의 캐싱을 믿고 진행.
    res_posts = DataManager.load("posts")
    res_comments = DataManager.load("comments")
    if not res_posts.success or not res_comments.success: return 0
    posts, comments = res_posts.data, res_comments.data
    if posts.empty or comments.empty: return 0
    my_posts = posts[posts["author"] == username]["id"].astype(str).tolist()
    today_mmdd = get_now().strftime("%m-%d")
    new_comments = comments[
        (comments["post_id"].astype(str).isin(my_posts)) &
        (comments["date"].str.contains(today_mmdd, na=False)) &
        (comments["author"] != username)
    ]
    return len(new_comments)

def get_mentions_for_user(username: str) -> List[dict]:
    comments = DataManager.load("comments").data
    if comments.empty: return []
    mentions = []
    for _, c in comments.iterrows():
        if f"@{username}" in str(c.get("content", "")): mentions.append(dict(c))
    return mentions

def search_content(query: str) -> Dict[str, List[dict]]:
    results = {"inform": [], "posts": []}
    query = query.lower().strip()
    if not query: return results
    informs = DataManager.load("inform_notes").data
    if not informs.empty:
        for _, row in informs.iterrows():
            if query in str(row.get("content", "")).lower(): results["inform"].append(dict(row))
    posts = DataManager.load("posts").data
    if not posts.empty:
        for _, row in posts.iterrows():
            if query in str(row.get("title", "")).lower() or query in str(row.get("content", "")).lower():
                results["posts"].append(dict(row))
    return results

# ============================================================
# [8. UI 컴포넌트]
# ============================================================
def show_network_status():
    pending_saves = st.session_state.get("pending_saves", [])
    if pending_saves:
        st.markdown(f'<div class="network-status network-error">📡 저장 대기: {len(pending_saves)}</div>', unsafe_allow_html=True)

def show_pending_saves_retry():
    pending = st.session_state.get("pending_saves", [])
    if pending:
        with st.expander(f"📡 저장 실패 항목 ({len(pending)}건)", expanded=True):
            for item in pending:
                ts = item['timestamp'][5:16]
                st.write(f"- {item['operation']} ({ts})")
            st.markdown('<div class="retry-btn">', unsafe_allow_html=True)
            if st.button("🔄 재시도", key="retry_pending"):
                with st.spinner("재시도 중..."):
                    success, fail = DataManager.retry_pending_saves()
                    if success > 0: st.success(f"✅ {success}건 완료")
                    if fail > 0: st.error(f"❌ {fail}건 실패")
                    time.sleep(1)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

@st.dialog("🚨 중요 알림")
def show_notification_popup(tasks: List[dict], inform_notes: List[dict]):
    if inform_notes:
        urgent = [n for n in inform_notes if n.get("priority") == "긴급"]
        if urgent:
            st.error(f"🚨 **긴급 필독 ({len(urgent)}건)**")
            for note in urgent: st.markdown(f"**📌 {note['content'][:50]}...**")
    if tasks:
        st.info(f"🔄 **오늘의 반복 업무 ({len(tasks)}건)**")
        for t in tasks: st.write(f"• {t['task_name']}")
    if st.button("확인", use_container_width=True): st.rerun()

def show_dashboard():
    username = st.session_state['name']
    
    # [속도 개선] 스피너 제거하고 바로 데이터 로드
    # 캐시가 있으면 0초, 없으면 순차 로드 (prefetch 제거로 초기 부하 분산)
    pending_tasks = get_pending_tasks_list()
    unconfirmed_informs = get_unconfirmed_inform_list(username)
    new_comments = get_new_comments_count(username)
    mentions = get_mentions_for_user(username)
    
    st.subheader("📊 오늘의 현황")
    
    urgent_cnt = len([i for i in unconfirmed_informs if i.get("priority") == "긴급"])
    inform_color = "summary-alert" if urgent_cnt > 0 else ""
    
    st.markdown(f"""
        <div class="summary-container">
            <div class="summary-card">
                <div class="summary-title">📢 미확인 인폼</div>
                <div class="summary-value {inform_color}">{len(unconfirmed_informs)}</div>
            </div>
            <div class="summary-card">
                <div class="summary-title">🔄 미완료 업무</div>
                <div class="summary-value">{len(pending_tasks)}</div>
            </div>
            <div class="summary-card">
                <div class="summary-title">💬 새 알림</div>
                <div class="summary-value">{new_comments + len(mentions)}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    if c1.button("📢 인폼 확인", use_container_width=True):
        st.session_state["dashboard_view"] = "inform"
        st.rerun()
    if c2.button("🔄 업무 처리", use_container_width=True):
        st.session_state["dashboard_view"] = "task"
        st.rerun()
    if c3.button("💬 알림 확인", use_container_width=True):
        st.session_state["dashboard_view"] = "notification"
        st.rerun()

    st.markdown("---")
    view = st.session_state.get("dashboard_view")
    if view:
        if st.button("↩️ 대시보드로 접기"):
            st.session_state["dashboard_view"] = None
            st.rerun()
        
        if view == "inform": page_inform()
        elif view == "task": page_routine()
        elif view == "notification":
            st.info("알림 내역")
            if mentions:
                st.write("나를 멘션한 댓글:")
                for m in mentions: st.markdown(f'- {m["content"]}')
            elif new_comments:
                st.write("새 댓글이 있습니다.")
            else:
                st.write("새로운 알림이 없습니다.")

def show_search():
    st.subheader("🔍 검색")
    query = st.text_input("검색어 입력")
    if query:
        with st.spinner("검색 중..."): res = search_content(query)
        st.write(f"결과: {len(res['inform']) + len(res['posts'])}건")
        if res['inform']:
            with st.expander(f"인폼 ({len(res['inform'])})"):
                for i in res['inform']: st.write(f"[{i['target_date']}] {i['content']}")
        if res['posts']:
            with st.expander(f"게시글 ({len(res['posts'])})"):
                for p in res['posts']: st.write(f"[{p['board_type']}] {p['title']} - {p['author']}")

# ============================================================
# [9. 페이지 함수]
# ============================================================
def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    processed_logo = get_processed_logo("logo.png", icon_size=(80, 80))
    if processed_logo:
        st.markdown(f"""
            <div class="logo-title-container">
                <img src="data:image/png;base64,{image_to_base64(processed_logo)}" style="max-height: 80px;">
                <h1>업무수첩</h1>
            </div>
        """, unsafe_allow_html=True)
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
                    users.columns = users.columns.str.strip()
                    users["username"] = users["username"].astype(str)
                    hpw = hash_password(upw)
                    u = users[(users["username"] == uid) & (users["password"].astype(str) == hpw)]
                    
                    if not u.empty:
                        if check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({
                                "logged_in": True,
                                "name": u.iloc[0]["name"],
                                "role": u.iloc[0]["role"],
                                "department": u.iloc[0].get("department", "전체"),
                                "show_popup_on_login": True
                            })
                            if auto and cookies:
                                try:
                                    cookies["auto_login"] = "true"
                                    cookies["uid"] = uid
                                    cookies["upw"] = hpw
                                    cookies.save()
                                except: pass
                            st.rerun()
                        else: st.warning("⏳ 승인 대기 중입니다.")
                    else: st.error("정보가 일치하지 않습니다.")
                else: st.error("서버 연결 실패")
    
    with tab2:
        with st.form("signup"):
            nid = st.text_input("아이디")
            npw = st.text_input("비밀번호", type="password")
            nname = st.text_input("이름")
            ndept = st.selectbox("근무지", DEPARTMENTS)
            if st.form_submit_button("신청", use_container_width=True):
                if nid and npw and nname:
                    res = DataManager.load("users", force_refresh=True)
                    if res.success:
                        users = res.data
                        if not users.empty: users.columns = users.columns.str.strip()
                        if not users.empty and nid in users["username"].astype(str).values:
                            st.error("이미 있는 아이디입니다.")
                        else:
                            new_row = {"username": nid, "password": hash_password(npw), "name": nname, "role": "Staff", "approved": "False", "department": ndept}
                            DataManager.append_row("users", new_row, None, "가입신청")
                            st.success("신청 완료! 승인을 기다려주세요.")
                    else: st.error("오류")
                else: st.warning("모두 입력해주세요")

def page_inform():
    st.subheader("📢 인폼노트")
    if "inform_date" not in st.session_state: st.session_state["inform_date"] = get_now().date()
    
    c1, c2, c3 = st.columns([1,2,1])
    with c1:
        if st.button("◀", use_container_width=True): st.session_state["inform_date"] -= timedelta(days=1); st.rerun()
    with c2: st.session_state["inform_date"] = st.date_input("날짜", value=st.session_state["inform_date"], label_visibility="collapsed")
    with c3:
        if st.button("▶", use_container_width=True): st.session_state["inform_date"] += timedelta(days=1); st.rerun()
            
    sel_date = st.session_state["inform_date"].strftime("%Y-%m-%d")
    name = st.session_state['name']
    
    if st.session_state['role'] in ["Master", "Manager"]:
        with st.expander("📝 작성"):
            with st.form("new_inf"):
                td = st.date_input("날짜", value=st.session_state["inform_date"])
                pr = st.radio("중요도", ["일반", "긴급"], horizontal=True)
                ct = st.text_area("내용")
                if st.form_submit_button("등록", use_container_width=True):
                    DataManager.append_row("inform_notes", {
                        "target_date": td.strftime("%Y-%m-%d"), "content": ct,
                        "author": name, "priority": pr, "created_at": get_now().strftime("%Y-%m-%d %H:%M")
                    }, "id", "인폼")
                    st.rerun()

    res_n = DataManager.load("inform_notes")
    res_l = DataManager.load("inform_logs")
    if res_n.success and not res_n.data.empty:
        notes = res_n.data
        daily = notes[notes["target_date"] == sel_date]
        if daily.empty: st.info("인폼 없음")
        else:
            daily = sorted(daily.to_dict('records'), key=lambda x: 0 if x.get('priority') == '긴급' else 1)
            logs = res_l.data if res_l.success else pd.DataFrame()
            for n in daily:
                nid = str(n['id'])
                urgent = n.get('priority') == '긴급'
                cls = "inform-item inform-urgent" if urgent else "inform-item"
                badge = "🚨 긴급" if urgent else ""
                
                st.markdown(f"""
                    <div class="{cls}">
                        <div style="font-weight:bold; margin-bottom:5px;">{n["author"]} <span style="color:red">{badge}</span></div>
                        <div style="white-space:pre-wrap;">{highlight_mentions(n["content"])}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                conf = []
                if not logs.empty: conf = logs[logs["note_id"].astype(str) == nid]["username"].tolist()
                c_btn, c_st = st.columns([1,2])
                with c_btn:
                    if name not in conf:
                        if st.button("확인함 ✅", key=f"ok_{nid}"):
                            DataManager.append_row("inform_logs", {"note_id": nid, "username": name, "confirmed_at": get_now().strftime("%m-%d %H:%M")}, None, "확인")
                            st.rerun()
                    else: st.success("확인됨")
                with c_st:
                    with st.expander(f"확인자 ({len(conf)})"): st.write(", ".join(conf) if conf else "-")

def page_routine():
    st.subheader("🔄 업무 체크")
    name = st.session_state['name']
    t1, t2 = st.tabs(["📋 오늘 업무", "📊 기록/관리"])
    
    with t1:
        tasks = get_pending_tasks_list()
        if not tasks: st.success("🎉 오늘의 업무를 모두 완료했습니다!")
        else:
            for t in tasks:
                st.markdown(f"**{t['task_name']}** <small>({t['cycle_type']})</small>", unsafe_allow_html=True)
                with st.form(f"do_{t['id']}"):
                    mm = st.text_input("메모", placeholder="특이사항")
                    if st.form_submit_button("완료 ✅", use_container_width=True):
                        DataManager.append_row("routine_log", {
                            "task_id": t['id'], "done_date": get_today_str(),
                            "worker": name, "memo": mm, "created_at": get_now().strftime("%H:%M")
                        }, None, "완료")
                        st.rerun()
                st.divider()

    with t2:
        if st.session_state['role'] in ["Master", "Manager"]:
            with st.expander("➕ 새 업무 추가"):
                with st.form("nr"):
                    tn = st.text_input("업무명")
                    sd = st.date_input("시작일", value=get_now().date())
                    cy = st.selectbox("주기", ["매일", "매주", "매월"])
                    if st.form_submit_button("추가"):
                        new_id = int(time.time())
                        DataManager.append_row("routine_def", {
                            "id": new_id, "task_name": tn, "start_date": sd.strftime("%Y-%m-%d"),
                            "cycle_type": cy, "interval_val": 1
                        }, "id", "추가")
                        st.rerun()
        
        res_def = DataManager.load("routine_def")
        if res_def.success and not res_def.data.empty:
            df = res_def.data
            cycles = ["매일", "매주", "매월"]
            tabs = st.tabs(cycles)
            for i, cy in enumerate(cycles):
                with tabs[i]:
                    sub = df[df['cycle_type'] == cy]
                    for _, r in sub.iterrows():
                        col_txt, col_btn = st.columns([3, 1])
                        col_txt.write(f"**{r['task_name']}** ({r['start_date']}~)")
                        if st.session_state['role'] in ["Master", "Manager"]:
                            if col_btn.button("삭제", key=f"del_{r['id']}_{cy}"):
                                DataManager.delete_row("routine_def", "id", r['id'], "삭제")
                                st.rerun()
        
        st.divider()
        st.caption("📋 최근 완료 기록")
        logs = DataManager.load("routine_log").data
        defs = DataManager.load("routine_def").data
        if not logs.empty and not defs.empty:
            logs['task_id'] = logs['task_id'].astype(str)
            defs['id'] = defs['id'].astype(str)
            m = pd.merge(logs, defs, left_on='task_id', right_on='id', how='left')
            st.dataframe(
                m[['done_date', 'task_name', 'worker', 'memo']].sort_values('done_date', ascending=False).head(50),
                hide_index=True, use_container_width=True
            )

def page_board(bn, icon):
    st.subheader(f"{icon} {bn}")
    name = st.session_state['name']
    
    if st.session_state['role'] in ["Master", "Manager"] or bn == "건의사항":
        with st.expander("글쓰기"):
            with st.form(f"w_{bn}"):
                tt = st.text_input("제목")
                ct = st.text_area("내용")
                if st.form_submit_button("등록", use_container_width=True):
                    DataManager.append_row("posts", {
                        "board_type": bn, "title": tt, "content": ct,
                        "author": name, "date": get_now().strftime("%Y-%m-%d")
                    }, "id", "글쓰기")
                    st.rerun()
    
    posts = DataManager.load("posts").data
    if not posts.empty and "board_type" in posts.columns:
        mp = posts[posts["board_type"].astype(str).str.strip() == bn].sort_values("id", ascending=False)
        for _, r in mp.iterrows():
            with st.expander(f"{r['title']} ({r['author']})"):
                st.write(r['content'])
                if st.session_state['role'] == "Master" or r['author'] == name:
                    if st.button("삭제", key=f"del_{r['id']}"):
                        DataManager.delete_row("posts", "id", r['id'], "삭제")
                        st.rerun()
                
                cmts = DataManager.load("comments").data
                if not cmts.empty:
                    for _, c in cmts[cmts["post_id"].astype(str) == str(r['id'])].iterrows():
                        st.caption(f"{c['author']}: {c['content']}")
                
                with st.form(f"c_{r['id']}"):
                    ctxt = st.text_input("댓글", label_visibility="collapsed")
                    if st.form_submit_button("등록"):
                        DataManager.append_row("comments", {"post_id": r['id'], "author": name, "content": ctxt, "date": get_now().strftime("%m-%d %H:%M")}, None, "댓글")
                        st.rerun()

def page_staff_mgmt():
    st.subheader("👥 직원 관리")
    users = DataManager.load("users", force_refresh=True).data
    if users.empty: return

    pending = users[users["approved"].apply(lambda x: not check_approved(x))]
    if not pending.empty:
        st.info(f"승인 대기: {len(pending)}명")
        for _, u in pending.iterrows():
            c1, c2, c3 = st.columns([2,1,1])
            c1.write(f"{u['name']} ({u['username']})")
            if c2.button("승인", key=f"ap_{u['username']}"):
                DataManager.update_row("users", "username", u['username'], {"approved": "True"}, "승인")
                st.rerun()
            if c3.button("거절", key=f"rj_{u['username']}"):
                DataManager.delete_row("users", "username", u['username'], "거절")
                st.rerun()
    st.divider()
    
    active = users[users["approved"].apply(check_approved)]
    for _, u in active.iterrows():
        if u['username'] == st.session_state['name']: continue
        with st.expander(f"{u['name']} ({u['role']})"):
            with st.form(f"ed_{u['username']}"):
                nr = st.selectbox("직급", ["Master", "Manager", "Staff"], index=["Master", "Manager", "Staff"].index(u['role']))
                if st.form_submit_button("수정"):
                    DataManager.update_row("users", "username", u['username'], {"role": nr}, "수정")
                    st.rerun()

# ============================================================
# [10. 메인 앱]
# ============================================================
def main():
    AppState.init()
    
    # 쿠키 에러 방지
    if not st.session_state.get("logged_in"):
        try:
            if safe_get_cookie("auto_login") == "true":
                uid = safe_get_cookie("uid")
                if uid:
                    res = DataManager.load("users")
                    if res.success and not res.data.empty:
                        users = res.data
                        u = users[users["username"] == uid]
                        if not u.empty and check_approved(u.iloc[0]["approved"]):
                            st.session_state.update({
                                "logged_in": True,
                                "name": u.iloc[0]["name"],
                                "role": u.iloc[0]["role"],
                                "department": u.iloc[0].get("department", "전체")
                            })
        except: pass

    if not st.session_state.get("logged_in"):
        login_page()
        return

    show_network_status()
    
    # 상단 로고 및 검색 (모바일에서 한 줄로)
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1:
        if processed_icon: st.image(processed_icon, width=35)
    with c2: st.markdown(f"**{st.session_state['name']}** ({st.session_state.get('department','전체')})")
    with c3:
        if st.button("🔄", key="refresh"): 
            DataManager.clear_cache()
            st.rerun()

    show_pending_saves_retry()
    
    menu = ["홈", "인폼", "본점", "작업", "건의", "체크", "로그아웃"]
    icons = ["house-fill", "megaphone-fill", "shop", "tools", "chat-dots", "check2-square", "box-arrow-right"]
    if st.session_state['role'] == "Master":
        menu.insert(-1, "관리")
        icons.insert(-1, "people-fill")

    m = option_menu(None, menu, icons=icons, menu_icon="cast", default_index=0, orientation="horizontal",
        styles={"container": {"padding": "0!important", "background-color": "#FFF3E0"}, "nav-link": {"font-size": "10px", "padding": "8px 5px"}})

    if m == "로그아웃":
        st.session_state["logged_in"] = False
        try:
            if cookies:
                cookies["auto_login"] = "false"
                cookies.save()
        except: pass
        st.rerun()
    elif m == "홈": show_dashboard()
    elif m == "인폼": page_inform()
    elif m == "체크": page_routine()
    elif m == "본점": page_board("본점", "🏠")
    elif m == "작업": page_board("작업장", "🏭")
    elif m == "건의": page_board("건의사항", "💡")
    elif m == "관리": page_staff_mgmt()

    if st.session_state.get("show_popup_on_login"):
        pt = get_pending_tasks_list()
        uc = get_unconfirmed_inform_list(st.session_state['name'])
        if pt or uc: show_notification_popup(pt, uc)
        st.session_state["show_popup_on_login"] = False

if __name__ == "__main__":
    main()
