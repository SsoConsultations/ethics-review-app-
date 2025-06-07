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

# --- HEADER WITH LOGO BESIDE HEADING ---
col1, col2 = st.columns([8, 1])
with col1:
    st.markdown("<h1 style='color:#06038D; margin-bottom: 0;'>ECR SYSTEM</h1>", unsafe_allow_html=True)
with col2:
    st.image("logo_ecr.png", width=100) # Updated width to 100 as discussed

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

def extract_section_text(text, section_title):
    # This extracts the full text content under a section heading
    # Looks for the section title and captures text until the next heading or end of string.
    # Pattern for headings: A line starting with a capital letter or number followed by spaces, then words.
    # Excludes the "Additional Questions" section as it's handled separately.
    # Updated to handle potential variations in headings.
    headings_pattern = r"(?:^|\n)(?!Additional Questions)(?:[A-Z0-9][^\n:]*?:|Summary and Recommendation:|English and Construction of the Questionnaire:|Questionnaire and Informed Consent Alignment:|Additional Aspects:|Additional Questions:)"
    
    start_index = text.find(section_title)
    if start_index == -1:
        return ""
    
    # Adjust start_index to capture from the end of the section_title line
    start_index += len(section_title)
    
    # Find the next heading after the current section title
    sub_text = text[start_index:]
    next_heading_match = re.search(headings_pattern, sub_text, re.MULTILINE)
    
    if next_heading_match:
        end_index = start_index + next_heading_match.start()
        return text[start_index:end_index].strip()
    else:
        return text[start_index:].strip() # Capture till end if no next heading

