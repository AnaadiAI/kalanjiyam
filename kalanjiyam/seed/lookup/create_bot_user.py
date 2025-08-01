import logging
import os

from sqlalchemy.orm import Session

from kalanjiyam import consts
from kalanjiyam import database as db
from kalanjiyam.seed.utils.data_utils import create_db


def _create_bot_user(session):
    try:
        password = os.environ["KALANJIYAM_BOT_PASSWORD"]
    except KeyError as e:
        raise ValueError(
            "Please set the KALANJIYAM_BOT_PASSWORD environment variable."
        ) from e

    user = db.User(username=consts.BOT_USERNAME, email="bot@kalanjiyam.org")
    user.set_password(password)
    session.add(user)
    session.commit()


def run():
    """Create page statuses iff they don't exist already."""
    engine = create_db()
    logging.debug("Creating bot user ...")
    with Session(engine) as session:
        user = session.query(db.User).filter_by(username=consts.BOT_USERNAME).first()
        if not user:
            _create_bot_user(session)
    logging.debug("Done.")


if __name__ == "__main__":
    run()
