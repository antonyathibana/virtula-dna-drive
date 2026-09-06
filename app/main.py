from __future__ import annotations

import io
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from .storage_manager import (
    analytics_summary,
    compare_correction_methods,
    create_record,
    delete_record,
    get_dna_preview,
    get_strand,
    list_records,
    recover_file,
    simulate_errors,
)

app = FastAPI(title="Virtual DNA Drive", version="2.0.0")


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE


@app.get("/api/files")
def api_files():
    return {"files": list_records()}


@app.get("/api/analytics")
def api_analytics():
    return analytics_summary()


@app.post("/api/store")
async def api_store(
    file: UploadFile = File(...),
    strand_size: int = Form(200),
    copies: int = Form(3),
):
    if strand_size < 20 or strand_size > 10000:
        raise HTTPException(400, "strand_size must be between 20 and 10000.")
    if copies < 1 or copies > 9:
        raise HTTPException(400, "copies must be between 1 and 9.")

    data = await file.read()

    # Keep demo storage manageable.
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Demo limit: files up to 5 MB.")

    return create_record(file.filename or "unnamed.bin", data, strand_size, copies)


@app.post("/api/simulate/{record_id}")
def api_simulate(
    record_id: str,
    error_rate: float = Form(0.01),
    insertion_rate: float = Form(0.0),
    deletion_rate: float = Form(0.0),
    dropout_rate: float = Form(0.0),
    seed: Optional[int] = Form(None),
):
    try:
        return simulate_errors(
            record_id,
            error_rate,
            seed=seed,
            insertion_rate=insertion_rate,
            deletion_rate=deletion_rate,
            dropout_rate=dropout_rate,
        )
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/preview/{record_id}")
def api_preview(record_id: str):
    try:
        return get_dna_preview(record_id)
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")


@app.get("/api/strand/{record_id}/{index}")
def api_strand(record_id: str, index: int):
    try:
        return get_strand(record_id, index)
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")
    except IndexError as exc:
        raise HTTPException(404, str(exc))


@app.get("/api/recover/{record_id}")
def api_recover(record_id: str):
    try:
        data, info = recover_file(record_id)
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")
    except ValueError as exc:
        raise HTTPException(422, f"Recovery failed: {exc}")

    headers = {
        "X-DNA-Verified": str(info["verified"]).lower(),
        "X-DNA-Recovered-SHA256": info["recovered_sha256"],
        "X-DNA-Unrecoverable-Strands": str(info["unrecoverable_strands"]),
    }
    return StreamingResponse(io.BytesIO(data), media_type="application/octet-stream", headers=headers)


@app.get("/api/verify/{record_id}")
def api_verify(record_id: str):
    try:
        _, info = recover_file(record_id)
        return info
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")
    except ValueError as exc:
        raise HTTPException(422, f"Recovery failed: {exc}")


@app.post("/api/compare/{record_id}")
def api_compare(record_id: str, bit_error_rate: float = Form(0.01), seed: Optional[int] = Form(None)):
    try:
        return compare_correction_methods(record_id, bit_error_rate, seed)
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.delete("/api/files/{record_id}")
def api_delete(record_id: str):
    try:
        delete_record(record_id)
        return {"deleted": True}
    except FileNotFoundError:
        raise HTTPException(404, "Record not found.")


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Virtual DNA Drive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<style>
:root{
  --ink:#06100c;
  --panel:#0d1a15;
  --panel-2:#0a1512;
  --line:#1e3327;
  --line-soft:#152720;
  --signal:#5eeba0;
  --signal-dim:#2e6b4d;
  --amber:#ffb454;
  --red:#ff8a80;
  --text:#ecfbf3;
  --muted:#7fa696;
  --muted-2:#5a8271;
  --base-a:#5eeba0;
  --base-c:#7ab8ff;
  --base-g:#ffcf6b;
  --base-t:#ff9d8a;
  --radius-sm:6px;
  --radius-md:10px;
  --mono:'JetBrains Mono', ui-monospace, monospace;
  --display:'Space Grotesk', sans-serif;
  --body:'Inter', ui-sans-serif, sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;
  font-family:var(--body);
  background:
    radial-gradient(ellipse 900px 500px at 85% -10%, rgba(94,235,160,.06), transparent 60%),
    var(--ink);
  color:var(--text);
  min-height:100vh;
}
@media (prefers-reduced-motion: reduce){ *{animation-duration:0.001ms !important; transition-duration:0.001ms !important;} }

