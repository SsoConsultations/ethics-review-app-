import streamlit as st
import os

st.title("Ethics Committee Review System")
st.write("Welcome to your Ethics Review App!")

# Path to your reference docs folder
REFERENCE_DOCS_PATH = "REFRENCE DOCS"

# List all files in the reference docs folder
if os.path.exists(REFERENCE_DOCS_PATH):
    files = os.listdir(REFERENCE_DOCS_PATH)
    pdf_files = [f for f in files if f.lower().endswith('.pdf')]
    if pdf_files:
        st.subheader("Reference Documents:")
        for pdf in pdf_files:
            st.write(f"- {pdf}")
    else:
        st.info("No PDF reference documents found.")
else:
    st.error("Reference documents folder not found.")
