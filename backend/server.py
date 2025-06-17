from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import aiohttp
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    text: str
    is_user: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    audio_base64: Optional[str] = None

class VoiceChatRequest(BaseModel):
    text: str
    session_id: str
    openai_api_key: str

class ConfigRequest(BaseModel):
    openai_api_key: str

# Health check
@api_router.get("/")
async def root():
    return {"message": "Voice Chat API is running"}

# Chat endpoint
@api_router.post("/chat")
async def voice_chat(request: VoiceChatRequest):
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        if not request.openai_api_key:
            raise HTTPException(status_code=400, detail="OpenAI API key is required")

        # Save user message
        user_message = ChatMessage(
            session_id=request.session_id,
            text=request.text,
            is_user=True
        )
        await db.chat_messages.insert_one(user_message.dict())

        # Create LLM chat instance
        chat = LlmChat(
            api_key=request.openai_api_key,
            session_id=request.session_id,
            system_message="あなたは親しみやすく楽しい日本語のAIアシスタントです。自然で会話らしい口調で返答してください。"
        ).with_model("openai", "gpt-4o")

        # Create user message for LLM
        llm_message = UserMessage(text=request.text)
        
        # Get response from LLM
        llm_response = await chat.send_message(llm_message)
        
        if not llm_response:
            raise HTTPException(status_code=500, detail="Failed to get response from LLM")

        # Generate speech using VOICEVOX
        audio_base64 = await generate_voicevox_audio(llm_response)

        # Save assistant message
        assistant_message = ChatMessage(
            session_id=request.session_id,
            text=llm_response,
            is_user=False,
            audio_base64=audio_base64
        )
        await db.chat_messages.insert_one(assistant_message.dict())

        return {
            "text": llm_response,
            "audio_base64": audio_base64,
            "session_id": request.session_id
        }

    except Exception as e:
        logger.error(f"Error in voice_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

async def generate_voicevox_audio(text: str) -> str:
    """Generate audio using VOICEVOX API with Zundamon voice (speaker_id=3)"""
    try:
        # VOICEVOX API endpoint (using demo server)
        voicevox_base_url = "https://voicevox.su-shiki.com"
        
        async with aiohttp.ClientSession() as session:
            # Create audio query
            query_params = {
                "text": text,
                "speaker": 3  # Zundamon
            }
            
            async with session.post(
                f"{voicevox_base_url}/audio_query",
                params=query_params
            ) as response:
                if response.status != 200:
                    logger.error(f"VOICEVOX audio_query failed: {response.status}")
                    return ""
                
                audio_query = await response.json()
            
            # Synthesize audio
            async with session.post(
                f"{voicevox_base_url}/synthesis",
                params={"speaker": 3},
                json=audio_query
            ) as response:
                if response.status != 200:
                    logger.error(f"VOICEVOX synthesis failed: {response.status}")
                    return ""
                
                audio_data = await response.read()
                
                # Convert to base64
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                return audio_base64

    except Exception as e:
        logger.error(f"Error generating VOICEVOX audio: {str(e)}")
        return ""

@api_router.get("/chat/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    try:
        messages = await db.chat_messages.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).to_list(100)
        
        return {"messages": [ChatMessage(**msg) for msg in messages]}
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get chat history")

@api_router.delete("/chat/{session_id}")
async def clear_chat_history(session_id: str):
    """Clear chat history for a session"""
    try:
        result = await db.chat_messages.delete_many({"session_id": session_id})
        return {"deleted_count": result.deleted_count}
    except Exception as e:
        logger.error(f"Error clearing chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear chat history")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()