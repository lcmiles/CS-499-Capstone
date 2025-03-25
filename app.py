from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    get_flashed_messages,
)
from flask_cors import CORS
from models import *
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pytz
import secrets
from google.cloud import storage
import google.auth
import os
import traceback
from sqlalchemy import create_engine
import sqlalchemy

app = Flask(__name__)

LOCAL_TESTING = False  # Set True if running locally
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "cs-499-final-project-177edd5f02ab.json"

DB_HOST = "logansserver1511.duckdns.org"  # logan's linux server dns used for sql server
DB_USER = "cs499user"
DB_PASS = "cs499password"
DB_NAME = "cs499_capstone_db"

if LOCAL_TESTING:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    )

app.config["GCS_BUCKET"] = "cs-499-final-project-uploads"
app.config["PROFILE_UPLOAD_FOLDER"] = "cs-499-final-project-uploads/profile_pics"

CORS(app)
db.init_app(app)
app.config["SECRET_KEY"] = secrets.token_hex(16)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

storage_client = storage.Client()
bucket = storage_client.bucket(app.config["GCS_BUCKET"])
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "avi", "mov"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_to_gcs(file, bucket_name, folder):
    credentials, project = google.auth.default()
    client = storage.Client(credentials=credentials, project=project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{folder}/{file.filename}")
    blob.upload_from_file(file)
    return blob.public_url


@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not User.query.first():
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if request.method == "POST":
        user_id = session["user_id"]
        post_content = request.form.get("post")
        photo = None
        video = None
        if "photo" in request.files:
            photo_file = request.files["photo"]
            if photo_file and allowed_file(photo_file.filename):
                if LOCAL_TESTING:
                    photo_filename = secure_filename(photo_file.filename)
                    photo_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], photo_filename
                    )
                    photo_file.save(photo_path)
                    photo = f"uploads/{photo_filename}"
                else:
                    photo = upload_to_gcs(
                        photo_file, app.config["GCS_BUCKET"], "uploads"
                    )
            else:
                flash("Unsupported photo file type.", "error")
        if "video" in request.files:
            video_file = request.files["video"]
            if video_file and allowed_file(video_file.filename):
                if LOCAL_TESTING:
                    video_filename = secure_filename(video_file.filename)
                    video_path = os.path.join(
                        app.config["UPLOAD_FOLDER"], video_filename
                    )
                    video_file.save(video_path)
                    video = f"uploads/{video_filename}"
                else:
                    video = upload_to_gcs(
                        video_file, app.config["GCS_BUCKET"], "uploads"
                    )
            else:
                flash("Unsupported video file type.", "error")
        create_post_db(user_id, post_content, photo, video)
    posts = get_posts(current_user_id=session["user_id"])
    notifs = get_follow_requests(user.id)
    central = pytz.timezone("US/Central")
    for post in posts:
        post.timestamp = post.timestamp.replace(tzinfo=pytz.utc).astimezone(central)
    return render_template("index.html", posts=posts, user=user, notifs=notifs)


@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        user_id = session["user_id"]
        post_content = request.form.get("post")
        pet_name = request.form.get("pet_name")
        pet_breed = request.form.get("pet_breed")
        pet_age = request.form.get("pet_age")
        pet_description = request.form.get("pet_description")
        photos = []
        videos = []
        if "photos" in request.files:
            for photo_file in request.files.getlist("photos"):
                if photo_file and allowed_file(photo_file.filename):
                    photo_url = upload_to_gcs(photo_file, app.config["GCS_BUCKET"], "uploads")
                    photos.append(photo_url)
                else:
                    flash("Unsupported photo file type.", "error")
                    return render_template("create_post.html")
        if not photos:
            flash("At least one photo is required for a pet listing.", "error")
            return render_template("create_post.html")
        if "videos" in request.files:
            for video_file in request.files.getlist("videos"):
                if video_file and allowed_file(video_file.filename):
                    video_url = upload_to_gcs(video_file, app.config["GCS_BUCKET"], "uploads")
                    videos.append(video_url)
                elif video_file.filename:
                    flash("Unsupported video file type.", "error")
                    return render_template("create_post.html")
        create_post_db(user_id, post_content, photos, videos)
        if pet_name and pet_age:
            new_pet = Pet(
                name=pet_name,
                breed=pet_breed,
                age=int(pet_age),
                description=pet_description or "No description provided.",
                photo=photos[0] if photos else None,
                user_id=user_id,
            )
            db.session.add(new_pet)
            db.session.commit()
        return redirect(url_for("index"))
    return render_template("create_post.html")


