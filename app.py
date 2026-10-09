import base64
import io
import random
import urllib.parse

import ollama
import streamlit as st
from PIL import Image, ImageOps

from prompts import SYSTEM_PROMPT, build_user_prompt

MODEL = "gemma3:latest"  # pin a size (e.g. "gemma3:4b") so updates don't swap the model

st.set_page_config(
    page_title="Trailside",
    page_icon="🍂",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Autumn field guide theme (Hacktoberfest week 1)
# Palette: paper #f6efe0, card #fffaf0, ink #2a2118, bark #5a4636,
#          forest #1f3d2b, moss #4f7a4a, pumpkin #e8731a, rust #b9470a,
#          gold #f2b134, plum #3b1f5e (Hacktoberfest nod)
# Type: Fraunces (display) + Hanken Grotesk (body), with offline fallbacks
# One memorable thing: a warm October morning with leaves drifting down
# behind a quiet, paper-like field journal.
# Layout: wide two-pane. Left = hero, inputs, photo. Right = field notes.
# Pair with .streamlit/config.toml (light base) so widgets follow the theme.
# ---------------------------------------------------------------------------


def treeline(seed: int, base: int, hmin: int, hmax: int, wmin: int, wmax: int, color: str) -> str:
    """A row of pine silhouettes as an SVG data URI."""
    rnd = random.Random(seed)
    d = f"M-40 300 L-40 {base}"
    x = -30.0
    while x < 1240:
        w = rnd.uniform(wmin, wmax)
        h = rnd.uniform(hmin, hmax)
        cx = x + w / 2
        pts = [
            (cx - w / 2, base),
            (cx - w / 4, base - h * 0.42),
            (cx - w / 8, base - h * 0.42),
            (cx, base - h),
            (cx + w / 8, base - h * 0.42),
            (cx + w / 4, base - h * 0.42),
            (cx + w / 2, base),
        ]
        d += "".join(f" L{px:.0f} {py:.0f}" for px, py in pts)
        x += w * rnd.uniform(0.55, 0.9)
    d += f" L1240 {base} L1240 300 Z"
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 300' "
        f"preserveAspectRatio='none'><path d='{d}' fill='{color}'/></svg>"
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&family=Hanken+Grotesk:wght@400;500;600&display=swap');

:root{
  --paper:#f6efe0; --card:#fffaf0; --ink:#2a2118; --bark:#5a4636;
  --forest:#1f3d2b; --moss:#4f7a4a; --pumpkin:#e8731a; --rust:#b9470a;
  --gold:#f2b134; --plum:#3b1f5e; --line:#dccfae;
  --serif:'Fraunces',Georgia,'Times New Roman',serif;
  --sans:'Hanken Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
}

[data-testid="stApp"]{
  font-family:var(--sans);
  color:var(--bark);
  background:
    radial-gradient(90% 50% at 85% -5%, #ffe2a8 0%, transparent 60%),
    radial-gradient(80% 50% at 0% 0%, #ffd9b8 0%, transparent 55%),
    linear-gradient(180deg, #fbf0d9 0%, #f6efe0 55%, #e6ecd0 100%);
}

[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu{display:none !important;}

/* ============================== LAYOUT ============================== */
[data-testid="stMainBlockContainer"]{
  max-width:1280px; padding:3rem 2.5rem 5rem; position:relative; z-index:1;
}

/* two panes */
[data-testid="stHorizontalBlock"]{align-items:flex-start;}
[data-testid="stColumn"]:first-child{position:sticky; top:2rem;}

@media (max-width:900px){
  [data-testid="stMainBlockContainer"]{padding:2rem 1.1rem 5rem;}
  [data-testid="stHorizontalBlock"]{flex-direction:column;}
  [data-testid="stColumn"]{width:100% !important; flex:1 1 100% !important; position:static !important;}
}

/* ============================== THE MORNING ============================== */
[data-testid="stElementContainer"]:has(.sky){height:0; margin:0; padding:0;}
.sky{position:fixed; inset:0; pointer-events:none; z-index:0; overflow:hidden;}
.sky *{position:absolute;}

/* sun */
.sun{
  top:6vh; right:8vw; width:clamp(70px,9vw,120px); aspect-ratio:1; border-radius:50%;
  background:radial-gradient(circle at 40% 35%, #fff6d6 0%, #ffd27a 55%, #f7b040 100%);
  box-shadow:0 0 50px 14px rgba(255,200,100,.55), 0 0 170px 70px rgba(255,190,110,.3);
  animation:bob 16s ease-in-out infinite alternate;
}
@keyframes bob{from{transform:translateY(-6px);} to{transform:translateY(8px);}}

/* clouds */
.cloud{
  height:11vh; width:34vw; border-radius:50%; filter:blur(10px);
  background:radial-gradient(closest-side, rgba(255,255,255,.8), transparent);
  animation:cloud var(--cs) ease-in-out infinite alternate;
}
.cloud.c1{top:9vh; left:6vw; --cs:48s;}
.cloud.c2{top:22vh; left:44vw; width:28vw; opacity:.7; --cs:62s;}
@keyframes cloud{from{transform:translateX(-5vw);} to{transform:translateX(9vw);}}

/* treelines + mist */
.hill{
  left:-3%; width:106%; bottom:0; background-repeat:no-repeat; background-size:100% 100%;
  animation:hillsway var(--hs) ease-in-out infinite alternate;
}
.hill.back{height:28vh; background-image:url("__BACK__"); opacity:.9; --hs:52s;}
.hill.front{height:17vh; background-image:url("__FRONT__"); --hs:40s;}
@keyframes hillsway{from{transform:translateX(-1.2%);} to{transform:translateX(1.2%);}}
.mist{
  left:-10%; right:-10%; bottom:0; height:26vh; filter:blur(16px);
  background:
    radial-gradient(60% 100% at 28% 100%, rgba(255,246,225,.7), transparent 70%),
    radial-gradient(50% 90% at 76% 100%, rgba(255,240,210,.55), transparent 70%);
  animation:mistdrift 28s ease-in-out infinite alternate;
}
@keyframes mistdrift{from{transform:translateX(-5%);} to{transform:translateX(6%);}}

/* falling leaves */
.leaves i{
  top:0; left:0; width:var(--sz); height:var(--sz); opacity:0;
  background:var(--c); border-radius:0 100% 0 100%;
  box-shadow:0 2px 6px rgba(90,50,10,.18);
  animation:fall var(--d) linear infinite;
}
.leaves i::after{
  content:""; inset:0;
  background:linear-gradient(135deg, transparent 47%, rgba(60,25,5,.28) 49% 52%, transparent 54%);
}
@keyframes fall{
  0%{transform:translate3d(0,-10vh,0) rotate(0deg); opacity:0;}
  8%{opacity:.9;}
  50%{transform:translate3d(calc(var(--dx) * .45),52vh,0) rotate(calc(var(--r) * .5));}
  92%{opacity:.9;}
  100%{transform:translate3d(var(--dx),112vh,0) rotate(var(--r)); opacity:0;}
}

/* ============================== THE UI ============================== */
.hero{margin-bottom:1.6rem;}
.hero .kicker{display:flex; align-items:center; gap:.7rem; flex-wrap:wrap; margin:0 0 1rem;}
.hero .badge{
  background:var(--plum); color:#fff4e0; font-size:.74rem; font-weight:600;
  letter-spacing:.06em; text-transform:uppercase; padding:.32rem .8rem; border-radius:999px;
}
.hero .eyebrow{font-size:.92rem; color:var(--rust); font-weight:600; margin:0; letter-spacing:.02em;}
.hero .title{
  font-family:var(--serif); font-weight:600; font-size:clamp(3.2rem,7vw,6rem);
  line-height:.95; letter-spacing:-.03em; margin:0 0 1rem; padding:0;
  color:transparent;
  background:linear-gradient(100deg, var(--forest) 8%, var(--moss) 42%, var(--rust) 88%);
  background-size:200% 100%;
  -webkit-background-clip:text; background-clip:text;
  animation:sheen 12s ease-in-out infinite alternate;
}
@keyframes sheen{from{background-position:0% 50%;} to{background-position:100% 50%;}}
.hero .lede{max-width:44ch; font-size:1.12rem; line-height:1.55; color:var(--bark); margin:0;}

/* tabs */
[data-baseweb="tab-list"]{gap:.25rem; border-bottom:1px solid var(--line);}
button[data-baseweb="tab"]{background:transparent; color:var(--bark);}
button[data-baseweb="tab"] p{color:inherit; font-weight:500;}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--forest);}
button[data-baseweb="tab"]:focus-visible{outline:2px solid var(--moss); outline-offset:2px;}
[data-baseweb="tab-highlight"]{background:var(--pumpkin) !important;}
[data-baseweb="tab-border"]{background:transparent !important;}

/* inputs: warm paper */
[data-testid="stWidgetLabel"] p{color:var(--bark);}
[data-testid="stCameraInput"] > div,
[data-testid="stFileUploaderDropzone"]{
  background:rgba(255,250,235,.75); border:1px dashed #c9b88f; border-radius:14px;
}
[data-testid="stFileUploaderDropzone"] *{color:var(--bark);}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stCameraInput"] button{
  background:var(--forest); color:#fff4e0; border:none;
}
[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stCameraInput"] button *{color:inherit;}
[data-testid="stTextInput"] [data-baseweb="base-input"],
[data-testid="stTextInput"] [data-baseweb="input"]{
  background:rgba(255,250,235,.85); border:1px solid #d8c9a8; border-radius:12px;
}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within{
  border-color:var(--pumpkin); box-shadow:0 0 0 3px rgba(232,115,26,.22);
}
[data-testid="stTextInput"] input{background:transparent; color:var(--ink);}
[data-testid="stTextInput"] input::placeholder{color:rgba(90,70,54,.62);}

/* identify button: a pumpkin-orange stamp */
[data-testid="stButton"] button{
  position:relative; overflow:hidden;
  width:100%; min-height:3.3rem; border-radius:999px; border:none; background:var(--rust);
  box-shadow:0 12px 28px -12px rgba(185,71,10,.7);
  transition:transform .15s ease, box-shadow .25s ease, background .2s ease;
}
[data-testid="stButton"] button::after{
  content:""; position:absolute; top:0; bottom:0; left:-60%; width:40%;
  background:linear-gradient(100deg, transparent, rgba(255,255,255,.4), transparent);
  transform:skewX(-20deg); animation:glint 6s ease-in-out infinite;
}
[data-testid="stButton"] button p{color:#fff8ea; font-weight:600; font-size:1.05rem; position:relative; z-index:1;}
[data-testid="stButton"] button:hover{
  background:#c9500c; transform:translateY(-1px);
  box-shadow:0 0 0 6px rgba(232,115,26,.18), 0 14px 32px -12px rgba(185,71,10,.8);
}
[data-testid="stButton"] button:focus-visible{outline:3px solid var(--forest); outline-offset:3px;}
@keyframes glint{0%,60%{left:-60%;} 100%{left:130%;}}

/* specimen plate: a photo taped to the page */
.plate{
  position:relative; margin:1.8rem 0 1rem; padding:10px 10px 14px; background:#fffdf6;
  border-radius:4px; transform:rotate(-1.2deg);
  border:1px solid rgba(90,70,54,.12);
  box-shadow:0 22px 40px -22px rgba(90,50,10,.45);
}
.plate::before{
  content:""; position:absolute; top:-12px; left:50%; width:96px; height:26px;
  transform:translateX(-50%) rotate(2.5deg);
  background:rgba(242,177,52,.6); border:1px solid rgba(90,70,54,.08);
}
.plate .frame{position:relative; overflow:hidden; border-radius:2px; line-height:0;}
.plate img{display:block; width:100%; max-height:36vh; object-fit:cover;}
.plate.scanning{animation:glow 2.6s ease-in-out infinite;}
.plate.scanning .frame::after{
  content:""; position:absolute; left:0; right:0; top:-40%; height:40%;
  background:linear-gradient(180deg, rgba(232,115,26,0), rgba(232,115,26,.28) 80%, rgba(255,235,190,.95) 100%);
  animation:scan 2.4s cubic-bezier(.55,0,.45,1) infinite;
}
@keyframes scan{from{top:-40%;} to{top:100%;}}
@keyframes glow{
  0%,100%{box-shadow:0 22px 40px -22px rgba(90,50,10,.45), 0 0 0 0 rgba(232,115,26,0);}
  50%{box-shadow:0 22px 40px -22px rgba(90,50,10,.45), 0 0 40px 6px rgba(232,115,26,.35);}
}
.status{
  text-align:center; font-family:var(--serif); font-style:italic; font-size:1.15rem;
  color:var(--rust); margin:.2rem 0 1rem; animation:breathe 2s ease-in-out infinite;
}
@keyframes breathe{0%,100%{opacity:.65;} 50%{opacity:1;}}

/* empty state for the notes pane */
.journal-empty{
  min-height:60vh; display:flex; flex-direction:column; align-items:center; justify-content:center;
  text-align:center; gap:.6rem; padding:2rem;
  border:1.5px dashed #c9b88f; border-radius:16px;
  background:rgba(255,250,235,.6);
}
.journal-empty .leaf-icon{font-size:2.6rem; animation:breathe 3s ease-in-out infinite;}
.journal-empty h3{font-family:var(--serif); font-weight:600; font-size:1.6rem; color:var(--forest); margin:0; padding:0;}
.journal-empty p{max-width:34ch; color:var(--bark); margin:0; line-height:1.55;}

/* field journal page */
.st-key-notes{
  position:relative;
  background:var(--card); border:1px solid #e3d5b5; border-radius:10px;
  padding:2.2rem 2.4rem 2.4rem 3.2rem;
  box-shadow:0 30px 56px -30px rgba(90,50,10,.5);
  animation:unfold .9s ease both;
}
.st-key-notes::before{
  content:""; position:absolute; left:1.35rem; top:1rem; bottom:1rem;
  border-left:2px dashed rgba(185,71,10,.28);
}
@keyframes unfold{from{opacity:0; transform:translateY(14px);} to{opacity:1; transform:none;}}
.st-key-notes p, .st-key-notes li, .st-key-notes span, .st-key-notes strong, .st-key-notes em,
.st-key-notes td, .st-key-notes th, .st-key-notes blockquote{
  color:var(--ink); font-size:1.02rem; line-height:1.65;
}
.st-key-notes .notes-title, .st-key-notes h1, .st-key-notes h2, .st-key-notes h3,
.st-key-notes h4, .st-key-notes h5, .st-key-notes h6{
  font-family:var(--serif); color:var(--forest); letter-spacing:-.01em;
}
.st-key-notes .notes-title{font-size:1.9rem; font-weight:600; margin:0 0 .6rem; padding:0;}
.st-key-notes a{color:#0b5a46; text-decoration:underline;}
.st-key-notes code{background:rgba(31,61,43,.1); color:var(--forest); padding:.1em .35em; border-radius:4px;}
.st-key-notes blockquote{border-left:3px solid var(--moss); margin:.8rem 0; padding-left:1rem;}
.st-key-notes table{border-collapse:collapse;}
.st-key-notes th, .st-key-notes td{border:1px solid rgba(31,61,43,.22); padding:.35rem .6rem;}
.fine{
  font-size:.88rem; line-height:1.5; color:var(--bark); margin:1.2rem 0 0; max-width:60ch;
  background:rgba(255,250,235,.85); border-radius:10px; padding:.7rem .95rem;
}

/* warnings and errors, in theme */
[data-testid="stAlert"], [data-testid="stAlertContainer"]{
  background:#fff3dc; border:1px solid rgba(232,115,26,.55); border-radius:12px;
}
[data-testid="stAlert"] *, [data-testid="stAlertContainer"] *{color:var(--ink);}

@media (max-width:640px){
  .sun{right:6vw;}
  .st-key-notes{padding:1.6rem 1.3rem 1.8rem 2rem;}
  .st-key-notes::before{left:.8rem;}
  .journal-empty{min-height:30vh;}
}
@media (prefers-reduced-motion:reduce){
  .sky *, .hero .title, .plate.scanning, .plate.scanning .frame::after, .status,
  .journal-empty .leaf-icon,
  [data-testid="stButton"] button::after, .st-key-notes{
    animation:none !important;
  }
  .leaves{display:none;}
}
</style>
"""

CSS = CSS.replace("__BACK__", treeline(11, 215, 38, 78, 26, 48, "#cbd8ab")).replace(
    "__FRONT__", treeline(5, 250, 46, 96, 34, 62, "#a3ba84")
)


def sky(n_leaves: int = 18) -> str:
    rnd = random.Random(7)
    colors = ["#e8731a", "#c2410c", "#f2b134", "#a63a12", "#d98324", "#8a5a2b"]
    leaves = []
    for _ in range(n_leaves):
        leaves.append(
            f'<i style="left:{rnd.uniform(0, 100):.1f}%;'
            f"--sz:{rnd.uniform(14, 30):.0f}px;--c:{rnd.choice(colors)};"
            f"--dx:{rnd.uniform(-140, 180):.0f}px;--r:{rnd.choice([-1, 1]) * rnd.uniform(360, 900):.0f}deg;"
            f"--d:{rnd.uniform(15, 28):.1f}s;"
            f'animation-delay:-{rnd.uniform(0, 28):.1f}s"></i>'
        )
    return (
        '<div class="sky">'
        '<div class="sun"></div>'
        '<div class="cloud c1"></div><div class="cloud c2"></div>'
        '<div class="hill back"></div><div class="mist"></div><div class="hill front"></div>'
        f'<div class="leaves">{"".join(leaves)}</div>'
        "</div>"
    )


def plate(b64: str, scanning: bool) -> str:
    cls = "plate scanning" if scanning else "plate"
    return (
        f'<figure class="{cls}"><div class="frame">'
        f'<img alt="Your photo" src="data:image/jpeg;base64,{b64}"></div></figure>'
    )


st.markdown(CSS, unsafe_allow_html=True)
st.markdown(sky(), unsafe_allow_html=True)

left, right = st.columns([5, 7], gap="large")

# ---------------- left pane: hero, inputs, photo ----------------
with left:
    st.markdown(
        '<div class="hero">'
        '<div class="kicker"><span class="badge">Hacktoberfest · Week 1</span>'
        '<p class="eyebrow">Autumn field guide</p></div>'
        '<h1 class="title">Trailside</h1>'
        '<p class="lede">Photograph a plant, bird, insect or fungus and get field notes. '
        "Everything runs on your device, so no signal is needed.</p></div>",
        unsafe_allow_html=True,
    )
    openCamera = st.button("Open Camera", type= "primary")
    if openCamera:
      tab_cam, tab_up = st.tabs(["Take a photo", "Upload"])
      with tab_cam:
          camera_photo = st.camera_input("Camera", label_visibility="collapsed")
      with tab_up:
          uploaded_file = st.file_uploader(
              "Photo", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed"
          )
    

    user_text = st.text_input(
        "What do you already know? (optional)",
        placeholder="Small red bird, plant near the trail, insect on a leaf",
    )

    identify = st.button("Identify", type="primary")
    save = st.button("Save to LogBook", type= "primary")

    plate_slot = st.empty()
    status = st.empty()

# ---------------- right pane: field notes ----------------
with right:
    stage = st.empty()
    stage.markdown(
        '<div class="journal-empty"><div class="leaf-icon">🍂</div>'
        "<h3>Your field journal is empty</h3>"
        "<p>Take or upload a photo and your field notes will be written here.</p></div>",
        unsafe_allow_html=True,
    )

if identify:
    source = camera_photo or uploaded_file

    if source is None:
        with right:
            st.warning("Take or upload a photo first.")
    else:
        image = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        image.thumbnail((1024, 1024))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        jpeg = buf.getvalue()
        b64 = base64.b64encode(jpeg).decode()

        plate_slot.markdown(plate(b64, scanning=True), unsafe_allow_html=True)
        status.markdown('<p class="status">Looking closely…</p>', unsafe_allow_html=True)

        try:
            stream = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_user_prompt(user_text),
                        "images": [jpeg],
                    },
                ],
                stream=True,
            )
            first = next(stream, None)  # waits for the model; errors surface here
            status.empty()
            stage.empty()

            def tokens():
                if first is not None:
                    yield first["message"]["content"]
                for chunk in stream:
                    yield chunk["message"]["content"]

            with right:
                with st.container(key="notes"):
                    st.markdown('<h2 class="notes-title">Field notes</h2>', unsafe_allow_html=True)
                    st.write_stream(tokens())

                st.markdown(
                    '<p class="fine">A photo can fool a model. Check anything important with a local '
                    "guide, and don't taste or handle anything you can't name for certain.</p>",
                    unsafe_allow_html=True,
                )

            plate_slot.markdown(plate(b64, scanning=False), unsafe_allow_html=True)

        except ollama.ResponseError as e:
            plate_slot.empty()
            status.empty()
            with right:
                if e.status_code == 404:
                    st.error(f"The model `{MODEL}` isn't installed. Run `ollama pull {MODEL}`, then try again.")
                else:
                    st.error(f"Ollama returned an error: {e}")
        except ConnectionError:
            plate_slot.empty()
            status.empty()
            with right:
                st.error("Can't reach Ollama. Start it with `ollama serve`, then try again.")
        except Exception as e:
            plate_slot.empty()
            status.empty()
            with right:
                st.error(f"Identification failed: {e}")