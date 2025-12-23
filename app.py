import streamlit as st
import pandas as pd
import hashlib
import time
import io
import base64
import uuid
import pytz
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
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
KST = pytz.timezone("Asia/Seoul")

def get_now():
    return datetime.now(KST)

def get_today_str():
    return get_now().strftime("%Y-%m-%d")

def now_str(fmt="%Y-%m-%d %H:%M:%S"):
    return get_now().strftime(fmt)

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
    "inform_logs": "inform_logs",
    # (선택) 토큰 자동로그인용 신규 시트 - 있으면 사용, 없으면 기존 방식 fallback
    "sessions": "sessions",
}

DEPARTMENTS = ["전체", "본점", "작업장"]
POST_STATUS = ["접수", "진행중", "완료", "보류"]

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
            "name": "",          # 표시용 이름
            "username": "",      # 로그인 ID
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
            # [추가] 홈/팝업 최소 프리패치 완료 플래그
            "boot_home_loaded": False,
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
    initial_sidebar_state="collapsed",
)

processed_icon = get_processed_logo("logo.png", icon_size=(192, 192))
if processed_icon:
    icon_base64 = image_to_base64(processed_icon)
    st.markdown(
        f"""
        <head>
            <link rel="apple-touch-icon" sizes="180x180" href="data:image/png;base64,{icon_base64}">
            <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,{icon_base64}">
        </head>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
@import url("https://fonts.googleapis.com/icon?family=Material+Icons");

html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; color: #333333; }

.material-icons,
[data-testid="stExpanderToggleIcon"] > svg,
[data-testid="stExpanderToggleIcon"] { font-family: 'Material Icons' !important; }

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

.stApp { background-color: #FFF3E0; }

header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stStatusWidget"] { display: none; }

.summary-container {
    display: flex; flex-direction: row; justify-content: space-between;
    gap: 10px; margin-bottom: 15px; overflow-x: auto;
}
.summary-card {
    flex: 1; background: white; border-radius: 12px; padding: 12px;
    text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    min-width: 90px;
}
.summary-title { font-size: 0.8rem; color: #666; margin-bottom: 5px; }
.summary-value { font-size: 1.5rem; font-weight: bold; color: #333; }
.summary-alert { color: #D32F2F !important; }

.inform-item {
    background: white; border-left: 4px solid #8D6E63;
    padding: 10px; margin-bottom: 8px; border-radius: 4px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.inform-urgent { border-left-color: #D32F2F; background-color: #FFEBEE; }

.logo-title-container { display: flex; align-items: center; justify-content: center; margin-bottom: 10px; }
.logo-title-container h1 { margin: 0 0 0 10px; font-size: 1.5rem; color: #4E342E; }

.network-status {
    position: fixed; top: 10px; right: 10px; padding: 5px 10px;
    border-radius: 20px; font-size: 0.75rem; z-index: 9999;
    background: #FFEBEE; color: #C62828; border: 1px solid #FFCDD2;
}

button[data-baseweb="tab"] { font-size: 0.9rem !important; }

/* 게시글 배지 */
.badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:0.75rem; margin-right:6px; }
.badge-ok { background:#E8F5E9; color:#2E7D32; border:1px solid #C8E6C9; }
.badge-wip { background:#FFF3E0; color:#E65100; border:1px solid #FFE0B2; }
.badge-hold { background:#ECEFF1; color:#455A64; border:1px solid #CFD8DC; }
.badge-new { background:#E3F2FD; color:#1565C0; border:1px solid #BBDEFB; }
</style>
""",
    unsafe_allow_html=True,
)

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
    except:
        return None

def safe_set_cookie(key, val):
    if cookies is None:
        return
    try:
        cookies[key] = val
        cookies.save()
    except:
        pass

