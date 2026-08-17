import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup
import random

# 페이지 기본 설정
st.set_page_config(page_title="Smart Blog AI Studio", page_icon="✨", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 💡 세션 상태(Session State) 완벽 관리 ---
for key in ["topic_input", "url_input", "text_input"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "adv_settings" not in st.session_state: st.session_state.adv_settings = False
if "scraped_data" not in st.session_state: st.session_state.scraped_data = None
if "generated_text" not in st.session_state: st.session_state.generated_text = None

# 고급 설정용 키
if "tone" not in st.session_state: st.session_state.tone = "친근한 내돈내산 리뷰형"
if "photo_style" not in st.session_state: st.session_state.photo_style = "상세하고 구체적인 묘사형"
if "creativity" not in st.session_state: st.session_state.creativity = 0.8
if "expertise" not in st.session_state: st.session_state.expertise = 7
if "friendliness" not in st.session_state: st.session_state.friendliness = 9

# 콜백 함수들
def clear_inputs():
    for key in ["topic_input", "url_input", "text_input"]:
        st.session_state[key] = ""
    st.session_state.scraped_data = None
    st.session_state.generated_text = None
    st.session_state.adv_settings = False

def on_url_change():
    # URL이 바뀌면 가져왔던 기존 데이터와 원고를 싹 초기화하여 1단계로 되돌림
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

def close_adv_settings():
    # 버튼을 누르면 고급 설정 창이 자동으로 닫힘
    st.session_state.adv_settings = False

# 크롤링 함수
def fetch_product_data_action():
    url = st.session_state.url_input
    if not url or "http" not in url:
        st.session_state.scraped_data = {"text": "", "img": "", "name": "URL을 확인해주세요", "price": ""}
        return
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9',
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            img_url = ""
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image['content']
                if img_url.startswith('//'): img_url = 'https:' + img_url

            product_name = ""
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                product_name = og_title['content']
            elif soup.title:
                product_name = soup.title.string.strip()

            product_price = ""
            og_price = soup.find('meta', property='product:price:amount')
            if og_price and og_price.get('content'):
                product_price = og_price['content'] + "원"

            for s in soup(["script", "style"]): s.decompose()
            text = soup.get_text(separator=' ', strip=True)[:3000]
            
            st.session_state.scraped_data = {
                "text": text, "img": img_url, "name": product_name, "price": product_price
            }
        else:
            st.session_state.scraped_data = {"text": "", "img": "", "name": "페이지 접근 차단됨", "price": ""}
    except Exception as e:
        st.session_state.scraped_data = {"text": "", "img": "", "name": "크롤링 에러", "price": ""}

# 생성 함수
def execute_generation():
    if not API_KEY:
        return "🚨 [오류] Streamlit Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다."
    try:
        client = genai.Client(api_key=API_KEY)
        
        # 세션에 저장된 값 불러오기
        topic, url, raw_text = st.session_state.topic_input, st.session_state.url_input, st.session_state.text_input
        tone, photo_style = st.session_state.tone, st.session_state.photo_style
        creativity, expertise, friendliness = st.session_state.creativity, st.session_state.expertise, st.session_state.friendliness

        if st.session_state.scraped_data:
            s_content, s_img = st.session_state.scraped_data["text"], st.session_state.scraped_data["img"]
            s_name, s_price = st.session_state.scraped_data["name"], st.session_state.scraped_data["price"]
        else:
            s_content, s_img, s_name, s_price = "", "", "", ""
        
        available_models = [m.name.replace('models/', '') for m in client.models.list() 
                            if 'gemini' in m.name and 'embed' not in m.name and 'aqa' not in m.name]
        
        intro_styles = ["독자의 고민이나 공감대로 시작", "솔직한 첫인상으로 시작", "호기심을 자극하며 시작"]
        selected_intro = random.choice(intro_styles)
        
        prompt = f"""
        당신은 트렌디하고 감각적인 네이버 블로그 포스팅 전문 크리에이터입니다.
        이번 포스팅은 **{selected_intro}** 방식으로 신선하게 전개해 주세요.
        
        [스타일] 톤: {tone}, 전문성: {expertise}, 친밀도: {friendliness}
        
        [입력 데이터] 
        - 주제: {topic}
        - 메모: {raw_text}
        - 제품명: {s_name}
        - 가격: {s_price}
        - 참고URL 정보: {s_content}
        - 참고 URL 링크: {url}

        [작성 가이드]
        1. 정보 분석: 제품명({s_name})과 가격({s_price}), 텍스트 정보를 바탕으로 정확한 스펙을 글에 자연스럽게 녹여내세요.
        2. 이미지 가이드 ({photo_style}): 
           - 최상단에 `![상품 대표 이미지]({s_img})` 마크다운을 넣어 실제 제품 사진이 보이게 하세요.
           - 글 중간중간 `[📸 이미지: (필요한 사진 구체적 묘사)]` 와 센스있는 캡션을 넣으세요.
        3. 마무리 시 독자들이 제품을 확인할 수 있도록 자연스럽게 참고 URL(리뷰/구매 링크)을 안내하고, 해시태그 5~7개로 마무리하세요.
        """
        
        for model_name in available_models:
            try:
                response = client.models.generate_content(model=model_name, contents=prompt, config={"temperature": creativity})
                return response.text
            except: continue
        return "❌ 사용 가능한 모델을 찾을 수 없습니다."
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

# --- UI 화면 구성 ---
st.title("✨ Smart Blog AI Studio")
st.caption("키워드와 링크만으로 완성하는 나만의 완벽한 포스팅")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📝 핵심 정보 입력")
    st.text_input("1. 블로그 주제", key="topic_input", placeholder="예: 차박용 미니 로봇청소기 사용 후기")
    # URL이 입력되거나 지워지면 실시간으로 상태 초기화
    st.text_input("2. 참고 상품 링크 (선택)", key="url_input", on_change=on_url_change, placeholder="쿠팡, 스마트스토어 등 URL")
    st.text_area("3. 나의 실제 후기/메모", key="text_input", height=130, placeholder="직접 써보니 가볍고 좋은데 배터리가 살짝 아쉬움...")
    
    # 💡 토글 스위치로 변경 (자동으로 닫기 가능)
    st.toggle("⚙️ AI 페르소나 및 고급 설정 열기", key="adv_settings")
    if st.session_state.adv_settings:
        with st.container(border=True):
            st.selectbox("글쓰기 톤", ["친근한 내돈내산 리뷰형", "정보 전달 전문 블로거형", "재치있는 에세이형", "진중한 분석형"], key="tone")
            st.selectbox("사진 가이드", ["상세하고 구체적인 묘사형", "감성적이고 직관적인 스냅형"], key="photo_style")
            st.slider("창의성 (Temperature)", 0.2, 1.0, 0.8, 0.1, key="creativity")
            st.slider("전문성", 1, 10, 7, key="expertise")
            st.slider("친밀도", 1, 10, 9, key="friendliness")
    
    # 💡 2단계 로직 적용 버튼
    btn_col1, btn_col2 = st.columns([3, 1])
    with btn_col1:
        # URL이 있는데 아직 정보를 안 가져온 경우 1단계 버튼 노출
        if st.session_state.url_input and not st.session_state.scraped_data:
            do_fetch = st.button("🔍 1단계: 링크 상품정보 미리보기", use_container_width=True, type="primary", on_click=close_adv_settings)
            do_gen = False
        else:
            do_fetch = False
            # URL이 없거나 이미 가져왔다면 최종 작성 버튼 노출
            do_gen = st.button("🚀 2단계: 블로그 원고 자동 완성", use_container_width=True, type="primary", on_click=close_adv_settings)
            
    with btn_col2:
        st.button("🗑️ 초기화", on_click=clear_inputs, use_container_width=True)

with col2:
    st.subheader("📄 검토 및 완성된 원고")
    
    # 1. 정보 가져오기 실행
    if do_fetch:
        with st.spinner("해당 링크의 상품 사진과 정보를 꼼꼼히 확인하고 있습니다..."):
            fetch_product_data_action()
        st.rerun() # UI 업데이트

    # 2. 가져온 정보 브리핑 화면 보여주기
    if st.session_state.scraped_data:
        st.info("💡 링크에서 확인한 내용입니다. 이 정보가 맞다면 좌측의 **[2단계: 블로그 원고 자동 완성]** 버튼을 누르세요.")
        with st.container(border=True):
            info_col1, info_col2 = st.columns([1, 2])
            with info_col1:
                img = st.session_state.scraped_data["img"]
                if img: st.image(img, use_container_width=True)
                else: st.write("🖼️ 이미지 확인 불가")
            with info_col2:
                st.write(f"**제품명:** {st.session_state.scraped_data['name']}")
                st.write(f"**가격:** {st.session_state.scraped_data['price']}")
                
    # 3. 원고 자동 완성 실행
    if do_gen:
        if not st.session_state.topic_input:
            st.warning("주제를 먼저 입력해 주세요!")
        else:
            with st.spinner("AI가 최적의 원고를 작성 중입니다... (약 10~20초 소요)"):
                st.session_state.generated_text = execute_generation()

    # 4. 완성된 원고 출력
    if st.session_state.generated_text:
        st.markdown("---")
        st.success("✅ 원고 작성이 완료되었습니다!")
        st.markdown(st.session_state.generated_text)
        
        with st.expander("📝 복사하기 전용 텍스트창 (클릭해서 열기)"):
            st.text_area("아래 내용을 전체 선택하여 네이버 블로그에 붙여넣으세요.", value=st.session_state.generated_text, height=300, label_visibility="collapsed")
