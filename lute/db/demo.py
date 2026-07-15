"""
Functions to manage demo database.

Lute db comes pre-loaded with some demo data.  User can view Tutorial,
wipe data, etc.

The db settings table contains a record, StKey = 'IsDemoData', if the
data is demo.
"""

import os
import sqlite3
from sqlalchemy import text
from lute.language.service import Service as LanguageService
from lute.book.model import Repository
from lute.book.stats import Service as StatsService
from lute.models.repositories import SystemSettingRepository, LanguageRepository
import lute.db.management


def _drop_fts_triggers(session):
    """
    Temporarily drop FTS triggers to speed up bulk inserts.
    """
    drop_statements = [
        "DROP TRIGGER IF EXISTS trig_texts_after_insert_update_fts",
        "DROP TRIGGER IF EXISTS trig_texts_after_delete_update_fts",
        "DROP TRIGGER IF EXISTS trig_texts_after_update_text_update_fts",
        "DROP TRIGGER IF EXISTS trig_books_after_update_title_update_fts",
    ]
    for statement in drop_statements:
        session.execute(text(statement))
    session.commit()


def _recreate_fts_triggers(session):
    """
    Recreate FTS triggers from repeatable migrations file and rebuild index.
    """
    # Commit first to release any active write locks/transactions
    session.commit()

    thisdir = os.path.dirname(os.path.realpath(__file__))
    trig_file = os.path.join(
        thisdir, "schema", "migrations_repeatable", "trig_texts_fts.sql"
    )
    with open(trig_file, "r", encoding="utf-8") as f:
        sql = f.read()

    # Open a separate sqlite3 connection to execute trigger creation
    db_file = session.connection().engine.url.database
    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()

    # Rebuild and optimize FTS index in a single batch
    session.execute(text("INSERT INTO texts_fts(texts_fts) VALUES('rebuild');"))
    session.execute(text("INSERT INTO texts_fts(texts_fts) VALUES('optimize');"))
    session.commit()


class Service:
    "Demo database service."

    def __init__(self, session):
        self.session = session

    def _demo_languages(self):
        """
        Demo languages to be loaded for new users.
        Also loaded during tests.
        """
        return [
            "Arabic",
            "Classical Chinese",
            "Czech",
            "English",
            "French",
            "German",
            "Greek",
            "Hindi",
            "Japanese",
            "Russian",
            "Sanskrit",
            "Spanish",
            "Turkish",
        ]

    def set_load_demo_flag(self):
        "Set the flag."
        repo = SystemSettingRepository(self.session)
        repo.set_value("LoadDemoData", True)
        self.session.commit()

    def remove_load_demo_flag(self):
        "Set the flag."
        repo = SystemSettingRepository(self.session)
        repo.delete_key("LoadDemoData")
        self.session.commit()

    def _flag_exists(self, flagname):
        "True if flag exists, else false."
        repo = SystemSettingRepository(self.session)
        return repo.key_exists(flagname)

    def should_load_demo_data(self):
        return self._flag_exists("LoadDemoData")

    def contains_demo_data(self):
        return self._flag_exists("IsDemoData")

    def remove_flag(self):
        """
        Remove IsDemoData setting.
        """
        if not self.contains_demo_data():
            raise RuntimeError("Can't delete non-demo data.")

        repo = SystemSettingRepository(self.session)
        repo.delete_key("IsDemoData")
        self.session.commit()

    def tutorial_book_id(self):
        """
        Return the book id of the tutorial.
        """
        if not self.contains_demo_data():
            return None
        sql = """select BkID from books
        inner join languages on LgID = BkLgID
        where LgName = 'English' and BkTitle = 'Tutorial'
        """
        r = self.session.execute(text(sql)).first()
        if r is None:
            return None
        return int(r[0])

    def delete_demo_data(self):
        """
        If this is a demo, wipe everything.
        """
        if not self.contains_demo_data():
            raise RuntimeError("Can't delete non-demo data.")
        self.remove_flag()
        lute.db.management.delete_all_data(self.session)

    # Loading demo data.

    def load_demo_languages(self):
        """
        Load selected predefined languages, if they're supported.

        This method will also be called during acceptance tests, so it's public.
        """
        demo_langs = self._demo_languages()
        service = LanguageService(self.session)
        langs = [service.get_language_def(langname).language for langname in demo_langs]
        supported = [lang for lang in langs if lang.is_supported]
        for lang in supported:
            self.session.add(lang)
        self.session.commit()

    def load_demo_stories(self):
        "Load the stories for any languages already loaded."
        _drop_fts_triggers(self.session)

        demo_langs = self._demo_languages()
        service = LanguageService(self.session)
        langdefs = [service.get_language_def(langname) for langname in demo_langs]

        langrepo = LanguageRepository(self.session)
        langdefs = [
            d
            for d in langdefs
            if d.language.is_supported
            and langrepo.find_by_name(d.language.name) is not None
        ]

        r = Repository(self.session)
        for d in langdefs:
            for b in d.books:
                r.add(b)
        r.commit()

        _recreate_fts_triggers(self.session)

        repo = SystemSettingRepository(self.session)
        repo.set_value("IsDemoData", True)
        self.session.commit()

        svc = StatsService(self.session)
        svc.refresh_stats()

    def _db_has_data(self):
        "True of the db contains any language data."
        sql = "select LgID from languages limit 1"
        r = self.session.execute(text(sql)).first()
        return r is not None

    def load_demo_data(self):
        """
        Load the data.
        """
        if self._db_has_data():
            self.remove_load_demo_flag()
            return

        repo = SystemSettingRepository(self.session)
        do_load = repo.get_value("LoadDemoData")
        if do_load is None:
            # Only load if flag is explicitly set.
            return

        do_load = bool(int(do_load))
        if not do_load:
            return

        self.load_demo_languages()
        self.load_demo_stories()
        self.remove_load_demo_flag()
        repo.set_value("IsDemoData", True)
        self.session.commit()
