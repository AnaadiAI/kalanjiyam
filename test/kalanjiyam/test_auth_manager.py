from kalanjiyam.auth import KalanjiyamAnonymousUser


def test_unauth_user_has_no_permissions():
    unauth = KalanjiyamAnonymousUser()
    assert not unauth.is_admin
    assert not unauth.is_proofreader
