#!/usr/bin/env python3
"""qbo-ops demo: scene frames via headless Chrome -> PNG.

Each scene is an HTML file with CSS keyframe animations; we capture the
frame at a chosen animation time using Chrome's --virtual-time-budget.
Frames are 1920x1080 @2x scale for crispness, downscaled to 1920x1080.
"""
import subprocess, os, sys
from pathlib import Path
from PIL import Image

BASE = Path("/home/blackghost/.hermes/cache/scratch/qbo_demo")
OUT = BASE / "frames"
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080

# Navy gradient + gold, matching the brand; DM Sans variable font
CSS = """
@font-face { font-family:'DMSans'; src:url('dm-sans-latin.woff2') format('woff2'); font-weight:100 1000; }
* { margin:0; padding:0; box-sizing:border-box; }
html,body { width:1920px; height:1080px; overflow:hidden;
  font-family:'DMSans',sans-serif;
  background:linear-gradient(135deg,#0a1428 0%,#12234d 55%,#0a1428 100%);
  color:#f4f6fb; }
.gold { color:#f4c542; }
.dim { color:#8b97b8; }
"""

def render(name, html, ms=800):
    f = BASE / f"{name}.html"
    f.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{html}</style></head>
<body>{'</head><body>'.join([]) }</body></html>""") if False else None
    # actual write: caller passes full body; we wrap
    f.write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}
{html[0]}</style></head><body>{html[1]}</body></html>""")
    png2x = OUT / f"{name}_2x.png"
    subprocess.run(["google-chrome","--headless=new","--disable-gpu","--no-sandbox",
        "--hide-scrollbars","--force-device-scale-factor=2",
        f"--window-size={W},{H}",
        f"--virtual-time-budget={ms}",
        f"--screenshot={png2x}", f"file://{f}"], check=True,
        capture_output=True, timeout=60)
    img = Image.open(png2x).resize((W,H), Image.LANCZOS)
    img.save(OUT / f"{name}.png")
    png2x.unlink()
    print(f"rendered {name}")

SCENES = {}

# ---- Scene 1: cold open (0-6.5s) ----
SCENES["s1_cold"] = ("""
.s1 { display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:1080px; gap:28px; animation:fadein 1.2s ease-out; }
@keyframes fadein { from{opacity:0} to{opacity:1} }
.line { font-size:64px; font-weight:300; letter-spacing:0.5px; }
.line b { font-weight:700; }
.q { font-size:88px; font-weight:800; margin-top:40px;
  animation:rise 1.6s 2.2s ease-out both; }
@keyframes rise { from{opacity:0; transform:translateY(30px)} to{opacity:1; transform:none} }
.logo { position:absolute; bottom:70px; font-size:26px; letter-spacing:6px;
  color:#8b97b8; animation:fadein 1s 4.5s both; }
""", """
<div class="s1">
  <div class="line">You run a business.</div>
  <div class="line">Your books live in <b>QuickBooks</b>.</div>
  <div class="line">Your agent lives in <b class="gold">Hermes</b>.</div>
  <div class="q">What if they <span class="gold">talked?</span></div>
</div>
<div class="logo">QBO-OPS &nbsp;·&nbsp; A HERMES PLUGIN</div>
""", 6500)

