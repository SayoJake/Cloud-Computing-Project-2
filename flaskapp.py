from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import os
import secrets

app = Flask(__name__)

# Configure secret key for session management
app.secret_key = secrets.token_hex(16)

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = '/var/www/flaskapp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max upload size: 16MB

ALLOWED_EXTENSIONS = {'txt'}

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

DATABASE = '/var/www/flaskapp/users.db'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_sqlite_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    firstname TEXT,
                    lastname TEXT,
                    email TEXT,
                    word_count INTEGER,
                    filename TEXT
                )''')
    conn.commit()
    conn.close()

def add_columns():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN word_count INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        c.execute("ALTER TABLE users ADD COLUMN filename TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()

# Initialize the database and ensure columns exist
init_sqlite_db()
add_columns()

@app.route('/')
def index():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    firstname = request.form['firstname']
    lastname = request.form['lastname']
    email = request.form['email']

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, firstname, lastname, email) VALUES (?, ?, ?, ?, ?)",
                  (username, password, firstname, lastname, email))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Username already exists."
    conn.close()

    # Automatically log the user in after registration
    session['username'] = username

    return redirect(url_for('profile', username=username))

@app.route('/profile/<username>')
def profile(username):
    # Ensure the user is logged in
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT firstname, lastname, email, word_count, filename FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()

    if user:
        firstname, lastname, email, word_count, filename = user
        return render_template('profile.html',
                               firstname=firstname,
                               lastname=lastname,
                               email=email,
                               word_count=word_count,
                               filename=filename)
    else:
        return "User not found."

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT firstname, lastname, email FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['username'] = username
            return redirect(url_for('profile', username=username))
        else:
            return "Invalid username or password."
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload():
    # Check if the user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if 'file' not in request.files:
        return "No file part."
    file = request.files['file']

    if file.filename == '':
        return "No selected file."

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Count the words in the file
        with open(filepath, 'r') as f:
            content = f.read()
            word_count = len(content.split())

        # Store word count and filename in the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("UPDATE users SET word_count=?, filename=? WHERE username=?", (word_count, filename, username))
        conn.commit()
        conn.close()

        return redirect(url_for('profile', username=username))
    else:
        return "Invalid file type. Only .txt files are allowed."

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Remove the app.run() block as we're using mod_wsgi
# if __name__ == '__main__':
#     app.run()

