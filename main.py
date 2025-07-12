from flask import Flask, redirect, request, session, render_template, url_for
import requests
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # 🔐 В проде задавай через переменные окружения

CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
app.secret_key = os.getenv('SECRET_KEY')



def get_user_guilds(access_token, bot_id):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get("https://discord.com/api/users/@me/guilds", headers=headers)

    if response.status_code == 200:
        guilds = response.json()
        result = []
        for g in guilds:
            # Показываем только сервера, где у пользователя есть права управлять сервером
            if int(g.get("permissions", 0)) & 0x20:
                icon_url = f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g.get('icon') else None
                result.append({
                    "id": g['id'],
                    "name": g['name'],
                    "icon_url": icon_url,
                    "members_count": "-",  # Можно будет расширить при необходимости
                })
        return result
    else:
        print("Ошибка при получении гильдий:", response.status_code, response.text)
        return []


@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login')
def login():
    discord_oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return redirect(discord_oauth_url)


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

    if not access_token:
        return 'OAuth Error: No access token returned', 400

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

    access_token = session.get('discord_token', {}).get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    user = session['user']
    servers = get_user_guilds(access_token, BOT_ID)

    return render_template('dashboard.html', user=user, servers=servers)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
