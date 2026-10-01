import streamlit as st
import time
from google import genai
from google.genai import types
from prompts import SYSTEM_PROMPT

import json
import re
import smtplib
from email.message import EmailMessage
from datetime import datetime


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=st.secrets["google"]["api_key"]
)

MODEL = "gemini-3.5-flash-lite"


# ============================================================
# SESSION STATE
# ============================================================

if "history" not in st.session_state:
    st.session_state["history"] = []

if "last_answer" not in st.session_state:
    st.session_state["last_answer"] = ""

if "last_question" not in st.session_state:
    st.session_state["last_question"] = ""

if "last_subject" not in st.session_state:
    st.session_state["last_subject"] = "General"

if "quiz_data" not in st.session_state:
    st.session_state["quiz_data"] = []

if "quiz_score" not in st.session_state:
    st.session_state["quiz_score"] = None

if "notes" not in st.session_state:
    st.session_state["notes"] = ""

if "flashcards" not in st.session_state:
    st.session_state["flashcards"] = []

if "followup_answer" not in st.session_state:
    st.session_state["followup_answer"] = ""

if "quiz_history" not in st.session_state:
    st.session_state["quiz_history"] = []

if "study_seconds" not in st.session_state:
    st.session_state["study_seconds"] = 0

if "timer_running" not in st.session_state:
    st.session_state["timer_running"] = False

if "timer_start" not in st.session_state:
    st.session_state["timer_start"] = None


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def extract_json(text):
    """
    Extract JSON from Gemini response.
    Handles normal JSON and ```json code blocks.
    """

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    return None


def send_email(receiver_email, subject, body):
    """
    Sends an email using Gmail SMTP.

    Required Streamlit secrets:

    [email]
    sender = "yourgmail@gmail.com"
    app_password = "your-gmail-app-password"
    """

    if "email" not in st.secrets:
        return False, "Email settings are not configured."

    if "sender" not in st.secrets["email"]:
        return False, "Sender email is missing in secrets.toml."

    if "app_password" not in st.secrets["email"]:
        return False, "Gmail app password is missing in secrets.toml."

    sender = st.secrets["email"]["sender"]
    app_password = st.secrets["email"]["app_password"]

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = sender
    message["To"] = receiver_email

    message.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:

            smtp.login(
                sender,
                app_password
            )

            smtp.send_message(message)

        return True, "Email sent successfully."

    except Exception as error:

        return False, str(error)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="SnapStudy",
    page_icon="📚",
    layout="wide"
)


# ============================================================
# HEADER
# ============================================================

st.title("📚 SnapStudy")

st.write(
    "Your AI-powered study assistant"
)


# ============================================================
# SIDEBAR - STUDENT PROFILE
# ============================================================

with st.sidebar:

    st.header("👤 Student Profile")

    student_name = st.text_input(
        "Your Name",
        value=st.session_state.get(
            "student_name",
            ""
        )
    )

    st.session_state["student_name"] = student_name

    course = st.text_input(
        "Course / Branch",
        value=st.session_state.get(
            "course",
            ""
        )
    )

    st.session_state["course"] = course

    email = st.text_input(
        "Email",
        value=st.session_state.get(
            "email",
            ""
        )
    )

    st.session_state["email"] = email

    st.divider()

    st.subheader("📊 Quick Stats")

    st.metric(
        "Questions Studied",
        len(st.session_state["history"])
    )

    st.metric(
        "Quizzes Taken",
        len(st.session_state["quiz_history"])
    )

    if st.session_state["quiz_history"]:

        average_score = sum(
            item["score"]
            for item in st.session_state["quiz_history"]
        ) / len(st.session_state["quiz_history"])

        st.metric(
            "Average Quiz %",
            f"{average_score:.0f}%"
        )

    else:

        st.metric(
            "Average Quiz %",
            "0%"
        )


# ============================================================
# MAIN TABS
# ============================================================

tabs = st.tabs(
    [
        "🏠 Study",
        "📝 Quiz",
        "📑 Notes",
        "🃏 Flashcards",
        "💬 Follow-up",
        "📊 Dashboard",
        "⏱️ Timer"
    ]
)