# ---- Scene 2: install (7.2-17.8s) ----
SCENES["s2_install"] = ("""
.s2 { display:flex; height:1080px; padding-top:60px; }
.term { flex:1; margin:100px 90px 120px; background:#060b18; border:1px solid #24304f;
  border-radius:16px; padding:48px 56px; font-family:monospace; font-size:30px;
  line-height:1.9; box-shadow:0 30px 80px rgba(0,0,0,.5); }
.bar { height:8px; background:#24304f; border-radius:4px; margin:-24px 56px 30px; }
.bar i { display:block; height:100%; width:70%; background:#f4c542; border-radius:4px; }
.prompt { color:#5ec26a; }
.cmd { color:#fff; }
.out { color:#8b97b8; }
.ok { color:#5ec26a; }
.warn { color:#e0a83c; }
.h { position:absolute; top:90px; left:90px; font-size:44px; font-weight:700; }
""", """
<div class="h">Install. <span class="dim">One command.</span></div>
<div class="s2"><div class="term">
  <div><span class="prompt">$</span> <span class="cmd">hermes plugins install blackghostosint/qbo-ops</span></div>
  <div class="out">Cloning qbo-ops...</div>
  <div class="out">qbo-ops requires credentials:</div>
  <div class="out">&nbsp;&nbsp;QBO_OPS_CLIENT_ID <span class="dim">— Intuit app client ID</span></div>
  <div class="out">&nbsp;&nbsp;QBO_OPS_CLIENT_SECRET <span class="dim">— secret</span></div>
  <div class="warn">&nbsp;&nbsp;Skipped? <span class="dim">Set these later in Hermes secrets.</span></div>
  <div><span class="ok">✓ Plugin qbo-ops installed and enabled.</span></div>
  <div class="out">&nbsp;</div>
  <div><span class="prompt">$</span> <span class="cmd">ask: is my QuickBooks connection healthy?</span></div>
  <div class="ok">→ Mailbox Plus of Ohio, LLC. — connected ✓</div>
</div></div>
""", 10000)

# ---- Scene 3: October (18.5-33.6s) ----
SCENES["s3_pnl"] = ("""
.s3 { display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:1080px; gap:36px; }
.q { font-size:54px; font-weight:300; color:#c9d4f0; }
.q b { color:#fff; font-weight:700; }
.cards { display:flex; gap:48px; margin-top:24px; }
.card { background:rgba(255,255,255,.04); border:1px solid #24304f; border-radius:20px;
  padding:56px 72px; text-align:center; min-width:420px;
  animation:pop .8s var(--d) cubic-bezier(.2,1.4,.4,1) both; }
@keyframes pop { from{opacity:0; transform:scale(.85)} to{opacity:1; transform:scale(1)} }
.card .label { font-size:24px; letter-spacing:3px; color:#8b97b8; text-transform:uppercase; }
.card .num { font-size:84px; font-weight:800; margin-top:12px; }
.card.gold .num { color:#f4c542; }
.src { margin-top:48px; font-family:monospace; font-size:24px; color:#5ec26a;
  animation:fadein .8s 5s both; }
""", """
<div class="s3">
  <div class="q">"<b>How did October look?</b>"</div>
  <div class="cards">
    <div class="card" style="--d:.6s"><div class="label">Income</div><div class="num">$14,256.69</div></div>
    <div class="card" style="--d:1.2s"><div class="label">Expenses</div><div class="num">$9,770.01</div></div>
    <div class="card gold" style="--d:1.8s"><div class="label">Net</div><div class="num">$4,486.68</div></div>
  </div>
  <div class="src">→ qbo_pnl · live QuickBooks data · 0.9s</div>
</div>
""", 14000)

# ---- Scene 4: vendor table (34.3-45.7s) ----
SCENES["s4_vendors"] = ("""
.s4 { display:flex; height:1080px; align-items:center; }
.left { width:760px; padding:0 90px; }
.left h2 { font-size:56px; font-weight:800; line-height:1.25; }
.left p { font-size:30px; color:#8b97b8; margin-top:28px; line-height:1.5; }
.big { font-size:120px; font-weight:800; color:#f4c542; margin-top:40px; }
.big small { font-size:30px; color:#8b97b8; font-weight:400; display:block; letter-spacing:2px; }
.tbl { flex:1; margin-right:90px; font-family:monospace; font-size:30px; }
.row { display:flex; justify-content:space-between; padding:16px 28px;
  border-bottom:1px solid #1a2647; animation:slidein .5s var(--d) ease-out both; }
@keyframes slidein { from{opacity:0; transform:translateX(40px)} to{opacity:1; transform:none} }
.row .v { color:#c9d4f0; } .row .a { color:#fff; font-weight:700; }
.row:nth-child(1) .a { color:#f4c542; }
""", """
<div class="s4">
  <div class="left">
    <h2>"Where did the money go?"</h2>
    <p>Any transaction-level question. The agent writes the query, the tool guards it — read-only, always.</p>
    <div class="big">88<small>TRANSACTIONS · OCTOBER · LIVE</small></div>
  </div>
  <div class="tbl">
    <div class="row" style="--d:.3s"><span class="v">Wire transfer fee</span><span class="a">$5,500.00</span></div>
    <div class="row" style="--d:.6s"><span class="v">Gristmill Village LLC</span><span class="a">$3,168.00</span></div>
    <div class="row" style="--d:.9s"><span class="v">FedEx</span><span class="a">$2,204.97</span></div>
    <div class="row" style="--d:1.2s"><span class="v">Huntington National</span><span class="a">$1,528.22</span></div>
    <div class="row" style="--d:1.5s"><span class="v">UPS</span><span class="a">$800.87</span></div>
    <div class="row" style="--d:1.8s"><span class="v">Stax Payments</span><span class="a">$326.95</span></div>
    <div class="row" style="--d:2.1s"><span class="v">Stamps.com</span><span class="a">$322.51</span></div>
  </div>
</div>
""", 11000)

