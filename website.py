from flask import request, session, g, render_template, Blueprint, redirect, url_for, current_app, send_file, flash
from datetime import datetime

import sqlite3
import random
import os
import math
import uuid
import hmac

import config
from i18n import t, current_lang, current_country, country_info

website = Blueprint('website', __name__)

# app = Blueprint('website', __name__)
# # app = Flask(__name__)

# # app.secret_key = '12345678'
# app.secret_key = os.urandom(24)


############ SESSION ############
# active_sessions = []

# def start_session():
#     # Create a new session object
#     session = {
#         'db_name': 'my-database-user.db',
#         'last_activity': time.time()
#     }
#     # Add the session to the list of active sessions
#     active_sessions.append(session)

# def handle_request(session):
#     # Update the last activity time for the session
#     session['last_activity'] = time.time()
#     # Handle the request for the session


############ COPY USER DATA TO FULL DATABASE ############

def copy_data_to_fdb(src_db_name, table_name):
    """Append one table of a player's database to the collected database (fdb.db).

    The table is created in fdb.db when it does not exist yet, and columns that were
    added to the game later (e.g. country, language) are added to fdb.db automatically.
    """
    print("PRINT: source file is ", src_db_name)

    if not os.path.exists(src_db_name):
        print(f"Source database file {src_db_name} does not exist.")
        return

    src_db = sqlite3.connect(src_db_name)
    row = src_db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    if row is None:
        print(f"Source table {table_name} does not exist in {src_db_name}.")
        src_db.close()
        return
    create_sql = row[0]
    src_columns = [(c[1], c[2]) for c in src_db.execute(f'PRAGMA table_info({table_name})')]
    src_db.close()

    fdb = sqlite3.connect(config.FDB_PATH)

    # Create the table or add missing columns
    if fdb.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone() is None:
        fdb.execute(create_sql)
    fdb_columns = {c[1] for c in fdb.execute(f'PRAGMA table_info({table_name})')}
    for name, ctype in src_columns:
        if name not in fdb_columns:
            fdb.execute(f'ALTER TABLE {table_name} ADD COLUMN {name} {ctype}')
    fdb.commit()

    # Copy all columns except 'uroundid' (fdb numbers its own rows)
    columns = ', '.join(name for name, _ in src_columns if name != 'uroundid')
    fdb.execute('ATTACH DATABASE ? AS temp_db', (src_db_name,))
    fdb.execute(f'INSERT INTO {table_name}({columns}) SELECT {columns} FROM temp_db.{table_name}')
    fdb.commit()
    fdb.execute('DETACH DATABASE temp_db')
    fdb.close()

    print("PRINT: table transfer finalized")


def has_game():
    """True when this browser session has a running game (its database still exists)."""
    db_name = session.get('db_name')
    return bool(db_name) and os.path.exists(db_name)


############ CONNECT TO THE DATABASE ############

def get_db():
    db_name = session.get('db_name')
    print("PRINT: get_db uses ", db_name)
    if 'db' not in g:
        g.db = sqlite3.connect(db_name)
        g.db.row_factory = sqlite3.Row
    return g.db


############ MAKE DATASET AND TABLES ############
# These functions are called on index.html

