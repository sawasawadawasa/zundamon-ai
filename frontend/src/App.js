import React, { useState, useEffect, useRef } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [messages, setMessages] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [currentTranscript, setCurrentTranscript] = useState("");
  const [isApiKeySet, setIsApiKeySet] = useState(false);
  
  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Initialize session ID
    setSessionId(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const initializeSpeechRecognition = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('お使いのブラウザは音声認識をサポートしていません。Chrome、Edge、Safariをご利用ください。');
      return false;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognitionRef.current = new SpeechRecognition();
    
    recognitionRef.current.continuous = false;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = 'ja-JP';

    recognitionRef.current.onstart = () => {
      setIsListening(true);
      setCurrentTranscript("");
    };

    recognitionRef.current.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          transcript += event.results[i][0].transcript;
        } else {
          setCurrentTranscript(event.results[i][0].transcript);
        }
      }
      
      if (transcript) {
        handleVoiceInput(transcript);
      }
    };

    recognitionRef.current.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
      setCurrentTranscript("");
      
      if (event.error === 'not-allowed') {
        alert('マイクのアクセス許可が必要です。ブラウザの設定でマイクのアクセスを許可してください。');
      }
    };

    recognitionRef.current.onend = () => {
      setIsListening(false);
      setCurrentTranscript("");
    };

    return true;
  };

  const startListening = () => {
    if (!isApiKeySet) {
      alert('OpenAI APIキーを設定してください。');
      return;
    }

    if (!recognitionRef.current) {
      if (!initializeSpeechRecognition()) {
        return;
      }
    }

    if (!isListening) {
      recognitionRef.current.start();
    }
  };

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  };

  const handleVoiceInput = async (text) => {
    if (!text.trim()) return;

    setIsProcessing(true);
    
    // Add user message to chat
    const userMessage = {
      id: Date.now().toString(),
      text: text,
      isUser: true,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await axios.post(`${API}/chat`, {
        text: text,
        session_id: sessionId,
        openai_api_key: apiKey
      });

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        text: response.data.text,
        isUser: false,
        timestamp: new Date(),
        audioBase64: response.data.audio_base64
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Play audio response
      if (response.data.audio_base64) {
        playAudio(response.data.audio_base64);
      }

    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        text: 'エラーが発生しました。APIキーを確認してください。',
        isUser: false,
        timestamp: new Date(),
        isError: true
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  const playAudio = (audioBase64) => {
    try {
      const audioBlob = base64ToBlob(audioBase64, 'audio/wav');
      const audioUrl = URL.createObjectURL(audioBlob);
      
      if (audioRef.current) {
        audioRef.current.src = audioUrl;
        audioRef.current.play().catch(error => {
          console.error('Audio play error:', error);
        });
        
        audioRef.current.onended = () => {
          URL.revokeObjectURL(audioUrl);
        };
      }
    } catch (error) {
      console.error('Audio play error:', error);
    }
  };

  const base64ToBlob = (base64, mimeType) => {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], {type: mimeType});
  };

  const handleApiKeySubmit = (e) => {
    e.preventDefault();
    if (apiKey.trim()) {
      setIsApiKeySet(true);
    }
  };

  const clearChat = async () => {
    try {
      await axios.delete(`${API}/chat/${sessionId}`);
      setMessages([]);
    } catch (error) {
      console.error('Clear chat error:', error);
    }
  };

  const resetApiKey = () => {
    setIsApiKeySet(false);
    setApiKey("");
    setMessages([]);
  };

  if (!isApiKeySet) {
    return (
      <div className="App">
        <div className="api-key-setup">
          <div className="setup-card">
            <h1>🎤 音声チャット</h1>
            <p>OpenAI APIキーを入力してください</p>
            <form onSubmit={handleApiKeySubmit}>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="api-key-input"
                required
              />
              <button type="submit" className="submit-btn">開始</button>
            </form>
            <div className="help-text">
              <p>APIキーは <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer">OpenAI Platform</a> で取得できます</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <div className="chat-container">
        <div className="chat-header">
          <h1>🎤 ずんだもん音声チャット</h1>
          <div className="header-controls">
            <button onClick={clearChat} className="clear-btn">履歴クリア</button>
            <button onClick={resetApiKey} className="reset-btn">APIキー変更</button>
          </div>
        </div>

        <div className="messages-container">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.isUser ? 'user' : 'assistant'} ${message.isError ? 'error' : ''}`}
            >
              <div className="message-content">
                <div className="message-text">{message.text}</div>
                <div className="message-time">
                  {new Date(message.timestamp).toLocaleTimeString('ja-JP')}
                </div>
              </div>
            </div>
          ))}
          
          {currentTranscript && (
            <div className="message user interim">
              <div className="message-content">
                <div className="message-text">{currentTranscript}</div>
                <div className="message-time">認識中...</div>
              </div>
            </div>
          )}
          
          {isProcessing && (
            <div className="message assistant processing">
              <div className="message-content">
                <div className="message-text">考え中...</div>
                <div className="loading-spinner"></div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="voice-controls">
          <button
            onClick={isListening ? stopListening : startListening}
            className={`voice-btn ${isListening ? 'listening' : ''} ${isProcessing ? 'disabled' : ''}`}
            disabled={isProcessing}
          >
            {isListening ? '🎤 録音中... (クリックで停止)' : '🎤 話しかける'}
          </button>
          
          {isListening && (
            <div className="listening-indicator">
              <div className="pulse"></div>
              音声を認識しています...
            </div>
          )}
        </div>
      </div>

      <audio ref={audioRef} />
    </div>
  );
}

export default App;