import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup

# 페이지 기본 설정
st.set_page_config(page_title="네이버 블로그 마스터 AI Studio", page_icon="📝", layout="wide")

API_KEY = st.secrets.get("GEMINI_API_KEY")

# --- 세션 상태 관리 ---
for key in ["topic_input", "keyword_input", "target_input", "url_input", "text_input"]:
    if key not in st.session_state:
        st.session_state[key] = ""

if "scraped_data" not in st.session_state: st.session_state.scraped_data = None
if "generated_text" not in st.session_state: st.session_state.generated_text = None

def clear_inputs():
    for key in ["topic_input", "keyword_input", "target_input", "url_input", "text_input"]:
        st.session_state[key] = ""
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

def url_changed():
    st.session_state.scraped_data = None
    st.session_state.generated_text = None

# --- 동적 모델 탐색 및 생성 함수 ---
def generate_with_fallback(client, prompt, config=None):
    available_models = [
        m.name.replace('models/', '') for m in client.models.list() 
        if 'gemini' in m.name and 'embed' not in m.name and 'aqa' not in m.name
    ]
    
    last_error = "사용 가능한 Gemini 모델을 찾을 수 없습니다."
    for model_name in available_models:
        try:
            if config:
                res = client.models.generate_content(model=model_name, contents=prompt, config=config)
            else:
                res = client.models.generate_content(model=model_name, contents=prompt)
            return res.text
        except Exception as e:
            last_error = str(e)
            continue
    raise Exception(last_error)

# --- 1차 검토: AI 요약 엔진 ---
def fetch_and_summarize(url):
    if not url or "http" not in url:
        return None
    
    try:
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
            
            ai_summary = "요약 내용을 불러오지 못했습니다. (텍스트 부족 또는 차단)"
            if API_KEY and len(body_text) > 50:
                try:
                    client = genai.Client(api_key=API_KEY)
                    summary_prompt = f"""
                    다음 웹문서의 원문을 분석하여 독자에게 유용한 핵심 포인트 3~4줄로 새롭게 요약해줘:
                    - 글머리 기호(- ) 사용
                    - 복사-붙여넣기가 아닌 자연스러운 문맥 재구성

                    [원문 텍스트]
                    {body_text}
                    """
                    ai_summary = generate_with_fallback(client, summary_prompt)
                except Exception as e:
                    ai_summary = f"⚠️ 요약 중 에러 발생: {str(e)}"

            return {"title": title, "price": price, "img": img_url, "summary": ai_summary, "raw_body": body_text}
        else:
            return {"title": f"접근 차단됨 (코드 {res.status_code})", "price": "", "img": "", "summary": "쇼핑몰/사이트 보안으로 내용을 읽지 못했습니다.", "raw_body": ""}
    except Exception as e:
        return {"title": "크롤링 에러", "price": "", "img": "", "summary": str(e), "raw_body": ""}

