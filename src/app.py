import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from models import db, Hero, HeroCounter, HeroSynergy, HeroBuild, BuildComment, MatchAnalysis
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///dota2.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)
db.init_app(app)

OPENDOTA_URL = "https://api.opendota.com/api"


# Вспомогательные функции
def fetch_opendota_data(endpoint):
    # Получение данных из опендоты
    try:
        response = requests.get(f"{OPENDOTA_URL}/{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        app.logger.error(f"Error fetching data from OpenDota: {e}")
        return None


def calculate_counters(hero_id):
    # Расчет контрпиков для героя на основе данных опендоты
    data = fetch_opendota_data(f"heroes/{hero_id}/matchups")
    if not data:
        return []

    counters = []
    for matchup in data:
        counter_hero_id = matchup['hero_id']
        games = matchup['games_played']
        wins = matchup['wins']

        if games > 0:
            win_rate = (wins / games) * 100
            # Если винрейт больше 53%, будем считать это контрпиком
            if win_rate > 53:
                counter_hero = Hero.query.get(counter_hero_id)
                if counter_hero:
                    counters.append({
                        'hero_id': counter_hero_id,
                        'win_rate': round(win_rate, 2),
                        'reason': f"High win rate of {round(win_rate, 2)}% in {games} matches"
                    })

    return counters


# Роуты для героев
@app.route('/api/heroes', methods=['GET'])
def get_heroes():
    # Получить всех героев
    try:
        heroes = Hero.query.all()
        return jsonify([{
            'id': hero.id,
            'name': hero.name,
            'localized_name': hero.localized_name,
            'primary_attr': hero.primary_attr,
            'attack_type': hero.attack_type,
            'roles': hero.roles
        } for hero in heroes])
    except SQLAlchemyError as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/heroes/<int:hero_id>', methods=['GET'])
def get_hero(hero_id):
    # Получить героя по ID
    try:
        hero = Hero.query.get_or_404(hero_id)
        return jsonify({
            'id': hero.id,
            'name': hero.name,
            'localized_name': hero.localized_name,
            'primary_attr': hero.primary_attr,
            'attack_type': hero.attack_type,
            'roles': hero.roles
        })
    except SQLAlchemyError as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/heroes/<int:hero_id>/counters', methods=['GET'])
def get_hero_counters(hero_id):
    # Получить контрпики для героя
    try:
        # Проверяем существование героя
        Hero.query.get_or_404(hero_id)

        counters = HeroCounter.query.filter_by(hero_id=hero_id).all()

        # Если данных нет в базе, получаем из OpenDota
        if not counters:
            counters_data = calculate_counters(hero_id)
            for counter_data in counters_data:
                counter = HeroCounter(
                    hero_id=hero_id,
                    counter_hero_id=counter_data['hero_id'],
                    win_rate=counter_data['win_rate'],
                    reason=counter_data.get('reason', '')
                )
                db.session.add(counter)
            db.session.commit()
            counters = HeroCounter.query.filter_by(hero_id=hero_id).all()

        return jsonify([{
            'id': counter.id,
            'counter_hero_id': counter.counter_hero_id,
            'counter_hero_name': counter.counter_hero.localized_name,
            'win_rate': counter.win_rate,
            'reason': counter.reason
        } for counter in counters])
    except SQLAlchemyError as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/heroes/<int:hero_id>/counters', methods=['POST'])
def add_hero_counter(hero_id):
    # Добавить контрпик для героя
    try:
        Hero.query.get_or_404(hero_id)

        data = request.get_json()
        if not data or 'counter_hero_id' not in data: # Проверяем существование героя-контрпика
            return jsonify({'error': 'counter_hero_id is required'}), 400

        Hero.query.get_or_404(data['counter_hero_id'])

        counter = HeroCounter(
            hero_id=hero_id,
            counter_hero_id=data['counter_hero_id'],
            win_rate=data.get('win_rate'),
            reason=data.get('reason', '')
        )

        db.session.add(counter)
        db.session.commit()

        return jsonify({
            'id': counter.id,
            'hero_id': counter.hero_id,
            'counter_hero_id': counter.counter_hero_id,
            'win_rate': counter.win_rate,
            'reason': counter.reason
        }), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/heroes/<int:hero_id>/counters/<int:counter_id>', methods=['PATCH'])
def update_hero_counter(hero_id, counter_id):
    # Обновить контрпик для героя
    try:
        counter = HeroCounter.query.filter_by(id=counter_id, hero_id=hero_id).first_or_404()

        data = request.get_json()
        if 'win_rate' in data:
            counter.win_rate = data['win_rate']
        if 'reason' in data:
            counter.reason = data['reason']

        db.session.commit()

        return jsonify({
            'id': counter.id,
            'hero_id': counter.hero_id,
            'counter_hero_id': counter.counter_hero_id,
            'win_rate': counter.win_rate,
            'reason': counter.reason
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/heroes/<int:hero_id>/counters/<int:counter_id>', methods=['DELETE'])
def delete_hero_counter(hero_id, counter_id):
    #Удалить контрпик для героя
    try:
        counter = HeroCounter.query.filter_by(id=counter_id, hero_id=hero_id).first_or_404()

        db.session.delete(counter)
        db.session.commit()

        return jsonify({'message': 'Counter deleted successfully'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# Роуты для сборок
@app.route('/api/heroes/<int:hero_id>/builds', methods=['GET'])
def get_hero_builds(hero_id):
    # Получить сборки для героя
    try:
        Hero.query.get_or_404(hero_id)

        builds = HeroBuild.query.filter_by(hero_id=hero_id).all()

        return jsonify([{
            'id': build.id,
            'hero_id': build.hero_id,
            'name': build.name,
            'description': build.description,
            'items': build.items,
            'skills': build.skills,
            'talents': build.talents,
            'playstyle': build.playstyle,
            'votes': build.votes,
            'created_at': build.created_at.isoformat()
        } for build in builds])
    except SQLAlchemyError as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/heroes/<int:hero_id>/builds', methods=['POST'])
def create_hero_build(hero_id):
    # Создать сборку для героя
    try:
        Hero.query.get_or_404(hero_id)

        data = request.get_json()
        if not data or 'name' not in data or 'items' not in data or 'skills' not in data:
            return jsonify({'error': 'name, items, and skills are required'}), 400

        build = HeroBuild(
            hero_id=hero_id,
            name=data['name'],
            description=data.get('description', ''),
            items=data['items'],
            skills=data['skills'],
            talents=data.get('talents', []),
            playstyle=data.get('playstyle', 'balanced'),
            votes=data.get('votes', 0)
        )

        db.session.add(build)
        db.session.commit()

        return jsonify({
            'id': build.id,
            'hero_id': build.hero_id,
            'name': build.name,
            'description': build.description,
            'items': build.items,
            'skills': build.skills,
            'talents': build.talents,
            'playstyle': build.playstyle,
            'votes': build.votes,
            'created_at': build.created_at.isoformat()
        }), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/builds/<int:build_id>', methods=['GET'])
def get_build(build_id):
    # Получить сборку по ID
    try:
        build = HeroBuild.query.get_or_404(build_id)

        return jsonify({
            'id': build.id,
            'hero_id': build.hero_id,
            'name': build.name,
            'description': build.description,
            'items': build.items,
            'skills': build.skills,
            'talents': build.talents,
            'playstyle': build.playstyle,
            'votes': build.votes,
            'created_at': build.created_at.isoformat(),
            'updated_at': build.updated_at.isoformat() if build.updated_at else None
        })
    except SQLAlchemyError as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/builds/<int:build_id>', methods=['PATCH'])
def update_build(build_id):
    # Обновить сборку
    try:
        build = HeroBuild.query.get_or_404(build_id)

        data = request.get_json()
        if 'name' in data:
            build.name = data['name']
        if 'description' in data:
            build.description = data['description']
        if 'items' in data:
            build.items = data['items']
        if 'skills' in data:
            build.skills = data['skills']
        if 'talents' in data:
            build.talents = data['talents']
        if 'playstyle' in data:
            build.playstyle = data['playstyle']
        if 'votes' in data:
            build.votes = data['votes']

        db.session.commit()

        return jsonify({
            'id': build.id,
            'hero_id': build.hero_id,
            'name': build.name,
            'description': build.description,
            'items': build.items,
            'skills': build.skills,
            'talents': build.talents,
            'playstyle': build.playstyle,
            'votes': build.votes,
            'updated_at': build.updated_at.isoformat() if build.updated_at else None
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/builds/<int:build_id>', methods=['DELETE'])
def delete_build(build_id):
    # Удалить сборку
    try:
        build = HeroBuild.query.get_or_404(build_id)

        # Сначала удаляем все комментарии к сборке
        BuildComment.query.filter_by(build_id=build_id).delete()

        db.session.delete(build)
        db.session.commit()

        return jsonify({'message': 'Build deleted successfully'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/builds/<int:build_id>/vote', methods=['POST'])
def vote_build(build_id):
    # Проголосовать за сборку
    try:
        build = HeroBuild.query.get_or_404(build_id)

        data = request.get_json()
        vote_value = data.get('vote', 1)  # По умолчанию +1 голос

        build.votes += vote_value
        db.session.commit()

        return jsonify({
            'id': build.id,
            'votes': build.votes
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# Роуты для комментариев к сборкам
@app.route('/api/builds/<int:build_id>/comments', methods=['GET'])
def get_build_comments(build_id):
    # Получить комментарии к сборке
    try:
        HeroBuild.query.get_or_404(build_id)

        comments = BuildComment.query.filter_by(build_id=build_id).order_by(BuildComment.created_at.desc()).all()

        return jsonify([{
            'id': comment.id,
            'build_id': comment.build_id,
            'author': comment.author,
            'content': comment.content,
            'rating': comment.rating,
            'created_at': comment.created_at.isoformat()
        } for comment in comments])
    except SQLAlchemyError as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/builds/<int:build_id>/comments', methods=['POST'])
def create_build_comment(build_id):
    # Создать комментарий к сборке
    try:
        HeroBuild.query.get_or_404(build_id)

        data = request.get_json()
        if not data or 'author' not in data or 'content' not in data:
            return jsonify({'error': 'author and content are required'}), 400

        comment = BuildComment(
            build_id=build_id,
            author=data['author'],
            content=data['content'],
            rating=data.get('rating')
        )

        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'id': comment.id,
            'build_id': comment.build_id,
            'author': comment.author,
            'content': comment.content,
            'rating': comment.rating,
            'created_at': comment.created_at.isoformat()
        }), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/comments/<int:comment_id>', methods=['PATCH'])
def update_build_comment(comment_id):
    # Обновить комментарий к сборке
    try:
        comment = BuildComment.query.get_or_404(comment_id)

        data = request.get_json()
        if 'content' in data:
            comment.content = data['content']
        if 'rating' in data:
            comment.rating = data['rating']

        db.session.commit()

        return jsonify({
            'id': comment.id,
            'build_id': comment.build_id,
            'author': comment.author,
            'content': comment.content,
            'rating': comment.rating,
            'created_at': comment.created_at.isoformat()
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_build_comment(comment_id):
    # Удалить комментарий к сборке
    try:
        comment = BuildComment.query.get_or_404(comment_id)

        db.session.delete(comment)
        db.session.commit()

        return jsonify({'message': 'Comment deleted successfully'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# Роуты для анализа матчей
@app.route('/api/matches/<int:match_id>', methods=['GET'])
def get_match_analysis(match_id):
    # Получить анализ матча
    try:
        analysis = MatchAnalysis.query.filter_by(match_id=match_id).first()

        if not analysis:
            # Если анализа нет в базе, берем из OpenDota
            match_data = fetch_opendota_data(f"matches/{match_id}")
            if not match_data or match_data is None:
                return jsonify({'error': 'Match not found'}), 404

            # Это базовый анализ
            analysis = MatchAnalysis(
                match_id=match_id,
                radiant_win=match_data.get('radiant_win'),
                duration=match_data.get('duration'),
                analysis={
                    'draft_analysis': analyze_draft(match_data),
                    'key_moments': identify_key_moments(match_data),
                    'performance_metrics': calculate_performance_metrics(match_data)
                }
            )

            db.session.add(analysis)
            db.session.commit()

        return jsonify({
            'match_id': analysis.match_id,
            'radiant_win': analysis.radiant_win,
            'duration': analysis.duration,
            'analysis': analysis.analysis,
            'created_at': analysis.created_at.isoformat()
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/matches/<int:match_id>', methods=['PATCH'])
def update_match_analysis(match_id):
    # Обновить анализ матча
    try:
        analysis = MatchAnalysis.query.filter_by(match_id=match_id).first_or_404()

        data = request.get_json()
        if 'analysis' in data:
            analysis.analysis = data['analysis']

        db.session.commit()

        return jsonify({
            'match_id': analysis.match_id,
            'radiant_win': analysis.radiant_win,
            'duration': analysis.duration,
            'analysis': analysis.analysis,
            'created_at': analysis.created_at.isoformat()
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/matches/<int:match_id>', methods=['DELETE'])
def delete_match_analysis(match_id):
    # Удалить анализ матча
    try:
        analysis = MatchAnalysis.query.filter_by(match_id=match_id).first_or_404()

        db.session.delete(analysis)
        db.session.commit()

        return jsonify({'message': 'Match analysis deleted successfully'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# Вспомогательные функции для анализа матчей
def analyze_draft(match_data):
    # Анализ драфта матча
    # Упрощенный анализ драфта
    radiant_heroes = [p['hero_id'] for p in match_data.get('players', [])[:5]]
    dire_heroes = [p['hero_id'] for p in match_data.get('players', [])[5:10]]

    return {
        'radiant_heroes': radiant_heroes,
        'dire_heroes': dire_heroes,
        'synergy_score': calculate_synergy_score(radiant_heroes),
        'counter_score': calculate_counter_score(radiant_heroes, dire_heroes)
    }


def identify_key_moments(match_data):
    # ключевые моменты матча
    key_moments = []

    objectives = match_data.get('objectives')

    # rage moment))
    # то ли из-за того, что данные о матчах хранятся не пожизненно, то или еще
    # из-за чего, но проверка на типы в данных о матче оказалась жизненно необходима
    if objectives is None:
        return key_moments
    if not isinstance(objectives, (list, tuple)):
        app.logger.warning(f"Unexpected objectives type: {type(objectives)}")
        return key_moments

    for objective in objectives:
        try:
            moment = {
                'time': objective.get('time', 0),
                'type': objective.get('type', 'unknown'),
                'slot': objective.get('slot', 0),
                'team': objective.get('team', 0),
                'unit': objective.get('unit', 'unknown'),
                'key': objective.get('key', 'unknown')
            }
            key_moments.append(moment)
        except (AttributeError, TypeError) as e:
            app.logger.warning(f"Error processing objective: {e}")
            continue

    key_moments.sort(key=lambda x: x['time'])

    return key_moments


def calculate_performance_metrics(match_data):
    # Расчет метрик производительности игроков
    metrics = []

    for player in match_data.get('players', []):
        metrics.append({
            'player_slot': player.get('player_slot'),
            'hero_id': player.get('hero_id'),
            'kills': player.get('kills', 0),
            'deaths': player.get('deaths', 0),
            'assists': player.get('assists', 0),
            'gpm': player.get('gold_per_min', 0),
            'xpm': player.get('xp_per_min', 0),
            'hero_damage': player.get('hero_damage', 0),
            'tower_damage': player.get('tower_damage', 0),
            'hero_healing': player.get('hero_healing', 0)
        })

    return metrics


def calculate_synergy_score(heroes):
    # Расчет синергии
    return len(heroes) * 10  # Костыль, придумать алгоритм для расчета синергии не успел.


def calculate_counter_score(team_a, team_b):
    # Расчет контрпиков
    return len(team_a) * 5  # Снова костыль)


# Инициализация базы данных
@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
        heroes_data = fetch_opendota_data("heroes")
        if heroes_data:
            for hero_data in heroes_data:
                hero = Hero(
                    id=hero_data['id'],
                    name=hero_data['name'],
                    localized_name=hero_data['localized_name'],
                    primary_attr=hero_data['primary_attr'],
                    attack_type=hero_data['attack_type'],
                    roles=hero_data['roles']
                )
                db.session.add(hero)

            db.session.commit()
            print("Database initialized with Dota 2 heroes")
        else:
            print("Failed to fetch heroes data from OpenDota")


if __name__ == '__main__':
    app.run(debug=True)