# ============================================================
# [5. DataManager - 충돌 완화 + 캐시 + (홈/팝업) 최소 프리패치]
# ============================================================
class DataManager:
    CACHE_TTL = 600

    # append-like: row_uuid 기반 union merge 저장으로 동시저장 덮어쓰기 완화
    APPEND_LIKE_KEYS = {"posts", "comments", "routine_log", "inform_logs", "inform_notes"}

    @staticmethod
    def _is_cache_valid(key: str) -> bool:
        cache_time = st.session_state.get("cache_time", {}).get(key)
        if cache_time is None:
            return False
        return (get_now() - cache_time).total_seconds() < DataManager.CACHE_TTL

    @staticmethod
    def _get_from_cache(key: str) -> Optional[pd.DataFrame]:
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
    def _normalize_df(key: str, df: pd.DataFrame) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()
        if not df.empty:
            df.columns = df.columns.str.strip()
        if key == "users" and (df is not None) and (not df.empty) and ("username" not in df.columns):
            raise ValueError("users 헤더 오류(username 없음)")
        return df

    @staticmethod
    def _sheet_exists(key: str) -> bool:
        try:
            _ = conn.read(worksheet=SHEET_NAMES[key], ttl=0)
            return True
        except Exception:
            return False

    @staticmethod
    def load(key: str, force_refresh: bool = False) -> LoadResult:
        if not force_refresh:
            cached = DataManager._get_from_cache(key)
            if cached is not None:
                return LoadResult(data=cached, success=True)

        for _ in range(3):
            try:
                df = conn.read(worksheet=SHEET_NAMES[key], ttl=0)
                df = DataManager._normalize_df(key, df)
                DataManager._set_cache(key, df)
                return LoadResult(data=df, success=True)
            except Exception:
                time.sleep(0.5)
                continue

        cached = st.session_state.get("data_cache", {}).get(key)
        if cached is not None:
            return LoadResult(data=cached, success=False, error_msg="캐시 사용")
        return LoadResult(data=pd.DataFrame(), success=False, error_msg="로드 실패")

    @staticmethod
    def _merge_append_like(latest: pd.DataFrame, mine: pd.DataFrame, unique_col: str = "row_uuid") -> pd.DataFrame:
        if latest is None or latest.empty:
            return mine.copy() if mine is not None else pd.DataFrame()
        if mine is None or mine.empty:
            return latest.copy()

        a = latest.copy()
        b = mine.copy()

        if unique_col not in a.columns:
            a[unique_col] = [str(uuid.uuid4()) for _ in range(len(a))]
        if unique_col not in b.columns:
            b[unique_col] = [str(uuid.uuid4()) for _ in range(len(b))]

        merged = pd.concat([a, b], ignore_index=True)
        merged[unique_col] = merged[unique_col].astype(str)
        merged = merged.drop_duplicates(subset=[unique_col], keep="last")
        return merged

    @staticmethod
    def save(key: str, df: pd.DataFrame, operation_desc: str = "") -> SaveResult:
        # users 대량삭제 보호(기존 유지)
        if key == "users":
            cached = st.session_state.get("data_cache", {}).get(key)
            if cached is not None and not cached.empty:
                if len(df) < len(cached) * 0.5:
                    return SaveResult(success=False, error_msg="데이터 보호: 대량 삭제 감지됨")

        for _ in range(3):
            try:
                if key in DataManager.APPEND_LIKE_KEYS:
                    latest = DataManager.load(key, force_refresh=True).data
                    df_to_save = DataManager._merge_append_like(latest, df, unique_col="row_uuid")
                else:
                    df_to_save = df

                conn.update(worksheet=SHEET_NAMES[key], data=df_to_save)
                DataManager._set_cache(key, df_to_save)
                return SaveResult(success=True)
            except Exception:
                time.sleep(0.5)
                continue

        pending = st.session_state.get("pending_saves", [])
        pending.append(
            {"key": key, "data": df.to_dict(), "operation": operation_desc, "timestamp": get_now().isoformat()}
        )
        st.session_state["pending_saves"] = pending[-10:]
        return SaveResult(success=False, error_msg="저장 실패")

    @staticmethod
    def append_row(key: str, new_row: dict, id_column: str = "id", operation_desc: str = "") -> SaveResult:
        if key in DataManager.APPEND_LIKE_KEYS:
            new_row.setdefault("row_uuid", str(uuid.uuid4()))

        for _ in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success and result.data.empty:
                time.sleep(0.5)
                continue

            current_df = result.data

            if id_column and id_column not in new_row:
                if current_df.empty:
                    new_row[id_column] = 1
                else:
                    try:
                        max_id = pd.to_numeric(current_df[id_column], errors="coerce").fillna(0).max()
                        new_row[id_column] = int(max_id) + 1
                    except:
                        new_row[id_column] = len(current_df) + 1

            new_df = pd.DataFrame([new_row])
            updated_df = pd.concat([current_df, new_df], ignore_index=True) if not current_df.empty else new_df
            save_result = DataManager.save(key, updated_df, operation_desc)
            if save_result.success:
                return save_result
            time.sleep(0.5)

        return SaveResult(success=False, error_msg="저장 실패")

    @staticmethod
    def update_row(key: str, match_column: str, match_value: Any, updates: dict, operation_desc: str = "") -> SaveResult:
        for _ in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(0.5)
                continue

            current_df = result.data.copy()
            if current_df.empty or match_column not in current_df.columns:
                return SaveResult(success=False, error_msg="대상 없음")

            mask = current_df[match_column].astype(str) == str(match_value)
            if not mask.any():
                return SaveResult(success=False, error_msg="대상 없음")

            for col, val in updates.items():
                current_df.loc[mask, col] = val

            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success:
                return save_result
            time.sleep(0.5)

        return SaveResult(success=False, error_msg="수정 실패")

    @staticmethod
    def delete_row(key: str, match_column: str, match_value: Any, operation_desc: str = "") -> SaveResult:
        for _ in range(3):
            result = DataManager.load(key, force_refresh=True)
            if not result.success:
                time.sleep(0.5)
                continue

            current_df = result.data.copy()
            if current_df.empty or match_column not in current_df.columns:
                return SaveResult(success=False, error_msg="삭제 실패(컬럼 없음)")

            current_df = current_df[current_df[match_column].astype(str) != str(match_value)]
            save_result = DataManager.save(key, current_df, operation_desc)
            if save_result.success:
                return save_result
            time.sleep(0.5)

        return SaveResult(success=False, error_msg="삭제 실패")

    @staticmethod
    def retry_pending_saves() -> Tuple[int, int]:
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

    # ---------- 프리패치 ----------
    @staticmethod
    def prefetch(keys: List[str]):
        """지정 시트만 병렬 로드"""
        def load_one(k):
            try:
                DataManager.load(k)
            except:
                pass

        with ThreadPoolExecutor() as ex:
            ex.map(load_one, keys)

    @staticmethod
    def prefetch_home_popup():
        """로그인 직후 홈/팝업에 필요한 최소 시트만 먼저 로드 (속도 핵심)"""
        keys = ["routine_def", "routine_log", "inform_notes", "inform_logs"]
        # 홈에서 댓글/멘션까지 로그인 직후 즉시 보여주고 싶으면 아래 두 줄 활성화
        # keys += ["posts", "comments"]
        if DataManager._sheet_exists("sessions"):
            keys.append("sessions")
        DataManager.prefetch(keys)

    @staticmethod
    def prefetch_all_data():
        """기존 전체 프리패치 (필요한 시점에만 호출 권장)"""
        target_sheets = ["users", "routine_def", "routine_log", "inform_notes", "inform_logs", "posts", "comments"]
        if DataManager._sheet_exists("sessions"):
            target_sheets.append("sessions")
        DataManager.prefetch(target_sheets)

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
    return re.sub(r"@(\S+)", r'<span style="color:#1565C0; font-weight:bold;">@\1</span>', str(text))

