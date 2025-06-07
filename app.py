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

# --- MODIFIED PARSING FUNCTIONS ---

def extract_section_text(text, section_title):
    # This extracts the full text content under a section heading
    # Looks for the section title and captures text until the next heading or end of string.
    # Pattern for headings: A line starting with a capital letter or number followed by spaces, then words.
    # Excludes the "Additional Questions" section as it's handled separately.
    headings_pattern = r"(?:^|\n)(?!Additional Questions)(?:[A-Z0-9][^\n]*?:|Summary and Recommendation:|English and Construction of the Questionnaire:|Questionnaire and Informed Consent Alignment:|Additional Aspects:|Additional Questions:)"
    
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

def parse_ai_table_like_text(table_like_text, num_columns):
    # This function attempts to parse the AI's non-markdown table text into rows and columns
    # It assumes the first line contains the concatenated headers.
    # It then tries to split subsequent lines into a fixed number of columns based on heuristics.
    
    lines = [line.strip() for line in table_like_text.split('\n') if line.strip()]
    if not lines:
        return [], []

    # Heuristically identify headers from the first line
    headers = []
    if num_columns == 3:
        headers = ["Section/Clause", "Compliance (Yes/No/Partial)", "Explanation"]
    elif num_columns == 2:
        headers = ["Concern", "Explanation"]
    
    # Attempt to split the content into rows based on known patterns or newline
    # This is the trickiest part due to lack of delimiters
    
    # Example for 3 columns (Guideline tables)
    # Input: Informed ConsentPartialThe submission includes informed consent forms, but it lacks details...
    # We need to find "Informed Consent", then "Partial", then the rest.
    
    rows = []
    current_row_data = []
    
    if num_columns == 3:
        # Regex to find common starting patterns for Section/Clause column
        # This is highly heuristic and might need adjustment based on diverse AI outputs
        row_start_patterns = [
            r"^(?:Informed Consent|Research Objectives|Voluntary Participation|Review Process|Participant Safety|Data Management|Data Validation|Investigator Responsibilities|Adverse Event Reporting)",
            r"^(?:Chapter \d+|Section \d+)" # Catch generic chapter/section
        ]
        
        # Regex to find compliance values
        compliance_patterns = r"(Yes|No|Partial)"
        
        full_text_after_headers = table_like_text # Consider the whole block after the "headers" line
        
        # Split by known Section/Clause names, assuming each creates a new row
        # This is a challenging part without clear delimiters from the AI.
        
        # A simpler approach: try to find common compliance indicators
        # This is still very fragile.
        
        # Let's try to split by the known sections in the output
        section_names = [
            "Informed Consent", "Research Objectives", "Voluntary Participation",
            "Review Process", "Participant Safety", "Data Management",
            "Data Validation", "Investigator Responsibilities", "Adverse Event Reporting"
        ]
        
        # Create a combined regex pattern for all section names to split the text
        split_pattern = '|'.join(re.escape(name) for name in section_names)
        
        # Use finditer to find all matches and extract content between them
        matches = list(re.finditer(split_pattern, full_text_after_headers))
        
        for i, match in enumerate(matches):
            section_clause = match.group(0)
            
            start_content_index = match.end()
            end_content_index = matches[i+1].start() if i+1 < len(matches) else len(full_text_after_headers)
            
            content_after_section = full_text_after_headers[start_content_index:end_content_index].strip()
            
            # Now, try to extract Compliance and Explanation from content_after_section
            comp_match = re.search(compliance_patterns, content_after_section)
            
            compliance = ""
            explanation = content_after_section # Default explanation to full content
            
            if comp_match:
                compliance = comp_match.group(0)
                # Split content based on compliance match
                parts = content_after_section.split(compliance, 1)
                explanation = parts[1].strip() if len(parts) > 1 else ""
            
            rows.append([section_clause, compliance, explanation])
            
    elif num_columns == 2:
        # For Concern/Explanation table, similar heuristic
        concern_names = ["Language Clarity", "Structured Format", "Cultural Sensitivity"]
        split_pattern = '|'.join(re.escape(name) for name in concern_names)
        
        full_text_after_headers = table_like_text
        matches = list(re.finditer(split_pattern, full_text_after_headers))
        
        for i, match in enumerate(matches):
            concern = match.group(0)
            
            start_content_index = match.end()
            end_content_index = matches[i+1].start() if i+1 < len(matches) else len(full_text_after_headers)
            
            explanation = full_text_after_headers[start_content_index:end_content_index].strip()
            
            rows.append([concern, explanation])
            
    return headers, rows

