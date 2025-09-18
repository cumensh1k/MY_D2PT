from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Hero(db.Model):
    __tablename__ = 'heroes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    localized_name = db.Column(db.String(100), nullable=False)
    primary_attr = db.Column(db.String(20))
    attack_type = db.Column(db.String(20))
    roles = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    counters = db.relationship('HeroCounter', foreign_keys='HeroCounter.hero_id', backref='hero')
    synergies = db.relationship('HeroSynergy', foreign_keys='HeroSynergy.hero_id', backref='hero')
    builds = db.relationship('HeroBuild', backref='hero')


class HeroCounter(db.Model):
    __tablename__ = 'hero_counters'

    id = db.Column(db.Integer, primary_key=True)
    hero_id = db.Column(db.Integer, db.ForeignKey('heroes.id'), nullable=False)
    counter_hero_id = db.Column(db.Integer, db.ForeignKey('heroes.id'), nullable=False)
    win_rate = db.Column(db.Float)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    counter_hero = db.relationship('Hero', foreign_keys=[counter_hero_id])


class HeroSynergy(db.Model):
    __tablename__ = 'hero_synergies'

    id = db.Column(db.Integer, primary_key=True)
    hero_id = db.Column(db.Integer, db.ForeignKey('heroes.id'), nullable=False)
    synergy_hero_id = db.Column(db.Integer, db.ForeignKey('heroes.id'), nullable=False)
    win_rate = db.Column(db.Float)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    synergy_hero = db.relationship('Hero', foreign_keys=[synergy_hero_id])


class HeroBuild(db.Model):
    __tablename__ = 'hero_builds'

    id = db.Column(db.Integer, primary_key=True)
    hero_id = db.Column(db.Integer, db.ForeignKey('heroes.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    items = db.Column(db.JSON, nullable=False)  # List of item IDs
    skills = db.Column(db.JSON, nullable=False)  # Skill build order
    talents = db.Column(db.JSON)  # Talent choices
    playstyle = db.Column(db.String(50))  # e.g., "aggressive", "defensive"
    votes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    comments = db.relationship('BuildComment', backref='build')


class BuildComment(db.Model):
    __tablename__ = 'build_comments'

    id = db.Column(db.Integer, primary_key=True)
    build_id = db.Column(db.Integer, db.ForeignKey('hero_builds.id'), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer) # оценочка от 1 до 5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MatchAnalysis(db.Model):
    __tablename__ = 'match_analyses'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.BigInteger, nullable=False, unique=True)
    radiant_win = db.Column(db.Boolean)
    duration = db.Column(db.Integer)
    analysis = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
