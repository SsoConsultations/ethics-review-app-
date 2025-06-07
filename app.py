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
    st.image("logo.png", width=120) # This assumes logo.png is in the same directory
    st.markdown("<h3 style='color:#06038D;'>ECR SYSTEM</h3>", unsafe_allow_html=True)
    st.markdown("<span style='color:#FF671F;'>Powered by SSO Consultants</span>", unsafe_allow_html=True)

# --- HEADER WITH LOGO BESIDE HEADING ---
col1, col2 = st.columns([8, 1])
with col1:
    st.markdown("<h1 style='color:#06038D; margin-bottom: 0;'>ECR SYSTEM</h1>", unsafe_allow_html=True)
with col2:
    st.image("logo_ecr.png", width=100) # This assumes logo_ecr.png is in the same directory

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

def clean_table_lines(md_table):
    lines = md_table.strip().split('\n')
    cleaned = []
    for line in lines:
        if line.startswith('|') and not line.endswith('|'):
            line += '|'
        cleaned.append(line)
    return '\n'.join(cleaned)

def extract_first_table(text):
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

def extract_section(text, section_title):
    pattern = rf"{section_title}[\.\:]*\s*(.*?)(?=\n\S|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def get_summary_section(ai_review):
    summary_pattern = r"(Summary|Recommendation|Highlights)[:\n]+(.+?)(?=\n\S|\Z)"
    match = re.search(summary_pattern, ai_review, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(2).strip()
    lines = ai_review.strip().split("\n")
    return "\n".join(lines[:4]) if lines else "No summary provided."

def extract_additional_section(text, section_title):
    pattern = rf"{section_title}[\.\:]*\s*(.*?)(?=\n\S|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def create_pdf_report(user_name, ai_review, logo_path="logo.png"):
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

    # --- MISSING/MISLABELED DOCUMENTS WARNING (if present) ---
    first_lines = ai_review.strip().split('\n')
    if first_lines and ('missing' in first_lines[0].lower() or 'mislabeled' in first_lines[0].lower()):
        elements.append(Paragraph(f"<b>Attention:</b> {first_lines[0]}", ParagraphStyle('warning', textColor=colors.red, fontSize=11)))
        elements.append(Spacer(1, 12))

    # --- TABLES FOR EACH GUIDELINE ---
    guidelines = [
        ("ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)", "ICMR National Ethical Guidelines"),
        ("ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)", "ICMR National Guidelines for Ethics Committees"),
        ("CDSCO Good Clinical Practice Guidelines (2001)", "CDSCO Good Clinical Practice Guidelines"),
    ]

    for title, section_title in guidelines:
        elements.append(Paragraph(f'<b>{title}</b>', styleH))
        section_text = extract_section(ai_review, section_title)
        table_md = extract_first_table(section_text)
        if table_md:
            headers, rows = parse_markdown_table(table_md)
            if headers and rows:
                data = [headers] + rows
                t = Table(data, colWidths=[150, 120, 200])
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
                elements.append(Paragraph("No table found for this guideline.", styleN))
        else:
            elements.append(Paragraph("No table found for this guideline.", styleN))
        elements.append(Spacer(1, 12))

    # --- ADDITIONAL ANALYSIS SECTIONS ---
    elements.append(Paragraph('<b>English and Construction of the Questionnaire</b>', styleH))
    section_text = extract_additional_section(ai_review, "English and construction of the questionnaire")
    table_md = extract_first_table(section_text)
    if table_md:
        headers, rows = parse_markdown_table(table_md)
        if headers and rows:
            data = [headers] + rows
            t = Table(data, colWidths=[180, 180, 110])
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

    elements.append(Paragraph('<b>Alignment with Research Proposal</b>', styleH))
    section_text = extract_additional_section(ai_review, "alignment with the research proposal")
    elements.append(Paragraph(section_text if section_text else "No information provided.", styleN))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph('<b>Other Relevant Aspects</b>', styleH))
    section_text = extract_additional_section(ai_review, "other aspect")
    elements.append(Paragraph(section_text if section_text else "No additional aspects provided.", styleN))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph('<b>Summary & Recommendation</b>', styleH))
    summary_text = get_summary_section(ai_review)
    elements.append(Paragraph(summary_text, ParagraphStyle('summary', textColor=colors.HexColor("#FF671F"), fontSize=11)))
    elements.append(Spacer(1, 24))

    elements.append(Paragraph('<para align="center" color="#FF671F">©copyright SSO Consultants</para>', styleN))
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- MAIN LOGIC ---

