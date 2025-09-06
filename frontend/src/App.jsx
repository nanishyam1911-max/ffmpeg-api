import React, { useState } from 'react'


export default function App() {
const [imageUrl, setImageUrl] = useState('')
const [audioUrl, setAudioUrl] = useState('')
const [lyricsUrl, setLyricsUrl] = useState('')
const [loading, setLoading] = useState(false)
const [error, setError] = useState('')


const submit = async (e) => {
e.preventDefault()
setError('')
setLoading(true)
try {
const resp = await fetch('/create_video', {
method: 'POST',
headers: { 'Content-Type': 'application/json' },
body: JSON.stringify({ image_url: imageUrl, audio_url: audioUrl, lyrics_url: lyricsUrl })
})
if (!resp.ok) {
const body = await resp.json()
throw new Error(body.error || 'Server error')
}
const blob = await resp.blob()
const url = URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
a.download = 'lyrics_video.mp4'
a.click()
URL.revokeObjectURL(url)
} catch (err) {
setError(err.message)
} finally {
setLoading(false)
}
}


return (
<div className="container">
<h1>Lyrics Video Generator</h1>
<form onSubmit={submit} className="form">
<label>Image URL (Dropbox link ok)</label>
<input value={imageUrl} onChange={e => setImageUrl(e.target.value)} placeholder="https://..." />


<label>Audio URL (Dropbox link ok)</label>
<input value={audioUrl} onChange={e => setAudioUrl(e.target.value)} placeholder="https://..." />


<label>Lyrics (SRT) URL (Dropbox link ok)</label>
<input value={lyricsUrl} onChange={e => setLyricsUrl(e.target.value)} placeholder="https://..." />


<button type="submit" disabled={loading}>{loading ? 'Rendering…' : 'Create Video'}</button>
</form>
{error && <div className="error">{error}</div>}
<p className="hint">If you deploy backend separately, change the frontend fetch URL to the full backend URL.</p>
</div>
)
}
