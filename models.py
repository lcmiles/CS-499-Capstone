from datetime import datetime
from typing import List
from sqlalchemy import desc
from sqlalchemy.orm import Mapped
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# association table for saved pets
saved_pets_table = db.Table(
    "saved_pets",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("pet_id", db.Integer, db.ForeignKey("pet.id"), primary_key=True),
)


# table for user information
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text)
    profile_picture = db.Column(
        db.String(100),
        nullable=False,
        default="https://storage.googleapis.com/cs-499-final-project-uploads/profile_pics/default.png",
    )
    is_private = db.Column(db.Boolean, default=False)
    followers: Mapped[List["Follow"]] = db.relationship(
        primaryjoin="and_(User.id==Follow.followed_id, Follow.approved==1)"
    )
    following: Mapped[List["Follow"]] = db.relationship(
        primaryjoin="and_(User.id==Follow.follower_id, Follow.approved==1)"
    )
    saved_pets = db.relationship(
        "Pet",
        secondary=saved_pets_table,
        backref=db.backref("saved_by_users", lazy="dynamic"),
        lazy="dynamic",
    )



class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    photos = db.Column(db.PickleType, nullable=True)  # list of photo URLs
    videos = db.Column(db.PickleType, nullable=True)  # list of video URLs
    user = db.relationship("User", backref=db.backref("posts", lazy=True))


# table for comments
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)

    user = db.relationship("User", backref=db.backref("comments", lazy=True))


# table for likes
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# table for follow relationships
class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # 0 = pending, 1 = accepted
    approved = db.Column(db.Integer, default=0)

    follower: Mapped["User"] = db.relationship(
        primaryjoin="and_(Follow.follower_id==User.id)", overlaps="following"
    )

    followed: Mapped["User"] = db.relationship(
        primaryjoin="and_(Follow.followed_id==User.id)", overlaps="followers"
    )


# table for pet information
class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    sex = db.Column(db.String(50), nullable=False)
    breed = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    vaccination_status = db.Column(db.String(50), nullable=False)
    adoption_fee = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    photo = db.Column(db.String(120), nullable=True)
    is_adopted = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    shelter_id = db.Column(db.Integer, db.ForeignKey('shelter.id'), nullable=True)
    user = db.relationship("User", backref=db.backref("adopted_pets", lazy=True))


