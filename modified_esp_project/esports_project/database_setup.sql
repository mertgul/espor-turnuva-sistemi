
-- 1. Teams Tablosu
CREATE TABLE Teams (
    team_id SERIAL PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    country VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Players Tablosu
CREATE TABLE Players (
    player_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    age INT CHECK (age >= 12),
    team_id INT,
    CONSTRAINT fk_team FOREIGN KEY (team_id) REFERENCES Teams(team_id) ON DELETE RESTRICT
);

-- 3. Tournaments Tablosu
CREATE TABLE Tournaments (
    tournament_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    game VARCHAR(50),
    max_teams INT,
    start_date DATE
);

-- 4. Matches Tablosu
CREATE TABLE Matches (
    match_id SERIAL PRIMARY KEY,
    tournament_id INT NOT NULL,
    team1_id INT NOT NULL,
    team2_id INT NOT NULL,
    score_team1 INT DEFAULT 0,
    score_team2 INT DEFAULT 0,
    match_date DATE,
    CONSTRAINT fk_tournament FOREIGN KEY (tournament_id) REFERENCES Tournaments(tournament_id) ON DELETE CASCADE,
    CONSTRAINT fk_team1 FOREIGN KEY (team1_id) REFERENCES Teams(team_id),
    CONSTRAINT fk_team2 FOREIGN KEY (team2_id) REFERENCES Teams(team_id)
);
