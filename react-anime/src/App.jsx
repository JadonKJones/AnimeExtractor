import { useState, useEffect } from 'react'
import '../assets/scss/main.css'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'
import MainContent from '../components/MainContent'


const modules = import.meta.glob('./stats/*.json', { eager: true });
const allDataArray = Object.values(modules).map(m => m.default || m);

function App() {
  const [animeList, setAnimeList] = useState(allDataArray); 
  const [topAnime, setTopAnime] = useState([]);
  const [search, setSearch] = useState(""); 
  const [selectedAnime, setSelectedAnime] = useState(null);

  useEffect(() => {
    const sortedTop = [...allDataArray]
      .sort((a, b) => (b.Perceived_Difficulty_Weighted || 0) - (a.Perceived_Difficulty_Weighted || 0))
      .slice(0, 5);
    setTopAnime(sortedTop);
  }, []);

  const HandleSearch = (e) => {
    if (e) e.preventDefault();
    setSelectedAnime(null); 
    if (search.trim() === "") {
      setAnimeList(allDataArray);
    } else {
      const filtered = allDataArray.filter((anime) =>
        (anime.Anime || "").toLowerCase().includes(search.toLowerCase())
      );
      setAnimeList(filtered);
    }
  };

  return (
    <div className="App">
      <Header />
      <div className="content-wrap">
        <Sidebar topAnime={topAnime} onAnimeClick={(anime) => setSelectedAnime(anime)} />
        <main>
          {selectedAnime ? (
            <div className="anime-details-view">
              <button className="back-btn" onClick={() => setSelectedAnime(null)}>
                ← Back to Results
              </button>
              
              <div className="details-card">
                <img 
                  src={`assets/covers/${selectedAnime.Anime}.png`} 
                  alt={selectedAnime.Anime} 
                  onError={(e) => { e.target.src = 'assets/covers/default.png'; }}
                />
                <div className="details-info">
                  <h1>{selectedAnime.Anime}</h1>
                  <p><strong>Length:</strong> {selectedAnime.Length_total_words.toLocaleString()}</p>
                  <p><strong>Unique Words:</strong> {selectedAnime.Unique_words_dictionary_size.toLocaleString()}</p>
                  <p><strong>Unique Kanji:</strong> {selectedAnime.Unique_kanji}</p>
                  <p><strong>Average Difficulty:</strong> {selectedAnime.Perceived_Difficulty_Weighted}</p>
                  
                  <a 
                    href={`/anki/${selectedAnime.Anime}_Master.apkg`} 
                    download 
                    className="download-button"
                  >
                    Download Anki Deck
                  </a>
                </div>
              </div>

              <div className="visuals-section">
                <h3>Vocabulary Analysis</h3>
                <div className="graph-container">
                    <img src={`/graphs/${selectedAnime.Anime}_level_dist_bar.png`} alt="JLPT Levels" />
                    <img src={`/graphs/${selectedAnime.Anime}_core_coverage_pie.png`} alt="Core Coverage" />
                </div>
              </div>
            </div>
          ) : (
            <MainContent 
              HandleSearch={HandleSearch} 
              search={search} 
              SetSearch={setSearch} 
              animeList={animeList}
              onAnimeClick={(anime) => setSelectedAnime(anime)} 
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;