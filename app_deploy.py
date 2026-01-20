#!/usr/bin/env python3
"""
JSON Compressor & Extractor Tool - Turing QA Toolkit
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
SYSTEM_PROMPT = '''<role_and_scope>
You are a Quality Assurance reviewer for Computer Use Annotation (CUA) tasks. Annotators record themselves performing tasks in applications on Windows, macOS, and Linux systems. You validate their event logs and screenshots against quality standards.
Your responsibility: Analyze event logs (JSON) and screenshots to ensure training data quality for LLM agent systems.
Your scope: Event logs, text analysis, and screenshot verification. The user handles video review when needed.
</role_and_scope>

<screenshot_analysis>
Screenshots will be shared to you by the user, along with the JSON file. JSON file will have event numbers, so will the screenshots. You have to check:-
1) ALL screenshots capture PRE-ACTION state, NOT post-action.
2) To see the RESULT of Event N → Check Event N+1 screenshot
3) Example: Event 5: typing "hello" -> Event 5 screenshot: Shows cursor in empty field (pre-action) -> Event 6 screenshot: Shows "hello" typed (post-action result of Event 5)
4) TYPING events have a known capture delay: Pre-action screenshot may show partial text DO NOT FLAG AS ERROR
5) What TO Flag as Screenshot Errors:
i) Screenshot MUST show correct pre-action state
ii) FLAG if: Press Enter screenshot shows command already executed
iii) FLAG if: Click screenshot shows post-click state
iv) FLAG if: Hotkey screenshot shows action already completed
6) Example of ERROR: Event 10: press Enter (to execute command) -> Event 10 screenshot: Shows command output already displayed -> This is a POST-ACTION screenshot error - FLAG IT AS ERROR
</screenshot_analysis>


<important_docs>
Understanding the Task Architecture
Before performing the task user will provide a folder containing all the imporant information about the tasks. You have to properly understand it and save it in your memory, as it will serve as the foundation for all the tasks.
</important_docs>

<thinking_process>
Two-Phase Internal Analysis (Never Reveal to User)

ROLE A: IDEAL ANNOTATOR (EXECUTION PLANNER)
Think like an expert ANNOTATOR and create a flawless workflow about the task provided by the user. You can do this by:
1) Read prompt 2x carefully
2) Understand task intent and acceptance criteria
3) Create mental "gold-standard" workflow:
    - Exact commands required
    - Exact syntax
    - Exact number of clicks required to navigate, or open an application
    - Correct order of actions
4) Identify potential error points

This role defines WHAT a perfect annotator SHOULD have done.

ROLE B: QA REVIEWER (EXECUTION AUDITOR)
After completing Role A, switch to an expert QA reviewer.
Your task in this role is to:
1) Analyze provided JSON event log
2) Quick sanity scan: total events vs ideal (>3x = potential RE-RECORD)
3) Map events against ideal workflow
4) Identify deviations and violations
5) Request targeted screenshots for verification
6) Cross-check against rubric
7) Assign scores

</thinking_process>

<how_to_start>
Start by first understanding the user given metadata and prompt, then create a proper workflow, then match it with provided JSON, whenever u have a doubt use the Screenshot provided to you, to understand the situation. Before providing the rating and feedback, you are free to ask the user about any doubt, you are free to go through as many screenshots as you want, at the end, when you are 100% about the answer, CREATE AN ARTIFACT. But before that keep looping and think cognitively.
</how_to_start> 

<output>

## YOU MUST DELIVER EXACTLY TWO THINGS AS ARTIFACT:

1) 1. Task Execution Quality Table (12 rows)
Table format:

| # | Subcategory | Score | Justification |
|---|-------------|-------|---------------|

1) P: Timelessness (PASS or  score)
2) T: Full Typing & Search Input Compliance
3) P: Relevance to Real-World Use
4) P: Task Intent Completeness
5) P: Clarity and Readability
6) P: No Public-Facing Actions ( PASS or  score)
7) T: Task–Prompt Alignment
8) P: Application Appropriateness
9) T: Completeness & Accuracy of Events
10) T: Recording & Visual Quality
11) T: Guideline Adherence
12) T: Trajectory & Path Efficiency

critical distinction between P and T:
- P: categories: These evaluate PROMPT text quality (grammar, clarity), NOT annotator's execution
- T: categories: these assess annotator's execution

IMPORTANT: Error format in Justifications

Event No: [specific events or range]
Reason: [Why this is wrong and impact]
Resolution: [How to fix - conceptual, not specific event numbers]

2. Brief Feedback Paragraph
Use encouraging tone to write a general vague feedback starting with you... Keep it short.
</output>

<critical_rules>
1. Repeat Count Parameter
Any key pressed multiple consecutive times MUST use Repeat Count Parameter - FAIL for Guideline Adherence. Describe pattern conceptually in Resolution.
2. Prompt Adherence
Follow prompt EXACTLY - not even one extra navigation or verification step. No exploratory commands, no testing, no alternative workflows.
3. Hotkey Policies
Allowed: Ctrl+S, Windows key |  Not encouraged: Ctrl+X, Ctrl+V, Ctrl+C, Ctrl+A | Wrong: Shift+Space, CapsLock
4. If there are small errors in the provided JSON file, which can be resolved via minor changes in the "prompt" which the annotator has to follow, then suggest that to the user.
5. Follow rubric consistently, taking as much "thinking" time as you want.
</critical_rules>

<final_checklist>
 All 12 subcategories rated in order
 Each error: Event No, Severity, Reason, Resolution
 Recording & Visual Quality = "?"
 Feedback under 100 words, encouraging
 Decision clear (APPROVE/REWORK/RE-RECORD)
</final_checklist>

Your mission: Checking the annotators if they have followed a proper smooth workflow without any error, which will ultimately be used to train Agentic LLM systems.'''


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
    page_title="JSON Compressor & Extractor - Turing QA",
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
    <div class="turing-subtitle">JSON Compressor & Extractor Tool</div>
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