# --- REVISED create_pdf_report to use new parsing ---
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
        ("ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)", "ICMR National Ethical Guidelines for Biomedical and Health Research involving Human Participants (2017)", 3),
        ("ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)", "ICMR National Guidelines for Ethics Committees Reviewing Biomedical & Health Research during COVID-19 Pandemic (2020)", 3),
        ("CDSCO Good Clinical Practice Guidelines (2001)", "CDSCO Good Clinical Practice Guidelines (2001)", 3),
    ]

    for full_title, section_header, num_cols in guidelines:
        elements.append(Paragraph(f'<b>{full_title}</b>', styleH))
        section_raw_text = extract_section_text(ai_review, section_header)
        
        # Skip the header line "Section/ClauseCompliance..." in the raw text
        content_for_parsing = ""
        header_found = False
        for line in section_raw_text.split('\n'):
            if not header_found and ("Section/Clause" in line or "Concern" in line): # Identify the concatenated header
                header_found = True
                continue
            if header_found:
                content_for_parsing += line + "\n"

        headers, rows = parse_ai_table_like_text(content_for_parsing.strip(), num_cols)
        
        if headers and rows:
            data = [headers] + rows
            t = Table(data, colWidths=[150, 120, 200] if num_cols == 3 else [180, 290])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F2F6")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#06038D")),
                ('ALIGN',(0,0),(-1,-1),'LEFT'), # Changed to left for better text flow
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#06038D")),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), # Align text to top
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("No structured table content found for this guideline.", styleN))
        elements.append(Spacer(1, 12))

    # --- ADDITIONAL ANALYSIS SECTIONS ---
    
    # English and Construction of the Questionnaire
    elements.append(Paragraph('<b>English and Construction of the Questionnaire</b>', styleH))
    section_header_eq = "English and Construction of the Questionnaire:"
    section_raw_text_eq = extract_section_text(ai_review, section_header_eq)
    
    content_for_parsing_eq = ""
    header_found_eq = False
    for line in section_raw_text_eq.split('\n'):
        if not header_found_eq and ("Concern" in line and "Explanation" in line): # Identify the concatenated header
            header_found_eq = True
            continue
        if header_found_eq:
            content_for_parsing_eq += line + "\n"
            
    headers_eq, rows_eq = parse_ai_table_like_text(content_for_parsing_eq.strip(), 2) # 2 columns for this section
    
    if headers_eq and rows_eq:
        data_eq = [headers_eq] + rows_eq
        t_eq = Table(data_eq, colWidths=[180, 290]) # Adjusted colWidths for 2 columns
        t_eq.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F0F2F6")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#06038D")),
            ('ALIGN',(0,0),(-1,-1),'LEFT'), # Changed to left
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#06038D")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(t_eq)
    else:
        elements.append(Paragraph("No structured concerns table found.", styleN))
    elements.append(Spacer(1, 12))

    # Questionnaire and Informed Consent Alignment
    elements.append(Paragraph('<b>Questionnaire and Informed Consent Alignment</b>', styleH))
    alignment_text = extract_section_text(ai_review, "Questionnaire and Informed Consent Alignment:")
    elements.append(Paragraph(alignment_text if alignment_text else "No information provided.", styleN))
    elements.append(Spacer(1, 12))

    # Additional Aspects
    elements.append(Paragraph('<b>Additional Aspects</b>', styleH))
    aspects_text = extract_section_text(ai_review, "Additional Aspects:")
    # This section usually comes as bullet points from the AI, not a table.
    # Convert bullet points if present for better display.
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
    elements.append(Paragraph('<b>Summary & Recommendation</b>', styleH))
    summary_text = extract_section_text(ai_review, "Summary and Recommendation:")
    elements.append(Paragraph(summary_text, ParagraphStyle('summary', textColor=colors.HexColor("#FF671F"), fontSize=11)))
    elements.append(Spacer(1, 24))

    # Additional Questions
    elements.append(Paragraph('<b>Additional Questions</b>', styleH))
    questions_text = extract_section_text(ai_review, "Additional Questions:")
    if questions_text:
        # Format as bullet points
        for line in questions_text.split('\n'):
            if line.strip().startswith('Can') or line.strip().startswith('How') or line.strip().startswith('Could'):
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

**Markdown Table Formatting Rules: STRICTLY ADHERE TO THIS. ALL TABLES MUST BE VALID MARKDOWN.**
- Start and end every header and data row with a pipe character '|'.
- Separate columns with pipe characters '|'.
- Include the header separator line `|---|---|---|` which must also start and end with '|'.
- **CRITICAL:** Ensure that `| Section/Clause | Compliance (Yes/No/Partial) | Explanation |` is the first line of your table, followed by `|---------------|-----------------------------|-------------|`.
- **Example of a PERFECTLY FORMATTED table (COPY THIS STRUCTURE EXACTLY):**
    ```
    | Section/Clause     | Compliance (Yes/No/Partial) | Explanation                          |
    |--------------------|-----------------------------|--------------------------------------|
    | 4.2 Informed Consent | Yes                         | User provided a valid consent form.  |
    | 5.1 Data Privacy   | Partial                     | Data anonymization needs clarification. |
    ```
- Ensure there are no missing pipes or separator lines.

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

        pdf_buffer = create_pdf_report(user_name, ai_review)
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
