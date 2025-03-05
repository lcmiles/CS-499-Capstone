from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
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

app = Flask(__name__)

LOCAL_TESTING = False  # Set True if running locally
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "cs-499-final-project-177edd5f02ab.json"

if LOCAL_TESTING:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "mysql+pymysql://root:AIrA$V{q$7:80J77@/cs-499-final-project-db?unix_socket=/cloudsql/cs-499-final-project:us-central1:cs-499-final-project-sql-instance"
    )
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

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
        photo = None
        video = None
        if "photo" in request.files:
            photo_file = request.files["photo"]
            if photo_file and allowed_file(photo_file.filename):
                photo = upload_to_gcs(photo_file, app.config["GCS_BUCKET"], "uploads")
            else:
                flash("Unsupported photo file type.", "error")
                return render_template("create_post.html")
        if "video" in request.files:
            video_file = request.files["video"]
            if video_file and allowed_file(video_file.filename):
                video = upload_to_gcs(video_file, app.config["GCS_BUCKET"], "uploads")
            else:
                flash("Unsupported video file type.", "error")
                return render_template("create_post.html")
        create_post_db(user_id, post_content, photo, video)
        return redirect(url_for("index"))
    return render_template("create_post.html")


def create_post_db(user_id, post_content, photo, video):
    new_post = Post(
        user_id=user_id,
        content=post_content,
        photo=photo,
        video=video,
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
    users = []
    if query == "*":
        users = User.query.all()
    elif query:
        users = User.query.filter(User.username.contains(query)).all()
    return render_template("search.html", users=users, query=query)


@app.errorhandler(500)
def internal_error(error):
    tb = traceback.format_exc()
    return render_template("500.html", error=error, traceback=tb), 500


@app.errorhandler(404)
def internal_error(error):
    return render_template("404.html", error=error), 404


@app.route("/followgroup", methods=["POST"])
def followgroup():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    group_id = request.form.get("groupid")
    action = request.form.get("action")

    if not user_id or not group_id:
        return "Missing user or group ID", 400

    group = get_group_by_id(group_id)

    if action == "follow":
        toggle_group_follow(user_id, group_id, follow=True)
        flash("You are now following ", "success")
    elif action == "unfollow":
        toggle_group_follow(user_id, group_id, follow=False)
        flash("You are now unfollowing ", "success")

    userrelation = get_group_by_id(group_id)
    return redirect(url_for("view_group", groupname=group.gname))


@app.route("/groups/<groupname>", methods=["GET"])
def view_group(groupname):
    if "user_id" not in session:
        return redirect(url_for("login"))

    grp = get_group_by_name(gname=groupname)
    if not grp:
        return "Group not found", 404

    user_id = session["user_id"]
    follow_status = part_of_group(user_id, grp.id)
    
    posts = get_posts_by_group(grp.id)

    return render_template(
        "group_profile.html",
        session=session,
        group=grp,
        get_follow_status=follow_status,
        posts=posts,
    )


@app.route("/searchgroups", methods=["GET"])
def search_groups():
    if "user_id" not in session:
        return redirect(url_for("login"))
    query = request.args.get("gsearch")
    groups = []
    if query == "*":
        groups = Group.query.all()
    elif query:
        groups = Group.query.filter(Group.gname.contains(query)).all()
    return render_template("groups.html", groups=groups, query=query)


@app.route("/create_group", methods=["GET", "POST"])
def create_group():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        user_id = session["user_id"]
        description = request.form.get("description")
        group_name = request.form.get("name")
        checkgname = Group.query.filter(Group.gname == group_name).first()
        if checkgname:
            flash("Found group name already exists", "succcess")
            return redirect(url_for("create_group"))
        else:
            group_type = request.form.get("type")
            create_group_db(user_id, description, group_name, group_type)
            flash("Group Successfully Created", "success")
    return render_template("create_group.html")


def create_group_db(user_id, content, gname, gtype):
    new_group = Group(
        user_id=user_id,
        content=content,
        gname=gname,
        gtype=gtype,
        timestamp=datetime.utcnow(),
    )
    user = get_user_by_id(user_id)
    new_group.group_followed_by.append(user)
    db.session.add(new_group)
    db.session.commit()


if __name__ == "__main__":
    # uncomment line to rebuild cloud sql db with next deployment
    # with app.app_context():
    #     db.drop_all()
    #     db.create_all()
    app.run(host="0.0.0.0", port=8080)