# --- 네이버 블로그 마스터 v1.0 통합 작성 엔진 ---
def generate_blog_post(mode, use_scraped_data):
    if not API_KEY:
        return "🚨 [오류] API 키가 설정되지 않았습니다."
    try:
        client = genai.Client(api_key=API_KEY)
        
        topic = st.session_state.topic_input
        keyword = st.session_state.keyword_input
        target = st.session_state.target_input if st.session_state.target_input else "일반 대중 및 해당 분야 관심 독자"
        url = st.session_state.url_input
        raw_text = st.session_state.text_input
        
        s_data = st.session_state.scraped_data
        if use_scraped_data and s_data and s_data.get('raw_body') and len(s_data.get('raw_body')) > 50:
            s_info = f"[참고 자료 정보]\n- 제목: {s_data.get('title')}\n- 상세 내용: {s_data.get('raw_body')}\n- 링크: {url}"
            s_img = s_data.get("img")
        else:
            s_info = "[참고 자료 정보]\n- 참고 자료 없음 혹은 내용 파악 불가(SKIP). 사용자의 주제와 메모를 중심으로 작성할 것."
            s_img = ""

        prompt = f"""
당신은 대한민국 네이버 블로그 생태계를 깊이 이해하는 최상위 블로그 콘텐츠 전략가이자 전문 작가입니다.
독자가 실제로 끝까지 읽고, 공감하고, 댓글을 남기고, 저장하고, 공유하도록 만드는 것이 최우선 목표입니다.

==================================================
[가장 중요한 원칙]
1. 절대 금지 (AI 냄새 나는 표현 완전 배제):
   '알아보겠습니다', '살펴보겠습니다', '정리해보겠습니다', '설명드리겠습니다', '도움이 되셨길 바랍니다', 
   '첫째', '둘째', '셋째', '지금부터', '결론적으로', '따라서', '요약하자면' 등은 절대 사용하지 마십시오.
2. 사람처럼 작성:
   - "나도 처음에는 그렇게 생각했다", "생각보다 많은 사람들이 놓치는 부분이다", "실제로 해보면 의외의 결과가 나온다" 등 실제 경험담과 공감 문구 활용.
3. 논문체 금지:
   - 친구에게 설명하듯 너무 가볍지도 딱딱하지도 않은 신뢰감 있는 블로그 문체 유지.
4. 신뢰성 및 다각도 분석:
   - 장점만 나열하지 말고 단점, 주의사항, 비교, 수치/사례를 균형 있게 포함.
5. 참고문서 예외 처리:
   - 만약 제공된 참고 자료의 내용이 부실하거나 파악하기 어려운 경우, 억지로 추측하지 말고 참고 자료는 과감히 SKIP하고 사용자의 입력 데이터와 일반 상식을 기반으로 독창적 원고를 완성하십시오.

==================================================
[선택된 블로그 모드: {mode}]
- 성장형: 호기심 > 공감 > 정보 > SEO | 질문형 문장 적극 활용, 짧은 문단, 독자 참여 유도, 체류시간 극대화
- 수익형: 검색의도 > 문제해결 > 비교 > SEO | 장단점, 추천 대상, 비추천 대상, 가성비/비용 분석, 구매 전 고민 해결
- 신뢰형: 공감 > 경험 > 진정성 > 정보 | 스토리와 감정 중심, 인간적인 실수 및 시행착오 포함, 팬 확보 중심
- 전문가형: 전문성 > 신뢰 > 이해도 > SEO | 데이터/사례/근거 중심, 실무적 깊이와 명확한 이유 제시

==================================================
[입력 데이터]
- 주제: {topic}
- 핵심 키워드: {keyword} (본문 내에 5회 자연스럽게 반복 필수, 유사 단어 다채롭게 활용)
- 대상 독자: {target}
- 나의 실제 메모/경험담: {raw_text}
{s_info}

==================================================
[최종 출력 구조]
반드시 아래의 양식으로 정돈하여 전체 원고를 작성해 주십시오.

### 📌 1. 추천 제목 3선 (클릭률 및 검색 유입 고려)
(후보 제목 3개와 각각의 타겟팅 특징 1줄씩 제시)

---

### 📝 2. 블로그 본문 원고
- 서론, 본론, 결론의 명확한 서술형 흐름 (리스트 나열 지양)
- 글자 수: 최소 2500자 이상 최대 5000자 수준으로 풍성하게 작성
- 이미지 배치 가이드: 
  * 참고 이미지가 있다면 최상단에 `![참고 이미지]({s_img})` 마크다운 렌더링
  * 본문 중간중간 `[📸 이미지: (필요한 사진 구체적 묘사)]` 와 센스 있는 사진 캡션 1줄 포함

---

### 🎨 3. 본문 삽입용 이미지 기획 가이드
(본문 속 이미지 3~4개에 대한 삽입 위치, 목적, AI 이미지 생성 프롬프트 제안)

---

### 🏷️ 4. SEO 태그 및 최적화
- 메타 디스크립션 (1~2문장)
- 검색 태그 및 해시태그 30개 (#태그1 #태그2 ...)

---

### ✅ 5. 최종 품질 자체 검수표
1. 금지된 AI 상투어가 완벽히 제거되었는가?
2. 핵심 키워드가 본문 내에 정확히 5회 반복되었는가?
3. 선택된 모드({mode})의 특징이 본문에 충실히 반영되었는가?
"""
        
        return generate_with_fallback(client, prompt, config={"temperature": 0.85})

    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

