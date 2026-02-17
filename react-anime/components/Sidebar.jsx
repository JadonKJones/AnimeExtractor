import React from 'react'

export default function Sidebar({topAnime}) {
  return (
    <aside>
        <nav>
            <h3>Easiest Anime</h3>
            {topAnime.map(anime =>(
                <a href={`anki/${anime.Anime}_Master.apkg`} target='_blank' key={anime.Anime} rel="noreferrer">
                    {anime.Anime}
                </a>
            ))}
            
        </nav>
    </aside>
  )
}