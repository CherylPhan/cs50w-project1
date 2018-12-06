import os, requests, json

from flask import Flask, session, render_template, request, redirect, url_for, flash, jsonify
from flask_session import Session
from functools import wraps
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Set secret key for session
app.secret_key = os.urandom(16)

# Login_required decorator
def login_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        # Check if user has logged in
        if "user_id" not in session:
            flash("You must log in first.")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorator

@app.route("/", methods=["GET", "POST"])
def index():

    # User reach route using "POST" method
    if request.method == "POST":

        # Forget current user:
        session.pop('user_id', None)

        # Get username and password
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username and password are provided
        if not (username and password):
            flash("Please enter your username and password.")
            return redirect(url_for('index'))
        
        # Ensure username and password are correct
        user = db.execute("SELECT * FROM users WHERE username = :username AND password = :password", 
                        {"username": username, "password": password}).fetchone()
        if user is None:
            flash("Incorrect username or password.")
            return redirect(url_for('index'))

        # Log user in
        session["user_id"] = user.id
        
        return redirect("/books")

    # User reach route using "GET" method
    if request.method == "GET":
        return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    # User reach route using "POST" method
    if request.method == "POST":
        # Get registration information from user
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        # Check if missing information
        if not (email and username and password):
            flash("Please provide your email, username and password.")
            return redirect(url_for('register'))

        # Check if email already existed
        if db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).rowcount > 0:
            flash("This email already existed.")
            return redirect(url_for('register'))

        # Check if username already existed
        if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount > 0:
            flash("This username already existed.")
            return redirect(url_for('register'))

        # Ensure passwords match
        if password != password_confirm:
            flash("Your passwords do not match.")
            return redirect(url_for('register'))

        # Register user into database
        db.execute("INSERT INTO users (email, username, password) VALUES (:email, :username, :password)", 
                    {"email": email, "username": username, "password": password})
        db.commit()
        
        return redirect("/")
        
    # User reach route using "GET" method
    if request.method == "GET":
        return render_template("register.html")

@app.route("/books", methods=["GET", "POST"])
@login_required
def books():

    # User reach route using "POST" method
    if request.method == "POST":
        # Get the search key
        key = request.form.get("key")

        # Look it up in the databse
        books = db.execute("SELECT * FROM books WHERE title LIKE :key OR author LIKE :key OR isbn LIKE :key", 
                            {"key": '%' + key + '%'}).fetchall()

        # Make sure the book exists
        if not books:
            return render_template("books.html", message="No book found.")
        
        return render_template("books.html", books=books)

    # User reach route using "GET" method
    if request.method == "GET":
        
        return render_template("books.html")

@app.route("/books/<int:book_id>", methods=["GET", "POST"])
@login_required
def book(book_id):

    # User reach route using "GET" method
    if request.method == "GET":
        # Make sure the book exists
        book =  db.execute("SELECT * FROM books WHERE id=:id", {"id": book_id}).fetchone()
        if book is None:
            flash(f"Book id {book_id} does not exist. Please search for another book.")
            return redirect(url_for('books'))
        
        # Get Goodreads rating (if any)
        gr_key = "Xya1V0Bn5G49rBg81lBl2w"
        gr_response = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": gr_key, "isbns": book.isbn}).json()
        gr = gr_response["books"][0]

        # Get book reviews
        reviews = db.execute("SELECT username, rating, comment FROM users JOIN reviews ON users.id = reviews.user_id WHERE reviews.book_id = :book_id",
                                {"book_id": book_id})

        return render_template("book.html", book=book, gr=gr, reviews=reviews)

    # User reach route using "POST" method (post a review)
    if request.method == "POST":

        # Check if user has already posted a review for current book
        if db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id", 
                    {"user_id": session["user_id"], "book_id": book_id}).rowcount > 0:
            flash("You have posted a review for this book.")
            return redirect(url_for('book', book_id=book_id))

        # Get rating and comment
        rating = request.form.get("rating")
        comment = request.form.get("comment")

        # Ensure user has picked a rating
        if rating is None:
            flash("Please rate this book.")
            return redirect(url_for('book', book_id=book_id))

        # Insert review into database
        db.execute("INSERT INTO reviews (user_id, book_id, rating, comment) VALUES (:user_id, :book_id, :rating, :comment)",
                    {"user_id": session["user_id"], "book_id": book_id, "rating": rating, "comment": comment})
        db.commit()

        return redirect(url_for('book', book_id=book_id))

@app.route('/logout')
@login_required
def logout():

    # Forget user
    session.pop('user_id', None)

    return redirect(url_for('index'))

@app.route("/api/<isbn>", methods=["GET"])
@login_required
def api(isbn):

    # Variable for book information
    book = {}

    # Get book information
    row = db.execute("SELECT * FROM books WHERE isbn = :isbn",
                    {"isbn": isbn}).fetchone()
    
    # Ensure the book exists
    if row is None:
        return "No book match that ISBN."

    book["title"] = row.title
    book["author"] = row.author
    book["year"] = row.year
    book["isbn"] = isbn

    # Get average rating and number of reviews
    review = db.execute("SELECT COUNT(*) AS count, SUM(rating) AS sum FROM reviews WHERE book_id = :book_id",
                        {"book_id": row.id}).fetchone()

    # If no review was posted for the book
    if review.count == 0:
        book["review_count"] = 0
        book["average_score"] = 0
    else:    
        book["review_count"] = review.count
        book["average_score"] = round(review.sum / review.count, 2)

    # Create JSON response
    response = jsonify(book)

    return response