def badge_for_status(status: str) -> str:
    s = (status or "").strip()
    if s == "완료":
        return '<span class="badge badge-ok">완료</span>'
    if s == "진행중":
        return '<span class="badge badge-wip">진행중</span>'
    if s == "보류":
        return '<span class="badge badge-hold">보류</span>'
    return '<span class="badge badge-new">접수</span>'

# ============================================================
# [7. 비즈니스 로직 - (팝업/홈) 최적화 버전]
# ============================================================
def get_pending_tasks_list() -> List[dict]:
    """
    (속도 개선) 루프 기반 필터링 -> pandas 벡터화 + set membership
    """
    res_def = DataManager.load("routine_def")
    res_log = DataManager.load("routine_log")
    if not res_def.success or res_def.data.empty:
        return []

    defs = res_def.data.copy()
    logs = res_log.data.copy() if res_log.success and not res_log.data.empty else pd.DataFrame()

    # 컬럼 방어
    need_cols = ["id", "task_name", "start_date", "cycle_type"]
    for c in need_cols:
        if c not in defs.columns:
            return []

    today = get_now().date()
    today_str = get_today_str()

    defs["start_date_dt"] = pd.to_datetime(defs["start_date"], errors="coerce").dt.date
    defs = defs[defs["start_date_dt"].notna()]
    defs = defs[defs["start_date_dt"] <= today]
    if defs.empty:
        return []

    delta = (pd.to_datetime(today) - pd.to_datetime(defs["start_date_dt"])).dt.days

    due = pd.Series(False, index=defs.index)
    due |= (defs["cycle_type"] == "매일")
    due |= (defs["cycle_type"] == "매주") & (delta % 7 == 0)
    due |= (defs["cycle_type"] == "매월") & (pd.Series([today.day] * len(defs), index=defs.index) ==
                                             pd.Series([d.day for d in defs["start_date_dt"]], index=defs.index))

    if "interval_val" in defs.columns:
        iv = pd.to_numeric(defs["interval_val"], errors="coerce").fillna(1).astype(int)
        due |= (defs["cycle_type"] == "N일 간격") & (delta % iv == 0)

    due_defs = defs[due].copy()
    if due_defs.empty:
        return []

    done_ids = set()
    if not logs.empty and ("task_id" in logs.columns) and ("done_date" in logs.columns):
        done_ids = set(
            logs.loc[logs["done_date"].astype(str) == today_str, "task_id"].astype(str).tolist()
        )

    due_defs["id_str"] = due_defs["id"].astype(str)
    pending = due_defs[~due_defs["id_str"].isin(done_ids)]
    return pending.drop(columns=["start_date_dt", "id_str"], errors="ignore").to_dict("records")

def get_unconfirmed_inform_list(username: str) -> List[dict]:
    """
    (속도 개선) 오늘 인폼 + 내 확인 로그만 set으로 빠르게 계산
    """
    res_n = DataManager.load("inform_notes")
    res_l = DataManager.load("inform_logs")

    if not res_n.success or res_n.data.empty:
        return []

    notes = res_n.data.copy()
    if "target_date" not in notes.columns or "id" not in notes.columns:
        return []

    today_str = get_today_str()
    today_notes = notes[notes["target_date"].astype(str) == today_str].copy()
    if today_notes.empty:
        return []

    logs = res_l.data.copy() if res_l.success and not res_l.data.empty else pd.DataFrame()
    if logs.empty or "note_id" not in logs.columns or "username" not in logs.columns:
        return today_notes.to_dict("records")

    note_ids = today_notes["id"].astype(str)
    my_checked = set(
        logs.loc[
            (logs["username"].astype(str) == str(username)) &
            (logs["note_id"].astype(str).isin(note_ids)),
            "note_id"
        ].astype(str).tolist()
    )

    unconfirmed = today_notes[~today_notes["id"].astype(str).isin(my_checked)]
    return unconfirmed.to_dict("records")

def get_new_comments_count(username: str) -> int:
    res_posts = DataManager.load("posts")
    res_comments = DataManager.load("comments")
    if not res_posts.success or not res_comments.success:
        return 0
    posts, comments = res_posts.data, res_comments.data
    if posts.empty or comments.empty or "author" not in posts.columns:
        return 0
    my_posts = posts[posts["author"] == username]["id"].astype(str).tolist()
    today_mmdd = get_now().strftime("%m-%d")
    if "date" not in comments.columns:
        return 0
    new_comments = comments[
        (comments["post_id"].astype(str).isin(my_posts)) &
        (comments["date"].astype(str).str.contains(today_mmdd, na=False)) &
        (comments["author"] != username)
    ]
    return len(new_comments)

