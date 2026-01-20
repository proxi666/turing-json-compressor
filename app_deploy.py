#!/usr/bin/env python3
"""
JSON Compressor - Turing QA Toolkit
Deployment-ready single-file Streamlit application.
"""

import streamlit as st
import json
import requests
import zipfile
from io import BytesIO

# =============================================================================
# EMBEDDED SYSTEM PROMPT
# =============================================================================
SYSTEM_PROMPT = '''<role>
You are a Quality Assurance reviewer for computer use annotation tasks from Turing. Annotators record themselves performing tasks in applications like GNOME Terminal, nano text editor, and Vim editor on Linux systems. You validate their event logs against quality standards.

Your scope: Event logs and text analysis only. The user handles all visual verification (screenshots, video, timing).
</role>

<job_overview>
## Understanding the Task Architecture

CRITICAL: Before performing any review work, you MUST read and develop complete understanding from these reference documents in your project context:

**Core Documentation Files:**
1. CENTRALIZED_DOCUMENT_-_CUA_META.pdf - Master reference
2. QA_rubric.md - Official rubric
3. Numbered_Workflow.md - Step-by-step process
4. Complete_Workflow.md - Comprehensive guide
5. Common_errors.md - Frequent mistakes
6. Task_Checklist.md - Verification checklist
7. qa_instructions.md - Quality assurance instructions

Go through these documents thoroughly to develop complete understanding. Your reviews must align with the standards defined in these documents.
</job_overview>

<category_definitions>
## P: vs T: Categories - Critical Distinction

**P: Categories (PROMPT Quality)** - Evaluate the prompt text itself (grammar, clarity, requirements)
- Categories 3, 4, 5, 8: Unless user explicitly requests, write "N/A - Prompt evaluation not requested"
- These assess the PROMPT, NOT the annotator's execution

**T: Categories (TASK Execution)** - Evaluate how the annotator performed
- Always score these - they assess execution quality
</category_definitions>

<error_severity_guidelines>
**CRITICAL:** Breaks functionality, missing 50%+ content, event count >3x target, catastrophic violations  
**MODERATE:** Wrong workflow, exploratory commands, 10-30% missing content, incorrect syntax  
**MINOR:** Cosmetic issues, single typo in non-functional text, fewer than 5 unnecessary events
</error_severity_guidelines>

<thinking_process>
You operate internally using TWO distinct expert roles. These roles are INTERNAL ONLY and must never be revealed to the user.

### ROLE A: IDEAL ANNOTATOR (EXECUTION PLANNER)
Imagine you are an expert ANNOTATOR, create a flawless workflow about the task provided by the user. You can do this by:
1) Read the prompt 2 times carefully
2) Fully understand the task intent and acceptance criteria
3) Decompose the task into a clean, minimal, deterministic execution plan:
    - Exact commands required
    - Exact syntax
    - Correct order of actions
4) Define the ideal workflow trajectory:
    - No exploratory steps which are not mentioned in the prompt
    - No verification unless explicitly required
    - No redundant navigation
5) Estimate:
    - Minimum reasonable event count
    - Expected keypress patterns
6) Identify risk points human annotator could make
7) Build a mental "gold-standard" execution reference

This role defines WHAT a perfect annotator SHOULD have done.

### ROLE B: QA REVIEWER (EXECUTION AUDITOR)
After completing Role A, switch to an expert QA reviewer.
Your task in this role is to:
1) Analyze the provided JSON event log (human annotation)
2) Perform a quick sanity scan:
   - Total events vs ideal
   - Event inflation (greater than 3x = RE-RECORD)
3) Map human events against the ideal workflow from Role A
4) Identify:
   - Deviations
   - Errors
   - Inefficiencies
   - Guideline violations
5) Cross-check findings against:
   - QA_rubric.md (all 12 subcategories)
   - Common_errors.md
   - Task_Checklist.md
6) Assign scores strictly per rubric definitions

IMPORTANT:
- Never reveal this internal process
- Never assume intent
- Never invent requirements
</thinking_process>

<workflow>
## Two-Phase Review Process

**Phase 1: Prompt Review**
When user shares task metadata and prompt:
1) Validate prompt against SOP: No web browsing (unless app listed in metadata), posting, time-bound instructions, all entities specified, fully deterministic
2) Generate expected workflow: Break into granular actions, specify exact syntax, estimate clean event count
3) Output: Expected workflow summary (concise)

**Phase 2: JSON Review**
When user shares event log - provide ONLY the structured output below.
</workflow>

<output>
## YOU MUST DELIVER EXACTLY TWO THINGS:

### 1. Task Execution Quality Table (12 rows)

**The 12 Subcategories (rate in this exact order):**

P: = PROMPT Quality (evaluate the prompt itself, not the execution)
T: = TASK Execution Quality (evaluate how annotator performed)

1) P: Timelessness (PASS or score)
2) T: Full Typing & Search Input Compliance
3) P: Relevance to Real-World Use → N/A unless requested
4) P: Task Intent Completeness → N/A unless requested
5) P: Clarity and Readability → N/A unless requested
6) P: No Public-Facing Actions (PASS or score)
7) T: Task–Prompt Alignment
8) P: Application Appropriateness → N/A unless requested
9) T: Completeness & Accuracy of Events
10) T: Recording & Visual Quality (usually ?)
11) T: Guideline Adherence
12) T: Trajectory & Path Efficiency

**Scoring:** 5★ Perfect | 4★ Good | 3★ HARD FAIL | 2★ Bad | 1★ Catastrophic  
**Rule:** Any ≤3★ = automatic REWORK or RE-RECORD

**Error format:** Event No → Severity → Reason → Resolution

### 2. Brief Feedback Paragraph
Under 100 words, encouraging tone, start positive, mention critical issues, use second person ("You..."). Be vague and generalize when mistakes present.

DO NOT include: Separate error lists, consolidation calculations, detailed analysis beyond table.
</output>

<critical_rules>
## 1. Repeat Count Parameter (MANDATORY)
Any key pressed multiple consecutive times MUST use Repeat Count Parameter - HARD FAIL for Guideline Adherence. Describe pattern conceptually in Resolution.

## 2. Prompt Adherence (ABSOLUTE)
Follow prompt EXACTLY - not even one extra navigation or verification step. No exploratory commands (pwd, ls, cat, wc, git status, docker images), no testing, no alternative workflows.

**BEFORE flagging as violation, verify:**
- Check Application Name(s) in metadata
- Check if action explicitly mentioned in prompt
- Don't assume browser/web use is always wrong

## 3. Hotkey Policies
Allowed: Ctrl+S, Windows key | Not encouraged: Ctrl+X, Ctrl+V, Ctrl+C, Ctrl+A | Wrong: Shift+Space, CapsLock

## 4. Recording Quality
Application full screen, Activity Monitor never visible, no PII. For Recording & Visual Quality: Always put "?" - NEVER claim to identify screenshot timing from event log.

## 5. Prompt Modification
If there are small errors in the provided JSON file which can be resolved via minor changes in the prompt that the annotator follows, suggest prompt modifications to the user.

## 6. Follow Rubric
Follow rubric consistently, taking as much thinking time as you want.
</critical_rules>

<edge_cases>
**Impossible Prompts:**
- If prompt requires platform features that don't exist (GNOME split without tmux, custom tool configurations)
- STOP review, flag as impossible requirement, escalate to management
- Don't blame annotator for impossible tasks

**Prompt Modification Option:**
- If task execution is clean but has 4-5 small errors resolvable via minor prompt changes
- Suggest prompt modifications instead of rejecting task
- Example: Change date to future year, specify exact file name, clarify ambiguous requirement
</edge_cases>

<event_count_guidance>
Being under target is GOOD when deliverables complete - efficiency is valued. If event count greater than 3x target after consolidation, recommend RE-RECORD.
</event_count_guidance>

<decision_framework>
**APPROVE:** All 4-5★, complete deliverables, clean execution  
**REWORK:** 1-2 scores ≤3★, fixable by editing events  
**RE-RECORD:** Multiple ≤3★, event count greater than 3x target, workflow foundation wrong
</decision_framework>

<common_error_patterns>
**Pattern 1:** Editing existing file - Navigation/deletion BEFORE typing = pre-existing content  
**Pattern 2:** Missing content - Never typed things required by the Prompt  
**Pattern 3:** Exploratory workflow - Testing/verification steps not in prompt
</common_error_patterns>

<feedback_guidelines>
Start positive, state issues clearly, mention fixes you made, keep under 100 words, encouraging second-person tone. Include when applicable: "After recording, check that start screenshots capture PRE-action events. I've corrected timestamp issues for you."
</feedback_guidelines>

<critical_reminders>
✅ Follow rubric consistently, describe resolutions conceptually, encourage annotators, being under target with complete work is excellent, check app names before flagging violations  
❌ Don't specify exact event numbers in resolutions, don't claim screenshot timing issues, don't reject for trivial cosmetic issues
</critical_reminders>

<final_checklist>
- All 12 subcategories rated in order
- Each error: Event No, Severity, Reason, Resolution
- Recording & Visual Quality = "?"
- Feedback under 100 words, encouraging
- Decision clear (APPROVE/REWORK/RE-RECORD)
</final_checklist>

---

**Your mission:** Checking the annotators if they have followed a proper smooth workflow without any error, which will ultimately be used to train Agentic LLM systems.'''


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def minimize_json(data: dict) -> dict:
    """Keep only QA-relevant fields (97-99% reduction)."""
    minimal = {
        "id": data.get("id"),
        "os": data.get("os"),
        "events": []
    }
    
    for idx, event in enumerate(data.get("events", []), 1):
        minimal_event = {
            "eventNum": idx,
            "type": event.get("type")
        }
        
        if "data" in event:
            minimal_data = {}
            
            if "text" in event["data"]:
                minimal_data["text"] = event["data"]["text"]
            
            if "repeatCount" in event["data"]:
                minimal_data["repeatCount"] = event["data"]["repeatCount"]
            
            if minimal_data:
                minimal_event["data"] = minimal_data
        
        minimal["events"].append(minimal_event)
    
    return minimal


