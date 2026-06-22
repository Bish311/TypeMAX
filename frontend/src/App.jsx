import { useState, useEffect } from 'react'
import axios from 'axios'
import './index.css'

const API_BASE = 'http://127.0.0.1:8765'

function App() {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [trending, setTrending] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)

  useEffect(() => {
    fetchTrending()
    const interval = setInterval(fetchTrending, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (query) {
        fetchSuggestions(query)
      } else {
        setSuggestions([])
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const fetchTrending = async () => {
    try {
      const res = await axios.get(`${API_BASE}/trending`)
      setTrending(res.data)
    } catch (e) {
      console.error(e)
    }
  }

  const fetchSuggestions = async (q) => {
    try {
      setLoading(true)
      const res = await axios.get(`${API_BASE}/suggest?q=${q}`)
      setSuggestions(res.data)
      setSelectedIndex(-1)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (searchQuery) => {
    if (!searchQuery) return
    try {
      await axios.post(`${API_BASE}/search`, { query: searchQuery })
      setQuery(searchQuery)
      setSuggestions([])
      setSelectedIndex(-1)
      setTimeout(fetchTrending, 1000)
    } catch (e) {
      console.error(e)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (selectedIndex < suggestions.length - 1) {
        setSelectedIndex(selectedIndex + 1)
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (selectedIndex > 0) {
        setSelectedIndex(selectedIndex - 1)
      }
    } else if (e.key === 'Enter') {
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        handleSearch(suggestions[selectedIndex].query)
      } else {
        handleSearch(query)
      }
    } else if (e.key === 'Escape') {
      setSuggestions([])
      setSelectedIndex(-1)
    }
  }

  return (
    <div className="container">
      <h1>TypeMAX</h1>
      <p className="subtitle">by Bishwayan</p>

      <div className="search-box">
        <input 
          type="text" 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Start typing to search..."
          spellCheck="false"
          autoComplete="off"
        />
        <button onClick={() => handleSearch(query)}>Search</button>
      </div>
      
      {loading && <div className="loading">loading...</div>}
      
      {suggestions.length > 0 && (
        <ul className="suggestions">
          {suggestions.map((s, i) => (
            <li
              key={i}
              className={i === selectedIndex ? 'selected' : ''}
              onClick={() => handleSearch(s.query)}
              onMouseEnter={() => setSelectedIndex(i)}
            >
              <span className="suggestion-query">{s.query}</span>
              <span className="count">{s.count.toLocaleString()}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="trending">
        <h2>Trending</h2>
        <div className="trending-list">
          {trending.map((t, i) => (
            <button key={i} className="trending-tag" onClick={() => handleSearch(t.query)}>
              {t.query}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default App
