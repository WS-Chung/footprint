import streamlit as st
from supabase import create_client, Client
from streamlit_folium import st_folium
import folium
import time
import base64
import os

st.set_page_config(page_title="우리 발자국 👣", page_icon="👣", layout="wide")

# 별점(st.feedback)의 크기를 1.2배로 키우는 CSS가 추가되었습니다.
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="stFeedback"] {
        transform: scale(1.2);
        transform-origin: left center;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

@st.cache_data(ttl=5)
def load_footprints():
    res = supabase.table("footprints").select("*").execute()
    return res.data if res.data else []

for key, val in {
    "selected_user"  : "운석",
    "is_adding"      : False,
    "clicked_lat"    : None,
    "clicked_lng"    : None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# 로컬 이미지 파일을 지도에 안전하게 띄우기 위한 마법(Base64 변환) 함수
def get_image_base64(filepath):
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return None

def build_map(footprints, center_lat=37.34541, center_lng=127.08995):
    m = folium.Map(location=[center_lat, center_lng], zoom_start=12, tiles="OpenStreetMap")

    ws_icon_data = get_image_base64("ws.png")
    hm_icon_data = get_image_base64("hm.png")

    for fp in footprints:
        is_ws = (fp["user_name"] == "운석")
        stars = "⭐" * int(fp.get("rating") or 0)
        
        # ⭐️ 모바일 최적화: 글자 크기를 1pt씩 줄이고, 패딩 및 최소 너비(min-width)를 컴팩트하게 수정했습니다.
        popup_html = (
            f"<div style='font-family:sans-serif; min-width:250px; padding:6px;'>"
            f"<div style='margin-top:0px; margin-bottom:8px; color:#333; font-size:15pt; font-weight:bold;'> {fp['place_name']}</div>"
            
            # 여기서부터 3가지 정보가 가로 한 줄로 배치됩니다.
            f"<div style='margin-bottom:12px; font-size:11pt; white-space:nowrap;'>"
            f"{'🩵' if is_ws else '🩷'} <b>{fp['user_name']}</b>"
            f"<span style='color:#ccc; margin:0 8px;'>|</span>"
            f"<span style='font-size:10pt; color:#666;'>📅 {fp.get('visit_date','-')}</span>"
            f"<span style='color:#ccc; margin:0 8px;'>|</span>"
            f"<span style='font-size:12pt;'>{stars}</span>"
            f"</div>"
            
            f"<div style='background-color:#f8f9fa; padding:10px; border-radius:8px; font-size:10pt; line-height:1.4; border-left:4px solid {'#3B82F6' if is_ws else '#EF4444'}; white-space:normal;'>"
            f" {fp.get('review') or '-'}</div>"
            f"</div>"
        )
        
        icon_data = ws_icon_data if is_ws else hm_icon_data
        if icon_data:
            icon_obj = folium.CustomIcon(icon_image=icon_data, icon_size=(32, 42))
        else:
            icon_obj = folium.Icon(color="blue" if is_ws else "red", icon="map-marker", prefix="fa")

        folium.Marker(
            location=[fp["lat"], fp["lng"]],
            # ⭐️ 팝업 최대 너비(max_width)도 모바일 화면을 고려하여 350으로 줄였습니다.
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=fp["place_name"],
            icon=icon_obj
        ).add_to(m)

    return m

# ════════════════════════════════════════════════════════════
# 화면 분할 (좌측: 메뉴 / 우측: 확장된 지도)
# ════════════════════════════════════════════════════════════
left_col, right_col = st.columns([1, 3])  

with left_col:
    st.markdown("## 👣 우리 발자국")
    st.divider()

    st.markdown("**나는 누구?**")
    st.radio("유저 선택", ["운석", "혜민"], horizontal=True, label_visibility="collapsed", key="selected_user")
    
    st.markdown("🩵 **운석** 으로 활동 중" if st.session_state.selected_user == "운석" else "🩷 **혜민** 으로 활동 중")
    st.divider()

    if not st.session_state.is_adding:
        if st.button("📍 새 발자국 등록", use_container_width=True, type="primary"):
            st.session_state.is_adding   = True
            st.session_state.clicked_lat = None
            st.session_state.clicked_lng = None
            st.rerun()
    else:
        st.info("🗺️ 지도를 클릭해서\n위치를 선택해 주세요!")
        if st.button("❌ 취소", use_container_width=True):
            st.session_state.is_adding   = False
            st.session_state.clicked_lat = None
            st.session_state.clicked_lng = None
            st.rerun()

    if st.session_state.is_adding and st.session_state.clicked_lat is not None:
        st.divider()
        st.success(f"✅ 위치 선택 완료!\n\n`{st.session_state.clicked_lat:.5f}`, `{st.session_state.clicked_lng:.5f}`")
        st.divider()
        st.markdown("**📝 발자국 정보 입력**")
        place_name    = st.text_input("장소 이름 *", placeholder="예: 산으로 간 고등어")
        visit_date    = st.date_input("방문 일자 *")
        review_text   = st.text_area("한 줄 리뷰 (30자 이내)", placeholder="예: 김지갑 더 가져올걸!", max_chars=30)
        
        st.markdown("**⭐ 별점 선택 * **")
        rating_index  = st.feedback("stars", key="feedback_rating")

        if st.button("💾 발자국 저장", use_container_width=True, type="primary"):
            if not place_name:
                st.error("장소 이름을 입력해 주세요!")
            elif rating_index is None:
                st.warning("앗! 별점을 클릭해서 선택해 주세요 ⭐")
            else:
                final_rating = int(rating_index + 1)
                
                try:
                    supabase.table("footprints").insert({
                        "user_name" : st.session_state.selected_user,
                        "lat"       : st.session_state.clicked_lat,
                        "lng"       : st.session_state.clicked_lng,
                        "place_name": place_name,
                        "visit_date": str(visit_date),
                        "review"    : review_text,
                        "rating"    : final_rating
                    }).execute()
                    st.success("✅ 발자국이 저장되었습니다!")
                    load_footprints.clear()
                    st.session_state.is_adding   = False
                    st.session_state.clicked_lat = None
                    st.session_state.clicked_lng = None
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

# ════════════════════════════════════════════════════════════
# 우측 패널 (풀사이즈 지도)
# ════════════════════════════════════════════════════════════
with right_col:
    footprints_data = load_footprints()
    
    c_lat = st.session_state.clicked_lat if st.session_state.clicked_lat else 37.34541
    c_lng = st.session_state.clicked_lng if st.session_state.clicked_lng else 127.08995

    fmap = build_map(footprints_data, c_lat, c_lng)
    
    map_data = st_folium(
        fmap, 
        height=700, 
        use_container_width=True,
        returned_objects=["last_clicked"] 
    )

    if map_data and map_data.get("last_clicked") and st.session_state.is_adding:
        new_lat = map_data["last_clicked"]["lat"]
        new_lng = map_data["last_clicked"]["lng"]
        if st.session_state.clicked_lat != new_lat or st.session_state.clicked_lng != new_lng:
            st.session_state.clicked_lat = new_lat
            st.session_state.clicked_lng = new_lng
            st.rerun()
