from kalanjiyam import database as db
from kalanjiyam import queries as q


def test_summary(client):
    resp = client.get("/proofing/users/u-admin/")
    assert resp.status_code == 200


def test_edit__user_match(rama_client):
    resp = rama_client.get("/proofing/users/u-basic/edit")
    assert resp.status_code == 200


def test_edit__user_match__post(rama_client):
    resp = rama_client.get("/proofing/users/u-basic/")
    assert resp.status_code == 200
    assert "Tell others who you are" in resp.text

    resp = rama_client.post(
        "/proofing/users/u-basic/edit", data={"description": "My description"}
    )
    assert resp.status_code == 302

    resp = rama_client.get("/proofing/users/u-basic/")
    assert resp.status_code == 200
    assert "My description" in resp.text


def test_edit__user_mismatch(rama_client):
    resp = rama_client.get("/proofing/users/u-admin/edit")
    assert resp.status_code == 403


def test_edit__user_does_not_exist(rama_client):
    resp = rama_client.get("/proofing/users/unknown/edit")
    assert resp.status_code == 404


def test_edit__unauth(client):
    resp = client.get("/proofing/users/u-basic/edit")
    assert resp.status_code == 302


def test_summary__missing(client):
    resp = client.get("/proofing/users/bad-user/")
    assert resp.status_code == 404


def test_activity(client):
    resp = client.get("/proofing/users/u-admin/activity")
    assert resp.status_code == 200


def test_activity_pagination(client):
    resp = client.get("/proofing/users/u-admin/activity?page=1&per_page=10")
    assert resp.status_code == 200
    assert "Contribution History" in resp.text


def test_activity_date_filter(client):
    resp = client.get("/proofing/users/u-admin/activity?date=2024-01-01")
    assert resp.status_code == 200


def test_activity__missing(client):
    resp = client.get("/proofing/users/bad-user/activity")
    assert resp.status_code == 404


def test_admin(admin_client):
    resp = admin_client.get("/proofing/users/u-admin/admin")
    assert resp.status_code == 200


def test_admin__unauth(rama_client):
    resp = rama_client.get("/proofing/users/u-admin/admin")
    assert resp.status_code == 302


def test_admin__missing(admin_client):
    resp = admin_client.get("/proofing/users/bad-user/admin")
    assert resp.status_code == 404


def _create_org_admin(session):
    user = session.query(db.User).filter_by(username="u-org-admin").first()
    if user is None:
        org = db.Group(slug="test-org", name="Original Org Name")
        session.add(org)
        session.flush()

        role = session.query(db.Role).filter_by(name="org_admin").one()
        user = db.User(username="u-org-admin", email="u_org_admin@siddhasagaram.in")
        user.set_password("pass_org_admin")
        user.organization_id = org.id
        session.add(user)
        session.flush()
        user.roles = [role]
        session.commit()
    return user


def test_edit__org_admin_can_change_org_name_but_not_slug(flask_app):
    with flask_app.app_context():
        session = q.get_session()
        user = _create_org_admin(session)
        org = user.organization
        original_slug = org.slug

        client = flask_app.test_client(user=user)

        # GET should show org name and slug
        resp = client.get(f"/proofing/users/{user.username}/edit")
        assert resp.status_code == 200
        assert "Original Org Name" in resp.text
        assert original_slug in resp.text

        # POST new org name and attempt tampering with slug
        resp = client.post(
            f"/proofing/users/{user.username}/edit",
            data={
                "description": "Updated admin bio",
                "org_name": "New Organization Name",
                "slug": "tampered-slug",
            },
        )
        assert resp.status_code == 302

        session.refresh(org)
        session.refresh(user)
        # Org name updated
        assert org.name == "New Organization Name"
        # Slug remains immutable
        assert org.slug == original_slug
        assert org.slug != "tampered-slug"
        assert user.description == "Updated admin bio"


def test_edit__org_admin_empty_org_name_fails(flask_app):
    with flask_app.app_context():
        session = q.get_session()
        user = _create_org_admin(session)
        client = flask_app.test_client(user=user)

        resp = client.post(
            f"/proofing/users/{user.username}/edit",
            data={
                "description": "Admin bio",
                "org_name": "   ",
            },
        )
        assert resp.status_code == 200
        assert "Organization name cannot be empty" in resp.text


def test_org_dashboard__org_admin_updates_name_only(flask_app):
    with flask_app.app_context():
        session = q.get_session()
        user = _create_org_admin(session)
        org = user.organization
        original_slug = org.slug

        client = flask_app.test_client(user=user)

        resp = client.post(
            "/admin/org/",
            data={
                "action": "update_org_name",
                "name": "Dashboard Renamed Org",
                "slug": "tampered-from-admin",
            },
        )
        assert resp.status_code == 302

        session.refresh(org)
        # Org name updated
        assert org.name == "Dashboard Renamed Org"
        # Slug remains immutable
        assert org.slug == original_slug
        assert org.slug != "tampered-from-admin"


def test_org_dashboard__empty_name_fails(flask_app):
    with flask_app.app_context():
        session = q.get_session()
        user = _create_org_admin(session)
        client = flask_app.test_client(user=user)

        resp = client.post(
            "/admin/org/",
            data={
                "action": "update_org_name",
                "name": "   ",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Organization name is required." in resp.text