# ============================================================
# TAB 1 - STUDY
# ============================================================

with tabs[0]:

    st.header("📖 Ask SnapStudy")

    col1, col2 = st.columns(2)

    with col1:

        subject = st.text_input(
            "📚 Subject / Topic",
            value=st.session_state.get(
                "last_subject",
                "General"
            )
        )

    with col2:

        answer_mode = st.selectbox(
            "🎯 Answer Style",
            [
                "Simple Explanation",
                "Step-by-Step",
                "Exam Answer",
                "Short Notes"
            ]
        )

    question = st.text_area(
        "✍️ Enter your question or topic",
        height=150
    )

    uploaded_image = st.file_uploader(
        "📸 Upload a question, diagram, textbook page or notes",
        type=[
            "jpg",
            "jpeg",
            "png"
        ]
    )

    col1, col2 = st.columns(2)

    with col1:

        generate_clicked = st.button(
            "✨ Generate Answer",
            use_container_width=True
        )

    with col2:

        clear_clicked = st.button(
            "🔄 Clear",
            use_container_width=True
        )

    if clear_clicked:

        st.session_state["last_answer"] = ""
        st.session_state["last_question"] = ""
        st.session_state["last_subject"] = "General"
        st.session_state["followup_answer"] = ""

        st.rerun()

    if generate_clicked:

        if not question.strip():

            st.warning(
                "Please enter a question or topic."
            )

        else:

            st.session_state["last_question"] = question
            st.session_state["last_subject"] = subject

            with st.spinner(
                "🤖 SnapStudy is thinking..."
            ):

                if uploaded_image:

                    image_data = uploaded_image.getvalue()

                    response = client.models.generate_content(

                        model=MODEL,

                        contents=[
                            question,
                            f"Answer style: {answer_mode}",

                            types.Part.from_bytes(
                                data=image_data,
                                mime_type=uploaded_image.type
                            )
                        ],

                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT
                        )
                    )

                else:

                    response = client.models.generate_content(

                        model=MODEL,

                        contents=[
                            f"Subject: {subject}",
                            f"Answer style: {answer_mode}",
                            question
                        ],

                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT
                        )
                    )

            st.session_state["last_answer"] = response.text

            st.session_state["history"].append(
                {
                    "question": question,
                    "answer": response.text,
                    "subject": subject,
                    "date": datetime.now().strftime(
                        "%Y-%m-%d %H:%M"
                    )
                }
            )

    if st.session_state["last_answer"]:

        st.divider()

        st.subheader("💡 Answer")

        st.write(
            st.session_state["last_answer"]
        )

        st.download_button(

            label="📥 Download Answer",

            data=st.session_state["last_answer"],

            file_name="snapstudy_answer.txt",

            mime="text/plain"
        )

        if st.button(
            "🧠 Explain More",
            use_container_width=True
        ):

            with st.spinner(
                "🤖 Preparing a deeper explanation..."
            ):

                more_response = client.models.generate_content(

                    model=MODEL,

                    contents=[
                        "Explain the following answer in more detail using simple language, examples and analogies.",
                        st.session_state["last_answer"]
                    ],

                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    )
                )

            st.subheader(
                "🧠 More Explanation"
            )

            st.write(
                more_response.text
            )


# ============================================================
# TAB 2 - INTERACTIVE QUIZ
# ============================================================

