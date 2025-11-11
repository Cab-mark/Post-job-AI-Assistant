# pages/03_Interview_Question_Generator.py
from password_gate import require_password
require_password()
import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Recruitment hub - Interview question generator", page_icon="💬")

# ----- SETUP -----
# Expect your key in env var; you can change this to st.secrets if you prefer
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.title("Interview question generator (mock)")
st.info('We could extend the hub to include other AI capabilities like a interview question generator.', icon="ℹ️")
st.caption("Answer a few structured questions and I'll draft suitable interview questions.")

# The structured steps we want the AI “agent” to ask
STRUCTURED_STEPS = [
    {
        "id": "role_title",
        "prompt": "First, what is the job title or role you're recruiting for?",
    },
    {
        "id": "grade_level",
        "prompt": "What level/grade is this role? (e.g. EO, HEO, SEO, or ‘mid-level engineer’)",
    },
    {
        "id": "core_capabilities",
        "prompt": "What are the core skills or behaviours you want to assess? (e.g. stakeholder management, delivery, problem solving, GOV.UK behaviours)",
    },
    {
        "id": "experience_focus",
        "prompt": "Do you want to prioritise technical experience, situational/judgement questions, or past-behaviour examples?",
    },
    {
        "id": "role_context",
        "prompt": "Tell me a bit about the context: team size, type of service/product, and whether it’s user-facing or internal.",
    },
]

if "messages" not in st.session_state:
    # chat history shown to user
    st.session_state.messages = []
if "answers" not in st.session_state:
    # collected structured answers
    st.session_state.answers = {}
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
if "generated_questions" not in st.session_state:
    st.session_state.generated_questions = []

# helper to get next prompt
def get_current_prompt():
    idx = st.session_state.current_step
    if idx < len(STRUCTURED_STEPS):
        return STRUCTURED_STEPS[idx]["prompt"]
    return None

# ----- DISPLAY HISTORY -----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# If we still have structured questions to ask, make sure the assistant asks it
current_prompt = get_current_prompt()
if current_prompt and (len(st.session_state.messages) == 0 or st.session_state.messages[-1]["role"] == "user"):
    # assistant asks the next structured question
    with st.chat_message("assistant"):
        st.markdown(current_prompt)
    st.session_state.messages.append({"role": "assistant", "content": current_prompt})

# ----- USER INPUT -----
user_input = st.chat_input("Type your answer…")
if user_input:
    # show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    # Immediately render the user's message so it appears in the chat UI without waiting
    # for the next rerun. This ensures the user sees their input straight away.
    with st.chat_message("user"):
        st.markdown(user_input)

    # store answer against the current step
    step_idx = st.session_state.current_step
    if step_idx < len(STRUCTURED_STEPS):
        step_id = STRUCTURED_STEPS[step_idx]["id"]
        st.session_state.answers[step_id] = user_input
        st.session_state.current_step += 1

    # if there is another structured question, ask it
    next_prompt = get_current_prompt()
    if next_prompt:
        with st.chat_message("assistant"):
            st.markdown(next_prompt)
        st.session_state.messages.append({"role": "assistant", "content": next_prompt})
    else:
        # we have all answers -> generate interview questions
        with st.chat_message("assistant"):
            with st.spinner("Generating tailored interview questions..."):
                role_title = st.session_state.answers.get("role_title", "the role")
                grade_level = st.session_state.answers.get("grade_level", "")
                core_capabilities = st.session_state.answers.get("core_capabilities", "")
                experience_focus = st.session_state.answers.get("experience_focus", "")
                role_context = st.session_state.answers.get("role_context", "")

                prompt = f"""
You are an experienced Civil Service / public sector interviewer.
Generate 6-8 interview questions tailored to the following role.

Role title: {role_title}
Level/Grade: {grade_level}
Core skills/behaviours to assess: {core_capabilities}
Priority style (technical / situational / past behaviour): {experience_focus}
Role context: {role_context}

Rules:
- Mix in competency/behavioural questions relevant to UK Civil Service context if appropriate.
- Ask for evidence (STAR) where relevant.
- Keep questions short and plain English.
- Group them by ‘Core’, ‘Behavioural’, ‘Scenario’.
                """.strip()

                # ----- CALL LLM -----
                try:
                    resp = client.responses.create(
                        model="gpt-4.1-mini",  # adjust to your model
                        input=prompt,
                    )
                    ai_text = resp.output[0].content[0].text
                    st.session_state.generated_questions = ai_text.split("\n")
                except Exception as e:
                    ai_text = f"Sorry, I couldn't generate questions: {e}"
                    st.session_state.generated_questions = [ai_text]

            # show result
            st.markdown("Here are your interview questions:")
            for line in st.session_state.generated_questions:
                if line.strip():
                    st.markdown(f"- {line.strip()}")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "I've generated some questions for you below. You can tweak them and ask me to regenerate."
                }
            )

# Sidebar intentionally left minimal; collected inputs removed to declutter UI



