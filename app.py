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
import pytz
import secrets
from google.cloud import storage
import google.auth
import os
import traceback
import base64

app = Flask(__name__)

LOCAL_TESTING = False  # set True if running locally
LOCAL_DB = False  # set True if using local database

if LOCAL_TESTING:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
        "cs-499-final-project-bc145992a16c.json"  # gcs service account json
    )
else:
    encoded_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if encoded_credentials:
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        with open("/tmp/service_account.json", "w") as f:
            f.write(decoded_credentials)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/service_account.json"

DB_HOST = "logansserver1511.duckdns.org"  # logan's linux server dns used for sql server
DB_USER = "cs499user"
DB_PASS = "cs499password"
DB_NAME = "cs499_capstone_db"

if LOCAL_DB:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///database.db"  # uri for local database
    )
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"  # uri for remote database
    )

app.config["GCS_BUCKET"] = "cs-499-final-project-uploads"  # google cloud storage bucket
app.config["PROFILE_UPLOAD_FOLDER"] = "cs-499-final-project-uploads/profile_pics"

CORS(app)
db.init_app(app)
app.config["SECRET_KEY"] = secrets.token_hex(16)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_EMAILS = ["lcmiles@uab.edu"]  # hardcoded admin emails

storage_client = storage.Client()
bucket = storage_client.bucket(app.config["GCS_BUCKET"])
ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "mp4",
    "avi",
    "mov",
}  # allowed file upload extensions


# function to define allowed file uploads
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# function to upload files to google cloud storage bucket
def upload_to_gcs(file, bucket_name, folder):
    credentials, project = google.auth.default()
    client = storage.Client(credentials=credentials, project=project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"{folder}/{file.filename}")
    blob.upload_from_file(file)
    return blob.public_url


# route to load home page (index.html)
@app.route("/", methods=["GET", "POST"])
def index():
    if not User.query.first():
        return redirect(url_for("login"))

    user = None
    liked_posts = []
    posts = get_posts()  # fetch public posts by default

    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
        liked_posts = [
            like.post_id
            for like in Like.query.filter_by(user_id=session["user_id"]).all()
        ]
        posts = get_posts(
            current_user_id=session["user_id"]
        )  # fetch posts for logged-in users

    central = pytz.timezone("US/Central")
    for post in posts:
        post.timestamp = post.timestamp.replace(tzinfo=pytz.utc).astimezone(central)

    return render_template("index.html", posts=posts, user=user, liked_posts=liked_posts)