with tabs[1]:

    st.header("📝 Interactive Practice Quiz")

    if not st.session_state["last_question"]:

        st.info(
            "First ask SnapStudy a question or topic in the Study tab."
        )

    else:

        st.write(
            f"Topic: **{st.session_state['last_question']}**"
        )

        if st.button(
            "🎲 Generate 5 MCQs",
            use_container_width=True
        ):

            with st.spinner(
                "📝 Creating your quiz..."
            ):

                quiz_prompt = f"""
Create exactly 5 multiple-choice questions about:

{st.session_state['last_question']}

Return ONLY valid JSON.

Use this exact structure:

{{
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "answer": 0
    }}
  ]
}}

The answer value must be:
0 for the first option,
1 for the second option,
2 for the third option,
3 for the fourth option.

Mix easy and medium questions.
Do not include explanations.
"""

                quiz_response = client.models.generate_content(

                    model=MODEL,

                    contents=[
                        quiz_prompt
                    ],

                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    )
                )

            quiz_data = extract_json(
                quiz_response.text
            )

            if quiz_data and "questions" in quiz_data:

                st.session_state["quiz_data"] = (
                    quiz_data["questions"]
                )

                st.session_state["quiz_score"] = None

                st.success(
                    "Quiz generated!"
                )

            else:

                st.error(
                    "SnapStudy could not format the quiz correctly. Please generate it again."
                )

        if st.session_state["quiz_data"]:

            st.divider()

            st.subheader(
                "🎯 Answer the questions"
            )

            selected_answers = []

            for index, quiz_item in enumerate(
                st.session_state["quiz_data"]
            ):

                st.write(
                    f"### Q{index + 1}. {quiz_item['question']}"
                )

                selected = st.radio(

                    "Choose an answer:",

                    quiz_item["options"],

                    key=f"quiz_{index}"
                )

                selected_answers.append(
                    quiz_item["options"].index(
                        selected
                    )
                )

            if st.button(
                "✅ Submit Quiz",
                use_container_width=True
            ):

                score = 0

                for index, quiz_item in enumerate(
                    st.session_state["quiz_data"]
                ):

                    if (
                        selected_answers[index]
                        == quiz_item["answer"]
                    ):

                        score += 1

                percentage = (
                    score
                    / len(st.session_state["quiz_data"])
                    * 100
                )

                st.session_state["quiz_score"] = percentage

                st.session_state["quiz_history"].append(
                    {
                        "score": percentage,
                        "date": datetime.now().strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        "topic": st.session_state[
                            "last_question"
                        ]
                    }
                )

            if st.session_state["quiz_score"] is not None:

                st.divider()

                score = st.session_state["quiz_score"]

                st.subheader(
                    "🏆 Quiz Result"
                )

                st.metric(
                    "Your Score",
                    f"{score:.0f}%"
                )

                if score == 100:

                    st.success(
                        "Excellent! 🎉"
                    )

                elif score >= 60:

                    st.info(
                        "Good job! Keep practicing. 💪"
                    )

                else:

                    st.warning(
                        "Keep studying and try the quiz again. 📚"
                    )


# ============================================================
# TAB 3 - AI NOTES
# ============================================================

with tabs[2]:

    st.header("📑 AI Notes Generator")

    notes_topic = st.text_input(
        "Enter a topic for notes",
        value=st.session_state.get(
            "last_question",
            ""
        )
    )

    notes_style = st.selectbox(
        "Notes style",
        [
            "Exam Notes",
            "Simple Revision Notes",
            "Detailed Notes",
            "10-Mark Answer"
        ]
    )

    if st.button(
        "📑 Generate Notes",
        use_container_width=True
    ):

        if not notes_topic.strip():

            st.warning(
                "Enter a topic first."
            )

        else:

            with st.spinner(
                "📑 Creating notes..."
            ):

                notes_response = client.models.generate_content(

                    model=MODEL,

                    contents=[
                        f"""
Create study notes about:

{notes_topic}

Notes style:
{notes_style}

Include:
- Definition
- Important concepts
- Key points
- Examples where useful
- Important terms
- Quick revision section
"""
                    ],

                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    )
                )

            st.session_state["notes"] = (
                notes_response.text
            )

    if st.session_state["notes"]:

        st.divider()

        st.subheader(
            "📑 Your Notes"
        )

        st.write(
            st.session_state["notes"]
        )

        st.download_button(

            "📥 Download Notes",

            data=st.session_state["notes"],

            file_name="snapstudy_notes.txt",

            mime="text/plain"
        )


# ============================================================
# TAB 4 - FLASHCARDS
# ============================================================

