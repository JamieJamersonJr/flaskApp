from flask import *
import sqlite3 as sql3
import helperFunctions.helper as helper
import argon2 as ar2
from datetime import datetime, timedelta
import time
from functools import wraps

app = Flask(__name__)
app.secret_key = b'VerySecureSecretYes'
# app.config['TESSERACT_PATH'] = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
app.config['SESSION_DURATION'] = seconds=1800
DATABASE = 'database/database.db'

def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value)
                for idx, value in enumerate(row))

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sql3.connect(DATABASE)
    db.row_factory = make_dicts
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if validate_session()['response']:
            print(f"Session message: {validate_session()['message']}")
            return func(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrapper


@app.route("/", methods=['GET', 'POST'])
@login_required
def home():
    return redirect('dashboard')
# def post_test():
#     if request.method == "POST":
#         file = request.files['file']

#         savedFileName = f"uploadedFiles/{file.filename}"
#         file.save(savedFileName)
#         import fitz  # PyMuPDF
#         from PIL import Image
#         import pytesseract
#         pytesseract.pytesseract.tesseract_cmd = app.config['TESSERACT_PATH'] 

#         def pdf_to_text(pdf_path):
#             doc = fitz.open(pdf_path)
#             text = ""
            
#             for page_num in range(doc.page_count):
#                 page = doc[page_num]
#                 pix = page.get_pixmap()
                
#                 # Convert the pixmap to a PIL Image
#                 img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                
#                 # Use Tesseract OCR to extract text from the image
#                 page_text = pytesseract.image_to_string(img, lang='ita+eng')
                
#                 # Append the extracted text to the result
#                 text += page_text

#             doc.close()
#             return text

#         pdf_path = savedFileName
#         result_text = pdf_to_text(pdf_path)


#         return result_text
#     else:
#         return render_template('read_pdf.html')
    
@app.route("/dashboard", methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == "POST":
        import csv
        with open('database/database.csv', 'a', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter='\n')
            newEntry = {'y': request.form["newMean"], 'x': time()}
            # writer.writerow([f'{{y:{request.form["newMean"]},x:{time()}}},'])
            writer.writerow([ str(newEntry) ])
            
        return render_template('dashboard.html', addedMean = request.form['newMean'], data=helper.readCSV('database/database.csv'))
    else:

        return render_template('dashboard.html')

@app.route("/graph", methods=['GET', 'POST'])
def graph():
    return render_template('graph.html')


def check_login(username, password):
    if " " in username:
        return {'message':f'Usernames may not contain spaces', 'success':False}
    
    cur = get_db().cursor()
    cur.execute(f'select username, password_hash from Users where username = "{username}"')
    user = [user for user in cur]
    if len(user) <= 0:
        return {'message':f'User {username} not found', 'success':False}
    
    ph = ar2.PasswordHasher()
    hash = user[0]['password_hash']
    try:
        if ph.verify(hash, password):
            if ph.check_needs_rehash(hash):
                cur.execute(f'replace into Users (username, password_hash) values ("{username}", "{ph.hash(password)}")')
            return {'message':f'Logged in as {username}', 'success':True}
        else:
            return {'message':'Incorrect username or password', 'success':False}
    except ar2.exceptions.VerifyMismatchError:
        return {'message':'Incorrect username or password', 'success':False}
    except:
        return {'message':'Login failed', 'success':False}

def add_login_log(username):
    login_timestamp =  time.time()
    ph = ar2.PasswordHasher()
    login_hash = ph.hash(f"{login_timestamp}{username}")
    cur = get_db().cursor()
    cur.execute(f'INSERT INTO Logins (login_hash, login_date, username) VALUES ("{login_hash}","{login_timestamp}","{username}")')
    get_db().commit()
    session['auth_token'] = login_hash
    # session.permanent = True

def validate_session():
    cur = get_db().cursor()
    token = session.get('auth_token')
    if token != None:
        cur.execute(f'SELECT login_date FROM Logins WHERE login_hash = "{session["auth_token"]}"')
        login_date = [row for row in cur]
        print(login_date)
        if len(login_date) == 1:
            print((time.time() - login_date[0]['login_date']))
            if (time.time() - login_date[0]['login_date']) < app.config['SESSION_DURATION']:
                return {'message':'Session Valid', 'response': True}
        return {'message':'Session Timed Out', 'response': False}
    else:
        return {'message':'User not logged in', 'response': False}


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        check = check_login(username, password)
        if check['success']:
            add_login_log(username)
            flash(check['message'])
            response = make_response(render_template('login_landing.html', user = request.cookies.get('current_user')))
            # response.set_cookie('current_user', username, expires = helper.createExpiryDate())
            # response.set_cookie('logged_in', 'true', expires = helper.createExpiryDate())
            return response
        else:
            response = make_response(render_template('login_landing.html'))
            return response
        

    return render_template('login_template.html')



@app.route("/admin", methods=['GET', 'POST'], strict_slashes=False)
def admin():
    
    return 'TODO'


@app.route("/admin/register", methods=['GET', 'POST'])
def add_user():
    cur = get_db().cursor()
    users = []
    cur.execute('SELECT * FROM Users')
    for row in cur:
        users.append(row)

    if request.method == 'POST':
        if request.form['password'] != request.form['confirm_password']:
            return render_template('register_user.html', activeUsers = users, error = "Password and confermation do not match, please re-enter password")
        username = request.form['username']
        ph = ar2.PasswordHasher()
        hashed_password = ph.hash(request.form['password'])
        
        cur.execute(f"INSERT INTO Users (username, password_hash) VALUES (\"{username}\", \"{hashed_password}\")")
        get_db().commit()

    return render_template('register_user.html', activeUsers = users)



#DEBUG STUFF REMOVE WHEN DONE
@app.route("/DEBUG", methods=['GET', 'POST'])
def _debug_db_query():
    if request.method == 'POST':
        cur = get_db().cursor()
        result = cur.execute(request.form['query'])
        if request.form.get('commit'):
            get_db().commit()
        return f"<form method='post'> Query: <input type='text' name='query'> Commit: <input type='checkbox' name='commit'> <input type='submit'> </form> {[row for row in result]}"
    return """<form method="post"> Query: <input type="text" name="query"> Commit: <input type='checkbox' name='commit'> <input type="submit"> </form>"""