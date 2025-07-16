from kalanjiyam import database as db
from kalanjiyam import queries as q
from kalanjiyam.enums import SiteRole
from kalanjiyam.utils.user_mixins import KalanjiyamAnonymousUser


def test_anonymous_user():
    u = KalanjiyamAnonymousUser()
    assert not u.is_p1
    assert not u.is_p2
    assert not u.is_proofreader
    assert not u.is_moderator
    assert not u.is_admin
    assert not u.has_role(SiteRole.P1)

    assert u.is_ok


def test_new_authenticated_user(client):
    u = db.User()
    session = q.get_session()
    p1 = session.query(db.Role).filter_by(name=SiteRole.P1).one()

    u.roles = [p1]
    assert u.is_p1
    assert not u.is_p2
    assert u.is_proofreader
    assert not u.is_moderator
    assert not u.is_admin
