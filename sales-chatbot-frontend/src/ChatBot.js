import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './ChatBot.css';

const ChatBot = () => {
  const [question, setQuestion] = useState('');
  const [responses, setResponses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages appear
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [responses]);

  // Initialize session when component mounts
  useEffect(() => {
    const initializeSession = async () => {
      try {
        const response = await axios.post('http://localhost:8000/session');
        setSessionId(response.data.session_id);
        console.log('Session initialized:', response.data.session_id);
      } catch (error) {
        console.error('Error initializing session:', error);
      }
    };

    initializeSession();
  }, []);

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
      const response = await axios.post('http://localhost:8000/ask', {
        question: userQuestion,
        session_id: sessionId
      });
      
      // Update the last message with bot response
      setResponses(prev => {
        const newResponses = [...prev];
        newResponses[newResponses.length - 1] = { 
          user: userQuestion, 
          bot: {
            answer: response.data.answer,
            sqlQuery: response.data.sql_query,
            explanation: response.data.sql_explanation
          }
        };
        return newResponses;
      });

      // Update session ID if it was created in the response
      if (response.data.session_id && !sessionId) {
        setSessionId(response.data.session_id);
      }
    } catch (error) {
      console.error('Error sending question:', error);
      
      // Update with error message
      setResponses(prev => {
        const newResponses = [...prev];
        newResponses[newResponses.length - 1] = { 
          user: userQuestion, 
          bot: {
            answer: error.response?.data?.detail || "Sorry, something went wrong. Please try again."
          }
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

  // Toggle SQL details visibility
  const toggleSqlDetails = (index) => {
    setResponses(prev => {
      const newResponses = [...prev];
      if (newResponses[index].bot.showDetails === undefined) {
        newResponses[index].bot.showDetails = true;
      } else {
        newResponses[index].bot.showDetails = !newResponses[index].bot.showDetails;
      }
      return newResponses;
    });
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
                  <div className="bot-response">
                    <div className="answer">{response.bot.answer}</div>
                    
                    {response.bot.sqlQuery && (
                      <div className="sql-container">
                        <button 
                          className="toggle-sql-btn"
                          onClick={() => toggleSqlDetails(index)}
                        >
                          {response.bot.showDetails ? 'Hide SQL Details' : 'Show SQL Details'}
                        </button>
                        
                        {response.bot.showDetails && (
                          <div className="sql-details">
                            <div className="sql-query">
                              <h4>SQL Query:</h4>
                              <pre>{response.bot.sqlQuery}</pre>
                            </div>
                            
                            {response.bot.explanation && (
                              <div className="sql-explanation">
                                <h4>Explanation:</h4>
                                <p>{response.bot.explanation}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
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