# route to load create_post.html
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if "user_id" not in session:

        flash("You must be logged in to create posts", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        user_id = session["user_id"]
        post_content = request.form.get("post")
        pet_name = request.form.get("pet_name")
        pet_sex = request.form.get("pet_sex")
        pet_breed = request.form.get("pet_breed")
        pet_age = request.form.get("pet_age")
        pet_weight = request.form.get("pet_weight")
        vaccination_status = request.form.get("vaccination_status")
        adoption_fee = request.form.get("adoption_fee")
        pet_description = request.form.get("pet_description")
        photos = []
        videos = []
        if "photos" in request.files:  # if there are photos in post get photo list
            for photo_file in request.files.getlist("photos"):
                if photo_file and allowed_file(
                    photo_file.filename
                ):  # if allowed extension then upload to gcs
                    photo_url = upload_to_gcs(
                        photo_file, app.config["GCS_BUCKET"], "uploads"
                    )
                    photos.append(photo_url)  # append url of photo within db
                else:
                    flash("Unsupported photo file type.", "error")
                    return render_template("create_post.html")
        if not photos:  # require at least one photo for post
            flash("At least one photo is required for a pet listing.", "error")
            return render_template("create_post.html")
        if "videos" in request.files:  # if there are videos in post get list
            for video_file in request.files.getlist("videos"):
                if video_file and allowed_file(
                    video_file.filename
                ):  # verify file extension and upload to gcs
                    video_url = upload_to_gcs(
                        video_file, app.config["GCS_BUCKET"], "uploads"
                    )
                    videos.append(video_url)
                elif video_file.filename:
                    flash("Unsupported video file type.", "error")
                    return render_template("create_post.html")
        create_post_db(
            user_id, post_content, photos, videos
        )  # create post within the db
        if pet_name and pet_age:
            new_pet = Pet(  # create pet in database based off of post information
                name=pet_name,
                sex=pet_sex,
                breed=pet_breed,
                age=int(pet_age),
                weight=float(pet_weight),
                vaccination_status=vaccination_status,
                adoption_fee=float(adoption_fee),
                description=pet_description or "No description provided.",
                photo=photos[0] if photos else None,
                user_id=user_id,
            )
            db.session.add(new_pet)
            db.session.commit()
        return redirect(url_for("index"))
    return render_template("create_post.html")


# function to create post within db
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


# routing to load register.html
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()
        if existing_user:  # check if username exists in db
            flash(
                "Username already taken. Please choose a different username.", "error"
            )
            return redirect(url_for("register"))
        if existing_email:  # check if email exists in db
            flash("Email already taken. Please choose a different email.", "error")
            return redirect(url_for("register"))
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(
                password
            ),  # create user in db, generate hash for password and save to db
        )
        db.session.add(new_user)
        db.session.commit()
        session.clear()
        session["user_id"] = new_user.id  # set session user id
        session["username"] = new_user.username  # set session user name
        session["profile_picture"] = new_user.profile_picture  # set session pfp
        return redirect(
            url_for("thankyou")
        )  # redirect to thank you page after registration
    return render_template("register.html")


# routing for thank you page
@app.route("/thankyou", methods=["GET", "POST"])
def thankyou():
    if "user_id" not in session:
        return redirect(url_for("login"))
    get_flashed_messages()
    return render_template("thankyou.html")


# routing for login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session.clear()
        email = request.form.get("email")  # get email from html form
        password = request.form.get("password")  # get pw from html form
        user = get_user_by_email(email)  # looks up email in db
        if user:  # if user exists
            if check_password_hash(user.password, password):  # verify password
                session["user_id"] = user.id
                session["username"] = user.username
                session["profile_picture"] = user.profile_picture
                return redirect(
                    url_for("index")
                )  # if user iformation correct, set session info and redirect to home page
            else:
                flash("Incorrect password. Please try again.", "error")
        else:
            flash("Unrecognized email. Please try again.", "error")
    return render_template("login.html")


# handles routing for logout
@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("profile_picture", None)
    return redirect(
        url_for("login")
    )  # pop infromation from session stack and redirect to login page


# routing for a given user's profile page
@app.route("/profile/<username>", methods=["GET"])
def view_profile(username):
    user = get_user_by_username(username)  # get the profile user
    if not user:
        return "User not found", 404

    current_user_id = None
    if "user_id" in session:
        current_user_id = session["user_id"]

    user_posts = get_posts(user_id=user.id)  # get the profile user's posts
    central = pytz.timezone("US/Central")
    for post in user_posts:  # format post timestamps
        post.timestamp = post.timestamp.replace(tzinfo=pytz.utc).astimezone(central)

    shelters = user.shelter_roles  # Retrieve shelters the user is staff of
    return render_template(
        "profile.html",
        session=session,
        user=user,
        current_user_id=current_user_id,
        get_follow_status=get_follow_status,
        posts=user_posts,
        shelters=shelters,
    )