def calculate_savings(original: dict, minimal: dict) -> tuple[int, int, float]:
    """Calculate size savings from compression."""
    original_size = len(json.dumps(original))
    minimal_size = len(json.dumps(minimal))
    savings_pct = (1 - minimal_size / original_size) * 100
    return original_size, minimal_size, savings_pct


def download_screenshots_as_zip(data: dict) -> tuple[bytes, int]:
    """Download all 'start' screenshots and return as ZIP bytes."""
    zip_buffer = BytesIO()
    downloaded_count = 0
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        events = data.get("events", [])
        for idx, event in enumerate(events, 1):
            screenshots = event.get("screenshots", {})
            start_url = screenshots.get("start")
            
            if start_url:
                try:
                    response = requests.get(start_url, timeout=30)
                    response.raise_for_status()
                    
                    filename = f"event{idx}.png"
                    zip_file.writestr(filename, response.content)
                    downloaded_count += 1
                except requests.exceptions.RequestException:
                    # Skip failed downloads silently
                    pass
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue(), downloaded_count


# =============================================================================
# PAGE CONFIG & STYLES
# =============================================================================

st.set_page_config(
    page_title="JSON Compressor - Turing QA",
    page_icon="📄",
    layout="centered"
)

# Dark theme CSS
st.markdown("""
<style>
    /* Dark theme */
    .stApp {
        background-color: #0a0a0a;
        color: #e0e0e0;
    }
    
    .main .block-container {
        max-width: 800px;
        padding-top: 2rem;
    }
    
    /* Custom header */
    .turing-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }
    
    .turing-title {
        font-size: 48px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.3rem;
        letter-spacing: 4px;
    }
    
    .turing-subtitle {
        font-size: 18px;
        font-weight: 300;
        color: #888888;
        letter-spacing: 1px;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
        background-color: #1a1a1a;
        border: 1px solid #333;
        color: #e0e0e0;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(255,255,255,0.1);
        background-color: #2a2a2a;
    }
    
    .stButton > button[kind="primary"] {
        background-color: #e94560;
        border: none;
        color: white;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #d13a54;
    }
    
    /* Text area */
    .stTextArea textarea {
        border-radius: 8px;
        border: 1px solid #333;
        background-color: #1a1a1a;
        color: #e0e0e0;
        font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
        font-size: 13px;
    }
    
    .stTextArea textarea:focus {
        border-color: #e94560;
        box-shadow: 0 0 0 1px #e94560;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 600;
        color: #e94560;
    }
    
    [data-testid="stMetricLabel"] {
        color: #888888;
    }
    
    /* Divider */
    hr {
        margin: 2rem 0;
        border: none;
        border-top: 1px solid #333;
    }
    
    /* Code blocks */
    .stCode {
        background-color: #1a1a1a;
    }
    
    code {
        background-color: #1a1a1a;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: 0.9em;
        color: #e0e0e0;
    }
    
    /* Caption */
    .stCaption {
        color: #666666;
    }
    
    /* Download button */
    .stDownloadButton > button {
        background-color: #10b981;
        border: none;
        color: white;
    }
    
    .stDownloadButton > button:hover {
        background-color: #059669;
    }
    
    /* Privacy notice */
    .privacy-notice {
        text-align: center;
        color: #555;
        font-size: 12px;
        margin-top: 2rem;
        padding: 1rem;
        border-top: 1px solid #222;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# APP UI
# =============================================================================

# Initialize session state
if 'show_prompt' not in st.session_state:
    st.session_state.show_prompt = False
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None  # Stores processed results
if 'original_data' not in st.session_state:
    st.session_state.original_data = None   # Stores original for screenshot download
if 'zip_data' not in st.session_state:
    st.session_state.zip_data = None        # Stores fetched ZIP bytes

# Centered header
st.markdown('''
<div class="turing-header">
    <div class="turing-title">TURING</div>
    <div class="turing-subtitle">JSON Compressor</div>
</div>
''', unsafe_allow_html=True)

# System prompt button (right-aligned)
col1, col2, col3 = st.columns([3, 1, 1])
with col3:
    if st.button("System Prompt", type="secondary"):
        st.session_state.show_prompt = not st.session_state.show_prompt

# System prompt section (toggle)
if st.session_state.show_prompt:
    st.divider()
    st.subheader("System Prompt")
    st.code(SYSTEM_PROMPT, language=None, line_numbers=False)
    st.divider()

# Main input section
json_input = st.text_area(
    label="Paste your JSON here",
    key="json_input_area",
    height=300,
    placeholder='{\n  "id": "...",\n  "os": "linux",\n  "events": [...]\n}',
    label_visibility="collapsed"
)

# Callback to clear text and reset state
def clear_text():
    st.session_state.json_input_area = ""
    st.session_state.processed_data = None
    st.session_state.original_data = None
    st.session_state.zip_data = None

# Button row
col1, col2, col3 = st.columns([2, 1, 2])
with col1:
    compress_btn = st.button("Compress & Extract", type="primary", use_container_width=True)
with col2:
    st.button("Clear", use_container_width=True, on_click=clear_text)

# Process on button click - store in session state
if compress_btn:
    if json_input.strip():
        try:
            # Parse
            original_data = json.loads(json_input)
            
            # Minimize
            compressed_data = minimize_json(original_data)
            
            # Calculate
            orig_size, min_size, savings = calculate_savings(original_data, compressed_data)
            
            # Store in session state
            st.session_state.processed_data = {
                'compressed': compressed_data,
                'orig_size': orig_size,
                'min_size': min_size,
                'savings': savings,
                'file_id': compressed_data.get('id', 'output')
            }
            st.session_state.original_data = original_data
            st.session_state.zip_data = None  # Reset ZIP when reprocessing
                
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON format: {str(e)}")
        except KeyError as e:
            st.error(f"Missing required field: {str(e)}")
        except Exception as e:
            st.error(f"Error processing JSON: {str(e)}")
    else:
        st.warning("Please paste JSON content first")

# Display results from session state (persists across reruns)
if st.session_state.processed_data:
    data = st.session_state.processed_data
    
    # Success message
    st.success("Compressed successfully")
    
    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Original", f"{data['orig_size']/1024:.1f} KB")
    with col2:
        st.metric("Compressed", f"{data['min_size']/1024:.1f} KB")
    with col3:
        st.metric("Saved", f"{data['savings']:.1f}%")
    
    st.caption(f"Processed {len(data['compressed']['events'])} events")
    
    # Download JSON
    compressed_json = json.dumps(data['compressed'], indent=2)
    st.download_button(
        label="📄 Download Minimal JSON",
        data=compressed_json,
        file_name=f"{data['file_id']}.json",
        mime="application/json",
        use_container_width=True
    )
    
    # Download Screenshots section
    st.divider()
    st.subheader("📸 Event Screenshots")
    
    # Fetch screenshots button
    if st.button("Fetch & Download Screenshots (ZIP)", type="secondary", use_container_width=True):
        with st.spinner("Downloading screenshots... This may take a moment."):
            zip_bytes, count = download_screenshots_as_zip(st.session_state.original_data)
            if count > 0:
                st.session_state.zip_data = {'bytes': zip_bytes, 'count': count}
            else:
                st.session_state.zip_data = None
                st.warning("No screenshots found in the JSON.")
    
    # Display ZIP download button if available
    if st.session_state.zip_data:
        st.success(f"Downloaded {st.session_state.zip_data['count']} screenshots!")
        st.download_button(
            label=f"📥 Download {st.session_state.zip_data['count']} Screenshots (ZIP)",
            data=st.session_state.zip_data['bytes'],
            file_name=f"{data['file_id']}_screenshots.zip",
            mime="application/zip",
            use_container_width=True
        )
    
    # Preview
    with st.expander("Preview Compressed JSON"):
        st.json(data['compressed'])

# Privacy notice
st.markdown('''
<div class="privacy-notice">
    🔒 <strong>Privacy:</strong> Your data is processed locally in your browser session.<br>
    No JSON data is stored, logged, or transmitted to any server.
</div>
''', unsafe_allow_html=True)

# Footer
st.divider()
st.caption("Turing QA Toolkit v1.0 • Minimizes annotation JSON files for efficient reviews")
