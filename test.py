# from ollama import chat

# response = chat(
#     model="gemma3:latest",
#     messages=[{"role": "user", "content": "Hello, are you working?"}]
# )
# print(response["message"]["content"])

import streamlit as st

st.title("Hello")
st.write("Streamlit is working!")