# --- UI 화면 구성 ---
st.title("📝 네이버 블로그 마스터 AI Studio")
st.caption("네이버 블로그 마스터 시스템 프롬프트 패키지 v1.0 탑재")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("⚙️ 포스팅 전략 & 정보 입력")
    
    # 💡 4대 모드 선택
    selected_mode = st.radio(
        "🎯 블로그 모드 선택",
        ["성장형", "수익형", "신뢰형", "전문가형"],
        horizontal=True,
        help="성장형(체류시간/소통), 수익형(전환/비교), 신뢰형(공감/스토리), 전문가형(데이터/근거)"
    )
    
    topic = st.text_input("1. 블로그 주제", key="topic_input", placeholder="예: 30대 직장인을 위한 현실적인 피로회복 영양제 추천")
    keyword = st.text_input("2. 🔑 핵심 키워드", key="keyword_input", placeholder="예: 직장인 피로회복제 (본문 5회 자동 반복)")
    target = st.text_input("3. 👥 대상 독자 (선택)", key="target_input", placeholder="예: 매일 야근에 지친 30~40대 직장인")
    url = st.text_input("4. 🔗 참고 링크 (선택)", key="url_input", on_change=url_changed, placeholder="참고할 블로그, 상품 URL 등")
    raw_text = st.text_area("5. ✍️ 나의 실제 메모/경험담", key="text_input", height=120, placeholder="내가 겪은 일, 실제 느낀 점, 제품 장단점 메모...")
    
    st.markdown("---")
    btn_col1, btn_col2 = st.columns(2)
    
    with btn_col1:
        if st.button("🔍 1차 검토 (링크 요약)", use_container_width=True):
            if st.session_state.url_input:
                with st.spinner("링크 본문을 분석하여 AI가 새롭게 요약 중입니다..."):
                    st.session_state.scraped_data = fetch_and_summarize(st.session_state.url_input)
            else:
                st.warning("참고 링크 URL을 먼저 입력해주세요.")
                
    with btn_col2:
        if st.button("🚀 최종 블로그 원고 작성", type="primary", use_container_width=True):
            if not st.session_state.topic_input or not st.session_state.keyword_input:
                st.warning("주제와 핵심 키워드는 필수 입력 항목입니다!")
            else:
                with st.spinner(f"[{selected_mode} 모드] 마스터 로직으로 원고를 작성 중입니다... (약 30초 소요)"):
                    use_data = st.session_state.get("use_scraped_data", True)
                    st.session_state.generated_text = generate_blog_post(selected_mode, use_scraped_data=use_data)
                    
    if st.button("🗑️ 전체 초기화", on_click=clear_inputs, use_container_width=True):
        pass

with col2:
    st.subheader("📄 검토 및 완성된 원고")
    
    if st.session_state.scraped_data:
        st.success("💡 1차 검토 결과: URL 분석 완료")
        with st.container(border=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                img = st.session_state.scraped_data.get("img")
                if img: st.image(img)
                else: st.caption("🖼️ 이미지 없음/차단")
            with c2:
                st.write(f"**제목:** {st.session_state.scraped_data.get('title', '없음')}")
                st.write(f"**가격:** {st.session_state.scraped_data.get('price', '없음')}")
            
            st.markdown("---")
            st.markdown(f"**🤖 AI 본문 핵심 요약:**\n\n{st.session_state.scraped_data.get('summary', '')}")
            
        st.checkbox("✅ 위 참고 자료를 블로그 원고에 반영 (부실하거나 불필요시 체크 해제)", value=True, key="use_scraped_data")

    if st.session_state.generated_text:
        st.markdown("---")
        st.markdown(st.session_state.generated_text)
        
        with st.expander("📝 복사 전용 텍스트창 (클릭하여 전체 복사)"):
            st.text_area("전체 복사 후 네이버 블로그에 붙여넣으세요.", value=st.session_state.generated_text, height=450, label_visibility="collapsed")
