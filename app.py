import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup
import random

# 페이지 기본 설정
st.set_page_config(page_title="Smart Blog AI Studio", page_icon="✨", layout="wide")

# API 키 가져오기
API_KEY = st.secrets.get("GEMINI_API_KEY")

# 세션 상태(Session State) 설정
if "topic_input" not in st.session_state:
    st.session_state.topic_input = ""
if "url_input" not in st.session_state:
    st.session_state.url_input = ""
if "text_input" not in st.session_state:
    st.session_state.text_input = ""

def clear_inputs():
    st.session_state.topic_input = ""
    st.session_state.url_input = ""
    st.session_state.text_input = ""

# 💡 텍스트, 이미지, 제품명, 가격을 모두 추출하는 함수
def fetch_product_data(url):
    if not url or "http" not in url:
        return "", "", "", ""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. 대표 이미지 추출
            img_url = ""
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image['content']
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url

            # 2. 제품명 추출 (og:title 또는 문서 title)
            product_name = ""
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                product_name = og_title['content']
            elif soup.title:
                product_name = soup.title.string.strip()

            # 3. 가격 정보 추출 (og:price 태그가 있는 경우)
            product_price = ""
            og_price = soup.find('meta', property='product:price:amount')
            if og_price and og_price.get('content'):
                product_price = og_price['content'] + "원"

            # 4. 전체 텍스트 추출 (AI 분석용)
            for s in soup(["script", "style"]):
                s.decompose()
            text = soup.get_text(separator=' ', strip=True)[:3000]
            
            return text, img_url, product_name, product_price
    except Exception as e:
        return "", "", "", ""
    return "", "", "", ""

def generate_blog_post(topic, raw_text, product_url, tone, creativity, expertise, friendliness, photo_style):
    if not API_KEY:
        return "🚨 [오류] Streamlit Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.", "", "", ""
    
    try:
        client = genai.Client(api_key=API_KEY)
        
        # 크롤링 실행
        scraped_content, scraped_img_url, scraped_name, scraped_price = fetch_product_data(product_url)
        
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
        - 추출된 제품명: {scraped_name}
        - 추출된 가격: {scraped_price}
        - 참고URL 텍스트: {scraped_content}
        - 참고 URL: {product_url}

        [작성 가이드]
        1. AI 분석: 추출된 제품명({scraped_name})과 가격({scraped_price}), 텍스트 정보를 바탕으로 정확한 스펙과 상품 정보를 글에 자연스럽게 녹여내세요.
        2. 이미지 가이드 ({photo_style}): 
           - 만약 크롤링된 이미지가 있다면, 최상단에 `![상품 대표 이미지]({scraped_img_url})` 마크다운을 넣어 출력되게 하세요.
           - 그 외 글 중간중간 `[📸 이미지: (필요한 사진 구체적 묘사)]` 와 센스있는 캡션 1줄을 넣으세요.
        3. 마무리 시 독자들이 제품을 확인할 수 있도록 자연스럽게 참고 URL(리뷰/구매 링크)을 안내하고, 해시태그 5~7개로 마무리하세요.
        """
        
        for model_name in available_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"temperature": creativity}
                )
                return response.text, scraped_img_url, scraped_name, scraped_price
            except:
                continue
        return "❌ 사용 가능한 모델을 찾을 수 없습니다.", "", "", ""
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", "", "", ""

# UI 화면 구성
st.title("✨ Smart Blog AI Studio")
st.caption("키워드와 링크만으로 완성하는 나만의 완벽한 포스팅")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📝 핵심 정보 입력")
    topic = st.text_input("1. 블로그 주제", key="topic_input", placeholder="예: 차박용 미니 로봇청소기 사용 후기")
    product_url = st.text_input("2. 참고 상품 링크 (선택)", key="url_input", placeholder="쿠팡, 스마트스토어 등 URL")
    raw_text = st.text_area("3. 나의 실제 후기/메모", key="text_input", height=130, placeholder="직접 써보니 가볍고 좋은데 배터리가 살짝 아쉬움...")
    
    with st.expander("⚙️ AI 페르소나 및 고급 설정"):
        tone = st.selectbox("글쓰기 톤", ["친근한 내돈내산 리뷰형", "정보 전달 전문 블로거형", "재치있는 에세이형", "진중한 분석형"])
        photo_style = st.selectbox("사진 가이드", ["상세하고 구체적인 묘사형", "감성적이고 직관적인 스냅형"])
        creativity = st.slider("창의성 (Temperature)", 0.2, 1.0, 0.8, 0.1)
        expertise = st.slider("전문성", 1, 10, 7)
        friendliness = st.slider("친밀도", 1, 10, 9)
    
    btn_col1, btn_col2 = st.columns([3, 1])
    with btn_col1:
        submit_btn = st.button("🚀 블로그 원고 자동 완성", use_container_width=True, type="primary")
    with btn_col2:
        st.button("🗑️ 초기화", on_click=clear_inputs, use_container_width=True)

with col2:
    st.subheader("📄 완성된 원고")
    if submit_btn:
        if not topic:
            st.warning("주제를 입력해 주세요!")
        else:
            with st.spinner("AI가 상품 정보를 읽고 최적의 원고를 작성 중입니다..."):
                result_text, img_url, prod_name, prod_price = generate_blog_post(topic, raw_text, product_url, tone, creativity, expertise, friendliness, photo_style)
                
                # 💡 정보 요약 브리핑 UI (이미지, 제품명, 가격)
                if product_url:
                    with st.container(border=True):
                        st.markdown("##### 🔍 AI가 파악한 링크 정보")
                        info_col1, info_col2 = st.columns([1, 2])
                        with info_col1:
                            if img_url:
                                st.image(img_url, use_container_width=True)
                            else:
                                st.write("🖼️ 이미지 차단됨")
                        with info_col2:
                            st.write(f"**제품명:** {prod_name if prod_name else '알 수 없음 (텍스트 내용 참조)'}")
                            st.write(f"**가격:** {prod_price if prod_price else '본문 텍스트 내에서 탐색함'}")
                
                st.markdown(result_text)
                
                with st.expander("📝 복사하기 전용 텍스트창 (클릭해서 열기)"):
                    st.text_area("아래 내용을 복사하세요", value=result_text, height=300, label_visibility="collapsed")
    else:
        st.info("왼쪽 정보를 입력하고 [블로그 원고 자동 완성] 버튼을 누르면 이곳에 결과가 출력됩니다.")
