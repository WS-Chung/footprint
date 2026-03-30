import streamlit as st
from supabase import create_client, Client
from streamlit_folium import st_folium
import folium
import time
import base64
import os
import json  # 지도를 임시 저장(캐싱)하기 위해 추가되었습니다.

st.set_page_config(page_title="우리 발자국 👣", page_icon="👣", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
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
    "selected_marker": None,
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

# 새로고침 방지를 위해 is_adding 관련 오버레이 코드를 삭제하고 깔끔하게 정리했습니다.
def build_map(footprints, center_lat=37.34541, center_lng=127.08995):
    m = folium.Map(location=[center_lat, center_lng], zoom_start=12, tiles="OpenStreetMap")

    # 미리 두 분의 아이콘 파일을 읽어둡니다. (파일이 없으면 None 반환)
    ws_icon_data = get_image_base64("ws.png")
    hm_icon_data = get_image_base64("hm.png")

    for fp in footprints:
        is_ws = (fp["user_name"] == "운석")
        stars = "⭐" * int(fp.get("rating") or 0)
        popup_html = (
            f"<div style='font-family:sans-serif;min-width:160px;'>"
            f"<b>📍 {fp['place_name']}</b><br>"
            f"{'🔵' if is_ws else '🔴'} {fp['user_name']}<br>"
            f"📅 {fp.get('visit_date','-')}<br>{stars}<br>"
            f"💬 {fp.get('review') or '-'}</div>"
        )
        
        # 아이콘 적용: 파일이 있으면 사진을 (56x56 사이즈로), 없으면 기본 핀(파랑/빨강)을 띄웁니다.
        icon_data = ws_icon_data if is_ws else hm_icon_data
        if icon_data:
            icon_obj = folium.CustomIcon(icon_image=icon_data, icon_size=(56, 56))
        else:
            icon_obj = folium.Icon(color="blue" if is_ws else "red", icon="map-marker", prefix="fa")

        folium.Marker(
            location=[fp["lat"], fp["lng"]],
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=fp["place_name"],
            icon=icon_obj
        ).add_to(m)

    return m

# ⭐️ 핵심 마법: 생성된 지도를 메모리에 저장해두고, 데이터가 안 바뀌면 재사용합니다.
@st.cache_resource(max_entries=5)
def get_cached_map(footprints_json, center_lat, center_lng):
    footprints = json.loads(footprints_json)
    return build_map(footprints, center_lat, center_lng)

# ════════════════════════════════════════════════════════════
# 좌측 패널
# ════════════════════════════════════════════════════════════
left_col, center_col, right_col = st.columns([1, 2.5, 1.5])

with left_col:
    st.markdown("## 👣 우리 발자국")
    st.divider()

    st.markdown("**나는 누구?**")
    user = st.radio("유저 선택", ["운석", "혜민"], horizontal=True, label_visibility="collapsed")
    st.session_state.selected_user = user
    st.markdown("🔵 **운석** 으로 활동 중" if user == "운석" else "🔴 **혜민** 으로 활동 중")
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
        place_name    = st.text_input("장소 이름 *", placeholder="예: 경복궁 앞 카페")
        visit_date    = st.date_input("방문 일자 *")
        review_text   = st.text_area("한 줄 리뷰 (30자 이내)", placeholder="예: 분위기가 너무 좋았어!", max_chars=30)
        rating        = st.select_slider("별점", options=[1,2,3,4,5], value=3, format_func=lambda x: "⭐"*x)
        uploaded_file = st.file_uploader("사진 등록", type=["jpg","jpeg","png"])

        if st.button("💾 발자국 저장", use_container_width=True, type="primary"):
            if not place_name:
                st.error("장소 이름을 입력해 주세요!")
            else:
                image_url = None
                if uploaded_file:
                    file_bytes = uploaded_file.read()
                    file_name  = f"{st.session_state.selected_user}_{int(time.time())}_{uploaded_file.name}"
                    try:
                        supabase.storage.from_("footprint_images").upload(
                            path=file_name,
                            file=file_bytes,
                            file_options={"content-type": uploaded_file.type}
                        )
                        raw_url = supabase.storage.from_("footprint_images").get_public_url(file_name)
                        image_url = raw_url if isinstance(raw_url, str) else raw_url.get("publicURL") or raw_url.get("publicUrl", "")
                    except Exception as e:
                        st.warning(f"이미지 업로드 실패: {e}")

                try:
                    supabase.table("footprints").insert({
                        "user_name" : st.session_state.selected_user,
                        "lat"       : st.session_state.clicked_lat,
                        "lng"       : st.session_state.clicked_lng,
                        "place_name": place_name,
                        "visit_date": str(visit_date),
                        "review"    : review_text,
                        "rating"    : int(rating),
                        "image_url" : image_url,
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
# 중앙 패널
# ════════════════════════════════════════════════════════════
with center_col:
    footprints_data = load_footprints()
    
    # 선택된 마커가 없을 때 맵의 초기 위치도 요청하신 좌표로 변경했습니다.
    c_lat = st.session_state.selected_marker["lat"] if st.session_state.selected_marker else 37.34541
    c_lng = st.session_state.selected_marker["lng"] if st.session_state.selected_marker else 127.08995

    # 데이터를 텍스트(JSON)로 변환하여 캐싱 함수에 전달합니다.
    footprints_json = json.dumps(footprints_data)
    fmap = get_cached_map(footprints_json, c_lat, c_lng)
    
    map_data = st_folium(
        fmap, 
        height=560, 
        use_container_width=True,
        returned_objects=["last_clicked", "last_object_clicked_popup"]
    )

    if map_data and map_data.get("last_clicked") and st.session_state.is_adding:
        new_lat = map_data["last_clicked"]["lat"]
        new_lng = map_data["last_clicked"]["lng"]
        if st.session_state.clicked_lat != new_lat or st.session_state.clicked_lng != new_lng:
            st.session_state.clicked_lat = new_lat
            st.session_state.clicked_lng = new_lng
            st.rerun()

    if map_data and map_data.get("last_object_clicked_popup"):
        popup_text = str(map_data["last_object_clicked_popup"])
        for fp in footprints_data:
            if fp["place_name"] in popup_text:
                if st.session_state.selected_marker != fp:
                    st.session_state.selected_marker = fp
                    st.session_state.is_adding = False
                    st.rerun()
                break

# ════════════════════════════════════════════════════════════
# 우측 패널
# ════════════════════════════════════════════════════════════
with right_col:
    st.markdown("## 📌 발자국 상세")
    st.divider()

    if st.session_state.selected_marker is None:
        st.markdown("""
        <div style='text-align:center;color:#aaa;padding:60px 10px;'>
            <div style='font-size:2.5rem'>👆</div>
            <div style='margin-top:10px;'>지도에서 마커를 클릭하면<br>상세 정보가 여기에 표시됩니다.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        marker     = st.session_state.selected_marker
        user_color = "#3B82F6" if marker.get("user_name") == "운석" else "#EF4444"
        user_emoji = "🔵" if marker.get("user_name") == "운석" else "🔴"

        st.markdown(f"""
        <div style='background:{user_color}18;border-left:4px solid {user_color};
             border-radius:8px;padding:12px 16px;margin-bottom:12px;'>
            <div style='font-size:0.85rem;color:{user_color};font-weight:bold;'>
                {user_emoji} {marker.get("user_name")}의 발자국
            </div>
            <div style='font-size:1.3rem;font-weight:bold;margin-top:4px;'>
                📍 {marker.get("place_name","")}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"📅 **방문일:** {marker.get('visit_date', '-')}")
        st.markdown(f"⭐ **별점:** {'⭐' * int(marker.get('rating') or 0)}")
        st.markdown(f"💬 **리뷰:** {marker.get('review') or '-'}")

        # ── 이미지 표시 ──────────────────────────────────────
        img = marker.get("image_url")
        if img and str(img).strip():
            st.image(str(img).strip(), use_container_width=True)

        st.divider()
        if st.button("✖ 닫기", use_container_width=True):
            st.session_state.selected_marker = None
            st.rerun()
