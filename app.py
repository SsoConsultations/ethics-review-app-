import streamlit as st
import os
import PyPDF2
from openai import OpenAI
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
import re

# --- SIDEBAR WITH LOGO AND COMPANY INFO ---
with st.sidebar:
    st.image("logo.png", width=120)
    st.markdown("<h3 style='color:#06038D;'>ECR SYSTEM</h3>", unsafe_allow_html=True)
    st.markdown("<span style='color:#FF671F;'>Powered by SSO Consultants</span>", unsafe_allow_html=True)

# --- BORDER START ---
st.markdown("""
    <style>
    .main-container {
        border: 3px solid #06038D;
        border-radius: 15px;
        padding: 30px 30px 10px 30px;
        background-color: #FFFFFF;
        margin-bottom: 30px;
        box-shadow: 0 4px 24px rgba(6,3,141,0.08);
    }
    </style>
    <div class="main-container">
""", unsafe_allow_html=True)

# --- HEADER WITH LOGO ---
col1, col2 = st.columns([8, 1])
with col1:
    st.markdown("<h1 style='color:#06038D;'>ECR SYSTEM</h1>", unsafe_allow_html=True)
with col2:
    st.image("logo.png", width=80)

user_name = st.text_input("Enter your name")
if user_name:
    st.success(f"Welcome, {user_name}!")

st.markdown(
    "<h4 style='color:#FF671F;'>Upload your documents (application, proposal, questionnaire, etc.):</h4>",
    unsafe_allow_html=True
)
uploaded_files = st.file_uploader(
    "Upload PDF or TXT files",
    type=["pdf", "txt"],
    accept_multiple_files=True
)

run_review = st.button("Run Ethics Review")

# --- HELPER FUNCTIONS ---

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

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

def clean_table_lines(md_table):
    lines = md_table.strip().split('\n')
    cleaned = []
    for line in lines:
        # If line starts with | but doesn't end with |, add it
        if line.startswith('|') and not line.endswith('|'):
            line += '|'
        cleaned.append(line)
    return '\n'.join(cleaned)

def extract_first_table(text):
    # More robust regex for markdown tables
    table_pattern = r"(\|.*?\|\n\|[-| :]+\|\n(?:\|.*?\|\n?)+)"
    match = re.search(table_pattern, text, re.DOTALL)
    if match:
        return clean_table_lines(match.group(1).strip())
    return ""

def parse_markdown_table(md_table):
    lines = [line.strip() for line in md_table.strip().split('\n') if '|' in line]
    if len(lines) < 2:
        return [], []
    headers = [h.strip() for h in lines[0].split('|')[1:-1]]
    rows = []
    for line in lines[2:]:
        row = [c.strip() for c in line.split('|')[1:-1]]
        if row and any(cell != "" for cell in row):
            rows.append(row)
    return headers, rows

def extract_section(text, section_number):
    # More robust: period after number is optional
    pattern = rf"\n{section_number}\.?\s*(.*?)(?=\n\d+\.?\s|$)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""

