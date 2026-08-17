import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup
import random

# 페이지 기본 설정
st.set_page_config(page_title="Smart Blog AI Studio", page_icon="✨", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 세션 상태(Session State) 관리 ---
for key in ["topic_input", "url_input", "text_input"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "scraped_data" not in st.session_state: st.session_state.scraped_data = None
if "generated_text" not in st.session_state: st.session_state.generated_text = None
if "adv_settings" not in st.session_state: st.session_state.adv_settings = False

def clear_inputs():
    st.session_state.topic_input = ""
    st.session_state.url_input = ""
    st.session_state.text_input = ""
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

def url_changed():
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

# --- 💡 독하게 튜닝한 크롤링 엔진 (방화벽 우회 및 메타데이터 추출 강화) ---
def fetch_product_info(url):
    if not url or "http" not in url:
        return None
    
    try:
        # 봇(Bot)이 아닌 실제 사람 브라우저처럼 완벽하게 위장
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        res = requests.get(url, headers=headers, timeout=8)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. 이미지 추출
            img_url = ""
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                img_url = og_img['content']
                if img_url.startswith('//'): img_url = 'https:' + img_url

            # 2. 제목 추출 (쇼핑몰 방화벽에 막혀도 제목은 보통 노출됨)
            title = ""
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'): title = og_title['content']
            elif soup.title: title = soup.title.string.strip()

            # 3. 요약 내용 추출 (본문이 막힐 경우를 대비한 Description 추출)
            desc = ""
            og_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
            if og_desc and og_desc.get('content'): desc = og_desc['content']

            # 4. 가격 추출
            price = ""
            og_price = soup.find('meta', property='product:price:amount')
            if og_price and og_price.get('content'): price = og_price['content'] + "원"

            # 5. 전체 본문 추출 시도
            for s in soup(["script", "style", "nav", "footer"]): s.decompose()
            body_text = soup.get_text(separator=' ', strip=True)
            
            # 본문이 너무 짧거나 막혔을 경우 메타(요약) 데이터로 대체
            final_text = body_text[:3000] if len(body_text) > 100 else f"요약 설명: {desc}"

            return {"title": title, "price": price, "img": img_url, "desc": desc, "body": final_text}
        else:
            return {"title": f"접근 차단됨 (상태코드 {res.status_code})", "price": "", "img": "", "desc": "", "body": ""}
    except Exception as e:
        return {"title": f"크롤링 에러 ({str(e)})", "price": "", "img": "", "desc": "", "body": ""}

# --- 💡 블로그 자동 완성 엔진 ---
def generate_blog_post():
    if not API_KEY:
        return "🚨 [오류] API 키가 설정되지 않았습니다."
    try:
        client = genai.Client(api_key=API_KEY)
        
        topic = st.session_state.topic_input
        url = st.session_state.url_input
        raw_text = st.session_state.text_input
        
        s_data = st.session_state.scraped_data
        if s_data:
            s_title = s_data.get("title", "")
            s_price = s_data.get("price", "")
            s_body = s_data.get("body", "")
            s_img = s_data.get("img", "")
        else:
            s_title, s_price, s_body, s_img = "", "", "", ""
            
        models = [m.name.replace('models/', '') for m in client.models.list() if 'gemini' in m.name and 'embed' not in m.name and 'aqa' not in m.name]
        
        prompt = f"""
        당신은 트렌디하고 감각적인 네이버 블로그 포스팅 전문 크리에이터입니다.
        
        [입력 데이터] 
        - 블로그 주제: {topic}
        - 나의 메모/후기: {raw_text}
        - 참고 상품명: {s_title}
        - 참고 가격: {s_price}
        - 참고 상품 상세내용: {s_body}
        - 상품 링크: {url}

        [작성 가이드]
        1. 정보 통합: 제공된 '참고 상품명'과 '상세내용'을 철저히 분석하여 스펙, 특징 등을 원고에 정확히 반영하세요. (상품 내용이 부족하면 URL과 주제를 기반으로 추론하세요.)
        2. 이미지 가이드: 
           - 최상단에 `![상품 이미지]({s_img})` 마크다운을 넣어 실제 제품 사진이 보이게 하세요.
           - 중간중간 `[📸 이미지: (필요한 사진 구체적 묘사)]` 와 센스있는 캡션을 넣으세요.
        3. 소제목을 활용하여 가독성을 높이고, 해시태그 5~7개로 마무리하세요.
        """
        
        for m_name in models:
            try:
                response = client.models.generate_content(model=m_name, contents=prompt, config={"temperature": 0.8})
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
    st.text_input("2. 참고 상품 링크 (선택)", key="url_input", on_change=url_changed, placeholder="쿠팡, 네이버 쇼핑 등 URL")
    st.text_area("3. 나의 실제 후기/메모", key="text_input", height=130, placeholder="메모할 내용 입력...")
    
    st.toggle("⚙️ 고급 설정 열기 (톤/스타일 등)", key="adv_settings")
    if st.session_state.adv_settings:
        with st.container(border=True):
            st.info("이 기능은 추후 업데이트를 통해 텍스트 프롬프트에 동적으로 반영될 예정입니다. 현재는 숨겨진 기본값으로 작성됩니다.")
    
    # 💡 명확하게 분리된 3개의 액션 버튼
    st.markdown("---")
    st.markdown("##### 🛠️ 작업 실행")
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🔍 1차 검토 (정보 불러오기)", use_container_width=True):
            st.session_state.adv_settings = False
            if st.session_state.url_input:
                with st.spinner("상품 정보를 긁어오고 있습니다..."):
                    st.session_state.scraped_data = fetch_product_info(st.session_state.url_input)
            else:
                st.warning("URL을 먼저 입력해주세요.")
                
    with btn_col2:
        if st.button("🚀 최종 블로그 원고 작성", type="primary", use_container_width=True):
            st.session_state.adv_settings = False
            if not st.session_state.topic_input:
                st.warning("주제를 입력해주세요!")
            else:
                with st.spinner("AI가 상품 정보를 바탕으로 원고를 작성 중입니다..."):
                    st.session_state.generated_text = generate_blog_post()
                    
    if st.button("🗑️ 모든 내용 초기화", on_click=clear_inputs, use_container_width=True):
        pass

with col2:
    st.subheader("📄 검토 및 완성된 원고")
    
    # 1차 검토 결과 (정보 확인창)
    if st.session_state.scraped_data:
        st.success("💡 1차 검토: URL에서 아래 정보를 확인했습니다.")
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                img = st.session_state.scraped_data.get("img")
                if img: st.image(img)
                else: st.write("🖼️ 이미지 차단됨")
            with c2:
                st.write(f"**제품명:** {st.session_state.scraped_data.get('title', '없음')}")
                st.write(f"**가격:** {st.session_state.scraped_data.get('price', '없음')}")
                # 긁어온 본문 중 앞부분 150자만 미리보기로 보여줌
                preview_text = st.session_state.scraped_data.get("body", "")[:150]
                st.caption(f"**내용 미리보기:** {preview_text}...")

    # 최종 작성된 원고 출력
    if st.session_state.generated_text:
        st.markdown("---")
        st.markdown(st.session_state.generated_text)
        
        with st.expander("📝 복사하기 전용 텍스트창"):
            st.text_area("전체 복사 후 블로그에 붙여넣으세요.", value=st.session_state.generated_text, height=300, label_visibility="collapsed")