def create_post_db(user_id, post_content, photos=None, videos=None):
    new_post = Post(
        user_id=user_id,
        content=post_content,
        photos=photos,
        videos=videos,
        timestamp=datetime.utcnow(),
    )
    db.session.add(new_post)
    db.session.commit()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()
        if existing_user:
            flash(
                "Username already taken. Please choose a different username.", "error"
            )
            return redirect(url_for("register"))
        if existing_email:
            flash("Email already taken. Please choose a different email.", "error")
            return redirect(url_for("register"))
        new_user = User(
            username=username, email=email, password=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        session.clear()
        session["user_id"] = new_user.id
        session["username"] = new_user.username
        session["profile_picture"] = new_user.profile_picture
        return redirect(url_for("thankyou"))
    return render_template("register.html")


@app.route("/thankyou", methods=["GET", "POST"])
def thankyou():
    if "user_id" not in session:
        return redirect(url_for("login"))
    get_flashed_messages()
    return render_template("thankyou.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session.clear()
        email = request.form.get("email")
        password = request.form.get("password")
        user = get_user_by_email(email)
        if user:
            if check_password_hash(user.password, password):
                session["user_id"] = user.id
                session["username"] = user.username
                session["profile_picture"] = user.profile_picture
                return redirect(url_for("index"))
            else:
                flash("Incorrect password. Please try again.", "error")
        else:
            flash("Unrecognized email. Please try again.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("profile_picture", None)
    return redirect(url_for("login"))


@app.route("/profile/<username>", methods=["GET"])
def view_profile(username):
    user = get_user_by_username(username)
    if not user:
        return "User not found", 404
    notifs = get_follow_requests(session["user_id"])
    user_posts = get_posts(user_id=user.id)
    central = pytz.timezone("US/Central")
    for post in user_posts:
        post.timestamp = post.timestamp.replace(tzinfo=pytz.utc).astimezone(central)
    return render_template(
        "profile.html",
        session=session,
        user=user,
        get_follow_status=get_follow_status,
        notifs=notifs,
        posts=user_posts,
    )


@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if request.method == "POST":
        bio = request.form.get("bio")
        profile_picture = request.files.get("profile_picture")
        is_private = request.form.get("is_private") == "on"
        if profile_picture:
            if allowed_file(profile_picture.filename):
                user.profile_picture = upload_to_gcs(
                    profile_picture, app.config["GCS_BUCKET"], "profile_pics"
                )
                session["profile_picture"] = user.profile_picture
            else:
                flash("Unsupported profile picture file type.", "error")
                notifs = get_follow_requests(session["user_id"])
                return render_template("edit_profile.html", user=user, notifs=notifs)
        user.bio = bio
        user.is_private = is_private
        db.session.commit()
        return redirect(url_for("view_profile", username=user.username))
    notifs = get_follow_requests(session["user_id"])
    return render_template("edit_profile.html", user=user, notifs=notifs)


@app.route("/follow", methods=["POST"])
def follow():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    followed_id = request.args.get("user")
    followed_user = get_user_by_id(followed_id)
    if not followed_user or not user:
        return "User not found", 404
    action = request.args.get("action")
    if action == "request":
        toggle_follow(user.id, followed_id)
        flash("Follow request has been sent.", "success")
    elif action == "unfollow":
        toggle_follow(user.id, followed_id)
        flash("User has been unfollowed.", "success")
    elif action == "approve":
        approve_follow_request(followed_id, user.id)
        flash("Follow request has been approved.", "success")
    elif action == "decline":
        decline_follow_request(followed_id, user.id)
        flash("Follow request has been declined.", "success")
    return redirect(url_for("view_profile", username=followed_user.username))


@app.route("/post/<post_id>", methods=["GET", "POST"])
def post_page(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if request.method == "POST":
        user_id = session["user_id"]
        comment = request.form.get("comment")
        add_comment(post_id, user_id, comment)
    post = get_post_by_id(post_id).first()
    if not post:
        return "Post not found", 404
    comments = get_comments(post_id)
    likes = get_likes(post_id)
    central = pytz.timezone("US/Central")
    post.timestamp = post.timestamp.replace(tzinfo=pytz.utc).astimezone(central)
    return render_template(
        "post_page.html", post=post, comments=comments, user=user, likes=likes
    )


@app.route("/like/<post_id>", methods=["GET", "POST"])
def server_like(post_id):

    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])

    if request.method == "POST":

        user_id = session["user_id"]

        like_post(post_id, user_id)

    return redirect(url_for("post_page", post_id=post_id))


@app.route("/search", methods=["GET"])
def search_users():
    query = request.args.get("query")
    if query:
        users = User.query.filter(User.username.ilike(f"%{query}%")).all()
    else:
        users = User.query.all()
    return render_template("search.html", users=users, query=query)


@app.errorhandler(500)
def internal_error(error):
    tb = traceback.format_exc()
    return render_template("500.html", error=error, traceback=tb), 500


@app.errorhandler(404)
def internal_error(error):
    return render_template("404.html", error=error), 404


@app.route("/search_pets", methods=["GET"])
def search_pets_route():
    if "user_id" not in session:
        return redirect(url_for("login"))
    query = request.args.get("query")
    if not query:
        flash("Please fill out this field.", "error")
        pets = Pet.query.filter_by(is_adopted=False).all()
    else:
        pets = Pet.query.filter(
            (Pet.name.ilike(f"%{query}%")) | (Pet.breed.ilike(f"%{query}%"))
        ).filter_by(is_adopted=False).all()
    return render_template("search_pets.html", pets=pets)

@app.route("/saved_pets", methods=["GET"])
def saved_pets():
    if "user_id" not in session:
        return redirect(url_for("login"))
    pets = get_saved_pets(session["user_id"])
    return render_template("saved_pets.html", pets=pets)

@app.route("/adopt_pet/<int:pet_id>", methods=["POST"])
def adopt_pet(pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    adopt_pet(pet_id, session["user_id"])
    flash("Pet adopted successfully!", "success")
    return redirect(url_for("index"))

@app.route("/save_pet/<int:pet_id>", methods=["POST"])
def save_pet(pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    save_pet_to_account(pet_id, session["user_id"])
    flash("Pet saved to your account!", "success")
    return redirect(url_for("view_pet", pet_id=pet_id))

@app.route("/view_pet/<int:pet_id>", methods=["GET"])
def view_pet(pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    pet = Pet.query.get(pet_id)
    if not pet:
        return "Pet not found", 404
    user = get_user_by_id(session["user_id"])  # Retrieve the user object
    return render_template("view_pet.html", pet=pet, user=user)  # Pass the user object

@app.route("/remove_saved_pet/<int:pet_id>", methods=["POST"])
def remove_saved_pet(pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    pet = Pet.query.get(pet_id)
    if pet in user.saved_pets:
        user.saved_pets.remove(pet)
        db.session.commit()
        flash("Pet removed from your saved list!", "success")
    return redirect(url_for("view_pet", pet_id=pet_id))

@app.context_processor
def utility_processor():
    return dict(get_likes=get_likes)

if __name__ == "__main__":
    # uncomment line to rebuild sql db with next deployment
    with app.app_context():
        db.drop_all()
        db.create_all()
    app.run(host="0.0.0.0", port=8080)
