import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add server directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import (
    app, _threshold_cache, _alert_state, 
    update_threshold, ingest_metrics, export_thresholds, import_thresholds
)
from app.models import Base, Server, User, ServerThreshold, AlertConfig, AlertRecipient
from app.schemas import (
    ServerThresholdUpdate, MetricsIngestSchema, ServerThresholdImport
)

# Use SQLite memory for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

class TestThresholdsLogic(unittest.TestCase):
    def setUp(self):
        # Setup DB
        self.engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        
        # Patch app.main.engine with our test engine
        self.patcher = patch('app.main.engine', self.engine)
        self.patcher.start()
        
        # Reset caches
        _threshold_cache.clear()
        _alert_state.clear()
        
        # Create initial data
        self.server = Server(server_id="srv1", token="token123")
        self.session.add(self.server)
        
        # Default Alert Config (Global)
        self.alert_config = AlertConfig(
            cpu_total_percent=80.0,
            memory_used_percent=80.0,
            disk_used_percent=80.0
        )
        self.session.add(self.alert_config)
        
        # Recipient
        self.recipient = AlertRecipient(email="admin@test.com", name="Admin")
        self.session.add(self.recipient)
        
        self.session.commit()
        
        self.admin_user = {"email": "admin@test.com", "is_admin": True, "id": 1}

    def tearDown(self):
        self.patcher.stop()
        Base.metadata.drop_all(self.engine)
        self.session.close()

    def test_custom_threshold_update_and_cache(self):
        # 1. Update threshold via Logic Function
        payload = ServerThresholdUpdate(cpu_threshold=50.0, memory_threshold=60.0, disk_threshold=70.0)
        
        # Call function directly
        t = update_threshold("srv1", payload, self.admin_user)
        
        self.assertEqual(t.server_id, "srv1")
        self.assertEqual(t.cpu_threshold, 50.0)
        
        # 2. Verify DB persistence
        with Session(self.engine) as sess:
            t_db = sess.query(ServerThreshold).filter_by(server_id="srv1").first()
            self.assertIsNotNone(t_db)
            self.assertEqual(t_db.cpu_threshold, 50.0)
        
        # 3. Verify Cache
        self.assertIn("srv1", _threshold_cache)
        self.assertEqual(_threshold_cache["srv1"]["cpu"], 50.0)

    @patch("app.main.send_alert_email")
    def test_alert_generation_with_custom_threshold(self, mock_send_email):
        # 1. Set Custom Threshold (CPU 50%)
        payload = ServerThresholdUpdate(cpu_threshold=50.0)
        update_threshold("srv1", payload, self.admin_user)
        
        # 2. Ingest Metrics (CPU 60%) -> Should Alert (60 > 50)
        metrics_payload = MetricsIngestSchema(
            server_id="srv1",
            memory={"total": 1000, "used": 200, "free": 800, "cache": 0},
            cpu={"total": 60.0, "per_core": [60.0]},
            disk={"total": 1000, "used": 100, "free": 900, "percent": 10.0},
            docker={"running_containers": 0, "containers": []}
        )
        
        ingest_metrics(metrics_payload, x_auth_token="token123")
        
        # Verify Email Sent
        mock_send_email.assert_called()
        args, _ = mock_send_email.call_args
        self.assertEqual(args[0], "srv1") # server_id
        self.assertEqual(args[1], "CPU Alta") # subject
        self.assertEqual(args[3], 50.0) # threshold used

    @patch("app.main.send_alert_email")
    def test_no_alert_below_custom_threshold(self, mock_send_email):
        # 1. Set Custom Threshold (CPU 90%) - Higher than global (80%)
        payload = ServerThresholdUpdate(cpu_threshold=90.0)
        update_threshold("srv1", payload, self.admin_user)
        
        # 2. Ingest Metrics (CPU 85%) -> Should NOT Alert (85 < 90)
        metrics_payload = MetricsIngestSchema(
            server_id="srv1",
            memory={"total": 1000, "used": 200, "free": 800, "cache": 0},
            cpu={"total": 85.0, "per_core": [85.0]},
            disk={"total": 1000, "used": 100, "free": 900, "percent": 10.0},
            docker={"running_containers": 0, "containers": []}
        )
        
        ingest_metrics(metrics_payload, x_auth_token="token123")
        
        # Verify Email NOT Sent
        mock_send_email.assert_not_called()

    def test_import_export(self):
        # 1. Create thresholds for srv1
        payload = ServerThresholdUpdate(cpu_threshold=40.0)
        update_threshold("srv1", payload, self.admin_user)
        
        # 2. Export
        exported = export_thresholds(self.admin_user)
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0].server_id, "srv1")
        self.assertEqual(exported[0].cpu_threshold, 40.0)
        
        # 3. Import (Update srv1, Add srv2)
        # Need srv2 first
        with Session(self.engine) as sess:
            srv2 = Server(server_id="srv2", token="token456")
            sess.add(srv2)
            sess.commit()
        
        import_payload = [
            ServerThresholdImport(server_id="srv1", cpu_threshold=45.0, memory_threshold=50.0),
            ServerThresholdImport(server_id="srv2", cpu_threshold=30.0)
        ]
        
        result = import_thresholds(import_payload, self.admin_user)
        self.assertEqual(result["count"], 2)
        
        # Verify updates in DB
        with Session(self.engine) as sess:
            t1 = sess.query(ServerThreshold).filter_by(server_id="srv1").first()
            self.assertEqual(t1.cpu_threshold, 45.0)
            
            t2 = sess.query(ServerThreshold).filter_by(server_id="srv2").first()
            self.assertEqual(t2.cpu_threshold, 30.0)
        
        # Verify cache
        self.assertEqual(_threshold_cache["srv1"]["cpu"], 45.0)
        self.assertEqual(_threshold_cache["srv2"]["cpu"], 30.0)

if __name__ == '__main__':
    unittest.main()
