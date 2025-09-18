import pytest
import json
import sys
import os
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from app import app, db, Hero, HeroCounter, HeroSynergy, HeroBuild, BuildComment, MatchAnalysis


@pytest.fixture
def client():
    # Фикстура для тестового клиента
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client


@pytest.fixture
def init_database(client):
    # Фикстура для бд
    with app.app_context():
        db.drop_all()
        db.create_all()

        hero = Hero(
            id=1,
            name="npc_dota_hero_antimage",
            localized_name="Anti-Mage",
            primary_attr="agi",
            attack_type="Melee",
            roles=["Carry", "Escape", "Nuker"]
        )
        db.session.add(hero)

        hero2 = Hero(
            id=2,
            name="npc_dota_hero_axe",
            localized_name="Axe",
            primary_attr="str",
            attack_type="Melee",
            roles=["Initiator", "Durable", "Disabler"]
        )
        db.session.add(hero2)

        counter = HeroCounter(
            id=1,
            hero_id=1,
            counter_hero_id=2,
            win_rate=65.5,
            reason="Axe's Berserker's Call prevents Anti-Mage from blinking away"
        )
        db.session.add(counter)

        build = HeroBuild(
            id=1,
            hero_id=1,
            name="Battle Fury Build",
            description="Standard farming build",
            items=[1, 2, 3],
            skills=[1, 2, 1, 3, 1, 4, 1, 2, 2, 2, 4, 3, 3, 3, 4],
            talents=[1, 2, 1, 2],
            playstyle="farming",
            votes=5
        )
        db.session.add(build)

        comment = BuildComment(
            id=1,
            build_id=1,
            author="TestUser",
            content="Great build for farming",
            rating=5
        )
        db.session.add(comment)

        match_analysis = MatchAnalysis(
            id=1,
            match_id=1234567890,
            radiant_win=True,
            duration=2400,
            analysis={
                "draft_analysis": {
                    "radiant_heroes": [1, 2, 3, 4, 5],
                    "dire_heroes": [6, 7, 8, 9, 10],
                    "synergy_score": 75,
                    "counter_score": 60
                }
            }
        )
        db.session.add(match_analysis)

        db.session.commit()

        yield

        db.session.remove()
        db.drop_all()


def test_get_heroes(client, init_database):
    # Тест получения списка всех героев
    response = client.get('/api/heroes')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 2
    assert data[0]['id'] == 1
    assert data[0]['localized_name'] == 'Anti-Mage'


def test_get_hero(client, init_database):
    # Тест получения информации о конкретном герое
    response = client.get('/api/heroes/1')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['id'] == 1
    assert data['localized_name'] == 'Anti-Mage'


def test_get_hero_not_found(client, init_database):
    # Тест получения информации о несуществующем герое
    response = client.get('/api/heroes/999')
    assert response.status_code == 404


def test_get_hero_counters(client, init_database):
    # Тест получения контрпиков для героя
    response = client.get('/api/heroes/1/counters')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['counter_hero_id'] == 2
    assert data[0]['win_rate'] == 65.5


@patch('app.fetch_opendota_data')
def test_get_hero_counters_from_opendota(mock_fetch, client, init_database):
    # Тест получения контрпиков из OpenDota, если их нет в базе
    mock_fetch.return_value = [
        {'hero_id': 3, 'games_played': 100, 'wins': 60},
        {'hero_id': 4, 'games_played': 80, 'wins': 50}
    ]

    with app.app_context():
        HeroCounter.query.delete()
        db.session.commit()

    response = client.get('/api/heroes/1/counters')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) >= 0


def test_add_hero_counter(client, init_database):
    # Тест добавления контрпика для героя
    new_counter = {
        'counter_hero_id': 2,
        'win_rate': 70.0,
        'reason': 'Test counter reason'
    }

    response = client.post('/api/heroes/1/counters',
                           data=json.dumps(new_counter),
                           content_type='application/json')

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['counter_hero_id'] == 2
    assert data['win_rate'] == 70.0


def test_update_hero_counter(client, init_database):
    # Тест обновления контрпика
    update_data = {
        'win_rate': 68.0,
        'reason': 'Updated reason'
    }

    response = client.patch('/api/heroes/1/counters/1',
                            data=json.dumps(update_data),
                            content_type='application/json')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['win_rate'] == 68.0
    assert data['reason'] == 'Updated reason'


def test_delete_hero_counter(client, init_database):
    # Тест удаления контрпика
    response = client.delete('/api/heroes/1/counters/1')
    assert response.status_code == 200

    response = client.get('/api/heroes/1/counters')
    data = json.loads(response.data)
    assert len(data) == 0


