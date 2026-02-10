import React from 'react'

export default function Sidebar({topAnime}) {
  return (
    <aside>
        <nav>
            <h3>Top Anime</h3>
            {topAnime.map(anime =>(
                <a href='#' target='_blank' key={anime.Anime} rel="noreferrer">
                    {anime.Anime}
                </a>
            ))}
            
        </nav>
    </aside>
  )
}