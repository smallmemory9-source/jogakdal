import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
import secrets
import pytz  # [필수] 한국 시간 처리를 위해 추가
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
# [중요] 한국 시간대 설정
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

# [수정됨] CSS: 아이콘 깨짐 방지를 위해 선택자 구체화
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');

/* 기본 폰트 적용 (아이콘 제외) */
html, body, .stMarkdown, .stButton, .stTextInput, .stTextArea, .stSelectbox, p, h1, h2, h3, h4, h5, h6 {
    font-family: 'Noto Sans KR', sans-serif !important;
    color: #333333 !important;
}

/* 입력 필드 색상 */
input, textarea, select {
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
.confirm-btn > button:hover { background-color: #1B5E20 !important; }
.retry-btn > button { background-color: #E65100 !important; }

/* 배경색 */
.stApp { background-color: #FFF3E0; }

/* 헤더 숨김 및 네비게이션 스타일 */
header { background-color: transparent !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
.nav-link-selected { background-color: #8D6E63 !important; color: white !important; }

/* 대시보드 카드 */
.dashboard-card {
    background: white;
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    color: #333333 !important;
}
.dashboard-card h1, .dashboard-card h3, .dashboard-card small { color: #333333 !important; }
.dashboard-card-urgent { border-left: 4px solid #D32F2F; }
.dashboard-card-warning { border-left: 4px solid #FFA000; }
.dashboard-card-success { border-left: 4px solid #388E3C; }

/* 배지 */
.urgent-badge { background: #D32F2F; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
.normal-badge { background: #757575; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }

/* 인폼 및 댓글 */
.inform-card { border: 1px solid #ddd; padding: 15px; border-radius: 10px; background-color: white; margin-bottom: 10px; }
.inform-card-urgent { border: 2px solid #D32F2F; background-color: #FFEBEE; }
.comment-box { background-color: #F5F5F5; padding: 10px; border-radius: 8px; margin-top: 5px; font-size: 0.9rem; }
.mention { background: #E3F2FD; color: #1565C0; padding: 1px 4px; border-radius: 4px; font-weight: 500; }

/* 로고 및 헤더 */
.logo-title-container { display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.logo-title-container h1 { margin: 0 0 0 10px; font-size: 1.8rem; }
.network-status { position: fixed; top: 60px; right: 10px; padding: 8px 12px; border-radius: 8px; font-size: 0.85rem; z-index: 1000; }
.network-error { background: #FFE0B2; color: #E65100; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# [4. 쿠키 및 DB 연결]
# ============================================================
cookies = CookieManager()
conn = st.connection("gsheets", type=GSheetsConnection)

# ============================================================
# [5. 데이터 로드/저장 - 안정성 강화 버전]
# ============================================================
class DataManager:
    """데이터 관리 클래스 - 캐싱, 에러 처리, 동시성 처리 포함"""
    
    @staticmethod
    def _is_cache_valid(key: str) -> bool:
        """로컬 캐시 유효성 검사 (60초로 단축하여 동시성 개선)"""
        cache_time = st.session_state.get("cache_time", {}).get(key)
        if cache_time is None:
            return False
        # 한국 시간 기준 비교
        return (get_now() - cache_time).total_seconds() < 60
    
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
        st.session_state["cache_time"][key] = get_now()
    
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
        """데이터 로드 - 검증 로직 추가"""
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
                    # [추가] 데이터 무결성 검사 (빈 껍데기 로드 방지)
                    if not df.empty and key == "users" and "username" not in df.columns:
                        raise ValueError("잘못된 데이터 형식입니다 (헤더 누락).")
                        
                    DataManager._set_cache(key, df)
                    return LoadResult(data=df, success=True)
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "Quota" in last_error.lower():
                    time.sleep(1 + i)
                    continue
                break
        
        # 최신 로드 실패 시 캐시라도 반환
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
        """데이터 저장 - 안전장치 추가"""
        # 안전장치: 기존 데이터보다 현저히 적으면(30% 이상 삭제) 저장 차단
        if key == "users":
            cached = st.session_state.get("data_cache", {}).get(key)
            if cached is not None and not cached.empty:
                if len(df) < len(cached) * 0.7 and len(cached) >= 3:
                    return SaveResult(
                        success=False, 
                        error_msg=f"안전장치 발동: 데이터가 너무 많이 줄었습니다. 저장을 차단합니다."
                    )
        
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
        
        # 저장 실패 시 큐잉
        pending = st.session_state.get("pending_saves", [])
        pending.append({
            "key": key,
            "data": df.to_dict(),
            "operation": operation_desc,
            "timestamp": get_now().isoformat(),
            "error": last_error
        })
        st.session_state["pending_saves"] = pending[-10:]
        
        return SaveResult(success=False, error_msg=last_error)

    @staticmethod
    def append_row(key: str, new_row: dict, id_column: str = "id", operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success and result.data.empty: # 완전히 로드 실패 시 대기
                time.sleep(1)
                continue
            
            current_df = result.data
            
            # ID 자동 생성
            if id_column and id_column in new_row:
                if current_df.empty:
                    new_row[id_column] = 1
                else:
                    try:
                        max_id = pd.to_numeric(current_df[id_column], errors='coerce').fillna(0).max()
                        new_row[id_column] = int(max_id) + 1
                    except:
                        new_row[id_column] = len(current_df) + 1
            
            new_df = pd.DataFrame([new_row])
            if current_df.empty:
                updated_df = new_df
            else:
                updated_df = pd.concat([current_df, new_df], ignore_index=True)
            
            save_result = DataManager.save(key, updated_df, operation_desc)
            if save_result.success:
                return save_result
            time.sleep(1)
            
        return SaveResult(success=False, error_msg="여러 번 시도했지만 저장에 실패했습니다.")

    @staticmethod
    def update_row(key: str, match_column: str, match_value: Any, updates: dict, operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(1)
                continue
            
            current_df = result.data.copy()
            if current_df.empty:
                return SaveResult(success=False, error_msg="데이터가 없습니다.")
            
            mask = current_df[match_column].astype(str) == str(match_value)
            if not mask.any():
                return SaveResult(success=False, error_msg="수정할 데이터를 찾을 수 없습니다.")
            
            for col, val in updates.items():
                current_df.loc[mask, col] = val
            
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success:
                return save_result
            time.sleep(1)
        return SaveResult(success=False, error_msg="수정에 실패했습니다.")

    @staticmethod
    def delete_row(key: str, match_column: str, match_value: Any, operation_desc: str = "") -> SaveResult:
        for attempt in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(1)
                continue
            
            current_df = result.data.copy()
            original_len = len(current_df)
            current_df = current_df[current_df[match_column].astype(str) != str(match_value)]
            
            if len(current_df) == original_len:
                return SaveResult(success=False, error_msg="삭제할 데이터를 찾을 수 없습니다.")
            
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success:
                return save_result
            time.sleep(1)
        return SaveResult(success=False, error_msg="삭제에 실패했습니다.")
    
    @staticmethod
    def retry_pending_saves() -> Tuple[int, int]:
        pending = st.session_state.get("pending_saves", [])
        if not pending: return (0, 0)
        
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

# ============================================================
# [6. 유틸리티 함수]
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode()).hexdigest()

def generate_session_token() -> str:
    return secrets.token_urlsafe(32)

def check_approved(val) -> bool:
    v = str(val).strip().lower()
    return v in ["true", "1", "1.0", "yes", "y", "t"]

def format_datetime(dt_str: str) -> str:
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%m/%d %H:%M")
    except:
        return dt_str

def highlight_mentions(text: str) -> str:
    import re
    return re.sub(r'@(\S+)', r'<span class="mention">@\1</span>', text)

def is_task_due(start_date_str, cycle_type, interval_val) -> bool:
    try:
        if pd.isna(start_date_str) or str(start_date_str).strip() == "": return False
        
        # [변경] 한국 시간 기준으로 날짜 비교
        start_date = datetime.strptime(str(start_date_str), "%Y-%m-%d").date()
        today = get_now().date()
        
        if today < start_date: return False
        delta_days = (today - start_date).days
        
        if cycle_type == "매일": return True
        elif cycle_type == "매주": return delta_days % 7 == 0
        elif cycle_type == "매월": return today.day == start_date.day
        elif cycle_type == "N일 간격": return delta_days % int(interval_val) == 0
        return False
    except:
        return False

# ============================================================
# [7. 비즈니스 로직 (개선된 시간 적용)]
# ============================================================
def get_pending_tasks_list() -> List[dict]:
    result_def = DataManager.load("routine_def")
    result_log = DataManager.load("routine_log")
    if not result_def.success: return []
    
    defs = result_def.data
    logs = result_log.data
    
    if defs.empty: return []

    today_str = get_today_str() # [변경] 한국 시간
    pending = []
    
    for _, task in defs.iterrows():
        if is_task_due(task.get("start_date"), task.get("cycle_type"), task.get("interval_val", 1)):
            is_done = False
            if not logs.empty:
                done = logs[
                    (logs["task_id"].astype(str) == str(task["id"])) & 
                    (logs["done_date"] == today_str)
                ]
                if not done.empty: is_done = True
            if not is_done:
                pending.append(dict(task))
    return pending

def get_unconfirmed_inform_list(username: str) -> List[dict]:
    res_informs = DataManager.load("inform_notes")
    res_logs = DataManager.load("inform_logs")
    
    if not res_informs.success or res_informs.data.empty: return []
    informs = res_informs.data
    logs = res_logs.data if res_logs.success else pd.DataFrame()
    
    today_str = get_today_str() # [변경] 한국 시간
    today_informs = informs[informs["target_date"] == today_str]
    
    if today_informs.empty: return []
    
    unconfirmed = []
    for _, note in today_informs.iterrows():
        is_checked = False
        if not logs.empty:
            is_checked = not logs[
                (logs["note_id"].astype(str) == str(note["id"])) & 
                (logs["username"] == username)
            ].empty
        
        if not is_checked:
            unconfirmed.append(dict(note))
    return unconfirmed

def get_unconfirmed_users_for_note(note_id: str, all_users: pd.DataFrame) -> List[str]:
    logs = DataManager.load("inform_logs").data
    approved_users = all_users[all_users["approved"].apply(check_approved)]["name"].tolist()
    
    if logs.empty: return approved_users
    
    confirmed = logs[logs["note_id"].astype(str) == str(note_id)]["username"].tolist()
    # username을 name으로 매핑해야 정확하지만, 편의상 승인된 유저 목록에서 제외
    # 실제로는 users 데이터프레임에서 username <-> name 매핑 필요.
    # 여기서는 name 기준으로 비교한다고 가정 (또는 username이 로직상 섞여 있다면 주의)
    # 기존 코드 로직 유지
    return [u for u in approved_users if u not in confirmed]

def get_new_comments_count(username: str) -> int:
    res_posts = DataManager.load("posts")
    res_comments = DataManager.load("comments")
    if not res_posts.success or not res_comments.success: return 0
    
    posts, comments = res_posts.data, res_comments.data
    if posts.empty or comments.empty: return 0
    
    my_posts = posts[posts["author"] == username]["id"].astype(str).tolist()
    today_mmdd = get_now().strftime("%m-%d") # [변경]
    
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
        if f"@{username}" in str(c.get("content", "")):
            mentions.append(dict(c))
    return mentions

def search_content(query: str) -> Dict[str, List[dict]]:
    results = {"inform": [], "posts": []}
    query = query.lower().strip()
    if not query: return results
    
    informs = DataManager.load("inform_notes").data
    if not informs.empty:
        for _, row in informs.iterrows():
            if query in str(row.get("content", "")).lower():
                results["inform"].append(dict(row))
    
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
        st.markdown(f"""
            <div class="network-status network-error">
                ⚠️ 저장 대기: {len(pending_saves)}건
            </div>
        """, unsafe_allow_html=True)

def show_pending_saves_retry():
    pending = st.session_state.get("pending_saves", [])
    if pending:
        with st.expander(f"⚠️ 저장 실패 항목 ({len(pending)}건)", expanded=True):
            for i, item in enumerate(pending):
                # [변경] 타임스탬프 슬라이싱 안전하게
                ts = item['timestamp']
                display_ts = ts[:16] if len(ts) >= 16 else ts
                st.write(f"• {item['operation']} ({display_ts})")
            
            st.markdown('<div class="retry-btn">', unsafe_allow_html=True)
            if st.button("🔄 재시도", key="retry_pending"):
                with st.spinner("재시도 중..."):
                    success, fail = DataManager.retry_pending_saves()
                    if success > 0: st.success(f"✅ {success}건 저장 완료")
                    if fail > 0: st.error(f"❌ {fail}건 여전히 실패")
                    time.sleep(1)
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

@st.dialog("🚨 중요 알림")
def show_notification_popup(tasks: List[dict], inform_notes: List[dict]):
    if inform_notes:
        urgent = [n for n in inform_notes if n.get("priority") == "긴급"]
        if urgent:
            st.error(f"🚨 **긴급 필독 ({len(urgent)}건)**")
            for note in urgent:
                preview = note['content'][:50] + "..." if len(note['content']) > 50 else note['content']
                st.markdown(f"**📌 {preview}**")
    
    if tasks:
        st.info(f"🔄 **오늘의 반복 업무 ({len(tasks)}건)**")
        for t in tasks:
            st.write(f"• {t['task_name']}")
    
    if st.button("확인", use_container_width=True):
        st.rerun()

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
        card_class = "dashboard-card-urgent" if urgent_informs else "dashboard-card-warning" if unconfirmed_informs else "dashboard-card-success"
        st.markdown(f"""
            <div class="dashboard-card {card_class}">
                <h3>📢 미확인 인폼</h3>
                <h1>{len(unconfirmed_informs)}</h1>
            </div>
        """, unsafe_allow_html=True)
        if unconfirmed_informs:
            if st.button("📢 인폼 확인하기", key="btn_inform", use_container_width=True):
                st.session_state["dashboard_view"] = "inform"
                st.rerun()
    
    with c2:
        card_class = "dashboard-card-warning" if pending_tasks else "dashboard-card-success"
        st.markdown(f"""
            <div class="dashboard-card {card_class}">
                <h3>🔄 미완료 업무</h3>
                <h1>{len(pending_tasks)}</h1>
            </div>
        """, unsafe_allow_html=True)
        if pending_tasks:
            if st.button("🔄 업무 처리하기", key="btn_task", use_container_width=True):
                st.session_state["dashboard_view"] = "task"
                st.rerun()
    
    with c3:
        total_noti = new_comments + len(mentions)
        card_class = "dashboard-card-warning" if total_noti else "dashboard-card-success"
        st.markdown(f"""
            <div class="dashboard-card {card_class}">
                <h3>💬 새 알림</h3>
                <h1>{total_noti}</h1>
            </div>
        """, unsafe_allow_html=True)
        if total_noti:
            if st.button("💬 알림 확인하기", key="btn_notif", use_container_width=True):
                st.session_state["dashboard_view"] = "notification"
                st.rerun()
    
    st.markdown("---")
    
    # 대시보드 내부 라우팅
    view = st.session_state.get("dashboard_view")
    
    if view:
        if st.button("← 대시보드로 돌아가기"):
            st.session_state["dashboard_view"] = None
            st.rerun()
        
        if view == "inform":
            page_inform()
        elif view == "task":
            page_routine()
        elif view == "notification":
            st.info("알림 상세 기능은 준비 중입니다. 각 메뉴에서 확인해주세요.")
            if mentions:
                st.write("나를 멘션한 글:")
                for m in mentions:
                    st.write(f"- {m['content']}")

def show_search():
    st.subheader("🔍 검색")
    query = st.text_input("검색어 입력", placeholder="내용 검색...")
    if query:
        with st.spinner("검색 중..."):
            results = search_content(query)
        st.write(f"**검색 결과: {len(results['inform']) + len(results['posts'])}건**")
        
        if results["inform"]:
            with st.expander(f"📢 인폼 ({len(results['inform'])})"):
                for item in results["inform"]:
                    st.write(f"[{item['target_date']}] {item['content']}")
        if results["posts"]:
            with st.expander(f"📝 게시글 ({len(results['posts'])})"):
                for item in results["posts"]:
                    st.write(f"[{item['board_type']}] {item['title']} - {item['author']}")

# ============================================================
# [9. 페이지 함수]
# ============================================================
def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    processed_logo = get_processed_logo("logo.png", icon_size=(80, 80))
    if processed_logo:
        st.markdown(f"""
            <div class="logo-title-container">
                <img src="data:image/png;base64,{image_to_base64(processed_logo)}" style="max-height: 80px; width: auto;">
                <h1>업무수첩</h1>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.title("업무수첩")

    tab1, tab2 = st.tabs(["로그인", "회원가입 요청"])
    
    with tab1:
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            auto = st.checkbox("자동 로그인")
            
            if st.form_submit_button("입장", use_container_width=True):
                result = DataManager.load("users", force_refresh=True)
                if result.success and not result.data.empty:
                    users = result.data
                    users["username"] = users["username"].astype(str)
                    users["password"] = users["password"].astype(str)
                    
                    hpw = hash_password(upw)
                    u = users[(users["username"] == uid) & (users["password"] == hpw)]
                    
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
                                cookies["auto_login"] = "true"
                                cookies["uid"] = uid
                                cookies["upw"] = hpw
                                cookies.save()
                            st.rerun()
                        else:
                            st.warning("⏳ 승인 대기 중입니다.")
                    else:
                        st.error("아이디/비밀번호 불일치")
                else:
                    st.error("서버 연결 실패")

    with tab2:
        with st.form("signup"):
            new_id = st.text_input("희망 아이디")
            new_pw = st.text_input("희망 비밀번호", type="password")
            new_name = st.text_input("이름")
            new_dept = st.selectbox("주 근무지", DEPARTMENTS)
            
            if st.form_submit_button("신청", use_container_width=True):
                if new_id and new_pw and new_name:
                    res = DataManager.load("users", force_refresh=True)
                    if res.success:
                        users = res.data
                        if not users.empty and new_id in users["username"].values:
                            st.error("이미 존재하는 아이디입니다.")
                        else:
                            new_row = {
                                "username": new_id,
                                "password": hash_password(new_pw),
                                "name": new_name,
                                "role": "Staff",
                                "approved": "False",
                                "department": new_dept
                            }
                            new_df = pd.DataFrame([new_row])
                            final_df = pd.concat([users, new_df], ignore_index=True) if not users.empty else new_df
                            
                            save_res = DataManager.save("users", final_df, "회원가입")
                            if save_res.success:
                                st.success("신청 완료. 승인을 기다려주세요.")
                            else:
                                st.error("신청 실패")
                    else:
                        st.error("서버 오류")
                else:
                    st.warning("모든 항목을 입력해주세요.")

def page_inform():
    st.subheader("📢 인폼노트")
    
    # [변경] 날짜 초기값을 한국 시간 기준
    if "inform_date" not in st.session_state:
        st.session_state["inform_date"] = get_now().date()
        
    c1, c2, c3 = st.columns([1,2,1])
    with c1:
        if st.button("◀", use_container_width=True):
            st.session_state["inform_date"] -= timedelta(days=1)
            st.rerun()
    with c2:
        st.session_state["inform_date"] = st.date_input("날짜", value=st.session_state["inform_date"], label_visibility="collapsed")
    with c3:
        if st.button("▶", use_container_width=True):
            st.session_state["inform_date"] += timedelta(days=1)
            st.rerun()
    
    selected_date_str = st.session_state["inform_date"].strftime("%Y-%m-%d")
    role = st.session_state['role']
    name = st.session_state['name']
    
    # 작성 (관리자)
    if role in ["Master", "Manager"]:
        with st.expander("📝 인폼 작성"):
            with st.form("new_inform"):
                # [변경] 기본 날짜 한국 시간
                t_date = st.date_input("날짜", value=st.session_state["inform_date"])
                priority = st.radio("중요도", ["일반", "긴급"], horizontal=True)
                content = st.text_area("내용")
                if st.form_submit_button("등록", use_container_width=True):
                    if content:
                        DataManager.append_row("inform_notes", {
                            "target_date": t_date.strftime("%Y-%m-%d"),
                            "content": content,
                            "author": name,
                            "priority": priority,
                            "created_at": get_now().strftime("%Y-%m-%d %H:%M")
                        }, "id", "인폼 등록")
                        st.rerun()

    # 목록
    res_notes = DataManager.load("inform_notes")
    res_logs = DataManager.load("inform_logs")
    
    if res_notes.success and not res_notes.data.empty:
        notes = res_notes.data
        daily = notes[notes["target_date"] == selected_date_str]
        
        if daily.empty:
            st.info("등록된 인폼이 없습니다.")
        else:
            daily = sorted(daily.to_dict('records'), key=lambda x: 0 if x.get('priority') == '긴급' else 1)
            logs = res_logs.data if res_logs.success else pd.DataFrame()
            
            for note in daily:
                note_id = str(note['id'])
                is_urgent = note.get('priority') == '긴급'
                cls = "inform-card-urgent" if is_urgent else "inform-card"
                badge = '<span class="urgent-badge">긴급</span>' if is_urgent else '<span class="normal-badge">일반</span>'
                content_html = highlight_mentions(note['content'])
                
                st.markdown(f"""
                    <div class="{cls}">
                        <div style="display:flex; justify-content:space-between;">
                            <b>{note['author']}</b> {badge}
                        </div>
                        <div style="margin-top:10px; white-space: pre-wrap;">{content_html}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                confirmed_list = []
                if not logs.empty:
                    confirmed_list = logs[logs["note_id"].astype(str) == note_id]["username"].tolist()
                
                c_btn, c_stat = st.columns([1,3])
                with c_btn:
                    if name not in confirmed_list:
                        if st.button("확인함 ✅", key=f"ok_{note_id}"):
                            DataManager.append_row("inform_logs", {
                                "note_id": note_id,
                                "username": name,
                                "confirmed_at": get_now().strftime("%m-%d %H:%M")
                            }, None, "인폼 확인")
                            st.rerun()
                    else:
                        st.success("확인 완료")
                with c_stat:
                    with st.expander(f"확인자 ({len(confirmed_list)}명)"):
                        st.write(", ".join(confirmed_list) if confirmed_list else "-")

def page_staff_mgmt():
    st.subheader("👥 직원 관리")
    res = DataManager.load("users", force_refresh=True)
    if not res.success:
        st.error("데이터 로드 실패")
        return

    users = res.data
    if users.empty:
        st.warning("데이터 없음")
        return

    # 승인 대기
    pending = users[users["approved"].apply(lambda x: not check_approved(x))]
    if not pending.empty:
        st.info(f"승인 대기: {len(pending)}명")
        for _, u in pending.iterrows():
            c1, c2, c3 = st.columns([2,1,1])
            c1.write(f"{u['name']} ({u['username']}) - {u.get('department','-')}")
            if c2.button("✅ 승인", key=f"app_{u['username']}"):
                DataManager.update_row("users", "username", u['username'], {"approved": "True"}, "직원 승인")
                st.rerun()
            if c3.button("❌ 거절", key=f"rej_{u['username']}"):
                DataManager.delete_row("users", "username", u['username'], "직원 거절")
                st.rerun()
    
    st.divider()
    
    # 직원 목록
    active = users[users["approved"].apply(check_approved)]
    if not active.empty:
        st.write("직원 목록")
        for _, u in active.iterrows():
            if u['username'] == st.session_state['name']: continue
            with st.expander(f"{u['name']} ({u['role']} / {u.get('department','-')})"):
                with st.form(f"edit_{u['username']}"):
                    new_role = st.selectbox("직급", ["Master", "Manager", "Staff"], index=["Master", "Manager", "Staff"].index(u['role']))
                    if st.form_submit_button("수정"):
                        DataManager.update_row("users", "username", u['username'], {"role": new_role}, "직급 수정")
                        st.rerun()

def page_board(b_name: str, icon: str):
    st.subheader(f"{icon} {b_name}")
    name = st.session_state['name']
    role = st.session_state['role']
    
    can_write = (role in ["Master", "Manager"]) or (b_name == "건의사항")
    
    if can_write:
        with st.expander("✏️ 글쓰기"):
            with st.form(f"w_{b_name}"):
                tt = st.text_input("제목")
                ct = st.text_area("내용")
                if st.form_submit_button("등록", use_container_width=True):
                    if tt and ct:
                        DataManager.append_row("posts", {
                            "board_type": b_name,
                            "title": tt,
                            "content": ct,
                            "author": name,
                            "date": get_now().strftime("%Y-%m-%d")
                        }, "id", "게시글 등록")
                        st.rerun()
    
    res = DataManager.load("posts")
    if res.success and not res.data.empty:
        posts = res.data
        if "board_type" in posts.columns:
            mp = posts[posts["board_type"].astype(str).str.strip() == b_name]
            mp = mp.sort_values("id", ascending=False)
            
            for _, r in mp.iterrows():
                with st.expander(f"{r['title']} ({r['author']} | {r['date']})"):
                    st.write(r['content'])
                    if role == "Master" or r['author'] == name:
                        if st.button("삭제", key=f"del_{r['id']}"):
                            DataManager.delete_row("posts", "id", r['id'], "삭제")
                            st.rerun()
                            
                    # 댓글 (약식)
                    cmts = DataManager.load("comments").data
                    if not cmts.empty:
                        pc = cmts[cmts["post_id"].astype(str) == str(r['id'])]
                        for _, c in pc.iterrows():
                            st.caption(f"{c['author']}: {c['content']}")
                    
                    with st.form(f"c_{r['id']}"):
                        ctxt = st.text_input("댓글", label_visibility="collapsed")
                        if st.form_submit_button("등록"):
                            DataManager.append_row("comments", {
                                "post_id": r['id'],
                                "author": name,
                                "content": ctxt,
                                "date": get_now().strftime("%m-%d %H:%M")
                            }, None, "댓글")
                            st.rerun()

def page_routine():
    st.subheader("🔄 업무 체크")
    name = st.session_state['name']
    today_str = get_today_str()
    
    res_def = DataManager.load("routine_def")
    res_log = DataManager.load("routine_log")
    
    t1, t2 = st.tabs(["오늘 업무", "기록"])
    
    with t1:
        if st.session_state['role'] in ["Master", "Manager"]:
            with st.expander("업무 추가"):
                with st.form("new_r"):
                    tn = st.text_input("업무명")
                    # [변경] 한국 시간
                    sd = st.date_input("시작일", value=get_now().date())
                    cy = st.selectbox("주기", ["매일", "매주", "매월"])
                    if st.form_submit_button("추가"):
                        DataManager.append_row("routine_def", {
                            "task_name": tn,
                            "start_date": sd.strftime("%Y-%m-%d"),
                            "cycle_type": cy,
                            "interval_val": 1
                        }, "id", "업무 추가")
                        st.rerun()
        
        tasks = get_pending_tasks_list()
        if not tasks:
            st.success("완료!")
        else:
            for t in tasks:
                st.markdown(f"**{t['task_name']}** ({t['cycle_type']})")
                with st.form(f"do_{t['id']}"):
                    mm = st.text_input("메모", placeholder="특이사항")
                    if st.form_submit_button("완료"):
                        DataManager.append_row("routine_log", {
                            "task_id": t['id'],
                            "done_date": today_str,
                            "worker": name,
                            "memo": mm,
                            "created_at": get_now().strftime("%H:%M")
                        }, None, "완료")
                        st.rerun()
    
    with t2:
        if res_log.success and res_def.success:
            logs = res_log.data
            defs = res_def.data
            if not logs.empty and not defs.empty:
                logs['task_id'] = logs['task_id'].astype(str)
                defs['id'] = defs['id'].astype(str)
                m = pd.merge(logs, defs, left_on='task_id', right_on='id', how='left')
                st.dataframe(m[['done_date', 'task_name', 'worker', 'memo']].sort_values('done_date', ascending=False), hide_index=True)

# ============================================================
# [10. 메인 앱]
# ============================================================
def main():
    AppState.init()
    
    # 자동 로그인 체크
    if not st.session_state.get("logged_in"):
        if cookies.get("auto_login") == "true":
            try:
                res = DataManager.load("users")
                if res.success and not res.data.empty:
                    users = res.data
                    users["username"] = users["username"].astype(str)
                    u = users[users["username"] == cookies["uid"]]
                    if not u.empty and check_approved(u.iloc[0]["approved"]):
                        st.session_state.update({
                            "logged_in": True,
                            "name": u.iloc[0]["name"],
                            "role": u.iloc[0]["role"],
                            "department": u.iloc[0].get("department", "전체")
                        })
            except:
                pass
    
    if not st.session_state.get("logged_in"):
        login_page()
        return
    
    # 헤더
    show_network_status()
    processed_logo_header = get_processed_logo("logo.png", icon_size=(35, 35))
    
    cols = st.columns([0.8, 4, 1, 1])
    with cols[0]:
        if processed_logo_header:
            st.image(processed_logo_header, width=35)
    with cols[1]:
        st.markdown(f"**{st.session_state['name']}** ({st.session_state.get('department','전체')})")
    with cols[2]:
        if st.button("🔍", key="search_btn"):
            st.session_state["show_search"] = not st.session_state.get("show_search", False)
            st.rerun()
    with cols[3]:
        if st.button("🔄", key="refresh_btn"):
            DataManager.clear_cache()
            st.rerun()

    if st.session_state.get("show_search"):
        show_search()
        st.divider()

    show_pending_saves_retry()
    
    # 메뉴
    menu_opts = ["홈", "인폼", "본점", "작업", "건의", "체크", "로그아웃"]
    menu_icons = ["house-fill", "megaphone-fill", "shop", "tools", "chat-dots", "check2-square", "box-arrow-right"]
    
    if st.session_state['role'] == "Master":
        menu_opts.insert(-1, "관리")
        menu_icons.insert(-1, "people-fill")
        
    m = option_menu(None, menu_opts, icons=menu_icons, menu_icon="cast", default_index=0, orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#FFF3E0", "margin": "0"},
            "nav-link": {"font-size": "10px", "text-align": "center", "margin": "0px", "padding": "8px 6px"}
        }
    )
    
    if m == "로그아웃":
        st.session_state["logged_in"] = False
        cookies["auto_login"] = "false"
        cookies.save()
        st.rerun()
    elif m == "홈": show_dashboard()
    elif m == "인폼": page_inform()
    elif m == "본점": page_board("본점", "🏠")
    elif m == "작업": page_board("작업장", "🏭")
    elif m == "건의": page_board("건의사항", "💡")
    elif m == "체크": page_routine()
    elif m == "관리": page_staff_mgmt()

    # 로그인 직후 팝업
    if st.session_state.get("show_popup_on_login"):
        pt = get_pending_tasks_list()
        uc = get_unconfirmed_inform_list(st.session_state['name'])
        if pt or uc:
            show_notification_popup(pt, uc)
        st.session_state["show_popup_on_login"] = False

if __name__ == "__main__":
    main()