# routing for edit profile page
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:

        flash("You must be logged into an account to edit profile.", "error")
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    if request.method == "POST":
        bio = request.form.get("bio")
        profile_picture = request.files.get("profile_picture")
        is_private = request.form.get("is_private") == "on"
        if profile_picture:  # get profile picture for user if set changed in form
            if allowed_file(profile_picture.filename):
                user.profile_picture = upload_to_gcs(
                    profile_picture,
                    app.config["GCS_BUCKET"],
                    "profile_pics",  # upload to gcs if the filename is allowed
                )
                session["profile_picture"] = user.profile_picture  # set session pfp
            else:
                flash("Unsupported profile picture file type.", "error")
                notifs = get_follow_requests(session["user_id"])
                return render_template("edit_profile.html", user=user, notifs=notifs)
        user.bio = bio
        user.is_private = is_private
        db.session.commit()  # commit changes to user information to db
        return redirect(
            url_for("view_profile", username=user.username)
        )  # redirect to profile page after info changed
    notifs = get_follow_requests(session["user_id"])
    return render_template("edit_profile.html", user=user, notifs=notifs)


# routing to handle follow button
@app.route("/follow", methods=["POST"])
def follow():

    if "user_id" not in session:
        flash("You must be logged into an account to follow users.", "error")
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    followed_id = request.args.get("user")
    followed_user = get_user_by_id(followed_id)
    if not followed_user or not user:
        return "User not found", 404
    action = request.args.get("action")
    if action == "request":
        toggle_follow(user.id, followed_id)  # toggle followed status
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


# routing to load page for a given post
@app.route("/post/<post_id>", methods=["GET", "POST"])
def post_page(post_id):
    user = None
    liked_posts = []
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
        liked_posts = [
            like.post_id
            for like in Like.query.filter_by(user_id=session["user_id"]).all()
        ]

    post = get_post_by_id(post_id).first()  # Ensure post is always initialized
    if not post:
        return "Post not found", 404

    if request.method == "POST":
        if "user_id" not in session:
            flash("You must be logged into an account to comment on posts.", "error")
            return redirect(url_for("login"))

        user_id = session["user_id"]
        comment = request.form.get("comment")
        add_comment(
            post_id, user_id, comment
        )  # Add comment to the post in the database

    pet = Pet.query.filter_by(photo=post.photos[0]).first() if post.photos else None
    comments = get_comments(post_id)  # Load comments
    likes = get_likes(post_id)  # Load likes

    central = pytz.timezone("US/Central")
    post.timestamp = post.timestamp.replace(tzinfo=pytz.utc).astimezone(central)

    return render_template(
        "post_page.html",
        post=post,
        comments=comments,
        user=user,
        likes=likes,
        pet=pet,
        liked_posts=liked_posts,
    )


# routing to like posts
@app.route("/like/<post_id>", methods=["GET", "POST"])
def server_like(post_id):

    if "user_id" not in session:
        flash("You must be logged into an account to like posts.", "error")
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])

    if request.method == "POST":

        user_id = session["user_id"]

        like_post(post_id, user_id)  # add like to a post in db

    return redirect(url_for("post_page", post_id=post_id))


# routing to search users in db
@app.route("/search_users", methods=["GET"])
def search_users():

    query = request.args.get("query")
    users = (
        User.query.filter(User.username.ilike(f"%{query}%")).all()
        if query
        else User.query.all()
    )
    return render_template("search.html", users=users, query=query)


# routing to handle server error
@app.errorhandler(500)
def internal_error(error):
    tb = traceback.format_exc()
    user = get_user_by_id(session["user_id"]) if "user_id" in session else None
    return render_template("500.html", error=error, traceback=tb, user=user), 500


# handle page not found error
@app.errorhandler(404)
def not_found_error(error):
    user = get_user_by_id(session["user_id"]) if "user_id" in session else None
    return render_template("404.html", error=error, user=user), 404


# handle forbidden error
@app.errorhandler(403)
def forbidden_error(error):
    user = get_user_by_id(session["user_id"]) if "user_id" in session else None
    return render_template("403.html", error=error, user=user), 403


# handle bad request error
@app.errorhandler(400)
def bad_request_error(error):
    user = get_user_by_id(session["user_id"]) if "user_id" in session else None
    return render_template("400.html", error=error, user=user), 400