/* ---------- shell ---------- */
.topbar{
  position:sticky;top:0;z-index:20;
  display:flex;align-items:center;gap:28px;
  padding:14px 28px;
  background:rgba(6,16,12,.86);
  backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line-soft);
}
.brand{display:flex;align-items:center;gap:10px;font-family:var(--display);font-weight:600;font-size:17px;letter-spacing:.2px;white-space:nowrap}
.brand .dna-mark{width:20px;height:20px;display:block}
.tabs{display:flex;gap:2px;flex:1;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{
  font-family:var(--body);font-size:13.5px;font-weight:500;color:var(--muted);
  background:none;border:0;padding:9px 14px;border-radius:999px;cursor:pointer;white-space:nowrap;
  transition:color .15s ease, background .15s ease;
}
.tab:hover{color:var(--text)}
.tab.active{color:var(--ink);background:var(--signal);font-weight:600}
.status-pill{
  font-family:var(--mono);font-size:11.5px;color:var(--muted);
  border:1px solid var(--line);padding:5px 10px;border-radius:999px;white-space:nowrap;
  display:flex;align-items:center;gap:6px;
}
.status-dot{width:6px;height:6px;border-radius:50%;background:var(--signal);box-shadow:0 0 8px var(--signal)}

.shell{max-width:1180px;margin:0 auto;padding:36px 28px 80px}
.view{display:none}
.view.active{display:block}

h1,h2,h3{font-family:var(--display);font-weight:600;margin:0}
h1{font-size:30px;line-height:1.2}
h2{font-size:19px}
h3{font-size:14.5px}
p{line-height:1.6;color:var(--muted)}
.eyebrow-free-lead{color:var(--muted);font-size:15px;max-width:640px;margin:10px 0 0}

.section{margin-top:44px}
.section:first-of-type{margin-top:0}

.panel{
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:var(--radius-md);
  padding:22px;
}
.panel-flat{
  background:var(--panel-2);
  border:1px solid var(--line-soft);
  border-radius:var(--radius-sm);
  padding:16px 18px;
}

.grid-2{display:grid;grid-template-columns:1.1fr 1fr;gap:20px}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
@media(max-width:880px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}}

/* ---------- stat cards ---------- */
.stat{border:1px solid var(--line);border-radius:var(--radius-sm);padding:16px;background:var(--panel)}
.stat .label{font-size:12px;color:var(--muted-2);margin-bottom:8px}
.stat .value{font-family:var(--mono);font-size:24px;font-weight:600}
.stat .value small{font-size:13px;color:var(--muted);font-weight:400;margin-left:4px}

/* ---------- forms ---------- */
label{display:block;color:var(--muted);font-size:12.5px;margin:14px 0 6px}
label:first-child{margin-top:0}
input[type=text],input[type=number],select{
  width:100%;border-radius:var(--radius-sm);border:1px solid var(--line);
  background:var(--panel-2);color:var(--text);padding:10px 12px;font-family:var(--body);font-size:14px;
}
input[type=text]:focus,input[type=number]:focus,select:focus,button:focus-visible{
  outline:2px solid var(--signal);outline-offset:1px;
}
input[type=file]{
  width:100%;padding:28px 14px;border-radius:var(--radius-sm);border:1.5px dashed var(--line);
  background:var(--panel-2);color:var(--muted);font-family:var(--body);font-size:13.5px;cursor:pointer;
}
input[type=range]{width:100%;accent-color:var(--signal)}
.range-row{display:flex;align-items:center;gap:10px}
.range-row output{font-family:var(--mono);font-size:12.5px;color:var(--signal);min-width:52px;text-align:right}

