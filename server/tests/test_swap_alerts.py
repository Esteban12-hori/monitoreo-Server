import sys
import os
import json
import tempfile
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Agregar el directorio server/ al path para resolver imports 'app.*'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Base, Server, AlertConfig, ServerThreshold, Metric, AuditLog
from app.schemas import MetricsIngestSchema
import app.main as main


def _payload(swap_percent=None, swap_used=None, include_swap=True):
    """Construye un payload de métricas; swap opcional (agente antiguo)."""
    d = {
        "server_id": "srv1",
        "memory": {"total": 8000, "used": 2000, "free": 6000, "cache": 100},
        "cpu": {"total": 5.0, "per_core": [5.0]},
        "disk": {"total": 100, "used": 10, "free": 90, "percent": 10.0},
        "docker": {"running_containers": 0, "containers": []},
        "services": [],
    }
    if include_swap:
        used = swap_used if swap_used is not None else (swap_percent or 0) * 20
        d["swap"] = {"total": 2000, "used": used, "free": 2000 - used, "percent": swap_percent or 0}
    return MetricsIngestSchema(**d)


class TestSwapAlerts(unittest.TestCase):
    def setUp(self):
        # DB temporal en archivo (compartida entre las Session que abre ingest_metrics).
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.engine = create_engine(f"sqlite:///{self.tmp.name}", future=True)
        Base.metadata.create_all(self.engine)

        # Parchear el engine global que usa main.ingest_metrics.
        self._orig_engine = main.engine
        main.engine = self.engine

        # Capturar los correos en lugar de enviarlos por red.
        self._orig_send = main.send_alert_email
        self.sent = []
        main.send_alert_email = lambda *a, **k: self.sent.append({"args": a, "kwargs": k})

        # Estado en memoria limpio para cada test.
        main._alert_state.clear()
        main._swap_alert_active.clear()
        main._threshold_cache.clear()

        # Semillas: servidor + config global de umbrales de swap (warning 30 / critical 60).
        with Session(self.engine) as s:
            s.add(Server(server_id="srv1", token="tok"))
            s.add(AlertConfig(
                cpu_total_percent=90, memory_used_percent=90, disk_used_percent=90,
                swap_warning_percent=30, swap_critical_percent=60,
            ))
            s.commit()

    def tearDown(self):
        main.engine = self._orig_engine
        main.send_alert_email = self._orig_send
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def _ingest(self, **kw):
        return main.ingest_metrics(_payload(**kw), x_auth_token="tok")

    def _last_alert(self):
        return self.sent[-1] if self.sent else None

    # Escenario 2: la medición de swap queda registrada.
    def test_swap_metric_persisted(self):
        self._ingest(swap_percent=40, swap_used=800)
        with Session(self.engine) as s:
            row = s.execute(select(Metric).where(Metric.server_id == "srv1")).scalar_one()
        self.assertEqual(row.swap_total, 2000)
        self.assertEqual(row.swap_used, 800)
        self.assertEqual(row.swap_percent, 40)

    # Escenario 3/4: consumo >= advertencia genera una alerta con severidad y ambiente.
    def test_swap_warning_alert(self):
        self._ingest(swap_percent=40)
        self.assertEqual(len(self.sent), 1)
        alert = self._last_alert()
        self.assertEqual(alert["args"][1], "Swap ADVERTENCIA")
        self.assertEqual(alert["kwargs"].get("severity"), "ADVERTENCIA")
        self.assertIsNotNone(alert["kwargs"].get("environment"))
        self.assertEqual(main._swap_alert_active.get("srv1"), "warning")

    # RN07: mientras siga en la misma severidad y dentro del cooldown, no se repite.
    def test_swap_no_duplicate_within_cooldown(self):
        self._ingest(swap_percent=40)
        self._ingest(swap_percent=45)  # sigue en 'warning'
        self.assertEqual(len(self.sent), 1)

    # Escalada advertencia -> crítico envía inmediatamente (salta cooldown).
    def test_swap_escalation_to_critical(self):
        self._ingest(swap_percent=40)
        self._ingest(swap_percent=70)  # >= critical 60
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self._last_alert()["kwargs"].get("severity"), "CRÍTICO")
        self.assertEqual(main._swap_alert_active.get("srv1"), "critical")

    # Escenario 6: al normalizarse envía notificación de recuperación y limpia el estado.
    def test_swap_recovery(self):
        self._ingest(swap_percent=70)
        self.sent.clear()
        self._ingest(swap_percent=10)  # < warning 30
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self._last_alert()["kwargs"].get("is_recovery"))
        self.assertIsNone(main._swap_alert_active.get("srv1"))

    # Escenario 6b: sin alerta previa, volver a normal no dispara nada.
    def test_swap_normal_no_alert(self):
        self._ingest(swap_percent=10)
        self.assertEqual(len(self.sent), 0)

    # Escenario 5: los umbrales por servidor tienen prioridad sobre los globales.
    def test_swap_per_server_threshold_override(self):
        with Session(self.engine) as s:
            s.add(ServerThreshold(server_id="srv1", swap_warning_threshold=10, swap_critical_threshold=15))
            s.commit()
        self._ingest(swap_percent=20)  # 20 < global 30, pero >= override crit 15
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self._last_alert()["kwargs"].get("severity"), "CRÍTICO")

    # Escenario 7: un payload sin swap (agente antiguo) no rompe la ingesta ni alerta.
    def test_no_swap_backward_compatible(self):
        result = self._ingest(include_swap=False)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(self.sent), 0)

    # RN06/Escenario 8: cada alerta y recuperación se audita.
    def test_swap_audit_logged(self):
        self._ingest(swap_percent=70)
        self._ingest(swap_percent=10)
        with Session(self.engine) as s:
            logs = s.execute(select(AuditLog).where(AuditLog.target_type == "swap")).scalars().all()
        actions = sorted(l.action for l in logs)
        self.assertIn("swap_alert", actions)
        self.assertIn("swap_recovery", actions)

    # Un servidor sin swap configurado (total 0) no genera alertas de swap.
    def test_swap_zero_total_ignored(self):
        self._ingest(swap_percent=0, swap_used=0)
        self.assertEqual(len(self.sent), 0)


