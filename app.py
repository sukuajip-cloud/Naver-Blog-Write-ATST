import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup

# 페이지 기본 설정
st.set_page_config(page_title="Smart Blog AI Studio", page_icon="✨", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 세션 상태(Session State) 관리 ---
for key in ["topic_input", "url_input", "text_input"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "scraped_data" not in st.session_state: st.session_state.scraped_data = None
if "generated_text" not in st.session_state: st.session_state.generated_text = None

def clear_inputs():
    st.session_state.topic_input = ""
    st.session_state.url_input = ""
    st.session_state.text_input = ""
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

def url_changed():
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

# --- 💡 1차 검토: 크롤링 + [AI 진짜 요약] 엔진 ---
def fetch_and_summarize(url):
    if not url or "http" not in url:
        return None
    
    try:
        # 네이버 블로그 모바일 우회
        if "blog.naver.com" in url and "m.blog.naver.com" not in url:
            url = url.replace("blog.naver.com", "m.blog.naver.com")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
        res = requests.get(url, headers=headers, timeout=8)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 이미지 & 제목 & 가격 가져오기 시도
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

            # 텍스트 본문 추출
            for s in soup(["script", "style", "nav", "footer", "header"]): 
                s.decompose()
            body_text = soup.get_text(separator=' ', strip=True)[:3000]
            
            # 💡 [핵심] 여기서 AI에게 원문을 넘겨 3~4줄로 "진짜 요약"을 시킵니다!
            ai_summary = "요약 실패 (텍스트가 없거나 AI 응답 지연)"
            if API_KEY and len(body_text) > 50:
                try:
                    client = genai.Client(api_key=API_KEY)
                    summary_prompt = f"다음 웹문서의 핵심 내용을 파악하기 쉽게 3~4줄의 글머리 기호(- )로 요약해줘:\n\n{body_text}"
                    # 가볍고 빠른 모델을 찾아 요약 수행
                    models = [m.name.replace('models/', '') for m in client.models.list() if 'gemini' in m.name and 'aqa' not in m.name]
                    if models:
                        res = client.models.generate_content(model=models[0], contents=summary_prompt)
                        ai_summary = res.text
                except:
                    ai_summary = body_text[:300] + "...(AI 요약 에러로 원문 일부 출력)"

            return {"title": title, "price": price, "img": img_url, "summary": ai_summary, "raw_body": body_text}
        else:
            return {"title": f"접근 차단됨 (상태코드 {res.status_code})", "price": "", "img": "", "summary": "쇼핑몰/사이트 보안으로 인해 내용을 읽을 수 없습니다.", "raw_body": ""}
    except Exception as e:
        return {"title": "크롤링 에러", "price": "", "img": "", "summary": str(e), "raw_body": ""}

# --- 💡 최종 블로그 자동 완성 엔진 ---
def generate_blog_post(use_scraped_data):
    if not API_KEY:
        return "🚨 [오류] API 키가 설정되지 않았습니다."
    try:
        client = genai.Client(api_key=API_KEY)
        
        topic = st.session_state.topic_input
        url = st.session_state.url_input
        raw_text = st.session_state.text_input
        
        # 고급 설정 값 가져오기
        tone = st.session_state.get("tone", "친근한 내돈내산 리뷰형")
        creativity = st.session_state.get("creativity", 0.8)
        photo_style = st.session_state.get("photo_style", "상세하고 구체적인 묘사형")
        
        # 체크박스(use_scraped_data)가 켜져 있을 때만 크롤링 정보를 프롬프트에 포함!
        s_data = st.session_state.scraped_data
        if use_scraped_data and s_data:
            s_info = f"- 참고 제목: {s_data.get('title')}\n- 참고 가격: {s_data.get('price')}\n- 참고 내용 요약: {s_data.get('summary')}\n- 참고 링크: {url}"
            s_img = s_data.get("img")
        else:
            s_info = "- URL 참고 정보 없음 (또는 사용 안 함)"
            s_img = ""
            
        models = [m.name.replace('models/', '') for m in client.models.list() if 'gemini' in m.name and 'embed' not in m.name and 'aqa' not in m.name]
        
        prompt = f"""
        당신은 트렌디하고 감각적인 네이버 블로그 포스팅 전문 크리에이터입니다.
        
        [에디터 설정]
        - 톤/스타일: {tone}
        
        [입력 데이터] 
        - 블로그 주제: {topic}
        - 나의 메모/후기: {raw_text}
        {s_info}

        [작성 가이드]
        1. 정보 통합: 제공된 데이터를 자연스럽게 녹여내어 읽기 편한 글로 작성하세요.
        2. 이미지 가이드 ({photo_style}): 
           - 최상단에 `![참고 이미지]({s_img})` 마크다운을 넣어 이미지가 보이게 하세요. (이미지가 없으면 생략)
           - 중간중간 `[📸 이미지: (필요한 사진 구체적 묘사)]` 와 센스있는 캡션을 넣으세요.
        3. 소제목을 활용하여 가독성을 높이고, 해시태그 5~7개로 마무리하세요.
        """
        
        for m_name in models:
            try:
                response = client.models.generate_content(model=m_name, contents=prompt, config={"temperature": creativity})
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
    st.text_input("2. 참고 자료/상품 링크 (선택)", key="url_input", on_change=url_changed, placeholder="네이버 블로그, 쿠팡 등 URL")
    st.text_area("3. 나의 실제 후기/메모", key="text_input", height=130, placeholder="메모할 내용 입력...")
    
    # 💡 텅 빈 깡통이었던 고급 설정을 다시 꽉꽉 채웠습니다!
    st.toggle("⚙️ 고급 설정 열기 (톤, 창의성 조절)", key="adv_settings")
    if st.session_state.adv_settings:
        with st.container(border=True):
            st.selectbox("글쓰기 톤", ["친근한 내돈내산 리뷰형", "정보 전달 전문 블로거형", "재치있는 에세이형", "진중한 분석형"], key="tone")
            st.selectbox("사진 가이드", ["상세하고 구체적인 묘사형", "감성적이고 직관적인 스냅형"], key="photo_style")
            st.slider("창의성 (Temperature)", 0.2, 1.0, 0.8, 0.1, key="creativity")
    
    st.markdown("---")
    st.markdown("##### 🛠️ 작업 실행")
    
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        if st.button("🔍 1차 검토 (정보 불러오기)", use_container_width=True):
            if st.session_state.url_input:
                with st.spinner("링크의 내용을 읽고 AI가 요약 중입니다..."):
                    st.session_state.scraped_data = fetch_and_summarize(st.session_state.url_input)
            else:
                st.warning("URL을 먼저 입력해주세요.")
                
    with btn_col2:
        # 이 버튼을 누르면 밑에서 설정한 '체크박스' 값에 따라 작동합니다.
        if st.button("🚀 최종 블로그 원고 작성", type="primary", use_container_width=True):
            if not st.session_state.topic_input:
                st.warning("주제를 입력해주세요!")
            else:
                with st.spinner("최종 원고를 작성 중입니다..."):
                    # 세션에 저장된 체크박스 상태 확인 (기본값 True)
                    use_data = st.session_state.get("use_scraped_data", True)
                    st.session_state.generated_text = generate_blog_post(use_scraped_data=use_data)
                    
    if st.button("🗑️ 모든 내용 초기화", on_click=clear_inputs, use_container_width=True):
        pass

with col2:
    st.subheader("📄 검토 및 완성된 원고")
    
    # 💡 1차 검토 결과: AI 요약본 + 선택 체크박스 추가
    if st.session_state.scraped_data:
        st.success("💡 1차 검토: AI가 URL 내용을 분석하고 요약했습니다.")
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                img = st.session_state.scraped_data.get("img")
                if img: st.image(img)
                else: st.caption("이미지 차단됨 (해당 사이트 보안)")
            with c2:
                st.write(f"**제목:** {st.session_state.scraped_data.get('title', '없음')}")
                st.write(f"**가격:** {st.session_state.scraped_data.get('price', '없음')}")
            
            st.markdown("---")
            st.markdown(f"**🤖 AI 본문 핵심 요약:**\n\n{st.session_state.scraped_data.get('summary', '')}")
            
        # 💡 [핵심] 이 정보를 블로그에 포함할지 말지 선택하는 체크박스!
        st.checkbox("✅ 위 1차 검토 정보를 최종 블로그 원고에 반영합니다.", value=True, key="use_scraped_data")

    # 최종 작성된 원고 출력
    if st.session_state.generated_text:
        st.markdown("---")
        st.markdown(st.session_state.generated_text)
        
        with st.expander("📝 복사하기 전용 텍스트창"):
            st.text_area("전체 복사 후 블로그에 붙여넣으세요.", value=st.session_state.generated_text, height=300, label_visibility="collapsed")