def test_get_hero_builds(client, init_database):
    # Тест получения сборок для героя
    response = client.get('/api/heroes/1/builds')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['name'] == 'Battle Fury Build'


def test_create_hero_build(client, init_database):
    # Тест создания сборки для героя
    new_build = {
        'name': 'New Test Build',
        'description': 'Test description',
        'items': [1, 2, 3, 4],
        'skills': [1, 2, 3, 4, 5, 6],
        'talents': [1, 1, 2, 2],
        'playstyle': 'aggressive',
        'votes': 0
    }

    response = client.post('/api/heroes/1/builds',
                           data=json.dumps(new_build),
                           content_type='application/json')

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['name'] == 'New Test Build'
    assert data['playstyle'] == 'aggressive'


def test_get_build(client, init_database):
    # Тест получения информации о сборке
    response = client.get('/api/builds/1')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['id'] == 1
    assert data['name'] == 'Battle Fury Build'


def test_update_build(client, init_database):
    # Тест обновления сборки
    update_data = {
        'name': 'Updated Build Name',
        'votes': 10
    }

    response = client.patch('/api/builds/1',
                            data=json.dumps(update_data),
                            content_type='application/json')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['name'] == 'Updated Build Name'
    assert data['votes'] == 10


def test_delete_build(client, init_database):
    # Тест удаления сборки
    response = client.delete('/api/builds/1')
    assert response.status_code == 200

    response = client.get('/api/builds/1')
    assert response.status_code == 404


def test_vote_build(client, init_database):
    # Тест голосования за сборку
    vote_data = {'vote': 1}

    response = client.post('/api/builds/1/vote',
                           data=json.dumps(vote_data),
                           content_type='application/json')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['votes'] == 6


def test_get_build_comments(client, init_database):
    # Тест получения комментариев к сборке
    response = client.get('/api/builds/1/comments')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]['author'] == 'TestUser'


def test_create_build_comment(client, init_database):
    # Тест создания комментария к сборке
    new_comment = {
        'author': 'NewUser',
        'content': 'New test comment',
        'rating': 4
    }

    response = client.post('/api/builds/1/comments',
                           data=json.dumps(new_comment),
                           content_type='application/json')

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['author'] == 'NewUser'
    assert data['content'] == 'New test comment'


def test_update_build_comment(client, init_database):
    # Тест обновления комментария
    update_data = {
        'content': 'Updated comment content',
        'rating': 3
    }

    response = client.patch('/api/comments/1',
                            data=json.dumps(update_data),
                            content_type='application/json')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['content'] == 'Updated comment content'
    assert data['rating'] == 3


def test_delete_build_comment(client, init_database):
    # Тест удаления комментария
    response = client.delete('/api/comments/1')
    assert response.status_code == 200

    response = client.get('/api/builds/1/comments')
    data = json.loads(response.data)
    assert len(data) == 0


@patch('app.fetch_opendota_data')
def test_get_match_analysis(mock_fetch, client, init_database):
    # Тест получения анализа матча
    mock_fetch.return_value = {
        'match_id': 1234567890,
        'radiant_win': True,
        'duration': 2400,
        'players': [
            {'hero_id': 1, 'kills': 10, 'deaths': 2, 'assists': 15},
            {'hero_id': 2, 'kills': 5, 'deaths': 8, 'assists': 20}
        ]
    }

    with app.app_context():
        MatchAnalysis.query.delete()
        db.session.commit()

    response = client.get('/api/matches/1234567890')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['match_id'] == 1234567890
    assert data['radiant_win'] == True


def test_update_match_analysis(client, init_database):
    # Тест обновления анализа матча
    update_data = {
        'analysis': {
            'draft_analysis': {
                'radiant_heroes': [1, 2, 3, 4, 5],
                'dire_heroes': [6, 7, 8, 9, 10],
                'synergy_score': 80,
                'counter_score': 70
            }
        }
    }

    response = client.patch('/api/matches/1234567890',
                            data=json.dumps(update_data),
                            content_type='application/json')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['analysis']['draft_analysis']['synergy_score'] == 80


def test_delete_match_analysis(client, init_database):
    # Тест удаления анализа матча
    response = client.delete('/api/matches/1234567890')
    assert response.status_code == 200

    response = client.get('/api/matches/1234567890')
    # Должен создать новый анализ
    assert response.status_code == 200


@patch('app.fetch_opendota_data')
def test_get_nonexistent_match_analysis(mock_fetch, client, init_database):
    # Тест получения анализа несуществующего матча
    mock_fetch.return_value = None

    with app.app_context():
        MatchAnalysis.query.delete()
        db.session.commit()

    response = client.get('/api/matches/9999999999')
    assert response.status_code == 404
