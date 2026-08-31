from decimal import Decimal
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

mysql_module = ModuleType("mysql")
mysql_connector_module = ModuleType("mysql.connector")
mysql_connector_module.connect = MagicMock()
mysql_connector_module.Error = Exception
mysql_module.connector = mysql_connector_module
sys.modules.setdefault("mysql", mysql_module)
sys.modules.setdefault("mysql.connector", mysql_connector_module)

database_module = ModuleType("database")
database_module.DB_CONFIG = {}
sys.modules.setdefault("database", database_module)

auth_module = ModuleType("auth")
auth_module.get_current_user = lambda: None
sys.modules.setdefault("auth", auth_module)

utils_module = ModuleType("utils")
utils_module.generate_uuid = lambda: "test-id"
sys.modules.setdefault("utils", utils_module)

from services.scores import service


def test_external_score_converts_database_decimal_to_float():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"score": Decimal("85.50"), "max_score": 100},
        {"score": Decimal("45.00"), "max_score": 50},
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch("services.scores.service.mysql.connector.connect", return_value=connection):
        score = service._calc_external_score("student-1", "class-1")

    assert score == 87.8
    assert isinstance(score, float)

    total = 0.0
    total += score * 20 / 100
    assert total == 17.56


def test_class_score_can_accumulate_external_decimal_score():
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        {"score": Decimal("85.50"), "max_score": 100},
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    config = {
        "video_enabled": False,
        "quiz_enabled": False,
        "note_enabled": False,
        "flashcard_enabled": False,
        "qa_enabled": False,
        "external_enabled": True,
        "external_weight": 100,
    }

    with (
        patch.object(service, "get_current_user", return_value={"user_id": "teacher-1"}),
        patch.object(service, "get_scoring_config", return_value=(True, config)),
        patch.object(
            service,
            "_get_class_students",
            return_value=[{"id": "student-1", "nickname": "测试学生", "email": ""}],
        ),
        patch.object(service, "_get_class_doc_ids_and_dialog_ids", return_value=([], [])),
        patch("services.scores.service.mysql.connector.connect", return_value=connection),
    ):
        success, result = service.calculate_class_scores("class-1")

    assert success is True
    assert result["students"][0]["dimensions"]["external"] == 85.5
    assert result["students"][0]["total_score"] == 85.5
