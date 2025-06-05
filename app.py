import streamlit as st

st.title("Ethics Committee Review System")
st.write("Welcome to your Ethics Review App!")

# Example: Display your OpenAI API key from secrets (just for testing; remove later)
st.write("API Key loaded:", st.secrets["OPENAI_API_KEY"][:5] + "..." )

