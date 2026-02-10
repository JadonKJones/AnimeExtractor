import React from 'react'

function AnimeDetails({ anime, onBack }) {
  return (
    <div className="anime-details">
      <button onClick={onBack} className="back-btn">← Back to List</button>
      
      <div className="details-content">
        <img src={`/assets/covers/${anime.Anime}.png`} alt={anime.Anime} />
        
        <div className="info">
          <h1>{anime.Anime}</h1>
          <p><strong>Length:</strong> {anime.Length_total_words}</p>
          <p><strong>Description:</strong> {anime.synopsis || "No description available."}</p>
          
          {/* Download Button */}
          <a 
            href={`/downloads/${anime.Anime}.zip`} 
            download 
            className="download-btn"
          >
            Download Assets
          </a>
        </div>
      </div>
    </div>
  )
}

export default AnimeDetails