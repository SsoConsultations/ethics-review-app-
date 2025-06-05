import streamlit as st
import os
import PyPDF2
from openai import OpenAI
import pandas as pd
from io import BytesIO

# Set your OpenAI API key
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

REFERENCE_DOCS_PATH = "REFRENCE DOCS"

# 1. Reference Documents
def extract_text_from_pdf(file):
    text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        st.warning(f"Error extracting PDF: {e}")
    return text

def extract_text_from_txt(file):
    try:
        return file.read().decode("utf-8")
    except Exception as e:
        st.warning(f"Error extracting TXT: {e}")
        return ""

def extract_text_from_path(file_path):
    if file_path.lower().endswith(".pdf"):
        with open(file_path, "rb") as f:
            return extract_text_from_pdf(f)
    elif file_path.lower().endswith(".txt"):
        with open(file_path, "rb") as f:
            return extract_text_from_txt(f)
    else:
        return ""

# Load reference docs
reference_docs = []
if os.path.exists(REFERENCE_DOCS_PATH):
    for f in os.listdir(REFERENCE_DOCS_PATH):
        if f.lower().endswith(('.pdf', '.txt')):
            text = extract_text_from_path(os.path.join(REFERENCE_DOCS_PATH, f))
            reference_docs.append({
                "filename": f,
                "text": text
            })

# 2. User Upload
st.title("Ethics Committee Review System")
st.write("Upload your documents (application, proposal, questionnaire, etc.):")
uploaded_files = st.file_uploader(
    "Upload PDF or TXT files", 
    type=["pdf", "txt"], 
    accept_multiple_files=True
)

# 3. Classification
required_types = [
    "Application Form",
    "Research Proposal",
    "Questionnaire",
]
optional_types = [
    "Informed Consent",
    "RAC Confirmation Letter"
]
all_types = required_types + optional_types

def classify_user_doc(text):
    text_lower = text.lower()
    if "informed consent" in text_lower:
        return "Informed Consent"
    elif "questionnaire" in text_lower or "survey" in text_lower:
        return "Questionnaire"
    elif "research proposal" in text_lower or "introduction" in text_lower:
        return "Research Proposal"
    elif "application" in text_lower:
        return "Application Form"
    elif "rac" in text_lower and "confirmation" in text_lower:
        return "RAC Confirmation Letter"
    else:
        return "Unknown"

user_docs = []
for file in uploaded_files:
    if file.name.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file)
    elif file.name.lower().endswith(".txt"):
        text = extract_text_from_txt(file)
    else:
        text = ""
    doc_type = classify_user_doc(text)
    user_docs.append({
        "filename": file.name,
        "type_detected": doc_type,
        "text": text
    })

# 4. Document Summary Table
summary = []
for t in all_types:
    found = False
    for doc in user_docs:
        if doc['type_detected'] == t:
            found = True
            summary.append({
                "Expected Type": t,
                "Detected In": doc['filename'],
                "Status": "OK"
            })
    if not found:
        summary.append({
            "Expected Type": t,
            "Detected In": "",
            "Status": "MISSING" if t in required_types else "Optional - Not Uploaded"
        })

df = pd.DataFrame(summary)
st.subheader("User Document Classification Summary")
st.dataframe(df)

# 5. Prepare prompt for OpenAI
user_documents_text = ""
for doc in user_docs:
    user_documents_text += f"{doc['type_detected']} ({doc['filename']}):\n{doc['text'][:1500]}\n\n"

reference_documents_text = ""
for doc in reference_docs:
    reference_documents_text += f"{doc['filename']}:\n{doc['text'][:1500]}\n\n"

ethics_prompt = f"""
You are an expert in India-related ethics committee working. You will provide answers based only on the reference documents provided below, except for English and grammar, where you may use your own expertise or other references.

If any required user document is missing, or if a document appears to be mislabeled (e.g., the content of a file uploaded as "Questionnaire" looks like a "Research Proposal"), please point this out clearly at the beginning of your response, and suggest to the user which document(s) need to be uploaded or corrected.

Your task is to review the following uploaded documents and provide a detailed analysis as per these points:

1. Are all the required documents provided? Present this in a tabular format.
2. Does this proposal meet ethics requirements as per the reference documents? Give section-wise compliance or non-compliance, with explanations where it is non-compliant.
3. Compare the English and construction of the questionnaire and highlight any concerns (present in a table).
4. Does the questionnaire and informed consent align with the research proposal?
5. Any other aspect that you might want to highlight.
6. Overall recommendation and questions to ask (and why).

User Documents:
{user_documents_text}

Reference Documents:
{reference_documents_text}
"""

# 6. Submit to OpenAI and Show Result
if st.button("Run Ethics Review") and user_docs:
    with st.spinner("Submitting to GPT..."):
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": ethics_prompt}],
                max_tokens=1500,
                temperature=0.2,
            )
            summary = response.choices[0].message.content
            st.subheader("📄 Ethics Committee Review")
            st.write(summary)

            # 7. Download Option
            st.download_button(
                label="Download Review as .txt",
                data=summary,
                file_name="ethics_committee_review.txt",
                mime="text/plain"
            )
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
else:
    st.info("Upload user documents and click 'Run Ethics Review' to start.")
