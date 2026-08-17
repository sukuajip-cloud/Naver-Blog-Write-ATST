import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup
import random

# 페이지 기본 설정
st.set_page_config(page_title="Smart Blog AI Studio", page_icon="✨", layout="wide")

# API 키 가져오기 (Secrets 연동)
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

# 💡 텍스트와 대표 이미지를 함께 추출하는 함수로 업그레이드
def fetch_product_data(url):
    if not url or "http" not in url:
        return "", ""
    try:
        # 사람인 것처럼 속이는 헤더 정보 강화
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. 대표 이미지(og:image) 추출
            img_url = ""
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image['content']
                # 주소가 //로 시작하는 경우 방지
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url

            # 2. 텍스트 추출
            for s in soup(["script", "style"]):
                s.decompose()
            text = soup.get_text(separator=' ', strip=True)[:3000]
            
            return text, img_url
    except Exception as e:
        return "", ""
    return "", ""

def generate_blog_post(topic, raw_text, product_url, tone, creativity, expertise, friendliness, photo_style):
    if not API_KEY:
        return "🚨 [오류] Streamlit Secrets에 'GEMINI_API_KEY'가 설정되지 않았습니다.", ""
    
    try:
        client = genai.Client(api_key=API_KEY)
        
        # 크롤링 실행
        scraped_content, scraped_img_url = fetch_product_data(product_url)
        
        available_models = [m.name.replace('models/', '') for m in client.models.list() 
                            if 'gemini' in m.name and 'embed' not in m.name and 'aqa' not in m.name]
        
        intro_styles = [
            "독자의 고민이나 공감대로 흥미롭게 시작", 
            "반전 있는 경험담이나 솔직한 첫인상으로 시작", 
            "질문형 문장으로 독자의 호기심을 자극하며 시작"
        ]
        selected_intro = random.choice(intro_styles)
        
        prompt = f"""
        당신은 트렌디하고 감각적인 네이버 블로그 포스팅 전문 크리에이터입니다.
        이번 포스팅은 **{selected_intro}** 방식으로 신선하게 전개해 주세요.
        
        [스타일] 톤: {tone}, 전문성: {expertise}, 친밀도: {friendliness}
        
        [입력 데이터] 
        - 주제: {topic}
        - 메모: {raw_text}
        - 참고URL 텍스트: {scraped_content}
        - 참고URL 대표이미지: {scraped_img_url}

        [가이드]
        1. 고정된 틀(개요-장단점 등)에서 벗어나 유연하고 자연스러운 소제목 활용
        2. 이미지 배치 ({photo_style}): 
           - 만약 [참고URL 대표이미지]에 주소가 있다면, 글의 가장 자연스러운 상단에 `![상품 대표 이미지]({scraped_img_url})` 마크다운을 넣어 실제 사진이 렌더링되게 해주세요.
           - 나머지 사진들은 기존처럼 `[📸 이미지: (필요한 사진 구체적 묘사)]` 형식과 캡션 1줄로 가이드해주세요.
        3. 네이버 블로그 감성에 맞는 해시태그 5~7개 마무리
        """
        
        for model_name in available_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"temperature": creativity}
                )
                return response.text, scraped_img_url
            except:
                continue
        return "❌ 사용 가능한 모델을 찾을 수 없습니다.", ""
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", ""

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
                result_text, img_url = generate_blog_post(topic, raw_text, product_url, tone, creativity, expertise, friendliness, photo_style)
                
                # 💡 쇼핑몰 보안에 막히지 않고 이미지를 성공적으로 가져왔다면 화면에 띄워줍니다!
                if img_url:
                    st.success("✅ AI가 링크 속 상품 이미지를 확인했습니다!")
                    st.image(img_url, width=250, caption="크롤링된 상품 대표 이미지")
                elif product_url:
                    st.info("⚠️ 링크 내용은 읽었으나, 해당 쇼핑몰 보안으로 인해 이미지는 직접 가져오지 못했습니다.")
                
                # 원고 출력 (텍스트 박스 대신 마크다운으로 렌더링되도록 st.markdown 사용)
                st.markdown(result_text)
                
                # 복사용 텍스트 제공
                with st.expander("📝 복사하기 전용 텍스트창 (클릭해서 열기)"):
                    st.text_area("아래 내용을 복사하세요", value=result_text, height=300, label_visibility="collapsed")
    else:
        st.info("왼쪽 정보를 입력하고 [블로그 원고 자동 완성] 버튼을 누르면 이곳에 결과가 출력됩니다.")