if run_review and uploaded_files and user_name:
    with st.spinner("Processing your documents and submitting to GPT..."):
        user_docs = []
        for file in uploaded_files:
            if file.name.lower().endswith(".pdf"):
                text = extract_text_from_pdf(file)
            elif file.name.lower().endswith(".txt"):
                text = file.read().decode("utf-8")
            else:
                text = ""
            user_docs.append({
                "filename": file.name,
                "text": text
            })

        user_documents_text = ""
        for doc in user_docs:
            # Limiting text to 1500 characters as per original prompt, adjust if needed
            user_documents_text += f"{doc['filename']}:\n{doc['text'][:1500]}\n\n"

        ethics_prompt = f"""
You are an expert in Indian research ethics committee review. Your role is to analyze the user's submission against three baseline reference documents:

1. ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)
2. ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)
3. CDSCO Good Clinical Practice Guidelines (2001)

**Instructions:**

- If any required user document is missing, or if a document appears to be mislabeled (e.g., a "Questionnaire" that looks like a "Research Proposal"), clearly state this at the very beginning and suggest which document(s) need to be uploaded or corrected.

- For each of the three reference documents above, create a table with three columns:
    | Section/Clause | Compliance (Yes/No/Partial) | Explanation |
  - The first column should reference the most relevant section or clause of the guideline.
  - The second column should state whether the user's submission is compliant, non-compliant, or partially compliant.
  - The third column should briefly explain your assessment for each section or clause.
  - Only include the most critical and relevant sections/clauses from each guideline (do not include the entire guideline).

**Markdown Table Formatting Rules:**
- All tables must be valid markdown.
- Every row (header and data) must start and end with the '|' character.
- The header separator line must also start and end with '|'.
- Example:
    | Section/Clause | Compliance (Yes/No/Partial) | Explanation |
    |---------------|-----------------------------|-------------|
    | 4.2 Informed Consent | Yes | User provided a valid consent form. |

**Table Placement Rules:**
- Place each table only in the section for its respective guideline, clearly labeled with the guideline name as a heading.
- Do not repeat or place tables in any other section.

**Additional Analysis:**
- After the three tables, provide:
    - A concise summary and overall recommendation for the user's submission (in plain text, not a table).
    - A section on English and construction of the questionnaire, highlighting any concerns in a markdown table (if applicable).
    - An assessment of whether the questionnaire and informed consent align with the research proposal.
    - Any other relevant aspects you wish to highlight.
    - Any additional questions to ask the user, with brief explanations.

---

**User Submission (for review):**
{user_documents_text}

---

**Reference Documents (for your use):**
1. ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)
2. ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)
3. CDSCO Good Clinical Practice Guidelines (2001)
"""

        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # You might consider a more recent model if available and cost-effective
            messages=[{"role": "user", "content": ethics_prompt}],
            max_tokens=1800,
            temperature=0.2,
        )
        ai_review = response.choices[0].message.content

        st.subheader("📄 ECR Report")
        st.write(f"Hello {user_name}, here is your review:")
        st.write(ai_review)

        # Pass "logo.png" as the default path for the PDF report's header logo
        pdf_buffer = create_pdf_report(user_name, ai_review, logo_path="logo.png")
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

# --- FOOTER ---
st.markdown(
    '<div style="text-align:center; color:#FF671F; margin-top:30px;">©copyright SSO Consultants</div>',
    unsafe_allow_html=True
)
