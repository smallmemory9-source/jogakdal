import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
import secrets
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
class UserRole(Enum):
    MASTER = "Master"
    MANAGER = "Manager"
    STAFF = "Staff"

class Priority(Enum):
    URGENT = "긴급"
    NORMAL = "일반"

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
CACHE_TTL = 300  # 5분 캐시

# ============================================================
# [1. 데이터 클래스 및 상태 관리]
# ============================================================
@dataclass
class LoadResult:
    """데이터 로드 결과 - 실패와 빈 데이터 구분"""
    data: pd.DataFrame
    success: bool
    error_msg: str = ""

@dataclass
class SaveResult:
    """저장 결과"""
    success: bool
    error_msg: str = ""

class AppState:
    """세션 상태 관리 헬퍼"""
    @staticmethod
    def init():
        defaults = {
            "logged_in": False,
            "name": "",
            "role": "",
            "department": "전체",
            "show_popup_on_login": False,
            "pending_saves": [],  # 실패한 저장 작업 큐
            "last_error": None,
            "data_cache": {},  # 로컬 캐시
            "cache_time": {},  # 캐시 시간
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v
    
    @staticmethod
    def get(key, default=None):
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key, value):
        st.session_state[key] = value
    
    @staticmethod
    def update(**kwargs):
        st.session_state.update(kwargs)

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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; color: #4E342E; }
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