def get_mentions_for_user(username: str) -> List[dict]:
    comments = DataManager.load("comments").data
    if comments.empty:
        return []
    mentions = []
    for _, c in comments.iterrows():
        if f"@{username}" in str(c.get("content", "")):
            mentions.append(dict(c))
    return mentions

def search_content(query: str) -> Dict[str, List[dict]]:
    results = {"inform": [], "posts": []}
    query = query.lower().strip()
    if not query:
        return results
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
        st.markdown(
            f'<div class="network-status network-error">📡 저장 대기: {len(pending_saves)}</div>',
            unsafe_allow_html=True,
        )

def show_pending_saves_retry():
    pending = st.session_state.get("pending_saves", [])
    if pending:
        with st.expander(f"📡 저장 실패 항목 ({len(pending)}건)", expanded=True):
            for item in pending:
                ts = item["timestamp"][5:16]
                st.write(f"- {item['operation']} ({ts})")
            st.markdown('<div class="retry-btn">', unsafe_allow_html=True)
            if st.button("🔄 재시도", key="retry_pending"):
                with st.spinner("재시도 중..."):
                    success, fail = DataManager.retry_pending_saves()
                    if success > 0:
                        st.success(f"✅ {success}건 완료")
                    if fail > 0:
                        st.error(f"❌ {fail}건 실패")
                    time.sleep(1)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

@st.dialog("🚨 중요 알림")
def show_notification_popup(tasks: List[dict], inform_notes: List[dict]):
    if inform_notes:
        urgent = [n for n in inform_notes if n.get("priority") == "긴급"]
        if urgent:
            st.error(f"🚨 **긴급 필독 ({len(urgent)}건)**")
            for note in urgent:
                st.markdown(f"**📌 {str(note.get('content',''))[:50]}...**")
    if tasks:
        st.info(f"🔄 **오늘의 반복 업무 ({len(tasks)}건)**")
        for t in tasks:
            st.write(f"• {t.get('task_name','')}")
    if st.button("확인", use_container_width=True):
        st.rerun()

def show_dashboard():
    username = st.session_state["name"]

    pending_tasks = get_pending_tasks_list()
    unconfirmed_informs = get_unconfirmed_inform_list(username)
    new_comments = get_new_comments_count(username)
    mentions = get_mentions_for_user(username)

    st.subheader("📊 오늘의 현황")

    urgent_cnt = len([i for i in unconfirmed_informs if i.get("priority") == "긴급"])
    inform_color = "summary-alert" if urgent_cnt > 0 else ""

    st.markdown(
        f"""
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
        """,
        unsafe_allow_html=True,
    )

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

        if view == "inform":
            page_inform()
        elif view == "task":
            page_routine()
        elif view == "notification":
            st.info("알림 내역")
            if mentions:
                st.write("나를 멘션한 댓글:")
                for m in mentions:
                    st.markdown(f'- {m.get("content","")}')
            elif new_comments:
                st.write("새 댓글이 있습니다.")
            else:
                st.write("새로운 알림이 없습니다.")

def show_search():
    st.subheader("🔍 검색")
    query = st.text_input("검색어 입력")
    if query:
        with st.spinner("검색 중..."):
            res = search_content(query)
        st.write(f"결과: {len(res['inform']) + len(res['posts'])}건")
        if res["inform"]:
            with st.expander(f"인폼 ({len(res['inform'])})"):
                for i in res["inform"]:
                    st.write(f"[{i.get('target_date','')}] {i.get('content','')}")
        if res["posts"]:
            with st.expander(f"게시글 ({len(res['posts'])})"):
                for p in res["posts"]:
                    st.write(f"[{p.get('board_type','')}] {p.get('title','')} - {p.get('author','')}")

# ============================================================
# [9. 세션(토큰 자동로그인) 로직]
# ============================================================
def sessions_available() -> bool:
    return DataManager._sheet_exists("sessions")

def create_session_token(username: str, days_valid: int = 30) -> Optional[str]:
    if not sessions_available():
        return None
    token = str(uuid.uuid4())
    created = now_str()
    expires = (get_now() + timedelta(days=days_valid)).strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "token": token,
        "username": username,
        "created_at": created,
        "expires_at": expires,
        "revoked": "False",
        "row_uuid": str(uuid.uuid4()),
    }
    DataManager.append_row("sessions", row, None, "세션생성")
    return token

def revoke_session_token(token: str):
    if not token or not sessions_available():
        return
    DataManager.update_row("sessions", "token", token, {"revoked": "True"}, "세션폐기")

def validate_session_token(token: str) -> Optional[str]:
    if not token or not sessions_available():
        return None
    df = DataManager.load("sessions", force_refresh=True).data
    if df.empty or "token" not in df.columns:
        return None
    row = df[df["token"].astype(str) == str(token)]
    if row.empty:
        return None
    r = row.iloc[-1].to_dict()
    if str(r.get("revoked", "False")).strip().lower() in ["true", "1", "yes", "y", "t"]:
        return None
    exp = str(r.get("expires_at", "")).strip()
    if not exp:
        return None
    try:
        exp_dt = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        if get_now() > exp_dt:
            return None
    except:
        return None
    return str(r.get("username", "")).strip() or None

