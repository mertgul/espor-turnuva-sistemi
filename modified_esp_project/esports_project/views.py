from flask import Blueprint, render_template
from models import Tournament

main_blueprint = Blueprint('main', __name__)

@main_blueprint.route('/')
def index():
    tournaments = Tournament.query.all()
    return render_template('index.html', tournaments=tournaments)

from flask import render_template
from flask_login import login_required

# Admin Panel Route
@app.route('/admin')
@login_required
def admin_panel():
    return render_template('admin_panel.html')

@app.route('/admin/tournaments')
@login_required
def tournaments():
    tournaments = Tournament.query.all()  # Replace with actual model data
    return render_template('tournaments.html', tournaments=tournaments)

@app.route('/tournament_bracket/<int:tournament_id>')
@login_required
def tournament_bracket(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Get all matches for the given tournament
    cur.execute(''' 
        SELECT m.match_id, m.team1_id, m.team2_id, m.round_number, m.status, t1.team_name as team1_name, t2.team_name as team2_name
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.team_id
        JOIN teams t2 ON m.team2_id = t2.team_id
        WHERE m.tournament_id = %s
        ORDER BY m.round_number, m.match_id
    ''', (tournament_id,))
    matches = cur.fetchall()
    rounds = {}
    for match in matches:
        round_num = match[3]
        if round_num not in rounds:
            rounds[round_num] = []
        rounds[round_num].append(match)
    
    cur.close()
    conn.close()

    return render_template('tournament_bracket.html', tournament_id=tournament_id, rounds=rounds)
