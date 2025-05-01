import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './ChatBot.css';

const ChatBot = () => {
  const [question, setQuestion] = useState('');
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages appear
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [responses]);

  const handleQuestionChange = (e) => {
    setQuestion(e.target.value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    // Add user message immediately
    const userQuestion = question;
    setResponses([...responses, { user: userQuestion, bot: null }]);
    setQuestion('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8001/ask', {
        question: userQuestion,
        session_id: "frontend-user-123"
      });
      
      // Update the last message with bot response
      setResponses(prev => {
        const newResponses = [...prev];
        newResponses[newResponses.length - 1] = { 
          user: userQuestion, 
          bot: response.data.gemini_answer 
        };
        return newResponses;
      });
    } catch (error) {
      console.error('Error sending question:', error);
      
      // Update with error message
      setResponses(prev => {
        const newResponses = [...prev];
        newResponses[newResponses.length - 1] = { 
          user: userQuestion, 
          bot: "Sorry, something went wrong. Please try again." 
        };
        return newResponses;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-box">
        <h1 className="chat-title">Coffee Sales Chatbot</h1>
        <div className="chat-messages">
          {responses.length === 0 && (
            <div className="welcome-message">
              <p>👋 Hi there! I'm your Coffee Sales Assistant.</p>
              <p>Ask me anything about coffee sales, inventory, or popular products!</p>
            </div>
          )}
          
          {responses.map((response, index) => (
            <div key={index} className="chat-message-group">
              <div className="chat-message user">
                <span className="message-icon">🧑</span> {response.user}
              </div>
              <div className="chat-message bot">
                <span className="message-icon">☕</span> 
                {response.bot === null ? (
                  <span className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </span>
                ) : (
                  response.bot
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        
        <form onSubmit={handleSubmit} className="chat-form">
          <input
            type="text"
            value={question}
            onChange={handleQuestionChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about coffee sales..."
            disabled={loading}
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Thinking...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatBot;