import streamlit as st
import os
import asyncio
import asyncpg
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database configuration
NEON_DB_USER = os.getenv("NEON_DB_USER")
NEON_DB_PASSWORD = os.getenv("NEON_DB_PASSWORD")
NEON_DB_HOST = os.getenv("NEON_DB_HOST")
NEON_DB_PORT = os.getenv("NEON_DB_PORT")
NEON_DB_NAME = os.getenv("NEON_DB_NAME")

# Database Functions
async def connect_to_neon():
    conn = await asyncpg.connect(
        user=NEON_DB_USER,
        password=NEON_DB_PASSWORD,
        database=NEON_DB_NAME,
        host=NEON_DB_HOST,
        port=NEON_DB_PORT
    )
    return conn

async def check_user_in_chat_table(username):
    """Check if username exists in the chat table"""
    conn = await connect_to_neon()
    try:
        result = await conn.fetchval(
            'SELECT COUNT(*) FROM chat WHERE username = $1',
            username
        )
        return result > 0
    finally:
        await conn.close()

async def create_new_user_in_chat(username):
    """Create a new user in the chat table"""
    conn = await connect_to_neon()
    try:
        await conn.execute(
            'INSERT INTO chat (username, summary) VALUES ($1, $2)',
            username, ""
        )
    finally:
        await conn.close()

async def get_user_summary(username):
    """Fetch user's chat summary"""
    conn = await connect_to_neon()
    try:
        return await conn.fetchval(
            'SELECT summary FROM chat WHERE username = $1',
            username
        )
    finally:
        await conn.close()

async def update_user_summary(username, new_summary):
    """Update user's chat summary"""
    conn = await connect_to_neon()
    try:
        await conn.execute(
            'UPDATE chat SET summary = $1 WHERE username = $2',
            new_summary, username
        )
    finally:
        await conn.close()

def get_deriv_services_summary():
    return """
    Deriv Affiliate Program Overview and Benefits

    About Deriv:
    Deriv is a leading online trading platform offering various trading instruments including forex, digital options, commodities, cryptocurrencies, and CFDs. With over 20 years of experience, Deriv serves traders globally with innovative trading solutions.

    Affiliate Program Structure:
    1. Commission Structure
    - Up to 45% revenue share commission
    - Lifetime commission on referred clients
    - Multi-tier referral system
    - Weekly payments with no minimum threshold

    2. Available Products
    - Deriv MT5 (Synthetic, Financial, Financial STP)
    - Deriv X
    - DBot (Automated trading)
    - SmartTrader
    - Binary Bot
    - Deriv GO (Mobile trading)

    3. Marketing Support
    - Ready-to-use marketing materials
    - Personalized landing pages
    - Real-time reporting and analytics
    - Dedicated affiliate manager
    - Regular training and webinars

    4. Commission Calculation
    - Revenue share based on client trading volume
    - Additional bonuses for high-performing affiliates
    - Special commission rates for large networks
    - Performance-based commission tiers
    """

def generate_ai_response(username, query, context, is_summary_generation=False):
    messages = [
        {
            "role": "system", 
            "content": f"""You are a knowledgeable Deriv affiliate program advisor. 
            Provide short and crisp answers to the point.
            Provide personalized guidance to affiliates about:
            - Trading strategies for their referral network
            - Ways to maximize commission earnings
            - Effective communication with referrals
            - Best practices for growing their network
            Reference this information: {get_deriv_services_summary()}
            Maintain a professional yet friendly tone."""
        },
        {"role": "user", "content": f"Previous Context: {context}\n\nNew Query: {query}"}
    ]
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=500
    )
    
    ai_response = response.choices[0].message.content
    
    if not is_summary_generation:
        summary_query = f"Create a summary of the conversation:\nPrevious Context: {context}\nUser: {query}\nAI: {ai_response}"
        summary_response = generate_ai_response(username, summary_query, context, is_summary_generation=True)
        asyncio.run(update_user_summary(username, summary_response))
    
    return ai_response

def main():
   
    # Initialize session state for username and chat history
    if 'username' not in st.session_state or 'chat_history' not in st.session_state:
        st.session_state.username = None
        st.session_state.chat_history = []

    # Username collection at the start
    if not st.session_state.username:
        username = st.text_input("Please enter your username to start chatting")
        
        if username:
            # Check if user exists in chat table
            user_exists = asyncio.run(check_user_in_chat_table(username))
            
            if not user_exists:
                # Create new user in chat table
                asyncio.run(create_new_user_in_chat(username))
            
            st.session_state.username = username
            st.rerun()

    else:
        # Chat interface
        st.title("Deriv Affiliate Assistant 💹")
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input
        user_input = st.chat_input("Type your message here...")
        
        if user_input:
            # Display user message
            with st.chat_message("user"):
                st.write(user_input)
            
            # Placeholder for typing indicator
            typing_placeholder = st.empty()
            with typing_placeholder:
                st.chat_message("assistant").write("Typing...")

            # Get context from DB
            context = asyncio.run(get_user_summary(st.session_state.username))
            
            # Generate AI response
            ai_response = generate_ai_response(st.session_state.username, user_input, context)
            
            # Remove typing indicator and display AI response
            typing_placeholder.empty()
            with st.chat_message("assistant"):
                st.write(ai_response)
            
            # Update chat history
            st.session_state.chat_history.extend([
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": ai_response}
            ])

if __name__ == "__main__":
    main()