# handle timeout error
@app.errorhandler(408)
def request_timeout_error(error):
    user = get_user_by_id(session["user_id"]) if "user_id" in session else None
    return render_template("408.html", error=error, user=user), 408


# routing to search pets in db
@app.route("/search_pets", methods=["GET"])
def search_pets_route():

    # if "user_id" not in session:   this now allows for anyone to search for pets
    # return redirect(url_for("login"))

    query = request.args.get("query")
    if not query:
        pets = Pet.query.all()  # if query blank return all pets
    else:
        pets = Pet.query.filter(  # run query against all pets in db
            (Pet.name.ilike(f"%{query}%"))
            | (Pet.breed.ilike(f"%{query}%"))
            | (Pet.sex.ilike(f"%{query}%"))
            | (Pet.age.ilike(f"%{query}%"))
            | (Pet.weight.ilike(f"%{query}%"))
            | (Pet.vaccination_status.ilike(f"%{query}%"))
            | (Pet.description.ilike(f"%{query}%"))
        ).all()
    return render_template("search_pets.html", pets=pets)


# routing to load saved_pets page
@app.route("/saved_pets", methods=["GET"])
def saved_pets():
    if "user_id" not in session:

        flash("you must be logged into an account to save a pet.", "error")
        return redirect(url_for("login"))

    pets = get_saved_pets(session["user_id"])
    return render_template("saved_pets.html", pets=pets)


# routing to handle adopt pet
@app.route("/adopt_pet/<int:pet_id>", methods=["POST"])
def adopt_pet(pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(
        url_for("adopt_pet_application", pet_id=pet_id)
    )  # redirect to application page


# routing to save pets to account
@app.route("/save_pet/<int:pet_id>", methods=["POST"])
def save_pet(pet_id):

    if "user_id" not in session:
        flash("you must be logged in to save a pets info.", "error")
        return redirect(url_for("login"))

    save_pet_to_account(pet_id, session["user_id"])
    flash("Pet saved to your account", "success")
    return redirect(url_for("saved_pets", pet_id=pet_id))


# routing to load pet page
@app.route("/view_pet/<int:pet_id>", methods=["GET"])
def view_pet(pet_id):
    pet = Pet.query.get(pet_id)
    if not pet:
        return "Pet not found", 404

    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])  # retrieve the user if logged in

    return render_template("view_pet.html", pet=pet, user=user)


# routing to handle unsave pet
@app.route("/remove_saved_pet/<int:pet_id>", methods=["POST"])
def remove_saved_pet(pet_id):

    if "user_id" not in session:

        flash("you must be logged into an account")
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    pet = Pet.query.get(pet_id)
    if pet in user.saved_pets:
        user.saved_pets.remove(pet)
        db.session.commit()
        flash("Pet removed from your saved list", "success")
    return redirect(url_for("saved_pets", pet_id=pet_id))


# helper function to load likes
@app.context_processor
def utility_processor():
    return dict(
        get_likes=get_likes, is_admin=is_admin, is_shelter_staff=is_shelter_staff
    )