class Adoption_Info(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    adopter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    pet_id = db.Column(db.Integer, db.ForeignKey("pet.id"), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    reason_for_adopting = db.Column(db.Text, nullable=False)
    home_type = db.Column(db.String(50), nullable=False)
    children_info = db.Column(db.Text, nullable=True)
    first_time_owner = db.Column(db.Boolean, nullable=False)
    other_pets_info = db.Column(db.Text, nullable=True)
    home_visit_agreement = db.Column(db.Boolean, nullable=False)
    fee_agreement = db.Column(db.Boolean, nullable=False)
    return_agreement = db.Column(db.Boolean, nullable=False)
    signature = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Pending")  # Pending, Approved, Denied

    adopter = db.relationship("User", foreign_keys=[adopter_id])
    owner = db.relationship("User", foreign_keys=[owner_id])
    pet = db.relationship("Pet", backref=db.backref("adoption_applications", lazy=True))


# function to create user in table
def create_user(email, username, password):
    new_user = User(email=email, username=username, password=password)
    db.session.add(new_user)
    db.session.commit()


def get_user_by_email(email):
    return User.query.filter_by(email=email).first()


def get_user_by_username(username):
    return User.query.filter_by(username=username).first()


def get_user_by_id(user_id):
    return User.query.get(user_id)


# function to update profile inf user table
def update_profile(user_id, bio, profile_picture):
    user = User.query.get(user_id)
    user.bio = bio
    user.profile_picture = profile_picture

    db.session.commit()


# function to create post in table
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


# function to get posts from table
def get_posts(user_id=None, current_user_id=None):
    if user_id:
        return (
            Post.query.filter_by(user_id=user_id).order_by(desc(Post.timestamp)).all()
        )
    else:
        if current_user_id:
            following_ids = [
                followed.followed_id
                for followed in Follow.query.filter_by(
                    follower_id=current_user_id, approved=1
                ).all()
            ]
            return (
                Post.query.filter(
                    (Post.user_id.in_(following_ids))
                    | (Post.user_id == current_user_id)
                    | (Post.user.has(User.is_private == False))
                )
                .order_by(desc(Post.timestamp))
                .all()
            )
        return (
            Post.query.filter(Post.user.has(User.is_private == False))
            .order_by(desc(Post.timestamp))
            .all()
        )


def get_post_by_id(post_id):

    return Post.query.filter_by(id=post_id)


# function to add comment to table
def add_comment(post_id, user_id, content):
   
    new_comment = Comment(post_id=post_id, user_id=user_id, content=content)

    db.session.add(new_comment)

    db.session.commit()


# function to get comments for post from table
def get_comments(post_id):
    return Comment.query.filter_by(post_id=post_id).all()


# function to add like to table
def like_post(post_id, user_id):
    
    existing_like = Like.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_like:
        db.session.delete(existing_like)

    else:
        new_like = Like(post_id=post_id, user_id=user_id)

        db.session.add(new_like)

    db.session.commit()


# function to get likes for post from table
def get_likes(post_id):
    return Like.query.filter_by(post_id=post_id).count()


# function to update follow relationship in table
def toggle_follow(follower_id, followed_id):
    existing_follow = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    if existing_follow:
        db.session.delete(existing_follow)

    else:
        new_follow = Follow(follower_id=follower_id, followed_id=followed_id)

        db.session.add(new_follow)

    db.session.commit()


# function to get follower requests for a user from table
def get_follow_requests(user_id):
    return Follow.query.filter_by(followed_id=user_id, approved=0).all()


# function to get follow relationship for users from table
def get_follow_status(follower_id, followed_id):
    existing_follow = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    if existing_follow:
        return existing_follow.approved

    return -1


# function to update follow requests in table with approve
def approve_follow_request(follower_id, followed_id):
    follow_request = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    follow_request.approved = 1

    db.session.commit()


# function to update follow requests in table with decline
def decline_follow_request(follower_id, followed_id):
    follow_request = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    db.session.delete(follow_request)

    db.session.commit()


# function to search pets in table
def search_pets(name=None, breed=None):
    query = Pet.query.filter_by(is_adopted=False)
    if name:
        query = query.filter(Pet.name.contains(name))
    if breed:
        query = query.filter_by(breed=breed)
    return query.all()


# function to set adoption status in table
def mark_pet_as_adopted(pet_id, user_id):
    pet = Pet.query.get(pet_id)
    if pet and not pet.is_adopted:
        pet.is_adopted = True
        pet.user_id = user_id
        db.session.commit()


# function to update saved pets in user table
def save_pet_to_account(pet_id, user_id):
    user = User.query.get(user_id)
    pet = Pet.query.get(pet_id)
    if pet not in user.saved_pets:
        user.saved_pets.append(pet)
        db.session.commit()


# function to get saved pets for a given user
def get_saved_pets(user_id):
    user = User.query.get(user_id)
    return user.saved_pets.all()


# function to get adoption application notifications for a user
def get_adoption_notifications(user_id):
    return Adoption_Info.query.filter_by(owner_id=user_id, status="Pending").all()


# function to initialize tables
def init_db():
    db.create_all()


# helper function for session information
def __repr__(self):
    return f"User('{self.username}', '{self.email}', '{self.profile_picture}')"


# helper function  for post timestamps
def __repr__(self):
    return f"Post('{self.content}', '{self.timestamp}')"


# helper functions
def create_adoption_application(data):
    application = Adoption_Info(**data)
    db.session.add(application)
    db.session.commit()


def get_adoption_applications(owner_id):
    return Adoption_Info.query.filter_by(owner_id=owner_id).all()


def update_adoption_status(application_id, status):
    application = Adoption_Info.query.get(application_id)
    application.status = status
    if status == "Approved":
        pet = Pet.query.get(application.pet_id)
        pet.is_adopted = True
    db.session.commit()


# helper functions
def create_adoption_application(data):
    application = Adoption_Info(**data)
    db.session.add(application)
    db.session.commit()


def get_adoption_applications(owner_id):
    return Adoption_Info.query.filter_by(owner_id=owner_id).all()


def update_adoption_status(application_id, status):
    application = Adoption_Info.query.get(application_id)
    application.status = status
    if status == "Approved":
        pet = Pet.query.get(application.pet_id)
        pet.is_adopted = True
    db.session.commit()

class Shelter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)
    website = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    pets = db.relationship('Pet', backref='shelter', lazy=True)