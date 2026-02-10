import React from 'react'


function AnimeCard({ anime, onAnimeClick }) {
  return (
    <article className="anime-card" onClick={() => onAnimeClick(anime)}>
      <figure>
        <img src={`assets/covers/${anime.Anime}.png`} alt={anime.Anime} />
      </figure>
      <h3>{anime.Anime}</h3>
    </article>
  )
}

export default AnimeCard