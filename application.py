from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir
from time import gmtime, strftime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    
    # Get user's username
    user = db.execute("SELECT username FROM users WHERE id = :id", id = session["user_id"])
    username = str(user[0]["username"])
    
    # Get stock info for user
    stock_info = db.execute("SELECT * FROM stock WHERE username = :username", username = username)
    
    rows = len(stock_info)
    
    total_stock_price = 0
    
    # Include stock price and worth as dict in each row
    for i in range(rows):
        
        # Get current price of stock
        stock = lookup(stock_info[i]["symbol"])
        
        stock_info[i]["current_price"] = int(stock["price"])
        stock_info[i]["current_worth"] = int(stock["price"]) * int(stock_info[i]["amount"])
        
        total_stock_price += int(stock_info[i]["current_worth"])
    
    # Get total worth of user
    cash_in_hand = db.execute("SELECT cash FROM users WHERE username = :username", username = username)
    raw_cash = int(cash_in_hand[0]["cash"])
    total_worth =  raw_cash + total_stock_price
    
    return render_template("index.html", stocks = stock_info, total = total_worth)    
        

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        
        # ensure none of the fields are empty
        if not request.form.get("symbol"):
            return apology("You need to provide a stock name")
        elif not request.form.get("amount"):
            return apology("You need to provide an amount")
            
        # Check the price of the stock
        check_stock = lookup(request.form.get("symbol"))
        
        # Apologize if stock symbol is invalid
        if not check_stock:
            return apology("The stock does not exist")
            
        required_amount = float(request.form.get("amount")) * check_stock["price"]
        total = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        total_money = total[0]["cash"]
        
        # Apologize if cash is insufficient
        if total_money < required_amount:
            return apology("You don't have enough cash to buy these stocks")
         
        user = db.execute("SELECT username FROM users WHERE id = :id", id = session["user_id"]) 
        username = user[0]["username"]
        rows = db.execute("SELECT * FROM stock WHERE username = :username", username = username) 
        number_of_stocks = len(rows)
        
        # Find id of stock which recorded user's transaction in that stock
        counter = 0
        for i in range(number_of_stocks):
            if rows[i]["symbol"] == request.form.get("symbol"):
                counter = rows[i]["id"]
        
        cash = total_money - required_amount
        
        # If 0, buy new stocks        
        if counter == 0:
            db.execute("INSERT INTO stock (username, symbol, amount) VALUES (:username, :symbol, :amount)",
                        username = username, symbol = request.form.get("symbol"), amount = request.form.get("amount"))
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash, id = session["user_id"])            
        
        # else, update
        else :
            info = db.execute("SELECT amount FROM stock WHERE id = :id", id = counter)
            amount_already_got = info[0]["amount"]
            amount = int(amount_already_got) + int(request.form.get("amount"))
            db.execute("UPDATE stock SET amount = :amount WHERE id = :id", amount = amount, id = counter)
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash, id = session["user_id"])
        
        dateandtime = strftime("%Y-%m-%d %H-%M-%S", gmtime())
        db.execute("INSERT INTO history (username, symbol, method, dateandtime, amount, price) VALUES (:username, :symbol, :method, :dateandtime, :amount, :price)",
                    username = username, symbol = request.form.get("symbol"), method = "bought", dateandtime = dateandtime, amount = request.form.get("amount"), price = check_stock["price"])
        
        # return index
        return redirect(url_for("index"))

    else :
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    userinfo = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    username = userinfo[0]["username"]
    rows = db.execute("SELECT * FROM history WHERE username = :username", username = username)
    return render_template("history.html", rows = rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method == "POST":
        
        # ensure user has passed a symbol 
        if not request.form.get("symbol"):
            return apology("Provide a stock name!")
            
        # lookup stock prices    
        row = lookup(request.form.get("symbol"))
        
        if not row:
            return apology("This stock does not exist!")
        
        return render_template("quoted.html", stock_name = row["name"],
                                stock_price = usd(row["price"]), stock_symbol = row["symbol"])   
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    #forget user id
    session.clear()
    
    if request.method == "POST":
        
        # ensure no fields are empty
        if not request.form.get("user_name"):
            return apology("Must provide username!")
        elif not request.form.get("pass") and not request.form.get("confirm_pass"):
            return apology("Must provide password!")
        
        # check if the password and the confirm password match    
        if request.form.get("pass") != request.form.get("confirm_pass"):
            return apology("Password confirmation doesn't match.")
        
        # check if username already exists    
        check = db.execute("SELECT * FROM users WHERE username = :user_name", user_name=request.form.get("user_name"))  
        
        if len(check) != 0:
            return apology("Username already exists")
        else :
            hash = pwd_context.encrypt(request.form.get("pass"))
            db.execute("INSERT INTO users (username, hash) VALUES (:user_name, :hash)",
                        user_name = request.form.get("user_name"), hash = hash)
        log = db.execute("SELECT * FROM users WHERE username = :user_name", user_name=request.form.get("user_name"))                
        
        # log user in by passing him/her in a session
        session["user_id"] = log[0]["id"]
        return redirect(url_for("index"))
    
    else :
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        
        # ensure fields are not empty
        if not request.form.get("symbol"):
            return apology("You must name a stock")
        elif not request.form.get("amount"):
            return apology("You must specify the amount")
            
        userinfo = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"]) 
        username = userinfo[0]["username"]
        
        rows = db.execute("SELECT * FROM stock WHERE username = :username", username = username)
        
        length = len(rows)
        counter = 0
        
        # ensure that the user has the stocks specified
        for i in range(length):
            if str(rows[i]["symbol"]) == str(request.form.get("symbol")):
                counter = 1
                id_stock = rows[i]["id"]
        if counter == 0:
            return apology("You don't have any of these stocks")
    
        amount_get = db.execute("SELECT amount FROM stock WHERE id = :id", id = id_stock)
        amount = amount_get[0]["amount"]
        
        if amount < int(request.form.get("amount")):
            return apology("You don't have these many stocks")
            
        # update stock by decreasing the amount of share the user holds
        amount_now = amount - int(request.form.get("amount"))    
        db.execute("UPDATE stock SET amount = :amount WHERE id = :id", amount = amount_now, id = id_stock)
        
        # incrememt cash in user
        stock_info = lookup(request.form.get("symbol"))
        stockprice = stock_info["price"]
        cashinhand = db.execute("SELECT cash FROM users WHERE username = :username", username = username)
        cash = cashinhand[0]["cash"]
        newcash = cash + float(request.form.get("amount"))*stockprice
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = newcash, id = session["user_id"])
        
        # Delete entry from stock if all of the stock sold
        stockleft = db.execute("SELECT * FROM stock WHERE id = :id", id = id_stock)
        stock_amount = int(stockleft[0]["amount"])
        if stock_amount == 0:
            db.execute("DELETE FROM stock WHERE rowid = :id", id = id_stock)
            
        dateandtime = strftime("%Y-%m-%d %H-%M-%S", gmtime())
        db.execute("INSERT INTO history (username, symbol, method, dateandtime, amount, price) VALUES (:username, :symbol, :method, :dateandtime, :amount, :price)",
                    username = username, symbol = request.form.get("symbol"), method = "sold", dateandtime = dateandtime , amount = request.form.get("amount"), price = stockprice)    
            
        return redirect(url_for("index"))    
    
    else:
        return render_template("sell.html")


@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():
    
    if request.method == "POST":
        if not request.form.get("currentpassword"):
            return apology("You must enter the current password")
        elif not request.form.get("newpassword") and not request.form.get("confirmnewpassword"):
            return apology("You must provide the new passwords")
            
        if request.form.get("newpassword") != request.form.get("confirmnewpassword"):
            return apology("New Password and Confirmation don't match!")
            
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

        # ensure password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("currentpassword"), rows[0]["hash"]):
            return apology("invalid Current Password")        
        
        hash = pwd_context.encrypt(request.form.get("newpassword"))
        db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash = hash, id = session["user_id"])
        
        return redirect(url_for("login"))
        
    else:
        return render_template("changepassword.html")
    