with tabs[3]:

    st.header("🃏 Flashcards")

    flashcard_topic = st.text_input(
        "Enter a topic for flashcards",
        value=st.session_state.get(
            "last_question",
            ""
        )
    )

    if st.button(
        "🃏 Generate Flashcards",
        use_container_width=True
    ):

        if not flashcard_topic.strip():

            st.warning(
                "Enter a topic first."
            )

        else:

            with st.spinner(
                "🃏 Creating flashcards..."
            ):

                flashcard_prompt = f"""
Create 8 study flashcards about:

{flashcard_topic}

Return ONLY valid JSON.

Use this structure:

{{
  "cards": [
    {{
      "question": "Question",
      "answer": "Answer"
    }}
  ]
}}
"""

                flashcard_response = client.models.generate_content(

                    model=MODEL,

                    contents=[
                        flashcard_prompt
                    ],

                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    )
                )

            flashcards = extract_json(
                flashcard_response.text
            )

            if flashcards and "cards" in flashcards:

                st.session_state["flashcards"] = (
                    flashcards["cards"]
                )

                st.success(
                    "Flashcards created!"
                )

            else:

                st.error(
                    "Could not create flashcards. Try again."
                )

    if st.session_state["flashcards"]:

        st.divider()

        for index, card in enumerate(
            st.session_state["flashcards"]
        ):

            with st.expander(
                f"🃏 Card {index + 1}: {card['question']}"
            ):

                st.write(
                    "### Answer"
                )

                st.write(
                    card["answer"]
                )


# ============================================================
# TAB 5 - FOLLOW-UP QUESTIONS
# ============================================================

with tabs[4]:

    st.header("💬 Ask a Follow-up")

    if not st.session_state["last_answer"]:

        st.info(
            "Generate an answer first in the Study tab."
        )

    else:

        st.write(
            "Ask anything about your previous answer."
        )

        followup_question = st.text_area(
            "Your follow-up question"
        )

        if st.button(
            "💬 Ask Follow-up",
            use_container_width=True
        ):

            if not followup_question.strip():

                st.warning(
                    "Enter a follow-up question."
                )

            else:

                with st.spinner(
                    "🤖 Thinking..."
                ):

                    followup_response = client.models.generate_content(

                        model=MODEL,

                        contents=[
                            f"""
Previous question:
{st.session_state['last_question']}

Previous answer:
{st.session_state['last_answer']}

Student follow-up:
{followup_question}
"""
                        ],

                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT
                        )
                    )

                st.session_state[
                    "followup_answer"
                ] = followup_response.text

        if st.session_state["followup_answer"]:

            st.subheader(
                "💬 Response"
            )

            st.write(
                st.session_state["followup_answer"]
            )


# ============================================================
# TAB 6 - DASHBOARD
# ============================================================

with tabs[5]:

    st.header("📊 Study Dashboard")

    total_questions = len(
        st.session_state["history"]
    )

    total_quizzes = len(
        st.session_state["quiz_history"]
    )

    total_time = (
        st.session_state["study_seconds"]
        // 60
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "📚 Questions Studied",
            total_questions
        )

    with col2:

        st.metric(
            "📝 Quizzes Taken",
            total_quizzes
        )

    with col3:

        st.metric(
            "⏱️ Study Minutes",
            total_time
        )

    st.divider()

    if st.session_state["quiz_history"]:

        st.subheader(
            "📈 Quiz Progress"
        )

        for item in reversed(
            st.session_state["quiz_history"]
        ):

            st.write(
                f"**{item['topic']}** — "
                f"{item['score']:.0f}% "
                f"({item['date']})"
            )

    else:

        st.info(
            "Take your first quiz to see your progress."
        )

    st.divider()

    st.subheader(
        "📚 Study History"
    )

    if st.session_state["history"]:

        for item in reversed(
            st.session_state["history"]
        ):

            with st.expander(
                f"❓ {item['question']} "
                f"— {item['subject']}"
            ):

                st.caption(
                    item["date"]
                )

                st.write(
                    item["answer"]
                )

    else:

        st.info(
            "No study history yet."
        )


# ============================================================
# TAB 7 - STUDY TIMER
# ============================================================

# =========================
# STUDY TIMER
# =========================

if "timer_running" not in st.session_state:
    st.session_state["timer_running"] = False

if "timer_end" not in st.session_state:
    st.session_state["timer_end"] = None