def get_summary_section(ai_review):
    summary_pattern = r"(Summary|Highlights|Key Findings)[:\n]+(.+?)(?=\n\d+\.?\s|$)"
    match = re.search(summary_pattern, ai_review, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(2).strip()
    lines = ai_review.strip().split("\n")
    return "\n".join(lines[:4]) if lines else "No summary provided."

def create_pdf_report(user_name, summary, ai_review, logo_path="logo.png"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    styleH = styles['Heading1']
    styleH.textColor = colors.HexColor("#06038D")
    styleN = styles['Normal']
    styleN.fontSize = 11

    # --- LOGO AND TITLE ---
    table_data = []
    try:
        img = Image(logo_path, width=60, height=60)
        table_data.append([Paragraph('<b>ECR Report</b>', styleH), img])
    except Exception:
        table_data.append([Paragraph('<b>ECR Report</b>', styleH), ""])
    t = Table(table_data, colWidths=[400, 60])
    elements.append(t)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Prepared for: {user_name}", styles['Italic']))
    elements.append(Spacer(1, 12))

    # --- SUMMARY SECTION ---
    elements.append(Paragraph('<b>Summary</b>', styleH))
    summary_text = get_summary_section(ai_review)
    elements.append(Paragraph(summary_text, ParagraphStyle('summary', textColor=colors.HexColor("#FF671F"), fontSize=11)))
    elements.append(Spacer(1, 12))

    # --- USER DOCUMENT CLASSIFICATION TABLE ---
    elements.append(Paragraph('<b>User Document Classification Summary</b>', styleH))
    if summary:
        headers = ['Expected Type', 'Detected In', 'Status']
        data = [headers] + [[row['Expected Type'], row['Detected In'], row['Status']] for row in summary]
        t = Table(data, colWidths=[110, 210, 110])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F2F6")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#06038D")),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#06038D")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No document summary available.", styleN))
    elements.append(Spacer(1, 12))

    # --- EXTRACT AND RENDER AI TABLES ---
    # 1. Required Documents Table
    elements.append(Paragraph('<b>Required Documents Table</b>', styleH))
    required_table_md = extract_first_table(extract_section(ai_review, "1"))
    if required_table_md:
        headers, rows = parse_markdown_table(required_table_md)
        if headers and rows:
            data = [headers] + rows
            t = Table(data, colWidths=[max(80, 500//len(headers))]*len(headers))
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F2F6")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#06038D")),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#06038D")),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No required documents table found.", styleN))
    else:
        elements.append(Paragraph("No required documents table found.", styleN))
    elements.append(Spacer(1, 12))

    # 2. Concerns & Explanation Table (from section 3)
    elements.append(Paragraph('<b>Questionnaire English & Construction Concerns</b>', styleH))
    concerns_table_md = extract_first_table(extract_section(ai_review, "3"))
    if concerns_table_md:
        headers, rows = parse_markdown_table(concerns_table_md)
        if headers and rows:
            data = [headers] + rows
            t = Table(data, colWidths=[max(80, 500//len(headers))]*len(headers))
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F2F6")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#06038D")),
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#06038D")),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No concerns table found.", styleN))
    else:
        elements.append(Paragraph("No concerns table found.", styleN))
    elements.append(Spacer(1, 12))

    # --- REMAINING SECTIONS (2, 4, 5, 6) ---
    for section_num, section_title in [
        ("2", "Ethics Compliance"),
        ("4", "Alignment Check"),
        ("5", "Other Aspects"),
        ("6", "Overall Recommendation"),
    ]:
        elements.append(Paragraph(f'<b>{section_title}</b>', styleH))
        section_text = extract_section(ai_review, section_num)
        elements.append(Paragraph(section_text if section_text else "No information provided.", styleN))
        elements.append(Spacer(1, 12))

    # --- FOOTER ---
    elements.append(Spacer(1, 24))
    elements.append(Paragraph('<para align="center" color="#FF671F">©copyright SSO Consultants</para>', styleN))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- MAIN LOGIC ---

if run_review and uploaded_files and user_name:
    with st.spinner("Processing your documents and submitting to GPT..."):
        # --- LOAD AND PROCESS REFERENCE DOCS ---
        REFERENCE_DOCS_PATH = "REFRENCE DOCS"
        reference_docs = []
        if os.path.exists(REFERENCE_DOCS_PATH):
            for f in os.listdir(REFERENCE_DOCS_PATH):
                if f.lower().endswith(('.pdf', '.txt')):
                    file_path = os.path.join(REFERENCE_DOCS_PATH, f)
                    if f.lower().endswith('.pdf'):
                        with open(file_path, "rb") as file:
                            text = extract_text_from_pdf(file)
                    else:
                        with open(file_path, "r", encoding="utf-8") as file:
                            text = file.read()
                    reference_docs.append({
                        "filename": f,
                        "text": text
                    })

        # --- PROCESS USER UPLOADED DOCS ---
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

        user_docs = []
        for file in uploaded_files:
            if file.name.lower().endswith(".pdf"):
                text = extract_text_from_pdf(file)
            elif file.name.lower().endswith(".txt"):
                text = file.read().decode("utf-8")
            else:
                text = ""
            doc_type = classify_user_doc(text)
            user_docs.append({
                "filename": file.name,
                "type_detected": doc_type,
                "text": text
            })

        # --- DOCUMENT SUMMARY TABLE ---
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

        # --- PREPARE PROMPT FOR OPENAI ---
        user_documents_text = ""
        for doc in user_docs:
            user_documents_text += f"{doc['type_detected']} ({doc['filename']}):\n{doc['text'][:1500]}\n\n"

        reference_documents_text = ""
        for doc in reference_docs:
            reference_documents_text += f"{doc['filename']}:\n{doc['text'][:1500]}\n\n"

        # --- IMPROVED PROMPT ENGINEERING ---
        ethics_prompt = f"""
You are an expert in India-related ethics committee working. You will provide answers based only on the reference documents provided below, except for English and grammar, where you may use your own expertise or other references.

**IMPORTANT INSTRUCTIONS FOR TABLES:**
- All tables must be valid markdown.
- Every row (header and data) must start and end with the '|' character.
- The header separator line must also start and end with '|'.
- Example:
| Column 1 | Column 2 |
|----------|----------|
| Data A   | Data B   |

- Tables must only appear in the explicitly requested numbered sections (e.g., Section 1 for Required Documents).
- Do not repeat or place tables in any other section.

Your task is to review the following uploaded documents and provide a detailed analysis as per these points:

1. Are all the required documents provided? Present this in a markdown table as shown above.
2. Does this proposal meet ethics requirements as per the reference documents? Give section-wise compliance or non-compliance, with explanations where it is non-compliant.
3. Compare the English and construction of the questionnaire and highlight any concerns (present in a markdown table as shown above).
4. Does the questionnaire and informed consent align with the research proposal?
5. Any other aspect that you might want to highlight.
6. Overall recommendation and questions to ask (and why).

Please start your answer with a 2-3 line summary of your findings.

User Name:
{user_name}

User Documents:
{user_documents_text}

Reference Documents:
{reference_documents_text}
"""

        # --- CALL OPENAI ---
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": ethics_prompt}],
            max_tokens=1500,
            temperature=0.2,
        )
        ai_review = response.choices[0].message.content

        st.subheader("📄 ECR Report")
        st.write(f"Hello {user_name}, here is your review:")
        st.write(ai_review)

        # --- CREATE STRUCTURED PDF REPORT ---
        pdf_buffer = create_pdf_report(user_name, summary, ai_review)
        file_name = f"{user_name.replace(' ', '_')}_ECR_Report.pdf"
        st.download_button(
            label="Download ECR Report as PDF",
            data=pdf_buffer,
            file_name=file_name,
            mime="application/pdf",
            key=file_name
        )

elif run_review and not user_name:
    st.warning("Please enter your name above to proceed.")
elif run_review and not uploaded_files:
    st.warning("Please upload at least one document to proceed.")

# --- BORDER END ---
st.markdown("</div>", unsafe_allow_html=True)

# --- FOOTER ---
st.markdown(
    '<div style="text-align:center; color:#FF671F; margin-top:30px;">©copyright SSO Consultants</div>',
    unsafe_allow_html=True
)
