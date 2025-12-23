import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
import pytz
import uuid  # [추가] 고유 Key 생성을 위해 필요
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
    """현재 한국 시간을 반환하는 헬퍼 함수"""
    return datetime.now(KST)

def get_today_str():
    """오늘 날짜 문자열 (YYYY-MM-DD)"""
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
            <link rel="icon" type="image/png" sizes="192x192" href="data:image/png;base64,{icon_base64}">
        </head>
    """, unsafe_allow_html=True)

# [수정됨] CSS: 아이콘 폰트 강제 보호 및 텍스트 폰트 적용
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');

/* 1. 명확한 텍스트 요소에만 폰트 적용 */
h1, h2, h3, h4, h5, h6, p, label, textarea, input, button, .stMarkdown, .stText, .stTextInput, .stTextArea, .stSelectbox {
    font-family: 'Noto Sans KR', sans-serif !important;
    color: #333333 !important;
}

/* 2. Expander 아이콘이 깨지지 않도록 폰트 재설정 방지 */
[data-testid="stExpanderToggleIcon"] {
    font-family: "Material Symbols Rounded", "Material Icons" !important;
    color: #333333 !important;
}

/* 버튼 스타일 */
.stButton > button {
    background-color: #8D6E63 !important; 
    color: white !important; 
    border-radius: 12px; 
    border: none;
    padding: 0.5rem; 
    font-weight: bold; 
    width: 100%; 
    transition: 0.3s;
}
.stButton > button:hover { background-color: #6D4C41 !important; color: #FFF8E1 !important; }

.confirm-btn > button { background-color: #2E7D32 !important; }
.retry-btn > button { background-color: #E65100 !important; }

/* 배경색 */
.stApp { background-color: #FFF3E0; }

/* 헤더 숨김 */
header { background-color: transparent !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }

/* 네비게이션 선택 스타일 */
.nav-link-selected { background-color: #8D6E63 !important; color: white !important; }

/* 카드 스타일 */
.dashboard-card {
    background: white;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.dashboard-card-urgent { border-left: 4px solid #D32F2F; }
.dashboard-card-warning { border-left: 4px solid #FFA000; }
.dashboard-card-success { border-left: 4px solid #388E3C; }

/* 배지 */
.urgent-badge { background: #D32F2F; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
.normal-badge { background: #757575; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }

.inform-card { border: 1px solid #ddd; padding: 15px; border-radius: 10px; background-color: white; margin-bottom: 10px; }
.inform-card-urgent { border: 2px solid #D32F2F; background-color: #FFEBEE; }

.mention { background: #E3F2FD; color: #1565C0; padding: 1px 4px; border-radius: 4px; font-weight: 500; }
.logo-title-container { display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.logo-title-container h1 { margin: 0 0 0 10px; font-size: 1.8rem; }
.network-status { position: fixed; top: 60px; right: 10px; padding: 8px 12px; border-radius: 8px; font-size: 0.85rem; z-index: 1000; }
.network-error { background: #FFE0B2; color: #E65100; }
.comment-box { background: #F5F5F5; padding: 8px 12px; border-radius: 8px; margin: 5px 0; color: #333333 !important; }
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
    if cookies is None:
        return None
    try:
        return cookies.get(key)
    except Exception:
        return None

# ============================================================
# [5. 데이터 로드/저장]
# ============================================================
class DataManager:
    @staticmethod
    def _is_cache_valid(key: str) -> bool:
        cache_time = st.session_state.get("cache_time", {}).get(key)
        if cache_time is None: return False
        return (get_now() - cache_time).total_seconds() < 60
    
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
        if not force_refresh:
            cached = DataManager._get_from_cache(key)
            if cached is not None: return LoadResult(data=cached, success=True)
        
        max_retries = 3
        last_error = ""
        for i in range(max_retries):
            try:
                df = conn.read(worksheet=SHEET_NAMES[key], ttl=0)
                if df is not None:
                    if not df.empty:
                        df.columns = df.columns.str.strip()
                    if not df.empty and key == "users" and "username" not in df.columns:
                        raise ValueError("헤더 오류")
                    DataManager._set_cache(key, df)
                    return LoadResult(data=df, success=True)
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "Quota" in last_error.lower():
                    time.sleep(1 + i)
                    continue
                break
        
        cached = st.session_state.get("data_cache", {}).get(key)
        if cached is not None:
            return LoadResult(data=cached, success=False, error_msg=f"서버 지연 (캐시 사용): {last_error}")
        return LoadResult(data=pd.DataFrame(), success=False, error_msg=f"로드 실패: {last_error}")
    
    @staticmethod
    def save(key: str, df: pd.DataFrame, operation_desc: str = "") -> SaveResult:
        if key == "users":
            cached = st.session_state.get("data_cache", {}).get(key)
            if cached is not None and not cached.empty:
                if len(df) < len(cached) * 0.7 and len(cached) >= 3:
                    return SaveResult(success=False, error_msg="데이터 보호: 대량 삭제 감지됨")
        
        max_retries = 3
        last_error = ""
        for i in range(max_retries):
            try:
                conn.update(worksheet=SHEET_NAMES[key], data=df)
                DataManager._set_cache(key, df)
                return SaveResult(success=True)
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "Quota" in last_error.lower():
                    time.sleep(2)
                    continue
                break
        
        pending = st.session_state.get("pending_saves", [])
        pending.append({
            "key": key, "data": df.to_dict(), "operation": operation_desc,
            "timestamp": get_now().isoformat(), "error": last_error
        })
        st.session_state["pending_saves"] = pending[-10:]
        return SaveResult(success=False, error_msg=last_error)

    @staticmethod
    def append_row(key: str, new_row: dict, id_column: str = "id", operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success and result.data.empty:
                time.sleep(1)
                continue
            current_df = result.data
            
            # ID 중복 방지 (시간 기반 생성인 경우 패스)
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
            time.sleep(1)
        return SaveResult(success=False, error_msg="저장 실패")

    @staticmethod
    def update_row(key: str, match_column: str, match_value: Any, updates: dict, operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(1)
                continue
            current_df = result.data.copy()
            mask = current_df[match_column].astype(str) == str(match_value)
            if not mask.any(): return SaveResult(success=False, error_msg="대상 없음")
            for col, val in updates.items(): current_df.loc[mask, col] = val
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success: return save_result
            time.sleep(1)
        return SaveResult(success=False, error_msg="수정 실패")

    @staticmethod
    def delete_row(key: str, match_column: str, match_value: Any, operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(1)
                continue
            current_df = result.data.copy()
            current_df = current_df[current_df[match_column].astype(str) != str(match_value)]
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success: return save_result
            time.sleep(1)
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
    return re.sub(r'@(\S+)', r'<span class="mention">@\1</span>', str(text))

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
# [7. 비즈니스 로직]
# ============================================================
def get_pending_tasks_list() -> List[dict]:
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
        st.markdown(f'<div class="network-status network-error">⚠️ 저장 대기: {len(pending_saves)}건</div>', unsafe_allow_html=True)

def show_pending_saves_retry():
    pending = st.session_state.get("pending_saves", [])
    if pending:
        with st.expander(f"⚠️ 저장 실패 항목 ({len(pending)}건)", expanded=True):
            for item in pending:
                ts = item['timestamp'][:16]
                st.write(f"• {item['operation']} ({ts})")
            st.markdown('<div class="retry-btn">', unsafe_allow_html=True)
            if st.button("🔄 재시도", key="retry_pending"):
                with st.spinner("재시도 중..."):
                    success, fail = DataManager.retry_pending_saves()
                    if success > 0: st.success(f"✅ {success}건 저장 완료")
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
    with st.spinner("데이터 로딩 중..."):
        pending_tasks = get_pending_tasks_list()
        unconfirmed_informs = get_unconfirmed_inform_list(username)
        new_comments = get_new_comments_count(username)
        mentions = get_mentions_for_user(username)
    
    st.subheader("📊 오늘의 현황")
    c1, c2, c3 = st.columns(3)
    urgent_informs = [i for i in unconfirmed_informs if i.get("priority") == "긴급"]
    
    with c1:
        cls = "dashboard-card-urgent" if urgent_informs else "dashboard-card-warning" if unconfirmed_informs else "dashboard-card-success"
        st.markdown(f'<div class="dashboard-card {cls}"><h3>📢 미확인 인폼</h3><h1>{len(unconfirmed_informs)}</h1></div>', unsafe_allow_html=True)
        if unconfirmed_informs:
            if st.button("확인하기", key="btn_inform", use_container_width=True):
                st.session_state["dashboard_view"] = "inform"
                st.rerun()
    with c2:
        cls = "dashboard-card-warning" if pending_tasks else "dashboard-card-success"
        st.markdown(f'<div class="dashboard-card {cls}"><h3>🔄 미완료 업무</h3><h1>{len(pending_tasks)}</h1></div>', unsafe_allow_html=True)
        if pending_tasks:
            if st.button("업무하기", key="btn_task", use_container_width=True):
                st.session_state["dashboard_view"] = "task"
                st.rerun()
    with c3:
        total = new_comments + len(mentions)
        cls = "dashboard-card-warning" if total else "dashboard-card-success"
        st.markdown(f'<div class="dashboard-card {cls}"><h3>💬 새 알림</h3><h1>{total}</h1></div>', unsafe_allow_html=True)
        if total:
            if st.button("알림보기", key="btn_notif", use_container_width=True):
                st.session_state["dashboard_view"] = "notification"
                st.rerun()
    st.markdown("---")
    view = st.session_state.get("dashboard_view")
    if view:
        if st.button("← 대시보드로 복귀"):
            st.session_state["dashboard_view"] = None
            st.rerun()
        if view == "inform": page_inform()
        elif view == "task": page_routine()
        elif view == "notification":
            st.info("알림 내역")
            if mentions:
                st.write("나를 멘션한 댓글:")
                for m in mentions: st.markdown(f'<div class="comment-box">{m["author"]}: {highlight_mentions(m["content"])}</div>', unsafe_allow_html=True)

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
                    users.columns = users.columns.str.strip() # 헤더 공백 제거
                    
                    users["username"] = users["username"].astype(str)
                    hpw = hash_password(upw)
                    u = users[(users["username"] == uid) & (users["password"].astype(str) == hpw)]
                    
                    if not u.empty:
                        # 승인 여부 체크 (1.0 처리 추가됨)
                        if check_approved(u.iloc[0].get("approved", "False")):
                            st.session_state.update({
                                "logged_in": True,
                                "name": u.iloc[0]["name"],
                                "role": u.iloc[0]["role"],
                                "department": u.iloc[0].get("department", "전체"),
                                "show_popup_on_login": True
                            })
                            if auto:
                                if cookies:
                                    cookies["auto_login"] = "true"
                                    cookies["uid"] = uid
                                    cookies["upw"] = hpw
                                    cookies.save()
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
                            new_row = {
                                "username": nid, "password": hash_password(npw),
                                "name": nname, "role": "Staff", "approved": "False", "department": ndept
                            }
                            new_df = pd.DataFrame([new_row])
                            final_df = pd.concat([users, new_df], ignore_index=True) if not users.empty else new_df
                            DataManager.save("users", final_df, "회원가입")
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
                cls = "inform-card-urgent" if urgent else "inform-card"
                badge = '<span class="urgent-badge">긴급</span>' if urgent else '<span class="normal-badge">일반</span>'
                st.markdown(f'<div class="{cls}"><div style="display:flex;justify-content:space-between;"><b>{n["author"]}</b> {badge}</div><div style="margin-top:10px;white-space:pre-wrap;">{highlight_mentions(n["content"])}</div></div>', unsafe_allow_html=True)
                conf = []
                if not logs.empty: conf = logs[logs["note_id"].astype(str) == nid]["username"].tolist()
                c_btn, c_st = st.columns([1,3])
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
    t1, t2 = st.tabs(["📋 오늘 업무", "📊 기록"])
    
    with t1:
        # 1. 관리자: 업무 추가 (ID 중복 방지를 위해 uuid 사용)
        if st.session_state['role'] in ["Master", "Manager"]:
            with st.expander("➕ 업무 추가"):
                with st.form("nr"):
                    tn = st.text_input("업무명")
                    sd = st.date_input("시작일", value=get_now().date())
                    cy = st.selectbox("주기", ["매일", "매주", "매월"])
                    if st.form_submit_button("추가"):
                        # [수정] ID 충돌 방지: 현재 시간 기반 Unique ID 사용
                        unique_id = int(time.time())
                        DataManager.append_row("routine_def", {
                            "id": unique_id, 
                            "task_name": tn, 
                            "start_date": sd.strftime("%Y-%m-%d"),
                            "cycle_type": cy, 
                            "interval_val": 1
                        }, "id", "업무추가")
                        st.rerun()
        
        # 2. 오늘 할 일
        tasks = get_pending_tasks_list()
        if not tasks: st.success("🎉 오늘의 모든 업무가 완료되었습니다!")
        else:
            for t in tasks:
                st.markdown(f"**{t['task_name']}** ({t['cycle_type']})")
                with st.form(f"do_{t['id']}"):
                    mm = st.text_input("메모")
                    if st.form_submit_button("✅ 완료"):
                        DataManager.append_row("routine_log", {
                            "task_id": t['id'], "done_date": get_today_str(),
                            "worker": name, "memo": mm, "created_at": get_now().strftime("%H:%M")
                        }, None, "완료")
                        st.rerun()
        
        st.markdown("---")
        
        # [신규] 전체 업무 리스트 확인 (탭에서 에러나지 않게 Key 유니크 처리)
        with st.expander("📂 전체 업무 리스트 확인 (주기별 모아보기)"):
            res_defs = DataManager.load("routine_def")
            res_logs = DataManager.load("routine_log")
            
            if res_defs.success and not res_defs.data.empty:
                df_defs = res_defs.data
                df_logs = res_logs.data if res_logs.success else pd.DataFrame()
                
                today_done_ids = []
                if not df_logs.empty:
                    today_logs = df_logs[df_logs["done_date"] == get_today_str()]
                    today_done_ids = today_logs["task_id"].astype(str).tolist()
                
                cycles = ["매일", "매주", "매월", "N일 간격"]
                tabs = st.tabs(cycles)
                
                for i, cy in enumerate(cycles):
                    with tabs[i]:
                        subset = df_defs[df_defs["cycle_type"] == cy]
                        if subset.empty:
                            st.caption("해당 주기의 업무가 없습니다.")
                        else:
                            for idx, row in subset.iterrows():
                                is_done = str(row['id']) in today_done_ids
                                icon = "✅" if is_done else "⬜"
                                status = "(완료됨)" if is_done else "(미완료)"
                                st.markdown(f"""
                                    <div style="padding:10px; border-bottom:1px solid #eee;">
                                        {icon} <b>{row['task_name']}</b> <small style='color:#888;'>{status}</small>
                                        <br><small>시작일: {row['start_date']}</small>
                                    </div>
                                """, unsafe_allow_html=True)

                                # 관리자용 수정/삭제 (Key 중복 방지: ID + Cycle + Index 조합)
                                if st.session_state['role'] in ["Master", "Manager"]:
                                    with st.expander(f"⚙️ 관리 ({row['task_name']})"):
                                        unique_key = f"edit_{row['id']}_{cy}_{i}_{idx}"
                                        with st.form(unique_key):
                                            nn = st.text_input("수정: 업무명", value=row['task_name'])
                                            try:
                                                s_dt = datetime.strptime(str(row['start_date']), "%Y-%m-%d").date()
                                            except:
                                                s_dt = get_now().date()
                                            ns = st.date_input("수정: 시작일", value=s_dt)
                                            
                                            c_idx = cycles.index(row['cycle_type']) if row['cycle_type'] in cycles else 0
                                            nc = st.selectbox("수정: 주기", cycles, index=c_idx)
                                            
                                            c_up, c_del = st.columns(2)
                                            if c_up.form_submit_button("💾 수정"):
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
            m = pd.merge(logs, defs, left_on='task_id', right_on='id', how='left')
            # [수정] 누가 했는지(worker) 잘 보이게 정렬 및 컬럼 선택
            m = m.sort_values('done_date', ascending=False)
            st.dataframe(
                m[['done_date', 'task_name', 'worker', 'memo']], 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "done_date": "날짜",
                    "task_name": "업무명",
                    "worker": "작업자",
                    "memo": "메모"
                }
            )
        else:
            st.info("기록이 없습니다.")

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
    
    # [수정] 쿠키 에러(CookiesNotReady) 완전 방어
    if not st.session_state.get("logged_in"):
        try:
            # 안전하게 쿠키 값 가져오기
            auto_val = safe_get_cookie("auto_login")
            uid_val = safe_get_cookie("uid")
            
            if auto_val == "true" and uid_val:
                res = DataManager.load("users")
                if res.success and not res.data.empty:
                    users = res.data
                    users["username"] = users["username"].astype(str)
                    u = users[users["username"] == uid_val]
                    if not u.empty and check_approved(u.iloc[0]["approved"]):
                        st.session_state.update({
                            "logged_in": True,
                            "name": u.iloc[0]["name"],
                            "role": u.iloc[0]["role"],
                            "department": u.iloc[0].get("department", "전체")
                        })
        except Exception:
            # 어떤 에러가 나더라도 무시하고 로그인 화면으로 유도
            pass

    if not st.session_state.get("logged_in"):
        login_page()
        return

    show_network_status()
    c1, c2, c3, c4 = st.columns([1, 4, 1, 1])
    with c1:
        if processed_icon: st.image(processed_icon, width=35)
    with c2: st.markdown(f"**{st.session_state['name']}**님 ({st.session_state.get('department','전체')})")
    with c3:
        if st.button("🔍", key="search"): 
            st.session_state["show_search"] = not st.session_state.get("show_search", False)
            st.rerun()
    with c4:
        if st.button("🔄", key="refresh"): 
            DataManager.clear_cache()
            st.rerun()

    if st.session_state.get("show_search"): 
        show_search()
        st.divider()
    
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
