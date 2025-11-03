# Streaming Response Implementation Guide for Frontend

## Overview
The backend now supports streaming responses via Server-Sent Events (SSE). The endpoint `/query/stream` streams responses in real-time as they're generated.

## Backend Endpoint Details

**Endpoint:** `POST /query/stream`  
**Content-Type:** `application/json` (request)  
**Response Type:** `text/event-stream` (SSE)

**Request Body:**
```json
{
  "question": "Your question here",
  "session_id": "optional-session-id",  // Optional
  "new_chat": false  // Optional, set to true for new chat
}
```

**Headers Required:**
- `Authorization: Bearer <your_jwt_token>`
- `Content-Type: application/json`

## Response Format (Server-Sent Events)

The response uses SSE format with JSON data in each event:

```
data: {"content": "chunk of text", "done": false}

data: {"content": "more text", "done": false}

data: {"content": "", "done": true, "full_response": "complete response text"}
```

### Response Fields:
- `content`: String - The text chunk for this event (empty string on final event)
- `done`: Boolean - `true` when streaming is complete
- `full_response`: String - (Only on final event) The complete concatenated response
- `error`: Boolean - (Optional) `true` if an error occurred

## Frontend Implementation

### Using Fetch API with EventSource-like parsing:

```javascript
async function streamQuery(question, sessionId = null, newChat = false) {
  const token = localStorage.getItem('token'); // or wherever you store the token
  
  const response = await fetch('http://your-backend-url/query/stream', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question: question,
      session_id: sessionId,
      new_chat: newChat
    })
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop(); // Keep incomplete line in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        
        if (data.error) {
          console.error('Error:', data.content);
          // Handle error
          return;
        }
        
        // Update UI with the content chunk
        if (data.content) {
          appendToChat(data.content); // Your function to update UI
        }
        
        if (data.done) {
          // Streaming complete
          // data.full_response contains the complete response
          console.log('Streaming complete:', data.full_response);
          return data.full_response;
        }
      }
    }
  }
}
```

### Using with React (Example Hook):

```javascript
import { useState, useCallback } from 'react';

export function useStreamingQuery() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);

  const streamQuery = useCallback(async (question, sessionId = null, onChunk = null) => {
    setIsStreaming(true);
    setError(null);
    
    const token = localStorage.getItem('token');
    let fullResponse = '';

    try {
      const response = await fetch('http://your-backend-url/query/stream', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: question,
          session_id: sessionId,
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.error) {
              throw new Error(data.content);
            }
            
            if (data.content) {
              fullResponse += data.content;
              if (onChunk) {
                onChunk(data.content);
              }
            }
            
            if (data.done) {
              setIsStreaming(false);
              return data.full_response || fullResponse;
            }
          }
        }
      }
    } catch (err) {
      setError(err.message);
      setIsStreaming(false);
      throw err;
    }
  }, []);

  return { streamQuery, isStreaming, error };
}
```

### React Component Example:

```javascript
function ChatComponent() {
  const [message, setMessage] = useState('');
  const [streamingText, setStreamingText] = useState('');
  const { streamQuery, isStreaming } = useStreamingQuery();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStreamingText(''); // Clear previous response
    
    // Start streaming
    streamQuery(message, null, (chunk) => {
      // Append each chunk as it arrives
      setStreamingText(prev => prev + chunk);
    });
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={isStreaming}
        />
        <button type="submit" disabled={isStreaming}>
          {isStreaming ? 'Streaming...' : 'Send'}
        </button>
      </form>
      
      <div className="response">
        {streamingText}
        {isStreaming && <span className="cursor">|</span>}
      </div>
    </div>
  );
}
```

## Important Notes

1. **Authentication**: Don't forget to include the JWT token in the `Authorization` header
2. **CORS**: Ensure your backend CORS settings allow your frontend origin
3. **Error Handling**: Always check for `error: true` in the response data
4. **Connection Management**: Handle connection drops gracefully
5. **Session Management**: The streaming endpoint supports the same session management as the regular `/query` endpoint

## Differences from Regular `/query` Endpoint

- **Response Type**: SSE stream instead of JSON
- **Real-time Updates**: Content arrives incrementally
- **No `session_id` or `session_name` in stream**: These are handled server-side, but you'll know the session_id from the request

## Testing

You can test the endpoint with curl:

```bash
curl -N -X POST http://your-backend-url/query/stream \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the topic about?"}'
```

The `-N` flag disables buffering so you can see the stream in real-time.