class TestSwapEmailContent(unittest.TestCase):
    """Escenario 4: el correo incluye ambiente, fecha/hora, severidad y datos de swap."""

    def setUp(self):
        import app.email_utils as eu
        self.eu = eu
        self._orig_conn = eu._has_connectivity
        self._orig_post = eu.requests.post
        self._orig_key = eu.EMAIL_API_KEY
        self._orig_secret = eu.EMAIL_API_SECRET
        eu._has_connectivity = lambda: True
        eu.EMAIL_API_KEY = "x"
        eu.EMAIL_API_SECRET = "y"
        self.captured = {}

        class _Resp:
            status_code = 200

        def _fake_post(url, **kw):
            self.captured["payload"] = json.loads(kw["data"])
            return _Resp()

        eu.requests.post = _fake_post

    def tearDown(self):
        self.eu._has_connectivity = self._orig_conn
        self.eu.requests.post = self._orig_post
        self.eu.EMAIL_API_KEY = self._orig_key
        self.eu.EMAIL_API_SECRET = self._orig_secret

    def _metrics(self):
        return {
            "memory": {"total": 8000, "used": 2000, "free": 6000},
            "disk": {"total": 100, "used": 10, "free": 90, "percent": 10},
            "cpu": {"total": 5},
            "swap": {"total": 2000, "used": 1400, "free": 600, "percent": 70},
        }

    def test_critical_email_content(self):
        self.eu.send_alert_email(
            "srv1", "Swap CRÍTICO", 70.0, 60.0, extra_recipients=["a@b.com"],
            full_metrics=self._metrics(), environment="Producción", severity="CRÍTICO",
        )
        msg = self.captured["payload"]["Messages"][0]
        html, text = msg["HTMLPart"], msg["TextPart"]
        for needle in ["Swap", "Ambiente", "Producción", "CRÍTICO", "Fecha y hora", "1400 MB / 2000 MB"]:
            self.assertIn(needle, html, f"Falta '{needle}' en el HTML")
        self.assertIn("Ambiente", text)
        self.assertIn("Severidad", text)

    def test_recovery_email_is_green(self):
        self.eu.send_alert_email(
            "srv1", "Swap Normalizado", 10.0, 30.0, extra_recipients=["a@b.com"],
            full_metrics={"swap": {"total": 2000, "used": 200, "free": 1800, "percent": 10}},
            environment="Producción", severity="NORMALIZACIÓN", is_recovery=True,
            custom_message="Swap normalizado.",
        )
        msg = self.captured["payload"]["Messages"][0]
        self.assertIn("#2e7d32", msg["HTMLPart"])   # acento verde
        self.assertIn("✅", msg["Subject"])


if __name__ == "__main__":
    unittest.main()
