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
    page_icon="🌙",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Night theme
# Palette: midnight #070d24, deep water #0a1a2e, aurora #5dffc0, violet #a98bff,
#          lichen #e9efd8, lantern #f4b942, mist #b9cde0
# Type: Fraunces (display) + Hanken Grotesk (body), with offline fallbacks
# One memorable thing: a living sky (aurora + stars + moon) behind quiet UI.
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
  --deep:#050b1c; --night:#0a1530; --water:#0a1a2e;
  --lichen:#e9efd8; --ink:#17261f; --lantern:#f4b942; --mist:#b9cde0;
  --aurora:#5dffc0; --violet:#a98bff;
  --serif:'Fraunces',Georgia,'Times New Roman',serif;
  --sans:'Hanken Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
}

[data-testid="stApp"]{
  font-family:var(--sans);
  color:var(--mist);
  background:
    radial-gradient(110% 60% at 82% -8%, #1c2c66 0%, transparent 58%),
    radial-gradient(90% 55% at 0% 8%, #0f4650 0%, transparent 55%),
    linear-gradient(180deg, #070d24 0%, #0a1a2e 50%, #06141a 100%);
}

[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu{display:none !important;}

[data-testid="stMainBlockContainer"]{
  max-width:680px; padding:3.5rem 1.25rem 7rem; position:relative; z-index:1;
}

/* ============================== THE SKY ============================== */
[data-testid="stElementContainer"]:has(.sky){height:0; margin:0; padding:0;}
.sky{position:fixed; inset:0; pointer-events:none; z-index:0; overflow:hidden;}
.sky *{position:absolute;}

/* aurora curtains */
.aur{
  left:-25%; width:150%; height:48vh; top:-10vh; border-radius:50%;
  mix-blend-mode:screen; opacity:.5;
  -webkit-mask-image:linear-gradient(180deg,#000 0%,rgba(0,0,0,.65) 45%,transparent 100%);
          mask-image:linear-gradient(180deg,#000 0%,rgba(0,0,0,.65) 45%,transparent 100%);
  animation:sway var(--s) ease-in-out infinite alternate, hue var(--h) ease-in-out infinite alternate;
}
.aur.a1{
  background:linear-gradient(100deg, transparent 4%, rgba(93,255,192,.7) 28%, rgba(70,170,255,.5) 55%, rgba(169,139,255,.55) 78%, transparent 96%);
  --s:17s; --h:36s;
}
.aur.a2{
  top:-4vh; height:36vh; opacity:.4;
  background:linear-gradient(80deg, transparent 8%, rgba(169,139,255,.6) 30%, rgba(93,255,192,.55) 62%, transparent 92%);
  --s:23s; --h:44s; animation-delay:-9s,-14s;
}
.aur.a3{
  top:2vh; height:28vh; opacity:.32;
  background:linear-gradient(120deg, transparent 10%, rgba(80,200,255,.55) 40%, rgba(93,255,192,.5) 70%, transparent 95%);
  --s:29s; --h:52s; animation-delay:-4s,-22s;
}
@keyframes sway{
  0%{transform:translateX(-7%) skewX(-9deg) scaleY(.88);}
  100%{transform:translateX(7%) skewX(11deg) scaleY(1.18);}
}
@keyframes hue{
  from{filter:blur(46px) hue-rotate(0deg);}
  to{filter:blur(46px) hue-rotate(75deg);}
}

/* stars: one element each, many shadows */
.stars{top:0; left:0; background:transparent; border-radius:50%;}
.stars.s1{width:1px; height:1px; animation:twinkle 5s ease-in-out infinite alternate;}
.stars.s2{width:2px; height:2px; animation:twinkle 7s ease-in-out -2s infinite alternate;}
.stars.s3{width:3px; height:3px; animation:twinkle 4s ease-in-out -1s infinite alternate;}
@keyframes twinkle{0%{opacity:.35;} 50%{opacity:1;} 100%{opacity:.55;}}

/* moon */
.moon{
  top:7vh; right:9vw; width:clamp(64px,9vw,108px); aspect-ratio:1; border-radius:50%;
  background:
    radial-gradient(circle at 62% 30%, rgba(160,150,110,.35) 0 7%, transparent 8%),
    radial-gradient(circle at 38% 62%, rgba(160,150,110,.3) 0 10%, transparent 11%),
    radial-gradient(circle at 70% 70%, rgba(160,150,110,.28) 0 5%, transparent 6%),
    radial-gradient(circle at 35% 30%, #fffdf0 0%, #f1e9c8 55%, #cfc59a 100%);
  box-shadow:0 0 36px 8px rgba(255,244,200,.38), 0 0 150px 56px rgba(150,180,255,.2);
  animation:bob 14s ease-in-out infinite alternate;
}
.moon::after{
  content:""; inset:-26%; border-radius:50%; border:1px solid rgba(255,244,200,.18);
  animation:halo 6s ease-in-out infinite;
}
@keyframes bob{from{transform:translateY(-6px);} to{transform:translateY(8px);}}
@keyframes halo{0%,100%{transform:scale(.96); opacity:.15;} 50%{transform:scale(1.12); opacity:.6;}}

/* shooting stars */
.shoot{
  width:150px; height:2px; opacity:0; border-radius:2px;
  background:linear-gradient(90deg, rgba(255,255,255,0), #fff);
  box-shadow:0 0 10px 1px rgba(200,225,255,.7);
  animation:shoot var(--t) linear infinite;
}
@keyframes shoot{
  0%{transform:translate(0,0) rotate(33deg); opacity:0;}
  1.5%{opacity:1;}
  6%{transform:translate(360px,234px) rotate(33deg); opacity:0;}
  100%{transform:translate(360px,234px) rotate(33deg); opacity:0;}
}

/* treelines + mist */
.hill{
  left:-3%; width:106%; bottom:0; background-repeat:no-repeat; background-size:100% 100%;
  animation:hillsway var(--hs) ease-in-out infinite alternate;
}
.hill.back{height:34vh; background-image:url("__BACK__"); opacity:.95;}
.hill.front{height:22vh; background-image:url("__FRONT__"); --hs:40s;}
@keyframes hillsway{from{transform:translateX(-1.4%);} to{transform:translateX(1.4%);}}
.mist{
  left:-10%; right:-10%; bottom:0; height:30vh; filter:blur(16px);
  background:
    radial-gradient(60% 100% at 28% 100%, rgba(170,215,215,.2), transparent 70%),
    radial-gradient(50% 90% at 76% 100%, rgba(150,185,230,.17), transparent 70%);
  animation:mistdrift 28s ease-in-out infinite alternate;
}
@keyframes mistdrift{from{transform:translateX(-5%);} to{transform:translateX(6%);}}

/* fireflies */
.flies i{
  width:5px; height:5px; border-radius:50%; opacity:0;
  background:var(--fc); box-shadow:0 0 12px 4px var(--fg);
  animation:drift var(--d) ease-in-out infinite alternate, blink var(--b) ease-in-out infinite;
}
@keyframes drift{from{transform:translate(0,0);} to{transform:translate(var(--dx),var(--dy));}}
@keyframes blink{0%,100%{opacity:0;} 45%,55%{opacity:.95;}}

/* ============================== THE UI ============================== */
.hero{margin-bottom:2rem;}
.hero .eyebrow{
  font-size:.9rem; color:var(--aurora); margin:0 0 .9rem; opacity:.9; letter-spacing:.02em;
}
.hero .title{
  font-family:var(--serif); font-weight:600; font-size:clamp(3.2rem,13vw,5.4rem);
  line-height:.95; letter-spacing:-.03em; margin:0 0 1rem; padding:0;
  color:transparent;
  background:linear-gradient(100deg, var(--lichen) 18%, #9ff0cf 38%, #c9bcff 56%, var(--lichen) 76%);
  background-size:260% 100%;
  -webkit-background-clip:text; background-clip:text;
  filter:drop-shadow(0 0 26px rgba(110,255,200,.28));
  animation:sheen 10s ease-in-out infinite alternate;
}
@keyframes sheen{from{background-position:0% 50%;} to{background-position:100% 50%;}}
.hero .lede{max-width:36ch; font-size:1.12rem; line-height:1.55; color:var(--mist); margin:0;}

/* tabs */
[data-baseweb="tab-list"]{gap:.25rem; border-bottom:1px solid rgba(233,239,216,.14);}
button[data-baseweb="tab"]{background:transparent; color:var(--mist);}
button[data-baseweb="tab"] p{color:inherit; font-weight:500;}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--lichen);}
button[data-baseweb="tab"]:focus-visible{outline:2px solid var(--aurora); outline-offset:2px;}
[data-baseweb="tab-highlight"]{background:var(--lantern) !important; box-shadow:0 0 12px 1px rgba(244,185,66,.6);}
[data-baseweb="tab-border"]{background:transparent !important;}

/* inputs: frosted night glass */
[data-testid="stWidgetLabel"] p{color:var(--mist);}
[data-testid="stCameraInput"] > div,
[data-testid="stFileUploaderDropzone"]{
  background:rgba(200,220,255,.06); border:1px dashed rgba(200,225,255,.3); border-radius:14px;
  -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px);
}
[data-testid="stFileUploaderDropzone"] *{color:var(--mist);}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stCameraInput"] button{
  background:rgba(233,239,216,.1); color:var(--lichen); border:1px solid rgba(233,239,216,.25);
}
[data-testid="stTextInput"] [data-baseweb="base-input"],
[data-testid="stTextInput"] [data-baseweb="input"]{
  background:rgba(200,220,255,.07); border:1px solid rgba(200,225,255,.22); border-radius:12px;
  -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px);
}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within{
  border-color:var(--lantern); box-shadow:0 0 0 3px rgba(244,185,66,.22);
}
[data-testid="stTextInput"] input{background:transparent; color:var(--lichen);}
[data-testid="stTextInput"] input::placeholder{color:rgba(185,205,224,.62);}

/* identify button: a lantern in the dark */
[data-testid="stButton"] button{
  position:relative; overflow:hidden;
  width:100%; min-height:3.3rem; border-radius:999px; border:none; background:var(--lantern);
  box-shadow:0 0 0 0 rgba(244,185,66,.45), 0 12px 34px -12px rgba(244,185,66,.7);
  transition:transform .15s ease, box-shadow .25s ease, background .2s ease;
  animation:lantern 3.4s ease-in-out infinite;
}
[data-testid="stButton"] button::after{
  content:""; position:absolute; top:0; bottom:0; left:-60%; width:40%;
  background:linear-gradient(100deg, transparent, rgba(255,255,255,.55), transparent);
  transform:skewX(-20deg); animation:glint 5s ease-in-out infinite;
}
[data-testid="stButton"] button p{color:#2a1d02; font-weight:600; font-size:1.05rem; position:relative; z-index:1;}
[data-testid="stButton"] button:hover{
  background:#ffc95c; transform:translateY(-1px);
  box-shadow:0 0 0 7px rgba(244,185,66,.16), 0 14px 38px -12px rgba(244,185,66,.8);
}
[data-testid="stButton"] button:focus-visible{outline:3px solid var(--lichen); outline-offset:3px;}
@keyframes lantern{
  0%,100%{box-shadow:0 0 0 0 rgba(244,185,66,0), 0 12px 34px -12px rgba(244,185,66,.6);}
  50%{box-shadow:0 0 0 6px rgba(244,185,66,.1), 0 14px 42px -10px rgba(244,185,66,.85);}
}
@keyframes glint{0%,60%{left:-60%;} 100%{left:130%;}}

/* specimen plate, moonlit */
.plate{
  position:relative; margin:2.2rem 0 1.4rem; padding:12px; background:var(--lichen);
  border-radius:6px; transform:rotate(-1.2deg);
  box-shadow:0 30px 60px -22px rgba(0,0,0,.75), 0 0 70px -10px rgba(120,160,255,.25);
}
.plate .frame{position:relative; overflow:hidden; border-radius:2px; line-height:0;}
.plate img{display:block; width:100%; max-height:62vh; object-fit:cover;}
.plate.scanning{animation:glow 2.6s ease-in-out infinite;}
.plate.scanning .frame::after{
  content:""; position:absolute; left:0; right:0; top:-40%; height:40%;
  background:linear-gradient(180deg, rgba(93,255,192,0), rgba(93,255,192,.3) 80%, rgba(220,255,240,.95) 100%);
  animation:scan 2.4s cubic-bezier(.55,0,.45,1) infinite;
}
@keyframes scan{from{top:-40%;} to{top:100%;}}
@keyframes glow{
  0%,100%{box-shadow:0 30px 60px -22px rgba(0,0,0,.75), 0 0 0 0 rgba(93,255,192,0);}
  50%{box-shadow:0 30px 60px -22px rgba(0,0,0,.75), 0 0 54px 8px rgba(93,255,192,.38);}
}
.status{
  text-align:center; font-family:var(--serif); font-style:italic; font-size:1.15rem;
  color:var(--lantern); margin:.2rem 0 1rem; animation:breathe 2s ease-in-out infinite;
}
@keyframes breathe{0%,100%{opacity:.65;} 50%{opacity:1;}}

/* field journal page, lit by lantern */
.st-key-notes{
  background:var(--lichen); border-radius:10px; padding:1.7rem 1.5rem 1.9rem;
  box-shadow:0 34px 64px -30px rgba(0,0,0,.85), 0 0 60px -14px rgba(244,185,66,.28);
  animation:unfold .9s ease both;
}
@keyframes unfold{from{opacity:0; transform:translateY(14px);} to{opacity:1; transform:none;}}
.st-key-notes p, .st-key-notes li, .st-key-notes span, .st-key-notes strong, .st-key-notes em,
.st-key-notes td, .st-key-notes th, .st-key-notes blockquote{
  color:var(--ink); font-size:1.02rem; line-height:1.65;
}
.st-key-notes .notes-title, .st-key-notes h1, .st-key-notes h2, .st-key-notes h3,
.st-key-notes h4, .st-key-notes h5, .st-key-notes h6{
  font-family:var(--serif); color:#0f3b2f; letter-spacing:-.01em;
}
.st-key-notes .notes-title{font-size:1.9rem; font-weight:600; margin:0 0 .6rem; padding:0;}
.st-key-notes a{color:#0b5a46; text-decoration:underline;}
.st-key-notes code{background:rgba(15,59,47,.1); color:#0f3b2f; padding:.1em .35em; border-radius:4px;}
.st-key-notes blockquote{border-left:3px solid #7fa77f; margin:.8rem 0; padding-left:1rem;}
.st-key-notes table{border-collapse:collapse;}
.st-key-notes th, .st-key-notes td{border:1px solid rgba(15,59,47,.25); padding:.35rem .6rem;}
.fine{font-size:.88rem; line-height:1.5; color:var(--mist); margin:1.2rem .2rem 0; max-width:52ch;}

/* warnings and errors, in theme */
[data-testid="stAlert"], [data-testid="stAlertContainer"]{
  background:rgba(200,220,255,.08); border:1px solid rgba(244,185,66,.4); border-radius:12px;
  -webkit-backdrop-filter:blur(8px); backdrop-filter:blur(8px);
}
[data-testid="stAlert"] *, [data-testid="stAlertContainer"] *{color:var(--lichen);}

@media (max-width:640px){
  .aur{filter:blur(34px);}
  .moon{right:6vw;}
}
@media (prefers-reduced-motion:reduce){
  .sky *, .hero .title, .plate.scanning, .plate.scanning .frame::after, .status,
  [data-testid="stButton"] button, [data-testid="stButton"] button::after, .st-key-notes{
    animation:none !important;
  }
  .flies i{opacity:.6;}
  .shoot{display:none;}
}
</style>
"""

CSS = CSS.replace("__BACK__", treeline(11, 215, 38, 78, 26, 48, "#0b2230")).replace(
    "__FRONT__", treeline(5, 250, 46, 96, 34, 62, "#040a12")
)


def star_shadows(n: int, seed: int, blur: int, ymax: float = 78) -> str:
    rnd = random.Random(seed)
    cols = ["#ffffff", "#cfe3ff", "#fff1c9", "#d9ccff"]
    return ",".join(
        f"{rnd.uniform(0, 100):.1f}vw {rnd.uniform(0, ymax):.1f}vh {blur}px 0 {rnd.choice(cols)}"
        for _ in range(n)
    )


def sky(n_flies: int = 22) -> str:
    rnd = random.Random(7)
    flies = []
    for i in range(n_flies):
        warm = i % 3 != 0
        core, glow = ("#ffe9a8", "rgba(244,185,66,.55)") if warm else ("#c8ffe9", "rgba(93,255,192,.5)")
        flies.append(
            f'<i style="left:{rnd.uniform(2, 98):.1f}%;top:{rnd.uniform(30, 92):.1f}%;'
            f"--fc:{core};--fg:{glow};"
            f'--dx:{rnd.uniform(-60, 60):.0f}px;--dy:{rnd.uniform(-90, 40):.0f}px;'
            f'--d:{rnd.uniform(9, 18):.1f}s;--b:{rnd.uniform(3, 7):.1f}s;'
            f'animation-delay:-{rnd.uniform(0, 15):.1f}s,-{rnd.uniform(0, 6):.1f}s"></i>'
        )
    shoots = "".join(
        f'<div class="shoot" style="left:{l}%;top:{t}%;--t:{d}s;animation-delay:-{o}s"></div>'
        for l, t, d, o in [(8, 6, 13, 3), (34, 2, 19, 11), (52, 14, 23, 17)]
    )
    return (
        '<div class="sky">'
        '<div class="aur a1"></div><div class="aur a2"></div><div class="aur a3"></div>'
        f'<div class="stars s1" style="box-shadow:{star_shadows(90, 3, 0)}"></div>'
        f'<div class="stars s2" style="box-shadow:{star_shadows(36, 8, 1)}"></div>'
        f'<div class="stars s3" style="box-shadow:{star_shadows(10, 21, 3)}"></div>'
        '<div class="moon"></div>'
        f"{shoots}"
        '<div class="hill back"></div><div class="mist"></div><div class="hill front"></div>'
        f'<div class="flies">{"".join(flies)}</div>'
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
st.markdown(
    '<div class="hero"><p class="eyebrow">Night walk edition</p>'
    '<h1 class="title">Trailside</h1>'
    '<p class="lede">Photograph a plant, bird, insect or fungus and get field notes. '
    "Everything runs on your device, so no signal is needed.</p></div>",
    unsafe_allow_html=True,
)

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

if identify:
    source = camera_photo or uploaded_file

    if source is None:
        st.warning("Take or upload a photo first.")
    else:
        image = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        image.thumbnail((1024, 1024))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        jpeg = buf.getvalue()
        b64 = base64.b64encode(jpeg).decode()

        plate_slot = st.empty()
        plate_slot.markdown(plate(b64, scanning=True), unsafe_allow_html=True)
        status = st.empty()
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

            def tokens():
                if first is not None:
                    yield first["message"]["content"]
                for chunk in stream:
                    yield chunk["message"]["content"]

            with st.container(key="notes"):
                st.markdown('<h2 class="notes-title">Field notes</h2>', unsafe_allow_html=True)
                st.write_stream(tokens())

            plate_slot.markdown(plate(b64, scanning=False), unsafe_allow_html=True)
            st.markdown(
                '<p class="fine">A photo can fool a model. Check anything important with a local '
                "guide, and don't taste or handle anything you can't name for certain.</p>",
                unsafe_allow_html=True,
            )

        except ollama.ResponseError as e:
            plate_slot.empty()
            status.empty()
            if e.status_code == 404:
                st.error(f"The model `{MODEL}` isn't installed. Run `ollama pull {MODEL}`, then try again.")
            else:
                st.error(f"Ollama returned an error: {e}")
        except ConnectionError:
            plate_slot.empty()
            status.empty()
            st.error("Can't reach Ollama. Start it with `ollama serve`, then try again.")
        except Exception as e:
            plate_slot.empty()
            status.empty()
            st.error(f"Identification failed: {e}")