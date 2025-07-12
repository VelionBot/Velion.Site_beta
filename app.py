from flask import Flask, redirect, request, session, render_template, url_for
from threading import Thread
import requests, json, os

# Импорт Discord-бота
from bot import start_bot

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# OAuth2 настройки
CLIENT_ID = '1392912652916887602'
CLIENT_SECRET = 'fcN21ynvpkLTqQ2bnbl9Z-jnodehw1V3'
REDIRECT_URI = 'https://velion-site-beta.onrender.com/callback'  # Укажи домен Render
BOT_ID = '1392912652916887602'

# === Flask routes ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/discord-login')
def discord_login():
    return redirect(get_discord_oauth_url())

def get_discord_oauth_url():
    return (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))

    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': 'identify guilds'
    }

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    token_response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)

    if token_response.status_code != 200:
        return f"OAuth Token Error: {token_response.text}", 400

    token_data = token_response.json()
    access_token = token_data.get('access_token')

    user_response = requests.get(
        'https://discord.com/api/users/@me',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    user_data = user_response.json()

    session['user'] = {
        'username': user_data.get('username'),
        'discriminator': user_data.get('discriminator'),
        'id': user_data.get('id'),
        'avatar': user_data.get('avatar')
    }
    session['discord_token'] = {
        'access_token': access_token
    }

    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))

    access_token = session['discord_token']['access_token']
    user = session['user']

    # Получаем сервера
    guilds = get_user_guilds(access_token)

    bank_data = None
    user_data = None

    if os.path.exists('users_data.json'):
        with open('users_data.json', 'r', encoding='utf-8') as f:
            users_data = json.load(f)
            user_data = users_data.get(user['id'])

    if os.path.exists('bank.json'):
        with open('bank.json', 'r', encoding='utf-8') as f:
            bank_users = json.load(f)
            bank_data = bank_users.get(user['id'])

    return render_template('dashboard.html', user=user, servers=guilds, bank_data=bank_data, users_data=users_data)

def get_user_guilds(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)
    if r.status_code != 200:
        return []
    guilds = r.json()
    return [{
        'id': g['id'],
        'name': g['name'],
        'icon_url': f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get('icon') else None
    } for g in guilds if int(g.get("permissions", 0)) & 0x20]

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# === Запуск сайта и бота одновременно ===
port = int(os.environ.get("PORT", 5000))  # Render сам задаёт PORT
app.run(host="0.0.0.0", port=port)

app = Flask(__name__, static_folder='imgs')

if __name__ == '__main__':
    Thread(target=run_flask).start()
    start_bot()  # импортируй и запускай бота из bot.py
