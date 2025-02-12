import streamlit as st
import requests
import json
from datetime import datetime
import os

# Set page config
st.set_page_config(
    page_title="AI Agent Interface",
    page_icon="🤖",
    layout="wide"
)

# Add custom CSS
st.markdown("""
    <style>
    .stTextArea textarea {
        font-size: 16px;
    }
    .stButton button {
        background-color: #4CAF50;
        color: white;
        font-size: 16px;
        padding: 10px 24px;
        border-radius: 5px;
    }
    .stButton button:hover {
        background-color: #45a049;
    }
    </style>
""", unsafe_allow_html=True)

def call_api(user_input, api_url):
    """
    Call the API endpoint with the user input
    """
    try:
        # Get the base API URL from environment variable, fallback to the one in session state
        base_url = os.getenv('API_ENDPOINT', api_url.rsplit('/', 1)[0])
        
        # Construct the full endpoint URL
        endpoint_url = f"{base_url}/query"
        
        # Prepare the payload
        payload = {
            "question": user_input  # Changed from "user_input" to "question" to match API
        }
        
        # Make the POST request with proper headers
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(endpoint_url, json=payload, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            result = response.json()
            # Add error handling for potential missing 'answer' key
            answer = result.get('answer', result)  # Fallback to entire response if 'answer' key missing
            return {"success": True, "data": answer}
        else:
            return {"success": False, "error": f"Error: {response.status_code} - {response.text}"}
            
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Error connecting to API: {str(e)}"}

def initialize_session_state():
    """Initialize session state variables"""
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'api_url' not in st.session_state:
        # Get the API URL from environment variable or use default
        default_url = os.getenv('API_ENDPOINT', 'http://localhost:8000')
        st.session_state.api_url = default_url

def main():
    initialize_session_state()
    
    # Create two columns for main content and sidebar
    main_col, sidebar_col = st.columns([3, 1])
    
    with main_col:
        # Add a title with emoji
        st.title("AI Agent Interface 🤖")
        
        # Add description
        st.markdown("""
        Welcome to the AI Agent Interface! This tool helps you interact with our AI agent.
        Simply enter your query below and get instant responses.
        """)
        
        # Create input text area with default text
        default_text = """Find one or more orthopedic specialist (knee doctor) who:
    1. Accepts uninsured patients
    2. Has availability for appointments on Mondays between 8:00 - 12:00 CET
    3. Can schedule a 30 min appointment for February 2025"""
        
        user_input = st.text_area(
            "Enter your query:",
            value=default_text,
            height=150,
            key="input_area"
        )
        
        # Create columns for button centering
        col1, col2, col3 = st.columns([1,1,1])
        
        # Add submit button
        with col2:
            submit_button = st.button("Submit Query", type="primary")
        
        # Add a divider
        st.divider()
        
        # Create a container for the response
        response_container = st.container()
        
        # When submit button is clicked
        if submit_button:
            if user_input:
                with response_container:
                    # Show spinner while waiting for response
                    with st.spinner("Processing your query..."):
                        response = call_api(user_input, st.session_state.api_url)
                    
                    if response["success"]:
                        st.success("Query processed successfully!")
                        st.markdown("### Response:")
                        st.markdown(response["data"])
                        
                        # Add to history
                        st.session_state.history.append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "query": user_input,
                            "response": response["data"]
                        })
                    else:
                        st.error(response["error"])
            else:
                st.warning("Please enter a query first.")
    
    # Sidebar content
    with sidebar_col:
        st.sidebar.header("Settings ⚙️")
        
        # API URL configuration
        api_url = st.sidebar.text_input(
            "API URL",
            value=st.session_state.api_url,
            key="api_url_input"
        )
        
        # Update session state when API URL changes
        if api_url != st.session_state.api_url:
            st.session_state.api_url = api_url
        
        # History section
        if st.session_state.history:
            st.sidebar.header("History 📚")
            
            # Clear history button
            if st.sidebar.button("Clear History"):
                st.session_state.history = []
                st.rerun()
            
            # Display history items
            for idx, item in enumerate(reversed(st.session_state.history)):
                with st.sidebar.expander(f"Query {len(st.session_state.history) - idx}", expanded=False):
                    st.write(f"**Time:** {item['timestamp']}")
                    st.write("**Query:**")
                    st.write(item["query"])
                    st.write("**Response:**")
                    st.write(item["response"])
                    st.divider()

if __name__ == "__main__":
    main()