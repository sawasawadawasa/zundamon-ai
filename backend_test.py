#!/usr/bin/env python3
import requests
import json
import uuid
import base64
import os
import time
from typing import Dict, Any, Optional

# Get the backend URL from the frontend .env file
BACKEND_URL = None
try:
    with open('/app/frontend/.env', 'r') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BACKEND_URL = line.strip().split('=')[1].strip('"\'')
                break
except Exception as e:
    print(f"Error reading frontend .env file: {e}")

if not BACKEND_URL:
    raise ValueError("Could not find REACT_APP_BACKEND_URL in frontend .env file")

API_URL = f"{BACKEND_URL}/api"
print(f"Using API URL: {API_URL}")

# Mock OpenAI API key for testing (this is not a real key)
MOCK_OPENAI_API_KEY = "sk-mock12345678901234567890123456789012345678901234"

class VoiceChatAPITester:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.session_id = str(uuid.uuid4())
        self.results = {
            "health_check": False,
            "chat_endpoint_validation": False,
            "chat_endpoint_error_handling": False,
            "chat_history_get": False,
            "chat_history_delete": False,
            "mongodb_integration": False,
            "voicevox_integration": False
        }
        self.test_messages = []
    
    def log_test(self, test_name: str, passed: bool, message: str):
        """Log test results with detailed messages"""
        status = "PASSED" if passed else "FAILED"
        print(f"[{status}] {test_name}: {message}")
        self.test_messages.append(f"[{status}] {test_name}: {message}")
        return passed
    
    def test_health_check(self) -> bool:
        """Test the health check endpoint"""
        try:
            response = requests.get(f"{self.api_url}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "Voice Chat API is running" in data["message"]:
                    self.results["health_check"] = True
                    return self.log_test("Health Check", True, "API is running correctly")
            return self.log_test("Health Check", False, f"Unexpected response: {response.text}")
        except Exception as e:
            return self.log_test("Health Check", False, f"Exception: {str(e)}")
    
    def test_chat_endpoint_validation(self) -> bool:
        """Test input validation on chat endpoint"""
        try:
            # Test empty text validation
            response = requests.post(
                f"{self.api_url}/chat",
                json={"text": "   ", "session_id": self.session_id, "openai_api_key": MOCK_OPENAI_API_KEY}
            )
            empty_text_valid = False
            if response.status_code == 400:
                empty_text_valid = True
                self.log_test("Empty Text Validation", True, "Empty text validation passed")
            else:
                self.log_test("Empty Text Validation", False, f"Empty text validation failed with status {response.status_code}")
            
            # Test missing API key validation
            response = requests.post(
                f"{self.api_url}/chat",
                json={"text": "Hello", "session_id": self.session_id, "openai_api_key": ""}
            )
            missing_key_valid = False
            if response.status_code == 400:
                missing_key_valid = True
                self.log_test("Missing API Key Validation", True, "Missing API key validation passed")
            else:
                self.log_test("Missing API Key Validation", False, f"Missing API key validation failed with status {response.status_code}")
            
            if empty_text_valid and missing_key_valid:
                self.results["chat_endpoint_validation"] = True
                return self.log_test("Chat Endpoint Validation", True, "Input validation is working correctly")
            else:
                return self.log_test("Chat Endpoint Validation", False, "One or more validation checks failed")
        except Exception as e:
            return self.log_test("Chat Endpoint Validation", False, f"Exception: {str(e)}")
    
    def test_chat_endpoint_error_handling(self) -> bool:
        """Test error handling with invalid OpenAI API key"""
        try:
            response = requests.post(
                f"{self.api_url}/chat",
                json={"text": "Test message", "session_id": self.session_id, "openai_api_key": "invalid_key"}
            )
            
            # We expect an error from OpenAI, but the API should handle it gracefully
            if 400 <= response.status_code < 600:
                self.results["chat_endpoint_error_handling"] = True
                return self.log_test("Chat Endpoint Error Handling", True, 
                                    f"API correctly handled invalid API key with status {response.status_code}")
            
            return self.log_test("Chat Endpoint Error Handling", False, 
                                f"Unexpected response with invalid API key: {response.status_code}")
        except Exception as e:
            return self.log_test("Chat Endpoint Error Handling", False, f"Exception: {str(e)}")
    
    def test_chat_history_endpoints(self) -> bool:
        """Test chat history GET and DELETE endpoints"""
        try:
            # First, add a test message to the history
            test_message = "This is a test message for history"
            requests.post(
                f"{self.api_url}/chat",
                json={"text": test_message, "session_id": self.session_id, "openai_api_key": MOCK_OPENAI_API_KEY}
            )
            
            # Test GET endpoint
            response = requests.get(f"{self.api_url}/chat/{self.session_id}")
            get_success = False
            
            if response.status_code == 200:
                data = response.json()
                if "messages" in data:
                    get_success = True
                    self.results["chat_history_get"] = True
                    self.log_test("Chat History GET", True, f"Successfully retrieved chat history")
            else:
                self.log_test("Chat History GET", False, f"Failed to get chat history: {response.text}")
            
            # Test DELETE endpoint
            response = requests.delete(f"{self.api_url}/chat/{self.session_id}")
            delete_success = False
            
            if response.status_code == 200:
                data = response.json()
                if "deleted_count" in data:
                    delete_success = True
                    self.results["chat_history_delete"] = True
                    self.log_test("Chat History DELETE", True, f"Successfully deleted chat history")
            else:
                self.log_test("Chat History DELETE", False, f"Failed to delete chat history: {response.text}")
            
            return get_success and delete_success
        except Exception as e:
            self.log_test("Chat History Endpoints", False, f"Exception: {str(e)}")
            return False
    
    def test_mongodb_integration(self) -> bool:
        """Test MongoDB integration by checking if messages are stored and retrieved"""
        try:
            # Generate a unique session ID for this test
            test_session_id = f"test-mongo-{uuid.uuid4()}"
            test_message = "Testing MongoDB integration"
            
            # Send a message
            requests.post(
                f"{self.api_url}/chat",
                json={"text": test_message, "session_id": test_session_id, "openai_api_key": MOCK_OPENAI_API_KEY}
            )
            
            # Check if the message was stored
            response = requests.get(f"{self.api_url}/chat/{test_session_id}")
            
            if response.status_code == 200:
                data = response.json()
                if "messages" in data and len(data["messages"]) > 0:
                    # Check if our test message is in the history
                    user_messages = [msg for msg in data["messages"] if msg.get("is_user") and msg.get("text") == test_message]
                    if user_messages:
                        self.results["mongodb_integration"] = True
                        return self.log_test("MongoDB Integration", True, "Messages are correctly stored and retrieved")
            
            return self.log_test("MongoDB Integration", False, "Failed to verify message storage in MongoDB")
        except Exception as e:
            return self.log_test("MongoDB Integration", False, f"Exception: {str(e)}")
    
    def test_voicevox_integration(self) -> bool:
        """Test VOICEVOX integration by checking if audio is generated"""
        try:
            # This test might fail if the VOICEVOX demo server is unavailable
            # We'll use a short message to minimize processing time
            test_message = "こんにちは"
            
            response = requests.post(
                f"{self.api_url}/chat",
                json={"text": test_message, "session_id": self.session_id, "openai_api_key": MOCK_OPENAI_API_KEY}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "audio_base64" in data and data["audio_base64"]:
                    # Try to decode the base64 to verify it's valid
                    try:
                        audio_data = base64.b64decode(data["audio_base64"])
                        if len(audio_data) > 0:
                            self.results["voicevox_integration"] = True
                            return self.log_test("VOICEVOX Integration", True, "Audio was successfully generated")
                    except:
                        pass
            
            return self.log_test("VOICEVOX Integration", False, "Failed to verify audio generation")
        except Exception as e:
            return self.log_test("VOICEVOX Integration", False, f"Exception: {str(e)}")
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        print("\n===== Starting Voice Chat API Tests =====\n")
        
        # Test health check first
        self.test_health_check()
        
        # Test validation and error handling
        self.test_chat_endpoint_validation()
        self.test_chat_endpoint_error_handling()
        
        # Test chat history endpoints
        self.test_chat_history_endpoints()
        
        # Test MongoDB integration
        self.test_mongodb_integration()
        
        # Test VOICEVOX integration last (may be slow or fail due to external dependency)
        self.test_voicevox_integration()
        
        # Print summary
        print("\n===== Test Results Summary =====")
        for test_name, result in self.results.items():
            status = "PASSED" if result else "FAILED"
            print(f"{test_name}: {status}")
        
        print("\n===== Detailed Test Messages =====")
        for message in self.test_messages:
            print(message)
        
        return self.results

if __name__ == "__main__":
    tester = VoiceChatAPITester(API_URL)
    results = tester.run_all_tests()
    
    # Overall test result
    all_passed = all(results.values())
    print(f"\n===== Overall Test Result: {'PASSED' if all_passed else 'FAILED'} =====")