if "timer_duration" not in st.session_state:
    st.session_state["timer_duration"] = 0

if "study_seconds" not in st.session_state:
    st.session_state["study_seconds"] = 0


st.header("⏱️ Study Timer")

st.write("Focus on your studies with a simple countdown timer. 📚")


# -------------------------
# TIMER SETTING
# -------------------------

minutes = st.number_input(
    "Set timer in minutes",
    min_value=1,
    max_value=180,
    value=25,
    step=1,
    disabled=st.session_state["timer_running"]
)


# -------------------------
# START / STOP BUTTONS
# -------------------------

col1, col2 = st.columns(2)


with col1:

    if st.button(
        "▶️ Start Timer",
        use_container_width=True,
        disabled=st.session_state["timer_running"]
    ):

        st.session_state["timer_duration"] = int(minutes * 60)

        st.session_state["timer_end"] = (
            time.time() + st.session_state["timer_duration"]
        )

        st.session_state["timer_running"] = True

        st.rerun()


with col2:

    if st.button(
        "⏹️ Stop Timer",
        use_container_width=True,
        disabled=not st.session_state["timer_running"]
    ):

        if st.session_state["timer_end"] is not None:

            remaining = max(
                0,
                st.session_state["timer_end"] - time.time()
            )

            elapsed = (
                st.session_state["timer_duration"]
                - remaining
            )

            st.session_state["study_seconds"] += int(elapsed)


        st.session_state["timer_running"] = False

        st.session_state["timer_end"] = None

        st.session_state["timer_duration"] = 0

        st.success("✅ Study session saved!")

        st.rerun()


# -------------------------
# LIVE TIMER
# -------------------------

@st.fragment(run_every="1s")
def live_timer():

    if st.session_state["timer_running"]:

        remaining = max(
            0,
            int(
                st.session_state["timer_end"]
                - time.time()
            )
        )

        mins = remaining // 60
        secs = remaining % 60


        # Countdown display
        st.subheader(
            f"⏳ {mins:02d}:{secs:02d}"
        )


        # Timer progress
        if st.session_state["timer_duration"] > 0:

            progress = (
                remaining
                / st.session_state["timer_duration"]
            )

            st.progress(progress)


        if remaining > 0:

            st.info(
                "🔥 Keep studying! "
                "Your timer is running..."
            )

        else:

            # Timer finished
            st.session_state["timer_running"] = False

            st.session_state["timer_end"] = None

            st.session_state["study_seconds"] += (
                st.session_state["timer_duration"]
            )

            st.session_state["timer_duration"] = 0

            st.success(
                "🎉 Study session completed! "
                "Great job! 📚❤️"
            )

    else:

        st.info(
            "⏱️ Timer is ready. "
            "Set your minutes and press Start."
        )


live_timer()


# -------------------------
# TOTAL STUDY TIME
# -------------------------

total_minutes = (
    st.session_state["study_seconds"] // 60
)

st.metric(
    "📊 Total Study Time",
    f"{total_minutes} minutes"
)

    


# ============================================================
# EMAIL STUDY MATERIAL
# ============================================================

st.divider()

st.header("📧 Email Study Material")

st.write(
    "Send your latest answer or notes to your email."
)

email_choice = st.text_input(
    "Email address to receive the material",
    value=st.session_state.get(
        "email",
        ""
    )
)

material_choice = st.selectbox(
    "Choose material",
    [
        "Latest Answer",
        "Latest Notes"
    ]
)

if st.button(
    "📧 Send Email",
    use_container_width=True
):

    if not email_choice.strip():

        st.warning(
            "Please enter an email address."
        )

    else:

        if material_choice == "Latest Answer":

            material = st.session_state[
                "last_answer"
            ]

            subject = "SnapStudy - Your Study Answer"

        else:

            material = st.session_state[
                "notes"
            ]

            subject = "SnapStudy - Your Study Notes"

        if not material:

            st.warning(
                "There is no material available yet."
            )

        else:

            success, message = send_email(

                email_choice,

                subject,

                material
            )

            if success:

                st.success(
                    message
                )

            else:

                st.error(
                    message
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "📚 SnapStudy — Learn smarter with AI"
)