button{
  cursor:pointer;font-family:var(--body);font-weight:600;font-size:13.5px;
  border:0;border-radius:var(--radius-sm);padding:11px 16px;
}
.btn-primary{background:var(--signal);color:#06170f;width:100%;margin-top:16px}
.btn-primary:hover{background:#7bf2b5}
.btn-secondary{background:transparent;border:1px solid var(--line);color:var(--text)}
.btn-secondary:hover{border-color:var(--signal-dim)}
.btn-danger{background:transparent;border:1px solid #4a2828;color:var(--red)}
.btn-danger:hover{background:rgba(255,138,128,.08)}
.btn-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.btn-row button{flex:1;min-width:96px}

.row{display:flex;gap:14px}
.row>*{flex:1}

/* ---------- pipeline ---------- */
.pipeline{display:flex;flex-direction:column;gap:0;margin-top:18px}
.pipeline-step{
  display:flex;align-items:center;gap:14px;padding:12px 0;
  border-bottom:1px dashed var(--line-soft);opacity:.4;transition:opacity .3s ease;
}
.pipeline-step:last-child{border-bottom:0}
.pipeline-step.active{opacity:1}
.pipeline-step .num{
  font-family:var(--mono);font-size:12px;color:var(--muted-2);
  width:26px;height:26px;border-radius:50%;border:1px solid var(--line);
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
}
.pipeline-step.active .num{border-color:var(--signal);color:var(--signal)}
.pipeline-step .txt{font-size:13.5px}
.pipeline-step .txt .sub{color:var(--muted-2);font-size:12px}

/* ---------- files table ---------- */
.file-row{
  padding:16px 0;border-bottom:1px solid var(--line-soft);
  display:flex;flex-direction:column;gap:8px;
}
.file-row:last-child{border-bottom:0}
.file-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.file-name{font-weight:600;font-size:14.5px}
.badge{
  font-family:var(--mono);font-size:11px;padding:3px 8px;border-radius:999px;
  background:var(--panel-2);border:1px solid var(--line);color:var(--muted);
}
.file-meta{font-family:var(--mono);font-size:11.5px;color:var(--muted);line-height:1.8}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
.actions button{font-size:12px;padding:8px 12px}

/* ---------- sequence display ---------- */
.seq{
  font-family:var(--mono);font-size:13px;line-height:1.9;word-break:break-all;
  background:var(--panel-2);border:1px solid var(--line-soft);border-radius:var(--radius-sm);
  padding:14px;max-height:240px;overflow:auto;
}
.b-A{color:var(--base-a)}.b-C{color:var(--base-c)}.b-G{color:var(--base-g)}.b-T{color:var(--base-t)}
.b-diff{background:rgba(255,138,128,.22);border-radius:2px}
.legend{display:flex;gap:14px;margin-top:10px;font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.legend span{display:flex;align-items:center;gap:5px}
.legend i{width:9px;height:9px;border-radius:2px;display:inline-block}

/* ---------- empty state ---------- */
.empty{
  text-align:left;padding:34px 20px;color:var(--muted);border:1px dashed var(--line);
  border-radius:var(--radius-sm);font-size:13.5px;
}

/* ---------- toast / status ---------- */
#toast{
  position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(0);
  background:var(--panel);border:1px solid var(--line);color:var(--text);
  padding:11px 18px;border-radius:999px;font-size:13px;box-shadow:0 12px 40px rgba(0,0,0,.4);
  opacity:0;pointer-events:none;transition:opacity .2s ease, transform .2s ease;z-index:50;
  font-family:var(--body);
}
#toast.show{opacity:1;transform:translateX(-50%) translateY(-6px)}
#toast.err{border-color:#4a2828;color:var(--red)}
#toast.ok{border-color:var(--signal-dim);color:var(--signal)}

/* ---------- quality bars ---------- */
.quality-row{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--line-soft);font-size:13px}
.quality-row:last-child{border-bottom:0}
.quality-row .ok{color:var(--signal)}
.quality-row .bad{color:var(--amber)}

/* ---------- disclosure note ---------- */
.note{
  font-size:12.5px;color:var(--muted-2);border-left:2px solid var(--line);
  padding:2px 0 2px 12px;margin-top:14px;
}

/* ---------- helix hero mark ---------- */
.hero-helix{position:relative;height:120px;overflow:hidden;border-radius:var(--radius-md);border:1px solid var(--line);background:var(--panel)}
.hero-helix svg{width:100%;height:100%;display:block}
.strand-a{animation:drift 14s linear infinite}
.strand-b{animation:drift 14s linear infinite reverse}
@keyframes drift{from{stroke-dashoffset:0}to{stroke-dashoffset:-560}}

canvas{max-height:220px}

select{appearance:none;background-image:linear-gradient(45deg, transparent 50%, var(--muted) 50%), linear-gradient(135deg, var(--muted) 50%, transparent 50%);background-position:calc(100% - 18px) center, calc(100% - 13px) center;background-size:5px 5px, 5px 5px;background-repeat:no-repeat;}
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">
    <svg class="dna-mark" viewBox="0 0 24 24" fill="none"><path d="M6 3c0 6 12 6 12 12M18 21c0-6-12-6-12-12" stroke="#5eeba0" stroke-width="1.6" stroke-linecap="round"/><path d="M7 6h10M7 18h10" stroke="#5eeba0" stroke-width="1.2" opacity=".5"/></svg>
    Virtual DNA Drive
  </div>
  <div class="tabs" id="tabs">
    <button class="tab active" data-view="overview">Overview</button>
    <button class="tab" data-view="drive">DNA Drive</button>
    <button class="tab" data-view="encode">Encode</button>
    <button class="tab" data-view="strand">Strand Viewer</button>
    <button class="tab" data-view="lab">Error Lab</button>
    <button class="tab" data-view="compare">Compare</button>
    <button class="tab" data-view="about">How it works</button>
  </div>
  <div class="status-pill"><span class="status-dot"></span>Simulation mode</div>
</div>

<div class="shell">

  <!-- ================= OVERVIEW ================= -->
  <div class="view active" id="view-overview">
    <h1>Store information in the language of life.</h1>
    <p class="eyebrow-free-lead">A software simulation of DNA-based data storage — encode files into virtual A/C/G/T sequences, damage them with realistic errors, and recover them with measurable accuracy. Nothing here touches physical DNA.</p>

    <div class="hero-helix section" aria-hidden="true">
      <svg viewBox="0 0 600 120" preserveAspectRatio="none">
        <path class="strand-a" d="M0,60 C50,10 100,110 150,60 C200,10 250,110 300,60 C350,10 400,110 450,60 C500,10 550,110 600,60" stroke="#5eeba0" stroke-width="2" fill="none" stroke-dasharray="6 8" opacity="0.8"/>
        <path class="strand-b" d="M0,60 C50,110 100,10 150,60 C200,110 250,10 300,60 C350,110 400,10 450,60 C500,110 550,10 600,60" stroke="#7ab8ff" stroke-width="2" fill="none" stroke-dasharray="6 8" opacity="0.6"/>
      </svg>
    </div>

    <div class="section grid-4" id="overviewStats"></div>

    <div class="section grid-2">
      <div class="panel">
        <h2>DNA base composition</h2>
        <p style="font-size:12.5px;margin-top:4px">Aggregated across every base of every strand currently stored.</p>
        <canvas id="compositionChart" height="180"></canvas>
      </div>
      <div class="panel">
        <h2>Simulation accuracy</h2>
        <p style="font-size:12.5px;margin-top:4px">Actual recovery accuracy measured from comparison runs you've executed.</p>
        <canvas id="accuracyChart" height="180"></canvas>
        <div id="accuracyEmpty" class="note">Run a comparison in the Compare tab to populate this chart.</div>
      </div>
    </div>
  </div>

  <!-- ================= DNA DRIVE ================= -->
  <div class="view" id="view-drive">
    <div class="file-head" style="margin-bottom:6px">
      <h1 style="font-size:22px">Stored files</h1>
      <button class="btn-secondary" onclick="loadFiles()">Refresh</button>
    </div>
    <p>Every file below is encoded into virtual DNA, chunked into strands, and stored with redundant copies.</p>
    <div class="panel section" style="margin-top:16px">
      <div id="files"></div>
    </div>
  </div>

  <!-- ================= ENCODE ================= -->
  <div class="view" id="view-encode">
    <h1 style="font-size:22px">Encode a file</h1>
    <p>Upload any file to convert it into a virtual DNA sequence, split into redundant strands.</p>

    <div class="section grid-2">
      <div class="panel">
        <form id="uploadForm">
          <label>File</label>
          <input type="file" id="file" required>
          <div class="row">
            <div>
              <label>Strand size (bases)</label>
              <input type="number" id="strandSize" value="200" min="20" max="10000">
            </div>
            <div>
              <label>Redundant copies</label>
              <input type="number" id="copies" value="3" min="1" max="9">
            </div>
          </div>
          <button class="btn-primary">Encode &amp; store</button>
        </form>
      </div>

      <div class="panel">
        <h3 style="margin-bottom:4px">Encoding pipeline</h3>
        <div class="pipeline" id="pipeline">
          <div class="pipeline-step" data-step="0"><div class="num">1</div><div class="txt">File read<div class="sub">Raw bytes loaded from upload</div></div></div>
          <div class="pipeline-step" data-step="1"><div class="num">2</div><div class="txt">Binary conversion<div class="sub">Each byte → 8 bits</div></div></div>
          <div class="pipeline-step" data-step="2"><div class="num">3</div><div class="txt">DNA encoding<div class="sub">2 bits → one of A / C / G / T</div></div></div>
          <div class="pipeline-step" data-step="3"><div class="num">4</div><div class="txt">Strand generation<div class="sub">Sequence chunked into fixed-length strands</div></div></div>
          <div class="pipeline-step" data-step="4"><div class="num">5</div><div class="txt">Redundancy<div class="sub">Each strand duplicated N times</div></div></div>
          <div class="pipeline-step" data-step="5"><div class="num">6</div><div class="txt">Stored<div class="sub">Ready for error simulation &amp; recovery</div></div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ================= STRAND VIEWER ================= -->
  <div class="view" id="view-strand">
    <h1 style="font-size:22px">Strand viewer</h1>
    <p>Inspect an individual strand's redundant copies and its current recovered value.</p>

    <div class="panel section">
      <div class="row">
        <div>
          <label>File</label>
          <select id="strandFileSelect"></select>
        </div>
        <div>
          <label>Strand index</label>
          <input type="number" id="strandIndex" value="0" min="0">
        </div>
      </div>
      <div class="btn-row">
        <button class="btn-secondary" onclick="shiftStrand(-1)">← Previous</button>
        <button class="btn-secondary" onclick="loadStrand()">Load</button>
        <button class="btn-secondary" onclick="shiftStrand(1)">Next →</button>
      </div>

      <div id="strandDetail" class="section" style="display:none">
        <div class="grid-3">
          <div class="stat"><div class="label">Status</div><div class="value" id="strandStatus" style="font-size:16px">—</div></div>
          <div class="stat"><div class="label">GC content</div><div class="value" id="strandGC">—</div></div>
          <div class="stat"><div class="label">Longest run</div><div class="value" id="strandHomopolymer">—</div></div>
        </div>
        <h3 class="section" style="margin-top:20px">Recovered sequence</h3>
        <div class="seq" id="strandRecovered"></div>
        <h3 class="section">Redundant copies</h3>
        <div id="strandCopies"></div>
        <div class="legend">
          <span><i style="background:var(--base-a)"></i>A</span>
          <span><i style="background:var(--base-c)"></i>C</span>
          <span><i style="background:var(--base-g)"></i>G</span>
          <span><i style="background:var(--base-t)"></i>T</span>
          <span><i style="background:var(--red)"></i>disagrees with majority</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ================= ERROR LAB ================= -->
  <div class="view" id="view-lab">
    <h1 style="font-size:22px">Error simulation lab</h1>
    <p>Introduce realistic DNA-storage errors into a stored file, then recover and verify it.</p>

    <div class="section grid-2">
      <div class="panel">
        <label>File</label>
        <select id="labFileSelect"></select>

        <label>Substitution rate (per base)</label>
        <div class="range-row"><input type="range" id="subRate" min="0" max="0.2" step="0.001" value="0.01"><output id="subRateOut">0.010</output></div>

        <label>Insertion rate (per base)</label>
        <div class="range-row"><input type="range" id="insRate" min="0" max="0.1" step="0.001" value="0"><output id="insRateOut">0.000</output></div>

        <label>Deletion rate (per base)</label>
        <div class="range-row"><input type="range" id="delRate" min="0" max="0.1" step="0.001" value="0"><output id="delRateOut">0.000</output></div>

        <label>Strand dropout rate (per copy)</label>
        <div class="range-row"><input type="range" id="dropRate" min="0" max="0.2" step="0.001" value="0"><output id="dropRateOut">0.000</output></div>

        <div class="btn-row">
          <button class="btn-primary" style="margin-top:6px" onclick="runSimulation()">Run simulation</button>
        </div>
        <div class="btn-row">
          <button class="btn-secondary" onclick="verifyLab()">Verify</button>
          <button class="btn-secondary" onclick="recoverLab()">Recover file</button>
        </div>
        <div class="note">Substitutions can usually be corrected by majority voting across redundant copies. Insertions and deletions shift alignment and strand dropout removes whole copies — both are harder to correct and are reported honestly, including when a strand becomes unrecoverable.</div>
      </div>

      <div class="panel">
        <h3>Result</h3>
        <div id="labResult" class="empty">Run a simulation to see results here.</div>
      </div>
    </div>
  </div>

  <!-- ================= COMPARE ================= -->
  <div class="view" id="view-compare">
    <h1 style="font-size:22px">Compare correction methods</h1>
    <p>Runs two real, independently-implemented strategies against the same file and error rate: majority voting across redundant DNA copies, and Hamming(7,4) single-error-correction on the underlying bitstream. All numbers shown are measured from the actual run, not estimated.</p>

    <div class="panel section">
      <div class="row">
        <div>
          <label>File</label>
          <select id="compareFileSelect"></select>
        </div>
        <div>
          <label>Bit / base error rate</label>
          <input type="number" id="compareRate" value="0.01" min="0" max="0.5" step="0.001">
        </div>
        <div>
          <label>Seed (optional)</label>
          <input type="number" id="compareSeed" placeholder="random">
        </div>
      </div>
      <button class="btn-primary" onclick="runCompare()">Run comparison</button>

      <div id="compareResult" class="section" style="display:none">
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead>
            <tr style="text-align:left;color:var(--muted);font-size:12px">
              <th style="padding:8px 0;border-bottom:1px solid var(--line)">Method</th>
              <th style="padding:8px 0;border-bottom:1px solid var(--line)">Storage overhead</th>
              <th style="padding:8px 0;border-bottom:1px solid var(--line)">Bytes matching</th>
              <th style="padding:8px 0;border-bottom:1px solid var(--line)">Byte-exact</th>
            </tr>
          </thead>
          <tbody id="compareTableBody" style="font-family:var(--mono)"></tbody>
        </table>
        <div class="note" id="compareNote"></div>
      </div>
    </div>
  </div>

  <!-- ================= ABOUT / HOW IT WORKS ================= -->
  <div class="view" id="view-about">
    <h1 style="font-size:22px">How this simulation works</h1>
    <div class="section grid-2">
      <div class="panel">
        <h3>Encoding</h3>
        <p style="font-size:13.5px">Each byte is split into four 2-bit groups. Each 2-bit group maps to one base: <span class="seq" style="display:inline;padding:2px 6px">00→A 01→C 10→G 11→T</span>. This is a simulation convention — real DNA-storage research uses more sophisticated, constraint-aware codecs.</p>
        <h3 class="section">Redundancy &amp; recovery</h3>
        <p style="font-size:13.5px">Each strand is stored as several identical copies. If some copies pick up substitution errors, majority voting at each position usually recovers the correct base — as long as most copies still agree.</p>
      </div>
      <div class="panel">
        <h3>Error types simulated</h3>
        <p style="font-size:13.5px"><strong style="color:var(--text)">Substitution</strong> — a base is replaced with a different one. Correctable by majority vote.<br><br>
        <strong style="color:var(--text)">Insertion / deletion</strong> — a base is added or removed, shifting everything after it. This breaks position-by-position majority voting, which is why the tool reports affected strands as unrecoverable rather than silently guessing.<br><br>
        <strong style="color:var(--text)">Strand dropout</strong> — an entire copy is lost. Recovery falls back to the surviving copies; if all copies of a strand are lost, that strand cannot be recovered.</p>
        <div class="note">This project implements majority voting and Hamming(7,4) only. Reed-Solomon and other advanced codes are not implemented — the Compare tab will never show numbers for a method that wasn't actually run.</div>
      </div>
    </div>
    <div class="section panel">
      <h3>Important</h3>
      <p style="font-size:13.5px">This is a computer simulation of an idea from DNA-data-storage research. It does not create, synthesize, or sequence physical DNA, and no numbers on this page should be read as a physical or economic estimate of real molecular storage.</p>
    </div>
  </div>

</div>

<div id="toast"></div>

<script>
/* ---------------- shared state & helpers ---------------- */
let filesCache = [];
let compositionChart, accuracyChart;
const accuracyHistory = []; // {label, majority, hamming}

function toast(msg, kind=''){
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show ' + kind;
  clearTimeout(toast._t);
  toast._t = setTimeout(()=> el.className = '', 2600);
}

function escapeHtml(str){
  return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
function formatBytes(bytes){
  if(!bytes) return '0 B';
  const k=1024, u=['B','KB','MB','GB'];
  const i=Math.floor(Math.log(bytes)/Math.log(k));
  return (bytes/Math.pow(k,i)).toFixed(i?2:0)+' '+u[i];
}
function colorizeSeq(seq, diffSet){
  let out = '';
  for(let i=0;i<seq.length;i++){
    const c = seq[i];
    const cls = 'b-' + c + (diffSet && diffSet.has(i) ? ' b-diff' : '');
    out += `<span class="${cls}">${c}</span>`;
  }
  return out;
}

/* ---------------- tabs ---------------- */
document.getElementById('tabs').addEventListener('click', (e)=>{
  const btn = e.target.closest('.tab');
  if(!btn) return;
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.getElementById('view-' + btn.dataset.view).classList.add('active');
  if(btn.dataset.view === 'overview') renderOverview();
});

/* ---------------- data loading ---------------- */
async function loadFiles(){
  const r = await fetch('/api/files');
  const data = await r.json();
  filesCache = data.files;
  renderFileList();
  populateFileSelects();
  renderOverview();
}

function renderFileList(){
  const el = document.getElementById('files');
  if(!filesCache.length){
    el.innerHTML = '<div class="empty">No files stored yet. Head to the Encode tab to create one.</div>';
    return;
  }
  el.innerHTML = filesCache.map(f => `
    <div class="file-row">
      <div class="file-head">
        <div class="file-name">${escapeHtml(f.filename)}</div>
        <span class="badge">${f.strand_count} strands</span>
      </div>
      <div class="file-meta">
        ${formatBytes(f.original_size_bytes)} original · ${f.dna_bases.toLocaleString()} DNA bases ·
        ${f.copies_per_strand} copies · GC ${f.gc_content ?? '—'}% · SHA ${f.sha256.slice(0,12)}…
        ${f.last_simulation ? `· last damage ${( f.last_simulation.actual_error_rate*100).toFixed(2)}%` : ''}
      </div>
      <div class="actions">
        <button class="btn-secondary" onclick="previewDNA('${f.id}')">Preview DNA</button>
        <button class="btn-secondary" onclick="verify('${f.id}')">Verify</button>
        <button class="btn-secondary" onclick="recover('${f.id}','${encodeURIComponent(f.filename)}')">Recover</button>
        <button class="btn-danger" onclick="removeFile('${f.id}')">Delete</button>
      </div>
      <div id="preview-${f.id}"></div>
    </div>
  `).join('');
}

function populateFileSelects(){
  const opts = filesCache.map(f => `<option value="${f.id}">${escapeHtml(f.filename)} (${f.strand_count} strands)</option>`).join('');
  ['strandFileSelect','labFileSelect','compareFileSelect'].forEach(id=>{
    const el = document.getElementById(id);
    const prev = el.value;
    el.innerHTML = opts || '<option value="">No files stored</option>';
    if(prev) el.value = prev;
  });
}

async function previewDNA(id){
  const r = await fetch('/api/preview/' + id);
  const d = await r.json();
  const el = document.getElementById('preview-' + id);
  el.innerHTML = `<div class="seq section">${colorizeSeq(d.preview)}</div><div class="file-meta">Showing ${d.preview_length} / ${d.total_bases} bases</div>`;
}

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = document.getElementById('file').files[0];
  if(!file) return;
  const fd = new FormData();
  fd.append('file', file);
  fd.append('strand_size', document.getElementById('strandSize').value);
  fd.append('copies', document.getElementById('copies').value);

  const steps = document.querySelectorAll('.pipeline-step');
  steps.forEach(s=>s.classList.remove('active'));
  for(let i=0;i<4;i++){
    await new Promise(res=>setTimeout(res, 140));
    steps[i].classList.add('active');
  }

  const r = await fetch('/api/store', {method:'POST', body:fd});
  const body = await r.json();
  if(!r.ok){ toast(body.detail || 'Upload failed', 'err'); return; }

  steps[4].classList.add('active');
  await new Promise(res=>setTimeout(res, 120));
  steps[5].classList.add('active');

  toast(`Stored ${body.filename} as ${body.dna_bases.toLocaleString()} DNA bases`, 'ok');
  e.target.reset();
  document.getElementById('strandSize').value = 200;
  document.getElementById('copies').value = 3;
  await loadFiles();
});

async function verify(id){
  const r = await fetch('/api/verify/' + id);
  const d = await r.json();
  if(!r.ok){ toast(d.detail, 'err'); return; }
  toast(d.verified ? 'Recovery verified — SHA-256 matches original' : `Recovery failed — ${d.unrecoverable_strands} strand(s) unrecoverable`, d.verified ? 'ok' : 'err');
}

async function recover(id, encodedFilename){
  const r = await fetch('/api/recover/' + id);
  if(!r.ok){ const d = await r.json(); toast(d.detail || 'Recovery failed', 'err'); return; }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = decodeURIComponent(encodedFilename);
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
  toast(r.headers.get('X-DNA-Verified') === 'true' ? 'File recovered and verified' : 'File recovered, but hash verification failed', r.headers.get('X-DNA-Verified') === 'true' ? 'ok' : 'err');
}

async function removeFile(id){
  await fetch('/api/files/' + id, {method:'DELETE'});
  toast('Record deleted');
  await loadFiles();
}

/* ---------------- overview ---------------- */
async function renderOverview(){
  const r = await fetch('/api/analytics');
  const a = await r.json();
  const stats = document.getElementById('overviewStats');
  stats.innerHTML = `
    <div class="stat"><div class="label">Files stored</div><div class="value">${a.total_files}</div></div>
    <div class="stat"><div class="label">Total DNA bases</div><div class="value">${a.total_dna_bases.toLocaleString()}</div></div>
    <div class="stat"><div class="label">Total strands</div><div class="value">${a.total_strands.toLocaleString()}</div></div>
    <div class="stat"><div class="label">Avg GC content</div><div class="value">${a.average_gc_content ?? '—'}<small>${a.average_gc_content!=null?'%':''}</small></div></div>
  `;

  // composition chart: aggregate from filesCache
  const comp = {A:0,C:0,G:0,T:0};
  filesCache.forEach(f=>{
    if(f.composition){ for(const k in comp) comp[k] += (f.composition[k]||0); }
  });
  const total = Object.values(comp).reduce((s,v)=>s+v,0);
  const ctx = document.getElementById('compositionChart');
  if(compositionChart) compositionChart.destroy();
  if(total > 0){
    compositionChart = new Chart(ctx, {
      type:'bar',
      data:{labels:['A','C','G','T'], datasets:[{data:['A','C','G','T'].map(k=>comp[k]), backgroundColor:['#5eeba0','#7ab8ff','#ffcf6b','#ff9d8a'], borderRadius:4}]},
      options:{plugins:{legend:{display:false}}, scales:{x:{ticks:{color:'#7fa696',font:{family:'JetBrains Mono'}},grid:{display:false}}, y:{ticks:{color:'#7fa696'},grid:{color:'#152720'}}}}
    });
  }

  const accCtx = document.getElementById('accuracyChart');
  document.getElementById('accuracyEmpty').style.display = accuracyHistory.length ? 'none' : 'block';
  if(accuracyChart) accuracyChart.destroy();
  if(accuracyHistory.length){
    accuracyChart = new Chart(accCtx, {
      type:'line',
      data:{labels:accuracyHistory.map(h=>h.label), datasets:[
        {label:'Majority vote', data:accuracyHistory.map(h=>h.majority), borderColor:'#5eeba0', backgroundColor:'transparent', tension:.3},
        {label:'Hamming(7,4)', data:accuracyHistory.map(h=>h.hamming), borderColor:'#ffb454', backgroundColor:'transparent', tension:.3},
      ]},
      options:{plugins:{legend:{labels:{color:'#ecfbf3',font:{family:'Inter'}}}}, scales:{x:{ticks:{color:'#7fa696'},grid:{display:false}}, y:{ticks:{color:'#7fa696'},grid:{color:'#152720'},min:0,max:100}}}
    });
  }
}

/* ---------------- strand viewer ---------------- */
function shiftStrand(delta){
  const el = document.getElementById('strandIndex');
  el.value = Math.max(0, (parseInt(el.value)||0) + delta);
  loadStrand();
}
async function loadStrand(){
  const fileId = document.getElementById('strandFileSelect').value;
  const idx = document.getElementById('strandIndex').value;
  if(!fileId){ toast('No file selected', 'err'); return; }
  const r = await fetch(`/api/strand/${fileId}/${idx}`);
  const d = await r.json();
  if(!r.ok){ toast(d.detail || 'Could not load strand', 'err'); return; }

  document.getElementById('strandDetail').style.display = 'block';
  document.getElementById('strandStatus').textContent = d.status === 'valid' ? 'Valid' : 'Unrecoverable';
  document.getElementById('strandStatus').style.color = d.status === 'valid' ? 'var(--signal)' : 'var(--red)';
  document.getElementById('strandGC').textContent = d.gc_content!=null ? d.gc_content + '%' : '—';
  document.getElementById('strandHomopolymer').textContent = d.longest_homopolymer!=null ? d.longest_homopolymer + ' bases' : '—';
  document.getElementById('strandRecovered').innerHTML = d.recovered ? colorizeSeq(d.recovered) : '<span style="color:var(--red)">No majority available — every copy was lost</span>';

  const copiesEl = document.getElementById('strandCopies');
  copiesEl.innerHTML = d.copies.map((c,i)=>{
    if(c === '') return `<div class="seq section" style="border-color:#4a2828">Copy ${i+1}: <span style="color:var(--red)">dropped</span></div>`;
    const diff = new Set();
    if(d.recovered){ for(let p=0;p<Math.min(c.length,d.recovered.length);p++){ if(c[p]!==d.recovered[p]) diff.add(p); } }
    return `<div class="seq section">Copy ${i+1}: ${colorizeSeq(c, diff)}</div>`;
  }).join('');
}

/* ---------------- error lab ---------------- */
['subRate','insRate','delRate','dropRate'].forEach(id=>{
  document.getElementById(id).addEventListener('input', (e)=>{
    document.getElementById(id+'Out').textContent = parseFloat(e.target.value).toFixed(3);
  });
});

async function runSimulation(){
  const fileId = document.getElementById('labFileSelect').value;
  if(!fileId){ toast('No file selected', 'err'); return; }
  const fd = new FormData();
  fd.append('error_rate', document.getElementById('subRate').value);
  fd.append('insertion_rate', document.getElementById('insRate').value);
  fd.append('deletion_rate', document.getElementById('delRate').value);
  fd.append('dropout_rate', document.getElementById('dropRate').value);
  const r = await fetch('/api/simulate/' + fileId, {method:'POST', body:fd});
  const d = await r.json();
  if(!r.ok){ toast(d.detail, 'err'); return; }
  const s = d.last_simulation;
  document.getElementById('labResult').innerHTML = `
    <div class="quality-row"><span>Substitutions applied</span><span class="ok">${s.actual_substitutions.toLocaleString()} (${(s.actual_error_rate*100).toFixed(3)}%)</span></div>
    <div class="quality-row"><span>Insertions / deletions</span><span>${s.insertions_made} / ${s.deletions_made}</span></div>
    <div class="quality-row"><span>Copies dropped</span><span>${s.copies_dropped}</span></div>
  `;
  toast('Damage applied to stored copies', 'ok');
  await loadFiles();
}
async function verifyLab(){
  const fileId = document.getElementById('labFileSelect').value;
  if(!fileId) return;
  const r = await fetch('/api/verify/' + fileId);
  const d = await r.json();
  if(!r.ok){ toast(d.detail, 'err'); return; }
  document.getElementById('labResult').innerHTML += `<div class="quality-row"><span>Verification</span><span class="${d.verified?'ok':'bad'}">${d.verified ? 'SHA-256 match' : d.unrecoverable_strands + ' strand(s) lost'}</span></div>`;
}
async function recoverLab(){
  const fileId = document.getElementById('labFileSelect').value;
  const f = filesCache.find(x=>x.id===fileId);
  if(!fileId || !f) return;
  await recover(fileId, encodeURIComponent(f.filename));
}

/* ---------------- compare ---------------- */
async function runCompare(){
  const fileId = document.getElementById('compareFileSelect').value;
  if(!fileId){ toast('No file selected', 'err'); return; }
  const fd = new FormData();
  fd.append('bit_error_rate', document.getElementById('compareRate').value);
  const seed = document.getElementById('compareSeed').value;
  if(seed) fd.append('seed', seed);
  const r = await fetch('/api/compare/' + fileId, {method:'POST', body:fd});
  const d = await r.json();
  if(!r.ok){ toast(d.detail, 'err'); return; }

  const mv = d.majority_vote, hm = d.hamming74;
  document.getElementById('compareResult').style.display = 'block';
  document.getElementById('compareTableBody').innerHTML = `
    <tr><td style="padding:10px 0">Majority vote (${mv.copies_per_strand} copies)</td><td>${mv.overhead_multiplier}×</td><td>${mv.bytes_matching}/${mv.bytes_total}</td><td style="color:${mv.byte_accurate?'var(--signal)':'var(--red)'}">${mv.byte_accurate?'yes':'no'}</td></tr>
    <tr><td style="padding:10px 0">Hamming(7,4)</td><td>${hm.overhead_multiplier}×</td><td>${hm.bytes_matching}/${hm.bytes_total}</td><td style="color:${hm.byte_accurate?'var(--signal)':'var(--red)'}">${hm.byte_accurate?'yes':'no'}</td></tr>
  `;
  document.getElementById('compareNote').textContent = `Majority vote corrected via ${mv.actual_substitutions} measured base substitutions (${mv.unrecoverable_strands} strand(s) unrecoverable). Hamming corrected ${hm.blocks_corrected}/${hm.total_blocks} 7-bit blocks against ${hm.bits_flipped} real bit flips.`;

  accuracyHistory.push({
    label: `${(d.bit_error_rate*100).toFixed(1)}%`,
    majority: Math.round(mv.bytes_matching / mv.bytes_total * 100),
    hamming: Math.round(hm.bytes_matching / hm.bytes_total * 100),
  });
  if(accuracyHistory.length > 8) accuracyHistory.shift();
  toast('Comparison complete', 'ok');
}

/* ---------------- boot ---------------- */
loadFiles();
</script>
</body>
</html>
"""