# routing to handle adoption application
@app.route("/adopt_pet_application/<int:pet_id>", methods=["GET", "POST"])
def adopt_pet_application(pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    pet = Pet.query.get(pet_id)
    if not pet or pet.is_adopted:
        return "Pet not available for adoption", 404
    if request.method == "POST":
        try:
            age = int(request.form.get("age"))
            if age <= 0:
                raise ValueError("Age must be a positive integer.")
        except ValueError:
            flash("Invalid age. Please enter a positive integer.", "error")
            return render_template("adopt_pet_application.html", pet=pet)

        home_type = request.form.get("home_type")
        if home_type == "Other":
            home_type = request.form.get(
                "other_home_type"
            )  # use the input text if "other" is selected
        data = {
            "adopter_id": session["user_id"],
            "owner_id": pet.user_id,
            "pet_id": pet_id,
            "full_name": request.form.get("full_name"),
            "address": request.form.get("address"),
            "email": request.form.get("email"),
            "phone": request.form.get("phone"),
            "age": request.form.get("age"),
            "reason_for_adopting": request.form.get("reason_for_adopting"),
            "home_type": home_type,
            "children_info": request.form.get("children_info"),
            "first_time_owner": request.form.get("first_time_owner") == "on",
            "other_pets_info": request.form.get("other_pets_info"),
            "home_visit_agreement": request.form.get("home_visit_agreement") == "on",
            "fee_agreement": request.form.get("fee_agreement") == "on",
            "return_agreement": request.form.get("return_agreement") == "on",
            "signature": request.form.get("signature"),
        }
        create_adoption_application(data)  # automatically includes username
        flash("Adoption application submitted successfully", "success")
        return redirect(url_for("view_adoption_applications"))
    return render_template("adopt_pet_application.html", pet=pet)


# routing to handle viewing adoption applications
@app.route("/view_adoption_applications", methods=["GET"])
def view_adoption_applications():
    if "user_id" not in session:
        return redirect(url_for("login"))
    current_user_id = session["user_id"]
    submitted_applications = Adoption_Info.query.filter_by(adopter_id=current_user_id).all()
    incoming_applications = Adoption_Info.query.filter_by(owner_id=current_user_id).all()

    return render_template(
        "view_adoption_applications.html",
        submitted_applications=submitted_applications,
        incoming_applications=incoming_applications,
    )


# routing to handle updating adoption status
@app.route(
    "/update_adoption_status/<int:application_id>/<string:status>", methods=["POST"]
)
def update_adoption_status_route(application_id, status):
    if "user_id" not in session:
        return redirect(url_for("login"))
    update_adoption_status(application_id, status)
    flash(f"Application {status} successfully", "success")
    return redirect(url_for("index"))


@app.route("/mark_notification_viewed/<int:notification_id>", methods=["POST"])
def mark_notification_viewed(notification_id):
    notification = Adoption_Info.query.get(notification_id)
    if notification:
        db.session.delete(notification)  # remove the notification after viewing
        db.session.commit()
    return redirect(url_for("view_pet", pet_id=notification.pet_id))

@app.route("/faq")
def faq():
    return render_template('faq.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.context_processor
def inject_notifications():
    if "user_id" in session:
        current_user_id = session["user_id"]
        follow_requests = get_follow_requests(current_user_id)
        adoption_applications = get_adoption_notifications(current_user_id)
        application_status_notifications = Adoption_Info.query.filter(
            Adoption_Info.adopter_id == current_user_id,
            Adoption_Info.status.in_(["Approved", "Denied"]),
        ).all()
        shelter_requests = []
        shelter_roles = ShelterStaff.query.filter_by(user_id=current_user_id).all()
        session["shelter_roles"] = [
            {"shelter_id": role.shelter_id, "shelter_name": role.shelter.name}
            for role in shelter_roles
        ]
        if is_admin(get_user_by_id(current_user_id).username):
            shelter_requests = Shelter.query.filter_by(is_approved=None).all()

        staff_requests = StaffRequest.query.filter_by(
            user_id=current_user_id, status="Pending"
        ).all()

        notifications = {
            "follow_requests": follow_requests,
            "adoption_applications": adoption_applications,
            "application_status_notifications": application_status_notifications,
            "shelter_requests": shelter_requests,
            "staff_requests": staff_requests,
        }

        return {"notifications": notifications}
    return {
        "notifications": {
            "follow_requests": [],
            "adoption_applications": [],
            "application_status_notifications": [],
            "shelter_requests": [],
            "staff_requests": [],
        }
    }


@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    return {"user": user}


@app.route("/shelters", methods=["GET"])
def view_shelters():
    shelters = Shelter.query.filter_by(is_approved=True).all()  # only approved shelters
    return render_template("shelter_list.html", shelters=shelters)


@app.route("/shelter/<int:shelter_id>", methods=["GET"])
def view_shelter(shelter_id):
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    shelter = Shelter.query.get(shelter_id)
    if not shelter or not shelter.is_approved:
        return "Shelter not found or not approved", 404
    return render_template("shelter_detail.html", shelter=shelter, user=user)


@app.route("/add_shelter", methods=["GET", "POST"])
def add_shelter():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form.get("name")
        location = request.form.get("location")
        email = request.form.get("contact_email")
        website = request.form.get("website")
        description = request.form.get("description")
        shelter = Shelter(
            name=name,
            location=location,
            contact_email=email,
            website=website,
            description=description,
            submitted_by=session["user_id"],
            is_approved=None,  # pending approval
        )
        db.session.add(shelter)
        db.session.commit()
        flash("Shelter submitted for approval", "success")
        return redirect(url_for("view_shelter_requests"))
    return render_template("add_shelter.html")


@app.route("/shelter_requests", methods=["GET"])
def view_shelter_requests():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])  # retrieve the logged-in user
    shelter_requests = Shelter.query.filter_by(
        is_approved=None
    ).all()  # pending requests
    return render_template(
        "shelter_requests.html", shelter_requests=shelter_requests, user=user
    )