# ============================================================
# [10. 페이지 함수]
# ============================================================
def login_page():
    st.markdown("<br>", unsafe_allow_html=True)
    processed_logo = get_processed_logo("logo.png", icon_size=(80, 80))
    if processed_logo:
        st.markdown(
            f"""
            <div class="logo-title-container">
                <img src="data:image/png;base64,{image_to_base64(processed_logo)}" style="max-height: 80px;">
                <h1>업무수첩</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )
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
                            st.session_state.update(
                                {
                                    "logged_in": True,
                                    "username": uid,
                                    "name": u.iloc[0]["name"],
                                    "role": u.iloc[0]["role"],
                                    "department": u.iloc[0].get("department", "전체"),
                                    "show_popup_on_login": True,
                                    "boot_home_loaded": False,  # 로그인 시 첫 홈 최적화를 위해 초기화
                                }
                            )

                            if auto and cookies:
                                token = create_session_token(uid)
                                if token:
                                    safe_set_cookie("auto_login", "true")
                                    safe_set_cookie("session_token", token)
                                    safe_set_cookie("uid", uid)  # 보조
                                else:
                                    # fallback(기존 방식 유지)
                                    safe_set_cookie("auto_login", "true")
                                    safe_set_cookie("uid", uid)
                                    safe_set_cookie("upw", hpw)

                            st.rerun()
                        else:
                            st.warning("⏳ 승인 대기 중입니다.")
                    else:
                        st.error("정보가 일치하지 않습니다.")
                else:
                    st.error("서버 연결 실패")

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
                        if not users.empty:
                            users.columns = users.columns.str.strip()
                        if not users.empty and nid in users["username"].astype(str).values:
                            st.error("이미 있는 아이디입니다.")
                        else:
                            new_row = {
                                "username": nid,
                                "password": hash_password(npw),
                                "name": nname,
                                "role": "Staff",
                                "approved": "False",
                                "department": ndept,
                            }
                            DataManager.append_row("users", new_row, None, "가입신청")
                            st.success("신청 완료! 승인을 기다려주세요.")
                    else:
                        st.error("오류")
                else:
                    st.warning("모두 입력해주세요")

def page_inform():
    st.subheader("📢 인폼노트")
    if "inform_date" not in st.session_state:
        st.session_state["inform_date"] = get_now().date()

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("◀", use_container_width=True):
            st.session_state["inform_date"] -= timedelta(days=1)
            st.rerun()
    with c2:
        st.session_state["inform_date"] = st.date_input(
            "날짜", value=st.session_state["inform_date"], label_visibility="collapsed"
        )
    with c3:
        if st.button("▶", use_container_width=True):
            st.session_state["inform_date"] += timedelta(days=1)
            st.rerun()

    sel_date = st.session_state["inform_date"].strftime("%Y-%m-%d")
    name = st.session_state["name"]

    if st.session_state["role"] in ["Master", "Manager"]:
        with st.expander("📝 작성"):
            with st.form("new_inf"):
                td = st.date_input("날짜", value=st.session_state["inform_date"])
                pr = st.radio("중요도", ["일반", "긴급"], horizontal=True)
                ct = st.text_area("내용")
                if st.form_submit_button("등록", use_container_width=True):
                    DataManager.append_row(
                        "inform_notes",
                        {
                            "target_date": td.strftime("%Y-%m-%d"),
                            "content": ct,
                            "author": name,
                            "priority": pr,
                            "created_at": get_now().strftime("%Y-%m-%d %H:%M"),
                        },
                        "id",
                        "인폼",
                    )
                    st.rerun()

    res_n = DataManager.load("inform_notes")
    res_l = DataManager.load("inform_logs")
    if res_n.success and not res_n.data.empty:
        notes = res_n.data
        if "target_date" not in notes.columns:
            st.info("인폼 컬럼(target_date) 없음")
            return

        daily = notes[notes["target_date"].astype(str) == sel_date]
        if daily.empty:
            st.info("인폼 없음")
        else:
            daily = sorted(daily.to_dict("records"), key=lambda x: 0 if x.get("priority") == "긴급" else 1)
            logs = res_l.data if res_l.success else pd.DataFrame()

            for n in daily:
                nid = str(n.get("id", ""))
                urgent = n.get("priority") == "긴급"
                cls = "inform-item inform-urgent" if urgent else "inform-item"
                badge = "🚨 긴급" if urgent else ""

                st.markdown(
                    f"""
                    <div class="{cls}">
                        <div style="font-weight:bold; margin-bottom:5px;">{n.get("author","")} <span style="color:red">{badge}</span></div>
                        <div style="white-space:pre-wrap;">{highlight_mentions(n.get("content",""))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                conf = []
                if not logs.empty and "note_id" in logs.columns and "username" in logs.columns:
                    conf = logs[logs["note_id"].astype(str) == nid]["username"].tolist()

                c_btn, c_st = st.columns([1, 2])
                with c_btn:
                    if name not in conf:
                        if st.button("확인함 ✅", key=f"ok_{nid}"):
                            DataManager.append_row(
                                "inform_logs",
                                {
                                    "note_id": nid,
                                    "username": name,
                                    "confirmed_at": get_now().strftime("%m-%d %H:%M"),
                                },
                                None,
                                "확인",
                            )
                            st.rerun()
                    else:
                        st.success("확인됨")
                with c_st:
                    with st.expander(f"확인자 ({len(conf)})"):
                        st.write(", ".join(conf) if conf else "-")

def page_routine():
    st.subheader("🔄 업무 체크")
    name = st.session_state["name"]
    t1, t2 = st.tabs(["📋 오늘 업무", "📊 기록/관리"])

    with t1:
        tasks = get_pending_tasks_list()
        if not tasks:
            st.success("🎉 오늘의 업무를 모두 완료했습니다!")
        else:
            for t in tasks:
                st.markdown(f"**{t.get('task_name','')}** <small>({t.get('cycle_type','')})</small>", unsafe_allow_html=True)
                with st.form(f"do_{t.get('id','')}"):
                    mm = st.text_input("메모", placeholder="특이사항")
                    if st.form_submit_button("완료 ✅", use_container_width=True):
                        DataManager.append_row(
                            "routine_log",
                            {
                                "task_id": t.get("id", ""),
                                "done_date": get_today_str(),
                                "worker": name,
                                "memo": mm,
                                "created_at": get_now().strftime("%H:%M"),
                            },
                            None,
                            "완료",
                        )
                        st.rerun()
                st.divider()

    with t2:
        if st.session_state["role"] in ["Master", "Manager"]:
            with st.expander("➕ 새 업무 추가"):
                with st.form("nr"):
                    tn = st.text_input("업무명")
                    sd = st.date_input("시작일", value=get_now().date())
                    cy = st.selectbox("주기", ["매일", "매주", "매월"])
                    if st.form_submit_button("추가"):
                        new_id = int(time.time())
                        DataManager.append_row(
                            "routine_def",
                            {
                                "id": new_id,
                                "task_name": tn,
                                "start_date": sd.strftime("%Y-%m-%d"),
                                "cycle_type": cy,
                                "interval_val": 1,
                            },
                            "id",
                            "추가",
                        )
                        st.rerun()

        res_def = DataManager.load("routine_def")
        if res_def.success and not res_def.data.empty:
            df = res_def.data
            cycles = ["매일", "매주", "매월"]
            tabs = st.tabs(cycles)
            for i, cy in enumerate(cycles):
                with tabs[i]:
                    if "cycle_type" not in df.columns:
                        st.info("routine_def 컬럼(cycle_type) 없음")
                        continue
                    sub = df[df["cycle_type"] == cy]
                    for _, r in sub.iterrows():
                        col_txt, col_btn = st.columns([3, 1])
                        col_txt.write(f"**{r.get('task_name','')}** ({r.get('start_date','')}~)")
                        if st.session_state["role"] in ["Master", "Manager"]:
                            if col_btn.button("삭제", key=f"del_{r.get('id','')}_{cy}"):
                                DataManager.delete_row("routine_def", "id", r.get("id", ""), "삭제")
                                st.rerun()

        st.divider()
        st.caption("📋 최근 완료 기록")
        logs = DataManager.load("routine_log").data
        defs = DataManager.load("routine_def").data
        if not logs.empty and not defs.empty and "task_id" in logs.columns and "id" in defs.columns:
            logs["task_id"] = logs["task_id"].astype(str)
            defs["id"] = defs["id"].astype(str)
            m = pd.merge(logs, defs, left_on="task_id", right_on="id", how="left")
            show_cols = [c for c in ["done_date", "task_name", "worker", "memo"] if c in m.columns]
            if show_cols:
                st.dataframe(
                    m[show_cols].sort_values("done_date", ascending=False).head(50),
                    hide_index=True,
                    use_container_width=True,
                )

# ---------------------------
# 게시판: 댓글 로딩 최적화 + 상태/담당자/마감
# ---------------------------
def page_board(bn, icon):
    st.subheader(f"{icon} {bn}")
    name = st.session_state["name"]

    if st.session_state["role"] in ["Master", "Manager"] or bn == "건의사항":
        with st.expander("글쓰기"):
            with st.form(f"w_{bn}"):
                tt = st.text_input("제목")
                ct = st.text_area("내용")

                status = "접수"
                assignee = ""
                due_date = ""
                if st.session_state["role"] in ["Master", "Manager"]:
                    cA, cB, cC = st.columns([1, 1, 1])
                    with cA:
                        status = st.selectbox("상태", POST_STATUS, index=0)
                    with cB:
                        assignee = st.text_input("담당자(이름)", placeholder="예: 김OO")
                    with cC:
                        d = st.date_input("마감(선택)", value=None)
                        due_date = d.strftime("%Y-%m-%d") if d else ""

                if st.form_submit_button("등록", use_container_width=True):
                    DataManager.append_row(
                        "posts",
                        {
                            "board_type": bn,
                            "title": tt,
                            "content": ct,
                            "author": name,
                            "date": get_now().strftime("%Y-%m-%d"),
                            "status": status,
                            "assignee": assignee,
                            "due_date": due_date,
                            "updated_at": now_str("%Y-%m-%d %H:%M"),
                        },
                        "id",
                        "글쓰기",
                    )
                    st.rerun()

    posts_df = DataManager.load("posts").data
    comments_df = DataManager.load("comments").data

    if posts_df.empty or "board_type" not in posts_df.columns:
        st.info("게시글이 없습니다.")
        return

    for col, default in [("status", "접수"), ("assignee", ""), ("due_date", ""), ("updated_at", "")]:
        if col not in posts_df.columns:
            posts_df[col] = default

    if not comments_df.empty:
        for col, default in [("post_id", ""), ("author", ""), ("content", ""), ("date", "")]:
            if col not in comments_df.columns:
                comments_df[col] = default

    # 댓글 groupby로 미리 맵 구성 (속도 핵심)
    comments_map: Dict[str, pd.DataFrame] = {}
    if not comments_df.empty:
        comments_df["post_id"] = comments_df["post_id"].astype(str)
        for pid, grp in comments_df.groupby("post_id", dropna=False):
            comments_map[str(pid)] = grp

    mp = posts_df[posts_df["board_type"].astype(str).str.strip() == bn].copy()
    if "id" in mp.columns:
        mp = mp.sort_values("id", ascending=False)

    with st.expander("필터", expanded=False):
        c1, c2 = st.columns([1, 1])
        with c1:
            sel_status = st.multiselect("상태", POST_STATUS, default=POST_STATUS)
        with c2:
            only_mine = st.checkbox("내 글만 보기", value=False)

    if sel_status:
        mp = mp[mp["status"].astype(str).isin(sel_status)]
    if only_mine:
        mp = mp[mp["author"] == name]

    for _, r in mp.iterrows():
        pid = str(r.get("id", ""))
        st_badge = badge_for_status(str(r.get("status", "접수")))
        ass = str(r.get("assignee", "")).strip()
        due = str(r.get("due_date", "")).strip()
        meta = []
        if ass:
            meta.append(f"담당: {ass}")
        if due:
            meta.append(f"마감: {due}")
        meta_txt = (" | " + " / ".join(meta)) if meta else ""

        exp_title = f"{r.get('title','')} ({r.get('author','')})"
        with st.expander(exp_title):
            st.markdown(f"{st_badge} <b>{r.get('title','')}</b>{meta_txt}", unsafe_allow_html=True)
            st.write(r.get("content", ""))

            # 관리자/매니저: 상태/담당자/마감 수정
            if st.session_state["role"] in ["Master", "Manager"]:
                with st.expander("상태/담당자/마감 수정", expanded=False):
                    with st.form(f"edit_post_{pid}"):
                        cA, cB, cC = st.columns([1, 1, 1])
                        with cA:
                            cur_status = str(r.get("status", "접수"))
                            idx = POST_STATUS.index(cur_status) if cur_status in POST_STATUS else 0
                            new_status = st.selectbox("상태", POST_STATUS, index=idx)
                        with cB:
                            new_assignee = st.text_input("담당자(이름)", value=str(r.get("assignee", "")))
                        with cC:
                            cur_due = None
                            try:
                                if str(r.get("due_date", "")).strip():
                                    cur_due = datetime.strptime(str(r.get("due_date", "")).strip(), "%Y-%m-%d").date()
                            except:
                                cur_due = None
                            d = st.date_input("마감", value=cur_due)
                            new_due = d.strftime("%Y-%m-%d") if d else ""
                        if st.form_submit_button("저장", use_container_width=True):
                            DataManager.update_row(
                                "posts",
                                "id",
                                r.get("id", ""),
                                {
                                    "status": new_status,
                                    "assignee": new_assignee,
                                    "due_date": new_due,
                                    "updated_at": now_str("%Y-%m-%d %H:%M"),
                                },
                                "게시글 상태 수정",
                            )
                            st.rerun()

            # 기존 삭제 권한 유지
            if st.session_state["role"] == "Master" or r.get("author", "") == name:
                if st.button("삭제", key=f"del_{pid}"):
                    DataManager.delete_row("posts", "id", r.get("id", ""), "삭제")
                    st.rerun()

            # 댓글 표시 (map에서 즉시)
            grp = comments_map.get(pid)
            if grp is not None and not grp.empty:
                st.caption("댓글")
                for _, c in grp.iterrows():
                    st.caption(f"{c.get('author','')}: {c.get('content','')}")

            # 댓글 작성 (기존 유지)
            with st.form(f"c_{pid}"):
                ctxt = st.text_input("댓글", label_visibility="collapsed")
                if st.form_submit_button("등록"):
                    DataManager.append_row(
                        "comments",
                        {
                            "post_id": r.get("id", ""),
                            "author": name,
                            "content": ctxt,
                            "date": get_now().strftime("%m-%d %H:%M"),
                        },
                        None,
                        "댓글",
                    )
                    st.rerun()

def page_staff_mgmt():
    st.subheader("👥 직원 관리")
    users = DataManager.load("users", force_refresh=True).data
    if users.empty:
        return

    pending = users[users["approved"].apply(lambda x: not check_approved(x))] if "approved" in users.columns else pd.DataFrame()
    if not pending.empty:
        st.info(f"승인 대기: {len(pending)}명")
        for _, u in pending.iterrows():
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"{u.get('name','')} ({u.get('username','')})")
            if c2.button("승인", key=f"ap_{u.get('username','')}"):
                DataManager.update_row("users", "username", u.get("username", ""), {"approved": "True"}, "승인")
                st.rerun()
            if c3.button("거절", key=f"rj_{u.get('username','')}"):
                DataManager.delete_row("users", "username", u.get("username", ""), "거절")
                st.rerun()
    st.divider()

    active = users[users["approved"].apply(check_approved)] if "approved" in users.columns else users
    for _, u in active.iterrows():
        # (버그 수정) username vs name 비교 오류 수정: 자기 자신 숨기기
        if str(u.get("username", "")) == str(st.session_state.get("username", "")):
            continue
        with st.expander(f"{u.get('name','')} ({u.get('role','')})"):
            with st.form(f"ed_{u.get('username','')}"):
                roles = ["Master", "Manager", "Staff"]
                cur_role = str(u.get("role", "Staff"))
                idx = roles.index(cur_role) if cur_role in roles else 2
                nr = st.selectbox("직급", roles, index=idx)
                if st.form_submit_button("수정"):
                    DataManager.update_row("users", "username", u.get("username", ""), {"role": nr}, "수정")
                    st.rerun()

# ============================================================
# [11. 메인 앱]
# ============================================================
def main():
    AppState.init()

    # ---------- 자동 로그인 ----------
    if not st.session_state.get("logged_in"):
        try:
            if safe_get_cookie("auto_login") == "true":
                # 1순위: 세션 토큰 자동로그인
                token = safe_get_cookie("session_token")
                if token:
                    uid = validate_session_token(token)
                    if uid:
                        res = DataManager.load("users", force_refresh=True)
                        if res.success and not res.data.empty:
                            users = res.data
                            users["username"] = users["username"].astype(str)
                            u = users[users["username"] == uid]
                            if not u.empty and check_approved(u.iloc[0].get("approved", "False")):
                                st.session_state.update(
                                    {
                                        "logged_in": True,
                                        "username": uid,
                                        "name": u.iloc[0]["name"],
                                        "role": u.iloc[0]["role"],
                                        "department": u.iloc[0].get("department", "전체"),
                                    }
                                )

                # 2순위: 기존 해시 쿠키 fallback
                if not st.session_state.get("logged_in"):
                    uid = safe_get_cookie("uid")
                    upw = safe_get_cookie("upw")
                    if uid:
                        res = DataManager.load("users", force_refresh=True)
                        if res.success and not res.data.empty:
                            users = res.data
                            users["username"] = users["username"].astype(str)
                            u = users[users["username"] == uid]
                            if not u.empty and check_approved(u.iloc[0].get("approved", "False")):
                                if upw:
                                    if str(u.iloc[0].get("password", "")) != str(upw):
                                        raise Exception("saved hash mismatch")
                                st.session_state.update(
                                    {
                                        "logged_in": True,
                                        "username": uid,
                                        "name": u.iloc[0]["name"],
                                        "role": u.iloc[0]["role"],
                                        "department": u.iloc[0].get("department", "전체"),
                                    }
                                )
        except:
            pass

    if not st.session_state.get("logged_in"):
        login_page()
        return

    # ✅ [속도 개선 핵심] 로그인 직후에는 홈/팝업 최소 데이터만 먼저 로드
    if not st.session_state.get("boot_home_loaded"):
        with st.spinner("동기화 중..."):
            DataManager.prefetch_home_popup()
        st.session_state["boot_home_loaded"] = True

    show_network_status()

    # ✅ [속도 개선] 팝업은 메뉴/페이지 렌더 전에 먼저 판단(홈 첫 진입 체감 개선)
    if st.session_state.get("show_popup_on_login"):
        pt = get_pending_tasks_list()
        uc = get_unconfirmed_inform_list(st.session_state["name"])
        if pt or uc:
            show_notification_popup(pt, uc)
        st.session_state["show_popup_on_login"] = False
        # 팝업 확인 버튼 -> rerun 발생. 아래 UI는 다음 렌더에서 그려짐.

    # 상단바
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1:
        if processed_icon:
            st.image(processed_icon, width=35)
    with c2:
        st.markdown(f"**{st.session_state['name']}** ({st.session_state.get('department','전체')})")
    with c3:
        if st.button("🔄", key="refresh"):
            DataManager.clear_cache()
            # 리프레시하면 다음 렌더에 최소 프리패치 다시
            st.session_state["boot_home_loaded"] = False
            st.rerun()

    show_pending_saves_retry()

    menu = ["홈", "인폼", "본점", "작업", "건의", "체크", "로그아웃"]
    icons = ["house-fill", "megaphone-fill", "shop", "tools", "chat-dots", "check2-square", "box-arrow-right"]
    if st.session_state["role"] == "Master":
        menu.insert(-1, "관리")
        icons.insert(-1, "people-fill")

    m = option_menu(
        None,
        menu,
        icons=icons,
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={"container": {"padding": "0!important", "background-color": "#FFF3E0"},
                "nav-link": {"font-size": "10px", "padding": "8px 5px"}},
    )

    # (선택) 메뉴에 따라 필요한 시트만 그때 추가 프리패치 (첫 홈 속도 유지)
    # - 홈은 이미 최소 프리패치 완료
    # - 게시판/알림 체감 올리고 싶으면 아래처럼 켜세요.
    if m in ["본점", "작업", "건의"]:
        DataManager.prefetch(["posts", "comments"])
    elif m == "관리":
        DataManager.prefetch(["users"])
    elif m == "체크":
        DataManager.prefetch(["routine_def", "routine_log"])
    elif m == "인폼":
        DataManager.prefetch(["inform_notes", "inform_logs"])

    if m == "로그아웃":
        st.session_state["logged_in"] = False

        # 토큰 세션 revoke
        try:
            token = safe_get_cookie("session_token")
            if token:
                revoke_session_token(token)
        except:
            pass

        # 쿠키 정리
        try:
            if cookies:
                safe_set_cookie("auto_login", "false")
                safe_set_cookie("session_token", "")
        except:
            pass

        # 로그인 재진입 시 홈 최적화 재적용
        st.session_state["boot_home_loaded"] = False
        st.rerun()

    elif m == "홈":
        show_dashboard()
    elif m == "인폼":
        page_inform()
    elif m == "체크":
        page_routine()
    elif m == "본점":
        page_board("본점", "🏠")
    elif m == "작업":
        page_board("작업장", "🏭")
    elif m == "건의":
        page_board("건의사항", "💡")
    elif m == "관리":
        page_staff_mgmt()

if __name__ == "__main__":
    main()
