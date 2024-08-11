from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar

# Initialize Flask app
app = Flask(__name__)

# Configure secret key for session management
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'

# Initialize CKEditor, Bootstrap, and Gravatar for the Flask app
ckeditor = CKEditor(app)
Bootstrap5(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# Setup SQLAlchemy and define the base class for models
class Base(DeclarativeBase):
    pass


# Configure the SQLite database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'

# Initialize SQLAlchemy with the Flask app
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Initialize Flask-Login manager
login_manager = LoginManager()
login_manager.init_app(app)


# User loader callback for Flask-Login to load a user by ID
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, int(user_id))


# Define User model with relationships to BlogPost and Comment models
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(250))
    name: Mapped[str] = mapped_column(String(1000))

    # Relationships with BlogPost and Comment models
    posts = relationship('BlogPost', back_populates='author')
    comments = relationship('Comment', back_populates='comment_author')


# Define BlogPost model with a relationship to User and Comment models
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # Relationships with User and Comment models
    author = relationship('User', back_populates='posts')
    comments = relationship("Comment", back_populates="parent_post")


# Define Comment model with relationships to User and BlogPost models
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)


    # Relationships with User and BlogPost models
    parent_post = relationship("BlogPost", back_populates="comments")
    comment_author = relationship("User", back_populates="comments")

# Create all the database tables within the application context
with app.app_context():
    db.create_all()


# Decorator to restrict access to routes for admin users only
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


# Route for user registration with password hashing using Werkzeug
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        user_email = form.email.data
        user_password = form.password.data
        user_name = form.name.data

        # Check if the user already exists in the database
        result = db.session.execute(db.select(User).where(User.email == user_email))
        user = result.scalar()
        if user:
            flash("This user already exists, Please login !")
            return redirect(url_for('login'))

        # Create a new user with hashed password
        new_user = User(
            email=user_email,
            password=generate_password_hash(user_password, method='pbkdf2:sha256', salt_length=8),
            name=user_name
        )
        db.session.add(new_user)
        db.session.commit()

        # Log in the new user and redirect to the home page
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form, current_user=current_user)


# Route for user login with email and password verification
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        user_email = form.email.data
        user_pass = form.password.data

        # Retrieve the user from the database
        result = db.session.execute(db.select(User).where(User.email == user_email))
        user = result.scalar()
        if not user:
            flash("This user not exists, please Try again! ")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, user_pass):
            flash("Password Incorrect Try again! ")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))
    return render_template("login.html", form=form, current_user=current_user)


# Route for logging out the user
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


# Route to display all blog posts on the home page
@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


# Route to show a single blog post and allow users to comment on it
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        # Create a new comment and add it to the database
        new_comment = Comment(
            text=form.text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, form=form, current_user=current_user)


# Route for creating a new blog post, accessible only by admin users
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        # Create a new blog post and add it to the database
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


# Route for editing an existing blog post, accessible only by admin users
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        # Update the blog post with the new data and commit changes
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


# Route for deleting a blog post, accessible only by admin users
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    Comment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# Route for displaying the About page
@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


# Run the Flask app in debug mode on port 5002
if __name__ == "__main__":
    app.run(debug=True, port=5002)
