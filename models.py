from datetime import datetime

from typing import List

from sqlalchemy import desc

from sqlalchemy.orm import Mapped

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


user_group = db.Table(
    "group_followers",
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("timestamp", db.DateTime, default=datetime.utcnow),
)


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

    followed_groups = db.relationship(
        "Group", secondary=user_group, back_populates="group_followed_by"
    )


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    gname = db.Column(db.Text)
    gtype = db.Column(db.Text)
    group_followed_by = db.relationship(
        "User", secondary=user_group, back_populates="followed_groups"
    )


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    photo = db.Column(db.String(120), nullable=True)
    video = db.Column(db.String(120), nullable=True)
    user = db.relationship("User", backref=db.backref("posts", lazy=True))
    group = db.relationship("Group", backref=db.backref("posts", lazy=True))


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)

    user = db.relationship("User", backref=db.backref("comments", lazy=True))


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


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


def update_profile(user_id, bio, profile_picture):
    user = User.query.get(user_id)
    user.bio = bio
    user.profile_picture = profile_picture

    db.session.commit()


def create_post_db(user_id, post_content, photo=None, video=None):

    new_post = Post(user_id=user_id, content=post_content, photo=photo, video=video)

    db.session.add(new_post)

    db.session.commit()


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
            group_ids = [
                group.id for group in User.query.get(current_user_id).followed_groups
            ]
            return (
                Post.query.filter(
                    (Post.user_id.in_(following_ids))
                    | (Post.user_id == current_user_id)
                    | (Post.group_id.in_(group_ids))
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

def get_posts_by_group(group_id):
    group = Group.query.get(group_id)
    if not group:
        return []

    follower_ids = [follower.id for follower in group.group_followed_by]
    posts = Post.query.filter(Post.user_id.in_(follower_ids)).order_by(Post.timestamp.desc()).all()
    return posts


def add_comment(post_id, user_id, content):
    new_comment = Comment(post_id=post_id, user_id=user_id, content=content)

    db.session.add(new_comment)

    db.session.commit()


def get_comments(post_id):
    return Comment.query.filter_by(post_id=post_id).all()


def like_post(post_id, user_id):
    existing_like = Like.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_like:
        db.session.delete(existing_like)

    else:
        new_like = Like(post_id=post_id, user_id=user_id)

        db.session.add(new_like)

    db.session.commit()


def get_likes(post_id):
    return Like.query.filter_by(post_id=post_id).count()


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


def get_follow_requests(user_id):
    return Follow.query.filter_by(followed_id=user_id, approved=0).all()


def get_follow_status(follower_id, followed_id):
    existing_follow = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    if existing_follow:
        return existing_follow.approved

    return -1


def part_of_group(user_id, group_id):
    association = (
        db.session.query(user_group)
        .filter_by(user_id=user_id, group_id=group_id)
        .first()
    )
    if association:
        return True
    return False


def get_group_by_name(gname):
    group = Group.query.filter(Group.gname == gname).first()
    return group


def get_group_by_id(gid):
    group = Group.query.filter(Group.id == gid).first()
    return group


def toggle_group_follow(userid, groupid, follow):
    user = User.query.get(userid)
    group = Group.query.get(groupid)

    if follow:
        if group not in user.followed_groups:
            user.followed_groups.append(group)
    else:
        if group in user.followed_groups:
            user.followed_groups.remove(group)
    db.session.commit()


def approve_follow_request(follower_id, followed_id):
    follow_request = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    follow_request.approved = 1

    db.session.commit()


def decline_follow_request(follower_id, followed_id):
    follow_request = Follow.query.filter_by(
        follower_id=follower_id, followed_id=followed_id
    ).first()

    db.session.delete(follow_request)

    db.session.commit()


def get_notifications(user_id):
    return get_follow_requests(user_id)


def init_db():
    db.create_all()


def __repr__(self):
    return f"User('{self.username}', '{self.email}', '{self.profile_picture}')"


def __repr__(self):
    return f"Post('{self.content}', '{self.timestamp}')"
