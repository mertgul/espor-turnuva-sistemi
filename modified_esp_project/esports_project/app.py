from flask import Flask, render_template, request, redirect, url_for, flash ,jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import os


app = Flask(__name__)
app.secret_key = 'secret_key_here'  # Secret key, session yönetimi için gerekli

login_manager = LoginManager()
login_manager.init_app(app)

# Veritabanı bağlantısı
def get_db_connection():
    conn = psycopg2.connect(
        dbname='esports_db',
        user='postgres',
        password='1245',
        host='localhost',
        port='5432',
    )
    return conn

class User(UserMixin):
    def __init__(self, user_id, team_id=None, is_admin=False):
        self.id = user_id
        self.team_id = team_id
        self.is_admin = is_admin  # Admin özelliğini burada tanımlıyoruz

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT player_id, team_id, is_admin FROM players WHERE player_id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user:
        return User(user_id=user[0], team_id=user[1], is_admin=user[2])  # Burada is_admin değerini de ekliyoruz
    return None


@app.route('/reports')
@login_required
def view_reports():
    # Raporları almak için gerekli işlemler
    return render_template('view_reports.html')

@app.route('/manage_content')
@login_required
def manage_content():
    # İçerik yönetimi işlemleri
    return render_template('manage_content.html')


# Kullanıcı Girişi
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT player_id, team_id, password FROM players WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[2], password):
            user_id, team_id = user[0], user[1]
            user_obj = User(user_id, team_id)
            login_user(user_obj)
            flash('Giriş başarılı!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# Kullanıcı Çıkışı
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Çıkış başarılı!', 'info')
    return redirect(url_for('login'))

# Anasayfa
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM tournaments')
    tournaments = cur.fetchall()

    # Her turnuva için katılımcıları çek
    tournament_list = []
    for tournament in tournaments:
        tournament_id = tournament[0]
        
        # Katılımcıları çek
        cur.execute('''
            SELECT t.team_name, p.name AS player_name
            FROM teams t
            LEFT JOIN players p ON t.team_id = p.team_id
            WHERE t.team_id IN (
                SELECT team_id FROM registrations WHERE tournament_id = %s
            )
        ''', (tournament_id,))
        participants = cur.fetchall()
        
        # Katılımcıları ve turnuva bilgilerini birleştirerek bir sözlük oluştur
        tournament_dict = {
            'id': tournament[0],
            'name': tournament[1],
            'game': tournament[2],
            'prize': tournament[3],
            'max_teams': tournament[4],
            'start_date': tournament[5],
            'participants': participants
        }
        tournament_list.append(tournament_dict)

    cur.close()
    conn.close()

    return render_template('index.html', tournaments=tournament_list)
@app.route('/tournament_bracket/<int:tournament_id>')
@login_required
def tournament_bracket(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Turnuvaya ait tüm maçları ve sonuçları alıyoruz
    cur.execute('''
        SELECT m.match_id, m.team1_id, m.team2_id, m.round_number, m.status,
               t1.team_name as team1_name, t2.team_name as team2_name,
               m.team1_score, m.team2_score
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.team_id
        JOIN teams t2 ON m.team2_id = t2.team_id
        WHERE m.tournament_id = %s
        ORDER BY m.round_number, m.match_id
    ''', (tournament_id,))

    matches = cur.fetchall()
    rounds = {}

    # Maçları turlara göre gruplayarak bir yapı oluşturuyoruz
    for match in matches:
        round_num = match[3]
        if round_num not in rounds:
            rounds[round_num] = []
        rounds[round_num].append({
            'team1_name': match[5],
            'team2_name': match[6],
            'status': match[4],
            'team1_score': match[7] if match[7] is not None else '',
            'team2_score': match[8] if match[8] is not None else '',
        })

    cur.close()
    conn.close()

    # Eğer maçlar varsa, braket gösterilecek
    if rounds:
        return render_template('tournament_bracket.html', tournament_id=tournament_id, rounds=rounds)
    else:
        flash('Bu turnuvada henüz maçlar oluşturulmamış.', 'warning')
        return redirect(url_for('index'))


@app.route('/tournament_participants/<int:tournament_id>')
@login_required
def tournament_participants(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Turnuvaya kayıtlı takımları al (Takım oyuncuları)
    cur.execute('''
        SELECT t.team_id, t.team_name, p.name as player_name
        FROM teams t
        LEFT JOIN players p ON t.team_id = p.team_id
        WHERE t.team_id IN (
            SELECT team_id FROM registrations WHERE tournament_id = %s
        )
    ''', (tournament_id,))
    team_participants = cur.fetchall()

    # Turnuvaya kayıtlı ve bireysel katılan oyuncuları al (Tek oyuncu katılımı)
    cur.execute('''
        SELECT p.name as player_name
        FROM players p
        LEFT JOIN registrations r ON p.team_id = r.team_id
        WHERE r.tournament_id = %s OR p.team_id IS NULL
    ''', (tournament_id,))
    individual_participants = cur.fetchall()

    cur.close()
    conn.close()

    # Turnuva bilgilerini almak
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name FROM tournaments WHERE tournament_id = %s', (tournament_id,))
    tournament = cur.fetchone()
    cur.close()
    conn.close()

    # Katılımcıları birleştiriyoruz
    participants = team_participants + individual_participants

    return render_template('tournament_participants.html', tournament=tournament[0], participants=participants)

@app.route('/create_team', methods=['GET', 'POST'])
@login_required
def create_team():
    conn = get_db_connection()
    cur = conn.cursor()

    # Tüm oyuncuları alıyoruz
    cur.execute('SELECT player_id, username FROM players WHERE team_id IS NULL')  # Hiçbir takıma katılmamış oyuncuları çekiyoruz
    players = cur.fetchall()
    conn.close()

    if request.method == 'POST':
        team_name = request.form['team_name']
        country = request.form['country']  # Ülke bilgisi
        selected_player_ids = request.form.getlist('player_ids')  # Seçilen oyuncuların idsini alıyoruz

        # En fazla 6 oyuncu eklenebilir
        if len(selected_player_ids) > 6:
            flash('Bir takım en fazla 6 oyuncu içerebilir!', 'error')
            return redirect(url_for('create_team'))  # Hata mesajı ile tekrar takım oluşturma sayfasına yönlendir

        # Takım oluştur ve takım_id'yi al
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO teams (team_name, country, status) VALUES (%s, %s, %s) RETURNING team_id', 
                    (team_name, country, 'pending'))  # Onay bekleyen takım
        team_id = cur.fetchone()[0]

        # Seçilen oyuncuları takıma ekle ve oyuncuların team_id'sini güncelle
        for player_id in selected_player_ids:
            # Player ID'nin players tablosunda mevcut olup olmadığını kontrol et
            cur.execute('SELECT player_id FROM players WHERE player_id = %s', (player_id,))
            player = cur.fetchone()

            if player:  # Eğer oyuncu varsa, takım oyuncusu olarak ekle
                cur.execute('INSERT INTO team_players (team_id, player_id) VALUES (%s, %s)', (team_id, player_id))
                cur.execute('UPDATE players SET team_id = %s WHERE player_id = %s', (team_id, player_id))  # Oyuncuların takım bilgilerini güncelliyoruz
            else:
                flash(f'Player with ID {player_id} does not exist!', 'error')

        # Takımın owner'ını (yaratıcısını) güncelle
        cur.execute('UPDATE players SET team_id = %s WHERE player_id = %s', (team_id, current_user.id))

        conn.commit()
        conn.close()

        flash('Takım başarıyla oluşturuldu ve oyuncular eklendi! Ancak admin onayı bekliyor.', 'success')
        return redirect(url_for('view_team'))  # Takım sayfasına yönlendir

    return render_template('create_team.html', players=players)


@app.route('/admin/approve_teams', methods=['GET', 'POST'])
@login_required
def approve_teams():
    # Admin kontrolü
    if not current_user.is_admin:
        flash('Bu sayfaya erişiminiz yok.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Onay bekleyen takımları alıyoruz
    cur.execute('SELECT team_id, team_name, country FROM teams WHERE status = %s', ('pending',))
    pending_teams = cur.fetchall()
    conn.close()

    return render_template('approve_teams.html', pending_teams=pending_teams)


@app.route('/admin/approve_team/<int:team_id>', methods=['POST'])
@login_required
def approve_team(team_id):
    # Admin kontrolü
    if not current_user.is_admin:
        flash('Bu sayfaya erişiminiz yok.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Takımın status bilgisini 'approved' olarak güncelliyoruz
    cur.execute('UPDATE teams SET status = %s WHERE team_id = %s', ('approved', team_id))
    conn.commit()
    conn.close()

    flash('Takım başarıyla onaylandı.', 'success')
    return redirect(url_for('approve_teams'))  # Admin onay sayfasına yönlendir





# Takım Güncelleme
@app.route('/update_team', methods=['GET', 'POST'])
@login_required
def update_team():
    if request.method == 'POST':
        new_team_name = request.form['team_name']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE teams SET team_name = %s WHERE player_id = %s', 
                    (new_team_name, current_user.id))
        conn.commit()
        conn.close()

        flash(f'Takım adı başarıyla güncellendi: {new_team_name}', 'success')
        return redirect(url_for('view_team'))

    return render_template('update_team.html')



# Turnuva Ekleme
@app.route('/add_tournament', methods=['GET', 'POST'])
@login_required
def add_tournament():
    conn = get_db_connection()
    cur = conn.cursor()
    # Oyun listesini çekiyoruz (dropdown için)
    cur.execute('SELECT game_id, name FROM games')
    games = cur.fetchall()

    if request.method == 'POST':
        name = request.form['name']
        game_id = request.form['game_id']  # artık oyun id'si geliyor
        prize = request.form['prize']
        max_teams = request.form['max_teams']
        start_date = request.form['start_date']

        cur.execute('''INSERT INTO tournaments (name, game_id, prize, max_teams, start_date)
                       VALUES (%s, %s, %s, %s, %s)''', 
                    (name, game_id, prize, max_teams, start_date))
        conn.commit()
        cur.close()
        conn.close()
        flash('Turnuva başarıyla eklendi!', 'success')
        return redirect(url_for('index'))

    cur.close()
    conn.close()
    return render_template('add_tournament.html', games=games)


@app.route('/register_tournament/<int:tournament_id>', methods=['POST'])
@login_required
def register_tournament(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'SELECT 1 FROM registrations WHERE player_id = %s AND tournament_id = %s',
            (current_user.id, tournament_id)
        )
        existing_registration = cur.fetchone()
        if existing_registration:
            flash('Zaten bu turnuvaya kayıtlısınız.', 'warning')
        else:
            cur.execute(
                'SELECT team_id FROM players WHERE player_id = %s',
                (current_user.id,)
            )
            player_team = cur.fetchone()
            team_id = player_team[0] if player_team else None
            cur.execute(
                'INSERT INTO registrations (player_id, team_id, tournament_id) VALUES (%s, %s, %s)',
                (current_user.id, team_id, tournament_id)
            )
            conn.commit()
            flash('Turnuvaya başarıyla katıldınız!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Bir hata oluştu: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/delete_tournament/<int:tournament_id>', methods=['POST'])
@login_required
def delete_tournament(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM tournaments WHERE tournament_id = %s', (tournament_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Turnuva başarıyla silindi!', 'danger')
    return redirect(url_for('index'))

# Kullanıcı Kaydı
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        # username ile name aynı olacak şekilde INSERT sorgusunu güncelliyoruz
        cur.execute('INSERT INTO players (username, name, email, password) VALUES (%s, %s, %s, %s)',
                    (username, username, email, hashed_password))  # name kolonu da username ile aynı
        conn.commit()
        conn.close()

        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    # Kullanıcı verilerini veritabanından al
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT username, email, password FROM players WHERE id = %s', (current_user.id,))
    user = cur.fetchone()
    conn.close()

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        new_password = request.form['password']

        # Şifreyi kontrol et: Eğer yeni şifre boşsa, mevcut şifreyi kullan
        if new_password:
            new_password_hash = generate_password_hash(new_password)
        else:
            # Yeni şifre girilmediyse, mevcut şifreyi olduğu gibi bırak
            new_password_hash = user[2]  # Mevcut şifreyi al (user[2] == mevcut şifre)

        # Veritabanında güncelleme işlemi
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE players SET username = %s, email = %s, password = %s WHERE id = %s',
                    (new_username, new_email, new_password_hash, current_user.id))
        conn.commit()
        conn.close()

        flash('Profiliniz başarıyla güncellendi!', 'success')
        return redirect(url_for('profile'))

    return render_template('update_profile.html', user=user)


@app.route('/profile')
@login_required
def profile():
    # Veritabanı bağlantısını sağlıyoruz
    conn = get_db_connection()
    cur = conn.cursor()

    # Kullanıcı bilgilerini alıyoruz
    cur.execute('SELECT username, email, team_id FROM players WHERE id = %s', (current_user.id,))
    user = cur.fetchone()

    # Veritabanı bağlantısını kapatıyoruz
    cur.close()
    conn.close()

    # Eğer kullanıcı bilgisi bulunmazsa, hata mesajı gösterebiliriz veya başka bir sayfaya yönlendirebiliriz
    if user is None:
        flash('User not found!', 'danger')
        return redirect(url_for('index'))  # Ana sayfaya yönlendirme

    # Profil sayfasını render ediyoruz ve kullanıcı bilgilerini şablona gönderiyoruz
    return render_template('profile.html', user=user)



# Turnuva Güncelleme
@app.route('/update_tournament/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
def update_tournament(tournament_id):
    # Admin olmayan kullanıcıları yönlendirme
    if not current_user.is_admin:
        flash("Bu işlemi yapmaya yetkiniz yok!", "danger")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # Formdan gelen güncel veriler
        name = request.form['name']
        game = request.form['game']
        prize = request.form['prize']
        max_teams = request.form['max_teams']
        start_date = request.form['start_date']

        # Veritabanında güncelleme yap
        cur.execute('''UPDATE tournaments
                       SET name = %s, game = %s, max_teams = %s, prize = %s, start_date = %s
                       WHERE tournament_id = %s''', 
                    (name, game, max_teams, prize, start_date, tournament_id))
        conn.commit()
        cur.close()
        conn.close()
        flash('Turnuva başarıyla güncellendi!', 'success')
        return redirect(url_for('index'))

    else:  # GET isteği ise
        # Turnuva bilgilerini veritabanından çek
        cur.execute('SELECT name, game, prize, max_teams, start_date FROM tournaments WHERE tournament_id = %s', (tournament_id,))
        tournament = cur.fetchone()
        cur.close()
        conn.close()

        # Veriyi formda göstermek için sözlük haline getir
        tournament_dict = {
            'name': tournament[0],
            'game': tournament[1],
            'prize': tournament[2],
            'max_teams': tournament[3],
            'start_date': tournament[4]
        }
        

        return render_template('update_tournament.html', tournament=tournament_dict)



@app.route('/admin/add_match', methods=['GET', 'POST'])
@login_required
def add_match():
    # Admin olmayan kullanıcıları yönlendir
    if not current_user.is_admin:
        return redirect(url_for('index'))  # Admin olmayan kullanıcıları anasayfaya yönlendir

    # Veritabanına bağlanıyoruz
    conn = get_db_connection()
    cur = conn.cursor()

    # Turnuva verilerini alıyoruz
    cur.execute('SELECT tournament_id, name FROM tournaments')
    tournaments = cur.fetchall()

    # Takım verilerini alıyoruz
    cur.execute('SELECT team_id, team_name FROM teams')
    teams = cur.fetchall()

    # Eğer form POST ile gönderildiyse
    if request.method == 'POST':
        try:
            # Form verilerini alıyoruz
            tournament_id = request.form['tournament_id']
            team1_id = request.form['team1_id']
            team2_id = request.form['team2_id']
            round_number = request.form['round_number']
            match_date = request.form['match_date']
            status = request.form['status']

            # Maçı veritabanına ekliyoruz
            cur.execute('''
                INSERT INTO matches (tournament_id, team1_id, team2_id, round_number, match_date, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (tournament_id, team1_id, team2_id, round_number, match_date, status))

            conn.commit()
            flash('Maç başarıyla eklendi!', 'success')
            return redirect(url_for('admin_dashboard'))  # Admin paneline geri yönlendirme

        except KeyError as e:
            flash(f"Formda eksik bir alan var: {e}", 'danger')

    cur.close()
    conn.close()

    # Turnuva ve takım verilerini formda göstermek için şablona gönderiyoruz
    return render_template('admin/add_match.html', tournaments=tournaments, teams=teams)



@app.route('/generate_matches/<int:tournament_id>', methods=['GET', 'POST'])
@login_required
def generate_matches(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Turnuva ile ilgili maçları çekme işlemi
    cur.execute(''' 
      SELECT 
        m.match_id,
        m.team1_id,
        m.team2_id,
        m.round_number,
        m.status,
        m.team1_score,
        m.team2_score,
        t1.team_name AS team1_name,
        t2.team_name AS team2_name
    FROM matches AS m
    JOIN teams AS t1 ON m.team1_id = t1.team_id
    JOIN teams AS t2 ON m.team2_id = t2.team_id
    WHERE m.tournament_id = %s
    ORDER BY m.round_number, m.match_id;
    ''', (tournament_id,))

    matches = cur.fetchall()
    rounds = {}

    # Maçları turlara göre gruplayarak bir yapı oluşturuyoruz
    for match in matches:
        round_num = match[3]
        if round_num not in rounds:
            rounds[round_num] = []
        rounds[round_num].append({
            'team1_name': match[7] if match[7] else 'Bilinmiyor',
            'team2_name': match[8] if match[8] else 'Bilinmiyor',
            'status': match[4],
            'team1_score': match[5] if match[5] is not None else '-',
            'team2_score': match[6] if match[6] is not None else '-',
        })

    cur.close()
    conn.close()

    # Şablonla veriyi render etme
    return render_template('generate_matches.html', tournament_id=tournament_id, rounds=rounds)


# ================== YÖNETİCİ PANELİ ===================

@app.route('/admin')
@login_required
def admin_dashboard():
    # Eğer kullanıcı admin değilse, erişimi kısıtla
    if not current_user.is_admin:
        flash("Bu sayfaya erişim yetkiniz yok!", "danger")
        return redirect(url_for('index'))

    return render_template('admin/dashboard.html')

@app.route('/admin/tournament/<int:tournament_id>/participants', methods=['GET', 'POST'])
@login_required
def manage_participants(tournament_id):
    # Admin olup olmadığını kontrol ediyoruz
    if not current_user.is_admin:
        return redirect(url_for('index'))  # Admin olmayan kullanıcıları anasayfaya yönlendir

    conn = get_db_connection()
    cur = conn.cursor()

    # Katılımcıları alıyoruz
    cur.execute('''
        SELECT r.player_id, p.username 
        FROM registrations r
        JOIN players p ON r.player_id = p.player_id
        WHERE r.tournament_id = %s
    ''', (tournament_id,))
    participants = cur.fetchall()

    # Yeni kullanıcıları sorgulama (turnuvaya kaydolmamış)
    cur.execute('''
        SELECT player_id, username
        FROM players
        WHERE player_id NOT IN (SELECT player_id FROM registrations WHERE tournament_id = %s)
    ''', (tournament_id,))
    new_users = cur.fetchall()  # Yeni kullanıcılar

    # Yeni katılımcı ekleme ve çıkarma işlemi
    if request.method == 'POST':
        action = request.form['action']
        player_id = request.form['player_id']

        if action == 'remove':
            # 'registrations' tablosundan sadece kullanıcıyı siliyoruz
            cur.execute('DELETE FROM registrations WHERE player_id = %s AND tournament_id = %s', 
                        (player_id, tournament_id))
            conn.commit()
            flash("Katılımcı başarıyla turnuvadan silindi.", 'success')
            return redirect(url_for('manage_participants', tournament_id=tournament_id))

        elif action == 'add':  # Yeni kullanıcıyı turnuvaya ekle
            cur.execute('INSERT INTO registrations (player_id, tournament_id) VALUES (%s, %s)', 
                        (player_id, tournament_id))
            conn.commit()
            flash("Kullanıcı başarıyla turnuvaya eklendi.", 'success')
            return redirect(url_for('manage_participants', tournament_id=tournament_id))

    cur.close()
    conn.close()

    return render_template('admin/manage_participants.html', tournament_id=tournament_id, 
                           participants=participants, new_users=new_users)



@app.route('/admin/tournament', methods=['GET'])
@login_required
def tournament_list():
    # Admin olup olmadığını kontrol ediyoruz
    if not current_user.is_admin:
        return redirect(url_for('index'))  # Admin olmayan kullanıcıları anasayfaya yönlendir

    conn = get_db_connection()
    cur = conn.cursor()

    # Tüm turnuvaları alıyoruz
    cur.execute('SELECT tournament_id, name FROM tournaments')
    tournaments = cur.fetchall()

    if not tournaments:
        flash('Veri bulunamadı.', 'danger')
    
    cur.close()
    conn.close()

    return render_template('tournament_list.html', tournaments=tournaments)






# Skor düzenleme
@app.route('/admin/match/<int:match_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_match_score(match_id):
    if current_user.is_admin:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        score1 = request.form['score1']
        score2 = request.form['score2']
        cur.execute('UPDATE matches SET team1_score = %s, team2_score = %s WHERE match_id = %s',
                    (score1, score2, match_id))
        conn.commit()
        flash("Skor güncellendi!", "success")
        return redirect(url_for('admin_dashboard'))

    cur.execute('SELECT * FROM matches WHERE match_id = %s', (match_id,))
    match = cur.fetchone()
    conn.close()
    return render_template('admin/edit_match.html', match=match)

#canlı maç skoru
@app.route('/live_score/<int:tournament_id>')
@login_required
def live_score(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).all()
    return render_template('live_score.html', tournament=tournament, matches=matches)

#Turnuva sonuçların
@app.route('/tournament_results/<int:tournament_id>')
@login_required
def tournament_results(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    matches = Match.query.filter_by(tournament_id=tournament_id).all()  # Varsayalım ki maçlar veritabanında tutuluyor
    return render_template('tournament_results.html', tournament=tournament, matches=matches)

#tüm takımları listeleme
@app.route('/manage_all_tournaments')
@login_required
def manage_all_tournaments():
    conn = get_db_connection()
    cur = conn.cursor()

    # Tüm turnuvaları alıyoruz
    cur.execute('SELECT tournament_id, tournament_name FROM tournaments')
    tournaments = cur.fetchall()
    
    conn.close()

    return render_template('manage_all_tournaments.html', tournaments=tournaments)



@app.route('/admin/participants', methods=['GET'])
@login_required
def participants():
    if not current_user.is_admin:
        return redirect(url_for('index'))  # Admin olmayan kullanıcıları yönlendir

    conn = get_db_connection()
    cur = conn.cursor()

    # Tüm turnuvaları alıyoruz
    cur.execute('SELECT tournament_id, name FROM tournaments')
    tournaments = cur.fetchall()

    # Eğer turnuva verisi yoksa, hata mesajı loglayın
    if not tournaments:
        print("Veritabanında turnuva bulunamadı!")

    # Seçilen turnuva ID'sini alıyoruz
    selected_tournament_id = request.args.get('tournament_id')

    # Seçilen turnuva varsa, o turnuvanın katılımcılarını alıyoruz
    if selected_tournament_id:
        cur.execute('''
            SELECT p.username
            FROM registrations r
            JOIN players p ON r.player_id = p.player_id
            WHERE r.tournament_id = %s
        ''', (selected_tournament_id,))
        participants = cur.fetchall()

        # Seçilen turnuva adını alıyoruz
        cur.execute('SELECT name FROM tournaments WHERE tournament_id = %s', (selected_tournament_id,))
        selected_tournament_name = cur.fetchone()[0]
    else:
        participants = []
        selected_tournament_name = ""

    return render_template('participants_list.html', tournaments=tournaments, participants=participants, 
                           selected_tournament_id=selected_tournament_id, selected_tournament_name=selected_tournament_name)




@app.route('/add_content', methods=['GET', 'POST'])
@login_required
def add_content():
    # Kullanıcının admin olup olmadığını kontrol et
    if not current_user.is_admin:
        flash('Bu sayfaya erişim izniniz yok.', 'danger')
        return redirect(url_for('manage_content'))  # Admin olmayan kullanıcıları yönlendir

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        status = request.form['status']

        # Veritabanı bağlantısı
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO content (title, category, status) VALUES (%s, %s, %s)', (title, category, status))
        conn.commit()
        conn.close()

        flash('İçerik başarıyla eklendi!', 'success')
        return redirect(url_for('manage_content'))  # İçerik yönetim sayfasına yönlendir

    return render_template('add_content.html')  # İçerik ekleme formunu göster


@app.route('/view_team')
@login_required
def view_team():
    # Veritabanı bağlantısını sağlıyoruz
    conn = get_db_connection()
    cur = conn.cursor()

    # Kullanıcının takım bilgilerini alıyoruz
    cur.execute('''
        SELECT t.team_id, t.team_name, t.created_at, p.username AS creator_name
        FROM teams t
        JOIN players p ON t.team_id = p.team_id
        WHERE t.team_id = %s AND p.player_id = %s -- Kullanıcı sadece kendi takımını görebilir
    ''', (current_user.team_id, current_user.id))

    team = cur.fetchone()  # Kullanıcının takım bilgilerini alıyoruz

    if team:
        # Takım üyelerini alıyoruz
        cur.execute('SELECT username, name FROM players WHERE team_id = %s', (current_user.team_id,))
        players = cur.fetchall()  # Takım üyelerini alıyoruz

        # Eğer oyuncular varsa, şablona gönderiyoruz
        if players:
            players_list = [{"username": player[0], "name": player[1]} for player in players]  # Listeyi daha kolay render etmek için
        else:
            players_list = []

        # Bağlantıyı kapatıyoruz
        cur.close()
        conn.close()

        # Takım bilgileri ve oyuncular ile birlikte view_team.html şablonunu render ediyoruz
        return render_template('view_team.html', team=team, players=players_list)
    else:
        # Eğer takım yoksa, uyarı mesajı gösteriyoruz
        flash('Henüz bir takımınız yok.', 'warning')
        cur.close()
        conn.close()

        # Takım bilgisi yoksa boş bir sayfa render ediyoruz
        return render_template('view_team.html', team=None, players=None)



#katıldığım turnuvalar
@app.route('/my_tournaments')
@login_required
def my_tournaments():
    # Kullanıcının katıldığı turnuvaları almak için veritabanı bağlantısı kuruyoruz
    conn = get_db_connection()
    cur = conn.cursor()

    # Kullanıcının katıldığı turnuvaları sorguluyoruz
    cur.execute('''
        SELECT t.tournament_id, t.name, t.start_date, t.max_teams
        FROM tournaments t
        JOIN registrations r ON t.tournament_id = r.tournament_id
        WHERE r.player_id = %s
    ''', (current_user.id,))

    tournaments = cur.fetchall()  # Kullanıcının katıldığı turnuvaları alıyoruz

    # Bağlantıyı kapatıyoruz
    cur.close()
    conn.close()

    # Turnuvalar varsa, şablona gönderiyoruz
    return render_template('my_tournaments.html', tournaments=tournaments)


@app.route('/submit_result/<int:tournament_id>', methods=['GET', 'POST'])
def submit_result(tournament_id):
    if request.method == 'POST':
        # Skorları, takım isimlerini ve itiraz nedenini alıyoruz
        team1_name = request.form['team1_name']
        team2_name = request.form['team2_name']
        score1 = request.form['score1']
        score2 = request.form['score2']
        objection_reason = request.form['objection_reason']
        
        # tournament_id burada gelen URL parametresinden alınır
        # match_id verisini ve tournament_id'yi veritabanına kaydediyoruz
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO match_results (tournament_id, team1_name, team2_name, score1, score2, objection_reason)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (tournament_id, team1_name, team2_name, score1, score2, objection_reason))
        conn.commit()
        cur.close()
        conn.close()

        flash('Sonuç başarıyla kaydedildi! Onay için adminin onayı bekleniyor.', 'success')
        return redirect(url_for('view_results', tournament_id=tournament_id))  # tournament_id kullanıldı

    return render_template('submit_result.html', tournament_id=tournament_id)

@app.route('/admin/approve_result', methods=['GET', 'POST'])
@login_required
def approve_results():
    # Admin kontrolü
    if not current_user.is_admin:
        flash("Yalnızca adminler bu sayfaya erişebilir!", "error")
        return redirect(url_for('home'))  # Admin olmayan kullanıcıları yönlendiriyoruz

    if request.method == 'POST':
        match_id = request.form['match_id']
        approve = request.form.get('approve')  # Onay verildi mi?

        # Skor onayı işlemi
        conn = get_db_connection()
        cur = conn.cursor()
        
        if approve == 'approve':
            cur.execute('''
                UPDATE match_results
                SET admin_approved = TRUE
                WHERE match_id = %s
            ''', (match_id,))
        else:
            cur.execute('''
                UPDATE match_results
                SET admin_approved = FALSE
                WHERE match_id = %s
            ''', (match_id,))
        
        conn.commit()
        cur.close()
        conn.close()

        flash('Skor onaylandı!', 'success')
        return redirect(url_for('approve_results'))  # Admin onay sonrası tekrar onay sayfasına yönlendir

    # Admin onayı yapılacak tüm maçları getiriyoruz
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM match_results WHERE admin_approved = FALSE')  # Onay bekleyenler
    results = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('approve_results.html', results=results)


@app.route('/view_results/<int:tournament_id>')
def view_results(tournament_id):
    # Veritabanından admin onayı verilmiş maç sonuçlarını almak
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''SELECT match_id, team1_name, team2_name, score1, score2, objection_reason 
                   FROM match_results WHERE tournament_id = %s AND admin_approved = TRUE''', (tournament_id,))
    results = cur.fetchall()  # Sadece admin onayı verilmiş maçları çekiyoruz
    cur.close()
    conn.close()

    # Eğer sonuç varsa, verileri şablona gönderiyoruz
    if results:
        results_list = []
        for result in results:
            # Veriyi kontrol edip şablona doğru gönderiyoruz
            if len(result) == 6:  # 6 sütun bekliyoruz
                results_list.append({
                    'match_id': result[0],  # 'id' yerine 'match_id' kullandık
                    'team1_name': result[1],
                    'team2_name': result[2],
                    'score1': result[3],
                    'score2': result[4],
                    'objection_reason': result[5]
                })
            else:
                # Bozuk veri kontrolü (eksik sütun varsa)
                print(f"Bozuk veri: {result}")

        # Veriler şablona gönderiliyor
        return render_template('view_results.html', results=results_list)
    
    # Sonuç yoksa hata mesajı veriliyor ve aynı sayfada kalınıyor
    flash("Onaylı sonuç bulunamadı", "error")
    return render_template('view_results.html', results=[])  # Sayfa aynı kalacak, boş sonuçlar gösterilecek

@app.route('/update_match', methods=['GET', 'POST'])
@login_required
def update_match():
    # Admin olup olmadığını kontrol ediyoruz
    if not current_user.is_admin:
        flash('Bu sayfaya erişim izniniz yok!', 'danger')
        return redirect(url_for('index'))  # Ana sayfaya yönlendirme

    conn = get_db_connection()
    cur = conn.cursor()

    # GET isteği ile tüm maçları veritabanından çekiyoruz
    if request.method == 'GET':
        cur.execute('''
            SELECT 
                m.match_id,
                m.team1_id,
                m.team2_id,
                m.round_number,
                m.status,
                m.team1_score,
                m.team2_score,
                t1.team_name AS team1_name,
                t2.team_name AS team2_name
            FROM matches AS m
            JOIN teams AS t1 ON m.team1_id = t1.team_id
            JOIN teams AS t2 ON m.team2_id = t2.team_id;
        ''')

        matches = cur.fetchall()
        cur.close()
        conn.close()

        return render_template('update_match_list.html', matches=matches)

    # POST isteği ile seçilen maçı güncelliyoruz
    if request.method == 'POST':
        match_id = request.form['match_id']  # Güncellenmek istenen maçın ID'si
        team1_score = request.form['team1_score']
        team2_score = request.form['team2_score']
        status = request.form['status']

        # Skorları ve durumu güncelliyoruz
        cur.execute('''
            UPDATE matches
            SET team1_score = %s, team2_score = %s, status = %s
            WHERE match_id = %s;
        ''', (team1_score, team2_score, status, match_id))

        conn.commit()
        cur.close()
        conn.close()

        flash('Maç başarıyla güncellendi!', 'success')
        return redirect(url_for('update_match'))  # Maçlar listesine geri yönlendiriyoruz
    

@app.route('/tournament_players/<int:tournament_id>', methods=['GET'])
@login_required
def tournament_players(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Turnuvaya katılan takımların oyuncularını alıyoruz
    cur.execute('''
        SELECT t.team_name, p.name AS player_name
        FROM teams t
        LEFT JOIN players p ON t.team_id = p.team_id
        WHERE t.team_id IN (
            SELECT team_id FROM registrations WHERE tournament_id = %s
        );
    ''', (tournament_id,))

    players = cur.fetchall()  # Katılımcı takımların oyuncuları

    cur.close()
    conn.close()

    # Katılımcıların listeleneceği sayfayı render ediyoruz
    return render_template('tournament_players.html', players=players)


@app.route('/edit_user', methods=['GET'])
@login_required
def edit_user():
    # Admin olup olmadığını kontrol ediyoruz
    if not current_user.is_admin:
        flash('Bu sayfaya erişim izniniz yok!', 'danger')
        return redirect(url_for('index'))  # Ana sayfaya yönlendirme

    conn = get_db_connection()
    cur = conn.cursor()

    # Tüm kullanıcıları veritabanından alıyoruz
    cur.execute('SELECT player_id, username, email, name, puan FROM players')
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('edit_user_list.html', users=users)


@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user_details(user_id):
    # Admin olup olmadığını kontrol ediyoruz
    if not current_user.is_admin:
        flash('Bu sayfaya erişim izniniz yok!', 'danger')
        return redirect(url_for('index'))  # Ana sayfaya yönlendirme

    conn = get_db_connection()
    cur = conn.cursor()

    # Seçilen kullanıcının verilerini alıyoruz (puan da dahil)
    cur.execute('''
        SELECT player_id, username, email, name, favorite_game, team_id, puan
        FROM players
        WHERE player_id = %s
    ''', (user_id,))
    user = cur.fetchone()

    # Eğer kullanıcı bulunamazsa hata mesajı veriyoruz
    if user is None:
        flash('Kullanıcı bulunamadı!', 'danger')
        return redirect(url_for('edit_user'))  # Kullanıcıları listeleme sayfasına yönlendiriyoruz

    if request.method == 'POST':
        # Formdan gelen veriyi alıyoruz
        username = request.form['username']
        email = request.form['email']
        name = request.form['name']
        team_id = request.form['team_id']
        favorite_game = request.form['favorite_game']
        puan = request.form['puan']  # Puanı alıyoruz

        # Kullanıcı bilgilerini güncelliyoruz
        cur.execute('''
            UPDATE players
            SET username = %s, email = %s, name = %s, favorite_game = %s, team_id = %s, puan = %s
            WHERE player_id = %s
        ''', (username, email, name, favorite_game, team_id, puan, user_id))

        conn.commit()
        flash('Kullanıcı başarıyla güncellendi!', 'success')

        cur.close()
        conn.close()

        return redirect(url_for('edit_user'))  # Kullanıcıları listeleme sayfasına yönlendiriyoruz

    cur.close()
    conn.close()

    # Kullanıcının bilgileriyle formu render ediyoruz
    return render_template('edit_user_form.html', user=user)


@app.route('/admin/approve_reward/<int:request_id>', methods=['POST'])
@login_required
def approve_reward(request_id):
    if not current_user.is_admin:  # Admin olup olmadığını kontrol ediyoruz
        flash('Bu işlemi yapma izniniz yok!', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Talebi alıyoruz
    cur.execute('SELECT * FROM reward_requests WHERE request_id = %s', (request_id,))
    reward_request = cur.fetchone()

    if reward_request:
        # Talep onaylanıyor
        cur.execute('UPDATE reward_requests SET approved = TRUE WHERE request_id = %s', (request_id,))
        
        # Talep onaylandığında, kullanıcı puanını düşürüyoruz
        cur.execute('SELECT * FROM players WHERE player_id = %s', (reward_request['player_id'],))
        player = cur.fetchone()

        # Ödül fiyatı
        cur.execute('SELECT * FROM rewards WHERE reward_id = %s', (reward_request['reward_id'],))
        reward = cur.fetchone()

        if player['puan'] >= reward['price']:
            new_puan = player['puan'] - reward['price']
            cur.execute('UPDATE players SET puan = %s WHERE player_id = %s', (new_puan, reward_request['player_id']))
            conn.commit()

            flash('Ödül başarıyla onaylandı ve puan düşürüldü!', 'success')
        else:
            flash('Yeterli puan yok!', 'danger')

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('admin_rewards'))  # Admin ödül talepleri sayfasına yönlendiriyoruz


@app.route('/admin/rewards', methods=['GET'])
@login_required
def admin_rewards():
    if not current_user.is_admin:
        flash('Bu sayfaya erişim izniniz yok!', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Onaylanmayı bekleyen ödül taleplerini alıyoruz
    cur.execute('''
        SELECT reward_requests.request_id, players.username, rewards.name, reward_requests.request_date
        FROM reward_requests
        JOIN players ON reward_requests.player_id = players.player_id
        JOIN rewards ON reward_requests.reward_id = rewards.reward_id
        WHERE reward_requests.approved = FALSE
    ''')
    pending_requests = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('admin_rewards.html', pending_requests=pending_requests)


@app.route('/rewards', methods=['GET', 'POST'])
@login_required
def rewards():
    conn = get_db_connection()
    cur = conn.cursor()

    # Tüm ödülleri alıyoruz
    cur.execute('SELECT * FROM rewards')
    rewards = cur.fetchall()

    # Kullanıcı bilgilerini (players tablosundan) alıyoruz
    cur.execute('SELECT * FROM players WHERE player_id = %s', (current_user.id,))
    player = cur.fetchone()

    # POST isteği ile ödül talebi yapılmışsa
    if request.method == 'POST':
        reward_id = request.form['reward_id']
        reward_price = int(request.form['reward_price'])

        # Kullanıcının yeterli puanı var mı?
        if player['puan'] >= reward_price:
            # Kullanıcının puanını güncelliyoruz
            new_puan = player['puan'] - reward_price
            cur.execute('UPDATE players SET puan = %s WHERE player_id = %s', (new_puan, current_user.id))

            # Ödül talebini kaydediyoruz
            cur.execute('INSERT INTO reward_requests (player_id, reward_id, approved) VALUES (%s, %s, %s)', 
                        (current_user.id, reward_id, False))  # Başlangıçta onaylanmamış
            conn.commit()

            flash('Ödül başarıyla talep edildi, admin onayı bekleniyor.', 'success')
        else:
            flash('Yeterli puanınız yok!', 'danger')

    cur.close()
    conn.close()

    return render_template('rewards.html', rewards=rewards, player=player)





@app.route('/admin/add_reward', methods=['GET', 'POST'])
@login_required
def add_reward():
    if not current_user.is_admin:  # Admin olup olmadığını kontrol ediyoruz
        flash('Bu sayfaya erişim izniniz yok!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Formdan gelen verileri alıyoruz
        reward_name = request.form['name']
        reward_description = request.form['description']
        reward_price = int(request.form['price'])

        # Veritabanına yeni ödül ekliyoruz
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO rewards (name, description, price)
            VALUES (%s, %s, %s)
        ''', (reward_name, reward_description, reward_price))
        conn.commit()
        cur.close()
        conn.close()

        flash('Ödül başarıyla eklendi!', 'success')
        return redirect(url_for('admin_rewards'))  # Admin ödüller sayfasına yönlendiriyoruz

    return render_template('add_reward.html')  # Ödül ekleme formunu render ediyoruz


@app.route('/turnuva/<int:tournament_id>')
def tournament_detail(tournament_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Turnuva bilgilerini al
    cur.execute('SELECT name, start_date, prize, max_teams FROM tournaments WHERE tournament_id = %s', (tournament_id,))
    tournament = cur.fetchone()

    # Katılımcılar
    cur.execute('''SELECT p.username FROM players p
                   JOIN registrations r ON p.player_id = r.player_id
                   WHERE r.tournament_id = %s''', (tournament_id,))
    participants = cur.fetchall()

    # Maç bilgileri (braket için)
    cur.execute('''SELECT m.match_id, t1.team_name, t2.team_name, m.team1_score, m.team2_score
                   FROM matches m
                   JOIN teams t1 ON m.team1_id = t1.team_id
                   JOIN teams t2 ON m.team2_id = t2.team_id
                   WHERE m.tournament_id = %s''', (tournament_id,))
    matches = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('tournament_detail.html', tournament=tournament, participants=participants, matches=matches)

@app.route('/oyunlar')
def oyunlar():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT game_id, name, image_url FROM games ORDER BY name')
    games = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('oyunlar.html', games=games)


@app.route('/turnuvalar')
def tournaments():
    game_id = request.args.get('game_id')
    conn = get_db_connection()
    cur = conn.cursor()
    if game_id:
        cur.execute('''
            SELECT t.tournament_id, t.name, g.name
            FROM tournaments t
            JOIN games g ON t.game_id = g.game_id
            WHERE t.game_id = %s
            ORDER BY t.start_date DESC
        ''', (game_id,))
    else:
        cur.execute('''
            SELECT t.tournament_id, t.name, g.name
            FROM tournaments t
            JOIN games g ON t.game_id = g.game_id
            ORDER BY t.start_date DESC
        ''')
    tournaments = cur.fetchall()
    cur.execute('SELECT game_id, name FROM games ORDER BY name')
    games = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('turnuvalar.html', tournaments=tournaments, games=games, selected_game=game_id)

@app.route('/admin/games', methods=['GET', 'POST'])
@login_required
def admin_games():
    if not current_user.is_admin:
        flash('Yalnızca adminler bu sayfaya erişebilir.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    # POST İsteği ile oyun ekleme, düzenleme veya silme
    if request.method == 'POST':
        action = request.form.get('action')

        # Oyun ekleme
        if action == 'add':
            name = request.form.get('name')
            image_url = request.form.get('image_url')
            if not name:
                flash('Oyun adı boş olamaz.', 'danger')
            else:
                cur.execute('INSERT INTO games (name, image_url) VALUES (%s, %s)', (name, image_url))
                conn.commit()
                flash(f'Oyun "{name}" başarıyla eklendi.', 'success')
            return redirect(url_for('admin_games'))

        # Oyun düzenleme
        elif action == 'edit':
            game_id = request.form.get('game_id')
            name = request.form.get('name')
            image_url = request.form.get('image_url')

            # Eğer game_id boşsa, işlem yapılmasın
            if not game_id:
                flash('Geçersiz oyun ID', 'danger')
                return redirect(url_for('admin_games'))

            if not name:
                flash('Oyun adı boş olamaz.', 'danger')
            else:
                cur.execute('UPDATE games SET name=%s, image_url=%s WHERE game_id=%s', (name, image_url, game_id))
                conn.commit()
                flash(f'Oyun "{name}" başarıyla güncellendi.', 'success')
            return redirect(url_for('admin_games'))

        # Oyun silme
        elif action == 'delete':
            game_id = request.form.get('game_id')

            # Eğer game_id boşsa, işlem yapılmasın
            if not game_id:
                flash('Geçersiz oyun ID', 'danger')
                return redirect(url_for('admin_games'))

            cur.execute('DELETE FROM games WHERE game_id=%s', (game_id,))
            conn.commit()
            flash('Oyun başarıyla silindi.', 'success')
            return redirect(url_for('admin_games'))

    # GET İsteği ile oyunları çekme
    cur.execute('SELECT game_id, name, image_url FROM games ORDER BY name')
    games = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('admin_games.html', games=games)



@app.route('/oyunlar/<string:game_name>')
def tournaments_by_game(game_name):
    game_name = game_name.replace('-', ' ')  # URL uyumluluğu için
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT t.tournament_id, t.name, t.start_date, t.prize
        FROM tournaments t
        JOIN games g ON t.game_id = g.game_id
        WHERE LOWER(g.name) = LOWER(%s)
        ORDER BY t.start_date DESC
    ''', (game_name,))
    tournaments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('turnuvalar.html', tournaments=tournaments, game_name=game_name.title())



if __name__ == '__main__':
    app.run(debug=True)
