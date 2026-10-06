import streamlit as st
from ollama import chat
from PIL import Image
import io
import base64
from prompts import SYSTEM_PROMPT, build_user_prompt

st.set_page_config(
    page_title="Trailside Nature Guide",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("🌿 Trailside Nature Guide")
st.caption("Offline • Powered by Gemma 3 • Get outside")

# Image input - works well on mobile
camera_photo = st.camera_input("Take a photo")
uploaded_file = st.file_uploader("Or upload a photo", type=["jpg", "jpeg", "png", "webp"])

user_text = st.text_input(
    "Optional details",
    placeholder="e.g. small red bird, plant near the trail, insect on a leaf..."
)

identify_button = st.button("Identify", type="primary", use_container_width=True)

if identify_button:
    image_source = camera_photo or uploaded_file

    if image_source is None:
        st.warning("Please take or upload a photo first.")
    else:
        with st.spinner("Observing..."):
            # Load and convert image
            image = Image.open(image_source)
            
            # Convert to base64 for Ollama
            buffered = io.BytesIO()
            image.convert("RGB").save(buffered, format="JPEG", quality=85)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            try:
                response = chat(
                    model="gemma3:latest",
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT
                        },
                        {
                            "role": "user",
                            "content": build_user_prompt(user_text),
                            "images": [img_base64]
                        }
                    ]
                )

                result = response["message"]["content"]

                # Show the image + result
                col1, col2 = st.columns([1, 1.2])
                with col1:
                    st.image(image, use_container_width=True)
                with col2:
                    st.markdown("### Field Notes")
                    st.markdown(result)

            except Exception as e:
                st.error(f"Something went wrong: {e}")
                st.info("Make sure Ollama is running and the model `gemma3:latest` is available.")