def create_table():
    with current_app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS workforce (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gender INTEGER,
                    age INTEGER,
                    origin INTEGER,
                    paylevel INTEGER,
                    member INTEGER,
                    jobcat INTEGER
                )
            """)
        conn.commit()

    return 'Table created successfully'

def populate_table():
    with current_app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        for gender in range(1, 3):
                for age in range(1, 4):
                    for origin in range(1, 3):
                        for paylevel in range(1, 4):
                            for member in range(1, 3):
                                for jobcat in range(1, 3):
                                    cursor.execute('''
                                        INSERT INTO workforce (gender, age, origin, paylevel, member, jobcat)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    ''', (gender, age, origin, paylevel, member, jobcat))
        conn.commit()

    return 'Table populated successfully'

def multiply_table():
    with current_app.app_context():
        conn = get_db()
        cursor = conn.cursor()

        # Fetch all rows from the table
        cursor.execute('SELECT gender, age, origin, paylevel, member, jobcat FROM workforce')
        rows = cursor.fetchall()

        # Duplicate each row ten times
        duplicated_rows = []
        for row in rows:
            duplicated_rows.extend([row] * 9)

        # Insert the duplicated rows into the table
        cursor.executemany('''
            INSERT INTO workforce (gender, age, origin, paylevel, member, jobcat)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', duplicated_rows)

        conn.commit()

    return 'Table multiplied successfully'

def expand_table():
    with current_app.app_context():

        conn = get_db()
        cursor = conn.cursor()

        # Add columns
        cursor.execute('ALTER TABLE workforce ADD COLUMN residual REAL')
        cursor.execute('ALTER TABLE workforce ADD COLUMN bonus0 REAL')
        conn.commit()

        # Add values
        # Why is the residual random between 600 and 200 and not 200 and 600 + shouldn't it depend on the average wage?
        cursor.execute('SELECT rowid FROM workforce')
        rows = cursor.fetchall() # retrieve all rows as a list of tuples
        for row in rows:
            residual = max(random.gauss(600, 200), 0.1)
            cursor.execute('UPDATE workforce SET bonus0 = ? WHERE rowid = ?', (0, row[0]))
            cursor.execute('UPDATE workforce SET residual = ? WHERE rowid = ?', (residual, row[0]))
        conn.commit()

    return 'Table expanded successfully'

def startwage(averagewage_float):
    with current_app.app_context():
        gpg     = random.randint(0,15)/100
        apg_old = random.randint(0,30)/100
        apg     = apg_old
        apg_mid = random.randint(0,math.floor(100*apg_old))/100
        epg     = random.randint(0,15)/100
        up      = (random.randint(5,10)-10)/100
        wd      = random.randint(0,30)/100
        pay_hi  = random.randint(0,30)/100
        pay_mid = random.randint(0,math.floor(100*pay_hi))/100
        base    = (4/10)*averagewage_float

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('ALTER TABLE workforce ADD COLUMN logwage0 FLOAT')
        sql = f"""UPDATE workforce SET
                logwage0 = LN({base} + residual)
                + {gpg} * (gender = 1)
                + {apg_old} * (age = 3) + {apg_mid} * (age = 2)
                + {epg} * (origin = 1)
                + {pay_hi} * (paylevel=3) + {pay_mid} * (paylevel=2)
                + {up} * (member = 1) + {wd} * (jobcat = 2)"""
        cursor.execute(sql)
        conn.commit()

    return 'Startwage added successfully'

def create_log():
    with current_app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS logtable
                       (uroundid INTEGER PRIMARY KEY AUTOINCREMENT,
                        page INT DEFAULT 0,
                        gpg FLOAT DEFAULT 0,
                        apg FLOAT DEFAULT 0,
                        epg FLOAT DEFAULT 0,
                        wnq FLOAT DEFAULT 0,
                        wd FLOAT DEFAULT 0,
                        up FLOAT DEFAULT 0,
                        mean_wage FLOAT DEFAULT 0,
                        mean_bonus FLOAT DEFAULT 0,
                        mean_wage_bonus FLOAT DEFAULT 0,
                        employment INT DEFAULT 0,
                        prev_employment INT DEFAULT 0,
                        agency INT DEFAULT 50,
                        flexwork INT DEFAULT 50,
                        hirings INT DEFAULT 0,
                        layoffs INT DEFAULT 0,
                        nemployment INT DEFAULT 0,
                        nagency INT DEFAULT 50,
                        nflexwork INT DEFAULT 50,
                        nhirings INT DEFAULT 0,
                        nlayoffs INT DEFAULT 0,
                        claim FLOAT DEFAULT 0,
                        mchoice STRING DEFAULT NULL,
                        bcshare FLOAT DEFAULT NULL,
                        wcshare FLOAT DEFAULT NULL,
                        budget FLOAT DEFAULT NULL,
                        inflation FLOAT DEFAULT 0,
                        deflator FLOAT DEFAULT 1,
                        ndeflator FLOAT DEFAULT 1,
                        gains FLOAT DEFAULT NULL,
                        pgender INT DEFAULT NULL,
                        pagg INT DEFAULT NULL,
                        porigin INT DEFAULT NULL,
                        pjobcat INT DEFAULT NULL,
                        ppay INT DEFAULT NULL,
                        punion INT DEFAULT NULL,
                        rounds INT DEFAULT NULL,
                        averagewage FLOAT DEFAULT NULL,
                        formatted_datetime STRING DEFAULT NULL,
                        current_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        userid STRING DEFAULT NULL,
                        country STRING DEFAULT NULL,
                        language STRING DEFAULT NULL,
                        eur_rate FLOAT DEFAULT 1
                        )'''
                   )
        conn.commit()

        # Add first row with defaults
        cursor.execute('SELECT COUNT(*) FROM logtable')
        rowcount = cursor.fetchone()[0]
        if rowcount == 0:
            cursor.execute('INSERT INTO logtable DEFAULT VALUES')
        conn.commit()

def init_db(averagewage_float):
    with current_app.app_context():
        create_table()
        populate_table()
        multiply_table()
        expand_table()
        startwage(averagewage_float)
        create_log()

############ SOCIAL DASHBOARD ############

# the scoreboard is used in every repetition and on the results page #
# the p-prefix refers to the 'past' or 'present' wage variable, as the #
# choices should not be calculated through yet #


def socialdashboard(wagevar, bonusvar):
    conn = get_db()
    cursor = conn.cursor()

    query = f'SELECT AVG({wagevar}) FROM workforce'
    result = cursor.execute(query).fetchone()
    mean_wage = round(math.exp(result[0]))

    query = f'SELECT AVG({bonusvar}) FROM workforce'
    result = cursor.execute(query).fetchone()
    mean_bonus = round(math.exp(result[0]))

    mean_wage_bonus = mean_wage + mean_bonus

    # Inequalities
    def fetch_mean(p, col, value):
        query = f"SELECT AVG({p}) as average FROM workforce WHERE {col} = {value}"
        cursor.execute(query)
        result = cursor.fetchone()['average']
        if result is None:
            return 0
        else:
            return round(result, 2)

    def compute_gap(mean1, mean2, bonus1, bonus2):
        return round(( math.log(math.exp(mean1) + math.exp(bonus1)) - math.log(math.exp(mean2) + math.exp(bonus2))) * 100, 2)

    triples = [
        ('gender', 1, 2),
        ('age', 3, 1),
        ('origin', 1, 2),
        ('paylevel', 3, 1),
        ('jobcat', 2, 1),
        ('member', 1, 2),
    ]

    gaps = []

    for col, val1, val2 in triples:
        mean1 = fetch_mean(wagevar, col, val1)
        mean2 = fetch_mean(wagevar, col, val2)
        bonus1 = fetch_mean(bonusvar, col, val1)
        bonus2 = fetch_mean(bonusvar, col, val2)
        gap = compute_gap(mean1, mean2, bonus1, bonus2)
        gaps.append(gap)

    gpg, apg, epg, wnq, wd, up = gaps

    return mean_wage_bonus, mean_bonus, mean_wage, gpg, apg, epg, wnq, wd, up



############ WAGE INCREASE ############

# Promotions: the promoted group gets {more} (1.2) times the increase, the others {less} (0.8).
# Age (1 young, 2 middle, 3 old) and pay level (1 low, 2 middle, 3 high) have three groups:
# only the opposite extreme gets {less}, the middle group gets the plain increase (x1).
# With the balanced workforce every promotion then averages exactly x1, so the total
# increase equals the claim, and it acts on the same extreme groups as the dashboard gaps.
def wageincrease(mchoice, nextwage, nextbonus, wagevar, pgender, pagg, porigin, ppay, pjobcat, punion, bonpm, aclaim, rclaim, more, less):
    conn = get_db()
    cursor = conn.cursor()

    # Check if last logwage column already exists
    cursor.execute("PRAGMA table_info(workforce)")
    columns = [col[1] for col in cursor.fetchall()]

    if nextwage not in columns:
        cursor.execute(f'ALTER TABLE workforce ADD COLUMN {nextwage} FLOAT')

    # Check if bonus1 column already exists
    if nextbonus not in columns:
        cursor.execute(f'ALTER TABLE workforce ADD COLUMN {nextbonus} FLOAT')

    sqla = ''
    sqlb = ''

    if mchoice == "lump":
        # mchoice = session.get('mchoice', 'select')
        sqla = f"""UPDATE workforce SET
                    {nextbonus} = LN(1+({bonpm}
                    * (({pgender} = 1)
                    + ({pgender} = 2)*(gender=2)*{more}
                    + ({pgender} = 2)*(gender!=2)*{less}
                    + ({pgender} = 3)*(gender=1)*{more}
                    + ({pgender} = 3)*(gender!=1)*{less})
                    * (({pagg} = 1)
                    + ({pagg} = 2)*(age=1)*{more}
                    + ({pagg} = 2)*((age=2) + (age=3)*{less})
                    + ({pagg} = 3)*(age=3)*{more}
                    + ({pagg} = 3)*((age=2) + (age=1)*{less}))
                    * (({porigin} = 1)
                    + ({porigin} = 2)*(origin=2)*{more}
                    + ({porigin} = 2)*(origin!=2)*{less}
                    + ({porigin} = 3)*(origin=1)*{more}
                    + ({porigin} = 3)*(origin!=1)*{less})
                    * (({ppay} = 1)
                    + ({ppay} = 2)*(paylevel=1)*{more}
                    + ({ppay} = 2)*((paylevel=2) + (paylevel=3)*{less})
                    + ({ppay} = 3)*(paylevel=3)*{more}
                    + ({ppay} = 3)*((paylevel=2) + (paylevel=1)*{less}))
                    * (({pjobcat} = 1)
                    + ({pjobcat} = 2)*(jobcat=1)*{more}
                    + ({pjobcat} = 2)*(jobcat!=1)*{less}
                    + ({pjobcat} = 3)*(jobcat=2)*{more}
                    + ({pjobcat} = 3)*(jobcat!=2)*{less})
                    * (({punion} = 1)
                    + ({punion} = 2)*(member=1)*{more}
                    + ({punion} = 2)*(member!=1)*{less}
                    + ({punion} = 3)*(member=2)*{more}
                    + ({punion} = 3)*(member!=2)*{less})
                    ))"""
        sqlb = f"""UPDATE workforce SET {nextwage} = {wagevar}"""
    elif mchoice == "absolute":
        sqla = f"""UPDATE workforce SET
                    {nextwage} = LN(EXP({wagevar})+({aclaim}
                    * (({pgender} = 1)
                    + ({pgender} = 2)*(gender=2)*{more}
                    + ({pgender} = 2)*(gender!=2)*{less}
                    + ({pgender} = 3)*(gender=1)*{more}
                    + ({pgender} = 3)*(gender!=1)*{less})
                    * (({pagg} = 1)
                    + ({pagg} = 2)*(age=1)*{more}
                    + ({pagg} = 2)*((age=2) + (age=3)*{less})
                    + ({pagg} = 3)*(age=3)*{more}
                    + ({pagg} = 3)*((age=2) + (age=1)*{less}))
                    * (({porigin} = 1)
                    + ({porigin} = 2)*(origin=2)*{more}
                    + ({porigin} = 2)*(origin!=2)*{less}
                    + ({porigin} = 3)*(origin=1)*{more}
                    + ({porigin} = 3)*(origin!=1)*{less})
                    * (({ppay} = 1)
                    + ({ppay} = 2)*(paylevel=1)*{more}
                    + ({ppay} = 2)*((paylevel=2) + (paylevel=3)*{less})
                    + ({ppay} = 3)*(paylevel=3)*{more}
                    + ({ppay} = 3)*((paylevel=2) + (paylevel=1)*{less}))
                    * (({pjobcat} = 1)
                    + ({pjobcat} = 2)*(jobcat=1)*{more}
                    + ({pjobcat} = 2)*(jobcat!=1)*{less}
                    + ({pjobcat} = 3)*(jobcat=2)*{more}
                    + ({pjobcat} = 3)*(jobcat!=2)*{less})
                    * (({punion} = 1)
                    + ({punion} = 2)*(member=1)*{more}
                    + ({punion} = 2)*(member!=1)*{less}
                    + ({punion} = 3)*(member=2)*{more}
                    + ({punion} = 3)*(member!=2)*{less})
                    ))"""
        sqlb = f"""UPDATE workforce SET {nextbonus} = 0"""
    elif mchoice == "percentual":
        sqla = f"""UPDATE workforce SET
                    {nextwage} = LN(EXP({wagevar})
                        * (1.0/100.0)
                        * (100.0
                            + {rclaim}
                            * ( ({pgender} = 1)
                                + ({pgender} = 2)*(gender=2)*{more}
                                + ({pgender} = 2)*(gender!=2)*{less}
                                + ({pgender} = 3)*(gender=1)*{more}
                                + ({pgender} = 3)*(gender!=1)*{less} )
                            * ( ({pagg} = 1)
                                + ({pagg} = 2)*(age=1)*{more}
                                + ({pagg} = 2)*((age=2) + (age=3)*{less})
                                + ({pagg} = 3)*(age=3)*{more}
                                + ({pagg} = 3)*((age=2) + (age=1)*{less}) )
                            * ( ({porigin} = 1)
                                + ({porigin} = 2)*(origin=2)*{more}
                                + ({porigin} = 2)*(origin!=2)*{less}
                                + ({porigin} = 3)*(origin=1)*{more}
                                + ({porigin} = 3)*(origin!=1)*{less} )
                            * ( ({ppay} = 1)
                                + ({ppay} = 2)*(paylevel=1)*{more}
                                + ({ppay} = 2)*((paylevel=2) + (paylevel=3)*{less})
                                + ({ppay} = 3)*(paylevel=3)*{more}
                                + ({ppay} = 3)*((paylevel=2) + (paylevel=1)*{less}) )
                            * ( ({pjobcat} = 1)
                                + ({pjobcat} = 2)*(jobcat=1)*{more}
                                + ({pjobcat} = 2)*(jobcat!=1)*{less}
                                + ({pjobcat} = 3)*(jobcat=2)*{more}
                                + ({pjobcat} = 3)*(jobcat!=2)*{less} )
                            * ( ({punion} = 1)
                                + ({punion} = 2)*(member=1)*{more}
                                + ({punion} = 2)*(member!=1)*{less}
                                + ({punion} = 3)*(member=2)*{more}
                                + ({punion} = 3)*(member!=2)*{less} )
                        )
                        )"""
        sqlb = f"""UPDATE workforce SET {nextbonus} = 0"""

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(sqla)
    cursor.execute(sqlb)
    conn.commit()

def updaterow(page):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT rounds FROM logtable ORDER BY rowid ASC LIMIT 1')
    #cursor.execute('SELECT rounds FROM logtable WHERE rowid = 1')
    result = cursor.fetchone()
    roundmax = result[0]
    cursor.execute(f'UPDATE logtable SET rounds = ? WHERE rowid = ?', (roundmax, page))
    conn.commit()

    cursor.execute('SELECT userid FROM logtable WHERE rowid = 1')
    result = cursor.fetchone()
    userid = result[0]
    cursor.execute(f'UPDATE logtable SET userid = ? WHERE rowid = ?', (userid, page))

    current_datetime = datetime.now()
    cursor.execute(f'UPDATE logtable SET current_datetime = ? WHERE rowid = ?', (current_datetime, page))
    conn.commit()

    cursor.execute('SELECT formatted_datetime FROM logtable WHERE rowid = 1')
    result = cursor.fetchone()
    formatted_datetime = result[0]
    cursor.execute(f'UPDATE logtable SET formatted_datetime = ? WHERE rowid = ?', (formatted_datetime, page))
    conn.commit()

    cursor.execute('SELECT averagewage FROM logtable WHERE rowid = 1')
    result = cursor.fetchone()
    averagewage = result[0]
    cursor.execute(f'UPDATE logtable SET averagewage = ? WHERE rowid = ?', (averagewage, page))
    conn.commit()

    cursor.execute(f'UPDATE logtable SET page = ? WHERE rowid = ?', (page, page))
    cursor.execute('UPDATE logtable SET country = ?, language = ? WHERE rowid = ?',
                   (current_country(), current_lang(), page))
    conn.commit()

    return roundmax

############ INDEX ROUTE ############
# i took this out of the form: action="{{ url_for('bround', page=1) }}"


@website.route('/', methods=['GET', 'POST'])
def index():
    bst_version = config.VERSION
   
    return render_template('index.html', bst_version=bst_version)


@website.route('/case', methods=['GET', 'POST'])
def case():
   
    return render_template('case.html')

@website.route('/instructions', methods=['GET', 'POST'])
def instructions():

    if 'button_states' in session:
        session.pop('button_states')

    # db_dir = 'data'
    # db_name = session.get('db_name')
    # db_path = os.path.join(db_dir, db_name)
    # print("DB PATH INDEX ROUTE: ", db_path)
    # if db_name and os.path.exists(db_path):
    #     os.remove(db_path)

    # After submitting the number of rounds and average wage, create the tables
    if request.method == 'POST':

        """Check if database has a name, then delete it if it exists (it could also have been cleared already, hence try)."""
        db_name = session.get('db_name')
        if db_name:
            try:
                os.remove(db_name)
            except FileNotFoundError:
                pass  # file didn't exist, nothing to do

        userid = str(uuid.uuid4())
        db_name = os.path.join(config.DATA_DIR, userid + '-user.db')
        session['db_name'] = db_name
        session['userid'] = userid

        conn = get_db()
        cursor = conn.cursor()

        # The wage is entered in the local currency; the model always works in EUR
        # (the random part of the wages is set in EUR), so convert it here.
        eur_rate = country_info()['eur_rate']
        try:
            averagewage_float = float(request.form.get('salary-text', '')) / eur_rate
            print('Average wage (EUR):', averagewage_float)
        except ValueError:
            print("Invalid averagewage: Value must be a numeric.")
            return redirect(url_for('website.instructions'))

        init_db(averagewage_float)

        cursor.execute('UPDATE logtable SET averagewage = ?, eur_rate = ? WHERE rowid = ?',
                       (averagewage_float, eur_rate, 1,))
        conn.commit()

        if 'roundnumber' in request.form:
            roundnumber = request.form['roundnumber']
            # Validate that roundnumber is an integer between 5 and 10
            try:
                roundnumber_int = int(roundnumber)
                if 1 <= roundnumber_int <= 10:
                    print('Number of rounds:', roundnumber)
                    try:
                        cursor.execute('UPDATE logtable SET rounds = ? WHERE rowid = ?', (roundnumber, 1,))
                        conn.commit()
                    except Exception as e:
                        print('Error:', e)
                else:
                    print("Invalid roundnumber: Value must be between 5 and 10.")
            except ValueError:
                print("Invalid roundnumber: Value must be an integer.")


        # Time and date
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        #return f"The current date and time is: {formatted_datetime}"


        # Save usera and time
        cursor.execute('UPDATE logtable SET current_datetime = ? WHERE rowid = ?', (current_datetime, 1,))
        cursor.execute('UPDATE logtable SET formatted_datetime = ? WHERE rowid = ?', (formatted_datetime, 1,))
        cursor.execute('UPDATE logtable SET userid = ? WHERE rowid = ?', (userid, 1,))
        conn.commit()

        return redirect(url_for('website.bround', page=1))
    return render_template('instructions.html')


############ BARGAINING ROUND ############

@website.route('/page/<int:page>', methods=['GET', 'POST'])
def bround(page):

    print('Current page: ', page)

    if not has_game():
        return redirect(url_for('website.index'))

    # Connect database
    db_name = session.get('db_name')
    print(f"PRINT: route {page}, db: {db_name}")

    # DEFAULTS (needed for return)
    # From round 2 onwards, the dashboard could include a comparison between plogwage and pplogwage
    # In that case, I need to pass the page to the function and also pplogwage and ppbonus
    # Then I can put red and green arrows in the fields.
    ppage = str(page - 1)
    pppage = str(page - 2)
    cpage = str(page)
    str_page = str(page)

    wagevar = 'logwage' + ppage
    bonusvar = 'bonus' + ppage
    prev_wagevar = 'logwage' + pppage
    prev_bonusvar = 'bonus' + pppage
    if page == 1: # this is just a trick so all gaps are unchanged
        prev_wagevar = 'logwage' + ppage
        prev_bonusvar = 'bonus' + ppage
    nextwage = 'logwage' + cpage
    nextbonus = 'bonus' + cpage

    sqla = "" # this is returned for troubleshooting, so it needs to exist

    # Insert new row into logtable, only at a new page, not when refreshing #############
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(rounds) FROM logtable')
    row_count = cursor.fetchone()[0]
    if row_count < page:
        cursor.execute('INSERT INTO logtable DEFAULT VALUES')
        conn.commit()

    (roundmax) = updaterow(page)

    results_next = 0
    if page == roundmax:
        results_next = 1

    if page == roundmax + 1:
        return redirect(url_for('website.results'))
    


    # TABLE 1: SOCIAL DASHBOARD ############

    ## Current values (to be saved)

    print('Bonus var print: ', bonusvar)

    (mean_wage_bonus, mean_bonus, mean_wage,
     gpg, apg, epg, wnq, wd, up) = socialdashboard(wagevar, bonusvar)

    inputlist = [(page, 'gpg', gpg), (page, 'apg', apg), (page, 'epg', epg),
                 (page, 'wnq', wnq), (page, 'wd', wd), (page, 'up', up),
                 (page, 'mean_wage_bonus', mean_wage_bonus), (page, 'mean_bonus', mean_bonus), (page, 'mean_wage', mean_wage) ]
    for page, column, value in inputlist:
        cursor.execute(
            f'UPDATE logtable SET {column} = ? WHERE rowid = ?', (value, page))
    conn.commit()

    ## Previous values (arrows)
    """ 
    Previous values are only needed to calculate the difference at the beginning of a round.
    There is no previous round in round 1, so therefore prev_wagevar and prev_bonusvar have been
    set to be the current var. See above.
    """
    (prev_mean_wage_bonus, prev_mean_bonus, prev_mean_wage,
     prev_gpg, prev_apg, prev_epg, prev_wnq,
     prev_wd, prev_up) = socialdashboard(prev_wagevar, prev_bonusvar)

    print('Previous GPG: ', prev_gpg)

    # Some defaults to make it work and reset the page
    claim = 0
    message = None

    # Get mchoice from logtable
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT mchoice FROM logtable WHERE rowid = ?', (page,))
    result = cursor.fetchone()

    # If no result or error, set mchoice to 'select'
    if result is None or result[0] is None:
        mchoice = 'select'
    else:
        mchoice = result[0]

    # inputlist = [(page, 'agency', agency), (page, 'hirings', hirings), (page, 'layoffs', layoffs), (page, 'flexwork', flexwork)]
    # for rowid, column, value in inputlist:
    #      cursor.execute(
    #      f'UPDATE logtable SET {column} = ? WHERE rowid = ?', (value, rowid))
    # conn.commit()

    # gains-BUDGET-SHARES
    # check if the logtable exists and has a row, input data only once, because it's randomized!
    cursor.execute('SELECT COUNT(*) FROM logtable WHERE gains IS NOT NULL')
    rowcount = cursor.fetchone()[0]

    if rowcount < page:
        # if logtable doesn't have a row yet, insert values on a new row
        # first run, page = 1, rowcount = 0, but then it gets completed, so row 1 cannot be overwritten
        inflation = random.randint(10, 30)/10
        gains = random.randint(1, 8)
        budget = gains
        randomnr = random.random()*2 
        bcshare = round(randomnr*gains,1)
        wcshare = round((2-randomnr)*gains, 1)

        pgender = 1
        pagg = 1
        porigin = 1
        pjobcat = 1
        ppay = 1
        punion = 1

        inputlist = [(page, 'inflation', inflation), (page, 'gains', gains),
                     (page, 'budget', budget),
                     (page, 'wcshare', wcshare), (page, 'bcshare', bcshare),
                     (page, 'pgender', pgender), (page, 'pagg', pagg),
                     (page, 'porigin', porigin), (page, 'pjobcat', pjobcat),
                     (page, 'ppay', ppay), (page, 'punion', punion)]
        for page, column, value in inputlist:
             cursor.execute(
             f'UPDATE logtable SET {column} = ? WHERE rowid = ?', (value, page))
        conn.commit()
    else:
        # if logtable does have a row, get values from it (meaning using the last row's values) - use query if problems ater
        cursor.execute("""SELECT inflation, gains, budget, claim, bcshare, wcshare,
                       pgender, pagg, porigin, pjobcat, ppay, punion
                       FROM logtable WHERE rowid = ?""", (page,))
        result = cursor.fetchone()
        inflation = result[0]
        gains = result[1]
        budget = result[2]
        claim = result[3]
        bcshare = result[4]
        wcshare = result[5]
        pgender = result[6]
        pagg = result[7]
        porigin = result[8]
        pjobcat = result[9]
        ppay = result[10]
        punion = result[11]

    # FORMS ############
    if 'button_states' not in session:
        session['button_states'] = {}

    # Only initialise the form states of a new round; a reload or a language switch keeps them
    if request.method == 'GET':
        if str_page not in session['button_states']:
            session['button_states'][str_page] = {'claim': False, 'method': False, 'promotions': False}
            session.modified = True

    if request.method == 'POST':
        if 'submit_button' in request.form:
            pressed_button = request.form['submit_button']

            if str_page not in session['button_states']:
                session['button_states'][str_page] = {'claim': False, 'method': False, 'promotions': False}

            if pressed_button == 'claim':
                session['button_states'][str_page]['claim'] = True
                session.modified = True

                # Get form values
                try:
                    tvar = float(request.form['claim'])
                    claim = float(tvar)
                except (TypeError, ValueError):
                    claim = claim
                print('claim: ', claim)
                cursor.execute('UPDATE logtable SET claim = ? WHERE rowid = ?', (claim,page,))
                conn.commit()

            elif pressed_button == 'method':
                session['button_states'][str_page]['method'] = True
                session.modified = True

                # Get form values
                try:
                    mchoice = request.form['mchoice']
                except (TypeError, ValueError, KeyError):
                    mchoice = mchoice
                # No bonus in the last round (the option is not shown there either)
                if mchoice not in ('lump', 'percentual', 'absolute') or (mchoice == 'lump' and page >= roundmax):
                    mchoice = 'select'

                # Store results
                cursor.execute('UPDATE logtable SET mchoice = ? WHERE rowid = ?', (mchoice,page,))
                conn.commit()

            elif pressed_button == 'promotions':
                session['button_states'][str_page]['promotions'] = True
                session.modified = True

                # Get form values
                pgender = int(request.form['pgender'][-1])
                pagg = int(request.form['pagg'][-1])
                porigin = int(request.form['porigin'][-1])
                pjobcat = int(request.form['pjobcat'][-1])
                ppay = int(request.form['ppay'][-1])
                punion = int(request.form['punion'][-1])

                # Store results
                cursor.execute('UPDATE logtable SET pgender = ? WHERE rowid = ?', (pgender,page,))
                cursor.execute('UPDATE logtable SET pagg    = ? WHERE rowid = ?', (pagg,page,))
                cursor.execute('UPDATE logtable SET porigin = ? WHERE rowid = ?', (porigin,page,))
                cursor.execute('UPDATE logtable SET pjobcat = ? WHERE rowid = ?', (pjobcat,page,))
                cursor.execute('UPDATE logtable SET ppay    = ? WHERE rowid = ?', (ppay,page,))
                cursor.execute('UPDATE logtable SET punion  = ? WHERE rowid = ?', (punion,page,))
                conn.commit()

            if all(session['button_states'][str_page].values()):
                print('good to go')

    if page - 1 in session['button_states']:
        del session['button_states'][page - 1]
        session.modified = True

    show_next = False
    if (str_page in session['button_states']
        and all(session['button_states'][str_page].values())
        and mchoice != 'select'):
        show_next = True
    show_claim = True
    show_method = False
    if (str_page in session['button_states']
        and session['button_states'][str_page]['claim'] == True):
        show_method = True

    show_promotions = False
    if (str_page in session['button_states']
        and session['button_states'][str_page]['method'] == True 
        and mchoice != 'select'):
        show_promotions = True

    # WORKFORCE AND DEFLATOR ############
    # This is a more dynamic section with calculations ovar the rows
    # whatever was stored as a 'next' variable in time t-1 will be called
    # first and be the current variable

    if page == 1:

        agency = 50
        hirings = 0
        layoffs = 0
        flexwork = 50
        employment = 0
        prev_employment = 0
        deflator = 1
        prev_deflator = 1


    elif page > 1:     # From the last round
        cursor.execute("SELECT ndeflator FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        deflator = result[0]
        cursor.execute("SELECT deflator FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        prev_deflator = result[0]
        cursor.execute("SELECT nemployment FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        employment = result[0]
        cursor.execute("SELECT employment FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        prev_employment = result[0]
        cursor.execute("SELECT nagency FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        agency = result[0]
        cursor.execute("SELECT nflexwork FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        flexwork = result[0]
        cursor.execute("SELECT nhirings FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        hirings = result[0]
        cursor.execute("SELECT nlayoffs FROM logtable WHERE rowid = ?", (page-1,))
        result = cursor.fetchone()
        layoffs = result[0]



    # Employment and wage change
    real_wage_bonus = mean_wage_bonus / deflator
    prev_real_wage_bonus = prev_mean_wage_bonus / prev_deflator

    shift_raw = (budget-claim)/0.5
    shiftplus = 0
    shiftminus = 0
    if shift_raw == 0:
        print('all good')
    elif shift_raw < 0:
        shiftminus = math.ceil(abs(shift_raw))
    elif shift_raw > 0:
        shiftplus = math.ceil(abs(shift_raw))
    shift = shiftplus - shiftminus #this could be the variable to report
    ndeflator = deflator*(1+inflation/100)
    nemployment = employment + shift
    nagency = agency + shift
    nhirings = max(nagency-50,0)
    nlayoffs = max(50-nagency,0)
    nflexwork = min(50,nagency)

    inputlist = [(page, 'agency', agency), (page, 'layoffs', layoffs),
                 (page, 'flexwork', flexwork), (page, 'hirings', hirings),
                 (page, 'nagency', nagency), (page, 'nlayoffs', nlayoffs),
                 (page, 'nflexwork', nflexwork), (page, 'nhirings', nhirings),
                 (page, 'nemployment', nemployment),(page, 'employment', employment),
                 (page, 'prev_employment', prev_employment),
                 (page, 'deflator', deflator), (page, 'ndeflator', ndeflator)]
    for pagenr, column, value in inputlist:
         cursor.execute(
         f'UPDATE logtable SET {column} = ? WHERE rowid = ?', (value, pagenr))
    conn.commit()


    # METHOD
    rclaim = claim
    aclaim = round((rclaim/100)*mean_wage)
    aclaimyear = 12*aclaim
    bonus = round(aclaim*12*2.5)
    bonpm = round(aclaim*2.5)
    if page > (roundmax-1): # just the last round has no bonus option
        bonus = 0
        bonpm = 0


    # PROMOTION
    more = 1.2
    less = 0.8

    wageincrease(mchoice, nextwage, nextbonus, wagevar, pgender, pagg, porigin,
                 ppay, pjobcat, punion, bonpm, aclaim, rclaim, more, less)

    return render_template('round.html',
                           results_next=results_next,
                           gpg=gpg,
                           apg=apg,
                           epg=epg,
                           wnq=wnq,
                           wd=wd,
                           up=up,
                           pgender=pgender,
                           pagg=pagg,
                           porigin=porigin,
                           pjobcat=pjobcat,
                           punion=punion,
                           ppay=ppay,
                           inflation=inflation,
                           gains=gains,
                           budget=budget,
                           mean_wage=mean_wage,
                           mean_bonus=mean_bonus,
                           mean_wage_bonus=mean_wage_bonus,
                           prev_real_wage_bonus=prev_real_wage_bonus,
                           prev_mean_wage_bonus=prev_mean_wage_bonus,
                           real_wage_bonus=real_wage_bonus,
                           deflator=deflator,
                           claim=claim,
                           rclaim=rclaim,
                           aclaim=aclaim,
                           aclaimyear=aclaimyear,
                           bonus=bonus,
                           bonpm=bonpm,
                           wcshare=wcshare,
                           bcshare=bcshare,
                           message=message,
                           mchoice=mchoice,
                           sqla=sqla,
                           page=page,
                           roundmax=roundmax,
                           show_next=show_next,
                           show_promotions=show_promotions,
                           show_method=show_method,
                           show_claim=show_claim,
                           employment=employment,
                           prev_employment=prev_employment,
                           agency=agency,
                           hirings=hirings,
                           layoffs=layoffs,
                           flexwork=flexwork,
                           prev_gpg=prev_gpg,
                           prev_apg=prev_apg,
                           prev_epg=prev_epg,
                           prev_wnq=prev_wnq,
                           prev_wd=prev_wd,
                           prev_up=prev_up)


@website.route('/results', methods=['GET', 'POST'])
def results():
    # gpg=0
    # apg=0
    # epg=0
    # wnq=0
    # wd=0
    # up=0
    # hirings=0
    # layoffs=0
    # flexwork=0

    if not has_game():
        return redirect(url_for('website.index'))

    # Get the userid and maximum number of rounds
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT userid FROM logtable WHERE rowid = 1')
    result = cursor.fetchone()
    userid = result[0]

    cursor.execute('SELECT rounds FROM logtable WHERE rowid = 1')
    result = cursor.fetchone()
    roundmax = result[0]


    # Average bonus
    """ make a new column in the workforce table for the mean bonus (bonusmean) """
    try:
        cursor.execute("ALTER TABLE workforce ADD COLUMN bonusmean REAL")
        conn.commit()
    except sqlite3.OperationalError:
        print("PRINT: Column already exists")

    """ Initialize bonusmean with EXP(bonus1), then loop over all rounds """
    cursor.execute("UPDATE workforce SET bonusmean = EXP(bonus1)")
    conn.commit()

    for i in range(2, roundmax + 1):
        bonus_i = f'bonus{i}'
        # Incrementally add EXP(bonus_i) to bonusmean
        sql = f"UPDATE workforce SET bonusmean = bonusmean + EXP({bonus_i})"
        cursor.execute(sql)
        conn.commit()

    """ Finally, take the log of the average """
    cursor.execute(f"UPDATE workforce SET bonusmean = LN(bonusmean * 1.0 / {roundmax})")
    conn.commit()


    # SOCIAL SCOREBOARD

    conn = get_db()
    cursor = conn.cursor()

    ## Initial values (step 0)
    """ logwage varies, bonus is always zero, this is now the 'previous' state """
    wagevar = 'logwage0'
    bonusvar = 'bonus0'

    (prev_mean_wage_bonus, prev_mean_bonus, prev_mean_wage, prev_gpg, prev_apg,
     prev_epg, prev_wnq, prev_wd, prev_up) = socialdashboard(wagevar, bonusvar)

    prev_real_wage_bonus = prev_mean_wage_bonus
    prev_employment = 0

    ## Fictitious results last round
    """ This is as if there had been a next round after the last round, page will be larger than roundmax but not 99"""

    ### Get wages
    wagevar = 'logwage' + str(roundmax)
    bonusvar = 'bonus' + str(roundmax)

    (mean_wage_bonus, mean_bonus, mean_wage, gpg, apg,
     epg, wnq, wd, up) = socialdashboard(wagevar, bonusvar)

    ### Get employment
    cursor.execute("SELECT nemployment FROM logtable WHERE rowid = ?", (roundmax,))
    result = cursor.fetchone()
    employment = result[0]

    ### Get deflator (last)
    cursor.execute("SELECT ndeflator FROM logtable WHERE rowid = ?", (roundmax,))
    result = cursor.fetchone()
    deflator = result[0]


    ### Save

    #### Insert new row into logtable, only at a new page, not when refreshing #############
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(page) FROM logtable')
    row_count = cursor.fetchone()[0]
    if row_count == roundmax:
        cursor.execute('INSERT INTO logtable DEFAULT VALUES')
        conn.commit()

    page = roundmax + 1

    (roundmax) = updaterow(page)

    inputlist = [(page, 'gpg', gpg), (page, 'apg', apg), (page, 'epg', epg),
                 (page, 'wnq', wnq), (page, 'wd', wd), (page, 'up', up),
                 (page, 'mean_wage_bonus', mean_wage_bonus), (page, 'mean_bonus', mean_bonus), (page, 'mean_wage', mean_wage), (page, 'employment', employment), (page, 'deflator', deflator), (page, 'page', page)]
    for page, column, value in inputlist:
        cursor.execute(
            f'UPDATE logtable SET {column} = ? WHERE rowid = ?', (value, page))
    conn.commit()


    ## Final values (to be displayed as results)

    ### Get wages
    """ This is wage + average bonus! """
    wagevar = 'logwage' + str(roundmax)
    bonusvar = 'bonusmean'

    (mean_wage_bonus, mean_bonus, mean_wage, gpg, apg,
     epg, wnq, wd, up) = socialdashboard(wagevar, bonusvar)

    cursor.execute(f'SELECT ndeflator FROM logtable WHERE rowid = {roundmax}')
    result = cursor.fetchone()
    deflator = result[0]

    real_wage_bonus = mean_wage_bonus / deflator

    ### Get employment
    cursor.execute("SELECT nemployment FROM logtable WHERE rowid = ?", (roundmax,))
    result = cursor.fetchone()
    employment = result[0]

    ### Get deflator (last)
    cursor.execute("SELECT ndeflator FROM logtable WHERE rowid = ?", (roundmax,))
    result = cursor.fetchone()
    deflator = result[0]

    ### Save on row '99'
    
    #### Insert new row into logtable, only at a new page, not when refreshing #############
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(page) FROM logtable')
    row_count = cursor.fetchone()[0]
    if row_count == roundmax + 1:
        cursor.execute('INSERT INTO logtable DEFAULT VALUES')
        conn.commit()

    page = roundmax + 2

    (roundmax) = updaterow(page)

    inputlist = [(page, 'gpg', gpg), (page, 'apg', apg), (page, 'epg', epg),
                 (page, 'wnq', wnq), (page, 'wd', wd), (page, 'up', up),
                 (page, 'mean_wage_bonus', mean_wage_bonus), (page, 'mean_bonus', mean_bonus), (page, 'mean_wage', mean_wage), (page, 'employment', employment), (page, 'deflator', deflator), (page, 'page', page)]
    for page, column, value in inputlist:
        cursor.execute(
            f'UPDATE logtable SET {column} = ? WHERE rowid = ?', (value, page))
    conn.commit()






    # Evaluation survey responses
    ### Make the table
    cursor.execute('''CREATE TABLE IF NOT EXISTS evaluation
               (svy_eval_strategy INT DEFAULT NULL,
                svy_eval_results INT DEFAULT NULL,
                svy_eval_approach TEXT DEFAULT NULL,
                svy_case_gender_pay_gap INT DEFAULT NULL,
                svy_real_gender_pay_gap INT DEFAULT NULL,
                svy_case_age_pay_gap INT DEFAULT NULL,
                svy_real_age_pay_gap INT DEFAULT NULL,
                svy_case_ethnic_pay_gap INT DEFAULT NULL,
                svy_real_ethnic_pay_gap INT DEFAULT NULL,
                svy_case_wage_inequality INT DEFAULT NULL,
                svy_real_wage_inequality INT DEFAULT NULL,
                svy_case_pay_differentials INT DEFAULT NULL,
                svy_real_pay_differentials INT DEFAULT NULL,
                svy_case_union_premium INT DEFAULT NULL,
                svy_real_union_premium INT DEFAULT NULL,
                svy_case_wagelevel INT DEFAULT NULL,
                svy_real_wagelevel INT DEFAULT NULL,
                svy_case_employment INT DEFAULT NULL,
                svy_real_employment INT DEFAULT NULL,
                resp_gender TEXT DEFAULT NULL,
                resp_age INT DEFAULT NULL,
                resp_country TEXT DEFAULT NULL,
                resp_origin TEXT DEFAULT NULL,
                resp_union TEXT DEFAULT NULL,
                resp_paylevel TEXT DEFAULT NULL,
                resp_jobstatus TEXT DEFAULT NULL,
                userid STRING DEFAULT NULL,
                country STRING DEFAULT NULL,
                language STRING DEFAULT NULL
                )'''
           )
    conn.commit()

    # Enter default values to ensure there is an (automatic) rowid
    cursor.execute("SELECT 1 FROM evaluation WHERE rowid = 1")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO evaluation DEFAULT VALUES")
    conn.commit()

    #cursor.execute('''INSERT INTO evaluation (userid) VALUES (?)''', (userid,))
    cursor.execute(f"UPDATE evaluation SET userid = ? WHERE rowid = 1", (userid,))

    conn.commit()

    # SURVEY

    if request.method == 'POST':
        # List of all expected form field names
        field_names = ['svy_eval_strategy', 'svy_eval_results', 'svy_eval_approach',
                    'svy_case_gender_pay_gap', 'svy_real_gender_pay_gap', 'svy_case_age_pay_gap',
                    'svy_real_age_pay_gap', 'svy_case_ethnic_pay_gap', 'svy_real_ethnic_pay_gap',
                    'svy_case_wage_inequality', 'svy_real_wage_inequality', 'svy_case_pay_differentials',
                    'svy_real_pay_differentials', 'svy_case_union_premium', 'svy_real_union_premium',
                    'svy_case_wagelevel', 'svy_real_wagelevel', 'svy_case_employment', 'svy_real_employment',
                    'resp_gender', 'resp_age', 'resp_country', 'resp_origin', 'resp_union',
                    'resp_paylevel', 'resp_jobstatus']

        # Checkboxes are stored as 0/1; sliders, age and choices keep their value
        value_fields = ['svy_eval_strategy', 'svy_eval_results', 'svy_eval_approach',
                        'resp_gender', 'resp_age', 'resp_country', 'resp_origin', 'resp_union',
                        'resp_paylevel', 'resp_jobstatus']
        int_fields = ['svy_eval_strategy', 'svy_eval_results', 'resp_age']
        form_values = {}
        for field in field_names:
            if field in value_fields:
                value = request.form.get(field) or None
                if field in int_fields and value is not None:
                    try:
                        value = int(value)
                    except ValueError:
                        value = None
                form_values[field] = value
            else:
                form_values[field] = 1 if request.form.get(field, 'off') == 'on' else 0
        if form_values['resp_paylevel'] is None:
            form_values['resp_paylevel'] = 'select'
        form_values['country'] = current_country()
        form_values['language'] = current_lang()
        
        for column, value in form_values.items():
            print(f"{column} has value {value}")
            cursor.execute(f"UPDATE evaluation SET {column} = ? WHERE rowid = 1", (value,))
            conn.commit()
            cursor.execute(f"SELECT {column} FROM evaluation WHERE rowid = 1")
            updated_value = cursor.fetchone()
            print(f"{column} updated to {updated_value}")
        conn.commit()
        return redirect(url_for('website.thanks'))



    # RESULTS TEMPLATE
    return render_template('results.html',
                           gpg=gpg,
                           apg=apg,
                           epg=epg,
                           wnq=wnq,
                           wd=wd,
                           up=up,
                           employment=employment,
                           prev_employment=prev_employment,
                           mean_wage_bonus=mean_wage_bonus,
                           mean_wage=mean_wage,
                           real_wage_bonus=real_wage_bonus,
                           mean_bonus=mean_bonus,
                           roundmax=roundmax,
                           prev_mean_wage_bonus=prev_mean_wage_bonus,
                           prev_real_wage_bonus=prev_real_wage_bonus,
                           prev_mean_wage=prev_mean_wage,
                           prev_mean_bonus=prev_mean_bonus,
                           prev_gpg=prev_gpg,
                           prev_apg=prev_apg,
                           prev_epg=prev_epg,
                           prev_wnq=prev_wnq,
                           prev_wd=prev_wd,
                           prev_up=prev_up)


@website.route('/thanks', methods=['GET', 'POST'])
def thanks():

    # Add the player's results to the collected database, only once
    # (reloading this page or switching language must not duplicate them)
    if has_game():
        db_name = session.get('db_name')
        try:
            conn = get_db()
            conn.execute('CREATE TABLE IF NOT EXISTS transfer (done INTEGER)')
            already = conn.execute('SELECT COUNT(*) FROM transfer').fetchone()[0]
            if not already:
                print("PRINT: Transfer user data to FDB")
                copy_data_to_fdb(db_name, 'logtable')
                copy_data_to_fdb(db_name, 'evaluation')
                conn.execute('INSERT INTO transfer VALUES (1)')
                conn.commit()
        except Exception as e:
            print(f"PRINT: An error occurred: {str(e)}")

    return render_template('thanks.html')

@website.route('/download', methods=['GET', 'POST'])
def download():
    # return render_template('download.html')

    # Report the number of entries
    nrentries = 0
    fdb_path = config.FDB_PATH
    if os.path.exists(fdb_path):
        print("PRINT: FDB path does exist")

        conn = sqlite3.connect(fdb_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(userid) FROM evaluation')
        nrentries = cursor.fetchone()[0]
        # Commit the changes and close the connection
        conn.close()
    else:
        print("PRINT: path does not exist")

    if request.method == 'POST':
        # get current attempt count and first attempt time
        attempt_count = session.get('attempt_count', 0)
        first_attempt_time = session.get('first_attempt_time')

        # if an hour has passed since first attempt, reset attempt count and time
        if first_attempt_time is not None and (datetime.now() - first_attempt_time).seconds > 3600:
            attempt_count = 0
            first_attempt_time = None

        # if the user has already tried 5 times in the last hour, don't allow the download
        if attempt_count >= 5 and (first_attempt_time is None or (datetime.now() - first_attempt_time).seconds <= 3600):
            flash(str(t('download.too_many')))
            return redirect(url_for('website.download'))

        # The code comes from the environment (config.DOWNLOAD_CODE); without it, no download
        password = (request.form.get('downloadcode') or '').strip()
        if config.DOWNLOAD_CODE and hmac.compare_digest(password.encode(), config.DOWNLOAD_CODE.encode()):
            try:
                # return send_file('data/fdb.db', attachment_filename='fdb.db', as_attachment=True)
                return send_file(os.path.abspath(config.FDB_PATH), as_attachment=True)
            except Exception as e:
                return str(e)
        else:
            flash(str(t('download.wrong')))

            # if it's the first attempt, save the time
            if first_attempt_time is None:
                session['first_attempt_time'] = datetime.now()

            # increase the attempt count
            session['attempt_count'] = attempt_count + 1

            return redirect(url_for('website.download'))

    # if it's a GET request, reset the attempt count and time
    session['attempt_count'] = 0
    session['first_attempt_time'] = None

    return render_template('download.html', nrentries=nrentries, enabled=bool(config.DOWNLOAD_CODE))