.retry-btn > button { background-color: #E65100 !important; }
.retry-btn > button:hover { background-color: #BF360C !important; }

.comment-box { 
    background-color: #F5F5F5; padding: 10px; border-radius: 8px; 
    margin-top: 5px; font-size: 0.9rem; 
}

.logo-title-container {
    display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
}
.logo-title-container h1 { margin: 0 0 0 10px; font-size: 1.8rem; }

.container-xxl { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }

.streamlit-expanderHeader { font-weight: bold; color: #4E342E; }

/* 대시보드 카드 스타일 */
.dashboard-card {
    background: white;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.dashboard-card-urgent {
    border-left: 4px solid #D32F2F;
}
.dashboard-card-warning {
    border-left: 4px solid #FFA000;
}
.dashboard-card-success {
    border-left: 4px solid #388E3C;
}

/* 긴급 인폼 스타일 */
.urgent-badge {
    background: #D32F2F;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: bold;
}
.normal-badge {
    background: #757575;
    color: white;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
}

/* 네트워크 상태 표시 */
.network-status {
    position: fixed;
    top: 60px;
    right: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.85rem;
    z-index: 1000;
}
.network-offline {
    background: #FFCDD2;
    color: #C62828;
}
.network-error {
    background: #FFE0B2;
    color: #E65100;
}

/* 로딩 오버레이 */
.loading-overlay {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(255,243,224,0.8);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
}

/* 멘션 스타일 */
.mention {
    background: #E3F2FD;
    color: #1565C0;
    padding: 1px 4px;
    border-radius: 4px;
    font-weight: 500;
}

/* 인폼 카드 개선 */
.inform-card {
    border: 1px solid #ddd;
    padding: 15px;
    border-radius: 10px;
    background-color: white;
    margin-bottom: 10px;
}
.inform-card-urgent {
    border: 2px solid #D32F2F;
    background-color: #FFEBEE;
}

/* 날짜 네비게이션 */
.date-nav {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# [4. 쿠키 및 DB 연결]
# ============================================================
cookies = CookieManager()
conn = st.connection("gsheets", type=GSheetsConnection)

# ============================================================
# [5. 데이터 로드/저장 - 개선된 버전]
# ============================================================
class DataManager:
    """데이터 관리 클래스 - 캐싱, 에러 처리, 재시도 로직 포함"""
    
    @staticmethod
    def _is_cache_valid(key: str) -> bool:
        """로컬 캐시 유효성 검사"""
        cache_time = st.session_state.get("cache_time", {}).get(key)
        if cache_time is None:
            return False
        return (datetime.now() - cache_time).total_seconds() < CACHE_TTL
    
    @staticmethod
    def _get_from_cache(key: str) -> Optional[pd.DataFrame]:
        """로컬 캐시에서 데이터 가져오기"""
        if DataManager._is_cache_valid(key):
            return st.session_state.get("data_cache", {}).get(key)
        return None
    
    @staticmethod
    def _set_cache(key: str, df: pd.DataFrame):
        """로컬 캐시에 데이터 저장"""
        if "data_cache" not in st.session_state:
            st.session_state["data_cache"] = {}
        if "cache_time" not in st.session_state:
            st.session_state["cache_time"] = {}
        st.session_state["data_cache"][key] = df.copy()
        st.session_state["cache_time"][key] = datetime.now()
    
    @staticmethod
    def clear_cache(key: str = None):
        """캐시 클리어"""
        if key:
            st.session_state.get("data_cache", {}).pop(key, None)
            st.session_state.get("cache_time", {}).pop(key, None)
        else:
            st.session_state["data_cache"] = {}
            st.session_state["cache_time"] = {}
    
    @staticmethod
    def load(key: str, force_refresh: bool = False) -> LoadResult:
        """
        데이터 로드 - 캐시 우선, 실패 시 명확한 에러 반환
        """
        # 강제 새로고침이 아니면 캐시 확인
        if not force_refresh:
            cached = DataManager._get_from_cache(key)
            if cached is not None:
                return LoadResult(data=cached, success=True)
        
        max_retries = 3
        last_error = ""
        
        for i in range(max_retries):
            try:
                df = conn.read(worksheet=SHEET_NAMES[key], ttl=0)
                if df is not None:
                    DataManager._set_cache(key, df)
                    return LoadResult(data=df, success=True)
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "Quota" in last_error.lower():
                    time.sleep(2 ** i)  # 지수 백오프
                    continue
                break
        
        # 실패 시 캐시된 데이터라도 반환 (있다면)
        cached = st.session_state.get("data_cache", {}).get(key)
        if cached is not None:
            return LoadResult(
                data=cached, 
                success=False, 
                error_msg=f"최신 데이터 로드 실패 (캐시 사용 중): {last_error}"
            )
        
        return LoadResult(
            data=pd.DataFrame(), 
            success=False, 
            error_msg=f"데이터 로드 실패: {last_error}"
        )
    
    @staticmethod
    def save(key: str, df: pd.DataFrame, operation_desc: str = "") -> SaveResult:
        """
        데이터 저장 - 재시도 및 실패 시 큐잉
        """
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
                    time.sleep(2 ** i)
                    continue
                break
        
        # 실패 시 재시도 큐에 추가
        pending = st.session_state.get("pending_saves", [])
        pending.append({
            "key": key,
            "data": df.to_dict(),
            "operation": operation_desc,
            "timestamp": datetime.now().isoformat(),
            "error": last_error
        })
        st.session_state["pending_saves"] = pending[-10:]  # 최근 10개만 유지
        
        return SaveResult(success=False, error_msg=last_error)
    
    @staticmethod
    def retry_pending_saves() -> Tuple[int, int]:
        """실패한 저장 재시도 - (성공 수, 실패 수) 반환"""
        pending = st.session_state.get("pending_saves", [])
        if not pending:
            return (0, 0)
        
        success_count = 0
        still_pending = []
        
        for item in pending:
            df = pd.DataFrame(item["data"])
            result = DataManager.save(item["key"], df, item["operation"])
            if result.success:
                success_count += 1
            else:
                still_pending.append(item)
        
        st.session_state["pending_saves"] = still_pending
        return (success_count, len(still_pending))

# 편의 함수
def load(key: str, force_refresh: bool = False) -> pd.DataFrame:
    """간편 로드 함수 - 에러 시 빈 DataFrame 반환"""
    result = DataManager.load(key, force_refresh)
    if not result.success and result.error_msg:
        st.session_state["last_error"] = result.error_msg
    return result.data

def save(key: str, df: pd.DataFrame, operation: str = "") -> bool:
    """간편 저장 함수"""
    result = DataManager.save(key, df, operation)
    if not result.success:
        st.session_state["last_error"] = result.error_msg
    return result.success

# ============================================================
# [6. 유틸리티 함수]
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode()).hexdigest()

def generate_session_token() -> str:
    """세션 토큰 생성 (비밀번호 대신 사용)"""
    return secrets.token_urlsafe(32)

def check_approved(val) -> bool:
    v = str(val).strip().lower()
    return v in ["true", "1", "1.0", "yes", "y", "t"]

def format_datetime(dt_str: str) -> str:
    """날짜/시간 포맷팅"""
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%m/%d %H:%M")
    except:
        return dt_str

def parse_mentions(text: str) -> List[str]:
    """텍스트에서 @멘션 추출"""
    import re
    return re.findall(r'@(\S+)', text)

def highlight_mentions(text: str) -> str:
    """멘션을 하이라이트 처리"""
    import re
    return re.sub(r'@(\S+)', r'<span class="mention">@\1</span>', text)

def is_task_due(start_date_str, cycle_type, interval_val) -> bool:
    try:
        if pd.isna(start_date_str) or str(start_date_str).strip() == "":
            return False
        try:
            start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
        except:
            return False
        
        today = date.today()
        if today < start_date:
            return False
        delta_days = (today - start_date).days
        
        if cycle_type == "매일":
            return True
        elif cycle_type == "매주":
            return delta_days % 7 == 0
        elif cycle_type == "매월":
            return today.day == start_date.day
        elif cycle_type == "N일 간격":
            return delta_days % int(interval_val) == 0
        return False
    except:
        return False

# ============================================================
# [7. 비즈니스 로직]
# ============================================================
def get_pending_tasks_list() -> List[dict]:
    """오늘 해야 할 미완료 업무 목록"""
    defs = load("routine_def")
    logs = load("routine_log")
    if defs.empty:
        return []

    today_str = date.today().strftime("%Y-%m-%d")
    pending = []
    
    for _, task in defs.iterrows():
        if is_task_due(task.get("start_date"), task.get("cycle_type"), task.get("interval_val", 1)):
            is_done = False
            if not logs.empty:
                done = logs[
                    (logs["task_id"].astype(str) == str(task["id"])) & 
                    (logs["done_date"] == today_str)
                ]
                if not done.empty:
                    is_done = True
            if not is_done:
                pending.append(dict(task))
    return pending

def get_unconfirmed_inform_list(username: str) -> List[dict]:
    """미확인 인폼 목록"""
    informs = load("inform_notes")
    logs = load("inform_logs")
    
    if informs.empty:
        return []
    
    today_str = date.today().strftime("%Y-%m-%d")
    today_informs = informs[informs["target_date"] == today_str]
    
    if today_informs.empty:
        return []
    
    unconfirmed = []
    for _, note in today_informs.iterrows():
        if not logs.empty:
            is_checked = logs[
                (logs["note_id"].astype(str) == str(note["id"])) & 
                (logs["username"] == username)
            ]
            if is_checked.empty:
                unconfirmed.append(dict(note))
        else:
            unconfirmed.append(dict(note))
    return unconfirmed

def get_unconfirmed_users_for_note(note_id: str, all_users: pd.DataFrame) -> List[str]:
    """특정 인폼의 미확인 사용자 목록"""
    logs = load("inform_logs")
    
    # 승인된 사용자만
    approved_users = all_users[all_users["approved"].apply(check_approved)]["name"].tolist()
    
    if logs.empty:
        return approved_users
    
    confirmed = logs[logs["note_id"].astype(str) == str(note_id)]["username"].tolist()
    return [u for u in approved_users if u not in confirmed]

def get_new_comments_count(username: str) -> int:
    """새 댓글 수 (자신의 글에 달린 댓글 중 오늘 것)"""
    posts = load("posts")
    comments = load("comments")
    
    if posts.empty or comments.empty:
        return 0
    
    my_posts = posts[posts["author"] == username]["id"].astype(str).tolist()
    today_str = date.today().strftime("%m-%d")
    
    new_comments = comments[
        (comments["post_id"].astype(str).isin(my_posts)) &
        (comments["date"].str.startswith(today_str)) &
        (comments["author"] != username)
    ]
    return len(new_comments)

def get_mentions_for_user(username: str) -> List[dict]:
    """나를 멘션한 댓글 목록"""
    comments = load("comments")
    if comments.empty:
        return []
    
    mentions = []
    for _, c in comments.iterrows():
        if f"@{username}" in str(c.get("content", "")):
            mentions.append(dict(c))
    return mentions

def search_content(query: str) -> Dict[str, List[dict]]:
    """인폼/게시판 검색"""
    results = {"inform": [], "posts": []}
    query = query.lower().strip()
    
    if not query:
        return results
    
    # 인폼 검색
    informs = load("inform_notes")
    if not informs.empty:
        for _, row in informs.iterrows():
            if query in str(row.get("content", "")).lower():
                results["inform"].append(dict(row))
    
    # 게시판 검색
    posts = load("posts")
    if not posts.empty:
        for _, row in posts.iterrows():
            if query in str(row.get("title", "")).lower() or \
               query in str(row.get("content", "")).lower():
                results["posts"].append(dict(row))
    
    return results

# ============================================================
# [8. UI 컴포넌트]
# ============================================================
def show_network_status():
    """네트워크/에러 상태 표시"""
    last_error = st.session_state.get("last_error")
    pending_saves = st.session_state.get("pending_saves", [])
    
    if pending_saves:
        st.markdown(f"""
            <div class="network-status network-error">
                ⚠️ 저장 대기 중: {len(pending_saves)}건
            </div>
        """, unsafe_allow_html=True)
    elif last_error:
        st.markdown(f"""
            <div class="network-status network-offline">
                ⚠️ 연결 불안정
            </div>
        """, unsafe_allow_html=True)

def show_pending_saves_retry():
    """실패한 저장 재시도 UI"""
    pending = st.session_state.get("pending_saves", [])
    if pending:
        with st.expander(f"⚠️ 저장 실패 항목 ({len(pending)}건)", expanded=True):
            for i, item in enumerate(pending):
                st.write(f"• {item['operation']} ({item['timestamp'][:16]})")
            
            st.markdown('<div class="retry-btn">', unsafe_allow_html=True)
            if st.button("🔄 재시도", key="retry_pending"):
                with st.spinner("재시도 중..."):
                    success, fail = DataManager.retry_pending_saves()
                    if success > 0:
                        st.success(f"✅ {success}건 저장 완료")
                    if fail > 0:
                        st.error(f"❌ {fail}건 여전히 실패")
                    time.sleep(1)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

@st.dialog("🚨 중요 알림")
def show_notification_popup(tasks: List[dict], inform_notes: List[dict]):
    """로그인 시 팝업"""
    if inform_notes:
        urgent = [n for n in inform_notes if n.get("priority") == "긴급"]
        normal = [n for n in inform_notes if n.get("priority") != "긴급"]
        
        if urgent:
            st.error(f"🚨 **긴급 필독 ({len(urgent)}건)**")
            for note in urgent:
                preview = note['content'][:50] + "..." if len(note['content']) > 50 else note['content']
                st.markdown(f"**📌 {preview}**")
        
        if normal:
            st.warning(f"📢 **오늘의 필독 사항 ({len(normal)}건)**")
            for note in normal:
                preview = note['content'][:30] + "..." if len(note['content']) > 30 else note['content']
                st.markdown(f"• {preview}")
        
        st.caption("※ [인폼] 메뉴에서 확인 버튼을 눌러주세요.")
        st.markdown("---")

    if tasks:
        st.info(f"🔄 **오늘의 반복 업무 ({len(tasks)}건)**")
        for t in tasks:
            st.write(f"• {t['task_name']}")
    
    st.write("")
    if st.button("확인", use_container_width=True):
        st.rerun()

def show_dashboard():
    """대시보드 - 오늘의 요약"""
    username = st.session_state['name']
    
    # 데이터 로드 (with spinner)
    with st.spinner("데이터 로딩 중..."):
        pending_tasks = get_pending_tasks_list()
        unconfirmed_informs = get_unconfirmed_inform_list(username)
        new_comments = get_new_comments_count(username)
        mentions = get_mentions_for_user(username)
    
    st.subheader("📊 오늘의 현황")
    
    # 카드 레이아웃
    c1, c2, c3 = st.columns(3)
    
    with c1:
        urgent_informs = [i for i in unconfirmed_informs if i.get("priority") == "긴급"]
        card_class = "dashboard-card-urgent" if urgent_informs else "dashboard-card-warning" if unconfirmed_informs else "dashboard-card-success"
        st.markdown(f"""
            <div class="dashboard-card {card_class}">
                <h3>📢 미확인 인폼</h3>
                <h1 style="margin:0;">{len(unconfirmed_informs)}</h1>
                {'<span class="urgent-badge">긴급 ' + str(len(urgent_informs)) + '건</span>' if urgent_informs else ''}
            </div>
        """, unsafe_allow_html=True)
    
    with c2:
        card_class = "dashboard-card-warning" if pending_tasks else "dashboard-card-success"
        st.markdown(f"""
            <div class="dashboard-card {card_class}">
                <h3>🔄 미완료 업무</h3>
                <h1 style="margin:0;">{len(pending_tasks)}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with c3:
        card_class = "dashboard-card-warning" if new_comments or mentions else "dashboard-card-success"
        st.markdown(f"""
            <div class="dashboard-card {card_class}">
                <h3>💬 새 알림</h3>
                <h1 style="margin:0;">{new_comments + len(mentions)}</h1>
                <small>댓글 {new_comments} / 멘션 {len(mentions)}</small>
            </div>
        """, unsafe_allow_html=True)
    
    # 긴급 인폼 바로 표시
    if urgent_informs:
        st.markdown("---")
        st.markdown("### 🚨 긴급 확인 필요")
        for note in urgent_informs[:3]:
            preview = note['content'][:80] + "..." if len(note['content']) > 80 else note['content']
            st.error(f"📌 {preview}")
    
    # 미완료 업무 표시
    if pending_tasks:
        st.markdown("---")
        st.markdown("### 📋 오늘 할 일")
        for task in pending_tasks[:5]:
            st.warning(f"• {task['task_name']}")

def show_search():
    """검색 기능"""
    st.subheader("🔍 검색")
    
    query = st.text_input("검색어 입력", placeholder="인폼, 게시글 내용 검색...")
    
    if query:
        with st.spinner("검색 중..."):
            results = search_content(query)
        
        total = len(results["inform"]) + len(results["posts"])
        st.write(f"**검색 결과: {total}건**")
        
        if results["inform"]:
            with st.expander(f"📢 인폼 ({len(results['inform'])}건)"):
                for item in results["inform"]:
                    st.markdown(f"""
                        <div class="inform-card">
                            <small>{item.get('target_date', '')} | {item.get('author', '')}</small>
                            <p>{item.get('content', '')}</p>
                        </div>
                    """, unsafe_allow_html=True)
        
        if results["posts"]:
            with st.expander(f"📝 게시글 ({len(results['posts'])}건)"):
                for item in results["posts"]:
                    st.write(f"**{item.get('title', '')}** - {item.get('author', '')} ({item.get('board_type', '')})")
                    st.caption(item.get('content', '')[:100] + "...")

# ============================================================
# [9. 페이지 함수]
# ============================================================
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
            
            if st.form_submit_button("입장", use_container_width=True):
                with st.spinner("로그인 중..."):
                    result = DataManager.load("users", force_refresh=True)
                    
                if not result.success:
                    st.error("서버 연결 실패. 잠시 후 다시 시도해주세요.")
                else:
                    users = result.data
                    hpw = hash_password(upw)
                    
                    if not users.empty:
                        users["username"] = users["username"].astype(str)
                        users["password"] = users["password"].astype(str)
                        u = users[(users["username"] == uid) & (users["password"] == hpw)]
                        
                        if not u.empty:
                            if check_approved(u.iloc[0].get("approved", "False")):
                                dept = u.iloc[0].get("department", "전체")
                                st.session_state.update({
                                    "logged_in": True,
                                    "name": u.iloc[0]["name"],
                                    "role": u.iloc[0]["role"],
                                    "department": dept,
                                    "show_popup_on_login": True
                                })
                                if auto:
                                    # 세션 토큰 사용 (비밀번호 해시 대신)
                                    token = generate_session_token()
                                    cookies["auto_login"] = "true"
                                    cookies["uid"] = uid
                                    cookies["token"] = token
                                    # 토큰을 users에 저장해야 하지만, 간단히 해시 사용
                                    cookies["upw"] = hpw
                                    cookies.save()
                                else:
                                    if cookies.get("auto_login"):
                                        cookies["auto_login"] = "false"
                                        cookies.save()
                                st.rerun()
                            else:
                                st.warning("⏳ 승인 대기 중입니다.")
                        else:
                            st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                    else:
                        st.error("사용자 정보를 불러올 수 없습니다.")
    
    with tab2:
        with st.form("signup"):
            st.write("가입 신청")
            new_id = st.text_input("희망 아이디")
            new_pw = st.text_input("희망 비밀번호", type="password")
            new_name = st.text_input("이름")
            new_dept = st.selectbox("주 근무지", DEPARTMENTS)
            
            if st.form_submit_button("신청", use_container_width=True):
                if not (new_id and new_pw and new_name):
                    st.warning("모든 항목을 입력해주세요.")
                else:
                    with st.spinner("처리 중..."):
                        result = DataManager.load("users", force_refresh=True)
                    
                    if not result.success:
                        st.error("서버 연결이 원활하지 않습니다. 잠시 후 다시 시도해주세요.")
                    elif not result.data.empty and new_id in result.data["username"].values:
                        st.error("이미 사용 중인 아이디입니다.")
                    else:
                        new_user = pd.DataFrame([{
                            "username": new_id,
                            "password": hash_password(new_pw),
                            "name": new_name,
                            "role": "Staff",
                            "approved": "False",
                            "department": new_dept
                        }])
                        
                        users = result.data
                        if users.empty:
                            save_result = save("users", new_user, "회원가입")
                        else:
                            save_result = save("users", pd.concat([users, new_user], ignore_index=True), "회원가입")
                        
                        if save_result:
                            st.success("✅ 가입 신청이 완료되었습니다. 관리자 승인을 기다려주세요.")
                        else:
                            st.error("신청 처리 중 오류가 발생했습니다.")

def page_inform():
    st.subheader("📢 인폼노트")
    
    # 날짜 네비게이션
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀ 이전", use_container_width=True):
            current = st.session_state.get("inform_date", date.today())
            st.session_state["inform_date"] = current - timedelta(days=1)
            st.rerun()
    with col2:
        selected_date = st.date_input(
            "날짜", 
            value=st.session_state.get("inform_date", date.today()),
            label_visibility="collapsed"
        )
        st.session_state["inform_date"] = selected_date
    with col3:
        if st.button("다음 ▶", use_container_width=True):
            current = st.session_state.get("inform_date", date.today())
            st.session_state["inform_date"] = current + timedelta(days=1)
            st.rerun()
    
    selected_date_str = selected_date.strftime("%Y-%m-%d")
    user_role = st.session_state['role']
    username = st.session_state['name']
    
    # 인폼 작성 (관리자만)
    if user_role in ["Master", "Manager"]:
        with st.expander("📝 인폼 작성"):
            with st.form("new_inform"):
                target_date_input = st.date_input("업무 수행일", value=selected_date)
                priority = st.radio("우선순위", ["일반", "긴급"], horizontal=True)
                ic = st.text_area("전달 내용 (필수)", height=100, 
                                  placeholder="@이름 으로 특정 직원을 멘션할 수 있습니다.")
                
                if st.form_submit_button("등록", use_container_width=True):
                    if ic.strip() == "":
                        st.warning("내용을 입력해주세요.")
                    else:
                        DataManager.clear_cache("inform_notes")
                        df = load("inform_notes", force_refresh=True)
                        
                        nid = 1
                        if not df.empty and "id" in df.columns:
                            nid = pd.to_numeric(df["id"], errors='coerce').fillna(0).max() + 1
                        
                        new_note = pd.DataFrame([{
                            "id": nid,
                            "target_date": target_date_input.strftime("%Y-%m-%d"),
                            "content": ic,
                            "author": username,
                            "priority": priority,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }])
                        
                        if df.empty:
                            success = save("inform_notes", new_note, "인폼 등록")
                        else:
                            success = save("inform_notes", pd.concat([df, new_note], ignore_index=True), "인폼 등록")
                        
                        if success:
                            st.success("✅ 등록 완료")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("등록 실패 - 잠시 후 재시도 버튼을 눌러주세요.")

    # 인폼 목록 표시
    with st.spinner("로딩 중..."):
        notes = load("inform_notes")
        logs = load("inform_logs")
        cmts = load("comments")
        users = load("users")
    
    if notes.empty:
        st.info("등록된 전달사항이 없습니다.")
        return

    daily_notes = notes[notes["target_date"] == selected_date_str]
    
    if daily_notes.empty:
        st.info(f"📅 {selected_date_str}의 인폼이 없습니다.")
    else:
        # 긴급 먼저, 그 다음 최신순
        daily_notes = daily_notes.copy()
        daily_notes["priority_order"] = daily_notes.get("priority", "일반").apply(
            lambda x: 0 if x == "긴급" else 1
        )
        daily_notes = daily_notes.sort_values(["priority_order", "id"], ascending=[True, False])
        
        for _, r in daily_notes.iterrows():
            note_id = str(r["id"])
            is_urgent = r.get("priority") == "긴급"
            card_class = "inform-card-urgent" if is_urgent else "inform-card"
            priority_badge = '<span class="urgent-badge">긴급</span>' if is_urgent else '<span class="normal-badge">일반</span>'
            
            # 멘션 하이라이트
            content_html = highlight_mentions(r['content'])
            
            st.markdown(f"""
                <div class="{card_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size:0.9em; color:#8D6E63; font-weight:bold;">
                            📅 {r['target_date']} | ✍️ {r['author']}
                        </span>
                        {priority_badge}
                    </div>
                    <div style="white-space: pre-wrap; line-height:1.6; font-size:1.05em; margin-top:10px; color:#333;">
                        {content_html}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 확인 상태
            confirmed_users = []
            if not logs.empty:
                l = logs[logs["note_id"].astype(str) == note_id]
                confirmed_users = l["username"].tolist()
            
            col_btn, col_status = st.columns([1, 3])
            
            with col_btn:
                if username not in confirmed_users:
                    st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
                    if st.button("확인함 ✅", key=f"confirm_{note_id}"):
                        nl = pd.DataFrame([{
                            "note_id": note_id,
                            "username": username,
                            "confirmed_at": datetime.now().strftime("%m-%d %H:%M")
                        }])
                        if logs.empty:
                            save("inform_logs", nl, "인폼 확인")
                        else:
                            save("inform_logs", pd.concat([logs, nl], ignore_index=True), "인폼 확인")
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.success("✅ 확인 완료")
            
            # 확인자/미확인자 표시 (관리자만)
            with col_status:
                if user_role in ["Master", "Manager"]:
                    unconfirmed = get_unconfirmed_users_for_note(note_id, users)
                    with st.expander(f"👀 확인: {len(confirmed_users)}명 | ⏳ 미확인: {len(unconfirmed)}명"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write("**✅ 확인**")
                            st.write(", ".join(confirmed_users) if confirmed_users else "-")
                        with c2:
                            st.write("**⏳ 미확인**")
                            st.write(", ".join(unconfirmed) if unconfirmed else "-")
                else:
                    with st.expander(f"👀 확인자 ({len(confirmed_users)}명)"):
                        st.write(", ".join(confirmed_users) if confirmed_users else "-")
            
            # 댓글
            if not cmts.empty:
                note_cmts = cmts[cmts["post_id"].astype(str) == f"inform_{note_id}"]
                for _, c in note_cmts.iterrows():
                    content_html = highlight_mentions(str(c['content']))
                    st.markdown(f"<div class='comment-box'><b>{c['author']}</b>: {content_html}</div>", 
                               unsafe_allow_html=True)
            
            with st.form(f"cmt_inform_{note_id}"):
                c1, c2 = st.columns([4, 1])
                ctxt = c1.text_input("댓글", label_visibility="collapsed", 
                                     placeholder="특이사항 작성 (@이름으로 멘션)")
                if c2.form_submit_button("등록"):
                    if ctxt.strip():
                        nc = pd.DataFrame([{
                            "post_id": f"inform_{note_id}",
                            "author": username,
                            "content": ctxt,
                            "date": datetime.now().strftime("%m-%d %H:%M")
                        }])
                        if cmts.empty:
                            save("comments", nc, "댓글 등록")
                        else:
                            save("comments", pd.concat([cmts, nc], ignore_index=True), "댓글 등록")
                        st.rerun()
            
            st.markdown("---")

def page_staff_mgmt():
    st.subheader("👥 직원 관리")
    
    with st.spinner("로딩 중..."):
        result = DataManager.load("users", force_refresh=False)
    
    if not result.success or result.data.empty:
        st.warning("데이터를 불러오지 못했습니다.")
        if st.button("🔄 다시 시도"):
            DataManager.clear_cache("users")
            st.rerun()
        return
    
    users = result.data.copy()
    
    if "approved" not in users.columns:
        users["approved"] = "False"
    if "department" not in users.columns:
        users["department"] = "전체"
    
    users["is_approved_bool"] = users["approved"].apply(check_approved)
    
    # 승인 대기
    pending = users[users["is_approved_bool"] == False]
    if not pending.empty:
        st.info(f"🔔 승인 대기: {len(pending)}명")
        for _, r in pending.iterrows():
            with st.expander(f"⏳ {r['name']} ({r['username']}) - {r['department']}"):
                c1, c2 = st.columns(2)
                if c1.button("✅ 수락", key=f"ok_{r['username']}", use_container_width=True):
                    users.loc[users["username"] == r["username"], "approved"] = "True"
                    users_save = users.drop(columns=["is_approved_bool"])
                    save("users", users_save, "직원 승인")
                    st.rerun()
                if c2.button("❌ 거절", key=f"no_{r['username']}", use_container_width=True):
                    users = users[users["username"] != r["username"]]
                    users_save = users.drop(columns=["is_approved_bool"])
                    save("users", users_save, "직원 거절")
                    st.rerun()
    
    st.divider()
    
    # 승인된 직원 목록
    active = users[users["is_approved_bool"] == True]
    if not active.empty:
        st.write("✅ 직원 목록")
        for i, r in active.iterrows():
            if r['username'] == st.session_state['name'] or r['username'] == "admin":
                continue
            
            with st.expander(f"👤 {r['name']} ({r['role']} / {r['department']})"):
                with st.form(key=f"edit_user_{r['username']}"):
                    c1, c2 = st.columns(2)
                    roles = ["Staff", "Manager", "Master"]
                    current_role_idx = roles.index(r['role']) if r['role'] in roles else 0
                    new_role = c1.selectbox("직급", roles, index=current_role_idx)
                    
                    current_dept_idx = DEPARTMENTS.index(r.get('department', '전체')) if r.get('department', '전체') in DEPARTMENTS else 0
                    new_dept = c2.selectbox("근무지", DEPARTMENTS, index=current_dept_idx)
                    
                    c3, c4 = st.columns(2)
                    if c3.form_submit_button("수정", type="primary", use_container_width=True):
                        users.loc[users["username"] == r["username"], "role"] = new_role
                        users.loc[users["username"] == r["username"], "department"] = new_dept
                        users_save = users.drop(columns=["is_approved_bool"])
                        save("users", users_save, "직원 정보 수정")
                        st.success("✅ 수정 완료")
                        time.sleep(0.5)
                        st.rerun()
                    
                    if c4.form_submit_button("삭제", type="secondary", use_container_width=True):
                        users = users[users["username"] != r["username"]]
                        users_save = users.drop(columns=["is_approved_bool"])
                        save("users", users_save, "직원 삭제")
                        st.warning("삭제됨")
                        time.sleep(0.5)
                        st.rerun()

def page_board(b_name: str, icon: str):
    st.subheader(f"{icon} {b_name}")
    user_role = st.session_state['role']
    username = st.session_state['name']
    
    can_write = (user_role in ["Master", "Manager"]) or (b_name == "건의사항")
    
    if can_write:
        expander_title = "✏️ 건의사항 올리기" if b_name == "건의사항" else "✏️ 글 쓰기"
        with st.expander(expander_title):
            with st.form(f"w_{b_name}"):
                tt = st.text_input("제목")
                ct = st.text_area("내용", placeholder="@이름으로 멘션 가능")
                # 파일 첨부 (링크만)
                file_link = st.text_input("📎 첨부 링크 (선택)", placeholder="구글 드라이브 등 링크")
                
                if st.form_submit_button("등록", use_container_width=True):
                    if not tt.strip() or not ct.strip():
                        st.warning("제목과 내용을 입력해주세요.")
                    else:
                        df = load("posts", force_refresh=True)
                        nid = 1 if df.empty else pd.to_numeric(df["id"], errors='coerce').fillna(0).max() + 1
                        
                        content = ct
                        if file_link.strip():
                            content += f"\n\n📎 첨부: {file_link}"
                        
                        np_df = pd.DataFrame([{
                            "id": nid,
                            "board_type": b_name,
                            "title": tt,
                            "content": content,
                            "author": username,
                            "date": datetime.now().strftime("%Y-%m-%d")
                        }])
                        
                        if df.empty:
                            save("posts", np_df, "게시글 등록")
                        else:
                            save("posts", pd.concat([df, np_df], ignore_index=True), "게시글 등록")
                        st.rerun()
    elif user_role == "Staff" and b_name != "건의사항":
        st.info("💡 Staff는 읽기 및 댓글만 가능합니다.")
    
    with st.spinner("로딩 중..."):
        posts = load("posts")
        cmts = load("comments")
    
    if posts.empty:
        st.info("등록된 글이 없습니다.")
    else:
        mp = posts[posts["board_type"].astype(str).str.strip() == b_name] if "board_type" in posts.columns else pd.DataFrame()
        if mp.empty:
            st.info("등록된 글이 없습니다.")
        else:
            mp = mp.sort_values("id", ascending=False)
            for _, r in mp.iterrows():
                can_del = (user_role == "Master") or (r['author'] == username)
                
                with st.expander(f"📄 {r['title']} ({r['author']} | {r['date']})"):
                    # 멘션 하이라이트
                    content_html = highlight_mentions(str(r['content']))
                    st.markdown(f"<div style='white-space: pre-wrap;'>{content_html}</div>", unsafe_allow_html=True)
                    
                    if can_del:
                        if st.button("🗑️ 삭제", key=f"del_{r['id']}"):
                            posts = posts[posts["id"] != r["id"]]
                            save("posts", posts, "게시글 삭제")
                            st.rerun()
                    
                    # 댓글
                    if not cmts.empty:
                        post_cmts = cmts[cmts["post_id"].astype(str) == str(r["id"])]
                        for _, c in post_cmts.iterrows():
                            c_html = highlight_mentions(str(c['content']))
                            st.markdown(f"<div class='comment-box'><b>{c['author']}</b> ({c['date']}): {c_html}</div>", 
                                       unsafe_allow_html=True)
                    
                    with st.form(f"c_{r['id']}"):
                        c1, c2 = st.columns([4, 1])
                        ctxt = c1.text_input("댓글", label_visibility="collapsed", placeholder="@이름으로 멘션")
                        if c2.form_submit_button("등록"):
                            if ctxt.strip():
                                nc = pd.DataFrame([{
                                    "post_id": r["id"],
                                    "author": username,
                                    "content": ctxt,
                                    "date": datetime.now().strftime("%m-%d %H:%M")
                                }])
                                if cmts.empty:
                                    save("comments", nc, "댓글 등록")
                                else:
                                    save("comments", pd.concat([cmts, nc], ignore_index=True), "댓글 등록")
                                st.rerun()

def page_routine():
    st.subheader("🔄 업무 체크")
    
    with st.spinner("로딩 중..."):
        defs = load("routine_def")
        logs = load("routine_log")
    
    if not defs.empty and "id" not in defs.columns:
        defs["id"] = range(1, len(defs) + 1)
    
    today = date.today().strftime("%Y-%m-%d")
    username = st.session_state['name']
    
    t1, t2 = st.tabs(["📋 오늘 업무", "📊 기록"])
    
    with t1:
        # 관리자용 업무 추가
        if st.session_state['role'] in ["Master", "Manager"]:
            with st.expander("⚙️ 업무 관리"):
                with st.form("new_r"):
                    c1, c2 = st.columns(2)
                    rn = c1.text_input("업무명")
                    rs = c2.date_input("시작일")
                    c3, c4 = st.columns(2)
                    rc = c3.selectbox("주기", ["매일", "매주", "매월", "N일 간격"])
                    ri = 1
                    if rc == "N일 간격":
                        ri = c4.number_input("간격(일)", 1, 365, 3)
                    
                    if st.form_submit_button("➕ 추가", use_container_width=True):
                        if rn.strip():
                            nid = 1 if defs.empty else pd.to_numeric(defs["id"], errors='coerce').fillna(0).max() + 1
                            nr = pd.DataFrame([{
                                "id": nid,
                                "task_name": rn,
                                "start_date": rs.strftime("%Y-%m-%d"),
                                "cycle_type": rc,
                                "interval_val": ri
                            }])
                            if defs.empty:
                                save("routine_def", nr, "반복업무 추가")
                            else:
                                save("routine_def", pd.concat([defs, nr], ignore_index=True), "반복업무 추가")
                            st.rerun()
                
                if not defs.empty:
                    st.write("**등록된 업무**")
                    for _, r in defs.iterrows():
                        c1, c2 = st.columns([4, 1])
                        c1.text(f"• {r['task_name']} ({r['cycle_type']})")
                        if c2.button("🗑️", key=f"d_{r['id']}"):
                            save("routine_def", defs[defs["id"] != r['id']], "반복업무 삭제")
                            st.rerun()
        
        st.divider()
        
        # 오늘 할 일
        ptasks = get_pending_tasks_list()
        if not ptasks:
            st.success("🎉 오늘의 모든 업무가 완료되었습니다!")
        else:
            st.write(f"**📋 오늘 할 일: {len(ptasks)}건**")
            for t in ptasks:
                st.markdown(f"""
                    <div style='padding:12px; border:1px solid #FFCDD2; background:#FFEBEE; 
                         border-radius:10px; margin-bottom:8px;'>
                        <b>{t['task_name']}</b>
                        <small style='color:#888;'> ({t['cycle_type']})</small>
                    </div>
                """, unsafe_allow_html=True)
                
                # 완료 메모 추가
                with st.form(f"complete_{t['id']}"):
                    c1, c2 = st.columns([3, 1])
                    memo = c1.text_input("완료 메모", label_visibility="collapsed", 
                                         placeholder="특이사항 (선택)", key=f"memo_{t['id']}")
                    if c2.form_submit_button("완료 ✅"):
                        nl = pd.DataFrame([{
                            "task_id": t["id"],
                            "done_date": today,
                            "worker": username,
                            "memo": memo,
                            "created_at": datetime.now().strftime("%H:%M")
                        }])
                        if logs.empty:
                            save("routine_log", nl, "업무 완료")
                        else:
                            save("routine_log", pd.concat([logs, nl], ignore_index=True), "업무 완료")
                        st.rerun()
    
    with t2:
        if not logs.empty and not defs.empty:
            logs_copy = logs.copy()
            defs_copy = defs.copy()
            logs_copy["task_id"] = logs_copy["task_id"].astype(str)
            defs_copy["id"] = defs_copy["id"].astype(str)
            
            m = pd.merge(logs_copy, defs_copy, left_on="task_id", right_on="id", how="left")
            m = m.sort_values(["done_date", "created_at"], ascending=False)
            
            display_cols = ["done_date", "task_name", "worker"]
            if "memo" in m.columns:
                display_cols.append("memo")
            
            st.dataframe(
                m[display_cols].head(50),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "done_date": "날짜",
                    "task_name": "업무",
                    "worker": "담당자",
                    "memo": "메모"
                }
            )
        else:
            st.info("기록이 없습니다.")

# ============================================================
# [10. 메인 앱]
# ============================================================
def main():
    AppState.init()
    
    # 자동 로그인 체크
    if not st.session_state.get("logged_in"):
        try:
            if cookies.get("auto_login") == "true":
                sid = cookies.get("uid")
                spw = cookies.get("upw")
                if sid and spw:
                    result = DataManager.load("users")
                    if result.success and not result.data.empty:
                        users = result.data
                        users["username"] = users["username"].astype(str)
                        users["password"] = users["password"].astype(str)
                        u = users[(users["username"] == sid) & (users["password"] == spw)]
                        if not u.empty and check_approved(u.iloc[0].get("approved", "False")):
                            dept = u.iloc[0].get("department", "전체")
                            st.session_state.update({
                                "logged_in": True,
                                "name": u.iloc[0]["name"],
                                "role": u.iloc[0]["role"],
                                "department": dept
                            })
                            cookies.save()
        except Exception:
            pass

    # 비로그인 상태
    if not st.session_state.get("logged_in"):
        login_page()
        return
    
    # 로그인 상태 - 헤더
    show_network_status()
    
    processed_logo_header = get_processed_logo("logo.png", icon_size=(50, 50))
    c1, c2, c3, c4 = st.columns([0.5, 3, 0.5, 0.5])
    
    with c1:
        if processed_logo_header:
            st.image(processed_logo_header, width=40)
    with c2:
        st.markdown(f"""
            <div style='padding-top:8px;'>
                <b>{st.session_state['name']}</b>
                <small style='color:#888;'>({st.session_state.get('department','전체')})</small>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        if st.button("🔍", help="검색"):
            st.session_state["show_search"] = not st.session_state.get("show_search", False)
            st.rerun()
    with c4:
        if st.button("🔄", help="새로고침"):
            DataManager.clear_cache()
            st.session_state["last_error"] = None
            st.rerun()
    
    # 검색 UI
    if st.session_state.get("show_search"):
        show_search()
        st.divider()
    
    # 실패한 저장 재시도 UI
    show_pending_saves_retry()
    
    # 메뉴 구성
    menu_opts = ["홈"]
    menu_icons = ["house"]
    dept = st.session_state.get('department', '전체')
    
    menu_opts.append("인폼")
    menu_icons.append("bell")
    
    if dept in ['전체', '본점']:
        menu_opts.append("본점")
        menu_icons.append("shop")
    if dept in ['전체', '작업장']:
        menu_opts.append("작업장")
        menu_icons.append("tools")
    
    menu_opts.extend(["건의", "업무"])
    menu_icons.extend(["lightbulb", "check-square"])
    
    if st.session_state['role'] == "Master":
        menu_opts.append("관리")
        menu_icons.append("people")
    
    menu_opts.append("나가기")
    menu_icons.append("box-arrow-right")
    
    m = option_menu(
        None, menu_opts,
        icons=menu_icons,
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#FFF3E0", "margin": "0"},
            "icon": {"color": "#4E342E", "font-size": "14px"},
            "nav-link": {
                "font-size": "12px",
                "text-align": "center",
                "margin": "0px",
                "--hover-color": "#eee",
                "padding": "5px 2px"
            },
            "nav-link-selected": {"background-color": "#8D6E63"},
        }
    )
    
    # 로그아웃
    if m == "나가기":
        st.session_state["logged_in"] = False
        cookies["auto_login"] = "false"
        cookies.save()
        DataManager.clear_cache()
        st.rerun()
    
    # 로그인 직후 팝업
    if st.session_state.get("show_popup_on_login", False):
        pt = get_pending_tasks_list()
        unconfirmed = get_unconfirmed_inform_list(st.session_state['name'])
        if pt or unconfirmed:
            show_notification_popup(pt, unconfirmed)
        st.session_state["show_popup_on_login"] = False
    
    # 페이지 라우팅
    if m == "홈":
        show_dashboard()
    elif m == "관리":
        page_staff_mgmt()
    elif m == "인폼":
        page_inform()
    elif m == "본점":
        page_board("본점", "🏠")
    elif m == "작업장":
        page_board("작업장", "🏭")
    elif m == "건의":
        page_board("건의사항", "💡")
    elif m == "업무":
        page_routine()

if __name__ == "__main__":
    main()