@app.route("/admin/approve_shelter/<int:shelter_id>", methods=["POST"])
def approve_shelter(shelter_id):
    if "user_id" not in session or not is_admin(get_user_by_id(session["user_id"]).username):  
        return redirect(url_for("login"))
    shelter = Shelter.query.get(shelter_id)
    if shelter:
        shelter.is_approved = True
        db.session.commit()
        if not ShelterStaff.query.filter_by(
            shelter_id=shelter.id, user_id=shelter.submitted_by
        ).first():
            staff_member = ShelterStaff(
                shelter_id=shelter.id, user_id=shelter.submitted_by
            )
            db.session.add(staff_member)
            db.session.commit()
        flash("Shelter approved and staff member added", "success")
    return redirect(url_for("view_shelter_requests"))


@app.route("/admin/deny_shelter/<int:shelter_id>", methods=["POST"])
def deny_shelter(shelter_id):
    if "user_id" not in session or not is_admin(get_user_by_id(session["user_id"]).username): 
        return redirect(url_for("login"))
    shelter = Shelter.query.get(shelter_id)
    if shelter:
        db.session.delete(shelter)
        db.session.commit()
        flash("Shelter request denied", "success")
    return redirect(url_for("view_shelter_requests"))


@app.route("/shelter/<int:shelter_id>/manage", methods=["GET", "POST"])
def manage_shelter(shelter_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    staff_member = ShelterStaff.query.filter_by(
        shelter_id=shelter_id, user_id=user_id
    ).first()
    if not staff_member:
        flash("You do not have permission to manage this shelter.", "error")
        return redirect(url_for("view_shelters"))

    shelter = Shelter.query.get(shelter_id)
    pets = Pet.query.filter_by(shelter_id=shelter_id).all()
    staff_users = ShelterStaff.query.filter_by(shelter_id=shelter_id).all()
    staff_ids = [staff.user_id for staff in staff_users]
    unadopted_pets = Pet.query.filter_by(shelter_id=shelter_id, is_adopted=False).all()
    unassociated_pets = Pet.query.filter(
        Pet.shelter_id.is_(None),
        Pet.user_id.in_(staff_ids),
    ).all()
    adoption_requests = Adoption_Info.query.filter(
        Adoption_Info.pet_id.in_([pet.id for pet in pets]),
        Adoption_Info.status == "Pending",
    ).all()
    adoption_history = Adoption_Info.query.filter(
        Adoption_Info.pet_id.in_([pet.id for pet in pets]),
        Adoption_Info.status.in_(["Approved", "Denied"]),
    ).all()
    staff = ShelterStaff.query.filter_by(shelter_id=shelter_id).all()

    staff_request_outcomes = StaffRequest.query.filter(
        StaffRequest.requested_by == user_id,
        StaffRequest.status.in_(["Approved", "Denied"]),
    ).all()

    return render_template(
        "manage_shelter.html",
        shelter=shelter,
        pets=pets,
        unadopted_pets=unadopted_pets,
        unassociated_pets=unassociated_pets,
        adoption_requests=adoption_requests,
        adoption_history=adoption_history,
        staff=staff,
        staff_request_outcomes=staff_request_outcomes,
        staff_member=staff_member,
    )


@app.route("/shelter/<int:shelter_id>/add_pet", methods=["POST"])
def add_pet_to_shelter(shelter_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    staff_member = ShelterStaff.query.filter_by(
        shelter_id=shelter_id, user_id=user_id
    ).first()

    if not staff_member:
        flash("You do not have permission to manage this shelter.", "error")
        return redirect(url_for("view_shelters"))

    pet_id = request.form.get("pet_id")
    pet = Pet.query.get(pet_id)

    if pet and pet.shelter_id is None:
        pet.shelter_id = shelter_id
        db.session.commit()
        flash(f"Pet '{pet.name}' has been added to the shelter.", "success")
    else:
        flash(
            "Invalid pet or the pet is already associated with another shelter.",
            "error",
        )

    return redirect(url_for("manage_shelter", shelter_id=shelter_id))


@app.route("/shelter/<int:shelter_id>/request_add_staff", methods=["POST"])
def request_add_staff(shelter_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    is_staff = ShelterStaff.query.filter_by(
        shelter_id=shelter_id, user_id=user_id
    ).first()
    if not is_staff:
        flash("You do not have permission to manage staff for this shelter.", "error")
        return redirect(url_for("view_shelters"))

    requested_user_username = request.form.get("username")
    requested_user = User.query.filter_by(username=requested_user_username).first()
    if not requested_user:
        flash("User with the provided username does not exist.", "error")
        return redirect(url_for("manage_shelter", shelter_id=shelter_id))

    existing_request = StaffRequest.query.filter_by(
        shelter_id=shelter_id, user_id=requested_user.id, status="Pending"
    ).first()
    is_already_staff = ShelterStaff.query.filter_by(
        shelter_id=shelter_id, user_id=requested_user.id
    ).first()

    if existing_request:
        flash("A request for this user is already pending.", "error")
    elif is_already_staff:
        flash("This user is already a staff member.", "error")
    else:
        new_request = StaffRequest(
            shelter_id=shelter_id,
            requested_by=user_id,
            user_id=requested_user.id,
        )
        db.session.add(new_request)
        db.session.commit()
        flash("Staff request sent successfully", "success")

    return redirect(url_for("manage_shelter", shelter_id=shelter_id))


@app.route("/staff_request/<int:request_id>/<string:action>", methods=["POST"])
def handle_staff_request(request_id, action):
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user_id = session["user_id"]
    staff_request = StaffRequest.query.get(request_id)

    if not staff_request or staff_request.user_id != current_user_id:
        flash("Staff request not found or unauthorized.", "error")
        return redirect(url_for("index"))

    if action == "approve":
        staff_request.status = "Approved"
        new_staff_member = ShelterStaff(
            shelter_id=staff_request.shelter_id, user_id=staff_request.user_id
        )
        db.session.add(new_staff_member)
    elif action == "deny":
        staff_request.status = "Denied"
    else:
        flash("Invalid action.", "error")
        return redirect(url_for("index"))

    db.session.commit()
    flash(f"Staff request {action}d successfully", "success")
    return redirect(url_for("index"))


@app.route("/shelter/<int:shelter_id>/remove_pet/<int:pet_id>", methods=["POST"])
def remove_pet_from_shelter(shelter_id, pet_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    staff_member = ShelterStaff.query.filter_by(
        shelter_id=shelter_id, user_id=user_id
    ).first()

    if not staff_member:
        flash("You do not have permission to manage this shelter.", "error")
        return redirect(url_for("view_shelters"))

    pet = Pet.query.get(pet_id)
    if pet and pet.shelter_id == shelter_id:
        pet.shelter_id = None
        db.session.commit()
        flash(f"Pet '{pet.name}' has been removed from the shelter", "success")
    else:
        flash("Invalid pet or the pet is not associated with this shelter.", "error")

    return redirect(url_for("manage_shelter", shelter_id=shelter_id))


@app.route("/edit_post_and_pet/<int:post_id>/<int:pet_id>", methods=["GET", "POST"])
@app.route("/edit_post_and_pet/<int:post_id>", methods=["GET", "POST"])
def edit_post_and_pet(post_id, pet_id=None):
    if "user_id" not in session:
        return redirect(url_for("login"))

    post = Post.query.get(post_id)
    user = get_user_by_id(session["user_id"])
    if not post or (post.user_id != session["user_id"] and not is_admin(user.username)):
        flash("You do not have permission to edit this post.", "error")
        return redirect(url_for("index"))

    pet = Pet.query.get(pet_id) if pet_id else None
    if pet and pet.user_id != session["user_id"] and not is_admin(user.username):
        flash("You do not have permission to edit this pet.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        post.content = request.form.get("content")
        if pet:
            pet.name = request.form.get("name")
            pet.breed = request.form.get("breed")
            pet.age = int(request.form.get("age"))
            pet.weight = float(request.form.get("weight"))
            pet.description = request.form.get("description")
        db.session.commit()
        flash("Changes saved successfully.", "success")
        return redirect(url_for("post_page", post_id=post.id))

    return render_template("edit_post_and_pet.html", post=post, pet=pet)


@app.route("/delete_post_and_pet/<int:post_id>/<int:pet_id>", methods=["POST"])
@app.route("/delete_post_and_pet/<int:post_id>", methods=["POST"])
def delete_post_and_pet(post_id, pet_id=None):
    if "user_id" not in session:
        return redirect(url_for("login"))

    post = Post.query.get(post_id)
    user = get_user_by_id(session["user_id"])
    if not post or (post.user_id != session["user_id"] and not is_admin(user.username)):
        flash("You do not have permission to delete this post.", "error")
        return redirect(url_for("index"))

    pet = Pet.query.get(pet_id) if pet_id else None
    if pet and pet.user_id != session["user_id"] and not is_admin(user.username):
        flash("You do not have permission to delete this pet.", "error")
        return redirect(url_for("index"))

    Like.query.filter_by(post_id=post.id).delete()
    Comment.query.filter_by(post_id=post.id).delete()
    db.session.delete(post)
    if pet:
        db.session.delete(pet)
    db.session.commit()
    flash("Post and associated pet deleted successfully.", "success")
    return redirect(url_for("index"))


@app.route("/shelter/<int:shelter_id>/remove_staff/<int:user_id>", methods=["POST"])
def remove_staff_from_shelter(shelter_id, user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user_id = session["user_id"]
    current_staff_member = ShelterStaff.query.filter_by(shelter_id=shelter_id, user_id=current_user_id).first()

    if not current_staff_member or current_staff_member.id != 1: # ensure the current user is the shelter owner (staff ID 1)
        flash("You do not have permission to remove staff from this shelter.", "error")
        return redirect(url_for("manage_shelter", shelter_id=shelter_id))

    staff_to_remove = ShelterStaff.query.filter_by(shelter_id=shelter_id, user_id=user_id).first()
    if not staff_to_remove:
        flash("Staff member not found.", "error")
        return redirect(url_for("manage_shelter", shelter_id=shelter_id))

    db.session.delete(staff_to_remove)
    db.session.commit()
    flash("Staff member removed successfully.", "success")
    return redirect(url_for("manage_shelter", shelter_id=shelter_id))

if __name__ == "__main__":
    # uncomment line to rebuild sql db with next deployment
    # with app.app_context():
    #     db.drop_all()
    #     db.create_all()
    app.run(host="0.0.0.0", port=8080)
