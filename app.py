import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup

# 페이지 기본 설정
st.set_page_config(page_title="Smart Blog AI Studio", page_icon="✨", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 세션 상태 관리 ---
for key in ["topic_input", "keyword_input", "url_input", "text_input"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "scraped_data" not in st.session_state: st.session_state.scraped_data = None
if "generated_text" not in st.session_state: st.session_state.generated_text = None

def clear_inputs():
    for key in ["topic_input", "keyword_input", "url_input", "text_input"]:
        st.session_state[key] = ""
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

def url_changed():
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

# --- 💡 1차 검토: AI 찐 요약 엔진 ---
def fetch_and_summarize(url):
    if not url or "http" not in url:
        return None
    
    try:
        # 네이버 블로그 모바일 우회
        if "blog.naver.com" in url and "m.blog.naver.com" not in url:
            url = url.replace("blog.naver.com", "m.blog.naver.com")

        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            img_url = ""
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content'):
                img_url = og_img['content']
                if img_url.startswith('//'): img_url = 'https:' + img_url

            title = ""
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'): title = og_title['content']
            elif soup.title: title = soup.title.string.strip()

            price = ""
            og_price = soup.find('meta', property='product:price:amount')
            if og_price and og_price.get('content'): price = og_price['content'] + "원"

            for s in soup(["script", "style", "nav", "footer", "header"]): 
                s.decompose()
            body_text = soup.get_text(separator=' ', strip=True)[:4000]
            
            # 💡 [핵심] 원문 복사가 아닌 "진짜 요약"을 강제하는 프롬프트
            ai_summary = "요약 내용을 불러오지 못했습니다. (텍스트가 너무 짧거나 보안에 막힘)"
            if API_KEY and len(body_text) > 50:
                try:
                    client = genai.Client(api_key=API_KEY)
                    summary_prompt = f"""
                    아래 제공된 웹문서의 원문을 읽고, 절대 원문을 그대로 복사하지 말고 당신의 언어로 '새롭게' 3~4줄로 핵심만 요약해주세요.
                    글머리 기호(- )를 사용하여 가독성 좋게 작성해주세요.
                    
                    [원문 텍스트]
                    {body_text}
                    """
                    # 가장 안정적이고 똑똑한 모델 강제 지정
                    res = client.models.generate_content(model='gemini-1.5-flash', contents=summary_prompt)
                    ai_summary = res.text
                except Exception as e:
                    ai_summary = f"⚠️ 요약 중 에러 발생: {str(e)}"

            return {"title": title, "price": price, "img": img_url, "summary": ai_summary, "raw_body": body_text}
        else:
            return {"title": f"접근 차단됨 (상태코드 {res.status_code})", "price": "", "img": "", "summary": "쇼핑몰/사이트 보안으로 인해 내용을 읽을 수 없습니다.", "raw_body": ""}
    except Exception as e:
        return {"title": "크롤링 에러", "price": "", "img": "", "summary": str(e), "raw_body": ""}

# --- 💡 10년 차 SEO 전문가 블로그 작성 엔진 ---
def generate_blog_post(use_scraped_data):
    if not API_KEY:
        return "🚨 [오류] API 키가 설정되지 않았습니다."
    try:
        client = genai.Client(api_key=API_KEY)
        
        topic = st.session_state.topic_input
        keyword = st.session_state.keyword_input
        url = st.session_state.url_input
        raw_text = st.session_state.text_input
        
        tone = st.session_state.get("tone", "친근한 느낌, AI스럽지 않게 자연스러운 어투")
        
        s_data = st.session_state.scraped_data
        if use_scraped_data and s_data:
            s_info = f"- 참고 자료 제목: {s_data.get('title')}\n- 참고 자료 상세(본문 텍스트): {s_data.get('raw_body')}"
            s_img = s_data.get("img")
        else:
            s_info = "- URL 참고 정보 없음 (또는 사용 안 함)"
            s_img = ""
            
        # 💡 제공해주신 완벽한 SEO 마케터 프롬프트 이식
        prompt = f"""
        다음 지침을 참고하여 상위노출 로직에 최적화된 네이버 블로그 포스팅을 작성해줘.
        모든 지침을 꼼꼼하게 확인하여 적용해주어야 해.

        [작성 지침]
        1. 작성자 : 10년차 SEO 전문가
        2. 어투 : {tone}
        3. 글자수 : 최대한 풍부하고 상세하게 작성해줘. (목표: 3000~5000자 수준으로 아주 길게)
        4. 정확하지 않은 정보는 배제할 것. 제공된 '참고 자료 상세'를 바탕으로 구체적인 데이터를 언급할 것.
        5. '나의 실제 메모/경험담'을 듬뿍 담은 독창적인 원고를 작성해줘. 중복 문서로 처리되지 않도록 주의해.
        6. 서론, 본론, 결론의 명확한 구조를 가질 것.
        7. 단순 리스트형이 아닌 '서술형'으로 스토리텔링하듯 풀어서 설명해줄 것.
        8. 도입부는 독자가 글에 흥미를 가지도록 구체적이고 흥미를 끌 수 있는 질문이나 경험담으로 시작해줘.
        9. 읽는 이의 공감을 이끌어낼 수 있는 문구를 넣어줘.
        10. 많은 사람들이 오해할 만한 내용이 있다면 바로잡아줘.
        11. 구체적인 사례를 통해 본문의 내용 이해를 도와줘.

        [이미지 가이드]
        - 최상단에 `![참고 이미지]({s_img})` 마크다운을 넣어 이미지가 보이게 해줘. (이미지가 없으면 생략)
        - 글 중간중간 내용에 맞는 위치에 `[📸 이미지 업로드: (어떤 사진이 들어가면 좋을지 구체적 묘사)]` 와 센스있는 캡션을 넣어줘.

        [작성 소스 데이터]
        - 블로그 제목 : {topic}
        - 핵심 키워드 : {keyword} (본문 내에 정확히 5회 반복되도록 신경 쓰고, 나머지는 유사 단어로 다채롭게 활용)
        - 나의 실제 메모/경험담 : {raw_text}
        {s_info}

        [자체 점검 브리핑]
        작성된 원고 맨 마지막에 아래 기준으로 자체 점검표를 짧게 달아줘.
        1. 분량이 충분히 길게 작성되었는가?
        2. 핵심 키워드가 5회 반복되었는가?
        3. 정보는 정확하며 출처(참고자료)가 명확하게 반영되었는가?
        """
        
        # 블로그 작성에 최적화된 1.5 Pro 모델을 우선 사용하도록 지정
        res = client.models.generate_content(model='gemini-1.5-pro', contents=prompt, config={"temperature": 0.85})
        return res.text

    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

# --- UI 화면 구성 ---
st.title("✨ Smart Blog AI Studio (SEO PRO 버전)")
st.caption("10년 차 마케터의 로직이 탑재된 블로그 원고 자동 완성기")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📝 핵심 정보 입력")
    st.text_input("1. 블로그 제목", key="topic_input", placeholder="예: 30대 직장인 영양제 추천")
    st.text_input("2. 🔑 핵심 키워드 (SEO용)", key="keyword_input", placeholder="예: 직장인 피로회복제")
    st.text_input("3. 참고 자료/상품 링크 (선택)", key="url_input", on_change=url_changed, placeholder="네이버 블로그, 쿠팡 등 URL")
    st.text_area("4. 나의 실제 후기/경험담", key="text_input", height=130, placeholder="내가 직접 겪은 이야기, 느낀 점, 메모 등...")
    
    st.toggle("⚙️ 고급 설정 열기 (톤/스타일)", key="adv_settings")
    if st.session_state.adv_settings:
        with st.container(border=True):
            st.selectbox("글쓰기 톤", [
                "친근한 느낌, AI스럽지 않게 자연스러운 어투", 
                "전문적이고 신뢰감 있는 정보 전달형 어투", 
                "재치있고 유머러스한 에세이형 어투"
            ], key="tone")
    
    st.markdown("---")
    st.markdown("##### 🛠️ 작업 실행")
    
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        if st.button("🔍 1차 검토 (AI 요약)", use_container_width=True):
            if st.session_state.url_input:
                with st.spinner("링크 본문을 분석하여 새로운 문장으로 요약 중입니다..."):
                    st.session_state.scraped_data = fetch_and_summarize(st.session_state.url_input)
            else:
                st.warning("URL을 먼저 입력해주세요.")
                
    with btn_col2:
        if st.button("🚀 최종 블로그 원고 작성", type="primary", use_container_width=True):
            if not st.session_state.topic_input or not st.session_state.keyword_input:
                st.warning("제목과 핵심 키워드를 모두 입력해주세요!")
            else:
                with st.spinner("10년 차 SEO 마케터의 뇌로 깊이 있는 원고를 작성 중입니다... (최대 1분 소요)"):
                    use_data = st.session_state.get("use_scraped_data", True)
                    st.session_state.generated_text = generate_blog_post(use_scraped_data=use_data)
                    
    if st.button("🗑️ 모든 내용 초기화", on_click=clear_inputs, use_container_width=True):
        pass

with col2:
    st.subheader("📄 검토 및 완성된 원고")
    
    if st.session_state.scraped_data:
        st.success("💡 1차 검토: AI가 URL 본문을 읽고 새롭게 요약했습니다.")
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                img = st.session_state.scraped_data.get("img")
                if img: st.image(img)
                else: st.caption("이미지 차단됨")
            with c2:
                st.write(f"**참고 제목:** {st.session_state.scraped_data.get('title', '없음')}")
                st.write(f"**가격:** {st.session_state.scraped_data.get('price', '없음')}")
            
            st.markdown("---")
            st.markdown(f"**🤖 AI 본문 핵심 요약:**\n\n{st.session_state.scraped_data.get('summary', '')}")
            
        st.checkbox("✅ 위 참고 자료를 최종 블로그 원고에 융합하여 작성합니다.", value=True, key="use_scraped_data")

    if st.session_state.generated_text:
        st.markdown("---")
        st.markdown(st.session_state.generated_text)
        
        with st.expander("📝 복사하기 전용 텍스트창"):
            st.text_area("전체 복사 후 블로그에 붙여넣으세요.", value=st.session_state.generated_text, height=400, label_visibility="collapsed")