# ---- Scene 5: trust (46.4-56.0s) ----
SCENES["s5_trust"] = ("""
.s5 { display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:1080px; gap:52px; }
.h { font-size:72px; font-weight:800; }
.pills { display:flex; gap:40px; }
.pill { border:1px solid #24304f; border-radius:999px; padding:26px 56px;
  font-size:32px; color:#c9d4f0; animation:pop .7s var(--d) cubic-bezier(.2,1.4,.4,1) both; }
@keyframes pop { from{opacity:0; transform:scale(.8)} to{opacity:1; transform:scale(1)} }
.pill b { color:#fff; }
.lock { margin-top:20px; display:flex; align-items:center; gap:20px;
  font-size:36px; color:#8b97b8; animation:fadein 1s 3s both; }
.sw { width:84px; height:44px; border-radius:22px; background:#24304f; position:relative; }
.sw i { position:absolute; left:6px; top:6px; width:32px; height:32px; border-radius:50%; background:#8b97b8; }
.sw.on { background:#f4c542; } .sw.on i { left:auto; right:6px; background:#0a1428; }
""", """
<div class="s5">
  <div class="h">Read-only. <span class="gold">By design.</span></div>
  <div class="pills">
    <div class="pill" style="--d:.4s"><b>Your</b> credentials</div>
    <div class="pill" style="--d:.9s"><b>Your</b> machine</div>
    <div class="pill" style="--d:1.4s"><b>Your</b> decision</div>
  </div>
  <div class="lock"><div class="sw"><i></i></div>&nbsp; writes stay off until you flip the switch</div>
</div>
""", 9500)

# ---- Scene 6: end card (56.7-63.6s) ----
SCENES["s6_end"] = ("""
.s6 { display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:1080px; gap:36px; }
.logo { font-size:120px; font-weight:800; letter-spacing:2px; }
.logo span { color:#f4c542; }
.tag { font-size:40px; font-weight:300; color:#c9d4f0; }
.url { margin-top:56px; font-family:monospace; font-size:34px; color:#8b97b8;
  border:1px solid #24304f; border-radius:12px; padding:20px 44px;
  animation:fadein 1s 1.2s both; }
@keyframes fadein { from{opacity:0} to{opacity:1} }
""", """
<div class="s6">
  <div class="logo">qbo<span>-ops</span></div>
  <div class="tag">Reconciliation tradecraft. Built in.</div>
  <div class="url">github.com/blackghostosint/qbo-ops</div>
</div>
""", 7000)

if __name__ == "__main__":
    # copy font next to scenes
    import shutil
    src = Path("/home/blackghost/.config/google-chrome/Default/Extensions/kcbaglhfgbkjdnpeokaamjjkddempipm/5.1.0_1/shared/fonts/dm-sans-latin.woff2")
    if src.exists():
        shutil.copy(src, BASE / "dm-sans-latin.woff2")
    for name, (style, body, ms) in SCENES.items():
        render(name, (style, body), ms)