# --- create_pdf_report function (no longer used for download, but kept for reference if needed) ---
def create_pdf_report(user_name, ai_review, logo_path="logo.png"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    styleH = styles['Heading1']
    styleH.textColor = colors.HexColor("#06038D")
    styleN = styles['Normal']
    styleN.fontSize = 11

    # Custom style for section sub-headings (e.g., for "Compliance")
    section_sub_heading_style = ParagraphStyle(
        name='SectionSubHeading',
        parent=styles['h3'],
        fontSize=12,
        leading=14,
        spaceAfter=6,
        textColor=colors.HexColor("#06038D") # Use a brand color
    )
    
    # Custom style for compliance/explanation text
    compliance_text_style = ParagraphStyle(
        name='ComplianceText',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        spaceBefore=3,
        spaceAfter=3,
    )

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
    # Find the first paragraph in AI review. If it contains "missing" or "mislabeled"
    first_paragraph_match = re.match(r"(.*?)(?:\n\n|$)", ai_review.strip(), re.DOTALL)
    if first_paragraph_match:
        first_paragraph = first_paragraph_match.group(1)
        if 'missing' in first_paragraph.lower() or 'mislabeled' in first_paragraph.lower():
            elements.append(Paragraph(f"<b>Attention:</b> {first_paragraph}", ParagraphStyle('warning', textColor=colors.red, fontSize=11)))
            elements.append(Spacer(1, 12))


    # --- GUIDELINE SECTIONS (Now in readable text, not tables) ---
    guideline_sections = [
        "ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)",
        "ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)",
        "CDSCO Good Clinical Practice Guidelines (2001)",
    ]

    for guideline_title in guideline_sections:
        elements.append(Paragraph(f'<b>{guideline_title}</b>', section_sub_heading_style))
        section_content = extract_section_text(ai_review, guideline_title)

        # Attempt to split the section content into logical "rows" based on known phrases
        # This is still a heuristic, but more robust than trying to force into a table.
        # This regex tries to split by the start of a new "Section/Clause" type entry
        # It's less strict than before to catch variations in AI output
        item_pattern = r"(Informed Consent|Research Objectives|Voluntary Participation|Review Process|Participant Safety|Data Management|Data Validation|Investigator Responsibilities|Adverse Event Reporting)"
        
        # Split the text by these markers, keeping the markers
        parts = re.split(item_pattern, section_content, flags=re.IGNORECASE)
        
        # The first part (before the first item_pattern match) might contain the header line.
        # We need to process parts from the second element onwards, in pairs (marker, content)
        
        # Find the actual start of content after the initial header string like "Section/ClauseCompliance..."
        content_start_after_header_match = re.search(r"(Section/Clause|Compliance|Explanation)", section_content, re.IGNORECASE)
        if content_start_after_header_match:
            actual_content_start_index = section_content.find(content_start_after_header_match.group(0)) + len(content_start_after_header_match.group(0))
            section_content_after_header = section_content[actual_content_start_index:].strip()
        else:
            section_content_after_header = section_content # Fallback

        # Re-split the content after the header to accurately get items
        items = re.split(item_pattern, section_content_after_header, flags=re.IGNORECASE)
        
        # Process the items, assuming first is junk, then [Section, Content, Section, Content...]
        processed_items_count = 0
        for i in range(1, len(items), 2):
            if i + 1 < len(items):
                section_clause = items[i].strip()
                item_details = items[i+1].strip()

                # Try to extract Compliance (Yes/No/Partial) and Explanation
                compliance_match = re.search(r"(Yes|No|Partial)", item_details, re.IGNORECASE)
                compliance = ""
                explanation = item_details

                if compliance_match:
                    compliance = compliance_match.group(0)
                    parts_after_compliance = item_details.split(compliance, 1)
                    explanation = parts_after_compliance[1].strip() if len(parts_after_compliance) > 1 else ""
                
                elements.append(Paragraph(f"<b>Section/Clause:</b> {section_clause}", compliance_text_style))
                elements.append(Paragraph(f"<b>Compliance:</b> {compliance if compliance else 'N/A'}", compliance_text_style))
                elements.append(Paragraph(f"<b>Explanation:</b> {explanation if explanation else 'N/A'}", compliance_text_style))
                elements.append(Spacer(1, 6)) # Small space between items
                processed_items_count += 1
        
        if processed_items_count == 0:
            elements.append(Paragraph("No structured details found for this guideline.", styleN))
        elements.append(Spacer(1, 12))

    # --- ADDITIONAL ANALYSIS SECTIONS ---
    
    # English and Construction of the Questionnaire
    elements.append(Paragraph('<b>English and Construction of the Questionnaire</b>', section_sub_heading_style))
    section_content_eq = extract_section_text(ai_review, "English and Construction of the Questionnaire:")
    
    # Similar parsing for English/Questionnaire section
    eq_item_pattern = r"(Language Clarity|Structured Format|Cultural Sensitivity)"
    eq_items = re.split(eq_item_pattern, section_content_eq, flags=re.IGNORECASE)

    processed_eq_items_count = 0
    for i in range(1, len(eq_items), 2):
        if i + 1 < len(eq_items):
            concern = eq_items[i].strip()
            explanation = eq_items[i+1].strip()
            
            elements.append(Paragraph(f"<b>Concern:</b> {concern}", compliance_text_style))
            elements.append(Paragraph(f"<b>Explanation:</b> {explanation if explanation else 'N/A'}", compliance_text_style))
            elements.append(Spacer(1, 6))
            processed_eq_items_count += 1

    if processed_eq_items_count == 0:
        elements.append(Paragraph("No structured concerns found.", styleN))
    elements.append(Spacer(1, 12))

    # Questionnaire and Informed Consent Alignment
    elements.append(Paragraph('<b>Questionnaire and Informed Consent Alignment</b>', section_sub_heading_style))
    alignment_text = extract_section_text(ai_review, "Questionnaire and Informed Consent Alignment:")
    elements.append(Paragraph(alignment_text if alignment_text else "No information provided.", styleN))
    elements.append(Spacer(1, 12))

    # Additional Aspects
    elements.append(Paragraph('<b>Additional Aspects</b>', section_sub_heading_style))
    aspects_text = extract_section_text(ai_review, "Additional Aspects:")
    if aspects_text:
        for line in aspects_text.split('\n'):
            if line.strip().startswith('-'):
                elements.append(Paragraph(f"• {line.strip()[1:].strip()}", styleN))
            else:
                elements.append(Paragraph(line.strip(), styleN))
    else:
        elements.append(Paragraph("No additional aspects provided.", styleN))
    elements.append(Spacer(1, 12))
    
    # Summary & Recommendation
    elements.append(Paragraph('<b>Summary & Recommendation</b>', section_sub_heading_style))
    summary_text = extract_section_text(ai_review, "Summary and Recommendation:")
    elements.append(Paragraph(summary_text, ParagraphStyle('summary', textColor=colors.HexColor("#FF671F"), fontSize=11)))
    elements.append(Spacer(1, 24))

    # Additional Questions
    elements.append(Paragraph('<b>Additional Questions</b>', section_sub_heading_style))
    questions_text = extract_section_text(ai_review, "Additional Questions:")
    if questions_text:
        # Format as bullet points
        for line in questions_text.split('\n'):
            if line.strip().startswith('Can') or line.strip().startswith('How') or line.strip().startswith('Could') or line.strip().startswith('1.') or line.strip().startswith('2.') or line.strip().startswith('3.'):
                elements.append(Paragraph(f"• {line.strip()}", styleN))
            else:
                elements.append(Paragraph(line.strip(), styleN))
    else:
        elements.append(Paragraph("No additional questions provided.", styleN))
    elements.append(Spacer(1, 24))
    
    # --- FOOTER ---
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
            user_documents_text += f"{doc['filename']}:\n{doc['text'][:1500]}\n\n"

        # Refined prompt to strongly emphasize newlines and blank lines
        ethics_prompt = f"""
You are an expert in Indian research ethics committee review. Your role is to analyze the user's submission against three baseline reference documents:

1. ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)
2. ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)
3. CDSCO Good Clinical Practice Guidelines (2001)

**Instructions:**

- If any required user document is missing, or if a document appears to be mislabeled (e.g., a "Questionnaire" that looks like a "Research Proposal"), clearly state this at the very beginning and suggest which document(s) need to be uploaded or corrected.

- For each of the three reference documents above, provide a review. For each point of review, state the relevant Section/Clause, the Compliance (Yes/No/Partial), and an Explanation.
  - The first point should reference the most relevant section or clause of the guideline.
  - The second point should state whether the user's submission is compliant, non-compliant, or partially compliant.
  - The third point should briefly explain your assessment for each section or clause.

**STRICT ADHERENCE TO TEXT FORMATTING (CRITICAL FOR DISPLAY):**
- For the review points under each guideline, present them clearly in the following format. Each label *must* start on a new line:
  Section/Clause: [Your Section/Clause Text]
  Compliance: [Yes/No/Partial]
  Explanation: [Your detailed explanation]
- After each complete 'Section/Clause', 'Compliance', 'Explanation' block, add an extra blank line for visual separation.

**Additional Analysis:**
- After the three guideline reviews, provide:
    - A concise summary and overall recommendation for the user's submission (in plain text).
    - A section on English and construction of the questionnaire, highlighting any concerns. For each concern, clearly label the 'Concern:' and 'Explanation:' on separate lines.
    - An assessment of whether the questionnaire and informed consent align with the research proposal.
    - Any other relevant aspects you wish to highlight (use bullet points if listing multiple items).
    - Any additional questions to ask the user, with brief explanations (use bullet points for each question).

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
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": ethics_prompt}],
            max_tokens=1800,
            temperature=0.2,
        )
        ai_review = response.choices[0].message.content

        # --- Post-process AI review for better display on Streamlit ---
        # This step will insert newlines to ensure each label appears on its own line for better readability.
        # It handles cases where AI might put labels on the same line.

        processed_ai_review = ai_review

        # Ensure "Section/Clause:", "Compliance:", "Explanation:" start on new lines.
        # The regex `(?<!\n)` ensures a newline is added *only if* it's not already preceded by one.
        processed_ai_review = re.sub(r'(?<!\n)(Section/Clause:)', r'\n\1', processed_ai_review, flags=re.IGNORECASE)
        processed_ai_review = re.sub(r'(?<!\n)(Compliance:)', r'\n\1', processed_ai_review, flags=re.IGNORECASE)
        processed_ai_review = re.sub(r'(?<!\n)(Explanation:)', r'\n\1', processed_ai_review, flags=re.IGNORECASE)

        # For "English and Construction of the Questionnaire" section concerns
        processed_ai_review = re.sub(r'(?<!\n)(Concern:)', r'\n\1', processed_ai_review, flags=re.IGNORECASE)

        # Specifically address the issue where the guideline title and first Section/Clause might be on one line
        # e.g., "... (2017) Section/Clause:" -> "... (2017)\nSection/Clause:"
        processed_ai_review = re.sub(r'(\)\s*)(Section/Clause:)', r'\1\n\2', processed_ai_review)


        st.subheader("📄 ECR Report")
        st.write(f"Hello {user_name}, here is your review:")
        st.write(processed_ai_review) # Display the processed content

        # Removed the call to create_pdf_report for download
        # Now providing a plain text download button
        txt_buffer = BytesIO(ai_review.encode('utf-8'))
        file_name = f"{user_name.replace(' ', '_')}_ECR_Report.txt"
        st.download_button(
            label="Download ECR Report as Text",
            data=txt_buffer,
            file_name=file_name,
            mime="text/plain",
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
