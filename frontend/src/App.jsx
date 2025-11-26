import React, { useState, useEffect } from 'react';
import { Bot, Inbox, LogIn, Loader2, Sparkles, X, Zap, Flame, CheckCircle2 } from 'lucide-react';

export default function App() {
  // --- STATE MANAGEMENT ---
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("checking"); // checking, online, offline, auth_required
  
  // Modal & Analysis State
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedThreadId, setSelectedThreadId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  // --- 1. INITIAL LOAD & AUTH CHECK ---
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      // We use credentials: 'include' to ensure the session cookie is sent
      const res = await fetch('http://localhost:5000/api/check-auth', { credentials: 'include' });
      const data = await res.json();
      
      if (data.authenticated) {
        setStatus("online");
        fetchEmails(); // Auto-load emails if logged in
      } else {
        setStatus("auth_required");
      }
    } catch (err) {
      console.error("Backend connection failed:", err);
      setStatus("offline");
    }
  };

  // --- 2. ACTIONS ---
  
  const fetchEmails = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:5000/api/fetch-emails', { credentials: 'include' });
      
      if (res.status === 401) {
        setStatus("auth_required");
        return;
      }
      
      const data = await res.json();
      if (Array.isArray(data)) {
        setEmails(data);
      }
    } catch (err) {
      console.error("Error fetching emails:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (threadId) => {
    setSelectedThreadId(threadId);
    setAnalyzing(true);
    setModalOpen(true); // Open modal immediately to show loading spinner
    setAnalysis(null);

    try {
      const res = await fetch(`http://localhost:5000/api/process-thread/${threadId}`, { credentials: 'include' });
      const data = await res.json();
      
      if (data.error) throw new Error(data.error);
      setAnalysis(data);
    } catch (err) {
      setAnalysis({ error: err.message || "Failed to analyze thread" });
    } finally {
      setAnalyzing(false);
    }
  };

  const closeModal = () => {
    setModalOpen(false);
    // Optional: Clear analysis when closing, or keep it to view again
    // setAnalysis(null); 
  };

  // --- 3. HELPER FOR BADGE COLORS ---
  const getBadgeColor = (category) => {
    switch (category) {
      case "Urgent / Action Required": return "bg-red-100 text-red-800";
      case "University Notice": return "bg-purple-100 text-purple-800";
      case "Personal / Social": return "bg-green-100 text-green-800";
      case "Spam / Promotion": return "bg-yellow-100 text-yellow-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  // --- 4. RENDER UI ---
  return (
    <div className="flex h-screen overflow-hidden bg-gray-100 text-gray-900 font-sans">
      
      {/* === SIDEBAR (Your Design) === */}
      <nav className="w-64 bg-white shadow-md flex-shrink-0 hidden md:block">
        <div className="p-4 flex items-center justify-center border-b">
          <Bot className="text-blue-600 w-8 h-8" />
          <h1 className="text-2xl font-bold ml-2">MailMind</h1>
        </div>
        
        {/* Connection Status Badge */}
        <div className="p-4">
          {status === "checking" && (
            <div className="w-full bg-blue-100 text-blue-800 font-semibold py-2 px-4 rounded-lg flex items-center justify-center animate-pulse">
              Checking API...
            </div>
          )}
          {status === "online" && (
            <div className="w-full bg-green-100 text-green-800 font-semibold py-2 px-4 rounded-lg flex items-center justify-center">
              System Online
            </div>
          )}
          {status === "offline" && (
            <div className="w-full bg-red-100 text-red-800 font-semibold py-2 px-4 rounded-lg flex items-center justify-center text-sm">
              Backend Offline
            </div>
          )}
          {status === "auth_required" && (
             <div className="w-full bg-yellow-100 text-yellow-800 font-semibold py-2 px-4 rounded-lg flex items-center justify-center">
             Login Required
           </div>
          )}
        </div>

        <ul className="space-y-1 p-2">
          <li>
            <a href="#" className="flex items-center space-x-3 px-3 py-2 bg-blue-50 text-blue-700 font-semibold rounded-lg">
              <Inbox className="w-5 h-5" />
              <span>Inbox</span>
            </a>
          </li>
        </ul>
      </nav>

      {/* === MAIN CONTENT === */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <header className="border-b bg-white p-4 flex justify-between items-center shadow-sm z-10">
          <h2 className="text-xl font-semibold">Your Recent Threads</h2>
          <a 
            href="http://localhost:5000/auth/google" 
            className="bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg shadow hover:bg-blue-700 transition duration-300 flex items-center cursor-pointer"
          >
            <LogIn className="w-4 h-4 mr-2" />
            {status === "online" ? "Refresh Login" : "Login with Google"}
          </a>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
             <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <Loader2 className="w-10 h-10 animate-spin mb-2" />
                <p>Syncing with Gmail...</p>
             </div>
          ) : emails.length === 0 ? (
            <div className="text-center p-10 text-gray-500 bg-white rounded-lg border border-dashed border-gray-300">
               {status === "auth_required" 
                 ? "Please log in using the button above to view your emails." 
                 : "No recent emails found in this inbox."}
            </div>
          ) : (
            // Email List Loop
            emails.map(thread => (
              <div key={thread.id} className="bg-white p-4 rounded-lg shadow border border-gray-100 hover:shadow-md transition-all">
                <div className="flex justify-between items-start">
                  <div className="w-3/4 pr-4">
                    <h3 className="font-bold text-lg text-gray-800 truncate">{thread.subject}</h3>
                    <p className="text-sm text-gray-500 font-medium mb-1">{thread.from}</p>
                    <p className="text-sm text-gray-400 line-clamp-2">{thread.snippet}</p>
                  </div>
                  
                  {/* Analyze Button */}
                  <button 
                    onClick={() => handleAnalyze(thread.threadId)}
                    disabled={analyzing && selectedThreadId === thread.threadId}
                    className="bg-blue-50 text-blue-600 hover:bg-blue-100 px-4 py-2 rounded-lg text-sm font-semibold flex items-center transition-colors flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {analyzing && selectedThreadId === thread.threadId ? (
                        <Loader2 className="w-4 h-4 mr-1 animate-spin"/>
                    ) : (
                        <Zap className="w-4 h-4 mr-1" />
                    )}
                    Analyze
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      {/* === RESULT MODAL (Your Design) === */}
      {modalOpen && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 bg-black bg-opacity-50 z-40 backdrop-blur-sm" onClick={closeModal}></div>
          
          {/* Modal Box */}
          <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-2xl bg-white rounded-lg shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            
            {/* Modal Header */}
            <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <Sparkles className="text-purple-600 w-5 h-5" />
                <h3 className="text-lg font-bold text-gray-800">AI Analysis Result</h3>
              </div>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600 transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 max-h-[70vh] overflow-y-auto">
              {analyzing ? (
                <div className="text-center py-12">
                   <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
                   <p className="text-gray-500 font-medium animate-pulse">Reading email & generating insights...</p>
                </div>
              ) : analysis ? (
                  analysis.error ? (
                    <div className="bg-red-50 p-4 rounded-lg text-red-700 text-center border border-red-200">
                      <p className="font-bold">Analysis Failed</p>
                      <p className="text-sm">{analysis.error}</p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      
                      {/* 1. Classification & Urgency */}
                      <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                         <span className={`px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wide ${getBadgeColor(analysis.classification?.category)}`}>
                           {analysis.classification?.category || "Uncategorized"}
                         </span>
                         
                         {analysis.classification?.is_urgent ? (
                           <span className="flex items-center text-red-600 font-bold text-sm bg-white px-2 py-1 rounded border border-red-100 shadow-sm">
                             <Flame className="w-4 h-4 mr-1 text-red-500" /> Urgent
                           </span>
                         ) : (
                           <span className="text-gray-400 text-sm font-medium">Normal Priority</span>
                         )}
                      </div>

                      {/* 2. Summary */}
                      <div>
                        <h4 className="text-xs font-bold text-gray-500 uppercase mb-2 tracking-wider">Executive Summary</h4>
                        <p className="text-gray-800 leading-relaxed bg-white p-4 rounded-lg border border-gray-200 shadow-sm text-lg">
                          {analysis.thread_summary || "No summary available for this thread."}
                        </p>
                      </div>

                      {/* 3. Action Items */}
                      {analysis.latest_action_item && (
                        <div>
                          <h4 className="text-xs font-bold text-blue-600 uppercase mb-2 tracking-wider">Recommended Action</h4>
                          <div className="flex items-start bg-blue-50 p-4 rounded-lg border border-blue-100 text-blue-900 shadow-sm">
                            <CheckCircle2 className="w-5 h-5 mr-3 mt-0.5 flex-shrink-0 text-blue-600" />
                            <p className="font-medium">{analysis.latest_action_item}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )
              ) : null}
            </div>
          </div>
        </>
      )}
    </div>
  );
}