"""Real MySQL snapshot regression. Never run against a shared database."""
import os
import unittest
from sqlalchemy import text
from app import create_app, db
from app.services.game_stock_guard import require_unallocated_inventory

class GameStockSnapshotTest(unittest.TestCase):
    def test_guard_reads_latest_pool_after_parent_lock(self):
        url = os.environ.get('GAMBIT_GAME_OA_TEST_DATABASE_URL', '')
        if not url:
            self.skipTest('isolated MySQL required')
        if not url.startswith('mysql+pymysql://') or '@127.0.0.1:13321/gambit_game_services_test' not in url:
            self.fail('refusing shared database')
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': url})
        with app.app_context():
            engine = db.engine
            if (engine.url.host, engine.url.port, engine.url.database) != ('127.0.0.1', 13321, 'gambit_game_services_test'):
                self.fail('refusing configured shared database')
            params = {'store': 190001, 'game': 190002}
            try:
                with engine.begin() as conn:
                    conn.execute(text('DELETE FROM game_service_stocks WHERE store_id=:store AND board_game_id=:game'), params)
                    conn.execute(text('DELETE FROM board_game_store_inventories WHERE store_id=:store AND board_game_id=:game'), params)
                    conn.execute(text('INSERT INTO board_game_store_inventories (store_id, board_game_id, count) VALUES (:store,:game,3)'), params)
                    conn.execute(text("INSERT INTO game_service_stocks (store_id,board_game_id,kind,description,quantity) VALUES (:store,:game,'rental','',2)"), params)
                # A starts a stale snapshot, analogous to queries during OA authentication.
                db.session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})
                self.assertEqual(db.session.execute(text('SELECT SUM(quantity) FROM game_service_stocks WHERE store_id=:store AND board_game_id=:game'),params).scalar(), 2)
                # B uses the same parent lock as Go to allocate one more copy and commits.
                with engine.begin() as conn:
                    conn.execute(text('SELECT id FROM board_game_store_inventories WHERE store_id=:store AND board_game_id=:game FOR UPDATE'),params).all()
                    conn.execute(text('UPDATE game_service_stocks SET quantity=3 WHERE store_id=:store AND board_game_id=:game'),params)
                # An ordinary read in A remains at 2 even after the parent lock.
                db.session.execute(text('SELECT id FROM board_game_store_inventories WHERE store_id=:store AND board_game_id=:game FOR UPDATE'),params).all()
                self.assertEqual(db.session.execute(text('SELECT SUM(quantity) FROM game_service_stocks WHERE store_id=:store AND board_game_id=:game'),params).scalar(), 2)
                with self.assertRaises(ValueError):
                    require_unallocated_inventory(params['store'], params['game'], 2)
                require_unallocated_inventory(params['store'], params['game'], 3)
            finally:
                db.session.rollback()
                db.session.remove()
                with engine.begin() as conn:
                    conn.execute(text('DELETE FROM game_service_stocks WHERE store_id=:store AND board_game_id=:game'),params)
                    conn.execute(text('DELETE FROM board_game_store_inventories WHERE store_id=:store AND board_game_id=:game'),params)
