import os

from flask import Flask, session, render_template, request, redirect
from flask_session import Session
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


@app.route("/", methods=["GET", "POST"])
def index():

    # User reach route using "POST" method
    if request.method == "POST":
        # Get username and password
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure username and password are provided
        if not (username and password):
            return render_template("error.html", message="Please enter your username and password.")
        
        # Ensure username and password are correct
        if db.execute("SELECT * FROM users WHERE username = :username AND password = :password", 
                        {"username": username, "password": password}).rowcount == 0:
            return render_template("error.html", message="Incorrect username and/or password.")
        
        return redirect("/search")

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
            return render_template("error.html", message="Please provide your email, username and password.")

        # Ensure passwords match
        if password != password_confirm:
            return render_template("error.html", message="Your passwords do not match.")

        # Check if email exists
        if db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).rowcount > 0:
            return render_template("error.html", message="This email already existed.")

        # Register user into database
        db.execute("INSERT INTO users (email, username, password) VALUES (:email, :username, :password)", 
                    {"email": email, "username": username, "password": password})
        db.commit()
        
        return redirect("/")
        
    # User reach route using "GET" method
    if request.method == "GET":
        return render_template("register.html")

@app.route("/search")
def search():
    return render_template("search.html")