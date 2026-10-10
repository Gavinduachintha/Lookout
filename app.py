import base64
import io
import random
import urllib.parse

import ollama
import streamlit as st
from PIL import Image, ImageOps

from prompts import SYSTEM_PROMPT, build_user_prompt
from config.db import init_db, save_sighting, fetch_sightings, fetch_image, delete_sighting

MODEL = "gemma3:latest"
GITHUB_URL  = "https://github.com/Gavinduachintha/Lookout"
GITHUB_USER = "Gavinduachintha"

# Create table on first run (no-op if it already exists)
try:
    init_db()
except Exception as _db_init_err:
    st.error(f"Database connection failed: {_db_init_err}\n\nSet DB_HOST / DB_NAME / DB_USER / DB_PASSWORD env vars and restart.")

st.set_page_config(
    page_title="Trailside",
    page_icon="🍂",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def treeline(seed: int, base: int, hmin: int, hmax: int, wmin: int, wmax: int, color: str) -> str:
    rnd = random.Random(seed)
    d = f"M-40 300 L-40 {base}"
    x = -30.0
    while x < 1240:
        w = rnd.uniform(wmin, wmax)
        h = rnd.uniform(hmin, hmax)
        cx = x + w / 2
        pts = [
            (cx - w / 2, base), (cx - w / 4, base - h * 0.42),
            (cx - w / 8, base - h * 0.42), (cx, base - h),
            (cx + w / 8, base - h * 0.42), (cx + w / 4, base - h * 0.42),
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


def log_card(row: dict) -> str:
    """Render one sighting row as a themed HTML card (no image bytes needed)."""
    import re
    created = row.get("created_at")
    ts = f"{created.day} {created.strftime('%b %Y · %H:%M UTC')}" if created else "—"
    hint = row.get("user_hint", "").strip()
    hint_html = (
        f'<p class="lc-hint">"{hint[:90]}{"…" if len(hint) > 90 else ""}"</p>'
        if hint else ""
    )
    notes_plain = re.sub(r"[#*_`>\[\]()]", "", row.get("notes", ""))
    notes_plain = re.sub(r"\s+", " ", notes_plain).strip()
    snippet = notes_plain[:280] + ("…" if len(notes_plain) > 280 else "")
    return (
        f'<div class="lc">'
        f'<p class="lc-ts">{ts}</p>'
        f"{hint_html}"
        f'<p class="lc-notes">{snippet}</p>'
        f"</div>"
    )


def render_top_bar() -> bool:
    """
    Formal site header — wordmark + tagline on the left, GitHub link + nav CTA on the right.
    Returns True if the nav CTA was clicked.
    """
    on_logbook = st.session_state.view == "logbook"
    cta_label  = "← Home"           if on_logbook else "📖 LogBook"
    cta_key    = "top_back_home"    if on_logbook else "top_open_logbook"
    tagline    = "LogBook"          if on_logbook else "On-device nature field guide"

    # GitHub SVG octocat icon (inline, no external image dependency)
    gh_icon = (
        '<svg aria-hidden="true" height="18" width="18" viewBox="0 0 16 16" '
        'fill="currentColor" style="display:block">'
        '<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17'
        ".55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94"
        "-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87"
        " 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59"
        ".82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2"
        "-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12"
        ".51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0"
        " 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42"
        '-3.58-8-8-8z"/></svg>'
    )

    with st.container(key="top_bar"):
        left_col, gh_col, btn_col = st.columns([6, 2, 2])

        with left_col:
            st.markdown(
                '<header class="site-header">'
                '  <div class="sh-identity">'
                '    <span class="sh-logo" aria-hidden="true"></span>'
                '    <span class="sh-wordmark">Trailside</span>'
                '    <span class="sh-divider" aria-hidden="true"></span>'
                f'    <span class="sh-tagline">{tagline}</span>'
                "  </div>"
                "</header>",
                unsafe_allow_html=True,
            )

        with gh_col:
            st.markdown(
                f'<div class="sh-gh-wrap">'
                f'  <a class="sh-gh-link" href="{GITHUB_URL}" '
                f'     target="_blank" rel="noopener noreferrer" '
                f'     aria-label="{GITHUB_USER} on GitHub">'
                f"    {gh_icon}"
                f'    <span class="sh-gh-user">{GITHUB_USER}</span>'
                f"  </a>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with btn_col:
            clicked = st.button(cta_label, key=cta_key)

    return clicked


def scroll_to_top() -> None:
    """Inject a one-shot JS snippet that scrolls the Streamlit viewport to (0, 0)."""
    st.components.v1.html(
        "<script>window.parent.document.querySelector('.main').scrollTo({top:0,behavior:'instant'});</script>",
        height=0,
    )


@st.dialog("Sighting", width="large")
def show_sighting(row: dict) -> None:
    """Popup with the full photo and the complete field notes for one log."""
    from html import escape

    created = row.get("created_at")
    ts = f"{created.day} {created.strftime('%b %Y · %H:%M UTC')}" if created else "—"
    hint = (row.get("user_hint") or "").strip()

    img_bytes = fetch_image(row["id"])
    if img_bytes:
        st.image(img_bytes, use_container_width=True)

    st.markdown(f'<p class="lc-ts">{ts}</p>', unsafe_allow_html=True)
    if hint:
        st.markdown(f'<p class="lc-hint-full">"{escape(hint)}"</p>', unsafe_allow_html=True)
    st.markdown(row.get("notes", ""))


def render_logbook(*, fullscreen: bool = False) -> None:
    """LogBook sightings list with compact thumbnails."""
    scroll_to_top()
    section_cls = "logbook-section logbook-section--screen" if fullscreen else "logbook-section"
    st.markdown(
        f'<section class="{section_cls}">'
        '<h2 class="logbook-title">LogBook</h2>'
        '<p class="logbook-lede">Saved sightings from the trail — identify, then tap Save to add one here.</p>'
        "</section>",
        unsafe_allow_html=True,
    )
    try:
        rows = fetch_sightings(limit=100)
    except Exception as e:
        st.error(f"Could not load logbook: {e}")
        rows = []

    if not rows:
        st.markdown(
            '<div class="journal-empty logbook-empty">'
            '<div class="leaf-icon">📖</div>'
            "<h3>LogBook is empty</h3>"
            "<p>Identify something and press Save to LogBook.</p></div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<p class="log-header">{len(rows)} sighting{"s" if len(rows) != 1 else ""} · newest first</p>',
        unsafe_allow_html=True,
    )
    for row in rows:
        with st.container(key=f"logrow_{row['id']}"):
            col_thumb, col_body, col_del = st.columns([2, 9, 1], gap="small")
            with col_thumb:
                img_bytes = fetch_image(row["id"])
                if img_bytes:
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    img.thumbnail((340, 240))
                    thumb_buf = io.BytesIO()
                    img.save(thumb_buf, format="JPEG", quality=65)
                    thumb_b64 = base64.b64encode(thumb_buf.getvalue()).decode()
                    st.markdown(
                        f'<img class="log-thumb" '
                        f'src="data:image/jpeg;base64,{thumb_b64}" alt="sighting photo">',
                        unsafe_allow_html=True,
                    )
            with col_body:
                st.markdown(log_card(row), unsafe_allow_html=True)
                # Its click area is stretched over the whole row via CSS
                if st.button("View full log →", key=f"open_{row['id']}"):
                    show_sighting(row)
            with col_del:
                if st.button("✕", key=f"del_{row['id']}", help="Delete this sighting"):
                    try:
                        delete_sighting(row["id"])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

BACK  = treeline(11, 215, 38, 78, 26, 48, "#cbd8ab")
FRONT = treeline(5,  250, 46, 96, 34, 62, "#a3ba84")

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&family=Hanken+Grotesk:wght@400;500;600&display=swap');

:root{{
  --paper:#f6efe0; --card:#fffaf0; --ink:#2a2118; --bark:#5a4636;
  --forest:#1f3d2b; --moss:#4f7a4a; --pumpkin:#e8731a; --rust:#b9470a;
  --gold:#f2b134; --plum:#3b1f5e; --line:#dccfae;
  --serif:'Fraunces',Georgia,'Times New Roman',serif;
  --sans:'Hanken Grotesk',system-ui,-apple-system,'Segoe UI',sans-serif;
}}

[data-testid="stApp"]{{
  font-family:var(--sans); color:var(--bark);
  background:
    radial-gradient(90% 50% at 85% -5%,#ffe2a8 0%,transparent 60%),
    radial-gradient(80% 50% at 0% 0%,#ffd9b8 0%,transparent 55%),
    linear-gradient(180deg,#fbf0d9 0%,#f6efe0 55%,#e6ecd0 100%);
}}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],footer,#MainMenu{{display:none !important;}}

[data-testid="stMainBlockContainer"]{{
  max-width:1280px; padding:3rem 2.5rem 5rem; position:relative; z-index:1;
}}
[data-testid="stHorizontalBlock"]{{align-items:flex-start;}}
[data-testid="stColumn"]:first-child{{position:sticky; top:6rem;}}

@media (max-width:900px){{
  [data-testid="stMainBlockContainer"]{{padding:2rem 1.1rem 5rem;}}
  [data-testid="stHorizontalBlock"]{{flex-direction:column;}}
  [data-testid="stColumn"]{{width:100% !important;flex:1 1 100% !important;position:static !important;}}
}}

/* ── Sky ── */
[data-testid="stElementContainer"]:has(.sky){{height:0;margin:0;padding:0;}}
.sky{{position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden;}}
.sky *{{position:absolute;}}
.sun{{
  top:6vh;right:8vw;width:clamp(70px,9vw,120px);aspect-ratio:1;border-radius:50%;
  background:radial-gradient(circle at 40% 35%,#fff6d6 0%,#ffd27a 55%,#f7b040 100%);
  box-shadow:0 0 50px 14px rgba(255,200,100,.55),0 0 170px 70px rgba(255,190,110,.3);
  animation:bob 16s ease-in-out infinite alternate;
}}
@keyframes bob{{from{{transform:translateY(-6px);}}to{{transform:translateY(8px);}}}}
.cloud{{
  height:11vh;width:34vw;border-radius:50%;filter:blur(10px);
  background:radial-gradient(closest-side,rgba(255,255,255,.8),transparent);
  animation:cloud var(--cs) ease-in-out infinite alternate;
}}
.cloud.c1{{top:9vh;left:6vw;--cs:48s;}}
.cloud.c2{{top:22vh;left:44vw;width:28vw;opacity:.7;--cs:62s;}}
@keyframes cloud{{from{{transform:translateX(-5vw);}}to{{transform:translateX(9vw);}}}}
.hill{{left:-3%;width:106%;bottom:0;background-repeat:no-repeat;background-size:100% 100%;animation:hillsway var(--hs) ease-in-out infinite alternate;}}
.hill.back{{height:28vh;background-image:url("{BACK}");opacity:.9;--hs:52s;}}
.hill.front{{height:17vh;background-image:url("{FRONT}");--hs:40s;}}
@keyframes hillsway{{from{{transform:translateX(-1.2%);}}to{{transform:translateX(1.2%);}}}}
.mist{{
  left:-10%;right:-10%;bottom:0;height:26vh;filter:blur(16px);
  background:radial-gradient(60% 100% at 28% 100%,rgba(255,246,225,.7),transparent 70%),
             radial-gradient(50% 90% at 76% 100%,rgba(255,240,210,.55),transparent 70%);
  animation:mistdrift 28s ease-in-out infinite alternate;
}}
@keyframes mistdrift{{from{{transform:translateX(-5%);}}to{{transform:translateX(6%);}}}}
.leaves i{{
  top:0;left:0;width:var(--sz);height:var(--sz);opacity:0;
  background:var(--c);border-radius:0 100% 0 100%;
  box-shadow:0 2px 6px rgba(90,50,10,.18);
  animation:fall var(--d) linear infinite;
}}
.leaves i::after{{
  content:"";inset:0;
  background:linear-gradient(135deg,transparent 47%,rgba(60,25,5,.28) 49% 52%,transparent 54%);
}}
@keyframes fall{{
  0%{{transform:translate3d(0,-10vh,0) rotate(0deg);opacity:0;}}
  8%{{opacity:.9;}}
  50%{{transform:translate3d(calc(var(--dx)*.45),52vh,0) rotate(calc(var(--r)*.5));}}
  92%{{opacity:.9;}}
  100%{{transform:translate3d(var(--dx),112vh,0) rotate(var(--r));opacity:0;}}
}}

/* ── Hero ── */
.hero{{margin-bottom:1.6rem;}}
.hero .kicker{{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin:0 0 1rem;}}
.hero .badge{{
  background:var(--plum);color:#fff4e0;font-size:.74rem;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;padding:.32rem .8rem;border-radius:999px;
}}
.hero .eyebrow{{font-size:.92rem;color:var(--rust);font-weight:600;margin:0;letter-spacing:.02em;}}
.hero .title{{
  font-family:var(--serif);font-weight:600;font-size:clamp(3.2rem,7vw,6rem);
  line-height:.95;letter-spacing:-.03em;margin:0 0 1rem;padding:0;
  color:transparent;
  background:linear-gradient(100deg,var(--forest) 8%,var(--moss) 42%,var(--rust) 88%);
  background-size:200% 100%;
  -webkit-background-clip:text;background-clip:text;
  animation:sheen 12s ease-in-out infinite alternate;
}}
@keyframes sheen{{from{{background-position:0% 50%;}}to{{background-position:100% 50%;}}}}
.hero .lede{{max-width:44ch;font-size:1.12rem;line-height:1.55;color:var(--bark);margin:0;}}

/* ── Tabs ── */
[data-baseweb="tab-list"]{{gap:.25rem;border-bottom:1px solid var(--line);}}
button[data-baseweb="tab"]{{background:transparent;color:var(--bark);}}
button[data-baseweb="tab"] p{{color:inherit;font-weight:500;}}
button[data-baseweb="tab"][aria-selected="true"]{{color:var(--forest);}}
button[data-baseweb="tab"]:focus-visible{{outline:2px solid var(--moss);outline-offset:2px;}}
[data-baseweb="tab-highlight"]{{background:var(--pumpkin) !important;}}
[data-baseweb="tab-border"]{{background:transparent !important;}}

/* ── Inputs ── */
[data-testid="stWidgetLabel"] p{{color:var(--bark);}}
[data-testid="stCameraInput"]>div,
[data-testid="stFileUploaderDropzone"]{{
  background:rgba(255,250,235,.75);border:1px dashed #c9b88f;border-radius:14px;
}}
[data-testid="stFileUploaderDropzone"] *{{color:var(--bark);}}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stCameraInput"] button{{background:var(--forest);color:#fff4e0;border:none;}}
[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stCameraInput"] button *{{color:inherit;}}
[data-testid="stTextInput"] [data-baseweb="base-input"],
[data-testid="stTextInput"] [data-baseweb="input"]{{
  background:rgba(255,250,235,.85);border:1px solid #d8c9a8;border-radius:12px;
}}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within{{
  border-color:var(--pumpkin);box-shadow:0 0 0 3px rgba(232,115,26,.22);
}}
[data-testid="stTextInput"] input{{background:transparent;color:var(--ink);}}
[data-testid="stTextInput"] input::placeholder{{color:rgba(90,70,54,.62);}}

/* ── Buttons ── */
[data-testid="stButton"] button{{
  position:relative;overflow:hidden;
  width:100%;min-height:3.1rem;border-radius:999px;border:none;
  box-shadow:0 12px 28px -12px rgba(185,71,10,.65);
  transition:transform .15s ease,box-shadow .25s ease,background .2s ease;
}}
[data-testid="stButton"] button::after{{
  content:"";position:absolute;top:0;bottom:0;left:-60%;width:40%;
  background:linear-gradient(100deg,transparent,rgba(255,255,255,.38),transparent);
  transform:skewX(-20deg);animation:glint 6s ease-in-out infinite;
}}
[data-testid="stButton"] button p{{font-weight:600;font-size:1rem;position:relative;z-index:1;}}
[data-testid="stButton"] button:hover{{transform:translateY(-1px);}}
[data-testid="stButton"] button:focus-visible{{outline:3px solid var(--forest);outline-offset:3px;}}
@keyframes glint{{0%,60%{{left:-60%;}}100%{{left:130%;}}}}

/* Identify = rust/orange */
[data-testid="stButton"]:has(button p:contains("Identify")) button,
div[data-testid="stButton"]:nth-of-type(1) button{{background:var(--rust);}}
div[data-testid="stButton"]:nth-of-type(1) button p{{color:#fff8ea;}}
/* Save = forest green  */
div[data-testid="stButton"]:nth-of-type(2) button{{background:var(--forest);}}
div[data-testid="stButton"]:nth-of-type(2) button p{{color:#e8f5e2;}}

/* ── Plate ── */
.plate{{
  position:relative;margin:1.2rem auto 1rem;max-width:240px;
  padding:8px 8px 12px;background:#fffdf6;
  border-radius:4px;transform:rotate(-1.2deg);
  border:1px solid rgba(90,70,54,.12);
  box-shadow:0 22px 40px -22px rgba(90,50,10,.45);
}}
.plate::before{{
  content:"";position:absolute;top:-12px;left:50%;width:96px;height:26px;
  transform:translateX(-50%) rotate(2.5deg);
  background:rgba(242,177,52,.6);border:1px solid rgba(90,70,54,.08);
}}
.plate .frame{{position:relative;overflow:hidden;border-radius:2px;line-height:0;}}
.plate img{{display:block;width:100%;max-height:32vh;object-fit:cover;}}
.plate.scanning{{animation:glow 2.6s ease-in-out infinite;}}
.plate.scanning .frame::after{{
  content:"";position:absolute;left:0;right:0;top:-40%;height:40%;
  background:linear-gradient(180deg,rgba(232,115,26,0),rgba(232,115,26,.28) 80%,rgba(255,235,190,.95) 100%);
  animation:scan 2.4s cubic-bezier(.55,0,.45,1) infinite;
}}
@keyframes scan{{from{{top:-40%;}}to{{top:100%;}}}}
@keyframes glow{{
  0%,100%{{box-shadow:0 22px 40px -22px rgba(90,50,10,.45),0 0 0 0 rgba(232,115,26,0);}}
  50%{{box-shadow:0 22px 40px -22px rgba(90,50,10,.45),0 0 40px 6px rgba(232,115,26,.35);}}
}}
.status{{
  text-align:center;font-family:var(--serif);font-style:italic;font-size:1.15rem;
  color:var(--rust);margin:.2rem 0 1rem;animation:breathe 2s ease-in-out infinite;
}}
@keyframes breathe{{0%,100%{{opacity:.65;}}50%{{opacity:1;}}}}

/* ── Empty state ── */
.journal-empty{{
  min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;gap:.6rem;padding:2rem;
  border:1.5px dashed #c9b88f;border-radius:16px;
  background:rgba(255,250,235,.6);
}}
.journal-empty .leaf-icon{{font-size:2.6rem;animation:breathe 3s ease-in-out infinite;}}
.journal-empty h3{{font-family:var(--serif);font-weight:600;font-size:1.6rem;color:var(--forest);margin:0;padding:0;}}
.journal-empty p{{max-width:34ch;color:var(--bark);margin:0;line-height:1.55;}}

/* ── Field journal ── */
.st-key-notes{{
  position:relative;
  background:var(--card);border:1px solid #e3d5b5;border-radius:10px;
  padding:2.2rem 2.4rem 2.4rem 3.2rem;
  box-shadow:0 30px 56px -30px rgba(90,50,10,.5);
  animation:unfold .9s ease both;
}}
.st-key-notes::before{{
  content:"";position:absolute;left:1.35rem;top:1rem;bottom:1rem;
  border-left:2px dashed rgba(185,71,10,.28);
}}
@keyframes unfold{{from{{opacity:0;transform:translateY(14px);}}to{{opacity:1;transform:none;}}}}
.st-key-notes p,.st-key-notes li,.st-key-notes span,.st-key-notes strong,.st-key-notes em,
.st-key-notes td,.st-key-notes th,.st-key-notes blockquote{{color:var(--ink);font-size:1.02rem;line-height:1.65;}}
.st-key-notes .notes-title,.st-key-notes h1,.st-key-notes h2,.st-key-notes h3,
.st-key-notes h4,.st-key-notes h5,.st-key-notes h6{{font-family:var(--serif);color:var(--forest);letter-spacing:-.01em;}}
.st-key-notes .notes-title{{font-size:1.9rem;font-weight:600;margin:0 0 .6rem;padding:0;}}
.st-key-notes a{{color:#0b5a46;text-decoration:underline;}}
.st-key-notes code{{background:rgba(31,61,43,.1);color:var(--forest);padding:.1em .35em;border-radius:4px;}}
.st-key-notes blockquote{{border-left:3px solid var(--moss);margin:.8rem 0;padding-left:1rem;}}
.st-key-notes table{{border-collapse:collapse;}}
.st-key-notes th,.st-key-notes td{{border:1px solid rgba(31,61,43,.22);padding:.35rem .6rem;}}
.fine{{
  font-size:.88rem;line-height:1.5;color:var(--bark);margin:1.2rem 0 0;
  background:rgba(255,250,235,.85);border-radius:10px;padding:.7rem .95rem;
}}

/* ── Log cards ── */
.log-header{{
  font-size:.82rem;letter-spacing:.05em;text-transform:uppercase;
  color:var(--rust);opacity:.8;margin:0 0 .6rem;
}}
.lc{{
  background:var(--card);border:1px solid #e3d5b5;border-radius:12px;
  padding:1.1rem 1.3rem;margin-bottom:.9rem;
  box-shadow:0 12px 28px -18px rgba(90,50,10,.35);
  animation:unfold .45s ease both;
}}
.lc-ts{{
  font-size:.76rem;letter-spacing:.05em;text-transform:uppercase;
  color:var(--moss);margin:0 0 .3rem;opacity:.9;
}}
.lc-hint{{
  font-size:.85rem;color:var(--rust);margin:0 0 .45rem;font-style:italic;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}
.lc-notes{{
  font-size:.92rem;line-height:1.55;color:var(--ink);
  display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;
}}
.log-thumb{{
  display:block;width:100%;max-width:160px;max-height:120px;object-fit:cover;
  border-radius:6px;margin:0;
  border:1px solid rgba(90,70,54,.14);
  box-shadow:0 6px 16px -8px rgba(90,50,10,.4);
  transform:rotate(-.6deg);
}}
/* ── Clickable log rows ── */
[class*="st-key-logrow_"]{{position:relative;cursor:pointer;}}
[class*="st-key-logrow_"] .lc{{transition:border-color .15s ease,box-shadow .15s ease;}}
[class*="st-key-logrow_"]:hover .lc{{
  border-color:var(--pumpkin);box-shadow:0 16px 32px -18px rgba(185,71,10,.45);
}}
/* the "View" button becomes a transparent overlay covering the whole row */
[class*="st-key-open_"] button{{
  position:static;overflow:visible;width:auto;min-height:0;padding:0 0 .2rem;
  background:transparent !important;box-shadow:none;border-radius:0;
}}
[class*="st-key-open_"] button::after{{
  content:"";position:absolute;inset:0;width:auto;background:none;
  transform:none;animation:none;z-index:1;
}}
[class*="st-key-open_"] button p{{
  font-size:.82rem;font-weight:600;color:var(--rust) !important;
}}
[class*="st-key-open_"] button:hover{{transform:none;}}
/* keep the delete button clickable above the overlay */
[class*="st-key-del_"]{{position:relative;z-index:2;}}

/* ── Popup (st.dialog) ── */
[data-testid="stDialog"] [role="dialog"],
[data-baseweb="modal"] [role="dialog"],
div[role="dialog"]{{
  background:var(--card) !important;border:1px solid #e3d5b5;border-radius:14px;
  color-scheme:light;
}}
[data-testid="stDialog"] [role="dialog"] > div,
[data-testid="stDialog"] [data-testid="stDialogContent"],
[data-testid="stDialog"] [data-testid="stVerticalBlock"],
[data-testid="stDialog"] [data-testid="stElementContainer"]{{
  background:transparent !important;
}}
[data-testid="stDialog"] h2,
[data-testid="stDialog"] [role="dialog"] h2{{font-family:var(--serif);color:var(--forest) !important;}}
[data-testid="stDialog"] button[aria-label="Close"],
[data-testid="stDialog"] button[aria-label="Close"] *{{color:var(--bark) !important;}}
[data-testid="stDialog"] p,[data-testid="stDialog"] li,[data-testid="stDialog"] strong,
[data-testid="stDialog"] em,[data-testid="stDialog"] td,[data-testid="stDialog"] th{{
  color:var(--ink);line-height:1.65;
}}
[data-testid="stDialog"] h1,[data-testid="stDialog"] h3,[data-testid="stDialog"] h4{{
  font-family:var(--serif);color:var(--forest);
}}
[data-testid="stDialog"] img{{border-radius:8px;max-height:45vh;object-fit:contain;}}
.lc-hint-full{{font-style:italic;color:var(--rust) !important;margin:0 0 .6rem;}}

.logbook-section{{margin:2.5rem 0 1.2rem;padding-top:2rem;border-top:1px solid var(--line);}}
/* FIX: removed min-height:calc(100vh - 7rem) — it forced the title block to
   nearly a full viewport tall, pushing the first sighting far down the page. */
.logbook-section--screen{{
  margin:0;padding:0;border-top:none;
}}
.logbook-title{{
  font-family:var(--serif);font-weight:600;font-size:clamp(1.75rem,4vw,2.35rem);
  color:var(--forest);margin:0 0 .45rem;padding:0;letter-spacing:-.02em;
}}
.logbook-lede{{max-width:52ch;font-size:1rem;line-height:1.5;color:var(--bark);margin:0 0 .6rem;}}
.logbook-empty{{min-height:28vh !important;}}
.logbook-section--screen .logbook-empty{{min-height:55vh !important;}}
/* ── Site header (floating glass bar) ── */
.st-key-top_bar{{
  position:sticky;top:.75rem;z-index:50;
  margin:0 0 2rem !important;
  padding:.5rem .55rem .5rem 1.2rem !important;
  background:rgba(255,250,235,.78);
  -webkit-backdrop-filter:blur(14px) saturate(1.15);
  backdrop-filter:blur(14px) saturate(1.15);
  border:1px solid rgba(201,184,143,.7);
  border-radius:999px;
  box-shadow:0 16px 34px -22px rgba(90,50,10,.5),inset 0 1px 0 rgba(255,255,255,.7);
}}
/* keep one row at every width, content-sized right side */
.st-key-top_bar [data-testid="stHorizontalBlock"]{{
  flex-direction:row !important;flex-wrap:nowrap !important;
  align-items:center !important;gap:.6rem !important;
}}
.st-key-top_bar [data-testid="stColumn"]{{position:static !important;min-width:0;}}
.st-key-top_bar [data-testid="stColumn"]:first-child{{flex:1 1 auto !important;width:auto !important;}}
.st-key-top_bar [data-testid="stColumn"]:not(:first-child){{flex:0 0 auto !important;width:auto !important;}}

/* brand */
.site-header{{margin:0;padding:0;}}
.sh-identity{{display:flex;align-items:center;gap:.65rem;min-width:0;}}
.sh-logo{{
  position:relative;flex:0 0 auto;width:1.8rem;height:1.8rem;
  border-radius:0 100% 0 100%;transform:rotate(-8deg);
  background:linear-gradient(135deg,var(--gold),var(--pumpkin) 55%,var(--rust));
  box-shadow:0 6px 14px -6px rgba(185,71,10,.7);
}}
.sh-logo::after{{
  content:"";position:absolute;inset:0;border-radius:inherit;
  background:linear-gradient(135deg,transparent 47%,rgba(60,25,5,.35) 49% 52%,transparent 54%);
}}
.sh-wordmark{{
  font-family:var(--serif);font-weight:600;font-size:1.4rem;line-height:1;
  color:var(--forest);letter-spacing:-.025em;
}}
.sh-divider{{flex:0 0 auto;width:1px;height:1.1rem;background:var(--line);}}
.sh-tagline{{
  font-family:var(--serif);font-style:italic;font-size:.9rem;
  color:var(--bark);opacity:.8;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}

/* GitHub pill — same height and radius as the CTA */
.sh-gh-wrap{{display:flex;align-items:center;}}
.sh-gh-link{{
  display:inline-flex;align-items:center;gap:.45rem;box-sizing:border-box;
  height:2.5rem;padding:0 1rem;
  font-size:.9rem;font-weight:600;color:var(--ink);text-decoration:none;white-space:nowrap;
  border-radius:999px;border:1px solid rgba(42,33,24,.16);
  background:rgba(255,250,235,.9);
  transition:background .15s ease,border-color .15s ease,color .15s ease;
}}
.sh-gh-link:hover{{background:rgba(31,61,43,.08);border-color:rgba(31,61,43,.35);color:var(--forest);}}
.sh-gh-link:focus-visible{{outline:3px solid var(--forest);outline-offset:2px;}}
.sh-gh-link svg{{flex:0 0 auto;margin:0;}}

/* LogBook / Home CTA */
.st-key-top_open_logbook [data-testid="stButton"] button,
.st-key-top_back_home    [data-testid="stButton"] button{{
  width:auto;height:2.5rem;min-height:2.5rem;padding:0 1.15rem;border-radius:999px;
  background:var(--forest) !important;
  box-shadow:0 10px 22px -14px rgba(31,61,43,.75);
}}
.st-key-top_open_logbook [data-testid="stButton"] button:hover,
.st-key-top_back_home    [data-testid="stButton"] button:hover{{background:var(--moss) !important;}}
.st-key-top_open_logbook [data-testid="stButton"] button p,
.st-key-top_back_home    [data-testid="stButton"] button p{{
  color:#e8f5e2 !important;font-weight:600;font-size:.9rem;white-space:nowrap;
}}
.st-key-top_open_logbook [data-testid="stButton"] button::after,
.st-key-top_back_home    [data-testid="stButton"] button::after{{display:none;}}

@media (max-width:640px){{
  .st-key-top_bar{{top:.5rem;padding:.4rem .4rem .4rem .9rem !important;}}
  .sh-divider,.sh-tagline,.sh-gh-user{{display:none;}}
  .sh-wordmark{{font-size:1.2rem;}}
  .sh-gh-link{{width:2.5rem;padding:0;justify-content:center;}}
}}

/* ── Alerts ── */
[data-testid="stAlert"],[data-testid="stAlertContainer"]{{
  background:#fff3dc;border:1px solid rgba(232,115,26,.55);border-radius:12px;
}}
[data-testid="stAlert"] *,[data-testid="stAlertContainer"] *{{color:var(--ink);}}

@media (max-width:640px){{
  .sun{{right:6vw;}}
  .st-key-notes{{padding:1.6rem 1.3rem 1.8rem 2rem;}}
  .st-key-notes::before{{left:.8rem;}}
  .journal-empty{{min-height:30vh;}}
}}
@media (prefers-reduced-motion:reduce){{
  .sky *,.hero .title,.plate.scanning,.plate.scanning .frame::after,.status,
  .journal-empty .leaf-icon,[data-testid="stButton"] button::after,.st-key-notes,.lc{{
    animation:none !important;
  }}
  .leaves{{display:none;}}
}}
</style>
"""

# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

st.markdown(CSS, unsafe_allow_html=True)
st.markdown(sky(), unsafe_allow_html=True)

if "view" not in st.session_state:
    st.session_state.view = "home"
if "last_notes" not in st.session_state:
    st.session_state.last_notes = ""
if "last_jpeg" not in st.session_state:
    st.session_state.last_jpeg = None

if render_top_bar():
    st.session_state.view = "home" if st.session_state.view == "logbook" else "logbook"
    st.rerun()

# ── FULL-SCREEN LOGBOOK ───────────────────────────────────────────────────
if st.session_state.view == "logbook":
    render_logbook(fullscreen=True)

# ── HOME (identify + field notes) ─────────────────────────────────────────
else:
    left, right = st.columns([5, 7], gap="large")

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

        tab_cam, tab_up = st.tabs(["📷  Take a photo", "Upload"])
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
        save = st.button("Save to LogBook", type="primary")

        plate_slot = st.empty()
        status = st.empty()

    with right:
        stage = st.empty()
        stage.markdown(
            '<div class="journal-empty"><div class="leaf-icon">🍂</div>'
            "<h3>Your field journal is empty</h3>"
            "<p>Take or upload a photo and your field notes will appear here.</p></div>",
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Identify action
    # -----------------------------------------------------------------------

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

            st.session_state.last_jpeg = jpeg
            st.session_state.last_notes = ""

            plate_slot.markdown(plate(b64, scanning=True), unsafe_allow_html=True)
            status.markdown('<p class="status">Looking closely…</p>', unsafe_allow_html=True)

            try:
                stream = ollama.chat(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(user_text), "images": [jpeg]},
                    ],
                    stream=True,
                )
                first = next(stream, None)
                status.empty()
                stage.empty()

                collected: list[str] = []

                def tokens():
                    if first is not None:
                        tok = first["message"]["content"]
                        collected.append(tok)
                        yield tok
                    for chunk in stream:
                        tok = chunk["message"]["content"]
                        collected.append(tok)
                        yield tok

                with right:
                    with st.container(key="notes"):
                        st.markdown('<h2 class="notes-title">Field notes</h2>', unsafe_allow_html=True)
                        st.write_stream(tokens())
                    st.markdown(
                        '<p class="fine">A photo can fool a model. Check anything important with a local '
                        "guide, and don't taste or handle anything you can't name for certain.</p>",
                        unsafe_allow_html=True,
                    )

                st.session_state.last_notes = "".join(collected)
                plate_slot.markdown(plate(b64, scanning=False), unsafe_allow_html=True)

            except ollama.ResponseError as e:
                plate_slot.empty()
                status.empty()
                with right:
                    if e.status_code == 404:
                        st.error(f"Model `{MODEL}` not installed. Run `ollama pull {MODEL}`.")
                    else:
                        st.error(f"Ollama error: {e}")
            except ConnectionError:
                plate_slot.empty()
                status.empty()
                with right:
                    st.error("Can't reach Ollama. Start it with `ollama serve`.")
            except Exception as e:
                plate_slot.empty()
                status.empty()
                with right:
                    st.error(f"Identification failed: {e}")

    if save:
        jpeg = st.session_state.get("last_jpeg")
        notes = st.session_state.get("last_notes", "").strip()

        if not jpeg:
            st.toast("Nothing to save — identify something first.", icon="🍂")
        elif not notes:
            st.toast("Notes are still empty — wait for the identification to finish.", icon="⏳")
        else:
            try:
                file_name = getattr(uploaded_file, "name", None) or "photo.jpg"
                row_id = save_sighting(
                    image_bytes=jpeg,
                    notes=notes,
                    user_hint=user_text,
                    file_name=file_name,
                    mime_type="image/jpeg",
                )
                st.session_state.view = "logbook"
                st.toast(f"Saved to LogBook (#{row_id}) ✓", icon="📖")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save: {e}")